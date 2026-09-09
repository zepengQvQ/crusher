/** 将结构化报告转为 Markdown（不含 API Key）。 */

/**
 * @param {object} report
 * @param {{ kind?: string, title?: string, sourceText?: string }} [meta]
 */
export function reportToMarkdown(report, meta = {}) {
  if (!report || typeof report !== 'object') {
    return '# 报告\n\n（空报告）\n'
  }
  const lines = []
  lines.push(`# ${meta.title || '分析报告'}`)
  lines.push('')
  lines.push('> 本 Demo 不进行用户适当性评估，不构成投资建议。浏览器清理数据后本地记录会丢失。')
  lines.push('')

  if (meta.kind === 'dual' || Array.isArray(report.comparisons)) {
    lines.push('## 双材料对照')
    lines.push('')
    for (const c of report.comparisons || []) {
      lines.push(`### ${c.subject || c.comparison_id || '对照项'}（${c.status || '-'}）`)
      if (c.summary) lines.push(c.summary)
      if (c.sales_claim?.summary) lines.push(`- 销售主张：${c.sales_claim.summary}`)
      if (c.sales_claim?.evidence?.quote) {
        lines.push(`- 销售原文：${c.sales_claim.evidence.quote}`)
      }
      if (c.official_evidence?.quote) {
        lines.push(`- 正式材料原文：${c.official_evidence.quote}`)
      } else {
        lines.push('- 正式材料原文：（未找到）')
      }
      if (c.suggested_follow_up) lines.push(`- 建议追问：${c.suggested_follow_up}`)
      lines.push('')
    }
    appendPending(lines, report)
    return `${lines.join('\n').trim()}\n`
  }

  lines.push('## 结论范围')
  lines.push(`- analysis_scope: ${report.analysis_scope || '-'}`)
  if (report.scope_reason) lines.push(`- 原因：${report.scope_reason}`)
  lines.push('')

  if (report.plain_language?.text) {
    lines.push('## 白话说明')
    lines.push(report.plain_language.text)
    lines.push('')
  }

  lines.push('## 关键参数')
  for (const p of report.key_parameters || []) {
    const val =
      p.status === 'not_disclosed'
        ? '材料未说明'
        : p.amount != null
          ? String(p.amount)
          : p.value ?? '-'
    lines.push(`- ${p.label || p.key}: ${val}（${p.status}）`)
  }
  lines.push('')

  lines.push('## 风险发现')
  if (!(report.findings || []).length) {
    lines.push('- （未命中已配置规则，不等于没有风险）')
  }
  for (const f of report.findings || []) {
    lines.push(`### ${f.title || f.id}（${f.finding_severity}）`)
    if (f.explanation) lines.push(f.explanation)
    for (const e of f.evidence || []) {
      if (e.quote) lines.push(`- 证据：${e.quote}`)
    }
    lines.push('')
  }

  appendPending(lines, report)

  if (meta.sourceText) {
    lines.push('## 完整输入原文（用户勾选保存）')
    lines.push('```')
    lines.push(meta.sourceText)
    lines.push('```')
    lines.push('')
  }

  return `${lines.join('\n').trim()}\n`
}

/**
 * 复制重点：结论 + 高/中风险 + 待确认。
 * @param {object} report
 */
export function reportHighlights(report) {
  if (!report) return ''
  if (Array.isArray(report.comparisons)) {
    const parts = [`对照 ${report.comparisons.length} 条`]
    for (const c of report.comparisons.slice(0, 5)) {
      parts.push(`- ${c.subject || c.status}: ${c.summary || ''}`)
    }
    appendPending(parts, report)
    return parts.join('\n')
  }
  const lines = []
  lines.push(`范围：${report.analysis_scope || '-'}`)
  if (report.plain_language?.text) lines.push(report.plain_language.text)
  const findings = (report.findings || []).filter(
    (f) => f.finding_severity === 'high' || f.finding_severity === 'mid',
  )
  for (const f of findings) {
    lines.push(`· ${f.title}（${f.finding_severity}）`)
    const q = f.evidence?.[0]?.quote
    if (q) lines.push(`  证据：${q}`)
  }
  appendPending(lines, report)
  return lines.join('\n')
}

function appendPending(lines, report) {
  const pending = []
  for (const m of report.missing_disclosures || []) {
    if (m.question) pending.push(m.question)
  }
  for (const q of report.pending_questions || []) {
    if (q) pending.push(String(q))
  }
  if (!pending.length) return
  lines.push('')
  lines.push('## 待确认')
  for (const q of pending) lines.push(`- ${q}`)
}
