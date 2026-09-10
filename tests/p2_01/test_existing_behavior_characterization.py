"""P2-01：锁定单材料分析既有对外行为（特征测试）。"""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from app.application.analyze_text import AnalyzeTextUseCase  # noqa: E402
from app.config.settings import Settings  # noqa: E402
from app.domain.llm_errors import LlmInvalidJsonError, LlmTimeoutError  # noqa: E402
from app.domain.models import AnalysisScope, AnalyzeTextRequest, DemoErrorKind, ProductHint  # noqa: E402
from app.domain.models.llm import LlmExplainRequest, LlmExplanation  # noqa: E402
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor  # noqa: E402
from app.infrastructure.knowledge.local_files import LocalFileKnowledgeRepository  # noqa: E402
from app.infrastructure.llm.mock_gateway import MockLlmGateway  # noqa: E402
from app.infrastructure.task_store.memory import InMemoryTaskStore  # noqa: E402
from app.shared.enums import ErrorCode, StageStatus, TaskStatus  # noqa: E402

LOAN = (
    "本贷款年化利率（单利）为7.20%，采用等额本息还款方式。"
    "借款人提前还款需支付剩余本金3%的违约金。"
)
DEPOSIT = (
    "本产品为结构性存款，期限90天，挂钩美元兑日元汇率。"
    "若观察期内汇率始终位于145.00-155.00区间，则到期年化收益率4.80%；"
    "若汇率突破观察区间，则仅获得1.20%的低档收益。"
)


def _settings() -> Settings:
    return Settings(
        mock_mode=True,
        llm_api_key="sk-test",
        llm_base_url="https://example.test/v1",
        llm_model="deepseek-chat",
        cors_origins="http://localhost:5173",
        max_input_chars=8000,
    )


def _uc(**kwargs: Any) -> AnalyzeTextUseCase:
    return AnalyzeTextUseCase(
        task_store=InMemoryTaskStore(),
        knowledge_repository=kwargs.pop("knowledge", LocalFileKnowledgeRepository()),
        llm_gateway=kwargs.pop("llm", MockLlmGateway()),
        settings=_settings(),
        **kwargs,
    )


async def _run(
    text: str,
    hint: ProductHint = ProductHint.auto,
    *,
    demo_error: DemoErrorKind | None = None,
    uc: AnalyzeTextUseCase | None = None,
):
    use_case = uc or _uc()
    req = AnalyzeTextRequest(text=text, product_hint=hint, demo_error=demo_error)
    task = use_case.submit(req)
    await use_case.run(task.task_id, req)
    return use_case._tasks.get(task.task_id)


def _stage(task, name: str):
    return next(s for s in task.stages if s.name == name)


class ExistingBehaviorCharacterizationTests(unittest.TestCase):
    def test_success_loan(self) -> None:
        task = asyncio.run(_run(LOAN))
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertIsNotNone(task.report)
        self.assertEqual(task.report.analysis_scope, AnalysisScope.supported)
        self.assertEqual(task.report.resolved_product_type.value, "loan")
        self.assertEqual(_stage(task, "explain").status, StageStatus.success)

    def test_product_conflict_needs_confirmation(self) -> None:
        task = asyncio.run(_run(LOAN, ProductHint.structured_deposit))
        self.assertEqual(task.task_status, TaskStatus.completed)
        self.assertEqual(task.report.analysis_scope, AnalysisScope.needs_confirmation)
        self.assertEqual(task.report.findings, [])
        self.assertEqual(_stage(task, "extract").status, StageStatus.not_applicable)
        self.assertEqual(_stage(task, "rule_review").status, StageStatus.not_applicable)

    def test_out_of_scope_fund(self) -> None:
        task = asyncio.run(_run("本产品为股票型基金，管理费1.5%。"))
        self.assertEqual(task.report.analysis_scope, AnalysisScope.out_of_scope)
        for name in ("extract", "rule_review", "evidence_validate"):
            self.assertEqual(_stage(task, name).status, StageStatus.not_applicable)
        self.assertEqual(task.report.findings, [])

    def test_knowledge_unavailable(self) -> None:
        class DeadKnowledge(LocalFileKnowledgeRepository):
            def ping(self) -> bool:
                return False

        task = asyncio.run(_run(LOAN, uc=_uc(knowledge=DeadKnowledge())))
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.KNOWLEDGE_UNAVAILABLE)
        self.assertIsNone(task.report)
        self.assertEqual(_stage(task, "classify").status, StageStatus.failed)

    def test_model_timeout_demo(self) -> None:
        task = asyncio.run(_run(LOAN, demo_error=DemoErrorKind.model_timeout))
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.MODEL_TIMEOUT)
        self.assertEqual(_stage(task, "explain").status, StageStatus.failed)
        self.assertIsNone(task.report)

    def test_model_invalid_json_from_gateway(self) -> None:
        class BadJsonGw:
            async def complete(self, request: LlmExplainRequest) -> LlmExplanation:
                raise LlmInvalidJsonError("bad json")

        task = asyncio.run(_run(DEPOSIT, uc=_uc(llm=BadJsonGw())))
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.INVALID_MODEL_JSON)
        self.assertEqual(_stage(task, "explain").status, StageStatus.failed)

    def test_model_timeout_from_gateway(self) -> None:
        class TimeoutGw:
            async def complete(self, request: LlmExplainRequest) -> LlmExplanation:
                raise LlmTimeoutError("timeout")

        task = asyncio.run(_run(DEPOSIT, uc=_uc(llm=TimeoutGw())))
        self.assertEqual(task.error_code, ErrorCode.MODEL_TIMEOUT)
        self.assertEqual(_stage(task, "explain").status, StageStatus.failed)

    def test_rule_exception_fails_extract_stage(self) -> None:
        class BoomExtractor(FactExtractor):
            def extract(self, text: str, product_type_id: str | None = None) -> ExtractResult:
                raise RuntimeError("规则抽取炸了")

        store = InMemoryTaskStore()
        knowledge = LocalFileKnowledgeRepository()
        uc = AnalyzeTextUseCase(
            task_store=store,
            knowledge_repository=knowledge,
            llm_gateway=MockLlmGateway(),
            settings=_settings(),
        )
        # 替换 harness 内抽取器
        uc._harness._extractor = BoomExtractor(knowledge)
        task = asyncio.run(_run(LOAN, uc=uc))
        self.assertEqual(task.task_status, TaskStatus.failed)
        self.assertEqual(task.error_code, ErrorCode.RULE_FAILED)
        self.assertEqual(_stage(task, "extract").status, StageStatus.failed)
        self.assertIsNone(task.report)


if __name__ == "__main__":
    unittest.main()
