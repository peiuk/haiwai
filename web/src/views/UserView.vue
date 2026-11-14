<script setup lang="ts">
// 用户主页（/user/:id）：公开资料 + 关注 / 举报 + 该用户的公开帖子列表。
// 后端：GET /users/{id}、GET /users/{id}/posts、PUT /me/follows/{id}、POST /users/{id}/report。
// 判断「是否自己」用 GET /me 的 user_id 对比；自己主页隐藏关注/举报，改跳「我的」编辑。
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  request,
  jsonBody,
  type DmOpenResponse,
  type MeProfile,
  type UserPostsResponse,
  type UserProfile,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import Avatar from "../components/base/Avatar.vue";
import BaseIcon from "../components/base/BaseIcon.vue";
import ReportButton from "../components/common/ReportButton.vue";
import EmptyState from "../components/base/EmptyState.vue";
import ErrorState from "../components/base/ErrorState.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();

const userId = computed(() => (typeof route.params.id === "string" ? route.params.id : ""));

const profile = ref<UserProfile | null>(null);
const posts = ref<UserPostsResponse["items"]>([]);
const loading = ref(true);
const error = ref("");
const selfId = ref("");
const followingBusy = ref(false);
const blockBusy = ref(false);
const dmOpen = ref(false);
const dmBody = ref("");
const dmBusy = ref(false);

const isSelf = computed(() => selfId.value !== "" && selfId.value === userId.value);

function requireLogin(): boolean {
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再继续");
    return false;
  }
  return true;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleDateString("zh-CN");
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
    if (profile.value) profile.value.following = body.following;
    toast.show(willFollow ? "已关注" : "已取消关注");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "操作没有成功");
  } finally {
    followingBusy.value = false;
  }
}

function openPost(contentId: string): void {
  void router.push(`/content/${contentId}`);
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
  void load();
});
</script>

<template>
  <section class="user-view">
    <nav class="user-back">
      <button type="button" class="back-btn" @click="router.back()">
        <BaseIcon name="i-back" :size="18" /> 返回
      </button>
    </nav>

    <p v-if="loading" class="empty">加载中…</p>
    <ErrorState v-else-if="error" :message="error" retry-label="重试" @retry="load" />

    <template v-else-if="profile">
      <!-- 资料卡 -->
      <header class="profile-card">
        <Avatar
          :name="profile.display_name || profile.handle || '·'"
          :size="56"
          kind="person"
          :tone="profile.avatar_tone"
        />
        <div class="profile-main">
          <h1 class="profile-name" data-ugc>{{ profile.display_name || "匿名用户" }}</h1>
          <p class="profile-sub">
            <span v-if="profile.handle">@{{ profile.handle }}</span>
            <span v-if="profile.city_label" class="profile-city">
              <BaseIcon name="i-globe" :size="14" /> {{ profile.city_label }}
            </span>
          </p>
        </div>
        <div v-if="!isSelf" class="profile-actions">
          <button
            type="button"
            class="follow-btn"
            :class="{ 'follow-btn--on': profile.following }"
            :disabled="followingBusy"
            @click="toggleFollow"
          >
            {{ profile.following ? "已关注" : followingBusy ? "关注中…" : "关注" }}
          </button>
          <button type="button" class="dm-btn" @click="openDm">
            <BaseIcon name="i-mail" :size="16" /> 私信
          </button>
          <button
            type="button"
            class="block-btn"
            :disabled="blockBusy"
            @click="toggleBlock"
          >
            {{ profile.blocked ? "解除拉黑" : "拉黑" }}
          </button>
          <ReportButton kind="user" :id="profile.user_id" compact />
        </div>
        <span v-else class="profile-self">这是你的主页</span>
      </header>

      <!-- 帖子列表 -->
      <section class="posts-section">
        <h2 class="posts-title">公开帖子</h2>
        <EmptyState
          v-if="posts.length === 0"
          title="还没有公开帖子"
          description="这位用户暂时没有发布公开内容"
        />
        <ul v-else class="posts-list">
          <li v-for="post in posts" :key="post.content_id">
            <button type="button" class="post-row" @click="openPost(post.content_id)">
              <span class="post-row-title" data-ugc>{{ post.title || "（无标题）" }}</span>
              <span class="post-row-time">{{ fmtTime(post.created_at) }}</span>
            </button>
          </li>
        </ul>
      </section>
    </template>

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
  display: grid;
  gap: var(--sp-4);
  max-width: 720px;
  margin: 0 auto;
}
.user-back {
  display: flex;
}
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  border: 0;
  background: transparent;
  color: var(--text);
  font-size: var(--fs-14);
  cursor: pointer;
}
.back-btn:hover {
  color: var(--accent-ink);
}
.empty {
  padding: var(--sp-6) 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.profile-card {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-4);
  padding: var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
}
.profile-main {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: var(--sp-1);
}
.profile-name {
  margin: 0;
  font-size: var(--fs-19);
  font-weight: var(--fw-bold);
  overflow-wrap: anywhere;
}
.profile-sub {
  margin: 0;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  color: var(--muted);
  font-size: var(--fs-13);
}
.profile-city {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.profile-actions {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-shrink: 0;
  flex-wrap: wrap;
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
  color: var(--muted);
  border-color: var(--line);
  cursor: pointer; /* 点击仍可取消关注，视觉与行为一致 */
}
.follow-btn:disabled {
  opacity: 0.65;
  cursor: default;
}
.dm-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-4);
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  border: 1px solid var(--accent-strong);
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.dm-btn:hover {
  opacity: 0.9;
}
.block-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-13);
  cursor: pointer;
}
.block-btn:hover {
  color: var(--danger);
  border-color: var(--danger);
}
.block-btn:disabled {
  opacity: 0.65;
  cursor: default;
}
.profile-self {
  color: var(--muted);
  font-size: var(--fs-13);
}
.posts-section {
  display: grid;
  gap: var(--sp-3);
}
.posts-title {
  margin: 0;
  font-size: var(--fs-16);
}
.posts-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  overflow: hidden;
}
.posts-list li + li {
  border-top: 1px solid var(--border);
}
.post-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  width: 100%;
  min-height: var(--tap);
  padding: var(--sp-3) var(--sp-4);
  border: 0;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  text-align: left;
}
.post-row:hover {
  background: var(--accent-soft);
}
.post-row-title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-14);
}
.post-row-time {
  flex-shrink: 0;
  color: var(--muted);
  font-size: var(--fs-12);
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
