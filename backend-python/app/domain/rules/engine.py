"""规则引擎：产品识别 + 风险模式匹配（确定性，不调用模型）。"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.negation import DEFAULT_NEGATION_CUES, is_negated_near

# 低于该置信度的产品候选丢弃，整体视为 unknown（调用方处理）
PRODUCT_CONFIDENCE_THRESHOLD = 0.5


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
        product_type: Optional[str] = None,
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

    def _score_product(self, text: str, product: dict) -> Optional[ProductHit]:
        strong = list(product.get("strong_aliases") or [])
        weak = list(product.get("weak_aliases") or [])
        # 兼容旧字段：未拆分时 aliases 全部当 strong，但过短弱信号需降权
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

    def _match_one_pattern(self, text: str, pattern: dict) -> Optional[RiskHit]:
        pattern_id = str(pattern["id"])
        # 正向保障类表述：不得命中「本金不保证」
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
        # 锚定片段末尾：覆盖「提前还款不收违约金」这类否定夹在中间的句子
        if is_negated_near(text, end, cues=cues, window=window):
            return None

        if not self._numeric_ok(text, pattern):
            return None

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
    ) -> Optional[tuple[int, int, str]]:
        regex = pattern.get("regex") or ""
        keywords: Sequence[str] = pattern.get("keywords") or []

        if match_mode == "regex_only":
            return self._regex_span(text, regex)

        if match_mode == "all_keywords":
            if not keywords or any(kw not in text for kw in keywords):
                # 关键词不全时仍可尝试 regex
                if regex:
                    return self._regex_span(text, regex)
                return None
            # 取原文中最靠后的关键词作证据（通常是风险宾语，如「违约金」）
            positioned = [(text.find(kw), kw) for kw in keywords]
            positioned = [(i, kw) for i, kw in positioned if i >= 0]
            idx, key = max(positioned, key=lambda item: item[0])
            return idx, idx + len(key), key

        # 默认：先 regex，再 any keyword
        if regex:
            span = self._regex_span(text, regex)
            if span is not None:
                return span
        for kw in sorted(keywords, key=len, reverse=True):
            idx = text.find(kw)
            if idx >= 0:
                return idx, idx + len(kw), kw
        return None

    def _regex_span(self, text: str, regex: str) -> Optional[tuple[int, int, str]]:
        if not regex:
            return None
        compiled = self._knowledge.get_compiled_regex(regex)
        m = compiled.search(text)
        if not m:
            return None
        return m.start(), m.end(), m.group(0)

    def _numeric_ok(self, text: str, pattern: dict) -> bool:
        rule = pattern.get("numeric_rule")
        if not rule:
            return True
        field_regex = str(rule.get("extract_regex") or "")
        if not field_regex:
            raise ValueError(f"风险模式 {pattern.get('id')} 的 numeric_rule 缺少 extract_regex")
        compiled = self._knowledge.get_compiled_regex(field_regex)
        m = compiled.search(text)
        if not m:
            # 没有数值则不凭纯关键词报「高额」类风险
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
