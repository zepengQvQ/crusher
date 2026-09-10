"""规则驱动的金融事实抽取（P2-05）。

模型只可提供候选；本模块完成 span 对齐、单位解析与状态晋级。
金额/比例/期限比较一律经 value_normalizer（Decimal）。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.models.financial_fact import (
    ExtractorSource,
    FactEvidenceRef,
    FactPolarity,
    FinancialFact,
    FinancialFactStatus,
    ValueKind,
    new_fact_id,
)
from app.domain.rules import value_normalizer as vn

_QUALIFIER_MAX = re.compile(
    r"(?:年化(?:收益率?|利率)?|收益率?|利率)[^。；\n]{0,12}?"
    r"(最高|不超过|至多|不高于)\s*([0-9.]+)\s*%"
)
_QUALIFIER_MAX_ALT = re.compile(
    r"(最高|不超过|至多|不高于)\s*([0-9.]+)\s*%"
)
_CONTRAST_RATE = re.compile(
    r"不是\s*([0-9.]+)\s*%\s*[，,]?\s*而是\s*([0-9.]+)\s*%"
)
_CONDITIONAL_RETURN = re.compile(
    r"(满足[^，。；\n]{0,24}(?:条件|后))[^，。；\n]{0,16}?"
    r"(?:收益|年化|利率)[为是]?\s*([0-9.]+)\s*%"
)
_CONDITIONAL_RETURN_ALT = re.compile(
    r"([^，。；\n]{0,24}后)[^，。；\n]{0,8}?"
    r"(?:收益|年化收益率?)[为是]?\s*([0-9.]+)\s*%"
)
_NO_PREPAY_FEE = re.compile(
    r"(不收取|不收|免收|无需支付)[^。；\n]{0,12}?(提前还款)?[^。；\n]{0,8}?违约金"
    r"|提前还款[^。；\n]{0,12}?(不收取|不收|免收|无需支付)[^。；\n]{0,8}?违约金"
)
_BP = re.compile(r"(\d+(?:\.\d+)?)\s*(?:bp|BP|基点)")
_TERM = re.compile(
    r"(?:产品|借款|贷款)?期限[^。；\n]{0,8}?(?:为|是|:|：)?\s*"
    r"(\d+(?:\.\d+)?\s*(?:个?月|年|天))"
)
_TERM_BARE = re.compile(r"(?<![逾赎宽])期限\s*(\d+(?:\.\d+)?\s*(?:个?月|年))")
_TERM_BAD_CONTEXT = ("逾期", "赎回", "到账", "宽限", "未约定", "未披露")
_UNDISCLOSED_FEE = re.compile(
    r"(未披露|未写明|未约定|材料未说明)\s*管理费|管理费\s*(未披露|未写明|未约定)"
)
_MGMT_FEE_VALUE = re.compile(r"管理费\s*为?\s*([0-9.]+)\s*%")


@dataclass
class FinancialFactLedger:
    """一次抽取得到的事实账本。"""

    facts: list[FinancialFact] = field(default_factory=list)

    def by_field(self, field_key: str) -> list[FinancialFact]:
        return [f for f in self.facts if f.field_key == field_key]

    def confirmed(self) -> list[FinancialFact]:
        return [f for f in self.facts if f.status == FinancialFactStatus.CONFIRMED]


class FinancialFactExtractor:
    """确定性事实提取服务；单材料 / 双材料 / 产品对比共用。"""

    def extract(
        self,
        text: str,
        *,
        product_id: str | None = None,
    ) -> FinancialFactLedger:
        text = text or ""
        facts: list[FinancialFact] = []
        facts.extend(self._extract_max_rate(text, product_id))
        facts.extend(self._extract_contrast_rate(text, product_id))
        facts.extend(self._extract_conditional_return(text, product_id))
        facts.extend(self._extract_prepayment_fee(text, product_id))
        facts.extend(self._extract_bp(text, product_id))
        facts.extend(self._extract_term(text, product_id))
        facts.extend(self._extract_management_fee(text, product_id))
        return FinancialFactLedger(facts=facts)

    def _ev(self, text: str, start: int, end: int) -> FactEvidenceRef:
        return FactEvidenceRef(quote=text[start:end], start=start, end=end)

    def _extract_max_rate(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        out: list[FinancialFact] = []
        for pattern in (_QUALIFIER_MAX, _QUALIFIER_MAX_ALT):
            for m in pattern.finditer(text):
                # 避免与「不是A而是B」重复抢占
                window = text[max(0, m.start() - 4) : m.end() + 4]
                if "不是" in window and "而是" in window:
                    continue
                qual = m.group(1)
                pct = m.group(2)
                raw = m.group(0)
                value, unit, _ = vn.normalize_percent_or_bp(f"{pct}%")
                if value is None:
                    continue
                out.append(
                    FinancialFact(
                        fact_id=new_fact_id(),
                        product_id=product_id,
                        field_key="expected_return",
                        raw_value=raw,
                        normalized_value=vn.format_decimal(value),
                        unit=unit,
                        value_kind=ValueKind.percent,
                        polarity=FactPolarity.affirmative,
                        qualifiers=[qual],
                        status=FinancialFactStatus.CONFIRMED,
                        evidence_refs=[self._ev(text, m.start(), m.end())],
                        extractor_source=ExtractorSource.RULE,
                    )
                )
                return out  # 一条即可
        return out

    def _extract_contrast_rate(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        m = _CONTRAST_RATE.search(text)
        if not m:
            return []
        wrong, right = m.group(1), m.group(2)
        value, unit, _ = vn.normalize_percent_or_bp(f"{right}%")
        if value is None:
            return []
        return [
            FinancialFact(
                fact_id=new_fact_id(),
                product_id=product_id,
                field_key="expected_return",
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.percent,
                polarity=FactPolarity.contrastive,
                qualifiers=[],
                negated_raw_value=f"{wrong}%",
                status=FinancialFactStatus.CONFIRMED,
                evidence_refs=[self._ev(text, m.start(), m.end())],
                extractor_source=ExtractorSource.RULE,
            )
        ]

    def _extract_conditional_return(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        for pattern in (_CONDITIONAL_RETURN, _CONDITIONAL_RETURN_ALT):
            m = pattern.search(text)
            if not m:
                continue
            cond, pct = m.group(1), m.group(2)
            value, unit, _ = vn.normalize_percent_or_bp(f"{pct}%")
            if value is None:
                continue
            return [
                FinancialFact(
                    fact_id=new_fact_id(),
                    product_id=product_id,
                    field_key="expected_return",
                    raw_value=m.group(0),
                    normalized_value=vn.format_decimal(value),
                    unit=unit,
                    value_kind=ValueKind.percent,
                    polarity=FactPolarity.affirmative,
                    condition_text=cond.strip(),
                    status=FinancialFactStatus.CONFIRMED,
                    evidence_refs=[self._ev(text, m.start(), m.end())],
                    extractor_source=ExtractorSource.RULE,
                )
            ]
        return []

    def _extract_prepayment_fee(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        m = _NO_PREPAY_FEE.search(text)
        if not m:
            return []
        return [
            FinancialFact(
                fact_id=new_fact_id(),
                product_id=product_id,
                field_key="prepayment_fee",
                raw_value=m.group(0),
                normalized_value="不收取",
                unit=None,
                value_kind=ValueKind.fee,
                polarity=FactPolarity.negative,
                status=FinancialFactStatus.CONFIRMED,
                evidence_refs=[self._ev(text, m.start(), m.end())],
                extractor_source=ExtractorSource.RULE,
            )
        ]

    def _extract_bp(self, text: str, product_id: str | None) -> list[FinancialFact]:
        out: list[FinancialFact] = []
        for m in _BP.finditer(text):
            raw = m.group(0)
            value, unit, _ = vn.normalize_percent_or_bp(raw)
            if value is None:
                continue
            out.append(
                FinancialFact(
                    fact_id=new_fact_id(),
                    product_id=product_id,
                    field_key="basis_points",
                    raw_value=raw,
                    normalized_value=vn.format_decimal(value),
                    unit=unit,
                    value_kind=ValueKind.percent,
                    polarity=FactPolarity.affirmative,
                    status=FinancialFactStatus.CONFIRMED,
                    evidence_refs=[self._ev(text, m.start(), m.end())],
                    extractor_source=ExtractorSource.RULE,
                )
            )
        return out

    def _extract_term(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        for pattern in (_TERM, _TERM_BARE):
            for m in pattern.finditer(text):
                # 句子上下文排除逾期/赎回等伪期限
                left = max(0, m.start() - 8)
                window = text[left : m.end() + 4]
                if any(bad in window for bad in _TERM_BAD_CONTEXT):
                    continue
                if m.start() >= 2 and text[m.start() - 2 : m.start()] in (
                    "逾期",
                    "赎回",
                ):
                    continue
                raw = m.group(1) if m.lastindex else m.group(0)
                months = vn.normalize_term_months(raw)
                if months is None:
                    return [
                        FinancialFact(
                            fact_id=new_fact_id(),
                            product_id=product_id,
                            field_key="term",
                            raw_value=raw,
                            normalized_value=None,
                            unit="month",
                            value_kind=ValueKind.term,
                            status=FinancialFactStatus.UNCERTAIN,
                            evidence_refs=[self._ev(text, m.start(), m.end())],
                            extractor_source=ExtractorSource.RULE,
                        )
                    ]
                return [
                    FinancialFact(
                        fact_id=new_fact_id(),
                        product_id=product_id,
                        field_key="term",
                        raw_value=raw,
                        normalized_value=vn.format_decimal(months),
                        unit="month",
                        value_kind=ValueKind.term,
                        status=FinancialFactStatus.CONFIRMED,
                        evidence_refs=[self._ev(text, m.start(), m.end())],
                        extractor_source=ExtractorSource.RULE,
                    )
                ]
        return []

    def _extract_management_fee(
        self, text: str, product_id: str | None
    ) -> list[FinancialFact]:
        m_und = _UNDISCLOSED_FEE.search(text)
        if m_und:
            return [
                FinancialFact(
                    fact_id=new_fact_id(),
                    product_id=product_id,
                    field_key="management_fee",
                    raw_value=m_und.group(0),
                    normalized_value=None,
                    unit=None,
                    value_kind=ValueKind.fee,
                    status=FinancialFactStatus.NOT_DISCLOSED,
                    evidence_refs=[self._ev(text, m_und.start(), m_und.end())],
                    extractor_source=ExtractorSource.RULE,
                )
            ]
        m = _MGMT_FEE_VALUE.search(text)
        if not m:
            return []
        value, unit, _ = vn.normalize_percent_or_bp(f"{m.group(1)}%")
        if value is None:
            return []
        return [
            FinancialFact(
                fact_id=new_fact_id(),
                product_id=product_id,
                field_key="management_fee",
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.fee,
                status=FinancialFactStatus.CONFIRMED,
                evidence_refs=[self._ev(text, m.start(), m.end())],
                extractor_source=ExtractorSource.RULE,
            )
        ]


def facts_comparable(a: FinancialFact, b: FinancialFact) -> bool:
    """同源标准化后是否可视为相同。"""
    if a.field_key != b.field_key:
        return False
    if a.normalized_value is None or b.normalized_value is None:
        return False
    return a.normalized_value == b.normalized_value and a.unit == b.unit
