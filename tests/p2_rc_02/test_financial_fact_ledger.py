"""P2-RC-02：统一金融事实账本、证据与稳定 ID（F-03 / F-08 / F-10）。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.compare_products import CompareProductsUseCase  # noqa: E402
from app.domain.models.enums import FactStatus, ParameterKey, ProductHint  # noqa: E402
from app.domain.models.financial_fact import FinancialFactStatus  # noqa: E402
from app.domain.models.product_facts import ProductCompareRequest  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.domain.rules.financial_fact_extractor import FinancialFactExtractor  # noqa: E402
from app.domain.rules.product_fact_builder import build_side_facts  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402

LOAN = (
    "本贷款金额10万元，期限12个月，年化利率7.20%。"
    "逾期按罚息计收。提前还款需支付违约金。风险等级：R2。"
)


class StableFactIdTests(unittest.TestCase):
    def test_f08_same_input_same_fact_ids(self) -> None:
        fx = FinancialFactExtractor()
        a = fx.extract(LOAN, product_id="loan").facts
        b = fx.extract(LOAN, product_id="loan").facts
        self.assertTrue(a)
        self.assertEqual(
            [(f.field_key, f.fact_id, f.normalized_value) for f in a],
            [(f.field_key, f.fact_id, f.normalized_value) for f in b],
        )

    def test_fact_id_changes_when_value_changes(self) -> None:
        fx = FinancialFactExtractor()
        a = fx.extract("本贷款金额10万元。", product_id="loan").by_field("amount")[0]
        b = fx.extract("本贷款金额20万元。", product_id="loan").by_field("amount")[0]
        self.assertNotEqual(a.fact_id, b.fact_id)


class AmountEvidenceTests(unittest.TestCase):
    def test_f03_display_normalized_evidence_keeps_wan_yuan(self) -> None:
        repo = LocalFileKnowledgeRepository()
        extracted = FactExtractor(repo).extract(LOAN, product_type_id="loan")
        amount_params = [
            p for p in extracted.key_parameters if p.key == ParameterKey.amount
        ]
        self.assertEqual(len(amount_params), 1)
        self.assertEqual(amount_params[0].value, "10万元")
        self.assertEqual(str(amount_params[0].amount), "100000")
        amount_facts = [
            f
            for f in extracted.financial_facts
            if f.field_key == "amount" and f.status == FinancialFactStatus.CONFIRMED
        ]
        self.assertEqual(len(amount_facts), 1)
        fact = amount_facts[0]
        self.assertEqual(fact.normalized_value, "100000")
        self.assertTrue(fact.evidence_refs)
        self.assertEqual(fact.evidence_refs[0].quote, "10万元")
        span = LOAN[fact.evidence_refs[0].start : fact.evidence_refs[0].end]
        self.assertEqual(span, "10万元")

        meta, fields = build_side_facts(
            text=LOAN, label="A", hint=ProductHint.loan, knowledge=repo
        )
        side = fields["amount"]
        # display 保留原文「10万元」；标准化值在 normalized（与 RC-06 证据口径一致）
        self.assertEqual(side.display, "10万元")
        self.assertEqual(side.normalized, "100000")
        self.assertTrue(side.evidence)
        self.assertEqual(side.evidence[0].quote, "10万元")


class DocumentFactLedgerCoverageTests(unittest.TestCase):
    def test_f10_each_document_fact_has_ledger_fact(self) -> None:
        extracted = FactExtractor(LocalFileKnowledgeRepository()).extract(
            LOAN, product_type_id="loan"
        )
        doc_params = [
            p
            for p in extracted.key_parameters
            if p.status == FactStatus.document_fact and p.value
        ]
        self.assertGreaterEqual(len(doc_params), 5)
        field_map = {
            ParameterKey.amount: "amount",
            ParameterKey.term: "term",
            ParameterKey.annual_interest_rate: "annual_interest_rate",
            ParameterKey.penalty_interest: "penalty_interest",
            ParameterKey.prepayment_fee: "prepayment_fee",
            ParameterKey.product_risk_grade: "product_risk_grade",
            ParameterKey.repayment_method: "repayment_method",
        }
        ff_fields = {
            f.field_key
            for f in extracted.financial_facts
            if f.status == FinancialFactStatus.CONFIRMED
        }
        for p in doc_params:
            fk = field_map.get(p.key)
            if fk is None:
                continue
            self.assertIn(fk, ff_fields, msg=f"missing ledger for {p.key}")
            facts = [
                f
                for f in extracted.financial_facts
                if f.field_key == fk and f.status == FinancialFactStatus.CONFIRMED
            ]
            self.assertTrue(facts[0].evidence_refs)


class HomologousEntryTests(unittest.TestCase):
    def test_single_dual_compare_share_amount_evidence(self) -> None:
        repo = LocalFileKnowledgeRepository()
        single = FactExtractor(repo).extract(LOAN, product_type_id="loan")
        amt = next(f for f in single.financial_facts if f.field_key == "amount")
        _, fields = build_side_facts(
            text=LOAN, label="A", hint=ProductHint.loan, knowledge=repo
        )
        self.assertEqual(fields["amount"].evidence[0].quote, amt.evidence_refs[0].quote)
        report = CompareProductsUseCase(repo).execute(
            ProductCompareRequest(
                text_a=LOAN,
                text_b=LOAN,
                product_hint_a=ProductHint.loan,
                product_hint_b=ProductHint.loan,
            )
        )
        row = next(r for r in report.dimensions if r.dimension.value == "amount")
        self.assertEqual(row.side_a.evidence[0].quote, "10万元")
        self.assertEqual(row.side_b.evidence[0].quote, "10万元")


class QualifierConditionTests(unittest.TestCase):
    def test_max_and_conditional_and_negation_preserved(self) -> None:
        fx = FinancialFactExtractor()
        max_f = fx.extract("年化最高3%。", product_id="structured_deposit").by_field(
            "expected_return"
        )[0]
        self.assertIn("最高", max_f.qualifiers)
        cond = fx.extract(
            "满足观察条件后收益为2.8%。", product_id="structured_deposit"
        ).by_field("expected_return")[0]
        self.assertTrue(cond.condition_text)
        neg = fx.extract(
            "提前还款不收取违约金。", product_id="loan"
        ).by_field("prepayment_fee")[0]
        self.assertEqual(neg.polarity.value, "negative")


if __name__ == "__main__":
    unittest.main()
