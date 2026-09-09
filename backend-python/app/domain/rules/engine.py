"""规则引擎：产品识别 + 风险模式匹配（确定性，不调用模型）。"""
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.negation import (
    DEFAULT_NEGATION_CUES,
    expand_to_clause,
    is_negated_near,
    strong_sentence_span,
)

# 低于该置信度的产品候选丢弃，整体视为 unknown（调用方处理）
PRODUCT_CONFIDENCE_THRESHOLD = 0.5
# 同一强句内关键词首尾最大距离（字符）
MAX_KEYWORD_SPAN = 48


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
            if product_type and product_type not in pattern.get(
                "applicable_product_types", []
            ):
                continue
            hit = self._match_one_pattern(text, pattern)
            if hit is not None:
                matched.append(hit)
        return matched

    def _score_product(self, text: str, product: dict) -> ProductHit | None:
        strong = list(product.get("strong_aliases") or [])
        weak = list(product.get("weak_aliases") or [])
        if not strong and not weak:
            aliases = list(product.get("aliases") or [])
            for a in aliases:
                if len(a) <= 2:
                    weak.append(a)
                else:
                    strong.append(a)

        cues = tuple(product.get("negation_cues") or DEFAULT_NEGATION_CUES)
        window = int(product.get("context_window") or 16)
        evidence: list[str] = []
        strong_score = 0.0
        weak_score = 0.0

        for alias in strong:
            idx = text.find(alias)
            if idx < 0:
                continue
            if is_negated_near(text, idx, cues=cues, window=window):
                continue
            strong_score = max(strong_score, 0.85)
            evidence.append(alias)

        for alias in weak:
            idx = text.find(alias)
            if idx < 0:
                continue
            if is_negated_near(text, idx, cues=cues, window=window):
                continue
            weak_score = max(weak_score, 0.4)
            evidence.append(alias)

        confidence = max(strong_score, weak_score)
        if confidence <= 0:
            return None
        return ProductHit(
            product_id=str(product["id"]),
            product_name=str(product.get("name") or product["id"]),
            confidence=confidence,
            evidence_quotes=evidence,
        )

    def _match_one_pattern(self, text: str, pattern: dict) -> RiskHit | None:
        pattern_id = str(pattern["id"])
        if pattern_id == "principal_not_guaranteed":
            if re.search(r"确保本金|本金安全|保证本金", text):
                if not re.search(r"不保证本金|本金(可能)?(面临)?亏损|本金损失|本金受损", text):
                    return None

        cues = tuple(pattern.get("negation_cues") or DEFAULT_NEGATION_CUES)
        window = int(pattern.get("context_window") or 16)
        match_mode = str(pattern.get("match_mode") or "regex_or_keywords")

        span = self._find_span(text, pattern, match_mode)
        if span is None:
            return None
        start, end, quote = span
        # 锚定命中片段右端：覆盖「提前还款不收违约金」这类否定夹在中间的句子
        if is_negated_near(text, end, cues=cues, window=window):
            return None
        if is_negated_near(text, start, cues=cues, window=window):
            return None

        if not self._numeric_ok(text, pattern, start=start, end=end):
            return None

        start, end, quote = expand_to_clause(text, start, end)
        return RiskHit(
            pattern_id=pattern_id,
            name=str(pattern["name"]),
            risk_level=str(pattern.get("risk_level") or "中"),
            explanation=str(pattern.get("explanation") or ""),
            quote=quote,
            start=start,
            end=end,
            confidence=0.9,
        )

    def _find_span(
        self,
        text: str,
        pattern: dict,
        match_mode: str,
    ) -> tuple[int, int, str] | None:
        regex = pattern.get("regex") or ""
        keywords: Sequence[str] = pattern.get("keywords") or []
        max_span = int(pattern.get("max_keyword_span") or MAX_KEYWORD_SPAN)

        if match_mode == "regex_only":
            return self._regex_span(text, regex)

        if match_mode == "all_keywords":
            return self._all_keywords_span(text, keywords, max_span=max_span, regex=regex)

        # 默认：先 regex，再 any keyword（关键词不得单独充当高风险泛化触发时，
        # 各 pattern 应改用 regex_only / all_keywords）
        if regex:
            span = self._regex_span(text, regex)
            if span is not None:
                return span
        for kw in sorted(keywords, key=len, reverse=True):
            idx = text.find(kw)
            if idx >= 0:
                return idx, idx + len(kw), kw
        return None

    def _all_keywords_span(
        self,
        text: str,
        keywords: Sequence[str],
        *,
        max_span: int,
        regex: str,
    ) -> tuple[int, int, str] | None:
        if not keywords:
            return self._regex_span(text, regex) if regex else None

        # 在每个强句内寻找全部关键词
        cursor = 0
        while cursor < len(text):
            sent_start, sent_end = strong_sentence_span(text, cursor)
            sentence = text[sent_start:sent_end]
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
                    return span_start, span_end, text[span_start:span_end]
            if regex:
                compiled = self._knowledge.get_compiled_regex(regex)
                m = compiled.search(sentence)
                if m:
                    abs_start = sent_start + m.start()
                    abs_end = sent_start + m.end()
                    return abs_start, abs_end, text[abs_start:abs_end]
            if sent_end <= cursor:
                cursor += 1
            else:
                cursor = sent_end
        return None

    def _regex_span(self, text: str, regex: str) -> tuple[int, int, str] | None:
        if not regex:
            return None
        compiled = self._knowledge.get_compiled_regex(regex)
        m = compiled.search(text)
        if not m:
            return None
        return m.start(), m.end(), m.group(0)

    def _numeric_ok(
        self,
        text: str,
        pattern: dict,
        *,
        start: int = 0,
        end: int | None = None,
    ) -> bool:
        rule = pattern.get("numeric_rule")
        if not rule:
            return True
        field_regex = str(rule.get("extract_regex") or "")
        if not field_regex:
            raise ValueError(f"风险模式 {pattern.get('id')} 的 numeric_rule 缺少 extract_regex")
        # 优先在命中片段所在强句内取数，避免跨句误用
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
            raise ValueError(
                f"风险模式 {pattern.get('id')} 数值提取失败: {exc}"
            ) from exc
        op = str(rule.get("operator") or ">")
        threshold = float(rule.get("threshold") or 0)
        if op == ">":
            return value > threshold
        if op == ">=":
            return value >= threshold
        if op == "<":
            return value < threshold
        if op == "<=":
            return value <= threshold
        raise ValueError(f"不支持的 numeric operator: {op}")
