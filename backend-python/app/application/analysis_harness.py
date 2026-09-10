"""分析流程 Harness（P2-01）。

用途：用显式阶段顺序编排单材料分析，并在停止条件处退出。
输入：AnalysisContext（任务 ID、原文、产品提示）。
输出：HarnessResult（Outcome、报告或 error_code、停止阶段）。
不变量：不依赖 FastAPI/HTTPException/Vue/MCP；后续未实现阶段用兼容适配器且显式标注。
失败方式：OutcomeStatus.refuse + failed_http_stage；
未知异常按当前 Harness 阶段映射，不一律标 explain。

Java 对照：Application Orchestrator / Workflow 编排器（非规则引擎、非 Agent 框架）。
"""
from __future__ import annotations

import json
from collections.abc import Awaitable, Callable

from app.domain.llm_errors import (
    LlmGatewayError,
    LlmInvalidJsonError,
    LlmRateLimitedError,
    LlmTimeoutError,
    LlmUpstreamError,
)
from app.domain.models import (
    AnalysisReport,
    AnalysisScope,
    Evidence,
    FactStatus,
    Finding,
    FindingSeverity,
    PlainLanguage,
    ProductCandidate,
    ProductResolution,
    ProductRiskGrade,
    ProductTypeId,
)
from app.domain.models.analysis_context import (
    HARNESS_TO_HTTP_STAGE,
    AnalysisContext,
    HarnessResult,
    HarnessStage,
    HttpStageUpdate,
    OutcomeStatus,
)
from app.domain.models.completeness import CompletenessCheckRequest
from app.domain.models.enums import EvidenceSource, ParameterKey
from app.domain.models.intent import (
    INTENT_USE_CASE_MAP,
    DecisionSource,
    DecisionStatus,
    IntentDecision,
    IntentResolveRequest,
    IntentType,
    SourceEnvelope,
)
from app.domain.models.llm import LlmExplainRequest
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway
from app.domain.rules.apply_fact_corrections import (
    active_financial_facts,
    apply_corrections_to_ledger,
)
from app.domain.rules.completeness_checker import CompletenessChecker
from app.domain.rules.engine import RiskHit, RuleEngine
from app.domain.rules.evidence import validate_and_fix_findings
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor
from app.domain.rules.intent_resolver import IntentResolver
from app.domain.rules.product_resolver import (
    CONFIRM_PENDING_QUESTION,
    DEMO_SUPPORTED_PRODUCTS,
    SCOPE_PENDING_QUESTION,
    ProductResolver,
)
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM
from app.domain.validation.program_plain_language import render_program_plain_language
from app.domain.validation.publication_gate import (
    decide_clarify,
    decide_publish,
    decide_publish_partial,
    decide_refuse,
)
from app.domain.validation.publication_service import PublicationService
from app.shared.enums import ErrorCode, StageStatus, user_message_for

_SEVERITY = {
    "高": FindingSeverity.high,
    "中": FindingSeverity.mid,
    "低": FindingSeverity.low,
}

StageEmitter = Callable[[str, StageStatus, str], Awaitable[None]]
ResolutionEmitter = Callable[[ProductResolution], Awaitable[None]]


