// 统一 API 请求封装与类型定义。
// 与后端 app/api/v1/* 的返回结构保持一致（游标分页、通知、房间、留言等）。
import { guestRegion } from "./utils/region";


export type ApiError = {
  code: string;
  message: string;
  request_id?: string;
};

export class ApiRequestError extends Error {
  code: string;
  status: number;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = code;
  }
}

const TOKEN_KEY = "ukcn.token";
const REFRESH_KEY = "ukcn.refresh";

// token 被清除（refresh 401 / 显式登出）时广播，供 auth store 同步登录态，避免 UI 与实际脱节。
const AUTH_CLEARED_EVENT = "ukcn:auth-cleared";

function notifyAuthCleared(): void {
  window.dispatchEvent(new CustomEvent(AUTH_CLEARED_EVENT));
}

/** 订阅「token 被清除」事件（供 auth store 使用）。 */
export function onAuthCleared(handler: () => void): void {
  window.addEventListener(AUTH_CLEARED_EVENT, handler);
}

// 令牌存在 localStorage：关掉标签页或新开标签页后仍保持登录。
// 读取时兼容旧版本存在 sessionStorage 里的令牌，并顺手迁移过来。
function readStored(key: string): string {
  try {
    const value = localStorage.getItem(key);
    if (value) return value;
    const legacy = sessionStorage.getItem(key);
    if (legacy) {
      localStorage.setItem(key, legacy);
      sessionStorage.removeItem(key);
      return legacy;
    }
  } catch {
    // 存储不可用（如隐私模式禁用）时按未登录处理
  }
  return "";
}

function writeStored(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    // 存储不可用时忽略
  }
}

function removeStored(key: string): void {
  try {
    localStorage.removeItem(key);
    sessionStorage.removeItem(key);
  } catch {
    // 忽略
  }
}

/** 其他标签页登录 / 登出时触发（供 auth store 同步登录态）。 */
export function onTokenChangedElsewhere(handler: () => void): void {
  window.addEventListener("storage", (event) => {
    if (event.key === TOKEN_KEY || event.key === null) handler();
  });
}

export function getToken(): string {
  return readStored(TOKEN_KEY);
}

export function setToken(value: string): void {
  writeStored(TOKEN_KEY, value);
}

export function getRefreshToken(): string {
  return readStored(REFRESH_KEY);
}

export function setRefreshToken(value: string): void {
  writeStored(REFRESH_KEY, value);
}

/** 登录 / 注册 / 续期成功后统一写入令牌对。 */
export function setSession(tokens: LoginResponse): void {
  setToken(tokens.access_token);
  if (tokens.refresh_token) setRefreshToken(tokens.refresh_token);
}

export function clearToken(): void {
  removeStored(TOKEN_KEY);
  removeStored(REFRESH_KEY);
  notifyAuthCleared();
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  const headers: Record<string, string> = { ...(extra ?? {}) };
  if (token) headers.Authorization = `Bearer ${token}`;
  // 浏览器这边的国家（选过的或自动判断的）：游客、以及还没在账号里存过国家的新用户，后端按它给内容；
  // 账号里存了国家的，后端以账号为准，不看这个头
  const region = guestRegion();
  if (region) headers["X-Region"] = region;
  return headers;
}

async function parseError(response: Response): Promise<ApiRequestError> {
  let code = "REQUEST_FAILED";
  let message = "请求没有成功，请稍后再试";
  try {
    const body = (await response.json()) as Partial<ApiError>;
    code = body.code ?? code;
    message = body.message ?? message;
  } catch {
    // 非 JSON 响应，保留默认文案
  }
  return new ApiRequestError(response.status, code, message);
}

// 并发 401 只发起一次 refresh，避免多请求同时刷新导致 refresh token 轮换失效。
let refreshing: Promise<boolean> | null = null;

async function refreshAccess(): Promise<boolean> {
  const token = getRefreshToken();
  if (!token) return false;
  try {
    const response = await fetch("/api/v1/auth/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: token }),
    });
    if (!response.ok) {
      // refresh token 只能用一次。两个标签页同时续期时，慢的那个会被拒绝，
      // 但另一个标签页已经把新令牌写进了共享存储：沿用它，不要清掉登录态。
      const current = getRefreshToken();
      if (current && current !== token) return true;
      clearToken();
      return false;
    }
    const body = (await response.json()) as LoginResponse;
    setSession(body);
    return true;
  } catch {
    return false;
  }
}

