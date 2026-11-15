<script setup lang="ts">
// 用户详情：资料、最近发帖、被举报记录、处理记录。
import { ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import { ACTION_LABELS, STATUS_LABELS, TYPE_LABELS, exact, statusTone, when, type CaseRow, type HistoryRow } from "./shared";
import { useAdminAction } from "./useAdminList";

type Detail = {
  user_id: string;
  display_name: string;
  handle: string;
  email: string;
  city_label: string;
  phone_verified: boolean;
  status: string;
  is_admin: boolean;
  created_at: string;
  post_count: number;
  comment_count: number;
  posts: { content_id: string; title: string; type: string; status: string; created_at: string }[];
  cases: CaseRow[];
  history: HistoryRow[];
};

const id = String(useRoute().params.id);
const detail = ref<Detail | null>(null);
const error = ref("");

async function load(): Promise<void> {
  error.value = "";
  try {
    detail.value = await adminRequest<Detail>(`/api/v1/admin/users/${id}`);
  } catch (err) {
    error.value = toMessage(err);
  }
}
const { busy, act, ask } = useAdminAction(load);
void load();

function suspend(): Promise<void> {
  return ask(
    { title: `封禁「${detail.value?.display_name}」？`, message: "封禁后对方立即无法登录和使用，之后可以解封。", confirmLabel: "封禁", danger: true, reason: true },
    id,
    `/api/v1/admin/users/${id}/status`,
    (reason) => ({ status: "suspended", reason }),
    "已封禁",
  );
}
function setAdmin(grant: boolean): Promise<void> {
  const name = detail.value?.display_name;
  return ask(
    grant
      ? { title: `把「${name}」设为管理员？`, message: "管理员可以登录后台，处理举报、下架内容、封禁用户。", confirmLabel: "设为管理员", reason: true }
      : { title: `撤销「${name}」的管理员权限？`, message: "撤销后对方立即无法使用后台。", confirmLabel: "撤销", danger: true, reason: true },
    id,
    `/api/v1/admin/users/${id}/admin`,
    (reason) => ({ is_admin: grant, reason }),
    grant ? "已设为管理员" : "已撤销管理员",
  );
}
function activate(): Promise<void> {
  return act(id, `/api/v1/admin/users/${id}/status`, { status: "active" }, "已解封");
}
</script>

<template>
  <div>
    <RouterLink class="adm-back" to="/admin/users">返回用户列表</RouterLink>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <template v-if="detail">
      <header class="adm-detail-head">
        <h1>{{ detail.display_name }}</h1>
        <span class="tag" :class="statusTone(detail.status)">{{ STATUS_LABELS[detail.status] ?? detail.status }}</span>
        <span v-if="detail.is_admin" class="tag tag--link">管理员</span>
        <a class="btn btn--ghost btn--sm" :href="`/user/${detail.user_id}`" target="_blank" rel="noopener">在前台查看</a>
        <button v-if="detail.is_admin" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setAdmin(false)">撤销管理员</button>
        <button v-else-if="detail.status === 'active'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setAdmin(true)">设为管理员</button>
        <button v-if="detail.status === 'suspended'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="activate">解封</button>
        <button v-else-if="detail.status === 'active' && !detail.is_admin" type="button" class="btn btn--danger btn--sm" :disabled="!!busy" @click="suspend">封禁</button>
      </header>

      <section class="adm-panel">
        <dl class="adm-facts">
          <div><dt>邮箱</dt><dd>{{ detail.email }}</dd></div>
          <div><dt>账号名</dt><dd>{{ detail.handle ? `@${detail.handle}` : "—" }}</dd></div>
          <div><dt>城市</dt><dd>{{ detail.city_label || "—" }}</dd></div>
          <div><dt>手机验证</dt><dd>{{ detail.phone_verified ? "已验证" : "未验证" }}</dd></div>
          <div><dt>注册时间</dt><dd :title="when(detail.created_at)">{{ exact(detail.created_at) }}</dd></div>
          <div><dt>发帖 / 留言</dt><dd>{{ detail.post_count }} / {{ detail.comment_count }}</dd></div>
        </dl>
      </section>

      <section class="adm-panel">
        <h2>最近发布</h2>
        <p v-if="!detail.posts.length" class="adm-empty">还没有发布过内容。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead><tr><th>标题</th><th>类型</th><th>状态</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.posts" :key="item.content_id">
                <td class="adm-wide"><RouterLink :to="`/admin/contents/${item.content_id}`">{{ item.title }}</RouterLink></td>
                <td class="adm-nowrap">{{ TYPE_LABELS[item.type] ?? item.type }}</td>
                <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>被举报记录（{{ detail.cases.length }}）</h2>
        <p v-if="!detail.cases.length" class="adm-empty">没有人举报过这个账号。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead><tr><th>理由</th><th>举报人</th><th>处理结果</th><th>时间</th></tr></thead>
            <tbody>
              <tr v-for="item in detail.cases" :key="item.case_id">
                <td class="adm-wide">{{ item.reason }}<span v-if="item.detail" class="adm-sub">{{ item.detail }}</span></td>
                <td class="adm-nowrap">{{ item.reporter_name || "游客" }}</td>
                <td class="adm-nowrap">{{ item.status === "open" ? "未处理" : item.decision === "remove" ? "已封禁" : "已驳回" }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>处理记录</h2>
        <p v-if="!detail.history.length" class="adm-empty">还没有针对这个账号的操作。</p>
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