class AnalysisHarness:
    """单材料分析流程总控。"""

    def __init__(
        self,
        knowledge_repository: KnowledgeRepository,
        llm_gateway: LlmGateway,
        product_resolver: ProductResolver,
        fact_extractor: FactExtractor,
        rule_engine: RuleEngine,
        intent_resolver: IntentResolver | None = None,
        completeness_checker: CompletenessChecker | None = None,
        publication: PublicationService | None = None,
    ) -> None:
        self._knowledge = knowledge_repository
        self._llm = llm_gateway
        self._product_resolver = product_resolver
        self._extractor = fact_extractor
        self._rules = rule_engine
        self._intent_resolver = intent_resolver or IntentResolver()
        self._completeness = completeness_checker or CompletenessChecker()
        self._publication = publication or PublicationService()

    async def run(
        self,
        ctx: AnalysisContext,
        *,
        on_http_stage: StageEmitter | None = None,
        on_resolution: ResolutionEmitter | None = None,
    ) -> HarnessResult:
        """执行固定阶段序列；遇停止条件立即返回。"""
        try:
            await self._stage(ctx, HarnessStage.receive, on_http_stage)
            await self._emit_http(
                ctx, on_http_stage, "preprocess", StageStatus.success, "输入检查通过"
            )

            await self._stage(ctx, HarnessStage.normalize, on_http_stage)
            # normalize：请求层已 strip/校验；此处仅占位保持阶段链完整

            await self._stage(ctx, HarnessStage.resolve_intent, on_http_stage)
            intent_stop = self._resolve_intent(ctx)
            if intent_stop is not None:
                return intent_stop

            await self._stage(ctx, HarnessStage.check_completeness, on_http_stage)
            completeness_stop = self._check_completeness(ctx)
            if completeness_stop is not None:
                return completeness_stop

            if not self._knowledge.ping():
                return await self._refuse(
                    ctx,
                    HarnessStage.resolve_product,
                    ErrorCode.KNOWLEDGE_UNAVAILABLE,
                    "知识库不可用",
                    on_http_stage,
                    failed_http_stage="classify",
                )

            await self._stage(ctx, HarnessStage.resolve_product, on_http_stage)
            resolution = self._product_resolver.resolve(ctx.source_text, ctx.product_hint)
            ctx.product_resolution = resolution
            if on_resolution is not None:
                await on_resolution(resolution)
                ctx.resolution_persisted = True
            await self._emit_http(
                ctx, on_http_stage, "classify", StageStatus.success, resolution.reason
            )

            if resolution.analysis_scope != AnalysisScope.supported:
                return await self._finish_scope_gate(ctx, resolution, on_http_stage)

            product_type_id = (
                resolution.resolved_product_type.value
                if resolution.resolved_product_type is not None
                else None
            )
            assert product_type_id is not None

            await self._stage(ctx, HarnessStage.extract_facts, on_http_stage)
            extracted = self._extractor.extract(
                ctx.source_text, product_type_id=product_type_id
            )
            # P2-09 / P2-RC-04：有效纠错同步 KP + FF；USER_ASSERTED 不伪造原文证据
            if ctx.corrections:
                from dataclasses import replace

                patched_params, patched_facts = apply_corrections_to_ledger(
                    list(extracted.key_parameters),
                    list(extracted.financial_facts),
                    list(ctx.corrections),
                )
                extracted = replace(
                    extracted,
                    key_parameters=patched_params,
                    financial_facts=patched_facts,
                )
                asserted = {
                    c.parameter_key
                    for c in ctx.corrections
                    if c.parameter_key is not None
                }
                if asserted:
                    extracted = replace(
                        extracted,
                        missing_disclosures=[
                            m
                            for m in extracted.missing_disclosures
                            if m.key not in asserted
                        ],
                    )
            disclosed_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.document_fact
            )
            missing_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.not_disclosed
            )
            user_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.user_asserted
            )
            extract_status = (
                StageStatus.partial if disclosed_n and missing_n else StageStatus.success
            )
            extract_msg = f"抽取完成：原文事实 {disclosed_n}，未说明 {missing_n}"
            if user_n:
                extract_msg += f"，用户声明 {user_n}"
            await self._emit_http(
                ctx,
                on_http_stage,
                "extract",
                extract_status,
                extract_msg,
            )

            await self._stage(ctx, HarnessStage.apply_rules, on_http_stage)
            risk_hits = self._collect_risks(ctx.source_text, product_type_id)
            await self._emit_http(
                ctx,
                on_http_stage,
                "rule_review",
                StageStatus.success,
                f"规则复核完成：{len(risk_hits)} 条候选发现（允许为 0）",
            )
            raw_findings = self._hits_to_findings(risk_hits)
            findings, dropped_finding_ids = validate_and_fix_findings(
                ctx.source_text, raw_findings
            )
            rule_hit_count = len(raw_findings)
            evidence_status = (
                StageStatus.partial
                if raw_findings and len(findings) < len(raw_findings)
                else StageStatus.success
            )
            await self._emit_http(
                ctx,
                on_http_stage,
                "evidence_validate",
                evidence_status,
                f"证据校验完成：保留 {len(findings)}/{len(raw_findings)} 条",
            )

            await self._stage(ctx, HarnessStage.build_draft, on_http_stage)
            if ctx.demo_error is not None:
                demo_code = self._demo_error_code(ctx)
                if demo_code is not None:
                    return await self._refuse(
                        ctx,
                        HarnessStage.build_draft,
                        demo_code,
                        "演示错误开关触发",
                        on_http_stage,
                        failed_http_stage="explain",
                    )

            explain_req = self._build_explain_request(extracted, findings)
            try:
                explanation = await self._llm.complete(explain_req)
            except LlmTimeoutError:
                return await self._refuse(
                    ctx,
                    HarnessStage.build_draft,
                    ErrorCode.MODEL_TIMEOUT,
                    "模型超时",
                    on_http_stage,
                    failed_http_stage="explain",
                )
            except LlmRateLimitedError:
                return await self._refuse(
                    ctx,
                    HarnessStage.build_draft,
                    ErrorCode.RATE_LIMITED,
                    "模型限流",
                    on_http_stage,
                    failed_http_stage="explain",
                )
            except LlmInvalidJsonError:
                return await self._refuse(
                    ctx,
                    HarnessStage.build_draft,
                    ErrorCode.INVALID_MODEL_JSON,
                    "模型非法 JSON",
                    on_http_stage,
                    failed_http_stage="explain",
                )
            except (LlmUpstreamError, LlmGatewayError):
                return await self._refuse(
                    ctx,
                    HarnessStage.build_draft,
                    ErrorCode.INTERNAL_ERROR,
                    "模型网关错误",
                    on_http_stage,
                    failed_http_stage="explain",
                )

            plain = explanation.render_plain_language()
            await self._emit_http(
                ctx, on_http_stage, "explain", StageStatus.success, "模型草稿已解析"
            )

            await self._stage(ctx, HarnessStage.verify, on_http_stage)
            # P2-07 / P2-RC-06：经 PublicationService 跑确定性门禁（不调用大模型）
            verification = self._publication.verify_single_analysis(
                source_text=ctx.source_text,
                draft=explanation,
                plain=plain,
                findings=findings,
                key_parameters=list(extracted.key_parameters),
                financial_facts=list(active_financial_facts(extracted.financial_facts)),
                allowed_fact_ids=list(explain_req.allowed_fact_ids),
                allowed_finding_ids=list(explain_req.allowed_finding_ids),
                allowed_knowledge_ids=list(explain_req.allowed_knowledge_ids),
                dropped_finding_ids=dropped_finding_ids,
                rule_hit_count=rule_hit_count,
            )
            if not verification.can_publish:
                decision = self._publication.decide_from_verification(verification)
                program_bits = render_program_plain_language(
                    findings=findings,
                    financial_facts=list(extracted.financial_facts),
                    key_parameters=list(extracted.key_parameters),
                )
                plain_partial = (
                    f"【部分结果】{decision.user_reason}\n"
                    "以下仅包含程序已确认的事实与风险；"
                    "模型通俗解释未通过校验，未作为确定说明发布。\n"
                    f"{program_bits}"
                )
                await self._emit_http(
                    ctx,
                    on_http_stage,
                    "explain",
                    StageStatus.partial,
                    decision.user_reason,
                )
                await self._stage(ctx, HarnessStage.decide_outcome, on_http_stage)
                report = self._build_report(
                    resolution,
                    extracted,
                    findings,
                    plain_partial,
                    plain_status=StageStatus.partial,
                    publication=decision,
                )
                ctx.report = report
                ctx.outcome = OutcomeStatus.publish_partial
                ctx.error_code = decision.reason_code
                ctx.stop_reason = decision.user_reason
                return HarnessResult(
                    context=ctx,
                    outcome=OutcomeStatus.publish_partial,
                    report=report,
                    error_code=decision.reason_code,
                    stop_harness_stage=HarnessStage.decide_outcome,
                    stop_reason=decision.user_reason,
                    failed_http_stage=None,
                    publication=decision,
                )

            await self._stage(ctx, HarnessStage.decide_outcome, on_http_stage)
            decision = decide_publish()
            # 完整发布：用户可见白话由程序模板生成，不采信未验证模型自由文案
            program_plain = render_program_plain_language(
                findings=findings,
                financial_facts=list(extracted.financial_facts),
                key_parameters=list(extracted.key_parameters),
            )
            report = self._build_report(
                resolution,
                extracted,
                findings,
                program_plain,
                publication=decision,
            )
            ctx.report = report
            outcome = OutcomeStatus.publish
            ctx.outcome = outcome
            return HarnessResult(
                context=ctx,
                outcome=outcome,
                report=report,
                error_code=None,
                stop_harness_stage=HarnessStage.decide_outcome,
                stop_reason="分析完成",
                failed_http_stage=None,
                publication=decision,
            )
        except Exception as exc:  # noqa: BLE001
            stage = ctx.current_stage
            http_stage = HARNESS_TO_HTTP_STAGE.get(stage, "explain")
            # 规则/抽取等程序异常：映射真实阶段，不用 explain 兜底
            if stage in (HarnessStage.extract_facts, HarnessStage.apply_rules):
                code = ErrorCode.RULE_FAILED
            else:
                code = ErrorCode.INTERNAL_ERROR
            return await self._refuse(
                ctx,
                stage,
                code,
                f"内部异常: {type(exc).__name__}",
                on_http_stage,
                failed_http_stage=http_stage,
            )

    def _resolve_intent(self, ctx: AnalysisContext) -> HarnessResult | None:
        """P2-02 / P2-RC-05：解析意图；单材料 Harness 仅接受 single_analysis。

        页面「开始分析」提交带 explicit_intent 时直接标记 explicit_ui，
        不再用空 user_query 走规则默认假装完成意图识别。
        材料正文中的命令不参与解析。
        """
        if ctx.intent_decision is not None:
            decision = ctx.intent_decision
        elif ctx.explicit_intent is not None:
            # 明确页面提交：直接构造 explicit_ui 决议
            if ctx.explicit_intent == IntentType.single_analysis:
                decision = IntentDecision(
                    intent=IntentType.single_analysis,
                    status=DecisionStatus.resolved,
                    source=DecisionSource.explicit_ui,
                    rationale=[
                        "来自明确页面操作（开始分析），忽略材料内指令",
                    ],
                    use_case_key=INTENT_USE_CASE_MAP[IntentType.single_analysis],
                )
            else:
                decision = self._intent_resolver.resolve(
                    IntentResolveRequest(
                        explicit_intent=ctx.explicit_intent,
                        source_envelopes=[
                            SourceEnvelope(
                                source_id="src_main", text=ctx.source_text
                            )
                        ],
                    )
                )
            ctx.intent_decision = decision
        else:
            # 无显式意图：不假装完成；返回澄清
            decision = IntentDecision(
                intent=IntentType.ambiguous,
                status=DecisionStatus.needs_clarification,
                source=DecisionSource.rule,
                rationale=["单材料入口缺少显式页面意图"],
                missing=["请从首页点击「开始分析」"],
            )
            ctx.intent_decision = decision

        if (
            decision.status == DecisionStatus.resolved
            and decision.intent == IntentType.single_analysis
        ):
            return None

        if decision.status == DecisionStatus.needs_clarification:
            prompts = [o.label for o in decision.clarifying_options][:3]
            if not prompts and decision.rationale:
                prompts = list(decision.rationale)[:3]
            reason = "; ".join(decision.rationale) or "意图需澄清"
            decision_pub = decide_clarify(
                reason_code=ErrorCode.INTENT_AMBIGUOUS,
                user_reason=reason,
            )
            report = AnalysisReport(
                product_candidates=[],
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                scope_reason=reason,
                product_risk_grade=ProductRiskGrade(
                    value=None,
                    status=FactStatus.not_disclosed,
                    note="原文未明确风险等级",
                ),
                plain_language=PlainLanguage(text=reason, status=StageStatus.partial),
                key_parameters=[],
                findings=[],
                missing_disclosures=[],
                general_references=[],
                pending_questions=prompts,
                disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
                publication=decision_pub,
            )
            ctx.report = report
            ctx.outcome = OutcomeStatus.clarify
            ctx.stop_reason = reason
            return HarnessResult(
                context=ctx,
                outcome=OutcomeStatus.clarify,
                report=report,
                error_code=ErrorCode.INTENT_AMBIGUOUS,
                stop_harness_stage=HarnessStage.resolve_intent,
                stop_reason=reason,
                failed_http_stage=None,
                publication=decision_pub,
            )

        # 其他意图或 rejected：本 Harness 只跑单材料分析，显式拒绝不继续抽取
        refuse_pub = decide_refuse(
            reason_code=ErrorCode.UNSUPPORTED_REQUEST,
            user_reason=(
                f"当前入口不支持意图「{decision.intent.value}」，"
                "请从对应页面发起（双材料对照 / 计算 / 追问等）。"
            ),
            next_steps=[
                "返回首页选择正确的分析入口",
                "单材料分析请保持当前入口",
            ],
        )
        ctx.outcome = OutcomeStatus.refuse
        ctx.error_code = ErrorCode.UNSUPPORTED_REQUEST
        ctx.stop_reason = refuse_pub.user_reason
        ctx.report = None
        return HarnessResult(
            context=ctx,
            outcome=OutcomeStatus.refuse,
            report=None,
            error_code=ErrorCode.UNSUPPORTED_REQUEST,
            stop_harness_stage=HarnessStage.resolve_intent,
            stop_reason=refuse_pub.user_reason,
            failed_http_stage="preprocess",
            publication=refuse_pub,
        )

    def _check_completeness(self, ctx: AnalysisContext) -> HarnessResult | None:
        """P2-03：完整性检查；can_continue=false 时停止，不进入抽取/规则/LLM。"""
        from app.domain.rules.clarification_catalog import ClarificationRejected

        try:
            result = self._completeness.check(
                CompletenessCheckRequest(
                    intent=IntentType.single_analysis,
                    source_envelopes=[
                        SourceEnvelope(source_id="src_main", text=ctx.source_text)
                    ],
                    product_hint=ctx.product_hint,
                    clarification_answers=list(ctx.clarification_answers),
                )
            )
        except ClarificationRejected as exc:
            decision_pub = decide_clarify(
                reason_code=ErrorCode.CLARIFICATION_INVALID,
                user_reason=exc.message,
                next_steps=["请按页面选项或规范格式重新回答追问"],
            )
            report = AnalysisReport(
                product_candidates=[],
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                scope_reason=exc.message,
                product_risk_grade=ProductRiskGrade(
                    value=None,
                    status=FactStatus.not_disclosed,
                    note="原文未明确风险等级",
                ),
                plain_language=PlainLanguage(
                    text=exc.message, status=StageStatus.partial
                ),
                key_parameters=[],
                findings=[],
                missing_disclosures=[],
                general_references=[],
                pending_questions=[exc.message],
                disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
                publication=decision_pub,
            )
            ctx.report = report
            ctx.outcome = OutcomeStatus.clarify
            ctx.stop_reason = exc.message
            return HarnessResult(
                context=ctx,
                outcome=OutcomeStatus.clarify,
                report=report,
                error_code=ErrorCode.CLARIFICATION_INVALID,
                error_message=exc.message,
            )

        # 使用规范化后的请求写回上下文
        if result.resolved_request is not None:
            ctx.product_hint = result.resolved_request.product_hint
            ctx.clarification_answers = list(result.answered)
        ctx.completeness_result = result
        if result.can_continue:
            return None

        prompts = [q.prompt for q in result.questions]
        plain = result.summary or "请先确认以下问题后再分析。"
        decision_pub = decide_clarify(
            reason_code=ErrorCode.INPUT_INCOMPLETE,
            user_reason=plain,
            next_steps=[
                "请回答页面上的追问后继续",
                "或返回首页重新粘贴更完整的材料",
            ],
        )
        report = AnalysisReport(
            product_candidates=[],
            resolved_product_type=None,
            analysis_scope=AnalysisScope.needs_confirmation,
            scope_reason=result.summary,
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(text=plain, status=StageStatus.partial),
            key_parameters=[],
            findings=[],
            missing_disclosures=[],
            general_references=[],
            pending_questions=prompts,
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
            publication=decision_pub,
        )
        ctx.report = report
        ctx.outcome = OutcomeStatus.clarify
        ctx.error_code = ErrorCode.INPUT_INCOMPLETE
        ctx.stop_reason = result.summary
        return HarnessResult(
            context=ctx,
            outcome=OutcomeStatus.clarify,
            report=report,
            error_code=ErrorCode.INPUT_INCOMPLETE,
            stop_harness_stage=HarnessStage.check_completeness,
            stop_reason=result.summary,
            failed_http_stage=None,
            publication=decision_pub,
        )

    async def _finish_scope_gate(
        self,
        ctx: AnalysisContext,
        resolution: ProductResolution,
        on_http_stage: StageEmitter | None,
    ) -> HarnessResult:
        for stage in ("extract", "rule_review", "evidence_validate"):
            await self._emit_http(
                ctx, on_http_stage, stage, StageStatus.not_applicable, "未进入完整分析"
            )

        demo_code = self._demo_error_code(ctx)
        if demo_code is not None:
            return await self._refuse(
                ctx,
                HarnessStage.build_draft,
                demo_code,
                "演示错误开关触发（范围门）",
                on_http_stage,
                failed_http_stage="explain",
            )

        await self._emit_http(
            ctx, on_http_stage, "explain", StageStatus.success, "范围说明完成"
        )
        if resolution.analysis_scope == AnalysisScope.needs_confirmation:
            decision = decide_clarify(
                reason_code=ErrorCode.PRODUCT_CONFLICT,
                user_reason=resolution.reason or "产品类型存在冲突，请确认后继续",
            )
            outcome = OutcomeStatus.clarify
        else:
            decision = decide_publish_partial(
                reason_code=ErrorCode.UNSUPPORTED_REQUEST,
                user_reason=resolution.reason
                or "当前 Demo 未分析该产品，请选择结构性存款或贷款",
                next_steps=[
                    "请选择结构性存款或贷款后重新分析",
                    "系统未进入完整风险分析，不等于产品安全",
                ],
            )
            outcome = OutcomeStatus.publish_partial
        report = self._build_scope_gate_report(resolution, publication=decision)
        ctx.report = report
        ctx.outcome = outcome
        ctx.error_code = decision.reason_code
        return HarnessResult(
            context=ctx,
            outcome=outcome,
            report=report,
            error_code=decision.reason_code,
            stop_harness_stage=HarnessStage.resolve_product,
            stop_reason=resolution.reason,
            failed_http_stage=None,
            publication=decision,
        )

    async def _refuse(
        self,
        ctx: AnalysisContext,
        harness_stage: HarnessStage,
        code: ErrorCode,
        reason: str,
        on_http_stage: StageEmitter | None,
        *,
        failed_http_stage: str,
    ) -> HarnessResult:
        decision = decide_refuse(
            reason_code=code,
            user_reason=user_message_for(code),
            next_steps=[
                "可返回首页修改材料后重试",
                "失败不等于产品安全或无风险",
            ],
        )
        ctx.current_stage = harness_stage
        ctx.outcome = OutcomeStatus.refuse
        ctx.error_code = code
        ctx.stop_reason = reason
        ctx.report = None
        await self._emit_http(
            ctx,
            on_http_stage,
            failed_http_stage,
            StageStatus.failed,
            reason,
        )
        return HarnessResult(
            context=ctx,
            outcome=OutcomeStatus.refuse,
            report=None,
            error_code=code,
            stop_harness_stage=harness_stage,
            stop_reason=reason,
            failed_http_stage=failed_http_stage,
            publication=decision,
        )

    async def _stage(
        self,
        ctx: AnalysisContext,
        stage: HarnessStage,
        on_http_stage: StageEmitter | None,
    ) -> None:
        ctx.current_stage = stage
        _ = on_http_stage

    async def _emit_http(
        self,
        ctx: AnalysisContext,
        on_http_stage: StageEmitter | None,
        name: str,
        status: StageStatus,
        message: str,
    ) -> None:
        ctx.http_stage_updates.append(
            HttpStageUpdate(name=name, status=status, message=message)
        )
        if on_http_stage is not None:
            await on_http_stage(name, status, message)

    @staticmethod
    def _demo_error_code(ctx: AnalysisContext) -> ErrorCode | None:
        from app.domain.models.enums import DemoErrorKind

        if ctx.demo_error == DemoErrorKind.model_timeout:
            return ErrorCode.MODEL_TIMEOUT
        if ctx.demo_error == DemoErrorKind.invalid_json:
            return ErrorCode.INVALID_MODEL_JSON
        if ctx.demo_error == DemoErrorKind.rate_limited:
            return ErrorCode.RATE_LIMITED
        return None

    def _collect_risks(self, text: str, product_type_id: str) -> list[RiskHit]:
        if product_type_id not in DEMO_SUPPORTED_PRODUCTS:
            return []
        return list(self._rules.match_risks(text, product_type=product_type_id))

    def _build_explain_request(
        self,
        extracted: ExtractResult,
        findings: list[Finding],
    ) -> LlmExplainRequest:
        fact_ids: list[str] = []
        facts_payload: list[dict] = []
        for p in extracted.key_parameters:
            fid = f"param:{p.key.value}"
            fact_ids.append(fid)
            facts_payload.append(
                {
                    "fact_id": fid,
                    "key": p.key.value,
                    "label": p.label,
                    "status": p.status.value,
                    "value": p.value,
                    "amount": str(p.amount) if p.amount is not None else None,
                }
            )
        for ff in active_financial_facts(extracted.financial_facts):
            fact_ids.append(ff.fact_id)
            facts_payload.append(
                {
                    "fact_id": ff.fact_id,
                    "field_key": ff.field_key,
                    "raw_value": ff.raw_value,
                    "normalized_value": ff.normalized_value,
                    "status": ff.status.value,
                    "qualifiers": list(ff.qualifiers),
                    "condition_text": ff.condition_text,
                }
            )
        finding_ids = [f.id for f in findings]
        findings_payload = [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.finding_severity.value,
                "explanation": f.explanation,
            }
            for f in findings
        ]
        evidence_payload = [
            {
                "finding_id": f.id,
                "quote": ev.quote,
                "start": ev.start,
                "end": ev.end,
            }
            for f in findings
            for ev in f.evidence
        ]
        knowledge_ids: list[str] = []
        for ref in extracted.general_references:
            kid = ref.source.strip() or "knowledge:general"
            if kid not in knowledge_ids:
                knowledge_ids.append(kid)
        if not knowledge_ids:
            knowledge_ids = ["knowledge:demo"]
        # 去重保序
        seen_f: set[str] = set()
        unique_fact_ids: list[str] = []
        for fid in fact_ids:
            if fid in seen_f:
                continue
            seen_f.add(fid)
            unique_fact_ids.append(fid)

        user_prompt = FINDINGS_USER_TEMPLATE.format(
            allowed_fact_ids_json=json.dumps(unique_fact_ids, ensure_ascii=False),
            allowed_finding_ids_json=json.dumps(finding_ids, ensure_ascii=False),
            allowed_knowledge_ids_json=json.dumps(knowledge_ids, ensure_ascii=False),
            facts_json=json.dumps(facts_payload, ensure_ascii=False),
            findings_json=json.dumps(findings_payload, ensure_ascii=False),
            evidence_json=json.dumps(evidence_payload, ensure_ascii=False),
        )
        return LlmExplainRequest(
            system_prompt=RULE_REVIEW_SYSTEM,
            user_prompt=user_prompt,
            allowed_fact_ids=unique_fact_ids,
            allowed_finding_ids=finding_ids,
            allowed_knowledge_ids=knowledge_ids,
        )

    def _build_scope_gate_report(
        self,
        resolution: ProductResolution,
        *,
        publication=None,
    ) -> AnalysisReport:
        if resolution.analysis_scope == AnalysisScope.needs_confirmation:
            plain = "产品类型存在冲突，请确认后重新分析。本次未做完整风险分析。"
            pending = [CONFIRM_PENDING_QUESTION]
        else:
            plain = "当前 Demo 未分析该产品，请选择结构性存款或贷款。本次未做完整风险分析。"
            pending = [SCOPE_PENDING_QUESTION]
        candidates = list(resolution.candidates)
        if not candidates:
            candidates = [
                ProductCandidate(
                    product_type_id=ProductTypeId.unknown,
                    product_type_name="未识别",
                    confidence=0.0,
                    evidence_quotes=[],
                )
            ]
        elif resolution.analysis_scope == AnalysisScope.out_of_scope:
            tagged: list[ProductCandidate] = []
            for c in candidates:
                name = c.product_type_name
                if "out of scope" not in name.lower():
                    name = f"{name}（out of scope）"
                tagged.append(
                    ProductCandidate(
                        product_type_id=c.product_type_id,
                        product_type_name=name,
                        confidence=c.confidence,
                        evidence_quotes=list(c.evidence_quotes),
                    )
                )
            candidates = tagged
        return AnalysisReport(
            product_candidates=candidates,
            resolved_product_type=resolution.resolved_product_type,
            analysis_scope=resolution.analysis_scope,
            scope_reason=resolution.reason,
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(text=plain, status=StageStatus.partial),
            key_parameters=[],
            findings=[],
            missing_disclosures=[],
            general_references=[],
            pending_questions=pending,
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
            publication=publication,
        )

    def _hits_to_findings(self, risk_hits: list[RiskHit]) -> list[Finding]:
        findings: list[Finding] = []
        for hit in risk_hits:
            findings.append(
                Finding(
                    id=hit.pattern_id,
                    title=hit.name,
                    finding_severity=_SEVERITY.get(hit.risk_level, FindingSeverity.mid),
                    explanation=hit.explanation,
                    evidence=[
                        Evidence(
                            quote=hit.quote,
                            start=hit.start,
                            end=hit.end,
                            source=EvidenceSource.input_text,
                        )
                    ],
                    rule_or_knowledge_id=hit.pattern_id,
                    confidence=hit.confidence,
                    needs_review=False,
                )
            )
        return findings

    def _build_report(
        self,
        resolution: ProductResolution,
        extracted: ExtractResult,
        findings: list[Finding],
        plain: str,
        *,
        plain_status: StageStatus = StageStatus.success,
        publication=None,
    ) -> AnalysisReport:
        candidates = list(resolution.candidates)
        if not candidates and resolution.resolved_product_type is not None:
            candidates = [
                ProductCandidate(
                    product_type_id=resolution.resolved_product_type,
                    product_type_name=resolution.resolved_product_type.value,
                    confidence=1.0,
                    evidence_quotes=[],
                )
            ]

        grade_param = next(
            (
                p
                for p in extracted.key_parameters
                if p.key == ParameterKey.product_risk_grade
            ),
            None,
        )
        if grade_param and grade_param.status == FactStatus.document_fact and grade_param.value:
            risk_grade = ProductRiskGrade(
                value=grade_param.value,
                status=FactStatus.document_fact,
                note="",
            )
        else:
            risk_grade = ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            )

        return AnalysisReport(
            product_candidates=candidates,
            resolved_product_type=resolution.resolved_product_type,
            analysis_scope=AnalysisScope.supported,
            scope_reason=resolution.reason,
            product_risk_grade=risk_grade,
            plain_language=PlainLanguage(text=plain, status=plain_status),
            key_parameters=list(extracted.key_parameters),
            financial_facts=list(extracted.financial_facts),
            findings=findings,
            missing_disclosures=list(extracted.missing_disclosures),
            general_references=list(extracted.general_references),
            pending_questions=list(extracted.pending_questions),
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
            publication=publication,
        )