/**
 * 统一请求：自动带鉴权头、解析后端 {code,message} 错误；
 * access token 过期（401）时自动用 refresh token 续期并重放一次请求。
 */
export async function request<T>(path: string, init?: RequestInit, allowRefresh = true): Promise<T> {
  const config: RequestInit = {
    ...init,
    headers: authHeaders(init?.headers as Record<string, string> | undefined),
  };
  const response = await fetch(path, config);
  const canRefresh =
    allowRefresh &&
    response.status === 401 &&
    getRefreshToken().length > 0 &&
    !path.startsWith("/api/v1/auth/login") &&
    !path.startsWith("/api/v1/auth/refresh");
  if (canRefresh) {
    refreshing = refreshing ?? refreshAccess();
    const ok = await refreshing;
    refreshing = null;
    if (ok) return request<T>(path, init, false);
  }
  if (!response.ok) {
    throw await parseError(response);
  }
  return (await response.json()) as T;
}

/** 统一把未知异常转成可展示文案（ApiRequestError 优先用后端 message）。 */
export function toMessage(err: unknown): string {
  if (err instanceof ApiRequestError) return err.message;
  return err instanceof Error ? err.message : "请求没有成功，请稍后再试";
}

export function jsonBody(value: unknown): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(value),
  };
}

/** 上传链路：POST /uploads/sign 申请名额 → PUT 原文件 → 返回 object_key。 */
export async function uploadFile(file: File, contentType?: string): Promise<string> {
  const type = contentType ?? file.type;
  const signed = await request<UploadSignResponse>("/api/v1/uploads/sign", jsonBody({ content_type: type }));
  const put = await fetch(signed.upload_url, {
    method: "PUT",
    headers: { "Content-Type": signed.content_type, ...authHeaders() },
    body: file,
  });
  if (!put.ok) throw await parseError(put);
  return signed.object_key;
}

// ---- 类型定义 -----------------------------------------------------------

export type Channel = {
  id: string;
  code: string;
  name_hans: string;
  name_hant: string;
  kind: string;
  room_type: string;
  region_code: string;
  parent_channel_id: string | null;
  subscriber_count: number;
  certified: boolean;
  /** 频道分类（房产/市场/招聘），由 /channels 下发，供分类信息发布精确过滤 */
  category: string | null;
};

export type FeedSource = {
  canonical_url: string;
  title: string;
  source_name: string | null;
};

export type FeedItem = {
  content_id: string;
  title: string;
  summary: string | null;
  channels: string[];
  channel_id: string;
  channel_name?: string;
  /** 频道是否官方认证（对应后端的 channel_certified） */
  channel_certified?: boolean;
  source_name: string | null;
  licence_ref: string | null;
  canonical_url: string | null;
  source_count: number;
  sources: FeedSource[];
  pinned: boolean;
  liked: boolean;
  favorited: boolean;
  reposted: boolean;
  repost_of: { content_id: string; title: string } | null;
  is_unread: boolean;
  added_at: string;
  author_id?: string | null;
  author_name: string;
  author_avatar?: string;
  author_handle: string;
  keywords: string[];
  type: string;
  /** 多图 key（最多 4 张），首图与 image_key 一致 */
  image_keys?: string[];
  /** 视频 key（post_type=video 时存在） */
  video_key?: string | null;
  /** 外链视频（YouTube / 哔哩哔哩）；不是外链帖为 null */
  embed?: EmbedCard | null;
};

export type EmbedCard = { status: string; provider: string | null };

export type FeedResponse = {
  items: FeedItem[];
  joined_count: number;
  paused_count: number;
  new_count: number;
  fresh_count: number;
  seen_at: string | null;
  next_cursor?: string;
};

export type Subscription = {
  channel_id: string;
  code: string;
  name_hans: string;
  is_muted: boolean;
  unread_count: number;
};

export type SubscriptionsResponse = {
  items: Subscription[];
  paused_count: number;
};

export type OwnRoom = {
  channel_id: string;
  name_hans: string;
  room_type: string;
  room_type_label: string;
  is_private: boolean;
  is_active: boolean;
  review_status: string;
  parent_channel_id: string | null;
  parent_name_hans: string;
  entry_count: number;
  role: "owner" | "member";
};

export type MyRoomsResponse = {
  items: OwnRoom[];
  paused_count: number;
  owned_count: number;
  room_limit: number;
  quota_used: number;
  next_cursor?: string;
};

