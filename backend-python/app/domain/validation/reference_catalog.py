"""
用途：构建发布门禁可用的引用目录（仅含证据已验证的 ID）。
Java 对照：只读 Lookup / Catalog。
输入：已通过证据校验的事实、Finding、知识 ID。
输出：ReferenceCatalog。
业务不变量：目录外 ID 不得支撑发布或扩充允许数值。
失败方式：查询未登记 ID 时返回 None。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.financial_fact import FinancialFact
from app.domain.models.report import Finding, KeyParameter


@dataclass(frozen=True)
class ReferenceEntry:
    ref_id: str
    kind: str  # fact | finding | knowledge
    field_key: str | None = None
    status: str | None = None
    standard_value: str | None = None
    raw_value: str | None = None
    qualifiers: tuple[str, ...] = ()
    condition_text: str | None = None
    evidence_quotes: tuple[str, ...] = ()


@dataclass
class ReferenceCatalog:
    """id → 已验证引用条目。"""

    entries: dict[str, ReferenceEntry] = field(default_factory=dict)

    def get(self, ref_id: str) -> ReferenceEntry | None:
        return self.entries.get(ref_id)

    def fact_ids(self) -> list[str]:
        return [k for k, v in self.entries.items() if v.kind == "fact"]

    def finding_ids(self) -> list[str]:
        return [k for k, v in self.entries.items() if v.kind == "finding"]

    @classmethod
    def from_verified(
        cls,
        *,
        financial_facts: list[FinancialFact],
        findings: list[Finding],
        knowledge_ids: list[str] | None = None,
        verified_fact_ids: set[str] | None = None,
        key_parameters: list[KeyParameter] | None = None,
    ) -> ReferenceCatalog:
        cat = cls()
        for param in key_parameters or []:
            fid = f"param:{param.key.value}"
            cat.entries[fid] = ReferenceEntry(
                ref_id=fid,
                kind="fact",
                field_key=param.key.value,
                status=param.status.value,
                standard_value=param.value,
                raw_value=param.value,
                evidence_quotes=(),
            )
        allowed_facts = verified_fact_ids
        for fact in financial_facts:
            if allowed_facts is not None and fact.fact_id not in allowed_facts:
                continue
            cat.entries[fact.fact_id] = ReferenceEntry(
                ref_id=fact.fact_id,
                kind="fact",
                field_key=fact.field_key,
                status=fact.status.value,
                standard_value=fact.normalized_value,
                raw_value=fact.raw_value,
                qualifiers=tuple(fact.qualifiers),
                condition_text=fact.condition_text,
                evidence_quotes=tuple(ev.quote for ev in fact.evidence_refs),
            )
        for finding in findings:
            cat.entries[finding.id] = ReferenceEntry(
                ref_id=finding.id,
                kind="finding",
                field_key=finding.rule_or_knowledge_id,
                status="confirmed",
                standard_value=None,
                raw_value=finding.explanation,
                evidence_quotes=tuple(ev.quote for ev in finding.evidence),
            )
        for kid in knowledge_ids or []:
            cat.entries[kid] = ReferenceEntry(ref_id=kid, kind="knowledge")
        return cat
