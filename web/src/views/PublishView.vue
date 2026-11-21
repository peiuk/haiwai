<script setup lang="ts">
// 发布页：对齐原型 publish-content.html 的「纯 X 式极简」单输入框结构。
// 一个输入框就能发；类型（发图文/发视频/发信息）用 type-picker 下拉切换，
// 「发分类信息」为类型下拉中的第 4 类（info）。
// 底部「我的发布」为可折叠 X 式帖子卡流。
// 官方外链登记（EmbedForm）从本页移除，另设入口（不在发布页混排）。
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { hashTags, hasOwnTitle } from "../utils/post";
import { BG_MAX_LEN, bgStyleOf } from "../utils/postBg";
import BgPicker from "../components/common/BgPicker.vue";
import {
  ApiRequestError,
  request,
  jsonBody,
  type Channel,
  type ChannelsResponse,
  type MyPostsResponse,
  type PublishResponse,
  type MyPost,
  type RoomDetail,
} from "../api";
import { useAuthStore } from "../stores/auth";
import { useToastStore } from "../stores/toast";
import { useLoginPromptStore } from "../stores/loginPrompt";
import Avatar from "../components/base/Avatar.vue";
import BaseIcon from "../components/base/BaseIcon.vue";
import BaseButton from "../components/base/BaseButton.vue";
import TextField from "../components/base/TextField.vue";
import NoticeBar from "../components/base/NoticeBar.vue";
import UploadField from "../components/common/UploadField.vue";
import MultiUploadField from "../components/common/MultiUploadField.vue";
import ListingForm from "../components/publish/ListingForm.vue";

const auth = useAuthStore();
const loginPrompt = useLoginPromptStore();
const toast = useToastStore();
const router = useRouter();
const route = useRoute();

// ---- 内容类型（对齐原型 type-picker 4 类）----
type ContentType = "text" | "video" | "info";
const TYPE_OPTIONS: { value: ContentType; label: string; icon: string }[] = [
  { value: "text", label: "发图文", icon: "i-image" },
  { value: "video", label: "发视频", icon: "i-video" },
  { value: "info", label: "发信息", icon: "i-pin" },
];
const currentType = ref<ContentType>("text");
const typePickerOpen = ref(false);
const showImage = ref(false);
const showExtras = ref(false);
const currentTypeMeta = computed(
  () => TYPE_OPTIONS.find((t) => t.value === currentType.value) ?? TYPE_OPTIONS[0],
);

// ---- 频道（「发布到」下拉，仅加载一次）----
const channels = ref<Channel[]>([]);
const loading = ref(true);
const error = ref("");

// ---- 发帖状态 ----
const body = ref("");
const title = ref("");
const channelId = ref("");
// 话题不再单独输入：正文里写 #词 就是话题，后端按同样规则从正文里取
const topics = computed(() => hashTags(body.value));
// 城市话题：默认取注册时填的城市名，作为发帖自动带上的话题之一（可删除）。
const cityTopic = ref("");
const cityInited = ref(false);
const videoKey = ref("");
// 发视频两种方式：上传原创视频文件，或贴 YouTube / 哔哩哔哩外链（站内播放）
const videoSource = ref<"upload" | "link">("upload");
const videoUrl = ref("");
const videoReady = computed(() =>
  videoSource.value === "link" ? Boolean(videoUrl.value.trim()) : Boolean(videoKey.value),
);
const imageKeys = ref<string[]>([]);
const busy = ref(false);
const submitError = ref("");
const success = ref("");
// 切换发布类型后，上一条帖子的「已提交」提示不该还留着
watch(currentType, () => {
  success.value = "";
});

const MAX_LEN = 2000;

// 「发布到」分三组：平台频道、我管的房间、其他公开房间。房间多了靠分组和下拉自身的滚动。
const myRooms = ref<ChannelsResponse["items"]>([]);
const channelGroups = computed(() => {
  const mine = new Set(myRooms.value.map((r) => r.id));
  const opt = (c: ChannelsResponse["items"][number]) => ({ value: c.id, label: c.name_hans });
  return [
    { label: "频道", options: channels.value.filter((c) => c.kind !== "room").map(opt) },
    // 剧集 / 视频房间按集数、视频逐条添加，选了就去房间里加（onDestChange）
    { label: "我的房间", options: myRooms.value.map((c) => ({ value: c.id, label: c.room_type === "general" ? c.name_hans : `${c.name_hans}（去房间里添加）` })) },
    { label: "其他房间", options: channels.value.filter((c) => c.kind === "room" && !mine.has(c.id)).map(opt) },
  ].filter((g) => g.options.length);
});
const allTargets = computed(() => [...channels.value, ...myRooms.value]);
function onDestChange(): void {
  const room = myRooms.value.find((r) => r.id === channelId.value);
  if (!room || room.room_type === "general") return;
  channelId.value = "";
  void router.push({ name: "room", params: { id: room.id } });
}

