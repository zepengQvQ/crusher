"""意图识别用例（P2-02）。

用途：对外提供安全意图决议；可选模型候选不得覆盖显式意图。
输入：IntentResolveRequest。
输出：IntentDecision。
不变量：材料信封不参与命令解析；use_case_key 仅来自白名单。
失败方式：模型超时/非法枚举 → needs_clarification，不执行分析。
"""
from __future__ import annotations

from app.domain.models.intent import (
    DecisionSource,
    DecisionStatus,
    IntentDecision,
    IntentResolveRequest,
    IntentType,
)
from app.domain.rules.intent_resolver import IntentResolver, _options


class ResolveIntentUseCase:
    """意图识别 Application Service。"""

    def __init__(self, resolver: IntentResolver | None = None) -> None:
        self._resolver = resolver or IntentResolver()

    def execute(self, request: IntentResolveRequest) -> IntentDecision:
        decision = self._resolver.resolve(request)
        # P2-RC-05：Demo 未接入真实模型候选。开关打开时仍只返回规则澄清，
        # 禁止在未调用模型时把 source 标成 model_candidate。
        if request.allow_model_candidate and decision.intent == IntentType.ambiguous:
            return IntentDecision(
                intent=IntentType.ambiguous,
                status=DecisionStatus.needs_clarification,
                source=DecisionSource.rule,
                rationale=list(decision.rationale)
                + ["Demo 未启用模型候选调用：保持规则澄清，不标记 model_candidate"],
                clarifying_options=decision.clarifying_options
                or _options(
                    (IntentType.single_analysis, "单材料分析", ""),
                    (IntentType.product_compare, "两款产品对照", ""),
                    (IntentType.calculation, "简单计算", ""),
                ),
                missing=list(decision.missing),
            )
        return decision
