"""P2-10：MCP 工具委托 Use Case，与 HTTP 语义一致。"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from app.interfaces.mcp.resources import list_resource_uris, read_resource  # noqa: E402
from app.interfaces.mcp.tools import (  # noqa: E402
    TOOL_WHITELIST,
    invoke_tool,
)
from app.main import create_app  # noqa: E402


class McpToolsTests(unittest.TestCase):
    def test_fastapi_imports_without_mcp_server_module(self) -> None:
        """核心应用不依赖 mcp 包导入路径（server 懒加载）。"""
        app = create_app()
        self.assertIsNotNone(app)
        # 确保 main 依赖链未强制 import interfaces.mcp.server
        import app.main as main_mod

        src = Path(main_mod.__file__).read_text(encoding="utf-8")
        self.assertNotIn("interfaces.mcp.server", src)
        self.assertNotIn("from mcp", src)

    def test_tool_whitelist_names(self) -> None:
        self.assertEqual(
            TOOL_WHITELIST,
            frozenset(
                {
                    "resolve_financial_intent",
                    "analyze_financial_text",
                    "compare_financial_products",
                    "calculate_financial_scenario",
                    "verify_financial_draft",
                }
            ),
        )

    def test_resolve_intent_matches_use_case(self) -> None:
        out = invoke_tool(
            "resolve_financial_intent",
            {
                "user_query": "",
                "explicit_intent": "single_analysis",
                "source_envelopes": [],
            },
        )
        self.assertEqual(out["intent"], "single_analysis")
        self.assertEqual(out["status"], "resolved")

    def test_analyze_financial_text_returns_publication(self) -> None:
        out = invoke_tool(
            "analyze_financial_text",
            {
                "text": "本贷款提前还款需支付本金3%的违约金。",
                "product_hint": "loan",
            },
        )
        self.assertIn(out["task_status"], {"completed", "failed"})
        self.assertIn("publication", out)
        if out["task_status"] == "completed":
            self.assertIsNotNone(out["report"])
            self.assertIn(out["publication"]["outcome"], {
                "publish",
                "publish_partial",
                "clarify",
            })

    def test_calculate_scenario(self) -> None:
        out = invoke_tool(
            "calculate_financial_scenario",
            {
                "kind": "fee",
                "user_confirmed": True,
                "fee_base": "100000",
                "fee_rate_percent": "3",
            },
        )
        self.assertEqual(out["kind"], "fee")
        self.assertIn("formula", out)
        self.assertIn("result", out)
        self.assertIn("inputs", out)

    def test_compare_products_no_ranking(self) -> None:
        out = invoke_tool(
            "compare_financial_products",
            {
                "text_a": "结构性存款期限90天",
                "text_b": "本贷款年利率7.2%",
                "locale": "zh-CN",
            },
        )
        self.assertIn("dimensions", out)
        self.assertNotIn("recommendation", out)
        self.assertNotIn("ranking", out)

    def test_verify_draft_gate(self) -> None:
        from app.domain.models.llm import make_simple_draft

        draft = make_simple_draft("建议购买，更适合你。", knowledge_ids=["knowledge:demo"])
        out = invoke_tool(
            "verify_financial_draft",
            {
                "source_text": "本贷款提前还款需支付违约金。",
                "draft": draft.model_dump(mode="json"),
                "findings": [],
                "key_parameters": [],
                "financial_facts": [],
                "allowed_fact_ids": [],
                "allowed_finding_ids": [],
                "allowed_knowledge_ids": ["knowledge:demo"],
            },
        )
        self.assertFalse(out["can_publish"])

    def test_manifest_resource(self) -> None:
        uris = list_resource_uris()
        self.assertIn("finance://manifest", uris)
        data = read_resource("finance://manifest")
        self.assertIn("content_version", data)
        self.assertIn("supported_products", data)


if __name__ == "__main__":
    unittest.main()
