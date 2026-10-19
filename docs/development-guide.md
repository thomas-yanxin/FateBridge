# FateBridge 开发指南

这份指南写给要在本仓库里改算法、补接口或修文档的开发者。当前仓库是 backend-only 的 Python 项目，没有内置前端应用。

## 环境准备

推荐用 [uv](https://docs.astral.sh/uv/) 安装依赖：

```bash
git clone https://github.com/Yonder-Lab/FateBridge.git
cd FateBridge

uv venv --python 3.12
source .venv/bin/activate
uv pip install -e ".[dev]"
```

如果你更习惯 pip，也可以这样操作：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

环境变量可以按需复制一份：

```bash
cp -n .env.example .env
```

已有 `.env` 时直接编辑，避免覆盖。环境变量、加载顺序、REST 鉴权与星历配置统一见 [快速入门](getting-started.md#配置环境变量)，避免另维护一份默认值。

## 项目结构概览

```text
FateBridge/
├── src/
│   └── fatebridge/         # 包代码（src layout：装包后才可 import）
│       ├── api.py          # REST (FastAPI) 入口
│       ├── mcp_server.py   # MCP (FastMCP) 入口
│       ├── cli.py          # CLI 入口
│       ├── application/   # 工具声明、绑定、执行与发现
│       ├── transports/    # REST/MCP 协议注册
│       ├── analysis/
│       ├── core/
│       ├── data/
│       ├── services/
│       └── utils/
├── tests/
├── docs/
├── pyproject.toml
└── CONTRIBUTING.md
```

各目录的职责大致如下：

- `src/fatebridge/services/catalog/`：各领域唯一工具声明及绑定；`tool_catalog.py` 按固定顺序装配 `CATALOG` 并补全合同，REST、MCP、CLI 共用这一份目录。
- `src/fatebridge/application/tool_spec.py`：`ToolSpec` 定义；`bindings.py`、`execution.py`、`projection.py` 分别负责绑定、执行和投影。
- `src/fatebridge/transports/rest.py`、`transports/mcp.py`：`register_rest` / `register_mcp` 注册器。
- 应用编排从 `application` 的定义模块导入，协议注册从 `transports` 导入；旧 core 兼容入口已删除。
- `src/fatebridge/application/discovery.py`：先筛选再描述目录，三端共用摘要与完整发现记录。
- `src/fatebridge/api.py`：从目录派生 REST 路由，处理 HTTP 层错误。
- `src/fatebridge/core/response_models.py`：公开根输出模型；`output_base.py`、`output_western.py`、`output_charts.py`、`output_chinese.py`、`output_bazi.py`、`output_reference.py` 共用部分响应基类，声明专业嵌套事实。
- `src/fatebridge/mcp_server.py`：从目录派生 MCP 工具，使用原生 FastMCP 协议工具。
- `src/fatebridge/mcp_transport.py`：原生 MCP 结构化结果、失败标记及安全输入校验。
- `src/fatebridge/cli.py`：从目录派生 CLI 子命令，支持 `list` / `describe` 自助发现。
- `src/fatebridge/core`：核心算法与合同。
- `src/fatebridge/services`：面向 transport 的编排层。
- `src/fatebridge/analysis`：复合分析逻辑。
- `src/fatebridge/core/requests/`：请求基类与领域模型。
- `src/fatebridge/utils`：出生输入、太阳时、展示、分析时钟、五行关系、地点与时区等公共能力。
- `tests`：回归测试、合同测试、API/MCP 对齐测试。
- `docs`：用户文档与开发者文档。

## 本地运行

启动 REST API：

```bash
API_HOST=127.0.0.1 python -m fatebridge.api
```

启动 FastMCP：

```bash
python -m fatebridge.mcp_server
```

健康检查：

```bash
curl http://localhost:8010/health
```

## 常用开发命令

### 测试

```bash
pytest -q
pytest tests/test_api_alignment.py -q
pytest tests/test_astrology_tools.py -q
pytest tests/test_chinese_metaphysics.py -q
```

测试需要在已安装 `.[dev]` 的 Python 3.10–3.13 环境里跑，这跟 CI 矩阵保持一致。注意不要用系统自带的解释器，否则容易出现伪失败。例如异步测试在缺少 `pytest-asyncio` 时不会真正执行，而是直接报 `FAILED`，错误信息通常是 `async def functions are not natively supported`。这类失败是环境问题，不是代码问题：先确认当前解释器里已经执行过 `pip install -e ".[dev]"`，再判断测试本身是否有错。同理，`black`、`isort`、`mypy` 也都来自 `.[dev]`，系统解释器里一般没有。

### 格式化与静态检查

```bash
black src/fatebridge/ scripts tests
isort src/fatebridge/ scripts tests
mypy src/fatebridge/
```

如果只想检查、不修改文件：

```bash
black --check src/fatebridge/ scripts tests
isort --check-only src/fatebridge/ scripts tests
mypy src/fatebridge/
```

## 推荐开发流程

### 新增或修改一个领域能力

建议按这个顺序来：

1. 先改 `src/fatebridge/core/*` 或 `src/fatebridge/analysis/*`。
2. 在 `src/fatebridge/services/*` 封装成对 transport 友好的返回结构。
3. 在 `src/fatebridge/core/requests/` 的对应领域模块定义 Pydantic 请求模型，调用方直接导入定义模块。
   大型独立领域也可拆为领域模型（如 `core/fengshui/models.py`）。在 `core/response_models.py` 声明响应根字段，复用 `core/output_*.py` 的专业嵌套类型，或在 ToolSpec 显式绑定领域 `output_model`；根输出继承 `ProjectedOutput` 以声明兼容投影警告，嵌套业务模型继承 `PartialOutput`，字段需支持投影缺省。动态字典键保持开放，值和列表条目应使用领域模型；同名但语义不同的根字段按工具覆写，避免以宽泛 union 掩盖错误。模型只校验、不回写响应。新增字段须检查真实构建器、可空与非默认分支，不能只照一个快照收紧类型。新工具缺少输出声明会在目录加载时失败。
4. 在 `src/fatebridge/services/catalog/` 的对应领域 `SPECS` 追加一个 `ToolSpec`；新领域还须接入 `tool_catalog.py` 的有序装配。声明的 REST / MCP 入口及 CLI 可支持的命令会自动派生，常规新增不需要再改 `api.py`、`mcp_server.py` 或 `cli.py`。`execution_hints` 默认描述已有本地只读计算；新增外部访问或写入能力时须声明实际环境影响，不能用 `idempotentHint` 表示结果确定性。
5. 在 `tests/` 增加能力测试。三端 parity 由 `tests/test_full_surface_validation.py` 自动覆盖，记得为新工具补一个代表性的 payload fixture。
   修改输出合同时运行 `tests/test_output_projection_contracts.py`：检查全目录可投影对象的必填字段、黄金样例的合法叶路径，以及原生 MCP 客户端与 REST、CLI 的结果。可经点路径裁剪的对象不能要求兄弟字段同时存在；数组条目与始终整块保留的 `run_metadata` 可保留必填事实。
6. 更新 `docs/api-reference.md`、`docs/algorithm-coverage.md`、`docs/scenario-routing.md` 与相关技能说明；若改了技能工具/输入，同步 `agents/interface.yaml`。工具计数、路由覆盖和技能契约均有现成测试。

家居风水的 `cli_request_file=True` 同时启用 JSON 对象／数组参数与 `--request-file`；新增复杂工具需明确启用、补嵌套校验与文件合并测试，不能仅依据模型顶层是否嵌套声称 CLI 可用。规则数据必须登记来源类别、版本、适用范围与约定，独立比较事实记录提交与 SHA-256；详见 [家居风水维护](fengshui.md#验证与维护)。

### 只改 transport 行为，不改算法

如果只是调整某一端的绑定（例如自定义 REST 绑定、CLI 不支持嵌套模型时的降级提示），改动应集中在 `src/fatebridge/transports/rest.py` / `transports/mcp.py` 的注册器，或 `services/catalog/` 的相应绑定处，并补充：

- request model 验证用例；
- `tests/test_full_surface_validation.py` 覆盖的三端 parity。

这样可以避免三端接入层继续漂移。

## 设计约束

### 输入归一化不要分散实现

涉及出生时间、地点、时区、真太阳时修正时，优先复用：

- `create_person_info`
- `normalize_birth_time`
- `resolve_birth_place_context`

不要在具体 endpoint 或 tool 里复制这些逻辑。

### 快照能力尽量复用统一合同

如果新增的工具需要“可读文本 + 可筛选 section”，优先复用：

- `snapshot_text`
- `snapshot_export`
- `parse_export_content`

不要自己发明另一套 section 过滤格式。

### 三端应共享 service 层与中央目录

新增能力时，不要把领域逻辑直接写进 `src/fatebridge/api.py`、`src/fatebridge/mcp_server.py` 或 `src/fatebridge/cli.py`。这三处只是从 `tool_catalog.py` 派生的 adapter，业务实现应留在 `services` / `core`，工具声明应留在 `CATALOG`。

### 维护依赖方向

核心算法、分析规则和共享工具不得导入应用层、领域服务或协议适配器。工具目录承担装配职责；协议签名与 FastAPI/FastMCP 注册放在 `transports`，执行时钟、receipt 和字段投影放在 `application`。共享出生计算从 `services.birth_context` 导入；共用占星基础表从 `core.astrology_tables` 导入。

请求模型从 `core.requests` 的领域定义模块导入；输入与显示分别使用 `utils.birth_input`、`solar_time`、`formatting`、`analysis_clock`、`elements`。领域工具声明不反向导入中央 `tool_catalog`，服务使用 `lazy_service` 代理保持延迟加载。保留全目录顺序、唯一性和公共合同；不得新增历史入口的兼容包装。

星盘内部代码从 `core.astro.birth`、`chart`、`relationship` 等定义模块导入，旧 `core.astrology` 已删除。故障注入应针对 `core.astro.runtime` 的 `swe`、`ephemeris_call` 或日志状态，以验证真实后端调用。原有 Swiss Ephemeris 锁与目录恢复仍由 `core.ephemeris_runtime` 管理。

出生公共响应使用 `services.birth_payload.build_destiny_payload`，当前时运状态使用 `services.timing_state.build_current_timing_state`。共享构造器不回调 `calculation`、`bazi`、`compatibility` 或 `timing` 用例服务；快照渲染留在 `timing_snapshots`，节气/农历查询留在 `calendar_tools`。这使计算状态和文本调整能分别维护，同时保持已有公开响应。

结构整理后运行 `pytest -q tests/test_architecture_boundaries.py tests/test_retired_entries.py`，并核对全工具输出与发现合同。完整测试和类型检查仍必须通过；不得为纯结构调整重新冻结数值基线。

## 测试策略

测试从已安装的 `src` 包导入，仓库根 `conftest.py` 负责 `tests.*` 命名空间；测试文件不再单独修改 `sys.path`。请求模型从 `core.requests` 领域模块导入，工具实现从定义模块导入。`tests/fixtures/transports.py` 提供已挂载 REST endpoint 查询及原生 FastMCP Client 调用，协议测试检查 text JSON 与 structuredContent 一致。`test_retired_entries.py` 检查旧模块、路由和包装保持移除，并验证原生协议成功/错误响应；`test_request_catalog_isolation.py` 在新进程验证独立嵌套模型 Schema、延迟编译与目录不加载计算引擎。

修改合同缓存时运行 `tests/test_schema_cache.py`，检查副本隔离、并发冷启动、同名类／输出覆写、模型重建、失败不缓存及逐次业务执行。不要缓存业务输入或结果。核心数值变更之外的清理，应先保存同环境的业务输出和发现合同，再与修改后结果比较；黄金快照仍需在规定的 Linux 环境完整核对，不应为清理重新冻结。

### 什么时候补 API/MCP 对齐测试

满足以下任一条件时建议补：

- 同时暴露 REST 与 MCP；
- 修改了请求字段默认值；
- 修改了响应结构；
- 修改了 `selected_sections`、`snapshot_export` 或 section 名映射。

### 什么时候补能力回归测试

满足以下任一条件时建议补：

- 改动了 `src/fatebridge/core/*`；
- 改动了算法边界条件；
- 改动了占星精度回退逻辑；
- 改动了导出合同或知识索引。

## 文档维护与验证

文档按读者任务组织；生成契约、规则资料和实际运行结果分别承担不同职责。修改前先定位信源，再更新依赖它的说明，避免同一个默认值分散维护。

| 变更内容 | 权威信源 | 需要同步的文档 / 生成物 |
| --- | --- | --- |
| 安装、版本、入口与运行配置 | `pyproject.toml`、`__init__.py`、`utils/runtime.py`、`.env.example`、入口模块 | 快速入门；README 仅保留最短示例；安全配置还查 `SECURITY.md` |
| 工具、字段、端口名称、公开数量 | `services/catalog/`、请求 / 响应模型、协议注册器、实时发现记录 | API 参考、算法矩阵；受影响的 README、接入例子和技能 |
| 选法、首轮字段、解读与来源 | 场景 `SKILL.md`、`agents/interface.yaml`、共享字段及规则数据 | 场景路由、技能资料；重建场景 manifest / 调用合同 |
| 模块职责和数据流 | 实际导入、绑定与执行代码 | 架构说明；已删除入口集中记录到迁移指南 |
| CI、打包与发布 | `.github/workflows/`、`pyproject.toml` | 本页与贡献指南；真实结果另行报告 |
| 可运行请求 | 当前请求模型和实际三端调用 | `docs/examples/` JSON 与示例索引；仅用虚构资料 |

### 检查命令与覆盖范围

只改文档时运行以下检查，不需要为措辞变化补业务测试：

```bash
python scripts/check_docs.py
python -m pytest -q tests/test_doc_tool_counts.py tests/test_scenario_routing_coverage.py \
  tests/test_skills_interface_contract.py tests/test_skills_engine_contract.py \
  tests/test_codex_call_contracts.py
python scripts/build_scenario_manifest.py --check
python scripts/build_codex_call_contracts.py --check
git diff --check
```

`check_docs.py` 只使用标准库，检查根目录、`docs/`（排除本地 `reviews/`）与 `skills/` 的 Markdown 内联链接、本地标题锚点、代码围栏、JSON 代码块及示例 JSON 语法。它不访问外网，不执行代码块，也不证明自然语言或接口参数正确；外部来源保留版本，按受影响内容另行核对。CI 对每个 Python 版本执行该检查。

现有文档测试把计数、路由覆盖、技能与生成合同关联到实时目录；`test_skills_engine_contract.py` 还会实际执行 CLI 示例，绑定测试进程解释器。修改可运行请求时，按[示例索引](examples/README.md)选择对应工具，验证模型与实际结果；结构校验成功不能替代三端或真实模型体验。

`AGENTS.md` 的 `codex-call-contracts` 区块由 `scripts/build_codex_call_contracts.py` 从实际 MCP 输入 Schema 和共享首轮字段生成，不能手改生成区。接口或首轮字段变化后先运行生成器，再用 `--check` 核对。场景矩阵或技能接口变化后同样重新生成 `data/agent_scenarios.json`，其中包含源文件散列，纯文案变更也可能需要同步生成物。

新增工具还须在 `core/response_models.py` 声明完整结果的必需业务根，目录装配缺声明会失败；不要为了让错误的 service 输出通过而放宽要求。公共投影模型允许字段缺失与合法 null，完整执行的必需根则不可缺失或为 null。相关回归包括 `tests/test_complete_output_contracts.py`、`tests/test_fengshui_analysis_progress.py`、`tests/test_relationship_and_career_semantics.py`、`tests/test_result_delivery_storage.py` 和 `tests/test_response_budget_contract.py`；验证跨端成功／失败、合法投影、状态转移、字符无损读取及多进程容量，而非只冻结一个用户答案。

### 最低同步面

接口或能力范围变化至少检查 README、API 参考和算法覆盖矩阵；涉及路由或技能再检查场景源及生成物。结构变化更新架构说明，删除支持的入口更新迁移指南。非生成源页面的导航或措辞调整通常无需改生成数据；生成器 `--check` 报告源文件散列变化时，重新生成后审查差异。

当前维护文档与具体实现应相互指向；历史审计只作为特定版本证据。一轮修改的测试数量、临时回执与工作区路径写在验收报告中，不作为长期能力承诺。

## CI、打包与发布

发布从干净 checkout 构建，并核对 wheel 的 Python 模块和 JSON 与当前源码清单一致。删除源模块后，旧 `build/lib` 的增量残留可能仍进入 wheel，因此发布构建应使用全新的工作目录。

`.github/workflows/ci.yml` 的 `test` 作业在 Ubuntu 24.04 上覆盖 Python 3.10–3.13，执行 pytest、black、isort、mypy；`floor` 在 Python 3.10 按最低直接依赖运行测试。黄金快照字节比对仅在受支持的 Linux x86_64 / Python 3.12 环境启用，其他环境跳过不代表该项通过。 每个作业记录解析后的完整依赖清单并上传 JUnit；`floor` 必须用 `uv pip install --system --resolution lowest-direct -e ".[dev]"` 在全新环境解析，不能仅固定 FastMCP 3.4.2 来代替全部最低直接依赖验证。

版本来自 `src/fatebridge/__init__.py::__version__`。发布需同步更新 CHANGELOG、检查包数据和版本、创建对应标签与 GitHub Release；仅改版本常量不会上传 PyPI。`publish.yml` 在 Release published 事件下构建 sdist/wheel，检查元数据、JSON 数据与 `py.typed` 后，通过已配置的 PyPI Trusted Publishing 发布。新增数据文件需确认被 `pyproject.toml` 的 package-data 覆盖；场景 `skills/` 目前随 Git 仓库分发，不由 wheel 包含。

## 依赖与运行时注意事项

### 核心占星盘

- 可以在缺少 `swisseph` 时继续运行；
- 但会回退到近似轨道模型；
- 某些 `hsys` 覆盖值依赖 `swisseph`。

### 西占推运

- 依赖 `kerykeion` / Swiss Ephemeris；
- 缺少依赖时不会自动降级。

这两类能力的差异在文档和代码里都要保持清晰，不要把“可运行”写成“等精度”。

## 提交前检查清单

提交前建议自查：

1. `pytest -q` 至少跑过相关子集。
2. `black --check` / `isort --check-only` / `mypy` 通过。
3. 新工具是否已在 `tool_catalog.py` 的 `CATALOG` 中声明（三端由此派生），并补了 `test_full_surface_validation.py` 的代表性 payload。
4. 文档是否更新了端口、能力名、section 名；若工具计数变化，`tests/test_doc_tool_counts.py` 是否仍通过。
5. 是否错误地把近似实现写成了高精度实现。

## 常用入口

场景源为技能的 `agents/interface.yaml` 与 `docs/scenario-routing.md`，生成物为包内 `data/agent_scenarios.json`。修改后运行 `python scripts/build_scenario_manifest.py`，用 `--check` 验证；PyYAML 只在 dev extra / 构建时需要，生产读取 JSON。新工具的场景角色须在源资料登记，不能只编辑生成文件。

`ToolSpec.reproducibility` 与 execution_hints 分别描述数值重放条件和环境副作用；新增读取默认时间的实现须经过 `execution_context.current_datetime`，随机实现须返回可固定的有效参数。三端共享 execute_tool；不要在某个 transport 单独生成 seed、使用服务器时区或拼装 receipt。实现/数据指纹按进程缓存，原地修改后须重启；重放仍须保存原输入并保持环境，不能只用 run_id 查询。

- 交互接口文档：`http://localhost:8010/docs`
- 架构说明：[architecture.md](architecture.md)
- API 参考：[api-reference.md](api-reference.md)
- 故障排除：[troubleshooting.md](troubleshooting.md)
