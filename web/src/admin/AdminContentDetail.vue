<script setup lang="ts">
// 内容详情：全文、图片、举报记录、处理记录；待审的可以直接在这里通过 / 拒绝。
import { ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import { ACTION_LABELS, STATUS_LABELS, TYPE_LABELS, exact, statusTone, when, type CaseRow, type HistoryRow } from "./shared";
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

      <section class="adm-panel">
        <h2>举报记录（{{ detail.cases.length }}）</h2>
        <p v-if="!detail.cases.length" class="adm-empty">没有人举报过这条内容。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead><tr><th>理由</th><th>举报人</th><th>处理结果</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.cases" :key="item.case_id">
                <td class="adm-wide">{{ item.reason }}<span v-if="item.detail" class="adm-sub">{{ item.detail }}</span></td>
                <td class="adm-nowrap">{{ item.reporter_name || "游客" }}</td>
                <td class="adm-nowrap">{{ item.status === "open" ? "未处理" : item.decision === "remove" ? "已下架" : "已驳回" }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>处理记录</h2>
        <p v-if="!detail.history.length" class="adm-empty">还没有人处理过这条内容。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead><tr><th>动作</th><th>操作人</th><th>理由</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="(item, index) in detail.history" :key="index">
                <td class="adm-nowrap">{{ ACTION_LABELS[item.action] ?? item.action }}</td>
                <td class="adm-nowrap">{{ item.actor_name || "系统 / 游客" }}</td>
                <td class="adm-wide">{{ item.detail || "—" }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
