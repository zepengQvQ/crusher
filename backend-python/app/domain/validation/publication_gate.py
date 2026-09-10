"""发布门禁：按固定顺序跑确定性校验，不调用大模型。"""
from __future__ import annotations

import logging

from app.domain.llm_errors import LlmInvalidJsonError
from app.domain.llm_explanation_guard import (
    allowed_numbers_from_program,
    validate_draft_reference_whitelist,
)
from app.domain.models.financial_fact import FinancialFact
from app.domain.models.llm import LlmAnalysisDraft
from app.domain.models.report import Finding, KeyParameter
from app.domain.models.verification import VerificationResult
from app.domain.validation.evidence_validator import validate_finding_evidence
from app.domain.validation.number_validator import validate_numbers_and_grades
from app.domain.validation.semantic_validator import validate_semantics
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode

logger = logging.getLogger("crusher")


def run_publication_gate(
    *,
    source_text: str,
    draft: LlmAnalysisDraft,
    plain: str,
    findings: list[Finding],
    key_parameters: list[KeyParameter],
    financial_facts: list[FinancialFact],
    allowed_fact_ids: list[str],
    allowed_finding_ids: list[str],
    allowed_knowledge_ids: list[str],
) -> VerificationResult:
    """固定顺序：schema → 引用 → 证据 → 数值 → 单位/否定条件/覆盖/边界。"""
    issues: list[VerificationIssue] = []

    # 1. Schema（解析后再次确认非空）
    if not draft.all_items():
        issues.append(
            VerificationIssue(
                check=VerificationCheck.schema,
                message="draft empty",
                error_code=ErrorCode.INVALID_MODEL_JSON,
            )
        )

    # 2. 引用白名单
    try:
        validate_draft_reference_whitelist(
            draft,
            allowed_fact_ids=allowed_fact_ids,
            allowed_finding_ids=allowed_finding_ids,
            allowed_knowledge_ids=allowed_knowledge_ids,
        )
    except LlmInvalidJsonError as exc:
        issues.append(
            VerificationIssue(
                check=VerificationCheck.reference,
                message=str(exc),
                error_code=ErrorCode.INVALID_MODEL_JSON,
            )
        )

    # 3. 证据
    issues.extend(validate_finding_evidence(source_text, findings))

    # 4. 数值 / 评级
    issues.extend(
        validate_numbers_and_grades(
            plain,
            findings=findings,
            key_parameters=key_parameters,
            financial_facts=financial_facts,
        )
    )

    # 5–8. 单位 / 否定条件 / 风险覆盖 / 边界（semantic 内含）
    allowed_nums = allowed_numbers_from_program(
        findings=findings, key_parameters=key_parameters
    )
    for fact in financial_facts:
        if fact.normalized_value:
            from app.domain.llm_explanation_guard import extract_number_tokens

            allowed_nums |= extract_number_tokens(fact.normalized_value)
            allowed_nums |= extract_number_tokens(fact.raw_value)

    issues.extend(
        validate_semantics(
            plain,
            draft=draft,
            findings=findings,
            financial_facts=financial_facts,
            allowed_numbers=allowed_nums,
        )
    )

    if not issues:
        return VerificationResult(
            can_publish=True,
            issues=[],
            failed_stage=None,
            error_code=None,
            adapter_note="P2-07 publication gate passed",
            failed_checks=[],
        )

    for issue in issues:
        logger.info(
            "verification_failed check=%s code=%s msg=%s",
            issue.check.value,
            issue.error_code.value,
            issue.message,
        )

    # 优先返回第一个问题的错误码；模型文案关键失败一律不可发布
    primary = issues[0]
    return VerificationResult(
        can_publish=False,
        issues=[i.message for i in issues],
        failed_stage=primary.check.value,
        error_code=primary.error_code,
        adapter_note="P2-07 publication gate rejected model copy",
        failed_checks=[i.check.value for i in issues],
    )
