import { mount, flushPromises } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import CorrectionSheet from '../components/CorrectionSheet.vue'
import ReportPage from '../pages/ReportPage.vue'
import * as api from '../api/client'
import { completedTaskPayload, mountWithApp } from '../test/helpers'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    getAnalysis: vi.fn(),
    createCorrection: vi.fn(),
    copyText: vi.fn(async () => true),
  }
})

vi.mock('vant', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, showToast: vi.fn() }
})

describe('correction-reanalysis-flow', () => {
  beforeEach(() => {
    sessionStorage.clear()
    api.getAnalysis.mockReset()
    api.createCorrection.mockReset()
  })

  it('ReportPage 提供纠错入口且区分材料未说明', async () => {
    const payload = completedTaskPayload({
      report: {
        ...completedTaskPayload().report,
        key_parameters: [
          {
            key: 'amount',
            label: '借款金额',
            value: null,
            status: 'not_disclosed',
            amount: null,
          },
          {
            key: 'annual_interest_rate',
            label: '年利率',
            value: '12%',
            status: 'document_fact',
            amount: null,
          },
        ],
      },
    })
    api.getAnalysis.mockResolvedValue(payload)
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_a' },
      props: { taskId: 'tsk_a' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('材料未说明')
    expect(wrapper.text()).toContain('产品认错了')
    expect(wrapper.text()).toContain('原文错了')
    expect(wrapper.text()).toContain('年利率')
  })

  it('CorrectionSheet 提交 fact_value 并展示前后差异', async () => {
    api.createCorrection.mockResolvedValue({
      task_id: 'tsk_child',
      task_status: 'queued',
    })
    const wrapper = mount(CorrectionSheet, {
      props: {
        modelValue: true,
        taskId: 'tsk_parent',
        mode: 'fact_value',
        parameterKey: 'amount',
        previousValue: '100000',
        sourceText: '原文',
        productHint: 'loan',
      },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('当前识别为')
    expect(wrapper.text()).toContain('100000')
    const fields = wrapper.findAll('textarea')
    await fields.at(0).setValue('200000')
    await flushPromises()
    expect(wrapper.text()).toContain('将改成')
    expect(wrapper.text()).toContain('200000')
    await wrapper.findAll('button').at(0).trigger('click')
    await flushPromises()
    expect(api.createCorrection).toHaveBeenCalledWith('tsk_parent', {
      corrections: [
        {
          kind: 'fact_value',
          parameter_key: 'amount',
          corrected_value: '200000',
          previous_value: '100000',
        },
      ],
    })
  })

  it('修订报告展示父任务追溯', async () => {
    api.getAnalysis.mockResolvedValue(
      completedTaskPayload({
        parent_task_id: 'tsk_parent',
        revision: {
          revision_no: 1,
          parent_task_id: 'tsk_parent',
          corrections: [
            {
              correction_id: 'cor_1',
              kind: 'fact_value',
              previous_value: '1',
              new_value: '2',
              parameter_key: 'amount',
              created_at: '2026-01-01T00:00:00Z',
            },
          ],
          created_at: '2026-01-01T00:00:00Z',
          note: '',
        },
      }),
    )
    const { wrapper } = await mountWithApp(ReportPage, {
      routeName: 'report',
      params: { taskId: 'tsk_child' },
      props: { taskId: 'tsk_child' },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('修订 #1')
    expect(wrapper.text()).toContain('tsk_parent')
    expect(wrapper.text()).toContain('未覆盖原报告')
  })
})
