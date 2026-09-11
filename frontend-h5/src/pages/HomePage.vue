<template>
  <div class="page home-page">
    <div class="hero-header">
      <div class="hero-top">
        <div class="brand">
          <div class="brand-logo">
            <van-icon name="shield-o" size="26" />
          </div>
          <div class="brand-text">
            <div class="brand-name">金融话术粉碎机</div>
            <div class="brand-sub">识破套路 · 读懂条款 · 守护钱包</div>
          </div>
        </div>
        <van-icon
          name="bulb-o"
          size="22"
          class="h-icon"
          @click="themeStore.toggle()"
        />
      </div>

      <van-swipe class="hero-swipe" :autoplay="4800" indicator-color="var(--crusher-primary)" lazy-render>
        <van-swipe-item v-for="b in banners" :key="b.id" class="s-item" @click="onBanner(b)">
          <div class="banner-inner">
            <div class="banner-text">
              <div class="banner-tag" :class="b.type">{{ b.tag }}</div>
              <div class="banner-title">{{ b.title }}</div>
              <div class="banner-desc">{{ b.desc }}</div>
            </div>
            <div class="banner-ico" :class="b.type">
              <van-icon :name="b.icon" size="28" />
            </div>
          </div>
        </van-swipe-item>
      </van-swipe>

      <button type="button" class="hero-cta" @click="goChat">
        <van-icon name="chat-o" size="18" />
        <span>开始对话分析</span>
        <van-icon name="arrow" size="14" />
      </button>
    </div>

    <div class="block block-tight">
      <div class="block-title">更多能力</div>
      <div class="entry-row">
        <button
          v-for="e in entries"
          :key="e.key"
          type="button"
          class="entry-chip"
          :class="e.cls"
          @click="go(e)"
        >
          <van-icon :name="e.icon" size="18" />
          <span>{{ e.label }}</span>
        </button>
      </div>
    </div>

    <div class="block block-tight">
      <div class="section-header">
        <h3>示例条款</h3>
        <span class="more" @click="goChat">去对话 →</span>
      </div>
      <div class="demo-list">
        <button
          v-for="ex in EXAMPLES"
          :key="ex.id"
          type="button"
          class="demo-card"
          @click="runDemo(ex)"
        >
          <div class="demo-card-ico" :class="ex.cls">
            <van-icon :name="ex.icon" size="20" />
          </div>
          <div class="demo-card-body">
            <div class="demo-card-title">{{ ex.name }}</div>
            <div class="demo-card-preview">{{ ex.preview }}</div>
          </div>
          <van-icon name="arrow" class="demo-arrow" />
        </button>
      </div>
    </div>

    <div class="block block-tight" v-if="historyStore.hasHistory">
      <div class="section-header">
        <h3>最近分析</h3>
        <span class="more" @click="clearHistory()">清空</span>
      </div>
      <van-cell-group :border="false" style="background:transparent">
        <van-cell
          v-for="r in historyStore.list.slice(0, 5)"
          :key="r.taskId"
          is-link
          :title="r.title"
          :label="formatTime(r.createdAt)"
          @click="goReport(r.taskId)"
        >
          <template #value>
            <span
              v-if="r.findingCount > 0"
              class="risk-count-badge"
              :class="r.findingCount >= 3 ? 'high' : 'mid'"
            >
              {{ r.findingCount }} 风险
            </span>
            <span v-else class="risk-count-badge low">安全</span>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <div class="footer-safe">
      <van-icon name="shield-o" size="13" />
      <span>分析在本机完成，密钥不出本机</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { EXAMPLES as RAW_EXAMPLES } from '../data/examples'
import { useTaskStore } from '../stores/task'
import { useHistoryStore } from '../stores/history'
import { useThemeStore } from '../stores/theme'
import { useChatStore } from '../stores/chat'

const router = useRouter()
const store = useTaskStore()
const historyStore = useHistoryStore()
const themeStore = useThemeStore()
const chatStore = useChatStore()

