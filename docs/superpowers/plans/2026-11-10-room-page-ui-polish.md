# 房间主页 UI 优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 优化房间页窄屏首屏层级，确保类型切换、房间信息与加入操作清楚可用。

**Architecture:** 保留单文件 HTML 原型和所有既有状态逻辑，只增加窄屏覆盖样式，并对装饰性封面背景作小幅增强。为 420px 演示模式提供与窄屏媒体查询一致的规则。

**Tech Stack:** HTML、CSS、原生 JavaScript；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-10-room-page-ui-polish-design.md`

## Global Constraints

- 遵循 `design-system/MASTER.md` v1.7 和房间页覆盖规则。
- 新控件不低于 44px 触控目标；保留已有焦点态和 reduced-motion。
- 不改房间数据、订阅状态、内容或媒体流程。

## Review Focus

- 375px 类型筛选：单行、可横向滚动且无需页面横向滚动。
- 375px 长标题：标题可换行，通知和加入按钮仍完整可见。
- 桌面：房间摘要和操作继续并排显示。
- `body.preview-mobile`：在宽桌面视口中切换预览时也应用移动头部样式。
- 深浅色主题：封面标题与装饰元素保持清楚可读。

---

### Task 1: 整理房间页窄屏首屏

**Files:**
- Modify: `prototype-collection-room.html`
- Modify: `.superpowers/sdd/2026-11-10-room-page-ui-polish/progress.md`

**Interfaces:**
- Consumes: existing `.room-switch`, `.hero-row`, `.hero-info`, `.hero-actions`, room cover and current CSS tokens.
- Produces: narrow-screen-only layout overrides; no JavaScript or data interface changes.

- [x] **Step 1: Add the approved responsive visual treatment**

Use the existing `max-width:760px` section and matching `body.preview-mobile` rules. Keep `.room-switch` on one horizontal scroll row. Reflow `.hero-row` so `.hero-info` uses the full row and `.hero-actions` spans the width below it; keep both actions at least 44px high. Add a subtle decorative cover overlay using existing colors and improve title contrast without changing cover copy.

- [x] **Step 2: Review the source against acceptance criteria**

Inspect the new selectors alongside existing desktop and mobile rules. Confirm no business handlers or content markup changed, both themes inherit existing tokens, and both physical narrow viewports and preview-mobile receive the new layout. Do not run automated tests or browser screenshot capture.

- [x] **Step 3: Record completion**

Update the progress ledger with changed areas, static review outcome, and the visual-preview limitation.
