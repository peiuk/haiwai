<script setup lang="ts">
// ErrorState：错误态，红框 + 可恢复的「重试」，对齐 MASTER §5.1。
// retryLabel 传空 = 重试也没用（比如内容不存在），不显示按钮。
withDefaults(
  defineProps<{
    message: string;
    retryLabel?: string;
  }>(),
  { retryLabel: "重试" },
);

const emit = defineEmits<{ (e: "retry"): void }>();
</script>

<template>
  <div class="error-state" role="alert">
    <p>{{ message }}</p>
    <button v-if="retryLabel" class="btn btn--outline" type="button" @click="emit('retry')">{{ retryLabel }}</button>
  </div>
</template>

<style scoped>
.error-state {
  display: grid;
  gap: var(--sp-3);
  justify-items: center;
  padding: var(--sp-6) var(--sp-5);
  border: 1px solid var(--danger);
  border-radius: var(--r-lg);
  color: var(--danger);
  font-size: var(--fs-13);
}
.error-state p {
  margin: 0;
}
</style>
