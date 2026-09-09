"""Mock OCR：固定 Fixture，供自动测试。"""
from __future__ import annotations

from app.domain.ocr_errors import OcrFailedError


class MockOcrGateway:
    """按文件名关键字返回固定文本；空图返回失败。"""

    async def recognize(self, image_bytes: bytes, *, filename: str) -> tuple[str, float]:
        name = filename.lower()
        # 仅空图片文件失败；PDF 无文本层文件名可能含 blank_page，仍应可 Mock OCR
        if name.endswith("blank.png") or (not image_bytes and "png" in name):
            raise OcrFailedError("empty image")
        if "blur" in name:
            return ("约 3.5% 年化收益，具体以合同为准", 0.42)
        if "rotate" in name:
            return ("产品风险评级：R2。期限：1年。", 0.88)
        return ("本产品为结构性存款，年化收益率3.65%。", 0.91)
