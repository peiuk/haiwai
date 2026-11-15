<script setup lang="ts">
// 留言管理：搜索、按状态筛选、删除 / 恢复。
import { ref } from "vue";
import { fmtRelativeTime } from "../utils/time";
import AdminPager from "./AdminPager.vue";
import { STATUS_LABELS, statusTone } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  comment_id: string;
  body: string;
  has_image: boolean;
  status: string;
  author_name: string;
  room_name: string;
  created_at: string;
};

const q = ref("");
const status = ref("");
const { items, total, page, pageSize, loading, error, busy, load, search, go, act } = useAdminList<Row>(
  "/api/v1/admin/comments",
  () => ({ q: q.value, status: status.value }),
);

function setStatus(item: Row, action: "remove" | "restore"): Promise<void> {
  return act(item.comment_id, `/api/v1/admin/comments/${item.comment_id}/status`, { action }, action === "remove" ? "已删除" : "已恢复");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>留言管理</h1>
      <p>只有被管理员删除的留言可以恢复</p>
    </header>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="按留言内容搜索" placeholder="留言内容" />
      <select v-model="status" class="input" aria-label="按状态筛选" @change="search">
        <option value="">全部状态</option>
        <option value="published">已发布</option>
        <option value="pending">待审</option>
        <option value="rejected">已拒绝</option>
        <option value="removed">已删除</option>
      </select>
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的留言。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>留言</th><th>作者</th><th>所在房间</th><th>状态</th><th>时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.comment_id">
              <td class="adm-wide">
                {{ item.body || "（只有图片的留言）" }}
                <span v-if="item.has_image && item.body" class="adm-sub">带图片</span>
              </td>
              <td class="adm-nowrap">{{ item.author_name || "—" }}</td>
              <td class="adm-nowrap">{{ item.room_name || "—" }}</td>
              <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
              <td class="adm-nowrap">{{ fmtRelativeTime(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="item.status === 'removed'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.comment_id" @click="setStatus(item, 'restore')">恢复</button>
                  <button v-else-if="item.status !== 'rejected'" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.comment_id" @click="setStatus(item, 'remove')">删除</button>
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
