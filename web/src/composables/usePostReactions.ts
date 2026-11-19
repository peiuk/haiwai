// 帖子互动（点赞 / 收藏 / 转发）的统一处理：先在界面上切换，请求失败再恢复原状。
// FeedTab、RecommendTab、ChannelView 共用，避免各写一套。
import { jsonBody, request, toMessage } from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import { useLoginPromptStore } from "../stores/loginPrompt";

export interface ReactableItem {
  content_id: string;
  liked?: boolean;
  like_count?: number;
  favorited?: boolean;
  reposted?: boolean;
}

type ToggleKind = "like" | "favorite";

const TOGGLE = {
  like: { field: "liked", verb: "点赞" },
  favorite: { field: "favorited", verb: "收藏" },
} as const;

export function usePostReactions() {
  const auth = useAuthStore();
  const toast = useToastStore();
  const prompt = useLoginPromptStore();
  // 同一条内容的同一种操作在请求返回前不重复发起，避免连点造成状态错乱。
  const pending = new Set<string>();

  async function toggle(item: ReactableItem, kind: ToggleKind): Promise<void> {
    const { field, verb } = TOGGLE[kind];
    if (!auth.isLoggedIn) {
      // 游客：弹出登录 / 注册，登录成功后自动完成这次操作。
      prompt.require(`登录后就能${verb}，登录成功会自动帮你${verb}。`, () => toggle(item, kind));
      return;
    }
    const lock = `${kind}:${item.content_id}`;
    if (pending.has(lock)) return;
    pending.add(lock);
    const before = Boolean(item[field]);
    const countBefore = item.like_count ?? 0;
    item[field] = !before;
    if (kind === "like") item.like_count = Math.max(0, countBefore + (before ? -1 : 1));
    try {
      const body = await request<{ liked?: boolean; favorited?: boolean; like_count?: number }>(
        `/api/v1/contents/${item.content_id}/${kind}`,
        { method: "POST" },
      );
      // 以服务器结果为准（正常情况下与界面已显示的一致）。
      const confirmed = body[field];
      if (typeof confirmed === "boolean") item[field] = confirmed;
      if (typeof body.like_count === "number") item.like_count = body.like_count;
    } catch (err) {
      item[field] = before;
      if (kind === "like") item.like_count = countBefore;
      toast.show(toMessage(err));
    } finally {
      pending.delete(lock);
    }
  }

  async function repost(
    item: ReactableItem,
    channelId: string | null | undefined,
    doneText = "已转发到关注流",
  ): Promise<void> {
    if (!auth.isLoggedIn) {
      prompt.require("登录后就能转发，登录成功会自动帮你转发。", () => repost(item, channelId, doneText));
      return;
    }
    if (!channelId) {
      toast.show("这条内容没有可转发的频道");
      return;
    }
    const lock = `repost:${item.content_id}`;
    if (pending.has(lock)) return;
    pending.add(lock);
    const before = Boolean(item.reposted);
    item.reposted = true;
    try {
      await request(`/api/v1/contents/${item.content_id}/repost`, jsonBody({ channel_id: channelId, body: "" }));
      toast.show(doneText);
    } catch (err) {
      item.reposted = before;
      toast.show(toMessage(err));
    } finally {
      pending.delete(lock);
    }
  }

  return {
    toggleLike: (item: ReactableItem) => toggle(item, "like"),
    toggleFavorite: (item: ReactableItem) => toggle(item, "favorite"),
    repost,
  };
}
