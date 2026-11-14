#!/usr/bin/env node
/* UKCN Design System · v2.1 H5 流程门禁（MASTER v2.1 §22 / PRD §36.9）。
 *
 * 真实执行三页脚本（轻量 DOM mock）并检查：
 *   A. 分类信息：卡片 / 详情要素齐全；联系方式需登录（游客点击不显示，登录后显示并留查看记录）；过期不给联系方式
 *   B. 分类信息不跨国：日本 / 定位关闭时发现页、频道详情、深链详情都看不到英国分类信息；「为你推荐」永不出现分类信息
 *   C. AI 自动关键词：最多 5 个、每个 ≤12 字、正文太短不建议；用户填了关键词就不触发；发布页标「AI 建议，可删」
 *   D. 简繁切换：界面文案转换、[data-ugc] 用户内容与输入框不转换、切回简体复原、偏好全站共享
 *   E. 「正在关注」未读分隔线：按共享层上次看到时间插入，进入后更新时间
 *   F. 房间页旧 roomForm 已删除；文档版本与条目
 *   G. 发现页头部瘦身（v2.2）：无登录状态条、地区 + 分类一行横滑、说明只首次显示且可关、游客预览开关在「我的」
 *   H. v2.3：移动端帖子正文 15px / 1.5；房间帖子默认不进频道，房主「推到频道」/「撤回推送」，来源房间标签，国家隔离与 norec；底栏 5 项
 *   J. v2.5 方便实用：喜欢 / 分享可用且状态可见、收藏状态重渲染不丢、滚动位置记忆与返回来处、手机端顶栏下滑收起、发布草稿自动保存、桌面「/」聚焦搜索
 *   I. v2.4：产品名「海外圈」（简繁同形），界面无旧名「全球中文频道社区」/「CN Channels」
 * Exit 1 blocks release.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const PROJECT = path.dirname(ROOT);
const read = f => fs.readFileSync(f, 'utf8');
const home = read(path.join(PROJECT, 'prototype-x-style.html'));
const room = read(path.join(PROJECT, 'prototype-collection-room.html'));
const pub = read(path.join(PROJECT, 'publish-content.html'));
const shared = read(path.join(PROJECT, 'shared', 'ukcn-shared.js'));
const master = read(path.join(ROOT, 'MASTER.md'));
const prd = read(path.join(PROJECT, 'PRD-UK-Chinese-Local-Community-v1.1.md'));
const homeJs = [...home.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

let fails = 0;
const note = (ok, label, extra) => {
  if (!ok) fails++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra !== undefined && extra !== '' ? ' · ' + extra : ''}`);
};

/* ---------------------------------------------- 首页 mock（同 check-location） */
class El {
  constructor(sel) {
    this.sel = sel; this._html = ''; this._text = ''; this.attrs = {};
    this.classes = new Set(); this.dataset = {}; this.style = {}; this.value = '';
    const self = this;
    this.classList = {
      add: (...c) => c.forEach(x => self.classes.add(x)),
      remove: (...c) => c.forEach(x => self.classes.delete(x)),
      contains: c => self.classes.has(c),
      toggle: (c, force) => { const on = force === undefined ? !self.classes.has(c) : force; on ? self.classes.add(c) : self.classes.delete(c); return on; },
    };
  }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  addEventListener() {}
  querySelector() { return null; }
  closest() { return null; }
}
const elements = new Map();
const handlers = {};
const doc = {
  body: new El('body'),
  querySelector(sel) { if (!elements.has(sel)) elements.set(sel, new El(sel)); return elements.get(sel); },
  querySelectorAll() { return []; },
  getElementById(id) { return doc.querySelector('#' + id); },
  addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
};
doc.body.dataset.theme = 'dark';
const sandbox = {
  document: doc, console, window: { scrollTo() {} },
  setTimeout: () => 1, clearTimeout: () => {}, CSS: { escape: s => String(s) },
  Date, Math, JSON, Array, Object, String, Number, Boolean, RegExp, Error, Set, Map,
};
sandbox.globalThis = sandbox;
const ev = s => vm.runInContext(s, sandbox);
function click(key, attrs) {
  const target = {
    closest(sel) {
      if (sel !== key) return null;
      return { dataset: Object.assign({}, attrs), getAttribute: n => attrs[n] ?? null, setAttribute() {},
        classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } }, textContent: '', innerHTML: '' };
    },
  };
  (handlers.click || []).forEach(fn => fn({ target, preventDefault() {} }));
}

console.log('v2.1 · H5 流程门禁（分类信息 / 联系方式 / AI 关键词 / 简繁 / 未读分隔线）');
console.log('='.repeat(78));
let runOk = true;
try { vm.createContext(sandbox); vm.runInContext(homeJs, sandbox, { filename: 'prototype-x-style.html', timeout: 5000 }); }
catch (e) { runOk = false; console.log('  RUN_ERROR ' + e.message); }
note(runOk, '首页脚本真实执行无未捕获异常');

