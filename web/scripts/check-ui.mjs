#!/usr/bin/env node
/**
 * 正式前端的 §12.2 等价门禁（改动 web/src 后交付前必须跑）。
 *
 * 原型侧八道 JS 门禁（check-ui / check-global / check-media / check-location /
 * check-rooms / check-discover / check-flow / check-h5）针对的是演示状态机与内联 HTML，
 * 正式前端是 Vue 3 + 真实 API，因此这里以「静态源码断言 + vue-tsc/vite build +
 * pytest 契约探针」作为等价验收：每条都对准原型门禁守的那条红线。
 *
 * 用法：npm run check:ui   （非 0 即禁止发布）
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const repoRoot = path.resolve(webRoot, "..");

let fails = 0;
function note(label, ok, detail = "") {
  console.log(`${ok ? "PASS" : "FAIL"}  ${label}${detail ? ` — ${detail}` : ""}`);
  if (!ok) fails += 1;
}
function read(rel) {
  return fs.readFileSync(path.join(repoRoot, rel), "utf8");
}
function listVue(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...listVue(full));
    else if (entry.name.endsWith(".vue")) out.push({ file: path.relative(repoRoot, full).replace(/\\/g, "/"), text: fs.readFileSync(full, "utf8") });
  }
  return out;
}

const vueFiles = listVue(path.join(webRoot, "src"));
const allVue = vueFiles.map((f) => f.text).join("\n");
const src = (tail) => read(`web/src/${tail}`);

// ① 应用骨架（check-ui：真实渲染入口存在，而非只做语法检查）
const app = src("App.vue");
const main = src("main.ts");
note(
  "① 骨架：App 挂 sprite + RouterView，main 挂 Pinia/Router/主题/界面语言",
  /<IconSprite\s*\/>/.test(app) &&
    /<RouterView\s*\/>/.test(app) &&
    /createPinia\(\)/.test(main) &&
    /app\.use\(router\)/.test(main) &&
    /useThemeStore\(\)/.test(main) &&
    /startUiLang\(\)/.test(main),
);
note(
  "① 骨架：全部 SFC 均有 template，且 <script> 标签成对",
  vueFiles.length >= 50 &&
    vueFiles.every((f) => f.text.includes("<template") && f.text.includes("</template>")) &&
    vueFiles.every((f) => (f.text.match(/<script\b/g) ?? []).length === (f.text.match(/<\/script>/g) ?? []).length),
  `${vueFiles.length} 个 SFC`,
);

// 模板里用到的组件必须在 <script> 里导入：vue-tsc 与 vite build 都发现不了漏导入，
// 运行时只会在控制台报 "Failed to resolve component"，对应组件静默不渲染。
const BUILTIN_TAGS = new Set(["RouterLink", "RouterView", "Transition", "TransitionGroup", "Teleport", "KeepAlive", "Suspense", "Component"]);
const missingImports = [];
for (const f of vueFiles) {
  const tpl = f.text.split("<template>").slice(1).join("<template>");
  for (const tag of new Set([...tpl.matchAll(/<([A-Z][A-Za-z0-9]+)/g)].map((m) => m[1]))) {
    if (BUILTIN_TAGS.has(tag)) continue;
    if (!new RegExp(`import\\s+${tag}\\b|import\\s*\\{[^}]*\\b${tag}\\b`).test(f.text)) missingImports.push(`${f.file}:${tag}`);
  }
}
note("① 骨架：模板用到的组件均已导入", missingImports.length === 0, missingImports.join(", ") || `${vueFiles.length} 个 SFC`);

// ② SVG sprite（check-ui：SVG 引用不悬空）
const sprite = src("components/base/IconSprite.vue");
const symbols = new Set([...sprite.matchAll(/<symbol id="(i-[a-z-]+)"/g)].map((m) => m[1]));
const refs = new Set();
for (const m of allVue.matchAll(/(?:name="(i-[a-z-]+)"|icon: "(i-[a-z-]+)"|href="#(i-[a-z-]+)")/g)) {
  refs.add(m[1] || m[2] || m[3]);
}
const dangling = [...refs].filter((name) => !symbols.has(name));
note("② SVG：图标引用全部命中 sprite", refs.size > 0 && dangling.length === 0, `${symbols.size} symbols / ${refs.size} refs ${dangling.join(",")}`);
const visibleText = allVue.replace(/<!--[\s\S]*?-->/g, "").replace(/^\s*\/\/.*$/gm, "");
note("② SVG：界面无残留 Unicode 装饰图标", !/[⚑♡♥☾☀✓✔▶‹›↑↓]/.test(visibleText));

// ③ 无障碍与外链（check-ui / check-location：label 关联、44px、noopener）
const blankLinks = [...allVue.matchAll(/<a\b[^>]*target="_blank"[^>]*>/g)].map((m) => m[0]);
const unsafeLinks = blankLinks.filter((tag) => !/rel="[^"]*noopener/.test(tag));
note("③ 无障碍：所有 target=_blank 带 rel=noopener", unsafeLinks.length === 0, `${blankLinks.length} 个外链`);
const controls = [...allVue.matchAll(/<(?:input|select|textarea)\b([^>]*)>/g)].map((m) => m[1]);
const unlabeled = controls.filter((attrs) => !/\bid=|:id=|aria-label|aria-labelledby/.test(attrs));
note("③ 无障碍：表单控件均有 id / aria-label", unlabeled.length === 0, `${controls.length} 个控件`);
const tokens = read("design-system/tokens.css");
note(
  "③ 无障碍：44px 触控、tablist / aria-live 语义齐备",
  /--tap:\s*44px/.test(tokens) && /role="tablist"/.test(allVue) && /aria-live/.test(allVue) && /aria-pressed/.test(allVue),
);

// ④ 媒体与外链同意（check-media / §7.3）
const embed = src("components/room/EmbedConsentCard.vue");
const iframe = embed.match(/<iframe[\s\S]*?<\/iframe>/)?.[0] ?? "";
note(
  "④ 媒体：iframe 默认不加载、v-if 销毁、src 只取服务端 embed_url",
  /v-if="embedUrl"/.test(iframe) &&
    /:src="embedUrl"/.test(iframe) &&
    !/:src="[^"]*canonical/.test(iframe) &&
    /stage = 'placeholder'/.test(embed) &&
    /withdrawn/.test(embed),
);

// ⑤ 分类信息（check-h5：联系方式、多图、限额）
const listingCard = src("components/discover/ListingCard.vue");
const listingForm = src("components/publish/ListingForm.vue");
const imageStrip = src("components/common/ImageStrip.vue");
const listingsPy = read("app/api/v1/listings.py");
const feedPy = read("app/feed.py");
// 张数以后端 MAX_LISTING_IMAGES 为准，前端上传框和图片条须用同一个数。
const maxImages = feedPy.match(/MAX_LISTING_IMAGES\s*=\s*(\d+)/)?.[1];
note(
  `⑤ 分类信息：多图 ≤${maxImages ?? "?"} 前后端一致、联系方式需登录主动点按、日限额 5`,
  maxImages !== undefined &&
    listingForm.includes(`:max="${maxImages}"`) &&
    /image_keys/.test(listingForm) &&
    imageStrip.includes(`slice(0, ${maxImages})`) &&
    /CONTACT_DAILY_LIMIT\s*=\s*5/.test(listingsPy) &&
    /auth\.isLoggedIn/.test(listingCard) &&
    /\/contact/.test(listingCard) &&
    // 种子/旧后端的 category 为空串时须退回官方频道口径，避免下拉被清空。
    /category\.trim\(\) !== ""/.test(listingForm),
);

// ⑥ 话题：正文里写 #词，前端预览与后端同一规则（≤5 个 / 单个 ≤12 字）
const keywordsPy = read("app/keywords.py");
const postUtils = src("utils/post.ts");
note(
  "⑥ 话题：正文 #词 ≤5 个 / 单个 ≤12 字，前后端同规则",
  /AI_MAX = 5/.test(keywordsPy) && /_HASH = re\.compile\(r"\[#/.test(keywordsPy) && /\{1,12\}/.test(postUtils) && /length >= 5/.test(postUtils),
);

// ⑦ 全站合规（§7.1 / §7.4 / §7.5）
const complianceTargets = [
  "components/common/PostCard.vue",
  "components/discover/ListingCard.vue",
  "components/room/RoomEntryCard.vue",
  "components/ContentDetail.vue",
  "components/RoomComments.vue",
  "components/room/EmbedConsentCard.vue",
  "views/RoomView.vue",
];
const missingSource = complianceTargets.filter((f) => !/SourceBlock/.test(src(f)) && !/ReportButton/.test(src(f)));
// 发现页 / 首页推荐 / 关注流 / 频道页的内容卡都必须走 PostCard（来源与举报由它常驻提供），不得各自重写一套。
const postCardUsers = ["views/DiscoverView.vue", "components/home/RecommendTab.vue", "components/home/FeedTab.vue", "views/ChannelView.vue"];
const notUsingPostCard = postCardUsers.filter((f) => !/<PostCard/.test(src(f)));
const postCardSrc = src("components/common/PostCard.vue");
const postCardHasProof = /canonicalUrl/.test(postCardSrc) && /ReportButton/.test(postCardSrc);
const ugcCount = (allVue.match(/data-ugc/g) ?? []).length;
note(
  "⑦ 合规：来源回链 / 常驻举报覆盖全部内容视图",
  missingSource.length === 0 && notUsingPostCard.length === 0 && postCardHasProof,
  `缺 ${[...missingSource, ...notUsingPostCard].join(",") || "无"}`,
);
note(
  "⑦ 合规：用户内容标 data-ugc、语言按钮标 data-no-hant、推荐流有「为什么推荐」、发现页不做个性化推荐",
  ugcCount >= 20 &&
    /data-no-hant/.test(src("layouts/AppShell.vue")) &&
    /whyText/.test(postCardSrc) &&
    /:why-text=/.test(src("components/home/RecommendTab.vue")) &&
    // 发现页 = 按地区 / 分类浏览、不进画像（PRD §36.11）：不得出现推荐理由与「减少此类内容」
    !/:why-text=|less-like/.test(src("views/DiscoverView.vue")),
  `${ugcCount} 处 UGC 标记`,
);

// ⑧ 简繁与主题（check-h5 / gen-hant --check / §7.6）
const proto = read("prototype-x-style.html");
const block = proto.match(/HANT-TABLE:BEGIN \*\/([\s\S]*?)\/\* HANT-TABLE:END/)[1];
const hantC = block.match(/HANT_C = ("(?:[^"\\]|\\.)*")/)[1];
const hantP = block.match(/HANT_P = ("(?:[^"\\]|\\.)*")/)[1];
const table = src("i18n/hantTable.ts");
const theme = src("stores/theme.ts");
const uiLang = src("i18n/uiLang.ts");
note(
  "⑧ 简繁：转换表与原型逐字同源（gen-hant.py 产物）",
  table.includes(`export const HANT_C = ${hantC};`) && table.includes(`export const HANT_P = ${hantP};`),
);
// 按函数边界切片，避免相邻 setter 被贪婪正则误判为「互相赋值」。
const setThemeBody = theme.slice(theme.indexOf("function setTheme"), theme.indexOf("function setLang"));
const setLangBody = theme.slice(theme.indexOf("function setLang"), theme.indexOf("function toggleTheme"));
note(
  "⑧ 主题：主题/语言 setter 互不耦合，watch 统一落 DOM",
  /watch\(\[theme, lang\], apply/.test(theme) &&
    setThemeBody.length > 0 &&
    setLangBody.length > 0 &&
    !/lang\.value\s*=/.test(setThemeBody) &&
    !/theme\.value\s*=/.test(setLangBody) &&
    /data-theme/.test(theme),
);
note(
  "⑧ 简繁：DOM 转换跳过 UGC / 输入控件，并覆盖 aria-label/title/document.title",
  /data-ugc/.test(uiLang) && /LANG_ATTRS/.test(uiLang) && /document\.title/.test(uiLang) && /SKIP_TAGS/.test(uiLang),
);

// ⑨ 路由与状态机（check-flow / check-discover 的正式前端等价）
const router = src("router/index.ts");
const viewNames = ["home", "discover", "messages", "profile", "room", "publish", "content", "user"];
const stores = ["auth", "theme", "toast"].every((name) => fs.existsSync(path.join(webRoot, "src/stores", `${name}.ts`)));
note(
  "⑨ 状态机：八个视图路由 + AppShell + 三 store 齐备",
  viewNames.every((name) => router.includes(`name: "${name}"`)) &&
    /AppShell/.test(router) &&
    stores &&
    /HomeView/.test(router) &&
    /PublishView/.test(router),
);

console.log(
  fails === 0
    ? `\nRESULT: 正式前端门禁全绿（${vueFiles.length} SFC / ${symbols.size} 图标）-> OK`
    : `\nRESULT: ${fails} 条门禁失败 -> release blocked`,
);
console.log("提示：对比度仍需单独跑 python design-system/check-contrast.py；构建跑 npm run build；后端契约跑 pytest tests/。");
process.exit(fails ? 1 : 0);
