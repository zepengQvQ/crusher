"""P2-10：MCP 安全边界 — 白名单、无任意路径/URL/shell。"""
from __future__ import annotations

import ast
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend-python"))
os.environ.setdefault("MOCK_MODE", "true")

from app.interfaces.mcp.resources import ResourceAccessError, read_resource  # noqa: E402
from app.interfaces.mcp.sanitize import sanitize_public_payload  # noqa: E402
from app.interfaces.mcp.tools import McpToolError, invoke_tool  # noqa: E402

MCP_DIR = ROOT / "backend-python" / "app" / "interfaces" / "mcp"


class McpSecurityBoundaryTests(unittest.TestCase):
    def test_unknown_tool_rejected(self) -> None:
        with self.assertRaises(McpToolError):
            invoke_tool("rm_rf_all", {})
        with self.assertRaises(McpToolError):
            invoke_tool("fetch_url", {"url": "https://example.com"})

    def test_path_traversal_resource_rejected(self) -> None:
        with self.assertRaises(ResourceAccessError):
            read_resource("finance://products/../../etc/passwd")
        with self.assertRaises(ResourceAccessError):
            read_resource("file:///etc/passwd")
        with self.assertRaises(ResourceAccessError):
            read_resource("finance://products/../secret")

    def test_sanitize_strips_secrets(self) -> None:
        raw = {
            "ok": 1,
            "api_key": "sk-secret",
            "nested": {"llm_api_key": "x", "value": 2},
            "base_url": "http://evil",
        }
        clean = sanitize_public_payload(raw)
        self.assertEqual(clean["ok"], 1)
        self.assertNotIn("api_key", clean)
        self.assertNotIn("base_url", clean)
        self.assertEqual(clean["nested"]["value"], 2)
        self.assertNotIn("llm_api_key", clean["nested"])

    def test_mcp_modules_have_no_shell_or_url_open(self) -> None:
        forbidden_calls = {"system", "popen", "check_output", "run", "urlopen", "urlretrieve"}
        for path in MCP_DIR.glob("*.py"):
            if path.name == "server.py":
                # server.run 是 MCP SDK 的 stdio run，允许属性名；仍禁止 subprocess
                tree = ast.parse(path.read_text(encoding="utf-8"))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            self.assertNotIn(alias.name.split(".")[0], {"subprocess", "requests"})
                    if isinstance(node, ast.ImportFrom) and node.module:
                        self.assertFalse(node.module.startswith("subprocess"))
                        self.assertFalse(node.module.startswith("requests"))
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        self.assertNotIn(root, {"subprocess", "requests", "httpx"})
                if isinstance(node, ast.ImportFrom) and node.module:
                    root = node.module.split(".")[0]
                    self.assertNotIn(root, {"subprocess", "requests", "httpx"})
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden_calls and isinstance(
                        node.func.value, ast.Name
                    ):
                        self.assertNotEqual(node.func.value.id, "os")
                        self.assertNotEqual(node.func.value.id, "subprocess")

    def test_server_registers_only_whitelist_when_mcp_installed(self) -> None:
        try:
            import mcp  # noqa: F401
        except ImportError as exc:
            if os.environ.get("CRUSHER_REQUIRE_MCP") == "1":
                self.fail(f"mcp 未安装；显式 P2-10 测试要求先 make setup-mcp: {exc}")
            self.skipTest("mcp 未安装；执行 make setup-mcp 后可测 SDK 注册")
        from mcp.shared.memory import create_connected_server_and_client_session

        from app.interfaces.mcp.server import build_mcp_server
        from app.interfaces.mcp.tools import TOOL_WHITELIST

        async def _list() -> set[str]:
            mcp_app = build_mcp_server()
            async with create_connected_server_and_client_session(
                mcp_app._mcp_server,  # noqa: SLF001
                raise_exceptions=True,
            ) as session:
                tools = await session.list_tools()
                return {t.name for t in tools.tools}

        import asyncio

        names = asyncio.run(_list())
        self.assertEqual(names, set(TOOL_WHITELIST))


if __name__ == "__main__":
    unittest.main()