/* ---------------------------------------------- A */
console.log('\n[A] 分类信息卡片 / 详情 / 联系方式需登录');
{
  const kinds = ev("Object.keys(LISTING_KINDS).join(',')");
  /* v2.7 / 2026-11-12 分类表单：房产拆租赁 / 买卖 / 商业，市场=二手，招聘含职位 */
  note(kinds === 'rent,sale,commercial,secondhand,job', '分类结构：房产三子类 + 二手 + 招聘', kinds);
  const card = ev("listingCardHTML(findListing('L1'))");
  note(/£720/.test(card) && /已认证/.test(card) && /剩 \d+ 天/.test(card) && card.includes('data-listing-open="L1"'), 'ListingCard：价格、认证、剩余天数、详情入口');
  const exp = ev("listingCardHTML(findListing('L3'))");
  note(exp.includes('已过期'), '过期信息卡片标「已过期」');
  ev("UKCN.state().signedIn=true; listingContactShown.clear()");
  const d = ev("renderListingDetail(findListing('L1'))");
  note(d.includes('lst-gallery') || d.includes('<img'), '详情：图片');
  note(['房型', '入住时间', 'Bills', '押金', '最短租期'].every(x => d.includes(x)), '详情：租房关键字段（房型 / 入住 / Bills / 押金 / 租期）');
  note(d.includes('lst-pub') && d.includes('已认证'), '详情：发布者信息与认证标识');
  note(/剩 \d+ 天|已过期/.test(d) && d.includes('防骗'), '详情：过期状态与防骗提示');
  note(d.includes('data-report'), '详情：举报入口');
  note(d.includes('不进「为你推荐」'), '详情：注明不进推荐');
  note(d.includes('data-listing-contact="L1"') && !d.includes('data-listing-contact-shown'), '登录用户也要主动点「查看联系方式」才显示');
  const full = ev("findListing('L1').contact.full"), masked = ev("findListing('L1').contact.masked");
  note(!d.includes(full) && d.includes(masked), '点击前只显示打码示例', masked);
  ev("UKCN.logout(); listingContactShown.clear(); listingDetailId='L1'; currentPage='discover'");
  const views0 = ev('UKCN.state().contactViews.length');
  click('[data-listing-contact]', { listingContact: 'L1' });
  const g = ev("renderListingDetail(findListing('L1'))");
  note(!g.includes(full) && !g.includes('data-listing-contact-shown') && ev('UKCN.state().contactViews.length') === views0,
    '游客点「查看联系方式」：先走轻注册，不显示号码、不记查看');
  note(g.includes('需先轻注册'), '游客看到「需先轻注册并验证手机号」提示');
  ev("UKCN.state().signedIn=true");
  const g2 = ev("renderListingDetail(findListing('L1'))");
  note(!g2.includes(full), '登录本身不自动泄露号码（仍需点击）');
  click('[data-listing-contact]', { listingContact: 'L1' });
  const s = ev("renderListingDetail(findListing('L1'))");
  note(s.includes(full) && s.includes('data-listing-contact-shown="L1"'), '登录后点击：显示联系方式');
  note(ev('UKCN.state().contactViews.length') === views0 + 1, '查看联系方式写入 contactViews 留痕');
  const e3 = ev("renderListingDetail(findListing('L3'))");
  note(!e3.includes('data-listing-contact="L3"') && !e3.includes(ev("findListing('L3').contact.full")), '过期信息不再给联系方式');
  ev("listingDetailId=null");
}

/* ---------------------------------------------- B */
console.log('\n[B] 分类信息不跨国 · 不进推荐');
{
  const ukDisc = ev("discoverDetailCode=null; listingDetailId=null; discoveryScope='UK'; discoveryCategoryFilter='all'; searchTerm=''; renderDiscover()");
  note(ukDisc.includes('listing-card') && ukDisc.includes('单独分区，不进推荐'), '英国：发现页（英国范围）有单独的分类信息区');
  note(!ev("discoveryScope='GLOBAL'; renderDiscover()").includes('listing-card'), '国际范围不出现国家分类信息');
  note(!/data-listing-open="L3"/.test(ukDisc), '发现页分类信息区不放过期信息');
  const ukCh = ev("renderChannelDetail(byCode['housing'])");
  note(ukCh.includes('data-listing-open="L1"'), '英国：租房频道详情有分类信息');
  note(!doc.querySelector('#panel-foryou').innerHTML.includes('listing-card'), '「为你推荐」不出现分类信息');
  const pick = value => (handlers.change || []).forEach(fn => fn({ target: { id: 'countryPick', value, closest: () => null, dataset: {} } }));
  const snap = () => ({
    n: ev('visibleListings().length'),
    disc: ev("discoverDetailCode=null; listingDetailId=null; discoveryScope='all'; renderDiscover()"),
    det: ev("renderListingDetail(findListing('L1'))"),
    ch: ev("renderChannelDetail(byCode['housing'])"),
  });
  for (const [name, c] of [['日本（未开通）', 'JP'], ['定位关闭 / 不选国家', '']]) {
    pick(c);
    const s = snap();
    note(s.n === 0, name + '：可见分类信息为 0', s.n);
    note(!s.disc.includes('listing-card'), name + '：发现页无英国分类信息');
    note(!s.ch.includes('listing-card'), name + '：频道详情深链不带分类信息');
    note(!s.det.includes('lst-fields') && !s.det.includes(ev("findListing('L1').contact.masked")) && s.det.includes('频道'), name + '：深链打开英国信息详情被拦下');
  }
  pick('UK');
  note(ev('visibleListings().length') > 0, '切回英国后分类信息恢复');
}

