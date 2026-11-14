<script setup lang="ts">
// 发现页：「为你推荐」单一信息流，分类信息与普通内容合并混排，不单独分区。
// 合规：每张资讯卡来源名 / 许可徽章 / 原文回链必显（§7.1）；推荐卡显示可解释性说明（§7.5）。
import { computed, onMounted, ref, watch } from "vue";
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
  type ListingsResponse,
} from "../api";
import ListingCard from "../components/discover/ListingCard.vue";
import PostCard from "../components/common/PostCard.vue";
import ContentDetail from "../components/ContentDetail.vue";
import EmptyState from "../components/base/EmptyState.vue";
import ErrorState from "../components/base/ErrorState.vue";

const toast = useToastStore();
const auth = useAuthStore();
const activeContentId = ref<string | null>(null);

const listings = ref<ListingCardItem[]>([]);
const items = ref<DiscoverItem[]>([]);
const categories = ref<string[]>([]);
const updatedCount = ref(0);
const activeCategory = ref("");
// 地区筛选：空 = 全部地区；GLOBAL = 国际；其余为当前开通国家代码（后端只在可见范围内收窄）
const activeRegion = ref("");
const region = ref<{ code: string; name: string }>({ code: "GLOBAL", name: "国际" });
const loading = ref(true);
const error = ref("");

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

// 合并后的统一信息流：普通内容 + 分类信息混排。
// listing 用 { kind: 'listing', listing }，普通内容用 { kind: 'content', item }。
type FeedEntry =
  | { kind: "content"; item: DiscoverItem }
  | { kind: "listing"; listing: ListingCardItem };

const feed = computed<FeedEntry[]>(() => {
  const contents: FeedEntry[] = items.value.map((item) => ({ kind: "content", item }));
  const listingEntries: FeedEntry[] = listings.value.map((listing) => ({ kind: "listing", listing }));
  // 分类信息（按到期时间近的在前）与普通内容（后端已按 added_at 倒序）合并，listing 排前更醒目。
  return [...listingEntries, ...contents];
});

const hasContent = computed(() => feed.value.length > 0);

async function load(): Promise<void> {
  // 已有内容时后台静默刷新（如登录后），不要整页换成「加载中」，否则页面会跳。
  loading.value = !hasContent.value;
  error.value = "";
  try {
    const query = new URLSearchParams();
    if (activeCategory.value) query.set("category", activeCategory.value);
    if (activeRegion.value) query.set("region", activeRegion.value);
    const qs = query.toString();
    const [listingBody, discoverBody] = await Promise.all([
      request<ListingsResponse>("/api/v1/discover/listings"),
      request<DiscoverResponse>(`/api/v1/discover/items${qs ? `?${qs}` : ""}`),
    ]);
    listings.value = listingBody.items;
    items.value = discoverBody.items;
    categories.value = discoverBody.categories;
    updatedCount.value = discoverBody.updated_count;
    if (discoverBody.region) region.value = discoverBody.region;
    // 登录 / 切换国家后原来选中的地区可能已不存在，回到「全部地区」避免一直空白。
    if (activeRegion.value && ![ "GLOBAL", region.value.code ].includes(activeRegion.value)) activeRegion.value = "";
  } catch (err) {
    error.value = err instanceof Error ? err.message : "发现页加载失败";
  } finally {
    loading.value = false;
  }
}

function selectCategory(category: string): void {
  activeCategory.value = category;
  void load();
}

function selectRegion(code: string): void {
  activeRegion.value = code;
  void load();
}

const loginPrompt = useLoginPromptStore();
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

function lessLikeThis(): void {
  toast.show("已记录偏好，后续会减少此类内容（推荐参数可在设置中调整）");
}

onMounted(load);
// 登录后等自动执行的操作完成再刷新，避免刷新读到操作前的状态。
watch(
  () => auth.isLoggedIn,
  () => void loginPrompt.whenIdle().then(load),
);
</script>

