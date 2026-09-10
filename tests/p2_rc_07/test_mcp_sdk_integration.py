"""P2-RC-07：真实 MCP SDK 会话协议测试（不得静默 skip）。"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from app.interfaces.mcp.tools import TOOL_WHITELIST  # noqa: E402


def _require_mcp() -> None:
    try:
        import mcp  # noqa: F401
    except ImportError as exc:  # pragma: no cover
        if os.environ.get("CRUSHER_REQUIRE_MCP") == "1":
            raise AssertionError(
                "mcp 未安装；显式 RC-07 / test-p2-10 要求先执行 make setup-mcp"
            ) from exc
        raise unittest.SkipTest(
            "mcp 未安装；执行 make setup-mcp 后可测 SDK 集成"
        ) from exc


class McpSdkIntegrationTests(unittest.TestCase):
    """通过 ClientSession 协议验收，不依赖 FastMCP 私有 _tool_manager。"""

    def setUp(self) -> None:
        _require_mcp()

    def test_sdk_tools_resources_and_calls(self) -> None:
        from mcp.shared.memory import create_connected_server_and_client_session

        from app.interfaces.mcp.server import build_mcp_server

        async def _run() -> None:
            mcp_app = build_mcp_server()
            async with create_connected_server_and_client_session(
                mcp_app._mcp_server,  # noqa: SLF001 — 公开协议入口，非工具表白名单验收
                raise_exceptions=True,
            ) as session:
                tools = await session.list_tools()
                names = {t.name for t in tools.tools}
                self.assertEqual(names, set(TOOL_WHITELIST))

                resources = await session.list_resources()
                resource_uris = {str(r.uri) for r in resources.resources}
                self.assertIn("finance://manifest", resource_uris)

                templates = await session.list_resource_templates()
                template_uris = {t.uriTemplate for t in templates.resourceTemplates}
                self.assertIn("finance://products/{product_type}", template_uris)
                self.assertIn("finance://terms/{term_id}", template_uris)
                self.assertIn("finance://rules/{rule_id}", template_uris)

                manifest = await session.read_resource("finance://manifest")
                self.assertTrue(manifest.contents)
                manifest_text = getattr(manifest.contents[0], "text", "") or ""
                manifest_data = json.loads(manifest_text)
                self.assertIn("content_version", manifest_data)
                self.assertIn("supported_products", manifest_data)

                product = await session.read_resource("finance://products/loan")
                self.assertTrue(product.contents)
                product_text = getattr(product.contents[0], "text", "") or ""
                self.assertIn("loan", product_text)

                analyze = await session.call_tool(
                    "analyze_financial_text",
                    {
                        "text": "本贷款提前还款需支付本金3%的违约金。",
                        "product_hint": "loan",
                    },
                )
                self.assertFalse(analyze.isError, getattr(analyze.content[0], "text", ""))
                analyze_payload = json.loads(analyze.content[0].text)
                self.assertIn("publication", analyze_payload)
                self.assertIn(analyze_payload["task_status"], {"completed", "failed"})

                compare = await session.call_tool(
                    "compare_financial_products",
                    {
                        "text_a": "贷款金额10万元，年利率7.2%。",
                        "text_b": "本贷款金额8万元，年利率6.5%。",
                        "product_hint_a": "loan",
                        "product_hint_b": "loan",
                    },
                )
                self.assertFalse(compare.isError, getattr(compare.content[0], "text", ""))
                compare_payload = json.loads(compare.content[0].text)
                self.assertIn("publication", compare_payload)
                self.assertIn(
                    compare_payload["publication"]["outcome"],
                    {"publish", "publish_partial", "clarify", "refuse"},
                )
                self.assertNotIn("recommendation", compare_payload)
                self.assertNotIn("ranking", compare_payload)

                from app.domain.models.llm import make_simple_draft

                draft = make_simple_draft(
                    "建议购买，更适合你。", knowledge_ids=["knowledge:demo"]
                )
                verify = await session.call_tool(
                    "verify_financial_draft",
                    {
                        "request_json": json.dumps(
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
                            ensure_ascii=False,
                        )
                    },
                )
                self.assertFalse(verify.isError, getattr(verify.content[0], "text", ""))
                verify_payload = json.loads(verify.content[0].text)
                self.assertFalse(verify_payload["can_publish"])

        asyncio.run(_run())

    def test_no_asyncio_run_inside_sync_tool_bodies(self) -> None:
        """生产 MCP 工具实现不得在同步体里直接 asyncio.run。"""
        tools_src = (
            ROOT / "backend-python" / "app" / "interfaces" / "mcp" / "tools.py"
        ).read_text(encoding="utf-8")
        server_src = (
            ROOT / "backend-python" / "app" / "interfaces" / "mcp" / "server.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("asyncio.run(", server_src)
        self.assertIn("async def analyze_financial_text", tools_src)
        analyze_start = tools_src.index("async def analyze_financial_text")
        next_defs = [
            i
            for i in (
                tools_src.find("\ndef ", analyze_start + 1),
                tools_src.find("\nasync def ", analyze_start + 1),
            )
            if i > 0
        ]
        analyze_end = min(next_defs) if next_defs else len(tools_src)
        self.assertNotIn("asyncio.run(", tools_src[analyze_start:analyze_end])


if __name__ == "__main__":
    unittest.main()
