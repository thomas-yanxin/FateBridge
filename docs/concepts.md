# 核心概念与结果阅读

FateBridge 把确定性计算、传统依据说明与自然语言对话拆开处理。本文说明三层分工、三端同源调用载体、时间口径，以及如何按分级与覆盖状态正确解读结果。首次安装请先看[快速入门](getting-started.md)，完整接入与字段规范见[开发者 / Agent 接入指南](agent-guide.md)和 [API 参考](api-reference.md)。

## 计算、解读与对话的分工

| 组成 | 负责什么 | 使用方式 |
| --- | --- | --- |
| FateBridge 计算引擎 | 按输入执行排盘、历法和规则计算，返回结构化结果与运行回执 | 本地运行，通过 MCP、REST 或 CLI 调用 |
| 方法参考 | 说明结果读取口径、经典/现代来源与适用范围 | `docs/interpretation/` 按需查阅 |
| 接入应用、Agent 客户端与模型 | 提供交互界面与对话，理解问题、调用工具并组织表达 | 由使用者或应用开发者选择和配置 |

计算服务本身无需 LLM API Key；对话能力取决于接入客户端所选模型。结果解读边界与参考总览见[方法参考](interpretation/README.md)。

## 工具与三端载体

用户提出的是自然语言问题，引擎接收的是结构化工具请求。REST、MCP 和 CLI 共享同一中央目录的规范工具名（`spec.name`）和业务输入字段（`spec.request_model`），仅传输载体与外层控制参数形态不同：

| 通道 | 工具寻址与业务输入载体 | 外层控制参数（`include` / `fields` / `as_of`） |
| --- | --- | --- |
| REST（HTTP） | `POST /api/...` 路径 + JSON 请求体 | URL 查询参数（如 `?include=view&fields=a&fields=b`） |
| MCP（FastMCP） | `run_calculation(tool="<spec.name>", arguments={...})` | 同级工具参数（`include`、`fields`、`as_of`） |
| CLI（`fatebridge`） | 子命令 `<spec.name>` + `--flag` 或 `--request-file PATH` | 子命令选项（`--include`、`--fields`、`--as-of`） |

| 概念 | 含义 | 何时使用 |
| --- | --- | --- |
| 工具（Tool） | 单项确定性计算的输入输出契约 | 已知计算目标，核对 Schema 后直接调用 |
| 分类（`family`） | 中央目录的 12 个能力分类 | 缩小发现范围，或用 `FATEBRIDGE_MCP_FAMILIES` 裁剪 MCP 公开范围 |

MCP 公开 `discover_tools`、`run_calculation` 与 `run_batch` 三个入口（无 MCP 资源）；三端能力边界与路径映射见[三端能力边界](api-reference.md#22-三端能力边界)，全量能力见[算法覆盖矩阵](algorithm-coverage.md)。

## 输入与时间口径

同一份请求中，出生时间、分析时间与“现在”属于不同时钟，不能混用：

- `birth_*` 描述出生事实，接口统一采用公历，农历须先转换；未知出生小时不得用默认值或示例值补齐。
- `analysis_*` 或查询时刻（如 `query_at`、`date`/`time`）指定本次分析目标，字段名以具体工具 Schema 为准。
- `as_of` 冻结未显式指定的当前时钟以便复现；它不能替代出生时刻，也不能覆盖工具要求显式给出的目标钟时。

出生时区取决于地点与历史日期；中式命理与西占本命盘对真太阳时的默认策略不同，需以实际工具合同和返回的 `time_adjustment` 为准。传统周期边界（节气年/月、生日年、返照周期等）的比较口径见[共享时间选择](interpretation/shared/timing-selection.md)。

## 一次结果包含什么

| 内容 | 用途 | 阅读时注意 |
| --- | --- | --- |
| 结构化业务字段 | 本次实际计算值、规则命中与分层证据 | 根键随工具变化，以输出合同或 `discover` 为准 |
| `run_metadata` | 工具名、版本、有效时间、`duration_ms`、`replay` 与 `omitted_fields` | 始终保留；默认省略真实存在的可选重型块时在 `omitted_fields` 列出 |

三端支持通过 `fields` 按点号对象路径严格投影，无效路径立即返回 `validation_error`（`issues[].code="unknown_projection_path"`）并在 `issues[].constraints.available` 提示当前可用键名；数组字段须选取所属父键后在客户端处理。

## 摘要与完整输出

三端默认返回核心层（仅对配置了 `default_omit` 的工具省略可选重型次级块，并在 `run_metadata.omitted_fields` 列出）。若需要按需追加被省略路径或专题视图，传入 `include`（支持点号路径或 `evidence_views` 名称）；若只需要指定分支证据，传入 `fields` 精确投影（与 `include` 互斥）；若需要无损完整业务载荷与全部时间线，则传入 `include=["*"]`（REST `?include=*`、CLI `--include "*"`）。完整控制约定见[输出控制与结果读取](agent-guide.md#输出控制与结果读取)。

## 状态与覆盖分开阅读

请求返回成功不等于所有方法层或现场事实都已完整覆盖。以家居风水分层结果（`fengshui_assess` 等）为例，应将整体状态、已覆盖层、缺失输入与规则冲突分开核对：

| 需要确认什么 | 读取字段 | 阅读边界 |
| --- | --- | --- |
| 整体与各层完成度 | `status`（`complete` / `partial`） | `partial` 只限制未完成层，不影响已完成层的有效判断 |
| 已实际算出的图层 | `coverage.implemented_layers` | 仅列真实完成计算并写入 `layers` 的方法层 |
| 当前缺失或未请求项 | `coverage.missing_inputs`、`coverage.not_requested_layers`（及 `unavailable_layers`） | 未请求或因缺输入未算不等于否定判断 |
| 流派或规则分歧 | `conflicts` | 各方法结论并列保留，不平均或合并成单一总分 |
| 叠盘与空间布局评估 | `palace_overlay`、`layout_analysis` | 仅在请求对应计算时产出，输出结构事实而非化煞处方 |

未知的现场事实不得按否定事实处理，也不能把条件候选升级为已确认现状。风水八工具的完整结构说明见[家居风水参考](fengshui.md)。

## 计算事实与解释

读取与转述结果时应保持三层分离：引擎实际产出的计算事实、所选传统来源对这些事实的解释口径，以及结合用户现实情况的可核对建议。星历精度需核对实际 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`（详见[星历数据](ephemeris.md)），咨询禁区见[硬边界](interpretation/shared/safety-boundaries.md)。
