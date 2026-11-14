<script setup lang="ts">
// 通用媒体上传：POST /uploads/sign 申请名额 → PUT 原文件 → 得到 object_key。
// 前端只提交 object_key（视频帖 video_key / 分类信息 image_key / 私信 image_key），
// 文件直传由后端按白名单 MIME 与大小限制校验。
import { ref } from "vue";
import { uploadFile } from "../../api";
import { useToastStore } from "../../stores/toast";

const props = withDefaults(
  defineProps<{
    id: string;
    label: string;
    modelValue: string;
    accept: string;
    maxMb: number;
    hint?: string;
    disabled?: boolean;
  }>(),
  { hint: "", disabled: false },
);

const emit = defineEmits<{ (e: "update:modelValue", value: string): void }>();
const toast = useToastStore();

const busy = ref(false);
const error = ref("");
const fileName = ref("");

const EXT_TYPE: Record<string, string> = {
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  png: "image/png",
  webp: "image/webp",
  mp4: "video/mp4",
  webm: "video/webm",
  mov: "video/quicktime",
};

function resolveType(file: File): string {
  if (file.type) return file.type;
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  return EXT_TYPE[ext] ?? "";
}

async function onFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  error.value = "";
  const allowed = props.accept.split(",").map((item) => item.trim());
  const contentType = resolveType(file);
  if (!allowed.includes(contentType)) {
    error.value = "这个文件类型不在允许范围内";
    input.value = "";
    return;
  }
  if (file.size === 0 || file.size > props.maxMb * 1_000_000) {
    error.value = `文件不能为空，且不能超过 ${props.maxMb}MB`;
    input.value = "";
    return;
  }
  busy.value = true;
  try {
    const key = await uploadFile(file, contentType);
    fileName.value = file.name;
    emit("update:modelValue", key);
    toast.show("文件已上传，提交后才会公开");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "上传没有成功";
    input.value = "";
  } finally {
    busy.value = false;
  }
}

function clear(): void {
  emit("update:modelValue", "");
  fileName.value = "";
  error.value = "";
}
</script>

<template>
  <div class="upload-field">
    <label :for="id">{{ label }}</label>
    <input
      :id="id"
      class="input"
      type="file"
      :accept="accept"
      :disabled="disabled || busy"
      @change="onFile"
    />
    <p v-if="hint" class="field-hint">{{ hint }}</p>
    <p v-if="busy" class="field-status" aria-live="polite">上传中…</p>
    <p v-else-if="modelValue" class="field-status" aria-live="polite">
      已上传：{{ fileName || modelValue }}
      <button type="button" class="clear-btn" :disabled="disabled" @click="clear">移除</button>
    </p>
    <p v-if="error" class="field-error" role="alert">{{ error }}</p>
  </div>
</template>

<style scoped>
.upload-field {
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
.clear-btn {
  min-height: var(--tap);
  margin-left: var(--sp-2);
  padding: 0 var(--sp-2);
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-12);
  cursor: pointer;
}
</style>
