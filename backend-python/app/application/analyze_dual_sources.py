"""双材料对照用例（P1-01）。

Java 对照：Application Service / UseCase。
用途：对比同一产品的销售话术与正式材料。
前置条件：两侧文本均非空。
处理边界：只做确定性主张抽取与对照，不判断法律效力、不给销售打分。
返回：DualAnalysisReport；单侧空在 HTTP 层拒绝。
错误：无业务异常码时由路由映射 4xx。
"""
from __future__ import annotations

from app.domain.models.claim_comparison import (
    DualAnalysisReport,
    DualAnalysisRequest,
    SourceDocument,
)
from app.domain.models.p1_enums import SourceType
from app.domain.rules.claim_extractor import extract_sales_claims
from app.domain.rules.claim_matcher import match_claims_to_official
from app.domain.rules.financial_fact_extractor import FinancialFactExtractor


class AnalyzeDualSourcesUseCase:
    """同一产品：销售材料 A vs 正式材料 B。"""

    def __init__(self) -> None:
        self._facts = FinancialFactExtractor()

    def execute(self, request: DualAnalysisRequest) -> DualAnalysisReport:
        sales = SourceDocument(
            source_type=SourceType.sales_pitch,
            name="销售话术",
            text=request.sales_text,
        )
        official = SourceDocument(
            source_type=SourceType.official_document,
            name="正式材料",
            text=request.official_text,
        )
        # 证据 source_id 与文档对齐
        claims = extract_sales_claims(sales.source_id, sales.text)
        # matcher 内官方证据先写 official，再改写 source_id
        comparisons = match_claims_to_official(
            claims,
            official.text,
            official_source_id=official.source_id,
        )
        pending = [
            c.suggested_follow_up
            for c in comparisons
            if c.suggested_follow_up and c.status.value != "confirmed"
        ]
        # 去重保序
        seen: set[str] = set()
        uniq_pending: list[str] = []
        for q in pending:
            if q in seen:
                continue
            seen.add(q)
            uniq_pending.append(q)
        sales_facts = self._facts.extract(
            sales.text, product_id=sales.source_id
        ).facts
        official_facts = self._facts.extract(
            official.text, product_id=official.source_id
        ).facts
        return DualAnalysisReport(
            sales_source=sales,
            official_source=official,
            comparisons=comparisons,
            pending_questions=uniq_pending,
            sales_financial_facts=sales_facts,
            official_financial_facts=official_facts,
        )
