"""P1-03：证据追问验收。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.application.answer_from_evidence import AnswerFromEvidenceUseCase  # noqa: E402
from app.domain.models.evidence_answer import AnswerStatus, FollowUpRequest  # noqa: E402
from app.main import create_app  # noqa: E402

SRC = (
    "本贷款年化利率7.2%。提前还款需支付剩余本金3%的违约金。"
    "费用说明：不收取账户管理费。"
)


class FollowUpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = AnswerFromEvidenceUseCase()

    def test_answered_with_evidence(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(question="提前还款要不要钱？", source_text=SRC)
        )
        self.assertEqual(ans.status, AnswerStatus.answered)
        self.assertTrue(ans.evidence)
        quote = ans.evidence[0].quote
        self.assertEqual(SRC[ans.evidence[0].start : ans.evidence[0].end], quote)

    def test_insufficient(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(question="有没有保险附加条款？", source_text=SRC)
        )
        self.assertEqual(ans.status, AnswerStatus.insufficient_evidence)
        self.assertTrue(ans.missing_info)

    def test_out_of_scope(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(question="今天北京天气怎么样？", source_text=SRC)
        )
        self.assertEqual(ans.status, AnswerStatus.out_of_scope)

    def test_http(self) -> None:
        client = TestClient(create_app())
        res = client.post(
            "/api/v1/follow-ups",
            json={"question": "年化利率多少？", "source_text": SRC},
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "answered")


if __name__ == "__main__":
    unittest.main()
