<template>
  <div class="page chat-page" :class="{ 'skill-open': showSkillPanel }">
    <van-nav-bar title="AI 条款助手" left-arrow @click-left="goHome">
      <template #right>
        <van-icon name="delete-o" size="20" style="color:#ee0a24" @click="confirmClear" />
      </template>
    </van-nav-bar>

    <div class="chat-top" v-if="showNotice || showContextCard">
      <van-notice-bar
        v-if="showNotice"
        left-icon="info-o"
        :text="noticeText"
      />

      <div class="context-card" v-if="showContextCard">
        <div class="ctx-head">
          <div class="ctx-ico">
            <van-icon name="description" size="18" style="color:#1989fa" />
          </div>
          <div class="ctx-info">
            <div class="ctx-title">{{ contextCardTitle }}</div>
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
    </div>

    <div class="chat-list" ref="chatListRef">
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
          <div
            v-if="m.meta?.kind === 'intent' && m.meta.options?.length"
            class="intent-options"
          >
            <button
              v-for="(opt, i) in m.meta.options"
              :key="(opt.intent || '') + i"
              class="chat-quick-btn"
              type="button"
              :disabled="aiThinking"
              @click="onClarifyPick(opt)"
            >
              {{ opt.label || opt.intent }}
            </button>
          </div>
          <div v-if="m.meta?.kind === 'analyze_done' && m.meta.taskId" class="intent-options">
            <button
              class="chat-quick-btn"
              type="button"
              @click="goReport(m.meta.taskId)"
            >
              查看报告
            </button>
          </div>
          <div v-if="m.meta?.kind === 'follow_up' && m.meta.needSupplement" class="intent-options">
            <button
              class="chat-quick-btn"
              type="button"
              :disabled="aiThinking"
              @click="openSupplement"
            >
              去补充材料
            </button>
          </div>
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

    <div class="quick-row" v-if="showFollowUpAsk">
      <button
        v-for="q in followUpQuestions"
        :key="q"
        class="chat-quick-btn"
        type="button"
        :disabled="aiThinking"
        @click="send(q)"
      >
        {{ q }}
      </button>
    </div>

    <div class="composer">
      <div v-if="showSkillPanel" class="skill-panel">
        <button
          v-for="s in SKILL_ITEMS"
          :key="s.key"
          type="button"
          class="skill-item"
          :disabled="aiThinking"
          @click="onSkill(s.key)"
        >
          <div class="skill-ico"><van-icon :name="s.icon" size="20" /></div>
          <div class="skill-label">{{ s.label }}</div>
        </button>
      </div>
      <div class="composer-row">
        <button
          type="button"
          class="icon-btn"
          :class="{ active: showSkillPanel }"
          :disabled="aiThinking"
          @click="showSkillPanel = !showSkillPanel"
          aria-label="技能栏"
        >
          <van-icon :name="showSkillPanel ? 'cross' : 'plus'" size="22" />
        </button>
        <van-field
          v-model="inputText"
          :placeholder="hasContext ? '输入你的问题…' : '说说你想做什么…'"
          type="textarea"
          autosize
          rows="1"
          class="composer-field"
          @keyup.enter.exact="onSend"
          :disabled="aiThinking"
          @focus="showSkillPanel = false"
        />
        <button
          type="button"
          class="icon-btn send"
          :disabled="!canSend"
          @click="onSend"
          aria-label="发送"
        >
          <van-icon v-if="!aiThinking" name="guide-o" size="20" />
          <van-loading v-else size="18" />
        </button>
      </div>
    </div>

    <input
      ref="fileInputRef"
      type="file"
      class="hidden-file"
      accept="image/*,.pdf,application/pdf"
      multiple
      @change="onFilePicked"
    />

    <van-popup v-model:show="showPasteSheet" position="bottom" round :style="{ height: '70%' }">
      <div class="paste-sheet">
        <div class="paste-head">
          <h3>粘贴条款</h3>
          <p class="paste-hint">内容会加入本会话材料，不会跳转到其它页面。</p>
        </div>
        <div class="paste-body">
          <van-field
            v-model="pasteText"
            rows="8"
            type="textarea"
            maxlength="8000"
            show-word-limit
            class="paste-field"
            placeholder="粘贴结构性存款或借贷相关条款…"
          />
        </div>
        <div class="paste-actions">
          <van-button block plain class="touch-btn" @click="showPasteSheet = false">取消</van-button>
          <van-button block type="primary" class="touch-btn" @click="confirmPaste">加入会话</van-button>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { showConfirmDialog, showToast } from 'vant'
