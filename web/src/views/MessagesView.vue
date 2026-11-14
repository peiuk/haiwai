<script setup lang="ts">
// 消息页：站内私信 + 通知中心两个 Tab（对齐 MASTER §22.15 MessagesSegment）。
// Tab 顺序「私信 / 通知」，默认私信；`?msg=notif` 直达通知。
// 角标分别来自 DmInbox 与 NotificationCenter 的 unread 事件，互不耦合。
import { ref } from "vue";
import { useRoute } from "vue-router";
import NotificationCenter from "../components/NotificationCenter.vue";
import DmInbox from "../components/messages/DmInbox.vue";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const route = useRoute();

const tabs = [
  { id: "dm", label: "私信" },
  { id: "notifications", label: "通知" },
] as const;
type TabId = (typeof tabs)[number]["id"];

const active = ref<TabId>(route.query.msg === "notif" ? "notifications" : "dm");
const unreadNotifications = ref(0);
const unreadDm = ref(0);
</script>

<template>
  <section>
    <h1 class="page-title">消息</h1>

    <div class="tablist" role="tablist" aria-label="消息类型">
      <button
        v-for="tab in tabs"
        :key="tab.id"
        type="button"
        role="tab"
        class="tab"
        :class="{ active: active === tab.id }"
        :aria-selected="active === tab.id"
        @click="active = tab.id"
      >
        {{ tab.label }}
        <span
          v-if="(tab.id === 'notifications' && unreadNotifications) || (tab.id === 'dm' && unreadDm)"
          class="tab-badge"
          :aria-label="`${tab.id === 'dm' ? unreadDm : unreadNotifications} 条未读`"
        >{{ tab.id === "dm" ? unreadDm : unreadNotifications }}</span>
      </button>
    </div>

    <p v-if="!auth.isLoggedIn" class="empty">注册或登录后查看私信与通知。</p>

    <div v-else class="tabpanel" role="tabpanel">
      <DmInbox v-if="active === 'dm'" @unread="unreadDm = $event" />
      <NotificationCenter v-else @unread="unreadNotifications = $event" />
    </div>
  </section>
</template>

<style scoped>
.page-title {
  margin: 0 0 var(--sp-4);
  font-size: var(--fs-21);
}
.tablist {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: var(--sp-4);
}
.tab {
  min-height: 48px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-2);
  padding: 0 var(--sp-3);
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-14);
  font-weight: 600;
  cursor: pointer;
}
.tab.active {
  color: var(--text);
  border-bottom-color: var(--accent-strong);
}
.tab-badge {
  min-width: 20px;
  padding: 1px 6px;
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: var(--fs-11);
}
.empty {
  padding: var(--sp-6) 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
</style>
