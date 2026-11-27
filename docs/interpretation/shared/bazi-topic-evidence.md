# 八字专题细问的证据读取

专题首次调用前先按任务选择所选工具公开 `evidence_views` 中的 `fields`（如事业 `target_year` / `depth` / `markers`），不要把卡名作为请求参数。本页说明九项专题与综合命盘的字段取证位置及适用范围。

## 按用户问题补证

| 问题 | 先读 | 按需补读 |
| --- | --- | --- |
| 事业与角色 | `career_analysis.topic_facts` | `natal_stars` 的官杀、印、食伤和财星位、`dominant_structure`、`structure_detail`、`seasonal_climate` 与 `markers`（含天乙贵人 `direction`、禄神、驿马、将星、国印贵人、文昌） |
| 学习 | `education_analysis.topic_facts` | `natal_stars` 中印星、食伤与官星透藏位置，及 `markers` 中的文昌位 |
| 婚恋 | 相应专题的 `topic_facts` | `four_pillars.day`、`markers`（红鸾/天喜/咸池/孤辰/寡宿）、`palace_relations.day` 和 `timing_layers` 触点 |
| 财务与六亲 | 相应专题的 `topic_facts` | 具体星位（`natal_stars`）、`palace_relations`、五行旺相（`element_distribution` / `element_seasonal_phase`）及 `timing_layers` |
| 分析时间 | `timing_context` | `topic_facts.timing_layers` 的透藏十神（`stars`）和逐柱触点（`natal_relations` / `palace_hits`） |

## 必须保留的范围

- 引擎只返回确定性结构事实，不内置主观现代职业分类、行业标签或创业倾向；相关行业映射与现实建议由消费结果的 Agent 结合用户实际工作经历、职责和目标推导，并与《子平真诠》格局术语分开说明。
- 路径从对应 `<dim>_analysis` 根读取（综合命盘直接读顶层，标准命盘在 `bazi_birth`），不跨工具混用前缀；数组选择所属整个字段后再读取条目。
- 未知出生时刻不能猜测或填默认 `0`/`12` 时；同一目标范围与精度内复用 `timing_context`，交节当日需小时精度时按[共享时间选择](timing-selection.md)补齐所需时间层。
- 涉及生死、疾病、临床诊断与医疗择时时遵守[硬边界](safety-boundaries.md)。

## 格局、扶抑与调候分别取证

综合命盘读取 `structure_profile`，专题读取 `<topic>_analysis.topic_facts`，标准命盘读取 `bazi_birth.structure_profile` 与 `bazi_birth.intra_month_duty`。`depth` / `audit` 视图或未投影的完整结果保留 `dominant_structure`、`structure_detail`、`seasonal_climate`、`markers`、`palace_relations`、`natal_groups` 与 `timing_layers`。

- **月令格局 vs 扶抑 vs 调候**：`topic_facts.dominant_structure` 给出主格局名称，`topic_facts.structure_detail`（综合/标准命盘为 `structure_profile.dominant_structure`）给出 `key`、`category`、`selection_rule`、`month_stem`、`month_ten_god`、`formation_status`、`obstructions`、`rescues`、`useful_elements`、`avoid_elements` 与 `reason`；`day_master.strength`（综合命盘另有 `day_master.classical_adjudication`）区分扶抑强弱；`seasonal_climate` 给出调候用神与透藏观测。
- **人元司令与交气**：`bazi_birth.intra_month_duty`（及综合命盘 `intra_month_duty`）保留月令司令来源与透藏状态；`calendar_context` 中节气 `datetime_with_offset` 保留偏移与 `fold`，起运年龄在 `bazi_timing` / `bazi_luck_cycles` 中区分 `start_age_precise` 与整数 `start_age`。
- **刑冲合害与流转**：`topic_facts.palace_relations` 与 `topic_facts.natal_groups` 给出本命宫位与合局/三刑关系，`topic_facts.timing_layers` 保留逐柱大运、流年干支十神及宫位触点（综合命盘另有 `structure_profile.harmony_patterns` 与 `clash_patterns`）。
- **词条核对**：需查阅任注燥湿、根字或合化原义时，可调用 `knowledge_read(domain="bazi", category="classical_force_semantics", key=...)`，保留原典与当前计算的差异。
