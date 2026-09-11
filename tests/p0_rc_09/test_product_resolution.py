"""
P0-RC-09：产品决议与分析范围，禁止混合报告。
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.domain.models import AnalysisScope, AnalyzeTextRequest, ProductHint  # noqa: E402
from app.domain.models.llm import LlmExplanation  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.shared.enums import StageStatus  # noqa: E402


def _settings() -> Settings:
    return Settings(
        mock_mode=True,
        llm_api_key="sk-test",
        llm_base_url="https://example.test/v1",
        llm_model="deepseek-chat",
        cors_origins="http://localhost:5173",
        max_input_chars=8000,
    )


def _uc() -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        task_store=InMemoryTaskStore(),
        knowledge_repository=LocalFileKnowledgeRepository(),
        llm_gateway=MockLlmGateway(),
        settings=_settings(),
    )


async def _run(text: str, hint: ProductHint = ProductHint.auto):
    uc = _uc()
    req = AnalyzeTextRequest(text=text, product_hint=hint)
    task = uc.submit(req)
    await uc.run(task.task_id, req)
    return uc._tasks.get(task.task_id)


def _stage(task, name: str):
    return next(s for s in task.stages if s.name == name)


class ProductResolutionTests(unittest.TestCase):
    def test_manual_deposit_hint_with_loan_text_needs_confirmation(self):
        task = asyncio.run(
            _run(
                "本贷款年化利率7.2%，提前还款需支付违约金。",
                ProductHint.structured_deposit,
            )
        )
        self.assertEqual(task.report.analysis_scope, AnalysisScope.needs_confirmation)
        self.assertEqual(task.report.findings, [])
        self.assertEqual(_stage(task, "extract").status, StageStatus.not_applicable)
        self.assertEqual(_stage(task, "rule_review").status, StageStatus.not_applicable)

    def test_manual_loan_hint_with_deposit_text_needs_confirmation(self):
        task = asyncio.run(
            _run(
                "本产品为结构性存款，突破观察区间仅获得1.20%低档收益。",
                ProductHint.loan,
            )
        )
        self.assertEqual(task.report.analysis_scope, AnalysisScope.needs_confirmation)
        self.assertEqual(task.report.findings, [])

    def test_auto_two_supported_needs_confirmation(self):
        text = (
            "本产品为结构性存款，观察区间已约定。"
            "另本合同为消费贷贷款，年化利率7.2%。"
        )
        task = asyncio.run(_run(text, ProductHint.auto))
        self.assertEqual(task.report.analysis_scope, AnalysisScope.needs_confirmation)

    def test_deposit_insurance_phrase_keeps_structured_deposit(self):
        text = "本产品为结构性存款，本金通常受存款保险保障，产品期限90天。"
        task = asyncio.run(_run(text, ProductHint.auto))
        self.assertEqual(task.report.analysis_scope, AnalysisScope.supported)
        self.assertEqual(task.report.resolved_product_type.value, "structured_deposit")

    def test_loan_with_insurance_aside_keeps_loan(self):
        text = "本合同为消费贷贷款，年化利率7.2%。附加说明：可自行购买保险。"
        task = asyncio.run(_run(text, ProductHint.auto))
        self.assertEqual(task.report.analysis_scope, AnalysisScope.supported)
        self.assertEqual(task.report.resolved_product_type.value, "loan")

    def test_fund_out_of_scope_stages_not_applicable(self):
        task = asyncio.run(_run("本产品为股票型基金，管理费1.5%。", ProductHint.auto))
        self.assertEqual(task.report.analysis_scope, AnalysisScope.out_of_scope)
        for name in ("extract", "rule_review", "evidence_validate"):
            self.assertEqual(_stage(task, name).status, StageStatus.not_applicable)
        self.assertEqual(task.report.findings, [])
        self.assertIn("未分析该产品", task.report.plain_language.text)

    def test_manual_hint_without_markers_uses_chinese_product_name(self):
        task = asyncio.run(
            _run("本说明书仅作演示，未写明产品品类。", ProductHint.structured_deposit)
        )
        self.assertEqual(task.report.analysis_scope, AnalysisScope.supported)
        self.assertEqual(task.report.resolved_product_type.value, "structured_deposit")
        self.assertTrue(task.report.product_candidates)
        top = task.report.product_candidates[0]
        self.assertEqual(top.product_type_name, "结构性存款")
        self.assertNotIn("structured_deposit", top.product_type_name)
        joined = "；".join(top.evidence_quotes or [])
        self.assertIn("手动选择", joined)
        self.assertNotIn("structured_deposit", joined)


class ReportPageScopeContractTests(unittest.TestCase):
    def test_report_page_has_three_scope_copy(self):
        src = (
            Path(__file__).resolve().parents[2]
            / "frontend-h5"
            / "src"
            / "pages"
            / "ReportPage.vue"
        ).read_text(encoding="utf-8")
        self.assertIn("未命中当前已配置规则，不等于产品没有风险", src)
        self.assertIn("当前 Demo 未分析该产品，请选择结构性存款或贷款", src)
        self.assertIn("产品类型存在冲突，请确认后重新分析", src)
        self.assertIn("analysis_scope", src)
        self.assertNotIn('image="success"', src)
        self.assertIn("这次没抓到风险点；不等于产品一定安全", src)


if __name__ == "__main__":
    unittest.main()