const count = computed(() => body.value.length);
const countOver = computed(() => count.value > MAX_LEN);

// 彩色背景：只给不带图的短文字帖；字写多了自动退回普通样式（选择保留，删短了又会变回来）
const bg = ref("");
const bgTooLong = computed(() => body.value.trim().length > BG_MAX_LEN);
const bgCss = computed(() =>
  currentType.value === "text" && !imageKeys.value.length && !bgTooLong.value ? bgStyleOf(bg.value) : null,
);

const canPublish = computed(() => {
  if (currentType.value === "info" || busy.value || countOver.value) return false;
  if (!body.value.trim() || body.value.trim().length < 2) return false;
  if (currentType.value === "video" && !videoReady.value) return false;
  return true;
});

// 招聘 / 房产 / 市场频道有固定的填写模块：从这类频道点「发布到此频道」进来，直接打开「发信息」，
// 不用先落在「发图文」再切一次。优先于草稿里记的类型——这次点击的意图更明确。
const LISTING_CATEGORIES = ["招聘", "房产", "市场"];
const presetChannelId = computed(() => (typeof route.query.channel === "string" ? route.query.channel : ""));
function openListingFormFor(id: string): void {
  const target = channels.value.find((item) => item.id === id);
  if (target?.certified && LISTING_CATEGORIES.includes(target.category ?? "")) currentType.value = "info";
}

async function loadChannels(): Promise<void> {
  loading.value = true;
  error.value = "";
  try {
    const [res, mine] = await Promise.all([
      request<ChannelsResponse>("/api/v1/channels"),
      // 游客没有自己的房间，不发这个必然 401 的请求；登录后下面的 watch 会重新加载
      auth.isLoggedIn
        ? request<ChannelsResponse>("/api/v1/channels/mine").catch(() => ({ items: [] }))
        : Promise.resolve({ items: [] } as ChannelsResponse),
    ]);
    channels.value = res.items;
    myRooms.value = mine.items;
    const requestedChannel = typeof route.query.channel === "string" ? route.query.channel : "";
    if (requestedChannel && !allTargets.value.some((item) => item.id === requestedChannel)) {
      // 从房间点「发帖」进来：房间不在公开频道列表里（私密 / 审核中 / 还没内容），单独取来当发布目标
      const room = await request<RoomDetail>(`/api/v1/channels/${requestedChannel}`).catch(() => null);
      if (room?.kind === "room") {
        channels.value.push({
          id: room.id,
          code: room.code,
          name_hans: room.name_hans,
          name_hant: room.name_hant,
          kind: room.kind,
          room_type: room.room_type,
          region_code: room.region_code ?? "",
          parent_channel_id: room.parent_channel_id,
          subscriber_count: room.subscriber_count ?? 0,
          certified: false,
          category: null,
        });
      }
    }
    if (requestedChannel && allTargets.value.some((item) => item.id === requestedChannel)) channelId.value = requestedChannel;
    openListingFormFor(requestedChannel);
  } catch (err) {
    error.value = err instanceof Error ? err.message : "频道列表加载失败";
  } finally {
    loading.value = false;
  }
}

const pickerEl = ref<HTMLElement | null>(null);
const pickerTrigger = ref<HTMLButtonElement | null>(null);
function closePicker(returnFocus = false): void {
  if (!typePickerOpen.value) return;
  typePickerOpen.value = false;
  if (returnFocus) pickerTrigger.value?.focus();
}
function onDocumentPointer(event: PointerEvent): void {
  if (pickerEl.value && !pickerEl.value.contains(event.target as Node)) closePicker();
}
onMounted(() => document.addEventListener("pointerdown", onDocumentPointer));
onBeforeUnmount(() => document.removeEventListener("pointerdown", onDocumentPointer));

