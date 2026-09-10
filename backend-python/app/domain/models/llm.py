"""领域侧 LLM 请求/响应 DTO（给 LlmGateway Protocol 用）。

P2-06：模型只能输出 LlmAnalysisDraft（逐项通俗化），不得生成 Finding / 风险级别 / 计算结果。
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class LlmDraftItem(BaseModel):
    """单条可检查的通俗解释项。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    item_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    fact_ids: list[str] = Field(default_factory=list)
    finding_ids: list[str] = Field(default_factory=list)
    knowledge_ids: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("text 不能为空")
        return text

    @model_validator(mode="after")
    def _need_reference(self) -> LlmDraftItem:
        if not (self.fact_ids or self.finding_ids or self.knowledge_ids):
            raise ValueError("每条解释至少引用一个 fact_ids / finding_ids / knowledge_ids")
        return self


class LlmAnalysisDraft(BaseModel):
    """模型结构化草稿：只能改写已确认事实，不能补充推测。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    overview_items: list[LlmDraftItem] = Field(default_factory=list)
    warning_items: list[LlmDraftItem] = Field(default_factory=list)
    unknown_items: list[LlmDraftItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _not_empty(self) -> LlmAnalysisDraft:
        if not (self.overview_items or self.warning_items or self.unknown_items):
            raise ValueError("草稿不能为空")
        return self

    def all_items(self) -> list[LlmDraftItem]:
        return list(self.overview_items) + list(self.warning_items) + list(self.unknown_items)

    def render_plain_language(self) -> str:
        """拼成报告用白话（H5 仍读 plain_language.text）。"""
        return "\n".join(item.text for item in self.all_items())


# 兼容旧名：网关/协议统一产出草稿
LlmExplanation = LlmAnalysisDraft


class LlmExplainRequest(BaseModel):
    """Application 组装、Gateway 只负责传输的解释请求。

    system/user 已分离；Gateway 不得再拼接或静默截断原文。
    白名单 ID 供解析后校验与 Mock 构造合法引用。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
    allowed_fact_ids: list[str] = Field(default_factory=list)
    allowed_finding_ids: list[str] = Field(default_factory=list)
    allowed_knowledge_ids: list[str] = Field(default_factory=list)


def make_simple_draft(
    text: str,
    *,
    fact_ids: list[str] | None = None,
    finding_ids: list[str] | None = None,
    knowledge_ids: list[str] | None = None,
    item_id: str = "overview_1",
) -> LlmAnalysisDraft:
    """测试与 Mock 用的最小合法草稿。"""
    fids = list(fact_ids or [])
    nids = list(finding_ids or [])
    kids = list(knowledge_ids or [])
    if not (fids or nids or kids):
        kids = ["knowledge:demo"]
    return LlmAnalysisDraft(
        overview_items=[
            LlmDraftItem(
                item_id=item_id,
                text=text,
                fact_ids=fids,
                finding_ids=nids,
                knowledge_ids=kids,
            )
        ]
    )
