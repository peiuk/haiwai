<script setup lang="ts">
// 外链内联播放同意面板（MASTER §7.3 合规红线）。
// 状态机：placeholder → consent → player → 收起销毁 iframe DOM。
// iframe 地址只能由服务端下发（embed_url），前端不自行拼接。
// 降级三态：fallback（禁嵌入/英区无授权 → 去原站看）、removed（死链）、embeddable（可走同意）。
import { computed, onMounted, ref } from "vue";
import { useAuthStore } from "../../stores/auth";
import { useToastStore } from "../../stores/toast";
import {
  request,
  jsonBody,
  type EmbedConsent,
  type EmbedConsentResult,
} from "../../api";
import BaseButton from "../base/BaseButton.vue";
import BaseTag from "../base/BaseTag.vue";
import SourceBlock from "../common/SourceBlock.vue";
import ReportButton from "../common/ReportButton.vue";

const props = defineProps<{
  contentId: string;
  title: string;
  embedStatus: string;
  sourceUrl: string | null;
  displayName?: string;
  providerNotice?: string;
  /** 嵌在条目 / 帖子卡里：不重复标题、来源和举报（外层卡片已有） */
  bare?: boolean;
}>();

const auth = useAuthStore();
const toast = useToastStore();

type Stage = "placeholder" | "consent" | "player";
const stage = ref<Stage>("placeholder");
const consent = ref<EmbedConsent | null>(null);
const consentScope = ref<"once" | "always" | "withdrawn" | null>(null);
const embedUrl = ref<string | null>(null);
const loading = ref(false);
const busy = ref(false);
const error = ref("");

// 降级态：不能站内播放
const fallback = computed(() => props.embedStatus === "fallback");
const removed = computed(() => props.embedStatus === "removed");
const canPlay = computed(() => props.embedStatus === "embeddable");

const statusBadge = computed(() => {
  if (removed.value) return { text: "链接已失效", variant: "warn" as const };
  if (fallback.value) return { text: "去原站看", variant: "warn" as const };
  if (props.embedStatus === "pending") return { text: "审核中", variant: "warn" as const };
  return { text: "官方外链", variant: "link" as const };
});