function setType(tp: ContentType): void {
  currentType.value = tp;
  typePickerOpen.value = false;
  submitError.value = "";
}

// ---- 图片上传（MultiUploadField，多选最多 6 张，带预览/进度）----

const needPhone = ref(false);

// Ctrl / ⌘ + Enter 直接发布（与 X 一致）；条件不满足时不做任何事，按钮的禁用状态已说明原因
function publishByKeyboard(): void {
  if (canPublish.value) void submit();
}

async function submit(): Promise<void> {
  submitError.value = "";
  needPhone.value = false;
  success.value = "";
  if (!auth.isLoggedIn) {
    // 与全站一致：弹登录 / 注册，登录成功后自动把这条发出去（草稿已在本机保存）
    loginPrompt.require("登录后就能发布，登录成功会自动帮你发出。", () => submit());
    return;
  }
  if (!body.value.trim() || body.value.trim().length < 2) {
    submitError.value = "写点内容再发布";
    return;
  }
  if (currentType.value === "video" && !videoReady.value) {
    submitError.value = videoSource.value === "link" ? "请贴上视频链接" : "发视频需要先上传视频文件";
    return;
  }
  busy.value = true;
  try {
    const payload: Record<string, unknown> = {
      title: title.value.trim() || body.value.trim().slice(0, 40),
      body: body.value.trim(),
      post_type: currentType.value === "video" && videoSource.value === "upload" ? "video" : "text",
    };
    // 城市话题：有则默认随帖（后端也会用 city_label 兜底）；用户删除了则显式传空串。
    if (cityTopic.value) payload.city_topic = cityTopic.value;
    else if (cityInited.value) payload.city_topic = "";
    if (channelId.value) payload.channel_id = channelId.value;
    if (imageKeys.value.length) payload.image_keys = imageKeys.value;
    if (currentType.value === "video" && videoSource.value === "link") {
      payload.video_url = videoUrl.value.trim();
    } else if (currentType.value === "video") {
      payload.video_key = videoKey.value;
    }
    if (bgCss.value) payload.bg_style = bg.value;

    const result = await request<PublishResponse>("/api/v1/contents", jsonBody(payload));
    success.value = result.status === "pending" ? "已提交，审核通过后会公开" : "已发布";
    toast.show(success.value);
    clearDraft();
    const target = allTargets.value.find((item) => item.id === channelId.value);
    // 从房间来的：发完回房间，刚发的这条在房间里就能看到；其他的打开刚发的这条
    if (target?.kind === "room") void router.push({ name: "room", params: { id: target.id } });
    else openPost(result.content_id);
  } catch (err) {
    const msg = err instanceof Error ? err.message : "发布没有成功";
    submitError.value = msg;
    // 手机没验证：给出直达「我的」页的入口，草稿已自动保存
    needPhone.value = err instanceof ApiRequestError && err.code === "PHONE_NOT_VERIFIED";
    toast.show(submitError.value);
  } finally {
    busy.value = false;
  }
}

// 发完离开发布页，打开刚发的这条（审核中的作者自己也看得到）；用 replace，按返回不会回到空白的发布页
function openPost(contentId: string): void {
  void router.replace({ name: "content", params: { id: contentId } });
}

// ---- 我的发布 feed ----
const feedOpen = ref(false);
const feed = ref<MyPost[]>([]);
const feedLoading = ref(false);
async function loadFeed(): Promise<void> {
  if (!auth.isLoggedIn) {
    feed.value = [];
    return;
  }
  feedLoading.value = true;
  try {
    const res = await request<MyPostsResponse>("/api/v1/me/posts");
    feed.value = res.items;
  } catch {
    feed.value = [];
  } finally {
    feedLoading.value = false;
  }
}

function statusLabel(status: string): string {
  return ({ published: "已公开", pending: "审核中", rejected: "未通过", removed: "已下架" } as Record<string, string>)[status] ?? status;
}

