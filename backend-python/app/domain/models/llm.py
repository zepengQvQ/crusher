"""领域侧 LLM 返回 DTO（给 LlmGateway Protocol 用）。"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LlmExplanation(BaseModel):
    """模型通俗解释的唯一允许结构。"""

    plain_language: str = Field(min_length=1)

    @field_validator("plain_language")
    @classmethod
    def _strip_non_empty(cls, value: str) -> str:
        text = value.strip()
        if not text:
            raise ValueError("plain_language 不能为空")
        return text
