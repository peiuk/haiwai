<script setup lang="ts">
// 待审推送：房主把房间里的帖子推到官方频道，通过后才会出现在频道里。
import AdminPager from "./AdminPager.vue";
import { exact, when } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  content_id: string;
  title: string;
  room_id: string;
  room_name: string;
  channel_id: string;
  channel_name: string;
  owner_name: string;
  pushed_at: string;
};

const { items, total, page, pageSize, loading, error, busy, load, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/pushes",
  () => ({ status: "pending" }),
);

const url = (item: Row): string => `/api/v1/admin/pushes/${item.content_id}/decision`;

function approve(item: Row): Promise<void> {
  return act(item.content_id, url(item), { decision: "approve" }, "已通过，帖子进入频道");
}

function reject(item: Row): Promise<void> {
  return ask(
    { title: `拒绝「${item.title}」推送到「${item.channel_name}」？`, message: "房主会收到通知，之后可以改推别的频道。", confirmLabel: "拒绝", danger: true, reason: true },
    item.content_id,
    url(item),
    (reason) => ({ decision: "reject", reason }),
    "已拒绝",
  );
}
</script>

<template>
  <section class="adm-panel">
    <h2>推送到频道（{{ total }}）</h2>
    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>
    <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有等待审核的推送。" }}</p>
    <div v-else class="adm-scroll">
      <table class="adm-table">
        <thead>
          <tr><th>帖子</th><th>来自房间</th><th>推到频道</th><th>房主</th><th>时间</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="item in items" :key="item.content_id">
            <td><strong>{{ item.title || "（无标题）" }}</strong></td>
            <td>{{ item.room_name }}</td>
            <td>{{ item.channel_name }}</td>
            <td class="adm-nowrap">{{ item.owner_name }}</td>
            <td class="adm-nowrap" :title="exact(item.pushed_at)">{{ when(item.pushed_at) }}</td>
            <td>
              <div class="adm-actions">
                <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.content_id" @click="approve(item)">通过</button>
                <button type="button" class="btn btn--danger btn--sm" :disabled="busy === item.content_id" @click="reject(item)">拒绝</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <AdminPager :page="page" :total="total" :page-size="pageSize" @go="go" />
  </section>
</template>
