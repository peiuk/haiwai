# 英国中文本地生活社区 Web — PRD + 技术方案

| 项目   | 内容                                    |
| ---- | ------------------------------------- |
| 文档版本 | v1.0（2026-11-08）                      |
| 项目代号 | UKCN Local                            |
| 交付对象 | 裴总                                    |
| 文档状态 | 待评审 / 可直接进入开发排期                       |
| 试点市场 | 英国（UK），首城建议伦敦或曼彻斯特                    |
| 形态   | Web 优先，PWA 可安装；暂不做原生 App              |
| 关联目录 | `C:/Users/Administrator/Documents/uk` |

---

## 0. 阅读指引与前置假设

本文分两部分：**第 1–7 章为 PRD（产品）**，**第 8–16 章为技术方案（工程）**，第 17–19 章为风险、排期与附录。开发同学可从第 8 章直接开始。

### 0.1 本方案基于的假设（需裴总确认，未确认前按此执行）

| 编号 | 假设                               | 若假设不成立的影响                |
| -- | -------------------------------- | ------------------------ |
| A1 | 团队 ≤ 3 人，且至少 1 人能写 Python + Vue  | 若纯外包/无研发，需改为无代码方案，整体重做   |
| A2 | 起步预算 ≤ £200/月基础设施                | 超出则可提前上托管搜索与云转码          |
| A3 | 服务器部署在英国/欧盟境外节点，不面向中国大陆做加速       | 若需大陆访问，须另行评估 ICP 备案与跨境合规 |
| A4 | MVP 不涉及在线支付、不做电商、不做直播            | 涉及支付需接入 Stripe + 消费者法合规  |
| A5 | 首版只做一个城市，且能在上线前人工准备 200+ 条真实种子信息 | 无种子内容 = 空城，产品必死          |
| A6 | 用户定位为 18 岁以上成年人                  | 见 §13.3，此设定可降低但不豁免合规义务   |

### 0.2 一句话定位

> **一个城市里，中文用户能查到、能发布、且敢相信的本地生活信息站。**

不是「海外华人版今日头条」。资讯是填充，结构化本地信息与可信度才是产品。

### 0.3 明确不做清单（MVP 边界）

- ❌ 个性化推荐算法（协同过滤 / 向量召回 / 排序模型）
- ❌ 抓取英国新闻全文并转载
- ❌ 自建视频转码、直播、短视频信息流
- ❌ 多城市同时铺开
- ❌ 微服务 / K8s / 多活
- ❌ 原生 iOS / Android App

---

## 1. 背景、市场判断与为什么选英国

### 1.1 已有竞品（2026-11 调研）

| 产品    | 形态                                       | 覆盖           | 与本项目重叠点                    |
| ----- | ---------------------------------------- | ------------ | -------------------------- |
|       | 资讯 + 分类信息 + 社交 + 短视频 + 商城，注册时选兴趣标签「定制头条」 | 69+ 国家       | 用户描述的形态几乎被完整覆盖，包括注册问卷与兴趣推送 |
| 华人168 | 招聘、租房、找商家、二手、社群发帖，认证发布 + 人机同审            | 北美为主，2014 年起 | 本地生活 + 分类信息赛道已有成熟玩法与质量管控范式 |

**结论**：功能清单不构成壁垒。这类产品的胜负手是「单一城市的信息密度」与「信息可信度」，而非算法或功能数量。

### 1.2 英国市场的特殊性（机会点）

1. **中文服务信息高度分散**：签证与 eVisa、NINo、GP 注册、council tax、垃圾分类、租房押金保护、中超与中餐、驾校、手机卡等信息散落在 GOV.UK、地方议会、NHS、大学官网与社群帖子里，缺少一个中文、结构化、会过期的入口。
2. **繁体中文与粤语使用者占比高**：英国中文社群在书写习惯上简繁并存，主流竞品以简体为主。首版即做 `zh-Hans` / `zh-Hant` 双语文案与简繁转换，是低成本、高感知的差异点。
3. **学生与落地前 90 天人群刚需明确**：租房、二手、接机、办卡、找工、同城互助是高频且愿意主动发布内容的场景，UGC 自增长条件成立。
4. **竞争强度低于北美**：北美已有深耕十余年的分类信息平台，英国尚无同等密度的中文产品。

### 1.3 成功指标（MVP 上线后 8 周）

| 指标           | 目标                         | 说明          |
| ------------ | -------------------------- | ----------- |
| 城市内有效分类信息存量  | ≥ 300 条，且 30 天内未过期占比 ≥ 70% | 密度是唯一先导指标   |
| 注册→完成引导问卷转化率 | ≥ 70%                      | 检验问卷是否过长    |
| 周活跃发布者       | ≥ 40 人                     | 检验 UGC 自增长  |
| 次周留存         | ≥ 25%                      | 低于此说明信息流无价值 |
| 举报处理中位时长     | ≤ 12 小时                    | 合规与信任指标     |
| 诈骗/垃圾信息占比    | ≤ 2%（抽检）                   | 超阈值立即收紧发布策略 |

**不把 PV/DAU 作为首期北极星指标**——早期刷量没有意义。

---

## 2. 用户画像与核心场景

| Persona   | 描述                         | 最痛的事                         | 我们给什么                        |
| --------- | -------------------------- | ---------------------------- | ---------------------------- |
| P1 落地新人   | 抵英 0–3 个月，中文为主，英语不足以处理行政流程 | 不知道办卡、GP、押金、council tax 从哪下手 | 结构化「落地清单」+ 同城分类信息 + 问答帖      |
| P2 在读学生   | 大学城，预算敏感，流动性高              | 找合租、买二手、找兼职、找同乡              | 租房/二手/兼职板块，按校区与城市筛选          |
| P3 本地常住家庭 | 已定居，熟悉流程                   | 找可靠华人服务（装修、家政、补习、诊所）、本地活动    | 认证商家、活动版块、口碑与举报体系            |
| P4 信息发布者  | 房东、中介、小商家、社团               | 发到哪里才有人看、怕被骚扰                | 免费发帖 + 联系方式受控 + 置顶/刷新（后期商业化） |

### 2.1 用户故事（P0，含验收标准）

