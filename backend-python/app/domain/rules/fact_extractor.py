"""从原文抽取关键参数（按产品拆分）；行业常识只进 general_reference。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from app.domain.models import GeneralReference, KeyParameter, MissingDisclosure
from app.domain.models.enums import FactStatus, ParameterKey
from app.domain.ports.protocols import KnowledgeRepository

_RISK_GRADE_RE = re.compile(
    r"(?:产品)?风险(?:等级|评级)\s*[:：]?\s*(R[1-5])|(?:评级|等级)\s*(R[1-5])",
    re.IGNORECASE,
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
            result = self._extract_loan(text)
        elif product_type_id == "structured_deposit":
            result = self._extract_structured_deposit(text)
        else:
            # 非首批产品由用例层短路；此处兜底为空
            result = ExtractResult()
        result.general_references = self._general_refs_for_product(product_type_id)
        # 待确认只保留 missing_disclosures，避免与 H5 pending 重复展示
        result.pending_questions = []
        return result

    def _extract_structured_deposit(self, text: str) -> ExtractResult:
        params: list[KeyParameter] = []
        missing: list[MissingDisclosure] = []

        self._add_param(
            params,
            missing,
            key=ParameterKey.term,
            label="产品期限",
            value=self._first_match(
                text,
                [
                    re.compile(r"产品期限\s*[:：]?\s*(\d+\s*天)"),
                    re.compile(r"期限\s*为?\s*(\d+\s*天)"),
                    re.compile(r"期限\s*为?\s*(\d+\s*个?月)"),
                    re.compile(r"共\s*(\d+\s*天)"),
                ],
            ),
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
            value=self._first_match(
                text,
                [
                    re.compile(
                        r"(不支持提前赎回|不可提前赎回|不可提前支取|可提前赎回|支持提前赎回)"
                    ),
                ],
            ),
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
            value=self._first_match(
                text,
                [
                    re.compile(r"(不保证本金|本金不保证|不保本)"),
                    re.compile(r"(确保本金安全|保证本金|本金保障|本金到期全额返还|保本)"),
                ],
            ),
            question="合同是否明确承诺本金保障？",
        )
        self._add_risk_grade(params, missing, text)

        return ExtractResult(key_parameters=params, missing_disclosures=missing)

    def _extract_loan(self, text: str) -> ExtractResult:
        params: list[KeyParameter] = []
        missing: list[MissingDisclosure] = []

        self._add_param(
            params,
            missing,
            key=ParameterKey.term,
            label="借款期限",
            value=self._first_match(
                text,
                [
                    re.compile(r"借款期限\s*[:：]?\s*(\d+\s*个?月|\d+\s*天|\d+\s*年)"),
                    re.compile(r"贷款期限\s*[:：]?\s*(\d+\s*个?月|\d+\s*天|\d+\s*年)"),
                    re.compile(r"期限\s*为?\s*(\d+\s*个?月|\d+\s*天|\d+\s*年)"),
                ],
            ),
            question="合同是否明确借款期限？",
        )

        rate = self._first_match(
            text,
            [
                re.compile(r"年化利率\s*(?:（[^）]*）)?\s*为?\s*([0-9.]+%)"),
                re.compile(r"年化利率\s*[:：]\s*([0-9.]+%)"),
                re.compile(r"年利率\s*为?\s*([0-9.]+%)"),
            ],
        )
        self._add_param(
            params,
            missing,
            key=ParameterKey.annual_interest_rate,
            label="年化利率",
            value=rate,
            question="合同是否写明年化利率？",
        )

        self._add_param(
            params,
            missing,
            key=ParameterKey.repayment_method,
            label="还款方式",
            value=self._first_match(
                text,
                [
                    re.compile(r"(等额本息|等额本金|先息后本|到期一次性还本付息)(?:还款(?:方式)?)?"),
                    re.compile(r"还款方式\s*[:：]?\s*([^，。；\n]{2,20})"),
                ],
            ),
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

        prep = self._first_match(
            text,
            [
                re.compile(r"(提前还款[^。；\n]{0,40}(?:违约金|手续费|费用)[^。；\n]{0,20})"),
                re.compile(r"(不收取?提前还款违约金|提前还款不收违约金)"),
            ],
        )
        self._add_param(
            params,
            missing,
            key=ParameterKey.prepayment_fee,
            label="提前还款费用",
            value=prep.strip(" ，,") if prep else None,
            question="提前还款是否收取违约金或手续费？",
        )

        amount_m = re.search(
            r"(?:借款|贷款)金额\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)\s*(万元|万|元)?",
            text,
        )
        if amount_m:
            raw_num = amount_m.group(1)
            unit = amount_m.group(2) or "元"
            try:
                num = Decimal(raw_num)
            except (InvalidOperation, ValueError):
                num = None
            else:
                if unit in ("万", "万元"):
                    num = num * Decimal("10000")
            params.append(
                KeyParameter(
                    key=ParameterKey.amount,
                    label="借款金额",
                    value=f"{raw_num}{unit}",
                    status=FactStatus.document_fact,
                    amount=num,
                )
            )
        # 金额：原文没有则不输出（可选字段，不进 not_disclosed）

        self._add_risk_grade(params, missing, text)
        return ExtractResult(key_parameters=params, missing_disclosures=missing)

    def _add_risk_grade(
        self,
        params: list[KeyParameter],
        missing: list[MissingDisclosure],
        text: str,
    ) -> None:
        grade = None
        m = _RISK_GRADE_RE.search(text)
        if m:
            grade = (m.group(1) or m.group(2) or "").upper() or None
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
        hits = re.findall(
            r"(?:到期)?年化收益率?\s*[:：]?\s*为?\s*([0-9.]+%)|"
            r"年化收益率?\s*([0-9.]+%)",
            text,
        )
        seen: list[str] = []
        for groups in hits:
            for g in groups if isinstance(groups, tuple) else (groups,):
                if g and g not in seen:
                    seen.append(g)
        return seen

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
