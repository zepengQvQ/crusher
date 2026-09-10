"""P1-01：双材料对照领域模型。

Java 对照：Claim / ClaimComparison / SourceDocument 为独立 DTO，不塞进 AnalysisReport。
业务不变量：没有 EvidenceRef 的结论不得标为 confirmed；not_found ≠ 现实不存在。
"""
from __future__ import annotations

from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator, model_validator

from app.domain.models.enums import ProductHint
from app.domain.models.financial_fact import FinancialFact
from app.domain.models.p1_enums import ClaimStatus, ClaimSubject, SourceType
from app.domain.models.report import StrictModel
from app.domain.models.verification import PublicationDecision
from app.shared.constants import MAX_INPUT_CHARS


class EvidenceRef(StrictModel):
    """对照用的证据引用（可带页码；纯文本页码为 None）。"""

    source_id: str = Field(..., min_length=1)
    quote: str = Field(..., min_length=1)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)
    page: int | None = Field(default=None, ge=1)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    user_corrected: bool = False

    @model_validator(mode="after")
    def _span(self) -> EvidenceRef:
        if self.end < self.start:
            raise ValueError("evidence.end 不能小于 start")
        return self


class SourceDocument(StrictModel):
    """一次对照中的一侧材料。"""

    source_id: str = Field(default_factory=lambda: f"src_{uuid4().hex[:10]}")
    source_type: SourceType
    name: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    pages: int = Field(default=1, ge=1)


class Claim(StrictModel):
    """从销售侧抽出的标准化主张。"""

    claim_id: str = Field(..., min_length=1)
    subject: ClaimSubject
    summary: str = Field(..., min_length=1)
    negated: bool = False
    numeric_value: Decimal | None = None
    numeric_unit: Literal["percent", "bp", "months", "days", "yuan"] | None = None
    evidence: EvidenceRef

    @field_validator("numeric_value", mode="before")
    @classmethod
    def _decimal(cls, value: object) -> Decimal | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        return Decimal(str(value))


class ClaimComparison(StrictModel):
    """一张对照卡：销售主张 vs 正式材料。"""

    comparison_id: str = Field(..., min_length=1)
    subject: ClaimSubject
    status: ClaimStatus
    summary: str = Field(..., min_length=1)
    sales_claim: Claim | None = None
    official_evidence: EvidenceRef | None = None
    suggested_follow_up: str = ""

    @model_validator(mode="after")
    def _evidence_rules(self) -> ClaimComparison:
        if self.sales_claim is None:
            raise ValueError("对照卡必须包含销售侧主张")
        if self.status == ClaimStatus.confirmed and self.official_evidence is None:
            raise ValueError("confirmed 必须有正式材料证据")
        if self.status == ClaimStatus.conflict and self.official_evidence is None:
            raise ValueError("conflict 必须同时引用销售与正式材料证据")
        return self


class DualAnalysisRequest(StrictModel):
    """POST /api/v1/dual-analyses 请求体。"""

    sales_text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    official_text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    product_hint: ProductHint = ProductHint.auto
    locale: Literal["zh-CN"] = "zh-CN"

    @field_validator("sales_text", "official_text")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("材料不能为空")
        return text


class DualAnalysisReport(StrictModel):
    """双材料对照报告。"""

    sales_source: SourceDocument
    official_source: SourceDocument
    comparisons: list[ClaimComparison] = Field(default_factory=list)
    pending_questions: list[str] = Field(default_factory=list)
    sales_financial_facts: list[FinancialFact] = Field(
        default_factory=list,
        description="销售材料侧同源 FinancialFact 账本",
    )
    official_financial_facts: list[FinancialFact] = Field(
        default_factory=list,
        description="正式材料侧同源 FinancialFact 账本",
    )
    disclaimer: str = (
        "本对照仅比较已提交材料中的表述，不判断合同法律效力，不对销售人员打分。"
    )
    publication: PublicationDecision | None = Field(
        default=None,
        description="发布决策（由 PublicationService 写入）",
    )
