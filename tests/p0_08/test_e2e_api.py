"""
P0-08：API 串联（成功 / 部分成功 / 失败 / 超时 / 非法 JSON）+ mock 演示包。
"""
from __future__ import annotations

import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

DEMO_PACK = ROOT / "tests" / "fixtures" / "demo" / "mock_smoke_pack.json"


def _fresh_client() -> TestClient:
    get_settings.cache_clear()
    get_task_store.cache_clear()
    get_analyze_text_use_case.cache_clear()
    return TestClient(create_app())


def _wait(client: TestClient, task_id: str) -> dict:
    for _ in range(50):
        body = client.get(f"/api/v1/analyses/{task_id}").json()
        if body["task_status"] in {"completed", "failed"}:
            return body
        time.sleep(0.12)
    raise AssertionError(f"timeout task={task_id}")


class ApiE2ETests(unittest.TestCase):
    def test_success_path(self):
        client = _fresh_client()
        res = client.post(
            "/api/v1/analyses",
            json={
                "text": "本产品为结构性存款，期限90天，到期年化收益率为4.80%。",
                "product_hint": "structured_deposit",
            },
        )
        self.assertEqual(res.status_code, 200)
        body = _wait(client, res.json()["task_id"])
        self.assertEqual(body["task_status"], "completed")
        self.assertFalse(body["is_failure"])
        self.assertIsNotNone(body["report"])
        self.assertIn("key_parameters", body["report"])

    def test_partial_success_has_disclosed_and_missing(self):
        client = _fresh_client()
        res = client.post(
            "/api/v1/analyses",
            json={
                "text": "本产品为结构性存款，期限90天。",
                "product_hint": "structured_deposit",
            },
        )
        body = _wait(client, res.json()["task_id"])
        self.assertEqual(body["task_status"], "completed")
        params = {p["key"]: p for p in body["report"]["key_parameters"]}
        self.assertEqual(params["term"]["status"], "document_fact")
        self.assertEqual(params["principal_protection"]["status"], "not_disclosed")
        extract = next(s for s in body["stages"] if s["name"] == "extract")
        self.assertEqual(extract["status"], "partial")

    def test_timeout_is_failure_not_empty_safe(self):
        client = _fresh_client()
        res = client.post(
            "/api/v1/analyses",
            json={"text": "任意", "demo_error": "model_timeout"},
        )
        body = _wait(client, res.json()["task_id"])
        self.assertEqual(body["task_status"], "failed")
        self.assertTrue(body["is_failure"])
        self.assertEqual(body["error_code"], "MODEL_TIMEOUT")
        self.assertIsNone(body["report"])

    def test_invalid_json_is_failure(self):
        client = _fresh_client()
        res = client.post(
            "/api/v1/analyses",
            json={"text": "任意", "demo_error": "invalid_json"},
        )
        body = _wait(client, res.json()["task_id"])
        self.assertEqual(body["task_status"], "failed")
        self.assertEqual(body["error_code"], "INVALID_MODEL_JSON")
        self.assertIsNone(body["report"])

    def test_rate_limited_is_failure(self):
        client = _fresh_client()
        res = client.post(
            "/api/v1/analyses",
            json={"text": "任意", "demo_error": "rate_limited"},
        )
        body = _wait(client, res.json()["task_id"])
        self.assertEqual(body["task_status"], "failed")
        self.assertEqual(body["error_code"], "RATE_LIMITED")

    def test_mock_smoke_pack(self):
        pack = json.loads(DEMO_PACK.read_text(encoding="utf-8"))
        client = _fresh_client()
        for case in pack["cases"]:
            payload = {
                "text": case["text"],
                "product_hint": case.get("product_hint") or "auto",
            }
            if case.get("demo_error"):
                payload["demo_error"] = case["demo_error"]
            res = client.post("/api/v1/analyses", json=payload)
            self.assertEqual(res.status_code, 200, case["name"])
            body = _wait(client, res.json()["task_id"])
            self.assertEqual(
                body["task_status"],
                case["expect_task_status"],
                case["name"],
            )
            if case.get("expect_error_code"):
                self.assertEqual(body["error_code"], case["expect_error_code"], case["name"])
                self.assertTrue(body["is_failure"], case["name"])
                self.assertIsNone(body["report"], case["name"])


if __name__ == "__main__":
    unittest.main()
