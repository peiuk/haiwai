#!/usr/bin/env node
/* UKCN Design System · PRD §28 location & governance gate.
 *
 * Executes prototype-x-style.html inside a lightweight DOM mock and verifies:
 *   - coarse auto-location prompt (source / precision / no GPS permission)
 *   - three-state location machine (prompt -> confirmed/locked -> off -> on -> replay)
 *   - unlaunched-jurisdiction fallback (no official channels, user badges, launch request)
 *   - governance matrix (region/pack/official channel = platform, user channel = user)
 *   - static design-system artefacts (MASTER §16, preview §11, PRD §28 DDL, tokens note)
 *   - no IP literal, no client-side navigator.geolocation, no region.enable write
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
const read = f => fs.readFileSync(f, 'utf8');
const html = read(HOME);
const js = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
const master = read(path.join(ROOT, 'MASTER.md'));
const preview = read(path.join(ROOT, 'preview.html'));
const prd = read(path.join(PROJECT, 'PRD-UK-Chinese-Local-Community-v1.1.md'));
const tokens = read(path.join(ROOT, 'tokens.css'));

let fails = 0;
const note = (ok, label, extra) => {
  if (!ok) fails++;
  console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`);
};
const generated = [];
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

class El {
  constructor(sel) {
    this.sel = sel; this._html = ''; this._text = ''; this.attrs = {};
    this.classes = new Set(); this.dataset = {}; this.style = {}; this.value = '';
    const self = this;
    this.classList = {
      add: (...c) => c.forEach(x => self.classes.add(x)),
      remove: (...c) => c.forEach(x => self.classes.delete(x)),
      contains: c => self.classes.has(c),
      toggle: (c, force) => {
        const on = force === undefined ? !self.classes.has(c) : force;
        on ? self.classes.add(c) : self.classes.delete(c);
        return on;
      },
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

console.log('PRD §28 · auto-location / region-channel governance gate');
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

const locBar = () => doc.querySelector('#locBar').innerHTML;
const regionBar = () => doc.querySelector('#regionBar').innerHTML;
const settings = () => doc.querySelector('#settingsPanel').innerHTML;
const addPanel = () => doc.querySelector('#panel-add').innerHTML;

/* ---------------------------------------------- A. static artefacts */
console.log('\n[A] 规范与文档交付物');
note(master.includes('## 16. 自动定位与开通权限') && master.includes('## 17. 首屏精简') &&
     /* v2.0 起 MASTER 跨主版本，正则同时接受 v1.4+ 与 v2+ */ /MASTER v(?:1\.(?:[4-9]|[1-9]\d)|[2-9]\.\d+)/.test(master), 'MASTER §16 / §17 与版本 ≥v1.4');
note(master.includes('LocationConfirmBar') && master.includes('RegionGovernanceBadge') &&
     master.includes('RegionLaunchCard') && master.includes('ChannelOwnerBadge') &&
     master.includes('RegionSourceNote'), '§16 五个组件规范齐全');
note(master.includes('CardJoinButton') && master.includes('SettingsPanel') && master.includes('SourceLine'),
  '§17 三个取代组件已入规范');
note(master.includes('不新增任何颜色 token'), '§16 明确不新增颜色 token');
note(preview.includes('id="s11"') && preview.includes("['s11','11 自动定位与开通权限']"),
  '展示页第 11 节与目录项');
note(preview.includes('id="s12"') && preview.includes("['s12'"), '展示页第 12 节（首屏精简）与目录项');
note(preview.includes('LocationConfirmBar') && preview.includes('RegionLaunchCard') &&
     preview.includes('SettingsPanel'), '展示页含定位条、开通状态卡与设置浮层活示例');
note(prd.includes('## 28. 自动定位') && prd.includes('### 28.12') && prd.includes('## 29.'),
  'PRD §28 全章与 §29');
note(prd.includes("ALTER TYPE region_source_t ADD VALUE IF NOT EXISTS 'ip_edge'") &&
     prd.includes('chk_signal_detail_shape') &&
     prd.includes('trg_official_channel_requires_launch') &&
     prd.includes('trg_launch_request_unlaunched'), '§28.5 可执行 DDL 与触发器');
note(prd.includes('CREATE TABLE region_resolution_log') &&
     prd.includes('CREATE TABLE region_launch_request'), '§28.5 两张新表');
note(master.includes('check-location.js') && prd.includes('check-location.js'),
  '发布门禁索引已同步到 MASTER / PRD');
note(tokens.includes('§16（自动定位与开通权限）刻意不新增任何 token'),
  'tokens.css 记录「不新增 token」决策');
