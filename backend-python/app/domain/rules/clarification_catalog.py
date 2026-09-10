"""追问定义表：校验、规范化与应用（P2-RC-03）。

未知 / 重复 question_id、非法选项与非法数值 → ClarificationRejected（稳定 422）。
ack_only 题（文档类「知道了」）可记录，但不可解阻材料缺失。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Callable

from app.domain.models.completeness import (
    ClarificationAnswer,
    CompletenessCheckRequest,
)
from app.domain.models.enums import ProductHint
from app.domain.models.intent import SourceEnvelope, SourceRole
from app.domain.models.p1_enums import CalculationKind, DayCountBasis
from app.shared.enums import ErrorCode


class ClarificationRejected(Exception):
    """澄清答案不合法，应映射 HTTP 422。"""

    def __init__(self, message: str, *, error_code: ErrorCode = ErrorCode.CLARIFICATION_INVALID) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AnswerKind(str, Enum):
    buttons = "buttons"
    enum = "enum"
    decimal_amount = "decimal_amount"
    decimal_percent = "decimal_percent"
    positive_int = "positive_int"
    free_text = "free_text"
    ack_only = "ack_only"


ApplyFn = Callable[[CompletenessCheckRequest, str], CompletenessCheckRequest]


@dataclass(frozen=True)
class QuestionDef:
    question_id: str
    kind: AnswerKind
    allowed_values: frozenset[str] = frozenset()
    apply: ApplyFn | None = None
    # ack_only：答案合法也不解除对应阻塞条件
    ack_only: bool = False
    max_amount: Decimal = Decimal("100000000")
    max_days: int = 36500
    max_percent: Decimal = Decimal("1000")


def _apply_product_hint(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    return req.model_copy(update={"product_hint": ProductHint(value)})


def _apply_calc_kind(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    return req.model_copy(update={"calculation_kind": CalculationKind(value)})


def _apply_day_count(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    return req.model_copy(update={"day_count_basis": DayCountBasis(value)})


def _apply_calc_confirm(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    if value == "confirmed":
        return req.model_copy(update={"user_confirmed_calculation": True})
    return req


def _apply_field(name: str) -> ApplyFn:
    def _inner(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
        return req.model_copy(update={name: value})

    return _inner


def _apply_dual_roles(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    envs = list(req.source_envelopes)
    if len(envs) < 2:
        return req
    first, second = envs[0], envs[1]
    if value == "first_official":
        first = first.model_copy(update={"role": SourceRole.official_document})
        second = second.model_copy(update={"role": SourceRole.sales_pitch})
    elif value == "second_official":
        first = first.model_copy(update={"role": SourceRole.sales_pitch})
        second = second.model_copy(update={"role": SourceRole.official_document})
    else:
        return req
    rest = envs[2:]
    return req.model_copy(update={"source_envelopes": [first, second, *rest]})


def _apply_compare_ab(req: CompletenessCheckRequest, value: str) -> CompletenessCheckRequest:
    envs = list(req.source_envelopes)
    if len(envs) < 2:
        return req
    if value == "swap":
        envs[0], envs[1] = envs[1], envs[0]
    # order_as_is：保持顺序
    return req.model_copy(update={"source_envelopes": envs})


QUESTION_DEFS: dict[str, QuestionDef] = {
    "product_type_confirm": QuestionDef(
        question_id="product_type_confirm",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"structured_deposit", "loan"}),
        apply=_apply_product_hint,
    ),
    "dual_roles": QuestionDef(
        question_id="dual_roles",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"first_official", "second_official"}),
        apply=_apply_dual_roles,
    ),
    "compare_ab": QuestionDef(
        question_id="compare_ab",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"order_as_is", "swap"}),
        apply=_apply_compare_ab,
    ),
    "calc_kind": QuestionDef(
        question_id="calc_kind",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"simple_return", "fee", "net_exit"}),
        apply=_apply_calc_kind,
    ),
    "day_count_basis": QuestionDef(
        question_id="day_count_basis",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"360", "365"}),
        apply=_apply_day_count,
    ),
    "calc_confirm": QuestionDef(
        question_id="calc_confirm",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"confirmed"}),
        apply=_apply_calc_confirm,
    ),
    "principal": QuestionDef(
        question_id="principal",
        kind=AnswerKind.decimal_amount,
        apply=_apply_field("principal"),
    ),
    "annual_rate_percent": QuestionDef(
        question_id="annual_rate_percent",
        kind=AnswerKind.decimal_percent,
        apply=_apply_field("annual_rate_percent"),
    ),
    "days": QuestionDef(
        question_id="days",
        kind=AnswerKind.positive_int,
        apply=_apply_field("days"),
    ),
    "fee_base": QuestionDef(
        question_id="fee_base",
        kind=AnswerKind.decimal_amount,
        apply=_apply_field("fee_base"),
    ),
    "fee_rate_percent": QuestionDef(
        question_id="fee_rate_percent",
        kind=AnswerKind.decimal_percent,
        apply=_apply_field("fee_rate_percent"),
    ),
    "return_amount": QuestionDef(
        question_id="return_amount",
        kind=AnswerKind.decimal_amount,
        apply=_apply_field("return_amount"),
    ),
    "fee_amount": QuestionDef(
        question_id="fee_amount",
        kind=AnswerKind.decimal_amount,
        apply=_apply_field("fee_amount"),
    ),
    "follow_up_question": QuestionDef(
        question_id="follow_up_question",
        kind=AnswerKind.free_text,
        apply=_apply_field("follow_up_question"),
    ),
    "bound_source": QuestionDef(
        question_id="bound_source",
        kind=AnswerKind.free_text,
        apply=_apply_field("bound_source_id"),
    ),
    "single_text": QuestionDef(
        question_id="single_text",
        kind=AnswerKind.free_text,
    ),
    "dual_need_two": QuestionDef(
        question_id="dual_need_two",
        kind=AnswerKind.free_text,
    ),
    "compare_need_two": QuestionDef(
        question_id="compare_need_two",
        kind=AnswerKind.free_text,
    ),
    "intent_pick": QuestionDef(
        question_id="intent_pick",
        kind=AnswerKind.buttons,
        allowed_values=frozenset(
            {
                "single_analysis",
                "dual_source_compare",
                "product_compare",
                "calculation",
            }
        ),
    ),
    "intent_unknown": QuestionDef(
        question_id="intent_unknown",
        kind=AnswerKind.buttons,
        allowed_values=frozenset({"home"}),
    ),
    "doc_missing": QuestionDef(
        question_id="doc_missing",
        kind=AnswerKind.ack_only,
        allowed_values=frozenset({"ok"}),
        ack_only=True,
    ),
    "doc_type": QuestionDef(
        question_id="doc_type",
        kind=AnswerKind.ack_only,
        allowed_values=frozenset({"ok"}),
        ack_only=True,
    ),
    "doc_size": QuestionDef(
        question_id="doc_size",
        kind=AnswerKind.ack_only,
        allowed_values=frozenset({"ok"}),
        ack_only=True,
    ),
    "doc_pages": QuestionDef(
        question_id="doc_pages",
        kind=AnswerKind.ack_only,
        allowed_values=frozenset({"ok"}),
        ack_only=True,
    ),
}


@dataclass
class ClarificationApplyResult:
    normalized_answers: list[ClarificationAnswer] = field(default_factory=list)
    resolved_request: CompletenessCheckRequest | None = None
    # question_id → 规范化后的值（不含 ack_only 的解阻语义）
    effective_answers: dict[str, str] = field(default_factory=dict)


def _parse_amount(raw: str, defn: QuestionDef) -> str:
    text = raw.strip().replace(",", "").replace("，", "").replace(" ", "")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ClarificationRejected(f"{defn.question_id} 无法解析为金额") from exc
    if value <= 0:
        raise ClarificationRejected(f"{defn.question_id} 必须为正数")
    if value > defn.max_amount:
        raise ClarificationRejected(f"{defn.question_id} 超出合理范围")
    return format(value.normalize(), "f")


def _parse_percent(raw: str, defn: QuestionDef) -> str:
    text = raw.strip().replace(",", "").replace("%", "").replace("％", "").replace(" ", "")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ClarificationRejected(f"{defn.question_id} 无法解析为百分比") from exc
    if value < 0:
        raise ClarificationRejected(f"{defn.question_id} 不能为负数")
    if value > defn.max_percent:
        raise ClarificationRejected(f"{defn.question_id} 超出合理范围")
    return format(value.normalize(), "f")


def _parse_positive_int(raw: str, defn: QuestionDef) -> str:
    text = raw.strip().replace(",", "").replace(" ", "")
    try:
        value = Decimal(text)
    except (InvalidOperation, ValueError) as exc:
        raise ClarificationRejected(f"{defn.question_id} 必须为正整数") from exc
    if value != value.to_integral_value() or value <= 0:
        raise ClarificationRejected(f"{defn.question_id} 必须为正整数")
    as_int = int(value)
    if as_int > defn.max_days:
        raise ClarificationRejected(f"{defn.question_id} 超出合理范围")
    return str(as_int)


def normalize_answer_value(defn: QuestionDef, raw: str) -> str:
    value = (raw or "").strip()
    if not value:
        raise ClarificationRejected(f"{defn.question_id} 答案不能为空")
    if defn.kind in (AnswerKind.buttons, AnswerKind.enum, AnswerKind.ack_only):
        if value not in defn.allowed_values:
            raise ClarificationRejected(
                f"{defn.question_id} 的取值不在允许选项内：{value}"
            )
        return value
    if defn.kind == AnswerKind.decimal_amount:
        return _parse_amount(value, defn)
    if defn.kind == AnswerKind.decimal_percent:
        return _parse_percent(value, defn)
    if defn.kind == AnswerKind.positive_int:
        return _parse_positive_int(value, defn)
    if defn.kind == AnswerKind.free_text:
        if len(value) > 200:
            raise ClarificationRejected(f"{defn.question_id} 过长")
        return value
    raise ClarificationRejected(f"未知答案类型：{defn.kind}")


def validate_and_apply_clarifications(
    request: CompletenessCheckRequest,
) -> ClarificationApplyResult:
    """校验 clarification_answers，写回 resolved_request，并产出有效答案表。"""
    raw = list(request.clarification_answers)
    seen: set[str] = set()
    for ans in raw:
        qid = ans.question_id
        if qid in seen:
            raise ClarificationRejected(f"重复的 question_id：{qid}")
        seen.add(qid)
        if qid not in QUESTION_DEFS:
            raise ClarificationRejected(f"未知的 question_id：{qid}")

    resolved = request.model_copy(deep=True)
    # 清空后再用规范化答案重建，避免脏值残留
    resolved = resolved.model_copy(update={"clarification_answers": []})

    normalized: list[ClarificationAnswer] = []
    effective: dict[str, str] = {}

    for ans in raw:
        defn = QUESTION_DEFS[ans.question_id]
        norm = normalize_answer_value(defn, ans.value)
        normalized.append(ClarificationAnswer(question_id=ans.question_id, value=norm))
        if not defn.ack_only:
            effective[ans.question_id] = norm
        if defn.apply is not None:
            resolved = defn.apply(resolved, norm)

    resolved = resolved.model_copy(update={"clarification_answers": list(normalized)})
    return ClarificationApplyResult(
        normalized_answers=normalized,
        resolved_request=resolved,
        effective_answers=effective,
    )


def is_ack_only(question_id: str) -> bool:
    defn = QUESTION_DEFS.get(question_id)
    return bool(defn and defn.ack_only)
