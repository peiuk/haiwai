<script setup lang="ts">
// 后台独立登录页：只接受管理员账号，登录状态和前台分开保存。
import { ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiRequestError, toMessage } from "../api";
import { adminLogin } from "./adminApi";
import "./admin.css";

const route = useRoute();
const router = useRouter();
const email = ref("");
const password = ref("");
const error = ref("");
const code = ref("");
const needCode = ref(false); // 账号开了两步验证：第一次提交后才知道，知道了就显示验证码输入框
const submitting = ref(false);

async function submit(): Promise<void> {
  if (submitting.value) return;
  submitting.value = true;
  error.value = "";
  try {
    await adminLogin(email.value.trim(), password.value, code.value);
    // 只接受站内的后台路径，避免被带到别处
    const next = typeof route.query.next === "string" && route.query.next.startsWith("/admin") ? route.query.next : "/admin";
    await router.replace(next);
  } catch (err) {
    if (err instanceof ApiRequestError && err.code.startsWith("TOTP_")) needCode.value = true;
    error.value = toMessage(err);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="adm-login">
    <form class="adm-login-card" @submit.prevent="submit">
      <h1>海外圈后台</h1>
      <p>仅限管理员登录。</p>
      <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>
      <div class="field">
        <label for="adm-email">邮箱</label>
        <input id="adm-email" v-model="email" class="input" type="email" autocomplete="username" required />
      </div>
      <div class="field">
        <label for="adm-password">密码</label>
        <input id="adm-password" v-model="password" class="input" type="password" autocomplete="current-password" required />
      </div>
      <div v-if="needCode" class="field">
        <label for="adm-code">两步验证码（验证器 App 上的 6 位数字）</label>
        <input id="adm-code" v-model="code" class="input" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required />
      </div>
      <button type="submit" class="btn btn--primary" :disabled="submitting">{{ submitting ? "正在登录…" : "登录" }}</button>
      <a class="adm-login-back" href="/">返回前台</a>
    </form>
  </div>
</template>
