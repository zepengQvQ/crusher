"""P1-02：文档提取与确认。"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.application.extract_document import ExtractDocumentUseCase  # noqa: E402
from app.infrastructure.document.mock_ocr import MockOcrGateway  # noqa: E402
from app.infrastructure.document.pdf_image_parser import PdfImageDocumentParser  # noqa: E402
from app.infrastructure.document.unavailable_ocr import UnavailableOcrGateway  # noqa: E402
from app.main import create_app  # noqa: E402
from app.shared.enums import StageStatus  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "documents"


class DocumentExtractTests(unittest.IsolatedAsyncioTestCase):
    async def test_image_mock_ocr_success(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(MockOcrGateway()))
        data = (FIX / "sample.png").read_bytes()
        doc = await uc.extract_images([("sample.png", data)])
        self.assertEqual(doc.overall_status, StageStatus.success)
        self.assertIn("结构性存款", doc.combined_text)
        self.assertFalse(any("未发现风险" in (p.text or "") for p in doc.pages))

    async def test_blur_image_low_confidence_hint(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(MockOcrGateway()))
        data = (FIX / "blur_rate.png").read_bytes()
        doc = await uc.extract_images([("blur_rate.png", data)])
        self.assertTrue(doc.sensitive_hints)
        self.assertTrue(any("低置信" in h or "%" in h for h in doc.sensitive_hints))

    async def test_blank_image_not_success_as_safe(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(MockOcrGateway()))
        doc = await uc.extract_images([("blank.png", b"")])
        self.assertEqual(doc.overall_status, StageStatus.failed)
        self.assertFalse(doc.combined_text.strip())

    async def test_rotate_image_ok(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(MockOcrGateway()))
        data = (FIX / "rotate_page.png").read_bytes()
        doc = await uc.extract_images([("rotate_page.png", data)])
        self.assertEqual(doc.overall_status, StageStatus.success)
        self.assertIn("R2", doc.combined_text)

    async def test_blank_pdf_page_uses_ocr_mock(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(MockOcrGateway()))
        data = (FIX / "blank_page.pdf").read_bytes()
        doc = await uc.extract_pdf(data, "blank_page.pdf")
        # 无文本层 → OCR；Mock 按文件名返回默认文本
        self.assertIn(doc.overall_status, (StageStatus.success, StageStatus.partial))
        self.assertTrue(doc.pages)
        self.assertTrue(doc.pages[0].used_ocr)

    async def test_ocr_unavailable_in_real_mode_gateway(self) -> None:
        uc = ExtractDocumentUseCase(PdfImageDocumentParser(UnavailableOcrGateway()))
        data = (FIX / "sample.png").read_bytes()
        doc = await uc.extract_images([("sample.png", data)])
        self.assertEqual(doc.overall_status, StageStatus.failed)
        self.assertTrue(
            any("OCR_UNAVAILABLE" in (p.error_message or "") for p in doc.pages)
        )


class DocumentExtractHttpTests(unittest.TestCase):
    def test_upload_image_http(self) -> None:
        client = TestClient(create_app())
        png = (FIX / "sample.png").read_bytes()
        res = client.post(
            "/api/v1/documents/extract",
            files=[("files", ("sample.png", png, "image/png"))],
        )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("combined_text", body)
        self.assertTrue(body["combined_text"])


if __name__ == "__main__":
    unittest.main()
