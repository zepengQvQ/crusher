"""P1-02：上传文件提取结果模型。"""
from __future__ import annotations

from enum import Enum
from uuid import uuid4

from pydantic import Field

from app.domain.models.report import StrictModel
from app.shared.enums import StageStatus


class PageExtractStatus(str, Enum):
    success = "success"
    failed = "failed"
    blank = "blank"


class PageExtractResult(StrictModel):
    page: int = Field(..., ge=1)
    status: PageExtractStatus
    text: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    error_message: str = ""
    used_ocr: bool = False


class ExtractedDocument(StrictModel):
    """用户确认前的提取结果（可编辑文本）。"""

    document_id: str = Field(default_factory=lambda: f"doc_{uuid4().hex[:10]}")
    filename: str = Field(..., min_length=1)
    media_type: str = Field(..., min_length=1)
    overall_status: StageStatus
    pages: list[PageExtractResult] = Field(default_factory=list)
    combined_text: str = ""
    sensitive_hints: list[str] = Field(
        default_factory=list,
        description="低置信或敏感数字提示，供 H5 人工确认",
    )
    message: str = ""


# Demo 限制
MAX_PDF_PAGES = 10
MAX_PDF_BYTES = 10 * 1024 * 1024
MAX_IMAGE_COUNT = 5
MAX_IMAGE_BYTES = 5 * 1024 * 1024
