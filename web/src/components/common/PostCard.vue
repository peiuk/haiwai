<script setup lang="ts">
// PostCard：信息流帖子卡（X 式），对齐 MASTER §17.3 与 prototype-x-style.html 的 .card。
// 结构：头像 + card-head（频道名/官方徽章/handle/时间/置顶）+ 正文 + 媒体网格 + 来源行 + 图标操作栏。
// FeedTab（关注流）与 RecommendTab（推荐流）共用；差异通过可选 props 表达。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import Avatar from "../base/Avatar.vue";
import BaseIcon from "../base/BaseIcon.vue";
import BaseTag from "../base/BaseTag.vue";
import ReportButton from "./ReportButton.vue";
import Lightbox from "./Lightbox.vue";
import PostActions from "./PostActions.vue";
import { fmtRelativeTime } from "../../utils/time";
import { hasOwnTitle } from "../../utils/post";
import type { EmbedCard } from "../../api";
import EmbedConsentCard from "../room/EmbedConsentCard.vue";
import { PROVIDER_NAMES } from "../room/EntryMedia.vue";

const props = withDefaults(
  defineProps<{
    contentId: string;
    title: string;
    summary: string | null;
    channelName: string;
    channelId?: string;
    /** 发帖人 ID：有值时头像和 @handle 可点进其主页 */
    authorId?: string | null;
    authorName?: string;
    authorHandle?: string;
    authorTone?: string;
    authorAvatar?: string;
    /** 是否官方频道（显示官方徽章） */
    certified?: boolean;
    /** 置顶 */
    pinned?: boolean;
    /** 发布时间（ISO） */
    time?: string;
    sourceName: string | null;
    licenceRef: string | null;
    canonicalUrl: string | null;
    keywords?: string[];
    imageKeys?: string[];
    /** 视频 key（post_type=video 时存在） */
    videoKey?: string | null;
    /** 外链视频：走第三方播放同意流程 */
    embed?: EmbedCard | null;
    liked?: boolean;
    favorited?: boolean;
    reposted?: boolean;
    /** 未读标记（关注流） */
    unread?: boolean;
    /** 是否显示加入频道按钮（推荐流） */
    showJoin?: boolean;
    isJoined?: boolean;
    /** 「为什么推荐」文案（推荐流） */
    whyText?: string;
  }>(),
  {
    channelId: "",
    authorId: null,
    authorName: "",
    authorHandle: "",
    authorTone: "",
    authorAvatar: "",
    certified: false,
    pinned: false,
    time: "",
    keywords: () => [],
    imageKeys: () => [],
    videoKey: null,
    embed: null,
    liked: false,
    favorited: false,
    reposted: false,
    unread: false,
    showJoin: false,
    isJoined: false,
    whyText: "",
  },
);

const emit = defineEmits<{
  (e: "like"): void;
  (e: "favorite"): void;
  (e: "repost"): void;
  (e: "open"): void;
  (e: "join"): void;
  (e: "less-like"): void;
  (e: "reported", caseId: string): void;
}>();

const displayChannel = computed(
  () => props.channelName || (props.authorName ? `${props.authorName} 的动态` : "频道"),
);
const displayHandle = computed(
  // @ 后面优先显示用户名（handle），没有时才退回昵称；都没有就不显示（不拿频道 ID 充数）。
  () => props.authorHandle || props.authorName || "",
);

// ---- 「⋯」更多菜单：低频操作（减少此类内容 / 举报）收在这里，不占操作栏 ----
const menuOpen = ref(false);
const menuRef = ref<HTMLElement | null>(null);

function onDocPointer(ev: PointerEvent): void {
  if (menuRef.value && !menuRef.value.contains(ev.target as Node)) menuOpen.value = false;
}

watch(menuOpen, (open) => {
  if (open) document.addEventListener("pointerdown", onDocPointer);
  else document.removeEventListener("pointerdown", onDocPointer);
});

// ---- 图片灯箱（X 平台式：点击放大、多图左右切换） ----
const lightboxIndex = ref(-1);

function openLightbox(index: number): void {
  lightboxIndex.value = index;
}

function closeLightbox(): void {
  lightboxIndex.value = -1;
}

// ---- 视频内联播放：滚动到可视区自动播放 + 循环 + 静音（离开暂停） ----
const videoEl = ref<HTMLVideoElement | null>(null);
const videoPaused = ref(false);
// 用户手动暂停标记：暂停后滚动离开再回来不自动重播，尊重用户意图。
const userPaused = ref(false);
let observer: IntersectionObserver | null = null;

