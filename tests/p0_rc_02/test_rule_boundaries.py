"""
P0-RC-02：规则边界、否定、证据质量、首批产品范围。
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.domain.models import AnalyzeTextRequest  # noqa: E402
from app.domain.models.llm import LlmExplainRequest, LlmExplanation  # noqa: E402
from app.domain.models.enums import ProductTypeId  # noqa: E402
from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.domain.rules.negation import is_negated_near  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.shared.enums import TaskStatus  # noqa: E402

KNOWLEDGE = ROOT / "knowledge"
H5_EXAMPLES = ROOT / "frontend-h5" / "src" / "data" / "examples.js"
SCOPE_HINT = "当前 Demo 仅支持结构性存款和贷款，请重新选择或补充材料。"


def _engine() -> RuleEngine:
    return RuleEngine(LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE))


class FixedGw:
    async def complete(self, request: LlmExplainRequest) -> LlmExplanation:
        _ = request
        return LlmExplanation(plain_language="（测试）通俗说明，不改写规则结论。")


class NegationBoundaryTests(unittest.TestCase):
    def test_negation_stops_at_comma(self):
        text = "不收申购费，管理费为1.5%。"
        idx = text.find("管理费")
        self.assertFalse(is_negated_near(text, idx, cues=("不收",), window=30))


class FalsePositiveRegressionTests(unittest.TestCase):
    def test_daily_rate_alone_not_penalty(self):
        risks = {r.pattern_id for r in _engine().match_risks("本贷款日利率为0.03%，按日计息。", "loan")}
        self.assertNotIn("high_penalty_interest", risks)

    def test_prepayment_not_cross_sentence(self):
        text = "本贷款支持提前还款。逾期行为另收违约金。"
        risks = {r.pattern_id for r in _engine().match_risks(text, "loan")}
        self.assertNotIn("prepayment_penalty", risks)

    def test_not_loan_negates_product(self):
        products = {p.product_id for p in _engine().detect_products("本产品不是贷款，只是普通客服说明。")}
        self.assertNotIn("loan", products)

    def test_current_deposit_rate_alone_not_low_floor(self):
        risks = {r.pattern_id for r in _engine().match_risks("本合同仅介绍活期存款利率，与本产品收益无关。")}
        self.assertNotIn("low_floor_return", risks)

    def test_waiting_period_days_alone_not_no_claim(self):
        risks = {
            r.pattern_id
            for r in _engine().match_risks("保险等待期为30天。", "insurance")
        }
        self.assertNotIn("waiting_period_no_claim", risks)

    def test_negation_does_not_cross_clause_for_management_fee(self):
        risks = {r.pattern_id for r in _engine().match_risks("不收申购费，管理费为1.5%。", "fund")}
        self.assertIn("high_management_fee", risks)


class PositiveStillHitsTests(unittest.TestCase):
    def test_penalty_interest_positive(self):
        text = "逾期部分按罚息日利率0.05%计收，罚息为正常利率的2.5倍。"
        hits = _engine().match_risks(text, "loan")
        self.assertIn("high_penalty_interest", {r.pattern_id for r in hits})
        hit = next(r for r in hits if r.pattern_id == "high_penalty_interest")
        self.assertEqual(text[hit.start : hit.end], hit.quote)
        self.assertIn("罚息", hit.quote)

    def test_prepayment_positive(self):
        text = "提前还款需支付剩余本金3%的违约金。"
        hits = _engine().match_risks(text, "loan")
        self.assertIn("prepayment_penalty", {r.pattern_id for r in hits})
        hit = next(r for r in hits if r.pattern_id == "prepayment_penalty")
        self.assertEqual(text[hit.start : hit.end], hit.quote)
        self.assertTrue("提前还款" in hit.quote and "违约金" in hit.quote)

    def test_low_floor_positive(self):
        text = "若汇率突破观察区间，则仅获得1.20%的低档收益。"
        hits = _engine().match_risks(text, "structured_deposit")
        self.assertIn("low_floor_return", {r.pattern_id for r in hits})
        hit = next(r for r in hits if r.pattern_id == "low_floor_return")
        self.assertEqual(text[hit.start : hit.end], hit.quote)
        self.assertIn("突破", hit.quote)


class EvidenceQuoteTests(unittest.TestCase):
    def test_quotes_are_readable_spans(self):
        text = "借款人提前还款需支付剩余本金3%的违约金。"
        for hit in _engine().match_risks(text, "loan"):
            self.assertEqual(text[hit.start : hit.end], hit.quote)
            self.assertGreaterEqual(len(hit.quote), 4)


class ScopeGateTests(unittest.TestCase):
    def _run(self, text: str, product_hint: str = "auto"):
        store = InMemoryTaskStore()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=LocalFileKnowledgeRepository(knowledge_dir=KNOWLEDGE),
            llm_gateway=FixedGw(),
            settings=Settings(mock_mode=True),
        )
        req = AnalyzeTextRequest(text=text, product_hint=product_hint)

        async def go():
            task = uc.submit(req)
            await uc.run(task.task_id, req)
            return store.get(task.task_id)

        return asyncio.run(go())

    def test_unknown_scope(self):
        task = self._run("今日天气晴朗，食堂供应番茄炒蛋。")
        self.assertEqual(task.task_status, TaskStatus.completed)
        report = task.report
        self.assertIsNotNone(report)
        self.assertEqual(len(report.product_candidates), 1)
        self.assertEqual(report.product_candidates[0].product_type_id, ProductTypeId.unknown)
        self.assertEqual(report.key_parameters, [])
        self.assertEqual(report.findings, [])
        self.assertEqual(report.missing_disclosures, [])
        self.assertEqual(report.pending_questions, [SCOPE_HINT])

    def test_insurance_out_of_scope(self):
        task = self._run("本保险合同等待期为30天，犹豫期后退保仅退现金价值。")
        report = task.report
        self.assertIsNotNone(report)
        self.assertEqual(len(report.product_candidates), 1)
        cand = report.product_candidates[0]
        self.assertEqual(cand.product_type_id, ProductTypeId.insurance)
        self.assertIn("out of scope", cand.product_type_name.lower())
        self.assertEqual(report.key_parameters, [])
        self.assertEqual(report.findings, [])
        self.assertEqual(report.missing_disclosures, [])
        self.assertEqual(report.pending_questions, [SCOPE_HINT])


class H5DemoRiskTests(unittest.TestCase):
    def test_structured_deposit_example_hits_low_floor(self):
        src = H5_EXAMPLES.read_text(encoding="utf-8")
        marker = "本产品为结构性存款"
        start = src.find(marker)
        self.assertGreaterEqual(start, 0)
        end = src.find("'", start)
        text = src[start:end]
        hits = _engine().match_risks(text, "structured_deposit")
        self.assertIn("low_floor_return", {r.pattern_id for r in hits}, text)


if __name__ == "__main__":
    unittest.main()
