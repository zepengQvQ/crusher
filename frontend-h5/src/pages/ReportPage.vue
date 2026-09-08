<template>
  <div class="page">
    <van-nav-bar title="分析报告" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar
      left-icon="info-o"
      :text="DISCLAIMER"
    />
    <div v-if="loading" class="block">
      <van-skeleton title :row="6" />
    </div>
    <template v-else-if="report">
      <div class="block">
        <h3>通俗解释</h3>
        <p>{{ report.plain_language?.text || '暂无通俗解释' }}</p>
        <van-tag type="primary">{{ productName }}</van-tag>
        <p class="meta">
          产品风险评级：{{ productGradeText }}
          <span class="sep">｜</span>
          字段来源：{{ report.product_risk_grade?.status || '-' }}
        </p>
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
            </div>
          </van-collapse-item>
        </van-collapse>
      </div>
      <div class="block">
        <h3>缺失披露 / 待确认</h3>
        <van-cell
          v-for="(m, idx) in report.missing_disclosures || []"
          :key="'m' + idx"
          :title="m.question || m.key"
        />
        <van-cell
          v-for="(q, idx) in report.pending_questions || []"
          :key="'q' + idx"
          :title="q"
        />
      </div>
      <p class="disclaimer">{{ report.disclaimer || DISCLAIMER }}</p>
    </template>
    <div v-else class="block">
      <van-empty description="报告不存在" />
      <van-button block type="primary" @click="$router.push('/')">返回重试</van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAnalysis } from '../api/client'
import { DISCLAIMER, FindingSeverity } from '../api/generated-types'
import { useTaskStore } from '../stores/task'

const props = defineProps({
  taskId: { type: String, required: true },
})

const router = useRouter()
const store = useTaskStore()
const loading = ref(true)
const report = ref(null)
const activeFindings = ref([])

const productName = computed(
  () => report.value?.product_candidates?.[0]?.product_type_name || '未知产品',
)

const productGradeText = computed(() => {
  const g = report.value?.product_risk_grade
  if (!g || g.status === 'not_disclosed' || !g.value) return '未披露'
  return g.value
})

function formatParam(p) {
  if (p.status === 'not_disclosed') return '材料未说明'
  if (p.key === 'amount' && p.amount != null) return String(p.amount)
  return p.value ?? '-'
}

function findingTitle(f) {
  const sev = f.finding_severity
  const label =
    sev === FindingSeverity.high ? '高' : sev === FindingSeverity.mid ? '中' : sev === FindingSeverity.low ? '低' : sev
  return `${f.title || '发现'}（严重度:${label}）`
}

onMounted(async () => {
  try {
    const data = await getAnalysis(props.taskId)
    if (data.task_status === 'failed' || data.is_failure) {
      store.setError(data.error_message || '模型调用失败', data.error_code || '')
      router.replace({ name: 'error' })
      return
    }
    report.value = data.report
  } catch (e) {
    store.setError(e?.response?.data?.detail?.message || e.message || '加载报告失败')
    router.replace({ name: 'error' })
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
h3 {
  margin: 0 0 10px;
  font-size: 16px;
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
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  color: #111827;
}
.evidence-meta {
  margin: 6px 0 0;
  font-size: 12px;
  color: #9ca3af;
}
</style>
