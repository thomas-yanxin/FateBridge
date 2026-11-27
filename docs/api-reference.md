# FateBridge API 参考

[文档中心](README.md) · [接入指南](agent-guide.md) · [算法覆盖矩阵](algorithm-coverage.md) · [可运行示例](examples/README.md)

本文列出 FateBridge 的 REST 路由、FastMCP 工具面、共享请求族与响应约定。安装步骤见[快速入门](getting-started.md)，端到端调用代码、错误恢复全表与 Agent 闭环见[接入指南](agent-guide.md)。

OpenAPI 发布 90 个业务 REST 路由，另有 `/api/batch`（多主体多工具无状态批处理）、`/health`、`/ready`、`/metrics` 四个共享端点。目录共有 90 条记录，CLI 可执行 90 条目录命令，MCP 通过三个入口（`discover_tools`、`run_calculation`、`run_batch`）提供 90 项业务能力。字段约束以当前服务的 `/openapi.json`、MCP `discover_tools(tool=...)` 或 CLI `fatebridge discover <tool>` 为准。

## 阅读导航

| 要查什么 | 章节 |
| --- | --- |
| 接口命名、错误包络、发现与输出控制 | [公共约定](#2-公共约定) |
| 咨询禁区与范围校验 | [咨询范围与禁区校验](#咨询范围与禁区校验) |
| 输入字段与默认值 | [共享请求族](#3-共享请求族) |
| REST 路由与风水入口 | [REST 端点家族](#4-rest-端点家族) |
| 可复制 HTTP 调用 | [REST 调用示例](#5-rest-调用示例) |
| MCP 公开工具列表与差异 | [FastMCP 工具面](#6-fastmcp-工具面) |
| 常见响应字段与调试 | [常见响应字段](#7-常见响应字段) · [调试建议](#8-调试建议) |

## 1. 基础信息

- **REST**：默认地址 `http://localhost:8010`（Swagger UI `/docs`、ReDoc `/redoc`、OpenAPI `/openapi.json`、能力发现 `/api/tools`）。业务参数放入 JSON 请求体，控制项（`detail`、`fields`、`as_of`）放入 URL 查询参数（多个 `fields` 重复传参）。
- **FastMCP**：通过 `python -m fatebridge.mcp_server` 启动（默认 stdio，HTTP 部署见 [MCP 部署指南](mcp-deployment.md)）；返回原生 `structuredContent` JSON 对象，失败时设置 `isError=true`。

## 2. 公共约定

### 2.1 鉴权与错误格式

`FATEBRIDGE_API_KEYS` 为空时 REST 不鉴权；非空时需发送 `X-API-Key: <secret>`（请求头名可通过 `API_KEY_HEADER_NAME` 修改）。`/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json` 及 `OPTIONS` 免检，其余接口均受保护；MCP 与 CLI 不使用 REST API Key。

模型校验与业务错误共享统一错误包络（`error`、`error_code`、`retryable`、`issues`；完整错误码对照表见[接入指南 § 错误恢复与复现](agent-guide.md#错误恢复与复现)）：

| `error_code` | HTTP / CLI | 说明 |
| --- | --- | --- |
| `validation_error` | 400 / 422 · `1` | 字段缺失、取值非法、未知字段、无效日期（如 `birth_date`、`invalid_clock_origin_datetime`）或无效 `fields` 路径（`unknown_projection_path`） |
| `unknown_tool` | 404 · `1` / `2` | 工具名不存在，在 `issues[].constraints.suggestions` 返回相近候选 |
| `authentication_required` | 401 · — | 缺少或携带无效 API Key |
| `consultation_restricted` | 422 · `1` | 命中禁区（生死、灾祸、临床诊断或医疗择时），`retryable=false` |
| `dependency_missing` / `ephemeris_calculation_failed` | 503 · `1` | 缺少运行时依赖或 Swiss Ephemeris 计算失败 |
| `ephemeris_source_inconsistent` | 503 · `1` | 星历/时区/参考数据文件或配置在运行时不一致，`retryable=false` |
| `fengshui_calculation_inconsistent` / `numerology_source_inconsistent` / `jyotish_calculation_inconsistent` | 503 · `1` | 玄空/月紫白、河洛参评或印占 Drik Bala 内部数据一致性校验失败，`retryable=false` |
| `timeout` / `internal_error` | 504 / 500 · `1` | 请求处理超时或服务端未预期异常 |
| `usage_error` | — · `2` | 仅 CLI：未知 flag、参数语法或 `--request-file` 读取错误 |

### 2.2 三端能力边界

目录共有 90 条记录。REST 和 MCP 默认公开全量，CLI 可执行 90 条目录命令（另有 `list`、`discover` 与 `doctor`）。三端共用规范工具名（`spec.name`）和业务输入合同，部分主要命名映射如下：

| 能力 | REST | MCP / CLI | 差异说明 |
| --- | --- | --- | --- |
| 独立八字命盘 | `/api/bazi/birth-chart` | `bazi_birth_chart` | 业务数据位于 `bazi_birth` |
| 综合命理分析 | `/api/bazi/overview` | `bazi_overview` | 提供出生盘、喜用与格局事实 |
| 关系盘 | `/api/astrology/relationship-chart` | `relationship_chart` | 三端统一使用 `inner_birth_*` / `outer_birth_*` |
| 家居风水 | `/api/fengshui/*` | `fengshui_*` | 八个工具同名；全部 90 个 CLI 命令均支持 `--request-file` 传入 JSON |

### 2.3 输出控制与字段投影

三端统一支持 `detail`（默认 `compact`，可选 `audit`）、`fields`（严格点号路径投影，`run_metadata` 始终保留）与 `as_of`（带时区 ISO 8601 冻结时钟）。无效 `fields` 路径返回 `validation_error`（`unknown_projection_path`）并在 `issues[].constraints.available` 给出可用字段；`ToolSpec.required_output_fields` 声明完整结果必需业务根，启用 `FATEBRIDGE_STRICT_OUTPUT_VALIDATION=1` 后触发完整嵌套模型核验。详细用法与代码示例见[接入指南 § 输出控制与结果读取](agent-guide.md#输出控制与结果读取)。

### 2.4 精度与依赖

核心占星盘优先使用本地 `swisseph`，缺失时回退内置近似轨道；西占推运、事件与生命周期工具依赖 `swisseph` 后端，缺失时返回 `dependency_missing`。`swisseph` 可导入不等于已加载 `.se1` 数据文件，请核对 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`，配置方式见[星历数据安装](ephemeris.md)。

### 2.5 渐进发现与按需 Schema

REST 使用 `GET /api/tools`（查询参数 `detail=summary|full`、`family`、`q`、`tool`、`surface`、`include_output_schema=false|true`），CLI 使用 `list` / `discover [tool]`（支持 `--detail`、`--include-output-schema`），MCP 使用 `discover_tools`。

- `detail=summary`（默认）：未传 `tool` 时返回全局 `counts`、`families` 与工具摘要；指定 `tool` 时返回完整 `input_schema`、`output_fields`、`example_input`、`evidence_views`、`suggested_fields` 与 `compact_fields`。
- `detail=full`：返回完整契约，必须配合 `tool`、`family` 或 `q` 过滤（否则返回 `filter_required_for_full_detail`）；**`output_schema` 默认不返回，仅当显式传入 `include_output_schema=true`（MCP `include_output_schema=True`，CLI `--include-output-schema`）时才会附带**。

### 2.6 确定性与复现元数据

三端支持 `as_of`（ISO 8601 带时区时刻）。`run_metadata` 包含 `run_id`、`tool_name`、`generated_at`、`engine`、`engine_is_approximate`、`effective_time` 与 `warnings`；`detail=audit` 另附 `duration_ms` 与 `replay`（含 `as_of`、`overrides`、`requires_original_input`），随机起卦在 `compact` 下也会附带 `replay.overrides.seed`。将 `replay.overrides` 与 `replay.as_of` 传回同一工具可在相同环境中复现同一计算结果。

## 3. 共享请求族

### 3.1 `FateBridgeRequest` 家族（`/api/bazi/*`、`/api/timing/*`）

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `name` / `gender` | string | 否 | 默认 `未提供` / `未知`；`bazi_luck_cycles` 等须传有效性别 |
| `birth_year` / `birth_month` / `birth_day` / `birth_hour` | int | 是 | 出生年月日时（公历） |
| `birth_minute` | int | 否 | 默认 `0` |
| `birth_second` | int / null | 否 | 八字与时运入口支持已确认整秒 `0..59`（需同时显式给出分钟） |
| `birth_utc_offset` | string / null | 否 | 已确认民用偏移 `±HH:MM[:SS]`，用于消歧重复钟时 |
| `birth_place` / `birth_timezone` | string | 否 | 内置地点解析或 IANA 时区 |
| `birth_longitude` | float | 否 | `-180..180` |
| `use_true_solar_time` | bool | 否 | 中式出生家族默认 `true`（无经度回退钟表时间；显式 `true` 无经度报错） |

九大专项追加 `analysis_year/month/day`、`dayun_pillar` 与 `liunian_pillar`。

### 3.2 核心占星与印度/果老请求家族

`AstroChartRequest` 用于 `/api/astrology/chart`、`/api/astrology/thirteen-sector-chart`、`/api/astrology/hellenistic-chart` 与 `/api/astrology/hamburg-midpoint-chart`；`/api/astrology/guolao-chart` 使用独立的 `GuolaoChartRequest`（默认开启 `use_true_solar_time=true`），`/api/astrology/vedic-chart` 与 `/api/astrology/vimshottari-dasha` 使用 `VedicChartRequest` / `VimshottariDashaRequest`（Lahiri 恒星黄道）。以上入口均要求 `birth_year/month/day/hour` 必填，`birth_minute` 默认 `0`，`birth_longitude` / `birth_latitude` 条件必需，`AstroChartRequest` 默认 `use_true_solar_time=false`。

### 3.3 `WesternTimingRequest` 家族（`/api/astrology/timing*`）

`birth_longitude` 与 `birth_latitude` 必填，并支持 `analysis_year/month/day/hour/minute`（省略 `analysis_hour` / `analysis_minute` 时沿用出生时分）、`return_longitude/latitude/timezone`、`house_system`、`zodiac_type`，聚合入口及对应单项工具按各自契约提供 `pd_method/pd_time_key/pd_type/pd_aspects/show_pd_bounds`、`firdaria_night_order`（`nodes_at_end` / `nodes_after_mars`）、`firdaria_year_basis`（`fixed_365_2425` / `calendar_anniversary`）。

### 3.4 本地技法请求约定

`solar_terms_for_year`、`lunar_calendar_time`、`liuyao`、`canping`、`heluo`、`suzhan`、`interpret_astrology_dice` 与 `sanshi_combined_chart` 等统一使用 `timezone`（常见默认 `+08:00`）、`latitude` / `longitude`；按工具契约配合 `date` / `time`（或 `year`）。`suzhan` 在省略 `time` 时仅做日期历法候选计算；已知钟时则需完整经纬度。`suzhan` 与 `interpret_astrology_dice` 同样支持 `house_system` 与 `zodiac_type`。

### 3.5 双人关系请求

`/api/bazi/compatibility` 使用 `person1_*` / `person2_*`（支持 `person1_zi_hour_policy` / `person2_zi_hour_policy`）与 `relationship_type`（`general`/`marriage`/`friendship`/`business`/`family`）；`/api/compatibility/sukuyo` 使用 `person1_date/time`、`person2_date/time` 与 `distance_rule`；`/api/astrology/relationship-chart` 三端统一使用 `inner_birth_*` / `outer_birth_*`。

## 4. REST 端点家族

### 4.1 基础命理与配合

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/bazi/birth-chart` | 独立八字命盘（数据根为 `bazi_birth`） |
| `POST` | `/api/bazi/overview` | 综合命理分析 |
| `POST` | `/api/bazi/compare-sources` | 明确四柱与已登记原典编释对照 |
| `POST` | `/api/bazi/compatibility` | 双人八字配合分析 |
| `POST` | `/api/compatibility/sukuyo` | 宿曜双人相性分析（三九之秘法） |

#### 4.1.1 八字九大专项维度

大运、流年缺省由命盘与分析日期自动推算，也可用 `dayun_pillar` / `liunian_pillar` 覆盖，输出位于 `<dimension>_analysis`（含 `calendar_context`、`timing_context` 与 `topic_facts`）：

| 方法 | 路径 | 专题事实 |
| --- | --- | --- |
| `POST` | `/api/bazi/marriage` | 配偶星、日支关系与四墓触点 |
| `POST` | `/api/bazi/career` | 官杀、印、食伤、财透藏与结构条件 |
| `POST` | `/api/bazi/wealth` | 财、食伤、比劫透藏与墓库冲动 |
| `POST` | `/api/bazi/health` | 盘内五行权重、寒暖分类与传统文化对应 |
| `POST` | `/api/bazi/children` | 子女星、时柱及传统关系对应 |
| `POST` | `/api/bazi/education` | 印、食伤、官杀及文昌位置 |
| `POST` | `/api/bazi/personality` | 十神透藏、根气与位置关系 |
| `POST` | `/api/bazi/relatives` | 偏财、正印、比劫与年月柱关系 |
| `POST` | `/api/bazi/romance` | 咸池、红鸾、天喜及日支关系 |

### 4.2 时运分析

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/bazi/timing` | 综合时运（含岁运关系、根位与有限投影） |
| `POST` | `/api/bazi/timing/luck-cycles` | 大运分析 |
| `POST` | `/api/bazi/timing/yearly` | 流年分析 |
| `POST` | `/api/bazi/timing/monthly` | 流月分析 |
| `POST` | `/api/bazi/timing/daily` | 流日分析 |
| `POST` | `/api/bazi/timing/hourly` | 流时分析 |
| `POST` | `/api/calendar/solar-term-timeline` | 全年节气节点时间轴 |

### 4.3 历法与知识检索

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/calendar/solar-terms` | 全年节气时刻表（响应位于 `jieqi_year`） |
| `POST` | `/api/calendar/lunar-time` | 农历与干支换算（`time_alg=0` 真太阳时 / `1` 直接时间） |
| `POST` | `/api/divination/gua` | 批量查询八卦/六十四卦结构与《周易》经文（`queries` / `lookup_mode`） |
| `POST` | `/api/knowledge/catalog` | 内置知识目录 |
| `POST` | `/api/knowledge/read` | 内置知识条目读取 |

### 4.4 占卜与本地技法

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/divination/meihua/time-cast` | 梅花时间取数、体用互变与经文参照 |
| `POST` | `/api/divination/meihua/cast` | 梅花显式物数/声音/字占与单动爻起卦 |
| `POST` | `/api/divination/combine-four-gua` | 统摄四卦组合 |
| `POST` | `/api/divination/liuyao` | 六爻纳甲与《增删卜易》结构证据 |
| `POST` | `/api/divination/canping` | 邵子参评数 / 金锁银匙 |
| `POST` | `/api/divination/heluo` | 河洛理数 |
| `POST` | `/api/divination/suzhan` | 二十七宿占 |
| `POST` | `/api/divination/astrology-dice/interpret` | [占星骰](astrodice.md)：`planet`/`sign`/`house` 必填（`house=0..11`） |
| `POST` | `/api/divination/sanshi` | 三式合一 |

### 4.5 中国术数独立盘

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/ziwei/birth-chart` | 紫微斗数命盘 |
| `POST` | `/api/ziwei/timing` | 紫微斗数运限（大限/小限/流年/流月/流日/流时与四化） |
| `POST` | `/api/ziwei/rules` | 紫微规则库（详见[紫微参考](ziwei.md)） |
| `POST` | `/api/liuren/chart` | 六壬起课 |
| `POST` | `/api/liuren/timing/yearly` | 六壬虚岁行年与分析课 |
| `POST` | `/api/qimen` | 奇门遁甲（支持置闰/拆补 `qimen_options`） |
| `POST` | `/api/taiyi` | 太乙神数（年/月/日/时计及历史年计 `year_profile`） |
| `POST` | `/api/jinkou` | 金口诀（四位、课钤与用位证据；`overview.month_general` 为中气月将，`overview.yuejiang` 为加时将神） |

### 4.6 核心占星盘

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astrology/chart` | 标准占星本命盘（纯本命盘，支持 `apparent_model=native\|opaque_solar`） |
| `POST` | `/api/astrology/thirteen-sector-chart` | 上升起点 13 等分扇区盘 |
| `POST` | `/api/astrology/hellenistic-chart` | 希腊风格盘 |
| `POST` | `/api/astrology/guolao-chart` | 果老 / 七政四余盘 |
| `POST` | `/api/astrology/vedic-chart` | 印占 Lahiri 本命、分盘与八分法 |
| `POST` | `/api/astrology/vimshottari-dasha` | 印占 Moon-nakshatra 达沙（可选 `dasha_depth=2..6`） |
| `POST` | `/api/astrology/hamburg-midpoint-chart` | 德国汉堡中点 / 太阳弧派生盘 |
| `POST` | `/api/astrology/relationship-chart` | 关系盘（`compare`/`composite`/`influence`/`timespace`/`marks`） |
| `POST` | `/api/human-design/chart` | [人类图](human-design.md)双时刻、门线与身体图 |

### 4.7 西占推运

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astrology/timing` | 推运总览 bundle |
| `POST` | `/api/astrology/timing/solar-return` | 太阳返照 |
| `POST` | `/api/astrology/timing/lunar-return` | 月亮返照 |
| `POST` | `/api/astrology/timing/transit-chart` | 行运盘 |
| `POST` | `/api/astrology/timing/solar-arc` | 太阳弧 |
| `POST` | `/api/astrology/timing/chart-for-year` | 指定年盘 |
| `POST` | `/api/astrology/timing/profection` | 年小限 |
| `POST` | `/api/astrology/timing/primary-directions` | 主限 |
| `POST` | `/api/astrology/timing/primary-directions-chart` | 主限图盘 |
| `POST` | `/api/astrology/timing/zodiacal-releasing` | 黄道释放 |
| `POST` | `/api/astrology/timing/firdaria` | 法达星限 |
| `POST` | `/api/astrology/timing/decennials` | 十年星限 |

### 4.8 事件占星（事件盘）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astrology/events/mundane-ingress-chart` | 世俗入宫盘（`ingress_term` 仅限春分/夏至/秋分/冬至） |
| `POST` | `/api/astrology/events/planetary-returns` | 多重回归 |
| `POST` | `/api/astrology/events/horary-chart` | 卜卦盘（支持 `orb_profile` 与 `radicality_context`） |
| `POST` | `/api/astrology/events/evaluate-election-time` | 择日盘 |

事件工具支持 `question_calendar` / `candidate_calendar`（`proleptic_gregorian` / `julian`）、`question_clock_basis` / `candidate_clock_basis`（`civil` / `local_mean_solar` / `local_apparent_solar`）、`question_hour_origin` / `candidate_hour_origin`（`midnight` / `noon`）、整秒 `question_second` / `candidate_second` 及 `ut1_source`（`swiss_delta_t` / `iers_c04`）。

### 4.9 全生命周期技法

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astrology/harmonic-chart` | 调波盘 |
| `POST` | `/api/astrology/timing/planetary-ages` | 行星年龄 |
| `POST` | `/api/astrology/timing/triplicity-ruler-periods` | 三分主星推运（`division=thirds/halves`） |
| `POST` | `/api/astrology/timing/lunar-phase-progressions` | 月相推运 |
| `POST` | `/api/astrology/timing/bounds-directions` | 界推运（`time_key=Ptolemy/Naibod`） |
| `POST` | `/api/astrology/timing/balbillus-periods` | Balbillus 129 年系统（`mode=nearest/forward`） |
| `POST` | `/api/astrology/timing/numeric-aspect-periods` | 数字相位推运（`release_mode=soul/body`） |
| `POST` | `/api/astrology/timing/planetary-periods-129-years` | 129 年系统 |
| `POST` | `/api/astrology/timing/planetary-arc-directions` | 行星弧方向 |
| `POST` | `/api/astrology/timing/persian-directions` | 波斯向运 |
| `POST` | `/api/astrology/timing/age-point` | 年龄推进点 |
| `POST` | `/api/astrology/timing/sidereal-progressions` | 恒星推运 |
| `POST` | `/api/astrology/timing/declination-progressions` | 赤纬推运 |

### 4.10 健康检查与能力发现

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 存活检查，返回 `{"status":"healthy"}` |
| `GET` | `/ready` | 服务就绪与可选西占运行时检查（`checks`） |
| `GET` | `/metrics` | Prometheus 文本指标 |
| `GET` | `/api/tools` | 机读能力发现清单（支持 `detail`/`family`/`q`/`tool`/`surface`/`include_output_schema`） |
| `POST` | `/api/batch` | 多主体多工具无状态批处理（共享 `subjects` 与 `defaults`，一次请求串联多工具） |

### 4.11 家居风水（family `fengshui`）

| REST POST | MCP / CLI | 说明 |
| --- | --- | --- |
| `/api/fengshui/directions` | `fengshui_directions` | 后天八卦与八方／24 山角区索引及地磁换算候选 |
| `/api/fengshui/minggua` | `fengshui_minggua` | 个人命卦与八方关系 |
| `/api/fengshui/bazhai` | `fengshui_bazhai` | 坐山宅盘、逐人命盘、位置/朝向校验与阳宅三要 |
| `/api/fengshui/jinsuo` | `fengshui_jinsuo` | 金锁玉关八宫与 24 山砂水偏好 |
| `/api/fengshui/annual-stars` | `fengshui_annual_stars` | 立春换年九宫年星、元运与岁煞 |
| `/api/fengshui/monthly-stars` | `fengshui_monthly_stars` | 十二节换月紫白及日/时紫白 |
| `/api/fengshui/xuankong-house-chart` | `fengshui_xuankong_house_chart` | 中州派玄空运山向宅盘、替星、城门与条件解读 |
| `/api/fengshui/assess` | `fengshui_assess` | 多层合参主入口（四层叠盘与跨层布局分析） |

三端可复制请求与状态字段语义见[家居风水参考](fengshui.md)。

### 4.12 心理测量量表（family `psychometrics`）

| REST POST | MCP / CLI | 说明 |
| --- | --- | --- |
| `/api/psychometrics/ipip-big-five` | `ipip_big_five` | Goldberg (1992) IPIP 50 题大五人格因子标记量表：支持 `action=list_items` 与 `action=score` |

## 5. REST 调用示例

```bash
# 核心占星盘
curl -X POST http://localhost:8010/api/astrology/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167, "birth_place": "上海"
  }'

# 太阳返照
curl -X POST http://localhost:8010/api/astrology/timing/solar-return \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SR Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167, "birth_place": "上海",
    "analysis_year": 2028, "analysis_month": 4, "analysis_day": 6,
    "analysis_hour": 12, "analysis_minute": 0
  }'
```

## 6. FastMCP 工具面

### 6.1 启动

```bash
uv run --extra dev python -m fatebridge.mcp_server
```

### 6.2 MCP 工具分组

全部 90 项业务能力由 `discover_tools`、`run_calculation` 与 `run_batch` 三个协议工具暴露（不暴露 MCP 资源），按 `family` 分组如下：

#### 基础命理（family `bazi`）

- `bazi_overview`
- `bazi_birth_chart`
- `compare_bazi_sources`
- `bazi_marriage`
- `bazi_career`
- `bazi_wealth`
- `bazi_health`
- `bazi_children`
- `bazi_education`
- `bazi_personality`
- `bazi_relatives`
- `bazi_romance`

#### 双人配合（family `compatibility`）

- `bazi_compatibility`
- `sukuyo_compatibility`

#### 时运与历法（family `timing`）

- `bazi_timing`
- `bazi_luck_cycles`
- `bazi_yearly_timing`
- `bazi_monthly_timing`
- `bazi_daily_timing`
- `bazi_hourly_timing`
- `solar_term_timeline`
- `solar_terms_for_year`
- `lunar_calendar_time`

#### 占卜与本地技法（family `divination`）

- `gua_lookup`
- `meihua_time_cast`
- `meihua_cast`
- `combine_four_gua`
- `liuyao`
- `canping`
- `heluo`
- `suzhan`
- `interpret_astrology_dice`
- `sanshi_combined_chart`

`heluo` 与 `canping` 的完整按需输入契约与视图字段见[河洛调用合同](contracts/heluo.json)及[参评调用合同](contracts/canping.json)。

#### 中国术数独立盘（family `metaphysics`）

- `ziwei_birth_chart`
- `ziwei_timing`
- `ziwei_rules`
- `liuren_chart`
- `liuren_yearly_timing`
- `qimen`
- `taiyi`
- `jinkou`

#### 知识库（family `knowledge`）

- `knowledge_catalog`
- `knowledge_read`

#### 核心占星盘（family `astro`）

- `astrology_chart`
- `thirteen_sector_chart`
- `hellenistic_chart`
- `guolao_chart`
- `vedic_chart`
- `vimshottari_dasha`
- `hamburg_midpoint_chart`
- `human_design`
- `relationship_chart`

#### 西占推运（family `western_timing`）

- `western_timing`
- `solar_return`
- `lunar_return`
- `transit_chart`
- `solar_arc`
- `chart_for_year`
- `profection`
- `primary_directions`
- `primary_directions_chart`
- `zodiacal_releasing`
- `firdaria`
- `decennials`

#### 事件占星（family `western_event`）

- `mundane_ingress_chart`
- `planetary_returns`
- `horary_chart`
- `evaluate_election_time`

#### 全生命周期技法（family `western_lifespan`）

- `harmonic_chart`
- `planetary_ages`
- `triplicity_ruler_periods`
- `lunar_phase_progressions`
- `bounds_directions`
- `balbillus_periods`
- `numeric_aspect_periods`
- `planetary_periods_129_years`
- `planetary_arc_directions`
- `persian_directions`
- `age_point`
- `sidereal_progressions`
- `declination_progressions`

#### 家居风水（family `fengshui`）

- `fengshui_directions`
- `fengshui_minggua`
- `fengshui_bazhai`
- `fengshui_jinsuo`
- `fengshui_annual_stars`
- `fengshui_monthly_stars`
- `fengshui_xuankong_house_chart`
- `fengshui_assess`

#### 心理测量量表（family `psychometrics`）

- `ipip_big_five`

### 6.3 MCP 与 REST 的差异

| 维度 | REST | FastMCP |
| --- | --- | --- |
| 传输协议 | HTTP JSON | MCP tool call |
| 返回格式 | JSON object | `structuredContent` JSON object |
| 错误表现 | HTTP status + 顶层错误 JSON | 模型/业务错误为 `isError=true` + 统一错误包络 |
| 使用场景 | Web / script / 后端集成 | Agent host / 工具调用 |

## 7. 常见响应字段

- **命理类**：`person_info`、`four_pillars`、`day_master`、`element_distribution`、`favorable_elements`、`structure_profile`、`ten_gods`、`patterns`、`calendar_context`。
- **占星类**：`chart_profile`、`angles`、`houses`、`planets`、`aspects`、`aspect_evidence`、`classical`。
- **推运类**：`summary`、`analysis_context`、各技法字段（如 `solarreturn`、`pd`、`firdaria`）。

## 8. 调试建议

投影报错（`unknown_projection_path`）、星历精度降级或 `dependency_missing` 的完整排查步骤见[故障排除](troubleshooting.md)，或通过 `discover_tools(tool=..., detail="full", include_output_schema=True)` 查看完整输出结构。

## 咨询范围与禁区校验

生死寿命、灾祸断言、临床诊断治疗与医疗择时不提供。卜卦 `category` 不接受 `death`、`health`、`pregnancy`，择时 `topic_id` 不接受 `surgery`；明确命中禁区的请求在计算前返回非重试错误 `consultation_restricted`。健康专项仅提供盘内传统文化分类，普通星盘亦已排除死亡点。详见[硬边界](interpretation/shared/safety-boundaries.md)。
