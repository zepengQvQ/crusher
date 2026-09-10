"""规则引擎：产品识别 + 风险模式匹配（确定性，不调用模型）。

Java 对照：领域规则服务；Finding 只由程序规则产生，不调用大模型。
"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.models.knowledge import ProductKnowledge, RiskPatternKnowledge
from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.negation import (
    DEFAULT_NEGATION_CUES,
    expand_evidence_for_conditions,
    expand_to_clause,
    is_target_negated,
    iter_strong_sentences,
    strong_sentence_span,
)

# 低于该置信度的产品候选丢弃，整体视为 unknown（调用方处理）
PRODUCT_CONFIDENCE_THRESHOLD = 0.5
# 同一强句内关键词首尾最大距离（字符）
MAX_KEYWORD_SPAN = 48

# 模式专属：命中后再过滤的伪阳性
_LOW_FLOOR_EXCLUDE_RE = re.compile(r"更高|较高档|高档收益")
_PREPAY_REQUIRE_CHARGE_RE = re.compile(r"违约金|手续费|需支付|支付|收取|计收")
_PREPAY_EXCLUDE_RE = re.compile(r"减免|免收|不收|不收取|无需")
_PENALTY_EXCLUDE_RE = re.compile(r"相同|不额外|不加收|与正常利率相同")
_PENALTY_REQUIRE_RE = re.compile(
    r"罚息日利率|罚息利率|罚息.{0,20}([0-9.]+\s*倍|倍)|罚息为正常利率"
)


@dataclass(frozen=True)
class ProductHit:
    product_id: str
    product_name: str
    confidence: float
    evidence_quotes: list[str]


@dataclass(frozen=True)
class RiskHit:
    pattern_id: str
    name: str
    risk_level: str
    explanation: str
    quote: str
    start: int
    end: int
    confidence: float


class RuleEngine:
    """程序侧规则复核：否定、数值、多候选产品。"""

    def __init__(self, knowledge: KnowledgeRepository) -> None:
        self._knowledge = knowledge

    def detect_products(self, text: str) -> list[ProductHit]:
        text = text or ""
        hits: list[ProductHit] = []
        for product in self._knowledge.list_products():
            hit = self._score_product(text, product)
            if hit is not None and hit.confidence >= PRODUCT_CONFIDENCE_THRESHOLD:
                hits.append(hit)
        hits.sort(key=lambda h: h.confidence, reverse=True)
        return hits

    def match_risks(
        self,
        text: str,
        product_type: str | None = None,
    ) -> list[RiskHit]:
        text = text or ""
        matched: list[RiskHit] = []
        for pattern in self._knowledge.list_risk_patterns():
            if product_type and product_type not in pattern.applicable_product_types:
                continue
            hit = self._match_one_pattern(text, pattern)
            if hit is not None:
                matched.append(hit)
        return matched

    def _score_product(self, text: str, product: ProductKnowledge) -> ProductHit | None:
        strong = list(product.strong_aliases)
        weak = list(product.weak_aliases)
        if not strong and not weak:
            for a in product.aliases:
                if len(a) <= 2:
                    weak.append(a)
                else:
                    strong.append(a)

        cues = tuple(product.negation_cues or DEFAULT_NEGATION_CUES)
        window = int(product.context_window or 16)
        evidence: list[str] = []
        strong_score = 0.0
        weak_score = 0.0

        for alias in strong:
            for idx in self._iter_alias_starts(text, alias):
                if self._alias_blocked_by_context(text, idx, alias, product):
                    continue
                end = idx + len(alias)
                if is_target_negated(text, idx, end, cues=cues, window=window):
                    continue
                strong_score = max(strong_score, 0.85)
                evidence.append(alias)
                break

        for alias in weak:
            for idx in self._iter_alias_starts(text, alias):
                if self._alias_blocked_by_context(text, idx, alias, product):
                    continue
                end = idx + len(alias)
                if is_target_negated(text, idx, end, cues=cues, window=window):
                    continue
                weak_score = max(weak_score, 0.4)
                evidence.append(alias)
                break

        confidence = max(strong_score, weak_score)
        if confidence <= 0:
            return None
        return ProductHit(
            product_id=product.id,
            product_name=product.name or product.id,
            confidence=confidence,
            evidence_quotes=evidence,
        )

    @staticmethod
    def _alias_blocked_by_context(
        text: str, idx: int, alias: str, product: ProductKnowledge
    ) -> bool:
        """排除「存款保险」等误触发非支持产品的上下文。"""
        if product.id == "insurance" and alias == "保险":
            if idx >= 2 and text[idx - 2 : idx] == "存款":
                return True
        return False
    @staticmethod
    def _iter_alias_starts(text: str, alias: str) -> list[int]:
        if not alias:
            return []
        starts: list[int] = []
        start = 0
        while True:
            idx = text.find(alias, start)
            if idx < 0:
                break
            starts.append(idx)
            start = idx + max(1, len(alias))
        return starts

    def _match_one_pattern(
        self, text: str, pattern: RiskPatternKnowledge
    ) -> RiskHit | None:
        pattern_id = pattern.id
        if pattern_id == "principal_not_guaranteed":
            if re.search(r"确保本金|本金安全|保证本金", text):
                if not re.search(r"不保证本金|本金(可能)?(面临)?亏损|本金损失|本金受损", text):
                    return None

        cues = tuple(pattern.negation_cues or DEFAULT_NEGATION_CUES)
        window = int(pattern.context_window or 16)
        match_mode = pattern.match_mode.value

        for start, end, quote in self._iter_spans(text, pattern, match_mode):
            if is_target_negated(text, start, end, cues=cues, window=window):
                continue
            if not self._numeric_ok(text, pattern, start=start, end=end):
                continue
            if not self._pattern_semantic_ok(pattern_id, text, start, end):
                continue

            start, end, quote = self._build_evidence(pattern_id, text, start, end)
            return RiskHit(
                pattern_id=pattern_id,
                name=pattern.name,
                risk_level=pattern.risk_level.value,
                explanation=pattern.explanation,
                quote=quote,
                start=start,
                end=end,
                confidence=0.9,
            )
        return None
    def _build_evidence(
        self,
        pattern_id: str,
        text: str,
        start: int,
        end: int,
    ) -> tuple[int, int, str]:
        if pattern_id == "high_penalty_interest":
            return expand_evidence_for_conditions(
                text,
                start,
                end,
                required_parts=("逾期", "罚息利率", "罚息日利率", "罚息"),
            )
        return expand_to_clause(text, start, end)

    def _pattern_semantic_ok(
        self,
        pattern_id: str,
        text: str,
        start: int,
        end: int,
    ) -> bool:
        sent_start, sent_end = strong_sentence_span(text, start)
        sentence = text[sent_start:sent_end]
        if pattern_id == "low_floor_return":
            if _LOW_FLOOR_EXCLUDE_RE.search(sentence):
                return False
            return True
        if pattern_id == "prepayment_penalty":
            if _PREPAY_EXCLUDE_RE.search(sentence):
                return False
            return bool(_PREPAY_REQUIRE_CHARGE_RE.search(sentence))
        if pattern_id == "high_penalty_interest":
            if _PENALTY_EXCLUDE_RE.search(sentence):
                return False
            return bool(_PENALTY_REQUIRE_RE.search(sentence))
        return True

    def _iter_spans(
        self,
        text: str,
        pattern: RiskPatternKnowledge,
        match_mode: str,
    ) -> list[tuple[int, int, str]]:
        regex = pattern.regex or ""
        keywords: Sequence[str] = pattern.keywords or []
        max_span = int(pattern.max_keyword_span or MAX_KEYWORD_SPAN)

        if match_mode == "regex_only":
            return self._regex_spans_per_sentence(text, regex)

        if match_mode == "all_keywords":
            return self._all_keywords_spans(
                text, keywords, max_span=max_span, regex=regex
            )

        spans: list[tuple[int, int, str]] = []
        if regex:
            spans.extend(self._regex_spans_per_sentence(text, regex))
        for kw in sorted(keywords, key=len, reverse=True):
            for idx in self._iter_alias_starts(text, kw):
                spans.append((idx, idx + len(kw), kw))
        return spans

    def _all_keywords_spans(
        self,
        text: str,
        keywords: Sequence[str],
        *,
        max_span: int,
        regex: str,
    ) -> list[tuple[int, int, str]]:
        found: list[tuple[int, int, str]] = []
        if not keywords:
            return self._regex_spans_per_sentence(text, regex) if regex else []

        for sent_start, _sent_end, sentence in iter_strong_sentences(text):
            positions: list[tuple[int, int, str]] = []
            ok = True
            for kw in keywords:
                local = sentence.find(kw)
                if local < 0:
                    ok = False
                    break
                abs_start = sent_start + local
                positions.append((abs_start, abs_start + len(kw), kw))
            if ok and positions:
                span_start = min(p[0] for p in positions)
                span_end = max(p[1] for p in positions)
                if span_end - span_start <= max_span:
                    found.append((span_start, span_end, text[span_start:span_end]))
            if regex:
                compiled = self._knowledge.get_compiled_regex(regex)
                for m in compiled.finditer(sentence):
                    abs_start = sent_start + m.start()
                    abs_end = sent_start + m.end()
                    found.append((abs_start, abs_end, text[abs_start:abs_end]))
        return found

    def _regex_spans_per_sentence(
        self,
        text: str,
        regex: str,
    ) -> list[tuple[int, int, str]]:
        if not regex:
            return []
        compiled = self._knowledge.get_compiled_regex(regex)
        found: list[tuple[int, int, str]] = []
        for sent_start, _sent_end, sentence in iter_strong_sentences(text):
            for m in compiled.finditer(sentence):
                abs_start = sent_start + m.start()
                abs_end = sent_start + m.end()
                found.append((abs_start, abs_end, text[abs_start:abs_end]))
        return found

    def _numeric_ok(
        self,
        text: str,
        pattern: RiskPatternKnowledge,
        *,
        start: int = 0,
        end: int | None = None,
    ) -> bool:
        rule = pattern.numeric_rule
        if rule is None:
            return True
        field_regex = rule.extract_regex
        if end is None:
            end = len(text)
        sent_start, sent_end = strong_sentence_span(text, start)
        search_text = text[sent_start:sent_end]
        compiled = self._knowledge.get_compiled_regex(field_regex)
        m = compiled.search(search_text) or compiled.search(text)
        if not m:
            return False
        try:
            value = float(m.group(1))
        except (IndexError, ValueError) as exc:
            raise ValueError(f"风险模式 {pattern.id} 数值提取失败: {exc}") from exc
        op = rule.operator.value
        threshold = float(rule.threshold)
        if op == ">":
            return value > threshold
        if op == ">=":
            return value >= threshold
        if op == "<":
            return value < threshold
        if op == "<=":
            return value <= threshold
        if op == "==":
            return value == threshold
        raise ValueError(f"不支持的 numeric operator: {op}")