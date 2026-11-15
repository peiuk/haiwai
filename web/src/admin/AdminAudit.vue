<script setup lang="ts">
// 操作日志：按动作筛选，往下加载更多。
import { ref } from "vue";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import { ACTION_LABELS, TARGET_LABELS, exact, when } from "./shared";

type Row = { id: string; action: string; actor_name: string; target_type: string | null; target_id: string | null; detail: string; created_at: string };
type Page = { items: Row[]; next_cursor: string | null };

const action = ref("");
const items = ref<Row[]>([]);
const cursor = ref<string | null>(null);
const loading = ref(false);
const error = ref("");

async function load(more = false): Promise<void> {
  if (loading.value) return;
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams();
  if (action.value) params.set("action", action.value);
  if (more && cursor.value) params.set("cursor", cursor.value);
  try {
    const body = await adminRequest<Page>(`/api/v1/admin/audit?${params.toString()}`);
    items.value = more ? [...items.value, ...body.items] : body.items;
    cursor.value = body.next_cursor;
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    loading.value = false;
  }
}
void load();
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>操作日志</h1>
      <p>后台的每个操作都记在这里，不能修改或删除</p>
    </header>

    <form class="adm-filters" @submit.prevent="load()">
      <select v-model="action" class="input" aria-label="按动作筛选" @change="load()">
        <option value="">全部动作</option>
        <option value="admin.">后台操作</option>
        <option value="moderation.">审核与举报处理</option>
        <option value="admin.login">登录后台</option>
        <option value="account.">账号</option>
      </select>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load()">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有记录。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>动作</th><th>操作人</th><th>对象</th><th>理由</th><th>时间</th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.id">
              <td>
                {{ ACTION_LABELS[item.action] ?? item.action }}
                <span class="adm-sub adm-mono">{{ item.action }}</span>
              </td>
              <td class="adm-nowrap">{{ item.actor_name || "系统 / 游客" }}</td>
              <td>
                <template v-if="item.target_type">
                  {{ TARGET_LABELS[item.target_type] ?? item.target_type }}
                  <span class="adm-sub adm-mono">{{ item.target_id }}</span>
                </template>
                <template v-else>—</template>
              </td>
              <td class="adm-wide">{{ item.detail || "—" }}</td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="cursor" class="adm-pager">
        <button type="button" class="btn btn--outline btn--sm" :disabled="loading" @click="load(true)">加载更多</button>
      </div>
    </section>
  </div>
</template>
