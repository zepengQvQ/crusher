<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ maxHeight: '75%' }">
    <div class="sheet">
      <h3>这里识别错了</h3>
      <p class="hint">{{ hint }}</p>

      <template v-if="mode === 'source_text'">
        <van-field
          v-model="textValue"
          rows="5"
          autosize
          type="textarea"
          label="修正原文"
          placeholder="粘贴或修改识别错误的原文"
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
        <p class="diff" v-if="previousLabel">
          当前识别：<strong>{{ previousLabel }}</strong>
        </p>
        <van-field
          v-model="factValue"
          rows="2"
          autosize
          type="textarea"
          label="正确值"
          placeholder="填写你认为正确的值（将标记为用户声明）"
        />
      </template>

      <div v-if="diffPreview" class="diff-box">
        <div class="diff-title">将提交的差异</div>
        <p>前：{{ diffPreview.before || '（空）' }}</p>
        <p>后：{{ diffPreview.after || '（空）' }}</p>
      </div>

      <van-button
        block
        type="primary"
        round
        class="touch-btn"
        :loading="submitting"
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

const hint = computed(() => {
  if (props.mode === 'source_text') return '修正 OCR/粘贴错误后会创建新任务，不覆盖原报告。'
  if (props.mode === 'product_type') return '确认产品类型后重跑；原任务保持只读。'
  return '用户声明值不会伪装成「原文事实」。'
})

const previousLabel = computed(() => props.previousValue || '材料未说明')

const diffPreview = computed(() => {
  if (props.mode === 'source_text') {
    return { before: (props.sourceText || '').slice(0, 80), after: textValue.value.slice(0, 80) }
  }
  if (props.mode === 'product_type') {
    return { before: props.productHint || 'auto', after: productValue.value }
  }
  return { before: previousLabel.value, after: factValue.value }
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
  padding: 16px 16px 28px;
  overflow: auto;
}
h3 {
  margin: 0 0 8px;
  font-size: 17px;
}
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: #64748b;
  line-height: 1.45;
}
.diff {
  margin: 0 0 8px;
  font-size: 13px;
  color: #475569;
}
.diff-box {
  margin: 12px 0;
  padding: 10px;
  background: #f8fafc;
  border-radius: 8px;
  font-size: 12px;
  color: #64748b;
  line-height: 1.5;
}
.diff-title {
  font-weight: 600;
  margin-bottom: 4px;
  color: #334155;
}
.touch-btn {
  min-height: 44px;
  margin-top: 8px;
}
</style>
