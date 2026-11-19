<script setup lang="ts">
// 房间条目列表：加载 /channels/:id/items?season=，游标分页，按 room_type 渲染。
// 负责条目数据加载与进度标记；具体形态的视觉渲染交给 RoomItems 内部按 type 分支。
import { computed, onMounted, ref, watch } from "vue";
import { useToastStore } from "../../stores/toast";
import { useAuthStore } from "../../stores/auth";
import { request, jsonBody, toMessage, type Channel, type RoomItem, type RoomItemsResponse } from "../../api";
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
  isPrivate: boolean;
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

// 新建的剧集不分季（都是第 1 季）；只有旧数据里真有多季的房间才显示季标签
const hasSeasons = computed(() => props.seasons.length > 1);

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

// ---- 推送到频道（房主、公开房间）：后台审核通过后才出现在频道里 ----
const pushOpen = ref(""); // 正在选频道的那条帖子
const pushTarget = ref("");
const pushBusy = ref("");
const officialChannels = ref<Channel[]>([]);

const canPush = (item: RoomItem): boolean => props.isOwner && !props.isPrivate && item.status === "published";

async function openPush(item: RoomItem): Promise<void> {
  pushOpen.value = item.content_id;
  pushTarget.value = "";
  if (officialChannels.value.length) return;
  try {
    const body = await request<{ items: Channel[] }>("/api/v1/channels");
    officialChannels.value = body.items.filter((channel) => channel.kind.startsWith("official"));
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function submitPush(item: RoomItem): Promise<void> {
  if (!pushTarget.value || pushBusy.value) return;
  pushBusy.value = item.content_id;
  try {
    const body = await request<{ status: string; channel_id: string }>(
      `/api/v1/channels/${props.roomId}/pushes/${item.content_id}`,
      jsonBody({ channel_id: pushTarget.value }),
    );
    item.push_status = body.status;
    item.push_channel_name = officialChannels.value.find((channel) => channel.id === body.channel_id)?.name_hans ?? null;
    pushOpen.value = "";
    toast.show("已提交，后台审核通过后会出现在频道里");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    pushBusy.value = "";
  }
}

async function withdrawPush(item: RoomItem): Promise<void> {
  if (pushBusy.value) return;
  pushBusy.value = item.content_id;
  try {
    await request(`/api/v1/channels/${props.roomId}/pushes/${item.content_id}`, { method: "DELETE" });
    item.push_status = null;
    item.push_channel_name = null;
    toast.show("已撤回");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    pushBusy.value = "";
  }
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
          :content-id="item.content_id" :title="item.title" :liked="item.liked" :like-count="item.like_count" :favorited="item.favorited"
          @open="router.push({ name: 'content', params: { id: item.content_id } })"
          @like="reactions.toggleLike(item)" @favorite="reactions.toggleFavorite(item)"
        />
        <div v-if="canPush(item)" class="push-row">
          <template v-if="item.push_status === 'pending' || item.push_status === 'approved'">
            <span>{{ item.push_status === "pending" ? "等待审核" : "已推送" }}：<span data-ugc>{{ item.push_channel_name }}</span></span>
            <button type="button" class="btn btn--ghost btn--sm" :disabled="pushBusy === item.content_id" @click="withdrawPush(item)">撤回</button>
          </template>
          <template v-else>
            <span v-if="item.push_status === 'rejected'">推送被拒绝：<span data-ugc>{{ item.push_channel_name }}</span></span>
            <button v-if="pushOpen !== item.content_id" type="button" class="btn btn--outline btn--sm" @click="openPush(item)">
              {{ item.push_status === "rejected" ? "重新推送" : "推送到频道" }}
            </button>
            <template v-else>
              <select v-model="pushTarget" class="field-input" aria-label="选择要推送到的频道">
                <option value="" disabled>选择频道</option>
                <option v-for="channel in officialChannels" :key="channel.id" :value="channel.id">{{ channel.name_hans }}</option>
              </select>
              <button type="button" class="btn btn--primary btn--sm" :disabled="!pushTarget || pushBusy === item.content_id" @click="submitPush(item)">提交审核</button>
              <button type="button" class="btn btn--ghost btn--sm" @click="pushOpen = ''">取消</button>
            </template>
          </template>
        </div>
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
.push-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  padding: 0 var(--sp-2);
  font-size: var(--fs-13);
  color: var(--muted);
}
.load-more {
  justify-self: center;
}
</style>
