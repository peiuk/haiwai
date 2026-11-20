<script setup lang="ts">
// 首页内嵌发布框（X 式），对齐 prototype-x-style.html 的 homeComposerHTML。
// 仅桌面端显示；移动端（≤760px）隐藏，发布走右下角 FAB。
// 发布逻辑复用 POST /contents（同 PublishView）。
import { computed, ref, watch } from "vue";
import { jsonBody, request, uploadFile, type PublishResponse } from "../../api";
import { hashTags } from "../../utils/post";
import { BG_MAX_LEN, bgStyleOf } from "../../utils/postBg";
import BgPicker from "../common/BgPicker.vue";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import Avatar from "../base/Avatar.vue";
import BaseIcon from "../base/BaseIcon.vue";
import Progress from "../base/Progress.vue";

const auth = useAuthStore();
const toast = useToastStore();

type ContentType = "text" | "video";
const TYPES: { value: ContentType; label: string; icon: string }[] = [
  { value: "text", label: "图文", icon: "i-image" },
  { value: "video", label: "视频", icon: "i-video" },
];

const body = ref("");
const title = ref("");
const currentType = ref<ContentType>("text");
const open = ref(false);
// 话题不再单独输入：正文里写 #词 就是话题，后端按同样规则从正文里取
const topics = computed(() => hashTags(body.value));
// 城市话题：默认取注册时填的城市名，作为发帖自动带上的话题之一（可删除）。
const cityTopic = ref("");
const cityInited = ref(false);
const imageKeys = ref<string[]>([]);
const imageBusy = ref(false);
const imageProgress = ref(0);
const justAdded = ref(new Set<string>());
const videoKey = ref("");
const videoName = ref("");
const videoBusy = ref(false);
const videoProgress = ref(0);
const busy = ref(false);
const error = ref("");

const MAX_LEN = 2000;
const count = computed(() => body.value.length);
const countOver = computed(() => count.value > MAX_LEN);

// 彩色背景：只给不带图的短文字帖；字写多了自动退回普通样式（选择保留，删短了又会变回来）
const bg = ref("");
const bgTooLong = computed(() => body.value.trim().length > BG_MAX_LEN);
const bgCss = computed(() =>
  currentType.value === "text" && !imageKeys.value.length && !bgTooLong.value ? bgStyleOf(bg.value) : null,
);

const canPublish = computed(() => {
  if (!body.value.trim() || body.value.trim().length < 2) return false;
  if (currentType.value === "video" && !videoKey.value) return false;
  return true;
});

function setType(tp: ContentType): void {
  currentType.value = tp;
  error.value = "";
}

function triggerImage(): void {
  document.getElementById("home-composer-image")?.click();
}
function triggerVideo(): void {
  // 工具栏点「视频」也切到视频帖，否则传上去的视频发帖时不会带上
  setType("video");
  document.getElementById("home-composer-video")?.click();
}

async function onImage(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files ?? []);
  if (!files.length) return;
  const room = 6 - imageKeys.value.length;
  const picked = files.slice(0, room);
  if (picked.length < files.length) {
    toast.show("最多上传 6 张图片");
  }
  imageBusy.value = true;
  let failed = 0;
  for (const file of picked) {
    imageProgress.value = 0;
    try {
      const key = await uploadFile(file, undefined, (p) => (imageProgress.value = p));
      imageKeys.value.push(key);
      justAdded.value.add(key);
    } catch (err) {
      failed += 1;
    }
  }
  imageBusy.value = false;
  if (picked.length > failed) {
    toast.show(failed ? `已上传 ${picked.length - failed} 张，${failed} 张失败` : "图片已上传，提交发布后才会公开");
  } else if (failed) {
    toast.show("图片上传没有成功");
  }
  input.value = "";
}

function removeImage(i: number): void {
  imageKeys.value.splice(i, 1);
}

async function onVideo(e: Event): Promise<void> {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  videoBusy.value = true;
  videoProgress.value = 0;
  videoName.value = file.name;
  videoKey.value = "";
  try {
    videoKey.value = await uploadFile(file, undefined, (p) => (videoProgress.value = p));
    toast.show(`视频「${file.name}」已上传，提交发布后才会公开`);
  } catch (err) {
    videoName.value = "";
    toast.show(`视频「${file.name}」${err instanceof Error ? err.message : "上传没有成功"}`);
  } finally {
    videoBusy.value = false;
    input.value = "";
  }
}

function removeVideo(): void {
  videoKey.value = "";
  videoName.value = "";
}

const emit = defineEmits<{ (e: "published"): void }>();

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