const banners = [
  {
    id: 1,
    tag: '热门',
    title: '结构性存款避坑指南',
    desc: '4.8% 的收益真能拿到吗？',
    icon: 'chart-trending-o',
    type: 'primary',
    demo: 'structured_deposit',
  },
  {
    id: 2,
    tag: '警惕',
    title: '消费贷罚息陷阱',
    desc: '日息 0.05% 看似低，年化可能很高',
    icon: 'warn-o',
    type: 'warning',
    demo: 'loan',
  },
  {
    id: 3,
    tag: '实用',
    title: '两份条款对比',
    desc: '同款产品不同银行，秒选更划算',
    icon: 'exchange',
    type: 'success',
    goto: 'compare',
  },
  {
    id: 4,
    tag: '反诈',
    title: '警惕「保本高息」',
    desc: '除存款/国债外不得承诺保本',
    icon: 'shield-o',
    type: 'tip',
  },
  {
    id: 5,
    tag: '反诈',
    title: '留意「小字条款」',
    desc: '赎回费、违约金常藏在免除章节',
    icon: 'eye-o',
    type: 'tip',
  },
  {
    id: 6,
    tag: '反诈',
    title: '拒绝逼单话术',
    desc: '正规产品不会「今天不买就没了」',
    icon: 'clock-o',
    type: 'tip',
  },
]

const entries = [
  { key: 'dual', label: '销售对照', icon: 'exchange', cls: 'pink', go: 'dual' },
  { key: 'compare', label: '条款对比', icon: 'balance-list-o', cls: 'purple', go: 'compare' },
]

const EXAMPLES = RAW_EXAMPLES.map((e) => ({
  ...e,
  preview: e.text.slice(0, 42) + '…',
  icon:
    e.id === 'structured_deposit' ? 'gold-coin-o' : e.id === 'loan' ? 'cash-o' : 'certificate',
  cls: e.id === 'structured_deposit' ? 'blue' : e.id === 'loan' ? 'orange' : 'green',
}))

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  const now = new Date()
  const diff = (now - d) / 1000
  if (diff < 60) return '刚刚'
  if (diff < 3600) return Math.floor(diff / 60) + '分钟前'
  if (diff < 86400) return Math.floor(diff / 3600) + '小时前'
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function goChat() {
  router.push({ name: 'chat' })
}

function go(e) {
  if (e.go === 'dual') return router.push({ name: 'dual-input' })
  if (e.go === 'compare') return router.push({ name: 'compare' })
}

function onBanner(b) {
  if (b.demo) {
    const ex = EXAMPLES.find((x) => x.id === b.demo)
    if (ex) return runDemo(ex)
  }
  if (b.goto === 'compare') return router.push({ name: 'compare' })
  if (b.type === 'tip') {
    showToast({ message: `${b.title}\n${b.desc}`, duration: 3200 })
  }
}

function runDemo(ex) {
  chatStore.restore()
  try {
    chatStore.addMaterial({
      kind: 'paste',
      name: ex.name,
      text: ex.text,
    })
    store.setDraft(ex.text, ex.id === 'safe' ? 'auto' : ex.id)
    router.push({ name: 'chat' })
  } catch {
    showToast('加入会话失败，请重试')
  }
}

function goReport(taskId) {
  router.push({ name: 'report', params: { taskId } })
}

async function clearHistory() {
  try {
    await showConfirmDialog({
      title: '确认清空历史记录？',
      message: '此操作无法撤销',
    })
    historyStore.clear()
    showToast('已清空')
  } catch {
    /* cancel */
  }
}

onMounted(() => {
  themeStore.restore()
  store.restoreFromStorage()
  historyStore.restore()
})
</script>

<style scoped>
.home-page {
  padding-bottom: calc(28px + env(safe-area-inset-bottom));
}

