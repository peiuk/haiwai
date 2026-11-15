<script setup lang="ts">
// 房间详情页：房间头部信息 + 按 room_type 分支渲染条目 + 留言讨论。
// 四种形态（general/series/film/video）通过 RoomItems 内部按 room_type 渲染。
import { computed, onMounted, ref, watch } from "vue";
import { setDocumentTitle } from "../i18n/uiLang";
import { useRoute } from "vue-router";
import RoomComments from "../components/RoomComments.vue";
import RoomItems from "../components/room/RoomItems.vue";
import RoomManager from "../components/room/RoomManager.vue";
import RoomSubmissions from "../components/room/RoomSubmissions.vue";
import { jsonBody, request, type MeProfile, type RoomDetail } from "../api";
import { ROOM_TYPES } from "../utils/room";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import BaseButton from "../components/base/BaseButton.vue";
import TextField from "../components/base/TextField.vue";
import SelectField from "../components/base/SelectField.vue";
import Checkbox from "../components/base/Checkbox.vue";
import BaseTag from "../components/base/BaseTag.vue";
import ErrorState from "../components/base/ErrorState.vue";
import ReportButton from "../components/common/ReportButton.vue";
import UploadField from "../components/common/UploadField.vue";

const route = useRoute();
const roomId = route.params.id as string;
const auth = useAuthStore();
const toast = useToastStore();

const detail = ref<RoomDetail | null>(null);
// 网页标题带上房间名，多开标签页时分得清
watch(
  () => detail.value?.name_hans,
  (name) => {
    if (name) setDocumentTitle(`${name} · 海外圈`);
  },
);
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

// 新建的房间要等管理员审核：房主先发内容，任一条审核通过后房间自动上线
const pending = computed(() => detail.value?.review_status === "pending");

// ---- 房主改房间（名字、类型；剧集房间还有封面图）----
const editing = ref(false);
const editName = ref("");
const editType = ref("general");
const editCover = ref("");
const editPrivate = ref(false);
const saving = ref(false);

function startEdit(): void {
  if (!detail.value) return;
  editName.value = detail.value.name_hans;
  editType.value = detail.value.room_type;
  editCover.value = detail.value.cover_key ?? "";
  editPrivate.value = Boolean(detail.value.is_private);
  editing.value = true;
}

async function saveEdit(): Promise<void> {
  const name = editName.value.trim();
  if (!name) {
    toast.show("房间名不能为空");
    return;
  }
  saving.value = true;
  try {
    // 只有剧集房间提交封面；空字符串表示去掉封面
    const cover = editType.value === "series" ? { cover_key: editCover.value } : {};
    await request(`/api/v1/channels/${roomId}`, { ...jsonBody({ name, room_type: editType.value, is_private: editPrivate.value, ...cover }), method: "PATCH" });
    editing.value = false;
    toast.show("房间已更新");
    onChanged();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "保存没有成功");
  } finally {
    saving.value = false;
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
        <img
          v-if="detail.room_type === 'series' && detail.cover_key"
          class="room-cover"
          :src="`/api/v1/uploads/${detail.cover_key}`"
          :alt="`${detail.name_hans} 封面`"
        />
        <h1 class="page-title" data-ugc>{{ detail.name_hans }}</h1>
        <div class="room-tags">
          <BaseTag>{{ detail.room_type_label || detail.room_type }}</BaseTag>
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
        <div v-if="canModerate && !editing" class="room-head__actions">
          <!-- 综合讨论房间：房主 / 协作者发帖走「发布内容」页（图片、视频、话题都有），预选这个房间 -->
          <RouterLink
            v-if="detail.room_type === 'general' && !detail.region_blocked"
            class="btn btn--primary btn--sm"
            :to="{ name: 'publish', query: { channel: roomId } }"
          >发帖</RouterLink>
          <BaseButton v-if="detail.is_owner" class="room-edit-btn" size="sm" variant="outline" @click="startEdit">编辑房间</BaseButton>
        </div>
        <form v-if="editing" class="room-edit" @submit.prevent="saveEdit">
          <TextField id="room-edit-name" v-model="editName" label="房间名" required />
          <SelectField id="room-edit-type" v-model="editType" label="类型" :options="[...ROOM_TYPES]" />
          <Checkbox id="room-edit-private" v-model="editPrivate" label="私密房间（只有成员能看到房间内容，加入要经你同意）" />
          <p v-if="detail.is_private && !editPrivate" class="room-meta" role="note">
            改成公开后，房间里已有的帖子和讨论所有人都能看到，任何人都能直接加入；待审的加入申请会清掉。
          </p>
          <p v-else-if="!detail.is_private && editPrivate" class="room-meta" role="note">
            改成私密后，只有现有成员能看到内容；已经推到频道里的帖子会撤回。
          </p>
          <UploadField
            v-if="editType === 'series'"
            id="room-edit-cover"
            v-model="editCover"
            label="封面图片（可选）"
            accept="image/jpeg,image/png,image/webp"
            :max-mb="5"
            hint="显示在房间页顶部，建议横图"
          />
          <div class="room-edit__actions">
            <BaseButton size="sm" variant="outline" type="button" @click="editing = false">取消</BaseButton>
            <BaseButton size="sm" type="submit" :loading="saving">保存</BaseButton>
          </div>
        </form>
      </header>

      <p v-if="pending && canModerate" class="notice room-pending" role="status">
        房间正在审核，暂时只有你和协作者能看到。先发一条内容，管理员审核通过后房间就会公开。
      </p>

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

      <!-- 加入申请和下面的内容区各自独立判断：以前它们连在同一串 v-else-if 里，
           私密房间的房主命中这一段后内容区就不渲染了，看不到帖子，也没有发帖入口。 -->
      <section v-if="!detail.region_blocked && detail.is_private && detail.is_owner" class="join-review" aria-label="加入申请">
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

      <template v-if="!detail.region_blocked && (!detail.is_private || detail.is_owner || detail.is_joined)">
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

      <!-- 留言讨论：房间上线后才开放 -->
      <template v-if="!pending">
        <h2 class="section-title">讨论</h2>
        <RoomComments :room-id="roomId" :room-name="detail.name_hans" />
      </template>
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
.room-cover {
  width: 100%;
  max-height: 280px;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  border-radius: var(--r-lg);
  background: var(--surface2);
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
.room-head__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
}
.room-edit-btn {
  width: auto;
}
.room-edit {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.room-edit__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
}
.room-pending {
  margin: var(--sp-3) 0;
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
