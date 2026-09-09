import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { mountWithApp } from '../test/helpers'
import DualInputPage from '../pages/DualInputPage.vue'
import * as client from '../api/client'

describe('P1-01 dual compare', () => {
  beforeEach(() => {
    sessionStorage.clear()
    vi.restoreAllMocks()
  })

  it('submits both texts and navigates to dual report', async () => {
    const spy = vi.spyOn(client, 'createDualAnalysis').mockResolvedValue({
      sales_source: { source_id: 'a', source_type: 'sales_pitch', name: '销售', text: 'x', pages: 1 },
      official_source: {
        source_id: 'b',
        source_type: 'official_document',
        name: '正式',
        text: 'y',
        pages: 1,
      },
      comparisons: [
        {
          comparison_id: 'c1',
          subject: 'fee',
          status: 'conflict',
          summary: '冲突',
          sales_claim: {
            claim_id: 'cl1',
            subject: 'fee',
            summary: '不收费',
            negated: true,
            evidence: { source_id: 'a', quote: '不收费', start: 0, end: 3, confidence: 1 },
          },
          official_evidence: {
            source_id: 'b',
            quote: '收取0.5%',
            start: 0,
            end: 6,
            confidence: 1,
          },
          suggested_follow_up: '核对费用',
        },
      ],
      pending_questions: ['核对费用'],
      disclaimer: 'demo',
    })
    const { wrapper, router } = await mountWithApp(DualInputPage, {
      routeName: 'dual-input',
    })
    const fields = wrapper.findAll('textarea')
    expect(fields.length).toBeGreaterThanOrEqual(2)
    await fields[0].setValue('我们不收费')
    await fields[1].setValue('收取手续费0.5%')
    await wrapper.find('.main-btn').trigger('click')
    await flushPromises()
    expect(spy).toHaveBeenCalled()
    expect(router.currentRoute.value.name).toBe('dual-report')
  })
})
