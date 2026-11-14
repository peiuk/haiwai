# ADR-0001 · 后端技术栈锁定（v1 基线）

- **状态**：`Proposed`（待确认；确认后改为 `Accepted`，并回填确认人与日期）
- **日期**：2026-11-13
- **依据**：`PRD-UK-Chinese-Local-Community-v1.1.md` §8 / §9 / §12 / §13 / §14 / §16 / §26 / §33 / §36；上一轮「后端技术优化清单」审查结论
- **范围**：后端 + 基础设施选型。**前端栈不并入本 ADR**，见第 6 节

---

## 1. 结论

**建议锁定 §12 为 v1 基线，不换栈。** 这套组合（Python 3.12 / FastAPI 单体模块化 / SQLAlchemy 2 + Alembic / Celery + Redis / PG16 + PostGIS / pg_trgm / R2 / 单机 Compose + Cloudflare）对本项目是**合格且偏保守**的配置：生态匹配采集、OpenCC、embedding 与简繁转换；单体 + 目录约束避免了早期微服务的运维成本；分阶段搜索与 AI 分层给成本留了退路。为了「更现代」换 Go / Node / 微服务，收益为负。

但**「照抄 §12 表格 + §14.1 compose 模板」不合格**。缺的不是选型，是三类东西：

1. **配置层没有钉子**：版本、进程数、连接池、内存预算、Redis 角色、备份加密、密钥轮换都没定，单机最容易在这里翻车；
2. **规格内部有 2 处矛盾**（第 3 节），照着写一定写歪，且其中 1 处是 UK GDPR 口径问题；
3. **前端栈是重写不是接后端**（第 6 节），必须与本 ADR 分开决策。

因此「锁定」的定义是：**锁组件与契约，附第 3 节 2 项修正 + 第 4 节 8 项补强**，作为写第一行代码的前置条件。

---

## 2. 逐项裁定

| 组件 | 裁定 | 附带条件 |
|---|---|---|
| Python 3.12 + FastAPI 单体模块化 | ✅ 锁定 | 保持 `app/internal/{auth,channel,subscription,content,ai,source,moderation,admin,dsar}` 分包，禁止跨包直接访问彼此 model；不拆服务 |
| SQLAlchemy 2.0 + Alembic | ✅ 锁定 | **同步驱动 `psycopg3` + 同步 session**（Celery worker 是同步上下文，全 async 需 `asgiref` 桥接，收益不抵踩坑）；每个 migration 必须写 `downgrade`；`content` / `channel_item` / `user_event` 的迁移先做影子表验证 |
| PostgreSQL 16 | ✅ 锁定 | `timestamptz` 全域；`Europe/London` 为业务日界；`max_connections` 与连接池对齐（C2） |
| PostGIS | ⚠️ 有条件锁定 | 扩展保留（`city.centre` / 未来「附近」）；**首版不写 `listing_ext.location` 精确坐标**，见 M1 |
| Celery + Redis，4 队列 | ⚠️ 有条件锁定 | 按队列拆 worker、显式 concurrency、beat 独立，见 C3 / C4。MVP 可推迟 `ai` 队列（L2 LLM 延后），**但 Celery 本身不砍**（过期、日报、通知、刷新都依赖定时） |
| `pg_trgm` → OpenSearch + IK | ✅ 锁定 | 早期不上独立集群；搜索走统一 repo 层，便于 P2 替换 |
| Cloudflare R2 | ⚠️ 有条件锁定 | 私有桶 + 签名 URL + 30 天生命周期；区域 hint 与 DPA / sub-processor 清单登记；备份先加密再上传（M2） |
| 单台英国 VPS + Compose + CF CDN/WAF | ⚠️ 有条件锁定 | VPS 规格下限与信任链，见 C2 / C7；日活过万前不引编排 |
| Web Push / PWA | ⏸ 延后 | PECR 默认关闭 + `consent_record` 留痕是前置条件，不进首发 MVP 验收 |
| Vue 3 + Nuxt SSR + PWA | ⏸ 另案 | 见第 6 节 |

---

## 3. 规格修正（写代码前必须定稿）

### M1 · `listing_ext.location` 与隐私口径冲突（P0）

`§8.2` 定义 `listing_ext.location geography(Point,4326)`，但 `§13.1` 明确「不采集精确位置」，`§33.2` 明确「不申请 GPS，不保存 IP 原文或经纬度」，`§26` 的 `chk_signal_detail_shape` 甚至专门加了正则把坐标排除在埋点之外。

