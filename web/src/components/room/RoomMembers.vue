<script setup lang="ts">
// 私密房间的成员管理（只给房主）：看成员，移出并禁止再加入，或解除禁止。
// 后端：GET /{id}/members、PUT / DELETE /{id}/bans/{user_id}。
import { onMounted, ref } from "vue";
import { request, toMessage } from "../../api";
import { useToastStore } from "../../stores/toast";
import BaseButton from "../base/BaseButton.vue";
import Modal from "../base/Modal.vue";

type Person = { user_id: string; display_name: string; handle: string };

const props = defineProps<{ roomId: string }>();
const emit = defineEmits<{ (e: "changed"): void }>();

const toast = useToastStore();
const members = ref<Person[]>([]);
const banned = ref<Person[]>([]);
const busy = ref(false);
const removing = ref<Person | null>(null); // 正在确认移出的人

async function load(): Promise<void> {
  try {
    const body = await request<{ items: Person[]; banned: Person[] }>(`/api/v1/channels/${props.roomId}/members`);
    members.value = body.items;
    banned.value = body.banned;
  } catch (err) {
    toast.show(toMessage(err));
  }
}

async function setBan(person: Person, on: boolean): Promise<void> {
  if (busy.value) return;
  busy.value = true;
  try {
    await request(`/api/v1/channels/${props.roomId}/bans/${person.user_id}`, { method: on ? "PUT" : "DELETE" });
    removing.value = null;
    toast.show(on ? "已移出，对方不能再加入" : "已解除，对方可以重新申请加入");
    await load();
    emit("changed");
  } catch (err) {
    toast.show(toMessage(err));
  } finally {
    busy.value = false;
  }
}

onMounted(load);
defineExpose({ reload: load });
</script>

<template>
  <section class="room-members" aria-label="成员">
    <h2 class="members-title">成员（{{ members.length }}）</h2>
    <p v-if="!members.length" class="members-empty">还没有成员</p>
    <div v-for="person in members" :key="person.user_id" class="members-row">
      <span data-ugc>{{ person.display_name }}<small v-if="person.handle"> @{{ person.handle }}</small></span>
      <BaseButton size="sm" variant="outline" :disabled="busy" @click="removing = person">移出</BaseButton>
    </div>

    <template v-if="banned.length">
      <h2 class="members-title">已禁止加入（{{ banned.length }}）</h2>
      <div v-for="person in banned" :key="person.user_id" class="members-row">
        <span data-ugc>{{ person.display_name }}<small v-if="person.handle"> @{{ person.handle }}</small></span>
        <BaseButton size="sm" variant="outline" :disabled="busy" @click="setBan(person, false)">解除</BaseButton>
      </div>
    </template>

    <Modal :open="removing !== null" title="移出这位成员？" labelledby="room-remove-member-title" @close="removing = null">
      <p class="members-note">
        「<span data-ugc>{{ removing?.display_name }}</span>」会立刻看不到房间内容，以后也不能再申请加入。你可以随时在「已禁止加入」里解除。
      </p>
      <div class="members-actions">
        <BaseButton variant="ghost" :disabled="busy" @click="removing = null">取消</BaseButton>
        <BaseButton variant="danger" :loading="busy" @click="removing && setBan(removing, true)">移出并禁止加入</BaseButton>
      </div>
    </Modal>
  </section>
</template>

<style scoped>
.room-members {
  margin-bottom: var(--sp-5);
}
.members-title {
  margin: var(--sp-6) 0 var(--sp-3);
  font-size: var(--fs-16);
}
.members-empty,
.members-note {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-13);
}
.members-note {
  margin-bottom: var(--sp-4);
  font-size: var(--fs-14);
  line-height: 1.6;
}
.members-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--sp-3);
  padding: var(--sp-3) 0;
  border-bottom: 1px solid var(--border);
}
.members-row small {
  color: var(--muted);
}
.members-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--sp-2);
}
</style>
