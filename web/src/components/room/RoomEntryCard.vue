<script setup lang="ts">
// 单条房间条目的视觉卡片：按 room_type 分支渲染。
// series → 集号方块 + 进度；film → 片单卡（封面图 + 衬线标题）；video → 缩略卡 + 版权徽章；general → 帖子卡。
// 各类条目都可带图片（最多 4 张）和一段视频，由 EntryMedia 统一渲染。
import { computed } from "vue";
import type { RoomItem } from "../../api";
import BaseIcon from "../base/BaseIcon.vue";
import EntryMedia from "./EntryMedia.vue";
import BaseTag from "../base/BaseTag.vue";
import SourceBlock from "../common/SourceBlock.vue";
import ReportButton from "../common/ReportButton.vue";
import EmbedConsentCard from "./EmbedConsentCard.vue";

const props = defineProps<{
  item: RoomItem;
  roomType: string;
  isOwner: boolean;
}>();

const emit = defineEmits<{
  (e: "watched"): void;
  (e: "toggle-watch", mark: "want" | "watched"): void;
  (e: "reorder", direction: "up" | "down"): void;
}>();

const episodeLabel = computed(() => {
  if (props.item.season == null || props.item.episode == null) return "";
  return `S${String(props.item.season).padStart(2, "0")}E${String(props.item.episode).padStart(3, "0")}`;
});

// 条目图片：新数据用 image_keys，老数据只有 image_key；最多显示 4 张（电影的第一张作封面）
const images = computed(() => (props.item.image_keys?.length ? props.item.image_keys : props.item.image_key ? [props.item.image_key] : []).slice(0, 4));

const isWatched = computed(() => props.item.watch_mark === "watched");
const isWant = computed(() => props.item.watch_mark === "want");

// video 版权徽章四态
const videoBadge = computed(() => {
  if (!props.item.rights_confirmed) return { text: "审核中", variant: "warn" as const };
  if (props.item.embed_status === "blocked") return { text: "去原站看", variant: "warn" as const };
  if (props.item.canonical_url) return { text: "官方外链", variant: "link" as const };
  return { text: "原创已确认", variant: "good" as const };
});
</script>

