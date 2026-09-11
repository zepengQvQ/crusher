<template>
  <div class="page">
    <div class="hero-header">
      <div class="hero-top">
        <div class="brand">
          <div class="brand-logo">
            <van-icon name="shield-o" size="28" />
          </div>
          <div class="brand-text">
            <div class="brand-name">金融话术粉碎机</div>
            <div class="brand-sub">识破套路 · 读懂条款 · 守护钱包</div>
          </div>
        </div>
        <div class="header-icons">
          <van-icon
            name="bulb-o"
            size="22"
            class="h-icon"
            @click="themeStore.toggle()"
          />
        </div>
      </div>

      <van-swipe class="hero-swipe" :autoplay="4500" indicator-color="#ffffff80" lazy-render>
        <van-swipe-item v-for="b in banners" :key="b.id" class="s-item" @click="onBanner(b)">
          <div class="banner-inner" :class="b.type">
            <div class="banner-text">
              <div class="banner-tag">{{ b.tag }}</div>
              <div class="banner-title">{{ b.title }}</div>
              <div class="banner-desc">{{ b.desc }}</div>
            </div>
            <div class="banner-ico">
              <van-icon :name="b.icon" size="54" />
            </div>
          </div>
        </van-swipe-item>
      </van-swipe>
    </div>

    <div class="block">
      <div class="block-title"><van-icon name="apps-o" /> 快捷入口</div>
      <div class="entry-grid">
        <div v-for="e in entries" :key="e.key" class="grid-entry" @click="go(e)">
          <div class="grid-entry-icon" :class="e.cls">
            <van-icon :name="e.icon" />
          </div>
          <div class="grid-entry-text">{{ e.label }}</div>
        </div>
      </div>
    </div>

    <div class="block">
      <div class="section-header">
        <h3><van-icon name="star-o" style="color:#1989fa;margin-right:4px" /> 快速分析示例</h3>
        <span class="more" @click="goAnalyze()">全部 →</span>
      </div>
      <div class="demo-list">
        <div v-for="ex in EXAMPLES" :key="ex.id" class="demo-card" @click="runDemo(ex)">
          <div class="demo-card-ico" :class="ex.cls">
            <van-icon :name="ex.icon" size="22" />
          </div>
          <div class="demo-card-body">
            <div class="demo-card-title">{{ ex.name }}</div>
            <div class="demo-card-preview">{{ ex.preview }}</div>
            <div class="demo-card-tags">
              <van-tag v-for="t in ex.tags" :key="t" type="primary" plain size="medium" style="margin-right:4px">{{ t }}</van-tag>
            </div>
          </div>
          <van-icon name="arrow" class="demo-arrow" />
        </div>
      </div>
    </div>

    <div class="block" v-if="historyStore.hasHistory">
      <div class="section-header">
        <h3><van-icon name="clock-o" style="color:#1989fa;margin-right:4px" /> 我的分析记录</h3>
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
            <div class="finding-count">
              <span v-if="r.findingCount > 0" class="risk-count-badge" :class="r.findingCount >= 3 ? 'high' : 'mid'">
                <van-icon name="warning-o" size="12" /> {{ r.findingCount }} 风险
              </span>
              <span v-else class="risk-count-badge low">
                <van-icon name="passed" size="12" /> 安全
              </span>
            </div>
          </template>
        </van-cell>
      </van-cell-group>
    </div>

    <div class="block">
      <div class="block-title"><van-icon name="info-o" /> 反诈小课堂</div>
      <div class="tips-list">
        <div v-for="(tip, i) in tips" :key="i" class="tip-item">
          <div class="tip-num">{{ i + 1 }}</div>
          <div class="tip-text">
            <div class="tip-title">{{ tip.title }}</div>
            <div class="tip-desc">{{ tip.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="footer-safe">
      <van-icon name="shield-o" size="14" style="color:#9ca3af" />
      <span>所有分析均在本地服务器完成，密钥不出本机</span>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { showToast, showConfirmDialog } from 'vant'
import { createAnalysis } from '../api/client'
import { EXAMPLES as RAW_EXAMPLES } from '../data/examples'
import { useTaskStore } from '../stores/task'
import { useHistoryStore } from '../stores/history'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const store = useTaskStore()
const historyStore = useHistoryStore()
const themeStore = useThemeStore()

const banners = [
  {
    id: 1,
    tag: '热门',
    title: '结构性存款避坑指南',
    desc: '4.8%的收益真能拿到吗？一图看懂',
    icon: 'chart-trending-o',
    type: 'primary',
    demo: 'structured_deposit',
  },
  {
    id: 2,
    tag: '警惕',
    title: '消费贷罚息陷阱',
    desc: '日息0.05%看似低，实际年化超18%？',
    icon: 'warn-o',
    type: 'warning',
    demo: 'loan',
  },
  {
    id: 3,
    tag: '实用',
    title: '两份条款对比',
    desc: '同款产品不同银行，秒选更划算的',
    icon: 'exchange',
    type: 'success',
    goto: 'compare',
  },
]

const entries = [
  { key: 'paste', label: '粘贴分析', icon: 'edit', cls: 'blue', go: 'input' },
  { key: 'upload', label: '上传解析', icon: 'photograph', cls: 'orange', go: 'upload' },
  { key: 'dual', label: '销售对照', icon: 'exchange', cls: 'pink', go: 'dual' },
  { key: 'compare', label: '条款对比', icon: 'balance-list-o', cls: 'purple', go: 'compare' },
]

const EXAMPLES = RAW_EXAMPLES.map((e) => ({
  ...e,
  preview: e.text.slice(0, 48) + '…',
  tags:
    e.id === 'structured_deposit'
      ? ['收益浮动', '流动性弱']
      : e.id === 'loan'
        ? ['罚息', '违约金']
        : ['零风险'],
  icon:
    e.id === 'structured_deposit'
      ? 'gold-coin-o'
      : e.id === 'loan'
        ? 'cash-o'
        : 'certificate',
  cls:
    e.id === 'structured_deposit'
      ? 'blue'
      : e.id === 'loan'
        ? 'orange'
        : 'green',
}))

const tips = [
  {
    title: '警惕「保本高息」话术',
    desc: '监管规定：除存款/国债外不得承诺保本。高收益必然伴随高风险。',
  },
  {
    title: '留意「小字条款」',
    desc: '提前赎回费、违约金、等待期常藏在角落。先看「责任免除/违约」章节。',
  },
  {
    title: '拒绝「今天不买就没了」',
    desc: '正规金融产品不会逼单。遇到限时/限额话术，先离开冷静1天再说。',
  },
]

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

function goAnalyze() {
  router.push({ name: 'input' })
}

function go(e) {
  if (e.go === 'input') return router.push({ name: 'input' })
  if (e.go === 'upload') return router.push({ name: 'upload' })
  if (e.go === 'dual') return router.push({ name: 'dual-input' })
  if (e.go === 'compare') return router.push({ name: 'compare' })
}

function onBanner(b) {
  if (b.demo) {
    const ex = EXAMPLES.find((x) => x.id === b.demo)
    if (ex) return runDemo(ex)
  }
  if (b.goto === 'compare') return router.push({ name: 'compare' })
}

async function runDemo(ex) {
  store.setDraft(ex.text, ex.id === 'safe' ? 'auto' : ex.id)
  try {
    const res = await createAnalysis(ex.text, { productHint: ex.id === 'safe' ? 'auto' : ex.id })
    store.setTask(res.task_id, res.task_status)
    router.push({ name: 'status', params: { taskId: res.task_id } })
  } catch (e) {
    showToast('提交失败，请检查后端是否启动')
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
.hero-header {
  background:
    url('../assets/hero-bg.png') center top / cover no-repeat,
    linear-gradient(180deg, #0b3d91 0%, #0d7ae8 32%, #1989fa 62%, #4facfe 88%, var(--crusher-bg) 100%);
  padding: 16px 16px 24px;
  margin-bottom: 12px;
}
.hero-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}
.brand { display: flex; align-items: center; gap: 10px; }
.brand-logo {
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: rgba(255,255,255,0.25);
  display: flex; align-items: center; justify-content: center;
  color: #fff;
  backdrop-filter: blur(8px);
}
.brand-name {
  color: #fff;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.brand-sub {
  color: rgba(255,255,255,0.85);
  font-size: 12px;
  margin-top: 2px;
}
.h-icon { color: #fff; }

.hero-swipe {
  height: 118px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
}
.s-item { height: 100%; }
.banner-inner {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  color: #fff;
  border-radius: 16px;
}
.banner-inner.primary {
  background:
    url('../assets/banner-bg-primary.png') center / cover no-repeat,
    linear-gradient(135deg, #0b3d91 0%, #0d7ae8 45%, #1989fa 78%, #4facfe 100%);
}
.banner-inner.warning {
  background:
    url('../assets/banner-bg-warning.png') center / cover no-repeat,
    linear-gradient(135deg, #c2410c 0%, #ea580c 45%, #f56723 78%, #ff976a 100%);
}
.banner-inner.success {
  background:
    url('../assets/banner-bg-success.png') center / cover no-repeat,
    linear-gradient(135deg, #047857 0%, #059669 45%, #07c160 78%, #3dd68c 100%);
}
.banner-text { flex: 1; min-width: 0; }
.banner-tag {
  display: inline-block;
  padding: 2px 8px;
  background: rgba(255,255,255,0.25);
  border-radius: 999px;
  font-size: 11px;
  margin-bottom: 6px;
  backdrop-filter: blur(4px);
}
.banner-title { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.banner-desc { font-size: 12px; opacity: 0.9; }
.banner-ico { opacity: 0.9; margin-left: 12px; }

.demo-list { display: flex; flex-direction: column; gap: 10px; }
.demo-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--crusher-surface);
  border-radius: 12px;
  border: 1px solid var(--crusher-border);
  box-shadow: var(--crusher-shadow-sm);
  transition: all 0.15s;
}
.demo-card:active { background: var(--crusher-surface-2); transform: scale(0.985); }
.demo-card-ico {
  width: 42px; height: 42px; border-radius: 12px;
  display: flex; align-items: center; justify-content: center;
  color: #fff; flex-shrink: 0;
}
.demo-card-ico.blue { background: var(--crusher-grad-primary); }
.demo-card-ico.orange { background: var(--crusher-grad-warning); }
.demo-card-ico.green { background: var(--crusher-grad-success); }
.demo-card-body { flex: 1; min-width: 0; }
.demo-card-title { font-size: 15px; font-weight: 600; margin-bottom: 4px; }
.demo-card-preview {
  font-size: 12px;
  color: var(--crusher-ink-3);
  margin-bottom: 6px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.demo-card-tags { line-height: 1.6; }
.demo-arrow { color: var(--crusher-ink-3); flex-shrink: 0; }

.tips-list { display: flex; flex-direction: column; gap: 12px; }
.tip-item {
  display: flex;
  gap: 10px;
  padding: 12px;
  background: var(--crusher-gold-light);
  border-radius: 12px;
  border: 1px solid var(--crusher-border);
}
.tip-num {
  width: 24px; height: 24px; border-radius: 50%;
  background: var(--crusher-grad-warning);
  color: #fff; font-weight: 700; font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.tip-text { flex: 1; min-width: 0; }
.tip-title { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
.tip-desc { font-size: 12px; color: var(--crusher-ink-2); line-height: 1.5; }

.footer-safe {
  text-align: center;
  color: var(--crusher-ink-3);
  font-size: 12px;
  padding: 20px 16px 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}

.finding-count { min-width: 80px; text-align: right; }

.entry-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 4px;
}
.entry-grid .grid-entry {
  padding: 10px 4px;
}
.entry-grid .grid-entry-icon {
  width: 46px;
  height: 46px;
  border-radius: 13px;
  font-size: 22px;
  margin-bottom: 7px;
}
.entry-grid .grid-entry-text {
  width: 100%;
  text-align: center;
  white-space: nowrap;
  font-size: 12px;
  line-height: 1.2;
}
</style>