note(html.includes('id="locBar" aria-live="polite"') && html.includes('role="region"'),
  '定位条 aria-live / role');
note(/\.loc-btn::after\{[^}]*inset:-6px/.test(html) && /\.set-btn\{[^}]*min-height:44px/.test(html),
  '紧凑按钮命中区扩到 44px / 设置按钮 44px');
note(html.includes('id="settingsPanel"') && html.includes('class="settings-panel hidden"'),
  '顶部设置浮层容器（默认收起）');
note(/\.region-bar\{[^}]*min-height:44px/.test(html), '区域栏单行 44px');
note(!/navigator\.geolocation|\.enabled\s*=\s*true/.test(js),
  '客户端不申请 GPS、不写 region.enabled');
note(!/\b(?:\d{1,3}\.){3}\d{1,3}\b/.test(html), '原型内无 IPv4 字面量');
note(!/<script[^>]+src=|<link[^>]+stylesheet/i.test(html), '零外部资源依赖');

/* ---------------------------------------------- B. initial state */
console.log('\n[B] 首次进入 · 粗粒度定位确认');
const views = ['#locBar', '#regionBar', '#settingsPanel', '#panel-foryou', '#panel-following',
  '#panel-add', '#sideChannels', '#trendBox'];
const filled = views.filter(s => (doc.querySelector(s).innerHTML || '').length > 40);
note(filled.length === views.length, '全部视图渲染非空', `${filled.length}/${views.length}`);
note(locBar().includes('根据网络判断你在 英国'), '默认定位到首启法域 UK');
note(locBar().includes('只到国家 / 城市级') && locBar().includes('不申请设备 GPS 权限') &&
     locBar().includes('不存 IP 原文与经纬度'), '明示精度与不采集项');
note(locBar().includes('来源：网络推断（CDN 边缘 IP → 国家）'), '定位来源可见');
note(locBar().includes('不会启用任何法域的官方频道'), '定位与法域启用明确分离');
note(['confirm', 'change', 'off'].every(a => locBar().includes('data-loc="' + a + '"')),
  '三动作：确认 / 手动改 / 关闭定位');
/* v1.9（Rio 2026-11-11 拍板）：国际频道各国共享；开通国家的分类数据彼此隔离；当前国家单选不叠加；未开通国家只显示国际频道。下列断言随定位口径改写 */
note(locBar().includes('已开通 · 有本国分类频道'), '三态徽章：已开通');
note(regionBar().includes('英国') && regionBar().includes('官方已开通'),
  '区域 chip 带开通状态短徽章');
note(addPanel().includes('地区与平台说明') && addPanel().includes('launch-grid') &&
     /区域由平台创建/.test(js), '添加页含开通权限说明与区域开通卡');
note(addPanel().includes('申请开通（仅登记需求）'), '未开法域含需求登记入口');
note(addPanel().includes('不代表该地区官方服务已开通'), '需求登记不伪装成上线');
note(addPanel().includes('owner-tag official') && addPanel().includes('owner-tag user'),
  '频道目录同时标注平台开设 / 用户创建');
