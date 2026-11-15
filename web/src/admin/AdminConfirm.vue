<script setup lang="ts">
// 二次确认弹窗：下架、封禁等操作前确认，并可填写理由。
import { nextTick, ref, watch } from "vue";
import { confirmState, settleConfirm } from "./confirm";

const reason = ref("");
const panel = ref<HTMLElement | null>(null);

watch(
  () => confirmState.open,
  async (open) => {
    if (!open) return;
    reason.value = "";
    await nextTick();
    // 有理由框就先聚焦它，否则聚焦"取消"，免得回车误触危险操作
    (panel.value?.querySelector("textarea, .adm-modal-cancel") as HTMLElement | null)?.focus();
  },
);
</script>

<template>
  <div v-if="confirmState.open" class="adm-overlay" @click.self="settleConfirm(null)" @keydown.esc="settleConfirm(null)">
    <div ref="panel" class="adm-modal" role="dialog" aria-modal="true" aria-labelledby="adm-confirm-title">
      <h2 id="adm-confirm-title">{{ confirmState.options.title }}</h2>
      <p v-if="confirmState.options.message">{{ confirmState.options.message }}</p>
      <div v-if="confirmState.options.reason" class="field">
        <label for="adm-confirm-reason">理由（选填，会记入操作日志）</label>
        <textarea id="adm-confirm-reason" v-model="reason" class="input" rows="3" maxlength="300"></textarea>
      </div>
      <div class="adm-modal-actions">
        <button type="button" class="btn btn--outline adm-modal-cancel" @click="settleConfirm(null)">取消</button>
        <button
          type="button"
          class="btn"
          :class="confirmState.options.danger ? 'btn--danger' : 'btn--primary'"
          @click="settleConfirm(reason.trim())"
        >
          {{ confirmState.options.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
