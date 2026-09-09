<template>
  <div class="page">
    <van-nav-bar title="两款产品对照" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar
      left-icon="info-o"
      text="仅并列事实与缺失项，不做推荐、评分或购买建议。只支持两款产品。"
    />
    <div class="block">
      <van-field
        v-model="textA"
        rows="5"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        label="产品 A"
        placeholder="粘贴第一款产品材料…"
      />
      <van-field
        v-model="textB"
        rows="5"
        autosize
        type="textarea"
        :maxlength="MAX_INPUT_CHARS"
        show-word-limit
        label="产品 B"
        placeholder="粘贴第二款产品材料…"
      />
      <van-button
        block
        round
        type="primary"
        class="touch-btn"
        :loading="loading"
        @click="onSubmit"
      >
        开始对照
      </van-button>
    </div>

    <div v-if="report" class="block">
      <p class="disclaimer">{{ report.disclaimer }}</p>
      <ProductComparisonCard
        v-for="(d, i) in report.dimensions"
        :key="d.dimension + i"
        :item="d"
      />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { createProductComparison, pickErrorMessage } from '../api/client'
import { MAX_INPUT_CHARS } from '../api/generated-types'
import ProductComparisonCard from '../components/ProductComparisonCard.vue'

const COMPARE_A_KEY = 'crusher_compare_a'

const textA = ref('')
const textB = ref('')
const loading = ref(false)
const report = ref(null)

onMounted(() => {
  try {
    const draft = sessionStorage.getItem(COMPARE_A_KEY)
    if (draft) {
      textA.value = draft
      sessionStorage.removeItem(COMPARE_A_KEY)
    }
  } catch {
    /* ignore */
  }
})

async function onSubmit() {
  if (!textA.value.trim() || !textB.value.trim()) {
    showToast('请填写两款产品材料')
    return
  }
  loading.value = true
  report.value = null
  try {
    report.value = await createProductComparison(textA.value, textB.value)
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.touch-btn {
  min-height: 44px;
  margin-top: 12px;
}
.disclaimer {
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.45;
  margin: 0 0 12px;
}
</style>
