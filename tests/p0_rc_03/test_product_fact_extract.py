"""
P0-RC-03：按产品拆分关键参数抽取。
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
FORBIDDEN_LOAN_LABELS = ("投资期限", "预期收益", "提前赎回", "本金保障")


def _fx() -> FactExtractor:
    return FactExtractor(LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE))


class StructuredDepositExtractTests(unittest.TestCase):
    def test_colon_format_and_multi_returns(self):
        text = (
            "本产品为结构性存款。产品期限：90天。"
            "年化收益率：4.80%；若突破观察区间，则到期年化收益率为1.20%。"
            "风险等级：R2。"
        )
        result = _fx().extract(text, "structured_deposit")
        params = {p.key: p for p in result.key_parameters}
        self.assertEqual(params[ParameterKey.term].status, FactStatus.document_fact)
        self.assertIn("90", params[ParameterKey.term].value or "")
        self.assertEqual(params[ParameterKey.expected_return].status, FactStatus.document_fact)
        value = params[ParameterKey.expected_return].value or ""
        self.assertIn("4.80", value)
        self.assertIn("1.20", value)
        self.assertEqual(params[ParameterKey.principal_protection].status, FactStatus.not_disclosed)
        self.assertEqual(params[ParameterKey.product_risk_grade].value, "R2")
        self.assertEqual(params[ParameterKey.product_risk_grade].status, FactStatus.document_fact)
        self.assertEqual(result.pending_questions, [])

    def test_no_risk_grade_not_from_knowledge(self):
        text = "本产品为结构性存款，期限90天，到期年化收益率4.80%。"
        result = _fx().extract(text, "structured_deposit")
        params = {p.key: p for p in result.key_parameters}
        self.assertEqual(params[ParameterKey.product_risk_grade].status, FactStatus.not_disclosed)
        joined_doc = " ".join(
            (p.value or "") for p in result.key_parameters if p.status == FactStatus.document_fact
        )
        self.assertNotIn("通常保本", joined_doc)
        self.assertTrue(
            any("通常保本" in r.text or "行业参考" in r.text for r in result.general_references)
            or any(r.text for r in result.general_references)
        )


class LoanExtractTests(unittest.TestCase):
    def test_loan_fields(self):
        text = (
            "借款期限12个月。年化利率（单利）为7.20%，采用等额本息还款。"
            "逾期按罚息日利率0.05%计收。提前还款需支付剩余本金3%的违约金。"
            "借款金额：10万元。"
        )
        result = _fx().extract(text, "loan")
        params = {p.key: p for p in result.key_parameters}
        self.assertEqual(params[ParameterKey.term].label, "借款期限")
        self.assertIn("12", params[ParameterKey.term].value or "")
        self.assertEqual(params[ParameterKey.annual_interest_rate].status, FactStatus.document_fact)
        self.assertIn("7.20", params[ParameterKey.annual_interest_rate].value or "")
        self.assertIn("等额本息", params[ParameterKey.repayment_method].value or "")
        self.assertIn("罚息", params[ParameterKey.penalty_interest].value or "")
        self.assertIn("违约金", params[ParameterKey.prepayment_fee].value or "")
        self.assertEqual(params[ParameterKey.amount].amount, Decimal("100000"))
        labels = [p.label for p in result.key_parameters]
        for banned in FORBIDDEN_LOAN_LABELS:
            self.assertNotIn(banned, labels)
        self.assertNotIn(ParameterKey.expected_return, params)
        self.assertNotIn(ParameterKey.principal_protection, params)
        self.assertEqual(result.pending_questions, [])

    def test_loan_missing_only_loan_fields(self):
        result = _fx().extract("本贷款合同由双方签字盖章后生效。", "loan")
        params = {p.key: p for p in result.key_parameters}
        for key in (
            ParameterKey.annual_interest_rate,
            ParameterKey.repayment_method,
            ParameterKey.penalty_interest,
            ParameterKey.prepayment_fee,
            ParameterKey.term,
        ):
            self.assertEqual(params[key].status, FactStatus.not_disclosed)
        self.assertNotIn(ParameterKey.principal_protection, params)
        self.assertNotIn(ParameterKey.expected_return, params)
        self.assertTrue(result.missing_disclosures)
        self.assertEqual(result.pending_questions, [])


if __name__ == "__main__":
    unittest.main()
