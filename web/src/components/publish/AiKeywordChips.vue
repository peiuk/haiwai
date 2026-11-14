<script setup lang="ts">
// AI 关键词建议（MASTER §22.8）：≤5 个、可删、「AI 建议，可删」标签、aria-live 播报。
// 用户自己填了关键词后整个建议区立即消失；删掉的不再出现。
import { computed, ref, watch } from "vue";
import { useToastStore } from "../../stores/toast";
import { request, jsonBody, type KeywordResponse } from "../../api";

const props = defineProps<{
  title: string;
  body: string;
  category?: string | null;
  userKeywordCount: number;
}>();

const emit = defineEmits<{
  (e: "change", words: string[]): void;
}>();

const toast = useToastStore();

const suggestions = ref<string[]>([]);
const dismissed = ref<Set<string>>(new Set());
const loading = ref(false);
const generated = ref(false);

const visible = computed(() => props.userKeywordCount === 0);
const remaining = computed(() => suggestions.value.filter((word) => !dismissed.value.has(word)));

async function generate(): Promise<void> {
  if (!props.title.trim() && !props.body.trim()) {
    toast.show("先写标题或正文，再生成关键词");
    return;
  }
  loading.value = true;
  try {
    const result = await request<KeywordResponse>(
      "/api/v1/ai/keywords",
      jsonBody({ title: props.title, body: props.body, category: props.category ?? null }),
    );
    suggestions.value = result.keywords.slice(0, result.max ?? 5).filter((word) => word.length <= 12);
    dismissed.value = new Set();
    generated.value = true;
    emit("change", remaining.value);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "关键词生成失败");
  } finally {
    loading.value = false;
  }
}

function remove(word: string): void {
  const next = new Set(dismissed.value);
  next.add(word);
  dismissed.value = next;
  emit("change", remaining.value);
}

// 用户开始自己填关键词：清空采纳的 AI 建议
watch(
  () => props.userKeywordCount,
  (count) => {
    if (count > 0) emit("change", []);
  },
);
</script>

<template>
  <div v-if="visible" class="ai-keywords">
    <p class="sr-only" aria-live="polite">
      {{ generated ? `官方 AI 生成 ${remaining.length} 个关键词，可改可删` : "可以生成官方 AI 关键词建议" }}
    </p>

    <button v-if="!generated" type="button" class="ai-trigger" :disabled="loading" @click="generate">
      {{ loading ? "生成中…" : "AI 建议，可删 · 生成关键词" }}
    </button>

    <template v-else-if="remaining.length > 0">
      <span class="ai-label">AI 建议，可删</span>
      <ul class="ai-chips">
        <li v-for="word in remaining" :key="word" class="ai-chip">
          <span class="ai-badge">AI</span>
          <span>{{ word }}</span>
          <button
            type="button"
            class="ai-chip-remove"
            :aria-label="`删除关键词 ${word}`"
            @click="remove(word)"
          >
            ×
          </button>
        </li>
      </ul>
    </template>
    <p v-else class="ai-empty">AI 建议已全部删除，可以自己填写关键词。</p>
  </div>
</template>

<style scoped>
.ai-keywords {
  display: grid;
  gap: var(--sp-2);
}
.ai-trigger,
.ai-label {
  font-size: var(--fs-12);
  color: var(--muted);
}
.ai-trigger {
  min-height: 44px;
  justify-self: start;
  padding: 0 var(--sp-2);
  border: 1px dashed var(--accent);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--accent-ink);
  cursor: pointer;
}
.ai-trigger:disabled {
  opacity: 0.6;
  cursor: default;
}
.ai-chips {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
  list-style: none;
  margin: 0;
  padding: 0;
}
.ai-chip {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
  min-height: 44px;
  padding: 0 var(--sp-2);
  border: 1px dashed var(--accent);
  border-radius: var(--r-pill);
  font-size: var(--fs-13);
}
.ai-badge {
  font-size: 10px;
  font-weight: 700;
  color: var(--accent-ink);
}
.ai-chip-remove {
  min-width: 44px;
  min-height: 44px;
  border: 0;
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-16);
  cursor: pointer;
}
.ai-empty {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
</style>
