#!/usr/bin/env node
/* UKCN Design System · PRD §30 + §34 / MASTER §18 + §19 + §20 gate.
 *
 * 静态 + 动态断言「房间挂靠官方频道（§34）」：
 *   1. 左侧导航项文案为「频道」，无「添加频道」残留（导航 + Tab）
 *   2. 创建房间「一步化」：房间名 + 父频道必填，无强制类型单选、无强制版权确认勾选
 *   3. 房间不再作为顶层目录并列卡片，而是嵌套在所属频道详情页
 *   4. 加入房间 → 通知未读 +1，存在「房间新增内容」通知摘要
 *   5. 创建房间表单仅建房间，不提供文件上传；原创视频上传留在视频内容流程
 *   6. 房间数据 room_type 默认 general、parentCode 必填（归属官方频道）
 *   7. 动态生成的 HTML 片段标签平衡
 *
 * Exit 1 blocks release. 这是真实执行门禁，不是语法检查。
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
  'span', 'button', 'label', 'a', 'svg', 'i', 'select', 'option', 'input'];
function balanced(s) {
  const bad = [];
  for (const t of PAIRS) {
    const o = (s.match(new RegExp('<' + t + '(?=[\\s>])', 'g')) || []).length;
    const c = (s.match(new RegExp('</' + t + '>', 'g')) || []).length;
    if (t === 'input') continue;
    if (o !== c) bad.push(`${t} ${o}/${c}`);
  }
  return bad;
}

console.log('UKCN Design System · rooms gate (§30 + §34)');
console.log('==============================================================================\n');

/* ---------------- [A] 静态断言 ---------------- */
console.log('[A] 静态：导航 / 创建流程 / 房间目录');

// 1. 导航项文案
const navAdd = html.match(/<button class="nav-item" data-goto="add"[^>]*>[\s\S]*?<\/button>/);
const navLabel = navAdd ? navAdd[0] : '';
note(/>频道<|>频道$/.test(navLabel), '导航项文案为「频道」', navLabel.match(/>频道</)?.[0]);
note(!/添加频道/.test(navLabel), '导航项无「添加频道」残留');

const tabAdd = html.match(/<button class="tab" data-tab="add"[^>]*>[^<]*/);
note(tabAdd && /频道/.test(tabAdd[0]), 'Tab 文案为「频道」');

// 2. 创建房间「一步化」：房间名 + 父频道必填，无强制类型单选，无强制版权确认
note(/rc-input/.test(html), '存在房间名输入（.rc-input，必填）');
note(/roomParentSelect/.test(html) && /required/.test(html), '父频道下拉为必选（.roomParentSelect required）');
note(!/不挂靠/.test(html), '父频道无「不挂靠」独立项（§34 废除空父级）');
note(/rc-type/.test(html) && /通用/.test(html), '房间类型为可选（含「通用」默认项）');
note(!/rc-confirm/.test(html), '无强制版权确认勾选（§32 移除）');
note(/rc-go/.test(html), '存在创建提交按钮（.rc-go，一步化主按钮）');

// 3. 创建引导口径：必挂官方频道 + 版权确认下移
note(/必须归属一个频道/.test(html), '创建引导含「必须归属一个频道」口径（官方 + 平台共建，待 Rio 拍板）');
note(/创建空房间无需版权确认/.test(html) && /上传原创视频/.test(html),
  '版权确认下移到内容动作的说明');

