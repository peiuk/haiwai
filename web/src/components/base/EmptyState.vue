<script setup lang="ts">
// EmptyState：空状态，必须给下一步动作，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    title: string;
    description?: string;
    actionLabel?: string;
  }>(),
  { description: "", actionLabel: "" },
);

const emit = defineEmits<{ (e: "action"): void }>();
</script>

<template>
  <div class="empty">
    <p>{{ title }}</p>
    <p v-if="description" class="empty__desc">{{ description }}</p>
    <slot name="extra" />
    <button v-if="actionLabel" class="btn btn--outline" type="button" @click="emit('action')">
      {{ actionLabel }}
    </button>
  </div>
</template>

<style scoped>
.empty {
  display: grid;
  gap: var(--sp-3);
  justify-items: center;
}
.empty__desc { margin: 0; font-size: 13px; color: var(--muted); text-align: center; }
</style>
