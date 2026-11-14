# 项目逻辑与首页原型优化实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 统一推荐与关注流的产品规则，精简首页说明区，并交付通过门禁且可人工检查的浏览器效果图。

**Architecture:** 继续使用现有单文件 HTML 原型和原生 Node 门禁。把设计决策写进 PRD、首页覆盖规范和项目审查文档；从首页右栏移除长篇说明，保留设置面板、频道目录与卡片上的必要说明。

**Tech Stack:** Markdown、HTML、CSS、原生 JavaScript、Node 检查脚本、Playwright CLI。

**Spec:** `docs/project-review-and-optimization.md`

## Global Constraints

- 推荐流最多 12 条，使用频道信号 0.40/0.30/0.20/0.10、新鲜度和已订阅降权 0.12；不用点击、停留或点赞逐条画像。
- 关注流严格按时间倒序；用户可从推荐页直接切换。
- 来源、许可、原文链接、举报入口及第三方播放器事前同意继续保留。
- 首页右栏不显示长篇定位、法域和推荐参数说明；完整设置仍留在当前设置/目录入口。
- 所有颜色和尺寸沿用现有 token。

## Review Focus

- 首屏推荐信息保持一条短提示，不挤压帖子。
- 420px 搜索栏和主题按钮不互相挤压。
- 移除侧栏说明后，定位和法域设置在其他入口仍可达。
- 房间目录行为按已发布内容数量验证，不依赖固定文案。
- 桌面与窄屏截图均检查横向溢出及关键控件可见性。

---

### Task 1: 统一产品规则与审查记录

**Files:**
- Create: `docs/project-review-and-optimization.md`
- Modify: `PRD-UK-Chinese-Local-Community-v1.1.md`
- Modify: `design-system/pages/home-feed.md`
- Modify: `pages-collection-discovery-notification.md`

- [x] 写出审查结论、推荐/关注流规则、MVP 阶段及来源真相表。
- [x] 将 PRD §2.5 与 §26–§29 的既有推荐公式对齐。
- [x] 将首页覆盖规范的条数、排序提示与参数对齐。
- [x] 把旧三页说明标为历史参考。

### Task 2: 首页说明区与可视层级

**Files:**
- Modify: `prototype-x-style.html`
- Modify: `design-system/check-location.js`
- Modify: `design-system/check-rooms.js`

- [x] 先调整门禁：断言首页右栏没有说明卡，设置面板仍包含透明度/定位说明；房间目录断言检查 `publishedCount > 0` 与对应提示。
- [x] 运行门禁确认首页说明卡断言按预期失败；房间门禁更新为行为断言并通过。
- [x] 从首页右栏移除说明卡和渲染函数；将推荐提示收敛为一行并写明条数、信号口径、更新时间和时间序入口。
- [x] 运行六组门禁并确认通过。

### Task 3: 浏览器视觉验收

**Files:**
- Create: `output/playwright/project-review-home-desktop.png`
- Create: `output/playwright/project-review-home-mobile.png`

- [x] 用本地 HTTP 服务打开原型。
- [x] 截取桌面首页、深浅色和 420px 移动预览。
- [x] 检查搜索栏、主题按钮、首屏提示、内容来源行、右侧栏及横向溢出。
- [x] 运行对比度、UI、区域、媒体、定位和房间门禁。
