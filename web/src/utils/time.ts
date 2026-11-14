// 相对时间：刚刚 / N 分钟前 / N 小时前 / N 天前，超过一周显示日期。
// PostCard 与 ContentDetail 共用；无效或空时间返回空串。
export function fmtRelativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  const minutes = Math.max(0, Math.floor((Date.now() - date.getTime()) / 60000));
  if (minutes < 1) return "刚刚";
  if (minutes < 60) return `${minutes} 分钟前`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)} 小时前`;
  if (minutes < 10080) return `${Math.floor(minutes / 1440)} 天前`;
  return date.toLocaleDateString("zh-CN");
}
