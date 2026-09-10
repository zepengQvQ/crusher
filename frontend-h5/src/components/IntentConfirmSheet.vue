<template>
  <van-popup v-model:show="show" position="bottom" round :style="{ height: '55%' }">
    <div class="sheet">
      <h3>{{ title }}</h3>
      <p class="hint">{{ hint }}</p>
      <van-cell
        v-for="(opt, i) in options"
        :key="opt.intent + i"
        :title="opt.label"
        :label="opt.reason || ''"
        is-link
        @click="pick(opt)"
      />
      <van-button block plain class="touch-btn" @click="show = false">取消</van-button>
    </div>
  </van-popup>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  decision: { type: Object, default: null },
})

const emit = defineEmits(['update:modelValue', 'select'])

const show = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const options = computed(() => props.decision?.clarifying_options || [])
const title = ref('请选择要做的事')
const hint = ref('')

watch(
  () => props.decision,
  (d) => {
    if (!d) return
    if (d.intent === 'unsupported') {
      title.value = '超出 Demo 范围'
      hint.value = (d.rationale || []).join('；') || '不能提供购买建议'
    } else {
      title.value = '意图不明确，请先选一件事'
      hint.value = (d.rationale || []).join('；')
    }
  },
  { immediate: true },
)

function pick(opt) {
  emit('select', opt)
  show.value = false
}
</script>

<style scoped>
.sheet {
  padding: 16px 16px 28px;
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
.touch-btn {
  min-height: 44px;
  margin-top: 12px;
}
</style>
