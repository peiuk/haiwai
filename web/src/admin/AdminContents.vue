<script setup lang="ts">
// 内容管理表格：帖子 / 分类信息 / 新闻公告 三个菜单共用，按 types 区分。
import { computed, ref } from "vue";
import { RouterLink } from "vue-router";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminRequest } from "./adminApi";
import AdminPager from "./AdminPager.vue";
import { STATUS_LABELS, TYPE_LABELS, exact, statusTone, when } from "./shared";
import { useAdminList } from "./useAdminList";

const props = defineProps<{ types: string; title: string; announce?: boolean }>();

type Row = {
  content_id: string;
  title: string;
  type: string;
  status: string;
  author_name: string;
  channel_name: string;
  view_count: number;
  featured: boolean;
  created_at: string;
};

const toast = useToastStore();
const q = ref("");
const status = ref("");
const showType = computed(() => props.types.includes(","));
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/contents",
  () => ({ q: q.value, status: status.value, type: props.types }),
);

function remove(item: Row): Promise<void> {
  return ask(
    { title: "下架这条内容？", message: `「${item.title}」下架后前台不再显示，之后可以恢复。`, confirmLabel: "下架", danger: true, reason: true },
    item.content_id,
    `/api/v1/admin/contents/${item.content_id}/status`,
    (reason) => ({ action: "remove", reason }),
    "已下架",
  );
}

function restore(item: Row): Promise<void> {
  return act(item.content_id, `/api/v1/admin/contents/${item.content_id}/status`, { action: "restore" }, "已恢复");
}

function feature(item: Row): Promise<void> {
  return act(item.content_id, `/api/v1/admin/contents/${item.content_id}/featured`, { featured: !item.featured }, item.featured ? "已取消精选" : "已设为精选");
}

// ---- 发布公告（只在「新闻 / 公告」页显示） ----
const composing = ref(false);
const channelOptions = ref<{ channel_id: string; name: string }[]>([]);
const draft = ref({ title: "", body: "", channel_id: "" });
const publishing = ref(false);

async function openComposer(): Promise<void> {
  composing.value = true;
  if (channelOptions.value.length) return;
  try {
    channelOptions.value = (await adminRequest<{ items: { channel_id: string; name: string }[] }>("/api/v1/admin/channel-options")).items;
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function publish(): Promise<void> {
  if (publishing.value) return;
  publishing.value = true;
  try {
    await adminRequest("/api/v1/admin/announcements", jsonBody(draft.value));
    toast.show("公告已发布并置顶");
    draft.value = { title: "", body: "", channel_id: "" };
    composing.value = false;
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    publishing.value = false;
  }
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>{{ props.title }}</h1>
      <p>下架后前台不再显示；精选内容会在「为你推荐」里靠前</p>
      <button v-if="props.announce && !composing" type="button" class="btn btn--primary btn--sm" @click="openComposer">发布公告</button>
    </header>

    <section v-if="composing" class="adm-panel">
      <h2>发布公告</h2>
      <form class="adm-form" @submit.prevent="publish">
        <div class="field">
          <label for="adm-ann-channel">发到哪个频道（会在该频道置顶）</label>
          <select id="adm-ann-channel" v-model="draft.channel_id" class="input" required>
            <option value="" disabled>请选择频道</option>
            <option v-for="item in channelOptions" :key="item.channel_id" :value="item.channel_id">{{ item.name }}</option>
          </select>
        </div>
        <div class="field">
          <label for="adm-ann-title">标题</label>
          <input id="adm-ann-title" v-model="draft.title" class="input" maxlength="200" required />
        </div>
        <div class="field">
          <label for="adm-ann-body">正文</label>
          <textarea id="adm-ann-body" v-model="draft.body" class="input" rows="6" maxlength="4000" required></textarea>
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--primary" :disabled="publishing">{{ publishing ? "正在发布…" : "发布" }}</button>
          <button type="button" class="btn btn--outline" @click="composing = false">取消</button>
        </div>
      </form>
    </section>

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="按标题搜索" placeholder="标题关键词" />
      <select v-model="status" class="input" aria-label="按状态筛选" @change="search">
        <option value="">全部状态</option>
        <option value="published">已发布</option>
        <option value="pending">待审</option>
        <option value="rejected">已拒绝</option>
        <option value="deleted">已下架</option>
      </select>
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的内容。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr>
              <th>标题</th><th v-if="showType">类型</th><th>作者 / 来源</th><th>频道</th><th>状态</th><th class="adm-num">浏览</th><th>发布时间</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.content_id">
              <td class="adm-wide">
                <RouterLink :to="`/admin/contents/${item.content_id}`">{{ item.title }}</RouterLink>
                <span v-if="item.featured" class="tag tag--link">精选</span>
              </td>
              <td v-if="showType" class="adm-nowrap">{{ TYPE_LABELS[item.type] ?? item.type }}</td>
              <td class="adm-nowrap">{{ item.author_name || "—" }}</td>
              <td class="adm-nowrap">{{ item.channel_name || "—" }}</td>
              <td><span class="tag" :class="statusTone(item.status)">{{ STATUS_LABELS[item.status] ?? item.status }}</span></td>
              <td class="adm-num">{{ item.view_count }}</td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="item.status === 'published'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="feature(item)">{{ item.featured ? "取消精选" : "精选" }}</button>
                  <button v-if="item.status === 'deleted'" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.content_id" @click="restore(item)">恢复</button>
                  <button v-else type="button" class="btn btn--danger btn--sm" :disabled="busy === item.content_id" @click="remove(item)">下架</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <AdminPager :page="page" :total="total" :page-size="pageSize" @go="go" />
    </section>
  </div>
</template>
