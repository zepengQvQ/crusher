import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import ClarificationCard from '../components/ClarificationCard.vue'

vi.mock('vant', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, showToast: vi.fn() }
})

describe('clarification-flow', () => {
  it('展示业务追问文案且不含字段名，点击选项发出 answer', async () => {
    const result = {
      can_continue: false,
      summary: '还需确认 1 项后才能继续',
      questions: [
        {
          question_id: 'product_type_confirm',
          prompt: '这是结构性存款还是贷款？',
          gap_kind: 'value_conflict',
          control: 'buttons',
          options: [
            { value: 'structured_deposit', label: '结构性存款' },
            { value: 'loan', label: '贷款' },
          ],
        },
      ],
    }
    const wrapper = mount(ClarificationCard, { props: { result } })
    expect(wrapper.text()).toContain('这是结构性存款还是贷款？')
    expect(wrapper.text()).not.toContain('source_envelopes')
    expect(wrapper.text()).not.toContain('product_hint')
    await wrapper.findAll('button').at(0).trigger('click')
    expect(wrapper.emitted('answer')?.[0]?.[0]).toEqual({
      question_id: 'product_type_confirm',
      value: 'structured_deposit',
    })
  })
})
