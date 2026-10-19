# 双人评分的计算与版本追踪

双人综合分使用 `compatibility_weighted_rules_v1`。它将五项规则分数按关系类型加权，
表示模型内部的结构评价，不是现实关系的成功概率。

## 分项、权重与舍入

| 关系类型 | 五行平衡 | 喜用互助 | 十神关系 | 格局协同 | 传统分析 |
| --- | --- | --- | --- | --- | --- |
| 一般 `general` | 0.25 | 0.35 | 0.22 | 0.13 | 0.05 |
| 婚姻 `marriage` | 0.25 | 0.35 | 0.17 | 0.18 | 0.05 |
| 合作 `business` | 0.15 | 0.32 | 0.35 | 0.13 | 0.05 |
| 朋友 `friendship` | 0.35 | 0.30 | 0.20 | 0.10 | 0.05 |
| 家庭 `family` | 0.25 | 0.30 | 0.20 | 0.20 | 0.05 |

总分先求各项 `score × weight` 之和，再截到 0–100，按 Python `round(..., 1)`
保留一位小数。独立传统净分 `traditional_compatibility` 不加入综合分，
与上表中的传统分析维度分开读取。

## 计算回执

`summary.scoring` 记录本次实际使用的输入版本和分项：

- `method_id`：关系加权规则版本。
- `input_methods.person1/person2`：旺衰模型、分类、状态及喜用解析策略。
  无版本信息的输入标为 `unversioned`。
- `dimensions`：每项实际使用的 `score/weight/weighted_score`。
- `unrounded_score`：最终截取、舍入之前的总和。
- `rounding`：最终显示分数的截取和舍入规则。

回执记录原计算，不另行打分。旺衰或喜用模型变化可改变喜用互助、十神承接及
事件分类，即使四柱、五行结构计数和关系权重保持相同，总分也可能变化。
比较版本时，应分别核对输入模型、逐项得分、权重和加权贡献。

旺衰与喜用的计算范围见[八字判定说明](bazi-assessment.md)。
`strength_status=rule_based` 不代表喜用层已无条件成立；
喜用层仍单独记录 `useful_assessment_status=conditional`。
条件项和未列为喜的元素不能自动作为忌避。

## 解释范围

格局协同会消费合并事件中的个人内部事件，综合分因此不等同于纯跨人互动分。
单方喜用命中的事件分类是工程规则，不能据此断言另一方现实中承压。
模型版本、固定命例符合度或参数稳定性均不证明现实预测效力。

## 回归依据

固定输入、五种关系权重和逐条加减项保存在
[`compatibility-score-reference.json`](../tests/fixtures/compatibility-score-reference.json)。
[`test_compatibility_score_provenance.py`](../tests/test_compatibility_score_provenance.py)
使用独立十进制账本核对历史与当前输入、单人输入升级的影响、分项贡献、
旺衰与喜用版本，以及 REST、MCP、CLI 的计算回执。

```bash
uv run --locked --extra dev pytest -q \
  tests/test_compatibility_score_provenance.py \
  tests/test_compatibility_structure.py \
  tests/test_relationship_and_career_semantics.py
```
