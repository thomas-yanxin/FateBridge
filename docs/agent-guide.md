# FateBridge 开发者 / Agent 接入指南

这份文档写给两类调用方：想在自己的应用或脚本里集成 FateBridge 的开发者，以及把 FateBridge 当作工具集让模型自主调用的 Agent。

Fatebridge 的领域能力通过三条通道暴露出来：

- REST：`python -m fatebridge.api`，默认监听 `:8010`，适合 Web、后端服务或脚本调用
- FastMCP：`fatebridge-mcp`（等价写法：`python -m fatebridge.mcp_server`），供 Claude / Cursor / Codex 等 MCP host 使用
- CLI：`fatebridge <tool> ...`，适合 Agentic 流程、shell 或自动化脚本

三条通道的工具集合、参数 schema 和错误形状都来自同一个地方：`src/fatebridge/services/tool_catalog.py`。所以你在一处改动，三处同时生效。

> 目前 REST 和 MCP 各暴露 80 个工具；CLI 多了几个别名（例如 `calculate_legacy`），因此 `/api/tools` 返回的 `counts.total` 会略大于 80。完整算法清单见 [algorithm-coverage.md](algorithm-coverage.md)，完整端点说明见 [api-reference.md](api-reference.md)。

---

## 自助发现：别硬编码工具列表

FateBridge 设计成可被机器自描述。Agent 不需要把本文档里的工具列表写死，启动时拉一次目录就能得到全部工具及其调用约定。

### REST：`GET /api/tools`

```bash
curl http://localhost:8010/api/tools
```

返回示例：

```json
{
  "counts": {"rest": 80, "mcp": 80, "total": 82},
  "tools": [
    {
      "tool": "bazi_wealth",
      "summary": "八字财运分析（可传 dayun_pillar / liunian_pillar 输出时机信号）",
      "operation_label_zh": "八字财运分析",
      "family": "bazi",
      "surfaces": {"cli": true, "rest_path": "/api/cn/bazi/wealth", "mcp_name": "bazi_wealth"},
      "parameters": [
        {"name": "birth_year", "type": "int", "required": true, "description": "..."}
      ]
    }
  ]
}
```

如果某个工具不在某一端暴露，`surfaces.rest_path` 或 `surfaces.mcp_name` 会返回 `null`。`parameters` 就是该工具的参数 schema，可以直接映射成你框架里的 tool / function 定义。

### CLI：`list` 和 `describe`

```bash
fatebridge list                 # 列出所有工具，一行一个
fatebridge describe bazi_wealth # 输出单个工具的参数 schema、接口和示例（JSON）
```

`describe` 的输出比 REST 多一个 `cli_example` 字段，可以直接复制运行。

### FastMCP

MCP host 连接后通过标准 `tools/list` 拿到全部工具及 input schema，无需额外配置。

> 推荐做法：Agent 启动时调用一次 `/api/tools`（或 MCP `tools/list`），把工具表按 `family` 分组缓存。之后按 `parameters` 校验入参即可。工具增删时不必再改 Agent 代码。

---

## 公共调用约定

### 统一错误包络

REST、FastMCP、CLI 三端返回的顶层错误结构一致。分支判断请用 `error_code`，不要依赖 `error` 文案：

```json
{
  "error": "无效的八字分析参数",
  "error_code": "validation_error",
  "retryable": false
}
```

`error_code` 目前有以下几种：

- `validation_error`：入参错误或日期非法，REST 返回 400
- `authentication_required`：缺少或无效 API key（仅在配置了密钥时），REST 返回 401
- `dependency_missing`：运行依赖缺失（例如西占 backend 不可用），REST 返回 503
- `internal_error`：服务内部异常，REST 返回 500

### `run_metadata` 溯源层

结构化工具响应都会带上 `run_metadata`：

```json
{
  "run_metadata": {
    "run_id": "f5c3...",
    "trace_id": "5f17...",
    "tool_name": "qimen",
    "generated_at": "2026-04-13T08:00:00Z",
    "engine": "fatebridge-offline"
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
- 如果 section 名没生效，先看 `section_titles_detected` 或 `missing_selected_sections`。

### 字段投影：控制 token 预算

三端都支持把响应裁剪到指定字段：

- CLI：`--fields KEY [KEY ...]`
- FastMCP：工具参数 `fields: [...]`
- REST：调用侧自行裁剪（REST 不内置 `fields`）

支持顶层 key（如 `wealth_analysis`）和点号子路径（如 `bazi_birth.day_master`）。`run_metadata` 始终保留以维持溯源；错误响应不会被裁剪。

```bash
# 只取需要的顶层字段
fatebridge bazi_wealth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male --fields analysis_type wealth_analysis

