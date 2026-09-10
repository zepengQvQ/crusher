"""草稿语义支撑：模型文案须能被已验证引用内容支撑（Demo 确定性启发式）。"""
from __future__ import annotations

import re

from app.domain.models.llm import LlmAnalysisDraft
from app.domain.validation.reference_catalog import ReferenceCatalog
from app.domain.validation.types import VerificationCheck, VerificationIssue
from app.shared.enums import ErrorCode

# 原文/账本未支撑时禁止出现的保证/兜底类表述
_UNSUPPORTED_CLAIM_RE = re.compile(
    r"(国家财政|财政兜底|银行倒闭|绝对稳健|绝对安全|全额赔付|"
    r"等同于?银行存款|存款保险全额|不会损失|零风险|稳赚不赔)"
)


def validate_draft_grounded_in_catalog(
    draft: LlmAnalysisDraft,
    catalog: ReferenceCatalog,
    *,
    source_text: str = "",
) -> list[VerificationIssue]:
    """合法引用 ID 不得为无关/虚构文案背书。"""
    issues: list[VerificationIssue] = []
    support_blob = source_text or ""
    for entry in catalog.entries.values():
        if entry.raw_value:
            support_blob += "\n" + entry.raw_value
        if entry.standard_value:
            support_blob += "\n" + entry.standard_value
        if entry.condition_text:
            support_blob += "\n" + entry.condition_text
        for q in entry.evidence_quotes:
            support_blob += "\n" + q
        for q in entry.qualifiers:
            support_blob += "\n" + q

    for item in draft.all_items():
        text = item.text or ""
        for m in _UNSUPPORTED_CLAIM_RE.finditer(text):
            phrase = m.group(0)
            if phrase not in support_blob:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.boundary,
                        message=(
                            f"draft item {item.item_id} unsupported claim "
                            f"not grounded in references: {phrase}"
                        ),
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
                break
        # 引用存在但文案与引用内容几乎无交集 → 拒绝（防「合法 ID 撑任意文案」）
        ref_bits: list[str] = []
        for rid in item.fact_ids + item.finding_ids + item.knowledge_ids:
            entry = catalog.get(rid)
            if entry is None:
                continue
            if entry.raw_value:
                ref_bits.append(entry.raw_value)
            if entry.standard_value:
                ref_bits.append(entry.standard_value)
            ref_bits.extend(entry.evidence_quotes)
            if entry.field_key:
                ref_bits.append(entry.field_key)
        if item.fact_ids or item.finding_ids:
            if not ref_bits:
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.reference,
                        message=(
                            f"draft item {item.item_id} references ids "
                            "not present in verified catalog"
                        ),
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
            elif (
                not _has_overlap(text, ref_bits)
                and _UNSUPPORTED_CLAIM_RE.search(text)
            ):
                issues.append(
                    VerificationIssue(
                        check=VerificationCheck.boundary,
                        message=(
                            f"draft item {item.item_id} text not supported "
                            "by referenced fact/finding content"
                        ),
                        error_code=ErrorCode.OUTPUT_VERIFICATION_FAILED,
                    )
                )
    return issues


def _has_overlap(text: str, bits: list[str]) -> bool:
    for bit in bits:
        token = (bit or "").strip()
        if len(token) >= 2 and token in text:
            return True
        # 数值片段
        for m in re.finditer(r"\d+(?:\.\d+)?", token):
            if m.group(0) in text:
                return True
    return False