| ID    | 用户故事                                      | 验收标准                                                |
| ----- | ----------------------------------------- | --------------------------------------------------- |
| US-01 | 作为新用户，我想用邮箱/手机注册并选择城市、身份、落地阶段与兴趣，以便看到相关内容 | 注册 ≤ 60 秒；问卷 ≤ 2 屏；可跳过兴趣但城市与身份必填；同意条款单独勾选且留痕        |
| US-02 | 作为落地新人，我想按分类和区域浏览租房/二手/招聘信息               | 列表支持 city + category + 区域 + 价格 + 关键词 + 排序；过期信息默认不展示 |
| US-03 | 作为发布者，我想免费发布一条带联系方式的分类信息                  | 发布需手机验证；必填有效期（默认 30 天）；联系方式默认受控展示；发布后进入审核队列         |
| US-04 | 作为浏览者，我想发布图文帖提问或分享当地生活                    | 支持最多 9 图；图片自动压缩与鉴黄；敏感词命中转人工                         |
| US-05 | 作为浏览者，我想搜索中文关键词找到信息                       | 中文关键词可命中标题与正文；无结果时给推荐词与相近分类                         |
| US-06 | 作为用户，我想举报可疑信息                             | 举报入口 ≤ 2 次点击；生成审核工单；举报人可见处理状态                       |
| US-07 | 作为审核员，我想在后台快速处理举报与待审内容                    | 队列 + 批量操作 + 处置理由 + 全流程审计日志                          |
| US-08 | 作为用户，我想导出或删除我的个人数据                        | 自助发起，7 天内完成；删除后不可恢复且级联清理                            |
| US-09 | 作为运营，我想看到官方公开资讯作为首页填充                     | 3–5 个合规源，只展示标题 + 摘要 + 原文链接；源故障不影响主流程                |
| US-10 | 作为用户，我想用繁体中文阅读界面与内容                       | 界面双语切换；UGC 内容提供简繁切换显示，原文不改写                         |

---

## 3. 功能清单与优先级

### 3.1 P0（6 周 MVP，必做）

| 模块     | 功能                                      | 备注                                    |
| ------ | --------------------------------------- | ------------------------------------- |
| 账号     | 邮箱/手机注册登录、手机验证、JWT 刷新、登出、自助注销           | 密码 Argon2id；不接第三方登录，减少合规面             |
| 引导     | 城市、身份类型、落地阶段、简繁偏好、兴趣标签（多选，可跳过）          | 显式标签写入 `user_tag.source='onboarding'` |
| 分类信息   | 发布 / 编辑 / 刷新 / 下架、分类、价格、区域、有效期、联系方式受控   | 7 个分类，见 §3.4                          |
| UGC 图文 | 发帖、图片上传、话题标签、评论（P0 只做一层评论）              | 评论同样进审核                               |
| 信息流    | 按「城市 + 显式标签 + 时间」的**规则流**               | 不做算法，规则可解释、可调试                        |
| 搜索     | 关键词 + 城市 + 类型 + 标签筛选                    | PG `pg_trgm` 起步，见 §8.4                |
| 互动     | 点赞、收藏、举报、浏览/点击埋点                        | 埋点从第一天就要有，否则后期推荐无数据                   |
| 审核     | 敏感词 + 新用户前 3 帖必审 + 举报工单 + 后台队列          | 对应 OSA 义务                             |
| 资讯填充   | 合规源采集（GOV.UK / 地方议会 / 大学 RSS / 天气 / 交通） | 只存摘要 + 原文链接                           |
| 后台     | 内容审核、用户封禁、采集源健康、标签维护、数据导出工单             | 内部使用，不开放注册                            |
| 合规基础   | 隐私政策、Cookie 同意、服务条款、同意留痕、DSAR 自助        | 见 §13                                 |

### 3.2 P1（2–3 个月）

视频（先外链/≤60 秒，云转码）、私信（陌生人限制）、规则加权推荐（行为权重）、商家认证与置顶、消息推送（Web Push / 邮件）、多城市模板化复制、SEO 落地页、运营数据看板。

### 3.3 P2（6 个月+）

向量召回 / 协同过滤 / 排序模型、OpenSearch + IK 中文分词、原生 App、多语言（英文）、支付与商业化、微服务拆分。

### 3.4 分类体系（固定枚举，避免早期自由膨胀）

`housing` 租房 · `job` 招聘兼职 · `secondhand` 二手 · `service` 本地服务 · `carshare` 拼车接机 · `event` 同城活动 · `qa` 问答互助

兴趣标签独立维护（新闻、娱乐、影视、美食、求职、留学、育儿、体育…），后台可增删改，不硬编码在代码里。

---

## 4. 信息架构与关键流程

### 4.1 前台结构

```
首页(规则流)  ─┬─ 分类信息(7 类) ─ 详情/联系方式受控
              ├─ 社区(图文帖)   ─ 详情/评论
              ├─ 资讯(摘要+跳转)
              ├─ 搜索
              ├─ 发布(选择类型 → 表单 → 审核)
              └─ 我的(资料/标签/我的发布/收藏/隐私与数据)
```

### 4.2 注册引导流程（关键：别把问卷做成劝退页）

```
注册(邮箱+密码+手机) → 手机验证码 → 同意条款(逐项勾选，留痕)
→ 必填 3 项：城市 / 身份 / 落地阶段 → 选填：兴趣标签(默认全选常用 6 个，可改)
→ 简繁偏好(按浏览器语言自动推断) → 进入首页
```

设计要点：兴趣标签给「默认推荐组合」，用户可一键跳过；所有属性后续在「我的」里可改，不做一次性锁定。

### 4.3 分类信息发布流程

```
选择分类 → 填写结构化字段(标题/描述/价格/区域/有效期/联系方式)
→ 提交 → 风控校验(频次/敏感词/黑名单/图片) → 入审核队列
→ [自动通过 | 人工复审] → 发布 → 到期前 3 天提醒刷新 → 到期自动下架
```

联系方式不直接渲染在 HTML 里：需登录 + 点击「查看联系方式」才返回，并记审计日志，降低被爬虫批量抓取与骚扰的风险。

### 4.4 内容审核流程

```
机审(敏感词/图片哈希/链接黑名单/发布频次)
  ├─ 高风险 → 人工队列 (SLA 12h)
  ├─ 中风险 → 先发后审 + 抽样
  └─ 低风险 → 直接发布
举报 → 生成 moderation_case → 人工裁决(通过/删除/封禁) → 通知举报人 → 审计日志
```

---

## 5. 非功能需求

| 类别   | 要求                                                                                        |
| ---- | ----------------------------------------------------------------------------------------- |
| 性能   | 首页 P95 < 800ms（英国节点）；列表接口 P95 < 300ms；图片 WebP + 懒加载                                       |
| 可用性  | MVP 目标 99.5%；采集源故障不得影响发帖与浏览（降级为隐藏资讯模块）                                                    |
| 国际化  | 界面 `zh-Hans` / `zh-Hant`；内容用 OpenCC 做显示层转换，不改原文；时区统一存 UTC，展示按 `Europe/London`（注意 BST 夏令时） |
| SEO  | 分类信息与社区详情页必须 SSR/预渲染并输出 JSON-LD；纯 CSR 会让本地生活流量归零                                          |
| 可访问性 | WCAG 2.1 AA 基线（对比度、键盘可达、图片 alt）                                                           |
| 安全   | 全站 HTTPS、密码 Argon2id、JWT 短时效 + 刷新轮换、接口限流、上传文件类型白名单、CSP、审计日志不可篡改                           |
| 可观测  | 结构化 JSON 日志、错误上报、采集源健康看板、慢查询告警                                                            |
| 数据   | 每日 `pg_dump` 异地备份，保留 30 天；每季度做一次恢复演练                                                      |

