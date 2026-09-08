"""
事实数据客户端（pipeline 侧 facade）

默认走 MCP（stdio）：启动 mcp_server/server.py 子进程，通过 MCP 协议调用
get_grounding_block 工具拿事实——这是「用户提问 → skill 编排 → MCP 取事实」的
运行时主链路。

in_process 模式：进程内直连 knowledge_base，作为 MCP 启动失败时的降级 / 调试用。
两者共享同一套知识库数据，事实同源（都来自 data/knowledge/*.json）。
"""
import asyncio
import json
import logging
import os
import sys

from . import knowledge_base as kb

logger = logging.getLogger("term_crusher.knowledge")

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SERVER_PATH = os.path.join(_PROJECT_ROOT, "mcp_server", "server.py")


class KnowledgeClient:
    """金融事实查询客户端，默认通过 MCP stdio 调用 mcp_server。"""

    def __init__(self, mode: str = "mcp"):
        if mode not in ("mcp", "in_process"):
            raise ValueError(f"未知的 knowledge client 模式: {mode}")
        self.mode = mode

    def gather_facts(self, raw_text: str) -> dict:
        """返回事实块（fact_block），供各阶段 prompt 注入。

        返回的 dict 会带一个 `_source` 字段，标记事实来源：
          - "mcp"：真正走了 MCP 协议
          - "in_process"：显式指定的进程内直连
          - "in_process_fallback"：MCP 调用失败后降级
        """
        if self.mode == "in_process":
            facts = kb.get_grounding_block(raw_text)
            facts["_source"] = "in_process"
            return facts

        try:
            facts = asyncio.run(self._async_gather(raw_text))
            facts["_source"] = "mcp"
            return facts
        except Exception as e:
            logger.warning("MCP 调用失败，降级为进程内查询: %s", e)
            facts = kb.get_grounding_block(raw_text)
            facts["_source"] = "in_process_fallback"
            return facts

    async def _async_gather(self, raw_text: str) -> dict:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        # 用当前解释器启动 mcp_server，保证 mcp 库可用
        params = StdioServerParameters(command=sys.executable, args=[_SERVER_PATH])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(
                    "get_grounding_block", {"text": raw_text},
                )
                return self._parse_tool_result(result)

    @staticmethod
    def _parse_tool_result(result) -> dict:
        """从 MCP CallToolResult 中提取 JSON 事实块。"""
        for content in result.content:
            text = getattr(content, "text", None)
            if text:
                return json.loads(text)
        raise ValueError("MCP 工具 get_grounding_block 返回为空")

    @staticmethod
    def build_knowledge_context(facts: dict) -> str:
        """把事实块转成注入 prompt 的中文上下文文本。"""
        lines = ["以下内容是本系统唯一的事实依据，只能引用其中的定义、数值与风险解读："]

        product = facts.get("product")
        detected = facts.get("detected_product_types") or []

        if detected:
            lines.append(f"识别到的产品类型：{'、'.join(detected)}")
        else:
            lines.append("未识别到已知产品类型（若条款确属某种金融产品，product_type 字段标注「未收录」）")

        if product:
            if product.get("definition"):
                lines.append(f"- 产品定义：{product['definition']}")
            if product.get("risk_level_hint"):
                lines.append(f"- 风险等级提示：{product['risk_level_hint']}")
            if product.get("principal_protection_hint"):
                lines.append(f"- 本金保障情况：{product['principal_protection_hint']}")
            if product.get("common_risks"):
                lines.append(f"- 常见风险：{'；'.join(product['common_risks'])}")
            if product.get("regulatory_notes"):
                lines.append(f"- 监管要点：{product['regulatory_notes']}")

        terms = facts.get("terms") or []
        if terms:
            lines.append("命中术语（可用其大白话解释组织 plain_language）：")
            for t in terms:
                lines.append(f"- {t.get('term')}：{t.get('plain_explanation') or t.get('definition', '')}")

        risks = facts.get("risk_patterns") or []
        if risks:
            lines.append("命中风险模式（阶段三风险识别的优先检查清单）：")
            for r in risks:
                lines.append(f"- [{r.get('risk_level')}风险] {r.get('name')}：{r.get('explanation')}")

        return "\n".join(lines)

    @staticmethod
    def build_risk_context(facts: dict) -> str:
        """把命中风险模式转成注入阶段三的检查清单文本。"""
        risks = facts.get("risk_patterns") or []
        if not risks:
            return "（无可用风险事实数据）"
        lines = ["以下风险模式是风险识别的优先检查清单："]
        for r in risks:
            lines.append(f"- [{r.get('risk_level')}风险] {r.get('name')}：{r.get('explanation')}")
        return "\n".join(lines)
