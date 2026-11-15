<script setup lang="ts">
// AppShell：响应式三栏布局 + 左导航 + 移动端底部 Tab，对齐 MASTER §6。
// 断点：≥1100 三栏；760–1099 两栏（隐藏右栏）；≤759 单栏 + 底部 Tab。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { useAuthStore } from "../stores/auth";
import { useThemeStore } from "../stores/theme";
import Toast from "../components/base/Toast.vue";
import BaseIcon from "../components/base/BaseIcon.vue";
import GlobalSearch from "../components/common/GlobalSearch.vue";
import RightRail from "../components/common/RightRail.vue";
import LoginPrompt from "../components/common/LoginPrompt.vue";
import Avatar from "../components/base/Avatar.vue";
import { request, type BadgesResponse } from "../api";
import { homeCacheKey } from "../router/homeCache";

const route = useRoute();
const auth = useAuthStore();
const theme = useThemeStore();

interface NavItem {
  key: string;
  label: string;
  to: string;
  icon: string;
}

const navItems: NavItem[] = [
  { key: "home", label: "首页", to: "/", icon: "i-home" },
  { key: "channels", label: "频道", to: "/?tab=channels", icon: "i-grid" },
  { key: "discover", label: "发现", to: "/discover", icon: "i-search" },
  { key: "messages", label: "消息", to: "/messages", icon: "i-mail" },
  { key: "profile", label: "我的", to: "/profile", icon: "i-user" },
];

// 底部 Tab（移动端）与左导航共用同一组条目；发布仅走右下角 FAB（对齐原型 MASTER §21）
const bottomItems = computed(() => navItems);

function isActive(item: NavItem): boolean {
  if (item.key === "channels") {
    return route.name === "home" && route.query.tab === "channels";
  }
  if (item.key === "home") {
    return route.name === "home" && route.query.tab !== "channels";
  }
  return route.name === item.key;
}

// 再点一次当前所在的导航项 = 回到顶部（MASTER §22.14 ScrollMemory，X 式）
function onNavClick(item: NavItem): void {
  if (!isActive(item)) return;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: 0, behavior: reduced ? "auto" : "smooth" });
}

function themeLabel(): string {
  return theme.theme === "dark" ? "浅色模式" : "深色模式";
}

function langLabel(): string {
  return theme.lang === "zh-Hans" ? "繁體" : "简体";
}

// 全站搜索框仅在首页 / 发现页显示（对齐原型 ['home','discover']）
const showSearch = computed(() => ["home", "discover", "search"].includes(String(route.name ?? "")));
const showFab = computed(() => ["home", "discover", "channel"].includes(String(route.name ?? "")));

// 吸顶栏标题：首页显示「首页」、发现显示「发现」，其余页面不显示标题（由页面自身渲染）
const PAGE_TITLES: Record<string, string> = {
  home: "首页",
  discover: "发现",
  search: "搜索",
};
const pageTitle = computed(() => PAGE_TITLES[String(route.name ?? "")] ?? "");

// AutoHideHeader（MASTER §22.14，仅手机端样式生效）：首页与房间页下滑超过 140px 收起顶栏，
// 上滑立即出现；顶部 140px 内、焦点在顶栏里（如搜索框）、有弹层打开时始终显示。
const HIDE_ROUTES = new Set(["home", "room"]);
let lastScrollY = 0;

function onScroll(): void {
  const y = window.scrollY || 0;
  const dy = y - lastScrollY;
  lastScrollY = y;
  const body = document.body.classList;
  const header = document.querySelector(".top-head, .topbar");
  if (
    !HIDE_ROUTES.has(String(route.name ?? "")) ||
    y < 140 ||
    header?.contains(document.activeElement) ||
    document.querySelector('[aria-modal="true"]')
  ) {
    body.remove("hdr-hide");
    return;
  }
  if (dy > 6) body.add("hdr-hide");
  else if (dy < -6) body.remove("hdr-hide");
}

// 用键盘 Tab 到被收起的顶栏时，让它重新出现
function onFocusIn(event: FocusEvent): void {
  const header = document.querySelector(".top-head, .topbar");
  if (header?.contains(event.target as Node)) document.body.classList.remove("hdr-hide");
}

onMounted(() => {
  window.addEventListener("scroll", onScroll, { passive: true });
  document.addEventListener("focusin", onFocusIn);
});
onBeforeUnmount(() => {
  window.removeEventListener("scroll", onScroll);
  document.removeEventListener("focusin", onFocusIn);
  document.body.classList.remove("hdr-hide");
});
watch(
  () => route.fullPath,
  () => document.body.classList.remove("hdr-hide"),
);

// 未读角标：/badges 返回 { notifications, messages, total }，登录后每 60s 轮询
const unreadTotal = ref(0);
let badgeTimer = 0;

