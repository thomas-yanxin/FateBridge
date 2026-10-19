# FateBridge API 参考

本文档按“能力域”描述 FateBridge 当前对外接口，而不是按历史模块拆散说明。当前仓库同时提供：

- REST API：FastAPI，默认 `http://localhost:8010`
- FastMCP：`python -m fatebridge.mcp_server` 启动的 MCP 工具面

> 当前实际暴露 86 个业务 REST 路由（另含 `/health`、`/ready`、`/metrics` 三个运维端点）和 87 个 FastMCP 工具。两个数字由中央目录派生，并由 `tests/test_doc_tool_counts.py` 锁定。

## 阅读导航

| 要查什么 | 章节 |
| --- | --- |
| 错误、快照、三端映射、投影、复现 | [公共约定](#2-公共约定) |
| 输入字段与默认值 | [共享请求族](#3-共享请求族)；具体约束以实际 Schema 为准 |
| REST 路由与风水入口 | [端点家族](#4-rest-端点家族) · [家居风水](#411-家居风水family-fengshui) |
| 可复制的 HTTP 调用 | [REST 示例](#5-rest-调用示例) |
| MCP 公开名称 | [FastMCP 工具面](#6-fastmcp-工具面) |
| 结果字段、精度排错 | [响应字段](#7-常见响应字段) · [调试建议](#8-调试建议) |

首次安装见[快速入门](getting-started.md)，客户端与完整导出见[接入指南](agent-guide.md)，旧调用升级见[迁移指南](migration.md)。

## 1. 基础信息

### REST

- 基础地址：`http://localhost:8010`
- Swagger UI：`/docs`
- ReDoc：`/redoc`
- Content-Type：`application/json`

### FastMCP

- 启动命令：`python -m fatebridge.mcp_server`
- 返回格式：原生 `structuredContent` JSON 对象，同时保留等价的 JSON 文本 content
- 设计目标：让 Agent 宿主可以直接把 FateBridge 视作工具箱使用

## 2. 公共约定

### 2.1 鉴权与错误格式

`FATEBRIDGE_API_KEYS` 为空时 REST 不鉴权；非空时发送 `X-API-Key: <secret>`（请求头名可用 `API_KEY_HEADER_NAME` 修改）。支持逗号分隔的 `name:secret` 或单独的 `secret`。空条目、缺少名称/密钥、重复名称会阻止启动。

免鉴权路径为 `/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json`，`OPTIONS` 也免检。`/api/tools` 需要鉴权。密钥只用于 REST；默认 stdio MCP 与 CLI 不使用此配置。

已知工具的模型校验和业务计算错误采用**扁平的顶层错误包络**，CLI 可额外包含 `status_code`。MCP 返回原生 `isError=true`；FastMCP 客户端默认抛出 `ToolError`，需要读取错误包络时设置 `raise_on_error=False` 并读取 `structured_content`。未知工具、非法 RPC 等协议错误仍由 MCP 框架处理。业务错误按 `error_code` 分支处理：

```json
{
  "error": "无效的八字分析参数",
  "error_code": "validation_error",
  "retryable": false
}
```

常见 `error_code`：`validation_error`（400 / 422）、`authentication_required`（401）、
`dependency_missing`（503）、`timeout`（504）、`internal_error`（500）。请基于 `error_code`
而非 `error` 文案做分支判断。

常见状态码：

- `400`：模型校验通过后的领域输入错误
- `422`：请求字段缺失、类型/范围/枚举错误、未知字段、完整公历日期无效；REST 非法 JSON
- `401`：缺少或无效的 API key（仅在配置了密钥时）
- `500`：服务内部异常
- `503`：能力依赖缺失（如西占预测运行时不可用）
- `504`：计算超时

`retryable` 是响应的实际重试提示，不能只由状态码推断。框架的未知路由 / 方法错误（404 / 405）不属于业务错误合同。CLI 工具调用成功退出 0，计算失败退出 1，用法错误/不支持退出 2；`list` 和 `--help` 输出文本。

模型校验错误带有 `issues`，每项包含字段 `path`、稳定错误 `code` 和可选 `constraints`，不回显输入值。未知字段会被拒绝；显式非法的 `astro_election.topic_id`、`astro_horary.category` 或 `two_person_compatibility.relationship_type` 不回退为其他主题或 `general`。关系类型只接受 `general/marriage/friendship/business/family`，省略时为 `general`。省略其他可选字段仍使用声明的默认值。CLI 的未知 flag 或 argparse 类型错误属于用法错误（退出 2），进入请求模型后的校验失败属于计算失败（退出 1）。

REST OpenAPI、MCP `tools/list`、`/api/tools` 和 CLI `describe` 发布中央目录的输入与输出 Schema。成功结果在字段投影前校验，输出违规属于 `internal_error`，不归责于请求参数。合同覆盖根字段，以及主限命中与坐标、时主递归子限、寿限时间线、古典与关系盘、紫微星曜、六壬四课三传、奇门宫位、太乙核心盘和地方术数条目，以及九类八字专题、宿曜双向关系、知识覆盖/查询与导出模板/分段/动态设置等稳定嵌套事实。动态星体、卦码和规则键保持开放，但已声明的字典值与列表条目会校验；解释文本和未声明扩展继续允许。业务字段可选且允许 null，以兼容 `fields` 投影、既有可空事实与 CLI 全局 `--no-metadata`；Schema 不保证完整结果的每个字段必定存在。校验不重序列化响应，因此不补默认值、不删除扩展字段、不改写原数值。OpenAPI 使用稳定 `operationId`，并在启用 REST 密钥时声明实际鉴权要求。合同回归见 [专业嵌套合同测试](../tests/test_agentic_nested_outputs.py) 和 [八字专题、宿曜及知识/导出合同测试](../tests/test_agentic_domain_outputs.py)。

### 2.2 快照协议

完整计算另有中央目录声明的 `required_output_fields`，通过发现记录的 `full_result_required_fields` 公开，并参与 `contract_sha256`。这些必需业务根缺失或为 null 时，共享执行返回 `internal_error`，不会只生成 metadata 冒充成功；字段投影在这项验证之后执行，仍可合法省略业务根。此保护不宣称所有嵌套可选事实都必须存在。领域返回的错误包络也须符合 `ErrorEnvelope`，缺错误事实或错误码／retryable 的异常结果归为内部错误，保留有效 trace／parent。

事业结构与创业倾向评分的 `score_kind=traditional_rule_index`、`scope`、`score_basis` 明确所选规则的范围和基准／加减／限制；分数及十神信号不测量实际能力、收入或创业成功率。

布局请求的 `coverage.analysis_progress` 与 `layout_analysis.analysis_progress` 分别呈现 `calculation_status`、`rule_coverage_status`、`assessment_complete`、`action_readiness` 和逐动作 `pending_confirmations`。原 `status` 保持既有含义；不能据 `complete` 自动执行动作，也不能因确认物件无独立规则就继续索取资料。具体状态及计数单位见[风水合同](fengshui.md)。

很多工具返回下面两层快照字段：

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
    "technique": {
      "key": "qimen"
    },
    "selected_sections": ["起盘信息", "九宫方盘"],
    "section_titles_detected": ["起盘信息", "九宫方盘", "离九宫"],
    "export_text": "[起盘信息]\n..."
  }
}
```

要点：

- `run_metadata` 默认附加于成功工具结果，错误和发现接口不保证附带；CLI 可用 `--no-metadata` 关闭
- `run_id` / `trace_id` 是本次响应生成的轻量标识
- `tool_name` 来自 `ToolSpec.run_metadata_name`，由工具声明明确指定
- `generated_at` 是 UTC ISO 8601 时间戳
- `engine` 是从当前 payload 推导出的运行引擎标识
- `engine_is_approximate` 标识轨道近似或被识别的 Moshier / mixed 星历降级；不是所有算法准确性的评级
- `snapshot_text` 是完整的人类可读文本
- `snapshot_export.export_text` 是根据 `selected_sections` 过滤后的导出文本
- `selected_sections` 只裁剪导出层，不会裁掉完整结构化 payload
- 部分工具只有 `snapshot_text`，或仅返回结构化业务数据；完整覆盖见 [算法覆盖的快照协议](algorithm-coverage.md#4-快照协议覆盖)

### 2.3 `selected_sections`

当前请求模型支持 `selected_sections` 的主要入口：

- `bazi_birth`，全部时运与历法 helper；
- `gua_lookup` / `gua_meiyi`、`sanshiunited`；
- 中国术数独立盘（紫微、六壬、奇门、太乙、金口诀）；
- knowledge 工具与 `export_parse`；
- 独立西占推运工具（`solarreturn` 至 `decennials`）。

八字九大专项、核心/关系盘、事件与生命周期、梅花和其他本地占法的请求模型没有此字段。是否有快照、是否有导出、是否接受裁剪参数是三个不同的合同。CLI 用空格分隔多个标题，带空格的单个标题需加引号；紫微命盘的导出 section 是 `起盘信息` / `宫位总览`，单个宫名并非 section。

排查 section 名不生效时，优先看：

- `snapshot_export.section_titles_detected`
- `snapshot_export.missing_selected_sections`

显式非空选择无任何命中时 `export_text` 为空；未命名前言也不会混入显式选择。未传或传空列表时使用工具默认导出规则。快照存在不代表请求支持该字段，请查询对应模型。

### 2.4 三端能力边界

中央目录含 88 条记录；REST 默认公开 86 项，MCP 默认公开 87 项，CLI 可执行 87 条目录命令（另有 `list`、`discover`、`describe`、`profile`）。13 个 family 的能力矩阵按 MCP 集合统计，不能把目录长度当作单端工具数。

| 能力 | REST | MCP / CLI | 差异 |
| --- | --- | --- | --- |
| 独立八字命盘 | `/api/cn/bazi/birth` | `bazi_birth` | 推荐的新接入入口，业务数据在 `bazi_birth` |
| 综合命理分析 | 无独立 REST 路由 | `analyze_destiny` | 使用 `calculate_destiny_analysis`；不能用旧 REST 等同替换 |
| 关系盘 | `/api/astro/relative`（目录 key `astro_relative`） | `astro_relative_chart` | REST 用嵌套 `inner` / `outer`；MCP / CLI 用 `inner_birth_*` / `outer_birth_*` |
| 家居风水 | `/api/fengshui/*` | `fengshui_*` | 七个工具同名三端；CLI 用 JSON `--request-file` 或 JSON 对象／数组参数 |

以 `surfaces` 选择端口名称，不能直接把目录 key 当 MCP 名。`/api/tools` 的 `parameters` 是参数摘要，完整记录另有 `input_schema` / `output_schema`。MCP 实际调用的 `inputSchema` 还包含传输开关，由 `tools/list` 发布。

### 2.5 字段投影与输出体积

| 选项 | REST（POST 查询参数） | MCP | CLI（工具名后） |
| --- | --- | --- | --- |
| 字段投影 | `?fields=bazi_birth.day_master&fields=person_info` | `fields=["bazi_birth.day_master", "person_info"]` | `--fields bazi_birth.day_master person_info` |
| 严格投影 | `?strict_fields=true` | `strict_fields=true` | `--strict-fields` 或 `--strict-fields true` |
| 省略顶层快照文本 | `?include_snapshot_text=false` | `include_snapshot_text=false` | `--no-include-snapshot-text` |
| 紧凑 JSON | HTTP 默认紧凑输出 | `compact=true`（默认） | `--compact` |
| 响应字符预算 | `?response_char_limit=8192`（默认0） | `response_char_limit=8192`（默认8192） | `--response-char-limit 8192`（默认0） |

路径从响应根开始，按本次实际响应对象校验，支持扩展对象键。空选择不投影；数组、标量及 null 应选择整个字段，不支持继续点路径遍历。已附带的 `run_metadata` 完整保留，错误不投影。省略 `snapshot_text` 不会删除 `snapshot_export.export_text`；要进一步控制体积，可仅投影业务字段。

例如 `fengshui_directions` 选择 `fields=["layers.directions.ruleset.version"]` 后，该规则对象仅含 `version`；公开输出 Schema 允许其余字段缺省，原生 MCP 客户端仍可校验成功结果。数组中的规则来源 `sources` 应整块选择，不能使用 `sources.0.title`。各字段保留既有类型校验，缺省不会被补成 null。投影用法见 [Agent 接入指南](agent-guide.md)。

默认 `strict_fields=false` 保留历史投影的数据形状及成功状态，但无效路径明确附加 `projection_warnings`，不会继续静默忽略。例如拼错 `bazi_birth.day_mastr` 会出现 `{"path":"bazi_birth.day_mastr","code":"unknown_projection_path"}`。另外两种代码为 `invalid_projection_path`（空段/空白段）和 `non_object_projection_path`（继续遍历数组/标量）。诊断不受 `fields` 裁剪，也不回显字段值；重复路径只提示一次。

`strict_fields=true` 遇到任何无效路径会整体失败：REST 422、MCP `isError=true`、CLI 退出 1，共享 `validation_error` / `retryable=false` / `issues`，其中 `path` 表示请求的输出路径。计算领域错误优先返回，不会被投影错误覆盖。校验发生在计算后，投影控制返回体积，不减少计算工作。

超出字符预算的成功结果不会切断 JSON。响应保留完整 `run_metadata` 和预算内业务字段，新增 `result_delivery` 明示原结果的 SHA-256、大小、待读取字段、引用及过期时间。MCP 默认8192以适应聊天宿主；REST/CLI 默认0保留历史完整交付。0或4096–65536为合法预算，程序客户端可设0保存全文；聊天不应通过取消预算重新制造大响应。

完整结果是同一 run 的不可变交付物，不是按出生输入命中的计算缓存。MCP 读取 `manifest_uri` 后按 `fatebridge://results/{result_id}/fields/{path}/{offset}` 取得所需点路径；字段读取另支持数组数字索引。完整文档为 `first_page_uri`，每页 `text` 至多2048字符，按 `next_offset` 拼接并核对 `sha256`。每页包装本身是完整 JSON，但文档片段不能单独当全文解析。读取不重新计算、不改变原 run／trace 和原回执。

保留的是字段投影与快照选项处理后的结果。需要全部业务 JSON 或完整时间线时，首次调用用 `fields=null`（REST / CLI 不传字段筛选），保留默认响应预算；需要快照文本时也保留 `include_snapshot_text=true`。先投影摘要后，交付文件无法恢复未选字段。分页读取和本地校验示例见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。

REST 对应 `GET /api/results/{result_id}` 和 `GET /api/results/{result_id}/pages?path=analysis_context.analysis_datetime&offset=0`，沿用 API 鉴权。CLI 也可据 `file_path` 读取本机交付物，按 `file_payload_path`（当前为 `payload`）取出完整原结果，以 `ensure_ascii=false` 和紧凑分隔符序列化后核对响应的 SHA-256；外层记录的文件散列并非该散列。临时目录仅当前系统用户可读，引用约一小时过期，清理按读取／新交付触发，容量最多约64MiB并可回收旧结果；引用失效有明确错误，不以新结果冒充旧 run。MCP 配置隐藏的工具，其结果也不可通过资源读取。

### 2.6 精度与依赖

- 核心占星盘优先使用本地 `swisseph`，缺失时会回退到 FateBridge 内置近似模型
- 西占推运不走近似回退；缺少 `kerykeion` / Swiss Ephemeris 时会直接报错
- `swisseph` 可导入不代表已加载 `.se1` 数据；实际模型检查 `chart_profile.ephemeris_model` 和 `run_metadata.engine_is_approximate`
- 完整说明见 [algorithm-coverage.md](algorithm-coverage.md)，数据配置见 [getting-started.md](getting-started.md#星历数据与精度)

### 2.7 渐进发现与执行提示

场景发现使用 `GET /api/scenarios?detail=summary`，按 `scenario=onda-shiyun` 读取完整 manifest；CLI 对应 `fatebridge scenarios --scenario onda-shiyun --detail full`。10 个场景从 9 个 Onda YAML 接口与住宅路由表生成，包括 `onda-fengshui` 咨询和 `fengshui` 基础计算两个独立入口，保留意图、主证/旁证/深调、条件和替代工具组。`required_inputs` 是技能层采集指引，每个工具的 `required_parameters` 与输入 Schema 才是调用要求；路由不是自动执行计划。

`/api/tools`、CLI `discover` / `list --json` 新增 `scenario` 筛选（CLI 为 `--scenario`），支持逗号并集，与 family / q / surface 取交集。未知场景返回 422 / CLI 退出 1。嵌套 REST 与扁平 MCP/CLI 孪生工具由中央目录关联实际入口。MCP resources 新增 `fatebridge://scenarios` 摘要与 `fatebridge://scenarios/{scenario}` 完整路由；只列当前配置可调用工具，通过 `availability` 和路由组 `available=false` 明示缺失能力，不将旁证升级为主证。

`FATEBRIDGE_MCP_SCENARIOS=onda-jiankang,onda-shiyun` 可缩小 MCP 注册范围；与 family 配置取交集，省略或留空仍公开全部工具。独立的 `reproducibility` 发现字段声明时间与 seed 条件，MCP 幂等标签仍只描述环境影响。

`GET /api/tools` 无参数时保留全量完整记录。可选参数：`detail=summary|full`（REST 默认 full）、`family`（逗号分隔分类）、`q`（名称/分类/描述搜索）、`tool`（精确工具名）和 `surface=rest|mcp|cli`。先请求 `?detail=summary&family=bazi`，选中工具后再请求 `?tool=bazi_birth&detail=full`。摘要不生成或返回参数及输入/输出 Schema。

`counts` 始终表示全局目录数量，`matched_count` 表示筛选后实际返回数量，`detail` 表示记录深度。无匹配关键词返回空列表；非法分类或精确工具名返回带安全 `issues` 的 422。

CLI `discover --family bazi` 默认返回同源 JSON 摘要；`discover --tool bazi_birth --detail full` 获取完整契约。CLI 的 `--query` 对应 REST `q`；`list` 默认文本格式不变，可追加同样的筛选参数及 `--json`。`describe` 保留原有示例与行为。

MCP 默认仍公开全部工具。host 可设置 `FATEBRIDGE_MCP_FAMILIES=bazi,knowledge`，使实际 `tools/list` 与调用注册表只保留这些分类。资源 `fatebridge://catalog/summary` 提供当前公开集合的摘要，`fatebridge://families/{family}` 提供分类摘要，`fatebridge://tools/{tool}` 按需提供单工具完整记录；资源只返回当前 MCP 集合中的工具。隐藏工具的单工具资源及非法资源筛选由标准资源协议报错，无 `isError` 工具结果。资源返回与 REST / CLI 的等效 `surface=mcp` 筛选完全同源。

工具 `annotations` 从 `ToolSpec.execution_hints` 派生，同时出现在三端发现记录中。当前本地计算/查询声明 `readOnlyHint=true`、`destructiveHint=false`、`openWorldHint=false`、`idempotentHint=true`。这些提示描述环境影响，不保证相同结果字节：随机起卦、缺省当前日期和每次运行元数据仍按原规则处理。annotations 是提示，不代替执行权限判断，见 [MCP 工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。

### 2.8 确定性与复现元数据

REST 查询参数与 MCP 参数支持 `as_of`、`trace_id`、`parent_run_id`；CLI 对应 `--as-of`、`--trace-id`、`--parent-run-id`。as_of 为含时区 ISO 8601 时刻，归一化到 UTC，例如 `2024-02-29T16:30:00Z`。省略时捕获本次执行开始时刻；各工具仍按原民用时区解析默认时间，显式日期优先，保留部分日期补齐/截日与流月默认 15 日等规则。上下文按调用隔离，不修改进程时区或全局时间。

标识仅接受 1–128 字符的字母、数字、`_ . : -`。控制项非法为三端校验失败，不回显值；有效 trace / parent 标识传播到成功元数据和模型、领域、投影失败包络。失败可含顶层 `trace_id` / `parent_run_id`；CLI 参数语法错误仍退出 2，框架非法 RPC 与未知工具不属于该包络。

原有六个基础元数据字段保持，新增字段在输出 Schema 中为可选：

- `metadata_schema_version=1.0`、`package_version`、`contract_sha256`：格式、包版本和工具输入/输出模型合同指纹。
- `input_sha256`：模型默认值/别名归一化请求摘要，包含影响真太阳时拒绝语义的显式字段状态，不保存原出生档案。嵌套与扁平合同的输入摘要不承诺相同。
- `business_output_sha256`：投影和快照删减前完整业务 JSON 的摘要，排除 run_metadata；不能直接对部分响应验算。`duration_ms` 测量绑定、服务与业务变换，不含指纹、队列、投影和网络时间。
- `effective_time`、`determinism`、`replay`：本次固定瞬间、读取时区、缺省时间字段、随机性及实际重放参数。
- `runtime`：Python / 平台 / 计算依赖版本、包内实现与 JSON 数据指纹、配置 `.se1` 库存内容指纹。只返回相对文件名；库存不证明实际使用某文件，实际模型保留在 provenance 与业务结果。
- `provenance`、`warnings`：允许列表内的规则/历法/星历口径与标准警告，包括 `current_time_frozen`、`random_seed_generated`、`approximate_engine`，投影后仍保留。

六爻 method=coin 且缺有效手动输入与 seed 时，共享执行层生成本次 seed，仍为随机起卦，返回 `replay.overrides.seed`。手动优先级沿用引擎判定；已有 seed、手动或时间起卦不生成 seed。将原输入与 overrides 合并，再使用 replay.as_of 调用任一入口，可在相同环境重放业务结果；运行 ID、生成时间、耗时及“本次生成 seed”标志仍变化。

实现、内置数据与配置星历指纹按进程缓存；升级或原地修改后须重启。完整复现要求另存原始请求和 receipt，保持实现、合同、规则数据、依赖、平台、时区数据库与星历配置一致。receipt 不是环境锁文件，不能证明版本相同的第三方安装内容未被修改；跨平台浮点仍可能微差。没有数据库、按 ID 查询或服务器保存出生档案。

CLI profile 沿用批量入口，子工具共用 as_of / trace，parent_run_id 指向 profile 根 run_id；`--no-metadata` 关闭根与子元数据。它仍不是 REST/MCP 的复合业务工具。

## 3. 共享请求族

### 3.1 `FateBridgeRequest` 家族

用于：

- `/api/cn/bazi/*`
- `/api/timing/*`

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 默认 `未提供` |
| `gender` | string | 否 | 默认 `未知` |
| `birth_year` | int | 是 | 出生年 |
| `birth_month` | int | 是 | `1..12` |
| `birth_day` | int | 是 | `1..31`，还需满足真实日期 |
| `birth_hour` | int | 是 | `0..23` |
| `birth_minute` | int | 否 | 默认 `0` |
| `birth_place` | string | 否 | 支持中文、英文、拼音地点文本 |
| `birth_timezone` | string | 否 | IANA 时区或 UTC offset |
| `birth_longitude` | float | 否 | `-180..180` |
| `use_true_solar_time` | bool | 否 | 此家族默认 true；显式 false 使用钟表时间 |

中式模型缺省开启真太阳时但没有可解析经度时，会使用钟表时间并附 `resolution_advisory`；显式 true 且无经度则返回错误。时区应显式传入，IANA 名称可表达历史夏令时，固定偏移不能。年/月柱、节气与起运使用实际民用时刻；太阳钟修正用于日/时柱等既有规则。当前小时必填，不提供省略小时的无时盘模式。

九大专项追加 `analysis_year/month/day`、`dayun_pillar`、`liunian_pillar`，`timing_context` 位于 `<dimension>_analysis` 内。时运子模型的必填字段各不相同，例如大运需要 `gender` 与 `analysis_age`；完整规则以 OpenAPI 为准。

### 3.2 `AstroChartRequest` 家族

用于：

- `/api/astro/chart`
- `/api/astro/chart13`
- `/api/astro/hellen`
- `/api/astro/guolao`
- `/api/astro/india`
- `/api/astro/germany`

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 否 | 默认 `未提供` |
| `birth_year` / `birth_month` / `birth_day` / `birth_hour` | int | 是 | 出生日期与时刻 |
| `birth_minute` | int | 否 | 默认 `0` |
| `birth_timezone` | string | 否 | 模型默认 null；服务尝试地点/经度推断，不是固定 UTC，建议显式传入 |
| `birth_longitude` | float | 条件必需 | 某些情况下可由 `birth_place` 推断 |
| `birth_latitude` | float | 条件必需 | 某些情况下可由 `birth_place` 推断 |
| `birth_place` | string | 否 | 支持有限内置地点推断 |
| `hsys` | int | 否 | 离线宫制覆盖；当前支持 `0..8` |
| `zodiacal` | int | 否 | `0=tropical`，`1=sidereal(Lahiri-like)` |
| `use_true_solar_time` | bool | 否 | 默认 false，西占默认使用出生地民用时刻 |

### 3.3 `WesternTimingRequest` 家族

用于：

- `/api/astro/timing`
- `/api/astro/timing/*`

`birth_longitude` 和 `birth_latitude` 在此家族均必填，不能仅靠城市文本替代。除出生信息外，还支持：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `analysis_year` / `analysis_month` / `analysis_day` | int | 目标分析日期 |
| `return_longitude` / `return_latitude` / `return_timezone` | mixed | 返照或行运地点 |
| `house_system` | string | 例如 `P` 表示 Placidus |
| `zodiac_type` | string | 例如 `Tropic` |
| `pd_method` | string | 主限方法 |
| `pd_time_key` | string | 例如 `Ptolemy` / `Naibod` |
| `pd_type` | int | `0=direct`，`1=converse` |
| `pd_aspects` | int[] | 主限相位列表 |
| `show_pd_bounds` | bool | 主限图盘是否带界限层 |
| `selected_sections` | string[] | 仅独立 timing tools 支持 |

完整非法分析日期返回 `validation_error`；只给部分年月日时逐字段补齐默认值，部分日期补齐时可约束到月底。复现计算请显式传齐目标日期、出生时区与返照/行运地点。

### 3.4 本地技法请求约定

`sixyao`、`suzhan`、`otherbu`、`sanshiunited` 等大量本地技法接口共享如下约定：

| 字段 | 说明 |
| --- | --- |
| `date` / `time` | 输入时刻，例如 `2028-04-06` / `09:33:00` |
| `zone` | 时区，常见默认 `+08:00` |
| `lat` / `lon` | 文本化地理提示 |
| `gps_lat` / `gps_lon` | REST / MCP 使用同一字段名，CLI 使用 `--gps-lat` / `--gps-lon` |
| `selected_sections` | 快照导出裁剪 |

### 3.5 双人关系请求

`/api/compatibility` 使用两套 `person1_*` / `person2_*` 出生字段（姓名和年月日时必填）；宿曜相性使用两套 `person1_date/time` / `person2_date/time` 等起盘字段。

`/api/astro/relative` 使用 `inner` / `outer` 对象，每个对象含 `birth_year/month/day/hour/longitude/latitude`；MCP / CLI `astro_relative_chart` 将它们展开为 `inner_birth_*` / `outer_birth_*`。模式兼容语义见 [algorithm-coverage.md](algorithm-coverage.md#32-关系盘astro_relative_chart)。

## 4. REST 端点家族

### 4.1 基础命理与配合

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cn/bazi/birth` | 独立八字命盘 |
| `POST` | `/api/compatibility` | 双人配合分析 |
| `POST` | `/api/compatibility/sukuyo` | 宿曜双人相性分析（三九の秘法，二十七宿） |

#### 4.1.1 八字九大专项维度

> 九个维度均同时提供 REST / MCP / CLI。大运、流年缺省由命盘 + 分析日期内部推算，也可传 `dayun_pillar` / `liunian_pillar` 覆盖以输出时机信号（详见 README）。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cn/bazi/marriage` | 八字婚姻分析 |
| `POST` | `/api/cn/bazi/career` | 八字事业分析 |
| `POST` | `/api/cn/bazi/wealth` | 八字财运分析 |
| `POST` | `/api/cn/bazi/health` | 八字健康分析 |
| `POST` | `/api/cn/bazi/children` | 八字子女分析 |
| `POST` | `/api/cn/bazi/education` | 八字学业分析 |
| `POST` | `/api/cn/bazi/personality` | 八字性格分析 |
| `POST` | `/api/cn/bazi/relatives` | 八字六亲分析 |
| `POST` | `/api/cn/bazi/romance` | 八字正缘桃花分析 |

#### 4.1.2 九大专项维度返回字段

每个维度返回结构化分析对象，同时在 `<dimension>_analysis.timing_context` 中回显内部推算的大运/流年与起运年龄。各维度核心字段：

| 维度 | 端点 | 主要返回字段 |
| --- | --- | --- |
| 婚姻 | `/api/cn/bazi/marriage` | `spouse_star`（配偶星：正/偏财为妻、正官/七杀为夫）、`spouse_palace`（配偶宫=日支稳定性）、`marriage_quality`（0–100 评分）、`marriage_timing`、`risk_factors`、`suggestions` |
| 事业 | `/api/cn/bazi/career` | `dominant_ten_gods`（事业类型）、`industry_analysis`（喜用神行业）、`career_structure`、`entrepreneurship`（创业 vs 打工）、`career_timing`、`noble_direction`（贵人方位）、`suggestions` |
| 财运 | `/api/cn/bazi/wealth` | `wealth_stars`（正/偏财含藏干）、`wealth_structure`（身财两停/财多身弱…）、`wealth_storage`（墓库财）、`wealth_style` / `wealth_direction`、`wealth_risk`、`wealth_timing` |
| 健康 | `/api/cn/bazi/health` | `constitution`（强弱+调候）、`organ_analysis`（五行脏腑）、`disease_risks`、`health_timing`、`regimen`（仅命理参考，非医学诊断） |
| 子女 | `/api/cn/bazi/children` | `child_star`（男命官杀/女命食伤）、`child_palace`（时柱）、`affinity`、`relationship`、`children_timing` |
| 学业 | `/api/cn/bazi/education` | `study_stars`（印/食伤/官/财）、`education_level`、`wenchang`（文昌）、`subject_orientation`（文理）、`exam_timing` |
| 性格 | `/api/cn/bazi/personality` | 日主五行心性、主导十神性格、刚柔内外向、优劣势与调适建议 |
| 六亲 | `/api/cn/bazi/relatives` | 父母星（偏财/正印）、兄弟姐妹星（比劫）、六亲宫位、贵人助力 |
| 正缘桃花 | `/api/cn/bazi/romance` | 桃花（咸池）、红鸾天喜、异性缘星（按性别）、桃花正邪、正缘时机（区别于侧重配偶宫的「婚姻」维度） |

> **大运/流年自动推算**：缺省由命盘 + 分析日期（默认今天，或传 `analysis_year`/`analysis_month`/`analysis_day`）内部推算；如需指定，传 `dayun_pillar` / `liunian_pillar`（如 `"甲子"`）覆盖。

### 4.2 时运分析

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/timing/comprehensive` | 综合时运 |
| `POST` | `/api/timing/dayun` | 大运 |
| `POST` | `/api/timing/liunian` | 流年 |
| `POST` | `/api/timing/liuyue` | 流月 |
| `POST` | `/api/timing/liuri` | 流日 |
| `POST` | `/api/timing/liushi` | 流时 |
| `POST` | `/api/timing/jieqi` | 全年节气节点时间轴 |

### 4.3 Calendar / knowledge / export helper

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cn/jieqi/year` | 全年节气 helper |
| `POST` | `/api/cn/nongli/time` | 农历换算 helper |
| `POST` | `/api/divination/gua` | 卦义检索 |
| `POST` | `/api/cn/gua/meiyi` | 梅易卦义批量查询 |
| `POST` | `/api/export/registry` | 导出合同注册表 |
| `POST` | `/api/export/parse` | 快照文本解析 |
| `POST` | `/api/knowledge/registry` | 内置知识目录 |
| `POST` | `/api/knowledge/read` | 内置知识条目读取 |

### 4.4 Divination 与本地技法

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/divination/meihua` | 梅花易数时卦 |
| `POST` | `/api/divination/tongshefa` | 统摄法 |
| `POST` | `/api/divination/sixyao` | 六爻 |
| `POST` | `/api/divination/canping` | 邵子参评数 / 金锁银匙 |
| `POST` | `/api/divination/heluo` | 河洛理数 |
| `POST` | `/api/divination/suzhan` | 宿占 |
| `POST` | `/api/divination/otherbu` | 占星骰子 / otherbu |
| `POST` | `/api/divination/sanshiunited` | 三式合一 |

### 4.5 中国术数独立盘

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/cn/ziwei/birth` | 紫微斗数命盘 |
| `POST` | `/api/cn/ziwei/horoscope` | 紫微斗数运限（大限/小限/流年/流月/流日/流时 + 动态四化） |
| `POST` | `/api/cn/ziwei/rules` | 紫微规则库 |
| `POST` | `/api/cn/liureng/gods` | 六壬起课 |
| `POST` | `/api/cn/liureng/runyear` | 六壬行年 |
| `POST` | `/api/cn/qimen` | 奇门遁甲 |
| `POST` | `/api/cn/taiyi` | 太乙神数 |
| `POST` | `/api/cn/jinkou` | 金口诀 |

### 4.6 核心占星盘

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/chart` | 标准盘 |
| `POST` | `/api/astro/chart13` | 13 扇区扩展盘 |
| `POST` | `/api/astro/hellen` | 希腊风格盘 |
| `POST` | `/api/astro/guolao` | 果老 / 七政四余风格盘 |
| `POST` | `/api/astro/india` | 印度 sidereal 盘 |
| `POST` | `/api/astro/germany` | 中点 / germany 派生盘 |
| `POST` | `/api/astro/relative` | 关系盘 |

### 4.7 西占推运

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/timing` | 推运总览 bundle |
| `POST` | `/api/astro/timing/solarreturn` | 太阳返照 |
| `POST` | `/api/astro/timing/lunarreturn` | 月返 |
| `POST` | `/api/astro/timing/transit` | 行运 |
| `POST` | `/api/astro/timing/solararc` | 太阳弧 |
| `POST` | `/api/astro/timing/givenyear` | 指定年盘 |
| `POST` | `/api/astro/timing/profection` | 年小限 |
| `POST` | `/api/astro/timing/pd` | 主限 |
| `POST` | `/api/astro/timing/pdchart` | 主限图盘 |
| `POST` | `/api/astro/timing/zr` | 黄道释放 |
| `POST` | `/api/astro/timing/firdaria` | 法达 |
| `POST` | `/api/astro/timing/decennials` | 十年星限 |

聚合推运与上述 11 个单项工具共用目标时间合同：`analysis_year`、
`analysis_month`、`analysis_day` 指定日期，`analysis_hour`（0–23）与
`analysis_minute`（0–59）指定小时和分钟，按 `birth_timezone` 解释。
显式传入 `0` 会生效。为保持日期级调用兼容，省略小时或分钟时分别沿用
`birth_hour` 或 `birth_minute`；省略的日期分量仍由当前时间（可用 `as_of` 冻结）
补齐。`as_of` 不替代显式分析时刻，`return_timezone` 只将同一时刻转换到返照／
行运地点，不重解释输入钟时。出生参数始终用于本命盘。

REST 在 JSON 请求体传入这五项，MCP 使用同名参数，CLI 使用
`--analysis-year/month/day/hour/minute` 对应的独立开关。实际采用时刻见
`analysis_context.analysis_datetime`，行运地点的时刻见聚合结果的
`transits.current_transit.analysis_datetime` 或独立工具的 `transit.analysis_datetime`。

### 4.8 事件占星（事件盘）

求解天文时刻后起盘的一组事件类工具。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/event/mundane` | 世俗入宫盘 |
| `POST` | `/api/astro/event/extrareturns` | 多重回归 |
| `POST` | `/api/astro/event/horary` | 卜卦判断 |
| `POST` | `/api/astro/event/election` | 择日 |

### 4.9 全生命周期 / 寿命技法

读取单张本命盘的一组全生命周期（寿命）技法。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/lifespan/harmonic` | 调波盘 |
| `POST` | `/api/astro/lifespan/planetary_ages` | 行星年龄 |
| `POST` | `/api/astro/lifespan/triplicity_rulers` | 三分主星推运 |
| `POST` | `/api/astro/lifespan/lunation_phase` | 月相推运 |
| `POST` | `/api/astro/lifespan/distributions` | 界推运 |
| `POST` | `/api/astro/lifespan/balbillus` | Balbillus 129 年系统 |
| `POST` | `/api/astro/lifespan/keypoints` | 数字相位推运 |
| `POST` | `/api/astro/lifespan/yearsystem129` | 129 年系统 |
| `POST` | `/api/astro/lifespan/planetaryarc` | 行星弧方向 |
| `POST` | `/api/astro/lifespan/persiandirected` | 波斯向运 |
| `POST` | `/api/astro/lifespan/agepoint` | 年龄推进点 (age point) |
| `POST` | `/api/astro/lifespan/vedicprog` | 恒星推运 |
| `POST` | `/api/astro/lifespan/jaynesprog` | 赤纬推运 |

### 4.10 健康检查与能力发现

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `GET` | `/health` | 存活检查，返回 `{"status":"healthy"}`，不验证全部算法依赖 |
| `GET` | `/ready` | 必需检查决定 `ready` / `not_ready`；可选西占运行时失败不一定改变状态，需检查 `checks` |
| `GET` | `/metrics` | Prometheus 文本指标，含请求计数、耗时、就绪与鉴权配置状态 |
| `GET` | `/api/scenarios` | 场景摘要或完整路由；支持 `scenario`、`surface` 与 `detail` |
| `GET` | `/api/results/{result_id}` | 同次结果的交付 manifest，沿用业务鉴权 |
| `GET` | `/api/results/{result_id}/pages` | 字符分页；`offset` 指定偏移，`path` 可选字段路径 |
| `GET` | `/api/tools` | 能力清单：返回每个工具的自描述记录（参数、类型、所在端、family），与 `fatebridge describe` 同源 |

`/api/tools` 是给 Agent 的机读能力清单——无需抓取本文档即可枚举全部工具及调用约定。
返回结构包含 `counts`（rest / mcp / total）、`matched_count`、`detail` 与 `tools`，其中每个完整
descriptor 形如：

```json
{
  "tool": "bazi_wealth",
  "summary": "八字财运分析：已按出生资料与分析日期自动推算大运、流年和时机依据；首轮无需先调用 timing_analysis 或手动传大运柱。仅有明确外部口径时用 dayun_pillar / liunian_pillar 覆盖。",
  "operation_label_zh": "八字财运分析",
  "family": "bazi",
  "surfaces": {"cli": true, "cli_name": "bazi_wealth", "rest_path": "/api/cn/bazi/wealth", "mcp_name": "bazi_wealth"},
  "parameters": [{"name": "birth_year", "type": "int", "required": true, "description": "..."}]
}
```

> 面向 Agent / 开发者的端到端接入说明（自助发现、错误处理、字段投影、MCP host 配置、Python/JS 示例）见 [agent-guide.md](agent-guide.md)。

`surfaces.rest_path` / `surfaces.mcp_name` 为 `null` 表示该工具不在对应端暴露。

### 4.11 家居风水（family `fengshui`）

| REST POST | MCP / CLI | 说明 |
| --- | --- | --- |
| `/api/fengshui/directions` | `fengshui_directions` | 后天八卦固定宫数与八方／24山角区索引 |
| `/api/fengshui/minggua` | `fengshui_minggua` | 出生日期／有效生年／出生时刻三选一、男女约定的命卦与个人八方关系 |
| `/api/fengshui/bazhai` | `fengshui_bazhai` | 坐山宅盘、逐人命盘、门床桌灶位置／朝向分开判定 |
| `/api/fengshui/jinsuo` | `fengshui_jinsuo` | 已确认观察的八宫砂水偏好；未知与混合不推断 |
| `/api/fengshui/annual_stars` | `fengshui_annual_stars` | 立春换年的九宫年星、有效区间、独立列示当前元运 |
| `/api/fengshui/xuankong_natal` | `fengshui_xuankong_natal` | 中州派运山向宅盘、历史定运、兼向替星及边界候选；独立于年星 |
| `/api/fengshui/assess` | `fengshui_assess` | 原始盘与布局关联、室内形态观察、按目标的元素候选、限定年度作者规则、来源与分歧 |

输入不继承完整八字生辰要求；命卦可用 `birth_date`、`effective_birth_year` 或 `birth_at` 三选一，年度使用 `effective_year` 或 `query_at` 二选一。角度须声明参考北。组合结果在 `layers.bazhai`、`layers.jinsuo`、`layers.annual_stars`、`layers.xuankong_natal` 中分别返回，合法缺失资料用 `status=partial`，不是协议错误。月飞星和金锁进阶规则不在此版；没有三法总分。每层带规则版本、来源和范围，快照记录同一组分层计算事实。

三端可复制示例、详细字段语义及来源限制见 [家居风水](fengshui.md)。CLI 示例：`fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json`。MCP 参数为同一文件内容的 JSON 对象；REST 请求体同理。`--request-file` 保留未知字段交给模型拒绝，显式字段参数覆盖同名顶层字段。

## 5. REST 调用示例

以下示例默认未开启 API Key 鉴权；开启后加 `-H "X-API-Key: <secret>"`。

### 5.1 旧入口迁移

`/api/calculate` 和 CLI `calculate_legacy` 已移除。独立八字命盘使用 `/api/cn/bazi/birth` 或 `bazi_birth`，命盘字段位于 `bazi_birth` 对象；综合命理使用 MCP / CLI 的 `analyze_destiny`。完整模块与字段替换见 [迁移指南](migration.md)。

### 5.2 核心占星盘

```bash
curl -X POST http://localhost:8010/api/astro/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990,
    "birth_month": 4,
    "birth_day": 6,
    "birth_hour": 9,
    "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667,
    "birth_latitude": 31.2167,
    "birth_place": "上海"
  }'
```

返回重点：

- `chart_profile.engine_precision`
- `angles`
- `houses`
- `planets`
- `aspects`
- `snapshot_text`
- `snapshot_export`

### 5.3 独立西占技法

```bash
curl -X POST http://localhost:8010/api/astro/timing/solarreturn \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SR Demo",
    "birth_year": 1990,
    "birth_month": 4,
    "birth_day": 6,
    "birth_hour": 9,
    "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667,
    "birth_latitude": 31.2167,
    "birth_place": "上海",
    "analysis_year": 2028,
    "analysis_month": 4,
    "analysis_day": 6,
    "analysis_hour": 12,
    "analysis_minute": 0,
    "selected_sections": ["起盘信息", "星盘信息"]
  }'
```

返回重点：

- `snapshot_text`
- `snapshot_export.selected_sections`
- `snapshot_export.export_text`

### 5.4 导出解析 helper

```bash
curl -X POST http://localhost:8010/api/export/parse \
  -H "Content-Type: application/json" \
  -d '{
    "technique": "qimen",
    "content": "[起盘信息]\n示例\n\n[九宫方盘]\n示例",
    "selected_sections": ["起盘信息"]
  }'
```

## 6. FastMCP 工具面

### 6.1 启动

```bash
python -m fatebridge.mcp_server
```

### 6.2 MCP 工具分组

> 全部 87 个 MCP 工具按 `family` 分组如下，各端绑定差异见 §2.4。机读清单见 `GET /api/tools` 或 `fatebridge list`。

#### 基础命理（family `bazi`）

- `analyze_destiny`
- `bazi_birth`
- `bazi_marriage` / `bazi_career` / `bazi_wealth` / `bazi_health` / `bazi_children`
- `bazi_education` / `bazi_personality` / `bazi_relatives` / `bazi_romance`

#### 双人配合（family `compatibility`）

- `two_person_compatibility`
- `sukuyo_compatibility`

#### 时运与历法（family `timing`）

- `timing_analysis`
- `dayun_analysis` / `liunian_analysis` / `liuyue_analysis` / `liuri_analysis` / `liushi_analysis`
- `jieqi_timeline_analysis`
- `jieqi_year` / `nongli_time`

#### Divination 与本地技法（family `divination`）

- `gua_lookup` / `gua_meiyi`
- `meihua_analysis` / `tongshefa` / `sixyao`
- `canping` / `heluo`
- `suzhan` / `otherbu` / `sanshiunited`

#### 中国术数独立盘（family `metaphysics`）

- `ziwei_birth` / `ziwei_horoscope` / `ziwei_rules`
- `liureng_gods` / `liureng_runyear`
- `qimen` / `taiyi` / `jinkou`

#### export / knowledge helper

- `export_registry` / `export_parse`
- `knowledge_registry` / `knowledge_read`

#### 核心占星盘（family `astro`）

- `astro_chart` / `astro_chart13` / `astro_hellen_chart`
- `astro_guolao_chart` / `astro_india_chart` / `astro_germany_chart`
- `astro_relative_chart`

#### 西占推运（family `western_timing` / `western_timing_tool`）

- `western_timing_analysis`
- `solarreturn` / `lunarreturn` / `transit` / `solararc` / `givenyear`
- `profection` / `pd` / `pdchart` / `zr` / `firdaria` / `decennials`

#### 事件占星（family `western_event`）

- `astro_mundane` / `astro_extrareturns` / `astro_horary` / `astro_election`

#### 全生命周期 / 寿命技法（family `western_lifespan`）

- `astro_harmonic` / `astro_planetary_ages` / `astro_triplicity_rulers` / `astro_lunation_phase`
- `astro_distributions` / `astro_balbillus` / `astro_keypoints` / `astro_yearsystem129`
- `astro_planetaryarc` / `astro_persiandirected` / `astro_agepoint` / `astro_vedicprog` / `astro_jaynesprog`

#### 家居风水（family `fengshui`）

- `fengshui_directions` / `fengshui_minggua` / `fengshui_bazhai` / `fengshui_jinsuo`
- `fengshui_annual_stars` / `fengshui_xuankong_natal` / `fengshui_assess`

住宅输入、分层响应与复杂 CLI 用法见 [家居风水接口](#411-家居风水family-fengshui)。

### 6.3 MCP 与 REST 的差异

| 维度 | REST | FastMCP |
| --- | --- | --- |
| 传输协议 | HTTP JSON | MCP tool call |
| 返回格式 | JSON object | `structuredContent` JSON object + 等价 JSON 文本 |
| 错误表现 | HTTP status + 顶层错误 JSON（不嵌套 `detail`） | 模型/业务错误为 `isError=true` + 统一错误包络；协议错误由框架处理 |
| 使用场景 | Web / script / service integration | Agent host / tool invocation |

## 7. 常见响应字段

### 7.1 命理类

- `person_info`
- `four_pillars`
- `day_master`
- `element_distribution`
- `favorable_elements`
- `structure_profile`
- `ten_gods`
- `patterns`
- `calendar_context`

兼容性分析相关字段补充：

- `detailed_analysis.favorable_synergy.score_basis`
- `detailed_analysis.favorable_synergy.useful_ten_gods_support`
- `detailed_analysis.ten_gods_relationship.supportive_patterns`
- `detailed_analysis.ten_gods_relationship.risk_reasons`
- `detailed_analysis.pattern_synergy.supportive_patterns`
- `detailed_analysis.pattern_synergy.tension_patterns`
- `detailed_analysis.pattern_synergy.risk_patterns`

备注：

- `pattern_synergy.tension_patterns` 中的 `天克地冲` 默认视为高吸引/高摩擦并存的张力型组合，不再直接等同于纯负面结论

### 7.2 占星类

- `chart_profile`
- `angles`
- `houses`
- `planets`
- `aspects`
- `interpretation`
- `snapshot_text`
- `snapshot_export`

### 7.3 推运类

- `summary`
- `analysis_context`
- 各 technique payload，例如 `solar_return`、`primary_directions`、`firdaria`
- `snapshot_text`
- `snapshot_export`

## 8. 调试建议

### 8.1 section 名称不匹配

优先检查：

- `snapshot_export.section_titles_detected`
- `snapshot_export.missing_selected_sections`

### 8.2 占星盘精度不如预期

优先检查：

- `chart_profile.engine_precision`
- `chart_profile.engine_backend`
- `chart_profile.ephemeris_model`
- `run_metadata.engine_is_approximate`

### 8.3 西占推运直接报错

优先检查本地是否具备：

- `kerykeion`
- Swiss Ephemeris 运行时

## 9. 进一步阅读

- [getting-started.md](getting-started.md)
- [architecture.md](architecture.md)
- [algorithm-coverage.md](algorithm-coverage.md)
- [troubleshooting.md](troubleshooting.md)
