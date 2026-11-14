#!/usr/bin/env node
/* UKCN Design System · 演示流程闸门（v13）
 * 验证三个原型页共用的一份演示数据（shared/ukcn-shared.js）能跑通：
 *   登录 → 创建房间 → 发帖 → 审核中 → 模拟审核通过 → 房间可见 → 其他用户加入 → 收到通知 → 重置
 * 并验证「正在关注」排序（置顶在前，其余严格按时间倒序）。
 * 用法：node design-system/check-flow.js */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { execFileSync } = require('child_process');

const ROOT = __dirname;
const PROJECT = path.dirname(ROOT);
let failures = 0;
const note = (ok, label, extra) => { if (!ok) failures++; console.log(`  ${ok ? 'PASS' : 'FAIL'}     ${label}${extra ? ' · ' + extra : ''}`); };

console.log('UKCN Design System · demo flow gate');
console.log('='.repeat(78));

/* A. 内联副本一致 */
console.log('\n[shared] 三个页面的共享层副本');
let syncOk = true;
try { execFileSync(process.execPath, [path.join(ROOT, 'sync-shared.js'), '--check'], { stdio: 'pipe' }); } catch (e) { syncOk = false; }
note(syncOk, '内联副本与 shared/ukcn-shared.js 一致（node design-system/sync-shared.js 可修复）');

/* B. 数据层语义（假 localStorage，两个上下文模拟跨页面） */
console.log('\n[store] 演示数据层');
const src = fs.readFileSync(path.join(PROJECT, 'shared', 'ukcn-shared.js'), 'utf8');
const mem = {};
const localStorage = { getItem: k => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); }, removeItem: k => { delete mem[k]; } };
function page() {
  const ctx = { window: { localStorage }, console, Date, Math, JSON, Object, Array, String, Number, setTimeout: () => 1, clearTimeout: () => {} };
  vm.createContext(ctx);
  vm.runInContext(src + '\n;this.UKCN = UKCN;', ctx, { filename: 'ukcn-shared.js' });
  return ctx.UKCN;
}
const A = page();
A.reset();
note(A.me() && A.me().handle === '@pei', '重置后为演示账号 @pei（已登录）');
note(A.unread() === 3, '种子通知 3 条未读', String(A.unread()));
A.logout();
note(A.isGuest() && A.unread() === 0, '退出后为游客，未读不计');
let called = false;
note(A.requireAuth('加入房间', () => { called = true; }) === false && !called, '游客触发登录门槛，不直接执行动作');
A.reset();
const room = A.createRoom({ name: '测试房间 · 剧集', type: 'series', parentCode: 'housing', parentName: '英国租房', isPublic: false });
note(room && room.owner === '@pei' && A.ownedRooms().length === 1, '创建房间归属当前账号');
note(A.state().roomsJoined.includes('测试房间 · 剧集'), '创建者自动加入房间');
note(room.type === 'series', '房间类型保留（剧集不会变成通用）', room.type);
const post = A.addPost({ dest: 'room', roomId: room.id, roomName: room.name, text: '第一条内容' });
note(post && post.status === 'pending', '新帖进入审核中');
const B = page(); /* 另一个页面读取同一份数据 */
note(B.postsFor(p => p.roomId === room.id).length === 1, '跨页面可读到同一条帖子（共享 localStorage）');
note(B.visiblePost(B.postsFor()[0]), '作者本人可见审核中内容');
const before = A.unread();
note(A.approve(post.id) === 1, '模拟审核通过 1 条');
const C = page();
const st = C.state();
note(st.posts[0].status === 'published', '审核通过后状态为已公开');
note(C.findRoom(room.id).publishedCount === 1, '房间公开内容计数 +1');
note(C.unread() === before + 1 && /通过审核/.test(st.notifications[0].title), '收到审核通过通知');
const members = C.findRoom(room.id).members;
C.simulateJoin(room.id);
const D = page();
note(D.findRoom(room.id).members === members + 1, '模拟其他用户加入，成员 +1');
note(/加入了你的房间/.test(D.state().notifications[0].title), '房主收到成员加入通知');
D.setFailNext(true);
note(page().consumeFail() === true && page().consumeFail() === false, '模拟网络错误只生效一次');
const exp = JSON.parse(D.exportData());
note(exp.rooms.length === 1 && exp.posts.length === 1, '导出数据含本人房间与帖子');
D.deleteAccount();
note(page().isGuest() && page().ownedRooms().length === 0, '注销后清除本人房间并回到游客');
/* v1.9：当前国家单选，存在共享数据里；国家频道下的房间只在该国可见，国际频道下的房间各国可见 */
const P = page();
P.reset();
note(P.country() === 'UK' && P.countryLaunched() && !P.countryLaunched('JP'), '种子当前国家为英国（已开通），日本未开通');
P.setCountry('JP');
note(page().country() === 'JP' && !page().regionVisible('UK') && page().regionVisible('GLOBAL'), '切到日本：英国房间不可见，国际房间可见（跨页面一致）');
P.setCountry('');
note(page().country() === '' && !page().regionVisible('UK') && page().regionVisible('GLOBAL'), '未定位：只看国际');
P.setChannelRegions({ housing: 'UK', movie: 'GLOBAL' });
note(page().roomRegion({ parentCode: 'housing' }) === 'UK' && page().roomRegion({ parentCode: 'movie' }) === 'GLOBAL' &&
     page().roomRegion({ parentCode: 'x', region: 'UK' }) === 'UK' && page().roomRegion({}) === 'GLOBAL',
     '房间法域跟随所属频道（频道映射由主页写入共享层）');
P.setCountry('UK');
note(page().regionVisible('UK') && page().regionVisible('GLOBAL') && !page().regionVisible('JP'), '英国：英国 + 国际可见，其他国家不可见');
page().reset();
note(page().state().rooms.length === 0 && page().me().handle === '@pei' && page().country() === 'UK', '重置演示数据恢复种子');

/* C. 正在关注：置顶在前，其余严格按时间倒序 */
console.log('\n[home] 正在关注排序');
const home = fs.readFileSync(path.join(PROJECT, 'prototype-x-style.html'), 'utf8');
const fl = (home.match(/function followingList\(\)\{[\s\S]*?\n\}/) || [''])[0];
const pa = (home.match(/function postAgeMinutes\(value\)\{[\s\S]*?\n\}/) || [''])[0];
note(!!fl && !!pa, '找到 followingList / postAgeMinutes');
if (fl && pa) {
  const ctx = { visibleChannel: () => true, byCode: {}, subs: new Set(['a', 'b']), items: [
    { id: 1, ch: 'a', time: '3 小时' }, { id: 2, ch: 'b', time: '5 分钟' }, { id: 3, ch: 'c', time: '刚刚' },
    { id: 4, ch: 'a', time: '2 天', pinned: true }, { id: 5, ch: 'b', time: '昨天' }, { id: 6, ch: 'a', time: '刚刚' }] };
  vm.createContext(ctx);
  vm.runInContext(pa + '\n' + fl + '\nthis.out = followingList().map(i => i.id).join(",");', ctx);
  note(ctx.out === '4,6,2,1,5', '置顶在前 + 时间倒序 + 只含已关注频道', ctx.out);
}
note(/(const|let) roomDraft\s*=/.test(home) && /let addSeg\s*=/.test(home), '创建房间草稿与目录分段保存在状态里（重渲染不丢）');

console.log('\n' + '='.repeat(78));
console.log(failures ? `RESULT: ${failures} FAILED -> release blocked` : 'RESULT: demo flow checks pass -> OK');
process.exit(failures ? 1 : 0);
