<template>
  <van-config-provider :theme="themeStore.theme" class="app-root">
    <router-view v-slot="{ Component }">
      <transition name="slide-up" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <van-floating-bubble
      v-if="showFloatingChat"
      v-model:offset="offset"
      icon="chat-o"
      axis="xy"
      :gap="GAP"
      @click="goChat"
      @offset-change="snapToNearestEdge"
      class="chat-float"
    />
  </van-config-provider>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ConfigProvider } from 'vant'
import { useThemeStore } from './stores/theme'

const router = useRouter()
const route = useRoute()
const themeStore = useThemeStore()

// 与 Vant 默认尺寸一致（--van-floating-bubble-size: 48px）
const BUBBLE_SIZE = 48
const GAP = 16
// 吸附后露出的比例（0.5 = 只露出图标的一半）
const PEEK_RATIO = 0.5
const offset = ref(null)

const showFloatingChat = computed(() => {
  const noShow = ['chat', 'compare', 'error']
  return !noShow.includes(route.name)
})

function goChat() {
  router.push({ name: 'chat' })
}

function snapToNearestEdge(pos) {
  if (!pos) return
  const w = window.innerWidth
  const h = window.innerHeight
  const peek = BUBBLE_SIZE * PEEK_RATIO
  // 吸附后气泡部分移出屏幕，只露出 peek 大小
  const left = -peek
  const right = w - peek
  const top = -peek
  const bottom = h - peek

  // 分别计算到左右上下四条边的距离，吸附到最近的一条
  const candidates = [
    { dist: Math.abs(pos.x - left), x: left, y: pos.y },
    { dist: Math.abs(pos.x - right), x: right, y: pos.y },
    { dist: Math.abs(pos.y - top), x: pos.x, y: top },
    { dist: Math.abs(pos.y - bottom), x: pos.x, y: bottom },
  ]
  candidates.sort((a, b) => a.dist - b.dist)
  const best = candidates[0]
  offset.value = { x: best.x, y: best.y }
}

onMounted(() => {
  themeStore.restore()
})
</script>

<style scoped>
.app-root {
  min-height: 100vh;
}
.chat-float :deep(.van-floating-bubble) {
  box-shadow: 0 8px 24px rgba(25, 137, 250, 0.4);
  /* 松手吸附时平滑过渡；拖拽过程中组件会以内联 transition:none 覆盖，保持跟手 */
  transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.35, 1);
}
</style>
