// 帖子标题 / 摘要的展示判断。
// 没填标题时，发布页会把正文前 40 个字当标题，后端又把正文整段存成摘要；
// 如果两处都显示，短帖子会把同一段话重复一遍。摘要以标题开头就说明标题是自动截的。
export function hasOwnTitle(title: string | null | undefined, summary: string | null | undefined): boolean {
  const t = (title ?? "").trim();
  if (!t) return false;
  const s = (summary ?? "").trim();
  return !s || !s.startsWith(t);
}

// 正文里的 #话题（半角 # 或全角 ＃），和后端 app/keywords.py 的 _HASH 同一规则：1–12 个字、去重、最多 5 个
export function hashTags(text: string): string[] {
  const out: string[] = [];
  for (const m of text.matchAll(/[#＃]([\p{L}\p{N}_]{1,12})/gu)) {
    if (!out.includes(m[1])) out.push(m[1]);
    if (out.length >= 5) break;
  }
  return out;
}
