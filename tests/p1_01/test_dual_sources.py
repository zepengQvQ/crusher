"""P1-01：双材料对照固定样例与验收测试。"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase  # noqa: E402
from app.domain.models import DualAnalysisRequest  # noqa: E402
from app.domain.models.p1_enums import ClaimStatus  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


class DualSourcesGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.uc = AnalyzeDualSourcesUseCase()

    def _run_fixture(self, name: str):
        data = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
        report = self.uc.execute(
            DualAnalysisRequest(
                sales_text=data["sales_text"],
                official_text=data["official_text"],
            )
        )
        return data, report

    def test_confirmed(self) -> None:
        data, report = self._run_fixture("confirmed.json")
        statuses = {c.status.value for c in report.comparisons}
        self.assertIn(ClaimStatus.confirmed.value, statuses)
        hit = next(c for c in report.comparisons if c.status == ClaimStatus.confirmed)
        self.assertIsNotNone(hit.sales_claim)
        self.assertIsNotNone(hit.official_evidence)

    def test_not_found(self) -> None:
        _, report = self._run_fixture("not_found.json")
        self.assertTrue(any(c.status == ClaimStatus.not_found for c in report.comparisons))

    def test_conflict(self) -> None:
        _, report = self._run_fixture("conflict.json")
        hit = next(c for c in report.comparisons if c.status == ClaimStatus.conflict)
        self.assertIsNotNone(hit.sales_claim)
        self.assertIsNotNone(hit.official_evidence)

    def test_conditional(self) -> None:
        _, report = self._run_fixture("conditional.json")
        self.assertTrue(any(c.status == ClaimStatus.conditional for c in report.comparisons))

    def test_uncertain(self) -> None:
        _, report = self._run_fixture("uncertain.json")
        self.assertTrue(any(c.status == ClaimStatus.uncertain for c in report.comparisons))

    def test_empty_side_http_rejected(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/dual-analyses",
            json={"sales_text": "有内容", "official_text": "   "},
        )
        self.assertIn(res.status_code, (400, 422))

    def test_api_happy_path(self) -> None:
        client = TestClient(create_app())
        data = json.loads((FIXTURES / "confirmed.json").read_text(encoding="utf-8"))
        res = client.post("/api/v1/dual-analyses", json=data)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("comparisons", body)
        self.assertTrue(body["comparisons"])


if __name__ == "__main__":
    unittest.main()