async function refreshBadges(): Promise<void> {
  if (!auth.isLoggedIn) {
    unreadTotal.value = 0;
    return;
  }
  try {
    const body = await request<BadgesResponse>("/api/v1/me/badges");
    unreadTotal.value = body.total;
  } catch {
    // 角标静默失败，不影响页面
  }
}

watch(
  () => auth.isLoggedIn,
  (loggedIn) => {
    window.clearInterval(badgeTimer);
    if (loggedIn) {
      refreshBadges();
      auth.refreshProfile();
      badgeTimer = window.setInterval(refreshBadges, 60_000);
    } else {
      unreadTotal.value = 0;
    }
  },
  { immediate: true },
);
</script>

<template>
  <div class="shell">
    <!-- 顶部栏（移动端） -->
    <!-- 首页 / 发现页的品牌、搜索和工具按钮已合并在 top-head 一行里，这里只给其余页面用 -->
    <!-- 发布页、帖子详情页有自己的顶栏（带返回），不再叠一层 -->
    <header v-if="route.name !== 'publish' && route.name !== 'content' && !pageTitle" class="topbar">
      <strong class="brand"><span class="brand-word">海外圈</span></strong>
      <div class="topbar-actions">
        <button class="icon-btn" type="button" :aria-label="themeLabel()" @click="theme.toggleTheme()">
          <BaseIcon name="i-theme" :size="22" />
        </button>
        <button
          class="icon-btn lang-btn"
          type="button"
          data-no-hant
          :aria-label="langLabel()"
          @click="theme.setLang(theme.lang === 'zh-Hans' ? 'zh-Hant' : 'zh-Hans')"
        >
          {{ langLabel() }}
        </button>
      </div>
    </header>

    <div class="shell-body" :class="{ 'shell-body--publish': route.name === 'publish' }">
      <!-- 左导航（桌面端） -->
      <aside class="left-col">
        <strong class="brand"><img class="brand-mark" src="/logo-mark.png" alt="" width="62" height="44" /><span class="brand-word">海外圈</span></strong>
        <nav aria-label="主导航">
          <RouterLink
            v-for="item in navItems"
            :key="item.key"
            :to="item.to"
            class="nav-link"
            :class="{ 'nav-link--active': isActive(item) }"
            :aria-current="isActive(item) ? 'page' : undefined"
            @click="onNavClick(item)"
          >
            <span class="nav-icon">
              <BaseIcon :name="item.icon" :size="22" />
              <span
                v-if="item.key === 'messages' && unreadTotal > 0"
                class="nav-badge"
                :aria-label="`${unreadTotal} 条未读`"
              >{{ unreadTotal > 99 ? "99+" : unreadTotal }}</span>
            </span>
            <span>{{ item.label }}</span>
          </RouterLink>
          <!-- 发布内容主按钮（对齐原型左导航 post-btn）-->
          <RouterLink to="/publish" class="post-btn" aria-label="发布内容">
            <BaseIcon name="i-feather" :size="20" />
            <span>发布内容</span>
          </RouterLink>
        </nav>
        <RouterLink to="/profile" class="left-footer">
          <Avatar :name="auth.displayName || '我'" :size="38" :image="auth.profile?.avatar_key" />
          <span v-if="auth.isLoggedIn">
            <strong>{{ auth.displayName || "我的" }}</strong>
            <small v-if="auth.handle">@{{ auth.handle }}</small>
          </span>
          <span v-else>
            <strong>我的</strong><small>登录或注册</small>
          </span>
        </RouterLink>
      </aside>

      <!-- 主栏 -->
      <main class="main-col" :class="{ 'main-col--home': route.name === 'home', 'main-col--publish': route.name === 'publish' }">
        <!-- 吸顶栏：标题 + 搜索 + 工具按钮同行（对齐原型 top-head） -->
        <div v-if="pageTitle" class="top-head">
          <!-- 手机端首页标题位显示产品名，桌面显示「首页」（MASTER §22.13） -->
          <h1 class="top-head-title">
            <span v-if="route.name === 'home'" class="pt-brand brand-word">海外圈</span>
            <span class="pt-page">{{ pageTitle }}</span>
          </h1>
          <GlobalSearch v-if="showSearch" class="top-head-search" />
          <div class="top-head-tools">
            <button class="icon-btn" type="button" :aria-label="themeLabel()" @click="theme.toggleTheme()">
              <BaseIcon name="i-theme" :size="22" />
            </button>
            <button
              class="icon-btn lang-btn"
              type="button"
              data-no-hant
              :aria-label="langLabel()"
              @click="theme.setLang(theme.lang === 'zh-Hans' ? 'zh-Hant' : 'zh-Hans')"
            >
              {{ langLabel() }}
            </button>
          </div>
        </div>
        <!-- 只缓存首页：后退回到信息流时保留已加载的内容和滚动位置 -->
        <RouterView v-slot="{ Component }">
          <!-- include 按组件名匹配：HomeView.vue 改名时这里要一起改，否则缓存会悄悄失效 -->
          <KeepAlive include="HomeView" :max="1">
            <component
              :is="Component"
              :key="route.name === 'home' ? `home-${homeCacheKey}` : undefined"
            />
          </KeepAlive>
        </RouterView>
      </main>

      <!-- 右栏（≥1100px 显示）：热门关键词 + 推荐频道 + 今日最关注等 -->
      <aside class="right-col">
        <RightRail />
      </aside>
    </div>

    <!-- 底部 Tab（移动端） -->
    <nav v-if="route.name !== 'publish'" class="bottom-nav" aria-label="底部导航">
      <RouterLink
        v-for="item in bottomItems"
        :key="item.key"
        :to="item.to"
        class="bottom-item"
        :class="{ 'bottom-item--active': isActive(item) }"
        :aria-current="isActive(item) ? 'page' : undefined"
        @click="onNavClick(item)"
      >
        <span class="nav-icon">
          <BaseIcon :name="item.icon" :size="22" />
          <span
            v-if="item.key === 'messages' && unreadTotal > 0"
            class="nav-badge"
            :aria-label="`${unreadTotal} 条未读`"
          >{{ unreadTotal > 99 ? "99+" : unreadTotal }}</span>
        </span>
        <span class="bottom-label">{{ item.label }}</span>
      </RouterLink>
    </nav>

    <!-- 移动端发布 FAB：只在看内容的页面出现，消息 / 我的 / 详情页不需要 -->
    <RouterLink
      v-if="showFab"
      to="/publish"
      class="fab"
      aria-label="发布内容"
    >
      <BaseIcon name="i-plus" :size="26" />
    </RouterLink>

    <Toast />
    <LoginPrompt />
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.topbar {
  display: none;
}

