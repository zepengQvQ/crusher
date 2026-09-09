<template>
  <div class="card" :class="`st-${item.status}`">
    <div class="head" @click="open = !open">
      <div class="title">{{ subjectLabel }}</div>
      <van-tag :type="tagType" plain>{{ statusLabel }}</van-tag>
    </div>
    <p class="summary">{{ item.summary }}</p>
    <p v-if="item.suggested_follow_up" class="follow">建议追问：{{ item.suggested_follow_up }}</p>
    <van-button size="small" plain class="touch-btn" @click="open = !open">
      {{ open ? '收起原文' : '展开 A/B 原文' }}
    </van-button>
    <div v-if="open" class="evidence">
      <div class="ev-block">
        <div class="ev-label">销售侧</div>
        <p class="ev-quote">{{ item.sales_claim?.evidence?.quote || '—' }}</p>
      </div>
      <div class="ev-block">
        <div class="ev-label">正式材料</div>
        <p class="ev-quote">{{ item.official_evidence?.quote || '（未找到）' }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  item: { type: Object, required: true },
})

const open = ref(false)

const STATUS_MAP = {
  confirmed: '一致',
  not_found: '正式材料未找到',
  conflict: '存在冲突',
  conditional: '附加条件',
  uncertain: '待确认',
}

const SUBJECT_MAP = {
  expected_return: '收益',
  fee: '费用',
  early_exit: '提前退出',
  principal_protection: '本金保障',
  term: '期限',
}

const statusLabel = computed(() => STATUS_MAP[props.item.status] || props.item.status)
const subjectLabel = computed(() => SUBJECT_MAP[props.item.subject] || props.item.subject)
const tagType = computed(() => {
  const s = props.item.status
  if (s === 'confirmed') return 'success'
  if (s === 'conflict') return 'danger'
  if (s === 'conditional') return 'warning'
  if (s === 'not_found') return 'primary'
  return 'default'
})
</script>

<style scoped>
.card {
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 10px;
  background: #f8fafc;
  border-left: 4px solid #94a3b8;
}
.st-confirmed {
  border-left-color: #16a34a;
}
.st-conflict {
  border-left-color: #dc2626;
}
.st-conditional {
  border-left-color: #d97706;
}
.st-not_found {
  border-left-color: #2563eb;
}
.st-uncertain {
  border-left-color: #64748b;
}
.head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.title {
  font-weight: 600;
  font-size: 15px;
}
.summary {
  margin: 8px 0;
  font-size: 14px;
  line-height: 1.5;
  color: #334155;
}
.follow {
  margin: 0 0 8px;
  font-size: 12px;
  color: #64748b;
}
.evidence {
  margin-top: 10px;
}
.ev-block {
  margin-bottom: 8px;
}
.ev-label {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 4px;
}
.ev-quote {
  margin: 0;
  padding: 8px;
  background: #fff;
  border-radius: 6px;
  font-size: 13px;
  line-height: 1.45;
  white-space: pre-wrap;
  word-break: break-word;
}
.touch-btn {
  min-height: 36px;
}
</style>
