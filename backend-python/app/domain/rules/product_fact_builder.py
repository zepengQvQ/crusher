"""从单份材料组装 ProductFacts 侧字段，并做等值规范化。"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.domain.models.claim_comparison import EvidenceRef
from app.domain.models.enums import FactStatus, ParameterKey, ProductHint, ProductTypeId
from app.domain.models.p1_enums import FieldStatus
from app.domain.models.product_facts import FactSideValue, ProductFacts
from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.engine import RuleEngine
from app.domain.rules.fact_extractor import FactExtractor

_LOAN_MARKERS = ("贷款", "消费贷", "借款", "等额本息", "年化利率")
_DEPOSIT_MARKERS = ("结构性存款", "结构存款", "观察区间", "挂钩型存款")
_RANGE_RE = re.compile(r"[0-9.]+\s*%?\s*[-~～至到]\s*[0-9.]+\s*%?")
_MONTHS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*个?月")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*年")
_DAYS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*天")
_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*%")


def resolve_product_type(text: str, hint: ProductHint) -> ProductTypeId | None:
    if hint == ProductHint.loan:
        return ProductTypeId.loan
    if hint == ProductHint.structured_deposit:
        return ProductTypeId.structured_deposit
    loan = any(m in text for m in _LOAN_MARKERS)
    deposit = any(m in text for m in _DEPOSIT_MARKERS)
    if loan and not deposit:
        return ProductTypeId.loan
    if deposit and not loan:
        return ProductTypeId.structured_deposit
    if loan and deposit:
        return None
    return None


def build_side_facts(
    *,
    text: str,
    label: str,
    hint: ProductHint,
    knowledge: KnowledgeRepository,
) -> tuple[ProductFacts, dict[str, FactSideValue]]:
    """返回产品元信息与维度值映射。"""
    product_id = f"prod_{uuid4().hex[:10]}"
    product_type = resolve_product_type(text, hint)
    extractor = FactExtractor(knowledge)
    extracted = extractor.extract(
        text,
        product_type_id=product_type.value if product_type else None,
    )
    rules = RuleEngine(knowledge)
    risks = []
    if product_type is not None:
        risks = rules.match_risks(text, product_type=product_type.value)

    fields: dict[str, FactSideValue] = {}
    fields["product_type"] = FactSideValue(
        display=_type_label(product_type),
        normalized=product_type.value if product_type else None,
        status=FieldStatus.confirmed if product_type else FieldStatus.uncertain,
        evidence=_find_type_evidence(product_id, text, product_type),
    )

    param_map = {p.key: p for p in extracted.key_parameters}

    fields["term"] = _from_param(
        product_id, text, param_map.get(ParameterKey.term), normalize="term"
    )
    fields["amount"] = _from_param(
        product_id, text, param_map.get(ParameterKey.amount), normalize="amount"
    )
    if product_type == ProductTypeId.loan:
        rate_param = param_map.get(ParameterKey.annual_interest_rate)
    else:
        rate_param = param_map.get(ParameterKey.expected_return)
    fields["return_or_rate"] = _from_param(
        product_id, text, rate_param, normalize="rate"
    )
    early_key = (
        ParameterKey.prepayment_fee
        if product_type == ProductTypeId.loan
        else ParameterKey.early_redemption
    )
    fields["early_exit"] = _from_param(product_id, text, param_map.get(early_key))
    fee_param = param_map.get(ParameterKey.fee_structure) or param_map.get(
        ParameterKey.prepayment_fee
    )
    fields["fees"] = _from_param(product_id, text, fee_param)
    fields["principal_protection"] = _from_param(
        product_id, text, param_map.get(ParameterKey.principal_protection)
    )

    if risks:
        titles = "；".join(r.name for r in risks[:5])
        evs: list[EvidenceRef] = []
        for r in risks[:3]:
            quote = (r.quote or "").strip()
            if not quote:
                continue
            start = r.start if r.start >= 0 else text.find(quote)
            end = r.end if r.end > start else start + len(quote)
            if start < 0:
                continue
            evs.append(
                EvidenceRef(
                    source_id=product_id,
                    quote=text[start:end] if end <= len(text) else quote,
                    start=start,
                    end=min(end, len(text)),
                )
            )
        fields["main_risks"] = FactSideValue(
            display=titles,
            normalized=titles,
            status=FieldStatus.confirmed,
            evidence=evs,
        )
    else:
        fields["main_risks"] = FactSideValue(status=FieldStatus.missing, display=None)

    missing_q = [m.question for m in extracted.missing_disclosures]
    if missing_q:
        fields["undisclosed"] = FactSideValue(
            display="；".join(missing_q[:6]),
            normalized="|".join(sorted(missing_q)),
            status=FieldStatus.confirmed,
        )
    else:
        fields["undisclosed"] = FactSideValue(
            display="（当前抽取字段均有材料表述）",
            normalized="none",
            status=FieldStatus.confirmed,
        )

    meta = ProductFacts(
        product_id=product_id,
        label=label,
        product_type=product_type,
        source_text=text,
    )
    return meta, fields


def compare_side_values(a: FactSideValue, b: FactSideValue) -> tuple[str, str]:
    """返回 (DiffStatus.value, note)。"""
    from app.domain.models.p1_enums import DiffStatus

    a_miss = a.status == FieldStatus.missing or not (a.display or "").strip()
    b_miss = b.status == FieldStatus.missing or not (b.display or "").strip()
    if a_miss and b_miss:
        return DiffStatus.both_missing.value, "两侧材料均未说明"
    if a_miss:
        return DiffStatus.missing_a.value, "产品 A 材料未说明"
    if b_miss:
        return DiffStatus.missing_b.value, "产品 B 材料未说明"
    if a.nature and b.nature and a.nature != b.nature:
        return DiffStatus.incomparable.value, "收益/利率口径不同，不可直接比较"
    if a.normalized and b.normalized and a.normalized == b.normalized:
        return DiffStatus.same.value, "标准化后一致"
    if (a.display or "").strip() == (b.display or "").strip():
        return DiffStatus.same.value, "表述一致"
    return DiffStatus.different.value, "两侧表述不同"


def _type_label(t: ProductTypeId | None) -> str | None:
    if t == ProductTypeId.loan:
        return "贷款"
    if t == ProductTypeId.structured_deposit:
        return "结构性存款"
    return None


def _find_type_evidence(
    product_id: str, text: str, product_type: ProductTypeId | None
) -> list[EvidenceRef]:
    if product_type is None:
        return []
    markers = _LOAN_MARKERS if product_type == ProductTypeId.loan else _DEPOSIT_MARKERS
    for m in markers:
        idx = text.find(m)
        if idx >= 0:
            return [
                EvidenceRef(
                    source_id=product_id,
                    quote=m,
                    start=idx,
                    end=idx + len(m),
                )
            ]
    return []


def _from_param(
    product_id: str,
    text: str,
    param: object | None,
    *,
    normalize: str | None = None,
) -> FactSideValue:
    if param is None or getattr(param, "status", None) == FactStatus.not_disclosed:
        return FactSideValue(status=FieldStatus.missing)
    value = getattr(param, "value", None)
    amount = getattr(param, "amount", None)
    display = format(amount, "f") if amount is not None else (str(value).strip() if value else None)
    if not display:
        return FactSideValue(status=FieldStatus.missing)
    nature = None
    normalized = display
    if normalize == "term":
        normalized = normalize_term_months(display) or display
    elif normalize == "amount":
        normalized = normalize_amount(display, amount) or display
    elif normalize == "rate":
        nature, normalized = normalize_rate(display)
    evidence = _quote_evidence(product_id, text, display)
    return FactSideValue(
        display=display,
        normalized=normalized,
        status=FieldStatus.confirmed,
        evidence=evidence,
        nature=nature,
    )


def normalize_term_months(raw: str) -> str | None:
    text = raw.replace(" ", "")
    m = _YEARS_RE.search(text)
    if m:
        months = Decimal(m.group(1)) * Decimal(12)
        return format(months.normalize(), "f")
    m = _MONTHS_RE.search(text)
    if m:
        return format(Decimal(m.group(1)).normalize(), "f")
    m = _DAYS_RE.search(text)
    if m:
        months = (Decimal(m.group(1)) / Decimal(30)).quantize(Decimal("0.01"))
        return format(months.normalize(), "f")
    return None


def normalize_amount(raw: str, amount: Decimal | None) -> str | None:
    if amount is not None:
        return format(amount.normalize(), "f")
    text = raw.replace(",", "").replace("，", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
    if m:
        return format((Decimal(m.group(1)) * Decimal(10000)).normalize(), "f")
    m = re.search(r"(\d+(?:\.\d+)?)", text)
    if m:
        try:
            return format(Decimal(m.group(1)).normalize(), "f")
        except InvalidOperation:
            return None
    return None


def normalize_rate(raw: str) -> tuple[str | None, str | None]:
    text = raw.replace(" ", "")
    if _RANGE_RE.search(text):
        # 区间不取上限，整段作为规范化键
        return "range", text
    m = _PCT_RE.search(text)
    if m:
        return "single", format(Decimal(m.group(1)).normalize(), "f")
    return "other", text


def _quote_evidence(product_id: str, text: str, needle: str) -> list[EvidenceRef]:
    snippet = needle[:40]
    idx = text.find(snippet)
    if idx < 0:
        # 尝试找百分比片段
        m = _PCT_RE.search(needle)
        if m:
            idx = text.find(m.group(0))
            snippet = m.group(0)
    if idx < 0:
        return []
    end = idx + len(snippet)
    return [
        EvidenceRef(
            source_id=product_id,
            quote=text[idx:end],
            start=idx,
            end=end,
        )
    ]
