import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import * as client from '../api/client'
import { useChatStore } from '../stores/chat'

vi.mock('../api/client', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    createFollowUp: vi.fn(),
    resolveIntent: vi.fn(),
    createAnalysis: vi.fn(),
    getAnalysis: vi.fn(),
    extractDocuments: vi.fn(),
  }
})

describe('chat store follow-up, guide and materials', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    sessionStorage.clear()
    client.createFollowUp.mockReset()
    client.resolveIntent.mockReset()
    client.createAnalysis.mockReset()
    client.getAnalysis.mockReset()
    client.extractDocuments.mockReset()
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
    expect(client.resolveIntent).not.toHaveBeenCalled()
    expect(msg.content).toContain('提前还款需支付违约金')
    expect(msg.meta?.status).toBe('answered')
  })

  it('without context uses intent guide and does not call follow-up', async () => {
    client.resolveIntent.mockResolvedValue({
      intent: 'single_analysis',
      status: 'resolved',
      source: 'rule',
      rationale: ['单材料分析'],
      missing: [],
      clarifying_options: [],
      use_case_key: 'AnalyzeSingleTextUseCase',
    })
    const store = useChatStore()
    const msg = await store.send('帮我分析这份条款')
    expect(client.createFollowUp).not.toHaveBeenCalled()
    expect(client.resolveIntent).toHaveBeenCalledTimes(1)
    expect(msg.meta?.kind).toBe('intent')
    expect(msg.meta?.decision?.intent).toBe('single_analysis')
    expect(msg.content).not.toContain('不太适合')
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

  it('addMaterial puts text into session context for follow-up', async () => {
    client.createFollowUp.mockResolvedValue({
      question: '有罚息吗？',
      status: 'answered',
      answer: '材料写明逾期按日计收罚息。',
      evidence: [],
      missing_info: [],
      publication: { outcome: 'publish', user_reason: 'ok' },
    })
    const store = useChatStore()
    store.addMaterial({
      kind: 'paste',
      name: '粘贴条款',
      text: '逾期部分按日利率0.05%计收罚息。',
    })
    expect(store.hasMaterials).toBe(true)
    expect(store.materialSourceText).toContain('罚息')
    const msg = await store.send('有罚息吗？')
    expect(client.resolveIntent).not.toHaveBeenCalled()
    expect(client.createFollowUp).toHaveBeenCalledWith(
      '有罚息吗？',
      expect.stringContaining('罚息'),
      [],
    )
    expect(msg.content).toContain('罚息')
  })

  it('analyzeMaterials without material pushes explicit tip', async () => {
    const store = useChatStore()
    await expect(store.analyzeMaterials()).rejects.toMatchObject({ code: 'NO_MATERIAL' })
    expect(client.createAnalysis).not.toHaveBeenCalled()
    const last = store.messages[store.messages.length - 1]
    expect(last.content).toContain('还没有材料')
  })

  it('analyzeMaterials creates task and records done bubble', async () => {
    client.createAnalysis.mockResolvedValue({ task_id: 'tsk_im', task_status: 'queued' })
    client.getAnalysis.mockResolvedValue({
      task_id: 'tsk_im',
      task_status: 'completed',
      source_text: '本贷款金额10万元。',
      report: { findings: [{ title: '罚息' }], pending_questions: [] },
      publication: { outcome: 'publish' },
    })
    const store = useChatStore()
    store.addMaterial({ kind: 'paste', text: '本贷款金额10万元。' })
    const result = await store.analyzeMaterials()
    expect(result.taskId).toBe('tsk_im')
    expect(client.createAnalysis).toHaveBeenCalled()
    expect(store.lastTaskId).toBe('tsk_im')
    const done = store.messages.filter((m) => m.meta?.kind === 'analyze_done').pop()
    expect(done?.content).toContain('分析完成')
    expect(done?.meta?.taskId).toBe('tsk_im')
  })

  it('addUploadFiles rejects empty extract without inventing text', async () => {
    client.extractDocuments.mockResolvedValue({
      combined_text: '',
      overall_status: 'failed',
      message: '无法识别正文',
    })
    const store = useChatStore()
    await expect(
      store.addUploadFiles([new File(['x'], 'a.pdf', { type: 'application/pdf' })]),
    ).rejects.toMatchObject({ code: 'EXTRACT_FAILED' })
    expect(store.materials).toHaveLength(0)
    const last = store.messages[store.messages.length - 1]
    expect(last.content).toContain('无法识别正文')
  })
})