# 点号子路径：从大块 payload 里只抽某个标量
fatebridge bazi_birth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male --fields snapshot_text bazi_birth.day_master
```

---

## 出生信息：一次说清

绝大多数命理 / 占星工具共享出生信息字段（详见 [api-reference.md](api-reference.md) §3）。最少需要 `birth_year/month/day/hour`，其余可选：

- `birth_year` / `birth_month` / `birth_day` / `birth_hour`：必需，出生日期与时刻
- `birth_minute`：可选，默认 0
- `gender`：可选，八字专项建议传入，取值为 `男` 或 `女`
- `birth_place`：可选，中文 / 英文 / 拼音地名；内置静态近似，不是联网地理编码
- `birth_timezone`：可选，IANA 时区或 UTC offset
- `birth_longitude` / `birth_latitude`：视工具而定，占星盘建议显式传入以保证精度
- `use_true_solar_time`：可选，启用真太阳时修正（含经度 + 均时差）

真太阳时、地点解析、时区补全统一走 `fatebridge.utils.helpers`，结果会回显在 `person_info.time_adjustment`。需要高精度占星盘时，优先显式传经纬度，而不是依赖 `birth_place` 推断。

---

## 按通道接入

### REST（HTTP）

```bash
curl -X POST http://localhost:8010/api/cn/bazi/wealth \
  -H "Content-Type: application/json" \
  -H "X-API-Key: replace-me" \
  -d '{"gender":"男","birth_year":1990,"birth_month":5,"birth_day":15,
       "birth_hour":10,"birth_timezone":"Asia/Shanghai","use_true_solar_time":true}'
```

如果配置了 `FATEBRIDGE_API_KEYS`，除 `/health`、`/ready`、`/metrics` 和文档页外，其余端点都需要带 `X-API-Key`。

**Python（requests）示例：**

```python
import requests

resp = requests.post(
    "http://localhost:8010/api/cn/bazi/wealth",
    headers={"X-API-Key": "replace-me"},
    json={
        "gender": "男", "birth_year": 1990, "birth_month": 5, "birth_day": 15,
        "birth_hour": 10, "birth_timezone": "Asia/Shanghai", "use_true_solar_time": True,
    },
    timeout=30,
)
resp.raise_for_status()
data = resp.json()
if data.get("error_code"):
    raise RuntimeError(data["error_code"])
print(data["wealth_analysis"])
```

**JavaScript（fetch）示例：**

```js
const res = await fetch("http://localhost:8010/api/cn/bazi/wealth", {
  method: "POST",
  headers: { "Content-Type": "application/json", "X-API-Key": "replace-me" },
  body: JSON.stringify({
    gender: "男", birth_year: 1990, birth_month: 5, birth_day: 15,
    birth_hour: 10, birth_timezone: "Asia/Shanghai", use_true_solar_time: true,
  }),
});
const data = await res.json();
if (data.error_code) throw new Error(data.error_code);
console.log(data.wealth_analysis);
```

### FastMCP（Agent host）

启动：

```bash
fatebridge-mcp
# 或等价写法（未安装时）
python -m fatebridge.mcp_server
```

注册到 MCP host（以 Claude Code / Claude Desktop 为例）：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "fatebridge-mcp"
    }
  }
}
```

如果 `fatebridge-mcp` 不在 PATH 里（虚拟环境未激活），用完整路径代替：

```json
{
  "mcpServers": {
    "fatebridge": {
      "command": "python",
      "args": ["-m", "fatebridge.mcp_server"]
    }
  }
}
```

几个注意点：

- MCP 工具多数返回 JSON 字符串而非原生对象，消费时需要 parse。
- 错误同样以 JSON 字符串形式返回，也带 `error_code`。
- 用 `fields` 参数控制返回体积。

### CLI（脚本 / 自动化）

```bash
fatebridge list
fatebridge describe ziwei_birth
fatebridge ziwei_birth --birth-year 1990 --birth-month 6 --birth-day 15 \
    --birth-hour 10 --gender male
fatebridge knowledge_read --domain bazi --category romance --key 桃花咸池
```

CLI 子命令与参数同样从中央目录派生，`--help` 可查每个工具的参数。

---

## Agent 接入建议

1. 发现：启动时拉一次 `/api/tools`（或 MCP `tools/list`），按 `family` 建立工具路由表。
2. 路由：按用户意图选 family，例如八字走 `bazi`、运势走 `timing`、星盘走 `astro`、术数走 `metaphysics` / `divination`。场景级取舍（谁主谁次、怎么省 token、怎么避免结论打架）见 [scenario-routing.md](scenario-routing.md)。
3. 取数：传齐出生信息；需要真太阳时就显式传 `use_true_solar_time=true`。
4. 裁剪：用 `fields` / `--fields` 或 `selected_sections` 控制 token。
5. 判错：始终基于 `error_code` 分支；`dependency_missing` 说明环境缺西占 backend，不是入参问题。
6. 溯源：把 `run_metadata.run_id` 和 `trace_id` 记进日志，方便复现。

---

## 相关文档

- [api-reference.md](api-reference.md)：全部 REST 路由、FastMCP 工具、请求族、响应字段
- [algorithm-coverage.md](algorithm-coverage.md)：12 family / 80 工具的算法与精度 / 依赖矩阵
- [scenario-routing.md](scenario-routing.md)：场景到工具的路由矩阵、调用纪律、交叉印证与去重策略
- [getting-started.md](getting-started.md)：从零启动服务
- [troubleshooting.md](troubleshooting.md)：依赖缺失、精度、快照导出等常见问题
