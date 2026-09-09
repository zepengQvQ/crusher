"""Mock LLM 网关（默认演示模式不发起真实模型请求）。"""
from __future__ import annotations

from app.domain.models.llm import LlmExplainRequest, LlmExplanation

_STABLE_TEXT = "（演示）已根据程序规则完成通俗说明，未改写风险结论。"


class MockLlmGateway:
    async def complete(self, request: LlmExplainRequest) -> LlmExplanation:
        # 忽略 request 内容，保证断网演示输出稳定；不发起网络请求。
        _ = request
        return LlmExplanation(plain_language=_STABLE_TEXT)
