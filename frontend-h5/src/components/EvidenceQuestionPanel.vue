<template>
  <div class="panel">
    <div class="title">待确认 / 追问（本页最多 5 次）</div>
    <van-cell
      v-for="(q, i) in pending"
      :key="'p' + i"
      :title="q"
      is-link
      @click="ask(q)"
    />
    <van-field
      v-model="question"
      rows="2"
      autosize
      type="textarea"
      maxlength="200"
      placeholder="围绕当前材料提问…"
    />
    <van-button
      size="small"
      type="primary"
      class="touch-btn"
      :loading="loading"
      :disabled="asks >= 5"
      @click="ask(question)"
    >
      提问
    </van-button>
    <div v-for="(a, i) in answers" :key="'a' + i" class="answer">
      <div class="q">Q: {{ a.question }}</div>
      <div class="s">{{ statusLabel(a.status) }}</div>
      <p>{{ a.answer }}</p>
      <p v-for="(e, j) in a.evidence || []" :key="j" class="ev">原文：{{ e.quote }}</p>
      <p v-for="(m, j) in a.missing_info || []" :key="'m' + j" class="miss">缺：{{ m }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { createFollowUp, pickErrorMessage } from '../api/client'

const props = defineProps({
  sourceText: { type: String, required: true },
  pending: { type: Array, default: () => [] },
})

const question = ref('')
const loading = ref(false)
const asks = ref(0)
const answers = ref([])

function statusLabel(s) {
  if (s === 'answered') return '已回答'
  if (s === 'insufficient_evidence') return '证据不足'
  if (s === 'out_of_scope') return '超范围'
  return s
}

async function ask(q) {
  const text = String(q || '').trim()
  if (!text) {
    showToast('请输入问题')
    return
  }
  if (asks.value >= 5) {
    showToast('本页追问次数已达上限')
    return
  }
  loading.value = true
  try {
    const ans = await createFollowUp(text, props.sourceText, props.pending)
    answers.value = [ans, ...answers.value]
    asks.value += 1
    question.value = ''
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.panel {
  margin: 12px 0;
  padding: 12px;
  background: var(--crusher-surface);
  border-radius: 10px;
}
.title {
  font-weight: 600;
  margin-bottom: 8px;
}
.touch-btn {
  min-height: 40px;
  margin-top: 8px;
}
.answer {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--crusher-border);
  font-size: 13px;
}
.q {
  font-weight: 600;
}
.s {
  color: #64748b;
  margin: 4px 0;
}
.ev {
  background: var(--crusher-card-bg);
  padding: 6px;
  border-radius: 6px;
}
.miss {
  color: #9a3412;
}
</style>
