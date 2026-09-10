"""证据校验：Finding.quote 必须与原文位置精确一致。"""
from __future__ import annotations

from app.domain.models.report import Finding
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode


def validate_finding_evidence(
    source_text: str,
    findings: list[Finding],
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    text = source_text or ""
    for finding in findings:
        for i, ev in enumerate(finding.evidence):
            if ev.end > len(text) or ev.start < 0 or ev.end < ev.start:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.evidence,
                        message=f"finding {finding.id} evidence[{i}] span 越界",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
                continue
            actual = text[ev.start : ev.end]
            if actual != ev.quote:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.evidence,
                        message=(
                            f"finding {finding.id} evidence[{i}] quote 与原文不一致"
                        ),
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
    return issues
