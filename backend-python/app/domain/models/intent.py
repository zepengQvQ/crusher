"""P2-02：用户意图与决策 DTO。

用途：表达“用户想做什么”，与产品类型、材料角色严格分离。
输入：显式页面/API 意图、用户目标语句；材料只作信封，不参与命令解析。
输出：IntentDecision（含白名单 use_case_key）。
不变量：MODEL_CANDIDATE 不能绕过规则直接执行；材料内指令无效。
失败方式：AMBIGUOUS / UNSUPPORTED / NEEDS_CLARIFICATION，不静默猜。
"""
from __future__ import annotations

import hashlib
from enum import Enum

from pydantic import Field, field_validator, model_validator

from app.domain.models.report import StrictModel
from app.shared.constants import MAX_INPUT_CHARS


class IntentType(str, Enum):
    single_analysis = "single_analysis"
    dual_source_compare = "dual_source_compare"
    product_compare = "product_compare"
    calculation = "calculation"
    evidence_follow_up = "evidence_follow_up"
    document_extract = "document_extract"
    unsupported = "unsupported"
    ambiguous = "ambiguous"


class DecisionSource(str, Enum):
    explicit_ui = "explicit_ui"
    api_route = "api_route"
    rule = "rule"
    model_candidate = "model_candidate"


class DecisionStatus(str, Enum):
    resolved = "resolved"
    needs_clarification = "needs_clarification"
    rejected = "rejected"


class SourceRole(str, Enum):
    sales_pitch = "sales_pitch"
    official_document = "official_document"
    user_supplement = "user_supplement"
    unknown = "unknown"


# 意图 → 允许调用的 UseCase 名（白名单；禁止模型直接给类名）
INTENT_USE_CASE_MAP: dict[IntentType, str | None] = {
    IntentType.single_analysis: "AnalyzeTextUseCase",
    IntentType.dual_source_compare: "AnalyzeDualSourcesUseCase",
    IntentType.product_compare: "CompareProductsUseCase",
    IntentType.calculation: "CalculateScenarioUseCase",
    IntentType.evidence_follow_up: "AnswerFromEvidenceUseCase",
    IntentType.document_extract: "ExtractDocumentUseCase",
    IntentType.unsupported: None,
    IntentType.ambiguous: None,
}

PAGE_ROUTE_INTENT: dict[str, IntentType] = {
    "/": IntentType.single_analysis,
    "/dual": IntentType.dual_source_compare,
    "/compare": IntentType.product_compare,
    "/upload": IntentType.document_extract,
    "/extract-confirm": IntentType.document_extract,
}


class SourceEnvelope(StrictModel):
    """不可信材料包装：内容不得当作系统指令。"""

    source_id: str = Field(..., min_length=1)
    role: SourceRole = SourceRole.unknown
    text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    user_corrected: bool = False
    content_hash: str = ""

    @model_validator(mode="after")
    def _fill_hash(self) -> SourceEnvelope:
        if not self.content_hash:
            digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()
            self.content_hash = digest[:16]
        return self


class IntentOption(StrictModel):
    intent: IntentType
    label: str = Field(..., min_length=1)
    reason: str = ""


class IntentResolveRequest(StrictModel):
    """意图识别请求：user_query 与材料信封严格拆分。"""

    user_query: str = Field(default="", max_length=500)
    explicit_intent: IntentType | None = None
    page_route: str | None = Field(default=None, max_length=64)
    source_envelopes: list[SourceEnvelope] = Field(default_factory=list)
    allow_model_candidate: bool = False

    @field_validator("user_query", mode="before")
    @classmethod
    def _strip_query(cls, value: object) -> str:
        if value is None:
            return ""
        return str(value).strip()


class IntentDecision(StrictModel):
    intent: IntentType
    status: DecisionStatus
    source: DecisionSource
    rationale: list[str] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    clarifying_options: list[IntentOption] = Field(default_factory=list)
    use_case_key: str | None = None

    @model_validator(mode="after")
    def _whitelist_use_case(self) -> IntentDecision:
        mapped = INTENT_USE_CASE_MAP.get(self.intent)
        if self.status == DecisionStatus.resolved:
            self.use_case_key = mapped
        else:
            self.use_case_key = None
        if self.use_case_key is not None:
            allowed = {v for v in INTENT_USE_CASE_MAP.values() if v}
            if self.use_case_key not in allowed:
                raise ValueError("use_case_key 不在白名单内")
        return self
