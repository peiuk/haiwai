<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ApiRequestError, request, toMessage, type RoomDetail, type RoomItem, type RoomItemsResponse } from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import { usePostReactions } from "../composables/usePostReactions";
import { setDocumentTitle } from "../i18n/uiLang";
import Avatar from "../components/base/Avatar.vue";
import BaseButton from "../components/base/BaseButton.vue";
import BaseTag from "../components/base/BaseTag.vue";
import ErrorState from "../components/base/ErrorState.vue";
import PostCard from "../components/common/PostCard.vue";
import ContentDetail from "../components/ContentDetail.vue";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();
const toast = useToastStore();
const channelId = computed(() => String(route.params.id ?? ""));
const detail = ref<RoomDetail | null>(null);
// 网页标题带上频道名，多开标签页时分得清
watch(
  () => detail.value?.name_hans,
  (name) => {
    if (name) setDocumentTitle(`${name} · 海外圈`);
  },
);
const items = ref<RoomItem[]>([]);
const cursor = ref<string | null>(null);
const roomCount = ref(6);
const loading = ref(true);
const loadingMore = ref(false);
const joining = ref(false);
const error = ref("");
const notFound = ref(false); // 404 时不给「重试」：内容不在了，重试也没用
const itemsError = ref("");
const activeContentId = ref<string | null>(null);

const visibleRooms = computed(() => (detail.value?.rooms ?? []).slice(0, roomCount.value));

const REGION_NAMES: Record<string, string> = { UK: "英国", GLOBAL: "国际" };
// §26.9 ScopeTag：国际频道「国际 · 各国共享」，其他国家频道「{国家}频道 · 仅{国家}」。
const scopeTag = computed(() => {
  const code = detail.value?.region_code ?? "";
  if (code === "GLOBAL") return "国际 · 各国共享";
  const name = REGION_NAMES[code] ?? code;
  return name ? `${name}频道 · 仅${name}` : "";
});

// §26.9 CountryGuard：其他国家频道不可用时的占位文案。
const guardText = computed(() => {
  const code = detail.value?.region_code ?? "";
  const name = REGION_NAMES[code] ?? code;
  return name ? `这个频道属于${name}，切回${name}后恢复` : "这个频道在其他国家暂不可用";
});

async function load(): Promise<void> {
  if (!channelId.value) return;
  loading.value = true;
  error.value = "";
  itemsError.value = "";
  roomCount.value = 6;
  try {
    const channel = await request<RoomDetail>(`/api/v1/channels/${channelId.value}`);
    if (channel.kind === "room") {
      void router.replace({ name: "room", params: { id: channelId.value } });
      return;
    }
    detail.value = channel;
    if (channel.region_blocked) {
      items.value = [];
      cursor.value = null;
      return;
    }
    await loadItems(true);
  } catch (err) {
    detail.value = null;
    notFound.value = err instanceof ApiRequestError && err.status === 404;
    error.value = toMessage(err);
  } finally {
    loading.value = false;
  }
}

async function loadItems(reset: boolean): Promise<void> {
  if (!reset && (!cursor.value || loadingMore.value)) return;
  if (!reset) loadingMore.value = true;
  itemsError.value = "";
  try {
    const query = !reset && cursor.value ? `?cursor=${encodeURIComponent(cursor.value)}` : "";
    const result = await request<RoomItemsResponse>(`/api/v1/channels/${channelId.value}/items${query}`);
    items.value = reset ? result.items : [...items.value, ...result.items];
    cursor.value = result.next_cursor ?? null;
  } catch (err) {
    itemsError.value = toMessage(err);
    if (reset) items.value = [];
  } finally {
    loadingMore.value = false;
  }
}

async function toggleJoin(): Promise<void> {
  if (!detail.value || joining.value) return;
  if (!auth.isLoggedIn) {
    toast.show("先登录，再加入频道");
    void router.push({ name: "profile" });
    return;
  }
  joining.value = true;
  try {
    await request(`/api/v1/me/subscriptions/${channelId.value}`, { method: detail.value.is_joined ? "DELETE" : "PUT" });
    detail.value.is_joined = !detail.value.is_joined;
    toast.show(detail.value.is_joined ? "已加入频道" : "已退出频道");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    joining.value = false;
  }
}

const reactions = usePostReactions();

function toggleReaction(item: RoomItem, kind: "like" | "favorite"): Promise<void> {
  return kind === "like" ? reactions.toggleLike(item) : reactions.toggleFavorite(item);
}

