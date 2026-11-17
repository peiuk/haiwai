<script setup lang="ts">
import { onMounted, ref } from "vue";
import { jsonBody, request, toMessage, uploadFile } from "../../api";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import { useThemeStore } from "../../stores/theme";
import Avatar from "../base/Avatar.vue";
import BaseButton from "../base/BaseButton.vue";
import TextArea from "../base/TextArea.vue";
import TextField from "../base/TextField.vue";

type Profile = {
  user_id: string;
  display_name: string;
  handle: string;
  avatar_tone: string;
  avatar_key: string;
  city_label: string;
  bio: string;
};

const auth = useAuthStore();
const toast = useToastStore();
const theme = useThemeStore();
const profile = ref<Profile | null>(null);
const loading = ref(true);
const saving = ref(false);
const editing = ref(false);
const error = ref("");
const name = ref("");
const handle = ref("");
const city = ref("");
const bio = ref("");

async function load(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    profile.value = await request<Profile>("/api/v1/me");
    resetFields();
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    loading.value = false;
  }
}

function resetFields(): void {
  name.value = profile.value?.display_name ?? "";
  handle.value = profile.value?.handle ?? "";
  city.value = profile.value?.city_label ?? "";
  bio.value = profile.value?.bio ?? "";
}

function cancel(): void {
  resetFields();
  editing.value = false;
  error.value = "";
}

async function save(): Promise<void> {
  if (!profile.value || saving.value) return;
  error.value = "";
  const displayName = name.value.trim();
  const accountName = handle.value.trim().replace(/^@/, "").toLowerCase();
  if (!displayName || displayName.length > 40) {
    error.value = "显示名需要 1 到 40 个字";
    return;
  }
  if (accountName && !/^[a-z0-9._]{1,20}$/.test(accountName)) {
    error.value = "账号名只能用 1 到 20 位字母、数字、点或下划线";
    return;
  }
  if (!accountName && profile.value.handle) {
    error.value = "账号名不能清空";
    return;
  }
  if (city.value.trim().length > 12 || /\s/.test(city.value.trim())) {
    error.value = "城市需要 1 到 12 个字，不能有空格";
    return;
  }
  if (bio.value.trim().length > 250) {
    error.value = "个人介绍最多 250 个字";
    return;
  }
  saving.value = true;
  try {
    const payload: Record<string, string> = { display_name: displayName, city_label: city.value.trim(), bio: bio.value.trim() };
    if (accountName) payload.handle = accountName;
    profile.value = await request<Profile>("/api/v1/me", { ...jsonBody(payload), method: "PATCH" });
    editing.value = false;
    toast.show("个人资料已保存");
  } catch (err) {
    error.value = toMessage(err);
  } finally {
    saving.value = false;
  }
}

// ---- 头像：选图即上传并保存，不用再点「保存资料」 ----
const avatarBusy = ref(false);

async function setAvatar(key: string): Promise<void> {
  profile.value = await request<Profile>("/api/v1/me", { ...jsonBody({ avatar_key: key }), method: "PATCH" });
  void auth.refreshProfile(); // 侧栏、发帖框里的头像跟着换
}

async function onAvatarFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || avatarBusy.value) return;
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type) || file.size > 5_000_000) {
    toast.show("头像只接受 jpeg / png / webp，不超过 5MB");
    return;
  }
  avatarBusy.value = true;
  try {
    await setAvatar(await uploadFile(file));
    toast.show("头像已更新");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    avatarBusy.value = false;
  }
}

