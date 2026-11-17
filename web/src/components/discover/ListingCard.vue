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
import BaseIcon from "../base/BaseIcon.vue";
import { fmtRelativeTime } from "../../utils/time";
import { KIND_LABEL, attrLabel } from "../../utils/listing";

// time：这条信息进入内容流的时间（发现页条目的 added_at）
// isJoined：传了才显示「加入 / 已加入」（发现页传，和 PostCard 的加入按钮一样）
const props = defineProps<{ item: ListingCardItem; time?: string; isJoined?: boolean }>();
const emit = defineEmits<{ (e: "join"): void }>();

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
// 「面议」这类非数字价格不带货币符号
const priceLabel = computed(() => {
  const { price_amount: amount, price_unit: unit } = props.item;
  if (!Number.isFinite(Number(amount))) return amount;
  return `${currencySymbol.value}${amount}${unit ? `/${unit}` : ""}`;
});

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

// 卡片上最多带两个字段，带上中文名，避免只露一个光秃秃的值（如「3」）
const attrChips = computed(() =>
  Object.entries(props.item.attrs ?? {})
    .slice(0, 2)
    .map(([key, value]) => `${attrLabel(props.item.kind, key)} ${value}`),
);
const cover = computed(() => props.item.image_keys?.[0] ?? "");
const imageCount = computed(() => props.item.image_keys?.length ?? 0);

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
    <!-- 整块点哪都展开（鼠标）；键盘用标题按钮。频道链接和加入按钮不能套在按钮里，所以外层是 div -->
    <div class="card-hit" @click="toggleDetail">
      <span class="card-thumb">
        <img v-if="cover" :src="`/api/v1/uploads/${cover}`" alt="" loading="lazy" />
        <BaseIcon v-else name="i-image" :size="24" />
        <span v-if="imageCount > 1" class="thumb-count">{{ imageCount }} 图</span>
      </span>
      <span class="card-main">
        <span class="card-kicker">
          {{ KIND_LABEL[item.kind] ?? item.category }}
          <template v-if="time"> · {{ fmtRelativeTime(time) }}</template>
        </span>
        <button
          type="button"
          class="card-title-btn"
          :aria-expanded="expanded"
          :aria-label="`${expanded ? '收起' : '查看'} ${item.title} 的详情`"
          @click.stop="toggleDetail"
        >
          <span class="card-title" data-ugc>{{ item.title }}</span>
        </button>
        <span class="card-source" @click.stop>
          <span class="card-price">{{ priceLabel }}</span>
          <span class="card-from">来自 <RouterLink class="detail-link" :to="{ name: 'channel', params: { id: item.channel_id } }">{{ item.channel_name }}</RouterLink></span>
          <button v-if="isJoined === false" type="button" class="card-join" :aria-label="`加入频道 ${item.channel_name}`" @click="emit('join')">
            <BaseIcon name="i-plus" :size="13" /> 加入
          </button>
          <span v-else-if="isJoined" class="card-joined"><BaseIcon name="i-check" :size="13" /> 已加入</span>
        </span>
        <span class="card-meta">
          <span class="meta-area" data-ugc>{{ item.area }}</span>
          <span v-for="chip in attrChips" :key="chip" class="meta-attr" data-ugc>{{ chip }}</span>
        </span>
      </span>
    </div>

    <div class="card-foot">
      <BaseTag :variant="item.certified ? 'good' : 'default'">
        {{ item.certified ? "已认证" : "未认证" }}
      </BaseTag>
      <BaseTag v-if="expiryBadge" :variant="expiryBadge.variant">{{ expiryBadge.text }}</BaseTag>
      <BaseTag v-if="item.closed_reason" variant="warn">已结案</BaseTag>
      <button type="button" class="detail-toggle" :aria-expanded="expanded" @click="toggleDetail">
        {{ expanded ? "收起" : "详情与联系方式" }}
        <BaseIcon name="i-chev" :size="14" :rotate="expanded ? 180 : 0" />
      </button>
      <ReportButton kind="content" :id="item.content_id" compact :label="`举报 ${item.title}`" />
    </div>

    <!-- 详情展开 -->
    <div v-if="expanded" class="card-detail">
      <p v-if="loadingDetail" class="detail-loading">加载中…</p>

      <!-- 国家隔离占位 -->
      <template v-else-if="detail?.placeholder">
        <p class="detail-placeholder"><span data-ugc>{{ detail.title }}</span>，不显示字段与联系方式。</p>
      </template>

      <template v-else-if="detail">
        <!-- §22.7 详情：返回后第一屏是图片横滑（16:10，最多 6 张） -->
        <ImageStrip :keys="detail.image_keys ?? []" :alt="`${detail.title} 的图片`" />

        <SourceBlock
          :source-name="detail.author_name || detail.source_name"
          :licence-ref="detail.licence_ref"
          :label="`${detail.title} 的来源与许可`"
        />

        <p v-if="detail.summary" class="detail-desc" data-ugc>{{ detail.summary }}</p>

        <dl v-if="Object.keys(detail.attrs ?? {}).length > 0" class="detail-attrs">
          <div v-for="(value, key) in detail.attrs" :key="key" class="attr-pair">
            <dt>{{ attrLabel(detail.kind, String(key)) }}</dt>
            <dd>{{ value }}</dd>
          </div>
        </dl>

        <p class="detail-author">
          发布者：<RouterLink v-if="detail.author_id" class="detail-link" :to="{ name: 'user', params: { id: detail.author_id } }" data-ugc>
            {{ detail.author_name || detail.author_handle }}<template v-if="detail.author_handle"> · @{{ detail.author_handle }}</template>
          </RouterLink>
          <span v-else data-ugc>{{ detail.source_name || "—" }}</span>
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
  gap: var(--sp-2);
  padding: 12px 16px;
  border-bottom: 1px solid var(--border);
  transition: background var(--dur-fast) var(--ease-out);
}
.listing-card:hover {
  background: var(--hover);
}
.listing-card.expired {
  color: var(--muted);
}
.card-hit {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  width: 100%;
  cursor: pointer;
}
.card-title-btn {
  padding: 0;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}