/* ---------------------------------------------- C */
console.log('\n[C] 官方 AI 自动关键词（PRD §30.6）');
{
  const sb = { console }; vm.createContext(sb);
  vm.runInContext(shared + ';this.U=UKCN;', sb);
  const U = sb.U;
  const long = 'Zone 2 合租单间转租，包 bills，近 Elizabeth line 和地铁，押金进 DPS，伦敦 Stratford，IKEA 家具，可随时看房，二手电器转让，兼职求职，签证 BRP';
  const k = U.aiKeywords(long, '房产');
  note(k.length === 5, '命中很多时最多 5 个', k.join(' / '));
  note(k.every(x => x.length <= 12), '每个 ≤12 字');
  note(new Set(k).size === k.length, '不重复');
  note(U.aiKeywords('你好', '房产').length === 0, '正文太短（低置信）不建议');
  note(U.AI_MAX === 5, 'AI_MAX = 5');
  const kk = U.aiKeywords('周末二手书桌转让，自取', '');
  note(kk.includes('二手') && kk.includes('自取'), '按正文命中受控词表', kk.join(' / '));
  note(/if \(state\.topics\.length\) return \[\];/.test(pub), '发布页：用户已填关键词则不触发');
  note(pub.includes('AI 建议，可删') && pub.includes('ai-badge') && pub.includes('id="aiLive" aria-live="polite"'), '发布页：「AI 建议，可删」+ AI 徽标 + aria-live');
  note(pub.includes("keywordSource: state.topics.length ? 'user' : ((state.aiKeywords || []).length ? 'ai_auto' : 'none')"), '发布时记录 keywordSource（ai_auto）');
  note(/state\.cityTopic/.test(pub) && !/state\.topics\.push\(routeCity\)/.test(pub), '城市话题单独存放，不算用户关键词');
  /* v2.7：分类改由发布者在标题后显式选择，不再只读继承目标频道；房产再选子类；
     招聘用「职位」取代工作许可；位置为单一自由输入；频道分类不匹配或非频道目标禁止提交。 */
  note(pub.includes('id="f-listing-category"') && pub.includes('请选择分类') &&
       pub.includes('function listingSpec(category, propertyType)') &&
       pub.includes("if (category === '房产') return PROPERTY_FORMS") &&
       pub.includes('id="f-listing-property-type"') && pub.includes('id="f-l-area"') &&
       pub.includes("['position', '职位'") && !pub.includes('工作许可') &&
       pub.includes('所选分类与当前频道不匹配') && pub.includes('分类信息必须发布到频道'),
       '发布页：标题后必选分类 + 房产三子类 + 职位 / 位置 + 频道分类匹配校验');
  note(pub.includes("CURRENCY_CODES = { UK: 'GBP', JP: 'JPY', CA: 'CAD' }") && pub.includes("GBP:'£'"),
       '发布页：价格符号按目标频道所属国家推导');
}

/* ---------------------------------------------- D */
console.log('\n[D] 简繁切换（界面转换，用户内容不转换）');
{
  /* 迷你 DOM：够跑共享层的 TreeWalker 转换 */
  class N {
    constructor(type, tag, value) { this.nodeType = type; this.tagName = tag; this.nodeValue = value; this.childNodes = []; this.parentNode = null; this.attrs = {}; }
    append(...c) { c.forEach(x => { x.parentNode = this; this.childNodes.push(x); }); return this; }
    hasAttribute(k) { return k in this.attrs; } getAttribute(k) { return this.attrs[k] ?? null; } setAttribute(k, v) { this.attrs[k] = String(v); }
  }
  const E = (tag, attrs, ...kids) => { const n = new N(1, tag); Object.assign(n.attrs, attrs || {}); return n.append(...kids); };
  const T = v => new N(3, undefined, v);
  const body = E('BODY', {},
    E('DIV', { 'aria-label': '发布内容' }, T('为你推荐 · 正在关注 · 设置')),
    E('ARTICLE', {}, E('P', { 'data-ugc': '' }, T('用户原文：伦敦这里发布')), E('SPAN', {}, T('举报这条帖子'))),
    E('TEXTAREA', {}, T('输入框里的草稿')),
    E('INPUT', { placeholder: '搜索频道' }));
  const docEl = E('HTML', { lang: 'zh-Hans' });
  const walker = (root, what, filter) => {
    const out = [];
    (function walk(n) { for (const c of n.childNodes) { const r = filter.acceptNode(c); if (r === 1) out.push(c); if (c.nodeType === 1 && r !== 2) walk(c); } })(root);
    let i = 0; return { nextNode: () => out[i++] || null };
  };
  const mem = {};
  const sb = { console, WeakMap, Array,
    window: { localStorage: { getItem: k => mem[k] ?? null, setItem: (k, v) => { mem[k] = v; } } },
    document: { body, documentElement: docEl, title: '首页', readyState: 'complete', createTreeWalker: walker,
      querySelector: () => null, addEventListener() {}, createElement: undefined } };
  sb.setTimeout = () => 1;
  vm.createContext(sb);
  vm.runInContext(shared + ';this.U=UKCN;', sb);
  const U = sb.U;
  const t = U.toHant('为你推荐 发布 查看联系方式 举报 视频 只看国际频道 设置');
  note(t === '為你推薦 發佈 查看聯繫方式 檢舉 影片 只看國際頻道 設置', 'toHant 字表 + 词组', t);
  note(U.lang() === 'zh-Hans', '默认简体');
  U.setLang('zh-Hant');
  const ui = body.childNodes[0], ugc = body.childNodes[1].childNodes[0].childNodes[0], rep = body.childNodes[1].childNodes[1].childNodes[0];
  note(ui.childNodes[0].nodeValue === '為你推薦 · 正在關注 · 設置' && rep.nodeValue === '檢舉這條帖子', '切到繁体：界面文案转换');
  note(ui.getAttribute('aria-label') === '發佈內容' && body.childNodes[3].getAttribute('placeholder') === '搜索頻道', 'aria-label / placeholder 一并转换');
  note(ugc.nodeValue === '用户原文：伦敦这里发布', '[data-ugc] 用户内容保持原文');
  note(body.childNodes[2].childNodes[0].nodeValue === '输入框里的草稿', 'textarea 草稿不转换');
  note(docEl.getAttribute('lang') === 'zh-Hant' && sb.document.title === '首頁', 'html lang 与标题同步');
  note(JSON.parse(mem['ukcn.demo.v1']).prefLang === 'zh-Hant', '偏好写入共享存储（三页共用）');
  U.setLang('zh-Hans');
  note(ui.childNodes[0].nodeValue === '为你推荐 · 正在关注 · 设置' && ui.getAttribute('aria-label') === '发布内容' && docEl.getAttribute('lang') === 'zh-Hans', '切回简体：原文复原');
  for (const [n, h] of [['首页', home], ['房间页', room], ['发布页', pub]]) note(h.includes('function applyLang()') && h.includes('/* HANT-TABLE:BEGIN */'), n + '内联共享层含简繁转换');
  note(/<p data-ugc>\$\{linkify\(it\.text\)\}<\/p>/.test(home) && home.includes('<h3 data-ugc>') && room.includes('cmt-text" data-ugc') && pub.includes('post-copy" data-ugc'), '三页的帖子正文 / 标题 / 留言标 data-ugc');
  note(!home.includes('其它页面文案待接入') && home.includes('UKCN.setLang(lang.dataset.meLang)'), '「我的 · 设置」简繁切换全站生效（游客可用）');
  note(shared.includes("s.prefLang = s.user.lang") , '注册第 3 屏的简繁选择写入全站偏好');
}

