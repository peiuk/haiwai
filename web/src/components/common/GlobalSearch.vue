<script setup lang="ts">
// 全站搜索框（对齐 X 的搜索体验）：
// - 聚焦但没输入：显示「最近搜索」（存本机）和「热门话题」
// - 输入时：第一行「搜索“xxx”」，下面是联想到的用户 / 频道
// - 回车或点「搜索“xxx”」：进入搜索结果页 /search?q=
// - 手机端聚焦后铺满全屏，右侧有「取消」
// 后端 GET /api/v1/search：q 以 @ 搜用户名、# 搜话题，否则搜内容 / 频道 / 用户。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request, type SearchResponse, type TrendingKeywordsResponse } from "../../api";
import BaseIcon from "../base/BaseIcon.vue";
import Avatar from "../base/Avatar.vue";

const RECENT_KEY = "ukcn.recentSearch";
const RECENT_MAX = 8;
const EMPTY: SearchResponse = { users: [], channels: [], contents: [] };

const router = useRouter();
const route = useRoute();

const query = ref("");
const open = ref(false);
const busy = ref(false);
const results = ref<SearchResponse>(EMPTY);
const inputEl = ref<HTMLInputElement | null>(null);
const boxEl = ref<HTMLElement | null>(null);
const recent = ref<string[]>(readRecent());
const trending = ref<string[]>([]);
let trendingLoaded = false;

const hasQuery = computed(() => query.value.trim().length > 0);
const suggestUsers = computed(() => results.value.users.slice(0, 4));
const suggestChannels = computed(() => results.value.channels.slice(0, 4));

// ---- 最近搜索：只存在这台设备上；读写失败（隐私模式等）时当作没有记录 ----
function readRecent(): string[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
    return Array.isArray(parsed) ? parsed.filter((s): s is string => typeof s === "string").slice(0, RECENT_MAX) : [];
  } catch {
    return [];
  }
}

function saveRecent(list: string[]): void {
  recent.value = list;
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(list));
  } catch {
    /* 存不了就只在本次会话里保留 */
  }
}

function remember(term: string): void {
  saveRecent([term, ...recent.value.filter((t) => t !== term)].slice(0, RECENT_MAX));
}

function forget(term: string): void {
  saveRecent(recent.value.filter((t) => t !== term));
}

async function loadTrending(): Promise<void> {
  if (trendingLoaded) return;
  trendingLoaded = true;
  try {
    const body = await request<TrendingKeywordsResponse>("/api/v1/search/trending-keywords?limit=6");
    trending.value = body.keywords.map((k) => k.keyword);
  } catch {
    trendingLoaded = false; // 下次聚焦再试
  }
}

// ---- 联想 ----
let debounce = 0;

