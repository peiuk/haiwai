<script setup lang="ts">
// SelectField：下拉选择，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    modelValue: string;
    label: string;
    id: string;
    options: { value: string; label: string }[];
    placeholder?: string;
    error?: string;
    disabled?: boolean;
  }>(),
  {
    placeholder: "请选择",
    error: "",
    disabled: false,
  },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();
</script>

<template>
  <div class="field">
    <label :for="id">{{ label }}</label>
    <select
      :id="id"
      class="input"
      :value="modelValue"
      :disabled="disabled"
      :aria-invalid="error ? 'true' : undefined"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option value="" disabled>{{ placeholder }}</option>
      <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
    <p v-if="error" role="alert" class="field-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.field-error {
  margin: var(--sp-1) 0 0;
  font-size: var(--fs-12);
  color: var(--danger);
}
</style>
