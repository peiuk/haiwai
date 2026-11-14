<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import {
  jsonBody,
  request,
  uploadFile,
  type CommentsResponse,
  type ContentDetail,
  type RoomComment,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import { fmtRelativeTime } from "../utils/time";
import SourceBlock from "./common/SourceBlock.vue";
import ReportButton from "./common/ReportButton.vue";
import Avatar from "./base/Avatar.vue";
import BaseIcon from "./base/BaseIcon.vue";

const props = withDefaults(
  defineProps<{ contentId: string | null; standalone?: boolean }>(),
  { standalone: false },
);

const emit = defineEmits<{
  (e: "close"): void;
}>();

function goBack(): void {
  if (window.history.length > 1) {
    window.history.back();
  } else {
    emit("close");
  }
}

// 非 standalone（弹窗）模式：Esc 关闭 + 锁定背景滚动
function onKeydown(ev: KeyboardEvent): void {
  if (!props.standalone && ev.key === "Escape") {
    emit("close");
  }
}

onMounted(() => {
  if (!props.standalone) {
    document.addEventListener("keydown", onKeydown);
    document.body.style.overflow = "hidden";
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("keydown", onKeydown);
  document.body.style.overflow = "";
});

const auth = useAuthStore();
const toast = useToastStore();

const detail = ref<ContentDetail | null>(null);
const loading = ref(false);
const error = ref("");

const comments = ref<RoomComment[]>([]);
const draft = ref("");
const imageKey = ref("");
const imageBusy = ref(false);
const imageName = ref("");
const emojiOpen = ref(false);
const posting = ref(false);
const togglingLike = ref(false);
const togglingFav = ref(false);
const reposting = ref(false);
const replyInput = ref<HTMLTextAreaElement | null>(null);

// 常用 emoji 面板（系统 Unicode emoji，直接插进文字，后端无需改动）
const EMOJIS = [
  "😀", "😁", "😂", "🤣", "😊", "😍", "🥰", "😘",
  "😎", "🤔", "🙄", "😭", "😅", "😉", "🤗", "😴",
  "👍", "👎", "👏", "🙏", "💪", "🤝", "👌", "✌️",
  "❤️", "💯", "🔥", "🎉", "✨", "🥳", "😱", "🤯",
];

function insertEmoji(emoji: string): void {
  draft.value += emoji;
  emojiOpen.value = false;
  replyInput.value?.focus();
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

const canInteract = computed(() => auth.isLoggedIn);

async function loadDetail(): Promise<void> {
  if (!props.contentId) {
    detail.value = null;
    comments.value = [];
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const [body, replies] = await Promise.all([
      request<ContentDetail>(`/api/v1/contents/${props.contentId}`),
      request<CommentsResponse>(`/api/v1/contents/${props.contentId}/comments`).catch(() => ({ items: [] })),
    ]);
    detail.value = body;
    comments.value = replies.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "内容加载失败";
  } finally {
    loading.value = false;
  }
}

async function toggleLike(): Promise<void> {
  if (!props.contentId || !canInteract.value) {
    toast.show("先注册或登录，再点赞");
    return;
  }
  togglingLike.value = true;
  try {
    const body = await request<{ liked: boolean }>(`/api/v1/contents/${props.contentId}/like`, { method: "POST" });
    if (detail.value) {
      detail.value.liked = body.liked;
    }
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "点赞没有成功");
  } finally {
    togglingLike.value = false;
  }
}

async function toggleFavorite(): Promise<void> {
  if (!props.contentId || !canInteract.value) {
    toast.show("先注册或登录，再收藏");
    return;
  }
  togglingFav.value = true;
  try {
    const body = await request<{ favorited: boolean }>(`/api/v1/contents/${props.contentId}/favorite`, {
      method: "POST",
    });
    if (detail.value) {
      detail.value.favorited = body.favorited;
    }
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "收藏没有成功");
  } finally {
    togglingFav.value = false;
  }
}

async function repost(): Promise<void> {
  const channelId = detail.value?.channel_id;
  if (!props.contentId || !channelId) {
    toast.show("这条内容没有可转发的频道");
    return;
  }
  reposting.value = true;
  try {
    await request(`/api/v1/contents/${props.contentId}/repost`, jsonBody({ channel_id: channelId, body: "" }));
    toast.show("已转发到关注流");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "转发没有成功");
  } finally {
    reposting.value = false;
  }
}

