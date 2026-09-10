"""P2-09：用户纠错与修订模型。

用途：记录对父任务的修正，驱动新任务重跑；不覆盖旧报告。
不变量：用户声明值只能是 user_asserted，不能伪装成 document_fact。
本模块不依赖 report.py，避免循环导入。
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models.enums import ParameterKey, ProductHint
from app.shared.constants import MAX_INPUT_CHARS


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CorrectionKind(str, Enum):
    """支持的修正类型。"""

    source_text = "source_text"
    product_type = "product_type"
    fact_value = "fact_value"


class CorrectionItem(_Strict):
    """单条纠错请求项。"""

    kind: CorrectionKind
    corrected_text: str | None = Field(
        default=None, max_length=MAX_INPUT_CHARS, description="原文/OCR 修正后的全文"
    )
    product_type: ProductHint | None = Field(
        default=None, description="产品类型确认（不得为 auto）"
    )
    parameter_key: ParameterKey | None = None
    corrected_value: str | None = Field(default=None, max_length=500)
    previous_value: str | None = Field(
        default=None, max_length=500, description="可选，前端展示差异用"
    )

    @model_validator(mode="after")
    def _kind_fields(self) -> CorrectionItem:
        if self.kind == CorrectionKind.source_text:
            text = (self.corrected_text or "").strip()
            if not text:
                raise ValueError("source_text 修正必须提供 corrected_text")
            object.__setattr__(self, "corrected_text", text)
        elif self.kind == CorrectionKind.product_type:
            if self.product_type is None or self.product_type == ProductHint.auto:
                raise ValueError("product_type 修正必须指定 structured_deposit 或 loan")
        elif self.kind == CorrectionKind.fact_value:
            if self.parameter_key is None:
                raise ValueError("fact_value 修正必须提供 parameter_key")
            value = (self.corrected_value or "").strip()
            if not value:
                raise ValueError("fact_value 修正必须提供 corrected_value")
            object.__setattr__(self, "corrected_value", value)
        return self


class CorrectionRequest(_Strict):
    """POST /analyses/{task_id}/corrections 请求体。"""

    corrections: list[CorrectionItem] = Field(..., min_length=1, max_length=10)
    note: str = Field(default="", max_length=200)


class CorrectionRecord(_Strict):
    """落库/落任务的修正记录（不可变快照）。"""

    correction_id: str = Field(default_factory=lambda: f"cor_{uuid4().hex[:10]}")
    kind: CorrectionKind
    previous_value: str | None = None
    new_value: str = Field(..., min_length=1)
    parameter_key: ParameterKey | None = None
    created_at: datetime = Field(default_factory=_utc_now)


class AnalysisRevision(_Strict):
    """相对父任务的一次修订元数据。"""

    revision_no: int = Field(..., ge=1)
    parent_task_id: str = Field(..., min_length=1)
    corrections: list[CorrectionRecord] = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=_utc_now)
    note: str = ""