// ---- 草稿自动保存（MASTER §22.14 DraftAutosave）：停止输入 0.4s 后存一份，发布成功或手动清空后删除 ----
const DRAFT_KEY = "ukcn.publish-draft";
let draftTimer: ReturnType<typeof setTimeout> | null = null;
const draftSaved = ref(false);
function clearDraft(): void {
  if (draftTimer) clearTimeout(draftTimer); // 还没写进去的那次保存也取消，否则清掉后又被写回
  localStorage.removeItem(DRAFT_KEY);
  draftSaved.value = false;
}
function saveDraft(): void {
  if (draftTimer) clearTimeout(draftTimer);
  draftTimer = setTimeout(() => {
    const draft = {
      body: body.value,
      title: title.value,
      type: currentType.value,
      channelId: channelId.value,
      cityTopic: cityTopic.value,
      imageKeys: imageKeys.value,
      videoKey: videoKey.value,
      videoSource: videoSource.value,
      videoUrl: videoUrl.value,
      bg: bg.value,
    };
    localStorage.setItem(DRAFT_KEY, JSON.stringify(draft));
    draftSaved.value = true;
  }, 400);
}
function restoreDraft(): void {
  try {
    const raw = localStorage.getItem(DRAFT_KEY);
    if (!raw) return;
    const draft = JSON.parse(raw) as {
      body: string; title: string; type: ContentType; channelId: string;
      cityTopic?: string; imageKeys?: string[]; videoKey?: string;
      videoSource?: "upload" | "link"; videoUrl?: string; bg?: string;
    };
    body.value = draft.body ?? "";
    title.value = draft.title ?? "";
    // 旧草稿可能存着已删掉的「发话题」类型
    if (TYPE_OPTIONS.some((t) => t.value === draft.type)) currentType.value = draft.type;
    if (draft.channelId) channelId.value = draft.channelId;
    if (draft.cityTopic) cityTopic.value = draft.cityTopic;
    if (Array.isArray(draft.imageKeys)) imageKeys.value = draft.imageKeys;
    if (draft.videoKey) videoKey.value = draft.videoKey;
    if (draft.videoSource) videoSource.value = draft.videoSource;
    if (draft.videoUrl) videoUrl.value = draft.videoUrl;
    if (draft.bg) bg.value = draft.bg;
    draftSaved.value = true;
  } catch {
    clearDraft();
  }
}

onMounted(() => {
  void loadChannels();
  void loadFeed();
  restoreDraft();
});

// 城市话题初始化：登录用户有 city_label 时默认带上，作为话题之一（可删除）。
watch(
  () => auth.profile?.city_label,
  (city) => {
    if (cityInited.value) return;
    cityInited.value = true;
    if (city) cityTopic.value = city;
  },
  { immediate: true },
);
// 在发布页里登录 / 退出后，「我的房间」要跟着变
watch(() => auth.isLoggedIn, () => void loadChannels());
watch(() => route.query.channel, (value) => {
  if (typeof value === "string" && allTargets.value.some((item) => item.id === value)) channelId.value = value;
  if (typeof value === "string") openListingFormFor(value);
});

// 输入变化 → 防抖保存草稿
watch(
  [body, title, currentType, channelId, cityTopic, imageKeys, videoKey, videoSource, videoUrl, bg],
  () => {
    const hasContent =
      body.value.trim() || title.value.trim() || imageKeys.value.length || videoKey.value || videoUrl.value;
    // 内容全删掉时连草稿一起删：否则下次进来会恢复出已经删掉的文字
    if (hasContent) saveDraft();
    else clearDraft();
  },
);
</script>

