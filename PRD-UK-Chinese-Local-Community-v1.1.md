# 海外圈 Web — PRD + 技术方案

> **当前准绳：§26（全球布局）+ §27（媒体布局与内容优先推荐）+ §28（自动定位与开通权限）+ §29（首屏精简与 X 式帖子卡）+ §30（多房间小圈子、评论、@/#、AI 关键词与顶部搜索）+ §31（「添加频道」改为「创建房间」、房间挂靠官方频道）+ §32（房间轻量化与更新通知；房间归属规则由 §34 覆盖）+ §33（国家法域开通范围与发帖城市话题）+ §34（官方频道与用户房间层级，2026-11-10）+ §35（导航名称调整）+ **§36（国际化三层模型与房间所属频道，2026-11-11，最高优先）**。**产品定位、国家数据隔离、国际频道共享、当前国家切换与房间所属频道以 §36 为准，§36 覆盖 §0.1、§26.1、§26.2、§28、§33.3、§33.4、§34 中相冲突的表述。** 房间层级、必选父频道与房间发现位置以 §34 为准，并覆盖 §31 / §32 中相冲突的历史规则。** 本文 §0–§25 中所有英国专属内容降级为 `jurisdiction='UK'` 的**法域实例与配置记录**保留，不再是全局规则；产品边界、区域模型与推荐打分输入以 §26.1 为准；**推荐输出形态、默认站内播放与媒体布局以 §27 为准**（§27 与 §20–§26 冲突处以 §27 为准）；**默认区域的自动定位、定位信号与「谁有权创建区域 / 频道」的治理边界以 §28 为准**；**首屏信息架构、帖子卡结构、加入按钮位置与媒体播放控件的取舍以 §29 为准**（§29 只覆盖渲染层，不改业务规则）；**「官方频道 vs 用户房间」的命名与权限、一人多房间、房间留言评论、`@用户名` / `#关键词`、官方 AI 自动关键词与搜索入口位置以 §30 为准**（§30 与 §22.6 冲突处以 §30 为准）；**「添加频道」入口改为「创建房间」、房间挂靠官方频道、房间承载「元数据 + 官方外链」以 §31 为准**；**房间类型 / 版权确认门槛、房间卡加入与更新通知以 §32 为准；房间必须挂靠官方频道并嵌套展示以 §34 为准**（§34 覆盖 §32 的可选挂靠与一级目录旧规则）。文件名保留 `UK-` 前缀仅为维持历史引用，不代表产品边界。

| 项目 | 内容 |
|---|---|
| 文档版本 | **v1.1 + §26 – §35 + §36（含 §36.9 – §36.17，2026-11-12）— 当前准绳** |
| 产品名 | **海外圈**（简繁同形；2026-11-11 Rio 拍板，§36.14） |
| 项目代号 | CN Channels / Global（内部代号，不对用户展示；原 UKCN Local，保留作 UK 法域实例名） |
| 交付对象 | 裴总 |
| 产品边界 | **国际化中文频道社区**（§36）：国际频道各国共享同一份数据；每个开通国家有独立的分类数据；当前国家单选，不叠加 |
| 首启法域 | **英国（UK）· 首城伦敦**，是第一个开通国家；其余国家按 §26.9 的 G2 逐个开通，未开通国家只显示国际频道 |
| 形态 | Web 优先，PWA 可安装；暂不做原生 App |
| 历史版本 | `PRD-UK-Chinese-Local-Community-v1.0.md`（算法推荐流模型，保留备查，**不再作为开发依据**） |
| 关联目录 | `C:/Users/Administrator/Documents/uk` |
| 增补章节 | §20 三 Tab · §21 内容供给 · §22 房间 · §23 电影视频 · §24 外链播放 · §25 设计规范 · §26 全球布局 · §27 媒体布局与内容优先推荐 · §28 自动定位与开通权限 · §29 首屏精简与 X 式帖子卡 · §30 多房间小圈子 / 评论 / @# / AI 关键词 / 顶部搜索 · §31 创建房间（挂靠官方频道） · §32 房间轻量化 / 上频道 / 加入通知 · **§33 国家法域开通范围 / 发帖城市话题 · §34 官方频道与用户房间层级 · §35 导航名称调整** |
| 交互原型 | `prototype-x-style.html` **v12**（官方频道内嵌用户房间；英国租房多图帖、竖屏视频封面与房间帖子示例）、`prototype-collection-room.html` **v6**（创建去强制类型/版权确认 + 更新通知开关）、`publish-content.html`（官方 AI 自动关键词）、`design-system/preview.html` **v1.7**（组件展示页第 14 节）、`design-system/MASTER.md` **v1.7** |

## 修订摘要：v1.0 → v1.1

| 处置 | 内容 |
|---|---|
| ✅ 保留 | 统一内容池 `content`、L1/L2/L3 采集源分级、审核风控、UK GDPR / OSA / NLA 合规框架、Vue3+FastAPI+PostgreSQL/PostGIS 选型、Docker Compose 部署方案、同城分类信息 |
| 🔄 替换 | 信息架构：功能分栏 → **频道**；注册引导：兴趣问卷 → **选频道**；首页：算法打分排序 → **订阅频道的时间倒序流**；AI 职责：推荐排序 → **归类、去重、聚类、摘要、翻译、风控** |
| ➕ 新增 | 三层频道体系、频道目录与新手组合包、频道主与投稿、AI 整理层与分层降本、事件聚类、人工修正闭环、`channel` / `channel_subscription` / `channel_item` / `ai_result` / `event_cluster` / `curation_feedback` 六张表、频道相关 API、Web Push 与未读语义 |
| ❌ 删除 | 注册兴趣标签问卷、S1 打分公式、三阶段推荐算法演进路线、把个性化推荐作为首期目标 |

**为什么改**：算法推荐流需要先积累海量行为数据，冷启动期效果差、不可解释；频道订阅把「猜你喜欢」换成「你订了什么」，订阅关系本身就是最准、最可解释且可随时撤回的显式兴趣信号，同时降低技术门槛与隐私解释成本。

---

## 0. 前置假设（需裴总确认，未确认前按此执行）

| 编号 | 假设 | 若不成立 |
|---|---|---|
| A1 | 团队 ≤ 3 人，至少 1 人能写 Python + Vue | 纯外包需改无代码方案，整体重做 |
| A2 | 起步预算 ≤ £200/月基础设施 + ≤ £100/月 AI API | 超预算则 AI 层全改本地模型 |
| A3 | 首版服务范围明确排除中国大陆地区（商店地区限制 + ToS 声明 + 无人民币结算 / 大陆客服 / 大陆加速）；服务器部署英国/欧洲节点 | 若不成立需单独法律意见，见 §26.3；不得默认全球可及 |
| A4 | MVP 无在线支付、无电商、无直播 | 涉及支付需 Stripe + 消费者法合规 |
| A5 | 上线前可人工准备 200+ 条种子内容与 ≥ 15 个非空频道 | 空频道 = 产品失败 |
| A6 | 用户限定 18+ | 见 §13.3，降低但不豁免儿童相关义务 |
| A7 | 可使用第三方 LLM API（需签 DPA、评估跨境传输） | 若禁止，AI 层改用本地小模型，摘要质量下降 |
| A8 | `region` / `jurisdiction` 从第一天就是一等数据维度，合规逻辑配置驱动（§26.5） | 若首版图省事写死 UK，开第二个法域需全量返工 |

### 0.1 一句话定位

> **一款国际化的中文频道社区：国际频道各国共享，你所在的开通国家另有一套本国分类频道（租房、二手、招聘等）。**

> 本节原为「英国本地信息」口径，已由 §26.1 修订为全球口径，2026-11-11 再由 §36 修订为国际化三层模型；UK 是第一个开通国家而非产品边界。**v1.0 文档中的「英国本地生活信息站」定位表述全部作废**（v1.0 文件不改，仅保留备查）。

### 0.2 明确不做清单（MVP 边界）

- ❌ 算法主导的个性化信息流 / 协同过滤 / 排序模型
- ❌ 抓取英国新闻全文、全文翻译、转载原文图片
- ❌ 托管视频文件、自建转码、直播
- ❌ 多个法域同时启用官方频道与合规（国家分类数据、平台官方频道、内容采集与法域合规按 §26.9 逐个开；未开通国家没有国家分类数据，见 §36）
- ❌ 微服务 / K8s / 原生 App

---

## 1. 市场判断与模型选择

### 1.1 已有竞品（2026-11 调研）

| 产品 | 形态 | 与本项目重叠点 |
|---|---|---|
| 华人头条 | 资讯 + 分类信息 + 社交 + 短视频，注册选兴趣标签「定制头条」，覆盖 69+ 国家 | 用户最初描述的「算法推送」形态已被完整实现 |
| 华人168 | 北美本地生活：招聘/租房/商家/二手/社群，认证发布 + 人机同审 | 分类信息与信息质量管控的成熟范式 |
| Telegram 频道 | 用户主动加入频道，按时间消费消息，频道主运营 | **本版直接借鉴的交互模型**，但 Telegram 不做 AI 整理，也无中文本地化 |

**结论**：功能清单不构成壁垒。差异化在「英国本地 + 中文简繁 + AI 整理后的信息密度与可信度」。

### 1.2 英国市场机会

1. 中文行政/生活信息极度分散：eVisa、NINo、GP 注册、council tax、押金保护、垃圾分类、交通，散落在 GOV.UK、地方议会、NHS、TfL、大学官网与社群帖子里。
2. 简繁并存的中文社群，主流竞品以简体为主；首版即做 `zh-Hans` / `zh-Hant` 双语文案与显示层转换。
3. 落地新人（0–3 个月）与学生人群刚需明确，且愿意主动发布内容。
4. 竞争强度低于北美。

### 1.3 两种模型对比（决策依据）

| 维度 | 算法推荐流（v1.0） | **频道订阅流（v1.1）** |
|---|---|---|
| 冷启动 | 需 ≥10 万条行为事件才有效 | 采集内容一入库即可用，首日可用 |
| 兴趣信号 | 注册问卷 + 埋点推断，弱且滞后 | 订阅/退订即显式信号，实时且可撤回 |
| 可解释性 | 黑箱，用户不知为何看到 | 「因为我加入了 X 频道」，完全可解释 |
| 隐私成本 | 需持续画像、行为追踪 | 只需保存订阅关系，数据最小化 |
| 工程复杂度 | 特征、召回、排序、AB 实验 | 关联表 + 时间倒序查询 |
| 用户控制感 | 弱，容易被骂「信息茧房」 | 强，退订即生效 |
| 风险 | 算法推荐在 OSA 下需额外评估放大效应 | 无排序放大，风险评估更简单 |
| 代价 | — | 需要人工维护频道目录与质量，否则退化成 RSS 阅读器 |

### 1.4 成功指标（上线后 8 周）

| 指标 | 目标 |
|---|---|
| 非空频道占比 | ≥ 90%（每个官方频道日更新 ≥ 3 条） |
| 新用户加入频道数 | 中位数 ≥ 4 |
| 频道次日回访率 | ≥ 30% |
| 自动频道分类准确率 | 抽检 ≥ 90% |
| AI 摘要事实一致性 | 抽检 ≥ 95%（禁止编造） |
| 举报处理中位时长 | ≤ 12 小时 |
| 单条内容 AI 成本 | ≤ £0.002（分层降本后） |

**不把 PV/DAU 作为首期北极星指标**。

---

## 2. 频道体系设计（本版核心）

### 2.1 三层频道

| 层 | 创建者 | 内容来源 | AI 角色 | 解决的问题 |
|---|---|---|---|---|
| **L1 官方自动频道** | 平台 | L1 开放许可采集源 | 全自动：去重 → 聚类 → 分类 → 摘要 → 翻译 → 风控 | 保证「打开就有内容」，不依赖 UGC 冷启动 |
| **L2 官方精选频道** | 平台编辑 / 志愿者 | L1 候选池 + 人工挑选、置顶、写按语 | AI 初筛 + 人把关 | 保证质量与「人味」，让用户有每天回来的理由 |
| **L3 用户自建频道** | 用户（频道主） | 频道主发帖 + 用户投稿 | AI 辅助分类与审核 | 承接 UGC、同城分享、社团圈子，社区自增长 |

> **最重要的产品判断**：Telegram 频道好看是因为频道主在里面说话。纯机器聚合的频道会退化成 RSS 阅读器。L2 的人工按语与 L3 的频道主是留存的真正来源，不能省。

### 2.2 频道目录（首版示例，18 个，按国家分组并按类别筛选）

**全国频道**：`签证与政策`（GOV.UK/Home Office）、`华人要闻`、`英镑与民生`（ONS/BoE 公开数据）、`天气与交通`（Met Office/TfL/National Rail）、`留学与大学`（各校 RSS）、`英超与体育`、`影视与娱乐`、`科技与数码`、`育儿与家庭`

**英国频道目录**：`英国租房`、`英国兼职`等全国频道按英国分组；`伦敦二手`、`伦敦同城活动`等城市主题频道仍按英国分组，伦敦只作为频道内容提示。频道可按**房产、招聘、市场、生活、交流、活动、其他**分类筛选。分类由平台维护，用户不可新增或改名。

**准入规则**：官方频道总数 ≤ 25；新建频道须连续 3 天日更新 ≥ 3 条才允许公开，否则自动隐藏或合并；目录按国家分组，官方服务开通按国家法域判断。

### 2.3 新手组合包（替代注册问卷）

首次进入不填问卷，直接给 3 个一键包：

- 「伦敦落地包」= 落地必读 + 签证与政策 + 英国租房 + 英国兼职 + 二手市场
- 「留学生包」= 留学与大学 + 伦敦二手 + 同城活动 + 问答互助
- 「生活娱乐包」= 华人要闻 + 英超与体育 + 影视与娱乐 + 伦敦吃喝

用户可一键加入、逐个退订、随时在频道目录补充。**订阅关系即兴趣画像**，无需 `user_tag.onboarding` 数据。

### 2.4 频道主与投稿（L3）

- 创建条件：手机验证 + 后台审核通过；一个用户最多 3 个频道。
- 频道主权限：发公告、置顶、审核投稿、开关投稿、移除内容、设置公开/不公开。
- 投稿：用户可向允许投稿的频道投稿，频道主或审核队列裁决。
- 平台责任：L3 内容与平台内容同样受 OSA 与审核策略约束，频道主操作全部写 `audit_log`。

### 2.5 个性化放在哪一层

**不做逐条行为画像；保留透明的频道与内容推荐。** 频道发现可基于「订阅了 A、B 的人也加入了 C」的共现规则，候选集 ≤25 个频道，用户可选择不使用。后续 §27 增加的「为你推荐」内容流沿用明确的频道级参数（订阅共现 0.40、区域匹配 0.30、频道活跃 0.20、编辑精选 0.10），再乘内容新鲜度；已订阅频道内容降权 0.12，避免重复。它不得使用逐条点击、停留或点赞行为建立画像，每条推荐必须显示理由，并保留「正在关注」严格时间序作为直接可选的非画像信息流。算法细节以 §26–§29 为准。

---

## 3. 用户画像与用户故事

| Persona | 最痛的事 | 我们给什么 |
|---|---|---|
| P1 落地新人（0–3 月） | 不知道办卡、GP、押金、council tax 从哪下手 | 「落地包」频道组合 + 精选频道的按语 |
| P2 在读学生 | 找合租、二手、兼职、同乡 | 本地频道 + 用户自建校园频道 |
| P3 常住家庭 | 找可靠华人服务与本地活动 | 认证商家频道、活动频道 |
| P4 频道主 | 想经营自己的圈子/商家/社团 | 自建频道、公告置顶、投稿管理 |
| P5 运营编辑 | 想控质量、修正 AI 分类 | L2 精选后台 + 修正回流 |

### 3.1 P0 用户故事与验收标准

| ID | 用户故事 | 验收 |
|---|---|---|
| US-01 | 新用户想跳过问卷，直接挑频道看内容 | 首屏即频道目录 + 组合包；未登录可浏览公开频道；注册 ≤ 40 秒 |
| US-02 | 用户想加入/退订/静音频道 | 订阅变更 ≤ 1 次点击，首页与未读数即时更新 |
| US-03 | 用户想按时间顺序看已订阅频道的新内容 | `/me/feed` 严格时间倒序，无算法重排；支持置顶与未读分隔线 |
| US-04 | 用户想看某频道全部历史 | 频道页游标分页，支持置顶公告与按语 |
| US-05 | 用户想知道有新内容 | 未读计数 + 频道角标；Web Push / 邮件日报需单独同意 |
| US-06 | 运营想让 AI 把一条新抓的内容自动放进正确频道 | 采集 → 聚类 → 分类 → 摘要 → 入库 ≤ 5 分钟，置信度可见 |
| US-07 | 编辑想修正错误分类与摘要 | 后台一键改频道/改摘要，写入 `curation_feedback` 并回流 |
| US-08 | 用户想发布图文/视频链接/分类信息 | 可发到自己的频道或向允许投稿的频道投稿，进审核队列 |
| US-09 | 用户想举报可疑内容 | ≤ 2 次点击生成工单，可见处理状态 |
| US-10 | 用户想导出/删除个人数据 | 自助发起，7 天内完成，订阅关系一并清理 |
| US-11 | 用户想用繁体阅读 | 界面与 AI 摘要双语；UGC 仅在显示层转换，原文不改写 |

---

## 4. AI 整理层设计

### 4.1 AI 到底做什么（不做排序）

| 步骤 | 说明 | 价值 |
|---|---|---|
| 归一化 | 异构源 → 统一 schema（title / url / published_at / source / licence） | 工程基础 |
| **去重与事件聚类** | SimHash + embedding 相似度，同一事件的 10 个源聚成 1 张卡片，展示「N 个来源」并逐一回链 | **最有价值**：解决刷屏，同时强化来源署名 |
| 分类路由 | 决定进哪个（可多个）频道，给出置信度 | 替代人工分拣 |
| 中文摘要 | 英文源 → ≤200 字中文提炼；**不是全文翻译、不是改写复制** | 中文用户的核心价值 |
| 翻译与繁简 | 标题与摘要生成 hans/hant 双版本（OpenCC） | 英国本地差异点 |
| 质量与风控 | 广告、标题党、过期、诈骗、违法风险打分，低质拦截 | 对应 OSA 与信任 |
| 实体抽取 | 城市、机构、时间、价格、地点 | 支持频道筛选与结构化展示 |

### 4.2 分层降本（硬性要求）

| 层 | 手段 | 目标覆盖 | 成本 |
|---|---|---|---|
| L0 | 源自带分类、URL 规则、关键词白名单、正则 | ~65% | 0 |
| L1 | embedding 与各频道「质心」相似度（本地小模型，如 bge-small） | ~25% | 极低，可自托管 |
| L2 | LLM：仅处理低置信条目 + 生成摘要 + 事件标题 + 英译中 | ~10% | 主要成本 |

工程约束：

- 按 `content_hash` 缓存分类结果，重复内容不重复调用；去重后不再进入 L2。
- L2 攒批（≥10 条或 60s 超时），设置日 token / 日费用双上限，超限自动降级为 L1 结果。
- LLM 不可用时标 `ai_status='degraded'`，内容仍以 L0/L1 结果入库，**不阻塞频道更新**。
- 每条 AI 调用记录 model / version / tokens，进 `ai_result`，可审计、可复算、可回放。
- 摘要红线：≤200 字、必须附原文链接与来源署名、禁止生成原文没有的事实、禁止全文翻译；发布前做事实一致性抽检。

### 4.3 人工修正闭环

编辑在后台执行「移动频道 / 增删频道 / 改摘要 / 驳回」→ 写 `curation_feedback(before, after)` → 每周离线任务：

1. 用修正样本重算各频道 embedding 质心；
2. 抽取高频修正作为 L2 的 few-shot 示例；
3. 输出分类准确率报表，低于 90% 的频道触发规则复审。

**AI 不是一次性部署，是有回路的系统**——这是保证长期质量的关键。

---

## 5. 功能清单与信息架构

### 5.1 P0（6 周 MVP）

| 模块 | 功能 |
|---|---|
| 频道目录 | 按城市/主题分组、搜索频道、频道详情与最近更新、组合包一键加入 |
| 订阅 | 加入 / 退订 / 静音 / 通知偏好 / 我的频道 / 未读计数 / 标记已读 |
| 频道流 | 单频道时间倒序流（含置顶公告、精选按语）、`/me/feed` 聚合已订阅频道 |
| AI 整理 | L0 规则 + L1 embedding 分类 + 事件聚类 + L2 摘要（含降级与缓存） |
| 采集 | 3–5 个 L1 开放源 + 适配器 + 合规闸门 + 健康看板 |
| UGC | 发图文帖 / 视频链接卡片 / 分类信息；可发到自己的频道或投稿；图片受控 |
| 频道主 | 创建频道（审核）、公告、置顶、投稿管理 |
| 审核 | 敏感词 + 新用户前 3 帖必审 + 举报工单 + 后台队列 + 编辑修正回流 |
| 搜索 | 频道内搜索、全站关键词（`pg_trgm` 兜底） |
| 合规基础 | 隐私政策、Cookie 与推送同意、条款、同意留痕、DSAR 自助导出/擦除 |
| 后台 | 频道管理、采集源健康、AI 质量看板、审核队列、用户封禁 |

### 5.2 P1 / P2

**P1（2–3 月）**：Web Push / 邮件日报、频道推荐（共现规则）、商家认证与置顶、视频云转码（≤60s）、私信、多城市模板化复制、SEO 频道落地页、运营看板。
**P2（6 月+）**：频道内容级轻排序（仅按热度，不做个性化画像）、OpenSearch + IK、原生 App、支付与商业化、事件专题页。

### 5.3 前台结构

```
频道目录(首屏) ─┬─ 组合包(一键加入)
               ├─ 频道页(时间倒序流 / 公告 / 投稿)
               ├─ 我的订阅(未读角标 / 聚合 feed)
               ├─ 搜索(频道 / 内容)
               ├─ 发布(选频道 → 表单 → 审核)
               └─ 我的(资料 / 简繁 / 我的频道 / 隐私与数据)
```

### 5.4 首次进入流程（替代 v1.0 注册问卷）

```
游客可浏览公开频道 → 点「加入」触发轻注册(邮箱+手机)
→ 同意条款逐项勾选(留痕) → 自动带入刚才的频道
→ 弹组合包推荐(可跳过) → 简繁偏好按浏览器语言推断 → 进入我的订阅
```

必填只剩：城市、简繁偏好（可推断）、同意条款。身份/落地阶段改为选填，只用于推荐组合包。

---

## 6. 分发与订阅语义

| 语义 | 规则 |
|---|---|
| 排序 | 严格 `added_at DESC` 时间倒序；置顶公告固定在前；不做算法重排 |
| 未读 | 以 `channel_subscription.last_read_at` 与 `channel_item.added_at` 比较计算，冗余 `unread_count` 便于展示 |
| 聚合 feed | 用户已订阅且未静音频道的 `channel_item` 合并按时间倒序；同一内容出现在多个频道时**只展示一次**（按 content_id 去重） |
| 事件卡片 | 同一 `event_cluster` 的多源内容合并为一张卡，展开可见各来源与回链 |
| 静音 | 静音频道仍可进入查看，但不进聚合 feed、不推送 |
| 推送 | Web Push / 邮件日报需单独同意（PECR），默认关闭，一键退订；突发重要信息（如签证政策变更）单独标注，不做强推 |
| 失效内容 | 分类信息类频道条目到期自动下架；采集资讯卡片保留但标注日期 |

---

## 7. 验收总清单

- [ ] 游客可浏览公开频道；加入触发 ≤40 秒轻注册
- [ ] 加入/退订/静音后，聚合 feed 与未读数即时变化
- [ ] 聚合 feed 严格时间倒序，无算法重排，同内容跨频道不重复
- [ ] 一条新抓内容在 5 分钟内完成聚类 → 分类 → 摘要 → 入频道
- [ ] LLM 不可用时采集链路仍正常，`ai_status='degraded'` 可查
- [ ] 编辑修正写入 `curation_feedback`，周任务能重算质心
- [ ] 事件卡片展示 N 个来源且每个都可回链原文，来源署名显著
- [ ] 全文/原图不落库，`allow_fulltext=false` 全源生效
- [ ] 用户可创建频道、发公告、投稿、举报，全流程有审计日志
- [ ] 繁体界面与 AI 摘要双语可用，UGC 原文不被改写
- [ ] 举报 → 工单 → 裁决 → 通知 → 审计闭环
- [ ] DSAR 导出/擦除级联清理订阅关系与频道
- [ ] 备份恢复演练成功；干净环境 `docker compose up -d` 拉起全栈

---

# 技术方案

## 8. 数据模型（PostgreSQL 16 + PostGIS）

### 8.1 设计原则

1. **统一内容池** `content` 用 `type` 区分 news/post/video/listing，共用审核、搜索、埋点（v1.0 保留）。
2. **内容与频道多对多**：`channel_item` 关联，一条内容可进多个频道；`score` 存**归类置信度/精选优先级**，不是个性化排序分。
3. **订阅关系即画像**：取消 `user_tag.onboarding`，保留 `user_tag` 仅用于频道推荐与后台标签。
4. **AI 结果独立可复算**：`ai_result` 记录模型版本、层级、token、状态，支持回放与重算。
5. **所有内容有有效期**：分类信息强制 `expires_at`。
6. 联系方式受控加密、软删除 + GDPR 硬擦除并存。

### 8.2 DDL

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS citext;

CREATE TYPE content_type   AS ENUM ('news','post','video','listing');
CREATE TYPE content_status AS ENUM ('draft','pending','published','rejected','expired','deleted');
CREATE TYPE script_type    AS ENUM ('hans','hant','mixed','en');
CREATE TYPE channel_kind   AS ENUM ('official_auto','official_curated','user_created');
CREATE TYPE channel_vis    AS ENUM ('public','unlisted','private');

CREATE TABLE city (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(16) UNIQUE NOT NULL,
  name_hans varchar(64) NOT NULL, name_hant varchar(64) NOT NULL,
  name_en varchar(64) NOT NULL, country char(2) NOT NULL DEFAULT 'GB',
  timezone varchar(64) NOT NULL DEFAULT 'Europe/London',
  centre geography(Point,4326), is_enabled boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app_user (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE, phone varchar(32) UNIQUE, password_hash text,
  display_name varchar(40) NOT NULL,
  city_id uuid REFERENCES city(id),
  script_pref script_type NOT NULL DEFAULT 'hans',
  locale varchar(12) NOT NULL DEFAULT 'zh-Hans',
  identity varchar(16), arrival_stage varchar(16),     -- 选填，仅用于组合包推荐
  status varchar(16) NOT NULL DEFAULT 'active',
  phone_verified boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz
);
CREATE INDEX idx_user_city ON app_user(city_id) WHERE deleted_at IS NULL;

CREATE TABLE tag (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  slug varchar(48) UNIQUE NOT NULL,
  name_hans varchar(48) NOT NULL, name_hant varchar(48) NOT NULL,
  category varchar(24) NOT NULL, is_active boolean NOT NULL DEFAULT true
);
CREATE TABLE user_tag (
  user_id uuid REFERENCES app_user(id) ON DELETE CASCADE,
  tag_id uuid REFERENCES tag(id) ON DELETE CASCADE,
  weight numeric(4,3) NOT NULL DEFAULT 1.000,
  source varchar(16) NOT NULL DEFAULT 'channel_inferred',
  PRIMARY KEY (user_id, tag_id, source)
);

CREATE TABLE source (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(96) NOT NULL,
  kind varchar(24) NOT NULL,                 -- 'api','rss','ogl','licensed','manual'
  base_url text NOT NULL, licence_ref text, licence_expiry date,
  robots_checked boolean NOT NULL DEFAULT false,
  rate_limit_qpm int NOT NULL DEFAULT 6,
  allow_fulltext boolean NOT NULL DEFAULT false,
  is_enabled boolean NOT NULL DEFAULT false,
  last_fetch_at timestamptz, last_error text,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_licensed_source CHECK (
    is_enabled = false OR allow_fulltext = false OR licence_ref IS NOT NULL)
);

-- 统一内容池
CREATE TABLE content (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type content_type NOT NULL,
  status content_status NOT NULL DEFAULT 'pending',
  author_id uuid REFERENCES app_user(id) ON DELETE SET NULL,
  source_id uuid REFERENCES source(id) ON DELETE SET NULL,
  city_id uuid REFERENCES city(id),
  title varchar(200) NOT NULL, summary varchar(500), body text,
  script script_type NOT NULL DEFAULT 'hans',
  canonical_url text, cover_key text,
  media jsonb NOT NULL DEFAULT '[]'::jsonb,
  extra jsonb NOT NULL DEFAULT '{}'::jsonb,
  content_hash varchar(64) UNIQUE,          -- 去重与 AI 缓存键
  ai_status varchar(16) NOT NULL DEFAULT 'pending',  -- pending/ok/degraded/failed
  event_cluster_id uuid,
  expires_at timestamptz, published_at timestamptz,
  view_count int NOT NULL DEFAULT 0, like_count int NOT NULL DEFAULT 0,
  report_count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(), deleted_at timestamptz,
  CONSTRAINT chk_news_link CHECK (type <> 'news' OR canonical_url IS NOT NULL),
  CONSTRAINT chk_listing_expiry CHECK (type <> 'listing' OR expires_at IS NOT NULL)
);
CREATE INDEX idx_content_published ON content(published_at DESC)
  WHERE status='published' AND deleted_at IS NULL;
CREATE INDEX idx_content_title_trgm ON content USING gin (title gin_trgm_ops);
CREATE INDEX idx_content_body_trgm ON content USING gin (body gin_trgm_ops);
CREATE INDEX idx_content_expiry ON content(expires_at) WHERE expires_at IS NOT NULL;

CREATE TABLE content_tag (
  content_id uuid REFERENCES content(id) ON DELETE CASCADE,
  tag_id uuid REFERENCES tag(id) ON DELETE CASCADE,
  weight numeric(4,3) NOT NULL DEFAULT 1.000,
  PRIMARY KEY (content_id, tag_id)
);

CREATE TABLE listing_ext (
  content_id uuid PRIMARY KEY REFERENCES content(id) ON DELETE CASCADE,
  category varchar(24) NOT NULL, price_gbp numeric(10,2), price_unit varchar(16),
  area_name varchar(96), location geography(Point,4326),
  is_verified boolean NOT NULL DEFAULT false,
  verified_by uuid REFERENCES app_user(id),
  refresh_count int NOT NULL DEFAULT 0, last_refreshed timestamptz
);
CREATE INDEX idx_listing_geo ON listing_ext USING gist(location);
CREATE TABLE listing_contact (
  content_id uuid PRIMARY KEY REFERENCES content(id) ON DELETE CASCADE,
  payload bytea NOT NULL,                  -- AES-GCM 密文
  created_at timestamptz NOT NULL DEFAULT now()
);

-- ===== v1.1 频道模型 =====
CREATE TABLE channel (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  code varchar(48) UNIQUE NOT NULL,
  name_hans varchar(64) NOT NULL, name_hant varchar(64) NOT NULL,
  description_hans text, description_hant text,
  kind channel_kind NOT NULL,
  visibility channel_vis NOT NULL DEFAULT 'public',
  city_id uuid REFERENCES city(id),        -- NULL = 全国频道
  owner_id uuid REFERENCES app_user(id),   -- 仅 user_created
  group_name varchar(32),                  -- '全国' / '伦敦' / '主题'
  is_active boolean NOT NULL DEFAULT false,
  min_daily_items int NOT NULL DEFAULT 3,
  subscriber_count int NOT NULL DEFAULT 0,
  last_item_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_owner CHECK (kind <> 'user_created' OR owner_id IS NOT NULL)
);
CREATE INDEX idx_channel_city_kind ON channel(city_id, kind) WHERE is_active;

CREATE TABLE channel_subscription (
  user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  channel_id uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  is_muted boolean NOT NULL DEFAULT false,
  notify varchar(16) NOT NULL DEFAULT 'none',   -- none/push/daily
  last_read_at timestamptz NOT NULL DEFAULT now(),
  unread_count int NOT NULL DEFAULT 0,
  joined_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, channel_id)
);
CREATE INDEX idx_sub_user ON channel_subscription(user_id, is_muted);

CREATE TABLE channel_item (
  channel_id uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  pinned boolean NOT NULL DEFAULT false,
  curator_note_hans text, curator_note_hant text,  -- L2 精选按语
  ai_confidence numeric(4,3),
  added_by varchar(16) NOT NULL DEFAULT 'ai',       -- ai/editor/owner/user
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (channel_id, content_id)
);
CREATE INDEX idx_channel_feed ON channel_item(channel_id, added_at DESC);