/* ---------------------------------------------- E */
console.log('\n[E] 「正在关注」未读分隔线（US-03）');
{
  ev("UKCN.state().signedIn=true; subs.add('housing'); UKCN.markSeen('following', Date.now()-150*6e4); followingOpen=false; currentPage='home'");
  ev("switchTab('following')");
  const f = doc.querySelector('#panel-following').innerHTML;
  const cnt = (f.match(/data-unread-divider/g) || []).length;
  note(cnt === 1 && f.includes('以下为上次看过'), '有一条「以下为上次看过」分隔线', cnt);
  const before = f.split('data-unread-divider')[0];
  note((before.match(/<article class="card"/g) || []).length >= 1, '分隔线之前是新内容');
  note(Date.now() - ev("UKCN.lastSeen('following')") < 5000, '进入后把上次看到时间更新为现在（共享存储）');
  note(/上次看到 .+，\d+ 条新内容/.test(f), '提示上次看到时间与新内容条数');
  ev("switchTab('foryou'); switchTab('following')");
  const f2 = doc.querySelector('#panel-following').innerHTML;
  note(f2.includes('没有新内容 · 以下为上次看过'), '再次进入：没有新内容时分隔线在最上方');
  ev("switchTab('foryou')");
}

/* ---------------------------------------------- G */
console.log('\n[G] 发现页头部瘦身（v2.2，Rio 2026-11-11 批准）');
{
  ev("UKCN.state().signedIn=true; listingDetailId=null; discoverDetailCode=null; discoveryScope='all'; discoveryCategoryFilter='all'; searchTerm=''");
  ev("UKCN.state().tips={}; discoverIntroOpen=null");
  const first = ev('renderDiscover()');
  const head = first.split('<article')[0];
  note(!/guest-mode-bar|已登录为|data-guest-preview/.test(first), '发现页不再有登录状态条与游客预览按钮');
  const rows = (head.match(/class="discover-chips"/g) || []).length;
  const chips = (head.split('class="discover-chips"')[1] || '').split('</div>')[0];
  note(rows === 1 && /data-discovery-scope=/.test(chips) && /data-discovery-category=/.test(chips) && chips.includes('dc-divider'), '地区与分类合成一行 chip（中间细分隔线）');
  note(!/page-toolbar|directory-filters/.test(head), '旧的地区行与分类行已去掉');
  note(/\.discover-chips\{[^}]*overflow-x:auto[^}]*white-space:nowrap/.test(home) && /\.discover-chips \.page-filter\{[^}]*min-height:44px/.test(home), 'chip 行横滑不换行，chip 高 44px');
  note(head.includes('discover-intro') && head.includes('data-discover-intro-close'), '首次进入显示说明，可关闭');
  note(!!ev('UKCN.state().tips.discoverIntro'), '首次显示即记入共享存储 tips.discoverIntro');
  click('[data-discover-intro-close]', {});
  note(!ev('renderDiscover()').includes('discover-intro'), '点「知道了」后说明消失');
  ev('discoverIntroOpen=null');
  note(!ev('renderDiscover()').includes('discover-intro'), '再次进入（新页面加载）不再显示说明');
  const meta = (head.split('class="discover-meta"')[1] || '').split('</p>')[0];
  note(meta.includes('page-heading') && meta.includes('不进画像') && /近期更新 \d+ 条/.test(meta), '标题、条数、不进画像收成一行元信息');
  note(!/class="page-description"/.test(head), '不再常驻说明段落');
  ev('UKCN.logout()');
  const g = ev('renderDiscover()').split('<article')[0];
  note(g.includes('访客浏览') && !g.includes('guest-mode-bar'), '游客：元信息行内保留精简「访客浏览」提示');
  const meGuest = ev('renderMe()');
  ev('UKCN.state().signedIn=true');
  const meIn = ev('renderMe()');
  note(meIn.includes('data-guest-preview') && meIn.includes('游客预览'), '「我的 · 设置」有游客预览开关（已登录）');
  note(meGuest.includes('正在游客预览') && meGuest.includes('data-auth='), '游客在「我的」可登录 / 注册恢复');
  note((meIn.match(/data-guest-preview/g) || []).length === 1, '游客预览开关只有一处（演示工具里的重复按钮已移除）');
}

