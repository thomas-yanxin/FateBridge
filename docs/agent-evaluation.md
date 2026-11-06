# Agent 行为验收

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

协议回归证明输入、输出与错误合同；真实模型验收另查技能选择、资料采集、范围与解释质量。原有用例使用虚构资料；外部公开资料须单独标记来源，不写用户真实档案，也不把模型调用放进普通 pytest / CI。

[MingLi-Bench 外部评估](mingli-bench-evaluation.md)将公开比赛资料清洗为输入质量、解释忠实度和咨询边界三层案例。默认只加载开发集，留出集按命例独立划分并显式选择；原人生答案不作为这三层的评分真值。来源核验、确定性准备、实际模型机械检查和人工语义审阅分别报告。

## 执行真实对话

先安装并登录 Codex CLI，完成当前源码的 `uv sync --locked --extra dev`，然后：

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py --case missing_hour --output /tmp/fatebridge-agent-eval-missing-hour
uv run --locked --extra dev python scripts/evaluate_agent.py --output /tmp/fatebridge-agent-eval-all
```

输出目录必须尚不存在。可重复传入 `--case` 选择任务，`--timeout` 控制每例时限，`--codex` 指定可执行文件。宿主提供有效的 `CODEX_CLI_PATH` 时优先使用该路径，否则查找 PATH 中的 `codex`；需要固定桌面版本时显式传入已核实的 `--codex` 路径，并核对输出中的 `cli_version`。`--model` 只在需要明确比较模型时使用。运行会消耗已登录账号的模型额度。

每批先冻结当前 AGENTS.md、Skills、接口合同与后端源码，每例从同一快照创建独立临时项目，通过当前解释器和快照的 `PYTHONPATH` 启动真实 stdio MCP，使用只读沙箱。禁用 Apps、插件和自动安装依赖，忽略无关用户连接配置，认证仍由 Codex 自身处理；使用该 CLI 的默认模型，不修改用户配置。宿主全局技能与指令仍可能参与，日志中的上下文预算或宿主警告应保留，不能把该测试称作脱离宿主的纯模型测试。

任务数据在 cases.json（本地数据：`../tests/fixtures/agent_behavior/cases.json`）；预期不进入模型提示。覆盖直接/间接技能选择、缺小时、明确不知道、工程与普通整理负例、概念解释、完整导出、医疗择时边界、更正生时、无罗盘的镜床关系、限定的多主题画像，以及印占 D1/D10、D9 生时敏感性、Vimshottari 主次运和不支持的配置。后续多轮复用与更多边界仍需按真实失败案例补充。

德国中点与 13 等分盘另有 5 个虚构用例（本地数据：`../tests/fixtures/agent_behavior/other_chart_cases.json`）：原文解释的生时条件、指定时刻推运 MC、假设天体与重复证据的错误前提、13 分区的跨界和天文星座区别、完整同 run 文件交付。全部为**单轮用例**，不冒充跨轮验收；评分标准在运行前保留于文件中。时间参数按实际时刻比较，等价时区偏移不判错；完整导出只允许一次成功排盘，合法失败后的恢复不计成重复成功。

梅花另有[10个解释忠实度诊断案例](meihua.md)。`--prepare-only` 只冻结材料与真实MCP参照，不启动模型；获授权的模型运行可为指定案例留存实际MCP回执与同run分页，机械通过和人工语义审阅继续分开。

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py \
  --cases-file tests/fixtures/agent_behavior/other_chart_cases.json \
  --output /tmp/fatebridge-other-chart-agent-eval
```

此命令启动独立 Codex 模型执行，须遵守当前会话对新增代理的授权限制。用例准备、参数校验和普通 pytest 均不代表已经运行真实模型；未生成并审阅实际轨迹前，解释语义验收继续记为未完成。授权运行后仍需逐项核对回答、真实 MCP 结果和引用来源，不能只因上述机械检查通过就宣称解释完全忠实。