<template>
  <section class="publish">
    <!-- 顶栏：返回、标题和唯一主操作 -->
    <header class="topbar">
      <button class="back" type="button" aria-label="返回" @click="router.back()">
        <BaseIcon name="i-back" :size="20" />
      </button>
      <span class="title">{{ currentType === 'info' ? '发布分类信息' : '发布帖子' }}</span>
      <div v-if="currentType !== 'info'" class="dest-control">
        <label class="sr-only" for="dest-select">发布到</label>
        <span class="dest-control-label" aria-hidden="true">发布到</span>
        <select id="dest-select" v-model="channelId" class="dest-select" aria-describedby="dest-hint" @change="onDestChange">
          <option value="">我的动态</option>
          <optgroup v-for="group in channelGroups" :key="group.label" :label="group.label">
            <option v-for="opt in group.options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
          </optgroup>
        </select>
      </div>
      <BaseButton v-if="currentType !== 'info'" type="button" variant="primary" :disabled="!canPublish" :loading="busy" title="Ctrl / ⌘ + Enter 发布" aria-keyshortcuts="Control+Enter Meta+Enter" @click="submit">发布</BaseButton>
    </header>

    <!-- 草稿提示 -->
    <p v-if="draftSaved" class="draft-note" role="status">
      草稿已自动保存
      <button type="button" class="draft-clear" @click="clearDraft">清空草稿</button>
    </p>

    <!-- 编辑区：以正文为中心，其他设置按需展开 -->
    <section class="compose" aria-label="发布内容">
      <Avatar v-if="currentType !== 'info'" :name="auth.displayName || '我'" :size="44" class="compose-avatar" :image="auth.profile?.avatar_key" />
      <div class="compose-body">
        <div class="compose-switch">
          <!-- 展开面板（不是 ARIA menu：menu 要求方向键导航，这里用普通按钮 + Tab 更可靠）；Esc / 点外面关闭 -->
          <div ref="pickerEl" class="type-picker" :class="{ open: typePickerOpen }" @keydown.esc="closePicker(true)">
            <button ref="pickerTrigger" class="type-trigger" type="button" :aria-expanded="typePickerOpen" aria-controls="publish-type-options" @click="typePickerOpen = !typePickerOpen">
              <BaseIcon :name="currentTypeMeta.icon" :size="16" />
              <span>{{ currentTypeMeta.label }}</span>
              <BaseIcon name="i-chev" :size="14" :rotate="typePickerOpen ? 180 : 0" />
            </button>
            <div v-if="typePickerOpen" id="publish-type-options" class="type-tabs">
              <button v-for="opt in TYPE_OPTIONS" :key="opt.value" type="button" class="type-tab" :class="{ active: currentType === opt.value }" :aria-pressed="currentType === opt.value" @click="setType(opt.value)">
                <BaseIcon :name="opt.icon" :size="18" /><span>{{ opt.label }}</span>
              </button>
            </div>
          </div>
          <span v-if="currentType === 'info'" class="compose-switch-hint">按分类填写信息</span>
          <span v-if="currentType !== 'info'" id="dest-hint" class="dest-hint">审核通过后公开</span>
        </div>

        <div v-if="currentType === 'info'" class="listing-wrap">
          <ListingForm :channels="channels" :preset-channel-id="presetChannelId" @submitted="openPost" />
        </div>

        <template v-else>
        <p v-if="error" class="type-error" role="alert">{{ error }}</p>
        <textarea
          v-model="body"
          class="body-input"
          :class="{ 'is-bg': bgCss }"
          :style="bgCss ?? undefined"
          rows="6"
          maxlength="2000"
          placeholder="有什么新鲜事想分享？写 #关键词 加话题"
          aria-label="正文"
          @keydown.ctrl.enter.exact.prevent="publishByKeyboard"
          @keydown.meta.enter.exact.prevent="publishByKeyboard"
        ></textarea>

        <BgPicker v-if="currentType === 'text' && !imageKeys.length" v-model="bg" class="bg-row" :disabled="bgTooLong" />

        <!-- 视频提示 -->
        <NoticeBar v-if="currentType === 'video' && videoSource === 'upload'" variant="warn">
          只能上传本人原创视频，不要带未授权的音乐或影视片段。
        </NoticeBar>

        <div v-if="topics.length || cityTopic" class="topics" aria-label="这条帖子会带上的话题">
          <span v-if="cityTopic" class="tag city-tag" title="城市话题">
            <BaseIcon name="i-pin" :size="12" />{{ cityTopic }}
            <button type="button" :aria-label="`移除城市话题 ${cityTopic}`" @click="cityTopic = ''">
              <BaseIcon name="i-close" :size="13" />
            </button>
          </span>
          <span v-for="t in topics" :key="t" class="tag">#{{ t }}</span>
        </div>

        <!-- 原创视频字段 -->
        <div v-if="currentType === 'video'" class="extra-fields">
          <div class="video-source" role="group" aria-label="视频来源">
            <button type="button" class="video-source-btn" :class="{ active: videoSource === 'upload' }" :aria-pressed="videoSource === 'upload'" @click="videoSource = 'upload'">上传视频</button>
            <button type="button" class="video-source-btn" :class="{ active: videoSource === 'link' }" :aria-pressed="videoSource === 'link'" @click="videoSource = 'link'">视频外链</button>
          </div>
          <TextField
            v-if="videoSource === 'link'"
            id="publish-video-url"
            v-model="videoUrl"
            label="视频链接"
            type="url"
            placeholder="https://www.youtube.com/watch?v=… 或 https://www.bilibili.com/video/BV…"
            hint="支持 YouTube、哔哩哔哩；YouTube 分享链接（youtu.be）可以直接贴，哔哩哔哩请贴完整地址。大家点开后在站内播放"
          />
          <template v-else>
          <UploadField
            id="publish-video"
            v-model="videoKey"
            label="原创视频文件"
            accept="video/mp4,video/webm,video/quicktime"
            :max-mb="200"
            hint="mp4 / webm / mov，最大 200MB、3 分钟；上传后才会随帖子提交"
          />
          </template>
        </div>

        <!-- 图片（发图文时，多选最多 6 张）-->
        <div v-if="currentType === 'text' && (showImage || imageKeys.length)" class="extra-fields">
          <MultiUploadField
            id="publish-image"
            v-model="imageKeys"
            label="图片（可选，最多 6 张）"
            accept="image/jpeg,image/png,image/webp"
            :max-mb="5"
            :max="6"
            hint="jpeg / png / webp，单张最大 5MB；第一张为封面"
          />
        </div>

        <div v-if="showExtras" class="extra-fields publish-more">
          <TextField id="publish-title" v-model="title" label="标题（可选）" hint="不填则取正文前 40 字" />
        </div>

        <!-- 工具栏：按需展开附件、话题和可选设置 -->
        <div class="toolbar">
          <button v-if="currentType !== 'video'" type="button" class="tool-btn" :class="{ active: showImage || imageKeys.length }" aria-label="添加图片" :aria-pressed="showImage" @click="showImage = !showImage"><BaseIcon name="i-image" :size="19" /></button>
          <button type="button" class="tool-btn" :class="{ active: showExtras }" aria-label="更多发布设置" :aria-expanded="showExtras" @click="showExtras = !showExtras"><BaseIcon name="i-more" :size="19" /></button>
          <span class="spacer"></span>
          <span class="count" :class="{ over: countOver }">{{ count }} / {{ MAX_LEN }}</span>
        </div>

        <p v-if="submitError" class="type-error" role="alert">
          {{ submitError }}
          <RouterLink v-if="needPhone" class="type-error-link" :to="{ name: 'profile' }">去验证手机</RouterLink>
        </p>
        </template>
      </div>
    </section>

    <div v-if="!auth.isLoggedIn" class="guest-note" role="note">
      <span>登录后才能发布，草稿会先保存在这台设备上。</span>
      <BaseButton type="button" variant="outline" size="sm" @click="loginPrompt.require('登录后发布内容')">登录 / 注册</BaseButton>
    </div>

    <!-- 成功 -->
    <p v-if="success" class="success" role="status">{{ success }}</p>

    <!-- 我的发布（可折叠 feed）-->
    <details v-if="auth.isLoggedIn" class="published-history" :open="feedOpen" @toggle="feedOpen = ($event.target as HTMLDetailsElement).open">
      <summary>我的发布 <BaseIcon name="i-chev" :size="16" class="history-chev" /></summary>
      <section class="feed" aria-label="已发布内容">
        <p v-if="feedLoading" class="feed-note">正在加载…</p>
        <p v-else-if="!feed.length" class="feed-note">还没有发布内容。</p>
        <template v-else>
          <RouterLink v-for="item in feed" :key="item.content_id" :to="{ name: 'content', params: { id: item.content_id } }" class="post">
            <Avatar :name="auth.displayName || '我'" :size="42" :image="auth.profile?.avatar_key" />
            <div class="post-body">
              <div class="post-head">
                <span class="name">我</span>
                <span class="status-pill" :class="item.status">{{ statusLabel(item.status) }}</span>
              </div>
              <strong v-if="hasOwnTitle(item.title, item.summary)" class="post-title">{{ item.title }}</strong>
              <p v-if="item.summary" class="post-copy">{{ item.summary }}</p>
            </div>
          </RouterLink>
        </template>
      </section>
    </details>
  </section>
