#!/usr/bin/env node
/* UKCN Design System · PRD §34 发现页内容流 / MASTER §12.2 gate.
 *
 * 静态 + 动态断言「发现 = 看内容，分类 = 作用域」：
 *   1. 主体为作用域内的近期内容卡（cardHTML），不再是频道目录网格
 *   2. 房间投稿不进顶层流；分类信息（norec）不进流；置顶优先 + 时间新鲜度
 *   3. 地区 tab 与分类 pill 在所有 scope 下都渲染，分类只列有内容的类目
 *   4. 分类 / 搜索 / 未开法域 / 旧分类回落 / 空态 各分支真实执行
 *   5. 内容卡带频道来源入口与右上角关注按钮；底部相关频道推荐位 ≤3
 *   6. postAgeMinutes 时间解析与「最近」预览排序正确
 *   7. 动态生成 HTML 标签平衡
 *
 * Exit 1 blocks release. 真实执行门禁，不是语法检查。
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const FILE = path.join(__dirname, '..', 'prototype-x-style.html');
const html = fs.readFileSync(FILE, 'utf8');
const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

let fails = 0;
const note = (ok, label, extra) => {
  if (!ok) fails++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`);
};

const PAIRS = ['div', 'section', 'article', 'main', 'nav', 'aside', 'header',
  'span', 'button', 'label', 'a', 'svg', 'i', 'h2', 'h3', 'p', 'b'];
function balanced(s) {
  const bad = [];
  for (const t of PAIRS) {
    const o = (s.match(new RegExp('<' + t + '(?=[\\s>])', 'g')) || []).length;
    const c = (s.match(new RegExp('</' + t + '>', 'g')) || []).length;
    if (o !== c) bad.push(`${t} ${o}/${c}`);
  }
  return bad;
}

console.log('UKCN Design System · discover gate (§34 内容发现)');
console.log('==============================================================================');

/* ---------------- [A] 静态：发现页内容流契约 ---------------- */
console.log('\n[A] 静态：内容流契约（防止回退成频道目录）');

const fnStart = js.indexOf('function renderDiscover()');
const fnEnd = js.indexOf('function renderChannelDetail(', fnStart);
const discoverSrc = fnStart >= 0 && fnEnd > fnStart ? js.slice(fnStart, fnEnd) : '';
note(discoverSrc.length > 500, 'renderDiscover 函数体可定位', `${discoverSrc.length} 字符`);
note(/matches\.map\(it=>cardHTML\(it,false\)\)/.test(discoverSrc),
  '主体为近期内容卡（cardHTML）而非频道目录网格');
