"""Mock LLM 网关（默认演示模式不发起真实模型请求）。

与真实网关走同一 DTO / parse_llm_explanation_content 路径，避免测试绕过契约。
"""
from __future__ import annotations

import json

from app.domain.models.llm import LlmAnalysisDraft, LlmExplainRequest, draft_from_request
from app.infrastructure.llm.openai_compatible_gateway import parse_llm_explanation_content

_STABLE_TEXT = "（演示）已根据程序规则完成通俗说明，未改写风险结论。"
_DISCLAIMER = "本回复不做投资建议，也不构成适当性判断。"


class MockLlmGateway:
    async def complete(self, request: LlmExplainRequest) -> LlmAnalysisDraft:
        draft = draft_from_request(request, _STABLE_TEXT)
        return parse_llm_explanation_content(
            json.dumps(draft.model_dump(mode="json"), ensure_ascii=False)
        )

    async def chat_text(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
    ) -> str:
        last_user = ""
        prev_user = ""
        for m in messages:
            if m.get("role") == "user":
                prev_user = last_user
                last_user = str(m.get("content") or "")
        parts = ["（演示）已结合当前材料与对话上下文作说明。"]
        blob = f"{system}\n" + "\n".join(str(m.get("content") or "") for m in messages)
        if any(k in last_user for k in ("老年", "适合", "买不买", "能不能买", "推荐")):
            parts.append(
                "材料本身通常不做「是否适合某类人群」的结论；是否购买需以销售机构适当性评估为准。"
            )
        if "区间外" in blob:
            parts.append("材料提到区间外相关表述，请对照原文。")
        elif "收益" in last_user or "风险" in last_user:
            parts.append("请对照材料里关于收益/风险的原文自行核对。")
        if prev_user and prev_user != last_user:
            short = prev_user.strip().replace("\n", " ")
            if len(short) > 24:
                short = short[:24] + "…"
            if "材料原文" not in short:
                parts.append(f"结合你前面提到的「{short}」继续说明。")
        parts.append(_DISCLAIMER)
        return "\n".join(parts)
