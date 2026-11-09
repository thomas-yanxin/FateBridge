# Agent 行为验收

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

协议回归检查输入、输出与错误合同；真实模型验收检查工具选择、资料采集、范围与解释质量。模型调用不进入普通 pytest 或 CI。历史运行与评分保存在仓库外，当前验收使用明确指定的任务文件。

## 执行真实对话

任务文件使用 `cases` 列表。每例包含唯一 `id`、用户请求 `prompt` 和人工判据 `manual_review`；按需声明 `allowed_tools`、`required_any`、已确认参数与 `reference_request`。计算交给真实 MCP，不把预期答案或人工判据放进模型提示。

完成 `uv sync --locked --extra dev` 后，先准备参照，将下方路径替换为实际任务文件：

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py --prepare-only \
  --cases-file /absolute/path/to/current-cases.json \
  --output /tmp/fatebridge-agent-preparation
```

`--prepare-only` 冻结源码、任务和真实 MCP 参照，不启动模型。实际对话需要已登录的 Codex CLI；在任务授权范围内移除该选项并使用新的输出目录即可运行，会消耗已登录账号的模型额度。普通任务必须传入 `--cases-file`。

输出目录必须尚不存在。可重复传入 `--case` 选择任务，`--timeout` 控制每例时限，`--codex` 指定可执行文件。宿主提供有效的 `CODEX_CLI_PATH` 时优先使用该路径，否则查找 PATH 中的 `codex`。默认沿用 CLI 的模型，只有显式比较模型时才传 `--model`。

每批冻结 `AGENTS.md`、方法参考、接口合同、后端源码与运行器；每例从同一快照创建独立临时项目。真实 stdio MCP 使用当前解释器和冻结源码的 `PYTHONPATH`，保留已选择的星历配置与原工作目录。模型使用只读沙箱，忽略用户连接配置，并禁用 Apps 和插件。宿主指令仍可能参与，运行日志应保留相应警告。

源码快照排除本地历史报告、工作草稿、日志和缓存。任务可用 `evidence_files` 明确指定只读证据及其目标路径，所选证据仍按声明冻结。评分标准留在模型工作目录之外。

[MingLi-Bench 外部评估](mingli-bench-evaluation.md)提供有固定来源的输入质量、解释忠实度和咨询边界任务，默认只加载开发集，留出集按命例独立选择。原比赛人生答案不作为这三层的评分真值。

## 判据与证据

每例保存 `events.jsonl`、`answer.txt`、错误日志和 `grade.json`。批次保存 CLI 与依赖版本、选中和未执行案例、任务文件、源码清单、耗时及实际工具参数；`source/` 保留实际执行的后端和评分实现。

当前机械评分版本为 `observed_tool_contracts_v3`，检查允许工具、必须调用、已确认输入、调用次数，以及完整导出时首次调用是否保留全部字段。工具报错默认失败；任务可用 `expected_tool_errors` 预先声明准确的错误类型和值。空答、错误原因不符或未恢复的普通工具错误均不能通过。

自动通过仅记为 `mechanical_checks_passed`。人工审阅需逐项核对实际回答是否由模型收到的同 run 回执支持，是否补造事实、重复追问、混淆传统解释与现实建议；准备阶段的参照不代替模型实际读取的证据。源码可复现、机械通过、解释忠实和现实预测分别验收。

比较不同修改时固定 CLI、模型、任务与判据，保留原始失败及未执行案例。声明 `expected_skill` 或 `expected_skill_sets` 的历史任务须使用原版评测器复核。不同模型和宿主分别报告。