---

## 6. 埋点与推荐策略（为什么算法要后置）

### 6.1 三阶段演进

| 阶段             | 触发条件                  | 做法                                                |
| -------------- | --------------------- | ------------------------------------------------- |
| S1 规则流（MVP）    | 0 行为数据                | `score = 同城权重 + 标签匹配 + 时间衰减 + 内容质量分`，SQL 即可实现，可解释 |
| S2 加权规则（P1）    | 累计 ≥ 10 万条有效事件        | 引入隐式标签权重 `w = 0.6·显式 + 0.4·行为`，行为按点击/停留/收藏/举报加权   |
| S3 召回 + 排序（P2） | ≥ 5 万 MAU 且内容池 ≥ 10 万 | 向量召回（embedding）+ 轻量排序模型，仍需保留 S1 兜底与人工运营位          |

### 6.2 S1 打分公式（可直接在 SQL/应用层实现）

```
score = 40·I(同城)
      + 25·(命中显式标签数 / 用户标签数)
      + 20·exp(-年龄小时数 / 72)
      + 10·内容质量分(认证/图片数/完整度)
      +  5·互动热度(log 归一化)
      - 100·I(被举报或风控命中)
```

### 6.3 埋点事件（P0 必须上报）

`view` `click` `dwell_ms` `like` `favorite` `share` `report` `publish` `search` `contact_reveal`。批量上报，前端做本地缓冲，失败重试；`user_event` 按月分区。

---

## 7. 验收总清单

- [ ] 新用户 60 秒内完成注册与引导，标签可在「我的」修改
- [ ] 发布一条租房信息 → 审核 → 前台可见 → 30 天后自动下架
- [ ] 中文关键词「押金」「合租」可搜到对应内容
- [ ] 繁体界面下 UGC 内容可切换显示且不改写原文
- [ ] 任一采集源挂掉，首页其余模块正常
- [ ] 举报 → 工单 → 裁决 → 通知 → 审计日志闭环
- [ ] 用户自助导出与注销，7 天内完成且数据不可恢复
- [ ] 隐私政策、Cookie 同意、条款、同意留痕齐备
- [ ] 备份恢复演练成功；`docker compose up -d` 可在干净环境拉起全栈

---

# 技术方案

## 8. 数据模型（PostgreSQL 15+ / PostGIS）

### 8.1 设计原则

1. **统一内容池**：资讯 / 图文 / 视频 / 分类信息共用 `content` 主表，`type` 区分，共用标签、审核、搜索、埋点、推荐管道。这是避免后期返工的核心决策。
2. **显式标签与行为数据物理分离**：`user_tag` 存声明偏好，`user_event` 存行为事实，权重永不混在一个字段里。
3. **联系方式受控**：联系方式单独存，访问需鉴权 + 审计。
4. **所有内容有有效期**：分类信息强制 `expires_at`，从数据层杜绝死信息。
5. **软删除 + 硬擦除并存**：日常软删，GDPR 擦除走级联硬删流程。


### 8.2 DDL

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE content_type   AS ENUM ('news','post','video','listing');
CREATE TYPE content_status AS ENUM ('draft','pending','published','rejected','expired','deleted');
CREATE TYPE script_type    AS ENUM ('hans','hant','mixed','en');
CREATE TYPE identity_type  AS ENUM ('student','worker','settled','visitor','other');
CREATE TYPE tag_source     AS ENUM ('onboarding','manual','behavior','inferred');

-- 城市：首版只启用一个
CREATE TABLE city (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code        varchar(16) UNIQUE NOT NULL,          -- 'london' / 'manchester'
  name_hans   varchar(64) NOT NULL,
  name_hant   varchar(64) NOT NULL,
  name_en     varchar(64) NOT NULL,
  country     char(2) NOT NULL DEFAULT 'GB',
  timezone    varchar(64) NOT NULL DEFAULT 'Europe/London',
  centre      geography(Point,4326),
  is_enabled  boolean NOT NULL DEFAULT false,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_user (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email          citext UNIQUE,
  phone          varchar(32) UNIQUE,
  password_hash  text,
  display_name   varchar(40) NOT NULL,
  city_id        uuid REFERENCES city(id),
  identity       identity_type,
  arrival_stage  varchar(16),                      -- '0_1m','1_3m','3_12m','1y_plus'
  script_pref    script_type NOT NULL DEFAULT 'hans',
  locale         varchar(12) NOT NULL DEFAULT 'zh-Hans',
  status         varchar(16) NOT NULL DEFAULT 'active',  -- active/suspended/erased
  phone_verified boolean NOT NULL DEFAULT false,
  is_minor_flag  boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  deleted_at     timestamptz
);
CREATE INDEX idx_user_city ON app_user(city_id) WHERE deleted_at IS NULL;

CREATE TABLE tag (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug        varchar(48) UNIQUE NOT NULL,
  name_hans   varchar(48) NOT NULL,
  name_hant   varchar(48) NOT NULL,
  category    varchar(24) NOT NULL,               -- 'interest' / 'topic' / 'listing'
  sort_order  int NOT NULL DEFAULT 0,
  is_active   boolean NOT NULL DEFAULT true
);

-- 显式偏好：source 区分来源，behavior 写入时不得覆盖 onboarding 行
CREATE TABLE user_tag (
  user_id    uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  tag_id     uuid NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  weight     numeric(4,3) NOT NULL DEFAULT 1.000,
  source     tag_source NOT NULL DEFAULT 'onboarding',
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, tag_id, source)
);

-- 采集源与授权状态：无许可的源不允许 enabled
CREATE TABLE source (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name           varchar(96) NOT NULL,
  kind           varchar(24) NOT NULL,            -- 'api','rss','ogl','licensed','manual'
  base_url       text NOT NULL,
  licence_ref    text,                           -- 'OGL v3.0' / NLA 许可编号 / 授权邮件编号
  licence_expiry date,
  robots_checked boolean NOT NULL DEFAULT false,
  rate_limit_qpm int NOT NULL DEFAULT 6,
  allow_fulltext boolean NOT NULL DEFAULT false,
  is_enabled     boolean NOT NULL DEFAULT false,
  last_fetch_at  timestamptz,
  last_error     text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_licensed_source CHECK (
    is_enabled = false OR allow_fulltext = false OR licence_ref IS NOT NULL
  )
);

