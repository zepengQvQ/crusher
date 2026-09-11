<template>
  <div class="page compare-page">
    <van-nav-bar title="条款对比" left-arrow @click-left="$router.back()">
      <template #right>
        <van-icon
          name="exchange"
          size="18"
          style="color:#1989fa"
          @click="swapText"
        />
      </template>
    </van-nav-bar>

    <div class="block">
      <div class="block-title"><van-icon name="balance-list-o" /> 输入两份条款</div>
      <div class="compare-row">
        <div class="compare-col">
          <div class="compare-col-title a">{{ compareStore.titleA }}</div>
          <van-field
            v-model="textA"
            rows="7"
            autosize
            type="textarea"
            maxlength="4000"
            :placeholder="`粘贴条款 A（如：银行A结构性存款）`"
            @update:model-value="(v) => compareStore.setText('A', v)"
          />
          <div class="col-actions">
            <van-button
              size="small"
              plain
              hairline
              v-for="ex in exA"
              :key="ex.id"
              @click="fill('A', ex.id)"
              style="margin-top:6px"
            >
              <van-icon name="copy-o" size="12" style="margin-right:3px" />{{ ex.name }}
            </van-button>
            <van-button size="small" plain style="margin-top:6px" @click="clear('A')">
              <van-icon name="delete-o" size="12" style="margin-right:3px" />清空
            </van-button>
          </div>
        </div>

        <div class="vs-divider">
          <div class="vs-circle">VS</div>
        </div>

        <div class="compare-col">
          <div class="compare-col-title b">{{ compareStore.titleB }}</div>
          <van-field
            v-model="textB"
            rows="7"
            autosize
            type="textarea"
            maxlength="4000"
            :placeholder="`粘贴条款 B（如：银行B同类产品）`"
            @update:model-value="(v) => compareStore.setText('B', v)"
          />
          <div class="col-actions">
            <van-button
              size="small"
              plain
              hairline
              type="warning"
              v-for="ex in exB"
              :key="ex.id"
              @click="fill('B', ex.id)"
              style="margin-top:6px"
            >
              <van-icon name="copy-o" size="12" style="margin-right:3px" />{{ ex.name }}
            </van-button>
            <van-button size="small" plain style="margin-top:6px" @click="clear('B')">
              <van-icon name="delete-o" size="12" style="margin-right:3px" />清空
            </van-button>
          </div>
        </div>
      </div>
    </div>

    <div class="block" v-if="compareStore.canCompare">
      <div class="result-card" :class="summary.winner">
        <div class="result-head">
          <van-icon :name="resultIcon" size="26" />
          <div class="result-text">
            <div class="result-title">{{ resultTitle }}</div>
            <div class="result-desc">{{ summary.reason }}</div>
          </div>
        </div>
        <div class="result-grid">
          <div class="result-cell a">
            <div class="cell-label">条款 A</div>
            <div class="cell-score dashboard-number">{{ summary.aSeverityScore }}</div>
            <div class="cell-meta">{{ summary.aFindingCount }} 条风险</div>
            <van-progress
              :percentage="Math.min(100, summary.aSeverityScore * 14)"
              color="#1989fa"
              :stroke-width="6"
              :show-pivot="false"
              style="margin-top:4px"
            />
          </div>
          <div class="cell-vs">
            <van-icon name="arrow" size="20" style="color:#9ca3af" />
          </div>
          <div class="result-cell b">
            <div class="cell-label">条款 B</div>
            <div class="cell-score dashboard-number">{{ summary.bSeverityScore }}</div>
            <div class="cell-meta">{{ summary.bFindingCount }} 条风险</div>
            <van-progress
              :percentage="Math.min(100, summary.bSeverityScore * 14)"
              color="#ff976a"
              :stroke-width="6"
              :show-pivot="false"
              style="margin-top:4px"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="block" v-if="compareStore.canCompare">
      <div class="block-title"><van-icon name="warning-o" /> 风险对比详情</div>

      <van-tabs v-model:active="activeTab" shrink line-width="3">
        <van-tab title="仅在 A">
          <div class="diff-list">
            <p v-if="!summary.uniqueInA.length" class="empty-findings">
              A 条款无独有风险
            </p>
            <FindingCard
              v-for="(f, i) in summary.uniqueInA"
              :key="'ua' + i"
              :item="f"
              side="A"
            />
          </div>
        </van-tab>
        <van-tab title="仅在 B">
          <div class="diff-list">
            <p v-if="!summary.uniqueInB.length" class="empty-findings">
              B 条款无独有风险
            </p>
            <FindingCard
              v-for="(f, i) in summary.uniqueInB"
              :key="'ub' + i"
              :item="f"
              side="B"
            />
          </div>
        </van-tab>
        <van-tab title="全部 A">
          <div class="diff-list">
            <FindingCard
              v-for="(f, i) in resultA.findings"
              :key="'fa' + i"
              :item="f"
              side="A"
            />
          </div>
        </van-tab>
        <van-tab title="全部 B">
          <div class="diff-list">
            <FindingCard
              v-for="(f, i) in resultB.findings"
              :key="'fb' + i"
              :item="f"
              :side="'B'"
            />
          </div>
        </van-tab>
      </van-tabs>
    </div>

    <div class="block" v-if="compareStore.canCompare">
      <div class="block-title"><van-icon name="orders-o" /> 参数对比</div>
      <van-cell-group :border="false">
        <van-cell title="条款 A 提取参数">
          <template #value>
            <span v-if="!resultA.params.length" style="color:#9ca3af">未识别</span>
          </template>
        </van-cell>
        <van-cell
          v-for="(p, i) in resultA.params"
          :key="'pa' + i"
          :title="p.label"
          :value="p.value"
          size="medium"
          style="padding-left: 32px"
        />
        <van-divider style="margin: 4px 0" />
        <van-cell title="条款 B 提取参数">
          <template #value>
            <span v-if="!resultB.params.length" style="color:#9ca3af">未识别</span>
          </template>
        </van-cell>
        <van-cell
          v-for="(p, i) in resultB.params"
          :key="'pb' + i"
          :title="p.label"
          :value="p.value"
          size="medium"
          style="padding-left: 32px"
        />
      </van-cell-group>
    </div>

    <div class="bottom-bar">
      <van-button
        block
        type="primary"
        round
        :disabled="!compareStore.canCompare"
        @click="scrollToResult"
      >
        <template #icon><van-icon name="fire-o" /></template>
        {{ compareStore.canCompare ? '查看对比结论' : '请先输入两份条款' }}
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { storeToRefs } from 'pinia'
import { EXAMPLES } from '../data/examples'
import { useCompareStore } from '../stores/compare'

