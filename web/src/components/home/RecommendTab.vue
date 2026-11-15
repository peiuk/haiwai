<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { RouterLink } from "vue-router";
import ContentDetail from "../ContentDetail.vue";
import PostCard from "../common/PostCard.vue";
import InfiniteSentinel from "../common/InfiniteSentinel.vue";
import HomeComposer from "./HomeComposer.vue";
import { request, type DiscoverItem } from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import { useLoginPromptStore } from "../../stores/loginPrompt";
import { usePostReactions } from "../../composables/usePostReactions";

type RecommendItem = DiscoverItem & {
  reason?: string;
  image_keys?: string[];
  video_key?: string | null;
  liked?: boolean;
  favorited?: boolean;
  reposted?: boolean;
};

const BATCH = 6;
const PAGE = 12;
type ForYouPage = { items: RecommendItem[]; next_cursor?: string };

const auth = useAuthStore();
const toast = useToastStore();
const loginPrompt = useLoginPromptStore();
const items = ref<RecommendItem[]>([]);
const visibleCount = ref(BATCH);
const cursor = ref<string | null>(null);
const order = ref<"ranked" | "time">("ranked");
const loading = ref(false);
const error = ref("");
const pageError = ref(false);
const activeContentId = ref<string | null>(null);
let loadVersion = 0;

const visibleItems = computed(() => items.value.slice(0, visibleCount.value));
const hasMore = computed(() =>
  visibleCount.value < items.value.length ||
  (!!cursor.value && !pageError.value),
);

async function load(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  pageError.value = false;
  items.value = [];
  visibleCount.value = BATCH;
  cursor.value = null;
  try {
    // 游客也走这个接口：不个性化，按新鲜度 / 活跃度 / 官方精选排序，和发现页的时间流不同。
    const body = await request<ForYouPage>(
      `/api/v1/me/feed?tab=foryou&order=${order.value}&limit=${PAGE}`,
    );
    if (version !== loadVersion) return;
    items.value = body.items;
    cursor.value = body.next_cursor ?? null;
  } catch (err) {
    if (version !== loadVersion) return;
    items.value = [];
    error.value = err instanceof Error ? err.message : "推荐内容暂时打不开";
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

async function loadMore(): Promise<void> {
  if (loading.value || pageError.value || !hasMore.value) return;
  // 先消费已加载的池，避免每次滚动都打接口。
  if (visibleCount.value < items.value.length) {
    visibleCount.value = Math.min(visibleCount.value + BATCH, items.value.length);
    return;
  }
  if (!cursor.value) return;
  const version = loadVersion;
  loading.value = true;
  try {
    const body = await request<ForYouPage>(
      `/api/v1/me/feed?tab=foryou&order=${order.value}&limit=${PAGE}&cursor=${encodeURIComponent(cursor.value)}`,
    );
    if (version !== loadVersion) return;
    const seen = new Set(items.value.map((item) => item.content_id));
    const fresh = body.items.filter((item) => !seen.has(item.content_id));
    items.value = [...items.value, ...fresh];
    cursor.value = body.next_cursor ?? null;
    // 无新增且无后续游标时收口，防止哨兵空转。
    if (fresh.length === 0 && !body.next_cursor) cursor.value = null;
    visibleCount.value = Math.min(visibleCount.value + BATCH, items.value.length);
  } catch (err) {
    if (version !== loadVersion) return;
    pageError.value = true;
    error.value = err instanceof Error ? err.message : "更多推荐暂时加载不了";
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

function retry(): void {
  pageError.value = false;
  error.value = "";
  if (!items.value.length) void load();
  else void loadMore();
}

const { toggleLike, toggleFavorite, repost: repostItem } = usePostReactions();

function repost(item: RecommendItem): Promise<void> {
  return repostItem(item, item.channel_id);
}

async function joinChannel(item: RecommendItem): Promise<void> {
  if (!auth.isLoggedIn) {
    loginPrompt.require("登录后就能加入频道，登录成功会自动帮你加入。", () => joinChannel(item));
    return;
  }
  try {
    await request(`/api/v1/me/subscriptions/${item.channel_id}`, { method: "PUT" });
    item.is_joined = true;
    toast.show("已加入频道");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "加入没有成功");
  }
}

// 登录后自动执行的操作（如点赞）完成后再重新加载，保证拿到的是操作后的状态。
watch([() => auth.isLoggedIn, order], () => void loginPrompt.whenIdle().then(load));
void load();
</script>

<template>
  <div class="recommend-tab">
    <div class="rec-note">
      <span>{{ order === "ranked" ? "按推荐排序" : "按时间排序" }}{{ auth.isLoggedIn ? "" : " · 未登录，不做个性化" }}</span>
      <button type="button" class="rec-order" @click="order = order === 'ranked' ? 'time' : 'ranked'">
        {{ order === "ranked" ? "切到时间序" : "切到推荐序" }}
      </button>
    </div>

    <HomeComposer @published="load" />

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="retry" @click="retry">重试</button>
    </p>
    <div v-else-if="!loading && items.length === 0" class="rec-empty">
      <strong>这里还没有可推荐的动态</strong>
      <span>去看看频道，加入感兴趣的话题。</span>
      <RouterLink class="rec-empty-link" to="/?tab=channels">浏览频道</RouterLink>
    </div>
    <p v-else-if="loading && items.length === 0" class="rec-loading">正在加载动态…</p>

    <PostCard
      v-for="item in visibleItems"
      :key="item.content_id"
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
      :time="item.added_at"
      :show-join="true"
      :is-joined="item.is_joined"
      :liked="item.liked"
      :favorited="item.favorited"
      :reposted="item.reposted"
      :why-text="`为什么推荐：${item.reason || `来自「${item.channel_name}」`}`"
      @join="joinChannel(item)"
      @open="activeContentId = item.content_id"
      @like="toggleLike(item)"
      @favorite="toggleFavorite(item)"
      @repost="repost(item)"
      @less-like="toast.show('推荐偏好设置将在后续版本提供')"
    />

    <InfiniteSentinel
      v-if="visibleItems.length"
      :loading="loading"
      :has-more="hasMore"
      hint="继续下拉加载更多动态"
      @load="loadMore"
    />

    <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
  </div>
</template>

<style scoped>
.rec-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 32px;
  padding: 0 16px;
  color: var(--muted);
  font-size: var(--fs-12);
}
.rec-order {
  flex: none;
  min-height: 32px;
  padding: 0 8px;
  border-radius: var(--r-pill);
  color: var(--accent-ink);
  font-size: var(--fs-12);
}
.rec-order:hover { background: var(--accent-soft); }
.rec-empty {
  display: grid;
  justify-items: start;
  gap: 6px;
  padding: 32px 20px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: var(--fs-13);
}
.rec-empty strong { color: var(--text); font-size: var(--fs-15); }
.rec-empty-link { margin-top: 6px; color: var(--accent-ink); font-weight: 700; }
.rec-loading { padding: 24px 20px; color: var(--muted); font-size: var(--fs-13); }
.retry {
  margin-left: 8px;
  border: 0;
  background: transparent;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}
@media (max-width: 759px) { .rec-note { padding: 0 12px; } }
</style>
