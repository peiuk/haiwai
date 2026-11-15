<script setup lang="ts">
// 内容管理表格：帖子 / 分类信息 / 新闻公告 三个菜单共用，按 types 区分。
import { computed, ref } from "vue";
import { fmtRelativeTime } from "../utils/time";
import AdminPager from "./AdminPager.vue";
import { STATUS_LABELS, TYPE_LABELS, statusTone } from "./shared";
import { useAdminList } from "./useAdminList";

const props = defineProps<{ types: string; title: string }>();

type Row = {
  content_id: string;
  title: string;
  type: string;
  status: string;
  author_name: string;
  channel_name: string;
  view_count: number;
  created_at: string;
};

const q = ref("");
const status = ref("");
const showType = computed(() => props.types.includes(","));
const { items, total, page, pageSize, loading, error, busy, load, search, go, act } = useAdminList<Row>(
  "/api/v1/admin/contents",
  () => ({ q: q.value, status: status.value, type: props.types }),
);

function setStatus(item: Row, action: "remove" | "restore"): Promise<void> {
  return act(item.content_id, `/api/v1/admin/contents/${item.content_id}/status`, { action }, action === "remove" ? "已下架" : "已恢复");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>{{ props.title }}</h1>
      <p>下架后前台不再显示；被管理员下架的可以恢复</p>
    </header>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="按标题搜索" placeholder="标题关键词" />
      <select v-model="status" class="input" aria-label="按状态筛选" @change="search">
        <option value="">全部状态</option>
        <option value="published">已发布</option>
        <option value="pending">待审</option>
        <option value="rejected">已拒绝</option>
        <option value="deleted">已下架</option>
      </select>
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的内容。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr>
              <th>标题</th><th v-if="showType">类型</th><th>作者 / 来源</th><th>频道</th><th>状态</th><th class="adm-num">浏览</th><th>发布时间</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.content_id">
              <td class="adm-wide">
                <a v-if="item.status === 'published'" :href="`/content/${item.content_id}`" target="_blank" rel="noopener">{{ item.title }}</a>
                <template v-else>{{ item.title }}</template>
              </td>
              <td v-if="showType" class="adm-nowrap">{{ TYPE_LABELS[item.type] ?? item.type }}</td>
              <td class="adm-nowrap">{{ item.author_name || "—" }}</td>
              <td class="adm-nowrap">{{ item.channel_name || "—" }}</td>
              <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
              <td class="adm-num">{{ item.view_count }}</td>
              <td class="adm-nowrap">{{ fmtRelativeTime(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="item.status === 'deleted'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="setStatus(item, 'restore')">恢复</button>
                  <button v-else type="button" class="btn btn--danger btn--sm" :disabled="busy === item.content_id" @click="setStatus(item, 'remove')">下架</button>
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
