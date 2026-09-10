"""Mock LLM 网关（默认演示模式不发起真实模型请求）。

与真实网关走同一 DTO / parse_llm_explanation_content 路径，避免测试绕过契约。
"""
from __future__ import annotations

import json

from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest, make_simple_draft
from app.infrastructure.llm.openai_compatible_gateway import parse_llm_explanation_content

_STABLE_TEXT = "（演示）已根据程序规则完成通俗说明，未改写风险结论。"


class MockLlmGateway:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        fact_ids = list(request.allowed_fact_ids[:1])
        finding_ids = list(request.allowed_finding_ids[:1]) if not fact_ids else []
        knowledge_ids = (
            list(request.allowed_knowledge_ids[:1])
            if not fact_ids and not finding_ids
            else []
        )
        draft = make_simple_draft(
            _STABLE_TEXT,
            fact_ids=fact_ids,
            finding_ids=finding_ids,
            knowledge_ids=knowledge_ids,
        )
        return parse_llm_explanation_content(
            json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        )
