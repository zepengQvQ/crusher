"""输入完整性检查（P2-03 / P2-RC-03）。

用途：按意图确定性矩阵判断能否继续；不足则生成最多 3 条业务追问。
输入：CompletenessCheckRequest。
输出：CompletenessResult（含规范化后的有效答案与 resolved_request）。
不变量：不调用大模型；材料内指令不改变要求矩阵；非法澄清答案拒绝而非静默放行。
失败方式：can_continue=false + questions；ClarificationRejected → 422。
"""
from __future__ import annotations

from app.domain.models.completeness import (
    AnswerControl,
    ClarifyingOption,
    ClarifyingQuestion,
    CompletenessCheckRequest,
    CompletenessResult,
    GapKind,
)
from app.domain.models.enums import ProductHint
from app.domain.models.intent import IntentType, SourceRole
from app.domain.models.p1_enums import CalculationKind
from app.domain.rules.clarification_catalog import (
    ClarificationRejected,
    is_ack_only,
    validate_and_apply_clarifications,
)

_LOAN_MARKERS = ("贷款", "消费贷", "借款", "等额本息", "年化利率")
_DEPOSIT_MARKERS = ("结构性存款", "结构存款", "观察区间", "挂钩型存款")
_ALLOWED_DOC_EXT = (".pdf", ".jpg", ".jpeg", ".png")
_MAX_DOC_BYTES = 10 * 1024 * 1024
_MAX_PDF_PAGES = 10


