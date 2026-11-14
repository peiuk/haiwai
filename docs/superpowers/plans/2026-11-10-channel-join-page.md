# 频道加入页面原型实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有原型中完成可浏览、可查看详情并能快捷加入频道与用户房间的响应式体验。

**Architecture:** 延续 `prototype-x-style.html` 单文件、无外部依赖的演示架构。扩展现有「发现频道」目录交互与频道详情视图，复用已有频道示例数据、订阅集合、通知状态、导航及主题切换。

**Tech Stack:** HTML、CSS、原生 JavaScript；现有 design tokens 与 SVG 图标。

**Spec:** `docs/superpowers/specs/2026-11-10-channel-join-page-design.md`

## Global Constraints

- 目录同时提供官方频道和用户房间筛选；房间须有至少一条已发布内容才显示。
- 加入按钮固定在卡片右上角，最小触控目标 44×44px。
- 用户房间标明「用户自建 · 非官方」并按最近更新时间倒序。
- 加入用户房间后更新通知默认开启；摘要通知不含原文、单集或外链。
- 游客可浏览；触发加入时保留目标频道，演示轻注册后完成该加入动作。
- 使用 `design-system/MASTER.md` v1.7 与现有 tokens，不新增颜色 token 或依赖。

## Review Focus

- 窄屏长标题：加入按钮仍可见且不覆盖名称。
- 无搜索结果/筛选结果：显示清楚的空状态与恢复浏览提示。
- 加入/退订：目录卡与详情视图的状态同步，重复点击不会产生重复通知。
- 游客触发加入：注册演示后保留所选对象并完成加入。
- 已加入房间的静音/通知语义：不能把静音误表示为退出房间。

---

### Task 1: 频道目录与详情原型

**Files:**
- Modify: `prototype-x-style.html`

**Interfaces:**
- Consumes: Existing `channels`, `myRooms`, `subs`, `roomJoined`, `notifications`, `renderPage`, `toast`, and page navigation patterns.
- Produces: Channel directory/detail UI and click behavior within the existing discovery page; no new global data format or external dependency.

- [x] **Step 1: Inspect the current discovery and join handlers**

Read the discovery renderer, room and official channel cards, join handlers, and responsive rules in `prototype-x-style.html`; identified insertion points without restructuring unrelated pages.

- [x] **Step 2: Add directory-to-detail navigation**

Added a channel detail view with description and published items. Directory filters and search remain in memory when returning. Directory cards remain directly joinable. Follow-up: channel names in feed cards now navigate to the same detail view, and the detail list includes all channel items with UGC labels for user posts.

- [x] **Step 3: Synchronize join state and guest flow**

Directory/detail buttons share subscription state. Guest preview starts with no subscriptions, and the demo registration restores the signed-in state before applying the intended join action. Room update notification is added only when the room was not already joined.

- [x] **Step 4: Add empty and failure feedback**

Search/filter empty states remain visible. Network failure simulation was not added because the prototype has no network failure mechanism.

- [x] **Step 5: Align responsive and accessibility behavior**

Added 44px join controls, descriptive join labels, mobile detail wrapping, and Escape/cancel behavior for the registration dialog. Existing theme tokens and focus-visible rules are reused.

- [x] **Step 6: Review the prototype source**

Reviewed relevant renderers, handlers, CSS, and state flow. Browser visual review was blocked by the browser security policy for `file://` pages; no alternate browser path was attempted. Desktop/mobile appearance remains unobserved.

---
