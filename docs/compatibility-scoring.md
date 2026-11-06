# 双人评分的计算与依据

[文档中心](README.md) · [八字判定](bazi-assessment.md) · [API 参考](api-reference.md)

双人配合结果可以拆开阅读：先看各项规则怎样评价双方结构，再看关系类型如何影响权重，最后结合具体互动讨论相处与磨合。以下计算说明适用于 `two_person_compatibility` 的分数解释与版本核对。

双人综合分使用 `compatibility_weighted_rules_v3`，将五项规则索引按关系类型加权。`score_kind=uncalibrated_rule_index` 表示未校准的内部指标；它不是现实关系的成功概率，其他关系技法不适用这套权重。

个人层取用使用`source_conditions_before_preference_v3`，先核对来源条件，再确定可用的喜用与回避项，
详见[八字判定](bazi-assessment.md)。独立手算账本列出固定输入、逐条加减、封顶及关系权重，
不以旧算法输出或源码哈希作为正确答案。

首次接入先按 [API 参考](api-reference.md) 提供两人的已确认资料；关系类型未指定时使用 `general`。读取结果时依次核对[分项权重](#分项权重与舍入)、[计算回执](#计算回执)和[解释范围](#解释范围)。

## 分项、权重与舍入

| 关系类型 | 五行平衡 | 喜用互助 | 十神关系 | 格局协同 | 传统分析 |
| --- | --- | --- | --- | --- | --- |
| 一般 `general` | 0.25 | 0.35 | 0.22 | 0.13 | 0.05 |
| 婚姻 `marriage` | 0.25 | 0.35 | 0.17 | 0.18 | 0.05 |
| 合作 `business` | 0.15 | 0.32 | 0.35 | 0.13 | 0.05 |
| 朋友 `friendship` | 0.35 | 0.30 | 0.20 | 0.10 | 0.05 |
| 家庭 `family` | 0.25 | 0.30 | 0.20 | 0.20 | 0.05 |

总分用声明的十进制分项及权重求各项 `score × weight` 之和，再截到 0–100，
按十进制 half-even（恰好一半时取偶数）保留一位小数。
相克扣分须命中明确回避项，中性和未裁定不补成忌；仅一方或双方未有喜忌命中的名义合局列为 `unresolved_patterns`，不计为双向支持或承压。基础60分本身不能生成互助结论。
独立传统净分 `traditional_compatibility` 不加入综合分，
与上表中的传统分析维度分开读取。

分项在 `summary.scoring.dimensions` 中使用下列键名，便于对照原始结果：

| 中文分项 | 字段键 |
| --- | --- |
| 五行平衡 | `element_balance` |
| 喜用互助 | `favorable_synergy` |
| 十神关系 | `ten_gods_relationship` |
| 格局协同 | `pattern_synergy` |
| 传统分析 | `traditional_analysis` |

## 计算回执

`summary.scoring` 记录本次实际使用的输入版本和分项：

- `method_id`：关系加权规则版本。
- `evidence_policy/status/unresolved_dimensions`：取用证据政策、完整程度和未裁定分项；`partial` 时摘要只陈述规则索引及条件，不生成确定匹配等级。
- `input_methods.person1/person2`：旺衰模型、分类、状态及喜用解析策略。
  无版本信息的输入标为 `unversioned`。
- `dimensions`：每项实际使用的 `score/weight/weighted_score`。
- `dependency_policy/dimension_dependencies`：分项共享的出生、强弱、分布及取用依据；不是五份独立证据，不能据分项数量增加置信度。
- `unrounded_score`：最终截取、舍入之前的总和。
- `rounding`：最终显示分数的截取和舍入规则。

回执记录原计算，不另行打分。旺衰或喜用模型变化可改变喜用互助、十神承接及
事件分类，即使四柱、五行结构计数和关系权重保持相同，总分也可能变化。
比较版本时，应分别核对输入模型、逐项得分、权重和加权贡献。

完整结果还核验五个具名分项、权重和为1、逐项乘积、未舍入总和、最终舍入及摘要状态。发现接口中的方法合同登记适用前提与比较范围，供调用方核对实际方法版本。该校验验证账本一致性，不证明权重具有实证效度。

旺衰与喜用的计算范围见[八字判定说明](bazi-assessment.md)。
`strength_status=rule_based` 不代表喜用层已无条件成立；
喜用层仍单独记录 `useful_assessment_status=conditional`。
条件项和未列为喜的元素不能自动作为忌避。

## 解释范围

格局协同会消费合并事件中的个人内部事件，综合分因此不等同于纯跨人互动分。
单方喜用命中只保留该方参考；另一方效力未定时列为未决。逐人 `person_info.*.preference_assessment` 保留已选喜用、回避、条件和中性，日主相克另列 `control_evidence`；不能据此断言另一方现实中承压。
模型版本、固定命例符合度或参数稳定性均不证明现实预测效力。

实现位于 [`analysis/compatibility.py`](../src/fatebridge/analysis/compatibility.py)。追查总分变化时，先看变化来自哪一项 `weighted_score`，再核对该项的输入与规则；只比较最终分数无法区分模型升级和关系权重变化。

## 回归依据

固定输入、五种关系权重和逐条加减项保存在本地独立资料
`tests/data/compatibility/score-ledger.json`。
[`test_compatibility_score_provenance.py`](../tests/compatibility/test_compatibility_score_provenance.py)
使用有理数与十进制手算账本核对当前输入、分项贡献、
旺衰与喜用依据，以及 REST、MCP、CLI 的计算回执。

两组独立账本的输入前提不同，不能互换结果：

| 账本 | 输入前提 | 一般关系结果与用途 |
| --- | --- | --- |
| [当前来源条件账本](../tests/data/compatibility/source-condition-ledger.json) | 第一人结构判为强，身印预算为 276／709，但数值档为弱，普通扶抑取用仍待复核；喜忌不由“强”标签补出 | 当前目录的虚构示例五项为 69／77／90／52／39，加权和 72.71，显示 **72.7**，`status=partial` |
| [明确给定喜忌的字面账本](../tests/data/compatibility/score-ledger.json) | 测试显式给定完整喜用、回避和条件项 | 加权和 80.03，显示 **80.0**；用于核对所声明前提下的有限评分算术，不作为当前示例的取用结论 |

字面账本的家庭关系和为 75.85，按 half-even 显示 75.8，用来防止浮点累加误显示 75.9。十神分项原始和超过 100 时仍按原规则截到 100，截取前的逐项值保留。权重、封顶及原有字面账本没有因取用未决而修改。

```bash
uv run --locked --extra dev pytest -q \
  tests/compatibility/test_compatibility_score_provenance.py \
  tests/compatibility/test_compatibility_structure.py \
  tests/compatibility/test_relationship_and_career_semantics.py
```
