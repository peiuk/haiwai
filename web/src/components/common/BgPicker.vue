<script setup lang="ts">
// 彩色背景选择（Facebook 式色块）：第一个是「无背景」，后面 8 个预设。
// disabled 时（字太多 / 带了图片视频）色块变灰、点不了，并说明为什么。
import { BG_MAX_LEN, BG_PRESETS } from "../../utils/postBg";
import BaseIcon from "../base/BaseIcon.vue";

defineProps<{ modelValue: string; disabled?: boolean }>();
const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();
</script>

<template>
  <div class="bg-picker">
    <div class="bg-swatches" role="radiogroup" aria-label="背景颜色">
      <button
        type="button"
        role="radio"
        class="bg-swatch bg-swatch--none"
        :aria-checked="!modelValue"
        aria-label="无背景"
        title="无背景"
        @click="emit('update:modelValue', '')"
      >
        <BaseIcon name="i-close" :size="14" />
      </button>
      <button
        v-for="preset in BG_PRESETS"
        :key="preset.key"
        type="button"
        role="radio"
        class="bg-swatch"
        :style="{ background: preset.background }"
        :aria-checked="modelValue === preset.key"
        :aria-label="`${preset.label}背景`"
        :title="preset.label"
        :disabled="disabled"
        @click="emit('update:modelValue', preset.key)"
      ></button>
    </div>
    <p v-if="disabled && modelValue" class="bg-hint">超过 {{ BG_MAX_LEN }} 字或带了图片、视频，这条不用背景</p>
  </div>
</template>

<style scoped>
.bg-picker {
  display: grid;
  gap: 4px;
}
.bg-swatches {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.bg-swatch {
  width: 32px;
  height: 32px;
  padding: 0;
  border: 2px solid transparent;
  border-radius: var(--r-md);
  box-shadow: inset 0 0 0 1px rgb(0 0 0 / 0.12);
  cursor: pointer;
}
.bg-swatch--none {
  display: grid;
  place-items: center;
  background: var(--surface2);
  color: var(--muted);
}
.bg-swatch[aria-checked="true"] {
  border-color: var(--text);
  outline: 2px solid var(--bg);
  outline-offset: -4px;
}
.bg-swatch:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.bg-swatch:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.bg-hint {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
</style>
