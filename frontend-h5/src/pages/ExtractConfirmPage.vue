<template>
  <div class="page">
    <van-nav-bar title="确认提取文字" left-arrow @click-left="$router.back()" />
    <div class="block">
      <van-notice-bar
        left-icon="info-o"
        text="请核对并修正后再分析。空识别不能当作「无风险」。"
      />
      <p v-if="hints.length" class="hints-title">需人工确认</p>
      <van-tag v-for="(h, i) in hints" :key="i" type="warning" plain class="hint-tag">{{ h }}</van-tag>
      <van-field
        v-model="text"
        rows="12"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        placeholder="提取文本为空，请改用粘贴输入"
        class="touch-field"
      />
      <van-button
        block
        round
        type="primary"
        class="touch-btn"
        :disabled="!text.trim()"
        @click="confirmToAnalyze"
      >
        确认并开始分析
      </van-button>
      <van-button block round plain class="touch-btn" style="margin-top: 8px" @click="$router.push('/')">
        返回纯文本输入
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAnalysis, pickErrorMessage } from '../api/client'
import { MAX_INPUT_CHARS } from '../api/generated-types'
import { useTaskStore } from '../stores/task'

const EXTRACT_KEY = 'crusher_extracted_doc'
const router = useRouter()
const store = useTaskStore()
const text = ref('')
const hints = ref([])
const loading = ref(false)

onMounted(() => {
  try {
    const raw = sessionStorage.getItem(EXTRACT_KEY)
    if (!raw) return
    const doc = JSON.parse(raw)
    text.value = doc.combined_text || ''
    hints.value = doc.sensitive_hints || []
  } catch {
    /* ignore */
  }
})

async function confirmToAnalyze() {
  const value = text.value.trim()
  if (!value) {
    showToast('请先确认非空文本')
    return
  }
  loading.value = true
  store.setDraft(value, 'auto')
  try {
    const res = await createAnalysis(value, { productHint: 'auto' })
    store.setTask(res.task_id, res.task_status)
    sessionStorage.removeItem(EXTRACT_KEY)
    router.replace({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.block {
  padding: 12px 16px 24px;
}
.hints-title {
  margin: 10px 0 6px;
  font-size: 13px;
  font-weight: 600;
}
.hint-tag {
  margin: 0 6px 6px 0;
}
.touch-btn {
  min-height: 44px;
  margin-top: 12px;
}
</style>