function togglePlay(shouldPlay: boolean): void {
  const v = videoEl.value;
  if (!v) return;
  if (shouldPlay) {
    // 用户已手动暂停时，进入视口也不自动播放，直到用户再次点击播放。
    if (userPaused.value) return;
    v.muted = true; // 自动播放需静音（浏览器策略 + X 式默认静音）
    const p = v.play();
    if (p) {
      p.then(() => {
        videoPaused.value = false;
      }).catch(() => {
        // 自动播放被浏览器拦截时保持暂停，用户点击可手动播放
        videoPaused.value = true;
      });
    }
  } else {
    v.pause();
    videoPaused.value = true;
  }
}

function onVideoClick(): void {
  const v = videoEl.value;
  if (!v) return;
  if (v.paused) {
    userPaused.value = false; // 用户主动点击播放，解除手动暂停状态
    togglePlay(true);
  } else {
    userPaused.value = true; // 用户主动暂停，标记不再自动重播
    v.pause();
    videoPaused.value = true;
  }
}

onMounted(() => {
  if (props.videoKey && "IntersectionObserver" in window) {
    observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // 进入可视区自动播放，离开暂停（对齐 X 信息流）
          togglePlay(entry.isIntersecting);
        }
      },
      // 10% 可见即触发：长视频/竖屏下也能可靠进入自动播放，避免 0.5 阈值永远达不到。
      { threshold: 0.1 },
    );
    if (videoEl.value) observer.observe(videoEl.value);
  }
});

onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointer);
  if (observer) {
    observer.disconnect();
    observer = null;
  }
  if (videoEl.value) {
    videoEl.value.pause();
  }
});
</script>

<template>
  <article class="post-card" :class="{ 'post-card--unread': unread }">
    <!-- 有发帖人时头像进发帖人主页（X 式）；官方/抓取内容没有发帖人，仍显示频道头像 -->
    <RouterLink
      v-if="authorId"
      class="post-avatar"
      :to="{ name: 'user', params: { id: authorId } }"
      :aria-label="`查看 ${authorName || displayHandle} 的主页`"
    >
      <Avatar :name="authorName || displayHandle" :size="40" kind="person" :tone="authorTone || authorName" :image="authorAvatar" />
    </RouterLink>
    <div v-else class="post-avatar">
      <Avatar :name="displayChannel" :size="40" kind="channel" :tone="authorTone || displayChannel" />
    </div>

    <div class="post-body">
      <!-- card-head -->
      <div class="post-head">
        <div class="post-meta">
          <!-- 频道名可点进频道（MASTER：每张卡带「进频道」入口）；没有频道时只显示文字 -->
          <RouterLink
            v-if="channelId"
            class="post-name post-name--link"
            :to="{ name: 'channel', params: { id: channelId } }"
            data-ugc
          >{{ displayChannel }}</RouterLink>
          <span v-else class="post-name" data-ugc>{{ displayChannel }}</span>
          <BaseIcon
            v-if="certified"
            name="i-check"
            :size="16"
            class="post-verified"
            label="官方认证"
          />
          <RouterLink
            v-if="displayHandle && authorId"
            class="post-handle post-handle--link"
            :to="{ name: 'user', params: { id: authorId } }"
            data-ugc
          >@{{ displayHandle }}</RouterLink>
          <span v-else-if="displayHandle" class="post-handle">@{{ displayHandle }}</span>
          <span v-if="time" class="post-time">· {{ fmtRelativeTime(time) }}</span>
          <BaseIcon v-if="pinned" name="i-pin" :size="16" class="post-pin" />
          <span
            v-if="whyText"
            class="post-why-dot"
            role="img"
            :aria-label="whyText"
            :title="whyText"
          >
            <BaseIcon name="i-spark" :size="14" />
          </span>
        </div>
        <div class="post-head-actions">
          <button
            v-if="showJoin && !isJoined"
            type="button"
            class="post-join"
            :aria-label="`加入频道 ${displayChannel}`"
            @click="emit('join')"
          >
            <BaseIcon name="i-plus" :size="13" /> 加入
          </button>
          <span v-else-if="showJoin && isJoined" class="post-joined">
            <BaseIcon name="i-check" :size="13" /> 已加入
          </span>
          <div ref="menuRef" class="post-more" @keydown.esc="menuOpen = false">
            <button
              type="button"
              class="post-more-btn"
              aria-label="更多操作"
              :aria-expanded="menuOpen"
              @click="menuOpen = !menuOpen"
            >
              <BaseIcon name="i-more" :size="18" />
            </button>
            <!-- v-show 而非 v-if：举报弹窗挂在 ReportButton 里，菜单收起时不能卸载它 -->
            <div v-show="menuOpen" class="post-menu" @click="menuOpen = false">
              <button v-if="whyText" type="button" class="post-menu-item" @click="emit('less-like')">
                <BaseIcon name="i-mute" :size="16" /> 减少此类内容
              </button>
              <ReportButton kind="content" :id="contentId" @reported="emit('reported', $event)" />
            </div>
          </div>
        </div>
      </div>

      <!-- card-copy -->
      <div class="post-copy">
        <h3
          v-if="hasOwnTitle(title, summary)"
          class="post-title post-title--link"
          data-ugc
          role="link"
          tabindex="0"
          @click="emit('open')"
          @keydown.enter="emit('open')"
          @keydown.space.prevent="emit('open')"
        >{{ title }}</h3>
        <p v-if="summary" class="post-summary" data-ugc>{{ summary }}</p>
        <div v-if="keywords.length" class="post-tags" data-ugc>
          <RouterLink v-for="kw in keywords" :key="kw" class="post-tag" :to="{ name: 'search', query: { q: `#${kw}` } }">#{{ kw }}</RouterLink>
        </div>
      </div>

      <!-- 媒体：图片网格（点击开灯箱） / 视频（内联自动播放） -->
      <div v-if="imageKeys.length" class="post-media" :class="`media--n${Math.min(imageKeys.length, 6)}`">
        <img
          v-for="(key, i) in imageKeys.slice(0, 6)"
          :key="key"
          :src="`/api/v1/uploads/${key}`"
          :alt="`${title} 图片 ${i + 1}`"
          loading="lazy"
          class="media-frame media-frame--clickable"
          tabindex="0"
          role="button"
          @click="openLightbox(i)"
          @keydown.enter.prevent="openLightbox(i)"
          @keydown.space.prevent="openLightbox(i)"
        />
      </div>
      <div v-else-if="videoKey" class="post-video">
        <video
          ref="videoEl"
          :src="`/api/v1/uploads/${videoKey}`"
          :poster="undefined"
          playsinline
          loop
          muted
          preload="metadata"
          class="media-video"
          :aria-label="`${title} 视频`"
          @click="onVideoClick"
        ></video>
        <button
          v-if="videoPaused"
          type="button"
          class="video-play-hint"
          :aria-label="`播放视频 ${title}`"
          @click="onVideoClick"
        >
          <BaseIcon name="i-play" :size="24" />
        </button>
      </div>

      <EmbedConsentCard
        v-if="embed"
        bare
        :content-id="contentId"
        :title="title"
        :embed-status="embed.status"
        :source-url="canonicalUrl"
        :display-name="PROVIDER_NAMES[embed.provider ?? ''] ?? embed.provider ?? undefined"
      />

      <!-- 来源行 -->
      <div v-if="sourceName" class="post-source">
        <span class="post-src-name">来源 <b>{{ sourceName }}</b></span>
        <BaseTag v-if="licenceRef" variant="default">{{ licenceRef }}</BaseTag>
        <a
          v-if="canonicalUrl"
          :href="canonicalUrl"
          target="_blank"
          rel="noopener"
          class="post-src-link"
        >原文 <BaseIcon name="i-link" :size="14" /></a>
      </div>

      <PostActions
        :content-id="contentId" :title="title" :liked="liked" :favorited="favorited" :reposted="reposted"
        @open="emit('open')" @like="emit('like')" @favorite="emit('favorite')" @repost="emit('repost')"
      >
        <slot name="extra" />
      </PostActions>
    </div>
  </article>

  <Lightbox
    :images="imageKeys.map((k) => `/api/v1/uploads/${k}`)"
    :initial-index="lightboxIndex"
    :alt="title"
    @close="closeLightbox"
  />