async function postComment(): Promise<void> {
  const text = draft.value.trim();
  const hasImage = Boolean(imageKey.value);
  if ((!text && !hasImage) || text.length > 1000 || !props.contentId) {
    return;
  }
  if (!canInteract.value) {
    toast.show("先注册或登录，再回复");
    return;
  }
  posting.value = true;
  try {
    await request(
      `/api/v1/contents/${props.contentId}/comments`,
      jsonBody({ body: text, image_key: imageKey.value || null }),
    );
    draft.value = "";
    imageKey.value = "";
    imageName.value = "";
    emojiOpen.value = false;
    const replies = await request<CommentsResponse>(`/api/v1/contents/${props.contentId}/comments`);
    comments.value = replies.items;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "回复没有成功");
  } finally {
    posting.value = false;
  }
}

async function toggleCommentLike(comment: RoomComment): Promise<void> {
  if (!props.contentId || !canInteract.value) {
    return;
  }
  try {
    const body = await request<{ liked: boolean; like_count: number }>(
      `/api/v1/contents/${props.contentId}/comments/${comment.id}/like`,
      { method: "POST" },
    );
    comment.liked = body.liked;
    comment.like_count = body.like_count;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "点赞没有成功");
  }
}

watch(() => props.contentId, () => void loadDetail(), { immediate: true });
watch(detail, async (value) => {
  if (value && !props.standalone && window.innerWidth > 760) {
    await nextTick();
    replyInput.value?.focus();
  }
});

</script>

