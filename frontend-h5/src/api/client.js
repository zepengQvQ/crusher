import axios from 'axios'

/**
 * @typedef {import('./generated-types.js').CreateAnalysisRequest} CreateAnalysisRequest
 * @typedef {import('./generated-types.js').CreateAnalysisResponse} CreateAnalysisResponse
 * @typedef {import('./generated-types.js').TaskResponse} TaskResponse
 */

const http = axios.create({
  baseURL: '',
  timeout: 15000,
})

/**
 * 提交分析。
 * @param {string} text
 * @param {{ demoError?: string, productHint?: string }} [options]
 * @returns {Promise<CreateAnalysisResponse>}
 */
export async function createAnalysis(text, options = {}) {
  /** @type {CreateAnalysisRequest} */
  const payload = {
    text,
    product_hint: options.productHint || 'auto',
    locale: 'zh-CN',
  }
  if (options.demoError) {
    payload.demo_error = options.demoError
  }
  const { data } = await http.post('/api/v1/analyses', payload)
  return data
}

/**
 * 查询任务状态与报告。
 * @param {string} taskId
 * @returns {Promise<TaskResponse>}
 */
export async function getAnalysis(taskId) {
  const { data } = await http.get(`/api/v1/analyses/${taskId}`)
  return data
}

export async function healthCheck() {
  const { data } = await http.get('/health')
  return data
}

export function pickErrorMessage(error) {
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED') return '请求太慢超时了，请稍后重试'
    return '网络异常或服务不可达，请检查网络后重试'
  }
  const detail = error.response.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return error.message || '请求失败'
}

export async function copyText(text) {
  const value = String(text || '')
  if (!value) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(value)
      return true
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement('textarea')
    ta.value = value
    ta.setAttribute('readonly', 'true')
    ta.style.position = 'fixed'
    ta.style.left = '-9999px'
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}
