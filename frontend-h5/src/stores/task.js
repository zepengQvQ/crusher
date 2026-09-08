import { defineStore } from 'pinia'

const STORAGE_KEY = 'crusher_task'
const DRAFT_KEY = 'crusher_draft'

/** 任务号进 session；草稿文本仅用于失败重试（Demo）。 */
export const useTaskStore = defineStore('task', {
  state: () => ({
    taskId: '',
    taskStatus: '',
    stages: [],
    lastError: '',
    lastErrorCode: '',
    draftText: '',
    productHint: 'auto',
  }),
  actions: {
    setDraft(text, productHint = 'auto') {
      this.draftText = text || ''
      this.productHint = productHint || 'auto'
      try {
        sessionStorage.setItem(
          DRAFT_KEY,
          JSON.stringify({ text: this.draftText, productHint: this.productHint }),
        )
      } catch {
        /* ignore quota */
      }
    },
    setTask(taskId, taskStatus = 'queued', stages = []) {
      this.taskId = taskId
      this.taskStatus = taskStatus
      this.stages = stages || []
      this.lastError = ''
      this.lastErrorCode = ''
      sessionStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ taskId, taskStatus }),
      )
    },
    setError(message, errorCode = '') {
      this.lastError = message || '未知错误'
      this.lastErrorCode = errorCode || ''
    },
    restoreFromStorage() {
      try {
        const draftRaw = sessionStorage.getItem(DRAFT_KEY)
        if (draftRaw) {
          const draft = JSON.parse(draftRaw)
          this.draftText = draft?.text || ''
          this.productHint = draft?.productHint || 'auto'
        }
        const raw = sessionStorage.getItem(STORAGE_KEY)
        if (!raw) return null
        const data = JSON.parse(raw)
        if (data?.taskId) {
          this.taskId = data.taskId
          this.taskStatus = data.taskStatus || ''
          return data.taskId
        }
      } catch {
        /* ignore */
      }
      return null
    },
    clear() {
      this.taskId = ''
      this.taskStatus = ''
      this.stages = []
      this.lastError = ''
      this.lastErrorCode = ''
      sessionStorage.removeItem(STORAGE_KEY)
    },
  },
})
