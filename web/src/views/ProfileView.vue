<script setup lang="ts">
// 我的页：对齐原型 prototype-x-style.html 的 renderMe() —— 单页分区列表式。
// 顶部 me-card（头像/昵称/副行/编辑资料）→ 我的房间 / 我的帖子 / 收藏 / 我的举报 /
// 设置 / 私信 / 隐私与数据 各 me-section 垂直排列。
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  jsonBody,
  request,
  toMessage,
  type MeProfile,
  type BlocksResponse,
  type FavoritesResponse,
  type MyPostsResponse,
  type MyRoomsResponse,
  type OwnRoom,
  type PrefsResponse,
  type Subscription,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useThemeStore } from "../stores/theme";
import { useToastStore } from "../stores/toast";
import Avatar from "../components/base/Avatar.vue";
import BaseIcon from "../components/base/BaseIcon.vue";
import BaseButton from "../components/base/BaseButton.vue";
import Modal from "../components/base/Modal.vue";
import { hasOwnTitle } from "../utils/post";
import { ROOM_TYPES } from "../utils/room";
import AccountPanel from "../components/profile/AccountPanel.vue";
import ProfileCard from "../components/profile/ProfileCard.vue";

const auth = useAuthStore();
const theme = useThemeStore();
const toast = useToastStore();
const router = useRouter();

// ---- 我的资料（顶卡）----
type Profile = {
  user_id: string;
  display_name: string;
  handle: string;
  avatar_tone: string;
  city_label: string;
  script_pref: string;
};
const profile = ref<Profile | null>(null);

// ---- 我的房间 ----
const rooms = ref<OwnRoom[]>([]);
const roomCount = ref(0);
const roomNextCursor = ref<string | null>(null);
const roomsLoadingMore = ref(false);
// 自己建的和加入别人的分两组；接口按「先自建、后加入」分页返回，role 区分
const roomGroups = computed(() => [
  { key: "owner", title: "我建的房间", empty: "还没有创建房间。", items: rooms.value.filter((r) => r.role === "owner") },
  { key: "member", title: "我加入的房间", empty: "还没有加入别人的房间。", items: rooms.value.filter((r) => r.role !== "owner") },
]);

// ---- 我的帖子 ----
const posts = ref<MyPostsResponse["items"]>([]);

// ---- 收藏 ----
const favorites = ref<FavoritesResponse["items"]>([]);
const savedCount = ref(0);
const followedCount = ref(0);
const favoritesOpen = ref(false);
const subscriptions = ref<Subscription[]>([]);

// ---- 我的举报 ----
type Report = {
  case_id: string;
  reason: string;
  reason_text: string;
  detail: string;
  status: string;
  sla: string;
  created_at: string;
};
const reports = ref<Report[]>([]);

// ---- 私信 / 设置 ----
const dmAllow = ref(false);
const blocks = ref<BlocksResponse["items"]>([]);
const consentVersion = ref<string | null>(null);

// ---- 状态 ----
const loading = ref(true);
const error = ref("");
const partialError = ref(false);

