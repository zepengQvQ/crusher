<template>
  <van-config-provider :theme="themeStore.theme" class="app-root">
    <router-view v-slot="{ Component }">
      <transition name="slide-up" mode="out-in">
        <component :is="Component" />
      </transition>
    </router-view>
    <van-floating-bubble
      v-if="showFloatingChat"
      icon="chat-o"
      axis="xy"
      :gap="24"
      @click="goChat"
      class="chat-float"
    />
  </van-config-provider>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useThemeStore } from './stores/theme'

const router = useRouter()
const route = useRoute()
const themeStore = useThemeStore()

const showFloatingChat = computed(() => {
  const noShow = ['home', 'chat', 'compare', 'error', 'report']
  return !noShow.includes(route.name)
})

function goChat() {
  router.push({ name: 'chat' })
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
}
</style>
