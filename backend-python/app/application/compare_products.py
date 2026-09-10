"""P1-06：两款产品事实对照用例。

Java 对照：Application Service / UseCase。
用途：按固定维度并列展示两款产品事实与缺失，不输出推荐或评分。
前置条件：两侧文本均非空。
处理边界：只支持两款；等值期限不伪差异；不同收益口径标 incomparable。
返回：ProductComparisonReport（经 PublicationService 门禁）。
错误：参数校验失败由路由 422；业务缺参以维度 MISSING 表达。
"""
from __future__ import annotations

from app.domain.models.p1_enums import DiffStatus, ProductFactDimension
from app.domain.models.product_facts import (
    DimensionComparison,
    ProductCompareRequest,
    ProductComparisonReport,
)
from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.product_fact_builder import build_side_facts, compare_side_values
from app.domain.validation.publication_service import PublicationService

_DIMENSIONS: list[tuple[ProductFactDimension, str, str]] = [
    (ProductFactDimension.product_type, "产品类型", "product_type"),
    (ProductFactDimension.term, "期限", "term"),
    (ProductFactDimension.amount, "起购/借款金额", "amount"),
    (ProductFactDimension.return_or_rate, "收益/利率口径", "return_or_rate"),
    (ProductFactDimension.early_exit, "流动性/提前退出", "early_exit"),
    (ProductFactDimension.fees, "费用", "fees"),
    (ProductFactDimension.principal_protection, "本金保障", "principal_protection"),
    (ProductFactDimension.main_risks, "主要风险", "main_risks"),
    (ProductFactDimension.undisclosed, "未披露信息", "undisclosed"),
]


class CompareProductsUseCase:
    def __init__(
        self,
        knowledge: KnowledgeRepository,
        publication: PublicationService | None = None,
    ) -> None:
        self._knowledge = knowledge
        self._publication = publication or PublicationService()

    def execute(self, request: ProductCompareRequest) -> ProductComparisonReport:
        meta_a, fields_a = build_side_facts(
            text=request.text_a,
            label=request.label_a,
            hint=request.product_hint_a,
            knowledge=self._knowledge,
        )
        meta_b, fields_b = build_side_facts(
            text=request.text_b,
            label=request.label_b,
            hint=request.product_hint_b,
            knowledge=self._knowledge,
        )
        dimensions: list[DimensionComparison] = []
        for dim, label, key in _DIMENSIONS:
            side_a = fields_a[key]
            side_b = fields_b[key]
            status_raw, note = compare_side_values(side_a, side_b)
            # 冲突/差异时两侧证据都尽量保留；缺失侧保持 empty evidence
            dimensions.append(
                DimensionComparison(
                    dimension=dim,
                    label=label,
                    status=DiffStatus(status_raw),
                    side_a=side_a,
                    side_b=side_b,
                    note=note,
                )
            )
        report = ProductComparisonReport(
            product_a=meta_a,
            product_b=meta_b,
            dimensions=dimensions,
        )
        return self._publication.finalize_compare(report)
