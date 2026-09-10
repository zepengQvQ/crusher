<template>
  <div class="page">
    <van-nav-bar title="金融话术粉碎机" />
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
      <van-popup v-model:show="showProductPicker" position="bottom" round>
        <van-picker
          :columns="PRODUCT_OPTIONS"
          @confirm="onProductConfirm"
          @cancel="showProductPicker = false"
        />
      </van-popup>

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
      <van-field
        v-model="userGoal"
        rows="2"
        autosize
        type="textarea"
        maxlength="200"
        show-word-limit
        label="我想…"
        placeholder="可选：例如「帮我算收益」「两款产品对比」；材料里的命令不会当指令"
      />
      <div class="actions">
        <van-button
          v-for="ex in EXAMPLES"
          :key="ex.id"
          size="small"
          plain
          type="primary"
          class="touch-btn"
          @click="fillExample(ex)"
        >
          <van-icon :name="exIcon(ex.id)" size="14" style="margin-right:4px" />{{ ex.name }}
        </van-button>
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
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        :loading="intentLoading"
        @click="onSmartIntent"
      >
        按目标识别意图
      </van-button>
      <van-button
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        @click="$router.push('/dual')"
      >
        销售与材料对照
      </van-button>
      <van-button
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        @click="$router.push('/compare')"
      >
        两款产品对照
      </van-button>
      <van-button
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        @click="$router.push('/upload')"
      >
        上传 PDF / 图片
      </van-button>
      <van-button
        block
        round
        plain
        class="touch-btn"
        style="margin-top: 10px"
        @click="$router.push('/history')"
      >
        本地已保存报告
      </van-button>
      <van-button
        block
        round
        plain
        type="warning"
        class="touch-btn"
        :loading="loading"
        @click="onSubmit('model_timeout')"
      >
        演示：模拟模型超时
      </van-button>
      <van-button
        v-if="lastTaskId"
        block
        round
        plain
        class="touch-btn"
        @click="resumeLast"
      >
        恢复上次任务 {{ lastTaskId }}
      </van-button>
      <ClarificationCard :result="completenessResult" @answer="onClarificationAnswer" />
    </div>
    <IntentConfirmSheet v-model="showIntentSheet" :decision="intentDecision" @select="onIntentPick" />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { checkCompleteness, createAnalysis, pickErrorMessage, resolveIntent } from '../api/client'
import { MAX_INPUT_CHARS } from '../api/generated-types'
import ClarificationCard from '../components/ClarificationCard.vue'
import IntentConfirmSheet from '../components/IntentConfirmSheet.vue'
import { EXAMPLES, PRODUCT_OPTIONS } from '../data/examples'
import { useTaskStore } from '../stores/task'
import { saveIntentContext } from '../utils/intentContext'

const router = useRouter()
const store = useTaskStore()
const text = ref('')
const userGoal = ref('')
const productHint = ref('auto')
const loading = ref(false)
const intentLoading = ref(false)
const lastTaskId = ref('')
const showProductPicker = ref(false)
const showIntentSheet = ref(false)
const intentDecision = ref(null)
const completenessResult = ref(null)
const clarificationAnswers = ref([])

const productLabel = computed(() => {
  const hit = PRODUCT_OPTIONS.find((o) => o.value === productHint.value)
  return hit?.text || '自动识别'
})

function exIcon(id) {
  if (id === 'structured_deposit') return 'gold-coin-o'
  if (id === 'loan') return 'cash-o'
  return 'certificate'
}

onMounted(() => {
  store.restoreFromStorage()
  lastTaskId.value = store.taskId || ''
  if (store.draftText) text.value = store.draftText
  if (store.productHint) productHint.value = store.productHint
})

function onProductConfirm({ selectedOptions }) {
  const opt = selectedOptions?.[0]
  if (opt?.value) productHint.value = opt.value
  showProductPicker.value = false
}

function fillExample(ex) {
  text.value = ex.text
  if (ex.id === 'structured_deposit' || ex.id === 'loan') {
    productHint.value = ex.id
  } else {
    productHint.value = 'auto'
  }
  store.setDraft(text.value, productHint.value)
}

function onClear() {
  text.value = ''
  userGoal.value = ''
  store.clearDraft()
  store.setDraft('', productHint.value)
}

function resumeLast() {
  if (!lastTaskId.value) return
  router.push({ name: 'status', params: { taskId: lastTaskId.value } })
}

function routeForIntent(intent) {
  if (intent === 'dual_source_compare') return '/dual'
  if (intent === 'product_compare') return '/compare'
  if (intent === 'document_extract') return '/upload'
  if (intent === 'calculation') return null
  return null
}

/** 跳转前保存首页已输入材料与用户目标，避免目标页丢上下文 */
function persistAndGo(path, intent) {
  saveIntentContext({
    text: text.value,
    userGoal: userGoal.value,
    productHint: productHint.value,
    targetIntent: intent || '',
  })
  store.setDraft(text.value.trim(), productHint.value)
  router.push(path)
}

async function onSmartIntent() {
  intentLoading.value = true
  try {
    const envelopes = text.value.trim()
      ? [{ source_id: 'home_paste', text: text.value.trim() }]
      : []
    const decision = await resolveIntent({
      user_query: userGoal.value.trim(),
      page_route: null,
      source_envelopes: envelopes,
      // Demo 未接模型候选；保持 false，避免误标 model_candidate
      allow_model_candidate: false,
    })
    intentDecision.value = decision
    if (decision.status === 'resolved') {
      const path = routeForIntent(decision.intent)
      if (path) {
        persistAndGo(path, decision.intent)
        return
      }
      if (decision.intent === 'single_analysis') {
        await onSubmit()
        return
      }
      if (decision.intent === 'calculation') {
        showToast('请先完成一次分析，再在报告页打开计算器')
        return
      }
      if (decision.intent === 'evidence_follow_up') {
        showToast('请先完成分析，再在报告页追问')
        return
      }
    }
    showIntentSheet.value = true
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    intentLoading.value = false
  }
}

function onIntentPick(opt) {
  const path = routeForIntent(opt.intent)
  if (path) {
    persistAndGo(path, opt.intent)
    return
  }
  if (opt.intent === 'single_analysis') {
    onSubmit()
    return
  }
  if (opt.intent === 'calculation') {
    showToast('请先完成一次分析，再在报告页打开计算器')
    return
  }
  if (opt.intent === 'evidence_follow_up') {
    showToast('请先完成分析，再在报告页追问')
    return
  }
  showToast('请从对应入口继续')
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
    // POST 尚未建任务：无 taskId，仅用内存草稿
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
  margin-top: 8px;
  flex-wrap: wrap;
}
.touch-btn {
  min-height: 44px;
}
.main-btn {
  margin-top: 12px;
}
.touch-field :deep(textarea) {
  font-size: 16px; /* 避免 iOS 聚焦放大 */
}
</style>