async function loadAll(): Promise<void> {
  loading.value = true;
  error.value = "";
  partialError.value = false;
  if (!auth.isLoggedIn) {
    profile.value = null;
    loading.value = false;
    return;
  }
  try {
    profile.value = await request<Profile>("/api/v1/me");
    const [roomBody, postBody, favBody, subscriptionBody, reportBody, meBody, prefs, blockBody] =
      await Promise.allSettled([
        request<MyRoomsResponse>("/api/v1/me/channels"),
        request<MyPostsResponse>("/api/v1/me/posts"),
        request<FavoritesResponse>("/api/v1/me/favorites"),
        request<{ items: Subscription[] }>("/api/v1/me/subscriptions"),
        request<{ items: Report[] }>("/api/v1/me/reports"),
        request<MeProfile>("/api/v1/me"),
        request<PrefsResponse>("/api/v1/me/prefs"),
        request<BlocksResponse>("/api/v1/me/blocks"),
      ]);
    partialError.value = [roomBody, postBody, favBody, subscriptionBody, reportBody, meBody, prefs, blockBody].some((result) => result.status === "rejected");
    if (roomBody.status === "fulfilled") {
      rooms.value = roomBody.value.items;
      roomCount.value = roomBody.value.owned_count;
      roomNextCursor.value = roomBody.value.next_cursor ?? null;
    }
    if (postBody.status === "fulfilled") posts.value = postBody.value.items;
    if (favBody.status === "fulfilled") {
      favorites.value = favBody.value.items;
      savedCount.value = favBody.value.saved_count;
      followedCount.value = favBody.value.followed_count;
    }
    if (subscriptionBody.status === "fulfilled") subscriptions.value = subscriptionBody.value.items;
    if (reportBody.status === "fulfilled") reports.value = reportBody.value.items;
    if (meBody.status === "fulfilled") consentVersion.value = meBody.value.consent_version;
    if (prefs.status === "fulfilled") dmAllow.value = prefs.value.dm_allow_strangers;
    if (blockBody.status === "fulfilled") blocks.value = blockBody.value.items;
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    loading.value = false;
  }
}

// ---- 状态文案 ----
// ---- 我的分类信息：续期 / 结案 ----
const listingBusy = ref("");

async function listingAction(contentId: string, action: "renew" | "close"): Promise<void> {
  listingBusy.value = contentId;
  try {
    await request(`/api/v1/listings/${contentId}/${action}`, jsonBody(action === "close" ? { reason: "withdrawn" } : {}));
    toast.show(action === "close" ? "已结案，联系方式已关闭" : "已续期，30 天后到期");
    posts.value = (await request<MyPostsResponse>("/api/v1/me/posts")).items;
  } catch (err) {
    toast.show(toMessage(err)); // 例如还没到可以续期的时间（到期前 3 天内才能续）
  } finally {
    listingBusy.value = "";
  }
}

function statusLabel(status: string): string {
  return ({ published: "已公开", pending: "审核中", rejected: "未通过", removed: "已下架", withdrawn: "已结案" } as Record<string, string>)[status] ?? status;
}
function reportStatusLabel(status: string): string {
  return ({ open: "处理中", resolved: "已处理", dismissed: "已驳回" } as Record<string, string>)[status] ?? status;
}
function ago(iso: string): string {
  const t = new Date(iso).getTime();
  const d = Math.max(0, Date.now() - t);
  const m = Math.floor(d / 60000);
  if (m < 1) return "刚刚";
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  if (h < 48) return "昨天";
  return `${Math.floor(h / 24)} 天前`;
}

// ---- 私信设置 ----
const prefsBusy = ref(false);
async function toggleDm(): Promise<void> {
  prefsBusy.value = true;
  try {
    const body = await request<PrefsResponse>("/api/v1/me/prefs", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ dm_allow_strangers: !dmAllow.value }),
    });
    dmAllow.value = body.dm_allow_strangers;
    toast.show(body.dm_allow_strangers ? "已允许陌生人私信请求" : "已关闭陌生人私信");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    prefsBusy.value = false;
  }
}

async function unblock(userId: string): Promise<void> {
  try {
    await request(`/api/v1/me/blocks/${userId}`, { method: "DELETE" });
    blocks.value = blocks.value.filter((b) => b.user_id !== userId);
    toast.show("已解除屏蔽");
  } catch (err) {
    toast.show(toMessage(err));
  }
}

// ---- 删除账号 ----
const deleteOpen = ref(false);
const deleteBusy = ref(false);

async function deleteAccount(): Promise<void> {
  deleteBusy.value = true;
  try {
    await request("/api/v1/me", { method: "DELETE" });
    deleteOpen.value = false;
    auth.logout();
    toast.show("账号已删除");
    void router.push("/");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    deleteBusy.value = false;
  }
}

