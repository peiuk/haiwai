<script setup lang="ts">
// 内容详情：全文、图片、举报记录、处理记录；待审的可以直接在这里通过 / 拒绝。
import { ref } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { confirmAction } from "./confirm";
import { adminRequest } from "./adminApi";
import AdminCaseTable from "./AdminCaseTable.vue";
import AdminHistoryTable from "./AdminHistoryTable.vue";
import { STATUS_LABELS, TYPE_LABELS, exact, statusTone, when, type CaseRow, type HistoryRow } from "./shared";
import { useAdminAction } from "./useAdminList";

type Detail = {
  content_id: string;
  title: string;
  body: string;
  type: string;
  status: string;
  author_id: string | null;
  author_name: string;
  channel_name: string;
  image_urls: string[];
  has_video: boolean;
  canonical_url: string;
  view_count: number;
  comment_count: number;
  featured: boolean;
  created_at: string;
  cases: CaseRow[];
  history: HistoryRow[];
};

const id = String(useRoute().params.id);
const router = useRouter();
const toast = useToastStore();
const detail = ref<Detail | null>(null);
const error = ref("");

async function load(): Promise<void> {
  error.value = "";
  try {
    detail.value = await adminRequest<Detail>(`/api/v1/admin/contents/${id}`);
  } catch (err) {
    error.value = toMessage(err);
  }
}
const { busy, act, ask } = useAdminAction(load);
void load();

function approve(): Promise<void> {
  return act(id, `/api/v1/moderation/${id}/decision`, { decision: "approve" }, "已通过");
}
function reject(): Promise<void> {
  return ask({ title: "拒绝这条帖子？", confirmLabel: "拒绝", danger: true, reason: true }, id, `/api/v1/moderation/${id}/decision`, (note) => ({ decision: "reject", note }), "已拒绝");
}
function remove(): Promise<void> {
  return ask(
    { title: "下架这条内容？", message: "下架后前台不再显示，之后可以恢复。", confirmLabel: "下架", danger: true, reason: true },
    id,
    `/api/v1/admin/contents/${id}/status`,
    (reason) => ({ action: "remove", reason }),
    "已下架",
  );
}
// 删除后这一页没有东西可显示了，所以不走通用的"提交后刷新"，直接回列表。
async function destroy(): Promise<void> {
  const reason = await confirmAction({
    title: "彻底删除这条内容？",
    message: "连同它的留言、点赞收藏和图片视频都会删掉，不能恢复。只想让它不显示的话请用「下架」。",
    confirmLabel: "彻底删除",
    danger: true,
    reason: true,
  });
  if (reason === null) return;
  try {
    await adminRequest(`/api/v1/admin/contents/${id}/delete`, jsonBody({ reason }));
    toast.show("已删除");
    await router.replace("/admin/posts");
  } catch (err) {
    toast.show(toMessage(err));
  }
}
function restore(): Promise<void> {
  return act(id, `/api/v1/admin/contents/${id}/status`, { action: "restore" }, "已恢复");
}
function feature(): Promise<void> {
  const on = !detail.value?.featured;
  return act(id, `/api/v1/admin/contents/${id}/featured`, { featured: on }, on ? "已设为精选" : "已取消精选");
}
</script>

<template>
  <div>
    <RouterLink class="adm-back" to="/admin/posts">返回帖子列表</RouterLink>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <template v-if="detail">
      <header class="adm-detail-head">
        <h1>{{ detail.title }}</h1>
        <span class="tag" :class="statusTone(detail.status)">{{ STATUS_LABELS[detail.status] ?? detail.status }}</span>
        <span v-if="detail.featured" class="tag tag--link">精选</span>
        <template v-if="detail.status === 'pending'">
          <button type="button" class="btn btn--primary btn--sm" :disabled="!!busy" @click="approve">通过</button>
          <button type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="reject">拒绝</button>
        </template>
        <template v-else-if="detail.status === 'published'">
          <a class="btn btn--ghost btn--sm" :href="`/content/${detail.content_id}`" target="_blank" rel="noopener">在前台查看</a>
          <button type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="feature">{{ detail.featured ? "取消精选" : "设为精选" }}</button>
          <button type="button" class="btn btn--danger btn--sm" :disabled="!!busy" @click="remove">下架</button>
        </template>
        <button v-else-if="detail.status === 'deleted'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="restore">恢复</button>
        <button type="button" class="btn btn--ghost btn--sm" :disabled="!!busy" @click="destroy">删除</button>
      </header>

      <section class="adm-panel">
        <dl class="adm-facts">
          <div><dt>类型</dt><dd>{{ TYPE_LABELS[detail.type] ?? detail.type }}</dd></div>
          <div>
            <dt>作者 / 来源</dt>
            <dd>
              <RouterLink v-if="detail.author_id" :to="`/admin/users/${detail.author_id}`">{{ detail.author_name }}</RouterLink>
              <template v-else>{{ detail.author_name || "—" }}</template>
            </dd>
          </div>
          <div><dt>频道</dt><dd>{{ detail.channel_name || "—" }}</dd></div>
          <div><dt>发布时间</dt><dd :title="when(detail.created_at)">{{ exact(detail.created_at) }}</dd></div>
          <div><dt>浏览 / 留言</dt><dd>{{ detail.view_count }} / {{ detail.comment_count }}</dd></div>
          <div v-if="detail.canonical_url"><dt>原文链接</dt><dd><a :href="detail.canonical_url" target="_blank" rel="noopener">{{ detail.canonical_url }}</a></dd></div>
        </dl>
      </section>

      <section class="adm-panel">
        <h2>正文</h2>
        <p class="adm-prose">{{ detail.body || "（没有正文）" }}</p>
        <div v-if="detail.image_urls.length" class="adm-images">
          <a v-for="url in detail.image_urls" :key="url" :href="url" target="_blank" rel="noopener"><img :src="url" alt="帖子配图" loading="lazy" /></a>
        </div>
        <p v-if="detail.has_video" class="adm-empty">这条内容带视频，请在前台查看。</p>
      </section>

      <AdminCaseTable title="举报记录" :cases="detail.cases" empty="没有人举报过这条内容。" removed-label="已下架" />
      <AdminHistoryTable :history="detail.history" empty="还没有人处理过这条内容。" />
    </template>
  </div>
</template>
