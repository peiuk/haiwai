# 管理后台第一版 设计

## 为什么
前台基本完成，运营需要一个地方处理举报、审帖、管用户和频道。现在后端只有"做决定"的接口（`/moderation/*`），没有任何列表，管理员没法知道有什么要处理。

## 范围（用户已确认）
- 审核与举报队列：待审帖子 / 留言 / 房间 + 未处理举报，一页处理。
- 用户管理：搜索、封禁 / 解封。
- 内容与频道管理：搜索帖子并下架 / 恢复；搜索频道并上 / 下架。
- 审计日志（按动作筛选、分页）+ 数据看板（几项计数）。
- 位置：同一 Vue 应用的 `/admin` 路由。

## 不做（第二版）
频道认证、官方精选（要加字段改表）；后台设管理员（继续用 `python -m app.make_admin`）。

## 做法
考虑过的两种：
1. **新路由 `app/api/v1/admin.py` + `require_admin` 依赖，现有 `/moderation/*` 决定接口保留并由前端直接调用**（选这个：不动现有调用方和测试）。
2. 把审核接口搬进 admin：要改现有调用方和测试，无收益。

## 设计
- 权限：`require_admin` 只认 `User.is_admin`。`_require_moderator` 的放行收窄为"仅单元测试（`settings.testing` 且 dev）"，本地 dev 不再人人可审。`/me` 返回 `is_admin`。
- 审计：admin 的每个写操作写 `write_audit`；审帖、审留言补审计。
- 接口（全部 `/api/v1/admin/*`，非管理员 403）：
  - `GET stats`：今日新帖、今日新用户、待审数、未处理举报数。
  - `GET queue`：待审帖子、待审留言、待审房间、未处理举报。
  - `GET users?q=`、`POST users/{id}/status {status: active|suspended}`（不能封自己 / 管理员）。
  - `GET contents?q=&status=`、`POST contents/{id}/status {action: remove|restore}`。
  - `GET channels?q=`、`POST channels/{id}/active {active: bool}`。
  - `GET audit?action=&cursor=`：倒序分页，带操作人名字。
- 前端：`AdminView.vue`，顶部看板，五个 tab（队列 / 用户 / 内容 / 频道 / 日志）。路由守卫：非管理员跳回首页。复用 `request`、设计 token、toast。
- 测试：非管理员访问每类 admin 接口都 403；封禁 / 解封、下架 / 恢复、频道上下架都写审计；队列与统计返回正确。

## 留给实现者
列表上限（50 条）、搜索字段、页面细节样式。
