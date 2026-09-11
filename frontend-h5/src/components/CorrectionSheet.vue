<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ maxHeight: '78%' }">
    <div class="sheet">
      <h3>{{ title }}</h3>
      <p class="hint">{{ hint }}</p>

      <template v-if="mode === 'source_text'">
        <van-field
          v-model="textValue"
          rows="5"
          autosize
          type="textarea"
          label="修正后的原文"
          placeholder="粘贴或改成正确的材料原文"
        />
      </template>

      <template v-else-if="mode === 'product_type'">
        <van-radio-group v-model="productValue">
          <van-cell title="结构性存款" clickable @click="productValue = 'structured_deposit'">
            <template #right-icon>
              <van-radio name="structured_deposit" />
            </template>
          </van-cell>
          <van-cell title="贷款" clickable @click="productValue = 'loan'">
            <template #right-icon>
              <van-radio name="loan" />
            </template>
          </van-cell>
        </van-radio-group>
      </template>

      <template v-else-if="mode === 'fact_value'">
        <div class="current" v-if="previousLabel">
          当前识别为 <strong>{{ previousLabel }}</strong>
        </div>
        <van-field
          v-model="factValue"
          rows="2"
          autosize
          type="textarea"
          label="你认为的正确值"
          placeholder="填写正确内容（会记为你的声明，不会伪装成材料原文）"
        />
      </template>

      <div v-if="showDiff" class="diff-box">
        <div class="diff-title">将改成</div>
        <div class="diff-row">
          <span class="tag">现在</span>
          <span class="val">{{ displayBefore }}</span>
        </div>
        <div class="diff-row">
          <span class="tag next">改后</span>
          <span class="val">{{ displayAfter }}</span>
        </div>
      </div>

      <van-button
        block
        type="primary"
        round
        class="touch-btn"
        :loading="submitting"
        :disabled="!canSubmit"
        @click="submit"
      >
        提交并重新分析
      </van-button>
      <van-button block plain round class="touch-btn" style="margin-top: 8px" @click="show = false">
        取消
      </van-button>
    </div>
  </van-popup>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { showToast } from 'vant'
import { createCorrection, pickErrorMessage } from '../api/client'

const PRODUCT_LABEL = {
  structured_deposit: '结构性存款',
  loan: '贷款',
  auto: '自动识别',
}

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  taskId: { type: String, required: true },
  mode: {
    type: String,
    default: 'fact_value', // source_text | product_type | fact_value
  },
  parameterKey: { type: String, default: '' },
  previousValue: { type: String, default: '' },
  sourceText: { type: String, default: '' },
  productHint: { type: String, default: 'auto' },
})

const emit = defineEmits(['update:modelValue', 'submitted'])

const show = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const textValue = ref('')
const productValue = ref('loan')
const factValue = ref('')
const submitting = ref(false)

const title = computed(() => {
  if (props.mode === 'source_text') return '原文识别错了'
  if (props.mode === 'product_type') return '产品类型认错了'
  return '这里识别错了'
})

const hint = computed(() => {
  if (props.mode === 'source_text') return '改完会生成一份新报告，原来的报告还在，不会被覆盖。'
  if (props.mode === 'product_type') return '选对产品类型后会重新分析；原来的报告仍可查看。'
  return '你填的内容会记成「你的声明」，不会当成材料原文。'
})

const previousLabel = computed(() => props.previousValue || '材料未说明')

function productLabel(id) {
  const key = String(id || '').trim()
  return PRODUCT_LABEL[key] || key || '未指定'
}

const displayBefore = computed(() => {
  if (props.mode === 'source_text') {
    const t = (props.sourceText || '').trim()
    if (!t) return '（空）'
    return t.length > 60 ? `${t.slice(0, 60)}…` : t
  }
  if (props.mode === 'product_type') return productLabel(props.productHint || 'auto')
  return previousLabel.value
})

const displayAfter = computed(() => {
  if (props.mode === 'source_text') {
    const t = textValue.value.trim()
    if (!t) return '（空）'
    return t.length > 60 ? `${t.slice(0, 60)}…` : t
  }
  if (props.mode === 'product_type') return productLabel(productValue.value)
  return factValue.value.trim() || '（空）'
})

const showDiff = computed(() => {
  const before = displayBefore.value
  const after = displayAfter.value
  if (!after || after === '（空）') return false
  return before !== after
})

const canSubmit = computed(() => {
  if (props.mode === 'source_text') return !!textValue.value.trim()
  if (props.mode === 'product_type') return !!productValue.value
  return !!factValue.value.trim() && !!props.parameterKey
})

watch(
  () => props.modelValue,
  (open) => {
    if (!open) return
    textValue.value = props.sourceText || ''
    productValue.value =
      props.productHint === 'structured_deposit' || props.productHint === 'loan'
        ? props.productHint
        : 'loan'
    factValue.value = props.previousValue || ''
  },
)

async function submit() {
  /** @type {import('../api/client').CorrectionPayload} */
  let item
  if (props.mode === 'source_text') {
    const t = textValue.value.trim()
    if (!t) {
      showToast('请填写修正后的原文')
      return
    }
    item = { kind: 'source_text', corrected_text: t }
  } else if (props.mode === 'product_type') {
    item = { kind: 'product_type', product_type: productValue.value }
  } else {
    const v = factValue.value.trim()
    if (!v || !props.parameterKey) {
      showToast('请填写正确值')
      return
    }
    item = {
      kind: 'fact_value',
      parameter_key: props.parameterKey,
      corrected_value: v,
      previous_value: props.previousValue || null,
    }
  }
  submitting.value = true
  try {
    const res = await createCorrection(props.taskId, { corrections: [item] })
    emit('submitted', res)
    show.value = false
  } catch (e) {
    showToast(pickErrorMessage(e))
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.sheet {
  padding: 18px 16px 28px;
  overflow: auto;
}
h3 {
  margin: 0 0 6px;
  font-size: 17px;
  color: var(--crusher-ink);
}
.hint {
  margin: 0 0 14px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.5;
}
.current {
  margin: 0 0 10px;
  font-size: 13px;
  color: #475569;
}
.diff-box {
  margin: 14px 0;
  padding: 12px;
  background: var(--crusher-bg-gray, #f5f6f8);
  border-radius: 12px;
}
.diff-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--crusher-ink-2);
  margin-bottom: 8px;
}
.diff-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 13px;
  line-height: 1.45;
  color: var(--crusher-ink);
}
.diff-row + .diff-row {
  margin-top: 8px;
}
.tag {
  flex-shrink: 0;
  min-width: 36px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #e5e7eb;
  color: #4b5563;
  font-size: 11px;
  font-weight: 600;
  text-align: center;
}
.tag.next {
  background: var(--crusher-primary-light, #ecf5ff);
  color: var(--crusher-primary, #1989fa);
}
.val {
  flex: 1;
  min-width: 0;
  word-break: break-word;
}
.touch-btn {
  min-height: 44px;
  margin-top: 8px;
}
</style>
