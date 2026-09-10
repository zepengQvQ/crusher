"""金融数值统一标准化（P2-05）。

所有业务判断使用 Decimal；禁止用 float 比较金额、比例或期限。
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

_AMOUNT_NUM = re.compile(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)")
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*%")
_BP = re.compile(r"(\d+(?:\.\d+)?)\s*(?:bp|BP|基点)")
_MONTHS = re.compile(r"(\d+(?:\.\d+)?)\s*个?月")
_YEARS = re.compile(r"(\d+(?:\.\d+)?)\s*年")
_DAYS = re.compile(r"(\d+(?:\.\d+)?)\s*天")
_RANGE = re.compile(r"[0-9.]+\s*%?\s*[-~～至到]\s*[0-9.]+\s*%?")


def to_decimal(value: object) -> Decimal:
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"无法解析为 Decimal: {value!r}") from exc


def format_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")


def normalize_percent_or_bp(raw: str) -> tuple[Decimal | None, str | None, str | None]:
    """返回 (标准百分比数值, 单位%, 性质)。

    50bp → 0.5% ；3% → 3 。区间返回 (None, None, "range") 并保留原串由调用方处理。
    """
    text = (raw or "").replace(" ", "")
    if not text:
        return None, None, None
    if _RANGE.search(text):
        return None, "%", "range"
    m_bp = _BP.search(text)
    if m_bp:
        bp = to_decimal(m_bp.group(1))
        return bp / Decimal(100), "%", "single"
    m_pct = _PCT.search(text)
    if m_pct:
        return to_decimal(m_pct.group(1)), "%", "single"
    return None, None, None


def normalize_rate_key(raw: str) -> tuple[str | None, str | None]:
    """产品对照用：(nature, normalized_key)。"""
    text = (raw or "").replace(" ", "")
    if _RANGE.search(text):
        return "range", text
    value, _unit, nature = normalize_percent_or_bp(text)
    if value is not None and nature == "single":
        return "single", format_decimal(value)
    if text:
        return "other", text
    return None, None


def normalize_term_months(raw: str) -> Decimal | None:
    """期限统一为月。12个月 与 1 年均可比较为 12。"""
    text = (raw or "").replace(" ", "")
    m = _YEARS.search(text)
    if m:
        return to_decimal(m.group(1)) * Decimal(12)
    m = _MONTHS.search(text)
    if m:
        return to_decimal(m.group(1))
    m = _DAYS.search(text)
    if m:
        return (to_decimal(m.group(1)) / Decimal(30)).quantize(Decimal("0.01"))
    return None


def normalize_term_months_key(raw: str) -> str | None:
    months = normalize_term_months(raw)
    if months is None:
        return None
    return format_decimal(months)


def normalize_amount_yuan(raw: str, amount: Decimal | None = None) -> Decimal | None:
    if amount is not None:
        return amount
    text = (raw or "").replace(",", "").replace("，", "")
    m = re.search(r"(\d+(?:\.\d+)?)\s*万", text)
    if m:
        return to_decimal(m.group(1)) * Decimal(10000)
    m = _AMOUNT_NUM.search(text)
    if m:
        try:
            return to_decimal(m.group(1))
        except ValueError:
            return None
    return None


def normalize_amount_key(raw: str, amount: Decimal | None = None) -> str | None:
    yuan = normalize_amount_yuan(raw, amount)
    if yuan is None:
        return None
    return format_decimal(yuan)
