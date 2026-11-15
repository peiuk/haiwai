// 后台各页面共用的类型、中文标签和时间显示。
import { fmtRelativeTime } from "../utils/time";

export type AdminStats = {
  new_posts_today: number;
  new_users_today: number;
  pending_contents: number;
  pending_comments: number;
  pending_channels: number;
  open_cases: number;
  total_users: number;
  total_contents: number;
  trend: { date: string; posts: number; users: number }[];
};

export type Paged<T> = { items: T[]; total: number; page_size: number };

export const STATUS_LABELS: Record<string, string> = {
  active: "正常",
  suspended: "已封禁",
  published: "已发布",
  pending: "待审",
  rejected: "已拒绝",
  deleted: "已下架",
  removed: "已删除",
  approved: "已通过",
};

export const TYPE_LABELS: Record<string, string> = {
  post: "帖子",
  listing: "分类信息",
  news: "新闻",
  announcement: "公告",
  topic: "话题",
};

export const KIND_LABELS: Record<string, string> = {
  official_curated: "官方频道",
  official_auto: "官方聚合",
  room: "房间",
};

export const TARGET_LABELS: Record<string, string> = { content: "帖子", comment: "留言", channel: "房间", user: "用户", region: "国家" };

export const ACTION_LABELS: Record<string, string> = {
  "admin.login": "登录后台",
  "admin.user.suspend": "封禁用户",
  "admin.user.activate": "解封用户",
  "admin.content.remove": "下架内容",
  "admin.content.restore": "恢复内容",
  "admin.content.delete": "彻底删除内容",
  "admin.comment.remove": "删除留言",
  "admin.comment.restore": "恢复留言",
  "admin.channel.activate": "上架频道",
  "admin.channel.deactivate": "下架频道",
  "admin.channel.certify": "认证频道",
  "admin.channel.create": "新增频道",
  "admin.channel.update": "编辑频道",
  "admin.channel.delete": "删除频道",
  "admin.region.open": "开通国家",
  "admin.region.close": "关闭国家",
  "admin.region.fill": "补齐默认频道",
  "admin.channel.uncertify": "取消认证",
  "admin.content.feature": "设为精选",
  "admin.content.unfeature": "取消精选",
  "admin.announcement.create": "发布公告",
  "admin.user.grant": "设为管理员",
  "admin.user.revoke": "撤销管理员",
  "admin.news.fetch": "抓取 AI 资讯",
  "announcement.create": "发布公告",
  "channel.report": "举报房间",
  "user.report": "举报用户",
  "comment.report": "举报留言",
  "moderation.approve": "审核通过",
  "moderation.reject": "审核拒绝",
  "moderation.remove": "举报成立并处理",
  "moderation.dismiss": "驳回举报",
  "channel.approve": "房间审核通过",
  "channel.reject": "房间审核拒绝",
  "account.register": "注册账号",
  "content.report": "举报内容",
};

/** 状态对应的标签颜色类（tokens.css 的 .tag--*）。 */
export function statusTone(status: string): string {
  if (status === "published" || status === "active" || status === "approved") return "tag--good";
  if (status === "pending") return "tag--warn";
  return "tag--danger";
}

// 后端时间是 UTC；SQLite 下不带时区后缀，浏览器会当成本地时间，这里统一补上。
function asUtc(iso: string): string {
  return /(Z|[+-]\d\d:?\d\d)$/.test(iso) ? iso : `${iso}Z`;
}

/** 相对时间：刚刚 / 3 小时前。 */
export function when(iso: string | null | undefined): string {
  return iso ? fmtRelativeTime(asUtc(iso)) : "";
}

/** 具体时间（本地时区），放在 title 里，鼠标停上去能看到。 */
export function exact(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(asUtc(iso));
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleString("zh-CN", { hour12: false });
}

export type CaseRow = {
  case_id: string;
  reason: string;
  detail: string;
  status: string;
  decision: string;
  reporter_name: string;
  created_at: string;
};
export type HistoryRow = { action: string; actor_name: string; detail: string; created_at: string };
