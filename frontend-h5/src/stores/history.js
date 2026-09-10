import { defineStore } from 'pinia'

const HISTORY_KEY = 'crusher_history'
const MAX_HISTORY = 20

export const useHistoryStore = defineStore('history', {
  state: () => ({
    list: [],
  }),
  getters: {
    hasHistory: (state) => state.list.length > 0,
  },
  actions: {
    restore() {
      try {
        const raw = localStorage.getItem(HISTORY_KEY)
        if (raw) {
          const data = JSON.parse(raw)
          this.list = Array.isArray(data) ? data : []
        }
      } catch {
        this.list = []
      }
    },
    _persist() {
      try {
        localStorage.setItem(HISTORY_KEY, JSON.stringify(this.list.slice(0, MAX_HISTORY)))
      } catch {
        /* ignore */
      }
    },
    add(record) {
      if (!record?.taskId) return
      this.list = [
        {
          taskId: record.taskId,
          title: record.title || '未命名分析',
          preview: (record.preview || '').slice(0, 80),
          productName: record.productName || '',
          findingCount: record.findingCount || 0,
          createdAt: record.createdAt || Date.now(),
        },
        ...this.list.filter((r) => r.taskId !== record.taskId),
      ].slice(0, MAX_HISTORY)
      this._persist()
    },
    remove(taskId) {
      this.list = this.list.filter((r) => r.taskId !== taskId)
      this._persist()
    },
    clear() {
      this.list = []
      try {
        localStorage.removeItem(HISTORY_KEY)
      } catch {
        /* ignore */
      }
    },
  },
})
