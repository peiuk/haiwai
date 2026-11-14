<script setup lang="ts">
// Modal：对话框，Esc 关闭 + 焦点陷阱 + 打开锁定滚动，对齐 MASTER §5.1。
import { onBeforeUnmount, onMounted, ref } from "vue";

withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    labelledby?: string;
  }>(),
  { labelledby: "" },
);

const emit = defineEmits<{ (e: "close"): void }>();

const panel = ref<HTMLElement | null>(null);

function onKeydown(ev: KeyboardEvent): void {
  if (ev.key === "Escape") {
    emit("close");
    return;
  }
  // 简易焦点陷阱：Tab 循环在面板内
  if (ev.key === "Tab" && panel.value) {
    const focusables = panel.value.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (focusables.length === 0) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (ev.shiftKey && document.activeElement === first) {
      ev.preventDefault();
      last.focus();
    } else if (!ev.shiftKey && document.activeElement === last) {
      ev.preventDefault();
      first.focus();
    }
  }
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.body.style.overflow = "";
});
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="modal-backdrop" @click.self="emit('close')">
      <div
        ref="panel"
        class="modal-panel"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="labelledby || 'modal-title'"
      >
        <header class="modal-head">
          <h2 :id="labelledby || 'modal-title'" class="modal-title">{{ title }}</h2>
          <button type="button" class="icon-btn" aria-label="关闭" @click="emit('close')">×</button>
        </header>
        <div class="modal-body"><slot /></div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.modal-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: grid;
  place-items: center;
  padding: var(--sp-4);
  background: color-mix(in srgb, var(--scrim-base) 50%, transparent);
}
.modal-panel {
  width: 100%;
  max-width: 480px;
  max-height: 85vh;
  overflow: auto;
  background: var(--bg);
  border-radius: var(--r-lg);
  box-shadow: var(--shadow);
}
.modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--sp-4);
  border-bottom: 1px solid var(--border);
}
.modal-title {
  margin: 0;
  font-size: var(--fs-15);
}
.modal-body {
  padding: var(--sp-4);
}
</style>
