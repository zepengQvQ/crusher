"""
P0-RC-07：规则语义、句界、否定与 Evidence（先失败再修复）。
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402


def _engine() -> RuleEngine:
    return RuleEngine(LocalFileKnowledgeRepository())


def _risk_ids(text: str, product: str) -> set[str]:
    return {r.pattern_id for r in _engine().match_risks(text, product)}


def _assert_quote(hit) -> None:
    # 测试辅助：Evidence 坐标必须自洽
    pass


class CrossSentenceFalsePositiveTests(unittest.TestCase):
    def test_low_floor_must_not_cross_strong_sentence(self):
        text = "本产品为结构性存款。汇率突破观察区间。客户仅获得1.20%的低档收益。"
        self.assertNotIn("low_floor_return", _risk_ids(text, "structured_deposit"))

    def test_higher_return_is_not_low_floor(self):
        text = "若汇率突破观察区间，则仅获得更高的8.00%收益。"
        self.assertNotIn("low_floor_return", _risk_ids(text, "structured_deposit"))


class NegationDoesNotBlockLaterPositiveTests(unittest.TestCase):
    def test_second_sentence_loan_still_detected(self):
        text = "本产品不是贷款。另一项服务是贷款，年化利率为7.2%。"
        products = {p.product_id for p in _engine().detect_products(text)}
        self.assertIn("loan", products)

    def test_first_prepayment_waiver_second_still_hits(self):
        text = "本贷款首次提前还款不收违约金。第二次提前还款需支付剩余本金3%的违约金。"
        self.assertIn("prepayment_penalty", _risk_ids(text, "loan"))

    def test_postposed_waiver_blocks_prepayment(self):
        text = "本贷款提前还款手续费免收。"
        self.assertNotIn("prepayment_penalty", _risk_ids(text, "loan"))

    def test_fee_reduction_is_not_prepayment_penalty(self):
        text = "本贷款提前还款可减免3%的利息。"
        self.assertNotIn("prepayment_penalty", _risk_ids(text, "loan"))


class NegationTargetBindingTests(unittest.TestCase):
    def test_wei_in_overdue_premise_not_negating_penalty(self):
        text = "本贷款借款人未按期还款的逾期部分按罚息日利率0.05%计收。"
        self.assertIn("high_penalty_interest", _risk_ids(text, "loan"))

    def test_same_rate_no_extra_is_not_high_penalty(self):
        text = "本贷款罚息利率与正常利率相同，不额外加收。"
        self.assertNotIn("high_penalty_interest", _risk_ids(text, "loan"))

    def test_non_revolving_loan_still_loan_product(self):
        text = "本产品为非循环贷款。"
        products = {p.product_id for p in _engine().detect_products(text)}
        self.assertIn("loan", products)


class EvidenceCompletenessTests(unittest.TestCase):
    def test_overdue_and_penalty_rate_in_same_evidence(self):
        text = "本产品为贷款。逾期，按罚息利率计收。"
        hits = [h for h in _engine().match_risks(text, "loan") if h.pattern_id == "high_penalty_interest"]
        self.assertTrue(hits)
        hit = hits[0]
        self.assertEqual(text[hit.start : hit.end], hit.quote)
        self.assertIn("逾期", hit.quote)
        self.assertIn("罚息利率", hit.quote)


class PositiveStillHitsTests(unittest.TestCase):
    def test_penalty_interest_positive(self):
        text = "逾期部分按罚息日利率0.05%计收，罚息为正常利率的2.5倍。"
        hits = [h for h in _engine().match_risks(text, "loan") if h.pattern_id == "high_penalty_interest"]
        self.assertTrue(hits)
        self.assertEqual(text[hits[0].start : hits[0].end], hits[0].quote)

    def test_prepayment_positive(self):
        text = "提前还款需支付剩余本金3%的违约金。"
        self.assertIn("prepayment_penalty", _risk_ids(text, "loan"))

    def test_low_floor_positive(self):
        text = "若汇率突破观察区间，则仅获得1.20%的低档收益。"
        self.assertIn("low_floor_return", _risk_ids(text, "structured_deposit"))

    def test_idempotent_findings(self):
        text = "提前还款需支付剩余本金3%的违约金。"
        a = [(h.pattern_id, h.start, h.end, h.quote) for h in _engine().match_risks(text, "loan")]
        b = [(h.pattern_id, h.start, h.end, h.quote) for h in _engine().match_risks(text, "loan")]
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
