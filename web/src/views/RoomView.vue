<script setup lang="ts">
// 房间详情页：房间头部信息 + 按 room_type 分支渲染条目 + 留言讨论。
// 四种形态（general/series/film/video）通过 RoomItems 内部按 room_type 渲染。
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";
import RoomComments from "../components/RoomComments.vue";
import RoomItems from "../components/room/RoomItems.vue";
import RoomManager from "../components/room/RoomManager.vue";
import RoomSubmissions from "../components/room/RoomSubmissions.vue";
import { request, type MeProfile, type RoomDetail } from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import BaseButton from "../components/base/BaseButton.vue";
import BaseTag from "../components/base/BaseTag.vue";
import ErrorState from "../components/base/ErrorState.vue";
import ReportButton from "../components/common/ReportButton.vue";

const route = useRoute();
const roomId = route.params.id as string;
const auth = useAuthStore();
const toast = useToastStore();

const detail = ref<RoomDetail | null>(null);
const loading = ref(true);
const error = ref("");
const requesting = ref(false);
const reviewingId = ref("");
const joinRequests = ref<{ request_id: string; user_id: string; display_name: string; handle: string }[]>([]);
const myUserId = ref("");

const roomItemsRef = ref<InstanceType<typeof RoomItems> | null>(null);
const roomManagerRef = ref<InstanceType<typeof RoomManager> | null>(null);

// §26.9 CountryGuard：房间所属频道属于其他国家时占位拦截。
const REGION_NAMES: Record<string, string> = { UK: "英国", GLOBAL: "国际" };
const countryName = computed(() => REGION_NAMES[detail.value?.region_code ?? ""] ?? detail.value?.region_code ?? "");
const guardText = computed(() => {
  const country = countryName.value;
  const parent = detail.value?.parent_name_hans;
  const scope = parent ? `${parent}频道` : country ? `${country}频道` : "其他国家频道";
  return country ? `这个房间属于${scope}，切回${country}后恢复` : `这个房间属于其他国家频道，切回对应国家后恢复`;
});

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    detail.value = await request<RoomDetail>(`/api/v1/channels/${roomId}`);
    if (detail.value.is_private && detail.value.is_owner) void loadJoinRequests();
    if (auth.isLoggedIn) void loadMe();
  } catch (err) {
    error.value = err instanceof Error ? err.message : "房间不存在或无法访问";
  } finally {
    loading.value = false;
  }
}

async function loadMe(): Promise<void> {
  try {
    const me = await request<MeProfile>("/api/v1/me");
    myUserId.value = me.user_id;
  } catch {
    // 未登录或 /me 失败：保持空，视为普通访客
  }
}

// 房主或协作者均可审核投稿（后端 _editor_channel 语义）
const canModerate = computed(() => {
  if (!detail.value) return false;
  if (detail.value.is_owner) return true;
  if (!myUserId.value) return false;
  return (detail.value.collaborators ?? []).some((c) => c.user_id === myUserId.value);
});

async function loadJoinRequests(): Promise<void> {
  try {
    const result = await request<{ items: typeof joinRequests.value }>(`/api/v1/channels/${roomId}/join-requests`);
    joinRequests.value = result.items;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "申请列表加载失败");
  }
}

async function requestJoin(): Promise<void> {
  if (requesting.value || !detail.value) return;
  requesting.value = true;
  try {
    await request(`/api/v1/channels/${roomId}/join-requests`, { method: "POST" });
    detail.value.join_request_pending = true;
    toast.show("申请已发送，等待房主审核");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "申请失败，请重试");
  } finally {
    requesting.value = false;
  }
}

async function approveJoin(requestId: string): Promise<void> {
  if (reviewingId.value) return;
  reviewingId.value = requestId;
  try {
    await request(`/api/v1/channels/${roomId}/join-requests/${requestId}/approve`, { method: "POST" });
    joinRequests.value = joinRequests.value.filter((item) => item.request_id !== requestId);
    toast.show("已通过加入申请");
    void load();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "审核失败，请重试");
  } finally {
    reviewingId.value = "";
  }
}

async function rejectJoin(requestId: string): Promise<void> {
  if (reviewingId.value) return;
  reviewingId.value = requestId;
  try {
    await request(`/api/v1/channels/${roomId}/join-requests/${requestId}/reject`, { method: "POST" });
    joinRequests.value = joinRequests.value.filter((item) => item.request_id !== requestId);
    toast.show("已拒绝加入申请");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "审核失败，请重试");
  } finally {
    reviewingId.value = "";
  }
}

function onChanged(): void {
  // 条目增删/移动/重排后：刷新条目列表与房间详情（entry_count 等）
  roomItemsRef.value?.reload();
  void load();
}

function onReorder(contentId: string, direction: "up" | "down"): void {
  roomManagerRef.value?.moveEntry(contentId, direction);
}

onMounted(load);
</script>

