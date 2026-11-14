#!/usr/bin/env node
/* UKCN Design System · PRD §27 + §29 / MASTER §15 + §17 gate.
 *
 * Executes prototype-x-style.html v6 inside a lightweight DOM mock and verifies:
 *   - 8 media layouts render (single / grid2 / grid3 / grid4 / portrait / landscape / embed_ph / none)
 *   - two-layer default in-app playback (first-party muted autoplay + third-party consent)
 *   - §17: NO play/mute buttons under the media block; tap the frame itself to pause
 *   - §17: CardJoinButton in the top-right of every card; no FromChannelRow, no in-card region badge
 *   - §17: playback prefs + DSA Art 27 parameters live in the top SettingsPanel (always rendered)
 *   - content-first recommendation, cold start, listing excluded, no iframe in the feed
 *   - static design-system artefacts (tokens / preview / MASTER / PRD)
 *   - every dynamically generated HTML fragment is tag-balanced
 *
 * Exit 1 blocks release. This is a REAL execution gate, not a syntax check.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const PROJECT = path.dirname(ROOT);
const HOME = path.join(PROJECT, 'prototype-x-style.html');
const html = fs.readFileSync(HOME, 'utf8');
const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

let fails = 0;
const note = (ok, label, extra) => {
  if (!ok) fails++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`);
};

const PAIRS = ['div', 'section', 'article', 'main', 'nav', 'aside', 'header',
  'span', 'button', 'label', 'a', 'svg', 'i'];
function balanced(s, sink) {
  const bad = [];
  for (const t of PAIRS) {
    const o = (s.match(new RegExp('<' + t + '(?=[\\s>])', 'g')) || []).length;
    const c = (s.match(new RegExp('</' + t + '>', 'g')) || []).length;
    if (o !== c) bad.push(`${t} ${o}/${c}`);
  }
  if (bad.length) sink.push(bad.join(', '));
  return bad.length === 0;
}

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

console.log('PRD §27 · media layouts / default playback / content-first feed');
console.log('='.repeat(78));

let runOk = true;
try {
  vm.createContext(sandbox);
  vm.runInContext(js, sandbox, { filename: 'prototype-x-style.html', timeout: 5000 });
} catch (e) {
  runOk = false;
  console.log('  RUN_ERROR ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 4).join('\n'));
}
note(runOk, '首页脚本真实执行无未捕获异常');

const feed = () => doc.querySelector('#panel-foryou').innerHTML;
const follow = () => doc.querySelector('#panel-following').innerHTML;
const settings = () => doc.querySelector('#settingsPanel').innerHTML;
const regionBar = () => doc.querySelector('#regionBar').innerHTML;
const cards = () => [...feed().matchAll(/<article class="card"[\s\S]*?<\/article>/g)].map(m => m[0]);
note(feed().length > 2000, '推荐流渲染非空', `${feed().length} chars`);
note(settings().length > 800, '设置浮层内容始终渲染（hidden 仅控可见性）', `${settings().length} chars`);

/* v2.7：推荐流改为「首屏 FOR_YOU_BATCH_SIZE 张 + 下拉加载」。
   先验证分页契约，再在 vm 内把 forYouVisibleCount 展开到全量；
   后续媒体 / 推荐断言仍对完整内容池生效，不降低阈值。 */
const batchSize = vm.runInContext('FOR_YOU_BATCH_SIZE', sandbox);
const firstScreenCards = cards().length;
note(batchSize === 6 && firstScreenCards === batchSize,
     '推荐流首屏分页 6 张', `batch=${batchSize} / cards=${firstScreenCards}`);
note(feed().includes('foryou-post-list') && feed().includes('下拉加载更多动态'),
     '分页容器与「下拉加载更多动态」提示已渲染');
note(vm.runInContext('typeof loadMoreForYou', sandbox) === 'function', '下拉加载函数 loadMoreForYou 存在');
vm.runInContext('forYouVisibleCount = forYouRanked.length; renderForYou();', sandbox);
note(cards().length > firstScreenCards, '展开全量后内容卡多于首屏',
     `${firstScreenCards} → ${cards().length} 张`);

