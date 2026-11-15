<script setup lang="ts">
// 审核开关：这一类内容（帖子 / 分类信息 / 留言）发布前要不要人工审核。
// 所有管理员都能看到当前状态，只有超级管理员能改（后端同样校验）。
import { ref } from "vue";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminMe, adminRequest } from "./adminApi";
import { confirmAction } from "./confirm";

type Kind = "post" | "listing" | "comment";
const props = defineProps<{ kind: Kind }>();
const NAMES: Record<Kind, string> = { post: "帖子", listing: "分类信息", comment: "留言" };

const toast = useToastStore();
const enabled = ref<boolean | null>(null); // null：还没读到
const busy = ref(false);

async function load(): Promise<void> {
  try {
    enabled.value = (await adminRequest<Record<Kind, boolean>>("/api/v1/admin/review-settings"))[props.kind];
  } catch {
    enabled.value = null; // 读不到就不显示开关，不影响列表
  }
}

async function toggle(): Promise<void> {
  if (busy.value || enabled.value === null) return;
  const name = NAMES[props.kind];
  const turnOff = enabled.value;
  const ok = await confirmAction(
    turnOff
      ? {
          title: `关闭${name}审核？`,
          message: `关闭后用户新发的${name}不用审核，直接公开；命中敏感词的仍会进待审核。已经在待审里的不受影响。`,
          confirmLabel: "关闭审核",
          danger: true,
        }
      : { title: `开启${name}审核？`, message: `开启后用户新发的${name}要先通过审核才公开。`, confirmLabel: "开启审核" },
  );
  if (ok === null) return;
  busy.value = true;
  try {
    const body = await adminRequest<Record<Kind, boolean>>("/api/v1/admin/review-settings", jsonBody({ kind: props.kind, enabled: !turnOff }));
    enabled.value = body[props.kind];
    toast.show(turnOff ? `已关闭${name}审核` : `已开启${name}审核`);
  } catch (err) {
    toast.show(toMessage(err));
    await load();
  } finally {
    busy.value = false;
  }
}

void load();
</script>

<template>
  <span v-if="enabled !== null" class="review-switch">
    <span class="tag" :class="enabled ? 'tag--good' : 'tag--warn'">{{ enabled ? "发布前审核：开" : "发布前审核：关" }}</span>
    <button v-if="adminMe.is_super" type="button" class="btn btn--outline btn--sm" :disabled="busy" @click="toggle">
      {{ enabled ? "关闭审核" : "开启审核" }}
    </button>
  </span>
</template>

<style scoped>
.review-switch {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  margin-left: auto;
}
</style>