.shell-body {
  flex: 1;
  width: 100%;
  max-width: var(--app-max);
  margin: 0 auto;
  display: grid;
  grid-template-columns: var(--col-left) minmax(0, 1fr) var(--col-right);
  gap: var(--sp-6);
  padding: 0 var(--sp-6);
}

.left-col {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: var(--sp-6) 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-6);
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: var(--fs-21);
  font-weight: var(--fw-heavy);
  padding: 0 var(--sp-3);
}
/* 字标：取 logo 地球的蓝到人物的青，字距拉开，避免雅黑粗体挤成一团 */
.brand-word {
  --brand-from: #1764c8;
  --brand-to: #0e9a8a;
  font-size: 20px;
  font-weight: var(--fw-bold);
  letter-spacing: 0.12em;
  background: linear-gradient(90deg, var(--brand-from), var(--brand-to));
  -webkit-background-clip: text;
  background-clip: text;
  color: transparent;
}
:global([data-theme="dark"]) .brand-word {
  --brand-from: #5aa2ff;
  --brand-to: #3cc7b4;
}
.brand-mark {
  width: 62px;
  height: 44px;
  flex: none;
  /* 图是白底，圆角方块在深色模式下也像个图标 */
  border-radius: 8px;
}
.lang-btn {
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
}

.nav-link {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  min-height: var(--tap);
  padding: 0 var(--sp-3);
  border-radius: var(--r-pill);
  color: var(--text);
  font-size: var(--fs-15);
  font-weight: var(--fw-semibold);
}
/* 导航图标 + 未读角标（桌面左导航与手机底栏共用） */
.nav-icon {
  position: relative;
  display: inline-flex;
}
.nav-badge {
  position: absolute;
  top: -4px;
  right: -10px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: var(--r-pill);
  background: var(--danger);
  color: var(--bg);
  font-size: 10px;
  line-height: 16px;
  text-align: center;
  font-weight: var(--fw-bold);
}
.pt-brand {
  display: none;
}

.nav-link:hover {
  background: var(--hover);
  text-decoration: none;
}
.nav-link--active {
  font-weight: var(--fw-heavy);
}

.post-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  min-height: var(--tap);
  margin-top: var(--sp-3);
  padding: 0 var(--sp-4);
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
}
.post-btn:hover {
  text-decoration: none;
  opacity: 0.92;
}

.left-footer {
  margin-top: auto;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: var(--r-pill);
  color: var(--text);
  text-decoration: none;
}
.left-footer:hover { background: var(--hover); }
.left-footer span { display: grid; gap: 2px; }
.left-footer small { color: var(--muted); font-size: var(--fs-12); }

.main-col {
  min-width: 0;
  padding: var(--sp-6) 0;
}

