"""分析文本用例（P0-06 + P0-RC-01：真模型通俗解释）。

固定顺序：预检 → 分类 → 抽取 → 规则复核 → 证据校验 → 通俗解释 → Report。
行业常识只进 general_references；模型不得覆盖规则 Finding；主链路不走 MCP。
"""
from __future__ import annotations

import asyncio
import json
import re

from app.config.settings import Settings
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
    AnalysisTask,
    AnalyzeTextRequest,
    DemoErrorKind,
    Evidence,
    FactStatus,
    Finding,
    FindingSeverity,
    PlainLanguage,
    ProductCandidate,
    ProductResolution,
    ProductRiskGrade,
    ProductTypeId,
    StageInfo,
)
from app.domain.models.enums import EvidenceSource, ParameterKey, ProductHint
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.domain.rules.engine import ProductHit, RiskHit, RuleEngine
from app.domain.rules.evidence import validate_and_fix_findings
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

_SEVERITY = {
    "高": FindingSeverity.high,
    "中": FindingSeverity.mid,
    "低": FindingSeverity.low,
}

PIPELINE_STAGES = (
    "preprocess",
    "classify",
    "extract",
    "rule_review",
    "evidence_validate",
    "explain",
)

_VALID_HINTS = {
    "structured_deposit",
    "loan",
    "snowball",
    "insurance",
    "fund",
}

# Demo 正式支持的产品；其它识别结果只提示范围，不做完整分析
DEMO_SUPPORTED_PRODUCTS = frozenset({"structured_deposit", "loan"})
SCOPE_PENDING_QUESTION = "当前 Demo 仅支持结构性存款和贷款，请重新选择或补充材料。"
CONFIRM_PENDING_QUESTION = "产品类型存在冲突，请确认后重新分析。"
_LOAN_TEXT_MARKERS = ("贷款", "消费贷", "借款", "等额本息", "年化利率")
_DEPOSIT_TEXT_MARKERS = ("结构性存款", "结构存款", "观察区间", "挂钩型存款")

# 已有 Finding 时，模型不得写这些「无风险」结论
_CONTRADICTION_RE = re.compile(
    r"(未发现风险|没有风险|无风险|未发现任何风险|不存在风险)",
)


