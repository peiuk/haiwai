<script setup lang="ts">
// 正文里的 #话题 显示成蓝色、可点（进搜索「#话题」），其余文字原样；切分规则见 utils/post.ts splitHashTags。
import { computed } from "vue";
import { RouterLink } from "vue-router";
import { splitHashTags } from "../../utils/post";

const props = defineProps<{ text: string }>();
const emit = defineEmits<{ (e: "pick"): void }>();
const parts = computed(() => splitHashTags(props.text));
</script>

<template><template v-for="(part, i) in parts" :key="i"><RouterLink v-if="part.tag" class="hash-tag" :to="{ name: 'search', query: { q: `#${part.tag}` } }" @click.stop="emit('pick')">{{ part.text }}</RouterLink><template v-else>{{ part.text }}</template></template></template>

<style scoped>
.hash-tag {
  color: var(--accent-ink);
  text-decoration: none;
}
.hash-tag:hover,
.hash-tag:focus-visible {
  text-decoration: underline;
}
</style>
