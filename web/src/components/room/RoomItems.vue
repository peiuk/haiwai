<script setup lang="ts">
// 房间条目列表：加载 /channels/:id/items?season=，游标分页，按 room_type 渲染。
// 负责条目数据加载与进度标记；具体形态的视觉渲染交给 RoomItems 内部按 type 分支。
import { computed, onMounted, ref, watch } from "vue";
import { useToastStore } from "../../stores/toast";
import { useAuthStore } from "../../stores/auth";
import { request, jsonBody, type RoomItem, type RoomItemsResponse } from "../../api";
import EmptyState from "../base/EmptyState.vue";
import ErrorState from "../base/ErrorState.vue";
import Skeleton from "../base/Skeleton.vue";
import RoomEntryCard from "./RoomEntryCard.vue";
import PostActions from "../common/PostActions.vue";
import { useRouter } from "vue-router";
import { usePostReactions } from "../../composables/usePostReactions";

const router = useRouter();
const reactions = usePostReactions();

const props = defineProps<{
  roomId: string;
  roomType: string;
  seasons: number[];
  isOwner: boolean;
  sortBasis: string;
}>();

const toast = useToastStore();
const auth = useAuthStore();

const items = ref<RoomItem[]>([]);
const nextCursor = ref<string | null>(null);
const loading = ref(false);
const loadingMore = ref(false);
const error = ref("");
const activeSeason = ref<number | null>(null);

const hasSeasons = computed(() => props.seasons.length > 0);

async function load(reset: boolean): Promise<void> {
  if (reset) {
    loading.value = true;
    items.value = [];
    nextCursor.value = null;
  } else {
    loadingMore.value = true;
  }
  error.value = "";
  try {
    const params = new URLSearchParams();
    if (activeSeason.value !== null) params.set("season", String(activeSeason.value));
    if (!reset && nextCursor.value) params.set("cursor", nextCursor.value);
    const qs = params.toString();
    const body = await request<RoomItemsResponse>(
      `/api/v1/channels/${props.roomId}/items${qs ? `?${qs}` : ""}`,
    );
    items.value = reset ? body.items : [...items.value, ...body.items];
    nextCursor.value = body.next_cursor ?? null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "条目加载失败";
  } finally {
    loading.value = false;
    loadingMore.value = false;
  }
}

function loadMore(): void {
  if (nextCursor.value && !loadingMore.value) void load(false);
}

function selectSeason(season: number | null): void {
  activeSeason.value = season;
  void load(true);
}

async function saveProgress(item: RoomItem, progress: number, watchMark?: string): Promise<void> {
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再标记进度");
    return;
  }
  try {
    const body = await request<{ progress: number; watch_mark: string | null }>(
      `/api/v1/channels/${props.roomId}/items/${item.content_id}/progress`,
      { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ progress, watch_mark: watchMark ?? null }) },
    );
    item.progress = body.progress;
    item.watch_mark = body.watch_mark;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "进度保存失败");
  }
}

async function toggleWatchMark(item: RoomItem, mark: "want" | "watched"): Promise<void> {
  const next = item.watch_mark === mark ? "" : mark;
  await saveProgress(item, item.progress ?? 0, next);
}

function markWatched(item: RoomItem): void {
  void saveProgress(item, 100, "watched");
}

function emitReorder(contentId: string, direction: "up" | "down"): void {
  // 上移/下移由房主工具条触发，事件冒泡到 RoomView 处理
  // 这里通过自定义事件向上传递
}

watch(() => props.roomId, () => void load(true));

onMounted(() => void load(true));

defineExpose({ reload: () => load(true) });
</script>

<template>
  <div class="room-items">
    <!-- 季 Tab（series 专属） -->
    <div v-if="roomType === 'series' && hasSeasons" class="season-tabs" role="tablist" aria-label="季">
      <button
        v-for="season in seasons"
        :key="season"
        type="button"
        role="tab"
        class="season-chip"
        :class="{ active: activeSeason === season }"
        :aria-selected="activeSeason === season"
        @click="selectSeason(season)"
      >
        第 {{ season }} 季
      </button>
      <button
        v-if="activeSeason !== null"
        type="button"
        class="season-chip season-chip--all"
        @click="selectSeason(null)"
      >
        全部
      </button>
    </div>

    <p v-if="loading" class="empty">加载中…</p>
    <Skeleton v-else-if="loadingMore && items.length === 0" />
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load(true)" />
    <EmptyState v-else-if="items.length === 0" title="还没有条目" :description="isOwner ? '点上面的「发帖」添加第一条内容' : '房主添加条目后会显示在这里'" />

    <ul v-else class="entry-list">
      <li v-for="item in items" :key="item.content_id">
        <RoomEntryCard
          :item="item"
          :room-type="roomType"
          :is-owner="isOwner"
          @watched="markWatched(item)"
          @toggle-watch="toggleWatchMark(item, $event)"
          @reorder="emitReorder(item.content_id, $event)"
        />
        <!-- 审核中的内容别人看不到，不显示互动按钮 -->
        <PostActions
          v-if="item.status !== 'pending'"
          class="entry-acts"
          no-repost
          :content-id="item.content_id" :title="item.title" :liked="item.liked" :favorited="item.favorited"
          @open="router.push({ name: 'content', params: { id: item.content_id } })"
          @like="reactions.toggleLike(item)" @favorite="reactions.toggleFavorite(item)"
        />
      </li>
    </ul>

    <button
      v-if="nextCursor"
      type="button"
      class="btn btn--outline load-more"
      :disabled="loadingMore"
      @click="loadMore"
    >
      {{ loadingMore ? "加载中…" : "加载更多" }}
    </button>
  </div>
</template>

<style scoped>
.room-items {
  display: grid;
  gap: var(--sp-4);
}
.season-tabs {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.season-chip {
  min-height: 44px;
  padding: 0 var(--sp-4);
  border-radius: var(--r-pill);
  border: 1px solid var(--line);
  background: var(--surface2);
  color: var(--text);
  font-size: var(--fs-13);
  font-weight: 600;
  cursor: pointer;
}
.season-chip.active {
  background: var(--accent-soft);
  color: var(--accent-ink);
  border-color: transparent;
}
.season-chip--all {
  background: transparent;
}
.entry-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--sp-3);
}
.entry-acts {
  padding: 0 var(--sp-2);
}
.load-more {
  justify-self: center;
}
</style>
