/**
 * 根据分析报告生成可点选的追问（优先能落到材料证据的问法）。
 * @param {object|null|undefined} report
 * @param {{ limit?: number }} [opts]
 * @returns {string[]}
 */
export function buildFollowUpSuggestions(report, opts = {}) {
  const limit = Math.max(1, Math.min(Number(opts.limit) || 4, 6))
  if (!report || typeof report !== 'object') return []

  const seen = new Set()
  const out = []

  const push = (q) => {
    const text = String(q || '')
      .replace(/\s+/g, ' ')
      .trim()
    if (!text || text.length < 4) return
    const key = text.replace(/[？?！!。．，,、\s]/g, '')
    if (seen.has(key)) return
    seen.add(key)
    out.push(text.length > 28 ? `${text.slice(0, 27)}…` : text)
  }

  for (const q of report.pending_questions || []) push(q)
  for (const m of report.missing_disclosures || []) {
    push(m?.question || '')
    if (m?.key) push(questionForMissingKey(m.key, m.label || m.key))
  }

  const findings = Array.isArray(report.findings) ? report.findings : []
  const ranked = [...findings].sort(
    (a, b) => severityRank(b?.finding_severity) - severityRank(a?.finding_severity),
  )
  for (const f of ranked) {
    const title = String(f?.title || '').trim()
    if (!title) continue
    if (severityRank(f?.finding_severity) >= 2) {
      push(`材料里「${clip(title, 12)}」具体怎么写的？`)
    } else {
      push(`「${clip(title, 14)}」是否有原文依据？`)
    }
  }

  const params = Array.isArray(report.key_parameters) ? report.key_parameters : []
  for (const p of params) {
    push(questionForParam(p))
  }

  const product =
    report.resolved_product_type ||
    report.product_candidates?.[0]?.product_type_id ||
    report.product_candidates?.[0]?.product_type_name ||
    ''
  if (String(product).includes('structured') || String(product).includes('结构性')) {
    push('收益触发条件材料写清楚了吗？')
    push('区间外收益会怎样，原文怎么说？')
  } else if (String(product).includes('loan') || String(product).includes('贷')) {
    push('逾期或罚息怎么算，材料写了吗？')
    push('提前还款的条件和费用原文怎么写？')
  }

  return out.slice(0, limit)
}

function severityRank(sev) {
  const s = String(sev || '').toLowerCase()
  if (s === 'high') return 3
  if (s === 'mid' || s === 'medium') return 2
  if (s === 'low') return 1
  return 0
}

function clip(s, n) {
  const t = String(s || '').trim()
  return t.length > n ? `${t.slice(0, n)}…` : t
}

function questionForMissingKey(key, label) {
  const k = String(key || '')
  const name = String(label || key || '该项').trim()
  if (k === 'principal_protection') return '材料有没有写清是否保本？'
  if (k === 'early_redemption' || k === 'prepayment_fee') return '提前赎回/支取的条件和费用写了吗？'
  if (k === 'fee_structure') return '费用和收费标准材料写明了吗？'
  if (k === 'term') return '产品期限、起息或到期日写清楚了吗？'
  if (k === 'product_risk_grade') return '风险评级在材料里怎么写的？'
  if (k === 'interest_rate' || k === 'expected_return') return '收益率或利率条款材料写了吗？'
  return `材料有没有说明「${clip(name, 10)}」？`
}

function questionForParam(p) {
  if (!p || typeof p !== 'object') return ''
  const key = String(p.key || '')
  const label = String(p.label || key || '').trim()
  const status = String(p.status || '')
  const value = formatParamValue(p)

  if (status === 'not_disclosed') {
    return questionForMissingKey(key, label)
  }
  if (!value || value === '-') return ''

  if (key === 'principal_protection') return `「${clip(value, 10)}」之外，本金条款还有别的限制吗？`
  if (key === 'early_redemption' || key === 'prepayment_fee') {
    return `提前退出「${clip(value, 10)}」，费用和条件原文怎么写？`
  }
  if (key === 'fee_structure') return `费用「${clip(value, 10)}」之外还有其他收费吗？`
  if (key === 'term') return `期限「${clip(value, 10)}」到期后本金和收益怎么结算？`
  if (key === 'product_risk_grade') return `评级「${clip(value, 8)}」对应的风险说明写了吗？`
  if (key === 'interest_rate' || key === 'expected_return') {
    return `收益/利率「${clip(value, 10)}」的计算条件原文怎么写？`
  }
  return `「${clip(label || key, 8)}」写成「${clip(value, 10)}」，还有补充条件吗？`
}

function formatParamValue(p) {
  if (p.key === 'amount' && p.amount != null) return String(p.amount)
  const v = p.value ?? p.raw_value
  if (v == null) return ''
  return String(v).trim()
}

/**
 * 压缩报告为追问用短摘要（1A）。
 * @param {object|null|undefined} report
 * @returns {string}
 */
export function buildReportDigest(report) {
  if (!report || typeof report !== 'object') return ''
  const lines = []
  const product =
    report.resolved_product_type ||
    report.product_candidates?.[0]?.product_type_name ||
    report.product_candidates?.[0]?.product_type_id
  if (product) lines.push(`产品：${product}`)
  const plain = String(report.plain_language?.text || '').trim()
  if (plain) lines.push(`说明：${plain.slice(0, 120)}${plain.length > 120 ? '…' : ''}`)
  const findings = Array.isArray(report.findings) ? report.findings : []
  if (findings.length) {
    const titles = findings
      .map((f) => String(f?.title || '').trim())
      .filter(Boolean)
      .slice(0, 5)
    if (titles.length) lines.push(`风险：${titles.join('；')}`)
  }
  const params = Array.isArray(report.key_parameters) ? report.key_parameters : []
  const paramBits = []
  for (const p of params.slice(0, 6)) {
    const label = String(p.label || p.key || '').trim()
    if (!label) continue
    if (p.status === 'not_disclosed') {
      paramBits.push(`${label}=材料未说明`)
      continue
    }
    const v = formatParamValue(p)
    if (v) paramBits.push(`${label}=${v}`)
  }
  if (paramBits.length) lines.push(`参数：${paramBits.join('；')}`)
  const pending = Array.isArray(report.pending_questions) ? report.pending_questions : []
  if (pending.length) {
    lines.push(`待确认：${pending.slice(0, 3).map((q) => String(q)).join('；')}`)
  }
  return lines.join('\n').slice(0, 1800)
}
