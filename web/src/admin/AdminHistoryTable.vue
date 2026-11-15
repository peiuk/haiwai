<script setup lang="ts">
// 处理记录表（谁在什么时候做了什么、理由是什么）：内容详情和用户详情共用。
import { ACTION_LABELS, exact, when, type HistoryRow } from "./shared";

defineProps<{ history: HistoryRow[]; empty: string }>();
</script>

<template>
  <section class="adm-panel">
    <h2>处理记录</h2>
    <p v-if="!history.length" class="adm-empty">{{ empty }}</p>
    <div v-else class="adm-scroll">
      <table class="adm-table">
        <thead><tr><th>动作</th><th>操作人</th><th>理由</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="(item, index) in history" :key="index">
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