/* ---------------------------------------------------- A. media layouts */
console.log('\n[A] X 式媒体布局');
for (const [cls, label] of [
  ['media--single', '单图'], ['media--grid3', '3 图网格'], ['media--grid4', '4 图网格'],
  ['media--portrait', '竖屏手机视频 9:16'], ['media--landscape', '横屏视频 16:9'],
]) note(feed().includes(cls), `${label} 已渲染`);
note(feed().includes('media--grid2') || html.includes('.media--grid2 '), 'grid2 布局样式已定义');
note(feed().includes('embed-ph'), '第三方播放器静态占位卡已渲染');
note(html.includes('media--none') || html.includes("layout==='none'"), '纯文本 none 分支存在');
for (const token of ['--media-ph-a', '--media-ph-b', '--media-ph-c']) {
  note(html.includes(token), `占位色 token ${token} 已定义`);
}

/* ------------------------------------------- B. two-layer default play */
console.log('\n[B] 默认站内播放（两层）· §17 媒体下方零按钮');
note(settings().includes('默认静音站内播放') && settings().includes('下滑'), '第一方静音自动播说明收在设置面板');
note(feed().includes('data-state="playing"'), '第一方视频默认自动播状态');
note(feed().includes('data-playtoggle=') && feed().includes('role="button"'), '点按媒体本身暂停 / 继续，且可键盘聚焦');
note(!feed().includes('data-media="pause"') && !feed().includes('data-media="mute"') &&
     !feed().includes('class="mbar"'), '媒体下方零播放 / 静音按钮、零工具条');
note(feed().includes('#i-mute'), '静音只是角标指示图标，不是控件');
note(settings().includes('data-playpref="autoplay"') && settings().includes('data-playpref="third"'),
     '播放偏好控件在设置面板，不占帖子区');
note(settings().includes('每次询问') && settings().includes('PECR'), '第三方首次需 PECR 同意');
note(!feed().includes('<iframe'), '推荐流内没有第三方 iframe');
note(feed().includes('不代理、不缓存'), '红线文案（不代理 / 不缓存）');

/* ------------------------------------- C. content-first recommendation */
console.log('\n[C] 内容优先推荐 · 先消费后订阅（§17 右上角加入）');
const cardList = cards();
note(cardList.length >= 8, '推荐流由内容卡构成', `${cardList.length} 张`);
note(cardList.every(c => c.includes('card-head') && c.includes('card-join') && c.includes('data-join=')),
     '每张卡头部右上角都有加入 / 已加入按钮');
note(cardList.every(c => !c.includes('from-row') && !c.includes('感兴趣 · 加入频道')),
     '卡片内不再有 FromChannelRow 独立行');
note(cardList.every(c => !c.includes('rbadge')), '内容卡内无区域徽章（区域只在顶部）');
note(cardList.every(c => /aria-label="(关注|取消关注|加入|退订)频道 [^"]+"/.test(c)),
     '关注按钮 aria-label 写明频道名（用语：频道 = 关注，见 CHANGES.md，可回退为「加入」）');
note(cardList.every(c => c.includes('src-line') && c.includes('查看原文')),
     '每张卡有 SourceLine（来源 / 许可 / 原文回链）');
note(cardList.every(c => c.includes('aria-label="举报"')), '举报入口常驻');
/* v1.9：顶部标签由「我的区域」改为「当前国家」（国家单选，Rio 2026-11-11 拍板） */
note(regionBar().includes('当前国家') && regionBar().includes('英国'), '区域只在顶部区域栏表达');
/* v2.7：推荐流不再混排独立频道推荐卡（频道发现交给频道目录 / 发现页）。
   保留「内容优先、频道发现入口不丢」的意图，按新 IA 改写。 */
note(!feed().includes('rec-chan') && doc.querySelector('#panel-add').innerHTML.includes('国际频道') &&
     html.includes('data-page="discover"'),
     '推荐流纯内容卡；频道发现由频道目录 / 发现页承担');
note(!feed().includes('Zone 2 合租单间'), '分类信息 listing 不进推荐流');
note(settings().includes('DSA Art 27') && settings().includes('0.40'),
     '推荐主要参数与相对重要性在设置面板披露');
/* DSA Art 27：推荐界面要能直接切到时间序。v2.7 由推荐流提示 + 顶部「正在关注」Tab 共同满足。 */
note(feed().includes('时间序') && html.includes('data-tab="following"'),
     '非画像时间序选项从推荐界面可达（提示 + 正在关注 Tab）');
note(settings().includes('0.30'), '区域匹配权重可见（设置面板）');