-- 统一内容池
CREATE TABLE content (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type          content_type NOT NULL,
  status        content_status NOT NULL DEFAULT 'pending',
  author_id     uuid REFERENCES app_user(id) ON DELETE SET NULL,
  source_id     uuid REFERENCES source(id) ON DELETE SET NULL,
  city_id       uuid REFERENCES city(id),
  title         varchar(200) NOT NULL,
  summary       varchar(500),
  body          text,
  script        script_type NOT NULL DEFAULT 'hans',
  canonical_url text,                            -- 采集内容必须指向原文
  cover_key     text,
  media         jsonb NOT NULL DEFAULT '[]'::jsonb,
  extra         jsonb NOT NULL DEFAULT '{}'::jsonb,
  expires_at    timestamptz,
  published_at  timestamptz,
  view_count    int NOT NULL DEFAULT 0,
  like_count    int NOT NULL DEFAULT 0,
  report_count  int NOT NULL DEFAULT 0,
  quality_score numeric(4,3) NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz,
  CONSTRAINT chk_news_link CHECK (type <> 'news' OR canonical_url IS NOT NULL),
  CONSTRAINT chk_listing_expiry CHECK (type <> 'listing' OR expires_at IS NOT NULL)
);
CREATE INDEX idx_content_feed ON content(city_id, type, published_at DESC)
  WHERE status = 'published' AND deleted_at IS NULL;
