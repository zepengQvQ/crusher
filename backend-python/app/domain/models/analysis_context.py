"""P2-01：分析流程上下文与 Harness 阶段结果。

用途：承载单次分析的可追踪上下文，供 Harness 编排与停止。
输入：任务 ID、原文、产品提示、演示错误开关。
输出：阶段进度、产品决议、报告或拒绝原因。
不变量：材料内容不可信；Outcome 必须显式，禁止静默空风险。
失败方式：通过 OutcomeStatus.refuse + error_code 表达，不抛 HTTP 异常。
"""
from __future__ import annotations

from enum import Enum

from pydantic import Field

from app.domain.models.completeness import (
    ClarificationAnswer,
    CompletenessResult,
)
from app.domain.models.enums import DemoErrorKind, ProductHint
from app.domain.models.intent import IntentDecision, IntentType
from app.domain.models.report import (
    AnalysisReport,
    ProductResolution,
    StrictModel,
)
from app.shared.enums import ErrorCode, StageStatus


class HarnessStage(str, Enum):
    """Harness 内部阶段（与 HTTP StageInfo 名称可映射，但不混用）。"""

    receive = "receive"
    normalize = "normalize"
    resolve_intent = "resolve_intent"
    check_completeness = "check_completeness"
    resolve_product = "resolve_product"
    extract_facts = "extract_facts"
    apply_rules = "apply_rules"
    build_draft = "build_draft"
    verify = "verify"
    decide_outcome = "decide_outcome"


class OutcomeStatus(str, Enum):
    """发布门禁结果。"""

    publish = "publish"
    publish_partial = "publish_partial"
    clarify = "clarify"
    refuse = "refuse"


class HttpStageUpdate(StrictModel):
    """映射到任务 StageInfo 的一次更新（供 UseCase 落库）。"""

    name: str
    status: StageStatus
    message: str = ""


class AnalysisContext(StrictModel):
    """单次分析流程上下文。

    Java 对照：流程上下文 DTO / Aggregate 的传输形态。
    """

    task_id: str = Field(..., min_length=1)
    source_text: str = Field(..., min_length=1)
    product_hint: ProductHint = ProductHint.auto
    demo_error: DemoErrorKind | None = None
    # P2-02：单材料 Harness 默认显式意图；可由上层注入已决议结果
    explicit_intent: IntentType = IntentType.single_analysis
    intent_decision: IntentDecision | None = None
    clarification_answers: list[ClarificationAnswer] = Field(default_factory=list)
    completeness_result: CompletenessResult | None = None
    current_stage: HarnessStage = HarnessStage.receive
    product_resolution: ProductResolution | None = None
    report: AnalysisReport | None = None
    outcome: OutcomeStatus | None = None
    error_code: ErrorCode | None = None
    stop_reason: str = ""
    http_stage_updates: list[HttpStageUpdate] = Field(default_factory=list)
    # 供 UseCase 写回任务级决议
    resolution_persisted: bool = False


class HarnessResult(StrictModel):
    """Harness 领域输出；不依赖 FastAPI / Vue / MCP。"""

    context: AnalysisContext
    outcome: OutcomeStatus
    report: AnalysisReport | None = None
    error_code: ErrorCode | None = None
    stop_harness_stage: HarnessStage
    stop_reason: str = ""
    failed_http_stage: str | None = None


# Harness 阶段 → 现有 HTTP 轮询阶段名
HARNESS_TO_HTTP_STAGE: dict[HarnessStage, str] = {
    HarnessStage.receive: "preprocess",
    HarnessStage.normalize: "preprocess",
    HarnessStage.resolve_intent: "preprocess",
    HarnessStage.check_completeness: "preprocess",
    HarnessStage.resolve_product: "classify",
    HarnessStage.extract_facts: "extract",
    HarnessStage.apply_rules: "rule_review",
    HarnessStage.build_draft: "explain",
    HarnessStage.verify: "explain",
    HarnessStage.decide_outcome: "explain",
}
