# FateBridge API 参考

本文列出 FateBridge 的 REST 路由、FastMCP 工具、CLI 约定、共享请求族与响应字段。首次安装请看[快速入门](getting-started.md)，客户端集成代码与分页交付示例见[接入指南](agent-guide.md)，各能力范围见[算法覆盖矩阵](algorithm-coverage.md)。

OpenAPI 发布 93 个业务 REST 路由，另有 `/health`、`/ready`、`/metrics` 三个运维端点。中央目录共有 93 条记录，CLI 可执行 93 条目录命令，MCP 通过四个入口提供 93 项业务能力。字段约束以当前服务的 `/openapi.json`、MCP `describe_capability` 或 CLI `describe` 为准。

## 阅读导航

| 要查什么 | 章节 |
| --- | --- |
| 接口命名、错误、快照、投影与复现 | [公共约定](#2-公共约定) |
| 咨询禁区与范围校验 | [咨询范围与禁区校验](#咨询范围与禁区校验) |
| 输入字段与默认值 | [共享请求族](#3-共享请求族) |
| REST 路由与风水入口 | [REST 端点家族](#4-rest-端点家族) |
| 可复制 HTTP 调用 | [REST 调用示例](#5-rest-调用示例) |
| MCP 公开工具列表与差异 | [FastMCP 工具面](#6-fastmcp-工具面) |
| 常见字段与排错 | [常见响应字段](#7-常见响应字段) · [调试建议](#8-调试建议) |

## 1. 基础信息

### REST

- 基础地址：`http://localhost:8010`（Swagger UI `/docs`，ReDoc `/redoc`，OpenAPI Schema `/openapi.json`，能力发现 `/api/tools`）。
- 请求格式：`Content-Type: application/json`。业务输入放在 JSON 请求体；通用控制项（`fields`、`strict_fields`、`detail`、`include_snapshot_text`、`response_char_limit`、`as_of`、`trace_id`、`parent_run_id`）放在 URL 查询参数，多个 `fields` 重复传参。

### FastMCP

- 启动命令：`python -m fatebridge.mcp_server`（默认 stdio，HTTP 部署见 [MCP 部署指南](mcp-deployment.md)）。
- 返回格式：原生 `structuredContent` JSON 对象；工具失败时返回 `isError=true`，`content` 附带简短错误消息。

## 2. 公共约定

### 2.1 鉴权与错误格式

`FATEBRIDGE_API_KEYS` 为空时 REST 不鉴权；非空时发送 `X-API-Key: <secret>`（请求头名可用 `API_KEY_HEADER_NAME` 修改）。`/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json` 及 `OPTIONS` 免检，其余业务和发现接口均受保护。MCP 与 CLI 不使用 REST API Key。

已知工具的模型校验与业务错误共享扁平错误包络（`error`、`error_code`、`retryable`、`issues`）：

```json
{
  "error": "请求参数无效",
  "error_code": "validation_error",
  "retryable": false,
  "issues": [
    {"path": "birth_month", "code": "less_than_equal",
     "message": "Input should be less than or equal to 12", "constraints": {"le": 12}}
  ]
}
```

请按 `error_code` 分支处理：

- `validation_error`（400 / 422）：字段缺失、格式或取值非法、未知字段、无效日期，或领域输入拒绝；出生年月日无效时 `issues[].path` 指向 `birth_date`（关系盘为 `inner.birth_date` / `outer.birth_date`），正午起算无效钟面返回 `invalid_clock_origin_datetime`。
- `authentication_required`（401）：缺少或无效 API Key。
- `consultation_restricted`（400 / 422）：命中咨询禁区（生死、灾祸、临床诊断或医疗择时），`retryable=false`。
- `dependency_missing` / `ephemeris_calculation_failed`（503）：运行依赖或 Swiss Ephemeris 计算失败。
- `fengshui_calculation_inconsistent` / `numerology_source_inconsistent`（503）：玄空或数算内部状态不一致，`retryable=false`。
- `timeout`（504）与 `internal_error`（500）。

CLI 成功退出 `0`，计算或校验失败退出 `1`，参数语法或未知 flag 错误退出 `2`。

### 2.2 快照协议

支持双层快照的工具可返回人读文本 `snapshot_text` 及结构化导出 `snapshot_export`（含 `selected_sections`、`section_titles_detected` 与 `export_text`），并附带 `run_metadata`：

```json
{
  "run_metadata": {
    "run_id": "f5c3...",
    "trace_id": "5f17...",
    "tool_name": "qimen",
    "generated_at": "2026-04-13T08:00:00Z",
    "engine": "fatebridge-offline",
    "engine_is_approximate": false
  },
  "snapshot_text": "[起盘信息]\n...",
  "snapshot_export": {
    "technique": {"key": "qimen"},
    "selected_sections": ["起盘信息", "九宫方盘"],
    "section_titles_detected": ["起盘信息", "九宫方盘", "离九宫"],
    "export_text": "[起盘信息]\n..."
  }
}
```

`ToolSpec.required_output_fields` 声明完整结果必需业务根；启用 `FATEBRIDGE_STRICT_OUTPUT_VALIDATION=1` 后校验完整嵌套输出模型。`astrology_chart` 按请求 `chart_variant` 附加对应业务根（`chart` 无额外根、`chart13` 需 `thirteen_sectors`、`hellen_chart` 需 `hellenistic`、`guolao_chart` 需 `guolao`、`india_chart` 需 `india`、`germany` 需 `base_chart` 与 `midpoints`）。

### 2.3 `selected_sections`

支持 `selected_sections` 的主要入口包括：`bazi_birth_chart`、全部时运与历法 helper、`gua_lookup` / `gua_meanings`、`sanshi_combined_chart`、中国术数独立盘（紫微、六壬、奇门、太乙、金口诀）、`knowledge_*`、`export_parse` 及 11 个独立西占推运工具。八字九专题、核心/关系星盘、事件与生命周期、梅花等本地占法不支持此字段。显式非空选择未命中任何标题时 `export_text` 为空；紫微命盘的导出章节为 `起盘信息` 与 `宫位总览`。

### 2.4 三端能力边界

中央目录含 93 条记录。REST 和 MCP 默认公开全量，CLI 可执行 93 条目录命令（另有 `list`、`discover`、`describe`、`profile`、`doctor` 与 `result-read`）。三端共用公开工具名和业务输入合同，部分主要命名映射如下：

| 能力 | REST | MCP / CLI | 差异说明 |
| --- | --- | --- | --- |
| 独立八字命盘 | `/api/bazi/birth-chart` | `bazi_birth_chart` | 业务数据位于 `bazi_birth` |
| 综合命理分析 | `/api/bazi/overview` | `bazi_overview` | 提供出生盘、喜用与格局事实 |
| 关系盘 | `/api/astrology/relationship-chart` | `relationship_chart` | 三端统一使用 `inner_birth_*` / `outer_birth_*` |
| 家居风水 | `/api/fengshui/*` | `fengshui_*` | 八个工具同名；CLI 支持 `--request-file` 传入 JSON |

### 2.5 字段投影与输出体积

| 选项 | REST（查询参数） | MCP | CLI（工具名后） |
| --- | --- | --- | --- |
| 字段投影 | `?fields=bazi_birth.day_master&fields=person_info` | `fields=["bazi_birth.day_master", "person_info"]` | `--fields bazi_birth.day_master person_info` |
| 严格投影 | `?strict_fields=true` | `strict_fields=true` | `--strict-fields` |
| 结果级别 | `?detail=compact`（默认 `standard`） | `detail="compact"`（默认） | `--detail compact`（默认 `standard`） |
| 省略顶层快照文本 | `?include_snapshot_text=false` | `include_snapshot_text=false` | `--no-include-snapshot-text` |
| 响应字符预算 | `?response_char_limit=8192`（默认 `0`） | `response_char_limit=8192`（默认 `8192`） | `--response-char-limit 8192`（默认 `0`） |

`compact` 在省略 `fields` 时返回领域首轮视图，`standard` 返回常规业务体，`audit` 返回完整业务体及方法与误差预算信息。11 个单项西占时运工具与 `horary_chart`、`evaluate_election_time` 在 `standard` 下默认省略快照，需要时可显式启用 `include_snapshot_text=true` 或 `detail=audit`。

`strict_fields=false` 时无效路径附带 `projection_warnings`，`strict_fields=true` 则报 `validation_error`。超出字符预算时响应包含 `result_delivery`，可通过 `GET /api/results/{result_id}/payload`、`/pages`、`/verified?expected_run_id=...`、CLI `fatebridge result-read RESULT_ID --run-id ORIGINAL_RUN_ID` 或 MCP `read_result` / 资源 URI 读取同一次运行保留的结果，详见[完整结果交付](agent-guide.md#完整结果交付与同次导出)。

### 2.6 精度与依赖

核心占星盘优先使用本地 `swisseph`，缺失时回退内置近似轨道；西占推运、事件与生命周期工具依赖 `swisseph` 后端，缺失时返回 `dependency_missing`。`swisseph` 可导入不等于已加载 `.se1` 数据文件，请核对 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`，配置方式见[星历数据安装](ephemeris.md)。

### 2.7 渐进发现与执行提示

REST 使用 `GET /api/tools?detail=summary|full&family=...&q=...&tool=...&surface=...`，CLI 使用 `discover` / `list` / `describe`，MCP 使用 `discover_capabilities`、`describe_capability` 与资源 `fatebridge://catalog/summary`、`fatebridge://families/{family}`、`fatebridge://tools/{tool}`。单工具输入契约可附 `evidence_views` 提供可直接复制的 `fields` 路径列表。

### 2.8 确定性与复现元数据

三端支持 `as_of`（ISO 8601 带时区时刻，公历 1–9999 年）、`trace_id` 与 `parent_run_id`（1–128 字符字母数字及 `_ . : -`）。`run_metadata`（2.0）包含 `effective_time`、`determinism`、`replay`、`runtime` 与 `provenance`；随机起卦保留 `replay.overrides.seed`。CLI `profile` 支持统一传入 `--as-of` 与 `--trace-id` 并自动关联子运行的 `parent_run_id`。

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

### 3.2 `AstroChartRequest` 家族

用于 `/api/astrology/chart`、`/api/astrology/thirteen-sector-chart`、`/api/astrology/hellenistic-chart`、`/api/astrology/guolao-chart`、`/api/astrology/vedic-chart` 与 `/api/astrology/hamburg-midpoint-chart`：`birth_year/month/day/hour` 必填，`birth_minute` 默认 `0`，`birth_longitude` / `birth_latitude` 条件必需，`use_true_solar_time` 默认 `false`，另可选 `hsys`（`0..8`）与 `zodiacal`（`0` 回归 / `1` 恒星）。

### 3.3 `WesternTimingRequest` 家族（`/api/astrology/timing*`）

`birth_longitude` 与 `birth_latitude` 必填，并支持 `analysis_year/month/day/hour/minute`（省略 `analysis_hour` / `analysis_minute` 时沿用出生时分）、`return_longitude/latitude/timezone`、`house_system`、`zodiac_type`、`pd_method/pd_time_key/pd_type/pd_aspects/show_pd_bounds`、`firdaria_night_order`（`nodes_at_end` / `nodes_after_mars`）、`firdaria_year_basis`（`fixed_365_2425` / `calendar_anniversary`）及独立工具的 `selected_sections`。

### 3.4 本地技法请求约定

`liuyao`、`suzhan`、`interpret_astrology_dice` 与 `sanshi_combined_chart` 等使用 `date` / `time`、`zone`（常见默认 `+08:00`）、`lat` / `lon`、`gps_lat` / `gps_lon` 与可选 `selected_sections`。`suzhan` 在省略 `time` 时仅做日期历法候选计算；已知钟时则需完整经纬度。

### 3.5 双人关系请求

`/api/bazi/compatibility` 使用 `person1_*` / `person2_*` 与 `relationship_type`（`general`/`marriage`/`friendship`/`business`/`family`）；`/api/compatibility/sukuyo` 使用 `person1_date/time` 与 `person2_date/time`；`/api/astrology/relationship-chart` 三端统一使用 `inner_birth_*` / `outer_birth_*`。

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

大运、流年缺省由命盘与分析日期自动推算，也可用 `dayun_pillar` / `liunian_pillar` 覆盖，输出位于 `<dimension>_analysis` 与 `evidence_chain`：

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

### 4.3 Calendar / knowledge / export helper

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/calendar/solar-terms` | 全年节气时刻表（响应位于 `jieqi_year`） |
| `POST` | `/api/calendar/lunar-time` | 农历与干支换算（`time_alg=0` 真太阳时 / `1` 直接时间） |
| `POST` | `/api/divination/gua` | 卦义检索 |
| `POST` | `/api/divination/gua/meanings` | 批量查询卦象结构与《周易》经文 |
| `POST` | `/api/export/formats` | 导出合同注册表 |
| `POST` | `/api/export/parse` | 快照文本解析 |
| `POST` | `/api/knowledge/catalog` | 内置知识目录 |
| `POST` | `/api/knowledge/read` | 内置知识条目读取 |

### 4.4 Divination 与本地技法

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/divination/meihua/time-cast` | 梅花时间取数、体用互变与经文参照 |
| `POST` | `/api/divination/meihua/cast` | 梅花显式物数/声音/字占与单动爻起卦 |
| `POST` | `/api/divination/combine-four-gua` | 统摄四卦组合 |
| `POST` | `/api/divination/liuyao` | 六爻纳甲与《增删卜易》结构证据 |
| `POST` | `/api/divination/canping` | 邵子参评数 / 金锁银匙 |
| `POST` | `/api/divination/heluo` | 河洛理数 |
| `POST` | `/api/divination/suzhan` | 二十七宿占 |
| `POST` | `/api/divination/astrology-dice/interpret` | [占星骰](astrodice.md)：planet/sign/house 必填（house=`0..11`） |
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
| `POST` | `/api/astrology/chart` | 标准占星本命盘（支持 `chart_variant` 与 `apparent_model=native\|opaque_solar`） |
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
| `GET` | `/api/results/{result_id}` | 同次结果交付 manifest |
| `GET` | `/api/results/{result_id}/payload` | 下载同次结果保留的完整 JSON |
| `GET` | `/api/results/{result_id}/pages` | 字符分页读取（支持 `offset` 与 `path`） |
| `GET` | `/api/results/{result_id}/verified` | 使用 `expected_run_id` 校验后按页读取 |
| `GET` | `/api/tools` | 机读能力发现清单（支持 `detail`/`family`/`q`/`tool`/`surface`） |

### 4.11 家居风水（family `fengshui`）

| REST POST | MCP / CLI | 说明 |
| --- | --- | --- |
| `/api/fengshui/directions` | `fengshui_directions` | 后天八卦与八方／24山角区索引 |
| `/api/fengshui/minggua` | `fengshui_minggua` | 个人命卦与八方关系 |
| `/api/fengshui/bazhai` | `fengshui_bazhai` | 坐山宅盘与逐人命盘 |
| `/api/fengshui/jinsuo` | `fengshui_jinsuo` | 金锁玉关八宫固定砂水偏好 |
| `/api/fengshui/annual-stars` | `fengshui_annual_stars` | 立春换年九宫年星与元运 |
| `/api/fengshui/monthly-stars` | `fengshui_monthly_stars` | 十二节换月中性月紫白 |
| `/api/fengshui/xuankong-house-chart` | `fengshui_xuankong_house_chart` | 中州派玄空运山向宅盘与替星 |
| `/api/fengshui/assess` | `fengshui_assess` | 分层宅盘、室内布局与条件式方案评估 |

三端可复制请求与状态字段语义见[家居风水参考](fengshui.md)。

### 4.12 心理测量量表（family `psychometrics`）

| REST POST | MCP / CLI | 说明 |
| --- | --- | --- |
| `/api/psychometrics/ipip-big-five` | `ipip_big_five` | Goldberg (1992) IPIP 50 题大五人格因子标记量表：支持 `action=list_items` 与 `action=score` |

## 5. REST 调用示例

### 5.1 核心占星盘

```bash
curl -X POST http://localhost:8010/api/astrology/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167, "birth_place": "上海"
  }'
```

### 5.2 独立西占技法

```bash
curl -X POST http://localhost:8010/api/astrology/timing/solar-return \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SR Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167, "birth_place": "上海",
    "analysis_year": 2028, "analysis_month": 4, "analysis_day": 6,
    "analysis_hour": 12, "analysis_minute": 0,
    "selected_sections": ["起盘信息", "星盘信息"]
  }'
```

### 5.3 导出解析 helper

```bash
curl -X POST http://localhost:8010/api/export/parse \
  -H "Content-Type: application/json" \
  -d '{"technique":"qimen","content":"[起盘信息]\n示例\n\n[九宫方盘]\n示例","selected_sections":["起盘信息"]}'
```

## 6. FastMCP 工具面

### 6.1 启动

```bash
uv run --locked --extra dev python -m fatebridge.mcp_server
```

### 6.2 MCP 工具分组

全部 93 项业务能力由 `discover_capabilities`、`describe_capability`、`run_calculation` 与 `read_result` 四个协议工具暴露，按 `family` 分组如下：

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

#### Divination 与本地技法（family `divination`）

- `gua_lookup`
- `gua_meanings`
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

#### export / knowledge helper

- `export_formats`
- `export_parse`
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

#### 西占推运（family `western_timing` / `western_timing_tool`）

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
- **占星类**：`chart_profile`、`angles`、`houses`、`planets`、`aspects`、`aspect_evidence`、`classical`、`snapshot_text`、`snapshot_export`。
- **推运类**：`summary`、`analysis_context`、各技法字段（如 `solarreturn`、`pd`、`firdaria`）、`snapshot_text`、`snapshot_export`。

## 8. 调试建议

- **`selected_sections` 不生效**：核对 `snapshot_export.section_titles_detected` 与 `missing_selected_sections`。
- **占星精度下降**：同时核对 `chart_profile.engine_precision`、`engine_backend`、`ephemeris_model` 与 `run_metadata.engine_is_approximate`。
- **西占推运报错**：检查当前进程解释器是否具备 `swisseph` 运行时依赖；更多排错见[故障排除](troubleshooting.md)。

## 咨询范围与禁区校验

生死寿命、灾祸断言、临床诊断治疗与医疗择时不提供。卜卦 `category` 不接受 `death`、`health`、`pregnancy`，择时 `topic_id` 不接受 `surgery`；明确命中禁区的请求在计算前返回非重试错误 `consultation_restricted`。健康专项仅提供盘内传统文化分类，子女专项仅提供命主视角的星宫关系而不做数量或生育时间预测，普通星盘亦已排除死亡点。详见[硬边界](interpretation/shared/safety-boundaries.md)。
