"""P2-10：本地 STDIO MCP Server。

日志只写 stderr；stdout 留给 MCP 协议。
不安装 mcp 可选依赖时，本模块不可导入，不影响 FastAPI。

注意：工具函数故意不用 `X | Y` / `dict[str, Any]` 注解，
避免 FastMCP 1.x 在嵌套函数里对未求值注解调用 issubclass 失败。
"""
import json
import logging
import sys

from app.interfaces.mcp.resources import list_resource_uris, read_resource
from app.interfaces.mcp.tools import TOOL_WHITELIST, invoke_tool

logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("crusher.mcp")


def _resolve_financial_intent(
    user_query="",
    explicit_intent="",
    page_route="",
    allow_model_candidate=False,
):
    """解析用户金融分析意图（不执行分析）。"""
    payload = {
        "user_query": user_query,
        "allow_model_candidate": bool(allow_model_candidate),
        "source_envelopes": [],
    }
    if str(explicit_intent).strip():
        payload["explicit_intent"] = str(explicit_intent).strip()
    if str(page_route).strip():
        payload["page_route"] = str(page_route).strip()
    return invoke_tool("resolve_financial_intent", payload)


def _analyze_financial_text(text, product_hint="auto"):
    """单材料分析；返回发布门禁后的结构化结果。"""
    return invoke_tool(
        "analyze_financial_text",
        {"text": text, "product_hint": product_hint},
    )


def _compare_financial_products(
    text_a,
    text_b,
    product_hint_a="auto",
    product_hint_b="auto",
    label_a="产品 A",
    label_b="产品 B",
):
    """两款产品事实对照；不返回推荐或排名。"""
    return invoke_tool(
        "compare_financial_products",
        {
            "text_a": text_a,
            "text_b": text_b,
            "product_hint_a": product_hint_a,
            "product_hint_b": product_hint_b,
            "label_a": label_a,
            "label_b": label_b,
            "locale": "zh-CN",
        },
    )


def _calculate_financial_scenario(
    kind,
    user_confirmed=False,
    principal="",
    annual_rate_percent="",
    days="",
    day_count_basis="365",
    fee_base="",
    fee_rate_percent="",
    return_amount="",
    fee_amount="",
):
    """确定性场景计算；数值用字符串，须 user_confirmed=true。"""

    def _opt(value):
        text = str(value or "").strip()
        return text or None

    return invoke_tool(
        "calculate_financial_scenario",
        {
            "kind": kind,
            "user_confirmed": bool(user_confirmed),
            "principal": _opt(principal),
            "annual_rate_percent": _opt(annual_rate_percent),
            "days": _opt(days),
            "day_count_basis": day_count_basis,
            "fee_base": _opt(fee_base),
            "fee_rate_percent": _opt(fee_rate_percent),
            "return_amount": _opt(return_amount),
            "fee_amount": _opt(fee_amount),
        },
    )


def _verify_financial_draft(request_json):
    """对结构化草稿做确定性发布前校验；入参为 JSON 字符串。"""
    try:
        payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        raise ValueError("request_json 不是合法 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("request_json 必须是对象")
    return invoke_tool("verify_financial_draft", payload)


def build_mcp_server():
    """构造 FastMCP 实例并注册白名单 Tools / Resources。"""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "未安装 MCP 可选依赖。请执行: make setup-mcp"
        ) from exc

    mcp = FastMCP(
        "crusher-finance",
        instructions=(
            "金融话术粉碎机本地 MCP：只读知识资源 + 白名单工具。"
            "工具委托现有 Use Case，不提供任意文件/URL/shell。"
        ),
    )

    @mcp.resource("finance://manifest")
    def resource_manifest():
        return json.dumps(read_resource("finance://manifest"), ensure_ascii=False)

    @mcp.resource("finance://products/{product_type}")
    def resource_product(product_type: str):
        return json.dumps(
            read_resource(f"finance://products/{product_type}"),
            ensure_ascii=False,
        )

    @mcp.resource("finance://terms/{term_id}")
    def resource_term(term_id: str):
        return json.dumps(
            read_resource(f"finance://terms/{term_id}"),
            ensure_ascii=False,
        )

    @mcp.resource("finance://rules/{rule_id}")
    def resource_rule(rule_id: str):
        return json.dumps(
            read_resource(f"finance://rules/{rule_id}"),
            ensure_ascii=False,
        )

    mcp.add_tool(_resolve_financial_intent, name="resolve_financial_intent")
    mcp.add_tool(_analyze_financial_text, name="analyze_financial_text")
    mcp.add_tool(_compare_financial_products, name="compare_financial_products")
    mcp.add_tool(_calculate_financial_scenario, name="calculate_financial_scenario")
    mcp.add_tool(_verify_financial_draft, name="verify_financial_draft")

    logger.info(
        "mcp_tools=%s resource_samples=%s",
        sorted(TOOL_WHITELIST),
        list_resource_uris()[:5],
    )
    return mcp


def main():
    """STDIO 入口：python -m app.interfaces.mcp.server"""
    server = build_mcp_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
