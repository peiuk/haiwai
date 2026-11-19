<script setup lang="ts">
// 发现页：按地区 / 分类浏览各频道的近期内容（PRD §36.11：不根据浏览记录推荐，不进画像）。
// 结构：一行筛选（地区下拉 + 分类横滑 + 「全部分类」展开）→（窄屏）热门话题 → 一个内容流
//（频道动态和分类信息混排，去重、按时间、滚动加载；分类信息用 ListingCard，不含过期 / 已结案）。
// 合规：每张资讯卡来源名 / 许可徽章 / 原文回链必显（§7.1）；卡片频道名可点进频道。
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useToastStore } from "../stores/toast";
import { useAuthStore } from "../stores/auth";
import { useLoginPromptStore } from "../stores/loginPrompt";
import { usePostReactions } from "../composables/usePostReactions";
import {
  request,
  toMessage,
  type DiscoverItem,
  type DiscoverResponse,
  type ListingCardItem,
  type RecommendedChannel,
  type RecommendedResponse,
  type TrendingKeywordsResponse,
} from "../api";
import ListingCard from "../components/discover/ListingCard.vue";
import PostCard from "../components/common/PostCard.vue";
import ContentDetail from "../components/ContentDetail.vue";
import EmptyState from "../components/base/EmptyState.vue";
import ErrorState from "../components/base/ErrorState.vue";
import InfiniteSentinel from "../components/common/InfiniteSentinel.vue";
import BaseIcon from "../components/base/BaseIcon.vue";

// 内容流里的分类信息带一份卡片数据，用 ListingCard 渲染
type FeedItem = DiscoverItem & { listing?: ListingCardItem | null };

const PAGE = 20;
// 推荐频道插在第几条帖子之后
const INLINE_REC_AFTER = 5;

const route = useRoute();
const router = useRouter();
const toast = useToastStore();
const auth = useAuthStore();
const loginPrompt = useLoginPromptStore();
const activeContentId = ref<string | null>(null);

const items = ref<FeedItem[]>([]);
// 「全部分类」展开面板：分类再多，筛选栏也只占一行
const catsOpen = ref(false);
const chipScroll = ref<HTMLElement | null>(null);
const categories = ref<string[]>([]);
const updatedCount = ref(0);
const cursor = ref<string | null>(null);
// 筛选写进网址（?region=&category=）：刷新、返回、分享都保留
const queryValue = (key: string): string => (typeof route.query[key] === "string" ? (route.query[key] as string) : "");
const activeCategory = ref(queryValue("category"));
// 地区：空 = 全部地区；GLOBAL = 国际；其余为当前开通国家代码（后端只在可见范围内收窄）
const activeRegion = ref(queryValue("region").toUpperCase());
const region = ref<{ code: string; name: string }>({ code: "GLOBAL", name: "国际" });
const loading = ref(true);
const refreshing = ref(false);
const loadingMore = ref(false);
const pageError = ref(false);
const error = ref("");

// 窄屏没有右栏：把热门话题和推荐频道放进页面里（宽屏右栏已有，不重复）
const narrow = typeof window !== "undefined" && window.matchMedia("(max-width: 1099px)").matches;
const trending = ref<string[]>([]);
const recommended = ref<RecommendedChannel[]>([]);

// 首次进入显示一次的说明（MASTER §22.11）：显示的同时就记下，之后再进来不再出现；点「知道了」可提前关掉。
const INTRO_KEY = "ukcn.tips.discoverIntro";
const showIntro = ref(false);
try {
  if (!localStorage.getItem(INTRO_KEY)) {
    localStorage.setItem(INTRO_KEY, String(Date.now()));
    showIntro.value = true;
  }
} catch {
  // 存储不可用时不显示，避免每次进来都出现
}

const hasFilter = computed(() => !!activeCategory.value || !!activeRegion.value);

// 选中的分类滚到看得见的位置（从「全部分类」里选的可能在横滑行的屏幕外）
function revealActiveChip(): void {
  void nextTick(() => {
    const active = chipScroll.value?.querySelector<HTMLElement>(".filter-chip.active");
    const row = chipScroll.value;
    if (!active || !row) return;
    const offset = active.getBoundingClientRect().left - row.getBoundingClientRect().left;
    row.scrollLeft += offset - (row.clientWidth - active.offsetWidth) / 2;
  });
}

function filterQuery(): string {
  const query = new URLSearchParams();
  if (activeCategory.value) query.set("category", activeCategory.value);
  if (activeRegion.value) query.set("region", activeRegion.value);
  return query.toString();
}