note(!/directoryChannelSections\(/.test(discoverSrc), '发现页不再渲染频道目录卡片列表');
note(/items\.filter\(it=>!it\.norec&&scopeCodes\.has\(it\.ch\)\)/.test(discoverSrc),
  '内容源为 items 且排除分类信息（norec）');
note(!/ROOM_POSTS/.test(discoverSrc), '房间投稿不进顶层发现流（§34 层级）');
note(/\(b\.pinned\?1:0\)-\(a\.pinned\?1:0\)/.test(discoverSrc) &&
     /postAgeMinutes\(a\.time\)-postAgeMinutes\(b\.time\)/.test(discoverSrc),
  '排序为置顶优先 + 时间新鲜度');
note(/不进画像/.test(discoverSrc), '差异化说明含「不进画像」');
note(/data-discovery-category=/.test(discoverSrc) && !/if\(scope!=='all'\)/.test(discoverSrc),
  'scope=all 时分类 pill 仍渲染（分类是作用域，不是主体）');
/* v1.8：术语统一为「频道 = 关注」（首页 TERMS.chFollow，Rio 11-11 确认沿用），推荐位标题接受「加入 / 关注 / TERMS 变量」三种写法 */
note(/slice\(0,3\)/.test(discoverSrc) && /这个范围内你可能还想(?:加入|关注|\$\{TERMS\.chFollow\})/.test(discoverSrc),
  '底部相关频道推荐位，最多 3 个');
note(/data-goto="add"/.test(discoverSrc) && /data-discovery-category="all"/.test(discoverSrc),
  '空态含「看全部内容」与「浏览频道目录」两个可执行下一步');
note(/function postAgeMinutes\(/.test(js), 'postAgeMinutes 为全局函数（时间解析统一）');
note(!/slice\(-1\)\[0\]/.test(js), '「最近」预览不再取数组末位');
note(/sort\(\(a,b\)=>postAgeMinutes\(a\.time\)-postAgeMinutes\(b\.time\)\)\[0\]/.test(js),
  '「最近」按时间新鲜度取最新一条');

/* ---------------- [B] 动态：真实执行各分支 ---------------- */
console.log('\n[B] 动态：真实执行 renderDiscover 各分支');

const generated = [];
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
  set innerHTML(v) { this._html = String(v); generated.push({ el: this.sel, html: this._html }); }
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
  document: doc, console,
  window: { scrollTo() {} },
  setTimeout: () => 1, clearTimeout: () => {},
  CSS: { escape: s => String(s) },
  Date, Math, JSON, Array, Object, String, Number, Boolean, RegExp, Error,
};
sandbox.globalThis = sandbox;

let runErr = null;
try {
  vm.createContext(sandbox);
  vm.runInContext(js, sandbox, { filename: 'prototype-x-style.html', timeout: 5000 });
} catch (e) { runErr = e; }
note(!runErr, '脚本执行无未捕获异常', runErr && runErr.message);

/* 探针在同一 vm context 的全局词法环境里读写 renderDiscover 的状态变量，
 * 与 check-rooms.js 注入 myRooms 的做法一致。全部用 split 计数，避免正则转义。 */
const probe = [
  '(function () {',
  '  var out = {};',
  '  function count(h, needle) { return h.split(needle).length - 1; }',
  '  function cardParts(h) { return h.split(\'<article class="card"\').slice(1); }',
  '  function reset(o) {',
  '    o = o || {};',
  "    discoveryScope = o.scope === undefined ? 'all' : o.scope;",
  "    discoveryCategoryFilter = o.cat === undefined ? 'all' : o.cat;",
  "    searchTerm = o.q || '';",
  "    locStage = o.loc || 'prompt';",
  "    detectedRegion = o.region || 'UK';",
  /* v1.8：访客态改由共享数据层 UKCN 决定（「游客预览」= 真实退出登录），旧的 guestMode 变量已不存在；两种实现都兼容 */
  "    if (typeof guestMode !== 'undefined') guestMode = !!o.guest;",
  "    if (typeof UKCN !== 'undefined') { var st = UKCN.state(); st.signedIn = !o.guest; UKCN.save(); }",
  '    discoverDetailCode = o.detail || null;',
  '  }',
  '  function snap(h) {',
  '    var parts = cardParts(h);',
  '    var seenPlain = false, pinOk = true;',
  '    parts.forEach(function (p) {',
  "      var pinned = p.indexOf('#i-pin') >= 0;",
  '      if (pinned && seenPlain) pinOk = false;',
  '      if (!pinned) seenPlain = true;',
  '    });',
  "    var tail = h.split(/这个范围内你可能还想(?:加入|关注)/)[1] || '';",
  '    return {',
  '      html: h,',
  '      cards: parts.length,',
  '      cats: h.split(\'data-discovery-category="\').slice(1).map(function (s) { return s.split(\'"\')[0]; }),',
  '      scopes: h.split(\'data-discovery-scope="\').slice(1).map(function (s) { return s.split(\'"\')[0]; }),',
  "      heading: (h.split('class=\"page-heading\">')[1] || '').split('<')[0],",
  "      empty: h.indexOf('empty-state') >= 0,",
  "      hasGuest: h.indexOf('访客浏览') >= 0,",
  "      hasPrivacy: h.indexOf('不进画像') >= 0,",
  "      relatedTitle: /这个范围内你可能还想(?:加入|关注)/.test(h),",
  '      relatedLinks: count(tail, \'data-channel-detail="\'),',
  '      pinOrderOk: pinOk,',
  "      allCardsHaveJoin: parts.every(function (p) { return p.indexOf('data-join=') >= 0; }),",
  '      allCardsHaveChannel: parts.every(function (p) {',
  "        return p.indexOf('data-channel-detail=\"') >= 0 || p.indexOf('user-post-name') >= 0;",
  '      })',
  '    };',
  '  }',
  '  function scopeChannelsFor(scope) {',
  '    return channels.filter(function (c) {',
  "      if (c.region === 'GLOBAL') return scope === 'all' || scope === 'GLOBAL';",
  '      var r = byRegion[c.region];',
  '      var j = r && r.jurisdiction;',
  "      return !!j && launchedJurisdictions.has(j) && (scope === 'all' || c.region === scope);",
  '    });',
  '  }',
  '  function postsFor(scope) {',
  '    var codes = {};',
  '    scopeChannelsFor(scope).forEach(function (c) { codes[c.code] = true; });',
  '    return items.filter(function (it) { return !it.norec && !!codes[it.ch]; });',
  '  }',
  '  function cardsMatchCategory(h, cat) {',
  '    return cardParts(h).every(function (p) {',
  "      var code = (p.split('data-channel=\"')[1] || '').split('\"')[0];",
  '      return !!byCode[code] && byCode[code].category === cat;',
  '    });',
  '  }',
  "  var allPosts = postsFor('all');",
  '  out.expect = {',
  '    all: allPosts.length,',
  "    global: postsFor('GLOBAL').length,",
  "    life: allPosts.filter(function (it) { return byCode[it.ch] && byCode[it.ch].category === '生活'; }).length,",
  "    housing: allPosts.filter(function (it) { return byCode[it.ch] && byCode[it.ch].category === '房产'; }).length,",
  '    emptyCats: CHANNEL_CATEGORIES.filter(function (cat) {',
  "      return !allPosts.some(function (it) { return byCode[it.ch] && byCode[it.ch].category === cat; });",
  '    }),',
  "    related: scopeChannelsFor('all').filter(function (c) { return !subs.has(c.code); }).slice(0, 3).length,",
  "    age: [postAgeMinutes('刚刚'), postAgeMinutes('3 小时前'), postAgeMinutes('2 天前'), postAgeMinutes('昨天'), postAgeMinutes('很久以前')]",
  '  };',
  "  reset({ scope: 'all' }); out.all = snap(renderDiscover());",
  "  reset({ scope: 'GLOBAL' }); out.global = snap(renderDiscover());",
  "  reset({ scope: 'all', cat: '生活' }); out.life = snap(renderDiscover());",
  '  out.life.filterAfter = discoveryCategoryFilter;',
  "  out.life.matchCat = cardsMatchCategory(out.life.html, '生活');",
  "  reset({ scope: 'all', cat: '房产' }); out.housing = snap(renderDiscover());",
  '  out.housing.filterAfter = discoveryCategoryFilter;',
  "  reset({ scope: 'all', q: '英超' }); out.search = snap(renderDiscover());",
  "  reset({ scope: 'all', q: 'zzz不存在的关键词zzz' }); out.noResult = snap(renderDiscover());",
  "  reset({ scope: 'all', cat: '生活', q: 'zzz不存在的关键词zzz' }); out.filteredEmpty = snap(renderDiscover());",
  "  reset({ scope: 'JP' }); out.jp = snap(renderDiscover());",
  "  reset({ scope: 'all', detail: 'movie' }); out.detail = snap(renderDiscover());",
  "  reset({ scope: 'all', guest: true }); out.guest = snap(renderDiscover());",
  '  return out;',
  '})()',
].join('\n');

let P = null, probeErr = null;
if (!runErr) {
  try { P = vm.runInContext(probe, sandbox, { filename: 'check-discover.probe', timeout: 5000 }); }
  catch (e) { probeErr = e; }
}
note(!probeErr, 'renderDiscover 全部 10 个分支可真实执行', probeErr && probeErr.message);

if (P) {
  const E = P.expect, A = P.all;
  note(E.age[0] === 0 && E.age[1] === 180 && E.age[2] === 2880 && E.age[3] === 1440 && E.age[4] === 1e6,
    'postAgeMinutes 时间解析（刚刚 / 小时 / 天 / 昨天 / 未知）', E.age.join(','));
  note(E.all > 0, '原型存在可探索的内容', `${E.all} 条`);
  note(A.cards === E.all, '全部地区：内容条数与作用域内数据一致', `${A.cards}/${E.all}`);
  note(A.heading.indexOf('全部内容') >= 0, '全部地区标题为「全部内容」');
  note(A.hasPrivacy && A.html.indexOf('近期更新') >= 0, '差异化说明含「近期更新 · 不进画像」');
  note(A.scopes.indexOf('all') >= 0 && A.scopes.indexOf('GLOBAL') >= 0 &&
       A.scopes.indexOf('UK') >= 0 && A.scopes.indexOf('JP') < 0,
    '地区 tab 只列已开通法域', A.scopes.join(','));
  note(A.cats.indexOf('all') >= 0 && A.cats.length >= 2, 'scope=all 时分类 pill 仍渲染', A.cats.join(','));
  note(A.cats.filter(c => E.emptyCats.indexOf(c) >= 0).length === 0,
    '分类按钮只列有内容类目（点不到空分类）', `空类目: ${E.emptyCats.join(',') || '无'}`);
  note(A.allCardsHaveJoin, '每张内容卡右上角有关注按钮');
  note(A.allCardsHaveChannel, '每张内容卡有「进频道」来源入口');
  note(A.pinOrderOk, '置顶内容排在所有非置顶内容之前');
  note(A.relatedTitle && A.relatedLinks === E.related && A.relatedLinks <= 3,
    '相关频道推荐位 ≤3 且数量与未订阅频道一致', `${A.relatedLinks}/${E.related}`);

  note(P.global.cards === E.global && P.global.cards < E.all,
    '全球范围：作用域收窄生效', `${P.global.cards}/${E.all}`);
  /* v1.9：GLOBAL 层统一称「国际」（Rio 2026-11-11 拍板：国际频道各国共享） */
  note(P.global.heading.indexOf('国际内容') >= 0, '国际范围标题为「国际内容」');

  note(E.life > 0 && P.life.cards === E.life && P.life.cards < E.all,
    '分类筛选生效（生活）', `${P.life.cards}/${E.all}`);
  note(P.life.filterAfter === '生活' && P.life.matchCat, '分类结果内每张卡的频道分类一致');

  if (E.housing === 0) {
    note(P.housing.filterAfter === 'all' && P.housing.cards === E.all,
      '无内容分类自动回落「全部」，避免空列表死局');
  } else {
    note(P.housing.cards === E.housing && P.housing.filterAfter === '房产', '房产分类筛选生效');
  }

  note(P.search.cards > 0 && P.search.cards < E.all && P.search.html.indexOf('英超') >= 0,
    '搜索命中：结果收敛且含关键词', `${P.search.cards} 条`);
  note(P.noResult.cards === 0 && P.noResult.empty &&
       P.noResult.html.indexOf('没有匹配的内容') >= 0 && P.noResult.html.indexOf('data-goto="add"') >= 0,
    '搜索无结果：空态 + 浏览频道目录下一步');
  note(P.filteredEmpty.empty && P.filteredEmpty.html.indexOf('data-discovery-category="all"') >= 0,
    '分类 + 无结果：空态提供「看全部内容」');
  note(P.jp.cards === 0 && P.jp.empty, '未开法域范围不泄露内容，显示空态');
  note(P.detail.html.indexOf('频道动态') >= 0 && P.detail.html.indexOf('用户房间') >= 0,
    '频道详情入口仍可达（未因内容流改造丢失）');
  note(P.guest.hasGuest, '访客模式提示在发现页保留');

  const scenes = {
    all: A, global: P.global, life: P.life, housing: P.housing, search: P.search,
    noResult: P.noResult, filteredEmpty: P.filteredEmpty, jp: P.jp, detail: P.detail, guest: P.guest,
  };
  const bad = [];
  for (const k of Object.keys(scenes)) {
    const b = balanced(scenes[k].html);
    if (b.length) bad.push(`${k}: ${b.join(',')}`);
  }
  note(bad.length === 0, `动态 HTML 标签平衡 · ${Object.keys(scenes).length} 个场景`, bad.slice(0, 2).join(' | '));
  note(generated.length > 0, '初始化阶段触发了视图渲染', `${generated.length} 片段`);
}

console.log('\n==============================================================================');
if (fails) { console.log(`RESULT: ${fails} discover check(s) FAIL -> release blocked`); process.exit(1); }
console.log('RESULT: all discover checks pass -> OK');
