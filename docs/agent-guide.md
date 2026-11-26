# FateBridge 开发者 / Agent 接入指南

应用集成 FateBridge 需要正确选择工具、传递时间与空间输入、处理统一错误包络，并在超出响应预算时读取同一次运行的完整输出。本文说明这些公共调用约定，帮助开发者与 Agent 宿主快速完成集成。首次安装请先看[快速入门](getting-started.md)，总体分工见[核心概念](concepts.md)。

| 集成任务 | 入口 |
| --- | --- |
| 选择 REST、MCP 或 CLI | [按通道接入](#按通道接入) |
| 根据用户问题选择工具 | [自助发现](#自助发现别硬编码工具列表) |
| 处理失败、快照和字段投影 | [公共调用约定](#公共调用约定) |
| 保存与核验完整 JSON | [完整结果交付与同次导出](#完整结果交付与同次导出) |
| 收集出生资料和时间条件 | [出生信息](#出生信息一次说清) |
| 实现咨询 Agent 或风水集成 | [Agent 接入建议](#agent-接入建议) · [家居风水接入](#家居风水接入) |

FateBridge 通过三条通道暴露领域能力：REST（`python -m fatebridge.api`，默认 `:8010`）、FastMCP（`fatebridge-mcp` 或 `python -m fatebridge.mcp_server`）和 CLI（`fatebridge <tool> ...`）。三条通道共用中央 `ToolSpec` 目录、请求模型与共享执行层。目录共有 93 条记录，REST 公开 93 个工具，CLI 可执行 93 条。MCP 通过四个入口提供 93 项业务能力。三端共用工具名和请求字段。完整算法清单见 [algorithm-coverage.md](algorithm-coverage.md)，完整端点说明见 [api-reference.md](api-reference.md)。

## 自助发现：别硬编码工具列表

工具列表由中央目录动态生成。已知工具定义时可直接调用；不确定用途或参数时按需要分步发现：

| 当前已有信息 | 下一步 |
| --- | --- |
| 工具已公开，输入 Schema 与用途明确 | 直接调用；解释同一结果无需重新发现或计算 |
| 知道用户场景，尚未确定工具 | 读实际工具说明或 family 摘要，再取选中工具契约 |
| 已确定工具，仅缺参数定义 | REST 单工具记录、CLI `describe --detail input` 或 MCP `describe_capability` |
| 需要更细输出字段 | 读取单工具完整契约与 `evidence_views` |

咨询组织与境界要求见[方法参考](interpretation/README.md)、[时间选择](interpretation/shared/timing-selection.md)与[硬边界](interpretation/shared/safety-boundaries.md)。公共接口拒绝已知明确的生死或临床医疗请求。

### REST：`GET /api/tools`

```bash
curl http://localhost:8010/api/tools
curl 'http://localhost:8010/api/tools?detail=summary&family=bazi'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart&detail=full'
```

`detail=summary` 返回精简摘要，`detail=full` 附带 `input_schema` 和 `output_schema`。支持按 `family`（逗号分隔）、`q`、`tool` 与 `surface` 筛选。`counts` 返回全局数量，`matched_count` 返回当前匹配数量。

### CLI：`list`、`discover` 与 `describe`

```bash
fatebridge list
fatebridge discover --family bazi
fatebridge discover --tool bazi_birth_chart --detail full
fatebridge describe bazi_wealth --detail input
```

`list` 输出文本列表，`discover` 返回与 REST 同源的 JSON 摘要，`describe` 提供单工具参数 Schema 与可直接运行的 `cli_example`（仅当存在合法示例时）或 `cli_usage`。

### FastMCP

MCP 暴露四个协议工具：`discover_capabilities`、`describe_capability`、`run_calculation` 和 `read_result`。也可读取 `fatebridge://catalog/summary`、`fatebridge://families/{family}` 与 `fatebridge://tools/{tool}` 等资源。

`run_calculation` 默认使用 `detail="compact"`，选取核心首轮字段并省略顶层快照文本；需要特定证据时按 `evidence_views` 传入 `fields` 并开启 `strict_fields=true`。需要完整 JSON、全部时间线或完整文件时，首次调用使用 `detail="audit"` 且 `fields=null`。`FATEBRIDGE_MCP_FAMILIES` 可限制 MCP 公开的能力范围，配置见 [MCP 部署指南](mcp-deployment.md#工具筛选与运行环境)。

## 公共调用约定

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

请按 `error_code` 和 `issues[].code` 分支，并用 `issues[].path` 修正输入参数，只有 `retryable=true` 时才按原参数重试。常见 `error_code` 包括：`validation_error`（400/422）、`authentication_required`（401）、`dependency_missing`（503）、`fengshui_calculation_inconsistent`（503，玄空内部数字矛盾不可重试）、`consultation_restricted`（禁区请求拦截）、`timeout`（504）和 `internal_error`（500）。

MCP 业务/校验失败返回原生 `isError=true`；使用 FastMCP Client 读取结构化详情时需传 `raise_on_error=False`。CLI 成功退出码为 `0`，计算或校验失败为 `1`，用法错误（如未知 flag）为 `2`；结果和错误输出到 stdout，日志写 stderr。

### `run_metadata` 溯源层

成功响应默认附带 `run_metadata`（CLI 可用 `--no-metadata` 关闭），包含 `run_id`、`trace_id`、`tool_name`、`generated_at`、`engine`、`engine_is_approximate`、`effective_time` 与 `replay`。将 `replay.overrides` 合并至原输入并使用 `replay.as_of`（REST 查询参数 / MCP `as_of` / CLI `--as-of`），可在相同环境中复现同一业务结果。跨工具关联传 `trace_id` 与 `parent_run_id`；服务不按 `run_id` 自动查询历史请求。

### 快照协议：`snapshot_text` 与 `snapshot_export`

支持双层快照的工具可返回人读文本 `snapshot_text` 及可筛选导出结构 `snapshot_export`（含 `selected_sections`、`section_titles_detected`、`export_text`）。`selected_sections` 仅裁剪导出文本，不影响结构化业务数据；显式选择未命中任何章节时 `export_text` 为空。覆盖矩阵见[快照协议覆盖](algorithm-coverage.md#4-快照协议覆盖)。

### 字段投影：控制输出体积

三端均支持字段投影与快照开关：

- CLI：`--fields KEY [KEY ...]`、`--strict-fields`、`--no-include-snapshot-text`、`--compact`
- FastMCP：`fields=[...]`、`strict_fields=true`、`include_snapshot_text=false`
- REST：查询参数 `?fields=wealth_analysis&strict_fields=true&include_snapshot_text=false`

路径从输出根开始，支持点号对象路径（如 `bazi_birth.day_master`），数组须选择所属字段。`strict_fields=false` 时无效路径附带 `projection_warnings`，`strict_fields=true` 则返回 `validation_error`（`retryable=false`）。

```bash
fatebridge bazi_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 \
  --birth-hour 10 --gender male --fields snapshot_text bazi_birth.day_master --strict-fields
```

## 完整结果交付与同次导出

MCP 默认 `response_char_limit=8192`，REST 与 CLI 默认 `0`（不限制；可设 `0` 或 `4096–65536`）。成功结果超出非零预算时，响应附带 `result_delivery`，已保留字段在行内返回，其余字段通过同一 run 的交付物按页或按字段读取，无需重算。需要完整 JSON 时，**首次调用必须使用 `detail=audit` 且 `fields=null`**（CLI 不传 `--fields`），因为交付文件仅保存首次过滤后的结果。

MCP 读取顺序：读取 `result_delivery.manifest_uri` 确认大小与有效期，随后从 `first_page_uri` 跟随 `next_uri` 解析每页 JSON 包装并拼接其中的 `text` 字符串后再整体解析为 JSON；也可按点路径读取 `fatebridge://results/{result_id}/fields/{path}/{offset}` 或校验资源 `fatebridge://results/{result_id}/verified/{run_id}/{offset}`。

HTTP 客户端可通过 `GET /api/results/{result_id}/payload` 一次下载完整保留 JSON，或使用 `/pages`、`/verified?expected_run_id=...` 按需分页读取。同机脚本可使用 CLI 校验读取：

```python
import json
import subprocess
from pathlib import Path

reply = json.loads(Path("reply.json").read_text(encoding="utf-8"))
ref = reply["result_delivery"]
offset = 0
while offset is not None:
    page = json.loads(subprocess.check_output([
        "fatebridge", "result-read", ref["result_id"],
        "--run-id", reply["run_metadata"]["run_id"],
        "--path", "analysis_context", "--offset", str(offset),
    ], text=True))
    print(page["text"], end="")
    offset = page["next_offset"]
```

交付引用约一小时过期，并受 64 MiB 容量回收限制，应及时保存所需结果。

## 出生信息：一次说清

大多数命理与占星工具共用出生信息字段（详见 [API 参考 §3](api-reference.md#3-共享请求族)）：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必填（公历）
- `birth_minute`：可选，默认 `0`
- `gender`：八字专项可选建议传入，`bazi_luck_cycles` 等必填，支持 `男`/`女`、`male`/`female`
- `birth_place`：可选，内置静态地名解析（参见[离线城市目录](place-catalog.md)）
- `birth_timezone`：可选，IANA 时区或 UTC 偏移；高精度星盘建议显式传入
- `birth_longitude` / `birth_latitude`：视工具而定，占星盘建议显式传入
- `use_true_solar_time`：中式出生模型默认 `true`（无经度时回退钟表时间并附提示，显式 `true` 无经度报错）；核心星盘默认 `false`

当前出生模型要求提供小时，不猜未知出生时刻。真太阳时与时区校正详情记录在 `person_info.time_adjustment`。

## 按通道接入

### REST（HTTP）

业务参数放入 JSON 请求体，`fields`、`strict_fields`、`include_snapshot_text`、`as_of` 等控制项放在 URL 查询参数：

```bash
curl -X POST 'http://localhost:8010/api/bazi/wealth?fields=wealth_analysis&strict_fields=true&include_snapshot_text=false' \
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
    params={"fields": ["wealth_analysis"], "strict_fields": "true", "include_snapshot_text": "false"},
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
url.searchParams.set("strict_fields", "true");
url.searchParams.set("include_snapshot_text", "false");
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

### FastMCP（Agent host）

客户端安装配置、Windows 写法与 HTTP 部署见 [MCP 部署指南](mcp-deployment.md)。协议调用需注意：

- 默认使用 stdio，由 host 启动子进程，请使用目标环境的 Python 绝对路径。
- 业务与错误结构化结果通过 `structuredContent` 返回，客户端需关注 `isError` 并读取 `error_code`。
- 通过 `fields` 与 `detail` 控制响应体积，超预算时通过 `read_result` 或 MCP 资源读取同次交付结果。

### CLI（脚本 / 自动化）

```bash
fatebridge list
fatebridge describe ziwei_birth_chart
fatebridge ziwei_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 --birth-hour 10 --gender male
fatebridge knowledge_read --domain bazi --category romance --key 桃花咸池
```

`--subject-file /path/to/person.json` 可复用扁平出生字段，显式参数优先。CLI 另提供 `profile` 命令为同一人批量运行多套体系（默认 `bazi,ziwei,astro`）：

```bash
fatebridge profile --systems bazi,ziwei,astro \
  --birth-year 1990 --birth-month 5 --birth-day 15 --birth-hour 10 \
  --gender 男 --birth-place 北京 --birth-timezone Asia/Shanghai \
  --birth-longitude 116.40 --birth-latitude 39.90
```

## Agent 接入建议

1. 发现：工具明确时直接调用；存在缺口时按 family 或关键词读摘要与单工具契约，首轮按 `suggested_fields` 取证，追问沿 `evidence_views` 补取，经典条文用 `knowledge_catalog` / `knowledge_read` 查询。
2. 路由：按问题意图与已确认资料选择能力，覆盖范围见[算法覆盖矩阵](algorithm-coverage.md)。
3. 取数：只索取所选方法必需的资料；未知生时禁止猜测或套用示例值。
4. 裁剪与交付：摘要启用 `strict_fields=true`；完整导出首轮用 `detail=audit` 且 `fields=null`。
5. 判错与溯源：基于 `error_code` 处理异常；保存原输入、`run_metadata` 与精度标志以便复现。

## 家居风水接入

八个 `fengshui_*` 工具共用同一目录与响应结构，CLI 对嵌套请求使用 `--request-file`（支持未知字段校验）。组合分析 `fengshui_assess` 在 `layers` 下分层返回八宅、砂水、年星、月星与玄空结果，合法缺项保持 `partial`，不会合并成单一总分；需要评估布局与室内形态时传 `analyze_layout=true`，完整字段语义与现场核对规则见[家居风水参考](fengshui.md)及[现场咨询指南](interpretation/fengshui/consultation.md)。

## 相关文档

- [api-reference.md](api-reference.md)：全部 REST 路由、FastMCP 工具、请求族与响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：14 family / 93 工具的能力范围与依赖矩阵
- [getting-started.md](getting-started.md)：安装与首次计算
- [troubleshooting.md](troubleshooting.md)：环境、依赖、投影与交付排错
