<script setup lang="ts">
// 管理后台：看板 + 队列 / 用户 / 内容 / 频道 / 日志。
// 权限由后端 require_admin 校验；路由守卫只负责不让普通用户看到这个页面。
import { computed, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import { jsonBody, request, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { fmtRelativeTime } from "../utils/time";

type Stats = Record<
  "new_posts_today" | "new_users_today" | "pending_contents" | "pending_comments" | "pending_channels" | "open_cases",
  number
>;
type Queue = {
  contents: { content_id: string; title: string; summary: string; author_name: string; created_at: string }[];
  comments: { comment_id: string; content_id: string | null; body: string; author_name: string; created_at: string }[];
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
type UserRow = { user_id: string; display_name: string; handle: string; email: string; status: string; is_admin: boolean; created_at: string };
type ContentRow = { content_id: string; title: string; type: string; status: string; author_name: string; created_at: string };
type ChannelRow = { channel_id: string; code: string; name: string; kind: string; is_active: boolean; review_status: string; subscriber_count: number };
type AuditRow = { id: string; action: string; actor_name: string; target_type: string | null; target_id: string | null; created_at: string };

const TABS = [
  { key: "queue", label: "待处理" },
  { key: "users", label: "用户" },
  { key: "contents", label: "内容" },
  { key: "channels", label: "频道" },
  { key: "audit", label: "操作日志" },
] as const;
type TabKey = (typeof TABS)[number]["key"];

const STAT_LABELS: [keyof Stats, string][] = [
  ["open_cases", "未处理举报"],
  ["pending_contents", "待审帖子"],
  ["pending_comments", "待审留言"],
  ["pending_channels", "待审房间"],
  ["new_posts_today", "今日新帖"],
  ["new_users_today", "今日新用户"],
];
const TARGET_LABELS = { content: "帖子", comment: "留言", channel: "房间", user: "用户" };
const CASE_REMOVE = { content: "下架", comment: "删除", channel: "下架", user: "封禁" };
const STATUS_LABELS: Record<string, string> = {
  active: "正常",
  suspended: "已封禁",
  published: "已发布",
  pending: "待审",
  rejected: "已拒绝",
  deleted: "已下架",
  approved: "已通过",
};

const route = useRoute();
const router = useRouter();
const toast = useToastStore();

const tab = computed<TabKey>(() => {
  const wanted = String(route.query.tab ?? "");
  return TABS.some((item) => item.key === wanted) ? (wanted as TabKey) : "queue";
});
function setTab(key: TabKey): void {
  void router.replace({ query: key === "queue" ? {} : { tab: key } });
}

const stats = ref<Stats | null>(null);
const queue = ref<Queue | null>(null);
const users = ref<UserRow[]>([]);
const contents = ref<ContentRow[]>([]);
const channels = ref<ChannelRow[]>([]);
const audit = ref<AuditRow[]>([]);
const auditCursor = ref<string | null>(null);

const userQuery = ref("");
const contentQuery = ref("");
const contentStatus = ref("");
const channelQuery = ref("");
const auditAction = ref("");

const loading = ref(false);
const error = ref("");
const busy = ref(""); // 正在提交的那一行，防止重复点击

const queueEmpty = computed(() => {
  const value = queue.value;
  return !!value && !value.cases.length && !value.contents.length && !value.comments.length && !value.channels.length;
});

function qs(params: Record<string, string>): string {
  const filled = Object.entries(params).filter(([, value]) => value.trim());
  return filled.length ? `?${new URLSearchParams(filled).toString()}` : "";
}

async function loadStats(): Promise<void> {
  try {
    stats.value = await request<Stats>("/api/v1/admin/stats");
  } catch {
    // 看板是辅助信息，失败不挡住下面的列表
  }
}

let loadVersion = 0;
async function loadTab(): Promise<void> {
  const version = ++loadVersion;
  loading.value = true;
  error.value = "";
  try {
    if (tab.value === "queue") {
      const body = await request<Queue>("/api/v1/admin/queue");
      if (version === loadVersion) queue.value = body;
    } else if (tab.value === "users") {
      const body = await request<{ items: UserRow[] }>(`/api/v1/admin/users${qs({ q: userQuery.value })}`);
      if (version === loadVersion) users.value = body.items;
    } else if (tab.value === "contents") {
      const body = await request<{ items: ContentRow[] }>(
        `/api/v1/admin/contents${qs({ q: contentQuery.value, status: contentStatus.value })}`,
      );
      if (version === loadVersion) contents.value = body.items;
    } else if (tab.value === "channels") {
      const body = await request<{ items: ChannelRow[] }>(`/api/v1/admin/channels${qs({ q: channelQuery.value })}`);
      if (version === loadVersion) channels.value = body.items;
    } else {
      const body = await request<{ items: AuditRow[]; next_cursor: string | null }>(
        `/api/v1/admin/audit${qs({ action: auditAction.value })}`,
      );
      if (version !== loadVersion) return;
      audit.value = body.items;
      auditCursor.value = body.next_cursor;
    }
  } catch (err) {
    if (version === loadVersion) error.value = toMessage(err);
  } finally {
    if (version === loadVersion) loading.value = false;
  }
}

async function moreAudit(): Promise<void> {
  if (!auditCursor.value || loading.value) return;
  loading.value = true;
  try {
    const body = await request<{ items: AuditRow[]; next_cursor: string | null }>(
      `/api/v1/admin/audit${qs({ action: auditAction.value, cursor: auditCursor.value })}`,
    );
    audit.value = [...audit.value, ...body.items];
    auditCursor.value = body.next_cursor;
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    loading.value = false;
  }
}

// 所有写操作走这里：提交 → 提示 → 刷新当前列表和看板。
async function act(key: string, path: string, body: unknown, done: string): Promise<void> {
  if (busy.value) return;
  busy.value = key;
  try {
    await request(path, jsonBody(body));
    toast.show(done);
    await Promise.all([loadTab(), loadStats()]);
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    busy.value = "";
  }
}

watch(tab, () => void Promise.all([loadTab(), loadStats()]), { immediate: true });
</script>

<template>
  <section class="admin">
    <header class="admin-head">
      <h1>管理后台</h1>
      <p>所有操作都会记入操作日志。</p>
    </header>

    <dl v-if="stats" class="stats">
      <div v-for="[key, label] in STAT_LABELS" :key="key" class="stat">
        <dt>{{ label }}</dt>
        <dd>{{ stats[key] }}</dd>
      </div>
    </dl>

    <div class="tabs" role="tablist" aria-label="后台分区">
      <button
        v-for="item in TABS"
        :key="item.key"
        type="button"
        role="tab"
        class="tab"
        :class="{ 'tab--on': tab === item.key }"
        :aria-selected="tab === item.key"
        @click="setTab(item.key)"
      >
        {{ item.label }}
      </button>
    </div>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="loadTab">重试</button>
    </p>

    <!-- 待处理：举报 + 待审 -->
    <div v-if="tab === 'queue' && queue" role="tabpanel">
      <p v-if="queueEmpty" class="empty">没有待处理的事项。</p>

      <template v-if="queue.cases.length">
        <h2 class="group">举报（{{ queue.cases.length }}）</h2>
        <article v-for="item in queue.cases" :key="item.case_id" class="row">
          <div class="row-main">
            <strong>
              <span class="tag tag--warn">{{ TARGET_LABELS[item.target_type] }}</span>
              <RouterLink v-if="item.target_type === 'content' && item.target_id" :to="{ name: 'content', params: { id: item.target_id } }">{{ item.target_label }}</RouterLink>
              <RouterLink v-else-if="item.target_type === 'user' && item.target_id" :to="{ name: 'user', params: { id: item.target_id } }">{{ item.target_label }}</RouterLink>
              <template v-else>{{ item.target_label }}</template>
            </strong>
            <span class="row-meta">理由：{{ item.reason }}{{ item.detail ? ` · ${item.detail}` : "" }}</span>
            <span class="row-meta">{{ item.reporter_name || "游客" }} 举报 · {{ fmtRelativeTime(item.created_at) }}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="btn btn--danger btn--sm" :disabled="busy === item.case_id" @click="act(item.case_id, `/api/v1/moderation/cases/${item.case_id}/decision`, { decision: 'remove' }, `已${CASE_REMOVE[item.target_type]}`)">
              {{ CASE_REMOVE[item.target_type] }}
            </button>
            <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.case_id" @click="act(item.case_id, `/api/v1/moderation/cases/${item.case_id}/decision`, { decision: 'dismiss' }, '已驳回举报')">
              驳回
            </button>
          </div>
        </article>
      </template>

      <template v-if="queue.contents.length">
        <h2 class="group">待审帖子（{{ queue.contents.length }}）</h2>
        <article v-for="item in queue.contents" :key="item.content_id" class="row">
          <div class="row-main">
            <strong>{{ item.title }}</strong>
            <span v-if="item.summary" class="row-body">{{ item.summary }}</span>
            <span class="row-meta">{{ item.author_name }} · {{ fmtRelativeTime(item.created_at) }}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.content_id" @click="act(item.content_id, `/api/v1/moderation/${item.content_id}/decision`, { decision: 'approve' }, '已通过')">通过</button>
            <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="act(item.content_id, `/api/v1/moderation/${item.content_id}/decision`, { decision: 'reject' }, '已拒绝')">拒绝</button>
          </div>
        </article>
      </template>

      <template v-if="queue.comments.length">
        <h2 class="group">待审留言（{{ queue.comments.length }}）</h2>
        <article v-for="item in queue.comments" :key="item.comment_id" class="row">
          <div class="row-main">
            <span class="row-body">{{ item.body || "（只有图片的留言）" }}</span>
            <span class="row-meta">{{ item.author_name }} · {{ fmtRelativeTime(item.created_at) }}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.comment_id" @click="act(item.comment_id, `/api/v1/moderation/comments/${item.comment_id}/decision`, { decision: 'approve' }, '已通过')">通过</button>
            <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.comment_id" @click="act(item.comment_id, `/api/v1/moderation/comments/${item.comment_id}/decision`, { decision: 'reject' }, '已拒绝')">拒绝</button>
          </div>
        </article>
      </template>

      <template v-if="queue.channels.length">
        <h2 class="group">待审房间（{{ queue.channels.length }}）</h2>
        <article v-for="item in queue.channels" :key="item.channel_id" class="row">
          <div class="row-main">
            <strong>{{ item.name }}</strong>
            <span class="row-meta">{{ item.owner_name }} 创建 · {{ fmtRelativeTime(item.created_at) }}</span>
          </div>
          <div class="row-actions">
            <button type="button" class="btn btn--primary btn--sm" :disabled="busy === item.channel_id" @click="act(item.channel_id, `/api/v1/moderation/channels/${item.channel_id}/decision`, { decision: 'approve' }, '已通过')">通过</button>
            <button type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="act(item.channel_id, `/api/v1/moderation/channels/${item.channel_id}/decision`, { decision: 'reject' }, '已拒绝')">拒绝</button>
          </div>
        </article>
      </template>
    </div>

    <!-- 用户 -->
    <div v-else-if="tab === 'users'" role="tabpanel">
      <form class="filters" @submit.prevent="loadTab">
        <input v-model="userQuery" class="input" type="search" aria-label="搜索用户" placeholder="邮箱、名字或账号名" />
        <button type="submit" class="btn btn--outline">搜索</button>
      </form>
      <p v-if="!loading && !users.length" class="empty">没有找到用户。</p>
      <article v-for="item in users" :key="item.user_id" class="row">
        <div class="row-main">
          <strong>
            <RouterLink :to="{ name: 'user', params: { id: item.user_id } }">{{ item.display_name }}</RouterLink>
            <span v-if="item.is_admin" class="tag tag--link">管理员</span>
            <span v-if="item.status !== 'active'" class="tag tag--danger">{{ STATUS_LABELS[item.status] ?? item.status }}</span>
          </strong>
          <span class="row-meta">{{ item.email }}{{ item.handle ? ` · @${item.handle}` : "" }} · {{ fmtRelativeTime(item.created_at) }}注册</span>
        </div>
        <div class="row-actions">
          <button v-if="item.status === 'suspended'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.user_id" @click="act(item.user_id, `/api/v1/admin/users/${item.user_id}/status`, { status: 'active' }, '已解封')">解封</button>
          <button v-else-if="item.status === 'active' && !item.is_admin" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.user_id" @click="act(item.user_id, `/api/v1/admin/users/${item.user_id}/status`, { status: 'suspended' }, '已封禁')">封禁</button>
        </div>
      </article>
    </div>

    <!-- 内容 -->
    <div v-else-if="tab === 'contents'" role="tabpanel">
      <form class="filters" @submit.prevent="loadTab">
        <input v-model="contentQuery" class="input" type="search" aria-label="搜索内容标题" placeholder="标题关键词" />
        <select v-model="contentStatus" class="input filters-select" aria-label="按状态筛选" @change="loadTab">
          <option value="">全部状态</option>
          <option value="published">已发布</option>
          <option value="pending">待审</option>
          <option value="rejected">已拒绝</option>
          <option value="deleted">已下架</option>
        </select>
        <button type="submit" class="btn btn--outline">搜索</button>
      </form>
      <p v-if="!loading && !contents.length" class="empty">没有找到内容。</p>
      <article v-for="item in contents" :key="item.content_id" class="row">
        <div class="row-main">
          <strong>
            <RouterLink v-if="item.status === 'published'" :to="{ name: 'content', params: { id: item.content_id } }">{{ item.title }}</RouterLink>
            <template v-else>{{ item.title }}</template>
            <span v-if="item.status !== 'published'" class="tag" :class="item.status === 'deleted' ? 'tag--danger' : 'tag--warn'">{{ STATUS_LABELS[item.status] ?? item.status }}</span>
          </strong>
          <span class="row-meta">{{ item.author_name || "未知作者" }} · {{ item.type }} · {{ fmtRelativeTime(item.created_at) }}</span>
        </div>
        <div class="row-actions">
          <button v-if="item.status === 'deleted'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="act(item.content_id, `/api/v1/admin/contents/${item.content_id}/status`, { action: 'restore' }, '已恢复')">恢复</button>
          <button v-else type="button" class="btn btn--danger btn--sm" :disabled="busy === item.content_id" @click="act(item.content_id, `/api/v1/admin/contents/${item.content_id}/status`, { action: 'remove' }, '已下架')">下架</button>
        </div>
      </article>
    </div>

    <!-- 频道 -->
    <div v-else-if="tab === 'channels'" role="tabpanel">
      <form class="filters" @submit.prevent="loadTab">
        <input v-model="channelQuery" class="input" type="search" aria-label="搜索频道" placeholder="频道名或代号" />
        <button type="submit" class="btn btn--outline">搜索</button>
      </form>
      <p v-if="!loading && !channels.length" class="empty">没有找到频道。</p>
      <article v-for="item in channels" :key="item.channel_id" class="row">
        <div class="row-main">
          <strong>
            {{ item.name }}
            <span v-if="!item.is_active" class="tag tag--danger">已下架</span>
            <span v-if="item.review_status !== 'approved'" class="tag tag--warn">{{ STATUS_LABELS[item.review_status] ?? item.review_status }}</span>
          </strong>
          <span class="row-meta">{{ item.code }} · {{ item.kind }} · {{ item.subscriber_count }} 人加入</span>
        </div>
        <div class="row-actions">
          <button v-if="item.is_active" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.channel_id" @click="act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/active`, { active: false }, '已下架')">下架</button>
          <button v-else type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/active`, { active: true }, '已上架')">上架</button>
        </div>
      </article>
    </div>

    <!-- 操作日志 -->
    <div v-else-if="tab === 'audit'" role="tabpanel">
      <form class="filters" @submit.prevent="loadTab">
        <input v-model="auditAction" class="input" type="search" aria-label="按动作筛选" placeholder="动作，如 admin. 或 moderation.remove" />
        <button type="submit" class="btn btn--outline">筛选</button>
      </form>
      <p v-if="!loading && !audit.length" class="empty">没有匹配的记录。</p>
      <article v-for="item in audit" :key="item.id" class="row">
        <div class="row-main">
          <strong class="mono">{{ item.action }}</strong>
          <span class="row-meta">
            {{ item.actor_name || "系统" }} · {{ fmtRelativeTime(item.created_at) }}
            <template v-if="item.target_type"> · {{ item.target_type }} {{ item.target_id }}</template>
          </span>
        </div>
      </article>
      <button v-if="auditCursor" type="button" class="btn btn--outline more" :disabled="loading" @click="moreAudit">加载更多</button>
    </div>

    <p v-if="loading" class="row-meta loading" aria-live="polite">正在加载…</p>
  </section>
</template>

<style scoped>
.admin { padding-bottom: var(--sp-10); }
.admin-head { padding: var(--sp-4) var(--sp-4) var(--sp-2); }
.admin-head h1 { font-size: var(--fs-19); font-weight: var(--fw-heavy); }
.admin-head p { color: var(--muted); font-size: var(--fs-13); }

.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--sp-2); padding: var(--sp-2) var(--sp-4) var(--sp-3); margin: 0; }
.stat { padding: var(--sp-3); border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface); }
.stat dt { color: var(--muted); font-size: var(--fs-12); }
.stat dd { margin: 0; font-size: var(--fs-21); font-weight: var(--fw-heavy); }

