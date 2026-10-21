# FateBridge 开发者 / Agent 接入指南

把术数与占星计算接入应用、脚本或 AI Agent，需要按产品任务发现工具、选择调用通道，并处理响应、错误与完整结果交付。下面按这些集成任务给出调用约定和示例，便于核对每一步的输入与输出。

自然语言咨询可搭配 Onda 技能指导选法与解读；对话、界面和模型由接入应用提供，分工见[核心概念](concepts.md#计算解读与对话的分工)。

开始前请完成[安装](getting-started.md#安装)。本文的 shell 命令在已激活的环境中运行；源码环境也可统一加 `uv run --locked --extra dev` 前缀。

| 集成任务 | 入口 |
| --- | --- |
| 选择 REST、MCP 或 CLI | [按通道接入](#按通道接入) |
| 根据用户问题选择工具 | [自助发现](#自助发现别硬编码工具列表) |
| 处理失败、快照和字段投影 | [公共调用约定](#公共调用约定) |
| 保存完整 JSON 和校验散列 | [完整结果交付与同次导出](#完整结果交付与同次导出) |
| 收集出生资料和时间条件 | [出生信息](#出生信息一次说清) |
| 实现咨询 Agent 或风水集成 | [Agent 接入建议](#agent-接入建议) · [家居风水接入](#家居风水接入) |

输入、投影、快照、交付与回执的关系见[核心概念](concepts.md)。

Codex 用户可直接从 [Codex 使用指南](codex-guide.md) 开始：独立 stdio 诊断、原生 TOML/CLI 配置、虚构对话示例、结果裁剪和错误恢复。

FateBridge 的领域能力通过三条通道暴露出来：

- REST：`python -m fatebridge.api`，默认监听 `:8010`，适合 Web、后端服务或脚本调用
- FastMCP：`fatebridge-mcp`（等价写法：`python -m fatebridge.mcp_server`），供 Claude / Cursor / Codex 等 MCP host 使用
- CLI：`fatebridge <tool> ...`，适合 Agentic 流程、shell 或自动化脚本

三条通道共用 `src/fatebridge/services/tool_catalog.py` 装配的中央目录，领域声明位于 `services/catalog/`，请求字段定义于 `core/requests/`。共享领域计算和错误字段，各端仍有名称、绑定和校验阶段差异。

目前 REST 暴露 86 个工具，MCP 暴露 87 个工具；目录共有 88 条记录，其中 CLI 可执行 87 条。`astro_relative` 是嵌套 REST 请求，与 MCP 的扁平请求存在对应关系，不是所有记录都能按同名跨端调用。完整算法清单见 [algorithm-coverage.md](algorithm-coverage.md)，完整端点说明见 [api-reference.md](api-reference.md)。

## 自助发现：别硬编码工具列表

工具列表来自中央目录。按当前缺口选择发现深度，避免每次调用重复读取全量 Schema：

| 当前已有信息 | 下一步 |
| --- | --- |
| 工具已公开，输入 Schema 与用途明确 | 直接调用；解释同一结果无需重新发现或计算 |
| 知道用户场景，尚未确定主证 | 读场景路由或 family 摘要，再取选中工具契约 |
| 已确定工具，仅缺参数定义 | REST 单工具记录、CLI `describe --detail input` 或 MCP `fatebridge://tools/{tool}/input` |
| 需要更细输出字段 | 单工具完整契约；不要展开无关候选 |

场景发现使用 REST `/api/scenarios?detail=summary`、CLI `fatebridge scenarios` 或 MCP `fatebridge://scenarios`；`discover --scenario onda-shiye` 可缩小候选。替代工具组不要求全部调用，路由不是自动执行计划。场景过滤会展开已声明的共享／条件／组合依赖；`dependencies` 的条件仍约束何时使用，family 限制造成的缺项由 availability 明示。场景返回 consultation.kind/topics 和共享咨询策略：按本轮主题、任务、时间与深度选依据，追问复用相关视角，禁区请求在调用前停止。

咨询组织见[技能分布](../skills/README.md)、[时间选择](../skills/_shared/timing-selection.md)与[硬边界](../skills/_shared/safety-boundaries.md)。公共接口拒绝已知明确的生死／临床请求，卜卦不公开 death/health/pregnancy，择时不公开 surgery。文本拦截不能替代调用方的跨轮语义判断。

### REST：`GET /api/tools`

```bash
curl http://localhost:8010/api/tools
# 推荐先筛选摘要，再按工具取完整 Schema
curl 'http://localhost:8010/api/tools?detail=summary&family=bazi'
curl 'http://localhost:8010/api/tools?tool=bazi_birth&detail=full'
```

返回示例（节选）：

```json
{
  "counts": {"rest": 86, "mcp": 87, "total": 88},
  "tools": [
    {
      "tool": "bazi_wealth",
      "summary": "八字财运分析：已按出生资料与分析日期自动推算大运、流年和时机依据；首轮无需先调用 timing_analysis 或手动传大运柱。仅有明确外部口径时用 dayun_pillar / liunian_pillar 覆盖。",
      "operation_label_zh": "八字财运分析",
      "family": "bazi",
      "surfaces": {"cli": true, "cli_name": "bazi_wealth", "rest_path": "/api/cn/bazi/wealth", "mcp_name": "bazi_wealth"},
      "parameters": [
        {"name": "birth_year", "type": "int", "required": true, "description": "..."}
      ]
    }
  ]
}
```

如果某个工具不在某一端暴露，`surfaces.rest_path` 或 `surfaces.mcp_name` 会返回 `null`。`parameters` 是参数摘要，完整记录有 `input_schema` / `output_schema`；摘要省略这三项。可用 `family`（逗号分隔）、`q`、`tool`、`surface` 筛选，`matched_count` 为实际返回数量，`counts` 仍为全局数量。MCP 的实际输入 Schema 另包含传输开关，由 `tools/list` 发布。

### CLI：`list` 和 `describe`

```bash
fatebridge list                 # 列出所有工具，一行一个
fatebridge describe bazi_wealth # 输出单个工具的参数 schema、接口和示例（JSON）
fatebridge discover --family bazi # 与 REST 同源的分类摘要 JSON
fatebridge discover --tool bazi_birth --detail full
fatebridge list --family astro --json # 文本 list 可按需改为 JSON 摘要
```

`describe` 的输出比 REST 多一个 `cli_example` 字段，可以直接复制运行。

`cli_example` 仅在提供了经过模型校验的虚构示例时返回；`cli_usage` 是需要替换占位符的语法模板。可用 `describe <tool> --detail input` 暂时省略输出 Schema。目录 key 和公开名称均可用于发现与 CLI，正式名称见 `surfaces.cli_name` / `mcp_name`。

### FastMCP

MCP 默认通过标准 `tools/list` 公开全部工具。host 可设置 `FATEBRIDGE_MCP_FAMILIES=bazi,knowledge` 只注册所需分类，拼错分类会在启动时失败。通过 `resources/read` 读取 `fatebridge://catalog/summary`、`fatebridge://families/bazi` 和 `fatebridge://tools/bazi_birth`，可获得当前公开集合的摘要及单工具完整契约。资源错误属于资源协议错误，工具失败仍使用 `isError`。

首次取数优先查看当前工具的 `evidence_views`，按本轮任务或盘型复制其 `fields`；视图名称不是请求参数。先选好主证再调用，可避免摘要投影丢掉所需字段后另算。完整文件或全部时间线请求仍首次 `fields=null`。

`FATEBRIDGE_MCP_SCENARIOS` 可按场景及其显式依赖筛选，与 family 配置取交集；隐藏工具不可调用，场景 `availability` 明示缺口。配置与发现参数见 [渐进发现](api-reference.md#27-渐进发现与执行提示)。

## 公共调用约定

### 统一错误包络

已知工具的模型校验与业务计算错误共享顶层 `error`、`error_code`、`retryable`，CLI 错误可额外包含 `status_code`。模型校验提供 `issues` 中的字段路径、错误代码和可选约束，不回显原始输入。分支判断请用 `error_code`，不要依赖 `error` 文案：

```json
{
  "error": "无效的八字分析参数",
  "error_code": "validation_error",
  "retryable": false
}
```

`error_code` 目前有以下几种：

- `validation_error`：领域计算参数错误返回 400；模型字段缺失、类型/范围/枚举错误、未知字段、完整公历日期无效返回 422；REST 非法 JSON 也返回 422
- `authentication_required`：缺少或无效 API key（仅在配置了密钥时），REST 返回 401
- `dependency_missing`：运行依赖缺失（例如西占 backend 不可用），REST 返回 503
- `internal_error`：服务内部异常，REST 返回 500
- `timeout`：计算超时，REST 返回 504；是否重试以 `retryable` 为准

MCP 模型/业务失败使用原生 `isError=true`。FastMCP 客户端默认抛出 `ToolError`；需要恢复提示时使用 `raise_on_error=False` 并读取 `structured_content`。未知工具、非法 RPC 等协议错误仍需单独处理。CLI 用退出码判定：0 成功，1 计算/模型校验失败，2 用法错误或不支持（包括未知 flag 和 argparse 类型错误）；工具结果及错误写 stdout，日志写 stderr，`list` / `--help` 返回文本。

不要依赖拼错的字段或主题被忽略：未知字段和非法主题现在会失败，省略可选字段仍使用声明默认值。输出 Schema 覆盖根字段与稳定的专业嵌套事实，包括主限命中、递归子限、宫位与星曜条目、九类八字专题、宿曜双向关系，以及知识来源/覆盖信息和导出设置/分段；动态键及未声明扩展保留。业务字段可选且可空，消费时检查存在性；投影支持对象路径，数组仍整字段选择。先按 `isError` / HTTP 状态 / CLI 退出码判定成功，再按输出 Schema 消费业务数据。需要专业字段时用 `describe` / 单工具资源读取合同；完整 MCP schema 的体积更大，场景 profile 与摘要发现仍是分步发现入口。

### `run_metadata` 溯源层

保存原始请求与完整 receipt，将 `replay.overrides` 合并至原输入，使用 `replay.as_of` 作为 REST 查询 / MCP as_of / CLI --as-of，核对输入与业务输出摘要。随机六爻必须采用本次 seed；仅工具名或 run_id 无法重放。跨工具使用同一 trace_id，parent_run_id 引用前次 run_id；CLI profile 自动建立根/子关联。详见 [API 复现契约](api-reference.md#28-确定性与复现元数据)。

成功的工具响应默认带上 `run_metadata`（错误和发现接口不保证附带；CLI 可用 `--no-metadata` 关闭）：

```json
{
  "run_metadata": {
    "run_id": "f5c3...",
    "trace_id": "5f17...",
    "tool_name": "qimen",
    "generated_at": "2026-04-13T08:00:00Z",
    "engine": "fatebridge-offline",
    "engine_is_approximate": false
  }
}
```

### 快照协议：`snapshot_text` + `snapshot_export`

很多工具返回统一的“可读文本 + 可筛选导出”双层结构：

```json
{
  "snapshot_text": "[起盘信息]\n...",
  "snapshot_export": {
    "technique": {"key": "qimen"},
    "selected_sections": ["起盘信息", "九宫方盘"],
    "section_titles_detected": ["起盘信息", "九宫方盘", "离九宫"],
    "export_text": "[起盘信息]\n..."
  }
}
```

- `snapshot_text` 是完整的人读文本，适合日志或直接展示。
- `snapshot_export.export_text` 是按 `selected_sections` 过滤后的导出文本。
- `selected_sections` 只裁剪导出层，不会裁掉完整的结构化 payload。
- 如果 section 名没生效，先看 `section_titles_detected` 或 `missing_selected_sections`。显式非空选择没有命中时，`export_text` 为空，不会回退全文。
- `selected_sections` 并非所有模型都支持，尤其八字九大专项没有此字段；它们仍返回快照，可用 `fields` 或 `include_snapshot_text` 控制体积。
- 梅花、中点盘与西占推运总览不返回双层快照；部分占法、事件和生命周期只有文本，详见 [快照覆盖](algorithm-coverage.md#4-快照协议覆盖)。

### 字段投影：控制 token 预算

三端都支持把响应裁剪到指定字段：

- CLI：`--fields KEY [KEY ...]`
- FastMCP：工具参数 `fields: [...]`
- REST：查询参数 `?fields=wealth_analysis&fields=analysis_type`，每个字段重复一次 `fields`

支持顶层 key（如 `wealth_analysis`）和对象点路径（如 `bazi_birth.day_master`）；数组选择整个字段。已附带的 `run_metadata` 完整保留；错误响应不会被裁剪。无效路径默认保留兼容形状，并附 `projection_warnings`。需要确保路径全部有效时，REST / MCP 设置 `strict_fields=true`，CLI 用 `--strict-fields`；失败为 422 / MCP isError / CLI 退出 1，按 `issues` 修正路径。

REST 可用 `?include_snapshot_text=false`，MCP 用 `include_snapshot_text=false`，CLI 用 `--no-include-snapshot-text` 去掉顶层快照文本；若还保留 `snapshot_export`，其中导出文本仍存在。MCP 的 `compact=true` 为默认值，CLI 用 `--compact` 输出单行 JSON。

```bash
# 只取需要的顶层字段
fatebridge bazi_wealth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male --fields analysis_type wealth_analysis

# 点号子路径：从大块 payload 里只抽某个标量
fatebridge bazi_birth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male --fields snapshot_text bazi_birth.day_master
```

## 完整结果交付与同次导出

MCP 默认 `response_char_limit=8192`，REST / CLI 默认 `0`（不限制）。成功结果超出非零预算时，响应包含 `result_delivery`，保留完整回执及预算内的业务字段；剩余字段从同一 run 的交付物读取，不重新计算。允许的预算为 `0` 或 `4096–65536`，错误响应不按业务字段裁剪。

需要完整 JSON、全部时间线或完整文件时，**首次调用 `fields=null`**；REST / CLI 不传字段筛选。需要完整快照时保留默认 `include_snapshot_text=true`，也不要用 `selected_sections` 缩小导出文本。保留默认预算即可。交付物保存的是投影和快照选项处理后的结果，摘要调用的文件无法恢复未选字段。

MCP 读取顺序：

1. 读取 `result_delivery.manifest_uri`，确认结果范围、大小、SHA-256 和有效期。
2. 全量读取从 `first_page_uri` 开始；每页资源内容是 JSON 包装，解析后提取其 `text`，依次跟随 `next_uri`（或 `next_offset`），直到下一页为 null。单页 `text` 至多 2048 字符，可能从 JSON 字符串中间截开，不能逐页当成完整业务 JSON 解析。
3. 将全部 `text` 按序直接拼接，以 UTF-8 编码核对 `result_delivery.sha256`，通过后再解析全文或保存。只需解释某一字段时可使用 `fatebridge://results/{result_id}/fields/{path}/{offset}`；该读取支持数组数字索引，与计算时的 `fields` 投影规则不同。

同机程序可直接读取返回的 `file_path`，取 `file_payload_path`（当前为 `payload`）指向的业务对象。例如先保存一次使用虚构资料的 CLI 响应：

```bash
fatebridge bazi_career --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京 \
  --birth-longitude 116.4074 --birth-timezone Asia/Shanghai \
  --as-of '2026-10-15T12:00:00+08:00' --response-char-limit 8192 --compact > reply.json
```

下面将 `reply.json` 导出为 `full-result.json`，同时处理未超限的普通响应：

```python
import hashlib
import json
from pathlib import Path

reply = json.loads(Path("reply.json").read_text(encoding="utf-8"))
if "error" in reply:
    raise RuntimeError(reply)
delivery = reply.get("result_delivery")
if delivery:
    record = json.loads(Path(delivery["file_path"]).read_text(encoding="utf-8"))
    payload = record[delivery["file_payload_path"]]
else:
    payload = reply
raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
if delivery and hashlib.sha256(raw).hexdigest() != delivery["sha256"]:
    raise ValueError("完整结果 SHA-256 不匹配")
Path("full-result.json").write_bytes(raw)
```

散列对象是保留的完整响应，包括其中的 `run_metadata`，不是外层临时记录文件或缩略响应。HTTP 客户端使用 `GET /api/results/{result_id}` 和 `/api/results/{result_id}/pages?offset=0`；选择字段时另加 `path` 查询参数，鉴权与业务接口一致。

引用约一小时过期，也可能因容量回收提前失效；长期留存须及时保存完整结果及原输入。`file_path` 指向运行 FateBridge 的机器，远程客户端应读取资源或 HTTP 分页。引用失效或字段未被首轮保留时，应说明本次交付范围，不能把新一次计算冒充旧结果。`parent_run_id` 仅关联调用，不自动继承输入事实。

## 出生信息：一次说清

绝大多数命理 / 占星工具共享出生信息字段（详见 [api-reference.md](api-reference.md) §3）。最少需要 `birth_year/month/day/hour`，其余可选：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必需，出生日期与时刻
- `birth_minute`：可选，默认 0
- `gender`：八字专项可选但建议传入；`dayun_analysis` 等工具要求必填，支持 `男` / `女`、`male` / `female` 等写法
- `birth_place`：可选，中文 / 英文 / 拼音地名；内置静态近似，不是联网地理编码
- `birth_timezone`：可选，IANA 时区或 UTC offset
- `birth_longitude` / `birth_latitude`：视工具而定，占星盘建议显式传入以保证精度
- `use_true_solar_time`：中式出生信息模型默认 true，核心星盘默认 false；具体以当前工具模型为准。中式模型缺省开启但没有可解析经度时使用钟表时间并附提示；显式 true 且没有经度会报错，显式 false 使用钟表时间

出生输入由 `fatebridge.utils.birth_input` 构造，真太阳时归一化由 `fatebridge.utils.solar_time` 处理，地点与时区解析分别由 `utils.places`、`utils.timezones` 提供。结果会回显在 `person_info.time_adjustment`。需要高精度占星盘时，优先显式传经纬度和 IANA 时区；地点/经度推断不包含完整历史夏令时信息。小时是必填项，当前没有可省略小时的“无时盘”入口。

## 按通道接入

### REST（HTTP）

先按[快速入门](getting-started.md#启动-rest-并检查状态)启动服务。业务输入放在 JSON 请求体，`fields`、`strict_fields`、`as_of` 等通用控制项放在 URL 查询参数。以下示例假设已开启密钥鉴权；未开启时可省略密钥头。

```bash
curl -X POST 'http://localhost:8010/api/cn/bazi/wealth?fields=wealth_analysis&strict_fields=true&include_snapshot_text=false' \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-me" \
  -d '{"gender":"男","birth_year":1990,"birth_month":5,"birth_day":15,
       "birth_hour":10,"birth_timezone":"Asia/Shanghai","birth_place":"北京","use_true_solar_time":true}'
```

如果配置了 `FATEBRIDGE_API_KEYS`，除 `/health`、`/ready`、`/metrics` 和文档页外，其余端点都需要带 `X-API-Key`。

**Python（requests）示例：** 示例客户端需先安装 `requests`，它不是 FateBridge 的直接依赖。

```python
import requests

resp = requests.post(
    "http://localhost:8010/api/cn/bazi/wealth",
    headers={"X-API-Key": "replace-me"},
    params={
        "fields": ["wealth_analysis"],
        "strict_fields": "true",
        "include_snapshot_text": "false",
    },
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

**JavaScript（fetch）示例：**

```js
const url = new URL("http://localhost:8010/api/cn/bazi/wealth");
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

安装、客户端配置、Windows、HTTP 运行、远程接入与升级见 [MCP 部署指南](mcp-deployment.md)。本节解释本地 stdio 的基础配置及协议合同。

启动：

```bash
fatebridge-mcp
# 等价于 python -m fatebridge.mcp_server
```

将 stdio 进程注册到支持 `mcpServers` 配置的 MCP host（以下是结构示例，路径需替换为实际安装目录）：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "/absolute/path/to/FateBridge/.venv/bin/python",
      "args": ["-m", "fatebridge.mcp_server"]
    }
  }
}
```

也可直接使用安装后的脚本，GUI host 同样建议使用绝对路径：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "/absolute/path/to/FateBridge/.venv/bin/fatebridge-mcp"
    }
  }
}
```

几个注意点：

- 默认使用 stdio，由 host 启动子进程；手工启动不会创建 HTTP MCP 地址。
- 使用已安装 FateBridge 的解释器绝对路径，避免 GUI host 继承不到虚拟环境。Windows 使用 `.venv\Scripts\python.exe`。
- MCP 工具同时返回 `structuredContent` JSON 对象与兼容的 text JSON；优先读取结构化对象，旧客户端仍可 parse text。
- 输入和执行失败返回 `isError=true`，内容带 `error_code`。使用 FastMCP Client 读取错误详情时设置 `raise_on_error=False`；默认会抛出 ToolError。
- 每个工具公布 `outputSchema`。业务字段允许缺省以支持 `fields` 投影；缺省不代表值为 null。根字段、核心命盘/择日、专业长尾事实及知识/导出嵌套字段有类型，动态键与未声明扩展保留。
- 用 `fields` 参数控制返回体积。
- 工具 annotations 和三端发现记录同源，描述本地只读计算/查询；`idempotentHint` 不表示随机、时间默认值或运行 ID 会重复产生相同输出。

### CLI（脚本 / 自动化）

单次调用无需启动 REST 或 MCP 服务。先用 `describe` 核对所选工具的输入，再运行它；进程退出码决定是否继续读取业务结果。

```bash
fatebridge list
fatebridge describe ziwei_birth
fatebridge ziwei_birth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male
fatebridge knowledge_read --domain bazi --category romance --key 桃花咸池
```

CLI 子命令与参数同样从中央目录派生，`--help` 可查每个工具的参数。

`--subject-file /path/to/person.json` 可复用扁平出生字段（`name`、`gender`、`birth_*` 等），显式命令参数优先。JSON 使用标准库；YAML 档案需要 PyYAML（包含在 dev 依赖中）。不要将含真实出生资料的档案直接提交仓库。

CLI 专有 `profile` 可为同一命主组织多套盘，默认 `bazi,ziwei,astro`；逐项结果在 `profile` 下，任一失败会使退出码为 1，其他结果仍返回：

```bash
fatebridge profile --systems bazi,ziwei,astro \
  --birth-year 1990 --birth-month 5 --birth-day 15 --birth-hour 10 \
  --gender 男 --birth-place 北京 --birth-timezone Asia/Shanghai \
  --birth-longitude 116.40 --birth-latitude 39.90
```

`profile` 保留各体系默认太阳时策略，不是全工具并行运行。支持 `--fields profile.bazi.bazi_birth.day_master`、`--strict-fields`、`--compact` 与 `--no-include-snapshot-text`；后者移除各子结果顶层快照。投影保留已选子结果的运行凭据和所有失败项，任一体系失败仍退出 1。按实际工具去重，空体系列表会失败；选项以 `profile --help` 为准。

## Agent 接入建议

面向人的咨询流程与接口发现是不同层次：技能决定本轮问题、解释方式及边界，Schema 决定能提交哪些参数。接入后用一条完整的虚构对话验证采集、调用、解释及追问；仅连接成功不能验证这些行为。

1. 发现：已知 Schema 且工具公开时直接调用；有缺口时按场景 / family 获取摘要或单工具契约。
2. 路由：按用户意图选 family，例如八字走 `bazi`、运势走 `timing`、星盘走 `astro`、术数走 `metaphysics` / `divination`。场景级取舍（谁主谁次、怎么省 token、怎么避免结论打架）见 [scenario-routing.md](scenario-routing.md)。
3. 取数：只核对所选计算真正需要的资料；出生时刻未知时不能猜。复现时保存时区、坐标来源、太阳时策略和分析日期。
4. 裁剪：摘要用严格 `fields` 与快照开关；完整导出首次保留全文，`selected_sections` 仅控制所支持工具的导出文本。
5. 判错：始终基于 `error_code` 分支；`dependency_missing` 说明环境缺西占 backend，不是入参问题。
6. 溯源：保存原输入、run_metadata、replay overrides 与精度字段；固定 as_of 和环境后重新调用可核对业务结果。服务不按 run_id 查询或自动重放历史。

## 家居风水接入

七个 `fengshui_*` 工具由同一目录发布 REST、MCP 和 CLI。独立命卦／年盘可用简单字段，组合住宅请求使用 JSON；CLI 提供 `--request-file`，文件里的未知字段也会校验。`layers` 保留八宅宅盘／逐人命盘、砂水观察和年度盘；每层带版本与来源，`coverage` 区分缺失、未请求和未实现层。`partial` 是可用的部分结果，不能按计算失败重试；也不能把候选命卦或三层叠加改写成一个总分。复制调用示例见 [家居风水](fengshui.md)。

问布局是否要改时使用通用 `fengshui_assess` 并设 `analyze_layout=true`，将已确认对象位置／朝向放入 `placements`。只知道朝向可省略位置并取部分计算；不得把朝向替代落宫。`layout_analysis` 返回跨层位置关联、按作用域反算的匹配方位、砂水调整分类与五行关系；其状态与原始盘分开。命卦可传 `birth_date`，非立春当日不强制出生时刻。所有风水工具描述均提供首轮字段；已知合同直接调用，缺定义时按工具名检索一次。

室内入口可见性、直线、实体背靠使用 `form_observations`，可 `methods=[]` 独立算，不先索取生辰/宅向。照片仅作待确认假设，1.5米等数字不套吉凶阈值。问物件时用 `element_adjustments` 绑定实际计算目标与作用域；作者代表物只作为有条件选项，不推缺五行或要求购物。年度方案显式选 `pang_2026_annual_v1`，只覆盖2026年南5/西北2，不外推年份。物件方案还应解释 `cross_scope_effects` 和作者分歧，不能宣称一件物品对所有层都有利。完整峦头、距离阈值、物件效果大小保持未实现。

玄空宅盘须显式调用 `fengshui_xuankong_natal` 或合参选择 `xuankong_natal`。宅盘按历史资料定运并记录事件依据、版本及来源，年度 `current_period` 不能当作宅运。兼向按本版本中州派规则，角度分界候选保持 `partial`，不自行裁成唯一盘。输入例子与独立验证见 [玄空宅盘](fengshui-xuankong.md)。

## 相关文档

- [api-reference.md](api-reference.md)：全部 REST 路由、FastMCP 工具、请求族、响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：13 family / 87 工具的算法与精度 / 依赖矩阵
- [scenario-routing.md](scenario-routing.md)：场景到工具的路由矩阵、调用纪律、交叉印证与去重策略
- [getting-started.md](getting-started.md)：从零启动服务
- [troubleshooting.md](troubleshooting.md)：依赖缺失、精度、快照导出等常见问题
