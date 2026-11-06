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

FateBridge 为 AI 应用提供本地术数与占星计算，通过 **MCP、REST API 和 CLI** 返回结构化结果、时间口径与运行回执。对话模型和界面由接入应用提供；[方法参考](docs/interpretation/README.md)说明结果读取、来源与适用范围。

计算服务无需 LLM API Key。项目适合希望接入计算的应用开发者、使用 MCP 的 AI 助手，以及核对历法与传统规则的研究者。计算可复现、规则有来源和现实预测有效性分别验证。

## 支持的能力

| 领域 | 当前计算范围 | 实现与限制 |
| --- | --- | --- |
| 八字与关系 | 四柱、九项专题、双人规则评分、大运至流时 | [八字判定](docs/bazi-assessment.md) · [时运](docs/bazi-timing.md) · [双人评分](docs/compatibility-scoring.md) |
| 中国术数与易占 | 紫微、奇门、六壬、金口诀、太乙、梅花、六爻、河洛与参评 | [专题索引](docs/README.md#计算原理与专题) |
| 占星 | 西占本命、关系盘、推运与事件盘；印度占星、果老、宿曜与其他流派 | [西占](docs/western-astrology.md) · [印占](docs/jyotish.md) · [覆盖矩阵](docs/algorithm-coverage.md) |
| 人类图 | 太阳 88° 双时刻、门线、通道、类型与权威 | [计算与验收范围](docs/human-design.md) |
| 风水空间 | 八宅、基础砂水、年／月星、玄空历史宅盘、布局与实测工位 | [家居风水](docs/fengshui.md) · [实测工位](docs/fengshui-workstation-layout.md) |

当前源码提供 **91 个业务 REST 路由**、**92 个 FastMCP 工具**，覆盖 **13 family / 92 工具**。中央目录含 93 条记录，CLI 可执行其中 92 条。三端共享领域计算，公开名称与输入形态见[接口边界](docs/api-reference.md#24-三端能力边界)。方法版本、原典分歧与尚未通过的项目见[当前算法状态](docs/algorithm-status.md)。

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

本文对应当前开发分支。已发布包查阅[对应标签](https://github.com/thomas-yanxin/FateBridge/tags)的文档，未发布变化见 [CHANGELOG](CHANGELOG.md#unreleased)。Python wheel 包含计算代码和规则数据。旧 Onda 技能、主题场景配置与插件打包入口已移除。

### 完成第一次计算

下列命令使用虚构资料，在 macOS / Linux 终端执行，无需启动服务。源码用户在 `fatebridge` 前加 `uv run --locked --extra dev`；[Windows 写法](docs/mcp-deployment.md#windows-powershell)另见部署指南。

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity --strict-fields --no-include-snapshot-text \
  --response-char-limit 8192
```

成功时退出码为 `0`，返回日主 `庚 / 金 / 阳` 与 `run_metadata`。较大的运行证据通过 `result_delivery` 延后交付，见下方[结果读取](#读取与核对结果)。这验证当前环境完成了这一次计算。查询其他工具及其请求格式：

```bash
fatebridge discover --family bazi
fatebridge describe bazi_birth --detail input
```

## 接入 AI 助手或应用

| 目标 | 运行与连接 | 指南 |
| --- | --- | --- |
| 本机 Codex、Claude Desktop、Cursor | 客户端启动 MCP stdio 子进程 | [MCP 部署](docs/mcp-deployment.md#注册本地-stdio) · [Codex 首次对话](docs/codex-guide.md) |
| 支持 URL 的 MCP 客户端 | 独立 Streamable HTTP 服务 | [HTTP 与远程部署](docs/mcp-deployment.md#http-与远程部署) |
| Web、移动端或后端服务 | 独立 REST 服务 | [启动 REST](docs/getting-started.md#启动-rest-并检查状态) · [Agent 接入](docs/agent-guide.md) |
| 批处理与终端 | CLI 单次执行 | [快速入门](docs/getting-started.md) · [请求示例](docs/examples/README.md) |

本机 MCP 先运行 `fatebridge doctor --mcp`，用返回的 `executable` 绝对路径注册客户端。客户端管理 stdio 进程；配置保存后，在新聊天确认工具可见并试调。升级后需重新加载 MCP 连接。

REST 本机启动命令为 `API_HOST=127.0.0.1 fatebridge-api`。默认端口 `8010`，交互文档在 `/docs`；默认监听所有网卡，密钥配置及网络边界见[运行配置](docs/configuration.md)和[安全策略](SECURITY.md)。REST 密钥不保护 MCP。

## 读取与核对结果

- **输入与时间**：使用已确认资料，明确时区、地点和分析时刻。未知出生小时不能用默认值或示例补齐；不同方法采用的时钟以实际返回为准。
- **摘要与全文**：摘要使用任务所需 `fields`；完整 JSON 首次保留全部字段，收到 `result_delivery` 后读取同一 run。操作步骤见[完整结果交付](docs/agent-guide.md#完整结果交付与同次导出)。
- **星历与精度**：安装 Python 库不保证读取了外部数据文件。核对实际模型、来源和近似标志；下载与验证见[星历数据](docs/ephemeris.md)，太阳交节另见[后端选择](docs/solar-backends.md)。
- **依据与限制**：软件回归、独立数值、原典对照、模型解释和现实效度分别报告；`partial` 只限制对应层。共同术语见[核心概念](docs/concepts.md)。

## 开发与贡献

源码使用 Python `src` 布局。FastAPI、FastMCP 与 CLI 通过中央 `ToolSpec` 目录调用共享执行层和领域服务；分层与数据流见[架构说明](docs/architecture.md)。依赖声明在 [pyproject.toml](pyproject.toml)，开发解析版本由 [uv.lock](uv.lock) 固定。

文档、算法、接口和测试均欢迎贡献。先按[贡献指南](CONTRIBUTING.md)准备改动，再按[开发指南](docs/development-guide.md)选择检查。文档写作要求见[维护指南](docs/documentation-guide.md)。纯文档改动的起始检查：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q tests/quality/test_documentation_integrity.py tests/quality/test_doc_tool_counts.py
```

接口与生成合同的同步要求见[文档维护与验证](docs/development-guide.md#文档维护与验证)。报告问题请附版本、虚构的最小复现和实际错误；安全问题按 [SECURITY.md](SECURITY.md) 私下报告。

## 文档与使用范围

[文档中心](docs/README.md)按任务索引安装、接入、专题和开发资料；[故障排除](docs/troubleshooting.md)按现象定位问题。平台入口：[ModelScope MCP Server](https://www.modelscope.cn/mcp/servers/thomas/FateBridge)。

传统解释与规则分数用于文化参考，分数不是现实成功概率。咨询排除生死寿命、灾祸断言、临床诊断治疗及医疗择时，详见[咨询边界](docs/interpretation/shared/safety-boundaries.md)。本地计算之外，客户端、模型供应商、聊天记录和导出文件仍各有个人数据处理边界。

项目代码采用 [Apache-2.0](LICENSE)。第三方组件和资料见 [NOTICE](NOTICE)；依赖、下载的星历与原典资料按各自声明核对许可，尤其在再分发或商业接入前。
