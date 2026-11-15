<script setup lang="ts">
// 留言管理：搜索、按状态筛选、删除 / 恢复。
import { ref } from "vue";
import { RouterLink } from "vue-router";
import AdminPager from "./AdminPager.vue";
import { STATUS_LABELS, exact, statusTone, when } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  comment_id: string;
  body: string;
  has_image: boolean;
  status: string;
  author_name: string;
  room_name: string;
  content_id: string | null;
  content_title: string;
  created_at: string;
};

const q = ref("");
const status = ref("");
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/comments",
  () => ({ q: q.value, status: status.value }),
);

function remove(item: Row): Promise<void> {
  return ask(
    { title: "删除这条留言？", message: "删除后前台不再显示，之后可以恢复。", confirmLabel: "删除", danger: true, reason: true },
    item.comment_id,
    `/api/v1/admin/comments/${item.comment_id}/status`,
    (reason) => ({ action: "remove", reason }),
    "已删除",
  );
}

function restore(item: Row): Promise<void> {
  return act(item.comment_id, `/api/v1/admin/comments/${item.comment_id}/status`, { action: "restore" }, "已恢复");
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
            <tr><th>留言</th><th>作者</th><th>所在位置</th><th>状态</th><th>时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.comment_id">
              <td class="adm-wide">
                {{ item.body || "（只有图片的留言）" }}
                <span v-if="item.has_image && item.body" class="adm-sub">带图片</span>
              </td>
              <td class="adm-nowrap">{{ item.author_name || "—" }}</td>
              <td>
                {{ item.room_name || "—" }}
                <RouterLink v-if="item.content_id && item.content_title" class="adm-sub" :to="`/admin/contents/${item.content_id}`">{{ item.content_title }}</RouterLink>
              </td>
              <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="item.status === 'removed'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.comment_id" @click="restore(item)">恢复</button>
                  <button v-else-if="item.status !== 'rejected'" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.comment_id" @click="remove(item)">删除</button>
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
