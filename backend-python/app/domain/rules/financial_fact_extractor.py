"""规则驱动的金融事实抽取（P2-05 / P2-RC-02）。

模型只可提供候选；本模块完成 span 对齐、单位解析与状态晋级。
金额/比例/期限比较一律经 value_normalizer（Decimal）。
fact_id 跨运行稳定。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.domain.models.financial_fact import (
    ExtractorSource,
    FactEvidenceRef,
    FactPolarity,
    FinancialFact,
    FinancialFactStatus,
    ValueKind,
    stable_fact_id,
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
_CHARGE_PREPAY_FEE = re.compile(
    r"(提前还款[^。；\n]{0,24}?(需支付|支付|收取)[^。；\n]{0,16}?违约金"
    r"|(需支付|支付|收取)[^。；\n]{0,12}?提前还款[^。；\n]{0,12}?违约金)"
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
_AMOUNT = re.compile(
    r"(?:借款|贷款)?金额\s*(?:为)?\s*[:：]?\s*"
    r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(万元|万|元)?"
)
_ANNUAL_RATE = re.compile(
    r"(?:年化利率|贷款利率|借款利率)\s*(?:为|是|:|：)?\s*([0-9.]+)\s*%"
)
_PENALTY = re.compile(r"(逾期[^。；\n]{0,40}罚息[^。；\n]{0,40}|罚息[^。；\n]{0,40})")
_REPAYMENT = re.compile(r"(等额本息|等额本金|先息后本|按月付息|到期还本)")
_RISK_GRADE = re.compile(
    r"(?:产品风险(?:等级|评级)|(?<!客户)风险(?:等级|评级))\s*[:：]?\s*(R[1-5])(?!\d)",
    re.I,
)
_PRINCIPAL_NEG = re.compile(r"(不承诺保本|非保本|不保证本金|本金不保证|不保本)")
_PRINCIPAL_POS = re.compile(r"(确保本金安全|保证本金|本金保障|本金到期全额返还|(?<![非不])保本)")
_EARLY_REDEEM = re.compile(
    r"(不支持提前赎回|不支持提前支取|不可提前赎回|不可提前支取|"
    r"可提前赎回|支持提前赎回|支持提前支取)"
)
_RETURN_RANGE = re.compile(
    r"(?:到期)?年化收益率?\s*(?:为)?\s*[:：]?\s*"
    r"([0-9.]+%\s*[-~～至到]\s*[0-9.]+%)"
)
_RETURN_SINGLE = re.compile(
    r"(?:到期)?年化收益率?\s*(?:为)?\s*[:：]?\s*([0-9.]+)\s*%"
)


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
        source_id: str | None = None,
    ) -> FinancialFactLedger:
        text = text or ""
        ctx = (text, product_id, source_id)
        facts: list[FinancialFact] = []
        facts.extend(self._extract_amount(text, ctx))
        facts.extend(self._extract_max_rate(text, ctx))
        facts.extend(self._extract_contrast_rate(text, ctx))
        facts.extend(self._extract_conditional_return(text, ctx))
        facts.extend(self._extract_annual_rate(text, ctx))
        facts.extend(self._extract_return_range(text, ctx))
        facts.extend(self._extract_return_single(text, ctx))
        facts.extend(self._extract_prepayment_fee(text, ctx))
        facts.extend(self._extract_bp(text, ctx))
        facts.extend(self._extract_term(text, ctx))
        facts.extend(self._extract_management_fee(text, ctx))
        facts.extend(self._extract_penalty(text, ctx))
        facts.extend(self._extract_repayment(text, ctx))
        facts.extend(self._extract_risk_grade(text, ctx))
        facts.extend(self._extract_principal(text, ctx))
        facts.extend(self._extract_early_redeem(text, ctx))
        return FinancialFactLedger(facts=facts)

    def _ev(self, text: str, start: int, end: int) -> FactEvidenceRef:
        return FactEvidenceRef(quote=text[start:end], start=start, end=end)

    def _fact(
        self,
        text: str,
        ctx: tuple[str, str | None, str | None],
        *,
        field_key: str,
        start: int,
        end: int,
        raw_value: str,
        normalized_value: str | None,
        unit: str | None,
        value_kind: ValueKind,
        status: FinancialFactStatus = FinancialFactStatus.CONFIRMED,
        polarity: FactPolarity = FactPolarity.affirmative,
        qualifiers: list[str] | None = None,
        condition_text: str | None = None,
        negated_raw_value: str | None = None,
    ) -> FinancialFact:
        _src, product_id, source_id = ctx
        return FinancialFact(
            fact_id=stable_fact_id(
                source_text=text,
                product_id=product_id,
                source_id=source_id,
                field_key=field_key,
                start=start,
                end=end,
                normalized_value=normalized_value,
            ),
            product_id=product_id,
            source_id=source_id,
            field_key=field_key,
            raw_value=raw_value,
            normalized_value=normalized_value,
            unit=unit,
            value_kind=value_kind,
            polarity=polarity,
            qualifiers=list(qualifiers or []),
            condition_text=condition_text,
            negated_raw_value=negated_raw_value,
            status=status,
            evidence_refs=[self._ev(text, start, end)],
            extractor_source=ExtractorSource.RULE,
        )

    def _extract_amount(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _AMOUNT.search(text)
        if not m:
            return []
        raw_num = m.group(1).replace(",", "")
        unit_raw = m.group(2) or "元"
        try:
            num = Decimal(raw_num)
        except (InvalidOperation, ValueError):
            return []
        if unit_raw in ("万", "万元"):
            num *= Decimal("10000")
        display = f"{m.group(1)}{unit_raw}"
        # 证据指向原文金额片段（如「10万元」），不是标准化后的 100000
        quote_start = m.start(1)
        quote_end = m.end(2) if m.group(2) else m.end(1)
        return [
            self._fact(
                text,
                ctx,
                field_key="amount",
                start=quote_start,
                end=quote_end,
                raw_value=text[quote_start:quote_end] or display,
                normalized_value=vn.format_decimal(num),
                unit="CNY",
                value_kind=ValueKind.amount,
            )
        ]

    def _extract_annual_rate(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _ANNUAL_RATE.search(text)
        if not m:
            return []
        value, unit, _ = vn.normalize_percent_or_bp(f"{m.group(1)}%")
        if value is None:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="annual_interest_rate",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.percent,
            )
        ]

    def _extract_return_range(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _RETURN_RANGE.search(text)
        if not m:
            return []
        span = m.group(0)
        return [
            self._fact(
                text,
                ctx,
                field_key="expected_return",
                start=m.start(),
                end=m.end(),
                raw_value=span,
                normalized_value=m.group(1),
                unit="%",
                value_kind=ValueKind.percent,
                qualifiers=["区间"],
            )
        ]

    def _extract_return_single(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        # 若已有区间/最高/条件/对比收益，不再重复单值
        if any(
            x.search(text)
            for x in (
                _RETURN_RANGE,
                _QUALIFIER_MAX,
                _QUALIFIER_MAX_ALT,
                _CONDITIONAL_RETURN,
                _CONDITIONAL_RETURN_ALT,
                _CONTRAST_RATE,
            )
        ):
            return []
        m = _RETURN_SINGLE.search(text)
        if not m:
            return []
        value, unit, nature = vn.normalize_percent_or_bp(f"{m.group(1)}%")
        if value is None or nature == "range":
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="expected_return",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.percent,
            )
        ]

    def _extract_max_rate(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        out: list[FinancialFact] = []
        for pattern in (_QUALIFIER_MAX, _QUALIFIER_MAX_ALT):
            for m in pattern.finditer(text):
                window = text[max(0, m.start() - 4) : m.end() + 4]
                if "不是" in window and "而是" in window:
                    continue
                qual = m.group(1)
                pct = m.group(2)
                value, unit, _ = vn.normalize_percent_or_bp(f"{pct}%")
                if value is None:
                    continue
                out.append(
                    self._fact(
                        text,
                        ctx,
                        field_key="expected_return",
                        start=m.start(),
                        end=m.end(),
                        raw_value=m.group(0),
                        normalized_value=vn.format_decimal(value),
                        unit=unit,
                        value_kind=ValueKind.percent,
                        qualifiers=[qual],
                    )
                )
                return out
        return out

    def _extract_contrast_rate(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _CONTRAST_RATE.search(text)
        if not m:
            return []
        wrong, right = m.group(1), m.group(2)
        value, unit, _ = vn.normalize_percent_or_bp(f"{right}%")
        if value is None:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="expected_return",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.percent,
                polarity=FactPolarity.contrastive,
                negated_raw_value=f"{wrong}%",
            )
        ]

    def _extract_conditional_return(
        self, text: str, ctx: tuple[str, str | None, str | None]
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
                self._fact(
                    text,
                    ctx,
                    field_key="expected_return",
                    start=m.start(),
                    end=m.end(),
                    raw_value=m.group(0),
                    normalized_value=vn.format_decimal(value),
                    unit=unit,
                    value_kind=ValueKind.percent,
                    condition_text=cond.strip(),
                )
            ]
        return []

    def _extract_prepayment_fee(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _NO_PREPAY_FEE.search(text)
        if m:
            return [
                self._fact(
                    text,
                    ctx,
                    field_key="prepayment_fee",
                    start=m.start(),
                    end=m.end(),
                    raw_value=m.group(0),
                    normalized_value="不收取",
                    unit=None,
                    value_kind=ValueKind.fee,
                    polarity=FactPolarity.negative,
                )
            ]
        m2 = _CHARGE_PREPAY_FEE.search(text)
        if not m2:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="prepayment_fee",
                start=m2.start(),
                end=m2.end(),
                raw_value=m2.group(0),
                normalized_value="收取",
                unit=None,
                value_kind=ValueKind.fee,
                polarity=FactPolarity.affirmative,
            )
        ]

    def _extract_bp(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        out: list[FinancialFact] = []
        for m in _BP.finditer(text):
            raw = m.group(0)
            value, unit, _ = vn.normalize_percent_or_bp(raw)
            if value is None:
                continue
            out.append(
                self._fact(
                    text,
                    ctx,
                    field_key="basis_points",
                    start=m.start(),
                    end=m.end(),
                    raw_value=raw,
                    normalized_value=vn.format_decimal(value),
                    unit=unit,
                    value_kind=ValueKind.percent,
                )
            )
        return out

    def _extract_term(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        for pattern in (_TERM, _TERM_BARE):
            for m in pattern.finditer(text):
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
                        self._fact(
                            text,
                            ctx,
                            field_key="term",
                            start=m.start(),
                            end=m.end(),
                            raw_value=raw,
                            normalized_value=None,
                            unit="month",
                            value_kind=ValueKind.term,
                            status=FinancialFactStatus.UNCERTAIN,
                        )
                    ]
                return [
                    self._fact(
                        text,
                        ctx,
                        field_key="term",
                        start=m.start(),
                        end=m.end(),
                        raw_value=raw,
                        normalized_value=vn.format_decimal(months),
                        unit="month",
                        value_kind=ValueKind.term,
                    )
                ]
        return []

    def _extract_management_fee(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m_und = _UNDISCLOSED_FEE.search(text)
        if m_und:
            return [
                self._fact(
                    text,
                    ctx,
                    field_key="management_fee",
                    start=m_und.start(),
                    end=m_und.end(),
                    raw_value=m_und.group(0),
                    normalized_value=None,
                    unit=None,
                    value_kind=ValueKind.fee,
                    status=FinancialFactStatus.NOT_DISCLOSED,
                )
            ]
        m = _MGMT_FEE_VALUE.search(text)
        if not m:
            return []
        value, unit, _ = vn.normalize_percent_or_bp(f"{m.group(1)}%")
        if value is None:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="management_fee",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(0),
                normalized_value=vn.format_decimal(value),
                unit=unit,
                value_kind=ValueKind.fee,
            )
        ]

    def _extract_penalty(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _PENALTY.search(text)
        if not m:
            return []
        raw = m.group(0).strip(" ，,")
        return [
            self._fact(
                text,
                ctx,
                field_key="penalty_interest",
                start=m.start(),
                end=m.start() + len(raw),
                raw_value=raw,
                normalized_value=raw,
                unit=None,
                value_kind=ValueKind.text,
            )
        ]

    def _extract_repayment(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _REPAYMENT.search(text)
        if not m:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="repayment_method",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(1),
                normalized_value=m.group(1),
                unit=None,
                value_kind=ValueKind.text,
            )
        ]

    def _extract_risk_grade(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _RISK_GRADE.search(text)
        if not m:
            return []
        clause = text[max(0, m.start() - 12) : m.end() + 8]
        if "客户" in clause or "未披露" in clause or "未约定" in clause:
            return []
        grade = m.group(1).upper()
        return [
            self._fact(
                text,
                ctx,
                field_key="product_risk_grade",
                start=m.start(1),
                end=m.end(1),
                raw_value=grade,
                normalized_value=grade,
                unit=None,
                value_kind=ValueKind.text,
            )
        ]

    def _extract_principal(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _PRINCIPAL_NEG.search(text)
        if m:
            return [
                self._fact(
                    text,
                    ctx,
                    field_key="principal_protection",
                    start=m.start(),
                    end=m.end(),
                    raw_value=m.group(1),
                    normalized_value=m.group(1),
                    unit=None,
                    value_kind=ValueKind.text,
                    polarity=FactPolarity.negative,
                )
            ]
        m2 = _PRINCIPAL_POS.search(text)
        if not m2:
            return []
        clause = text[max(0, m2.start() - 8) : m2.end() + 8]
        if any(x in clause for x in ("不承诺", "非保本", "不保证", "不保本")):
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="principal_protection",
                start=m2.start(),
                end=m2.end(),
                raw_value=m2.group(1),
                normalized_value=m2.group(1),
                unit=None,
                value_kind=ValueKind.text,
            )
        ]

    def _extract_early_redeem(
        self, text: str, ctx: tuple[str, str | None, str | None]
    ) -> list[FinancialFact]:
        m = _EARLY_REDEEM.search(text)
        if not m:
            return []
        return [
            self._fact(
                text,
                ctx,
                field_key="early_redemption",
                start=m.start(),
                end=m.end(),
                raw_value=m.group(1),
                normalized_value=m.group(1),
                unit=None,
                value_kind=ValueKind.text,
            )
        ]


def facts_comparable(a: FinancialFact, b: FinancialFact) -> bool:
    """同源标准化后是否可视为相同。"""
    if a.field_key != b.field_key:
        return False
    if a.normalized_value is None or b.normalized_value is None:
        return False
    return a.normalized_value == b.normalized_value and a.unit == b.unit
