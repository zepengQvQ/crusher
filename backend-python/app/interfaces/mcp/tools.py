"""P2-10：MCP Tools —— 仅白名单，委托现有 Use Case / 校验门禁。

分析类工具为 async，避免在已有事件循环内调用 asyncio.run()。
"""
from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import Field, ValidationError

from app.composition_root import (
    get_analyze_text_use_case,
    get_calculate_scenario_use_case,
    get_compare_products_use_case,
    get_resolve_intent_use_case,
    get_task_store,
)
from app.domain.models.calculation import CalculateScenarioRequest
from app.domain.models.financial_fact import FinancialFact
from app.domain.models.intent import IntentResolveRequest
from app.domain.models.llm import LlmAnalysisDraft
from app.domain.models.product_facts import ProductCompareRequest
from app.domain.models.report import (
    AnalyzeTextRequest,
    Finding,
    KeyParameter,
    StrictModel,
)
from app.domain.validation.publication_service import PublicationService
from app.interfaces.mcp.sanitize import sanitize_public_payload
from app.shared.constants import MAX_INPUT_CHARS

TOOL_WHITELIST = frozenset(
    {
        "resolve_financial_intent",
        "analyze_financial_text",
        "compare_financial_products",
        "calculate_financial_scenario",
        "verify_financial_draft",
    }
)

_PUBLICATION = PublicationService()


class McpToolError(ValueError):
    """工具调用业务/校验错误（不含堆栈）。"""


class AnalyzeFinancialTextArgs(StrictModel):
    text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    product_hint: str = "auto"


class VerifyFinancialDraftArgs(StrictModel):
    source_text: str = Field(..., min_length=1, max_length=MAX_INPUT_CHARS)
    draft: LlmAnalysisDraft
    findings: list[Finding] = Field(default_factory=list)
    key_parameters: list[KeyParameter] = Field(default_factory=list)
    financial_facts: list[FinancialFact] = Field(default_factory=list)
    allowed_fact_ids: list[str] = Field(default_factory=list)
    allowed_finding_ids: list[str] = Field(default_factory=list)
    allowed_knowledge_ids: list[str] = Field(default_factory=list)


def _dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return sanitize_public_payload(model.model_dump(mode="json"))
    return sanitize_public_payload(model)


def resolve_financial_intent(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        req = IntentResolveRequest.model_validate(payload)
    except ValidationError as exc:
        raise McpToolError("意图请求不合法") from exc
    decision = get_resolve_intent_use_case().execute(req)
    return _dump(decision)


async def analyze_financial_text(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        args = AnalyzeFinancialTextArgs.model_validate(payload)
        req = AnalyzeTextRequest.model_validate(
            {"text": args.text, "product_hint": args.product_hint, "locale": "zh-CN"}
        )
    except ValidationError as exc:
        raise McpToolError("分析请求不合法") from exc

    uc = get_analyze_text_use_case()
    store = get_task_store()
    task = uc.submit(req)
    await uc.run(task.task_id, req)
    done = store.get(task.task_id)
    if done is None:
        raise McpToolError("任务丢失")
    publication = done.publication
    if publication is None and done.report is not None:
        publication = done.report.publication
    return sanitize_public_payload(
        {
            "task_id": done.task_id,
            "task_status": done.task_status.value,
            "error_code": done.error_code.value if done.error_code else None,
            "error_message": done.error_message,
            "publication": _dump(publication) if publication else None,
            "report": _dump(done.report) if done.report is not None else None,
            "resolved_product_type": (
                done.resolved_product_type.value if done.resolved_product_type else None
            ),
            "analysis_scope": done.analysis_scope.value if done.analysis_scope else None,
        }
    )


def compare_financial_products(payload: dict[str, Any]) -> dict[str, Any]:
    """产品对照：走 CompareProductsUseCase → PublicationService（与 RC-06 同门禁）。"""
    try:
        req = ProductCompareRequest.model_validate(payload)
    except ValidationError as exc:
        raise McpToolError("产品对照请求不合法") from exc
    report = get_compare_products_use_case().execute(req)
    data = _dump(report)
    data.pop("recommendation", None)
    data.pop("ranking", None)
    data.pop("score", None)
    return data


def calculate_financial_scenario(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        req = CalculateScenarioRequest.model_validate(payload)
    except ValidationError as exc:
        raise McpToolError("计算请求不合法") from exc
    try:
        result = get_calculate_scenario_use_case().execute(req)
    except ValueError as exc:
        raise McpToolError(str(exc) or "计算失败") from exc
    return _dump(result)


def verify_financial_draft(payload: dict[str, Any]) -> dict[str, Any]:
    try:
        args = VerifyFinancialDraftArgs.model_validate(payload)
    except ValidationError as exc:
        raise McpToolError("校验请求不合法") from exc
    plain = args.draft.render_plain_language()
    result = _PUBLICATION.verify_single_analysis(
        source_text=args.source_text,
        draft=args.draft,
        plain=plain,
        findings=list(args.findings),
        key_parameters=list(args.key_parameters),
        financial_facts=list(args.financial_facts),
        allowed_fact_ids=list(args.allowed_fact_ids),
        allowed_finding_ids=list(args.allowed_finding_ids),
        allowed_knowledge_ids=list(args.allowed_knowledge_ids),
    )
    return _dump(result)


_HANDLERS: dict[str, Callable[..., dict[str, Any] | Awaitable[dict[str, Any]]]] = {
    "resolve_financial_intent": resolve_financial_intent,
    "analyze_financial_text": analyze_financial_text,
    "compare_financial_products": compare_financial_products,
    "calculate_financial_scenario": calculate_financial_scenario,
    "verify_financial_draft": verify_financial_draft,
}


async def invoke_tool_async(
    name: str, arguments: dict[str, Any] | None = None
) -> dict[str, Any]:
    """异步工具入口：供 MCP Host / 已有事件循环调用。"""
    tool = (name or "").strip()
    if tool not in TOOL_WHITELIST:
        raise McpToolError(f"工具不在白名单：{tool}")
    handler = _HANDLERS[tool]
    result = handler(arguments or {})
    if inspect.isawaitable(result):
        return await result
    return result


def invoke_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    """同步桥接：仅在无运行中事件循环时用 asyncio.run；有循环时请用 invoke_tool_async。"""
    tool = (name or "").strip()
    if tool not in TOOL_WHITELIST:
        raise McpToolError(f"工具不在白名单：{tool}")
    handler = _HANDLERS[tool]
    result = handler(arguments or {})
    if not inspect.isawaitable(result):
        return result
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        if inspect.iscoroutine(result):
            return asyncio.run(result)
        async def _await_once() -> dict[str, Any]:
            return await result  # type: ignore[misc]

        return asyncio.run(_await_once())
    raise McpToolError(
        f"工具 {tool} 为 async，当前已有事件循环，请使用 invoke_tool_async"
    )
