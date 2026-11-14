<script setup lang="ts">
// 分类信息卡片（MASTER §22.7）：价格 / 认证 / 剩 N 天 / 举报常驻 / 过期不静默消失。
// 详情展开：关键字段、发布者、防骗提示、联系方式需登录且主动点按（写 contact_views）。
import { computed, ref } from "vue";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import { request, type ListingCardItem } from "../../api";
import BaseTag from "../base/BaseTag.vue";
import BaseButton from "../base/BaseButton.vue";
import ReportButton from "../common/ReportButton.vue";
import ImageStrip from "../common/ImageStrip.vue";
import SourceBlock from "../common/SourceBlock.vue";

const props = defineProps<{ item: ListingCardItem }>();

const auth = useAuthStore();
const toast = useToastStore();

type ListingDetail = ListingCardItem & {
  status?: string;
  contact_views_limit?: number;
  contact_views_remaining?: number | null;
  image_keys?: string[];
};

const expanded = ref(false);
const detail = ref<ListingDetail | null>(null);
const loadingDetail = ref(false);
const contact = ref("");
const contactBusy = ref(false);

const CURRENCY_SYMBOL: Record<string, string> = { GBP: "£", JPY: "¥", CAD: "C$" };
const currencySymbol = computed(() => CURRENCY_SYMBOL[props.item.currency] ?? "¤");
const priceLabel = computed(() => `${currencySymbol.value}${props.item.price_amount}${props.item.price_unit ? `/${props.item.price_unit}` : ""}`);

const daysLeft = computed(() => {
  if (!props.item.expires_at) return null;
  const diff = new Date(props.item.expires_at).getTime() - Date.now();
  return Math.ceil(diff / 86_400_000);
});

const expiryBadge = computed(() => {
  if (props.item.expired || (daysLeft.value !== null && daysLeft.value <= 0)) {
    return { text: "已过期", variant: "warn" as const, urgent: true };
  }
  if (daysLeft.value !== null && daysLeft.value <= 3) {
    return { text: `剩 ${daysLeft.value} 天过期`, variant: "warn" as const, urgent: true };
  }
  if (daysLeft.value !== null) {
    return { text: `剩 ${daysLeft.value} 天`, variant: "default" as const, urgent: false };
  }
  return null;
});

const firstAttr = computed(() => {
  const entries = Object.entries(props.item.attrs ?? {});
  return entries.length > 0 ? entries[0][1] : "";
});

async function toggleDetail(): Promise<void> {
  if (expanded.value) {
    expanded.value = false;
    return;
  }
  expanded.value = true;
  if (detail.value) return;
  loadingDetail.value = true;
  try {
    detail.value = await request<ListingDetail>(`/api/v1/listings/${props.item.content_id}`);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "详情加载失败");
  } finally {
    loadingDetail.value = false;
  }
}

async function viewContact(): Promise<void> {
  if (!auth.isLoggedIn) {
    toast.show("先登录后再查看联系方式");
    return;
  }
  contactBusy.value = true;
  try {
    const body = await request<{ contact: string; contact_views_remaining: number }>(
      `/api/v1/listings/${props.item.content_id}/contact`,
      { method: "POST" },
    );
    contact.value = body.contact;
    toast.show(`今日还可查询 ${body.contact_views_remaining} 次`);
  } catch (err) {
    toast.show(err instanceof Error ? err.message : "查看失败");
  } finally {
    contactBusy.value = false;
  }
}

</script>

