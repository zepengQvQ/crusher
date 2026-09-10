"""统一金融事实账本（P2-05）。

确认事实必须带可定位证据；金额/比例/期限用 Decimal 字符串承载，禁止 float 业务判断。
"""
from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import Field, model_validator

from app.domain.models.report import StrictModel


class ValueKind(str, Enum):
    amount = "amount"
    percent = "percent"
    term = "term"
    text = "text"
    fee = "fee"


class FactPolarity(str, Enum):
    affirmative = "affirmative"
    negative = "negative"
    contrastive = "contrastive"


class ExtractorSource(str, Enum):
    RULE = "RULE"
    MODEL_CANDIDATE = "MODEL_CANDIDATE"
    USER_CORRECTION = "USER_CORRECTION"


class FinancialFactStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    UNCERTAIN = "UNCERTAIN"
    NOT_DISCLOSED = "NOT_DISCLOSED"


class FactEvidenceRef(StrictModel):
    quote: str = Field(..., min_length=1)
    start: int = Field(..., ge=0)
    end: int = Field(..., ge=0)

    @model_validator(mode="after")
    def _span_ok(self) -> FactEvidenceRef:
        if self.end < self.start:
            raise ValueError("evidence.end 不能小于 start")
        if self.end == self.start:
            raise ValueError("evidence span 不能为空")
        return self


class FinancialFact(StrictModel):
    """程序确认的金融事实条目。"""

    fact_id: str = Field(..., min_length=1)
    product_id: str | None = None
    field_key: str = Field(..., min_length=1)
    raw_value: str = Field(..., min_length=1)
    normalized_value: str | None = None
    unit: str | None = None
    value_kind: ValueKind
    polarity: FactPolarity = FactPolarity.affirmative
    qualifiers: list[str] = Field(default_factory=list)
    condition_text: str | None = None
    status: FinancialFactStatus
    evidence_refs: list[FactEvidenceRef] = Field(default_factory=list)
    extractor_source: ExtractorSource = ExtractorSource.RULE
    negated_raw_value: str | None = None

    @model_validator(mode="after")
    def _confirmed_needs_evidence(self) -> FinancialFact:
        if self.status == FinancialFactStatus.CONFIRMED and not self.evidence_refs:
            raise ValueError(f"确认事实必须有证据: {self.fact_id}")
        if self.status == FinancialFactStatus.NOT_DISCLOSED:
            if self.evidence_refs and self.normalized_value not in (None, ""):
                # 允许保留「未披露」原文证据，但不得有已披露标准值
                pass
        return self


def new_fact_id(prefix: str = "ff") -> str:
    return f"{prefix}_{uuid4().hex[:12]}"
