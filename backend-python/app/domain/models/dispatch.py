"""P2-RC-05：分析分发请求/结果 DTO。

用途：承载「意图 → 完整性 → UseCase」统一入口的入参与出参。
Java 对照：Application Service 的 Request/Response DTO。
输入：显式页面意图、用户目标、材料信封与各意图所需字段。
输出：DispatchResult（含决议、完整性、use_case_key、下一步或业务结果）。
业务不变量：歧义/拒绝不得执行任何业务 UseCase；use_case_key 仅来自白名单。
失败方式：status=needs_clarification / incomplete / rejected / needs_prior_report。
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from app.domain.models.completeness import (
    ClarificationAnswer,
    CompletenessResult,
)
from app.domain.models.enums import ProductHint
from app.domain.models.intent import IntentDecision, IntentType, SourceEnvelope
from app.domain.models.p1_enums import CalculationKind, DayCountBasis
from app.domain.models.report import StrictModel
from app.domain.models.verification import PublicationDecision


class DispatchStatus(str, Enum):
    """分发结果状态。"""

    executed = "executed"
    needs_clarification = "needs_clarification"
    incomplete = "incomplete"
    rejected = "rejected"
    needs_prior_report = "needs_prior_report"


class DispatchRequest(StrictModel):
    """统一分发入口请求：意图字段与完整性字段同屏提交。"""

    user_query: str = Field(default="", max_length=500)
    explicit_intent: IntentType | None = None
    page_route: str | None = Field(default=None, max_length=64)
    source_envelopes: list[SourceEnvelope] = Field(default_factory=list)
    allow_model_candidate: bool = False
    # 计算/追问是否已绑定前置报告（报告页入口为 true）
    prior_report_available: bool = False

    product_hint: ProductHint = ProductHint.auto
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
    follow_up_question: str | None = None
    bound_source_id: str | None = None
    document_file_names: list[str] = Field(default_factory=list)
    document_bytes_total: int | None = None
    document_page_count: int | None = None
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)

    @field_validator("user_query", mode="before")
    @classmethod
    def _strip_query(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("follow_up_question", mode="before")
    @classmethod
    def _strip_follow_up(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class DispatchResult(StrictModel):
    """分发结果：未执行业务时 payload 为空。"""

    status: DispatchStatus
    intent_decision: IntentDecision
    completeness: CompletenessResult | None = None
    use_case_key: str | None = None
    next_steps: list[str] = Field(default_factory=list)
    publication: PublicationDecision | None = None
    # 已执行 UseCase 时的结果快照（类型因意图而异，用 Any 承载）
    payload: Any = None