</template>

<style scoped>
.publish {
  max-width: 680px;
  margin: 0 auto;
  min-height: 100vh;
  padding-bottom: var(--sp-6);
  background: var(--bg);
}

/* 顶栏 */
.topbar {
  display: flex;
  align-items: center;
  gap: var(--sp-3);
  min-height: 60px;
  padding: var(--sp-2) var(--sp-3);
  border-bottom: 1px solid var(--border);
}
.topbar .back {
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  display: grid;
  place-items: center;
  color: var(--text);
  border: 0;
  background: transparent;
  cursor: pointer;
}
.topbar .back:hover { background: var(--hover); }
.topbar .title {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--fs-17);
  font-weight: var(--fw-heavy);
}
.topbar > button:last-child { flex-shrink: 0; }
/* 游客提示 */
.guest-note {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  margin: 0;
  padding: 10px 20px;
  border-bottom: 1px solid var(--border);
  font-size: var(--fs-12);
  color: var(--muted);
}

/* 草稿提示 */
.draft-note {
  margin: var(--sp-3) var(--sp-4) 0;
  padding: 4px 4px 4px 12px;
  border-radius: var(--r-md);
  background: var(--surface2);
  font-size: var(--fs-13);
  color: var(--muted);
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
}
.draft-clear {
  min-height: var(--tap);
  padding: 0 var(--sp-2);
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-12);
  cursor: pointer;
}
.draft-clear:hover { text-decoration: underline; }

