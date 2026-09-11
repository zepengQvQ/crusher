import { describe, expect, it } from 'vitest'
import { buildFollowUpSuggestions, buildReportDigest } from '../utils/followUpSuggestions'

describe('buildFollowUpSuggestions', () => {
  it('builds questions from findings, pending and key parameters', () => {
    const qs = buildFollowUpSuggestions({
      resolved_product_type: 'structured_deposit',
      pending_questions: ['合同有没有写清提前支取条件？'],
      findings: [
        {
          title: '区间外收益可能为零',
          finding_severity: 'high',
        },
      ],
      key_parameters: [
        {
          key: 'principal_protection',
          label: '本金保障',
          status: 'disclosed',
          value: '保本',
        },
        {
          key: 'fee_structure',
          label: '费用结构',
          status: 'not_disclosed',
        },
      ],
    })
    expect(qs.length).toBeGreaterThan(0)
    expect(qs.length).toBeLessThanOrEqual(4)
    expect(qs.some((q) => q.includes('提前支取'))).toBe(true)
    expect(qs.some((q) => q.includes('区间外') || q.includes('费用'))).toBe(true)
    expect(qs.join('')).not.toContain('适合老年人')
  })

  it('returns empty when report missing', () => {
    expect(buildFollowUpSuggestions(null)).toEqual([])
    expect(buildFollowUpSuggestions({})).toEqual([])
  })
})

describe('buildReportDigest', () => {
  it('compresses report into short digest', () => {
    const digest = buildReportDigest({
      resolved_product_type: 'structured_deposit',
      plain_language: { text: '注意收益条件' },
      findings: [{ title: '区间外收益可能为零' }],
      key_parameters: [
        { key: 'term', label: '期限', status: 'disclosed', value: '183天' },
      ],
    })
    expect(digest).toContain('区间外')
    expect(digest).toContain('183')
  })
})
