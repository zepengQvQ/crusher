"""简单收益：本金 × 年化比例 × 天数 ÷ 计息基数。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.models.calculation import (
    CalculationResult,
    parse_decimal_input,
    parse_percent_input,
)
from app.domain.models.p1_enums import CalculationKind, DayCountBasis

_MONEY = Decimal("0.01")


def calculate_simple_return(
    *,
    principal: str,
    annual_rate_percent: str,
    days: str,
    day_count_basis: DayCountBasis,
) -> CalculationResult:
    p = parse_decimal_input(principal, label="本金")
    rate_pct = parse_percent_input(annual_rate_percent, label="年化比例")
    d = parse_decimal_input(days, label="天数")
    if p < 0:
        raise ValueError("本金不能为负")
    if rate_pct < 0:
        raise ValueError("年化比例不能为负")
    if d < 0:
        raise ValueError("天数不能为负")
    if d == 0:
        raise ValueError("天数不能为零")

    basis = Decimal(day_count_basis.value)
    # 本金 × (年化%/100) × 天数 ÷ 基数
    raw = p * (rate_pct / Decimal("100")) * d / basis
    result = raw.quantize(_MONEY, rounding=ROUND_HALF_UP)
    formula = (
        f"{format(p, 'f')} × {format(rate_pct, 'f')}% × {format(d, 'f')} ÷ {day_count_basis.value}"
    )
    return CalculationResult(
        kind=CalculationKind.simple_return,
        formula=formula,
        inputs={
            "principal": format(p, "f"),
            "annual_rate_percent": format(rate_pct, "f"),
            "days": format(d, "f"),
            "day_count_basis": day_count_basis.value,
        },
        assumptions=[
            f"计息基数按 {day_count_basis.value} 天/年",
            "按单利、比例天数折算，不做复利",
        ],
        result=format(result, "f"),
    )
