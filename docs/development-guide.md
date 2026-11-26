# FateBridge 开发指南

[文档中心](README.md) · [贡献流程](../CONTRIBUTING.md) · [架构说明](architecture.md)

FateBridge 使用 Python `src` 布局，通过共享执行层和中央目录统一提供 REST、MCP 与 CLI 能力。建议按**安装 → 复现 → 修改 → 验证 → 贡献**的闭环开展开发：先配置隔离环境并用最小虚构请求复现现象，再按变更范围修改代码与契约，运行对应测试与静态检查后提交 PR。协作与 PR 规范见[贡献指南](../CONTRIBUTING.md)。

## 环境准备

统一使用 [uv](https://docs.astral.sh/uv/) 管理依赖与虚拟环境，源码默认使用 `.python-version` 指定的 Python 3.12：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

变更依赖时使用 `uv add` / `uv remove`（开发依赖加 `--optional dev`），确保 `pyproject.toml` 与 `uv.lock` 同步，并通过 `uv lock --check` 校验。如需自定义端口、鉴权密钥或星历路径，可复制配置模板 `cp -n .env.example .env`，配置说明见[运行配置](configuration.md)。

## 项目结构概览

源码位于 `src/fatebridge/`：领域声明放在 `services/catalog/` 并由 `services/tool_catalog.py` 装配；REST、MCP 与 CLI 经 `application/` 调用 `services/`，再进入 `core/` 与 `analysis/`；规则与知识数据位于包内 `data/`；方法解读参考位于 `docs/interpretation/`。完整分层职责见[架构说明](architecture.md#分层职责)。

## 本地运行

```bash
# 启动 REST API（仅本机监听）
API_HOST=127.0.0.1 uv run --locked --extra dev fatebridge-api

# 启动 FastMCP stdio 进程或验证连接
uv run --locked --extra dev fatebridge-mcp
uv run --locked --extra dev fatebridge doctor --mcp --family bazi
```

## 常用开发命令

脚本按领域维护，通用构建与检验入口在 `scripts/` 顶层，见[脚本索引](../scripts/README.md)；测试按领域和公共边界分组，见[测试索引](../tests/README.md)。

| 改动范围 | 起始检查 |
| --- | --- |
| 单个算法或边界条件 | 对应领域测试（如 `tests/bazi`、`tests/fengshui`） |
| 请求模型、输出模型或默认值 | `tests/integration/test_full_surface_validation.py`、`tests/integration/test_output_projection_contracts.py` |
| 模块整理或导入依赖 | `tests/quality/test_architecture_boundaries.py`、`tests/integration/test_ci_regressions.py` |
| 合同缓存与运行时配置 | `tests/integration/test_schema_cache.py`、`tests/integration/test_runtime_and_errors.py` |
| 文档与生成合同 | [文档维护与验证](#文档维护与验证)中的检查 |

运行自包含 CI 测试集、代码格式化与静态类型检查：

```bash
uv run --locked --extra dev python scripts/run_ci_checks.py
uv run --locked --extra dev black --check src/fatebridge scripts tests
uv run --locked --extra dev isort --check-only src/fatebridge scripts tests
uv run --locked --extra dev mypy src/fatebridge/
```

需要外部星历数值参考时，按[星历安装说明](ephemeris.md)准备数据，或运行 `uv run --locked --extra dev python -m scripts.astronomy.prepare_reference_kernel`。

## 推荐开发流程

### 新增或修改领域能力

1. 在 `src/fatebridge/core/*` 或 `src/fatebridge/analysis/*` 实现领域计算逻辑。
2. 在 `src/fatebridge/services/*` 编排结构化业务返回与方法追溯。
3. 在 `src/fatebridge/core/requests/` 定义或更新请求模型，在 `src/fatebridge/core/response_models.py` 与 `core/contracts/` 声明输出模型（业务根继承 `ProjectedOutput`，可投影嵌套对象继承 `PartialOutput`）。
4. 在 `src/fatebridge/services/catalog/` 追加或更新 `ToolSpec`（新领域须接入 `tool_catalog.py`）。所有 CLI 工具均支持 `--request-file`；复杂嵌套输入可设 `cli_request_file=True` 在 `discover` 示例中优先提示文件传参。
5. 在 `tests/fixtures/surface_payloads.py` 补充代表请求，并编写领域回归与三端契约测试。
6. 同步更新 [API 参考](api-reference.md)、[算法覆盖矩阵](algorithm-coverage.md)及相关文档，必要时重新生成按需调用合同。

### 调整传输层行为

修改 REST 路由绑定或 FastMCP 注册器位于 `src/fatebridge/transports/rest.py` 与 `src/fatebridge/mcp_server.py`，公共 `detail` 分级（`compact` / `audit`）与严格 `fields` 投影位于 `src/fatebridge/application/response_delivery.py` 与 `src/fatebridge/application/projection.py`。修改后运行 [完整接口验证](../tests/integration/test_full_surface_validation.py)、[CLI 集成测试](../tests/integration/test_cli.py) 与 [投影合同测试](../tests/integration/test_output_projection_contracts.py)。

## 设计与测试约束

编码与审查须遵循 [AGENTS.md 代码审查原则](../AGENTS.md#代码审查)：领域计算保持在 `core/` 与 `analysis/`，不反向导入 `application/` 或传输层；出生输入复用 `create_person_info`、`normalize_birth_time` 与 `resolve_birth_place_context`，默认执行时钟读取 `core.execution_context.current_datetime`，Swiss Ephemeris 共享目录状态经 `core.ephemeris_runtime` 协调。

测试从已安装的 `src` 包导入，依赖 `tests/support/` 中的共享夹具与独立参考，不使用当前生产输出重新生成期望值。`tests/quality/test_architecture_boundaries.py` 静态校验模块导入边界与无环约束。严格输出校验测试通过环境变量 `FATEBRIDGE_STRICT_OUTPUT_VALIDATION=1` 触发完整嵌套模型核验。

## 文档维护与验证

### 文档写作

- 文档按读者任务分工：README 介绍定位与安装，快速入门完成首次运行，部署/配置/排错提供操作步骤，API/覆盖矩阵维护准确契约，领域与方法参考说明输入及来源。
- 散文段落使用单行（不在句中换行），保持简洁清晰；并列字段用表格，顺序操作用列表。
- 同一约定只在一个主文档中维护，其余文档通过链接引用；机器调用合同（`docs/contracts/`）从代码自动生成，不得手改。
- 删除页面或标题前先搜索全库引用，确保无断链或失效锚点，且不引入过程日志、临时散列或免责声明。

### 验证命令

修改文档后运行以下检查，确保零断链、计数准确且生成合同无漂移：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py \
  tests/quality/test_doc_tool_counts.py tests/quality/test_interpretation_examples.py \
  tests/quality/test_codex_call_contracts.py
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
git diff --check
```

`scripts/check_docs.py` 校验根目录文档、`docs/`（不含临时评审目录）以及脚本与测试索引中的本地链接、标题锚点、代码围栏、JSON 代码块和示例 JSON 文件。`test_doc_tool_counts.py` 核对核心文档与实时中央目录的工具、路由、family 数量及所有公开路线覆盖。`test_interpretation_examples.py` 提取并实际执行 `docs/interpretation/` 中的 CLI 示例。当工具参数或 `evidence_views` 变化时，先运行 `uv run --locked --extra dev python scripts/build_codex_call_contracts.py` 更新 `docs/contracts/`，再以 `--check` 复核。

## 仓库维护与打包发布

### 清理本地临时产物

```bash
uv run --locked --extra dev python scripts/clean_repository.py
uv run --locked --extra dev python scripts/clean_repository.py --apply
```

默认仅预览可再生成的构建缓存与临时产物，`--apply` 执行清理，不会删除虚拟环境、星历数据或 Git 跟踪文件。

### 构建与发布

版本唯一来源为 `src/fatebridge/__init__.py::__version__`。从干净工作区构建分发包前确认规则数据、随包星历、许可证与 `py.typed` 均已包含在 wheel 中：

```bash
uv build
uvx --from twine twine check dist/*
```

CI 在 push 与 PR 中运行多平台（Linux Python 3.10–3.13 与 Windows Python 3.12）自包含分片测试、静态检查（Black / isort / Mypy / 生成合同）及文档完整性检查；版本递增并推送到主分支且 CI 通过后，由发布工作流通过 PyPI Trusted Publishing 上传并创建 `v<version>` GitHub Release。若仅 GitHub Release 同步失败，可使用 `scripts/sync_github_release.py` 补建对应版本的发布页。
