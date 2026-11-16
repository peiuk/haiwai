<script setup lang="ts">
// 账号面板：登录 / 注册 / 手机验证 / 退出，补齐 Phase 1 改壳后丢失的登录入口。
// 令牌对（access + refresh）统一经 setSession 写入，退出时同时吊销 refresh 会话。
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import {
  clearToken,
  getRefreshToken,
  jsonBody,
  request,
  setSession,
  toMessage,
  type MeProfile,
  type LoginResponse,
} from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useThemeStore } from "../../stores/theme";
import { useToastStore } from "../../stores/toast";
import BaseButton from "../base/BaseButton.vue";
import Checkbox from "../base/Checkbox.vue";
import TextField from "../base/TextField.vue";

const auth = useAuthStore();
const theme = useThemeStore();
const toast = useToastStore();
const supportContact = (import.meta.env.VITE_SUPPORT_CONTACT ?? "").trim();

const mode = ref<"login" | "register">("login");
const email = ref("");
const password = ref("");
const displayName = ref("");
const city = ref("");
const agreedAll = ref(false);
const phone = ref("");
const phoneCode = ref("");
const busy = ref(false);
const error = ref("");
const profile = ref<MeProfile | null>(null);

async function loadProfile(): Promise<void> {
  if (!auth.isLoggedIn) {
    profile.value = null;
    return;
  }
  try {
    profile.value = await request<MeProfile>("/api/v1/me");
  } catch {
    profile.value = null;
  }
}

async function submitAuth(): Promise<void> {
  error.value = "";
  if (!email.value.trim() || !password.value.trim()) {
    error.value = "邮箱和密码都要填写";
    return;
  }
  if (mode.value === "register") {
    if (!displayName.value.trim()) {
      error.value = "请填写显示名";
      return;
    }
    if (!agreedAll.value) {
      error.value = "注册需要同意服务条款与隐私政策";
      return;
    }
  }
  busy.value = true;
  try {
    const payload: Record<string, unknown> = {
      email: email.value.trim(),
      password: password.value,
    };
    if (mode.value === "register") {
      payload.display_name = displayName.value.trim();
      const cityLabel = city.value.trim();
      if (cityLabel && (cityLabel.length > 12 || /\s/.test(cityLabel))) {
        error.value = "城市需要 1 到 12 个字，不能有空格";
        busy.value = false;
        return;
      }
      if (cityLabel) payload.city_code = cityLabel;
      payload.script_pref = theme.lang === "zh-Hant" ? "hant" : "hans";
      payload.consents = [
        { purpose: "tos", version: "v1", granted: agreedAll.value },
        { purpose: "privacy", version: "v1", granted: agreedAll.value },
      ];
    }
    const body = await request<LoginResponse>(
      mode.value === "register" ? "/api/v1/auth/register" : "/api/v1/auth/login",
      jsonBody(payload),
      false,
    );
    setSession(body);
    auth.login(body.access_token);
    password.value = "";
    toast.show(mode.value === "register" ? "注册成功，已登录" : "登录成功");
    await loadProfile();
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    busy.value = false;
  }
}

async function verifyPhone(): Promise<void> {
  if (!phone.value.trim() || !phoneCode.value.trim()) {
    error.value = "请填写手机号与验证码";
    return;
  }
  busy.value = true;
  error.value = "";
  try {
    await request("/api/v1/auth/verify-phone", jsonBody({ phone: phone.value.trim(), code: phoneCode.value.trim() }));
    toast.show("手机号已验证，可以发布内容了");
    await loadProfile();
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    busy.value = false;
  }
}

async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  try {
    if (refresh) {
      await request("/api/v1/auth/logout", jsonBody({ refresh_token: refresh }), false);
    }
  } catch {
    // 吊销失败也要清理本地登录态
  }
  clearToken();
  auth.logout();
  profile.value = null;
  toast.show("已退出登录");
}

onMounted(loadProfile);
</script>

