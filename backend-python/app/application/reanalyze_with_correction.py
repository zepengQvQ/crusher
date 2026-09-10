"""P2-09：基于用户纠错创建新修订任务并重跑分析。

用途：在不覆盖父任务报告的前提下提交修正并异步重分析。
输入：父 task_id + CorrectionRequest。
输出：新 AnalysisTask（带 parent_task_id / revision）。
不变量：伪造 parameter_key 拒绝；USER_ASSERTED 不伪装 DOCUMENT_FACT；不复用旧模型草稿。
"""
from __future__ import annotations

from app.application.analyze_text import PIPELINE_STAGES, AnalyzeTextUseCase
from app.domain.models.correction import (
    AnalysisRevision,
    CorrectionItem,
    CorrectionKind,
    CorrectionRecord,
    CorrectionRequest,
)
from app.domain.models.enums import ParameterKey, ProductHint
from app.domain.models.report import AnalysisTask, AnalyzeTextRequest, StageInfo
from app.domain.ports.protocols import TaskStore
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task


class CorrectionRejectedError(Exception):
    """业务层纠错拒绝（映射 HTTP 400）。"""

    def __init__(self, error_code: str, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


class ReanalyzeWithCorrectionUseCase:
    """用户纠错后创建新任务并委托 AnalyzeTextUseCase 重跑。"""

    def __init__(
        self,
        task_store: TaskStore,
        analyze_text: AnalyzeTextUseCase,
    ) -> None:
        self._tasks = task_store
        self._analyze = analyze_text

    def submit(self, parent_task_id: str, request: CorrectionRequest) -> AnalysisTask:
        parent = self._tasks.get(parent_task_id)
        if parent is None:
            raise CorrectionRejectedError(
                ErrorCode.TASK_NOT_FOUND.value,
                user_message_for(ErrorCode.TASK_NOT_FOUND),
            )
        if parent.task_status != TaskStatus.completed or parent.report is None:
            raise CorrectionRejectedError(
                "CORRECTION_PARENT_INVALID",
                "只能对已完成且有报告的任务纠错；失败任务请返回首页重新分析",
            )

        parent_param_keys = {p.key for p in parent.report.key_parameters}
        records = [
            self._to_record(item, parent, parent_param_keys)
            for item in request.corrections
        ]

        new_text = parent.source_text
        new_hint = parent.product_hint
        for rec in records:
            if rec.kind == CorrectionKind.source_text:
                new_text = rec.new_value
            elif rec.kind == CorrectionKind.product_type:
                new_hint = ProductHint(rec.new_value)

        revision_no = 1
        if parent.revision is not None:
            revision_no = parent.revision.revision_no + 1
        revision = AnalysisRevision(
            revision_no=revision_no,
            parent_task_id=parent.task_id,
            corrections=records,
            note=request.note or "",
        )

        preview = new_text.strip().replace("\n", " ")[:80]
        child = AnalysisTask(
            task_status=TaskStatus.queued,
            input_text_preview=preview,
            source_text=new_text,
            product_hint=new_hint,
            stages=[
                StageInfo(name=name, status=StageStatus.not_applicable, message="等待中")
                for name in PIPELINE_STAGES
            ],
            parent_task_id=parent.task_id,
            revision=revision,
        )
        created = self._tasks.create(child)
        parent_again = self._tasks.get(parent.task_id)
        if parent_again is None or parent_again.report is None:
            raise CorrectionRejectedError(
                "CORRECTION_PARENT_INVALID",
                "父任务在纠错过程中丢失，请重新分析",
            )
        log_task(
            "correction_submitted",
            created.task_id,
            parent_task_id=parent.task_id,
            revision_no=revision_no,
            kinds=",".join(r.kind.value for r in records),
        )
        return created

    async def run(self, task_id: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        req = AnalyzeTextRequest(text=task.source_text, product_hint=task.product_hint)
        await self._analyze.run(task_id, req)

    def _to_record(
        self,
        item: CorrectionItem,
        parent: AnalysisTask,
        parent_param_keys: set[ParameterKey],
    ) -> CorrectionRecord:
        if item.kind == CorrectionKind.source_text:
            assert item.corrected_text is not None
            return CorrectionRecord(
                kind=CorrectionKind.source_text,
                previous_value=parent.source_text,
                new_value=item.corrected_text,
            )
        if item.kind == CorrectionKind.product_type:
            assert item.product_type is not None
            prev = (
                parent.resolved_product_type.value
                if parent.resolved_product_type is not None
                else parent.product_hint.value
            )
            return CorrectionRecord(
                kind=CorrectionKind.product_type,
                previous_value=prev,
                new_value=item.product_type.value,
            )
        assert item.parameter_key is not None
        assert item.corrected_value is not None
        if item.parameter_key not in parent_param_keys:
            raise CorrectionRejectedError(
                "CORRECTION_UNKNOWN_FACT",
                f"参数 {item.parameter_key.value} 不在父任务报告中，无法修正",
            )
        prev_val = item.previous_value
        if prev_val is None and parent.report is not None:
            for p in parent.report.key_parameters:
                if p.key == item.parameter_key:
                    prev_val = p.value
                    break
        return CorrectionRecord(
            kind=CorrectionKind.fact_value,
            previous_value=prev_val,
            new_value=item.corrected_value,
            parameter_key=item.parameter_key,
        )
