# 运行配置

[文档中心](README.md) · [快速入门](getting-started.md) · [MCP 部署](mcp-deployment.md)

本页列出常用环境变量、加载顺序和 REST 鉴权。只运行本地 CLI 示例时无需配置 REST。完整星历选项见[太阳后端](solar-backends.md)和[星历安装](ephemeris.md)。

## 环境变量

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
| `SE_EPHE_PATH` | 未设置 | 自定义本地星历目录，不在模板内 |
| `FATEBRIDGE_SOLAR_TERM_MODEL` | `auto` | 当前源码在 1700–2300 年默认使用随包 DE440；严格原生 JPL 配置优先。各模式、年份和相邻边界见[太阳后端](solar-backends.md) |
| `FATEBRIDGE_SOLAR_SPK_FILE` | 未设置 | 仅显式`spk`模式使用的外部文件，需可选`jpl`依赖；默认随包系数不读取该文件 |
| `FATEBRIDGE_HEAVY_CALC_MAX_CONCURRENCY` | `min(4, max(1, CPU 数))` | 单进程的重计算并发上限，至少为 1；不是请求速率限制 |

## 加载顺序

API 和 MCP 启动时会读取源码安装目录根部的 `.env`，已经存在的进程环境变量优先。文件解析仅支持简单 `KEY=value`、包裹引号和整行注释，不执行 shell 展开。CLI 不自动加载 `.env`，需要时在启动前设置进程环境变量。wheel 安装不应依赖当前工作目录 `.env` 的自动发现，请由启动器注入环境。

## REST 鉴权

REST 鉴权示例：`FATEBRIDGE_API_KEYS=agent:replace-me`，请求发送 `X-API-Key: replace-me`，不是 `agent:replace-me`。也支持逗号分隔多项与单独 secret；非空配置的空条目、缺少名称/密钥或重复名称会阻止启动。修改环境后重启进程。

免鉴权路径：`/health`、`/ready`、`/metrics`、`/docs`、`/redoc`、`/openapi.json`；`OPTIONS` 免检。`/api/tools` 和业务路由均需密钥。鉴权仅适用于 REST，默认 stdio MCP 与 CLI 不使用 API Key。

密钥共享服务可访问的结果存储，不提供用户或结果所有权隔离；网络部署职责见[安全策略](../SECURITY.md#scope-notes)。修改配置后重启对应进程，再用实际请求确认生效。
