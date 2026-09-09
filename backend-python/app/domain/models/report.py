"""报告与阶段的强类型 Schema（P0-04）。

Java 对照：DTO / Record + Bean Validation。
规则：extra=forbid；金额用 Decimal；枚举用 Enum。
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Generic, Literal, Optional, TypeVar
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.models.enums import (
    DemoErrorKind,
    EvidenceSource,
    FactStatus,
    FindingSeverity,
    ParameterKey,
    ProductHint,
    ProductTypeId,
)
from app.shared.enums import ErrorCode, StageStatus, TaskStatus

T = TypeVar("T")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class StrictModel(BaseModel):
    """默认拒绝多余字段。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Evidence(StrictModel):
    quote: str = Field(..., min_length=1, description="原文摘录")
    start: int = Field(..., ge=0, description="起始字符下标")
    end: int = Field(..., ge=0, description="结束字符下标（不含）")
    source: EvidenceSource = EvidenceSource.input_text

    @model_validator(mode="after")
    def _check_span(self) -> Evidence:
        if self.end < self.start:
            raise ValueError("evidence.end 不能小于 start")
        return self


class Finding(StrictModel):
    id: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    finding_severity: FindingSeverity
    explanation: str = Field(..., min_length=1)
    evidence: list[Evidence] = Field(..., min_length=1)
    rule_or_knowledge_id: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_review: bool = False


class ProductCandidate(StrictModel):
    product_type_id: ProductTypeId
    product_type_name: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_quotes: list[str] = Field(default_factory=list)


class ProductRiskGrade(StrictModel):
    """产品级风险评级（与 FindingSeverity 分开）。"""

    value: Optional[str] = None
    status: FactStatus
    note: str = ""

    @model_validator(mode="after")
    def _not_disclosed_has_no_value(self) -> ProductRiskGrade:
        if self.status == FactStatus.not_disclosed and self.value not in (None, ""):
            raise ValueError("not_disclosed 时 product_risk_grade.value 必须为空")
        return self


class PlainLanguage(StrictModel):
    text: str = Field(..., min_length=1)
    status: StageStatus = StageStatus.success


class KeyParameter(StrictModel):
    key: ParameterKey
    label: str = Field(..., min_length=1)
    value: Optional[str] = None
    status: FactStatus
    # 金额类参数用 Decimal，避免浮点误差；非金额保持 None
    amount: Optional[Decimal] = None

    @field_validator("amount", mode="before")
    @classmethod
    def _parse_amount(cls, value: object) -> Optional[Decimal]:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return value
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("金额无法解析为 Decimal") from exc

    @model_validator(mode="after")
    def _consistency(self) -> KeyParameter:
        if self.status == FactStatus.not_disclosed:
            if self.value not in (None, "") or self.amount is not None:
                raise ValueError("not_disclosed 参数不能带 value/amount")
        if self.key == ParameterKey.amount and self.status == FactStatus.document_fact:
            if self.amount is None:
                raise ValueError("amount 参数在 document_fact 时必须提供可解析金额")
        return self


class MissingDisclosure(StrictModel):
    key: ParameterKey
    question: str = Field(..., min_length=1)


class GeneralReference(StrictModel):
    status: FactStatus = FactStatus.general_reference
    text: str = Field(..., min_length=1)
    source: str = Field(..., min_length=1)

    @field_validator("status")
    @classmethod
    def _must_be_general(cls, value: FactStatus) -> FactStatus:
        if value != FactStatus.general_reference:
            raise ValueError("general_references.status 必须是 general_reference")
        return value


class AnalysisReport(StrictModel):
    """完整分析报告。"""

    product_candidates: list[ProductCandidate] = Field(default_factory=list)
    product_risk_grade: ProductRiskGrade
    plain_language: PlainLanguage
    key_parameters: list[KeyParameter] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    missing_disclosures: list[MissingDisclosure] = Field(default_factory=list)
    general_references: list[GeneralReference] = Field(default_factory=list)
    pending_questions: list[str] = Field(
        default_factory=list,
        description="待确认问题（可与 missing_disclosures 互补）",
    )
    disclaimer: str = Field(
        default="本 Demo 不进行用户适当性评估，不构成投资建议。",
        min_length=1,
    )


class StageInfo(StrictModel):
    name: str
    status: StageStatus
    message: str = ""


class StageResult(StrictModel, Generic[T]):
    """某一步的结果包装。"""

    status: StageStatus
    data: Optional[T] = None
    error_code: Optional[ErrorCode] = None
    message: str = ""


class CreateAnalysisRequest(StrictModel):
    """POST /api/v1/analyses 唯一请求体（应用层与 HTTP 共用）。"""

    text: str = Field(..., min_length=1, description="待分析原文")
    product_hint: ProductHint = ProductHint.auto
    locale: Literal["zh-CN"] = "zh-CN"
    demo_error: Optional[DemoErrorKind] = None

    @field_validator("text")
    @classmethod
    def _text_must_be_non_blank(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("text must not be blank")
        return text


# 兼容旧名：与 CreateAnalysisRequest 为同一类型
AnalyzeTextRequest = CreateAnalysisRequest


class AnalysisTask(StrictModel):
    task_id: str = Field(default_factory=lambda: f"tsk_{uuid4().hex[:12]}")
    task_status: TaskStatus = TaskStatus.queued
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    input_text_preview: str = ""
    # 仅存本进程内存；GET 按 task_id 返回，供报告/失败重试用
    source_text: str = ""
    stages: list[StageInfo] = Field(default_factory=list)
    error_code: Optional[ErrorCode] = None
    error_message: Optional[str] = None
    report: Optional[AnalysisReport] = None

    def touch(self) -> None:
        self.updated_at = utc_now()
