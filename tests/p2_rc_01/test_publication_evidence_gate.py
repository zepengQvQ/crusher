"""P2-RC-01：堵住发布门禁与假证据绕过（F-01 / F-02 等）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.models.enums import EvidenceSource, FindingSeverity  # noqa: E402
from app.domain.models.financial_fact import (  # noqa: E402
    FactEvidenceRef,
    FinancialFact,
    FinancialFactStatus,
    ValueKind,
)
from app.domain.models.llm import LlmAnalysisDraft, LlmDraftItem  # noqa: E402
from app.domain.models.report import Evidence, Finding  # noqa: E402
from app.domain.models.verification import PublicationOutcome  # noqa: E402
from app.domain.rules.evidence import validate_and_fix_findings  # noqa: E402
from app.domain.validation.evidence_validator import (  # noqa: E402
    validate_financial_fact_evidence,
)
from app.domain.validation.publication_gate import (  # noqa: E402
    decide_from_verification,
    run_publication_gate,
)
from app.domain.validation.program_plain_language import (  # noqa: E402
    render_program_plain_language,
)
from app.shared.enums import ErrorCode  # noqa: E402

SRC = "本贷款金额10万元，期限12个月。提前还款需支付违约金。"


def _amount_fact(*, quote: str = "10万元", start: int | None = None) -> FinancialFact:
    q = quote
    s = SRC.index("10万元") if start is None else start
    if quote == "10万元":
        s = SRC.index(q)
        e = s + len(q)
    else:
        e = start + len(quote)  # type: ignore[operator]
        s = start  # type: ignore[assignment]
    return FinancialFact(
        fact_id="ff_amt",
        product_id="loan",
        field_key="amount",
        raw_value="10万元",
        normalized_value="100000",
        unit="CNY",
        value_kind=ValueKind.amount,
        status=FinancialFactStatus.CONFIRMED,
        evidence_refs=[FactEvidenceRef(quote=q, start=s, end=e)],
    )


def _draft(text: str, *, fact_ids: list[str] | None = None) -> LlmAnalysisDraft:
    return LlmAnalysisDraft(
        overview_items=[
            LlmDraftItem(
                item_id="o1",
                text=text,
                fact_ids=fact_ids or ["ff_amt"],
            )
        ]
    )


class FinancialFactEvidenceTests(unittest.TestCase):
    def test_forged_quote_span_rejected(self) -> None:
        forged = FinancialFact(
            fact_id="ff_amt",
            product_id="loan",
            field_key="amount",
            raw_value="10万元",
            normalized_value="100000",
            unit="CNY",
            value_kind=ValueKind.amount,
            status=FinancialFactStatus.CONFIRMED,
            evidence_refs=[FactEvidenceRef(quote="保本承诺", start=0, end=4)],
        )
        issues = validate_financial_fact_evidence(SRC, [forged])
        self.assertTrue(issues)

    def test_confirmed_without_matching_span_rejected(self) -> None:
        bad = FinancialFact(
            fact_id="ff_amt",
            product_id="loan",
            field_key="amount",
            raw_value="10万元",
            normalized_value="100000",
            unit="CNY",
            value_kind=ValueKind.amount,
            status=FinancialFactStatus.CONFIRMED,
            evidence_refs=[
                FactEvidenceRef(quote="10万元", start=0, end=3)  # wrong span
            ],
        )
        issues = validate_financial_fact_evidence(SRC, [bad])
        self.assertTrue(issues)


class PublicationGateRc01Tests(unittest.TestCase):
    def test_f01_legal_id_cannot_publish_unrelated_guarantee(self) -> None:
        fact = _amount_fact()
        draft = _draft("国家财政兜底，银行倒闭也不会损失。")
        plain = draft.render_plain_language()
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=plain,
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        decision = decide_from_verification(result)
        self.assertIn(
            decision.outcome,
            {PublicationOutcome.publish_partial, PublicationOutcome.refuse},
        )

    def test_f01_unrelated_qualitative_claim_blocked(self) -> None:
        fact = _amount_fact()
        draft = _draft("本产品绝对稳健，等同银行存款保险全额赔付。")
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)

    def test_f02_forged_financial_fact_evidence_blocks_publish(self) -> None:
        forged = FinancialFact(
            fact_id="ff_amt",
            product_id="loan",
            field_key="amount",
            raw_value="10万元",
            normalized_value="100000",
            unit="CNY",
            value_kind=ValueKind.amount,
            status=FinancialFactStatus.CONFIRMED,
            evidence_refs=[FactEvidenceRef(quote="保本承诺", start=0, end=4)],
        )
        draft = _draft("贷款金额为10万元。")
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[forged],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        self.assertIn("evidence", result.failed_checks)

    def test_all_findings_dropped_cannot_full_publish(self) -> None:
        raw = [
            Finding(
                id="prepayment_penalty",
                title="提前还款违约金",
                finding_severity=FindingSeverity.high,
                explanation="可能收取违约金",
                evidence=[
                    Evidence(
                        quote="并不存在的句子",
                        start=0,
                        end=7,
                        source=EvidenceSource.input_text,
                    )
                ],
                rule_or_knowledge_id="prepayment_penalty",
                confidence=0.9,
            )
        ]
        kept, dropped = validate_and_fix_findings(SRC, raw)
        self.assertEqual(kept, [])
        self.assertEqual(dropped, ["prepayment_penalty"])
        # 门禁侧：有规则命中痕迹但 findings 为空 → 不得 can_publish
        draft = _draft("说明贷款金额。", fact_ids=["ff_amt"])
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=draft.render_plain_language(),
            findings=kept,
            key_parameters=[],
            financial_facts=[_amount_fact()],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
            dropped_finding_ids=dropped,
            rule_hit_count=1,
        )
        self.assertFalse(result.can_publish)

    def test_program_plain_language_excludes_model_hallucination(self) -> None:
        fact = _amount_fact()
        findings = [
            Finding(
                id="prepayment_penalty",
                title="提前还款违约金",
                finding_severity=FindingSeverity.high,
                explanation="提前还款需支付违约金",
                evidence=[
                    Evidence(
                        quote="提前还款需支付违约金",
                        start=SRC.index("提前还款需支付违约金"),
                        end=SRC.index("提前还款需支付违约金")
                        + len("提前还款需支付违约金"),
                        source=EvidenceSource.input_text,
                    )
                ],
                rule_or_knowledge_id="prepayment_penalty",
                confidence=0.9,
            )
        ]
        model_plain = "国家财政兜底，银行倒闭也不会损失。"
        program = render_program_plain_language(
            findings=findings,
            financial_facts=[fact],
            key_parameters=[],
        )
        self.assertNotIn("国家财政兜底", program)
        self.assertIn("10万元", program)
        self.assertIn("违约金", program)
        # 验证失败路径不得把模型原文塞进最终文案
        draft = _draft(model_plain)
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=model_plain,
            findings=findings,
            key_parameters=[],
            financial_facts=[fact],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=["prepayment_penalty"],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        decision = decide_from_verification(result)
        self.assertNotIn(model_plain, decision.user_reason)


class ReferenceCatalogGateTests(unittest.TestCase):
    def test_unverified_fact_id_not_in_allowed_numbers_set(self) -> None:
        forged = FinancialFact(
            fact_id="ff_amt",
            product_id="loan",
            field_key="amount",
            raw_value="10万元",
            normalized_value="999999",
            unit="CNY",
            value_kind=ValueKind.amount,
            status=FinancialFactStatus.CONFIRMED,
            evidence_refs=[FactEvidenceRef(quote="保本承诺", start=0, end=4)],
        )
        draft = _draft("金额为999999元。")
        result = run_publication_gate(
            source_text=SRC,
            draft=draft,
            plain=draft.render_plain_language(),
            findings=[],
            key_parameters=[],
            financial_facts=[forged],
            allowed_fact_ids=["ff_amt"],
            allowed_finding_ids=[],
            allowed_knowledge_ids=[],
        )
        self.assertFalse(result.can_publish)
        # 未验证事实不得扩充允许集合导致放行
        self.assertFalse(result.can_publish)


if __name__ == "__main__":
    unittest.main()
