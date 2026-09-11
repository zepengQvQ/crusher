<template>
  <div class="page">
    <van-nav-bar title="金融话术粉碎机" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar
      left-icon="info-o"
      text="密钥只在本机 .env；网页不能填 Key。重启服务后旧任务会丢失。"
    />
    <div class="block">
      <van-field
        is-link
        readonly
        name="product"
        label="产品类型"
        :model-value="productLabel"
        placeholder="选择产品类型"
        @click="showProductPicker = true"
      />
      <van-action-sheet
        v-model:show="showProductPicker"
        :actions="productActions"
        cancel-text="取消"
        close-on-click-action
        @select="onProductSelect"
      />

      <van-field
        v-model="text"
        rows="8"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        placeholder="粘贴结构性存款或借贷相关条款…"
        class="touch-field"
      />
      <div class="actions">
        <van-button size="small" plain class="touch-btn" @click="onClear">
          <van-icon name="delete-o" size="14" style="margin-right:4px" />清空
        </van-button>
      </div>
      <van-button
        type="primary"
        block
        round
        class="touch-btn main-btn"
        :loading="loading"
        @click="onSubmit()"
      >
        <template #icon v-if="!loading"><van-icon name="fire-o" /></template>
        开始分析
      </van-button>
      <van-button
        v-if="lastTaskId"
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 8px"
        @click="resumeLast"
      >
        恢复上次任务 {{ lastTaskId }}
      </van-button>
      <ClarificationCard :result="completenessResult" @answer="onClarificationAnswer" />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { checkCompleteness, createAnalysis, pickErrorMessage } from '../api/client'
import { MAX_INPUT_CHARS } from '../api/generated-types'
import ClarificationCard from '../components/ClarificationCard.vue'
import { PRODUCT_OPTIONS } from '../data/examples'
import { useTaskStore } from '../stores/task'
import { loadIntentContext } from '../utils/intentContext'

const router = useRouter()
const store = useTaskStore()
const text = ref('')
const productHint = ref('auto')
const loading = ref(false)
const lastTaskId = ref('')
const showProductPicker = ref(false)
const completenessResult = ref(null)
const clarificationAnswers = ref([])

const productLabel = computed(() => {
  const hit = PRODUCT_OPTIONS.find((o) => o.value === productHint.value)
  return hit?.text || '自动识别'
})

const productActions = computed(() =>
  PRODUCT_OPTIONS.map((o) => ({
    name: o.text,
    value: o.value,
    color: o.value === productHint.value ? 'var(--crusher-primary)' : undefined,
  })),
)

function onProductSelect(action) {
  if (action?.value) productHint.value = action.value
  showProductPicker.value = false
}

onMounted(() => {
  store.restoreFromStorage()
  lastTaskId.value = store.taskId || ''
  if (store.draftText) text.value = store.draftText
  if (store.productHint) productHint.value = store.productHint
  const intentCtx = loadIntentContext()
  if (intentCtx?.text && !text.value.trim()) {
    text.value = intentCtx.text
  }
  if (intentCtx?.productHint && intentCtx.productHint !== 'auto') {
    productHint.value = intentCtx.productHint
  }
})

function onClear() {
  text.value = ''
  store.clearDraft()
  store.setDraft('', productHint.value)
}

function resumeLast() {
  if (!lastTaskId.value) return
  router.push({ name: 'status', params: { taskId: lastTaskId.value } })
}

async function onClarificationAnswer({ question_id, value }) {
  const next = [
    ...clarificationAnswers.value.filter((a) => a.question_id !== question_id),
    { question_id, value },
  ]
  clarificationAnswers.value = next
  if (question_id === 'product_type_confirm' && (value === 'loan' || value === 'structured_deposit')) {
    productHint.value = value
  }
  await runCompletenessGate()
  if (completenessResult.value?.can_continue) {
    completenessResult.value = null
    await onSubmit()
  }
}

async function runCompletenessGate() {
  const value = text.value.trim()
  const result = await checkCompleteness({
    intent: 'single_analysis',
    product_hint: productHint.value,
    source_envelopes: value ? [{ source_id: 'home_paste', text: value }] : [],
    clarification_answers: clarificationAnswers.value,
  })
  completenessResult.value = result
  return result
}

async function onSubmit(demoError) {
  const value = text.value.trim()
  if (!value) {
    showToast('请先粘贴条款文本')
    return
  }
  store.setDraft(value, productHint.value)
  loading.value = true
  try {
    if (!demoError) {
      const gate = await runCompletenessGate()
      if (!gate.can_continue) {
        showToast(gate.summary || '请先确认问题')
        return
      }
    }
    completenessResult.value = null
    const res = await createAnalysis(value, {
      demoError,
      productHint: productHint.value,
    })
    store.setTask(res.task_id, res.task_status)
    lastTaskId.value = res.task_id
    clarificationAnswers.value = []
    router.push({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    const msg = pickErrorMessage(e)
    const code = e?.response?.data?.detail?.error_code || ''
    store.setError(msg, code)
    router.push({ name: 'error' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.actions {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  flex-wrap: wrap;
}
.touch-btn {
  min-height: 44px;
}
.main-btn {
  margin-top: 10px;
}
.touch-field :deep(textarea) {
  font-size: 16px; /* 避免 iOS 聚焦放大 */
}
</style>