Witte 1923 子午宫表另有一份虚构用例（本地数据：`../tests/fixtures/agent_behavior/other_chart_meridian_cases.json`），预先固定八条人工判据：赤经与黄经间隔、赤道上升点与实际 ASC、基础宫制身份、两种 TT 及路径恢复状态、实际应用的偏移、生时样点、原典含义与预测边界，以及模型实际回执的逐句核对。可以仅冻结材料并捕获真实 MCP 参照：

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py \
  --prepare-only --snapshot-profile runtime \
  --cases-file tests/fixtures/agent_behavior/other_chart_meridian_cases.json \
  --output /tmp/fatebridge-meridian-agent-preparation
```

`--prepare-only` 不启动模型。参照 run 与未来模型的实际 run 分开保存；不得拿准备阶段的参照冒充模型读取的证据。该用例已完成参照准备，`model_invocations=0`、`semantic_acceptance=not_run`，没有因此提高解释忠实度或现实效果评级。

年长钥匙另有原典失败与时角单位用例（本地数据：`../tests/fixtures/agent_behavior/other_chart_key_cases.json`），预先固定八条人工判据，重点核对当前 365.25 日钥匙、历史例与当前盘身份、两个有符号残差、时角时间秒、日期标签未裁定状态及整链失败。该用例使用相同 `--prepare-only --snapshot-profile runtime` 流程，并将 `--cases-file` 改为该文件以取得真实 MCP 参照；模型调用和人工语义评分均未执行。源算术检查失败、检测器测试通过和模型解释通过是三个分别验收的结果。

## 判据与证据

输出保存每例的 `events.jsonl`、`answer.txt`、错误日志和 `grade.json`，汇总含 CLI 版本、运行依赖版本、任务集与全部冻结来源的文件散列、耗时及工具参数。`source/` 与 `source-manifest.json` 保留技能 YAML、合同、实际执行的后端和评估脚本自身，避免并行开发使同一批用例执行不同代码，也保留评分实现供复核。自动判据检查工具范围、必须调用、已确认输入、是否先投影完整导出，以及技能文件读取是否可观察；宿主没有返回可解析工具事件时不能把必调案例判为通过。

每例另有人工作答标准：核对实际工具结果是否支持解释，是否乱补事实/时间、是否重复追问、是否把概率或现实建议当作计算结论。自动通过只记 `mechanical_checks_passed`；人工审阅前不宣称整体咨询质量通过。

对比改动前后时固定 CLI、模型选择、数据集与评分标准，保留原始轨迹，并核对是否有超时、工具未加载或全局技能预算告警。不同模型或宿主的结果分开报告，不把一次通过扩成所有客户端已验证。

官方依据：[技能测试](https://developers.openai.com/plugins/build/skills#test-the-skill)、[Agent 评测](https://developers.openai.com/api/docs/guides/agent-evals)。`strict_fields` 检查输出投影路径，不能当成 [OpenAI function calling strict 模式](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)。

太乙与三式另有[13个解释忠实度案例](taiyi-sanshi-audit.md)，含52条预先固定语义要求，覆盖实际四计、来源差异、三值条件、天地盘推步、合参和完整同run交付。一个历史配置范围外案例按`expected_tool_errors`登记准确类型和值；`--prepare-only`可留存真实预期拒绝并继续其他参照，不将报错伪装成成功盘。常规工具错误仍失败，预期拒绝的空答、错误原因不符、回退成功或超过`max_total_calls`也失败。新评测说明及判据不进入模型工作目录；准备和真实模型评分仍分开。

机械评分统一使用当前 `grade_case/observations`：实际工具调用、预声明的允许范围、参数与成功次数共同核对；只有用例预先声明且实际返回类型完全相符的错误才可作为预期拒绝接受。当前记录保存 `observed_calls_and_declared_errors_v2`，不分发到旧评分器，也不保留旧函数 AST 白名单。机械通过仍不等于语义或预测通过。

西方占星另有[八个解释忠实度诊断](western-astrology.md)，预先固定44条人工要求。准备仅捕获参照，不启动模型；必须核对未来模型实际读到的同run回执。Marks双方个人盘、来源拒绝与末端缺失事件、历法／闰秒、宗派／行星时以及象征推运均分别验收。
