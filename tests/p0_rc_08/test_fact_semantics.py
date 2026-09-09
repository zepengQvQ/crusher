"""
P0-RC-08：事实抽取语义与数值正确性。
"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.models.enums import FactStatus, ParameterKey  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"


def _fx() -> FactExtractor:
    return FactExtractor(LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE))


def _params(text: str, product: str) -> dict:
    return {p.key: p for p in _fx().extract(text, product).key_parameters}


class AmountExtractTests(unittest.TestCase):
    def test_thousand_separator(self):
        p = _params("借款金额：100,000元。", "loan")[ParameterKey.amount]
        self.assertEqual(p.amount, Decimal("100000"))

    def test_wan_yuan(self):
        p = _params("借款金额为10万元。", "loan")[ParameterKey.amount]
        self.assertEqual(p.amount, Decimal("100000"))


class PolarityExtractTests(unittest.TestCase):
    def test_non_principal_protected(self):
        p = _params("本产品为非保本结构性存款。", "structured_deposit")[
            ParameterKey.principal_protection
        ]
        self.assertEqual(p.status, FactStatus.document_fact)
        self.assertIn("非保本", p.value or "")
        self.assertNotEqual(p.value, "保本")

    def test_no_principal_promise(self):
        p = _params("本产品不承诺保本。", "structured_deposit")[ParameterKey.principal_protection]
        self.assertEqual(p.status, FactStatus.document_fact)
        self.assertNotEqual(p.value, "保本")
        self.assertTrue("不" in (p.value or "") or "非" in (p.value or ""))

    def test_no_prepayment_fee(self):
        p = _params("不收取提前还款违约金。", "loan")[ParameterKey.prepayment_fee]
        self.assertEqual(p.status, FactStatus.document_fact)
        self.assertTrue(
            any(x in (p.value or "") for x in ("不收取", "不收", "免收")),
            p.value,
        )

    def test_repayment_not_a_but_b(self):
        p = _params("还款方式不是等额本息，而是等额本金。", "loan")[ParameterKey.repayment_method]
        self.assertIn("等额本金", p.value or "")
        self.assertNotIn("等额本息", p.value or "")

    def test_early_redeem_pos_neg(self):
        pos = _params("支持提前支取。", "structured_deposit")[ParameterKey.early_redemption]
        neg = _params("不支持提前支取。", "structured_deposit")[ParameterKey.early_redemption]
        self.assertEqual(pos.status, FactStatus.document_fact)
        self.assertIn("支持提前支取", pos.value or "")
        self.assertEqual(neg.status, FactStatus.document_fact)
        self.assertIn("不支持提前支取", neg.value or "")


class RateAndGradeTests(unittest.TestCase):
    def test_normal_rate_excludes_penalty_clause(self):
        text = "逾期罚息年化利率24%，正常借款年化利率7.2%。"
        p = _params(text, "loan")[ParameterKey.annual_interest_rate]
        self.assertIn("7.2", p.value or "")
        self.assertNotIn("24", p.value or "")

    def test_customer_grade_not_product_grade(self):
        p = _params("客户评级R4，产品风险评级未披露。", "structured_deposit")[
            ParameterKey.product_risk_grade
        ]
        self.assertEqual(p.status, FactStatus.not_disclosed)

    def test_illegal_r30_not_matched(self):
        p = _params("产品风险评级：R30。", "structured_deposit")[ParameterKey.product_risk_grade]
        self.assertEqual(p.status, FactStatus.not_disclosed)

    def test_rate_with_paren_note(self):
        p = _params("年化利率（单利）：7.20%。", "loan")[ParameterKey.annual_interest_rate]
        self.assertIn("7.20", p.value or "")


class TermAndReturnTests(unittest.TestCase):
    def test_redeem_days_not_product_term(self):
        p = _params("赎回到账共3天，产品期限未约定。", "structured_deposit")[ParameterKey.term]
        self.assertEqual(p.status, FactStatus.not_disclosed)

    def test_overdue_days_not_loan_term(self):
        p = _params("逾期期限30天，借款期限未约定。", "loan")[ParameterKey.term]
        self.assertEqual(p.status, FactStatus.not_disclosed)

    def test_return_range_kept(self):
        p = _params("年化收益率为1.20%-4.80%。", "structured_deposit")[
            ParameterKey.expected_return
        ]
        self.assertIn("1.20", p.value or "")
        self.assertIn("4.80", p.value or "")
        self.assertTrue("-" in (p.value or "") or "～" in (p.value or "") or "/" in (p.value or ""))

    def test_term_one_year(self):
        p = _params("产品期限：1年。", "structured_deposit")[ParameterKey.term]
        self.assertEqual(p.status, FactStatus.document_fact)
        self.assertIn("1年", p.value or "")


if __name__ == "__main__":
    unittest.main()