.card-title-btn:focus-visible,
.detail-toggle:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--r-md);
}
.card-thumb {
  position: relative;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  width: 96px;
  height: 96px;
  overflow: hidden;
  border-radius: var(--r-md);
  background: var(--surface2);
  color: var(--muted);
}
.card-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.listing-card.expired .card-thumb img {
  filter: grayscale(1);
  opacity: 0.6;
}
.thumb-count {
  position: absolute;
  right: 4px;
  bottom: 4px;
  padding: 0 6px;
  border-radius: var(--r-pill);
  background: rgb(0 0 0 / 0.6);
  color: #fff;
  font-size: var(--fs-12);
  line-height: 18px;
}
.card-main {
  min-width: 0;
  flex: 1;
  display: grid;
  gap: 2px;
}
.card-kicker,
.card-meta {
  font-size: var(--fs-12);
  color: var(--muted);
}
.card-title {
  font-size: var(--fs-15);
  font-weight: 600;
  line-height: 1.4;
  overflow-wrap: anywhere;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.card-price {
  font-size: var(--fs-16);
  font-weight: 700;
  color: var(--accent-ink);
}
.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 4px;
}
.card-source {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 4px 8px;
  cursor: default;
}
.card-from {
  font-size: var(--fs-12);
  color: var(--muted);
}
.card-join {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  min-height: 30px;
  margin-left: auto;
  padding: 0 var(--sp-3);
  border: 1px solid var(--text);
  border-radius: var(--r-pill);
  background: var(--text);
  color: var(--bg);
  font-size: var(--fs-12);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.card-join:hover {
  opacity: 0.85;
}
.card-joined {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-left: auto;
  font-size: var(--fs-12);
  color: var(--muted);
}
.meta-attr::before {
  content: "· ";
}
.card-foot {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--sp-2);
  padding-left: 108px;
}
.detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  min-height: 44px;
  margin-left: auto;
  padding: 0 var(--sp-1);
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-13);
  font-weight: 600;
  cursor: pointer;
}
@media (max-width: 420px) {
  .card-thumb {
    width: 80px;
    height: 80px;
  }
  .card-foot {
    padding-left: 0;
  }
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
.detail-link {
  color: var(--accent-ink);
  font-weight: 600;
  text-decoration: none;
}
.detail-link:hover {
  text-decoration: underline;
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
