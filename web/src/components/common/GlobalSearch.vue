<script setup lang="ts">
// 全站搜索：接通后端 GET /api/v1/search（q 以 @ 搜用户、# 搜关键词，否则搜内容/频道）。
// 对齐原型首页顶部 top-search：支持 / 聚焦、清除、结果下拉、Esc 关闭。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request, type SearchResponse } from "../../api";
import BaseIcon from "../base/BaseIcon.vue";
import Avatar from "../base/Avatar.vue";

const router = useRouter();
const route = useRoute();

const query = ref("");
const open = ref(false);
const busy = ref(false);
const results = ref<SearchResponse>({ users: [], channels: [], contents: [] });
const inputEl = ref<HTMLInputElement | null>(null);
const boxEl = ref<HTMLElement | null>(null);

const hasResults = computed(
  () => results.value.users.length + results.value.channels.length + results.value.contents.length > 0,
);
const hasQuery = computed(() => query.value.trim().length > 0);

let debounce = 0;

async function runSearch(): Promise<void> {
  const raw = query.value.trim();
  if (!raw) {
    results.value = { users: [], channels: [], contents: [] };
    open.value = false;
    return;
  }
  busy.value = true;
  try {
    results.value = await request<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(raw)}`);
    open.value = true;
  } catch {
    // 搜索失败静默，保留空结果并收起下拉
    results.value = { users: [], channels: [], contents: [] };
    open.value = false;
  } finally {
    busy.value = false;
  }
}

function onInput(): void {
  window.clearTimeout(debounce);
  debounce = window.setTimeout(runSearch, 200);
}

function clear(): void {
  query.value = "";
  results.value = { users: [], channels: [], contents: [] };
  open.value = false;
  inputEl.value?.focus();
}

function close(): void {
  open.value = false;
}

function goChannel(id: string, kind: string): void {
  close();
  clear();
  router.push({ name: kind === "room" ? "room" : "channel", params: { id } });
}

function goContent(contentId: string): void {
  // 跳内容详情独立页（/content/:id）
  close();
  clear();
  router.push({ name: "content", params: { id: contentId } });
}

function goUser(userId: string): void {
  close();
  clear();
  // 跳用户主页（/user/:id）
  router.push({ name: "user", params: { id: userId } });
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape") {
    close();
    return;
  }
  // 全局 / 聚焦搜索框
  if (
    e.key === "/" &&
    !(e.target instanceof HTMLInputElement) &&
    !(e.target instanceof HTMLTextAreaElement)
  ) {
    e.preventDefault();
    inputEl.value?.focus();
  }
}

function onClickOutside(e: MouseEvent): void {
  if (boxEl.value && !boxEl.value.contains(e.target as Node)) close();
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  document.addEventListener("click", onClickOutside);
});
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.removeEventListener("click", onClickOutside);
  window.clearTimeout(debounce);
});

watch(query, (v) => {
  if (!v.trim()) {
    results.value = { users: [], channels: [], contents: [] };
    open.value = false;
  }
});

// 从 URL 的 ?q= 初始化搜索词并自动检索（供右栏「热门关键词」等入口跳转后触发）。
// 仅在查询串变化时同步一次，避免覆盖用户正在输入的内容。
watch(
  () => route.query.q,
  (q) => {
    if (typeof q === "string" && q.trim()) {
      query.value = q.trim();
      void runSearch();
    }
  },
);
</script>

<template>
  <div ref="boxEl" class="gsearch" role="search" aria-label="全站搜索">
    <div class="gsearch-input">
      <BaseIcon name="i-search" :size="18" />
      <label class="sr-only" for="global-search">搜索内容、频道、房间、@用户名或 #关键词</label>
      <input
        id="global-search"
        ref="inputEl"
        v-model="query"
        type="search"
        autocomplete="off"
        placeholder="搜索内容、频道、@用户、#关键词"
        @input="onInput"
        @focus="hasQuery && (open = true)"
      />
      <button
        v-if="hasQuery"
        class="gsearch-clear"
        type="button"
        aria-label="清除搜索"
        @click="clear"
      >
        <BaseIcon name="i-close" :size="16" />
      </button>
      <button type="button" class="gsearch-submit" :disabled="!hasQuery || busy" @click="runSearch">搜索</button>
    </div>

    <div v-if="open" class="gsearch-drop" role="listbox" aria-label="搜索结果">
      <p v-if="busy" class="gsearch-hint">搜索中…</p>
      <template v-else-if="hasResults">
        <div v-if="results.channels.length" class="gsearch-group">
          <p class="gsearch-group-title">频道</p>
          <button
            v-for="ch in results.channels"
            :key="ch.id"
            type="button"
            class="gsearch-item"
            role="option"
            @click="goChannel(ch.id, ch.kind)"
          >
            <span class="gsearch-kind">#</span>
            <span class="gsearch-label">{{ ch.name_hans }}</span>
            <span class="gsearch-sub">{{ ch.kind === "room" ? "房间" : "频道" }}</span>
          </button>
        </div>

        <div v-if="results.contents.length" class="gsearch-group">
          <p class="gsearch-group-title">内容</p>
          <button
            v-for="c in results.contents"
            :key="c.content_id"
            type="button"
            class="gsearch-item"
            role="option"
            @click="goContent(c.content_id)"
          >
            <span class="gsearch-kind"><BaseIcon name="i-image" :size="16" /></span>
            <span class="gsearch-label" data-ugc>{{ c.title }}</span>
            <span class="gsearch-sub">{{ c.channel_name }}</span>
          </button>
        </div>

        <div v-if="results.users.length" class="gsearch-group">
          <p class="gsearch-group-title">用户</p>
          <button
            v-for="u in results.users"
            :key="u.user_id"
            type="button"
            class="gsearch-item"
            role="option"
            @click="goUser(u.user_id)"
          >
            <Avatar :name="u.display_name" :size="38" :tone="u.avatar_tone" />
            <span class="gsearch-label" data-ugc>{{ u.display_name }}</span>
            <span class="gsearch-sub">{{ u.handle }}</span>
          </button>
        </div>
      </template>
      <p v-else class="gsearch-hint">没有找到匹配结果</p>
    </div>
  </div>
</template>

<style scoped>
.gsearch {
  position: relative;
}
.gsearch-input {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 44px;
  padding: 3px 4px 3px var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-pill);
  background: var(--surface2);
  color: var(--muted);
}
.gsearch-input input {
  flex: 1;
  min-width: 0;
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: var(--fs-15);
}
.gsearch-input input:focus {
  outline: none;
}
.gsearch-clear {
  display: grid;
  place-items: center;
  min-width: var(--tap);
  min-height: var(--tap);
  color: var(--muted);
}
.gsearch-submit {
  flex: none;
  min-height: 36px;
  padding: 0 16px;
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: var(--fs-13);
  font-weight: var(--fw-bold);
}
.gsearch-submit:disabled { opacity: 0.55; }
.gsearch-drop {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: var(--z-toast);
  max-height: 420px;
  overflow-y: auto;
  padding: var(--sp-1);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.gsearch-group + .gsearch-group {
  margin-top: var(--sp-1);
}
.gsearch-group-title {
  margin: 0;
  padding: var(--sp-1) var(--sp-2);
  font-size: var(--fs-12);
  color: var(--muted);
}
.gsearch-item {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  border-radius: var(--r-sm);
  text-align: left;
  color: var(--text);
}
.gsearch-item:hover {
  background: var(--hover);
}
.gsearch-kind {
  flex: none;
  width: 20px;
  text-align: center;
  color: var(--muted);
}
.gsearch-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gsearch-sub {
  flex: none;
  max-width: 40%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: var(--fs-12);
}
.gsearch-hint {
  margin: 0;
  padding: var(--sp-3);
  color: var(--muted);
  font-size: var(--fs-13);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
</style>