function openRoom(id: string): void {
  void router.push({ name: "room", params: { id } });
}

async function loadMoreRooms(): Promise<void> {
  if (!roomNextCursor.value || roomsLoadingMore.value) return;
  roomsLoadingMore.value = true;
  try {
    const body = await request<MyRoomsResponse>(`/api/v1/me/channels?cursor=${encodeURIComponent(roomNextCursor.value)}`);
    rooms.value = [...rooms.value, ...body.items];
    roomNextCursor.value = body.next_cursor ?? null;
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    roomsLoadingMore.value = false;
  }
}

// ---- 创建房间 ----

// 房间不属于任何频道；想出现在某个频道里，由官方指定房间位，或把帖子推送到频道（审核后）。
const roomForm = ref({
  name: "",
  room_type: "general",
  is_private: false,
});
const roomFormOpen = ref(false);
const roomFormBusy = ref(false);
const roomFormError = ref("");

function openCreateRoom(): void {
  roomForm.value = { name: "", room_type: "general", is_private: false };
  roomFormError.value = "";
  roomFormOpen.value = true;
}

async function submitCreateRoom(): Promise<void> {
  roomFormError.value = "";
  roomFormBusy.value = true;
  try {
    await request("/api/v1/channels", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(roomForm.value),
    });
    toast.show("房间已提交，审核通过后公开");
    roomFormOpen.value = false;
    void loadAll();
  } catch (err) {
    roomFormError.value = toMessage(err);
  } finally {
    roomFormBusy.value = false;
  }
}

onMounted(loadAll);

// 登录态变化 → 重新加载分区数据（登录后显示分区列表，退出后回到账号面板）
watch(
  () => auth.isLoggedIn,
  () => {
    void loadAll();
  },
);
</script>