</template>

<style scoped>
.post-card {
  display: flex;
  gap: 12px;
  padding: 12px 16px 6px;
  border-bottom: 1px solid var(--border);
  transition: background var(--dur-fast) var(--ease-out);
}
.post-card:hover {
  background: var(--hover);
}
.post-card--unread {
  border-left: 3px solid var(--accent);
}
.post-avatar {
  flex-shrink: 0;
}
.post-body {
  min-width: 0;
  flex: 1;
  display: grid;
  grid-template-columns: minmax(0, 1fr); /* 卡头一行不换行，列宽不能被它撑开 */
  gap: var(--sp-2);
}

/* card-head */
.post-head {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: 30px;
}
.post-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--sp-1);
  /* 一行放下：窄屏时先把 @用户名 截成省略号，再截频道名；时间和「为什么推荐」不截 */
  flex-wrap: nowrap;
  font-size: var(--fs-14);
  line-height: 1.3;
  overflow: hidden;
}
.post-name {
  flex: 0 0 auto;
  max-width: 55%; /* 频道名一般很短，不跟 @用户名 抢；特别长时才截 */
  font-weight: var(--fw-bold);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.post-name--link {
  color: inherit;
  text-decoration: none;
}
.post-name--link:hover,
.post-name--link:focus-visible {
  text-decoration: underline;
}
.post-verified {
  color: var(--accent-ink);
  flex-shrink: 0;
}
.post-handle,
.post-time {
  color: var(--muted);
  flex-shrink: 0;
  white-space: nowrap;
}
.post-handle {
  flex: 0 100 auto; /* 比频道名先缩 */
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
}
.post-pin {
  color: var(--accent-ink);
}
.post-handle--link {
  text-decoration: none;
}
.post-handle--link:hover,
.post-handle--link:focus-visible {
  text-decoration: underline;
}
a.post-avatar {
  align-self: flex-start;
  border-radius: 50%;
}
a.post-avatar:hover {
  opacity: 0.85;
}
.post-why-dot {
  display: inline-flex;
  align-items: center;
  color: var(--muted);
  flex-shrink: 0;
  cursor: help;
}
.post-head-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 2px;
}
.post-join {
  min-height: 30px;
  padding: 0 var(--sp-3);
  border-radius: var(--r-pill);
  border: 1px solid var(--text);
  background: var(--text);
  color: var(--bg);
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 3px;
}
.post-join:hover {
  opacity: 0.85;
}
.post-joined {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: var(--fs-12);
  color: var(--muted);
}

