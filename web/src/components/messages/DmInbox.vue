<script setup lang="ts">
// 站内私信（对齐 /me/messages 全套端点）：会话列表 / 消息详情 / 发送 / 接受或删除请求 / 标记已读。
// 陌生人请求需对方接受；图片消息走 /uploads/sign 直传后只提交 object_key。
import { fmtRelativeTime } from "../../utils/time";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { request, jsonBody, type DmThreadItem, type DmThreadsResponse, type DmThreadResponse, type DmOpenResponse } from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import Avatar from "../base/Avatar.vue";
import BaseButton from "../base/BaseButton.vue";
import BaseTag from "../base/BaseTag.vue";
import EmptyState from "../base/EmptyState.vue";
import ErrorState from "../base/ErrorState.vue";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";
import UploadField from "../common/UploadField.vue";

const emit = defineEmits<{ (e: "unread", value: number): void }>();

const auth = useAuthStore();
const toast = useToastStore();

const threads = ref<DmThreadItem[]>([]);
const requestCount = ref(0);
const activeId = ref("");
const messages = ref<DmThreadResponse["items"]>([]);
const threadStatus = ref<DmThreadResponse["status"]>("active");
const loading = ref(true);
const detailLoading = ref(false);
const listError = ref("");
const detailError = ref("");
const sending = ref(false);
const draft = ref("");
const imageKey = ref("");
const showNew = ref(false);
const peerId = ref("");
const newBody = ref("");
const newBusy = ref(false);

// 自动轮询：仅页面可见时刷新，切回前台立即补一次；不与发送/加载竞争。
const POLL_MS = 30_000;
const polling = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

function onVisible(): void {
  if (document.visibilityState === "visible") void poll();
}

async function poll(): Promise<void> {
  if (polling.value || !auth.isLoggedIn || document.visibilityState !== "visible") return;
  if (sending.value || newBusy.value || detailLoading.value || showNew.value) return;
  polling.value = true;
  try {
    await loadThreads(true);
    if (activeId.value) await reloadMessages(true);
  } finally {
    polling.value = false;
  }
}

const activeThread = computed(() => threads.value.find((item) => item.thread_id === activeId.value) ?? null);
const isIncomingRequest = computed(() => {
  if (threadStatus.value !== "request" || messages.value.length === 0 || !activeThread.value) return false;
  return messages.value[0].sender_id === activeThread.value.peer_id;
});
const canReply = computed(() => threadStatus.value === "active" || !isIncomingRequest.value);

function emitUnread(): void {
  emit("unread", threads.value.reduce((sum, item) => sum + item.unread, 0));
}

async function loadThreads(silent = false): Promise<void> {
  if (!auth.isLoggedIn) {
    threads.value = [];
    emitUnread();
    loading.value = false;
    return;
  }
  // 静默轮询不切换 loading、不覆盖错误态，避免列表闪烁或打断用户操作。
  if (!silent) {
    loading.value = true;
    listError.value = "";
  }
  try {
    const body = await request<DmThreadsResponse>("/api/v1/me/messages");
    threads.value = body.items;
    requestCount.value = body.request_count;
    emitUnread();
  } catch (err) {
    if (!silent) listError.value = err instanceof Error ? err.message : "私信列表加载失败";
  } finally {
    if (!silent) loading.value = false;
  }
}

async function openThread(thread: DmThreadItem): Promise<void> {
  activeId.value = thread.thread_id;
  detailLoading.value = true;
  detailError.value = "";
  messages.value = [];
  try {
    const body = await request<DmThreadResponse>(`/api/v1/me/messages/${thread.thread_id}`);
    messages.value = body.items;
    threadStatus.value = body.status;
    if (thread.unread > 0) {
      await request(`/api/v1/me/messages/${thread.thread_id}/read`, { method: "POST" });
      thread.unread = 0;
      emitUnread();
    }
  } catch (err) {
    detailError.value = err instanceof Error ? err.message : "会话加载失败";
  } finally {
    detailLoading.value = false;
  }
}

async function reloadMessages(silent = false): Promise<void> {
  if (!activeId.value) return;
  try {
    const body = await request<DmThreadResponse>(`/api/v1/me/messages/${activeId.value}`);
    messages.value = body.items;
    threadStatus.value = body.status;
  } catch (err) {
    // 静默轮询失败不打扰用户；显式刷新仍把错误交给调用方的 catch。
    if (silent) return;
    throw err;
  }
}