export type NotificationItem = {
  id: string;
  kind: string;
  body: string;
  content_id: string | null;
  unread: boolean;
  created_at: string;
};

export type NotificationsResponse = {
  items: NotificationItem[];
  unread_count: number;
  next_cursor?: string;
};

export type RoomComment = {
  id: string;
  author_id: string;
  author_name: string;
  author_avatar?: string;
  author_handle: string;
  body: string;
  image_key: string | null;
  content_id: string | null;
  parent_id: string | null;
  mention_count: number;
  mentions: string[];
  keyword_count: number;
  like_count: number;
  liked: boolean;
  status: string;
  created_at: string;
};

export type CommentsResponse = {
  items: RoomComment[];
  next_cursor?: string;
  /** 帖子回复总数（帖子详情的回复按页取，标题上显示总数） */
  total?: number;
};

export type RoomDetail = {
  id: string;
  code: string;
  name_hans: string;
  name_hant: string;
  kind: string;
  room_type: string;
  /** 房间类型的中文名（综合讨论 / 剧集系列 / 电影 / 视频），由后端下发 */
  room_type_label?: string;
  /** 房间封面图的上传 key（剧集房间页顶部） */
  cover_key?: string | null;
  review_status?: string;
  is_private?: boolean;
  join_request_pending?: boolean;
  is_owner?: boolean;
  sort_basis?: string;
  certified?: boolean;
  region_code?: string;
  category?: string | null;
  parent_channel_id: string | null;
  parent_name_hans?: string;
  subscriber_count?: number;
  is_joined: boolean;
  region_blocked?: boolean;
  pinned_announcement_count?: number;
  seasons?: number[];
  owner?: { user_id: string; display_name: string; handle: string } | null;
  collaborators?: { user_id: string; display_name: string; handle: string }[];
  rooms?: { id: string; name_hans: string; room_type: string; room_type_label: string; is_private: boolean; is_active: boolean; has_published: boolean }[];
};

// 房间条目（series/film/video/general 共用的 item 结构）
export type RoomItem = {
  content_id: string;
  title: string;
  title_hant: string;
  summary: string | null;
  source_name: string;
  licence_ref: string;
  canonical_url: string | null;
  embed_status: string;
  embed_provider_code: string | null;
  /** 帖子卡用：外链视频帖才有 */
  embed?: EmbedCard | null;
  type: string;
  keywords: string[];
  image_key: string | null;
  image_keys?: string[];
  origin_room_id?: string | null;
  origin_room_name?: string | null;
  video_key: string | null;
  rights_confirmed: boolean;
  author_id: string | null;
  author_name: string;
  author_avatar?: string;
  author_handle: string;
  city_topic: string;
  liked: boolean;
  favorited: boolean;
  reposted: boolean;
  repost_of: { content_id: string; title: string } | null;
  status: string;
  comment_count: number;
  pinned: boolean;
  season: number | null;
  episode: number | null;
  year: number | null;
  sort_key: string;
  progress: number | null;
  watch_mark: string | null;
  added_at: string;
  listing?: {
    category: string;
    kind: string;
    area: string;
    price_amount: string;
    price_unit: string;
    currency: string;
    closed_reason: string | null;
    certified: boolean;
    expires_at: string | null;
    expired: boolean;
  } | null;
};

export type RoomItemsResponse = {
  items: RoomItem[];
  progress_scope: string;
  sort_basis: string;
  next_cursor?: string;
};

export type DiscoverItem = {
  content_id: string;
  title: string;
  summary: string | null;
  source_name: string;
  licence_ref: string;
  canonical_url: string | null;
  channel_id: string;
  channel_name: string;
  channel_certified?: boolean;
  is_joined: boolean;
  category: string | null;
  added_at: string;
  author_id?: string | null;
  author_name: string;
  author_avatar?: string;
  author_handle: string;
  keywords: string[];
  image_keys?: string[];
  video_key?: string | null;
  embed?: EmbedCard | null;
  /** 当前用户的互动状态（游客恒为 false） */
  liked?: boolean;
  favorited?: boolean;
  reposted?: boolean;
};

export type DiscoverResponse = {
  items: DiscoverItem[];
  updated_count: number;
  categories: string[];
  /** 当前浏览国家（游客按 X-Region 头里选的国家，没选是 GLOBAL），用于渲染地区筛选 chip */
  region?: { code: string; name: string };
  /** 下一页游标；没有更多时为空 */
  next_cursor?: string | null;
};

