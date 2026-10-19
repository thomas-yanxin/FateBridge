# FateBridge 迁移指南

[文档中心](README.md) · [API 参考](api-reference.md) · [故障排除](troubleshooting.md)

本页供使用旧版路由、字段或 Python 导入的调用方升级。先用 `fatebridge describe <tool> --detail input`、REST `/openapi.json` 或当前 MCP `tools/list` 核对目标契约；首次接入直接阅读[快速入门](getting-started.md)。具体发布变化见 [CHANGELOG](../CHANGELOG.md)。

本页导航：[升级步骤](#升级步骤) · [入口与模块迁移](#入口与模块迁移) · [请求与响应变化](#请求与响应变化) · [升级后验证](#升级后验证)

## 升级步骤

1. 记录当前包版本、调用入口和一组虚构的代表请求；保留原始响应，便于比较字段与错误行为。
2. 升级依赖并核对当前契约。源码开发环境使用 `uv sync --locked --extra dev`；已发布包的安装方式见[快速入门](getting-started.md)。
3. 按下方迁移表替换入口，清理旧字段和枚举，再更新投影路径及响应解析。
4. 重启 REST 服务或 MCP 进程，重新建立客户端连接并执行[升级后验证](#升级后验证)。

从源码运行时，可先查看请求定义，再用完整视图读取输出 Schema：

```bash
uv run --locked --extra dev fatebridge describe bazi_birth --detail input
uv run --locked --extra dev fatebridge describe bazi_birth --detail full
```

对于只使用 MCP 的客户端，以新进程实际公开的 `tools/list` 为准；REST 以运行中服务的 `/openapi.json` 为准。迁移 Python 导入只适用于直接调用内部模块的集成；日常使用优先通过三个公开接口。

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

### 字段与关系盘

公开请求字段统一使用模型的 Python 字段名，例如 `gps_lat`、`gps_lon`、`use_true_solar_time`、`planet_info`、`astro_meaning`。历史 camelCase 请求别名已移除，未知字段在三端返回输入校验错误。关系盘只接受 `relative_mode`；比较盘使用 `compare`，影响盘使用 `synastry` / `influence`，合成盘使用 `composite`。关系盘方向字段只保留 snake_case，单盘结果放在 `chart`，不再重复返回 `composite_chart`。

### 技法名称与导出

主限赤经推运使用唯一方法名 `equatorial`；`legacy_reference` 和 `legacy_equatorial` 已移除。导出章节按当前注册名称精确匹配，不映射历史标题。当前 FastMCP 最低版本为 3.4.2，直接使用其原生 `ToolResult`，不保留旧版本结果子类。

### 专题输出与结果存储

健康文化结果已删除停用的 `disease_risks`、`regimen` 区块，子女专项已删除
`affinity.count_hint` 数量占位字段。健康只提供盘内分类、传统对应与关系变化；
调整字段投影时以当前输出合同为准，不再请求这些旧路径。

完整结果交付只读取带索引与元数据的当前存储格式，不再自动升级旧版无索引记录。
旧记录缺少交付元数据时返回 `result_unavailable`，不会改写已有文件或生成新 run。

## 升级后验证

验证应覆盖成功调用和调用方确实处理的失败分支。仅替换依赖版本、URL 或 Python 导入，不能确认字段和语义已经迁移。

1. 用虚构的最小请求核对当前输入 Schema，处理未知字段和枚举错误；不要只替换 URL。
2. 通过实际使用的 REST / MCP / CLI 调用检查响应层级、错误包络及投影路径。三端名称映射见 [API 参考](api-reference.md#24-三端能力边界)。
3. 更新包后重启服务及 MCP 连接，重新读取工具 Schema；配置存在不代表当前聊天已加载新定义。
4. 数值对比固定原输入、分析时间、太阳时策略与环境，保存 `run_metadata`；完整文件沿用[同次导出](agent-guide.md#完整结果交付与同次导出)流程。

若无法复现旧结果，先比较输入、时钟、依赖和星历指纹，再判断是否为算法差异。过期或旧格式交付引用不能作为重新获取完整结果的来源；需要新计算时，由调用方明确发起新请求并保存新的回执。
