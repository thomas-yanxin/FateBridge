# FateBridge 开发者 / Agent 接入指南

一次能跑通的调用，只是接入的开始。应用还要选对工具，知道输入从哪里来，分清计算失败与部分结果，并在需要时交付同一次运行的完整输出。本文按这些任务组织调用约定和示例，帮助开发者逐步核对输入、响应与交付。

FateBridge 提供计算能力，自然语言咨询由接入方根据实际工具合同选择方法并解释结果。对话、界面和模型仍由接入应用提供，具体分工见[核心概念](concepts.md#计算解读与对话的分工)。

开始前请完成[安装](getting-started.md#安装)。本文的 shell 命令在已激活的环境中运行；源码环境也可统一加 `uv run --locked --extra dev` 前缀。

| 集成任务 | 入口 |
| --- | --- |
| 选择 REST、MCP 或 CLI | [按通道接入](#按通道接入) |
| 根据用户问题选择工具 | [自助发现](#自助发现别硬编码工具列表) |
| 处理失败、快照和字段投影 | [公共调用约定](#公共调用约定) |
| 保存与核验完整 JSON | [完整结果交付与同次导出](#完整结果交付与同次导出) |
| 收集出生资料和时间条件 | [出生信息](#出生信息一次说清) |
| 实现咨询 Agent 或风水集成 | [Agent 接入建议](#agent-接入建议) · [家居风水接入](#家居风水接入) |

输入、投影、快照、交付与回执的关系见[核心概念](concepts.md)。

Codex 用户可直接从 [Codex 使用指南](codex-guide.md) 开始：独立 stdio 诊断、原生 TOML/CLI 配置、虚构对话示例、结果裁剪和错误恢复。

FateBridge 的领域能力通过三条通道暴露出来：

- REST：`python -m fatebridge.api`，默认监听 `:8010`，适合 Web、后端服务或脚本调用
- FastMCP：`fatebridge-mcp`（等价写法：`python -m fatebridge.mcp_server`），供 Claude / Cursor / Codex 等 MCP host 使用
- CLI：`fatebridge <tool> ...`，适合 Agentic 流程、shell 或自动化脚本

三条通道共用 `src/fatebridge/services/tool_catalog.py` 装配的中央目录，领域声明位于 `services/catalog/`，请求字段定义于 `core/requests/`。共享领域计算和错误字段，各端仍有名称、绑定和校验阶段差异。

目录共有 93 条记录，REST 公开 93 个工具，CLI 可执行 93 条。MCP 通过四个入口提供 93 项业务能力。三端共用工具名和请求字段。完整算法清单见 [algorithm-coverage.md](algorithm-coverage.md)，完整端点说明见 [api-reference.md](api-reference.md)。

## 自助发现：别硬编码工具列表

工具列表来自中央目录。先看当前缺什么，再决定发现到哪一层：已知的合同不必反复查询，不确定的参数则要在调用前核对。

| 当前已有信息 | 下一步 |
| --- | --- |
| 工具已公开，输入 Schema 与用途明确 | 直接调用；解释同一结果无需重新发现或计算 |
| 知道用户场景，尚未确定主证 | 读实际工具说明或 family 摘要，再取选中工具契约 |
| 已确定工具，仅缺参数定义 | REST 单工具记录、CLI `describe --detail input` 或 MCP `fatebridge://tools/{tool}/input` |
| 需要更细输出字段 | 单工具完整契约；不要展开无关候选 |

工具发现使用 REST `/api/tools`、CLI `fatebridge discover` 或 MCP `fatebridge://catalog/summary`。先按实际工具说明、family 或关键词缩小范围，再读取所选工具的合同；未返回的工具不能据此判断为引擎不支持。调用与解释按当前问题及已确认资料决定，不使用固定主题清单。

咨询组织见[方法参考](interpretation/README.md)、[时间选择](interpretation/shared/timing-selection.md)与[硬边界](interpretation/shared/safety-boundaries.md)。公共接口拒绝已知明确的生死／临床请求，卜卦不公开 death/health/pregnancy，择时不公开 surgery。文本拦截不能替代调用方的跨轮语义判断。

### REST：`GET /api/tools`

```bash
curl http://localhost:8010/api/tools
# 推荐先筛选摘要，再按工具取完整 Schema
curl 'http://localhost:8010/api/tools?detail=summary&family=bazi'
curl 'http://localhost:8010/api/tools?tool=bazi_birth_chart&detail=full'
```

返回示例（节选）：

```json
{
  "counts": {"rest": 91, "mcp": 92, "total": 93},
  "tools": [
    {
      "tool": "bazi_wealth",
      "summary": "八字财运分析：已按出生资料与分析日期自动推算大运、流年和时机依据；首轮无需先调用 bazi_timing 或手动传大运柱。仅有明确外部口径时用 dayun_pillar / liunian_pillar 覆盖。",
      "operation_label_zh": "八字财运分析",
      "family": "bazi",
      "surfaces": {"cli": true, "cli_name": "bazi_wealth", "rest_path": "/api/bazi/wealth", "mcp_name": "bazi_wealth"},
      "parameters": [
        {"name": "birth_year", "type": "int", "required": true, "description": "..."}
      ]
    }
  ]
}
```

如果某项能力未在某一端公开，对应的 `surfaces.rest_path` 或 `surfaces.mcp_name` 为 `null`。`parameters` 是参数摘要，`detail=full` 还提供 `input_schema` 和 `output_schema`。可按 `family`（逗号分隔）、`q`、`tool`、`surface` 筛选，`matched_count` 是实际返回数量，`counts` 是全局数量。MCP 的 `tools/list` 发布四个协议工具及其参数。业务参数的 Schema 通过 `describe_capability` 按需读取。

### CLI：`list` 和 `describe`

```bash
fatebridge list                 # 列出所有工具，一行一个
fatebridge describe bazi_wealth # 输出单个工具的参数 schema、接口和示例（JSON）
fatebridge discover --family bazi # 与 REST 同源的分类摘要 JSON
fatebridge discover --tool bazi_birth_chart --detail full
fatebridge list --family astro # 筛选文本列表
```

`describe` 的输出比 REST 多一个 `cli_example` 字段，可以直接复制运行。

`cli_example` 仅在提供了经过模型校验的虚构示例时返回；`cli_usage` 是需要替换占位符的语法模板。可用 `describe <tool> --detail input` 暂时省略输出 Schema。发现和调用使用公开名称，见 `surfaces.cli_name` / `mcp_name`。

### FastMCP

MCP 公开 `discover_capabilities`、`describe_capability`、`run_calculation` 和 `read_result`。已知能力和参数时可用 `run_calculation` 直接执行。需要参数时用 `describe_capability` 查看该项。也可读取 `fatebridge://catalog/summary`、`fatebridge://families/bazi` 和 `fatebridge://tools/bazi_birth_chart` 等资源。

`run_calculation` 默认选取推荐核心字段并省略快照正文。主题需要特定证据时，按 `evidence_views` 提供 `fields`。完整文件、全部时间线及计算审计首次使用 `detail="audit"` 和 `fields=null`，按回执读取同一次运行。

`compact` 回执保留运行标识、有效时刻、重放参数和实际降级状态。需要运行环境时，可选取 `run_metadata.runtime`。`standard` 附常规运行环境，`audit` 另提供本次启用的方法和声明误差预算。规则和操作数见各工具的业务字段。

`FATEBRIDGE_MCP_FAMILIES` 限制可执行的能力。用 `discover_capabilities` 或目录资源核对当前公开范围，配置见[部署指南](mcp-deployment.md#工具筛选与运行环境)。

## 公共调用约定

### 统一错误包络

已知工具的模型校验与业务计算错误共享顶层 `error`、`error_code`、`retryable`，MCP 和 CLI 错误可额外包含 `status_code`。以下响应指向超出范围的出生月份。

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

按 `error_code` 和 `issues[].code` 分支。用 `issues[].path` 找到参数，结合 `issues[].message`、`constraints` 和顶层 `error` 修正后再提交。缺少事实时向用户核对。只有 `retryable=true` 才考虑原参数重试。

`error_code` 目前有以下几种：

- `validation_error`：模型校验或领域输入被拒绝时返回 400 或 422。REST 的 JSON 语法错误返回 422
- `authentication_required`：缺少或无效 API key（仅在配置了密钥时），REST 返回 401
- `dependency_missing`：运行依赖缺失（例如西占 backend 不可用），REST 返回 503
- `fengshui_calculation_inconsistent`：玄空内部数字或飞行记录矛盾，REST返回503且不可重试；停止解释，不用修改用户事实或挑选其余候选绕过，见[异常盘处理](fengshui-xuankong.md)
- `internal_error`：服务内部异常，REST 返回 500
- `timeout`：计算超时，REST 返回 504；是否重试以 `retryable` 为准

MCP 模型/业务失败使用原生 `isError=true`。FastMCP 客户端默认抛出 `ToolError`；需要恢复提示时使用 `raise_on_error=False` 并读取 `structured_content`。未知工具、非法 RPC 等协议错误仍需单独处理。CLI 用退出码判定：0 成功，1 计算/模型校验失败，2 用法错误或不支持（包括未知 flag 和 argparse 类型错误）；工具结果及错误写 stdout，日志写 stderr，`list` / `--help` 返回文本。

不要依赖拼错的字段或主题被忽略：未知字段和非法主题现在会失败，省略可选字段仍使用声明默认值。输出 Schema 覆盖根字段与稳定的专业嵌套事实，包括主限命中、递归子限、宫位与星曜条目、九类八字专题、宿曜双向关系，以及知识来源/覆盖信息和导出设置/分段；动态键及未声明扩展保留。业务字段可选且可空，消费时检查存在性；投影支持对象路径，数组仍整字段选择。先按 `isError` / HTTP 状态 / CLI 退出码判定成功，再按输出 Schema 消费业务数据。需要专业字段时用 `describe` / 单工具资源读取合同；完整 MCP schema 的体积更大，family 摘要与单工具契约用于分步发现。

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

很多工具同时返回可读文本和可筛选导出。两者服务不同用途：快速阅读可以使用前者，按章节导出可以使用后者。

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
fatebridge bazi_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male --fields snapshot_text bazi_birth.day_master
```

## 完整结果交付与同次导出

MCP 默认 `response_char_limit=8192`，REST / CLI 默认 `0`（不限制）。成功结果超出非零预算时，响应包含 `result_delivery`，保留运行标识及预算内的业务字段；剩余字段从同一 run 的交付物读取，不重新计算。允许的预算为 `0` 或 `4096–65536`，错误响应不按业务字段裁剪。

行内响应可能保留全部业务字段，也可能只保留一部分。先查看 `result_delivery.deferred_fields`，再读取所需内容：

| 响应情况 | 下一步 |
| --- | --- |
| 业务字段完整，部分 `run_metadata` 延后 | 按 `delivery_path` 读取运行证据 |
| 业务字段也已延后 | 从清单读取所需字段或完整分页，再解释这些内容 |
| `compact_reference=true` | 引用省略了部分重复定位信息，从 `manifest_uri` 取得完整清单 |

以上均读取原 run，不重新计算。预算、回执保留顺序和引用字段约定见[API 参考](api-reference.md#25-字段投影与输出体积)。

需要完整 JSON、全部时间线或完整文件时，**首次调用用 `detail=audit` 和 `fields=null`**。REST / CLI 省略字段筛选。需要完整快照时可显式设置 `include_snapshot_text=true` 并省略 `selected_sections`。交付物保存当前结果级别、字段投影和快照选项处理后的结果。

MCP 读取顺序：

1. 读取 `result_delivery.manifest_uri`，确认结果范围、大小和有效期。
2. 全量读取从清单中的 `first_page_uri` 开始；每页资源内容是 JSON 包装，解析后提取其 `text`，依次跟随 `next_uri`（或 `next_offset`），直到下一页为 null。单页 `text` 至多 2048 字符，可能从 JSON 字符串中间截开，不能逐页当成完整业务 JSON 解析。
3. 将全部 `text` 按序直接拼接，再解析全文或保存；需要核验时使用下述同 run 读取接口。只需解释某一字段时可使用 `fatebridge://results/{result_id}/fields/{path}/{offset}`；该读取支持数组数字索引，与计算时的 `fields` 投影规则不同。

同机程序可直接读取返回的 `file_path`，取 `file_payload_path`（当前为 `payload`）指向的业务对象。例如先保存一次使用虚构资料的 CLI 响应：

```bash
fatebridge bazi_career --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 --birth-place 北京 \
  --birth-longitude 116.4074 --birth-timezone Asia/Shanghai \
  --as-of '2026-10-15T12:00:00+08:00' --response-char-limit 8192 --compact > reply.json
```

下面在安装FateBridge的同一Python环境中将 `reply.json` 导出为 `full-result.json`，同时处理未超限的普通响应；精简引用省略文件定位时只查询本机清单，不重新计算：

```python
import json
from pathlib import Path

from fatebridge.application.result_delivery import RESULT_STORE

reply = json.loads(Path("reply.json").read_text(encoding="utf-8"))
if "error" in reply:
    raise RuntimeError(reply)
delivery = reply.get("result_delivery")
if delivery:
    locator = delivery if "file_path" in delivery else RESULT_STORE.manifest(delivery["result_id"])
    record = json.loads(Path(locator["file_path"]).read_text(encoding="utf-8"))
    payload = record[locator["file_payload_path"]]
else:
    payload = reply
raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
Path("full-result.json").write_bytes(raw)
```

HTTP 客户端从 `GET /api/results/{result_id}` 的 `rest_export_path` 一次下载完整保留 JSON。按需读少数字段时用 `/api/results/{result_id}/pages?offset=0&path=字段路径`。每页会读取整份 JSON，完整导出用单次读取路径。鉴权与业务接口一致。

也可以让确定性读取接口执行存储完整性与 run 校验，再取所需页。下面沿用上例的`reply.json`，读取同一结果的`analysis_context`，不重算：

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

每次调用先使用私有摘要核对完整 payload 与原 run，再从同一内存对象返回至多 2048 字符的所选文档片段。`verification.run_id`、`scope` 与 `calculation_repeated=false` 说明核验对象和范围。REST 入口为 `/api/results/{result_id}/verified`，必传 `expected_run_id`。错 run、损坏和失效会返回错误。MCP 模板见[交付合同](api-reference.md#25-字段投影与输出体积)。

`result-read`可在只读沙箱中读取已有结果，不依赖可写临时目录或锁文件。若原缓存位于自定义位置，或读写进程的临时目录环境不同，使用`--directory 原交付文件所在私有目录`；同ID匹配多个缓存目录时也须明确原目录，不能依次尝试副本来猜测原目录。过期或被并发回收的引用仍不可用，目录参数不延长保留期限。源码环境使用已有依赖环境的Python和正确的源码路径；临时评测工作目录未必包含`.venv`。

引用约一小时过期，也可因容量回收提前失效。升级单文件存储后，升级前的临时引用失效。长期留存须及时保存完整结果及原输入。`file_path` 指向运行 FateBridge 的机器。引用失效或字段未被首轮保留时，应说明本次交付范围。`parent_run_id` 用于关联调用，重算应使用已确认的原输入。

## 出生信息：一次说清

绝大多数命理 / 占星工具共享出生信息字段（详见 [api-reference.md](api-reference.md) §3）。最少需要 `birth_year/month/day/hour`，其余可选：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必需，出生日期与时刻
- `birth_minute`：可选，默认 0
- `gender`：八字专项可选但建议传入；`bazi_luck_cycles` 等工具要求必填，支持 `男` / `女`、`male` / `female` 等写法
- `birth_place`：可选，中文 / 英文 / 拼音地名；内置静态近似，不是联网地理编码
- `birth_timezone`：可选，IANA 时区或 UTC offset
- `birth_longitude` / `birth_latitude`：视工具而定，占星盘建议显式传入以保证精度
- `use_true_solar_time`：中式出生信息模型默认 true，核心星盘默认 false；具体以当前工具模型为准。中式模型缺省开启但没有可解析经度时使用钟表时间并附提示；显式 true 且没有经度会报错，显式 false 使用钟表时间

出生输入由 `fatebridge.utils.birth_input` 构造，真太阳时归一化由 `fatebridge.utils.solar_time` 处理，地点与时区解析分别由 `utils.places`、`utils.timezones` 提供。结果会回显在 `person_info.time_adjustment`。需要高精度占星盘时，优先显式传经纬度和 IANA 时区；地点/经度推断不包含完整历史夏令时信息。小时是必填项，当前没有可省略小时的“无时盘”入口。

## 按通道接入

### REST（HTTP）

先按[快速入门](getting-started.md#启动-rest-并检查状态)启动服务。业务输入放在 JSON 请求体，`fields`、`strict_fields`、`as_of` 等通用控制项放在 URL 查询参数。以下示例假设已开启密钥鉴权；未开启时可省略密钥头。

```bash
curl -X POST 'http://localhost:8010/api/bazi/wealth?fields=wealth_analysis&strict_fields=true&include_snapshot_text=false' \
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
    "http://localhost:8010/api/bazi/wealth",
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

安装、客户端配置、Windows、HTTP 运行、远程接入与升级见 [MCP 部署指南](mcp-deployment.md)。本节解释本地 stdio 的基础配置及协议合同。

客户端启动命令为 `fatebridge-mcp`，GUI host 使用实际安装环境的绝对路径。可复制的 JSON／TOML 配置统一见[本地 stdio 注册](mcp-deployment.md#注册本地-stdio)。

协议处理要点：

- 默认使用 stdio，由 host 启动子进程；手工启动不会创建 HTTP MCP 地址。
- 使用已安装 FateBridge 的解释器绝对路径，避免 GUI host 继承不到虚拟环境。Windows 使用 `.venv\Scripts\python.exe`。
- MCP 工具在 `structuredContent` 返回业务事实或结构化错误详情；失败时 `content` 带简短错误消息。
- 输入和执行失败返回 `isError=true`，内容带 `error_code`。使用 FastMCP Client 读取错误详情时设置 `raise_on_error=False`；默认会抛出 ToolError。
- 每个工具公布 `outputSchema`。业务字段允许缺省以支持 `fields` 投影；缺省不代表值为 null。根字段、核心命盘/择日、专业长尾事实及知识/导出嵌套字段有类型，动态键与未声明扩展保留。
- 用 `fields` 参数控制返回体积。
- 工具 annotations 和三端发现记录同源，描述本地只读计算/查询；`idempotentHint` 不表示随机、时间默认值或运行 ID 会重复产生相同输出。

### CLI（脚本 / 自动化）

单次调用无需启动 REST 或 MCP 服务。先用 `describe` 核对所选工具的输入，再运行它；进程退出码决定是否继续读取业务结果。

```bash
fatebridge list
fatebridge describe ziwei_birth_chart
fatebridge ziwei_birth_chart --birth-year 1990 --birth-month 6 --birth-day 15 \
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

`profile` 保留各体系默认太阳时策略。档案若明确记录 `birth_clock_basis` 为地方平太阳时或地方真太阳时，请选择支持该输入的子工具。各子工具独立校验钟制，合法子项仍会返回结果。支持 `--fields profile.bazi.bazi_birth.day_master`、`--strict-fields`、`--compact` 与 `--no-include-snapshot-text`；后者移除各子结果顶层快照。投影保留已选子结果的运行凭据和所有失败项，任一体系失败仍退出 1。按实际工具去重，空体系列表会失败；选项以 `profile --help` 为准。

## Agent 接入建议

首轮读取当前工具的 `suggested_fields`，追问时沿 `evidence_views` 补取所需事实。经典词条用 `knowledge_catalog` 查目录、用 `knowledge_read` 读取条文、版本和出处。按同次结果引用实际柱位、相位或规则条件，再结合用户确认的职责、关系和资源讨论现实问题。行业映射、心理类比和行动建议由 Agent 根据该对话生成。

接口连通后，Agent 还要完成一段面向人的对话：收集必要资料、选择工具、解释结果，再处理追问。接入方负责本轮问题、解释方式及边界，Schema 规定可以提交哪些参数。用一条完整的虚构对话验证这些环节；连接成功本身无法证明它们都能正常工作。

1. 发现：已知 Schema 且工具公开时直接调用；有缺口时按 family 或关键词获取摘要或单工具契约。
2. 路由：按用户意图选 family，例如八字走 `bazi`、运势走 `timing`、星盘走 `astro`、术数走 `metaphysics` / `divination`。具体方法的实现范围与限制见[工具覆盖](algorithm-coverage.md)。
3. 取数：只核对所选计算真正需要的资料；出生时刻未知时不能猜。复现时保存时区、坐标来源、太阳时策略和分析日期。
4. 裁剪：摘要用严格 `fields` 与快照开关；完整导出首次保留全文，`selected_sections` 仅控制所支持工具的导出文本。
5. 判错：始终基于 `error_code` 分支；`dependency_missing` 说明环境缺西占 backend，不是入参问题。
6. 溯源：保存原输入、run_metadata、replay overrides 与精度字段；固定 as_of 和环境后重新调用可核对业务结果。服务不按 run_id 查询或自动重放历史。

## 家居风水接入

八个 `fengshui_*` 工具由同一目录发布 REST、MCP 和 CLI。独立命卦／年盘可用简单字段，组合住宅请求使用 JSON；CLI 提供 `--request-file`，文件里的未知字段也会校验。`layers` 保留八宅宅盘／逐人命盘、砂水观察和年度盘；每层带版本与来源，`coverage` 区分缺失、未请求和未实现层。`partial` 是可用的部分结果，不能按计算失败重试；也不能把候选命卦或三层叠加改写成一个总分。复制调用示例见 [家居风水](fengshui.md)。

问布局是否要改时使用通用 `fengshui_assess` 并设 `analyze_layout=true`，将已确认对象位置／朝向放入 `placements`。只知道朝向可省略位置并取部分计算；不得把朝向替代落宫。`layout_analysis` 返回跨层位置关联、按作用域反算的匹配方位、砂水调整分类与五行关系；其状态与原始盘分开。命卦可传 `birth_date`，非立春当日不强制出生时刻。所有风水工具描述均提供首轮字段；已知合同直接调用，缺定义时按工具名检索一次。

室内入口可见性、直线、实体背靠使用 `form_observations`，可 `methods=[]` 独立算，不先索取生辰/宅向。照片仅作待确认假设，1.5米等数字不套吉凶阈值。问物件时用 `element_adjustments` 绑定实际计算目标与作用域；作者代表物只作为有条件选项，不推缺五行或要求购物。年度方案显式选 `pang_2026_annual_v1`，只覆盖2026年南5/西北2，不外推年份。物件方案还应解释 `cross_scope_effects` 和作者分歧，不能宣称一件物品对所有层都有利。完整峦头、距离阈值、物件效果大小保持未实现。

玄空宅盘须显式调用 `fengshui_xuankong_house_chart` 或合参选择 `xuankong_natal`。宅盘按历史资料定运并记录事件依据、版本及来源，年度 `current_period` 不能当作宅运。兼向按本版本中州派规则，角度分界候选保持 `partial`，不自行裁成唯一盘。输入例子与独立验证见 [玄空宅盘](fengshui-xuankong.md)。

## 相关文档

- [api-reference.md](api-reference.md)：全部 REST 路由、FastMCP 工具、请求族、响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：14 family / 93 工具的算法与精度 / 依赖矩阵
- [工具覆盖](algorithm-coverage.md)：各方法的实现范围、已知限制与验证边界
- [getting-started.md](getting-started.md)：从零启动服务
- [troubleshooting.md](troubleshooting.md)：依赖缺失、精度、快照导出等常见问题
