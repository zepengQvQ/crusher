<template>
  <div class="page">
    <van-nav-bar title="分析报告" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar left-icon="info-o" :text="DISCLAIMER" />
    <div v-if="loading" class="block">
      <van-skeleton title :row="6" />
    </div>
    <div v-else-if="loadError" class="block">
      <van-empty :description="loadError" />
      <van-button block type="primary" class="touch-btn" @click="$router.push('/')">
        返回重试
      </van-button>
    </div>
    <template v-else-if="report">
      <div class="block">
        <h3>一句结论</h3>
        <p class="conclusion">{{ conclusion }}</p>
        <p class="meta">
          产品风险评级：{{ productGradeText }}
          <span class="sep">｜</span>
          字段来源：{{ report.product_risk_grade?.status || '-' }}
        </p>
      </div>

      <div class="block">
        <h3>产品候选</h3>
        <van-cell
          v-for="(c, idx) in report.product_candidates || []"
          :key="c.product_type_id + idx"
          :title="c.product_type_name || c.product_type_id"
          :label="candidateLabel(c)"
          :value="`置信度 ${(Number(c.confidence) || 0).toFixed(2)}`"
        />
      </div>

      <div class="block">
        <h3>关键参数</h3>
        <van-cell
          v-for="p in report.key_parameters || []"
          :key="p.key"
          :title="p.label || p.key"
          :value="formatParam(p)"
        />
      </div>

      <div class="block">
        <h3>风险发现</h3>
        <van-empty
          v-if="!(report.findings || []).length"
          description="本次无风险发现（任务成功，不是失败）"
        />
        <van-collapse v-model="activeFindings">
          <van-collapse-item
            v-for="(f, idx) in report.findings || []"
            :key="f.id || idx"
            :name="String(f.id || idx)"
            :title="findingTitle(f)"
          >
            <p class="finding-explain">{{ f.explanation }}</p>
            <div
              v-for="(ev, eidx) in f.evidence || []"
              :key="eidx"
              class="evidence"
            >
              <div class="evidence-label">原文证据</div>
              <blockquote>{{ ev.quote }}</blockquote>
              <p class="evidence-meta">位置 {{ ev.start }}–{{ ev.end }}</p>
              <van-button
                size="small"
                plain
                class="touch-btn"
                @click="onCopy(ev.quote)"
              >
                复制证据
              </van-button>
            </div>
          </van-collapse-item>
        </van-collapse>
      </div>

      <div class="block">
        <h3>通俗解释</h3>
        <p>{{ report.plain_language?.text || '暂无通俗解释' }}</p>
      </div>

      <div class="block">
        <div class="row-between">
          <h3>原文折叠</h3>
          <van-button size="small" plain class="touch-btn" @click="sourceExpanded = !sourceExpanded">
            {{ sourceExpanded ? '收起' : '展开' }}
          </van-button>
        </div>
        <p class="source" :class="{ clamped: !sourceExpanded }">{{ sourceText }}</p>
        <van-button block plain class="touch-btn" @click="onCopy(sourceText)">复制原文</van-button>
      </div>

      <div class="block">
        <h3>待确认问题</h3>
        <van-cell
          v-for="(q, idx) in pendingItems"
          :key="'q' + idx"
          :title="q"
        />
        <van-empty
          v-if="!pendingItems.length"
          description="暂无待确认项"
        />
      </div>

      <div v-if="(report.general_references || []).length" class="block">
        <h3>行业参考（非本材料事实）</h3>
        <van-cell
          v-for="(r, idx) in report.general_references"
          :key="'r' + idx"
          :title="r.text"
          :label="r.source"
        />
      </div>

      <div class="block">
        <EvidenceQuestionPanel
          :source-text="sourceText"
          :pending="pendingItems"
        />
      </div>

      <div class="block">
        <ScenarioCalculator :key-parameters="report.key_parameters || []" />
      </div>

      <p class="disclaimer">{{ report.disclaimer || DISCLAIMER }}</p>
      <div class="block">
        <van-button block type="primary" round class="touch-btn" @click="$router.push('/')">
          再分析一段
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { copyText, getAnalysis } from '../api/client'
import { DISCLAIMER, FindingSeverity } from '../api/generated-types'
import EvidenceQuestionPanel from '../components/EvidenceQuestionPanel.vue'
import ScenarioCalculator from '../components/ScenarioCalculator.vue'
import { useTaskStore } from '../stores/task'

