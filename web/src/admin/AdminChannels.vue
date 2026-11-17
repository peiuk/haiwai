<script setup lang="ts">
// 频道 / 房间管理：搜索、新增、编辑、认证、上架 / 下架、删除。
import { ref } from "vue";
import { ApiRequestError, jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { ADMIN_CHANGED, adminMe, adminRequest } from "./adminApi";
import AdminPager from "./AdminPager.vue";
import AdminPushes from "./AdminPushes.vue";
import AdminSlots from "./AdminSlots.vue";
import { confirmAction } from "./confirm";
import { KIND_LABELS, STATUS_LABELS, exact, when } from "./shared";
import { useAdminList } from "./useAdminList";

type Row = {
  channel_id: string;
  code: string;
  name: string;
  name_hant: string;
  kind: string;
  region_code: string;
  category: string;
  sort_order: number;
  owner_name: string;
  is_active: boolean;
  is_certified: boolean;
  certified: boolean;
  review_status: string;
  subscriber_count: number;
  created_at: string;
};
type RegionOption = { code: string; name: string; is_open: boolean };

const toast = useToastStore();
const q = ref("");
const region = ref("");
// 分开看：官方频道由后台管理；用户房间由用户自己创建，后台只做审核、认证、上下架；待审推送是房主推到频道的帖子
const scope = ref<"official" | "room" | "push">("official");
const slotFor = ref<Row | null>(null); // 正在编辑房间位的官方频道
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/channels",
  () => ({ q: q.value, region: region.value, scope: scope.value }),
);

function setScope(next: "official" | "room" | "push"): void {
  if (scope.value === next) return;
  scope.value = next;
  editing.value = "";
  slotFor.value = null;
  if (next !== "push") search();
}

const regions = ref<RegionOption[]>([]);
const regionNames = ref<Record<string, string>>({});
void adminRequest<{ items: RegionOption[] }>("/api/v1/admin/regions")
  .then((body) => {
    regions.value = body.items.filter((item) => item.is_open);
    regionNames.value = Object.fromEntries(body.items.map((item) => [item.code, item.name]));
  })
  .catch(() => {
    // 国家列表拿不到时筛选和表单里的下拉为空，表格本身照常显示
  });

// ---- 新增 / 编辑表单 ----
const blank = { code: "", name_hans: "", name_hant: "", region_code: "", category: "", sort_order: 0, kind: "official_curated" };
const editing = ref<"" | "new" | string>(""); // ""=关着，"new"=新增，其余是正在编辑的频道 id
const form = ref({ ...blank });
const saving = ref(false);

function openCreate(): void {
  form.value = { ...blank, region_code: region.value };
  editing.value = "new";
}

function openEdit(item: Row): void {
  form.value = {
    code: item.code,
    name_hans: item.name,
    name_hant: item.name_hant === item.name ? "" : item.name_hant,
    region_code: item.region_code,
    category: item.category,
    sort_order: item.sort_order,
    kind: item.kind,
  };
  editing.value = item.channel_id;
  window.scrollTo({ top: 0 });
}

async function save(): Promise<void> {
  if (saving.value) return;
  saving.value = true;
  const creating = editing.value === "new";
  const { code, kind, ...fields } = form.value;
  try {
    await adminRequest(creating ? "/api/v1/admin/channels" : `/api/v1/admin/channels/${editing.value}`, {
      method: creating ? "POST" : "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(creating ? { code, kind, ...fields } : fields),
    });
    toast.show(creating ? "频道已创建" : "已保存");
    window.dispatchEvent(new Event(ADMIN_CHANGED));
    editing.value = "";
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    saving.value = false;
  }
}

function deactivate(item: Row): Promise<void> {
  return ask(
    { title: `下架「${item.name}」？`, message: "下架后前台不再显示，成员和内容保留，可以重新上架。", confirmLabel: "下架", danger: true, reason: true },
    item.channel_id,
    `/api/v1/admin/channels/${item.channel_id}/active`,
    (reason) => ({ active: false, reason }),
    "已下架",
  );
}

