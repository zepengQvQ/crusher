<template>
  <div class="calc">
    <van-button block plain type="primary" class="touch-btn" @click="show = true">
      简单收益 / 费用计算
    </van-button>
    <van-popup
      v-model:show="show"
      position="bottom"
      round
      :style="{ height: '88%' }"
    >
      <div class="drawer">
        <h3>情景计算器</h3>
        <p class="hint">参数可预填报告抽取值，须你确认后才会计算。这不是收益承诺。</p>

        <van-radio-group v-model="kind" direction="horizontal" class="kinds">
          <van-radio name="simple_return">简单收益</van-radio>
          <van-radio name="fee">比例费用</van-radio>
          <van-radio name="net_exit">退出净结果</van-radio>
        </van-radio-group>

        <template v-if="kind === 'simple_return'">
          <van-field v-model="principal" label="本金" :placeholder="pref.principal || '如 100000'" />
          <van-field
            v-model="annualRate"
            label="年化%"
            :placeholder="pref.rate || '如 3.65'"
          />
          <van-field v-model="days" label="天数" :placeholder="pref.days || '如 90'" />
          <van-field name="basis" label="计息基数">
            <template #input>
              <van-radio-group v-model="basis" direction="horizontal">
                <van-radio name="365">365</van-radio>
                <van-radio name="360">360</van-radio>
              </van-radio-group>
            </template>
          </van-field>
          <p v-if="pref.sources.length" class="src">预填来源：{{ pref.sources.join('；') }}</p>
        </template>

        <template v-else-if="kind === 'fee'">
          <van-field v-model="feeBase" label="计费基数" :placeholder="pref.principal || '如 100000'" />
          <van-field v-model="feeRate" label="费率%" :placeholder="pref.feeRate || '如 0.5'" />
        </template>

        <template v-else>
          <van-field v-model="principal" label="本金" />
          <van-field v-model="returnAmount" label="收益" placeholder="可先算简单收益再填" />
          <van-field v-model="feeAmount" label="费用" placeholder="可先算比例费用再填" />
        </template>

        <van-button
          block
          type="primary"
          class="touch-btn"
          :loading="loading"
          @click="run"
        >
          我已确认参数，开始计算
        </van-button>

        <div v-if="result" class="result">
          <div class="row">公式：{{ result.formula }}</div>
          <div class="row strong">结果：{{ result.result }}</div>
          <div class="row">舍入：{{ result.rounding }}</div>
          <ul>
            <li v-for="(a, i) in result.assumptions || []" :key="i">{{ a }}</li>
          </ul>
          <p class="disc">{{ result.disclaimer }}</p>
        </div>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { createCalculation, pickErrorMessage } from '../api/client'

const props = defineProps({
  keyParameters: { type: Array, default: () => [] },
})

const show = ref(false)
const loading = ref(false)
const kind = ref('simple_return')
const principal = ref('')
const annualRate = ref('')
const days = ref('')
const basis = ref('365')
const feeBase = ref('')
const feeRate = ref('')
const returnAmount = ref('')
const feeAmount = ref('')
const result = ref(null)

const pref = computed(() => {
  const sources = []
  let p = ''
  let rate = ''
  let d = ''
  let feeR = ''
  for (const item of props.keyParameters || []) {
    if (item.status === 'not_disclosed') continue
    if (item.key === 'amount') {
      p = item.amount != null ? String(item.amount) : extractNumber(item.value)
      if (p) sources.push(`本金←${item.label || 'amount'}`)
    }
    if (item.key === 'annual_interest_rate' || item.key === 'expected_return') {
      rate = extractPercent(item.value)
      if (rate) sources.push(`年化←${item.label || item.key}`)
    }
    if (item.key === 'term') {
      d = termToDays(item.value)
      if (d) sources.push(`天数←${item.label || 'term'}`)
    }
    if (item.key === 'fee_structure' || item.key === 'prepayment_fee') {
      feeR = extractPercent(item.value)
      if (feeR) sources.push(`费率←${item.label || item.key}`)
    }
  }
  return { principal: p, rate, days: d, feeRate: feeR, sources }
})

watch(show, (open) => {
  if (!open) return
  if (!principal.value && pref.value.principal) principal.value = pref.value.principal
  if (!annualRate.value && pref.value.rate) annualRate.value = pref.value.rate
  if (!days.value && pref.value.days) days.value = pref.value.days
  if (!feeBase.value && pref.value.principal) feeBase.value = pref.value.principal
  if (!feeRate.value && pref.value.feeRate) feeRate.value = pref.value.feeRate
})

function extractNumber(v) {
  if (!v) return ''
  const m = String(v).replace(/,/g, '').match(/(\d+(?:\.\d+)?)/)
  return m ? m[1] : ''
}

function extractPercent(v) {
  if (!v) return ''
  const s = String(v)
  if (/[~～—至-]/.test(s.replace(/^-/, ''))) return ''
  const m = s.replace(/,/g, '').match(/(\d+(?:\.\d+)?)\s*%?/)
  return m ? m[1] : ''
}

function termToDays(v) {
  if (!v) return ''
  const s = String(v)
  const year = s.match(/(\d+(?:\.\d+)?)\s*年/)
  if (year) return String(Math.round(Number(year[1]) * 365))
  const month = s.match(/(\d+(?:\.\d+)?)\s*个?月/)
  if (month) return String(Math.round(Number(month[1]) * 30))
  const day = s.match(/(\d+(?:\.\d+)?)\s*天/)
  if (day) return day[1]
  return extractNumber(s)
}

async function run() {
  loading.value = true
  result.value = null
  try {
    /** @type {Record<string, string|boolean>} */
    const payload = { kind: kind.value, user_confirmed: true }
    if (kind.value === 'simple_return') {
      payload.principal = principal.value
      payload.annual_rate_percent = annualRate.value
      payload.days = days.value
      payload.day_count_basis = basis.value
    } else if (kind.value === 'fee') {
      payload.fee_base = feeBase.value
      payload.fee_rate_percent = feeRate.value
    } else {
      payload.principal = principal.value
      payload.return_amount = returnAmount.value
      payload.fee_amount = feeAmount.value
    }
    result.value = await createCalculation(payload)
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.drawer {
  padding: 16px 16px 32px;
  overflow: auto;
  height: 100%;
  box-sizing: border-box;
}
h3 {
  margin: 0 0 8px;
  font-size: 18px;
}
.hint,
.src,
.disc {
  color: #666;
  font-size: 13px;
  line-height: 1.5;
}
.kinds {
  margin: 12px 0;
  flex-wrap: wrap;
  gap: 8px;
}
.touch-btn {
  min-height: 44px;
  margin-top: 12px;
}
.result {
  margin-top: 16px;
  padding: 12px;
  background: #f7f8fa;
  border-radius: 8px;
}
.row {
  margin: 4px 0;
  word-break: break-all;
}
.strong {
  font-size: 18px;
  font-weight: 600;
}
ul {
  margin: 8px 0;
  padding-left: 18px;
  color: #666;
  font-size: 13px;
}
</style>
