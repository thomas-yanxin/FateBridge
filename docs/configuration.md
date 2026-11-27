# 运行配置

[文档中心](README.md) · [快速入门](getting-started.md) · [MCP 部署](mcp-deployment.md) · [星历安装](ephemeris.md)

本页列出 FateBridge 源码中的全部环境变量、`.env` 加载顺序与 REST 鉴权规则。本地直接运行 CLI 示例时无需预先配置 REST 环境变量。

## 环境变量

源码环境可按需复制模板后编辑（已有 `.env` 时不会覆盖）：

```bash
cp -n .env.example .env
```

### 服务与鉴权

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `API_HOST` | `0.0.0.0` | REST 监听地址；仅本机访问建议设为 `127.0.0.1` |
| `API_PORT` | `8010` | REST 服务端口 |
| `ALLOWED_ORIGINS` | 空 | 逗号分隔的浏览器 CORS 允许来源；为空时不开放跨域浏览器请求 |
| `LOG_LEVEL` | `INFO` | 应用日志级别（如 `DEBUG`、`INFO`、`WARNING`、`ERROR`） |
| `FATEBRIDGE_API_KEYS` | 空 | REST API Key 列表（`name:secret,...` 或逗号分隔密文）；为空关闭鉴权，非空但格式非法会阻止启动 |
| `API_KEY_HEADER_NAME` | `X-API-Key` | REST API Key 请求头名称 |

### MCP 接口

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `FATEBRIDGE_MCP_FAMILIES` | 空 | 逗号分隔的 MCP 公开 `family` 列表；为空时公开全量 90 项能力，分类名无效会阻止启动；不影响 REST 与 CLI |

### 星历与太阳交节模型

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `SE_EPHE_PATH` | 未设置 | 自定义 Swiss `.se1` 或 JPL 内核搜索目录；优先级高于代码内置路径，整串须小于 242 编码字节 |
| `FATEBRIDGE_JPL_FILE` | 未设置 | 显式启用的严格 DE441 内核短文件名（如 `linux_m13000p17000.441`），须位于 `SE_EPHE_PATH` 内 |
| `FATEBRIDGE_DE441_DIR` | 未设置 | 可选 DE441 连续行星系数分片目录的绝对路径；未设置且缺失分片时自动使用内置 Moshier／`analytic_solar`／`astronomy-engine` 零体积降级，显式设置但缺少分片时报错 `de441_archive_missing`（详见[星历说明](ephemeris.md)） |
| `FATEBRIDGE_SOLAR_TERM_MODEL` | `auto` | 太阳交节模型；`auto` 在 1700–2300 年默认使用随包 DE440（`FATEBRIDGE_JPL_FILE` 优先），可选 `native`、`swiss`、`analytic`、`spk`、`de440`、`aa1996`、`vsop2013` |
| `FATEBRIDGE_SOLAR_SPK_FILE` | 未设置 | 仅 `FATEBRIDGE_SOLAR_TERM_MODEL=spk` 时读取的外部 SPK 文件路径（需安装 `jpl` 可选依赖） |
| `FATEBRIDGE_VSOP2013_MANIFEST` | 未设置 | 仅 `FATEBRIDGE_SOLAR_TERM_MODEL=vsop2013` 时读取的本地构建 `manifest.json` 路径（1700–2300 年） |
| `FATEBRIDGE_AA1996_MANIFEST` | 未设置 | 仅 `FATEBRIDGE_SOLAR_TERM_MODEL=aa1996` 时读取的本地构建 `manifest.json` 路径 |

### 运行时、校验与诊断

| 变量 | 默认值 | 用途 |
| --- | --- | --- |
| `FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY` | `min(4, max(1, CPU 数))` | 单进程重计算并发信号量上限，最小为 `1`；用于进程内并发保护，不是请求速率限制 |
| `FATEBRIDGE_STRICT_OUTPUT_VALIDATION` | 未设置（关闭） | 设为 `1` / `true` / `yes` / `on` 时，每次执行均校验完整嵌套输出模型与领域不变量（用于开发与契约测试） |
| `CODEX_CLI_PATH` | 未设置 | 仅供 `fatebridge doctor` 解析桌面端 Codex CLI 可执行路径，不影响 REST、MCP 或计算结果 |

## 加载顺序

REST、MCP 与 CLI 启动时会读取源码仓库根目录的 `.env`，但进程中已经存在的环境变量优先级更高。内置 `.env` 解析仅支持简单 `KEY=value`、首尾成对引号和 `#` 整行注释，不执行 shell 展开。CLI 自身通常不依赖服务端 `.env` 鉴权设置；独立工具（`uv tool install`）或服务管理器部署时，不应依赖当前工作目录 `.env` 的自动发现，请直接通过启动器或客户端 `env` 注入。

## REST 鉴权

开启鉴权示例：`FATEBRIDGE_API_KEYS=agent:replace-me`，调用端发送请求头 `X-API-Key: replace-me`。支持逗号分隔多个条目（可带 `name:` 前缀或仅填密文，但非空配置中的空条目、缺字段或重名会阻止启动）。

免鉴权路径包括 `/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json` 及 `OPTIONS` 预检；`/api/tools` 与全部业务路由均受 API Key 保护。鉴权仅适用于 REST，默认 stdio MCP 与 CLI 不读取也不校验 REST API Key。共享密钥不提供多用户权限或数据隔离，网络部署职责见[安全策略](../SECURITY.md#scope-notes)。修改任何配置后请重启对应进程并用实际请求确认生效。
