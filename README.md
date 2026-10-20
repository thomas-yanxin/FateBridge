# FateBridge

<p align="center">
  <img src="asserts/fatebridge-banner.png" alt="FateBridge：银色莫比乌斯环与星轨横幅" width="100%">
</p>

<p align="center">
  <strong>面向应用与 AI Agent 的传统术数与占星计算引擎</strong>
</p>

<p align="center">
  简体中文 · <a href="README.en.md">English</a>
</p>

<p align="center">
  <a href="https://pypi.org/project/fatebridge/"><img src="https://img.shields.io/pypi/v/fatebridge.svg" alt="PyPI"></a>
  <a href="pyproject.toml"><img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg" alt="Python"></a>
  <a href="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml"><img src="https://github.com/thomas-yanxin/FateBridge/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue.svg" alt="License"></a>
</p>

<p align="center">
  <a href="#快速开始">快速开始</a> ·
  <a href="#mcp-部署">MCP 部署</a> ·
  <a href="#rest-api">REST API</a> ·
  <a href="docs/README.md">文档中心</a> ·
  <a href="#参与贡献">参与贡献</a>
</p>

FateBridge 是面向开发者与 AI Agent 的本地计算工具包，将八字、紫微、西方占星、中国占术与风水规则整理为结构化接口。同一套领域计算可通过 **MCP、REST API 和 CLI** 调用，返回计算数据、规则范围与运行回执，便于应用集成和结果核对。

计算服务无需 LLM API Key；自然语言对话由你选择的 Agent 客户端与模型提供。项目提供后端和 Onda 咨询技能，前端由接入应用实现。

## 为什么使用 FateBridge

- **统一接入多种方法**：共享请求校验、工具目录、错误格式与计算回执，减少为不同体系单独编写接入代码。
- **让结果可检查**：保留时间、精度、规则来源及未覆盖范围；支持字段投影和同次计算结果的分页读取。
- **在自己的环境运行**：CLI 单次执行，MCP 由客户端启动，REST 可独立部署。安装依赖与下载星历需要网络；本地计算不依赖在线占算服务。
- **按问题组织 Agent 工作**：仓库中的 [Onda 技能](skills/README.md)提供事业、财务、关系、学习等主题的取证与解读流程，区分计算事实、传统解释和现实建议。

## 支持的能力

| 领域 | 主要内容 |
| --- | --- |
| 八字与双人关系 | 四柱命盘、事业与财务等九项专题、双人配合、宿曜相性 |
| 时运与历法 | 大运、流年、流月、流日、流时、节气与农历 |
| 中国术数与占卜 | 紫微、奇门、六壬、太乙、金口诀、梅花、六爻及本地技法 |
| 西方占星 | 本命与流派盘、关系盘、返照、行运、主限与时主等推运 |
| 风水空间 | 八宅、金锁基础砂水、年星、玄空历史宅盘，以及分层的布局与物件审查 |

当前源码提供 **86 个业务 REST 路由**、**87 个 FastMCP 工具**，覆盖 **13 family / 87 工具**。中央目录含 88 条记录，CLI 可执行其中 87 条。各端的名称与公开范围见[三端能力边界](docs/api-reference.md#24-三端能力边界)，逐项实现与限制见[算法覆盖矩阵](docs/algorithm-coverage.md)。

## 快速开始

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/)；包要求 Python 3.10+，当前 CI 覆盖 3.10–3.13。下面显式使用 Python 3.12，uv 可在缺少时下载该解释器。

### 1. 安装

只使用已发布的 CLI、REST 或 MCP，从 PyPI 安装独立工具环境：

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

安装提供 `fatebridge`、`fatebridge-api`、`fatebridge-mcp` 三个命令。若终端找不到命令，运行 `uv tool update-shell` 后重新打开终端。

**需要当前分支功能、Onda 技能或参与开发时，使用源码安装：**

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge doctor
```

源码命令使用 `uv run --locked --extra dev` 前缀；下文无前缀的 `fatebridge` 命令面向独立工具安装。无需同时安装两种版本。本文描述当前开发分支，已发布包以[对应标签的文档](https://github.com/thomas-yanxin/FateBridge/tags)为准，未发布变化见 [CHANGELOG](CHANGELOG.md#unreleased)。**wheel 不包含 Onda 技能目录**，仅连接 MCP 不会自动安装这些技能。

### 2. 完成第一次计算

CLI 无需启动服务。以下使用虚构资料，macOS / Linux 可直接执行；PowerShell 多行命令见[部署指南](docs/mcp-deployment.md#windows-powershell)：

```bash
fatebridge bazi_birth \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem \
    bazi_birth.day_master.element bazi_birth.day_master.polarity \
  --strict-fields --no-include-snapshot-text
