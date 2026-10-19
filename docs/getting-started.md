# FateBridge 快速入门

本页负责安装、运行配置和首次调用。所有人物请求均为虚构示例。工具字段与各端差异查 [API 参考](api-reference.md)，精度边界查 [算法覆盖](algorithm-coverage.md)。

## 安装

需要 Python 3.10+；当前 CI 覆盖 3.10–3.13，建议首次使用 Python 3.12。依赖与三个控制台入口由 `pyproject.toml` 声明，先安装再运行：

```bash
python -m pip install fatebridge==0.1.0
```

需要修改源码时再使用 Git 安装；当前 `src/` 布局不能仅靠切到仓库根目录导入包：

```bash
git clone https://github.com/Yonder-Lab/FateBridge.git
cd FateBridge
uv venv --python 3.12
source .venv/bin/activate
uv pip install -e .
```

未安装 uv 时，使用可用的 Python 3.12：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
```

以上是 macOS / Linux 命令。Windows PowerShell 用 `py -3.12 -m venv .venv` 创建环境，再用 `.\.venv\Scripts\Activate.ps1` 激活。

开发者安装 `.[dev]`，见 [开发指南](development-guide.md)。确认当前解释器加载的是预期包：

```bash
python -c "import fatebridge; print(fatebridge.__version__, fatebridge.__file__)"
fatebridge list
fatebridge describe bazi_birth
```

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

结果包含所选的 `bazi_birth.day_master` 与 `run_metadata`。CLI 不自动读取 `.env`，不需要配置 REST 密钥；如果已有进程环境配置，仍会按实际设置运行。

## 配置环境变量

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

推荐使用独立八字命盘入口：

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

源码安装可选择下载默认星历段（此步骤需要网络）：

```bash
python -m fatebridge.fetch_ephe
```

默认下载 `sepl_18.se1`、`semo_18.se1`、`seas_18.se1` 到源码仓库 `ephe/`；所需年代/天体的数据可能不同。wheel 安装或自定义路径应明确指定可写目录，并在各服务启动前设置同一路径：

```bash
python -m fatebridge.fetch_ephe --dest /absolute/path/to/ephe
export SE_EPHE_PATH=/absolute/path/to/ephe
```

重启服务后检查核心盘的 `chart_profile.ephemeris_model`（如 `swieph`、`jpl`、`moshier`、`mixed`），以及 `run_metadata.engine_is_approximate`。`engine_backend` / `engine_precision` 不能单独证明加载了数据文件。数据路径、版本和算法限制见 [算法覆盖矩阵](algorithm-coverage.md)。

## MCP 与 CLI

默认 MCP 使用 stdio，由 host 启动子进程，不会自动提供 HTTP 地址：

```bash
fatebridge-mcp
# 等价于 python -m fatebridge.mcp_server
```

host 应使用已安装 FateBridge 的虚拟环境解释器绝对路径。配置结构见 [接入指南](agent-guide.md#fastmcpagent-host)。

MCP 默认响应预算为 8192 字符，超限时返回 `result_delivery`；需要全文时读取同一次结果。完整 JSON 首次调用不做字段筛选，文件导出方法见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。三端投影、错误和快照规则查 [API 参考](api-reference.md)。出错时查看 [故障排除](troubleshooting.md)。
