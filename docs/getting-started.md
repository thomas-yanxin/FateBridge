# FateBridge 快速入门

想知道 FateBridge 能做什么，先看一次实际返回。安装后，用虚构资料运行一条本地计算，查看数据与运行回执，再决定如何接入应用或 AI 助手。

领域计算在本地完成；自然语言对话由你选择的客户端与模型提供。

第一次体验只需完成[安装](#安装)和 [CLI 调用](#选择运行方式)，无需启动服务。要接入应用或助手，可以按目标选择下面的路径。本文中的人物资料均为虚构示例。

| 你的目标 | 从这里开始 |
| --- | --- |
| 在终端得到第一个结果 | [安装](#安装) → [选择运行方式](#选择运行方式) |
| 在应用中调用 HTTP 接口 | [启动 REST](#启动-rest-并检查状态) → [第一条八字请求](#第一条八字请求) |
| 在 Codex 中用自然语言咨询 | 安装后转到 [Codex 使用指南](codex-guide.md) |
| 部署本地或远程 MCP、接入其他 host | [MCP 部署指南](mcp-deployment.md) |

字段含义见 [API 参考](api-reference.md)，工具与场景等概念见 [核心概念](concepts.md)。

## 安装

先确定需要哪个版本：下方 PyPI 命令安装最新已发布版本，可用 `fatebridge doctor` 确认实际版本；需要当前开发分支的场景、技能与接口范围时，选择源码安装。版本差异见 [CHANGELOG](../CHANGELOG.md#unreleased)，已发布版本的使用说明以对应 Git 标签为准。

包管理统一使用 [uv](https://docs.astral.sh/uv/getting-started/installation/)。需要 Python 3.10+；当前 CI 覆盖 3.10–3.13，源码环境默认使用 `.python-version` 中的 Python 3.12。依赖与三个控制台入口由 `pyproject.toml` 声明。从 PyPI 安装独立命令工具：

```bash
uv tool install --python 3.12 fatebridge
```

该命令会在独立工具环境中提供 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp`；命令找不到时运行 `uv tool update-shell` 并重开终端。需要将包安装到已有虚拟环境时使用 `uv pip install fatebridge`，需要复现特定发布版时加 `==<version>`。需要修改源码时使用 Git 安装；当前 `src/` 布局不能仅靠切到仓库根目录导入包：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
```

`uv sync --locked --extra dev` 按锁文件创建 `.venv`，以 editable 方式安装源码及开发依赖。后续源码命令使用 `uv run --locked --extra dev`，无需激活环境：

```bash
uv run --locked --extra dev python -c "import fatebridge; print(fatebridge.__version__, fatebridge.__file__)"
uv run --locked --extra dev fatebridge list
uv run --locked --extra dev fatebridge describe bazi_birth --detail input
```

独立工具安装可直接使用 `fatebridge`、`fatebridge-api` 与 `fatebridge-mcp`，不会把该包加入系统 Python 环境。下文 `python -m ...` 形式须使用已安装 FateBridge 的虚拟环境解释器；独立工具用户下载星历时使用[星历数据与精度](#星历数据与精度)中的专用命令。

下文 CLI 简写面向独立工具安装。源码用户统一加 `uv run --locked --extra dev`；Windows PowerShell 多行命令与 MCP 路径见[部署指南](mcp-deployment.md#windows-powershell)。开发工作流见[开发指南](development-guide.md)。

安装入口为 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp`。`pyswisseph` / `kerykeion` 都是常规依赖；FateBridge 的规则、知识与场景 JSON 随包安装，外部星历文件不随 FateBridge wheel 分发，见下文。

当前源码构建另附无损裁取的DE440太阳轨道系数，供默认交节计算使用，不需要可选`jpl`依赖或外部SPK文件。[默认交节审计](solar-backends.md)列出数据体积、实际模型、适用范围和完整有限验收；已安装环境仍以自己的实际模型回执为准。

## 选择运行方式

| 方式 | 是否要常驻进程 | 下一步 |
| --- | --- | --- |
| CLI | 否，命令执行后退出 | 直接运行下面的虚构示例 |
| REST | 是，由你启动 HTTP 服务 | [配置](#配置环境变量)后[启动 REST](#启动-rest-并检查状态) |
| MCP | 是，由 host 启动 stdio 子进程 | [MCP 与 CLI](#mcp-与-cli)；Codex 用户看[注册步骤](codex-guide.md#2-注册到-codex) |

想先验证安装，直接运行 CLI 即可，无需启动 REST：

```bash
fatebridge bazi_birth --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京 \
  --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity --strict-fields --no-include-snapshot-text \
  --response-char-limit 8192
```

执行成功时，退出码为 `0`，返回 JSON 包含 `bazi_birth.day_master` 的 `stem/element/polarity` 和 `run_metadata`。较大的运行证据通过 `result_delivery` 延后交付，按[同次结果读取](agent-guide.md#完整结果交付与同次导出)展开。这表明当前安装完成了这一次八字计算；`run_metadata` 记录本次运行，字段含义见 [核心概念](concepts.md)。

CLI 不自动读取 `.env`，不需要配置 REST 密钥；如果已有进程环境配置，仍会按实际设置运行。

## 配置环境变量

如果只是第一次用 CLI，可跳过本节。准备启动 REST、配置 MCP 工具范围或使用自定义星历目录时，再设置相应变量。

源码安装时可选复制模板；已有 `.env` 时直接编辑，避免覆盖：

```bash
cp -n .env.example .env
```

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `API_HOST` | `0.0.0.0` | REST 监听地址；仅本机使用时改成 `127.0.0.1` |
| `API_PORT` | `8010` | REST 端口 |
| `ALLOWED_ORIGINS` | `http://localhost:3000` | 逗号分隔的浏览器 CORS 来源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `FATEBRIDGE_API_KEYS` | 空 | REST API Key；为空关闭鉴权 |
| `API_KEY_HEADER_NAME` | `X-API-Key` | 密钥请求头名称 |
| `FATEBRIDGE_MCP_FAMILIES` | 空 | MCP 公开的工具分类，逗号分隔；空时保留全部工具，分类拼错阻止启动；不影响 REST / CLI |
| `FATEBRIDGE_MCP_SCENARIOS` | 空 | MCP 场景 ID，逗号分隔；与 family 配置取交集，空时不限制，拼错阻止启动 |
| `FATEBRIDGE_MCP_TOOL_SCOPE` | `complete` | 当前源码支持；`complete` 包含场景条件依赖，`topic` 仅保留直接工具与知识支撑且必须指定场景；见[MCP 范围](mcp-deployment.md#工具范围环境与技能) |
| `SE_EPHE_PATH` | 未设置 | 自定义本地星历目录，不在模板内 |
| `FATEBRIDGE_SOLAR_TERM_MODEL` | `auto` | 当前源码在 1700–2300 年默认使用随包 DE440；严格原生 JPL 配置优先。各模式、年份和相邻边界见[太阳后端](solar-backends.md) |
| `FATEBRIDGE_SOLAR_SPK_FILE` | 未设置 | 仅显式`spk`模式使用的外部文件，需可选`jpl`依赖；默认随包系数不读取该文件 |
| `FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY` | `min(4, max(1, CPU 数))` | 单 REST 进程的重计算并发上限，至少为 1；不是请求速率限制 |

API 和 MCP 启动时会读取源码安装目录根部的 `.env`，已经存在的进程环境变量优先。文件解析仅支持简单 `KEY=value`、包裹引号和整行注释，不执行 shell 展开。CLI 不自动加载 `.env`，需要时在启动前设置进程环境变量。wheel 安装不应依赖当前工作目录 `.env` 的自动发现，请由启动器注入环境。

REST 鉴权示例：`FATEBRIDGE_API_KEYS=agent:replace-me`，请求发送 `X-API-Key: replace-me`，不是 `agent:replace-me`。也支持逗号分隔多项与单独 secret；非空配置的空条目、缺少名称/密钥或重复名称会阻止启动。修改环境后重启进程。

免鉴权路径：`/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json`；`OPTIONS` 免检。`/api/tools` 和业务路由均需密钥。鉴权仅适用于 REST，默认 stdio MCP 与 CLI 不使用 API Key。

## 启动 REST 并检查状态

仅本机使用的启动命令（Windows 可在 `.env` 中设置监听地址）：

```bash
API_HOST=127.0.0.1 fatebridge-api
# 同一个入口也可用 python -m fatebridge.api
```

在另一个终端验证：

```bash
curl http://localhost:8010/health
curl http://localhost:8010/ready
curl http://localhost:8010/metrics
```

`/health` 返回 `{"status":"healthy"}`，仅表示服务存活。`/ready` 的必需检查决定状态，可选西占依赖缺失时仍可能返回 `ready`；要确认 `checks.western_predictive_runtime`，不能把就绪当作所有算法/星历已验证。`/metrics` 返回 Prometheus 文本，统计当前进程的请求计数、耗时和配置状态。

浏览器访问 `/docs` 或 `/redoc` 查看交互文档，`/openapi.json` 提供完整请求 Schema。默认 `0.0.0.0` 会监听所有网卡，部署边界见 [安全策略](../SECURITY.md)。

## 第一条八字请求

保持 REST 进程运行，在另一个终端执行。推荐使用独立八字命盘入口：

```bash
curl -X POST http://localhost:8010/api/cn/bazi/birth \
  -H "Content-Type: application/json" \
  -d '{
    "name": "张三", "gender": "男",
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai", "birth_place": "北京",
    "use_true_solar_time": true
  }'
```

开启鉴权时加 `-H "X-API-Key: replace-me"`。响应业务字段在 `bazi_birth`，包含 `four_pillars`、`day_master` 等；此外还有 `person_info`、`snapshot_text`、`snapshot_export` 和 `run_metadata`。

旧版 `/api/calculate` 已移除。独立命盘使用 `/api/cn/bazi/birth`，综合命理 `analyze_destiny` 使用 MCP / CLI。详情见 [三端能力边界](api-reference.md#24-三端能力边界)。

中式出生信息默认开启真太阳时，显式 true 时必须提供可解析地点或经度；没有经度且只使用模型默认值时，按钟表时间计算并附提示。小时必填。固定时区、经度和分析日期有助于复现。

八字与七个时运入口可另传已知 `birth_second`（整数0—59，同时显式给出分钟）。未知秒数省略或传null；输入回执区分未知分量与兼容00值，不推定实际出生范围，见[出生时间分量](bazi-timing.md)。

## 第一条星盘请求

```bash
curl -X POST http://localhost:8010/api/astro/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167,
    "birth_place": "上海"
  }'
```

核心星盘默认使用民用时刻（真太阳时 false）。经纬度与时区建议显式传入。开启 REST 鉴权时同样加密钥请求头。

## 星历数据与精度

首次 CLI 示例无需下载星历。占星与历法结果仍须核对实际使用的模型：Python 库可导入，不代表读取了 Swiss `.se1` 文件；Moshier、JPL、随包 DE440 和近似轨道各有适用范围。

需要外部数据时，按[星历安装指南](ephemeris.md)选择 Swiss 分段或严格 JPL，并在服务启动前设置实际数据路径。下载后重启进程，核对 `chart_profile.ephemeris_model`、来源回执及 `run_metadata.engine_is_approximate`。太阳交节模型另见[太阳后端](solar-backends.md)。

## MCP 与 CLI

默认 MCP 使用 stdio，由 host 启动子进程，不会自动提供 HTTP 地址：

```bash
fatebridge-mcp
# 等价于 python -m fatebridge.mcp_server
```

host 应使用已安装 FateBridge 的虚拟环境解释器绝对路径，可从 `fatebridge doctor --mcp` 的 `executable` 取得。可复制的 Codex / Claude Desktop / Cursor 配置、Windows 路径、HTTP 运行、远程接入与升级步骤见 [MCP 部署指南](mcp-deployment.md)。HTTP 模式由 FastMCP runner 加载应用，REST 端口不是 MCP 地址。

MCP 默认响应预算为 8192 字符，超限时返回 `result_delivery`；需要全文时读取同一次结果。完整 JSON 首次调用不做字段筛选，文件导出方法见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。三端投影、错误和快照规则查 [API 参考](api-reference.md)。出错时查看 [故障排除](troubleshooting.md)。

## 下一步

- 为应用接入错误处理、字段投影和完整结果读取：[开发者与 Agent 接入指南](agent-guide.md)。
- 按自己的问题选择工具与示例：[场景路由](scenario-routing.md)和[示例索引](examples/README.md)。
- 确认算法、星历及传统规则的适用范围：[算法覆盖](algorithm-coverage.md)。
