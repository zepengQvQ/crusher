"""销售主张抽取与标准化（P1-01，确定性规则，不经大模型）。

Java 对照：无状态 Domain Service。
"""
from __future__ import annotations

import re
from decimal import Decimal
from uuid import uuid4

from app.domain.models.claim_comparison import Claim, EvidenceRef
from app.domain.models.p1_enums import ClaimSubject

_PERCENT = re.compile(
    r"(?P<neg>不|并非|无|免)?[^。；\n]{0,12}?"
    r"(?:年化(?:收益|利率)|预期?收益(?:率)?|收益率|利率)"
    r"[^。；\n]{0,12}?(?P<num>\d+(?:\.\d+)?)\s*%",
)
_FEE_CHARGE = re.compile(
    r"(收取|需支付|支付).{0,12}(?P<num>\d+(?:\.\d+)?)\s*%|"
    r"(?P<num2>\d+(?:\.\d+)?)\s*%.{0,8}(手续费|管理费|服务费)"
)
_FEE_FREE = re.compile(r"(不收|免收|无需支付|没有).{0,8}(手续费|管理费|服务费|费用)|不收费")
_TERM = re.compile(
    r"(?:期限|存期|借款期限)[^。；\n]{0,8}?(?P<n>\d+)\s*(?P<u>个?月|年|天)"
)
_EARLY = re.compile(
    r"(支持|可|允许).{0,6}(提前(支取|赎回|还款))"
    r"|(提前(支取|赎回|还款)).{0,6}(免费|不收)"
)
_EARLY_COST = re.compile(r"提前(支取|赎回|还款).{0,16}(违约金|手续费|费用)")
_PROTECT = re.compile(r"(保本|保证本金)")
_NOT_PROTECT = re.compile(r"(非保本|不保本|不承诺保本|不保证本金)")


def _span_evidence(source_id: str, text: str, start: int, end: int) -> EvidenceRef:
    return EvidenceRef(
        source_id=source_id,
        quote=text[start:end],
        start=start,
        end=end,
        page=None,
        confidence=1.0,
    )


def _norm_term_months(n: int, unit: str) -> Decimal:
    if "年" in unit:
        return Decimal(n) * Decimal(12)
    if "天" in unit:
        # 标准化为月（粗）：30 天≈1 月
        return (Decimal(n) / Decimal(30)).quantize(Decimal("0.01"))
    return Decimal(n)


def extract_sales_claims(source_id: str, text: str) -> list[Claim]:
    """从销售话术抽出可对照主张。"""
    claims: list[Claim] = []

    for m in _PERCENT.finditer(text):
        neg = bool(m.group("neg"))
        num = Decimal(m.group("num"))
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.expected_return,
                summary=f"{'否定' if neg else ''}年化/收益约 {num}%".strip(),
                negated=neg,
                numeric_value=num,
                numeric_unit="percent",
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )

    for m in _FEE_FREE.finditer(text):
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.fee,
                summary="销售称不收费/免收费用",
                negated=True,
                numeric_value=Decimal("0"),
                numeric_unit="percent",
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )
    for m in _FEE_CHARGE.finditer(text):
        raw = m.group("num") or m.group("num2")
        if raw is None:
            continue
        num = Decimal(raw)
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.fee,
                summary=f"销售称收取费用约 {num}%",
                negated=False,
                numeric_value=num,
                numeric_unit="percent",
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )

    for m in _TERM.finditer(text):
        months = _norm_term_months(int(m.group("n")), m.group("u"))
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.term,
                summary=f"销售称期限约 {months} 个月",
                negated=False,
                numeric_value=months,
                numeric_unit="months",
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )

    for m in _EARLY.finditer(text):
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.early_exit,
                summary="销售称可提前退出/支取",
                negated=False,
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )
    for m in _EARLY_COST.finditer(text):
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.early_exit,
                summary="销售提及提前退出需付费",
                negated=False,
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )

    for m in _NOT_PROTECT.finditer(text):
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.principal_protection,
                summary="销售称非保本/不承诺保本",
                negated=True,
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )
    for m in _PROTECT.finditer(text):
        # 跳过已被「非保本」覆盖的 span
        if any(c.subject == ClaimSubject.principal_protection and c.negated for c in claims):
            # 若同句已有非保本，跳过裸「保本」
            window = text[max(0, m.start() - 2) : m.end()]
            if "非保本" in window or "不保本" in window:
                continue
        claims.append(
            Claim(
                claim_id=f"clm_{uuid4().hex[:8]}",
                subject=ClaimSubject.principal_protection,
                summary="销售称保本/保证本金",
                negated=False,
                evidence=_span_evidence(source_id, text, m.start(), m.end()),
            )
        )

    return _dedupe_by_subject(claims)


def _dedupe_by_subject(claims: list[Claim]) -> list[Claim]:
    """同主题保留第一条（销售材料通常一句一个主张）。"""
    seen: set[ClaimSubject] = set()
    out: list[Claim] = []
    for c in claims:
        if c.subject in seen:
            continue
        seen.add(c.subject)
        out.append(c)
    return out