export type LoginResponse = {
  access_token: string;
  refresh_token: string;
  token_type: string;
  joined_channels?: number;
};

export type ContentDetail = {
  content_id: string;
  title: string;
  title_hant: string;
  summary: string | null;
  body: string;
  keywords: string[];
  city_topic: string;
  source_name: string;
  licence_ref: string;
  canonical_url: string | null;
  image_key: string | null;
  image_keys: string[];
  video_key: string | null;
  published_at: string | null;
  type: string;
  embed_status?: string;
  embed_provider_code?: string | null;
  author_id: string | null;
  author_name: string | null;
  author_avatar?: string;
  author_handle: string;
  channel_id: string | null;
  channel_name: string;
  category: string | null;
  is_joined: boolean;
  repost_of: { content_id: string; title: string } | null;
  status: string;
  liked: boolean;
  favorited: boolean;
};

// ---- Phase 4：发布 / 分类信息 / 外链同意 -------------------------------

// POST /contents 与 /listings 通用响应
export type PublishResponse = {
  content_id: string;
  status: string;
  type: string;
  keywords?: string[];
  keyword_source?: string;
  city_topic?: string;
};

// GET /embed/{content_id}/consent 响应
export type EmbedConsent = {
  provider_code: string | null;
  display_name: string;
  notice: string;
  policy_version: string;
  scope: "once" | "always" | "withdrawn" | null;
  embed_status: string;
  source_url: string | null;
  may_load: boolean;
  embed_url?: string | null;
};

// POST /embed/{content_id}/consent 响应
export type EmbedConsentResult = {
  scope: "once" | "always" | "withdrawn";
  may_load: boolean;
  embed_url?: string | null;
};

// GET /discover/listings 单条（对齐 _public_listing）
export type ListingCardItem = {
  content_id: string;
  title: string;
  summary: string | null;
  category: string;
  kind: string;
  area: string;
  price_amount: string;
  price_unit: string;
  currency: string;
  attrs: Record<string, string>;
  closed_reason: string | null;
  expires_at: string | null;
  expired: boolean;
  channel_id: string;
  channel_name: string;
  certified: boolean;
  source_name: string;
  licence_ref: string;
  region_code: string;
  placeholder: boolean;
  author_id?: string;
  author_name?: string;
  author_handle?: string;
  /** 详情图片（后端 image_keys_json，最多 4 张；横滑容器按数组渲染） */
  image_keys?: string[];
};

// 频道（发布目标下拉用），后端 /channels 返回 items
export type ChannelsResponse = {
  items: Channel[];
};

// ---- Phase 5：私信 / 我的 / 合规 / 上传 -------------------------------

export type UploadSignResponse = {
  object_key: string;
  upload_url: string;
  content_type: string;
};

export type ListingRef = {
  id: string;
  title: string;
  price: string;
  unit: string;
  currency: string;
  area: string;
  image_key: string;
};

export type DmThreadItem = {
  thread_id: string;
  peer_id: string;
  peer_name: string;
  peer_handle: string;
  peer_tone: string;
  peer_avatar: string;
  status: "request" | "active";
  listing_inquiry: boolean;
  listing_ref: ListingRef | null;
  preview: string;
  updated_at: string;
  unread: number;
};

export type DmThreadsResponse = {
  items: DmThreadItem[];
  request_count: number;
};

export type DmMessageItem = {
  id: string;
  sender_id: string;
  kind: "text" | "image";
  body: string;
  image_key: string | null;
  created_at: string;
};

export type DmThreadResponse = {
  thread_id: string;
  status: "request" | "active";
  items: DmMessageItem[];
};

export type DmOpenResponse = {
  thread_id: string;
  status: "request" | "active";
  listing_ref?: ListingRef;
  suggested_text?: string;
};

export type PrefsResponse = { dm_allow_strangers: boolean };
export type BlockedUser = { user_id: string; display_name: string };
export type BlocksResponse = { items: BlockedUser[] };
export type BadgesResponse = { notifications: number; messages: number; total: number };

export type SavedItem = {
  content_id: string;
  title: string;
  type: string;
  summary: string | null;
};

export type FavoritesResponse = {
  saved_count: number;
  followed_count: number;
  paused_count: number;
  items: SavedItem[];
};

