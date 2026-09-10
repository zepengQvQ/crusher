"""发布前校验问题条目（P2-07）。"""
from __future__ import annotations

from enum import Enum

from pydantic import Field

from app.domain.models.report import StrictModel
from app.shared.enums import ErrorCode


class VerificationCheck(str, Enum):
    schema = "schema"
    reference = "reference"
    evidence = "evidence"
    number = "number"
    unit = "unit"
    negation_condition = "negation_condition"
    risk_coverage = "risk_coverage"
    boundary = "boundary"


class VerificationIssue(StrictModel):
    check: VerificationCheck
    message: str = Field(..., min_length=1)
    error_code: ErrorCode
