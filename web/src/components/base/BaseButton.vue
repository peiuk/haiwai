<script setup lang="ts">
// BaseButton：4 变体 + loading 态，对齐 MASTER §5.1。
// 变体映射 tokens.css 的 .btn--primary/outline/solid-dark/ghost/danger，尺寸 .btn--sm。
withDefaults(
  defineProps<{
    variant?: "primary" | "outline" | "solid-dark" | "ghost" | "danger";
    size?: "md" | "sm";
    type?: "button" | "submit";
    loading?: boolean;
    disabled?: boolean;
  }>(),
  {
    variant: "primary",
    size: "md",
    type: "button",
    loading: false,
    disabled: false,
  },
);
</script>

<template>
  <button
    :type="type"
    class="btn"
    :class="[`btn--${variant}`, size === 'sm' ? 'btn--sm' : '']"
    :disabled="disabled || loading"
    :aria-busy="loading || undefined"
  >
    <slot>{{ loading ? "处理中…" : "确认" }}</slot>
  </button>
</template>
