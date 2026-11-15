<script setup lang="ts">
// 用户主页（/user/:id），X 式布局：吸顶顶栏（名字 + 帖子数）、横幅、大头像、关注/私信、资料、关注数、帖子流。
// 后端：GET /users/{id}、GET /users/{id}/posts、PUT /me/follows/{id}、POST /users/{id}/report。
// 判断「是否自己」用 GET /me 的 user_id 对比；自己主页隐藏关注/举报，改成「编辑资料」。
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  request,
  jsonBody,
  type DmOpenResponse,
  type MeProfile,
  type UserPost,
  type UserPostsResponse,
  type UserProfile,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import { usePostReactions } from "../composables/usePostReactions";
import Avatar from "../components/base/Avatar.vue";
import BaseIcon from "../components/base/BaseIcon.vue";
import ReportButton from "../components/common/ReportButton.vue";
import PostCard from "../components/common/PostCard.vue";
import ContentDetail from "../components/ContentDetail.vue";
import EmptyState from "../components/base/EmptyState.vue";
import ErrorState from "../components/base/ErrorState.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();
const { toggleLike, toggleFavorite, repost } = usePostReactions();

const userId = computed(() => (typeof route.params.id === "string" ? route.params.id : ""));

const profile = ref<UserProfile | null>(null);
const posts = ref<UserPost[]>([]);
const loading = ref(true);
const error = ref("");
const selfId = ref("");
const followingBusy = ref(false);
const blockBusy = ref(false);
const dmOpen = ref(false);
const dmBody = ref("");
const dmBusy = ref(false);
const activeContentId = ref<string | null>(null);
const tab = ref<"posts" | "rooms">("posts");

const isSelf = computed(() => selfId.value !== "" && selfId.value === userId.value);
const displayName = computed(() => profile.value?.display_name || profile.value?.handle || "匿名用户");
const joinedText = computed(() => {
  const d = new Date(profile.value?.joined_at ?? "");
  return Number.isNaN(d.getTime()) ? "" : `${d.getFullYear()}年${d.getMonth() + 1}月加入`;
});

function requireLogin(): boolean {
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再继续");
    return false;
  }
  return true;
}

async function loadSelf(): Promise<void> {
  if (!auth.isLoggedIn) return;
  try {
    const me = await request<MeProfile>("/api/v1/me");
    selfId.value = me.user_id;
  } catch {
    // 未登录或 token 失效，忽略；仅影响「是否自己」判断
  }
}

async function load(): Promise<void> {
  if (!userId.value) return;
  loading.value = true;
  error.value = "";
  try {
    const [p, ps] = await Promise.all([
      request<UserProfile>(`/api/v1/users/${userId.value}`),
      request<UserPostsResponse>(`/api/v1/users/${userId.value}/posts`),
    ]);
    profile.value = p;
    posts.value = ps.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "用户主页加载失败";
  } finally {
    loading.value = false;
  }
}

async function toggleFollow(): Promise<void> {
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再关注");
    return;
  }
  if (!profile.value) return;
  const willFollow = !profile.value.following;
  followingBusy.value = true;
  try {
    const body = await request<{ following: boolean }>(`/api/v1/me/follows/${userId.value}`, {
      method: willFollow ? "PUT" : "DELETE",
    });
    if (profile.value && profile.value.following !== body.following) {
      profile.value.follower_count += body.following ? 1 : -1;
      profile.value.following = body.following;
    }
    toast.show(willFollow ? "已关注" : "已取消关注");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "操作没有成功");
  } finally {
    followingBusy.value = false;
  }
}

async function toggleBlock(): Promise<void> {
  if (!requireLogin()) return;
  if (!profile.value) return;
  const willBlock = !profile.value.blocked;
  blockBusy.value = true;
  try {
    await request(`/api/v1/me/blocks/${userId.value}`, { method: willBlock ? "PUT" : "DELETE" });
    if (profile.value) profile.value.blocked = willBlock;
    toast.show(willBlock ? "已拉黑" : "已解除拉黑");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "操作没有成功");
  } finally {
    blockBusy.value = false;
  }
}

function openDm(): void {
  if (!requireLogin()) return;
  dmBody.value = "";
  dmOpen.value = true;
}

async function sendDm(): Promise<void> {
  if (!dmBody.value.trim()) {
    toast.show("请输入首条消息");
    return;
  }
  dmBusy.value = true;
  try {
    const body = await request<DmOpenResponse>(
      "/api/v1/me/messages",
      jsonBody({ to_user_id: userId.value, body: dmBody.value.trim() }),
    );
    dmOpen.value = false;
    dmBody.value = "";
    toast.show(body.status === "request" ? "已发出私信请求，等待对方接受" : "私信已发送");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "私信没有发出");
  } finally {
    dmBusy.value = false;
  }
}

onMounted(() => {
  void load();
  void loadSelf();
});
watch(userId, () => {
  profile.value = null;
  posts.value = [];
  activeContentId.value = null;
  tab.value = "posts";
  void load();
});
</script>

