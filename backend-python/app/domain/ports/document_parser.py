"""文档解析与 OCR 端口。"""
from __future__ import annotations

from typing import Protocol

from app.domain.models.source_document import PageExtractResult


class DocumentParser(Protocol):
    """轻量 PDF/图片解析端口。"""

    async def parse_pdf(self, data: bytes, filename: str) -> list[PageExtractResult]:
        ...

    async def parse_image(
        self, data: bytes, filename: str, page: int = 1
    ) -> PageExtractResult:
        ...


class OcrGateway(Protocol):
    """视觉 OCR 网关；不可用时抛出明确错误。"""

    async def recognize(self, image_bytes: bytes, *, filename: str) -> tuple[str, float]:
        """返回 (text, confidence)。"""
        ...
