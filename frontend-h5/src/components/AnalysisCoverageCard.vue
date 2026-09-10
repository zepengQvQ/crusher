<template>
  <div v-if="coverage" class="card">
    <div class="title">本次系统检查范围</div>
    <p class="hint">「材料未说明」≠「系统没有检查」；下列未检查项不代表产品无风险。</p>
    <div class="col">
      <div class="label">已检查</div>
      <ul v-if="checked.length">
        <li v-for="(item, i) in checked" :key="'c' + i">{{ item }}</li>
      </ul>
      <p v-else class="empty">本次未进入可检查阶段</p>
    </div>
    <div class="col">
      <div class="label">未检查 / 未确认</div>
      <ul v-if="notChecked.length">
        <li v-for="(item, i) in notChecked" :key="'n' + i">{{ item }}</li>
      </ul>
      <p v-else class="empty">无</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  coverage: { type: Object, default: null },
})

const checked = computed(() => props.coverage?.checked || [])
const notChecked = computed(() => props.coverage?.not_checked || [])
</script>

<style scoped>
.card {
  padding: 12px;
  background: var(--crusher-surface);
  border-radius: 10px;
  border: 1px solid var(--crusher-border);
}
.title {
  font-weight: 600;
  margin-bottom: 6px;
}
.hint {
  margin: 0 0 10px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.col + .col {
  margin-top: 10px;
}
.label {
  font-size: 13px;
  color: var(--crusher-ink-2);
  margin-bottom: 4px;
}
ul {
  margin: 0;
  padding-left: 1.2em;
  font-size: 13px;
  line-height: 1.5;
  color: #475569;
}
.empty {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}
</style>
