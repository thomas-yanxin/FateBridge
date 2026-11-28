# FateBridge 开发者 / Agent 接入指南

[文档中心](README.md) · [快速入门](getting-started.md) · [API 参考](api-reference.md) · [算法覆盖矩阵](algorithm-coverage.md)

应用与 Agent 宿主集成 FateBridge 遵循四步闭环：**1. 发现 → 2. 调用 → 3. 读取 → 4. 恢复**。REST（`fatebridge-api`，默认 `:8010`）、FastMCP（`fatebridge-mcp`）与 CLI（`fatebridge <tool>`）共用同一中央目录与执行管道：目录共有 91 条记录，REST 公开 91 个工具，CLI 可执行 91 条目录命令，MCP 通过三个入口提供 91 项业务能力，完整清单见[算法覆盖矩阵](algorithm-coverage.md)。

| 环节 | 核心动作 | 跳转 |
| --- | --- | --- |
| 1. 发现 | 动态查询 `family`、`q`、`tool` 与按需 `output_schema` | [发现：自助发现，不硬编码工具列表](#1-发现自助发现不硬编码工具列表) |
| 2. 调用 | 选择通道并准备出生资料、控制项与业务参数 | [调用：三端控制面与按通道接入](#2-调用三端控制面与按通道接入) · [按通道接入](#按通道接入) |
| 3. 读取 | 使用 `include` 增量展开与严格 `fields` 路径投影 | [输出控制与结果读取](#输出控制与结果读取) |
| 4. 恢复 | 按 `error_code`、`issues[]` 与 `run_metadata` 修正或复现 | [错误恢复与复现](#错误恢复与复现) |
| 领域接入 | 遵循咨询流程或集成 8 个家居风水工具 | [Agent 接入闭环](#agent-接入闭环) · [家居风水接入](#家居风水接入) |

## 1. 发现：自助发现，不硬编码工具列表

工具契约由中央目录动态生成。已知工具定义时直接调用；存在不确定项时按两级发现渐进检索：

| 当前状态 | 推荐动作 |
| --- | --- |
| 已知工具名与输入参数 | 直接调用计算入口；同一结果的后续解读无需重算或重新发现 |
| 只知道用户主题，未定工具 | 无参数或按 `family` / `q` 检索 `detail=summary` 摘要 |
| 已确定工具名，缺输入契约或视图 | REST `GET /api/tools?tool=...`、CLI `fatebridge discover <tool>` 或 MCP `discover_tools(tool=...)` |
| 需要完整输出 Schema | 传入 `detail=full` 并配合 `tool`、`family` 或 `q` 过滤，且显式设置 `include_output_schema=True` |

- `detail="brief"`：仅返回必填字段、`field_types`、一两行 `usage_hint` 与 `evidence_views` 名称列表，适合批量预检多个工具。
- `detail="summary"`（默认）：未传 `tool`/`tools` 时返回全局 `counts`、`families` 与工具摘要；指定单个 `tool` 时直接解包返回该工具的 `input_schema`、`example_input`、`evidence_views`、`suggested_fields` 与 `default_omit`；指定多个 `tools` 时返回精简列表。
- `detail="full"`：返回完整契约（包括 `output_fields` 等），**必须**配合 `tool`、`tools`、`family` 或 `q` 之一过滤（否则返回 `validation_error` / `filter_required_for_full_detail`）。**`output_schema` 默认不返回**，仅当显式传入 `include_output_schema=True`（REST `?include_output_schema=true`，CLI `--include-output-schema`）时才会附带。
- 拼写错误时返回 `unknown_tool`（404）并在 `issues[].constraints.suggestions` 给出候选名称。

```bash
# REST 能力发现
curl 'http://localhost:8010/api/tools'
curl 'http://localhost:8010/api/tools?detail=summary&family=bazi'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart'
curl 'http://localhost:8010/api/tools?tools=qimen,liuren_chart,jinkou&detail=brief'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart&detail=full&include_output_schema=true'

# CLI 能力发现与环境自检（同样支持 python -m fatebridge ...）
fatebridge list
fatebridge discover --family bazi
fatebridge discover qimen liuren_chart jinkou --detail brief
fatebridge discover bazi_birth_chart
fatebridge discover --tool bazi_birth_chart --detail full --include-output-schema
fatebridge doctor
```

MCP 暴露 `discover_tools`、`run_calculation` 与 `run_batch` 三个工具（无资源 URI）；多主体或多工具串联可通过 `run_batch`（REST `POST /api/batch`、CLI `fatebridge batch --request-file ...`）共享 `subjects`、`context`（问事/分析时刻 `analysis_datetime`、`place`、`timezone`、`longitude`、`latitude`）与 `defaults`，并在同批请求内自动复用共享计算结果（所有 `extra_forbidden` 校验失败统一返回 `constraints.allowed_fields` 与近义字段建议）。可通过 `FATEBRIDGE_MCP_FAMILIES` 限制公开的 family，配置见 [MCP 部署指南](mcp-deployment.md)。

## 2. 调用：三端控制面与按通道接入

REST、MCP 与 CLI 共用三项正交控制参数：

| 控制项 | REST（URL 查询参数） | MCP（`run_calculation` 参数） | CLI（子命令选项） | 默认值与行为 |
| --- | --- | --- | --- | --- |
| `include` | `?include=view&include=a.b` 或 `?include=*` | `include=["view", "a.b"]` 或 `include=["*"]` | `--include view a.b` 或 `--include "*"` | 默认省略 `default_omit` 中的重型次级块（见 `run_metadata.omitted_fields`）；`include` 按需增量展开点号路径、`evidence_views` 名称或 `["*"]` 无损全量（与 `fields` 互斥） |
| `fields` | `?fields=a&fields=b.c` | `fields=["a", "b.c"]` | `--fields a b.c` | 严格校验点号对象路径替换投影；`run_metadata` 始终保留（与 `include` 互斥） |
| `as_of` | `?as_of=2026-06-01T12:00:00+08:00` | `as_of="2026-06-01T12:00:00+08:00"` | `--as-of 2026-06-01T12:00:00+08:00` | 带时区 ISO 8601 时刻，冻结隐式当前时钟以便复现 |

### 出生信息收集要点

命理与占星工具共用基础出生字段（各家族详情见 [API 参考 §3](api-reference.md#3-共享请求族)）：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必填（公历）；不猜未知出生时刻。当用户确认未知出生时辰时，八字与 `liuren_yearly_timing` 支持显式传入 `birth_time_unknown=true`（不传 `birth_hour`），按三柱模式计算并在 `coverage` 声明边界与缺失项；`jinkou` 与 `liuren_chart` 可直接传入 `birth_date` 自动换算年命并附立春/春节边界提示。
- `birth_minute`：可选，默认 `0`；八字与时运另支持 `birth_second`（`0..59`）与 `birth_utc_offset`（消歧夏令时重复钟时）。
- `gender`：八字专项可选建议传入，`bazi_luck_cycles` 等必填，支持 `男`/`女`、`male`/`female`。
- `birth_place` / `birth_timezone` / `birth_longitude` / `birth_latitude`：支持内置离线 SQLite 地名索引秒级解析（参见[离线城市目录](place-catalog.md)）；`qimen`、`liuren_chart`、`liuren_yearly_timing`、`jinkou`、`taiyi`、`meihua_time_cast` 支持 `analysis_place`（`meihua_cast` 无地点字段），`liuyao`、`canping`、`heluo`、`suzhan`、`interpret_astrology_dice`、`sanshi_combined_chart`、`solar_terms_for_year`、`lunar_calendar_time`、`mundane_ingress_chart`、`horary_chart`、`evaluate_election_time` 支持 `place`（`planetary_returns` 使用 `birth_place`），批处理可在顶层 `context` 统一提供问事时刻与地点。高精度星盘建议显式传经纬度与 IANA 时区。
- `use_true_solar_time`：中式出生模型默认 `true`（无经度回退钟表时间并附提示，显式 `true` 无经度报错）；核心星盘默认 `false`。校正详情见 `person_info.time_adjustment`。

### 按通道接入

#### REST（HTTP）

业务参数放 JSON 请求体，控制参数放 URL 查询参数；若服务端配置了 `FATEBRIDGE_API_KEYS`，请附带 `X-API-Key` 请求头：

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

#### FastMCP（Agent Host）

客户端安装、Windows 配置与 HTTP 部署见 [MCP 部署指南](mcp-deployment.md)。调用时统一使用 `run_calculation(tool=..., arguments={...}, include=[...], fields=[...], as_of=...)`（`include` 与 `fields` 互斥），结果与错误均通过 `structuredContent` 返回，客户端须检查 `isError`。

#### CLI（脚本 / 自动化）

```bash
fatebridge ziwei_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 --birth-hour 10 --gender male
fatebridge knowledge_read --domain bazi --category romance --key 桃花咸池
fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json
```

全部目录命令均支持 `--request-file PATH` 读取 JSON 请求文件（命令行显式参数覆盖文件中的同名顶层字段），以及 `--include`、`--fields` 与 `--as-of`。

#### Python SDK（进程内直接调用）

```python
import fatebridge

info = fatebridge.discover(tools=["bazi_birth_chart", "firdaria"], surface="cli")
chart = fatebridge.run("firdaria", {"birth_year": 1990, "birth_month": 5, "birth_day": 15, "birth_hour": 10, "birth_timezone": "Asia/Shanghai", "birth_longitude": 116.4, "birth_latitude": 39.9, "analysis_year": 2026, "analysis_month": 6, "analysis_day": 1})
bundle = fatebridge.batch(
    [{"id": "c1", "tool": "bazi_birth_chart", "subject": "p1"}],
    subjects={"p1": {"birth_year": 1990, "birth_month": 5, "birth_day": 15, "birth_hour": 10, "gender": "男", "birth_place": "北京"}},
    as_of="2026-10-12T12:00:00+08:00",
)
```

Python SDK 与 REST、MCP、CLI 共用同一 `application/execution.py` 管道与 `default_omit` / `include` / `fields` / `as_of` 控制面。工具入参校验与批量计算错误返回统一错误包络（含 `constraints.allowed_fields` 与 `suggestions`）；`discover(...)` 及 `run(...)` 中的未知工具名或无效交付参数（`include` / `fields` / 非映射 `arguments`）直接抛出 `ParameterError`（可通过 `.as_result()` 与 `.issues` 读取同构错误包络）。

## 输出控制与结果读取

### 默认核心层与增量展开：`default_omit` 与 `include`

- 默认（不传 `include` 与 `fields`）：返回完整核心层业务字段；仅对配置了 `default_omit` 的工具省略真实存在的可选重型次级块，并将实际被省略的路径列表记录在 `run_metadata.omitted_fields`（无省略时不输出）。
- `include` 增量展开：在核心层基础上按需追加指定点号路径、`evidence_views` 名称，或传入 `include=["*"]` 获取无损全量载荷（此时 `omitted_fields` 不输出）。`include` 与 `fields` 互斥，同时传入返回 `validation_error`；无效路径或视图名返回 `validation_error` 并附带 `constraints.available` 与 `suggestions`。

### 严格字段投影：`fields`

- 路径从输出根开始，支持多层点号路径（如 `bazi_birth.day_master`），针对完整规范结果执行严格投影。
- 不支持数组数字索引（传入数字索引返回 `validation_error` / `non_object_projection_path`），请先投影所属列表字段后在调用方处理。
- 始终严格校验路径：无效路径返回 `validation_error`（`issues[].code="unknown_projection_path"`、`retryable=false`），并在 `issues[].constraints.available` 列出当前层级的可用字段名。
- `run_metadata` 始终保留（使用 `fields` 投影时不输出 `omitted_fields`）。

```bash
fatebridge bazi_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 \
  --birth-hour 10 --gender male --fields bazi_birth.four_pillars bazi_birth.day_master
```

## 错误恢复与复现

### 统一错误包络与完整错误码

模型校验与计算失败均返回统一 JSON 错误包络（`error`、`error_code`、`retryable`，可选 `issues`；MCP 与 CLI 另带 `status_code`）：

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

| `error_code` | HTTP 状态 / CLI 退出 | `retryable` | 含义与处理方式 |
| --- | --- | --- | --- |
| `validation_error` | 400 / 422 · CLI `1` | `false` | 字段缺失、格式/取值非法、未知参数或无效 `fields` 路径；按 `issues[].path` 与 `constraints`（`available`、`expected` 等）修正输入 |
| `unknown_tool` | 404 · CLI `1` / `2` | `false` | 工具名不存在或未公开；读取 `issues[].constraints.suggestions` 修正工具名 |
| `authentication_required` | 401 · — | `false` | REST 启用了 `FATEBRIDGE_API_KEYS` 但请求头缺少或携带无效 API Key |
| `consultation_restricted` | 422 · CLI `1` | `false` | 命中禁区（生死寿命、灾祸断言、临床诊断治疗、医疗择时）；停止对应计算并遵守[硬边界](interpretation/shared/safety-boundaries.md) |
| `dependency_missing` | 503 · CLI `1` | `false` | 缺少必需运行时依赖（如 `swisseph`），需检查部署环境 |
| `ephemeris_calculation_failed` | 503 · CLI `1` | `false` | 原生星历计算失败，检查星历环境与输入范围 |
| `ephemeris_source_inconsistent` | 503 · CLI `1` | `false` | 星历/时区/参考数据文件或配置在运行时发生不一致，先核查数据文件完整性 |
| `numerology_source_inconsistent` | 503 · CLI `1` | `false` | 河洛/参评原典对照数据内部一致性失败，需维护者排查 |
| `timeout` | 504 · CLI `1` | `true` | 计算或请求处理超时，可按原参数适度退避重试 |
| `internal_error` | 500 · CLI `1` | `true`（未捕获计算异常）/ `false` | 服务端内部未预期异常；检查日志与输入边界 |
| `usage_error` | — · CLI `2` | `false` | 仅 CLI：`--request-file` 读取失败、未知命令行 flag 或参数语法错误 |

MCP 失败返回原生 `isError=true`（使用 FastMCP Python Client 读取 `structuredContent` 时传 `raise_on_error=False`）。CLI 成功退出码为 `0`，计算/校验错误为 `1`，用法错误为 `2`；结构化输出与错误 JSON 均写往 stdout，诊断日志写往 stderr。

### `run_metadata` 与结果复现

成功响应均附带 `run_metadata`，始终包含 `run_id`、`tool_name`、`generated_at`、`engine`、`engine_is_approximate`、`effective_time`、`duration_ms`、`replay` 与 `warnings`；仅当默认或局部 `include` 响应实际省略了 `default_omit` 中真实存在的可选重型路径时，附带 `omitted_fields`（随机起卦同时在 `replay.overrides.seed` 保留当次种子）。将 `replay.overrides` 合并至原始请求并传入 `replay.as_of`（REST `?as_of=` / MCP `as_of` / CLI `--as-of`），即可在相同运行环境中复现同一计算结果。服务不持久化历史运行记录。

## Agent 接入闭环

1. **发现**：工具定义清楚时直接调用；存在缺口时调用 `discover_tools` / `GET /api/tools` / `fatebridge discover`，按 `family` 或 `q` 检索后取目标工具的 `input_schema`、`evidence_views`、`suggested_fields` 与 `default_omit`。咨询规范见[方法参考](interpretation/README.md)、[时间选择](interpretation/shared/timing-selection.md)与[硬边界](interpretation/shared/safety-boundaries.md)。
2. **调用**：仅收集所选方法必需的资料，未知生时禁止猜测或套用默认/示例。默认返回核心层（省略项记入 `run_metadata.omitted_fields`），需按需展开证据传入 `include`（路径或 `evidence_views` 名称），需严格只取子字段传入 `fields`，需无损全量结构与依据传入 `include=["*"]`。
3. **读取**：按需读取业务字段与 `status`、`coverage`、`run_metadata` 等结构化结果（`partial` 仅表示对应层缺少部分输入）。
4. **恢复**：遇到 `isError=true`、HTTP 4xx/5xx 或 CLI 非零退出码时，依 `error_code`、`issues[].path` 与 `constraints` 精确修正；仅 `retryable=true` 才按原参数重试。

## 家居风水接入

8 个 `fengshui_*` 工具共用统一响应结构，CLI 对嵌套请求优先使用 `--request-file`。主入口 `fengshui_assess` 在 `layers` 下分层返回八宅、金锁、年星、月星（含日/时紫白）与中州玄空宅盘；同时计算住宅或年/月/日/时紫白时返回九宫 `palace_overlay`，传入 `placements`（或 `analyze_layout=true`）时生成 `layout_analysis`；`coverage` 明确声明已算层与缺失项（`partial` 仅限制对应层，不会合并成单一吉凶分数）。完整工具速查、坐标系与请求示例见[家居风水参考](fengshui.md)及[现场咨询指南](interpretation/fengshui/consultation.md)。

## 相关文档

- [api-reference.md](api-reference.md)：全部 91 条 REST 路由、FastMCP 工具、共享请求族与响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：12 个 family 与 91 项计算能力覆盖及精度边界
- [fengshui.md](fengshui.md)：家居风水 8 工具速查、坐标系与可运行示例
- [troubleshooting.md](troubleshooting.md)：环境、依赖、投影与错误排错