import { SKILL_ITEMS, useChatStore } from '../stores/chat'
import { useTaskStore } from '../stores/task'
import { saveIntentContext } from '../utils/intentContext'

const router = useRouter()
const chatStore = useChatStore()
const taskStore = useTaskStore()
const inputText = ref('')
const pasteText = ref('')
const aiThinking = ref(false)
const showSkillPanel = ref(false)
const showPasteSheet = ref(false)
const chatListRef = ref(null)
const fileInputRef = ref(null)

const messages = computed(() => chatStore.messages)
const hasContext = computed(() => chatStore.hasContext)
const hasMaterials = computed(() => chatStore.hasMaterials)
const contextPreview = computed(
  () => chatStore.materialSourceText?.slice(0, 60) || '（无材料预览）',
)
const contextFindingCount = computed(() => chatStore.contextFindings.length)
const showContextCard = computed(() => hasContext.value)
const showNotice = computed(() => !hasContext.value)
const contextCardTitle = computed(() =>
  contextFindingCount.value > 0
    ? '已关联分析报告'
    : hasMaterials.value
      ? `会话材料 · ${chatStore.materials.length}`
      : '已关联材料',
)
const noticeText = '点左下角「+」粘贴或上传材料，也可直接说出想做的事'
const canSend = computed(() => inputText.value.trim().length > 0 && !aiThinking.value)
const showFollowUpAsk = computed(
  () => hasContext.value && contextFindingCount.value > 0 && !showSkillPanel.value,
)

const followUpQuestions = [
  '最坏情况会损失多少？',
  '适合老年人买吗？',
  '提前赎回有何费用？',
  '保本吗？本金安全吗？',
]

