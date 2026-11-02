# 通关回执的一致性验收

通关路径的五行、根状态、合绊状态和数量必须忠于同次节点。此前合同只核对部分柱位，17个刻意构造的矛盾回执仍能通过；本次补入共享输出校验，综合与九专题在摘要投影前执行。没有改变路径生成、根预算、身印能量、旺衰公式或原典标签。

## 原典依据及工程范围

本次再读1947年李雨田校订兼发行、大东书局经售《任注滴天髓阐微》〈通關〉原PDF197–200，并保留196–201页完整上下文（本地数据：`../tests/fixtures/bazi_passage_conditions_v1/passage-original196-201.pdf`）。来源记录（本地数据：`../tests/fixtures/bazi_passage_conditions_v1/source-context-first.json`）绑定完整原PDF的既有SHA-256、六页摘录及逐页像素对应。书影为同一开发者目读，未增加独立专家验收。

197–198页明确分开隔位、被合住、被冲坏及原局与岁运引通，199页“四冲反为四助”又有具体生扶关系。原文没有提供本次模型的数值系数，不能由“有路径”跳到“已通关”。本次引用它来核对解释所需条件；节点引用、集合、相生相克与同次回执一致性的校验是项目工程实现，不冒充原典已完整形式化。

## 保留首次反例

冻结方案（本地数据：`../tests/fixtures/bazi_passage_conditions_v1/protocol.json`）先于扫描计数与修复；首次发现（本地数据：`validation/bazi-passage-conditions-discovery-first-v1.json.gz`）保留349条既有生产回执及全部17个矛盾输入，首份反例（本地数据：`../tests/fixtures/bazi_passage_conditions_v1/counterexamples-first.json.gz`）不覆写。

17个输入均为人工故障注入，旧合同全部接受；349份实际计算回执中没有观察到这些矛盾。因此这是验收漏洞及故障防护修复，不是发现17个真实命例算错，不增加原典符合数、独立样本或预测准确率。

| 校验层 | 此前可通过的矛盾 | 本次处理 |
| --- | --- | --- |
| 实体节点 | 引用和天干不符、癸写成火、酉中冒出甲、藏干序位错、透干冒充藏干、引用格式错误或重复节点 | 核对实际柱位、干藏层、十干五行及原有藏干目录；不新增根 |
| 路径 | 引用不存在节点、根预算汇总与节点相反、合绊状态被替换、五行链不符、干藏层被改、本气资格被改 | 沿同次节点与已知引用逐项比较；缺失的投影上下文不补算 |
| 集合及汇总 | 重复路径计票、本气路径不在全部藏干路径中、可见／本气数量与实际列表不符 | 核对实体路径唯一性、子集关系及实际列表长度 |

修复验收（本地数据：`validation/bazi-passage-conditions-accepted-v1.json.gz`）现拒绝全部17个首次矛盾输入，349份正常回执全部保留原值且继续通过。JSON Schema结构保持相同；新增的是Pydantic运行时语义校验，不能宣称普通JSON Schema验证器也获得了这些跨字段约束。

## 三端交付与解释边界

独立进程的新旧合同对照（本地数据：`validation/bazi-passage-conditions-public-final-v1.json.gz`）使用相同当前依赖和业务代码，分别加载冻结旧合同与新合同，完整比较综合和九专题。有效业务值、文本及十个输出Schema均相同；这不代表整个历史运行环境与当前并行工作树相同。

实际REST、原生MCP和CLI分别验证正常摘要投影，以及在完整结果内注入错误数量、只请求无关摘要字段的情形。矛盾回执应在投影前成为内部合同错误，不能因未选择通关字段而隐藏。缺失节点目录或列表时保留合法部分投影；未提供根回执与已提供空根回执分别保留未知和无正剩余预算。校验不调用旺衰或路径求解器。

另发现旧`binding_state=no_binding_recorded`没有逐项携带争合、半合、条件转化等关系上下文。这句话只表示没有已记合绊，不能解释成所有来源条件已经清楚。首次统计分别保留相关节点与事件出现次数，含重复命例与同一事件的多个节点，不能把这些次数当成独立错误数。本次没有更改关系分类或采用新的通关效力规则，这项证据扩展仍待完成。

完整原典回放（本地数据：`validation/bazi-passage-conditions-source-corpus-v1.json.gz`）继续保留25组349记录、303个不同输入与26个不同输入分歧，原19例全未解；既定门槛与原测试断言保持。身印收支、月令司令未裁定、有效通关未裁定、三批真实模型结果及其首次失败也保持。本轮没有新真实模型调用或独立专家审阅，现实预测继续`not_tested`。

本地回执（本地数据：`validation/bazi-passage-conditions-local-v1.json`）分别记录源码、故障注入、协议、构建及全仓检查；局部通过不替代全仓或部署验收。

新增44项测试、相关129项回归及冻结wheel同44项用例通过；重复运行不增加独立准确性信用。另做的完整性首探（本地数据：`validation/bazi-passage-conditions-completeness-probe-first-v1.json`）发现，十工具保留必需顶层字段、将嵌套业务对象清空后，现有完整输出校验仍接受。这是另一组人工故障探测，不混入前述17项，也未在本次修复；后续需分别设计完整业务必需依据与合法部分投影的约束。它进一步说明当前合同防护尚未完整。

后续[完整结果依据校验](bazi-complete-anchors.md)保留这份首次探测，并扩查独立综合入口`analyze_destiny`。完整执行与部分输出模型分别维护，缺少计算依据在投影前拒绝；不将原标准命盘加九专题的十工具记录改写成已经覆盖综合入口。

后续[同次关系条件](bazi-passage-relations.md)补齐上述待完成的上下文：保留全部关系原回执，分列透干合与支中根载体，不更改本页所验收的旧通关字段或Schema。原19分歧、数值公式及首次8192字符门槛失败保持。

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_passage_conditions --output /tmp/bazi-passage-conditions.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_passage_conditions_public --output /tmp/bazi-passage-public.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_passage_conditions.py
```

审计拒绝覆盖已有结果。
