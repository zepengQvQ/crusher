import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import {
  createSharedPinia,
  failedTaskPayload,
  mountWithApp,
} from '../test/helpers'
import * as client from '../api/client'
import ErrorPage from '../pages/ErrorPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import StatusPage from '../pages/StatusPage.vue'
import InputPage from '../pages/InputPage.vue'
import { useTaskStore } from '../stores/task'

describe('P0-RC-11 task binding', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('retries task A with A hint even when store has B hint (shared pinia)', async () => {
    const pinia = createSharedPinia()
    const store = useTaskStore(pinia)
    store.setDraft('任务B贷款草稿', 'loan')

    const getSpy = vi.spyOn(client, 'getAnalysis').mockResolvedValue(
      failedTaskPayload({
        task_id: 'tsk_a',
        source_text: '任务A结构性存款原文',
        product_hint: 'structured_deposit',
      }),
    )
    const createSpy = vi.spyOn(client, 'createAnalysis').mockResolvedValue({
      task_id: 'tsk_retry',
      task_status: 'queued',
    })

    const { wrapper } = await mountWithApp(ErrorPage, {
      pinia,
      routeName: 'error',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(getSpy).toHaveBeenCalledWith('tsk_a')
    expect(store.productHint).toBe('loan') // Pinia 仍可能是 B

    await wrapper.find('.touch-btn').trigger('click')
    await flushPromises()
    expect(createSpy).toHaveBeenCalledWith('任务A结构性存款原文', {
      productHint: 'structured_deposit',
    })
  })

  it('status poll restores draft for keep-input reanalyze', async () => {
    const pinia = createSharedPinia()
    vi.spyOn(client, 'getAnalysis').mockResolvedValue(
      failedTaskPayload({
        task_id: 'tsk_status',
        task_status: 'running',
        is_failure: false,
        error_code: null,
        error_message: null,
        source_text: '状态页恢复原文',
        product_hint: 'loan',
      }),
    )
    const { wrapper, store } = await mountWithApp(StatusPage, {
      pinia,
      routeName: 'status',
      params: { taskId: 'tsk_status' },
      props: { taskId: 'tsk_status' },
    })
    await flushPromises()
    expect(store.draftText).toBe('状态页恢复原文')
    expect(store.productHint).toBe('loan')
    expect(wrapper.text()).toContain('重新分析（保留输入）')
  })

  it('clear removes legacy crusher_draft', () => {
    sessionStorage.setItem('crusher_draft', '旧版金融全文')
    const pinia = createSharedPinia()
    const store = useTaskStore(pinia)
    store.clear()
    expect(sessionStorage.getItem('crusher_draft')).toBeNull()
  })

  it('report page does not navigate after unmount', async () => {
    let resolveGet
    const pending = new Promise((resolve) => {
      resolveGet = resolve
    })
    vi.spyOn(client, 'getAnalysis').mockReturnValue(pending)
    const { wrapper, router } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_u' },
      props: { taskId: 'tsk_u' },
    })
    const replaceSpy = vi.spyOn(router, 'replace')
    wrapper.unmount()
    resolveGet(
      failedTaskPayload({
        task_id: 'tsk_u',
        task_status: 'failed',
      }),
    )
    await flushPromises()
    expect(replaceSpy).not.toHaveBeenCalled()
  })

  it('error retry does not navigate after unmount', async () => {
    vi.spyOn(client, 'getAnalysis').mockResolvedValue(
      failedTaskPayload({
        source_text: '待重试原文',
        product_hint: 'loan',
      }),
    )
    let resolveCreate
    vi.spyOn(client, 'createAnalysis').mockReturnValue(
      new Promise((resolve) => {
        resolveCreate = resolve
      }),
    )
    const { wrapper, router } = await mountWithApp(ErrorPage, {
      routeName: 'error',
      params: { taskId: 'tsk_e' },
      props: { taskId: 'tsk_e' },
    })
    await flushPromises()
    const replaceSpy = vi.spyOn(router, 'replace')
    await wrapper.find('.touch-btn').trigger('click')
    wrapper.unmount()
    resolveCreate({ task_id: 'tsk_new', task_status: 'queued' })
    await flushPromises()
    expect(replaceSpy).not.toHaveBeenCalled()
  })

  it('shared pinia proves B draft then A error retry ignores it', async () => {
    const pinia = createSharedPinia()
    const { store: inputStore } = await mountWithApp(InputPage, {
      pinia,
      routeName: 'input',
    })
    inputStore.setDraft('任务B全文', 'loan')
    expect(useTaskStore(pinia).draftText).toBe('任务B全文')

    vi.spyOn(client, 'getAnalysis').mockResolvedValue(
      failedTaskPayload({
        source_text: '任务A全文',
        product_hint: 'structured_deposit',
      }),
    )
    const createSpy = vi.spyOn(client, 'createAnalysis').mockResolvedValue({
      task_id: 'tsk_x',
      task_status: 'queued',
    })
    const { wrapper } = await mountWithApp(ErrorPage, {
      pinia,
      routeName: 'error',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(useTaskStore(pinia).draftText).toBe('任务B全文')
    await wrapper.find('.touch-btn').trigger('click')
    await flushPromises()
    expect(createSpy.mock.calls[0][0]).toBe('任务A全文')
    expect(createSpy.mock.calls[0][1]).toEqual({ productHint: 'structured_deposit' })
  })
})