<template>
  <section class="account-panel" aria-label="账号">
    <template v-if="!auth.isLoggedIn">
      <div class="mode-switch" role="tablist" aria-label="账号操作">
        <button
          type="button"
          role="tab"
          class="mode-btn"
          :class="{ active: mode === 'login' }"
          :aria-selected="mode === 'login'"
          @click="mode = 'login'"
        >登录</button>
        <button
          type="button"
          role="tab"
          class="mode-btn"
          :class="{ active: mode === 'register' }"
          :aria-selected="mode === 'register'"
          @click="mode = 'register'"
        >注册</button>
      </div>

      <form class="account-form" @submit.prevent="submitAuth">
        <p class="form-lead">
          {{ mode === "login" ? "欢迎回来，登录后继续。" : "创建一个账号，几秒就能加入社区。" }}
        </p>

        <TextField id="account-email" v-model="email" label="邮箱" type="email" autocomplete="email" placeholder="you@example.com" required />
        <TextField
          id="account-password"
          v-model="password"
          label="密码"
          type="password"
          :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
          :hint="mode === 'register' ? '至少 8 位' : ''"
          required
        />

        <template v-if="mode === 'register'">
          <TextField id="account-name" v-model="displayName" label="显示名" placeholder="其他用户看到的昵称" required />
          <TextField id="account-city" v-model="city" label="所在城市" placeholder="例如 London，选填" hint="填写后发帖会自动带上你的城市话题" />
          <div class="consent-group" role="group" aria-label="协议确认">
            <Checkbox id="account-agree" v-model="agreedAll" label="我已阅读并同意服务条款与隐私政策（v1）" />
            <p class="consent-links">
              <RouterLink :to="{ name: 'legal', params: { section: 'tos' } }">服务条款</RouterLink>
              <span aria-hidden="true">·</span>
              <RouterLink :to="{ name: 'legal', params: { section: 'privacy' } }">隐私政策</RouterLink>
              <span aria-hidden="true">·</span>
              <RouterLink :to="{ name: 'legal', params: { section: 'cookie' } }">Cookie 政策</RouterLink>
            </p>
          </div>
        </template>

        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <BaseButton type="submit" :loading="busy" class="submit-btn">
          {{ mode === "login" ? "登录" : "注册并登录" }}
        </BaseButton>
        <p v-if="mode === 'login'" class="account-meta">忘记密码？请联系{{ supportContact ? `平台（${supportContact}）` : "平台管理员" }}，对方会给你一个一次性的重置链接。</p>
      </form>
    </template>

    <template v-else>
      <div class="account-summary">
        <strong>{{ profile?.display_name || "已登录" }}</strong>
        <span v-if="profile" class="account-meta">
          {{ profile.email }}<template v-if="profile.handle"> · @{{ profile.handle }}</template>
        </span>
        <span v-if="profile?.phone" class="account-meta">手机已验证：{{ profile.phone }}</span>
        <span v-else class="account-meta">手机未验证 · 发布内容前需完成验证</span>
      </div>

      <form v-if="!profile?.phone" class="phone-form" @submit.prevent="verifyPhone">
        <TextField id="account-phone" v-model="phone" label="手机号" type="tel" placeholder="+44..." required />
        <TextField id="account-code" v-model="phoneCode" label="验证码" hint="开发环境验证码 246810" required />
        <BaseButton type="submit" variant="outline" size="sm" :loading="busy" class="submit-btn">验证手机</BaseButton>
      </form>

      <div class="account-footer">
        <p v-if="error" class="form-error" role="alert">{{ error }}</p>
        <BaseButton type="button" variant="ghost" size="sm" @click="logout">退出登录</BaseButton>
      </div>
    </template>
  </section>
</template>

<style scoped>
.account-panel {
  display: grid;
  gap: 0;
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  overflow: hidden;
}
.mode-switch {
  display: grid;
  grid-template-columns: 1fr 1fr;
  border-bottom: 1px solid var(--border);
  background: var(--bg);
}
.mode-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-3);
  border: 0;
  border-bottom: 3px solid transparent;
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
  cursor: pointer;
  transition: color var(--dur-fast) var(--ease-out),
    border-color var(--dur-fast) var(--ease-out);
}
.mode-btn:hover {
  color: var(--text);
}
.mode-btn.active {
  color: var(--text);
  border-bottom-color: var(--accent);
}
.account-form,
.phone-form {
  display: grid;
  gap: var(--sp-4);
  padding: var(--sp-5) var(--sp-5) var(--sp-6);
}
.form-lead {
  margin: 0;
  padding-bottom: var(--sp-2);
  border-bottom: 1px solid var(--border);
  color: var(--muted);
  font-size: var(--fs-13);
  line-height: var(--lh-body);
}
.consent-group {
  display: grid;
  gap: var(--sp-2);
  padding: var(--sp-3) var(--sp-3) var(--sp-3) var(--sp-4);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--bg);
}
.consent-group :deep(.check) {
  min-height: var(--tap);
  align-items: center;
}
.consent-links {
  margin: 0;
  padding-left: 28px;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-1);
  font-size: var(--fs-12);
  color: var(--muted);
}
.consent-links a {
  color: var(--accent-strong);
  text-decoration: none;
}
.consent-links a:hover {
  text-decoration: underline;
}
.submit-btn {
  width: 100%;
  justify-self: stretch;
  margin-top: var(--sp-1);
}
.account-summary {
  display: grid;
  gap: var(--sp-1);
  padding: var(--sp-5) var(--sp-5) var(--sp-4);
  font-size: var(--fs-14);
}
.phone-form {
  border-top: 1px solid var(--border);
}
.account-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) var(--sp-5) var(--sp-5);
  border-top: 1px solid var(--border);
}
.account-footer .form-error {
  flex: 1;
}
.account-meta,
.form-error {
  font-size: var(--fs-12);
}
.account-meta {
  color: var(--muted);
}
.form-error {
  margin: 0;
  color: var(--danger);
}
</style>
