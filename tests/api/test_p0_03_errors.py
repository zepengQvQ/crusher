"""P0-03：配置、错误码、失败语义验收。"""
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


class P003ConfigAndErrorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        cls.client = TestClient(create_app())

    def test_health_has_no_api_key(self) -> None:
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertNotIn("llm_api_key", body)
        self.assertNotIn("api_key", body)
        payload = json.dumps(body)
        self.assertNotIn("sk-", payload)
        self.assertIn("has_api_key", body)
        self.assertIn("mock_mode", body)

    def test_reject_client_api_key(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={
                "text": "结构性存款期限90天",
                "api_key": "sk-should-not-accept",
            },
        )
        self.assertEqual(res.status_code, 400)
        detail = res.json()["detail"]
        self.assertEqual(detail["error_code"], "FORBIDDEN_CLIENT_CONFIG")
        self.assertNotIn("sk-should-not-accept", json.dumps(res.json()))

    def test_reject_client_base_url(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={
                "text": "结构性存款期限90天",
                "base_url": "https://evil.example/v1",
            },
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["error_code"], "FORBIDDEN_CLIENT_CONFIG")

    def test_input_too_long(self) -> None:
        settings = get_settings()
        text = "啊" * (settings.max_input_chars + 1)
        res = self.client.post("/api/v1/analyses", json={"text": text})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()["detail"]["error_code"], "INPUT_TOO_LONG")

    def test_model_timeout_is_failure_not_safe(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款期限90天", "demo_error": "model_timeout"},
        )
        self.assertEqual(res.status_code, 200)
        task_id = res.json()["task_id"]

        body = None
        for _ in range(40):
            poll = self.client.get(f"/api/v1/analyses/{task_id}")
            self.assertEqual(poll.status_code, 200)
            body = poll.json()
            if body["task_status"] in {"completed", "failed"}:
                break
            time.sleep(0.15)

        assert body is not None
        self.assertEqual(body["task_status"], "failed")
        self.assertTrue(body["is_failure"])
        self.assertEqual(body["error_code"], "MODEL_TIMEOUT")
        self.assertIn("模型调用失败", body["error_message"])
        self.assertIsNone(body["report"])
        # 不得出现“未发现风险”文案
        blob = json.dumps(body, ensure_ascii=False)
        self.assertNotIn("未发现风险", blob)
        self.assertNotIn("没有风险", blob)

    def test_task_not_found_message(self) -> None:
        res = self.client.get("/api/v1/analyses/tsk_not_exist")
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["detail"]["error_code"], "TASK_NOT_FOUND")
        self.assertIn("重启", res.json()["detail"]["message"])


if __name__ == "__main__":
    unittest.main()