/* ---------------------------------------------- H */
console.log('\n[H] v2.3：正文 15px · 房间帖子推到频道 · 频道与发现分开');
{
  const tokens = read(path.join(ROOT, 'tokens.css'));
  const mob15 = (h, sel) => new RegExp('@media\\(max-width:760px\\)\\{\\s*[^}]*' + sel.replace(/\./g, '\\.') + '[^{]*\\{font-size:15px;line-height:1\\.5\\}').test(h);
  note(mob15(home, '.card-copy p') && mob15(home, '.channel-post-copy') && mob15(room, '.cmt-text') && mob15(pub, '.post-copy'), '三页移动端帖子正文 15px / 行高 1.5');
  note(/--fs-body-mobile: 15px; --lh-body-mobile: 1\.5;/.test(tokens) && /input, textarea, select \{ font-size: var\(--fs-16\); \}/.test(tokens) && !/正文不得小于 16px -/.test(tokens), 'tokens.css：移动端正文 15px / 1.5，输入框仍 16px（旧 16px 规则作废）');
  note(/MASTER v2\.(?:[3-9]|\d{2,})/.test(master) && master.includes('RoomPushAction') && master.includes('RoomOriginLabel') && master.includes('保持分开'), 'MASTER ≥ v2.3：15px、RoomPushAction / RoomOriginLabel、频道与发现分开');
  note(['### 36.11', '### 36.12', '### 36.13', 'room_post_push'].every(x => prd.includes(x)) && /\| 2026-11-11 \| v1\.1 \+ §36\.11 – §36\.13 \|/.test(prd), 'PRD §36.11 – §36.13 + 变更记录');
  note((home.match(/data-nav-key="(home|channels|discover|notifications|me)"/g) || []).length === 5 && home.includes('data-nav-key="discover"'), '底栏仍为 5 项，「发现」独立存在');

  const pick = value => (handlers.change || []).forEach(fn => fn({ target: { id: 'countryPick', value, closest: () => null, dataset: {} } }));
  pick('UK');
  ev("UKCN.state().signedIn=true; UKCN.state().user.handle='@pei'; reloadFromStore()");
  const housing = () => ev("renderChannelDetail(byCode['housing'])");
  const h0 = housing();
  note((h0.match(/room-origin-post/g) || []).length === 1 && h0.includes('来自房间 · ') && h0.includes('data-room-origin="r6"'), '示例：房主推过的 1 条出现在频道动态，标「来自房间 · 房间名」');
  note(!h0.includes(ev("ROOM_POSTS.find(p=>p.id==='rp-r6-2').title")), '没推的房间帖子不进频道动态');
  note(!ev("renderChannelDetail(byCode['movie'])").includes('room-origin-post'), '没有推送的频道里没有房间帖子（默认不进）');
  const r6 = "myRooms.find(r=>r.id==='r6')";
  note(ev(`UKCN.pushRoomPost(${r6},'rp-r6-2','seed')`) === null && !ev("UKCN.pushedPost('rp-r6-2')"), '非房主不能推（共享层拒绝）');
  note(ev(`UKCN.unpushRoomPost(${r6},'rp-r6-1')`) === false && !!ev("UKCN.pushedPost('rp-r6-1')"), '非房主不能撤回别人的推送');
  ev("var __room=UKCN.createRoom({name:'门禁测试房',parentCode:'housing',typeCode:'general',type:'通用'}); reloadFromStore();" +
     "var __p=UKCN.addPost({dest:'room',roomId:__room.id,roomName:__room.name,parentCode:'housing',title:'门禁推送测试帖',text:'只用于门禁',tags:[]});");
  note(ev("UKCN.pushRoomPost(__room,__p.id,'store')") !== null && !housing().includes('门禁推送测试帖'), '审核中的帖子即使有推送记录也不显示');
  ev("UKCN.unpushRoomPost(__room,__p.id); UKCN.approve(__p.id)");
  note(!housing().includes('门禁推送测试帖'), '已公开但未推送：不进频道动态');
  note(ev("!!UKCN.pushRoomPost(__room,__p.id,'store')") && housing().includes('门禁推送测试帖') && housing().includes('data-room-origin="' + ev('__room.id') + '"'), '房主推送后出现在所属频道，带来源房间标签');
  note(/data-room-origin="[^"]+" data-room-open="/.test(housing()), '来源标签可点开房间（data-room-open）');
  const noRec = () => ['#panel-foryou', '#panel-following'].map(sel => doc.querySelector(sel).innerHTML).join('') + ev("discoverDetailCode=null; listingDetailId=null; discoveryScope='all'; renderDiscover()");
  ev('renderAll()');
  note(!/room-origin-post|门禁推送测试帖/.test(noRec()), '推送帖子不进为你推荐 / 正在关注 / 发现（norec）');
  pick('JP');
  note(!housing().includes('门禁推送测试帖') && !housing().includes('room-origin-post'), '切到日本：英国频道里的推送帖子不可见');
  pick('UK');
  note(ev("UKCN.unpushRoomPost(__room,__p.id)") === true && !housing().includes('门禁推送测试帖'), '房主撤回推送后从频道动态消失');
  note(room.includes('function pushOpsHTML(room,p)') && /if\(UKCN\.canPush\(room\)&&published\)/.test(room) && room.includes("if(!UKCN.canPush(room)){ toast('只有房主可以推到频道'); return; }"), '房间页：推送按钮只给房主且限已公开帖子，点击处理再校验一次');
  note(room.includes('推到频道') && room.includes('撤回推送') && room.includes('已推到频道「'), '房间页三种状态文案：推到频道 / 已推到频道 / 撤回推送');
  note(!pub.includes('显示在房间与所属频道详情'), '发布页提示不再说房间帖子会进频道');
}

/* ---------------------------------------------- I */
console.log('\n[I] v2.4：产品名「海外圈」');
{
  const preview = read(path.join(ROOT, 'preview.html'));
  const shared = read(path.join(PROJECT, 'shared', 'ukcn-shared.js'));
  const OLD = /CN Channels|CN CHANNELS|全球中文频道社区|全球中文頻道社區|海外社区|海外社區/i;
  const files = { 首页: home, 房间: room, 发布: pub, 展示页: preview, 共享层: shared };
  note(Object.values(files).every(h => !OLD.test(h)), '三页、展示页与共享层没有旧产品名（全球中文频道社区 / CN Channels / 海外社区）');
  const title = h => (h.match(/<title>([^<]*)<\/title>/) || [])[1] || '';
  note([home, room, pub, preview].every(h => title(h).includes('海外圈')), '四个页面的 <title> 都是「海外圈」');
  const brand = '<span class="mark" aria-hidden="true">海</span><span>海外圈</span>';
  note(home.includes(brand) && room.includes(brand) && preview.includes('<span class="mark" aria-hidden="true">海</span><span>海外圈 Design System</span>'), '品牌栏 logo 字「海」+ 产品名');
  note(home.includes('<h1 id="pageTitle"><span class="pt-brand">海外圈</span><span class="pt-page">首页</span></h1>') && /@media\(max-width:760px\)\{\.pt-brand\{display:inline\}\.pt-brand\+\.pt-page\{display:none\}\}/.test(home) && /\.pt-brand\{display:none\}/.test(home), '手机端首页标题位显示产品名，桌面显示「首页」');
  ev("setPage('notifications'); setPage('home')");
  note(doc.querySelector('#pageTitle').innerHTML.includes('pt-brand'), '切页回到首页后标题位仍带产品名');
  note(shared.includes("setSheet('登录或注册海外圈'") && shared.includes("title: '欢迎来到海外圈'"), '登录弹窗标题与欢迎通知用新名');
  note(ev("UKCN.toHant('海外圈')") === '海外圈', '繁体：海外圈简繁同形（toHant 不变）');
  note(/MASTER v2\.(?:[4-9]|\d{2,})/.test(master) && master.includes('BrandName') && master.startsWith('# 海外圈设计规范系统'), 'MASTER ≥ v2.4：BrandName，标题为新名');
  note(prd.startsWith('# 海外圈 Web') && prd.includes('### 36.14') && prd.includes('| 产品名 | **海外圈**') && /\| 2026-11-11 \| v1\.1 \+ §36\.14 \|/.test(prd), 'PRD 标题、产品名行、§36.14 与变更记录');
  note(home.includes("name:'国际华人交流'") && !/name:'海外[^']*'/.test(home), '频道层级用语未被改名（国际频道照旧）');
}