<template>
  <section class="profile-view">
    <h1 class="page-title">我的</h1>

    <p v-if="loading" class="muted">正在加载…</p>
    <div v-else-if="error" class="load-error" role="alert">
      <p class="error">{{ error }}</p>
      <BaseButton variant="outline" size="sm" @click="loadAll">重试</BaseButton>
    </div>

    <template v-else-if="auth.isLoggedIn && profile">
      <div v-if="partialError" class="load-error" role="status">
        <p class="muted">部分资料暂时无法加载。</p>
        <BaseButton variant="outline" size="sm" @click="loadAll">重新加载</BaseButton>
      </div>
      <!-- 顶卡（ProfileCard 承担头像卡 + 编辑资料）-->
      <ProfileCard />

      <!-- 我的房间 -->
      <div class="me-section">
        <h3>我的房间 <span>{{ rooms.length }} 个</span>
          <BaseButton class="section-btn" variant="outline" size="sm" @click="openCreateRoom">创建房间</BaseButton>
        </h3>
        <div v-for="group in roomGroups" :key="group.key" class="rooms-group">
          <h4>{{ group.title }} <span>{{ group.items.length }} 个</span></h4>
          <p v-if="!group.items.length && !roomNextCursor" class="me-empty">{{ group.empty }}</p>
          <button
            v-for="room in group.items"
            :key="room.channel_id"
            type="button"
            class="me-row"
            @click="openRoom(room.channel_id)"
          >
            <BaseIcon name="i-circle" :size="20" />
            <span class="mr-main">
              <span class="mr-t">{{ room.name_hans }}</span>
              <span class="mr-s">{{ room.room_type_label }} · {{ room.entry_count }} 条内容{{ room.is_private ? ' · 私密' : '' }}{{ !room.is_active ? ' · 审核中' : '' }}</span>
            </span>
            <span class="mr-end">进入</span>
          </button>
        </div>
        <BaseButton v-if="roomNextCursor" class="rooms-more" variant="outline" size="sm" :loading="roomsLoadingMore" @click="loadMoreRooms">加载更多房间</BaseButton>
      </div>

      <!-- 我的帖子 -->
      <div class="me-section">
        <h3>我的帖子 <span>{{ posts.length }} 条</span></h3>
        <p v-if="!posts.length" class="me-empty">还没有发布内容。</p>
        <template v-else>
          <template v-for="post in posts" :key="post.content_id">
            <component
              :is="post.status === 'published' ? 'button' : 'div'"
              class="me-row"
              :type="post.status === 'published' ? 'button' : undefined"
              @click="post.status === 'published' && router.push({ name: 'content', params: { id: post.content_id } })"
            >
              <BaseIcon name="i-reply" :size="20" />
              <span class="mr-main">
                <span class="mr-t">{{ post.title }}</span>
              </span>
              <span class="status-pill" :class="post.status">{{ statusLabel(post.status) }}</span>
            </component>
            <!-- 分类信息 30 天过期：发布页承诺了「可在我的续期」，入口在这里 -->
            <div v-if="post.type === 'listing' && (post.status === 'published' || post.status === 'withdrawn')" class="listing-actions">
              <BaseButton size="sm" variant="outline" :loading="listingBusy === post.content_id" @click="listingAction(post.content_id, 'renew')">
                {{ post.closed ? "重新上架 30 天" : "续期 30 天" }}
              </BaseButton>
              <BaseButton v-if="!post.closed" size="sm" variant="ghost" :disabled="listingBusy === post.content_id" @click="listingAction(post.content_id, 'close')">
                已成交，结案
              </BaseButton>
            </div>
          </template>
        </template>
      </div>

      <!-- 收藏 -->
      <div class="me-section">
        <h3>收藏</h3>
        <button type="button" class="me-row" :aria-expanded="favoritesOpen" @click="favoritesOpen = !favoritesOpen">
          <BaseIcon name="i-bookmark" :size="20" />
          <span class="mr-main">
            <span class="mr-t">收藏的内容与关注的频道</span>
            <span class="mr-s">{{ savedCount }} 条内容 · {{ followedCount }} 个频道</span>
          </span>
          <span class="mr-end">{{ favoritesOpen ? '收起' : '查看' }}</span>
        </button>
        <div v-if="favoritesOpen" class="favorites-list">
          <h4>收藏的内容</h4>
          <p v-if="!favorites.length" class="me-empty">还没有收藏内容。</p>
          <RouterLink
            v-for="item in favorites"
            :key="item.content_id"
            :to="{ name: 'content', params: { id: item.content_id } }"
            class="me-row"
          >
            <BaseIcon name="i-bookmark" :size="20" />
            <span class="mr-main">
              <span class="mr-t" data-ugc>{{ item.title }}</span>
              <span v-if="item.summary && hasOwnTitle(item.title, item.summary)" class="mr-s" data-ugc>{{ item.summary }}</span>
            </span>
            <span class="mr-end">打开</span>
          </RouterLink>
          <h4>关注的频道</h4>
          <p v-if="!subscriptions.length" class="me-empty">还没有关注频道。</p>
          <RouterLink v-for="item in subscriptions" :key="item.channel_id" :to="{ name: 'channel', params: { id: item.channel_id } }" class="me-row">
            <BaseIcon name="i-circle" :size="20" />
            <span class="mr-main"><span class="mr-t" data-ugc>{{ item.name_hans }}</span></span>
            <span class="mr-end">进入</span>
          </RouterLink>
        </div>
      </div>

      <!-- 我的举报 -->
      <div class="me-section">
        <h3>我的举报 <span>{{ reports.length }} 条</span></h3>
        <p v-if="!reports.length" class="me-empty">还没有举报记录。</p>
        <template v-else>
          <div v-for="report in reports" :key="report.case_id" class="me-row">
            <BaseIcon name="i-flag" :size="20" />
            <span class="mr-main">
              <span class="mr-t">{{ report.reason_text }}</span>
              <span class="mr-s">工单 {{ report.case_id.slice(0, 8) }} · {{ ago(report.created_at) }}</span>
            </span>
            <span class="mr-end">{{ reportStatusLabel(report.status) }}</span>
          </div>
        </template>
      </div>

      <!-- 设置 -->
      <div class="me-section">
        <h3>设置</h3>
        <div class="me-row">
          <BaseIcon name="i-globe" :size="20" />
          <span class="mr-main">
            <span class="mr-t">简繁偏好</span>
            <span class="mr-s">只转换界面文案，用户发布的内容保持原文</span>
          </span>
          <span class="seg-toggle" role="group" aria-label="简繁偏好">
            <button type="button" :aria-pressed="theme.lang === 'zh-Hans'" @click="theme.setLang('zh-Hans')">简体</button>
            <button type="button" :aria-pressed="theme.lang === 'zh-Hant'" @click="theme.setLang('zh-Hant')">繁體</button>
          </span>
        </div>
        <div class="me-row">
          <BaseIcon name="i-theme" :size="20" />
          <span class="mr-main">
            <span class="mr-t">深色 / 浅色主题</span>
          </span>
          <span class="seg-toggle" role="group" aria-label="主题">
            <button type="button" :aria-pressed="theme.theme === 'light'" @click="theme.setTheme('light')">浅色</button>
            <button type="button" :aria-pressed="theme.theme === 'dark'" @click="theme.setTheme('dark')">深色</button>
          </span>
        </div>
      </div>

      <!-- 私信 -->
      <div class="me-section">
        <h3>私信</h3>
        <div class="me-row">
          <BaseIcon name="i-mail" :size="20" />
          <span class="mr-main">
            <span class="mr-t">陌生人私信</span>
            <span class="mr-s">{{ dmAllow ? '开启：陌生人第一次私信你会先进「消息请求」' : '已关闭：只接收你关注的人的私信' }}</span>
          </span>
          <span class="seg-toggle" role="group" aria-label="陌生人私信">
            <button type="button" :aria-pressed="dmAllow" :disabled="prefsBusy" @click="!dmAllow && toggleDm()">允许</button>
            <button type="button" :aria-pressed="!dmAllow" :disabled="prefsBusy" @click="dmAllow && toggleDm()">关闭</button>
          </span>
        </div>
        <template v-if="blocks.length">
          <div v-for="person in blocks" :key="person.user_id" class="me-row">
            <BaseIcon name="i-user" :size="20" />
            <span class="mr-main">
              <span class="mr-t">{{ person.display_name }}</span>
              <span class="mr-s">已拉黑：不能私信你</span>
            </span>
            <BaseButton variant="ghost" size="sm" @click="unblock(person.user_id)">解除</BaseButton>
          </div>
        </template>
        <div v-else class="me-row">
          <BaseIcon name="i-user" :size="20" />
          <span class="mr-main">
            <span class="mr-t">拉黑名单</span>
            <span class="mr-s">还没有拉黑任何人</span>
          </span>
        </div>
      </div>

      <!-- 隐私与数据 -->
      <div class="me-section">
        <h3>账号与安全</h3>
        <details class="account-details">
          <summary class="me-row">手机验证与退出登录 <span class="mr-end">管理</span></summary>
          <AccountPanel />
        </details>
      </div>

      <div class="me-section">
        <h3>隐私与数据</h3>
        <div class="me-row">
          <BaseIcon name="i-check" :size="20" />
          <span class="mr-main">
            <span class="mr-t">同意记录</span>
            <span class="mr-s">{{ consentVersion ? `条款版本 ${consentVersion} · 年满 18 岁已确认` : '暂无同意记录' }}</span>
          </span>
        </div>
        <button type="button" class="me-row danger" @click="deleteOpen = true">
          <BaseIcon name="i-close" :size="20" />
          <span class="mr-main">
            <span class="mr-t">删除账号</span>
            <span class="mr-s">删除资料、帖子与房间</span>
          </span>
        </button>
      </div>
    </template>

    <!-- 未登录：账号面板 + 设置 -->
    <template v-else>
      <div class="me-card">
        <Avatar name="客" :size="56" tone="e" />
        <div class="me-identity">
          <div class="me-name">游客</div>
          <div class="me-sub">登录后可关注频道、加入房间、发布内容</div>
        </div>
      </div>
      <div class="guest-account">
        <AccountPanel />
      </div>
    </template>

    <!-- 创建房间弹窗 -->
    <Modal :open="roomFormOpen" title="创建房间" labelledby="create-room-title" @close="roomFormOpen = false">
        <form class="room-form" @submit.prevent="submitCreateRoom">
          <label class="field">
            <span class="field-label">房间名</span>
            <input
              id="room-name"
              v-model="roomForm.name"
              class="field-input"
              type="text"
              maxlength="64"
              placeholder="例如：伦敦租房互助"
              required
            />
          </label>
          <fieldset class="field">
            <legend class="field-label">房间类型</legend>
            <div class="room-type-grid">
              <label
                v-for="t in ROOM_TYPES"
                :key="t.value"
                class="room-type-opt"
                :class="{ active: roomForm.room_type === t.value }"
              >
                <input v-model="roomForm.room_type" type="radio" :value="t.value" :aria-label="t.label" />
                <span>{{ t.label }}</span>
              </label>
            </div>
          </fieldset>
          <label class="field checkbox-field">
            <input id="room-is-private" v-model="roomForm.is_private" type="checkbox" />
            <span>设为私密房间（申请加入需房主审核）</span>
          </label>
          <p v-if="roomFormError" class="error" role="alert">{{ roomFormError }}</p>
          <div class="modal-actions">
            <BaseButton type="button" variant="ghost" :disabled="roomFormBusy" @click="roomFormOpen = false">取消</BaseButton>
            <BaseButton type="submit" :loading="roomFormBusy">提交审核</BaseButton>
          </div>
        </form>
    </Modal>

    <!-- 删除账号确认：用站内弹窗代替原生 confirm（可 Esc 关闭、焦点陷阱、简繁自动转换） -->
    <Modal :open="deleteOpen" title="删除账号？" labelledby="delete-account-title" @close="deleteOpen = false">
      <p class="delete-note">将删除你的资料、帖子和房间，并退出登录。此操作不可撤销。</p>
      <div class="modal-actions">
        <BaseButton type="button" variant="ghost" :disabled="deleteBusy" @click="deleteOpen = false">取消</BaseButton>
        <BaseButton type="button" variant="danger" :loading="deleteBusy" @click="deleteAccount">确认删除</BaseButton>
      </div>
    </Modal>
  </section>
