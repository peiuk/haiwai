<script setup lang="ts">
// Progress：进度条，role="progressbar"，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    value: number;
    max?: number;
    label?: string;
  }>(),
  {
    max: 100,
    label: "进度",
  },
);
</script>

<template>
  <div
    class="progress"
    role="progressbar"
    :aria-label="label"
    :aria-valuenow="value"
    :aria-valuemin="0"
    :aria-valuemax="max"
  >
    <i :style="{ width: `${Math.min(100, (value / max) * 100)}%` }"></i>
  </div>
</template>
