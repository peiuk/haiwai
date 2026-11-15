<script setup lang="ts">
// 频道 / 房间管理：搜索、认证、上架 / 下架。
import { ref } from "vue";
import AdminPager from "./AdminPager.vue";
import { KIND_LABELS, STATUS_LABELS, exact, when } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  channel_id: string;
  code: string;
  name: string;
  kind: string;
  owner_name: string;
  is_active: boolean;
  is_certified: boolean;
  certified: boolean;
  review_status: string;
  subscriber_count: number;
  created_at: string;
};

const q = ref("");
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/channels",
  () => ({ q: q.value }),
);

function deactivate(item: Row): Promise<void> {
  return ask(
    { title: `下架「${item.name}」？`, message: "下架后前台不再显示，成员和内容保留，可以重新上架。", confirmLabel: "下架", danger: true, reason: true },
    item.channel_id,
    `/api/v1/admin/channels/${item.channel_id}/active`,
    (reason) => ({ active: false, reason }),
    "已下架",
  );
}

function activate(item: Row): Promise<void> {
  return act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/active`, { active: true }, "已上架");
}

function certify(item: Row): Promise<void> {
  return act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/certified`, { certified: !item.is_certified }, item.is_certified ? "已取消认证" : "已认证");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>频道 / 房间</h1>
      <p>官方频道自带认证；用户房间可以在这里加认证标记</p>
    </header>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="搜索频道" placeholder="名称或代号" />
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的频道。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>名称</th><th>类型</th><th>创建者</th><th class="adm-num">成员</th><th>状态</th><th>创建时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.channel_id">
              <td>
                <strong>{{ item.name }}</strong>
                <span v-if="item.certified" class="tag tag--link">已认证</span>
                <span class="adm-sub adm-mono">{{ item.code }}</span>
              </td>
              <td class="adm-nowrap">{{ KIND_LABELS[item.kind] ?? item.kind }}</td>
              <td class="adm-nowrap">{{ item.owner_name || "官方" }}</td>
              <td class="adm-num">{{ item.subscriber_count }}</td>
              <td class="adm-nowrap">
                <span class="tag" :class="item.is_active ? 'tag--good' : 'tag--danger'">{{ item.is_active ? "已上架" : "已下架" }}</span>
                <span v-if="item.review_status !== 'approved'" class="tag tag--warn">{{ STATUS_LABELS[item.review_status] ?? item.review_status }}</span>
              </td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <!-- 官方频道天然认证，不需要也不能改 -->
                  <button v-if="!item.kind.startsWith('official')" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="certify(item)">{{ item.is_certified ? "取消认证" : "认证" }}</button>
                  <button v-if="item.is_active" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.channel_id" @click="deactivate(item)">下架</button>
                  <button v-else type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="activate(item)">上架</button>
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
