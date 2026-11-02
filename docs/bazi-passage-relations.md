# 通关的同次关系条件

通关节点不能只显示一个合绊概括状态。同次计算已经记录的争合、半合、条件转化、冲刑及零效果，需要分别交付，才能解释实际路径仍缺少哪些条件。本次新增`classical_passage_relations`，原路径、身印预算、月令司令及旺衰结果保持。

## 原典与首次范围

本次重新目读1947年李雨田校订《任注滴天髓阐微》〈通關〉原PDF197–200页；完整章节与前后页见固定书影（本地数据：`../tests/fixtures/bazi_passage_conditions_v1/passage-original196-201.pdf`），页图、逐页观察及来源散列见来源复核（本地数据：`../tests/fixtures/bazi_passage_relations_v1/source-review-first.json`）。书影分别讨论隔位、合住、冲坏及原局与岁运引通，未给出本模型的数值系数。本次仅补齐解释所需的同次工程条件，不据此裁定有效通关。

冻结方案（本地数据：`../tests/fixtures/bazi_passage_relations_v1/protocol.json`）先于修复，首次完整依据（本地数据：`../tests/fixtures/bazi_passage_relations_v1/baseline-first.json.gz`）保留全部349条已有结果。其同次旺衰回执共有626次关系事件，包含17种关系与状态组合；原专题证据没有逐项交付这套通关条件。上述数目含重复输入，不是626个独立算错案例。

## 关系与载体分别保留

新字段逐字保留`assessment.relations`的事件、顺序、状态及附加参数，不挑选有利事件或把待审状态改成成化。引用以同次事件序号连接实际通关节点：

- 透干合只直接连接涉及的透干节点，不套给同柱藏干。
- 藏干的支关系连接自身物理载体；透干的支关系连接已给同五行根账本所在柱，不能只查透干坐支而遗漏别柱的根。
- 零剩余根所在柱仍保留关系条件；未知根账本为`null`，已给空账本为`[]`。
- 未知关系种类保留原事件并另列未分类引用，不猜干支层或效力。

`binding_state=no_binding_recorded`仍只是没有已记合绊；它不能代替这些条件。`effective_passage`继续为`not_adjudicated`，新增上下文的`calculation_effect`为`none`。

新依据链版本为`bazi_position_prerequisites_v2`，完整执行须携带关系上下文和全部实际节点；缺失时在投影前报错。旧版本结果与合法部分投影仍可读取。原`ClassicalPassage`的字段、Schema与所有旧值不变，新上下文使用独立类型。

## 实际读取与验收

综合`analyze_destiny`、标准命盘`bazi_birth`及九专题都有`passage_relations`任务视图；取其公开`fields`，不把视图名当请求参数。该视图同时包含原典来源、原通关汇总和完整关系上下文。较大结果读取同一run的`result_delivery`，核对载荷散列，不重算替换首次结果。综合实际有MCP／CLI，其余十入口另有REST，共32个协议面。

全部349条回放（本地数据：`validation/bazi-passage-relations-closure-v1.json.gz`）核对原始事件及全部旧命理值保持。原19例逐例复核表（本地数据：`validation/bazi-passage-relations-nineteen-review-v1.md`）分列工程身量、印量、原文司令时序与当前状态；239条字段陈述（本地数据：`validation/bazi-passage-relations-nineteen-review-v1.json`）逐项对照同次记录，未补造出生时刻。它是开发者字段与措辞自检，新增真实模型解释验收及独立专家验收仍未完成。

后续发现上述记录复制的史例历史附注误把己写成印：戊日的月干己为劫财，午中丁才是正印。239条直接字段陈述没有覆盖这句附注，不能用其通过结果认证附注无误。更正记录（本地数据：`validation/bazi-nineteen-role-notes-first-v1.json`）保留原句及同次十神出现项；原JSON、标签和计算结果均不覆写。

新增49项测试在源码和冻结wheel中分别通过，覆盖未知与空值、跨柱根载体、零预算、未分类事件、错误上下文拒绝、全部实际入口及同次分页恢复；925份必需包文件与构建快照相符。相关303项回归为293通过、10失败：原通关视图8192字符不分页门槛仍未通过。没有删除环境指纹、原典来源或分页标记来提高分数，原断言与首次失败保留。

完整原典回放（本地数据：`validation/bazi-passage-relations-source-corpus-v1.json.gz`）仍为25组349记录、303个不同输入、26个不同输入分歧，原19例全未解；本轮没有新增数值修复、原典符合例或实际模型调用，现实预测继续`not_tested`。构建、质量检查及固定源码范围分别记入本地回执（本地数据：`validation/bazi-passage-relations-local-v1.json`），不冒充全仓或部署验收。

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_passage_relations --output /tmp/bazi-passage-relations.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_passage_relations.py
```

审计拒绝覆盖已有输出。
