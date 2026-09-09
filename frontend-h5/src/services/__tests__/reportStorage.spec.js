import { beforeEach, describe, expect, it } from 'vitest'
import {
  deleteReport,
  isSchemaCompatible,
  listReports,
  MAX_SAVED_REPORTS,
  REPORT_SCHEMA_VERSION,
  saveReport,
} from '../reportStorage'
import { reportHighlights, reportToMarkdown } from '../../utils/reportToMarkdown'

const sampleReport = {
  analysis_scope: 'supported',
  plain_language: { text: '这是白话说明' },
  key_parameters: [{ key: 'amount', label: '金额', value: '10万', status: 'document_fact' }],
  findings: [
    {
      id: 'f1',
      title: '收益不确定',
      finding_severity: 'high',
      explanation: '说明',
      evidence: [{ quote: '预期收益不保证', start: 0, end: 7 }],
    },
  ],
  pending_questions: ['费率是否一次性收取？'],
  missing_disclosures: [{ key: 'fee_structure', question: '费用怎么收？' }],
}

describe('reportToMarkdown', () => {
  it('包含结论、风险、证据和待确认，不含 api key', () => {
    const md = reportToMarkdown(sampleReport, { title: '测试报告' })
    expect(md).toContain('白话说明')
    expect(md).toContain('收益不确定')
    expect(md).toContain('预期收益不保证')
    expect(md).toContain('费率是否一次性收取')
    expect(md).not.toMatch(/api[_-]?key/i)
    expect(md).not.toContain('sk-')
  })

  it('重点摘要含高风险', () => {
    const text = reportHighlights(sampleReport)
    expect(text).toContain('收益不确定')
    expect(text).toContain('待确认')
  })
})

describe('reportStorage', () => {
  beforeEach(async () => {
    const all = await listReports()
    for (const r of all) {
      await deleteReport(r.report_id)
    }
  })

  it('保存、查看、删除', async () => {
    const saved = await saveReport({
      title: '样例',
      kind: 'analysis',
      report: sampleReport,
    })
    expect(saved.schema_version).toBe(REPORT_SCHEMA_VERSION)
    const listed = await listReports()
    expect(listed).toHaveLength(1)
    await deleteReport(saved.report_id)
    expect(await listReports()).toHaveLength(0)
  })

  it('最多保留 10 份', async () => {
    for (let i = 0; i < MAX_SAVED_REPORTS + 3; i += 1) {
      await saveReport({
        title: `r${i}`,
        kind: 'analysis',
        report: sampleReport,
      })
    }
    const listed = await listReports()
    expect(listed.length).toBe(MAX_SAVED_REPORTS)
  })

  it('schema 不兼容判定', () => {
    expect(isSchemaCompatible({ schema_version: REPORT_SCHEMA_VERSION })).toBe(true)
    expect(isSchemaCompatible({ schema_version: 999 })).toBe(false)
    expect(isSchemaCompatible(null)).toBe(false)
  })

  it('默认不保存完整原文', async () => {
    const saved = await saveReport({
      title: '无原文',
      kind: 'analysis',
      report: sampleReport,
    })
    expect(saved.source_text).toBeUndefined()
  })
})
