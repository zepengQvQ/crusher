<template>
  <div class="page">
    <van-nav-bar title="出错了" left-arrow @click-left="$router.push('/')" />
    <div class="block">
      <van-empty image="error" :description="message" />
      <p v-if="code" class="code">错误码：{{ code }}</p>
      <p class="hint">{{ retainHint }}</p>

      <ul v-if="nextSteps.length" class="next-steps">
        <li v-for="(s, i) in nextSteps" :key="'ns' + i">{{ s }}</li>
      </ul>

      <div v-if="draftText" class="draft">
        <div class="draft-title">保留输入</div>
        <p class="draft-text">{{ draftText }}</p>
      </div>
      <van-empty v-else description="暂无可恢复的原文，请返回首页重新粘贴" />

      <van-button
        block
        type="primary"
        round
        class="touch-btn"
        :loading="retrying"
        :disabled="!draftText"
        @click="retryWithDraft"
      >
        重新分析
      </van-button>
      <van-button block round plain class="touch-btn" style="margin-top: 10px" @click="$router.push('/')">
        返回首页
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAnalysis, getAnalysis, pickErrorMessage } from '../api/client'
import { useTaskStore } from '../stores/task'

const props = defineProps({
  taskId: { type: String, default: '' },
})

const router = useRouter()
const store = useTaskStore()
const draftText = ref('')
const productHint = ref('auto')
const retrying = ref(false)
const nextSteps = ref([])
let active = true

const message = computed(() => {
  const raw = store.lastError || '请求失败，请重试'
  if (raw.includes('未发现风险') || raw.includes('没有风险')) {
    return '模型调用失败'
  }
  return raw
})
const code = computed(() => store.lastErrorCode || '')
const retainHint = computed(() =>
  draftText.value
    ? '这不是「没发现风险」。下方已保留本任务输入，可直接重新分析。'
    : '这不是「没发现风险」。暂无可恢复原文，请返回首页重新粘贴。',
)

onMounted(async () => {
  active = true
  store.restoreFromStorage()
  if (props.taskId) {
    // 有 taskId：原文与 product_hint 均只取该任务 GET，禁止回退全局草稿/hint
    try {
      const data = await getAnalysis(props.taskId)
      if (!active) return
      draftText.value = data.source_text || ''
      productHint.value = data.product_hint || 'auto'
      nextSteps.value = data.publication?.next_steps || []
      if (data.error_message) {
        store.setError(data.error_message, data.error_code || '')
      }
      if (data.publication?.user_reason && !data.error_message) {
        store.setError(data.publication.user_reason, data.publication.reason_code || '')
      }
    } catch (e) {
      if (!active) return
      const detail = e?.response?.data?.detail
      if (detail?.error_code === 'TASK_NOT_FOUND' || e?.response?.status === 404) {
        store.setError('任务可能因服务重启而丢失', 'TASK_NOT_FOUND')
      } else {
        store.setError(pickErrorMessage(e), detail?.error_code || '')
      }
      draftText.value = ''
    }
    return
  }
  // 无 taskId：仅限 POST 尚未建任务的网络错误，用 Pinia 内存草稿
  draftText.value = store.draftText || ''
  productHint.value = store.productHint || 'auto'
})

onUnmounted(() => {
  active = false
})

async function retryWithDraft() {
  const value = (draftText.value || '').trim()
  if (!value) {
    router.push('/')
    return
  }
  retrying.value = true
  const hint = productHint.value || 'auto'
  store.setDraft(value, hint)
  try {
    const res = await createAnalysis(value, { productHint: hint })
    if (!active) return
    store.setTask(res.task_id, res.task_status)
    router.replace({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    if (!active) return
    store.setError(pickErrorMessage(e), e?.response?.data?.detail?.error_code || '')
    showToast(store.lastError)
  } finally {
    if (active) retrying.value = false
  }
}
</script>

<style scoped>
.code {
  text-align: center;
  color: #6b7280;
  font-size: 12px;
}
.hint {
  text-align: center;
  color: #9ca3af;
  font-size: 12px;
  margin: 8px 12px 16px;
}
.next-steps {
  margin: 0 16px 16px;
  padding-left: 1.2em;
  font-size: 13px;
  color: #4b5563;
  line-height: 1.5;
}
.draft {
  margin: 0 0 16px;
  padding: 12px;
  background: var(--crusher-bg-gray);
  border-radius: 8px;
}
.draft-title {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}
.draft-text {
  margin: 0;
  font-size: 14px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 160px;
  overflow: auto;
}
.touch-btn {
  min-height: 44px;
}
</style>
