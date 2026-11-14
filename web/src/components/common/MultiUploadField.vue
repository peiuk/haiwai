<script setup lang="ts">
// 分类信息多图上传：逐个走 /uploads/sign → PUT → object_key，最终只把 key 数组交给表单。
// 上限与后端 MAX_LISTING_IMAGES 对齐（4 张）；单图接口由 UploadField 负责。
import { computed, ref } from "vue";
import { toMessage, uploadFile } from "../../api";
import { useToastStore } from "../../stores/toast";

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
  { max: 4, hint: "", disabled: false },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string[]): void }>();
const toast = useToastStore();

const busy = ref(false);
const error = ref("");
const names = ref<string[]>([]);

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
    for (const file of picked) {
      const key = await uploadFile(file, resolveType(file));
      keys.push(key);
      added.push(file.name);
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
    <label :for="id">{{ label }}（{{ modelValue.length }}/{{ max }}）</label>
    <input
      :id="id"
      class="input"
      type="file"
      multiple
      :accept="accept"
      :disabled="disabled || busy || atLimit"
      @change="onFile"
    />
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <p v-if="busy" class="field-status" aria-live="polite">上传中…</p>
    <p v-else-if="atLimit" class="field-status">已达上限，移除一张后可继续添加</p>
    <ul v-if="modelValue.length" class="thumb-list">
      <li v-for="(key, index) in modelValue" :key="key" class="thumb-item">
        <img class="thumb" :src="`/api/v1/uploads/${key}`" :alt="`第 ${index + 1} 张图片预览`" loading="lazy" />
        <span class="thumb-name" :title="names[index] || key">{{ names[index] || key.slice(0, 8) }}</span>
        <button type="button" class="remove-btn" :disabled="disabled" :aria-label="`移除第 ${index + 1} 张图片`" @click="remove(index)">
          移除
        </button>
      </li>
    </ul>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.multi-upload {
  display: grid;
  gap: var(--sp-1);
}
label {
  font-size: var(--fs-13);
  font-weight: 600;
}
.input {
  width: 100%;
  min-height: var(--tap);
  padding: var(--sp-2);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--bg);
  color: var(--text);
  font-size: var(--fs-13);
}
.field-hint,
.field-status,
.field-error {
  margin: 0;
  font-size: var(--fs-12);
}
.field-hint,
.field-status {
  color: var(--muted);
}
.field-error {
  color: var(--danger);
}
.thumb-list {
  list-style: none;
  margin: var(--sp-2) 0 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(112px, 1fr));
  gap: var(--sp-2);
}
.thumb-item {
  display: grid;
  gap: var(--sp-1);
  min-width: 0;
}
.thumb {
  width: 100%;
  aspect-ratio: 16 / 10;
  object-fit: cover;
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface2);
}
.thumb-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--muted);
  font-size: var(--fs-11);
}
.remove-btn {
  min-height: var(--tap);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-12);
  cursor: pointer;
}
</style>
