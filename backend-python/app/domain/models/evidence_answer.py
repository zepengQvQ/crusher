"""P1-03：基于证据的追问响应。"""
from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import Field, field_validator

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.report import StrictModel
from app.domain.models.verification import PublicationDecision


class AnswerStatus(str, Enum):
    answered = "answered"
    insufficient_evidence = "insufficient_evidence"
    out_of_scope = "out_of_scope"
    contextual = "contextual"


class ChatTurn(StrictModel):
    """追问可选附带的最近对话轮次。"""

    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=1000)

    @field_validator("content", mode="before")
    @classmethod
    def _strip_content(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class FollowUpRequest(StrictModel):
    question: str = Field(..., min_length=1, max_length=500)
    source_text: str = Field(..., min_length=1, max_length=8000)
    pending_questions: list[str] = Field(default_factory=list)
    report_digest: str = Field(default="", max_length=2000)
    recent_messages: list[ChatTurn] = Field(default_factory=list, max_length=8)

    @field_validator("report_digest", mode="before")
    @classmethod
    def _strip_digest(cls, value: object) -> object:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return value


class EvidenceAnswer(StrictModel):
    question: str
    status: AnswerStatus
    answer: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
    publication: PublicationDecision | None = Field(
        default=None,
        description="发布决策（由 PublicationService 写入）",
    )
