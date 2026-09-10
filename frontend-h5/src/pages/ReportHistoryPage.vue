<template>
  <div class="page">
    <van-nav-bar title="本地已保存报告" left-arrow @click-left="$router.push('/')" />
    <van-notice-bar
      left-icon="info-o"
      text="记录仅存本机 IndexedDB，最多 10 份；清理浏览器数据后会丢失。不做跨设备同步。"
    />
    <div class="block">
      <van-empty v-if="!loading && !items.length" description="暂无保存的报告" />
      <van-cell
        v-for="item in items"
        :key="item.report_id"
        :title="item.title"
        :label="`${formatTime(item.created_at)} · ${item.kind}`"
        is-link
        @click="open(item)"
      >
        <template #right-icon>
          <van-button size="mini" type="danger" plain @click.stop="remove(item.report_id)">
            删除
          </van-button>
        </template>
      </van-cell>
    </div>

    <van-popup v-model:show="showDetail" position="bottom" round :style="{ height: '90%' }">
      <div class="detail">
        <h3>{{ current?.title }}</h3>
        <p v-if="incompatible" class="warn">旧报告无法直接打开（schema 不兼容）</p>
        <template v-else-if="current">
          <pre class="md">{{ markdown }}</pre>
          <van-button block type="primary" class="touch-btn" @click="copyMd">复制 Markdown</van-button>
        </template>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { showToast } from 'vant'
import { copyText } from '../api/client'
import {
  deleteReport,
  getReport,
  isSchemaCompatible,
  listReports,
} from '../services/reportStorage'
import { reportToMarkdown } from '../utils/reportToMarkdown'

const loading = ref(true)
const items = ref([])
const showDetail = ref(false)
const current = ref(null)
const incompatible = ref(false)
const markdown = ref('')

async function refresh() {
  loading.value = true
  try {
    items.value = await listReports()
  } catch (e) {
    showToast(e?.message || '读取失败')
    items.value = []
  } finally {
    loading.value = false
  }
}

function formatTime(iso) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

async function open(item) {
  const full = await getReport(item.report_id)
  current.value = full
  incompatible.value = !isSchemaCompatible(full)
  markdown.value = incompatible.value
    ? ''
    : reportToMarkdown(full.report, {
        kind: full.kind,
        title: full.title,
        sourceText: full.source_text || '',
      })
  showDetail.value = true
}

async function remove(id) {
  await deleteReport(id)
  showToast('已删除')
  if (current.value?.report_id === id) {
    showDetail.value = false
    current.value = null
  }
  await refresh()
}

async function copyMd() {
  const ok = await copyText(markdown.value)
  showToast(ok ? '已复制' : '复制失败')
}

onMounted(refresh)
</script>

<style scoped>
.detail {
  padding: 16px;
  overflow: auto;
  height: 100%;
  box-sizing: border-box;
}
.warn {
  color: #c2410c;
  font-size: 14px;
}
.md {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  background: var(--crusher-surface);
  padding: 12px;
  border-radius: 8px;
  max-height: 60vh;
  overflow: auto;
}
.touch-btn {
  min-height: 44px;
  margin-top: 12px;
}
</style>
