<script setup lang="ts">
// 房间投稿 / 审核：房主（或协作者）看待审投稿队列并裁决，普通用户看投稿表单。
// 后端：GET/POST /{channel_id}/submissions、POST /{channel_id}/submissions/{content_id}/decision。
import { onMounted, ref } from "vue";
import { jsonBody, request, toMessage, type SubmissionsResponse } from "../../api";
import { useToastStore } from "../../stores/toast";
import BaseButton from "../base/BaseButton.vue";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";
import MultiUploadField from "../common/MultiUploadField.vue";
import UploadField from "../common/UploadField.vue";

const props = defineProps<{
  roomId: string;
  canModerate: boolean;
}>();

const emit = defineEmits<{
  (e: "changed"): void;
}>();

const toast = useToastStore();

// —— 待审队列（房主/协作者）——
const submissions = ref<SubmissionsResponse["items"]>([]);
const loading = ref(false);
const decidingId = ref("");

// —— 投稿表单（普通用户）——
const title = ref("");
const body = ref("");
const imageKeys = ref<string[]>([]);
const videoKey = ref("");
const videoUrl = ref("");
const posting = ref(false);

async function loadSubmissions(): Promise<void> {
  if (!props.canModerate) return;
  loading.value = true;
  try {
    const result = await request<SubmissionsResponse>(`/api/v1/channels/${props.roomId}/submissions`);
    submissions.value = result.items;
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    loading.value = false;
  }
}

async function decide(contentId: string, decision: "accept" | "reject"): Promise<void> {
  if (decidingId.value) return;
  decidingId.value = contentId;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/submissions/${contentId}/decision`,
      jsonBody({ decision }),
    );
    submissions.value = submissions.value.filter((item) => item.content_id !== contentId);
    toast.show(decision === "accept" ? "已通过投稿" : "已拒绝投稿");
    emit("changed");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    decidingId.value = "";
  }
}

async function submit(): Promise<void> {
  if (!title.value.trim()) {
    toast.show("请填写标题");
    return;
  }
  if (!body.value.trim() && !imageKeys.value.length && !videoKey.value && !videoUrl.value.trim()) {
    toast.show("正文、图片、视频至少要有一样");
    return;
  }
  if (videoKey.value && videoUrl.value.trim()) {
    toast.show("上传视频和视频外链只能选一个");
    return;
  }
  posting.value = true;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/submissions`,
      jsonBody({
        title: title.value.trim(),
        body: body.value.trim(),
        image_keys: imageKeys.value,
        video_key: videoKey.value || null,
        video_url: videoUrl.value.trim() || null,
      }),
    );
    title.value = "";
    body.value = "";
    imageKeys.value = [];
    videoKey.value = "";
    videoUrl.value = "";
    toast.show("投稿已提交，等待房主审核");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    posting.value = false;
  }
}

onMounted(() => {
  if (props.canModerate) void loadSubmissions();
});
</script>

