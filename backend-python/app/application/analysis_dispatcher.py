"""分析分发器（P2-RC-05）。

用途：把六种支持意图稳定路由到已注入的 UseCase，并固定编排顺序。
Java 对照：Application Service / Facade + 构造函数注入的策略表（禁止反射选工具）。
输入：DispatchRequest（显式意图 / 用户目标 / 材料信封 / 各意图字段）。
输出：DispatchResult。
业务不变量：
  1) IntentType → UseCase 仅走显式映射，禁止动态 import / Agent 挑工具名；
  2) 顺序固定：显式意图 → IntentDecision → CompletenessCheck → UseCase → 结果校验；
  3) 歧义/拒绝/不完整不得执行任何业务 UseCase；
  4) 计算/追问缺前置报告时返回明确 next_steps。
失败方式：status 为 needs_clarification / incomplete / rejected / needs_prior_report。
"""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from app.application.analyze_dual_sources import AnalyzeDualSourcesUseCase
from app.application.analyze_text import AnalyzeTextUseCase
from app.application.answer_from_evidence import AnswerFromEvidenceUseCase
from app.application.calculate_scenario import CalculateScenarioUseCase
from app.application.check_input_completeness import (
    CheckInputCompletenessUseCase,
    ClarificationRejected,
)
from app.application.compare_products import CompareProductsUseCase
from app.application.extract_document import ExtractDocumentUseCase
from app.application.resolve_intent import ResolveIntentUseCase
from app.domain.models.calculation import CalculateScenarioRequest
from app.domain.models.claim_comparison import DualAnalysisRequest
from app.domain.models.completeness import CompletenessCheckRequest, CompletenessResult
from app.domain.models.dispatch import DispatchRequest, DispatchResult, DispatchStatus
from app.domain.models.evidence_answer import FollowUpRequest
from app.domain.models.intent import (
    INTENT_USE_CASE_MAP,
    DecisionStatus,
    IntentDecision,
    IntentResolveRequest,
    IntentType,
    SourceRole,
)
from app.domain.models.p1_enums import DayCountBasis
from app.domain.models.product_facts import ProductCompareRequest
from app.domain.models.report import CreateAnalysisRequest
from app.domain.validation.publication_gate import (
    decide_clarify,
    decide_publish,
    decide_refuse,
)
from app.shared.enums import ErrorCode

Handler = Callable[[DispatchRequest, CompletenessResult], Any]


