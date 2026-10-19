# Codex 使用 FateBridge

本页带你将本地 FateBridge 注册到 Codex，确认当前聊天已加载工具，并完成一次虚构咨询。前提是已按[快速入门](getting-started.md#安装)完成源码安装；无需启动 REST。其他 MCP host 请看[通用接入指南](agent-guide.md#fastmcpagent-host)。

1. [确认安装与接入范围](#1-确认安装与接入范围)：运行 doctor，取得当前解释器的注册命令。
2. [注册到 Codex](#2-注册到-codex)：保存配置并在新聊天检查工具。
3. [完成第一次对话](#3-完成第一次对话)：用自然语言描述问题与已知资料。

连接失败见[恢复步骤](#5-出错后的恢复)，当前聊天尚未加载工具时可使用[CLI](#4-当前聊天尚未加载-mcp-时直接用-cli)。文中的 `.venv/bin/` 是 macOS / Linux 路径；Windows 使用 `.venv\Scripts\` 中对应入口。

Codex 负责理解问题、选择工具和解释结果，FateBridge 负责计算。以 FateBridge 项目根目录开始聊天，会加载同一份 [`AGENTS.md`](../AGENTS.md)，按请求区分咨询与工程任务。桌面聊天选择该项目；终端使用 doctor 返回的原生 CLI 路径，执行 `<Codex CLI 绝对路径> -C "$PWD"`。模型、推理强度及插件沿用用户配置。人物资料完整的独立咨询可直接使用当前聊天事实；用户未要求沿用历史时，无需搜索仓库或历史记录。

## 1. 确认安装与接入范围

在已经按[快速入门](getting-started.md#安装)安装的仓库中执行：

```bash
.venv/bin/fatebridge doctor --mcp --scenario onda-shiye
```

`ok=true` 表示依赖版本检查、独立 stdio 进程初始化、工具发现、资源读取和一条虚构计算通过。进程在仓库之外的临时目录启动，能检查 GUI host 常见的工作目录问题。它不证明所有工具、真实对话或远程部署都已验证。

`codex.add_command` 给出使用当前解释器绝对路径的注册命令；`codex.cli` 记录 CLI 来源。桌面环境存在 `CODEX_CLI_PATH` 时优先使用桌面版自带 CLI，避免 PATH 中旧版 CLI 与账号可用模型不一致。诊断只输出配置，不修改 Codex 设置。`--scenario` 限制实际公开的工具，并展开场景声明的知识支撑、条件服务和组合主题依赖；这些工具按问题使用，不自动全部执行；`--family` 可以进一步筛选，二者取交集。没有筛选时检查全部 MCP 工具。无效分类和空交集返回失败，先修正筛选。

普通安装检查可用 `fatebridge doctor`；它不启动 MCP，也不验证星历精度。全量工具 Schema 较大，首次接入可选当前问题对应的场景。下面的 `onda-shiye` 只公开事业场景所需工具；需要跨主题咨询时，扩大范围或清空筛选。配置含义见[核心概念](concepts.md)。

## 2. 注册到 Codex

复制 doctor 输出中的 `codex.add_command` 执行。下面是事业场景的语法示例；桌面环境请将示例中的 `codex` 换成 doctor 返回的 CLI 绝对路径：

```bash
codex mcp add fatebridge \
  --env FATEBRIDGE_MCP_FAMILIES= \
  --env FATEBRIDGE_MCP_SCENARIOS=onda-shiye \
  -- "$PWD/.venv/bin/python" -m fatebridge.mcp_server
codex mcp get fatebridge
```

也可以在 Codex 的 `config.toml` 加入下列配置，替换成 doctor 确认的绝对路径：

```toml
[mcp_servers.fatebridge]
command = "/absolute/path/to/FateBridge/.venv/bin/python"
args = ["-m", "fatebridge.mcp_server"]
startup_timeout_sec = 30
tool_timeout_sec = 60

[mcp_servers.fatebridge.env]
FATEBRIDGE_MCP_FAMILIES = ""
FATEBRIDGE_MCP_SCENARIOS = "onda-shiye"
```

Codex 使用 `[mcp_servers.fatebridge]`；其他 host 的 `mcpServers` JSON 不能直接粘进 TOML。stdio 服务由 Codex 启动，无需另外开一个终端运行，也不使用 `http://localhost:8010`。

注册或调整范围后，在新聊天中检查 FateBridge 工具是否可见；CLI TUI 可用 `/mcp` 查看连接。`codex mcp get` 只证明配置存在，doctor 只证明 MCP 进程可用，都不等于当前聊天已加载。配置约定依据 [OpenAI 官方 MCP 文档](https://developers.openai.com/codex/mcp)。

想公开全部工具时，清空两个筛选变量并重新启动连接；想查住宅风水时可以只设 `FATEBRIDGE_MCP_FAMILIES=fengshui` 并清空场景变量。更新已有配置中的同一条目即可。范围受限的连接不能调用隐藏工具，读取场景详情时检查 `availability`。

## 3. 完成第一次对话

可在接入后的 Codex 聊天中使用以下提示：

> 请用 FateBridge 帮我看看事业。我最近想换工作，也在考虑自己做点生意。以下是虚构体验资料：男，公历 1990 年 5 月 15 日上午 10:30，在北京出生，按当地钟表时间记录。看 2026 年的情况，请用普通人能懂的话讲。

这一步应看到 Codex 使用 FateBridge 工具，并基于返回结果解释本次事业问题。回答应包含实际依据的传统含义和现实建议；只显示连接成功、工具清单或限制说明，还没有完成这次体验。

你不需要记工具名、查坐标或填写专业表单。城市能够被引擎解析时，时区、经度和太阳时处理由 Codex 与工具完成；实际解析有歧义再核对。只有“上午”、确实不知道几点时，不能猜时刻生成个人命盘，但仍可解释相关方法、讨论已给的现实选项，并说明哪些个人判断暂时不能计算。只问术语含义时，直接核对知识来源解释即可。

### 调用与解读约定

维护集成或检查 Agent 行为时，使用以下流程。普通用户可在完成上述对话后按实际问题继续追问，无需逐项操作。

1. 按所选计算核对当前用户已确认的资料；缺小时或只有时段时说明影响并简短追问，用户明确不知道后停止索取同项，转交可用范围。不能补零点、借用示例或沿用确定时刻的盘。可选精度和无关方法缺项不作为全局门槛。双人关系未说明类型时用 `general`，不能从性别推断婚姻。
2. 先读取匹配的场景技能，按主题与时间范围选择有价值的依据。已发布工具的参数 Schema 和描述够用时直接计算；描述包含经过验证的首轮 `fields` 建议。专项已自动推算的大运、流年不重复计算，也不手工覆盖。普通咨询无需先列资源、读完整输出契约或搜索仓库。
3. 仅在选择不明确时读场景/目录；参数不清楚时读 `fatebridge://tools/{tool}/input`，需要更细字段时读完整工具契约。资源用于补足缺口，不是每轮必经步骤。
4. 冻结明确的分析日期，例如 `as_of="2026-10-12T04:00:00Z"` 对应上海中午 12 点；设置 `strict_fields=true`、`include_snapshot_text=false`，按问题取必要字段。明确的分析日期仍优先。
5. 先检查 `isError`，再读取 `structuredContent`。保存原输入与 `run_metadata`；后续调用沿用前次 `trace_id`，用前次 `run_id` 作为 `parent_run_id`。不要把同一出生资料的多次计算当成独立证据。
6. 先回答问题，再讲清依据的传统含义与本题的联系，区分可复算计算、有来源解释和现实建议。有充分依据的选项偏向应直接说明理由与条件，避免只有“不能替你决定”。用户要求深入时再扩展已有结果；同一主题边界无需反复重述。日期、时区、地点、太阳时及精度以实际返回为准。

上述精简字段用于摘要咨询。用户要求完整 JSON、全部时间线或完整文件时，首次调用改用 `fields=null`，保留默认响应预算及所需快照，超限后从 `result_delivery` 读取同一 run。不能先裁出摘要再重新计算来补全文。资源分页、文件提取与 SHA-256 校验见 [完整结果交付](agent-guide.md#完整结果交付与同次导出)。西占推运须显式传目标 `analysis_hour` / `analysis_minute`，并核对返回的 `analysis_context.analysis_datetime`；`as_of` 不替代目标钟时。

双人关系中，`summary.overall_score` 是 0–100 的规则加权分，`traditional_compatibility.score` 是加减净分，`detailed_analysis.traditional_analysis.score` 是独立摩擦维度；三处的 `score_basis` 说明口径。不能平均、视为成功概率或用一个子项等级替代整体评价。首轮建议字段保留完整依据、人物和建议，避免为了补解释再计算一遍。

根目录 `AGENTS.md` 包含事业、双人相处、综合时运、风水布局和西占推运的实际输入合同与首轮字段。当前公历资料齐全、工具公开时可以直接调用，省去一次工具检索和模型往返。合同由 `scripts/build_codex_call_contracts.py` 从当前 MCP 生成，接口更新后的测试会检查是否同步，参数约束与完整服务端 Schema 保留。

合同未覆盖的工具可能仍需 `ALL_TOOLS` 检索。此时一次返回所需主证的完整条目，保留说明和参数定义；不要先展开全部候选、再检索同一工具，也不要只返回名称。用途确有歧义再展开候选。工具定义在当前对话已取得且未改变时，后续计算沿用已知合同，无需为解释已有结果重新发现或计算。当前聊天与新聊天的连接加载状态需分别核对。

### 风水布局咨询

从 [onda-fengshui](../skills/onda-fengshui/SKILL.md) 及其[咨询闭环](../skills/onda-fengshui/references/consultation.md)进入。布局调用 `fengshui_assess` 并设置 `analyze_layout=true`；只提交已确认事实，位置、朝向、宅向与使用人分别核对。只知道桌子朝西时可算朝向部分，不能补成桌在西宫或住宅坐向。

独立形态可用 `methods=[]` 与 `form_observations`，无需生辰或罗盘；照片保留为候选。原始盘、布局关联、规则审查和动作可执行状态分别报告，已有判断先解释，搬动许可与物理可行性只约束落实动作。无规则或未实现的项目直接说明范围。

MCP 场景 `onda-fengshui` 与 `fengshui` 分别供咨询和基础计算发现。完整输入、支持对象及规则版本见[家居风水](fengshui.md)，可运行输入见[示例索引](examples/README.md)。更正事实时重建受影响输入并沿用 trace / parent 关联；仅解释未改变的结果不重算。

## 4. 当前聊天尚未加载 MCP 时直接用 CLI

```bash
# 先按问题发现工具，再取输入契约；默认 describe full 还包含输出 Schema。
.venv/bin/fatebridge discover --query 跳槽 --surface cli
.venv/bin/fatebridge scenarios --scenario onda-shiye --detail full
.venv/bin/fatebridge describe bazi_career --detail input

# 同一份虚构资料可以用于多次调用。
.venv/bin/fatebridge bazi_career \
  --subject-file examples/demo-subject.json \
  --as-of 2026-10-12T04:00:00Z \
  --fields career_analysis.dominant_ten_gods.primary_career_type \
           career_analysis.career_timing career_analysis.timing_context \
  --strict-fields --compact

# 综合命盘也支持裁剪；子结果与根结果的运行凭据保留。
.venv/bin/fatebridge profile --systems bazi,astro \
  --subject-file examples/demo-subject.json \
  --as-of 2026-10-12T04:00:00Z \
  --fields profile.bazi.bazi_birth.day_master profile.astro.chart_profile \
  --strict-fields --compact
```

`describe` 区分两种输出：`cli_usage` 是需替换占位符的语法模板；有 `cli_example` 时，该命令使用已验证的虚构输入，可直接执行。目录 key（如 `astro_hellen`）与公开名称（`astro_hellen_chart`）均可用于 CLI、describe 和发现查询；MCP 的 `tools/call` 仍使用实际发布的 `mcp_name`。`surfaces.cli_name` 明确标出正式命令。

`profile` 按实际工具去重，`bazi,八字` 只计算一次并保留第一个标签；空体系列表会报错。单个体系失败时退出码为 1，即使只投影成功体系也会保留失败项，不能把部分失败解释为全部成功。`--no-include-snapshot-text` 移除各子结果顶层快照；导出文本仍可能保留，需要更小输出时用 `--fields`。

真实资料请保存到用户选择的文件位置，不要覆盖演示文件或提交到仓库。需要删除元数据时，`--no-metadata` 可放在工具命令前或后。

## 5. 出错后的恢复

| 现象 | 下一步 |
| --- | --- |
| `isError=true` / 退出码非零 | 读 `error_code` 和 `issues`，不要先解读业务数据 |
| 缺少 `birth_hour` | 向用户确认小时；当前没有无时盘入口 |
| 日期无效、未知字段、投影拼错 | 按字段路径修正后重发；不要重复发送原请求 |
| `dependency_missing` | 用 doctor 检查同一解释器，再核对具体后端/星历；不伪造成功结果 |
| 工具或资源不可见 | 检查 family/scenario 交集与当前连接的 `tools/list` |
| 有结果但近似 / `partial` | 按精度与 coverage 字段说明已算范围和缺失信息 |

CLI 错误 JSON 写 stdout，日志写 stderr；0 成功、1 模型/计算失败、2 用法错误。MCP 工具错误使用原生 `isError`，资源错误使用资源协议错误。完整错误、投影与复现合同见 [Agent 接入指南](agent-guide.md)。

## 可复现体验

维护者可在 `uv sync --locked --extra dev` 后，重跑独立 stdio、CLI 和本地 REST 流程：

```bash
uv run --locked --extra dev python scripts/experience_codex.py --output /tmp/fatebridge-experience
```

脚本用虚构资料检查多种计算、输出 Schema、裁剪前后业务摘要、错误恢复和场景范围，输出报告及原始结果。它不启动另一位模型，也不修改 Codex 配置；实际 Codex 聊天的选工具与解读质量需在连接加载后另行观察。

真实 Codex 聊天的工具选择、事实采集和解读质量可在正常连接后的人工体验中观察；项目回归测试验证 FateBridge 自身的计算和接口，不包含 Codex 宿主或桌面日志的测试。
