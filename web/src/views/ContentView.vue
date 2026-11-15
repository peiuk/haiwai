<script setup lang="ts">
// 内容详情独立页（/content/:id）：复用 ContentDetail 组件的加载 / 互动 / 回复逻辑，
// 提供可分享、可收藏、可被搜索结果 / 通知 / 帖子卡链接到的固定 URL。
import { computed } from "vue";
import { useRoute } from "vue-router";
import ContentDetail from "../components/ContentDetail.vue";

const route = useRoute();
const contentId = computed(() => (typeof route.params.id === "string" ? route.params.id : ""));
</script>

<template>
  <section class="content-view">
    <ContentDetail :content-id="contentId" standalone />
  </section>
</template>

<style scoped>
.content-view {
  max-width: 720px;
  margin: 0 auto;
}
/* 手机上应用顶栏已隐藏，抵掉主栏顶部留白，让详情顶栏贴顶 */
@media (max-width: 759px) {
  .content-view { margin-top: calc(-1 * var(--sp-4)); }
}
</style>