async function send(): Promise<void> {
  if (!activeId.value || (!draft.value.trim() && !imageKey.value)) {
    toast.show("请输入文字或选择一张图片");
    return;
  }
  sending.value = true;
  try {
    await request(
      `/api/v1/me/messages/${activeId.value}`,
      jsonBody({ body: draft.value.trim(), image_key: imageKey.value || null }),
    );
    draft.value = "";
    imageKey.value = "";
    await reloadMessages();
    await loadThreads();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "发送没有成功");
  } finally {
    sending.value = false;
  }
}

async function openNewThread(): Promise<void> {
  if (!peerId.value.trim() || !newBody.value.trim()) {
    toast.show("请填写对方用户 ID 和首条消息");
    return;
  }
  newBusy.value = true;
  try {
    const body = await request<DmOpenResponse>(
      "/api/v1/me/messages",
      jsonBody({ to_user_id: peerId.value.trim(), body: newBody.value.trim() }),
    );
    peerId.value = "";
    newBody.value = "";
    showNew.value = false;
    await loadThreads();
    const thread = threads.value.find((item) => item.thread_id === body.thread_id);
    if (thread) await openThread(thread);
    toast.show(body.status === "request" ? "已发出私信请求，等待对方接受" : "私信已发送");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "私信没有发出");
  } finally {
    newBusy.value = false;
  }
}

async function acceptRequest(): Promise<void> {
  if (!activeId.value) return;
  try {
    await request(`/api/v1/me/messages/${activeId.value}/accept`, { method: "POST" });
    toast.show("已接受私信请求");
    await Promise.all([reloadMessages(), loadThreads()]);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "接受没有成功");
  }
}

async function deleteRequest(): Promise<void> {
  if (!activeId.value) return;
  try {
    await request(`/api/v1/me/messages/${activeId.value}`, { method: "DELETE" });
    toast.show("已删除私信请求");
    activeId.value = "";
    messages.value = [];
    await loadThreads();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "删除没有成功");
  }
}

function timeLabel(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN", { hour12: false });
}

onMounted(() => {
  void loadThreads();
  pollTimer = setInterval(() => void poll(), POLL_MS);
  document.addEventListener("visibilitychange", onVisible);
});

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = null;
  document.removeEventListener("visibilitychange", onVisible);
});

defineExpose({ reload: () => loadThreads(false) });
</script>