<template>
  <section class="user-view">
    <!-- 顶栏：返回 + 名字 + 帖子数，滚动时吸顶 -->
    <nav class="user-top">
      <button type="button" class="back-btn" aria-label="返回" @click="router.back()">
        <BaseIcon name="i-back" :size="20" />
      </button>
      <div v-if="profile" class="user-top-text">
        <strong data-ugc>{{ displayName }}</strong>
        <span>{{ profile.post_count }} 条帖子</span>
      </div>
    </nav>

    <p v-if="loading" class="empty">加载中…</p>
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />

    <template v-else-if="profile">
      <header class="profile">
        <div class="profile-banner" aria-hidden="true"></div>
        <div class="profile-row">
          <div class="profile-avatar">
            <Avatar :name="displayName" :size="88" kind="person" :tone="profile.avatar_tone" />
          </div>
          <div v-if="!isSelf" class="profile-actions">
            <ReportButton kind="user" :id="profile.user_id" compact />
            <button type="button" class="pill-btn" :disabled="blockBusy" @click="toggleBlock">
              {{ profile.blocked ? "解除拉黑" : "拉黑" }}
            </button>
            <button type="button" class="pill-btn" aria-label="私信" @click="openDm">
              <BaseIcon name="i-mail" :size="18" />
            </button>
            <button
              type="button"
              class="follow-btn"
              :class="{ 'follow-btn--on': profile.following }"
              :disabled="followingBusy"
              @click="toggleFollow"
            >
              {{ profile.following ? "已关注" : followingBusy ? "关注中…" : "关注" }}
            </button>
          </div>
          <div v-else class="profile-actions">
            <RouterLink class="pill-btn" :to="{ name: 'profile' }">编辑资料</RouterLink>
          </div>
        </div>

        <div class="profile-info">
          <div>
            <h1 class="profile-name" data-ugc>{{ displayName }}</h1>
            <p v-if="profile.handle" class="profile-handle">@{{ profile.handle }}</p>
          </div>
          <p v-if="profile.city_label || joinedText" class="profile-sub">
            <span v-if="profile.city_label"><BaseIcon name="i-pin" :size="15" /> {{ profile.city_label }}</span>
            <span v-if="joinedText">{{ joinedText }}</span>
          </p>
          <p class="profile-counts">
            <span><strong>{{ profile.following_count }}</strong> 正在关注</span>
            <span><strong>{{ profile.follower_count }}</strong> 关注者</span>
          </p>
        </div>

        <div class="profile-tabs" role="tablist">
          <button
            type="button"
            class="profile-tab"
            :class="{ 'profile-tab--on': tab === 'posts' }"
            role="tab"
            :aria-selected="tab === 'posts'"
            @click="tab = 'posts'"
          >帖子</button>
          <button
            type="button"
            class="profile-tab"
            :class="{ 'profile-tab--on': tab === 'rooms' }"
            role="tab"
            :aria-selected="tab === 'rooms'"
            @click="tab = 'rooms'"
          >房间 {{ profile.rooms.length || "" }}</button>
        </div>
      </header>

      <template v-if="tab === 'rooms'">
        <EmptyState v-if="profile.rooms.length === 0" title="还没有房间" description="这位用户还没有创建公开房间" />
        <ul v-else class="room-list">
          <li v-for="room in profile.rooms" :key="room.id">
            <RouterLink class="room-row" :to="{ name: 'room', params: { id: room.id } }">
              <span class="room-row-name" data-ugc>{{ room.name_hans }}</span>
              <span class="room-row-meta">
                {{ room.room_type_label }} · {{ room.subscriber_count }} 人订阅
                <template v-if="room.is_private"> · 私密</template>
                <template v-if="room.pending"> · 审核中</template>
              </span>
            </RouterLink>
          </li>
        </ul>
      </template>

      <EmptyState
        v-else-if="posts.length === 0"
        title="还没有公开帖子"
        description="这位用户暂时没有发布公开内容"
      />
      <div v-else class="posts">
        <PostCard
          v-for="post in posts"
          :key="post.content_id"
          :content-id="post.content_id"
          :title="post.title"
          :summary="post.summary"
          :channel-name="post.channel_name"
          :channel-id="post.channel_id || ''"
          :author-id="profile.user_id"
          :author-name="profile.display_name"
          :author-handle="profile.handle"
          :author-tone="profile.avatar_tone"
          :source-name="post.source_name"
          :licence-ref="post.licence_ref"
          :canonical-url="post.canonical_url"
          :keywords="post.keywords"
          :image-keys="post.image_keys"
          :video-key="post.video_key"
          :time="post.created_at"
          :liked="post.liked"
          :favorited="post.favorited"
          :reposted="post.reposted"
          @open="activeContentId = post.content_id"
          @like="toggleLike(post)"
          @favorite="toggleFavorite(post)"
          @repost="repost(post, post.channel_id)"
        />
      </div>
    </template>

    <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />

    <!-- 私信弹窗 -->
    <div v-if="dmOpen" class="dm-overlay" role="dialog" aria-modal="true" aria-label="发送私信">
      <div class="dm-sheet">
        <h3 class="dm-title">私信 @{{ profile?.handle || profile?.display_name || "TA" }}</h3>
        <textarea
          id="dm-message"
          v-model="dmBody"
          class="dm-input"
          maxlength="1000"
          rows="4"
          placeholder="写下首条消息…"
          aria-label="私信内容"
        ></textarea>
        <p class="dm-hint">陌生人私信需对方接受后才进入会话</p>
        <div class="dm-actions">
          <button type="button" class="dm-cancel" @click="dmOpen = false">取消</button>
          <button type="button" class="dm-send" :disabled="dmBusy" @click="sendDm">
            {{ dmBusy ? "发送中…" : "发送" }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.user-view {
  max-width: 720px;
  margin: 0 auto;
}
.user-top {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  gap: var(--sp-4);
  min-height: 53px;
  padding: 0 var(--sp-2);
  background: color-mix(in srgb, var(--bg) 85%, transparent);
  backdrop-filter: blur(12px);
}
.back-btn {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--text);
  cursor: pointer;
}
.back-btn:hover {
  background: var(--accent-soft);
}
.user-top-text {
  display: grid;
  min-width: 0;
  line-height: 1.25;
}
.user-top-text strong {
  font-size: var(--fs-16);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-top-text span {
  color: var(--muted);
  font-size: var(--fs-12);
}
.empty {
  padding: var(--sp-6) var(--sp-4);
  color: var(--muted);
  font-size: var(--fs-13);
}
.profile {
  border-bottom: 1px solid var(--border);
}
.profile-banner {
  height: 150px;
  background: linear-gradient(135deg, var(--accent-soft), color-mix(in srgb, var(--accent-strong) 40%, var(--bg)));
}
.profile-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: 0 var(--sp-4);
}
.profile-avatar {
  margin-top: -48px;
  padding: 4px;
  border-radius: 50%;
  background: var(--bg);
  flex-shrink: 0;
}
.profile-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--sp-2);
  min-width: 0;
  padding-top: var(--sp-3);
}
.profile-actions > * {
  flex-shrink: 0;
}
.pill-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: var(--tap);
  min-height: var(--tap);
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--text);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  text-decoration: none;
  cursor: pointer;
}
.pill-btn:hover {
  background: var(--accent-soft);
}
.pill-btn:disabled {
  opacity: 0.65;
  cursor: default;
}
.follow-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-4);
  border: 1px solid var(--text);
  border-radius: var(--r-pill);
  background: var(--text);
  color: var(--bg);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.follow-btn:hover {
  opacity: 0.85;
}
.follow-btn--on {
  background: transparent;
  color: var(--text);
  border-color: var(--line);
}
.follow-btn:disabled {
  opacity: 0.65;
  cursor: default;
}
.profile-info {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-4) 0;
}
.profile-name {
  margin: 0;
  font-size: var(--fs-19);
  font-weight: var(--fw-bold);
  line-height: 1.25;
  overflow-wrap: anywhere;
}
.profile-handle {
  margin: 2px 0 0;
  color: var(--muted);
  font-size: var(--fs-14);
}
.profile-sub,
.profile-counts {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1) var(--sp-4);
  color: var(--muted);
  font-size: var(--fs-14);
}
.profile-sub span {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.profile-counts strong {
  color: var(--text);
}
.profile-tabs {
  display: flex;
  margin-top: var(--sp-3);
}
.profile-tab {
  flex: 1;
  display: grid;
  place-items: center;
  min-height: 52px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.profile-tab:hover {
  background: var(--accent-soft);
}
.room-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.room-list li {
  border-bottom: 1px solid var(--border);
}
.room-row {
  display: grid;
  gap: 2px;
  padding: var(--sp-3) var(--sp-4);
  color: var(--text);
  text-decoration: none;
}
.room-row:hover {
  background: var(--accent-soft);
}
.room-row-name {
  font-weight: var(--fw-bold);
  overflow-wrap: anywhere;
}
.room-row-meta {
  color: var(--muted);
  font-size: var(--fs-13);
}
.profile-tab {
  position: relative;
}
.profile-tab--on {
  color: var(--text);
}
.profile-tab--on::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 50%;
  width: 56px;
  height: 4px;
  border-radius: 2px;
  background: var(--accent-strong);
  transform: translateX(-50%);
}
.posts {
  display: grid;
}
.dm-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--sp-4);
  background: rgba(0, 0, 0, 0.4);
}
.dm-sheet {
  width: 100%;
  max-width: 420px;
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-4);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.dm-title {
  margin: 0;
  font-size: var(--fs-16);
  font-weight: var(--fw-bold);
}
.dm-input {
  width: 100%;
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--bg);
  color: var(--text);
  font-size: var(--fs-14);
  line-height: 1.5;
  resize: vertical;
  font-family: inherit;
}
.dm-input:focus {
  outline: none;
  border-color: var(--accent);
}
.dm-hint {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.dm-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
}
.dm-cancel {
  min-height: var(--tap);
  padding: 0 var(--sp-4);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-14);
  cursor: pointer;
}
.dm-send {
  min-height: var(--tap);
  padding: 0 var(--sp-4);
  border: 1px solid var(--accent-strong);
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.dm-send:disabled {
  opacity: 0.65;
  cursor: default;
}
</style>
