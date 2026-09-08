<template>
  <div class="page">
    <van-nav-bar title="出错了" left-arrow @click-left="$router.push('/')" />
    <div class="block">
      <van-empty image="error" :description="message" />
      <p v-if="code" class="code">错误码：{{ code }}</p>
      <p class="hint">这不是「没发现风险」。下方已保留输入，可直接重新分析。</p>

      <div v-if="draftText" class="draft">
        <div class="draft-title">保留输入</div>
        <p class="draft-text">{{ draftText }}</p>
      </div>

      <van-button block type="primary" round class="touch-btn" @click="retryWithDraft">
        重新分析
      </van-button>
      <van-button block round plain class="touch-btn" style="margin-top: 10px" @click="$router.push('/')">
        返回首页
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAnalysis, pickErrorMessage } from '../api/client'
import { useTaskStore } from '../stores/task'

const router = useRouter()
const store = useTaskStore()
const draftText = ref('')
const productHint = ref('auto')
const retrying = ref(false)

const message = computed(() => {
  const raw = store.lastError || '请求失败，请重试'
  if (raw.includes('未发现风险') || raw.includes('没有风险')) {
    return '模型调用失败'
  }
  return raw
})
const code = computed(() => store.lastErrorCode || '')

onMounted(() => {
  store.restoreFromStorage()
  draftText.value = store.draftText || ''
  productHint.value = store.productHint || 'auto'
})

async function retryWithDraft() {
  const value = (draftText.value || '').trim()
  if (!value) {
    router.push('/')
    return
  }
  retrying.value = true
  store.setDraft(value, productHint.value)
  try {
    const res = await createAnalysis(value, { productHint: productHint.value })
    store.setTask(res.task_id, res.task_status)
    router.replace({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    store.setError(pickErrorMessage(e), e?.response?.data?.detail?.error_code || '')
    showToast(store.lastError)
  } finally {
    retrying.value = false
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
.draft {
  margin: 0 0 16px;
  padding: 12px;
  background: #f3f4f6;
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
