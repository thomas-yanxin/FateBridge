# FateBridge 快速入门

本页带你在 5 分钟内安装 FateBridge、完成首次本地计算，并启动 REST 或验证 MCP 入口。首次体验只需完成[安装](#安装)与本地 CLI 计算，无需常驻服务。文中人物与出生资料均为虚构示例；对话模型和界面由接入应用提供。

| 你的目标 | 最短路径 |
| --- | --- |
| 终端完成第一次计算 | [安装](#安装) → [完成首次 CLI 计算](#完成首次-cli-计算) |
| 应用接入 HTTP REST 服务 | [安装](#安装) → [启动 REST 并检查状态](#启动-rest-并检查状态) → [发送第一条 REST 请求](#发送第一条-rest-请求) |
| 接入 Codex / Claude Desktop / Cursor | [安装](#安装) → [验证 MCP 入口](#验证-mcp-入口) → [MCP 部署指南](mcp-deployment.md) |

三端共用规范工具名（`spec.name`）与业务请求字段，详细契约见 [API 参考](api-reference.md)，字段投影与错误恢复见[开发者 / Agent 接入指南](agent-guide.md)。

## 安装

需要 [uv](https://docs.astral.sh/uv/getting-started/installation/) 与 Python 3.10+（CI 覆盖 3.10–3.13，源码默认 Python 3.12）。选择一种安装方式：

**方式 A：安装已发布版本**（提供全局命令 `fatebridge`、`fatebridge-api` 与 `fatebridge-mcp`）：

```bash
uv tool install --python 3.12 fatebridge
fatebridge doctor
```

若终端提示找不到命令，运行 `uv tool update-shell` 并重开终端；需要特定版本时安装 `fatebridge==<version>` 并查阅对应 [Git 标签](https://github.com/thomas-yanxin/FateBridge/tags)文档。

**方式 B：使用当前源码**（适合开发或使用未发布特性）：

```bash
git clone https://github.com/thomas-yanxin/FateBridge.git
cd FateBridge
uv sync --extra dev
uv run --extra dev fatebridge doctor
```

源码环境在下方命令的 `fatebridge`、`fatebridge-api` 或 `fatebridge-mcp` 前加 `uv run --extra dev` 即可，无需手动激活虚拟环境。Windows PowerShell 写法见 [MCP 部署指南](mcp-deployment.md#windows-powershell)，未发布改动见 [CHANGELOG](../CHANGELOG.md#unreleased)。

## 完成首次 CLI 计算

CLI 不自动读取 `.env`，也无需启动后台服务。运行以下虚构八字计算：

```bash
fatebridge bazi_birth_chart \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-place 北京 --birth-timezone Asia/Shanghai \
  --fields bazi_birth.day_master.stem bazi_birth.day_master.element \
    bazi_birth.day_master.polarity
```

退出码为 `0` 即成功，输出包含日主（`庚 / 金 / 阳`）与 `run_metadata`。三端默认返回核心层（被省略的可选重型路径记入 `run_metadata.omitted_fields`）；需要无损完整结果与方法依据时传 `--include "*"`（或按需传路径/`evidence_views` 名称，且不与 `--fields` 并用）。发现其他工具和请求定义：

```bash
fatebridge list
fatebridge discover --family bazi
fatebridge discover bazi_birth_chart
```

## 启动 REST 并检查状态

默认 `API_HOST=0.0.0.0` 会监听所有网卡；仅本机调用时显式绑定回环地址（需调整端口、鉴权或 CORS 见[运行配置](configuration.md)）：

```bash
API_HOST=127.0.0.1 fatebridge-api
```

在另一个终端检查健康与就绪端点（`/docs` 与 `/redoc` 提供交互式文档，`/openapi.json` 提供完整 Schema）：

```bash
curl http://localhost:8010/health
curl http://localhost:8010/ready
curl http://localhost:8010/metrics
```

`/health` 返回 `{"status":"healthy"}`，`/ready` 返回服务就绪状态与可选西占运行时检查结果（字段详情见[健康检查与能力发现](api-reference.md#410-健康检查与能力发现)）。

### 发送第一条 REST 请求

保持 REST 服务运行，调用独立八字命盘（开启 `FATEBRIDGE_API_KEYS` 时附加 `-H "X-API-Key: <secret>"`）：

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

再试一条西占核心本命盘请求（默认使用民用时刻 `use_true_solar_time=false`，建议显式提供经纬度与时区）：

```bash
curl -X POST http://localhost:8010/api/astrology/chart \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Chart Demo",
    "birth_year": 1990, "birth_month": 4, "birth_day": 6,
    "birth_hour": 9, "birth_minute": 33,
    "birth_timezone": "Asia/Shanghai",
    "birth_longitude": 121.4667, "birth_latitude": 31.2167, "birth_place": "上海"
  }'
```

更多请求族字段约定、输出控制与错误处理见[接入指南](agent-guide.md)与 [API 参考](api-reference.md)。

## 验证 MCP 入口

MCP 默认通过 stdio 由 AI 客户端拉起子进程，暴露 `discover_tools`、`run_calculation` 与 `run_batch` 三个工具（0 个 MCP 资源）。在客户端注册前，先验证独立 stdio 探测：

```bash
fatebridge doctor --mcp
```

确认输出 `ok=true` 且 `mcp.ok=true`，随后按返回的 `executable` 绝对路径在 Codex、Claude Desktop 或 Cursor 中配置即可，完整配置与远程 HTTP 模式见 [MCP 部署指南](mcp-deployment.md)。

## 星历数据与精度

首次 CLI 与基础八字示例无需下载外部星历。占星与历法调用前须留意：`swisseph` Python 库可导入不代表已加载 `.se1` 数据文件；缺少外部数据时核心星盘可能使用内置 Moshier 模型或离线近似轨道，而显式复杂宫制与西占推运则会返回 `dependency_missing`。如需安装或校验外部星历（Swiss `.se1`、DE441、VSOP2013 等），按[星历数据安装与运行模型](ephemeris.md)配置路径并重启服务，再核对返回中的 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`。

## 下一步

- 接入应用、工具发现、严格 `fields` 投影与错误恢复：[开发者 / Agent 接入指南](agent-guide.md)
- 按业务场景运行风水、六爻与星盘示例：[可运行请求示例](examples/README.md) · [家居风水参考](fengshui.md)
- 查看全部 91 项能力清单与问题排查：[算法覆盖矩阵](algorithm-coverage.md) · [故障排除](troubleshooting.md)
