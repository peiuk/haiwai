<script setup lang="ts">
// Toast：底部居中 pill 提示，接入全局 toast store，对齐 MASTER §5.1。
import { storeToRefs } from "pinia";
import { useToastStore } from "../../stores/toast";

const store = useToastStore();
const { text } = storeToRefs(store);
</script>

<template>
  <div v-if="text" class="toast show" role="status" aria-live="polite">{{ text }}</div>
</template>
