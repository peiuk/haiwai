<script setup lang="ts">
// 概览：数字卡片 + 近 14 天新帖 / 新用户趋势。
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import { when, type AdminStats } from "./shared";

const stats = ref<AdminStats | null>(null);
const error = ref("");

const pending = computed(() =>
  stats.value ? stats.value.pending_contents + stats.value.pending_comments + stats.value.pending_channels : 0,
);
const peak = computed(() => Math.max(1, ...(stats.value?.trend ?? []).flatMap((day) => [day.posts, day.users])));
const chartSummary = computed(() => {
  const trend = stats.value?.trend ?? [];
  const posts = trend.reduce((sum, day) => sum + day.posts, 0);
  const users = trend.reduce((sum, day) => sum + day.users, 0);
  return `近 14 天新帖 ${posts} 条，新用户 ${users} 人`;
});

function height(value: number): string {
  return `${Math.round((value / peak.value) * 100)}%`;
}

const upheld = computed(() => {
  const value = stats.value;
  return value && value.cases_closed_30d ? `${Math.round((value.cases_upheld_30d / value.cases_closed_30d) * 100)}%` : "—";
});
const regionPeak = computed(() => Math.max(1, ...(stats.value?.posts_by_region ?? []).map((row) => row.posts)));

type Health = { storage: string; storage_ok: boolean; server_errors_1h: number; oldest_pending: string | null; oldest_case: string | null };
const health = ref<Health | null>(null);

async function load(): Promise<void> {
  error.value = "";
  try {
    stats.value = await adminRequest<AdminStats>("/api/v1/admin/stats");
  } catch (err) {
    error.value = toMessage(err);
  }
}
void load();
// 运行状况单独取：存储连不上时这个请求会等很久，不能拖住上面的数字
void adminRequest<Health>("/api/v1/admin/health")
  .then((value) => (health.value = value))
  .catch(() => undefined);
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>概览</h1>
      <p>日期按 UTC 计算</p>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <template v-if="stats">
      <p v-if="stats.overdue_cases || stats.overdue_contents" class="notice notice--danger" role="alert">
        有 {{ stats.overdue_cases }} 条举报、{{ stats.overdue_contents }} 条待审内容等了超过 24 小时。
        <RouterLink :to="stats.overdue_cases ? '/admin/reports' : '/admin/review'">去处理</RouterLink>
      </p>
      <div class="adm-cards">
        <RouterLink to="/admin/reports" class="adm-card" :class="{ 'adm-card--alert': stats.open_cases > 0 }">
          <span>未处理举报</span>
          <strong>{{ stats.open_cases }}</strong>
        </RouterLink>
        <RouterLink to="/admin/review" class="adm-card" :class="{ 'adm-card--alert': pending > 0 }">
          <span>待审核</span>
          <strong>{{ pending }}</strong>
        </RouterLink>
        <div class="adm-card">
          <span>今日新帖</span>
          <strong>{{ stats.new_posts_today }}</strong>
        </div>
        <div class="adm-card">
          <span>今日新用户</span>
          <strong>{{ stats.new_users_today }}</strong>
        </div>
        <RouterLink to="/admin/users" class="adm-card">
          <span>用户总数</span>
          <strong>{{ stats.total_users }}</strong>
        </RouterLink>
        <RouterLink to="/admin/posts" class="adm-card">
          <span>已发布内容</span>
          <strong>{{ stats.total_contents }}</strong>
        </RouterLink>
        <div class="adm-card" title="近 7 天打开过首页的登录用户">
          <span>近 7 天活跃用户</span>
          <strong>{{ stats.active_users_7d }}</strong>
        </div>
        <div class="adm-card" title="近 30 天，帖子从发布到被审核平均等了多久">
          <span>平均审核用时</span>
          <strong>{{ stats.avg_review_hours === null ? "—" : `${stats.avg_review_hours} 小时` }}</strong>
        </div>
        <div class="adm-card" :title="`近 30 天处理了 ${stats.cases_closed_30d} 条举报，其中 ${stats.cases_upheld_30d} 条成立`">
          <span>举报成立率（30 天）</span>
          <strong>{{ upheld }}</strong>
        </div>
      </div>

      <section class="adm-panel">
        <h2>近 14 天趋势</h2>
        <div class="adm-legend">
          <span class="adm-dot adm-dot--posts" aria-hidden="true"></span>新帖
          <span class="adm-dot adm-dot--users" aria-hidden="true"></span>新用户
        </div>
        <div class="adm-chart" role="img" :aria-label="chartSummary">
          <div v-for="day in stats.trend" :key="day.date" class="adm-day" :title="`${day.date}：新帖 ${day.posts}，新用户 ${day.users}`">
            <div class="adm-bars">
              <span class="adm-bar adm-bar--posts" :style="{ height: height(day.posts) }"><b v-if="day.posts">{{ day.posts }}</b></span>
              <span class="adm-bar adm-bar--users" :style="{ height: height(day.users) }"><b v-if="day.users">{{ day.users }}</b></span>
            </div>
            <small>{{ day.date.slice(5) }}</small>
          </div>
        </div>
      </section>

      <section class="adm-panel">
        <h2>近 14 天各国新帖</h2>
        <p v-if="!stats.posts_by_region.length" class="adm-empty">这段时间没有新发布的内容。</p>
        <div v-else class="adm-scroll">
          <table class="adm-table">
            <thead><tr><th>国家</th><th class="adm-num">新帖</th><th>占比</th></tr></thead>
            <tbody>
              <tr v-for="row in stats.posts_by_region" :key="row.region">
                <td class="adm-nowrap">{{ row.region }}</td>
                <td class="adm-num">{{ row.posts }}</td>
                <td class="adm-wide"><span class="adm-meter" :style="{ width: `${Math.round((row.posts / regionPeak) * 100)}%` }"></span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <section class="adm-panel">
        <h2>运行状况</h2>
        <p v-if="!health" class="adm-empty">正在检查…</p>
        <dl v-else class="adm-facts">
          <div>
            <dt>图片 / 视频存储（{{ health.storage }}）</dt>
            <dd><span class="tag" :class="health.storage_ok ? 'tag--good' : 'tag--danger'">{{ health.storage_ok ? "正常" : "连不上" }}</span></dd>
          </div>
          <div>
            <dt>近 1 小时服务器错误</dt>
            <dd><span class="tag" :class="health.server_errors_1h ? 'tag--danger' : 'tag--good'">{{ health.server_errors_1h }} 次</span></dd>
          </div>
          <div><dt>最早一条待审内容</dt><dd>{{ health.oldest_pending ? when(health.oldest_pending) : "没有" }}</dd></div>
          <div><dt>最早一条未处理举报</dt><dd>{{ health.oldest_case ? when(health.oldest_case) : "没有" }}</dd></div>
        </dl>
      </section>
    </template>
  </div>
</template>
