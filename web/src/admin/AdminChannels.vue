<script setup lang="ts">
// 频道 / 房间管理：搜索、新增、编辑、认证、上架 / 下架。
import { ref } from "vue";
import { toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { ADMIN_CHANGED, adminRequest } from "./adminApi";
import AdminPager from "./AdminPager.vue";
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
const { items, total, page, pageSize, loading, error, busy, load, search, go, act, ask } = useAdminList<Row>(
  "/api/v1/admin/channels",
  () => ({ q: q.value, region: region.value }),
);

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
      <p>同一国家里按排序号从小到大排列</p>
      <button v-if="!editing" type="button" class="btn btn--primary btn--sm" @click="openCreate">新增频道</button>
    </header>

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
      <p v-if="!items.length" class="adm-empty">{{ loading ? "正在加载…" : "没有符合条件的频道。" }}</p>
      <div v-else class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>名称</th><th>国家</th><th>分类</th><th class="adm-num">排序</th><th>类型</th><th class="adm-num">成员</th><th>状态</th><th>创建时间</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in items" :key="item.channel_id">
              <td>
                <strong>{{ item.name }}</strong>
                <span v-if="item.certified" class="tag tag--link">已认证</span>
                <span class="adm-sub adm-mono">{{ item.code }}</span>
              </td>
              <td class="adm-nowrap">{{ regionNames[item.region_code] ?? item.region_code }}</td>
              <td class="adm-nowrap">{{ item.category || "—" }}</td>
              <td class="adm-num">{{ item.sort_order }}</td>
              <td class="adm-nowrap">
                {{ KIND_LABELS[item.kind] ?? item.kind }}
                <span v-if="item.owner_name" class="adm-sub">{{ item.owner_name }} 创建</span>
              </td>
              <td class="adm-num">{{ item.subscriber_count }}</td>
              <td class="adm-nowrap">
                <span class="tag" :class="item.is_active ? 'tag--good' : 'tag--danger'">{{ item.is_active ? "已上架" : "已下架" }}</span>
                <span v-if="item.review_status !== 'approved'" class="tag tag--warn">{{ STATUS_LABELS[item.review_status] ?? item.review_status }}</span>
              </td>
              <td class="adm-nowrap" :title="exact(item.created_at)">{{ when(item.created_at) }}</td>
              <td>
                <div class="adm-actions">
                  <button type="button" class="btn btn--outline btn--sm" @click="openEdit(item)">编辑</button>
                  <!-- 官方频道天然认证，不需要也不能改 -->
                  <button v-if="!item.kind.startsWith('official')" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="certify(item)">{{ item.is_certified ? "取消认证" : "认证" }}</button>
                  <button v-if="item.is_active" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.channel_id" @click="deactivate(item)">下架</button>
                  <button v-else type="button" class="btn btn--outline btn--sm" :disabled="busy === item.channel_id" @click="activate(item)">上架</button>
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
