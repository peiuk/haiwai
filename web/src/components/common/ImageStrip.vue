<script setup lang="ts">
// 分类信息详情图片横滑（MASTER §22.7）：16:10，最多 6 张，滚动吸附。
// 后端 image_keys_json 支持 1–6 张，旧数据回退到单列 image_key；无图时显示占位而不是虚构图片。
import { computed, ref } from "vue";
import BaseIcon from "../base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{ keys?: string[]; alt?: string }>(),
  { keys: () => [], alt: "分类信息图片" },
);

const images = computed(() => (props.keys ?? []).filter(Boolean).slice(0, 6));
const strip = ref<HTMLElement | null>(null);
const index = ref(0);

function scrollTo(next: number): void {
  const node = strip.value;
  if (!node || images.value.length === 0) return;
  const clamped = Math.max(0, Math.min(images.value.length - 1, next));
  index.value = clamped;
  node.scrollTo({ left: clamped * node.clientWidth, behavior: "smooth" });
}

function onScroll(): void {
  const node = strip.value;
  if (!node) return;
  index.value = Math.round(node.scrollLeft / Math.max(1, node.clientWidth));
}
</script>

<template>
  <div class="image-strip" role="group" :aria-label="alt">
    <div v-if="images.length === 0" class="image-empty">暂无图片</div>
    <template v-else>
      <div ref="strip" class="strip" @scroll.passive="onScroll">
        <img
          v-for="(key, i) in images"
          :key="key"
          class="slide"
          :src="`/api/v1/uploads/${key}`"
          :alt="`${alt} ${i + 1}/${images.length}`"
          loading="lazy"
        />
      </div>
      <div v-if="images.length > 1" class="strip-controls">
        <button type="button" class="strip-btn" aria-label="上一张" @click="scrollTo(index - 1)">
          <BaseIcon name="i-chev" :size="20" :rotate="90" />
        </button>
        <span class="strip-count" aria-live="polite">{{ index + 1 }} / {{ images.length }}</span>
        <button type="button" class="strip-btn" aria-label="下一张" @click="scrollTo(index + 1)">
          <BaseIcon name="i-chev" :size="20" :rotate="-90" />
        </button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.image-strip {
  display: grid;
  gap: var(--sp-2);
}
.strip {
  display: flex;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  border-radius: var(--r-md);
  border: 1px solid var(--border);
  background: var(--surface2);
}
.slide {
  flex: 0 0 100%;
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  scroll-snap-align: start;
}
.image-empty {
  display: grid;
  place-items: center;
  aspect-ratio: 16 / 10;
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  background: var(--surface2);
  color: var(--muted);
  font-size: var(--fs-12);
}
.strip-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-3);
}
.strip-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: var(--tap);
  min-height: var(--tap);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--surface2);
  color: var(--text);
  cursor: pointer;
}
.strip-count {
  font-size: var(--fs-12);
  color: var(--muted);
}
</style>
