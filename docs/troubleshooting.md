# FateBridge 故障排除

本页按现象定位安装导入、服务连接、鉴权错误、字段投影与星历精度问题。排查前先保留完整的 `error_code`、`issues`、HTTP 状态码 / CLI 退出码或 MCP `isError` 标志；输入类错误修正请求参数，依赖与数据错误修正运行环境后重启进程。三端错误协议详情见[错误恢复与复现](agent-guide.md#错误恢复与复现)和 [API 参考](api-reference.md#2-公共约定)。

## 按现象定位

| 现象 | 排查章节 |
| --- | --- |
| 无法导入包、环境缺失或异步测试报错 | [安装和导入](#安装和导入) |
| 服务不通、端口占用或 MCP 无工具 / 列表不全 | [服务启动与连接](#服务启动与连接) |
| 桌面 Codex 与终端 CLI 模型或连接不一致 | [Codex 桌面版与终端 CLI 不一致](#codex-桌面版与终端-cli-不一致) |
| 401 / 404 / 400 / 422 / 503 或 CLI 非零退出 | [鉴权与错误码排查](#鉴权与错误码排查) |
| 出生时刻、地点解析或真太阳时与预期不符 | [出生信息与时间口径](#出生信息与时间口径) |
| 星历精度降级、`de441_archive_missing` 或数据源冲突 | [占星与星历排查](#占星与星历排查) |
| 返回字段被裁剪或投影报 `unknown_projection_path` | [输出分级与字段投影](#输出分级与字段投影) |

## 先运行环境诊断

```bash
uv run --extra dev python -c "import sys, fatebridge; print(sys.executable); print(fatebridge.__version__, fatebridge.__file__)"
uv run --extra dev fatebridge doctor
```

独立工具安装可直接运行 `fatebridge doctor`。若仅 MCP 客户端异常，使用同一安装环境运行 `fatebridge doctor --mcp`（或加 `--family <family>`）；REST 问题先请求 `/health` 与 `/ready`。

## 安装和导入

### `ModuleNotFoundError: No module named 'fatebridge'`

仓库采用 `src/` 布局，仅切到仓库根目录不会自动将源码加入 `sys.path`。执行 `uv sync --extra dev` 并通过 `uv run --extra dev ...` 运行，或确认客户端配置指向当前 `.venv` 中的 Python 绝对路径。

### 测试或运行缺少依赖

确认 Python 版本为 3.10+（CI 覆盖 3.10–3.13）并重新执行 `uv sync --extra dev`。`async def functions are not natively supported` 说明当前解释器缺少 `pytest-asyncio`；缺少 `swisseph` 属于 Python 运行时依赖缺失，而缺少 `.se1` 属于外部星历文件未配置。

## 服务启动与连接

### 端口占用或健康检查失败

macOS / Linux 可用 `lsof -i :8010` 查看端口占用，或改用其他端口启动并同步修改请求地址：

```bash
API_HOST=127.0.0.1 API_PORT=8011 fatebridge-api
curl http://localhost:8011/health
```

进程环境变量优先于源码根目录 `.env`；修改 `.env` 或环境变量后须重启对应进程。

### `/ready` 为 `ready`，西占推运仍失败

`/ready` 仅依据必需运行条件决定总状态，西占高精度运行时属于可选项。先检查 `/ready` 返回的 `checks.western_predictive_runtime`，再核对具体工具依赖与星历目录。

### MCP 无法连接或只看到部分能力

1. 运行 `fatebridge doctor --mcp` 验证独立 stdio 进程（MCP 默认仅提供 `discover_tools` 与 `run_calculation`，0 资源，不会自动开启 HTTP URL）。
2. 检查客户端配置的 `command` 是否为 `doctor` 输出的 `executable` 绝对路径，以及是否将普通日志写到了 `stdout`（stdio 协议要求日志只写 `stderr`）。
3. 检查启动环境中的 `FATEBRIDGE_MCP_FAMILIES` 是否限制了公开 `family`；需要 URL 接入时须按 [HTTP 与远程部署](mcp-deployment.md#http-与远程部署)启动 FastMCP HTTP runner，REST 的 `8010` 端口不提供 MCP。

### Codex 桌面版与终端 CLI 不一致

运行 `fatebridge doctor` 检查 `codex.cli`。桌面版读取的 `CODEX_CLI_PATH` 可能与终端 `PATH` 中的 `codex` 版本或配置不同；按 `doctor` 输出的 `codex.add_command` 注册后重启连接并在新聊天确认。

## 鉴权与错误码排查

已知工具的模型校验与计算错误均返回统一包络（`error`、`error_code`、`retryable`、`issues`）。仅当 `retryable=true` 时才原参数重试。

| `error_code` | 常见状态 / 退出码 | 原因与处理 |
| --- | --- | --- |
| `authentication_required` | HTTP 401 | 配置了 `FATEBRIDGE_API_KEYS` 但请求缺少或错传密钥头；`agent:secret` 配置只发送 `secret` 不含前缀，`/api/tools` 同样受保护 |
| `unknown_tool` | HTTP 404 / CLI 2 | 工具名拼错或被 `FATEBRIDGE_MCP_FAMILIES` 排除；从 `issues[].constraints.suggestions` 选择正确工具名 |
| `validation_error` | HTTP 422 / 400 | 缺必填字段、类型/取值越界、非法 JSON、重复钟时缺 `birth_utc_offset`（看 `constraints.expected`）、无经度显式要求真太阳时，同时传入 `include` 与 `fields`、传入已移除的 `detail` 参数，或将 `include`/`fields`/`as_of` 误放入 REST JSON 体（应放 URL 查询参数） |
| `filter_required_for_full_detail` | HTTP 422 | 调用 `discover_tools` / `/api/tools` / `fatebridge discover` 时传了 `detail=full` 但未提供 `tool`、`family` 或 `q` 过滤 |
| `consultation_restricted` | HTTP 422 | 命中生死寿命、灾祸断言、临床诊断或医疗择时红线（不可重试） |
| `dependency_missing` | HTTP 503 | 缺少 `swisseph` 等运行时依赖（如西占推运、事件与生命周期工具或显式非整宫宫制），不回退近似轨道 |
| `ephemeris_calculation_failed` | HTTP 503 | 原生星历计算异常；核对运行时环境、`SE_EPHE_PATH` 与输入有效范围 |
| `ephemeris_source_inconsistent` | HTTP 503 | 太阳交节模型与 `FATEBRIDGE_JPL_FILE` 冲突、SPK/VSOP2013/AA1996 清单或字节不一致、或计算期间文件发生变化（`retryable=false`） |
| `de441_archive_missing` | HTTP 503 | 显式设置了 `FATEBRIDGE_DE441_DIR`（或直接调用 DE441 系数接口）但目录下缺少 DE441 连续行星系数分片；补齐对应分片或取消 `FATEBRIDGE_DE441_DIR` 改用内置降级后重启（`retryable=false`） |
| `fengshui_calculation_inconsistent` / `numerology_source_inconsistent` / `jyotish_calculation_inconsistent` | HTTP 503 | 领域内部计算或来源校验矛盾，不能靠改用户输入绕过，需保留输入与版本反馈维护者（`retryable=false`） |
| `timeout` / `internal_error` | HTTP 504 / 500 | 服务端超时或未预期内部异常（`retryable=true`，可原参数有限重试并附诊断上下文） |
| `usage_error` | CLI exit 2 | CLI 未知 flag、参数语法或 `--request-file` 读取错误（MCP 客户端注意 `raise_on_error=False` 读取结构化 `issues`） |

浏览器遇到 CORS 错误时，先确认是否被服务端先返回了 `401`，再核对精确的协议/域名/端口格式 `ALLOWED_ORIGINS` 并重启进程。

## 出生信息与时间口径

- **地点未命中或真太阳时报错**：内置地名解析使用离线静态目录（见[离线城市目录](place-catalog.md)），不做联网地理编码。中式模型默认真太阳时 `true`：缺省且无经度时回退钟表时间并附提示；显式传 `true` 且无经度返回 `400`。补传可解析城市或 `birth_longitude` 与 IANA 时区，并在 `person_info.time_adjustment` 核对校正详情。
- **太阳时与民用时间差异**：经度、均时差与夏令时调整记录在 `person_info.normalized_birth_datetime`；年/月柱、节气交接与起运仍按实际民用时刻判断，不因真太阳时跨节气而提前换柱。
- **关系盘与推运时分默认值**：`relationship_chart` 三端统一使用 `inner_birth_*` 与 `outer_birth_*`（`synastry` 对应 `influence`，比较盘为 `compare`）。西占推运省略 `analysis_hour` / `analysis_minute` 时沿用出生时分，需精确到某时请显式传参（零点传 `0`）。

## 占星与星历排查

同时核对 `chart_profile.engine_backend`、`engine_precision`、`ephemeris_model` 与 `run_metadata.engine_is_approximate`。若 `swisseph` 可用但仍回退 Moshier，通常是未设置 `SE_EPHE_PATH`、CLI 未读取 `.env`，或 `SE_EPHE_PATH` 超过 242 编码字节被底层静默忽略；按[星历安装指南](ephemeris.md)修正路径并重启进程即可。

## 输出分级与字段投影

### 默认省略次级重型块而非完整结果

三端默认返回核心业务字段，并通过 `run_metadata.omitted_fields` 列出实际省略的可选重型路径。需要按需展开指定路径或 `evidence_views` 名称时传 `include`，需要无损完整业务载荷与全部时间线时传 `include=["*"]`（REST `?include=*`、MCP `include=["*"]`、CLI `--include "*"`；不可与 `fields` 同时传入）。

### 投影报 `unknown_projection_path` 或 `non_object_projection_path`

- `unknown_projection_path`：点号路径在当前返回对象中不存在。先查看错误 `issues[].constraints.available` 提示的可用键名，或通过 `discover_tools(tool=..., detail="full", include_output_schema=True)` / `fatebridge discover <tool> --detail full --include-output-schema` 核对完整输出 Schema。
- `non_object_projection_path`：路径穿越了列表（数组）或标量。`fields` 只能选择对象键路径，数组字段须投影到其所属父键后由客户端处理。

## 提交最小复现材料

提交问题前请用虚构资料复现，并将版本/提交、Python 路径、脱敏请求及完整的 `error_code` / `issues` 提交至 [GitHub Issues](https://github.com/thomas-yanxin/FateBridge/issues)。
