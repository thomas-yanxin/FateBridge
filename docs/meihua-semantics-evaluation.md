# 梅花解释忠实度验收

本文分别记录原10案、1.6.0六案和当前1.7.0的28案虚构单轮诊断，检查模型解释与实际MCP结果的对应。各批版本、首次失败与待审分母分别保留；它们不测现实命中率，也不因有限用例全部通过而认定所有输入或所有模型的解释满分。

方法区分三个问题：[NISTIR 8312](https://www.nist.gov/publications/four-principles-explainable-artificial-intelligence)区分解释是否反映实际过程与决定本身是否正确；[AIS](https://aclanthology.org/2023.cl-4.2/)提供对照已识别来源检查归因的研究框架；[FActScore](https://aclanthology.org/2023.emnlp-main.741/)将长回答拆成可核对的原子事实。本批借鉴逐条核对的思路，不声称实现这两个正式指标，也不把引用数量当忠实度。

## 固定案例与准备

任务与私有判据在 meihua_semantic_cases.json（本地数据：`../tests/fixtures/agent_behavior/meihua_semantic_cases.json`）。模型只收到其中的 `prompt`；预期判据不复制进模型工作目录，不拼进提示。目录只读与不访问外部服务的约束仍受宿主影响，不冒称隔绝了所有全局技能或文件访问。

覆盖范围为春节／立春边界、酉时原数、物数两种口径、纯乾候选取互、天气已受制／范围未决／缺失季节、实际动爻经文、现实确定性追问和已明确未知的时支。所有批次保留全部选定案例，不能删除失败、未运行或无输出的项来改变分母。

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py \
  --cases-file tests/fixtures/agent_behavior/meihua_semantic_cases.json \
  --prepare-only --output /tmp/fatebridge-meihua-semantic-preparation
```

准备命令不启动模型。它冻结后端、技能、文档、评估器和完整数据集，用真实独立stdio MCP保存9份完整参照回执；缺时支的负例不计算。它输出模型提示、30条待审阅判据及具体执行命令。参照回执是解释应对应的程序结果示例，不是独立历法／原典预期，也不是未来模型实际读取的同一run。

## 1.6.0新增季节句的诊断语料

六个新增虚构案例（本地数据：`../tests/fixtures/agent_behavior/meihua_seasonal_semantic_cases_v6.json`）另固定18条待审判据，覆盖冬坎有离、春土雨与受制坎雨分开、秋金晴与受制离晴分开、兑／艮版本差异、未知季节及取爻候选各自有无坎。它们在实现后整理，属于诊断语料，不冒充未见验收集。

这六案已另完成准备与留证（本地数据：`validation/meihua-seasonal-semantics-preparation-v6.json`）：冻结当前后端与资料，保存6次真实stdio参考回执及其日志链，18条判据仍全部待审，实际模型调用为0。参考回执不是模型实际读取的同一run，不能计作模型解释通过。原10案归档及其版本范围保留，不合并分母。需要另建准备批次时可用：

```bash
uv run --locked --extra dev python scripts/evaluate_agent.py \
  --cases-file tests/fixtures/agent_behavior/meihua_seasonal_semantic_cases_v6.json \
  --prepare-only --output /tmp/fatebridge-meihua-seasonal-semantic-preparation
```

上述命令只准备材料；模型执行仍须满足当前会话的明确授权要求。

## 1.7.0的28案与引用绑定

当前诊断集（本地数据：`../tests/fixtures/agent_behavior/meihua_current_semantic_cases_v40.json`）逐对象保留原16案，另加12案，覆盖金银／兵器反例、原数／卦序候选、阻节日数的明例与类推、未知事情境、子初／午夜日气、月气与日气分列、雪与雨偏好的区分、分时天气象及研究分数。新增案例在实现后整理，属于诊断材料；35条字段断言在本批参考调用之前固定，不是独立历法或原典真值。

固定后端已取得27份真实stdio参考回执，一项明确未知时支的案例不计算；28案的84条语义判据全部待审，模型调用为0。当前连接未刷新，不能用这些本地回执替代当前聊天MCP验收。旧1.6.0六案仍为6份参考、18条待审，旧提示未展示工具限制，故只保留参考绑定，不宣称旧模型执行合同就绪。

[绑定核对器](../src/fatebridge/validation/meihua_semantic_binding.py)提供两种检查，均不启动模型：

- `preparation`核对外部另行固定的清单、源码、提示、实际服务器日志、输入类型、run及完整业务摘要；只返回参考绑定状态，语义保持`not_run`。
- `answer`核对已保存回答的逐字区间、该进程实际收到的同run字段及完整读取的资源页。支持协议`text`和FastMCP服务器`content`、普通与verified分页；未读内容、残页、错run、改写原句、服务器错误、未知变否定及布尔／整数替换均不提供通过证据。新增事情境缺项约束另行核对，原机械评分函数保持不变。

例如已冻结准备目录可这样只读重放，摘要须从另存回执取得，不能临时对待检查文件重新算一个散列冒充信任锚：

```bash
uv run --locked --extra dev python scripts/audit_meihua_semantic_binding.py \
  preparation /path/to/preparation \
  --commitment /path/to/preparation-commitment.json \
  --expected-commitment-sha256 3c5699b617fabf1d65400e4f646ca8a212b09d0ffc9be4edfa5c13a1547d83cf
```

该命令的退出0只表示绑定核对成功。回答检查使用另存的回答、日志、所选原句清单散列和参考run黑名单；`semantic_acceptance`仍为`not_assessed`，还需人工或明确标注类型的审阅者判断语义、遗漏、候选与现实断言。空原句清单不能代替覆盖审阅，源码回执也不能证明模型内部确实理解了字段。新增约束、失败与固定副本验证见本轮记录（本地数据：`validation/meihua-semantic-binding-review.md`）。

## 模型运行与实际回执

独立模型执行遵守当前会话对新增代理的明确授权要求；准备材料不等于已运行。获授权后使用准备目录 `proposed-execution.json` 的冻结入口与参数，默认模型不另改配置。该批设置 `--stop-on-execution-failure`：账号或模型入口拒绝、超时等执行失败后停止，其余案例保留为未运行，拒绝不能计为成功，也不连续重试同一不可用入口。

`capture_payloads=true` 仅为这些案例选择 `fatebridge.validation.agent_capture` 服务器，显式指定新的私有日志路径。正常FateBridge服务器不启用留证。日志保存实际MCP参数、返回的结构化回执、错误和结果分页读取；与CLI事件中的调用按参数核对，缺失、损坏或不一致均不能机械通过。日志的序列与内容哈希只提供本地一致性检查，不是外部认证或防篡改签名。

模型回答的解释必须对照该模型进程自己的 `mcp-calls.jsonl`，核对其中的 `run_metadata.run_id`、返回字段和已读分页。不能用准备阶段另一run的结果代替；没有读取的内容不能伪装成该模型引用的依据。只读文件／CLI命令等宿主行为也要查看完整事件，服务器日志不证明宿主没有其他行为。

## 逐条审阅，不以平均分消除错误

| 项目 | 审阅要求 |
| --- | --- |
| 原子陈述 | 保留回答原句，定位实际run、候选、字段路径和值；引用原典时核对返回的版本、条款及作用域 |
| 候选与条件 | 原体、互变、计数口径分别对应；`pending_context`、制约和范围未决不得被删去，未知不能转成否定 |
| 解释层次 | 程序事实、传统含义、助手现实建议、经验效力主张分开；现代提示不能冒充经文 |
| 回答覆盖 | 每案三项判据逐项记支持、反驳、歧义或待审；只给免责声明或不回答不能因“没有错误”而通过 |
| 否决项 | 编造卦变、时支或现场事实、混用候选、把规则转成概率或保证，均单独保留，不被其他正确句子抵消 |
| 审阅来源 | 记录审阅者及其类型；模型自审或自动关键字检查不冒充独立人工验收 |

`review-worksheet.json` 初始全部为 `pending`。机械判据通过只证明可观察的工具调用／输入／留证要求，不能自动填为语义通过。审阅材料保留原句和反例；修复后另建批次，首次失败与恢复分别记录。这批诊断案例用于发现与修复问题，不能在围绕它调好后冒称未见验收集；最终范围还需新用例、重复采样、独立复核及各宿主验证。

即使有限案例的解释全部忠实，也只证明这些回答对应计算；历法、指定原典符合度和现实预测仍由各自证据验证。当前现实负结果及未来天气试验不会因这批解释评估而改写。
