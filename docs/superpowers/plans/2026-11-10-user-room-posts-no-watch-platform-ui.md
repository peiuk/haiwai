# 用户房间内容 UI 清理实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除用户帖子、剧集条目和电影条目中的观看平台字段与文案。

**Architecture:** 延续原生单文件原型。剧集/电影只显示用户内容字段；视频房间继续使用独立播放器、平台与版权确认 UI。同步更新房间页规范和首页帖子样例。

**Tech Stack:** Markdown、HTML、CSS、原生 JavaScript；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-10-user-room-posts-no-watch-platform-ui-design.md`

## Global Constraints

- 不移除视频房间的官方外链、同意与原创上传确认流程。
- 不改加入/退订、追更进度、排序、发布权限和数据模型。
- 遵循当前设计系统；控件触控目标和焦点态维持原值。

## Review Focus

- 剧集条目：无平台名、观看入口徽章或平台播放器。
- 电影卡片：无平台名或仅登记状态。
- 添加剧集/电影：表单无平台选择器，保存逻辑不再读取已删除字段。
- 视频类型：外链播放器、版权确认和举报继续存在。
- 普通 UGC 样例：文案不要求合法观看入口或仅登记说明。

---

### Task 1: 清理用户房间观看平台 UI

**Files:**
- Modify: `prototype-collection-room.html`
- Modify: `prototype-x-style.html`
- Modify: `design-system/pages/collection-room.md`
- Modify: `.superpowers/sdd/2026-11-10-user-room-posts-no-watch-platform-ui/progress.md`

**Interfaces:**
- Consumes: existing room forms, `renderEps()`, `renderFilms()`, `renderHero()` and video-only `embedSlot()`.
- Produces: user-owned episode/movie content without provider fields in UI or add handlers; video workflow remains unchanged.

- [x] **Step 1: Remove episode/movie provider display and editing**

Remove provider selects from both forms; update tips and add handlers to use only episode/movie metadata and notes. Render no provider badge, watch link or episode inline player in these collections. Remove the global provider-list side card; keep video-only policy content associated with the video type.

- [x] **Step 2: Remove misleading user-post copy and update page guidance**

Replace series/film notice and description copy with community/collection language. Remove viewing-platform wording from sample user notes and the ordinary UGC feed item. Update the page override to define EpisodeRow and FilmCard without watch-provider fields.

- [x] **Step 3: Review source and record outcome**

Inspect the touched renderers, forms, add handlers, room-type copy, side panel and the video workflow. No automated tests or browser screenshot capture per project instructions; record static review and preview limitation.
