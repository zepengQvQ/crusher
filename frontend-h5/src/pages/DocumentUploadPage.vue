<template>
  <div class="page">
    <van-nav-bar title="上传材料" left-arrow @click-left="$router.push('/')" />
    <div class="block">
      <DocumentUploader @extracted="onExtracted" />
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import DocumentUploader from '../components/DocumentUploader.vue'

const EXTRACT_KEY = 'crusher_extracted_doc'
const router = useRouter()

function onExtracted(doc) {
  if (!doc?.combined_text?.trim() && doc?.overall_status === 'failed') {
    showToast(doc.message || '提取失败')
    return
  }
  sessionStorage.setItem(EXTRACT_KEY, JSON.stringify(doc))
  router.push({ name: 'extract-confirm' })
}
</script>

<style scoped>
.block {
  padding: 12px 16px 24px;
}
</style>
