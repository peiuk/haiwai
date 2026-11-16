<script setup lang="ts">
// MediaFeed：全屏竖向刷媒体（抖音式）。一条占满一屏，上下滑翻一条（CSS scroll-snap）；
// 滑到的视频自动播放（静音起播，手机浏览器只放行静音自动播放），滑走就暂停。
// start 从 -1 变成 >=0 时打开并定位到那一条；Esc / 关闭按钮关闭；点标题打开原帖。
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import BaseIcon from "../base/BaseIcon.vue";

export type MediaFeedItem = { src: string; video: boolean; post: { content_id: string; title: string } };

const props = defineProps<{ items: MediaFeedItem[]; start: number; label: string }>();
const emit = defineEmits<{ (e: "close"): void; (e: "open", contentId: string): void }>();

const list = ref<HTMLElement | null>(null);
const current = ref(0);
const muted = ref(true);
let observer: IntersectionObserver | null = null;

function videoAt(i: number): HTMLVideoElement | null {
  return list.value?.querySelector<HTMLVideoElement>(`[data-i="${i}"] video`) ?? null;
}

function watchSlides(): void {
  observer?.disconnect();
  if (!list.value) return;
  observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        const i = Number((entry.target as HTMLElement).dataset.i);
        const video = videoAt(i);
        if (entry.isIntersecting) {
          current.value = i;
          void video?.play().catch(() => undefined);
        } else {
          video?.pause();
        }
      }
    },
    { root: list.value, threshold: 0.6 },
  );
  list.value.querySelectorAll(".mf-slide").forEach((slide) => observer?.observe(slide));
}

// 手机返回手势：打开时压一条历史记录，返回就只关掉全屏、不离开主页。
// 带上原有的 history.state，vue-router 靠它记位置；用按钮 / Esc / 点标题关掉时把这条记录退掉。
function onPop(): void {
  if (props.start >= 0) emit("close");
}

watch(
  () => props.start,
  async (start, before) => {
    if (start < 0) {
      observer?.disconnect();
      if (history.state?.mediaFeed) history.back();
      return;
    }
    if (before === undefined || before < 0) history.pushState({ ...history.state, mediaFeed: true }, "");
    current.value = start;
    await nextTick();
    if (list.value) list.value.scrollTop = start * list.value.clientHeight;
    watchSlides();
  },
);

function togglePlay(i: number): void {
  const video = videoAt(i);
  if (video) void (video.paused ? video.play().catch(() => undefined) : video.pause());
}

function step(delta: number): void {
  list.value?.scrollBy({ top: delta * list.value.clientHeight, behavior: "smooth" });
}

function onKey(e: KeyboardEvent): void {
  if (props.start < 0) return;
  if (e.key === "Escape") emit("close");
  else if (e.key === "ArrowDown") (e.preventDefault(), step(1));
  else if (e.key === "ArrowUp") (e.preventDefault(), step(-1));
}

onMounted(() => {
  window.addEventListener("keydown", onKey);
  window.addEventListener("popstate", onPop);
});
onBeforeUnmount(() => {
  window.removeEventListener("keydown", onKey);
  window.removeEventListener("popstate", onPop);
  observer?.disconnect();
});
</script>

<template>
  <Teleport to="body">
    <div v-if="start >= 0" class="mf" role="dialog" aria-modal="true" :aria-label="`${label} 的图片和视频`">
      <div ref="list" class="mf-list">
        <section v-for="(item, i) in items" :key="item.src" class="mf-slide" :data-i="i">
          <video
            v-if="item.video"
            :src="item.src"
            class="mf-media"
            :muted="muted"
            loop
            playsinline
            preload="metadata"
            @click="togglePlay(i)"
          ></video>
          <img v-else :src="item.src" :alt="item.post.title" class="mf-media" loading="lazy" />
          <button type="button" class="mf-caption" @click="emit('open', item.post.content_id)">
            <span data-ugc>{{ item.post.title || "查看帖子" }}</span>
            <small>点这里看帖子</small>
          </button>
        </section>
      </div>

      <button type="button" class="mf-btn mf-close" aria-label="关闭" @click="emit('close')">
        <BaseIcon name="i-close" :size="24" />
      </button>
      <button
        v-if="items[current]?.video"
        type="button"
        class="mf-btn mf-sound"
        :aria-pressed="!muted"
        @click="muted = !muted"
      >
        {{ muted ? "开声音" : "静音" }}
      </button>
      <div class="mf-count">{{ current + 1 }} / {{ items.length }}</div>
    </div>
  </Teleport>
</template>

<style scoped>
.mf {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  background: #000;
  color: #fff;
}
.mf-list {
  height: 100%;
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  overscroll-behavior: contain;
  scrollbar-width: none;
}
.mf-list::-webkit-scrollbar {
  display: none;
}
.mf-slide {
  position: relative;
  height: 100%;
  display: grid;
  place-items: center;
  scroll-snap-align: start;
  scroll-snap-stop: always;
}
.mf-media {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
.mf-caption {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  display: grid;
  gap: 2px;
  padding: 48px 16px calc(20px + env(safe-area-inset-bottom));
  border: 0;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.7));
  color: #fff;
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
  text-align: left;
  cursor: pointer;
}
.mf-caption span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.mf-caption small {
  font-size: var(--fs-13);
  font-weight: 400;
  opacity: 0.8;
}
.mf-btn {
  position: fixed;
  top: calc(12px + env(safe-area-inset-top));
  display: grid;
  place-items: center;
  min-width: 44px;
  height: 44px;
  padding: 0 12px;
  border: 0;
  border-radius: var(--r-pill);
  background: rgba(255, 255, 255, 0.15);
  color: #fff;
  font-size: var(--fs-14);
  cursor: pointer;
}
.mf-btn:hover {
  background: rgba(255, 255, 255, 0.3);
}
.mf-close {
  right: 12px;
  padding: 0;
}
.mf-sound {
  left: 12px;
}
.mf-count {
  position: fixed;
  top: calc(22px + env(safe-area-inset-top));
  left: 50%;
  transform: translateX(-50%);
  font-size: var(--fs-13);
  opacity: 0.8;
}
</style>
