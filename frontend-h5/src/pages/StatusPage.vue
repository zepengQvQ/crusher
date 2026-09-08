<template>
  <div class="page">
    <van-nav-bar title="分析中" left-arrow @click-left="$router.push('/')" />
    <div class="block">
      <p class="meta">任务编号：{{ taskId }}</p>
      <p class="meta">任务状态：{{ statusLabel }}</p>
      <van-skeleton title :row="3" :loading="!stages.length" />
      <van-cell-group v-if="stages.length" inset>
        <van-cell
          v-for="s in stages"
          :key="s.name"
          :title="stageTitle(s.name)"
          :label="s.message"
          :value="stageStatusText(s.status)"
        />
      </van-cell-group>
      <van-button
        v-if="failed"
        block
        type="danger"
        round
        style="margin-top: 16px"
        @click="goError"
      >
        查看失败原因
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
let timer = null

const failed = computed(() => taskStatus.value === 'failed')
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

function goError() {
  store.setError(errorMessage.value || '分析失败', errorCode.value)
  router.replace({ name: 'error' })
}

async function poll() {
  try {
    const data = await getAnalysis(props.taskId)
    taskStatus.value = data.task_status
    stages.value = data.stages || []
    store.setTask(props.taskId, data.task_status, data.stages || [])

    if (data.task_status === 'completed') {
      clearInterval(timer)
      // 失败标志时绝不进报告页
      if (data.is_failure) {
        errorMessage.value = data.error_message || '分析失败'
        errorCode.value = data.error_code || ''
        goError()
        return
      }
      router.replace({ name: 'report', params: { taskId: props.taskId } })
    } else if (data.task_status === 'failed') {
      clearInterval(timer)
      errorMessage.value = data.error_message || '分析失败'
      errorCode.value = data.error_code || ''
      goError()
    }
  } catch (e) {
    clearInterval(timer)
    const msg = pickErrorMessage(e)
    const code = e?.response?.data?.detail?.error_code || ''
    store.setError(msg, code)
    router.replace({ name: 'error' })
  }
}

onMounted(() => {
  store.setTask(props.taskId, 'queued')
  poll()
  timer = setInterval(poll, 800)
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.meta {
  margin: 0 0 8px;
  font-size: 13px;
  color: #6b7280;
}
</style>
