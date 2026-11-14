#!/usr/bin/env node
/* UKCN Design System · UI gate.
 *
 * Does two things (syntax checks alone are NOT acceptance):
 *   A. Static checks on all three HTML deliverables: script syntax, tag balance,
 *      SVG symbol references, label-for/id pairing, a11y tokens.
 *   B. Real execution of preview.html inside a lightweight DOM mock: verifies the
 *      main view renders, theme switch / embed state machine / tabs / checkbox
 *      all work, and that every dynamically generated HTML fragment is balanced.
 *
 * Exit code 1 on any failure -> release blocked.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const ROOT = __dirname;
const PROJECT = path.dirname(ROOT);
const FILES = [
  path.join(ROOT, 'preview.html'),
  path.join(PROJECT, 'prototype-x-style.html'),
  path.join(PROJECT, 'prototype-collection-room.html'),
  path.join(PROJECT, 'publish-content.html'),
];

let failures = 0;
const note = (ok, label, extra) => {
  if (!ok) failures++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`);
};
const warn = (label, extra) => console.log(`  WARN     ${label}${extra ? ' · ' + extra : ''}`);

/* ---------------------------------------------------------------- helpers */
function stripBlocks(html) {
  return html
    .replace(/<style\b[\s\S]*?<\/style>/gi, '')
    .replace(/<script\b[\s\S]*?<\/script>/gi, '')
    .replace(/<svg class="sprite"[\s\S]*?<\/svg>/gi, '');
}
const PAIRS = ['div', 'section', 'article', 'main', 'nav', 'aside', 'header',
  'table', 'tbody', 'thead', 'tr', 'td', 'th', 'span', 'button', 'label', 'a', 'svg', 'i'];
