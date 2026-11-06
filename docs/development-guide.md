# FateBridge 开发指南

[文档中心](README.md) · [贡献流程](../CONTRIBUTING.md) · [架构说明](architecture.md)

改进计算引擎、接入接口或方法参考，从建立可复现的环境和找到对应职责层开始。完成修改后，再按影响范围验证计算依据与接入行为。FateBridge 使用 Python `src` 布局，需先安装包再运行；对话模型与前端由接入应用提供。协作、Issue 和 PR 流程见[贡献指南](../CONTRIBUTING.md)。

阅读导航：[环境准备](#环境准备) · [项目结构](#项目结构概览) · [本地运行](#本地运行) · [开发流程](#推荐开发流程) · [设计约束](#设计约束) · [测试策略](#测试策略) · [文档维护](#文档维护与验证) · [打包发布](#ci打包与发布)

## 环境准备

统一用 [uv](https://docs.astral.sh/uv/) 管理依赖、虚拟环境与构建；源码环境默认使用 `.python-version` 中的 Python 3.12：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge

uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

`uv.lock` 由 uv 生成并随源码提交，`--locked` 会在锁文件与声明不一致时报错。依赖调整后先更新锁文件，再验证：

```bash
uv add <package>
uv add --optional dev <package>
uv remove <package>
uv lock --upgrade-package <package>
uv lock --check
uv sync --locked --extra dev
```

首次 `doctor` 应能识别包版本和已安装依赖；缺少外部星历文件时按返回的能力范围处理。Windows 的环境准备见[快速入门](getting-started.md)。

当前独立输入、数值与原典转录维护在 `tests/data/`；`tests/fixtures/` 的 Python 模块提供代表请求与协议辅助。外部星历和大型参考按实际测试准备，缺失仍应报错。退役源码、旧输出快照、迁移哈希链和单次日志不再作为当前测试依赖，规则见[仓库维护](repository-maintenance.md)。

开发依赖继续声明在 `project.optional-dependencies.dev`，兼容既有的 dev extra。本页统一用 `uv run --locked --extra dev <command>` 运行仓库命令，无需激活虚拟环境。提交依赖变更时同时审查 `pyproject.toml` 和 `uv.lock`；不要手改锁文件。

环境变量可以按需复制一份：

```bash
cp -n .env.example .env
```

已有 `.env` 时直接编辑，避免覆盖。环境变量、加载顺序、REST 鉴权与星历配置统一见 [运行配置](configuration.md)，避免另维护一份默认值。

## 项目结构概览

代码位于 `src/fatebridge/`。领域声明由 `services/catalog/` 装配为中央目录，REST、MCP、CLI 经 `application/` 的共享执行层调用 `services/`，再进入 `core/` 与 `analysis/`。规则与知识位于包内 `data/`，方法参考在 `docs/interpretation/`。

完整目录职责、导入方向、请求流和[历法依赖](architecture.md#历法与星历依赖)统一维护在[架构说明](architecture.md#分层职责)。开发时从实际工具的目录声明、请求模型及领域测试定位修改入口。

## 本地运行

启动 REST API：

```bash
API_HOST=127.0.0.1 uv run --locked --extra dev fatebridge-api
```

启动 FastMCP：

```bash
uv run --locked --extra dev fatebridge-mcp
```

MCP 默认使用 stdio，由客户端启动时应配置上述命令及仓库工作目录；直接启动会等待协议输入。检查实际连接可运行 `uv run --locked --extra dev fatebridge doctor --mcp --family bazi`。

在另一个终端检查 REST：

```bash
curl http://localhost:8010/health
```

## 常用开发命令

脚本按领域维护，通用生成、CI 和发布入口留在 `scripts/` 顶层；见[脚本索引](../scripts/README.md)。测试按领域和公共边界分组，手算与协议辅助集中在 `tests/support/`；见[测试索引](../tests/README.md)。新增检查优先扩展已有同主题用例和参数，不为每次迭代创建一个文件。合并时保留输入、断言和标记，删除重复执行前核对实际消费的完整数据与覆盖它的现行用例。

先运行与改动相关的子集，再按共享合同的影响范围补齐检查。测试通过只能说明该环境和该检查覆盖的内容；CI、安装包与真实客户端需要各自验证。

| 改动范围 | 起始检查 |
| --- | --- |
| 单个算法或边界条件 | 对应领域测试与独立参考用例 |
| 请求模型、输出模型或默认值 | `tests/integration/test_full_surface_validation.py`、`tests/integration/test_output_projection_contracts.py` |
| 模块整理或入口移除 | `tests/quality/test_architecture_boundaries.py`、`tests/integration/test_ci_regressions.py` |
| 合同缓存 | `tests/integration/test_schema_cache.py` |
| 纯文档与导航 | [文档维护与验证](#文档维护与验证)中的检查 |

### 测试

领域与完整测试命令见[测试索引](../tests/README.md)，当前自包含集合由 `scripts/run_ci_checks.py` 维护。需要外部数值参考时，先按[星历安装](ephemeris.md)准备所选模型；独立 DE440 控制使用：

```bash
uv run --locked --extra dev python -m scripts.astronomy.prepare_reference_kernel
```

测试与格式工具均使用锁定的 dev extra。缺依赖先修复环境，不将收集成功、跳过或三端相同当作计算正确。数值测试显式选择实际模型；`tests/support/ephemeris_context.py` 管理 Moshier 环境与缓存恢复，`tests/support/output_facts.py` 比较完整未舍入事实，只排除执行回执。需要固定执行时刻时传入带时区的 `as_of`。

### CI 运行范围

代码变更在 PR 与 main／master push 上保留同一组自包含检查。同一 PR 的新提交取消旧 CI；主分支每次 push 使用独立并发组，运行中与排队中的提交均不互相替换。普通 README 和 `docs/` Markdown 变更仍运行独立的 `documentation` 作业与 `CI result` 汇总，不启动重测试；`docs/interpretation/` 中的可执行参考另触发相关回归。文档 JSON、工作流、源码和测试变更也保留完整检查。

Python 3.10–3.13 最新依赖、Python 3.10 最低直接依赖及 Windows／Python 3.12 锁定依赖共六种环境，各按收集后的节点分成三片并行执行；按近期 CI 的相对耗时均衡分配，每片再使用最多四个独立 pytest 进程调度。`.github/ci-test-costs.json` 只影响分片归属，不筛掉任何测试，也不是数值验收门槛。`scripts/run_ci_checks.py` 的默认本地命令仍运行整个自包含集合；分片不改变标记排除与断言。每片上传实际节点清单，汇总验证每个环境的全部节点恰好执行一次。uv 使用 setup action 的依赖缓存，按 Python／依赖策略隔离并仅由首片写入，不缓存测试资料或虚拟环境。只有 Ubuntu 静态检查作业另缓存 Black／Mypy 的增量状态，按锁文件、工具配置与 Python 源码区分；工具仍按文件内容自行失效。

云端不下载外部星历或大型独立参考。完整领域回归、数值与原典对照在本地使用原数据和固定门槛执行；云端通过不能作为这些项目的验收结论。混合测试文件中依赖本地资料的用例标记为 `local_data`，默认本地 `pytest` 不排除它们。

文档链接、示例语法、工具数量与路由覆盖由独立 `documentation` 作业在每次 push／PR 中检查。Black、isort、mypy 与生成合同在 Ubuntu／Python 3.12 锁定环境的 `quality` 作业执行，与测试并行。原有 Ubuntu 锁定环境的 CLI／API 和真实 stdio MCP 验证保留。`CI result` 要求所有选中作业成功且分片覆盖完整；失败、取消或意外跳过均不能通过，只有已确认的纯普通文档变更允许重作业全部跳过。

Windows Server 2022 / Python 3.12 在没有外部测试数据的锁定环境验证 stdio MCP、私有 ACL、重解析点拒绝、线程与跨进程锁、完整分页及三端合同。Windows 权限检查使用原生 ACL，不将 POSIX mode bits 当作 Windows 私有性的证明。

### 格式化与静态检查

```bash
uv run --locked --extra dev black src/fatebridge scripts tests
uv run --locked --extra dev isort src/fatebridge scripts tests
uv run --locked --extra dev mypy src/fatebridge/
```

如果只想检查、不修改文件：

```bash
uv run --locked --extra dev black --check src/fatebridge scripts tests
uv run --locked --extra dev isort --check-only src/fatebridge scripts tests
uv run --locked --extra dev mypy src/fatebridge/
```

## 推荐开发流程

### 新增或修改一个领域能力

建议按这个顺序来：

1. 先改 `src/fatebridge/core/*` 或 `src/fatebridge/analysis/*`。
2. 在 `src/fatebridge/services/*` 封装成对 transport 友好的返回结构。
3. 在 `src/fatebridge/core/requests/` 的对应领域模块定义 Pydantic 请求模型，调用方直接导入定义模块。
   大型独立领域也可拆为领域模型（如 `core/fengshui/models.py`）。在 `core/response_models.py` 声明响应根字段，复用 `core/output_*.py` 的专业嵌套类型，或在 ToolSpec 显式绑定领域 `output_model`；根输出继承 `ProjectedOutput` 以声明兼容投影警告，嵌套业务模型继承 `PartialOutput`，字段需支持投影缺省。动态字典键保持开放，值和列表条目应使用领域模型；同名但语义不同的根字段按工具覆写，避免以宽泛 union 掩盖错误。模型只校验、不回写响应。新增字段须检查真实构建器、可空与非默认分支，不能只照一个快照收紧类型。新工具缺少输出声明会在目录加载时失败。
4. 在 `src/fatebridge/services/catalog/` 的对应领域 `SPECS` 追加一个 `ToolSpec`；新领域还须接入 `tool_catalog.py` 的有序装配。声明的 REST / MCP 入口及 CLI 可支持的命令会自动派生，常规新增不需要再改 `api.py`、`mcp_server.py` 或 `cli.py`。`execution_hints` 默认描述已有本地只读计算；新增外部访问或写入能力时须声明实际环境影响，不能用 `idempotentHint` 表示结果确定性。
5. 在 `tests/` 增加能力测试。三端 parity 由 `tests/integration/test_full_surface_validation.py` 自动覆盖，记得为新工具补一个代表性的 payload fixture。
   修改输出合同时运行 `tests/integration/test_output_projection_contracts.py`：检查全目录可投影对象的必填字段、当前代表请求的合法叶路径，以及原生 MCP 客户端与 REST、CLI 的结果。可经点路径裁剪的对象不能要求兄弟字段同时存在；数组条目与始终整块保留的 `run_metadata` 可保留必填事实。
6. 更新 `docs/api-reference.md`、`docs/algorithm-coverage.md` 与相关方法说明；接口或首轮字段变化时重建调用合同。工具计数、文档覆盖和实际发现接口均有对应检查。

家居风水的 `cli_request_file=True` 同时启用 JSON 对象／数组参数与 `--request-file`；新增复杂工具需明确启用、补嵌套校验与文件合并测试，不能仅依据模型顶层是否嵌套声称 CLI 可用。规则数据必须登记来源类别、版本、适用范围与约定，独立比较事实记录提交与 SHA-256；详见 [家居风水维护](fengshui.md#验证与维护)。

### 只改 transport 行为，不改算法

调整某一端的参数绑定时，修改 `src/fatebridge/transports/rest.py` / `transports/mcp.py` 的注册器，或 `services/catalog/` 的相应绑定。共同的字段投影、快照选项和预算交付在 `application/response_delivery.py` 维护，JSON 格式化只负责序列化。按影响范围补充：

- request model 验证用例；
- `tests/integration/test_full_surface_validation.py` 覆盖的三端 parity。

这样可以避免三端接入层继续漂移。

## 设计约束

编码与审查遵循 [AGENTS.md 的代码简洁与边界原则](../AGENTS.md#代码简洁与边界)，职责和导入方向见[架构说明](architecture.md#分层职责)。领域计算留在 `core` / `analysis`，服务在 `services`，工具由 `services/catalog/` 装配；REST、MCP、CLI 共享执行与输出合同。

- 出生资料复用 `create_person_info`、`normalize_birth_time`、`resolve_birth_place_context`；分析时刻经 `services.timing_clock` 归一化，隐式当前时间读取 `core.execution_context.current_datetime`。
- 共享出生响应使用 `services.birth_payload.build_destiny_payload`，时运状态使用 `services.timing_state.build_current_timing_state`；快照、历法查询分别在 `timing_snapshots`、`calendar_tools`，构造器不回调上层用例服务。
- 可读文本和分节交付沿用 `snapshot_text`、`snapshot_export`、`parse_export_content`；执行回执、重放与投影由 `application` 管理。
- 请求、星盘与其他共享定义从实际领域模块导入，不添加旧入口兼容包装。Swiss 故障注入针对 `core.astro.runtime`，锁与路径恢复由 `core.ephemeris_runtime` 管理。

模块整理后运行 `tests/quality/test_architecture_boundaries.py`、`tests/integration/test_ci_regressions.py` 和受影响的领域／三端检查；不为结构调整重建数值参考。

## 测试策略

测试从已安装的 `src` 包导入，使用 pytest 的 `importlib` 模式；根 `conftest.py` 排除原始资料目录，测试不各自修改 `sys.path`。通用协议调用在 `tests/support/transports.py`，风水协议辅助在 `tests/support/fengshui_transports.py`，代表请求和原生客户端辅助在 `tests/fixtures/`；领域测试直接依赖这些定义，避免通过另一领域的测试文件间接加载。共享辅助与独立参考的入口见[测试索引](../tests/README.md)。`test_runtime_contracts.py`、`test_request_catalog_isolation.py` 分别核对运行时隔离和新进程目录加载。

共享计算或合同变化需核对 REST、MCP、CLI 的当前未舍入事实、错误和严格投影。独立期望值来自手算、外部数值或指定原典，并注明坐标系、时标、后端、日期范围、容差及未裁定项；复制生产公式、三端相同和 Schema 合法均不能单独证明计算正确。

清理前比较完整测试节点与实际输入／断言，删除已被同范围检查覆盖的冒烟、参数打印和旧入口专用测试。同一行为用参数化保留各输入和故障，不能删反例或改门槛。独立参考、来源身份和原始失败继续保留，维护规则见[仓库维护](repository-maintenance.md)。

CI 仅运行[明确选择的自包含集合](#ci-运行范围)；`local_data` 用例默认仍参与本地完整 pytest。HKO 分钟表的60秒容差与独立 TT 的1秒门槛分别保留，不能相互替代。当前数值与原典分歧见[算法状态](algorithm-status.md)。

## 文档维护与验证

页面职责、写作要求和各类内容的维护位置见[文档写作与维护](documentation-guide.md)。先核对实际实现和来源，再修改对应页面；纯措辞调整无需补业务测试。

### 检查命令与覆盖范围

只改文档时运行以下检查，不需要为措辞变化补业务测试：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py \
  tests/quality/test_doc_tool_counts.py tests/evaluation/test_agentic_replay.py \
  tests/quality/test_interpretation_examples.py \
  tests/quality/test_codex_call_contracts.py
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
git diff --check
```

`check_docs.py` 只使用标准库，默认检查根目录与 `docs/` 中的当前维护文档，以及脚本／测试索引中的 Markdown 内联／引用式链接、HTML 的 `href/src`、本地标题锚点、代码围栏、JSON 代码块及示例 JSON 语法。当前引用的文件和标题必须存在；原始文献按其实际位置保留，不混入过程日志。本地 `reviews/` 始终排除。它不访问外网，不执行代码块，也不证明自然语言或接口参数正确；外部来源保留版本，按受影响内容另行核对。CI 的独立 `documentation` 作业执行文档检查；纯文档变更也必须通过。

现有文档测试把计数、接口覆盖与生成合同关联到实时目录；`test_interpretation_examples.py` 还会实际执行 CLI 示例，绑定测试进程解释器。修改可运行请求时，按[示例索引](examples/README.md)选择对应工具，验证模型与实际结果；结构校验成功不能替代三端或真实模型体验。

`docs/contracts/` 的逐工具 JSON 与索引由 `scripts/build_codex_call_contracts.py` 从实际 MCP 输入 Schema 和共享首轮字段生成，不能手改生成文件。根 `AGENTS.md` 不嵌入这些大合同。接口或首轮字段变化后先运行生成器，再用 `--check` 核对。工具发现直接读取中央目录，不再维护独立主题 YAML 或生成的场景清单。

完整执行的必需业务根在 `core/response_models.py` 声明；嵌套必需事实使用 `FullFact[T]` 或 `PresentFact[T]`，由完整执行上下文递归核验，规则在完整执行时核对。公开投影允许缺少兄弟字段与合法 null，投影读取不启用完整执行上下文。不能为接收错误输出而放宽声明；相关验证从 `test_complete_output_contracts.py`、`test_algorithm_review_repairs.py` 和对应领域测试开始。

### 最低同步面

接口或能力范围变化至少检查 README、API 参考和算法覆盖矩阵；涉及调用字段时同步生成合同。结构变化更新架构说明，删除支持的入口更新故障排除中的升级说明。非生成源页面的导航或措辞调整通常无需改生成数据；生成器 `--check` 报告源文件散列变化时，重新生成后审查差异。

当前维护文档与具体实现应相互指向；历史审计只作为特定版本证据。一轮修改的测试数量、临时回执与工作区路径写在验收报告中，不作为长期能力承诺。历史报告并入专题时标明日期、模型与范围，保留失败和未决项，并与当前使用步骤分开。

## CI、打包与发布

发布从干净 checkout 构建，并核对 wheel 的 Python 模块和 JSON 与当前源码清单一致。删除源模块后，旧 `build/lib` 的增量残留可能仍进入 wheel，因此发布构建应使用全新的工作目录。

日常整理使用[仓库维护](repository-maintenance.md)中的预览与清理命令。构建缓存与当前参考分别维护；退役材料按实际依赖清理，不按扩展名误删当前来源或完整性校验。

```bash
uv build
uvx --from twine twine check dist/*
```

CI 的 `locked` 作业检查 `uv.lock`、安装环境、命令入口与真实 stdio MCP；文档检查在 `documentation` 作业中执行，生成物检查在 `quality` 作业中执行。现有最新版依赖矩阵和最低依赖作业使用独立的 `uv pip` 环境，不受开发锁文件约束。

矩阵与路径筛选见[CI 运行范围](#ci-运行范围)。最低直接依赖用 `uv pip install --system --resolution lowest-direct -e ".[dev]"` 在全新环境解析，不能仅固定 FastMCP 版本代替最低直接依赖验证。本地数值与来源检查按其实际后端、数据及适用范围报告。

发布前另行完成与改动相关的本地领域及外部数据验收；云端 CI 只证明其明确列出的检查通过。

版本来自 `src/fatebridge/__init__.py::__version__`。发布时递增该版本并同步更新 CHANGELOG；`publish.yml` 在 `master` 的 push CI 成功完成后，检出该次 CI 实际测试的提交，查询 PyPI，仅在版本尚未发布时构建 sdist/wheel。版本已存在则跳过构建与发布；查询失败则停止，不把网络错误当成新版本。流程不会自动递增版本，因此普通提交沿用已发布版本时不会更新 PyPI。

GitHub Release published 入口继续保留，并要求标签严格匹配 `v<包版本>`；已经由 `master` 自动发布的版本会跳过。两个入口串行执行，检查元数据、JSON 数据、`py.typed` 和安装包运行情况后，通过 PyPI Trusted Publishing 发布。PyPI 的 Trusted Publisher 须匹配仓库实际 owner/name、`publish.yml` 与 GitHub `pypi` environment；若该 environment 设置了人工审批，发布仍需审批。新增数据文件需确认被 `pyproject.toml` 的 package-data 覆盖。

新版本的 PyPI 上传成功后，独立的 `github_release` 作业使用 `contents: write` 创建
`v<包版本>` 标签和 GitHub Release，目标为同一个实际构建并发布的提交；其余作业继续
保留各自最小权限。已有 Release 保持原样，已有标签须指向该发布提交，否则停止，
不会移动标签。普通同版本提交跳过同步，不把较新的 master 冒充已发布包的源码。
Release 自动附加变更记录，并按 GitHub 的版本／日期规则选择 Latest。

若 PyPI 已上传而 GitHub 同步失败，优先在原工作流使用 **Re-run failed jobs**，保留
成功的检查与上传作业及其输出。完整重跑会因版本已存在而跳过上传和同步。也可先从
原发布作业的 checkout 日志及 PyPI provenance 核实完整源码 SHA，再用有仓库发布权限
的 `GH_TOKEN` 或 `GITHUB_TOKEN` 执行以下恢复命令（将版本、SHA 与仓库替换为核实值）：

```bash
uv run --locked --extra dev python scripts/sync_github_release.py \
  --version 0.1.1 --sha fee5e5a4373327e65f3b91e002121d49c18ee49c \
  --repo thomas-yanxin/FateBridge
```

## 提交前检查

确认已完成受影响领域、三端与静态检查，并同步公共合同、代表请求、文档和生成源。依赖可用、近似回退与实际数值精度分别核对，参见[历法与星历依赖](architecture.md#历法与星历依赖)；完整测试、云端 CI、真实模型和部署按实际运行范围报告。

## 常用入口

重放与默认时间的实现约束见[架构说明](architecture.md#执行回执与重放)。新增读取默认时间的实现使用 `execution_context.current_datetime`，随机实现返回可固定的有效参数；三端共用 `execute_tool` 生成回执。实现或数据原地变化后重启进程，使进程内缓存与实现一致。

- 交互接口文档：`http://localhost:8010/docs`
- 架构说明：[architecture.md](architecture.md)
- API 参考：[api-reference.md](api-reference.md)
- 故障排除：[troubleshooting.md](troubleshooting.md)

真实模型行为与激活评测按[Agent 行为验收](agent-evaluation.md)执行，分别报告机械判据与人工解释质量；安装接入见[MCP 部署](mcp-deployment.md)。

[MingLi-Bench 外部评估](mingli-bench-evaluation.md)另行维护固定来源、完整题目分类和命例级开发／留出划分。运行 `uv run --locked --extra dev python -m scripts.evaluation.build_mingli_evaluation --check` 核对清洗产物漂移；普通测试不启动模型，真实对话继续使用上述运行器，分别保留机械成绩和待人工审阅状态。
