"""P1-03：基于证据的追问响应。"""
from __future__ import annotations

from enum import Enum

from pydantic import Field

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.report import StrictModel


class AnswerStatus(str, Enum):
    answered = "answered"
    insufficient_evidence = "insufficient_evidence"
    out_of_scope = "out_of_scope"


class FollowUpRequest(StrictModel):
    question: str = Field(..., min_length=1, max_length=500)
    source_text: str = Field(..., min_length=1, max_length=8000)
    pending_questions: list[str] = Field(default_factory=list)


class EvidenceAnswer(StrictModel):
    question: str
    status: AnswerStatus
    answer: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)
