"""Mock LLM 网关（默认演示模式不发起真实模型请求）。

与真实网关走同一 DTO / parse_llm_explanation_content 路径，避免测试绕过契约。
"""
from __future__ import annotations

import json

from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest, draft_from_request
from app.infrastructure.llm.openai_compatible_gateway import parse_llm_explanation_content

_STABLE_TEXT = "（演示）已根据程序规则完成通俗说明，未改写风险结论。"


class MockLlmGateway:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        draft = draft_from_request(request, _STABLE_TEXT)
        return parse_llm_explanation_content(
            json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        )
