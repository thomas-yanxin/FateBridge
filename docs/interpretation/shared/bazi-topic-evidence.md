# 八字专题细问的证据读取

专题首次调用前先按任务选择所选工具公开 `evidence_views` 中的 `fields`（如事业 `direction` / `target_year`），不要把卡名作为请求参数。本页说明九项专题与综合命盘的字段取证位置及适用范围。

## 按用户问题补证

| 问题 | 先读 | 按需补读 |
| --- | --- | --- |
| 事业与角色 | `career_analysis.topic_facts` | `natal_stars` 的官杀、印、食伤和财星位，及 `dominant_structure` / `seasonal_climate` |
| 学习 | `education_analysis.topic_facts` | `natal_stars` 中印星、食伤与官星透藏位置 |
| 婚恋 | 相应专题的 `topic_facts` | `four_pillars.day`、传统选星分支和 `timing_layers` 触点 |
| 财务与六亲 | 相应专题的 `topic_facts` | 具体星位、对应柱位、五行旺相及 `timing_layers` |
| 分析时间 | `timing_context` | `topic_facts.timing_layers` 的透藏十神和逐柱触点 |

## 必须保留的范围

- 转述 `career_type/traits/suitable_roles` 等规则类比时须忠于实际字段值，与用户现实职责分开。
- 路径从对应 `<dim>_analysis` 根读取（标准命盘在 `bazi_birth`），不跨工具混用前缀；数组选择所属整个字段后再读取条目。
- 未知出生时刻不能猜测或填默认 `0`/`12` 时；同一目标范围与精度内复用 `timing_context`，交节当日需小时精度时按[共享时间选择](timing-selection.md)补齐所需时间层。
- 涉及生死、疾病、临床诊断与医疗择时时遵守[硬边界](safety-boundaries.md)。

## 格局、扶抑与调候分别取证

综合命盘读取 `structure_profile`，专题读取 `<topic>_analysis.topic_facts`，标准命盘读取 `bazi_birth.structure_profile` 与 `bazi_birth.intra_month_duty`。`depth` / `audit` 视图保留完整 `ten_gods`、`patterns`、`calendar_context` 与 `timing_layers`。

- **月令格局 vs 扶抑 vs 调候**：`dominant_structure` 与 `recognized_structures` 给出月令取格与成格裁定，`day_master.classical_adjudication` 区分扶抑强弱，`seasonal_climate` 给出调候用神与透藏观测。
- **人元司令与交气**：`intra_month_duty` 保留月令司令来源与透藏状态；`calendar_context` 中节气 `datetime_with_offset` 保留偏移与 `fold`，起运年龄区分 `start_age_unrounded` 与整数 `start_age`。
- **刑冲合害与流转**：`harmony_patterns` 与 `clash_patterns` 给出本命及运年干支作用关系，专题 `topic_facts.timing_layers` 保留逐柱大运、流年宫位触点。
- **词条核对**：需查阅任注燥湿、根字或合化原义时，可调用 `knowledge_read(domain="bazi", category="classical_force_semantics", key=...)`，保留原典与当前计算的差异。

`career_type/traits/suitable_roles` 属于 FateBridge 的规则类比，解读时须与《子平真诠》格局术语及用户现实条件分开说明。
