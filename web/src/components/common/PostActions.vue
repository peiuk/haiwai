<script setup lang="ts">
// 帖子操作栏：回复 / 转发 / 喜欢 / 收藏 / 分享（纯图标，对齐 MASTER §17.3 序 6 ActionBar）。
// PostCard 和房间条目共用；点赞、收藏的请求由使用方处理（usePostReactions）。
import { ref, watch } from "vue";
import BaseIcon from "../base/BaseIcon.vue";
import { useToastStore } from "../../stores/toast";

const props = defineProps<{
  contentId: string;
  title: string;
  liked?: boolean;
  likeCount?: number;
  favorited?: boolean;
  reposted?: boolean;
  /** 不显示转发（房间里转发会在同一个房间多出一条重复内容） */
  noRepost?: boolean;
}>();

const emit = defineEmits<{
  (e: "open"): void;
  (e: "like"): void;
  (e: "favorite"): void;
  (e: "repost"): void;
}>();

// 点赞动画：点击瞬间弹跳；liked 置真后红心放大脉冲
const likePop = ref(false);
const likedPulse = ref(false);
let likedTimer: ReturnType<typeof setTimeout> | undefined;

function onLike(): void {
  likePop.value = true;
  setTimeout(() => {
    likePop.value = false;
  }, 300);
  emit("like");
}

watch(
  () => props.liked,
  (val) => {
    if (val) {
      likedPulse.value = true;
      if (likedTimer) clearTimeout(likedTimer);
      likedTimer = setTimeout(() => {
        likedPulse.value = false;
      }, 450);
    }
  },
);

// 分享：优先系统分享面板 → 复制链接（不发任何外部请求），对齐原型 shareLink()。
const toast = useToastStore();

function shareContent(): void {
  const url = `${window.location.origin}/content/${props.contentId}`;
  const title = props.title || "海外圈";
  const nav = navigator;
  if (typeof nav.share === "function") {
    nav
      .share({ title, url })
      .then(() => toast.show("已打开系统分享"))
      .catch(() => {
        /* 用户取消分享，静默 */
      });
    return;
  }
  if (nav.clipboard && typeof nav.clipboard.writeText === "function") {
    nav.clipboard
      .writeText(url)
      .then(() => toast.show("链接已复制，可以粘贴发给朋友"))
      .catch(() => toast.show("复制失败，请长按地址栏复制链接"));
    return;
  }
  toast.show("复制失败，请长按地址栏复制链接");
}
</script>

<template>
  <div class="post-actions">
    <button type="button" class="act" aria-label="回复" @click="emit('open')">
      <BaseIcon name="i-reply" :size="17" />
    </button>
    <button
      v-if="!noRepost"
      type="button"
      class="act"
      :class="{ 'act--on': reposted }"
      :aria-pressed="reposted"
      aria-label="转发"
      @click="emit('repost')"
    >
      <BaseIcon name="i-repost" :size="17" />
    </button>
    <button
      type="button"
      class="act act--like"
      :class="{ 'act--on': liked, 'act--pop': likePop, 'act--pulse': likedPulse }"
      :aria-pressed="liked"
      :aria-label="likeCount ? `喜欢，${likeCount} 个赞` : '喜欢'"
      @click="onLike"
    >
      <BaseIcon :name="liked ? 'i-heart-fill' : 'i-heart'" :size="17" />
      <span v-if="likeCount" class="act-count">{{ likeCount }}</span>
    </button>
    <button
      type="button"
      class="act act--fav"
      :class="{ 'act--on': favorited }"
      :aria-pressed="favorited"
      aria-label="收藏"
      @click="emit('favorite')"
    >
      <BaseIcon :name="favorited ? 'i-bookmark-fill' : 'i-bookmark'" :size="17" />
    </button>
    <button type="button" class="act" aria-label="分享" @click="shareContent">
      <BaseIcon name="i-share" :size="17" />
    </button>
    <slot />
  </div>
</template>

<style scoped>
/* 操作栏：纯图标，space-between 等距（对齐原型 .actions） */
.post-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  max-width: 420px;
  margin-top: 4px;
  color: var(--muted);
}
.act {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 44px;
  height: 34px;
  min-height: 34px;
  border-radius: var(--r-pill);
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out);
}
.act:hover {
  color: var(--accent-ink);
  background: var(--accent-soft);
}
.act--on {
  color: var(--accent-ink);
}
/* 有数字时按钮随内容变宽，不挤压图标 */
.act--like {
  width: auto;
  min-width: 44px;
  gap: 4px;
  padding: 0 8px;
}
.act-count {
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
/* 点赞爱心：激活与悬停均为爱心红 */
.act--like.act--on {
  color: var(--love);
}
.act--like:hover {
  color: var(--love);
  background: var(--love-soft);
}
/* 收藏书签：激活与悬停同为红色（与点赞一致） */
.act--fav.act--on {
  color: var(--love);
}
.act--fav:hover {
  color: var(--love);
  background: var(--love-soft);
}
/* 点赞弹跳（点击瞬间） */
.act--pop {
  animation: act-pop 0.3s var(--ease-out);
}
@keyframes act-pop {
  0% { transform: scale(1); }
  40% { transform: scale(1.35); }
  70% { transform: scale(0.92); }
  100% { transform: scale(1); }
}
/* 点赞成功红心脉冲 */
.act--pulse .base-icon {
  animation: act-pulse 0.45s var(--ease-out);
}
@keyframes act-pulse {
  0% { transform: scale(1); }
  30% { transform: scale(1.4); }
  60% { transform: scale(0.9); }
  100% { transform: scale(1); }
}
</style>
