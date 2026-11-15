<script setup lang="ts">
// 房间条目的图片（最多 4 张）和视频，各种房间类型共用。
defineProps<{ images: string[]; videoKey?: string | null; title: string; poster?: string | null }>();
</script>

<template>
  <div v-if="images.length" class="entry-media" :class="`entry-media--n${images.length}`">
    <img v-for="(key, i) in images" :key="key" :src="`/api/v1/uploads/${key}`" :alt="`${title} 图片 ${i + 1}`" loading="lazy" />
  </div>
  <video
    v-if="videoKey"
    class="entry-video"
    :src="`/api/v1/uploads/${videoKey}`"
    :poster="poster ? `/api/v1/uploads/${poster}` : undefined"
    controls
    playsinline
    preload="metadata"
    :aria-label="`${title} 视频`"
  ></video>
</template>

<style scoped>
.entry-media {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 4px;
  margin-top: var(--sp-2);
  border-radius: var(--r-md);
  overflow: hidden;
}
.entry-media--n1 {
  grid-template-columns: 1fr;
}
.entry-media img {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  display: block;
  background: var(--accent-soft);
}
.entry-media--n1 img {
  aspect-ratio: auto;
  max-height: 420px;
}
.entry-video {
  width: 100%;
  max-height: 420px;
  margin-top: var(--sp-2);
  border-radius: var(--r-md);
  background: #000;
}
</style>
