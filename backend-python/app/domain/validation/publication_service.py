"""
用途：跨业务入口统一结果门禁（双材料 / 产品对比 / 追问 / 计算 / 单材料校验）。
Java 对照：领域校验服务 PublicationService / ResultGate（与单材料 Harness 解耦）。
输入：各入口报告 DTO + 原文。
输出：附带 PublicationDecision 的同型报告；单材料返回 VerificationResult。
业务不变量：假证据不得支撑 confirmed/same/conflict；对外 outcome 仅四态。
失败方式：降级字段状态并写入 PUBLISH_PARTIAL / CLARIFY / REFUSE。
"""
from __future__ import annotations

import re

from app.domain.models.calculation import CalculationResult
from app.domain.models.claim_comparison import (
    ClaimComparison,
    DualAnalysisReport,
)
from app.domain.models.evidence_answer import AnswerStatus, EvidenceAnswer
from app.domain.models.financial_fact import FinancialFact
from app.domain.models.llm import LlmAnalysisDraft
from app.domain.models.p1_enums import (
    ClaimStatus,
    DiffStatus,
    FieldStatus,
    ProductFactDimension,
    SourceType,
)
from app.domain.models.product_facts import (
    DimensionComparison,
    FactSideValue,
    ProductComparisonReport,
)
from app.domain.models.report import Finding, KeyParameter
from app.domain.models.verification import PublicationDecision, VerificationResult
from app.domain.rules.product_fact_builder import compare_side_values
from app.domain.validation.evidence_validator import (
    evidence_ref_locates,
    validate_financial_fact_evidence,
)
from app.domain.validation.publication_gate import (
    decide_clarify,
    decide_from_verification,
    decide_publish,
    decide_publish_partial,
    decide_refuse,
    run_publication_gate,
)
from app.shared.enums import ErrorCode

_REC_BAD = re.compile(
    r"(更适合你|综合排名|推荐购买|建议购买|赢家|最优选|强烈推荐)"
)