**裁定**：保留列定义（避免改 DDL baseline）但**首版恒为 NULL**，位置只写 `area_name` / `city` 文本；`city.centre` 作为城市级公开坐标保留。若确需「附近」，须走单独同意 + DPIA，另立 ADR。否则分类信息帖会静默收集精确位置，直接违反自己写的合规条款。

### M2 · 备份未加密即出网（P0）

`§14.4` 的命令是 `pg_dump -Fc | gzip | r2-upload.sh`，而库内含 `contact_cipher` 等敏感列、`app_user`、`consent_record`。明文（虽为密文列，但整体仍是可读的个人数据快照）直传对象存储，与 `§12.1`「密钥禁止入库与进 Git」和 `§13.1` DPA 要求不匹配。

**裁定**：`pg_dump -Fc | gzip | age -r <backup_pubkey> | r2-upload.sh`，公钥托管在 VPS 之外，解密私钥不落 VPS；备份恢复演练纳入 `§14.4` 季度纪律。

> 另：上轮指出的 `§13.3` 第 10 条「不做算法排序，不存在推荐放大风险」与 §26/§27 的 OSA 放大评估要求冲突，属合规前提，需在 OpenAPI/Alembic baseline 定稿时一并修订；不在本 ADR 的技术栈范围内，但**是同一个「锁定前置」批次**。

---

## 4. 合格配置补强清单

### C1 · 版本与依赖钉死
- `uv.lock`（或 `requirements.txt` 带 hash）纳入 Git；`python:3.12-slim` 固定到 digest，不用浮动 tag。
- 镜像 tag 已钉的保持：`postgis/postgis:16-3.4`、`redis:7-alpine`、`nginx:1.27-alpine`。
- 一份 OpenAPI 3.1 作为**唯一契约源**（收敛 §9.2 与 §20.5 / 21.8 / 22.7 / 23.5 / 24.8 / 26.7 / 27.7 / 28.6 / 30.8 / 32.6 的增量端点，并补齐 §36.16 站内信与 §36.17 六项闭环缺失的端点与表），FastAPI 由 schema 生成、前端生成 TS 类型。
- 一份 Alembic baseline（含 `postgis` / `pg_trgm` 扩展与三个 CHECK 约束），禁止手工改库。

### C2 · 单机资源预算（4 vCPU / 8 GB 参考下限）
| 进程 | 实例 | 内存上限 | 说明 |
|---|---|---|---|
| nginx | 1 | 128 MB | 静态 + 反代 |
| api（uvicorn） | 2 | 512 MB / ea | `--workers 2`；`pool_size=4, max_overflow=4` → ≤16 连接 |
| worker（fetch/notify/maintenance） | 1 | 512 MB | `--concurrency=2 --prefetch-multiplier=1` |
| worker（ai） | 1 | 1.5 GB | `-Q ai --concurrency=1`，bge-small 常驻；与业务队列隔离，避免 embedding 积压堵通知 |
| celery beat | 1 | 128 MB | **独立进程**，见 C3 |
| PG16 + PostGIS | 1 | 2.5 GB | `shared_buffers=2GB`、`max_connections=60` |
| Redis | 1 | 512 MB | 见 C4 |

合计约 6.3 GB，留 ≥1.5 GB 给 OS / page cache。**关键风险**：Celery 默认按 CPU 核数起 prefork，8 GB 机器会被直接打爆，必须显式 `--concurrency`。

### C3 · Celery 进程模型
`§14.1` 用 `celery worker -B -Q fetch,ai,notify,maintenance` 单进程带内嵌 beat。按队列拆 worker 后**多个 `-B` 会重复发定时任务**（日报、过期、降权都重复执行）。改为独立 `celery -A app.worker beat`，且 beat 只保留 1 实例；所有周期任务显式 `Europe/London` 时区，不用 UTC 日界（BST 期间差 1 小时会影响 5 次/日频控与 30 天过期）。

### C4 · Redis 角色边界
单实例阶段按 DB 分离：`db0` broker、`db1` result（必须设 TTL 过期）、`db2` 限流 / 临时态，并统一 key 前缀。**不得对 broker 所在 DB 设 `allkeys-lru`**（会静默丢任务）。`Idempotency-Key` 落到 PG 唯一索引 + 响应快照，不放 Redis（多 worker / 重启会失效）。注明多 DB 仅适用于单机，未来上 Redis Cluster 需改为前缀方案。

