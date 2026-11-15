<script setup lang="ts">
// 二次确认弹窗：下架、封禁等操作前确认，并可填写理由。
import { nextTick, ref, watch } from "vue";
import { confirmExtras, confirmState, settleConfirm } from "./confirm";

const reason = ref("");
const typed = ref("");
const panel = ref<HTMLElement | null>(null);

watch(
  () => confirmState.open,
  async (open) => {
    if (!open) return;
    reason.value = "";
    typed.value = "";
    confirmExtras.days = "";
    confirmExtras.checked = false;
    await nextTick();
    // 有输入框就先聚焦它，否则聚焦"取消"，免得回车误触危险操作
    (panel.value?.querySelector("input, textarea, .adm-modal-cancel") as HTMLElement | null)?.focus();
  },
);
</script>

<template>
  <div v-if="confirmState.open" class="adm-overlay" @click.self="settleConfirm(null)" @keydown.esc="settleConfirm(null)">
    <div ref="panel" class="adm-modal" role="dialog" aria-modal="true" aria-labelledby="adm-confirm-title">
      <h2 id="adm-confirm-title">{{ confirmState.options.title }}</h2>
      <p v-if="confirmState.options.message">{{ confirmState.options.message }}</p>
      <div v-if="confirmState.options.mustType" class="field">
        <label for="adm-confirm-typed">请输入「{{ confirmState.options.mustType }}」确认</label>
        <input id="adm-confirm-typed" v-model="typed" class="input" autocomplete="off" />
      </div>
      <div v-if="confirmState.options.days" class="field">
        <label for="adm-confirm-days">封禁多久</label>
        <select id="adm-confirm-days" v-model="confirmExtras.days" class="input">
          <option value="">永久（直到手动解封）</option>
          <option value="1">1 天</option>
          <option value="7">7 天</option>
          <option value="30">30 天</option>
        </select>
      </div>
      <label v-if="confirmState.options.checkbox" class="adm-check">
        <input id="adm-confirm-check" v-model="confirmExtras.checked" type="checkbox" />
        {{ confirmState.options.checkbox }}
      </label>
      <div v-if="confirmState.options.reason" class="field">
        <label for="adm-confirm-reason">理由（选填，会记入操作日志，也会告诉当事人）</label>
        <textarea id="adm-confirm-reason" v-model="reason" class="input" rows="3" maxlength="300"></textarea>
      </div>
      <div class="adm-modal-actions">
        <button type="button" class="btn btn--outline adm-modal-cancel" @click="settleConfirm(null)">取消</button>
        <button
          type="button"
          class="btn"
          :class="confirmState.options.danger ? 'btn--danger' : 'btn--primary'"
          :disabled="!!confirmState.options.mustType && typed.trim() !== confirmState.options.mustType"
          @click="settleConfirm(reason.trim())"
        >
          {{ confirmState.options.confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>