/* ---------------------------------------------- J */
console.log('\n[J] v2.5：方便实用');
{
  const shared = read(path.join(PROJECT, 'shared', 'ukcn-shared.js'));
  ev("UKCN.state().signedIn=true; reloadFromStore(); renderAll()");
  note(ev("var __k='j-like-test'; UKCN.toggleLike(__k)===true && UKCN.liked(__k)===true && UKCN.toggleLike(__k)===false && UKCN.liked(__k)===false"), '共享层：喜欢可切换，状态按账号存');
  note(ev("(function(){var s=UKCN.state(),u=s.signedIn;s.signedIn=false;var r=UKCN.toggleLike('j-guest')===null&&!UKCN.liked('j-guest');s.signedIn=u;return r})()"), '游客不能直接喜欢（返回 null，页面会先轻注册）');
  note(ev("UKCN.saveDraft({text:'  '})===null && UKCN.draft()===null && !!UKCN.saveDraft({text:'草稿',type:'text',topics:['a']}) && UKCN.draft().text==='草稿' && (UKCN.clearDraft(),UKCN.draft()===null)"), '共享层：草稿保存 / 读取 / 清空，空内容不存');
  note(typeof ev('UKCN.shareLink') === 'function' && /nav\.share/.test(shared) && /clipboard\.writeText/.test(shared) && !/fetch\(|XMLHttpRequest/.test(shared.slice(shared.indexOf('function shareLink'), shared.indexOf('function shareLink') + 1200)), '分享：系统分享 → 复制链接，不发外部请求');
  const card = ev("cardHTML(items.find(it=>!it.userPost),true)");
  note(/data-like="[^"]+" aria-pressed="false" aria-label="喜欢"/.test(card) && /data-share="[^"]+" aria-label="分享"/.test(card) && /data-save="[^"]+" aria-pressed="false" aria-label="收藏"/.test(card), '帖子卡：喜欢 / 收藏 / 分享都是真按钮（aria-pressed）');
  note(!/喜欢功能待接入|分享功能待接入/.test(home), '首页不再有「喜欢 / 分享功能待接入」占位提示');
  ev("var __it=items.find(it=>!it.userPost); saved.add(__it.title); UKCN.toggleLike(__it.postId||__it.title)");
  const card2 = ev("cardHTML(__it,true)");
  note(/class="act like liked" data-like="[^"]+" aria-pressed="true" aria-label="已喜欢"/.test(card2) && /class="act saved" data-save="[^"]+" aria-pressed="true" aria-label="已收藏"/.test(card2), '重新渲染后喜欢 / 收藏状态仍可见（原来收藏重渲染会丢）');
  ev("saved.delete(__it.title); UKCN.toggleLike(__it.postId||__it.title)");
  note(/\.act\.liked\{color:var\(--danger\)\}/.test(home) && /\.act\.liked \.ico,\.act\.saved \.ico\{fill:currentColor\}/.test(home), '喜欢红色实心、收藏蓝色实心（AA 色板）');
  const h = ev("renderChannelDetail(byCode['housing'])");
  note(/room-origin-post[\s\S]*data-like="rp-r6-1"/.test(h) && /data-like=/.test(h) && /data-share=/.test(h), '频道帖子与推送的房间帖子也能喜欢 / 分享');
  note(['function viewKey()', 'function rememberScroll()', 'function restoreScroll()', 'function popDetailReturn()', 'function pushDetailReturn()'].every(x => home.includes(x)) && /if\(detailBack\)\{popDetailReturn\(\);return;\}/.test(home) && /\[data-listing-back\]'\)\)\{popDetailReturn\(\);return;\}/.test(home), '滚动记忆 + 详情「返回」回到来处');
  note(!/switchTab[\s\S]{0,400}window\.scrollTo\(\{top:0,behavior:'smooth'\}\);\r?\n\}/.test(home) && /restoreScroll\(\);\r?\n\}/.test(home), '切 Tab / 切页不再一律回顶部');
  ev("setPage('notifications'); setPage('home')");
  note(doc.querySelector('#pageTitle').innerHTML.includes('pt-brand'), '沙箱里切页仍正常（无滚动 API 时不报错）');
  const hide = /@media\(max-width:760px\)\{\s*\.top\{transition:transform \.2s ease\}\s*body\.hdr-hide \.top\{transform:translateY\(-100%\)\}/;
  note(hide.test(home) && hide.test(room) && /prefers-reduced-motion:reduce\)\{\.top\{transition:none!important\}/.test(home) && /prefers-reduced-motion:reduce\)\{\.top\{transition:none!important\}/.test(room), '首页与房间页：手机端下滑收起顶栏，减少动效时不做动画');
  note([home, room].every(x => /if\(y<140\|\|\(top&&top\.contains\(document\.activeElement\)\)\|\|UKCN\.isOpen\(\)\)/.test(x) && x.includes("typeof window.addEventListener==='function'")), '顶栏：顶部 140px 内、搜索框有焦点、弹层打开时不收起');
  note(room.includes('function postQuickOpsHTML(p)') && room.includes("if(act==='like-post')") && room.includes("if(act==='share-post')") && room.includes("UKCN.requireAuth('喜欢帖子',go)"), '房间帖子：喜欢 / 分享，游客先轻注册');
  note(pub.includes('id="draftNote"') && pub.includes('function restoreDraft()') && pub.includes("$('#body').addEventListener('input', saveDraftSoon)") && /showSubmitted\(saved, room\);\n\s*clearTimeout\(draftTimer\); UKCN\.clearDraft\(\)/.test(pub) && /if \(SELFTEST\) return;/.test(pub), '发布页：草稿自动保存、回来自动恢复、发布成功后删除、自测模式不读写');
  note(/\.draft-clear\{min-height:44px/.test(pub) && pub.includes('清空草稿'), '「清空草稿」按钮 44px');
  note(/e\.key==='\/'&&!typing/.test(home) && home.includes("e.key==='Escape'&&e.target&&e.target.id==='searchInput'"), '桌面：「/」聚焦搜索、Esc 退出（输入时不触发）');
  note(/MASTER v2\.(?:[5-9]|\d{2,})/.test(master) && master.includes('### 22.14') && /\| 2026-11-11 \| v1\.1 \+ §36\.15 \|/.test(prd) && prd.includes('### 36.15'), 'MASTER ≥ v2.5 §22.14、PRD §36.15 + 变更记录');
}

console.log('\n[K] v2.6：站内信（私信 / 消息请求 / 拉黑 / 陌生人私信开关）');
{
  ev("UKCN.reset(); UKCN.state().signedIn=true; reloadFromStore(); renderAll()");
  note(ev("UKCN.dmThreads().length===2 && UKCN.dmRequests().length===2 && UKCN.dmUnread()===3"), '示例：2 个会话 + 2 条消息请求，未读 3');
  note(ev("UKCN.unreadAll()===UKCN.unread()+UKCN.dmUnread()"), '共享层：unreadAll = 未读通知 + 未读私信');
  note(ev("UKCN.dmSend('dm-req-lily',{text:'hi'}).reason==='request' && UKCN.dmAccept('dm-req-lily') && UKCN.dmSend('dm-req-lily',{text:'你好'}).ok"), '消息请求：接受前不能回复，接受后可以');
  note(ev("UKCN.dmDelete('dm-req-sofa') && UKCN.dmRequests().length===0"), '消息请求可删除');
  note(ev("UKCN.dmSend('dm-manling',{text:'  '}).reason==='empty' && UKCN.dmSend('dm-manling',{text:'字'.repeat(1001)}).reason==='long' && UKCN.dmSend('dm-manling',{kind:'image',src:'data:image/png;base64,AA',alt:'图'}).message.kind==='image'"), '发送规则：空内容 / 超 1000 字拒绝；支持图片');
  note(ev("UKCN.dmSend('dm-manling',{kind:'voice',src:'x.m4a'}).ok===false") && !/kind:\s*'voice'|已读回执：已读|readAt/.test(shared), 'v1 没有语音、没有已读回执');
  note(ev("UKCN.blockUser('@londonhome') && UKCN.dmThreads().every(d=>d.peer.handle!=='@londonhome') && UKCN.dmReceive({handle:'@londonhome'},'x')==='blocked' && UKCN.dmSend('dm-londonhome',{text:'x'}).reason==='blocked' && UKCN.unblockUser('@londonhome')"), '拉黑：会话隐藏、对方发不进来、自己也发不出；可解除');
  note(ev("UKCN.setDmAllowStrangers(false)===false && UKCN.dmReceive({handle:'@k_stranger'},'hi')==='filtered' && UKCN.dmReceive({handle:'@manling'},'hi')==='active' && UKCN.setDmAllowStrangers(true) && UKCN.dmReceive({handle:'@k_stranger2'},'hi')==='request'"), '陌生人私信：关闭后陌生人不送达、关注的人照常；打开后陌生人进消息请求');
  note(ev("(function(){var s=UKCN.state(),u=s.signedIn;s.signedIn=false;var r=UKCN.dmOpen({handle:'@manling'})===null&&UKCN.dmUnread()===0&&UKCN.unreadAll()===0;s.signedIn=u;return r})()"), '游客不能发私信，角标为 0');
  note(ev("UKCN.dmOpen({handle:UKCN.me().handle})===null"), '不能给自己发私信');
  note(/dms: \[[\s\S]*dm-req-lily/.test(shared) && /真实投递、推送与风控需要后端/.test(shared), '示例数据在 UKCN 共享层，标注需要后端');
  note((home.match(/data-nav-key="(home|channels|discover|notifications|me)"/g) || []).length === 5 && /data-nav-key="notifications" aria-label="消息"><svg class="ico" aria-hidden="true"><use href="#i-mail"\/><\/svg><span>消息<\/span>/.test(home) && />消息<span class="badge hidden" id="notifyBadge">/.test(home), '底栏 / 左栏「通知」改名「消息」，仍 5 项（内部 key 不变）');
  note(/const all=UKCN\.unreadAll\(\);/.test(home) && /const n = UKCN\.unreadAll\(\);/.test(room), '首页与房间页角标都用 unreadAll');
  note(/data-nav="notifications" aria-label="消息"/.test(room) && !/<span>通知<\/span>/.test(room) && !/<span>通知<\/span>/.test(home), '房间页导航也叫「消息」');
  ev("setPage('notifications')");
  const pv = () => doc.querySelector('#page-view').innerHTML;
  note(/role="tablist"[\s\S]*data-msg-tab="dm" aria-selected="true"[\s\S]*data-msg-tab="notif" aria-selected="false"/.test(pv()) && doc.querySelector('#pageTitle').textContent === '消息', '「消息」页：私信 / 通知分段，默认私信');
  note(/data-dm-requests/.test(pv()) && /data-dm-open="dm-manling"/.test(pv()) && /真实发送需要后端/.test(pv()), '私信列表：消息请求入口、会话、需要后端说明');
  ev("msgTab='notif'; renderPage()");
  note(/data-notif-open|data-notif-allread/.test(pv()), '「通知」分段：原有通知');
  ev("msgTab='dm'; openDMThread('dm-manling')");
  note(/data-dm-block="@manling"/.test(pv()) && /data-dm-report="dm-manling"/.test(pv()) && /maxlength="1000"/.test(pv()) && /data-dm-image/.test(pv()) && /没有已读回执/.test(pv()) && !/data-msg-tab/.test(pv()), '会话：拉黑 / 举报 / 图片 / 1000 字上限 / 无已读回执提示');
  note(/kind:'dm',kindLabel:'私信'/.test(home) && /UKCN\.confirm\(\{title:'拉黑 '/.test(home) && /UKCN\.confirm\(\{title:'删除这条消息请求？'/.test(home), '举报走 openReport（私信），拉黑 / 删除请求先确认');
  ev("dmView={type:'thread',id:'dm-req-lily'}; renderPage()");
  ev("UKCN.reset(); UKCN.state().signedIn=true; reloadFromStore(); dmView={type:'thread',id:'dm-req-lily'}; renderPage()");
  note(/dm-req-banner/.test(pv()) && !/id="dmInput"/.test(pv()), '未接受的请求：横幅 + 不显示输入框');
  note(/UKCN\.requireAuth\('发私信',go\)/.test(home) && /function startDM\(h,name\)/.test(home), '游客点「私信」先登录 / 注册，完成后续上');
  const ch = ev("renderChannelDetail(byCode['housing'])");
  note(/class="dm-chip" data-dm-to="@londonhome"/.test(ch) && (ch.match(/<div class="channel-post-actions">[\s\S]*?<\/div>/g) || []).every(m => !m.includes('dm-chip')), '帖子作者旁有「私信」，不在主操作行');
  note(!/dm-chip/.test(ev("authorHeadHTML(UKCN.me().handle,'我')")), '自己的帖子不显示「私信」');
  ev("openProfile('@londonhome')");
  note(/data-user-follow="@londonhome"/.test(pv()) && /class="mini-btn primary profile-dm" data-dm-to="@londonhome"/.test(pv()) && /data-user-block="@londonhome"/.test(pv()) && /data-user-report="@londonhome"/.test(pv()), '个人主页：关注 / 私信 / 拉黑 / 举报');
  ev("closeProfile()");
  ev("setPage('me')");
  note(/data-dm-strangers="on" aria-pressed="true"/.test(pv()) && /data-dm-strangers="off" aria-pressed="false"/.test(pv()) && /data-demo-dm/.test(pv()), '我的 · 设置：陌生人私信开关 + 演示按钮');
  note(room.includes('function postAuthorHTML(p)') && /prototype-x-style\.html\?page=notifications&amp;dm='\+encodeURIComponent\(h\)/.test(room) && /prototype-x-style\.html\?user='/.test(room), '房间帖子：作者 → 个人主页，「私信」→ 首页原型会话');
  note(/if\(dmTo&&\/\^@\[\\w\.-\]\{1,32\}\$\/\.test\(dmTo\)\)startDM/.test(home) && /if\(msg&&\['dm','notif'\]\.includes\(msg\)\)msgTab=msg;/.test(home), 'URL：&dm=@handle 打开会话、&msg=notif 选通知');
  note(/body\.dm-thread-open \.fab\{display:none !important\}/.test(home) && /\.dm-send\{[^}]*min-height:44px/.test(home) && /\.dm-msg p\{[^}]*font-size:15px;line-height:1\.5/.test(home), '会话：隐藏 +、发送按钮 44px、气泡 15px / 1.5');
  note(/MASTER v2\.(?:[6-9]|\d{2,})/.test(master) && master.includes('### 22.15') && master.includes('DMThread') && /\| 2026-11-11 \| v1\.1 \+ §36\.16 \|/.test(prd) && prd.includes('### 36.16'), 'MASTER ≥ v2.6 §22.15、PRD §36.16 + 变更记录');
  ev("UKCN.reset(); UKCN.state().signedIn=true; reloadFromStore(); msgTab='dm'; dmView=null; setPage('home')");
}

/* ---------------------------------------------- F */
console.log('\n[F] 清理与文档');
note(!room.includes('id="roomForm"') && !/data-act="(save|cancel)-room"/.test(room) && !/\.room-form/.test(room), '房间页旧的就地建房表单 roomForm 已删除');
note(/act === 'create-room'|create-room/.test(room) && room.includes('seg=create'), '房间页建房统一走首页新建房表单');
note(/MASTER v2\.(?:[1-9]|\d{2,})/.test(master) && master.includes('DiscoverChipRow') && master.includes('ListingCard') && master.includes('UnreadDivider') && master.includes('AIKeywordChip'), 'MASTER ≥ v2.1：ListingCard / UnreadDivider / AIKeywordChip');
note(prd.includes('### 36.9') && prd.includes('listing_ext.attrs') && prd.includes('check-h5.js'), 'PRD §36.9 分类信息补充 + 门禁索引');
note(prd.includes('### 36.10') && /\| 2026-11-11 \| v1\.1 \+ §36\.10 \|/.test(prd), 'PRD §36.10 发现页头部瘦身 + 变更记录');

console.log('='.repeat(78));
console.log(fails === 0 ? 'RESULT: v2.1 – v2.6 H5 flow checks pass -> OK' : `RESULT: ${fails} check(s) FAILED -> release blocked`);
process.exit(fails ? 1 : 0);
