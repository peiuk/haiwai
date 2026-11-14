// 全局 toast store：替代散落的 notice 一次性提示，统一走 tokens.css 的 .toast。
import { defineStore } from "pinia";
import { ref } from "vue";

let timer: ReturnType<typeof setTimeout> | null = null;

export const useToastStore = defineStore("toast", () => {
  const text = ref("");

  function show(message: string, duration = 2600): void {
    text.value = message;
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(() => {
      text.value = "";
    }, duration);
  }

  function clear(): void {
    text.value = "";
    if (timer) {
      clearTimeout(timer);
      timer = null;
    }
  }

  return { text, show, clear };
});
