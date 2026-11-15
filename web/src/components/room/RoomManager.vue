<script setup lang="ts">
// 房主条目管理：添加条目（series 季集 / film 封面图 / video 版权确认；都可带图片和一段视频）、按集号重排。
// 上移/下移由 RoomItems 里的卡片按钮触发，事件经 RoomView 转发到本组件处理。
import { ref } from "vue";
import { useToastStore } from "../../stores/toast";
import { request, jsonBody } from "../../api";
import BaseButton from "../base/BaseButton.vue";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";
import Checkbox from "../base/Checkbox.vue";
import MultiUploadField from "../common/MultiUploadField.vue";
import UploadField from "../common/UploadField.vue";

const props = defineProps<{
  roomId: string;
  roomType: string;
}>();

const emit = defineEmits<{
  (e: "changed"): void;
}>();

const toast = useToastStore();

const title = ref("");
const body = ref("");
const season = ref("");
const episode = ref("");
const imageKeys = ref<string[]>([]);
const videoKey = ref("");
const rightsConfirmed = ref(false);
const busy = ref(false);

function resetForm(): void {
  title.value = "";
  body.value = "";
  season.value = "";
  episode.value = "";
  imageKeys.value = [];
  videoKey.value = "";
  rightsConfirmed.value = false;
}

async function addEntry(): Promise<void> {
  if (!title.value.trim() || !body.value.trim()) {
    toast.show("标题和正文都需要填写");
    return;
  }
  const seasonNum = season.value ? Number(season.value) : null;
  const episodeNum = episode.value ? Number(episode.value) : null;
  if (props.roomType === "series" && (seasonNum == null || episodeNum == null)) {
    toast.show("剧集需要填写季和集");
    return;
  }
  if (props.roomType === "video" && !rightsConfirmed.value) {
    toast.show("原创视频需要确认人物同意且无未授权内容");
    return;
  }
  busy.value = true;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/entries`,
      jsonBody({
        title: title.value.trim(),
        body: body.value.trim(),
        season: props.roomType === "series" ? seasonNum : null,
        episode: props.roomType === "series" ? episodeNum : null,
        rights_confirmed: props.roomType === "video" ? rightsConfirmed.value : false,
        image_keys: imageKeys.value,
        video_key: videoKey.value || null,
      }),
    );
    toast.show("条目已添加");
    resetForm();
    emit("changed");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "添加失败");
  } finally {
    busy.value = false;
  }
}

async function reorderByEpisode(): Promise<void> {
  try {
    await request(`/api/v1/channels/${props.roomId}/entries/reorder`, { method: "POST" });
    toast.show("已按集号重排");
    emit("changed");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "重排失败");
  }
}

async function moveEntry(contentId: string, direction: "up" | "down"): Promise<void> {
  try {
    await request(
      `/api/v1/channels/${props.roomId}/entries/${contentId}/move`,
      jsonBody({ direction }),
    );
    emit("changed");
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "移动失败");
  }
}

defineExpose({ moveEntry, reorderByEpisode });
</script>

<template>
  <details class="room-manager">
    <summary class="manager-toggle">房主工具 · 添加条目</summary>
    <form class="manager-form" @submit.prevent="addEntry">
      <TextField id="entry-title" v-model="title" label="标题" required />
      <TextArea id="entry-body" v-model="body" label="正文" :rows="3" required />

      <div v-if="roomType === 'series'" class="form-row">
        <TextField id="entry-season" v-model="season" label="季" type="number" inputmode="numeric" />
        <TextField id="entry-episode" v-model="episode" label="集" type="number" inputmode="numeric" />
      </div>
      <Checkbox v-else-if="roomType === 'video'" id="entry-rights" v-model="rightsConfirmed" label="确认是本人原创视频，已取得人物同意，且不含未授权音乐或影视片段" />

      <MultiUploadField
        id="entry-images"
        v-model="imageKeys"
        :label="roomType === 'film' ? '封面图片（可选）' : '图片（可选，最多 4 张）'"
        :max="roomType === 'film' ? 1 : 4"
        accept="image/jpeg,image/png,image/webp"
        :max-mb="5"
      />
      <UploadField
        id="entry-video"
        v-model="videoKey"
        label="视频（可选，1 段）"
        accept="video/mp4,video/webm,video/quicktime"
        :max-mb="100"
        hint="mp4 / webm / mov，不超过 100MB"
      />

      <div class="form-actions">
        <BaseButton type="submit" :loading="busy" variant="primary">添加条目</BaseButton>
        <BaseButton v-if="roomType === 'series'" type="button" variant="ghost" @click="reorderByEpisode">按集号重排</BaseButton>
      </div>
    </form>
  </details>
</template>

<style scoped>
.room-manager {
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
  padding: var(--sp-3);
}
.manager-toggle {
  cursor: pointer;
  font-weight: 600;
  font-size: var(--fs-14);
}
.manager-form {
  display: grid;
  gap: var(--sp-3);
  margin-top: var(--sp-3);
}
.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--sp-3);
}
.form-actions {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
</style>
