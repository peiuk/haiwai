<script setup lang="ts">
// 列表底部哨兵：进入视口即请求下一批；无 IntersectionObserver 时退回手动按钮。
import { onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = withDefaults(
  defineProps<{ loading: boolean; hasMore: boolean; hint?: string }>(),
  { hint: "继续下拉加载更多" },
);
const emit = defineEmits<{ load: [] }>();
const anchor = ref<HTMLElement | null>(null);
const supported = ref(false);
let observer: IntersectionObserver | null = null;

function trigger(): void {
  if (props.hasMore && !props.loading) emit("load");
}

function reobserve(): void {
  if (!observer || !anchor.value) return;
  // 重新观察会立即回调一次，保证「内容不足一屏、哨兵始终可见」时也能连续加载。
  observer.unobserve(anchor.value);
  observer.observe(anchor.value);
}

onMounted(() => {
  if (!("IntersectionObserver" in window)) return;
  supported.value = true;
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) trigger();
    },
    { rootMargin: "240px 0px" },
  );
  if (anchor.value) observer.observe(anchor.value);
});

watch(
  () => [props.hasMore, props.loading],
  () => {
    if (props.hasMore && !props.loading) reobserve();
  },
);

onBeforeUnmount(() => observer?.disconnect());
</script>

<template>
  <div ref="anchor" class="infinite-sentinel" role="status" aria-live="polite">
    <p v-if="loading" class="state">正在加载更多…</p>
    <button v-else-if="hasMore && !supported" class="manual" type="button" @click="trigger">加载更多</button>
    <p v-else-if="hasMore" class="state">{{ hint }}</p>
    <p v-else class="state state--end">已经到底了</p>
  </div>
</template>

<style scoped>
.infinite-sentinel {
  display: grid;
  place-items: center;
  min-height: 44px;
  padding: 12px 16px 20px;
}
.state {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.state--end { opacity: 0.7; }
.manual {
  min-height: var(--tap);
  padding: 0 18px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--bg);
  color: var(--accent-ink);
  font-size: var(--fs-13);
  cursor: pointer;
}
.manual:hover { background: var(--accent-soft); }
</style>