CREATE INDEX idx_content_title_trgm ON content USING gin (title gin_trgm_ops);
CREATE INDEX idx_content_body_trgm  ON content USING gin (body  gin_trgm_ops);
CREATE INDEX idx_content_expiry ON content(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE content_tag (
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  tag_id     uuid NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
  weight     numeric(4,3) NOT NULL DEFAULT 1.000,
  PRIMARY KEY (content_id, tag_id)
);
CREATE INDEX idx_content_tag_rev ON content_tag(tag_id, content_id);

-- 分类信息扩展字段
CREATE TABLE listing_ext (
  content_id     uuid PRIMARY KEY REFERENCES content(id) ON DELETE CASCADE,
  category       varchar(24) NOT NULL,
  price_gbp      numeric(10,2),
  price_unit     varchar(16),                    -- 'month','once','hour','negotiable'
  area_name      varchar(96),
  location       geography(Point,4326),
  is_verified    boolean NOT NULL DEFAULT false,
  verified_by    uuid REFERENCES app_user(id),
  refresh_count  int NOT NULL DEFAULT 0,
  last_refreshed timestamptz
);
CREATE INDEX idx_listing_geo ON listing_ext USING gist(location);
CREATE INDEX idx_listing_cat ON listing_ext(category, price_gbp);

-- 联系方式：受控访问，应用层加密存储，访问写审计日志
CREATE TABLE listing_contact (
  content_id  uuid PRIMARY KEY REFERENCES content(id) ON DELETE CASCADE,
  payload     bytea NOT NULL,                    -- AES-GCM 密文(phone/email/wechat)
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE media_asset (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id   uuid REFERENCES content(id) ON DELETE CASCADE,
  kind         varchar(12) NOT NULL,            -- 'image','video'
  object_key   text NOT NULL,
  mime         varchar(64) NOT NULL,
  size_bytes   bigint NOT NULL,
  duration_s   int,
  transcode    varchar(16) NOT NULL DEFAULT 'n/a',
  created_at   timestamptz NOT NULL DEFAULT now()
);

-- 行为事件：按月分区，避免单表膨胀
CREATE TABLE user_event (
  id          bigserial,
  user_id     uuid,
  content_id  uuid,
  session_id  uuid,
  event_type  varchar(24) NOT NULL,
  value       numeric(10,2),                   -- dwell_ms 等
  props       jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE TABLE user_event_2026_11 PARTITION OF user_event
  FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE INDEX idx_event_user_time ON user_event(user_id, occurred_at DESC);

CREATE TABLE moderation_case (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id  uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  reporter_id uuid REFERENCES app_user(id),
  reason      varchar(32) NOT NULL,
  status      varchar(16) NOT NULL DEFAULT 'open',
  decision    varchar(24),
  reviewer_id uuid REFERENCES app_user(id),
  notes       text,
  sla_due_at  timestamptz NOT NULL DEFAULT (now() + interval '12 hours'),
  decided_at  timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_mod_open ON moderation_case(status, sla_due_at) WHERE status = 'open';

-- GDPR 同意留痕
CREATE TABLE consent_record (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  purpose    varchar(48) NOT NULL,             -- 'tos','privacy','marketing','analytics'
  version    varchar(16) NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz,
  ip         inet,
  user_agent text
);

-- DSAR 工单（导出 / 擦除）
CREATE TABLE data_request (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  kind        varchar(16) NOT NULL,            -- 'export','erasure'
  status      varchar(16) NOT NULL DEFAULT 'pending',
  due_at      timestamptz NOT NULL DEFAULT (now() + interval '30 days'),
  completed_at timestamptz,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE audit_log (
  id          bigserial PRIMARY KEY,
  actor_type  varchar(16) NOT NULL,           -- 'user','admin','system'
  actor_id    uuid,
  action      varchar(48) NOT NULL,
  target_type varchar(24),
  target_id   uuid,
  payload     jsonb NOT NULL DEFAULT '{}'::jsonb,
  ip          inet,
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_time ON audit_log(created_at DESC);
```

### 8.3 关键约束说明

- `chk_news_link`：采集资讯必须带原文链接，从数据层阻止全文转载。
- `chk_licensed_source`：只有登记了许可编号的源才允许 `allow_fulltext=true`；MVP 阶段全部保持 `false`。
- `chk_listing_expiry`：分类信息必须有有效期，配合定时任务自动转 `expired`。
- `listing_contact` 用 `bytea` 密文，密钥放 KMS/环境变量，**不进数据库备份明文**。

### 8.4 中文搜索的重要坑

PostgreSQL 内建 `to_tsvector` **不分词中文**，`'simple'` 配置对中文几乎无效。MVP 采用 `pg_trgm` GIN + `ILIKE` 兜底（短词与 2–3 字查询效果尚可），或安装 `zhparser` 扩展。规模上升后迁 OpenSearch + IK 分词。**不要在 PRD 阶段承诺「全文检索」，这是 P2 能力。**

### 8.5 定时任务

| 任务 | 频率 | 动作 |
|---|---|---|
| `expire_listings` | 每小时 | `expires_at < now()` 且 `status='published'` → `expired` |
| `expiry_reminder` | 每日 | 到期前 3 天通知发布者可刷新 |
| `fetch_sources` | 每源独立（默认 30 min） | 采集、去重、清洗、入库 |
| `moderation_sla_check` | 每小时 | 超 12h 未处理工单告警 |
| `dsar_worker` | 每小时 | 处理导出/擦除工单 |
| `backup` | 每日 03:00 UTC | `pg_dump` → R2，保留 30 天 |
| `partition_maintain` | 每月 | 预建下月 `user_event` 分区 |

---

## 9. API 设计（REST / v1）

### 9.1 通用约定

- Base：`https://api.<domain>/api/v1`，全站 HTTPS，JSON（UTF-8）。
- 认证：`Authorization: Bearer <JWT>`，access 15 分钟，refresh 7 天且轮换，注销即刻拉黑。
- 分页：游标式 `?cursor=<opaque>&limit=20`（上限 50），返回 `next_cursor`，不用 offset。
- 限流：未登录 60 req/min/IP；登录 300 req/min/user；发布类 5 次/小时/user。
- 幂等：所有 POST 支持 `Idempotency-Key` 头（发布、举报、注册尤其需要）。
- 错误体：`{ "code": "CONTENT_PENDING_REVIEW", "message": "...", "request_id": "..." }`。

### 9.2 端点清单

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/auth/register` | 注册（含同意条款版本） | 否 |
| POST | `/auth/verify-phone` | 手机验证码校验 | 否 |
| POST | `/auth/login` / `/auth/refresh` / `/auth/logout` | 会话 | 否/是 |
| POST | `/auth/password-reset` | 重置 | 否 |
| GET | `/cities?enabled=true` | 已启用城市 | 否 |
| GET | `/tags?category=interest` | 标签字典（含简繁名） | 否 |
| PUT | `/me/tags` | 更新显式标签 | 是 |
| PATCH | `/me` | 更新城市/身份/简繁偏好 | 是 |
| GET | `/me` / `DELETE /me` | 资料 / 发起注销（擦除工单） | 是 |
| GET | `/me/export` | 发起数据导出（DSAR） | 是 |
| GET | `/feed?cursor=&city=&tab=` | 规则流（S1 打分） | 可选 |
| GET | `/contents/:id` | 详情 | 可选 |
| POST | `/contents` | 发布图文帖 | 是 |
| PATCH / DELETE | `/contents/:id` | 编辑 / 下架 | 是（作者） |
| GET | `/listings?city=&category=&area=&min=&max=&q=&sort=` | 分类信息列表 | 否 |
| POST | `/listings` | 发布分类信息 | 是 + 手机验证 |
| POST | `/listings/:id/refresh` | 刷新（延长有效期，限次） | 是 |
| POST | `/listings/:id/contact` | 查看联系方式（写审计日志） | 是 |
| GET | `/search?q=&type=&city=&tag=` | 统一搜索 | 否 |
| GET | `/news?city=&limit=` | 资讯摘要流 | 否 |
| POST | `/contents/:id/like` / `/favorite` / `/report` | 互动 | 是 |
| POST | `/events:batch` | 批量埋点 | 可选 |
| POST | `/uploads/sign` | 获取对象存储直传签名 | 是 |
| GET | `/admin/moderation?status=open` | 审核队列 | 管理员 |
| POST | `/admin/moderation/:id/decision` | 裁决 | 管理员 |
| POST | `/admin/users/:id/suspend` | 封禁 | 管理员 |
| GET | `/admin/sources` / `POST /admin/sources/:id/toggle` | 采集源健康与开关 | 管理员 |
| GET | `/healthz` / `/readyz` | 探针（不含敏感信息） | 否 |

### 9.3 关键请求/响应示例

```http
POST /api/v1/auth/register
Content-Type: application/json
Idempotency-Key: 9f2c...

{
  "email": "user@example.com",
  "password": "...",
  "phone": "+44...",
  "consents": [
    { "purpose": "tos", "version": "2026-11-01" },
    { "purpose": "privacy", "version": "2026-11-01" },
    { "purpose": "analytics", "version": "2026-11-01", "granted": false }
  ]
}
```

```http
POST /api/v1/listings
{
  "category": "housing",
  "title": "近 xxx 站合租单间，包 bills",
  "body": "...",
  "price_gbp": 720,
  "price_unit": "month",
  "area_name": "Zone 2",
  "expires_in_days": 30,
  "tag_slugs": ["student", "housing"],
  "contact": { "phone": "+44...", "wechat": "..." }
}
→ 202 Accepted
{ "id": "...", "status": "pending", "review_sla_hours": 12 }
```

响应 `202` 而非 `201`，因为发布后必须过审；前端要明确提示「审核中」，不能假发布。

### 9.4 错误码（节选）

| HTTP | code | 场景 |
|---|---|---|
| 400 | `VALIDATION_FAILED` | 字段校验失败 |
| 401 | `TOKEN_EXPIRED` | access 过期 |
| 403 | `PHONE_NOT_VERIFIED` | 发布前未验证手机 |
| 409 | `DUPLICATE_CONTENT` | 采集/发布去重命中 |
| 422 | `CONTENT_POLICY_BLOCKED` | 敏感词/风控拦截 |
| 429 | `RATE_LIMITED` | 触发限流 |
| 451 | `SOURCE_NOT_LICENSED` | 采集源无有效许可 |
| 503 | `SOURCE_DEGRADED` | 采集源降级（资讯模块隐藏） |

---

## 10. 采集管线设计（英国合规优先）

### 10.1 源分级（这是本项目的合规红线）

| 级别 | 类型 | 例子 | 可用方式 |
|---|---|---|---|
| **L1 开放** | 政府/公共机构开放数据 | GOV.UK Content API（eVisa、NINo、council tax）、NHS、地方议会公告、Met Office、TfL / National Rail API、大学官网 RSS | OGL v3.0 等开放许可，通常允许商业复用，**须署名并遵守许可条款**；仍要限速与标注来源 |
| **L2 需授权** | 英国报业与通讯社 | 全国/地方报纸、PA Media、News UK、FT、中文媒体 | **即使只用标题与摘要，商业聚合也可能需要 NLA 许可**；News UK 与 FT 不在 NLA 通用许可范围内，须单独谈；或购买 NLA 面向聚合商的 eClips Web / MMO 许可 |
| **L3 禁止** | 全文抓取、绕过 paywall、robots disallow、房产平台数据、个人数据 | Rightmove/Zoopla、社交平台内容、论坛私域 | 一律不做；只允许「用户手动粘贴链接 + 自写摘要」 |

> NLA 参考：其 Corporate Website Republishing Licence 覆盖 headlines 与 text extracts，2026 年 4 月价目中微型公司 1 篇约 £159/年、25 篇约 £1,165/年（**以官方最新价目为准**），且所有使用需标注来源并回链原文。MVP 阶段**不采购任何商业新闻许可**，只走 L1。

### 10.2 管线流程

```
调度(APScheduler/Celery Beat, 每源独立 cron)
→ 抓取(遵守 robots.txt / UA 标识 / QPS 限制 / 超时与重试退避)
→ 解析(按源适配器: JSON / RSS / HTML 选择器)
→ 归一化(统一字段: title, summary, canonical_url, published_at, licence_ref)
→ 去重(SimHash 标题 + canonical_url 唯一 + 近 7 天相似窗口)
→ 清洗(去广告/去脚本/繁简转换 OpenCC/敏感词)
→ 分类打标(规则关键词 → tag，置信度低则标 'uncategorized')
→ 合规闸门(allow_fulltext=false → 只保留 ≤ 200 字摘要 + 原文链接)
→ 入库(content.type='news', status 依源信任度设 published/pending)
→ 健康检查(连续 3 次失败 → 自动 disable + 告警)
```

适配器模式：每个源一个 `SourceAdapter` 子类，新增源不改主管线；`source.last_error` 与后台看板可观测。

### 10.3 采集源故障降级

资讯模块是**可降级模块**：任一源失败或全部失败时，首页自动隐藏该模块，其余功能不受影响。禁止让采集阻塞主链路。

---

## 11. 审核与风控

| 风险 | 措施 |
|---|---|
| 租房/招聘诈骗 | 手机验证、新用户前 3 帖必审、价格异常规则、外链黑名单、重复文案检测、举报入口 |
| 垃圾广告 | 发布频次限制（5 条/小时、20 条/天）、同内容去重、图片指纹 |
| 联系方式滥用 | 受控展示 + 访问审计 + 单用户每日查看上限 |
| 违法内容 | 敏感词 + 图片哈希比对 + 人工队列 + 12h SLA + 向 NCA 报告 CSEA 的流程（见 §13.3） |
| 死信息 | 强制有效期、到期下架、刷新限次 |
| 内部滥用 | 所有后台操作写 `audit_log`，导出与删帖双人复核 |

MVP 建议直接**限定 18+ 用户**（注册时声明 + 条款），降低但是**不免除**儿童保护相关义务，见 §13.3。

---

## 12. 技术架构与选型

### 12.1 选型对比与结论

| 层 | 选择 | 备选 | 结论理由 |
|---|---|---|---|
| 前端 | Vue 3 + Vite + TS + Pinia，Nuxt 或自建 SSR | React/Next | 需要 SEO；若用 Vite SPA 必须补 SSR/预渲染，否则本地生活流量归零 |
| 移动端形态 | **PWA**（可安装、Web Push、离线缓存） | 原生 App / 小程序 | 一套代码覆盖「web」与「app」诉求，避开双端与商店审核 |
| 后端 | **Python 3.12 + FastAPI 单体模块化** | Go / Spring Boot | 采集、清洗、OpenCC、文本处理生态最全；小团队别拆微服务 |
| ORM/迁移 | SQLAlchemy 2.0 + Alembic | — | 迁移可版本化、可回滚 |
| 任务队列 | Celery + Redis（或轻量 ARQ） | — | 采集、通知、DSAR、过期任务统一 |
| 数据库 | PostgreSQL 16 + PostGIS | MySQL | 同城地理查询、jsonb、分区、trgm 都是刚需 |
| 搜索 | `pg_trgm`（MVP）→ OpenSearch + IK（P2） | 直接上 ES | 早期数据量不值得维护独立集群 |
| 对象存储 | Cloudflare R2（S3 兼容） | AWS S3 | 免出网流量费，视频/图片成本可控 |
| 视频 | 云转码或先只做外链 | 自建 FFmpeg 集群 | 自建是早期最大成本黑洞 |
| 部署 | 单台英国/欧洲 VPS + Docker Compose | K8s | 日活过万前不需要编排 |
| 边界 | Cloudflare CDN + WAF + Nginx | — | 海外节点无需 ICP 备案；WAF/限流前置 |

### 12.2 逻辑分层

```
客户端(PWA / 管理后台)
→ CDN + WAF + Nginx(反向代理/静态资源/限流)
→ FastAPI 单体，按 domain 分模块:
   auth / user_tag / content / listing / search / moderation / source / event / admin / dsar
→ PostgreSQL+PostGIS / Redis / R2
外部数据源(L1 开放数据) → 独立 worker → 合规闸门 → 内容池
```

**模块边界靠目录与接口约束，不靠网络拆分**：`internal/` 下按 domain 分包，禁止跨包直接访问对方的数据模型，为 P2 拆分留好后路但不提前付成本。

### 12.3 dev / prod 差异

| 项 | dev | prod |
|---|---|---|
| 域名 | `localhost` / 内网 | 正式域名，强制 HSTS |
| 数据库 | 本地 Compose，假数据 | 托管 PG 或同机 + 每日异地备份 |
| 密钥 | `.env.local` 占位 | 环境变量/KMS，禁止入库与进 Git |
| 采集 | 关闭或用固定 fixture | 按源限速，全量合规校验 |
| 审核 | 自动通过 + 标记 | 强制机审 + 人工队列 |
| 日志 | 控制台 | JSON 结构化 + 脱敏 + 集中收集 |
| 邮件/短信 | 控制台输出 | 真实供应商（需 PECR/GDPR 依据） |
| 错误暴露 | 详细堆栈 | 仅 request_id，不泄露内部信息 |
| 备份 | 无 | 每日 `pg_dump` → R2，30 天保留 |

---

## 13. 合规专章（英国，务必逐条落实）

> 以下为工程落地要点，**不构成法律意见**；上线前请英国本地律师复核条款与 OSA 风险评估。

### 13.1 数据保护：UK GDPR + Data Protection Act 2018

- **法律依据**：账号履约用「合同必需」；兴趣画像与推荐用「同意」（可撤回）；埋点分析用「同意」或「合法利益」并做 LIA 记录。
- **同意留痕**：`consent_record` 记录用途、条款版本、时间、IP/UA；条款更新需重新征求。**Cookie 与非必要埋点须先获同意（PECR）**，默认拒绝。
- **数据最小化**：位置只到城市级，不采集精确坐标与通讯录；注册问卷只问影响信息流的字段。
- **数据主体权利**：自助导出（JSON + 附件）、自助擦除、更正、撤回同意；`data_request` 工单默认 30 天内完成，内部目标 7 天。
- **儿童**：UK GDPR 下数字服务儿童同意年龄为 13；本项目建议直接限定 18+。
- **其他**：向 ICO 缴纳 data protection fee（按规模分档）；指定英国/欧盟代表（若主体在境外）；数据处理者与 sub-processor 清单（R2、邮件、短信、错误上报）需有 DPA；跨境传输需评估 adequacy/IDTA。
- **保留期**：账号注销后 30 天内硬删除；`user_event` 保留 13 个月后聚合或删除；`audit_log` 按合规需要保留（脱敏）。

### 13.2 版权：NLA 与新闻聚合

- 英国报业内容由 NLA Media Access 集中管理版权，**标题、摘要、剪报的商业性复制/聚合可能需许可**；聚合商路径是 MMO / eClips Web 许可，企业网站转载路径是 Corporate Website Republishing Licence（需署名 + 回链原文）。
- **News UK 与 FT 不在该通用许可内**，须单独授权。
- MVP 对策：**只接 L1 开放许可源（OGL v3.0 等）**，`content.canonical_url` 必填，摘要 ≤ 200 字，禁止存全文，`allow_fulltext` 全部为 false，并在页面显著标注来源与许可。
- 工程约束：`source` 表的 `chk_licensed_source` 约束 + API `451 SOURCE_NOT_LICENSED`，从代码层堵住「临时抓一篇试试」。

### 13.3 Online Safety Act 2023（Ofcom 监管）

- 本产品允许用户在英国互相发布内容，属于 **regulated user-to-user service**。违法内容义务自 2025 年起生效、儿童保护义务随后生效；Ofcom 已对近百个服务启动调查，**小型服务不当然豁免**。
- **必须做**：第 9 条「适当且充分的非法内容风险评估」（评估用户群、各类优先违法内容风险、功能设计带来的传播风险、危害程度等），并在重大功能变更前重做、至少年度复核、留存记录以备 Ofcom 调取。
- **必须建**：第 10 条相应措施——内容审核策略、快速下架机制、易用的举报与投诉通道、条款透明与执行一致、审计留痕。
- **CSEA 报告义务**：自 2026-04-07 起，user-to-user 服务须向 NCA 报告发现的 CSEA 内容；需在 NCA 的行业报告门户注册并接入流程。境外主体报告 UK-linked 内容。
- **儿童保护**：即使声明 18+，仍需评估儿童实际可访问性；建议加年龄声明 + 不面向儿童设计 + 不投放儿童导向内容，并请律师确认义务范围。
- **罚则**：最高 £18m 或合格全球营收的 10%（取高者），严重情形可申请法院令要求支付/广告/ISP 中断服务。
- **费用**：Ofcom 有 fees regime（按 QWR 门槛），MVP 阶段大概率低于缴费门槛，但需自行确认并保留判断依据。

### 13.4 其他

- **消费者与广告**：分类信息中的商家内容需区分广告与 UGC，标注「推广」；置顶/认证商业化前复核消费者保护规则。
- **域名与主体**：`.co.uk` 注册规则、公司主体与条款中的服务提供者信息需明确。
- **Cookie / 推送**：Web Push 与营销邮件需单独同意，提供一键退订。
- **无障碍**：WCAG 2.1 AA，既是体验也是降低歧视投诉风险。

---

## 14. 部署与运维手册

### 14.1 `docker-compose.yml`（模板）

```yaml
services:
  db:
    image: postgis/postgis:16-3.4
    environment:
      POSTGRES_DB: ${PG_DB}
      POSTGRES_USER: ${PG_USER}
      POSTGRES_PASSWORD: ${PG_PASSWORD}
    volumes: ["pgdata:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${PG_USER} -d ${PG_DB}"]
      interval: 10s
      retries: 5

  redis:
    image: redis:7-alpine
    command: ["redis-server", "--appendonly", "yes"]
    volumes: ["redisdata:/data"]

  api:
    build: .
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    env_file: [.env]
    depends_on:
      db: { condition: service_healthy }
      redis: { condition: service_started }
    restart: unless-stopped

  worker:
    build: .
    command: celery -A app.worker worker -B -l info -Q fetch,notify,maintenance
    env_file: [.env]
    depends_on: [db, redis]
    restart: unless-stopped

  nginx:
    image: nginx:1.27-alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./certs:/etc/nginx/certs:ro
      - ./static:/usr/share/nginx/html:ro
    depends_on: [api]

volumes:
  pgdata:
  redisdata:
```

### 14.2 `.env.example`（prod 值由 KMS/密钥管理注入，禁止提交）

```ini
APP_ENV=prod
APP_SECRET_KEY=<32+ bytes random>
JWT_ACCESS_TTL=900
DATABASE_URL=postgresql+psycopg://user:pass@db:5432/ukcn
REDIS_URL=redis://redis:6379/0
R2_ACCOUNT_ID=
R2_ACCESS_KEY_ID=
R2_SECRET_ACCESS_KEY=
R2_BUCKET=ukcn-media
R2_PUBLIC_BASE=https://media.example.com
CONTACT_ENCRYPTION_KEY=<AES-GCM key>
OPENCC_MODE=s2t
DEFAULT_TIMEZONE=Europe/London
ENABLED_CITY_CODE=london
SOURCE_FETCH_ENABLED=true
SENTRY_DSN=
ICO_DPA_VERSION=2026-11-01
TOS_VERSION=2026-11-01
```

### 14.3 上线步骤（prod 首次）

1. 域名接入 Cloudflare（代理开启、WAF 托管规则、TLS Full Strict、HSTS、速率限制）。
2. VPS 选英国/西欧节点（伦敦优先，降低延迟并简化数据驻留叙事）；只开 80/443 与限源 SSH。
3. `git clone` → 写 `.env` → `docker compose up -d` → `docker compose exec api alembic upgrade head`。
4. 灌入城市、标签字典、200+ 条种子分类信息、3–5 个 L1 采集源（先 `is_enabled=false`，验证后开启）。
5. 冒烟：`/healthz`、注册、发帖、搜索、审核、导出、删除、采集源降级演练。
6. 打开监控与告警（错误率、P95、审核 SLA、源失败次数、磁盘与备份）。
7. 灰度：先小范围邀请，观察 1 周再开放注册。

### 14.4 备份、迁移与回滚

```bash
# 每日备份（cron，UTC 03:00）
docker compose exec -T db pg_dump -Fc -U "$PG_USER" "$PG_DB" \
  | gzip | r2-upload.sh backups/$(date -u +%F).dump.gz

# 发布（零数据丢失变更）
docker compose exec api alembic upgrade head
docker compose up -d --no-deps --build api worker

# 回滚（先代码，后按需回滚迁移；迁移必须写 downgrade）
docker compose exec api alembic downgrade -1
git checkout <previous-tag> && docker compose up -d --no-deps --build api worker
```

**回滚纪律**：任何涉及 `content` / `user_event` 的迁移必须可 downgrade 且先做影子表验证；禁止在生产直接改列类型。恢复演练每季度一次，未演练过的备份视为不存在。

### 14.5 监控与告警

| 指标 | 阈值 | 动作 |
|---|---|---|
| API 5xx 率 | > 1% / 5min | 告警 + 回滚评估 |
| 首页 P95 | > 1.5s / 10min | 查慢查询与缓存命中 |
| 审核队列 open 超时 | 有任一超 12h | 通知审核员与负责人 |
| 采集源连续失败 | ≥ 3 次 | 自动 disable + 告警 |
| 备份任务 | 未成功 | 立即告警 |
| 举报量突增 | 环比 > 3x | 人工介入，排查攻击 |

---

## 15. 测试与验证

| 层级 | 工具 | 必须覆盖的用例 |
|---|---|---|
| 单元 | pytest | S1 打分公式、有效期计算、简繁转换、去重 SimHash、敏感词、限流 |
| 接口 | pytest + httpx | 注册同意留痕、未验证手机禁止发布、联系方式访问审计、游标分页、幂等键重复提交、DSAR 导出/擦除级联 |
| 数据 | pytest + testcontainers | `chk_news_link` / `chk_listing_expiry` / `chk_licensed_source` 三个约束确实会拒绝非法写入 |
| E2E | Playwright | 注册→引导→发帖→审核→搜索→举报→裁决 |
| 采集 | 固定 fixture | 每个源适配器在 HTML 结构变化时的失败可被捕获并告警 |
| 合规 | 人工清单 | OSA 风险评估文档、条款版本、Cookie 默认拒绝、举报通道可达、CSEA 上报流程演练 |
| 性能 | k6 / locust | 首页 100 并发 P95 < 800ms |
| 恢复 | 演练 | 从 R2 备份恢复到干净环境并跑通冒烟 |

**「如何验证修复结果」统一标准**：修复必须附带一个可复现的失败用例 → 修复后该用例通过 → 在 dev 复现原场景 → prod 灰度观察 24h 指标。

---

## 16. 目录结构建议

```
ukcn/
├── app/
│   ├── main.py                 # FastAPI 入口
│   ├── internal/
│   │   ├── auth/  user_tag/  content/  listing/
│   │   ├── search/  moderation/  source/  event/
│   │   └── admin/  dsar/
│   ├── sources/adapters/       # 每个 L1 源一个适配器
│   ├── workers/                # celery tasks
│   ├── models/  schemas/  migrations/
│   └── core/                   # config, security, audit, crypto
├── web/                        # Vue 3 + SSR
├── deploy/                     # nginx.conf, compose, cron, backup.sh
├── tests/
├── docs/                       # 本文、OSA 风险评估、API 文档、条款
└── .env.example
```

---

## 17. 风险登记册

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|---|---|---|---|
| R1 | 单城市种子信息不足，上线即空城 | 高 | 致命 | 上线前人工录入 200+ 条；与本地社团/商家合作供稿；先做「落地清单」这类编辑型内容兜底 |
| R2 | 新闻版权（NLA）侵权 | 中 | 高 | 只走 L1 开放源；数据层禁止全文；采购许可前不碰 L2 |
| R3 | OSA 义务未履行被调查 | 中 | 高 | 上线前完成书面风险评估、举报与下架机制、CSEA 上报注册；律师复核 |
| R4 | 分类信息诈骗导致口碑崩塌 | 高 | 高 | 手机验证、前 3 帖必审、联系方式受控、12h SLA、抽检 |
| R5 | 中文搜索效果差 | 高 | 中 | MVP 明确用 trgm + 分类筛选，不承诺全文检索；P2 上 IK |
| R6 | 采集源结构变更/失效 | 高 | 中 | 适配器 + 健康检查 + 自动降级；资讯非核心链路 |
| R7 | GDPR 同意/擦除实现遗漏 | 中 | 高 | 数据层留痕 + DSAR 工单 + 上线前合规清单逐项验收 |
| R8 | 早期上算法/微服务/自建转码导致成本失控 | 中 | 高 | 本文「不做清单」作为排期护栏 |
| R9 | BST/GMT 夏令时导致有效期与提醒错乱 | 中 | 低 | 全链路存 UTC，仅展示层按 `Europe/London` 转换；写专门单测 |
| R10 | 简繁转换改写 UGC 原文引发争议 | 低 | 中 | 只在显示层转换，原文不可变 |

---

## 18. 里程碑（6 周 MVP）

| 周 | 交付 | 验收 |
|---|---|---|
| W1 | 需求冻结、原型、DDL 评审、合规清单与 OSA 风险评估初稿 | 本文评审通过；律师确认关键条款 |
| W2 | 脚手架、Compose、CI、账号与引导、标签体系 | 可注册登录、可改标签 |
| W3 | 分类信息发布/列表/详情/联系方式受控、图片上传 | US-02/03 通过 |
| W4 | UGC 图文、规则流、搜索、审核后台与举报闭环 | US-01/04/05/06/07 通过 |
| W5 | 3–5 个 L1 采集源 + 埋点 + 繁简 + DSAR + 种子数据灌入 | US-08/09/10 通过；种子 ≥ 200 条 |
| W6 | 灰度、监控告警、备份恢复演练、性能与合规验收 | §7 全清单通过 |

后续：M2（2–3 月）视频/私信/加权推荐/商家认证；M3（6 月+）召回排序、OpenSearch、第二城市、App。

---

## 19. 附录

### 19.1 常见坑速查

1. 一上来做推荐算法、微服务、自建视频转码 —— 三大烧钱点，**全部推到 P2**。
2. 多城市同时铺 —— 每个城市都是空城；先做透一个。
3. 分类信息没有过期机制 —— 三个月后满屏死贴。
4. 纯 SPA 不做 SSR/SEO —— 本地生活最依赖搜索流量，却搜不到。
5. 认为「只放摘要和链接就不涉及版权」—— 英国有 NLA 集中许可，需按 §13.2 处理。
6. 认为「小平台不用管 OSA」—— 风险评估义务适用于所有受监管 user-to-user 服务。
7. 联系方式直接渲染在 HTML —— 被批量爬取后用户被骚扰，信任瞬间归零。
8. 时间用本地时间存储 —— BST/GMT 切换时有效期与提醒全乱。
9. 埋点等「以后再加」—— 没有行为数据，P1 的推荐永远做不了。
10. 采集阻塞主链路 —— 源挂了整个首页打不开。

### 19.2 术语

| 术语 | 含义 |
|---|---|
| OGL v3.0 | Open Government Licence，英国政府开放数据许可，通常允许商业复用但需署名 |
| NLA | NLA Media Access，英国报业版权集体许可机构 |
| OSA 2023 | Online Safety Act 2023，Ofcom 监管的在线安全法 |
| CSEA | Child Sexual Exploitation and Abuse 内容，2026-04-07 起有 NCA 报告义务 |
| DSAR | Data Subject Access Request，数据主体访问/导出/擦除请求 |
| PECR | Privacy and Electronic Communications Regulations，管 Cookie 与电子营销 |
| PWA | Progressive Web App，可安装的 Web 应用 |
| trgm | PostgreSQL `pg_trgm`，三元组模糊匹配，中文搜索的 MVP 兜底 |

### 19.3 参考来源（2026-11-08 检索）

- legislation.gov.uk — Online Safety Act 2023, Part 3 Ch.2（第 9/10 条非法内容风险评估与措施）
- Ofcom — Roadmap to regulation（义务生效时间、执法进展、CSEA 报告、fees regime）
- Ofcom — 执法公告（罚则上限 £18m / 全球营收 10%）
- GOV.UK — Online Safety Act 非法内容实践准则修订草案（2026）
- NLA Media Access — Corporate Website Republishing Licence 与价目（2026-04 起适用）、What We Do、eClips Web FAQ
- 应用宝 / Google Play — 华人头条、华人168 产品功能描述

---

**待裴总拍板后，下一轮可直接交付**：① 可运行 MVP 代码脚手架（含上述 DDL 与接口），② OSA 非法内容风险评估文档模板，③ 种子内容采编清单，④ 界面原型稿。