class PublicationService:
    """与 Harness 解耦的跨入口结果门禁。"""

    def verify_single_analysis(
        self,
        *,
        source_text: str,
        draft: LlmAnalysisDraft,
        plain: str,
        findings: list[Finding],
        key_parameters: list[KeyParameter],
        financial_facts: list[FinancialFact],
        allowed_fact_ids: list[str],
        allowed_finding_ids: list[str],
        allowed_knowledge_ids: list[str],
        dropped_finding_ids: list[str] | None = None,
        rule_hit_count: int | None = None,
    ) -> VerificationResult:
        """单材料：复用 publication_gate 确定性校验。"""
        return run_publication_gate(
            source_text=source_text,
            draft=draft,
            plain=plain,
            findings=findings,
            key_parameters=key_parameters,
            financial_facts=financial_facts,
            allowed_fact_ids=allowed_fact_ids,
            allowed_finding_ids=allowed_finding_ids,
            allowed_knowledge_ids=allowed_knowledge_ids,
            dropped_finding_ids=dropped_finding_ids,
            rule_hit_count=rule_hit_count,
        )

    def decide_from_verification(
        self, verification: VerificationResult
    ) -> PublicationDecision:
        return decide_from_verification(verification)

    def finalize_dual(self, report: DualAnalysisReport) -> DualAnalysisReport:
        roles_ok = (
            report.sales_source.source_type == SourceType.sales_pitch
            and report.official_source.source_type == SourceType.official_document
        )
        sales_text = report.sales_source.text
        official_text = report.official_source.text

        cleaned: list[ClaimComparison] = []
        downgraded = False
        for cmp in report.comparisons:
            scrubbed, changed = self._scrub_dual_comparison(
                cmp, sales_text=sales_text, official_text=official_text
            )
            if scrubbed is None:
                downgraded = True
                continue
            if changed:
                downgraded = True
            cleaned.append(scrubbed)

        fact_issues = validate_financial_fact_evidence(
            sales_text, report.sales_financial_facts
        ) + validate_financial_fact_evidence(
            official_text, report.official_financial_facts
        )
        if fact_issues:
            downgraded = True

        if not roles_ok:
            publication = decide_clarify(
                reason_code=ErrorCode.CLARIFICATION_INVALID,
                user_reason="销售话术与正式材料角色未区分清楚，请重新标注两侧来源",
                next_steps=["确认哪一侧是销售话术", "确认哪一侧是正式材料"],
            )
        elif downgraded:
            publication = decide_publish_partial(
                reason_code=ErrorCode.INSUFFICIENT_EVIDENCE,
                user_reason="部分对照缺少可定位证据，已降级为不确定/不可硬判",
                next_steps=[
                    "请核对双方原文证据",
                    "证据不足时请补充正式材料后再对照",
                ],
                checked=["双材料证据定位", "来源角色检查"],
                not_checked=["未验证对照的一致/冲突硬判"],
            )
        else:
            publication = decide_publish(
                user_reason="双材料对照完成，双方证据均可定位"
            )

        return report.model_copy(
            update={"comparisons": cleaned, "publication": publication}
        )

    def finalize_compare(
        self, report: ProductComparisonReport
    ) -> ProductComparisonReport:
        text_a = report.product_a.source_text
        text_b = report.product_b.source_text
        dimensions: list[DimensionComparison] = []
        downgraded = False
        for dim in report.dimensions:
            # undisclosed 为抽取摘要元信息，允许无 span 证据
            require_ev = dim.dimension != ProductFactDimension.undisclosed
            side_a, ch_a = self._scrub_side(
                dim.side_a, text_a, require_evidence=require_ev
            )
            side_b, ch_b = self._scrub_side(
                dim.side_b, text_b, require_evidence=require_ev
            )
            if ch_a or ch_b:
                downgraded = True
            status_raw, note = compare_side_values(side_a, side_b)
            # 不同收益口径 → 不可直接比较（compare_side_values 已处理 nature）
            note = self._scrub_recommendation_copy(note)
            if _REC_BAD.search(note):
                note = "两侧表述不同"
                downgraded = True
            new_status = DiffStatus(status_raw)
            # same/different 必须两侧均有可定位证据（undisclosed 除外）
            if (
                require_ev
                and new_status in (DiffStatus.same, DiffStatus.different)
                and (not side_a.evidence or not side_b.evidence)
            ):
                new_status = DiffStatus.incomparable
                note = "缺少两侧可定位证据，不可直接判定一致或差异"
                downgraded = True
            dimensions.append(
                DimensionComparison(
                    dimension=dim.dimension,
                    label=dim.label,
                    status=new_status,
                    side_a=side_a,
                    side_b=side_b,
                    note=note,
                )
            )

        disclaimer = self._scrub_recommendation_copy(report.disclaimer)
        if downgraded:
            publication = decide_publish_partial(
                reason_code=ErrorCode.INSUFFICIENT_EVIDENCE,
                user_reason="产品对比中部分维度证据不足或口径不可比，已降级发布",
                next_steps=["请核对两侧原文", "不同收益口径请勿直接比较"],
                checked=["产品对比证据定位", "推荐文案过滤"],
                not_checked=["投资建议与综合排名（本 Demo 不输出）"],
            )
        else:
            publication = decide_publish(user_reason="产品事实对照完成")

        return report.model_copy(
            update={
                "dimensions": dimensions,
                "disclaimer": disclaimer,
                "publication": publication,
            }
        )

    def finalize_follow_up(
        self, answer: EvidenceAnswer, *, source_text: str
    ) -> EvidenceAnswer:
        if answer.status == AnswerStatus.out_of_scope:
            publication = decide_refuse(
                reason_code=ErrorCode.UNSUPPORTED_REQUEST,
                user_reason=answer.answer or "问题超出材料核对范围",
                next_steps=["请改问与材料条款相关的事实问题"],
            )
            return answer.model_copy(update={"publication": publication})

        valid_evidence = [
            ev
            for ev in answer.evidence
            if evidence_ref_locates(source_text, ev)
        ]
        if answer.status == AnswerStatus.answered:
            if not valid_evidence:
                publication = decide_publish_partial(
                    reason_code=ErrorCode.INSUFFICIENT_EVIDENCE,
                    user_reason="追问答案缺少可定位证据，未作为确定答案发布",
                    next_steps=["请用会话「+」补充相关正式条款后再问"],
                    checked=["追问证据定位"],
                    not_checked=["确定答案"],
                )
                return answer.model_copy(
                    update={
                        "status": AnswerStatus.insufficient_evidence,
                        "answer": "找到相关原文，未形成确定答案"
                        if answer.evidence
                        else "当前材料里找不到足够依据，没法确定回答。",
                        "evidence": [],
                        "missing_info": answer.missing_info
                        or ["请补充可精确定位的正式条款"],
                        "publication": publication,
                    }
                )
            publication = decide_publish(user_reason="追问已绑定可定位证据")
            return answer.model_copy(
                update={"evidence": valid_evidence, "publication": publication}
            )

        # insufficient_evidence
        publication = decide_publish_partial(
            reason_code=ErrorCode.INSUFFICIENT_EVIDENCE,
            user_reason=answer.answer or "证据不足，无法给出确定结论",
            next_steps=answer.missing_info[:3] or ["请补充相关正式条款"],
            checked=["追问证据检索"],
            not_checked=["确定答案"],
        )
        return answer.model_copy(
            update={
                "evidence": valid_evidence,
                "publication": publication,
            }
        )

    def finalize_calculation(
        self,
        result: CalculationResult,
        *,
        user_confirmed: bool,
    ) -> CalculationResult:
        if not user_confirmed:
            publication = decide_refuse(
                reason_code=ErrorCode.CALCULATION_INVALID,
                user_reason="计算参数未经用户确认，拒绝演算",
                next_steps=["请确认本金/费率等参数后再计算"],
            )
            return result.model_copy(update={"publication": publication})

        missing = [
            name
            for name, value in (
                ("formula", result.formula),
                ("result", result.result),
                ("rounding", result.rounding),
            )
            if not (value or "").strip()
        ]
        if missing or not result.inputs:
            publication = decide_refuse(
                reason_code=ErrorCode.CALCULATION_INVALID,
                user_reason="计算结果不完整：必须同时返回公式、输入、舍入与结果",
                next_steps=["请重新确认参数后计算"],
            )
            return result.model_copy(update={"publication": publication})

        publication = decide_publish(
            user_reason="按已确认参数完成确定性计算"
        )
        return result.model_copy(update={"publication": publication})

    def _scrub_dual_comparison(
        self,
        cmp: ClaimComparison,
        *,
        sales_text: str,
        official_text: str,
    ) -> tuple[ClaimComparison | None, bool]:
        sales_claim = cmp.sales_claim
        if sales_claim is None:
            return None, True
        sales_ok = evidence_ref_locates(sales_text, sales_claim.evidence)
        if not sales_ok:
            return None, True

        official_ev = cmp.official_evidence
        official_ok = bool(
            official_ev and evidence_ref_locates(official_text, official_ev)
        )
        if official_ev is not None and not official_ok:
            official_ev = None
            official_ok = False

        hard = cmp.status in (ClaimStatus.confirmed, ClaimStatus.conflict)
        if hard and not official_ok:
            return (
                ClaimComparison(
                    comparison_id=cmp.comparison_id,
                    subject=cmp.subject,
                    status=ClaimStatus.uncertain,
                    summary="双方证据无法同时定位，不作一致或冲突硬判",
                    sales_claim=sales_claim,
                    official_evidence=None,
                    suggested_follow_up=cmp.suggested_follow_up
                    or "请补充可定位的正式材料证据后再对照",
                ),
                True,
            )
        if cmp.status == ClaimStatus.conditional and not official_ok:
            return (
                ClaimComparison(
                    comparison_id=cmp.comparison_id,
                    subject=cmp.subject,
                    status=ClaimStatus.uncertain,
                    summary="条件表述缺少可定位正式证据，暂不判定",
                    sales_claim=sales_claim,
                    official_evidence=None,
                    suggested_follow_up=cmp.suggested_follow_up
                    or "请在正式材料中定位条件条款",
                ),
                True,
            )
        if official_ev != cmp.official_evidence:
            return (
                ClaimComparison(
                    comparison_id=cmp.comparison_id,
                    subject=cmp.subject,
                    status=cmp.status,
                    summary=cmp.summary,
                    sales_claim=sales_claim,
                    official_evidence=official_ev,
                    suggested_follow_up=cmp.suggested_follow_up,
                ),
                True,
            )
        return cmp, False

    def _scrub_side(
        self,
        side: FactSideValue,
        source_text: str,
        *,
        require_evidence: bool = True,
    ) -> tuple[FactSideValue, bool]:
        valid = [ev for ev in side.evidence if evidence_ref_locates(source_text, ev)]
        changed = len(valid) != len(side.evidence)
        if side.status == FieldStatus.confirmed and not valid:
            if not require_evidence and not side.evidence:
                return side, False
            return (
                FactSideValue(
                    display=side.display,
                    normalized=side.normalized,
                    status=FieldStatus.uncertain,
                    evidence=[],
                    nature=side.nature,
                ),
                True,
            )
        if changed:
            return side.model_copy(update={"evidence": valid}), True
        return side, False

    @staticmethod
    def _scrub_recommendation_copy(text: str) -> str:
        if not text:
            return text
        cleaned = _REC_BAD.sub("", text)
        return cleaned.strip() or "仅并列展示材料事实，不作选择建议"


# Java 命名对照别名（同一实现，不新增第二套逻辑）
ResultGate = PublicationService

__all__ = ["PublicationService", "ResultGate"]
