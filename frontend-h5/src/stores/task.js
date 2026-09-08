import { defineStore } from 'pinia'

const STORAGE_KEY = 'crusher_task'

/** 只保存任务号和状态，不保存整段原文。 */
export const useTaskStore = defineStore('task', {
  state: () => ({
    taskId: '',
    taskStatus: '',
    stages: [],
    lastError: '',
    lastErrorCode: '',
  }),
  actions: {
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
