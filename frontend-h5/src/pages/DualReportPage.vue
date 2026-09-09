<template>
  <div class="page">
    <van-nav-bar title="对照报告" left-arrow @click-left="$router.push('/dual')" />
    <div v-if="!report" class="block">
      <van-empty description="暂无对照结果，请返回重新提交" />
      <van-button block round type="primary" class="touch-btn" @click="$router.push('/dual')">
        返回对照输入
      </van-button>
    </div>
    <template v-else>
      <div class="block">
        <p class="meta">共 {{ report.comparisons?.length || 0 }} 条对照</p>
        <p class="disclaimer">{{ report.disclaimer }}</p>
        <ClaimComparisonCard
          v-for="c in report.comparisons"
          :key="c.comparison_id"
          :item="c"
        />
        <div v-if="report.pending_questions?.length" class="pending">
          <div class="pending-title">建议继续核对</div>
          <p v-for="(q, i) in report.pending_questions" :key="i" class="pending-item">· {{ q }}</p>
        </div>
        <van-button block round plain class="touch-btn" @click="$router.push('/dual')">
          再对照一组
        </van-button>
        <van-button block round plain class="touch-btn" style="margin-top: 8px" @click="$router.push('/')">
          返回单文本分析
        </van-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import ClaimComparisonCard from '../components/ClaimComparisonCard.vue'

const DUAL_STORE_KEY = 'crusher_dual_report'
const report = ref(null)

onMounted(() => {
  try {
    const raw = sessionStorage.getItem(DUAL_STORE_KEY)
    report.value = raw ? JSON.parse(raw) : null
  } catch {
    report.value = null
  }
})
</script>

<style scoped>
.block {
  padding: 12px 16px 28px;
}
.meta {
  margin: 0 0 6px;
  font-size: 13px;
  color: #64748b;
}
.disclaimer {
  margin: 0 0 14px;
  font-size: 12px;
  color: #94a3b8;
  line-height: 1.4;
}
.pending {
  margin: 8px 0 16px;
  padding: 10px;
  background: #fff7ed;
  border-radius: 8px;
}
.pending-title {
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 6px;
}
.pending-item {
  margin: 0 0 4px;
  font-size: 13px;
  color: #9a3412;
}
.touch-btn {
  min-height: 44px;
}
</style>
