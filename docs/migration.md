# FateBridge 迁移指南

[文档中心](README.md) · [API 参考](api-reference.md) · [故障排除](troubleshooting.md)

本页供使用旧版路由、字段或 Python 导入的调用方升级。先用 `fatebridge describe <tool> --detail input`、REST `/openapi.json` 或当前 MCP `tools/list` 核对目标契约；首次接入直接阅读[快速入门](getting-started.md)。具体发布变化见 [CHANGELOG](../CHANGELOG.md)。

## 入口与模块迁移

历史兼容模块、重导出、文本包装及旧路由已退出支持。Python 调用方应直接导入职责模块，协议调用方使用正式路由或原生 MCP Client。

| 已删除的入口 | 当前入口 |
| --- | --- |
| `core/tool_spec.py` | `application.tool_spec`、`bindings`、`execution`、`projection`、`description`；协议注册使用 `transports.rest/mcp` |
| `core/discovery.py`、`core/scenarios.py` | `application.discovery`、`application.scenarios` |
| `core/request_models.py` | `core.requests` 中各领域的定义模块 |
| `core/astrology.py` | `core.astro` 中的职责模块；共用表使用 `core.astrology_tables` |
| `utils/helpers.py` | `utils.birth_input/solar_time/formatting/analysis_clock/elements` |
| `core.predictive`、`core.local_techniques`、`core.metaphysics` 的包级重导出 | 按技法导入具体子模块 |
| `services.calculation` 的出生构造器/响应私有别名 | `services.birth_context.build_birth_computation_context`、`birth_payload.build_destiny_payload` |
| `services.timing` 的日历查询和私有 helper 重导出 | `services.calendar_tools/calendar_input/timing_state/timing_snapshots` |
| `services.tool_catalog` 的绑定/服务代理重导出 | `services.catalog` 中相应领域模块；中央目录只负责装配和合同补全 |
| `api` 的请求模型、服务和历史 handler 别名 | 请求模型直接导入定义模块；HTTP 调用正式路由 |
| `mcp_server.<tool>.fn` 文本包装 | 原生 FastMCP Client；结果包含 JSON text、`structuredContent` 与原生 `isError` |
| `POST /api/calculate`、CLI `calculate_legacy` | 独立命盘使用 `/api/cn/bazi/birth` / `bazi_birth`，字段位于 `bazi_birth` 对象；综合分析使用 MCP / CLI `analyze_destiny` |

## 请求与响应变化

公开请求字段统一使用模型的 Python 字段名，例如 `gps_lat`、`gps_lon`、`use_true_solar_time`、`planet_info`、`astro_meaning`。历史 camelCase 请求别名已移除，未知字段在三端返回输入校验错误。关系盘只接受 `relative_mode`；比较盘使用 `compare`，影响盘使用 `synastry` / `influence`，合成盘使用 `composite`。关系盘方向字段只保留 snake_case，单盘结果放在 `chart`，不再重复返回 `composite_chart`。

主限赤经推运使用唯一方法名 `equatorial`；`legacy_reference` 和 `legacy_equatorial` 已移除。导出章节按当前注册名称精确匹配，不映射历史标题。当前 FastMCP 最低版本为 3.4.2，直接使用其原生 `ToolResult`，不保留旧版本结果子类。

## 升级后验证

1. 用虚构的最小请求核对当前输入 Schema，处理未知字段和枚举错误；不要只替换 URL。
2. 通过实际使用的 REST / MCP / CLI 调用检查响应层级、错误包络及投影路径。三端名称映射见 [API 参考](api-reference.md#24-三端能力边界)。
3. 更新包后重启服务及 MCP 连接，重新读取工具 Schema；配置存在不代表当前聊天已加载新定义。
4. 数值对比固定原输入、分析时间、太阳时策略与环境，保存 `run_metadata`；完整文件沿用[同次导出](agent-guide.md#完整结果交付与同次导出)流程。
