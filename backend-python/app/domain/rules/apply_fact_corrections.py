"""把用户事实纠错应用到关键参数列表。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation

from app.domain.models.correction import CorrectionKind, CorrectionRecord
from app.domain.models.enums import FactStatus, ParameterKey
from app.domain.models.report import KeyParameter


def apply_fact_corrections_to_parameters(
    key_parameters: list[KeyParameter],
    corrections: list[CorrectionRecord],
) -> list[KeyParameter]:
    """fact_value → user_asserted；禁止写成 document_fact。"""
    fact_recs = [
        c
        for c in corrections
        if c.kind == CorrectionKind.fact_value and c.parameter_key is not None
    ]
    if not fact_recs:
        return key_parameters

    by_key = {p.key: i for i, p in enumerate(key_parameters)}
    out = list(key_parameters)
    for rec in fact_recs:
        key = rec.parameter_key
        assert key is not None
        if key not in by_key:
            continue
        old = out[by_key[key]]
        amount = None
        if key == ParameterKey.amount:
            try:
                amount = Decimal(str(rec.new_value).replace(",", ""))
            except (InvalidOperation, ValueError):
                amount = None
        out[by_key[key]] = KeyParameter(
            key=old.key,
            label=old.label,
            value=rec.new_value,
            status=FactStatus.user_asserted,
            amount=amount,
        )
    return out
