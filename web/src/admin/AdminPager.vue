<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ page: number; total: number; pageSize: number }>();
defineEmits<{ go: [page: number] }>();

const pages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)));
</script>

<template>
  <div class="adm-pager">
    <span>共 {{ total }} 条 · 第 {{ page }} / {{ pages }} 页</span>
    <button type="button" class="btn btn--outline btn--sm" :disabled="page <= 1" @click="$emit('go', page - 1)">上一页</button>
    <button type="button" class="btn btn--outline btn--sm" :disabled="page >= pages" @click="$emit('go', page + 1)">下一页</button>
  </div>
</template>