-- AI 结果：可复算、可审计、可回放
CREATE TABLE ai_result (
  content_id uuid PRIMARY KEY REFERENCES content(id) ON DELETE CASCADE,
  model varchar(64), version varchar(16),
  layer varchar(4) NOT NULL,               -- L0/L1/L2
  summary_hans varchar(500), summary_hant varchar(500),
  title_hans varchar(200), title_hant varchar(200),
  channels uuid[] NOT NULL DEFAULT '{}',
  confidence numeric(4,3), quality_score numeric(4,3),
  risk_flags text[] NOT NULL DEFAULT '{}',
  tokens_in int NOT NULL DEFAULT 0, tokens_out int NOT NULL DEFAULT 0,
  status varchar(16) NOT NULL DEFAULT 'ok',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE event_cluster (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  title_hans varchar(200), title_hant varchar(200),
  representative_content_id uuid,
  source_count int NOT NULL DEFAULT 1,
  first_seen_at timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE event_source (
  event_id uuid REFERENCES event_cluster(id) ON DELETE CASCADE,
  content_id uuid REFERENCES content(id) ON DELETE CASCADE,
  PRIMARY KEY (event_id, content_id)
);

CREATE TABLE curation_feedback (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  channel_id uuid REFERENCES channel(id),
  editor_id uuid NOT NULL REFERENCES app_user(id),
  action varchar(20) NOT NULL,             -- move_channel/add_channel/edit_summary/reject
  before jsonb NOT NULL DEFAULT '{}'::jsonb,
  after jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_feedback_time ON curation_feedback(created_at DESC);
-- ===== /v1.1 =====

CREATE TABLE media_asset (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id uuid REFERENCES content(id) ON DELETE CASCADE,
  kind varchar(12) NOT NULL, object_key text NOT NULL,
  mime varchar(64) NOT NULL, size_bytes bigint NOT NULL,
  duration_s int, transcode varchar(16) NOT NULL DEFAULT 'n/a',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE user_event (
  id bigserial, user_id uuid, content_id uuid, channel_id uuid, session_id uuid,
  event_type varchar(24) NOT NULL, value numeric(10,2),
  props jsonb NOT NULL DEFAULT '{}'::jsonb,
  occurred_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id, occurred_at)
) PARTITION BY RANGE (occurred_at);
CREATE TABLE user_event_2026_11 PARTITION OF user_event
  FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE INDEX idx_event_user_time ON user_event(user_id, occurred_at DESC);

CREATE TABLE moderation_case (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  reporter_id uuid REFERENCES app_user(id), reason varchar(32) NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'open', decision varchar(24),
  reviewer_id uuid REFERENCES app_user(id), notes text,
  sla_due_at timestamptz NOT NULL DEFAULT (now() + interval '12 hours'),
  decided_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_mod_open ON moderation_case(status, sla_due_at) WHERE status='open';

CREATE TABLE consent_record (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  purpose varchar(48) NOT NULL, version varchar(16) NOT NULL,
  granted_at timestamptz NOT NULL DEFAULT now(), revoked_at timestamptz,
  ip inet, user_agent text
);
CREATE TABLE data_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  kind varchar(16) NOT NULL, status varchar(16) NOT NULL DEFAULT 'pending',
  due_at timestamptz NOT NULL DEFAULT (now() + interval '30 days'),
  completed_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE audit_log (
  id bigserial PRIMARY KEY, actor_type varchar(16) NOT NULL, actor_id uuid,
  action varchar(48) NOT NULL, target_type varchar(24), target_id uuid,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb, ip inet,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_time ON audit_log(created_at DESC);
```

### 8.3 关键约束

- `chk_news_link`：采集资讯必须带原文回链，从数据层阻止全文转载。
- `chk_licensed_source`：无许可的源不得开启 `allow_fulltext`；**MVP 全部为 false**。
- `chk_owner`：用户自建频道必须有频道主。
- `channel_item.pinned` 与 `curator_note_*` 支撑 L2 精选频道的人工温度。
- `content_hash` 唯一约束：去重 + AI 结果缓存键，同一内容不重复调用 LLM。

### 8.4 中文搜索与分区

PostgreSQL 内建 `to_tsvector` **不分词中文**，MVP 用 `pg_trgm` GIN + `ILIKE` 兜底，或装 `zhparser`；规模上升后迁 OpenSearch + IK。`user_event` 按月分区，每月预建下月分区。

### 8.5 定时任务

| 任务 | 频率 | 动作 |
|---|---|---|
| `fetch_sources` | 每源独立，默认 30 min | 采集 → 合规闸门 → 去重 → 入池 |
| `ai_pipeline` | 事件驱动 + 批量 | 聚类 → 分类 → 摘要 → 路由频道 |
| `channel_health` | 每小时 | 统计日更新量，低于 `min_daily_items` 连续 3 天自动隐藏 |
| `expire_listings` | 每小时 | 到期转 `expired` |
| `moderation_sla_check` | 每小时 | 超 12h 工单告警 |
| `recalc_centroids` | 每周 | 用 `curation_feedback` 重算频道质心、更新 few-shot |
| `daily_digest` | 每日 07:00 Europe/London | 为订阅 `notify='daily'` 的用户生成邮件日报 |
| `dsar_worker` / `backup` / `partition_maintain` | 每小时/每日/每月 | 见 §14 |

---

## 9. API 设计（REST / v1）

### 9.1 通用约定

- Base `https://api.<domain>/api/v1`，全站 HTTPS，UTF-8 JSON。
- 认证：JWT access 15 分钟 + refresh 7 天轮换；**游客可读公开频道与内容**。
- 分页：游标式 `?cursor=&limit=20`（上限 50），返回 `next_cursor`。
- 限流：游客 60/min/IP，登录 300/min/user，发布 5 次/小时/user。
- 幂等：所有 POST 支持 `Idempotency-Key`。
- 错误体：`{ "code": "...", "message": "...", "request_id": "..." }`。

### 9.2 端点清单

| 方法 | 路径 | 说明 | 鉴权 |
|---|---|---|---|
| POST | `/auth/register` `/auth/verify-phone` `/auth/login` `/auth/refresh` `/auth/logout` | 会话与同意留痕 | 否/是 |
| GET | `/cities?enabled=true` | 已启用城市 | 否 |
| **GET** | **`/channels?city=&kind=&group=&q=`** | **频道目录（含订阅状态、日更新量）** | 可选 |
| **GET** | **`/channels/:id`** | **频道详情 + 公告** | 可选 |
| **GET** | **`/channels/recommended`** | **频道共现推荐（规则，非内容画像）** | 是 |
| **POST** | **`/channels`** | **创建用户频道（审核后公开）** | 是 + 手机验证 |
| **GET** | **`/channels/:id/items?cursor=`** | **频道时间倒序流** | 可选 |
| **POST** | **`/channels/:id/items`** | **向频道投稿/发布** | 是 |
| **POST** | **`/channels/:id/read`** | **标记已读，清零未读** | 是 |
| **GET** | **`/me/feed?cursor=`** | **聚合已订阅频道，时间倒序、跨频道去重** | 是 |
| **GET** | **`/me/subscriptions`** | **我的频道（含未读、静音）** | 是 |
| **PUT / DELETE** | **`/me/subscriptions/:channelId`** | **加入 / 退订** | 是 |
| **PATCH** | **`/me/subscriptions/:channelId`** | **静音 / 通知偏好** | 是 |
| GET | `/events/:id` | 事件卡片（N 个来源与回链） | 否 |
| GET | `/contents/:id` | 内容详情 | 可选 |
| POST | `/contents` `/listings` | 发布图文 / 分类信息 | 是 |
| POST | `/listings/:id/contact` | 查看联系方式（写审计） | 是 |
| GET | `/search?q=&type=&city=&channel=` | 统一搜索 | 否 |
| POST | `/contents/:id/like` `/favorite` `/report` | 互动 | 是 |
| POST | `/events:batch` | 批量埋点 | 可选 |
| POST | `/uploads/sign` | 对象存储直传签名 | 是 |
| GET / POST | `/admin/ai/quality` `/admin/ai/reclassify/:contentId` | AI 质量看板 / 人工修正回流 | 管理员 |
| GET / POST | `/admin/moderation` `/admin/moderation/:id/decision` | 审核队列与裁决 | 管理员 |
| GET / POST | `/admin/channels/:id/*` | 频道准入、隐藏、合并 | 管理员 |
| GET / POST | `/admin/sources` `/admin/sources/:id/toggle` | 采集源健康与开关 | 管理员 |
| GET / DELETE | `/me/export` `/me` | DSAR 导出 / 发起擦除 | 是 |
| GET | `/healthz` `/readyz` | 探针 | 否 |

### 9.3 关键示例

```http
POST /api/v1/auth/register
{
  "email": "user@example.com", "password": "...", "phone": "+44...",
  "city_code": "london", "script_pref": "hant",
  "consents": [
    { "purpose": "tos", "version": "2026-11-08" },
    { "purpose": "privacy", "version": "2026-11-08" },
    { "purpose": "push", "version": "2026-11-08", "granted": false }
  ],
  "join_codes": ["london-arrival", "visa-policy", "london-housing"]
}
```

`join_codes` 来自游客浏览时想加入的频道，注册后自动带入，避免「注册完又要重新找一遍」。

```http
GET /api/v1/me/feed?cursor=...
→ 200
{
  "items": [
    {
      "content_id": "...",
      "channels": ["visa-policy", "london-arrival"],
      "event_cluster_id": "...", "source_count": 4,
      "title_hant": "...", "summary_hant": "...",
      "canonical_url": "https://www.gov.uk/...",
      "source_name": "GOV.UK", "licence_ref": "OGL v3.0",
      "added_at": "2026-11-08T22:10:00Z", "is_unread": true
    }
  ],
  "next_cursor": "..."
}
```

注意 `source_name` 与 `licence_ref` 是**必返字段**，前端必须显著展示来源与回链。

### 9.4 错误码（节选）

| HTTP | code | 场景 |
|---|---|---|
| 400 | `VALIDATION_FAILED` | 字段校验 |
| 403 | `PHONE_NOT_VERIFIED` | 发布/建频道前未验证手机 |
| 403 | `CHANNEL_SUBMISSION_CLOSED` | 频道不接受投稿 |
| 409 | `DUPLICATE_CONTENT` | `content_hash` 命中 |
| 422 | `CONTENT_POLICY_BLOCKED` | 风控拦截 |
| 429 | `RATE_LIMITED` | 限流 |
| 451 | `SOURCE_NOT_LICENSED` | 采集源无有效许可 |
| 503 | `AI_DEGRADED` | AI 层降级（内容仍可读） |

---

## 10. 采集与 AI 管线

### 10.1 源分级（合规红线，不变）

| 级别 | 例子 | 处置 |
|---|---|---|
| **L1 开放** | GOV.UK Content API、NHS、地方议会、Met Office、TfL / National Rail API、大学 RSS、ONS/BoE 公开数据（OGL v3.0 等） | MVP 唯一接入；须署名、遵守许可条款、限速 |
| **L2 需授权** | 英国报业、PA Media、News UK、FT、中文媒体 | **即使只用标题与摘要，商业聚合也可能需 NLA 许可**；News UK 与 FT 不在通用许可内；MVP 不接 |
| **L3 禁止** | 全文抓取、绕过 paywall、robots disallow、房产平台数据、社交平台私域 | 一律不做；只允许「用户手动粘贴链接 + 自写摘要」 |

> NLA 的 MMO / eClips Web 许可 FAQ **明确面向 "news aggregators"**；本产品形态在法律上正是聚合器。Corporate Website Republishing Licence 覆盖 headlines 与 text extracts（2026-04 价目：微型公司 1 篇约 £159/年、25 篇约 £1,165/年，以官方最新价目为准），所有使用需署名并回链原文。

### 10.2 管线流程（含 AI 层）

```
调度(每源独立 cron，遵守 robots.txt / UA 标识 / QPS / 退避重试)
→ 抓取 → 解析(每源一个 SourceAdapter) → 归一化
→ 合规闸门(allow_fulltext=false → 只保留标题 + 原文链接 + 元数据)
→ 去重(content_hash: URL 归一 + 标题 SimHash + 7 天窗口)
→ 【AI L0】源自带分类 / 关键词 / URL 规则             ~65%
→ 【AI L1】embedding 与频道质心相似度                 ~25%
→ 【AI L2】低置信聚类 + 中文摘要 + 事件标题 + 英译中   ~10%（攒批/缓存/预算上限）
→ 事件聚类(同一事件多源 → event_cluster，逐一署名回链)
→ 频道路由(channel_item 批量写入，写 ai_confidence)
→ 繁简生成(OpenCC，仅显示层，不改原文)
→ 质量风控(广告/标题党/过期/诈骗/违法 → 拦截或转人工)
→ 入库(content.ai_status = ok | degraded)
→ 健康检查(连续 3 次失败 → 自动 disable + 告警)
```

降级规则：LLM 不可用时跳过 L2，用 L0/L1 分类结果 + 原标题入库，标 `degraded`，**绝不阻塞频道更新**；采集源全部失败时隐藏资讯类频道，其余频道不受影响。

### 10.3 摘要与版权红线

- 摘要是**提炼**而非改写复制，≤200 字，禁止生成原文没有的事实；
- 不存全文、不存原图、不做全文翻译；
- 每条卡片必须携带 `source_name`、原文链接、`licence_ref`；
- 视频只做「标题 + 封面外链 + 原站跳转」卡片，不托管媒体文件；
- UGC 频道配置 notice-and-takedown 流程与重复侵权封禁策略。

---

## 11. 审核与风控

| 风险 | 措施 |
|---|---|
| 租房/招聘诈骗 | 手机验证、新用户前 3 帖必审、价格异常规则、外链黑名单、重复文案检测 |
| 垃圾广告 | 发布频次（5 条/小时、20 条/天）、`content_hash` 去重、图片指纹 |
| AI 摘要幻觉/错误分类 | 置信度阈值、低置信转人工、抽检事实一致性 ≥95%、编辑修正回流 |
| 频道主滥用 | 建频道审核、一人最多 3 个、所有管理操作写审计日志 |
| 联系方式滥用 | 受控加密展示 + 访问审计 + 每日查看上限 |
| 违法内容 | 敏感词 + 图片哈希 + 人工队列 12h SLA + CSEA 上报流程（§13.3） |
| 死信息/空频道 | 分类信息强制有效期；频道日更新不足自动隐藏 |

---

## 12. 技术架构与选型

| 层 | 选择 | 理由 |
|---|---|---|
| 前端 | Vue 3 + Vite + TS + SSR/预渲染（Nuxt 或自建） | 频道落地页需 SEO；纯 CSR 会让搜索流量归零 |
| 形态 | PWA（可安装、Web Push、离线读已缓存内容） | 一套代码覆盖 web 与「app」诉求 |
| 后端 | Python 3.12 + FastAPI 单体模块化 | 采集、OpenCC、embedding、LLM 生态最全 |
| ORM/迁移 | SQLAlchemy 2.0 + Alembic | 可版本化、可回滚 |
| 队列 | Celery + Redis（queues: fetch / ai / notify / maintenance） | AI 攒批、日报、聚类解耦 |
| 数据库 | PostgreSQL 16 + PostGIS | jsonb、数组、分区、trgm、地理查询 |
| **AI L1** | 本地 embedding 小模型（bge-small 等）+ 频道质心 | 零 API 成本、可自托管、可复算 |
| **AI L2** | 第三方 LLM API（签 DPA、评估跨境传输） | 只处理 ~10% 低置信条目与摘要 |
| 搜索 | `pg_trgm`（MVP）→ OpenSearch + IK（P2） | 早期不值得独立集群 |
| 存储 | Cloudflare R2（图片；视频不托管） | 免出网流量费 |
| 部署 | 单台英国 VPS + Docker Compose + Cloudflare CDN/WAF | 日活过万前不需要编排 |

**模块边界靠目录约束，不靠网络拆分**：`auth / channel / subscription / content / ai / source / moderation / admin / dsar` 分包，禁止跨包直接访问彼此的数据模型。

### 12.1 dev / prod 差异

| 项 | dev | prod |
|---|---|---|
| AI | 固定 fixture / 规则层，禁用真实 LLM 计费 | 分层启用，日预算上限与降级开启 |
| 采集 | fixture | 按源限速、全量合规校验 |
| 密钥 | `.env.local` 占位 | KMS/环境变量，禁止入库与进 Git |
| 审核 | 自动通过 + 标记 | 强制机审 + 人工队列 |
| 日志 | 控制台 | JSON 结构化 + 脱敏 + 集中收集 |
| 推送 | 控制台输出 | 真实供应商，需同意留痕 |
| 备份 | 无 | 每日 `pg_dump` → R2，30 天保留 |

---

## 13. 合规专章（英国）

> 以下为工程落地要点，**不构成法律意见**；上线前请英国本地律师复核条款与 OSA 风险评估。

### 13.1 数据保护：UK GDPR + DPA 2018

- 订阅关系属于个人数据（兴趣画像），隐私政策须说明用途；用户可随时退订、撤回同意。
- 频道共现推荐须说明「基于其他用户的频道加入情况」，并提供关闭选项。
- Cookie / 埋点 / Web Push / 邮件日报需 PECR 同意，默认关闭，一键退订；`consent_record` 记录用途、版本、时间、IP/UA。
- 数据最小化：不采集精确位置、通讯录；身份与落地阶段改为选填。
- DSAR：自助导出（含订阅关系、发布内容）、自助擦除，30 天法定 / 7 天内部目标，级联清理 `channel_subscription`、用户频道与 `ai_result` 关联。
- 18+ 限定；向 ICO 缴纳 data protection fee（按规模分档）；第三方 LLM / R2 / 推送 / 错误上报需 DPA 与 sub-processor 清单，跨境传输需评估 IDTA/adequacy。
- 保留期：注销后 30 天硬删除；`user_event` 13 个月后聚合或删除。

### 13.2 版权：聚合器定位下的 NLA

- 本形态就是 news aggregator，NLA 有面向聚合商的 MMO / eClips Web 许可；**标题与摘要的商业性复制也可能落入许可范围**。
- MVP 只接 L1 开放许可源，`canonical_url` 必填，摘要 ≤200 字，禁止存全文、原图与全文翻译；页面显著标注来源与许可。
- News UK 与 FT 不在 NLA 通用许可内，须单独授权；未来若接英国报业，先采购许可再开发，不要「先上再说」。
- 工程约束：`chk_news_link`、`chk_licensed_source`、`451 SOURCE_NOT_LICENSED` 三层堵住越界。
- UGC：notice-and-takedown、重复侵权封禁、频道主责任条款。

### 13.3 Online Safety Act 2023（Ofcom）

- 允许用户在英国互相发布内容 → **regulated user-to-user service**；违法内容义务 2025 年生效，儿童保护义务随后生效，Ofcom 已调查近百个服务，**小型服务不当然豁免**。
- 第 9 条：必须做「适当且充分的非法内容风险评估」，评估用户群、各类优先违法内容风险、功能设计（尤其**频道创建、投稿、转发、推送、事件聚类**）带来的传播风险；重大功能变更前重做、至少年度复核、留存记录备查。
- 第 10 条：审核策略、快速下架、易用举报与投诉通道、条款一致执行、审计留痕。因不做算法排序，可说明**不存在推荐放大风险**，但频道置顶与推送仍需评估。
- CSEA 报告：自 2026-04-07 起须向 NCA 报告发现的 CSEA 内容，需在其行业门户注册。
- 儿童保护：即使声明 18+，仍须评估儿童实际可访问性，请律师确认义务范围。
- 罚则上限 £18m 或合格全球营收 10%（取高者）；Ofcom fees regime 按 QWR 门槛，MVP 大概率低于门槛但需留存判断依据。

### 13.4 其他

- 商家/推广内容需标注「推广」；置顶商业化前复核消费者保护规则。
- Web Push 与营销邮件单独同意 + 一键退订。
- WCAG 2.1 AA 基线。

---

## 14. 部署与运维

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
    command: celery -A app.worker worker -B -l info -Q fetch,ai,notify,maintenance
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

### 14.2 `.env.example`（prod 值由密钥管理注入，禁止提交）

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
CONTACT_ENCRYPTION_KEY=<AES-GCM key>
LLM_API_BASE=
LLM_API_KEY=
LLM_MODEL=
LLM_DAILY_TOKEN_LIMIT=200000
LLM_DAILY_COST_GBP_CAP=3.00
EMBEDDING_MODEL=bge-small-zh-v1.5
EMBEDDING_LOCAL_PATH=/models/bge-small
AI_LAYER2_MIN_CONFIDENCE=0.55
OPENCC_MODE=s2t
DEFAULT_TIMEZONE=Europe/London
ENABLED_CITY_CODE=london
SOURCE_FETCH_ENABLED=true
TOS_VERSION=2026-11-08
PRIVACY_VERSION=2026-11-08
SENTRY_DSN=
```

### 14.3 上线步骤

1. 域名接 Cloudflare（代理、WAF 托管规则、TLS Full Strict、HSTS、限流）。
2. VPS 选伦敦节点；只开 80/443 与限源 SSH。
3. `docker compose up -d` → `alembic upgrade head`。
4. 灌入城市、18 个频道定义、3 个组合包、200+ 条种子内容、3–5 个 L1 源（先 `is_enabled=false`，验证后开启）。
5. 计算各频道 embedding 质心（用种子内容的标题/摘要），写入配置表。
6. 冒烟：`/healthz`、游客浏览、加入频道、聚合 feed、采集→AI→入频道、编辑修正回流、举报闭环、DSAR、LLM 降级演练。
7. 打开监控告警；先邀请灰度 1 周再开放注册。

### 14.4 备份、迁移与回滚

```bash
docker compose exec -T db pg_dump -Fc -U "$PG_USER" "$PG_DB" \
  | gzip | r2-upload.sh backups/$(date -u +%F).dump.gz

docker compose exec api alembic upgrade head
docker compose up -d --no-deps --build api worker

# 回滚：先代码，后按需回滚迁移（每个迁移必须写 downgrade）
docker compose exec api alembic downgrade -1
git checkout <previous-tag> && docker compose up -d --no-deps --build api worker
```

**纪律**：涉及 `content` / `channel_item` / `user_event` 的迁移必须可 downgrade 且先做影子表验证；恢复演练每季度一次，未演练过的备份视为不存在。

### 14.5 监控与告警

| 指标 | 阈值 | 动作 |
|---|---|---|
| API 5xx 率 | > 1% / 5min | 告警 + 回滚评估 |
| 聚合 feed P95 | > 500ms / 10min | 查索引与缓存 |
| 采集→入频道时延 | > 5min | 查队列积压 |
| AI L2 日成本 | 达上限 80% | 自动降级 + 告警 |
| 分类准确率（抽检） | < 90% | 触发规则复审 |
| 频道日更新量 | 连续 3 天 < 3 条 | 自动隐藏 + 通知运营 |
| 审核工单 | 任一超 12h | 通知负责人 |
| 备份任务失败 | 任一 | 立即告警 |

---

## 15. 测试与验证

| 层级 | 必须覆盖 |
|---|---|
| 单元 | 去重 SimHash、频道质心分类、事件聚类、OpenCC 转换、未读计算、跨频道去重、有效期、限流 |
| 接口 | 游客可读/游客加入触发注册、订阅变更即时生效、聚合 feed 严格时间序、`content_hash` 幂等、DSAR 级联清理、合规约束三个 CHECK |
| AI | L0/L1/L2 分层覆盖率、缓存命中率、LLM 降级不阻塞、摘要 ≤200 字且带来源、事实一致性抽检 |
| E2E | 游客浏览 → 加入 → 轻注册 → 组合包 → 频道流 → 举报 → 裁决 → 修正回流 |
| 采集 | 每个源适配器在结构变化时可失败并告警；源全挂时仅隐藏资讯频道 |
| 合规 | OSA 风险评估文档、条款与同意版本、Cookie 默认拒绝、举报可达、CSEA 上报演练、来源署名与回链逐条检查 |
| 性能 | 100 并发下 `/me/feed` P95 < 500ms |
| 恢复 | 从 R2 备份恢复到干净环境并跑通冒烟 |

**修复验证统一标准**：可复现失败用例 → 修复后通过 → dev 复现原场景 → prod 灰度观察 24h。

---

## 16. 目录结构

```
ukcn/
├── app/
│   ├── main.py
│   ├── internal/
│   │   ├── auth/  channel/  subscription/  content/
│   │   ├── ai/  source/  moderation/  admin/  dsar/
│   ├── ai/
│   │   ├── l0_rules.py  l1_embedding.py  l2_llm.py
│   │   ├── cluster.py  summarise.py  centroid.py
│   ├── sources/adapters/
│   ├── workers/                # fetch / ai / notify / maintenance
│   ├── models/  schemas/  migrations/
│   └── core/                   # config, security, audit, crypto
├── web/                        # Vue 3 + SSR
├── deploy/                     # nginx.conf, compose, cron, backup.sh
├── tests/
└── docs/                       # 本文、OSA 风险评估、API 文档、条款
```

---

## 17. 风险登记册

| # | 风险 | 概率 | 影响 | 缓解 |
|---|---|---|---|---|
| R1 | 纯机器频道退化成 RSS 阅读器，无留存 | 高 | 致命 | L2 精选频道人工按语 + L3 频道主 + 事件聚类 + 本地相关性，四者缺一不可 |
| R2 | 频道过多导致选择瘫痪 / 空频道 | 高 | 高 | 首版 ≤25 个；日更新 ≥3 条才公开；组合包一键加入；空频道自动隐藏 |
| R3 | NLA 聚合版权侵权 | 中 | 高 | 只走 L1；摘要+回链+署名；数据层禁止全文；采购许可前不碰 L2 媒体 |
| R4 | OSA 义务未履行 | 中 | 高 | 上线前书面风险评估（须覆盖频道创建/投稿/推送）、举报与下架机制、CSEA 上报注册、律师复核 |
| R5 | AI 摘要幻觉或错误分类损害信任 | 中 | 高 | 置信度阈值、低置信转人工、事实一致性抽检 ≥95%、修正回流、来源必显 |
| R6 | LLM 成本失控 | 中 | 中 | 分层降本、哈希缓存、攒批、日 token/费用双上限、自动降级 |
| R7 | 分类信息诈骗 / 频道主滥用 | 高 | 高 | 手机验证、前 3 帖必审、联系方式受控、建频道审核、12h SLA、审计日志 |
| R8 | 中文搜索效果差 | 高 | 中 | MVP 用 trgm + 频道内筛选，不承诺全文检索；P2 上 IK |
| R9 | GDPR 同意/擦除遗漏 | 中 | 高 | 同意留痕、DSAR 工单、级联清理、上线前合规清单逐项验收 |
| R10 | BST/GMT 夏令时打乱日报与有效期 | 中 | 低 | 全链路存 UTC，仅展示层按 `Europe/London` 转换；写专门单测 |
| R11 | 早期上算法/微服务/自建转码 | 中 | 高 | §0.2 不做清单作为排期护栏 |

---

## 18. 里程碑（6 周 MVP）

| 周 | 交付 | 验收 |
|---|---|---|
| W1 | 频道目录定稿（18 个）、组合包、合规清单与 OSA 风险评估初稿、DDL 评审 | 本文评审通过；律师确认关键条款 |
| W2 | 脚手架、Compose、CI、轻注册、频道目录、订阅与未读 | US-01/02 通过 |
| W3 | 聚合 feed、单频道流、UGC 发布与分类信息、审核后台 | US-03/04/08/09 通过 |
| W4 | 采集适配器 + L0 规则 + 事件聚类 + L1 embedding 分类 + 频道质心 | US-06 通过；准确率抽检 ≥90% |
| W5 | L2 摘要与繁简、降级与缓存、编辑修正回流、Web Push/日报、种子内容灌入 | US-07/11 通过；种子 ≥200 条、非空频道 ≥15 |
| W6 | 灰度、监控告警、备份恢复演练、性能与合规验收 | §7 全清单通过 |

后续：M2（2–3 月）频道推荐、商家认证、视频云转码、多城市；M3（6 月+）OpenSearch、内容级轻排序、原生 App。

---

## 19. 附录

### 19.1 常见坑

1. 频道开得越多越好 —— 实际是选择瘫痪 + 空频道，必须设日更新准入门槛。
2. 以为「AI 整理完就不需要人」 —— 没有 L2 精选与频道主，留存会掉到 RSS 阅读器水平。
3. 每条内容都调 LLM —— 成本和延迟都炸，必须分层 + 缓存 + 攒批 + 降级。
4. 认为「只有标题和链接就不涉及版权」 —— 英国有 NLA 集中许可，聚合商有专门许可类别。
5. 认为「小平台不用管 OSA」 —— 风险评估义务适用于所有受监管 user-to-user 服务。
6. 用 `to_tsvector` 做中文全文检索 —— PG 不分词中文，MVP 用 `pg_trgm`。
7. 纯 SPA 不做 SSR —— 频道落地页的搜索流量归零。
8. 聚合 feed 按「相关度」排序 —— 一旦重排就退回黑箱模型，破坏订阅语义；只按时间 + 置顶。
9. 同一内容进多个频道就重复展示 —— 聚合 feed 必须按 `content_id` 去重。
10. 联系方式直接渲染 / 时间用本地时间存 / 埋点以后再加 / 采集阻塞主链路 —— 均为 v1.0 已列坑，继续适用。

### 19.2 参考来源（2026-11-08 检索）

- legislation.gov.uk — Online Safety Act 2023, Part 3 Ch.2（第 9/10 条）
- Ofcom — Roadmap to regulation（义务生效、执法进展、CSEA 报告、fees regime）与执法公告（罚则）
- GOV.UK — 非法内容实践准则修订草案（2026）
- NLA Media Access — Corporate Website Republishing Licence 及 2026-04 价目、What We Do、eClips Web FAQ（明确覆盖 news aggregators）
- 应用宝 / Google Play — 华人头条、华人168 功能描述

---

**待裴总拍板后，下一轮可直接交付**：① 可运行 MVP 脚手架（含本文全部 DDL 与频道 API），② OSA 非法内容风险评估文档模板，③ 18 个频道的种子内容采编清单与 AI 分类提示词，④ 频道目录与订阅流界面原型稿。

---

## 20. X 式三 Tab 界面规范（2026-11-09 增补）

**背景**：裴总提出界面模仿 X（Twitter）App：用户订阅喜欢的频道，首页为「为你推荐 / 正在关注 / 添加」。可交互原型见 `prototype-x-style.html`。

### 20.1 三 Tab 定义

| Tab | 内容 | 排序 | 与 v1.1 的关系 |
|---|---|---|---|
| **为你推荐** | AI 整理后的每日精选 + 相邻频道内容 + 同城热点 + 编辑精选 | 规则加权，**有限列表**（非无限滚动） | **补回 v1.1 砍掉的「发现」能力**，但不恢复重推荐算法 |
| **正在关注** | 仅已订阅频道的 `channel_item`，跨频道按 `content_id` 去重 | **严格 `added_at DESC`**，置顶公告固定在前，无算法重排 | 就是 v1.1 的订阅时间流，内核不变 |
| **添加频道** | 频道目录（按城市/主题分组）、新手组合包、搜索、加入/退订 | 按分组 + 日更新量 | 把订阅动作从设置页提到首屏 |

X 的双 Tab 是「算法派 vs 时间派」的成熟解法：**让用户自己选**，不用在架构上二选一。

### 20.2 「为你推荐」不是 X 的 For You

X 依赖海量行为数据与排序模型，本项目早期既无数据也不该付这个成本。改用**可解释规则**：

```
recall = 已订阅频道的相邻频道内容（频道共现）
       + 同城频道的热门条目
       + event_cluster.source_count ≥ 3 的多源事件
       + 编辑精选（L2 频道的人工加权）
       - 已读 / 已退订频道 / 风控命中
```

- 每张卡必须显示「为什么推荐」（如「你关注了伦敦落地必读」「同城 + 多源事件合并」），用户可点开查看规则来源。
- 推荐的是**频道与内容**，不是「你可能认识的人」——**频道 ≠ 账号**，X 关注人，我们订阅主题容器。
- 提供「减少此类内容」反馈，写入 `curation_feedback`，用于调整频道共现权重。
- 一旦出现逐条内容的相关度重排，就退回黑箱模型、破坏订阅语义，明确禁止。

### 20.3 最致命的错配：内容节奏

X 靠每秒都有新帖撑起无限滚动；本项目 L1 源是 GOV.UK、地方议会、TfL，**一天可能只有几条**。照抄无限流会得到一片空白的信息流。

对策（必须同时做）：

1. 「为你推荐」做成**每日精选有限列表**（每日 07:00 Europe/London 更新，10–20 条封顶），并明确显示「今天先看这些」；
2. **事件聚类**合并多源为一张卡，既提密度又强化来源署名；
3. 靠 **L3 用户频道 / UGC** 与本地分类信息补密度；
4. 频道日更新不足时自动隐藏（§2.2 准入规则），不靠填充低质内容凑数。

### 20.4 界面组件清单

| 区域 | 桌面（≥1100px，三栏） | 移动（≤760px 或移动视图） |
|---|---|---|
| 左 | 品牌 + 导航（首页/添加频道/发现/通知/收藏/我的频道）+ 发布按钮 + 用户块 | 隐藏 |
| 中 | 顶部标题栏 + 三 Tab（吸顶）+ 信息流 | 三 Tab 撑满 + 信息流 |
| 右 | 搜索、你可能想加入、伦敦本地趋势、来源与合规说明 | 隐藏 |
| 底 | — | 5 项底部 Tab bar（首页/添加/关注/通知/菜单），带未读角标 |

卡片规范（**§29 已重写为 X 式**）：左列频道头像；头部一行「频道名 + handle + 时间 + 推荐理由小图标」且**右上角固定「加入 / 已加入」按钮**；正文（标题 + 摘要 + 内联话题标签）；媒体块（下方无条、无按钮）；一行 `SourceLine`（**来源名 + 许可标注 + 原文回链 + N 个来源展开**）；一行纯 SVG 图标操作栏（回复 / 转发 / 喜欢 / 收藏 / 分享 / 举报）。**来源与回链是必显字段，不是可折叠的次要信息**；区域徽章不再出现在卡片内，统一到顶部区域栏（§29.2）。

其他：深浅色主题切换、简繁界面切换、频道加入/退订即时生效、事件来源展开、未读角标、移动视图预览。

### 20.5 数据模型与 API 增量

| 位置 | 增量 |
|---|---|
| `channel_item` | 增加 `reason_code varchar(32)`（推荐/精选理由枚举）与 `editor_weight numeric(3,2)` |
| `curation_feedback` | `action` 增加 `reduce_recommend`（减少此类内容） |
| `GET /me/feed` | 增加 `tab=foryou|following`；`following` 强制时间序，`foryou` 返回 `reason_label` 字段 |
| `GET /channels/recommended` | 频道共现规则，返回推荐理由 |
| 新增 | `GET /me/daily-digest?date=` 每日精选（有限列表，服务端封顶 20 条） |

### 20.6 合规回退（重要）

- **OSA 2023**：v1.1 §13.3 曾写「因不做算法排序，可说明不存在推荐放大风险」——**加回「为你推荐」后该结论作废**。OSA 非法内容风险评估必须新增章节，覆盖推荐规则对优先违法内容的放大可能、置顶与推送功能、低质/诈骗内容进入推荐流的拦截措施，以及儿童可访问性评估；重大功能变更前需重做评估并留存记录。
- **NLA 版权**：无限滚动会放大「聚合内容替代原文」的观感与风险。坚持有限列表 + ≤200 字摘要 + 显著来源署名 + 原文回链；推荐流不得增加每条内容的正文长度或原文图片。
- **UK GDPR**：推荐理由基于订阅关系与共现统计，隐私政策须说明并提供「减少此类内容」与关闭个性化推荐的选项；不得引入跨站行为追踪。

### 20.7 原型验收点

`prototype-x-style.html` 为单文件、无外部依赖的可交互演示：三 Tab 切换、频道加入/退订即时同步到「正在关注」、组合包一键加入、事件来源展开、收藏、深浅色切换、桌面三栏/移动底部 Tab 响应式切换。全部内容为示例数据，每张卡均带来源与许可标注。

**未实现**（需开发补齐）：真实接口、SSR/SEO、Web Push、审核后台、AI 管线、登录态、DSAR。

### 20.8 待裴总确认

① 「为你推荐」首版是否接受「可解释规则 + 每日精选」，而非真正的时间线无限流；② 界面是否以移动端 App 形态为第一优先（影响是否先做 PWA 壳）；③ 是否保留 v1.1 的 18 个频道目录规模，还是随界面重排调整分组。

---

## 21. 内容供给模式与自营频道账号规范（2026-11-09 增补）

**背景**：裴总提出「自己管理几个订阅频道账号，采集新闻、视频、小视频发到平台」。本质是**把内容生产从「系统自动采集入库」改为「运营账号人工/半自动发布」**。

### 21.1 结论：采用混合模式

| 模式 | 开发量 | 持续人力 | 密度可控 | 人味/质量 | 版权责任 | 适用 |
|---|---|---|---|---|---|---|
| 全自动采集入库 | 高 | 低 | 受源限制 | 低 | 取决于源 | 规模化后 |
| 自营账号纯人工发 | **低** | **高** | 高 | 高 | **最高（平台直接责任）** | 极简验证 |
| **混合：系统素材队列 + 运营账号把关（推荐）** | 中 | 中 | 高 | 高 | 可控 | **MVP** |

混合链路：开放源/用户投稿 → 系统仅抓元数据 + 去重 + AI 摘要草稿 → **编辑素材队列（不自动发布）** → 运营账号审核/改写/加按语/溯源登记 → 发布到频道 → 用户三 Tab 消费。

**界面层完全不变**（§20 原型可原样复用），这正是生产/消费分层的好处。

### 21.2 必须纠正的法律误区

> **「用我们自己的账号发」不改变版权性质，反而责任更重。**

- 侵权判定看「是否复制/传播受保护作品」，与账号归属、是否自家平台无关。
- 用户 UGC 时平台尚可主张中介地位与通知删除；**自营账号发布时平台是直接内容提供者**，失去避风港空间，NLA 可直接向平台主张，OSA 下也更易被认定为内容提供者。
- 视频/短视频风险最高：搬运 YouTube / 抖音 / 小红书 / Reels 叠加著作权、平台 ToS、水印、肖像权问题，几乎必然踩线。

**底线不变**：只发开放许可源（OGL v3.0）、原创或已授权内容；新闻只做摘要 + 署名 + 原文回链；视频只做官方嵌入/外链卡片，不落文件。

### 21.3 账号与频道的关系（避免多账号人设）

| 概念 | 定义 | 数量建议 |
|---|---|---|
| 运营账号 | **权限主体**（登录、发布、审核），`app_user` 中 `role='operator'` | MVP **1 个官方主体 + 1–2 个备用编辑账号**，用于轮班与交接 |
| 频道 | **内容容器**，`channel.owner_id` 指向运营账号 | 12–18 个，一个账号可管多个 |

不做「几个账号各管一个频道」的人设矩阵：分散、难交接、用户误以为是不同人。频道上打「官方运营」徽章即足够。账号所有操作写 `audit_log`；离职/交接只需改 `channel.owner_id`。

### 21.4 视频与短视频红线

| 形式 | 允许 | 条件 |
|---|---|---|
| 官方嵌入（YouTube / 官方播放器 iframe） | ✅ | 遵守对方 ToS、不去除标识、不套壳播放 |
| 外链卡片（标题 + 封面外链 + 原站跳转） | ✅ | 不下载、不转存、不落 R2 |
| 开放许可视频 / 政府公开视频 / 本地社团授权供稿 | ✅ | 记录 `licence_ref` 与授权凭证 |
| 原创自拍 / 用户授权 UGC | ✅ | 取得发布授权，可登记 `provenance_log` |
| 抖音 / Reels / Shorts / 小红书搬运、去水印、二次剪辑 | ❌ | 一律禁止 |
| 自建转码与视频托管 | ❌ | MVP 不做，成本黑洞 |

### 21.5 内容溯源台账（合规证据链）

每条发布必须可回答「内容从哪来、谁授权、谁审的、有没有 AI 参与」。NLA 核查、OSA 审计、编辑交接都靠它。

```sql
CREATE TYPE publish_mode AS ENUM ('auto','editorial','curated','ugc');

ALTER TABLE content
  ADD COLUMN publish_mode publish_mode NOT NULL DEFAULT 'ugc',
  ADD COLUMN operator_id uuid REFERENCES app_user(id),
  ADD COLUMN ai_assisted boolean NOT NULL DEFAULT false;

-- 编辑素材队列：系统只写草稿，绝不自动发布
CREATE TABLE editorial_draft (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source_id uuid REFERENCES source(id),
  source_url text NOT NULL,
  licence_ref text,
  raw_title text,
  ai_summary_hans varchar(500), ai_summary_hant varchar(500),
  suggested_channels uuid[] NOT NULL DEFAULT '{}',
  status varchar(16) NOT NULL DEFAULT 'pending',  -- pending/approved/rejected/published
  reviewer_id uuid REFERENCES app_user(id),
  published_content_id uuid REFERENCES content(id),
  ai_model varchar(64), ai_version varchar(16),
  created_at timestamptz NOT NULL DEFAULT now(),
  reviewed_at timestamptz
);
CREATE INDEX idx_draft_pending ON editorial_draft(status, created_at) WHERE status='pending';

-- 溯源台账：不可删除，仅追加
CREATE TABLE provenance_log (
  id bigserial PRIMARY KEY,
  content_id uuid NOT NULL REFERENCES content(id),
  source_url text NOT NULL,
  licence_ref text NOT NULL,
  editor_id uuid NOT NULL REFERENCES app_user(id),
  publish_mode publish_mode NOT NULL,
  ai_assisted boolean NOT NULL DEFAULT false,
  note text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_prov_content ON provenance_log(content_id);
```

前端卡片继续强制显示 `source_name` + `licence_ref` + 原文回链；`ai_assisted=true` 的内容在编辑按语处标注「AI 辅助整理，人工复核」。

### 21.6 编辑后台流程与人力测算

```
素材队列(按 suggested_channels / 时间 / 置信度排序)
→ 打开草稿(左：原文链接与元数据；右：AI 摘要与建议频道)
→ 人工核对事实、改写摘要(≤200 字)、选频道、写按语
→ 点发布 → 写 content + channel_item + provenance_log → 前端可见
→ 驳回则写 rejected 并回流 curation_feedback
```

| 规模 | 条/天 | 单条耗时 | 每日人力 |
|---|---|---|---|
| 12 频道 × 5 条 | 60 | ~5 min | ~5 h（1–1.5 全职编辑） |
| **8 频道 × 3 条（MVP 建议）** | **24** | ~5 min | **~2 h（0.5 人可撑）** |

风险：节假日断更、编辑离职交接、人工标准不一致。对策：素材队列允许提前排期、发布 SLA 告警、按语模板与术语表、`provenance_log` 完整留痕。

### 21.7 AI 定位调整

AI 从「自动分类入库」降级为**辅助编辑**：只生成摘要草稿、建议频道、繁简版本、查重提示；**低置信或事实存疑一律转人工**，不自动发布。好处是幻觉风险由人兜住、版权由人把关，成本也更可控（L2 仅对进入队列的条目调用）。

### 21.8 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/admin/editorial/drafts?status=pending&channel=` | 素材队列 |
| POST | `/admin/editorial/drafts` | 人工录入素材（必填 `source_url` + `licence_ref`） |
| POST | `/admin/editorial/drafts/:id/approve` | 发布；body 含 `channel_codes` / `summary_override` / `curator_note` / `pinned` |
| POST | `/admin/editorial/drafts/:id/reject` | 驳回并回流修正样本 |
| POST | `/admin/editorial/publish` | 原创内容直接发布（同样强制溯源字段） |
| GET | `/admin/provenance?content_id=` | 溯源记录查询（管理员/合规） |

`approve` 与 `publish` 服务端强制校验：无 `source_url`、无 `licence_ref`、摘要 >200 字、`publish_mode` 缺失，一律 `400`，不允许前端绕过。

### 21.9 排期调整（两种起步方式）

| 方案 | 周期 | 内容 | 适用 |
|---|---|---|---|
| **极简版** | 3 周 | 纯人工录入 + 编辑后台 + 三 Tab 前端，无采集无 AI | 先验证「有人愿意每天回来」，最省 |
| **推荐版（混合）** | 4–5 周 | 1–2 个 L1 源适配器 + AI 草稿 + 素材队列 + 三 Tab + 审核与溯源 | 验证同时把编辑效率做起来 |

推荐版周计划：W1 频道/运营账号体系与 DDL → W2 素材队列 + AI 草稿 + 编辑后台 → W3 三 Tab 前端 + 审核举报 → W4 溯源台账、合规清单、种子内容 → W5 灰度与监控。**原 6 周方案中的多路采集、自动分类入库、事件聚类自动化推到 M2。**

### 21.10 风险、常见坑与验证

**风险提示**：① 自营账号使平台成为直接内容提供者，责任重于 UGC 中介，条款与保险需相应调整；② 持续人力是 OPEX，需提前定编制与排班；③ 人工发布的一致性与断更风险；④ 短视频搬运是最容易踩的法律红线。

**常见坑**：
1. 以为「自家账号发」就不侵权 —— 见 §21.2，这是本轮最需要纠正的认知。
2. 一个频道配一个账号 —— 账号膨胀、交接混乱，用 `owner_id` 一对多即可。
3. 把采集到的全文/图片直接粘进编辑器 —— 前端应只给「原文链接 + 元数据」，不提供全文粘贴入口。
4. AI 草稿不经人审直接发布 —— 队列存在的意义就是拦住这一步。
5. 溯源字段做成选填 —— 一旦可绕过，合规证据链就断了，服务端必须强校验。
6. 为了填满信息流放宽来源 —— §20.3 已定每日精选封顶，宁可少也不放低质/无授权内容。

**部署与验证**：dev 用固定素材 fixture 与假编辑账号，`provenance_log` 可清空重建；prod 台账只追加不可删，纳入每日备份与 30 天保留。验收点：① 任一草稿不点发布则前台不可见；② 无 `licence_ref` 的发布请求被 400 拒绝；③ 每条已发布内容都能查到溯源记录；④ 换编辑账号后 `owner_id` 迁移不影响频道内容；⑤ 草稿队列为空时告警而不是自动补内容。

---

## 22. 用户自建「房间」：有序合集 + 分类信息（2026-11-09 第三轮增补）

### 22.1 结论与定位

裴总提出：用户创建频道相当于给一部剧建一个房间，把各季各集按顺序排好，**数据全部来自用户**；分类信息发布也放进同一模型。

**采纳，但产品定义必须是「追剧清单」，不是「影视资源站」。**

这一轮一次性解决了此前四轮最头疼的三件事：

| 老问题 | 房间模型怎么解决 |
|---|---|
| §20.3 内容节奏错配（GOV.UK / TfL 一天几条，撑不起信息流） | 一部剧几十集，天然高密度结构化内容 |
| §2.1 纯机器频道没人味、留存弱 | 追更 + 房主按语 + 同好讨论，是最强的每日回访动机 |
| §21.6 自营账号需 0.5–1 个全职编辑（持续 OPEX） | 内容 100% 用户录入，平台编辑人力降到近 0 |

**必须回答的差异化问题**：用户为什么不去 B 站合集 / 豆瓣小组 / Telegram 频道 / Letterboxd 建房间？答案不是「能放片」，而是**「海外可看性」**——哪部中文剧在英国哪个平台能合法看、更到第几集、有没有繁体/粤语字幕、跟谁一起聊、本地有没有观影局。这是海外华人的真实痛点，纯资源站做不了，而且是合规的差异化。房间由此与「英国中文本地生活」主线接上：分类信息（观影局、二手碟、粤语角、拼车）是共同底座。

### 22.2 与既有模型的关系：新增「布局维度」，不推翻任何一层

现有 `channel.kind` 是**层级**（`official_auto` / `official_curated` / `user_created`），本轮新增的是**形态**，两者正交，禁止混用：

| `channel.layout` | 语义 | 排序 | 扩展表 | 对应章节 |
|---|---|---|---|---|
| `feed` | 时间流频道（默认，兼容全部存量频道） | `channel_item.added_at DESC` | — | §2 / §20 三 Tab |
| `collection` | 有序房间（季 → 集） | `season_no, COALESCE(sort_override, episode_no)`，固定顺序**不重排** | `collection_item` | 本章 |
| `board` | 分类信息看板 | `published_at DESC` + 置顶 | `listing_ext` | §8，沿用 |

`content` 统一内容池、`channel_item` 关联、订阅关系、审核风控、埋点、三 Tab 首页、部署选型**全部沿用**。房间只是给 L3 用户自建频道加一种编排方式，§20 与 §21 均不推翻；但 §21 的 `editorial_draft` 采集队列适用范围收缩到 L1/L2 官方频道，用户房间走「直发 + 审核」，自动采集与 AI 草稿推到 M2。

### 22.3 法律边界（本轮核实，与前几轮的口径差异要写清）

**影视版权不走 OSA。** OSA 2023 的 illegal content 定义**明确排除知识产权侵权**（与 EU DSA 的宽定义不同），因此 §13.3 的 OSA 风险评估结论不因此作废，但不能拿 OSA 当版权投诉依据。实际适用的是：

1. **CDPA 1988**：复制、向公众传播、改编等专属权利；影视正片属保护期内的作品。
2. **Electronic Commerce (EC Directive) Regulations 2002**（脱欧后保留的英国法）**hosting defence**：平台对用户上传内容无 actual knowledge，且知悉后 **expeditiously 移除/禁用访问**，方可免责。英国**没有美式 DMCA 法定程序**（无指定代理人、无法定通知格式、无反通知法定流程），靠 ToS + 通知删除 + 处置审计实现；平台**无一般监控义务**。
3. **s97A CDPA 屏蔽令**：权利人可申请针对 ISP 的网站屏蔽令，英国已有成熟判例链（Newzbin2、Dramatico v Sky / The Pirate Bay、EMI v Sky、英超动态屏蔽令）。
4. **被动托管 vs 主动参与**：平台若**选择、编排、置顶、推广、变现**侵权内容，可能被认定为 active participant / facilitator，从而丧失托管抗辩。

> **最关键的一条**：本产品的「房间排序 + 订阅 + 为你推荐」恰好就是选择、编排、推广。所以**只要托管了正片，产品做得越好、法律风险越大**。这不是运营注意一下就能绕过的，必须靠架构约束堵死。

§21.2「自营账号发布使平台成为直接内容提供者」的结论仍然成立，那是针对平台自有内容；本章针对用户上传内容，两者叠加时平台责任最重，务必区分。

### 22.4 允许与禁止（写进 ToS，服务端强校验）

| 允许 | 禁止 |
|---|---|
| 剧集元数据：剧名、年份、季/集号、集标题、语言、字幕情况 | 正片视频/音频文件上传、转存、落对象存储 |
| 房主**原创**按语、考据、观后感、追更打卡、讨论 | 搬运 YouTube / 抖音 / Reels / Shorts 短视频、去水印、剪辑合集 |
| **合法观看入口外链**（白名单域名，跳转不嵌入文件） | 指向盗版站 / 网盘 / 未授权聚合站的链接 |
| 用户自制或开放许可的房间封面 | 直接搬用官方海报、剧照、宣传图 |
| 分类信息（沿用 `listing_ext` + `expires_at`） | 转让平台账号 / 共享会员（违反对方 ToS） |
| 官方 embed（须逐平台核对 ToS，仍不落文件） | 对侵权高风险房间/单集做置顶、推荐、广告变现 |

### 22.5 DDL 增量

```sql
-- 迁移脚本须单独提交：PG 中 ALTER TYPE ... ADD VALUE 不可与使用新值同事务
ALTER TYPE content_type ADD VALUE IF NOT EXISTS 'episode';

CREATE TYPE channel_layout AS ENUM ('feed','collection','board');

ALTER TABLE channel
  ADD COLUMN layout channel_layout NOT NULL DEFAULT 'feed',
  ADD COLUMN collection_meta jsonb NOT NULL DEFAULT '{}'::jsonb,  -- 剧名/年份/语言/总季数，仅元数据
  ADD COLUMN cover_licence_ref text,                              -- 封面授权凭证，非空才允许展示
  ADD COLUMN collaborator_limit smallint NOT NULL DEFAULT 2;

-- 从代码层堵死「房间托管正片」：episode 不允许媒体、封面、长正文
ALTER TABLE content ADD CONSTRAINT chk_episode_no_media CHECK (
  type <> 'episode' OR (
    media = '[]'::jsonb
    AND cover_key IS NULL
    AND length(coalesce(body,'')) <= 500
  )
);
ALTER TABLE content ADD CONSTRAINT chk_episode_no_fulltext CHECK (
  type <> 'episode' OR length(coalesce(summary,'')) <= 200
);

CREATE TABLE watch_provider (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name varchar(64) NOT NULL,
  domain citext NOT NULL UNIQUE,
  region char(2) NOT NULL DEFAULT 'GB',
  licence_status varchar(16) NOT NULL DEFAULT 'verified',
  is_active boolean NOT NULL DEFAULT true,
  verified_at timestamptz, note text
);

CREATE TABLE channel_collaborator (
  channel_id uuid REFERENCES channel(id) ON DELETE CASCADE,
  user_id uuid REFERENCES app_user(id) ON DELETE CASCADE,
  can_reorder boolean NOT NULL DEFAULT true,
  added_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (channel_id, user_id)
);

-- 有序编排层：与 channel_item 双写，同一事务保证一致
CREATE TABLE collection_item (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  channel_id uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  season_no smallint NOT NULL DEFAULT 1 CHECK (season_no BETWEEN 1 AND 99),
  episode_no smallint NOT NULL CHECK (episode_no BETWEEN 1 AND 999),
  sort_key varchar(16) NOT NULL,             -- 服务端生成 S01E001，字典序即播放序
  sort_override smallint,                    -- 房主手工微调，留痕
  item_role varchar(16) NOT NULL DEFAULT 'episode',  -- episode/special/extra
  title_hant varchar(120),
  provider_id uuid REFERENCES watch_provider(id),
  external_url text,                         -- 应用层校验域名白名单
  is_locked boolean NOT NULL DEFAULT false,
  created_by uuid NOT NULL REFERENCES app_user(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (channel_id, sort_key),
  UNIQUE (channel_id, content_id),
  CONSTRAINT chk_sort_key_format CHECK (sort_key ~ '^S[0-9]{2}E[0-9]{3}$'),
  CONSTRAINT chk_external_https CHECK (external_url IS NULL OR external_url ~ '^https://')
);
CREATE INDEX idx_collection_order ON collection_item(channel_id, season_no, sort_override, episode_no);

CREATE TABLE user_progress (
  user_id uuid REFERENCES app_user(id) ON DELETE CASCADE,
  collection_item_id uuid REFERENCES collection_item(id) ON DELETE CASCADE,
  state varchar(12) NOT NULL DEFAULT 'seen',
  visibility varchar(12) NOT NULL DEFAULT 'self',   -- UK GDPR：默认仅自己可见
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, collection_item_id)
);

CREATE TABLE takedown_request (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id uuid REFERENCES content(id),
  collection_item_id uuid REFERENCES collection_item(id),
  channel_id uuid REFERENCES channel(id),
  claimant varchar(120) NOT NULL,
  claimant_contact text NOT NULL,
  work_title text NOT NULL,
  infringing_url text,
  received_at timestamptz NOT NULL DEFAULT now(),
  action varchar(16) NOT NULL DEFAULT 'pending',  -- pending/removed/rejected/counter_notice/restored
  acted_at timestamptz, acted_by uuid REFERENCES app_user(id),
  response_sla_hours int NOT NULL DEFAULT 24,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  audit_ref text,
  CONSTRAINT chk_takedown_acted CHECK (action <> 'removed' OR acted_at IS NOT NULL)
);
CREATE INDEX idx_takedown_pending ON takedown_request(received_at)
  WHERE action = 'pending';
```

### 22.6 排序与权限规则

- `sort_key` 由服务端按 `S%02dE%03d` 生成，**房主不可直接编辑**，避免前端伪造；`UNIQUE (channel_id, sort_key)` 防重复集。
- 默认 `ORDER BY season_no, COALESCE(sort_override, episode_no), episode_no`；`sort_override` 变更写 `audit_log`，含旧值、新值、操作人。
- 房主 / 协作者：增删集、改按语、锁定集、微调顺序、审核投稿、转让房主。普通用户：投稿（入审核队列）、打卡、讨论、举报。
- 沿用 §2.4：创建房间需手机验证 + 后台审核；~~每用户最多 3 个房间~~ **已由 §30.3 改判**：一人可创建多个房间，默认软上限 **20 个活跃房间**（`trg_room_quota` + 每小时 3 / 每天 10 的创建速率 + 空房 30 天归档），超过需人工复核。原 3 个上限会掐死「一部剧一个房间」的核心用法。**§32 再改判**：创建房间只要求房间名必填，`room_type` / 挂靠频道 / 版权确认全部可选，想建就建（详见 §32.2）。
- 集号变更视为破坏性操作：禁止直接改，只能删除重建，否则 `user_progress` 会错乱。

### 22.7 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rooms` | 创建房间；**仅 `name` 必填**（§32）；~~`layout=collection`，强制版权确认勾选，写 `audit_log`~~ **已由 §32 改判**：版权确认下移到「发内容」动作，创建空房间零版权门槛 |
| GET | `/rooms/:id` | 房间头 + 季列表 + 订阅状态 + 我的进度 |
| GET | `/rooms/:id/episodes?season=1` | 按 `sort_key` 返回，含 `external_url` 白名单校验结果 |
| POST | `/rooms/:id/episodes` | 新增集；**服务端拒绝任何 `media` / `cover_key` 非空请求（400）**，`external_url` 域名须在 `watch_provider` |
| PATCH | `/rooms/:id/episodes/:eid/order` | 微调 `sort_override`，仅房主/协作者 |
| POST | `/rooms/:id/episodes/:eid/progress` | 追更打卡；默认 `visibility=self` |
| POST | `/rooms/:id/listings` | 复用 §9 分类信息发布，强制 `expires_at ≤ now()+30d` |
| POST | `/reports` | 举报，`reason=copyright` 自动建 `takedown_request` 并告警 |
| POST | `/admin/takedowns/:id/remove` | 24h SLA 内下架，写 `audit_log` + 通知投诉人 |
| POST | `/admin/takedowns/:id/counter-notice` | 反通知与恢复判定 |

### 22.8 版权投诉处置（维持 hosting defence 的最小工程集）

1. ToS 明令禁止侵权上传；~~创建房间 / 添加集时勾选版权确认，勾选事件写 `audit_log`~~ **已由 §32 改判**：创建房间不再强制勾选版权确认，版权确认下移到「上传原创视频文件」与「登记官方外链」两个具体内容动作（§23.3 / §24），勾选事件仍写 `audit_log`。
2. 公开**指定版权投诉联系人与邮箱**；房间页、每一集、全局页脚均有「举报侵权内容」入口。
3. 收到通知 → **24h 内**移除或禁用访问 → 写 `takedown_request` + `audit_log`（保留证据链，不可删）。
4. 反通知（counter-notice）流程与恢复判定留痕；误删可回溯。
5. **重复侵权者政策**：3 次有效投诉 → 冻结该用户发布权限 → 复核后封号。
6. 外链域名白名单 + 疑似盗版站黑名单，服务端校验，不接受前端传入任意 URL。
7. 不做「全面主动监控」（ECR 无此义务），但对已知内容必须处置；**不得对投诉中 / 高风险房间做置顶、推荐或变现**。

### 22.9 分类信息接入

用户明确要求「分类信息发布也可以」。做法：房间内二级 Tab「本房间分类信息」→ 复用 `content.type='listing'` + `listing_ext`（城市、价格、PostGIS 位置、联系方式 AES-GCM 加密、`is_verified`）+ §8 强制 `expires_at`。全局「伦敦租房 / 二手 / 活动」频道改挂 `layout='board'`，两者共用同一套发布、审核、过期、举报管道。原型 `prototype-collection-room.html` 已演示：发布需审核、手机号验证、30 天自动过期、认证徽章。

### 22.10 推荐流的处理（§20 合规回退的延续）

- **房间卡片**可进「为你推荐」（频道级共现，可解释，标 `reason_code=similar_channels`）。
- **具体单集卡片、外链、按语一律不得进推荐流、不得置顶、不得推送**；只在「正在关注」Tab 中以「本房间新增 N 集」摘要形式出现。
- `report_count` 超阈值、含未认证外链、处于版权投诉中的房间，自动从推荐池剔除并降权。
- §20.6 的 OSA 风险评估继续适用；本章另需在合规文档中补一份**版权投诉处置流程记录**，两者分开存档。

### 22.11 原型与验收

交付 `C:/Users/Administrator/Documents/uk/prototype-collection-room.html`（单文件无外部依赖，与 §20 原型同一套视觉与深浅色/移动视图）。可点部分：季 Tab、集列表固定排序、标记已看与进度条、加入/退订房间、房主添加一集（**表单不提供视频上传**）、上移下移微调、按集号重排、二级 Tab 切到分类信息并发布（进审核、30 天过期）、深浅色与 420px 移动视图。**v4 起另增**「我的房间」切换器（多房间 / 20 集剧房间 / 电影名房间 / 新建房间）、「留言 · 讨论」Tab、`@用户名` / `#关键词` 渲染与「用户自建 · 非官方」徽章，详见 §30。示例剧目选《新闻女王》，刻意用繁体/粤语场景呼应 §1 的差异化判断；每集只显示合法观看平台徽章与外链，不显示播放器。

**验收点**：① 前端无上传控件，直接 POST 带 `media` 的 `episode` 被 `chk_episode_no_media` 拒绝；② 非白名单域名外链被 400；③ 重复 `sort_key` 被唯一约束拒绝；④ 举报后 24h 内下架且 `takedown_request` / `audit_log` 可查；⑤ 房间单集不出现在「为你推荐」；⑥ 分类信息 30 天自动过期；⑦ 换房主不影响排序与用户进度；⑧ 无 `cover_licence_ref` 的封面不展示。

### 22.12 排期与人力（相对 §21 的重算）

「数据来源全部来自用户」意味着 **MVP 可以完全不做采集管线与 AI 草稿**，这是本轮最大的成本红利：

| 方案 | 周期 | 内容 | 适用 |
|---|---|---|---|
| **A 房间优先（推荐）** | **4 周** | 注册订阅 + 房间 CRUD + 排序/进度 + 分类信息 + 审核举报 + takedown 后台 + 三 Tab 首页 | 砍掉采集与 AI，验证「用户愿不愿意自己建房间」 |
| B §21 混合版 + 房间 | 5–6 周 | 上述 + 1–2 个 L1 源 + AI 草稿 + 素材队列 | 官方资讯频道与房间同时上 |

A 周计划：W1 DDL 迁移 + 房间/订阅模型 → W2 房间页 + 排序 + 进度 + 分类信息挂载 → W3 审核举报 + 版权投诉后台 + 白名单 → W4 种子房间（平台自建 3–5 个示范房间，全部走同一套用户流程）+ 灰度 + 监控。**§21 的 `editorial_draft`、AI 摘要草稿、多路采集、事件聚类自动化全部推到 M2。**

人力变化：编辑 OPEX 从 §21 的 0.5–1 人降到近 0；新增的是**审核与版权处置**，按每千条 UGC 约 0.2 人估，MVP 阶段可由开发/运营兼任，但**必须有人负责 24h SLA**，不能无人值守。

### 22.13 风险、常见坑与待确认

**风险**：① 若用户实际诉求是「能看片」而非「追剧清单」，本方案与期望会错位，需在启动前对齐；② 用户自建内容密度依赖种子房间与房主活跃度，冷启动要平台先自建 3–5 个示范房间；③ 版权处置是持续义务，不是一次性开发；④ 繁体/粤语内容占比不足会让差异化落空。

**常见坑**：
1. 把房间做成资源站 —— 本轮最致命，见 §22.3 的 active participant 问题。
2. 用官方海报当封面 —— 海报、剧照同样是受保护作品，`cover_licence_ref` 非空才展示。
3. 允许任意外链或网盘链接 —— 等于盗版导航，白名单必须服务端校验。
4. 对房间/单集做置顶、推荐、广告 —— 侵蚀被动托管地位，见 §22.10。
5. 只在前端隐藏上传按钮，服务端不校验 —— DB CHECK + 服务端 400 双保险。
6. 房主直接改集号 —— 会让 `user_progress` 错乱，只能删后重建。
7. 分类信息忘挂 `expires_at` —— 复用 §8 的 `chk_listing_expiry`，30 天自动过期。
8. 把 OSA 当版权投诉依据 —— OSA illegal content 明确排除 IP 侵权，法律依据是 CDPA + ECR 2002。
9. 追更进度默认公开 —— UK GDPR 下应默认 `visibility=self`。
10. 冷启动等用户来建房间 —— 上线当天就要有 3–5 个填满的示范房间。

**待裴总确认**：① 首版就开放用户建房间，还是先只做平台示范房间（决定审核量）；② 是否允许官方 embed 播放器（建议允许但逐个核对 ToS，仍不落文件）；③ 分类信息是否保留全局 `board` 频道，还是只挂在房间内（建议两者都要）。

---

## 23. 房间类型扩展：电影、视频与原创媒体（2026-11-09 第四轮增补）

### 23.1 结论：把「房间也可以放电影、视频」拆成三件事

| 诉求 | 产品形态 | 是否托管文件 |
|---|---|---|
| 放电影 | **片单房间**：无季/集，按自定义顺序 / 年份 / 系列排 | ❌ 整片不上传、不转存；只登记片名、年份、片长、合法观看入口 |
| 放视频（他人影视内容） | **官方外链卡片 / 官方 embed**（逐平台核对 ToS） | ❌ 不下载、不转存、不落对象存储 |
| 放视频（用户自己拍的） | **原创短视频条目**（当地生活、探店、活动记录） | ✅ **可以托管**，走 `media_origin = original_user` 通道 |

**对 §22 的一处修正**：§22.5 的 `chk_episode_no_media` 把媒体写死为空，对「剧集元数据条目」是对的，但会误伤第一轮就提出的「用户自己也可以发布信息和视频」。本轮把它推广为基于 `media_origin` 的通用约束——**只有用户原创内容允许落媒体文件**，其余一律空。§22 的其余结论（不托管正片、OSA 不管 IP、hosting defence、24h 下架、推荐流限制）全部不变。

**电影比剧集更不能碰**：托管一整部电影是完整复制整部作品，连「片段 / 摘要」的争议空间都没有；且电影房间最容易诱导用户上传全片，产品上要把上传入口从电影房间彻底移走（只保留到原创视频房间）。

### 23.2 房间类型与 UI / 排序

`channel.room_type` 在**创建时选定一次**（原型顶部切换仅用于预览），决定 UI 形态与排序，不在运行中混用：**§32 改判**：`room_type` 改为**可选、可空、默认 `general`（通用圈子）、创建后可改**，不再是创建前置（详见 §32.2）；下述 `series / film / video` 三种形态仍是「后设的编排选项」，仅影响 UI 与排序：

| `room_type` | 内容单元 | 排序 | UI 形态 | 进度语义 |
|---|---|---|---|---|
| `general`（§32 新增默认） | 任意内容 / 分类信息 / 留言 | `published_at DESC` | 通用信息流 | 活跃度（本周新增） |
| `series` | 季 → 集 | `season_no, COALESCE(sort_override, episode_no)`，固定不重排 | 季 Tab + 集列表 | 追更「已看 N / 总集数」 |
| `film` | 单部影片 | `custom`（片单顺序）/ `film_year ASC|DESC` | 海报位网格卡片（**纯色占位，非官方海报**） | 「想看 / 看过」+ 已看进度 |
| `video` | 原创短视频 / 官方外链卡片 | `published_at DESC` | 缩略色块 + 时长 + 来源徽章 + 播放/跳转 | 本周新增条数（活跃度） |

三者共用同一张 `content` 主表、`channel_item` / `collection_item` 编排层、订阅、审核、举报、分类信息挂载与三 Tab 首页。`item_role` 扩展为 `episode / special / film / clip / original_video`，**不再新增 `content_type` 枚举值**：元数据条目仍用 `episode`，原创视频沿用 v1.0 已有的 `video` 类型。

### 23.3 法律分层：`media_origin` 四态

```text
none            纯元数据条目（剧集/电影/特别篇）：无媒体、无封面、正文 ≤500 字
external_link   合法观看入口跳转卡片：域名须在 watch_provider 白名单
licensed_embed  官方 embed：逐平台核对 ToS，文件不落本地
original_user   用户原创视频：唯一允许 media 非空的通道
```

原创视频可托管的**前置条件**（缺一不可，服务端强校验）：

1. 上传时勾选版权确认：本人原创、画面中人物已同意、未使用未授权音乐或影视片段，记录 `rights_confirmed_at/by` 并写 `audit_log`；
2. 手机号验证 + `sha256` 全局哈希去重（同时是已知侵权内容的哈希黑名单基础）；
3. 首版限制 **≤ 60 秒 / 100 MB / video\***，病毒扫描 + 人工审核，通过前仅自己可见；
4. 纳入 §22.8 的同一套 notice-and-takedown、24h SLA、反通知与重复侵权者政策；
5. ToS 明确用户对素材授权负责（画面肖像、背景音乐、商标入镜）；UK GDPR 下他人可要求删除；
6. **不得**对投诉中 / 未审核 / 高风险房间做推荐、置顶或变现，维持 §22.3 的被动托管地位。

> 依据仍是 §22.3：OSA 2023 的 illegal content 排除知识产权侵权；平台依赖 CDPA 1988 + E-Commerce Regulations 2002 的 hosting defence。原创视频托管本身合法，但平台仍需具备快速下架与处置留痕能力。

### 23.4 DDL 增量

```sql
CREATE TYPE room_type AS ENUM ('series','film','video');
CREATE TYPE media_origin AS ENUM ('none','external_link','licensed_embed','original_user');

ALTER TABLE channel
  ADD COLUMN room_type room_type,
  ADD COLUMN room_sort_mode varchar(16) NOT NULL DEFAULT 'custom';  -- custom/year_asc/year_desc/recent
ALTER TABLE channel ADD CONSTRAINT chk_room_type CHECK (
  (layout = 'collection' AND room_type IS NOT NULL)
  OR (layout <> 'collection' AND room_type IS NULL)
);

ALTER TABLE content
  ADD COLUMN media_origin media_origin NOT NULL DEFAULT 'none',
  ADD COLUMN rights_confirmed_at timestamptz,
  ADD COLUMN rights_confirmed_by uuid REFERENCES app_user(id);

-- 替换 §22.5 的 chk_episode_no_media：只有原创内容可落媒体
ALTER TABLE content DROP CONSTRAINT IF EXISTS chk_episode_no_media;
ALTER TABLE content ADD CONSTRAINT chk_media_origin CHECK (
  media_origin = 'original_user'
  OR (media = '[]'::jsonb AND cover_key IS NULL)
);
ALTER TABLE content ADD CONSTRAINT chk_original_confirmation CHECK (
  media_origin <> 'original_user'
  OR (rights_confirmed_at IS NOT NULL AND rights_confirmed_by IS NOT NULL)
);
ALTER TABLE content ADD CONSTRAINT chk_metadata_body CHECK (
  media_origin = 'original_user' OR type = 'video' OR length(coalesce(body,'')) <= 500
);

-- collection_item：电影/视频条目无季集，季集相关列改为可空
ALTER TABLE collection_item
  ALTER COLUMN season_no DROP NOT NULL,
  ALTER COLUMN episode_no DROP NOT NULL,
  ALTER COLUMN sort_key DROP NOT NULL,
  ADD COLUMN film_year smallint,
  ADD COLUMN runtime_min smallint,
  ADD COLUMN watch_state varchar(12) NOT NULL DEFAULT 'unwatched';
ALTER TABLE collection_item ADD CONSTRAINT chk_series_fields CHECK (
  item_role IN ('film','clip','original_video')
  OR (season_no IS NOT NULL AND episode_no IS NOT NULL AND sort_key IS NOT NULL)
);

CREATE TABLE media_asset (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  object_key text NOT NULL,
  sha256 varchar(64) NOT NULL,
  duration_sec int NOT NULL CHECK (duration_sec BETWEEN 1 AND 60),
  size_bytes bigint NOT NULL CHECK (size_bytes <= 104857600),
  mime varchar(64) NOT NULL,
  moderation_status varchar(16) NOT NULL DEFAULT 'pending',
  virus_scan varchar(16) NOT NULL DEFAULT 'pending',
  uploader_id uuid NOT NULL REFERENCES app_user(id),
  rights_confirmed boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_asset_rights CHECK (moderation_status <> 'approved' OR rights_confirmed)
);
CREATE UNIQUE INDEX idx_asset_hash ON media_asset(sha256);
CREATE INDEX idx_asset_moderation ON media_asset(moderation_status, created_at);
```

`watch_provider` 白名单同步扩充 MUBI（英国区）、BFI Player、iQIYI 国际版、TVB Anywhere、myTV SUPER、YouTube 官方频道、Netflix 英国区；非白名单域名一律 400。

### 23.5 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rooms` | 增加 `room_type` / `room_sort_mode`，创建后不可改类型 |
| PATCH | `/rooms/:id/sort-mode` | 片单排序切换（custom / year_asc / year_desc） |
| POST | `/rooms/:id/films` | 新增影片；**拒绝任何 `media` / `cover_key` 请求**，服务端 400 |
| POST | `/rooms/:id/films/:fid/state` | 想看 / 看过，`user_progress` 兼容 |
| POST | `/rooms/:id/media/upload-url` | 仅 `room_type=video` 且 `media_origin=original_user` 时签发；返回一次性上传 URL |
| POST | `/rooms/:id/media` | 登记 `media_asset`：校验哈希、时长、大小、版权确认、病毒扫描 → 进审核队列 |
| POST | `/admin/media/:id/approve` | 人工审核通过后才公开；驳回写 `audit_log` |
| GET | `/admin/media?status=pending` | 审核队列，含哈希命中提示 |

### 23.6 审核与风控（原创专属）

原创视频是本项目**唯一**需要真实内容审核的 UGC 类型，其余条目只做元数据/外链校验。队列按 `created_at` 排序，SLA 24h；哈希命中已下架侵权内容的 `sha256` 时直接拒绝并记 `audit_log`；同一用户 7 天内 3 次驳回自动限流。所有上传、确认、审核、下架操作写 §22.8 的同一套处置台账，便于向权利人证明「expeditiously removed」。

### 23.7 UI / UX 规范（本轮按 ui-ux-pro-max 设计系统执行）

**设计系统取舍**：工具给出的推荐是紫色 Vibrant & Block-based + Community/Forum Landing + Noto Serif TC / Noto Sans TC。本项目**保留 X 式蓝色三栏与 PWA 移动底部 Tab**——风格一致性优先，且与 §20 原型是同一套产品，换主色会变成两个产品。采纳的部分：社区活跃度指标（「今日新增 3 集」脉冲点 + 成员数 + 本周活跃）、繁体场景的 Noto Serif TC / Noto Sans TC 本地字体栈（**不加载外部字体，保持单文件零依赖**）、块状高对比用于海报位与房间类型 chip。

**已落地的硬性规则**（`prototype-collection-room.html` v2）：

| 规则 | 落地 |
|---|---|
| 触控目标 ≥44×44px | `.icon-btn` / `.back` / `.op` / `.mini-btn` / `.subtab` / `.room-tab` / `.season` / `.mark` / `.join` / `.watch` / `.state-btn` / 底部 Tab 全部 ≥44px |
| 可见焦点环 | 全局 `:focus-visible{outline:2px solid var(--accent)}`；图标按钮全部 `aria-label`；缩略图 `role="button" tabindex="0"` + Enter/Space 触发 |
| 减少动效 | `@media(prefers-reduced-motion:reduce)` 关闭全部 transition/animation/smooth-scroll；常规动效 200–250ms，仅用 transform/opacity |
| 表单可访问 | 每个 `input/select` 均有 `for`/`id` 关联；`<label class="check" for="vConfirm">` 可点；错误用就近 toast 反馈 |
| 对比度 | 深色 `--muted` 由 `#71767b` 提到 `#9aa6b1`（约 6:1）；浅色保持 `#536471`；语义色 `--good/--warn` 在两种主题下分别取值 |
| 图标一致性 | 全部换成 24×24 viewBox 内联 SVG symbol（stroke 1.8），移除 emoji 与 Unicode 符号图标 |
| 状态不只靠颜色 | 「已看 / 想看 / 审核中 / 原创 / 官方外链」均为文字 + SVG + 颜色三重指示 |
| 响应式 | 375 / 768 / 1024 / 1440 四档；移动端正文 16px（§36.12 起帖子正文改 15px / 1.5，输入框 16px）、两列片单、`.ep-ops` 纵向排列；`body{overflow-x:hidden}` 防横向滚动 |
| 稳定 hover | 只改 background / border-color / opacity，无 scale、无布局位移；全可点元素 `cursor:pointer` |
| 图片替代 | 无外链图片；封面为纯色占位并带 `role="img"` + `aria-label` 说明「非官方海报」（同时规避版权） |
| 层级 | z-index 约定：sticky 顶栏 20、底部 Tab 30、toast 50 |

### 23.8 原型 v2 验收点

`prototype-collection-room.html` 已升级为三种房间形态可切换：剧集（季 Tab / 集序 / 追更）、电影（片单网格 / 年份排序 / 想看看过）、视频（原创卡片与官方外链卡片分色标注 / 播放与跳转 / 举报）、以及共用的「本房间分类信息」二级 Tab 与发布审核流程。

验收点：① 剧集与电影房间**没有**任何文件上传控件；② 原创视频表单不勾选版权确认无法提交，提交后为「审核中」且仅自己可见；③ 官方外链卡片点击是跳转提示而非本地播放；④ 电影封面为纯色占位、无官方海报；⑤ 三种房间的订阅、进度、分类信息共用同一套状态；⑥ 键盘 Tab 可到达所有交互元素且焦点可见；⑦ 切换深浅色与 420px 移动视图后无横向滚动、触控目标不缩小；⑧ 开启系统「减少动效」后无过渡动画。

### 23.9 排期与人力

相对 §22.12 的方案 A（4 周）**净增约 3–5 天**：DDL 迁移与 `media_origin` 约束 1 天、片单/视频两种渲染与排序 2 天、原创上传与审核队列 1–2 天、无障碍整改 1 天。原创视频审核带来**新增持续人力**（按每百条原创约 0.2 人估），可与 §22 的 24h 版权投诉 SLA 由同一人兼任；若首版不愿承担审核，可先只开 `series` + `film` 两种房间，把 `video` 留到 M2（此时原型里的上传入口隐藏即可，DDL 已预留）。

### 23.10 风险、常见坑与待确认

**常见坑**：① 把「房间可以放视频」理解成「可以放别人家的片」——见 §23.1，只有原创可托管；② 给电影房间也加上传按钮；③ 用官方海报做片单封面；④ 原创视频跳过哈希去重或审核直接公开；⑤ 忘记让用户确认人物同意与背景音乐授权（这两项是原创 UGC 最常见的隐性侵权）；⑥ 把 `media_origin` 做成前端可传字段（必须服务端按房间类型与接口签发，不许客户端自选）；⑦ 电影房间沿用剧集的「季/集」必填约束导致无法保存；⑧ 三种房间各自写一套订阅/审核逻辑（应共用）。

**待裴总确认**：① 首版是否同时开三种房间，还是先 `series` + `film`（`video` 涉及真实审核人力）；② 原创视频时长上限接受 60 秒 / 100 MB 吗（§21 原为 15 秒）；③ 官方 embed 播放器是否开放 —— **本轮已按「允许但受限」落地，详见 §24**。

## 24. 外链站内播放（inline embed）规范（2026-11-09 第五轮增补）

### 24.1 结论：采纳，但形态是「播放入口」不是「媒体文件」

裴总提出：像 Telegram 频道一样，用户贴官方视频链接后**在 App 内直接播放**，不跳出。

采纳。但准确表述是：**平台提供一张「点击才加载的官方 iframe 卡片」，媒体流始终由第三方平台提供、由用户浏览器直连**。房间 / 频道里存的仍然是链接与元数据，不是片。

分层不动：消费层（§20 三 Tab）、编排层（§22 `collection_item`）、供给层（§21 / §23）、统一内容池与订阅关系全部沿用。本轮新增的只有两件东西：服务端 `embed_provider` 解析校验管线，前端 `EmbedPlayerCard` 渲染组件。§23.3 的 `media_origin = 'licensed_embed'` 四态正好复用，**不新增枚举值、不新增 `content_type`**。

### 24.2 法律核实（本轮新增，会改变白名单结论）

英国走 **CDPA 1988 §20「向公众传播 / making available」**，不是 OSA 2023。

- **Svensson (C-466/12) / BestWater (C-348/13)**：链接或框架嵌入「权利人已同意、免费公开、不绕过技术保护措施、不构成新公众」的内容，不需另行授权。
- **VG Bild-Kunst (C-392/19)**：framing 本身属于 communication to the public；若权利人设置了防框架技术措施并被规避，必须取得明示授权。
- **TuneIn v Warner Music UK [2021] EWCA Civ 441**：英国上诉法院明确**拒绝背离** retained EU case law，并把脱欧后才判决的 VG Bild-Kunst 视为「高度有说服力」加以适用。核心结论：即便源站在别处免费可得，**若平台把传播定向到英国、而源站没有英国地区授权，仍构成侵权**。
- **GS Media (C-160/15)**：商业性经营者对明显侵权内容有合理核查义务，「不知情」不是万能挡箭牌。

对本项目三条直接后果：

1. **「英国区可看性」从产品差异化升级为合规硬要求**。§22 定的差异化（哪部中文剧在英国哪个平台能合法看、更到第几集）现在同时是 TuneIn 式地域授权校验的依据，产品价值和法律要求同向。
2. **B 站 / 爱奇艺 / 优酷 / 抖音等大量内容仅中国大陆授权，MVP 不纳入白名单**，用户粘贴一律驳回或仅登记。这条对用户体感影响最大，需在产品文案里说清楚「为什么英区不能播」。
3. 不得绕过付费墙、登录、地区限制、防嵌入措施；不得嵌入明知 / 应知侵权内容；须遵守来源平台 ToS（YouTube 允许 embed，但要求保留播放器控件、品牌与广告，禁止去广告、禁止包装成自家播放器、禁止自动播放牟利）。

**OSA 2023 结论不推翻**：illegal content 定义排除知识产权侵权（§22.2 已核实）。但用户举报、儿童保护与风险评估义务照常适用，且需在非法内容风险评估中新增「第三方嵌入内容的举报路径与处置时效」。

### 24.3 工程红线（写进代码评审清单，三条）

1. **禁止服务端代理 / 转存 / 缓存媒体流**。一旦服务端拉取第三方流再转发给客户端，性质从「超链接 / 框架」变成平台自己 making available + 复制，Svensson 空间与托管抗辩同时丧失。CDN 不缓存第三方媒体，CSP `frame-src` 只列白名单。
2. **禁止任意 URL**。只接受白名单官方域名与规范化 `media_id`；短链、跳转链、直链（`.m3u8` / `.mp4`）、盗版域名一律拒绝。服务端先白名单再发请求，防 SSRF（禁内网地址、限重定向次数）。
3. **禁止默认加载**。列表页只渲染静态占位卡，用户点击 + 同意后才创建 iframe。这一条同时解决 PECR 同意、首屏性能与自动播放三个问题。

### 24.4 PECR / UK GDPR（本轮核实）

- 第三方 iframe 在页面加载时即向第三方传 IP、设备与浏览信息并可能设置 cookie，属非必要 storage / access，**PECR Reg 6 要求事前同意**。Data (Use and Access) Act 2025 的 cookie 修订自 2026-02-05 生效、ICO 最终指南 2026-04-29 发布；新增豁免很窄，**第三方 embed 基本不符合**。
- **ICO 明确口径**：用户主动选择观看嵌入内容且告知充分时，可视为「提供用户所请求服务所严格必需」；或在与该功能交互的时点取得同意。→ 本方案采用 **click-to-load + 一次性告知 + 三选项**。
- 三选项：① **仅本次加载**（用户主动请求，写 `user_consent_log`）；② **总是允许此平台**（按 provider 记偏好，含时间戳与政策版本，可撤回 / 导出 / 删除）；③ **去原站看**（完全不加载）。
- 必须清晰说明第三方是谁、会收到什么数据；`youtube-nocookie.com` 隐私增强域名可降低但**不免除**告知义务。
- **收起播放器 = 销毁 iframe DOM 节点**，不只是 `display:none`；切换 Tab / 路由离开同样销毁，断开第三方连接。

### 24.5 分发规则（延续 §22.9 并收紧）

- embed 卡片可出现在「正在关注」时间流、房间内、频道页。
- **不进「为你推荐」、不进每日精选、不置顶、不推送**。理由：TuneIn 的「定向传播」与 §22 的主动参与问题 —— 平台不应主动组织、放大第三方受版权保护内容。
- 官方自动频道（§2 L1）不得批量自动嵌入；只有用户 / 房主显式贴链接并审核通过后才生成卡片。
- 单条只显示来源徽章 + 标题 + 时长 + 「在原站观看」+ 举报，**不复制缩略图、简介、字幕、剧照**。

### 24.6 服务端解析与降级

流程：提交 URL → 规范化（去跟踪参数、解析 provider + `media_id`）→ 域名白名单 → 英国区授权标记 → oEmbed / 官方 API 取**元数据**（标题、作者、时长，不落缩略图）→ 探测 `X-Frame-Options` / `CSP frame-ancestors` → 写 `embed_status` → 进审核队列 → 通过后才可见。

| `embed_status` | 触发 | 前台表现 |
|---|---|---|
| `embeddable` | 白名单 + 英区可看 + 允许框架 | 静态占位卡，点击后加载官方 iframe |
| `fallback` | 源站禁止嵌入 / 地区不可用 / 内容删除 | 只显示「去原站看」跳转卡，**不尝试破解** |
| `pending` | 待人工审核 | 不可见或仅房主可见 |
| `removed` | 举报下架 / takedown / 源站复查 404 | 替换为「内容已下架」，保留处置记录 |

每日定时复查源站删除、地区变化、ToS 变更 → 自动降级或移除，避免长期挂死链。下架处置对象是**链接**，24h SLA、反通知、重复侵权者政策沿用 §22.8。

### 24.7 DDL 增量

```sql
-- 平台白名单：逐个核对 ToS 与英国区授权后录入
CREATE TABLE embed_provider (
  code               text PRIMARY KEY,
  display_name       text NOT NULL,
  allowed_hosts      text[] NOT NULL,
  embed_url_template text NOT NULL,      -- 例 https://www.youtube-nocookie.com/embed/{id}
  oembed_endpoint    text,
  allows_framing     boolean NOT NULL DEFAULT false,
  uk_rights_verified boolean NOT NULL DEFAULT false,
  tos_ref            text NOT NULL,      -- 条款链接 + 核对日期
  third_party_notice text NOT NULL,      -- 隐私告知文案
  consent_required   boolean NOT NULL DEFAULT true,
  enabled            boolean NOT NULL DEFAULT false,
  checked_at         timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE content ADD COLUMN embed_provider_code text REFERENCES embed_provider(code);
ALTER TABLE content ADD COLUMN embed_media_id      text;
ALTER TABLE content ADD COLUMN embed_source_url    text;
ALTER TABLE content ADD COLUMN embed_checked_at    timestamptz;
ALTER TABLE content ADD COLUMN embed_status        text NOT NULL DEFAULT 'none'
  CHECK (embed_status IN ('none','pending','embeddable','fallback','removed'));

-- 硬约束一：嵌入类内容绝不落媒体文件（复用 §23.3 的 media_origin）
ALTER TABLE content ADD CONSTRAINT chk_embed_no_media CHECK (
  media_origin <> 'licensed_embed' OR (media = '[]'::jsonb AND cover_key IS NULL)
);
-- 硬约束二：嵌入类必须有规范化来源、审核状态，且正文仅限原创按语
ALTER TABLE content ADD CONSTRAINT chk_embed_source CHECK (
  embed_status = 'none' OR (
    embed_source_url ~ '^https://' AND embed_provider_code IS NOT NULL
    AND embed_media_id IS NOT NULL AND length(body) <= 500
  )
);

CREATE TABLE user_consent_log (
  id             bigserial PRIMARY KEY,
  user_id        uuid NOT NULL REFERENCES app_user(id),
  provider_code  text NOT NULL REFERENCES embed_provider(code),
  scope          text NOT NULL CHECK (scope IN ('once','always','withdrawn')),
  policy_version text NOT NULL,
  created_at     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX ON user_consent_log(user_id, provider_code, created_at DESC);
```

`user_consent_log` 只追加，不存内容 ID 与观看记录（数据最小化）；「总是允许」的当前状态取该用户 + provider 最新一条，撤回即写 `withdrawn`。

### 24.8 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/v1/embed/resolve` | 提交 `{url}`，返回 provider / `media_id` / `embed_status` / `uk_rights_verified` / 拒绝原因；**只解析不发布** |
| POST | `/v1/channels/{id}/items/embed` | 创建外链条目，服务端重新校验，进审核队列 |
| GET | `/v1/embed/{content_id}/consent` | 返回该 provider 的当前偏好与告知文案 |
| POST | `/v1/embed/{content_id}/consent` | `{scope: once\|always\|withdrawn}` 写 `user_consent_log` |
| POST | `/v1/embed/{content_id}/report` | 链接类举报 → `takedown_request`，24h SLA |
| POST | `/v1/admin/embed/recheck` | 定时复查，批量降级 / 移除 |

错误码：`EMBED_PROVIDER_NOT_ALLOWED`、`EMBED_UK_RIGHTS_UNKNOWN`、`EMBED_FRAMING_BLOCKED`、`EMBED_SHORTLINK_REJECTED`、`EMBED_REMOVED`。

**信任边界在服务端**：前端拿到 `embeddable` 后仍不得自行拼接 embed URL，iframe 地址只能由服务端按 `embed_url_template` 下发；前端不得默认创建 iframe。

### 24.9 前端组件与无障碍

`EmbedPlayerCard` 四态与原型一致：idle / consent / playing / fallback|removed。

- 占位卡显示：来源平台徽章、标题、时长、第三方数据提示、「站内播放」「去原站看」。
- iframe：`loading="lazy"`、`referrerpolicy="strict-origin-when-cross-origin"`、`allow` 不含 `autoplay`；不使用会破坏播放器的 `sandbox`；保留平台控件、品牌与广告。
- CSP：`frame-src` 只列白名单域名；`connect-src` / `img-src` 不因 embed 放开。
- PWA / WebView：iOS 需用户手势才能起播，click-to-load 天然满足；部分平台在 WebView 内拒绝 embed → 走 `fallback`。
- 无障碍沿用 §23.7：44px 触控目标、`:focus-visible`、SVG + 文字 + 颜色三重状态指示、`aria-label`、`prefers-reduced-motion`、移动端正文字号见 §36.12（帖子正文 15px / 1.5，输入框 16px）；播放器内部不可控，需在卡片外层提供文字等价说明。

### 24.10 原型验收点（v3）

- `prototype-collection-room.html` v3：视频房间点封面 /「站内播放」→ 同意面板（仅本次 / 总是允许 / 去原站看）→ 模拟官方播放器；「收起」卸载；源站禁止嵌入的条目只给「去原站看」；英区无授权的条目显示「仅登记」；「添加外链视频」粘贴 URL 实时校验（YouTube 通过 / 大陆限定平台拒绝 / 短链拒绝），**表单无文件上传控件**；剧集房间 YouTube 官方预告共用同一组件。
- `prototype-x-style.html`：「正在关注」出现外链卡并可站内播放；「为你推荐」**不出现**该卡（顶部说明已标注）。
- 两原型均为单文件零外部依赖，深浅色与 420px 移动视图可用，44px 触控目标、label 关联与焦点环无缺失。

### 24.11 排期与成本

相对 §23 净增 **2–3 天**：DDL 与约束 0.5d、服务端解析 / 白名单 / SSRF / 框架探测 1d、前端组件与 CSP 1d、同意记录与定时复查 0.5d。

**成本反而更低**：媒体流不经平台，无带宽、无转码、无对象存储费用（§23 原创视频托管有）。新增的是「链接审核」与 24h 下架人力，可与 §22 版权处置由同一人兼任。

建议首版**只开 YouTube 官方（`youtube-nocookie`）一个 provider**，把 ToS 核对、英区授权、框架探测、同意记录跑通后再逐个加 Vimeo / TVB 官方。

### 24.12 常见坑

① 为了「播得更顺」做服务端代理 / 缓存媒体流（最致命，法律性质直接改变）；② 把 B 站 / 爱奇艺等大陆限定链接放进白名单（TuneIn 地域授权）；③ 列表页自动创建 iframe（PECR 违规 + 性能 + 自动播放）；④ 以为用 `youtube-nocookie` 就免告知；⑤ 去广告、隐藏原平台 logo、把播放器包装成自家 UI（违反 ToS 且强化「主动参与」）；⑥ 下架只删数据库记录，不销毁 iframe、不清 `embed_status`；⑦ 把 embed 卡片放进「为你推荐」或推送；⑧ 前端自行拼接 embed URL 绕过白名单；⑨ 收起播放器只 `display:none`，第三方仍在后台连接；⑩ 短链 / 跳转链未规范化就入库。

### 24.13 待裴总确认

① 首版白名单是否只开 YouTube 官方（建议是）；② 是否保留「总是允许此平台」这一持久偏好（涉及 UK GDPR 同意记录与撤回，若嫌繁琐可只保留「仅本次加载」）；③ 是否接受「外链卡片不进为你推荐」（若要求进推荐流，需先补一份推荐系统对第三方版权内容的法律评估）。

---

## 25. 设计规范系统索引（2026-11-09 第六轮增补）

**本章只做索引，视觉准绳已独立成体系**：`design-system/MASTER.md`（Global Source of Truth）。本 PRD 定义「做什么」，设计系统定义「长什么样、怎么点」；功能冲突以 PRD 为准，视觉冲突以 MASTER 为准。

### 25.1 交付物

| 文件 | 作用 |
|---|---|
| `design-system/MASTER.md` | 完整规范：设计原则、一致性审计、颜色/字体/间距/动效、组件库与状态矩阵、合规 UI、响应式、无障碍、开发交付、迁移清单、QA 门禁 |
| `design-system/tokens.css` | **唯一可 import 的 CSS 变量与基础类**，Vue3 在 `main.ts` 引入一次；组件禁止硬编码颜色/尺寸 |
| `design-system/preview.html` | 单文件零依赖的组件与 token 展示页，深浅色 / 420px 移动视图 / 全部组件状态可点 |
| `design-system/pages/home-feed.md` | 三 Tab 首页页面级 override |
| `design-system/pages/collection-room.md` | 剧集 / 电影 / 视频房间页面级 override |
| `design-system/check-contrast.py` | WCAG 对比度断言门禁 |
| `design-system/check-ui.js` | 脚本语法、标签平衡、SVG 引用、label 关联、CSS 变量定义，并**真实执行** preview 脚本与主要交互 |

### 25.2 本轮关键裁决（影响已交付原型）

从两份原型反向提取 CSS 后裁决 **12 处真实不一致**：深色 `--muted` 统一 `#9aa6b1`（旧值在卡片上仅 3.88:1）、浅色语义色统一 `#00875a` / `#a86800`（旧值 2.53 / 1.87 几乎不可读）、三栏统一 `240/1fr/320`、`line-height:1.6`、图标尺寸与底部栏统一 44px / 60px。

**最重要的一条架构改动**：品牌蓝 `#1d9bf0` 在白底只有 **3.00:1**，做小字链接与「白字蓝底」主按钮都不达 AA。因此把品牌装饰色与可读文字色分离为 5 个 token：`--accent`（仅装饰）/ `--accent-ink`（链接）/ `--accent-strong` + `--on-accent`（按钮配对）/ `--focus`（独立焦点环，修补浅色卡片上 2.84:1 的缺陷）。深色主题按钮为「亮蓝底 + 近黑字」，浅色为「深蓝底 + 白字」。

**合规 UI 升格为一等组件**：`SourceBlock`（来源名 + 许可徽章 + 原文回链）、四态状态徽章、常驻举报入口、`ConsentPanel` 三选项、版权确认勾选项，全部写入规范，不允许开发当装饰省略。

### 25.3 落地状态

两份原型已完成 P0 全部项与主要 P1 项迁移（变量块、链接色、按钮配对、焦点环、栅格、字体栈、触控尺寸），**交互逻辑与数据结构未改动**。§27 增补时首页 13 处 Unicode 图标已全部替换为 9 个 24×24 SVG symbol（§11 最后一项 P1 收尾），`check-ui.js` 现为零 WARN。

### 25.4 发布门禁

```bash
python design-system/check-contrast.py   # 32 组配对，正文 ≥4.5:1 / 控件 ≥3:1
node design-system/check-ui.js           # 静态检查 + 真实执行页面脚本与交互
node design-system/check-global.js       # §26 区域包 / 频道图谱推荐 / 法域角标回归
node design-system/check-media.js        # §27 + §29 媒体布局 / 默认播放 / 右上角加入 / 无底部播放按钮 / 冷启动
node design-system/check-location.js    # §28 + §29 定位状态机 / 开通权限 / 未开法域回退 / 设置浮层可达
node design-system/check-rooms.js       # §30 顶部搜索/多房间/留言/@#/AI 关键词 + §31 创建房间 + §32 房间轻量化/上频道/加入通知
```

任一返回非 0 即禁止发布。语法检查不算验收通过。§29 起三道业务门禁同时断言「区域只在顶部」「加入在右上角」「媒体下方零按钮」「设置浮层内容始终渲染」；**§30 起新增第六道 `check-rooms.js`，§32 起改写为断言「创建房间仅房间名必填、房间上频道目录、右上角加入、加入后更新通知」，六道全绿方可发布**。

### 25.5 待裴总拍板（视觉口径，不阻塞开发）

① 浅色 `--line` 加深到 `#707c87` 后描边变重，接受合规优先还是偏好轻盈（后者需书面记录为无障碍偏差）；② 深浅两主题按钮的「亮蓝底近黑字 / 深蓝底白字」反转是否接受；③ 简繁切换是否放到首屏可见控件（影响顶部工具栏 44px 排布）。

---

## 26. 全球布局：区域作为频道维度 + 频道数据驱动推荐（2026-11-09 第七轮增补）

> **本章是当前产品边界的最高优先级口径。** 与 §0–§25 冲突之处，以本章为准；§0–§25 中的英国专属内容不删除，全部降级为 `jurisdiction='UK'` 的法域实例与配置记录保留。

### 26.1 结论与定位修订

**采纳。** 产品边界由「英国中文本地生活社区」改为「**全球中文频道社区**」，英国是**首启法域（launch jurisdiction）**，不再是产品边界。

一句话定位修订为：

> **你加入感兴趣的中文频道 —— 包括任意地区的频道 —— 内容由频道与同好整理好，按时送进来。**

三条核心表述：

1. **区域是 `channel` 上的一个数据维度，不是独立站点、独立账号、独立数据库。** 用户「加入英国频道」即完成区域化，与加入「港剧追剧房间」是同一个动作。
2. ~~区域包可叠加，不是单选切换。~~ **（2026-11-11 由 §36 作废）** 当前国家单选；国际频道各国共享，开通国家的分类数据彼此隔离，切换国家不叠加、不串数据。
3. **主页推荐的内容来源于频道数据**，而非逐条内容特征或用户行为画像（详见 §26.4）。

**架构影响：接近于零。** §8 的统一内容池 `content`、§2 的三层频道、§20 的三 Tab、§22 的 `channel.layout`、§23 的 `room_type`、§24 的 embed 状态机全部沿用。本章只新增一个正交维度 `region` / `jurisdiction`。

**明确不做**：不拆多站点、不做多套数据库、不做区域版 App、不做全球统一合规声明、不在业务代码里写 `if country=='UK'`。

### 26.2 三层模型与两个必须补的洞

| 层 | 实体 | 变更 |
|---|---|---|
| 平台 | 一套代码 / 一个内容池 / 一套订阅关系 / 一套审核管道 | 不变 |
| **区域（新增）** | `region` 配置：法域、时区、语言、货币、内容源、审核策略 | 一等数据维度，配置驱动 |
| 频道 | `channel.region_code` + `region_scope` | 仅加字段 |

`channel.region_scope` 三态（服务端枚举校验）：

| 值 | 含义 | 示例 |
|---|---|---|
| `global` | 跨区域主题频道，不带地域 | 港剧追剧房间、国际华人求职、中文影视 |
| `region` | 国家 / 城市级 | 伦敦租房、东京落地、多伦多二手 |
| `local` | 同城 / 附近（沿用 PostGIS） | 同城活动、二手自取、观影局 |

**洞 1 · 新用户首屏为空。** 纯靠主动加入频道做区域化，第一次打开是空页。对策：默认区域包，来源按优先级取 ① 应用商店地区 ② 系统语言/地区 ③ 用户自选；**只存城市级、可改可关、位置类数据单独同意**（UK GDPR Art 6 + PECR；禁止静默 GPS 精确定位）。若用户拒绝，给「国际频道」兜底包而非空白页。

**洞 2 · 跨区域主题不该被绑死到某个国家。** 「港剧追剧房间」如果强制挂 `region=HK` 或 `UK`，会破坏 §22–§23 的房间模型。所以 `region_scope='global'` 必须是一等选项，且全局频道不带区域徽章。

**冷启动最省钱的路径（重要，2026-11-11 由 §36 修订）**：~~全球用户自己建各区域频道（L3 UGC）~~ 未开通国家不开放国家分类数据，用户只能在国际频道下建房间；平台只在开通国家做官方频道（L1/L2）。§21 已确认：平台主动采集/自营账号 = 直接内容提供者，法域责任重；用户自建频道 = 托管服务，责任轻。这条让「全球」在界面上第一天就成立，却不使平台立刻承担 N 个法域的主动内容责任。

### 26.3 合规核实（本轮新增，会改变上线策略）

**最反直觉的一条**：DSA / GDPR 的域外适用靠 **targeting（针对）** 判定，不看公司注册地。Regulation (EU) 2022/2065 Recital 明确：使用某成员国通用语言或货币、在当地应用商店上架、本地广告、当地语言客服，均可构成 targeting；「与该成员国有实质联系」即适用。

> 因此「做英国频道包 + 中文界面 + 英镑标价 + 英国区商店上架」本身就是一组 targeting 信号。**全球平台不因此豁免，反而是每开一个区域包就主动指向一个法域。**

| 法域 | 关键义务 | 与 UK 的关键差异 | 上线前置 |
|---|---|---|---|
| **UK（首启）** | §13 / §22 / §24 全量：OSA 2023 非法内容风险评估、NLA 报业许可、UK GDPR / PECR、CDPA 1988 + hosting defence、TuneIn 英区授权判定 | OSA 2023 的 illegal content 定义**明确排除知识产权侵权** | 已完成评估模板，复用即可 |
| **EU** | DSA Art 16 notice-and-action、Art 20 申诉、ToS 内容审核说明、透明度报告；GDPR；ePrivacy；版权指令 (EU) 2019/790 **Art 17** | **DSA 的 illegal content 明确包含「未授权使用受版权保护材料」**（Recital 12、Eurojust DSA 概况表）。Art 17 对「以营利为目的存储并组织、推广大量用户上传版权作品」的 OCSSP 要求：尽力取得许可、阻止权利人已登记作品、收到有效通知后下架、防止再上传。**「房间排序 + 订阅 + 推荐」恰好往 OCSSP 定义靠，比英国更紧** | EU 代表、DSA 合规评估、Art 17 义务判定；VLOP 门槛 4500 万 EU 月活，早期不适用 |
| **US** | DMCA 17 U.S.C. §512(c) 通知删除 | **有法定程序，比英国「ToS 自定 + 处置审计」更明确**；但硬前置：向 U.S. Copyright Office 注册 designated agent（电子登记每 3 年续期）、合理实施并**真实执行** repeat-infringer 政策且留台账、§512(g) 反通知后 10–14 工作日恢复、不得干扰标准技术措施。Section 230 不覆盖 IP 侵权 | 注册 agent、政策与台账落地 |
| **CA / AU / SG / JP …** | 各自隐私法与内容法 | 逐个评估 | G2 按法域排期 |
| **中国大陆** | 原 A3 假设升级为显式策略 | 全球上架不等于必须面向所有地区提供服务 | 建议商店地区排除 + ToS 声明服务范围 + 不提供人民币结算 / 大陆客服 / 大陆加速；**需单独法律意见，本文不下结论** |

**工程结论**：合规必须做成 `jurisdiction` 一等维度 + 配置驱动开关。`jurisdiction_policy` 表存各法域的通知渠道、下架 SLA、反通知天数、重复侵权政策、embed 同意模式、未成年人年龄；业务代码只读配置，不写国家分支。开新法域 = 一份风险评估 + 一组配置 + 审核语言，不是重构。

**embed 授权矩阵（§24 升级）**：§24 的 TuneIn 结论是「把传播定向到英国、而源站无英国授权即侵权」。全球布局后该判定按法域复制 N 次，白名单从 `embed_provider` 单表升级为 `embed_provider_region`。判定取三者交集：**用户法域 ∩ 频道 `region_scope` ∩ 源站授权地域**，交集为空即降级为「去原站看 / 仅登记」。B 站 / 爱奇艺 / 优酷等大陆限定内容在 UK 频道仍不进白名单，但可能在其授权区域可用——这是**配置，不是硬编码**，也不许为了绕过而代理或转存。

### 26.4 频道数据驱动的推荐（重写 §2.5 与 §20.3）

输入只取三类**频道级聚合数据**，不采集逐条内容行为画像、不建用户画像表：

| 信号 | 来源 | 含义 |
|---|---|---|
| `co_subscription` | `channel_co_subscription` 物化表（每日离线算） | 订阅了 A 的人也订 C 的共现度 |
| `region_activity` | 频道近 7 日新增条目数、活跃频道主数 | 同区域频道的热度 |
| `room_progress` | `collection_item` / `user_progress` 聚合计数 | 房间新增集数、追更打卡数 |

打分公式（可解释，服务端每日按**用户本地 IANA 时区 07:00** 物化）：

```
score = 0.40 * co_subscription
      + 0.30 * region_match      -- 频道 region 与用户已订阅区域集合的交集权重
      + 0.20 * activity_7d
      + 0.10 * editor_pick
```

输出仍是 §20 定的 **10–20 条有限列表**，但条目形态改为「**频道卡 + 频道内代表性条目**」两张一组，而不是无限内容流。每张卡必带 `reason_code` 与可见文案：「同区域 128 人加入了该频道」「你关注的频道本周新增 12 条」「与『伦敦落地必读』订阅共现 0.62」。

约束延续并加强：

- 单集卡、外链卡、embed 卡、分类信息**不进推荐流**（§22.9 / §24.5）。
- 推荐系统对有害内容的放大效应，要在**每个已启用法域**的风险评估里单独记录（UK OSA §20.6 / EU DSA 系统性风险）。
- 只用订阅关系与频道级计数，`user_event` 不参与推荐；UK GDPR 数据最小化成立，DSA 下推荐透明度也好交代。
- 推荐可一键关闭，关闭后「为你推荐」退化为「发现频道目录」，不影响「正在关注」。

### 26.5 DDL 增量（PostgreSQL 16）

```sql
CREATE TYPE region_scope_t AS ENUM ('global','region','local');
CREATE TYPE region_source_t AS ENUM ('store','locale','self','none');

CREATE TABLE region (
  region_code        text PRIMARY KEY,               -- 'UK','UK-LON','JP-TOK','GLOBAL'
  parent_code        text REFERENCES region(region_code),
  jurisdiction       text NOT NULL,                  -- 'UK','EU','US','CA'...
  iana_tz            text NOT NULL,                  -- 'Europe/London'
  currency           char(3) NOT NULL,              -- 无默认值，按区域配置填写
  default_locale     text NOT NULL DEFAULT 'zh-Hant',
  script_options     text[] NOT NULL DEFAULT ARRAY['zh-Hans','zh-Hant'],
  enabled            boolean NOT NULL DEFAULT false,
  launched_at        timestamptz,
  risk_assessment_ref text,                         -- 无评估不得启用
  CONSTRAINT chk_region_launch CHECK (NOT enabled OR risk_assessment_ref IS NOT NULL)
);

CREATE TABLE jurisdiction_policy (
  jurisdiction          text PRIMARY KEY,
  notice_channel        text NOT NULL,              -- 通知删除入口 URL / 邮箱
  takedown_sla_hours    int  NOT NULL DEFAULT 24,
  counter_notice_days   int,                       -- US = 10~14 工作日
  repeat_infringer_policy text NOT NULL,
  dsa_notice_action     boolean NOT NULL DEFAULT false,
  embed_consent_mode    text NOT NULL DEFAULT 'click_to_load',
  minor_age             int  NOT NULL DEFAULT 18,
  tos_version           text NOT NULL,
  privacy_version       text NOT NULL,
  updated_at            timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE channel_pack (
  pack_code      text PRIMARY KEY,
  region_code    text NOT NULL REFERENCES region(region_code),
  name_hans      text NOT NULL,
  name_hant      text NOT NULL,
  channel_codes  text[] NOT NULL,
  enabled        boolean NOT NULL DEFAULT false
);
-- 注意：PostgreSQL 的 CHECK 不允许子查询，「未启用区域不得启用频道包」用下方触发器实现

CREATE TABLE user_region_pref (
  user_id       uuid NOT NULL REFERENCES app_user(id),
  region_code   text NOT NULL REFERENCES region(region_code),
  source        region_source_t NOT NULL DEFAULT 'self',
  consent_id    uuid,                               -- 位置类数据单独同意
  created_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, region_code)
);

CREATE TABLE channel_co_subscription (
  a_code     text NOT NULL REFERENCES channel(code),
  b_code     text NOT NULL REFERENCES channel(code),
  score      numeric(4,3) NOT NULL,
  updated_at date NOT NULL DEFAULT current_date,
  PRIMARY KEY (a_code, b_code),
  CHECK (a_code <> b_code)
);

CREATE TABLE recommend_reason (
  reason_code  text PRIMARY KEY,
  tpl_hans     text NOT NULL,
  tpl_hant     text NOT NULL,
  needs_count  boolean NOT NULL DEFAULT false
);

CREATE TABLE embed_provider_region (
  provider_code text NOT NULL REFERENCES embed_provider(code),
  region_code   text NOT NULL REFERENCES region(region_code),
  allowed       boolean NOT NULL DEFAULT false,
  licence_ref   text,
  checked_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (provider_code, region_code)
);

ALTER TABLE channel
  ADD COLUMN region_code       text REFERENCES region(region_code),
  ADD COLUMN region_scope      region_scope_t NOT NULL DEFAULT 'global',
  ADD COLUMN jurisdiction_code text REFERENCES jurisdiction_policy(jurisdiction),
  ADD CONSTRAINT chk_channel_region CHECK (
    (region_scope = 'global' AND region_code IS NULL)
    OR (region_scope IN ('region','local') AND region_code IS NOT NULL)
  );

ALTER TABLE takedown_request
  ADD COLUMN jurisdiction text NOT NULL DEFAULT 'UK',
  ADD COLUMN region_code  text REFERENCES region(region_code);

ALTER TABLE user_consent_log
  ADD COLUMN jurisdiction text NOT NULL DEFAULT 'UK';

CREATE INDEX idx_channel_region ON channel (region_scope, region_code) WHERE is_active;
CREATE INDEX idx_content_region ON content (published_at DESC)
  WHERE status = 'published' AND deleted_at IS NULL;

-- 跨表约束：CHECK 不能写子查询，改用触发器
CREATE OR REPLACE FUNCTION trg_pack_region_enabled() RETURNS trigger AS $$
BEGIN
  IF NEW.enabled AND NOT EXISTS (
    SELECT 1 FROM region WHERE region_code = NEW.region_code AND enabled
  ) THEN
    RAISE EXCEPTION 'region % is not launched', NEW.region_code;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER pack_region_enabled BEFORE INSERT OR UPDATE ON channel_pack
  FOR EACH ROW EXECUTE FUNCTION trg_pack_region_enabled();

-- 移除 §8 的英国硬编码默认值；采集源按法域登记
ALTER TABLE city   ALTER COLUMN country DROP DEFAULT, ALTER COLUMN timezone DROP DEFAULT;
ALTER TABLE source ADD COLUMN jurisdiction text;
```

**DDL 自洽说明（本轮自查修正，开发按此执行）**：① `app_user` 是用户表真名，§24 的 `user_consent_log` 曾误写 `"user"` 且 `user_id` 用了 `bigint` 与 `uuid` 主键不匹配，已在 §24.7 原地修正；② `channel` 主键是 `id uuid`，`code` 带 UNIQUE，故 `channel_co_subscription` 引用 `channel(code)` 合法；③ `embed_provider` 主键是 `code` 而非 `id`；④ `channel` 无 `deleted_at`，索引条件用 `is_active`；⑤ `content` 同时有 `status` 与 `deleted_at`，两者都要进索引条件；⑥ `city.country` 默认 `'GB'`、`city.timezone` 默认 `'Europe/London'` 已去掉默认值，由 `region` 配置提供；⑦ §24 的 `embed_provider.uk_rights_verified` 保留为 UK 法域实例字段，全球判定统一由 `embed_provider_region` 承担。

`content` 不新增 region 字段——内容继承所属频道的区域，`channel_item` 是唯一关联入口，避免同一内容进多频道时地域歧义。

### 26.6 区域参数化清单（把常量改成配置）

| 项 | 原 UK 常量 | 改为 |
|---|---|---|
| 每日精选时间 | 07:00 BST | 用户 `region.iana_tz` 本地 07:00；全部内部时间戳仍存 UTC |
| 货币 | £ | `listing_ext.currency` + `region.currency`，展示层格式化 |
| 语言 | zh-Hans / zh-Hant | 保留双文案，追加 `region.default_locale` 与日期 / 数字格式 |
| 当地术语 | eVisa / GP / council tax | 每个区域一份术语表，不共用 |
| 内容源 | GOV.UK / ONS / TfL（OGL v3.0） | `source.jurisdiction` + `licence_ref` 逐源登记，各区域开放许可源单独评估 |
| 审核 | 英文 + 中文，UK 违法定义 | 按 `jurisdiction_policy` 切换违法定义、语言与 SLA |
| 频道准入 | §2.2「≤25 个、日更新 ≥3」 | 规则不变，但**按 region 分组生效**；未 `enabled` 的区域其频道在任何入口不可见 |

### 26.7 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/v1/regions` | 仅返回 `enabled=true` 的区域与其法域 |
| GET | `/v1/regions/{code}/packs` | 区域频道包与所含频道 |
| POST | `/me/regions` | ~~叠加订阅区域~~ 设置当前国家（单选，§36）；body 带 `source` 与 `consent_id` |
| DELETE | `/me/regions/{code}` | 移除区域包（不自动退订该区域频道，需二次确认） |
| GET | `/v1/channels?region=&scope=` | 频道目录按区域过滤；`scope=global` 恒可见 |
| GET | `/me/feed?tab=foryou&region=` | 推荐结果带 `reason_code` 与可见理由文案 |
| GET | `/v1/embed/resolve?url=&region=` | 三重授权判定，返回 `inline` / `external` / `blocked` |
| POST | `/v1/admin/jurisdictions/{code}/enable` | 必须带 `risk_assessment_ref`，否则 409 |

错误码：`REGION_NOT_LAUNCHED`(403)、`JURISDICTION_POLICY_MISSING`(409)、`EMBED_REGION_NOT_LICENSED`(403)、`REGION_CONSENT_REQUIRED`(428)、`PACK_CHANNEL_EMPTY`(422)。

### 26.8 界面变更（原型同步）

- 主栏顶部新增 `RegionPicker`：~~显示当前已订阅的区域集合（多选、叠加、带「国际」兜底）~~（§36：改为「当前国家」单选 + 常驻国际频道），文案标明来源与「可随时移除」；不是站点/账号切换器。
- 「添加频道」Tab 顶部新增 `RegionPackCard`：英国频道包 / 东京频道包 / 国际频道，一键加入 N 个频道；未启用区域显示「用户自建频道 · 平台未开设官方频道」。
- 频道行与卡片显示区域徽章（`英国 · 伦敦` / `国际`）；`global` 频道不加地域徽章。
- 「为你推荐」卡片理由改为频道数据口径，保留来源署名、许可徽章、原文回链（§25 合规 UI 组件不变）。
- 右侧合规说明按**用户当前法域**渲染文案，不再写死 `UK GDPR · OSA 2023`；EU 显示 DSA 通知与申诉入口，US 显示 DMCA designated agent 与反通知说明。

### 26.9 分阶段路线（开发是配置，合规是项目）

| 阶段 | 内容 | 增量 |
|---|---|---|
| **G0 · 架构预留（M0）** | `region` / `jurisdiction` 一等维度、§26.5 DDL、配置开关、区域包 UI 骨架；**只 `enabled` UK 一个法域** | ≈ 2–3 天，且不阻塞 §22 的 4 周方案 |
| **G1 · 首法域上线** | UK 官方频道 + 全球用户自建任意区域频道（L3 UGC）、只开 YouTube 官方 provider、推荐走频道图谱 | 沿用 §22 / §24 排期 |
| **G2 · 每新增一个法域** | 一份风险评估、`jurisdiction_policy` 配置、embed 授权矩阵、通知删除通道与 SLA、审核语言、ToS / 隐私政策本地化、商店地区设置 | **2–3 周，主要成本是合规而非开发** |

建议第二法域选 **US 或 CA**（中文社群密度高、DMCA 程序明确）；**EU 因 DSA + Art 17 最重，建议放第三**，且启用前需专门判定本产品是否落入 OCSSP 定义。

### 26.10 验收要点与风险登记

验收：① 未 `enabled` 的 region，其频道在目录 / 搜索 / 推荐 / 首页任何入口均不可见；② 无 `risk_assessment_ref` 的法域启用请求返回 409；③ 用户可同时订阅 UK + JP 两个区域包，首页按订阅集合出内容且互不覆盖；④ 任一推荐理由可追溯到 `channel_co_subscription` / 频道级计数，且查询日志不含 `user_event`；⑤ embed 在非法域自动降级为跳转卡，不允许前端绕过；⑥ 同意记录与下架工单都带 `jurisdiction`；⑦ 用户拒绝位置同意时，首屏是「国际频道」兜底包而非空白页。

| 风险 | 影响 | 对策 |
|---|---|---|
| 「全球」被理解成一次性做完全球合规 | 上线无限期拖延 | G0 只做数据维度，G2 逐法域开 |
| targeting 触发域外适用而未评估 | DSA / GDPR 罚则 | 开区域包前先做该法域评估；默认区域包来源可审计 |
| EU Art 17 OCSSP 判定 | 需许可 / 上传过滤，成本陡增 | 启用 EU 前专项判定；首版房间不托管正片、不进推荐变现 |
| 默认区域包被视为静默定位 | UK GDPR / ePrivacy 同意瑕疵 | 只存城市级、明示来源、单独同意、可关 |
| 多区域内容稀释本地密度 | 「为你推荐」变杂 | `region_match` 权重 0.30，且用户可对区域单独静音 |
| 各法域 ToS 用同一份 | 条款无效、通知渠道不成立 | `jurisdiction_policy.tos_version` 逐法域版本化 |

### 26.11 常见坑

1. 把「全球布局」做成多站点 / 多数据库 / 多套账号体系。
2. 在业务代码里写 `if country == 'UK'` 分支，开第二个法域时全量返工。
3. 静默 GPS 精确定位做默认区域，未取得单独同意。
4. 区域做成单选切换，导致用户无法「人在伦敦同时关心东京」。
5. 把跨区域主题房间硬挂到某个国家，`global` scope 形同虚设。
6. 全球上架却只挂一份 ToS / 隐私政策 / 通知删除邮箱。
7. 推荐理由引用 `user_event` 逐条行为，把频道订阅模型的隐私优势丢掉。
8. embed 白名单只按 provider 不按 region，或为绕过地区限制而代理媒体流（§24 红线）。
9. 用 UTC 或北京时间发「每日 07:00 精选」，BST / JST / EST 全部错位。
10. 以为公司注册在境外即不受 DSA / GDPR 约束。

### 26.12 待裴总拍板

① **首启法域是否仍为 UK**（建议是：§13 / §24 的合规工作可直接复用，迁移成本最低）；② 第二法域顺序（建议 US 或 CA，EU 放第三）；③ **是否首版就允许全球用户自建任意区域频道**（建议是，这是「全球」低成本成立的关键）；④ 中国大陆地区是否明确排除服务范围（建议是，需单独法律意见）。

---

## 27. 媒体布局、默认站内播放与内容优先推荐（2026-11-09 增补 · 新准绳）

> 本章回答裴总第九轮三个问题：①「默认站内播放，和 X app 那样，有图片 / 手机竖视频 / 横视频布局」；②「为你推荐直接推荐频道？直接显示可能对你感兴趣的内容不好吗？感兴趣再加入频道？」；③「新闻、视频等 UI 需要设计」。
> **结论：三件全部采纳，但第①件必须分两层，第②件是产品内核改动，第③件只加一个字段不新增内容类型。**

### 27.1 裁决摘要

| # | 诉求 | 裁决 | 对既有章节的影响 |
|---|---|---|---|
| ① | 默认站内播放 + 图片 / 竖屏 / 横屏布局 | **采纳，但分两层**：平台自有媒体默认静音自动播；第三方 iframe 首次 PECR 同意后默认站内播放 | **修订 §24.5**：第三方 embed 的**静态占位卡**可进推荐流，但 iframe 仍禁止预加载 / 自动播；§24 三条红线不变 |
| ② | 推荐先给内容，感兴趣再加频道 | **采纳，改产品内核**：输出从「频道卡 + 代表条目」改为**内容卡 + 卡片内一键加入来源频道** | **修订 §26.4 的输出形态**；打分公式、区域维度、可解释理由、统一内容池、API 全部沿用 |
| ③ | 新闻 / 图片 / 视频统一 UI | **采纳**：新增 `content.media_layout` 8 态枚举，共用同一张内容卡 | 不新增 `content_type`，不改 `channel` 容器，不改订阅关系与设计 token |

**不推翻的清单**（避免开发误以为要重构）：统一内容池 `content`、频道订阅关系、三 Tab 首页、房间三种形态、区域包叠加、`region_scope`、L1/L2/L3 内容源分级、审核与举报、24h 版权下架、Vue3 + FastAPI + PostgreSQL/PostGIS + 单机 Compose 部署、§26 全部 DDL。

### 27.2 默认站内播放：两层，不能一刀切

这是本轮最容易做错的地方。「贴个链接就在 App 里播」在技术上没有问题，但**法律性质取决于媒体由谁提供**。

| 层 | 内容 | 默认行为 | 依据 |
|---|---|---|---|
| **L1 第一方** | 平台自有图片、用户原创视频（`media_origin='original_user'`，§23 通道） | **默认静音站内播放**：进入可视区即播，可暂停 / 静音 / 关闭自动播 | 客户端播放自有媒体不引入第三方终端存储，PECR Reg 6 不因播放动作本身触发；仍须通过 §23 的版权确认、sha256 去重、病毒扫描与人工审核 |
| **L2 第三方** | 白名单官方 iframe（`youtube-nocookie` 等） | **首次**加载前显示事前同意面板（仅本次 / **总是允许此平台** / 去原站看）；选「总是允许」后**默认站内播放**，同意可随时撤回 | 第三方播放器会取得 IP、设备信息并可能设 cookie；ICO 口径：用户主动选择观看且告知充分时可视为「用户所请求服务所严格必需」，但一般 embed 不符窄豁免，需事前同意（§24.2 已核实，DUAA 2025 cookie 修订与 ICO 最终指南） |

这同时**解掉 §24.12 留的第二个待决问题**：「总是允许此平台」持久偏好必须保留——它正是「默认站内播放」得以成立的钥匙，不是可省的繁琐项。

**四条硬红线**（沿用 §24.5，不因默认播放放宽）：

1. **禁止服务端代理 / 转存 / 缓存媒体流**。一旦服务端拉流转发，性质从超链接变成平台自己 making available + 复制，Svensson 空间与 hosting defence 一并消失。CDN 不缓存第三方媒体，CSP `frame-src` 只列白名单。
2. **禁止推荐流预加载 iframe**。推荐列表只渲染静态占位卡；只有用户点「站内播放」并完成（或已有）同意后才创建 iframe；收起播放器必须**销毁 iframe DOM**，不能只 `display:none`。
3. **禁止带声音自动播 / 非可视区播放 / 省流量或 `prefers-reduced-motion` 下自动播**；`IntersectionObserver` + `visibilitychange` 控制，一次仅允许一个有声媒体。
4. **第三方播放器永无「自动播」开关**：`embed_provider.default_autoplay` 在 DB 层被 CHECK 锁死为 false。

**§29 覆盖**：原计划「`PlaybackPrefBar` 推荐流顶部常驻」已废止，改为顶部 `SettingsPanel` 浮层里的「播放」分组（右上角齿轮一次点击可达），含第一方自动播开关、第三方偏好与冷启动演示入口；**视频下方不出现任何播放 / 静音按钮**，下滑静音自动播、点按画面暂停 / 继续，用户在设置里可全局关闭自动播。四条硬红线与 PECR 同意流程完全不变。

### 27.3 X 式媒体布局矩阵

`content.media_layout` 是内容条目上的一个字段，**不是新内容类型**；所有布局共用同一张卡片、同一套 `SourceBlock`、审核与举报管道。占位色用 `--media-ph-a/b/c`（tokens.css v1.2 已加），禁止硬编码颜色。

| 布局 | 适用 | 桌面 | ≤760px | 自动播 |
|---|---|---|---|---|
| `none` | 新闻摘要、政策要点、纯文字讨论 | 无媒体块 | 同 | — |
| `single` | 单张原创图 / 信息图 | 等比，最大高 510px | 最大高 320px | 静态 |
| `grid2` | 对比图 / 前后图 | 2 列等分，间隙 2px | 同 | 静态 |
| `grid3` | 房源、探店多图 | 左大右两小（`1.35fr / 1fr`，首格 `grid-row:span 2`） | 同 | 静态 |
| `grid4` | 活动相册 | 2×2，间隙 2px | 同 | 静态 |
| `portrait` | **手机竖屏视频 9:16** | 居中限宽 258px、最大高 460px，两侧 `--bg` 留白 | 限宽 230px / 高 390px | 静音自动播 |
| `landscape` | **横屏视频 16:9** | 全宽 16:9 | 全宽 16:9 | 静音自动播 |
| `embed_ph` | 第三方官方视频 | 静态占位卡 + 官方来源徽章 | 同 | **禁止** |

通用规则（**§29 覆盖**）：圆角由外层容器统一裁切（`--r-lg`）；媒体块下方**不再挂 `MediaCreditBar`**，也不放暂停 / 静音按钮——来源、许可与原创声明统一由卡片级 `SourceLine` 一行承载，媒体内部只保留布局角标、视频时长与静音指示图标；图片 `loading="lazy"` + `width/height` 占位防 CLS；视频必须有文字替代，暂停 / 继续靠**点按画面本身**（键盘 Enter / Space 同效），`data-state` 记录播放状态；移动端防横向滚动。

### 27.4 内容优先推荐：先消费，后订阅

裴总这一问是对的，而且比 §26.4 更优：**先推频道是让用户为一个未知的东西做承诺，先推内容是让用户用最低成本判断有没有兴趣**。订阅动作从「入口」变成「转化」，同时解决新用户 0 订阅时首屏空白。

**打分输入完全沿用 §26.4**（不采集 `user_event` 逐条行为画像）：

```
channel_score = 0.40 * co_subscription
             + 0.30 * region_match
             + 0.20 * activity_7d
             + 0.10 * editor_pick

item_score    = channel_score * item_freshness
final_score   = item_score - 0.12 * I(already_subscribed)   -- 已订阅降权，避免与「正在关注」重复
```

**输出形态改了，公式没改**：从每个候选频道取 1–2 条代表内容，渲染成**内容卡**（含新闻 / 图片 / 竖视频 / 横视频 / embed 静态占位），按 `final_score` 降序，每日 07:00 按用户本地时区更新，10–20 条封顶，仍是有限列表不是无限滚动。

每张推荐内容卡必须带：

- `RecommendReason`：可见理由 + `reason_code`（沿用 §26.4）；
- **`CardJoinButton`（§29 取代 `FromChannelRow`）**：固定在卡片头部**右上角**；未订阅「＋ 加入」、已订阅「✓ 已加入」，`aria-label` 写明频道名；点击即时订阅 / 退订并写 `recommend_impression.joined_channel=true`，该频道内容降权 0.12。频道名已在头部，不再有「来自频道 X」独立行，也不在卡内重复区域徽章；
- `SourceBlock` + 许可徽章 + 原文回链 + 举报入口（§7 / MASTER §15 一等组件，不许省略）。

**频道推荐卡降级**：从推荐流首屏移到列表尾部「看完还想持续关注？」与「添加频道」页，仍由频道图谱生成，但不再是首屏主形态。

**不进推荐池**（§22.9 / §24.5 保留）：分类信息 `listing`、房间**单集卡**、外链按语、以及任何第三方 iframe 本体（只允许静态占位卡进）。房间「本周新增 3 集」这类**房间级更新卡**可以进。

**DSA Art 27（已核实）**：所有使用推荐系统的 online platform 都须在 ToS 用通俗语言写明主要参数**及其相对重要性**；若提供多种选项，切换功能必须「从推荐界面直接可达」。我们的 `0.40/0.30/0.20/0.10` 写在 ToS 全文、顶部 `SettingsPanel`「推荐与透明度」分组（§29，从推荐界面一次点击可达）与合规角标三处，正好满足披露；**「正在关注」时间序 Tab 就是天然的非画像选项**（Art 38 的非画像强制仅适用于 VLOP，我们不属 VLOP，但该能力已在，属合规红利而非负担）。

### 27.5 合规增量（不能只写产品）

1. **PECR / UK GDPR**：第三方同意写入既有 `user_consent_log`，`scope='always'` 后默认站内播放，`withdrawn` 立即回退为每次询问；偏好表只存播放开关与 provider 级状态，不存观看记录。不因默认播放而新增行为画像。
2. **OSA 2023**：§20.6 曾写「若加回为你推荐，须补推荐系统对有害内容的放大评估」——**这条现在正式生效**。非法内容风险评估（第 9 条）新增章节：推荐流是否放大诈骗 / 违法分类信息、置顶与推送的评估、以及推荐池的拦截措施（listing 禁入、审核状态必须为 `approved`、举报数阈值降权）。
3. **EU DSA**：除 Art 27 披露外，因 Art 17 / Recital 12 的 illegal content 定义包含未授权使用版权材料（§26.3 已核实），启用 EU 法域前须评估「第三方版权内容被推荐放大」的风险；因此 embed 静态占位卡进推荐**必须**限定为白名单官方源 + 该地区已核验授权 + 不预加载 iframe。
4. **版权**：第一方原创视频仍走 §23 全链路（`rights_confirmed`、sha256 去重、≤60s/100MB、人工审核）；第三方仍走 §24 白名单、规范化 `media_id`、短链/`.m3u8` 直链拒绝、TuneIn 地区授权核验。**默认播放不改变任何一条版权约束**。
5. **§24.5 精确修订**：原文「embed 卡不进为你推荐」改为「**embed 静态占位卡可进推荐流，iframe 不得在推荐流预加载或自动播放**」。其余（不置顶、不推送、不代理、不缓存、24h 下架）不变。

### 27.6 DDL 增量（PostgreSQL 16，可直接执行）

```sql
-- 27.6.1 媒体布局枚举与 content 增量
CREATE TYPE media_layout AS ENUM
  ('none','single','grid2','grid3','grid4','portrait','landscape','embed_ph');

ALTER TABLE content
  ADD COLUMN media_layout       media_layout NOT NULL DEFAULT 'none',
  ADD COLUMN autoplay_allowed   boolean NOT NULL DEFAULT false,
  ADD COLUMN recommend_eligible boolean NOT NULL DEFAULT true,
  ADD COLUMN media_alt          text;

-- 只允许竖/横第一方视频自动播；embed 占位不得落媒体文件或封面
ALTER TABLE content ADD CONSTRAINT chk_autoplay_layout CHECK (
  NOT autoplay_allowed OR media_layout IN ('portrait','landscape')
);
ALTER TABLE content ADD CONSTRAINT chk_embed_ph_no_media CHECK (
  media_layout <> 'embed_ph' OR (media = '[]'::jsonb AND cover_key IS NULL)
);
ALTER TABLE content ADD CONSTRAINT chk_listing_no_rec CHECK (
  type <> 'listing' OR NOT recommend_eligible
);
ALTER TABLE content ADD CONSTRAINT chk_video_alt CHECK (
  media_layout NOT IN ('portrait','landscape') OR media_alt IS NOT NULL
);
CREATE INDEX idx_content_rec ON content (published_at DESC)
  WHERE status='published' AND recommend_eligible AND deleted_at IS NULL;

-- 27.6.2 播放偏好（第三方同意明细仍只在 user_consent_log）
CREATE TABLE user_playback_pref (
  user_id              uuid PRIMARY KEY REFERENCES app_user(id) ON DELETE CASCADE,
  first_party_autoplay boolean NOT NULL DEFAULT true,
  autoplay_muted       boolean NOT NULL DEFAULT true,
  wifi_only            boolean NOT NULL DEFAULT true,
  third_party_default  text NOT NULL DEFAULT 'ask'
    CHECK (third_party_default IN ('ask','always','external')),
  updated_at           timestamptz NOT NULL DEFAULT now()
);

-- 27.6.3 第三方播放器永不自动播（代码层堵死）
ALTER TABLE embed_provider
  ADD COLUMN default_autoplay boolean NOT NULL DEFAULT false;
ALTER TABLE embed_provider
  ADD CONSTRAINT chk_provider_no_autoplay CHECK (NOT default_autoplay);

-- 27.6.4 静态封面，供省流量 / reduced-motion / 离开视口降级
ALTER TABLE media_asset ADD COLUMN poster_key text;

-- 27.6.5 推荐曝光与「先消费后订阅」转化（频道级，不建逐条画像）
CREATE TABLE recommend_impression (
  id              bigserial PRIMARY KEY,
  user_id         uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  content_id      uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  channel_id      uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  reason_code     text NOT NULL,
  score           numeric(5,3) NOT NULL,
  surface         text NOT NULL CHECK (surface IN ('foryou','daily_digest')),
  joined_channel  boolean NOT NULL DEFAULT false,
  created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_rec_imp_user ON recommend_impression (user_id, created_at DESC);
CREATE INDEX idx_rec_imp_conv ON recommend_impression (channel_id, joined_channel, created_at DESC);
```

`recommend_impression` 只用于**去重、频控、转化统计与 A/B**，明令禁止作为个性化画像输入；30 天滚动删除，纳入 UK GDPR 导出 / 删除流程。`user_consent_log` 仍是同意事实的唯一来源，`user_playback_pref` 只是可重建的读取缓存。

### 27.7 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/me/feed?tab=foryou&script=zh-Hant` | 返回内容卡数组；每项含 `media_layout`、`recommend_reason{code,text}`、`from_channel{code,name,joined}`、`source_block`；**不返回 iframe 地址** |
| GET | `/me/feed?tab=following` | 时间序不变；第一方视频返回 `autoplay_allowed` + 封面，第三方返回 `embed_ph` 占位 |
| POST | `/me/channels/{code}/subscribe` | 由推荐卡 `FromChannelRow` 调用；成功后写 `recommend_impression.joined_channel=true`，并在下一次 feed 计算中对该频道降权 0.12 |
| GET/PUT | `/me/playback-pref` | 读写第一方自动播、静音、Wi-Fi、第三方默认策略 |
| POST | `/embeds/{content_id}/consent` | `scope=once\|always\|withdrawn`；写 `user_consent_log`；`always` 同步 `user_playback_pref.third_party_default` |
| GET | `/embeds/{content_id}/play-url` | 仅在同意有效时返回白名单 iframe URL；否则 403 `CONSENT_REQUIRED`；地区未授权 451 `REGION_NOT_LICENSED`；源站禁嵌入 409 `FRAMING_DISABLED` |

错误码沿用 §24.7；新增 `AUTOPLAY_DISABLED_BY_PREF`（客户端按偏好直接不请求，服务端不报错）。

### 27.8 埋点与指标

只看聚合，不建画像：推荐卡曝光→加入频道转化率（核心指标）、按 `reason_code` 的转化对比、第三方同意 `always` 占比与撤回率、第一方自动播关闭率、推荐流内 iframe 创建次数（**必须为 0**，作为合规断言）、冷启动 0 订阅用户首屏非空率与次日留存。所有指标按 `channel_id` / `region_code` 聚合，禁止落到个人行为序列。

### 27.9 排期增量

相对 §26 的 G1（4 周）净增 **4–6 天**：`media_layout` 枚举与 DDL 1d、8 种布局渲染 2d、`PlaybackPrefBar` + 同意持久化与 iframe 状态机 1–2d、`FromChannelRow` 与推荐输出改写 1d、门禁与合规文案 1d。**成本反而下降**：第一方视频不落第三方带宽，embed 仍不落文件；新增的只是链接审核与同意日志，可与 24h 版权处置同一人兼任。首版建议顺序：`none/single/grid*` → `portrait/landscape` → `embed_ph`，白名单仍只开 `youtube-nocookie` 一个 provider。

### 27.10 验收点

1. 0 订阅新用户首屏有 ≥10 条内容卡，每条都能一键加入来源频道；加入后卡片变「已加入」且排序下降。
2. 8 种 `media_layout` 均可渲染，420px 移动视图无横向滚动；`portrait` / `landscape` 默认静音自动播且可暂停 / 静音。
3. 滚动推荐列表期间 DOM 中**没有**任何第三方 iframe；收起播放器后 iframe 节点被销毁。
4. 首次点第三方「站内播放」出现同意面板；选「总是允许」后第二次点击直接播放；撤回后恢复询问。
5. `listing`、房间单集、外链按语不出现在推荐流；无 `media_alt` 的视频发布请求被 400 拒绝；`default_autoplay=true` 的 provider 配置被 DB CHECK 拒绝。
6. OSA 风险评估文档含「推荐放大」章节；ToS 与推荐界面含 Art 27 参数说明及时间序切换入口。
7. 三道既有门禁 + `check-media.js` 全绿，且 `check-ui.js` 无 WARN（§11 图标迁移已收尾）。

### 27.11 常见坑

1. 把「默认站内播放」做成一刀切，让第三方 iframe 在推荐流自动加载——一次越界就把 §24 的 PECR 与托管抗辩一起赔进去。
2. 为做竖视频新增 `content_type='short_video'`，导致内容池、审核、推荐、搜索四套管道分叉；正确做法是只加 `media_layout` 字段。
3. 推荐流先推频道卡，新用户面对一堆陌生频道名没有判断依据，首屏转化率接近 0。
4. 已订阅频道内容不降权，推荐流与「正在关注」大量重复，用户以为算法在刷屏。
5. 服务器为了「播得顺」代理或缓存第三方媒体流，性质从链接变成自己传播。
6. 同意面板只留「同意 / 拒绝」，没有「总是允许」——「默认站内播放」就永远无法实现，且撤回路径缺失。
7. `prefers-reduced-motion` / 省流量 / 非 Wi-Fi 下仍自动播，无障碍与流量投诉齐飞。
8. 为了填满推荐流放宽来源，把分类信息、房间单集、大陆限定平台链接放进来。
9. 只写 ToS 不写在推荐界面，DSA Art 27(3) 的「直接可达」不达标。
10. 把 `recommend_impression` 拿去训练画像，丢掉频道订阅模型最大的 UK GDPR 优势。

### 27.12 待裴总拍板

① **首版是否三种媒体形态齐开**（建议：图片 + 竖 / 横第一方视频齐开，`embed_ph` 只保留 1 个 provider 跑通）；② 是否接受「第三方首次同意后默认站内播放」作为默认策略（建议是，这是本轮诉求成立的前提；若否，则回退为每次询问，体感会退化成旧版）；③ 推荐流内是否允许 embed 静态占位卡（建议允许，但必须接受「不预加载 iframe」这条硬约束）；④ DSA Art 27 参数说明是否直接放在推荐流顶部（建议是，原型已这么做）。

---

## 28. 自动定位与区域 / 频道开通权限（2026-11-09 第九轮增补）

> **本章裁决两个问题：App 如何自动定位到所在国家；区域由官方创建时，频道究竟由谁开通。** 与 §26 冲突处以本章为准（§26 的「默认区域包」只写了来源优先级，未区分信号用途，也未定义创建权限）。§26 的 `region` / `jurisdiction_policy` / `channel_pack` DDL 全部沿用，本章只做增量。

### 28.1 结论（两句话）

1. **采纳自动定位，但定位的是「国家级大区域」，且只决定默认展示哪个频道包 —— 绝不触发任何法域的官方频道启用。** 技术上用 CDN 边缘 IP 粗粒度推断即可，**不申请设备 GPS 权限、不弹权限框、不存 IP 原文与经纬度**，首次进入用一条可确认 / 更改 / 关闭的轻提示条告知来源与精度，用户确认后锁定、不再自动覆盖。
2. **区域是官方的合规开关，频道是用户的表达空间；定位只决定先给用户看哪个包，不决定哪个法域被启用。** `region`、`channel_pack`（官方包）、L1/L2 官方频道**只能由平台创建**（开一个法域 = 一份风险评估 + 通知渠道 + 下架 SLA + 申诉入口 + 当地语言）；**L3 用户自建频道 / 房间由用户创建，且允许存在于官方尚未开通的区域**。用户「加入区域包」不是开通动作，只是订阅关系。

§26.2 定的冷启动路径因此成立且不失控：全球用户自己把各区域频道建起来（托管责任轻），平台只在首启法域做官方频道（直接内容提供者责任重）。**「全球」是界面上第一天就成立的，不是靠平台在 N 个法域同时开官方频道换来的。**

### 28.2 定位信号：两个用途必须分离

| 用途 | 判定链 | 说明 |
|---|---|---|
| **内容区域**（我现在在哪 → 默认展示哪个包） | ① 已保存的明确选择（`user_region_pref.locked=true`）→ ② **CDN 边缘 IP → ISO 国家码** → ③ 系统语言 / 时区 / `Accept-Language` → ④ 用户自选 → ⑤ `GLOBAL` 兜底 | 用户确认或手动改过后 `locked=true`，**漫游、VPN、换网络都不再自动覆盖**；可手动切换当前国家（§36 单选，不叠加） |
| **法域参考**（我受谁约束 / 账号国 / 上架地区） | 商店地区（Apple ID / Play 账号国）、账号国、上架地区、用户声明 | **不能当「我在哪」**；法域判定由 `jurisdiction_policy` 驱动，见 §26.3 |

**纠正 §26.2 的一处隐含假设**：原文把「应用商店地区」列为默认区域包的第一来源，但商店地区（Apple `storefront` / Google Play country）跟**账号国**走，不跟设备语言、地区设置、GPS 或 IP 走；移民用户换国家后账号国往往长期不变。所以它只能作**法域弱信号**，不能作当前所在地。本轮把「CDN 边缘 IP 国家级推断」提为内容区域的主信号。

**四态回退**：

| 情况 | 行为 |
|---|---|
| 定位到已启用法域（如 UK） | 显示「确认，用这个区域」，可一键加入该区域的官方区域包 |
| 定位到**未启用法域**（如 JP） | **不开官方包**；只显示该区域的用户自建频道 + 国际频道，标「官方未开通 · 仅用户自建频道」，给「申请开通（仅登记需求）」 |
| 定位到明确排除服务范围的国家 | `GLOBAL` 兜底包 + 合规提示，不推断、不存该区域偏好 |
| 定位失败 / 用户拒绝 / 关闭定位 | `GLOBAL` 兜底包，**绝不空白页**（§26.2 洞 1） |

~~区域可叠加的定位语义：自动定位只给一个起点，不锁死；用户随时在「添加频道」里加东京、多伦多，移除区域包也不退订频道（§26.8 已实现）。~~（2026-11-11 由 §36 覆盖：定位只决定当前国家，单选；切换国家只暂停显示其他国家数据，不退订。）

### 28.3 合规核实（本轮两条，都会改变实现）

**① 粗粒度 IP 定位与设备 GPS 是两件事。**

- ICO《storage and access technologies 指南》明确把 **「Coarse geolocation information of website users (eg at city or region level) that does not allow people to be identified」列为可落入统计目的例外、无需 PECR 同意** 的情形；同时明确「基于 IP 地址对个人访客做追踪 / 画像」不在例外内、需要同意。
- PECR Reg 6 管的是「在终端设备上存储 / 访问信息」。**服务端从 CDN 边缘国家头推断大区域不读写用户设备**，不触发设备访问；但 IP 本身仍是 UK GDPR Art 4(1) 个人数据（Breyer 口径），必须落在 Art 6 合法利益 + 透明告知 + 数据最小化 + Art 21 反对权之下，且做 LIA 记录。**用 `navigator.geolocation` / 精确 GPS 则性质完全不同**：需单独同意 + 系统权限弹窗 + DPIA，本产品不用。
- 因此工程约束：CDN 只把 **`CF-IPCountry` 之类两位国家码**传给后端；**不落 IP 原文、不落经纬度、不落到城市以下精度**；日志只存 `region_code` + `signal` + 国家码，且约束其字符串形状以杜绝误写 IP（见 §28.5 的 `chk_signal_detail_shape`）。

**② 商店地区是账号国，不是当前所在地。** Apple StoreKit 的 storefront 由 Apple ID 的国家设置决定，捆绑货币 / 价格档 / 税务 / 上架可用性；设备 locale 与 storefront 相互独立，IP 与 GPS 都不改变 storefront。Google Play 同理（Play 国家与付款方式绑定）。所以：
- 商店地区可用于「在哪上架、按哪套法域文案渲染、货币」，**不可**用于「默认给我哪个城市频道包」；
- VPN 只改 IP 不改账号国，这正好是「定位结果必须可确认、可手动改」的产品理由，而不是靠多源交叉去猜得更准。

> 结论：本轮实现**零新增权限弹窗、零新增同意弹窗**，只新增一条透明的定位确认条与设置项；UK GDPR 侧的义务是告知、最小化、可反对、可撤回。

### 28.4 开通权限矩阵（本章核心）

| 对象 | 谁能创建 | 前置条件 | 责任性质 |
|---|---|---|---|
| `region` 国家 / 城市区域 | **仅平台**（后台配置） | `risk_assessment_ref` 非空、`jurisdiction_policy` 已配置；`chk_region_launch` 约束（§26.5） | 开一个法域 = 一个合规项目 |
| `channel_pack` 官方区域包 | **仅平台** | `region.enabled=true`，由 `trg_pack_region_enabled` 触发器保证（§26.5） | 平台策展，直接内容提供者 |
| L1 官方自动 / L2 官方精选频道 | **仅平台「开通」**（随法域启用批量开设，非用户申请即开） | 所属 `region.enabled=true`；DDL 触发器见 §28.5 | 平台直接内容提供者（§21），责任最重 |
| **L3 用户自建频道 / 房间（小圈子）** | **用户** | 手机验证、风控、审核队列；**不要求区域已启用**；§30.2 规定一律称「房间」、不得用认证徽章 | 托管服务，责任较轻 |
| 用户订阅 / 移除区域包 | 用户 | 无 | 订阅关系，不是开通 |
| 「申请开通」 | 用户 | 无 | **需求信号，不是开通动作** |

**四条硬边界（缺一条就会把平台拖进未评估法域）**：

1. 用户自建频道**不得使用官方认证徽章**、不得命名为「XX 官方 / 官方认证」；`channel.kind='user_created'` 由服务端强制，前端只展示 `ChannelOwnerBadge`（§28.7）。
2. 用户自建频道**不自动进入官方区域包**（`channel_pack.channel_codes` 由运营维护），也**不占据「为你推荐」高权重位**——避免被认定为「以营利为目的组织、推广大量用户上传作品」而落入 EU DSA / 版权指令 Art 17 的 OCSSP 义务（§26.3）。
3. 未启用法域内，官方频道在任何入口（目录、推荐、搜索、Trends）**一律不可见**；用户自建频道可见但必须标注「用户自建 · 平台未设官方频道」（§14.1 已定），且**仍走同一套审核、举报、24h 下架**，不因「未开通」而免审。
4. **自动定位不得写入 `region.enabled`**，不得调用任何启用接口；业务代码禁止 `if country=='UK'`，一律读配置（§26.6）。这是 §28.1 第一句在代码层的落地。

### 28.5 DDL 增量（PostgreSQL 16，可执行）

```sql
-- 迁移 1：新增定位信号枚举值。必须作为独立事务提交后才能写入新值
-- （PostgreSQL 不允许 ADD VALUE 与使用该值出现在同一事务），部署脚本需分两步执行。
ALTER TYPE region_source_t ADD VALUE IF NOT EXISTS 'ip_edge';

-- 迁移 2：定位解析台账（不存 IP 原文 / 经纬度）
CREATE TABLE region_resolution_log (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES app_user(id),   -- 未登录为 NULL
  session_key     text,                           -- 匿名会话哈希，非 IP
  resolved_region text REFERENCES region(region_code),
  signal          region_source_t NOT NULL,       -- ip_edge / store / locale / self / none
  signal_detail   text,                           -- 'edge_country=GB' 等国家码
  confidence      text NOT NULL DEFAULT 'low',
  applied         boolean NOT NULL DEFAULT false, -- 是否真的写入默认区域
  reason_code     text,                           -- user_locked / region_not_enabled / excluded / refused ...
  consent_id      uuid,
  created_at      timestamptz NOT NULL DEFAULT now(),
  -- 只允许字母数字与 _=:- ，彻底排除 IPv4 / 域名 / 坐标被误写进来
  CONSTRAINT chk_signal_detail_shape CHECK (
    signal_detail IS NULL OR signal_detail ~ '^[A-Za-z0-9_=:-]+$'
  )
);
CREATE INDEX idx_region_resolution_user ON region_resolution_log (user_id, created_at DESC);

-- 迁移 3：用户区域偏好补锁定与关闭态
ALTER TABLE user_region_pref
  ADD COLUMN locked         boolean NOT NULL DEFAULT false,  -- 用户确认 / 手动改过 → 不再自动覆盖
  ADD COLUMN disabled       boolean NOT NULL DEFAULT false,  -- 关闭定位 → 仅 GLOBAL 兜底
  ADD COLUMN signal_detail  text,
  ADD COLUMN updated_at     timestamptz NOT NULL DEFAULT now();

-- 迁移 4：开通需求登记（只统计，不启用任何东西）
CREATE TABLE region_launch_request (
  region_code text NOT NULL REFERENCES region(region_code),
  user_id     uuid NOT NULL REFERENCES app_user(id),
  created_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (region_code, user_id)
);
-- CHECK 不能写子查询，用触发器拦「已启用法域还来申请」
CREATE OR REPLACE FUNCTION trg_launch_request_unlaunched() RETURNS trigger AS $$
BEGIN
  IF EXISTS (SELECT 1 FROM region WHERE region_code = NEW.region_code AND enabled) THEN
    RAISE EXCEPTION 'region % already launched; request is meaningless', NEW.region_code;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER launch_request_unlaunched BEFORE INSERT ON region_launch_request
  FOR EACH ROW EXECUTE FUNCTION trg_launch_request_unlaunched();

-- 迁移 5：从数据库层堵死「未启用法域出现官方频道」
CREATE OR REPLACE FUNCTION trg_official_channel_requires_launch() RETURNS trigger AS $$
BEGIN
  IF NEW.kind IN ('official_auto','official_curated') THEN
    IF NEW.region_scope = 'global' THEN
      RETURN NEW;   -- 国际主题频道不带地域，不适用区域启用约束
    END IF;
    IF NOT EXISTS (
      SELECT 1 FROM region WHERE region_code = NEW.region_code AND enabled
    ) THEN
      RAISE EXCEPTION 'official channel requires an enabled region: %', NEW.region_code;
    END IF;
  END IF;
  RETURN NEW;
END; $$ LANGUAGE plpgsql;
CREATE TRIGGER official_channel_requires_launch
  BEFORE INSERT OR UPDATE OF kind, region_code, region_scope ON channel
  FOR EACH ROW EXECUTE FUNCTION trg_official_channel_requires_launch();
```

**DDL 自洽说明**：`channel` 在 §26.5 已加 `region_code` / `region_scope` / `jurisdiction_code`，触发器可直接引用；`region.enabled` 与 `risk_assessment_ref` 见 §26.5；`app_user` 主键是 `uuid`；触发器名与 §26.5 的 `pack_region_enabled` 不冲突；`region_launch_request` 的 PRIMARY KEY 天然实现「一人一区域一次」，无需额外去重逻辑。

### 28.6 API 增量

| 方法 | 路径 | 说明 | 关键错误码 |
|---|---|---|---|
| `GET` | `/v1/me/location` | 返回 `{region_code, source, precision:'country', locked, disabled, jurisdiction, can_change, can_disable, source_label}` | `401` |
| `POST` | `/v1/me/location/resolve` | 内部调用：入参仅国家码 + signal，服务端写 `region_resolution_log`，返回默认区域与四态回退结论 | `422 LOCATION_SIGNAL_INVALID` |
| `POST` | `/v1/me/location/confirm` | `{region_code}`，写 `user_region_pref` 并置 `locked=true`；不触碰 `region.enabled` | `404 REGION_NOT_FOUND` / `409 REGION_NOT_LAUNCHED_OK_UGC_ONLY` |
| `DELETE` | `/v1/me/location` | `disabled=true`，返回 `GLOBAL` 兜底包 | `200`，幂等 |
| `GET` | `/v1/regions` | 区域列表含 `enabled` / `official_channel_count` / `user_channel_count` / `pack_code` / `launch_request_count` / `governance`（三态） | — |
| `POST` | `/v1/regions/{code}/launch-requests` | 需求登记，返回 `{count}`；文案强制「仅登记需求，不代表已上线」 | `409 ALREADY_LAUNCHED` / `429` 限频 |
| `POST` | `/v1/channels` | `kind=official_*` 时服务端校验区域已启用 | `403 OFFICIAL_CHANNEL_FORBIDDEN` |
| `GET` | `/v1/regions/{code}/channels` | 未启用法域只返回 `kind='user_created'` 频道，且强制带 `owner_badge='user_created'` | `206`（附 `notice`） |

**服务端铁律**：`/v1/me/location/*` 与 `/v1/regions/*` 的写路径只有 `region_resolution_log`、`user_region_pref`、`region_launch_request` 三张表，**任何请求都不得 UPDATE `region.enabled` / `channel_pack.enabled`**。启用法域是运营后台带审计的独立流程（§26.9 G2），不暴露在用户 API。

### 28.7 界面变更（原型 v6，设计规范 §16 + §17）

`prototype-x-style.html` v6 新增 5 个组件：`LocationConfirmBar`（首次两行横幅 / 已确认细条 / 已关闭细条三态）、`RegionGovernanceBadge`（三态）、`RegionLaunchCard`（开通状态 + 频道构成 + 需求登记）、`ChannelOwnerBadge`（平台开设 / 用户创建）、`RegionSourceNote`（来源与精度说明）。**不新增颜色 token**，全部复用 §4 变量。

能直接点的动作：顶部「确认 / 手动改 / 关闭定位」，以及右上角齿轮浮层里的「更改区域 / 关闭定位 / 重新开启 / 重放首次进入」与演示按钮「模拟定位到未开法域（日本）/ 定位回英国」；「添加频道」页每张区域状态卡的「申请开通（仅登记需求）」。区域 chip 上带短徽章「官方已开通 / 仅用户自建」。

**§29 的后续改动**：v5 的定位条是常驻细条 + 演示按钮堆在首屏，v6 改为「首次横幅 → 确认后收成一行细条，详细开关与演示按钮收进 `SettingsPanel`」；区域栏压成一行；卡片内区域徽章移到顶部；加入频道移到右上角，视频下方取消播放 / 静音按钮。**权限矩阵、定位状态机、法域启用触发器、打分公式与内容优先推荐全部未改**——§29 只动渲染层，验证了 §26 的分层设计。

### 28.8 状态机与埋点

`prompt → confirmed（locked=true，不再自动覆盖）→ off（GLOBAL 兜底）→ on → replay`；另有 `sim-jp / sim-uk` 仅用于原型演示法域回退。

埋点只记**频道级与配置级**事件：`location_resolved`（signal / region / applied / reason_code）、`location_confirmed`、`location_changed`、`location_disabled`、`region_launch_requested`。**禁止**把定位结果写进 `recommend_impression` 或 `user_event` 画像字段（§27 的 UK GDPR 优势不能丢）；区域偏好只用于「默认展示哪个包」，不参与 §26.4 的打分权重。

### 28.9 路线与成本

| 阶段 | 内容 | 增量 |
|---|---|---|
| **G0（2–3 天）** | CDN 边缘国家头 → 后端解析 → 定位确认条 → `user_region_pref` 锁定 / 关闭 → `GLOBAL` 兜底 | 无新增合规项目，**零带宽 / 零权限弹窗成本** |
| **G1（与首法域上线合并，1–2 天）** | 开通权限矩阵落地：三态徽章、频道归属徽章、区域状态卡、官方频道触发器 | 主要是前端与 DDL |
| **G2（可选，1 天）** | 「申请开通」需求登记 + 计数，作为下一法域排序输入 | 纯配置 |
| **每新增一个法域** | 沿用 §26.9：2–3 周，成本全在合规（风险评估、通知渠道、SLA、申诉入口），**不在定位与开发** |

### 28.10 验收要点

1. 首次进入不弹系统权限框、不空白页，定位条明示来源与「仅国家 / 城市级」。
2. 数据库里查不到任何 IP 原文、经纬度；`region_resolution_log.signal_detail` 只含国家码。
3. 确认后换网络 / 漫游 / 重进，默认区域不变（`locked=true`）；关闭定位后只剩国际频道且可重新开启。
4. 定位到未启用法域时**一条官方频道都不可见**，每条用户频道都有「用户创建」徽章，合规角标按法域回退。
5. 「申请开通」只增加计数，不产生官方频道、不改 `region.enabled`；已启用法域的申请返回 `409`。
6. 用 API 直接 POST 一个 `kind='official_curated'` 到未启用法域 → 被触发器拒绝（`403/DB exception`）。
7. 移除区域包不退订频道；定位条换简繁 / 深浅主题后徽章文案与对比度不退化。
8. 六道门禁全绿（§25.4 / §30.10）。

### 28.11 常见坑

1. 把「应用商店地区」当当前所在地 —— 它跟账号国走，移民用户会长期错配。
2. 为了「更准」去申请 `navigator.geolocation` / GPS 权限 —— 一举把 PECR 例外、DPIA、权限弹窗全引回来，而产品只需要国家码。
3. 把 IP 原文写进访问日志或 `signal_detail` —— 个人数据扩散，且违反 §28.3 的约束意图。
4. 定位成功就自动把 `region.enabled` 置 true —— **本章最致命的一条**，等于让用户用 VPN 替平台开法域。
5. 让「申请开通」看起来像投票即上线 —— 用户会认为平台承诺了未评估法域的官方内容。
6. 用户自建频道带官方认证徽章，或自动进官方区域包 —— 误导用户以为平台已在该法域提供内容服务，也可能触发 OCSSP 义务。
7. 每次启动都重新定位并覆盖用户手动选择 —— 漫游 / 出差用户区域天天跳，确认条形同虚设。
8. 未启用法域的用户频道跳过审核 —— 托管责任仍在，OSA / DSA 下举报与 24h 下架一样适用。
9. 定位失败给空白页 —— §26.2 洞 1 白补，`GLOBAL` 兜底必须存在。
10. 在业务代码里写 `if country=='UK'` 判断能否显示官方频道 —— 应用 `region.enabled` + `jurisdiction_policy`，否则每加一个法域都要改代码。

### 28.12 待裴总拍板

① ~~定位确认条用常驻细条，还是首次横幅、确认后收进设置~~ **已由第十轮反馈拍板（§29）**：选「首次两行横幅、确认后收成顶部一行细条，详情与开关收进右上角设置浮层」。来源与精度在首次条 + 设置面板两处可见，§28.3 / MASTER §16.6 的透明性要求不丢失；② **未启用法域是否保留「申请开通」入口**（建议保留，作为下一法域排序数据；若担心被误读为上线承诺，可只显示人数）；③ **商店地区是否纳入合规角标的法域输入**（建议只作弱信号，需法务确认与账号国、上架地区的优先级）；④ 前几轮仍悬而未决的四项：首启法域是否仍 UK、第二法域顺序（建议 US/CA，EU 第三）、是否首版允许全球用户自建任意区域频道（**建议是，本章治理模型的前提**）、中国大陆是否明确排除服务范围（建议是，需单独法律意见）。

---

## 29. 首屏精简与 X 式帖子卡（2026-11-09 第十轮反馈 · UI 新准绳）

> 本章是**渲染层与信息架构**准绳，回答裴总四个连问：①「区域 / 定位应该放在上面，不要贴在帖子内容上面」；②「加入频道应该放在帖子右上角，让画面简单整洁」；③「视频下面不需要按钮播放还是静音，一般下滑自动就播放了，不喜欢自己会暂停」；④「帖子区域就像 X 平台那种布局」。
> 配套 `design-system/MASTER.md` §17（v1.4 建立，v1.5 §18 扩展）、`pages/home-feed.md`、`prototype-x-style.html` v6（v7 增补顶部搜索与 @/#）、展示页第 12 节（v1.5 补第 13 节）。**§0–§28 的业务规则全部沿用**：8 种媒体布局、两层默认播放、内容优先推荐与打分公式、PECR 同意、DSA Art 27、区域 / 法域权限矩阵、24h 下架，一条不减；本章只改控件的位置与形态。

### 29.1 三条硬裁决

| 反馈 | 裁决 | 废止的旧口径 |
|---|---|---|
| 区域 / 定位放上面 | 区域 chips、开通状态、定位来源、播放偏好、推荐参数**全部集中到顶部吸顶层**（区域栏一行 + 首次确认条 + 齿轮设置浮层）；帖子卡内**不得**出现区域徽章、来源频道行、说明条 | §20.4 卡片内区域徽章；§27.4 `FromChannelRow` 独立行；§27.2 推荐流顶部常驻 `PlaybackPrefBar`；§28.7 定位条常驻长说明 |
| 加入频道放右上角 | `CardJoinButton` 固定在 `card-head` 最右，与 `···` 同排；不在正文 / 媒体下方 | §27.4 `FromChannelRow` |
| 视频下方不要按钮 | 媒体块下方**零按钮零工具条**；第一方视频下滑进入可视区静音自动播，点按**画面本身**暂停 / 继续 / 开声；右下角只留时长 + 静音指示图标（纯指示非控件） | §27.3 `MediaCreditBar`、44px 暂停 / 静音两个独立按钮 |

**不变项**：`0.40 共现 + 0.30 区域 + 0.20 活跃 + 0.10 精选`、`final_score = channel_score × 新鲜度 − 0.12 × 已订阅`、冷启动非空页、有限列表、第三方 iframe 静态占位与同意流程、来源署名 / 许可 / 原文回链 / 举报入口。

### 29.2 首屏三层信息架构（不许混层）

```text
吸顶层 sticky：标题栏 → 三 Tab → 首次定位条（两行）/ 确认后细条（一行）
              → 区域栏（当前国家 chip + 国际频道常驻 + 添加频道 + 齿轮，唯一区域表达位置；§36 单选）
              → TopSearchBar（§30.7：一行搜索框 + 搜索按钮，帖子之上）
              → SettingsPanel（齿轮展开浮层，不占信息流高度）
内容层：1 条 11px 极细提示 → Compose 发帖框（仅桌面；手机端只用右下角 + FAB，§36.8） → N 张内容卡
        → 尾部频道候选 → 1 条极细收尾
右栏：热门关键词 chips / 你可能想加入 / 趋势 / 合规说明
```

> **§30 补充**：搜索栏属于吸顶层的**功能控件**，不是「第一条帖子上方的说明条」，因此不违反本节「首屏只有一条 11px 极细提示」的精简裁决；桌面右栏不再重复放输入框，避免两个同名 `id` 抢焦点。

**禁止**出现在「第一条帖子上方」或「卡片内部」：区域徽章、定位来源说明、播放偏好开关、DSA 参数长文、多行演示说明、原型版本号。v5 首屏有 4 条 `section-hint` + 一条 `PlaybackPrefBar` + `demo-note`，v6 压到 1 条极细提示。区域信息只在顶部出现，**卡片里不再重复**。

### 29.3 X 式帖子卡结构

| 序 | 区块 | 内容 | 规则 |
|---|---|---|---|
| 1 | 左列头像 | 40px 圆形色块 + 频道首字 | 桌面 40 / 移动 36，固定列宽 |
| 2 | `card-head` | 频道名（粗体）、认证、`@handle` · 时间、置顶图标、推荐理由小图标 | 单行 `nowrap` + 省略号；**右上角 `CardJoinButton` + `···`** |
| 3 | `card-copy` | 按语（可选）、标题 15px、正文 14px、内联话题标签 | 标签不另起色块 |
| 4 | `MediaBlock` | 8 种布局 | `--r-lg` 外层裁切；**下方无条、无按钮** |
| 5 | `SourceLine` | 来源名 + 许可角标 + 原文回链 + N 个来源展开 | 一行 11px，合规一等组件，不可折叠删除 |
| 6 | `ActionBar` | 回复 / 转发 / 喜欢 / 收藏 / 分享 / 举报 6 个纯 SVG 图标 | `space-between`，命中区 44px；举报常驻 |

全宽无圆角列表卡、仅底部分隔线；`padding:12px 16px 6px`，移动 `10px 12px 5px`。推荐理由从可见长条收为头部 `why-dot`（`role="img"` + `aria-label` + `title`），悬停与读屏仍可读，满足 §26 可解释要求。

### 29.4 加入频道：右上角

- 未订阅「＋ 加入」实心 / 已订阅「✓ 已加入」幽灵；视觉高 30px，**命中区 44px**（伪元素扩展，§29.7）。
- `aria-label` 写明「加入频道 {频道名}」/「退订频道 {频道名}」，不能只写「加入」。
- 点击即时同步订阅集合、「正在关注」内容、Tab 计数、按钮状态，并写 `recommend_impression.joined_channel=true`；已订阅频道内容降权 0.12（§27.4 不变）。
- 频道名已在头部，故删除「来自频道 X」独立行；区域归属也不在卡片重复，减少重复信息。

### 29.5 视频：无按钮，下滑自动播

| 行为 | 实现 |
|---|---|
| 起播 | 第一方视频 `IntersectionObserver` 进入可视区 → `muted=true` + `autoplay`；第三方 iframe 仍**禁止**自动播 |
| 暂停 / 继续 / 开声 | 点按媒体块本身（`data-playtoggle` + `data-state="playing|paused"` + `role="button"` + `tabindex="0"`，Enter / Space 同效） |
| 静音指示 | 右下角时长角标旁 12px `i-mute` 图标，**纯状态指示，不是控件** |
| 离开视口 / 省流量 / 减少动效 / 非 Wi-Fi | 暂停并降级静态封面 |
| 禁止 | 媒体块下方的 `mbar`、暂停按钮、静音按钮、说明条、任何 `data-media` 控件 |

用户心智是「下滑就播、点一下就停」，额外按钮是冗余认知负担；把播放控制权还给播放器本身，把版面还给内容。第三方播放器的「站内播放 / 去原站看」与 PECR 同意三选项**不受影响**——它们是合规动作，不是播放控件。

### 29.6 SettingsPanel：设置型信息的唯一去处

- 入口：区域栏最右齿轮（`aria-expanded` 同步）+ 首次定位条「详情与开关」；`position:absolute; top:100%; right:0`，宽 `min(420px,100%)`，`max-height:70vh` 可滚。
- 四组：播放（第一方自动播开 / 关、第三方每次询问 / 默认站内播放）、推荐与透明度（DSA Art 27 的 0.40/0.30/0.20/0.10 + 非画像时间序 + 冷启动演示）、区域与定位（来源、精度、更改 / 关闭 / 重开 / 重放 / 模拟未开法域）、演示（版本与精简口径）。
- **内容始终渲染，只用 `hidden` 控可见性**：读屏与自动化门禁都能读到 DSA 参数，不因面板收起而丢失披露；切 Tab 自动收起。
- 首次定位条压缩到两行后，「区域由平台创建、频道可由用户自建」的口径仍在「添加频道」页与合规角标，不丢失 §28 的治理表达。

### 29.7 无障碍：44px 约束的是命中区

X 式紧凑按钮视觉 30–34px 才能整洁；本产品自定 44×44 不变，但判定对象是**命中区**（WCAG 2.2 AA 2.5.8 亦按目标尺寸判定）：

```css
.card-join,.card-more,.reg-gear,.rchip button{position:relative;min-height:30px}
.card-join::after,.card-more::after,.reg-gear::after,.rchip button::after{
  content:"";position:absolute;inset:-7px -3px;  /* 命中区扩到 44px */
}
```

图标按钮全部有 `aria-label`；加入状态靠文字 + 图标 + 底色三重指示，不靠颜色；`data-playtoggle` 可键盘聚焦；`prefers-reduced-motion` 下不自动播。收藏按钮用 `aria-label` + `.saved` 切状态，**不得改 `textContent` 把 SVG 冲掉**。

### 29.8 数据 / API / 埋点增量

- **无新增表、无 DDL、无后端改动**。`user_playback_pref`（§27.6）、`recommend_impression`（§27.6）、`user_consent_log`（§24）全部沿用；`settings_panel_open` 仅前端会话态，不入库、不进画像。
- 新增埋点（仍按 `channel_id` / `region_code` 聚合，禁止逐条行为序列）：`card_join_clicked(position='card_head_right')`、`media_frame_tapped(action=pause|resume)`、`settings_panel_opened(entry='gear'|'loc_detail')`。
- `/me/feed?tab=`、三 Tab、区域图谱打分、冷启动兜底、房间原型**全部未改**。

### 29.9 原型 v6 界面变更清单

| 位置 | v5 | v6 |
|---|---|---|
| 顶部 | 定位条常驻多行 + 区域栏 + 4 条说明 + demo-note | 首次两行横幅 / 之后一行细条 + 单行区域栏 + 齿轮；1 条极细提示 |
| 区域表达 | 区域栏 + 每张卡 `rbadge` | **只在顶部区域栏与「添加频道」页** |
| 加入入口 | 卡内「来自频道 X · 感兴趣 · 加入频道」独立行 | 卡片右上角 pill 按钮 |
| 媒体 | 下方 `MediaCreditBar` + 暂停 / 静音按钮 | 下方零条零按钮，点按画面暂停 |
| 来源 / 操作 | 带边框来源块 + 文字按钮操作栏 | 一行 `SourceLine` + 一行 6 个 SVG 图标 |
| 播放 / 推荐参数 | 推荐流顶部常驻 `PlaybackPrefBar` | 顶部 `SettingsPanel` 浮层，一次点击可达 |

### 29.10 门禁与验收

```bash
python design-system/check-contrast.py
node  design-system/check-ui.js
node  design-system/check-global.js       # 区域只在顶部 / 卡片内无 rbadge / 右上角加入
node  design-system/check-media.js        # 8 布局 / 无底部播放按钮 / 点按暂停 / 设置面板含 DSA 参数
node  design-system/check-location.js    # 定位三态 / 设置浮层可达 / 未开法域回退
node  design-system/check-rooms.js       # §30 顶部搜索 / 多房间 / 评论 / @# / AI 关键词
```

三道业务门禁已按 §29 改写断言；**§30 起六道全绿方可发布**（新增 `check-rooms.js`）。人工断言：① 第一条帖子前只有一条 11px 提示；② 每张卡右上角「加入」可见且不换行；③ 视频下方无按钮、点按画面能暂停；④ 齿轮展开不遮挡 Tab、四组可读；⑤ 深浅主题 / 420px 移动 / 200% 缩放无重叠；⑥ 紧凑按钮命中区 ≥44px 且互不重叠。

### 29.11 排期与合规增量

| 阶段 | 内容 | 增量 |
|---|---|---|
| G0（1 天，与 §28 G1 合并） | 前端渲染层改造：顶部区域栏、设置浮层、X 式卡片、右上角加入、媒体无按钮 | **无新表、无接口、无新增合规评估项** |
| 法务复核（0.5 天） | 确认 DSA Art 27 从「常驻」改为「一次点击可达」仍满足 directly accessible | ToS 全文 + 设置面板 + Tab 时间序三重兜底；建议保留右栏合规角标摘要 |
| 回归（0.5 天） | 六道门禁（§30 新增 `check-rooms.js`） + 深浅主题 / 移动视图 / 读屏走查 | — |

OSA 2023 风险评估无需重做：推荐规则、内容池与放大路径未变，只是控件位置变化；但须在评估记录里留一条「UI 精简未改变推荐输入与排序」的变更说明。

### 29.12 常见坑

1. 为「简洁」把来源署名折叠进「···」→ 违反 §7 / §20.6 的 NLA 口径与显著署名要求。
2. 把 DSA 参数只放设置页、推荐界面无入口 → Art 27「directly accessible」风险；齿轮必须一次点击可达且面板内容始终渲染。
3. 紧凑按钮直接把 `min-height` 降到 30px 而不扩命中区 → 破坏 44px 自定底线与 WCAG 2.5.8。
4. 用 `textContent` 改收藏按钮文字把 SVG 冲掉（v6 已改用 `aria-label` + `.saved`）。
5. 视频「点按暂停」忘加 `tabindex` / Enter / Space → 键盘用户无法暂停。
6. 第三方 iframe 也跟着「下滑自动播」→ 违反 §24 / §27 四条硬红线与 PECR 事前同意。
7. 设置面板用 `display:none` 且内容不渲染 → 门禁与读屏都读不到 DSA 参数，合规披露丢失。
8. 把区域徽章从卡片删掉后，连顶部区域栏也一起省了 → 用户失去「我在看哪个区域包」的上下文。

### 29.13 待裴总拍板

① 设置浮层是否需要 Esc / 点击外部关闭（建议要，当前仅齿轮与切 Tab 收起）；② 「区域由平台创建、频道可用户自建」只留在「添加频道」页与合规角标是否足够（建议够，首次条已压缩）；③ 简繁切换是否也收进同一浮层（与 §25.5 第 ③ 项合并）；④ 前几轮悬而未决四项仍见 §28.12 ④。

---

## 30. 多房间小圈子、留言评论、@/# 语法、AI 关键词与顶部搜索（2026-11-09 第十一轮反馈）

> 本章回答裴总五连问：①「官方开通频道」到底是谁开通；②「用户创建多个房间，像一个小圈子，剧名 / 电影名都能当房间名，一部剧 20 集」；③「其他用户可以在房间留言评论」；④「@ 是用户名，# 是关键词；发帖没设关键词时官方 AI 自动最多生成 5 个」；⑤「搜索按钮放在帖子上面」。
> **§0–§29 的业务规则全部沿用**：三层频道、统一内容池、`channel.layout` / `room_type` / `media_origin`、版权四态、24h 下架、区域与法域权限矩阵、X 式帖子卡与右上角加入、视频无按钮自动播、DSA Art 27 披露。本章只做**治理边界澄清 + 三块增量（房间数量、评论、@/# 与关键词）+ 一处位置调整（搜索）**。

### 30.1 裁决摘要

| 反馈 | 裁决 | 不改的东西 |
|---|---|---|
| 官方开通频道 | **「频道」= 平台开通的官方 L1/L2 频道**（随法域启用由后台批量开设，带认证徽章）；**用户创建的一律叫「房间 · 小圈子」**，`channel.kind='user_created'`，不带认证徽章、不叫「官方」、不自动进官方区域包。用户点「申请开通」仍是需求信号，不是开通动作（§28.4） | §28 权限矩阵一条不减 |
| 用户创建多个房间 | 一人可建**多个房间**（默认软上限 20 个活跃房间），一部剧一个房间、一部电影一个房间；20 集电视剧按 `sort_key` 固定排序；房间名可用作品名，但**必须带描述性后缀 + 「用户自建 · 非官方」徽章** | §22 / §23 的 `layout='collection'`、`room_type`、`collection_item`、无正片上传 |
| 房间留言评论 | 房间新增「留言 / 讨论」Tab，其他用户可留言、可回复、可 @ 人、可 # 关键词、可举报；评论走同一套审核 / 24h 下架 / `takedown_request` | 被动托管地位、不主动监控义务 |
| @ / # / AI 关键词 | `@handle` = 用户名提及，`#关键词` = 检索关键词；**用户一个关键词都没填时**，服务端官方 AI 生成**最多 5 个**，逐个标注「AI 生成」且用户可改可删；只要用户填了 ≥1 个，AI 不介入 | §21.7「AI 只做辅助、不自动发布」 |
| 搜索放帖子上面 | 吸顶层新增**一行 `TopSearchBar`**（区域栏下方、第一条帖子上方），桌面右栏保留热门关键词；支持内容 / 频道 / 房间 / `#关键词` / `@用户名` 五种检索 | §29「帖子区只放内容」「第一条帖子前只有一条 11px 提示」——搜索栏属于**吸顶层**，不是帖子区说明条 |

### 30.2 名称与权限：官方频道 vs 用户房间（本轮最容易做错的一层）

| 对象 | 谁能创建 / 开通 | 标识 | 能否进官方区域包 | 责任 |
|---|---|---|---|---|
| `region` / `jurisdiction_policy` | 平台后台，风险评估后 | — | — | 开一个法域 = 一个合规项目 |
| L1 官方自动 / L2 官方精选**频道** | **平台随法域启用批量开通**，`kind ∈ {official_auto, official_curated}` | 认证徽章 + 「平台开设」 | 是（运营维护 `channel_pack`） | 平台直接内容提供者，责任最重 |
| 用户**房间（小圈子）** | 用户，手机验证 + 审核队列 | 「用户自建 · 非官方」+ 房主 `@handle` | **否** | 托管服务，责任较轻 |
| 用户房间内的**留言 / 评论** | 任意登录用户（可配置成需加入房间） | 作者 handle + 时间 | — | UGC 托管，与内容同一套处置 |

四条硬边界（§28.4 的延伸，写进 ToS 与服务端校验）：

1. 用户房间**不得**使用认证徽章、不得命名为「XX 官方 / 官方认证 / 官方频道」；房间名允许指称作品（描述性 / nominative use），但必须加「追更房间 / 片单 / 小圈子」之类后缀，且房间页首屏显示「用户自建 · 非官方，与片方无关联」。
2. 房间封面**不得**使用官方海报、剧照、Logo（`cover_licence_ref` 非空才展示，§22.5）；用户名、头像、房间名都不得暗示片方授权。
3. 平台**不得**对高风险房间 / 单集 / 评论做置顶、推荐加权、广告变现（§22.3 active participant 红线仍然成立；评论的出现不改变这一条）。
4. 「申请开通」永远只写 `region_launch_request`，**不得**写 `region.enabled`、不得创建官方频道（§28.5 触发器仍生效）。

### 30.3 多房间模型：一人多房间，不新增表

房间本质仍是 `channel` 的一行：`layout='collection'`、`kind='user_created'`、`room_type ∈ {series, film, video}`、`owner_id=user.id`。**不新建 `room` 表**，避免与 `channel` / `channel_item` / 订阅 / 审核 / 埋点分叉。前端新增 `RoomSwitcher`（我的房间列表）只是 `GET /me/rooms` 的一个视图。

| 场景 | 数据形态 | 排序 |
|---|---|---|
| 剧名房间（《新闻女王》追更，20 集） | `room_type='series'`，20 行 `collection_item`，`sort_key=S01E001..S01E020` | `season_no, COALESCE(sort_override, episode_no)`，固定不重排 |
| 电影名房间（《花樣年華》片單） | `room_type='film'`，`collection_item` 无季集（`chk_series_fields`，§23.4） | 自定义顺序 / 年份 |
| 视频小圈子 | `room_type='video'`，原创可托管、他人内容仅官方外链（§23.3） | 时间序 |

**数量上限从 §22.6 的「每用户 3 个」改为「默认 20 个活跃房间」**：一部剧一个房间是产品前提，3 个会直接掐死核心用法。用软上限 + 触发器 + 风控替代硬编码 3：

- `trg_room_quota`：同一 `owner_id` 且 `layout IN ('collection','board')` 且 `deleted_at IS NULL` 的行数 > 20 → 拒绝，需人工复核后调 `room_quota_override`。
- 创建速率：每小时 ≤3、每天 ≤10；空房间（0 条目且 30 天无活跃）自动归档，不占额度。
- 手机验证、审核队列、重复侵权政策（3 次有效投诉冻结发布权）沿用 §22.8。

> 为什么不是「无限」：无限房间 = 无限审核面 + 刷屏 / SEO 垃圾房 / 盗版索引房，托管抗辩也会被「组织、推广大量用户上传作品」侵蚀（§28.4 第 2 条 / EU DSA Art 17 OCSSP）。

### 30.4 房间留言与评论

**产品形态**：房间页二级 Tab 增加「留言 · 讨论」（`view=comments`），与「内容」「本房间分类信息」并列。其他用户可发留言、回复、点赞、举报；单集 / 片目上的「N 条讨论」点击后跳到留言 Tab 并带 `#comment-<item_id>` 锚点。评论**不进推荐流、不进全局信息流、不推送**（§22.10 放大红线），只在房间内按时间倒序展示。

**DDL 增量**（PostgreSQL 16；`CHECK` 内不写子查询，跨表约束用触发器）：

```sql
CREATE TYPE comment_status AS ENUM ('pending','published','removed','restored');

CREATE TABLE room_comment (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id       uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  content_id    uuid REFERENCES content(id) ON DELETE CASCADE,   -- 可空：房间级留言
  parent_id     uuid REFERENCES room_comment(id) ON DELETE CASCADE,
  author_id     uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  body          varchar(1000) NOT NULL,
  status        comment_status NOT NULL DEFAULT 'pending',
  mentions      smallint NOT NULL DEFAULT 0 CHECK (mentions BETWEEN 0 AND 10),
  keywords      smallint NOT NULL DEFAULT 0 CHECK (keywords BETWEEN 0 AND 5),
  created_at    timestamptz NOT NULL DEFAULT now(),
  edited_at     timestamptz,
  removed_at    timestamptz,
  moderation_ref text,
  CONSTRAINT chk_comment_len CHECK (char_length(body) BETWEEN 1 AND 1000),
  CONSTRAINT chk_comment_scope CHECK (
    (room_id IS NOT NULL) AND (content_id IS NULL OR parent_id IS NULL)
  )
);
CREATE INDEX idx_comment_room ON room_comment(room_id, created_at DESC)
  WHERE status = 'published';
CREATE INDEX idx_comment_item ON room_comment(content_id, created_at DESC)
  WHERE status = 'published' AND content_id IS NOT NULL;
-- content_id 必须属于同一房间：由 trg_comment_room_scope 触发器校验（CHECK 不能跨表）
```

**规则**：① 评论与内容共用审核队列、举报入口、`takedown_request` 与 **24h SLA**，不因为是「小圈子」而免审；② 房主可隐藏自己房间内的评论但不能删他人证据链，`removed_at` + `audit_log` 留痕；③ 评论按房间维度限流（同一用户 5 条/分钟、20 条/小时）；④ `mentions` / `keywords` 是解析后的计数，服务端写入，**不接受前端传值**；⑤ 默认公开可见但登录才可发，UK GDPR 下作者可删除自己的评论（DSAR 擦除走 §9 `/me`）。

**合规增量（必须补进 §13.3 风险评估记录）**：评论是典型的 **user-to-user service**，OSA 2023 风险评估要新增「留言骚扰、@ 提及滥用、剧透 / 盗版链接被评论转发」三条；EU DSA 下评论同样可能构成 OCSSP 的「存储 + 向公众传播」，因此仍坚持**被动托管、不做算法放大、不变现**；评论区出现外链时沿用 §24 白名单校验，不因在评论里就放过。

### 30.5 `@用户名` 与 `#关键词` 语法（内容 / 评论 / 房间按语统一）

| 记号 | 语义 | 存储 | 点击行为 |
|---|---|---|---|
| `@handle` | 提及用户（`app_user.handle`，2–20 位字母数字下划线） | `mention` 表一行 | `GET /search?type=user&q=handle` → 用户页 |
| `#关键词` | 检索关键词（1–12 位中文 / 字母 / 数字 / 下划线，**不含空格、URL、标点**） | `content_keyword` / `comment_keyword` 关联 | `GET /search?type=keyword&q=关键词` → 关键词聚合页 |

解析规则（服务端权威，前端只做展示）：

1. 先 HTML 转义再按 token 正则替换，**禁止把原文拼进 `innerHTML`**（防 XSS）；`javascript:` / `data:` 一律不匹配。
2. 去前缀存储（`#伦敦` 存 `伦敦`），统一小写 + NFC 归一；`#` 后第一个空格 / 标点即终止；`@` 只在词首或空白后生效，避免把邮箱当成提及。
3. 单条内容 / 评论：**关键词 ≤5、提及 ≤10**；超出部分保留为纯文本，不报错、不静默丢弃。
4. 提及必须解析到存在的 `app_user`，否则不生成通知，只渲染成普通文本；同一用户同一条内容只通知一次。
5. 提及通知默认「仅我关注的人」开启、陌生人关闭；用户可全局关闭 @ 通知；批量 @（>5）触发风控，不生成通知。
6. 关键词**不得含**个人数据、健康 / 政治倾向 / 宗教 / 族裔 / 性取向 / 移民状态等敏感属性，也不得是 AI 凭空推断的事实；命中禁用词直接丢弃该 token。
7. `#关键词` 与 `@handle` 只作为**检索与导航元数据**，**不进入 §26 / §27 的推荐打分公式、不进用户画像**——否则要重做 DSA Art 27 参数披露与 UK GDPR 合法利益评估。

```sql
CREATE TYPE keyword_source AS ENUM ('user','ai_auto','ai_suggested_accepted','editor');

CREATE TABLE keyword (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name      citext NOT NULL UNIQUE,
  status    varchar(12) NOT NULL DEFAULT 'active',  -- active / blocked
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_keyword_name CHECK (name ~ '^[\p{Han}A-Za-z0-9_]{1,12}$')
);
CREATE TABLE content_keyword (
  content_id uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  keyword_id uuid NOT NULL REFERENCES keyword(id) ON DELETE RESTRICT,
  source     keyword_source NOT NULL,
  position   smallint NOT NULL CHECK (position BETWEEN 1 AND 5),
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (content_id, keyword_id),
  UNIQUE (content_id, position)
);
CREATE TABLE comment_keyword (
  comment_id uuid NOT NULL REFERENCES room_comment(id) ON DELETE CASCADE,
  keyword_id uuid NOT NULL REFERENCES keyword(id) ON DELETE RESTRICT,
  source     keyword_source NOT NULL DEFAULT 'user',
  PRIMARY KEY (comment_id, keyword_id)
);
CREATE TABLE mention (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id        uuid REFERENCES content(id) ON DELETE CASCADE,
  comment_id        uuid REFERENCES room_comment(id) ON DELETE CASCADE,
  mentioned_user_id uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  created_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_mention_one_source CHECK (
    (content_id IS NOT NULL)::int + (comment_id IS NOT NULL)::int = 1
  )
);
CREATE UNIQUE INDEX uq_mention_once ON mention
  (content_id, comment_id, mentioned_user_id) NULLS NOT DISTINCT;
```

> `citext` + `UNIQUE` 保证 `#倫敦` / `#伦敦` 不重复建词（简繁映射另由 §4 AI 整理层处理）；`UNIQUE (content_id, position)` + `position ≤5` 在数据库层把「最多 5 个」钉死，不靠前端 `maxlength`。

### 30.6 官方 AI 自动关键词：只在用户一个都没填时触发

**触发条件**：`POST /contents` / `POST /channels/:id/items` / `POST /rooms/:id/comments` 时，客户端传入 `keywords=[]` → 服务端调用官方 AI 关键词服务；**只要用户填了 ≥1 个，AI 完全不介入**，不「补全到 5 个」，不覆盖用户选择。

| 约束 | 规则 |
|---|---|
| 数量 | **最多 5 个**（可以少于 5；低置信时宁少勿滥），每个 ≤12 字 |
| 输入 | 仅标题 + 正文 + 用户选的分类；**不读浏览历史、订阅关系、位置、设备、行为序列** |
| 输出 | 受控词表优先 + 正文抽取；不得生成人名（除非原文出现）、地点推断、未出现的事实、敏感属性 |
| 标识 | `source='ai_auto'`，UI 每个 chip 带「AI」角标 + `aria-live` 说明「官方 AI 生成 N 个关键词，可改可删」 |
| 可撤回 | 发布前可逐个删除 / 改写；发布后仍可编辑，改写即变 `source='user'`；删除写 `audit_log` |
| 审计 | `ai_keyword_run` 记 `model_version / policy_version / input_hash / result / latency / user_edited`；**不存正文原文**，只存 SHA-256 摘要 |
| 失败降级 | 模型超时 / 低置信 / 命中禁用词 → 返回 0–3 个或空数组，**绝不阻塞发布**；空关键词内容仍可正常发布与检索 |
| AI 定位 | 沿用 §21.7：AI 是辅助整理器，不是排序器；关键词不进推荐打分公式 |

```sql
CREATE TABLE ai_keyword_run (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  content_id     uuid NOT NULL REFERENCES content(id) ON DELETE CASCADE,
  model_version  varchar(40) NOT NULL,
  policy_version varchar(40) NOT NULL,
  input_hash     char(64) NOT NULL,          -- sha256(title||body||category)，不存原文
  result         jsonb NOT NULL DEFAULT '[]'::jsonb,
  max_keywords   smallint NOT NULL DEFAULT 5 CHECK (max_keywords = 5),
  latency_ms     int,
  user_edited    boolean NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_ai_result_len CHECK (jsonb_array_length(result) <= 5)
);
```

**合规说明**（写进 ToS 与隐私政策）：① UK GDPR Art 22 不触发——关键词不产生法律或类似重大影响，且用户可编辑、可删除、有人复核；② 合法利益为「让内容可被检索」，LIA 记录最小化输入、不画像、可反对；③ EU AI Act 的透明度义务按「AI 生成 / 辅助的元数据」主动披露，不依赖是否属于深伪；④ DSA Art 27 参数表**不变**，因为关键词不参与排序，若将来把关键词接入打分，必须重新披露并评估放大风险；⑤ AI 输出同样受 §11 审核与关键词禁用词表约束，幻觉词不得进入公共词表。

### 30.7 搜索入口：移到帖子上方

`TopSearchBar` 放在 §29.2 吸顶层的最后一行（三 Tab → 定位条 → 区域栏 → **搜索栏** → 齿轮浮层），第一条帖子之上；桌面右栏把重复的输入框换成「热门关键词」chips（`#租房` `#eVisa` `#追剧`），移动视图只保留顶部一行，避免两处输入框抢焦点。

- 一行结构：搜索 SVG + `input[aria-label="搜索内容、频道、房间、@用户名或#关键词"]` + 「搜索」按钮（44px 命中区）+ 清除按钮（有查询时才显示）；Enter 提交。
- `#` 前缀 → `type=keyword`；`@` 前缀 → `type=user`；否则 `type=all`；结果页可按 `content / channel / room / keyword / user` 分栏。
- 搜索词只写**聚合计数**（`search_query_agg`，按 `region_code` + 天聚合），**不写逐用户搜索历史、不进画像**；`q` 写访问日志时做截断与脱敏。
- `/search?q=&type=&city=&channel=` 扩展 `type` 枚举并新增 `GET /keywords/hot?region=`、`GET /me/rooms`、`GET /rooms/:id/comments`（§9.2）。

### 30.8 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/me/rooms?cursor=` | 我创建的多个房间（含 `room_type`、条目数、活跃度、软上限用量 `quota_used/20`） |
| POST | `/rooms` | 增加 `quota` 校验与 `owner_badge='user_created'`；创建后不可改 `room_type`（§23.2） |
| GET / POST | `/rooms/:id/comments?cursor=` | 房间留言 / 单集评论；`mentions` `keywords` 由服务端解析回填 |
| POST | `/rooms/:id/comments/:cid/report` | 复用举报 → `takedown_request` / 24h SLA |
| PATCH / DELETE | `/rooms/:id/comments/:cid` | 作者编辑 / 删除（软删留痕） |
| POST | `/contents/:id/keywords` | 用户改写 AI 关键词（`source` 变 `user`，写 `audit_log`） |
| POST | `/ai/keywords:preview` | 编辑器内预览 AI 关键词（不写库、不入画像） |
| GET | `/search?q=&type=all\|content\|channel\|room\|keyword\|user` | 统一搜索扩展 |
| GET | `/keywords/hot?region=` | 顶部右栏热门关键词（聚合，非个性化） |

### 30.9 界面变更清单

| 文件 | 版本 | 变更 |
|---|---|---|
| `prototype-x-style.html` | **v7** | 吸顶层新增 `TopSearchBar`；卡片正文 / 按语内联渲染 `@handle` / `#关键词`（可点击、转义安全）；右栏改热门关键词 chips；「添加频道」页分区「官方频道（平台开通）」与「用户房间（小圈子）」 |
| `prototype-collection-room.html` | **v4** | `RoomSwitcher` 我的房间（含 20 集剧房间、电影名房间）+ 新建房间表单；新增「留言 · 讨论」Tab（评论、回复、@/#、举报、审核提示）；房间页显示「用户自建 · 非官方」徽章与官方频道说明 |
| `publish-content.html` | **AI 关键词版** | 0 关键词时提交自动补 ≤5 个，chip 带「AI」角标，可改可删，简繁双语说明 + `aria-live`；不填关键词不阻塞发布 |
| `design-system/MASTER.md` / `preview.html` | **v1.5 / 第 13 节** | 新增 §18 组件规范：`TopSearchBar` / `RoomSwitcher` / `RoomCommentList` / `MentionToken` / `KeywordToken` / `AiKeywordChip` / `RoomOwnerBadge` |

### 30.10 验收与门禁

```bash
python design-system/check-contrast.py
node  design-system/check-ui.js
node  design-system/check-global.js
node  design-system/check-media.js
node  design-system/check-location.js
node  design-system/check-rooms.js     # 本章新增：六道门禁
```

`check-rooms.js` 真实执行三份原型并断言：① 顶部搜索栏存在于第一条帖子之前且可提交 / 清除；② `@/#` token 被转义后渲染为可点击链接，卡片内无裸 `<script>`；③ 我的房间 ≥2 个、含 20 集电视剧房间与电影名房间、可切换可新建、每个房间标「用户自建 · 非官方」；④ 留言 Tab 可发评论、渲染 @/#、举报入口常驻、评论不进推荐流；⑤ 发帖页 AI 关键词函数返回 ≤5 个、每个 ≤12 字、无重复、无敏感词、用户已有关键词时不触发；⑥ 动态生成 HTML 标签平衡。

**人工断言**：① 顶部搜索栏只有一行、不遮挡三 Tab、420px 下不横向溢出；② 一部剧 20 集按 `S01E001…S01E020` 固定排序，切房间后进度不串房；③ 陌生人 @ 不产生通知、批量 @ 被限流；④ `#` 关键词点击能到聚合页，`@` 点击能到用户页；⑤ 0 关键词提交后 AI chip 可逐个删除且不影响发布；⑥ 用户填 1 个关键词时 AI **没有**补到 5 个；⑦ 评论举报后 24h SLA 台账可查；⑧ 深浅色 / 移动视图 / 读屏走查无重叠。

### 30.11 排期与合规增量

| 阶段 | 内容 | 增量 |
|---|---|---|
| G0（1 天） | `TopSearchBar`、`RoomSwitcher`、房间归属徽章、@/# 前端渲染 | 无新表、无新合规项 |
| G1（2–3 天） | `room_comment` / `mention` / `keyword` / `content_keyword` / `ai_keyword_run` DDL + 触发器 + API | 服务端解析、限流、审计 |
| G2（1–2 天） | AI 关键词服务（受控词表 + 模型兜底）+ 编辑器标注与可撤回 | 模型版本 / 政策版本台账 |
| 法务（0.5 天） | 补 OSA user-to-user 风险项、UK GDPR LIA、EU AI Act 透明度文案、ToS 房间命名与反冒充条款 | 不重做 §13 全文，只追加变更记录 |
| 回归（0.5 天） | 六道门禁 + 三份原型深浅 / 420px / 读屏 | — |

### 30.12 常见坑

1. **把用户房间也叫「频道」并给认证徽章** → 直接违反 §28.4，平台被拖进未评估法域的「直接内容提供者」责任。
2. **新建 `room` 表** → 与 `channel` / 订阅 / 审核 / 埋点分叉，后续每个功能做两遍；房间只是 `channel.layout` 的一个值。
3. **把 3 个房间上限留着不改** →「一部剧一个房间」的核心用法当场失效；改成 20 + 速率 + 空房归档，而不是改成无限。
4. **用 `CHECK` 写跨表子查询**（如「评论的 content 必须属于本房间」）→ PostgreSQL 不支持，必须用触发器。
5. **先渲染后转义**：把用户正文拼进 `innerHTML` 再做 @/# 链接 → XSS；顺序必须是「转义 → 正则替换 → 输出」。
6. **AI 把关键词补满 5 个** → 用户填了 1 个也被覆盖，违背「没有设置才自动生成」；且低置信时硬凑 5 个会造出幻觉词。
7. **把 AI 关键词接进推荐打分** → DSA Art 27 参数表、UK GDPR 合法利益、放大风险三项全部要重做；本章明确不接。
8. **评论免审 / 评论里放过外链白名单** → 24h SLA 与 hosting defence 出现缺口，且盗版链接会绕到评论区。
9. **顶部搜索 + 右栏搜索两个同名 `id`** → 键盘焦点、label 关联与自动化门禁一起坏；右栏只留热门关键词 chips。
10. **搜索写逐用户历史** → 把「检索」变成「画像」，与 §26 / §27 的非画像承诺冲突。

### 30.13 待裴总拍板

① 房间软上限 20 是否合适（建议 20，超过走人工复核）；② 评论是否要求「先加入房间才能发言」（建议要求，能显著降低骚扰与刷屏，但会压低首日互动）；③ `#关键词` 是否允许简繁自动合并成同一个词（建议合并，需词表映射）；④ 陌生人 @ 通知默认关闭是否过严（建议保持关闭，可在设置里开）；⑤ AI 关键词是否也用于**房间名 / 房间按语**（建议首版只用于帖子与分类信息，房间沿用用户自填）；⑥ 前几轮遗留四项仍见 §28.12 ④、§29.13。

---

## 31. 「添加频道」改为「创建房间」：房间强制挂靠官方频道（2026-11-09 第十二轮反馈）

> 本章回答裴总第十二轮反馈：① 左侧导航「添加频道」应改为「创建房间」；② 用户在自己**已加入的官方频道**下创建房间，自定义房间名（如「30 级电视剧」）；③ 其他用户可访问并留言评论；④ 房间能承载「30 集电视剧」或「一部电影」的条目。**§0–§30 的业务规则全部沿用**，尤其 §22 / §23 的 `layout='collection'`、`room_type`、`collection_item`、**无正片上传**、`media_origin` 约束、§24 官方外链、§30 的「官方频道 vs 用户房间」与留言评论。本章只做**一处入口与导航重定位 + 一处归属关系（父频道）+ 一处容量与承载澄清**。

### 31.1 裁决摘要

| 反馈 | 裁决 | 不改的东西 |
|---|---|---|
| 「添加频道」→「创建房间」 | 左侧导航项与对应 Tab/页面**更名并重定位**为「创建房间」；原「添加频道」的**官方频道目录 + 加入/退订**功能**迁移**到「发现」页与「我的频道」页，不删除（用户仍需发现并订阅官方频道，才能在其下建房间） | §20 三 Tab 首页、§26 频道数据推荐、§28 权限矩阵 |
| 房间挂靠官方频道 | 房间新增 `parent_channel_id`（可空，但**用户创建流程强制必填**）：房间必须挂靠在用户**已加入**的官方频道下；`room_type ∈ {series, film, video}` 不变 | §30.2 命名与权限、§22.3 不托管正片 |
| 自定义房间名（30 级电视剧） | 房间名 = 用户自填 + 描述性后缀（「追更房间 / 片单 / 小圈子」），保留「用户自建 · 非官方」徽章；「30 集电视剧」是 `room_type='series'` 的典型形态，**30 是示例容量、非硬上限**（软上限仍为 §30.3 的 20 个活跃房间） | §30.2 反冒充、§30.6 AI 关键词不用于房间名 |
| 承载「数据」 | **「数据」= 元数据条目 + 官方观看外链**，**绝非视频文件**；30 集 = 30 行 `collection_item`，一部电影 = `room_type='film'` 的 1 行片目 | §22.5 `chk_episode_no_media`、§23 `media_origin`、§24 外链白名单 |

### 31.2 入口与导航变更（本轮界面层主改动）

| 位置 | 变更前 | 变更后 |
|---|---|---|
| 左侧导航（桌面） | `添加频道`（`data-goto="add"`，`#i-plus` 图标） | `创建房间`（保留 `#i-plus` 图标，`aria-label="创建房间"`，点击打开创建流程） |
| 移动底部 Tab | 「添加频道」 | 「创建房间」 |
| 原「添加频道」页内容 | 频道目录 + 组合包 + 加入/退订 | **迁移**：频道目录并入「发现」页「官方频道」区；组合包与加入/退订并入「我的频道」页；「添加频道」独立页**废弃** |
| 新「创建房间」入口 | — | 点击后进入**两段式创建流程**：①选父频道（已加入的官方频道，单选必填）→ ②填房间名 + 选 `room_type` + 版权确认 → 提交 |

> **为什么不直接删「添加频道」**：订阅官方频道是建房间的前置条件（房间必须挂靠已加入的官方频道）。若用户尚未订阅任何官方频道，创建流程第一步就应提示「你还没有加入任何官方频道，先去发现页加入一个」，并给跳转按钮。订阅动作只是**换了入口位置**，没有从产品里消失。

### 31.3 数据模型：`parent_channel_id`（一处增量，不新建表）

房间仍是 `channel` 的一行，`layout='collection'`、`kind='user_created'`。新增一个可空外键表达父子关系：

```sql
ALTER TABLE channel
  ADD COLUMN parent_channel_id uuid REFERENCES channel(id) ON DELETE SET NULL;

-- 只允许「用户房间」挂到「官方频道」下，跨表约束用触发器
-- trg_room_parent：INSERT/UPDATE 时校验
--   1) parent_channel_id 非空 → 本行 kind='user_created' AND layout IN ('collection','board')
--   2) 父行 kind IN ('official_auto','official_curated')
--   3) 父行是该 owner 已订阅的频道（subscription 表存在 active 行）
-- 任一不满足 → RAISE EXCEPTION
```

**规则**：

1. `parent_channel_id` 对**用户创建的房间**是**必填**（创建流程强制选择）；对平台自建的示范房间可为空。
2. 挂靠关系**创建时锁定**，创建后**不可改**（与 §23.2「room_type 创建后不可改」同粒度）。
3. 父频道删除 → `ON DELETE SET NULL`，房间降级为「未挂靠」并显示「原频道已下线」提示，**不级联删除房间**（用户内容仍在）。
4. 房间的可见性与推荐：**不进全局推荐流**（§22.10 红线不变），仅在父频道页的「本频道房间」区、房主的「我的房间」、以及搜索 `type=room` 中可见。
5. `GET /me/rooms` 返回 `parent_channel_name` 供 RoomSwitcher 显示归属。

### 31.4 容量与承载澄清（「30 级电视剧 / 一部电影」）

| 用户诉求 | 数据形态 | 容量 |
|---|---|---|
| 30 集电视剧 | `room_type='series'`，30 行 `collection_item`，`sort_key=S01E001..S01E030` | 软上限仍为 20 个活跃房间，**单房间条目数不设硬上限**（30 是示例，50 集长剧也支持），但每房间条目数建议引导 ≤200（防刷屏） |
| 一部电影 | `room_type='film'`，1 行片目（片名、年份、片长、合法观看入口） | 同上 |
| 「放视频」 | **只登记元数据 + 官方外链**（`embed_url_template` 由服务端下发，§24）；**永不存储 / 转存 / 代理视频流** | §23.3：只有用户原创视频房间可托管文件，且强制版权确认 + 审核 |

> 向裴总的明确答复（本轮已确认）：视频承载选「**元数据 + 官方外链**」，不存视频文件。房间看起来「能放 30 集 / 一部电影」，实际是「登记 30 集的剧名 / 集号 / 合法观看入口」，用户点击跳转 YouTube / 官方平台观看。这是 §22.3「不托管正片」红线的直接延续。

### 31.5 与 §30 的冲突裁决

| 项 | §30 原判 | §31 新判 | 理由 |
|---|---|---|---|
| 房间归属 | 房间可全局、可跨区域（§30.2「港剧追剧房间」不必绑国家） | **用户创建的房间强制挂靠已加入官方频道** | 裴总第十二轮明确要求；挂靠的是「频道」不是「区域」，跨区域主题仍可通过挂到「全球」官方频道实现 |
| 创建入口 | 「添加频道」页分区「官方频道 / 用户房间」 | 「添加频道」→「创建房间」，官方频道目录迁至发现页 | 入口语义更准：订阅 ≠ 创建 |
| 房间承载 | 元数据 + 外链（§22/§23/§24） | **不变**，仅重申「30 集 / 一部电影」的容量澄清 | 合规红线不可动 |

### 31.6 界面与原型变更清单

| 文件 | 版本 | 变更 |
|---|---|---|
| `prototype-x-style.html` | **v8** | 左侧导航「添加频道」→「创建房间」；点击弹创建流程（选父频道 → 房间名 + 类型 + 版权确认）；原「添加频道」Tab 内容迁至发现页「官方频道」区与「我的频道」页；移动底部 Tab 同步更名 |
| `prototype-collection-room.html` | **v5** | 房间页头部新增「挂靠频道」归属行（`@频道名 · 官方`）；RoomSwitcher 显示每个房间的父频道；新建房间表单增加「父频道（必选，仅列出已加入的官方频道）」下拉 |
| `design-system/MASTER.md` / `preview.html` | **v1.6** | 新增 §18.1 组件规范：`RoomCreateFlow` / `ParentChannelPicker` / `RoomParentLine`；复用既有 token |

### 31.7 验收与门禁

在 §30.10 六道门禁基础上，`check-rooms.js` 追加断言：① 导航项文案为「创建房间」，无「添加频道」残留；② 创建流程第一步父频道下拉**只含已加入的官方频道**，未加入时显示引导而非空列表；③ 房间名保存后带「用户自建 · 非官方」徽章与「追更房间 / 片单」后缀；④ `parent_channel_id` 为空的用户房间无法通过创建（前端 + 服务端双重校验）；⑤ 30 集剧房间固定排序 `S01E001..S01E030` 不重排；⑥ 房间内每条目只有「去原站看」外链、无任何视频文件控件；⑦ 父频道删除后房间降级显示「原频道已下线」，房间与条目不丢失。

**人工断言**：① 「创建房间」与「发现页官方频道目录」不重复不冲突，订阅与创建两条路径清晰；② 未订阅任何官方频道的用户点「创建房间」被正确引导；③ 420px 移动视图下创建流程表单不横向溢出、父频道下拉可完整操作；④ 挂靠关系在房间页、RoomSwitcher、搜索结果三处展示一致。

### 31.8 排期与合规增量

| 阶段 | 内容 | 增量 |
|---|---|---|
| G0（0.5 天） | 导航更名 + 入口迁移 + 创建流程（选父频道 / 房间名 / 类型 / 版权确认） | 无新表、无新合规项 |
| G1（1 天） | `parent_channel_id` 列 + `trg_room_parent` 触发器 + `GET /me/rooms` 返回父频道 + 创建接口校验 | 服务端归属校验 |
| 回归（0.5 天） | 六道门禁 + 新增断言 + 三份原型深浅 / 420px / 读屏 | — |

**合规增量**：挂靠官方频道**不改变**房间的「被动托管」地位（§22.3）——房间仍不进推荐流、不变现、不托管正片；挂靠只是组织维度的 UI 与数据关系，不构成「平台组织、推广用户上传版权作品」。`parent_channel_id` 属于频道级结构数据，不引入新的个人数据字段，UK GDPR / DSA 披露不变。

### 31.9 常见坑

1. **把「添加频道」直接删掉** → 用户无法订阅官方频道，也就无法建房间；订阅动作要迁到发现页，不是删除。
2. **父频道下拉列出「全部频道」而非「已加入的官方频道」** → 用户会挂到没订阅的频道，违背「自己加入的官方频道下创建」。
3. **给房间加视频文件上传控件** → 触碰 §22.3 正片托管红线；「放视频」永远是「登记元数据 + 官方外链」。
4. **父频道删除时级联删除房间** → 用户内容丢失；应 `SET NULL` + 降级提示。
5. **`parent_channel_id` 用 `CHECK` 写跨表子查询** → PostgreSQL 不支持，必须触发器。
6. **把 30 当成硬上限** → 用户诉求是「30 集电视剧」这个场景，不是「每个房间最多 30 条」；软上限是「20 个活跃房间」，不是「20 条条目」。
7. **房间挂靠后自动进官方区域包或推荐流** → 违反 §22.10 与 §30.2 红线，用户房间永不带认证、不进官方包。
8. **创建流程跳过版权确认勾选** → §22.8 要求创建房间强制勾选，勾选写 `audit_log`。

### 31.10 待裴总拍板

① 父频道下拉是否**只允许挂靠「官方频道」**（建议是；挂到别的用户房间会造成房间套房间的层级失控）；② 房间条目数是否需要软引导上限（建议 ≤200，超出提示而非硬拦）；③ 是否允许房间挂靠多个父频道（建议**否**，单父保持层级清晰）；④ 跨区域主题房间（如「港剧追剧」）通过挂靠「全球」官方频道实现，是否接受。

---

## 32. 房间轻量化：去强制类型 / 版权确认 / 挂靠，房间上频道，右上角加入与更新通知（2026-11-09 第十三轮反馈）

> 本章回答裴总第十三轮反馈：① 房间**不一定是视频**，没有类型限制；② 创建房间**没有版权确认**；③ **想创建房间就创建**，不做重流程前置；④ 房间**有内容就显示在频道里**；⑤ 房间名字**右上角 + 加入标识**；⑥ 用户感兴趣加入后，**以后有更新都会有通知**。
> **§0–§31 的业务规则大部分沿用**：三层频道、统一内容池、`channel.layout`、`collection_item`、`media_origin`、24h 下架、区域 / 法域权限矩阵、X 式帖子卡、@/#、AI 关键词、顶部搜索。本章对 §31 引入的三处**创建前置门槛做减法**，把房间从「重合规流程」回拨到「想建就建的轻量小圈子」，并新增「房间上频道目录 + 右上角加入 + 更新通知」三块增量。

### 32.1 裁决摘要

| 反馈 | 裁决 | 改动的既有规则 | 不动的红线 |
|---|---|---|---|
| 房间不一定是视频、没类型限制 | `room_type` 从「创建时强制单选」改为**可选、可空、创建后可改**；`room_type` 默认 `general`（通用圈子），用户可随时在房间设置里切换 `series / film / video / general`，仅影响 UI 形态与排序，不阻塞创建 | §23.2「`room_type` 创建时选定、创建后不可改」 | §23 原创视频托管仍需 `room_type=video` + 版权确认；「无正片上传」不变 |
| 没有版权确认 | **创建房间不再强制勾选版权确认**；版权确认下移到「发布 / 上传版权敏感内容」的具体动作（原创视频上传、外链登记），创建空房间零门槛 | §22.8 第 1 条「创建房间强制勾选版权确认」 | §23.3 原创视频上传仍强制版权确认；§22.8 通知删除 / 24h SLA / 重复侵权政策全保留 |
| 想创建就创建 | 创建房间**只要求房间名必填**；挂靠官方频道（`parent_channel_id`）、`room_type`、版权确认全部**可选**，不再有「未加入官方频道就不能建房间」的前置拦截 | §31「`parent_channel_id` 用户创建必填」「未订阅引导」 | §28.4 权限矩阵（区域与官方频道仍只能平台开）；反冒充命名规则仍保留 |
| 房间有内容就显示在频道里 | 房间一旦有 ≥1 条**已发布内容**，就作为「用户房间（小圈子）」出现在「添加 / 发现」频道的目录区（`type=room` 检索也命中）；空房间不展示、引导房主先添加内容 | §31.3「房间仅在父频道页 / 我的房间 / 搜索可见」、§22.10「房间不进推荐流」 | 房间**单集 / 外链按语仍不进「为你推荐」个性化流**；频道目录 ≠ 推荐流 |
| 房间名右上角 + 加入 | 房间卡右上角放 `CardJoinButton`（＋加入 / ✓已加入），与帖子卡、频道卡一致；未加入可一键加入，加入后进入「正在关注」时间流 | §30.2「房间不进官方区域包」（不冲突：房间在频道目录可见，但**不进官方 `channel_pack`**） | 房间永不带认证徽章、永不进官方区域包 |
| 加入后更新有通知 | 新增 `channel_notification` 通知机制：加入房间（或频道）即默认订阅「更新通知」，房主发内容 / 新集 / 新片目 / 新评论（可配置）时推给加入者；通知进全局「通知」中心 + 未读角标，用户可全局或按频道静音 | §22.10「单集 / 外链不得推送」 | 通知是**频控的摘要**（「本房间新增 N 条」），不是把每条内容 / 单集 / 外链原样 push；推送文案仍不带未授权媒体 |

### 32.2 创建房间「一步化」（本轮最核心的体验回拨）

创建房间从 §31 的两段式重流程，收敛为**一段式、仅房间名必填**：

```text
① 房间名（必填，40 字内，可后加「追更房间 / 片单 / 小圈子」后缀，但不再强制）
② 可选：挂靠官方频道（下拉，默认「不挂靠」）
③ 可选：房间类型（默认「通用」，可后改）
④ 可选：一句话按语
→ 创建（POST /rooms，仅 name 必填）
```

- **默认「不挂靠」**：`parent_channel_id` 允许为空；房间仍独立存在、可被搜索、可上频道目录。挂靠只是「额外归属线索」，不再是创建前置。
- **默认「通用」类型**：`room_type` 新增 `general` 值（默认），不预设季 / 集 / 片单 UI；用户之后在房间设置里切换到 `series / film / video` 时才启用对应编排。
- **零版权确认**：创建空房间不弹任何版权勾选；版权确认只在「上传原创视频文件」与「登记官方外链」两个动作上出现（§23.3 / §24），这是 hosting defence 的最小保留面。

> 为什么「想建就建」仍安全：空房间没有任何内容，不存在侵权面；风险出现在**内容**上，而不是**房间壳子**上。把版权确认从「建房间」挪到「发内容」这一步，既满足裴总要的轻量，又不丢 §22.8 的防线——防线跟着内容走，而不是跟着壳子走。

### 32.3 数据模型增量：`room_type` 加 `general` + `parent_channel_id` 可空 + 通知表

```sql
-- 32.3.1 room_type 增加 general（通用圈子），并放开「创建后不可改」
ALTER TYPE room_type ADD VALUE IF NOT EXISTS 'general';

-- 32.3.2 parent_channel_id 允许为空（§31 的「用户创建必填」改为可选）
-- trg_room_parent 触发器放宽：parent_channel_id 为 NULL 时直接放行（不挂靠）

-- 32.3.3 加入即订阅更新通知
CREATE TABLE channel_notification (
  id            bigserial PRIMARY KEY,
  channel_id    uuid NOT NULL REFERENCES channel(id) ON DELETE CASCADE,
  actor_id      uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,   -- 触发者（房主/协作者）
  kind          text NOT NULL CHECK (kind IN ('new_content','new_episode','new_film','new_video','new_listing','new_comment')),
  summary       varchar(200) NOT NULL,        -- 摘要，绝不带未授权媒体 URL / 文件
  content_ref   uuid REFERENCES content(id) ON DELETE SET NULL,            -- 可选：指向具体内容（不推送原文）
  created_at    timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_notif_summary CHECK (char_length(summary) BETWEEN 1 AND 200)
);
CREATE INDEX idx_channel_notif ON channel_notification (channel_id, created_at DESC);

-- 通知送达表（按用户，可静音 / 已读）
CREATE TABLE user_notification (
  id            bigserial PRIMARY KEY,
  user_id       uuid NOT NULL REFERENCES app_user(id) ON DELETE CASCADE,
  channel_notif_id bigint NOT NULL REFERENCES channel_notification(id) ON DELETE CASCADE,
  read_at       timestamptz,
  muted         boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, channel_notif_id)
);
CREATE INDEX idx_user_notif ON user_notification (user_id, read_at);
```

**规则**：① 加入房间 / 频道即默认订阅该对象的「更新通知」，`user_notification` 按加入者批量写入；② 房主发内容 → 生成一条 `channel_notification`（`summary` 为「房间 X 新增 1 条内容」），**不推送原文 / 单集 / 外链**，只给摘要 + 跳转；③ 通知**频控**：同一房间对同一用户 24h 内最多 3 条摘要（防刷屏），跨房间不叠加限制；④ 用户可全局关闭通知，或对单个房间 / 频道静音（`muted`），静音后仍可回看历史；⑤ 评论通知默认**关闭**（只对房主开「有新留言」提醒），避免小圈子被回复淹没；⑥ 通知中心展示 + 未读角标 + `aria-live` 播报，简繁双语。

### 32.4 房间上频道目录：有内容才可见

- 房间一旦有 **≥1 条 `status='published'` 的内容**（内容 / 集 / 片目 / 分类信息，任一即可），即进入「添加 / 发现」页的「用户房间（小圈子）」目录区；空房间不展示，房主房间页有「先添加内容，才能被更多人看到」的引导。
- 房间在目录里的排序：**按最近更新时间倒序**（活跃优先），非个性化、可解释；`reason` 字段标「用户自建 · 非官方」。
- 房间**仍不进「为你推荐」个性化推荐流**（§22.10 红线：具体单集 / 外链 / 按语不得被算法放大），但**频道目录 ≠ 推荐流**，两者是不同的曝光面——目录是「用户主动来挑」，推荐是「平台主动推」，前者不构成 active participant 的放大问题。
- 房间卡右上角 `CardJoinButton`：未加入显示「＋加入」，已加入显示「✓已加入」（点击退订）；加入后房间进入「正在关注」Tab 的时间流（房主发内容时以「房间新增 N 条」摘要形式出现）。

### 32.5 通知与「正在关注」的关系（与 §27.2 的衔接）

- 「正在关注」Tab 本就是时间序（§27 冻结的「非画像时间序」），加入房间后，房间的内容更新以**摘要卡片**形式进入时间流，这与频道订阅行为完全一致——房间就是「一种用户自建的频道」，§22.3 的「房间本质是 `channel` 一行」在此得到最自然的体现。
- 通知中心（`channel_notification` + `user_notification`）是**推送 / 未读角标**层面，与「正在关注」的**拉取时间流**层面分开：前者负责「我知道有更新」，后者负责「我去看更新」。
- 两类都不进「为你推荐」个性化打分（§27），也不进画像（UK GDPR / DSA Art 27 参数表不变）。

### 32.6 API 增量

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/rooms` | **仅 `name` 必填**；`parent_channel_id`、`room_type`（默认 `general`）、`description` 全部可选；去掉强制版权确认字段 |
| PATCH | `/rooms/:id` | 允许改 `room_type`（general ↔ series/film/video）、`description`；`parent_channel_id` 仍创建后不可改（§31.3） |
| GET | `/rooms/:id/notifications` | 本房间更新通知列表（摘要 + 时间 + 触发者） |
| POST | `/rooms/:id/notify-subscribe` | 加入房间（= 订阅更新通知，默认动作） |
| DELETE | `/rooms/:id/notify-subscribe` | 静音本房间通知（不退出加入） |
| GET | `/me/notifications?cursor=` | 全局通知中心（聚合 `user_notification`，未读计数） |
| PATCH | `/me/notifications/:id/read` | 标记单条已读 |
| POST | `/me/notifications/read-all` | 全部已读 |

### 32.7 界面变更清单

| 文件 | 版本 | 变更 |
|---|---|---|
| `prototype-x-style.html` | **v9** | 创建房间表单收敛为「房间名（必填）+ 可选挂靠 / 可选类型 / 可选按语」一步式，去掉强制版权确认；「添加」Tab 新增「用户房间（小圈子）」目录区，只列**有内容**的房间，房间卡右上角 `CardJoinButton`；加入房间后顶部通知未读角标 +1（模拟「房间新增内容」通知） |
| `prototype-collection-room.html` | **v6** | 新建房间表单去掉强制类型下拉（类型改为创建后可选，默认「通用」）与强制版权确认（仅房间名必填）；房间头新增「更新通知」开关（开/关）与「最近更新」时间；原创视频上传仍保留版权确认勾选 |
| `design-system/MASTER.md` / `preview.html` | **v1.7 / 第 14 节** | 新增 §20 组件规范：`RoomCreateForm`（一步式）/ `RoomDirectoryCard`（右上角加入）/ `UpdateNotifyToggle` / `NotificationCenter`；修订 §19 创建流程为「可选项」，不再强制 |

### 32.8 验收与门禁

在 §30.10 / §31.7 的六道门禁基础上，`check-rooms.js` 改写断言：

```bash
python design-system/check-contrast.py
node  design-system/check-ui.js
node  design-system/check-global.js
node  design-system/check-media.js
node  design-system/check-location.js
node  design-system/check-rooms.js     # 本章改写：去强制类型/版权确认 + 房间上频道 + 右上角加入 + 通知
```

`check-rooms.js` 新断言：① 创建房间表单**仅房间名必填**，无强制类型单选、无强制版权确认勾选、无「未加入官方频道则禁用」拦截；② 房间目录区只列 `status='published'` 且 ≥1 条内容的房间，空房间不展示；③ 房间卡右上角有 `CardJoinButton`（＋加入 / ✓已加入）；④ 加入房间后通知未读角标 +1，存在「房间新增内容」通知摘要；⑤ 通知摘要不含原文 / 外链 / 未授权媒体；⑥ 房间数据 `room_type` 默认 `general`、`parent_channel_id` 可空；⑦ 动态 HTML 标签平衡。

**人工断言**：① 创建房间从「选父频道 + 类型 + 版权确认」三步收敛为「填名字」一步，新用户 10 秒内可建房间；② 空房间不污染频道目录，有内容后自动出现；③ 420px 下房间卡右上角加入按钮完整、不遮挡房间名；④ 通知中心未读计数正确、可按房间静音；⑤ 深浅色 / 移动视图 / 读屏走查无重叠。

### 32.9 排期与合规增量

| 阶段 | 内容 | 增量 |
|---|---|---|
| G0（0.5 天） | 创建房间表单一步化 + 房间目录区 + 右上角加入 | 无新表、无新合规项 |
| G1（1–2 天） | `room_type` 加 `general` + `parent_channel_id` 可空 + `channel_notification` / `user_notification` DDL + 触发器 + 频控 + 通知中心 API | 通知频控与静音 |
| 法务（0.5 天） | 复核「版权确认下移到内容动作」不削弱 hosting defence；补通知机制的 UK GDPR（通知属于「履行合同/合法利益」的 LIA 记录） | 不重做 §13，只追加变更记录 |
| 回归（0.5 天） | 六道门禁 + 三份原型深浅 / 420px / 读屏 | — |

**合规增量**：① **版权确认下移到内容动作**（原创视频上传 / 外链登记）仍是 §22.8 hosting defence 的完整保留面——空房间无内容即无侵权面，防线跟着内容走更精确；② **房间上「频道目录」≠ 进「推荐流」**，前者是用户主动浏览、后者是平台主动放大，§22.3 active participant 红线不因此触发；③ 通知是**频控摘要**，不推送原文 / 单集 / 外链，§22.10「单集 / 外链不得推送」依旧成立；④ 通知不接推荐打分、不进画像，DSA Art 27 参数表与 UK GDPR 披露不变。

### 32.10 常见坑

1. **把「去版权确认」理解成「去版权红线」** → 大错；版权确认只是从「建房间」挪到「发内容」，原创视频上传、外链登记仍要确认，通知删除 / 24h SLA 一条不减。
2. **房间一建好就进「为你推荐」个性化流** → 触碰 §22.10 active participant 红线；房间只能上「频道目录」（主动浏览面），不能进「推荐流」（被动放大面）。
3. **空房间也上频道目录** → 目录被零内容的壳子刷屏，且 SEO 垃圾房泛滥；必须 `status='published'` 且 ≥1 条内容才可见。
4. **通知把每条内容 / 单集 / 外链原样 push** → 变成「平台推广用户上传版权作品」，且刷屏；通知必须是频控摘要，不带原文与媒体 URL。
5. **把 `room_type` 改回「创建后不可改」** → 用户想建就建后被类型卡死；类型应是「后设的编排选项」，不是「创建前置」。
6. **通知默认全开（含评论）** → 小圈子被回复淹没，用户秒退订；评论通知默认关，只对房主开「新留言」。
7. **`parent_channel_id` 仍强制必填** → 想建就建的体验没落地；挂靠应是可选线索，不是拦截。
8. **房间卡右上角加入按钮与频道名重叠 / 420px 被挤出** → 复用 §29 的 `CardJoinButton` 规范（≥44px 命中、`flex-shrink:0`、移动端收字号）。

## 33. 国家法域开通范围与发帖城市话题（2026-11-10）

### 33.1 法域开通以国家为单位

- 官方服务是否开通，以 `jurisdiction` 国家法域配置为唯一范围；一个国家法域完成风险评估并启用后，其境内所有城市均处于该法域官方服务范围。
- 用户定位到该国任一城市时，该国家法域的官方频道仍属于可见范围；城市级内容组织不能把官方可用范围缩回单一城市。
- 城市是频道和内容的细分维度，不得再创建「伦敦已开、曼彻斯特未开」一类城市级官方开通开关。城市包可作为默认展示或运营编排，但不能缩小国家法域已启用的服务范围。
- 用户定位到城市时，先由城市映射到所属国家法域，再按该国家法域的开通状态判定官方频道资格；定位本身仍不得启用法域或官方频道。

### 33.2 发布时自动城市话题

- 用户明确确认粗粒度定位后，发帖编辑器预填定位城市话题，例如英国伦敦为 `#伦敦`、日本东京为 `#东京`。
- 城市话题在发布前可移除；用户手动添加了同名话题时去重。该话题进入帖子标签，可用于公开检索和内容分类。
- 定位关闭、拒绝或尚未确认时，不自动添加城市话题；不申请 GPS，不保存 IP 原文或经纬度。
- 城市话题只表达用户当前选择的城市标签，不作为精确位置证明，不影响法域开通、官方频道权限或推荐画像。

### 33.3 频道目录按国家展示与分类

- 频道目录的地区筛选与国家分组只显示国家法域名称（如「英国」）；城市可以放在国家之后作为较弱的内容提示（如「英国 · 伦敦」），不再作为目录的主地区或开通边界。
- 面向全国的频道使用全国范围名称与描述，例如「英国租房」「英国兼职」；租房与招聘信息可以另按帖子城市筛选，不能把频道本身限制为伦敦。
- 频道目录提供七类筛选：**房产、招聘、市场、生活、交流、活动、其他**。城市提示和城市话题不替代频道分类。
- 「发现」范围依次为「全部频道、国际、当前国家（仅当它已开通）」；未确认定位时默认共享的「国际」，确认定位到已开通国家后默认选中该国。（2026-11-11 §36：国家选项只列当前国家，不再列出所有已开通国家，避免跨国浏览别国分类数据。）
- 选择「国际」时，分类仅从国际频道生成，国际频道对所有用户共享；选择单个国家时，只显示该国的频道，并只从该国频道生成分类。选择「全部频道」时按国际和国家分组展示，不显示跨国家混合的分类筛选。
- 国家范围选项仅由平台已开通的国家法域配置生成。定位到未开通国家时不创建或暗示该国已有官方数据，默认回到国际范围；该国开通并配置数据后，定位会自动使用对应国家范围。

### 33.4 官方分类、频道详情与房间来源标识

- 官方分类由平台维护（房产、招聘、市场、生活、交流、活动、其他）；用户端没有新增、删除或改名分类的入口。创建房间必须从官方分类中选择一个分类，服务端也要校验分类 ID 有效。
- ~~房间必须从平台官方分类中选择分类；可选关联一个同分类的官方频道。~~（2026-11-11 由 §36.5 覆盖：所属频道必填，分类随所属频道继承。）房间必须从平台官方分类中选择分类；可选关联一个同分类的官方频道。从频道详情发起创建时，自动带入频道及分类。房间帖子在关联频道详情中展示；未关联频道的房间按分类进入目录。
- 频道详情先展示频道简介、分类和订阅状态，其后展示该频道下的用户房间，再展示频道动态。房间内容卡明确显示「来自房间」、房间名称和作者；房间名称可进入房间，卡片提供「加入房间」操作。加入后按钮状态即时显示「已加入」。
- 用户房间帖子可以进入其关联频道的详情页，但不进入「为你推荐」个性化流；官方频道内容继续保留原有来源与认证标识。

### 32.11 待裴总拍板

① 房间类型默认「通用（general）」是否接受（建议是；用户之后可自选剧集 / 电影 / 视频形态）；② 通知频控「同一房间 24h 内最多 3 条摘要」是否合适（建议 3，可调）；③ 评论通知默认关闭、只房主开「新留言」是否接受（建议是，控噪）；④ 房间上频道目录但不进「为你推荐」个性化流，这层区分是否清楚（建议清楚，这是 §22.10 红线的关键）；⑤ 前几轮遗留项仍见 §28.12 ④、§29.13、§30.13、§31.10。


## 34. 官方频道与用户房间层级（2026-11-10）

### 34.1 顶层与子级

- 平台创建的国家频道和国际频道是频道目录的顶层对象。官方频道之间可以并列展示。
- 用户创建的房间必须选择平台维护的官方分类；可选归属同分类官方频道。房间不得以频道卡片的同级对象出现在频道组合包或官方频道列表中。
- 用户房间只能在所属频道的详情页内呈现；房间帖子留在房间内，不自动混入父频道动态或推荐流。只有已发布至少一条内容的房间对其他用户可见；房主可在自己的频道详情中看到空房间。
- 房间不可再创建子房间。用户房间与频道是不同层级和不同类型的数据对象。

### 34.2 创建、导航与发现

- ~~创建房间时，房间名与官方分类必填，所属官方频道可选~~（2026-11-11 由 §36.5 覆盖：房间名与所属频道必填，分类自动继承）；从频道详情创建时预选当前频道及其分类。
- 从频道详情页发起创建时，所属频道预选当前频道。创建成功后返回该频道详情。
- 频道详情页提供「这个频道里的用户房间」区，显示有已发布内容的房间卡、加入状态和创建入口。
- 房间页显示所属频道链接，点击后回到对应频道详情；从其他入口打开房间时也使用同一链接。
- 顶层目录只展示频道。搜索结果若匹配房间，应以所属频道为导航入口，不创建独立的顶层房间结果卡。

### 34.3 数据与历史规则裁决

- ~~`user_room.category_id` 必须引用平台维护的官方分类；`parent_channel_id` 可空~~（2026-11-11 由 §36.5 覆盖：`parent_channel_id` NOT NULL，`category_id` 由服务端从父频道写入）。房间类型仍可默认为 `general`。
- ~~本条分类规则覆盖旧版本中“房间必须归属官方频道”的创建约束~~（2026-11-11 作废：所属频道恢复必填，见 §36.5）；频道详情发起创建仍自动挂靠当前频道。
- `parent_channel_id` 不进入官方频道包；房间不获得官方认证，也不参与频道级推荐排序。
- 本章明确覆盖 §31 与 §32 中关于房间可不挂靠、房间可独立出现在目录或「房间上频道目录」的相反规定。§32 的房间通知、内容审核、空房间创建和媒体规则继续有效。
- 原型使用页面内存模拟数据，不代表服务端持久化已实现。

## 35. 导航名称调整（2026-11-10）

- 主导航、首页 Tab、添加页里的创建分段与底部入口中原「创建房间」入口统一显示为「频道」，点击行为仍进入频道目录与房间创建流程。
- 原「我的频道」个人入口统一显示为「我的房间」，涵盖侧栏导航、个人空间页标题及发帖目标选项。
- 「我的房间」只列出当前用户自己创建的房间，并提供进入房间 / 创建房间入口；已收藏的频道不显示在此页。
- 「收藏」页新增「频道」分类，展示用户收藏（订阅）的频道；频道卡继续使用现有频道卡样式和取消收藏操作。
- 名称调整只影响界面文案与无障碍标签；底层订阅频道、创建用户房间、内容归属和 API 语义保持既有定义。实际提交动作保留「创建房间」动词，避免「频道」单独作为提交按钮时语义不清。

## 36. 国际化三层模型与房间所属频道（2026-11-11 · 最高优先）

> 裴总 2026-11-11 拍板：「我还是倾向于这是一款国际化的 app。开通国家分类数据独立，但是国际频道是共享的数据。」本章是产品定位与数据边界的最高优先口径，覆盖 §0.1、§26.1 ②、§26.2 冷启动段、§28 中「区域包叠加」、§33.3 发现范围、§33.4 与 §34 中「所属频道可选」的表述。

### 36.1 定位

- 本产品是**国际化中文频道社区**，不是某国本地生活站。v1.0 的「英国本地生活信息站」表述作废。
- 英国（UK）是第一个开通国家，首城伦敦。英国的租房、二手、招聘等分类频道只属于英国。
- 「国际」是 `region_code='GLOBAL'` 的显示名。2026-11-11 裴总确认：频道名里指代跨国共享频道的「全球」统一改为「国际」（如「全球华人交流」→「国际华人交流」、「全球华人求职」→「国际华人求职」）；一般叙述（如「全球布局」「全球合规」「全球上架」）不改。

### 36.2 三层模型

| 层 | 是什么 | 数据范围 | 谁能看到 |
|---|---|---|---|
| ① 国际共享频道 | `region_code='GLOBAL'` 的频道（影视、体育、国际华人交流等） | **全平台一份数据**，各国用户读写同一份帖子、评论与房间 | 所有用户，任何国家、包括未定位与未开通国家 |
| ② 开通国家分类频道 | `region_code=<已开通国家>` 的频道（英国租房、英国二手、英国招聘等），按七类官方分类组织 | **每个开通国家独立一份**，国家之间不共享、不合并、不互相推荐 | 当前国家等于该国的用户 |
| ③ 房间 | 用户在 ① 或 ② 的某个频道下创建的小圈子 | 跟随所属频道：挂国际频道的房间各国共享；挂国家频道的房间只属于该国 | 同所属频道 |

### 36.3 数据隔离规则（服务端强制，前端只做呈现）

1. 所有国家分类数据的读接口（频道列表、频道详情、帖子流、房间、搜索、趋势、通知）都必须带服务端解析出的 `current_country`，并按 `channel.region_code IN ('GLOBAL', current_country)` 且 `current_country` 已开通过滤。前端传来的国家参数只能缩小范围，不能扩大。
2. `current_country` 单选，不叠加。来源优先级沿用 §28.2：已保存的明确选择 → 粗粒度定位 → 系统地区；定位关闭或无法判定时为空，只看国际。
3. 未开通国家：没有国家分类数据，不显示、不创建、不暗示该国已有官方数据；用户只看到国际频道。
4. 切换国家时，用户在旧国家的订阅、收藏、已加入房间、我创建的房间**保留但暂停显示**，界面提示「另有 N 个属于其他国家，切回后恢复」；切回后原样恢复。不得把旧国家数据并入新国家，也不得在新国家里推荐旧国家内容。
5. 国际频道在任何国家看到的是**同一份内容**；不得按国家改写、筛掉或重新排序国际频道的帖子（个人屏蔽与审核除外）。
6. 深链或搜索命中其他国家的频道、房间或帖子时，返回「属于 X 国频道，当前国家不显示」的占位，不返回正文。
7. 合规与审核按所属频道的法域执行：国际频道走平台通用审核策略；国家频道走该国法域策略（§26.5）。

### 36.4 不同国家下首页与「发现」显示什么

| 场景 | 首页（为你推荐 / 正在关注） | 发现与频道目录 | 创建房间可选的所属频道 |
|---|---|---|---|
| 当前国家 = 英国（已开通） | 国际频道 + 英国分类频道的内容 | 「全部 / 国际 / 英国」三个范围；目录分「国际」「英国」两组 | 国际频道 + 英国频道中允许建房的频道 |
| 当前国家 = 日本等未开通国家 | 只有国际频道内容 | 只有「国际」范围；目录只列国际频道 | 只有国际频道 |
| 定位关闭 / 未定位 | 只有国际频道内容 | 同上 | 同上 |

- 区分「国际」与「英国」放在**频道层**表达：频道目录分组标题、频道行的区域标识、频道详情标题旁的「国际 · 各国共享」或「英国频道 · 仅英国」标签。内容卡片不加区域徽章（MASTER §17）。
- 顶部区域栏显示「当前国家」单个 chip 与常驻「国际频道 · 共享」标识，不再显示可叠加的区域集合。

### 36.5 房间所属频道规则（覆盖 §34.2 / §34.3 中的可选挂靠）

1. **创建房间时「所属频道」必填。**
2. **房间只能挂在已开通国家的官方频道或平台共建频道下，或挂在国际频道下。** 不能挂在未开通国家，也不能挂在其他用户的房间下。房间名与简介进入审核，审核通过前仅房主可见。
3. 房间的国家范围由所属频道决定（`user_room.region_code` 冗余存储并与父频道保持一致），见 §36.2 ③。
4. 数据：`user_room.parent_channel_id` 改为 NOT NULL，引用 `can_host_rooms=true` 且 `region_code IN ('GLOBAL', 已开通国家)` 的频道；服务端拒绝未开通国家或不可建房的频道。
5. **分类跟随所属频道（2026-11-11 裴总定稿）。** 用户不再单独选分类，`user_room.category_id` 由服务端写入父频道的分类，客户端只显示继承结果。目录分类、七类筛选与审核路由都不受影响，也不会出现「分类与所属频道不一致」的校验错误。若以后要在同一频道下细分，用可选的房间标签，不用分类字段承担。
6. **帖子分类同样跟随发布目标，不提供选择。** 发到房间 = 房间所属频道的分类；投稿到频道 = 该频道的分类；发到「我的动态」不归入分类。`content.category_id` 由服务端按目标写入，客户端传来的分类一律忽略。发布页原有的「生活 / 租房 / 求职 / 求助」四类作废，统一使用七类官方分类（房产、招聘、市场、生活、交流、活动、其他）；旧数据映射为 生活→生活、租房→房产、求职→招聘、求助→其他。

### 36.6 定位与国家切换

- 定位只决定「当前国家」，**不会启用任何法域的官方频道**（§28 原则不变）。确认定位后不再自动覆盖，用户可在设置里手动切换国家（单选）。
- 切换到未开通国家：提示「该国未开通，只显示国际频道」；切回已开通国家：恢复该国分类数据与之前的订阅。
- 移除当前国家等同于定位关闭：只看国际频道。
- **允许手动切换当前国家（2026-11-11 裴总确认）。** 用户可在设置里把当前国家切到任意已开通国家，不要求与定位一致；例如人在日本，可以切到英国看英国的分类频道。手动选择记为「已保存的明确选择」，优先级最高，之后定位不再自动覆盖；切到未开通国家时同样只显示国际频道。手动切换不改变法域合规归属的判定（§26.3），也不启用任何法域的官方频道。
- 埋点：`country_switch {from, to, launched, source: manual|location}`；不记录精确位置。

### 36.8 发帖入口：手机端只保留 + FAB（2026-11-11）

- **手机端（移动断点，≤760px）不在内容流里嵌发帖框**，首页及其他页面的发帖只走右下角 + FAB 一个入口；桌面端保留首页内嵌发帖框。
- FAB 必须覆盖原内嵌框的全部场景：发到我的动态或自己的房间、图文 / 视频 / 话题 / 信息四种类型、话题、确认定位后的城市话题（预填、可移除）、视频原创确认。
- FAB 带上下文：在房间内点 + 预选当前房间（已加入或房主）；在频道详情内点 + 预选「投稿到该频道」；分类按 §36.5 ⑥ 跟随目标显示。
- 游客点 + 先走三屏轻注册，完成后进入发布页。

### 36.7 原型对应（H5 演示，无后端）

- 共享层 `UKCN.country()` / `setCountry()` / `regionVisible()` 保存当前国家；主页、房间页、发布页三页一致。
- 主页：切到未开通国家后，推荐、关注、发现、目录、趋势、建房可选频道都只剩国际频道；切回英国恢复。国际频道在不同国家下内容一致。
- 房间页：所属频道属于其他国家时显示占位提示，拦下加入、发帖与留言。发布页：发布目标只列当前国家可见的房间。
- 门禁：`check-location.js` 新增「F. 国家数据隔离 + 国际共享」断言；`check-global.js`、`check-flow.js` 同步改为单选国家模型。
- 2026-11-11 第二轮：手机端去掉内嵌发帖框（`check-ui.js` 与 `_flow.py` 断言手机端不可见、桌面端可见）；建房表单与发布页的分类改为只读继承；频道名「全球…」改「国际…」。

### 36.9 H5 流程补齐：分类信息、AI 关键词、未读分隔线、简繁（2026-11-11 · 补充，不改既有规则）

1. **分类信息（租房 / 二手 / 招聘）**沿用 §8 `listing_ext` 与 §22.9，补充：
   - `listing_ext.attrs jsonb`：按类别的结构化字段。租房 `roomType` / `moveIn` / `bills`（包含 / 不含 / 部分包含）/ `deposit` / `minTerm`；二手 `condition` / `pickup`；招聘 `jobType` / `hours` / `rightToWork`。`price_unit` 取值扩展：租房 月 / 周，招聘 小时 / 月 / 年，二手为空。服务端按 `category` 校验 `attrs` 的键，未知键丢弃。
   - 类别不由用户选：发布页按发布目标的分类决定（房产 → 租房，市场 → 二手，招聘 → 招聘，§36.5 ⑥），价格与区域必填，`expires_at` 仍为发布后 30 天。
   - **联系方式**：列表与详情只给打码示例；`POST /listings/:id/contact` 需登录（游客先三屏轻注册，完成后才返回明文）并写审计；过期信息不返回联系方式。
   - **国家隔离**：分类信息跟随所属频道的国家（§36.3），不跨国；深链打开其他国家的信息返回占位，不返回字段与联系方式。
   - **不进推荐**（§27.4 `chk_listing_no_rec` 不变）：「为你推荐」不出现；频道详情显示该频道的分类信息；「发现」不做个性化，可在内容流之外以**单独分区**展示当前开通国家、未过期的分类信息（最多 4 条），不混入内容流。
2. **AI 自动关键词**按 §30.6 执行。H5 演示用本地受控词表代替模型（共享层 `UKCN.aiKeywords()`），规则不变：用户填 0 个才触发、最多 5 个、每个 ≤12 字、只读标题 + 正文 + 分类、标「AI 建议，可删」、可删、不阻塞发布、`source = ai_auto`。定位得到的城市话题单独存放，不算用户关键词。
3. **「正在关注」未读分隔线（US-03）**：客户端记录该用户上次看到「正在关注」的时间（正式版存服务端 `user_feed_cursor`），进入时按此时间在第一条更早的非置顶内容前插「以下为上次看过」，不改变排序。
4. **繁体（US-11）**：界面文案全站随偏好切换（账号 `lang`；游客本地偏好）；用户内容不在原型中转换，正式版按 US-11 只在显示层转换，原文不改写。
5. 原型与门禁：`prototype-x-style.html`（分类信息卡片 / 详情 / 发现分区 / 未读分隔线 / 简繁）、`publish-content.html`（结构化表单 / AI 关键词）、房间页删除旧的就地建房表单；新增门禁 `check-h5.js`（联系方式需登录、分类信息不跨国、AI 关键词 ≤5、简繁切换、未读分隔线），`gen-hant.py --check` 校验转换表。

### 36.10 发现页头部瘦身（2026-11-11 · Rio 批准，只改呈现）

- 发现页去掉登录状态条；「游客预览 / 退出登录」开关移到「我的 · 设置」，功能不变。游客在发现页只保留一行内的「访客浏览」提示。
- 地区范围与分类合成一行横滑 chip（地区在前，细分隔线，分类在后），不换行，不撑出页面，触控高度 44px。
- 范围说明只在首次进入显示一次，可关闭，记在本地共享存储；之后只保留一行元信息（范围标题 · 近期更新 N 条 · 不进画像）。
- 目标与实测：390×844 首条内容顶部 ≤260px（实测 157px，游客 175px）。§33.3 的地区与分类作用域规则、§36.4 的显示规则不变。门禁 `check-h5.js` [G] 覆盖。

### 36.11 「频道」与「发现」保持分开（2026-11-11 · Rio 拍板）

- 移动端底栏保持 5 项：首页 / 频道 / 发现 / 通知 / 我的，不合并。
- 分工：「频道」= 频道目录、关注、在频道下建房间；「发现」= 按地区 / 分类浏览近期内容（不进画像，§33.3）。两者互相有入口（发现里的「进频道」、频道目录里的频道详情），不重复做同一件事。
- 原型无需改动；`CHANGES.md` 第六节第 4 项关闭。

### 36.12 移动端正文字号 15px（2026-11-11 · Rio 拍板）

- 移动端（≤760px）帖子正文（信息流卡片、频道帖子、房间帖子、留言、发布页信息流）**15px、行高 1.5**，与 X 一致，一屏多看一些内容。
- 不变：标题、按钮、Tab、徽章字号与字重；触控目标 ≥44px；正文对比 ≥4.5:1。输入框与 textarea 保持 ≥16px，避免 iOS Safari 聚焦时放大页面。
- 覆盖：§21 / §23.7 中「移动端正文 16px」的表述以本节为准；MASTER v2.3 §3.2 与 `tokens.css`（`--fs-body-mobile` / `--lh-body-mobile`）同步。

### 36.13 房间帖子默认不进频道动态，房主可「推到频道」（2026-11-11 · Rio 拍板）

1. **默认**：房间里的帖子只在房间内显示，不进所属频道的「频道动态」，也不进「为你推荐」「正在关注」「发现」（norec 不变）。覆盖此前「审核通过的房间帖子出现在所属频道详情」的做法。
2. **推到频道**：房主可以对单条**已公开**的房间帖子点「推到频道」，该帖子出现在所属频道详情的「频道动态」，标「来自房间 · 房间名」，点按打开房间（未加入可直接加入）。房主可随时「撤回推送」。平台管理员可在后台撤回（原型不做此角色）。审核中 / 未通过的帖子不能推。
3. **约束**：推送不改变帖子的国家归属，频道不可见（其他国家 / 未开通 / 定位关闭）时推送帖子同样不可见；原帖删除或下架即自动消失；推送不触发通知、不进推荐。
4. **数据**：建议表 `room_post_push(post_id PK, room_id, channel_id, pushed_by, pushed_at)`；`pushed_by` 必须是该房间房主（服务端校验）；撤回即删行并写审计。原型存共享演示数据 `pushes`。
5. 门禁：`check-h5.js` [H]（默认不进频道、只有房主能推、推送出现在频道并带来源房间、撤回、国家隔离、norec）；`_flow.py` 端到端覆盖。

### 36.14 产品名「海外圈」（2026-11-11 · Rio 拍板）

1. **产品名**：对用户展示的产品名统一为「**海外圈**」（简繁同形），替代「全球中文频道社区」与英文展示名「CN Channels」。
2. **范围**：页面 `<title>`、左侧品牌栏（logo 字「海」+ 产品名）、手机端首页标题位（X 式品牌头，桌面仍显示「首页」）、登录 / 注册弹窗标题（「登录或注册海外圈」）、欢迎通知、编辑署名（「海外圈编辑」）、房间封面水印（「海外圈 · XXX ROOM」）、设计系统展示页。上线时应用名、PWA manifest（`name` / `short_name`）、`application-name` / `apple-mobile-web-app-title`、分享卡片 `og:site_name`、短信 / 邮件签名同样使用「海外圈」（原型暂无 manifest 与 meta）。
3. **不改**：频道层级用语（「国际」频道、国际华人交流等）与表示范围的「全球」（全球合规、全球上架等）不是产品名，保持原样；内部代号 `UKCN` / CN Channels（代码标识、存储 key `ukcn.demo.v1`、门禁脚本名、文件名）不对用户展示，不改；§36 正文「国际化中文频道社区」是产品定位描述，不是名称，保留；历史记录（§36 决策原文、v1.0 文档、memory）保留原貌。
4. 门禁：`check-h5.js` [I]（三页与展示页无旧名、标题与品牌栏为新名、繁体下名称不变、无「海外社区」）；`_flow.py` 端到端检查首页与登录弹窗显示「海外圈」、界面无旧名。

### 36.15 方便实用的界面优化（2026-11-11 · Rio：「UI 再帮我优化方便实用的」）

只改交互细节，不改布局、命名与既有拍板（底栏 5 项、频道与发现分开、正文 15px、房间帖子默认不进频道、+ FAB 唯一发帖入口、「国际」命名、产品名海外圈、房间必选所属频道）。

1. **喜欢可用**：帖子卡、频道帖子、推送的房间帖子、房间帖子都能点喜欢，状态按账号保存，各页面一致；游客先轻注册。
2. **分享可用**：调起系统分享面板；不支持时复制链接并提示。
3. **收藏状态不丢**：收藏后刷新或切页，图标仍显示已收藏（原来重新渲染会丢失高亮）。
4. **滚动位置记忆**：切底栏或首页 Tab 再回来，停在原来看到的位置；再点一次当前底栏项回到顶部。
5. **详情返回来处**：从首页进频道详情或分类信息，点「返回」回到首页原位置（原来会停在发现页顶部）。
6. **手机端顶栏下滑收起**：首页与房间页下滑时收起顶栏，多出约 156px 内容区，上滑立即出现。
7. **发布草稿自动保存**：写到一半离开，回来自动恢复，可一键清空；发布成功后自动删除。服务端建议：草稿只存在本机（localStorage / IndexedDB），不上传。
8. **桌面「/」聚焦搜索**，Esc 退出。
9. 门禁：`check-h5.js` [J]；`_flow.py` v2.5 段端到端覆盖。

### 36.16 站内信 / 私信（2026-11-11 · Rio 批准）

在不改既有拍板的前提下（底栏 5 项、频道与发现分开、正文 15px、房间帖子默认不进频道、+ FAB 唯一发帖入口、「国际」命名、产品名海外圈、房间必选所属频道），新增用户之间的私信。

1. **底栏「通知」改名「消息」**，仍是 5 项（首页 / 频道 / 发现 / 消息 / 我的），桌面左栏同步。内部页面标识 `notifications` 不改。「消息」页顶部分段「私信 / 通知」，默认「私信」；原有通知全部放在「通知」分段，功能不变。分段各显示未读数。
2. **角标**：底栏与左栏「消息」角标 = 未读私信（含消息请求）+ 未读通知。
3. **入口**：帖子作者名旁一个小「私信」按钮（不放进回复 / 喜欢 / 分享主操作行；自己的帖子不显示）；点作者名进入个人主页，主页有「关注 / 私信 / 拉黑 / 举报」。房间页帖子同样有作者主页与「私信」入口，跳到首页原型的会话。
4. **消息请求**：不是我关注的人第一次私信我，先进「消息请求」。接受前不能回复，对方也看不到我是否看过；可以接受、删除（先确认，删除不通知对方），或在会话里拉黑。
5. **拉黑与举报**：每个会话头部都有「拉黑」（先确认）和「举报」（走统一举报流程，类型「私信」）。拉黑后对方不能私信我、我也看不到与对方的会话，对方不会收到通知；在「我的 · 设置 · 私信」可解除。
6. **陌生人私信开关**：「我的 · 设置 · 私信」里「陌生人私信 允许 / 关闭」，默认允许。关闭后只接收我关注的人的私信，陌生人的私信不送达（不进消息请求）。
7. **v1 范围**：只支持文字（最多 1000 字）和图片；没有已读回执、没有语音、没有群聊。手机端会话中隐藏 + 按钮，输入框固定在底栏上方，发送按钮 ≥44px，气泡正文 15px / 1.5。
8. **游客**：点「私信」先弹登录 / 注册，完成后直接进入与对方的会话（与「喜欢」相同的续上模式）；游客看「消息」页只显示登录引导，角标为 0。
9. **数据（演示）**：会话、关注、拉黑、开关都存在 UKCN 共享层（`dms` / `follows` / `blocked` / `dmPrefs`），三个原型页共用；示例有 2 个会话和 2 条消息请求。页面用 12px 次要色小字标注「真实发送需要后端」。「我的 · 演示工具」有「模拟陌生人发来私信」。
10. **服务端建议**：`dm_thread(id, a, b, status: request|active, created_at)`、`dm_message(id, thread_id, from, kind: text|image, body, image_key, created_at)`、`user_block(user, target)`、`user_pref.dm_allow_strangers`。投递前按「拉黑 → 是否关注 → 陌生人开关」判定；图片走与帖子相同的审核与存储；举报附会话 ID 与最近消息快照；导出数据包含私信文字（图片只标类型，不含原图）；删除账号同时删除会话。
11. URL：`?page=notifications&msg=notif` 打开通知分段；`&dm=@handle` 直接打开会话（游客先登录）；`?user=@handle` 打开个人主页。
12. 门禁：`check-h5.js` [K]；`_flow.py` v2.6 段端到端覆盖（含游客续上与桌面）。

### 36.17 核心业务逻辑与交互闭环优化（2026-11-12）

针对 v1.1 既有逻辑在实测与场景复盘中发现的 6 处业务与交互盲区，进行系统性闭环设计。**保持既有基础架构不变**（底栏 5 项、频道与发现分开、正文 15px、房间必选所属频道、产品名海外圈）：

1. **已加入房间内容聚合进「正在关注」流（消除社群孤岛）**
   - **规则**：用户加入房间（`roomsJoined`）后，该房间内所有**已通过审核（published）的公开帖子**，自动以**严格时间倒序**聚合进入首页「正在关注」流。
   - **呈现**：帖子卡片顶部明确标注文案：`来自已加入的房间 · [房间名]`，点击房间名可直接跳转进入该房间；卡片右上角为「收藏」与「分享」，不显示频道「关注」按钮。
   - **静音支持**：若用户在房间内开启「静音更新」，则该房间帖子不进入「正在关注」流，仅保留在房间内。
   - **排序**：与频道官方帖子共享时间倒序队列，置顶公告依然绝对优先排在最前。

2. **分类信息（租房/二手/招聘）全生命周期闭环**
   - **发布者手动下架**：作者本人在分类信息卡片或详情页可点击「标记已租出」（租房类）或「标记已售出」（二手类）或「下架」；操作后写入 `listingsClosed[postId] = { reason, ts, by }`。
   - **下架呈现**：卡片与详情页展示半透明置灰与状态印章：`[已租出]` / `[已售出]` / `[已下架]`；立即关闭「查看联系方式」入口并提示「该信息已结案，联系方式已关闭」；同时移出发现页与频道动态。
   - **一键刷新（延期）**：对于快到期（剩 ≤3 天）或已过期但未租出的房源，作者本人可见「刷新有效期」按钮；点击后将 `ts` 重置为当前时间，清除下架标记，重新获得 30 天展示期，并在列表重新按最新时间展示。

3. **分类信息交易咨询直通通道（免陌生人私信拦截）**
   - **入口**：在分类信息详情页与卡片操作行中，增设**「私信咨询房东/卖家」**专用入口。
   - **直通规则**：通过该入口发起的对话，携带 `listingInquiry: true` 与 `listingRef: { id, title, price, unit }`；**无视双方是否互相关注，直接进入房东的正式「私信」列表（status: active）**，不被丢入「消息请求」分段，发出站内高优先级未读提醒。
   - **呈现**：会话气泡顶部固定渲染迷你「房源/物品信息卡片快照」，首条消息自动附带交易意向标签，双方即刻进入免接受的双向沟通。

4. **房主「推到频道」级联失效与生命周期一致性**
   - **规则**：频道渲染推送帖子时，建立**强依赖级联校验**：动态比对原帖当前状态（`status === 'published'`）。
   - **联动失效**：若原帖进入 `deleted`（作者删除）、`rejected`（审核驳回/封禁）或 `pending`（重新编辑待审），频道的推送引用自动实时隐藏；
   - **彻底清空**：当原帖被彻底删除（`deletePost`）或审核驳回（`reject`）时，系统自动联动清空 `pushes[postId]` 映射表，彻底杜绝僵尸外链。

5. **跨国漫游与出境前浏览模式（准留学生场景）**
   - **规则**：在顶部区域条及「我的 · 设置 · 区域与定位」中，新增**「跨国漫游 / 浏览开通国家」**选项；
   - **场景适配**：当用户处于未开通地区（或未定位）时，允许主动选择「浏览国家：英国」，系统保留其原有国际频道的同时，为其开放英国频道的目录、分类信息（租房/二手）及房间的**只读浏览权限**；
   - **呈现**：页面顶栏常驻轻量漫游提示条：`正在浏览英国站（伦敦）内容 · 落地后可切为本地发布`。

6. **联系方式每日查看频控与防骗透明提示**
   - **频控上限**：引入用户维度每日查看上限：`CONTACT_DAILY_LIMIT = 5` 次/自然日（UTC/英国时间凌晨重置）；
   - **知情权与确认**：查看按钮下方明确展示剩余额度 `今日还剩 N/5 次`；点击「查看联系方式」时，弹出规范确认面板：“为防范诈骗与恶意爬取，每日最多查看 5 次联系方式。查看本条信息将消耗 1 次额度（今日剩余 N 次）。确定查看？”；
   - **额度耗尽**：达到 5 次后，按钮变灰禁用并提示“今日查看额度已用完，请明天再试”，并引导通过站内“私信咨询”继续联系房东。

## 37. 变更记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-11-12 | v1.1 + §36.17 | 核心业务逻辑与交互闭环优化：① 已加入房间帖子以时间倒序聚合进「正在关注」流并带房间来源标签；② 分类信息全生命周期闭环（房东手动标记已租出/已售出 + 刷新延期 + 状态印章）；③ 分类信息交易咨询直通通道（免陌生人私信拦截，直达正式私信并带房源快照）；④ 房主推送级联失效保障（原帖删除/下架/驳回时频道推送自动失效）；⑤ 跨国漫游浏览模式（未开通地区可主动浏览英国站，满足准留学生行前看房）；⑥ 联系方式每日查看频控（上限 5 次，剩余额度透明确认与防骗提示） |
| 2026-11-10 | v1.1 + §33 – §35 | 国家法域开通范围、城市话题、频道与房间层级、导航名称调整 |
| 2026-11-11 | v1.1 + §36 | 裴总拍板国际化定位：新增 §36 三层模型（国际共享频道 / 开通国家独立分类 / 房间）、数据隔离规则、各国首页与发现显示规则、当前国家单选切换；房间所属频道改为必填，只能挂已开通国家的官方或平台共建频道或国际频道，房间名与简介审核；分类改为从所属频道继承。作废 v1.0「英国本地生活信息站」表述、§26.1 ②「区域包可叠加」、§26.2 未开通国家 UGC 建区域频道、§33.3「已开通国家」全列、§34「所属频道可选」 |
| 2026-11-11 | v1.1 + §36 修订 | 裴总确认三项：允许在设置里手动切换当前国家（§36.6）；分类跟随所属频道定稿，帖子分类跟随发布目标，发布页旧四类作废（§36.5 ⑤⑥）；频道名「全球」统一改「国际」（§36.1）。新增 §36.8：手机端只保留 + FAB 发帖入口，桌面端保留内嵌发帖框 |
| 2026-11-11 | v1.1 + §36.9 | 补齐 H5 流程（只补充，不改既有规则）：分类信息 `listing_ext.attrs` 结构化字段、联系方式需登录并审计、不跨国、发现页单独分区；AI 关键词演示实现；「正在关注」未读分隔线；繁体界面全站切换；新增 `check-h5.js` 门禁 |
| 2026-11-11 | v1.1 + §36.10 | 发现页头部瘦身（只改呈现）：去掉登录状态条，游客预览开关移到「我的」；地区 + 分类一行横滑 chip；说明首次显示一次、可关；元信息收成一行 |
| 2026-11-11 | v1.1 + §36.11 – §36.13 | Rio 拍板三项：「频道」与「发现」保持分开（底栏 5 项）；移动端帖子正文 15px / 行高 1.5（输入框 16px）；房间帖子默认不进频道动态，房主可「推到频道」与「撤回推送」，频道里标「来自房间 · 房间名」 |
| 2026-11-11 | v1.1 + §36.14 | Rio 拍板产品名「海外圈」（简繁同形），替代「全球中文频道社区」与展示名「CN Channels」；频道层级「国际」与范围用语「全球」不改，内部代号 UKCN 不改 |
| 2026-11-11 | v1.1 + §36.15 | 方便实用的界面优化（只改交互细节）：喜欢 / 分享可用、收藏状态重渲染不丢、切页与 Tab 记住滚动位置并支持再点回顶、详情「返回」回到来处、手机端顶栏下滑收起、发布草稿自动保存、桌面「/」聚焦搜索 |
| 2026-11-11 | v1.1 + §36.16 | 站内信（Rio 批准）：底栏「通知」改名「消息」（仍 5 项），内分「私信 / 通知」，角标合计；帖子作者旁与个人主页有「私信」；陌生人首条进「消息请求」需接受；会话可拉黑、举报；「我的 · 设置」可关闭陌生人私信；v1 只有文字和图片，无已读回执、无语音；游客先登录再续上；演示数据存 UKCN 共享层，真实投递需后端 |
