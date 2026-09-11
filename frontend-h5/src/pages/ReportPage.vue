<template>
  <div class="page report-page">
    <van-nav-bar title="分析报告" left-arrow @click-left="goBack" />

    <div v-if="loading" class="block">
      <van-skeleton title :row="8" :avatar="true" />
    </div>

    <div v-else-if="loadError" class="block">
      <van-empty :description="loadError" />
    </div>

    <template v-else-if="report">
      <div v-if="revisionBanner" class="block">
        <van-notice-bar left-icon="replay" :text="revisionBanner" />
      </div>

      <div v-if="outcomeBanner" class="block">
        <van-notice-bar
          left-icon="warning-o"
          :text="outcomeBanner"
          color="#9a3412"
          background="#fff7ed"
        />
        <ul v-if="nextSteps.length" class="next-steps">
          <li v-for="(s, i) in nextSteps" :key="'ns' + i">{{ s }}</li>
        </ul>
      </div>

      <div class="block dashboard-block">
        <div class="dashboard-grid">
          <div class="dash-left">
            <van-circle
              v-model="dashScore"
              :rate="dashRate"
              :size="96"
              :stroke-width="8"
              :color="dashColor"
              layer-color="var(--crusher-bg-gray)"
              text=""
            >
              <div class="dash-inner">
                <div class="dash-score dashboard-number" :style="{ color: dashColor }">
                  {{ dashScore }}
                </div>
                <div class="dash-label">{{ dashLevelText }}</div>
              </div>
            </van-circle>
          </div>
          <div class="dash-right">
            <div class="dash-title">
              <van-tag type="primary" round style="font-size:12px">{{ productName }}</van-tag>
              <span style="margin-left:6px;font-size:12px;color:var(--crusher-ink-3)">
                评级 {{ productGradeText }}
              </span>
            </div>
            <div class="dash-conclusion">{{ conclusion }}</div>
            <div class="dash-counts">
              <div class="count-item high" v-if="highCount > 0">
                <span class="count-dot"></span>
                <span class="count-label">高</span>
                <span class="count-num">{{ highCount }}</span>
              </div>
              <div class="count-item mid" v-if="midCount > 0">
                <span class="count-dot"></span>
                <span class="count-label">中</span>
                <span class="count-num">{{ midCount }}</span>
              </div>
              <div class="count-item low" v-if="lowCount > 0">
                <span class="count-dot"></span>
                <span class="count-label">低</span>
                <span class="count-num">{{ lowCount }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="block" v-if="displayPlain">
        <div class="block-title">一句话说明</div>
        <div class="plain-box">
          <p>{{ displayPlain }}</p>
        </div>
      </div>

      <div class="block">
        <div class="section-header">
          <h3>需要留意的点</h3>
          <span class="more">{{ findings.length }} 条</span>
        </div>
        <van-empty
          v-if="!findings.length"
          description="这次没抓到风险点；不等于产品一定安全"
          image="success"
        />
        <van-collapse v-else v-model="activeFindings">
          <van-collapse-item
            v-for="(f, idx) in findings"
            :key="f.id || idx"
            :name="String(f.id || idx)"
          >
            <template #title>
              <div class="finding-title-row">
                <span class="sev-badge" :class="'sev-' + sevClass(f.finding_severity)">
                  {{ sevLabel(f.finding_severity) }}
                </span>
                <span class="finding-name">{{ f.title || '发现' }}</span>
              </div>
            </template>
            <p class="finding-explain">{{ f.explanation }}</p>
            <div
              v-for="(ev, eidx) in f.evidence || []"
              :key="eidx"
              class="evidence-block"
            >
              <div class="evidence-label">材料原文</div>
              <blockquote>{{ ev.quote }}</blockquote>
              <div class="evidence-actions">
                <button type="button" class="ghost-action ghost-action--link" @click="onCopy(ev.quote)">
                  <van-icon name="description" size="14" />
                  复制原文
                </button>
              </div>
            </div>
          </van-collapse-item>
        </van-collapse>
      </div>

      <div class="block">
        <div class="section-header">
          <h3>产品类型</h3>
          <button type="button" class="ghost-action" @click="openCorrection('product_type')">
            <van-icon name="edit" size="14" />
            产品认错了
          </button>
        </div>
        <van-cell-group :border="false">
          <van-cell
            v-for="(c, idx) in report.product_candidates || []"
            :key="c.product_type_id + idx"
            :title="c.product_type_name || c.product_type_id"
            :label="candidateLabel(c)"
            :value="confidenceLabel(c.confidence)"
            size="large"
          />
        </van-cell-group>
      </div>

      <div class="block">
        <div class="block-title">材料里写明的关键信息</div>
        <van-cell-group :border="false" v-if="disclosedParams.length">
          <van-cell
            v-for="p in disclosedParams"
            :key="p.key"
            :title="p.label || p.key"
            size="large"
            is-link
            @click="openFactCorrection(p)"
          >
            <template #value>
              <div class="param-val">{{ formatParam(p) }}</div>
            </template>
          </van-cell>
        </van-cell-group>
        <p v-else class="soft-hint">材料里暂时没抽出可展示的关键数字/条款。</p>

        <details v-if="undisclosedParams.length" class="more-details">
          <summary>材料没写明的项（{{ undisclosedParams.length }}）</summary>
          <van-cell-group :border="false">
            <van-cell
              v-for="p in undisclosedParams"
              :key="p.key"
              :title="p.label || p.key"
              size="large"
              is-link
              @click="openFactCorrection(p)"
            >
              <template #value>
                <div class="param-val not-disclosed">材料未说明</div>
              </template>
            </van-cell>
          </van-cell-group>
        </details>
      </div>

      <div class="block" v-if="pendingItems.length">
        <div class="block-title">还想确认的问题</div>
        <van-cell-group :border="false">
          <van-cell v-for="(q, idx) in pendingItems" :key="'q' + idx" :title="q" size="large" />
        </van-cell-group>
      </div>

      <div class="block">
        <div class="section-header">
          <h3>原文</h3>
          <div class="row-actions">
            <button type="button" class="ghost-action" @click="openCorrection('source_text')">
              <van-icon name="edit" size="14" />
              原文错了
            </button>
            <button
              type="button"
              class="ghost-action ghost-action--link"
              @click="sourceExpanded = !sourceExpanded"
            >
              {{ sourceExpanded ? '收起' : '展开' }}
              <van-icon :name="sourceExpanded ? 'arrow-up' : 'arrow-down'" size="12" />
            </button>
          </div>
        </div>
        <div class="source-wrap" :class="{ clamped: !sourceExpanded }">
          <div class="source-text" v-html="highlightedSource"></div>
        </div>
      </div>

      <details v-if="publication?.coverage" class="block more-details">
        <summary>系统检查范围（可选）</summary>
        <AnalysisCoverageCard :coverage="publication.coverage" />
      </details>

      <van-collapse v-model="moreOpen" class="block more-collapse">
        <van-collapse-item title="更多工具" name="tools">
          <EvidenceQuestionPanel :source-text="sourceText" :pending="pendingItems" />
          <div style="height:10px" />
          <ScenarioCalculator :key-parameters="report.key_parameters || []" />
          <div style="height:10px" />
          <ReportActions
            :report="report"
            kind="analysis"
            title="分析报告"
            :task-id="taskId"
            :source-text="sourceText"
          />
          <van-button
            block
            plain
            type="primary"
            class="touch-btn"
            style="margin-top:10px"
            @click="goCompareSecond"
          >
            加入第二款产品对照
          </van-button>
        </van-collapse-item>
      </van-collapse>

      <p class="disclaimer">
        {{ report.disclaimer || DISCLAIMER }}
      </p>

      <div class="bottom-bar">
        <van-button block type="primary" round class="touch-btn" @click="goChat">
          回到对话继续追问
        </van-button>
      </div>
    </template>

    <CorrectionSheet
      v-model="sheetOpen"
      :task-id="taskId"
      :mode="sheetMode"
      :parameter-key="sheetParamKey"
      :previous-value="sheetPrevValue"
      :source-text="sourceText"
      :product-hint="productHint"
      @submitted="onCorrectionSubmitted"
    />
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { copyText, getAnalysis } from '../api/client'
import { DISCLAIMER, FindingSeverity } from '../api/generated-types'
import AnalysisCoverageCard from '../components/AnalysisCoverageCard.vue'
import CorrectionSheet from '../components/CorrectionSheet.vue'
import EvidenceQuestionPanel from '../components/EvidenceQuestionPanel.vue'
import ReportActions from '../components/ReportActions.vue'
import ScenarioCalculator from '../components/ScenarioCalculator.vue'
import { useTaskStore } from '../stores/task'
import { useChatStore } from '../stores/chat'

const props = defineProps({
  taskId: { type: String, required: true },
})

const router = useRouter()
const store = useTaskStore()
const chatStore = useChatStore()

function syncChatContext() {
  if (!report.value) return
  chatStore.setContext(
    sourceText.value,
    (report.value?.findings || []).map((f) => ({
      title: f.title,
      explanation: f.explanation,
      finding_severity: f.finding_severity,
    })),
    pendingItems.value,
    report.value,
  )
  if (props.taskId) {
    chatStore.lastTaskId = props.taskId
  }
}

function goBack() {
  syncChatContext()
  router.push({ name: 'chat' })
}

function goChat() {
  syncChatContext()
  router.push({ name: 'chat' })
}

const loading = ref(true)
const loadError = ref('')
const report = ref(null)
const publication = ref(null)
const revision = ref(null)
const parentTaskId = ref('')
const productHint = ref('auto')
const activeFindings = ref([])
const sourceExpanded = ref(false)
const sourceText = ref('')
const dashScore = ref(0)
const sheetOpen = ref(false)
const sheetMode = ref('fact_value')
const sheetParamKey = ref('')
const sheetPrevValue = ref('')
let active = true

function sevClass(sev) {
  if (sev === FindingSeverity.high) return 'high'
  if (sev === FindingSeverity.low) return 'low'
  return 'mid'
}
function sevLabel(sev) {
  if (sev === FindingSeverity.high) return '高'
  if (sev === FindingSeverity.low) return '低'
  return '中'
}

const findings = computed(() => report.value?.findings || [])
const highCount = computed(
  () => findings.value.filter((f) => f.finding_severity === FindingSeverity.high).length,
)
const midCount = computed(
  () => findings.value.filter((f) => f.finding_severity === FindingSeverity.mid).length,
)
const lowCount = computed(
  () => findings.value.filter((f) => f.finding_severity === FindingSeverity.low).length,
)

const moreOpen = ref([])
const allParams = computed(() => report.value?.key_parameters || [])
const disclosedParams = computed(() =>
  allParams.value.filter((p) => p && p.status !== 'not_disclosed' && (p.value || p.amount != null)),
)
const undisclosedParams = computed(() =>
  allParams.value.filter((p) => p && p.status === 'not_disclosed'),
)

const displayPlain = computed(() => {
  const t = String(report.value?.plain_language?.text || '').trim()
  if (!t) return ''
  if (/【事实】|【参数】|【风险】|【程序说明】|invents numbers|product_risk_grade|\bterm\s*:/i.test(t)) {
    return ''
  }
  return t
})

function confidenceLabel(confidence) {
  const n = Number(confidence)
  if (!Number.isFinite(n)) return ''
  if (n >= 0.8) return '较有把握'
  if (n >= 0.5) return '大致判断'
  return '把握不大'
}

const productName = computed(
  () => report.value?.product_candidates?.[0]?.product_type_name || '未知产品',
)

const productGradeText = computed(() => {
  const g = report.value?.product_risk_grade
  if (!g || g.status === 'not_disclosed' || !g.value) return '材料未说明'
  return g.value
})

const outcome = computed(
  () => publication.value?.outcome || report.value?.publication?.outcome || 'publish',
)

const nextSteps = computed(
  () => publication.value?.next_steps || report.value?.publication?.next_steps || [],
)

const outcomeBanner = computed(() => {
  const o = outcome.value
  const reason =
    publication.value?.user_reason || report.value?.publication?.user_reason || ''
  const clean = String(reason || '')
    .replace(/（[^）]*invents numbers[^）]*）/gi, '')
    .replace(/explanation invents numbers:[^。；\n]*/gi, '')
    .trim()
  if (o === 'publish_partial') {
    return clean || '部分内容已确认；通俗解释未通过校验，请以原文和风险点为准'
  }
  if (o === 'clarify') {
    return clean || '还有信息需要确认后才能继续'
  }
  return ''
})

const revisionBanner = computed(() => {
  if (!revision.value) return ''
  const parent = parentTaskId.value || revision.value.parent_task_id || ''
  const n = revision.value.revision_no
  return `本报告为修订 #${n}（父任务 ${parent}），未覆盖原报告`
})

const conclusion = computed(() => {
  const o = outcome.value
  if (o === 'clarify') {
    return publication.value?.user_reason || '请先确认下方问题后再继续'
  }
  if (o === 'publish_partial') {
    const scope = report.value?.analysis_scope || 'supported'
    if (scope === 'out_of_scope') {
      return '当前 Demo 未分析该产品，请选择结构性存款或贷款'
    }
    return (
      publication.value?.user_reason ||
      '部分结果已确认；通俗解释未通过校验或不适用'
    )
  }
  const scope = report.value?.analysis_scope || 'supported'
  if (scope === 'out_of_scope') {
    return '当前 Demo 未分析该产品，请选择结构性存款或贷款'
  }
  if (scope === 'needs_confirmation') {
    return '产品类型存在冲突，请确认后重新分析'
  }
  const n = findings.value.length
  if (!n) return '未命中当前已配置规则，不等于产品没有风险'
  if (highCount.value > 0) return `存在 ${highCount.value} 条高风险，请重点关注原文证据。`
  return `共发现 ${n} 条风险，请展开查看原文证据。`
})

const dashRate = computed(() => Math.max(0, 100 - dashScore.value))
const dashColor = computed(() => {
  if (dashScore.value >= 70) return '#ee0a24'
  if (dashScore.value >= 40) return '#ff976a'
  if (dashScore.value >= 20) return '#07c160'
  return '#1989fa'
})
const dashLevelText = computed(() => {
  if (dashScore.value >= 70) return '风险较高'
  if (dashScore.value >= 40) return '有一定风险'
  if (dashScore.value >= 20) return '风险较低'
  return '风险很低'
})

const highlightedSource = computed(() => {
  const text = sourceText.value || ''
  if (!text || !findings.value.length) return escapeHtml(text)
  const spans = []
  findings.value.forEach((f) => {
    const cls = sevClass(f.finding_severity)
    ;(f.evidence || []).forEach((ev) => {
      if (typeof ev.start === 'number' && typeof ev.end === 'number') {
        spans.push({ start: ev.start, end: ev.end, cls })
      }
    })
  })
  if (!spans.length) return escapeHtml(text)
  spans.sort((a, b) => a.start - b.start)
  const merged = []
  spans.forEach((s) => {
    const last = merged[merged.length - 1]
    if (last && s.start <= last.end) {
      last.end = Math.max(last.end, s.end)
      if (!last.cls.includes(s.cls)) last.cls = pickHigher(last.cls, s.cls)
    } else {
      merged.push({ ...s })
    }
  })
  let result = ''
  let cursor = 0
  merged.forEach((s) => {
    result += escapeHtml(text.slice(cursor, s.start))
    result += `<span class="highlight-${s.cls}">${escapeHtml(text.slice(s.start, s.end))}</span>`
    cursor = s.end
  })
  result += escapeHtml(text.slice(cursor))
  return result
})

function pickHigher(a, b) {
  const rank = { high: 3, mid: 2, low: 1 }
  return rank[a] >= rank[b] ? a : b
}
function escapeHtml(s) {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

const pendingItems = computed(() => {
  const seen = new Set()
  const out = []
  for (const m of report.value?.missing_disclosures || []) {
    const q = (m.question || m.key || '').trim()
    if (!q || seen.has(q)) continue
    seen.add(q)
    out.push(q)
  }
  for (const q of report.value?.pending_questions || []) {
    const text = String(q || '').trim()
    if (!text || seen.has(text)) continue
    seen.add(text)
    out.push(text)
  }
  return out
})

function candidateLabel(c) {
  const quotes = (c.evidence_quotes || []).filter(Boolean)
  if (!quotes.length) return '暂无识别证据'
  return `证据：${quotes.slice(0, 3).join('；')}`
}

function formatParam(p) {
  if (p.status === 'not_disclosed') return '材料未说明'
  if (p.status === 'user_asserted') {
    const v = p.key === 'amount' && p.amount != null ? String(p.amount) : p.value ?? '-'
    return `${v}（用户声明）`
  }
  if (p.key === 'amount' && p.amount != null) return String(p.amount)
  return p.value ?? '-'
}

function statusLabel(status) {
  if (status === 'user_asserted') return '用户声明，非原文事实'
  if (status === 'not_disclosed') return '材料未说明'
  if (status === 'document_fact') return '原文事实'
  return status || ''
}

function openCorrection(mode) {
  sheetMode.value = mode
  sheetParamKey.value = ''
  sheetPrevValue.value = ''
  sheetOpen.value = true
}

function openFactCorrection(p) {
  sheetMode.value = 'fact_value'
  sheetParamKey.value = p.key
  sheetPrevValue.value =
    p.status === 'not_disclosed' ? '' : p.value || (p.amount != null ? String(p.amount) : '')
  sheetOpen.value = true
}

function onCorrectionSubmitted(res) {
  showToast('已创建修订任务')
  store.setTask(res.task_id, res.task_status)
  router.replace({ name: 'status', params: { taskId: res.task_id } })
}

async function onCopy(text) {
  const ok = await copyText(text)
  showToast(ok ? '已复制到剪贴板' : '复制失败')
}

function goCompareSecond() {
  try {
    sessionStorage.setItem('crusher_compare_a', sourceText.value || '')
  } catch {
    /* ignore */
  }
  router.push('/compare')
}

onMounted(async () => {
  active = true
  store.restoreFromStorage()
  chatStore.restore()
  try {
    const data = await getAnalysis(props.taskId)
    if (!active) return
    if (data.task_status === 'queued' || data.task_status === 'running') {
      router.replace({ name: 'status', params: { taskId: props.taskId } })
      return
    }
    if (data.task_status === 'failed' || data.is_failure) {
      store.setError(data.error_message || '模型调用失败', data.error_code || '')
      router.replace({ name: 'error', params: { taskId: props.taskId } })
      return
    }
    if (!data.report) {
      loadError.value = '报告不存在'
      return
    }
    report.value = data.report
    publication.value = data.publication || data.report.publication || null
    revision.value = data.revision || null
    parentTaskId.value = data.parent_task_id || ''
    productHint.value = data.product_hint || 'auto'
    sourceText.value = data.source_text || ''
    const raw = highCount.value * 25 + midCount.value * 10 + lowCount.value * 4
    dashScore.value = Math.min(100, raw + (report.value?.missing_disclosures?.length || 0) * 3)
    activeFindings.value = []
    if (findings.value.length) activeFindings.value.push(String(findings.value[0].id ?? 0))
  } catch (e) {
    if (!active) return
    const code = e?.response?.data?.detail?.error_code || ''
    const msg = e?.response?.data?.detail?.message || e.message || '加载报告失败'
    loadError.value = code === 'TASK_NOT_FOUND' || e?.response?.status === 404
      ? '这份报告已经失效了，点左上角返回，重新分析一次即可。'
      : msg
  } finally {
    if (active) loading.value = false
  }
})

onUnmounted(() => {
  active = false
})
</script>

<style scoped>
.report-page { padding-bottom: 120px; }

.dashboard-block {
  background: var(--crusher-card-bg);
}
.dashboard-grid {
  display: flex;
  align-items: center;
  gap: 18px;
}
.dash-left { flex-shrink: 0; }
.dash-right { flex: 1; min-width: 0; }
.dash-inner {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
}
.dash-score { font-size: 30px; line-height: 1; }
.dash-label { font-size: 11px; color: var(--crusher-ink-3); margin-top: 4px; }
.dash-title { margin-bottom: 8px; display: flex; align-items: center; }
.dash-conclusion {
  font-size: 14px; color: var(--crusher-ink-2); line-height: 1.5;
  margin-bottom: 10px; font-weight: 500;
}
.dash-counts { display: flex; flex-wrap: wrap; gap: 8px; }
.count-item {
  display: flex; align-items: center; gap: 4px;
  padding: 3px 9px; border-radius: 999px; font-size: 12px;
  background: var(--crusher-bg-gray);
}
.count-dot { width: 8px; height: 8px; border-radius: 50%; }
.count-item.high { background: var(--crusher-danger-light); color: var(--crusher-danger); }
.count-item.high .count-dot { background: var(--crusher-danger); }
.count-item.mid { background: var(--crusher-warning-light); color: var(--crusher-warning); }
.count-item.mid .count-dot { background: var(--crusher-warning); }
.count-item.low { background: var(--crusher-primary-light); color: var(--crusher-primary); }
.count-item.low .count-dot { background: var(--crusher-primary); }
.count-item.safe { background: var(--crusher-success-light); color: var(--crusher-success); }
.count-item.safe .count-dot { background: var(--crusher-success); }
.count-label { opacity: 0.85; }
.count-num { font-weight: 700; }

.param-val { font-size: 14px; font-weight: 500; text-align: right; }
.param-val.not-disclosed { color: var(--crusher-warning); font-weight: 500; font-size: 13px; }

.finding-title-row { display: flex; align-items: center; gap: 8px; min-width: 0; }
.sev-badge {
  padding: 2px 8px; border-radius: 6px; font-size: 11px; font-weight: 700; color: #fff;
  flex-shrink: 0;
}
.sev-badge.sev-high { background: linear-gradient(135deg, #ee0a24, #ff6a6a); }
.sev-badge.sev-mid { background: linear-gradient(135deg, #ff976a, #f56723); }
.sev-badge.sev-low { background: linear-gradient(135deg, #1989fa, #4facfe); }
.finding-name { font-size: 14px; font-weight: 600; color: var(--crusher-ink); }

.finding-explain {
  margin: 12px 0 6px; font-size: 14px; line-height: 1.6; color: var(--crusher-ink-2);
  white-space: pre-wrap;
}
.evidence-block {
  margin-top: 10px; padding: 12px; background: var(--crusher-bg-gray);
  border-radius: var(--crusher-radius-md); border-left: 3px solid var(--crusher-primary);
}
.evidence-label {
  font-size: 12px; color: var(--crusher-ink-3); margin-bottom: 6px;
  display: flex; align-items: center; gap: 4px;
}
.evidence-block blockquote {
  margin: 0 0 6px; font-size: 14px; line-height: 1.6; color: var(--crusher-ink);
  white-space: pre-wrap;
}
.evidence-actions {
  display: flex; align-items: center; justify-content: space-between; margin-top: 8px;
}
.evidence-meta { font-size: 12px; color: var(--crusher-ink-3); }

.plain-box {
  display: flex; gap: 10px; padding: 14px;
  background: var(--crusher-primary-light);
  border-radius: var(--crusher-radius-md); border-left: 3px solid var(--crusher-primary);
}
.plain-box p {
  margin: 0; font-size: 14px; line-height: 1.7; color: var(--crusher-ink);
}
.soft-hint {
  margin: 0;
  font-size: 13px;
  color: var(--crusher-ink-3);
  line-height: 1.5;
}
.more-collapse {
  margin-top: 8px;
}
.more-details {
  margin-top: 8px;
}
.more-details summary {
  cursor: pointer;
  font-size: 13px;
  color: var(--crusher-ink-2);
  padding: 6px 0;
  list-style: none;
}
.more-details summary::-webkit-details-marker {
  display: none;
}

.row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.ghost-action {
  appearance: none;
  border: none;
  margin: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: var(--crusher-bg-gray);
  color: var(--crusher-ink-2);
  font-size: 12px;
  font-weight: 500;
  line-height: 1;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s ease, color 0.15s ease;
}
.ghost-action:active {
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
}
.ghost-action--link {
  background: transparent;
  color: var(--crusher-primary);
  padding: 0 6px;
  font-weight: 600;
}
.ghost-action--link:active {
  background: var(--crusher-primary-light);
}
.source-wrap {
  font-size: 14px; line-height: 1.7; color: var(--crusher-ink);
  background: var(--crusher-surface); padding: 12px; border-radius: 10px;
  white-space: pre-wrap; word-break: break-word;
}
.source-wrap.clamped {
  display: -webkit-box; -webkit-line-clamp: 5; line-clamp: 5; -webkit-box-orient: vertical;
  overflow: hidden; position: relative;
}
.source-wrap.clamped::after {
  content: ''; position: absolute; left: 0; right: 0; bottom: 0; height: 40px;
  background: linear-gradient(180deg, transparent, var(--crusher-surface));
}
.legend-row { display: flex; gap: 14px; margin-top: 10px; justify-content: flex-end; }
.legend-item {
  font-size: 12px; color: var(--crusher-ink-3);
  display: flex; align-items: center; gap: 4px;
}
.legend-item .dot { width: 10px; height: 10px; border-radius: 3px; }
.legend-item .dot.high { background: var(--crusher-danger-light); border: 1px solid var(--crusher-danger); }
.legend-item .dot.mid { background: var(--crusher-gold-light); border: 1px solid var(--crusher-gold); }
.legend-item .dot.low { background: var(--crusher-primary-light); border: 1px solid var(--crusher-primary); }

.next-steps {
  margin: 10px 0 0;
  padding-left: 1.2em;
  font-size: 13px;
  color: #9a3412;
  line-height: 1.5;
}

.disclaimer {
  margin: 12px 16px; color: var(--crusher-ink-3); font-size: 12px;
  line-height: 1.5; text-align: center;
}

.bottom-bar {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 480px; padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: var(--crusher-card-bg); display: flex; z-index: 99;
  border-top: 1px solid var(--crusher-border);
}
</style>
