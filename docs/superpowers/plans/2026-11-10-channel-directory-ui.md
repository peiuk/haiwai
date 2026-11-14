# 频道加入目录 UI 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化现有频道目录，让用户能更快发现、比较并加入频道，同时保留房间和法域信息。

**Architecture:** 在 `prototype-x-style.html` 单文件原型中调整 `renderAdd()` 的内容层级，复用现有订阅、组合包、地区和用户房间数据。扩展 `channelRow` 为可选近期帖子预览；详情仍沿用现有频道详情页。

**Tech Stack:** HTML、CSS、原生 JavaScript、现有设计 tokens；不加依赖。

**Spec:** `docs/superpowers/specs/2026-11-10-channel-directory-ui-design.md`

## Global Constraints

- 保留「频道目录 / 创建房间」分段及现有频道加入、退订、频道包订阅语义。
- 官方频道按地区分组，用户房间标记「用户自建 · 非官方」。
- 频道卡上的加入按钮固定右侧，至少 44×44px；频道名称可打开详情。
- 组合包优先于长目录；法域/开通说明保留并放入可展开区域。
- 375px 下筛选可横向滚动，标题不被按钮遮挡；复用深浅色 tokens。

## Review Focus

- 组合包中部分频道已加入：按钮状态与一键加入/移除区域语义保持一致。
- 无搜索结果或分类无匹配：呈现清楚空状态，不显示空地区标题。
- 无近期帖子频道：卡片仍完整可读，不出现空白预览区域。
- 已加入频道：筛选或搜索不会错误重置订阅状态。
- 移动端窄宽：筛选可滚动，加入按钮保持可见和可点。

---

### Task 1: 重整频道目录层级与卡片

**Files:**
- Modify: `prototype-x-style.html`

**Interfaces:**
- Consumes: Existing `channels`, `items`, `packs`, `regions`, `myRooms`, `subs`, `roomJoined`, `visibleChannel`, `packHTML`, `launchCardHTML`, and `renderAdd()`.
- Produces: Refreshed directory markup/styles plus local region/category filters; preserve current join handlers and channel-detail navigation.

- [x] **Step 1: Add directory filter state and filtering controls**

Add `directoryRegionFilter` and `directoryKindFilter` state. Render horizontally scrollable controls inside the directory: `全部` plus regions represented by currently visible channels, and `全部 / 官方频道 / 用户频道`. Combine these with existing `visibleChannel(c)` and `searchTerm` when deriving directory channels. Keep filter state when switching between directory/create segments.

- [x] **Step 2: Move packs above the channel list and compact their layout**

Render region packs immediately after the filters in a horizontally scrollable compact row. Reuse `packHTML` join state and existing pack click handling. For partially joined packs, show the joined count while keeping the action「一键补齐」. Keep unavailable jurisdiction information secondary.

- [x] **Step 3: Add recent-post hints to directory channel rows**

Extend `channelRow(c, options = {})` with an optional preview flag. When enabled from `renderAdd()`, select the final matching entry in `items` for that channel and show its title, or a concise no-recent-content label, alongside existing description, activity and region metadata. Keep other callers unchanged. Channel name continues to use `data-channel-detail`; join button remains directly actionable.

- [x] **Step 4: De-emphasize secondary policy and launch content**

Keep user rooms after official channels. Put launch cards and legal/opening notes inside a native `<details>` disclosure labelled「地区与平台说明」. Keep the create-room segment and its form untouched.

- [x] **Step 5: Apply responsive visual hierarchy**

Add focused styles for directory filters, compact packs, channel preview rows, empty states and disclosure. Reuse current tokens and maintain 44px join targets. At 375px, allow filters/packs to scroll horizontally without forcing channel rows wider than the viewport.

- [x] **Step 6: Review source and prototype behavior**

Re-read `renderAdd()`, filters, `packHTML`, `channelRow`, join handlers and responsive rules. Confirm expected markup/data flow for filters, previews, join states, detail navigation and disclosure. Do not add or run automated tests unless requested. Browser visual review may be unavailable for local `file://` pages under the current browser security policy; report that limitation if it remains blocked.

---