async function removeAvatar(): Promise<void> {
  if (avatarBusy.value) return;
  avatarBusy.value = true;
  try {
    await setAvatar("");
    toast.show("头像已移除");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    avatarBusy.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="profile-card" aria-label="个人资料">
    <p v-if="loading" class="muted">正在加载个人资料…</p>
    <div v-else-if="profile" class="profile-card__body">
      <div class="profile-card__identity">
        <!-- 头像、昵称去个人主页，城市去搜「#城市」，链接不能互相嵌套所以分开 -->
        <div class="profile-card__link">
          <RouterLink :to="{ name: 'user', params: { id: profile.user_id } }" aria-label="查看我的个人主页">
            <Avatar :name="profile.display_name" :size="56" :tone="profile.avatar_tone" :image="profile.avatar_key" />
          </RouterLink>
          <div class="profile-card__name">
            <RouterLink class="name" :to="{ name: 'user', params: { id: profile.user_id } }" data-ugc>{{ profile.display_name }}</RouterLink>
            <span class="sub">{{ profile.handle ? `@${profile.handle}` : "尚未设置账号名" }}<template v-if="profile.city_label"> · <RouterLink class="profile-card__city" :to="{ name: 'search', query: { q: `#${profile.city_label}` } }">{{ profile.city_label }}</RouterLink></template> · {{ theme.lang === 'zh-Hant' ? '繁體' : '简体' }}</span>
          </div>
        </div>
        <BaseButton v-if="!editing" variant="outline" size="sm" @click="editing = true">编辑资料</BaseButton>
      </div>
      <div v-if="editing" class="profile-card__actions">
        <label class="profile-card__pick" :class="{ 'is-busy': avatarBusy }">
          {{ avatarBusy ? "正在上传…" : profile.avatar_key ? "更换头像" : "上传头像" }}
          <input id="profile-avatar" class="sr-only" type="file" accept="image/jpeg,image/png,image/webp" :disabled="avatarBusy" @change="onAvatarFile" />
        </label>
        <BaseButton v-if="profile.avatar_key" variant="ghost" size="sm" :disabled="avatarBusy" @click="removeAvatar">移除头像</BaseButton>
      </div>
      <form v-if="editing" class="profile-card__form" @submit.prevent="save">
        <TextField id="profile-name" v-model="name" label="显示名" required />
        <TextField id="profile-handle" v-model="handle" label="账号名" placeholder="例如 overseas_uk" hint="字母、数字、点和下划线；设置后可用于 @ 提及" />
        <TextField id="profile-city" v-model="city" label="所在城市" placeholder="例如 London" />
        <TextArea id="profile-bio" v-model="bio" label="个人介绍" :rows="3" :maxlength="250" placeholder="介绍一下自己，显示在你的主页上（最多 250 字）" />
        <p v-if="error" class="error" role="alert">{{ error }}</p>
        <div class="profile-card__actions">
          <BaseButton type="submit" size="sm" :loading="saving">保存资料</BaseButton>
          <BaseButton variant="ghost" size="sm" :disabled="saving" @click="cancel">取消</BaseButton>
        </div>
      </form>
    </div>
    <div v-else>
      <p class="error" role="alert">{{ error || "个人资料加载失败" }}</p>
      <BaseButton variant="outline" size="sm" @click="load">重试</BaseButton>
    </div>
  </section>
</template>

<style scoped>
.profile-card {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 18px 16px;
  border-bottom: 1px solid var(--border);
}
.profile-card__body { display: grid; gap: var(--sp-4); flex: 1; min-width: 0; }
.profile-card__identity { display: flex; align-items: center; gap: 14px; }
.profile-card__link { display: flex; align-items: center; gap: 14px; flex: 1; min-width: 0; }
.profile-card__name .name, .profile-card__city { color: inherit; text-decoration: none; }
.profile-card__name .name:hover, .profile-card__city:hover { text-decoration: underline; }
.profile-card__name { display: grid; gap: 2px; min-width: 0; flex: 1; overflow-wrap: anywhere; }
.profile-card__name .name { font-size: 19px; font-weight: 800; }
.profile-card__name .sub { font-size: 13px; color: var(--muted); }
.profile-card__form { max-width: 30rem; }
.profile-card__actions { display: flex; gap: var(--sp-2); align-items: center; }
.profile-card__pick {
  padding: 6px 14px;
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: 13px;
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.profile-card__pick:focus-within { outline: 2px solid var(--accent); outline-offset: 2px; }
.profile-card__pick.is-busy { opacity: 0.6; cursor: default; }
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
.muted { margin: 0; color: var(--muted); font-size: var(--fs-12); }
.error { margin: 0; color: var(--danger); font-size: var(--fs-12); }
</style>