/* 编辑区 */
.compose {
  display: flex;
  gap: var(--sp-3);
  padding: 20px 16px 26px;
}
.compose-avatar { flex-shrink: 0; }
.compose-body {
  flex: 1;
  min-width: 0;
}
.compose-switch {
  display: flex;
  align-items: center;
  gap: var(--sp-2);
  margin-bottom: 14px;
}
.compose-switch-hint {
  color: var(--muted);
  font-size: var(--fs-12);
}
.body-input {
  width: 100%;
  border: none;
  outline: none;
  resize: none;
  background: transparent;
  color: var(--text);
  font-size: var(--fs-19);
  line-height: var(--lh-body);
  min-height: 170px;
  padding: 12px 0 20px;
}
.body-input::placeholder { color: var(--muted); }
/* 选了彩色背景：输入框就是发出去的样子（字大、居中、在色块上） */
.body-input.is-bg {
  min-height: 240px;
  padding: 80px 20px;
  border-radius: var(--r-lg);
  font-size: 26px;
  font-weight: var(--fw-bold);
  line-height: 1.4;
  text-align: center;
}
.body-input.is-bg::placeholder { color: inherit; opacity: 0.7; }
.bg-row { margin-bottom: var(--sp-3); }

.type-hint { margin: var(--sp-2) 0 0; font-size: var(--fs-13); color: var(--muted); }

.extra-fields {
  margin: var(--sp-3) 0;
  display: flex;
  flex-direction: column;
  gap: var(--sp-3);
}

/* 话题：正文里 #词 的预览，城市话题可删 */
.topics { display: flex; flex-wrap: wrap; gap: 6px; }
.topics .tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  padding: 0 12px;
  border-radius: var(--r-pill);
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 13px;
  font-weight: 600;
}
.topics .tag button {
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.topics .tag button:hover { background: var(--hover); }
.topics .city-tag {
  background: var(--surface2);
  color: var(--text);
  border: 1px dashed var(--line);
}

/* 工具栏 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--border);
}
.tool-btn {
  display: grid;
  place-items: center;
  width: var(--tap);
  height: var(--tap);
  border-radius: 50%;
  color: var(--accent-ink);
}
.tool-btn:hover, .tool-btn.active { background: var(--accent-soft); }
.spacer { flex: 1; }
.count {
  font-size: var(--fs-13);
  color: var(--muted);
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
.count.over { color: var(--danger); }

/* 类型下拉 */
.type-picker { position: relative; }
.type-trigger {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: var(--tap);
  padding: 0 12px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  color: var(--accent-ink);
  font-size: var(--fs-13);
  font-weight: var(--fw-semibold);
  cursor: pointer;
  background: transparent;
}
.type-picker.open .type-trigger { background: var(--accent-soft); }
.type-tabs {
  position: absolute;
  left: 0;
  top: calc(100% + 8px);
  z-index: var(--z-sticky);
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 168px;
  padding: 6px;
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
  box-shadow: var(--shadow);
}
.type-tab {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 100%;
  min-height: 44px;
  padding: 8px 10px;
  border-radius: var(--r-md);
  color: var(--text);
  font-size: var(--fs-13);
  font-weight: var(--fw-medium);
  text-align: left;
  border: 0;
  background: transparent;
  cursor: pointer;
}
.type-tab:hover { background: var(--hover); }
.type-tab.active { background: var(--accent-soft); color: var(--accent-ink); font-weight: var(--fw-semibold); }

.type-error {
  margin: 6px 0 0;
  color: var(--danger);
  font-size: var(--fs-13);
  line-height: 1.45;
}
.type-error:empty { display: none; }
.type-error-link {
  margin-left: var(--sp-2);
  color: var(--accent-ink);
  font-weight: var(--fw-bold);
  text-decoration: underline;
}

/* 发布到：顶栏右侧，紧邻主操作 */
.dest-control {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-shrink: 0;
}
.dest-control-label { font-size: var(--fs-12); color: var(--muted); white-space: nowrap; }
.sr-only { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; }
.dest-select {
  min-height: var(--tap);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--bg);
  color: var(--accent-ink);
  font: inherit;
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  padding: 0 10px;
  min-width: 0;
  max-width: 148px;
  cursor: pointer;
}
.dest-hint { margin-left: auto; font-size: var(--fs-12); line-height: 1.45; color: var(--muted); white-space: nowrap; }

