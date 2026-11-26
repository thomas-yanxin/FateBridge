# FateBridge 故障排除

安装失败、工具不可见、请求报错或结果不完整时，可先按现象定位问题所在的环节。保存原始错误和退出码后再排查；参数错误应修正输入，依赖错误应修复当前进程环境。接口字段与返回合同见 [API 参考](api-reference.md)，配置见[快速入门](getting-started.md)。

## 按现象定位

| 现象 | 先看哪里 |
| --- | --- |
| 无法导入、安装或测试环境异常 | [安装和导入](#安装和导入) |
| 服务不通、MCP 没有工具 | [服务启动与连接](#服务启动与连接) |
| 桌面 Codex 与终端可用模型不同 | [Codex CLI 路径](#codex-桌面版与终端-cli-的模型不一致) |
| 401、400、422、CLI 非零退出 | [鉴权与错误](#rest-鉴权与错误) |
| 时刻、地点或命盘字段不符 | [出生信息与返回字段](#出生信息与返回字段) |
| 星历降级或西占后端错误 | [占星与推运](#占星与推运) |
| 字段投影报错或结果被裁剪 | [输出分级与字段投影](#输出分级与字段投影) |

## 先检查当前环境

源码环境在仓库根目录执行以下命令；独立工具安装可直接运行 `fatebridge doctor`。诊断只检查当前安装，不修改 host 设置。

```bash
uv run --locked --extra dev python -c "import sys, fatebridge; print(sys.executable); print(fatebridge.__version__, fatebridge.__file__)"
uv run --locked --extra dev fatebridge doctor
```

若问题只出现在 MCP host，再用相同环境运行 `fatebridge doctor --mcp --family bazi`，将分类替换为实际范围。REST 问题还应检查实际端口的 `/health` 与 `/ready`。

## 安装和导入

### `ModuleNotFoundError: No module named 'fatebridge'`

当前项目使用 `src/` 布局，切到仓库根目录不会自动把包放入导入路径。在仓库目录执行同步并核对加载路径：

```bash
cd /path/to/FateBridge
uv sync --locked --extra dev
uv run --locked --extra dev python -c "import sys, fatebridge; print(sys.executable); print(fatebridge.__version__, fatebridge.__file__)"
```

`fatebridge.__file__` 应指向当前 checkout 的 `src/fatebridge/`。若仍来自其他安装，确认启动器和 host 使用的是本次 `.venv` 中的解释器。

### 安装失败或异步测试不能执行

确认满足 Python 3.10+（CI 覆盖 3.10–3.13），并检查锁文件与开发环境同步：

```bash
uv lock --check
uv sync --locked --extra dev
```

`async def functions are not natively supported` 说明当前测试解释器缺少 `pytest-asyncio`，需使用 `--extra dev` 环境。缺少 `swisseph` 是 Python 依赖问题，缺 `.se1` 则是星历数据文件未配置。

## 服务启动与连接

### 端口占用或健康检查不通

macOS / Linux 可用 `lsof -i :8010` 查看占用者。临时改端口后请求也要对应修改：

```bash
API_HOST=127.0.0.1 API_PORT=8011 python -m fatebridge.api
```

在另一个终端执行 `curl http://localhost:8011/health`。环境变量优先于源码目录 `.env`，改配置后重启进程。

### `/ready` 为 ready，西占仍报错

`/ready` 只用必需检查决定总状态，西占 runtime 是可选项。查看 `checks.western_predictive_runtime`，再核对具体工具的依赖、数据与输入。

### MCP host 连不上

先用同一安装环境执行 `fatebridge doctor --mcp` 验证独立 stdio 进程。默认 MCP 不创建 HTTP URL，host 配置应使用已安装本仓库的解释器绝对路径和 `-m fatebridge.mcp_server` 参数，见 [MCP 部署指南](mcp-deployment.md#注册本地-stdio)。

需要 URL 时，使用 [HTTP MCP 部署](mcp-deployment.md#http-与远程部署)中的 FastMCP runner；REST 的 `8010` 地址不提供 MCP。

### 工具已连接但列表不完整

查看 host 启动环境中的 `FATEBRIDGE_MCP_FAMILIES`。先用相同分类运行 doctor，再检查当前连接的 `tools/list`。扩大范围后重启连接，并在新聊天确认工具列表。

### Codex 桌面版与终端 CLI 的模型不一致

先用 `fatebridge doctor` 查看 `codex.cli`。桌面版的 `CODEX_CLI_PATH` 和 PATH 中的 CLI 可能是不同版本；按 doctor 返回的完整 `codex.add_command` 注册，保存后在新聊天检查连接。

## REST 鉴权与错误

### 401 `authentication_required`

检查已配置的 `FATEBRIDGE_API_KEYS` 与 `API_KEY_HEADER_NAME`。配置 `agent:replace-me` 时，请求头发送 `X-API-Key: replace-me`，不发送名称前缀。`/api/tools` 也受鉴权保护，运维/文档路径和 `OPTIONS` 免检。

### 400 与 422 `validation_error`

- `422`：请求字段缺失、类型或取值错误、未知字段、无效日期、非法 JSON，以及梅花时卦钟时校验失败。遇到回拨重复钟时，`analysis_utc_offset` 的 `constraints.expected` 列出该时区允许的偏移。
- `400`：请求进入领域计算后被拒绝，例如显式要求真太阳时却无经度。

先查看 `issues[].path`；若路径指向 `fields` 中的输出路径，修正投影。`detail`、`fields`、`as_of` 等 REST 控制项应放在查询参数，放入 JSON 请求体会作为未知字段失败。

### MCP / CLI 返回错误的位置

MCP 已知工具失败返回原生 `isError=true` 与结构化错误包络；FastMCP Client 读取 `issues` 时需设置 `raise_on_error=False`。CLI 工具结果与错误写 stdout，日志写 stderr；退出码 `0` 表示成功，`1` 表示计算或模型校验失败，`2` 表示用法错误或不支持。仅在 `retryable=true` 时原参数重试。

### 浏览器 CORS 错误

`ALLOWED_ORIGINS` 是逗号分隔的精确来源（协议、域名、端口），修改后重启。CORS 不代替 API Key；浏览器看到跨域错误时，也要检查服务端是否先返回了 401。

## 出生信息与返回字段

### 地点没命中或太阳时未生效

地点解析使用有限内置静态目录，不做联网地理编码。中式模型默认真太阳时 `true`：缺省开启且无经度时使用钟表时间并附提示；显式 `true` 且无经度返回错误。可补传可解析城市或 `birth_longitude`，并显式传 IANA 时区。核对 `person_info.time_adjustment` 的解析详情。

### 太阳时和原时间不同

经度、均时差与夏令时修正会改变用于相应规则的钟表读数，可查看 `person_info.normalized_birth_datetime` 和 `time_adjustment`。年/月柱、节气与起运以实际民用时刻判断，不因修正后跨过节气边界而提前换柱。

### 命盘字段层级不同或无时盘报错

独立八字入口 `/api/bazi/birth-chart` 的业务字段位于 `bazi_birth` 下；综合分析使用 `bazi_overview`。出生类模型当前要求小时，不能省略 `birth_hour`。字段投影的点号路径从响应根开始且始终严格校验，无效路径会返回 `unknown_projection_path` 并在 `issues[].constraints.available` 提示当前可用键名。

## 占星与推运

### 本地 runtime 可用但精度仍降级

同时检查 `chart_profile.engine_backend`、`engine_precision`、`ephemeris_model` 与 `run_metadata.engine_is_approximate`。运行时可用但缺 `.se1` 时可能使用 Moshier。数据获取与 `SE_EPHE_PATH` 配置见[星历安装](ephemeris.md)。CLI 不自动读取 `.env`，应在启动前设进程环境。

### 显式 `hsys` 覆盖报依赖错误

核心/关系盘的 `hsys` 是整数 `0..8`，西占推运的 `house_system` 支持 `P` 等字符串。显式 `hsys=1..8` 缺 `swisseph` 时会报错，需安装或修复运行时，或按需使用 `hsys=0`。

### 西占推运 `dependency_missing`

`astro/timing*`、事件与生命周期工具缺 `swisseph` 后端会直接失败，不回退到轨道近似。正常安装已声明 `pyswisseph`，请核对当前进程的 Python 解释器与依赖。

### 关系盘与 `synastry` 预期不同

`relative_mode="synastry"` 映射为 `influence`，比较盘使用 `relative_mode="compare"`。三端均使用 `inner_birth_*` / `outer_birth_*`。

## 输出分级与字段投影

### 只返回精简字段而非完整载荷

三端默认使用 `detail=compact`，在未指定 `fields` 时仅返回工具配置的核心业务字段及精简 `run_metadata`。需要完整业务载荷、全部时间线与 `calculation_evidence` 时，请传入 `detail=audit`（REST `?detail=audit`、MCP `detail="audit"`、CLI `--detail audit`）且不传 `fields`（`fields=null`）。详见[输出控制与结果读取](agent-guide.md#输出控制与结果读取)。

### 字段投影返回 `unknown_projection_path`

`fields` 在三端始终严格校验点号对象路径：先核对错误 `issues[].constraints.available` 列出的可用字段名，或通过 `discover_tools` / `fatebridge discover <tool> --detail full` 查看 `output_schema`。数组字段须选择其所属父键，不能使用数字索引（否则返回 `non_object_projection_path`）。

### 西占推运采用了出生钟时

推运省略 `analysis_hour` 或 `analysis_minute` 时，分别沿用出生小时或分钟。需要某日某时结果时应显式传入这两项（零点传 `0`）。输入按 `birth_timezone` 解释，`return_timezone` 只转换同一时刻。

## 最小复现材料

提交问题前请先使用虚构输入复现，并附版本/提交、Python 路径、脱敏请求、HTTP 状态/CLI 退出码/MCP `isError`、`error_code` 与 `issues` 到 [GitHub Issues](https://github.com/thomas-yanxin/FateBridge/issues)。