<template>
  <div class="dm-inbox">
    <p v-if="!auth.isLoggedIn" class="dm-hint">注册或登录后查看私信。</p>

    <template v-else>
      <div class="dm-head">
        <p class="dm-summary">
          {{ threads.length }} 个会话<template v-if="requestCount"> · {{ requestCount }} 个待处理请求</template>
        </p>
        <BaseButton type="button" variant="outline" size="sm" @click="showNew = !showNew">
          {{ showNew ? "收起" : "发起私信" }}
        </BaseButton>
      </div>

      <form v-if="showNew" class="dm-new" @submit.prevent="openNewThread">
        <TextField id="dm-peer" v-model="peerId" label="对方用户 ID" required />
        <TextArea id="dm-first" v-model="newBody" label="首条消息" :rows="2" required />
        <p class="dm-hint">陌生人私信会先进入「请求」，对方接受后才能继续对话。</p>
        <BaseButton type="submit" variant="primary" size="sm" :loading="newBusy">发送私信请求</BaseButton>
      </form>

      <ErrorState v-if="listError" :message="listError" @retry="loadThreads(false)" />

      <div v-else-if="loading" class="dm-hint">加载中…</div>

      <EmptyState v-else-if="threads.length === 0" title="还没有私信会话" />

      <div v-else class="dm-body">
        <ul class="dm-list" aria-label="私信会话列表">
          <li v-for="thread in threads" :key="thread.thread_id">
            <button
              type="button"
              class="dm-item"
              :class="{ active: thread.thread_id === activeId }"
              :aria-pressed="thread.thread_id === activeId"
              @click="openThread(thread)"
            >
              <Avatar :name="thread.peer_name || '?'" :size="38" :tone="thread.peer_tone" :image="thread.peer_avatar" />
              <span class="dm-item-main">
                <span class="dm-peer">
                  {{ thread.peer_name || "用户" }}
                  <BaseTag v-if="thread.status === 'request'" variant="warn">请求</BaseTag>
                  <BaseTag v-if="thread.listing_inquiry" variant="link">分类信息咨询</BaseTag>
                </span>
                <span class="dm-preview" data-ugc>{{ thread.preview || "暂无消息" }}</span>
                <span class="dm-time" :title="timeLabel(thread.updated_at)">{{ fmtRelativeTime(thread.updated_at) }}</span>
              </span>
              <span v-if="thread.unread" class="dm-unread" :aria-label="`${thread.unread} 条未读`">{{ thread.unread }}</span>
            </button>
          </li>
        </ul>

        <section class="dm-detail" aria-label="会话内容">
          <template v-if="activeThread">
            <header class="dm-detail-head">
              <strong data-ugc>{{ activeThread.peer_name || "用户" }}</strong>
              <span v-if="activeThread.peer_handle" class="dm-time">@{{ activeThread.peer_handle }}</span>
            </header>

            <div v-if="activeThread.listing_ref" class="dm-listing" role="note">
              关于「{{ activeThread.listing_ref.title }}」· {{ activeThread.listing_ref.area }} ·
              {{ activeThread.listing_ref.price }} {{ activeThread.listing_ref.unit }}
            </div>

            <ErrorState v-if="detailError" :message="detailError" @retry="activeThread && openThread(activeThread)" />
            <p v-else-if="detailLoading" class="dm-hint">加载中…</p>

            <ol v-else class="dm-messages" aria-live="polite">
              <li v-for="message in messages" :key="message.id" class="dm-message">
                <img
                  v-if="message.kind === 'image' && message.image_key"
                  class="dm-image"
                  :src="`/api/v1/uploads/${message.image_key}`"
                  alt="私信图片"
                  loading="lazy"
                />
                <span v-else data-ugc>{{ message.body || "[图片]" }}</span>
                <time class="dm-time">{{ timeLabel(message.created_at) }}</time>
              </li>
            </ol>

            <div v-if="isIncomingRequest" class="dm-request">
              <p>对方请求与你私信，接受前不能回复。</p>
              <div class="dm-request-actions">
                <BaseButton type="button" variant="primary" size="sm" @click="acceptRequest">接受请求</BaseButton>
                <BaseButton type="button" variant="ghost" size="sm" @click="deleteRequest">删除请求</BaseButton>
              </div>
            </div>

            <form v-if="canReply" class="dm-compose" @submit.prevent="send">
              <TextArea id="dm-draft" v-model="draft" label="写消息" :rows="2" hint="最多 1000 个字" />
              <UploadField
                id="dm-image"
                v-model="imageKey"
                label="附加图片（可选）"
                accept="image/jpeg,image/png,image/webp"
                :max-mb="5"
              />
              <BaseButton type="submit" variant="primary" size="sm" :loading="sending">发送</BaseButton>
            </form>
          </template>
          <EmptyState v-else title="选一个会话查看消息" />
        </section>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dm-inbox {
  display: grid;
  gap: var(--sp-3);
}
.dm-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.dm-summary,
.dm-hint {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.dm-new {
  display: grid;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface2);
}
.dm-body {
  display: grid;
  grid-template-columns: minmax(200px, 1fr) minmax(0, 1.6fr);
  gap: var(--sp-3);
  align-items: start;
}
.dm-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--sp-1);
}
.dm-item {
  width: 100%;
  min-height: var(--tap);
  display: flex;
  align-items: flex-start;
  gap: var(--sp-2);
  padding: var(--sp-2);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
  color: var(--text);
  text-align: left;
  cursor: pointer;
}
.dm-item.active {
  border-color: var(--accent);
  background: var(--accent-soft);
}
.dm-item-main {
  min-width: 0;
  display: grid;
  gap: 2px;
  flex: 1;
}
.dm-peer {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-13);
  font-weight: 600;
}
.dm-preview,
.dm-time {
  font-size: var(--fs-11);
  color: var(--muted);
  overflow-wrap: anywhere;
}
.dm-unread {
  min-width: 22px;
  padding: 2px 6px;
  border-radius: var(--r-pill);
  background: var(--accent);
  color: var(--accent-ink);
  font-size: var(--fs-11);
  text-align: center;
}
.dm-detail {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.dm-detail-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  font-size: var(--fs-14);
}
.dm-listing {
  padding: var(--sp-2);
  border-radius: var(--r-md);
  background: var(--surface2);
  font-size: var(--fs-12);
}
.dm-messages {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: var(--sp-2);
  max-height: 320px;
  overflow-y: auto;
}
.dm-message {
  display: grid;
  gap: var(--sp-1);
  padding: var(--sp-2);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  font-size: var(--fs-13);
  overflow-wrap: anywhere;
}
.dm-image {
  max-width: 100%;
  border-radius: var(--r-md);
}
.dm-request {
  display: grid;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border: 1px dashed var(--line);
  border-radius: var(--r-md);
  font-size: var(--fs-13);
}
.dm-request p {
  margin: 0;
}
.dm-request-actions,
.dm-compose {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.dm-compose {
  flex-direction: column;
  align-items: flex-start;
}
@media (max-width: 759px) {
  .dm-body {
    grid-template-columns: 1fr;
  }
}
</style>