<template>
  <section>
    <RouterLink to="/profile" class="back-link">← 我的房间</RouterLink>

    <p v-if="loading" class="empty">加载中…</p>
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />

    <template v-else-if="detail">
      <header class="room-head">
        <h1 class="page-title" data-ugc>{{ detail.name_hans }}</h1>
        <div class="room-tags">
          <BaseTag>{{ detail.room_type }}</BaseTag>
          <BaseTag v-if="detail.certified" variant="link">官方</BaseTag>
          <BaseTag v-else variant="warn">用户自建 · 非官方</BaseTag>
          <BaseTag v-if="detail.is_owner" variant="good">我是房主</BaseTag>
          <BaseTag v-else-if="canModerate" variant="good">我是协作者</BaseTag>
          <BaseTag v-if="detail.is_private" variant="warn">私密房间</BaseTag>
          <ReportButton kind="channel" :id="roomId" compact />
        </div>
        <p v-if="detail.parent_name_hans" class="room-meta">挂在 <span data-ugc>{{ detail.parent_name_hans }}</span></p>
        <p v-if="detail.subscriber_count !== undefined" class="room-meta">
          <template v-if="countryName">{{ countryName }} · </template>{{ detail.subscriber_count }} 人订阅<template v-if="detail.sort_basis"> · 排序：{{ detail.sort_basis }}</template>
        </p>
      </header>

      <!-- §26.9 CountryGuard：其他国家频道 → 占位拦截，隐藏内容区 -->
      <section v-if="detail.region_blocked" class="country-guard" role="status">
        <h2>这个房间在您所在的国家暂不可用</h2>
        <p>{{ guardText }}</p>
      </section>

      <div v-else-if="detail.is_private && !detail.is_owner && !detail.is_joined" class="private-gate" role="status">
        <h2>这是私密房间</h2>
        <p>房间内容仅对已加入的成员开放。申请通过后即可查看条目和讨论。</p>
        <RouterLink v-if="!auth.isLoggedIn" to="/profile" class="btn btn--primary">登录后申请加入</RouterLink>
        <p v-else-if="detail.join_request_pending" class="notice" role="status">申请已提交，等待房主审核。</p>
        <BaseButton v-else :loading="requesting" @click="requestJoin">申请加入</BaseButton>
      </div>

      <section v-else-if="detail.is_private && detail.is_owner" class="join-review" aria-label="加入申请">
        <h2 class="section-title">加入申请</h2>
        <p v-if="!joinRequests.length" class="room-meta">暂无待审核申请</p>
        <div v-for="item in joinRequests" :key="item.request_id" class="join-review__row">
          <span data-ugc>{{ item.display_name }}<small v-if="item.handle"> @{{ item.handle }}</small></span>
          <div class="join-review__actions">
            <BaseButton size="sm" variant="outline" :disabled="Boolean(reviewingId)" @click="rejectJoin(item.request_id)">拒绝</BaseButton>
            <BaseButton size="sm" :loading="reviewingId === item.request_id" :disabled="Boolean(reviewingId)" @click="approveJoin(item.request_id)">通过</BaseButton>
          </div>
        </div>
      </section>

      <template v-else-if="!detail.region_blocked && (!detail.is_private || detail.is_owner || detail.is_joined)">
      <!-- 房主工具条（非 general 房间才可编排条目） -->
      <RoomManager
        v-if="detail.is_owner && detail.room_type !== 'general'"
        :ref="(el) => (roomManagerRef = el as typeof roomManagerRef)"
        :room-id="roomId"
        :room-type="detail.room_type"
        @changed="onChanged"
      />

      <!-- 条目列表（四种形态） -->
      <RoomItems
        :ref="(el) => (roomItemsRef = el as typeof roomItemsRef)"
        :room-id="roomId"
        :room-type="detail.room_type"
        :seasons="detail.seasons ?? []"
        :is-owner="Boolean(detail.is_owner)"
        :sort-basis="detail.sort_basis ?? ''"
        @reorder="onReorder"
      />

      <!-- 投稿 / 审核（房主或协作者看待审队列，普通用户投稿） -->
      <RoomSubmissions
        :room-id="roomId"
        :can-moderate="canModerate"
        @changed="onChanged"
      />

      <!-- 留言讨论 -->
      <h2 class="section-title">讨论</h2>
      <RoomComments :room-id="roomId" :room-name="detail.name_hans" />
      </template>
    </template>
  </section>
</template>

<style scoped>
.back-link {
  display: inline-block;
  margin-bottom: var(--sp-3);
  font-size: var(--fs-13);
}
.page-title {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-21);
  overflow-wrap: anywhere;
}
.room-head {
  display: grid;
  gap: var(--sp-2);
  margin-bottom: var(--sp-6);
  padding-bottom: var(--sp-4);
  border-bottom: 1px solid var(--border);
}
.room-tags {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.room-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.section-title {
  margin: var(--sp-6) 0 var(--sp-3);
  font-size: var(--fs-16);
}
.private-gate {
  display: grid;
  justify-items: start;
  gap: var(--sp-3);
  padding: var(--sp-6);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.country-guard {
  display: grid;
  justify-items: start;
  gap: var(--sp-2);
  padding: var(--sp-6);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.country-guard h2 {
  margin: 0;
  font-size: var(--fs-16);
}
.country-guard p {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.private-gate h2, .private-gate p { margin: 0; }
.private-gate p { color: var(--muted); }
.join-review { margin-bottom: var(--sp-5); }
.join-review__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.join-review__row small { color: var(--muted); }
.join-review__actions { display: flex; gap: var(--sp-2); }
</style>
