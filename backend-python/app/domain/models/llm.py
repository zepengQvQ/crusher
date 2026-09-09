"""领域侧 LLM 请求/响应 DTO（给 LlmGateway Protocol 用）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LlmExplanation(BaseModel):
    """模型通俗解释的唯一允许结构。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    plain_language: str = Field(min_length=1)

    @field_validator("plain_language")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("plain_language 不能为空")
        return text


class LlmExplainRequest(BaseModel):
    """Application 组装、Gateway 只负责传输的解释请求。

    system/user 已分离；Gateway 不得再拼接或静默截断原文。
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    system_prompt: str = Field(min_length=1)
    user_prompt: str = Field(min_length=1)