const compareStore = useCompareStore()
const { textA, textB } = storeToRefs(compareStore)

const activeTab = ref(0)

const exA = EXAMPLES.slice(0, 2)
const exB = EXAMPLES.slice(1, 3)

const resultA = computed(() => compareStore.resultA)
const resultB = computed(() => compareStore.resultB)
const summary = computed(() => compareStore.summary)

const resultIcon = computed(() => {
  if (summary.value.winner === 'tie') return 'balance-o'
  return 'award-o'
})
const resultTitle = computed(() => {
  if (summary.value.winner === 'tie') return '两份条款风险相近'
  if (summary.value.winner === 'A') return '条款 A 风险更低（推荐）'
  return '条款 B 风险更低（推荐）'
})

function fill(side, exId) {
  compareStore.fillExample(side, exId)
  showToast(`已填充${side}条款示例`)
}
function clear(side) {
  compareStore.clear(side)
}
function swapText() {
  const tmpText = textA.value
  const tmpTitle = compareStore.titleA
  compareStore.setText('A', textB.value, compareStore.titleB)
  compareStore.setText('B', tmpText, tmpTitle)
  showToast('已交换 A / B')
}
function scrollToResult() {
  const el = document.querySelector('.result-card')
  el?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
</script>

<script>
import { h } from 'vue'
const FindingCard = {
  name: 'FindingCard',
  props: ['item', 'side'],
  setup(props) {
    const sevCls = props.item?.severity === 'high' ? 'high' : props.item?.severity === 'low' ? 'low' : 'mid'
    const sevLabel = props.item?.severity === 'high' ? '高' : props.item?.severity === 'low' ? '低' : '中'
    const sideCls = props.side === 'A' ? 'a' : 'b'
    return () =>
      h('div', { class: ['finding-item', `sev-${sevCls}`, `side-${sideCls}`] }, [
        h('div', { class: 'fi-head' }, [
          h('span', { class: `sev-tag sev-${sevCls}` }, sevLabel),
          h('span', { class: `side-tag side-${sideCls}` }, `条款 ${props.side}`),
          h('span', { class: 'fi-title' }, props.item?.title || '未命名风险'),
        ]),
        h('div', { class: 'fi-desc' }, props.item?.desc || ''),
      ])
  },
}
</script>

<style scoped>
.compare-page { padding-bottom: 110px; }

.compare-row {
  display: flex;
  gap: 10px;
  align-items: stretch;
}
.compare-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.compare-col-title {
  font-size: 13px;
  font-weight: 600;
  padding: 7px 10px;
  border-radius: 8px;
  text-align: center;
  margin-bottom: 8px;
}
.compare-col-title.a { background: var(--crusher-primary-light); color: var(--crusher-primary); }
.compare-col-title.b { background: var(--crusher-warning-light); color: var(--crusher-warning); }

.col-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 6px;
}
.col-actions .van-button {
  flex: 1;
  min-width: calc(50% - 6px);
}

