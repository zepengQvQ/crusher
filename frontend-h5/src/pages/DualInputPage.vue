<template>
  <div class="page">
    <van-nav-bar title="销售与材料对照" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar left-icon="info-o" text="同一产品：上栏销售话术，下栏正式材料。不判断法律效力。" />
    <div class="block">
      <div class="label">A · 销售话术</div>
      <van-field
        v-model="salesText"
        rows="5"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        placeholder="粘贴聊天、宣传或口头承诺整理…"
        class="touch-field"
      />
      <div class="label">B · 正式材料</div>
      <van-field
        v-model="officialText"
        rows="5"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        placeholder="粘贴说明书、合同或风险揭示…"
        class="touch-field"
      />
      <div class="actions">
        <van-button size="small" plain type="primary" class="touch-btn" @click="fillDemo">
          填入对照示例
        </van-button>
        <van-button size="small" plain class="touch-btn" @click="onClear">清空</van-button>
      </div>
      <van-button
        type="primary"
        block
        round
        class="touch-btn main-btn"
        :loading="loading"
        @click="onSubmit"
      >
        开始对照
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createDualAnalysis, pickErrorMessage } from '../api/client'
import { MAX_INPUT_CHARS } from '../api/generated-types'

const DUAL_STORE_KEY = 'crusher_dual_report'

const router = useRouter()
const salesText = ref('')
const officialText = ref('')
const loading = ref(false)

function fillDemo() {
  salesText.value = '本产品年化收益率3.65%，我们不收费，随时可以提前支取。'
  officialText.value =
    '产品说明书：年化收益率3.65%。费用说明：提前支取若未满观察期，需支付手续费0.5%。'
}

function onClear() {
  salesText.value = ''
  officialText.value = ''
}

async function onSubmit() {
  const a = salesText.value.trim()
  const b = officialText.value.trim()
  if (!a || !b) {
    showToast('请同时填写销售话术与正式材料')
    return
  }
  loading.value = true
  try {
    const report = await createDualAnalysis(a, b, 'auto')
    sessionStorage.setItem(DUAL_STORE_KEY, JSON.stringify(report))
    router.push({ name: 'dual-report' })
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
.label {
  margin: 8px 0 6px;
  font-size: 13px;
  font-weight: 600;
  color: #475569;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 10px 0 14px;
}
.touch-btn {
  min-height: 44px;
}
.main-btn {
  margin-top: 4px;
}
.touch-field :deep(textarea) {
  min-height: 96px;
}
</style>
