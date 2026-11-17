<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import {
  jsonBody,
  request,
  uploadFile,
  type CommentsResponse,
  type RoomComment,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import ReportButton from "./common/ReportButton.vue";
import BaseIcon from "./base/BaseIcon.vue";

const props = defineProps<{ roomId: string | null; roomName: string }>();

const auth = useAuthStore();
const toast = useToastStore();

const items = ref<RoomComment[]>([]);
const nextCursor = ref<string | null>(null);
const loading = ref(false);
const error = ref("");
const draft = ref("");
const imageKey = ref("");
const imageBusy = ref(false);
const imageName = ref("");
const emojiOpen = ref(false);
const posting = ref(false);
const toggling = ref("");

const EMOJIS = [
  "😀", "😁", "😂", "🤣", "😊", "😍", "🥰", "😘",
  "😎", "🤔", "🙄", "😭", "😅", "😉", "🤗", "😴",
  "👍", "👎", "👏", "🙏", "💪", "🤝", "👌", "✌️",
  "❤️", "💯", "🔥", "🎉", "✨", "🥳", "😱", "🤯",
];

function insertEmoji(emoji: string): void {
  draft.value += emoji;
  emojiOpen.value = false;
}

function onImagePick(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  imageBusy.value = true;
  uploadFile(file, file.type || "image/jpeg")
    .then((key) => {
      imageKey.value = key;
      imageName.value = file.name;
      toast.show("图片已上传，提交后才会公开");
    })
    .catch((err) => {
      toast.show(err instanceof Error ? err.message : "图片上传没有成功");
    })
    .finally(() => {
      imageBusy.value = false;
      input.value = "";
    });
}

function removeImage(): void {
  imageKey.value = "";
  imageName.value = "";
}

async function load(reset: boolean): Promise<void> {
  if (!props.roomId) {
    items.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const cursor = reset ? "" : nextCursor.value ?? "";
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const body = await request<CommentsResponse>(`/api/v1/channels/${props.roomId}/comments${query}`);
    items.value = reset ? body.items : [...items.value, ...body.items];
    nextCursor.value = body.next_cursor ?? null;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "留言加载失败";
  } finally {
    loading.value = false;
  }
}

async function post(): Promise<void> {
  const text = draft.value.trim();
  const hasImage = Boolean(imageKey.value);
  if ((!text && !hasImage) || !props.roomId) {
    return;
  }
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再留言");
    return;
  }
  posting.value = true;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/comments`,
      jsonBody({ body: text, image_key: imageKey.value || null }),
    );
    draft.value = "";
    imageKey.value = "";
    imageName.value = "";
    emojiOpen.value = false;
    await load(true);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "留言没有成功");
  } finally {
    posting.value = false;
  }
}

async function toggleLike(comment: RoomComment): Promise<void> {
  if (!props.roomId) {
    return;
  }
  toggling.value = comment.id;
  try {
    const body = await request<{ liked: boolean; like_count: number }>(
      `/api/v1/channels/${props.roomId}/comments/${comment.id}/like`,
      { method: "POST" },
    );
    comment.liked = body.liked;
    comment.like_count = body.like_count;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "点赞没有成功");
  } finally {
    toggling.value = "";
  }
}

// 删除留言：作者本人或房主（后端给 can_delete）。第一次点只变成「确认删除」，再点才真删。
const confirming = ref("");

async function remove(comment: RoomComment): Promise<void> {
  if (confirming.value !== comment.id) {
    confirming.value = comment.id;
    return;
  }
  try {
    await request(`/api/v1/channels/${props.roomId}/comments/${comment.id}`, { method: "DELETE" });
    items.value = items.value.filter((item) => item.id !== comment.id);
    toast.show("留言已删除");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "删除没有成功");
  } finally {
    confirming.value = "";
  }
}

watch(() => props.roomId, () => void load(true));
onMounted(() => void load(true));
</script>

<template>
  <section class="room-comments">
    <header class="rc-head">
      <h3>留言 · 讨论</h3>
      <span v-if="roomName" class="rc-room">{{ roomName }}</span>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>

    <form v-if="roomId" class="rc-form" @submit.prevent="post">
      <label for="room-comment">写留言</label>
      <textarea id="room-comment" v-model="draft" rows="3" placeholder="说说你的想法，支持 @ 提及与 # 关键词"></textarea>
      <div v-if="imageKey" class="rc-image-preview">
        <img :src="`/api/v1/uploads/${imageKey}`" alt="留言图片预览" />
        <button class="rc-image-remove" type="button" aria-label="移除图片" @click="removeImage">移除</button>
      </div>
      <div class="rc-tools">
        <div class="rc-emoji-wrap">
          <button class="rc-tool" type="button" :aria-expanded="emojiOpen" aria-label="插入表情" @click="emojiOpen = !emojiOpen">😊</button>
          <div v-if="emojiOpen" class="rc-emoji-panel" role="menu" aria-label="表情">
            <button v-for="emoji in EMOJIS" :key="emoji" class="rc-emoji" type="button" role="menuitem" :aria-label="`插入 ${emoji}`" @click="insertEmoji(emoji)">{{ emoji }}</button>
          </div>
        </div>
        <label class="rc-tool" :aria-disabled="imageBusy">
          <BaseIcon name="i-image" :size="18" />
          <span class="sr-only">添加图片</span>
          <input class="rc-file" type="file" accept="image/jpeg,image/png,image/webp" aria-label="添加留言图片" :disabled="imageBusy || Boolean(imageKey)" @change="onImagePick" />
        </label>
        <span v-if="imageBusy" class="rc-tool-hint">上传中…</span>
        <button class="btn btn--primary btn--sm rc-submit" type="submit" :disabled="posting || (!draft.trim() && !imageKey)">
          {{ posting ? "发送中…" : "发送" }}
        </button>
      </div>
    </form>

    <p v-if="!loading && items.length === 0" class="empty">还没有留言。</p>

    <ul class="rc-list">
      <li v-for="comment in items" :key="comment.id" class="rc-item">
        <div class="rc-main">
          <div class="rc-meta">
            <RouterLink class="rc-author" :to="{ name: 'user', params: { id: comment.author_id } }" data-ugc>{{ comment.author_name || comment.author_handle || "匿名" }}</RouterLink>
            <time class="rc-time" :datetime="comment.created_at">{{ comment.created_at }}</time>
          </div>
          <p class="rc-text" data-ugc>{{ comment.body }}</p>
          <img v-if="comment.image_key" class="rc-comment-img" :src="`/api/v1/uploads/${comment.image_key}`" alt="留言图片" loading="lazy" />
        </div>
        <button
          class="btn btn--ghost btn--sm rc-like"
          type="button"
          :disabled="toggling === comment.id"
          :class="{ 'rc-like--on': comment.liked }"
          @click="toggleLike(comment)"
        >
          {{ comment.liked ? "已赞" : "赞" }} {{ comment.like_count }}
        </button>
        <button v-if="comment.can_delete" class="btn btn--ghost btn--sm" type="button" @click="remove(comment)">
          {{ confirming === comment.id ? "确认删除" : "删除" }}
        </button>
        <ReportButton
          kind="comment"
          :id="comment.id"
          :channel-id="roomId || ''"
          compact
          :label="`举报留言`"
        />
      </li>
    </ul>

    <div v-if="nextCursor" class="rc-more">
      <button class="btn btn--outline" type="button" :disabled="loading" @click="load(false)">
        {{ loading ? "加载中…" : "加载更多" }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.room-comments {
  display: grid;
  gap: var(--sp-4);
}
.rc-head {
  display: flex;
  align-items: baseline;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.rc-head h3 {
  margin: 0;
  font-size: var(--fs-17);
}
.rc-room {
  color: var(--muted);
  font-size: var(--fs-12);
}
.rc-form {
  display: grid;
  gap: var(--sp-2);
}
.rc-form label {
  font-size: var(--fs-12);
  color: var(--muted);
}
.rc-form textarea {
  width: 100%;
  min-height: var(--tap);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  padding: 10px;
  background: var(--bg);
  color: var(--text);
  font-size: var(--fs-14);
  resize: vertical;
}
.rc-form .btn {
  justify-self: end;
}
.rc-tools {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.rc-submit {
  margin-left: auto;
}
.rc-emoji-wrap {
  position: relative;
}
.rc-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  min-height: 34px;
  padding: 0 6px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--bg);
  color: var(--muted);
  font-size: var(--fs-17);
  cursor: pointer;
}
.rc-tool:hover {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.rc-file {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
.rc-tool-hint {
  color: var(--muted);
  font-size: var(--fs-12);
}
.rc-emoji-panel {
  position: absolute;
  left: 0;
  bottom: calc(100% + 6px);
  z-index: var(--z-modal);
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  width: 288px;
  padding: 8px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.rc-emoji {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 34px;
  border: 0;
  border-radius: var(--r-sm);
  background: transparent;
  font-size: var(--fs-18);
  cursor: pointer;
}
.rc-emoji:hover {
  background: var(--accent-soft);
}
.rc-image-preview {
  position: relative;
  display: inline-block;
}
.rc-image-preview img {
  display: block;
  max-width: 200px;
  max-height: 200px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
}
.rc-image-remove {
  position: absolute;
  top: 6px;
  right: 6px;
  min-height: 28px;
  padding: 0 10px;
  border: 0;
  border-radius: var(--r-pill);
  background: color-mix(in srgb, var(--scrim-base) 70%, transparent);
  color: #fff;
  font-size: var(--fs-12);
  cursor: pointer;
}
.rc-comment-img {
  display: block;
  max-width: 220px;
  max-height: 220px;
  margin-top: 6px;
  border-radius: var(--r-md);
  border: 1px solid var(--line);
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
.rc-list {
  display: grid;
  gap: 0;
  padding: 0;
  margin: 0;
  list-style: none;
}
.rc-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.rc-main {
  display: grid;
  gap: var(--sp-1);
  min-width: 0;
  flex: 1;
}
.rc-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.rc-author {
  font-weight: var(--fw-semibold);
  color: var(--text);
  text-decoration: none;
}
.rc-author:hover {
  text-decoration: underline;
}
.rc-time {
  color: var(--muted);
  font-size: var(--fs-12);
}
.rc-text {
  margin: 0;
  color: var(--text);
  overflow-wrap: anywhere;
}
.rc-like {
  flex-shrink: 0;
}
.rc-like--on {
  color: var(--accent-ink);
}
.rc-more {
  display: flex;
  justify-content: center;
}
</style>
