# 双人八字取证

[文档中心](README.md) · [八字判定](bazi-assessment.md) · [API 参考](api-reference.md)

`bazi_compatibility` 用双方确认的出生资料各排一次本命盘。`relationship_type` 保留咨询语境，默认 `general`。相同两张盘的关系事实在婚姻、合作、朋友、家庭与一般语境下相同。

| 字段 | 内容 |
| --- | --- |
| `natal_contexts.person1/person2` | 各自的四柱、时历、五行分布、日主工程口径、原典力量和取用状态 |
| `element_relationship` | 双方日主五行的关系 |
| `cross_chart_relations.pairs` | 逐柱的干支接触；天干相克按施克方向记录 |
| `cross_chart_relations.groups` | 三合、三会、三刑、半合、拱候选；`natal_matches` 标出单方原局已具备的成员 |
| `cross_chart_relations.directional_punishments` | 各有向跨人刑链及两端柱位 |
| `directional_ten_gods` | 两个方向各以目标方日干参照，保留来源方明干与藏干 |

三合关系按[地支成员口径](bazi-relations-audit.md)区分三字齐、含中神的半合及缺中神的拱候选。盘内已齐与跨盘共同出现可以同时记录。`effect_status=relation_only` 表示接触资格，取用与作用仍按双方各自的状态解释。

Agent 用已取得的柱位与方向组织解读，并结合当事人已确认的实际互动。旧综合分与传统净分字段已移除。固定历史账本仍见 `tests/data/compatibility/score-ledger.json` 和 `tests/data/compatibility/source-condition-ledger.json`。

实现见[双人服务](../src/fatebridge/services/compatibility.py)及[共享八字关系](../src/fatebridge/core/bazi/bazi_evidence.py)。全量交付与严格投影见[Agent 接入](agent-guide.md)。
