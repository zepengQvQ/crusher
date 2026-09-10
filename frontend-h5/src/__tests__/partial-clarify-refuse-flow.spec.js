import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import AnalysisCoverageCard from '../components/AnalysisCoverageCard.vue'
import ReportPage from '../pages/ReportPage.vue'
import ErrorPage from '../pages/ErrorPage.vue'
import * as api from '../api/client'
import { completedTaskPayload, failedTaskPayload, mountWithApp } from '../test/helpers'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    getAnalysis: vi.fn(),
    createAnalysis: vi.fn(),
    copyText: vi.fn(async () => true),
  }
})

vi.mock('vant', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, showToast: vi.fn() }
})

describe('partial-clarify-refuse-flow', () => {
  beforeEach(() => {
    sessionStorage.clear()
    api.getAnalysis.mockReset()
  })

  it('AnalysisCoverageCard 区分已检查与未检查', () => {
    const wrapper = mount(AnalysisCoverageCard, {
      props: {
        coverage: {
          checked: ['产品类型识别（程序规则）'],
          not_checked: ['用户适当性评估'],
        },
      },
    })
    expect(wrapper.text()).toContain('已检查')
    expect(wrapper.text()).toContain('产品类型识别（程序规则）')
    expect(wrapper.text()).toContain('未检查')
    expect(wrapper.text()).toContain('用户适当性评估')
    expect(wrapper.text()).toContain('材料未说明')
  })

  it('PUBLISH_PARTIAL 展示横幅与覆盖说明，不伪装全绿成功', async () => {
    const payload = completedTaskPayload({
      publication: {
        outcome: 'publish_partial',
        reason_code: 'OUTPUT_VERIFICATION_FAILED',
        user_reason: '模型解释未通过校验，仅展示程序已确认内容',
        next_steps: ['请查看下方已确认的程序事实与风险'],
        coverage: {
          checked: ['风险模式匹配（程序规则）'],
          not_checked: ['模型通俗解释（未通过校验）'],
        },
      },
      report: {
        ...completedTaskPayload().report,
        publication: {
          outcome: 'publish_partial',
          reason_code: 'OUTPUT_VERIFICATION_FAILED',
          user_reason: '模型解释未通过校验，仅展示程序已确认内容',
          next_steps: ['请查看下方已确认的程序事实与风险'],
          coverage: {
            checked: ['风险模式匹配（程序规则）'],
            not_checked: ['模型通俗解释（未通过校验）'],
          },
        },
        plain_language: {
          text: '【部分结果】解释未通过',
          status: 'partial',
        },
      },
    })
    api.getAnalysis.mockResolvedValue(payload)
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_partial' },
      props: { taskId: 'tsk_partial' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('模型解释未通过校验')
    expect(wrapper.text()).toContain('模型通俗解释（未通过校验）')
    expect(wrapper.text()).not.toContain('可以放心')
  })

  it('CLARIFY 展示追问原因与下一步', async () => {
    const payload = completedTaskPayload({
      publication: {
        outcome: 'clarify',
        reason_code: 'INPUT_INCOMPLETE',
        user_reason: '输入还不完整，请先回答追问',
        next_steps: ['请回答页面上的追问后继续'],
        coverage: {
          checked: ['输入完整性检查'],
          not_checked: ['完整风险分析（待补充信息）'],
        },
      },
      report: {
        ...completedTaskPayload().report,
        findings: [],
        pending_questions: ['这是结构性存款还是贷款？'],
        analysis_scope: 'needs_confirmation',
        publication: {
          outcome: 'clarify',
          reason_code: 'INPUT_INCOMPLETE',
          user_reason: '输入还不完整，请先回答追问',
          next_steps: ['请回答页面上的追问后继续'],
          coverage: {
            checked: ['输入完整性检查'],
            not_checked: ['完整风险分析（待补充信息）'],
          },
        },
      },
    })
    api.getAnalysis.mockResolvedValue(payload)
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_clarify' },
      props: { taskId: 'tsk_clarify' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('输入还不完整')
    expect(wrapper.text()).toContain('请回答页面上的追问后继续')
    expect(wrapper.text()).toContain('这是结构性存款还是贷款？')
  })

  it('REFUSE 错误页展示原因码与下一步', async () => {
    api.getAnalysis.mockResolvedValue(
      failedTaskPayload({
        publication: {
          outcome: 'refuse',
          reason_code: 'MODEL_TIMEOUT',
          user_reason: '模型调用失败：等待超时',
          next_steps: ['可返回首页修改材料后重试', '失败不等于产品安全或无风险'],
          coverage: { checked: [], not_checked: ['完整风险结论（本次已拒绝发布）'] },
        },
      }),
    )
    const { wrapper, store } = await mountWithApp(ErrorPage, {
      routeName: 'error',
      params: { taskId: 'tsk_fail' },
      props: { taskId: 'tsk_fail' },
    })
    await flushPromises()
    expect(store.lastErrorCode).toBe('MODEL_TIMEOUT')
    expect(wrapper.text()).toContain('MODEL_TIMEOUT')
    expect(wrapper.text()).toContain('可返回首页修改材料后重试')
    expect(wrapper.text()).toContain('失败不等于产品安全或无风险')
  })
})