class AnalysisDispatcher:
    """显式 IntentType → UseCase 映射的统一入口。"""

    def __init__(
        self,
        *,
        resolve_intent: ResolveIntentUseCase,
        check_completeness: CheckInputCompletenessUseCase,
        analyze_text: AnalyzeTextUseCase,
        analyze_dual: AnalyzeDualSourcesUseCase,
        compare_products: CompareProductsUseCase,
        calculate: CalculateScenarioUseCase,
        answer_from_evidence: AnswerFromEvidenceUseCase,
        extract_document: ExtractDocumentUseCase,
    ) -> None:
        self._resolve_intent = resolve_intent
        self._check_completeness = check_completeness
        self._analyze_text = analyze_text
        self._analyze_dual = analyze_dual
        self._compare_products = compare_products
        self._calculate = calculate
        self._answer_from_evidence = answer_from_evidence
        self._extract_document = extract_document
        # 显式映射表：键为 IntentType，值为已注入实例上的处理函数（非动态 import）
        self._handlers: dict[IntentType, Handler] = {
            IntentType.single_analysis: self._handle_single,
            IntentType.dual_source_compare: self._handle_dual,
            IntentType.product_compare: self._handle_compare,
            IntentType.calculation: self._handle_calculation,
            IntentType.evidence_follow_up: self._handle_follow_up,
            IntentType.document_extract: self._handle_document,
        }

    def dispatch(
        self,
        request: DispatchRequest,
        *,
        document_files: list[tuple[str, bytes]] | None = None,
    ) -> DispatchResult:
        """同步分发；文档提取在需要时于本方法内跑事件循环。"""
        # 1) 意图决议
        decision = self._resolve_intent.execute(
            IntentResolveRequest(
                user_query=request.user_query,
                explicit_intent=request.explicit_intent,
                page_route=request.page_route,
                source_envelopes=list(request.source_envelopes),
                allow_model_candidate=request.allow_model_candidate,
            )
        )

        if decision.status == DecisionStatus.needs_clarification:
            return DispatchResult(
                status=DispatchStatus.needs_clarification,
                intent_decision=decision,
                use_case_key=None,
                next_steps=[
                    o.label for o in decision.clarifying_options
                ]
                or list(decision.missing)
                or ["请先选择要做的事"],
                publication=decide_clarify(
                    reason_code=ErrorCode.INTENT_AMBIGUOUS,
                    user_reason="; ".join(decision.rationale) or "意图需澄清",
                    next_steps=[o.label for o in decision.clarifying_options][:3] or None,
                ),
            )

        if decision.status == DecisionStatus.rejected:
            return DispatchResult(
                status=DispatchStatus.rejected,
                intent_decision=decision,
                use_case_key=None,
                next_steps=[o.label for o in decision.clarifying_options]
                or ["请改用事实对照或单材料分析"],
                publication=decide_refuse(
                    reason_code=ErrorCode.UNSUPPORTED_REQUEST,
                    user_reason="; ".join(decision.rationale) or "超出 Demo 范围",
                    next_steps=[o.label for o in decision.clarifying_options][:3] or None,
                ),
            )

        intent = decision.intent
        use_case_key = INTENT_USE_CASE_MAP.get(intent)
        if use_case_key is None or intent not in self._handlers:
            return DispatchResult(
                status=DispatchStatus.rejected,
                intent_decision=decision,
                use_case_key=None,
                next_steps=["请从对应页面入口重新发起"],
                publication=decide_refuse(
                    reason_code=ErrorCode.UNSUPPORTED_REQUEST,
                    user_reason=f"不支持的意图：{intent.value}",
                ),
            )

        # 计算 / 追问：无前置报告且缺独立参数时，返回明确下一步（不做无效跳转）
        prior_gate = self._prior_report_gate(request, decision)
        if prior_gate is not None:
            return prior_gate

        # 2) 完整性检查（服务端真实执行）
        try:
            completeness = self._check_completeness.execute(
                self._to_completeness_request(request, intent)
            )
        except ClarificationRejected as exc:
            return DispatchResult(
                status=DispatchStatus.incomplete,
                intent_decision=decision,
                use_case_key=use_case_key,
                next_steps=["请按页面选项或规范格式重新回答追问"],
                publication=decide_clarify(
                    reason_code=ErrorCode.CLARIFICATION_INVALID,
                    user_reason=exc.message,
                ),
            )

        if not completeness.can_continue:
            return DispatchResult(
                status=DispatchStatus.incomplete,
                intent_decision=decision,
                completeness=completeness,
                use_case_key=use_case_key,
                next_steps=[q.prompt for q in completeness.questions]
                or [completeness.summary or "请补全必要输入后再继续"],
                publication=decide_clarify(
                    reason_code=ErrorCode.INTENT_AMBIGUOUS,
                    user_reason=completeness.summary or "输入不完整",
                    next_steps=[q.prompt for q in completeness.questions][:3] or None,
                ),
            )

        # 3) 调用已映射 UseCase
        handler = self._handlers[intent]
        # document_files 仅文档意图使用；挂在 request 旁路参数上
        self._document_files = document_files or []
        try:
            payload = handler(request, completeness)
        except ValueError as exc:
            return DispatchResult(
                status=DispatchStatus.incomplete,
                intent_decision=decision,
                completeness=completeness,
                use_case_key=use_case_key,
                next_steps=[str(exc)],
                publication=decide_clarify(
                    reason_code=ErrorCode.CLARIFICATION_INVALID,
                    user_reason=str(exc),
                ),
            )
        finally:
            self._document_files = []

        # 4) 结果校验：payload 必须非空；适用时附 PublicationDecision
        if payload is None:
            return DispatchResult(
                status=DispatchStatus.rejected,
                intent_decision=decision,
                completeness=completeness,
                use_case_key=use_case_key,
                next_steps=["业务执行未返回结果，请重试或换入口"],
                publication=decide_refuse(
                    reason_code=ErrorCode.INTERNAL_ERROR,
                    user_reason="UseCase 未返回结果",
                ),
            )

        publication = None
        if intent == IntentType.single_analysis:
            # 异步任务已提交；完整 publication 由 Harness 写回任务
            publication = decide_publish(
                user_reason="单材料分析任务已提交，发布门禁将在任务完成后给出"
            )
        elif hasattr(payload, "publication") and payload.publication is not None:
            # P2-RC-06：同步入口以报告内 PublicationService 决策为准
            publication = payload.publication
        elif intent in (
            IntentType.dual_source_compare,
            IntentType.product_compare,
            IntentType.calculation,
            IntentType.evidence_follow_up,
            IntentType.document_extract,
        ):
            publication = decide_publish(
                user_reason="已按意图执行对应 UseCase"
            )

        return DispatchResult(
            status=DispatchStatus.executed,
            intent_decision=decision,
            completeness=completeness,
            use_case_key=use_case_key,
            next_steps=[],
            publication=publication,
            payload=payload,
        )

    def _prior_report_gate(
        self, request: DispatchRequest, decision: IntentDecision
    ) -> DispatchResult | None:
        if request.prior_report_available:
            return None
        intent = decision.intent
        if intent == IntentType.calculation:
            has_params = bool(
                request.calculation_kind
                or request.principal
                or request.fee_base
                or request.clarification_answers
            )
            if has_params:
                return None
            steps = [
                "请先完成一次单材料分析",
                "再在报告页打开计算器填写参数",
            ]
            return DispatchResult(
                status=DispatchStatus.needs_prior_report,
                intent_decision=decision,
                use_case_key=INTENT_USE_CASE_MAP[intent],
                next_steps=steps,
                publication=decide_clarify(
                    reason_code=ErrorCode.INTENT_AMBIGUOUS,
                    user_reason="计算需要先有分析报告或完整计算参数",
                    next_steps=steps,
                ),
            )
        if intent == IntentType.evidence_follow_up:
            has_source = bool(request.source_envelopes) or bool(
                (request.follow_up_question or "").strip()
                and request.bound_source_id
            )
            if has_source and (request.follow_up_question or "").strip():
                # 有材料+问题可直接追问；仍无材料则要求前置报告
                if request.source_envelopes:
                    return None
            if not request.source_envelopes:
                steps = [
                    "请先完成一次单材料分析",
                    "再在报告页使用追问",
                ]
                return DispatchResult(
                    status=DispatchStatus.needs_prior_report,
                    intent_decision=decision,
                    use_case_key=INTENT_USE_CASE_MAP[intent],
                    next_steps=steps,
                    publication=decide_clarify(
                        reason_code=ErrorCode.INTENT_AMBIGUOUS,
                        user_reason="追问需要绑定已有分析材料",
                        next_steps=steps,
                    ),
                )
        return None

    def _to_completeness_request(
        self, request: DispatchRequest, intent: IntentType
    ) -> CompletenessCheckRequest:
        return CompletenessCheckRequest(
            intent=intent,
            source_envelopes=list(request.source_envelopes),
            product_hint=request.product_hint,
            calculation_kind=request.calculation_kind,
            principal=request.principal,
            annual_rate_percent=request.annual_rate_percent,
            days=request.days,
            day_count_basis=request.day_count_basis,
            fee_base=request.fee_base,
            fee_rate_percent=request.fee_rate_percent,
            return_amount=request.return_amount,
            fee_amount=request.fee_amount,
            user_confirmed_calculation=request.user_confirmed_calculation,
            follow_up_question=request.follow_up_question,
            bound_source_id=request.bound_source_id,
            document_file_names=list(request.document_file_names),
            document_bytes_total=request.document_bytes_total,
            document_page_count=request.document_page_count,
            clarification_answers=list(request.clarification_answers),
        )

    def _resolved_envelopes(
        self, completeness: CompletenessResult, fallback: DispatchRequest
    ) -> list:
        if completeness.resolved_request is not None:
            return list(completeness.resolved_request.source_envelopes)
        return list(fallback.source_envelopes)

    def _handle_single(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        envs = self._resolved_envelopes(completeness, request)
        if not envs:
            raise ValueError("单材料分析缺少原文")
        text = envs[0].text
        hint = request.product_hint
        if completeness.resolved_request is not None:
            hint = completeness.resolved_request.product_hint
        task = self._analyze_text.submit(
            CreateAnalysisRequest(text=text, product_hint=hint)
        )
        return {"task_id": task.task_id, "task_status": task.task_status.value}

    def _handle_dual(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        envs = self._resolved_envelopes(completeness, request)
        if len(envs) < 2:
            raise ValueError("双材料对照需要两份材料")
        sales = next((e for e in envs if e.role == SourceRole.sales_pitch), envs[0])
        official = next(
            (e for e in envs if e.role == SourceRole.official_document), envs[1]
        )
        hint = (
            completeness.resolved_request.product_hint
            if completeness.resolved_request is not None
            else request.product_hint
        )
        return self._analyze_dual.execute(
            DualAnalysisRequest(
                sales_text=sales.text,
                official_text=official.text,
                product_hint=hint,
            )
        )

    def _handle_compare(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        envs = self._resolved_envelopes(completeness, request)
        if len(envs) < 2:
            raise ValueError("产品对比需要两份材料")
        return self._compare_products.execute(
            ProductCompareRequest(text_a=envs[0].text, text_b=envs[1].text)
        )

    def _handle_calculation(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        resolved = completeness.resolved_request or self._to_completeness_request(
            request, IntentType.calculation
        )
        if resolved.calculation_kind is None:
            raise ValueError("缺少计算类型")
        return self._calculate.execute(
            CalculateScenarioRequest(
                kind=resolved.calculation_kind,
                user_confirmed=True,
                principal=resolved.principal,
                annual_rate_percent=resolved.annual_rate_percent,
                days=resolved.days,
                day_count_basis=resolved.day_count_basis or DayCountBasis.days_365,
                fee_base=resolved.fee_base,
                fee_rate_percent=resolved.fee_rate_percent,
                return_amount=resolved.return_amount,
                fee_amount=resolved.fee_amount,
            )
        )

    def _handle_follow_up(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        resolved = completeness.resolved_request or self._to_completeness_request(
            request, IntentType.evidence_follow_up
        )
        envs = list(resolved.source_envelopes)
        if not envs:
            raise ValueError("追问缺少绑定材料")
        question = resolved.follow_up_question or request.follow_up_question or ""
        if not question.strip():
            raise ValueError("追问缺少问题")
        return self._answer_from_evidence.execute(
            FollowUpRequest(question=question.strip(), source_text=envs[0].text)
        )

    def _handle_document(
        self, request: DispatchRequest, completeness: CompletenessResult
    ) -> Any:
        files = list(getattr(self, "_document_files", []) or [])
        if not files:
            raise ValueError("请前往上传页提交 PDF 或图片")
        name, data = files[0]
        lower = name.lower()
        if lower.endswith(".pdf"):
            return self._run_async(self._extract_document.extract_pdf(data, name))
        return self._run_async(self._extract_document.extract_images(files))

    @staticmethod
    def _run_async(coro: Any) -> Any:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        if loop and loop.is_running():
            # 测试/嵌套场景：新建线程跑独立循环
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, coro).result()
        return asyncio.run(coro)


__all__ = ["AnalysisDispatcher"]
