<template>
  <div class="actions">
    <div class="title">带走结果</div>
    <p class="note">可复制报告，或保存到本机（最多 10 份；清理浏览器数据后会丢失）。</p>
    <div class="row">
      <van-button size="small" type="primary" class="touch-btn" @click="onCopy">复制报告</van-button>
      <van-button size="small" plain class="touch-btn" :loading="saving" @click="onSave">保存本机</van-button>
    </div>
    <button type="button" class="link" @click="$router.push('/history')">查看已保存 ›</button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { copyText } from '../api/client'
import { saveReport } from '../services/reportStorage'
import { reportToMarkdown } from '../utils/reportToMarkdown'

const props = defineProps({
  report: { type: Object, required: true },
  kind: { type: String, default: 'analysis' },
  title: { type: String, default: '分析报告' },
  taskId: { type: String, default: '' },
  sourceText: { type: String, default: '' },
})

const saving = ref(false)

async function onCopy() {
  const md = reportToMarkdown(props.report, {
    kind: props.kind,
    title: props.title,
  })
  const ok = await copyText(md)
  showToast(ok ? '已复制报告' : '复制失败')
}

async function onSave() {
  saving.value = true
  try {
    await saveReport({
      title: props.title,
      kind: props.kind,
      report: props.report,
      task_id: props.taskId || undefined,
    })
    showToast('已保存到本机')
  } catch (e) {
    showToast(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.title {
  font-weight: 600;
  font-size: 15px;
}
.note {
  margin: 0;
  font-size: 12px;
  color: var(--crusher-ink-3, #64748b);
  line-height: 1.45;
}
.row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.touch-btn {
  min-height: 44px;
}
.link {
  align-self: flex-start;
  border: 0;
  background: transparent;
  padding: 6px 0;
  font: inherit;
  font-size: 13px;
  color: var(--van-primary-color, #1989fa);
  cursor: pointer;
}
</style>
