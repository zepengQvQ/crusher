"""
用途：由程序事实/风险生成用户可见白话（不采信未验证模型自由文案）。
Java 对照：Assembler / Template Renderer。
输入：Finding、FinancialFact、KeyParameter。
输出：确定说明字符串。
业务不变量：不得写入原文与账本中不存在的保证/兜底类表述。
失败方式：无内容时返回固定「仅程序已确认条目」提示。
"""
from __future__ import annotations

from app.domain.models.financial_fact import FinancialFact, FinancialFactStatus
from app.domain.models.report import Finding, KeyParameter


def render_program_plain_language(
    *,
    findings: list[Finding],
    financial_facts: list[FinancialFact] | None = None,
    key_parameters: list[KeyParameter] | None = None,
) -> str:
    parts: list[str] = []
    for fact in financial_facts or []:
        if fact.status != FinancialFactStatus.CONFIRMED:
            continue
        label = fact.field_key
        value = fact.raw_value or fact.normalized_value or ""
        line = f"【事实】{label}：{value}"
        if fact.condition_text:
            line += f"（条件：{fact.condition_text}）"
        if fact.qualifiers:
            line += f"（限定：{'/'.join(fact.qualifiers)}）"
        parts.append(line)
    for param in key_parameters or []:
        if param.value:
            parts.append(f"【参数】{param.label}：{param.value}")
    for finding in findings:
        parts.append(f"【风险】{finding.title}：{finding.explanation}")
    if not parts:
        return "【程序说明】当前仅确认输入已校验；未形成可发布的通俗解释条目。"
    return "\n".join(parts)