async function submit(): Promise<void> {
  if (!auth.isLoggedIn) {
    toast.show("发布前需要先登录或注册");
    return;
  }
  error.value = "";
  busy.value = true;
  try {
    const payload: Record<string, unknown> = {
      title: title.value.trim() || body.value.trim().slice(0, 40),
      body: body.value.trim(),
      post_type: currentType.value === "video" ? "video" : "text",
    };
    // 城市话题：有则默认随帖；用户删除了则显式传空串。
    if (cityTopic.value) payload.city_topic = cityTopic.value;
    else if (cityInited.value) payload.city_topic = "";
    if (imageKeys.value.length) payload.image_keys = imageKeys.value;
    if (currentType.value === "video") payload.video_key = videoKey.value;
    if (bgCss.value) payload.bg_style = bg.value;
    await request<PublishResponse>("/api/v1/contents", jsonBody(payload));
    toast.show("已发布，审核通过后会公开");
    body.value = "";
    title.value = "";
    imageKeys.value = [];
    videoKey.value = "";
    videoName.value = "";
    bg.value = "";
    currentType.value = "text";
    open.value = false;
    // 发布成功后恢复默认城市话题（下次发帖仍默认带上）
    cityTopic.value = auth.profile?.city_label ?? "";
    cityInited.value = true;
    emit("published");
  } catch (err) {
    error.value = err instanceof Error ? err.message : "发布没有成功";
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="home-composer">
    <Avatar name="我" :size="44" class="home-composer-avatar" :image="auth.profile?.avatar_key" />

    <div class="home-composer-body">
      <div class="home-composer-top">
        <span class="home-composer-label">发布到</span>
        <span class="home-composer-destination">我的动态 · 审核后公开</span>
      </div>

      <textarea
        v-model="body"
        :class="{ 'is-bg': bgCss }"
        :style="bgCss ?? undefined"
        :rows="open ? 4 : 1"
        maxlength="2000"
        placeholder="分享你所在城市的发现… 写 #关键词 加话题"
        aria-label="帖子正文"
        @focus="open = true"
      ></textarea>

      <div v-if="open" class="home-composer-options">
        <div class="home-compose-types" role="tablist" aria-label="帖子类型">
          <button
            v-for="t in TYPES"
            :key="t.value"
            type="button"
            class="home-compose-type"
            :class="{ active: currentType === t.value }"
            role="tab"
            :aria-selected="currentType === t.value"
            @click="setType(t.value)"
          >
            <BaseIcon :name="t.icon" :size="14" />
            {{ t.label }}
          </button>
        </div>

        <BgPicker v-if="currentType === 'text' && !imageKeys.length" v-model="bg" class="home-compose-bg" :disabled="bgTooLong" />

        <!-- 视频标题 -->
        <div v-if="currentType === 'video'" class="home-compose-extra">
          <div class="field">
            <label for="home-composer-title">视频标题（选填）</label>
            <input
              id="home-composer-title"
              v-model="title"
              maxlength="80"
              placeholder="给视频加个标题"
            />
          </div>
        </div>

        <div v-if="topics.length || cityTopic" class="home-compose-topics" aria-label="这条帖子会带上的话题">
          <!-- 话题和帖子卡片上一样能点进搜索；首页是缓存的，回来时写到一半的内容还在 -->
          <span v-if="cityTopic" class="home-compose-topic home-compose-city-topic">
            <RouterLink class="home-compose-topic-link" :to="{ name: 'search', query: { q: `#${cityTopic}` } }" :title="`搜索城市话题 ${cityTopic}`">
              <BaseIcon name="i-pin" :size="12" />{{ cityTopic }}
            </RouterLink>
            <button type="button" :aria-label="`删除城市话题 ${cityTopic}`" @click="cityTopic = ''">
              <BaseIcon name="i-close" :size="13" />
            </button>
          </span>
          <RouterLink
            v-for="t in topics"
            :key="t"
            class="home-compose-topic home-compose-topic-link"
            :to="{ name: 'search', query: { q: `#${t}` } }"
          >#{{ t }}</RouterLink>
        </div>

        <!-- 已选图片缩略图预览（上传成功即显示小图） -->
        <div v-if="imageKeys.length" class="home-compose-thumbs" aria-label="已选择的图片">
          <div v-for="(key, i) in imageKeys" :key="key" class="home-compose-thumb">
            <img :src="`/api/v1/uploads/${key}`" :alt="`已上传图片 ${i + 1}`" loading="lazy" />
            <span v-if="justAdded.has(key)" class="home-compose-done" aria-hidden="true"><BaseIcon name="i-check" :size="14" /></span>
            <button type="button" :aria-label="`移除第 ${i + 1} 张图片`" @click="removeImage(i)">
              <BaseIcon name="i-close" :size="14" />
            </button>
          </div>
          <div v-if="imageBusy" class="home-compose-thumb home-compose-thumb--busy" aria-live="polite">
            <span>{{ imageProgress >= 100 ? "处理中" : `${imageProgress}%` }}</span>
            <Progress :value="imageProgress" :pending="imageProgress >= 100" label="图片上传进度" />
          </div>
        </div>

        <!-- 视频：上传中显示文件名 + 进度，传完打勾 -->
        <div v-if="videoBusy || videoKey" :key="videoKey || 'busy'" class="home-compose-video" :class="{ 'is-done': !videoBusy }" aria-live="polite">
          <span class="home-compose-video-icon">
            <BaseIcon :name="videoBusy ? 'i-video' : 'i-check'" :size="16" />
          </span>
          <div class="home-compose-video-info">
            <span class="home-compose-video-name">{{ videoName || "视频" }}</span>
            <template v-if="videoBusy">
              <Progress :value="videoProgress" :pending="videoProgress >= 100" :label="`${videoName} 上传进度`" />
              <span class="home-compose-video-state">{{ videoProgress >= 100 ? "处理中…（压缩需要一会儿）" : `上传中 ${videoProgress}%` }}</span>
            </template>
            <span v-else class="home-compose-video-state">已上传</span>
          </div>
          <button v-if="!videoBusy" type="button" :aria-label="`移除视频 ${videoName}`" @click="removeVideo">
            <BaseIcon name="i-close" :size="14" />
          </button>
        </div>
      </div>

      <!-- 隐藏的上传 input -->
      <input id="home-composer-image" class="sr-only" type="file" accept="image/png,image/jpeg,image/webp" multiple @change="onImage" />
      <input id="home-composer-video" class="sr-only" type="file" accept="video/mp4,video/webm,video/quicktime" @change="onVideo" />

      <div class="home-compose-toolbar">
        <button type="button" class="home-compose-tool" title="添加图片" @click="triggerImage">
          <BaseIcon name="i-image" :size="16" /><span>图片</span>
        </button>
        <button type="button" class="home-compose-tool" title="添加视频" @click="triggerVideo">
          <BaseIcon name="i-video" :size="16" /><span>视频</span>
        </button>
        <span class="home-compose-spacer"></span>
        <span class="home-compose-count" :class="{ over: countOver }">{{ count }} / {{ MAX_LEN }}</span>
        <button
          type="button"
          class="home-compose-submit"
          :disabled="!canPublish || busy || imageBusy || videoBusy"
          @click="submit"
        >
          {{ busy ? "发布中…" : "发布" }}
        </button>
      </div>
      <p v-if="error" class="home-compose-error" role="alert">{{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.home-composer {
  display: flex;
  gap: 12px;
  padding: 14px 16px;
  border-bottom: 1px solid var(--border);
  align-items: flex-start;
}
.home-composer-avatar {
  flex-shrink: 0;
}
.home-composer-body {
  flex: 1;
  min-width: 0;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  padding: 10px 12px;
}
.home-composer-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 5px;
}
.home-composer-label {
  font-size: 12px;
  color: var(--muted);
}
.home-composer-destination {
  min-height: 44px;
  max-width: 190px;
  padding: 3px 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: var(--bg);
  color: var(--accent-ink);
  font-size: 12px;
  font-weight: 600;
  display: inline-flex;
  align-items: center;
}
.home-composer textarea {
  display: block;
  width: 100%;
  min-height: 44px;
  resize: vertical;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--text);
  font: inherit;
  font-size: 15px;
  line-height: 1.55;
  padding: 6px 0;
}
.home-composer textarea::placeholder {
  color: var(--muted);
}
/* 选了彩色背景：输入框就是发出去的样子（字大、居中、在色块上） */
.home-composer textarea.is-bg {
  min-height: 180px;
  padding: 56px 16px;
  border-radius: var(--r-lg);
  font-size: 22px;
  font-weight: 700;
  line-height: 1.4;
  text-align: center;
  resize: none;
}
.home-composer textarea.is-bg::placeholder {
  color: inherit;
  opacity: 0.7;
}
.home-compose-bg {
  margin-top: 10px;
}
.home-composer-options {
  border-top: 1px solid var(--border);
  margin-top: 8px;
  padding-top: 10px;
}
.home-compose-types {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  scrollbar-width: none;
}
.home-compose-types::-webkit-scrollbar {
  display: none;
}
.home-compose-type {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  min-height: 44px;
  padding: 0 12px;
  border: 1px solid transparent;
  border-radius: var(--r-pill);
  color: var(--muted);
  font-size: 12px;
  white-space: nowrap;
}
.home-compose-type:hover {
  background: var(--hover);
}
.home-compose-type.active {
  border-color: var(--line);
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-weight: 700;
}
.home-compose-extra {
  display: flex;
  gap: 8px;
  align-items: flex-end;
  margin-top: 10px;
}
.home-compose-extra .field {
  flex: 1;
  min-width: 0;
}
.home-compose-extra label {
  display: block;
  margin-bottom: 4px;
  color: var(--muted);
  font-size: 12px;
}
.home-compose-extra input {
  width: 100%;
  min-height: 44px;
  padding: 7px 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--bg);
  color: var(--text);
  font: inherit;
  font-size: 13px;
}
.home-compose-topics {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.home-compose-topic {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  min-height: 28px;
  padding: 2px 8px;
  border-radius: var(--r-pill);
  background: var(--accent-soft);
  color: var(--accent-ink);
  font-size: 12px;
}
.home-compose-topic button {
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
.home-compose-topic-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: inherit;
  text-decoration: none;
}
.home-compose-topic-link:hover,
.home-compose-topic-link:focus-visible {
  text-decoration: underline;
}
.home-compose-city-topic {
  background: var(--surface2);
  color: var(--text);
  border: 1px dashed var(--line);
}
.home-compose-thumbs {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 10px;
}
.home-compose-thumb {
  position: relative;
  width: 72px;
  height: 72px;
  border-radius: var(--r-md);
  overflow: hidden;
  border: 1px solid var(--line);
  background: var(--surface2);
}
.home-compose-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.home-compose-thumb button {
  position: absolute;
  top: 3px;
  right: 3px;
  display: grid;
  place-items: center;
  width: 22px;
  height: 22px;
  border: 0;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.6);
  color: #fff;
  cursor: pointer;
}
.home-compose-thumb button:hover {
  background: rgba(0, 0, 0, 0.85);
}
.home-compose-thumb--busy {
  display: grid;
  align-content: center;
  gap: 6px;
  padding: 0 8px;
  color: var(--muted);
  font-size: 12px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}
/* 刚传完的图：✓ 弹出来再淡掉 */
.home-compose-done {
  position: absolute;
  inset: 0;
  margin: auto;
  display: grid;
  place-items: center;
  width: 26px;
  height: 26px;
  border-radius: 50%;
  background: var(--accent);
  color: var(--on-accent, #fff);
  pointer-events: none;
  animation: compose-done 1.8s var(--ease-out, ease-out) forwards;
}
@keyframes compose-done {
  0% { transform: scale(0); opacity: 1; }
  15% { transform: scale(1.2); }
  25%, 75% { transform: scale(1); opacity: 1; }
  100% { transform: scale(1); opacity: 0; }
}
.home-compose-video {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 10px;
  padding: 8px 10px;
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface2);
}
.home-compose-video.is-done {
  border-color: var(--accent);
  animation: compose-video-done 0.4s var(--ease-out, ease-out);
}
@keyframes compose-video-done {
  from { background: var(--accent-soft); }
}
.home-compose-video-icon {
  display: grid;
  place-items: center;
  flex: none;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--accent-soft);
  color: var(--accent-ink);
}
.home-compose-video.is-done .home-compose-video-icon {
  background: var(--accent);
  color: var(--on-accent, #fff);
  animation: compose-pop 0.35s var(--ease-out, ease-out);
}
@keyframes compose-pop {
  0% { transform: scale(0); }
  70% { transform: scale(1.2); }
}
.home-compose-video-info {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: 4px;
}
.home-compose-video-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 13px;
  font-weight: 600;
}
.home-compose-video-state {
  color: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.home-compose-video button {
  display: grid;
  place-items: center;
  flex: none;
  width: 32px;
  height: 32px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--muted);
  cursor: pointer;
}
.home-compose-video button:hover {
  background: var(--hover);
}
@media (prefers-reduced-motion: reduce) {
  .home-compose-done { animation: none; opacity: 0; }
  .home-compose-video.is-done,
  .home-compose-video.is-done .home-compose-video-icon { animation: none; }
}
.home-compose-toolbar {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 8px;
  padding-top: 7px;
  border-top: 1px solid var(--border);
}
.home-compose-tool {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 5px;
  min-width: 44px;
  min-height: 44px;
  padding: 0 9px;
  border: 0;
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--accent-ink);
  font-size: 12px;
  cursor: pointer;
}
.home-compose-tool:hover {
  background: var(--accent-soft);
}
.home-compose-spacer {
  flex: 1;
}
.home-compose-count {
  color: var(--muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}
.home-compose-count.over {
  color: var(--danger);
}
.home-compose-submit {
  min-height: 44px;
  padding: 0 16px;
  border: 0;
  border-radius: var(--r-pill);
  background: var(--accent-strong);
  color: var(--on-accent);
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}
.home-compose-submit:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}
.home-compose-error {
  min-height: 0;
  margin: 6px 0 0;
  color: var(--danger);
  font-size: 12px;
}
.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* 移动端（≤760px）隐藏内嵌发布框，发布走 FAB */
@media (max-width: 760px) {
  .home-composer {
    display: none;
  }
}
</style>