</template>

<style scoped>
.delete-note {
  margin: 0 0 var(--sp-4);
  color: var(--muted);
  font-size: var(--fs-14);
  line-height: 1.6;
}
.profile-view {
  display: grid;
  gap: 0;
}
.page-title {
  margin: 0 0 var(--sp-3);
  font-size: var(--fs-21);
  font-weight: var(--fw-heavy);
}
.muted { margin: 0; color: var(--muted); font-size: var(--fs-13); }
.error { margin: 0; color: var(--danger); font-size: var(--fs-13); }

/* 顶卡 */
.me-card {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 18px 16px;
  border-bottom: 1px solid var(--border);
}
.me-identity { flex: 1; min-width: 0; }
.me-name { font-size: 19px; font-weight: 800; }
.me-sub { font-size: 13px; color: var(--muted); overflow-wrap: anywhere; }
.me-actions { display: flex; gap: 8px; flex-shrink: 0; }

/* 未登录：游客卡 + 账号面板，视觉上合成一张卡片 */
.guest-account {
  margin: var(--sp-4) var(--sp-4) var(--sp-6);
}
.guest-account :deep(.account-panel) {
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  overflow: hidden;
}

/* 分区 */
.me-section {
  border-bottom: 1px solid var(--border);
  padding: 4px 0 10px;
}
.me-section h3 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 12px 16px 6px;
  font-size: 15px;
}
.me-section h3 span {
  font-size: 12px;
  color: var(--muted);
  font-weight: 600;
}
.me-section h3 .section-btn { margin-left: auto; }
.rooms-more { margin: var(--sp-2) var(--sp-4); }
.rooms-group h4 { margin: var(--sp-2) var(--sp-4) var(--sp-1); font-size: var(--fs-13); }
.rooms-group h4 span { color: var(--muted); font-weight: 600; font-size: 12px; }
.favorites-list { padding-left: var(--sp-4); border-top: 1px solid var(--border); }
.favorites-list h4 { margin: var(--sp-3) var(--sp-4) var(--sp-1); font-size: var(--fs-13); }
.favorites-list a.me-row { text-decoration: none; }
.listing-actions { display: flex; flex-wrap: wrap; gap: var(--sp-2); padding: 0 var(--sp-4) var(--sp-3) calc(var(--sp-4) + 32px); }
.load-error { display: flex; align-items: center; justify-content: space-between; gap: var(--sp-3); padding: var(--sp-3) var(--sp-4); }
.account-details > summary { cursor: pointer; list-style: none; justify-content: space-between; }
.account-details > summary::-webkit-details-marker { display: none; }
.account-details :deep(.account-panel) { margin: 0 var(--sp-4) var(--sp-3); }
.me-row {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
  min-height: 52px;
  padding: 8px 16px;
  text-align: left;
  color: var(--text);
  font-size: 14px;
  border-radius: 0;
  border: 0;
  background: transparent;
}
button.me-row:hover { background: var(--hover); }
button.me-row:disabled { cursor: default; }
.me-row :deep(.base-icon) { color: var(--muted); flex-shrink: 0; }
.me-row .mr-main { flex: 1; min-width: 0; }
.me-row .mr-t {
  display: block;
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.me-row .mr-s {
  display: block;
  font-size: 12px;
  color: var(--muted);
  overflow-wrap: anywhere;
}
.me-row .mr-end {
  margin-left: auto;
  font-size: 12px;
  color: var(--muted);
  white-space: nowrap;
  flex-shrink: 0;
}
.me-row.danger .mr-t { color: var(--danger); }
.me-empty {
  padding: 6px 16px 8px;
  font-size: 13px;
  color: var(--muted);
}

/* 状态 pill */
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border-radius: var(--r-pill);
  border: 1px dashed var(--warn);
  color: var(--warn);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  flex-shrink: 0;
}
.status-pill.published { border-style: solid; border-color: var(--good); color: var(--good); }
.status-pill.rejected { border-style: solid; border-color: var(--danger); color: var(--danger); }

