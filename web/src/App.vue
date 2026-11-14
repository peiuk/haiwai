<script setup lang="ts">
// 应用根组件：挂载一次全局 SVG sprite，页面布局由 AppShell 提供。
import IconSprite from "./components/base/IconSprite.vue";
</script>

<template>
  <IconSprite />
  <RouterView />
</template>
