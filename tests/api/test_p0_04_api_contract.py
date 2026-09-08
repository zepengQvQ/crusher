"""P0-04 验收：API 报告强类型 + 失败空 findings 不等于没风险。"""
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
from app.domain.models import AnalysisReport  # noqa: E402
from app.main import create_app  # noqa: E402


class P004ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        cls.client = TestClient(create_app())

    def _wait_terminal(self, task_id: str) -> dict:
        body = None
        for _ in range(40):
            poll = self.client.get(f"/api/v1/analyses/{task_id}")
            self.assertEqual(poll.status_code, 200)
            body = poll.json()
            if body["task_status"] in {"completed", "failed"}:
                return body
            time.sleep(0.15)
        self.fail(f"task not terminal: {body}")

    def test_completed_report_matches_analysis_report_schema(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "本产品为结构性存款，期限90天。"},
        )
        self.assertEqual(res.status_code, 200)
        body = self._wait_terminal(res.json()["task_id"])
        self.assertEqual(body["task_status"], "completed")
        self.assertFalse(body["is_failure"])
        # 必须能被强类型 Report 解析；缺字段/错枚举会抛错
        report = AnalysisReport.model_validate(body["report"])
        self.assertIn("不进行用户适当性评估", report.disclaimer)
        self.assertTrue(hasattr(report, "product_risk_grade"))
        # findings 允许为空，但是成功态
        self.assertIsInstance(report.findings, list)

    def test_failed_empty_findings_still_failure(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "demo_error": "model_timeout"},
        )
        body = self._wait_terminal(res.json()["task_id"])
        self.assertEqual(body["task_status"], "failed")
        self.assertTrue(body["is_failure"])
        self.assertIsNone(body["report"])
        self.assertEqual(body["error_code"], "MODEL_TIMEOUT")
        # 即使未来误塞 findings=[]，前端也应看 is_failure；此处契约是 report=None
        self.assertNotIn("未发现风险", str(body))

    def test_reject_unknown_request_field(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "fitness_score": 99},
        )
        self.assertEqual(res.status_code, 422)

    def test_invalid_demo_error_enum(self) -> None:
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": "结构性存款", "demo_error": "爆炸"},
        )
        self.assertEqual(res.status_code, 422)


if __name__ == "__main__":
    unittest.main()
