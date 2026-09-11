"""
用途：把产品决议、事实账本、发现与白话组装成对外 AnalysisReport。
Java 对照：DTO Assembler（应用层，不跑规则、不调模型）。
输入：ProductResolution、ExtractResult、findings、plain、publication。
输出：AnalysisReport（支持范围闸门报告与完整分析报告）。
业务不变量：范围闸门报告不得冒充完整风险分析；风险等级仅来自原文事实。
失败方式：不抛异常；缺候选时填 unknown / out-of-scope 标记。
"""
from __future__ import annotations

from app.domain.models import (
    AnalysisReport,
    AnalysisScope,
    FactStatus,
    Finding,
    PlainLanguage,
    ProductCandidate,
    ProductResolution,
    ProductRiskGrade,
    ProductTypeId,
)
from app.domain.models.enums import ParameterKey
from app.domain.rules.fact_extractor import ExtractResult
from app.domain.rules.product_resolver import (
    CONFIRM_PENDING_QUESTION,
    SCOPE_PENDING_QUESTION,
)
from app.shared.enums import StageStatus


class ReportAssembler:
    """分析报告 DTO 组装。"""

    @staticmethod
    def build_scope_gate_report(
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

    @staticmethod
    def build_supported_report(
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
            resolved = resolution.resolved_product_type
            candidates = [
                ProductCandidate(
                    product_type_id=resolved,
                    product_type_name=resolved.label,
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