/* 吸顶栏：标题 + 搜索 + 工具按钮同行（对齐原型 .top-head） */
.top-head {
  position: sticky;
  top: 0;
  z-index: var(--z-sticky);
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  margin-bottom: var(--sp-4);
  padding-top: var(--sp-2);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(12px);
}
/* 手机搜索全屏时：backdrop-filter / transform 会让 fixed 定位相对顶栏而不是整屏，先关掉 */
.top-head:has(.gsearch--active) {
  z-index: var(--z-modal); /* 顶栏自成层叠上下文，不抬高的话吸顶 Tab 和底栏会盖在全屏搜索上面 */
  backdrop-filter: none;
  transform: none !important;
}
.top-head-title {
  margin: 0;
  font-size: 19px;
  font-weight: 800;
  flex-shrink: 0;
}
.top-head-search {
  flex: 1;
  min-width: 0;
  max-width: 620px;
  margin: 0 auto;
}
.top-head-tools {
  display: flex;
  gap: var(--sp-1);
  flex-shrink: 0;
}
.icon-btn {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  color: var(--muted);
}
.icon-btn:hover {
  background: var(--hover);
  color: var(--text);
}

.right-col {
  position: sticky;
  top: 0;
  height: 100vh;
  padding: var(--sp-6) 0;
  overflow-y: auto;
}

.bottom-nav {
  display: none;
}

.fab {
  display: none;
}

/* 760–1099px：两栏，隐藏右栏 */
@media (max-width: 1099px) {
  .shell-body {
    grid-template-columns: var(--col-left) minmax(0, 1fr);
  }
  .shell-body--publish { padding: 0; }
  .right-col {
    display: none;
  }
}

/* ≤759px：单栏 + 底部 Tab，隐藏左栏 */
@media (max-width: 759px) {
  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: var(--z-sticky);
    padding: 0 var(--sp-4);
    min-height: 56px;
    background: var(--bg);
    border-bottom: 1px solid var(--border);
  }
  .topbar-actions {
    display: flex;
    gap: var(--sp-1);
  }

  .shell-body {
    grid-template-columns: minmax(0, 1fr);
    max-width: 640px;
    padding: 0 var(--sp-4);
    /* 底栏 + 发布按钮（56px + 间距）的高度，最后一条内容不会被压住 */
    padding-bottom: calc(var(--bottom-bar) + 88px + env(safe-area-inset-bottom));
  }
  .left-col {
    display: none;
  }
  .main-col {
    padding: var(--sp-4) 0;
  }
  .main-col--publish { padding: 0; }

  /* 移动端：首页 / 发现页只有 top-head 一行（标题 + 搜索 + 工具按钮），对齐原型 */
  .top-head {
    gap: var(--sp-2);
    min-height: 56px;
    margin-bottom: 0;
    padding-top: 0;
  }
  .top-head-title {
    font-size: 17px;
  }
  .pt-brand {
    display: inline;
  }
  .pt-brand + .pt-page {
    display: none;
  }

  /* AutoHideHeader：下滑收起（0.2s），底栏与发布按钮不动；减少动效时无动画 */
  .top-head,
  .topbar {
    transition: transform 0.2s ease;
  }
  /* 收起时的位移规则在文件末尾的非 scoped 样式块里（scoped 的 :global 逗号并列会被编译坏） */
  @media (prefers-reduced-motion: reduce) {
    .top-head,
    .topbar {
      transition: none;
    }
  }

  .bottom-nav {
    display: flex;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: var(--z-bottom-bar);
    height: calc(var(--bottom-bar) + env(safe-area-inset-bottom));
    padding-bottom: env(safe-area-inset-bottom);
    background: var(--bg);
    border-top: 1px solid var(--border);
  }
  .bottom-item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 2px;
    color: var(--muted);
  }
  .bottom-item--active {
    color: var(--accent-ink);
    font-weight: var(--fw-bold);
  }
  .bottom-label {
    font-size: var(--fs-11);
  }

  .fab {
    display: grid;
    place-items: center;
    position: fixed;
    right: var(--sp-4);
    bottom: calc(var(--bottom-bar) + var(--sp-4) + env(safe-area-inset-bottom));
    width: 56px;
    height: 56px;
    border-radius: 50%;
    background: var(--accent-strong);
    color: var(--on-accent);
    box-shadow: var(--shadow);
    z-index: var(--z-bottom-bar);
  }
}
</style>

<!-- AutoHideHeader 的收起位移：依赖 body 上的 hdr-hide 类，必须是非 scoped 样式 -->
<style>
@media (max-width: 759px) {
  body.hdr-hide .top-head,
  body.hdr-hide .topbar {
    transform: translateY(-100%);
  }
}
</style>
