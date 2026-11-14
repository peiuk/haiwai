<script setup lang="ts">
// 分类信息发布表单（MASTER §22.7）：结构化字段按类别自动切换。
// 对齐 POST /api/v1/listings（ListingBody）：category/kind 必须匹配，价格单位按 kind 约束。
import { computed, onMounted, ref, watch } from "vue";
import { useToastStore } from "../../stores/toast";
import { useAuthStore } from "../../stores/auth";
import { request, jsonBody, type Channel, type PublishResponse } from "../../api";
import TextField from "../base/TextField.vue";
import TextArea from "../base/TextArea.vue";
import SelectField from "../base/SelectField.vue";
import BaseButton from "../base/BaseButton.vue";
import MultiUploadField from "../common/MultiUploadField.vue";

const props = defineProps<{ channels: Channel[] }>();

const emit = defineEmits<{ (e: "submitted"): void }>();

const toast = useToastStore();
const auth = useAuthStore();

// 联系方式默认带出用户已验证的手机号（资料里填了电话就自动填，免手动输入；可自行修改）。
function prefillContact(): void {
  const phone = auth.profile?.phone?.trim();
  if (phone && !contact.value.trim()) {
    contact.value = phone;
  }
}
onMounted(prefillContact);
// profile 可能异步加载（登录后 refreshProfile），就绪后再补一次。
watch(() => auth.profile?.phone, prefillContact);

const category = ref("房产");
const propertyKind = ref("rent");
const channelId = ref("");
const title = ref("");
const body = ref("");
const area = ref("");
const priceAmount = ref("");
const priceUnit = ref("月");
const contact = ref("");
const attrs = ref<Record<string, string>>({});
const imageKeys = ref<string[]>([]);
const busy = ref(false);
const error = ref("");
const success = ref("");

const CATEGORIES = [
  { value: "房产", label: "房产" },
  { value: "市场", label: "市场" },
  { value: "招聘", label: "招聘" },
];

const PROPERTY_KINDS = [
  { value: "rent", label: "租赁" },
  { value: "sale", label: "买卖" },
  { value: "commercial", label: "商业房产" },
];

// 后端 _UNITS / _ATTRS 的前端镜像
const UNITS: Record<string, string[]> = {
  rent: ["月", "周"],
  sale: ["总价"],
  commercial: ["月", "总价"],
  secondhand: [""],
  job: ["小时", "月", "年"],
};

const ATTR_FIELDS: Record<string, { key: string; label: string }[]> = {
  rent: [
    { key: "roomType", label: "房型" },
    { key: "moveIn", label: "入住时间" },
    { key: "bills", label: "Bills 是否包含" },
    { key: "deposit", label: "押金" },
    { key: "minTerm", label: "最短租期" },
  ],
  sale: [{ key: "roomType", label: "房型" }],
  commercial: [{ key: "roomType", label: "物业类型" }],
  secondhand: [
    { key: "condition", label: "成色" },
    { key: "pickup", label: "交易方式" },
  ],
  job: [
    { key: "jobType", label: "工作类型" },
    { key: "hours", label: "工作时间" },
  ],
};

const kind = computed(() => {
  if (category.value === "房产") return propertyKind.value;
  if (category.value === "市场") return "secondhand";
  return "job";
});

const units = computed(() => UNITS[kind.value] ?? []);
const attrFields = computed(() => ATTR_FIELDS[kind.value] ?? []);
const showUnit = computed(() => units.value[0] !== "");

const unitOptions = computed(() =>
  units.value.filter((unit) => unit !== "").map((unit) => ({ value: unit, label: unit })),
);

// 分类信息只能发到官方频道，且分类需与频道一致。
// /channels 已下发 category，前端按当前分类精确过滤（后端仍会二次校验）。
// 兼容尚未重启的旧后端进程（/channels 未下发 category）：退回「官方频道」口径并明确提示。
const hasCategoryData = computed(() =>
  props.channels.some(
    (channel) => typeof channel.category === "string" && channel.category.trim() !== "",
  ),
);
const matchingChannels = computed(() =>
  props.channels.filter(
    (channel) => channel.certified && (!hasCategoryData.value || channel.category === category.value),
  ),
);
const channelOptions = computed(() =>
  matchingChannels.value.map((channel) => ({ value: channel.id, label: channel.name_hans })),
);

function setAttr(key: string, value: string): void {
  attrs.value = { ...attrs.value, [key]: value };
}

function onKindChange(): void {
  // 切换类型后把单位重置为该类型的首个合法值，并清空可能不匹配的频道
  priceUnit.value = showUnit.value ? units.value[0] : "";
  attrs.value = {};
  channelId.value = "";
  error.value = "";
}