async function runTypeahead(): Promise<void> {
  const raw = query.value.trim();
  if (!raw) {
    results.value = EMPTY;
    return;
  }
  busy.value = true;
  try {
    const body = await request<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(raw)}`);
    // 慢请求回来时输入已经变了，就丢掉这次结果
    if (query.value.trim() === raw) results.value = body;
  } catch {
    results.value = EMPTY;
  } finally {
    busy.value = false;
  }
}

function onFocus(): void {
  open.value = true;
  void loadTrending();
}

function onInput(): void {
  open.value = true;
  window.clearTimeout(debounce);
  debounce = window.setTimeout(runTypeahead, 200);
}

function close(): void {
  open.value = false;
  inputEl.value?.blur();
}

function clear(): void {
  query.value = "";
  results.value = EMPTY;
  inputEl.value?.focus();
}

/** 进入搜索结果页，并记进「最近搜索」。 */
function submit(term = query.value): void {
  const q = term.trim();
  if (!q) return;
  remember(q);
  query.value = q;
  close();
  router.push({ name: "search", query: { q } });
}

function goChannel(id: string, kind: string): void {
  remember(query.value.trim());
  close();
  router.push({ name: kind === "room" ? "room" : "channel", params: { id } });
}

function goUser(userId: string): void {
  remember(query.value.trim());
  close();
  router.push({ name: "user", params: { id: userId } });
}

function onKeydown(e: KeyboardEvent): void {
  if (e.key === "Escape" && open.value) {
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

/** 上下方向键在输入框和下拉各行之间移动焦点；聚焦的行按回车即触发它自己的点击。 */
function onArrow(e: KeyboardEvent): void {
  if (!open.value || (e.key !== "ArrowDown" && e.key !== "ArrowUp")) return;
  const items = Array.from(boxEl.value?.querySelectorAll<HTMLElement>(".gsearch-item") ?? []);
  if (!items.length) return;
  e.preventDefault();
  const next = items.indexOf(document.activeElement as HTMLElement) + (e.key === "ArrowDown" ? 1 : -1);
  if (next < 0) inputEl.value?.focus();
  else items[Math.min(next, items.length - 1)].focus();
}

// 手机上搜索铺满全屏时，锁住背后页面的滚动（和详情弹窗同样做法）
const mobile = window.matchMedia("(max-width: 759px)");
let locked = false;
function setLock(on: boolean): void {
  if (on === locked) return;
  locked = on;
  document.body.style.overflow = on ? "hidden" : "";
}
watch(open, (on) => setLock(on && mobile.matches));

function onClickOutside(e: MouseEvent): void {
  if (boxEl.value && !boxEl.value.contains(e.target as Node)) open.value = false;
}

onMounted(() => {
  document.addEventListener("keydown", onKeydown);
  document.addEventListener("click", onClickOutside);
});
onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.removeEventListener("click", onClickOutside);
  window.clearTimeout(debounce);
  setLock(false);
});

// 在搜索结果页时，输入框显示当前搜索词；离开结果页后清空
watch(
  () => (route.name === "search" ? route.query.q : undefined),
  (q) => {
    query.value = typeof q === "string" ? q : "";
    results.value = EMPTY;
  },
  { immediate: true },
);
</script>

<template>
  <div
    ref="boxEl"
    class="gsearch"
    :class="{ 'gsearch--active': open }"
    role="search"
    aria-label="全站搜索"
    @keydown="onArrow"
  >
    <div class="gsearch-bar">
      <div class="gsearch-input">
        <BaseIcon name="i-search" :size="18" />
        <label class="sr-only" for="global-search">搜索内容、频道、房间、@用户名或 #话题</label>
        <input
          id="global-search"
          ref="inputEl"
          v-model="query"
          type="search"
          autocomplete="off"
          placeholder="搜索内容、频道、@用户、#话题"
          enterkeyhint="search"
          @focus="onFocus"
          @click="onFocus"
          @input="onInput"
          @keydown.enter.prevent="submit()"
        />
        <button v-if="hasQuery" class="gsearch-clear" type="button" aria-label="清除搜索" @click="clear">
          <BaseIcon name="i-close" :size="16" />
        </button>
        <button type="button" class="gsearch-submit" :disabled="!hasQuery" @click="submit()">搜索</button>
      </div>
      <button type="button" class="gsearch-cancel" @click="close">取消</button>
    </div>

    <div v-if="open" class="gsearch-drop">
      <!-- 还没输入：最近搜索 + 热门话题 -->
      <template v-if="!hasQuery">
        <div v-if="recent.length" class="gsearch-group">
          <div class="gsearch-group-head">
            <p class="gsearch-group-title">最近搜索</p>
            <button type="button" class="gsearch-link" @click="saveRecent([])">全部清除</button>
          </div>
          <div v-for="term in recent" :key="term" class="gsearch-row">
            <button type="button" class="gsearch-item" @click="submit(term)">
              <span class="gsearch-kind"><BaseIcon name="i-search" :size="16" /></span>
              <span class="gsearch-label" data-ugc>{{ term }}</span>
            </button>
            <button type="button" class="gsearch-remove" :aria-label="`删除搜索记录 ${term}`" @click="forget(term)">
              <BaseIcon name="i-close" :size="14" />
            </button>
          </div>
        </div>
        <div v-if="trending.length" class="gsearch-group">
          <p class="gsearch-group-title">热门话题</p>
          <button v-for="kw in trending" :key="kw" type="button" class="gsearch-item" @click="submit(`#${kw}`)">
            <span class="gsearch-kind">#</span>
            <span class="gsearch-label" data-ugc>{{ kw }}</span>
          </button>
        </div>
        <p v-if="!recent.length && !trending.length" class="gsearch-hint">试试搜索内容、频道、@用户名或 #话题</p>
      </template>

      <!-- 输入中：先给「搜索 xxx」，再给联想到的用户 / 频道 -->
      <template v-else>
        <button type="button" class="gsearch-item gsearch-item--go" @click="submit()">
          <span class="gsearch-kind"><BaseIcon name="i-search" :size="16" /></span>
          <span class="gsearch-label">搜索「<span data-ugc>{{ query.trim() }}</span>」</span>
        </button>
        <div v-if="suggestUsers.length" class="gsearch-group">
          <p class="gsearch-group-title">用户</p>
          <button v-for="u in suggestUsers" :key="u.user_id" type="button" class="gsearch-item" @click="goUser(u.user_id)">
            <Avatar :name="u.display_name" :size="38" :tone="u.avatar_tone" :image="u.avatar_key" />
            <span class="gsearch-label gsearch-label--stack">
              <strong data-ugc>{{ u.display_name }}</strong>
              <small v-if="u.handle">@{{ u.handle }}</small>
            </span>
          </button>
        </div>
        <div v-if="suggestChannels.length" class="gsearch-group">
          <p class="gsearch-group-title">频道</p>
          <button
            v-for="ch in suggestChannels"
            :key="ch.id"
            type="button"
            class="gsearch-item"
            @click="goChannel(ch.id, ch.kind)"
          >
            <Avatar :name="ch.name_hans" :size="38" kind="channel" />
            <span class="gsearch-label" data-ugc>{{ ch.name_hans }}</span>
            <span class="gsearch-sub">{{ ch.kind === "room" ? "房间" : "频道" }}</span>
          </button>
        </div>
        <p v-if="busy && !suggestUsers.length && !suggestChannels.length" class="gsearch-hint">搜索中…</p>
      </template>
    </div>
  </div>
</template>

<style scoped>
.gsearch {
  position: relative;
}
.gsearch-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.gsearch-input {
  flex: 1;
  min-width: 0;
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
/* 用自己的清除按钮，去掉浏览器自带的那个 × */
.gsearch-input input::-webkit-search-cancel-button {
  appearance: none;
}
/* 输入框去掉了 outline，焦点改由外框表达 */
.gsearch-input:focus-within {
  border-color: var(--accent);
  background: var(--bg);
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
.gsearch-cancel { display: none; }
.gsearch-drop {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: var(--z-toast);
  max-height: 480px;
  overflow-y: auto;
  padding: var(--sp-1);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.gsearch-group + .gsearch-group,
.gsearch-item--go + .gsearch-group {
  margin-top: var(--sp-1);
}
.gsearch-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.gsearch-group-title {
  margin: 0;
  padding: var(--sp-2) var(--sp-2) var(--sp-1);
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
  color: var(--text);
}
.gsearch-link {
  min-height: 32px;
  padding: 0 var(--sp-2);
  color: var(--accent-ink);
  font-size: var(--fs-13);
}
.gsearch-row {
  display: flex;
  align-items: center;
}
.gsearch-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  width: 100%;
  min-height: var(--tap);
  padding: 6px var(--sp-2);
  border-radius: var(--r-sm);
  text-align: left;
  color: var(--text);
}
.gsearch-item:hover,
.gsearch-item:focus-visible {
  background: var(--hover);
}
.gsearch-item--go {
  font-weight: var(--fw-semibold);
}
.gsearch-remove {
  flex: none;
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  color: var(--muted);
}
.gsearch-remove:hover { background: var(--hover); color: var(--text); }
.gsearch-kind {
  flex: none;
  display: grid;
  place-items: center;
  width: 38px;
  color: var(--muted);
  font-weight: var(--fw-bold);
}
.gsearch-label {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gsearch-label--stack {
  display: grid;
}
.gsearch-label--stack strong,
.gsearch-label--stack small {
  overflow: hidden;
  text-overflow: ellipsis;
}
.gsearch-label--stack small {
  color: var(--muted);
  font-size: var(--fs-13);
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

/* 手机：顶栏太窄，去掉「搜索」按钮（回车 / 联想第一行就是搜索）；聚焦后铺满全屏 */
@media (max-width: 759px) {
  .gsearch-submit { display: none; }
  .gsearch-clear { min-width: 32px; }
  .gsearch--active {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    display: flex;
    flex-direction: column;
    padding: var(--sp-2) var(--sp-4) env(safe-area-inset-bottom);
    background: var(--bg);
  }
  .gsearch--active .gsearch-cancel {
    display: block;
    flex: none;
    min-height: var(--tap);
    padding: 0 var(--sp-1);
    color: var(--text);
    font-size: var(--fs-15);
    font-weight: var(--fw-semibold);
  }
  .gsearch--active .gsearch-drop {
    position: static;
    flex: 1;
    max-height: none;
    margin-top: var(--sp-2);
    padding: 0;
    border: 0;
    border-radius: 0;
    background: transparent;
    box-shadow: none;
  }
}
</style>
