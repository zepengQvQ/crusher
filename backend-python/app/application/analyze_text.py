"""分析文本用例（P0-05：规则复核接入）。

模型只做通俗解释占位；产品识别与风险命中由 RuleEngine 确定性完成。
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
    GeneralReference,
    KeyParameter,
    MissingDisclosure,
    ParameterKey,
    PlainLanguage,
    ProductCandidate,
    ProductRiskGrade,
    ProductTypeId,
    StageInfo,
)
from app.domain.models.enums import EvidenceSource
from app.domain.ports.protocols import KnowledgeRepository, LlmGateway, TaskStore
from app.domain.rules.engine import RuleEngine, RiskHit
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM
from app.shared.enums import ErrorCode, StageStatus, TaskStatus, user_message_for
from app.shared.logging_utils import log_task

_SEVERITY = {
    "高": FindingSeverity.high,
    "中": FindingSeverity.mid,
    "低": FindingSeverity.low,
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

    def submit(self, request: AnalyzeTextRequest) -> AnalysisTask:
        preview = request.text.strip().replace("\n", " ")[:80]
        task = AnalysisTask(
            task_status=TaskStatus.queued,
            input_text_preview=preview,
            stages=[
                StageInfo(name="preprocess", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="classify", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="extract", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="rule_review", status=StageStatus.not_applicable, message="等待中"),
                StageInfo(name="explain", status=StageStatus.not_applicable, message="等待中"),
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

            products = self._rules.detect_products(request.text)
            if products:
                top = products[0]
                classify_msg = f"识别到 {len(products)} 个候选，首选 {top.product_name}"
            else:
                classify_msg = "未达置信度阈值，产品类型为 unknown"
            await self._mark_stage(task_id, "classify", StageStatus.success, classify_msg)

            await self._mark_stage(task_id, "extract", StageStatus.success, "抽取完成（演示）")

            risk_hits = self._collect_risks(request.text, products)

            await self._mark_stage(
                task_id,
                "rule_review",
                StageStatus.success,
                f"规则复核完成：{len(risk_hits)} 条发现（允许为 0）",
            )

            # 模型只接收规则结果做解释；不得要求凑数量
            prompt = (
                RULE_REVIEW_SYSTEM
                + "\n\n"
                + FINDINGS_USER_TEMPLATE.format(
                    raw_text=request.text[:2000],
                    rule_findings_json=json.dumps(
                        [{"id": h.pattern_id, "name": h.name} for h in risk_hits],
                        ensure_ascii=False,
                    ),
                )
            )
            await self._llm.complete(prompt)
            await self._mark_stage(task_id, "explain", StageStatus.success, "解释完成（演示）")

            task = self._tasks.get(task_id)
            if task is None:
                return
            task.report = self._build_report(request.text, products, risk_hits)
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
        await asyncio.sleep(0.25)
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

    def _collect_risks(self, text: str, products) -> list[RiskHit]:
        """按候选产品过滤规则；无候选时全量匹配。"""
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

    def _build_report(self, _text: str, products, risk_hits: list[RiskHit]) -> AnalysisReport:
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

        plain = (
            f"程序规则命中 {len(findings)} 条风险（允许为 0，未凑数）。"
            if findings
            else "未命中已知风险模式；安全文本允许零发现，未为版面凑数。"
        )

        return AnalysisReport(
            product_candidates=candidates,
            product_risk_grade=ProductRiskGrade(
                value=None,
                status=FactStatus.not_disclosed,
                note="原文未明确风险等级",
            ),
            plain_language=PlainLanguage(text=plain, status=StageStatus.success),
            key_parameters=[
                KeyParameter(
                    key=ParameterKey.term,
                    label="投资期限",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
                KeyParameter(
                    key=ParameterKey.principal_protection,
                    label="本金保障",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
                KeyParameter(
                    key=ParameterKey.expected_return,
                    label="预期收益",
                    value=None,
                    status=FactStatus.not_disclosed,
                ),
            ],
            findings=findings,
            missing_disclosures=[
                MissingDisclosure(
                    key=ParameterKey.principal_protection,
                    question="合同是否明确承诺本金保障？",
                )
            ],
            general_references=[
                GeneralReference(
                    text="行业常识仅供参考，不能自动填入当前材料未披露字段。",
                    source="docs/demo-scope.md",
                )
            ],
            pending_questions=["是否支持提前赎回？"] if not findings else [],
            disclaimer="本 Demo 不进行用户适当性评估，不构成投资建议。",
        )
