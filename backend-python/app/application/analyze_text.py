"""分析文本用例（P0-06 + P0-RC-01：真模型通俗解释）。

固定顺序：预检 → 分类 → 抽取 → 规则复核 → 证据校验 → 通俗解释 → Report。
行业常识只进 general_references；模型不得覆盖规则 Finding；主链路不走 MCP。
"""
from __future__ import annotations

import asyncio
import json
import re

from app.config.settings import Settings
from app.domain.models import (
    AnalysisReport,
    AnalysisTask,
    AnalyzeTextRequest,
    DemoErrorKind,
    Evidence,
    FactStatus,
    Finding,
    FindingSeverity,
    PlainLanguage,
    ProductCandidate,
    ProductRiskGrade,
    ProductTypeId,
    StageInfo,
)
from app.domain.models.enums import EvidenceSource, ParameterKey
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.domain.rules.engine import ProductHit, RuleEngine, RiskHit
from app.domain.rules.evidence import validate_and_fix_findings
from app.domain.rules.fact_extractor import ExtractResult, FactExtractor
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM
from app.domain.llm_errors import (
    LlmGatewayError,
    LlmInvalidJsonError,
    LlmRateLimitedError,
    LlmTimeoutError,
    LlmUpstreamError,
)
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

# 已有 Finding 时，模型不得写这些「无风险」结论
_CONTRADICTION_RE = re.compile(
    r"(未发现风险|没有风险|无风险|未发现任何风险|不存在风险)",
)


class AnalyzeTextUseCase:
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

            products = self._resolve_products(request.text, request.product_hint)
            if products:
                classify_msg = (
                    f"识别到 {len(products)} 个候选，首选 {products[0].product_name}"
                )
                product_type_id = products[0].product_id
            else:
                classify_msg = "未达置信度阈值，产品类型为 unknown"
                product_type_id = None
            if request.product_hint and request.product_hint != "auto":
                classify_msg = f"{classify_msg}（手动指定 {request.product_hint}）"
            await self._mark_stage(task_id, "classify", StageStatus.success, classify_msg)

            if product_type_id not in DEMO_SUPPORTED_PRODUCTS:
                await self._finish_out_of_scope(task_id, products, request)
                return

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

            risk_hits = self._collect_risks(request.text, products)
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
            task.report = self._build_report(products, extracted, findings, plain)
            task.task_status = TaskStatus.completed
            task.error_code = None
            task.error_message = None
            self._tasks.save(task)
            log_task("task_completed", task_id, findings=len(task.report.findings))

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

    def _resolve_products(self, text: str, product_hint: str | None) -> list[ProductHit]:
        """自动识别；若手动指定合法产品类型则置为首选。"""
        detected = self._rules.detect_products(text)
        hint = (product_hint or "auto").strip().lower()
        if hint in ("", "auto") or hint not in _VALID_HINTS:
            return detected

        forced: ProductHit | None = None
        for product in self._knowledge.list_products():
            if product.get("id") != hint:
                continue
            forced = ProductHit(
                product_id=str(product["id"]),
                product_name=str(product.get("name") or product["id"]),
                confidence=1.0,
                evidence_quotes=[f"手动选择:{hint}"],
            )
            break
        if forced is None:
            return detected

        rest = [p for p in detected if p.product_id != forced.product_id]
        return [forced, *rest]

    def _collect_risks(self, text: str, products) -> list[RiskHit]:
        if not products:
            return []
        primary = products[0].product_id
        if primary not in DEMO_SUPPORTED_PRODUCTS:
            return []
        merged: list[RiskHit] = []
        seen: set[str] = set()
        for product in products:
            if product.product_id not in DEMO_SUPPORTED_PRODUCTS:
                continue
            for hit in self._rules.match_risks(text, product_type=product.product_id):
                if hit.pattern_id in seen:
                    continue
                seen.add(hit.pattern_id)
                merged.append(hit)
        return merged

    async def _finish_out_of_scope(
        self,
        task_id: str,
        products: list[ProductHit],
        request: AnalyzeTextRequest,
    ) -> None:
        """unknown / 非首批产品：不跑全量规则，只提示 Demo 范围。"""
        await self._mark_stage(task_id, "extract", StageStatus.success, "不在支持范围，跳过参数抽取")
        await self._mark_stage(task_id, "rule_review", StageStatus.success, "不在支持范围，跳过规则复核")
        await self._mark_stage(
            task_id, "evidence_validate", StageStatus.success, "不在支持范围，跳过证据校验"
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

        await self._mark_stage(task_id, "explain", StageStatus.success, "范围提示完成")
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.report = self._build_out_of_scope_report(products)
        task.task_status = TaskStatus.completed
        task.error_code = None
        task.error_message = None
        self._tasks.save(task)
        log_task("task_completed", task_id, findings=0, out_of_scope=True)

    def _build_out_of_scope_report(self, products: list[ProductHit]) -> AnalysisReport:
        candidates: list[ProductCandidate] = []
        if not products:
            candidates = [
                ProductCandidate(
                    product_type_id=ProductTypeId.unknown,
                    product_type_name="未识别",
                    confidence=0.0,
                    evidence_quotes=[],
                )
            ]
        else:
            primary = products[0]
            try:
                pid = ProductTypeId(primary.product_id)
            except ValueError:
                pid = ProductTypeId.unknown
            name = primary.product_name
            if "out of scope" not in name.lower():
                name = f"{name}（out of scope）"
            candidates = [
                ProductCandidate(
                    product_type_id=pid,
                    product_type_name=name,
                    confidence=primary.confidence,
                    evidence_quotes=list(primary.evidence_quotes),
                )
            ]

        return AnalysisReport(
            product_candidates=candidates,
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(
                text="当前材料不在 Demo 支持范围内，未做完整风险分析。",
                status=StageStatus.success,
            ),
            key_parameters=[],
            findings=[],
            missing_disclosures=[],
            general_references=[],
            pending_questions=[SCOPE_PENDING_QUESTION],
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
        products,
        extracted: ExtractResult,
        findings: list[Finding],
        plain: str,
    ) -> AnalysisReport:
        candidates: list[ProductCandidate] = []
        for p in products:
            try:
                pid = ProductTypeId(p.product_id)
            except ValueError:
                pid = ProductTypeId.unknown
            candidates.append(
                ProductCandidate(
                    product_type_id=pid,
                    product_type_name=p.product_name,
                    confidence=p.confidence,
                    evidence_quotes=list(p.evidence_quotes),
                )
            )
        if not candidates:
            candidates = [
                ProductCandidate(
                    product_type_id=ProductTypeId.unknown,
                    product_type_name="未识别",
                    confidence=0.0,
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
            product_risk_grade=risk_grade,
            plain_language=PlainLanguage(text=plain, status=StageStatus.success),
            key_parameters=list(extracted.key_parameters),
            findings=findings,
            missing_disclosures=list(extracted.missing_disclosures),
            general_references=list(extracted.general_references),
            pending_questions=list(extracted.pending_questions),
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
        )
