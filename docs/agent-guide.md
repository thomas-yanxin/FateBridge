# FateBridge 开发者 / Agent 接入指南

应用集成 FateBridge 需要遵循清晰的闭环：**发现 → 调用 → 解读 → 恢复**。本文说明三端共享的渐进发现、控制面、字段投影、统一错误包络与出生资料约定，帮助开发者与 Agent 宿主快速完成集成。首次安装请先看[快速入门](getting-started.md)，总体分工见[核心概念](concepts.md)。

| 集成任务 | 入口 |
| --- | --- |
| 选择 REST、MCP 或 CLI | [按通道接入](#按通道接入) |
| 1. 发现：根据问题定位工具与契约 | [发现：自助发现，不硬编码工具列表](#发现自助发现不硬编码工具列表) |
| 2. 调用：三端共享控制面 | [调用：三端共享的控制面与通道](#调用三端共享的控制面与通道) |
| 3. 解读：输出分级与严格投影 | [输出控制与结果读取](#输出控制与结果读取) |
| 4. 恢复：错误处理与时钟复现 | [错误恢复与复现](#错误恢复与复现) |
| 收集出生资料和时间条件 | [出生信息：一次说清](#出生信息一次说清) |
| 实现咨询 Agent 或风水集成 | [Agent 接入闭环](#agent-接入闭环) · [家居风水接入](#家居风水接入) |

FateBridge 通过三条通道暴露领域能力：REST（`python -m fatebridge.api`，默认 `:8010`）、FastMCP（`fatebridge-mcp` 或 `python -m fatebridge.mcp_server`）和 CLI（`fatebridge <tool> ...`）。三条通道共用中央 `ToolSpec` 目录、请求模型与共享执行层。目录共有 90 条记录，REST 公开 90 个工具，CLI 可执行 90 条。MCP 通过两个入口提供 90 项业务能力（`discover_tools` 与 `run_calculation`）。三端共用规范工具名（`spec.name`）和请求字段。完整算法清单见 [algorithm-coverage.md](algorithm-coverage.md)，完整端点说明见 [api-reference.md](api-reference.md)。

## 发现：自助发现，不硬编码工具列表

工具列表由中央目录动态生成。已知工具定义时可直接调用；不确定用途或参数时按两级发现（`summary` 默认 / `full` 附带 `output_schema`，需配合 `tool`、`family` 或 `q` 过滤）渐进查询，返回始终包含全局 `families` 计数：

| 当前已有信息 | 下一步 |
| --- | --- |
| 工具已公开，输入 Schema 与用途明确 | 直接调用；解释同一结果无需重新发现或计算 |
| 知道用户场景，尚未确定工具 | 按 `family` 或 `q` 检索摘要（`detail=summary`），再取选中工具契约 |
| 已确定工具，仅缺参数或视图定义 | REST `GET /api/tools?tool=...`、CLI `fatebridge discover <tool>` 或 MCP `discover_tools(tool=...)` |
| 需要完整输出 Schema | 传入 `detail=full` 并配合 `tool`、`family` 或 `q` 额外读取 `output_schema` |

拼错工具名时，发现接口与 `run_calculation` 均返回 `unknown_tool`（404）并在 `issues[].constraints.suggestions` 中给出相近候选。咨询组织与边界要求见[方法参考](interpretation/README.md)、[时间选择](interpretation/shared/timing-selection.md)与[硬边界](interpretation/shared/safety-boundaries.md)。公共接口拒绝已知明确的生死或临床医疗请求。

### REST：`GET /api/tools`

```bash
curl http://localhost:8010/api/tools
curl 'http://localhost:8010/api/tools?detail=summary&family=bazi'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart&detail=full'
```

`detail=summary`（默认）在未指定 `tool` 时返回各工具摘要，在指定 `tool` 时返回完整 `input_schema`、`parameters`、`evidence_views` 与 `example_input`；`detail=full` 额外附带 `output_schema`，但必须配合 `tool`、`family` 或 `q` 过滤（未过滤的 `detail=full` 返回 `filter_required_for_full_detail`），避免全量输出超出上下文预算。支持按 `family`（逗号分隔）、`q`、`tool` 与 `surface` 筛选。`counts` 返回全局数量，`families` 返回各分类数量，`matched_count` 返回当前匹配数量；每条记录的 `surfaces` 采用 `{"cli": true, "rest": "<path>|null", "mcp": <bool>}` 标记可用通道。

### CLI：`list`、`discover` 与 `doctor`

```bash
fatebridge list
fatebridge discover --family bazi
fatebridge discover bazi_birth_chart
fatebridge discover --tool bazi_birth_chart --detail full
```

`list` 输出分类文本列表，`discover` 返回与 REST 同源的 JSON 契约（指定 `tool` 或 `--detail full` 时附带可直接运行的 `cli_example`），`doctor` 检查当前安装、依赖版本与独立 stdio MCP 连通性。

### FastMCP：`discover_tools` 与 `run_calculation`

MCP 仅暴露两个协议工具：`discover_tools` 和 `run_calculation`（无资源 URI）。`FATEBRIDGE_MCP_FAMILIES` 可限制 MCP 公开的能力范围，配置见 [MCP 部署指南](mcp-deployment.md#工具筛选与运行环境)。

## 调用：三端共享的控制面与通道

REST、MCP 与 CLI 共用三项正交输出与时钟控制参数：

| 控制项 | REST（查询参数） | MCP（`run_calculation` 参数） | CLI（子命令选项） | 默认值与行为 |
| --- | --- | --- | --- | --- |
| `detail` | `?detail=compact\|audit` | `detail="compact"\|"audit"` | `--detail compact\|audit` | 默认 `compact`（精简核心业务字段）；`audit` 返回完整结果、方法与误差证据 |
| `fields` | `?fields=a&fields=b.c` | `fields=["a", "b.c"]` | `--fields a b.c` | 始终严格校验点号对象路径；`run_metadata` 始终保留 |
| `as_of` | `?as_of=2026-06-01T12:00:00+08:00` | `as_of="2026-06-01T12:00:00+08:00"` | `--as-of 2026-06-01T12:00:00+08:00` | 带时区 ISO 8601 时刻，冻结隐式当前时钟以便复现 |

### 出生信息：一次说清

大多数命理与占星工具共用出生信息字段（详见 [API 参考 §3](api-reference.md#3-共享请求族)）：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必填（公历）
- `birth_minute`：可选，默认 `0`
- `gender`：八字专项可选建议传入，`bazi_luck_cycles` 等必填，支持 `男`/`女`、`male`/`female`
- `birth_place`：可选，内置静态地名解析（参见[离线城市目录](place-catalog.md)）
- `birth_timezone`：可选，IANA 时区或 UTC 偏移；高精度星盘建议显式传入
- `birth_longitude` / `birth_latitude`：视工具而定，占星盘建议显式传入
- `use_true_solar_time`：中式出生模型默认 `true`（无经度时回退钟表时间并附提示，显式 `true` 无经度报错）；核心星盘默认 `false`

当前出生模型要求提供小时，不猜未知出生时刻。真太阳时与时区校正详情记录在 `person_info.time_adjustment`。

### 按通道接入

#### REST（HTTP）

业务参数放入 JSON 请求体，`detail`、`fields`、`as_of` 等控制项放在 URL 查询参数：

```bash
curl -X POST 'http://localhost:8010/api/bazi/wealth?fields=wealth_analysis' \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-me" \
  -d '{"gender":"男","birth_year":1990,"birth_month":5,"birth_day":15,
       "birth_hour":10,"birth_timezone":"Asia/Shanghai","birth_place":"北京","use_true_solar_time":true}'
```

Python `requests` 示例：

```python
import requests

resp = requests.post(
    "http://localhost:8010/api/bazi/wealth",
    headers={"X-API-Key": "replace-me"},
    params={"fields": ["wealth_analysis"]},
    json={
        "gender": "男", "birth_year": 1990, "birth_month": 5, "birth_day": 15,
        "birth_hour": 10, "birth_timezone": "Asia/Shanghai", "birth_place": "北京",
        "use_true_solar_time": True,
    },
    timeout=30,
)
data = resp.json()
if not resp.ok or data.get("error_code"):
    raise RuntimeError(f"HTTP {resp.status_code}: {data.get('error_code', data)}")
print(data["wealth_analysis"])
```

JavaScript `fetch` 示例：

```js
const url = new URL("http://localhost:8010/api/bazi/wealth");
url.searchParams.append("fields", "wealth_analysis");
const res = await fetch(url, {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": "replace-me" },
  body: JSON.stringify({
    gender: "男", birth_year: 1990, birth_month: 5, birth_day: 15,
    birth_hour: 10, birth_timezone: "Asia/Shanghai", birth_place: "北京",
    use_true_solar_time: true,
  }),
});
const data = await res.json();
if (!res.ok || data.error_code) throw new Error(`HTTP ${res.status}: ${data.error_code ?? "request_failed"}`);
console.log(data.wealth_analysis);
```

#### FastMCP（Agent host）

客户端安装配置、Windows 写法与 HTTP 部署见 [MCP 部署指南](mcp-deployment.md)。协议调用需注意：

- 默认使用 stdio，由 host 启动子进程，请使用目标环境的 Python 绝对路径。
- 业务与错误结构化结果通过 `structuredContent` 返回，客户端需关注 `isError` 并读取 `error_code`。
- 调用 `run_calculation(tool=..., arguments={...}, detail="compact"|"audit", fields=[...], as_of=...)` 执行计算。

#### CLI（脚本 / 自动化）

```bash
fatebridge list
fatebridge discover ziwei_birth_chart
fatebridge ziwei_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 --birth-hour 10 --gender male
fatebridge knowledge_read --domain bazi --category romance --key 桃花咸池
```

所有 90 个目录命令均支持 `--request-file PATH` 读取 JSON 请求文件（命令行显式参数覆盖文件中的同名顶层字段），以及 `--detail {compact,audit}`、`--fields` 与 `--as-of`。

## 输出控制与结果读取

### 两级详细度：`compact` 与 `audit`

- `detail="compact"`（默认）：在未指定 `fields` 时按工具配置返回精简的核心业务字段，同时 `run_metadata` 精简为 `run_id`、`tool_name`、`generated_at`、`engine`、`engine_is_approximate`、`effective_time`、`warnings`、`replay`。
- `detail="audit"`：保留完整业务载荷（含完整时间线、嵌套取证与方法依据），并在 `run_metadata` 中附加 `calculation_evidence`、`runtime`、`provenance` 等审计信息。

需要完整 JSON、全部时间线或深度审计字段时，直接传入 `detail="audit"` 且保持 `fields=null`（CLI 省略 `--fields`）。

### 严格字段投影：`fields`

三端均支持按点号对象路径严格投影（如 `bazi_birth.day_master`）：

- 路径从输出根开始，支持多层点号路径；数组须选择其所属字段后在调用方处理，不能传入数字索引（否则返回 `non_object_projection_path`）。
- 始终严格校验：若路径不存在，返回 `validation_error`（`issues[].code="unknown_projection_path"`，`retryable=false`），并在 `issues[].constraints.available` 中列出当前层级可用的字段名以便立即修正。
- `run_metadata` 始终保留；若与 `detail="compact"` 合用且未显式请求 `run_metadata`，则保留精简版 `run_metadata`。

```bash
fatebridge bazi_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 \
  --birth-hour 10 --gender male --fields bazi_birth.four_pillars bazi_birth.day_master
```

## 错误恢复与复现

### 统一错误包络

已知工具的模型校验与业务计算错误共享顶层 `error`、`error_code` 与 `retryable`（MCP 与 CLI 可附带 `status_code`）：

```json
{
  "error": "请求参数无效",
  "error_code": "validation_error",
  "retryable": false,
  "issues": [
    {
      "path": "birth_month",
      "code": "less_than_equal",
      "message": "Input should be less than or equal to 12",
      "constraints": {"le": 12}
    }
  ]
}
```

请按 `error_code` 和 `issues[].code` 分支，并用 `issues[].path` 与 `constraints`（如 `suggestions`、`available`、`expected`）修正输入参数；只有 `retryable=true` 时才按原参数重试。常见 `error_code` 包括：`validation_error`（400/422）、`unknown_tool`（404）、`authentication_required`（401）、`dependency_missing`（503）、`fengshui_calculation_inconsistent`（503，玄空内部数字矛盾不可重试）、`consultation_restricted`（禁区请求拦截）、`timeout`（504）和 `internal_error`（500）。

MCP 业务/校验失败返回原生 `isError=true`；使用 FastMCP Client 读取结构化详情时需传 `raise_on_error=False`。CLI 成功退出码为 `0`，计算或校验失败为 `1`，用法错误（如未知 flag）为 `2`；结果和错误均输出到 stdout，日志写 stderr。

### `run_metadata` 与复现

成功响应始终附带 `run_metadata`，包含 `run_id`、`tool_name`、`generated_at`、`engine`、`engine_is_approximate`、`effective_time` 与 `replay`。将 `replay.overrides` 合并至原输入并使用 `replay.as_of`（REST 查询参数 / MCP `as_of` / CLI `--as-of`），可在相同环境中复现同一业务结果。服务不持久化历史运行数据库。

## Agent 接入闭环

1. **发现**：工具与参数明确时直接调用；存在缺口时调用 `discover_tools` / `GET /api/tools` / `fatebridge discover`，按 `family` 或 `q` 检索后读取目标工具的 `input_schema`、`evidence_views` 与 `suggested_fields`；经典条文用 `knowledge_catalog` / `knowledge_read` 查询。
2. **调用**：只索取所选方法必需的资料；未知生时禁止猜测或套用示例值。默认使用 `detail="compact"`，需要特定证据时按 `evidence_views` 传入 `fields`，需要完整载荷时传入 `detail="audit"` 且 `fields=null`。
3. **解读**：区分计算事实、传统来源与现实建议，保留 `rulesets`、`rule_trace`、`engine_is_approximate` 与 `partial` 范围限制。
4. **恢复**：遇到 `isError=true` / 非零退出码 / 4xx-5xx 时，读取 `error_code`、`issues[].path` 与 `constraints`（`suggestions` / `available`）精确修正输入；仅 `retryable=true` 才按原参数重试。

## 家居风水接入

八个 `fengshui_*` 工具共用同一目录与响应结构，CLI 对嵌套请求使用 `--request-file`。组合分析 `fengshui_assess` 在 `layers` 下分层返回八宅、砂水、年星、月星与玄空结果，合法缺项保持 `partial`，不会合并成单一总分；需要评估布局与室内形态时传 `analyze_layout=true`，完整字段语义与现场核对规则见[家居风水参考](fengshui.md)及[现场咨询指南](interpretation/fengshui/consultation.md)。

## 相关文档

- [api-reference.md](api-reference.md)：全部 REST 路由、FastMCP 工具、请求族与响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：12 family / 90 工具的能力范围与依赖矩阵
- [getting-started.md](getting-started.md)：安装与首次计算
- [troubleshooting.md](troubleshooting.md)：环境、依赖、投影与错误排错