/* card-copy */
.post-copy {
  display: grid;
  gap: var(--sp-2);
  min-width: 0;
}
.post-title {
  margin: 0;
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
  line-height: var(--lh-heading);
  overflow-wrap: anywhere;
}
.post-title--link {
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out);
}
.post-title--link:hover {
  color: var(--accent-ink);
}
.post-title--link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--r-sm);
}
.post-summary {
  margin: 0;
  color: var(--text);
  font-size: var(--fs-14);
  line-height: var(--lh-body);
  overflow-wrap: anywhere;
}
.post-tags {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.post-tag {
  font-size: var(--fs-12);
  color: var(--accent-ink);
  text-decoration: none;
}
.post-tag:hover,
.post-tag:focus-visible {
  text-decoration: underline;
}
.post-more {
  position: relative;
}
.post-more-btn {
  display: grid;
  place-items: center;
  width: 34px;
  height: 34px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.post-more-btn:hover,
.post-more-btn[aria-expanded="true"] {
  background: var(--hover);
  color: var(--text);
}
.post-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: var(--z-sticky);
  display: grid;
  min-width: 168px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--bg);
  box-shadow: var(--shadow-md, 0 8px 24px rgb(0 0 0 / 0.12));
}
.post-menu-item,
.post-menu :deep(.report-trigger) {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  width: 100%;
  min-height: var(--tap);
  padding: 0 10px;
  border: 0;
  border-radius: var(--r-sm, 8px);
  background: transparent;
  color: var(--text);
  font-size: var(--fs-14);
  text-align: left;
  cursor: pointer;
}
.post-menu-item:hover {
  background: var(--hover);
}
.post-menu :deep(.report-wrap) {
  display: grid;
}

/* 媒体网格（对齐原型 media--grid2/3/4） */
.post-media {
  display: grid;
  gap: 2px;
  border-radius: var(--r-md);
  overflow: hidden;
  border: 1px solid var(--border);
}
.media--n1 {
  grid-template-columns: 1fr;
}
.media--n2 {
  grid-template-columns: repeat(2, 1fr);
}
.media--n3 {
  grid-template-columns: 1.35fr 1fr;
}
.media--n3 .media-frame:first-child {
  grid-row: span 2;
}
.media--n4 {
  grid-template-columns: repeat(2, 1fr);
}
/* 5 张：左边大图占两行，右边 2×2；6 张：3×2 */
.media--n5,
.media--n6 {
  grid-template-columns: repeat(3, 1fr);
}
.media--n5 .media-frame:first-child {
  grid-row: span 2;
}
.media-frame {
  width: 100%;
  height: 100%;
  object-fit: cover;
  aspect-ratio: 16 / 10;
  background: var(--surface2);
}
.media--n1 .media-frame {
  aspect-ratio: 16 / 9;
}
.media-frame--clickable {
  cursor: zoom-in;
}
.media-frame--clickable:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: -2px;
}
/* 视频内联播放 */
.post-video {
  position: relative;
  border-radius: var(--r-md);
  overflow: hidden;
  border: 1px solid var(--border);
  background: var(--surface2);
}
.media-video {
  display: block;
  width: 100%;
  max-height: 480px;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  cursor: pointer;
  background: #000;
}
.video-play-hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  border: 0;
  background: rgba(0, 0, 0, 0.35);
  color: #fff;
  cursor: pointer;
}
.video-play-hint:hover {
  background: rgba(0, 0, 0, 0.5);
}

/* 来源行 */
.post-source {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
  font-size: var(--fs-12);
  color: var(--muted);
  line-height: 1.5;
}
.post-src-name b {
  color: var(--text);
  font-weight: var(--fw-semibold);
}
.post-src-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--accent-ink);
  font-size: var(--fs-11);
}
</style>
