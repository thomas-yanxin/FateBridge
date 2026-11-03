# FateBridge API 参考

正确调用一项计算，需要先确认输入要求、公开入口和结果结构。REST、MCP 与 CLI 的公共约定、请求族、路由映射及响应字段集中列在下方，供应用开发者与 Agent 维护者查询，并据此处理精度说明与错误信息。

首次运行请先看[快速入门](getting-started.md)，可复制的客户端代码见[接入指南](agent-guide.md)，按日常问题选择方法见[场景路由](scenario-routing.md)。

当前实际暴露 91 个业务 REST 路由（另含 `/health`、`/ready`、`/metrics` 三个运维端点）和 92 个 FastMCP 工具。两个数字由中央目录派生，并由 `tests/test_doc_tool_counts.py` 锁定。版本之间的准确字段约束以当前服务的 `/openapi.json`、MCP `tools/list` 或 CLI `describe` 为准。

## 阅读导航

| 要查什么 | 章节 |
| --- | --- |
| 错误、快照、三端映射、投影、复现 | [公共约定](#2-公共约定) |
| 主题限制与调用前检查 | [咨询范围与禁区校验](#咨询范围与禁区校验) |
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
- 业务输入：JSON 请求体；通用控制项：URL 查询参数
- 完整 Schema：`/openapi.json`；能力发现：`/api/tools`

例如 `POST /api/cn/bazi/birth?fields=bazi_birth.day_master&strict_fields=true` 的请求体只放出生信息。多个 `fields` 重复写查询参数；不要放进请求体，未知请求字段会被拒绝。

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

玄空内部盘数、身份或飞行记录矛盾返回 `fengshui_calculation_inconsistent`（503、`retryable=false`），`issues.path=runtime.fengshui.natal_chart`。此时无有效盘可交付；不能修改用户资料、丢弃失败候选或以字段投影绕过，维护者须修复计算一致性。详见[计算盘异常处理](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/fengshui-source-comparison.md#计算盘异常会停止交付)。

常见状态码：

- `400`：模型校验通过后的领域输入错误
- `422`：请求字段缺失、类型/范围/枚举错误、未知字段、完整公历日期无效；REST 非法 JSON
- `401`：缺少或无效的 API key（仅在配置了密钥时）
- `500`：服务内部异常
- `503`：能力依赖缺失，或领域计算／来源一致性检查拒绝交付；按实际 `error_code` 和 `retryable` 处理
- `504`：计算超时

`retryable` 是响应的实际重试提示，不能只由状态码推断。框架的未知路由 / 方法错误（404 / 405）不属于业务错误合同。CLI 工具调用成功退出 0，计算失败退出 1，用法错误/不支持退出 2；`list` 和 `--help` 输出文本。

模型校验错误带有 `issues`，每项包含字段 `path`、稳定错误 `code` 和可选 `constraints`，不回显输入值。未知字段会被拒绝；显式非法的 `astro_election.topic_id`、`astro_horary.category` 或 `two_person_compatibility.relationship_type` 不回退为其他主题或 `general`。关系类型只接受 `general/marriage/friendship/business/family`，省略时为 `general`。省略其他可选字段仍使用声明的默认值。CLI 的未知 flag 或 argparse 类型错误属于用法错误（退出 2），进入请求模型后的校验失败属于计算失败（退出 1）。

REST OpenAPI、MCP `tools/list`、`/api/tools` 和 CLI `describe` 发布中央目录的输入与输出 Schema。成功结果在字段投影前校验，输出违规属于 `internal_error`，不归责于请求参数。合同覆盖根字段，以及主限命中与坐标、时主递归子限、寿限时间线、古典与关系盘、紫微星曜、六壬四课三传、奇门宫位、太乙核心盘和地方术数条目，以及九类八字专题、宿曜双向关系、知识覆盖/查询与导出模板/分段/动态设置等稳定嵌套事实。动态星体、卦码和规则键保持开放，但已声明的字典值与列表条目会校验；解释文本和未声明扩展继续允许。业务字段可选且允许 null，以兼容 `fields` 投影、既有可空事实与 CLI 全局 `--no-metadata`；Schema 不保证完整结果的每个字段必定存在。校验不重序列化响应，因此不补默认值、不删除扩展字段、不改写原数值。OpenAPI 使用稳定 `operationId`，并在启用 REST 密钥时声明实际鉴权要求。合同回归见 [专业嵌套合同测试](../tests/test_agentic_nested_outputs.py) 和 [八字专题、宿曜及知识/导出合同测试](../tests/test_agentic_domain_outputs.py)。

### 2.2 快照协议

完整计算另有中央目录声明的 `required_output_fields`，通过发现记录的 `full_result_required_fields` 公开，并参与 `contract_sha256`。这些必需业务根缺失或为 null 时，共享执行返回 `internal_error`，不会只生成 metadata 冒充成功；字段投影在这项验证之后执行，仍可合法省略业务根。此保护不宣称所有嵌套可选事实都必须存在。领域返回的错误包络也须符合 `ErrorEnvelope`，缺错误事实或错误码／retryable 的异常结果归为内部错误，保留有效 trace／parent。

事业结构与创业规则索引的 `score_kind=uncalibrated_rule_index`、`scope`、`score_basis` 明确所选规则的范围和基准／加减／限制；`weighted_counts`包含日支全部藏干，分数及十神信号不测量实际能力、收入或创业成功率。`legacy_level/legacy_tendency`仅供旧标签迁移，不作为原典裁定。

事业方向的 `dominant_ten_gods` 同时保留完整计权、最高及第三位的全部并列、计数口径与现代映射范围；`primary_career_type`在最高权重并列时一起列出各标签。事业结构与创业部分的 `formation_status=heuristic_candidate_only`、`rule_signals` 和 `unverified_conditions` 区分共现线索与尚未验证的古典成格条件。综合与九专题可用公开`classical_routes`字段视图核对所选月令、星位节点和原典生克合路径，视图名不是请求参数。日期级专项的 `timing_context.analysis_datetime/timezone/anchor_policy` 回显本地零点锚点，`boundary_status` 标明是否立春年界日；交节当日的具体钟时须取相应小时级时运结果，不能用零点代表全天。

`ziwei_horoscope.analysis_context` 回显实际目标时刻与时区，原出生校正信息保留在 `birth_context`。运限 `scopes[].palace_name/natal_palace_name` 指命宫活动索引所临的本命宫，`scope_palace_role` 明确其角色；`mutagen_natal_links` 将本层四化星关联到实际本命星曜及宫位，保留本命四化与本层四化的区别。新增 `palace_map` 单独列出本层十二宫功能名与本命星位的映射，四化连接另标 `scope_palace_name`；不能把本命官禄误叫流年官禄。这仍不包含全部流曜或飞宫体系。三个紫微工具共用 `rule_profile`；运限可独立指定 `target_minute` / `target_timezone`，默认 0 / Asia/Shanghai。规则版本、资料来源和独立验收见[紫微文档](ziwei.md)。

`ziwei_horoscope.natal_prerequisites` 携带本次运限计算内部已经使用的本命农历、年干、时支、命身宫、五行局及三条原始推导轨迹。需要解释起大限岁数或局数来源时，读取已发布的 `evidence_views.natal_prerequisites` 所列字段；视图名本身不是请求参数。该链没有另起本命计算 run，也不证明公历换算或古典岁首政策。出生排盘年干、出生民用参考岁序和目标流层天干分别保留，不能互相替代；各条 `source_comparison` 的原典核对范围仍按其自身声明解释。

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

中央目录含 93 条记录；REST 默认公开 91 项，MCP 默认公开 92 项，CLI 可执行 92 条目录命令（另有 `list`、`discover`、`describe`、`profile`）。13 个 family 的能力矩阵按 MCP 集合统计，不能把目录长度当作单端工具数。

| 能力 | REST | MCP / CLI | 差异 |
| --- | --- | --- | --- |
| 独立八字命盘 | `/api/cn/bazi/birth` | `bazi_birth` | 推荐的新接入入口，业务数据在 `bazi_birth` |
| 综合命理分析 | 无独立 REST 路由 | `analyze_destiny` | 使用 `calculate_destiny_analysis`；不能用旧 REST 等同替换 |
| 关系盘 | `/api/astro/relative`（目录 key `astro_relative`） | `astro_relative_chart` | REST 用嵌套 `inner` / `outer`；MCP / CLI 用 `inner_birth_*` / `outer_birth_*` |
| 家居风水 | `/api/fengshui/*` | `fengshui_*` | 八个工具同名三端；CLI 用 JSON `--request-file` 或 JSON 对象／数组参数 |

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

超出字符预算的成功结果不会切断 JSON。响应保留运行标识、散列与预算内业务字段，新增 `result_delivery` 明示原结果的 SHA-256、大小、待读取字段、引用及过期时间。MCP 默认8192以适应聊天宿主；REST/CLI 默认0保留历史完整交付。0或4096–65536为合法预算，程序客户端可设0保存全文；聊天不应通过取消预算重新制造大响应。

完整结果超过输出预算且运行环境较长时，`run_metadata.runtime` 只在行内保留环境散列、清单散列 `ephemeris_inventory_sha256`、文件数 `ephemeris_files_count` 及 `delivery_path`。`result_delivery.deferred_fields` 明列 `run_metadata.runtime`；按该点路径读取可恢复完整运行环境及每个文件散列，清单没有被当作空集合或静默截断。预算为0时仍返回原完整回执。首轮业务分析优先保持可读。

业务字段仍接近预算上限时，可再把补充回执`run_metadata.provenance`、`run_metadata.determinism`留在同次交付物中，并在`deferred_fields`逐项明列。只有在此举能保留全部业务字段时才采用；运行标识、输入／契约／业务散列及环境指纹仍行内可见。读取对应点路径可精确恢复原回执，不重新计算、不缩减业务事实或提高预算。

完整结果是同一 run 的不可变交付物，不是按出生输入命中的计算缓存。MCP 读取 `manifest_uri` 后按 `fatebridge://results/{result_id}/fields/{path}/{offset}` 取得所需点路径；字段读取另支持数组数字索引。完整文档为 `first_page_uri`，每页 `text` 至多2048字符，按 `next_offset` 拼接并核对 `sha256`。每页包装本身是完整 JSON，但文档片段不能单独当全文解析。读取不重新计算、不改变原 run／trace 和原回执。

保留的是字段投影与快照选项处理后的结果。需要全部业务 JSON 或完整时间线时，首次调用用 `fields=null`（REST / CLI 不传字段筛选），保留默认响应预算；需要快照文本时也保留 `include_snapshot_text=true`。先投影摘要后，交付文件无法恢复未选字段。分页读取和本地校验示例见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。

REST 对应 `GET /api/results/{result_id}` 和 `GET /api/results/{result_id}/pages?path=analysis_context.analysis_datetime&offset=0`，沿用 API 鉴权。CLI 也可据 `file_path` 读取本机交付物，按 `file_payload_path`（当前为 `payload`）取出完整原结果，以 `ensure_ascii=false` 和紧凑分隔符序列化后核对响应的 SHA-256；外层记录的文件散列并非该散列。临时目录仅当前系统用户可读，引用约一小时过期，清理按读取／新交付触发，容量最多约64MiB并可回收旧结果；引用失效有明确错误，不以新结果冒充旧 run。MCP 配置隐藏的工具，其结果也不可通过资源读取。

精简引用可省略重复的首分页URI及本地文件定位，以保留行内业务和来源事实；此时从`manifest_uri`对应的同次清单恢复定位。清单本身与原交付物保持完整，响应预算不变。

确定性校验读取使用`GET /api/results/{result_id}/verified?expected_sha256=原散列&expected_run_id=原run`，另可传`path`和`offset`。CLI对应`fatebridge result-read RESULT_ID --sha256 ORIGINAL_SHA256 --run-id ORIGINAL_RUN_ID [--path FIELD_PATH] [--offset 0]`；MCP资源为`fatebridge://results/{result_id}/verified/{run_id}/{sha256}/{offset}`及`.../verified/{run_id}/{sha256}/fields/{path}/{offset}`。它们先对完整保留payload执行原序列化SHA-256和run一致性检查，再从同一内存对象选页，均不重算；错散列、错run、损坏内容或失效引用明确失败，MCP仍限制原工具公开范围。`verification.payload_sha256`是整包核验，外层`sha256`是所选字段文档核验；`text/next_offset`的分页含义不变。它不是业务计算工具，不计入领域工具数量。核验一次需读取完整payload，按需选择字段和页，不能用核验成功代替业务内容已读。

校验读取支持只读沙箱：只检查已发布的私有目录和文件，不创建临时探测文件、锁文件或索引，不删除过期结果；写入和回收仍由原锁保护。并发回收可能返回不可用，不一致的载荷与清单不能获核验。CLI可用`--directory 原交付文件所在私有目录`指定已有目录；默认按结果ID查找既有临时存储，若同ID匹配多个目录则报`result_directory_ambiguous`，不会靠散列挑选副本。指定目录不创建目录、不改变原保留期限。

### 2.6 精度与依赖

- 核心占星盘优先使用本地 `swisseph`，缺失时会回退到 FateBridge 内置近似模型
- 西占推运不走近似回退；缺少 `kerykeion` / Swiss Ephemeris 时会直接报错
- `swisseph` 可导入不代表已加载 `.se1` 数据；实际模型检查 `chart_profile.ephemeris_model` 和 `run_metadata.engine_is_approximate`
- 完整说明见 [algorithm-coverage.md](algorithm-coverage.md)，数据配置见 [getting-started.md](getting-started.md#星历数据与精度)

### 2.7 渐进发现与执行提示

场景发现使用 `GET /api/scenarios?detail=summary`，按 `scenario=onda-shiyun` 读取完整 manifest；CLI 对应 `fatebridge scenarios --scenario onda-shiyun --detail full`。14 个场景从13个 Onda YAML 接口、共享规则与住宅路由表生成，包括 `onda-fengshui` 咨询和 `fengshui` 基础计算两个独立入口，保留意图、主证/旁证/深调、条件和替代工具组。`required_inputs` 是技能层采集指引，每个工具的 `required_parameters` 与输入 Schema 才是调用要求；路由不是自动执行计划。

`/api/tools`、CLI `discover` / `list --json` 新增 `scenario` 筛选（CLI 为 `--scenario`），支持逗号并集，与 family / q / surface 取交集。未知场景返回 422 / CLI 退出 1。嵌套 REST 与扁平 MCP/CLI 孪生工具由中央目录关联实际入口。MCP resources 新增 `fatebridge://scenarios` 摘要与 `fatebridge://scenarios/{scenario}` 完整路由；只列当前配置可调用工具，通过 `availability` 和路由组 `available=false` 明示缺失能力，不将旁证升级为主证。

场景清单将直接工具和依赖区分：`direct_engine_tools` 是本入口直接文档化的工具，`resolved_engine_tools` 为依赖展开后的工具键；`dependencies` 保留 `shared_support`、`conditional_service`、`composite_topic` 的使用条件及实际 availability。完整发现另保留依赖路由的原场景与条件，不将条件服务升级为默认主证。场景过滤按依赖闭包公开工具，family 交集仍可能产生明确缺项。

工具的 input/full describe 和 MCP 描述可附 `evidence_views`：这是按用户任务或盘型组织的字段参考。首次调用复制匹配卡片的 `fields`，仍使用既有 `strict_fields` 和 `include_snapshot_text`；不向接口发送 `view` 或 `evidence_views`。未指定视图时使用安全的 `suggested_fields`。`fields=null` 仍表示完整结果，不受参考视图影响。

`FATEBRIDGE_MCP_SCENARIOS=onda-jiankang,onda-shiyun` 可缩小 MCP 注册范围；与 family 配置取交集，省略或留空仍公开全部工具。独立的 `reproducibility` 发现字段声明时间与 seed 条件，MCP 幂等标签仍只描述环境影响。

`GET /api/tools` 无参数时保留全量完整记录。可选参数：`detail=summary|full`（REST 默认 full）、`family`（逗号分隔分类）、`q`（名称/分类/描述搜索）、`tool`（精确工具名）和 `surface=rest|mcp|cli`。先请求 `?detail=summary&family=bazi`，选中工具后再请求 `?tool=bazi_birth&detail=full`。摘要不生成或返回参数及输入/输出 Schema。

`counts` 始终表示全局目录数量，`matched_count` 表示筛选后实际返回数量，`detail` 表示记录深度。无匹配关键词返回空列表；非法分类或精确工具名返回带安全 `issues` 的 422。

CLI `discover --family bazi` 默认返回同源 JSON 摘要；`discover --tool bazi_birth --detail full` 获取完整契约。CLI 的 `--query` 对应 REST `q`；`list` 默认文本格式不变，可追加同样的筛选参数及 `--json`。`describe` 保留原有示例与行为。

MCP 默认仍公开全部工具。host 可设置 `FATEBRIDGE_MCP_FAMILIES=bazi,knowledge`，使实际 `tools/list` 与调用注册表只保留这些分类。资源 `fatebridge://catalog/summary` 提供当前公开集合的摘要，`fatebridge://families/{family}` 提供分类摘要，`fatebridge://tools/{tool}` 按需提供单工具完整记录；资源只返回当前 MCP 集合中的工具。隐藏工具的单工具资源及非法资源筛选由标准资源协议报错，无 `isError` 工具结果。资源返回与 REST / CLI 的等效 `surface=mcp` 筛选完全同源。

工具 `annotations` 从 `ToolSpec.execution_hints` 派生，同时出现在三端发现记录中。当前本地计算/查询声明 `readOnlyHint=true`、`destructiveHint=false`、`openWorldHint=false`、`idempotentHint=true`。这些提示描述环境影响，不保证相同结果字节：随机起卦、缺省当前日期和每次运行元数据仍按原规则处理。annotations 是提示，不代替执行权限判断，见 [MCP 工具规范](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)。

### 2.8 确定性与复现元数据

REST 查询参数与 MCP 参数支持 `as_of`、`trace_id`、`parent_run_id`；CLI 对应 `--as-of`、`--trace-id`、`--parent-run-id`。as_of 为含时区 ISO 8601 时刻，归一化到 UTC，例如 `2024-02-29T16:30:00Z`。省略时捕获本次执行开始时刻；显式日期优先，各工具的部分日期补齐规则仍分别适用。八字综合、流月、流日、流时及独立大运在分析日期全部省略时使用完整当地瞬间，`analysis_reference`保留偏移、fold和秒微秒；只有显式部分日期的流月才沿用缺日取15。不存在／重复的显式分析钟时不猜瞬间，详见[时钟与补齐规则](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-analysis-instant.md)。上下文按调用隔离，不修改进程时区或全局时间。

标识仅接受 1–128 字符的字母、数字、`_ . : -`。控制项非法为三端校验失败，不回显值；有效 trace / parent 标识传播到成功元数据和模型、领域、投影失败包络。失败可含顶层 `trace_id` / `parent_run_id`；CLI 参数语法错误仍退出 2，框架非法 RPC 与未知工具不属于该包络。

原有六个基础元数据字段保持，新增字段在输出 Schema 中为可选：

- `metadata_schema_version=1.0`、`package_version`、`contract_sha256`：格式、包版本和工具输入/输出模型合同指纹。
- `input_sha256`：模型默认值/别名归一化请求摘要，包含真太阳时开关与出生分钟的显式状态；省略分钟与显式00分因输入回执不同而区分。未知秒数的省略与null语义相同。不保存原出生档案。嵌套与扁平合同的输入摘要不承诺相同。
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
| `birth_second` | int / null | 否 | 八字与七个时运入口支持；已知整秒 `0..59`，提供时必须显式提供分钟；未知省略或 null |
| `birth_utc_offset` | string / null | 否 | 八字与七个时运入口支持；已确认民用偏移 `±HH:MM[:SS]`，须匹配已解析时区，用于重复钟时消歧；未知省略或 null |
| `birth_place` | string | 否 | 支持中文、英文、拼音地点文本 |
| `birth_timezone` | string | 否 | IANA 时区或 UTC offset |
| `birth_longitude` | float | 否 | `-180..180` |
| `use_true_solar_time` | bool | 否 | 此家族默认 true；显式 false 使用钟表时间 |

中式模型缺省开启真太阳时但没有可解析经度时，会使用钟表时间并附 `resolution_advisory`；显式 true 且无经度则返回错误。时区应显式传入，IANA 名称可表达历史夏令时，固定偏移不能。年/月柱、节气与起运使用实际民用时刻；太阳钟修正用于日/时柱等既有规则。当前小时必填，不提供省略小时的无时盘模式。

八字与时运的 `BaziClockRequest` 扩展基类以支持已知秒数；其他继承模型不因此获得此参数。`calendar_context.birth_time_input` 区分显式00分／秒与兼容默认值，回显计算参考与校正钟面。省略分量不代表真实记录精确，也不自动推定舍入方式或误差区间；完整路径和接口范围见[出生秒数与输入分量](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-birth-seconds-audit.md)。

`BaziClockRequest` 的 `birth_utc_offset` 在重复小时中选择已确认的实际出生瞬间，回执包含实际UTC、fold、歧义状态和时区规则身份。偏移不推断地区时区、不认证记录精度，也不能令不存在的钟时有效；原IANA时区保留用于后续交运。紫微与六壬原有同名参数继续有效。见[重复钟时与UTC偏移](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-birth-fold-audit.md)。

九大专项追加 `analysis_year/month/day`、`dayun_pillar`、`liunian_pillar`，`timing_context` 位于 `<dimension>_analysis` 内。时运子模型的必填字段各不相同；大运需要 `gender`，可选的 `analysis_age` 与显式分析日期互斥，日期全部省略时按 `as_of`／执行开始时刻选运。完整规则以 OpenAPI 为准。

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
| `analysis_hour` / `analysis_minute` | int | 目标钟时，分别为 `0..23` / `0..59`；省略时分别沿用出生小时 / 分钟 |
| `return_longitude` / `return_latitude` / `return_timezone` | mixed | 返照或行运地点 |
| `house_system` | string / int | 已注册的十二宫制字母／名称或 `0..8` 代码；未知、空白、布尔值及浮点选择报错，不改用默认宫制；`E` 等价归为 `A`，Gauquelin (`G`) 不在此接口内 |
| `zodiac_type` | string | 例如 `Tropic` |
| `pd_method` | string | 主限方法 |
| `pd_time_key` | string | 例如 `Ptolemy` / `Naibod` |
| `pd_type` | int | `0=direct`，`1=converse` |
| `pd_aspects` | int[] | 主限相位列表 |
| `show_pd_bounds` | bool | 主限图盘是否带界限层 |
| `firdaria_night_order` | string | `nodes_at_end`（默认）或 `nodes_after_mars`；只影响法达夜盘顺序 |
| `firdaria_year_basis` | string | `fixed_365_2425`（默认）或 `calendar_anniversary`；只影响法达日期计算 |
| `selected_sections` | string[] | 仅独立 timing tools 支持 |

两项法达参数可独立组合，同时适用于综合时运和独立 `firdaria`，REST / MCP 同名，CLI 使用 `--firdaria-night-order` / `--firdaria-year-basis`。公历周年的闰日、UTC 七等分、时区异常拒绝及分钟展示规则见[法达兼容约定](firdaria-compatibility.md#参数与调用)。默认组合保留现有返回结构，非默认组合在法达对象内增加 `calculation_options` 回执。

完整非法分析日期返回 `validation_error`；只给部分年月日时逐字段补齐默认值，部分日期补齐时可约束到月底。目标日期与钟时按 `birth_timezone` 解释，`return_timezone` 用于转换同一时刻。指定某日某时应同时传齐五项 `analysis_*`，核对聚合结果的 `analysis_context.analysis_datetime`；`as_of` 不替代目标钟时。复现计算还应保留出生时区与返照/行运地点。

### 3.4 本地技法请求约定

`sixyao`、`suzhan`、`otherbu`、`sanshiunited` 等大量本地技法接口共享如下约定：

`sixyao` 的 `calendar_context`、`liuyao_evidence` 和 `classical_text_evidence` 分别提供历法、指定版本的日月／动变关系和实际动爻原文；`current_hexagram.classical` 保留《周易》原文、版本与来源。重复提供的铜钱、卦码和六条爻线必须一致；畸形卦码与不完整爻线会明确报错。规则覆盖及现实验证状态见[六爻深度审计](liuyao-depth-audit.md)。

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
| `POST` | `/api/cn/bazi/source-compare` | 已明确的原样四柱与登记编释核对 |
| `POST` | `/api/compatibility` | 双人配合分析 |
| `POST` | `/api/compatibility/sukuyo` | 宿曜双人相性分析（三九の秘法，二十七宿） |

`bazi_source_compare` 只接收明确给出的 `year_pillar`、`month_pillar`、`day_pillar`、`hour_pillar`，各为天干地支两字。先按当前模型计算，再核对所有同柱登记编释；`current_calculation` 与 `source_comparison.records` 分开返回。 经过图版修订的条目另附 `input_reading_revision`，保留原录文、旧索引条目及校读散列；`registered_document_scope` 说明引用的登记文档仍是原始转录。未知标签不会因输入修订而自动补定。 `editorial_annotation_provenance`另标记原登记编辑说明的文件、字段位置和散列；补回的说明保存在`annotation_basis`与`retained_context`，不冒称原典逐字引文或新的强弱裁定。相符、差异、未裁定和未收录各自保留，不重建历史生日，也不改写强弱。首轮字段视图为 `source_strength`，详见[原典材料与核对范围](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-source-corpus-audit.md)。

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

九专题另提供 `<dimension>_analysis.evidence_chain`，含逐星透藏与根气、位置关系、五类格局有限前提审查、上游旺衰状态与主题运年触点；发现入口为 `evidence_views.depth`。未知性别仅限制自动大运顺逆，仍返回本命及独立流年，`timing_context.dayun_status=unavailable_gender_direction`；显式覆盖的大运标为 `explicit_override`。综合结果的位置为 `structure_profile.evidence_chain`，标准命盘为 `bazi_birth.structure_profile.evidence_chain`。条件审查不认证成格，详见[深化审查](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-depth-audit.md)。

| 维度 | 端点 | 主要返回字段 |
| --- | --- | --- |
| 婚姻 | `/api/cn/bazi/marriage` | `spouse_star`（配偶星：正/偏财为妻、正官/七杀为夫）、`spouse_palace`（配偶宫=日支稳定性）、`marriage_quality`（0–100 评分）、`marriage_timing`、`risk_factors`、`suggestions` |
| 事业 | `/api/cn/bazi/career` | `dominant_ten_gods`（事业类型）、`industry_analysis`（喜用神行业）、`career_structure`、`entrepreneurship`（创业 vs 打工）、`career_timing`、`noble_direction`（贵人方位）、`suggestions` |
| 财运 | `/api/cn/bazi/wealth` | `wealth_stars`（正/偏财含藏干）、`wealth_structure`（身财两停/财多身弱…）、`wealth_storage`（墓库财）、`wealth_style` / `wealth_direction`、`wealth_risk`、`wealth_timing` |
| 健康 | `/api/cn/bazi/health` | `constitution`（盘内强弱／寒暖分类）、`organ_analysis`（权重与传统名称对照）、`health_timing`（仅传统关系）；不提供疾病风险或调理处方 |
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

综合时运的 `interaction_analysis.root_context` 分列日主在时运支的根类与运干在原局四支的根类，复用原局根类规则并引用同次地支关系。`roots`、`stem_roots` 是字段视图名；`effective_force_status=not_adjudicated` 表示尚未裁定作用后的旺衰，流月不替换原局月令。字段和来源见[岁运根类与根位触点](bazi-timing.md#岁运根类与根位触点)。

`interaction_analysis.strength_projection` 另提供单层时间支冲刑及唯一大运干五合对原局既有预算的限定投影，字段视图为 `root_effects`。运干数值作用仅限大运、非日干、唯一配对且无争合；其它时间粒度出现干合或合会未解时返回 `blocked`。来源与既有工程系数分别保留，`residual_natal_numerical_label` 仅属残存原局预算，完整行运后旺衰仍为 `not_adjudicated`，不能据此推导吉凶。详见[限定投影](bazi-timing.md#单层岁运支对原局根预算的限定投影)。

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

日历 helper 的全年列表位于 `jieqi_year`；农历查询的年柱、时柱分别使用
`yearGanZi`、`timeGanZi`。梅易批量查询从 `results[query]` 读取条目。
这些结果不再附带旧的重复根字段，详见[迁移指南](migration.md#五行依据与重复字段)。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/divination/meihua` | 梅花时间取数；[规则、历法约定与验收](meihua.md) |
| `POST` | `/api/divination/meihua/cast` | 梅花显式资料起卦与已有单动爻卦解读；判别字段 `casting.method` |
| `POST` | `/api/divination/tongshefa` | 统摄法 |
| `POST` | `/api/divination/sixyao` | 六爻 |
| `POST` | `/api/divination/canping` | 邵子参评数 / 金锁银匙 |
| `POST` | `/api/divination/heluo` | 河洛理数 |
| `POST` | `/api/divination/suzhan` | 宿占 |
| `POST` | `/api/divination/otherbu` | [占星骰](astrodice.md)：planet/sign/house必填，house=0..11；时间地点可省略 |
| `POST` | `/api/divination/sanshiunited` | 三式合一 |

梅花一般解读的 `interpretation.moving_line_phase.real_stage_inferred=false` 表示爻位不确定现实阶段。实际动爻及假设单爻参考的 `timing_scope=modern_action_order_hint_not_event_time` 保留现代行动次序提示，`transition_scope=computed_hexagram_change_not_real_outcome_forecast` 标明只计算卦图变化；原典条件断语与经文引用另列。详细字段含义见[梅花解释范围](meihua.md#解释怎样对应实际计算)。

梅花天气的 `interpretation.weather.research_validation.current_profile_study.primary_attainable_skill_bound` 披露完整固定预测向量相对常量基线的理论评分上限。`passing_is_possible_for_some_complete_binary_outcomes` 仅表示是否存在可能通过的二元观测组合；不是准确率或预测有效性。当前273日向量的最大差为−88，旧实际29对158的负结果继续保留；[计算条件与容量诊断](meihua.md#固定预测向量的可达评分上限)另列。

梅花天气的 `interpretation.weather.symbolic_attributions` 返回所选文明书局本的霜雪霰雹、日电虹霓及既有雷象的实际位置和明示季令核对。`season_matched` 只核对已报季节，`season_not_matched` 不推导现象不会出现；缺少季节保持 `pending_context`。补充配置版本与主40条天气规则分别报告，未加入旧研究标签映射，详见[类象与季令](meihua.md#天时类象与明示季令)。

梅花两入口另支持 `interpretation_topic=travel`／`meeting`，分别读取文明书局本出行／谒见章的实际初始体用句，使用既有 `topic`／`topic_audit` 字段卡。出行的 `interpretation.topic_reading.chapter_qualifications` 核对本候选的旺气偏好和四辅助角色生体关系，并保留未裁定的多字、舟陆角色及影印末句主语。既有四章规则不变；不自动选交通方式、方位、灾祸判断、收益或会面日期，详见[题篇范围](meihua.md#出行与谒见)。

梅花人事两入口可选 `observation_context={label, quiet_room, nothing_heard, nothing_seen}`。后三项为严格布尔或 `null`，省略不推定无外应；`quiet` 字段卡读取 `interpretation.observation_context`，区分未采集、条件待齐、已报符合与已报不符。仅核对所选《静占》的同次声明条件，整条年月日衰旺合参尚未实现；天气分支拒绝该对象。声明与同次听声、完整观物或外应记录相矛盾时返回校验错误，不据此重写旧研究分母，详见[静占条件](meihua.md#静室与无所闻见的声明条件)。

梅花人事的 `interpretation.day_qi` 返回文明书局本所选日应、月日旺衰和生体／克体角色偏好；`day_qi` 字段卡可读取。时间入口按已声明民用午夜日界自动计算，23时另列子初候选，不能把附带八字的下一日日柱冒作午夜日气。显式入口只接已确认 `day_qi_context={label,day_branch,declared_day_boundary?}`，未知省略；时间入口拒绝该覆盖对象，天气拒绝该体用情境。月日矛盾不合成净旺衰，完整年、月、日合参仍未实现，详见[日气范围](meihua.md#日气与月日衰旺)。

梅花两个人事入口另可接`response_context`，声明同次现场的方应、天时应、地理应、人事应。须有非空label、严格布尔`same_casting_episode_confirmed=true`；其余字段未知省略，不从题目、历法种子、住址或端法物象方向推断。只在已提供该对象时使用`situational`字段卡，读`interpretation.situational_responses`及各候选自身原体；多卦候选和影印／转录差异不合成结果。天气预测分支拒绝，详见[十应现场条件](meihua.md#同次现场的方应天时应地理应与人事应)。

梅花人事两入口的`interpretation.stage_emphasis.obstruction_timing`返回条件化阻节计日，`obstruction_days`字段卡可读取。既有`matter_scenario=favorable_matter`明示且本候选内卦同时生体、克体才激活；乾1兑2为明例，其余六卦为类推，重复卦名按角色分组而不累加。日数不转换成净延迟或完成日期，天气不使用此层，详见[阻节计日](meihua.md#生克并见时的阻节计日)。

梅花已报外应的`manifestation`另支持`gold_silver_treasure`及`weapon`（原文兵刃类），不自动从普通金属、刀锯、问题或标签取象。`external_symbol`字段卡读完整`interpretation.external_omens`及其中`body_relative_symbols`，按各候选自身原体核对两则《内外论》限定；不凶不改成吉，实物资格及现实结果另留未知，详见[原体限定](meihua.md#宝象凶器与原体限定)。

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

太乙年计可明确选择`year_profile=jinjing_year_historical_table_v1`（381—385晋历）或`jinjing_year_qiliang_table_v1`（501—505齐梁史历）；三式放入`taiyi_options`。两者按原表民用日期、只用于year，范围外拒绝。齐梁配置保留502年闰四月及未决算法候选，`historical_calendar.source_disagreements`与快照同源；不认证王氏古日积或另外两术古历。日期、来源及调用示例见[历史年计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-year-calendar.md)。

六壬起课、行年和金口诀支持 `is_diurnal` 显式选择昼贵/夜贵；`guiren_profile` 可选既有 `liuren_common_v1` 或《探原》贵人歌 `tanyuan_xieji_v1`。金口诀本课独立使用古本贵神表，配置仅影响其附带六壬盘。`di_fen` 仅接受十二地支，省略的时支回退会明确标注。金口诀分别返回 `seasonal_power`、`internal_power` 与 `internal_strength`；旧 `power` 仅为季节旺衰别名，多候选未裁定时课内旺衰为 null。原典疑文和验收范围见[专业能力审计](liuren-jinkou-audit.md)。三工具的 `describe` 已发布 `evidence_views.core`，可复制其中 `fields` 做严格摘要投影。

金口诀 `jinkou.overview.month_general` 是中气月将本位，`jinkou.overview.yuejiang` 是兼容字段名，表示月将加时后移到地分的将神，对应 `jinkou.rows` 的将神行；两支可以不同。默认快照分别显示“月将本位”和“将神落地分”，字段描述与调用指导也明确该范围，不将落地分支误作中气月将。详见整秒交气与说明验收（本地数据：`validation/ren-seconds-validation-2026-10-23.md`）。

金口诀接受可选 `natal_branch`（十二地支之一），表示问课对象已确认的本命年支；也可由明确的 `birth_year_ganzhi` 提供其年支，两者并给须一致。`jinkou.relations.si_jue.natal` 返回该支与本次将神的京本大绝配对，来源分别记录为 `explicit_natal_branch` 或 `explicit_birth_year_ganzhi`；两项均缺时 `matched=null`。不由占时、地分或行年推定本命，也不要求补猜出生时刻。已有 `evidence_views.natal_absolute.fields` 仍有效。

金口诀1.11.0另用 `birth_year_ganzhi`、`year_fate_age` 及明确男／女计算京本六甲旬行年；岁序为指定的一岁起算整数1–150，不是寿限，未核验其是否为占时实际年龄或原典换岁边界。`jinkou.year_fate` 保留起点、顺逆、岁序与独立另课；另课采用行年支作地分的所选释读，标记为推导而非已观测方位，原问课地分保留。缺项或性别未知不补猜、另课为null，原典“课干”所指及综合喜用仍未裁定。可用 `evidence_views.year_fate.fields` 核对，视图名不是请求参数；来源、疑义与验收见京本行年记录（本地数据：`validation/jinkou-year-fate-validation-2026-10-23.md`）。

三工具用 `analysis_second` 保留显式秒数。六壬 `classification` 按实际四课从《探原》总说推导始入、比用／知一、杜传／不虞和返吟细名；不等同于所有逐课表注已经认证。金口诀 `qi_evidence` 分列月建进退与日支生将，月建“进气相”与季节五态分开；未分类或未命中生扶条件不自动算作弱或凶。

六壬规则集1.3.0增加 `liureng.life_stages`，明确采用《探原》十干十二运：阳顺阴逆、戊己随丙丁；与所选 `guiren_profile` 独立。返回十二支阶段、日干、方向、长生／临官／墓、两个生墓加临结构及书影来源。四课 `upper_day_stem_life_stage`、三传 `day_stem_life_stage` 和 `seated_day_stem_life_stage` 均以实际日干为参照，旬空与坐空另列。`month_building_element` 才是月建五行，旧 `twelve_life_element` 仅为弃用别名；不再以月建五行冒充十二长生。金口诀附带六壬与三式内六壬亦同。阶段名不代表现实疾病、生死或成功概率，口径及完整范围见十二运验收（本地数据：`validation/liuren-life-stages-validation-2026-10-22.md`）。

六壬规则集1.6.0增加 `liureng.emptiness_evidence`，按《探原》论空亡分列十二位 `sky_xun_kong/earth_xun_kong`、日干寄宫地盘例外 `earth_stem_house_exception`、三种权威角色 `role_conditions/sky_authority_roles` 及占时本空。局部例外不改原旬空两支或三传本空、坐空；每位 `effective_empty` 与整体 `comprehensive_judgement` 均为null，Schema拒绝改成布尔裁定。年命例外、真空半空、填实冲实及综合优先级尚未裁定。六壬起课与行年的 `describe` 发布 `evidence_views.emptiness_evidence.fields`，复制其中字段进行严格投影；金口诀附带六壬盘与三式内嵌六壬也返回本层，不能用于替代金口诀四位空亡规则。见空亡分层验收（本地数据：`validation/liuren-empty-scope-validation-2026-10-23.md`）。

`calendar_policy.solar_term_dependencies[*].published_date_reference` 给出每项实际交气的香港天文台刊载日期、计算的固定UTC+08日期及来源URL／散列。`status=date_match/date_mismatch/outside_published_range` 分别表示日期相符、不符与超出1901—2100资料范围；范围外的 `published_date/dates_equal` 为null。`instant_accuracy_certified` 仅允许布尔false，逐日表不验证交气秒数。完整执行先核对五个依赖的同次名与瞬间及完整对照对象，再投影；三工具的 `published_term_dates` 视图复制其 `fields` 使用。依赖数组须整体读取，不能把视图名或数组内部路径当请求参数。固定UTC+08是对照约定，不替代输入IANA时区、真太阳钟或历史时制。原数值不因日期冲突改写，见第四十二轮验收（本地数据：`validation/ren-hko-dates-validation-2026-10-23.md`）。

金口诀1.10.0的 `jinkou.branch_stars` 返回所选七项历法目标、锚点类别、三位本支相同位置、天赦完整日序比较及原页。`yima_anchor=month_building_branch`；当前节月名义月序与三个月分季的约定明确，不能借月将、日支驿马或土旺月五态替换。`comprehensive_effect`仅为null、完整认证仅为布尔false。完整执行校验同次四柱、四位和唯一轨迹后才投影；公开 `branch_stars` 视图带四柱及完整四位数组，不以视图名充参数。见第四十四轮验收（本地数据：`validation/jinkou-branch-stars-validation-2026-10-23.md`）。

六壬1.9.0的 `liureng.seasonal_evidence` 给出月建支、季节分组、五态表、日干状态，以及完整十二地盘中支神／天将／地盘各自的固有五行与五态。本配置以辰未戌丑整月为季月，明确未裁季末十八日异法。`sky_empty_seasonal_condition` 为null、真空条件或半空条件；仅对支神本空适用，不替换原本空、坐空或例外。`effective_empty_classification/effective_empty_class` 只允许null，有效真半与全书认证只允许布尔false。完整执行核对同次月建、日干支、盘位、三传及唯一轨迹，再投影。视图为起课／行年的 `seasonal_evidence` 与金口诀附盘的 `liuren_seasonal_evidence`；数组须整体读取，不借此改金口诀本课取用。见第四十三轮验收（本地数据：`validation/liuren-seasonal-validation-2026-10-23.md`）。

六壬1.8.0返回 `liureng.transmission_progression`：三传支序、模十二步长、连茹／间断及 `sequence_direction`。`branch_xun_kong` 是初中末支神本空；`raw_branch_empty_conditional_reading/direction` 明确限定在支神本空适用假设下，综合 `effective_direction/comprehensive_judgement` 只允许null。完整执行核对同次三传、日干支和唯一轨迹后才允许投影；省略上下文的局部投影不冒充完整验证。起课／行年公开 `transmission_progression` 视图，金口诀附盘公开 `liuren_transmission_progression`，金口诀本课不借此改四位或定用。见原页与验收（本地数据：`validation/liuren-progression-validation-2026-10-23.md`）。

三工具另支持 `analysis_utc_offset`，与 `analysis_timezone` 联合核对当地民用钟，格式为 `±HH:MM` 或 `±HH:MM:SS`。例如哈瓦那 `2021-11-07 00:30` 出现两次：`America/Havana` 配 `-04:00` 选择第一次，配 `-05:00` 选择第二次。偏移必须符合该命名时区当时的规则；省略偏移的重复时刻、不存在的跳钟时刻及错误偏移均拒绝。指定后 `calendar_policy.civil_clock_resolution` 返回实际UTC瞬间、偏移、`fold`、是否重复及所用TZif版本和散列。真太阳钟的 `corrected_clock` 是不带时区的取用标签，实际瞬间另见 `civil_instant_utc`。三端示例与验收范围见重复民用钟验收（本地数据：`validation/ren-civil-fold-validation-2026-10-22.md`）。CLI负偏移建议写成 `--analysis-utc-offset=-05:00`。

金口诀 `patterns` 登记六十四课钤，返回实际结构命中、条件、书影页码和未决条目；58条已评估、6条未判，不表示64课原例均符合。`patterns.evaluations` 另列全部64条，`matched=true/false/null` 分别表示命中、所选定义下未命中、疑义未判，对应 `status=matched/not_matched/unresolved_definition`；`evaluation_counts` 分列数量，未判不计作不成立或验收通过。只投影该列表可请求 `fields=["jinkou.patterns.evaluations"]`，设 `strict_fields=true`；完整记录超过响应限额时按同一run的 `result_delivery` 读取，不能用重算替代。`use_evidence` 分列阴阳用位的受克、空破与无克从旺条件，`comprehensive_position` 尚为 null；不会自行改掉阴阳用位来凑一个综合结论。

金口诀规则集1.5.1将 `use_evidence.comprehensive_position` 的Schema限定为null，非空的综合结论会在投影前作为输出错误拒绝。`internal_strength.source_evidence` 明确旺衰取自网上转录十二例的归纳规则，另列京本天乙例末位“木／水”的未决文本差异及书影散列；不是十二例书影全部符合认证。`use_evidence.source_evidence` 给出无克从旺的PDF18／页脚17及阴阳取用PDF45–46，综合优先次序仍未裁定。日下完整五态和完整原典认证字段只允许false，不能用true冒充已裁定。快照保留同一文本依据，见书影校勘与合同验收（本地数据：`validation/jinkou-strength-scan-validation-2026-10-22.md`）。

六壬与金口诀的 `calendar_policy` 发布民用输入、日时取用钟、23:00子初换日及日柱归属日期、实际交气提供者。真太阳钟用于日时柱，年/月柱及月将据民用瞬间；提供者状态不代表全部历法域精度认证。天文求解失败不使用线性节气回退起课，返回503 `dependency_missing`。五个 `solar_term_dependencies` 逐项公布TT求解、民用转换方法、冻结闰秒表到期日和未来末值假设。共享节气 `datetime` 字符串保留小数秒，可用 `datetime.fromisoformat` 解析；时区仍见响应上下文，小数位不代表微秒物理精度。按各依赖的 `provider/ephemeris_model/solar_model_details` 区分原生Swiss与具名解析模型，后者不借用原生返回选项。第三十五轮完整分钟比较在原生／解析路径分别仍有21／22项未通过；原200年队列7项节气日期差异未重评，不能据TT有限对照或农历表补充宣布全历法通过。见部署模型验收（本地数据：`validation/ren-model-matrix-validation-2026-10-22.md`）及历史第七轮验收（本地数据：`validation/ren-timescale-validation-2026-10-22.md`）。

五个交气依赖还返回求解实际使用的 `ephemeris_model`、`ephemeris_retflags` 与 `ephemeris_library_version`，快照显示实际模型。提供者 `swisseph` 是软件名；缺数据时实际模型可能为 `moshier`，不能由提供者名称推断使用了SWIEPH数据文件。年度缓存随库实例、搜索路径和文件状态变化失效，短暂求解失败不会长期污染缓存；无效或混用模型被拒绝。完整分钟比较仍保留原21项未通过，见第十一轮验收（本地数据：`validation/ren-ephemeris-cache-validation-2026-10-22.md`）。

金口诀 `relations` 按所读京本书影返回四绝、五行临地分的四败、岁建/岁破/日建/日冲，保留对象、实际支、是否命中、页码及网上转录异文。缺命支的大绝为 `matched=null`；四败不替代旺衰，新增关系不自动改变阴阳用爻。规则集1.4.0的范围及64课默认不符记录见第六轮验收（本地数据：`validation/jinkou-relations-validation-2026-10-22.md`）。

金口诀规则集自1.5.0起提供 `combinations`，逐组返回三合成员齐缺、人元五行关系、成员日冲月破空亡和神将遁干克局事实。`waiting_branch` 只是虚一支；完整合化、妒合及实际日期候选尚为 null，Schema拒绝将这些未决层改成布尔判断或日期。默认与选节导出均含“三合与虚一待用”，首轮 `evidence_views.core.fields` 同步包含该层。原书所忌支的完整适用条件尚未裁定，不能因润下成员辰、从革成员巳自身出现而判破局，见第八轮验收（本地数据：`validation/jinkou-combinations-validation-2026-10-22.md`）。

六壬 `liureng.meta.diurnal_evidence`、金口诀 `jinkou.overview.diurnal_evidence` 另以 `ren_diurnal_selection_provenance_v1` 回显所选 `is_diurnal`、原始显式选择（省略为null，false明确为夜）、占时时支及来源；金口诀速览同时直接返回 `is_diurnal`。`stellar_visibility_observed` 和 `solar_altitude_threshold_degrees` 尚为null，`astronomical_boundary_computed=false`；未记录观星不等于已知星不可见，显式选择也不证明已符合原典星没星出的界线。三端完整/严格投影和快照保留该依据，见第九轮验收（本地数据：`validation/ren-diurnal-validation-2026-10-22.md`）。

### 4.6 核心占星盘

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/chart` | 标准盘 |
| `POST` | `/api/astro/chart13` | 13扇区；ASC未解析时实际落区为null，见范围与复现（本地数据：`validation/specialty-reference-angle-qualification.md`） |
| `POST` | `/api/astro/hellen` | 希腊风格盘 |
| `POST` | `/api/astro/guolao` | 果老 / 七政四余风格盘 |
| `POST` | `/api/astro/india` | 印占 Lahiri 本命、分盘与具名八分法分析；表级`source_profile_comparison.aiyar1905`另列Aiyar自己的原始表及削减，旧`reduction_analysis.source_profile_comparison`仅比较削减读法，Rao默认保留，范围与缺项见[印占说明](jyotish.md) |
| `POST` | `/api/astro/vimshottari` | 印占 Moon-nakshatra 主运／次运；可选`dasha_depth=3..6`当前递归分期，`time_quantization`回显各样本自己的出生历元与精确比例，见范围与验收（本地数据：`validation/jyotish-dasha-global-epoch-audit.md`） |
| `POST` | `/api/astro/germany` | 中点 / germany 派生盘；基础宫制／参考角／子午宫的角色（本地数据：`validation/specialty-house-roles.md`）分别读取；太阳弧名义目标有效时保留越界生时样点，分层 `partial` 见范围说明（本地数据：`validation/solar-arc-boundary-sampling.md`） |
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

`profection`、`givenyear` 和综合推运的月小限采用周年区间的 UTC 时长十二等分；2 月 29 日出生者在平年采用 2 月 28 日，闰年恢复原生日。年区间、月段端点和活动月序共用该口径，见[年小限与月段边界](western-astrology.md#年小限与月段边界)。

### 4.8 事件占星（事件盘）

求解天文时刻后起盘的一组事件类工具。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/astro/event/mundane` | 世俗入宫盘 |
| `POST` | `/api/astro/event/extrareturns` | 多重回归 |
| `POST` | `/api/astro/event/horary` | 卜卦判断 |
| `POST` | `/api/astro/event/election` | 择日 |

卜卦的 `orb_profile` 可选 `lilly_1647_p107_first`（默认）或 `lilly_1647_p107_second`，对应原书第107页两列全容许度；`rule_profile.orb_table` 返回实际选式。主星的 `house` 表示所代表的事项宫，`occupied_house` 表示实际落宫。`lilly_orbs_houses` 是公开的按需字段卡，按其中 `fields` 调用；居宫与月亮传递的必要子条件不等于完整判断。来源、边界与可复算检查见[西占验证说明](western-astrology.md#lilly两列容许度实际落宫与居宫条款)。

近太阳速率的v5计算在`longitude_motion.complete_position_derivatives`返回多层差分、方向检查及适用时的`source_branch_motion`；这些是数值方法证据，不能当作物理误差界。成功事件历史的`unavailable_reason`、`unavailable_code`、`failed_sample`明确为`null`，可由`reference_points`严格视图读取。对照与未通过项见源模型核验（本地数据：`validation/western-solar-disc-motion/report.md`）。

本命、希腊盘、印度盘及卜卦公开 `solar_position_model` 字段卡，读取标称历元的 `apparent_position_policy`；原生推运盘也在 `calculation_basis` 携带此回执。其中 `bodies` 保留未偏折有限视线的前景／后景几何、原生太阳质量模型及未核定的物理误差；未知版本／后端不计算该几何。事件历史的同名字段仅描述提问历元，不能外推整个窗口。`virtual_native_solar_disc_extension` 表示原生模型的虚拟视位置。v2 回执的 `source_model_regularity` 保留质量表来源哈希，并明确未认证太阳轴线处的连续性及质量表节点处的唯一导数；未知原生版本时该字段为 `null`。这些是源码模型的适用限制，不能替代实际可观测位置的精度证明。它不改变已有坐标、日速和原有失败比较；见位置模型与三端核验（本地数据：`validation/western-solar-position/report.md`）及太阳轴线独立复核（本地数据：`validation/astrodice-solar-axis.md`）。

卜卦另发布 `lilly_fortitudes` 字段卡，读取 `horary.fortitudes.summary` 及其模型／缺项。每颗星有第115页完整41行的独立回执；`applied_conditions` 给出实际满足的条款，深入核对可请求如 `horary.fortitudes.planets.Sun.rows`。日运动取五个原生采样点展开的一完整TT日位移，瞬时方向另列；恒星采用所声明历元的视位置，印刷度数只用于历史对照。`literal_table_balance` 不等于原典完整判断，任一必需行未知时为 `null`。原书例题复现仍为3/7，未改权重配平，见全表与例题核验（本地数据：`validation/western-lilly-fortitudes/report.md`）。

卜卦新增 `lilly_fortune` 字段卡：读取 `horary.fortune` 的昼夜同式、实际上升点、宫头效力与第145页独立表摘要。`house_assignment` 分开几何落宫与第33页最近宫头五度归属；缺项、等距与逆序宫头不补默认值。福点相位／恒星范围为明确声明的政策，原书算式复现不等于第180页应用或完整原典已通过。见福点与归宫核验（本地数据：`validation/western-lilly-fortune-houses/report.md`）。

卜卦的 `lilly_radicality` 字段卡读取第121–123页12项手工条款清单、实际不等时主、时主对应、可选报告及未知条件。`radicality_context` 为严格对象，已知提问时刻不自动满足确定事件图例外；未报告的个人／受损条件不推断。CLI支持 `--request-file` 及 `--radicality-context` JSON。`safe_to_judge=null` 表示完整判断资格未建立；四个印刷对应例复现不认证整盘判断。详见审查条款及接口核验（本地数据：`validation/western-lilly-radicality/report.md`）。

卜卦 `question_calendar`、择日 `candidate_calendar` 支持 `proleptic_gregorian`（默认）和 `julian`。后者先按儒略历校验日期，再换成内部格里历，最后处理所给时区；1700／1800／1900／2100年的儒略历2月29日可表达，格里历同名非法日继续拒绝。年份须为已按1月1日换年整理的公元编号，不自动猜地区改历、英国旧式年份或地方太阳钟时。默认首轮字段和 `calendar_input` 卡保留 `calendar_conversion`；原标签另见 `analysis_context.input_calendar/input_date`，规范化的 `question_datetime/candidate_datetime` 为格里历本地钟时。两个工具的按需合同均由正式生成器维护。见来源与三端核验（本地数据：`validation/western-civil-calendar/report.md`）。

钟时另用 `question_clock_basis`／`candidate_clock_basis` 声明：`civil`（默认）、`local_mean_solar`（UT1加东经时差）、`local_apparent_solar`（再加地心视太阳均时差）。`timezone_name` 现为可空；民用模式省略／null保留旧 `+08:00` 默认并标注来源，太阳时模式必须省略／null，给任何时区都拒绝。默认首轮字段与 `clock_input` 卡含 `clock_conversion`，返回声明、原钟面、实际物理轴及来源比较；太阳时输入的 `analysis_context.timezone` 为null，`chart_timezone=UTC` 只标内部载体。历法先于钟时转换，不猜原书口径；分钟输入不因反解残差很小就获得实测精度认证。见事件钟时核验（本地数据：`validation/western-event-clocks/report.md`）。

小时日起点另由 `question_hour_origin`／`candidate_hour_origin` 选择 `midnight`（默认）或 `noon`。后者0=同日12:00，12–23=次日00:00–11:00，例如午后第14小时成为次日02:00；只接收已确认的钟时格式。它与民用／LMT／LAT独立，不表示实际持续时长、时区或JD起点修正。`hour_origin` 字段卡与 `clock_conversion.hour_origin_conversion` 保留原日期、小时及最终钟面；`analysis_context.question_datetime/candidate_datetime` 使用最终标准钟面。历法标签与日进位以整数处理，最终范围检验允许有效终点越过不可表示的中间日期。后者的 `calendar_conversion.normalized_local_datetime` 可以为null，并由 `normalized_date_representable=false` 标明；最终值在 `clock_conversion.input_wall_datetime`。夏令时检查采用最终钟面。见来源、边界及三端核验（本地数据：`validation/western-noon-origin/report.md`）。

太阳时反解落入UTC闰秒时，卜卦／择日保留原生TT／UT1继续计算，`converted_utc`可返回含`23:59:60`的标签。`clock_conversion.utc_representation`明确区分UTC标签、闰秒与Python datetime可表示性；不要截断、平滑、移秒或把显示限制说成星盘不可算。仍不推断原资料精度、实测EOP、完整原典或现实预测有效性。见物理时刻与闰秒核验（本地数据：`validation/western-leap-epoch/report.md`）。

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
| `/api/fengshui/monthly_stars` | `fengshui_monthly_stars` | 十二节换月的中性月紫白；含时区query_at或确认的effective_solar_year/solar_month_number，独立有效期与固定位置释义 |
| `/api/fengshui/xuankong_natal` | `fengshui_xuankong_natal` | 中州派运山向宅盘、历史定运、兼向替星及边界候选；独立于年星 |
| `/api/fengshui/assess` | `fengshui_assess` | 原始盘与布局关联、室内形态观察、按目标的元素候选、限定年度作者规则、来源与分歧 |

输入不继承完整八字生辰要求；命卦可用 `birth_date`、`effective_birth_year` 或 `birth_at` 三选一，年度使用 `effective_year` 或 `query_at` 二选一。角度须声明参考北。组合结果在 `layers.bazhai`、`layers.jinsuo`、`layers.annual_stars`、`layers.xuankong_natal` 中分别返回，合法缺失资料用 `status=partial`，不是协议错误。月飞星和金锁进阶规则不在此版；没有三法总分。每层带规则版本、来源和范围，快照记录同一组分层计算事实。

三端可复制示例、详细字段语义及来源限制见 [家居风水](fengshui.md)。CLI 示例：`fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json`。MCP 参数为同一文件内容的 JSON 对象；REST 请求体同理。`--request-file` 保留未知字段交给模型拒绝，显式字段参数覆盖同名顶层字段。

## 5. REST 调用示例

以下人物资料均为虚构示例，默认未开启 API Key 鉴权；开启后加 `-H "X-API-Key: <secret>"`。

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

下表按 family 列出公开名称。MCP host 的配置与结构化结果处理见[接入指南](agent-guide.md#fastmcpagent-host)，Codex 配置见[专用指南](codex-guide.md)。

### 6.1 启动

```bash
uv run --locked --extra dev python -m fatebridge.mcp_server
```

### 6.2 MCP 工具分组

> 全部 92 个 MCP 工具按 `family` 分组如下，各端绑定差异见 §2.4。机读清单见 `GET /api/tools` 或 `fatebridge list`。

#### 基础命理（family `bazi`）

- `analyze_destiny`
- `bazi_birth`
- `bazi_source_compare`
- `bazi_marriage` / `bazi_career` / `bazi_wealth` / `bazi_health` / `bazi_children`
- `bazi_education` / `bazi_personality` / `bazi_relatives` / `bazi_romance`

#### 双人配合（family `compatibility`）

- `two_person_compatibility`
- `sukuyo_compatibility`

`two_person_compatibility` 的 `summary.scoring` 返回实际分项、关系权重、加权贡献和双方旺衰／喜用输入模型版本。它区分上游模型变化与关系权重变化；独立传统净分仍不并入综合分。分项权重、版本追踪与回归依据见[双人评分计算说明](compatibility-scoring.md)。

#### 时运与历法（family `timing`）

- `timing_analysis`
- `dayun_analysis` / `liunian_analysis` / `liuyue_analysis` / `liuri_analysis` / `liushi_analysis`
- `jieqi_timeline_analysis`
- `jieqi_year` / `nongli_time`

#### Divination 与本地技法（family `divination`）

- `gua_lookup` / `gua_meiyi`
- `meihua_analysis` / `meihua_cast` / `tongshefa` / `sixyao`
- `canping` / `heluo`
- `suzhan` / `otherbu` / `sanshiunited`

河洛新增`month_assignment_method`：默认`intro_preferred_v1`采用卦条63项、無妄缺号取卷首八月；`volume_one_table_v1`采用卷首64项。晋、节、睽、震、井五处异号均在`judge.month_affinity.source_assignment_conflicts`列出，逐阶段`source_readings`保留双方月号／页码／本月匹配。`source_consensus_match=null`可能是来源缺号或双方对本月判断相反，不能当false；所选`deTime`仍仅为月表匹配，不是综合得时。规范来源事实损坏为不可重试503。见[合同](contracts/heluo.json)与校勘记录（本地数据：`validation/heluo-month-source-profiles-audit.md`）。

河洛新增`jiehou_evidence`与`jiehou`视图，按本次已算节气名查四正节卦爻，并保留三项原列候卦、四处爻名差异和两模型对照。`selected_hou`／`huagong_assessment`／`selected_reconstruction_model`均null，不能拿十五名义日代替真实节气间隔或择优补实际日序。来源及上游上下文冲突均为不可重试503，见节候核对（本地数据：`validation/heluo-jiehou-audit.md`）。

河洛新增`heluo_timing.year_context`及`source_clock`，`clock_basis`视图保留实际年柱标签、卷一百刻与六日移支相对推演。六十块全年闭合不证明日内添分或实际日期已解，分制及物理原点保持null，两个应用／完整映射标志false。内部年柱冲突或源式损坏均为不可重试503来源故障，见百刻与年上下文核对（本地数据：`validation/heluo-clock-year-context-audit.md`）。

河洛`selected_texts`现含乾坤屯蒙需讼师比小畜履泰否同人大有谦90条单次目校记录（含未决字形，非90条全部确定），旧文另存`inherited_detail`；各条件段`applicability=null`，不按部分葉否或字兆挑选。两层`content_sha256`绑定该版本规范JSON正文／标签／元数据，`sha256`另报实际载入字节；排版可变，非空换文不可沿用已校身份。来源不符为不可重试503，完整校勘仍未完成，见需讼与内容身份核对（本地数据：`validation/heluo-xusong-commentary-audit.md`）。

大有九三在岁运段“在庶俗／凶则”语境只印“变睽”，`target_line`／`target_quote`均null。单爻翻转可核对到睽，但原文未指定目标爻；正式后天仍按原算子取革上，适用未定，不能据此改盘。该六条经一次独立模型读稿，全部分歧及更正保留；九四矜／衿仍未决，`commentary_review_status`与读稿注记明示，人工专家未审。见大有完整注文与有条件引卦（本地数据：`validation/heluo-dayou-commentary-audit.md`）。

谦初、四爻在岁运条件中引明夷、小过；原文未指定目标爻，`target_line=null`，仅四爻有`target_quote="往厲必戒勿用"`。展示保留实际条件及所引字面，不能将所有未编号引卦写成“凶则”或“只印卦名”。正式后天晋／颐仍取实际算子结果。谦二、五爻的諂／謟与彀字候选未决，`snapshot_text`显式提示“字形未决”，条件适用仍null。旧84条保持；没有新增独立读稿或咨询模型复测。见谦完整注文与条件引文（本地数据：`validation/heluo-qian15-commentary-audit.md`）。

二数太阳来源另有`numerology_consumed_solar_sources_v1`轨迹；规则集链接来自实际边界回执，Native供应方文档与精确文件身份区分，混合或未知总链接为null。`all_source_urls_available`仅表示链接存在；源自报的限定年份照录而非精度认证。AA1996派生立春保留公开年份护栏和完整年序，来源不足为不可重试503，见来源与精度核对（本地数据：`validation/numerology-solar-providers-audit.md`）。

师六三选文的`commentary_cross_references`保留“如與命相合者”引升三原句和单爻变核对，适用仍null，`automatic_application`与`replaces_chart`均false；不交换上下体或改正式后天盘。比六二不再混入全卦纳甲句，总论条件仍在`month_affinity`／`najia`，见师比注文与引卦核对（本地数据：`validation/heluo-shibi-commentary-audit.md`）。

小畜九三的`commentary_branch_selection.condition_labels_not_separately_printed`报告原段未单列不葉者，只有实际三段；不是不匹配或false。小畜初引用巽初与正式后天巽四的卦名相同但爻位不同，不能互换选文。标题层新增履六条，来源版本独立升级，见小畜履核对（本地数据：`validation/heluo-xiaochuli-commentary-audit.md`）。

两数新增`pillar_links`证据视图，读取`numerology_evidence.pillar_links`的实际基准年／日柱、原句头干、顺行步数及匹配。内部不相容柱或损坏来源返回不可重试503；匹配不认证完整历法。固定四柱Python起命拒绝不相容组合，原书冲突取数例仅作明确标记的形式算术，见起月起时核对（本地数据：`validation/numerology-pillar-links-audit.md`）。

河洛新增`body_structure`证据视图，读取`judge.body_structure.phases[]`的八条混合爻数记录、原爻位映射、全卦倒序及原例／算子推演标签。完整伏体与得体仍未裁定，五命干支字表不自动选柱；旧纳音／化工取体保持。来源一致性故障不可重试，见渐卦结构核对（本地数据：`validation/heluo-structure-audit.md`）。

河洛`line_conditions.phases[].source_youyuan`逐先后天公布实际元堂／应爻阴阳及主本阴元堂、阳应爻式匹配，保留别本字面；反向相应不能代入。旧`yuanTang.youYing`值保持，仅表示先天通用阴阳相异，`youYing_policy`说明范围，未匹配不推出无援或现实结果。该来源一致性故障为不可重试HTTP503，见有援核对（本地数据：`validation/heluo-support-clause-audit.md`）。

河洛新增`line_conditions`证据视图，返回逐先后天实际元堂的二五位、五同一异众宗式和爻位偏好。`yuanTang.dangWei`为位序阴阳比较的旧别名；原典阴月当位位于`judge.line_conditions.source_dangwei`，定义待核、匹配为null，不用至点半年补定，也不生成十体评分，见爻位核对（本地数据：`validation/heluo-line-conditions-audit.md`）。

两数`date`为推算格里历`YYYY-MM-DD`，含1582年前；不自动切换儒略历，不转换年号／历史阴历。`numerology_evidence.birth_clock.calendar_policy`、同次轨迹和快照同步说明输入历制与未复原历史颁历；历史题注须先有具名历制转换依据。见历史命例日期核对（本地数据：`validation/heluo-historical-calendar-audit.md`）。

宋历研究另有具名Python来源算术入口，返回原书干支日和有理日分，见纪元／统元核对（本地数据：`validation/heluo-song-qi-audit.md`）及统天三位读法（本地数据：`validation/heluo-tongtian-audit.md`）。统天另返回分步修正轨迹，以及逐气端点与次年重算冬至的差额。未新增REST／MCP历史历法参数；不要将`profile_id`传给现有`heluo`或`canping`工具，也不把原书日分直接当UTC。

`core.song_clock`另有`source_clock_from_fraction`、`source_term_clock`及`compare_branch_window_to_term`三个Python来源入口，返回原辰刻、精确刻余及显式共用源钟制条件下的完整时支区间比较。相对源日位移须有独立日期依据；没有补生时中点、默认地点／UTC或切换公开月柱，见来源辰刻核对（本地数据：`validation/heluo-song-clock-audit.md`）。

两数`zone`省略／null统一为固定`+08:00`，不代表历史`Asia/Shanghai`；需要地区历史规则时明确传IANA名称。空白／非法时区拒绝；不存在或重复钟时不能猜，重复钟时须把已知UTC偏移放在`zone`。`birth_clock`证据增加实际时区、偏移秒数、夏令时量和规则库身份，见时区核对与兼容性（本地数据：`validation/numerology-timezone-audit.md`）。

`canping.method` 默认 `gu`（卷六日支起数），`ming` 须显式指定，其他值拒绝。`canping`、`heluo` 返回 `numerology_evidence`，含规则来源、取数轨迹、选中条文、语料身份与四项验证状态；可使用 `fields` 严格投影。变更与未决规则见[河洛与参评数审计](numerology-audit.md)。

`canping.gender` 必填且须明确男／女。配运 `dayun_method` 默认 `bazi_appendix_v1`（卷七附子平法与明确的整日借除约定），另有 `bazi_continuous_v1` 和保留旧命宫配运结构的 `legacy_minggong_v1`。可选 `analysis_datetime` 为带时区ISO时刻，返回 `canping_timing.selected`；无默认当前时刻，legacy不支持日期查询。新方案 `ming_gong` 为 `null`，实际起运和分段见 `canping_timing`、`dayun`、`liunian_series.rows[].segments`；未起运段不生成流年数。

`canping_timing.first_row`保留本次实际`dayun[0]`的编号、栏目和条文，三个方案均有；`timing_policy`视图包含此行，无需连带读取整组时间线。旧法首行的`ageStart/ageEnd`仍为年龄标签，`first_period=null`表示没有已核日期首运，不表示没有首行。现代方案的`first_period`与首行一致；两者均不代替`selected`查询当段。完整输出在投影前核对两种摘要与实际首行，编号、选文、边界、年龄或额外未计算事实不一致时返回不可重试的`numerology_source_inconsistent`。部分投影仍保留缺项与null，不从旧法标签补UTC日期。

旧命宫流年首年同样须与本次年柱一致，立春前可能标上一公历年；`liunian_series.birth_pillar_year`记录起始标签，`year_boundary=lichun_year_labels_only`与`age_policy`说明标签年龄。出生日期不变；这不表示旧配运或年序已有已核UTC起止，见旧方案年序核对（本地数据：`validation/canping-legacy-year-label-audit.md`）。

固定四柱Python函数`fatebridge.core.canping.liunian_series`另可在公历年未知时按已知年干支计算相对年序，返回`year=null`与`year_boundary=relative_ganzhi_year_labels_only`，不猜世纪；起运年龄前没有编号／诗文。这里不是REST／MCP／CLI的新入参模式，出生接口仍要求其既有出生资料。legacy行的`status=active`仅表示落在所给名义年龄运段，不能当作已核UTC区间。来源回执`canping_luck_substitution_v1`列出PDF64释文与同次实际查询配对，详见相对流年与替支释文（本地数据：`validation/canping-relative-years-audit.md`）。

`heluo.gender` 同样必填，已知中英文别名统一归一化；缺失、未知或无法识别的值不默认男命。`numerology_evidence.yaoci_collation` 返回局部爻辞校勘层身份与覆盖数；选文的 `text_provenance` 分开标明爻辞、注文和诗歌状态，已核爻辞保留旧文与PDF页码。校勘层散列与原继承语料散列分别报告，详见第六轮核对（本地数据：`validation/heluo-text-audit.md`）。

参评`canping_timing.schedule_basis`的固定摘要、范围说明、来源书目、版本与角色按当前载入资料及实际方法核验；时钟策略须与规则提供方一致。完整结果还核对同次`birth_clock`、对应`rule_trace`和原生释文段。矛盾在投影之前返回不可重试503 `numerology_source_inconsistent`，原因`runtime_canping_schedule_binding_conflict`；仅投影无关字段也不能隐藏它。缺失投影上下文不猜测，未知扩展字段保留；该约束不对任意人类释义作自动语义判分，见回执绑定核对（本地数据：`validation/canping-receipt-binding-audit.md`）。

河洛泰否三处具名条件引卦增加`source_section_id`及`source_condition_label`：泰九二明夷二在歲運段，否九四观四在葉者段，否九五晋五在歲運段。引用的单爻翻转不交换上下体，`applicability=null`、`automatic_application=false`、`replaces_chart=false`；不据引文认证目标卦全文或改写正式后天盘。疑读见`commentary_reading_notes`，见泰否核对（本地数据：`validation/heluo-taipi-commentary-audit.md`）。

同人六爻现采用同一底本PDF149—151页的单次目校文；九三“葉者”段保留不利措辞，九五“不葉者”续文跨页，九四“士後見榮”保留疑义注记。条件适用仍为null，诗歌及旧verdict来源不随注文提升，见同人原页核对（本地数据：`validation/heluo-tongren-commentary-audit.md`）。

河洛公开`selected_texts`视图增加`numerology_evidence.commentary_collation`。乾坤十二条`detail`采用底本注文，原继承文保存在`text_provenance.inherited_detail`；`commentary_sections`按原文分段，`applicability=null`及空选择集合表示未综合裁定，不能从`judge.xie`挑选葉／不葉。标题、注文、诗歌和旧`verdict`各有独立状态；诗歌未见于这十二爻解段落，来源待核。这一初批之后已逐批扩为72条、312条待校，初批依据详见第十三轮核对（本地数据：`validation/heluo-commentary-audit.md`）。

参评在已对读格的`selectionShun/Ni.witnesses`提供另一印本原文、`pdf_pages/body_pdf_page`、文本状态、`relation`及`replaces_selected_text=false`；实际主选文仍为`textShun/Ni`。`canping_text_collation.comparison_witness`提供独立版本与载入散列。对读仅36格，其中两格疑读，不增加主本1123格已确定数，不以对读文补主本○／□；字面不同不自动裁定错误，见印本对读核对（本地数据：`validation/canping-witness-audit.md`）。

参评同馆藏原图复读格的`selectionShun/Ni.reading_revision`保留旧疑读、状态、页码、见证ID与原因，`canping_text_collation.rereading_witness`记录馆方原图区域及清单身份。水部旧40格疑读复读后30格确定、10格仍未决；旧夹具原样保留，新增编号格和独立审阅者均为0。实际采用本次`textShun/Ni`，原页○与剩余□不按另一印本或典故补齐，见原图复读核对（本地数据：`validation/canping-native-rereading-audit.md`）。

参评校勘层1.11.0追加土部三格复读，一格确定、两格仍未定；3377女文录晝字形，不据此裁定词义。3379既有檠／晝转录保持，拟改已撤回，不生成虚假修订；继承语料对外返回副本，不能串改后续来源旧文，见土部原图与缓存核对（本地数据：`validation/canping-earth-rereading-audit.md`）。

参评校勘层1.10.0追加金部复读批次：15格保留1.9.0旧疑读，4格确定、11格仍未定；3314时运只补明花，仍带□及不确定状态，不能借用同号女文。保留麴蘖、追遊世，不按熟语改字；金部末十一条号文归属问题独立保留，不改计算编号。旧水火木及编号见证保持，见金部原图复读（本地数据：`validation/canping-gold-rereading-audit.md`）。

参评校勘层1.9.0在`additional_rereading_witnesses`继续追加木部批次，水、火及编号见证保持；四格以`reading_revision`保存1.8.0旧疑读，三格确定、一格只补明傾字而仍保留□。原页少见字面不改成熟语，整格仍未定的不计入确认数，见木部原图复读（本地数据：`validation/canping-wood-rereading-audit.md`）。

参评校勘层1.8.0在`canping_text_collation.additional_rereading_witnesses`分批记录后续复读见证，原`rereading_witness`水部记录保持。火部11格旧疑读经同一审阅者复读后六格确定、五格未决，逐格`reading_revision`保留1.7.0旧文及对应批次、页码与原因；未决末字不填，新旧批次不冒称独立复核，见火部原图复读（本地数据：`validation/canping-fire-rereading-audit.md`）。

参评1.7.0对六处未决编号增加`number_reading_evidence`，保留可见编号片段、页码、遮损原因及`resolution_status=unresolved`；`body_reading_status`另列暂定行正文可读、全圈空、局部圈空或仍有编辑疑读。其依据为此前字面转录，`body_evidence_basis=prior_literal_transcription_not_new_body_collation`，不表示本轮新校正文。十八格仍为整体未决，不因正文或圈空可辨增加已确定数；这些字段与`reading_revision`均已声明类型并支持严格叶字段投影，见编号证据核对（本地数据：`validation/canping-header-evidence-audit.md`）。

参评原页编号遮损的行返回`number_attribution_status=provisional_inherited_key`和`number_reading_uncertainties`，表示暂沿继承键定位、号文归属未定；该行所有已录栏目均为`source_reading_uncertain`，即使正文没有□或只有○。仅正文有□时返回`editorial_unknown_marker`；快照分别说明编号与正文疑读，详见火部核对（本地数据：`validation/canping-fire-audit.md`）及木部核对（本地数据：`validation/canping-wood-audit.md`）。

参评校勘层1.1.0起区分`source_printed_partial_blank`和`source_reading_uncertain`，分别表示原页局部○与编辑疑读□；后者带`reading_uncertainties`，仅正文含□时返回`editorial_unknown_marker`，不计入`collated_cells`。当前1.11.0已确定1123、未决47、未目读0，`pending_cells=47`；`part_coverage`分别列出五部覆盖。`numbered_table_visual_review_complete=true`仅表示编号表全部单次目读，`numbered_table_clear_readings_complete=false`仍有未决格；目读覆盖不代表全书符合、独立复核完成或预测有效，见土部与全表范围（本地数据：`validation/canping-earth-audit.md`）。金部末十一行按所选底本原页编号与正文归属选文，保留继承同号旧文，计算编号不重映射；差异原因与继承语料来源尚未核定，详见金部整段核对（本地数据：`validation/canping-gold-audit.md`）及水部整段核对（本地数据：`validation/canping-water-audit.md`）。

参评新增`text_selection`证据视图及`verses.selectionShun/selectionNi/pair_resolution`；逐条返回实际五行、编号、男命／女命／岁运栏及源文状态。`numerology_evidence.canping_text_collation`集中报告版本、实际载入语料散列和1123／1170格经目校及同一审阅者复读确定及疑读／未目读的分别计数。原页圈空、本地缺行与未选男女栏不同；顺逆仅一方有文为原典允许，同号为同一行。2838与3373错号已修正，未决2869不作通用补文，见第十五轮核对（本地数据：`validation/canping-text-audit.md`）。视图提供字段清单，调用仍传`fields`和`strict_fields=true`，不传视图名。

河洛新增`yuantang`证据视图，读取`chart.yuantang_derivation`的性别、配时序列、顺逆、实际至点半年、反事实敏感性和后天换卦。公开日期工具仍自动确定实际半年；`month_yang_ling`仅属固定四柱Python函数。该函数在子／午月缺半年时，仅结果唯一才保留计算与`yangLing=null`、`heLi=null`；结果有分歧则报错，见第十四轮核对（本地数据：`validation/heluo-yuantang-audit.md`）。

参评新增`canping_timing.schedule_basis`与`first_period`。来源回执按实际`profile_id`列原句的`role`及`applied_clause_ids`，区分所选附段与另书背景，并复制实际日期政策、折算结果和起运点；局部来源、全书与现实效验分别标注。`first_period`严格为同次`dayun[0]`摘要，不能代替`selected`查询当段；legacy为null且不补实际日期。首轮可复制`timing_policy`视图字段，完整`periods`、120年分段及121个立春继续按需读取。原句损坏或方法回执冲突在投影前返回不可重试503，不能更换出生参数绕过。详见配运来源映射（本地数据：`validation/canping-schedule-basis-audit.md`）。

两工具支持可选`birth_utc_offset=±HH:MM[:SS]`：在保留IANA `zone`的前提下核对已确认出生偏移、选择重复钟时的实际瞬间。未知偏移不猜，不存在钟时或地区／偏移冲突仍报输入错误；不将出生偏移固化为未来地区规则。显式偏移时`numerology_evidence.birth_clock`增加请求与实际偏移、`civil_fold`、重复钟时状态和具名政策，可窄投影读取；无偏移的普通结果不新增这些回执字段。参评附法零岁起运保留实际出生瞬间，后续周年仍按具名fold／gap政策和地区规则。见第五十一轮核对（本地数据：`validation/numerology-birth-fold-audit.md`）。

两工具 `time` 须明确为当地钟时 `HH:MM[:SS]`，可带显式小数秒；不将空白或未知补零点，不接受时间字段内的时区后缀，时区放 `zone`。显式零点有效。河洛 `judge.month_affinity` 的`version`为规则实现版本，`collation_version`与`collation_sha256`标识实际载入的校勘数据；缓存期不把后来文件的散列配给旧数据。它分开返回先后天的卦属月、另述月份条件和原页状态；`judge.deTime`仅卦属月匹配，未代表完整得时／得体。额外条件区分离散、跨年和季节；`month_label_match`仅月号，附加条件未决时即使月号未中也保持`match=null`。十三条`phases[].natal_najia_clause`另列原句、页码、月号和同阶段年命正纳／借用事实，及字连接范围与解卦例外未决，不输出整条吉凶；见第三十轮核对（本地数据：`validation/heluo-najia-qualifiers-audit.md`）。`opposed_month_conditions`保留相反条件。公开 `month_affinity` 视图可按需读取，63项明确属月、无妄未决及边界限制见第八轮核对（本地数据：`validation/heluo-month-depth-audit.md`）。

河洛`judge.najia[].lines[].source`提供实际位置的原页依据：`basis=hexagram_entry`为该卦条目已核，`pure_trigram_rule`为按纯卦内外位推演。`numerology_evidence.najia_collation`分开报告八纯卦基础48项正纳／12项借用与十三条卦解78／18项观察；其余51卦未逐卦目校。`source_issues`保留解卦两印本的列举次序差异，不改计算爻位。可用公开`najia`视图读取，数组应整体选择。来源表载入或实际位置冲突返回`numerology_source_inconsistent`、HTTP503、`retryable=false`，需维护者核对源表；出生参数不作为修正提示。坎卦及時／纳甲句的月号仍为空，见基础表与源据（本地数据：`validation/heluo-najia-foundations-audit.md`）。

河洛输出迁移：旧`judge.deTi.gua/present`日干查卦移至`judge.day_stem_mapping`。`judge.deTi`现为年柱纳音、实际上下体及两互体的有向五行关系，完整`present=null`；`generating_qi.condition_match`同时要求无元气与卦体生纳音，第87页反向关系另列于`mutual_generation`。公开`body_relations`视图可按需读取，语义与未决范围见第九轮核对（本地数据：`validation/heluo-body-audit.md`）。

公开`qi_phases`视图读取`judge.qi_phases`：先后天分别保存正反元气、化工的实际上下体／互体位置与阶段得失，旧聚合字段只表示并集。春季反化工按所核底本保留离、巽重叠，土用与乙亥例乾化工冲突尚待核。见第十一轮核对（本地数据：`validation/heluo-qi-audit.md`）。 新增`yuanqi_opposition`按出生年干支核正反目标，并逐阶段计算`yuan_absent && fan_present`；`direct_only_condition_match`只作范围比较，不覆盖包含两互体的所选取法。`fanYuan_policy`说明旧并集仅候选命中，`rescue_match=null`。来源非空改写或运行时目标／卦体冲突均返回不可重试503，见第四十三轮核对（本地数据：`validation/heluo-yuanqi-opposition-audit.md`）。 `solar_term.boundary_context`另保存当前节气、最近至点及下一四立的实际来源和绝对时刻，按原民用年使用共享相邻年窗口；`judge.seasonal_numbers`保留同一上下文及各起止来源。相邻求根不扩展显式模型公开年份，河洛端点来源见端点年核对（本地数据：`validation/heluo-solar-context-audit.md`）。参平`liunian_series.year_boundaries/solar_context`另列完整121个立春与摘要，`canping_timing.solar_year_context`同次相等，`selected.year_start_boundary/year_end_boundary`绑定查询所选年两端。1800–2200输入民用年所需的有界立春保留显式模型、完整120年及未来钟面条件，不能扩充公开年表；`calendar_boundaries`视图传其中字段。见完整年序核对（本地数据：`validation/canping-projection-audit.md`）。

两数默认开启真太阳时，必须明确`lon`或数值`gps_lon`，GPS字段优先，0°有效；缺经度会报错，不再使用上海缺省值。只有明确选择钟表时才传`use_true_solar_time=false`，此时未给经度输出null。`birth_clock`公开视图读取同次`numerology_evidence.birth_clock`，区分民用时刻、物理UTC瞬间、计算钟面与经度是否使用，见第十二轮核对（本地数据：`validation/numerology-clock-audit.md`）。

`heluo.judge.seasonal_numbers` 返回原始二数的正数比较、绝对数段、十一数式及六个实际节气窗口。原文重叠全部保留；`active` 表示是否落入时窗，`numeric_band_match` 只表示对应绝对数条件，得中未量化时为 `null`。`erShu` 相等标签现为“正数”，超出正数为“有余”；不据此裁定季节得中。公开 `number_conditions` 视图提供该组字段，调用时复制其 `fields`，视图名不是请求参数。

共享太阳模型可显式选 `FATEBRIDGE_SOLAR_TERM_MODEL=swiss`，要求实际 Swiss 文件模型。参评投影若超出该模式的已声明范围，返回 `solar_swiss_range`，完整120年要求不缩短；缺文件返回 `solar_swiss_files_required`。两者均为非重试503。选择范围、文件准备与原失败保留见[严格 Swiss 文件模式](solar-backends.md#严格-swiss-文件模式)。

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
- `astro_vimshottari`：独立月宿达沙，参数、任务字段、分盘与版本来源见[印占说明](jyotish.md)
- `astro_relative_chart`
- `human_design`：人类图双时刻、门线、身体图与来源审计；`POST /api/astro/human-design`，详见[人类图](human-design.md)

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
- `fengshui_annual_stars` / `fengshui_monthly_stars` / `fengshui_xuankong_natal` / `fengshui_assess`

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

## 咨询范围与禁区校验

场景按9主题、3服务和1多主题组合组织，另有风水基础计算。机器发现返回 consultation 元数据与共享策略，细则见 [技能分布](../skills/README.md)。

生死寿命、灾祸断言、临床诊断治疗与医疗择时不提供。卜卦 category 不再接受 death、health、pregnancy，择时 topic_id 不再接受 surgery；直接服务／核心调用亦不能将这些类别静默回退为 general 或 marriage。对已知明确的禁区问法，REST／MCP／CLI 在计算前返回非重试错误 consultation_restricted，issues 保留安全路径而不回显问题。其他无效枚举仍按 validation_error 处理。调用方须在选工具前完成语义判断；有限文本检测不是完整语义安全保证。

健康返回仅含盘内文化分类与对应，旧疾病风险根保留但禁用。没有中医辨证／体质问卷能力，不能据五行制定饮食、药物或治疗。

子女专项保留命主视角的星／宫与传统关系，不提供数量预测字段；时间信号不提供备孕、添丁或生育建议。孩子本人分析需使用孩子资料。普通星盘已移除死亡点计算及输出，剩余阿拉伯点不用于生死解释。

卜卦 `astro_horary` 与择日 `astro_election` 增加 `ut1_source`：默认 `swiss_delta_t`；`iers_c04` 仅使用固定1962-01-01 00:00至2026-09-19 00:00 UTC的IERS20 C04日值，不外推或自动回退。`clock_conversion.ut1_reference` 与盘面 `calculation_basis.earth_rotation.ut1_reference` 保留源区间／指纹／插值方式；模型路径为null。REST、MCP、CLI共享同一请求合同。只校正UT1，完整EOP和瞬时物理误差未认证。地心TT黄经事件搜索不需要试算时刻的UT1，可跨C04边界；宫位、地平及日出等仍要求对应UT1来源覆盖。见IERS UT1核验（本地数据：`validation/western-iers-ut1/report.md`）。

关系盘Marks的公开字段卡主层为 `marks_chart_pair`，读取 `marks_charts.inner/outer`；`chart`仍是内方个人盘别名。安全联合投影保留 `marks_charts` 根，非Marks模式返回空对象，不增加计算。两种请求形式共享这些响应字段；按需合同见[astro_relative_chart](contracts/astro_relative_chart.json)。
