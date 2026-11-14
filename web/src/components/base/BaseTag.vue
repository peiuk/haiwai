<script setup lang="ts">
// BaseTag：状态标签，good/link/warn/danger 四态，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    variant?: "default" | "good" | "link" | "warn" | "danger";
  }>(),
  { variant: "default" },
);
</script>

<template>
  <span class="tag" :class="variant !== 'default' ? `tag--${variant}` : ''">
    <slot />
  </span>
</template>
