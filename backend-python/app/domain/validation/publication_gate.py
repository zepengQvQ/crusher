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
from app.domain.models.verification import (
    AnalysisCoverage,
    PublicationDecision,
    PublicationOutcome,
    VerificationResult,
)
from app.domain.validation.evidence_validator import validate_finding_evidence
from app.domain.validation.number_validator import validate_numbers_and_grades
from app.domain.validation.semantic_validator import validate_semantics
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode, user_message_for

logger = logging.getLogger("crusher")

_DEFAULT_CHECKED = [
    "产品类型识别（程序规则）",
    "关键参数抽取（程序规则）",
    "风险模式匹配（程序规则）",
    "证据位置校验",
    "模型解释引用与数值门禁",
]
_DEFAULT_NOT_CHECKED = [
    "用户适当性评估",
    "完整合同法律效力",
    "市场行情与未来收益预测",
    "未配置规则覆盖的风险",
]


def _coverage(
    *,
    checked: list[str] | None = None,
    not_checked: list[str] | None = None,
) -> AnalysisCoverage:
    return AnalysisCoverage(
        checked=list(_DEFAULT_CHECKED if checked is None else checked),
        not_checked=list(_DEFAULT_NOT_CHECKED if not_checked is None else not_checked),
    )


def decide_publish(*, user_reason: str = "分析完成，关键门禁已通过") -> PublicationDecision:
    return PublicationDecision(
        outcome=PublicationOutcome.publish,
        reason_code=None,
        user_reason=user_reason,
        next_steps=["可查看风险证据与关键参数", "如有识别错误可返回首页重新分析"],
        coverage=_coverage(),
    )


def decide_publish_partial(
    *,
    reason_code: ErrorCode,
    user_reason: str | None = None,
    next_steps: list[str] | None = None,
    checked: list[str] | None = None,
    not_checked: list[str] | None = None,
) -> PublicationDecision:
    return PublicationDecision(
        outcome=PublicationOutcome.publish_partial,
        reason_code=reason_code,
        user_reason=user_reason or user_message_for(reason_code),
        next_steps=next_steps
        or [
            "请查看下方已确认的程序事实与风险",
            "通俗解释未通过校验，请勿当作模型已完整说明",
            "可修改输入后重新分析",
        ],
        coverage=_coverage(
            checked=[
                "产品类型识别（程序规则）",
                "关键参数抽取（程序规则）",
                "风险模式匹配（程序规则）",
                "证据位置校验",
            ]
            if checked is None
            else checked,
            not_checked=[
                "模型通俗解释（未通过校验）",
                "用户适当性评估",
                "完整合同法律效力",
                "未配置规则覆盖的风险",
            ]
            if not_checked is None
            else not_checked,
        ),
    )


def decide_clarify(
    *,
    reason_code: ErrorCode,
    user_reason: str,
    next_steps: list[str] | None = None,
) -> PublicationDecision:
    return PublicationDecision(
        outcome=PublicationOutcome.clarify,
        reason_code=reason_code,
        user_reason=user_reason,
        next_steps=next_steps
        or ["请回答页面上的追问后继续", "或返回首页重新粘贴材料"],
        coverage=_coverage(
            checked=["输入完整性检查"],
            not_checked=[
                "完整风险分析（待补充信息）",
                "模型通俗解释",
                "用户适当性评估",
            ],
        ),
    )


def decide_refuse(
    *,
    reason_code: ErrorCode,
    user_reason: str | None = None,
    next_steps: list[str] | None = None,
) -> PublicationDecision:
    return PublicationDecision(
        outcome=PublicationOutcome.refuse,
        reason_code=reason_code,
        user_reason=user_reason or user_message_for(reason_code),
        next_steps=next_steps
        or ["可返回首页修改材料后重试", "失败不等于产品安全或无风险"],
        coverage=_coverage(
            checked=[],
            not_checked=[
                "完整风险结论（本次已拒绝发布）",
                "模型通俗解释",
                "用户适当性评估",
            ],
        ),
    )


def decide_from_verification(verification: VerificationResult) -> PublicationDecision:
    """校验失败：阻止模型文案，允许部分发布程序事实。"""
    code = verification.error_code or ErrorCode.OUTPUT_VERIFICATION_FAILED
    if code == ErrorCode.INVALID_MODEL_JSON:
        code = ErrorCode.MODEL_OUTPUT_INVALID
    detail = "; ".join(verification.issues[:3]) if verification.issues else ""
    reason = user_message_for(code)
    if detail:
        reason = f"{reason}（{detail}）"
    return decide_publish_partial(reason_code=code, user_reason=reason)


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
