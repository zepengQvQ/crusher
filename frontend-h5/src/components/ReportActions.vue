<template>
  <div class="actions">
    <div class="title">带走结果</div>
    <p class="note">
      本地最多保存 10 份；默认不含完整原文，但会保留结论核对用的原文片段。清理浏览器数据后会丢失。
    </p>
    <label class="check">
      <input v-model="includeSource" type="checkbox" />
      额外保存完整输入原文
    </label>
    <van-button size="small" type="primary" class="touch-btn" :loading="saving" @click="onSave">
      保存到本机
    </van-button>
    <van-button size="small" plain class="touch-btn" @click="onCopyHighlights">复制重点</van-button>
    <van-button size="small" plain class="touch-btn" @click="onCopyFull">复制完整报告</van-button>
    <van-button size="small" plain class="touch-btn" @click="onShare">系统分享</van-button>
    <van-button size="small" plain class="touch-btn" @click="$router.push('/history')">
      查看已保存
    </van-button>
    <van-field
      v-if="manualShare"
      v-model="manualShare"
      rows="4"
      autosize
      type="textarea"
      label="请手动复制"
      readonly
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { copyText } from '../api/client'
import { saveReport } from '../services/reportStorage'
import { reportHighlights, reportToMarkdown } from '../utils/reportToMarkdown'

const props = defineProps({
  report: { type: Object, required: true },
  kind: { type: String, default: 'analysis' },
  title: { type: String, default: '分析报告' },
  taskId: { type: String, default: '' },
  sourceText: { type: String, default: '' },
})

const includeSource = ref(false)
const saving = ref(false)
const manualShare = ref('')

async function onSave() {
  saving.value = true
  try {
    await saveReport({
      title: props.title,
      kind: props.kind,
      report: props.report,
      task_id: props.taskId || undefined,
      source_text: includeSource.value ? props.sourceText || undefined : undefined,
    })
    showToast('已保存到本机')
  } catch (e) {
    showToast(e?.message || '保存失败')
  } finally {
    saving.value = false
  }
}

async function onCopyHighlights() {
  const ok = await copyText(reportHighlights(props.report))
  showToast(ok ? '已复制重点' : '复制失败')
}

async function onCopyFull() {
  const md = reportToMarkdown(props.report, {
    kind: props.kind,
    title: props.title,
    sourceText: includeSource.value ? props.sourceText : '',
  })
  const ok = await copyText(md)
  showToast(ok ? '已复制完整报告' : '复制失败')
}

async function onShare() {
  const text = reportToMarkdown(props.report, {
    kind: props.kind,
    title: props.title,
  })
  if (typeof navigator !== 'undefined' && navigator.share) {
    try {
      await navigator.share({ title: props.title, text })
      return
    } catch {
      /* fall through */
    }
  }
  manualShare.value = text
  showToast('当前环境不支持系统分享，请手动复制')
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
  color: #64748b;
  line-height: 1.45;
}
.check {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  min-height: 44px;
}
.touch-btn {
  min-height: 44px;
}
</style>