.vs-divider {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  padding: 20px 0;
}
.vs-circle {
  width: 38px; height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #1989fa, #ff976a);
  color: #fff;
  font-weight: 800;
  font-size: 12px;
  display: flex; align-items: center; justify-content: center;
  box-shadow: 0 4px 10px rgba(25,137,250,0.25);
}

.result-card {
  padding: 18px;
  border-radius: 14px;
  background: var(--crusher-card-bg);
  border: 2px solid var(--crusher-border);
}
.result-card.A { border-color: var(--crusher-primary); background: var(--crusher-primary-light); }
.result-card.B { border-color: var(--crusher-warning); background: var(--crusher-warning-light); }
.result-card.tie { border-color: var(--crusher-ink-3); }

.result-head {
  display: flex;
  gap: 14px;
  align-items: flex-start;
  margin-bottom: 16px;
}
.result-head .van-icon { color: var(--crusher-primary); }
.result-card.B .result-head .van-icon { color: var(--crusher-warning); }
.result-card.tie .result-head .van-icon { color: var(--crusher-ink-2); }
.result-text { flex: 1; min-width: 0; }
.result-title { font-size: 17px; font-weight: 700; color: var(--crusher-ink); margin-bottom: 4px; }
.result-desc { font-size: 13px; color: var(--crusher-ink-2); line-height: 1.5; }

.result-grid {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--crusher-surface);
  border-radius: 12px;
  border: 1px solid var(--crusher-border);
}
.result-cell {
  flex: 1;
  text-align: center;
  padding: 6px;
  border-radius: 10px;
}
.result-cell.a { background: var(--crusher-primary-light); }
.result-cell.b { background: var(--crusher-warning-light); }
.cell-label { font-size: 12px; font-weight: 600; color: var(--crusher-ink-2); margin-bottom: 4px; }
.cell-score { font-size: 28px; color: var(--crusher-ink); }
.result-cell.a .cell-score { color: var(--crusher-primary); }
.result-cell.b .cell-score { color: var(--crusher-warning); }
.cell-meta { font-size: 11px; color: var(--crusher-ink-2); margin-top: 2px; }
.cell-vs {
  width: 36px; height: 36px; border-radius: 50%;
  background: var(--crusher-surface-2);
  display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}

.diff-list {
  padding: 8px 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100px;
}
.empty-findings {
  margin: 12px 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--crusher-ink-3);
  text-align: center;
}
.finding-item {
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--crusher-border);
  background: var(--crusher-card-bg);
}
.finding-item.sev-high { border-color: var(--crusher-danger); background: var(--crusher-danger-light); }
.finding-item.sev-mid { border-color: var(--crusher-warning); background: var(--crusher-warning-light); }
.finding-item.sev-low { border-color: var(--crusher-primary); background: var(--crusher-primary-light); }
.fi-head {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}
.sev-tag {
  padding: 2px 7px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 700;
  color: #fff;
}
.sev-tag.sev-high { background: var(--crusher-danger); }
.sev-tag.sev-mid { background: var(--crusher-warning); }
.sev-tag.sev-low { background: var(--crusher-primary); }
.side-tag {
  padding: 2px 6px;
  border-radius: 5px;
  font-size: 11px;
  font-weight: 600;
}
.side-tag.side-a { background: var(--crusher-primary-light); color: var(--crusher-primary); }
.side-tag.side-b { background: var(--crusher-warning-light); color: var(--crusher-warning); }
.fi-title { font-size: 14px; font-weight: 600; color: var(--crusher-ink); }
.fi-desc {
  font-size: 12px;
  color: var(--crusher-ink-2);
  line-height: 1.5;
  padding-left: 2px;
}

.bottom-bar {
  position: fixed;
  bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 480px;
  padding: 12px;
  padding-bottom: calc(12px + env(safe-area-inset-bottom));
  background: linear-gradient(180deg, transparent, #fff 30%);
  z-index: 99;
}
</style>