<template>
  <section class="room-submissions" :aria-label="canModerate ? '待审投稿' : '投稿'">
    <!-- 房主/协作者：待审队列 -->
    <template v-if="canModerate">
      <h2 class="sub-title">待审投稿</h2>
      <p v-if="loading" class="sub-empty">加载中…</p>
      <p v-else-if="!submissions.length" class="sub-empty">暂无待审核的投稿</p>
      <div v-else class="sub-list">
        <div v-for="item in submissions" :key="item.content_id" class="sub-row">
          <div class="sub-main">
            <strong class="sub-item-title" data-ugc>{{ item.title }}</strong>
            <p v-if="item.summary" class="sub-item-summary" data-ugc>{{ item.summary }}</p>
            <div v-if="item.image_keys.length" class="sub-media">
              <img v-for="key in item.image_keys" :key="key" :src="`/api/v1/uploads/${key}`" alt="投稿图片" loading="lazy" />
            </div>
            <video v-if="item.video_key" class="sub-video" :src="`/api/v1/uploads/${item.video_key}`" controls preload="metadata" aria-label="投稿视频"></video>
            <a v-if="item.embed_source_url" class="sub-link" :href="item.embed_source_url" target="_blank" rel="noopener noreferrer">视频外链：{{ item.embed_source_url }}</a>
            <p class="sub-item-meta">
              <span data-ugc>{{ item.author_name }}</span>
              <span v-if="item.author_handle">@{{ item.author_handle }}</span>
              <time :datetime="item.created_at">{{ item.created_at.slice(0, 10) }}</time>
            </p>
          </div>
          <div class="sub-actions">
            <BaseButton
              size="sm"
              variant="outline"
              :disabled="Boolean(decidingId)"
              @click="decide(item.content_id, 'reject')"
            >拒绝</BaseButton>
            <BaseButton
              size="sm"
              :loading="decidingId === item.content_id"
              :disabled="Boolean(decidingId)"
              @click="decide(item.content_id, 'accept')"
            >通过</BaseButton>
          </div>
        </div>
      </div>
    </template>

    <!-- 普通用户：投稿表单 -->
    <template v-else>
      <h2 class="sub-title">投稿到房间</h2>
      <form class="sub-form" @submit.prevent="submit">
        <TextField id="submission-title" v-model="title" label="标题" required />
        <TextArea id="submission-body" v-model="body" label="正文（带图片或视频时可以不写）" :rows="3" />
        <MultiUploadField
          id="submission-images"
          v-model="imageKeys"
          label="图片（可选）"
          accept="image/jpeg,image/png,image/webp"
          :max-mb="5"
          :max="6"
          hint="jpeg / png / webp，单张最大 5MB；第一张为封面"
        />
        <UploadField
          id="submission-video"
          v-model="videoKey"
          label="视频（可选，1 段）"
          accept="video/mp4,video/webm,video/quicktime"
          :max-mb="200"
          hint="mp4 / webm / mov，不超过 200MB、3 分钟"
        />
        <TextField
          id="submission-video-url"
          v-model="videoUrl"
          label="或者贴视频外链（可选）"
          type="url"
          placeholder="https://youtu.be/… 或 https://www.bilibili.com/video/BV…"
          hint="支持 YouTube、哔哩哔哩，和上传视频二选一"
        />
        <div class="sub-form-actions">
          <BaseButton type="submit" :loading="posting" variant="primary">提交投稿</BaseButton>
        </div>
        <p class="sub-hint">投稿将进入审核队列，由房主审核后发布。</p>
      </form>
    </template>
  </section>
</template>

<style scoped>
.room-submissions {
  display: grid;
  gap: var(--sp-3);
}
.sub-title {
  margin: 0;
  font-size: var(--fs-16);
}
.sub-empty,
.sub-hint {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.sub-list {
  display: grid;
  gap: var(--sp-2);
}
.sub-row {
  display: flex;
  align-items: flex-start;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.sub-main {
  flex: 1;
  min-width: 0;
  display: grid;
  gap: var(--sp-1);
}
.sub-item-title {
  font-size: var(--fs-14);
  overflow-wrap: anywhere;
}
.sub-item-summary {
  margin: 0;
  color: var(--text);
  font-size: var(--fs-13);
  overflow-wrap: anywhere;
}
.sub-media {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-1);
}
.sub-media img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: var(--r-sm);
}
.sub-video {
  width: 100%;
  max-height: 240px;
  border-radius: var(--r-sm);
  background: #000;
}
.sub-link {
  font-size: var(--fs-12);
  overflow-wrap: anywhere;
}
.sub-item-meta {
  margin: 0;
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  color: var(--muted);
  font-size: var(--fs-12);
}
.sub-actions {
  display: flex;
  gap: var(--sp-2);
  flex-shrink: 0;
}
.sub-form {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-md);
  background: var(--surface);
}
.sub-form-actions {
  display: flex;
}
@media (max-width: 480px) {
  .sub-row {
    flex-direction: column;
  }
  .sub-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
