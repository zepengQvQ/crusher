import { defineStore } from 'pinia'

const STORAGE_KEY = 'crusher_task'

/**
 * sessionStorage 只存 taskId / 状态 / 产品选择，不存金融原文全文。
 * 草稿文本仅在 Pinia 内存中，刷新未提交草稿可丢失。
 */
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
      this._persistMeta()
    },
    clearDraft() {
      this.draftText = ''
    },
    setTask(taskId, taskStatus = 'queued', stages = []) {
      this.taskId = taskId
      this.taskStatus = taskStatus
      this.stages = stages || []
      this.lastError = ''
      this.lastErrorCode = ''
      this._persistMeta()
    },
    setError(message, errorCode = '') {
      this.lastError = message || '未知错误'
      this.lastErrorCode = errorCode || ''
    },
    restoreFromStorage() {
      try {
        const raw = sessionStorage.getItem(STORAGE_KEY)
        if (!raw) return null
        const data = JSON.parse(raw)
        if (data?.productHint) {
          this.productHint = data.productHint
        }
        // 兼容旧版曾写入 text 的脏数据：忽略 text，不回填草稿
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
      this.draftText = ''
      this.productHint = 'auto'
      sessionStorage.removeItem(STORAGE_KEY)
    },
    _persistMeta() {
      try {
        sessionStorage.setItem(
          STORAGE_KEY,
          JSON.stringify({
            taskId: this.taskId || '',
            taskStatus: this.taskStatus || '',
            productHint: this.productHint || 'auto',
          }),
        )
      } catch {
        /* ignore quota */
      }
    },
  },
})
