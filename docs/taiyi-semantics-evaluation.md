# 太乙／三式的解释忠实度评测

这批13个虚构单轮案例检查助手是否忠实解释实际计算，不检验现实预测能力，也不是独立古历或原典计算验收。52条语义要求在模型作答前冻结，只有操作合同和用户问题进入模型提示；评分要求、预备参照和过去答案不进入其工作目录。

案例由本项目的Codex处理者制定，处理者已知当前实现和旧差异；这是开发诊断，不是独立人类专家裁定或从未用于开发的外部留出集。后续运行保留全部案例、失败、未运行及未裁定项，不选较好的配置或子集报满分。

## 固定案例

| 案例 | 固定请求 | 核对重点 |
| --- | --- | --- |
| `taiyi_civil_lunar_year_boundary` | 2026-02-04年计 | 民用农历岁首、四柱年、实际主客算与粒度 |
| `taiyi_source_count_not_actual_count` | 1938-07-01年计 | 实际算路、原表和源位置重算不互换 |
| `taiyi_five_generals_blocked` | 1900-07-01年计 | 真实阻断及三值合取 |
| `taiyi_five_generals_unknown` | 1904-07-01年计 | 未决不当作通过或否定 |
| `taiyi_five_generals_matched` | 1913-07-01年计 | 五将匹配不代替另一门层 |
| `taiyi_shiji_zero_intervals` | 1925-07-01年计 | 天地盘、零间隔和主客算分开 |
| `taiyi_day_is_implemented_and_scoped` | 2026-07-01日计 | 已实现日计、零时边界、实际十精与未知 |
| `taiyi_full_hour_accumulation` | 2026-07-01金钥匙时计 | 完整积时与捷数、定计和原例异数 |
| `taiyi_month_profile_not_switched` | 2026-07-01金钥匙月计 | 指定起元、节月、门段差异，不换法 |
| `taiyi_matrix_lookup_not_joint_victory` | 2026-07-01年计 | 查格、原栏结果与实际条件不混 |
| `sanshi_day_scope_and_correspondence` | 2026-07-01，太乙日计合参 | 三系实际时间层与方位对应、联合未实施层 |
| `sanshi_complete_same_run` | 同上，完整JSON | 一次成功计算、实际同run文件与散列 |
| `taiyi_historical_range_refusal` | 2026日期＋381—385历史年表配置 | 如实拒绝范围外输入，不回退或重试 |

各例时刻固定12:00、偏移`+08:00`、不校正真太阳时；详细输入及全部语义要求见冻结案例（本地数据：`../tests/fixtures/agent_behavior/taiyi_semantic_cases_v1.json`）。三种五将状态按1900—1971完整软件周期中各状态首个年份选取，选择表单独留存，不是独立古例；完整年盘的三门状态仍以实际MCP回执核对，不用未附门盘的内部辅助结果代替。

## 准备与运行分别验收

```sh
uv run --locked --extra dev python scripts/evaluate_agent.py \
  --prepare-only \
  --snapshot-profile runtime \
  --cases-file tests/fixtures/agent_behavior/taiyi_semantic_cases_v1.json \
  --output /tmp/fatebridge-taiyi-agent-prepared
```

准备只冻结当前源、操作提示和隐藏判据，再通过冻结后端的真实stdio MCP取得参照。预备参照只是准备证据，不能冒充模型自己调用的结果，也不是历法／原典的独立正确答案。准备阶段`model_invocations=0`、语义为pending；实际解释评分另检查模型调用所获的`mcp-calls.jsonl`、回答及同run交付物。

边界案例预先登记准确的`error_code/status_code/retryable/operation/error`，只有实际返回的同类型、同值结构化错误才可作为预期拒绝。错误内容、成功盘和传输失败分别保留；错误码不同、错误原因不同、预期拒绝却得到成功、空回答或多次非可重试尝试均失败。常规案例的工具错误仍按原规则处理，不因新增边界例而放宽。

部分CLI将实际业务拒绝记为`status=failed`且省略`isError`。后续评测器只在已验证散列链的服务器捕获与同次工具、参数、实际`is_error=true`及预登记错误类型/值一致时识别这种表示；CLI原状态不抹去，没有匹配捕获的失败不能据文本猜成正确拒绝。初批旧评分保留，不以补丁回写历史成绩。

源快照改为逐文件核对和复制，保持复制前／中／后的指纹检查，不将整套历史验证档案同时读入内存。源在复制中变化就拒绝该快照，不能拿混合版本继续评测；不删除旧记录或既有源材料。

显式`--snapshot-profile runtime`保留全部`src`后端与运行数据、全部技能、公开操作文档和合同、锁文件及评分代码／相关测试，仅排除`docs/validation`的旧评分与嵌套源档案。默认`full`保留原完整快照范围；两种选择都继续做源一致性校验，选择记录于准备报告并传给后续运行。旧档案未从原仓库删除，运行源选择也不改变13例或52条要求。

准备完成后，`proposed-execution.json`给出基于同一冻结源及案例的准确命令。真实运行会启动独立Codex模型并使用当前账号额度，须先符合当前会话的代理授权要求；不通过改用另一个模型通道绕过该限制。运行默认CLI模型、只读本地FateBridge，首个执行失败即停止并保留剩余未运行案例。此限制不是咨询技能要求再次确认普通计算。

## 评分与边界

机械判据检查工具范围、实际输入、成功／拒绝状态、次数和导出投影；机械通过不等于回答语义忠实。逐条语义审阅须填写原回答引句、模型实际run_id、实际回执字段路径及审阅者身份；没有证据或尚未阅读保持pending，不自动按关键词给通过。

默认响应预算保留，同run分页及运行凭据按实际返回核对；不以另一次重算参照补全模型遗漏。不得因某项未知而否定已返回的可答事实，也不得因为原文写主胜／客胜就应用尚未满足的完整条件。

评测方法参考[OpenAI的评测最佳实践](https://developers.openai.com/api/docs/guides/evaluation-best-practices)及[Agent工作流评测](https://developers.openai.com/api/docs/guides/agent-evals)，采用任务具体判据、边界案例和实际轨迹审阅。它们是评测方法资料，不是太乙原典或预测有效性的认证。

本批记录见V25验收材料（本地数据：`validation/taiyi-jinjing-v25/README.md`）。完整古历、指定原典及解释忠实三个目标仍按原总清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续验收；本批开发诊断即使将来全过，也不能单独认证全部场景、部署或现实效力。

首批获授权后已实际运行13例，全部正常结束作答；原严格机械0/13通过，52项作者语义审阅为50通过、2未满足。完整原失败保留，并单列入口选择、默认参数等价及CLI业务拒绝表示的判据问题。两项语义未满足均为冻结复合判据要求的范围说明遗漏，超出用户仅选读两项十精／说明当前定计的直接请求；不把这种遗漏改称当前数值错误，也不删判据报满分。冻结后的路由和评测器修补不能沿用旧模型回答验收。
