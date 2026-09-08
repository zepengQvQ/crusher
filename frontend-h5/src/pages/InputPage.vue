<template>
  <div class="page">
    <van-nav-bar title="金融话术粉碎机" />
    <van-notice-bar
      left-icon="info-o"
      text="密钥只在本机 Python 程序的 .env 里配置；网页不能填 Key。重启服务后旧任务会丢失。"
    />
    <div class="block">
      <van-field
        v-model="text"
        rows="8"
        autosize
        type="textarea"
        maxlength="8000"
        show-word-limit
        placeholder="粘贴结构性存款或借贷相关条款…"
      />
      <div class="actions">
        <van-button size="small" plain type="primary" @click="fillExample">填入示例</van-button>
        <van-button size="small" plain @click="text = ''">清空</van-button>
      </div>
      <van-button
        type="primary"
        block
        round
        :loading="loading"
        style="margin-top: 12px"
        @click="onSubmit()"
      >
        开始分析
      </van-button>
      <van-button
        block
        round
        plain
        type="warning"
        :loading="loading"
        style="margin-top: 10px"
        @click="onSubmit('model_timeout')"
      >
        演示：模拟模型超时（应显示调用失败）
      </van-button>
      <van-button
        v-if="lastTaskId"
        block
        round
        plain
        style="margin-top: 10px"
        @click="resumeLast"
      >
        恢复上次任务 {{ lastTaskId }}
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { showToast } from 'vant'
import { createAnalysis, pickErrorMessage } from '../api/client'
import { useTaskStore } from '../stores/task'

const router = useRouter()
const store = useTaskStore()
const text = ref('')
const loading = ref(false)
const lastTaskId = ref('')

const EXAMPLE =
  '本产品为结构性存款，期限90天，挂钩美元兑日元汇率。若观察期内汇率始终位于145.00-155.00区间，则到期年化收益率4.80%；若突破区间，则到期年化收益率1.20%。'

onMounted(() => {
  lastTaskId.value = store.restoreFromStorage() || ''
})

function fillExample() {
  text.value = EXAMPLE
}

function resumeLast() {
  if (!lastTaskId.value) return
  router.push({ name: 'status', params: { taskId: lastTaskId.value } })
}

async function onSubmit(demoError) {
  const value = text.value.trim()
  if (!value) {
    showToast('请先粘贴条款文本')
    return
  }
  loading.value = true
  try {
    const res = await createAnalysis(value, { demoError })
    store.setTask(res.task_id, res.task_status)
    lastTaskId.value = res.task_id
    router.push({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    const msg = pickErrorMessage(e)
    const code = e?.response?.data?.detail?.error_code || ''
    store.setError(msg, code)
    router.push({ name: 'error' })
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  flex-wrap: wrap;
}
</style>
