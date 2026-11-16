<script setup lang="ts">
// 法律条款独立页（/legal/:section）：服务条款 / 隐私政策 / Cookie 政策。
// 三节集中承载网站级法律文本，注册表单与「来源与合规」均链接到本页对应章节。
// 文案遵循 UK GDPR / PECR 合规红线，法域以用户确认区域 + 账号国综合判定。
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const contact = (import.meta.env.VITE_SUPPORT_CONTACT ?? "").trim();
const router = useRouter();

const SECTIONS = [
  { key: "tos", label: "服务条款", anchor: "tos" },
  { key: "privacy", label: "隐私政策", anchor: "privacy" },
  { key: "cookie", label: "Cookie 政策", anchor: "cookie" },
] as const;

type SectionKey = (typeof SECTIONS)[number]["key"];

const active = ref<SectionKey>("tos");

function normalize(key: string): SectionKey {
  return (SECTIONS.some((s) => s.key === key) ? key : "tos") as SectionKey;
}

const currentSection = computed(() => normalize(typeof route.params.section === "string" ? route.params.section : "tos"));

function selectSection(key: SectionKey): void {
  active.value = key;
  router.replace({ name: "legal", params: { section: key } });
}

watch(currentSection, (key) => {
  active.value = key;
  document.getElementById(key)?.scrollIntoView({ behavior: "smooth", block: "start" });
});

onMounted(() => {
  active.value = currentSection.value;
});
</script>

<template>
  <section class="legal-view">
    <h1 class="page-title">条款与政策</h1>

    <nav class="legal-nav" aria-label="条款章节">
      <button
        v-for="s in SECTIONS"
        :key="s.key"
        type="button"
        class="legal-nav-btn"
        :class="{ active: active === s.key }"
        :aria-current="active === s.key ? 'page' : undefined"
        @click="selectSection(s.key)"
      >
        {{ s.label }}
      </button>
    </nav>

    <article id="tos" class="legal-section">
      <h2>服务条款</h2>
      <p class="legal-meta">生效版本：v1 · 最近更新：2026 年 11 月</p>

      <h3>1. 接受条款</h3>
      <p>访问或使用本社区（「平台」）即表示你已阅读、理解并同意遵守本服务条款。若你代表机构使用，你声明已获授权使该机构受本条款约束。</p>

      <h3>2. 账户与资格</h3>
      <p>注册账户需年满 18 周岁，并提供真实、准确的邮箱地址。你对自己的账户凭据安全负责；发现未经授权的使用须立即通知我们。发布内容前需完成手机号验证。</p>

      <h3>3. 用户内容</h3>
      <p>你保留所发布内容的权利，但授予平台为运营、展示与分发目的所必需的许可。你保证所发布内容为原创或已取得合法授权，不含未授权音乐、影视片段，且已取得出镜人物同意。禁止发布违法、侵权、仇恨、骚扰或欺诈性内容。</p>

      <h3>4. 内容审核与处置</h3>
      <p>平台对新用户发布内容实施审核机制，并有权对违规内容进行下架、限制展示或移除。你可通过卡片「举报」入口反馈不当内容，平台在 24 小时内响应。</p>

      <h3>5. 知识产权</h3>
      <p>平台界面、标识与原创设计归平台所有。第三方内容的版权归属其权利人，转载与引用须保留原出处署名与许可标记（详见来源与许可规范）。</p>

      <h3>6. 免责与责任限制</h3>
      <p>用户原创内容仅代表作者本人观点，不代表平台立场。在适用法律允许的范围内，平台不对服务的中断、数据丢失或第三方内容承担责任。</p>

      <h3>7. 条款变更</h3>
      <p>平台可能不时更新本条款。重大变更将通过在站内显著位置公告或邮件通知。继续使用平台即表示你接受更新后的条款。</p>

      <h3>8. 联系与管辖</h3>
      <p>本条款受英国法律管辖。如有疑问或争议，请通过平台公示的联系渠道与我们联系。</p>
      <p v-if="contact">联系方式：<span data-no-hant>{{ contact }}</span></p>
    </article>

    <article id="privacy" class="legal-section">
      <h2>隐私政策</h2>
      <p class="legal-meta">生效版本：v1 · 最近更新：2026 年 11 月 · 依据 UK GDPR</p>

      <h3>1. 我们收集的信息</h3>
      <p>注册时收集你的邮箱、显示名；发布内容时收集你主动提交的正文、图片与互动记录；为满足发布风控，你可能自愿验证手机号。我们遵循数据最小化原则，仅收集提供与改进服务所必需的信息。</p>

      <h3>2. 位置与法域信息</h3>
      <p>为提供本地化与合规服务，我们会根据你确认的区域、账号注册地区等信息判定法域，用于展示对应的合规说明、通知渠道与版权规则。我们<strong>不申请</strong>设备精确定位权限，不存储 IP 原文与经纬度。</p>

      <h3>3. 信息的使用</h3>
      <p>你的信息用于账号运营、内容展示、个性化推荐（仅基于频道级聚合数据，不采集逐条行为画像）、安全与合规审查。推荐理由可追溯到频道级数据，你可随时查看并选择「减少此类内容」。</p>

      <h3>4. 信息的共享</h3>
      <p>我们不会出售你的个人信息。仅在以下情形共享：法律要求、为保护平台与用户安全、或经你明确同意（如第三方播放器内联加载）。第三方内联播放会传输你的 IP、设备与浏览信息，并可能设置 cookie，我们会在加载前取得你的单独同意。</p>

      <h3>5. 你的权利</h3>
      <p>依据 UK GDPR，你享有访问、更正、删除、限制处理、数据可携与反对处理等权利。你可在「我的 → 隐私与数据」中查看同意记录、撤回同意或删除账号；需要账号数据副本时，请通过平台公示的联系渠道提出，我们会在一个月内提供。</p>

      <h3>6. 数据保留与安全</h3>
      <p>我们在实现目的所需的期限内保留数据，并采取合理的技术与组织措施保护数据安全。删除账号后将删除或匿名化你的资料、帖子与房间数据（法定义务要求保留的除外）。</p>

      <h3>7. 联系我们</h3>
      <p>如对本政策或数据保护有任何疑问，请通过平台公示的联系渠道联系我们的数据保护负责人。</p>
      <p v-if="contact">联系方式：<span data-no-hant>{{ contact }}</span></p>
    </article>

    <article id="cookie" class="legal-section">
      <h2>Cookie 政策</h2>
      <p class="legal-meta">生效版本：v1 · 最近更新：2026 年 11 月 · 依据 PECR</p>

      <h3>1. 什么是 Cookie</h3>
      <p>Cookie 是网站在你的设备上存储的小型文本文件，用于识别会话、记住偏好与保障功能正常。</p>

      <h3>2. 我们使用的 Cookie</h3>
      <ul>
        <li><strong>必要 Cookie</strong>：用于登录会话、安全防护与基本功能，无法关闭。此类 Cookie 不采集可用于识别你的额外信息。</li>
        <li><strong>偏好 Cookie</strong>：用于记住简繁语言、深浅色主题等偏好设置。</li>
        <li><strong>第三方 Cookie</strong>：当你主动选择加载第三方内联播放器（如视频平台）时，第三方可能设置 Cookie 并收到你的 IP、设备与浏览信息。这仅在取得你的事前同意后发生，且同意可随时撤回。</li>
      </ul>

      <h3>3. 同意与撤回</h3>
      <p>对于非必要的第三方 Cookie，我们在加载前征得你的明确同意。你可随时在对应播放器的同意面板撤回授权，或通过浏览器设置清除 Cookie。</p>

      <h3>4. 管理 Cookie</h3>
      <p>你可以在浏览器设置中禁用或删除 Cookie，但这可能影响登录状态与部分功能的正常使用。</p>
    </article>
  </section>