<template>
  <Teleport to="body" :disabled="standalone">
    <!-- 弹窗遮罩：仅非独立页模式 -->
    <div v-if="contentId && !standalone" class="cd-overlay" @click.self="emit('close')">
      <section class="content-detail cd-dialog" role="dialog" aria-modal="true" aria-labelledby="cd-dialog-title">
        <header class="cd-head">
          <h3 id="cd-dialog-title">回复帖子</h3>
          <div class="cd-head-tools">
            <ReportButton v-if="detail" kind="content" :id="detail.content_id" compact />
            <button class="cd-close" type="button" aria-label="关闭回复窗口" @click="emit('close')"><BaseIcon name="i-close" :size="20" /></button>
          </div>
        </header>
        <div class="cd-scroll">
          <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
          <p v-if="loading" class="empty">加载中…</p>

          <template v-if="detail">
            <article class="cd-original">
              <div class="cd-timeline"><Avatar :name="detail.author_name || detail.author_handle || detail.channel_name || '用户'" :size="42" /></div>
              <div class="cd-original-main">
                <div class="cd-original-author">
                  <strong data-ugc>{{ detail.author_name || detail.channel_name || "匿名用户" }}</strong>
                  <span v-if="detail.author_handle && detail.author_name !== detail.author_handle">@{{ detail.author_handle }}</span>
                </div>
                <p v-if="detail.channel_name" class="cd-context">发布于 {{ detail.channel_name }}</p>
                <h2 data-ugc>{{ detail.title }}</h2>
                <p v-if="detail.repost_of" class="cd-repost">转发了「<span data-ugc>{{ detail.repost_of.title }}</span>」</p>
                <p v-if="detail.body || detail.summary" class="cd-summary" data-ugc>{{ detail.body || detail.summary }}</p>
                <div v-if="detail.keywords.length" class="cd-keywords">
                  <span v-for="keyword in detail.keywords" :key="keyword">#{{ keyword }}</span>
                </div>
                <SourceBlock
                  :source-name="detail.author_name || detail.source_name"
                  :licence-ref="detail.licence_ref"
                  :canonical-url="detail.canonical_url"
                  :label="`${detail.title} 的来源与许可`"
                />
                <p class="cd-replying">回复给 <span data-ugc>{{ detail.author_name || detail.author_handle || detail.channel_name || "作者" }}</span></p>
              </div>
            </article>

            <form class="cd-compose" @submit.prevent="postComment">
              <Avatar name="我" :size="42" />
              <div class="cd-compose-main">
                <label class="sr-only" for="cd-comment">写回复</label>
                <textarea id="cd-comment" ref="replyInput" v-model="draft" rows="3" maxlength="1000" placeholder="发布你的回复"></textarea>
                <div v-if="imageKey" class="cd-image-preview">
                  <img :src="`/api/v1/uploads/${imageKey}`" alt="回复图片预览" />
                  <button class="cd-image-remove" type="button" aria-label="移除图片" @click="removeImage">移除</button>
                </div>
                <div class="cd-compose-tools">
                  <div class="cd-emoji-wrap">
                    <button
                      class="cd-tool"
                      type="button"
                      :aria-expanded="emojiOpen"
                      aria-label="插入表情"
                      @click="emojiOpen = !emojiOpen"
                    >😊</button>
                    <div v-if="emojiOpen" class="cd-emoji-panel" role="menu" aria-label="表情">
                      <button
                        v-for="emoji in EMOJIS"
                        :key="emoji"
                        class="cd-emoji"
                        type="button"
                        role="menuitem"
                        :aria-label="`插入 ${emoji}`"
                        @click="insertEmoji(emoji)"
                      >{{ emoji }}</button>
                    </div>
                  </div>
                  <label class="cd-tool" :aria-disabled="imageBusy">
                    <BaseIcon name="i-image" :size="18" />
                    <span class="sr-only">添加图片</span>
                    <input class="cd-file" type="file" accept="image/jpeg,image/png,image/webp" aria-label="添加回复图片" :disabled="imageBusy || Boolean(imageKey)" @change="onImagePick" />
                  </label>
                  <span v-if="imageBusy" class="cd-tool-hint">上传中…</span>
                </div>
                <div class="cd-compose-footer">
                  <span :class="{ 'cd-limit': draft.length >= 950 }">{{ draft.length }} / 1000</span>
                  <button class="cd-send" type="submit" :disabled="posting || (!draft.trim() && !imageKey) || draft.trim().length > 1000">
                    {{ posting ? "发送中…" : "回复" }}
                  </button>
                </div>
              </div>
            </form>

            <div class="cd-replies-head"><h4>回复</h4><span>{{ comments.length }}</span></div>
            <p v-if="comments.length === 0" class="cd-no-replies">还没有回复，来写下第一条。</p>
            <ul v-else class="cd-list cd-list--dialog">
              <li v-for="comment in comments" :key="comment.id" class="cd-item">
                <Avatar :name="comment.author_name || comment.author_handle || '用户'" :size="40" />
                <div class="cd-item-main">
                  <div class="cd-item-meta">
                    <span class="cd-author" data-ugc>{{ comment.author_name || comment.author_handle || "匿名" }}</span>
                    <time class="cd-time" :datetime="comment.created_at">· {{ fmtRelativeTime(comment.created_at) }}</time>
                  </div>
                  <p class="cd-text" data-ugc>{{ comment.body }}</p>
                  <img v-if="comment.image_key" class="cd-comment-img" :src="`/api/v1/uploads/${comment.image_key}`" alt="回复图片" loading="lazy" />
                  <button
                    class="cd-reply-like"
                    type="button"
                    :aria-pressed="comment.liked"
                    :class="{ 'cd-on': comment.liked }"
                    @click="toggleCommentLike(comment)"
                  >
                    <BaseIcon name="i-heart" :size="16" /> {{ comment.like_count || "" }}
                  </button>
                </div>
              </li>
            </ul>
          </template>
        </div>
      </section>
    </div>

    <!-- 独立页模式：内联渲染 -->
    <section v-else-if="contentId" class="content-detail">
      <header class="cd-head">
        <h3>内容详情</h3>
        <button class="btn btn--ghost btn--sm" type="button" @click="goBack">返回</button>
      </header>
      <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
      <p v-if="loading" class="empty">加载中…</p>

      <template v-if="detail">
        <article class="cd-body">
          <h2 data-ugc>{{ detail.title }}</h2>
          <p v-if="detail.repost_of" class="cd-repost">转发了「<span data-ugc>{{ detail.repost_of.title }}</span>」</p>
          <p class="cd-meta">
            <span>{{ detail.author_name || detail.author_handle || "匿名" }}</span>
            <span v-if="detail.channel_name"> · {{ detail.channel_name }}</span>
          </p>
          <p class="cd-summary" data-ugc>{{ detail.body || detail.summary }}</p>
          <div v-if="detail.keywords.length" class="cd-keywords">
            <span v-for="keyword in detail.keywords" :key="keyword" class="tag tag--link"># {{ keyword }}</span>
          </div>
          <SourceBlock
            :source-name="detail.author_name || detail.source_name"
            :licence-ref="detail.licence_ref"
            :canonical-url="detail.canonical_url"
            :label="`${detail.title} 的来源与许可`"
          />
        </article>

        <div class="cd-actions">
          <button
            class="btn btn--outline btn--sm"
            type="button"
            :disabled="togglingLike"
            :class="{ 'cd-on': detail.liked }"
            @click="toggleLike"
          >
            {{ detail.liked ? "已赞" : "赞" }}
          </button>
          <button
            class="btn btn--outline btn--sm"
            type="button"
            :disabled="togglingFav"
            :class="{ 'cd-on': detail.favorited }"
            @click="toggleFavorite"
          >
            {{ detail.favorited ? "已收藏" : "收藏" }}
          </button>
          <button class="btn btn--outline btn--sm" type="button" :disabled="reposting" @click="repost">
            {{ reposting ? "转发中…" : "转发" }}
          </button>
          <ReportButton kind="content" :id="detail.content_id" />
        </div>

        <h4>回复</h4>
        <form class="cd-form" @submit.prevent="postComment">
          <label for="cd-comment">写回复</label>
          <textarea id="cd-comment" v-model="draft" rows="2" placeholder="写下你的回复"></textarea>
          <div v-if="imageKey" class="cd-image-preview">
            <img :src="`/api/v1/uploads/${imageKey}`" alt="回复图片预览" />
            <button class="cd-image-remove" type="button" aria-label="移除图片" @click="removeImage">移除</button>
          </div>
          <div class="cd-compose-tools">
            <div class="cd-emoji-wrap">
              <button class="cd-tool" type="button" :aria-expanded="emojiOpen" aria-label="插入表情" @click="emojiOpen = !emojiOpen">😊</button>
              <div v-if="emojiOpen" class="cd-emoji-panel" role="menu" aria-label="表情">
                <button v-for="emoji in EMOJIS" :key="emoji" class="cd-emoji" type="button" role="menuitem" :aria-label="`插入 ${emoji}`" @click="insertEmoji(emoji)">{{ emoji }}</button>
              </div>
            </div>
            <label class="cd-tool" :aria-disabled="imageBusy">
              <BaseIcon name="i-image" :size="18" />
              <span class="sr-only">添加图片</span>
              <input class="cd-file" type="file" accept="image/jpeg,image/png,image/webp" aria-label="添加回复图片" :disabled="imageBusy || Boolean(imageKey)" @change="onImagePick" />
            </label>
            <span v-if="imageBusy" class="cd-tool-hint">上传中…</span>
          </div>
          <button class="btn btn--primary btn--sm" type="submit" :disabled="posting || (!draft.trim() && !imageKey)">
            {{ posting ? "发送中…" : "发送" }}
          </button>
        </form>

        <p v-if="comments.length === 0" class="empty">还没有回复。</p>
        <ul class="cd-list">
          <li v-for="comment in comments" :key="comment.id" class="cd-item">
            <div class="cd-item-main">
              <div class="cd-item-meta">
                <span class="cd-author" data-ugc>{{ comment.author_name || comment.author_handle || "匿名" }}</span>
                <time class="cd-time" :datetime="comment.created_at">{{ comment.created_at }}</time>
              </div>
              <p class="cd-text" data-ugc>{{ comment.body }}</p>
              <img v-if="comment.image_key" class="cd-comment-img" :src="`/api/v1/uploads/${comment.image_key}`" alt="回复图片" loading="lazy" />
            </div>
            <button
              class="btn btn--ghost btn--sm"
              type="button"
              :class="{ 'cd-on': comment.liked }"
              @click="toggleCommentLike(comment)"
            >
              {{ comment.liked ? "已赞" : "赞" }} {{ comment.like_count }}
            </button>
          </li>
        </ul>
      </template>
    </section>
  </Teleport>
