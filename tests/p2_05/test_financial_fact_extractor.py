"""P2-05：金融事实抽取语义。"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase  # noqa: E402
from app.application.compare_products import CompareProductsUseCase  # noqa: E402
from app.domain.models.claim_comparison import DualAnalysisRequest  # noqa: E402
from app.domain.models.financial_fact import (  # noqa: E402
    FactPolarity,
    FinancialFactStatus,
)
from app.domain.models.p1_enums import DiffStatus  # noqa: E402
from app.domain.models.product_facts import ProductCompareRequest  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.domain.rules.financial_fact_extractor import (  # noqa: E402
    FinancialFactExtractor,
    facts_comparable,
)
from app.domain.rules.value_normalizer import (  # noqa: E402
    normalize_percent_or_bp,
    normalize_term_months,
)
from app.infrastructure.knowledge.local_files import (  # noqa: E402
    LocalFileKnowledgeRepository,
)

KNOWLEDGE = ROOT / "knowledge"


def _fx() -> FinancialFactExtractor:
    return FinancialFactExtractor()


class ValueNormalizerTests(unittest.TestCase):
    def test_bp_to_percent_uses_decimal(self) -> None:
        value, unit, nature = normalize_percent_or_bp("50bp")
        self.assertEqual(value, Decimal("0.5"))
        self.assertEqual(unit, "%")
        self.assertEqual(nature, "single")
        self.assertIsInstance(value, Decimal)

    def test_term_12m_equals_1y(self) -> None:
        a = normalize_term_months("期限 12 个月")
        b = normalize_term_months("期限 1 年")
        self.assertEqual(a, Decimal("12"))
        self.assertEqual(b, Decimal("12"))


class FinancialFactExtractorTests(unittest.TestCase):
    def test_max_qualifier(self) -> None:
        facts = _fx().extract("本产品年化最高 3%。").by_field("expected_return")
        self.assertEqual(len(facts), 1)
        f = facts[0]
        self.assertEqual(f.status, FinancialFactStatus.CONFIRMED)
        self.assertEqual(f.normalized_value, "3")
        self.assertIn("最高", f.qualifiers)
        self.assertTrue(f.evidence_refs)
        self.assertNotIn("保证", f.raw_value)

    def test_contrast_not_a_but_b(self) -> None:
        facts = _fx().extract("收益率不是 3%，而是 2.5%。").by_field("expected_return")
        self.assertEqual(len(facts), 1)
        f = facts[0]
        self.assertEqual(f.normalized_value, "2.5")
        self.assertEqual(f.polarity, FactPolarity.contrastive)
        self.assertEqual(f.negated_raw_value, "3%")

    def test_conditional_return(self) -> None:
        facts = _fx().extract(
            "满足观察条件后收益为 2.8%。"
        ).by_field("expected_return")
        self.assertEqual(len(facts), 1)
        f = facts[0]
        self.assertEqual(f.normalized_value, "2.8")
        self.assertIsNotNone(f.condition_text)
        self.assertIn("观察条件", f.condition_text or "")

    def test_no_prepayment_fee(self) -> None:
        facts = _fx().extract("提前还款不收取违约金。").by_field("prepayment_fee")
        self.assertEqual(len(facts), 1)
        f = facts[0]
        self.assertEqual(f.polarity, FactPolarity.negative)
        self.assertEqual(f.normalized_value, "不收取")

    def test_bp(self) -> None:
        facts = _fx().extract("上浮 50bp。").by_field("basis_points")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].raw_value.replace(" ", ""), "50bp")
        self.assertEqual(facts[0].normalized_value, "0.5")
        self.assertEqual(facts[0].unit, "%")

    def test_term_comparable(self) -> None:
        a = _fx().extract("产品期限 12 个月。").by_field("term")[0]
        b = _fx().extract("产品期限 1 年。").by_field("term")[0]
        self.assertTrue(facts_comparable(a, b))

    def test_undisclosed_management_fee(self) -> None:
        facts = _fx().extract("本说明书未披露管理费。").by_field("management_fee")
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0].status, FinancialFactStatus.NOT_DISCLOSED)
        self.assertIsNone(facts[0].normalized_value)

    def test_confirmed_always_has_evidence(self) -> None:
        source = (
            "年化最高 3%。不是 2%，而是 2.5%。满足观察条件后收益为 2.8%。"
            "提前还款不收取违约金。上浮 50bp。期限 12 个月。"
        )
        ledger = _fx().extract(source)
        for f in ledger.confirmed():
            self.assertTrue(f.evidence_refs)
            for ev in f.evidence_refs:
                self.assertGreater(ev.end, ev.start)
                self.assertEqual(source[ev.start : ev.end], ev.quote)

    def test_no_float_in_normalized_compare(self) -> None:
        a = normalize_term_months("12个月")
        b = normalize_term_months("1年")
        self.assertIsInstance(a, Decimal)
        self.assertIsInstance(b, Decimal)
        self.assertEqual(a, b)


class ThreeEntryHomologousTests(unittest.TestCase):
    """单材料 / 双材料 / 产品对比对同一段材料得到同源事实。"""

    SAMPLE = "本贷款年化最高 3%，提前还款不收取违约金，期限 12 个月。"

    def test_single_and_dual_and_compare_share_normalizer(self) -> None:
        knowledge = LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE)
        single = FactExtractor(knowledge).extract(self.SAMPLE, "loan")
        dual = AnalyzeDualSourcesUseCase().execute(
            DualAnalysisRequest(sales_text=self.SAMPLE, official_text=self.SAMPLE)
        )
        compare = CompareProductsUseCase(knowledge).execute(
            ProductCompareRequest(text_a=self.SAMPLE, text_b=self.SAMPLE)
        )

        single_fees = [
            f
            for f in single.financial_facts
            if f.field_key == "prepayment_fee"
            and f.status == FinancialFactStatus.CONFIRMED
        ]
        dual_fees = [
            f
            for f in dual.sales_financial_facts
            if f.field_key == "prepayment_fee"
            and f.status == FinancialFactStatus.CONFIRMED
        ]
        self.assertEqual(len(single_fees), 1)
        self.assertEqual(len(dual_fees), 1)
        self.assertEqual(single_fees[0].normalized_value, dual_fees[0].normalized_value)

        single_terms = [
            f.normalized_value
            for f in single.financial_facts
            if f.field_key == "term" and f.normalized_value
        ]
        dual_terms = [
            f.normalized_value
            for f in dual.official_financial_facts
            if f.field_key == "term" and f.normalized_value
        ]
        self.assertEqual(single_terms, dual_terms)
        self.assertEqual(single_terms, ["12"])
        term = next(d for d in compare.dimensions if d.dimension.value == "term")
        self.assertEqual(term.status, DiffStatus.same)


if __name__ == "__main__":
    unittest.main()
