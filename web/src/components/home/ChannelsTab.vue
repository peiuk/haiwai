<script setup lang="ts">
// 「频道」目录 Tab：频道列表 + 订阅/退订，对齐 /channels 与 /me/subscriptions。
import { computed, ref, watch } from "vue";
import { request, type Channel, type Subscription } from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import Avatar from "../base/Avatar.vue";
import BaseTag from "../base/BaseTag.vue";

const auth = useAuthStore();
const toast = useToastStore();
const props = defineProps<{ regionCode: string }>();

const channels = ref<Channel[]>([]);
const subscriptions = ref<Subscription[]>([]);
const loading = ref(false);
const error = ref("");
const busyId = ref("");

const subscribedIds = computed(() => new Set(subscriptions.value.map((s) => s.channel_id)));
const visibleChannels = computed(() => channels.value.filter((channel) =>
  channel.kind !== "room" &&
  (channel.region_code === "GLOBAL" || channel.region_code === props.regionCode),
));
const groups = computed(() => [
  { code: "GLOBAL", title: "国际频道", items: visibleChannels.value.filter((channel) => channel.region_code === "GLOBAL") },
  ...(props.regionCode === "GLOBAL" ? [] : [
    { code: props.regionCode, title: props.regionCode === "UK" ? "英国频道" : `${props.regionCode} 频道`, items: visibleChannels.value.filter((channel) => channel.region_code === props.regionCode) },
  ]),
]);

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [chBody, subBody] = await Promise.all([
      request<{ items: Channel[] }>("/api/v1/channels"),
      auth.isLoggedIn
        ? request<{ items: Subscription[] }>("/api/v1/me/subscriptions")
        : Promise.resolve({ items: [] as Subscription[] }),
    ]);
    channels.value = chBody.items;
    subscriptions.value = subBody.items;
  } catch (err) {
    error.value = err instanceof Error ? err.message : "频道列表暂时打不开";
  } finally {
    loading.value = false;
  }
}

async function toggle(id: string): Promise<void> {
  if (!auth.isLoggedIn) {
    toast.show("先注册或登录，再加入频道");
    return;
  }
  busyId.value = id;
  try {
    if (subscribedIds.value.has(id)) {
      await request(`/api/v1/me/subscriptions/${id}`, { method: "DELETE" });
      toast.show("已退订");
    } else {
      await request(`/api/v1/me/subscriptions/${id}`, { method: "PUT" });
      toast.show("已加入频道");
    }
    await load();
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "操作没有成功");
  } finally {
    busyId.value = "";
  }
}

watch(() => auth.isLoggedIn, () => void load());
void load();
</script>

<template>
  <div class="channels-tab">
    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
    <div class="ch-tools">
      <span>{{ visibleChannels.length }} 个频道</span>
    </div>
    <p v-if="loading && !channels.length" class="ch-state">正在加载频道…</p>
    <p v-else-if="!error && !visibleChannels.length" class="ch-state">当前国家还没有公开频道</p>

    <section v-for="group in groups" v-show="group.items.length" :key="group.code" class="ch-group">
      <h2>{{ group.title }} <span>{{ group.items.length }}</span></h2>
      <ul class="ch-list">
      <li v-for="channel in group.items" :key="channel.id" class="ch-item">
        <Avatar :name="channel.name_hans" :size="42" kind="channel" />
        <RouterLink :to="{ name: 'channel', params: { id: channel.id } }" class="ch-main">
          <div class="ch-title">
            <span class="ch-name" data-ugc>{{ channel.name_hans }}</span>
            <BaseTag v-if="channel.certified" variant="link">官方</BaseTag>
          </div>
          <p class="ch-meta">{{ group.code === "GLOBAL" ? "各国共享" : "当前国家" }} · {{ channel.subscriber_count }} 人订阅</p>
        </RouterLink>
        <button
          class="btn btn--sm"
          :class="subscribedIds.has(channel.id) ? 'btn--outline' : 'btn--primary'"
          type="button"
          :disabled="busyId === channel.id"
          :aria-pressed="subscribedIds.has(channel.id)"
          @click="toggle(channel.id)"
        >
          {{ subscribedIds.has(channel.id) ? "退订" : "加入" }}
        </button>
      </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.channels-tab {
  display: grid;
  gap: var(--sp-2);
}
.ch-tools {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: var(--sp-2) var(--sp-3);
}
.ch-tools span, .ch-state { color: var(--muted); font-size: var(--fs-12); }
.ch-tools span { white-space: nowrap; }
.ch-state { margin: 0; padding: var(--sp-3); }
.ch-group h2 {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  padding: 10px var(--sp-3);
  color: var(--text);
  font-size: var(--fs-15);
  border-bottom: 1px solid var(--border);
}
.ch-group h2 span { color: var(--muted); font-size: var(--fs-12); font-weight: 400; }
.ch-group {
  /* 按列表本身的宽度切列数（不看窗口宽度）：主栏够宽时一行两个，手机一行一个 */
  container-type: inline-size;
}
.ch-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  gap: 0;
}
.ch-item {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  padding: 10px var(--sp-3);
  border-bottom: 1px solid var(--border);
}
@container (min-width: 560px) {
  .ch-list { grid-template-columns: 1fr 1fr; }
  .ch-item { padding: var(--sp-3); }
  .ch-item:nth-child(odd) { border-right: 1px solid var(--border); }
}
.ch-main {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: var(--sp-1);
  text-decoration: none;
}
.ch-title {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.ch-name {
  font-weight: var(--fw-semibold);
  color: var(--text);
  overflow-wrap: anywhere;
}
.ch-meta {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
}
</style>
