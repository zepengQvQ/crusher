"""P2-07：条件遗漏与否定反转门禁。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.models.financial_fact import (  # noqa: E402
    ExtractorSource,
    FactEvidenceRef,
    FactPolarity,
    FinancialFact,
    FinancialFactStatus,
    ValueKind,
)
from app.domain.models.llm import make_simple_draft  # noqa: E402
from app.domain.validation.publication_gate import run_publication_gate  # noqa: E402
from app.shared.enums import ErrorCode  # noqa: E402


def _fact(**kwargs: object) -> FinancialFact:
    base = dict(
        fact_id="ff_1",
        product_id="structured_deposit",
        field_key="expected_return",
        raw_value="满足观察条件后收益为2.8%",
        normalized_value="2.8",
        unit="%",
        value_kind=ValueKind.percent,
        polarity=FactPolarity.affirmative,
        qualifiers=[],
        condition_text="满足观察条件后",
        status=FinancialFactStatus.CONFIRMED,
        evidence_refs=[
            FactEvidenceRef(
                quote="满足观察条件后收益为2.8%",
                start=0,
                end=len("满足观察条件后收益为2.8%"),
            )
        ],
        extractor_source=ExtractorSource.RULE,
    )
    base.update(kwargs)
    return FinancialFact.model_validate(base)


class ConditionAndNegationGateTests(unittest.TestCase):
    def test_max_rewritten_as_maturity_blocked(self) -> None:
        fact = _fact(
            raw_value="年化最高3%",
            qualifiers=["最高"],
            condition_text=None,
            evidence_refs=[FactEvidenceRef(quote="年化最高3%", start=0, end=len("年化最高3%"))],
        )
        draft = make_simple_draft("到期收益为3%。", fact_ids=[fact.fact_id])
        result = run_publication_gate(
            source_text="年化最高3%。",
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=[fact.fact_id],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        self.assertIn("unit", result.failed_checks)

    def test_condition_omission_blocked(self) -> None:
        fact = _fact()
        draft = make_simple_draft("收益为2.8%。", fact_ids=[fact.fact_id])
        result = run_publication_gate(
            source_text="满足观察条件后收益为2.8%。",
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=[fact.fact_id],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        self.assertIn("negation_condition", result.failed_checks)
        self.assertEqual(result.error_code, ErrorCode.OUTPUT_VERIFICATION_FAILED)

    def test_negation_flip_fee_blocked(self) -> None:
        fact = _fact(
            fact_id="ff_fee",
            field_key="prepayment_fee",
            raw_value="提前还款不收取违约金",
            normalized_value="不收取",
            unit=None,
            value_kind=ValueKind.fee,
            polarity=FactPolarity.negative,
            condition_text=None,
            evidence_refs=[
                FactEvidenceRef(
                    quote="提前还款不收取违约金",
                    start=0,
                    end=len("提前还款不收取违约金"),
                )
            ],
        )
        draft = make_simple_draft(
            "提前还款需支付违约金。",
            fact_ids=[fact.fact_id],
        )
        result = run_publication_gate(
            source_text="提前还款不收取违约金。",
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=[fact.fact_id],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        self.assertIn("negation_condition", result.failed_checks)

    def test_condition_kept_passes(self) -> None:
        fact = _fact()
        draft = make_simple_draft(
            "满足观察条件后收益为2.8%。",
            fact_ids=[fact.fact_id],
        )
        result = run_publication_gate(
            source_text="满足观察条件后收益为2.8%。",
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=[fact.fact_id],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertTrue(result.can_publish)


if __name__ == "__main__":
    unittest.main()