```

退出码为 `0` 时，响应包含以下业务数据及 `run_metadata` 回执：

```json
{
  "bazi_birth": {
    "day_master": {"stem": "庚", "element": "金", "polarity": "阳"}
  }
}
```

### 3. 选择接入方式

| 你的目标 | 运行方式 | 下一步 |
| --- | --- | --- |
| 在 Codex、Claude Desktop、Cursor 中使用 | 本地 MCP / stdio，客户端管理进程 | [MCP 部署](#mcp-部署) |
| 为支持 URL 的 MCP 客户端提供服务 | FastMCP / Streamable HTTP，独立进程 | [HTTP MCP](#http-mcp) |
| 为 Web、移动端或自己的后端提供计算 | REST API，独立 HTTP 进程 | [REST API](#rest-api) |
| 批处理、脚本或终端调用 | CLI，运行后退出 | `fatebridge discover --family bazi`、`fatebridge describe bazi_birth --detail input` |

## MCP 部署

### 本地 MCP：由客户端启动 stdio 进程

这是桌面 Agent 的直接接入方式。**无需启动 REST、开放端口或提前运行 `fatebridge-mcp`**。客户端根据配置启动子进程，通过标准输入输出通信；手工运行后等待输入属于正常行为。

先在选定的安装环境验证 MCP：

```bash
# PyPI 工具安装
fatebridge doctor --mcp

