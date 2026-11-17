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

// 视频不提供下载：屏蔽视频上的右键菜单（「视频另存为」）；控制条里的下载按钮由各 <video> 的 controlslist 去掉。
// shortcut: 只挡普通用户，懂行的人仍能从网络请求拿到文件；要真防盗再上 HLS 分片 + 签名链接。
document.addEventListener("contextmenu", (e) => {
  if (e.target instanceof Element && e.target.closest("video")) e.preventDefault();
});

// 挂载后启动界面简繁转换（需要真实 DOM）；仅观察文本节点，用户内容以 data-ugc 跳过。
startUiLang();