const props = defineProps({
  taskId: { type: String, required: true },
})

const router = useRouter()
const store = useTaskStore()
const loading = ref(true)
const loadError = ref('')
const report = ref(null)
const activeFindings = ref([])
const sourceExpanded = ref(false)
const sourceText = ref('')
let active = true

const productGradeText = computed(() => {
  const g = report.value?.product_risk_grade
  if (!g || g.status === 'not_disclosed' || !g.value) return '材料未说明'
  return g.value
})

const conclusion = computed(() => {
  const scope = report.value?.analysis_scope || 'supported'
  if (scope === 'out_of_scope') {
    return '当前 Demo 未分析该产品，请选择结构性存款或贷款'
  }
  if (scope === 'needs_confirmation') {
    return '产品类型存在冲突，请确认后重新分析'
  }
  const findings = report.value?.findings || []
  if (!findings.length) {
    return '未命中当前已配置规则，不等于产品没有风险'
  }
  return `共发现 ${findings.length} 条风险，请展开查看原文证据。`
})

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
  if (p.key === 'amount' && p.amount != null) return String(p.amount)
  return p.value ?? '-'
}

function findingTitle(f) {
  const sev = f.finding_severity
  const label =
    sev === FindingSeverity.high
      ? '高'
      : sev === FindingSeverity.mid
        ? '中'
        : sev === FindingSeverity.low
          ? '低'
          : sev
  return `${f.title || '发现'}（严重度:${label}）`
}

async function onCopy(text) {
  const ok = await copyText(text)
  showToast(ok ? '已复制' : '复制失败')
}

onMounted(async () => {
  active = true
  store.restoreFromStorage()
  // 故意不使用 Pinia 草稿冒充本任务原文
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
    sourceText.value = data.source_text || ''
  } catch (e) {
    if (!active) return
    const code = e?.response?.data?.detail?.error_code || ''
    const msg = e?.response?.data?.detail?.message || e.message || '加载报告失败'
    if (code === 'TASK_NOT_FOUND' || e?.response?.status === 404) {
      loadError.value = '任务可能因服务重启而丢失'
    } else {
      loadError.value = msg
    }
  } finally {
    if (active) loading.value = false
  }
})

onUnmounted(() => {
  active = false
})
</script>

<style scoped>
h3 {
  margin: 0 0 10px;
  font-size: 16px;
}
.conclusion {
  margin: 0 0 10px;
  font-size: 16px;
  line-height: 1.6;
  font-weight: 600;
}
.meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: #6b7280;
}
.sep {
  margin: 0 4px;
}
.disclaimer {
  margin: 12px;
  color: #9ca3af;
  font-size: 12px;
  line-height: 1.5;
}
.finding-explain {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.5;
  color: #374151;
  white-space: pre-wrap;
}
.evidence {
  margin-top: 8px;
  padding: 10px;
  background: #f3f4f6;
  border-radius: 8px;
}
.evidence-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.evidence blockquote {
  margin: 0 0 8px;
  font-size: 14px;
  line-height: 1.5;
  color: #111827;
  white-space: pre-wrap;
}
.evidence-meta {
  margin: 0 0 8px;
  font-size: 12px;
  color: #9ca3af;
}
.row-between {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.source {
  margin: 0 0 10px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.source.clamped {
  display: -webkit-box;
  -webkit-line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.touch-btn {
  min-height: 44px;
}
</style>
