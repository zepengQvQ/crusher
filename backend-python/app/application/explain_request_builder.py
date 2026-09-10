"""
用途：把抽取事实与 Finding 组装成模型解释请求（白名单 ID + 结构化载荷）。
Java 对照：Assembler / Builder（应用层组装器，不裁决发布）。
输入：ExtractResult、已证据校验的 Finding 列表。
输出：LlmExplainRequest（含 allowed_* 白名单与 user_prompt）。
业务不变量：允许引用 ID 只来自当前账本与有效 Finding；知识 ID 去重保序。
失败方式：不抛业务异常；空知识时使用 knowledge:demo 占位供门禁校验。
"""
from __future__ import annotations

import json

from app.domain.models.llm import LlmExplainRequest
from app.domain.models.report import Finding
from app.domain.rules.apply_fact_corrections import active_financial_facts
from app.domain.rules.fact_extractor import ExtractResult
from app.domain.rules.prompts import FINDINGS_USER_TEMPLATE, RULE_REVIEW_SYSTEM


class ExplainRequestBuilder:
    """将事实与发现组装为模型解释请求。"""

    @staticmethod
    def build(
        extracted: ExtractResult,
        findings: list[Finding],
    ) -> LlmExplainRequest:
        fact_ids: list[str] = []
        facts_payload: list[dict] = []
        for p in extracted.key_parameters:
            fid = f"param:{p.key.value}"
            fact_ids.append(fid)
            facts_payload.append(
                {
                    "fact_id": fid,
                    "key": p.key.value,
                    "label": p.label,
                    "status": p.status.value,
                    "value": p.value,
                    "amount": str(p.amount) if p.amount is not None else None,
                }
            )
        for ff in active_financial_facts(extracted.financial_facts):
            fact_ids.append(ff.fact_id)
            facts_payload.append(
                {
                    "fact_id": ff.fact_id,
                    "field_key": ff.field_key,
                    "raw_value": ff.raw_value,
                    "normalized_value": ff.normalized_value,
                    "status": ff.status.value,
                    "qualifiers": list(ff.qualifiers),
                    "condition_text": ff.condition_text,
                }
            )
        finding_ids = [f.id for f in findings]
        findings_payload = [
            {
                "id": f.id,
                "title": f.title,
                "severity": f.finding_severity.value,
                "explanation": f.explanation,
            }
            for f in findings
        ]
        evidence_payload = [
            {
                "finding_id": f.id,
                "quote": ev.quote,
                "start": ev.start,
                "end": ev.end,
            }
            for f in findings
            for ev in f.evidence
        ]
        knowledge_ids: list[str] = []
        for ref in extracted.general_references:
            kid = ref.source.strip() or "knowledge:general"
            if kid not in knowledge_ids:
                knowledge_ids.append(kid)
        if not knowledge_ids:
            knowledge_ids = ["knowledge:demo"]
        seen_f: set[str] = set()
        unique_fact_ids: list[str] = []
        for fid in fact_ids:
            if fid in seen_f:
                continue
            seen_f.add(fid)
            unique_fact_ids.append(fid)

        user_prompt = FINDINGS_USER_TEMPLATE.format(
            allowed_fact_ids_json=json.dumps(unique_fact_ids, ensure_ascii=False),
            allowed_finding_ids_json=json.dumps(finding_ids, ensure_ascii=False),
            allowed_knowledge_ids_json=json.dumps(knowledge_ids, ensure_ascii=False),
            facts_json=json.dumps(facts_payload, ensure_ascii=False),
            findings_json=json.dumps(findings_payload, ensure_ascii=False),
            evidence_json=json.dumps(evidence_payload, ensure_ascii=False),
        )
        return LlmExplainRequest(
            system_prompt=RULE_REVIEW_SYSTEM,
            user_prompt=user_prompt,
            allowed_fact_ids=unique_fact_ids,
            allowed_finding_ids=finding_ids,
            allowed_knowledge_ids=knowledge_ids,
        )
