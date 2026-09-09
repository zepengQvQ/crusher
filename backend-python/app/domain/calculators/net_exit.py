"""退出净结果：本金 + 收益 - 费用。"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from app.domain.models.calculation import CalculationResult, parse_decimal_input
from app.domain.models.p1_enums import CalculationKind

_MONEY = Decimal("0.01")


def calculate_net_exit(
    *,
    principal: str,
    return_amount: str,
    fee_amount: str,
) -> CalculationResult:
    p = parse_decimal_input(principal, label="本金")
    ret = parse_decimal_input(return_amount, label="收益")
    fee = parse_decimal_input(fee_amount, label="费用")
    if p < 0:
        raise ValueError("本金不能为负")
    if fee < 0:
        raise ValueError("费用不能为负")

    raw = p + ret - fee
    result = raw.quantize(_MONEY, rounding=ROUND_HALF_UP)
    formula = f"{format(p, 'f')} + {format(ret, 'f')} - {format(fee, 'f')}"
    return CalculationResult(
        kind=CalculationKind.net_exit,
        formula=formula,
        inputs={
            "principal": format(p, "f"),
            "return_amount": format(ret, "f"),
            "fee_amount": format(fee, "f"),
        },
        assumptions=["收益与费用须由用户确认；不做 IRR/税费/复利"],
        result=format(result, "f"),
    )
