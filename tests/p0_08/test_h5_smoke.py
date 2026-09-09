"""
P0-08：H5 冒烟契约（输入→状态→报告，失败→重试）。
"""
from __future__ import annotations

import unittest
from pathlib import Path

H5 = Path(__file__).resolve().parents[2] / "frontend-h5" / "src"


class H5SmokeContractTests(unittest.TestCase):
    def test_happy_path_pages_wired(self):
        router = (H5 / "router" / "index.js").read_text(encoding="utf-8")
        self.assertIn("name: 'input'", router)
        self.assertIn("name: 'status'", router)
        self.assertIn("name: 'report'", router)
        self.assertIn("name: 'error'", router)
        self.assertIn("/error/:taskId?", router)

        input_page = (H5 / "pages" / "InputPage.vue").read_text(encoding="utf-8")
        self.assertIn("createAnalysis", input_page)
        self.assertIn("name: 'status'", input_page)

        status = (H5 / "pages" / "StatusPage.vue").read_text(encoding="utf-8")
        self.assertIn("name: 'report'", status)
        self.assertIn("重新查询", status)
        self.assertIn("重新分析", status)

        report = (H5 / "pages" / "ReportPage.vue").read_text(encoding="utf-8")
        self.assertIn("一句结论", report)
        self.assertIn("原文折叠", report)
        self.assertIn("source_text", report)

    def test_failure_retry_keeps_draft(self):
        error = (H5 / "pages" / "ErrorPage.vue").read_text(encoding="utf-8")
        self.assertIn("保留输入", error)
        self.assertIn("重新分析", error)
        self.assertIn("createAnalysis", error)
        self.assertIn("source_text", error)
        store = (H5 / "stores" / "task.js").read_text(encoding="utf-8")
        self.assertIn("setDraft", store)
        self.assertIn("draftText", store)
        self.assertIn("clearDraft", store)
        # sessionStorage 不得持久化全文
        self.assertNotIn("text: this.draftText", store)
        self.assertNotIn("text: this.draft", store)


if __name__ == "__main__":
    unittest.main()
