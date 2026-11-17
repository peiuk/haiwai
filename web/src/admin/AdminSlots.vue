<script setup lang="ts">
// 官方频道的房间位：官方指定出现在这个频道里的房间（推荐 / VIP 置顶），按排序号从小到大。
import { ref } from "vue";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminRequest } from "./adminApi";
import { exact, when } from "./shared";

const props = defineProps<{ channelId: string; channelName: string }>();
defineEmits<{ close: [] }>();

type Slot = { room_id: string; name: string; owner_name: string; is_active: boolean; sort_order: number; label: string; expires_at: string | null };
type Hit = { channel_id: string; name: string; owner_name: string; is_active: boolean };

const toast = useToastStore();
const slots = ref<Slot[]>([]);
const hits = ref<Hit[]>([]);
const q = ref("");
const label = ref("推荐");
const days = ref("");
const busy = ref("");
const base = `/api/v1/admin/channels/${props.channelId}/slots`;

async function load(): Promise<void> {
  try {
    slots.value = (await adminRequest<{ items: Slot[] }>(base)).items;
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function search(): Promise<void> {
  try {
    const params = new URLSearchParams({ scope: "room", q: q.value.trim() });
    hits.value = (await adminRequest<{ items: Hit[] }>(`/api/v1/admin/channels?${params.toString()}`)).items.filter((item) => item.is_active);
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function send(key: string, path: string, body: unknown, done: string): Promise<void> {
  if (busy.value) return;
  busy.value = key;
  try {
    await adminRequest(path, jsonBody(body));
    toast.show(done);
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    busy.value = "";
  }
}

function add(hit: Hit): Promise<void> {
  const next = Math.max(0, ...slots.value.map((slot) => slot.sort_order)) + 1;
  return send(hit.channel_id, base, { room_id: hit.channel_id, sort_order: next, label: label.value, days: days.value ? Number(days.value) : null }, "已放入房间位");
}

function remove(slot: Slot): Promise<void> {
  return send(slot.room_id, `${base}/${slot.room_id}/delete`, {}, "已撤下");
}

void load();
</script>

<template>
  <section class="adm-panel">
    <h2>「{{ channelName }}」的房间位 <button type="button" class="btn btn--ghost btn--sm" @click="$emit('close')">收起</button></h2>
    <p v-if="!slots.length" class="adm-empty">还没有指定房间。</p>
    <div v-else class="adm-scroll">
      <table class="adm-table">
        <thead><tr><th class="adm-num">排序</th><th>房间</th><th>房主</th><th>标签</th><th>到期</th><th></th></tr></thead>
        <tbody>
          <tr v-for="slot in slots" :key="slot.room_id">
            <td class="adm-num">{{ slot.sort_order }}</td>
            <td>
              <strong>{{ slot.name }}</strong>
              <span v-if="!slot.is_active" class="tag tag--danger">已下架</span>
            </td>
            <td class="adm-nowrap">{{ slot.owner_name || "—" }}</td>
            <td class="adm-nowrap">{{ slot.label || "—" }}</td>
            <td class="adm-nowrap" :title="slot.expires_at ? exact(slot.expires_at) : ''">{{ slot.expires_at ? when(slot.expires_at) : "长期" }}</td>
            <td><button type="button" class="btn btn--outline btn--sm" :disabled="busy === slot.room_id" @click="remove(slot)">撤下</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="搜索用户房间" placeholder="搜索用户房间名称" />
      <input v-model="label" class="input" maxlength="16" aria-label="前台标签" placeholder="标签（付费位请写「赞助」）" />
      <input v-model="days" class="input" type="number" min="1" max="3650" aria-label="有效天数" placeholder="有效天数，不填长期" />
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>
    <ul v-if="hits.length" class="adm-list">
      <li v-for="hit in hits" :key="hit.channel_id">
        <strong>{{ hit.name }}</strong> <span class="adm-sub">{{ hit.owner_name || "—" }} 创建</span>
        <button type="button" class="btn btn--primary btn--sm" :disabled="busy === hit.channel_id" @click="add(hit)">放入</button>
      </li>
    </ul>
  </section>
</template>
