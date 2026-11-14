/* UKCN-SHARED:BEGIN
 * 海外圈演示共享层 v1 · 源文件 shared/ukcn-shared.js
 * 三个原型页（首页 / 房间 / 发布）内联同一份副本：运行 node design-system/sync-shared.js 同步，勿直接改内联副本。
 * 职责：一份 localStorage 演示数据（账号 / 订阅 / 房间 / 帖子 / 通知 / 举报）+ 轻注册弹窗 + 举报面板 + 通用对话框。
 * 无后端：所有「审核」「其他用户加入」都由演示按钮模拟。 */
var UKCN = (function(){
  'use strict';
  var KEY = 'ukcn.demo.v1', VERSION = 1;
  var LEGACY_KEYS = ['cnchannels.savedChannels', 'ukcn-publish-posts'];
  var memory = null;
  var DEMO_CODE = '246810';
  var TONES = ['a', 'b', 'c', 'd', 'e', 'f'];
  var OTHER_USERS = ['@lily_ldn', '@chen_uk', '@amy.l', '@ukmax', '@xiaoyu', '@harbourkid'];

  function hasDoc(){ return typeof document !== 'undefined' && document && typeof document.querySelector === 'function'; }
  function storage(){
    try { var w = (typeof window !== 'undefined') ? window : null; return w && w.localStorage ? w.localStorage : null; }
    catch (e) { return null; }
  }
  function now(){ return Date.now(); }
  function uid(p){ return (p || 'id') + '-' + now().toString(36) + Math.floor(Math.random() * 1e4).toString(36); }
  function esc(s){ return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  function seed(){
    var t = now();
    return {
      v: VERSION, createdAt: t, signedIn: true,
      user: { id: 'u-pei', handle: '@pei', name: '裴总', avatar: '裴', tone: 'a', contact: '+44 7700 900123',
        contactType: 'phone', lang: 'zh-Hans', city: '伦敦', joinedAt: t - 30 * 864e5 },
      subs: ['visa', 'arrival', 'housing', 'jobs', 'market'],
      roomsJoined: ['新闻女王 追更房间'],
      saved: [], mutedRooms: [],
      rooms: [], posts: [], reports: [], consents: [], contactViews: [],
      listingsClosed: {}, contactDaily: { date: '', count: 0 }, browseCountry: '',
      notifications: [
        { id: 'n1', kind: 'room', title: '房间新增 3 条内容', body: '新闻女王 · 追更房间', ts: t - 12 * 6e4, unread: true, room: '新闻女王 追更房间' },
        { id: 'n2', kind: 'reply', title: '房间收到新留言', body: '伦敦新手问答 · 关于 GP 注册的讨论有新回复', ts: t - 36e5, unread: true, room: '伦敦新手问答' },
        { id: 'n3', kind: 'system', title: '欢迎来到海外圈', body: '关注频道后，可在「正在关注」按时间查看最新内容。', ts: t - 864e5, unread: true }
      ],
      /* v1.9 三层模型：country = 当前国家（单选，由定位或手动切换决定，不叠加）。
       * 国际频道（region=GLOBAL）各国共享；国家频道与房间只在同一国家内可见。'' = 未定位 / 未开通，只看国际频道 */
      country: 'UK',
      /* v2.1：界面简繁偏好（游客）与「正在关注」上次看到的时间 */
      prefLang: 'zh-Hans', lastSeen: { following: t - 150 * 6e4 },
      /* v2.3：房间帖子默认不进频道动态；房主对单条帖子「推到频道」后才出现在所属频道详情（key = 帖子 id）。示例：英国租房看房互助房的房主推过 1 条 */
      pushes: { 'rp-r6-1': { key: 'rp-r6-1', roomId: 'r6', roomName: '英国租房看房互助房', parentCode: 'housing', by: '@londonhome', ts: t - 30 * 6e4, source: 'seed' } },
      /* v2.6 站内信（PRD §36.16）：只存在本机演示数据里，真实投递需要后端。
       * status：active = 正常会话；request = 陌生人第一次发来、待我接受（接受前不能回复，对方看不到我是否已读）。
       * v1 只支持文字与图片，不做已读回执、不做语音 */
      dms: [
        { id: 'dm-manling', peer: { handle: '@manling', name: '曼玲', tone: 'c' }, status: 'active', unread: 1, ts: t - 25 * 6e4,
          messages: [
            { id: 'm1', from: 'me', kind: 'text', text: '曼玲你好，新闻女王第二季什么时候开始追更？', ts: t - 3 * 36e5 },
            { id: 'm2', from: 'peer', kind: 'text', text: '这周六晚上开始～房间里我置顶了时间表，到时候一起讨论。', ts: t - 25 * 6e4 }
          ] },
        { id: 'dm-londonhome', peer: { handle: '@londonhome', name: '伦敦看房互助', tone: 'b' }, status: 'active', unread: 0, ts: t - 26 * 36e5,
          messages: [
            { id: 'm3', from: 'peer', kind: 'text', text: '你问的 Zone 2 那套，我上周看过，客厅采光不错。', ts: t - 27 * 36e5 },
            { id: 'm4', from: 'peer', kind: 'image', src: '', alt: '客厅照片（演示占位）', ts: t - 27 * 36e5 + 6e4 },
            { id: 'm5', from: 'me', kind: 'text', text: '谢谢！押金是几周的？', ts: t - 26 * 36e5 }
          ] },
        { id: 'dm-req-lily', peer: { handle: '@lily_newcomer', name: '莉莉', tone: 'e' }, status: 'request', unread: 1, ts: t - 40 * 6e4,
          messages: [ { id: 'm6', from: 'peer', kind: 'text', text: '你好！看到你在英国租房频道的帖子，想问下押金一般是几周房租？', ts: t - 40 * 6e4 } ] },
        { id: 'dm-req-sofa', peer: { handle: '@sofa_deals', name: '二手家具小铺', tone: 'f' }, status: 'request', unread: 1, ts: t - 5 * 36e5,
          messages: [ { id: 'm7', from: 'peer', kind: 'text', text: '你好，我们有全新沙发清仓，私信领优惠码～', ts: t - 5 * 36e5 } ] }
      ],
      follows: ['@manling', '@londonhome'], blocked: [], dmPrefs: { allowStrangers: true },
      demo: { failNext: false },
      /* v2.7 帖子详情评论（X 式模态下的快速回复）：title -> [{id,by,handle,time,color,text}]，本机持久化 */
      postComments: {}
    };
  }
  function load(){
    if (memory) return memory;
    var ls = storage(), parsed = null;
    if (ls) { try { parsed = JSON.parse(ls.getItem(KEY) || 'null'); } catch (e) { parsed = null; } }
    memory = (parsed && parsed.v === VERSION) ? parsed : seed();
    var base = seed();
    Object.keys(base).forEach(function(k){ if (memory[k] === undefined) memory[k] = base[k]; });
    if (!parsed) save();
    return memory;
  }
  function save(){
    var ls = storage(); if (!ls || !memory) return;
    try { ls.setItem(KEY, JSON.stringify(memory)); }
    catch (e) {
      /* 配额不足：丢掉帖子里的大图，保留文字 */
      try { memory.posts.forEach(function(p){ if (p.images && p.images.length) { p.imageCount = p.images.length; p.images = []; } }); ls.setItem(KEY, JSON.stringify(memory)); } catch (e2) {}
    }
  }
  function reset(){
    memory = seed();
    var ls = storage();
    if (ls) { try { LEGACY_KEYS.forEach(function(k){ ls.removeItem(k); }); } catch (e) {} }
    save();
    return memory;
  }
  function state(){ return load(); }
  function me(){ var s = load(); return s.signedIn && s.user ? s.user : null; }
  function isGuest(){ return !me(); }
  /* ---------- 国家（v1.9）：国家频道数据彼此隔离，国际频道共享 ---------- */
  var LAUNCHED = ['UK'];                       /* 已开通国家（法域），与首页 launchedJurisdictions 一致 */
  var COUNTRY_NAMES = { UK: '英国', JP: '日本', CA: '加拿大', GLOBAL: '国际' };
  function country(){ var c = load().country; return typeof c === 'string' ? c : 'UK'; }
  function setCountry(code){ var s = load(); s.country = (code && code !== 'GLOBAL') ? String(code) : ''; save(); return s.country; }
  function countryLaunched(code){ return LAUNCHED.indexOf(code === undefined ? country() : code) >= 0; }
  function countryName(code){ return COUNTRY_NAMES[code] || code || '国际'; }
  /* 房间可见：挂在国际频道下（或旧数据没记 region）各国都可见；挂在国家频道下只在该国家（且已开通）可见 */
  function regionVisible(region){ return !region || region === 'GLOBAL' || (region === country() && countryLaunched(region)); }
  /* 频道 → 法域映射由主页写入，房间页 / 发布页据此判断房间属于国际还是某国（v1.9） */
  function setChannelRegions(map){ var s = load(); s.channelRegions = map || {}; save(); }
  function channelRegion(code){ var m = load().channelRegions || {}; return m[code] || ''; }
  function roomRegion(r){ return (r && (r.region || channelRegion(r.parentCode || r.parent))) || 'GLOBAL'; }
  /* 频道 → 名称 / 官方分类，同样由主页写入（v2.0：分类跟随所属频道，用户不单独选择） */
  function setChannelInfo(map){ var s = load(); s.channelInfo = map || {}; save(); }
  function channelInfo(code){ var m = load().channelInfo || {}; return m[code] || null; }
  function channelCategory(code){ var i = channelInfo(code); return (i && i.category) || ''; }
  function roomCategory(r){ return (r && (r.category || channelCategory(r.parentCode || r.parent))) || ''; }
  function ago(ts){
    var d = Math.max(0, now() - Number(ts || 0)), m = Math.floor(d / 6e4);
    if (m < 1) return '刚刚';
    if (m < 60) return m + ' 分钟前';
    var h = Math.floor(m / 60);
    if (h < 24) return h + ' 小时前';
    if (h < 48) return '昨天';
    return Math.floor(h / 24) + ' 天前';
  }
  function notify(n){
    var s = load();
    s.notifications.unshift(Object.assign({ id: uid('n'), ts: now(), unread: true, kind: 'system' }, n));
    if (s.notifications.length > 60) s.notifications.length = 60;
    save();
  }
  function unread(){ return isGuest() ? 0 : load().notifications.filter(function(n){ return n.unread; }).length; }
  function consumeFail(){ var s = load(); if (s.demo && s.demo.failNext) { s.demo.failNext = false; save(); return true; } return false; }
  function setFailNext(on){ load().demo.failNext = !!on; save(); }

  /* ---------- 房间 / 帖子 / 审核 ---------- */
  function findRoom(idOrName){ var s = load(); return s.rooms.filter(function(r){ return r.id === idOrName || r.name === idOrName; })[0] || null; }
  function roomIsPrivate(room){
    if (!room) return false;
    var map = load().roomPrivacy || {};
    return Object.prototype.hasOwnProperty.call(map, room.id) ? !!map[room.id] : !!(room.private || (findRoom(room.id) || {}).private);
  }
  function canViewRoom(room){
    if (!roomIsPrivate(room)) return true;
    var u = me(), s = load();
    return !!(u && (u.handle === room.owner || u.handle === (s.roomOwners || {})[room.id] || (s.roomMembers && (s.roomMembers[room.id] || []).indexOf(u.handle) >= 0)));
  }
  function setRoomPrivate(room, on){
    var u = me(); if (!u || !room || u.handle !== room.owner) return false;
    var s = load(); if (!s.roomPrivacy) s.roomPrivacy = {};
    s.roomPrivacy[room.id] = !!on;
    if (!s.roomOwners) s.roomOwners = {};
    s.roomOwners[room.id] = room.owner;
    var stored = findRoom(room.id); if (stored) stored.private = !!on;
    save(); return true;
  }
  function roomJoinRequested(room){ var u = me(), s = load(); return !!(u && room && (s.roomJoinRequests || []).some(function(r){ return r.roomId === room.id && r.handle === u.handle; })); }
  function requestRoomJoin(room){
    var u = me(), s = load(); if (!u || !room || !roomIsPrivate(room) || canViewRoom(room)) return false;
    if (!s.roomJoinRequests) s.roomJoinRequests = [];
    if (!roomJoinRequested(room)) s.roomJoinRequests.push({ roomId: room.id, handle: u.handle, name: u.name, ts: now() });
    save(); return true;
  }
  function roomRequests(room){ var u = me(); return u && room && u.handle === room.owner ? (load().roomJoinRequests || []).filter(function(r){ return r.roomId === room.id; }) : []; }
  function approveRoomJoin(room, handle){
    var u = me(), s = load(); if (!u || !room || u.handle !== room.owner) return false;
    var i = (s.roomJoinRequests || []).findIndex(function(r){ return r.roomId === room.id && r.handle === handle; });
    if (i < 0) return false;
    s.roomJoinRequests.splice(i, 1);
    if (!s.roomMembers) s.roomMembers = {};
    if (!s.roomMembers[room.id]) s.roomMembers[room.id] = [];
    if (s.roomMembers[room.id].indexOf(handle) < 0) s.roomMembers[room.id].push(handle);
    save(); return true;
  }
  function ownedRooms(){ var u = me(); return u ? load().rooms.filter(function(r){ return r.owner === u.handle; }) : []; }
  function createRoom(r){
    var s = load(), u = me(); if (!u) return null;
    var room = Object.assign({ id: uid('room'), owner: u.handle, ownerName: u.name, members: 1, publishedCount: 0, private: false,
      badge: '用户自建 · 非官方', recent: '刚刚创建', createdAt: now(), updatedOrder: now() }, r);
    s.rooms.unshift(room);
    if (s.roomsJoined.indexOf(room.name) < 0) s.roomsJoined.push(room.name);
    save();
    return room;
  }
  function addPost(p){
    var s = load(), u = me(); if (!u) return null;
    if (p && p.dest === 'room' && roomIsPrivate({ id: p.roomId }) && !canViewRoom(findRoom(p.roomId) || { id: p.roomId })) return null;
    var post = Object.assign({ id: uid('p'), author: u.handle, authorName: u.name, authorTone: u.tone || 'a', ts: now(),
      status: 'pending', dest: 'profile', tags: [], images: [], title: '', text: '' }, p);
    s.posts.unshift(post);
    save();
    return post;
  }
  function postsFor(filter){ return load().posts.filter(filter || function(){ return true; }); }
  function visiblePost(p){ var u = me(); return p.status === 'published' || (u && p.author === u.handle); }
  function approve(id){
    var s = load(), list = s.posts.filter(function(p){ return p.status === 'pending' && (!id || p.id === id); });
    list.forEach(function(p){
      p.status = 'published'; p.publishedAt = now();
      var room = p.roomId ? findRoom(p.roomId) : null;
      if (room) { room.publishedCount = (room.publishedCount || 0) + 1; room.recent = '刚刚更新'; room.updatedOrder = now(); }
      notify({ kind: 'review', title: '帖子已通过审核', body: '「' + String(p.title || p.text).slice(0, 24) + '」已在' + (room ? '房间「' + room.name + '」' : '我的动态') + '公开', room: room ? room.name : '' });
    });
    save();
    return list.length;
  }
  function reject(id){
    var s = load(), list = s.posts.filter(function(p){ return p.status === 'pending' && (!id || p.id === id); });
    list.forEach(function(p){
      p.status = 'rejected'; p.rejectReason = '疑似包含联系方式或站外引流（演示原因）';
      if (s.pushes && s.pushes[p.id]) delete s.pushes[p.id];
      notify({ kind: 'review', title: '帖子未通过审核', body: '「' + String(p.title || p.text).slice(0, 24) + '」' + p.rejectReason + ' · 可修改后重新发布或申诉' });
    });
    save();
    return list.length;
  }
  function deletePost(postId){
    var s = load(), u = me(); if (!u || !postId) return false;
    var idx = -1;
    s.posts.forEach(function(p, i){ if (p.id === postId && p.author === u.handle) idx = i; });
    if (idx < 0) return false;
    s.posts.splice(idx, 1);
    if (s.pushes && s.pushes[postId]) delete s.pushes[postId];
    save();
    return true;
  }
  function roomPostsForFollowing(){
    var s = load(), u = me();
    if (!u) return [];
    var joined = s.roomsJoined || [];
    return s.posts.filter(function(p){
      return p.status === 'published' && p.roomId && joined.indexOf(p.roomName || '') >= 0;
    });
  }
  function closeListing(postId, reason){
    var s = load(), u = me(); if (!u || !postId) return false;
    if (!s.listingsClosed) s.listingsClosed = {};
    s.listingsClosed[String(postId)] = { reason: reason || 'closed', ts: now(), by: u.handle };
    save();
    return true;
  }
  function renewListing(postId){
    var s = load(), u = me(); if (!u || !postId) return false;
    var p = s.posts.filter(function(x){ return x.id === postId; })[0];
    if (p) { p.ts = now(); p.publishedAt = now(); }
    if (s.listingsClosed && s.listingsClosed[String(postId)]) delete s.listingsClosed[String(postId)];
    save();
    return true;
  }
  function isListingClosed(postId){
    var s = load(); return !!(s.listingsClosed && s.listingsClosed[String(postId)]);
  }
  function listingCloseInfo(postId){
    var s = load(); return (s.listingsClosed && s.listingsClosed[String(postId)]) || null;
  }
  function simulateJoin(roomIdOrName){
    var rooms = ownedRooms(); if (!rooms.length) return null;
    var room = (roomIdOrName && findRoom(roomIdOrName)) || rooms[0];
    var who = OTHER_USERS[Math.floor(Math.random() * OTHER_USERS.length)];
    room.members = (room.members || 1) + 1;
    notify({ kind: 'member', title: who + ' 加入了你的房间', body: '「' + room.name + '」现在有 ' + room.members + ' 人', room: room.name });
    save();
    return { room: room, who: who };
  }
  function logout(){ var s = load(); s.signedIn = false; save(); }
  function deleteAccount(){
    var s = load(), u = s.user;
    if (u) {
      s.posts = s.posts.filter(function(p){ return p.author !== u.handle; });
      s.rooms = s.rooms.filter(function(r){ return r.owner !== u.handle; });
    }
    s.user = null; s.signedIn = false; s.subs = []; s.roomsJoined = []; s.saved = []; s.mutedRooms = [];
    s.notifications = []; s.contactViews = [];
    s.dms = []; s.follows = []; s.blocked = []; s.dmPrefs = { allowStrangers: true };
    save();
  }
  function exportData(){
    var s = load(), u = s.user;
    return JSON.stringify({ exportedAt: new Date().toISOString(), note: '演示导出：真实环境 30 天内通过邮件提供下载链接（UK GDPR Art 15 / 20）',
      account: u, consents: s.consents, subs: s.subs, roomsJoined: s.roomsJoined,
      rooms: s.rooms.filter(function(r){ return u && r.owner === u.handle; }),
      posts: s.posts.filter(function(p){ return u && p.author === u.handle; }).map(function(p){ var c = Object.assign({}, p); c.images = (p.images || []).length + ' 张图片（已省略）'; return c; }),
      reports: s.reports, contactViews: s.contactViews,
      dms: (s.dms || []).map(function(d){ return { peer: d.peer.handle, status: d.status, messages: d.messages.map(function(m){ return { from: m.from, kind: m.kind, text: m.text || '', ts: m.ts }; }) }; }),
      follows: s.follows, blocked: s.blocked, dmPrefs: s.dmPrefs }, null, 2);
  }

  /* ---------- 样式（只用 tokens，首次打开弹层时注入） ---------- */
  var CSS = ''
    + '.uks-backdrop{position:fixed;inset:0;z-index:var(--z-modal);background:color-mix(in srgb,var(--text) 38%,transparent);display:flex;align-items:flex-end;justify-content:center;padding:0}'
    + '@media(min-width:761px){.uks-backdrop{align-items:center;padding:24px}}'
    + '.uks-sheet{width:100%;max-width:440px;max-height:92vh;overflow:auto;background:var(--bg);color:var(--text);border:1px solid var(--border);border-radius:var(--r-lg) var(--r-lg) 0 0;box-shadow:var(--shadow);padding:16px 18px 20px;font-size:14px;line-height:1.6}'
    + '@media(min-width:761px){.uks-sheet{border-radius:var(--r-lg)}}'
    + '.uks-head{display:flex;align-items:center;gap:8px;margin-bottom:4px}'
    + '.uks-step{font-size:12px;color:var(--muted);font-weight:600}'
    + '.uks-dots{display:flex;gap:4px;margin-left:4px}.uks-dots i{width:18px;height:4px;border-radius:var(--r-pill);background:var(--border)}.uks-dots i.on{background:var(--accent-strong)}'
    + '.uks-x{margin-left:auto;width:var(--tap);height:var(--tap);border-radius:50%;display:grid;place-items:center;color:var(--muted);background:transparent;border:0;cursor:pointer}'
    + '.uks-x:hover{background:var(--hover);color:var(--text)}'
    + '.uks-x svg,.uks-ico{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}'
    + '.uks-sheet h2{margin:2px 0 4px;font-size:19px;line-height:1.35}'
    + '.uks-sub{margin:0 0 14px;color:var(--muted);font-size:13px}'
    + '.uks-seg{display:flex;gap:6px;margin-bottom:12px}'
    + '.uks-seg button{flex:1;min-height:var(--tap);border-radius:var(--r-pill);border:1px solid var(--line);background:transparent;color:var(--muted);font:inherit;font-weight:700;cursor:pointer}'
    + '.uks-seg button[aria-selected="true"]{background:var(--text);color:var(--bg);border-color:var(--text)}'
    + '.uks-field{margin-bottom:12px}.uks-field label{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;font-weight:600}'
    + '.uks-row{display:flex;gap:8px}'
    + '.uks-lbl{display:block;font-size:12px;color:var(--muted);margin-bottom:4px;font-weight:600}.uks-sheet .hidden{display:none}'
    + '.uks-input{width:100%;min-height:var(--tap);border:1px solid var(--line);border-radius:var(--r-md);background:var(--surface);color:var(--text);font:inherit;font-size:16px;padding:0 12px}'
    + 'textarea.uks-input{min-height:88px;padding:10px 12px;resize:vertical}'
    + '.uks-input:focus{outline:2px solid var(--focus);outline-offset:1px}'
    + '.uks-btn{min-height:var(--tap);padding:0 16px;border-radius:var(--r-pill);border:1px solid var(--line);background:transparent;color:var(--text);font:inherit;font-weight:700;white-space:nowrap;cursor:pointer}'
    + '.uks-btn:hover{background:var(--hover)}'
    + '.uks-btn.primary{background:var(--accent-strong);border-color:var(--accent-strong);color:var(--on-accent)}'
    + '.uks-btn.primary:hover{opacity:.92}'
    + '.uks-btn.danger{color:var(--danger);border-color:var(--danger)}'
    + '.uks-btn[disabled]{opacity:.45;cursor:not-allowed}'
    + '.uks-btn[aria-busy="true"]{opacity:.7;cursor:progress}'
    + '.uks-actions{display:flex;gap:8px;justify-content:flex-end;margin-top:14px;flex-wrap:wrap}'
    + '.uks-actions .uks-btn.primary{flex:1}'
    + '.uks-hint{font-size:12px;color:var(--muted);margin:6px 0 0}'
    + '.uks-hint b{color:var(--text)}'
    + '.uks-err{font-size:13px;color:var(--danger);margin:6px 0 0;min-height:0}'
    + '.uks-err:empty{display:none}'
    + '.uks-check{display:flex;gap:10px;align-items:flex-start;min-height:var(--tap);padding:6px 0;font-size:14px;cursor:pointer}'
    + '.uks-check input{width:20px;height:20px;margin:2px 0 0;flex:none;accent-color:var(--accent-strong)}'
    + '.uks-check small{display:block;color:var(--muted);font-size:12px}'
    + '.uks-link{background:none;border:0;padding:0;color:var(--accent-ink);font:inherit;text-decoration:underline;cursor:pointer}'
    + '.uks-tones{display:flex;gap:8px;flex-wrap:wrap}'
    + '.uks-tone{width:var(--tap);height:var(--tap);border-radius:50%;border:2px solid transparent;display:grid;place-items:center;color:var(--on-accent);font-weight:800;cursor:pointer}'
    + '.uks-tone[aria-checked="true"]{border-color:var(--text);box-shadow:0 0 0 2px var(--bg) inset}'
    + '.uks-av-a{background:var(--accent-strong);color:var(--on-accent)}.uks-av-b{background:var(--good-solid);color:var(--on-good)}.uks-av-c{background:var(--warn);color:var(--bg)}'
    + '.uks-av-d{background:var(--danger);color:var(--bg)}.uks-av-e{background:var(--media-ph-b);color:var(--on-media)}.uks-av-f{background:var(--media-ph-c);color:var(--on-media)}'
    + '.uks-radio{display:flex;gap:10px;align-items:center;min-height:var(--tap);padding:0 12px;border:1px solid var(--border);border-radius:var(--r-md);margin-bottom:6px;cursor:pointer;font-size:14px}'
    + '.uks-radio:has(input:checked){border-color:var(--accent-strong);background:var(--accent-soft)}'
    + '.uks-radio input{width:18px;height:18px;margin:0;accent-color:var(--accent-strong)}'
    + '.uks-done{text-align:center;padding:10px 0 2px}'
    + '.uks-done .uks-badge{width:56px;height:56px;border-radius:50%;margin:0 auto 10px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent-ink)}'
    + '.uks-done .uks-badge svg{width:28px;height:28px}'
    + '.uks-reason{margin:0 0 4px}'
    + '.uks-ticket{display:inline-block;margin-top:6px;padding:2px 10px;border-radius:var(--r-pill);border:1px solid var(--line);font-size:12px;color:var(--muted)}'
    + '.uks-spin{display:inline-block;width:14px;height:14px;margin-right:6px;vertical-align:-2px;border-radius:50%;border:2px solid currentColor;border-right-color:transparent;animation:uksSpin .8s linear infinite}'
    + '@keyframes uksSpin{to{transform:rotate(360deg)}}'
    + '@media(prefers-reduced-motion:reduce){.uks-spin{animation:none}}';

  var CHECK_SVG = '<svg class="uks-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="m5 12 5 5L20 7"/></svg>';
  var CLOSE_SVG = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg>';
  var FLAG_SVG = '<svg class="uks-ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 21V4h11l-1.5 4L16 12H5"/></svg>';

  function ensureStyle(){
    if (!hasDoc() || typeof document.createElement !== 'function' || !document.head) return;
    if (document.getElementById && document.getElementById('uksStyle')) return;
    var st = document.createElement('style'); st.id = 'uksStyle'; st.textContent = CSS; document.head.appendChild(st);
  }

  /* ---------- 通用弹层 ---------- */
  var layer = null, lastFocus = null, onCloseCb = null;
  function closeLayer(){
    if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    layer = null;
    if (typeof document !== 'undefined' && document.removeEventListener) document.removeEventListener('keydown', trapKeys, true);
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) {} }
    var cb = onCloseCb; onCloseCb = null; if (cb) cb();
  }
  function trapKeys(e){
    if (!layer) return;
    if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeLayer(); return; }
    if (e.key !== 'Tab') return;
    var f = Array.prototype.filter.call(layer.querySelectorAll('button,input,select,textarea,a[href]'), function(el){ return !el.disabled && el.offsetParent !== null; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function openLayer(html, onClose){
    if (!hasDoc() || !document.body || typeof document.createElement !== 'function') return null;
    ensureStyle();
    if (layer) { onCloseCb = null; closeLayer(); }
    lastFocus = document.activeElement;
    layer = document.createElement('div');
    layer.className = 'uks-backdrop';
    layer.innerHTML = html;
    layer.addEventListener('click', function(e){ if (e.target === layer) closeLayer(); });
    document.body.appendChild(layer);
    document.addEventListener('keydown', trapKeys, true);
    onCloseCb = onClose || null;
    focusFirst();
    return layer;
  }
  function focusFirst(){
    if (!layer) return;
    var el = layer.querySelector('[data-uks-autofocus]') || layer.querySelector('input,button.primary,button');
    if (el && el.focus) { try { el.focus(); } catch (e) {} }
  }
  function sheet(title, sub, body, stepInfo){
    return '<div class="uks-sheet" role="dialog" aria-modal="true" aria-labelledby="uksTitle">'
      + '<div class="uks-head">' + (stepInfo || '') + '<button type="button" class="uks-x" data-uks-close aria-label="关闭">' + CLOSE_SVG + '</button></div>'
      + '<h2 id="uksTitle">' + esc(title) + '</h2>' + (sub ? '<p class="uks-sub">' + esc(sub) + '</p>' : '')
      + '<div class="uks-body">' + body + '</div></div>';
  }
  function setSheet(title, sub, body, stepInfo){
    if (!layer) return;
    layer.innerHTML = sheet(title, sub, body, stepInfo);
    bindClose();
    focusFirst();
  }
  function bindClose(){
    if (!layer) return;
    Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-close]'), function(b){ b.addEventListener('click', function(){ closeLayer(); }); });
  }
  function q(sel){ return layer ? layer.querySelector(sel) : null; }
  function busy(btn, on, label){
    if (!btn) return;
    if (on) { btn._label = btn.innerHTML; btn.disabled = true; btn.setAttribute('aria-busy', 'true'); btn.innerHTML = '<span class="uks-spin" aria-hidden="true"></span>' + esc(label || '处理中…'); }
    else { btn.disabled = false; btn.removeAttribute('aria-busy'); if (btn._label) btn.innerHTML = btn._label; }
  }
  function toast(msg){
    if (!hasDoc()) return;
    var t = document.querySelector('#toast'); if (!t) return;
    t.textContent = msg; t.classList.add('show');
    clearTimeout(t._uksTimer); t._uksTimer = setTimeout(function(){ t.classList.remove('show'); }, 2200);
  }

  /* ---------- 轻注册 / 登录（3 屏） ---------- */
  function dots(n){ return '<span class="uks-step">第 ' + n + ' / 3 步</span><span class="uks-dots" aria-hidden="true"><i class="' + (n >= 1 ? 'on' : '') + '"></i><i class="' + (n >= 2 ? 'on' : '') + '"></i><i class="' + (n >= 3 ? 'on' : '') + '"></i></span>'; }
  function requireAuth(reason, cb){
    if (me()) { if (cb) cb(); return true; }
    openAuth(reason, cb);
    return false;
  }
  function openAuth(reason, cb){
    var flow = { reason: reason || '继续操作', cb: cb, mode: 'phone', contact: '', sent: false, consent: null };
    if (!openLayer('')) return;
    step1(flow);
  }
  function step1(flow){
    var phone = flow.mode === 'phone';
    setSheet('登录或注册海外圈', '为了' + flow.reason + '，先花 30 秒验证身份。完成后会自动回到这一步。',
      '<div class="uks-seg" role="tablist" aria-label="验证方式">'
      + '<button type="button" role="tab" data-uks-mode="phone" aria-selected="' + phone + '">手机号</button>'
      + '<button type="button" role="tab" data-uks-mode="email" aria-selected="' + (!phone) + '">邮箱</button></div>'
      + '<div class="uks-field"><label for="uksContact">' + (phone ? '英国手机号' : '邮箱地址') + '</label>'
      + '<div class="uks-row"><input class="uks-input" id="uksContact" data-uks-autofocus type="' + (phone ? 'tel' : 'email') + '" autocomplete="' + (phone ? 'tel' : 'email') + '" inputmode="' + (phone ? 'tel' : 'email') + '" placeholder="' + (phone ? '07700 900123' : 'name@example.com') + '" value="' + esc(flow.contact) + '">'
      + '<button type="button" class="uks-btn" data-uks-send>' + (flow.sent ? '重新发送' : '获取验证码') + '</button></div>'
      + '<p class="uks-err" id="uksContactErr" role="alert"></p></div>'
      + '<div class="uks-field' + (flow.sent ? '' : ' hidden') + '" id="uksCodeBox"><label for="uksCode">6 位验证码</label>'
      + '<input class="uks-input" id="uksCode" inputmode="numeric" autocomplete="one-time-code" maxlength="6" placeholder="······">'
      + '<p class="uks-hint">演示验证码 <b>' + DEMO_CODE + '</b>（真实环境通过短信或邮件发送，5 分钟内有效）</p>'
      + '<p class="uks-err" id="uksCodeErr" role="alert"></p></div>'
      + '<div class="uks-actions"><button type="button" class="uks-btn" data-uks-close>稍后再说</button><button type="button" class="uks-btn primary" data-uks-next ' + (flow.sent ? '' : 'disabled') + '>下一步</button></div>',
      dots(1));
    Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-mode]'), function(b){
      b.addEventListener('click', function(){ flow.mode = b.getAttribute('data-uks-mode'); flow.sent = false; flow.contact = ''; step1(flow); });
    });
    var contact = q('#uksContact'), code = q('#uksCode'), next = q('[data-uks-next]');
    function validContact(v){ v = String(v || '').trim(); return flow.mode === 'phone' ? /^(\+44\s?7\d{3}|07\d{3})\s?\d{3}\s?\d{3}$/.test(v) : /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(v); }
    q('[data-uks-send]').addEventListener('click', function(){
      var btn = this, v = contact.value.trim();
      q('#uksContactErr').textContent = '';
      if (!validContact(v)) { q('#uksContactErr').textContent = flow.mode === 'phone' ? '请输入英国手机号，例如 07700 900123' : '邮箱格式不正确'; contact.focus(); return; }
      busy(btn, true, '发送中…');
      setTimeout(function(){
        busy(btn, false);
        if (consumeFail()) { q('#uksContactErr').textContent = '网络不稳定，验证码没有发出，请重试。'; return; }
        flow.contact = v; flow.sent = true;
        q('#uksCodeBox').classList.remove('hidden'); btn.innerHTML = '重新发送';
        next.disabled = false; code.focus();
        toast('验证码已发送（演示：' + DEMO_CODE + '）');
      }, 600);
    });
    contact.addEventListener('keydown', function(e){ if (e.key === 'Enter') { e.preventDefault(); q('[data-uks-send]').click(); } });
    code.addEventListener('keydown', function(e){ if (e.key === 'Enter') { e.preventDefault(); next.click(); } });
    next.addEventListener('click', function(){
      if (code.value.trim() !== DEMO_CODE) { q('#uksCodeErr').textContent = '验证码不正确，请输入 ' + DEMO_CODE + '（演示）'; code.focus(); return; }
      var s = load(), norm = function(x){ return String(x || '').replace(/\s/g, '').replace(/^\+44/, '0'); };
      if (s.user && norm(s.user.contact) === norm(flow.contact)) {
        s.signedIn = true; save();
        finish(flow, '欢迎回来，' + s.user.name);
        return;
      }
      step2(flow);
    });
  }
  function step2(flow){
    setSheet('确认年龄与条款', '首次注册需要你确认以下事项。我们会记录确认时间与条款版本。',
      '<label class="uks-check"><input type="checkbox" id="uksAge" data-uks-req data-uks-autofocus><span>我已年满 18 岁<small>本服务面向 18 岁及以上用户；未满 18 岁暂不支持注册。</small></span></label>'
      + '<label class="uks-check"><input type="checkbox" id="uksTerms" data-uks-req><span>我已阅读并同意 <button type="button" class="uks-link" data-uks-doc="服务条款">服务条款</button> 与 <button type="button" class="uks-link" data-uks-doc="社区规范">社区规范</button></span></label>'
      + '<label class="uks-check"><input type="checkbox" id="uksPrivacy" data-uks-req><span>我已阅读 <button type="button" class="uks-link" data-uks-doc="隐私说明">隐私说明</button><small>手机号 / 邮箱只用于登录与安全验证，不公开、不用于画像。</small></span></label>'
      + '<label class="uks-check"><input type="checkbox" id="uksMkt"><span>接收活动与产品更新（可选）<small>默认不勾选，可随时在「我的 · 设置」关闭。</small></span></label>'
      + '<p class="uks-err" id="uksConsentErr" role="alert"></p>'
      + '<div class="uks-actions"><button type="button" class="uks-btn" data-uks-back>上一步</button><button type="button" class="uks-btn primary" data-uks-next disabled>同意并继续</button></div>',
      dots(2));
    var req = layer.querySelectorAll('[data-uks-req]'), next = q('[data-uks-next]');
    function sync(){ next.disabled = !Array.prototype.every.call(req, function(c){ return c.checked; }); }
    Array.prototype.forEach.call(req, function(c){ c.addEventListener('change', sync); });
    Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-doc]'), function(b){ b.addEventListener('click', function(e){ e.preventDefault(); toast('演示：《' + b.getAttribute('data-uks-doc') + '》全文待法务定稿'); }); });
    q('[data-uks-back]').addEventListener('click', function(){ step1(flow); });
    next.addEventListener('click', function(){
      flow.consent = { ts: now(), version: '2026-11', age18: true, terms: true, privacy: true, marketing: !!q('#uksMkt').checked };
      step3(flow);
    });
  }
  function step3(flow){
    var lang = (typeof navigator !== 'undefined' && /TW|HK|MO|Hant/i.test(navigator.language || '')) ? 'zh-Hant' : 'zh-Hans';
    flow.tone = flow.tone || 'a';
    setSheet('设置你的资料', '昵称和头像会公开显示在你的帖子和房间里，之后可以修改。',
      '<div class="uks-field"><label for="uksName">昵称（2–20 字）</label><input class="uks-input" id="uksName" data-uks-autofocus maxlength="20" placeholder="例如：伦敦小陈"><p class="uks-err" id="uksNameErr" role="alert"></p></div>'
      + '<div class="uks-field"><span class="uks-lbl" id="uksToneLbl">头像颜色</span><div class="uks-tones" role="radiogroup" aria-labelledby="uksToneLbl">'
      + TONES.map(function(t, i){ return '<button type="button" class="uks-tone uks-av-' + t + '" role="radio" aria-checked="' + (t === flow.tone) + '" data-uks-tone="' + t + '" aria-label="头像颜色 ' + (i + 1) + '">' + esc(flow.initial || '我') + '</button>'; }).join('')
      + '</div></div>'
      + '<div class="uks-field" role="radiogroup" aria-label="简繁偏好"><span class="uks-lbl">简繁偏好</span>'
      + '<label class="uks-radio"><input type="radio" name="uksLang" value="zh-Hans" ' + (lang === 'zh-Hans' ? 'checked' : '') + '>简体中文</label>'
      + '<label class="uks-radio"><input type="radio" name="uksLang" value="zh-Hant" ' + (lang === 'zh-Hant' ? 'checked' : '') + '>繁體中文</label></div>'
      + '<div class="uks-actions"><button type="button" class="uks-btn" data-uks-back>上一步</button><button type="button" class="uks-btn primary" data-uks-next>完成注册</button></div>',
      dots(3));
    var name = q('#uksName');
    name.addEventListener('input', function(){
      flow.initial = name.value.trim().charAt(0) || '我';
      Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-tone]'), function(b){ b.textContent = flow.initial; });
    });
    Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-tone]'), function(b){
      b.addEventListener('click', function(){
        flow.tone = b.getAttribute('data-uks-tone');
        Array.prototype.forEach.call(layer.querySelectorAll('[data-uks-tone]'), function(x){ x.setAttribute('aria-checked', String(x === b)); });
      });
    });
    q('[data-uks-back]').addEventListener('click', function(){ step2(flow); });
    q('[data-uks-next]').addEventListener('click', function(){
      var nm = name.value.trim();
      if (nm.length < 2) { q('#uksNameErr').textContent = '昵称至少 2 个字'; name.focus(); return; }
      var langSel = layer.querySelector('input[name="uksLang"]:checked');
      var s = load(), t = now();
      s.user = { id: uid('u'), handle: '@user' + String(t).slice(-4), name: nm, avatar: nm.charAt(0), tone: flow.tone, contact: flow.contact,
        contactType: flow.mode, lang: langSel ? langSel.value : 'zh-Hans', city: '', joinedAt: t };
      s.signedIn = true; s.subs = []; s.roomsJoined = []; s.saved = []; s.mutedRooms = [];
      s.notifications = [{ id: uid('n'), kind: 'system', title: '注册成功，欢迎你 ' + nm, body: '关注几个频道，「正在关注」就会按时间显示它们的更新。', ts: t, unread: true }];
      s.consents.push(Object.assign({ user: s.user.handle }, flow.consent));
      s.prefLang = s.user.lang; s.lastSeen = { following: t };
      save(); applyLang();
      finish(flow, '注册完成，欢迎你 ' + nm);
    });
  }
  function finish(flow, msg){
    var cb = flow.cb;
    onCloseCb = null; closeLayer();
    toast(msg);
    if (cb) cb();
  }

  /* ---------- 举报（选原因 → 提交 → 反馈） ---------- */
  var REASONS = [
    ['scam', '诈骗、虚假信息或可疑交易'], ['harass', '骚扰、仇恨或人身攻击'], ['sexual', '色情内容或未成年人风险'],
    ['ip', '侵犯版权或盗用内容'], ['privacy', '泄露他人隐私（住址、证件、电话）'], ['other', '其他问题']
  ];
  function openReport(target, cb){
    target = target || {};
    if (!openLayer('')) return;
    var label = target.label || '这条内容';
    setSheet('举报' + (target.kindLabel || '内容'), '「' + String(label).slice(0, 40) + '」· 举报不会通知对方。',
      '<div role="radiogroup" aria-label="举报原因">'
      + REASONS.map(function(r, i){ return '<label class="uks-radio"><input type="radio" name="uksReason" value="' + r[0] + '"' + (i === 0 ? ' data-uks-autofocus' : '') + '>' + esc(r[1]) + '</label>'; }).join('')
      + '</div><div class="uks-field hidden" id="uksDetailBox"><label for="uksDetail">补充说明（必填）</label><textarea class="uks-input" id="uksDetail" maxlength="300" placeholder="说明问题所在，方便审核员判断"></textarea></div>'
      + '<p class="uks-err" id="uksReportErr" role="alert"></p>'
      + '<p class="uks-hint">' + (me() ? '可在「我的 · 我的举报」查看处理进度。' : '未登录也可以举报；登录后可查看处理进度。') + ' 违法内容 24 小时内处理（OSA 2023）。</p>'
      + '<div class="uks-actions"><button type="button" class="uks-btn" data-uks-close>取消</button><button type="button" class="uks-btn primary" data-uks-next disabled>提交举报</button></div>',
      '<span class="uks-step">' + FLAG_SVG + '</span>');
    var next = q('[data-uks-next]');
    Array.prototype.forEach.call(layer.querySelectorAll('input[name="uksReason"]'), function(r){
      r.addEventListener('change', function(){ next.disabled = false; q('#uksDetailBox').classList.toggle('hidden', r.value !== 'other'); });
    });
    next.addEventListener('click', function(){
      var picked = layer.querySelector('input[name="uksReason"]:checked'); if (!picked) return;
      var detail = (q('#uksDetail') && q('#uksDetail').value.trim()) || '';
      if (picked.value === 'other' && detail.length < 4) { q('#uksReportErr').textContent = '请补充至少 4 个字的说明'; q('#uksDetail').focus(); return; }
      busy(next, true, '提交中…');
      setTimeout(function(){
        if (consumeFail()) { busy(next, false); q('#uksReportErr').textContent = '提交失败：网络异常。你的选择已保留，请重试。'; return; }
        var ticket = 'R-' + String(now()).slice(-6);
        var reasonText = REASONS.filter(function(r){ return r[0] === picked.value; })[0][1];
        var s = load();
        s.reports.unshift({ id: uid('r'), ticket: ticket, target: label, kind: target.kind || 'post', reason: reasonText, detail: detail, ts: now(), status: '已受理 · 待审核', by: me() ? me().handle : 'guest' });
        save();
        setSheet('已收到你的举报', '',
          '<div class="uks-done"><div class="uks-badge">' + CHECK_SVG + '</div>'
          + '<p class="uks-reason">原因：' + esc(reasonText) + '</p>'
          + '<p class="uks-hint">审核员会尽快处理；违法内容 24 小时内处理，结果会通过通知告诉你。在处理前，你可以屏蔽这条内容。</p>'
          + '<span class="uks-ticket">工单号 ' + esc(ticket) + '</span></div>'
          + '<div class="uks-actions"><button type="button" class="uks-btn primary" data-uks-close data-uks-autofocus>完成</button></div>');
        if (cb) cb(ticket);
      }, 500);
    });
  }

  /* ---------- 通用确认框 ---------- */
  function confirmDialog(opts, onOk){
    if (!openLayer('')) { if (onOk) onOk(); return; }
    setSheet(opts.title || '确认', opts.body || '',
      '<div class="uks-actions"><button type="button" class="uks-btn" data-uks-close data-uks-autofocus>取消</button><button type="button" class="uks-btn ' + (opts.danger ? 'danger' : 'primary') + '" data-uks-ok>' + esc(opts.ok || '确定') + '</button></div>');
    q('[data-uks-ok]').addEventListener('click', function(){ onCloseCb = null; closeLayer(); if (onOk) onOk(); });
  }

  /* ---------- v2.1 简繁：界面文案显示层转换（PRD US-11：UGC 只在显示层转换，原文不改写；本原型对用户内容不转换） ----------
   * 偏好来源：已登录 = 账号 lang（注册第 3 屏 / 「我的 · 设置」）；游客 = prefLang。三页共用，全站生效。
   * 转换表由 design-system/gen-hant.py 从页面文案生成（OpenCC s2tw 字表 + 少量词组），勿手改。
   * 跳过：[data-ugc]（帖子标题正文、话题、留言、用户名、房间名等用户内容）、输入框、textarea、script / style。 */
  /* HANT-TABLE:BEGIN */
  var HANT_C = "与與专專业業东東丢丟两兩严嚴个個临臨为為举舉么麼义義乐樂习習书書买買于於云雲亚亞产產亲親仅僅从從仓倉们們价價优優会會传傳伦倫伪偽体體侧側储儲儿兒关關兴興内內册冊写寫决決况況准準减減凑湊几幾凭憑击擊划劃则則刚剛创創删刪别別剧劇办辦务務动動势勢区區医醫华華协協单單卖賣占佔卧臥卫衛却卻厅廳历歷压壓厨廚参參双雙发發变變叠疊号號后後吗嗎启啟员員咨諮响響团團围圍国國图圖圆圓场場块塊垫墊墙牆声聲处處备備复復头頭娱娛学學实實审審宫宮对對导導将將尘塵尽盡层層届屆属屬岁歲岗崗币幣师師帜幟带帶帮幫并並广廣庆慶库庫应應开開异異弃棄张張弹彈强強归歸当當录錄彻徹径徑忆憶态態总總恒恆户戶托託执執扩擴扰擾抛拋护護报報拟擬拦攔择擇挂掛挡擋换換据據摊攤敛斂数數断斷无無旧舊时時昵暱显顯暂暫机機权權条條来來杰傑极極构構柜櫃标標栈棧栏欄树樹样樣档檔检檢楼樓槛檻横橫欢歡气氣汇匯沟溝没沒泄洩浅淺测測浏瀏涨漲温溫游遊滚滾满滿炉爐点點炼煉烧燒热熱爱愛状狀独獨环環现現电電画畫盖蓋盗盜盘盤着著码碼确確礼禮离離种種积積称稱稳穩竖豎笔筆筛篩签籤简簡类類粤粵紧緊红紅约約级級纪紀纬緯纯純纳納线線组組细細终終经經绑綁结結绕繞绘繪给給络絡绝絕统統继繼续續绳繩缓緩编編缘緣缩縮网網职職联聯胀脹胆膽脚腳脸臉节節范範荐薦获獲萝蘿营營虚虛补補装裝见見观觀规規视視览覽觉覺触觸计計订訂认認讨討让讓训訓议議讯訊记記讲講许許论論设設访訪证證评評识識诈詐诉訴诊診词詞试試话話询詢该該详詳语語误誤说說请請读讀调調谢謝谱譜责責败敗账賬货貨质質购購贴貼费費赁賃资資赛賽赞贊趋趨跃躍车車转轉轮輪软軟轻輕载載辑輯输輸辩辯边邊达達过過运運还還这這进進远遠违違连連适適选選递遞邮郵邻鄰采採里裡钟鍾钮鈕铁鐵铺鋪链鏈销銷锁鎖锅鍋错錯键鍵镑鎊镜鏡长長门門闭閉问問闲閒间間闻聞阅閱队隊际際陈陳险險随隨隐隱雇僱静靜页頁顶頂项項顺順须須预預领領频頻题題颜顏额額风風饭飯饮飲馆館馈饋驳駁验驗骗騙骚騷鲜鮮鸭鴨麦麥黄黃齐齊齿齒龄齡龙龍", HANT_P = "一只一隻|一周一週|上周上週|举报檢舉|交并交併|信息資訊|公布公佈|关系關係|分钟分鐘|前台前臺|发布發佈|台不臺不|台会臺會|台共臺共|台创臺創|台可臺可|台后臺後|台品臺品|台官臺官|台开臺開|台批臺批|台按臺按|台控臺控|台播臺播|台操臺操|台管臺管|台编臺編|台自臺自|台说臺說|台账臺賬|台面檯面|合并合併|后台後臺|周五週五|周六週六|周日週日|周末週末|回复回覆|复上覆上|复制複製|复印複印|复用複用|多只多隻|审核審核|尽快儘快|布局佈局|平台平臺|并发併發|房台房臺|手表手錶|批准批准|折叠摺疊|日志日誌|本周本週|每周每週|汇总彙總|注册註冊|注明註明|源台源臺|签约簽約|签证簽證|绘制繪製|网络網絡|联系聯繫|聞台聞臺|视频影片|账号帳號|轻松輕鬆|里拉里拉|重复重複|阿杰阿杰|面团麵糰|面粉麵粉|须发鬚髮|默认預設";
  /* HANT-TABLE:END */
  var hantChar = null, hantPhrase = null;
  function hantTables(){
    if (hantChar) return;
    hantChar = {}; hantPhrase = {};
    var cs = Array.from ? Array.from(HANT_C) : HANT_C.split('');
    for (var i = 0; i + 1 < cs.length; i += 2) hantChar[cs[i]] = cs[i + 1];
    HANT_P.split('|').forEach(function(p){ if (p.length === 4) hantPhrase[p.slice(0, 2)] = p.slice(2); });
  }
  function toHant(str){
    hantTables();
    var s = String(str == null ? '' : str), out = '';
    for (var i = 0; i < s.length; i++) {
      var two = s.substr(i, 2);
      if (two.length === 2 && hantPhrase[two]) { out += hantPhrase[two]; i++; continue; }
      var c = s.charAt(i); out += hantChar[c] || c;
    }
    return out;
  }
  function lang(){ var s = load(), u = me(); return (u && (u.lang === 'zh-Hant' || u.lang === 'zh-Hans')) ? u.lang : (s.prefLang || 'zh-Hans'); }
  function setLang(l){
    l = l === 'zh-Hant' ? 'zh-Hant' : 'zh-Hans';
    var s = load(), u = me(); if (u) u.lang = l; s.prefLang = l; save(); applyLang();
    return l;
  }
  var langOrig = (typeof WeakMap !== 'undefined') ? new WeakMap() : null;
  var LANG_ATTRS = ['aria-label', 'placeholder', 'title'];
  function skipNode(el){
    for (var n = el; n && n.nodeType === 1; n = n.parentNode) {
      var tg = n.tagName;
      if (tg === 'SCRIPT' || tg === 'STYLE' || tg === 'TEXTAREA' || tg === 'NOSCRIPT') return true;
      if (n.hasAttribute && (n.hasAttribute('data-ugc') || n.hasAttribute('data-no-hant'))) return true;
    }
    return false;
  }
  function convertText(node, hant){
    var rec = langOrig.get(node), v = node.nodeValue;
    if (hant) {
      if (!rec || (v !== rec.hant && v !== rec.hans)) rec = { hans: v, hant: toHant(v) };
      else if (v === rec.hans) rec.hant = toHant(v);
      langOrig.set(node, rec);
      if (v !== rec.hant) node.nodeValue = rec.hant;
    } else if (rec && v === rec.hant && rec.hans !== v) node.nodeValue = rec.hans;
  }
  function convertAttrs(el, hant){
    var recs = langOrig.get(el) || {};
    LANG_ATTRS.forEach(function(a){
      if (!el.hasAttribute(a)) return;
      var v = el.getAttribute(a), r = recs[a];
      if (hant) {
        if (!r || (v !== r.hant && v !== r.hans)) r = { hans: v, hant: toHant(v) };
        recs[a] = r; if (v !== r.hant) el.setAttribute(a, r.hant);
      } else if (r && v === r.hant && r.hans !== v) el.setAttribute(a, r.hans);
    });
    langOrig.set(el, recs);
  }
  function applyLangTo(root, hant){
    if (!root || !langOrig) return;
    if (root.nodeType === 3) { if (!skipNode(root.parentNode)) convertText(root, hant); return; }
    if (root.nodeType !== 1 || skipNode(root)) return;
    convertAttrs(root, hant);
    var walker = document.createTreeWalker(root, 5, { acceptNode: function(n){
      if (n.nodeType === 1) return skipNode(n) ? 2 : 1;            // REJECT 子树 / ACCEPT
      return /[\u4e00-\u9fff]/.test(n.nodeValue) ? 1 : 3;         // 只处理含中文的文本
    } });
    var n, list = [];
    while ((n = walker.nextNode())) list.push(n);
    list.forEach(function(x){ if (x.nodeType === 3) convertText(x, hant); else convertAttrs(x, hant); });
  }
  var langObserver = null;
  function applyLang(){
    if (!hasDoc() || typeof document.createTreeWalker !== 'function') return;
    var hant = lang() === 'zh-Hant';
    document.documentElement.setAttribute('lang', hant ? 'zh-Hant' : 'zh-Hans');
    if (document.title) { var tt = document.title; if (hant) { if (!document.__hansTitle || toHant(document.__hansTitle) !== tt) document.__hansTitle = tt; document.title = toHant(document.__hansTitle); } else if (document.__hansTitle) document.title = document.__hansTitle; }
    applyLangTo(document.body, hant);
    if (!langObserver && typeof MutationObserver !== 'undefined') {
      langObserver = new MutationObserver(function(muts){
        if (lang() !== 'zh-Hant') return;
        muts.forEach(function(m){
          if (m.type === 'characterData') applyLangTo(m.target, true);
          else if (m.type === 'attributes') { if (!skipNode(m.target)) convertAttrs(m.target, true); }
          else Array.prototype.forEach.call(m.addedNodes, function(x){ applyLangTo(x, true); });
        });
      });
      langObserver.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: LANG_ATTRS });
    }
  }

  /* ---------- v2.3 房间帖子「推到频道」（PRD §36.11）----------
   * 默认不进频道动态。只有房主能推、能撤回（平台管理员在正式版后台操作，原型无此角色）；只能推已公开的帖子；
   * 推送记录只存 key 与房间 / 所属频道，内容仍以原帖为准（原帖删除或下架即不再显示）。显示仍受国家隔离与 norec 约束。 */
  function pushMap(){ var s = load(); if (!s.pushes) s.pushes = {}; return s.pushes; }
  function canPush(room){ var u = me(); return !!(u && room && !roomIsPrivate(room) && room.owner === u.handle && room.parentCode); }
  function pushRoomPost(room, key, source){
    if (!canPush(room) || !key) return null;
    var rec = { key: String(key), roomId: room.id, roomName: room.name, parentCode: room.parentCode, by: me().handle, ts: now(), source: source || 'store' };
    pushMap()[rec.key] = rec; save();
    return rec;
  }
  function unpushRoomPost(room, key){
    var m = pushMap(), rec = m[key];
    if (!rec || !canPush(room) || rec.roomId !== room.id) return false;
    delete m[key]; save();
    return true;
  }
  function pushedPost(key){ return pushMap()[key] || null; }
  function pushedFor(code){
    var m = pushMap(), s = load();
    var postMap = {}; s.posts.forEach(function(p){ postMap[p.id] = p; });
    return Object.keys(m).map(function(k){ return m[k]; }).filter(function(r){
      if (code && r.parentCode !== code) return false;
      var p = postMap[r.key];
      if (p && p.status !== 'published') return false;
      return true;
    }).sort(function(a, b){ return b.ts - a.ts; });
  }

  /* ---------- v2.6 站内信（私信 / 消息请求 / 拉黑 / 陌生人私信开关）----------
   * 演示：消息只存在本机 localStorage，真实投递、推送与风控需要后端（PRD §36.16）。v1 只有文字和图片，没有已读回执、没有语音 */
  var DM_MAX = 1000;
  function dmList(){ var s = load(); if (!s.dms) s.dms = []; return s.dms; }
  function blockedList(){ var s = load(); if (!s.blocked) s.blocked = []; return s.blocked; }
  function isBlocked(h){ return blockedList().indexOf(h) >= 0; }
  function followsUser(h){ var s = load(); return (s.follows || []).indexOf(h) >= 0; }
  function followUser(h, on){
    if (!me() || !h || h === me().handle) return null;
    var s = load(); if (!s.follows) s.follows = [];
    var i = s.follows.indexOf(h), want = on === undefined ? i < 0 : !!on;
    if (want && i < 0) s.follows.push(h); if (!want && i >= 0) s.follows.splice(i, 1);
    save(); return want;
  }
  function dmAllowStrangers(){ var p = load().dmPrefs; return !p || p.allowStrangers !== false; }
  function setDmAllowStrangers(on){ var s = load(); s.dmPrefs = s.dmPrefs || {}; s.dmPrefs.allowStrangers = !!on; save(); return s.dmPrefs.allowStrangers; }
  function dmVisible(d){ return !isBlocked(d.peer.handle); }
  function dmThreads(){ return me() ? dmList().filter(function(d){ return d.status === 'active' && dmVisible(d); }).sort(function(a, b){ return b.ts - a.ts; }) : []; }
  function dmRequests(){ return me() ? dmList().filter(function(d){ return d.status === 'request' && dmVisible(d); }).sort(function(a, b){ return b.ts - a.ts; }) : []; }
  function dmThread(id){ for (var i = 0, l = dmList(); i < l.length; i++) if (l[i].id === id) return l[i]; return null; }
  function dmFind(h){ for (var i = 0, l = dmList(); i < l.length; i++) if (l[i].peer.handle === h) return l[i]; return null; }
  function dmUnread(){ return me() ? dmList().filter(dmVisible).reduce(function(n, d){ return n + (d.unread || 0); }, 0) : 0; }
  function unreadAll(){ return unread() + dmUnread(); }
  /* 我主动发起：没有会话就新建一个 active 会话（对方那边会进「消息请求」或被对方的开关挡住，需要后端） */
  function dmOpen(peer){
    if (!me() || !peer || !peer.handle || peer.handle === me().handle) return null;
    var d = dmFind(peer.handle);
    if (!d) { d = { id: uid('dm'), peer: { handle: peer.handle, name: peer.name || peer.handle, tone: peer.tone || 'a' }, status: 'active', unread: 0, ts: now(), messages: [] }; dmList().push(d); save(); }
    return d;
  }
  function dmOpenForListing(peer, listingRef){
    if (!me() || !peer || !peer.handle || peer.handle === me().handle) return null;
    if (isBlocked(peer.handle)) return null;
    var d = dmFind(peer.handle);
    if (!d) {
      d = { id: uid('dm'), peer: { handle: peer.handle, name: peer.name || peer.handle, tone: peer.tone || 'a' },
        status: 'active', unread: 0, ts: now(), messages: [],
        listingInquiry: true, listingRef: listingRef || null };
      dmList().push(d);
    } else {
      d.status = 'active';
      if (listingRef) d.listingRef = listingRef;
    }
    save();
    return d;
  }
  function dmSend(id, msg){
    var d = dmThread(id); msg = msg || {};
    if (!me() || !d) return { ok: false, reason: 'auth' };
    if (isBlocked(d.peer.handle)) return { ok: false, reason: 'blocked' };
    if (d.status === 'request') return { ok: false, reason: 'request' };
    var m = { id: uid('m'), from: 'me', ts: now() };
    if (msg.kind === 'image') { m.kind = 'image'; m.src = msg.src && msg.src.length < 150000 ? msg.src : ''; m.alt = msg.alt || '图片'; }
    else { var tx = String(msg.text || '').trim(); if (!tx) return { ok: false, reason: 'empty' }; if (tx.length > DM_MAX) return { ok: false, reason: 'long' }; m.kind = 'text'; m.text = tx; }
    if (msg.listingRef) m.listingRef = msg.listingRef;
    d.messages.push(m); d.ts = m.ts; save();
    return { ok: true, message: m };
  }
  /* 对方发来（演示工具用）：拉黑 → 丢弃；已有会话 → 追加；我关注的人 → 正常会话；陌生人 → 消息请求，若我关了陌生人私信 → 不送达 */
  function dmReceive(peer, text, opts){
    if (!me() || !peer || !peer.handle) return 'auth';
    if (isBlocked(peer.handle)) return 'blocked';
    opts = opts || {};
    var d = dmFind(peer.handle);
    if (!d) {
      var stranger = !followsUser(peer.handle);
      if (stranger && !dmAllowStrangers() && !opts.listingInquiry) return 'filtered';
      var status = (stranger && !opts.listingInquiry) ? 'request' : 'active';
      d = { id: uid('dm'), peer: { handle: peer.handle, name: peer.name || peer.handle, tone: peer.tone || 'd' },
        status: status, unread: 0, ts: now(), messages: [],
        listingInquiry: !!opts.listingInquiry, listingRef: opts.listingRef || null };
      dmList().push(d);
    }
    var msgObj = { id: uid('m'), from: 'peer', kind: 'text', text: String(text || '你好'), ts: now() };
    if (opts.listingRef) msgObj.listingRef = opts.listingRef;
    d.messages.push(msgObj);
    d.unread = (d.unread || 0) + 1; d.ts = now(); save();
    return d.status;
  }
  var CONTACT_DAILY_LIMIT = 5;
  function contactViewsRemaining(){
    var s = load(), today = new Date().toISOString().slice(0, 10);
    if (!s.contactDaily || s.contactDaily.date !== today) return CONTACT_DAILY_LIMIT;
    return Math.max(0, CONTACT_DAILY_LIMIT - (s.contactDaily.count || 0));
  }
  function recordContactView(title){
    var s = load(), u = me(), today = new Date().toISOString().slice(0, 10);
    if (!s.contactDaily || s.contactDaily.date !== today) s.contactDaily = { date: today, count: 0 };
    if (s.contactDaily.count >= CONTACT_DAILY_LIMIT) return -1;
    s.contactDaily.count++;
    s.contactViews.push({ title: title || '', ts: now(), by: u ? u.handle : 'guest' });
    save();
    return Math.max(0, CONTACT_DAILY_LIMIT - s.contactDaily.count);
  }
  function browseCountry(){ return load().browseCountry || ''; }
  function setBrowseCountry(code){ var s = load(); s.browseCountry = (code && code !== 'GLOBAL') ? String(code) : ''; save(); return s.browseCountry; }
  function effectiveCountry(){
    var c = country();
    if (c && countryLaunched(c)) return c;
    var b = browseCountry();
    if (b && countryLaunched(b)) return b;
    return c;
  }
  function dmMarkRead(id){ var d = dmThread(id); if (d && d.unread) { d.unread = 0; save(); } return d; }
  function dmAccept(id){ var d = dmThread(id); if (!me() || !d || d.status !== 'request') return false; d.status = 'active'; save(); return true; }
  function dmDelete(id){ var l = dmList(), n = l.length; load().dms = l.filter(function(d){ return d.id !== id; }); save(); return load().dms.length < n; }
  function blockUser(h){ if (!me() || !h) return false; var b = blockedList(); if (b.indexOf(h) < 0) b.push(h); save(); return true; }
  function unblockUser(h){ var b = blockedList(), i = b.indexOf(h); if (i >= 0) { b.splice(i, 1); save(); return true; } return false; }

  /* ---------- v2.5 喜欢（按账号存；游客不能点，先轻注册） ---------- */
  function likeMap(){ var s = load(); if (!s.likes) s.likes = {}; return s.likes; }
  function liked(key){ return !!(me() && key && likeMap()[String(key)]); }
  function toggleLike(key){
    if (!me() || !key) return null;
    var m = likeMap(), k = String(key);
    if (m[k]) delete m[k]; else m[k] = now();
    save();
    return !!m[k];
  }

  /* ---------- v2.5 发布草稿自动保存（一份；发布成功或手动清空后删除） ---------- */
  function draft(){ var d = load().draft; return d && (String(d.text || '').trim() || String(d.title || '').trim()) ? d : null; }
  function saveDraft(d){
    var s = load();
    if (!d || !(String(d.text || '').trim() || String(d.title || '').trim())) { if (s.draft) { delete s.draft; save(); } return null; }
    s.draft = { text: String(d.text || ''), title: String(d.title || ''), type: d.type || 'text', topics: (d.topics || []).slice(0, 10), dest: d.dest || '', ts: now() };
    save();
    return s.draft;
  }
  function clearDraft(){ var s = load(); if (s.draft) { delete s.draft; save(); } }

  /* ---------- v2.5 分享：系统分享面板 → 复制链接 → 提示链接（不发任何外部请求） ---------- */
  function shareLink(opts){
    opts = opts || {};
    var url = opts.url || (typeof location !== 'undefined' ? String(location.href).split('#')[0] : '');
    var title = opts.title || '海外圈';
    var nav = typeof navigator !== 'undefined' ? navigator : null;
    var done = function(msg){ toast(msg); return msg; };
    if (nav && typeof nav.share === 'function' && opts.native !== false) {
      return nav.share({ title: title, url: url }).then(function(){ return done('已打开系统分享'); }, function(){ return 'cancel'; });
    }
    if (nav && nav.clipboard && typeof nav.clipboard.writeText === 'function') {
      return nav.clipboard.writeText(url).then(function(){ return done('链接已复制，可以粘贴发给朋友'); }, function(){ return done('复制失败，请长按地址栏复制链接'); });
    }
    return Promise.resolve(done('复制失败，请长按地址栏复制链接'));
  }

  /* ---------- v2.1 「正在关注」上次看到的时间（US-03 未读分隔线） ---------- */
  function lastSeen(key){ var s = load(); s.lastSeen = s.lastSeen || {}; return Number(s.lastSeen[key] || 0); }
  function markSeen(key, ts){ var s = load(); s.lastSeen = s.lastSeen || {}; s.lastSeen[key] = ts || now(); save(); return s.lastSeen[key]; }

  /* ---------- v2.1 官方 AI 自动关键词（演示版，PRD §30.6）----------
   * 只在用户一个关键词都没填时触发；最多 5 个，每个 ≤12 字；只读标题 + 正文 + 分类，不读位置、订阅与行为；
   * 本地受控词表匹配代替模型，低置信（正文太短）返回空数组，绝不阻塞发布。 */
  var AI_MAX = 5;
  var AI_LEXICON = [
    ['租房', /租房|房租|租金|整租|出租|求租|租屋/], ['合租', /合租|室友|单间/], ['押金保护', /押金|deposit|DPS|TDS|mydeposits/i],
    ['包bills', /bills|水电|包网/i], ['看房', /看房|房源|采光|户型/], ['二手', /二手|转让|闲置|九成新|出售/], ['家具', /家具|书桌|椅子|沙发|衣柜|床垫|IKEA/i],
    ['电器', /电器|电饭煲|微波炉|冰箱|洗衣机|吸尘器/], ['自取', /自取|自提|当面交收|上门取/], ['兼职', /兼职|part.?time|时薪|小时工/i], ['求职', /求职|招聘|岗位|面试|简历|实习/],
    ['工作签证', /工作签|工签|right to work|sponsor/i], ['签证', /签证|visa|BRP|eVisa/i], ['GP注册', /GP|NHS|看病|诊所/], ['落地', /落地|新生|刚到|开学/],
    ['交通', /地铁|TfL|Elizabeth line|巴士|火车|Oyster/i], ['美食', /美食|餐厅|火锅|奶茶|烘焙|菠萝包|中超/], ['活动', /活动|聚会|线下|观影局|报名/],
    ['追剧', /追剧|追更|第\s*\d+\s*集|港剧|剧集/], ['影视', /电影|影视|片单/], ['英超', /英超|足球|球赛|球迷/], ['留学', /留学|大学|学生/], ['council tax', /council tax/i]
  ];
  var AI_PLACES = /伦敦|曼彻斯特|伯明翰|爱丁堡|利物浦|Stratford|Ealing|Camden|Lewisham|Canary Wharf|Chinatown|Zone\s?\d/gi;
  function aiKeywords(text, category){
    var s = String(text || '');
    if (s.replace(/\s/g, '').length < 6) return [];
    var hits = [];
    AI_LEXICON.forEach(function(e){ var m = s.search(e[1]); if (m >= 0) hits.push({ k: e[0], at: m }); });
    var pm; AI_PLACES.lastIndex = 0;
    while ((pm = AI_PLACES.exec(s))) { var k = pm[0].replace(/^zone\s?/i, 'Zone '); if (!hits.some(function(h){ return h.k.toLowerCase() === k.toLowerCase(); })) hits.push({ k: k, at: pm.index }); }
    hits.sort(function(a, b){ return a.at - b.at; });
    var out = [];
    if (category && /^(房产|招聘|市场|生活|交流|活动|其他)$/.test(category) && category !== '其他') out.push(category);
    hits.forEach(function(h){ if (out.length < AI_MAX && out.indexOf(h.k) < 0 && h.k.length <= 12) out.push(h.k); });
    return out.slice(0, AI_MAX);
  }

  ensureStyle();
  if (hasDoc() && typeof document.createTreeWalker === 'function') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', applyLang); else setTimeout(applyLang, 0);
  }
  return {
    KEY: KEY, state: state, save: save, reset: reset, me: me, isGuest: isGuest, ago: ago, uid: uid, esc: esc,
    notify: notify, unread: unread, consumeFail: consumeFail, setFailNext: setFailNext,
    country: country, setCountry: setCountry, countryLaunched: countryLaunched, countryName: countryName, regionVisible: regionVisible,
    setChannelRegions: setChannelRegions, channelRegion: channelRegion, roomRegion: roomRegion,
    setChannelInfo: setChannelInfo, channelInfo: channelInfo, channelCategory: channelCategory, roomCategory: roomCategory,
    findRoom: findRoom, ownedRooms: ownedRooms, createRoom: createRoom, roomIsPrivate: roomIsPrivate, canViewRoom: canViewRoom, setRoomPrivate: setRoomPrivate,
    roomJoinRequested: roomJoinRequested, requestRoomJoin: requestRoomJoin, roomRequests: roomRequests, approveRoomJoin: approveRoomJoin,
    addPost: addPost, postsFor: postsFor, visiblePost: visiblePost,
    approve: approve, reject: reject, deletePost: deletePost, roomPostsForFollowing: roomPostsForFollowing,
    closeListing: closeListing, renewListing: renewListing, isListingClosed: isListingClosed, listingCloseInfo: listingCloseInfo,
    contactViewsRemaining: contactViewsRemaining, recordContactView: recordContactView, CONTACT_DAILY_LIMIT: CONTACT_DAILY_LIMIT,
    browseCountry: browseCountry, setBrowseCountry: setBrowseCountry, effectiveCountry: effectiveCountry,
    simulateJoin: simulateJoin, logout: logout, deleteAccount: deleteAccount, exportData: exportData,
    requireAuth: requireAuth, openAuth: openAuth, openReport: openReport, confirm: confirmDialog, closeLayer: closeLayer, toast: toast,
    dmThreads: dmThreads, dmRequests: dmRequests, dmThread: dmThread, dmFind: dmFind, dmOpen: dmOpen, dmOpenForListing: dmOpenForListing, dmSend: dmSend, dmReceive: dmReceive,
    dmMarkRead: dmMarkRead, dmAccept: dmAccept, dmDelete: dmDelete, dmUnread: dmUnread, unreadAll: unreadAll, DM_MAX: DM_MAX,
    blockUser: blockUser, unblockUser: unblockUser, isBlocked: isBlocked, blockedList: function(){ return blockedList().slice(); },
    followUser: followUser, followsUser: followsUser, dmAllowStrangers: dmAllowStrangers, setDmAllowStrangers: setDmAllowStrangers,
    liked: liked, toggleLike: toggleLike, draft: draft, saveDraft: saveDraft, clearDraft: clearDraft, shareLink: shareLink,
    canPush: canPush, pushRoomPost: pushRoomPost, unpushRoomPost: unpushRoomPost, pushedPost: pushedPost, pushedFor: pushedFor,
    lang: lang, setLang: setLang, toHant: toHant, applyLang: applyLang, lastSeen: lastSeen, markSeen: markSeen, aiKeywords: aiKeywords, AI_MAX: AI_MAX,
    isOpen: function(){ return !!layer; }
  };
})();
/* UKCN-SHARED:END */
