import { describe, it, expect, vi, beforeEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import ReportPage from '../pages/ReportPage.vue'
import * as api from '../api/client'
import { completedTaskPayload, mountWithApp } from '../test/helpers'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    getAnalysis: vi.fn(),
    copyText: vi.fn(async () => true),
  }
})

describe('ReportPage analysis_scope 文案', () => {
  beforeEach(() => {
    sessionStorage.clear()
    api.getAnalysis.mockReset()
  })

  it('supported 无 Finding 不伪装成无风险', async () => {
    const payload = completedTaskPayload()
    payload.report.findings = []
    payload.report.analysis_scope = 'supported'
    api.getAnalysis.mockResolvedValue(payload)
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('未命中当前已配置规则，不等于产品没有风险')
    expect(wrapper.text()).toContain('这次没抓到风险点；不等于产品一定安全')
    expect(wrapper.text()).not.toContain('可以放心')
    const broken = wrapper.findAll('img').filter((img) => {
      const src = img.attributes('src') || ''
      return src === 'success' || src.endsWith('/success')
    })
    expect(broken.length).toBe(0)
  })

  it('产品类型英文 id 展示为中文名', async () => {
    const payload = completedTaskPayload()
    payload.report.product_candidates = [
      {
        product_type_id: 'structured_deposit',
        product_type_name: 'structured_deposit',
        confidence: 1,
        evidence_quotes: ['手动选择:structured_deposit'],
      },
    ]
    api.getAnalysis.mockResolvedValue(payload)
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('结构性存款')
    expect(wrapper.text()).toContain('你手动指定的类型，不是从材料原文读出的')
    expect(wrapper.text()).toContain('更多工具')
    expect(wrapper.text()).toContain('复制报告')
    expect(wrapper.text()).not.toMatch(/structured_deposit/)
  })

  it('out_of_scope 与 needs_confirmation 文案正确', async () => {
    api.getAnalysis.mockResolvedValue(
      completedTaskPayload({
        report: {
          ...completedTaskPayload().report,
          findings: [],
          analysis_scope: 'out_of_scope',
        },
      }),
    )
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('当前 Demo 未分析该产品，请选择结构性存款或贷款')

    api.getAnalysis.mockResolvedValue(
      completedTaskPayload({
        report: {
          ...completedTaskPayload().report,
          findings: [],
          analysis_scope: 'needs_confirmation',
        },
      }),
    )
    const second = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_b' },
      props: { taskId: 'tsk_b' },
    })
    await flushPromises()
    expect(second.wrapper.text()).toContain('产品类型存在冲突，请确认后重新分析')
  })
})