async function load(): Promise<void> {
  // 首次加载显示「加载中」；之后（换筛选、登录后刷新）保留旧列表，只把它变淡，页面不跳。
  loading.value = items.value.length === 0;
  refreshing.value = !loading.value;
  error.value = "";
  pageError.value = false;
  const qs = filterQuery();
  try {
    const discoverBody = await request<DiscoverResponse>(`/api/v1/discover/items?limit=${PAGE}${qs ? `&${qs}` : ""}`);
    if (qs !== filterQuery()) return; // 期间又换了筛选，丢弃过期结果
    items.value = discoverBody.items;
    categories.value = discoverBody.categories;
    updatedCount.value = discoverBody.updated_count;
    cursor.value = discoverBody.next_cursor ?? null;
    if (discoverBody.region) region.value = discoverBody.region;
    // 登录 / 切换国家后原来选中的地区可能已不存在，回到「全部地区」避免一直空白。
    if (activeRegion.value && !["GLOBAL", region.value.code].includes(activeRegion.value)) selectRegion("");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "发现页加载失败";
  } finally {
    loading.value = false;
    refreshing.value = false;
    revealActiveChip();
  }
}

async function loadMore(): Promise<void> {
  if (!cursor.value || loadingMore.value || pageError.value) return;
  loadingMore.value = true;
  const qs = filterQuery();
  try {
    const body = await request<DiscoverResponse>(
      `/api/v1/discover/items?limit=${PAGE}&cursor=${encodeURIComponent(cursor.value)}${qs ? `&${qs}` : ""}`,
    );
    if (qs !== filterQuery()) return;
    const seen = new Set(items.value.map((item) => item.content_id));
    items.value = [...items.value, ...body.items.filter((item) => !seen.has(item.content_id))];
    cursor.value = body.next_cursor ?? null;
  } catch {
    pageError.value = true;
  } finally {
    loadingMore.value = false;
  }
}

function applyFilters(): void {
  void router.replace({
    query: {
      ...route.query,
      region: activeRegion.value || undefined,
      category: activeCategory.value || undefined,
    },
  });
  void load();
}

function selectCategory(category: string): void {
  activeCategory.value = category;
  catsOpen.value = false;
  applyFilters();
}

function selectRegion(code: string): void {
  activeRegion.value = code;
  applyFilters();
}

function resetFilters(): void {
  activeCategory.value = "";
  activeRegion.value = "";
  applyFilters();
}

function searchTopic(keyword: string): void {
  void router.push({ name: "search", query: { q: `#${keyword}` } });
}

async function loadSideBlocks(): Promise<void> {
  if (!narrow) return;
  const [topics, channels] = await Promise.allSettled([
    request<TrendingKeywordsResponse>("/api/v1/search/trending-keywords?limit=8"),
    request<RecommendedResponse>("/api/v1/channels/recommended"),
  ]);
  trending.value = topics.status === "fulfilled" ? topics.value.keywords.map((item) => item.keyword) : [];
  recommended.value = channels.status === "fulfilled" ? channels.value.items.slice(0, 3) : [];
}

const { toggleLike, toggleFavorite, repost: repostItem } = usePostReactions();

function repost(item: DiscoverItem): Promise<void> {
  return repostItem(item, item.channel_id);
}

async function joinChannel(item: DiscoverItem): Promise<void> {
  if (!auth.isLoggedIn) {
    loginPrompt.require("登录后就能加入频道，登录成功会自动帮你加入。", () => joinChannel(item));
    return;
  }
  try {
    await request(`/api/v1/me/subscriptions/${item.channel_id}`, { method: "PUT" });
    item.is_joined = true;
    toast.show("已加入频道");
  } catch (err) {
    toast.show(toMessage(err));
  }
}

onMounted(() => {
  void load();
  void loadSideBlocks();
});
// 登录后等自动执行的操作完成再刷新，避免刷新读到操作前的状态。
watch(
  () => auth.isLoggedIn,
  () => void loginPrompt.whenIdle().then(load),
);
</script>

