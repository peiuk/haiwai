<script setup lang="ts">
// 用户详情：资料、最近发帖、被举报记录、处理记录。
import { ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminDownload, adminMe, adminRequest } from "./adminApi";
import AdminCaseTable from "./AdminCaseTable.vue";
import AdminHistoryTable from "./AdminHistoryTable.vue";
import { confirmAction } from "./confirm";
import { STATUS_LABELS, TYPE_LABELS, exact, statusTone, suspendBody, when, type CaseRow, type HistoryRow } from "./shared";
import { useAdminAction } from "./useAdminList";

type Detail = {
  user_id: string;
  display_name: string;
  handle: string;
  email: string;
  avatar_key: string;
  city_label: string;
  bio: string;
  phone_verified: boolean;
  status: string;
  suspended_until: string | null;
  suspend_reason: string;
  is_admin: boolean;
  is_super: boolean;
  two_factor: boolean;
  deleted: boolean;
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

// ---- 重置密码链接：用户忘记密码时，管理员生成一次性链接发给对方 ----
const toast = useToastStore();
const resetLink = ref("");

async function makeResetLink(): Promise<void> {
  const ok = await confirmAction({
    title: `给「${detail.value?.display_name}」生成重置密码链接？`,
    message: "链接 24 小时内有效、只能用一次；之前生成但没用的链接会作废。请通过你确认是本人的渠道发给对方。",
    confirmLabel: "生成链接",
  });
  if (ok === null) return;
  try {
    const result = await adminRequest<{ token: string }>(`/api/v1/admin/users/${id}/reset-link`, { method: "POST" });
    resetLink.value = `${window.location.origin}/reset-password?token=${encodeURIComponent(result.token)}`;
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function copyResetLink(): Promise<void> {
  try {
    await navigator.clipboard.writeText(resetLink.value);
    toast.show("已复制");
  } catch {
    toast.show("复制失败，请手动选中链接复制");
  }
}

function suspend(): Promise<void> {
  return ask(
    {
      title: `封禁「${detail.value?.display_name}」？`,
      message: "封禁后对方立即无法登录和使用；限时封禁到期自动解封，也可以提前手动解封。",
      confirmLabel: "封禁",
      danger: true,
      reason: true,
      days: true,
      checkbox: "同时下架对方发过的全部帖子和留言（刷广告的账号用）",
    },
    id,
    `/api/v1/admin/users/${id}/status`,
    suspendBody,
    "已封禁",
  );
}

const ROLE_ASK = {
  moderator: { label: "管理员", message: "管理员可以登录后台，审核内容、处理举报、下架内容、封禁用户；不能彻底删除、管理频道和国家、任免管理员。" },
  super: { label: "超级管理员", message: "超级管理员可以做后台的全部操作，包括彻底删除内容、删除频道、任免其他管理员、导出数据。请只给完全信任的人。" },
};

function setRole(role: "none" | "moderator" | "super"): Promise<void> {
  const name = detail.value?.display_name;
  return ask(
    role === "none"
      ? { title: `撤销「${name}」的管理员权限？`, message: "撤销后对方立即无法使用后台。", confirmLabel: "撤销", danger: true, reason: true }
      : { title: `把「${name}」设为${ROLE_ASK[role].label}？`, message: ROLE_ASK[role].message, confirmLabel: `设为${ROLE_ASK[role].label}`, reason: true },
    id,
    `/api/v1/admin/users/${id}/admin`,
    (reason) => ({ is_admin: role !== "none", is_super: role === "super", reason }),
    role === "none" ? "已撤销管理员" : `已设为${ROLE_ASK[role].label}`,
  );
}

// ---- 用户数据请求：用户有权拿到、删除自己的数据 ----
async function exportData(): Promise<void> {
  try {
    await adminDownload(`/api/v1/admin/users/${id}/export`, `user-${id}.json`);
  } catch (err) {
    toast.show(toMessage(err));
  }
}

function erase(): Promise<void> {
  const email = detail.value?.email ?? "";
  return ask(
    {
      title: `注销「${detail.value?.display_name}」的账号？`,
      message: "抹掉对方的个人资料、下架全部帖子、删掉上传的图片视频，不能恢复。只在用户本人要求删除数据时使用；想让对方不能用请用「封禁」。",
      confirmLabel: "注销账号",
      danger: true,
      reason: true,
      mustType: email,
    },
    id,
    `/api/v1/admin/users/${id}/erase`,
    (reason) => ({ confirm_email: email, reason }),
    "账号已注销",
  );
}
function removeAvatar(): Promise<void> {
  return ask(
    {
      title: `移除「${detail.value?.display_name}」的头像？`,
      message: "图片会被删除，对方回到首字色块头像，并收到一条通知。对方可以重新上传。",
      confirmLabel: "移除头像",
      danger: true,
      reason: true,
    },
    id,
    `/api/v1/admin/users/${id}/avatar/remove`,
    (reason) => ({ reason }),
    "头像已移除",
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
        <span v-if="detail.is_admin" class="tag tag--link">{{ detail.is_super ? "超级管理员" : "管理员" }}</span>
        <span v-if="detail.is_admin && !detail.two_factor" class="tag tag--warn">未开两步验证</span>
        <span v-if="detail.deleted" class="tag tag--danger">已注销</span>
        <template v-if="!detail.deleted">
          <a class="btn btn--ghost btn--sm" :href="`/user/${detail.user_id}`" target="_blank" rel="noopener">在前台查看</a>
          <button v-if="detail.status === 'suspended'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="activate">解封</button>
          <button v-else-if="detail.status === 'active' && !detail.is_admin" type="button" class="btn btn--danger btn--sm" :disabled="!!busy" @click="suspend">封禁</button>
        </template>
      </header>

      <p v-if="detail.status === 'suspended'" class="notice notice--danger">
        封禁{{ detail.suspended_until ? `到 ${exact(detail.suspended_until)}，到期自动解封` : "没有期限，要手动解封" }}。{{ detail.suspend_reason ? `原因：${detail.suspend_reason}` : "" }}
      </p>

      <!-- 只有超级管理员能做的事：能接管账号、改权限、动用户数据 -->
      <section v-if="adminMe.is_super && !detail.deleted" class="adm-panel">
        <h2>账号与权限（仅超级管理员）</h2>
        <div class="adm-batch">
          <button type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="makeResetLink">重置密码链接</button>
          <template v-if="detail.user_id !== adminMe.user_id">
            <button v-if="!detail.is_admin && detail.status === 'active'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setRole('moderator')">设为管理员</button>
            <button v-if="detail.is_super" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setRole('moderator')">降为管理员</button>
            <button v-if="!detail.is_super && detail.status === 'active'" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setRole('super')">设为超级管理员</button>
            <button v-if="detail.is_admin" type="button" class="btn btn--outline btn--sm" :disabled="!!busy" @click="setRole('none')">撤销管理员</button>
          </template>
          <button type="button" class="btn btn--ghost btn--sm" title="用户本人要求查看自己的数据时用" @click="exportData">导出此人的数据</button>
          <button v-if="!detail.is_admin" type="button" class="btn btn--ghost btn--sm" :disabled="!!busy" @click="erase">代为注销账号</button>
        </div>
      </section>

      <section v-if="resetLink" class="adm-panel">
        <h2>重置密码链接（只显示这一次，离开页面后无法再看到）</h2>
        <div class="adm-form">
          <div class="field">
            <label for="adm-reset-link">把这个链接发给用户本人</label>
            <input id="adm-reset-link" class="input" :value="resetLink" readonly @focus="($event.target as HTMLInputElement).select()" />
          </div>
          <div class="adm-form-actions">
            <button type="button" class="btn btn--primary" @click="copyResetLink">复制链接</button>
          </div>
        </div>
      </section>

      <section class="adm-panel">
        <dl class="adm-facts">
          <div v-if="detail.avatar_key">
            <dt>头像</dt>
            <dd>
              <a :href="`/api/v1/uploads/${detail.avatar_key}`" target="_blank" rel="noopener"><img class="adm-avatar" :src="`/api/v1/uploads/${detail.avatar_key}`" alt="用户上传的头像" /></a>
              <button type="button" class="btn btn--danger btn--sm" :disabled="!!busy" @click="removeAvatar">移除头像</button>
            </dd>
          </div>
          <div><dt>邮箱</dt><dd>{{ detail.email }}</dd></div>
          <div><dt>账号名</dt><dd>{{ detail.handle ? `@${detail.handle}` : "—" }}</dd></div>
          <div><dt>城市</dt><dd>{{ detail.city_label || "—" }}</dd></div>
          <div><dt>个人介绍</dt><dd data-ugc>{{ detail.bio || "—" }}</dd></div>
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

      <AdminCaseTable title="被举报记录" :cases="detail.cases" empty="没有人举报过这个账号。" removed-label="已封禁" />
      <AdminHistoryTable :history="detail.history" empty="还没有针对这个账号的操作。" />
    </template>
  </div>
</template>
