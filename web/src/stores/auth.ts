// 登录态 store：集中管理 token、登录状态与当前用户基本信息。
// 与 api.ts 的 token 读写保持一致（localStorage "ukcn.token"）。
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { clearToken, getToken, setToken, request, onAuthCleared, onTokenChangedElsewhere, type MeProfile } from "../api";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(getToken());

  const isLoggedIn = computed(() => token.value.length > 0);

  // 当前用户基本信息（名字 + 用户名），登录后通过 /me 拉取
  const profile = ref<MeProfile | null>(null);
  const displayName = computed(() => profile.value?.display_name ?? "");
  const handle = computed(() => profile.value?.handle ?? "");

  async function refreshProfile(): Promise<void> {
    if (!isLoggedIn.value) {
      profile.value = null;
      return;
    }
    try {
      profile.value = await request<MeProfile>("/api/v1/me");
    } catch {
      profile.value = null;
    }
  }

  function login(value: string): void {
    setToken(value);
    token.value = value;
  }

  function logout(): void {
    clearToken();
    token.value = "";
    profile.value = null;
  }

  // refresh token 失效被 api.ts 清除时，同步本地登录态，避免 UI 显示「已登录」但请求已 401。
  onAuthCleared(() => {
    token.value = "";
    profile.value = null;
  });

  // 其他标签页登录或登出后，这个标签页跟着同步。
  onTokenChangedElsewhere(() => {
    token.value = getToken();
    if (!token.value) profile.value = null;
  });

  return { token, isLoggedIn, profile, displayName, handle, login, logout, refreshProfile };
});
