import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithApp } from '../test/helpers'
import InputPage from '../pages/InputPage.vue'
import DualInputPage from '../pages/DualInputPage.vue'
import ProductComparePage from '../pages/ProductComparePage.vue'
import * as client from '../api/client'
import {
  COMPARE_A_KEY,
  DUAL_SALES_PREFILL_KEY,
  INTENT_CONTEXT_KEY,
} from '../utils/intentContext'

describe('P2-RC-05 intent context preserve', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('smart jump to dual keeps pasted text as sales prefill', async () => {
    vi.spyOn(client, 'resolveIntent').mockResolvedValue({
      intent: 'dual_source_compare',
      status: 'resolved',
      source: 'rule',
      rationale: ['命中双材料'],
      missing: [],
      clarifying_options: [],
      use_case_key: 'AnalyzeDualSourcesUseCase',
    })

    const { wrapper, router } = await mountWithApp(InputPage)
    await wrapper.find('textarea').setValue('首页已粘贴的销售话术原文')
    const goal = wrapper.findAll('textarea')[1]
    if (goal) await goal.setValue('对照销售与正式材料')

    const smartBtn = wrapper
      .findAll('.touch-btn')
      .find((b) => b.text().includes('按目标识别') || b.text().includes('识别意图'))
    expect(smartBtn).toBeTruthy()
    await smartBtn.trigger('click')
    await flushPromises()

    expect(sessionStorage.getItem(DUAL_SALES_PREFILL_KEY)).toContain('首页已粘贴')
    expect(sessionStorage.getItem(INTENT_CONTEXT_KEY)).toBeTruthy()
    expect(router.currentRoute.value.path).toBe('/dual')

    const { wrapper: dual } = await mountWithApp(DualInputPage, { routeName: 'dual-input' })
    await flushPromises()
    const fields = dual.findAll('textarea')
    expect(fields[0].element.value).toContain('首页已粘贴')
  })

  it('smart jump to compare prefills product A', async () => {
    vi.spyOn(client, 'resolveIntent').mockResolvedValue({
      intent: 'product_compare',
      status: 'resolved',
      source: 'rule',
      rationale: ['命中产品对比'],
      missing: [],
      clarifying_options: [],
      use_case_key: 'CompareProductsUseCase',
    })

    const { wrapper, router, pinia } = await mountWithApp(InputPage)
    await wrapper.find('textarea').setValue('产品A材料：贷款金额10万元')
    const smartBtn = wrapper
      .findAll('.touch-btn')
      .find((b) => b.text().includes('按目标识别') || b.text().includes('识别意图'))
    await smartBtn.trigger('click')
    await flushPromises()

    expect(sessionStorage.getItem(COMPARE_A_KEY)).toContain('产品A材料')
    expect(router.currentRoute.value.path).toBe('/compare')

    // ProductComparePage 不在默认 helper 路由表时，直接挂载并带 pinia
    const { mount } = await import('@vue/test-utils')
    const { createMemoryHistory, createRouter } = await import('vue-router')
    const r = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/compare', name: 'compare', component: ProductComparePage }],
    })
    await r.push('/compare')
    await r.isReady()
    const cmp = mount(ProductComparePage, {
      global: { plugins: [pinia, r] },
    })
    await flushPromises()
    expect(cmp.findAll('textarea')[0].element.value).toContain('产品A材料')
  })
})