<template>
  <!-- 剧集：集号方块 + 进度 -->
  <article v-if="roomType === 'series'" class="entry entry--episode" :class="{ watched: isWatched }">
    <div class="episode-box" :class="{ watched: isWatched }" aria-hidden="true">
      <BaseIcon v-if="isWatched" name="i-check" :size="18" class="check" />
      <span v-else>{{ item.episode }}</span>
    </div>
    <div class="entry-body">
      <h3 class="entry-title" data-ugc>{{ item.title }}</h3>
      <p class="entry-meta">{{ episodeLabel }}<span v-if="item.summary" data-ugc> · {{ item.summary }}</span></p>
      <div v-if="item.progress != null" class="progress-row">
        <div class="progress-bar"><span :style="{ width: `${item.progress}%` }"></span></div>
        <span class="progress-pct">{{ item.progress }}%</span>
      </div>
      <EntryMedia :images="images" :video-key="item.video_key" :title="item.title" :content-id="item.content_id" :embed-status="item.type === 'embed' ? item.embed_status : null" :source-url="item.canonical_url" :provider="item.embed_provider_code" />
      <div class="entry-compliance">
        <SourceBlock :source-name="item.source_name" :licence-ref="item.licence_ref" :canonical-url="item.canonical_url" :label="`${item.title} 的来源与许可`" />
        <ReportButton kind="content" :id="item.content_id" compact />
      </div>
    </div>
    <div class="entry-actions">
      <button v-if="!isWatched" type="button" class="btn btn--ghost btn--sm" @click="emit('watched')">看过</button>
      <button type="button" class="icon-btn" :aria-pressed="isWant" :title="isWant ? '取消想看' : '想看'" @click="emit('toggle-watch', 'want')"><BaseIcon name="i-heart" :size="20" /></button>
    </div>
  </article>

  <!-- 电影：片单卡（封面图 + 衬线标题）；没有封面时用片名首字 -->
  <article v-else-if="roomType === 'film'" class="entry entry--film">
    <div class="film-cover">
      <img v-if="images[0]" :src="`/api/v1/uploads/${images[0]}`" :alt="`${item.title} 封面`" loading="lazy" />
      <span v-else aria-hidden="true">{{ item.title.slice(0, 1) }}</span>
    </div>
    <div class="entry-body">
      <h3 class="entry-title entry-title--serif" data-ugc>{{ item.title }}</h3>
      <p v-if="item.summary" class="entry-meta" data-ugc>{{ item.summary }}</p>
      <EntryMedia :images="images.slice(1)" :video-key="item.video_key" :title="item.title" :content-id="item.content_id" :embed-status="item.type === 'embed' ? item.embed_status : null" :source-url="item.canonical_url" :provider="item.embed_provider_code" />
      <div class="entry-actions">
        <button type="button" class="icon-btn" :aria-pressed="isWant" :title="isWant ? '取消想看' : '想看'" @click="emit('toggle-watch', 'want')"><BaseIcon name="i-heart" :size="20" /></button>
        <button v-if="!isWatched" type="button" class="btn btn--ghost btn--sm" @click="emit('watched')">看过</button>
        <BaseTag v-else variant="good">看过</BaseTag>
      </div>
      <div class="entry-compliance">
        <SourceBlock :source-name="item.source_name" :licence-ref="item.licence_ref" :canonical-url="item.canonical_url" :label="`${item.title} 的来源与许可`" />
        <ReportButton kind="content" :id="item.content_id" compact />
      </div>
    </div>
    <div v-if="isOwner" class="entry-reorder">
      <button type="button" class="icon-btn" title="上移" @click="emit('reorder', 'up')"><BaseIcon name="i-up" :size="18" /></button>
      <button type="button" class="icon-btn" title="下移" @click="emit('reorder', 'down')"><BaseIcon name="i-down" :size="18" /></button>
    </div>
  </article>

  <!-- 视频：官方外链走 §7.3 同意面板；原创视频走缩略卡 -->
  <div v-else-if="roomType === 'video'" class="video-row">
    <EmbedConsentCard
      v-if="item.type === 'embed'"
      class="video-embed"
      :content-id="item.content_id"
      :title="item.title"
      :embed-status="item.embed_status"
      :source-url="item.canonical_url"
      :display-name="item.source_name"
    />
    <article v-else class="entry entry--video">
      <!-- 有上传的视频就直接播放（第一张图作海报），没有才显示缩略图 -->
      <div v-if="!item.video_key" class="video-thumb" aria-hidden="true">
        <img v-if="item.image_key" :src="`/api/v1/uploads/${item.image_key}`" :alt="item.title" />
        <BaseIcon v-else name="i-play" :size="26" class="video-thumb-fallback" />
      </div>
      <div class="entry-body">
        <h3 class="entry-title" data-ugc>{{ item.title }}</h3>
        <BaseTag :variant="videoBadge.variant">{{ videoBadge.text }}</BaseTag>
        <p v-if="item.summary" class="entry-meta" data-ugc>{{ item.summary }}</p>
        <EntryMedia
          :images="item.video_key ? images.slice(1) : []"
          :video-key="item.video_key"
          :poster="images[0]"
          :title="item.title"
        />
        <a v-if="item.canonical_url" :href="item.canonical_url" target="_blank" rel="noopener" class="entry-link">去原站看</a>
        <div class="entry-compliance">
          <SourceBlock :source-name="item.source_name" :licence-ref="item.licence_ref" :canonical-url="item.canonical_url" :label="`${item.title} 的来源与许可`" />
          <ReportButton kind="content" :id="item.content_id" compact />
        </div>
      </div>
    </article>
    <div v-if="isOwner" class="entry-reorder">
      <button type="button" class="icon-btn" title="上移" @click="emit('reorder', 'up')"><BaseIcon name="i-up" :size="18" /></button>
      <button type="button" class="icon-btn" title="下移" @click="emit('reorder', 'down')"><BaseIcon name="i-down" :size="18" /></button>
    </div>
  </div>

  <!-- 通用：帖子卡 -->
  <article v-else class="entry entry--general">
    <div class="entry-body">
      <h3 class="entry-title" data-ugc>{{ item.title }}</h3>
      <p v-if="item.summary" class="entry-meta" data-ugc>{{ item.summary }}</p>
      <EntryMedia :images="images" :video-key="item.video_key" :title="item.title" :content-id="item.content_id" :embed-status="item.type === 'embed' ? item.embed_status : null" :source-url="item.canonical_url" :provider="item.embed_provider_code" />
      <div class="entry-meta-row">
        <span v-if="item.author_name || item.author_handle" data-ugc>{{ item.author_name || item.author_handle }}</span>
        <span v-if="item.comment_count > 0">{{ item.comment_count }} 条留言</span>
        <BaseTag v-if="item.status === 'pending'" variant="warn">审核中</BaseTag>
      </div>
      <div class="entry-compliance">
        <SourceBlock :source-name="item.source_name" :licence-ref="item.licence_ref" :canonical-url="item.canonical_url" :label="`${item.title} 的来源与许可`" />
        <ReportButton kind="content" :id="item.content_id" compact />
      </div>
    </div>
  </article>
