"""分析文本用例（P0-06：事实分层 + 证据校验流水线）。

固定顺序：预检 → 分类 → 抽取 → 规则复核 → 证据校验 → 通俗解释 → Report。
行业常识只进 general_references；模型不生成 Mermaid，主链路不走 MCP。
"""
from __future__ import annotations

import asyncio
import json

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
from app.domain.models.enums import EvidenceSource
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.domain.rules.engine import ProductHit, RuleEngine, RiskHit
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

            if request.demo_error == DemoErrorKind.model_timeout:
                await self._fail(task_id, "extract", ErrorCode.MODEL_TIMEOUT)
                return
            if request.demo_error == DemoErrorKind.invalid_json:
                await self._fail(task_id, "extract", ErrorCode.INVALID_MODEL_JSON)
                return
            if request.demo_error == DemoErrorKind.rate_limited:
                await self._fail(task_id, "extract", ErrorCode.RATE_LIMITED)
                return

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

            # 通俗解释：只基于已校验事实；禁止要求模型输出 Mermaid
            prompt = (
                RULE_REVIEW_SYSTEM
                + "\n禁止输出 Mermaid 或任何可执行图表代码。\n\n"
                + FINDINGS_USER_TEMPLATE.format(
                    raw_text=request.text[:2000],
                    rule_findings_json=json.dumps(
                        [{"id": f.id, "title": f.title} for f in findings],
                        ensure_ascii=False,
                    ),
                )
            )
            await self._llm.complete(prompt)
            plain = self._plain_language(extracted, findings)
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

        except TimeoutError:
            await self._fail(task_id, "extract", ErrorCode.MODEL_TIMEOUT)
        except Exception as exc:  # noqa: BLE001
            log_task("task_internal_error", task_id, err_type=type(exc).__name__)
            await self._fail(task_id, "extract", ErrorCode.INTERNAL_ERROR)

    async def _mark_stage(
        self,
        task_id: str,
        name: str,
        status: StageStatus,
        message: str,
    ) -> None:
        await asyncio.sleep(0.2)
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
            return self._rules.match_risks(text, product_type=None)
        merged: list[RiskHit] = []
        seen: set[str] = set()
        for product in products:
            for hit in self._rules.match_risks(text, product_type=product.product_id):
                if hit.pattern_id in seen:
                    continue
                seen.add(hit.pattern_id)
                merged.append(hit)
        return merged

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

    def _plain_language(self, extracted: ExtractResult, findings: list[Finding]) -> str:
        disclosed = [
            f"{p.label}={p.value}"
            for p in extracted.key_parameters
            if p.status == FactStatus.document_fact and p.value
        ]
        missing = [p.label for p in extracted.key_parameters if p.status == FactStatus.not_disclosed]
        parts = [
            f"原文已写明：{'；'.join(disclosed) if disclosed else '（无结构化参数）'}。",
            f"材料未说明：{'；'.join(missing) if missing else '无'}。",
            f"规则命中风险 {len(findings)} 条（允许为 0）。",
        ]
        return "".join(parts)

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

        return AnalysisReport(
            product_candidates=candidates,
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(text=plain, status=StageStatus.success),
            key_parameters=list(extracted.key_parameters),
            findings=findings,
            missing_disclosures=list(extracted.missing_disclosures),
            general_references=list(extracted.general_references),
            pending_questions=list(extracted.pending_questions),
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
        )