/* 分段开关 */
.seg-toggle {
  display: inline-flex;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  overflow: hidden;
  flex-shrink: 0;
}
.seg-toggle button {
  min-height: 44px;
  padding: 0 14px;
  font-size: 13px;
  font-weight: 700;
  color: var(--muted);
  border: 0;
  background: transparent;
  cursor: pointer;
}
.seg-toggle button[aria-pressed="true"] { background: var(--text); color: var(--bg); }
.seg-toggle button:disabled { opacity: 0.6; cursor: default; }

/* 创建房间弹窗：外壳用统一的 Modal，这里只管表单 */
.room-form { display: grid; gap: 14px; }
.field { display: grid; gap: 6px; }
.field-label { font-size: 13px; font-weight: 700; color: var(--muted); }
.field-input {
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--bg);
  color: var(--text);
  font-size: 14px;
}
.field-input:focus { outline: 2px solid var(--accent); outline-offset: 0; }
.room-type-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
.room-type-opt {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  cursor: pointer;
  font-size: 14px;
}
.room-type-opt.active { border-color: var(--accent); color: var(--accent); }
.room-type-opt input { accent-color: var(--accent); }
.checkbox-field { display: flex; flex-direction: row; align-items: center; gap: 8px; }
.checkbox-field input { accent-color: var(--accent); }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; padding-top: 4px; }
</style>
