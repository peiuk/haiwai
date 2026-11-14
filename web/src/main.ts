import { createApp } from "vue";
import { createPinia } from "pinia";
import "../../design-system/tokens.css";
import App from "./App.vue";
import { router } from "./router";
import { useThemeStore } from "./stores/theme";
import { startUiLang } from "./i18n/uiLang";

const app = createApp(App);
app.use(createPinia());
app.use(router);

// 主题 store 在创建时已应用 data-theme/lang 到 <html>；
// 这里显式初始化一次，确保挂载前生效。
useThemeStore();

app.mount("#app");

// 挂载后启动界面简繁转换（需要真实 DOM）；仅观察文本节点，用户内容以 data-ugc 跳过。
startUiLang();
