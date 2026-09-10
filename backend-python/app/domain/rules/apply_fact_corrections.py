"""把用户事实纠错应用到 KeyParameter 与 FinancialFact 账本（P2-RC-04）。"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.domain.models.correction import CorrectionKind, CorrectionRecord
from app.domain.models.enums import FactStatus, ParameterKey
from app.domain.models.financial_fact import (
    ExtractorSource,
    FinancialFact,
    FinancialFactStatus,
    ValueKind,
)
from app.domain.models.report import KeyParameter

_PARAM_TO_FIELD: dict[ParameterKey, str] = {
    ParameterKey.amount: "amount",
    ParameterKey.term: "term",
    ParameterKey.annual_interest_rate: "annual_interest_rate",
    ParameterKey.expected_return: "expected_return",
    ParameterKey.prepayment_fee: "prepayment_fee",
    ParameterKey.penalty_interest: "penalty_interest",
    ParameterKey.repayment_method: "repayment_method",
    ParameterKey.product_risk_grade: "product_risk_grade",
    ParameterKey.fee_structure: "management_fee",
    ParameterKey.principal_protection: "principal_protection",
    ParameterKey.early_redemption: "early_redemption",
}

_FIELD_TO_PARAM: dict[str, ParameterKey] = {v: k for k, v in _PARAM_TO_FIELD.items()}


def parameter_key_for_field(field_key: str) -> ParameterKey | None:
    return _FIELD_TO_PARAM.get(field_key)


def field_key_for_parameter(key: ParameterKey) -> str | None:
    return _PARAM_TO_FIELD.get(key)


def apply_fact_corrections_to_parameters(
    key_parameters: list[KeyParameter],
    corrections: list[CorrectionRecord],
) -> list[KeyParameter]:
    """兼容旧接口：仅更新 KeyParameter。"""
    patched, _ = apply_corrections_to_ledger(key_parameters, [], corrections)
    return patched


def apply_corrections_to_ledger(
    key_parameters: list[KeyParameter],
    financial_facts: list[FinancialFact],
    corrections: list[CorrectionRecord],
) -> tuple[list[KeyParameter], list[FinancialFact]]:
    """同步 KP + FF；USER_ASSERTED 不伪造 evidence，保留被替代的原文事实。"""
    fact_recs = [c for c in corrections if c.kind == CorrectionKind.fact_value]
    if not fact_recs:
        return key_parameters, financial_facts

    by_key = {p.key: i for i, p in enumerate(key_parameters)}
    out_params = list(key_parameters)
    out_facts = list(financial_facts)
    facts_by_id = {f.fact_id: f for f in out_facts}

    for rec in fact_recs:
        target = _resolve_target_fact(rec, out_facts, facts_by_id)
        param_key = rec.parameter_key
        if param_key is None and target is not None:
            param_key = parameter_key_for_field(target.field_key)
        if param_key is None:
            # 无法映射参数时仍写入账本
            param_key = None

        if param_key is not None and param_key in by_key:
            old = out_params[by_key[param_key]]
            amount = None
            if param_key == ParameterKey.amount:
                try:
                    amount = Decimal(str(rec.new_value).replace(",", ""))
                except (InvalidOperation, ValueError):
                    amount = None
            out_params[by_key[param_key]] = KeyParameter(
                key=old.key,
                label=old.label,
                value=rec.new_value,
                status=FactStatus.user_asserted,
                amount=amount,
            )
        elif param_key is not None and param_key not in by_key:
            # 父任务校验应已拒绝；此处不再静默忽略——追加一条用户声明参数
            out_params.append(
                KeyParameter(
                    key=param_key,
                    label=param_key.value,
                    value=rec.new_value,
                    status=FactStatus.user_asserted,
                )
            )
            by_key[param_key] = len(out_params) - 1

        field_key = (
            target.field_key
            if target is not None
            else (field_key_for_parameter(param_key) if param_key else None)
        )
        if field_key is None:
            continue
        supersedes = (
            rec.supersedes_fact_id
            or rec.fact_id
            or (target.fact_id if target is not None else None)
        )
        user_fact = FinancialFact(
            fact_id=f"ff_user_{uuid4().hex[:12]}",
            product_id=target.product_id if target else None,
            source_id=target.source_id if target else None,
            field_key=field_key,
            raw_value=rec.new_value,
            normalized_value=rec.new_value,
            unit=target.unit if target else None,
            value_kind=target.value_kind if target else ValueKind.text,
            status=FinancialFactStatus.USER_ASSERTED,
            evidence_refs=[],
            extractor_source=ExtractorSource.USER_CORRECTION,
            supersedes_fact_id=supersedes,
        )
        out_facts.append(user_fact)
        facts_by_id[user_fact.fact_id] = user_fact

    return out_params, out_facts


def _resolve_target_fact(
    rec: CorrectionRecord,
    facts: list[FinancialFact],
    by_id: dict[str, FinancialFact],
) -> FinancialFact | None:
    if rec.fact_id and rec.fact_id in by_id:
        return by_id[rec.fact_id]
    if rec.supersedes_fact_id and rec.supersedes_fact_id in by_id:
        return by_id[rec.supersedes_fact_id]
    if rec.parameter_key is not None:
        field = field_key_for_parameter(rec.parameter_key)
        if field:
            for f in facts:
                if (
                    f.field_key == field
                    and f.status == FinancialFactStatus.CONFIRMED
                    and f.supersedes_fact_id is None
                ):
                    return f
            for f in facts:
                if f.field_key == field:
                    return f
    return None


def active_financial_facts(facts: list[FinancialFact]) -> list[FinancialFact]:
    """被 USER_ASSERTED 替代的原文事实不再进入有效集合（仍保留在完整账本中）。"""
    superseded = {
        f.supersedes_fact_id
        for f in facts
        if f.status == FinancialFactStatus.USER_ASSERTED and f.supersedes_fact_id
    }
    return [f for f in facts if f.fact_id not in superseded]
