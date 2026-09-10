"""P1-06：两款产品事实与对照模型。"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.enums import ProductHint, ProductTypeId
from app.domain.models.p1_enums import DiffStatus, FieldStatus, ProductFactDimension
from app.domain.models.report import StrictModel
from app.domain.models.verification import PublicationDecision
from app.shared.constants import MAX_INPUT_CHARS


class FactSideValue(StrictModel):
    """某一侧在固定维度上的值。"""

    display: str | None = None
    normalized: str | None = None
    status: FieldStatus = FieldStatus.missing
    evidence: list[EvidenceRef] = Field(default_factory=list)
    nature: str | None = None  # 如 single / range / guarantee / expected


class ProductFacts(StrictModel):
    product_id: str = Field(..., min_length=1)
    label: str = Field(..., min_length=1)
    product_type: ProductTypeId | None = None
    source_text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)


class DimensionComparison(StrictModel):
    dimension: ProductFactDimension
    label: str
    status: DiffStatus
    side_a: FactSideValue
    side_b: FactSideValue
    note: str = ""


class ProductCompareRequest(StrictModel):
    text_a: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    text_b: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    product_hint_a: ProductHint = ProductHint.auto
    product_hint_b: ProductHint = ProductHint.auto
    label_a: str = Field(default="产品 A", max_length=40)
    label_b: str = Field(default="产品 B", max_length=40)
    locale: Literal["zh-CN"] = "zh-CN"

    @field_validator("text_a", "text_b")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        text = (value or "").strip()
        if not text:
            raise ValueError("产品材料不能为空")
        return text


class ProductComparisonReport(StrictModel):
    product_a: ProductFacts
    product_b: ProductFacts
    dimensions: list[DimensionComparison] = Field(default_factory=list)
    disclaimer: str = (
        "本对照仅按固定维度并列展示已提交材料中的事实与缺失项，"
        "不对产品做选择判断，不构成投资建议。"
    )
    publication: PublicationDecision | None = Field(
        default=None,
        description="发布决策（由 PublicationService 写入）",
    )
