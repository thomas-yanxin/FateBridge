# 八字解释验收的评分规则隔离

此前的节气交付验收（本地数据：`validation/bazi-term-offset-local-v1.json`）记录了一个真实失败：共享评分器后来增加预声明拒绝、实际响应采集核对与调用总数检查，改变了`grade/observations`的AST。原三批八字不能因此自动改用新规则。修复前再次验证（本地数据：`../tests/fixtures/bazi_grader_policy_v1/pytest-before-first-failure.log`）仍为42通过、1失败，原守卫及失败均保留。

## 实际执行规则

冻结方案（本地数据：`../tests/fixtures/bazi_grader_policy_v1/protocol.json`）先保存共享评分器、原始归档评分器、既有测试、三个完整批次的散列及全部验收门槛。本次没有修改原`tests/test_bazi_first_model_grades.py`，也没有用别名、包装器或重新赋值让它看见一份不会被调用的旧代码。

| 预先登记的用例合同 | 实际函数与版本 | 保留的判断 |
| --- | --- | --- |
| 未声明`expected_tool_errors`或`max_total_calls` | 原`grade/observations`，`observable_tools_v1` | 三个原函数AST与首批源码相同，工具范围、参数、技能、未恢复错误和成功计算次数门槛保持 |
| 已声明上述新增合同 | 显式`grade_expected_errors/observations_expected_errors`，`expected_errors_v1` | 保留此前新增的精确类型和值匹配、实际采集响应核对及调用总数门槛；除显式函数名外，规则AST保持 |

`grade_case`是实际运行入口的分发函数，仅按运行前的用例合同选择规则。模型响应、是否通过、`capture_payloads`或输出里的版本文字不能选择规则。新运行记录增加`grading_policy`，便于审阅实际使用的版本。旧33例没有这些新增合同，始终调用原评分函数；旧规则下，结构化错误仍按原门槛失败。

预声明拒绝测试只将调用改为显式的新API，全部断言、错误类型和值不变，整份测试AST经名称规范化后与修复前相同。该测试的改名不影响原八字守卫或用例。旧评分器函数体保持原状，以独立`.pyi`接口声明参数类型，另核对存根与实际签名；没有为通过类型检查改写冻结函数的AST。

本审计文档属于评审材料，已从受测模型工作目录排除；完整审阅来源继续保留它，计算说明等运行指南仍可读。该隔离有独立回归，不是操作系统级的保密认证。

## 原三批和执行入口回放

首次修复审计（本地数据：`validation/bazi-grader-policy-first-v1.json.gz`）及增加运行时身份核对后的审计（本地数据：`validation/bazi-grader-policy-accepted-v1.json.gz`）保留33例完整结果。每例分别使用冻结原评分函数和实际现行入口重算，并比对原报告的全部评分字段，包括工具调用、参数、原始状态、命令、失败原因及人工标准；机械成绩仍为10/11、10/11、11/11。首轮综合误用工具和第二轮桃花缺少指定计算继续失败，没有重写报告、作答、模型轨迹或逐句审阅。

实际入口`run_case`另执行10个**合成CLI事件和采集日志的离线控制用例**：正常成功、原综合错用工具、未恢复失败、合法恢复、采集不符、预声明拒绝、拒绝原因不符、缺少采集、重复尝试，以及旧规则不能借用拒绝豁免。原始事件、合成日志、实际调用的规则及结果均保存；只有预先声明应通过的3项通过。这里验证执行控制流，不是新的模型答案、独立服务器观察或解释准确率样本。

实际stdio MCP、响应采集及预声明拒绝参照仍由既有`test_agent_capture.py`和`test_agent_expected_errors.py`单独验证。审计还拒绝仅保留函数名的包装器、其他来源的同名函数、通过数量相同却篡改调用事实，以及借API改名修改原断言的情况。

## 原典条件与验收边界

19例同次复算（本地数据：`validation/bazi-grader-policy-focus-v1.json.gz`）逐例保留身、印、实体根、月令条件、原文日序及全部通关路径。未取整收支均可对账；原19例仍未解。仅ML-02有所选原文节后日序，其他18例仍未知；没有一个可唯一恢复的绝对出生瞬间，司令干与有效通关继续未裁定。

完整来源队列（本地数据：`validation/bazi-grader-policy-source-corpus-v1.json.gz`）仍为25组349记录、303个不同四柱输入及26个不同输入分歧，所有349份结果与上一轮完整队列相同。21项既有力量、证据与时间依赖文件散列相同；旺衰公式、权重、门槛和标签未改。

原首次焦点对象在后续版本新增了27处六冲解释字段，因此本次误断言整个对象相同的首次审计失败也保留；逐项旧值、身印与通关摘要相同。共享需求台账的并行追加同样使整个文件字节相同的断言失败，状态逐项保持；没有把历史对象重写成当前对象。类型存根首次把`command_for`参数误写为`target`，签名检查拒绝，原失败和存根均留存，现按实际`output`修正。

本地结果见验收回执（本地数据：`validation/bazi-grader-policy-local-v1.json`）。本次修复的是验收规则身份与执行隔离，不增加原典符合数、模型逐句忠实度或独立专家验收信用。新增节气字段仍未追加真实模型解释批次；现实预测无真实数据，继续`not_tested`，总体完成和权威认证均未成立。

## 复算

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_grader_policy --output /tmp/bazi-grader-policy.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_grader_policy.py tests/test_bazi_first_model_grades.py tests/test_agent_expected_errors.py
```

此审计不启动模型，输出路径已存在即拒绝覆盖。
