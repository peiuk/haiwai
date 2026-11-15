<script setup lang="ts">
// 举报记录表：内容详情和用户详情共用。
import { exact, when, type CaseRow } from "./shared";

defineProps<{
  title: string;
  cases: CaseRow[];
  empty: string;
  /** 举报成立时的处理结果怎么叫：内容是"已下架"，用户是"已封禁" */
  removedLabel: string;
}>();
</script>

<template>
  <section class="adm-panel">
    <h2>{{ title }}（{{ cases.length }}）</h2>
    <p v-if="!cases.length" class="adm-empty">{{ empty }}</p>
    <div v-else class="adm-scroll">
      <table class="adm-table">
        <thead><tr><th>理由</th><th>举报人</th><th>处理结果</th><th>时间</th></tr></thead>
        <tbody>
          <tr v-for="item in cases" :key="item.case_id">
            <td class="adm-wide">{{ item.reason }}<span v-if="item.detail" class="adm-sub">{{ item.detail }}</span></td>
            <td class="adm-nowrap">{{ item.reporter_name || "游客" }}</td>
            <td class="adm-nowrap">{{ item.status === "open" ? "未处理" : item.decision === "remove" ? removedLabel : "已驳回" }}</td>
            <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
