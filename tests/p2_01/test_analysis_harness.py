"""P2-01：Harness 阶段顺序、停止分支与适配器标注。"""
from __future__ import annotations

import asyncio
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analysis_harness import AnalysisHarness  # noqa: E402
from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.domain.models.analysis_context import (  # noqa: E402
    AnalysisContext,
    HarnessStage,
    OutcomeStatus,
)
from app.domain.models.enums import ProductHint  # noqa: E402
from app.domain.rules.engine import RuleEngine  # noqa: E402
from app.domain.rules.fact_extractor import FactExtractor  # noqa: E402
from app.domain.rules.product_resolver import ProductResolver  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402


LOAN = "本贷款年化利率7.2%，提前还款需支付违约金。"


def _harness() -> AnalysisHarness:
    knowledge = LocalFileKnowledgeRepository()
    rules = RuleEngine(knowledge)
    return AnalysisHarness(
        knowledge_repository=knowledge,
        llm_gateway=MockLlmGateway(),
        product_resolver=ProductResolver(rules),
        fact_extractor=FactExtractor(knowledge),
        rule_engine=rules,
    )


class AnalysisHarnessTests(unittest.TestCase):
    def test_stage_order_on_success(self) -> None:
        h = _harness()
        ctx = AnalysisContext(task_id="tsk_t", source_text=LOAN, product_hint=ProductHint.auto)
        result = asyncio.run(h.run(ctx))
        self.assertEqual(result.outcome, OutcomeStatus.publish)
        self.assertEqual(result.stop_harness_stage, HarnessStage.decide_outcome)
        names = [u.name for u in result.context.http_stage_updates]
        # 关键 HTTP 阶段按既有顺序出现
        expected = [
            "preprocess",
            "classify",
            "extract",
            "rule_review",
            "evidence_validate",
            "explain",
        ]
        pos = -1
        for name in expected:
            idx = names.index(name)
            self.assertGreater(idx, pos, msg=f"{name} 应出现在前序阶段之后")
            pos = idx

    def test_stop_on_conflict_at_resolve_product(self) -> None:
        h = _harness()
        ctx = AnalysisContext(
            task_id="tsk_c",
            source_text=LOAN,
            product_hint=ProductHint.structured_deposit,
        )
        result = asyncio.run(h.run(ctx))
        self.assertEqual(result.outcome, OutcomeStatus.clarify)
        # P2-03：产品信号冲突在完整性阶段即停止，不再进入产品决议后抽取
        self.assertEqual(result.stop_harness_stage, HarnessStage.check_completeness)
        self.assertIsNotNone(result.report)
        self.assertEqual(result.report.findings, [])

    def test_adapters_are_explicitly_marked(self) -> None:
        src = Path(
            ROOT / "backend-python/app/application/analysis_harness.py"
        ).read_text(encoding="utf-8")
        self.assertIn("P2-01 兼容适配器", src)
        self.assertIn("P2-02", src)
        self.assertIn("P2-03", src)
        self.assertIn("P2-07", src)

    def test_no_agent_framework_dependency(self) -> None:
        src = Path(
            ROOT / "backend-python/app/application/analysis_harness.py"
        ).read_text(encoding="utf-8")
        for banned in ("langchain", "langgraph", "crewai", "autogen"):
            self.assertNotIn(banned, src.lower())

    def test_use_case_no_longer_owns_product_resolve(self) -> None:
        self.assertFalse(hasattr(AnalyzeTextUseCase, "_resolve_product_decision"))
        self.assertTrue(inspect.isclass(ProductResolver))
        src = Path(
            ROOT / "backend-python/app/application/analyze_text.py"
        ).read_text(encoding="utf-8")
        self.assertIn("AnalysisHarness", src)
        self.assertNotIn("def _resolve_product_decision", src)
        self.assertNotIn("def _build_report", src)


if __name__ == "__main__":
    unittest.main()