/* -------------------------------------------------- D. static artefacts */
console.log('\n[D] 设计规范交付物');
const tokens = fs.readFileSync(path.join(ROOT, 'tokens.css'), 'utf8');
const preview = fs.readFileSync(path.join(ROOT, 'preview.html'), 'utf8');
const master = fs.readFileSync(path.join(ROOT, 'MASTER.md'), 'utf8');
const prd = fs.readFileSync(path.join(PROJECT, 'PRD-UK-Chinese-Local-Community-v1.1.md'), 'utf8');
note(tokens.includes('--media-ph-a') && tokens.includes('Canonical Tokens v1.2'), 'tokens.css 同步媒体占位色');
note(preview.includes('id="s10"') && preview.includes("['s10'"), '展示页第 10 节与目录项');
note(preview.includes('id="s12"') && preview.includes("['s12'"), '展示页第 12 节（首屏精简）与目录项');
/* 版本号用区间而非字面量：MASTER 会随新增章节继续升版，§15 + §17 同时存在即视为规范未回退 */
note(master.includes('## 15. 媒体布局') && master.includes('## 17. 首屏精简') &&
     /MASTER v(?:1\.(?:[4-9]|[1-9]\d)|[2-9]\.\d+)/.test(master), 'MASTER §15 / §17 与版本 ≥v1.4');
note(prd.includes('## 27. 媒体布局') && prd.includes('CREATE TYPE media_layout') && prd.includes('## 29.'),
     'PRD §27 与 §29');
note(master.includes('check-media.js') && prd.includes('check-media.js'), '两处发布门禁索引已同步');
note(preview.includes('CardJoinButton') && preview.includes('SettingsPanel'),
     '展示页含右上角加入与设置浮层示例');
note(!/data-media="(?:pause|mute)"/.test(html), '原型源码内不含底部播放 / 静音控件');

/* ------------------------------------------------------- E. interaction */
const KEYS = {
  '.tab': 'tab', '[data-goto]': 'goto', '[data-playpref]': 'playpref',
  '[data-cold]': 'cold', '[data-playtoggle]': 'playtoggle', '[data-settings]': 'settings',
  '[data-embed]': 'embed', '[data-join]': 'join', '[data-pack]': 'pack',
  '[data-rmregion]': 'rmregion', '[data-cluster]': 'cluster', '[data-save]': 'save',
};
function click(attrs) {
  const target = {
    closest(sel) {
      const key = KEYS[sel];
      if (!key || !(key in attrs)) return null;
      const val = attrs[key];
      const store = typeof val === 'object' ? Object.assign({}, val) : { [key]: val };
      return {
        dataset: store,
        getAttribute: n => (n in store ? store[n] : null),
        setAttribute: (n, v) => { store[n] = String(v); },
        classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
        textContent: '', innerHTML: '',
      };
    },
  };
  (handlers.click || []).forEach(fn => fn({ target, preventDefault() {} }));
}

console.log('\n[E] 交互状态机');
const before = generated.length;
click({ settings: '1' });
note(!doc.querySelector('#settingsPanel').classList.contains('hidden'), '齿轮一次点击展开设置浮层');
click({ playpref: 'autoplay' });
note(settings().includes('第一方自动播 关'), '关闭第一方自动播生效');
click({ playpref: 'autoplay' });
note(settings().includes('第一方自动播 开'), '恢复第一方自动播生效');
click({ playpref: 'third' });
note(settings().includes('第三方 默认站内播放'), '第三方持久偏好开启');
click({ embed: { embed: '官方短片：eVisa 账户绑定演示（GOV.UK 公开）', embedAct: 'play' } });
note(feed().includes('eplayer') && !feed().includes('econsent'), '有持久偏好时第三方直接站内播放');
click({ playtoggle: '唐人街新春舞獅｜手機直拍 42 秒' });
note(feed().includes('data-state="paused"'), '点按媒体本身改变播放状态（无按钮）');
click({ join: 'events' });
note(feed().includes('class="card-join joined"'), '先消费后订阅：右上角加入来源频道生效');
click({ cold: '1' });
note(feed().includes('冷启动演示') && feed().includes('card-join') && cards().length >= 1,
     '冷启动 0 订阅首屏仍有内容卡', `${cards().length} 张`);
note(follow().length < 400, '冷启动后「正在关注」为空态提示');

let dynOk = true;
const bad = [];
for (const g of generated) if (!balanced(g.html, bad)) dynOk = false;
note(dynOk, '动态 HTML 标签平衡', bad.length ? bad.slice(0, 3).join(' | ') : `${generated.length} 片段`);
note(generated.length > before, '交互触发重渲染', `${before} → ${generated.length} 片段`);

console.log('\n' + '='.repeat(78));
console.log(fails === 0 ? 'RESULT: §27 media checks pass -> OK' : `RESULT: ${fails} check(s) FAILED -> release blocked`);
process.exit(fails === 0 ? 0 : 1);