note(!html.includes('id="legalBox"') && !/function renderLegal\(/.test(js),
  '首页右栏不渲染长篇定位/法域说明');
note(settings().includes('不会启用任何法域的官方频道') && settings().includes('不存 IP 原文与经纬度'),
  '§17 设置面板复述来源、精度与法域分离（来源说明不丢失）');
note(['change','off','on','replay','sim-jp','sim-uk'].every(a => settings().includes('data-loc="' + a + '"')),
  '§17 详细开关与演示按钮收进设置浮层');
note(!locBar().includes('data-loc="sim-jp"'), '首次定位条不再堆演示按钮');

/* ---------------------------------------------- C. state machine */
const KEYS = {
  '.tab': 'tab', '[data-goto]': 'goto', '[data-playpref]': 'playpref',
  '[data-cold]': 'cold', '[data-playtoggle]': 'playtoggle', '[data-settings]': 'settings',
  '[data-embed]': 'embed', '[data-join]': 'join', '[data-pack]': 'pack',
  '[data-rmregion]': 'rmregion', '[data-cluster]': 'cluster', '[data-save]': 'save',
  '[data-loc]': 'loc', '[data-apply]': 'apply',
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

console.log('\n[C] 定位状态机与未开法域回退');
const before = generated.length;
click({ loc: 'confirm' });
note(locBar().includes('已确认') && locBar().includes('此后不再自动覆盖'),
  '确认后锁定，不再自动覆盖');
note(regionBar().includes('英国'), '确认后默认区域包存在');
/* v2.0（PRD §36.6 允许手动切换国家）：「切换国家」改为打开设置里的国家选择，不再跳到添加频道页 */
click({ loc: 'change' });
note(!doc.querySelector('#settingsPanel').classList.contains('hidden') && settings().includes('id="countryPick"'),
  '「切换国家」打开设置里的手动国家选择');
vm.runInContext('settingsOpen=false; renderAll()', sandbox);
click({ loc: 'off' });
note(locBar().includes('定位已关闭') && locBar().includes('仅显示国际频道'),
  '关闭定位 → 国际频道兜底，绝不空白页');
note(!regionBar().includes('英国'), '关闭定位后移除自动推断的区域');
note(settings().includes('当前 国际') && settings().includes('不会启用任何法域的官方频道'),
  '关闭定位后设置说明回退到国际');
click({ loc: 'on' });
note(locBar().includes('根据网络判断你在'), '重新开启定位回到确认态');
click({ loc: 'sim-jp' });
note(locBar().includes('根据网络判断你在 日本'), '模拟定位到未开法域（日本）');
note(locBar().includes('未开通 · 仅显示国际频道'), '定位条呈现未开通徽章');
note(regionBar().includes('日本') && regionBar().includes('未开通 · 仅国际'),
  '区域 chip 标注未开通 · 仅国际');
note(addPanel().includes('日本 <span class="gov-tag user">未开通 · 仅显示国际频道</span>'),
  '日本区域状态卡为未开通态');
const rows = [...addPanel().matchAll(/<button class="channel-open"[^>]*>([^<]+)<\/button> <span class="owner-tag ([a-z]+)">/g)]
  .map(m => ({ name: m[1], owner: m[2] }));
const unlaunchedRows = rows.filter(r => /东京|多伦多/.test(r.name));
note(unlaunchedRows.length === 0, '未开通国家不显示任何国家频道（只看国际频道）',
  `${unlaunchedRows.length} 行：${unlaunchedRows.map(r => r.name).join(' ')}`);
note(settings().includes('当前 日本') && settings().includes('不会启用任何法域的官方频道'),
  '未开法域治理说明仍在设置中可见');
click({ apply: 'JP' });
note(addPanel().includes('已有 38 人希望开通此地区官方频道'),
  '「申请开通」只增加需求计数');
note(!addPanel().includes('<div class="lc-h">日本 <span class="gov-tag official">'),
  '申请后不产生官方频道 / 不启用法域');
click({ loc: 'sim-uk' });
note(locBar().includes('根据网络判断你在 英国') &&
     regionBar().includes('英国'), '定位回首启法域');
note(settings().includes('当前 英国'), '首启法域状态在设置中更新');
click({ loc: 'replay' });
note(locBar().includes('data-loc="confirm"'), '重放首次进入回到确认态');
click({ pack: 'jp' });
note(!regionBar().includes('日本') && regionBar().includes('英国'),
  '当前国家单选：未开通国家的频道包不能叠加进来');
click({ settings: '1' });
note(!doc.querySelector('#settingsPanel').classList.contains('hidden'),
  '§17 齿轮 / 详情开关一次点击展开设置浮层');

/* ---------------------------------------------- F. 国家数据隔离 + 国际共享（v1.9） */
console.log('\n[F] 国家数据隔离 + 国际频道共享');
{
  const ev = s => vm.runInContext(s, sandbox);
  const UK = new Set(ev("channels.filter(c=>c.region==='UK').map(c=>c.code)"));
  const GL = new Set(ev("channels.filter(c=>c.region==='GLOBAL').map(c=>c.code)"));
  const codesIn = h => [...h.matchAll(/data-channel(?:-detail)?="([^"]+)"/g)].map(m => m[1]);
  const snapshot = () => {
    const disc = ev("discoverDetailCode=null; discoveryScope='all'; discoveryCategoryFilter='all'; searchTerm=''; renderDiscover()");
    /* 只比内容区（标题之后）：地区选项本来就随国家变化 */
    const global = ev("discoveryScope='GLOBAL'; discoveryCategoryFilter='all'; renderDiscover()").split('class="page-heading"')[1] || '';
    const detail = ev("renderChannelDetail(byCode['sport'])");
    const ukDetail = ev("renderChannelDetail(byCode['housing'])");
    const hosts = ev("channels.filter(c=>canHostRooms(c)&&visibleChannel(c)).map(c=>c.code)");
    ev("discoveryScope='auto'");
    return { disc, global, detail, ukDetail, hosts,
      feed: doc.querySelector('#panel-foryou').innerHTML, add: addPanel(),
      following: doc.querySelector('#panel-following').innerHTML };
  };
  ev("subs.add('housing'); subs.add('sport'); saved.clear();");
  click({ loc: 'sim-uk' });
  const uk = snapshot();
  click({ loc: 'sim-jp' });
  const jp = snapshot();
  click({ loc: 'off' });
  const off = snapshot();
  click({ loc: 'sim-uk' });
  const ukLeak = s => codesIn(s).filter(c => UK.has(c));
  note(ukLeak(uk.disc).length > 0 && codesIn(uk.disc).some(c => GL.has(c)), '英国：发现页同时显示国际频道与英国分类');
  note(ukLeak(uk.add).length > 0 && codesIn(uk.add).some(c => GL.has(c)), '英国：频道目录同时列国际频道与英国分类频道');
  for (const [name, s] of [['日本（未开通）', jp], ['定位关闭', off]]) {
    note(ukLeak(s.disc).length === 0 && codesIn(s.disc).some(c => GL.has(c)), name + '：发现页只有国际频道，无英国分类', ukLeak(s.disc).join(','));
    note(ukLeak(s.feed).length === 0, name + '：推荐流无英国分类内容', ukLeak(s.feed).join(','));
    note(ukLeak(s.following).length === 0 && s.following.includes('属于其他国家'), name + '：正在关注不串入英国频道，并提示已暂停的关注');
    note(ukLeak(s.add).length === 0, name + '：频道目录无英国分类频道', ukLeak(s.add).join(','));
    note(s.hosts.every(c => GL.has(c)), name + '：建房可选的所属频道只剩国际频道', s.hosts.join(','));
    note(!s.ukDetail.includes('channel-feed-head') && s.ukDetail.includes('不显示其他国家的分类数据'), name + '：深链打开英国频道被拦下，不泄露内容');
    note(!/data-discovery-scope="UK"/.test(s.disc), name + '：发现页地区选项不含英国');
  }
  note(uk.global === jp.global && jp.global === off.global, '国际频道内容在各国一致（发现 · 国际范围）');
  note(uk.detail === jp.detail, '国际频道详情在各国一致（英超与体育）');
  /* v2.0：允许手动切换当前国家（不必与定位一致） */
  const pick = (value) => (handlers.change || []).forEach(fn => fn({ target: { id: 'countryPick', value, closest: () => null, dataset: {} } }));
  click({ loc: 'sim-jp' });
  note(settings().includes('id="countryPick"') && /<option value="UK"[^>]*>英国 · 已开通/.test(settings()), '设置里有手动切换国家的选择，标明开通状态');
  pick('UK');
  const manual = snapshot();
  note(ev('currentCountry()') === 'UK' && ukLeak(manual.disc).length > 0 && ukLeak(manual.add).length > 0,
       '人在日本也可手动切到英国，看到英国分类');
  note(manual.global === uk.global, '手动切换后国际频道内容不变');
  pick('');
  note(ev('currentCountry()') === '' && ukLeak(snapshot().feed).length === 0, '手动选「不选国家」后只看国际');
  pick('UK');
  note(uk.hosts.some(c => UK.has(c)) && uk.hosts.some(c => GL.has(c)), '英国：建房可选国际频道与英国频道');
}

/* ---------------------------------------------- D. governance invariants */
console.log('\n[D] 治理边界（文档层）');
note(prd.includes('任何请求都不得 UPDATE `region.enabled`'),
  '用户 API 禁止启用法域');
note(prd.includes('区域是官方的合规开关，频道是用户的表达空间'),
  '权限矩阵一句话口径');
note(prd.includes('不得使用官方认证徽章') && prd.includes('不自动进入官方区域包'),
  '用户自建频道四条硬边界');
note(master.includes('定位只决定先给用户看哪个包，不决定哪个法域被启用'),
  '设计系统与 PRD 口径一致');
note(prd.includes('商店地区（Apple ID / Play 账号国）') &&
     prd.includes('不能当「我在哪」'), '商店地区用途纠正已写入');

/* ---------------------------------------------- E. dynamic balance */
console.log('\n[E] 动态渲染与标签平衡');
let dynOk = true;
const bad = [];
for (const g of generated) if (!balanced(g.html, bad)) dynOk = false;
note(dynOk, '动态 HTML 标签平衡', bad.length ? bad.slice(0, 3).join(' | ') : `${generated.length} 片段`);
note(generated.length > before, '交互触发重渲染', `${before} → ${generated.length} 片段`);

console.log('='.repeat(78));
console.log(fails === 0 ? 'RESULT: §28 location & governance checks pass -> OK'
  : `RESULT: ${fails} check(s) FAILED -> release blocked`);
process.exit(fails === 0 ? 0 : 1);
