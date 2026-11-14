<script setup lang="ts">
// 常驻举报入口（MASTER §7.4 / §12.1）：内容 / 用户 / 频道 / 房间留言四类目标。
// 提交后显示受理编号与 24h SLA；原因与补充说明对齐后端 REASONS 校验。
import { computed, ref } from "vue";
import { request, jsonBody, type ReportReason, type ReportReceipt } from "../../api";
import { useToastStore } from "../../stores/toast";
import BaseButton from "../base/BaseButton.vue";
import BaseIcon from "../base/BaseIcon.vue";
import BaseTag from "../base/BaseTag.vue";
import Modal from "../base/Modal.vue";
import SelectField from "../base/SelectField.vue";
import TextArea from "../base/TextArea.vue";

const props = withDefaults(
  defineProps<{
    kind: "content" | "user" | "channel" | "comment";
    id: string;
    channelId?: string;
    compact?: boolean;
    label?: string;
  }>(),
  { channelId: "", compact: false, label: "举报" },
);

const toast = useToastStore();
const emit = defineEmits<{ (e: "reported", caseId: string): void }>();

const REASONS: { value: ReportReason; label: string }[] = [
  { value: "scam", label: "诈骗、虚假信息或可疑交易" },
  { value: "harass", label: "骚扰、仇恨或人身攻击" },
  { value: "sexual", label: "色情内容或未成年人风险" },
  { value: "ip", label: "侵犯版权或盗用内容" },
  { value: "privacy", label: "泄露他人隐私" },
  { value: "other", label: "其他问题" },
];

const open = ref(false);
const reason = ref<string>("scam");
const detail = ref("");
const busy = ref(false);
const error = ref("");
const receipt = ref<ReportReceipt | null>(null);

const modalId = computed(() => `report-modal-${props.kind}-${props.id}`);
const endpoint = computed(() => {
  switch (props.kind) {
    case "user":
      return `/api/v1/users/${props.id}/report`;
    case "channel":
      return `/api/v1/channels/${props.id}/report`;
    case "comment":
      return `/api/v1/channels/${props.channelId}/comments/${props.id}/report`;
    default:
      return `/api/v1/contents/${props.id}/report`;
  }
});

function openDialog(): void {
  error.value = "";
  open.value = true;
}

async function submit(): Promise<void> {
  if (reason.value === "other" && detail.value.trim().length < 4) {
    error.value = "选择「其他问题」时请补充至少 4 个字的说明";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    const body = await request<ReportReceipt>(
      endpoint.value,
      jsonBody({ reason: reason.value, detail: detail.value.trim() }),
    );
    receipt.value = body;
    emit("reported", body.case_id);
    open.value = false;
    toast.show(`已受理（${body.case_id.slice(0, 8)}）· ${body.sla}`);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "举报没有提交成功";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <span class="report-wrap">
    <button
      type="button"
      class="report-trigger"
      :class="{ compact }"
      :aria-label="label === '举报' ? '举报这条内容' : label"
      :aria-haspopup="receipt ? undefined : 'dialog'"
      :disabled="!!receipt"
      @click="openDialog"
    >
      <template v-if="receipt">已受理</template>
      <template v-else-if="compact"><BaseIcon name="i-flag" :size="16" /></template>
      <template v-else><BaseIcon name="i-flag" :size="16" /> {{ label }}</template>
    </button>

    <span v-if="receipt" class="report-receipt">
      <BaseTag variant="good">{{ receipt.reason_text }}</BaseTag>
      <span class="sla">{{ receipt.sla }}</span>
    </span>

    <Modal :open="open" title="举报这条内容" :labelledby="modalId" @close="open = false">
      <form class="report-form" @submit.prevent="submit">
        <p class="form-note">举报会进入审核队列，违法内容 24 小时内处理；请勿重复提交。</p>
        <SelectField
          :id="`${modalId}-reason`"
          v-model="reason"
          label="举报原因"
          :options="REASONS"
          placeholder="请选择原因"
        />
        <TextArea
          :id="`${modalId}-detail`"
          v-model="detail"
          label="补充说明（选填，最多 300 字）"
          :rows="3"
          hint="选择「其他问题」时必填至少 4 个字"
        />
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <div class="form-actions">
          <BaseButton type="submit" :loading="busy" variant="danger">提交举报</BaseButton>
          <BaseButton type="button" variant="ghost" @click="open = false">取消</BaseButton>
        </div>
      </form>
    </Modal>
  </span>
</template>

<style scoped>
.report-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.report-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--sp-1);
  min-height: var(--tap);
  min-width: var(--tap);
  padding: 0 var(--sp-2);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--text);
  font-size: var(--fs-12);
  white-space: nowrap;
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out), background-color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out), transform var(--dur-fast) var(--ease-out);
}
.report-trigger:hover:not(:disabled) {
  color: var(--danger);
  border-color: var(--danger);
  background: var(--danger-soft);
}
.report-trigger:active:not(:disabled) {
  transform: scale(0.96);
}
.report-trigger.compact {
  min-width: var(--tap);
  padding: 0;
  border: 0;
}
.report-trigger:disabled {
  opacity: 0.65;
  cursor: default;
}
.report-receipt {
  display: inline-flex;
  align-items: center;
  gap: var(--sp-1);
}
.sla {
  font-size: var(--fs-11);
  color: var(--muted);
}
.report-form {
  display: grid;
  gap: var(--sp-3);
}
.form-note {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
  line-height: 1.6;
}
.form-error {
  margin: 0;
  font-size: var(--fs-13);
  color: var(--danger);
}
.form-actions {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
</style>
