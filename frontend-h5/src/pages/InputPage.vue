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
        maxlength="8000"
        show-word-limit
        placeholder="粘贴结构性存款或借贷相关条款…"
        class="touch-field"
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
          {{ ex.name }}
        </van-button>
        <van-button size="small" plain class="touch-btn" @click="text = ''">清空</van-button>
      </div>
      <van-button
        type="primary"
        block
        round
        class="touch-btn main-btn"
        :loading="loading"
        @click="onSubmit()"
      >
        开始分析
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
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAnalysis, pickErrorMessage } from '../api/client'
import { EXAMPLES, PRODUCT_OPTIONS } from '../data/examples'
import { useTaskStore } from '../stores/task'

const router = useRouter()
const store = useTaskStore()
const text = ref('')
const productHint = ref('auto')
const loading = ref(false)
const lastTaskId = ref('')
const showProductPicker = ref(false)

const productLabel = computed(() => {
  const hit = PRODUCT_OPTIONS.find((o) => o.value === productHint.value)
  return hit?.text || '自动识别'
})

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
}

function resumeLast() {
  if (!lastTaskId.value) return
  router.push({ name: 'status', params: { taskId: lastTaskId.value } })
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
    const res = await createAnalysis(value, {
      demoError,
      productHint: productHint.value,
    })
    store.setTask(res.task_id, res.task_status)
    lastTaskId.value = res.task_id
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