function formatTime(ts) {
  const d = new Date(ts || Date.now())
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

function routeForIntent(intent) {
  if (intent === 'dual_source_compare') return '/dual'
  if (intent === 'product_compare') return '/compare'
  if (intent === 'document_extract') return null
  if (intent === 'single_analysis') return null
  return null
}

function persistAndGo(path, intent, userGoal = '') {
  saveIntentContext({
    text: chatStore.materialSourceText || taskStore.draftText || '',
    userGoal,
    productHint: taskStore.productHint || 'auto',
    targetIntent: intent || '',
  })
  router.push(path)
}

function handleResolvedIntent(intent, userGoal = '') {
  if (intent === 'single_analysis') {
    showToast('请用「+」添加材料后点「开始分析」')
    showSkillPanel.value = true
    return true
  }
  if (intent === 'document_extract') {
    showToast('请用「+」→「上传文件」')
    showSkillPanel.value = true
    return true
  }
  const path = routeForIntent(intent)
  if (path) {
    persistAndGo(path, intent, userGoal)
    return true
  }
  if (intent === 'calculation') {
    showToast('请先完成一次分析，再在报告页打开计算器')
    return true
  }
  if (intent === 'evidence_follow_up') {
    showToast('请先完成分析后再追问')
    return true
  }
  return false
}

async function scrollBottom() {
  await nextTick()
  if (chatListRef.value) {
    chatListRef.value.scrollTop = chatListRef.value.scrollHeight
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
  const q = String(text || '').trim()
  if (!q) return
  showSkillPanel.value = false
  aiThinking.value = true
  try {
    const hadContext = hasContext.value
    const msg = await chatStore.send(q)
    await scrollBottom()
    if (!hadContext && msg?.meta?.kind === 'intent') {
      const decision = msg.meta.decision
      if (decision?.status === 'resolved') {
        handleResolvedIntent(decision.intent, q)
      }
    }
  } catch {
    showToast(hasContext.value ? '追问未成功，请查看对话说明' : '意图识别未成功，请查看对话说明')
  } finally {
    aiThinking.value = false
    await scrollBottom()
  }
}

function onClarifyPick(opt) {
  if (!opt?.intent || aiThinking.value) return
  const label = opt.label || opt.intent
  chatStore._pushUser(label)
  if (handleResolvedIntent(opt.intent, label)) return
  showToast('请从对应入口继续')
}

function onSkill(key) {
  showSkillPanel.value = false
  if (key === 'paste') {
    pasteText.value = ''
    showPasteSheet.value = true
    return
  }
  if (key === 'upload') {
    fileInputRef.value?.click()
    return
  }
  if (key === 'analyze') {
    runAnalyze()
    return
  }
  if (key === 'clear') {
    if (!chatStore.hasMaterials && !chatStore.contextText) {
      showToast('当前没有材料')
      return
    }
    if (typeof chatStore.clearMaterials === 'function') {
      chatStore.clearMaterials()
    } else {
      // Pinia 热更新偶发丢 action：降级清状态
      chatStore.$patch({
        materials: [],
        contextFindings: [],
        pendingQuestions: [],
        contextText: '',
        lastTaskId: '',
      })
      chatStore.messages.push({
        id: 'a_' + Date.now(),
        role: 'ai',
        content: '已清空会话材料。可用「+」重新粘贴或上传。',
        time: Date.now(),
        meta: { kind: 'materials_cleared' },
      })
      if (typeof chatStore._persist === 'function') chatStore._persist()
    }
    showToast('已清空材料')
  }
}

function confirmPaste() {
  const text = pasteText.value.trim()
  if (!text) {
    showToast('请先粘贴条款文本')
    return
  }
  try {
    chatStore.addMaterial({ kind: 'paste', name: '粘贴条款', text })
    showPasteSheet.value = false
    pasteText.value = ''
    scrollBottom()
  } catch {
    showToast('加入材料失败')
  }
}

async function onFilePicked(ev) {
  const files = Array.from(ev?.target?.files || [])
  if (fileInputRef.value) fileInputRef.value.value = ''
  if (!files.length) return
  aiThinking.value = true
  try {
    await chatStore.addUploadFiles(files)
    await scrollBottom()
  } catch (e) {
    if (e?.code !== 'EXTRACT_FAILED' && e?.code !== 'EMPTY_MATERIAL') {
      showToast('上传解析失败')
    }
  } finally {
    aiThinking.value = false
    await scrollBottom()
  }
}

async function runAnalyze() {
  if (aiThinking.value) return
  aiThinking.value = true
  try {
    const result = await chatStore.analyzeMaterials(taskStore.productHint || 'auto')
    if (result?.taskId) {
      taskStore.setTask(result.taskId, result.data?.task_status || 'completed')
    }
    await scrollBottom()
  } catch (e) {
    if (e?.code === 'NO_MATERIAL') {
      showToast('请先添加材料')
      showSkillPanel.value = true
    } else {
      showToast('分析未成功，请查看对话说明')
    }
  } finally {
    aiThinking.value = false
    await scrollBottom()
  }
}

function goHome() {
  router.push({ name: 'home' })
}

function goReport(taskId) {
  if (!taskId) return
  router.push({ name: 'report', params: { taskId } })
}

function openSupplement() {
  showSkillPanel.value = false
  pasteText.value = ''
  showPasteSheet.value = true
  showToast('把缺的条款粘贴进来，加入会话后再问')
}

function clearContext() {
  if (typeof chatStore.clearMaterials === 'function') {
    chatStore.clearMaterials()
  } else {
    chatStore.$patch({
      materials: [],
      contextFindings: [],
      pendingQuestions: [],
      contextText: '',
      lastTaskId: '',
    })
  }
  showToast('已解除关联')
}

async function confirmClear() {
  try {
    await showConfirmDialog({
      title: '清空对话记录？',
      message: '将同时清空会话材料，此操作无法撤销',
    })
    chatStore.clear()
    chatStore.ensureGuideWelcome()
    showToast('已清空')
  } catch {
    /* cancel */
  }
}

onMounted(() => {
  taskStore.restoreFromStorage()
  chatStore.restore()
  chatStore.ensureGuideWelcome()
  scrollBottom()
})

watch(messages, () => scrollBottom(), { deep: true })
</script>

<style scoped>
.chat-page {
  height: 100vh;
  height: 100dvh;
  max-height: 100vh;
  max-height: 100dvh;
  min-height: 0 !important;
  padding-bottom: calc(72px + env(safe-area-inset-bottom));
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--crusher-bg);
  box-sizing: border-box;
}
.chat-page.skill-open {
  padding-bottom: calc(168px + env(safe-area-inset-bottom));
}
.chat-page :deep(.van-nav-bar) {
  flex: 0 0 auto;
}

.chat-top {
  flex: 0 0 auto;
  z-index: 5;
  background: var(--crusher-bg);
  box-shadow: 0 1px 0 var(--crusher-border);
}

.context-card {
  margin: 8px 12px 10px;
  padding: 10px 12px;
  background: var(--crusher-primary-light);
  border: 1px solid var(--crusher-border);
  border-radius: 12px;
}
.ctx-head {
  display: flex;
  align-items: center;
  gap: 8px;
}
.ctx-ico {
  width: 32px; height: 32px; border-radius: 9px;
  background: var(--crusher-card-bg);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.ctx-info { flex: 1; min-width: 0; }
.ctx-title { font-size: 12px; font-weight: 600; color: var(--crusher-primary); margin-bottom: 1px; }
.ctx-preview { font-size: 12px; color: var(--crusher-ink-2); }
.ctx-findings { margin-top: 6px; }

.chat-list {
  flex: 1 1 auto;
  min-height: 0;
  padding: 10px 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow-x: hidden;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
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

.intent-options {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}

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
  padding: 4px 12px 2px;
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
.chat-quick-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.composer {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  z-index: 100;
  background: var(--crusher-card-bg);
  border: 1px solid var(--crusher-border);
  border-bottom: none;
  border-radius: 16px 16px 0 0;
  padding: 10px 12px calc(10px + env(safe-area-inset-bottom));
  box-shadow: 0 -4px 20px rgba(15, 23, 42, 0.06);
}
:global(.van-theme-dark) .composer {
  box-shadow: 0 -4px 20px rgba(0, 0, 0, 0.35);
}
.skill-panel {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 6px;
  padding: 2px 0 12px;
  margin-bottom: 8px;
  border-bottom: 1px solid var(--crusher-border);
}
.skill-item {
  border: none;
  background: transparent;
  padding: 4px 0;
  cursor: pointer;
  color: var(--crusher-ink);
}
.skill-item:disabled { opacity: 0.45; }
.skill-ico {
  width: 42px;
  height: 42px;
  margin: 0 auto 4px;
  border-radius: 12px;
  background: var(--crusher-surface-2);
  color: var(--crusher-ink-2);
  display: flex;
  align-items: center;
  justify-content: center;
}
.skill-label {
  font-size: 11px;
  text-align: center;
  color: var(--crusher-ink-3);
  line-height: 1.2;
}
.composer-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.icon-btn {
  width: 36px;
  height: 36px;
  border: none;
  background: transparent;
  color: var(--crusher-ink-2);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  cursor: pointer;
  border-radius: 12px;
}
.icon-btn.active,
.icon-btn.send:not(:disabled) {
  color: var(--crusher-primary);
}
.icon-btn:disabled {
  color: var(--crusher-ink-3);
  opacity: 0.5;
  cursor: not-allowed;
}
.composer-field {
  flex: 1;
  min-width: 0;
  padding: 0 !important;
  background: transparent !important;
  border-radius: 12px;
}
.composer-field :deep(.van-cell) {
  padding: 8px 10px !important;
  background: transparent !important;
  border-radius: 12px;
  align-items: center;
}
.composer-field :deep(.van-field__body) {
  background: transparent !important;
  min-height: 22px;
}
.composer-field :deep(.van-field__control) {
  padding: 0 !important;
  margin: 0 !important;
  font-size: 15px !important;
  line-height: 22px !important;
  max-height: 88px;
  color: var(--crusher-ink) !important;
  caret-color: var(--crusher-primary);
}
.composer-field :deep(textarea.van-field__control) {
  padding: 0 !important;
  box-sizing: border-box;
}
.hidden-file {
  display: none;
}
.paste-sheet {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 16px 16px 12px;
  box-sizing: border-box;
  overflow: hidden;
}
.paste-head {
  flex: 0 0 auto;
}
.paste-sheet h3 {
  margin: 0 0 6px;
  font-size: 17px;
}
.paste-hint {
  margin: 0 0 10px;
  font-size: 13px;
  color: var(--crusher-ink-3);
}
.paste-body {
  flex: 1 1 auto;
  min-height: 120px;
  overflow: hidden;
}
.paste-field {
  height: 100%;
  background: var(--crusher-card-bg, #fff);
  border: 1px solid var(--crusher-line, rgba(0, 0, 0, 0.08));
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.paste-field :deep(.van-cell__value) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.paste-field :deep(.van-field__body) {
  flex: 1;
  min-height: 0;
  align-items: stretch;
}
.paste-field :deep(textarea.van-field__control) {
  height: 100% !important;
  max-height: none !important;
  overflow-y: auto !important;
  box-sizing: border-box;
  -webkit-overflow-scrolling: touch;
}
.paste-field :deep(.van-field__word-limit) {
  flex: 0 0 auto;
  padding: 4px 8px 8px;
}
.paste-actions {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  padding-top: 12px;
}
.touch-btn {
  min-height: 44px;
}
</style>
