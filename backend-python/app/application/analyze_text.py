"""分析文本用例（P0-04：强类型报告）。"""
from __future__ import annotations

import asyncio

from app.config.settings import Settings
from app.domain.models import (
    AnalysisReport,
    AnalysisTask,
    AnalyzeTextRequest,
    DemoErrorKind,
    FactStatus,
    GeneralReference,
    KeyParameter,
    MissingDisclosure,
    ParameterKey,
    PlainLanguage,
    ProductCandidate,
    ProductRiskGrade,
    ProductTypeId,
    StageInfo,
)
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task


class AnalyzeTextUseCase:
    def __init__(
        self,
        task_store: TaskStore,
        knowledge_repository: KnowledgeRepository,
        llm_gateway: LlmGateway,
        settings: Settings,
    ) -> None:
        self._tasks = task_store
        self._knowledge = knowledge_repository
        self._llm = llm_gateway
        self._settings = settings

    def submit(self, request: AnalyzeTextRequest) -> AnalysisTask:
        preview = request.text.strip().replace("\n", " ")[:80]
        task = AnalysisTask(
            task_status=TaskStatus.queued,
            input_text_preview=preview,
            stages=[
                StageInfo(name="preprocess", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="classify", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="extract", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="rule_review", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="explain", status=StageStatus.not_applicable, message="等待中"),
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

        try:
            await self._mark_stage(task_id, "preprocess", StageStatus.success, "输入检查通过")

            if request.demo_error == DemoErrorKind.model_timeout:
                await self._fail(task_id, "extract", ErrorCode.MODEL_TIMEOUT)
                return
            if request.demo_error == DemoErrorKind.invalid_json:
                await self._fail(task_id, "extract", ErrorCode.INVALID_MODEL_JSON)
                return
            if request.demo_error == DemoErrorKind.rate_limited:
                await self._fail(task_id, "extract", ErrorCode.RATE_LIMITED)
                return

            if not self._knowledge.ping():
                await self._fail(task_id, "classify", ErrorCode.KNOWLEDGE_UNAVAILABLE)
                return

            await self._mark_stage(task_id, "classify", StageStatus.success, "分类完成（演示）")
            await self._mark_stage(task_id, "extract", StageStatus.success, "抽取完成（演示）")
            await self._mark_stage(task_id, "rule_review", StageStatus.success, "规则复核完成（演示）")
            await self._llm.complete(f"[len={len(request.text)}]")
            await self._mark_stage(task_id, "explain", StageStatus.success, "解释完成（演示）")

            task = self._tasks.get(task_id)
            if task is None:
                return
            task.report = self._build_mock_report()
            task.task_status = TaskStatus.completed
            task.error_code = None
            task.error_message = None
            self._tasks.save(task)
            log_task("task_completed", task_id, findings=len(task.report.findings))

        except TimeoutError:
            await self._fail(task_id, "extract", ErrorCode.MODEL_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            log_task("task_internal_error", task_id, err_type=type(exc).__name__)
            await self._fail(task_id, "extract", ErrorCode.INTERNAL_ERROR)

    async def _mark_stage(
        self,
        task_id: str,
        name: str,
        status: StageStatus,
        message: str,
    ) -> None:
        await asyncio.sleep(0.25)
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

    def _build_mock_report(self) -> AnalysisReport:
        return AnalysisReport(
            product_candidates=[
                ProductCandidate(
                    product_type_id=ProductTypeId.structured_deposit,
                    product_type_name="结构性存款",
                    confidence=0.5,
                    evidence_quotes=["（演示数据）"],
                )
            ],
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(
                text="这是演示结果：真实分析会在后续步骤接入。",
                status=StageStatus.success,
            ),
            key_parameters=[
                KeyParameter(
                    key=ParameterKey.term,
                    label="投资期限",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
                KeyParameter(
                    key=ParameterKey.principal_protection,
                    label="本金保障",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
                KeyParameter(
                    key=ParameterKey.expected_return,
                    label="预期收益",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
            ],
            findings=[],  # 允许 0 条；成功空 findings ≠ 失败
            missing_disclosures=[
                MissingDisclosure(
                    key=ParameterKey.principal_protection,
                    question="合同是否明确承诺本金保障？",
                )
            ],
            general_references=[
                GeneralReference(
                    text="行业常识仅供参考，不能自动填入当前材料未披露字段。",
                    source="docs/demo-scope.md",
                )
            ],
            pending_questions=["是否支持提前赎回？"],
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
        )
