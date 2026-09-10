"""
用途：校验 FinancialFact 证据是否与原文精确一致。
Java 对照：Validator。
输入：原文 + 事实列表。
输出：VerificationIssue 列表（空表示通过）。
业务不变量：CONFIRMED 事实必须有合法 quote/span；失败不得进入允许数值集合。
失败方式：返回 issues，由发布门禁降级为 PUBLISH_PARTIAL/REFUSE。
"""
from __future__ import annotations

from app.domain.models.financial_fact import FinancialFact, FinancialFactStatus
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


def validate_financial_fact_evidence(
    source_text: str,
    financial_facts: list[FinancialFact],
) -> list[VerificationIssue]:
    """CONFIRMED 事实必须有精确落在原文上的证据。"""
    issues: list[VerificationIssue] = []
    text = source_text or ""
    for fact in financial_facts:
        if fact.status != FinancialFactStatus.CONFIRMED:
            continue
        if not fact.evidence_refs:
            issues.append(
                VerificationIssue(
                    check=VerificationCheck.evidence,
                    message=f"fact {fact.fact_id} CONFIRMED 但无证据",
                    error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                )
            )
            continue
        for i, ev in enumerate(fact.evidence_refs):
            if not (0 <= ev.start < ev.end <= len(text)):
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.evidence,
                        message=f"fact {fact.fact_id} evidence[{i}] span 越界",
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
                            f"fact {fact.fact_id} evidence[{i}] quote 与原文不一致"
                        ),
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
    return issues
