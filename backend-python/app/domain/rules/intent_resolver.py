"""意图识别规则（P2-02）。

用途：按优先级决定用户意图；只读 user_query / 显式 UI / 路由，不读材料正文指令。
输入：IntentResolveRequest。
输出：IntentDecision。
不变量：显式页面意图不可被模型或材料覆盖；多意图并列不猜。
失败方式：ambiguous / unsupported / needs_clarification。
"""
from __future__ import annotations

import re

from app.domain.models.intent import (
    INTENT_USE_CASE_MAP,
    PAGE_ROUTE_INTENT,
    DecisionSource,
    DecisionStatus,
    IntentDecision,
    IntentOption,
    IntentResolveRequest,
    IntentType,
)

_CALC_RE = re.compile(
    r"(算|计算|测算).{0,12}(收益|利息|费用|净结果)|"
    r"(收益|利息|费用).{0,8}(算|计算)|"
    r"帮我算|算一下|按\s*\d+",
    re.IGNORECASE,
)
_PRODUCT_COMPARE_RE = re.compile(
    r"(两款|两个产品|产品对比|对比一下|比一比|pk|PK|哪个更好|哪款更好)",
)
_DUAL_RE = re.compile(
    r"(销售.{0,6}(材料|合同|条款)|话术.{0,6}(对照|对比)|正式材料.{0,6}(对照|对比)|"
    r"口头承诺.{0,8}(合同|条款))",
)
_FOLLOW_RE = re.compile(r"(追问|再问|根据材料回答|有没有写|材料里有没有)")
_EXTRACT_RE = re.compile(r"(上传|识别|提取).{0,8}(pdf|PDF|图片|扫描)|ocr|OCR")
_ADVICE_RE = re.compile(r"(能买吗|适合我吗|该不该买|推荐购买|给我推荐|哪个好买)")
_ANALYSIS_RE = re.compile(r"(分析|解读|看看这段|帮我看看|风险)")


def _options(*pairs: tuple[IntentType, str, str]) -> list[IntentOption]:
    return [IntentOption(intent=i, label=lab, reason=r) for i, lab, r in pairs]


