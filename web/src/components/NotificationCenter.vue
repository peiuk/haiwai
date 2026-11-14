<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import {
  request,
  type NotificationItem,
  type NotificationsResponse,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";

const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();

const items = ref<NotificationItem[]>([]);
const unreadCount = ref(0);
const nextCursor = ref<string | null>(null);
const loading = ref(false);
const error = ref("");
const busy = ref(false);

const emit = defineEmits<{
  (e: "unread", count: number): void;
}>();

async function load(reset: boolean): Promise<void> {
  if (!auth.isLoggedIn) {
    items.value = [];
    unreadCount.value = 0;
    nextCursor.value = null;
    return;
  }
  loading.value = true;
  error.value = "";
  try {
    const cursor = reset ? "" : nextCursor.value ?? "";
    const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
    const body = await request<NotificationsResponse>(`/api/v1/me/notifications${query}`);
    items.value = reset ? body.items : [...items.value, ...body.items];
    unreadCount.value = body.unread_count;
    nextCursor.value = body.next_cursor ?? null;
    emit("unread", body.unread_count);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "通知加载失败";
  } finally {
    loading.value = false;
  }
}

async function markOne(id: string): Promise<void> {
  busy.value = true;
  try {
    await request(`/api/v1/me/notifications/${id}/read`, { method: "PATCH" });
    const item = items.value.find((it) => it.id === id);
    if (item && item.unread) {
      item.unread = false;
      unreadCount.value = Math.max(0, unreadCount.value - 1);
      emit("unread", unreadCount.value);
    }
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "标记已读失败");
  } finally {
    busy.value = false;
  }
}

async function markAll(): Promise<void> {
  busy.value = true;
  try {
    await request("/api/v1/me/notifications/read-all", { method: "POST" });
    for (const item of items.value) {
      item.unread = false;
    }
    unreadCount.value = 0;
    emit("unread", 0);
    toast.show("已全部标记为已读");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "操作失败");
  } finally {
    busy.value = false;
  }
}

function loadMore(): void {
  void load(false);
}

function openItem(item: NotificationItem): void {
  if (item.content_id) {
    void router.push({ name: "content", params: { id: item.content_id } });
  }
}

onMounted(() => void load(true));

defineExpose({ reload: () => load(true) });
</script>

<template>
  <section class="notification-center">
    <header class="nc-head">
      <h2>通知</h2>
      <span v-if="unreadCount > 0" class="tag tag--link">{{ unreadCount }} 条未读</span>
      <button
        v-if="unreadCount > 0"
        class="btn btn--outline btn--sm"
        type="button"
        :disabled="busy"
        @click="markAll"
      >
        全部已读
      </button>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
    <p v-if="!loading && items.length === 0" class="empty">还没有通知。</p>

    <ul class="nc-list">
      <li
        v-for="item in items"
        :key="item.id"
        class="nc-item"
        :class="{ 'nc-item--unread': item.unread }"
      >
        <div class="nc-body">
          <p class="nc-text" :class="{ 'nc-text--link': item.content_id }" data-ugc @click="openItem(item)">
            {{ item.body }}
          </p>
          <time class="nc-time" :datetime="item.created_at">{{ item.created_at }}</time>
        </div>
        <button
          v-if="item.unread"
          class="btn btn--ghost btn--sm"
          type="button"
          :disabled="busy"
          @click="markOne(item.id)"
        >
          标记已读
        </button>
      </li>
    </ul>

    <div v-if="nextCursor" class="nc-more">
      <button class="btn btn--outline" type="button" :disabled="loading" @click="loadMore">
        {{ loading ? "加载中…" : "加载更多" }}
      </button>
    </div>
  </section>
</template>

<style scoped>
.notification-center {
  display: grid;
  gap: var(--sp-4);
}
.nc-head {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  flex-wrap: wrap;
}
.nc-head h2 {
  margin: 0;
  font-size: var(--fs-17);
}
.nc-list {
  display: grid;
  gap: 0;
  padding: 0;
  margin: 0;
  list-style: none;
}
.nc-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.nc-item--unread .nc-text {
  font-weight: var(--fw-semibold);
}
.nc-body {
  display: grid;
  gap: var(--sp-1);
  min-width: 0;
}
.nc-text {
  margin: 0;
  color: var(--text);
  overflow-wrap: anywhere;
}
.nc-text--link {
  cursor: pointer;
}
.nc-text--link:hover {
  color: var(--accent-ink);
}
.nc-time {
  color: var(--muted);
  font-size: var(--fs-12);
}
.nc-more {
  display: flex;
  justify-content: center;
}
</style>
