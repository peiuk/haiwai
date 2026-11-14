# 频道与用户房间层级实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户房间改为官方频道下的二级空间，并移除发现页中的并列房间目录。

**Architecture:** 在原型数据中用 `parentCode` 表示单一父官方频道。创建表单强制选择父频道；频道详情内渲染房间卡。用户房间页通过 URL 保留父频道上下文。文档新增 §34 覆盖旧版 §32 的可选父级与一级目录规则。

**Tech Stack:** Markdown、HTML、CSS、原生 JavaScript；不增加依赖。

**Spec:** `docs/superpowers/specs/2026-11-10-channel-room-hierarchy-design.md`

## Global Constraints

- 父级只能是官方频道，单一父级，不允许独立房间或房间套房间。
- 空房间对其他用户隐藏；房主可在自己的频道详情页查看。
- 用户房间不进入官方组合包或个性化推荐流。
- 保持原有房间加入、通知、内容和频道帖子行为。

## Review Focus

- 房间不再出现在 `renderAdd()` / `renderDiscover()` 的顶层目录。
- 官方频道组合包不包含用户房间代码。
- 频道详情显示公开房间；房主也能看见自己尚无内容的房间。
- 房间名或父频道缺失时创建按钮禁用，保存也有防御性检查。
- 新建房间 URL 包含父频道；房间页返回链接重新打开该频道详情。

---

### Task 1: 统一层级数据与目录展示

**Files:**
- Modify: `prototype-x-style.html`

**Interfaces:**
- Consumes: `channels`, `myRooms`, `items`, `renderAdd()`, `renderDiscover()`, `renderChannelDetail()`.
- Produces: `myRooms[].parentCode`; a global official fallback channel; room cards nested within channel details; no top-level room listing.

- [x] **Step 1: Add parent-channel data and remove room pseudo-channel**

Add the global general official channel. Give every room an official `parentCode`. Remove the `drama-room` channel stub and its category / pack reference; do not retain its room post as a top-level channel item.

- [x] **Step 2: Nest room cards in channel details**

Render a “用户房间” section in `renderChannelDetail(c)` only when one or more published rooms match `c.code`. Keep room join state and open behavior. Remove the standalone room directory and discover filter.

### Task 2: Require a parent when creating a room

**Files:**
- Modify: `prototype-x-style.html`

**Interfaces:**
- Consumes: official `channels`, `roomParentSelection`, `.rc-go` submit behavior.
- Produces: required official-parent select, defaulted to the global general channel; room navigation includes `parent`.

- [x] **Step 1: Make parent selection visible and required**

Move parent selection outside the optional “more options” block. Offer official channels only. Disable submit until both room name and parent are present; validate both on submit.

- [x] **Step 2: Pass parent context through navigation**

When opening a room, pass its `parentCode`. When creating a room, save the mock record and return to the parent channel detail; opening its card passes the parent code to the room page.

### Task 3: Show room parent and synchronize documentation

**Files:**
- Modify: `prototype-collection-room.html`
- Modify: `PRD-UK-Chinese-Local-Community-v1.1.md`
- Modify: `design-system/pages/collection-room.md`
- Modify: `.superpowers/sdd/2026-11-10-channel-room-hierarchy/progress.md`

- [x] **Step 1: Add parent-channel context and back navigation**

Read the `parent` URL parameter in the room prototype, display the parent channel as a breadcrumb/action, and return to its discovery detail page.

- [x] **Step 2: Write authoritative PRD and design-system override**

Add PRD §34 superseding the old §32 optional parent and top-level room directory. Update the room page override to specify required parent and nested room presentation.

- [x] **Step 3: Review source and record outcome**

Inspect data records, directory renderers, room form and submit logic, URL flow, and conflicting PRD references. Do not run automated tests or browser screenshot capture.
