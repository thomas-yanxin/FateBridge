# FateBridge 架构说明

[文档中心](README.md) · [开发指南](development-guide.md) · [核心概念](concepts.md)

本页面向要理解执行链路、定位问题或扩展能力的开发者。读完后应能判断一个变更属于哪一层，以及哪些合同需要一起验证。首次接入请先读[快速入门](getting-started.md)，字段与路由查询使用 [API 参考](api-reference.md)。

FateBridge 是一个纯后端 Python 项目，通过 REST、MCP 和 CLI 暴露领域计算。`src/fatebridge/services/catalog/` 按领域声明工具，`services/tool_catalog.py` 有序装配成唯一的 `CATALOG`；请求字段定义于 `core/requests/` 的领域模块。传输层复用服务和算法，但保留各端的绑定、名称和校验方式。

本页导航：[系统概览](#系统概览) · [分层职责](#分层职责) · [典型请求流](#典型请求流) · [关键实现约束](#关键实现约束) · [依赖边界](#内聚与依赖边界) · [运行边界](#运行配置与边界) · [扩展验证](#扩展与验证)

## 系统概览

```mermaid
flowchart TD
    Catalog["services/tool_catalog.py<br/>CATALOG / ToolSpec"] --> Registrar["transports/rest.py / mcp.py<br/>register_rest / register_mcp"]
    Catalog --> CLI["cli.py<br/>目录命令 + profile"]
    Registrar --> REST["api.py / FastAPI"]
    Registrar --> MCP["mcp_server.py / FastMCP stdio"]
    REST --> Execution["application/execution.py<br/>共享执行、输出校验、receipt"]
    MCP --> Execution
    CLI --> Execution
    Execution --> Bind["application/bindings.py<br/>ToolSpec.bind 绑定已校验请求"]
    Bind --> Services["services/*<br/>领域编排与响应构造"]
    Services --> Analysis["analysis/*<br/>专项与复合分析"]
    Services --> Core["core/*<br/>领域计算与导出合同"]
    Services --> Utils["utils/*<br/>输入归一化、地点、时区、错误"]
    Core --> Ephe["ephemeris_runtime.py<br/>Swiss Ephemeris 路径与共享锁"]
    Core --> Data["data/*<br/>知识及条文 JSON"]
    Analysis --> Core
```

`application/tool_spec.py` 的 `ToolSpec` 是冻结 dataclass，包含 key、family、请求与输出模型、绑定器、各端名称、必需业务根和重计算标记。`core/response_models.py` 定义公开根契约，复用 `core/output_western.py`、`output_charts.py`、`output_chinese.py`、`output_bazi.py`、`output_reference.py` 的专业嵌套模型；它们继承 `output_base.PartialOutput`，支持部分响应、可空事实与增量扩展，只校验而不重写业务 JSON。目录将输出模型附到 ToolSpec；`rest_specs()` / `mcp_specs()` 过滤各端集合，注册器据此挂载入口，CLI 按模型生成参数。新增工具须同时声明响应字段契约。

`application/discovery.py` 在生成 Schema 前筛选目录，供 REST `/api/tools`、CLI `discover` 和 MCP 摘要/单工具资源共用。MCP host 的 family 配置只筛选注册表；默认保留完整集合。`ToolSpec.execution_hints` 是三端发现记录与 MCP annotations 的共同来源，描述环境影响，不描述数值确定性。

当前 FastAPI 提供 86 个业务 REST 路由，另有 `GET /api/tools` 发现接口与 `/health`、`/ready`、`/metrics` 运维端点；FastMCP 默认提供 87 个 MCP 工具。中央目录包含 88 条记录，CLI 可执行其中 87 条。CLI 另有 `list`、`discover`、`describe`、`profile`、`doctor`；风水工具明确启用嵌套 JSON `--request-file`，关系盘嵌套入口仍使用已有扁平变体。

家居风水领域位于 `core/fengshui/`，请求、响应、公共方位、历法边界、八宅、年度飞星、玄空历史宅盘、砂水与可读快照各有模块。`services/fengshui.py` 只编排独立层和逐人差异，`data/fengshui/rules-v1.json` 保存版本与来源并随包发布。工具在中央目录显式绑定领域响应模型；`cli_request_file` 声明复杂 CLI 输入支持，不改变未启用工具的行为。规则与验收边界见 [家居风水](fengshui.md)。

目录声明让领域能力共用信源，不意味着所有端逐项同名同形：独立八字命盘使用 `/api/cn/bazi/birth`，`analyze_destiny` 是 MCP / CLI 综合命理；关系盘 REST 使用嵌套对象，MCP / CLI 使用扁平字段。具体映射见 [API 参考](api-reference.md#24-三端能力边界)。

## 分层职责

| 层 | 主要路径 | 职责 |
| --- | --- | --- |
| 工具声明 | `services/catalog/`、`services/tool_catalog.py`、`application/tool_spec.py` | 领域声明、中央装配与不依赖协议框架的工具描述 |
| 应用编排 | `application/bindings.py`、`execution.py`、`projection.py` | 请求绑定、统一执行与输出校验、字段投影 |
| 能力发现 | `application/description.py`、`discovery.py`、`scenarios.py` | 公共描述、目录筛选、场景清单；共享描述避免反向引用 |
| 协议注册 | `transports/rest.py`、`transports/mcp.py` | REST/MCP 签名、注册、协议错误与输出选项 |
| 请求模型 | `core/requests/` | 公共校验基类、领域字段、默认值与取值范围 |
| 传输 | `api.py`、`mcp_server.py`、`cli.py` | HTTP/协议/参数处理，错误、元数据与输出包装 |
| 服务 | `services/*.py` | 调用核心、拼接分析、生成快照；`run_metadata.py` 生成响应溯源 |
| 分析 | `analysis/*.py` | 婚姻、事业、健康等专项及配合度/时运复合规则 |
| 核心 | `core/*.py`、`core/metaphysics/` | 历法、八字、占星、紫微、六壬、太乙等领域计算 |
| 子技法 | `core/predictive/`、`core/local_techniques/` | 西占推运和本地技法模块；两者均为目录，不是旧单文件模块 |
| 运行公共层 | `utils/birth_input.py`、`solar_time.py`、`formatting.py`、`analysis_clock.py`、`elements.py`、`places.py`、`timezones.py`、`runtime.py`、`errors.py` | 出生输入、太阳钟、展示、分析时钟、五行关系、地点/时区、配置与错误 |
| 星历运行时 | `core/ephemeris_runtime.py` | 数据路径、模型标识、共享状态与并发保护 |
| 数据 | `data/knowledge/`、`data/canping/`、`data/heluo/` | 知识与条文 JSON，打包进 wheel |
| 导出 | `core/export_contracts.py`、`export_parser.py`、`services/structured_snapshot.py` | section 合同、文本解析与快照构造 |
| 验证 | `tests/`、`tests/golden/` | 领域回归、跨端对齐、完整工具面、快照与文档契约 |

## 典型请求流

### 独立八字命盘

```mermaid
sequenceDiagram
    participant C as Client
    participant R as REST handler
    participant E as application/execution.py
    participant B as ToolSpec.bind
    participant S as services/bazi.py
    C->>R: POST /api/cn/bazi/birth
    R->>R: 鉴权与请求模型校验
    R->>E: 线程池执行 execute_tool
    E->>E: 固定默认时钟与调用上下文
    E->>B: 绑定已校验的请求
    B-->>E: service 与参数
    E->>S: calculate_bazi_birth
    S->>S: 归一化出生时间与领域计算
    S-->>E: 业务结果与快照
    E->>E: 输出校验与 run_metadata
    E-->>R: 完整结果
    R->>R: 字段投影与响应预算处理
    R-->>C: JSON 响应
```

`api.py` 不直接手工构造领域对象。`ToolSpec.bind` 通过公共绑定器构造请求，再交服务执行。REST 同步服务均在线程池执行，标为 `cpu_bound` 的重计算另受信号量限制；这保护事件循环并限制进程内并发，不是速率限制或任务队列。

`analyze_destiny` 的 MCP / CLI 绑定进入 `services/calculation.py::calculate_destiny_analysis`，在命盘之上组织综合分析。独立八字命盘绑定到 `services/bazi.py::calculate_bazi_birth`。

### 快照与输出流

一次成功请求依次经过业务输出校验、执行回执、字段投影、快照选项和响应预算处理。这一顺序决定了保存与交付的数据范围。

支持双层快照的服务生成可读的 `snapshot_text` 与 `snapshot_export`，使用 `parse_export_content` 或共享快照构造器；部分工具只有文本或结构化数据，覆盖见 [算法矩阵](algorithm-coverage.md#4-快照协议覆盖)。`selected_sections` 只筛选导出文本，完整业务数据与原快照仍在。显式选择没有命中时导出为空，不回退全文。

成功业务输出由共享模型验证，但不经模型重写，保留原有字段与数值。共享执行层附加 `run_metadata`，传输层随后执行 `fields` 投影，再按选项去掉顶层 `snapshot_text`。MCP 通过 `mcp_transport.py` 返回 structuredContent、JSON text 和原生 isError；REST 返回 JSON 对象，CLI 写 stdout 并用退出码表达失败。MCP 前置 middleware 将模型错误转换为安全的统一字段提示，避免框架回显提交内容。完整选项见 [API 参考](api-reference.md#25-字段投影与输出体积)。

### 合同缓存

`core/schema_cache.py` 缓存默认验证 Schema 和合同 SHA-256：按实际模型类、core schema 身份及完整结果必需根声明区分，每类缓存最多 256 条；模型 `model_rebuild()` 后自动使用新版本，公开 Schema 返回深拷贝。

动态修改模型配置、Schema hook 或嵌套模型而未重建根模型时，需要调用 `clear_contract_caches()`。业务输入、输出、调用时间和 execution receipt 仍逐次生成。输出在领域返回后、receipt 附加后分别校验；完整执行必须包含 `ToolSpec.required_output_fields` 的非 null 业务根，公共可投影模型仍允许省略字段。异常错误包络按内部输出错误处理。REST 不再重复第三次校验同一完整结果。

### 大结果交付

`application/result_delivery.py` 将超预算结果写入按操作系统用户隔离的私有临时目录。保留范围是投影与快照选项处理后的响应，不能从摘要交付恢复未选字段；完整导出须首次保留完整范围。原 JSON 保留 `payload`，字符分页用 UTF-8 字节边界索引 seek 原正文，散列与小型 manifest 在写入时生成；字段展开首次定位后仅保存索引，不复制正文或无限缓存用户结果。

跨进程锁覆盖容量预留、提交、读取与回收，容量计量包含已提交 sidecar。POSIX 使用 owner-only 权限和 flock；Windows 通过平台限定的 pywin32 使用用户 SID、私有 ACL 与原生文件锁，拒绝重解析点。缺少当前索引元数据的旧记录返回 `result_unavailable`，不会自动升级或改写；临时原子替换文件可能增加瞬时磁盘峰值。此机制提供同 run 展开，不提供咨询事实继承；`parent_run_id` 仍只是关联标记。

原生 MCP 从投影后的字典直接生成 structuredContent 和 JSON text，不经过文本反解析。协议工具仅通过原生 FastMCP 调用，REST 通过已挂载路由调用；旧 Python 别名和模块级 `.fn` 包装已删除。内部导入使用定义模块（如 `utils.errors`、`core.requests`、`core.predictive` 的具体子模块），不依赖兼容重导出。

## 关键实现约束

### 出生时间与分析时钟

出生输入构造与校验集中在 `utils/birth_input.py`，太阳时归一化集中在 `utils/solar_time.py`，时区解析集中在 `utils/timezones.py`。中式出生模型默认开启太阳时、核心星盘默认关闭；缺省值和用户显式选择有不同的缺经度处理，不可在适配层丢失。四柱年/月与节气、起运按实际民用时刻，日/时柱等遵循太阳钟规则；应保留原始时刻与修正结果供复核。

### 星历模型与共享状态

核心占星可走本地 `swisseph` 或轨道近似路径，显式复杂宫制缺运行时则报错。西占推运、事件和生命周期依赖 backend，缺失时不使用 FateBridge 的轨道近似替代。包可导入仍不保证星历数据存在，实际模型需检查 `ephemeris_model` 与 `engine_is_approximate`，详见 [算法覆盖](algorithm-coverage.md)。

Swiss Ephemeris 存在共享 C 状态。直接调用与会修改目录的第三方调用通过 `ephemeris_runtime.py` 的可重入锁协调；第三方操作正常或异常结束都应恢复配置目录。新增星历调用应复用这一层，避免跨请求的目录漂移。

### 执行回执与重放

`run_metadata` 在原 ID、时间、引擎与近似标志上增加版本、合同/输入/业务摘要、环境指纹、实际时间与重放参数。`application/execution.py` 的 `execute_tool` 包装现有 `execute_spec`，REST 由原执行器限制重计算并发并卸载到线程，MCP / CLI 共用执行层；execute_spec 保留无元数据的服务调用契约。ContextVar 隔离默认时钟，无 seed 随机六爻保留本次 seed，没有运行数据库。重放需要保存原始请求和环境，`run_id` 本身不能查询或恢复一次计算。

### 场景发现

`data/agent_scenarios.json` 从 13 个技能 YAML、共享规则与场景路由文档生成，共 14 项（9 主题、3 服务、1 多主题组合及独立的 `fengshui` 基础计算路由），`application.scenarios` 将其关联到实时 ToolSpec。REST / CLI / MCP resources 共用 manifest，生产只读 JSON，不增加 YAML 运行依赖；CI 核对生成物与源资料。接口将直接工具与知识支撑、条件服务、组合主题依赖分开，生成和运行时验证依赖闭包及循环，场景筛选展开依赖后再与传输和 family 求交集。发现结果保留依赖条件、原始路由和逐项缺失，不把可调用工具当作自动执行清单。

## 内聚与依赖边界

入口和协议适配器调用应用层，应用层调用领域服务，领域服务调用 `core`、`analysis` 与公共工具。`services/tool_catalog.py` 是装配入口，可以依赖应用层的 `ToolSpec` 与绑定工厂；普通领域服务不依赖协议适配器。`application` 不导入 FastAPI / FastMCP，动态协议签名由 `transports` 生成。

| 关注点 | 当前模块与维护规则 |
| --- | --- |
| 出生公共计算 | `services/birth_context.py` 复用归一化、四柱与历法；`birth_payload.py` 构造公共命盘响应 |
| 时运与日历 | `services/timing.py` 编排时运，`timing_state.py` 计算各层状态，`timing_snapshots.py` 组织文本；日历查询用 `calendar_tools.py` / `calendar_input.py` |
| 星盘 | `core/astro/` 按出生、几何、星历、宫位、盘面与关系盘拆分；公共星座、庙旺和界表位于 `core/astrology_tables.py` |
| 请求模型 | `core/requests/base.py` 管理未知字段和日期校验；`birth.py` 管理出生基类，领域模块直接导入所需类型 |
| 工具声明 | `services/catalog/` 各领域拥有 `SPECS`、绑定和延迟服务代理；不反向导入中央装配器或提前加载计算引擎 |
| 输入与展示 | `utils/birth_input.py`、`solar_time.py`、`formatting.py`、`analysis_clock.py`、`elements.py` 各自承担单一公共职责 |

`tests/test_architecture_boundaries.py` 检查核心/分析/工具层不依赖应用与协议层、应用与服务不依赖协议适配器或旧兼容入口，并核对含函数内导入的静态导入图无循环。它不分析动态 `importlib` 调用或第三方库内部依赖。

## 运行配置与边界

REST 默认监听 `0.0.0.0:8010`，可选 API Key 鉴权；CORS、运维路径豁免和配置加载见 [快速入门](getting-started.md#配置环境变量) 与 [安全策略](../SECURITY.md)。FastMCP 默认使用 stdio，由 host 启动子进程。CLI 不需要 REST 服务，`profile` 可为同一命主编排多套盘，`--subject-file` 复用出生信息。

当前项目不包含内置 Web 前端、持久化运行数据库、账户体系、队列或多服务编排。大结果交付仅提供有有效期和容量上限的本地临时文件，不是历史查询服务。网络访问与生产控制由部署方的网关和 host 承担。

## 扩展与验证

新增能力通常先实现 `core` / `analysis`，封装 service 和 request model，再追加 `ToolSpec`。常规新增工具无需手工修改三个 transport 的领域入口，但只有声明对应 surface 且 CLI 模型可表达时才会实际暴露。

为新工具补 `tests/fixtures/surface_payloads.py` 的代表请求，运行领域回归与 `test_full_surface_validation.py`；涉及输出、默认值或投影时补跨端对齐证据。文档、场景清单及技能契约同步方式见 [开发指南](development-guide.md#文档维护与验证)。黄金快照与 CI 平台约束也在那里统一维护。

玄空版本独立放在 `data/fengshui/xuankong-v1.json`，与基础规则版本分别发布。`core/fengshui/xuankong.py` 只使用历史定运及磁北宅向，按输入误差解析候选角区；合参新增的是独立层，不给年度盘添加山向星，也不按当前元运重算宅盘。详见 [来源与合同](fengshui-xuankong.md)。

## 旧入口迁移

旧路由、字段别名、包级重导出与 `.fn` 包装的替换表统一见 [迁移指南](migration.md)。当前代码直接导入职责模块，协议调用使用正式路由或原生 MCP Client。
