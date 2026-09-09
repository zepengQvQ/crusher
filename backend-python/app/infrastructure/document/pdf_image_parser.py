"""PDF 文本层 + 图片 OCR 解析实现。"""
from __future__ import annotations

import io
import re

from pypdf import PdfReader

from app.domain.models.source_document import (
    MAX_PDF_PAGES,
    PageExtractResult,
    PageExtractStatus,
)
from app.domain.ocr_errors import OcrFailedError, OcrUnavailableError
from app.domain.ports.document_parser import OcrGateway

_SENSITIVE = re.compile(
    r"\d+(?:\.\d+)?\s*%|\d+\s*万?元|R[1-5]|\d{4}[-/年]\d{1,2}[-/月]\d{1,2}"
)


class PdfImageDocumentParser:
    """普通 PDF 优先文本层；无字页再 OCR。图片一律走 OCR。"""

    def __init__(self, ocr: OcrGateway) -> None:
        self._ocr = ocr

    async def parse_pdf(self, data: bytes, filename: str) -> list[PageExtractResult]:
        reader = PdfReader(io.BytesIO(data))
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ValueError(f"PDF 超过 {MAX_PDF_PAGES} 页限制")
        pages: list[PageExtractResult] = []
        for i, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append(
                    PageExtractResult(
                        page=i,
                        status=PageExtractStatus.success,
                        text=text,
                        confidence=1.0,
                        used_ocr=False,
                    )
                )
                continue
            pages.append(await self._ocr_page(data, f"{filename}#p{i}", i))
        return pages

    async def parse_image(
        self, data: bytes, filename: str, page: int = 1
    ) -> PageExtractResult:
        return await self._ocr_page(data, filename, page)

    async def _ocr_page(self, data: bytes, filename: str, page: int) -> PageExtractResult:
        try:
            text, conf = await self._ocr.recognize(data, filename=filename)
        except OcrUnavailableError as exc:
            return PageExtractResult(
                page=page,
                status=PageExtractStatus.failed,
                error_message=str(exc) or "OCR_UNAVAILABLE",
                used_ocr=True,
            )
        except OcrFailedError as exc:
            return PageExtractResult(
                page=page,
                status=PageExtractStatus.failed,
                error_message=str(exc),
                used_ocr=True,
            )
        except Exception as exc:  # noqa: BLE001 — 单页失败不拖垮整份
            return PageExtractResult(
                page=page,
                status=PageExtractStatus.failed,
                error_message=str(exc) or "ocr failed",
                used_ocr=True,
            )
        if not text.strip():
            return PageExtractResult(
                page=page,
                status=PageExtractStatus.blank,
                used_ocr=True,
                error_message="识别结果为空",
            )
        return PageExtractResult(
            page=page,
            status=PageExtractStatus.success,
            text=text.strip(),
            confidence=conf,
            used_ocr=True,
        )


def collect_sensitive_hints(pages: list[PageExtractResult]) -> list[str]:
    hints: list[str] = []
    for p in pages:
        if p.status != PageExtractStatus.success:
            continue
        for m in _SENSITIVE.finditer(p.text):
            tip = f"第{p.page}页疑似敏感：{m.group(0)}"
            if p.confidence < 0.6:
                tip += "（低置信，请人工确认）"
            if tip not in hints:
                hints.append(tip)
    return hints[:20]
