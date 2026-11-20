<script setup lang="ts">
// 分类信息多图上传：逐个走 /uploads/sign → PUT → object_key，最终只把 key 数组交给表单。
// 上限与后端 MAX_LISTING_IMAGES 对齐（6 张）；单图接口由 UploadField 负责。
import { computed, ref } from "vue";
import { toMessage, uploadFile } from "../../api";
import { useToastStore } from "../../stores/toast";
import BaseIcon from "../base/BaseIcon.vue";
import Progress from "../base/Progress.vue";

const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    modelValue: string[];
    accept: string;
    maxMb: number;
    max?: number;
    hint?: string;
    disabled?: boolean;
  }>(),
  { max: 6, hint: "", disabled: false },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string[]): void }>();
const toast = useToastStore();

const busy = ref(false);
const error = ref("");
const names = ref<string[]>([]);
const progress = ref(0);
const step = ref("");
// 这次刚传上的图，缩略图上闪一下对勾（编辑时原有的图不闪）
const justAdded = ref(new Set<string>());

const EXT_TYPE: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
};

const remaining = computed(() => Math.max(0, props.max - props.modelValue.length));
const atLimit = computed(() => remaining.value === 0);

function resolveType(file: File): string {
  if (file.type) return file.type;
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TYPE[ext] ?? "";
}

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const picked = Array.from(input.files ?? []);
  if (picked.length === 0) return;
  error.value = "";
  if (picked.length > remaining.value) {
    error.value = `最多还能选 ${remaining.value} 张（共 ${props.max} 张）`;
    input.value = "";
    return;
  }
  const allowed = props.accept.split(",").map((item) => item.trim());
  for (const file of picked) {
    const contentType = resolveType(file);
    if (!allowed.includes(contentType) || file.size === 0 || file.size > props.maxMb * 1_000_000) {
      error.value = `只接受 jpeg / png / webp，单张不超过 ${props.maxMb}MB`;
      input.value = "";
      return;
    }
  }
  busy.value = true;
  try {
    const keys: string[] = [];
    const added: string[] = [];
    for (const [i, file] of picked.entries()) {
      step.value = `${i + 1}/${picked.length}`;
      progress.value = 0;
      const key = await uploadFile(file, resolveType(file), (p) => (progress.value = p));
      keys.push(key);
      added.push(file.name);
      justAdded.value.add(key);
    }
    emit("update:modelValue", [...props.modelValue, ...keys].slice(0, props.max));
    names.value = [...names.value, ...added].slice(0, props.max);
    toast.show(`已上传 ${keys.length} 张图片，提交发布后才会公开`);
  } catch (err) {
    error.value = toMessage(err);
    toast.show(error.value);
  } finally {
    busy.value = false;
    input.value = "";
  }
}

function remove(index: number): void {
  emit(
    "update:modelValue",
    props.modelValue.filter((_, i) => i !== index),
  );
  names.value = names.value.filter((_, i) => i !== index);
  error.value = "";
}
</script>