async function submit(): Promise<void> {
  error.value = "";
  success.value = "";
  if (!title.value.trim() || !body.value.trim() || !area.value.trim() || !priceAmount.value.trim() || !contact.value.trim()) {
    error.value = "标题、描述、区域、价格和联系方式都是必填项";
    return;
  }
  if (!channelId.value) {
    error.value = "请选择发布到的官方频道";
    return;
  }
  busy.value = true;
  try {
    const result = await request<PublishResponse>(
      "/api/v1/listings",
      jsonBody({
        channel_id: channelId.value,
        title: title.value.trim(),
        body: body.value.trim(),
        category: category.value,
        kind: kind.value,
        area: area.value.trim(),
        price_amount: priceAmount.value.trim(),
        price_unit: priceUnit.value,
        contact: contact.value.trim(),
        attrs: attrs.value,
        keywords: [],
        image_keys: imageKeys.value,
        // 兼容尚未重启的旧后端（只认单图）：同时下发首图。
        image_key: imageKeys.value[0] || null,
      }),
    );
    success.value = result.status === "pending" ? "已提交，审核通过后公开" : "已发布";
    toast.show(success.value);
    title.value = "";
    body.value = "";
    area.value = "";
    priceAmount.value = "";
    contact.value = "";
    attrs.value = {};
    imageKeys.value = [];
    emit("submitted");
  } catch (err) {
    const message = err instanceof Error ? err.message : "发布没有成功";
    error.value = message.includes("手机") ? "发布前需要先验证手机号，请到「我的」完成手机验证。" : message;
    toast.show(error.value);
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <form class="listing-form" @submit.prevent="submit">
    <p class="form-hint">分类信息只发到对应的官方频道，分类需与频道一致；不进「为你推荐」。</p>

    <SelectField id="listing-category" v-model="category" label="信息分类" :options="CATEGORIES" @update:model-value="onKindChange" />
    <SelectField
      v-if="category === '房产'"
      id="listing-kind"
      v-model="propertyKind"
      label="房产类型"
      :options="PROPERTY_KINDS"
      @update:model-value="onKindChange"
    />
    <SelectField
      id="listing-channel"
      v-model="channelId"
      label="发布到"
      :options="channelOptions"
      :placeholder="matchingChannels.length ? '请选择对应的官方频道' : '当前分类暂无可用官方频道'"
      :disabled="matchingChannels.length === 0"
    />
    <p class="form-hint">
      <template v-if="hasCategoryData">这里只列出与「{{ category }}」分类一致的官方频道，避免提交后被后端拒绝。</template>
      <template v-else>当前频道没有可用的分类信息，暂按官方频道展示；提交仍以后端校验为准。</template>
    </p>

    <TextField id="listing-title" v-model="title" label="标题" required />
    <TextArea id="listing-body" v-model="body" label="描述" :rows="4" required />
    <TextField id="listing-area" v-model="area" label="区域" placeholder="例如：London Ealing" required />

    <div class="price-row">
      <TextField id="listing-price" v-model="priceAmount" label="价格" type="number" required />
      <SelectField v-if="showUnit" id="listing-unit" v-model="priceUnit" label="单位" :options="unitOptions" />
    </div>

    <div v-if="attrFields.length > 0" class="attr-grid">
      <TextField
        v-for="field in attrFields"
        :id="`listing-attr-${field.key}`"
        :key="field.key"
        :model-value="attrs[field.key] ?? ''"
        :label="field.label"
        @update:model-value="setAttr(field.key, $event)"
      />
    </div>

    <MultiUploadField
      id="listing-image"
      v-model="imageKeys"
      label="信息图片（可选，最多 4 张）"
      accept="image/jpeg,image/png,image/webp"
      :max-mb="5"
      :max="4"
      hint="jpeg / png / webp，单张最大 5MB；详情中以 16:10 横滑展示，第一张为封面"
    />

    <TextField id="listing-contact" v-model="contact" label="联系方式" hint="已自动带入你验证过的手机号，可修改；只有登录用户主动点按才可见，并留查看记录" required />

    <p v-if="error" class="form-error" role="alert">{{ error }}</p>
    <p v-if="success" class="form-success" role="status">{{ success }}</p>

    <div class="form-actions">
      <BaseButton type="submit" :loading="busy" variant="primary">发布分类信息</BaseButton>
    </div>
    <p class="form-note">发布后 30 天自动过期，可在「我的」续期；过期信息不静默消失，会标记「已过期」并关闭联系方式。</p>
  </form>
</template>

<style scoped>
.listing-form {
  display: grid;
  gap: var(--sp-3);
}
.form-hint,
.form-note {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-12);
  line-height: 1.6;
}
.price-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--sp-3);
}
.attr-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--sp-3);
}
.form-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--fs-13);
}
.form-success {
  margin: 0;
  color: var(--good, var(--accent-ink));
  font-size: var(--fs-13);
}
.form-actions {
  display: flex;
  gap: var(--sp-2);
}
@media (max-width: 480px) {
  .price-row {
    grid-template-columns: 1fr;
  }
}
</style>
