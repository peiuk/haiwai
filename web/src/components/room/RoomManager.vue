<script setup lang="ts">
// 房主条目管理：添加条目（series 一次可加多集，每集一个视频 / film 封面图 / video 版权确认；图片最多 1 张，视频上传或外链二选一）、按集号重排。
// 上移/下移由 RoomItems 里的卡片按钮触发，事件经 RoomView 转发到本组件处理。
import { ref } from "vue";
import { useToastStore } from "../../stores/toast";
import { request, jsonBody } from "../../api";
import BaseButton from "../base/BaseButton.vue";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";
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
const imageKeys = ref<string[]>([]);
const videoKey = ref("");
const videoUrl = ref("");
const busy = ref(false);

// ---- 剧集：一次可以填好几集，每集一个视频（上传或外链二选一）、一张可不传的图 ----
type EpisodeRow = { key: number; episode: string; title: string; imageKeys: string[]; videoKey: string; videoUrl: string };
let rowSeq = 0;
const blankRow = (episode = ""): EpisodeRow => ({ key: ++rowSeq, episode, title: "", imageKeys: [], videoKey: "", videoUrl: "" });
const rows = ref<EpisodeRow[]>([blankRow()]);

function addRow(): void {
  const last = Number(rows.value[rows.value.length - 1]?.episode);
  rows.value.push(blankRow(Number.isInteger(last) && last > 0 ? String(last + 1) : "")); // 集号顺着上一集往下排
}

function removeRow(key: number): void {
  rows.value = rows.value.filter((row) => row.key !== key);
  if (!rows.value.length) rows.value = [blankRow()];
}

async function addEpisodes(): Promise<void> {
  for (const row of rows.value) {
    const number = Number(row.episode);
    if (!Number.isInteger(number) || number < 1 || number > 999) {
      toast.show("请填集号（1 到 999 的整数）");
      return;
    }
    if (Boolean(row.videoKey) === Boolean(row.videoUrl.trim())) {
      toast.show(`第 ${number} 集需要一个视频：上传一段，或者贴一个外链（二选一）`);
      return;
    }
  }
  busy.value = true;
  const lastEpisode = Number(rows.value[rows.value.length - 1].episode);
  let done = 0;
  try {
    for (const row of rows.value) {
      await request(
        `/api/v1/channels/${props.roomId}/entries`,
        jsonBody({
          title: row.title.trim() || `第 ${row.episode} 集`,
          episode: Number(row.episode),
          image_keys: row.imageKeys,
          video_key: row.videoKey || null,
          video_url: row.videoUrl.trim() || null,
        }),
      );
      done += 1;
    }
    toast.show(done > 1 ? `已添加 ${done} 集` : "已添加");
    rows.value = [blankRow(String(lastEpisode + 1))];
  } catch (err) {
    // 前面成功的已经加进去了，只留下没成功的，改好再提交一次就行
    const failed = rows.value[done];
    rows.value = rows.value.slice(done);
    toast.show(`第 ${failed.episode} 集没有添加成功：${err instanceof Error ? err.message : "请稍后再试"}`);
  } finally {
    busy.value = false;
    if (done > 0) emit("changed");
  }
}

function resetForm(): void {
  title.value = "";
  body.value = "";
  imageKeys.value = [];
  videoKey.value = "";
  videoUrl.value = "";
}

async function addEntry(): Promise<void> {
  if (!title.value.trim() || !body.value.trim()) {
    toast.show("标题和正文都需要填写");
    return;
  }
  if (videoKey.value && videoUrl.value.trim()) {
    toast.show("上传视频和视频外链只能选一个");
    return;
  }
  busy.value = true;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/entries`,
      jsonBody({
        title: title.value.trim(),
        body: body.value.trim(),
        image_keys: imageKeys.value,
        video_key: videoKey.value || null,
        video_url: videoUrl.value.trim() || null,
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
    <form v-if="roomType === 'series'" class="manager-form" @submit.prevent="addEpisodes">
      <fieldset v-for="row in rows" :key="row.key" class="episode-row">
        <div class="form-row">
          <TextField :id="`ep-${row.key}-no`" v-model="row.episode" label="集号" type="number" required />
          <TextField :id="`ep-${row.key}-title`" v-model="row.title" label="标题（可不填，默认「第 N 集」）" />
        </div>
        <UploadField
          :id="`ep-${row.key}-video`"
          v-model="row.videoKey"
          label="上传视频"
          accept="video/mp4,video/webm,video/quicktime"
          :max-mb="100"
          hint="mp4 / webm / mov，不超过 100MB"
        />
        <TextField
          :id="`ep-${row.key}-url`"
          v-model="row.videoUrl"
          label="或者贴视频外链"
          type="url"
          placeholder="https://www.youtube.com/watch?v=… 或 https://www.bilibili.com/video/BV…"
          hint="每一集需要一个视频：上传和外链二选一"
        />
        <MultiUploadField :id="`ep-${row.key}-img`" v-model="row.imageKeys" label="图片（可选，1 张）" :max="1" accept="image/jpeg,image/png,image/webp" :max-mb="5" />
        <BaseButton v-if="rows.length > 1" type="button" variant="ghost" size="sm" @click="removeRow(row.key)">删除这一集</BaseButton>
      </fieldset>
      <div class="form-actions">
        <BaseButton type="button" variant="outline" @click="addRow">+ 添加一集</BaseButton>
        <BaseButton type="submit" :loading="busy" variant="primary">{{ rows.length > 1 ? `添加 ${rows.length} 集` : "添加" }}</BaseButton>
        <BaseButton type="button" variant="ghost" @click="reorderByEpisode">按集号重排</BaseButton>
      </div>
    </form>
    <form v-else class="manager-form" @submit.prevent="addEntry">
      <TextField id="entry-title" v-model="title" label="标题" required />
      <TextArea id="entry-body" v-model="body" label="正文" :rows="3" required />

      <MultiUploadField
        id="entry-images"
        v-model="imageKeys"
        label="图片（可选，1 张）"
        :max="1"
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
      <TextField
        id="entry-video-url"
        v-model="videoUrl"
        label="或者贴视频外链（可选）"
        type="url"
        placeholder="https://www.youtube.com/watch?v=… 或 https://www.bilibili.com/video/BV…"
        hint="支持 YouTube、哔哩哔哩，和上传视频二选一；大家点开后在站内播放"
      />

      <div class="form-actions">
        <BaseButton type="submit" :loading="busy" variant="primary">添加条目</BaseButton>
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
.episode-row {
  display: grid;
  gap: var(--sp-3);
  margin: 0;
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-lg);
}
.form-actions {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
</style>
