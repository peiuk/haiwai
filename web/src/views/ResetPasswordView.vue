<script setup lang="ts">
// 重置密码：用户打开管理员给的一次性链接（?token=…），设置新密码。
import { computed, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";
import { jsonBody, request, toMessage } from "../api";
import "../admin/admin.css"; // 复用居中卡片样式（类名带 adm- 前缀，不影响其他页面）

const route = useRoute();
const token = computed(() => (typeof route.query.token === "string" ? route.query.token : ""));
const password = ref("");
const again = ref("");
const error = ref("");
const done = ref(false);
const submitting = ref(false);

async function submit(): Promise<void> {
  if (submitting.value) return;
  if (password.value !== again.value) {
    error.value = "两次输入的密码不一样";
    return;
  }
  submitting.value = true;
  error.value = "";
  try {
    await request("/api/v1/auth/reset-password", jsonBody({ token: token.value, password: password.value }));
    done.value = true;
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="adm-login">
    <div v-if="done" class="adm-login-card">
      <h1>密码已重置</h1>
      <p>其他设备上的登录已全部退出，请用新密码重新登录。</p>
      <RouterLink class="btn btn--primary" :to="{ name: 'profile' }">去登录</RouterLink>
    </div>
    <div v-else-if="!token" class="adm-login-card">
      <h1>链接不完整</h1>
      <p>请打开管理员发给你的完整重置链接。</p>
      <RouterLink class="adm-login-back" to="/">返回首页</RouterLink>
    </div>
    <form v-else class="adm-login-card" @submit.prevent="submit">
      <h1>设置新密码</h1>
      <p>链接只能用一次，24 小时内有效。</p>
      <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
      <div class="field">
        <label for="reset-password">新密码（至少 8 位）</label>
        <input id="reset-password" v-model="password" class="input" type="password" autocomplete="new-password" minlength="8" required />
      </div>
      <div class="field">
        <label for="reset-again">再输一次</label>
        <input id="reset-again" v-model="again" class="input" type="password" autocomplete="new-password" minlength="8" required />
      </div>
      <button type="submit" class="btn btn--primary" :disabled="submitting">{{ submitting ? "正在保存…" : "保存新密码" }}</button>
    </form>
  </div>
</template>
