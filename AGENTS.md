# FateBridge 工作方式

FateBridge 是面向 Agent 的泛心理领域统一计算引擎，目标是在各细分工具上提供快速、准确的结构化计算。按方法用权威参照和边界用例核验精度，按实际调用路径实测性能。

引擎只产出干净、紧凑、确定性的结构化计算事实，包括符号与关系、权重与计数、星历坐标与相位、量表维度得分。消费结果的大模型 Agent 依据实际返回的事实，结合用户问题与上下文生成行业映射、现代心理类比和个性化建议。

开发、安装、排错、审查和验收走工程流程。排盘、概念解释和结果解读走咨询流程，包括针对个人的假设或练习。仅审查代码、资料或评估标准时，即使材料含有出生资料，也不展开个案咨询。

## 工程与契约

- 变更前检查实际代码、共享契约、相关测试和 Git 状态，保留无关改动。1.0 发布前不保留向后兼容。直接删除过时接口、字段和实现，同步更新调用方、测试和文档，不为旧行为编写迁移脚本、兼容别名或回退分支。
- 每条计算规则由一个领域组件负责。REST、MCP 和 CLI 共用领域服务与契约。变更后分别验证算法结果和三端一致性，验收时区分本地协议、真实模型行为与部署结果。测试入口见[开发指南](docs/development-guide.md)。
- 书目元数据按来源维护一份，规则引用来源与版本，结果保留核验所需的规则轨迹、精度与缺项。
- 包管理统一使用 uv。用 `uv sync --extra dev` 准备源码环境，用 `uv run --extra dev` 运行命令。用 `uv add` / `uv remove` 变更依赖，用 `uv build` 构建。
- 用 `uv run --extra dev python scripts/build_codex_call_contracts.py` 生成按需调用合同，加 `--check` 检查漂移。不得手改生成文件，完整 Schema 留在合同中。

## 代码审查

- 同一规则的状态、计算和测试围绕同一职责组织。只有出现实际复用或需要隔离复杂边界时才拆分函数或组件。跨领域复用真正共同的计算原语，不依赖另一个领域的内部实现。直接修正职责或依赖方向，不用临时分支、函数内导入或预留框架绕过设计问题。
- 外部输入在所属边界校验一次，随后传递有具体类型的领域值。参数、字段和返回值标明类型，名称写清业务含义与计量单位。未知输入可用 `object` 在入口收窄，避免 `Any`、强制转换以及重复检查已由契约保证的字段。
- 仅在需要恢复、清理或转换边界错误时捕获具体异常。计算失败应可见，不用示例值或伪造的成功结果兜底。为极低概率的竞态或安全边缘情况增加复杂度前，先说明具体失败方式、发生可能性和维护成本，取得用户认可。
- 测试通过公开输入与输出锁定已知回归、可推导的不变量或易漏的契约，不把内部数据布局固定成测试要求。

## 咨询与方法选择

按用户实际问题、指定方法、已确认资料和当前连接的工具 Schema 选择能力；工具目录与 family 用于发现能力，不预设固定主题的调用组合。

概念问题不收个人资料，已有结果解释优先复用原 run。个人咨询先识别对象、主题、任务和实际时间范围；“算一下”“哪一年”本身不是起卦请求。单主题多体系不自动扩成人生报告。计算交给引擎，传统来源、分歧与现实建议分别说明。

需要核对具体方法的读取细节或来源时，按需查[结果解读参考](docs/interpretation/README.md)，不把整套参考设为每轮必读流程。

## 调用与交付

- 使用当前聊天已确认资料。独立咨询不查仓库、历史或记忆；明确要求沿用历史资料时再核对。
- 计算前检查[硬边界](docs/interpretation/shared/safety-boundaries.md)：不提供生死寿命、灾祸断言、临床诊断治疗或医疗择时。未知出生时刻不能猜，也不套默认值或示例；明确不知出生时辰时，对支持三柱模式的工具（`bazi_overview`、`bazi_birth_chart`、`bazi_timing`、`liuren_yearly_timing`）显式传入 `birth_time_unknown=true`（不传 `birth_hour`），其余无法缺省时辰的排盘不强行补齐；必要缺项简短追问，明确不知道后停止追问同项，交付已有可答部分。
- MCP 已连接且定义清楚时直接调用。只在工具或参数不清楚时按名称取得完整定义（`discover_tools(tool=...)` 或批量 `discover_tools(tools=[...], detail="brief")`，仅在需要完整输出 Schema 时传 `detail="full"` 与 `include_output_schema=True`）；本地无连接时可用 CLI（`fatebridge discover <tool...>` 或 `python -m fatebridge discover ... --detail brief`，需要完整输出 Schema 时加 `--detail full --include-output-schema`）。多工具或多主体共享出生/问事上下文资料时优先用 `run_batch`（REST `POST /api/batch`，CLI `fatebridge batch --request-file ...`）通过 `subjects` 与 `context`（问事时刻/地点）一次串联执行。工具发现不是每轮必经步骤。
- 离线核对常用合同见[按需合同索引](docs/contracts/README.md)，只读所选工具文件。以当前连接的实际 Schema 和公开范围为准，不因文件存在而调用隐藏工具。
- 默认交付返回核心层（`run_calculation`、`run_batch`、REST、CLI 与 Python API 一致），省略 `default_omit` 声明的可选重型次级块，并将实际被省略的路径记录在 `run_metadata.omitted_fields`。按需展开特定块时传 `include`（已发布的 `evidence_views` 名称或规范点号路径），需无损全量输出时传 `include=["*"]`；需要用严格点号路径投影替换返回载荷时传 `fields`。`include` 与 `fields` 互斥，各端严格校验路径与视图名，无效时报错并附 `constraints.available` 与 `suggestions`。
- 核对 `isError`、实际时区与时间粒度；按错误字段修正，仅 `retryable=true` 才重试。更正事实重建受影响输入；解释未变结果无需重算，需要固定默认时钟或复现时传入 `as_of`。
- 风水工具的输入口径与图层结构见[家居风水参考](docs/fengshui.md)与[现场资料与口径](docs/interpretation/fengshui/consultation.md)。
