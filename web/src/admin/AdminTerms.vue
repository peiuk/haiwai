<script setup lang="ts">
// 敏感词 / 链接黑名单：帖子里出现名单上的词，就先进待审核而不是直接发布。
import { ref } from "vue";
import { toMessage } from "../api";
import { adminMe, adminRequest } from "./adminApi";
import { exact, when } from "./shared";
import { useAdminAction } from "./useAdminList";

type Row = { term: string; created_at: string };

const items = ref<Row[]>([]);
const error = ref("");
const term = ref("");

async function load(): Promise<void> {
  error.value = "";
  try {
    items.value = (await adminRequest<{ items: Row[] }>("/api/v1/admin/terms")).items;
  } catch (err) {
    error.value = toMessage(err);
  }
}
const { busy, act } = useAdminAction(load);
void load();

async function add(): Promise<void> {
  await act("add", "/api/v1/admin/terms", { term: term.value }, "已添加");
  term.value = "";
}

function remove(item: Row): Promise<void> {
  return act(item.term, "/api/v1/admin/terms/delete", { term: item.term }, "已删除");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>敏感词</h1>
      <p>帖子的标题或正文里出现名单上的词或网址，就不直接发布，先进「待审核」。不分大小写。</p>
    </header>

    <form v-if="adminMe.is_super" class="adm-filters" @submit.prevent="add">
      <input v-model="term" class="input" aria-label="要添加的词或网址" placeholder="词或网址，如 某某博彩、bad-site.com" minlength="2" maxlength="64" required />
      <button type="submit" class="btn btn--primary" :disabled="busy === 'add'">添加</button>
    </form>
    <p v-else class="adm-sub">只有超级管理员可以增删。</p>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">名单是空的。太短或太常见的词会把正常帖子也拦下来，建议只加明确的广告词和网址。</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead><tr><th>词 / 网址</th><th>添加时间</th><th></th></tr></thead>
          <tbody>
            <tr v-for="item in items" :key="item.term">
              <td class="adm-wide">{{ item.term }}</td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="adminMe.is_super" type="button" class="btn btn--ghost btn--sm" :disabled="busy === item.term" @click="remove(item)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
