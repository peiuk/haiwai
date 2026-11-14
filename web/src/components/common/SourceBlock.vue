<script setup lang="ts">
// 来源与许可块（MASTER §7.1）：来源名 / 许可徽章 / 原文回链必显，默认不折叠。
// 多源事件给出可展开的来源列表；每条链接都 target=_blank rel=noopener。
import { computed } from "vue";
import BaseTag from "../base/BaseTag.vue";

export type SourceEntry = {
  canonical_url: string;
  title: string;
  source_name?: string | null;
};

const props = withDefaults(
  defineProps<{
    sourceName?: string | null;
    licenceRef?: string | null;
    canonicalUrl?: string | null;
    sources?: SourceEntry[];
    label?: string;
  }>(),
  { sourceName: "", licenceRef: "", canonicalUrl: "", sources: () => [], label: "来源与许可" },
);

const name = computed(() => props.sourceName?.trim() || "用户投稿");
const licence = computed(() => props.licenceRef?.trim() || "UGC");
const multi = computed(() => props.sources?.filter((item) => item.canonical_url) ?? []);
</script>

<template>
  <div class="source-block" role="group" :aria-label="label">
    <span class="source-name">来源：{{ name }}</span>
    <BaseTag variant="link">{{ licence }}</BaseTag>
    <a
      v-if="canonicalUrl"
      class="source-link"
      :href="canonicalUrl"
      target="_blank"
      rel="noopener"
    >原文 ↗</a>
    <span v-else class="source-origin">原创内容</span>

    <details v-if="multi.length > 1">
      <summary>{{ multi.length }} 个来源</summary>
      <ul>
        <li v-for="source in multi" :key="source.canonical_url">
          <a :href="source.canonical_url" target="_blank" rel="noopener">
            {{ source.title || source.source_name || source.canonical_url }}
          </a>
        </li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.source-block {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--sp-2);
  padding: var(--sp-2) 0;
  border-top: 1px solid var(--border);
  font-size: var(--fs-12);
}
.source-name {
  font-weight: 600;
}
.source-link,
.source-origin {
  font-size: var(--fs-12);
}
.source-origin {
  color: var(--muted);
}
details {
  flex-basis: 100%;
}
summary {
  min-height: var(--tap);
  display: flex;
  align-items: center;
  cursor: pointer;
  color: var(--accent-ink);
}
ul {
  margin: 0;
  padding-left: var(--sp-4);
  display: grid;
  gap: var(--sp-1);
}
a {
  overflow-wrap: anywhere;
}
</style>
