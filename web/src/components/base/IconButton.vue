<script setup lang="ts">
// IconButton：44×44 圆形图标按钮，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    label: string;
    pressed?: boolean;
    disabled?: boolean;
  }>(),
  {
    pressed: false,
    disabled: false,
  },
);

const emit = defineEmits<{ (e: "click", ev: MouseEvent): void }>();
</script>

<template>
  <button
    type="button"
    class="icon-btn"
    :aria-label="label"
    :aria-pressed="pressed === false ? undefined : pressed"
    :disabled="disabled"
    @click="emit('click', $event)"
  >
    <slot />
  </button>
</template>
