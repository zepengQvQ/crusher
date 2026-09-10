"""P2-06：草稿引用白名单校验。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.llm_errors import LlmInvalidJsonError  # noqa: E402
from app.domain.llm_explanation_guard import validate_draft_reference_whitelist  # noqa: E402
from app.domain.models.llm import LlmDraftItem, LlmAnalysisDraft, make_simple_draft  # noqa: E402


class WhitelistTests(unittest.TestCase):
    def test_unknown_fact_id_fails(self) -> None:
        draft = make_simple_draft("说明", fact_ids=["param:term"])
        with self.assertRaises(LlmInvalidJsonError) as ctx:
            validate_draft_reference_whitelist(
                draft,
                allowed_fact_ids={"param:amount"},
                allowed_finding_ids=set(),
                allowed_knowledge_ids=set(),
            )
        self.assertIn("unknown fact_id", str(ctx.exception))

    def test_unknown_finding_id_fails(self) -> None:
        draft = make_simple_draft("说明", finding_ids=["prepayment_penalty"])
        with self.assertRaises(LlmInvalidJsonError):
            validate_draft_reference_whitelist(
                draft,
                allowed_fact_ids=set(),
                allowed_finding_ids={"other"},
                allowed_knowledge_ids=set(),
            )

    def test_unknown_knowledge_id_fails(self) -> None:
        draft = make_simple_draft("说明", knowledge_ids=["knowledge:x"])
        with self.assertRaises(LlmInvalidJsonError):
            validate_draft_reference_whitelist(
                draft,
                allowed_fact_ids=set(),
                allowed_finding_ids=set(),
                allowed_knowledge_ids={"knowledge:y"},
            )

    def test_whitelist_ok(self) -> None:
        draft = LlmAnalysisDraft(
            warning_items=[
                LlmDraftItem(
                    item_id="w1",
                    text="注意违约金",
                    finding_ids=["prepayment_penalty"],
                )
            ]
        )
        validate_draft_reference_whitelist(
            draft,
            allowed_fact_ids=set(),
            allowed_finding_ids={"prepayment_penalty"},
            allowed_knowledge_ids=set(),
        )


if __name__ == "__main__":
    unittest.main()
