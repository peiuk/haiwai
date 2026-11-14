<script setup lang="ts">
// BaseCard：卡片容器，可点击时用 role="button" + 键盘 Enter/Space，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    clickable?: boolean;
  }>(),
  { clickable: false },
);

const emit = defineEmits<{ (e: "click", ev: MouseEvent): void }>();

function onKey(ev: KeyboardEvent): void {
  if (ev.key === "Enter" || ev.key === " ") {
    ev.preventDefault();
    emit("click", ev as unknown as MouseEvent);
  }
}
</script>

<template>
  <div
    class="card"
    :role="clickable ? 'button' : undefined"
    :tabindex="clickable ? 0 : undefined"
    @click="clickable && emit('click', $event)"
    @keydown="clickable && onKey($event)"
  >
    <slot />
  </div>
</template>

<style scoped>
.card {
  padding: var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
}
.card[role="button"]:hover {
  background: var(--hover);
}
</style>