function balance(html, label, sink) {
  const bad = [];
  for (const t of PAIRS) {
    const open = (html.match(new RegExp('<' + t + '(?=[\\s>])', 'g')) || []).length;
    const close = (html.match(new RegExp('</' + t + '>', 'g')) || []).length;
    if (open !== close) bad.push(`${t} ${open}/${close}`);
  }
  sink.push({ label, bad });
  return bad.length === 0;
}
function scripts(html) {
  return [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
}

/* ------------------------------------------------------- A. static checks */
console.log('UKCN Design System · UI gate');
console.log('='.repeat(78));
const balanceSink = [];
for (const f of FILES) {
  const name = path.basename(f);
  const html = fs.readFileSync(f, 'utf8');
  console.log(`\n[static] ${name}`);

  const js = scripts(html);
  let syntaxOk = true;
  try { new vm.Script(js, { filename: name }); } catch (e) { syntaxOk = false; console.log('    ' + e.message); }
  note(syntaxOk, '脚本语法');

  const layout = stripBlocks(html);
  const layoutOk = balance(layout, name + ' (layout)', balanceSink);
  note(layoutOk, '静态 HTML 标签平衡', balanceSink[balanceSink.length - 1].bad.join(', '));

  const symbols = new Set([...html.matchAll(/<symbol id="(i-[\w-]+)"/g)].map(m => m[1]));
  const refs = new Set([...html.matchAll(/#(i-[\w-]+)/g)].map(m => m[1]));
  const missing = [...refs].filter(r => !symbols.has(r));
  note(missing.length === 0, 'SVG symbol 引用', missing.length ? '缺失 ' + missing.join(',') : `${symbols.size} symbols`);

  const labels = [...html.matchAll(/<label[^>]*\sfor="([^"]+)"/g)].map(m => m[1]);
  const ids = new Set([...html.matchAll(/\sid="([^"]+)"/g)].map(m => m[1]));
  const orphan = labels.filter(l => !ids.has(l));
  note(orphan.length === 0, 'label for ↔ id', orphan.length ? '缺失 ' + orphan.join(',') : `${labels.length} 组`);

  const defined = new Set([...html.matchAll(/(--[\w-]+)\s*:/g)].map(m => m[1]));
  const used = new Set([...html.matchAll(/var\(\s*(--[\w-]+)/g)].map(m => m[1]));
  const undef = [...used].filter(t => !defined.has(t));
  note(undef.length === 0, 'CSS 变量均有定义', undef.length ? '未定义 ' + undef.join(', ') : `${used.size} 个引用`);

  note(html.includes(':focus-visible'), ':focus-visible 存在');
  note(html.includes('prefers-reduced-motion'), 'prefers-reduced-motion 存在');
  note(/min-height:\s*44px|min-height:var\(--tap\)/.test(html), '44px 触控目标');
  note(html.includes('width=device-width'), 'viewport meta');
  const external = /<script[^>]+src=|<link[^>]+stylesheet|@import\s|url\(\s*['"]?https?:/i.test(html);
  note(!external, '零外部资源依赖');

  const emoji = ['⌂', '＋', '⌕', '♡', '▤', '◉', '◐', '▯'].filter(c => html.includes(c));
  if (emoji.length) warn('Unicode 图标残留（MASTER §11 P1 迁移项）', emoji.join(' '));
}

const homePrototype = fs.readFileSync(path.join(PROJECT, 'prototype-x-style.html'), 'utf8');
note(/function homeComposerHTML\(\)[\s\S]*?class="compose home-composer"/.test(homePrototype), '首页含内联发帖编辑器');
note(/id="homeComposerBody"[^>]*maxlength="2000"/.test(homePrototype), '首页编辑区支持 2000 字正文');
/* v2.0（PRD §36.8）：手机端发帖只走 + FAB，内嵌发帖框只在桌面端可见 */
note(/@media\(max-width:760px\)\{[^]*?\.home-composer\{display:none\}[^]*?\n\}/.test(homePrototype) && /body\.preview-mobile \.home-composer\{display:none\}/.test(homePrototype),
     '手机断点与移动预览隐藏内嵌发帖框（桌面保留）');
note(/id="homeComposerDestination"/.test(homePrototype), '首页可选择个人动态或自己的频道');
note(['text','video','topic','info'].every(type => new RegExp("\\['" + type + "'").test(homePrototype)), '首页支持图文、视频、话题与信息类型');
note(/id="homeComposerImageInput"/.test(homePrototype) && /id="homeComposerVideoInput"/.test(homePrototype), '首页支持添加图片与原创视频附件');
note(/data-compose-submit/.test(homePrototype), '首页编辑器可直接发布');
note(/if\(publishBtn\)\{[^]*?q\.set\('channel'[^]*?UKCN\.isGuest\(\)\)UKCN\.requireAuth\('发布内容',go\)/.test(homePrototype),
     'FAB 在频道详情预选投稿到该频道，游客先轻注册');
/* v2.0（PRD §36.5）：分类跟随所属频道，建房表单与发帖框只读显示，不提供分类选择 */
note(!/id="homeComposerCategory"[^>]*><option/.test(homePrototype) && !/<select[^>]*id="homeComposerCategory"/.test(homePrototype) &&
     /id="roomCategoryInherit"/.test(homePrototype) && /跟随所属频道，无需选择/.test(homePrototype),
     '建房表单与桌面发帖框的分类只读继承，无分类选择控件');
note(!/name:'全球[^']*'/.test(homePrototype) && /name:'国际华人交流'/.test(homePrototype) && !/group:'全球'/.test(homePrototype),
     '频道名与分组的「全球」已统一为「国际」');

/* v13 · 共享演示数据层：三个页面都走 UKCN（登录门槛 / 审核中 / 举报 / 底部导航） */
const roomPrototype = fs.readFileSync(path.join(PROJECT, 'prototype-collection-room.html'), 'utf8');
const publishPage = fs.readFileSync(path.join(PROJECT, 'publish-content.html'), 'utf8');
note(/<nav class="bottom"[\s\S]*?data-nav-key="me"/.test(homePrototype) && /class="fab"/.test(homePrototype), '首页移动端底栏含「我的」与发布 FAB');
note(/function renderMe\(\)/.test(homePrototype) && /data-me-export/.test(homePrototype) && /data-me-delete/.test(homePrototype), '「我的」页含导出数据与注销入口');
note(/data-demo-reset/.test(homePrototype), '「我的」页含重置演示数据');
note(/UKCN\.requireAuth\(/.test(homePrototype) && /UKCN\.requireAuth\(/.test(roomPrototype) && /UKCN\.requireAuth\(/.test(publishPage), '加入 / 发布 / 评论统一走轻注册门槛');
note(/if\(act==='publish'\)[^]*?UKCN\.isGuest\(\)\) UKCN\.requireAuth\('发布内容', go\)/.test(roomPrototype), '房间页 FAB：游客先轻注册，成员预选当前房间');
/* v2.7（2026-11-12 分类表单）：信息帖分类改由发布者显式选择，不再只读继承目标频道；
   细粒度表单契约由 check-h5.js 覆盖，此处只守住「必选选择器 + 旧只读控件已移除」。 */
note(/id="f-listing-category"/.test(publishPage) && !/class="inherit-cat" id="f-cat"/.test(publishPage) &&
     !/<select class="input" id="f-cat"/.test(publishPage),
     '发布页分类为信息帖必选选择器（不再只读继承目标频道）');
note(/routeChannel/.test(publishPage) && /'channel:' \+ routeChannel\.code/.test(publishPage) && /routeCity/.test(publishPage) && /id="f-rights"/.test(publishPage),
     '发布页承接 FAB 上下文：频道投稿、城市话题、视频原创确认');
note(/UKCN\.addPost\(/.test(publishPage) && !/getItem\('ukcn-publish-posts'/.test(publishPage), '独立发布页写入共享数据层（不再用私有存储）');
note(/id="destSelect"/.test(publishPage) && /routeRoom/.test(publishPage), '独立发布页可选发布到房间并承接 ?room=');
note(/UKCN\.openReport\(/.test(homePrototype) && /UKCN\.openReport\(/.test(roomPrototype) && /UKCN\.openReport\(/.test(publishPage), '三个页面的举报都走统一举报流程');
note(!/id="joinModal"/.test(homePrototype) && !/id="joinModal"/.test(roomPrototype), '旧的加入弹窗已移除（由轻注册替代）');

/* v2.6.1 · 桌面 / 移动端 IA 对齐：收藏与我的房间收进「我的」（CHANGES 第二节落地） */
const leftNavBlock = (homePrototype.match(/<aside class="left">([\s\S]*?)<\/aside>/) || [])[1] || '';
const leftNavItems = [...leftNavBlock.matchAll(/<button class="nav-item[^"]*"[^>]*>/g)];
note(leftNavItems.length === 5 && !/data-page="favorites"|data-page="my-channels"/.test(leftNavBlock),
     '桌面左栏 5 项与底栏一致；收藏 / 我的房间已从主导航收起', leftNavItems.length + ' 项');
note(homePrototype.includes("meSection('收藏'") && homePrototype.includes('data-page="favorites"') && homePrototype.includes("meSection('我的房间'"),
     '「我的」页仍提供收藏与我的房间入口（删左栏不丢功能）');
note(homePrototype.includes('el.dataset.page===key') && homePrototype.includes("key==='channels'&&el.dataset.goto==='add'"),
     '桌面左栏高亮改用与底栏相同的 key 映射');
note(homePrototype.includes("el.setAttribute('aria-current','page')"), '桌面左栏同步 aria-current（选中态可访问）');
note(homePrototype.includes('收藏的内容 ${matches.length} 条') && homePrototype.includes('${TERMS.chFollow}的频道 ${savedChannels.length} 个') && !homePrototype.includes('共 ${count} 项收藏'),
     '收藏页分开计数：收藏的内容 / 关注的频道，不混算为「共 N 项收藏」');
note(!homePrototype.includes('收藏 · 频道'), '旧术语「收藏 · 频道」已清除');
note(homePrototype.includes("'my-channels':'我的房间'") && homePrototype.includes("currentPage==='favorites')") && homePrototype.includes("currentPage==='my-channels')"),
     '收藏 / 我的房间路由保留，深链仍可达');

/* ----------------------------------------------- B. real DOM execution */
console.log('\n[dynamic] preview.html · 真实执行页面脚本与主要交互');

class El {
  constructor(sel) {
    this.sel = sel;
    this._html = '';
    this._text = '';
    this.attrs = {};
    this.classes = new Set();
    this.disabled = false;
    this.checked = false;
    this.value = '';
    this.style = {};
    this.dataset = {};
    const self = this;
    this.classList = {
      add: (...c) => c.forEach(x => self.classes.add(x)),
      remove: (...c) => c.forEach(x => self.classes.delete(x)),
      contains: c => self.classes.has(c),
      toggle: c => { if (self.classes.has(c)) { self.classes.delete(c); return false; } self.classes.add(c); return true; },
    };
  }
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); generated.push({ el: this.sel, html: this._html }); }
  get textContent() { return this._text; }
  set textContent(v) { this._text = String(v); }
  getAttribute(k) { return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k, v) { this.attrs[k] = String(v); }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener() {}
  querySelector(s) { return doc.querySelector(s); }
  closest() { return null; }
  focus() {}
  scrollIntoView() {}
}

const generated = [];
const elements = new Map();
const handlers = {};
const doc = {
  body: new El('body'),
  documentElement: new El('html'),
  querySelector(sel) {
    if (!elements.has(sel)) elements.set(sel, new El(sel));
    return elements.get(sel);
  },
  querySelectorAll() { return []; },
  getElementById(id) { return doc.querySelector('#' + id); },
  createElement(tag) { return new El('<' + tag + '>'); },
  addEventListener(type, fn) { (handlers[type] = handlers[type] || []).push(fn); },
};
doc.body.attrs['data-theme'] = 'dark';

const sandbox = {
  document: doc, window: {}, console,
  setTimeout: () => 1, clearTimeout: () => {},
  CSS: { escape: s => String(s) },
  location: { href: '', hash: '' }, navigator: { userAgent: 'node' },
  Date, Math, JSON, Array, Object, String, Number, Boolean, RegExp, Error,
};
sandbox.globalThis = sandbox;

const html = fs.readFileSync(FILES[0], 'utf8');
const js = scripts(html);
let runOk = true;
try {
  vm.createContext(sandbox);
  vm.runInContext(js, sandbox, { filename: 'preview.html', timeout: 5000 });
} catch (e) {
  runOk = false;
  console.log('  RUN_ERROR ' + e.message);
}
note(runOk, '脚本执行无未捕获异常');

const mainSections = ['#swatches', '#tokenTable tbody', '#typeScale', '#spBars',
  '#radii', '#tagRow', '#stateRow', '#demoTabs', '#checklist', '#sourceList', '#embedSlot', '#tocLinks'];
const rendered = mainSections.filter(s => (doc.querySelector(s).innerHTML || '').length > 40);
note(rendered.length === mainSections.length, '主视图渲染非空',
  `${rendered.length}/${mainSections.length}`);

const initialGenerated = generated.length;
let dynOk = true;
const dynBad = [];
for (const g of generated) {
  if (!balance(g.html, g.el, [])) { dynOk = false; dynBad.push(g.el); }
}
note(dynOk, '动态 HTML 标签平衡', dynBad.length ? dynBad.join(', ') : `${initialGenerated} 片段`);

function click(attrs) {
  const target = {
    closest(sel) {
      const key = sel.replace(/[\[\]]/g, '');
      if (!attrs[key]) return null;
      const store = Object.assign({}, attrs[key]);
      return {
        getAttribute: n => (n in store ? store[n] : null),
        setAttribute: (n, v) => { store[n] = String(v); },
        classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
        dataset: {}, textContent: '', innerHTML: '',
      };
    },
  };
  (handlers.click || []).forEach(fn => fn({ target, preventDefault() {} }));
}

const themeBefore = doc.body.getAttribute('data-theme');
click({ 'data-act': { 'data-act': 'theme', 'aria-pressed': 'true' } });
const themeAfter = doc.body.getAttribute('data-theme');
note(themeBefore === 'dark' && themeAfter === 'light' &&
  doc.querySelector('#swatches').innerHTML.includes('#0a6ba8'),
  '主题切换生效且色板重渲染', `${themeBefore} → ${themeAfter}`);

click({ 'data-embed': { 'data-embed': 'consent' } });
const consentOk = doc.querySelector('#embedSlot').innerHTML.includes('PECR 事前同意');
click({ 'data-embed': { 'data-embed': 'player' } });
const playerOk = doc.querySelector('#embedSlot').innerHTML.includes('模擬官方 iframe');
click({ 'data-embed': { 'data-embed': 'placeholder' } });
const destroyedOk = doc.querySelector('#embedSlot').innerHTML.includes('站內播放');
note(consentOk && playerOk && destroyedOk, 'Embed 状态机（占位→同意→播放→销毁）');

click({ 'data-tab': { 'data-tab': '2' } });
note(doc.querySelector('#tabPanel').textContent.includes('日更新') &&
  doc.querySelector('#demoTabs').innerHTML.includes('aria-selected="true"'),
  'Tab 切换与 aria-selected');

(handlers.change || []).forEach(fn => fn({
  target: { getAttribute: n => n === 'data-role' ? 'confirm' : null, checked: true },
}));
note(doc.querySelector('#submitBtn').disabled === false &&
  doc.querySelector('#submitHint').textContent.includes('可提交'),
  '版权确认勾选启用提交按钮');

click({ 'data-act': { 'data-act': 'mobile', 'aria-pressed': 'false' } });
note(doc.body.classList.contains('preview-mobile'), '420px 移动视图切换');

const finalGenerated = generated.length;
note(finalGenerated > initialGenerated, '交互触发重渲染',
  `${initialGenerated} → ${finalGenerated} 片段`);
let allDynOk = true;
const allDynBad = [];
for (const g of generated) if (!balance(g.html, g.el, [])) { allDynOk = false; allDynBad.push(g.el); }
note(allDynOk, '交互后全量动态 HTML 标签平衡', allDynBad.length ? allDynBad.join(', ') : `${finalGenerated} 片段`);

console.log('\n' + '='.repeat(78));
if (failures) {
  console.log(`RESULT: ${failures} FAILED -> release blocked`);
  process.exit(1);
}
console.log('RESULT: all UI checks pass -> OK');
