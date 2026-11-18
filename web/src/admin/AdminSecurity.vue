<script setup lang="ts">
// 账号安全：给自己的后台账号开 / 关两步验证。
import { ref } from "vue";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminMe, adminRequest, loadAdminMe } from "./adminApi";

const toast = useToastStore();
type Setup = { secret: string; uri: string; qr_svg: string };
const setup = ref<Setup | null>(null);
const code = ref("");
const busy = ref(false);
const error = ref("");

async function run(task: () => Promise<void>): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await task();
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    busy.value = false;
  }
}

function start(): Promise<void> {
  return run(async () => {
    setup.value = await adminRequest<Setup>("/api/v1/admin/totp/setup", { method: "POST" });
    code.value = "";
  });
}

function enable(): Promise<void> {
  return run(async () => {
    await adminRequest("/api/v1/admin/totp/enable", jsonBody({ secret: setup.value?.secret, code: code.value }));
    setup.value = null;
    code.value = "";
    await loadAdminMe();
    toast.show("两步验证已开启，下次登录后台要输入验证码");
  });
}

function disable(): Promise<void> {
  return run(async () => {
    await adminRequest("/api/v1/admin/totp/disable", jsonBody({ code: code.value }));
    code.value = "";
    await loadAdminMe();
    toast.show("两步验证已关闭");
  });
}

/** 密钥每 4 位空一格，手输时不容易看串行。 */
function spaced(secret: string): string {
  return secret.replace(/(.{4})/g, "$1 ").trim();
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>账号安全</h1>
      <p>两步验证：登录后台除了密码，还要输入手机验证器 App 上的 6 位数字。密码泄露了别人也进不来。</p>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>

    <section class="adm-panel">
      <h2>两步验证：{{ adminMe.two_factor ? "已开启" : "未开启" }}</h2>

      <form v-if="adminMe.two_factor" class="adm-form" @submit.prevent="disable">
        <p class="adm-sub">要关闭的话，输入验证器 App 上当前的验证码。手机丢了请联系能登录服务器的人重置。</p>
        <div class="field">
          <label for="adm-totp-off">验证码</label>
          <input id="adm-totp-off" v-model="code" class="input" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required />
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--danger" :disabled="busy">关闭两步验证</button>
        </div>
      </form>

      <div v-else-if="!setup" class="adm-form">
        <p class="adm-sub">需要手机上装一个验证器 App（Google Authenticator、Microsoft Authenticator、1Password 等都可以）。</p>
        <div class="adm-form-actions">
          <button type="button" class="btn btn--primary" :disabled="busy" @click="start">开始设置</button>
        </div>
      </div>

      <form v-else class="adm-form" @submit.prevent="enable">
        <div class="field">
          <p class="adm-sub">第 1 步：用验证器 App 扫描下面的二维码</p>
          <!-- 二维码 SVG 由后端生成，内容只有我们自己的 otpauth 链接，不含用户输入 -->
          <div class="adm-qr" role="img" aria-label="两步验证二维码" v-html="setup.qr_svg"></div>
        </div>
        <div class="field">
          <label for="adm-totp-secret">扫不了的话，在 App 里选「手动输入密钥」，账户名随意，密钥填下面这串（基于时间）</label>
          <input id="adm-totp-secret" class="input adm-mono" :value="spaced(setup.secret)" readonly @focus="($event.target as HTMLInputElement).select()" />
          <a class="adm-sub" :href="setup.uri">在这台设备上装了验证器 App 的话，点这里直接添加</a>
        </div>
        <div class="field">
          <label for="adm-totp-on">第 2 步：输入 App 上显示的 6 位数字确认</label>
          <input id="adm-totp-on" v-model="code" class="input" inputmode="numeric" autocomplete="one-time-code" maxlength="8" required />
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--primary" :disabled="busy">确认开启</button>
          <button type="button" class="btn btn--outline" @click="setup = null">取消</button>
        </div>
      </form>
    </section>
  </div>
</template>

<style scoped>
.adm-qr {
  justify-self: start;
  line-height: 0;
}
</style>
