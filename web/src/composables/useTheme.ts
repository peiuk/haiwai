// 主题/语言 composable：对 theme store 的轻量封装，便于组件内直接使用。
import { storeToRefs } from "pinia";
import { useThemeStore } from "../stores/theme";

export function useTheme() {
  const store = useThemeStore();
  const { theme, lang } = storeToRefs(store);

  return {
    theme,
    lang,
    isDark: () => theme.value === "dark",
    isHant: () => lang.value === "zh-Hant",
    setTheme: store.setTheme,
    setLang: store.setLang,
    toggleTheme: store.toggleTheme,
  };
}