</template>

<style scoped>
.legal-view {
  max-width: 760px;
  margin: 0 auto;
  padding-bottom: var(--sp-8);
}
.legal-nav {
  display: flex;
  flex-wrap: wrap;
  gap: var(--sp-2);
  margin: var(--sp-4) 0;
  padding-bottom: var(--sp-3);
  border-bottom: 1px solid var(--border);
}
.legal-nav-btn {
  min-height: var(--tap);
  padding: 0 var(--sp-3);
  border: 1px solid var(--border);
  border-radius: var(--r-pill);
  background: var(--surface);
  color: var(--muted);
  font-size: var(--fs-14);
  font-weight: var(--fw-bold);
  cursor: pointer;
}
.legal-nav-btn.active {
  color: var(--on-accent);
  background: var(--accent-strong);
  border-color: var(--accent-strong);
}
.legal-section {
  margin-top: var(--sp-6);
  padding: var(--sp-5);
  border: 1px solid var(--border);
  border-radius: var(--r-lg);
  background: var(--surface);
}
.legal-section h2 {
  margin: 0 0 var(--sp-2);
  font-size: var(--fs-18);
  font-weight: var(--fw-bold);
}
.legal-section h3 {
  margin: var(--sp-5) 0 var(--sp-2);
  font-size: var(--fs-15);
  font-weight: var(--fw-bold);
}
.legal-section p,
.legal-section li {
  margin: 0;
  color: var(--muted);
  font-size: var(--fs-14);
  line-height: var(--lh-body);
}
.legal-section ul {
  margin: var(--sp-2) 0;
  padding-left: var(--sp-5);
  display: grid;
  gap: var(--sp-2);
}
.legal-meta {
  font-size: var(--fs-12) !important;
  color: var(--muted);
}
</style>
