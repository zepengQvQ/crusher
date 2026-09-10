import { defineStore } from 'pinia'
import { createFollowUp } from '../api/client'

const CHAT_KEY = 'crusher_chat'

function mockAiReply(question) {
  const q = (question || '').trim()
  if (!q) return '请输入你的问题，我可以帮你解读条款~'
  if (/最坏|损失|最大.*风险/.test(q)) {
    return '根据这份条款的风险发现，最坏情况下可能面临：\n\n1) 收益大幅低于预期；\n2) 流动性受限，无法提前赎回；\n3) 若挂钩标的剧烈波动，可能损失部分收益。\n\n建议仅用闲置资金投资，不要 all in 哦~'
  }
  if (/适合|老人|小白|新手|老年人/.test(q)) {
    return '这份产品【不太适合】风险偏好低的人群：\n\n· 风险点：收益浮动 + 流动性弱 + 结构复杂\n· 适合：有一定投资经验、资金短期不用的投资者\n· 老年人建议：优先选择保本保息的普通存款或国债'
  }
  if (/提前|赎回|支取|违约/.test(q)) {
    return '关于提前退出的条款：\n\n· 若产品「不支持提前赎回」，投资期内无法取回资金\n· 风险：急用钱时只能等到期\n· 建议：用 3-6 个月生活费以外的闲置资金购买'
  }
  if (/保本|本金|安全/.test(q)) {
    return '结构性存款通常**本金有保障**（银行存款属性），但**收益不保证**。\n\n本金 + 最低收益基本有保障，高收益部分取决于挂钩标的表现。'
  }
  return `我来帮你分析「${q}」：\n\n建议关注：\n1️⃣ 先看原文证据中是否直接写明；\n2️⃣ 再看关键参数里的数值是否合理；\n3️⃣ 最后结合风险发现综合判断。\n\n可以问得更具体一点，比如「最坏情况损失多少」~`
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    messages: [],
    contextText: '',
    contextFindings: [],
    pendingQuestions: [],
  }),
  actions: {
    restore() {
      try {
        const raw = sessionStorage.getItem(CHAT_KEY)
        if (raw) {
          const d = JSON.parse(raw)
          this.messages = Array.isArray(d?.messages) ? d.messages : []
          this.contextText = d?.contextText || ''
          this.contextFindings = Array.isArray(d?.contextFindings) ? d.contextFindings : []
          this.pendingQuestions = Array.isArray(d?.pendingQuestions) ? d.pendingQuestions : []
        }
      } catch {
        this.messages = []
      }
    },
    _persist() {
      try {
        sessionStorage.setItem(
          CHAT_KEY,
          JSON.stringify({
            messages: this.messages,
            contextText: this.contextText,
            contextFindings: this.contextFindings,
            pendingQuestions: this.pendingQuestions,
          }),
        )
      } catch {
        /* ignore */
      }
    },
    setContext(text, findings = [], pendingQuestions = []) {
      this.contextText = text || ''
      this.contextFindings = findings || []
      this.pendingQuestions = pendingQuestions || []
      if (!this.messages.length) {
        this.messages.push({
          id: 'welcome_' + Date.now(),
          role: 'ai',
          content:
            '你好~我是你的条款解读助手\n\n基于刚才的分析报告，你可以问我：\n• 最坏情况会损失多少？\n• 适合老年人买吗？\n• 提前赎回有什么费用？',
          time: Date.now(),
        })
      }
      this._persist()
    },
    async send(question) {
      const q = (question || '').trim()
      if (!q) return null
      const userMsg = {
        id: 'u_' + Date.now(),
        role: 'user',
        content: q,
        time: Date.now(),
      }
      this.messages.push(userMsg)
      this._persist()

      let reply
      // 有关联原文时走真实追问接口；否则用本地兜底
      if (this.contextText) {
        try {
          const data = await createFollowUp(q, this.contextText, this.pendingQuestions)
          if (data?.answer) {
            reply = data.answer
            if (data.status === 'insufficient_evidence') {
              reply = '⚠️ 材料证据不足，无法给出确定结论。\n\n' + data.answer
            } else if (data.status === 'out_of_scope') {
              reply = '该问题超出了当前材料范围。\n\n' + data.answer
            }
          } else {
            reply = mockAiReply(q)
          }
        } catch {
          reply = mockAiReply(q)
        }
      } else {
        await new Promise((r) => setTimeout(r, 500))
        reply = mockAiReply(q)
      }

      const aiMsg = {
        id: 'a_' + Date.now(),
        role: 'ai',
        content: reply,
        time: Date.now(),
      }
      this.messages.push(aiMsg)
      this._persist()
      return aiMsg
    },
    clear() {
      this.messages = []
      this._persist()
    },
  },
})

