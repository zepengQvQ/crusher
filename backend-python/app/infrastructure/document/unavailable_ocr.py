"""真实视觉 OCR：当前 Demo 默认明确不可用（不引入第二套 Key）。"""
from __future__ import annotations

from app.domain.ocr_errors import OcrUnavailableError


class UnavailableOcrGateway:
    async def recognize(self, image_bytes: bytes, *, filename: str) -> tuple[str, float]:
        _ = (image_bytes, filename)
        raise OcrUnavailableError("OCR_UNAVAILABLE")
