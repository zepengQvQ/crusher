·<template>
  <div class="page chat-page">
    <van-nav-bar title="AI 条款助手" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon name="delete-o" size="20" style="color:#ee0a24" @click="confirmClear" />
      </template>
    </van-nav-bar>

    <van-notice-bar
      v-if="!hasContext"
      left-icon="info-o"
      text="请先完成条款分析，并从报告页进入追问；回答只来自服务端证据接口，不会本地编造。"
    />

    <div class="context-card" v-if="hasContext">
      <div class="ctx-head">
        <div class="ctx-ico">
          <van-icon name="description" size="18" style="color:#1989fa" />
        </div>
        <div class="ctx-info">
          <div class="ctx-title">已关联分析报告</div>
          <div class="ctx-preview text-ellipsis-1">{{ contextPreview }}</div>
        </div>
        <van-icon name="close" size="18" style="color:#9ca3af" @click="clearContext" />
      </div>
      <div class="ctx-findings" v-if="contextFindingCount > 0">
        <span class="risk-count-badge mid">
          <van-icon name="warning-o" size="12" /> 已发现 {{ contextFindingCount }} 条风险
        </span>
      </div>
    </div>

    <van-empty
      v-if="!messages.length"
      image="chat"
      description="有什么关于条款的疑问？问我吧~"
      style="padding: 60px 20px"
    />

    <div v-else class="chat-list" ref="chatListRef">
      <div
        v-for="m in messages"
        :key="m.id"
        class="chat-bubble-wrap"
        :class="m.role"
      >
        <div class="avatar" v-if="m.role === 'ai'">
          <van-icon name="service-o" size="20" />
        </div>
        <div class="chat-bubble" :class="m.role">
          <pre style="white-space:pre-wrap;margin:0;word-break:break-word;font-family:inherit">{{ m.content }}</pre>
          <div class="bubble-time">{{ formatTime(m.time) }}</div>
        </div>
        <div class="avatar user" v-if="m.role === 'user'">
          <van-icon name="user-o" size="18" />
        </div>
      </div>
      <div v-if="aiThinking" class="chat-bubble-wrap ai">
        <div class="avatar">
          <van-icon name="service-o" size="20" />
        </div>
        <div class="chat-bubble ai thinking">
          <span class="dot"></span>
          <span class="dot"></span>
          <span class="dot"></span>
        </div>
      </div>
    </div>

    <div class="quick-row" v-if="showQuickAsk">
      <button
        v-for="q in quickQuestions"
        :key="q"
        class="chat-quick-btn"
        @click="send(q)"
      >
        {{ q }}
      </button>
    </div>

    <div class="input-bar-wrap">
      <div class="input-bar">
        <van-field
          v-model="inputText"
          placeholder="输入你的问题…"
          type="textarea"
          autosize
          rows="1"
          class="chat-input"
          @keyup.enter.exact="onSend"
          :disabled="aiThinking"
        />
        <van-button
          type="primary"
          round
          size="small"
          :disabled="!canSend"
          :loading="aiThinking"
          @click="onSend"
        >
          <van-icon name="guide-o" size="16" />
        </van-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { showConfirmDialog, showToast } from 'vant'
import { useChatStore } from '../stores/chat'

const chatStore = useChatStore()
const inputText = ref('')
const aiThinking = ref(false)
const chatListRef = ref(null)

const messages = computed(() => chatStore.messages)
const hasContext = computed(() => !!(chatStore.contextText || '').trim())
const contextPreview = computed(
  () => chatStore.contextText?.slice(0, 60) || '（无材料预览）',
)
const contextFindingCount = computed(() => chatStore.contextFindings.length)
const canSend = computed(
  () => hasContext.value && inputText.value.trim().length > 0 && !aiThinking.value,
)
const showQuickAsk = computed(() => hasContext.value)

const quickQuestions = computed(() => {
  if (!hasContext.value) return []
  return [
    '最坏情况会损失多少？',
    '适合老年人买吗？',
    '提前赎回有何费用？',
    '保本吗？本金安全吗？',
  ]
})

