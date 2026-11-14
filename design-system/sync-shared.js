#!/usr/bin/env node
/* 把 shared/ukcn-shared.js 内联进三个原型页（零外部资源依赖：不用 <script src>）。
 *   node design-system/sync-shared.js          写入
 *   node design-system/sync-shared.js --check  只校验，副本不一致则退出 1 */
const fs = require('fs');
const path = require('path');
const PROJECT = path.dirname(__dirname);
const SRC = path.join(PROJECT, 'shared', 'ukcn-shared.js');
const PAGES = ['prototype-x-style.html', 'prototype-collection-room.html', 'publish-content.html'];
const check = process.argv.includes('--check');
/* 源文件按 LF 保存；写入时跟随每个页面自己的换行符（Rio 的 Windows 副本里首页是 CRLF） */
const sourceLF = fs.readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n').trim();
const BEGIN = '/* UKCN-SHARED:BEGIN', END = '/* UKCN-SHARED:END */';
let bad = 0;
for (const page of PAGES) {
  const file = path.join(PROJECT, page);
  let html = fs.readFileSync(file, 'utf8');
  const eol = /\r\n/.test(html) ? '\r\n' : '\n';
  const source = sourceLF.replace(/\n/g, eol);
  const b = html.indexOf(BEGIN), e = html.indexOf(END);
  let next;
  if (b >= 0 && e > b) next = html.slice(0, b) + source + html.slice(e + END.length);
  else {
    const at = html.indexOf('<script>');
    if (at < 0) { console.log('  FAIL     ' + page + ' · 找不到 <script> 插入点'); bad++; continue; }
    next = html.slice(0, at) + '<script>' + eol + source + eol + '</script>' + eol + html.slice(at);
  }
  const same = next === html;
  if (check) { console.log(`  ${same ? 'PASS' : 'FAIL'}     ${page} · 共享层副本与 shared/ukcn-shared.js 一致`); if (!same) bad++; }
  else { if (!same) fs.writeFileSync(file, next); console.log(`  ${same ? 'same' : 'sync'}     ${page}`); }
}
process.exit(bad ? 1 : 0);
