<template>
  <div v-if="coverage" class="card">
    <div class="title">这次系统看了什么</div>
    <p class="hint">材料没写到的内容，不等于系统没检查；下面「没做」的事，也不等于产品没风险。</p>

    <div class="section ok">
      <div class="label">已检查</div>
      <div class="chips" v-if="checkedLabels.length">
        <span v-for="(item, i) in checkedLabels" :key="'c' + i" class="chip chip-ok">{{ item }}</span>
      </div>
      <p v-else class="empty">这次还没走到可检查的步骤</p>
    </div>

    <div class="section skip">
      <div class="label">未检查</div>
      <div class="chips" v-if="notCheckedLabels.length">
        <span v-for="(item, i) in notCheckedLabels" :key="'n' + i" class="chip chip-skip">{{ item }}</span>
      </div>
      <p v-else class="empty">无</p>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  coverage: { type: Object, default: null },
})

/** 把程序术语翻成用户能懂的短句；未知项原样展示。 */
const LABEL_MAP = {
  '产品类型识别（程序规则）': '产品类型',
  '关键参数抽取（程序规则）': '关键数字与条款',
  '风险模式匹配（程序规则）': '常见风险点',
  证据位置校验: '原文证据位置',
  模型解释引用与数值门禁: '通俗说明是否乱写数字',
  用户适当性评估: '是否适合你买（适当性）',
  完整合同法律效力: '合同是否具有完整法律效力',
  市场行情与未来收益预测: '市场走势与未来收益',
  未配置规则覆盖的风险: '规则没覆盖到的其他风险',
  '模型通俗解释（未通过校验）': '模型通俗说明（未通过）',
}

function humanize(item) {
  const raw = String(item || '').trim()
  if (!raw) return ''
  return LABEL_MAP[raw] || raw.replace(/（程序规则）/g, '').replace(/\(程序规则\)/g, '')
}

const checkedLabels = computed(() =>
  (props.coverage?.checked || []).map(humanize).filter(Boolean),
)
const notCheckedLabels = computed(() =>
  (props.coverage?.not_checked || []).map(humanize).filter(Boolean),
)
</script>

<style scoped>
.card {
  padding: 14px;
  background: var(--crusher-card-bg, #fff);
  border-radius: 12px;
}
.title {
  font-weight: 600;
  font-size: 15px;
  color: var(--crusher-ink);
  margin-bottom: 6px;
}
.hint {
  margin: 0 0 12px;
  font-size: 12px;
  color: var(--crusher-ink-3, #64748b);
  line-height: 1.5;
}
.section + .section {
  margin-top: 12px;
}
.label {
  font-size: 12px;
  font-weight: 600;
  color: var(--crusher-ink-2);
  margin-bottom: 8px;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  display: inline-flex;
  align-items: center;
  max-width: 100%;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  line-height: 1.3;
  font-weight: 500;
}
.chip-ok {
  background: var(--crusher-success-light, #e8f8ef);
  color: var(--crusher-success, #07c160);
}
.chip-skip {
  background: var(--crusher-bg-gray, #f3f4f6);
  color: var(--crusher-ink-2, #64748b);
}
.empty {
  margin: 0;
  font-size: 13px;
  color: #94a3b8;
}
</style>
