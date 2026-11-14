<script setup lang="ts">
// 矢量图标：引用 App.vue 全局挂载的 IconSprite。复刻原型 .ico 的描边规范。
// label 为空时图标为纯装饰（aria-hidden）；有 label 时作为独立 img 角色可读。
import { computed } from "vue";

const props = withDefaults(
  defineProps<{
    name: string;
    size?: number | string;
    label?: string;
    rotate?: number;
  }>(),
  { size: 20, label: "", rotate: 0 },
);

const box = computed(() => (typeof props.size === "number" ? `${props.size}px` : props.size));
const transform = computed(() => (props.rotate ? `rotate(${props.rotate}deg)` : undefined));
</script>

<template>
  <svg
    class="base-icon"
    :style="{ width: box, height: box, transform }"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    :role="label ? 'img' : undefined"
    :aria-label="label || undefined"
    :aria-hidden="label ? undefined : 'true'"
    focusable="false"
  >
    <use :href="`#${name}`" />
  </svg>
</template>

<style scoped>
.base-icon {
  display: block;
  flex-shrink: 0;
}
</style>
