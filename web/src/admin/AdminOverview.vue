<script setup lang="ts">
// 概览：数字卡片 + 近 14 天新帖 / 新用户趋势。
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { toMessage } from "../api";
import { adminRequest } from "./adminApi";
import type { AdminStats } from "./shared";

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

async function load(): Promise<void> {
  error.value = "";
  try {
    stats.value = await adminRequest<AdminStats>("/api/v1/admin/stats");
  } catch (err) {
    error.value = toMessage(err);
  }
}
void load();
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
    </template>
  </div>
</template>