async function loadConsent(): Promise<void> {
  if (!auth.isLoggedIn || !canPlay.value) return;
  loading.value = true;
  error.value = "";
  try {
    const body = await request<EmbedConsent>(`/api/v1/embed/${props.contentId}/consent`);
    consent.value = body;
    consentScope.value = body.scope;
    // 已有「总是允许」偏好：服务端直接允许加载，但仍由用户点占位卡才创建 iframe
    if (body.may_load && body.embed_url) {
      embedUrl.value = body.embed_url;
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "同意状态读取失败";
  } finally {
    loading.value = false;
  }
}

function openConsent(): void {
  if (!auth.isLoggedIn) {
    toast.show("先登录后再加载第三方播放器");
    return;
  }
  // 已有 always 偏好：跳过面板直接播放
  if (embedUrl.value) {
    stage.value = "player";
    return;
  }
  stage.value = "consent";
}

async function choose(scope: "once" | "always" | "withdrawn"): Promise<void> {
  busy.value = true;
  error.value = "";
  try {
    const body = await request<EmbedConsentResult>(
      `/api/v1/embed/${props.contentId}/consent`,
      jsonBody({ scope }),
    );
    consentScope.value = body.scope;
    if (body.may_load && body.embed_url) {
      embedUrl.value = body.embed_url;
      stage.value = "player";
    } else {
      // withdrawn 或不加载：销毁 iframe
      embedUrl.value = null;
      stage.value = "placeholder";
      if (scope === "withdrawn") toast.show("已撤回该平台的播放同意");
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "同意提交失败";
  } finally {
    busy.value = false;
  }
}

function collapse(): void {
  // 关键：收起时必须销毁 iframe DOM（v-if 切换），不能 display:none
  stage.value = "placeholder";
  embedUrl.value = null;
}

function withdraw(): void {
  void choose("withdrawn");
}

onMounted(loadConsent);
</script>

<template>
  <article class="embed-card" :class="{ 'embed-card--bare': bare }">
    <header v-if="!bare" class="embed-head">
      <h3 class="embed-title">{{ title }}</h3>
      <BaseTag :variant="statusBadge.variant">{{ statusBadge.text }}</BaseTag>
    </header>

    <!-- 死链：不给播放，也不给跳转 -->
    <div v-if="removed" class="embed-state embed-state--warn" role="note">
      源站链接已失效，仅保留登记记录。
    </div>

    <!-- 禁嵌入 / 英区无授权：降级为跳转卡，禁止破解 -->
    <div v-else-if="fallback" class="embed-state embed-state--warn">
      <p>{{ providerNotice || "该平台不允许站内播放或英区暂无合法入口，请前往原站观看。" }}</p>
      <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener" class="btn btn--outline btn--sm">
        去原站看
      </a>
    </div>

    <!-- 可嵌入：占位 → 同意 → 播放 -->
    <template v-else-if="canPlay">
      <!-- 占位卡：明确告知第三方加载会传输 IP / 设备信息 -->
      <div v-if="stage === 'placeholder'" class="embed-placeholder">
        <p class="embed-notice">
          将加载第三方播放器（{{ displayName || consent?.display_name || "外部平台" }}），并向其传输你的 IP、设备与浏览信息。平台不代理、不缓存影片。
        </p>
        <p v-if="consent?.notice" class="embed-notice-sub">{{ consent.notice }}</p>
        <BaseButton type="button" variant="outline" :disabled="loading" @click="openConsent">
          {{ loading ? "检查同意状态…" : "查看播放选项" }}
        </BaseButton>
        <p v-if="!bare" class="embed-scope-note">
          仅在已订阅频道出现 · 不进「为你推荐」、不置顶、不推送、不进每日精选
        </p>
      </div>

      <!-- 同意面板：三选项 -->
      <div v-else-if="stage === 'consent'" class="embed-consent" role="group" aria-label="第三方播放同意选项">
        <p class="embed-notice">
          {{ consent?.notice || providerNotice || "加载后第三方平台会收到你的 IP、设备与浏览信息，并可能设置 cookie。" }}
        </p>
        <p class="embed-policy">同意政策版本：{{ consent?.policy_version || "—" }}</p>
        <div class="consent-actions">
          <BaseButton type="button" variant="primary" :loading="busy" @click="choose('once')">仅本次加载</BaseButton>
          <BaseButton type="button" variant="outline" :disabled="busy" @click="choose('always')">总是允许此平台</BaseButton>
          <a v-if="sourceUrl" :href="sourceUrl" target="_blank" rel="noopener" class="btn btn--ghost btn--sm">去原站看</a>
        </div>
        <button type="button" class="text-btn" @click="stage = 'placeholder'">取消</button>
      </div>

      <!-- 播放：iframe 地址服务端下发，收起用 v-if 销毁 DOM -->
      <div v-else class="embed-player">
        <p class="sr-only" aria-live="polite">第三方播放器已加载</p>
        <iframe
          v-if="embedUrl"
          :src="embedUrl"
          :title="`第三方播放器：${title}`"
          class="embed-frame"
          allow="encrypted-media; picture-in-picture"
          allowfullscreen
          referrerpolicy="strict-origin-when-cross-origin"
        ></iframe>
        <div class="player-actions">
          <BaseButton type="button" variant="outline" size="sm" @click="collapse">收起并停止播放</BaseButton>
          <button
            v-if="consentScope === 'always'"
            type="button"
            class="text-btn"
            :disabled="busy"
            @click="withdraw"
          >
            撤回「总是允许」
          </button>
        </div>
      </div>
    </template>

    <p v-if="error" class="embed-error" role="alert">{{ error }}</p>

    <!-- 来源与许可 + 举报常驻（§7.1 / §7.4） -->
    <footer v-if="!bare" class="embed-foot">
      <SourceBlock
        :source-name="displayName"
        licence-ref="官方外链"
        :canonical-url="sourceUrl"
        :label="`${title} 的来源与许可`"
      />
      <ReportButton kind="content" :id="contentId" compact />
    </footer>
  </article>
</template>

<style scoped>
.embed-card {
  display: grid;
  gap: var(--sp-3);
  padding: var(--sp-3);
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
}
.embed-card--bare {
  margin-top: var(--sp-2);
  padding: 0;
  border: 0;
  background: transparent;
}
.embed-head {
  display: flex;
  gap: var(--sp-2);
  align-items: flex-start;
  justify-content: space-between;
}
.embed-title {
  margin: 0;
  font-size: var(--fs-15);
  font-weight: 600;
  overflow-wrap: anywhere;
}
.embed-state {
  display: grid;
  gap: var(--sp-2);
  padding: var(--sp-3);
  border-radius: var(--r-md);
  font-size: var(--fs-13);
}
.embed-state--warn {
  background: var(--warn-soft, var(--surface2));
  color: var(--text);
}
.embed-state p {
  margin: 0;
}
.embed-placeholder,
.embed-consent,
.embed-player {
  display: grid;
  gap: var(--sp-3);
}
.embed-notice {
  margin: 0;
  font-size: var(--fs-13);
  line-height: 1.6;
}
.embed-notice-sub,
.embed-policy,
.embed-scope-note {
  margin: 0;
  font-size: var(--fs-12);
  color: var(--muted);
}
.consent-actions,
.player-actions {
  display: flex;
  gap: var(--sp-2);
  align-items: center;
  flex-wrap: wrap;
}
.embed-frame {
  width: 100%;
  aspect-ratio: 16 / 9;
  border: 0;
  border-radius: var(--r-md);
}
.text-btn {
  min-height: 44px;
  padding: 0 var(--sp-2);
  border: 0;
  background: transparent;
  color: var(--accent-ink);
  font-size: var(--fs-13);
  cursor: pointer;
  text-decoration: underline;
}
.text-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.embed-error {
  margin: 0;
  color: var(--danger);
  font-size: var(--fs-12);
}
.embed-foot {
  display: grid;
  gap: var(--sp-2);
  padding-top: var(--sp-1);
}
</style>
