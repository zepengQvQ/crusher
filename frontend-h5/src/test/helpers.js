import { createPinia, setActivePinia } from 'pinia'
import { createMemoryHistory, createRouter } from 'vue-router'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import InputPage from '../pages/InputPage.vue'
import StatusPage from '../pages/StatusPage.vue'
import ReportPage from '../pages/ReportPage.vue'
import ErrorPage from '../pages/ErrorPage.vue'
import DualInputPage from '../pages/DualInputPage.vue'
import DualReportPage from '../pages/DualReportPage.vue'
import { useTaskStore } from '../stores/task'

export function makeRouter(initial = '/') {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', name: 'input', component: InputPage },
      { path: '/dual', name: 'dual-input', component: DualInputPage },
      { path: '/dual/report', name: 'dual-report', component: DualReportPage },
      { path: '/status/:taskId', name: 'status', component: StatusPage, props: true },
      { path: '/report/:taskId', name: 'report', component: ReportPage, props: true },
      { path: '/error/:taskId?', name: 'error', component: ErrorPage, props: true },
    ],
  })
}

export function createSharedPinia() {
  const pinia = createPinia()
  setActivePinia(pinia)
  return pinia
}

export async function mountWithApp(
  component,
  { props = {}, routeName, params = {}, pinia } = {},
) {
  const activePinia = pinia || createSharedPinia()
  setActivePinia(activePinia)
  const router = makeRouter()
  await router.push({ name: routeName || 'input', params })
  await router.isReady()
  const wrapper = mount(component, {
    props,
    global: {
      plugins: [activePinia, router],
    },
  })
  await flushPromises()
  await nextTick()
  return { wrapper, router, pinia: activePinia, store: useTaskStore(activePinia) }
}

export function completedTaskPayload(overrides = {}) {
  return {
    task_id: 'tsk_a',
    task_status: 'completed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:01Z',
    stages: [],
    is_failure: false,
    source_text: '任务A原文：区间外收益可能为零',
    product_hint: 'structured_deposit',
    resolved_product_type: 'structured_deposit',
    analysis_scope: 'supported',
    report: {
      product_candidates: [
        {
          product_type_id: 'structured_deposit',
          product_type_name: '结构性存款',
          confidence: 0.91,
          evidence_quotes: ['结构性存款'],
        },
        {
          product_type_id: 'loan',
          product_type_name: '消费贷',
          confidence: 0.2,
          evidence_quotes: [],
        },
      ],
      resolved_product_type: 'structured_deposit',
      analysis_scope: 'supported',
      scope_reason: '自动识别',
      product_risk_grade: { value: 'R2', status: 'document_fact', note: null },
      plain_language: { text: '通俗解释', status: 'success' },
      key_parameters: [],
      findings: [
        {
          id: 'f1',
          title: '区间外收益可能为零',
          finding_severity: 'high',
          explanation: '风险说明',
          evidence: [{ quote: '区间外收益可能为零', start: 0, end: 9, source: 'input_text' }],
          rule_or_knowledge_id: 'r1',
          confidence: 0.9,
          needs_review: false,
        },
      ],
      missing_disclosures: [],
      general_references: [],
      pending_questions: [],
      disclaimer: '本 Demo 不进行用户适当性评估，不构成投资建议。',
    },
    ...overrides,
  }
}

export function failedTaskPayload(overrides = {}) {
  return {
    task_id: 'tsk_fail',
    task_status: 'failed',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:01Z',
    stages: [],
    is_failure: true,
    error_code: 'MODEL_TIMEOUT',
    error_message: '模型调用失败：等待超时',
    source_text: '失败任务原文：模拟超时条款',
    product_hint: 'loan',
    resolved_product_type: 'loan',
    analysis_scope: 'supported',
    report: null,
    ...overrides,
  }
}
