<script setup lang="ts">
// 后台外壳：左侧菜单 + 顶栏 + 页面区。不套前台的 AppShell。
import { onBeforeUnmount, onMounted, ref } from "vue";
import { RouterLink, RouterView, useRoute, useRouter } from "vue-router";
import Toast from "../components/base/Toast.vue";
import { useThemeStore } from "../stores/theme";
import AdminConfirm from "./AdminConfirm.vue";
import { ADMIN_CHANGED, ADMIN_SIGNED_OUT, adminLogout, adminMe, adminRequest, loadAdminMe } from "./adminApi";
import type { AdminStats } from "./shared";
import "./admin.css";

type Badge = "cases" | "review";
const NAV: { to: string; label: string; badge?: Badge }[] = [
  { to: "/admin", label: "概览" },
  { to: "/admin/reports", label: "举报", badge: "cases" },
  { to: "/admin/review", label: "待审核", badge: "review" },
  { to: "/admin/posts", label: "帖子" },
  { to: "/admin/listings", label: "分类信息" },
  { to: "/admin/news", label: "新闻 / 公告" },
  { to: "/admin/comments", label: "留言" },
  { to: "/admin/users", label: "用户" },
  { to: "/admin/channels", label: "频道 / 房间" },
  { to: "/admin/regions", label: "国家" },
  { to: "/admin/terms", label: "敏感词" },
  { to: "/admin/audit", label: "操作日志" },
  { to: "/admin/mail", label: "邮件设置" },
  { to: "/admin/security", label: "账号安全" },
];

const route = useRoute();
const router = useRouter();
const theme = useThemeStore();
const counts = ref<Record<Badge, number>>({ cases: 0, review: 0 });

async function loadCounts(): Promise<void> {
  try {
    const stats = await adminRequest<AdminStats>("/api/v1/admin/stats");
    counts.value = {
      cases: stats.open_cases,
      review: stats.pending_contents + stats.pending_comments + stats.pending_channels + stats.pending_pushes,
    };
  } catch {
    // 数字只是提示；登录失效会由 ADMIN_SIGNED_OUT 处理
  }
}

function toLogin(): void {
  void router.replace({ name: "admin-login" });
}

async function logout(): Promise<void> {
  await adminLogout();
  toLogin();
}

onMounted(async () => {
  window.addEventListener(ADMIN_SIGNED_OUT, toLogin);
  window.addEventListener(ADMIN_CHANGED, loadCounts);
  void loadCounts();
  try {
    await loadAdminMe();
  } catch {
    // 名字拿不到不影响使用
  }
});
onBeforeUnmount(() => {
  window.removeEventListener(ADMIN_SIGNED_OUT, toLogin);
  window.removeEventListener(ADMIN_CHANGED, loadCounts);
});
</script>

<template>
  <div class="adm">
    <aside class="adm-side">
      <strong class="adm-brand">海外圈后台</strong>
      <nav class="adm-nav" aria-label="后台菜单">
        <RouterLink v-for="item in NAV" :key="item.to" :to="item.to" class="adm-link">
          {{ item.label }}
          <span v-if="item.badge && counts[item.badge] > 0" class="adm-badge" :aria-label="`${counts[item.badge]} 条待处理`">
            {{ counts[item.badge] }}
          </span>
        </RouterLink>
      </nav>
    </aside>
    <div class="adm-body">
      <header class="adm-top">
        <span v-if="adminMe.display_name" class="adm-who">
          {{ adminMe.display_name }}（{{ adminMe.is_super ? "超级管理员" : "管理员" }}）
          <RouterLink v-if="!adminMe.two_factor" to="/admin/security" class="tag tag--warn">未开两步验证</RouterLink>
        </span>
        <button type="button" class="btn btn--ghost btn--sm" @click="theme.toggleTheme()">切换深浅色</button>
        <a href="/" target="_blank" rel="noopener" class="btn btn--ghost btn--sm">打开前台</a>
        <button type="button" class="btn btn--outline btn--sm" @click="logout">退出</button>
      </header>
      <main class="adm-main">
        <!-- 帖子 / 分类信息 / 新闻共用一个组件，按路径重建，免得筛选条件串页 -->
        <RouterView :key="route.path" />
      </main>
    </div>
    <AdminConfirm />
    <Toast />
  </div>
</template>
