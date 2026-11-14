<script setup lang="ts">
// 全局登录提示弹窗：由 loginPrompt store 控制开关，内容复用「我的」页的账号面板。
import Modal from "../base/Modal.vue";
import AccountPanel from "../profile/AccountPanel.vue";
import { useLoginPromptStore } from "../../stores/loginPrompt";

const prompt = useLoginPromptStore();
</script>

<template>
  <Modal :open="prompt.open" title="登录或注册海外圈" labelledby="login-prompt-title" @close="prompt.close()">
    <p v-if="prompt.reason" class="login-reason">{{ prompt.reason }}</p>
    <AccountPanel v-if="prompt.open" />
  </Modal>
</template>

<style scoped>
.login-reason {
  margin: 0 0 var(--sp-3);
  color: var(--muted);
  font-size: var(--fs-13);
}
</style>
