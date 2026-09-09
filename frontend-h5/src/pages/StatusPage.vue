<template>
  <div class="page">
    <van-nav-bar title="分析中" left-arrow @click-left="goHome" />
    <div class="block">
      <p class="meta">任务编号：{{ taskId }}</p>
      <p class="meta">任务状态：{{ statusLabel }}</p>
      <p class="meta">已用时：{{ elapsedLabel }}</p>
      <van-notice-bar
        v-if="slow"
        left-icon="clock-o"
        text="慢请求：分析仍在进行，请稍候…"
      />
      <van-skeleton title :row="3" :loading="!stages.length && !failed && !needManualPoll" />
      <van-cell-group v-if="stages.length" inset>
        <van-cell
          v-for="s in stages"
          :key="s.name"
          :title="stageTitle(s.name)"
          :label="s.message"
          :value="stageStatusText(s.status)"
        />
      </van-cell-group>
      <van-empty
        v-if="needManualPoll"
        :description="offlineHint"
      />
      <van-button
        v-if="failed"
        block
        type="danger"
        round
        class="touch-btn"
        style="margin-top: 16px"
        @click="goError"
      >
        查看失败原因
      </van-button>
      <van-button
        v-if="needManualPoll"
        block
        type="primary"
        round
        class="touch-btn"
        style="margin-top: 16px"
        @click="manualRepoll"
      >
        重新查询当前任务
      </van-button>
      <van-button
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        @click="retryAnalyze"
      >
        {{ retryButtonLabel }}
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { getAnalysis, pickErrorMessage } from '../api/client'
import { useTaskStore } from '../stores/task'

const props = defineProps({
  taskId: { type: String, required: true },
})

const router = useRouter()
const store = useTaskStore()
const taskStatus = ref('queued')
const stages = ref([])
const errorMessage = ref('')
const errorCode = ref('')
const elapsed = ref(0)
const networkFails = ref(0)
const needManualPoll = ref(false)
const offlineHint = ref('网络异常，已暂停自动查询')
const recoveredSourceText = ref('')
const recoveredProductHint = ref('auto')
let pollTimer = null
let tickTimer = null
let startedAt = Date.now()
let active = true
let polling = false

const failed = computed(() => taskStatus.value === 'failed')
const slow = computed(() => elapsed.value >= 8 && taskStatus.value === 'running')
const elapsedLabel = computed(() => `${elapsed.value} 秒`)
const retryButtonLabel = computed(() =>
  recoveredSourceText.value.trim() ? '重新分析（保留输入）' : '返回重新输入',
)
const statusLabel = computed(() => {
  const map = {
    queued: '排队中',
    running: '进行中',
    completed: '已完成',
    failed: '失败',
  }
  return map[taskStatus.value] || taskStatus.value
})

function stageTitle(name) {
  const map = {
    preprocess: '预处理',
    classify: '产品识别',
    extract: '信息抽取',
    rule_review: '规则复核',
    evidence_validate: '证据校验',
    explain: '通俗解释',
  }
  return map[name] || name
}

function stageStatusText(status) {
  const map = {
    success: '成功',
    partial: '部分成功',
    failed: '失败',
    not_applicable: '未开始',
  }
  return map[status] || status
}

function goHome() {
  router.push('/')
}

function goError() {
  store.setError(errorMessage.value || '分析失败', errorCode.value)
  router.replace({ name: 'error', params: { taskId: props.taskId } })
}

function retryAnalyze() {
  if (recoveredSourceText.value.trim()) {
    store.setDraft(recoveredSourceText.value, recoveredProductHint.value || 'auto')
  }
  router.replace({ name: 'input' })
}

function applyTaskBinding(data) {
  recoveredSourceText.value = data.source_text || ''
  recoveredProductHint.value = data.product_hint || 'auto'
  if (recoveredSourceText.value.trim()) {
    store.setDraft(recoveredSourceText.value, recoveredProductHint.value)
  }
}

function clearPollTimer() {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
}

function scheduleNext(ms = 800) {
  clearPollTimer()
  if (!active) return
  pollTimer = setTimeout(() => {
    poll()
  }, ms)
}

async function poll() {
  if (!active || polling) return
  polling = true
  try {
    const data = await getAnalysis(props.taskId)
    if (!active) return
    networkFails.value = 0
    needManualPoll.value = false
    taskStatus.value = data.task_status
    stages.value = data.stages || []
    store.setTask(props.taskId, data.task_status, data.stages || [])
    applyTaskBinding(data)

    if (data.task_status === 'completed') {
      clearPollTimer()
      if (data.is_failure) {
        errorMessage.value = data.error_message || '分析失败'
        errorCode.value = data.error_code || ''
        goError()
        return
      }
      router.replace({ name: 'report', params: { taskId: props.taskId } })
      return
    }
    if (data.task_status === 'failed') {
      clearPollTimer()
      errorMessage.value = data.error_message || '分析失败'
      errorCode.value = data.error_code || ''
      goError()
      return
    }
    scheduleNext(800)
  } catch (e) {
    if (!active) return
    networkFails.value += 1
    const code = e?.response?.data?.detail?.error_code || ''
    const msg = pickErrorMessage(e)
    errorMessage.value = msg
    errorCode.value = code
    store.setError(msg, code)
    if (code === 'TASK_NOT_FOUND') {
      needManualPoll.value = true
      offlineHint.value = '任务可能因服务重启而丢失，请返回重新分析'
      clearPollTimer()
      return
    }
    if (networkFails.value >= 3) {
      needManualPoll.value = true
      offlineHint.value = '网络异常，已暂停自动查询。可点「重新查询当前任务」。'
      clearPollTimer()
      return
    }
    scheduleNext(1000)
  } finally {
    polling = false
  }
}

function manualRepoll() {
  needManualPoll.value = false
  networkFails.value = 0
  poll()
}

onMounted(() => {
  active = true
  store.restoreFromStorage()
  store.setTask(props.taskId, 'queued')
  startedAt = Date.now()
  tickTimer = setInterval(() => {
    elapsed.value = Math.floor((Date.now() - startedAt) / 1000)
  }, 500)
  poll()
})

onUnmounted(() => {
  active = false
  clearPollTimer()
  if (tickTimer) clearInterval(tickTimer)
})
</script>

<style scoped>
.meta {
  margin: 0 0 8px;
  font-size: 13px;
  color: #6b7280;
}
.touch-btn {
  min-height: 44px;
}
</style>