### C5 · 三个横切模块先于业务端点
`core/` 下先落：**国家/法域上下文**（repo 层强制 WHERE + RLS/强制 view，无上下文的查询直接拒绝）、**crypto**（AES-GCM 的 `nonce` / `key_version` 三列 + 解密收敛到单一函数 + 轮换策略）、**审核状态机 + audit**（发布可见性统一走一个 view，`push` 外键 `ON DELETE CASCADE`）。这三项是上一轮 P0 技术债的落点，不能边写端点边补。

### C6 · 频控原子性与事务边界
联系方式 5 次/日：`INSERT ... ON CONFLICT (user_id, day) DO UPDATE SET count=count+1 WHERE count < 5 RETURNING`；解密、扣额度、写 `contact_view_audit` 同一事务。发布频控 5/h、20/天同样在 DB 层计数，不依赖应用层内存。

### C7 · Cloudflare 信任链与限流对齐
§36 的「CDN 边缘 IP 国家级推断」依赖 `CF-Connecting-IP`；若源站可被直连，该头可伪造 → 国家上下文可被越权。必须：只放行 CF IP 段（或 Authenticated Origin Pulls）+ nginx 覆盖而非追加该头。同时 §9.1 的「游客 60/min/IP」与 WAF 限流要对齐口径，避免双重计数或互相绕过。

### C8 · 可观测、密钥与测试
- `request_id` 中间件贯穿结构化 JSON 日志；脱敏白名单明确（不记手机号、正文全文、联系方式明文）；Sentry 只收脱敏字段。
- `readyz` 真查 PG + Redis，`healthz` 只查进程。
- `CONTACT_ENCRYPTION_KEY` / `APP_SECRET_KEY` 的轮换流程写进 runbook，`.env` 不进 Git、不落镜像层。
- 测试栈补齐：`pytest` + `testcontainers` PostgreSQL 契约测试，把现有 8 道 Node `vm` 门禁里的规则断言（严格时间序、国家隔离、listing 禁入推荐、频控上限、级联失效、DSAR 级联、三个 CHECK）翻译过来。**原型门禁不是后端验收。**

---

## 5. 锁定边界

**锁死（改动需新 ADR）**：组件清单与版本基线、模块分包边界、OpenAPI 契约与 `/api/v1` 版本策略、DDL baseline、国家上下文 / crypto / 审核三个横切模块的调用纪律、时区口径。

**可替换接缝（无需新 ADR）**：LLM 供应商（走 `LLM_API_BASE` 适配层）、搜索后端（`pg_trgm` → OpenSearch）、对象存储（保持 S3 兼容 API）、部署形态（Compose → 编排）、embedding 模型版本。

---

## 6. 前端栈：另案，不并入本次锁定

当前交付物是 `prototype-x-style.html` / `prototype-collection-room.html` / `publish-content.html` 三个**静态 HTML + localStorage 共享层**原型，而 §12 要的是 Vue 3 + Nuxt SSR + PWA。这不是「给原型接后端」，是**重写前端**，成本远大于后端选型本身，也决定 `shared/ukcn-shared.js` 的去留。

三个选项，需单独拍板：
- **(a) 直接重写**：一步到位 SSR/SEO，但原型与 8 道门禁、简繁表、共享层同步链路全部作废；
- **(b) 原型保留为演示快照 + 另起 `web/`（建议）**：原型冻结为设计验收基线，新前端按 OpenAPI 生成类型；原型继续跑现有门禁，两者不互相覆盖；
- **(c) 渐进**：先 Vite SPA + 轻量预渲染满足频道落地页 SEO，P2 再迁 Nuxt；风险是 SSR 迁移期做两次路由与数据层。

建议 **(b) + (c) 组合**，并在同一决策里明确 localStorage 共享层是否与真实 API 并存（决定是否要加 adapter 层）。

---

## 7. 锁定生效的验收条件

1. 本 ADR 状态改为 `Accepted`；
2. OpenAPI 3.1 单一契约源 + Alembic baseline 生成，§36.16 / §36.17 端点补齐；
3. M1 / M2 与 §13.3 合规前提修订落文档；
4. compose 按 C1–C4 落地，`docker compose config -q` 通过，dev 可 `up -d` 起全栈；
5. 首条 `pytest + testcontainers` 契约测试通过；
6. 第 6 节的前端栈决策另行记录（ADR-0002）。

---

## 8. 未解决 / 待确认

- 首发范围（全 PRD vs 英国 MVP 闭环）尚未定，影响 `ai` 队列与 L2 LLM 是否进 v1；
- grokbot 在 box 侧按自有基线打包，本 ADR 与后续 PC 侧后端改动需回灌，避免下一轮 sync 覆盖。