function repost(item: RoomItem): Promise<void> {
  return reactions.repost(item, channelId.value, "已转发");
}

function price(item: RoomItem): string {
  const listing = item.listing;
  if (!listing) return "";
  const amount = Number(listing.price_amount);
  const value = Number.isFinite(amount) && listing.price_amount.trim()
    ? new Intl.NumberFormat("zh-CN", { style: "currency", currency: listing.currency || "GBP", maximumFractionDigits: 0 }).format(amount)
    : listing.price_amount;
  return [listing.area, value, listing.price_unit].filter(Boolean).join(" · ");
}

function listingLabel(item: RoomItem): string {
  const listing = item.listing;
  if (!listing) return "";
  const kind = ({ rent: "出租", sale: "买卖", commercial: "商业", secondhand: "二手", job: "职位" } as Record<string, string>)[listing.kind] ?? "信息";
  return `${listing.category} · ${kind}`;
}

watch(channelId, () => void load(), { immediate: true });
</script>

<template>
  <section class="channel-view">
    <RouterLink :to="{ name: 'home', query: { tab: 'channels' } }" class="back-link">← 全部频道</RouterLink>
    <p v-if="loading" class="channel-note">正在加载频道…</p>
    <ErrorState v-else-if="error" :message="error" :retry-label="notFound ? '' : '重试'" @retry="load" />
    <template v-else-if="detail">
      <header class="channel-head">
        <Avatar :name="detail.name_hans" :size="44" kind="channel" />
        <div class="channel-head__main">
          <div class="channel-head__title">
            <h1 data-ugc>{{ detail.name_hans }}</h1>
            <BaseTag v-if="detail.certified" variant="link">官方</BaseTag>
            <span v-if="scopeTag" class="scope-tag">{{ scopeTag }}</span>
          </div>
          <p><template v-if="detail.subscriber_count !== undefined">{{ detail.subscriber_count }} 人加入</template></p>
        </div>
        <BaseButton v-if="!detail.region_blocked" :variant="detail.is_joined ? 'outline' : 'primary'" size="sm" :loading="joining" @click="toggleJoin">{{ detail.is_joined ? "已加入" : "加入频道" }}</BaseButton>
      </header>

      <p v-if="detail.region_blocked" class="channel-note" role="note">{{ guardText }}</p>
      <template v-else>
        <section class="channel-section" aria-label="频道房间">
          <div class="channel-section__head"><h2>频道房间</h2><span>{{ detail.rooms?.length ?? 0 }} 个</span></div>
          <p v-if="!detail.rooms?.length" class="channel-note">这个频道还没有公开房间。</p>
          <div v-else class="room-grid">
            <RouterLink v-for="room in visibleRooms" :key="room.id" :to="{ name: 'room', params: { id: room.id } }" class="room-card">
              <strong data-ugc>{{ room.name_hans }}</strong>
              <span>{{ room.slot_label ? `${room.slot_label} · ` : "" }}{{ room.is_private ? "私密" : "公开" }} · {{ room.room_type_label }}</span>
            </RouterLink>
          </div>
          <BaseButton v-if="roomCount < (detail.rooms?.length ?? 0)" variant="ghost" size="sm" @click="roomCount += 6">查看更多房间</BaseButton>
        </section>

        <section class="channel-section" aria-label="频道动态">
          <div class="channel-section__head"><h2>频道动态</h2><RouterLink :to="{ name: 'publish', query: { channel: channelId } }">发布到此频道</RouterLink></div>
          <p v-if="itemsError" class="channel-error" role="alert">{{ itemsError }} <button type="button" @click="loadItems(true)">重试</button></p>
          <p v-else-if="!items.length" class="channel-note">这个频道还没有动态。</p>
          <div v-for="item in items" :key="item.content_id" class="channel-item">
            <p v-if="item.listing || item.status === 'pending'" class="item-context">
              <span v-if="item.listing">{{ listingLabel(item) }} · {{ price(item) }}</span>
              <span v-if="item.status === 'pending'">审核中，仅自己可见</span>
            </p>
            <div v-if="item.status === 'pending'" class="pending-card">
              <strong data-ugc>{{ item.title }}</strong>
              <p v-if="item.summary" data-ugc>{{ item.summary }}</p>
            </div>
            <PostCard
              v-else
              :content-id="item.content_id" :title="item.title" :summary="item.summary"
              :channel-name="detail.name_hans" :channel-id="detail.id" hide-channel
              :author-id="item.author_id" :author-name="item.author_name" :author-handle="item.author_handle" :author-avatar="item.author_avatar"
              :certified="Boolean(detail.certified)" :pinned="item.pinned" :time="item.added_at"
              :source-name="item.source_name" :licence-ref="item.licence_ref" :canonical-url="item.canonical_url"
              :keywords="item.keywords" :image-keys="item.image_keys ?? (item.image_key ? [item.image_key] : [])"
              :video-key="item.video_key"
              :bg-style="item.bg_style"
              :embed="item.embed"
              :liked="item.liked" :favorited="item.favorited" :reposted="item.reposted"
              @open="activeContentId = item.content_id"
              @like="toggleReaction(item, 'like')" @favorite="toggleReaction(item, 'favorite')" @repost="repost(item)"
            >
              <!-- 房主从房间推来的帖子：右上角、更多菜单左边标出来源房间 -->
              <template v-if="item.origin_room_name" #head-extra>
                <RouterLink
                  v-if="item.origin_room_id"
                  class="room-origin"
                  :to="{ name: 'room', params: { id: item.origin_room_id } }"
                  :title="`房主从「${item.origin_room_name}」推到频道`"
                >来自房间 · <span data-ugc>{{ item.origin_room_name }}</span></RouterLink>
                <span class="room-push-note">房主推到频道</span>
              </template>
            </PostCard>
          </div>
          <BaseButton v-if="cursor" variant="outline" size="sm" :loading="loadingMore" @click="loadItems(false)">加载更多动态</BaseButton>
        </section>
      </template>
    </template>
    <ContentDetail v-if="activeContentId" :content-id="activeContentId" @close="activeContentId = null" />
  </section>
