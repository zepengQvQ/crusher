import axios from 'axios'

const http = axios.create({
  baseURL: '',
  timeout: 15000,
})

/**
 * 提交分析。
 * @param {string} text
 * @param {{ demoError?: string }} [options]
 */
export async function createAnalysis(text, options = {}) {
  const payload = {
    text,
    product_hint: 'auto',
    locale: 'zh-CN',
  }
  if (options.demoError) {
    payload.demo_error = options.demoError
  }
  const { data } = await http.post('/api/v1/analyses', payload)
  return data
}

export async function getAnalysis(taskId) {
  const { data } = await http.get(`/api/v1/analyses/${taskId}`)
  return data
}

export async function healthCheck() {
  const { data } = await http.get('/health')
  return data
}

export function pickErrorMessage(error) {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return error?.message || '请求失败'
}
