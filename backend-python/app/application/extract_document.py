"""文档提取用例（P1-02）。

Java 对照：Application Service。
用途：把 PDF/图片转成可确认的 Source 文本。
前置条件：文件大小与页数在 Demo 限制内。
处理边界：优先 PDF 文本层；无字页/图片走 OCR；OCR 不可用明确失败。
返回：ExtractedDocument（overall_status success/partial/failed）。
"""
from __future__ import annotations

from app.domain.models.source_document import (
    MAX_IMAGE_BYTES,
    MAX_IMAGE_COUNT,
    MAX_PDF_BYTES,
    ExtractedDocument,
    PageExtractResult,
    PageExtractStatus,
)
from app.infrastructure.document.pdf_image_parser import (
    PdfImageDocumentParser,
    collect_sensitive_hints,
)
from app.shared.enums import StageStatus


class ExtractDocumentUseCase:
    def __init__(self, parser: PdfImageDocumentParser) -> None:
        self._parser = parser

    async def extract_pdf(self, data: bytes, filename: str) -> ExtractedDocument:
        if len(data) > MAX_PDF_BYTES:
            raise ValueError("PDF 超过 10MB 限制")
        pages = await self._parser.parse_pdf(data, filename)
        return self._assemble(filename, "application/pdf", pages)

    async def extract_images(
        self, files: list[tuple[str, bytes]]
    ) -> ExtractedDocument:
        if len(files) > MAX_IMAGE_COUNT:
            raise ValueError(f"图片最多 {MAX_IMAGE_COUNT} 张")
        pages: list[PageExtractResult] = []
        for i, (name, data) in enumerate(files, start=1):
            if len(data) > MAX_IMAGE_BYTES:
                pages.append(
                    PageExtractResult(
                        page=i,
                        status=PageExtractStatus.failed,
                        error_message="单张图片超过 5MB",
                        used_ocr=True,
                    )
                )
                continue
            pages.append(await self._parser.parse_image(data, name, page=i))
        return self._assemble(
            files[0][0] if files else "images",
            "image/*",
            pages,
        )

    def _assemble(
        self,
        filename: str,
        media_type: str,
        pages: list[PageExtractResult],
    ) -> ExtractedDocument:
        ok = [p for p in pages if p.status == PageExtractStatus.success and p.text.strip()]
        failed = [p for p in pages if p.status == PageExtractStatus.failed]
        if not pages:
            overall = StageStatus.failed
            msg = "未解析到任何页面"
        elif failed and ok:
            overall = StageStatus.partial
            msg = f"部分页面失败：成功 {len(ok)}，失败 {len(failed)}"
        elif failed and not ok:
            overall = StageStatus.failed
            # OCR 不可用优先提示
            if any("OCR_UNAVAILABLE" in (p.error_message or "") for p in failed):
                msg = "OCR_UNAVAILABLE"
            else:
                msg = "全部页面提取失败"
        else:
            overall = StageStatus.success
            msg = f"提取完成：{len(ok)} 页可用文字"

        combined = "\n\n".join(f"【第{p.page}页】\n{p.text}" for p in ok)

        return ExtractedDocument(
            filename=filename,
            media_type=media_type,
            overall_status=overall,
            pages=pages,
            combined_text=combined,
            sensitive_hints=collect_sensitive_hints(pages),
            message=msg,
        )