<template>
  <div class="multi-upload">
    <p class="mu-label"><span>{{ label }}</span><span class="mu-count">{{ modelValue.length }}/{{ max }}</span></p>
    <ul class="mu-grid">
      <li v-for="(key, index) in modelValue" :key="key" class="mu-tile">
        <img :src="`/api/v1/uploads/${key}`" :alt="`第 ${index + 1} 张图片预览`" :title="names[index] || undefined" loading="lazy" />
        <span v-if="index === 0 && max > 1" class="mu-cover">封面</span>
        <span v-if="justAdded.has(key)" class="mu-done" aria-hidden="true"><BaseIcon name="i-check" :size="16" /></span>
        <button type="button" class="mu-remove" :disabled="disabled" :aria-label="`移除第 ${index + 1} 张图片`" @click="remove(index)">
          <BaseIcon name="i-close" :size="14" />
        </button>
      </li>
      <li v-if="busy" class="mu-tile mu-busy" aria-live="polite">
        <BaseIcon name="i-image" :size="22" />
        <span>{{ progress >= 100 ? "处理中…" : `上传中 ${progress}%` }}</span>
        <Progress class="mu-bar" :value="progress" :pending="progress >= 100" :label="`第 ${step} 张上传进度`" />
        <span class="mu-step">第 {{ step }} 张</span>
      </li>
      <li v-else-if="!atLimit">
        <!-- 真正的 input 藏起来但仍可 Tab 聚焦，点整块虚线框就是选图 -->
        <input :id="id" class="mu-input" type="file" multiple :accept="accept" :disabled="disabled" @change="onFile" />
        <label :for="id" class="mu-tile mu-add" :class="{ 'is-disabled': disabled }">
          <span class="mu-add-icon"><BaseIcon name="i-plus" :size="20" /></span>
          <span class="mu-add-text">添加图片</span>
          <span class="mu-add-sub">还能加 {{ remaining }} 张</span>
        </label>
      </li>
    </ul>
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.multi-upload {
  display: grid;
  gap: var(--sp-2);
}
.mu-label {
  margin: 0;
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: var(--sp-2);
  font-size: var(--fs-13);
  font-weight: 600;
}
.mu-count {
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 400;
  font-variant-numeric: tabular-nums;
}
.mu-grid {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(96px, 1fr));
  gap: var(--sp-2);
}
.mu-tile {
  position: relative;
  display: grid;
  place-items: center;
  aspect-ratio: 1;
  border-radius: var(--r-md);
  overflow: hidden;
  background: var(--surface2);
}
.mu-tile img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border: 1px solid var(--border);
  border-radius: inherit;
}
.mu-cover {
  position: absolute;
  left: 6px;
  bottom: 6px;
  padding: 1px 8px;
  border-radius: var(--r-pill);
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  font-size: var(--fs-11);
}
.mu-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  cursor: pointer;
  transition: background 0.15s;
}
.mu-remove:hover {
  background: rgba(0, 0, 0, 0.8);
}
.mu-remove:focus-visible {
  outline: 2px solid #fff;
  outline-offset: -4px;
}
.mu-busy {
  align-content: center;
  gap: 4px;
  padding: 0 10px;
  border: 1px dashed var(--line);
  color: var(--muted);
  font-size: var(--fs-12);
  font-variant-numeric: tabular-nums;
}
.mu-bar {
  width: 100%;
}
.mu-step {
  font-size: var(--fs-11);
}
/* 刚传完的图：对勾弹出来，1.5 秒后淡掉 */
.mu-done {
  position: absolute;
  inset: 0;
  margin: auto;
  display: grid;
  place-items: center;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--on-accent, #fff);
  pointer-events: none;
  animation: mu-done 1.8s var(--ease-out, ease-out) forwards;
}
@keyframes mu-done {
  0% { transform: scale(0); opacity: 1; }
  15% { transform: scale(1.2); }
  25%, 75% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1); opacity: 0; }
}
@media (prefers-reduced-motion: reduce) {
  .mu-done { animation: none; opacity: 0; }
}
.mu-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
}
.mu-add {
  align-content: center;
  gap: 2px;
  border: 1.5px dashed var(--line);
  background: transparent;
  color: var(--muted);
  cursor: pointer;
  transition: border-color 0.15s, background 0.15s, color 0.15s;
}
.mu-add:hover,
.mu-input:focus-visible + .mu-add {
  border-color: var(--accent);
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.mu-input:focus-visible + .mu-add {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
.mu-add.is-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mu-add-icon {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin-bottom: 4px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.mu-add-text {
  font-size: var(--fs-13);
  font-weight: 600;
}
.mu-add-sub {
  font-size: var(--fs-11);
}
.field-hint,
.field-error {
  margin: 0;
  font-size: var(--fs-12);
}
.field-hint {
  color: var(--muted);
}
.field-error {
  color: var(--danger);
}
</style>