</template>

<style scoped>
.entry {
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
}
.video-row {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-start;
}
.video-row > .entry,
.video-embed {
  flex: 1;
  min-width: 0;
}
.entry--episode.watched {
  opacity: 0.72;
}
.episode-box {
  flex: 0 0 46px;
  width: 46px;
  height: 46px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: var(--surface2);
  font-weight: 700;
  font-size: var(--fs-14);
}
.episode-box.watched {
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.check {
  font-size: var(--fs-16);
}
.entry-body {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: var(--sp-1);
}
.entry-title {
  margin: 0;
  font-size: var(--fs-15);
  font-weight: 600;
  overflow-wrap: anywhere;
}
.entry-title--serif {
  font-family: var(--font-serif);
  font-size: var(--fs-16);
  letter-spacing: 0.5px;
}
.entry-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
.entry-compliance {
  display: grid;
  gap: var(--sp-1);
  margin-top: var(--sp-1);
}
.entry-meta-row {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
  color: var(--muted);
  font-size: var(--fs-12);
}
.entry-actions {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex: 0 0 auto;
}
.entry-reorder {
  display: flex;
  flex-direction: column;
  gap: var(--sp-1);
  flex: 0 0 auto;
}
.progress-row {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
}
.progress-bar {
  flex: 1;
  height: 6px;
  border-radius: var(--r-pill);
  background: var(--surface2);
  overflow: hidden;
}
.progress-bar span {
  display: block;
  height: 100%;
  background: var(--accent);
  border-radius: var(--r-pill);
}
.progress-pct {
  font-size: var(--fs-12);
  color: var(--muted);
}
.film-cover {
  flex: 0 0 56px;
  width: 56px;
  height: 76px;
  display: grid;
  place-items: center;
  border-radius: var(--r-md);
  background: var(--surface2);
  font-family: var(--font-serif);
  font-size: 28px;
  color: var(--accent-ink);
  overflow: hidden;
}
.film-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-thumb {
  flex: 0 0 96px;
  width: 96px;
  height: 60px;
  border-radius: 10px;
  overflow: hidden;
  background: var(--surface2);
  display: grid;
  place-items: center;
}
.video-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.video-thumb-fallback {
  color: var(--muted);
  font-size: 20px;
}
.entry-link {
  font-size: var(--fs-13);
}
.icon-btn {
  min-width: 44px;
  min-height: 44px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--text);
  cursor: pointer;
}
.icon-btn[aria-pressed="true"] {
  color: var(--accent-ink);
  background: var(--accent-soft);
}
</style>
