<script setup lang="ts">
// Checkbox：20×20，label 可点击，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    modelValue: boolean;
    label: string;
    id: string;
    disabled?: boolean;
  }>(),
  {
    disabled: false,
  },
);

const emit = defineEmits<{ (e: "update:modelValue", value: boolean): void }>();
</script>

<template>
  <label class="check" :for="id">
    <input
      :id="id"
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="emit('update:modelValue', ($event.target as HTMLInputElement).checked)"
    />
    <span>{{ label }}</span>
  </label>
</template>
