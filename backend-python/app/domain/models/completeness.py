"""P2-03：输入完整性与追问 DTO。

用途：按已确认意图检查输入是否足够继续分析。
输入：意图、材料信封、可选计算/追问参数、用户已答澄清。
输出：CompletenessResult（can_continue + 最多 3 条追问）。
不变量：缺什么问什么；追问用业务语言；不由模型自由决定缺项。
失败方式：can_continue=false 时 Harness 必须停止。
"""
from __future__ import annotations

from enum import Enum

from pydantic import Field, field_validator

from app.domain.models.enums import ProductHint
from app.domain.models.intent import IntentType, SourceEnvelope
from app.domain.models.p1_enums import CalculationKind, DayCountBasis
from app.domain.models.report import StrictModel


class GapKind(str, Enum):
    """缺失/冲突类型。"""

    field_missing = "field_missing"  # 字段未提供
    not_disclosed = "not_disclosed"  # 材料未披露（预留）
    ocr_unrecognized = "ocr_unrecognized"  # OCR 未识别
    value_conflict = "value_conflict"  # 值有冲突
    user_unconfirmed = "user_unconfirmed"  # 用户尚未确认


class AnswerControl(str, Enum):
    buttons = "buttons"
    enum = "enum"
    free_text = "free_text"


class ClarifyingOption(StrictModel):
    value: str = Field(..., min_length=1, max_length=64)
    label: str = Field(..., min_length=1, max_length=80)


class ClarifyingQuestion(StrictModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    prompt: str = Field(..., min_length=1, max_length=200)
    gap_kind: GapKind
    control: AnswerControl = AnswerControl.buttons
    options: list[ClarifyingOption] = Field(default_factory=list)
    blocking_priority: int = Field(default=100, ge=1, le=1000)


class InputRequirement(StrictModel):
    """某意图下的一项确定性要求（矩阵条目）。"""

    requirement_id: str
    intent: IntentType
    description: str
    gap_kind: GapKind


class ClarificationAnswer(StrictModel):
    question_id: str = Field(..., min_length=1, max_length=64)
    value: str = Field(..., min_length=1, max_length=200)


class CompletenessCheckRequest(StrictModel):
    intent: IntentType
    source_envelopes: list[SourceEnvelope] = Field(default_factory=list)
    product_hint: ProductHint = ProductHint.auto
    # 计算意图
    calculation_kind: CalculationKind | None = None
    principal: str | None = None
    annual_rate_percent: str | None = None
    days: str | None = None
    day_count_basis: DayCountBasis | None = None
    fee_base: str | None = None
    fee_rate_percent: str | None = None
    return_amount: str | None = None
    fee_amount: str | None = None
    user_confirmed_calculation: bool = False
    # 追问意图
    follow_up_question: str | None = None
    bound_source_id: str | None = None
    # 文档提取
    document_file_names: list[str] = Field(default_factory=list)
    document_bytes_total: int | None = None
    document_page_count: int | None = None
    # 用户已回答的澄清（重新提交完整上下文）
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)

    @field_validator("follow_up_question", mode="before")
    @classmethod
    def _strip_q(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class CompletenessResult(StrictModel):
    intent: IntentType
    can_continue: bool
    questions: list[ClarifyingQuestion] = Field(default_factory=list, max_length=3)
    summary: str = ""
    answered: list[ClarificationAnswer] = Field(default_factory=list)
    # 已校验并应用澄清后的请求快照；后续 UseCase 必须使用该快照中的字段
    resolved_request: CompletenessCheckRequest | None = None
