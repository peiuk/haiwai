<script setup lang="ts">
// 搜索结果页（/search?q=&f=）：内容 / 用户 / 频道三个 Tab，对齐 X 的搜索结果页。
// 搜索词由顶栏搜索框写进 URL，这里只读 URL，所以结果可以分享、刷新、后退。
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request, type SearchResponse } from "../api";
import { useAuthStore } from "../stores/auth";
import { usePostReactions } from "../composables/usePostReactions";
import PostCard from "../components/common/PostCard.vue";
import ContentDetail from "../components/ContentDetail.vue";
import Avatar from "../components/base/Avatar.vue";
import EmptyState from "../components/base/EmptyState.vue";
import ErrorState from "../components/base/ErrorState.vue";

const TABS = [
  { id: "top", label: "内容" },
  { id: "user", label: "用户" },
  { id: "channel", label: "频道" },
] as const;
type TabId = (typeof TABS)[number]["id"];

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const { toggleLike, toggleFavorite, repost } = usePostReactions();

const q = computed(() => (typeof route.query.q === "string" ? route.query.q.trim() : ""));
const tab = computed<TabId>(() => TABS.find((t) => t.id === route.query.f)?.id ?? "top");

const results = ref<SearchResponse>({ users: [], channels: [], contents: [] });
const loading = ref(false);
const error = ref("");
const activeContentId = ref<string | null>(null);

async function load(): Promise<void> {
  const term = q.value;
  if (!term) {
    results.value = { users: [], channels: [], contents: [] };
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const body = await request<SearchResponse>(`/api/v1/search?q=${encodeURIComponent(term)}`);
    if (term === q.value) results.value = body;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "搜索没有成功";
  } finally {
    loading.value = false;
  }
}

// 搜索词变了重新搜；登录状态变了也重搜一次，拿到自己的点赞 / 收藏状态
watch([q, () => auth.isLoggedIn], () => void load(), { immediate: true });

function setTab(id: TabId): void {
  router.replace({ query: { ...route.query, f: id === "top" ? undefined : id } });
}
</script>

<template>
  <section class="search-page">
    <div class="tablist" role="tablist" aria-label="搜索结果类型">
      <button
        v-for="t in TABS"
        :key="t.id"
        type="button"
        role="tab"
        class="tab"
        :class="{ active: tab === t.id }"
        :aria-selected="tab === t.id"
        @click="setTab(t.id)"
      >
        {{ t.label }}
      </button>
    </div>

    <EmptyState v-if="!q" title="输入关键词开始搜索，可以搜内容、频道、@用户名或 #话题" />
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />
    <p v-else-if="loading" class="search-hint" role="status">搜索中…</p>

    <template v-else-if="tab === 'top'">
      <EmptyState v-if="!results.contents.length" :title="`没有找到「${q}」相关的内容`" />
      <ul v-else class="search-list">
        <li v-for="item in results.contents" :key="item.content_id">
          <PostCard
            :content-id="item.content_id"
            :title="item.title"
            :summary="item.summary"
            :channel-name="item.channel_name"
            :channel-id="item.channel_id ?? ''"
            :author-name="item.author_name"
            :author-handle="item.author_handle"
            :source-name="item.source_name"
            :licence-ref="item.licence_ref"
            :canonical-url="item.canonical_url"
            :keywords="item.keywords"
            :image-keys="item.image_keys"
            :video-key="item.video_key"
            :time="item.published_at ?? ''"
            :liked="item.liked"
            :favorited="item.favorited"
            :reposted="item.reposted"
            @open="activeContentId = item.content_id"
            @like="toggleLike(item)"
            @favorite="toggleFavorite(item)"
            @repost="repost(item, item.channel_id)"
          />
        </li>
      </ul>
    </template>

    <template v-else-if="tab === 'user'">
      <EmptyState v-if="!results.users.length" :title="`没有找到「${q}」相关的用户`" />
      <ul v-else class="search-list">
        <li v-for="u in results.users" :key="u.user_id">
          <RouterLink class="search-row" :to="{ name: 'user', params: { id: u.user_id } }">
            <Avatar :name="u.display_name" :size="44" :tone="u.avatar_tone" />
            <span class="search-row-main">
              <strong data-ugc>{{ u.display_name }}</strong>
              <small>
                <template v-if="u.handle">@{{ u.handle }}</template>
                <template v-if="u.city_label"> · {{ u.city_label }}</template>
              </small>
            </span>
          </RouterLink>
        </li>
      </ul>
    </template>

    <template v-else>
      <EmptyState v-if="!results.channels.length" :title="`没有找到「${q}」相关的频道`" />
      <ul v-else class="search-list">
        <li v-for="ch in results.channels" :key="ch.id">
          <RouterLink class="search-row" :to="{ name: ch.kind === 'room' ? 'room' : 'channel', params: { id: ch.id } }">
            <Avatar :name="ch.name_hans" :size="44" kind="channel" />
            <span class="search-row-main">
              <strong data-ugc>{{ ch.name_hans }}</strong>
              <small>{{ ch.kind === "room" ? "房间" : "频道" }}</small>
            </span>
          </RouterLink>
        </li>
      </ul>
    </template>

    <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
  </section>
</template>

<style scoped>
.tablist {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  border-bottom: 1px solid var(--border);
}
.tab {
  min-height: 48px;
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-15);
  font-weight: var(--fw-semibold);
  cursor: pointer;
}
.tab:hover {
  background: var(--hover);
}
.tab.active {
  color: var(--text);
  font-weight: var(--fw-bold);
  border-bottom-color: var(--accent-strong);
}
.search-hint {
  padding: var(--sp-6) 0;
  color: var(--muted);
  font-size: var(--fs-14);
  text-align: center;
}
.search-page :deep(.empty) {
  padding: var(--sp-6) var(--sp-4);
  color: var(--muted);
  text-align: center;
}
.search-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.search-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-2);
  border-bottom: 1px solid var(--border);
  color: var(--text);
  text-decoration: none;
}
.search-row:hover {
  background: var(--hover);
}
.search-row-main {
  display: grid;
  min-width: 0;
}
.search-row-main strong,
.search-row-main small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.search-row-main small {
  color: var(--muted);
  font-size: var(--fs-13);
}
</style>
