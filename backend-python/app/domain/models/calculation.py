"""P1-04：确定性计算模型（全程 Decimal，字符串入出）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Generic, TypeVar

from pydantic import Field, field_validator, model_validator

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.p1_enums import CalculationKind, DayCountBasis, FieldStatus
from app.domain.models.report import StrictModel
from app.domain.models.verification import PublicationDecision

T = TypeVar("T")


class ExtractedField(StrictModel, Generic[T]):
    """原文抽取字段：原始值 + 标准化值 + 状态 + 证据。"""

    raw_value: str | None = None
    standard_value: T | None = None
    unit: str | None = None
    status: FieldStatus = FieldStatus.missing
    evidence: list[EvidenceRef] = Field(default_factory=list)
    user_corrected: bool = False


class ExtractedDecimalField(StrictModel):
    """OpenAPI 友好的 Decimal 字段（standard_value 用字符串）。"""

    raw_value: str | None = None
    standard_value: str | None = None
    unit: str | None = None
    status: FieldStatus = FieldStatus.missing
    evidence: list[EvidenceRef] = Field(default_factory=list)
    user_corrected: bool = False

    @field_validator("standard_value", mode="before")
    @classmethod
    def _as_str(cls, value: object) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, Decimal):
            return format(value, "f")
        return str(value).strip()


class CalculateScenarioRequest(StrictModel):
    """用户确认后的计算请求；数值一律字符串，禁止 float。"""

    kind: CalculationKind
    user_confirmed: bool = False
    principal: str | None = None
    annual_rate_percent: str | None = None
    days: str | None = None
    day_count_basis: DayCountBasis = DayCountBasis.days_365
    fee_base: str | None = None
    fee_rate_percent: str | None = None
    return_amount: str | None = None
    fee_amount: str | None = None

    @model_validator(mode="after")
    def _must_confirm(self) -> CalculateScenarioRequest:
        if not self.user_confirmed:
            raise ValueError("必须由用户确认参数后才能计算（user_confirmed=true）")
        return self


class CalculationResult(StrictModel):
    kind: CalculationKind
    formula: str
    inputs: dict[str, str] = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    result: str
    rounding: str = "ROUND_HALF_UP, scale=2"
    disclaimer: str = "这不是收益承诺，仅按你确认的参数做简单演算。"
    publication: PublicationDecision | None = Field(
        default=None,
        description="发布决策（由 PublicationService 写入）",
    )


def parse_decimal_input(raw: str | None, *, label: str) -> Decimal:
    """解析金额/天数等；拒绝空值、区间与非法格式。"""
    if raw is None or not str(raw).strip():
        raise ValueError(f"缺少必要参数：{label}")
    text = str(raw).strip().replace(",", "").replace("，", "").replace(" ", "")
    if re_looks_like_range(text):
        raise ValueError(f"{label} 不能是区间，请填写单一数值")
    if "%" in text or "％" in text:
        raise ValueError(f"{label} 请填写纯数字（百分比请用专用费率字段）")
    if "bp" in text.lower() or "百分点" in text:
        raise ValueError(f"{label} 不支持基点/百分点写法，请换算为百分比数字")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} 无法解析为数字") from exc


def parse_percent_input(raw: str | None, *, label: str) -> Decimal:
    """解析年化/费率：'3.65' 或 '3.65%' 均表示 3.65%。"""
    if raw is None or not str(raw).strip():
        raise ValueError(f"缺少必要参数：{label}")
    text = str(raw).strip().replace(",", "").replace("，", "").replace(" ", "")
    if re_looks_like_range(text):
        raise ValueError(f"{label} 不能是区间，收益区间不自动取上限")
    if "bp" in text.lower() or "百分点" in text:
        raise ValueError(f"{label} 不支持基点/百分点，请换算为百分比")
    text = text.replace("%", "").replace("％", "")
    try:
        return Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{label} 无法解析为百分比") from exc


def re_looks_like_range(text: str) -> bool:
    stripped = text.replace("%", "").replace("％", "")
    for sep in ("~", "～", "—", "至"):
        if sep in stripped:
            return True
    # 3-5 形式（中间短横且两侧像数字）
    if "-" in stripped.lstrip("-"):
        parts = stripped.lstrip("-").split("-", 1)
        if len(parts) == 2 and parts[0] and parts[1]:
            try:
                Decimal(parts[0])
                Decimal(parts[1])
                return True
            except (InvalidOperation, ValueError):
                return False
    return False