// 删除分两步：先按空频道删；后端说里面还有内容时，再让管理员输入频道名确认连内容一起删。
async function remove(item: Row): Promise<void> {
  const url = `/api/v1/admin/channels/${item.channel_id}/delete`;
  const reason = await confirmAction({
    title: `彻底删除「${item.name}」？`,
    message: "删除后不能恢复。只是不想让它显示的话，请用「下架」。",
    confirmLabel: "删除",
    danger: true,
    reason: true,
  });
  if (reason === null || busy.value) return;
  busy.value = item.channel_id;
  try {
    try {
      await adminRequest(url, jsonBody({ reason }));
    } catch (err) {
      if (!(err instanceof ApiRequestError) || err.code !== "CHANNEL_NOT_EMPTY") throw err;
      const again = await confirmAction({
        title: `连内容一起删除「${item.name}」？`,
        message: `${err.message}。继续的话：只属于这个频道的帖子会一并下架，留言会删掉，下属房间保留但不再归属这个频道。不能恢复。`,
        confirmLabel: "连内容一起删除",
        danger: true,
        mustType: item.name,
      });
      if (again === null) return;
      await adminRequest(url, jsonBody({ reason, with_content: true, confirm_name: item.name }));
    }
    toast.show("已删除");
    window.dispatchEvent(new Event(ADMIN_CHANGED));
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    busy.value = "";
  }
}

