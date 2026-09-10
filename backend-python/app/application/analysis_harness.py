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
from app.domain.llm_explanation_guard import (
    allowed_numbers_from_program,
    validate_explanation_against_program,
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
from app.domain.models.enums import EvidenceSource, ParameterKey
from app.domain.models.llm import LlmExplainRequest
from app.domain.models.verification import VerificationResult
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway
from app.domain.rules.engine import RiskHit, RuleEngine
from app.domain.rules.evidence import validate_and_fix_findings
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor
from app.domain.rules.product_resolver import (
    CONFIRM_PENDING_QUESTION,
    DEMO_SUPPORTED_PRODUCTS,
    SCOPE_PENDING_QUESTION,
    ProductResolver,
)
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM
from app.shared.enums import ErrorCode, StageStatus

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
    ) -> None:
        self._knowledge = knowledge_repository
        self._llm = llm_gateway
        self._product_resolver = product_resolver
        self._extractor = fact_extractor
        self._rules = rule_engine

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
            self._resolve_intent_adapter(ctx)

            await self._stage(ctx, HarnessStage.check_completeness, on_http_stage)
            self._check_completeness_adapter(ctx)

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
            disclosed_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.document_fact
            )
            missing_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.not_disclosed
            )
            extract_status = (
                StageStatus.partial if disclosed_n and missing_n else StageStatus.success
            )
            await self._emit_http(
                ctx,
                on_http_stage,
                "extract",
                extract_status,
                f"抽取完成：原文事实 {disclosed_n}，未说明 {missing_n}",
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
            findings = validate_and_fix_findings(ctx.source_text, raw_findings)
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

            plain = explanation.plain_language
            allowed_nums = allowed_numbers_from_program(
                findings=findings,
                key_parameters=list(extracted.key_parameters),
            )
            try:
                validate_explanation_against_program(
                    plain,
                    findings=findings,
                    allowed_numbers=allowed_nums,
                )
            except LlmInvalidJsonError:
                return await self._refuse(
                    ctx,
                    HarnessStage.build_draft,
                    ErrorCode.INVALID_MODEL_JSON,
                    "解释未通过程序校验",
                    on_http_stage,
                    failed_http_stage="explain",
                )

            await self._emit_http(
                ctx, on_http_stage, "explain", StageStatus.success, "解释完成"
            )

            await self._stage(ctx, HarnessStage.verify, on_http_stage)
            verification = self._verify_adapter(ctx)
            if not verification.can_publish:
                code = verification.error_code or ErrorCode.INTERNAL_ERROR
                return await self._refuse(
                    ctx,
                    HarnessStage.verify,
                    code,
                    "; ".join(verification.issues) or "校验未通过",
                    on_http_stage,
                    failed_http_stage="explain",
                )

            await self._stage(ctx, HarnessStage.decide_outcome, on_http_stage)
            report = self._build_report(resolution, extracted, findings, plain)
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

    def _resolve_intent_adapter(self, ctx: AnalysisContext) -> None:
        """P2-01 兼容适配器：本路径固定为单材料分析，真正意图识别见 P2-02。"""
        _ = ctx

    def _check_completeness_adapter(self, ctx: AnalysisContext) -> None:
        """P2-01 兼容适配器：CreateAnalysisRequest 已保证非空文本；完整矩阵见 P2-03。"""
        _ = ctx

    def _verify_adapter(self, ctx: AnalysisContext) -> VerificationResult:
        """P2-01 兼容适配器：解释守卫已在 BUILD_DRAFT 执行；系统校验见 P2-07。"""
        _ = ctx
        return VerificationResult(can_publish=True)

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
        report = self._build_scope_gate_report(resolution)
        ctx.report = report
        if resolution.analysis_scope == AnalysisScope.needs_confirmation:
            outcome = OutcomeStatus.clarify
        else:
            outcome = OutcomeStatus.publish_partial
        ctx.outcome = outcome
        return HarnessResult(
            context=ctx,
            outcome=outcome,
            report=report,
            error_code=None,
            stop_harness_stage=HarnessStage.resolve_product,
            stop_reason=resolution.reason,
            failed_http_stage=None,
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
        facts_payload = [
            {
                "key": p.key.value,
                "label": p.label,
                "status": p.status.value,
                "value": p.value,
                "amount": str(p.amount) if p.amount is not None else None,
            }
            for p in extracted.key_parameters
        ]
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
        user_prompt = FINDINGS_USER_TEMPLATE.format(
            facts_json=json.dumps(facts_payload, ensure_ascii=False),
            findings_json=json.dumps(findings_payload, ensure_ascii=False),
            evidence_json=json.dumps(evidence_payload, ensure_ascii=False),
        )
        return LlmExplainRequest(
            system_prompt=RULE_REVIEW_SYSTEM,
            user_prompt=user_prompt,
        )

    def _build_scope_gate_report(self, resolution: ProductResolution) -> AnalysisReport:
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
            plain_language=PlainLanguage(text=plain, status=StageStatus.success),
            key_parameters=[],
            findings=[],
            missing_disclosures=[],
            general_references=[],
            pending_questions=pending,
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
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
            plain_language=PlainLanguage(text=plain, status=StageStatus.success),
            key_parameters=list(extracted.key_parameters),
            findings=findings,
            missing_disclosures=list(extracted.missing_disclosures),
            general_references=list(extracted.general_references),
            pending_questions=list(extracted.pending_questions),
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
        )
