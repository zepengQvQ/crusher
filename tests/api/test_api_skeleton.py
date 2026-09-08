"""API 冒烟：创建任务并轮询到完成（不依赖真实模型）。"""
from __future__ import annotations

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


class ApiSkeletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        cls.client = TestClient(create_app())

    def test_health(self) -> None:
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

    def test_create_and_poll_analysis(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "本产品为结构性存款，期限90天。"},
        )
        self.assertEqual(res.status_code, 200)
        task_id = res.json()["task_id"]
        self.assertTrue(task_id)

        report = None
        for _ in range(40):
            poll = self.client.get(f"/api/v1/analyses/{task_id}")
            self.assertEqual(poll.status_code, 200)
            body = poll.json()
            if body["task_status"] == "completed":
                self.assertFalse(body["is_failure"])
                report = body["report"]
                break
            if body["task_status"] == "failed":
                self.fail(f"unexpected failed: {body}")
            time.sleep(0.2)
        self.assertIsNotNone(report)
        self.assertIn("plain_language", report)
        self.assertIn("key_parameters", report)


if __name__ == "__main__":
    unittest.main()
