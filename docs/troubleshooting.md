# FateBridge 故障排除

先确认当前版本、解释器和原始请求，再按错误层定位。接口字段与返回合同以 [API 参考](api-reference.md) 为准，配置见 [快速入门](getting-started.md)。

## 按现象定位

| 现象 | 先看哪里 |
| --- | --- |
| 无法导入、安装或测试环境异常 | [安装和导入](#安装和导入) |
| 服务不通、MCP 没有工具 | [服务启动与连接](#服务启动与连接) |
| 401、400、422、CLI 非零退出 | [鉴权与错误](#rest-鉴权与错误) |
| 时刻、地点或命盘字段不符 | [出生信息与返回字段](#出生信息与返回字段) |
| 星历降级或西占后端错误 | [占星与推运](#占星与推运) |
| 只收到部分结果、引用失效 | [快照与结果交付](#快照导出) |
| 旧路由、字段或 Python 导入失效 | [迁移指南](migration.md) |

## 安装和导入

### `ModuleNotFoundError: No module named 'fatebridge'`

当前项目使用 `src/` 布局，切到仓库根目录不会自动把包放入导入路径。激活环境并安装，用实际加载路径判断是否装到了另一个解释器：

```bash
cd /path/to/FateBridge
source .venv/bin/activate
python -m pip install -e .
python -c "import sys, fatebridge; print(sys.executable); print(fatebridge.__version__, fatebridge.__file__)"
```

Windows 激活命令见 [快速入门](getting-started.md#安装)。测试和静态检查还需安装 `.[dev]`。

### 安装失败或异步测试不能执行

保存完整的 pip/uv 错误和 Python 版本，确认满足 Python 3.10+；当前 CI 为 3.10–3.13。可先更新 pip 再重试：

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`async def functions are not natively supported` 通常说明当前测试解释器没有 `pytest-asyncio`，检查是否安装了 dev 依赖。缺少 `swisseph` / `kerykeion` 时核对的是 Python 包依赖；缺 `.se1` 时核对的是星历数据，二者不同。

## 服务启动与连接

### 端口占用或健康检查不通

macOS / Linux 可用 `lsof -i :8010` 查看占用者。临时改端口后请求也要对应修改：

```bash
API_HOST=127.0.0.1 API_PORT=8011 python -m fatebridge.api
```

在另一个终端执行 `curl http://localhost:8011/health`。环境变量优先于源码目录 `.env`，改配置后重启进程。默认 `0.0.0.0` 会监听所有网卡，访问时用 `localhost` 或服务主机地址。

### `/ready` 为 ready，西占仍报错

`/ready` 只用必需检查决定总状态，西占 runtime 是可选项。查看 `checks.western_predictive_runtime`，再核对具体工具的依赖、数据与输入。健康/就绪接口不是全工具验证。

### MCP host 连不上

先用同一安装环境执行 `fatebridge doctor --mcp`，或加 `--scenario onda-shiye` 验证所选场景；它会从无关工作目录启动独立进程。Codex 的原生配置与检查步骤见 [Codex 使用指南](codex-guide.md)。

默认 MCP 是 stdio 进程，不创建 HTTP URL。host 配置应使用已安装本仓库的解释器绝对路径，例如 `/absolute/path/to/FateBridge/.venv/bin/python` 和参数 `-m fatebridge.mcp_server`。不要依赖 GUI host 继承 shell 的环境激活状态。确认 host 的进程日志、解释器和包路径，配置结构见 [接入指南](agent-guide.md#fastmcpagent-host)。

## REST 鉴权与错误

### 401 `authentication_required`

检查已配置的 `FATEBRIDGE_API_KEYS` 与 `API_KEY_HEADER_NAME`。配置 `agent:replace-me` 时，请求头发送 `X-API-Key: replace-me`；不发送名称前缀。`/api/tools` 也受鉴权保护，运维/文档路径和 `OPTIONS` 免检。

非空配置出现空条目、缺名称/密钥或重复名称，会在启动时失败；不要把删除全部密钥作为恢复步骤。无需在报告中输出密钥值。

### 400 与 422 `validation_error`

当前 REST 错误使用顶层字段，不再从 `detail` 取业务错误：

```json
{
  "error": "请求参数无效",
  "error_code": "validation_error",
  "retryable": false
}
```

- 422：请求字段缺失、类型/范围/枚举错误、未知字段或无效完整公历日期，在请求模型层被拒绝；REST JSON 语法错误也返回 422。
- 400：请求进入领域计算后被拒绝，例如未由模型限制的未知模式，或显式要求太阳时却无经度。

同一错误码可以来自不同层。模型错误通过 `issues` 指明字段路径、错误类型及可选约束，不回显原始值。查看状态码与 schema，把月/日范围检查和真实日期检查都纳入调用侧校验。完整非法分析日期不会自动改成月底；部分年月日的补齐规则与完整日期校验不同。

### MCP / CLI 返回错误的位置

MCP 已知工具的模型/业务失败返回 `isError=true` 与结构化错误包络。FastMCP Client 默认抛出 `ToolError`；需读取 `issues` 时使用 `raise_on_error=False` 并读取 `structured_content`。未知工具、非法 RPC 等协议错误单独处理。CLI 工具结果与错误均写 stdout，日志写 stderr；退出码 0 成功、1 计算/模型失败、2 用法错误或不支持。`list` / `--help` 是文本输出。按实际 `retryable` 判断是否重试，参数或依赖错误需先修正。

### 浏览器 CORS 错误

`ALLOWED_ORIGINS` 是逗号分隔的精确来源（协议、域名、端口），例如 `http://localhost:3000,http://localhost:5173`。修改后重启。CORS 不代替 API Key；自定义密钥请求头应与服务的 `API_KEY_HEADER_NAME` 一致。浏览器看到跨域错误时，也要检查服务端是否先返回了 401。

## 出生信息与返回字段

### 地点没命中或太阳时未生效

地点解析使用有限静态目录，不做联网地理编码。中式模型默认太阳时 true：缺省开启且无经度时使用钟表时间并附提示；显式 true 且无经度返回错误。补可解析城市或明确的 `birth_longitude`，同时传 IANA 时区。占星还应提供纬度。

核对 `person_info.time_adjustment` 的 `resolved_place`、`resolution_level`、`longitude_source`、`resolution_advisory` 与 `applied`。省级中心点只是近似，不等于实际县市位置。

### 太阳时和原时间不同

经度、均时差与夏令时修正会改变用于相应规则的钟表读数。查看 `person_info.normalized_birth_datetime` 和 `time_adjustment`。年/月柱、节气与起运以实际民用时刻判断，不应因修正后跨过节气边界而提前换柱。

### 命盘字段层级不同或无时盘报错

新独立八字入口 `/api/cn/bazi/birth` 的业务字段在 `bazi_birth` 下；旧 `/api/calculate` 已移除。MCP / CLI `analyze_destiny` 执行综合分析。

当前出生类模型要求小时，不能省略 `birth_hour` 来生成无时盘，也不能无依据填 0。字段投影的点号路径从响应根开始，不会深搜同名字段；无效路径默认附 `projection_warnings`，使用 `strict_fields=true` / `--strict-fields` 可明确拒绝。

## 占星与推运

### 本地 runtime 可用但精度仍降级

同时检查 `chart_profile.engine_backend`、`engine_precision`、`ephemeris_model` 与 `run_metadata.engine_is_approximate`。运行时可用但缺 `.se1` 时可能使用 Moshier；仅看 backend 名称会遗漏降级。数据获取与 `SE_EPHE_PATH` 配置见 [快速入门](getting-started.md#星历数据与精度)。

CLI 不自动读取 `.env`，`SE_EPHE_PATH` 应在启动前设进程环境。GUI MCP host 也需传入相同路径。选择一致的版本、数据路径和日期后重试，并保存结果的实际模型标识。

### 显式 `hsys` 覆盖报依赖错误

核心/关系盘的 `hsys` 是整数 `0..8`，不是 `P`；西占推运的 `house_system` 支持 `P` 等字符串。显式 `hsys=1..8` 缺 `swisseph` 会报错，可安装/修复运行时，或在接受宫制变化的前提下使用可运行的 `hsys=0`。不要把去掉覆盖当作保持同一宫制精度。

### 西占推运 `dependency_missing`

`astro/timing*`、事件与生命周期工具缺 backend 会直接失败，不使用 FateBridge 的轨道近似替代。正常安装已声明 `kerykeion` / `pyswisseph`；核对实际进程的解释器及依赖版本。核心 chart 的回退能力不能推广到所有西占工具。

### 关系盘与 `synastry` 预期不同

`relative_mode="synastry"` 映射 `influence`；比较盘使用 `relative_mode="compare"`。旧字段 `relationship_mode` 已移除，提交会返回输入校验错误。REST 使用嵌套 `inner` / `outer`，MCP / CLI 使用 `inner_birth_*` / `outer_birth_*`；不要跨端直接复制整段请求。

## 快照导出

### `selected_sections` 没生效或导出为空

先确认模型支持该字段（八字九大专项不支持输入此字段），再查看 `snapshot_export.section_titles_detected` 与 `missing_selected_sections`。显式非空选择没有命中时导出为空，不回退全文；未知标题或旧别名需按实际检测结果修正。CLI 用空格分隔多个标题，不能逗号拼接；紫微命盘检测的是 `起盘信息` / `宫位总览`，`命宫` / `夫妻宫` 等不是导出 section。

`selected_sections` 只作用于导出层，完整 payload 与 `snapshot_text` 仍保留。若要控制整体体积，用三端 `fields` 投影和 `include_snapshot_text=false`。保留 `snapshot_export` 时，其中的 `export_text` 也可能很大。

### 只返回部分字段或出现 `result_delivery`

先检查首次调用的 `fields`、`include_snapshot_text` 与 `selected_sections`，再检查响应预算。MCP 默认 8192 字符，超限时通过交付引用提供同一 run 的保留结果，响应仍是合法 JSON。读取 `manifest_uri`，从 `first_page_uri` 跟随 `next_uri` 拼接每页 `text`，核对 SHA-256 后解析全文。资源返回的外层 JSON 与其中的正文片段需要分别解析，不能直接解析单页片段。

交付发生在投影之后：首轮只选了摘要，文件也只有所选范围。完整导出首次使用 `fields=null`，需要快照时保留相应选项。引用过期或被容量回收后无法继续读取；不要通过重复计算声称恢复了原 run。完整操作见 [同次导出](agent-guide.md#完整结果交付与同次导出)。

### 西占推运采用了出生钟时

推运省略 `analysis_hour` 或 `analysis_minute` 时，分别沿用出生小时或分钟。只传分析日期或 `as_of` 不代表指定了目标钟时；需要某日某时的结果，应显式传这两项，零点传 `0`。输入按 `birth_timezone` 解释，`return_timezone` 只转换同一时刻。核对聚合结果的 `analysis_context.analysis_datetime`，以及行运分支实际采用的时刻。

### 结果引用过期或首轮没有保留字段

`result_delivery` 是临时交付引用，可能过期或因容量回收失效；`file_path` 位于运行服务的机器，远程客户端应使用资源或 HTTP 分页。还未失效时尽快保存原结果，读取方法见[完整结果交付](agent-guide.md#完整结果交付与同次导出)。

若首次 `fields` 未选择某字段，分页与文件都不能补回；这与引用过期是不同问题。说明这一次实际保留的范围，不能以新计算冒充旧 run。需要再次计算时明确它是新运行。

## 最小复现材料

报告问题时提供以下脱敏证据：版本/提交、解释器与依赖版本、端口及鉴权是否开启（不含值）、原始请求、状态/退出码、错误码、输入时区和坐标、太阳时策略、分析日期、星历模型、运行 ID（若有）。不要只提供解读文本。

文档漂移优先核对 `services/tool_catalog.py` 的装配、`services/catalog/` 的领域声明、`core/requests/` 的模型与实际 OpenAPI/MCP schema，再按 [文档维护流程](development-guide.md#文档维护与验证) 同步修正。


### Codex 桌面版与终端 CLI 的模型不一致

若终端 CLI 报模型不受 ChatGPT 账号支持，而桌面聊天可正常使用，先用 `fatebridge doctor` 查看 `codex.cli`。桌面版的 `CODEX_CLI_PATH` 和 PATH 中的 CLI 可能是不同版本；按 doctor 返回的完整 `codex.add_command` 注册，不必为此修改用户模型。保存配置不代表当前聊天已经重载 MCP，请在新聊天检查连接。
