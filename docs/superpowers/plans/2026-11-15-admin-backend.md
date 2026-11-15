# 管理后台第一版 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 管理员在 `/admin` 处理审核队列和举报、封禁用户、下架恢复内容、上下架频道，并查看审计日志和看板。

**Architecture:** 新增 `app/api/v1/admin.py`（前缀 `/admin`，依赖 `require_admin`），读接口和新写操作都在这里；审帖 / 审举报沿用 `/moderation/*`。前端新增顶层路由 `/admin` → `web/src/views/AdminView.vue`（不套 AppShell，桌面宽表格），守卫要求 `profile.is_admin`。

**Tech Stack:** FastAPI + SQLAlchemy；Vue 3 + TS + Pinia；pytest。

**Spec:** `docs/superpowers/specs/2026-11-15-admin-backend-design.md`

## Global Constraints
- 每个 admin 写操作调用 `write_audit(session, admin.id, action, target_type, target_id)`，在 `session.commit()` 之前。
- 动作名：`admin.user.suspend` / `admin.user.activate` / `admin.content.remove` / `admin.content.restore` / `admin.channel.activate` / `admin.channel.deactivate`；补的审核审计：`moderation.approve` / `moderation.reject`（target_type `content` 或 `comment`）。
- 非管理员访问 `/api/v1/admin/*` → 403；未登录 → 401。
- 列表上限 50 条；错误用 `APIError`。
- 前端只用 `design-system/tokens.css` 的变量，过 `npm run check:ui`。

## Review Focus
- 管理员封禁自己或其他管理员 → 409（否则后台可能被锁死）。Task 2 测试。
- 恢复一条没删的内容 / 重复操作 → 409，不重复写审计。Task 2 测试。
- 用户被封禁后旧 access token 立即失效（`_load_user` 已检查 status）。Task 2 测试。
- 非管理员直接打开 `/admin` → 跳回首页，不闪出数据。Task 4 浏览器验证。
- 本地 dev 不再人人可审：`_require_moderator` 仅在 `settings.testing` 下放行。Task 1（已有 prod 测试覆盖拒绝分支）。

---

### Task 1: 权限收口与审核审计

**Files:** Modify `app/api/v1/moderation.py`、`app/api/v1/me.py:45`；Create `app/api/v1/admin.py`；Test `tests/test_admin.py`

**Produces:** `require_admin(user: User = Depends(current_user)) -> User`（403 `FORBIDDEN`）；`/me` 返回 `is_admin: bool`。

- [ ] 测试 `test_me_reports_admin_flag`、`test_moderation_decision_writes_audit`（approve 后有 `moderation.approve` 审计）。
- [ ] `_require_moderator` 放行改为 `user.is_admin or (settings.testing and settings.app_env == "dev")`；`decide` / `decide_comment` 写审计。
- [ ] 全量 pytest 绿。

### Task 2: admin 接口（全部 `Depends(require_admin)`，在 `app/main.py` 注册）

- `GET /admin/stats` → `{new_posts_today, new_users_today, pending_contents, pending_comments, pending_channels, open_cases}`（UTC 当天）
- `GET /admin/queue` → `{contents, comments, channels, cases}`；case 带 `target_type`（content/comment/channel/user，按 `decide_case` 分支规则）与 `target_label`。
- `GET /admin/users?q=`；`POST /admin/users/{id}/status {status}`：自己或管理员 409 `CANNOT_SUSPEND_ADMIN`，没变化 409 `NO_CHANGE`。
- `GET /admin/contents?q=&status=`；`POST /admin/contents/{id}/status {action: remove|restore}`：remove 设 deleted + `drop_pushes`，restore 仅限 deleted → published。
- `GET /admin/channels?q=`；`POST /admin/channels/{id}/active {active}`。
- `GET /admin/audit?action=&cursor=` → `{items:[{id,action,actor_name,target_type,target_id,created_at}], next_cursor}`。

- [ ] 测试：`test_admin_endpoints_reject_non_admin`、`test_suspend_and_reactivate_user`、`test_remove_and_restore_content`、`test_queue_and_stats`、`test_channel_toggle_and_audit_list`。
- [ ] 实现，全量 pytest 绿。

### Task 3: 前端 /admin
- `web/src/api.ts`：`MeProfile.is_admin?: boolean`。
- `web/src/router/index.ts`：顶层 `/admin`（通配之前），`beforeEnter` 未登录或 `refreshProfile()` 后非管理员 → `"/"`。
- `web/src/views/AdminView.vue`：stats 卡片 + tab（队列 / 用户 / 内容 / 频道 / 日志，`?tab=`）；队列调 `/moderation/*` 决定接口，其余调 admin；成功后 toast 并刷新。
- `ProfileView.vue`：管理员可见"管理后台"入口。
- [ ] `npm run check:ui`、`npm run test:logic`、`npx vue-tsc --noEmit -p tsconfig.json` 全过。

### Task 4: 浏览器实测
- [ ] `python -m app.make_admin <测试账号>`，重启 uvicorn；`/admin` 每个 tab 点一次操作；普通账号打开 `/admin` 跳回首页。
- [ ] 提交前问用户。
