"""用共享 FinancialFact 账本做双材料字段级对照（P2-RC-02）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.domain.models.claim_comparison import Claim, ClaimComparison, EvidenceRef
from app.domain.models.financial_fact import (
    FinancialFact,
    FinancialFactStatus,
    FactPolarity,
)
from app.domain.models.p1_enums import ClaimStatus, ClaimSubject

_FIELD_SUBJECT: dict[str, ClaimSubject] = {
    "expected_return": ClaimSubject.expected_return,
    "annual_interest_rate": ClaimSubject.expected_return,
    "management_fee": ClaimSubject.fee,
    "prepayment_fee": ClaimSubject.fee,
    "term": ClaimSubject.term,
    "early_redemption": ClaimSubject.early_exit,
    "principal_protection": ClaimSubject.principal_protection,
}

_UNIT: dict[str, str] = {
    "expected_return": "percent",
    "annual_interest_rate": "percent",
    "management_fee": "percent",
    "term": "months",
    "amount": "yuan",
}


def _ev_from_fact(fact: FinancialFact, source_id: str) -> EvidenceRef | None:
    if not fact.evidence_refs:
        return None
    ref = fact.evidence_refs[0]
    return EvidenceRef(
        source_id=source_id,
        quote=ref.quote,
        start=ref.start,
        end=ref.end,
        confidence=1.0,
    )


def _claim_from_fact(fact: FinancialFact, source_id: str, subject: ClaimSubject) -> Claim | None:
    ev = _ev_from_fact(fact, source_id)
    if ev is None:
        return None
    numeric: Decimal | None = None
    unit = _UNIT.get(fact.field_key)
    if fact.normalized_value and "区间" not in fact.qualifiers:
        try:
            numeric = Decimal(fact.normalized_value)
        except (InvalidOperation, ValueError):
            numeric = None
    return Claim(
        claim_id=f"clm_{fact.fact_id[-8:]}",
        subject=subject,
        summary=f"{subject.value}: {fact.raw_value}",
        negated=fact.polarity == FactPolarity.negative,
        numeric_value=numeric,
        numeric_unit=unit,  # type: ignore[arg-type]
        evidence=ev,
    )


def _values_equal(a: FinancialFact, b: FinancialFact) -> bool | None:
    """True/False 可判定；None 表示无法数值比较。"""
    if a.polarity != b.polarity:
        return False
    if "区间" in a.qualifiers or "区间" in b.qualifiers:
        return (a.normalized_value or a.raw_value) == (b.normalized_value or b.raw_value)
    if a.normalized_value and b.normalized_value:
        try:
            return Decimal(a.normalized_value) == Decimal(b.normalized_value)
        except (InvalidOperation, ValueError):
            pass
    if a.raw_value.strip() == b.raw_value.strip():
        return True
    return None


def compare_ledgers(
    *,
    sales_facts: list[FinancialFact],
    official_facts: list[FinancialFact],
    sales_source_id: str,
    official_source_id: str,
) -> list[ClaimComparison]:
    """按 field_key 对齐两侧确认事实，生成对照卡。"""
    official_by_field: dict[str, list[FinancialFact]] = {}
    for fact in official_facts:
        if fact.status != FinancialFactStatus.CONFIRMED:
            continue
        official_by_field.setdefault(fact.field_key, []).append(fact)

    out: list[ClaimComparison] = []
    seen_subjects: set[ClaimSubject] = set()
    for sales in sales_facts:
        if sales.status != FinancialFactStatus.CONFIRMED:
            continue
        subject = _FIELD_SUBJECT.get(sales.field_key)
        if subject is None:
            continue
        claim = _claim_from_fact(sales, sales_source_id, subject)
        if claim is None:
            continue
        peers = official_by_field.get(sales.field_key, [])
        if not peers:
            out.append(
                ClaimComparison(
                    comparison_id=f"cmp_{uuid4().hex[:10]}",
                    subject=subject,
                    status=ClaimStatus.not_found,
                    summary=f"正式材料未找到与「{sales.raw_value}」对应的表述",
                    sales_claim=claim,
                    official_evidence=None,
                    suggested_follow_up="请向机构索取正式材料中的对应条款",
                )
            )
            seen_subjects.add(subject)
            continue
        official = peers[0]
        off_ev = _ev_from_fact(official, official_source_id)
        if official.condition_text or sales.condition_text:
            out.append(
                ClaimComparison(
                    comparison_id=f"cmp_{uuid4().hex[:10]}",
                    subject=subject,
                    status=ClaimStatus.conditional,
                    summary=(
                        f"正式材料对「{sales.raw_value}」附加条件："
                        f"{official.condition_text or sales.condition_text}"
                    ),
                    sales_claim=claim,
                    official_evidence=off_ev,
                    suggested_follow_up="请确认触发条件是否适用于你的情形",
                )
            )
            seen_subjects.add(subject)
            continue
        equal = _values_equal(sales, official)
        if equal is True:
            status = ClaimStatus.confirmed
            summary = f"两侧关于「{subject.value}」表述一致"
            follow = ""
        elif equal is False:
            status = ClaimStatus.conflict
            summary = (
                f"销售「{sales.raw_value}」与正式材料「{official.raw_value}」不一致"
            )
            follow = "请以正式材料为准并要求销售解释差异"
        else:
            status = ClaimStatus.uncertain
            summary = f"无法可靠比较「{sales.raw_value}」与「{official.raw_value}」"
            follow = "请提供更明确的正式条款"
        out.append(
            ClaimComparison(
                comparison_id=f"cmp_{uuid4().hex[:10]}",
                subject=subject,
                status=status,
                summary=summary,
                sales_claim=claim,
                official_evidence=off_ev,
                suggested_follow_up=follow,
            )
        )
        seen_subjects.add(subject)
    return out


def merge_comparisons(
    ledger_comps: list[ClaimComparison],
    claim_comps: list[ClaimComparison],
) -> list[ClaimComparison]:
    """账本对照优先；主张路径仅补账本未覆盖的 subject。"""
    covered = {c.subject for c in ledger_comps}
    merged = list(ledger_comps)
    for c in claim_comps:
        if c.subject in covered:
            continue
        merged.append(c)
        covered.add(c.subject)
    return merged