.listing-wrap { margin-top: var(--sp-4); padding-top: var(--sp-3); border-top: 1px solid var(--border); }

.success {
  margin: var(--sp-2) var(--sp-4);
  color: var(--good);
  font-size: var(--fs-13);
}

/* 我的发布 feed */
.published-history { border-top: 1px solid var(--border); }
.published-history summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-height: 48px;
  padding: 0 16px;
  list-style: none;
  cursor: pointer;
  color: var(--text);
  font-size: 14px;
  font-weight: 700;
}
.published-history summary::-webkit-details-marker { display: none; }
.history-chev { color: var(--muted); transition: transform .2s; }
.published-history[open] .history-chev { transform: rotate(180deg); }
.feed { padding: 0 var(--sp-4) var(--sp-4); }
.feed-note { padding: var(--sp-4) 0; color: var(--muted); font-size: var(--fs-13); }
.post {
  display: flex;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
  color: inherit;
  text-decoration: none;
}
.post-body { flex: 1; min-width: 0; }
.post-head { display: flex; align-items: center; gap: var(--sp-2); }
.post-head .name { font-weight: var(--fw-bold); font-size: var(--fs-14); }
.post-title { display: block; margin-top: 2px; font-weight: var(--fw-bold); font-size: var(--fs-16); }
.post-copy { margin: 2px 0 0; font-size: var(--fs-15); line-height: var(--lh-body); color: var(--text); overflow-wrap: break-word; }
.status-pill {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 8px;
  border-radius: var(--r-pill);
  border: 1px dashed var(--warn);
  color: var(--warn);
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  white-space: nowrap;
}
.status-pill.published { border-style: solid; border-color: var(--good); color: var(--good); }
.status-pill.rejected { border-style: solid; border-color: var(--danger); color: var(--danger); }
/* 与 AppShell 单栏断点（759px）对齐，避免 481–759px 顶栏被目标选择器撑破 */
@media (max-width: 760px) {
  .topbar { gap: 6px; padding: var(--sp-2) 8px; }
  /* 窄屏标题与类型选择器重复，让位给「发布到」，否则下拉框看不出是选发布目标 */
  .topbar .title { display: none; }
  .dest-control { flex: 1; min-width: 0; }
  .dest-select { flex: 1; min-width: 0; max-width: 160px; padding: 0 8px; }
  .compose-switch { flex-wrap: wrap; }
  .dest-hint { margin-left: 0; }
}
@media (max-width: 480px) {
  .compose { gap: 10px; padding: 16px 14px 24px; }
  .body-input { min-height: 160px; }
}
.video-source {
  display: inline-flex;
  gap: 4px;
  padding: 3px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  width: fit-content;
}
.video-source-btn {
  min-height: 36px;
  padding: 0 var(--sp-3);
  border: 0;
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--muted);
  font-size: var(--fs-13);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.video-source-btn.active {
  background: var(--accent-soft);
  color: var(--text);
}
</style>