# 源码安装：在仓库根目录运行
uv run --locked --extra dev fatebridge doctor --mcp
```

二选一即可。`ok=true` 表示依赖、独立进程初始化、工具发现、资源读取和一条虚构计算通过。记录输出中的 **`executable` 绝对路径**，作为下面配置的 `command`；它指向已安装 FateBridge 的 Python，不依赖桌面客户端的 PATH 或工作目录。

#### Codex

将以下配置合并到 `~/.codex/config.toml`，替换解释器路径；已有 `fatebridge` 条目时编辑原条目：

```toml
[mcp_servers.fatebridge]
command = "/absolute/path/to/python"
args = ["-m", "fatebridge.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 60

[mcp_servers.fatebridge.env]
FATEBRIDGE_MCP_FAMILIES = ""
FATEBRIDGE_MCP_SCENARIOS = ""
PYTHONUTF8 = "1"
```

也可执行 doctor 返回的 `codex.add_command` 自动注册；该命令使用当前安装的绝对路径。桌面版与终端可能有不同 Codex CLI，优先使用 doctor 确认的路径。注册只需选择一种方式；细节见 [Codex 指南](docs/codex-guide.md#2-注册到-codex)与 [Codex 官方配置说明](https://developers.openai.com/codex/mcp)。

#### Claude Desktop / Cursor

将下面的 `fatebridge` 条目合并到客户端的 `mcpServers`，保留已有服务并替换解释器路径：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "/absolute/path/to/python",
      "args": ["-m", "fatebridge.mcp_server"],
      "env": {
        "FATEBRIDGE_MCP_FAMILIES": "",
        "FATEBRIDGE_MCP_SCENARIOS": "",
        "PYTHONUTF8": "1"
      }
    }
  }
}
```

[Claude Desktop](https://modelcontextprotocol.io/docs/develop/connect-local-servers) 的配置文件为 macOS 的 `~/Library/Application Support/Claude/claude_desktop_config.json` 或 Windows 的 `%APPDATA%\Claude\claude_desktop_config.json`。[Cursor](https://cursor.com/docs/context/mcp) 使用项目级 `.cursor/mcp.json` 或用户级 `~/.cursor/mcp.json`；Cursor 的 stdio 条目还应加入 `"type": "stdio"`。

Windows 的解释器示例为 `C:\path\to\FateBridge\.venv\Scripts\python.exe`，JSON 中反斜杠写成 `\\`。完整 PowerShell 与配置示例见 [Windows 部署](docs/mcp-deployment.md#windows-powershell)。

#### 确认客户端可用

保存配置后重新加载 MCP 连接；必要时重启客户端并打开新聊天，检查 FateBridge 工具是否可见，再用虚构资料试调：

> 请使用 FateBridge，计算男、公历 1990 年 5 月 15 日上午 10:30、北京出生的八字，只解释日主的传统含义。

看到实际工具调用并成功返回，才完成客户端接入。配置存在或 doctor 通过均不能替代这一步。

默认公开全部工具。需要减小工具范围时设置 `FATEBRIDGE_MCP_SCENARIOS=onda-shiye`（事业），或 `FATEBRIDGE_MCP_FAMILIES=fengshui`（风水）；两个筛选取交集，空值表示不限制。修改后重启 MCP。场景列表可用 `fatebridge scenarios` 查询。

### HTTP MCP

支持 URL 的客户端可通过 FastMCP 运行同一个 `app`。**以下是源码安装方式**，在仓库根目录启动并保持进程运行：

```bash
uv run --locked --extra dev fastmcp run src/fatebridge/mcp_server.py:app \
  --transport http --host 127.0.0.1 --port 8011 --path /mcp
```

MCP URL 为 `http://127.0.0.1:8011/mcp`。`fatebridge-mcp` 入口本身仍使用 stdio；HTTP 参数属于 [FastMCP runner](https://gofastmcp.com/deployment/running-server)。REST 的 `8010` 端口与 MCP 的 `8011` 端口是两个独立服务。

远程机器可保持监听回环地址，通过 SSH 隧道接入。完整 URL 配置、协议验证和常驻进程示例见 [MCP 部署指南](docs/mcp-deployment.md#http-与远程部署)。**REST 的 `FATEBRIDGE_API_KEYS` 不保护 MCP**；公网服务需要另行配置 TLS、MCP 鉴权与访问限制，当前示例不提供多租户隔离。

### 使用 Onda 咨询技能

MCP 提供计算工具，Onda 提供按问题组织咨询的技能。使用源码仓库作为 Codex 项目时，仓库的 `AGENTS.md` 与 `.agents/skills/` 提供项目指导和技能入口；在新聊天确认发现状态。其他客户端需要按其技能机制加载 `skills/` 中的内容，不会因 MCP 连接自动获得这些文件。详见 [Onda 技能索引](skills/README.md)。

## REST API

安装后启动本机服务。macOS / Linux：

```bash
API_HOST=127.0.0.1 fatebridge-api
# 源码安装：API_HOST=127.0.0.1 uv run --locked --extra dev fatebridge-api
```

Windows PowerShell：

```powershell
$env:API_HOST = "127.0.0.1"
fatebridge-api
```

另开终端检查服务并执行与 CLI 相同的虚构计算：

```bash
curl --fail http://127.0.0.1:8010/health
curl --fail http://127.0.0.1:8010/ready
curl --fail 'http://127.0.0.1:8010/api/cn/bazi/birth?fields=bazi_birth.day_master&strict_fields=true&include_snapshot_text=false' \
  -H 'Content-Type: application/json' \
  -d '{
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30, "gender": "男",
    "birth_place": "北京", "birth_timezone": "Asia/Shanghai"
  }'
```

`/health` 返回 `{"status":"healthy"}`；命盘结果位于 `bazi_birth.day_master`，另附 `run_metadata`。`/ready` 表示必需检查就绪，不等于所有算法或星历均已验证。[Swagger UI](http://127.0.0.1:8010/docs)可查看 Schema 与试调请求。

监听默认值为 `0.0.0.0:8010`，上例显式限制为本机。共享部署前设置 `FATEBRIDGE_API_KEYS=client:replace-with-a-secret`，业务请求发送 `X-API-Key: replace-with-a-secret`，并在网关处理 TLS、访问和请求速率。密钥不提供用户账户或结果所有权隔离；`/health`、`/ready`、`/metrics` 与接口文档等运维路径免鉴权，详见[安全策略](SECURITY.md#scope-notes)。

## 配置、结果与精度

| 设置 | 用途 |
| --- | --- |
| `FATEBRIDGE_MCP_FAMILIES` / `FATEBRIDGE_MCP_SCENARIOS` | 筛选公开的 MCP 工具；不改变 REST / CLI |
| `API_HOST` / `API_PORT` | REST 监听地址与端口 |
| `FATEBRIDGE_API_KEYS` / `API_KEY_HEADER_NAME` | REST 共享密钥；默认关闭鉴权，默认请求头为 `X-API-Key` |
| `ALLOWED_ORIGINS` | REST 浏览器 CORS 来源；不代替鉴权 |
| `SE_EPHE_PATH` | 本地星历文件目录 |
| `LOG_LEVEL` | 日志级别，默认 `INFO` |

源码 API / MCP 会读取仓库根目录 `.env`，进程环境变量优先；CLI 不自动读取 `.env`。独立工具安装请在启动器或客户端 `env` 中显式注入配置。完整变量表与星历下载见[快速入门](docs/getting-started.md#配置环境变量)。

- **输入**：出生接口使用公历；按各工具 Schema 提供小时、时区和地点，不能把未知出生时刻补成零点。中式出生计算默认开启真太阳时，西占核心盘默认使用民用时刻；保留实际解析和精度提示。
- **结果**：先检查 MCP `isError`、REST 状态码或 CLI 退出码，再读取业务字段。`fields` 支持点路径投影，`strict_fields=true` 拒绝无效路径；REST 投影选项放在 query，而非 JSON body。
- **完整导出**：完整 JSON 首次调用设置 `fields=null`。MCP 默认预算为 8192 字符，超限后按 `result_delivery` 读取同一 run；未被首次选中的字段不能事后恢复。详见[同次完整导出](docs/agent-guide.md#完整结果交付与同次导出)。
- **精度与复现**：保留原输入与 `run_metadata`。外部 `.se1` 星历不随 wheel 分发；检查 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`，不能仅凭依赖可导入就认定加载了高精度数据。重现还需匹配实现、数据与环境，见[星历说明](docs/getting-started.md#星历数据与精度)。

## 常见问题

| 现象 | 处理 |
| --- | --- |
| `fatebridge` 找不到 / GUI 启动失败 | 工具安装运行 `uv tool update-shell`；GUI 使用 doctor 的 `executable` 绝对路径 |
| `fatebridge-mcp` 没有输出、一直等待 | stdio 正在等待客户端消息；将其注册到客户端，或使用上面的 HTTP runner |
| MCP 工具缺失或新参数不可见 | 核对 family / scenario 交集、实际包路径，重启连接并打开新聊天 |
| 将 `http://localhost:8010` 填入 MCP 后失败 | 该地址是 REST；stdio 填 `command/args`，HTTP MCP 使用对应的 `/mcp` URL |
| 返回 `partial`、近似或依赖错误 | 按实际 coverage、精度和错误字段核对所需输入、后端与星历 |

更多恢复步骤见[故障排除](docs/troubleshooting.md)，MCP 的升级、停用与部署验证见[部署指南](docs/mcp-deployment.md)。

## 文档导航

| 你想做什么 | 阅读入口 |
| --- | --- |
| 安装、配置、下载星历 | [快速入门](docs/getting-started.md) |
| 部署本地或远程 MCP | [MCP 部署指南](docs/mcp-deployment.md) |
| 在 Codex 中完成咨询 | [Codex 指南](docs/codex-guide.md) · [Onda 技能](skills/README.md) |
| 编写应用与 Agent 集成 | [接入指南](docs/agent-guide.md) · [API 参考](docs/api-reference.md) |
| 查实现范围、方法与精度 | [算法覆盖](docs/algorithm-coverage.md) · [核心概念](docs/concepts.md) |
| 查主题路由、规则与示例 | [场景路由](docs/scenario-routing.md) · [示例索引](docs/examples/README.md) · [规则文档](docs/README.md#理解计算与结果) |
| 开发、迁移或定位问题 | [架构](docs/architecture.md) · [开发指南](docs/development-guide.md) · [迁移指南](docs/migration.md) · [故障排除](docs/troubleshooting.md) |

全部文档见[文档中心](docs/README.md)，版本变化见 [CHANGELOG](CHANGELOG.md)。

## 参与贡献

欢迎算法修正、接口改进、测试、文档和技能贡献。使用上面的源码安装流程后，纯文档改动运行：

```bash
uv run --locked --extra dev python scripts/check_docs.py
uv run --locked --extra dev python -m pytest -q \
  tests/test_doc_tool_counts.py tests/test_scenario_routing_coverage.py
```

代码改动按影响范围运行领域测试及 CI 检查；依赖变更使用 `uv add` / `uv remove`，同时提交 `pyproject.toml` 与 `uv.lock`。开发与 PR 流程见[贡献指南](CONTRIBUTING.md)。通过 [Issues](https://github.com/thomas-yanxin/FateBridge/issues)报告问题时，附版本、系统、最小虚构输入与实际错误；安全问题按 [SECURITY.md](SECURITY.md)私下报告。

## 使用范围与许可

传统解释与分数用于文化参考，分数不代表现实成功概率。计算测试验证历法、数值和所选规则的一致性，不证明预测有效性。咨询不提供生死寿命、灾祸断言、临床诊断治疗与医疗择时，详见[咨询硬边界](skills/_shared/safety-boundaries.md)。

本地运行仍需考虑 Agent 客户端、模型服务、聊天记录与导出文件对资料的处理；真实出生资料不应提交到公开 Issue 或仓库。

项目代码采用 [Apache-2.0](LICENSE)，第三方组件与来源见 [NOTICE](NOTICE)。依赖与星历数据遵循各自许可，分发或商用集成时需分别核对。

[返回顶部 ↑](#fatebridge)