</template>

<style scoped>
/* 弹窗遮罩 + 居中浮层（X 式） */
.cd-overlay {
  position: fixed;
  inset: 0;
  z-index: var(--z-modal);
  display: grid;
  place-items: center;
  padding: var(--sp-4);
  background: color-mix(in srgb, var(--scrim-base) 60%, transparent);
  backdrop-filter: blur(2px);
  animation: cd-fade var(--dur-fast) var(--ease-out);
}
.cd-dialog {
  width: 100%;
  max-width: 600px;
  max-height: min(88vh, 780px);
  background: var(--bg);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 20px 70px color-mix(in srgb, var(--scrim-base) 25%, transparent);
  overflow: hidden;
  animation: cd-pop var(--dur-fast) var(--ease-out);
}
.cd-dialog .cd-head {
  min-height: 58px;
  padding: 0 20px;
  border-bottom: 1px solid var(--border);
}
.cd-scroll {
  max-height: calc(min(88vh, 780px) - 58px);
  overflow: auto;
  display: block;
  scrollbar-width: thin;
}
.cd-close {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  color: var(--text);
}
.cd-head-tools { display: flex; align-items: center; gap: 4px; }
.cd-close:hover { background: var(--hover); }
.cd-original {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 20px 22px 4px;
}
.cd-timeline { position: relative; }
.cd-timeline::after {
  content: "";
  position: absolute;
  top: 52px;
  bottom: -12px;
  left: 20px;
  width: 2px;
  border-radius: 2px;
  background: var(--border);
}
.cd-original-main { min-width: 0; }
.cd-original-author { display: flex; align-items: baseline; gap: 7px; min-width: 0; }
.cd-original-author strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-15); }
.cd-original-author span, .cd-context { color: var(--muted); font-size: var(--fs-12); }
.cd-context { margin: 3px 0 12px; }
.cd-original-main h2 { margin: 10px 0 8px; font-size: var(--fs-17); line-height: 1.4; overflow-wrap: anywhere; }
.cd-original-main .cd-context + h2 { margin-top: 0; }
.cd-original-main .cd-summary { line-height: 1.6; font-size: var(--fs-14); }
.cd-original-main .cd-keywords { margin-top: 10px; }
.cd-original-main .cd-keywords span { color: var(--accent-ink); font-size: var(--fs-13); }
.cd-original-main .cd-repost { margin: 0 0 8px; }
.cd-original-main :deep(.source-block) { margin-top: 10px; }
.cd-replying { margin: 18px 0 12px; color: var(--muted); font-size: var(--fs-13); }
.cd-replying span { color: var(--accent-ink); }
.cd-compose {
  display: grid;
  grid-template-columns: 42px minmax(0, 1fr);
  gap: 12px;
  padding: 8px 22px 18px;
  border-bottom: 1px solid var(--border);
}
.cd-compose-main { min-width: 0; }
.cd-compose textarea {
  display: block;
  width: 100%;
  min-height: 106px;
  padding: 5px 0;
  border: 0;
  outline: none;
  resize: vertical;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: var(--fs-17);
  line-height: 1.5;
}
.cd-compose textarea::placeholder { color: var(--muted); }
.cd-compose-footer { display: flex; align-items: center; justify-content: flex-end; gap: 14px; }
.cd-compose-footer span { color: var(--muted); font-size: var(--fs-12); font-variant-numeric: tabular-nums; }
.cd-compose-footer .cd-limit { color: var(--danger); }
.cd-send {
  min-width: 82px;
  min-height: 38px;
  padding: 0 18px;
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-weight: var(--fw-bold);
  font-size: var(--fs-14);
}
.cd-send:disabled { opacity: 0.5; cursor: not-allowed; }
.cd-compose-tools { display: flex; align-items: center; gap: 8px; padding: 4px 0; }
.cd-emoji-wrap { position: relative; }
.cd-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 34px;
  min-height: 34px;
  padding: 0 6px;
  border: 0;
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-17);
  cursor: pointer;
}
.cd-tool:hover { background: var(--accent-soft); color: var(--accent-ink); }
.cd-file { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
.cd-tool-hint { color: var(--muted); font-size: var(--fs-12); }
.cd-emoji-panel {
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
.cd-emoji {
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
.cd-emoji:hover { background: var(--accent-soft); }
.cd-image-preview { position: relative; display: inline-block; margin: 6px 0 0; }
.cd-image-preview img { display: block; max-width: 200px; max-height: 200px; border-radius: var(--r-md); border: 1px solid var(--line); }
.cd-image-remove {
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
.cd-comment-img { display: block; max-width: 220px; max-height: 220px; margin-top: 6px; border-radius: var(--r-md); border: 1px solid var(--line); }
.cd-replies-head { display: flex; align-items: center; gap: 8px; padding: 16px 22px 6px; }
.cd-replies-head h4 { margin: 0; font-size: var(--fs-15); }
.cd-replies-head span { color: var(--muted); font-size: var(--fs-12); }
.cd-no-replies { margin: 0; padding: 14px 22px 28px; color: var(--muted); font-size: var(--fs-13); }
.cd-list--dialog .cd-item { justify-content: flex-start; padding: 16px 22px; }
.cd-list--dialog .cd-item:last-child { border-bottom: 0; }
.cd-list--dialog .cd-item-main { gap: 7px; }
.cd-list--dialog .cd-text { white-space: pre-wrap; line-height: 1.5; font-size: var(--fs-14); }
.cd-reply-like { display: inline-flex; align-items: center; gap: 5px; justify-self: start; min-height: 32px; padding: 0 7px; border-radius: var(--r-pill); color: var(--muted); font-size: var(--fs-12); }
.cd-reply-like:hover { background: var(--accent-soft); color: var(--accent-ink); }
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
@media (max-width: 760px) {
  .cd-overlay { padding: 0; place-items: stretch; }
  .cd-dialog { max-width: none; max-height: 100dvh; height: 100dvh; border: 0; border-radius: 0; box-shadow: none; }
  .cd-dialog .cd-head { min-height: 56px; padding: 0 14px; }
  .cd-scroll { max-height: calc(100dvh - 56px); }
  .cd-original { padding: 16px 14px 2px; gap: 10px; }
  .cd-compose { padding: 8px 14px 16px; gap: 10px; }
  .cd-replies-head { padding: 16px 14px 6px; }
  .cd-no-replies { padding: 14px 14px 28px; }
  .cd-list--dialog .cd-item { padding: 14px; }
}
@keyframes cd-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes cd-pop {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
.content-detail {
  display: grid;
  gap: var(--sp-4);
}
.content-detail.cd-dialog {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.cd-dialog .cd-head { flex: none; }
.cd-dialog .cd-scroll { min-height: 0; }
.cd-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
}
.cd-head h3 {
  margin: 0;
  font-size: var(--fs-17);
}
.cd-body {
  display: grid;
  gap: var(--sp-2);
  border-bottom: 1px solid var(--border);
  padding-bottom: var(--sp-3);
}
.cd-body h2 {
  margin: 0;
  font-size: var(--fs-19);
  overflow-wrap: anywhere;
}
.cd-repost {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.cd-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.cd-summary {
  margin: 0;
  color: var(--text);
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.cd-keywords {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.cd-actions {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.cd-on {
  color: var(--accent-ink);
  border-color: var(--accent-ink);
}
.cd-form {
  display: grid;
  gap: var(--sp-2);
}
.cd-form label {
  font-size: var(--fs-12);
  color: var(--muted);
}
.cd-form textarea {
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
.cd-form .btn {
  justify-self: end;
}
.cd-list {
  display: grid;
  gap: 0;
  padding: 0;
  margin: 0;
  list-style: none;
}
.cd-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.cd-item-main {
  display: grid;
  gap: var(--sp-1);
  min-width: 0;
  flex: 1;
}
.cd-item-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.cd-author {
  font-weight: var(--fw-semibold);
  color: var(--text);
}
.cd-time {
  color: var(--muted);
  font-size: var(--fs-12);
}
.cd-text {
  margin: 0;
  color: var(--text);
  overflow-wrap: anywhere;
}
</style>
