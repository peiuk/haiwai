<script setup lang="ts">
// 右栏展示真实热门关键词、推荐频道和今日最关注。
import { onMounted, ref } from "vue";
import {
  request,
  type RecommendedResponse,
  type TrendingKeywordsResponse,
  type HomeRailResponse,
  type RailItem,
} from "../../api";
import { useRoute, useRouter } from "vue-router";
import { RouterLink } from "vue-router";
import Avatar from "../base/Avatar.vue";

const router = useRouter();
const route = useRoute();

const hotKeywords = ref<string[]>([]);
const keywordsLoaded = ref(false);
const recommended = ref<RecommendedResponse["items"]>([]);
const recLoaded = ref(false);
const today = ref<RailItem[]>([]);
const todayLoaded = ref(false);

async function loadHotKeywords(): Promise<void> {
  try {
    const body = await request<TrendingKeywordsResponse>("/api/v1/search/trending-keywords");
    hotKeywords.value = body.keywords.map((k) => `#${k.keyword}`);
  } catch {
    hotKeywords.value = [];
  } finally {
    keywordsLoaded.value = true;
  }
}

async function loadRecommended(): Promise<void> {
  try {
    const body = await request<RecommendedResponse>("/api/v1/channels/recommended");
    recommended.value = body.items;
  } catch {
    recommended.value = [];
  } finally {
    recLoaded.value = true;
  }
}

async function loadToday(): Promise<void> {
  try {
    const body = await request<HomeRailResponse>("/api/v1/discover/home-rail");
    today.value = body.today;
  } catch {
    today.value = [];
  } finally {
    todayLoaded.value = true;
  }
}

function searchKeyword(keyword: string): void {
  // 点击热门关键词：按话题进搜索结果页（keyword 已带 #）。
  router.push({ name: "search", query: { q: keyword } });
}

function openChannel(id: string): void {
  router.push({ name: "channel", params: { id } });
}

function openContent(item: RailItem): void {
  if (!item.content_id) return;
  router.push({ name: "content", params: { id: item.content_id } });
}

onMounted(() => {
  loadHotKeywords();
  loadRecommended();
  loadToday();
});
</script>

<template>
  <div class="right-rail">
    <div class="side-box">
      <h3>今日最关注</h3>
      <ol v-if="today.length" class="rail-list rail-list--rank">
        <li v-for="(item, i) in today" :key="item.content_id">
          <button
            type="button"
            class="rail-item"
            :class="{ 'is-current': route.name === 'content' && route.params.id === item.content_id }"
            :aria-current="route.name === 'content' && route.params.id === item.content_id ? 'page' : undefined"
            @click="openContent(item)"
          >
            <span class="rail-rank" :class="{ 'rail-rank--top': i < 3 }">{{ i + 1 }}</span>
            <span class="rail-title" data-ugc>{{ item.title }}</span>
          </button>
        </li>
      </ol>
      <p v-else class="side-empty">{{ todayLoaded ? "今日暂无热门内容" : "加载中…" }}</p>
    </div>

    <div class="side-box">
      <h3>热门关键词</h3>
      <div class="hot-key">
        <button
          v-for="kw in hotKeywords"
          :key="kw"
          type="button"
          class="hot-key-btn"
          :class="{ 'is-current': route.name === 'search' && route.query.q === kw }"
          :aria-pressed="route.name === 'search' && route.query.q === kw"
          :aria-label="`搜索关键词 ${kw}`"
          @click="searchKeyword(kw)"
        >
          {{ kw }}
        </button>
      </div>
      <p v-if="keywordsLoaded && !hotKeywords.length" class="side-empty">近期暂无热门关键词</p>
      <p v-else-if="!keywordsLoaded" class="side-empty">加载中…</p>
    </div>

    <div class="side-box">
      <h3>你可能想加入</h3>
      <div v-if="recommended.length" class="side-channels">
        <button
          v-for="ch in recommended"
          :key="ch.id"
          type="button"
          class="side-row"
          @click="openChannel(ch.id)"
        >
          <Avatar :name="ch.name_hans" :size="38" />
          <span class="side-row-name" data-ugc>{{ ch.name_hans }}</span>
        </button>
      </div>
      <p v-else-if="recLoaded" class="side-empty">暂无推荐频道</p>
      <p v-else class="side-empty">加载中…</p>
    </div>

    <div class="side-box">
      <h3>来源与合规</h3>
      <ul class="compliance-list">
        <li>内容来源分级：官方频道 / 编辑精选 / 用户原创，卡片以徽章区分。</li>
        <li>转载与引用均需保留原出处署名与许可标记。</li>
        <li>用户原创内容（UGC）仅代表作者本人观点。</li>
        <li>发现不当内容可随时通过卡片「举报」入口反馈。</li>
      </ul>
      <div class="legal-links">
        <RouterLink :to="{ name: 'legal', params: { section: 'tos' } }">服务条款</RouterLink>
        <span aria-hidden="true">·</span>
        <RouterLink :to="{ name: 'legal', params: { section: 'privacy' } }">隐私政策</RouterLink>
        <span aria-hidden="true">·</span>
        <RouterLink :to="{ name: 'legal', params: { section: 'cookie' } }">Cookie 政策</RouterLink>
      </div>
    </div>
  </div>
</template>

<style scoped>
.right-rail {
  display: flex;
  flex-direction: column;
  gap: var(--sp-4);
}
.side-box {
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.side-box h3 {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
}
.hot-key {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}
.hot-key-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  border-radius: var(--r-pill);
  background: var(--surface2);
  color: var(--text);
  font-size: var(--fs-13);
}
.hot-key-btn:hover {
  background: var(--hover);
}
.hot-key-btn:active,
.hot-key-btn.is-current {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.side-channels {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
}
.side-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  width: 100%;
  min-height: var(--tap);
  padding: 0 var(--sp-1);
  border-radius: var(--r-sm);
  text-align: left;
  color: var(--text);
}
.side-row:hover {
  background: var(--hover);
}
.side-row-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.side-empty,
.side-note {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.rail-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 2px;
}
.rail-list--rank {
  counter-reset: none;
}
.rail-item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  width: 100%;
  padding: 6px var(--sp-1);
  border-radius: var(--r-sm);
  text-align: left;
  color: var(--text);
}
.rail-item:hover {
  background: var(--hover);
}
.rail-item:active,
.rail-item.is-current {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.rail-rank {
  flex: none;
  width: 20px;
  height: 20px;
  margin-top: 1px;
  display: grid;
  place-items: center;
  border-radius: var(--r-sm);
  background: var(--surface2);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
}
.rail-rank--top {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.rail-title {
  flex: 1;
  min-width: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  font-size: var(--fs-13);
  line-height: 1.45;
}
.compliance-list {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 1.5;
}
.compliance-list li {
  position: relative;
  padding-left: var(--sp-3);
}
.compliance-list li::before {
  content: "";
  position: absolute;
  left: 0;
  top: 0.5em;
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--accent-ink);
}
.legal-links {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-1);
  margin-top: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border);
  font-size: var(--fs-12);
  color: var(--muted);
}
.legal-links a {
  color: var(--accent-strong);
  text-decoration: none;
}
.legal-links a:hover {
  text-decoration: underline;
}
</style>
