<script setup lang="ts">
// 邮件设置：网站发信用的邮箱（SMTP）。现在用它发「忘记密码」的重置邮件。
import { reactive, ref } from "vue";
import { jsonBody, toMessage } from "../api";
import { useToastStore } from "../stores/toast";
import { adminRequest } from "./adminApi";

type MailSettings = { host: string; port: number; ssl: boolean; user: string; from_name: string; site_url: string; password_set: boolean };

const URL = "/api/v1/admin/mail-settings";
const toast = useToastStore();
const form = reactive({ host: "", port: 465, ssl: true, user: "", password: "", from_name: "", site_url: "" });
const passwordSet = ref(false);
const testTo = ref("");
const busy = ref(false);
const error = ref("");

/** 授权码不会从服务器回来：输入框清空，只记「填没填过」。网站地址没填过就先用当前这个。 */
function fill(data: MailSettings): void {
  const { password_set, ...rest } = data;
  Object.assign(form, rest, { password: "", site_url: rest.site_url || window.location.origin });
  passwordSet.value = password_set;
}

async function run(task: () => Promise<void>): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  error.value = "";
  try {
    await task();
  } catch (err) {
    error.value = toMessage(err);
    toast.show(error.value); // 出错提示在页面顶部，点下面的「发送测试邮件」时可能已经滚出屏幕
  } finally {
    busy.value = false;
  }
}

void run(async () => fill(await adminRequest<MailSettings>(URL)));

function save(): Promise<void> {
  return run(async () => {
    fill(await adminRequest<MailSettings>(URL, jsonBody(form)));
    toast.show("邮件设置已保存");
  });
}

function sendTest(): Promise<void> {
  return run(async () => {
    await adminRequest(`${URL}/test`, jsonBody({ to: testTo.value }));
    toast.show(`测试邮件已发到 ${testTo.value}，收件箱里没有的话看看垃圾箱`);
  });
}
</script>

<template>
  <div>
    <header class="adm-head">
      <h1>邮件设置</h1>
      <p>网站用这个邮箱发信：用户在登录页点「忘记密码」，会收到一封带重置链接的邮件。只有超级管理员能看和改。</p>
    </header>

    <p v-if="error" class="notice notice--danger" role="alert">{{ error }}</p>

    <section class="adm-panel">
      <h2>发信邮箱（SMTP）</h2>
      <form class="adm-form" @submit.prevent="save">
        <p class="adm-sub">
          先到邮箱的网页版设置里开启「POP3/SMTP 服务」，拿到一串授权码填在下面（不是邮箱的登录密码）。QQ 邮箱：smtp.qq.com；163 邮箱：smtp.163.com；端口都是 465。
        </p>
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-mail-host">SMTP 服务器</label>
            <input id="adm-mail-host" v-model.trim="form.host" class="input" maxlength="120" placeholder="smtp.qq.com" required />
          </div>
          <div class="field">
            <label for="adm-mail-ssl">加密方式</label>
            <select id="adm-mail-ssl" v-model="form.ssl" class="input" @change="form.port = form.ssl ? 465 : 587">
              <option :value="true">SSL（一般是 465 端口）</option>
              <option :value="false">STARTTLS（一般是 587 端口）</option>
            </select>
          </div>
          <div class="field">
            <label for="adm-mail-port">端口</label>
            <input id="adm-mail-port" v-model.number="form.port" class="input" type="number" min="1" max="65535" required />
          </div>
        </div>
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-mail-user">邮箱账号（也是发件地址）</label>
            <input id="adm-mail-user" v-model.trim="form.user" class="input" type="email" maxlength="120" autocomplete="off" placeholder="noreply@example.com" required />
          </div>
          <div class="field">
            <label for="adm-mail-password">授权码</label>
            <input
              id="adm-mail-password"
              v-model="form.password"
              class="input"
              type="password"
              maxlength="200"
              autocomplete="new-password"
              :placeholder="passwordSet ? '已设置，留空表示不改' : '开启 SMTP 时拿到的授权码'"
              :required="!passwordSet"
            />
          </div>
        </div>
        <div class="adm-form-row">
          <div class="field">
            <label for="adm-mail-name">发件人名称（收件人看到的名字，可不填）</label>
            <input id="adm-mail-name" v-model.trim="form.from_name" class="input" maxlength="40" placeholder="海外圈" />
          </div>
          <div class="field">
            <label for="adm-mail-site">网站地址（邮件里的重置链接以它开头，结尾不带 /）</label>
            <input id="adm-mail-site" v-model.trim="form.site_url" class="input" type="url" maxlength="120" pattern="https?://[^/\s]+" placeholder="https://example.com" required />
          </div>
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--primary" :disabled="busy">保存</button>
        </div>
      </form>
    </section>

    <section class="adm-panel">
      <h2>发一封测试邮件</h2>
      <form class="adm-form" @submit.prevent="sendTest">
        <p class="adm-sub">用已经保存的设置发。上面改过的话先点保存。</p>
        <div class="field">
          <label for="adm-mail-to">收件邮箱</label>
          <input id="adm-mail-to" v-model.trim="testTo" class="input" type="email" maxlength="255" placeholder="填一个你能收信的邮箱" required />
        </div>
        <div class="adm-form-actions">
          <button type="submit" class="btn btn--outline" :disabled="busy || !passwordSet">{{ busy ? "请稍候…" : "发送测试邮件" }}</button>
        </div>
      </form>
    </section>
  </div>
</template>
