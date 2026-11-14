<script setup lang="ts">
// Lightbox：图片灯箱（X 平台式）。点背景 / Esc / 关闭按钮关闭，多图左右切换，键盘 ← → 切换。
// initial-index 从 -1 变为 >=0 时打开；关闭回传 close 事件。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import BaseIcon from "../base/BaseIcon.vue";

const props = defineProps<{
  images: string[];
  initialIndex: number;
  alt: string;
}>();

const emit = defineEmits<{ (e: "close"): void }>();

const current = ref(0);
const open = computed(() => props.initialIndex >= 0 && props.initialIndex < props.images.length);

watch(
  () => props.initialIndex,
  (idx) => {
    if (idx >= 0) current.value = idx;
  },
);

function close(): void {
  emit("close");
}

function prev(): void {
  if (props.images.length < 2) return;
  current.value = (current.value - 1 + props.images.length) % props.images.length;
}

function next(): void {
  if (props.images.length < 2) return;
  current.value = (current.value + 1) % props.images.length;
}

function onKey(e: KeyboardEvent): void {
  if (!open.value) return;
  if (e.key === "Escape") close();
  else if (e.key === "ArrowLeft") prev();
  else if (e.key === "ArrowRight") next();
}

onMounted(() => {
  window.addEventListener("keydown", onKey);
});

onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKey);
});
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="lightbox-backdrop"
      role="dialog"
      aria-modal="true"
      :aria-label="`${alt} 图片预览`"
      @click.self="close"
    >
      <button type="button" class="lightbox-close" aria-label="关闭预览" @click="close">
        <BaseIcon name="i-close" :size="24" />
      </button>

      <button
        v-if="images.length > 1"
        type="button"
        class="lightbox-nav lightbox-prev"
        aria-label="上一张"
        @click="prev"
      >
        <BaseIcon name="i-back" :size="28" />
      </button>

      <img :src="images[current]" :alt="`${alt} 图片 ${current + 1}`" class="lightbox-img" />

      <button
        v-if="images.length > 1"
        type="button"
        class="lightbox-nav lightbox-next"
        aria-label="下一张"
        @click="next"
      >
        <BaseIcon name="i-back" :size="28" class="flip" />
      </button>

      <div v-if="images.length > 1" class="lightbox-count">{{ current + 1 }} / {{ images.length }}</div>
    </div>
  </Teleport>
</template>

<style scoped>
.lightbox-backdrop {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.9);
}
.lightbox-img {
  max-width: 92vw;
  max-height: 88vh;
  object-fit: contain;
  border-radius: 4px;
}
.lightbox-close {
  position: fixed;
  top: 16px;
  right: 16px;
  display: grid;
  place-items: center;
  width: 44px;
  height: 44px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
}
.lightbox-close:hover {
  background: rgba(255, 255, 255, 0.3);
}
.lightbox-nav {
  position: fixed;
  top: 50%;
  transform: translateY(-50%);
  display: grid;
  place-items: center;
  width: 48px;
  height: 48px;
  border: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  cursor: pointer;
}
.lightbox-nav:hover {
  background: rgba(255, 255, 255, 0.3);
}
.lightbox-prev {
  left: 16px;
}
.lightbox-next {
  right: 16px;
}
.lightbox-next .flip {
  transform: rotate(180deg);
}
.lightbox-count {
  position: fixed;
  bottom: 20px;
  left: 50%;
  transform: translateX(-50%);
  padding: 4px 12px;
  border-radius: var(--r-pill);
  background: rgba(0, 0, 0, 0.5);
  color: #fff;
  font-size: var(--fs-13);
}
</style>
