"""比例费用：计费基数 × 费率。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.models.calculation import (
    CalculationResult,
    parse_decimal_input,
    parse_percent_input,
)
from app.domain.models.p1_enums import CalculationKind

_MONEY = Decimal("0.01")


def calculate_fee(*, fee_base: str, fee_rate_percent: str) -> CalculationResult:
    base = parse_decimal_input(fee_base, label="计费基数")
    rate_pct = parse_percent_input(fee_rate_percent, label="费率")
    if base < 0:
        raise ValueError("计费基数不能为负")
    if rate_pct < 0:
        raise ValueError("费率不能为负")

    raw = base * (rate_pct / Decimal("100"))
    result = raw.quantize(_MONEY, rounding=ROUND_HALF_UP)
    formula = f"{format(base, 'f')} × {format(rate_pct, 'f')}%"
    return CalculationResult(
        kind=CalculationKind.fee,
        formula=formula,
        inputs={
            "fee_base": format(base, "f"),
            "fee_rate_percent": format(rate_pct, "f"),
        },
        assumptions=["按比例费用一次性计算，不含税费与附加条件"],
        result=format(result, "f"),
    )