.tabs { display: flex; overflow-x: auto; border-bottom: 1px solid var(--border); }
.tab {
  flex: 1 0 auto; min-height: var(--tap); padding: 0 var(--sp-4);
  border: 0; border-bottom: 2px solid transparent; background: transparent;
  color: var(--muted); font-size: var(--fs-14); font-weight: var(--fw-semibold); white-space: nowrap;
}
.tab:hover { background: var(--hover); }
.tab--on { color: var(--text); border-bottom-color: var(--accent); }

.filters { display: flex; gap: var(--sp-2); padding: var(--sp-3) var(--sp-4); }
.filters .input { flex: 1; min-width: 0; }
.filters .filters-select { flex: 0 0 auto; width: auto; }

.group { padding: var(--sp-4) var(--sp-4) var(--sp-1); font-size: var(--fs-14); font-weight: var(--fw-bold); }
.row { display: flex; align-items: center; gap: var(--sp-3); padding: var(--sp-3) var(--sp-4); border-bottom: 1px solid var(--border); }
.row-main { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--sp-1); }
.row-main strong { display: flex; flex-wrap: wrap; align-items: center; gap: var(--sp-2); font-size: var(--fs-14); overflow-wrap: anywhere; }
.row-main a { color: var(--text); }
.row-body { font-size: var(--fs-13); line-height: var(--lh-body); overflow-wrap: anywhere; }
.row-meta { color: var(--muted); font-size: var(--fs-12); overflow-wrap: anywhere; }
.row-actions { display: flex; gap: var(--sp-2); flex-shrink: 0; }
.mono { font-family: ui-monospace, monospace; }
.more { display: flex; margin: var(--sp-4) auto 0; }
.loading { padding: var(--sp-4); text-align: center; }
.notice { align-items: center; justify-content: space-between; }

@media (max-width: 520px) {
  .stats { grid-template-columns: repeat(2, 1fr); }
  .row { flex-direction: column; align-items: stretch; }
}
</style>
