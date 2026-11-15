<script setup lang="ts">
// 房间投稿 / 审核：房主（或协作者）看待审投稿队列并裁决，普通用户看投稿表单。
// 后端：GET/POST /{channel_id}/submissions、POST /{channel_id}/submissions/{content_id}/decision。
import { onMounted, ref } from "vue";
import { jsonBody, request, toMessage, type SubmissionsResponse } from "../../api";
import { useToastStore } from "../../stores/toast";
import BaseButton from "../base/BaseButton.vue";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";

const props = defineProps<{
  roomId: string;
  canModerate: boolean;
  /** 综合讨论房间的房主 / 协作者直接发帖（其他类型用 RoomManager 加条目） */
  canPost?: boolean;
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
  if (!title.value.trim() || !body.value.trim()) {
    toast.show("标题和正文都需要填写");
    return;
  }
  posting.value = true;
  try {
    await request(
      `/api/v1/channels/${props.roomId}/submissions`,
      jsonBody({ title: title.value.trim(), body: body.value.trim() }),
    );
    title.value = "";
    body.value = "";
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
    <!-- 房主/协作者：发帖走「发布内容」页（图片、视频、话题都有），预选这个房间 -->
    <RouterLink
      v-if="canModerate && canPost"
      class="btn btn--primary sub-post"
      :to="{ name: 'publish', query: { channel: roomId } }"
    >发帖到房间（可带图片、视频）</RouterLink>

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
        <TextArea id="submission-body" v-model="body" label="正文" :rows="3" required />
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
.sub-post {
  justify-self: start;
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
