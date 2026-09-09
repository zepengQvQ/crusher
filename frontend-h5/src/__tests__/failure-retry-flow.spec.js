import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import StatusPage from '../pages/StatusPage.vue'
import ErrorPage from '../pages/ErrorPage.vue'
import * as api from '../api/client'
import { failedTaskPayload, mountWithApp } from '../test/helpers'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    createAnalysis: vi.fn(),
    getAnalysis: vi.fn(),
    copyText: vi.fn(async () => true),
  }
})

describe('H5 失败重试流程', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.useFakeTimers()
    api.createAnalysis.mockReset()
    api.getAnalysis.mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('模型失败进入错误页，按 taskId 恢复原文，失败文案不是「无风险」', async () => {
    const source = '失败任务原文：模拟超时条款'
    api.getAnalysis.mockResolvedValue(failedTaskPayload({ source_text: source }))

    const { router, store } = await mountWithApp(StatusPage, {
      routeName: 'status',
      params: { taskId: 'tsk_fail' },
      props: { taskId: 'tsk_fail' },
    })
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('error')
    expect(router.currentRoute.value.params.taskId).toBe('tsk_fail')

    // 故意放一个错误的全局草稿，错误页有 taskId 时不得回退它
    store.setDraft('全局错误草稿，不应用于重试', 'auto')
    store.setError('模型调用失败：等待超时', 'MODEL_TIMEOUT')

    const { wrapper: error, router: errorRouter } = await mountWithApp(ErrorPage, {
      routeName: 'error',
      params: { taskId: 'tsk_fail' },
      props: { taskId: 'tsk_fail' },
    })
    await flushPromises()

    const text = error.text()
    expect(text).toContain(source)
    expect(text).not.toContain('全局错误草稿')
    expect(text).not.toContain('未发现风险')
    expect(text).not.toContain('没有风险')
    expect(text).toContain('模型调用失败')

    api.createAnalysis.mockResolvedValue({ task_id: 'tsk_retry', task_status: 'queued' })
    await error.findAll('button').find((b) => b.text().includes('重新分析')).trigger('click')
    await flushPromises()

    expect(api.createAnalysis).toHaveBeenCalledWith(
      source,
      expect.objectContaining({ productHint: expect.any(String) }),
    )
    expect(errorRouter.currentRoute.value.name).toBe('status')
    expect(errorRouter.currentRoute.value.params.taskId).toBe('tsk_retry')
  })
})
