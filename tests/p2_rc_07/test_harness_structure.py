"""P2-RC-07：Harness 只编排；请求/报告拼装外置。"""
from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend-python"
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("MOCK_MODE", "true")

from app.application.analysis_harness import AnalysisHarness  # noqa: E402
from app.application.explain_request_builder import ExplainRequestBuilder  # noqa: E402
from app.application.report_assembler import ReportAssembler  # noqa: E402
from app.domain.validation.evidence_validator import (  # noqa: E402
    validate_financial_fact_evidence,
)
from app.domain.validation.publication_service import PublicationService  # noqa: E402


class HarnessStructureTests(unittest.TestCase):
    def test_builder_modules_exist_with_java_docstrings(self) -> None:
        for path in (
            BACKEND / "app" / "application" / "explain_request_builder.py",
            BACKEND / "app" / "application" / "report_assembler.py",
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn("用途：", text)
            self.assertIn("Java 对照：", text)
            self.assertIn("业务不变量：", text)

    def test_harness_no_longer_owns_build_helpers(self) -> None:
        src = (BACKEND / "app" / "application" / "analysis_harness.py").read_text(
            encoding="utf-8"
        )
        tree = ast.parse(src)
        methods = {
            node.name
            for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "AnalysisHarness"
            for node in node.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertNotIn("_build_explain_request", methods)
        self.assertNotIn("_build_report", methods)
        self.assertNotIn("_build_scope_gate_report", methods)
        self.assertIn("run", methods)

    def test_public_types_importable(self) -> None:
        self.assertTrue(callable(ExplainRequestBuilder.build))
        self.assertTrue(callable(ReportAssembler.build_supported_report))
        self.assertTrue(callable(ReportAssembler.build_scope_gate_report))
        self.assertTrue(issubclass(PublicationService, object))
        self.assertTrue(callable(validate_financial_fact_evidence))
        self.assertTrue(hasattr(AnalysisHarness, "run"))


if __name__ == "__main__":
    unittest.main()