</template>

<style scoped>
.channel-view { display: grid; gap: var(--sp-4); }
.back-link { font-size: var(--fs-13); color: var(--muted); }
.channel-head { display: flex; align-items: center; gap: var(--sp-3); padding: var(--sp-4) 0; border-bottom: 1px solid var(--border); }
.channel-head__main { flex: 1; min-width: 0; }
.channel-head__title { display: flex; align-items: center; gap: var(--sp-2); flex-wrap: wrap; }
.scope-tag {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 var(--sp-2);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  color: var(--muted);
  font-size: var(--fs-12);
  white-space: nowrap;
}
.channel-head h1 { margin: 0; font-size: var(--fs-21); overflow-wrap: anywhere; }
.channel-head p, .channel-note { margin: var(--sp-1) 0 0; color: var(--muted); font-size: var(--fs-13); }
.channel-section { display: grid; gap: var(--sp-3); }
.channel-section__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--sp-2); }
.channel-section__head h2 { margin: 0; font-size: var(--fs-16); }
.channel-section__head span, .channel-section__head a { font-size: var(--fs-13); color: var(--muted); }
.room-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--sp-2); }
.room-card { display: grid; gap: var(--sp-1); min-width: 0; padding: var(--sp-3); border: 1px solid var(--border); border-radius: var(--r-md); background: var(--surface); text-decoration: none; color: var(--text); }
.room-card:hover { border-color: var(--accent); }
.room-card strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: var(--fs-13); }
.room-card span { color: var(--muted); font-size: var(--fs-12); }
.channel-item { border-top: 1px solid var(--border); }
.item-context { display: flex; flex-wrap: wrap; gap: var(--sp-2); margin: var(--sp-2) var(--sp-3) 0; color: var(--muted); font-size: var(--fs-12); }
.room-origin {
  max-width: 10em; /* 窄屏时房间名先截断，更多菜单始终可点 */
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--accent-ink);
  font-size: var(--fs-12);
}
.room-origin:hover {
  text-decoration: underline;
}
.room-push-note {
  margin: 0 var(--sp-1);
  color: var(--muted);
  font-size: var(--fs-12);
  white-space: nowrap;
}
/* 手机上右上角太挤会把发帖人名字挤没：只留「来自房间」链接，「房主推到频道」放进它的提示里 */
@media (max-width: 480px) {
  .room-origin { max-width: 6em; margin-right: var(--sp-1); }
  .room-push-note { display: none; }
}
.pending-card { display: grid; gap: var(--sp-1); padding: var(--sp-3); }
.pending-card p { margin: 0; color: var(--muted); font-size: var(--fs-13); }
.channel-error { margin: 0; color: var(--danger); font-size: var(--fs-13); }
.channel-error button { border: 0; background: none; color: inherit; text-decoration: underline; cursor: pointer; }
@media (max-width: 480px) { .channel-head { flex-wrap: wrap; } .channel-head > :last-child { margin-left: auto; } }
</style>
