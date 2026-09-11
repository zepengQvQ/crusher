import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as client from '../api/client'
import { useChatStore } from '../stores/chat'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    createFollowUp: vi.fn(),
  }
})

describe('chat store uses follow-up API only', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    client.createFollowUp.mockReset()
  })

  it('calls createFollowUp with context text and uses answer', async () => {
    client.createFollowUp.mockResolvedValue({
      question: '提前还款有费用吗？',
      status: 'answered',
      answer: '根据已提交材料，提前还款需支付违约金。',
      evidence: [{ quote: '提前还款需支付违约金', start: 0, end: 10 }],
      missing_info: [],
      publication: { outcome: 'publish', user_reason: 'ok' },
    })
    const store = useChatStore()
    store.setContext('本贷款金额10万元。提前还款需支付违约金。', [], [])
    const msg = await store.send('提前还款有费用吗？')
    expect(client.createFollowUp).toHaveBeenCalledTimes(1)
    expect(client.createFollowUp.mock.calls[0][0]).toBe('提前还款有费用吗？')
    expect(client.createFollowUp.mock.calls[0][1]).toContain('提前还款需支付违约金')
    expect(msg.content).toContain('提前还款需支付违约金')
    expect(msg.meta?.status).toBe('answered')
  })

  it('does not invent local financial advice without context', async () => {
    const store = useChatStore()
    await expect(store.send('适合老年人买吗？')).rejects.toMatchObject({ code: 'NO_CONTEXT' })
    expect(client.createFollowUp).not.toHaveBeenCalled()
    const last = store.messages[store.messages.length - 1]
    expect(last.role).toBe('ai')
    expect(last.content).toContain('尚未关联分析材料')
    expect(last.content).not.toContain('不太适合')
  })

  it('does not fall back to local mock when API fails', async () => {
    client.createFollowUp.mockRejectedValue(new Error('network'))
    const store = useChatStore()
    store.setContext('本贷款金额10万元。提前还款需支付违约金。', [], [])
    await expect(store.send('保本吗？')).rejects.toBeTruthy()
    const last = store.messages[store.messages.length - 1]
    expect(last.content).toContain('追问失败')
    expect(last.content).not.toContain('本金有保障')
  })
})
