<script setup lang="ts">
// 国家管理：开通新国家（自动建默认频道）、关闭 / 重开、补齐默认频道、连数据一起删除。
import { ref } from "vue";
import { RouterLink } from "vue-router";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminMe, adminRequest } from "./adminApi";
import { useAdminAction } from "./useAdminList";

type Region = { code: string; name: string; city: string; is_open: boolean; channel_count: number };
type Body = { items: Region[]; requests: { code: string; count: number }[] };

const toast = useToastStore();
const data = ref<Body | null>(null);
const error = ref("");

async function load(): Promise<void> {
  error.value = "";
  try {
    data.value = await adminRequest<Body>("/api/v1/admin/regions");
  } catch (err) {
    error.value = toMessage(err);
  }
}
const { busy, act, ask } = useAdminAction(load);
void load();

// ---- 开通新国家 ----
const form = ref({ code: "", name: "", city: "" });
const opening = ref(false);

async function open(): Promise<void> {
  if (opening.value) return;
  opening.value = true;
  try {
    const result = await adminRequest<{ channels: string[] }>("/api/v1/admin/regions", jsonBody(form.value));
    toast.show(`已开通，并建好 ${result.channels.length} 个频道`, 4000);
    form.value = { code: "", name: "", city: "" };
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    opening.value = false;
  }
}

function prefill(code: string): void {
  form.value.code = code;
  document.getElementById("adm-region-name")?.focus();
}

function close(item: Region): Promise<void> {
  return ask(
    {
      title: `关闭「${item.name}」？`,
      message: "关闭后用户不能再选这个国家，已选的用户会回到国际频道。频道和内容都保留，可以重新开通。",
      confirmLabel: "关闭",
      danger: true,
      reason: true,
    },
    item.code,
    `/api/v1/admin/regions/${item.code}/open`,
    (reason) => ({ open: false, reason }),
    "已关闭",
  );
}

// 彻底删除：频道、房间和里面的内容一起删，要原样输入国家名。国际各国共享，不能删。
function remove(item: Region): Promise<void> {
  return ask(
    {
      title: `彻底删除「${item.name}」？`,
      message: `会一并删除这个国家的 ${item.channel_count} 个官方频道、所有房间和其中的留言（含留言图片）；帖子全部下架，帖子的图片和视频文件仍保留。选了这个国家的用户回到国际。不能恢复。只想暂停的话，请用「关闭」。`,
      confirmLabel: "连数据一起删除",
      danger: true,
      reason: true,
      mustType: item.name,
    },
    item.code,
    `/api/v1/admin/regions/${item.code}/delete`,
    (reason) => ({ reason, confirm_name: item.name }),
    "已删除",
  );
}

function reopen(item: Region): Promise<void> {
  return act(item.code, `/api/v1/admin/regions/${item.code}/open`, { open: true }, "已重新开通");
}

async function fill(item: Region): Promise<void> {
  if (busy.value) return;
  busy.value = item.code;
  try {
    const result = await adminRequest<{ channels: string[] }>(`/api/v1/admin/regions/${item.code}/channels`, { method: "POST" });
    toast.show(result.channels.length ? `已补上：${result.channels.join("、")}` : "默认频道已经齐了", 4000);
    await load();
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    busy.value = "";
  }
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>国家</h1>
      <p>开通新国家时自动建好：资讯、交流、招聘、房产、市场、商务（频道名前加国家名）</p>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">
      {{ error }}
      <button type="button" class="btn btn--outline btn--sm" @click="load">重试</button>
    </p>

    <section v-if="adminMe.is_super" class="adm-panel">
      <h2>开通新国家</h2>
      <form class="adm-form" @submit.prevent="open">
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-region-code">国家代码（2 到 8 个英文字母，如 US、CA、AU）</label>
            <input id="adm-region-code" v-model="form.code" class="input" pattern="[A-Za-z]{2,8}" maxlength="8" required />
          </div>
          <div class="field">
            <label for="adm-region-name">中文名（会加在频道名前面）</label>
            <input id="adm-region-name" v-model="form.name" class="input" maxlength="32" placeholder="例如 美国" required />
          </div>
          <div class="field">
            <label for="adm-region-city">主要城市（选填）</label>
            <input id="adm-region-city" v-model="form.city" class="input" maxlength="32" placeholder="例如 纽约" />
          </div>
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--primary" :disabled="opening">{{ opening ? "正在开通…" : "开通" }}</button>
        </div>
      </form>
    </section>

    <section v-if="data" class="adm-panel">
      <h2>已有国家</h2>
      <div class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>国家</th><th>主要城市</th><th class="adm-num">官方频道</th><th>状态</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in data.items" :key="item.code">
              <td>
                <strong>{{ item.name }}</strong>
                <span class="adm-sub adm-mono">{{ item.code }}</span>
              </td>
              <td class="adm-nowrap">{{ item.city || "—" }}</td>
              <td class="adm-num"><RouterLink to="/admin/channels">{{ item.channel_count }}</RouterLink></td>
              <td>
                <span class="tag" :class="item.is_open ? 'tag--good' : 'tag--danger'">{{ item.is_open ? "已开通" : "已关闭" }}</span>
                <span v-if="item.code === 'GLOBAL'" class="adm-sub">各国共享</span>
              </td>
              <td>
                <div class="adm-actions">
                  <button v-if="adminMe.is_super && item.is_open" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.code" @click="fill(item)">补齐默认频道</button>
                  <!-- 国际频道各国共享，不能关 -->
                  <button v-if="adminMe.is_super && item.is_open && item.code !== 'GLOBAL'" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.code" @click="close(item)">关闭</button>
                  <button v-if="adminMe.is_super && !item.is_open" type="button" class="btn btn--outline btn--sm" :disabled="busy === item.code" @click="reopen(item)">重新开通</button>
                  <button v-if="adminMe.is_super && item.code !== 'GLOBAL'" type="button" class="btn btn--danger btn--sm" :disabled="busy === item.code" @click="remove(item)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section v-if="data && data.requests.length" class="adm-panel">
      <h2>用户申请开通的国家</h2>
      <div class="adm-scroll">
        <table class="adm-table">
          <thead>
            <tr><th>国家代码</th><th class="adm-num">申请人数</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="item in data.requests" :key="item.code">
              <td class="adm-mono">{{ item.code }}</td>
              <td class="adm-num">{{ item.count }}</td>
              <td>
                <div class="adm-actions">
                  <button v-if="adminMe.is_super" type="button" class="btn btn--outline btn--sm" @click="prefill(item.code)">填到开通表单</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>