<template>
  <section class="discover">
    <p v-if="loading" class="empty">加载中…</p>
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />

    <template v-else>
      <!-- 筛选栏（MASTER §22.11）：永远一行。地区收成一个下拉；分类横滑；末尾「全部分类」展开完整列表 -->
      <div class="filter-bar">
        <label class="sr-only" for="discover-region">按地区筛选</label>
        <select
          id="discover-region"
          class="region-select"
          :value="activeRegion"
          @change="selectRegion(($event.target as HTMLSelectElement).value)"
        >
          <option value="">全部地区</option>
          <option value="GLOBAL">国际</option>
          <option v-if="region.code !== 'GLOBAL'" :value="region.code">{{ region.name }}</option>
        </select>
        <div v-if="categories.length > 0" ref="chipScroll" class="chip-scroll" role="group" aria-label="按分类筛选">
          <button type="button" class="filter-chip" :class="{ active: activeCategory === '' }" :aria-pressed="activeCategory === ''" @click="selectCategory('')">全部</button>
          <button
            v-for="category in categories"
            :key="category"
            type="button"
            class="filter-chip"
            :class="{ active: activeCategory === category }"
            :aria-pressed="activeCategory === category"
            @click="selectCategory(category)"
          >{{ category }}</button>
        </div>
        <button
          v-if="categories.length > 0"
          type="button"
          class="filter-chip filter-more"
          :class="{ active: catsOpen }"
          aria-label="全部分类"
          aria-controls="discover-all-cats"
          :aria-expanded="catsOpen"
          @click="catsOpen = !catsOpen"
        >
          <BaseIcon name="i-grid" :size="18" />
        </button>
      </div>
      <div v-if="catsOpen" id="discover-all-cats" class="cat-panel" role="group" aria-label="全部分类" @keydown.esc="catsOpen = false">
        <button type="button" class="filter-chip" :class="{ active: activeCategory === '' }" :aria-pressed="activeCategory === ''" @click="selectCategory('')">全部</button>
        <button
          v-for="category in categories"
          :key="category"
          type="button"
          class="filter-chip"
          :class="{ active: activeCategory === category }"
          :aria-pressed="activeCategory === category"
          @click="selectCategory(category)"
        >{{ category }}</button>
      </div>

      <div v-if="showIntro" class="discover-intro" role="note">
        <span>这里按时间汇集各频道的动态和分类信息，可以用上面的地区和分类筛选。</span>
        <button type="button" class="intro-close" aria-label="关闭说明，不再显示" @click="showIntro = false">知道了</button>
      </div>

      <!-- 窄屏：热门话题（宽屏在右栏） -->
      <section v-if="trending.length" class="topics-block" aria-labelledby="discover-topics-title">
        <h2 id="discover-topics-title" class="block-title">热门话题</h2>
        <div class="topic-row">
          <button v-for="word in trending" :key="word" type="button" class="topic-chip" @click="searchTopic(word)">#{{ word }}</button>
        </div>
      </section>

      <div :class="{ 'is-refreshing': refreshing }" :aria-busy="refreshing">
        <!-- 只有一个列表：频道动态和分类信息按时间混排（分类信息用 ListingCard，价格 / 地区一眼可见） -->
        <section class="feed-block" aria-labelledby="discover-feed-title">
          <h2 id="discover-feed-title" class="sr-only">最新动态和分类信息</h2>
          <p class="block-meta">按时间排序 · 近 7 天 {{ updatedCount }} 条更新 · 不根据浏览记录推荐</p>

          <EmptyState
            v-if="!items.length"
            :title="hasFilter ? '这个范围里暂时没有内容' : '还没有频道内容'"
            :action-label="hasFilter ? '看全部内容' : '去频道目录'"
            @action="hasFilter ? resetFilters() : router.push({ name: 'home', query: { tab: 'channels' } })"
          />

          <ul v-else class="content-list">
            <template v-for="(item, index) in items" :key="item.content_id">
              <li class="content-card">
                <ListingCard v-if="item.listing" :item="item.listing" :time="item.added_at" :is-joined="item.is_joined" @join="joinChannel(item)" />
                <!-- 发现页不做个性化推荐：不传推荐理由，也就没有「减少此类内容」 -->
                <PostCard
                  v-else
                  :content-id="item.content_id"
                  :title="item.title"
                  :summary="item.summary"
                  :channel-name="item.channel_name"
                  :channel-id="item.channel_id"
                  :certified="item.channel_certified"
                  :author-id="item.author_id" :author-name="item.author_name"
                  :author-handle="item.author_handle" :author-avatar="item.author_avatar"
                  :source-name="item.source_name"
                  :licence-ref="item.licence_ref"
                  :canonical-url="item.canonical_url"
                  :keywords="item.keywords"
                  :image-keys="item.image_keys"
                  :video-key="item.video_key"
                  :bg-style="item.bg_style"
                  :embed="item.embed"
                  :time="item.added_at"
                  :show-join="true"
                  :is-joined="item.is_joined"
                  :liked="item.liked"
                  :like-count="item.like_count"
                  :favorited="item.favorited"
                  :reposted="item.reposted"
                  @join="joinChannel(item)"
                  @open="activeContentId = item.content_id"
                  @like="toggleLike(item)"
                  @favorite="toggleFavorite(item)"
                  @repost="repost(item)"
                />
              </li>
              <!-- 窄屏：推荐频道（≤3）插在第 5 条之后；宽屏在右栏 -->
              <li v-if="index === INLINE_REC_AFTER - 1 && recommended.length" class="rec-block" aria-labelledby="discover-rec-title">
                <h2 id="discover-rec-title" class="block-title">你可能想加入</h2>
                <RouterLink
                  v-for="channel in recommended"
                  :key="channel.id"
                  class="rec-channel"
                  :to="{ name: 'channel', params: { id: channel.id } }"
                >
                  <span class="rec-name" data-ugc>{{ channel.name_hans }}</span>
                  <span class="rec-go">进频道</span>
                </RouterLink>
              </li>
            </template>
          </ul>

          <InfiniteSentinel
            v-if="items.length"
            :loading="loadingMore"
            :has-more="!!cursor && !pageError"
            hint="继续下拉加载更多"
            @load="loadMore"
          />
          <p v-if="pageError" class="page-error" role="alert">
            更多内容加载失败
            <button type="button" class="retry" @click="pageError = false; loadMore()">重试</button>
          </p>
        </section>
      </div>
      <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
    </template>
  </section>