export type MyPost = {
  content_id: string;
  title: string;
  status: string;
  summary: string | null;
};

export type MyPostsResponse = { items: MyPost[] };

export type ReportReason = "scam" | "harass" | "sexual" | "ip" | "privacy" | "other";

export type ReportReceipt = {
  case_id: string;
  status: string;
  reason: string;
  reason_text: string;
  sla: string;
};

// ---- 全站搜索 / 区域 / 推荐（对齐原型首页顶部搜索、当前国家区域栏、右栏）----

export type SearchChannel = {
  id: string;
  code: string;
  name_hans: string;
  kind: string;
  room_type: string;
};

export type SearchContent = {
  content_id: string;
  title: string;
  summary: string | null;
  type: string;
  source_name: string;
  licence_ref: string;
  canonical_url: string | null;
  author_id?: string | null;
  author_name: string;
  author_avatar?: string;
  author_handle: string;
  channel_id: string | null;
  channel_name: string;
  keywords: string[];
  image_keys: string[];
  video_key: string | null;
  embed?: EmbedCard | null;
  published_at: string | null;
  liked: boolean;
  favorited: boolean;
  reposted?: boolean;
};

export type SearchUser = {
  user_id: string;
  display_name: string;
  handle: string;
  avatar_tone: string;
  avatar_key: string;
  city_label: string;
};

export type SearchResponse = {
  users: SearchUser[];
  channels: SearchChannel[];
  contents: SearchContent[];
};

export type OpenRegion = {
  code: string;
  name: string;
  city: string;
};

export type RegionPref = {
  region_code: string;
  source: string;
  locked: boolean;
  consent_id?: string | null;
  browse_region_code?: string | null;
  roaming: boolean;
  station_name?: string;
  station_city?: string;
  updated_at?: string;
  open_regions?: OpenRegion[];
};

export type RecommendedChannel = {
  id: string;
  code: string;
  name_hans: string;
  region_code: string;
};

export type RecommendedResponse = { items: RecommendedChannel[] };

export type TrendingKeyword = { keyword: string; count: number };

export type TrendingKeywordsResponse = {
  keywords: TrendingKeyword[];
  window_days: number;
  generated: string;
};

// ---- 首页右栏：最新新闻 / 今日最关注 / 本周点击最多 ------------------

export type RailItem = {
  content_id: string;
  title: string;
  summary: string | null;
  source_name: string;
  canonical_url: string | null;
  channel_id: string | null;
  channel_name: string;
  type: string;
  published_at: string | null;
  view_count: number;
  author_name: string;
};

export type HomeRailResponse = {
  news: RailItem[];
  today: RailItem[];
  week: RailItem[];
};

// ---- 用户主页 / 关注 --------------------------------------------------

export type UserProfile = {
  user_id: string;
  display_name: string;
  handle: string;
  avatar_tone: string;
  avatar_key: string;
  city_label: string;
  joined_at: string;
  post_count: number;
  follower_count: number;
  following_count: number;
  following: boolean;
  blocked: boolean;
  /** 这个人建的房间；本人看自己时含私密和审核中的 */
  rooms: {
    id: string;
    name_hans: string;
    room_type: string;
    room_type_label: string;
    is_private: boolean;
    pending: boolean;
    subscriber_count: number;
  }[];
};

export type UserPost = {
  content_id: string;
  title: string;
  summary: string | null;
  type: string;
  created_at: string;
  source_name: string;
  licence_ref: string;
  canonical_url: string | null;
  channel_id: string | null;
  channel_name: string;
  keywords: string[];
  image_keys: string[];
  video_key: string | null;
  embed?: EmbedCard | null;
  liked: boolean;
  favorited: boolean;
  reposted?: boolean;
};

export type UserPostsResponse = { items: UserPost[] };

export type MeProfile = {
  user_id: string;
  display_name: string;
  handle: string;
  avatar_tone: string;
  avatar_key: string;
  city_label: string;
  script_pref: string;
  phone: string;
  email: string;
  /** 最近一次同意的条款版本 */
  consent_version: string | null;
  is_admin?: boolean;
};

// ---- 房间投稿 / 审核 --------------------------------------------------

export type Submission = {
  content_id: string;
  title: string;
  summary: string | null;
  author_id: string;
  author_name: string;
  author_handle: string;
  created_at: string;
};

export type SubmissionsResponse = { items: Submission[]; pending_count: number };
