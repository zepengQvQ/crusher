<template>
  <div class="page">
    <van-nav-bar title="出错了" left-arrow @click-left="$router.push('/')" />
    <div class="block">
      <van-empty image="error" :description="message" />
      <p v-if="code" class="code">错误码：{{ code }}</p>
      <p class="hint">这不是「没发现风险」。请返回后重试，或换一段文本。</p>
      <van-button block type="primary" round @click="$router.push('/')">返回重试</van-button>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useTaskStore } from '../stores/task'

const store = useTaskStore()
const message = computed(() => {
  // 兜底：绝不展示成安全结论
  const raw = store.lastError || '请求失败，请重试'
  if (raw.includes('未发现风险') || raw.includes('没有风险')) {
    return '模型调用失败'
  }
  return raw
})
const code = computed(() => store.lastErrorCode || '')
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
</style>
