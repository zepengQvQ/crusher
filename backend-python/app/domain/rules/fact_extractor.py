"""从原文抽取关键参数（按产品拆分）；行业常识只进 general_reference。

Java 对照：产品专属 FactExtractor；候选→上下文过滤→极性→规范化。
业务不变量：不确定则 not_disclosed；金额只用 Decimal；知识库不得写成 document_fact。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.domain.models import GeneralReference, KeyParameter, MissingDisclosure
from app.domain.models.enums import FactStatus, ParameterKey
from app.domain.ports.protocols import KnowledgeRepository
from app.domain.rules.negation import strong_sentence_span

_AMOUNT_RE = re.compile(
    r"(?:借款|贷款)金额\s*(?:为)?\s*[:：]?\s*"
    r"(?P<num>\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)\s*(?P<unit>万元|万|元)?",
)

_PRODUCT_GRADE_RE = re.compile(
    r"产品风险(?:等级|评级)\s*[:：]?\s*(R[1-5])(?!\d)",
    re.IGNORECASE,
)

_RETURN_RANGE_RE = re.compile(
    r"(?:到期)?年化收益率?\s*(?:为)?\s*[:：]?\s*"
    r"([0-9.]+%\s*[-~～至到]\s*[0-9.]+%)",
)
_RETURN_SINGLE_RE = re.compile(
    r"(?:到期)?年化收益率?\s*(?:为)?\s*[:：]?\s*([0-9.]+%)",
)


@dataclass
class ExtractResult:
    key_parameters: list[KeyParameter] = field(default_factory=list)
    missing_disclosures: list[MissingDisclosure] = field(default_factory=list)
    general_references: list[GeneralReference] = field(default_factory=list)
    pending_questions: list[str] = field(default_factory=list)


class FactExtractor:
    """只采信原文；产品知识库提示不得写入 document_fact。"""

    def __init__(self, knowledge: KnowledgeRepository) -> None:
        self._knowledge = knowledge

    def extract(self, text: str, product_type_id: str | None = None) -> ExtractResult:
        text = text or ""
        if product_type_id == "loan":
            result = self.extract_loan(text)
        elif product_type_id == "structured_deposit":
            result = self.extract_structured_deposit(text)
        else:
            result = ExtractResult()
        result.general_references = self._general_refs_for_product(product_type_id)
        result.pending_questions = []
        return result

    def extract_structured_deposit(self, text: str) -> ExtractResult:
        """结构性存款专属字段抽取。"""
        params: list[KeyParameter] = []
        missing: list[MissingDisclosure] = []

        self._add_param(
            params,
            missing,
            key=ParameterKey.term,
            label="产品期限",
            value=self._extract_deposit_term(text),
            question="合同是否明确产品期限？",
        )

        returns = self._collect_deposit_returns(text)
        if returns:
            params.append(
                KeyParameter(
                    key=ParameterKey.expected_return,
                    label="预期/到期收益率",
                    value=" / ".join(returns),
                    status=FactStatus.document_fact,
                )
            )
        else:
            self._add_param(
                params,
                missing,
                key=ParameterKey.expected_return,
                label="预期/到期收益率",
                value=None,
                question="合同是否写明预期/到期收益率？",
            )

        self._add_param(
            params,
            missing,
            key=ParameterKey.early_redemption,
            label="提前赎回/支取",
            value=self._extract_early_redemption(text),
            question="是否支持提前赎回或提前支取？",
        )
        self._add_param(
            params,
            missing,
            key=ParameterKey.fee_structure,
            label="费用结构",
            value=self._first_match(
                text,
                [
                    re.compile(r"(管理费\s*为?\s*[0-9.]+\s*%[^，。；]*)"),
                    re.compile(r"(手续费[^，。；]{0,20})"),
                    re.compile(r"(托管费\s*为?\s*[0-9.]+\s*%)"),
                ],
            ),
            question="费用（管理费/手续费等）如何收取？",
        )
        self._add_param(
            params,
            missing,
            key=ParameterKey.principal_protection,
            label="本金保障",
            value=self._extract_principal_protection(text),
            question="合同是否明确承诺本金保障？",
        )
        self._add_risk_grade(params, missing, text)
        return ExtractResult(key_parameters=params, missing_disclosures=missing)

    def extract_loan(self, text: str) -> ExtractResult:
        """消费贷专属字段抽取。"""
        params: list[KeyParameter] = []
        missing: list[MissingDisclosure] = []

        self._add_param(
            params,
            missing,
            key=ParameterKey.term,
            label="借款期限",
            value=self._extract_loan_term(text),
            question="合同是否明确借款期限？",
        )

        self._add_param(
            params,
            missing,
            key=ParameterKey.annual_interest_rate,
            label="年化利率",
            value=self._extract_loan_annual_rate(text),
            question="合同是否写明年化利率？",
        )

        self._add_param(
            params,
            missing,
            key=ParameterKey.repayment_method,
            label="还款方式",
            value=self._extract_repayment_method(text),
            question="合同是否写明还款方式？",
        )

        penalty = self._first_match(
            text,
            [
                re.compile(r"(逾期[^。；\n]{0,40}罚息[^。；\n]{0,40})"),
                re.compile(r"(罚息[^。；\n]{0,40})"),
            ],
        )
        self._add_param(
            params,
            missing,
            key=ParameterKey.penalty_interest,
            label="罚息约定",
            value=penalty.strip(" ，,") if penalty else None,
            question="合同是否约定逾期罚息？",
        )

        self._add_param(
            params,
            missing,
            key=ParameterKey.prepayment_fee,
            label="提前还款费用",
            value=self._extract_prepayment_fee(text),
            question="提前还款是否收取违约金或手续费？",
        )

        amount = self._extract_loan_amount(text)
        if amount is not None:
            params.append(amount)

        self._add_risk_grade(params, missing, text)
        return ExtractResult(key_parameters=params, missing_disclosures=missing)

    # --- 字段级抽取 ---

    def _extract_deposit_term(self, text: str) -> str | None:
        patterns = [
            re.compile(r"(?:产品|存款)期限\s*[:：]?\s*(\d+\s*(?:天|个?月|年))"),
            re.compile(r"期限\s*为?\s*(\d+\s*(?:天|个?月|年))"),
        ]
        for pattern in patterns:
            for m in pattern.finditer(text):
                clause = self._clause_around(text, m.start())
                if any(bad in clause for bad in ("赎回", "到账", "逾期", "宽限")):
                    continue
                if "未约定" in clause or "未披露" in clause:
                    continue
                return m.group(1).replace(" ", "")
        return None

    def _extract_loan_term(self, text: str) -> str | None:
        patterns = [
            re.compile(r"(?:借款|贷款)期限\s*[:：]?\s*(\d+\s*(?:个?月|天|年))"),
            re.compile(r"期限\s*为?\s*(\d+\s*(?:个?月|天|年))"),
        ]
        for pattern in patterns:
            for m in pattern.finditer(text):
                clause = self._clause_around(text, m.start())
                if any(bad in clause for bad in ("逾期", "宽限", "赎回")):
                    continue
                if "未约定" in clause or "未披露" in clause:
                    continue
                return m.group(1).replace(" ", "")
        return None

    def _extract_loan_annual_rate(self, text: str) -> str | None:
        patterns = [
            re.compile(r"年化利率\s*(?:（[^）]*）)?\s*(?:为)?\s*[:：]?\s*([0-9.]+%)"),
            re.compile(r"年利率\s*(?:为)?\s*[:：]?\s*([0-9.]+%)"),
            re.compile(r"正常借款年化利率\s*(?:为)?\s*[:：]?\s*([0-9.]+%)"),
        ]
        for pattern in patterns:
            for m in pattern.finditer(text):
                clause = self._clause_around(text, m.start())
                if any(bad in clause for bad in ("罚息", "逾期罚息")):
                    continue
                return m.group(1)
        return None

    def _extract_repayment_method(self, text: str) -> str | None:
        # 「不是 A 而是 B」优先取 B
        m = re.search(
            r"还款方式\s*不是\s*(等额本息|等额本金|先息后本|到期一次性还本付息)"
            r"[^。；\n]{0,20}而是\s*(等额本息|等额本金|先息后本|到期一次性还本付息)",
            text,
        )
        if m:
            return m.group(2)
        m = re.search(
            r"不是\s*(等额本息)[^。；\n]{0,20}而是\s*(等额本金)",
            text,
        )
        if m:
            return m.group(2)
        return self._first_match(
            text,
            [
                re.compile(r"(等额本息|等额本金|先息后本|到期一次性还本付息)(?:还款(?:方式)?)?"),
                re.compile(r"还款方式\s*[:：]?\s*([^，。；\n]{2,20})"),
            ],
        )

    def _extract_prepayment_fee(self, text: str) -> str | None:
        m = re.search(
            r"((?:不收取?|免收|无需支付)提前还款(?:违约金|手续费|费用)"
            r"|提前还款(?:违约金|手续费|费用)(?:免收|不收取?))",
            text,
        )
        if m:
            return m.group(1)
        m = re.search(r"(提前还款[^。；\n]{0,40}(?:违约金|手续费|费用)[^。；\n]{0,20})", text)
        if m:
            clause = m.group(1)
            if any(x in clause for x in ("不收", "免收", "无需", "减免")):
                return clause.strip(" ，,")
            return clause.strip(" ，,")
        return None

    def _extract_principal_protection(self, text: str) -> str | None:
        m = re.search(r"(不承诺保本|非保本|不保证本金|本金不保证|不保本)", text)
        if m:
            return m.group(1)
        m = re.search(r"(确保本金安全|保证本金|本金保障|本金到期全额返还|保本)", text)
        if m:
            # 若同句已有否定，不再输出肯定保本
            clause = self._clause_around(text, m.start())
            if any(x in clause for x in ("不承诺", "非保本", "不保证", "不保本")):
                return None
            return m.group(1)
        return None

    def _extract_early_redemption(self, text: str) -> str | None:
        patterns = [
            re.compile(
                r"(不支持提前赎回|不支持提前支取|不可提前赎回|不可提前支取|"
                r"可提前赎回|支持提前赎回|支持提前支取)"
            ),
        ]
        return self._first_match(text, patterns)

    def _extract_loan_amount(self, text: str) -> KeyParameter | None:
        m = _AMOUNT_RE.search(text)
        if not m:
            return None
        raw_num = m.group("num").replace(",", "")
        unit = m.group("unit") or "元"
        try:
            num = Decimal(raw_num)
        except (InvalidOperation, ValueError):
            return None
        if unit in ("万", "万元"):
            num = num * Decimal("10000")
        return KeyParameter(
            key=ParameterKey.amount,
            label="借款金额",
            value=f"{m.group('num')}{unit}",
            status=FactStatus.document_fact,
            amount=num,
        )

    def _add_risk_grade(
        self,
        params: list[KeyParameter],
        missing: list[MissingDisclosure],
        text: str,
    ) -> None:
        grade = None
        m = _PRODUCT_GRADE_RE.search(text)
        if m:
            grade = (m.group(1) or "").upper() or None
            clause = self._clause_around(text, m.start())
            if "未披露" in clause or "未约定" in clause:
                grade = None
        # 兼容旧样例「风险等级：R2」但拒绝「客户评级」
        if grade is None:
            m2 = re.search(r"(?<!客户)(?:风险(?:等级|评级))\s*[:：]?\s*(R[1-5])(?!\d)", text, re.I)
            if m2:
                clause = self._clause_around(text, m2.start())
                if "客户" in clause:
                    m2 = None
                elif "未披露" in clause or "未约定" in clause:
                    m2 = None
                else:
                    grade = m2.group(1).upper()
        if grade:
            params.append(
                KeyParameter(
                    key=ParameterKey.product_risk_grade,
                    label="产品风险评级",
                    value=grade,
                    status=FactStatus.document_fact,
                )
            )
        else:
            self._add_param(
                params,
                missing,
                key=ParameterKey.product_risk_grade,
                label="产品风险评级",
                value=None,
                question="合同是否写明产品风险评级（如 R1～R5）？",
            )

    @staticmethod
    def _collect_deposit_returns(text: str) -> list[str]:
        seen: list[str] = []
        for m in _RETURN_RANGE_RE.finditer(text):
            val = re.sub(r"\s+", "", m.group(1))
            val = val.replace("至", "-").replace("到", "-").replace("～", "-").replace("~", "-")
            if val not in seen:
                seen.append(val)
        if seen:
            return seen
        for m in _RETURN_SINGLE_RE.finditer(text):
            g = m.group(1)
            if g and g not in seen:
                seen.append(g)
        return seen

    @staticmethod
    def _clause_around(text: str, pos: int) -> str:
        start, end = strong_sentence_span(text, pos)
        # 再按逗号收紧，避免跨分句误判
        left = pos
        while left > start and text[left - 1] not in "，,":
            left -= 1
        right = pos
        while right < end and text[right] not in "，,":
            right += 1
        return text[left:right]

    @staticmethod
    def _add_param(
        params: list[KeyParameter],
        missing: list[MissingDisclosure],
        *,
        key: ParameterKey,
        label: str,
        value: str | None,
        question: str,
    ) -> None:
        if value:
            params.append(
                KeyParameter(
                    key=key,
                    label=label,
                    value=value.strip(),
                    status=FactStatus.document_fact,
                )
            )
            return
        params.append(
            KeyParameter(
                key=key,
                label=label,
                value=None,
                status=FactStatus.not_disclosed,
            )
        )
        missing.append(MissingDisclosure(key=key, question=question))

    def _general_refs_for_product(self, product_type_id: str | None) -> list[GeneralReference]:
        refs: list[GeneralReference] = [
            GeneralReference(
                text="行业常识仅供参考，不能自动填入当前材料未披露字段。",
                source="docs/demo-支持范围与样例.md",
            )
        ]
        if not product_type_id:
            return refs
        for product in self._knowledge.list_products():
            if product.get("id") != product_type_id:
                continue
            hint = (product.get("principal_protection_hint") or "").strip()
            if hint and product_type_id == "structured_deposit":
                refs.append(
                    GeneralReference(
                        text=f"行业参考（非本材料事实）：{hint}",
                        source=f"knowledge/products.json#{product_type_id}",
                    )
                )
            note = (product.get("regulatory_notes") or "").strip()
            if note:
                refs.append(
                    GeneralReference(
                        text=f"监管要点参考：{note}",
                        source=f"knowledge/products.json#{product_type_id}",
                    )
                )
            break
        return refs

    @staticmethod
    def _first_match(text: str, patterns: list[re.Pattern[str]]) -> str | None:
        for pattern in patterns:
            m = pattern.search(text)
            if m:
                return m.group(1) if m.lastindex else m.group(0)
        return None
