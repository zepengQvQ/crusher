<template>
  <div class="card" :class="`st-${item.status}`">
    <div class="head" @click="open = !open">
      <div class="title">{{ item.label }}</div>
      <van-tag plain :type="tagType">{{ statusLabel }}</van-tag>
    </div>
    <p class="note">{{ item.note }}</p>
    <div class="sides">
      <div class="side">
        <div class="side-label">A</div>
        <p>{{ item.side_a?.display || '材料未说明' }}</p>
      </div>
      <div class="side">
        <div class="side-label">B</div>
        <p>{{ item.side_b?.display || '材料未说明' }}</p>
      </div>
    </div>
    <van-button size="small" plain class="touch-btn" @click="open = !open">
      {{ open ? '收起原文' : '展开双方原文' }}
    </van-button>
    <div v-if="open" class="evidence">
      <div class="ev">
        <div class="ev-label">A 原文</div>
        <p v-for="(e, i) in item.side_a?.evidence || []" :key="'a' + i">{{ e.quote }}</p>
        <p v-if="!(item.side_a?.evidence || []).length">—</p>
      </div>
      <div class="ev">
        <div class="ev-label">B 原文</div>
        <p v-for="(e, i) in item.side_b?.evidence || []" :key="'b' + i">{{ e.quote }}</p>
        <p v-if="!(item.side_b?.evidence || []).length">—</p>
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
  same: '一致',
  different: '不同',
  missing_a: 'A 未说明',
  missing_b: 'B 未说明',
  both_missing: '两侧未说明',
  incomparable: '不可直接比较',
}

const statusLabel = computed(() => STATUS_MAP[props.item.status] || props.item.status)
const tagType = computed(() => {
  const s = props.item.status
  if (s === 'same') return 'success'
  if (s === 'different') return 'danger'
  if (s === 'incomparable') return 'warning'
  return 'primary'
})
</script>

<style scoped>
.card {
  margin: 0 0 12px;
  padding: 12px;
  border-radius: 12px;
  background: var(--crusher-surface);
  border-left: 4px solid var(--crusher-ink-3);
}
.st-same {
  border-left-color: var(--crusher-success);
}
.st-different {
  border-left-color: var(--crusher-danger);
}
.st-incomparable {
  border-left-color: var(--crusher-warning);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.title {
  font-weight: 600;
  font-size: 15px;
  color: var(--crusher-ink);
}
.note {
  margin: 6px 0;
  font-size: 12px;
  color: var(--crusher-ink-2);
}
.sides {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: 8px;
}
.side {
  background: var(--crusher-card-bg);
  border: 1px solid var(--crusher-border);
  border-radius: 8px;
  padding: 8px;
  font-size: 13px;
  word-break: break-word;
  color: var(--crusher-ink);
}
.side-label {
  font-size: 11px;
  color: var(--crusher-ink-3);
  margin-bottom: 4px;
}
.evidence {
  margin-top: 8px;
}
.ev {
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--crusher-ink-2);
}
.ev-label {
  font-weight: 600;
  margin-bottom: 2px;
  color: var(--crusher-ink);
}
.touch-btn {
  min-height: 44px;
}
</style>
