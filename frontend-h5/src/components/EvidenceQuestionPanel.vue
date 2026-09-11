<template>
  <div class="panel">
    <div class="head">
      <div class="title">还可以追问</div>
      <div class="meta">本页最多 {{ MAX_ASKS }} 次 · 已用 {{ asks }}/{{ MAX_ASKS }}</div>
    </div>

    <div v-if="pending.length" class="chips">
      <button
        v-for="(q, i) in pending"
        :key="'p' + i"
        type="button"
        class="chip"
        :disabled="loading || asks >= MAX_ASKS"
        @click="ask(q)"
      >
        {{ q }}
      </button>
    </div>
    <p v-else class="soft">点选上方待确认问题，或自己输入。</p>

    <div class="composer">
      <input
        v-model="question"
        class="composer-input"
        type="text"
        maxlength="200"
        placeholder="围绕当前材料提问…"
        :disabled="loading || asks >= MAX_ASKS"
        @keyup.enter="ask(question)"
      />
      <button
        type="button"
        class="ask-btn"
        :disabled="loading || asks >= MAX_ASKS || !question.trim()"
        @click="ask(question)"
      >
        <van-loading v-if="loading" size="16" color="#fff" />
        <span v-else>提问</span>
      </button>
    </div>

    <div v-for="(a, i) in answers" :key="'a' + i" class="answer">
      <div class="q">{{ a.question }}</div>
      <div class="s">{{ statusLabel(a.status) }}</div>
      <p class="body">{{ a.answer }}</p>
      <p v-for="(e, j) in a.evidence || []" :key="j" class="ev">原文：{{ e.quote }}</p>
      <p v-for="(m, j) in a.missing_info || []" :key="'m' + j" class="miss">缺：{{ m }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { createFollowUp, pickErrorMessage } from '../api/client'

const MAX_ASKS = 5

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
  if (s === 'contextual') return '结合材料说明'
  return s
}

async function ask(q) {
  const text = String(q || '').trim()
  if (!text) {
    showToast('请输入问题')
    return
  }
  if (asks.value >= MAX_ASKS) {
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
  margin: 4px 0 12px;
}
.head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.title {
  font-size: 15px;
  font-weight: 600;
  color: var(--crusher-ink);
}
.meta {
  font-size: 12px;
  color: var(--crusher-ink-3, #94a3b8);
  flex-shrink: 0;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 10px;
}
.chip {
  appearance: none;
  border: 1px solid var(--crusher-border);
  background: var(--crusher-card-bg, #fff);
  color: var(--crusher-ink-2);
  font-size: 12px;
  line-height: 1.35;
  text-align: left;
  padding: 8px 12px;
  border-radius: 999px;
  max-width: 100%;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.chip:active:not(:disabled) {
  background: var(--crusher-primary-light);
  border-color: var(--crusher-primary);
  color: var(--crusher-primary);
}
.chip:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.soft {
  margin: 0 0 10px;
  font-size: 12px;
  color: var(--crusher-ink-3);
}
.composer {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 6px 6px 14px;
  background: var(--crusher-bg-gray, #f5f6f8);
  border-radius: 999px;
}
.composer-input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: none;
  background: transparent;
  font: inherit;
  font-size: 14px;
  color: var(--crusher-ink);
  min-height: 36px;
}
.composer-input::placeholder {
  color: #9ca3af;
}
.ask-btn {
  appearance: none;
  border: none;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  min-width: 64px;
  padding: 0 14px;
  border-radius: 999px;
  background: var(--crusher-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}
.ask-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.answer {
  margin-top: 12px;
  padding: 12px;
  background: var(--crusher-card-bg, #fff);
  border-radius: 12px;
  border: 1px solid var(--crusher-border);
  font-size: 13px;
}
.q {
  font-weight: 600;
  color: var(--crusher-ink);
}
.s {
  color: #64748b;
  margin: 4px 0 6px;
  font-size: 12px;
}
.body {
  margin: 0;
  line-height: 1.55;
  color: var(--crusher-ink-2);
  white-space: pre-wrap;
}
.ev {
  margin: 8px 0 0;
  background: var(--crusher-bg-gray, #f5f6f8);
  padding: 8px 10px;
  border-radius: 8px;
  line-height: 1.45;
}
.miss {
  margin: 6px 0 0;
  color: #9a3412;
}
</style>