function formatTime(ts) {
  const d = new Date(ts || Date.now())
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

async function scrollBottom() {
  await nextTick()
  if (chatListRef.value) {
    chatListRef.value.scrollTop = chatListRef.value.scrollHeight
  } else {
    document.querySelector('.chat-list')?.scrollTo({
      top: 99999,
      behavior: 'smooth',
    })
  }
}

async function onSend() {
  const text = inputText.value.trim()
  if (!text) return
  await send(text)
  inputText.value = ''
}

async function send(text) {
  if (aiThinking.value) return
  if (!(chatStore.contextText || '').trim()) {
    showToast('请先完成分析并关联材料后再追问')
    return
  }
  aiThinking.value = true
  try {
    await chatStore.send(text)
    await scrollBottom()
  } catch (e) {
    if (e?.code !== 'NO_CONTEXT') {
      // store 已写入失败说明；再给轻提示
      showToast('追问未成功，请查看对话中的失败说明')
    }
  } finally {
    aiThinking.value = false
    await scrollBottom()
  }
}

function clearContext() {
  chatStore.contextText = ''
  chatStore.contextFindings = []
  chatStore.pendingQuestions = []
  chatStore._persist()
  showToast('已解除关联')
}

async function confirmClear() {
  try {
    await showConfirmDialog({
      title: '清空对话记录？',
      message: '此操作无法撤销',
    })
    chatStore.clear()
    showToast('已清空')
  } catch {
    /* cancel */
  }
}

onMounted(() => {
  chatStore.restore()
  if (!chatStore.messages.length && !hasContext.value) {
    chatStore.messages.push({
      id: 'welcome_' + Date.now(),
      role: 'ai',
      content:
        '你好~我是你的条款解读助手 🤖\n\n你可以这样用：\n1️⃣ 先在首页分析一份条款，报告页点「AI 追问」带着上下文来聊；\n2️⃣ 或者直接问我通用问题，比如"什么是敲入敲出？"。\n\n试试下面的快捷问题~',
      time: Date.now(),
    })
  }
  scrollBottom()
})

watch(messages, () => scrollBottom(), { deep: true })
</script>

<style scoped>
.chat-page {
  padding-bottom: calc(120px + env(safe-area-inset-bottom));
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.context-card {
  margin: 10px 12px;
  padding: 12px 14px;
  background: var(--crusher-primary-light);
  border: 1px solid var(--crusher-border);
  border-radius: 12px;
}
.ctx-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.ctx-ico {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--crusher-card-bg);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ctx-info { flex: 1; min-width: 0; }
.ctx-title { font-size: 13px; font-weight: 600; color: var(--crusher-primary); margin-bottom: 2px; }
.ctx-preview { font-size: 12px; color: var(--crusher-ink-2); }
.ctx-findings { margin-top: 8px; }

.chat-list {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}
.chat-bubble-wrap {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.chat-bubble-wrap.user { justify-content: flex-end; }
.chat-bubble-wrap.ai { justify-content: flex-start; }

.avatar {
  width: 32px; height: 32px; border-radius: 50%;
  background: var(--crusher-grad-primary);
  color: #fff;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.avatar.user {
  background: var(--crusher-grad-warning);
}

.chat-bubble {
  max-width: 78%;
  padding: 12px 14px;
  border-radius: 16px;
  font-size: 14px;
  line-height: 1.6;
  word-break: break-word;
  position: relative;
}
.chat-bubble.user {
  background: var(--crusher-grad-primary);
  color: #fff;
  border-bottom-right-radius: 4px;
  box-shadow: 0 4px 12px rgba(25,137,250,0.22);
}
.chat-bubble.ai {
  background: var(--crusher-card-bg);
  color: var(--crusher-ink);
  border: 1px solid var(--crusher-border);
  border-bottom-left-radius: 4px;
  box-shadow: var(--crusher-shadow-sm);
}
.bubble-time {
  font-size: 10px;
  color: var(--crusher-ink-3);
  text-align: right;
  margin-top: 4px;
  opacity: 0.7;
}
.chat-bubble.user .bubble-time { color: rgba(255,255,255,0.75); text-align: right; }
.chat-bubble.ai .bubble-time { text-align: left; }

.chat-bubble.ai.thinking {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 14px 18px;
}
.chat-bubble.ai.thinking .dot {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--crusher-ink-3);
  animation: pulse 1.2s infinite;
}
.chat-bubble.ai.thinking .dot:nth-child(2) { animation-delay: 0.2s; }
.chat-bubble.ai.thinking .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes pulse {
  0%, 60%, 100% { transform: scale(0.8); opacity: 0.4; }
  30% { transform: scale(1.2); opacity: 1; }
}

.quick-row {
  padding: 6px 12px 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chat-quick-btn {
  padding: 7px 14px;
  border-radius: 999px;
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
  font-size: 13px;
  border: 1px solid var(--crusher-border);
  min-height: 32px !important;
  cursor: pointer;
  transition: all 0.15s;
  font-weight: 500;
}
.chat-quick-btn:active {
  background: var(--crusher-surface-2);
  transform: scale(0.96);
}

.input-bar-wrap {
  position: fixed;
  bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  background: linear-gradient(180deg, transparent, var(--crusher-card-bg) 30%);
  padding: 10px 12px;
  padding-bottom: calc(10px + env(safe-area-inset-bottom));
  z-index: 100;
}
.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 8px;
  background: var(--crusher-card-bg);
  border-radius: 16px;
  border: 1px solid var(--crusher-border);
  box-shadow: var(--crusher-shadow-sm);
}
.chat-input {
  flex: 1;
  min-width: 0;
  background: var(--crusher-bg-gray) !important;
}
.chat-input :deep(.van-field__control) {
  padding: 6px 4px !important;
  font-size: 14px !important;
  max-height: 90px;
}
.input-bar .van-button {
  width: 42px !important;
  height: 40px !important;
  min-height: 40px !important;
  padding: 0 !important;
  flex-shrink: 0;
}
</style>
