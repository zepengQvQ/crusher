"""产品类型决议（从 AnalyzeTextUseCase 抽出）。

用途：根据手动提示与原文信号生成唯一 ProductResolution。
输入：原文、ProductHint、RuleEngine 产品检测结果。
输出：ProductResolution（supported / needs_confirmation / out_of_scope）。
不变量：后续抽取与规则只能读本决议，不得重新猜产品。
失败方式：不抛业务异常；冲突与超范围用 analysis_scope 表达。
"""
from __future__ import annotations

from app.domain.models import (
    AnalysisScope,
    ProductCandidate,
    ProductResolution,
    ProductTypeId,
)
from app.domain.models.enums import ProductHint
from app.domain.rules.engine import ProductHit, RuleEngine

# Demo 正式支持的产品；其它识别结果只提示范围，不做完整分析
DEMO_SUPPORTED_PRODUCTS = frozenset({"structured_deposit", "loan"})
SCOPE_PENDING_QUESTION = "当前 Demo 仅支持结构性存款和贷款，请重新选择或补充材料。"
CONFIRM_PENDING_QUESTION = "产品类型存在冲突，请确认后重新分析。"
_LOAN_TEXT_MARKERS = ("贷款", "消费贷", "借款", "等额本息", "年化利率")
_DEPOSIT_TEXT_MARKERS = ("结构性存款", "结构存款", "观察区间", "挂钩型存款")


class ProductResolver:
    """分类阶段产品决议器。

    Java 对照：领域服务 / Strategy，由 Harness 在 RESOLVE_PRODUCT 调用。
    """

    def __init__(self, rule_engine: RuleEngine) -> None:
        self._rules = rule_engine

    def resolve(
        self,
        text: str,
        product_hint: ProductHint | str | None,
    ) -> ProductResolution:
        """生成唯一产品决议；后续抽取/规则只能读此 DTO。"""
        if isinstance(product_hint, ProductHint):
            hint = product_hint
        else:
            raw = (product_hint or "auto").strip().lower()
            hint = ProductHint(raw) if raw in {e.value for e in ProductHint} else ProductHint.auto

        detected = self._rules.detect_products(text)
        # 受支持产品优先排序，避免保险等附带词抢第一
        detected_sorted = sorted(
            detected,
            key=lambda p: (
                0 if p.product_id in DEMO_SUPPORTED_PRODUCTS else 1,
                -p.confidence,
            ),
        )
        candidates = self._hits_to_candidates(detected_sorted)
        text_loan = self._text_has_markers(text, _LOAN_TEXT_MARKERS)
        text_deposit = self._text_has_markers(text, _DEPOSIT_TEXT_MARKERS)
        supported_hits = [p for p in detected_sorted if p.product_id in DEMO_SUPPORTED_PRODUCTS]

        if hint == ProductHint.structured_deposit and text_loan and not text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择结构性存款，但原文更像贷款，需确认产品类型",
            )
        if hint == ProductHint.loan and text_deposit and not text_loan:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择贷款，但原文更像结构性存款，需确认产品类型",
            )
        if hint == ProductHint.structured_deposit and text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择与原文产品信号冲突，需确认",
            )
        if hint == ProductHint.loan and text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="手动选择与原文产品信号冲突，需确认",
            )

        if hint in (ProductHint.structured_deposit, ProductHint.loan):
            resolved = ProductTypeId(hint.value)
            label = resolved.label
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=resolved,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates
                or self._hits_to_candidates(
                    [
                        ProductHit(
                            product_id=hint.value,
                            product_name=label,
                            confidence=1.0,
                            evidence_quotes=[f"手动选择：{label}"],
                        )
                    ]
                ),
                reason=f"手动指定 {label}",
            )

        # auto
        strong_supported = [p for p in supported_hits if p.confidence >= 0.85]
        if len(strong_supported) >= 2:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="自动识别到多个受支持产品，需确认",
            )
        if len(supported_hits) == 1 or (len(strong_supported) == 1 and len(supported_hits) >= 1):
            primary = strong_supported[0] if strong_supported else supported_hits[0]
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId(primary.product_id),
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason=f"自动识别首选 {primary.product_name}",
            )
        if text_loan and text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=None,
                analysis_scope=AnalysisScope.needs_confirmation,
                candidates=candidates,
                reason="原文同时出现贷款与结构性存款信号，需确认",
            )
        if text_loan:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId.loan,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason="根据原文贷款信号识别为贷款",
            )
        if text_deposit:
            return ProductResolution(
                requested_hint=hint,
                resolved_product_type=ProductTypeId.structured_deposit,
                analysis_scope=AnalysisScope.supported,
                candidates=candidates,
                reason="根据原文识别为结构性存款",
            )
        return ProductResolution(
            requested_hint=hint,
            resolved_product_type=None,
            analysis_scope=AnalysisScope.out_of_scope,
            candidates=candidates,
            reason="未识别到 Demo 支持的产品类型",
        )

    @staticmethod
    def _text_has_markers(text: str, markers: tuple[str, ...]) -> bool:
        return any(m in text for m in markers)

    @staticmethod
    def _hits_to_candidates(products: list[ProductHit]) -> list[ProductCandidate]:
        out: list[ProductCandidate] = []
        for p in products:
            try:
                pid = ProductTypeId(p.product_id)
            except ValueError:
                pid = ProductTypeId.unknown
            out.append(
                ProductCandidate(
                    product_type_id=pid,
                    product_type_name=p.product_name,
                    confidence=p.confidence,
                    evidence_quotes=list(p.evidence_quotes),
                )
            )
        return out
