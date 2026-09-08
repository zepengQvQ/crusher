"""
P0-07：H5 主流程契约 + product_hint 后端行为。

前端无源码静态断言钉住四页必备能力；后端验证手动产品提示生效。
"""
from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
H5 = ROOT / "frontend-h5" / "src"
sys.path.insert(0, str(ROOT / "backend-python"))

from fastapi.testclient import TestClient  # noqa: E402

from app.composition_root import get_analyze_text_use_case, get_task_store  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402


def _read(*parts: str) -> str:
    return (H5.joinpath(*parts)).read_text(encoding="utf-8")


class H5PageContractTests(unittest.TestCase):
    def test_input_page_has_product_hint_and_examples(self):
        src = _read("pages", "InputPage.vue")
        self.assertIn("productHint", src)
        self.assertIn("自动识别", src)
        self.assertIn("开始分析", src)
        self.assertIn("EXAMPLES", src)
        self.assertIn("setDraft", src)

    def test_status_page_has_elapsed_and_retry(self):
        src = _read("pages", "StatusPage.vue")
        self.assertIn("elapsed", src)
        self.assertIn("重试", src)
        self.assertIn("慢请求", src)

    def test_report_page_order_and_source_fold(self):
        src = _read("pages", "ReportPage.vue")
        # 结论在前
        self.assertLess(src.find("一句结论"), src.find("关键参数"))
        self.assertLess(src.find("关键参数"), src.find("风险发现"))
        self.assertIn("原文折叠", src)
        self.assertIn("材料未说明", src)
        self.assertIn("copyText", src)

    def test_error_page_keeps_draft_for_retry(self):
        src = _read("pages", "ErrorPage.vue")
        self.assertIn("draftText", src)
        self.assertIn("保留输入", src)
        self.assertIn("重新分析", src)
        self.assertIn("这不是", src)
    def test_no_runtime_cdn_in_h5_src(self):
        offenders = []
        for path in H5.rglob("*"):
            if path.suffix not in {".vue", ".js", ".html"}:
                continue
            text = path.read_text(encoding="utf-8")
            for needle in ("cdn.jsdelivr", "unpkg.com", "cdnjs.", "https://cdn."):
                if needle in text:
                    offenders.append(f"{path.relative_to(ROOT)}:{needle}")
        self.assertEqual(offenders, [])

    def test_app_layout_is_single_column_mobile(self):
        src = _read("App.vue")
        self.assertIn("max-width: 480px", src)
        self.assertIn("safe-area-inset-bottom", src)
        self.assertIn("min-height: 44px", src)


class ProductHintApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        get_settings.cache_clear()
        get_task_store.cache_clear()
        get_analyze_text_use_case.cache_clear()
        cls.client = TestClient(create_app())

    def test_manual_product_hint_loan_forces_loan_candidate(self):
        # 文本偏模糊，但手动选择借贷后首选应为借贷
        text = "本合同约定提前还款相关费用与利率条款。"
        res = self.client.post(
            "/api/v1/analyses",
            json={"text": text, "product_hint": "loan"},
        )
        self.assertEqual(res.status_code, 200)
        task_id = res.json()["task_id"]
        report = None
        for _ in range(40):
            body = self.client.get(f"/api/v1/analyses/{task_id}").json()
            if body["task_status"] == "completed":
                report = body["report"]
                break
            if body["task_status"] == "failed":
                self.fail(body)
            time.sleep(0.15)
        self.assertIsNotNone(report)
        top = report["product_candidates"][0]
        self.assertEqual(top["product_type_id"], "loan")


if __name__ == "__main__":
    unittest.main()
