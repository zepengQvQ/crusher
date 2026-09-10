"""P2-09 / P2-RC-04：基于用户纠错创建新修订任务并重跑分析。

用途：在不覆盖父任务报告的前提下提交修正并异步重分析。
输入：父 task_id + CorrectionRequest。
输出：新 AnalysisTask（带 parent_task_id / revision / effective_corrections）。
不变量：伪造 fact_id / parameter_key 拒绝；USER_ASSERTED 不伪装 DOCUMENT_FACT；不复用旧模型草稿。
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
from app.domain.rules.apply_fact_corrections import (
    parameter_key_for_field,
)
from app.domain.rules.merge_effective_corrections import merge_effective_corrections
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

_LOAN_ONLY = {
    ParameterKey.annual_interest_rate,
    ParameterKey.penalty_interest,
    ParameterKey.repayment_method,
    ParameterKey.prepayment_fee,
}
_DEPOSIT_ONLY = {
    ParameterKey.expected_return,
    ParameterKey.early_redemption,
    ParameterKey.principal_protection,
}


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
        parent_fact_ids = {f.fact_id for f in parent.report.financial_facts}
        records = [
            self._to_record(item, parent, parent_param_keys, parent_fact_ids)
            for item in request.corrections
        ]

        new_text = parent.source_text
        new_hint = parent.product_hint
        for rec in records:
            if rec.kind == CorrectionKind.source_text:
                new_text = rec.new_value
            elif rec.kind == CorrectionKind.product_type:
                new_hint = ProductHint(rec.new_value)

        effective = merge_effective_corrections(
            parent=parent, new_records=records, task_store=self._tasks
        )
        self._reject_stale_fact_corrections(
            effective=effective,
            new_text=new_text,
            new_hint=new_hint,
            parent=parent,
            this_round=records,
        )

        revision_no = 1
        if parent.revision is not None:
            revision_no = parent.revision.revision_no + 1
        revision = AnalysisRevision(
            revision_no=revision_no,
            parent_task_id=parent.task_id,
            corrections=records,
            effective_corrections=effective,
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
        parent_fact_ids: set[str],
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
        assert item.corrected_value is not None
        fact_id = (item.fact_id or "").strip() or None
        param_key = item.parameter_key
        if fact_id is not None:
            if fact_id not in parent_fact_ids:
                raise CorrectionRejectedError(
                    "CORRECTION_UNKNOWN_FACT",
                    f"fact_id {fact_id} 不属于父任务报告，无法修正",
                )
            assert parent.report is not None
            matched = next(
                f for f in parent.report.financial_facts if f.fact_id == fact_id
            )
            mapped = parameter_key_for_field(matched.field_key)
            if param_key is None:
                param_key = mapped
            elif mapped is not None and param_key != mapped:
                raise CorrectionRejectedError(
                    "CORRECTION_FACT_MISMATCH",
                    "fact_id 与 parameter_key 不匹配",
                )
        if param_key is None:
            raise CorrectionRejectedError(
                "CORRECTION_UNKNOWN_FACT",
                "无法解析要修正的事实键",
            )
        if param_key not in parent_param_keys and fact_id is None:
            raise CorrectionRejectedError(
                "CORRECTION_UNKNOWN_FACT",
                f"参数 {param_key.value} 不在父任务报告中，无法修正",
            )
        prev_val = item.previous_value
        if prev_val is None and parent.report is not None:
            for p in parent.report.key_parameters:
                if p.key == param_key:
                    prev_val = p.value
                    break
        return CorrectionRecord(
            kind=CorrectionKind.fact_value,
            previous_value=prev_val,
            new_value=item.corrected_value,
            parameter_key=param_key,
            fact_id=fact_id,
            supersedes_fact_id=fact_id,
        )

    def _reject_stale_fact_corrections(
        self,
        *,
        effective: list[CorrectionRecord],
        new_text: str,
        new_hint: ProductHint,
        parent: AnalysisTask,
        this_round: list[CorrectionRecord],
    ) -> None:
        """原文或产品类型变化后，祖先 fact_id 纠错若已不适用则明确拒绝。"""
        text_changed = any(r.kind == CorrectionKind.source_text for r in this_round)
        type_changed = any(r.kind == CorrectionKind.product_type for r in this_round)
        if not text_changed and not type_changed:
            # 仍校验产品类型与字段兼容性（hint 可能来自祖先）
            pass

        resolved_type = new_hint
        for r in effective:
            if r.kind == CorrectionKind.product_type:
                try:
                    resolved_type = ProductHint(r.new_value)
                except ValueError:
                    continue

        parent_ids = {
            f.fact_id for f in (parent.report.financial_facts if parent.report else [])
        }
        this_ids = {r.correction_id for r in this_round}
        for rec in effective:
            if rec.kind != CorrectionKind.fact_value:
                continue
            if rec.parameter_key is not None:
                if resolved_type == ProductHint.loan and rec.parameter_key in _DEPOSIT_ONLY:
                    raise CorrectionRejectedError(
                        "CORRECTION_STALE",
                        f"产品类型变为贷款后，字段 {rec.parameter_key.value} 已不适用，请重新确认",
                    )
                if (
                    resolved_type == ProductHint.structured_deposit
                    and rec.parameter_key in _LOAN_ONLY
                ):
                    raise CorrectionRejectedError(
                        "CORRECTION_STALE",
                        f"产品类型变为结构性存款后，字段 {rec.parameter_key.value} 已不适用，请重新确认",
                    )
            if text_changed and rec.correction_id not in this_ids:
                raise CorrectionRejectedError(
                    "CORRECTION_STALE",
                    "原文已修改，旧事实纠错已失效，请对最新抽取结果重新确认",
                )
        _ = new_text
        _ = parent_ids