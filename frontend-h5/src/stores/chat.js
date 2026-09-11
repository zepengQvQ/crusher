import { defineStore } from 'pinia'
import { createFollowUp, pickErrorMessage } from '../api/client'

const CHAT_KEY = 'crusher_chat'

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
            '已关联刚才的分析材料。请围绕原文提问；回答将由服务端按证据接口返回，不会编造结论。',
          time: Date.now(),
        })
      }
      this._persist()
    },
    async send(question) {
      const text = String(question || '').trim()
      if (!text) return null

      const userMsg = {
        id: 'u_' + Date.now(),
        role: 'user',
        content: text,
        time: Date.now(),
      }
      this.messages.push(userMsg)
      this._persist()

      const source = (this.contextText || '').trim()
      if (!source) {
        const err = new Error('NO_CONTEXT')
        err.code = 'NO_CONTEXT'
        this.messages.push({
          id: 'a_' + Date.now(),
          role: 'ai',
          content:
            '尚未关联分析材料。请先完成条款分析，再从报告页进入追问；答案只来自服务端证据接口。',
          time: Date.now(),
        })
        this._persist()
        throw err
      }

      try {
        const data = await createFollowUp(text, source, this.pendingQuestions)
        if (!data || typeof data.answer !== 'string' || !data.answer.trim()) {
          throw new Error('追问接口未返回有效答案')
        }
        let reply = data.answer
        if (data.status === 'insufficient_evidence') {
          reply = '材料证据不足，无法给出确定结论。\n\n' + data.answer
        } else if (data.status === 'out_of_scope') {
          reply = '该问题超出了当前材料范围。\n\n' + data.answer
        }
        const aiMsg = {
          id: 'a_' + Date.now(),
          role: 'ai',
          content: reply,
          time: Date.now(),
          meta: {
            status: data.status,
            evidence: Array.isArray(data.evidence) ? data.evidence : [],
            publication: data.publication || null,
          },
        }
        this.messages.push(aiMsg)
        this._persist()
        return aiMsg
      } catch (e) {
        if (e?.code === 'NO_CONTEXT') throw e
        const msg = pickErrorMessage(e)
        this.messages.push({
          id: 'a_' + Date.now(),
          role: 'ai',
          content: `追问失败：${msg}\n\n请确认后端已启动，且已关联有效分析材料。`,
          time: Date.now(),
        })
        this._persist()
        throw e
      }
    },
    clear() {
      this.messages = []
      this._persist()
    },
  },
})
