<script setup lang="ts">
// Progress：进度条，role="progressbar"，对齐 MASTER §5.1。
// pending：进度走完但还在等（如服务器转码），条上走一道光，告诉用户还没卡住。
withDefaults(
  defineProps<{
    value: number;
    max?: number;
    label?: string;
    pending?: boolean;
  }>(),
  {
    max: 100,
    label: "进度",
    pending: false,
  },
);
</script>

<template>
  <div
    class="progress"
    :class="{ 'is-pending': pending }"
    role="progressbar"
    :aria-label="label"
    :aria-valuenow="value"
    :aria-valuemin="0"
    :aria-valuemax="max"
  >
    <i :style="{ width: `${Math.min(100, (value / max) * 100)}%` }"></i>
  </div>
</template>

<style scoped>
.progress {
  position: relative;
  height: 4px;
  border-radius: var(--r-pill);
  background: var(--line);
  overflow: hidden;
}
.progress i {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--accent);
  transition: width 0.2s linear;
}
.progress.is-pending::after {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.6), transparent);
  animation: progress-shine 1.2s ease-in-out infinite;
}
@keyframes progress-shine {
  from { transform: translateX(-100%); }
  to { transform: translateX(100%); }
}
@media (prefers-reduced-motion: reduce) {
  .progress.is-pending::after { animation: none; }
}
</style>