<template>
  <section>
    <p v-if="loading" class="empty">加载中…</p>
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />

    <template v-else>
      <!-- 为你推荐：单一信息流，分类信息与普通内容合并 -->
      <section class="discover-section">
        <header class="section-head">
          <h2 class="section-title">为你推荐</h2>
          <p class="section-note">
            按频道分类与近 7 天更新排序 · {{ updatedCount }} 条近期更新 ·
            推荐参数可在设置中查看和调整
          </p>
        </header>

        <!-- DiscoverChipRow（MASTER §22.11）：一行横滑，先地区 chip，竖线分隔，再分类 chip -->
        <div class="chip-row" role="toolbar" aria-label="按地区和分类筛选">
          <div class="chip-group" role="group" aria-label="按地区筛选">
            <button
              type="button"
              class="filter-chip"
              :class="{ active: activeRegion === '' }"
              :aria-pressed="activeRegion === ''"
              @click="selectRegion('')"
            >
              全部地区
            </button>
            <button
              type="button"
              class="filter-chip"
              :class="{ active: activeRegion === 'GLOBAL' }"
              :aria-pressed="activeRegion === 'GLOBAL'"
              @click="selectRegion('GLOBAL')"
            >
              国际
            </button>
            <button
              v-if="region.code !== 'GLOBAL'"
              type="button"
              class="filter-chip"
              :class="{ active: activeRegion === region.code }"
              :aria-pressed="activeRegion === region.code"
              @click="selectRegion(region.code)"
            >
              {{ region.name }}
            </button>
          </div>
          <span v-if="categories.length > 0" class="chip-divider" aria-hidden="true"></span>
          <div v-if="categories.length > 0" class="chip-group" role="group" aria-label="按分类筛选">
            <button
              type="button"
              class="filter-chip"
              :class="{ active: activeCategory === '' }"
              :aria-pressed="activeCategory === ''"
              @click="selectCategory('')"
            >
              全部分类
            </button>
            <button
              v-for="category in categories"
              :key="category"
              type="button"
              class="filter-chip"
              :class="{ active: activeCategory === category }"
              :aria-pressed="activeCategory === category"
              @click="selectCategory(category)"
            >
              {{ category }}
            </button>
          </div>
        </div>

        <div v-if="showIntro" class="discover-intro" role="note">
          <span>这里集中展示各频道近 7 天的更新，可以用上面的地区和分类筛选。</span>
          <button type="button" class="intro-close" aria-label="关闭说明，不再显示" @click="showIntro = false">知道了</button>
        </div>

        <EmptyState v-if="!hasContent" title="暂无推荐内容" description="换个分类看看" />

        <ul v-else class="content-list">
          <li
            v-for="entry in feed"
            :key="entry.kind === 'content' ? entry.item.content_id : entry.listing.content_id"
            class="content-card"
            :class="{ 'content-card--listing': entry.kind === 'listing' }"
          >
            <ListingCard v-if="entry.kind === 'listing'" :item="entry.listing" />
            <!-- 普通内容与首页推荐共用同一张帖子卡：来源、许可、举报、推荐理由都由 PostCard 常驻显示 -->
            <PostCard
              v-else
              :content-id="entry.item.content_id"
              :title="entry.item.title"
              :summary="entry.item.summary"
              :channel-name="entry.item.channel_name"
              :channel-id="entry.item.channel_id"
              :certified="entry.item.channel_certified"
              :author-name="entry.item.author_name"
              :author-handle="entry.item.author_handle"
              :source-name="entry.item.source_name"
              :licence-ref="entry.item.licence_ref"
              :canonical-url="entry.item.canonical_url"
              :keywords="entry.item.keywords"
              :image-keys="entry.item.image_keys"
              :video-key="entry.item.video_key"
              :time="entry.item.added_at"
              :show-join="true"
              :is-joined="entry.item.is_joined"
              :liked="entry.item.liked"
              :favorited="entry.item.favorited"
              :reposted="entry.item.reposted"
              :why-text="`为什么推荐：来自「${entry.item.channel_name}」· 近 7 天更新`"
              @join="joinChannel(entry.item)"
              @open="activeContentId = entry.item.content_id"
              @like="toggleLike(entry.item)"
              @favorite="toggleFavorite(entry.item)"
              @repost="repost(entry.item)"
              @less-like="lessLikeThis"
            />
          </li>
        </ul>
        <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
      </section>
    </template>
  </section>
</template>

<style scoped>
.empty {
  padding: var(--sp-6) 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.discover-section {
  display: grid;
  gap: var(--sp-3);
  margin-bottom: var(--sp-6);
}
.section-head {
  display: grid;
  gap: var(--sp-1);
}
.section-title {
  margin: 0;
  font-size: var(--fs-16);
}
.section-note {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 1.6;
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
/* 一行横滑，绝不撑出页面宽度；隐藏滚动条 */
.chip-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  overflow-x: auto;
  white-space: nowrap;
  scrollbar-width: none;
}
.chip-row::-webkit-scrollbar {
  display: none;
}
.chip-group {
  display: flex;
  gap: var(--sp-2);
  flex: none;
}
.chip-divider {
  flex: none;
  width: 1px;
  height: 24px;
  background: var(--line);
}
.filter-chip {
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
.content-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: block;
}
/* 帖子卡自带分隔线与内边距；分类信息卡保持原样，两者在同一条流里 */
.content-card {
  display: block;
}
.content-card--listing {
  padding: var(--sp-3) var(--sp-4);
  border-bottom: 1px solid var(--border);
}
</style>
