<script setup lang="ts">
// Skeleton：加载占位，>300ms 异步才显示，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    height?: string;
    width?: string;
  }>(),
  {
    height: "16px",
    width: "100%",
  },
);
</script>

<template>
  <div class="skeleton" :style="{ height, width }" aria-busy="true" aria-hidden="true"></div>
</template>