<template>
  <article class="listing-card" :class="{ expired: expiryBadge?.urgent }">
    <div class="card-head">
      <div class="card-main">
        <h3 class="card-title" data-ugc>{{ item.title }}</h3>
        <p class="card-price">{{ priceLabel }}</p>
        <p class="card-meta">
          {{ item.area }}<template v-if="firstAttr"> · {{ firstAttr }}</template> · {{ item.channel_name }}
        </p>
      </div>
      <ReportButton kind="content" :id="item.content_id" compact :label="`举报 ${item.title}`" />
    </div>

    <div class="badge-row">
      <BaseTag :variant="item.certified ? 'good' : 'default'">
        {{ item.certified ? "已认证" : "未认证" }}
      </BaseTag>
      <BaseTag v-if="expiryBadge" :variant="expiryBadge.variant">{{ expiryBadge.text }}</BaseTag>
      <BaseTag v-if="item.closed_reason" variant="warn">已结案</BaseTag>
    </div>

    <div class="card-actions">
      <BaseButton type="button" variant="outline" size="sm" @click="toggleDetail">
        {{ expanded ? "收起详情" : "查看详情" }}
      </BaseButton>
    </div>

    <!-- 详情展开 -->
    <div v-if="expanded" class="card-detail">
      <p v-if="loadingDetail" class="detail-loading">加载中…</p>

      <!-- 国家隔离占位 -->
      <template v-else-if="detail?.placeholder">
        <p class="detail-placeholder"><span data-ugc>{{ detail.title }}</span>，不显示字段与联系方式。</p>
      </template>

      <template v-else-if="detail">
        <!-- §22.7 详情：返回后第一屏是图片横滑（16:10，最多 4 张） -->
        <ImageStrip :keys="detail.image_keys ?? []" :alt="`${detail.title} 的图片`" />

        <SourceBlock
          :source-name="detail.author_name || detail.source_name"
          :licence-ref="detail.licence_ref"
          :label="`${detail.title} 的来源与许可`"
        />

        <p v-if="detail.summary" class="detail-desc" data-ugc>{{ detail.summary }}</p>

        <dl v-if="Object.keys(detail.attrs ?? {}).length > 0" class="detail-attrs">
          <div v-for="(value, key) in detail.attrs" :key="key" class="attr-pair">
            <dt>{{ key }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>

        <p class="detail-author">
          发布者：{{ detail.author_name || detail.source_name || "—" }}
          <template v-if="detail.author_handle"> · @{{ detail.author_handle }}</template>
        </p>

        <!-- 防骗提示 -->
        <div class="fraud-note" role="note">
          请勿在交易前转账或提供证件、银行账户信息；当面核验物品或合同，谨防诈骗。
        </div>

        <!-- 联系方式：默认打码示例，登录用户主动点按才显示 -->
        <div class="contact-box">
          <p v-if="contact" class="contact-value">{{ contact }}</p>
          <p v-else class="contact-masked">联系方式已隐藏 · **** **** ****</p>
          <BaseButton
            v-if="!contact"
            type="button"
            variant="ghost"
            size="sm"
            :loading="contactBusy"
            :disabled="expiryBadge?.urgent || !!detail.closed_reason"
            @click="viewContact"
          >
            {{ expiryBadge?.urgent ? "已过期，联系方式已关闭" : detail.closed_reason ? "已结案，联系方式已关闭" : "查看联系方式" }}
          </BaseButton>
        </div>

        <p class="detail-foot">不进「为你推荐」· 30 天自动过期 · 每日最多查询 5 次联系方式</p>
      </template>
    </div>
  </article>
</template>

<style scoped>
.listing-card {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
}
.listing-card.expired {
  color: var(--muted);
}
.card-head {
  display: flex;
  gap: var(--sp-3);
  align-items: flex-start;
  justify-content: space-between;
}
.card-main {
  min-width: 0;
}
.card-title {
  margin: 0 0 var(--sp-1);
  font-size: var(--fs-15);
  font-weight: 600;
  overflow-wrap: anywhere;
}
.card-price {
  margin: 0 0 var(--sp-1);
  font-size: var(--fs-15);
  font-weight: 700;
  color: var(--accent-ink);
}
.card-meta {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.report-btn {
  min-height: 44px;
  min-width: 44px;
  padding: 0 var(--sp-2);
  border: 1px solid var(--line);
  border-radius: var(--r-pill);
  background: transparent;
  color: var(--text);
  font-size: var(--fs-12);
  white-space: nowrap;
  cursor: pointer;
}
.report-btn:disabled {
  opacity: 0.6;
  cursor: default;
}
.badge-row {
  display: flex;
  gap: var(--sp-2);
  flex-wrap: wrap;
}
.card-actions {
  display: flex;
  gap: var(--sp-2);
}
.card-detail {
  display: grid;
  gap: var(--sp-3);
  padding-top: var(--sp-3);
  border-top: 1px solid var(--border);
}
.detail-loading,
.detail-placeholder,
.detail-desc,
.detail-author,
.detail-foot,
.contact-masked,
.contact-value {
  margin: 0;
  font-size: var(--fs-13);
}
.detail-placeholder,
.detail-foot,
.detail-author,
.contact-masked {
  color: var(--muted);
}
.detail-desc {
  line-height: 1.6;
}
.detail-attrs {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: var(--sp-2);
  margin: 0;
}
.attr-pair {
  display: grid;
  gap: 2px;
}
.attr-pair dt {
  font-size: var(--fs-12);
  color: var(--muted);
}
.attr-pair dd {
  margin: 0;
  font-size: var(--fs-13);
}
.fraud-note {
  padding: var(--sp-3);
  border: 1px solid var(--line);
  border-radius: var(--r-md);
  background: var(--surface2);
  font-size: var(--fs-12);
  line-height: 1.6;
}
.contact-box {
  display: grid;
  gap: var(--sp-2);
  justify-items: start;
}
.contact-value {
  font-weight: 600;
}
</style>
