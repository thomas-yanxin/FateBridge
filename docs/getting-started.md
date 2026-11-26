# FateBridge 快速入门

本页带你安装 FateBridge、完成一次本地计算，并选择 REST 或 MCP 接入。首次体验只需完成[安装](#安装)与 [CLI 调用](#选择运行方式)，无需启动服务。人物资料均为虚构示例；自然语言对话由接入客户端和模型提供。

| 你的目标 | 从这里开始 |
| --- | --- |
| 在终端得到第一个结果 | [安装](#安装) → [选择运行方式](#选择运行方式) |
| 在应用中调用 HTTP 接口 | [启动 REST](#启动-rest-并检查状态) → [第一条八字请求](#第一条八字请求) |
| 部署本地或远程 MCP、接入 AI 客户端 | [MCP 部署指南](mcp-deployment.md) |

字段含义见 [API 参考](api-reference.md)，工具与分类等概念见 [核心概念](concepts.md)。

## 安装

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 和 Python 3.10+。当前 CI 覆盖 Python 3.10–3.13，源码默认 Python 3.12。选择一种安装方式。

**使用已发布版本**：从 PyPI 安装到独立工具环境。

```bash
uv tool install --python 3.12 fatebridge
```

安装后提供 `fatebridge`、`fatebridge-api` 和 `fatebridge-mcp`。命令找不到时运行 `uv tool update-shell` 并重开终端；用 `fatebridge doctor` 确认版本。特定版本可用 `fatebridge==<version>` 安装，使用说明查阅[对应 Git 标签](https://github.com/thomas-yanxin/FateBridge/tags)。

**使用当前源码**：适合开发或使用尚未发布的功能。

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --locked --extra dev
```

同步后在 `.venv` 中安装源码与开发依赖。下文命令使用独立工具写法；源码用户在命令前加 `uv run --locked --extra dev`，无需激活环境。例如 `uv run --locked --extra dev fatebridge doctor`。未发布差异见 [CHANGELOG](../CHANGELOG.md#unreleased)，开发流程见[开发指南](development-guide.md)，Windows 写法见[部署指南](mcp-deployment.md#windows-powershell)。

## 选择运行方式

| 方式 | 是否要常驻进程 | 下一步 |
| --- | --- | --- |
| CLI | 否，命令执行后退出 | 直接运行下面的虚构示例 |
| REST | 是，由你启动 HTTP 服务 | [配置环境变量](#配置环境变量)后[启动 REST](#启动-rest-并检查状态) |
| MCP | 是，由 host 启动 stdio 子进程 | [MCP 与 CLI](#mcp-与-cli) |

想先验证安装，直接运行 CLI 即可，无需启动 REST：

```bash
fatebridge bazi_birth_chart --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京 \
  --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity
```

执行成功时，退出码为 `0`，`bazi_birth.day_master` 返回 `stem=庚`、`element=金`、`polarity=阳`，并附 `run_metadata`。三端默认采用 `--detail compact` 返回核心业务字段，需要完整输出与方法依据时传 `--detail audit`（详细约定见[输出控制与结果读取](agent-guide.md#输出控制与结果读取)）。查看其他工具和输入格式：

```bash
fatebridge list
fatebridge discover bazi_birth_chart
```

CLI 不自动读取 `.env`，不需要配置 REST 密钥；如果已有进程环境配置，仍会按实际设置运行。

## 配置环境变量

首次 CLI 计算无需配置。REST 本机运行可直接使用下一节命令；需要密钥、自定义端口、MCP 工具筛选或星历目录时，查[运行配置](configuration.md)。

## 启动 REST 并检查状态

仅本机使用的启动命令（Windows 可在 `.env` 中设置监听地址）：

```bash
API_HOST=127.0.0.1 fatebridge-api
```

在另一个终端验证：

```bash
curl http://localhost:8010/health
curl http://localhost:8010/ready
curl http://localhost:8010/metrics
```

`/health` 返回 `{"status":"healthy"}` 表示服务存活。`/ready` 返回各项运行条件；`/metrics` 返回当前进程的 Prometheus 指标。字段说明见[运行状态](api-reference.md#410-健康检查与能力发现)。浏览器访问 `/docs` 或 `/redoc` 查看交互文档，`/openapi.json` 提供完整请求 Schema。默认 `0.0.0.0` 会监听所有网卡，部署边界见[安全策略](../SECURITY.md)。

## 第一条八字请求

保持 REST 进程运行，在另一个终端执行。推荐使用独立八字命盘入口：

```bash
curl -X POST http://localhost:8010/api/bazi/birth-chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "张三", "gender": "男",
    "birth_year": 1990, "birth_month": 5, "birth_day": 15,
    "birth_hour": 10, "birth_minute": 30,
    "birth_timezone": "Asia/Shanghai", "birth_place": "北京",
    "use_true_solar_time": true
  }'
```

开启鉴权时加 `-H "X-API-Key: replace-me"`。默认 `detail=compact` 返回核心业务字段（例如 `bazi_birth` 下的 `four_pillars`、`day_master`）与精简 `run_metadata`；传入 `?detail=audit` 可获得包含 `person_info` 与完整方法证据的完整响应。独立命盘使用 `/api/bazi/birth-chart`，综合命理 `bazi_overview` 的 REST 路由为 `/api/bazi/overview`，详情见[三端能力边界](api-reference.md#22-三端能力边界)。

中式出生信息默认开启真太阳时，显式 true 时必须提供可解析地点或经度；没有经度且只使用默认值时，按钟表时间计算并附提示。小时必填。八字与时运入口可另传已知 `birth_second`（整数 `0..59`，须同时显式给出分钟），未知秒数省略或传 `null`。

## 第一条星盘请求

```bash
curl -X POST http://localhost:8010/api/astrology/chart \
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

首次 CLI 示例无需下载星历。占星与历法结果仍须核对实际使用的模型：Python 库可导入不代表已读取 Swiss `.se1` 文件；Moshier、JPL、随包 DE440 和近似轨道各有适用范围。需要外部数据时，按[星历安装指南](ephemeris.md)配置路径并重启进程，再核对 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`。

## MCP 与 CLI

默认 MCP 使用 stdio，由 host 启动子进程，不会自动提供 HTTP 地址：

```bash
fatebridge-mcp
```

host 应使用已安装 FateBridge 的虚拟环境解释器绝对路径，可从 `fatebridge doctor --mcp` 的 `executable` 取得。Codex / Claude Desktop / Cursor 配置、Windows 路径、HTTP 运行、远程接入与升级步骤见 [MCP 部署指南](mcp-deployment.md)。

MCP 仅公开 `discover_tools` 与 `run_calculation` 两个入口（无资源 URI），与 REST、CLI 共用三项输出控制：`detail`（默认 `compact`，可选 `audit`）、`fields`（始终严格校验的点号路径列表）与 `as_of`（冻结当前时钟）。三端发现、投影与错误恢复规则查 [API 参考](api-reference.md)，出错时查看[故障排除](troubleshooting.md)。

## 下一步

- 为应用接入错误处理、字段投影和完整结果读取：[开发者与 Agent 接入指南](agent-guide.md)。
- 按任务选择工具与示例：[工具覆盖](algorithm-coverage.md)和[示例索引](examples/README.md)。
