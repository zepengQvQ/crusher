import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import ChatPage from '../pages/ChatPage.vue'
import DualInputPage from '../pages/DualInputPage.vue'
import ProductComparePage from '../pages/ProductComparePage.vue'
import InputPage from '../pages/InputPage.vue'
import DocumentUploadPage from '../pages/DocumentUploadPage.vue'
import * as client from '../api/client'
import { useTaskStore } from '../stores/task'
import {
  COMPARE_A_KEY,
  DUAL_SALES_PREFILL_KEY,
  INTENT_CONTEXT_KEY,
} from '../utils/intentContext'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    resolveIntent: vi.fn(),
    createFollowUp: vi.fn(),
  }
})

async function mountChat() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/chat', name: 'chat', component: ChatPage },
      { path: '/analyze', name: 'input', component: InputPage },
      { path: '/dual', name: 'dual-input', component: DualInputPage },
      { path: '/compare', name: 'compare', component: ProductComparePage },
      { path: '/upload', name: 'upload', component: DocumentUploadPage },
    ],
  })
  await router.push('/chat')
  await router.isReady()
  const wrapper = mount(ChatPage, {
    global: { plugins: [pinia, router] },
  })
  await flushPromises()
  return { wrapper, router, pinia, store: useTaskStore(pinia) }
}

describe('P2-RC-05 intent context preserve via IM guide', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
    client.resolveIntent.mockReset()
    client.createFollowUp.mockReset()
  })

  it('chat guide jump to dual keeps draft text as sales prefill', async () => {
    client.resolveIntent.mockResolvedValue({
      intent: 'dual_source_compare',
      status: 'resolved',
      source: 'rule',
      rationale: ['命中双材料'],
      missing: [],
      clarifying_options: [],
      use_case_key: 'AnalyzeDualSourcesUseCase',
    })

    const { wrapper, router, store } = await mountChat()
    store.setDraft('首页已粘贴的销售话术原文', 'auto')

    await wrapper.vm.send('对照销售话术和正式材料')
    await flushPromises()

    expect(client.resolveIntent).toHaveBeenCalled()
    expect(client.createFollowUp).not.toHaveBeenCalled()
    expect(sessionStorage.getItem(DUAL_SALES_PREFILL_KEY)).toContain('首页已粘贴')
    expect(sessionStorage.getItem(INTENT_CONTEXT_KEY)).toBeTruthy()
    expect(router.currentRoute.value.path).toBe('/dual')

    const dual = mount(DualInputPage, {
      global: { plugins: [createPinia(), router] },
    })
    await flushPromises()
    const fields = dual.findAll('textarea')
    expect(fields[0].element.value).toContain('首页已粘贴')
  })

  it('chat guide jump to compare prefills product A', async () => {
    client.resolveIntent.mockResolvedValue({
      intent: 'product_compare',
      status: 'resolved',
      source: 'rule',
      rationale: ['命中产品对比'],
      missing: [],
      clarifying_options: [],
      use_case_key: 'CompareProductsUseCase',
    })

    const { wrapper, router, store, pinia } = await mountChat()
    store.setDraft('产品A材料：贷款金额10万元', 'auto')

    await wrapper.vm.send('两款产品对比一下')
    await flushPromises()

    expect(sessionStorage.getItem(COMPARE_A_KEY)).toContain('产品A材料')
    expect(router.currentRoute.value.path).toBe('/compare')

    const cmp = mount(ProductComparePage, {
      global: { plugins: [pinia, router] },
    })
    await flushPromises()
    expect(cmp.findAll('textarea')[0].element.value).toContain('产品A材料')
  })
})
