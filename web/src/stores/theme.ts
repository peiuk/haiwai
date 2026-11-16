// 主题与语言 store：data-theme（light/dark）与 lang（zh-Hans/zh-Hant）双独立维度。
// 依据 MASTER §7.6：两者互不耦合，切换后持久化（localStorage）并可撤回。
import { defineStore } from "pinia";
import { ref, watch } from "vue";

const THEME_KEY = "ukcn.theme";
const LANG_KEY = "ukcn.lang";

export type ThemeMode = "light" | "dark";
export type LangCode = "zh-Hans" | "zh-Hant";

function readTheme(): ThemeMode {
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === "dark" || saved === "light") return saved;
  // 没手动选过：跟手机 / 电脑的深色模式走，不然深色手机上一打开是一片白
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function readLang(): LangCode {
  const saved = localStorage.getItem(LANG_KEY);
  return saved === "zh-Hant" ? "zh-Hant" : "zh-Hans";
}

export const useThemeStore = defineStore("theme", () => {
  const theme = ref<ThemeMode>(readTheme());
  const lang = ref<LangCode>(readLang());

  function apply(): void {
    document.documentElement.setAttribute("data-theme", theme.value);
    document.documentElement.setAttribute("lang", lang.value);
  }

  function setTheme(value: ThemeMode): void {
    theme.value = value;
    localStorage.setItem(THEME_KEY, value);
  }

  function setLang(value: LangCode): void {
    lang.value = value;
    localStorage.setItem(LANG_KEY, value);
  }

  function toggleTheme(): void {
    setTheme(theme.value === "dark" ? "light" : "dark");
  }

  // 初始化时立即应用到 <html>；之后每次切换同步写回 data-theme / lang。
  // 两个维度只由各自 setter 修改，watch 只负责落 DOM，互不耦合（§7.6）。
  apply();
  watch([theme, lang], apply, { flush: "post" });

  return { theme, lang, apply, setTheme, setLang, toggleTheme };
});
