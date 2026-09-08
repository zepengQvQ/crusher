"""
金融知识 MCP server —— 把 backend/knowledge_base.py 的事实查询暴露成 MCP 工具。

供外部 agent（Claude Code 等）按需查询；pipeline 热路径默认进程内直连
knowledge_base（见 backend/knowledge_client.py），两者共享同一套事实查询逻辑。

运行（stdio，默认）：
    python mcp_server/server.py
或用 MCP Inspector 调试：
    mcp dev mcp_server/server.py
"""
import os
import sys

# 将 legacy 目录加入 path，便于导入 backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "legacy"))

from mcp.server.mcpserver import MCPServer  # noqa: E402

from backend import knowledge_base as kb  # noqa: E402

mcp = MCPServer("crusher-finance-knowledge")


@mcp.tool()
def get_grounding_block(text: str) -> dict:
    """
    对一段金融条款文本做确定性事实检索，一次返回：
      - detected_product_types：命中的产品类型名称列表
      - product：首个命中产品类型的完整条目
      - terms：命中的术语词典条目（含定义与大白话解释）
      - risk_patterns：命中的风险模式（含风险等级与解读）
    纯确定性匹配，不调用 LLM。这些事实是解读条款的唯一依据。
    """
    return kb.get_grounding_block(text)


@mcp.tool()
def search_terms(query: str, limit: int = 10) -> list[dict]:
    """按关键词搜索金融术语词典（匹配术语名/别名/分类），返回定义与大白话解释。"""
    return kb.search_terms(query, limit=limit)


@mcp.tool()
def get_product(name: str) -> dict:
    """按名称或别名查询金融产品类型（定义、典型条款、风险等级、本金保障、常见风险、监管要点）。未命中返回空 dict。"""
    return kb.get_product(name) or {}


@mcp.tool()
def match_risks(text: str) -> list[dict]:
    """对金融条款文本匹配已知风险模式，返回风险点列表（含风险等级与解读）。"""
    return kb.match_risks(text)


if __name__ == "__main__":
    mcp.run(transport="stdio")
