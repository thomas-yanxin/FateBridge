# 八字解释逐句验收

本组11个虚构、单轮用例覆盖综合和九专题，另加未知生时边界。
提示与人工标准（本地数据：`../tests/fixtures/agent_behavior/bazi_semantic_cases_v1.json`）在模型执行前固定；
每例最多一次成功计算，保留合法错误恢复与同run分页。
综合例核对三会归组与实际门槛；九专题核对岗位、财务、身心文化、子女、学业、性格、六亲、婚姻和桃花的实际依据。
不把规则计数、指数、成格候选或空命中替换成现实结局。

准备目录为`/tmp/fatebridge-bazi-v37/semantic-preparation`，冻结后端、指令与全部用例，并实际获取10份MCP参照。
第11例明确不知道生时，不计算。准备阶段模型调用数为0。
参照是另一次调用，正式审阅根据模型实际收到的MCP回执核对，未将准备参照充当模型证据。

运行器的模型工作目录现在排除`docs/validation`、`docs/reviews`及验收方案文档，
防止将历史作答、评分和测试材料复制给受测模型；完整审阅快照保留这些材料。
此措施限制工作目录内容，不是操作系统级的保密认证，也不证明历史模型曾利用这些材料。

真实执行遵守[运行器文档](agent-evaluation.md)的要求：
“此命令启动独立 Codex 模型执行，须遵守当前会话对新增代理的授权限制。”
用户显式授权全部11例后，已按准备目录的`proposed-execution.json`顺序运行，
使用CLI默认模型（`codex-cli 0.163.0-alpha.11`），首轮全部完成，未在该轮内重跑；总用时599.71秒。后续两轮完整复验分别记录如下。
实际运行源码清单与授权前准备清单完全一致，共3623项。

| 用例 | 首次机械检查 | 开发者逐句审阅 |
| --- | --- | --- |
| 综合 | 失败，工具约束不符 | 未发现超出实际回执的结论，原失败保留 |
| 事业 | 通过 | 保留十神并列、条件岗位比较及日期粒度 |
| 财务 | 通过 | 分数不转金额、收益率；未计算2027年 |
| 身心文化 | 通过 | 权重与器官文化对应不转医学判断 |
| 子女 | 通过 | 星位不转人数、性别及生育事件 |
| 学业 | 通过 | 84及并列计数不转智商、录取或成格 |
| 性格 | 通过 | 并列保留，文化类比待经历核实 |
| 六亲 | 通过 | 加权量、出现次数和现实人数/助力区分 |
| 婚姻 | 通过 | 不将旧稳定、外貌、助力标签当事实 |
| 桃花 | 通过 | 目标支与零命中区分，空合冲不当全盘无合冲 |
| 未知生时 | 通过 | 零计算，不追问、不套默认时刻 |

综合例限定`bazi_birth`，模型实际采用技能通用综合入口`analyze_destiny`。
两者不能在首轮后直接视为等价以消去失败。实际出生参数与题面一致；
机械输出的`input_mismatch:bazi_birth`由缺少指定调用连带产生，不证明出生值填错。
原工具门槛和三条机械失败均保留，整组机械验收未通过。

首次原始报告、作答、轨迹与回执（本地数据：`../tests/fixtures/bazi_semantic_run_v1/report.json`）
及归档来源（本地数据：`../tests/fixtures/bazi_semantic_run_v1/provenance.json`）保存11次首次结果。
逐句审阅涵盖204个句段和表格行、10份实际同run回执；第11例没有计算。
当前审阅索引（本地数据：`validation/bazi-semantic-first-review-v2.json`）附原文字符区间、出处路径、实际回执及每项判据，
没有把投影回执冒充完整业务散列核验。

审阅初版误加了一个不存在的学业出处路径，机械核对明确拒绝；
原初版（本地数据：`validation/bazi-semantic-first-review-v1.json`）保留。
第二版只移除错误索引，已有实际`study_stars`及`evidence_chain`保留，未改模型作答、首次评分、判据或进行模型重跑。
运行`uv run --locked --extra dev python scripts/audit_bazi_semantic_review.py --review docs/validation/bazi-semantic-first-review-v2.json`
可核对全部引文、来源与首次失败未被替换；此命令不自动判断自然语言语义。

当前审阅是同一开发者的有限逐句复核，第二位独立外部审阅尚未完成。
后端婚姻回执还含`predicted_appearance`、`spouse_personality_hint`及“稳定”等旧标签；
本次模型正确限制了其含义，不等于这些旧字段已获现实证实或全部模板均已验收。
可携带的执行源码包（本地数据：`../tests/fixtures/bazi_semantic_run_v1/runtime-source.tar.gz`）保留992个运行/评估输入；
未交给受测模型的历史审阅目录不重复打包，完整原始清单及本地完整审阅包位置另行保留。

这些是解释忠实度用例，不是原典旺衰正确率、跨轮全面验收或现实预测效度样本。

## 工具合同与初始化修复后的两轮复验

