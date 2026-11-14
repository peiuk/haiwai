#!/usr/bin/env node
/* UKCN Design System · global-region home prototype gate.
 * Executes prototype-x-style.html inside a lightweight DOM mock and verifies
 * region packs, channel-graph recommendations, jurisdiction notices and
 * dynamic HTML balance. Exit 1 blocks release. */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const FILE = path.join(__dirname, '..', 'prototype-x-style.html');
const html = fs.readFileSync(FILE, 'utf8');
const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');

let fails = 0;
const note = (ok, label, extra) => { if (!ok) fails++; console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`); };
const generated = [];
const PAIRS = ['div', 'section', 'article', 'main', 'nav', 'aside', 'header', 'span', 'button', 'label', 'a', 'svg', 'i'];
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

console.log('Global-region home prototype · real execution gate');
console.log('='.repeat(78));
let runOk = true;
try {
  vm.createContext(sandbox);
  vm.runInContext(js, sandbox, { filename: 'prototype-x-style.html', timeout: 5000 });
} catch (e) { runOk = false; console.log('  RUN_ERROR ' + e.message + '\n' + (e.stack || '').split('\n').slice(0, 4).join('\n')); }
note(runOk, '脚本执行无未捕获异常');

const views = ['#locBar', '#regionBar', '#settingsPanel', '#panel-foryou', '#panel-following',
  '#panel-add', '#sideChannels', '#trendBox'];
const filled = views.filter(s => (doc.querySelector(s).innerHTML || '').length > 40);
note(filled.length === views.length, '全部视图渲染非空', `${filled.length}/${views.length}`);
const feed = () => doc.querySelector('#panel-foryou').innerHTML;
const cards = () => [...feed().matchAll(/<article class="card"[\s\S]*?<\/article>/g)].map(m => m[0]);
const settings = () => doc.querySelector('#settingsPanel').innerHTML;
const regionBar = () => doc.querySelector('#regionBar').innerHTML;
note(regionBar().includes('英国'), '默认区域包为英国');
/* v2.7：推荐流首屏 6 张 + 下拉加载。先验证分页，再展开全量，
   让下方区域隔离 / 频道归属断言继续覆盖完整内容池，不降阈值。 */
const batchSize = vm.runInContext('FOR_YOU_BATCH_SIZE', sandbox);
const firstScreenCards = cards().length;
note(batchSize === 6 && firstScreenCards === batchSize,
     '推荐流首屏分页 6 张', `batch=${batchSize} / cards=${firstScreenCards}`);
note(feed().includes('foryou-post-list') && feed().includes('下拉加载更多动态'),
     '分页容器与加载提示已渲染');
vm.runInContext('forYouVisibleCount = forYouRanked.length; renderForYou();', sandbox);
note(cards().length > firstScreenCards, '展开全量后内容卡多于首屏',
     `${firstScreenCards} → ${cards().length} 张`);
/* v1.9（Rio 2026-11-11 拍板）：国际频道各国共享；开通国家的分类数据彼此隔离；当前国家单选不叠加；未开通国家只显示国际频道。下列断言随定位口径改写 */
note(doc.querySelector('#panel-add').innerHTML.includes('英国频道包') && doc.querySelector('#panel-add').innerHTML.includes('国际频道') &&
     !doc.querySelector('#panel-add').innerHTML.includes('东京频道包'), '频道包只列国际 + 当前国家（不列未开通国家）');
note(feed().includes('频道数据'), '推荐理由为频道数据口径（收在头部 why-dot）');
/* v2.7：频道图谱推荐卡不再混排进推荐流，频道发现由目录页承担；
   此处守住「内容卡为主 + 目录仍列出国际 / 当前国家频道包」。 */
note(!feed().includes('rec-chan') && doc.querySelector('#panel-add').innerHTML.includes('国际频道') &&
     doc.querySelector('#panel-add').innerHTML.includes('英国频道包'),
     '推荐流以内容卡为主，频道发现仍由频道目录承担');
note(feed().includes('card-join') && !feed().includes('from-row') &&
     cards().every(c => c.includes('card-head') && c.includes('data-join=')),
     '§17 加入按钮固定在每张卡右上角，卡片内无 FromChannelRow');
note(cards().every(c => !c.includes('rbadge')), '§17 内容卡内无区域徽章（区域只在顶部区域栏）');
note(regionBar().includes('官方已开通') && regionBar().includes('当前国家'),
     '§17 区域与开通状态只在顶部区域栏表达');
note(!feed().includes('data-media="pause"') && !feed().includes('class="mbar"'),
     '§17 媒体下方零播放 / 静音按钮');
note(settings().includes('默认静音站内播放') && !feed().includes('<iframe'),
     '§27 两层默认站内播放（说明收在设置面板），推荐流无 iframe');
note(settings().includes('DSA Art 27') && settings().length > 800,
     '§17 播放偏好与 DSA 参数收进顶部设置浮层且始终渲染');
note(settings().includes('不会启用任何法域的官方频道') &&
     doc.querySelector('#panel-add').innerHTML.includes('launch-grid'),
     '定位治理说明留在设置与地区目录，不占首页右栏');

const KEYS = {
  '.tab': 'tab', '[data-goto]': 'goto', '[data-embed]': 'embed', '[data-join]': 'join',
  '[data-pack]': 'pack', '[data-rmregion]': 'rmregion', '[data-cluster]': 'cluster', '[data-save]': 'save',
  '[data-settings]': 'settings', '[data-playtoggle]': 'playtoggle',
  '[data-playpref]': 'playpref', '[data-cold]': 'cold', '[data-loc]': 'loc',
};
function click(attrs) {
  const target = {
    closest(sel) {
      const key = KEYS[sel];
      if (!key || !(key in attrs)) return null;
      const val = attrs[key];
      const store = typeof val === 'object' ? val : { [key]: val };
      return {
        dataset: Object.assign({}, store),
        getAttribute: n => (n in store ? store[n] : null),
        setAttribute: (n, v) => { store[n] = String(v); },
        classList: { add() {}, remove() {}, toggle() { return false; }, contains() { return false; } },
        textContent: '', innerHTML: '',
      };
    },
  };
  (handlers.click || []).forEach(fn => fn({ target, preventDefault() {} }));
}

const before = generated.length;
/* v1.9（Rio 2026-11-11 拍板）：国际频道各国共享；开通国家的分类数据彼此隔离；当前国家单选不叠加；未开通国家只显示国际频道。下列断言随定位口径改写 */
const ev = s => vm.runInContext(s, sandbox);
const UK_CODES = new Set(ev("channels.filter(c=>c.region==='UK').map(c=>c.code)"));
const GL_CODES = new Set(ev("channels.filter(c=>c.region==='GLOBAL').map(c=>c.code)"));
const cardCodes = h => [...h.matchAll(/<article class="card"[\s\S]*?<\/article>/g)]
  .map(m => (m[0].match(/data-channel="([^"]+)"/) || [])[1]).filter(Boolean);
const feedCodes = () => cardCodes(feed());
click({ pack: 'jp' });
note(!regionBar().includes('东京') && !doc.querySelector('#panel-add').innerHTML.includes('东京落地'),
     '未开通国家的频道包不能加入，不串入目录与区域栏');
click({ join: 'sport' });
note(doc.querySelector('#panel-following').innerHTML.includes('英超'), '单独关注国际频道生效');
note(feedCodes().some(c => UK_CODES.has(c)) && feedCodes().some(c => GL_CODES.has(c)),
     '英国下：推荐流同时有国际频道与英国分类频道内容');
click({ loc: 'sim-jp' });
note(regionBar().includes('日本') && !regionBar().includes('英国'), '切换国家为单选：切到日本后英国不再是当前国家');
note(feedCodes().length > 0 && feedCodes().every(c => GL_CODES.has(c) || c === 'my-profile'),
     '未开通国家：推荐流只剩国际频道内容（无英国分类）', feedCodes().filter(c => !GL_CODES.has(c)).join(','));
note(cardCodes(doc.querySelector('#panel-following').innerHTML).every(c => !UK_CODES.has(c)) &&
     doc.querySelector('#panel-following').innerHTML.includes('英超'),
     '未开通国家：正在关注不串入英国频道，国际频道照常显示');
note(!doc.querySelector('#trendBox').innerHTML.includes('eVisa'), '未开通国家：趋势不显示英国话题');
click({ loc: 'sim-uk' });
note(regionBar().includes('英国') && feedCodes().some(c => UK_CODES.has(c)), '切回英国：英国分类恢复显示');
click({ rmregion: 'UK' });
note(!regionBar().includes('英国') && feedCodes().every(c => GL_CODES.has(c) || c === 'my-profile'),
     '离开当前国家后只看国际频道');
click({ tab: 'add' });
note(doc.querySelector('#panel-foryou').classList.contains('hidden'), 'Tab 切换生效');
click({ embed: { embed: 'x', embedAct: 'play' } });
click({ save: '测试收藏' });
click({ pack: 'uk' });
note(!doc.querySelector('#regionBar').innerHTML.includes('英国') &&
     settings().includes('不会启用任何法域的官方频道'), '离开首启国家后首页保持通用治理说明');

let dynOk = true;
const bad = [];
for (const g of generated) if (!balanced(g.html, bad)) dynOk = false;
note(dynOk, '动态 HTML 标签平衡', bad.length ? bad.slice(0, 3).join(' | ') : `${generated.length} 片段`);
note(generated.length > before, '交互触发重渲染', `${before} → ${generated.length} 片段`);

console.log('='.repeat(78));
console.log(fails === 0 ? 'RESULT: global prototype checks pass -> OK' : `RESULT: ${fails} check(s) FAILED`);
process.exit(fails === 0 ? 0 : 1);
