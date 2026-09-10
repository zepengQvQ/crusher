<template>
  <div v-if="result && !result.can_continue" class="card">
    <div class="title">还需要确认</div>
    <p class="summary">{{ result.summary }}</p>
    <div v-for="q in result.questions" :key="q.question_id" class="q">
      <div class="prompt">{{ q.prompt }}</div>
      <div v-if="q.control === 'buttons' || q.control === 'enum'" class="opts">
        <van-button
          v-for="opt in q.options"
          :key="opt.value"
          size="small"
          plain
          type="primary"
          class="touch-btn"
          @click="answer(q.question_id, opt.value)"
        >
          {{ opt.label }}
        </van-button>
      </div>
      <van-field
        v-else
        v-model="textAnswers[q.question_id]"
        rows="2"
        autosize
        type="textarea"
        placeholder="请填写后点确认"
      />
      <van-button
        v-if="q.control === 'free_text'"
        size="small"
        type="primary"
        class="touch-btn"
        @click="answer(q.question_id, textAnswers[q.question_id])"
      >
        确认
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { reactive, watch } from 'vue'

const props = defineProps({
  result: { type: Object, default: null },
})

const emit = defineEmits(['answer'])

const textAnswers = reactive({})

watch(
  () => props.result,
  (r) => {
    for (const key of Object.keys(textAnswers)) delete textAnswers[key]
    for (const q of r?.questions || []) {
      if (q.control === 'free_text') textAnswers[q.question_id] = ''
    }
  },
  { immediate: true },
)

function answer(questionId, value) {
  const v = String(value || '').trim()
  if (!v) return
  emit('answer', { question_id: questionId, value: v })
}
</script>

<style scoped>
.card {
  margin-top: 12px;
  padding: 12px;
  background: var(--crusher-warning-light);
  border-radius: 10px;
}
.title {
  font-weight: 600;
  margin-bottom: 6px;
}
.summary {
  margin: 0 0 10px;
  font-size: 13px;
  color: #9a3412;
}
.q {
  margin-bottom: 12px;
}
.prompt {
  font-size: 14px;
  margin-bottom: 8px;
}
.opts {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.touch-btn {
  min-height: 44px;
}
</style>
