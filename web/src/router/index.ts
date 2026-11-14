import { createRouter, createWebHistory } from "vue-router";
import type { RouteRecordRaw } from "vue-router";
import AppShell from "../layouts/AppShell.vue";
import { setDocumentTitle } from "../i18n/uiLang";
import { homeCacheKey } from "./homeCache";

// 路由结构对齐原型：首页三 Tab（Home 内含「为你推荐/正在关注/频道」）、
// 发现、消息、我的，以及房间详情、发布页、内容详情、用户主页。
const routes: RouteRecordRaw[] = [
  {
    path: "/",
    component: AppShell,
    children: [
      { path: "", name: "home", component: () => import("../views/HomeView.vue") },
      { path: "discover", name: "discover", meta: { title: "发现" }, component: () => import("../views/DiscoverView.vue") },
      { path: "search", name: "search", meta: { title: "搜索" }, component: () => import("../views/SearchView.vue") },
      { path: "messages", name: "messages", meta: { title: "消息" }, component: () => import("../views/MessagesView.vue") },
      { path: "profile", name: "profile", meta: { title: "我的" }, component: () => import("../views/ProfileView.vue") },
      { path: "room/:id", name: "room", meta: { title: "房间" }, component: () => import("../views/RoomView.vue") },
      { path: "channel/:id", name: "channel", meta: { title: "频道" }, component: () => import("../views/ChannelView.vue") },
      { path: "publish", name: "publish", meta: { title: "发布内容" }, component: () => import("../views/PublishView.vue") },
      { path: "content/:id", name: "content", meta: { title: "内容详情" }, component: () => import("../views/ContentView.vue") },
      { path: "user/:id", name: "user", meta: { title: "用户主页" }, component: () => import("../views/UserView.vue") },
      { path: "legal/:section", name: "legal", meta: { title: "条款与政策" }, component: () => import("../views/LegalView.vue") },
    ],
  },
  // 兜底：未匹配回到首页
  { path: "/:pathMatch(.*)*", redirect: "/" },
];

let viaHistory = false;
if (typeof window !== "undefined") {
  // 必须在 createRouter 之前注册，这样会先于路由自己的 popstate 监听执行。
  window.addEventListener("popstate", () => {
    viaHistory = true;
  });
}

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(_to, _from, savedPosition) {
    // 后退 / 前进时回到离开时的位置，其余情况回到顶部。
    return savedPosition ?? { top: 0 };
  },
});

router.beforeEach((to, from) => {
  if (to.name === "home" && from.name && from.name !== "home" && !viaHistory) {
    homeCacheKey.value += 1;
  }
});
router.afterEach((to) => {
  viaHistory = false;
  // 网页标题随页面变化（MASTER §22.13：「页面名 · 海外圈」），标签页、历史记录、分享预览才分得清
  const page = typeof to.meta.title === "string" ? to.meta.title : "";
  setDocumentTitle(page ? `${page} · 海外圈` : "海外圈");
});

export default router;
