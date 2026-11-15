<script setup lang="ts">
// 「正在关注」Tab：关注流 + 点赞/收藏/转发 + 详情 + 游标加载更多。
// 帖子卡使用统一的 PostCard（X 式），交互透传。
import { computed, ref, watch } from "vue";
import ContentDetail from "../ContentDetail.vue";
import PostCard from "../common/PostCard.vue";
import InfiniteSentinel from "../common/InfiniteSentinel.vue";
import {
  jsonBody,
  request,
  type FeedItem,
  type FeedResponse,
} from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import { useLoginPromptStore } from "../../stores/loginPrompt";
import { usePostReactions } from "../../composables/usePostReactions";

const auth = useAuthStore();
const toast = useToastStore();

const feed = ref<FeedItem[]>([]);
const cursor = ref<string | null>(null);
const loading = ref(false);
const error = ref("");
const pageError = ref(false);
const activeContentId = ref<string | null>(null);
const reportCases = ref<Record<string, string>>({});

const hasMore = computed(() => !!cursor.value && !pageError.value);

async function load(reset = true): Promise<void> {
  if (!auth.isLoggedIn) {
    feed.value = [];
    cursor.value = null;
    return;
  }
  if (!reset && (loading.value || !cursor.value || pageError.value)) return;
  loading.value = true;
  error.value = "";
  try {
    const q = cursor.value && !reset ? `?cursor=${encodeURIComponent(cursor.value)}` : "";
    const body = await request<FeedResponse>(`/api/v1/me/feed${q}`);
    if (reset) {
      feed.value = body.items;
    } else {
      const seen = new Set(feed.value.map((item) => item.content_id));
      feed.value = [...feed.value, ...body.items.filter((item) => !seen.has(item.content_id))];
    }
    cursor.value = body.next_cursor ?? null;
    // 空页或无游标时收口，避免哨兵在视口内反复触发。
    if (!reset && body.items.length === 0) cursor.value = null;
    // 用户浏览关注流即视为已读，上报 seen_at，使未读角标/未读标记在下次加载时正确清零。
    if (reset && feed.value.some((item) => item.is_unread)) {
      void request("/api/v1/me/feed/seen", { method: "POST" }).catch(() => undefined);
    }
  } catch (err) {
    if (reset) {
      feed.value = [];
    } else {
      pageError.value = true;
    }
    error.value = err instanceof Error ? err.message : "关注流需要重新登录";
  } finally {
    loading.value = false;
  }
}

function retry(): void {
  pageError.value = false;
  error.value = "";
  void load(feed.value.length === 0);
}

const { toggleLike, toggleFavorite, repost: repostItem } = usePostReactions();

function repost(item: FeedItem): Promise<void> {
  return repostItem(item, item.channel_id);
}

function onReported(contentId: string, caseId: string): void {
  reportCases.value = { ...reportCases.value, [contentId]: caseId };
}

async function removeReported(contentId: string): Promise<void> {
  const caseId = reportCases.value[contentId];
  if (!caseId) return;
  try {
    await request(`/api/v1/moderation/cases/${caseId}/decision`, jsonBody({ decision: "remove" }));
    toast.show("已从关注流下架");
    await load();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "下架没有成功");
  }
}

function openDetail(item: FeedItem): void {
  activeContentId.value = item.content_id;
}

defineExpose({ reload: () => load(true) });

// 首页被缓存后不会重新创建，登录状态变化时要主动重新加载。
watch(
  () => auth.isLoggedIn,
  () => void useLoginPromptStore().whenIdle().then(() => load(true)),
);

load();
</script>

<template>
  <div class="feed-tab">
    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="retry" @click="retry">重试</button>
    </p>

    <p v-if="!auth.isLoggedIn" class="empty">注册或登录后，加入频道即可在这里看到内容。</p>
    <p v-else-if="!loading && feed.length === 0" class="empty">加入频道后，这里按时间显示内容。</p>

    <p class="feed-note">严格按时间排序 · 仅显示已加入的频道</p>

    <PostCard
      v-for="item in feed"
      :key="item.content_id"
      :content-id="item.content_id"
      :title="item.title"
      :summary="item.summary"
      :channel-name="item.channel_name || item.author_name"
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
      :pinned="item.pinned"
      :liked="item.liked"
      :favorited="item.favorited"
      :reposted="item.reposted"
      :unread="item.is_unread"
      @like="toggleLike(item)"
      @favorite="toggleFavorite(item)"
      @repost="repost(item)"
      @open="openDetail(item)"
      @reported="onReported(item.content_id, $event)"
    >
      <template v-if="reportCases[item.content_id]" #extra>
        <button class="btn btn--ghost btn--sm" type="button" @click="removeReported(item.content_id)">下架</button>
      </template>
    </PostCard>

    <InfiniteSentinel
      v-if="auth.isLoggedIn && feed.length"
      :loading="loading"
      :has-more="hasMore"
      hint="继续下拉加载更多动态"
      @load="load(false)"
    />

    <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
  </div>
</template>

<style scoped>
.feed-tab {
  display: grid;
  gap: var(--sp-3);
}
.feed-note {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.retry {
  margin-left: 8px;
  border: 0;
  background: transparent;
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}
</style>
