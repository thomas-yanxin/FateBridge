# FateBridge 快速入门

本页带你安装 FateBridge、完成第一条计算，并按需要接入 REST 或 MCP。首次体验可只完成[安装](#安装)和[CLI 调用](#选择运行方式)，无需配置服务。所有人物资料均为虚构示例。

| 你的目标 | 从这里开始 |
| --- | --- |
| 在终端得到第一个结果 | [安装](#安装) → [选择运行方式](#选择运行方式) |
| 在应用中调用 HTTP 接口 | [启动 REST](#启动-rest-并检查状态) → [第一条八字请求](#第一条八字请求) |
| 在 Codex 中用自然语言咨询 | 安装后转到 [Codex 使用指南](codex-guide.md) |
| 接入其他 MCP host | [MCP 与 CLI](#mcp-与-cli) |

字段含义见 [API 参考](api-reference.md)，工具与场景等概念见 [核心概念](concepts.md)。

## 安装

包管理统一使用 [uv](https://docs.astral.sh/uv/getting-started/installation/)。需要 Python 3.10+；当前 CI 覆盖 3.10–3.13，源码环境默认使用 `.python-version` 中的 Python 3.12。依赖与三个控制台入口由 `pyproject.toml` 声明。从 PyPI 安装独立命令工具：

```bash
uv tool install fatebridge==0.1.0
```

该命令会在独立工具环境中提供 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp`。需要将包安装到已有虚拟环境时使用 `uv pip install fatebridge==0.1.0`。需要修改源码时使用 Git 安装；当前 `src/` 布局不能仅靠切到仓库根目录导入包：

```bash
git clone https://github.com/Yonder-Lab/FateBridge.git
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

源码用户可在简写命令前加 `uv run --locked --extra dev`，或先激活环境。macOS / Linux 使用 `source .venv/bin/activate`，Windows PowerShell 使用 `.\.venv\Scripts\Activate.ps1`。开发工作流见 [开发指南](development-guide.md)。

安装入口为 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp`。`pyswisseph` / `kerykeion` 都是常规依赖；FateBridge 的规则、知识与场景 JSON 随包安装，外部星历文件不随 FateBridge wheel 分发，见下文。

## 选择运行方式

| 方式 | 是否要常驻进程 | 下一步 |
| --- | --- | --- |
| CLI | 否，命令执行后退出 | 直接运行下面的虚构示例 |
| REST | 是，由你启动 HTTP 服务 | [配置](#配置环境变量)后[启动 REST](#启动-rest-并检查状态) |
| MCP | 是，由 host 启动 stdio 子进程 | [MCP 与 CLI](#mcp-与-cli)；Codex 用户看[注册步骤](codex-guide.md#2-注册到-codex) |

CLI 可直接调用，不需要启动 REST：

```bash
fatebridge bazi_birth --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京 \
  --birth-timezone Asia/Shanghai --fields bazi_birth.day_master --strict-fields
```

执行成功时退出码为 `0`，返回 JSON 中包含 `bazi_birth.day_master` 和 `run_metadata`。这说明当前安装能够完成一次八字计算；`run_metadata` 用于记录本次运行，字段含义见 [核心概念](concepts.md)。

CLI 不自动读取 `.env`，不需要配置 REST 密钥；如果已有进程环境配置，仍会按实际设置运行。

## 配置环境变量

CLI 首次体验可跳过本节。启动 REST、配置 MCP 工具范围或使用自定义星历目录时，再设置相应变量。

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
| `SE_EPHE_PATH` | 未设置 | 自定义本地星历目录，不在模板内 |
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

`swisseph` 可导入，只能证明运行时可用。缺少相应 `.se1` 文件时，它可能使用内置 Moshier 模型；没有运行时的核心星盘则使用 FateBridge 轨道近似。显式复杂宫制与西占推运缺 backend 时会报错。

源码安装可在仓库根目录下载默认星历段（此步骤需要网络）：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
```

默认下载 `sepl_18.se1`、`semo_18.se1`、`seas_18.se1` 到源码仓库 `ephe/`；所需年代/天体的数据可能不同。使用已安装包的虚拟环境时，可显式指定可写目录：

```bash
python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe
export SE_EPHE_PATH=/absolute/path/to/ephe
```

通过 `uv tool install` 安装的用户可用独立运行环境下载到同一目录，无需寻找工具环境中的 Python：

```bash
uv run --no-project --with fatebridge==0.1.0 python -m fatebridge.fetch_ephe \
  --dest /absolute/path/to/ephe
```

在各服务启动前设置 `SE_EPHE_PATH` 指向该目录；上面的 `export` 为 macOS / Linux 写法，Windows PowerShell 使用 `$env:SE_EPHE_PATH="C:\path\to\ephe"`。

重启服务后检查核心盘的 `chart_profile.ephemeris_model`（如 `swieph`、`jpl`、`moshier`、`mixed`），以及 `run_metadata.engine_is_approximate`。`engine_backend` / `engine_precision` 不能单独证明加载了数据文件。数据路径、版本和算法限制见 [算法覆盖矩阵](algorithm-coverage.md)。

## MCP 与 CLI

默认 MCP 使用 stdio，由 host 启动子进程，不会自动提供 HTTP 地址：

```bash
fatebridge-mcp
# 等价于 python -m fatebridge.mcp_server
```

host 应使用已安装 FateBridge 的虚拟环境解释器绝对路径。配置结构见 [接入指南](agent-guide.md#fastmcpagent-host)。

MCP 默认响应预算为 8192 字符，超限时返回 `result_delivery`；需要全文时读取同一次结果。完整 JSON 首次调用不做字段筛选，文件导出方法见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。三端投影、错误和快照规则查 [API 参考](api-reference.md)。出错时查看 [故障排除](troubleshooting.md)。

## 下一步

- 为应用接入错误处理、字段投影和完整结果读取：[开发者与 Agent 接入指南](agent-guide.md)。
- 按自己的问题选择工具与示例：[场景路由](scenario-routing.md)和[示例索引](examples/README.md)。
- 确认算法、星历及传统规则的适用范围：[算法覆盖](algorithm-coverage.md)。
