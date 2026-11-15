<script setup lang="ts">
// 帖子详情：弹窗（信息流点开）与独立页（/content/:id）共用一套模板。
// 结构对齐 X 的帖子详情：作者 → 正文 → 图片/视频 → 发布时间 → 互动栏 → 回复列表 → 底部回复框。
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
import { useLoginPromptStore } from "../stores/loginPrompt";
import { fmtRelativeTime } from "../utils/time";
import SourceBlock from "./common/SourceBlock.vue";
import ReportButton from "./common/ReportButton.vue";
import Lightbox from "./common/Lightbox.vue";
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
const loginPrompt = useLoginPromptStore();

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
const lightboxIndex = ref(-1);

const authorLabel = computed(
  () => detail.value?.author_name || detail.value?.author_handle || detail.value?.channel_name || "匿名用户",
);
const images = computed(() => {
  const d = detail.value;
  if (!d) return [];
  const keys = d.image_keys?.length ? d.image_keys : d.image_key ? [d.image_key] : [];
  return keys.slice(0, 4).map((k) => `/api/v1/uploads/${k}`);
});
const publishedText = computed(() => {
  const at = detail.value?.published_at;
  if (!at) return "";
  const date = new Date(at);
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleString("zh-CN", { year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit" });
});

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

function focusReply(): void {
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

/** 游客：弹出登录，登录成功后自动完成刚才的操作。 */
function needLogin(verb: string, action: () => void): boolean {
  if (auth.isLoggedIn) return false;
  loginPrompt.require(`登录后就能${verb}，登录成功会自动帮你${verb}。`, action);
  return true;
}

async function toggleLike(): Promise<void> {
  if (!props.contentId || needLogin("点赞", () => void toggleLike())) return;
  togglingLike.value = true;
  try {
    const body = await request<{ liked: boolean }>(`/api/v1/contents/${props.contentId}/like`, { method: "POST" });
    if (detail.value) detail.value.liked = body.liked;
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "点赞没有成功");
  } finally {
    togglingLike.value = false;
  }
}

async function toggleFavorite(): Promise<void> {
  if (!props.contentId || needLogin("收藏", () => void toggleFavorite())) return;
  togglingFav.value = true;
  try {
    const body = await request<{ favorited: boolean }>(`/api/v1/contents/${props.contentId}/favorite`, {
      method: "POST",
    });
    if (detail.value) detail.value.favorited = body.favorited;
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
  if (needLogin("转发", () => void repost())) return;
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

// 分享：优先系统分享面板，其次复制链接（与帖子卡一致）
function share(): void {
  if (!props.contentId) return;
  const url = `${window.location.origin}/content/${props.contentId}`;
  if (typeof navigator.share === "function") {
    navigator.share({ title: detail.value?.title || "海外圈", url }).catch(() => undefined);
    return;
  }
  if (navigator.clipboard?.writeText) {
    navigator.clipboard
      .writeText(url)
      .then(() => toast.show("链接已复制，可以粘贴发给朋友"))
      .catch(() => toast.show("复制失败，请长按地址栏复制链接"));
    return;
  }
  toast.show("复制失败，请长按地址栏复制链接");
}

async function postComment(): Promise<void> {
  const text = draft.value.trim();
  const hasImage = Boolean(imageKey.value);
  if ((!text && !hasImage) || text.length > 1000 || !props.contentId) {
    return;
  }
  if (needLogin("回复", () => void postComment())) return;
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

/** 弹层里点进用户主页时顺手关掉弹层，返回列表时不会还挂着。 */
function leaveOverlay(): void {
  if (!props.standalone) emit("close");
}

async function toggleCommentLike(comment: RoomComment): Promise<void> {
  if (!props.contentId || needLogin("点赞", () => void toggleCommentLike(comment))) return;
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
    <!-- 弹窗模式外面套遮罩；独立页模式直接内联 -->
    <div v-if="contentId" :class="standalone ? 'cd-page' : 'cd-overlay'" @click.self="!standalone && emit('close')">
      <section
        class="content-detail"
        :class="{ 'cd-dialog': !standalone }"
        :role="standalone ? undefined : 'dialog'"
        :aria-modal="standalone ? undefined : 'true'"
        aria-labelledby="cd-dialog-title"
      >
        <header class="cd-head">
          <button v-if="standalone" class="cd-close" type="button" aria-label="返回" @click="goBack">
            <BaseIcon name="i-back" :size="20" />
          </button>
          <h3 id="cd-dialog-title">帖子详情</h3>
          <div class="cd-head-tools">
            <ReportButton v-if="detail" kind="content" :id="detail.content_id" compact />
            <button v-if="!standalone" class="cd-close" type="button" aria-label="关闭帖子详情" @click="emit('close')">
              <BaseIcon name="i-close" :size="20" />
            </button>
          </div>
        </header>

        <div class="cd-scroll">
          <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
          <p v-if="loading && !detail" class="cd-loading" role="status">加载中…</p>

          <template v-if="detail">
            <article class="cd-original">
              <div class="cd-author-row">
                <RouterLink
                  v-if="detail.author_id"
                  class="cd-user-link"
                  :to="{ name: 'user', params: { id: detail.author_id } }"
                  :aria-label="`查看 ${authorLabel} 的主页`"
                  @click="leaveOverlay"
                ><Avatar :name="authorLabel" :size="44" kind="person" :image="detail.author_avatar" /></RouterLink>
                <Avatar v-else :name="authorLabel" :size="44" />
                <div class="cd-author-text">
                  <RouterLink
                    v-if="detail.author_id"
                    class="cd-user-link"
                    :to="{ name: 'user', params: { id: detail.author_id } }"
                    @click="leaveOverlay"
                  ><strong data-ugc>{{ authorLabel }}</strong></RouterLink>
                  <strong v-else data-ugc>{{ authorLabel }}</strong>
                  <span>
                    <template v-if="detail.author_handle">@{{ detail.author_handle }}</template>
                    <template v-if="detail.channel_name"> · 发布于 {{ detail.channel_name }}</template>
                  </span>
                </div>
              </div>

              <p v-if="detail.repost_of" class="cd-repost">转发了「<span data-ugc>{{ detail.repost_of.title }}</span>」</p>
              <h2 data-ugc>{{ detail.title }}</h2>
              <p v-if="(detail.body || detail.summary) && (detail.body || detail.summary) !== detail.title" class="cd-summary" data-ugc>
                {{ detail.body || detail.summary }}
              </p>

              <div v-if="images.length" class="cd-media" :class="`cd-media--n${images.length}`">
                <img
                  v-for="(src, i) in images"
                  :key="src"
                  :src="src"
                  :alt="`${detail.title} 图片 ${i + 1}`"
                  loading="lazy"
                  tabindex="0"
                  role="button"
                  @click="lightboxIndex = i"
                  @keydown.enter.prevent="lightboxIndex = i"
                  @keydown.space.prevent="lightboxIndex = i"
                />
              </div>
              <video
                v-else-if="detail.video_key"
                class="cd-video"
                :src="`/api/v1/uploads/${detail.video_key}`"
                controls
                playsinline
                preload="metadata"
                :aria-label="`${detail.title} 视频`"
              ></video>

              <div v-if="detail.keywords.length || detail.city_topic" class="cd-keywords" data-ugc>
                <span v-if="detail.city_topic"><BaseIcon name="i-pin" :size="13" />{{ detail.city_topic }}</span>
                <span v-for="keyword in detail.keywords" :key="keyword">#{{ keyword }}</span>
              </div>

              <SourceBlock
                :source-name="detail.author_name || detail.source_name"
                :licence-ref="detail.licence_ref"
                :canonical-url="detail.canonical_url"
                :label="`${detail.title} 的来源与许可`"
              />

              <p v-if="publishedText" class="cd-time-line">
                <time :datetime="detail.published_at ?? undefined">{{ publishedText }}</time>
              </p>

              <div class="cd-actbar">
                <button type="button" class="cd-act" aria-label="回复" @click="focusReply">
                  <BaseIcon name="i-reply" :size="19" />
                </button>
                <button type="button" class="cd-act" aria-label="转发" :disabled="reposting" @click="repost">
                  <BaseIcon name="i-repost" :size="19" />
                </button>
                <button
                  type="button"
                  class="cd-act cd-act--like"
                  :class="{ 'cd-act--on': detail.liked }"
                  :aria-pressed="detail.liked"
                  aria-label="喜欢"
                  :disabled="togglingLike"
                  @click="toggleLike"
                >
                  <BaseIcon :name="detail.liked ? 'i-heart-fill' : 'i-heart'" :size="19" />
                </button>
                <button
                  type="button"
                  class="cd-act cd-act--fav"
                  :class="{ 'cd-act--on': detail.favorited }"
                  :aria-pressed="detail.favorited"
                  aria-label="收藏"
                  :disabled="togglingFav"
                  @click="toggleFavorite"
                >
                  <BaseIcon :name="detail.favorited ? 'i-bookmark-fill' : 'i-bookmark'" :size="19" />
                </button>
                <button type="button" class="cd-act" aria-label="分享" @click="share">
                  <BaseIcon name="i-share" :size="19" />
                </button>
              </div>
            </article>

            <div class="cd-replies-head"><h4>回复</h4><span>{{ comments.length }}</span></div>
            <p v-if="comments.length === 0" class="cd-no-replies">还没有回复，来写下第一条。</p>
            <ul v-else class="cd-list">
              <li v-for="comment in comments" :key="comment.id" class="cd-item">
                <RouterLink
                  class="cd-user-link"
                  :to="{ name: 'user', params: { id: comment.author_id } }"
                  :aria-label="`查看 ${comment.author_name || comment.author_handle || '用户'} 的主页`"
                  @click="leaveOverlay"
                ><Avatar :name="comment.author_name || comment.author_handle || '用户'" :size="40" kind="person" :image="comment.author_avatar" /></RouterLink>
                <div class="cd-item-main">
                  <div class="cd-item-meta">
                    <RouterLink
                      class="cd-author cd-user-link"
                      :to="{ name: 'user', params: { id: comment.author_id } }"
                      data-ugc
                      @click="leaveOverlay"
                    >{{ comment.author_name || comment.author_handle || "匿名" }}</RouterLink>
                    <time class="cd-time" :datetime="comment.created_at">· {{ fmtRelativeTime(comment.created_at) }}</time>
                  </div>
                  <p class="cd-text" data-ugc>{{ comment.body }}</p>
                  <img v-if="comment.image_key" class="cd-comment-img" :src="`/api/v1/uploads/${comment.image_key}`" alt="回复图片" loading="lazy" />
                  <button
                    class="cd-reply-like"
                    type="button"
                    :aria-pressed="comment.liked"
                    :aria-label="`赞这条回复，当前 ${comment.like_count || 0} 个赞`"
                    :class="{ 'cd-reply-like--on': comment.liked }"
                    @click="toggleCommentLike(comment)"
                  >
                    <BaseIcon :name="comment.liked ? 'i-heart-fill' : 'i-heart'" :size="16" /> {{ comment.like_count || "" }}
                  </button>
                </div>
              </li>
            </ul>

            <!-- 回复框固定在底部：先看正文和回复，再决定要不要回 -->
            <form class="cd-compose" @submit.prevent="postComment">
              <Avatar :name="auth.displayName || '我'" :size="40" :image="auth.profile?.avatar_key" />
              <div class="cd-compose-main">
                <label class="sr-only" for="cd-comment">写回复</label>
                <textarea
                  id="cd-comment"
                  ref="replyInput"
                  v-model="draft"
                  rows="1"
                  maxlength="1000"
                  :placeholder="`回复 ${authorLabel}`"
                ></textarea>
                <div v-if="imageKey" class="cd-image-preview">
                  <img :src="`/api/v1/uploads/${imageKey}`" alt="回复图片预览" />
                  <button class="cd-image-remove" type="button" aria-label="移除图片" @click="removeImage">移除</button>
                </div>
                <div class="cd-compose-footer">
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
                  <span v-if="draft.length >= 800" :class="{ 'cd-limit': draft.length >= 950 }">{{ draft.length }} / 1000</span>
                  <button class="cd-send" type="submit" :disabled="posting || (!draft.trim() && !imageKey) || draft.trim().length > 1000">
                    {{ posting ? "发送中…" : "回复" }}
                  </button>
                </div>
              </div>
            </form>
          </template>
        </div>
      </section>
    </div>
  </Teleport>

  <Lightbox
    v-if="detail"
    :images="images"
    :initial-index="lightboxIndex"
    :alt="detail.title"
    @close="lightboxIndex = -1"
  />
</template>

<style scoped>
/* ---- 外层：弹窗遮罩（X 式居中浮层）/ 独立页 ---- */
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
.content-detail {
  display: flex;
  flex-direction: column;
  background: var(--bg);
}
.cd-dialog {
  width: 100%;
  max-width: 600px;
  max-height: min(88vh, 780px);
  border: 1px solid var(--border);
  border-radius: 20px;
  box-shadow: 0 20px 70px color-mix(in srgb, var(--scrim-base) 25%, transparent);
  overflow: hidden;
  animation: cd-pop var(--dur-fast) var(--ease-out);
}

/* ---- 顶栏 ---- */
.cd-head {
  flex: none;
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 56px;
  padding: 0 var(--sp-3) 0 var(--sp-4);
  border-bottom: 1px solid var(--border);
  background: color-mix(in srgb, var(--bg) 90%, transparent);
}
.cd-page .cd-head {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  padding-left: var(--sp-1);
  backdrop-filter: blur(12px);
}
.cd-head h3 {
  flex: 1;
  margin: 0;
  font-size: var(--fs-17);
}
.cd-head-tools { display: flex; align-items: center; gap: 4px; }
.cd-close {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  color: var(--text);
}
.cd-close:hover { background: var(--hover); }

/* ---- 滚动区：弹窗里自己滚，独立页跟随页面滚 ---- */
.cd-dialog .cd-scroll {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: auto;
  scrollbar-width: thin;
}
.cd-dialog .cd-compose { margin-top: auto; }
.cd-loading {
  padding: var(--sp-6) var(--sp-4);
  color: var(--muted);
  text-align: center;
}

/* ---- 正文 ---- */
.cd-original {
  padding: var(--sp-4) var(--sp-4) 0;
}
.cd-author-row {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-width: 0;
}
.cd-author-text {
  display: grid;
  min-width: 0;
}
.cd-author-text strong,
.cd-author-text span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.cd-author-text strong { font-size: var(--fs-15); }
.cd-author-text span { color: var(--muted); font-size: var(--fs-13); }
.cd-repost {
  margin: var(--sp-3) 0 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.cd-original h2 {
  margin: var(--sp-3) 0 0;
  font-size: var(--fs-19);
  line-height: 1.4;
  overflow-wrap: anywhere;
}
.cd-summary {
  margin: var(--sp-2) 0 0;
  color: var(--text);
  font-size: var(--fs-16);
  line-height: 1.65;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.cd-media {
  display: grid;
  gap: 2px;
  margin-top: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  overflow: hidden;
}
.cd-media img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: zoom-in;
}
.cd-media--n1 img { max-height: 560px; }
.cd-media--n2,
.cd-media--n3,
.cd-media--n4 {
  grid-template-columns: 1fr 1fr;
  aspect-ratio: 16 / 10;
}
.cd-media--n3,
.cd-media--n4 { grid-template-rows: 1fr 1fr; }
.cd-media--n3 img:first-child { grid-row: span 2; }
.cd-media img:focus-visible { outline-offset: -3px; }
.cd-video {
  display: block;
  width: 100%;
  max-height: 560px;
  margin-top: var(--sp-3);
  border-radius: var(--r-md);
  background: #000;
}
.cd-keywords {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 10px;
  margin-top: var(--sp-3);
}
.cd-keywords span {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  color: var(--accent-ink);
  font-size: var(--fs-14);
}
.cd-original :deep(.source-block) { margin-top: var(--sp-3); }
.cd-time-line {
  margin: var(--sp-3) 0 0;
  color: var(--muted);
  font-size: var(--fs-14);
}

/* ---- 互动栏 ---- */
.cd-actbar {
  display: flex;
  justify-content: space-around;
  margin-top: var(--sp-3);
  padding: 2px 0;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
}
.cd-act {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  color: var(--muted);
  transition: color var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out);
}
.cd-act:hover { background: var(--accent-soft); color: var(--accent-ink); }
.cd-act:disabled { opacity: 0.6; }
.cd-act--like:hover,
.cd-act--like.cd-act--on { color: var(--danger); }
.cd-act--like:hover { background: var(--danger-soft); }
.cd-act--fav.cd-act--on { color: var(--accent-ink); }

/* ---- 回复列表 ---- */
.cd-replies-head { display: flex; align-items: center; gap: 8px; padding: var(--sp-4) var(--sp-4) 6px; }
.cd-replies-head h4 { margin: 0; font-size: var(--fs-15); }
.cd-replies-head span { color: var(--muted); font-size: var(--fs-13); }
.cd-no-replies { margin: 0; padding: 14px var(--sp-4) 28px; color: var(--muted); font-size: var(--fs-14); }
.cd-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.cd-item {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: 14px var(--sp-4);
  border-bottom: 1px solid var(--border);
}
.cd-item:last-child { border-bottom: 0; }
.cd-item-main {
  display: grid;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.cd-item-meta {
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  flex-wrap: wrap;
}
.cd-author { font-weight: var(--fw-semibold); color: var(--text); }
.cd-user-link { color: inherit; text-decoration: none; border-radius: 50%; }
.cd-user-link:hover strong, a.cd-author:hover { text-decoration: underline; }
.cd-time { color: var(--muted); font-size: var(--fs-13); }
.cd-text {
  margin: 0;
  color: var(--text);
  font-size: var(--fs-15);
  line-height: 1.5;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.cd-comment-img { display: block; max-width: 220px; max-height: 220px; border-radius: var(--r-md); border: 1px solid var(--line); }
.cd-reply-like {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  justify-self: start;
  min-height: 32px;
  margin-left: -7px;
  padding: 0 7px;
  border-radius: var(--r-pill);
  color: var(--muted);
  font-size: var(--fs-13);
}
.cd-reply-like:hover { background: var(--danger-soft); color: var(--danger); }
.cd-reply-like--on { color: var(--danger); }

/* ---- 底部回复框 ---- */
.cd-compose {
  position: sticky;
  bottom: 0;
  display: grid;
  grid-template-columns: 40px minmax(0, 1fr);
  gap: var(--sp-3);
  padding: 10px var(--sp-4) 10px;
  border-top: 1px solid var(--border);
  background: var(--bg);
}
.cd-compose-main { min-width: 0; }
.cd-compose textarea {
  display: block;
  width: 100%;
  min-height: 40px;
  max-height: 160px;
  padding: 8px 0;
  border: 0;
  outline: none;
  resize: none;
  field-sizing: content; /* 支持的浏览器里随内容自动长高 */
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: var(--fs-16);
  line-height: 1.5;
}
.cd-compose:focus-within { border-top-color: var(--accent); }
.cd-compose textarea::placeholder { color: var(--muted); }
.cd-compose-footer { display: flex; align-items: center; gap: 10px; }
.cd-compose-footer > span { color: var(--muted); font-size: var(--fs-12); font-variant-numeric: tabular-nums; }
.cd-compose-footer .cd-limit { color: var(--danger); }
.cd-compose-tools { flex: 1; display: flex; align-items: center; gap: 4px; }
.cd-send {
  min-width: 76px;
  min-height: 36px;
  padding: 0 16px;
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-weight: var(--fw-bold);
  font-size: var(--fs-14);
}
.cd-send:disabled { opacity: 0.5; cursor: not-allowed; }
.cd-emoji-wrap { position: relative; }
.cd-tool {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  min-height: 36px;
  padding: 0 6px;
  border: 0;
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-17);
  cursor: pointer;
}
.cd-tool:hover { background: var(--accent-soft); }
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
.cd-image-preview { position: relative; display: inline-block; margin: 6px 0; }
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
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }

@media (max-width: 760px) {
  .cd-overlay { padding: 0; place-items: stretch; }
  .cd-dialog { max-width: none; max-height: 100dvh; height: 100dvh; border: 0; border-radius: 0; box-shadow: none; }
  .cd-original { padding: var(--sp-3) var(--sp-4) 0; }
  .cd-compose { padding-bottom: calc(10px + env(safe-area-inset-bottom)); }
  /* 独立页：回复框停在底部导航栏上方 */
  .cd-page .cd-compose {
    bottom: calc(var(--bottom-bar) + env(safe-area-inset-bottom));
    padding-bottom: 10px;
  }
}
@keyframes cd-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}
@keyframes cd-pop {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}
@media (prefers-reduced-motion: reduce) {
  .cd-overlay,
  .cd-dialog { animation: none; }
}
</style>