</template>

<style scoped>
.discover {
  display: grid;
  /* 列宽钉死在容器宽度：不然分类 chip 一多，整列被撑宽，手机上整页能左右滑、帖子卡被切 */
  grid-template-columns: minmax(0, 1fr);
  gap: var(--sp-3);
  margin-bottom: var(--sp-6);
}
.empty {
  padding: var(--sp-6) 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.discover-intro {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface2);
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 1.6;
}
.intro-close {
  flex: none;
  min-height: 44px;
  padding: 0 var(--sp-2);
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
/* 筛选栏永远一行：地区下拉（固定）+ 分类横滑（占满剩余宽度）+ 「全部分类」按钮（固定） */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-width: 0;
}
.region-select {
  flex: none;
  min-height: 44px;
  max-width: 132px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--bg);
  color: var(--accent-ink);
  font: inherit;
  font-size: var(--fs-13);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
/* 横滑行，绝不撑出页面宽度；隐藏滚动条；右边缘渐隐提示还能往右滑 */
.chip-scroll,
.topic-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  overflow-x: auto;
  white-space: nowrap;
  scrollbar-width: none;
}
.chip-scroll {
  flex: 1;
  min-width: 0;
  padding-right: var(--sp-5);
  -webkit-mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent);
  mask-image: linear-gradient(to right, #000 calc(100% - 28px), transparent);
}
.chip-scroll::-webkit-scrollbar,
.topic-row::-webkit-scrollbar {
  display: none;
}
.filter-more {
  display: inline-grid;
  place-items: center;
  width: 44px;
  padding: 0;
}
/* 「全部分类」：就地展开、自动换行，分类再多也都看得到 */
.cat-panel {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface2);
}
.filter-chip,
.topic-chip {
  flex: none;
  white-space: nowrap;
  min-height: 44px;
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--surface2);
  color: var(--text);
  font-size: var(--fs-13);
  cursor: pointer;
}
.filter-chip.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
  border-color: transparent;
}
.topic-chip {
  background: transparent;
  color: var(--accent-ink);
}
.topic-chip:hover,
.filter-chip:hover {
  background: var(--hover);
}

/* 分区标题 */
.topics-block,
.feed-block {
  display: grid;
  grid-template-columns: minmax(0, 1fr); /* 同上：长内容不许把列撑宽 */
  gap: var(--sp-2);
}
.block-title {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: var(--fw-heavy);
}
.block-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.content-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.content-card {
  display: block;
}

/* 推荐频道（窄屏插在内容流里） */
.rec-block {
  display: grid;
  gap: var(--sp-1);
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border);
  background: var(--surface2);
}
.rec-channel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 44px;
  color: var(--text);
  text-decoration: none;
}
.rec-name {
  font-weight: var(--fw-semibold);
}
.rec-go {
  color: var(--accent-ink);
  font-size: var(--fs-13);
  font-weight: var(--fw-bold);
}

/* 换筛选时保留旧列表并变淡，不整页跳成「加载中」 */
.is-refreshing {
  opacity: 0.55;
  transition: opacity var(--dur-fast, 0.15s) ease;
}
@media (prefers-reduced-motion: reduce) {
  .is-refreshing {
    transition: none;
  }
}
.page-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--fs-13);
  text-align: center;
}
.retry {
  margin-left: var(--sp-2);
  min-height: 44px;
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
</style>
