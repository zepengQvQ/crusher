"""模型通俗解释与程序结论的一致性校验（P0-RC-10）。

Gateway 只负责传输；Application 在拿到 LlmExplanation 后调用本模块。
非法或与 Finding 冲突时抛出 LlmInvalidJsonError，任务失败且 report=None。
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from app.domain.llm_errors import LlmInvalidJsonError
from app.domain.models.report import Finding, KeyParameter

# 笼统「无风险」；双重否定前缀保护「不能说没有风险」类表述
_BLANKET_NO_RISK = re.compile(
    r"(未发现(?:明显|任何)?风险|没有风险|无风险|不存在风险|可以放心(?:办理|提前还款)?)"
)
_DOUBLE_NEG_PREFIX = re.compile(
    r"(不能说|并非|不是说|别以为|不要以为|并不等于|不等于).{0,16}$"
)

# 按 Finding.id（规则 pattern_id）检查是否明确否定该风险事实
_FINDING_DENIALS: dict[str, re.Pattern[str]] = {
    "prepayment_penalty": re.compile(
        r"(不会产生|不产生|不收取|无需支付|免收|没有|无).{0,8}违约金"
        r"|违约金.{0,6}(不会|不产生|不收取|免收)"
    ),
    "high_penalty_interest": re.compile(
        r"(不会|不|无需|免).{0,8}(罚息|高额罚息)|(罚息|高额罚息).{0,6}(不收|免收|没有)"
    ),
    "low_floor_return": re.compile(
        r"(不会|并非|不是).{0,12}(低档|较低).{0,4}(收益|回报)"
    ),
}

_NUMBER_TOKEN = re.compile(
    r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?!\d)"
)


def _norm_number(whole: str, frac: str | None) -> str:
    raw = whole.replace(",", "")
    if frac:
        raw = f"{raw}.{frac}"
    try:
        return format(Decimal(raw).normalize(), "f")
    except InvalidOperation:
        return raw


def extract_number_tokens(text: str) -> set[str]:
    """抽取文本中的数值词元（去千分位、规范化）。"""
    out: set[str] = set()
    for m in _NUMBER_TOKEN.finditer(text or ""):
        out.add(_norm_number(m.group(1), m.group(2)))
    return out


def allowed_numbers_from_program(
    *,
    findings: list[Finding],
    key_parameters: list[KeyParameter] | None = None,
) -> set[str]:
    """程序已确定事实中的允许数值：Finding/Evidence/参数。"""
    allowed: set[str] = set()
    for f in findings:
        allowed |= extract_number_tokens(f.title)
        allowed |= extract_number_tokens(f.explanation)
        for ev in f.evidence:
            allowed |= extract_number_tokens(ev.quote)
    for p in key_parameters or []:
        if p.value:
            allowed |= extract_number_tokens(p.value)
        if p.amount is not None:
            allowed.add(format(Decimal(p.amount).normalize(), "f"))
    return allowed


def _blanket_unprotected(plain: str) -> bool:
    for m in _BLANKET_NO_RISK.finditer(plain):
        prefix = plain[: m.start()]
        if _DOUBLE_NEG_PREFIX.search(prefix):
            continue
        return True
    return False


def validate_explanation_against_program(
    plain_language: str,
    *,
    findings: list[Finding],
    allowed_numbers: set[str] | None = None,
) -> None:
    """与程序 Finding/数值冲突则抛 LlmInvalidJsonError。"""
    plain = (plain_language or "").strip()
    if not plain:
        raise LlmInvalidJsonError("empty plain_language")

    if findings:
        if _blanket_unprotected(plain):
            raise LlmInvalidJsonError("explanation contradicts findings (blanket no-risk)")
        for f in findings:
            pattern = _FINDING_DENIALS.get(f.id) or _FINDING_DENIALS.get(
                f.rule_or_knowledge_id
            )
            if pattern is not None and pattern.search(plain):
                raise LlmInvalidJsonError(f"explanation denies finding {f.id}")

    allowed = allowed_numbers
    if allowed is None:
        allowed = allowed_numbers_from_program(findings=findings)

    if findings or allowed:
        novel = extract_number_tokens(plain) - allowed
        if novel:
            raise LlmInvalidJsonError(f"explanation invents numbers: {sorted(novel)}")