class IntentResolver:
    """确定性意图路由；模型候选仅可选且不可覆盖显式意图。"""

    def resolve(self, request: IntentResolveRequest) -> IntentDecision:
        # 1) 显式 UI / 调用方指定
        if request.explicit_intent is not None:
            return self._from_explicit(
                request.explicit_intent,
                DecisionSource.explicit_ui,
                "来自明确页面操作或调用方指定，忽略材料内指令",
            )

        # 2) 页面路由
        route = (request.page_route or "").strip()
        if route in PAGE_ROUTE_INTENT:
            intent = PAGE_ROUTE_INTENT[route]
            return self._from_explicit(
                intent,
                DecisionSource.api_route,
                f"来自页面路由 {route}，不重新猜测意图",
            )

        query = request.user_query
        # 3) 无用户目标、仅有材料 → 默认单材料分析（粘贴合同）
        if not query:
            if request.source_envelopes:
                return IntentDecision(
                    intent=IntentType.single_analysis,
                    status=DecisionStatus.resolved,
                    source=DecisionSource.rule,
                    rationale=[
                        "用户未写目标语句，仅提交材料，默认单材料分析",
                        "材料正文不作为系统指令",
                    ],
                    use_case_key=INTENT_USE_CASE_MAP[IntentType.single_analysis],
                )
            return IntentDecision(
                intent=IntentType.ambiguous,
                status=DecisionStatus.needs_clarification,
                source=DecisionSource.rule,
                rationale=["缺少用户目标与材料"],
                missing=["请选择要做的事，或粘贴一份材料"],
                clarifying_options=_options(
                    (IntentType.single_analysis, "单材料分析", "粘贴条款做风险解读"),
                    (IntentType.dual_source_compare, "销售与材料对照", "对比口头承诺与正式文本"),
                    (IntentType.product_compare, "两款产品对照", "按固定维度并列事实"),
                    (IntentType.calculation, "简单计算", "确认参数后算收益/费用"),
                ),
            )

        # 4) 只对 user_query 做规则（故意不扫描 source_envelopes 正文）
        hits: list[IntentType] = []
        rationale: list[str] = []

        if _ADVICE_RE.search(query):
            return IntentDecision(
                intent=IntentType.unsupported,
                status=DecisionStatus.rejected,
                source=DecisionSource.rule,
                rationale=[
                    "请求涉及投资建议/购买决策，超出 Demo 范围",
                    "可改为只做事实对照，不输出推荐",
                ],
                clarifying_options=_options(
                    (
                        IntentType.product_compare,
                        "只做两款产品事实对照",
                        "不评价好坏，不给购买建议",
                    ),
                    (
                        IntentType.single_analysis,
                        "只分析材料事实与风险",
                        "不判断是否适合购买",
                    ),
                ),
            )

        if _CALC_RE.search(query):
            hits.append(IntentType.calculation)
            rationale.append("用户目标命中计算相关表述")
        if _PRODUCT_COMPARE_RE.search(query):
            hits.append(IntentType.product_compare)
            rationale.append("用户目标命中产品对比相关表述")
        if _DUAL_RE.search(query):
            hits.append(IntentType.dual_source_compare)
            rationale.append("用户目标命中销售/正式材料对照表述")
        if _FOLLOW_RE.search(query):
            hits.append(IntentType.evidence_follow_up)
            rationale.append("用户目标命中证据追问表述")
        if _EXTRACT_RE.search(query):
            hits.append(IntentType.document_extract)
            rationale.append("用户目标命中文档提取表述")
        if _ANALYSIS_RE.search(query) and IntentType.single_analysis not in hits:
            hits.append(IntentType.single_analysis)
            rationale.append("用户目标命中单材料分析表述")

        unique = list(dict.fromkeys(hits))
        if len(unique) > 1:
            return IntentDecision(
                intent=IntentType.ambiguous,
                status=DecisionStatus.needs_clarification,
                source=DecisionSource.rule,
                rationale=rationale + ["同时出现多种意图，不自动猜测"],
                clarifying_options=_options(
                    *[(i, _label(i), "请先选一件事") for i in unique]
                ),
            )
        if len(unique) == 1:
            intent = unique[0]
            return IntentDecision(
                intent=intent,
                status=DecisionStatus.resolved,
                source=DecisionSource.rule,
                rationale=rationale,
                use_case_key=INTENT_USE_CASE_MAP[intent],
            )

        # 5) 规则无法唯一确定：不调用任意工具名；可选模型候选在 UseCase 层处理
        return IntentDecision(
            intent=IntentType.ambiguous,
            status=DecisionStatus.needs_clarification,
            source=DecisionSource.rule,
            rationale=["规则无法从用户目标唯一确定意图"] + rationale,
            clarifying_options=_options(
                (IntentType.single_analysis, "单材料分析", ""),
                (IntentType.dual_source_compare, "销售与材料对照", ""),
                (IntentType.product_compare, "两款产品对照", ""),
                (IntentType.calculation, "简单计算", ""),
            ),
        )

    def _from_explicit(
        self,
        intent: IntentType,
        source: DecisionSource,
        reason: str,
    ) -> IntentDecision:
        if intent in (IntentType.ambiguous, IntentType.unsupported):
            status = (
                DecisionStatus.needs_clarification
                if intent == IntentType.ambiguous
                else DecisionStatus.rejected
            )
            return IntentDecision(
                intent=intent,
                status=status,
                source=source,
                rationale=[reason],
            )
        return IntentDecision(
            intent=intent,
            status=DecisionStatus.resolved,
            source=source,
            rationale=[reason],
            use_case_key=INTENT_USE_CASE_MAP[intent],
        )


def _label(intent: IntentType) -> str:
    return {
        IntentType.single_analysis: "单材料分析",
        IntentType.dual_source_compare: "销售与材料对照",
        IntentType.product_compare: "两款产品对照",
        IntentType.calculation: "简单计算",
        IntentType.evidence_follow_up: "证据追问",
        IntentType.document_extract: "文档提取",
        IntentType.unsupported: "超出范围",
        IntentType.ambiguous: "需要选择",
    }.get(intent, intent.value)
