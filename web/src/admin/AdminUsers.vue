<script setup lang="ts">
// 用户管理：搜索、按状态筛选、封禁 / 解封。设 / 撤管理员在用户详情页。
import { ref } from "vue";
import { RouterLink } from "vue-router";
import AdminPager from "./AdminPager.vue";
import { STATUS_LABELS, exact, statusTone, when } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  user_id: string;
  display_name: string;
  handle: string;
  email: string;
  status: string;
  is_admin: boolean;
  post_count: number;
  created_at: string;
};

const q = ref("");
const status = ref("");
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/users",
  () => ({ q: q.value, status: status.value }),
);

function suspend(item: Row): Promise<void> {
  return ask(
    { title: `封禁「${item.display_name}」？`, message: "封禁后对方立即无法登录和使用，之后可以解封。", confirmLabel: "封禁", danger: true, reason: true },
    item.user_id,
    `/api/v1/admin/users/${item.user_id}/status`,
    (reason) => ({ status: "suspended", reason }),
    "已封禁",
  );
}

function activate(item: Row): Promise<void> {
  return act(item.user_id, `/api/v1/admin/users/${item.user_id}/status`, { status: "active" }, "已解封");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>用户管理</h1>
      <p>点名字看详情；管理员权限在详情页里设置</p>
    </header>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="搜索用户" placeholder="邮箱、名字或账号名" />
      <select v-model="status" class="input" aria-label="按状态筛选" @change="search">
        <option value="">全部状态</option>
        <option value="active">正常</option>
        <option value="suspended">已封禁</option>
      </select>
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的用户。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>用户</th><th>邮箱</th><th class="adm-num">发帖</th><th>状态</th><th>注册时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.user_id">
              <td>
                <RouterLink :to="`/admin/users/${item.user_id}`">{{ item.display_name }}</RouterLink>
                <span v-if="item.is_admin" class="tag tag--link">管理员</span>
                <span v-if="item.handle" class="adm-sub">@{{ item.handle }}</span>
              </td>
              <td class="adm-nowrap">{{ item.email }}</td>
              <td class="adm-num">{{ item.post_count }}</td>
              <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="item.status === 'suspended'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.user_id" @click="activate(item)">解封</button>
                  <button v-else-if="item.status === 'active' && !item.is_admin" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.user_id" @click="suspend(item)">封禁</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <AdminPager :page="page" :total="total" :page-size="pageSize" @go="go" />
    </section>
  </div>
</template>