class CompletenessChecker:
    """确定性完整性检查器。"""

    def check(self, request: CompletenessCheckRequest) -> CompletenessResult:
        applied = validate_and_apply_clarifications(request)
        resolved = applied.resolved_request or request
        answers = dict(applied.effective_answers)

        raw: list[ClarifyingQuestion] = []

        if resolved.intent == IntentType.single_analysis:
            raw.extend(self._single_analysis(resolved, answers))
        elif resolved.intent == IntentType.dual_source_compare:
            raw.extend(self._dual(resolved, answers))
        elif resolved.intent == IntentType.product_compare:
            raw.extend(self._product_compare(resolved, answers))
        elif resolved.intent == IntentType.calculation:
            raw.extend(self._calculation(resolved, answers))
        elif resolved.intent == IntentType.evidence_follow_up:
            raw.extend(self._follow_up(resolved, answers))
        elif resolved.intent == IntentType.document_extract:
            raw.extend(self._document(resolved, answers))
        elif resolved.intent in (IntentType.unsupported, IntentType.ambiguous):
            raw.append(
                ClarifyingQuestion(
                    question_id="intent_pick",
                    prompt="请先选择要做的事（分析、对照、对比或计算）",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(value="single_analysis", label="单材料分析"),
                        ClarifyingOption(value="dual_source_compare", label="销售与材料对照"),
                        ClarifyingOption(value="product_compare", label="两款产品对照"),
                        ClarifyingOption(value="calculation", label="简单计算"),
                    ],
                    blocking_priority=1,
                )
            )
        else:
            raw.append(
                ClarifyingQuestion(
                    question_id="intent_unknown",
                    prompt="当前意图无法继续，请返回首页重新选择",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[ClarifyingOption(value="home", label="返回首页")],
                    blocking_priority=1,
                )
            )

        # 仅当有效答案覆盖且非 ack_only 时跳过；文档「知道了」不可解阻
        pending: list[ClarifyingQuestion] = []
        for q in raw:
            if is_ack_only(q.question_id):
                pending.append(q)
                continue
            if q.question_id in answers and answers[q.question_id]:
                continue
            pending.append(q)
        pending.sort(key=lambda q: q.blocking_priority)
        top = pending[:3]
        can_continue = len(top) == 0
        summary = (
            "输入已满足继续条件"
            if can_continue
            else f"还需确认 {len(top)} 项后才能继续"
        )
        return CompletenessResult(
            intent=resolved.intent,
            can_continue=can_continue,
            questions=top,
            summary=summary,
            answered=list(applied.normalized_answers),
            resolved_request=resolved,
        )

    def _single_analysis(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        texts = [e.text.strip() for e in request.source_envelopes if e.text.strip()]
        if not texts:
            out.append(
                ClarifyingQuestion(
                    question_id="single_text",
                    prompt="请粘贴一份产品材料或合同条款后再分析",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.free_text,
                    blocking_priority=10,
                )
            )
            return out

        joined = "\n".join(texts)
        loan = any(m in joined for m in _LOAN_MARKERS)
        deposit = any(m in joined for m in _DEPOSIT_MARKERS)
        hint = request.product_hint
        product_answer = answers.get("product_type_confirm", "")
        hint_resolved = hint in (ProductHint.loan, ProductHint.structured_deposit)

        conflict = False
        if hint == ProductHint.auto and loan and deposit and not product_answer:
            conflict = True
        if (
            hint == ProductHint.structured_deposit
            and loan
            and not deposit
            and not product_answer
        ):
            conflict = True
        if hint == ProductHint.loan and deposit and not loan and not product_answer:
            conflict = True
        # 已应用 product_hint 后 auto 冲突应已解除
        if conflict and hint_resolved and product_answer:
            conflict = False
        if conflict:
            out.append(
                ClarifyingQuestion(
                    question_id="product_type_confirm",
                    prompt="这是结构性存款还是贷款？",
                    gap_kind=GapKind.value_conflict,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(value="structured_deposit", label="结构性存款"),
                        ClarifyingOption(value="loan", label="贷款"),
                    ],
                    blocking_priority=20,
                )
            )
        return out

    def _dual(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        envs = list(request.source_envelopes)
        if len(envs) < 2:
            out.append(
                ClarifyingQuestion(
                    question_id="dual_need_two",
                    prompt="请分别提供销售话术和正式材料两侧内容",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.free_text,
                    blocking_priority=10,
                )
            )
            return out

        roles = {e.role for e in envs}
        sales = any(e.role == SourceRole.sales_pitch for e in envs)
        official = any(e.role == SourceRole.official_document for e in envs)
        role_answer = answers.get("dual_roles", "")
        if (not sales or not official) and SourceRole.unknown in roles and not role_answer:
            out.append(
                ClarifyingQuestion(
                    question_id="dual_roles",
                    prompt="哪一份是正式材料？",
                    gap_kind=GapKind.user_unconfirmed,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(value="first_official", label="第一份是正式材料"),
                        ClarifyingOption(value="second_official", label="第二份是正式材料"),
                    ],
                    blocking_priority=20,
                )
            )
        return out

    def _product_compare(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        envs = [e for e in request.source_envelopes if e.text.strip()]
        if len(envs) < 2:
            out.append(
                ClarifyingQuestion(
                    question_id="compare_need_two",
                    prompt="请补充第二款产品材料",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.free_text,
                    blocking_priority=10,
                )
            )
            return out
        ab_answer = answers.get("compare_ab", "")
        if all(e.role == SourceRole.unknown for e in envs[:2]) and not ab_answer:
            out.append(
                ClarifyingQuestion(
                    question_id="compare_ab",
                    prompt="请确认哪一份是产品 A、哪一份是产品 B",
                    gap_kind=GapKind.user_unconfirmed,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(
                            value="order_as_is",
                            label="按当前顺序：第一份=A，第二份=B",
                        ),
                        ClarifyingOption(value="swap", label="对调：第一份=B，第二份=A"),
                    ],
                    blocking_priority=20,
                )
            )
        return out

    def _calculation(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        kind = request.calculation_kind
        kind_ans = answers.get("calc_kind", "")
        if kind is None and not kind_ans:
            out.append(
                ClarifyingQuestion(
                    question_id="calc_kind",
                    prompt="要算哪一类？",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(value="simple_return", label="简单收益"),
                        ClarifyingOption(value="fee", label="比例费用"),
                        ClarifyingOption(value="net_exit", label="退出净结果"),
                    ],
                    blocking_priority=5,
                )
            )
            return out

        try:
            resolved_kind = kind or CalculationKind(kind_ans)
        except ValueError as exc:
            raise ClarificationRejected(
                f"calc_kind 的取值不在允许选项内：{kind_ans}"
            ) from exc

        if resolved_kind == CalculationKind.simple_return:
            if not (request.principal or answers.get("principal")):
                out.append(
                    ClarifyingQuestion(
                        question_id="principal",
                        prompt="请填写本金金额（元）",
                        gap_kind=GapKind.field_missing,
                        control=AnswerControl.free_text,
                        blocking_priority=10,
                    )
                )
            if not (request.annual_rate_percent or answers.get("annual_rate_percent")):
                out.append(
                    ClarifyingQuestion(
                        question_id="annual_rate_percent",
                        prompt="请填写年化比例（例如 3.65）",
                        gap_kind=GapKind.field_missing,
                        control=AnswerControl.free_text,
                        blocking_priority=11,
                    )
                )
            if not (request.days or answers.get("days")):
                out.append(
                    ClarifyingQuestion(
                        question_id="days",
                        prompt="请填写计息天数",
                        gap_kind=GapKind.field_missing,
                        control=AnswerControl.free_text,
                        blocking_priority=12,
                    )
                )
            if request.day_count_basis is None and not answers.get("day_count_basis"):
                out.append(
                    ClarifyingQuestion(
                        question_id="day_count_basis",
                        prompt="按 360 天还是 365 天计息？",
                        gap_kind=GapKind.user_unconfirmed,
                        control=AnswerControl.buttons,
                        options=[
                            ClarifyingOption(value="360", label="360 天"),
                            ClarifyingOption(value="365", label="365 天"),
                        ],
                        blocking_priority=13,
                    )
                )
        elif resolved_kind == CalculationKind.fee:
            if not (request.fee_base or answers.get("fee_base")):
                out.append(
                    ClarifyingQuestion(
                        question_id="fee_base",
                        prompt="请填写计费基数（元）",
                        gap_kind=GapKind.field_missing,
                        control=AnswerControl.free_text,
                        blocking_priority=10,
                    )
                )
            if not (request.fee_rate_percent or answers.get("fee_rate_percent")):
                out.append(
                    ClarifyingQuestion(
                        question_id="fee_rate_percent",
                        prompt="请填写费率百分比",
                        gap_kind=GapKind.field_missing,
                        control=AnswerControl.free_text,
                        blocking_priority=11,
                    )
                )
        elif resolved_kind == CalculationKind.net_exit:
            checks = (
                ("principal", request.principal, "请填写本金金额（元）"),
                ("return_amount", request.return_amount, "请填写收益金额（元）"),
                ("fee_amount", request.fee_amount, "请填写费用金额（元）"),
            )
            for qid, attr, prompt in checks:
                if not (attr or answers.get(qid)):
                    out.append(
                        ClarifyingQuestion(
                            question_id=qid,
                            prompt=prompt,
                            gap_kind=GapKind.field_missing,
                            control=AnswerControl.free_text,
                            blocking_priority=10,
                        )
                    )

        if not request.user_confirmed_calculation and not answers.get("calc_confirm"):
            out.append(
                ClarifyingQuestion(
                    question_id="calc_confirm",
                    prompt="请确认以上计算参数无误后再计算",
                    gap_kind=GapKind.user_unconfirmed,
                    control=AnswerControl.buttons,
                    options=[
                        ClarifyingOption(value="confirmed", label="我已确认参数"),
                    ],
                    blocking_priority=90,
                )
            )
        return out

    def _follow_up(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        if not (request.follow_up_question or answers.get("follow_up_question")):
            out.append(
                ClarifyingQuestion(
                    question_id="follow_up_question",
                    prompt="请输入要追问的问题",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.free_text,
                    blocking_priority=10,
                )
            )
        if not request.source_envelopes and not request.bound_source_id and not answers.get(
            "bound_source"
        ):
            out.append(
                ClarifyingQuestion(
                    question_id="bound_source",
                    prompt="请先选择要基于哪份材料回答",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.free_text,
                    blocking_priority=11,
                )
            )
        return out

    def _document(
        self,
        request: CompletenessCheckRequest,
        answers: dict[str, str],
    ) -> list[ClarifyingQuestion]:
        out: list[ClarifyingQuestion] = []
        names = [n.lower() for n in request.document_file_names]
        if not names:
            out.append(
                ClarifyingQuestion(
                    question_id="doc_missing",
                    prompt="请上传 PDF 或图片（JPG/PNG）；暂不支持 Word/Excel",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[ClarifyingOption(value="ok", label="知道了")],
                    blocking_priority=10,
                )
            )
            return out
        bad_ext = [n for n in names if not any(n.endswith(ext) for ext in _ALLOWED_DOC_EXT)]
        if bad_ext:
            out.append(
                ClarifyingQuestion(
                    question_id="doc_type",
                    prompt="文件类型不支持，请换成 PDF 或 JPG/PNG",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[ClarifyingOption(value="ok", label="知道了")],
                    blocking_priority=5,
                )
            )
        if (
            request.document_bytes_total is not None
            and request.document_bytes_total > _MAX_DOC_BYTES
        ):
            out.append(
                ClarifyingQuestion(
                    question_id="doc_size",
                    prompt="文件过大（超过 10MB），请压缩或换文本粘贴",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[ClarifyingOption(value="ok", label="知道了")],
                    blocking_priority=6,
                )
            )
        if request.document_page_count is not None and request.document_page_count > _MAX_PDF_PAGES:
            out.append(
                ClarifyingQuestion(
                    question_id="doc_pages",
                    prompt="PDF 超过 10 页，请拆分后再上传",
                    gap_kind=GapKind.field_missing,
                    control=AnswerControl.buttons,
                    options=[ClarifyingOption(value="ok", label="知道了")],
                    blocking_priority=7,
                )
            )
        _ = answers
        return out


__all__ = ["CompletenessChecker", "ClarificationRejected"]
