"""分析文本用例（P0 管道 + P2-01 Harness 委托）。

固定对外契约：submit / run、任务 StageInfo、错误码映射。
实际分析委托 AnalysisHarness；本类不再内嵌产品判断与抽取编排。

用途：任务提交、异步执行、把 Harness 结果写回 TaskStore。
输入：AnalyzeTextRequest。
输出：AnalysisTask（queued → running → completed/failed）。
不变量：失败时 report=None；风险 Finding 仍由规则产生。
失败方式：按 Harness 返回的 failed_http_stage 标记，禁止一律标 explain。
"""
from __future__ import annotations

import asyncio

from app.application.analysis_harness import AnalysisHarness
from app.config.settings import Settings
from app.domain.models import AnalysisTask, AnalyzeTextRequest, ProductResolution, StageInfo
from app.domain.models.analysis_context import AnalysisContext, OutcomeStatus
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.domain.rules.engine import RuleEngine
from app.domain.rules.fact_extractor import FactExtractor
from app.domain.rules.product_resolver import (
    CONFIRM_PENDING_QUESTION,
    DEMO_SUPPORTED_PRODUCTS,
    SCOPE_PENDING_QUESTION,
    ProductResolver,
)
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

# 兼容旧导入路径（测试/文档可能引用）
__all__ = [
    "AnalyzeTextUseCase",
    "PIPELINE_STAGES",
    "DEMO_SUPPORTED_PRODUCTS",
    "SCOPE_PENDING_QUESTION",
    "CONFIRM_PENDING_QUESTION",
]

PIPELINE_STAGES = (
    "preprocess",
    "classify",
    "extract",
    "rule_review",
    "evidence_validate",
    "explain",
)


class AnalyzeTextUseCase:
    """分析流水线入口：提交任务并委托 Harness。

    Java 对照：Application Service / UseCase Facade。
    """

    def __init__(
        self,
        task_store: TaskStore,
        knowledge_repository: KnowledgeRepository,
        llm_gateway: LlmGateway,
        settings: Settings,
        harness: AnalysisHarness | None = None,
        product_resolver: ProductResolver | None = None,
    ) -> None:
        self._tasks = task_store
        self._knowledge = knowledge_repository
        self._llm = llm_gateway
        self._settings = settings
        self._rules = RuleEngine(knowledge_repository)
        self._extractor = FactExtractor(knowledge_repository)
        self._product_resolver = product_resolver or ProductResolver(self._rules)
        self._harness = harness or AnalysisHarness(
            knowledge_repository=knowledge_repository,
            llm_gateway=llm_gateway,
            product_resolver=self._product_resolver,
            fact_extractor=self._extractor,
            rule_engine=self._rules,
        )

    def submit(self, request: AnalyzeTextRequest) -> AnalysisTask:
        preview = request.text.strip().replace("\n", " ")[:80]
        task = AnalysisTask(
            task_status=TaskStatus.queued,
            input_text_preview=preview,
            source_text=request.text,
            product_hint=request.product_hint,
            stages=[
                StageInfo(name=name, status=StageStatus.not_applicable, message="等待中")
                for name in PIPELINE_STAGES
            ],
        )
        created = self._tasks.create(task)
        log_task(
            "task_created",
            created.task_id,
            text_len=len(request.text),
            demo_error=(request.demo_error.value if request.demo_error else ""),
        )
        return created

    async def run(self, task_id: str, request: AnalyzeTextRequest) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        task.task_status = TaskStatus.running
        self._tasks.save(task)

        ctx = AnalysisContext(
            task_id=task_id,
            source_text=request.text,
            product_hint=request.product_hint,
            demo_error=request.demo_error,
        )

        async def on_http_stage(name: str, status: StageStatus, message: str) -> None:
            await self._mark_stage(task_id, name, status, message)

        async def on_resolution(resolution: ProductResolution) -> None:
            await self._persist_resolution(task_id, resolution)

        result = await self._harness.run(
            ctx, on_http_stage=on_http_stage, on_resolution=on_resolution
        )

        task = self._tasks.get(task_id)
        if task is None:
            return

        if result.outcome == OutcomeStatus.refuse:
            code = result.error_code or ErrorCode.INTERNAL_ERROR
            failed = result.failed_http_stage or "explain"
            await self._fail(task_id, failed, code)
            return

        if result.outcome == OutcomeStatus.clarify and result.report is None:
            # 意图未决：不发布空风险报告
            await self._fail(task_id, "preprocess", ErrorCode.INTERNAL_ERROR)
            return

        task = self._tasks.get(task_id)
        if task is None:
            return
        task.report = result.report
        task.task_status = TaskStatus.completed
        task.error_code = None
        task.error_message = None
        if result.context.product_resolution is not None:
            task.resolved_product_type = (
                result.context.product_resolution.resolved_product_type
            )
            task.analysis_scope = result.context.product_resolution.analysis_scope
        self._tasks.save(task)
        finding_count = len(task.report.findings) if task.report is not None else 0
        log_task("task_completed", task_id, findings=finding_count)

    async def _persist_resolution(self, task_id: str, resolution: ProductResolution) -> None:
        """分类后写回任务级决议字段，失败态 GET 仍可读取。"""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.resolved_product_type = resolution.resolved_product_type
        task.analysis_scope = resolution.analysis_scope
        task.touch()
        self._tasks.save(task)

    async def _mark_stage(
        self,
        task_id: str,
        name: str,
        status: StageStatus,
        message: str,
    ) -> None:
        await asyncio.sleep(0.05)
        task = self._tasks.get(task_id)
        if task is None:
            return
        for stage in task.stages:
            if stage.name == name:
                stage.status = status
                stage.message = message
        self._tasks.save(task)

    async def _fail(self, task_id: str, failed_stage: str, code: ErrorCode) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        for stage in task.stages:
            if stage.name == failed_stage:
                stage.status = StageStatus.failed
                stage.message = user_message_for(code)
            elif stage.status == StageStatus.not_applicable:
                stage.message = "未执行"
        task.task_status = TaskStatus.failed
        task.error_code = code
        task.error_message = user_message_for(code)
        task.report = None
        self._tasks.save(task)
        log_task("task_failed", task_id, error_code=code.value)
