<script setup lang="ts">
// TextField：高 44px 文本输入，label/错误/禁用三态，对齐 MASTER §5.1。
withDefaults(
  defineProps<{
    modelValue: string;
    label: string;
    id: string;
    type?: string;
    placeholder?: string;
    autocomplete?: string;
    error?: string;
    hint?: string;
    disabled?: boolean;
    required?: boolean;
    maxlength?: number;
  }>(),
  {
    type: "text",
    placeholder: "",
    autocomplete: undefined,
    error: "",
    hint: "",
    disabled: false,
    required: false,
  },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();
</script>

<template>
  <div class="field">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      class="input"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :disabled="disabled"
      :required="required"
      :maxlength="maxlength"
      :aria-invalid="error ? 'true' : undefined"
      :aria-describedby="hint ? `${id}-hint` : undefined"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="hint" :id="`${id}-hint`" class="sr-only">{{ hint }}</p>
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
