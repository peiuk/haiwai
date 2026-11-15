// 后台专用的登录状态与请求封装。
// 令牌和前台分开存：登录 / 退出后台不影响前台，反过来也一样。
import { ApiRequestError, type ApiError, type LoginResponse } from "../api";

const TOKEN_KEY = "ukcn.admin.token";
const REFRESH_KEY = "ukcn.admin.refresh";
/** 后台登录失效时广播，AdminLayout 收到后跳回登录页。 */
export const ADMIN_SIGNED_OUT = "ukcn:admin-signed-out";
/** 后台做了写操作后广播，AdminLayout 收到后刷新菜单上的待办数字。 */
export const ADMIN_CHANGED = "ukcn:admin-changed";

function read(key: string): string {
  try {
    return localStorage.getItem(key) ?? "";
  } catch {
    return ""; // 存储不可用时按未登录处理
  }
}

function store(tokens: LoginResponse | null): void {
  try {
    if (tokens) {
      localStorage.setItem(TOKEN_KEY, tokens.access_token);
      if (tokens.refresh_token) localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(REFRESH_KEY);
    }
  } catch {
    // 忽略
  }
}

async function toError(response: Response): Promise<ApiRequestError> {
  let body: Partial<ApiError> = {};
  try {
    body = (await response.json()) as Partial<ApiError>;
  } catch {
    // 非 JSON 响应，用默认文案
  }
  return new ApiRequestError(response.status, body.code ?? "REQUEST_FAILED", body.message ?? "请求没有成功，请稍后再试");
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export function hasAdminSession(): boolean {
  return read(TOKEN_KEY).length > 0;
}

export async function adminLogin(email: string, password: string): Promise<void> {
  const response = await fetch("/api/v1/admin/login", {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) throw await toError(response);
  store((await response.json()) as LoginResponse);
}

export async function adminLogout(): Promise<void> {
  const refresh = read(REFRESH_KEY);
  store(null);
  if (!refresh) return;
  try {
    await fetch("/api/v1/auth/logout", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ refresh_token: refresh }) });
  } catch {
    // 本地已经退出；服务端的续期令牌到期会自己失效
  }
}

// 并发 401 只续期一次：续期令牌只能用一次。
let refreshing: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  const token = read(REFRESH_KEY);
  if (!token) return false;
  try {
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: JSON_HEADERS,
      body: JSON.stringify({ refresh_token: token }),
    });
    if (!response.ok) return read(REFRESH_KEY) !== token; // 另一个标签页已经续过了，沿用它的
    store((await response.json()) as LoginResponse);
    return true;
  } catch {
    return false;
  }
}

/** 带后台令牌的请求；令牌过期自动续期一次，续不上或不是管理员就退回登录页。 */
export async function adminRequest<T>(path: string, init?: RequestInit, allowRefresh = true): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: { ...(init?.headers as Record<string, string> | undefined), Authorization: `Bearer ${read(TOKEN_KEY)}` },
  });
  if (response.status === 401 && allowRefresh) {
    refreshing = refreshing ?? refreshAccess();
    const ok = await refreshing;
    refreshing = null;
    if (ok) return adminRequest<T>(path, init, false);
  }
  if (response.status === 401 || response.status === 403) {
    store(null);
    window.dispatchEvent(new Event(ADMIN_SIGNED_OUT));
  }
  if (!response.ok) throw await toError(response);
  return (await response.json()) as T;
}
