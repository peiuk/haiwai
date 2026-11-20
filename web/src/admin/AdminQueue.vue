<script setup lang="ts">
// 举报（mode=reports）与待审核（mode=review）共用一份队列数据。
import { onUnmounted, ref } from "vue";
import { RouterLink } from "vue-router";
import { ApiRequestError, jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { ADMIN_CHANGED, adminRequest } from "./adminApi";
import { confirmAction } from "./confirm";
import { TARGET_LABELS, exact, overdue, when } from "./shared";
import { useAdminAction } from "./useAdminList";
import ReviewSwitch from "./ReviewSwitch.vue";
import AdminPushes from "./AdminPushes.vue";

const props = defineProps<{ mode: "reports" | "review" }>();

type Queue = {
  contents: {
    content_id: string;
    title: string;
    summary: string;
    author_name: string;
    created_at: string;
    ai_draft: boolean;
    ai_check: boolean;
    source_url: string | null;
    claimed_by: string; // 别的管理员正在处理时是对方的名字，否则空串
  }[];
  comments: { comment_id: string; body: string; author_name: string; created_at: string; claimed_by: string }[];
  channels: { channel_id: string; name: string; owner_name: string; created_at: string; claimed_by: string }[];
  cases: {
    case_id: string;
    target_type: "content" | "comment" | "channel" | "user";
    target_id: string | null;
    target_label: string;
    reason: string;
    detail: string;
    reporter_name: string;
    created_at: string;
    claimed_by: string;
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

// 抓取 GOV.UK 和 BBC 最新资讯，AI 写成中文稿后放进下面的待审列表。要两三分钟，后台在服务器上跑，这里每 5 秒问一次进度
const NEWS_API = "/api/v1/admin/ingest/news";
type NewsStatus = { running: boolean; ok: boolean | null; detail: string | null };
const fetching = ref(false);
const fetchNote = ref("");
let pollTimer: ReturnType<typeof setTimeout> | undefined;

async function pollNews(): Promise<void> {
  try {
    const status = await adminRequest<NewsStatus>(NEWS_API);
    if (status.running) {
      fetching.value = true;
      fetchNote.value = "正在抓取并让 AI 写中文稿，大约两三分钟；可以先去处理别的，回到这页会接着显示进度。";
      pollTimer = setTimeout(() => void pollNews(), 5000);
      return;
    }
    if (fetching.value) {
      fetchNote.value = status.detail ?? "";
      await load();
    }
  } catch (err) {
    fetchNote.value = toMessage(err);
  }
  fetching.value = false;
}

async function fetchNews(): Promise<void> {
  if (fetching.value) return;
  fetching.value = true;
  fetchNote.value = "";
  try {
    await adminRequest<NewsStatus>(NEWS_API, { method: "POST" });
  } catch (err) {
    if (!(err instanceof ApiRequestError && err.code === "NEWS_BUSY")) {
      fetchNote.value = toMessage(err);
      fetching.value = false;
      return;
    }
  }
  await pollNews();
}

onUnmounted(() => clearTimeout(pollTimer));
if (props.mode === "review") void pollNews(); // 离开时还在抓，回来接着显示

function path(kind: Kind, id: string): string {
  return `/api/v1/moderation/${kind}${id}/decision`;
}

const toast = useToastStore();
const CLAIM_TYPE: Record<Kind, string> = { "": "content", "comments/": "comment", "channels/": "channel", "cases/": "case" };

/** 动手之前先认领：别的管理员正在处理这一条就提示并停下，免得两个人审同一条。 */
async function claim(kind: Kind, id: string): Promise<boolean> {
  try {
    await adminRequest("/api/v1/admin/claims", jsonBody({ target_type: CLAIM_TYPE[kind], target_id: id }));
    return true;
  } catch (err) {
    toast.show(toMessage(err));
    void load();
    return false;
  }
}

// ---- 批量审帖：勾选多条后一次通过或拒绝 ----
const selected = ref<string[]>([]);

function toggleAll(checked: boolean): void {
  selected.value = checked ? (queue.value?.contents ?? []).map((item) => item.content_id) : [];
}

async function batch(action: "approve" | "reject"): Promise<void> {
  const count = selected.value.length;
  const reason = action === "reject" ? await confirmAction({ title: `拒绝选中的 ${count} 条帖子？`, confirmLabel: "拒绝", danger: true, reason: true }) : "";
  if (reason === null) return;
  try {
    const result = await adminRequest<{ done: number; failed: { message: string }[] }>(
      "/api/v1/admin/contents/batch",
      jsonBody({ ids: selected.value, action, reason }),
    );
    toast.show(result.failed.length ? `处理了 ${result.done} 条，${result.failed.length} 条没成功：${result.failed[0].message}` : `已处理 ${result.done} 条`);
    selected.value = [];
    window.dispatchEvent(new Event(ADMIN_CHANGED));
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  }
}

// 通过 / 驳回不改动内容，直接提交；拒绝、下架、封禁先确认并可填理由。
async function approve(kind: Kind, id: string, decision: "approve" | "dismiss", done: string): Promise<void> {
  if (await claim(kind, id)) await act(id, path(kind, id), { decision }, done);
}

async function reject(kind: Kind, id: string, decision: "reject" | "remove", label: string, what: string): Promise<void> {
  if (!(await claim(kind, id))) return;
  await ask(
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

    <!-- 发布前审核开关：三类内容各一个，关掉后新发的直接公开（命中敏感词的仍进这里） -->
    <section v-if="props.mode !== 'reports'" class="adm-panel review-switches" aria-label="发布前审核开关">
      <ReviewSwitch kind="post" />
      <ReviewSwitch kind="listing" />
      <ReviewSwitch kind="comment" />
    </section>

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
                  <span v-if="item.claimed_by" class="tag">{{ item.claimed_by }} 处理中</span>
                </td>
                <td class="adm-wide">{{ item.reason }}<span v-if="item.detail" class="adm-sub">{{ item.detail }}</span></td>
                <td class="adm-nowrap">{{ item.reporter_name || "游客" }}</td>
                <td class="adm-nowrap" :title="exact(item.created_at)">
                  {{ when(item.created_at) }}
                  <span v-if="overdue(item.created_at)" class="tag tag--danger">超过 24 小时</span>
                </td>
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
        <div class="adm-actions">
          <button type="button" class="btn btn--outline btn--sm" :disabled="fetching" @click="fetchNews">
            {{ fetching ? "正在抓取并生成…" : "抓取今日资讯" }}
          </button>
          <span class="adm-sub" role="status">{{ fetchNote || "从 GOV.UK 和 BBC 抓最新新闻，AI 写成中文稿后出现在下面（英国的进英国资讯，国际的进国际新闻），通过才会发布。" }}</span>
        </div>
      </section>

      <section class="adm-panel">
        <h2>帖子（{{ queue.contents.length }}）</h2>
        <div v-if="selected.length" class="adm-batch" role="status">
          已选 {{ selected.length }} 条
          <button type="button" class="btn btn--primary btn--sm" @click="batch('approve')">全部通过</button>
          <button type="button" class="btn btn--outline btn--sm" @click="batch('reject')">全部拒绝</button>
          <button type="button" class="btn btn--ghost btn--sm" @click="selected = []">取消选择</button>
        </div>
        <p v-if="!queue.contents.length" class="adm-empty">没有待审的帖子。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead>
              <tr>
                <th><input type="checkbox" aria-label="全选待审帖子" :checked="selected.length === queue.contents.length" @change="toggleAll(($event.target as HTMLInputElement).checked)" /></th>
                <th>标题与内容</th><th>作者</th><th>时间</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in queue.contents" :key="item.content_id">
                <td><input v-model="selected" type="checkbox" :value="item.content_id" :aria-label="`选择「${item.title}」`" /></td>
                <td class="adm-wide">
                  <span v-if="item.claimed_by" class="tag">{{ item.claimed_by }} 处理中</span>
                  <span v-if="overdue(item.created_at)" class="tag tag--danger">超过 24 小时</span>
                  <span v-if="item.ai_draft" class="tag">AI 资讯</span>
                  <span v-if="item.ai_check" class="tag tag--warn" title="中文稿里有原文里找不到的数字，请点「原文」对照">数字待核对</span>
                  <RouterLink :to="`/admin/contents/${item.content_id}`"><strong>{{ item.title }}</strong></RouterLink>
                  <span v-if="item.summary" class="adm-sub">{{ item.summary }}</span>
                  <a v-if="item.source_url" class="adm-sub" :href="item.source_url" target="_blank" rel="noopener noreferrer">原文</a>
                </td>
                <td class="adm-nowrap">{{ item.author_name || (item.ai_draft ? "AI 编辑" : "") }}</td>
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
                <td class="adm-wide">
                  <span v-if="item.claimed_by" class="tag">{{ item.claimed_by }} 处理中</span>
                  {{ item.body || "（只有图片的留言）" }}
                </td>
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
                <td class="adm-wide">
                  <span v-if="item.claimed_by" class="tag">{{ item.claimed_by }} 处理中</span>
                  <strong>{{ item.name }}</strong>
                </td>
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

      <AdminPushes />
    </template>
  </div>
</template>

<style scoped>
.review-switches {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-3) var(--sp-5);
}
/* 开关自带 margin-left: auto（在列表页靠右），这里并排放不需要 */
.review-switches > * {
  margin-left: 0;
}
</style>
