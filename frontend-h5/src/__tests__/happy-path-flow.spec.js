import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import InputPage from '../pages/InputPage.vue'
import StatusPage from '../pages/StatusPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import * as api from '../api/client'
import { completedTaskPayload, mountWithApp } from '../test/helpers'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    checkCompleteness: vi.fn(),
    createAnalysis: vi.fn(),
    getAnalysis: vi.fn(),
    copyText: vi.fn(async () => true),
  }
})

describe('H5 成功流程', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.useFakeTimers()
    api.checkCompleteness.mockReset()
    api.createAnalysis.mockReset()
    api.getAnalysis.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('输入→POST→轮询→报告，展示原文/风险/多候选；草稿 B 不串到任务 A', async () => {
    const sourceA = '任务A原文：区间外收益可能为零'
    api.checkCompleteness.mockResolvedValue({
      can_continue: true,
      summary: '输入完整，可以继续分析',
      questions: [],
    })
    api.createAnalysis.mockResolvedValue({ task_id: 'tsk_a', task_status: 'queued' })
    api.getAnalysis
      .mockResolvedValueOnce({
        task_id: 'tsk_a',
        task_status: 'running',
        stages: [{ name: 'classify', status: 'success', message: '识别中' }],
        source_text: sourceA,
        is_failure: false,
        report: null,
      })
      .mockResolvedValue(completedTaskPayload({ source_text: sourceA }))

    const { wrapper: input, router, store } = await mountWithApp(InputPage, {
      routeName: 'input',
    })
    const textarea = input.find('textarea')
    expect(textarea.exists()).toBe(true)
    await textarea.setValue(sourceA)
    await input.findAll('button').find((b) => b.text().includes('开始分析')).trigger('click')
    await flushPromises()

    expect(api.createAnalysis).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('status')
    expect(router.currentRoute.value.params.taskId).toBe('tsk_a')

    // Pinia 草稿改成任务 B，报告仍只能用 GET 的任务 A 原文
    store.setDraft('任务B草稿：不该出现在报告页', 'loan')

    const { wrapper: status } = await mountWithApp(StatusPage, {
      routeName: 'status',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(900)
    await flushPromises()
    await nextTick()

    expect(api.getAnalysis).toHaveBeenCalled()
    // 第二次成功后应进入报告
    expect(status.vm).toBeTruthy()

    const { wrapper: report } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()

    expect(report.text()).toContain(sourceA)
    expect(report.text()).not.toContain('任务B草稿')
    expect(report.text()).toContain('区间外收益可能为零')
    expect(report.text()).toContain('结构性存款')
    expect(report.text()).toContain('消费贷')
    expect(report.text()).toContain('0.91')
  })

  it('状态页一次网络失败后仍可恢复并进入报告', async () => {
    api.getAnalysis
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValue(completedTaskPayload())

    const { router } = await mountWithApp(StatusPage, {
      routeName: 'status',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    await vi.advanceTimersByTimeAsync(1200)
    await flushPromises()

    expect(api.getAnalysis.mock.calls.length).toBeGreaterThanOrEqual(2)
    expect(router.currentRoute.value.name).toBe('report')
  })
})
