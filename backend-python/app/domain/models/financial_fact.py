"""统一金融事实账本（P2-05 / P2-RC-02）。

确认事实必须带可定位证据；金额/比例/期限用 Decimal 字符串承载，禁止 float 业务判断。
fact_id 对同一原文+字段+证据跨运行稳定。
"""
from __future__ import annotations

import hashlib
import uuid
from enum import Enum

from pydantic import Field, model_validator

from app.domain.models.base import StrictModel


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
    USER_ASSERTED = "USER_ASSERTED"


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
    source_id: str | None = Field(
        default=None,
        description="材料来源 ID（双材料/对比）；与 product_id 分离",
    )
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
    supersedes_fact_id: str | None = Field(
        default=None,
        description="用户声明事实所替代的原文事实 ID（不删除原文记录）",
    )

    @model_validator(mode="after")
    def _confirmed_needs_evidence(self) -> FinancialFact:
        if self.status == FinancialFactStatus.CONFIRMED and not self.evidence_refs:
            raise ValueError(f"确认事实必须有证据: {self.fact_id}")
        if self.status == FinancialFactStatus.USER_ASSERTED and self.evidence_refs:
            raise ValueError(
                f"用户声明事实不得伪造原文证据: {self.fact_id}"
            )
        return self


def source_content_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def stable_fact_id(
    *,
    source_text: str,
    product_id: str | None,
    field_key: str,
    start: int,
    end: int,
    normalized_value: str | None,
    source_id: str | None = None,
) -> str:
    """同一原文/字段/证据位置/标准值 → 相同 fact_id。"""
    payload = "|".join(
        [
            source_content_hash(source_text),
            product_id or "",
            source_id or "",
            field_key,
            str(start),
            str(end),
            normalized_value or "",
        ]
    )
    return "ff_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def new_fact_id(prefix: str = "ff") -> str:
    """兼容旧调用；新抽取请用 stable_fact_id。"""
    return f"{prefix}_{uuid.uuid4().hex[:12]}"
