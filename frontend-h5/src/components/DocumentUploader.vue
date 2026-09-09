<template>
  <div class="uploader">
    <van-uploader
      v-model="fileList"
      multiple
      :max-count="5"
      accept="image/*,application/pdf"
      :after-read="onAfterRead"
      @delete="onDelete"
    />
    <p class="tip">支持 JPG/PNG（最多 5 张）或单个 PDF（≤10 页/10MB）。提取后必须确认文字再分析。</p>
    <van-button
      block
      round
      type="primary"
      class="touch-btn"
      :loading="loading"
      :disabled="!rawFiles.length"
      @click="onExtract"
    >
      提取文字
    </van-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { showToast } from 'vant'
import { extractDocuments, pickErrorMessage } from '../api/client'

const emit = defineEmits(['extracted'])

const fileList = ref([])
const rawFiles = ref([])
const loading = ref(false)

function onAfterRead(items) {
  const list = Array.isArray(items) ? items : [items]
  for (const item of list) {
    if (item.file) rawFiles.value.push(item.file)
  }
}

function onDelete() {
  rawFiles.value = fileList.value.map((x) => x.file).filter(Boolean)
}

async function onExtract() {
  if (!rawFiles.value.length) {
    showToast('请先选择文件')
    return
  }
  loading.value = true
  try {
    const doc = await extractDocuments(rawFiles.value)
    emit('extracted', doc)
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.uploader {
  margin: 8px 0 16px;
}
.tip {
  margin: 8px 0 12px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.4;
}
.touch-btn {
  min-height: 44px;
}
</style>
