"""数值 / 评级校验：禁止模型引入程序未确认的数字与评级。"""
from __future__ import annotations

import re

from app.domain.llm_explanation_guard import (
    allowed_numbers_from_program,
    extract_number_tokens,
)
from app.domain.models.financial_fact import FinancialFact
from app.domain.models.report import Finding, KeyParameter
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode

_GRADE_RE = re.compile(r"\bR[1-5]\b", re.IGNORECASE)
_BAOBEN_RE = re.compile(r"(?<![非不未])保本(?!浮动)")


def validate_numbers_and_grades(
    plain: str,
    *,
    findings: list[Finding],
    key_parameters: list[KeyParameter],
    financial_facts: list[FinancialFact] | None = None,
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    allowed = allowed_numbers_from_program(
        findings=findings, key_parameters=key_parameters
    )
    for fact in financial_facts or []:
        if fact.normalized_value:
            allowed |= extract_number_tokens(fact.normalized_value)
        if fact.raw_value:
            allowed |= extract_number_tokens(fact.raw_value)

    novel = extract_number_tokens(plain) - allowed
    if novel:
        issues.append(
            VerificationIssue(
                check=VerificationCheck.number,
                message=f"explanation invents numbers: {sorted(novel)}",
                error_code=ErrorCode.INVALID_MODEL_JSON,
            )
        )

    allowed_grades: set[str] = set()
    blob = " ".join(
        [
            *(p.value or "" for p in key_parameters),
            *(f.title + f.explanation for f in findings),
            *(ff.raw_value for ff in (financial_facts or [])),
        ]
    )
    for m in _GRADE_RE.finditer(blob):
        allowed_grades.add(m.group(0).upper())

    for m in _GRADE_RE.finditer(plain or ""):
        grade = m.group(0).upper()
        if grade not in allowed_grades:
            issues.append(
                VerificationIssue(
                    check=VerificationCheck.number,
                    message=f"explanation invents risk grade: {grade}",
                    error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                )
            )
            break

    program_has_baoben = "保本" in blob and "非保本" not in blob and "不保本" not in blob
    if _BAOBEN_RE.search(plain or "") and not program_has_baoben:
        # 程序未确认保本时，模型不得写成保本
        if not any("保本" in (p.value or "") for p in key_parameters):
            if "非保本" not in (plain or "") and "不保本" not in (plain or ""):
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.number,
                        message="explanation invents principal protection 保本",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
    return issues