.hero-header {
  background:
    url('../assets/hero-bg.png') center top / cover no-repeat,
    linear-gradient(180deg, #0b3d91 0%, #0d7ae8 36%, #1989fa 68%, var(--crusher-bg) 100%);
  padding: 14px 16px 8px;
  margin-bottom: 4px;
}
:global(.van-theme-dark) .hero-header {
  background:
    linear-gradient(180deg, #071528 0%, #0b2748 42%, #0f172a 72%, var(--crusher-bg) 100%);
}
:global(.van-theme-dark) .hero-cta:active {
  opacity: 0.92;
}
.hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-logo {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(255,255,255,0.22);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
}
.brand-name {
  color: #fff;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: 0.3px;
}
.brand-sub {
  color: rgba(255,255,255,0.82);
  font-size: 12px;
  margin-top: 2px;
}
.h-icon { color: #fff; padding: 4px; }

.hero-swipe {
  height: 104px;
  border-radius: 14px;
  overflow: hidden;
}
.s-item { height: 100%; }
.banner-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  color: var(--crusher-ink);
  background: var(--crusher-card-bg);
  border: 1px solid var(--crusher-border);
  box-shadow: var(--crusher-shadow-md);
}
.banner-text { flex: 1; min-width: 0; }
.banner-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 5px;
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
}
.banner-tag.warning {
  background: var(--crusher-warning-light);
  color: var(--crusher-warning);
}
.banner-tag.success {
  background: var(--crusher-success-light);
  color: var(--crusher-success);
}
.banner-tag.tip,
.banner-tag.primary {
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
}
.banner-title {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 3px;
  color: var(--crusher-ink);
}
.banner-desc {
  font-size: 12px;
  color: var(--crusher-ink-2);
  line-height: 1.35;
}
.banner-ico {
  width: 44px;
  height: 44px;
  border-radius: 12px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
}
.banner-ico.warning {
  background: var(--crusher-warning-light);
  color: var(--crusher-warning);
}
.banner-ico.success {
  background: var(--crusher-success-light);
  color: var(--crusher-success);
}
.banner-ico.tip,
.banner-ico.primary {
  background: var(--crusher-primary-light);
  color: var(--crusher-primary);
}

.hero-cta {
  margin-top: 12px;
  width: 100%;
  border: 1px solid var(--crusher-border);
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: var(--crusher-card-bg);
  color: var(--crusher-primary);
  font-size: 15px;
  font-weight: 600;
  box-shadow: var(--crusher-shadow-md);
  cursor: pointer;
}
.hero-cta:active { transform: scale(0.985); opacity: 0.96; }

.block-tight {
  margin: 10px 12px;
  padding: 14px;
}
.block-tight .block-title {
  margin-bottom: 10px;
  font-size: 15px;
}
.section-header {
  margin-bottom: 10px;
}
.section-header h3 {
  font-size: 15px;
  font-weight: 600;
}

.entry-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}
.entry-chip {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 12px 10px;
  border-radius: 12px;
  border: 1px solid var(--crusher-border);
  background: var(--crusher-surface);
  color: var(--crusher-ink);
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.entry-chip.pink { color: var(--crusher-pink); background: var(--crusher-pink-light); border-color: transparent; }
.entry-chip.purple { color: var(--crusher-purple); background: var(--crusher-purple-light); border-color: transparent; }
.entry-chip:active { transform: scale(0.98); }

.demo-list { display: flex; flex-direction: column; gap: 8px; }
.demo-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  background: var(--crusher-surface);
  border-radius: 10px;
  border: 1px solid var(--crusher-border);
  text-align: left;
  color: inherit;
  cursor: pointer;
  width: 100%;
}
.demo-card:active { background: var(--crusher-surface-2); }
.demo-card-ico {
  width: 38px; height: 38px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
}
.demo-card-ico.blue { background: var(--crusher-grad-primary); }
.demo-card-ico.orange { background: var(--crusher-grad-warning); }
.demo-card-ico.green { background: var(--crusher-grad-success); }
.demo-card-body { flex: 1; min-width: 0; }
.demo-card-title { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.demo-card-preview {
  font-size: 12px;
  color: var(--crusher-ink-3);
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.demo-arrow { color: var(--crusher-ink-3); flex-shrink: 0; }

.footer-safe {
  text-align: center;
  color: var(--crusher-ink-3);
  font-size: 12px;
  padding: 16px 16px 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
</style>
