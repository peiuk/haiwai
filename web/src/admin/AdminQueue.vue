<script setup lang="ts">
// 举报（mode=reports）与待审核（mode=review）共用一份队列数据。
import { ref } from "vue";
import { RouterLink } from "vue-router";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import { TARGET_LABELS, exact, when } from "./shared";
import { useAdminAction } from "./useAdminList";

const props = defineProps<{ mode: "reports" | "review" }>();

type Queue = {
  contents: { content_id: string; title: string; summary: string; author_name: string; created_at: string }[];
  comments: { comment_id: string; body: string; author_name: string; created_at: string }[];
  channels: { channel_id: string; name: string; owner_name: string; created_at: string }[];
  cases: {
    case_id: string;
    target_type: "content" | "comment" | "channel" | "user";
    target_id: string | null;
    target_label: string;
    reason: string;
    detail: string;
    reporter_name: string;
    created_at: string;
  }[];
};
type Kind = "" | "comments/" | "channels/" | "cases/";
const CASE_REMOVE = { content: "下架", comment: "删除", channel: "下架", user: "封禁" };

const queue = ref<Queue | null>(null);
const error = ref("");

async function load(): Promise<void> {
  error.value = "";
  try {
    queue.value = await adminRequest<Queue>("/api/v1/admin/queue");
  } catch (err) {
    error.value = toMessage(err);
  }
}
const { busy, act, ask } = useAdminAction(load);
void load();

function path(kind: Kind, id: string): string {
  return `/api/v1/moderation/${kind}${id}/decision`;
}

// 通过 / 驳回不改动内容，直接提交；拒绝、下架、封禁先确认并可填理由。
function approve(kind: Kind, id: string, decision: "approve" | "dismiss", done: string): Promise<void> {
  return act(id, path(kind, id), { decision }, done);
}

function reject(kind: Kind, id: string, decision: "reject" | "remove", label: string, what: string): Promise<void> {
  return ask(
    { title: `${label}${what}？`, confirmLabel: label, danger: true, reason: true },
    id,
    path(kind, id),
    (note) => ({ decision, note }),
    `已${label}`,
  );
}

// 举报对象在后台有详情页的才给链接（帖子、用户）
function targetLink(item: Queue["cases"][number]): string {
  if (!item.target_id) return "";
  if (item.target_type === "content") return `/admin/contents/${item.target_id}`;
  if (item.target_type === "user") return `/admin/users/${item.target_id}`;
  return "";
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>{{ props.mode === "reports" ? "举报" : "待审核" }}</h1>
      <p>{{ props.mode === "reports" ? "用户举报的帖子、留言、房间和账号" : "新用户的头几条帖子、留言和新建房间需要先审" }}</p>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <template v-if="queue && props.mode === 'reports'">
      <section class="adm-panel">
        <p v-if="!queue.cases.length" class="adm-empty">没有未处理的举报。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead>
              <tr><th>被举报对象</th><th>理由</th><th>举报人</th><th>时间</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.cases" :key="item.case_id">
                <td class="adm-wide">
                  <span class="tag tag--warn">{{ TARGET_LABELS[item.target_type] }}</span>
                  <RouterLink v-if="targetLink(item)" :to="targetLink(item)">{{ item.target_label }}</RouterLink>
                  <template v-else>{{ item.target_label }}</template>
                </td>
                <td class="adm-wide">{{ item.reason }}<span v-if="item.detail" class="adm-sub">{{ item.detail }}</span></td>
                <td class="adm-nowrap">{{ item.reporter_name || "游客" }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
                <td>
                  <div class="adm-actions">
                    <button type="button" class="btn btn--danger btn--sm" :disabled="busy === item.case_id" @click="reject('cases/', item.case_id, 'remove', CASE_REMOVE[item.target_type], `这个${TARGET_LABELS[item.target_type]}`)">{{ CASE_REMOVE[item.target_type] }}</button>
                    <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.case_id" @click="approve('cases/', item.case_id, 'dismiss', '已驳回举报')">驳回</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>

    <template v-if="queue && props.mode === 'review'">
      <section class="adm-panel">
        <h2>帖子（{{ queue.contents.length }}）</h2>
        <p v-if="!queue.contents.length" class="adm-empty">没有待审的帖子。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead>
              <tr><th>标题与内容</th><th>作者</th><th>时间</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.contents" :key="item.content_id">
                <td class="adm-wide">
                  <RouterLink :to="`/admin/contents/${item.content_id}`"><strong>{{ item.title }}</strong></RouterLink>
                  <span v-if="item.summary" class="adm-sub">{{ item.summary }}</span>
                </td>
                <td class="adm-nowrap">{{ item.author_name }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
                <td>
                  <div class="adm-actions">
                    <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.content_id" @click="approve('', item.content_id, 'approve', '已通过')">通过</button>
                    <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="reject('', item.content_id, 'reject', '拒绝', '这条帖子')">拒绝</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>留言（{{ queue.comments.length }}）</h2>
        <p v-if="!queue.comments.length" class="adm-empty">没有待审的留言。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead>
              <tr><th>留言</th><th>作者</th><th>时间</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.comments" :key="item.comment_id">
                <td class="adm-wide">{{ item.body || "（只有图片的留言）" }}</td>
                <td class="adm-nowrap">{{ item.author_name }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
                <td>
                  <div class="adm-actions">
                    <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.comment_id" @click="approve('comments/', item.comment_id, 'approve', '已通过')">通过</button>
                    <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.comment_id" @click="reject('comments/', item.comment_id, 'reject', '拒绝', '这条留言')">拒绝</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>房间（{{ queue.channels.length }}）</h2>
        <p v-if="!queue.channels.length" class="adm-empty">没有待审的房间。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead>
              <tr><th>房间名</th><th>创建者</th><th>时间</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.channels" :key="item.channel_id">
                <td class="adm-wide"><strong>{{ item.name }}</strong></td>
                <td class="adm-nowrap">{{ item.owner_name }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
                <td>
                  <div class="adm-actions">
                    <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.channel_id" @click="approve('channels/', item.channel_id, 'approve', '已通过')">通过</button>
                    <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="reject('channels/', item.channel_id, 'reject', '拒绝', '这个房间')">拒绝</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </template>
  </div>
</template>