首次运行器没有将既定`allowed_tools`操作限制交给模型。现在实际提示和准备提示都由同一函数生成工具限制前缀，
不包含隐藏审阅标准、期望数值或参照回执；11例原题面、指定工具、输入和调用次数上限不变。
评分器、观察提取及参数比较函数的AST与首次归档一致，三轮33份实际轨迹均重放出原机械结果。

共享评分器后续接入预声明拒绝时曾破坏上述AST不变要求，原失败留存在节气验收（本地数据：`validation/bazi-term-offset-local-v1.json`）。现在按[评分规则隔离](bazi-grader-policy-audit.md)恢复原函数及八字实际执行路径，新增规则独立命名；33例完整评分字段再次与冻结函数和原报告一致，历史失败与原守卫未改。这项工程修复不构成新的模型解释批次。

| 独立整轮 | 机械结果 | 保留的失败 | 开发者复核 |
| --- | --- | --- | --- |
| 原首轮v1（本地数据：`../tests/fixtures/bazi_semantic_run_v1/report.json`） | 10/11 | 综合误用`analyze_destiny` | 204句段，初版错误路径与修订均保留 |
| 合同前缀修复v2（本地数据：`../tests/fixtures/bazi_semantic_run_v2/report.json`） | 10/11 | 桃花未调用FateBridge计算 | 186句段；缺实际回执的两项标准记不可评估 |
| 初始化修复v3（本地数据：`../tests/fixtures/bazi_semantic_run_v3/report.json`） | 11/11 | 本轮无机械失败 | 194句段，43项原人工标准在本次作答内通过 |

第二轮综合已正确调用`bazi_birth`。桃花例却没有FateBridge调用，随后查询其他服务资源并尝试本地回退，未完成题目要求的实际结果解释；全部轨迹、失败与作答保留。
模型自述“工具未接通”，确切原因尚未证明。运行器确实把服务设为可选；
[官方MCP说明](https://learn.chatgpt.com/docs/extend/mcp?surface=cli)列明可选服务的初始目录宽限与必需服务的等待行为，
因此按事前冻结的再验方案（本地数据：`../tests/fixtures/bazi_focus_validation_v1/runtime-repair-protocol.json`）将FateBridge设为`required=true`并启用严格配置。
没有过滤可见工具或改变评分门槛、模型、超时与计算政策，只再顺序执行一整轮11例，此后未继续重跑。

实际`tools/list`工具名和Schema散列现在进入原散列链日志，分别核对服务就绪、模型调用与计算回执。
第三轮11例均有实际目录记录，按原专题范围分别发布5–19个工具；综合例为19个。10例各一次指定计算，未知生时例零计算。
新增采集器最初误把工具列表当作单一模型对象，原单测失败及修复前源码保留；改按安装版本的实际列表转换接口后通过，未修改计算或评分。

## 同次回执与可见字段审阅

第二轮审阅（本地数据：`validation/bazi-semantic-repair-review-v1.json`）保存9次实际排盘、12份含知识查询的回执；
桃花缺回执，相关计算解释标准继续不可评估。
第三轮当前审阅（本地数据：`validation/bazi-semantic-readiness-review-v2.json`）保存10次实际排盘、16份含知识查询的回执。
两轮各有3份分页文件经过原`result_delivery.sha256`核对。文件交付散列与完整业务散列是不同核对，本审计未声称完成未投影业务散列验证。

第三轮婚姻例实际用`jq`选择读取文件字段，未把整份文件打印给模型。
审阅初版将审阅者取得的整份文件字段列为宽泛索引，初版及当时的索引通过报告保留；
收紧后的审计明确拒绝初版（本地数据：`validation/bazi-semantic-readiness-review-v1.json`）。
第二版将每个可引用字段连到实际命令输出和原文件路径，全文散列核对不替代模型可见性；未改作答、评分或标准，也未重跑模型。

```bash
uv run --locked --extra dev python scripts/audit_bazi_semantic_batch.py --artifacts tests/fixtures/bazi_semantic_run_v2 --review docs/validation/bazi-semantic-repair-review-v1.json
uv run --locked --extra dev python scripts/audit_bazi_semantic_batch.py --artifacts tests/fixtures/bazi_semantic_run_v3 --review docs/validation/bazi-semantic-readiness-review-v2.json
```

审计检查原始文件、日志链、逐句字符区间、实际回执和选择读取输出的路径；自然语言判断仍由同一开发者执行。
重复使用这11例不是新增独立样本，局部人工通过不等于全部模板、多轮或外部专家验收。
目前无真实事前队列及独立结果，现实预测继续`not_tested`，不由这三轮结果换算权威性或满分。

补充的解释回归记录（本地数据：`validation/bazi-semantic-refresh-v1.md`）和响应预算复核（本地数据：`validation/bazi-budget-guide-v1.md`）分别保留首次答案、逐句依据、默认响应预算失败与同次分页交付的分项证据。

原五例五行解释的复验准备收据（本地数据：`validation/bazi-element-revalidation-preparation-v1/local-report.json`）另行保留首次机械 0／5、四例来源版本交付不完整、原答案及冻结过程的失败。准备材料和 MCP 参照不等于实际模型复验；新增模型执行须有对应授权，原判据与首次成绩保持。
