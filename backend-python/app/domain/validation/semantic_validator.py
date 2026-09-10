"""语义 / 口径 / 边界校验（确定性，不调用大模型）。"""
from __future__ import annotations

import re

from app.domain.llm_errors import LlmInvalidJsonError
from app.domain.llm_explanation_guard import (
    validate_explanation_against_program,
)
from app.domain.models.enums import FindingSeverity
from app.domain.models.financial_fact import FinancialFact, FinancialFactStatus
from app.domain.models.llm import LlmAnalysisDraft
from app.domain.models.report import Finding
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode

_BOUNDARY_RE = re.compile(
    r"(建议购买|推荐购买|建议选择|更适合你|适合你|绝对安全|保证收益|稳赚|必赚)"
)
_SAFE_NO_FINDING_RE = re.compile(
    r"(产品安全|完全安全|没有风险|无风险|未发现(?:明显|任何)?风险|可以放心)"
)
_MAX_TO_MATURITY_RE = re.compile(r"(到期(?:年化)?收益|保证收益|固定收益)")
_CHARGE_FLIP_RE = re.compile(
    r"(收取|需支付|支付|计收).{0,8}(违约金|手续费)|(违约金|手续费).{0,6}(收取|支付)"
)


def validate_semantics(
    plain: str,
    *,
    draft: LlmAnalysisDraft,
    findings: list[Finding],
    financial_facts: list[FinancialFact],
    allowed_numbers: set[str] | None = None,
) -> list[VerificationIssue]:
    issues: list[VerificationIssue] = []
    text = plain or ""

    # 复用既有否定 / 笼统无风险 / 数值守卫
    try:
        validate_explanation_against_program(
            text, findings=findings, allowed_numbers=allowed_numbers
        )
    except LlmInvalidJsonError as exc:
        issues.append(
            VerificationIssue(
                check=VerificationCheck.negation_condition,
                message=str(exc),
                error_code=ErrorCode.INVALID_MODEL_JSON,
            )
        )

    # 条件不得省略
    for fact in financial_facts:
        if fact.status != FinancialFactStatus.CONFIRMED:
            continue
        cond = (fact.condition_text or "").strip()
        if not cond:
            continue
        # 条件核心词须出现在解释中
        key = cond
        for token in ("满足", "观察", "条件", "后"):
            if token in cond and token not in text:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.negation_condition,
                        message=f"omitted condition from fact {fact.fact_id}: {cond}",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
                break
        else:
            # 至少保留一段条件原文子串
            if len(key) >= 4 and key[:4] not in text and key not in text:
                # 若含「观察条件」则要求出现
                if "观察条件" in cond and "观察条件" not in text:
                    issues.append(
                        VerificationIssue(
                            check=VerificationCheck.negation_condition,
                            message=f"omitted condition from fact {fact.fact_id}",
                            error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                        )
                    )

    # 「最高」不得偷换成到期/保证收益
    for fact in financial_facts:
        if "最高" in fact.qualifiers or "最高" in (fact.raw_value or ""):
            if _MAX_TO_MATURITY_RE.search(text) and "最高" not in text:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.unit,
                        message="qualifier 最高 rewritten as maturity/guaranteed return",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
                break

    # 不收费事实不得写成收费
    for fact in financial_facts:
        if fact.field_key == "prepayment_fee" and fact.polarity.value == "negative":
            if _CHARGE_FLIP_RE.search(text) and not re.search(
                r"不收取|不收|免收|无需支付", text
            ):
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.negation_condition,
                        message="negation flipped: fee became charged",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
                break

    # 边界用语
    if _BOUNDARY_RE.search(text):
        issues.append(
            VerificationIssue(
                check=VerificationCheck.boundary,
                message="boundary phrase forbidden (advice/guarantee/suitability)",
                error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
            )
        )

    # 无 Finding 时不得凭空写产品安全
    if not findings and _SAFE_NO_FINDING_RE.search(text):
        issues.append(
            VerificationIssue(
                check=VerificationCheck.boundary,
                message="claims product safe without program findings",
                error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
            )
        )

    # 高风险 Finding 须被草稿 warning 或正文覆盖
    high = [f for f in findings if f.finding_severity == FindingSeverity.high]
    if high:
        warned_ids = {
            nid
            for item in draft.warning_items
            for nid in item.finding_ids
        }
        covered = set(warned_ids)
        for item in draft.all_items():
            covered.update(item.finding_ids)
        for f in high:
            blob = f.title + f.explanation
            keyword_hit = any(
                tok in text
                for tok in ("违约金", "罚息", "亏损", "风险")
                if tok in blob
            )
            mentioned = f.id in covered or f.title[:4] in text or keyword_hit
            if not mentioned:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.risk_coverage,
                        message=f"high finding not covered in draft: {f.id}",
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )

    return issues