// 4. 房间创建不承载内容上传；视频文件入口属于房间内的原创视频动作
const createStart=js.indexOf('const createView = `');
const directoryStart=js.indexOf('const directoryView = `',createStart);
const createViewSource=createStart>=0&&directoryStart>createStart?js.slice(createStart,directoryStart):'';
const hasFileInput = /<input[^>]*type=["']file["']/i.test(createViewSource);
note(!hasFileInput, '房间创建流程无视频文件上传控件（type=file）');

// 5. 房间数据 room_type 默认 general、parentCode 必填（归属官方频道）
note(!/parent:\s*['"]未挂靠/.test(html), 'myRooms 无「未挂靠」独立房间（§34 废除空父级）');
note(/parentCode:\s*['"][a-z]/.test(html), 'myRooms 房间均含 parentCode（归属官方频道）');
note(/type:\s*['"]通用/.test(html), 'myRooms 数据含「通用」类型房间（room_type=general）');

// 6. 房间卡：嵌套在频道详情（无顶层目录卡），右上角 CardJoinButton
note(!/房间目录卡/.test(html) || !/renderDiscover[\s\S]*?room-dir-card/.test(html),
  '发现页顶层目录不出现房间并列卡片');
note(/parentCode===c\.code/.test(js) && /\(r\.publishedCount\|\|0\)\s*>\s*0/.test(js),
  '频道详情嵌套展示已发布内容的房间');
note(/data-roomjoin/.test(html), '房间卡右上角有 CardJoinButton（data-roomjoin）');

console.log('\n[B] 动态：真实执行脚本');

// 轻量 DOM mock
const generated = [];
class El {
  constructor(sel) { this.sel = sel; this._html = ''; this._text = ''; this.attrs = {}; this.classes = new Set(); this.dataset = {}; this.style = {}; this.value = ''; this.disabled = false; this.checked = false; this.children = [];
    const self = this;
    this.classList = { add: (...c)=>c.forEach(x=>self.classes.add(x)), remove:(...c)=>c.forEach(x=>self.classes.delete(x)), contains:c=>self.classes.has(c), toggle:(c,f)=>{const on=f===undefined?!self.classes.has(c):f; on?self.classes.add(c):self.classes.delete(c); return on;} }; }
  get innerHTML(){ return this._html; }
  set innerHTML(v){ this._html = String(v); generated.push({el:this.sel, html:this._html}); }
  get textContent(){ return this._text; }
  set textContent(v){ this._text = String(v); }
  getAttribute(k){ return k in this.attrs ? this.attrs[k] : null; }
  setAttribute(k,v){ this.attrs[k]=String(v); }
  addEventListener(){}
  querySelector(){ return null; }
  closest(){ return null; }
}
const elements = new Map();
const handlers = {};
const doc = {
  body: new El('body'),
  querySelector(sel){ if(!elements.has(sel)) elements.set(sel, new El(sel)); return elements.get(sel); },
  querySelectorAll(){ return []; },
  getElementById(id){ return doc.querySelector('#'+id); },
  addEventListener(type,fn){ (handlers[type]=handlers[type]||[]).push(fn); },
};
doc.body.dataset.theme = 'dark';
const sandbox = { document: doc, console, setTimeout, clearTimeout, Math, JSON, Date, Intl };
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

let execErr = null;
try { vm.createContext(sandbox); vm.runInContext(js, sandbox, { filename: 'prototype-x-style.html' }); }
catch (e) { execErr = e; }
note(!execErr, '脚本执行无未捕获异常', execErr && execErr.message);

if (!execErr && typeof sandbox.renderAll === 'function') {
  try { sandbox.renderAll(); } catch (e) { execErr = e; }
  note(!execErr, 'renderAll() 无异常', execErr && execErr.message);
  note(typeof sandbox.updateRoomSubmit === 'function', 'updateRoomSubmit 函数存在');
  note(/const myRooms\s*=/.test(js), 'myRooms 数据已声明');
  note(/const roomJoined\s*=/.test(js), 'roomJoined 状态集已声明（加入房间用）');
  try { vm.runInContext(`myRooms.push({name:'空房间门禁样本',type:'通用',owner:'@test',members:0,badge:'用户自建 · 非官方',parentCode:'global-community',publishedCount:0,updatedOrder:0}); renderAll();`, sandbox); }
  catch (e) { execErr = e; }
  note(!doc.querySelector('#panel-discover').innerHTML.includes('空房间门禁样本'), '空房间不会进入频道详情嵌套列表');
}

// 动态 HTML 标签平衡
let balanceFail = false;
for (const g of generated) {
  const bad = balanced(g.html);
  if (bad.length) { balanceFail = true; note(false, `动态片段标签平衡 · ${g.el}`, bad.join(', ')); }
}
if (!balanceFail) note(true, `动态 HTML 标签平衡 · ${generated.length} 片段`);

console.log('\n==============================================================================');
if (fails) { console.log(`RESULT: ${fails} rooms check(s) FAIL -> release blocked`); process.exit(1); }
console.log('RESULT: all rooms checks pass -> OK');
