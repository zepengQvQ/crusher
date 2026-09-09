"""
P0-RC-05：OpenAPI 请求契约同源 + 请求校验 4xx。
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _fresh_client() -> TestClient:
    get_settings.cache_clear()
    get_task_store.cache_clear()
    get_analyze_text_use_case.cache_clear()
    return TestClient(create_app())


class OpenApiContractTests(unittest.TestCase):
    def test_post_has_request_body_and_product_hint(self) -> None:
        app = create_app()
        schema = app.openapi()
        post = schema["paths"]["/api/v1/analyses"]["post"]
        self.assertIn("requestBody", post)
        body_schema = post["requestBody"]["content"]["application/json"]["schema"]
        # 直接或 $ref 到 CreateAnalysisRequest
        ref = body_schema.get("$ref") or ""
        if not ref and "allOf" in body_schema:
            ref = (body_schema["allOf"][0] or {}).get("$ref", "")
        self.assertIn("CreateAnalysisRequest", ref or json.dumps(body_schema))

        components = schema["components"]["schemas"]
        self.assertIn("CreateAnalysisRequest", components)
        self.assertIn("ProductHint", components)
        self.assertEqual(
            set(components["ProductHint"]["enum"]),
            {"auto", "structured_deposit", "loan"},
        )
        self.assertIn("source_text", components["TaskResponse"]["properties"])
        # ParameterKey 含贷款字段
        keys = set(components["ParameterKey"]["enum"])
        for k in (
            "annual_interest_rate",
            "repayment_method",
            "penalty_interest",
            "prepayment_fee",
        ):
            self.assertIn(k, keys)
        # 内部网关 DTO 不得进 OpenAPI
        self.assertNotIn("LlmExplanation", components)

    def test_disk_openapi_matches_runtime(self) -> None:
        live = create_app().openapi()
        disk = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
        self.assertEqual(disk, live)

    def test_generated_types_include_request_dto(self) -> None:
        gen = (ROOT / "frontend-h5" / "src" / "api" / "generated-types.js").read_text(
            encoding="utf-8"
        )
        self.assertIn("@typedef CreateAnalysisRequest", gen)
        self.assertIn("export const ProductHint", gen)
        self.assertIn("source_text", gen)
        self.assertIn("annual_interest_rate", gen)
        self.assertIn("export const DemoErrorKind", gen)
        openapi = json.loads((ROOT / "contracts" / "openapi.json").read_text(encoding="utf-8"))
        for name in ("CreateAnalysisRequest", "ProductHint", "TaskResponse", "ParameterKey"):
            self.assertIn(name, openapi["components"]["schemas"])
            self.assertIn(f'"{name}"', gen)


class CreateAnalysisValidationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = _fresh_client()

    def test_valid_request_succeeds(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={
                "text": "本产品为结构性存款，期限90天。",
                "product_hint": "structured_deposit",
                "locale": "zh-CN",
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertIn("task_id", res.json())

    def test_blank_text_is_4xx(self) -> None:
        res = self.client.post("/api/v1/analyses", json={"text": "   "})
        self.assertIn(res.status_code, (400, 422))
        blob = json.dumps(res.json(), ensure_ascii=False)
        self.assertNotIn("ValidationError", blob)
        detail = res.json().get("detail")
        if isinstance(detail, dict):
            self.assertIn("message", detail)

    def test_invalid_product_hint_is_4xx(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "product_hint": "insurance"},
        )
        self.assertIn(res.status_code, (400, 422))

    def test_too_long_text(self) -> None:
        settings = get_settings()
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "啊" * (settings.max_input_chars + 1)},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["error_code"], "INPUT_TOO_LONG")

    def test_client_api_key_forbidden(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "api_key": "sk-leak"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["error_code"], "FORBIDDEN_CLIENT_CONFIG")
        self.assertNotIn("sk-leak", json.dumps(res.json()))

    def test_client_base_url_forbidden(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "base_url": "https://evil.example"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["error_code"], "FORBIDDEN_CLIENT_CONFIG")

    def test_invalid_json_is_4xx(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            content="{not-json",
            headers={"Content-Type": "application/json"},
        )
        self.assertIn(res.status_code, (400, 422))

    def test_demo_error_rejected_when_not_mock(self) -> None:
        with mock.patch.dict(
            os.environ,
            {
                "MOCK_MODE": "false",
                "LLM_API_KEY": "sk-test",
                "LLM_BASE_URL": "https://example.test/v1",
                "LLM_MODEL": "deepseek-chat",
            },
        ):
            get_settings.cache_clear()
            get_task_store.cache_clear()
            get_analyze_text_use_case.cache_clear()
            client = TestClient(create_app())
            res = client.post(
                "/api/v1/analyses",
                json={"text": "结构性存款期限90天", "demo_error": "model_timeout"},
            )
            self.assertEqual(res.status_code, 400)
            detail = res.json()["detail"]
            self.assertEqual(detail["error_code"], "DEMO_ERROR_NOT_ALLOWED")
            self.assertIn("demo_error", detail["message"])
        # 退出 patch 后恢复默认 Mock 缓存，避免污染同进程其它用例
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        type(self).client = _fresh_client()

class ClientJsDocTests(unittest.TestCase):
    def test_client_references_generated_typedefs(self) -> None:
        src = (ROOT / "frontend-h5" / "src" / "api" / "client.js").read_text(encoding="utf-8")
        self.assertIn("CreateAnalysisResponse", src)
        self.assertIn("TaskResponse", src)
        self.assertIn("CreateAnalysisRequest", src)
        self.assertIn("generated-types", src)


if __name__ == "__main__":
    unittest.main()