class AnalyzeTextUseCase:
    """分析流水线编排：提交任务并异步跑完各阶段。

    Java 对照：Application Service / UseCase。
    业务不变量：风险 Finding 由规则决定；模型只产出通俗解释；失败时 report=None。
    """

    def __init__(
        self,
        task_store: TaskStore,
        knowledge_repository: KnowledgeRepository,
        llm_gateway: LlmGateway,
        settings: Settings,
    ) -> None:
        self._tasks = task_store
        self._knowledge = knowledge_repository
        self._llm = llm_gateway
        self._settings = settings
        self._rules = RuleEngine(knowledge_repository)
        self._extractor = FactExtractor(knowledge_repository)

    def submit(self, request: AnalyzeTextRequest) -> AnalysisTask:
        preview = request.text.strip().replace("\n", " ")[:80]
        task = AnalysisTask(
            task_status=TaskStatus.queued,
            input_text_preview=preview,
            source_text=request.text,
            stages=[
                StageInfo(name=name, status=StageStatus.not_applicable, message="等待中")
                for name in PIPELINE_STAGES
            ],
        )
        created = self._tasks.create(task)
        log_task(
            "task_created",
            created.task_id,
            text_len=len(request.text),
            demo_error=(request.demo_error.value if request.demo_error else ""),
        )
        return created

    async def run(self, task_id: str, request: AnalyzeTextRequest) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return

        task.task_status = TaskStatus.running
        self._tasks.save(task)

        try:
            await self._mark_stage(task_id, "preprocess", StageStatus.success, "输入检查通过")

            if not self._knowledge.ping():
                await self._fail(task_id, "classify", ErrorCode.KNOWLEDGE_UNAVAILABLE)
                return

            resolution = self._resolve_product_decision(request.text, request.product_hint)
            classify_msg = resolution.reason
            await self._mark_stage(task_id, "classify", StageStatus.success, classify_msg)

            if resolution.analysis_scope != AnalysisScope.supported:
                await self._finish_scope_gate(task_id, resolution, request)
                return

            product_type_id = (
                resolution.resolved_product_type.value
                if resolution.resolved_product_type is not None
                else None
            )
            assert product_type_id is not None

            extracted = self._extractor.extract(request.text, product_type_id=product_type_id)
            disclosed_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.document_fact
            )
            missing_n = sum(
                1 for p in extracted.key_parameters if p.status == FactStatus.not_disclosed
            )
            extract_status = (
                StageStatus.partial if disclosed_n and missing_n else StageStatus.success
            )
            await self._mark_stage(
                task_id,
                "extract",
                extract_status,
                f"抽取完成：原文事实 {disclosed_n}，未说明 {missing_n}",
            )

            risk_hits = self._collect_risks(request.text, product_type_id)
            await self._mark_stage(
                task_id,
                "rule_review",
                StageStatus.success,
                f"规则复核完成：{len(risk_hits)} 条候选发现（允许为 0）",
            )

            raw_findings = self._hits_to_findings(risk_hits)
            findings = validate_and_fix_findings(request.text, raw_findings)
            evidence_status = (
                StageStatus.partial
                if raw_findings and len(findings) < len(raw_findings)
                else StageStatus.success
            )
            await self._mark_stage(
                task_id,
                "evidence_validate",
                evidence_status,
                f"证据校验完成：保留 {len(findings)}/{len(raw_findings)} 条",
            )

            # 演示按钮：模型错误在 explain 阶段触发（与真网关错误阶段一致）
            if request.demo_error == DemoErrorKind.model_timeout:
                await self._fail(task_id, "explain", ErrorCode.MODEL_TIMEOUT)
                return
            if request.demo_error == DemoErrorKind.invalid_json:
                await self._fail(task_id, "explain", ErrorCode.INVALID_MODEL_JSON)
                return
            if request.demo_error == DemoErrorKind.rate_limited:
                await self._fail(task_id, "explain", ErrorCode.RATE_LIMITED)
                return

            prompt = (
                RULE_REVIEW_SYSTEM
                + "\n\n"
                + FINDINGS_USER_TEMPLATE.format(
                    raw_text=request.text[:2000],
                    rule_findings_json=json.dumps(
                        [{"id": f.id, "title": f.title} for f in findings],
                        ensure_ascii=False,
                    ),
                )
            )
            try:
                explanation = await self._llm.complete(prompt)
            except LlmTimeoutError:
                await self._fail(task_id, "explain", ErrorCode.MODEL_TIMEOUT)
                return
            except LlmRateLimitedError:
                await self._fail(task_id, "explain", ErrorCode.RATE_LIMITED)
                return
            except LlmInvalidJsonError:
                await self._fail(task_id, "explain", ErrorCode.INVALID_MODEL_JSON)
                return
            except LlmUpstreamError:
                await self._fail(task_id, "explain", ErrorCode.INTERNAL_ERROR)
                return
            except LlmGatewayError:
                await self._fail(task_id, "explain", ErrorCode.INTERNAL_ERROR)
                return

            plain = explanation.plain_language
            if findings and _CONTRADICTION_RE.search(plain):
                await self._fail(task_id, "explain", ErrorCode.INVALID_MODEL_JSON)
                return

            await self._mark_stage(task_id, "explain", StageStatus.success, "解释完成")

            task = self._tasks.get(task_id)
            if task is None:
                return
            task.report = self._build_report(
                resolution,
                extracted,
                findings,
                plain,
            )
            task.task_status = TaskStatus.completed
            task.error_code = None
            task.error_message = None
            self._tasks.save(task)
            finding_count = len(task.report.findings) if task.report is not None else 0
            log_task("task_completed", task_id, findings=finding_count)

        except Exception as exc:  # noqa: BLE001
            log_task("task_internal_error", task_id, err_type=type(exc).__name__)
            await self._fail(task_id, "explain", ErrorCode.INTERNAL_ERROR)

    async def _mark_stage(
        self,
        task_id: str,
        name: str,
        status: StageStatus,
        message: str,
    ) -> None:
        await asyncio.sleep(0.05)
        task = self._tasks.get(task_id)
        if task is None:
            return
        for stage in task.stages:
            if stage.name == name:
                stage.status = status
                stage.message = message
        self._tasks.save(task)

    async def _fail(self, task_id: str, failed_stage: str, code: ErrorCode) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        for stage in task.stages:
            if stage.name == failed_stage:
                stage.status = StageStatus.failed
                stage.message = user_message_for(code)
            elif stage.status == StageStatus.not_applicable:
                stage.message = "未执行"
        task.task_status = TaskStatus.failed
        task.error_code = code
        task.error_message = user_message_for(code)
        task.report = None
        self._tasks.save(task)
        log_task("task_failed", task_id, error_code=code.value)

    def _resolve_product_decision(
        self,
        text: str,
        product_hint: ProductHint | str | None,
    ) -> ProductResolution:
        """生成唯一产品决议；后续抽取/规则只能读此 DTO。"""
        if isinstance(product_hint, ProductHint):
            hint = product_hint
        else:
            raw = (product_hint or "auto").strip().lower()
            hint = ProductHint(raw) if raw in {e.value for e in ProductHint} else ProductHint.auto

        detected = self._rules.detect_products(text)
        # 受支持产品优先排序，避免保险等附带词抢第一
        detected_sorted = sorted(
            detected,
            key=lambda p: (
                0 if p.product_id in DEMO_SUPPORTED_PRODUCTS else 1,
                -p.confidence,
            ),
        )
        candidates = self._hits_to_candidates(detected_sorted)
        text_loan = self._text_has_markers(text, _LOAN_TEXT_MARKERS)
        text_deposit = self._text_has_markers(text, _DEPOSIT_TEXT_MARKERS)
        supported_hits = [p for p in detected_sorted if p.product_id in DEMO_SUPPORTED_PRODUCTS]

        if hint == ProductHint.structured_deposit and text_loan and not text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择结构性存款，但原文更像贷款，需确认产品类型",
            )
        if hint == ProductHint.loan and text_deposit and not text_loan:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择贷款，但原文更像结构性存款，需确认产品类型",
            )
        if hint == ProductHint.structured_deposit and text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择与原文产品信号冲突，需确认",
            )
        if hint == ProductHint.loan and text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择与原文产品信号冲突，需确认",
            )

        if hint in (ProductHint.structured_deposit, ProductHint.loan):
            resolved = ProductTypeId(hint.value)
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=resolved,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates or self._hits_to_candidates(
                    [
                        ProductHit(
                            product_id=hint.value,
                            product_name=hint.value,
                            confidence=1.0,
                            evidence_quotes=[f"手动选择:{hint.value}"],
                        )
                    ]
                ),
                reason=f"手动指定 {hint.value}",
            )

        # auto
        strong_supported = [p for p in supported_hits if p.confidence >= 0.85]
        if len(strong_supported) >= 2:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="自动识别到多个受支持产品，需确认",
            )
        if len(supported_hits) == 1 or (len(strong_supported) == 1 and len(supported_hits) >= 1):
            primary = strong_supported[0] if strong_supported else supported_hits[0]
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId(primary.product_id),
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason=f"自动识别首选 {primary.product_name}",
            )
        if text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="原文同时出现贷款与结构性存款信号，需确认",
            )
        if text_loan:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId.loan,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason="根据原文贷款信号识别为贷款",
            )
        if text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId.structured_deposit,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason="根据原文识别为结构性存款",
            )
        return ProductResolution(
            requested_hint=hint,
            resolved_product_type=None,
            analysis_scope=AnalysisScope.out_of_scope,
            candidates=candidates,
            reason="未识别到 Demo 支持的产品类型",
        )

    @staticmethod
    def _text_has_markers(text: str, markers: tuple[str, ...]) -> bool:
        return any(m in text for m in markers)

    @staticmethod
    def _hits_to_candidates(products: list[ProductHit]) -> list[ProductCandidate]:
        out: list[ProductCandidate] = []
        for p in products:
            try:
                pid = ProductTypeId(p.product_id)
            except ValueError:
                pid = ProductTypeId.unknown
            out.append(
                ProductCandidate(
                    product_type_id=pid,
                    product_type_name=p.product_name,
                    confidence=p.confidence,
                    evidence_quotes=list(p.evidence_quotes),
                )
            )
        return out

    def _collect_risks(self, text: str, product_type_id: str) -> list[RiskHit]:
        if product_type_id not in DEMO_SUPPORTED_PRODUCTS:
            return []
        return list(self._rules.match_risks(text, product_type=product_type_id))

    async def _finish_scope_gate(
        self,
        task_id: str,
        resolution: ProductResolution,
        request: AnalyzeTextRequest,
    ) -> None:
        """超范围 / 待确认：不跑抽取与规则，阶段记 not_applicable。"""
        for stage in ("extract", "rule_review", "evidence_validate"):
            await self._mark_stage(
                task_id,
                stage,
                StageStatus.not_applicable,
                "未进入完整分析",
            )

        if request.demo_error == DemoErrorKind.model_timeout:
            await self._fail(task_id, "explain", ErrorCode.MODEL_TIMEOUT)
            return
        if request.demo_error == DemoErrorKind.invalid_json:
            await self._fail(task_id, "explain", ErrorCode.INVALID_MODEL_JSON)
            return
        if request.demo_error == DemoErrorKind.rate_limited:
            await self._fail(task_id, "explain", ErrorCode.RATE_LIMITED)
            return

        await self._mark_stage(task_id, "explain", StageStatus.success, "范围说明完成")
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.report = self._build_scope_gate_report(resolution)
        task.task_status = TaskStatus.completed
        task.error_code = None
        task.error_message = None
        self._tasks.save(task)
        log_task(
            "task_completed",
            task_id,
            findings=0,
            out_of_scope=resolution.analysis_scope == AnalysisScope.out_of_scope,
            needs_confirmation=resolution.analysis_scope
            == AnalysisScope.needs_confirmation,
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
