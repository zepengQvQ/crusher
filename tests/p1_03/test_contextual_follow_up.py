"""追问：咨询类走 contextual；证据路径不变。"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from app.application.answer_from_evidence import AnswerFromEvidenceUseCase  # noqa: E402
from app.domain.models.evidence_answer import (  # noqa: E402
    AnswerStatus,
    ChatTurn,
    FollowUpRequest,
)
from app.domain.validation.publication_service import PublicationService  # noqa: E402
from app.domain.models.verification import PublicationOutcome  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402

SRC = (
    "本结构性存款期限183天。区间外收益可能为零。"
    "本金保障：保本。提前支取需支付违约金。"
)


class ContextualFollowUpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.uc = AnswerFromEvidenceUseCase(
            publication=PublicationService(),
            llm_gateway=MockLlmGateway(),
        )

    def test_suitability_goes_contextual_with_disclaimer(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(
                question="适合老年人买吗？",
                source_text=SRC,
                report_digest="风险：区间外收益可能为零；本金保障：保本",
            )
        )
        self.assertEqual(ans.status, AnswerStatus.contextual)
        self.assertFalse(ans.evidence)
        self.assertIn("投资建议", ans.answer)
        self.assertIn("适当性", ans.answer)
        self.assertIsNotNone(ans.publication)
        self.assertEqual(ans.publication.outcome, PublicationOutcome.publish_partial)

    def test_recent_messages_influence_mock_reply(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(
                question="那和刚才说的风险有关系吗？",
                source_text=SRC,
                report_digest="风险：区间外收益可能为零",
                recent_messages=[
                    ChatTurn(role="user", content="区间外收益可能为零是什么意思？"),
                    ChatTurn(role="assistant", content="材料写了区间外收益可能为零。"),
                ],
            )
        )
        self.assertEqual(ans.status, AnswerStatus.contextual)
        self.assertIn("区间外", ans.answer)

    def test_evidence_path_unchanged(self) -> None:
        ans = self.uc.execute(
            FollowUpRequest(question="保本吗？", source_text=SRC)
        )
        self.assertEqual(ans.status, AnswerStatus.answered)
        self.assertTrue(ans.evidence)


if __name__ == "__main__":
    unittest.main()
