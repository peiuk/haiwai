<script setup lang="ts">
// 首页：三 Tab（为你推荐 / 正在关注 / 频道），对齐原型首页结构。
// 支持 ?tab=channels 深链定位到「频道」Tab（对齐原型左导航「频道」项 data-goto）。
import { onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { request, type SubscriptionsResponse } from "../api";
import { useAuthStore } from "../stores/auth";
import FeedTab from "../components/home/FeedTab.vue";
import ChannelsTab from "../components/home/ChannelsTab.vue";
import RecommendTab from "../components/home/RecommendTab.vue";
import RegionBar from "../components/common/RegionBar.vue";

const tabs = [
  { key: "recommend", label: "为你推荐" },
  { key: "following", label: "正在关注" },
  { key: "channels", label: "频道" },
] as const;

type TabKey = (typeof tabs)[number]["key"];

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const initialTab = tabs.some((t) => t.key === route.query.tab)
  ? (route.query.tab as TabKey)
  : "recommend";
const active = ref<TabKey>(initialTab);
// 空 = RegionBar 还没定下国家；定下之前不渲染信息流，免得先按旧国家拉一遍再整块重拉
const regionCode = ref("");

// 「正在关注」关注数 pill：订阅频道数
const followingCount = ref(0);

async function loadFollowingCount(): Promise<void> {
  if (!auth.isLoggedIn) {
    followingCount.value = 0;
    return;
  }
  try {
    const body = await request<SubscriptionsResponse>("/api/v1/me/subscriptions");
    followingCount.value = body.items.length;
  } catch {
    followingCount.value = 0;
  }
}

onMounted(loadFollowingCount);
watch(
  () => auth.isLoggedIn,
  () => void loadFollowingCount(),
);
watch(
  () => route.query.tab,
  (tab) => {
    active.value = tabs.some((item) => item.key === tab) ? (tab as TabKey) : "recommend";
  },
);

// 点击 Tab：同步 active 并回写 URL，刷新/分享链接保留当前分区。
function selectTab(key: TabKey): void {
  active.value = key;
  if ((route.query.tab ?? "recommend") === key) return;
  void router.replace({ name: "home", query: { ...route.query, tab: key } });
}
</script>

<template>
  <section>
    <div class="sticky-head">
      <nav class="tabbar" role="tablist" aria-label="首页分区">
        <button
          v-for="tab in tabs"
          :key="tab.key"
          type="button"
          class="tab"
          :class="{ 'tab--active': active === tab.key }"
          role="tab"
          :aria-selected="active === tab.key"
          @click="selectTab(tab.key)"
        >
          {{ tab.label }}
          <span v-if="tab.key === 'following'" class="pill">{{ followingCount }}</span>
        </button>
      </nav>

      <RegionBar @changed="regionCode = $event" />
    </div>

    <div role="tabpanel" class="tab-panel">
      <template v-if="regionCode">
        <RecommendTab v-if="active === 'recommend'" :key="regionCode" />
        <FeedTab v-else-if="active === 'following'" :key="regionCode" />
        <ChannelsTab v-else :region-code="regionCode" />
      </template>
    </div>
  </section>
</template>

<style scoped>
.sticky-head {
  position: sticky;
  top: 60px;
  z-index: var(--z-sticky);
  background: color-mix(in srgb, var(--bg) 88%, transparent);
  backdrop-filter: blur(12px);
}

/* 移动端：上方只有 top-head 一行（56px） */
@media (max-width: 759px) {
  .sticky-head {
    top: 56px;
    transition: top 0.2s ease;
  }
}
@media (prefers-reduced-motion: reduce) {
  .sticky-head {
    transition: none;
  }
}
.tabbar {
  display: flex;
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
}
.tab {
  flex: 1;
  min-height: var(--tap);
  padding: 15px 4px 13px;
  font-size: var(--fs-15);
  font-weight: 500;
  color: var(--muted);
  text-align: center;
  white-space: nowrap;
  position: relative;
}
.tab:hover {
  background: var(--hover);
}
.tab--active {
  color: var(--text);
  font-weight: 700;
}
.tab--active::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 56px;
  height: 4px;
  border-radius: var(--r-pill);
  background: var(--accent);
}
.pill {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  background: var(--chip);
  color: var(--muted);
  font-size: var(--fs-12);
  font-weight: 600;
  margin-left: 4px;
}
.tab-panel {
  padding: var(--sp-2) 0;
}
</style>

<!-- 顶栏收起后（AppShell 的 AutoHideHeader），Tab 栏和区域栏顶到屏幕最上方，不留空隙 -->
<style>
@media (max-width: 759px) {
  body.hdr-hide .sticky-head {
    top: 0;
  }
}
</style>
