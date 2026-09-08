"""从原文抽取关键参数（确定性），行业常识只进 general_reference。"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.domain.models import GeneralReference, KeyParameter, MissingDisclosure
from app.domain.models.enums import FactStatus, ParameterKey
from app.domain.ports.protocols import KnowledgeRepository

_PARAM_SPECS: list[tuple[ParameterKey, str, list[re.Pattern[str]]]] = [
    (
        ParameterKey.term,
        "投资期限",
        [
            re.compile(r"产品期限\s*(\d+\s*天)"),
            re.compile(r"期限\s*(\d+\s*天)"),
            re.compile(r"期限\s*(\d+\s*个?月)"),
            re.compile(r"共\s*(\d+\s*天)"),
        ],
    ),
    (
        ParameterKey.expected_return,
        "预期收益/利率",
        [
            re.compile(r"年化收益率?为?\s*([0-9.]+%)"),
            re.compile(r"到期年化收益率?为?\s*([0-9.]+%)"),
            re.compile(r"年化利率[^0-9%]{0,20}([0-9.]+%)"),
        ],
    ),
    (
        ParameterKey.early_redemption,
        "提前赎回",
        [
            re.compile(r"(不支持提前赎回|不可提前赎回|不可提前支取|可提前赎回|支持提前赎回)"),
        ],
    ),
    (
        ParameterKey.fee_structure,
        "费用结构",
        [
            re.compile(r"(管理费\s*为?\s*[0-9.]+\s*%[^，。；]*)"),
            re.compile(r"(手续费[^，。；]{0,20})"),
            re.compile(r"(托管费\s*为?\s*[0-9.]+\s*%)"),
        ],
    ),
    (
        ParameterKey.principal_protection,
        "本金保障",
        [
            re.compile(r"(不保证本金|本金不保证|不保本)"),
            re.compile(r"(确保本金安全|保证本金|本金保障|保本)"),
        ],
    ),
]


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
        params: list[KeyParameter] = []
        missing: list[MissingDisclosure] = []
        pending: list[str] = []

        # 收益/利率：收集全部命中，合并为一条 document_fact
        return_hits = re.findall(
            r"(?:到期)?年化收益率?为?\s*([0-9.]+%)|年化利率[^0-9%]{0,20}([0-9.]+%)",
            text,
        )
        flat_hits: list[str] = []
        for groups in return_hits:
            if isinstance(groups, tuple):
                for g in groups:
                    if g:
                        flat_hits.append(g)
            elif groups:
                flat_hits.append(groups)
        if flat_hits:
            seen: list[str] = []
            for h in flat_hits:
                if h not in seen:
                    seen.append(h)
            params.append(
                KeyParameter(
                    key=ParameterKey.expected_return,
                    label="预期收益/利率",
                    value=" / ".join(seen),
                    status=FactStatus.document_fact,
                )
            )
        else:
            params.append(
                KeyParameter(
                    key=ParameterKey.expected_return,
                    label="预期收益/利率",
                    value=None,
                    status=FactStatus.not_disclosed,
                )
            )
            missing.append(
                MissingDisclosure(
                    key=ParameterKey.expected_return,
                    question="合同是否写明预期/到期收益率或年化利率？",
                )
            )
            pending.append("预期收益率或年化利率是多少？")
        for key, label, patterns in _PARAM_SPECS:
            if key == ParameterKey.expected_return:
                continue
            value = self._first_match(text, patterns)
            if value:
                params.append(
                    KeyParameter(
                        key=key,
                        label=label,
                        value=value.strip(),
                        status=FactStatus.document_fact,
                    )
                )
            else:
                params.append(
                    KeyParameter(
                        key=key,
                        label=label,
                        value=None,
                        status=FactStatus.not_disclosed,
                    )
                )
                missing.append(
                    MissingDisclosure(
                        key=key,
                        question=self._question_for(key),
                    )
                )
                pending.append(self._question_for(key))

        # calculated_fact 示例：期限天数可被解析时标注计算确认（仍来自原文数字）
        term_param = next(p for p in params if p.key == ParameterKey.term)
        if term_param.status == FactStatus.document_fact and term_param.value:
            days = re.search(r"(\d+)\s*天", term_param.value)
            if days and "共" + days.group(1) + "天" in text.replace(" ", ""):
                # 原文同时出现「期限90天」与「共90天」——保持 document_fact 即可
                pass

        refs = self._general_refs_for_product(product_type_id)
        return ExtractResult(
            key_parameters=params,
            missing_disclosures=missing,
            general_references=refs,
            pending_questions=pending,
        )

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
            if hint:
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

    @staticmethod
    def _question_for(key: ParameterKey) -> str:
        mapping = {
            ParameterKey.term: "合同是否明确投资/借款期限？",
            ParameterKey.early_redemption: "是否支持提前赎回或提前还款？",
            ParameterKey.fee_structure: "费用（管理费/手续费等）如何收取？",
            ParameterKey.principal_protection: "合同是否明确承诺本金保障？",
            ParameterKey.expected_return: "合同是否写明预期/到期收益率？",
        }
        return mapping.get(key, f"请确认字段 {key.value}")
