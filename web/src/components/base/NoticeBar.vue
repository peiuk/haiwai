<script setup lang="ts">
// NoticeBar：提示条，info/warn/danger 三态，可关闭，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    variant?: "info" | "warn" | "danger";
    dismissible?: boolean;
  }>(),
  {
    variant: "info",
    dismissible: false,
  },
);

const emit = defineEmits<{ (e: "dismiss"): void }>();
</script>

<template>
  <div class="notice" :class="variant !== 'info' ? `notice--${variant}` : ''" role="note">
    <span class="notice-body"><slot /></span>
    <button v-if="dismissible" type="button" class="notice-close" aria-label="关闭" @click="emit('dismiss')">×</button>
  </div>
</template>

<style scoped>
.notice-body {
  flex: 1;
  min-width: 0;
}
.notice-close {
  font-size: var(--fs-17);
  line-height: 1;
  color: var(--muted);
}
.notice-close:hover {
  color: var(--text);
}
</style>
