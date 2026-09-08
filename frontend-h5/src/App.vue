<template>
  <router-view />
</template>

<script setup>
</script>

<style>
  :root {
    --crusher-bg: #f5f6f8;
    --crusher-ink: #1f2937;
  }
  * {
    box-sizing: border-box;
  }
  html,
  body,
  #app {
    margin: 0;
    min-height: 100%;
    background: var(--crusher-bg);
    color: var(--crusher-ink);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB',
      'Microsoft YaHei', sans-serif;
  }
  .page {
    max-width: 480px;
    margin: 0 auto;
    min-height: 100vh;
    padding-bottom: calc(24px + env(safe-area-inset-bottom));
  }
  .block {
    margin: 12px;
    padding: 14px;
    background: #fff;
    border-radius: 10px;
  }
</style>
