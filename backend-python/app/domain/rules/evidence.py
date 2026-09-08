"""证据校验：quote 必须能在原文中定位；无法定位则丢弃该发现（不静默留脏数据）。"""
from __future__ import annotations

from app.domain.models import Evidence, Finding
from app.domain.models.enums import EvidenceSource


def validate_and_fix_findings(text: str, findings: list[Finding]) -> list[Finding]:
    """校验并修正证据下标；原文对不上的 Finding 直接丢弃。"""
    text = text or ""
    kept: list[Finding] = []
    for finding in findings:
        fixed_evidence: list[Evidence] = []
        for ev in finding.evidence:
            fixed = _fix_one(text, ev)
            if fixed is not None:
                fixed_evidence.append(fixed)
        if not fixed_evidence:
            # 无可用原文证据 → 丢弃，禁止带着假证据进入报告
            continue
        kept.append(
            finding.model_copy(
                update={
                    "evidence": fixed_evidence,
                    "needs_review": finding.needs_review,
                }
            )
        )
    return kept


def _fix_one(text: str, ev: Evidence) -> Evidence | None:
    quote = ev.quote
    if not quote:
        return None
    if 0 <= ev.start <= ev.end <= len(text) and text[ev.start : ev.end] == quote:
        return ev
    idx = text.find(quote)
    if idx < 0:
        return None
    return Evidence(
        quote=quote,
        start=idx,
        end=idx + len(quote),
        source=ev.source if ev.source else EvidenceSource.input_text,
    )