function activate(item: Row): Promise<void> {
  return act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/active`, { active: true }, "已上架");
}

function certify(item: Row): Promise<void> {
  return act(item.channel_id, `/api/v1/admin/channels/${item.channel_id}/certified`, { certified: !item.is_certified }, item.is_certified ? "已取消认证" : "已认证");
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>频道 / 房间</h1>
      <p>{{ scope === "official" ? "后台建立和管理的官方频道，同一国家里按排序号从小到大排列" : scope === "room" ? "用户自己创建的房间，房主负责运营；这里只做审核、认证、上下架" : "房主把房间里的帖子推到官方频道，通过后才会出现在频道里" }}</p>
      <button v-if="scope === 'official' && !editing && adminMe.is_super" type="button" class="btn btn--primary btn--sm" @click="openCreate">新增频道</button>
    </header>

    <div class="adm-filters" role="tablist" aria-label="频道与房间">
      <button type="button" role="tab" class="btn btn--sm" :class="scope === 'official' ? 'btn--primary' : 'btn--outline'" :aria-selected="scope === 'official'" @click="setScope('official')">官方频道</button>
      <button type="button" role="tab" class="btn btn--sm" :class="scope === 'room' ? 'btn--primary' : 'btn--outline'" :aria-selected="scope === 'room'" @click="setScope('room')">用户房间</button>
      <button type="button" role="tab" class="btn btn--sm" :class="scope === 'push' ? 'btn--primary' : 'btn--outline'" :aria-selected="scope === 'push'" @click="setScope('push')">待审推送</button>
    </div>

    <AdminPushes v-if="scope === 'push'" />
    <div v-show="scope !== 'push'">

    <section v-if="editing" class="adm-panel">
      <h2>{{ editing === "new" ? "新增频道" : "编辑频道" }}</h2>
      <form class="adm-form" @submit.prevent="save">
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-ch-name">频道名</label>
            <input id="adm-ch-name" v-model="form.name_hans" class="input" maxlength="64" required />
          </div>
          <div class="field">
            <label for="adm-ch-hant">繁体名（不填则和频道名相同）</label>
            <input id="adm-ch-hant" v-model="form.name_hant" class="input" maxlength="64" />
          </div>
        </div>
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-ch-region">所属国家</label>
            <select id="adm-ch-region" v-model="form.region_code" class="input" required>
              <option value="" disabled>请选择</option>
              <option v-for="item in regions" :key="item.code" :value="item.code">{{ item.name }}</option>
            </select>
          </div>
          <div class="field">
            <label for="adm-ch-category">分类（如 资讯、房产；可不填）</label>
            <input id="adm-ch-category" v-model="form.category" class="input" maxlength="16" />
          </div>
          <div class="field">
            <label for="adm-ch-sort">排序号</label>
            <input id="adm-ch-sort" v-model.number="form.sort_order" class="input" type="number" min="0" max="999" required />
          </div>
        </div>
        <div v-if="editing === 'new'" class="adm-form-row">
          <div class="field">
            <label for="adm-ch-code">英文代号（小写字母、数字、短横线；建好后不能改）</label>
            <input id="adm-ch-code" v-model="form.code" class="input" pattern="[a-z0-9][a-z0-9-]{2,47}" placeholder="例如 us-food" required />
          </div>
          <div class="field">
            <label for="adm-ch-kind">类型</label>
            <select id="adm-ch-kind" v-model="form.kind" class="input">
              <option value="official_curated">官方频道（人工发布）</option>
              <option value="official_auto">官方聚合（自动收录）</option>
            </select>
          </div>
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--primary" :disabled="saving">{{ saving ? "正在保存…" : "保存" }}</button>
          <button type="button" class="btn btn--outline" @click="editing = ''">取消</button>
        </div>
      </form>
    </section>

    <AdminSlots v-if="slotFor" :key="slotFor.channel_id" :channel-id="slotFor.channel_id" :channel-name="slotFor.name" @close="slotFor = null" />

    <form class="adm-filters" @submit.prevent="search">
      <input v-model="q" class="input" type="search" aria-label="搜索频道" placeholder="名称或代号" />
      <select v-model="region" class="input" aria-label="按国家筛选" @change="search">
        <option value="">全部国家</option>
        <option v-for="item in regions" :key="item.code" :value="item.code">{{ item.name }}</option>
      </select>
      <button type="submit" class="btn btn--outline">搜索</button>
    </form>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section class="adm-panel">
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : scope === "official" ? "没有符合条件的频道。" : "没有符合条件的用户房间。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr v-if="scope === 'official'"><th>名称</th><th>国家</th><th>分类</th><th class="adm-num">排序</th><th>类型</th><th class="adm-num">成员</th><th>状态</th><th>创建时间</th><th></th></tr>
            <tr v-else><th>房间</th><th>国家</th><th>房主</th><th class="adm-num">成员</th><th>状态</th><th>创建时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.channel_id">
              <td>
                <strong>{{ item.name }}</strong>
                <span v-if="item.certified" class="tag tag--link">已认证</span>
                <span class="adm-sub adm-mono">{{ item.code }}</span>
              </td>
              <td class="adm-nowrap">{{ regionNames[item.region_code] ?? item.region_code }}</td>
              <template v-if="scope === 'official'">
                <td class="adm-nowrap">{{ item.category || "—" }}</td>
                <td class="adm-num">{{ item.sort_order }}</td>
                <td class="adm-nowrap">{{ KIND_LABELS[item.kind] ?? item.kind }}</td>
              </template>
              <td v-else class="adm-nowrap">{{ item.owner_name || "—" }}</td>
              <td class="adm-num">{{ item.subscriber_count }}</td>
              <td class="adm-nowrap">
                <span class="tag" :class="item.is_active ? 'tag--good' : 'tag--danger'">{{ item.is_active ? "已上架" : "已下架" }}</span>
                <span v-if="item.review_status !== 'approved'" class="tag tag--warn">{{ STATUS_LABELS[item.review_status] ?? item.review_status }}</span>
              </td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="scope === 'official'" type="button" class="btn btn--outline btn--sm" @click="slotFor = item">房间位</button>
                  <button v-if="adminMe.is_super" type="button" class="btn btn--outline btn--sm" @click="openEdit(item)">编辑</button>
                  <!-- 官方频道天然认证，不需要也不能改 -->
                  <button v-if="adminMe.is_super && !item.kind.startsWith('official')" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="certify(item)">{{ item.is_certified ? "取消认证" : "认证" }}</button>
                  <button v-if="item.is_active" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.channel_id" @click="deactivate(item)">下架</button>
                  <button v-else type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="activate(item)">上架</button>
                  <button v-if="adminMe.is_super" type="button" class="btn btn--ghost btn--sm" :disabled="busy === item.channel_id" @click="remove(item)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <AdminPager :page="page" :total="total" :page-size="pageSize" @go="go" />
    </section>
    </div>
  </div>
</template>
