# FateBridge

<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge：银色莫比乌斯环与星轨横幅" width="100%">
</p>

<p align="center">
  <strong>为 AI 应用提供可核对的术数与占星计算</strong>
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/fatebridge/"><img src="https://img.shields.io/pypi/v/fatebridge.svg" alt="PyPI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python"></a>
  <a href="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml"><img src="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
  <a href="https://www.modelscope.cn/mcp/servers/thomas/FateBridge"><img src="https://img.shields.io/badge/ModelScope-MCP%20Server-624AFF.svg" alt="ModelScope MCP Server"></a>
</p>

FateBridge 为 AI 应用提供本地术数、占星与心理测量计算，通过 **MCP、REST API 和 CLI** 返回结构化结果、时间口径与运行回执。对话模型和界面由接入应用提供；[方法参考](docs/interpretation/README.md)说明结果读取、来源与适用范围。计算服务无需 LLM API Key。

## 支持的能力

| 领域 | 当前计算范围 | 参考与详情 |
| --- | --- | --- |
| 八字与关系 | 四柱、九项专题、双人干支与十神关系、大运至流时 | [算法覆盖](docs/algorithm-coverage.md) · [方法参考](docs/interpretation/README.md) |
| 中国术数与易占 | 紫微、奇门、六壬、金口诀、太乙、梅花、六爻、河洛与参评 | [紫微斗数](docs/ziwei.md) · [算法覆盖](docs/algorithm-coverage.md) |
| 占星 | 西占本命、关系盘、推运与事件盘；印度占星、果老、宿曜与其他流派 | [宿曜](docs/sukuyo.md) · [占星骰](docs/astrodice.md) · [算法覆盖](docs/algorithm-coverage.md) |
| 人类图 | 太阳 88° 双时刻、门线、通道、类型与权威 | [人类图参考](docs/human-design.md) |
| 风水空间 | 八宅、基础砂水、年／月星、玄空历史宅盘、布局与实测工位 | [家居风水](docs/fengshui.md) · [现场咨询指南](docs/interpretation/fengshui/consultation.md) |
| 心理测量 | IPIP 50 题大五人格因子标记量表（Goldberg 1992 公有领域） | [覆盖矩阵](docs/algorithm-coverage.md#212-psychometrics--心理测量量表implemented) |

当前源码提供 **91 个业务 REST 路由**。MCP 通过两个入口提供 **91 项业务能力**，覆盖 **12 个 family**。目录共有 91 条记录，CLI 可执行 91 条。三端共用公开工具名、请求字段与领域计算，见[接口边界](docs/api-reference.md#22-三端能力边界)和[算法覆盖矩阵](docs/algorithm-coverage.md)。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Python 3.10+；源码默认 Python 3.12，CI 测试 3.10–3.13。选择一种安装方式。

### 已发布版本

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

安装提供 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp` 三个命令。找不到命令时运行 `uv tool update-shell` 并重开终端。

### 当前源码

需要当前分支功能或参与开发时：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

本文对应当前开发分支。已发布包查阅[对应标签](https://github.com/thomas-yanxin/FateBridge/tags)的文档，未发布变化见 [CHANGELOG](CHANGELOG.md#unreleased)。Python wheel 包含计算代码和规则数据，方法范围与结果读取见[方法参考](docs/interpretation/README.md)。

### 完成第一次计算

下列命令使用虚构资料，在 macOS / Linux 终端执行，无需启动服务。源码用户在 `fatebridge` 前加 `uv run --locked --extra dev`；[Windows 写法](docs/mcp-deployment.md#windows-powershell)另见部署指南。

```bash
fatebridge bazi_birth_chart \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity
```

成功时退出码为 `0`，返回日主 `庚 / 金 / 阳` 与 `run_metadata`。默认 `--detail compact` 返回核心业务字段；需要完整输出与方法依据时传 `--detail audit`。查询其他工具及其请求格式：

```bash
fatebridge discover --family bazi
fatebridge discover bazi_birth_chart
```

## 接入 AI 助手或应用

| 目标 | 运行与连接 | 指南 |
| --- | --- | --- |
| 本机 Codex、Claude Desktop、Cursor | 客户端启动 MCP stdio 子进程 | [MCP 部署](docs/mcp-deployment.md#注册本地-stdio) |
| 支持 URL 的 MCP 客户端 | 独立 Streamable HTTP 服务 | [HTTP 与远程部署](docs/mcp-deployment.md#http-与远程部署) |
| Web、移动端或后端服务 | 独立 REST 服务 | [启动 REST](docs/getting-started.md#启动-rest-并检查状态) · [Agent 接入](docs/agent-guide.md) |
| 批处理与终端 | CLI 单次执行 | [快速入门](docs/getting-started.md) · [请求示例](docs/examples/README.md) |

本机 MCP 先运行 `fatebridge doctor --mcp`，用返回的 `executable` 绝对路径注册客户端。客户端管理 stdio 进程；配置保存后，在新聊天确认工具可见并试调，升级后需重新加载 MCP 连接。

REST 本机启动命令为 `API_HOST=127.0.0.1 fatebridge-api`。默认端口 `8010`，交互文档在 `/docs`；默认监听所有网卡，密钥配置及网络边界见[运行配置](docs/configuration.md)和[安全策略](SECURITY.md)。REST 密钥不保护 MCP。

## 读取与核对结果

- **输入与时间**：使用已确认资料，明确时区、地点和分析时刻。未知出生小时不能用默认值或示例补齐；不同方法采用的时钟以实际返回为准。
- **摘要与全文**：三端默认使用 `detail=compact` 返回核心业务字段；需要指定子字段时传 `fields`（严格校验路径）；需要完整结果、全部时间线与方法依据时传 `detail=audit`（`fields=null`）。操作步骤见[输出控制与结果读取](docs/agent-guide.md#输出控制与结果读取)。
- **星历与精度**：安装 Python 库不保证读取了外部数据文件。核对实际模型、来源和近似标志；下载与验证见[星历数据](docs/ephemeris.md)。
- **依据与限制**：软件回归、原典对照与运行依赖分别报告；`partial` 只限制对应层。共同术语见[核心概念](docs/concepts.md)。

## 开发与贡献

源码使用 Python `src` 布局。FastAPI、FastMCP 与 CLI 通过中央 `ToolSpec` 目录调用共享执行层和领域服务；分层与数据流见[架构说明](docs/architecture.md)。依赖声明在 [pyproject.toml](pyproject.toml)，开发解析版本由 [uv.lock](uv.lock) 固定。

文档、算法、接口和测试均欢迎贡献。先按[贡献指南](CONTRIBUTING.md)准备改动，再按[开发指南](docs/development-guide.md)选择检查。文档写作要求见[维护指南](docs/development-guide.md#文档写作)。纯文档改动的起始检查：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py tests/quality/test_doc_tool_counts.py
```

接口与生成合同的同步要求见[文档维护与验证](docs/development-guide.md#文档维护与验证)。报告问题请附版本、虚构的最小复现和实际错误；安全问题按 [SECURITY.md](SECURITY.md) 私下报告。

## 文档与许可

[文档中心](docs/README.md)按任务索引安装、接入、专题和开发资料；[故障排除](docs/troubleshooting.md)按现象定位问题。平台入口：[ModelScope MCP Server](https://www.modelscope.cn/mcp/servers/thomas/FateBridge)。咨询硬边界见[安全边界](docs/interpretation/shared/safety-boundaries.md)。

项目代码采用 [Apache-2.0](LICENSE)。第三方组件和资料见 [NOTICE](NOTICE)；依赖、下载的星历与原典资料按各自声明核对许可。
