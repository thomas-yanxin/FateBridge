# 八字专题细问的证据读取

专题首次调用前先按任务选择所选工具公开 `evidence_views` 中的 `fields`（如事业 `direction` / `target_year`），不要把卡名作为请求参数。本页说明九项专题与综合命盘的字段取证位置及适用范围。

## 按用户问题补证

| 问题 | 先读 | 按需补读 |
| --- | --- | --- |
| 事业与角色 | `career_analysis.evidence_chain.topic.first_view` | `topic.stars` 的官杀、印、食伤和财星位，及 `structure_checks` 的实际前提 |
| 学习 | `education_analysis.evidence_chain.topic.first_view` | 文昌 `topic.markers`、印和食伤的透藏位置 |
| 婚恋 | 相应专题的 `topic.first_view` | 日支 `topic.palaces.day`、传统选星分支和各运年触点 |
| 财务与六亲 | 相应专题的 `topic.first_view` | 具体星位、对应柱位、墓库及关系 |
| 分析时间 | `timing_context` | `topic.timing.layers` 的透藏十神和逐柱触点 |

## 必须保留的范围

- 转述 `career_type/traits/suitable_roles` 等规则类比时须忠于实际字段值，与用户现实职责分开。
- 路径从对应 `<dim>_analysis` 根读取（标准命盘在 `bazi_birth`），不跨工具混用前缀；数组选择所属整个字段后再读取条目。
- 未知出生时刻不能猜测或填默认 `0`/`12` 时；同一目标范围与精度内复用 `timing_context`，交节当日需小时精度时按[共享时间选择](timing-selection.md)补齐所需时间层。
- 涉及生死、疾病、临床诊断、医疗择时与生育结局时遵守[硬边界](safety-boundaries.md)。

## 格局、扶抑与调候分别取证

综合命盘读取 `structure_profile.evidence_chain`，专题读取 `<topic>_analysis.evidence_chain`，标准命盘读取 `bazi_birth.structure_profile.evidence_chain`。`depth` 视图返回 `ten_gods`、`roots`、`growth_phase_roots`、`financial_seal_positions`、`month_command` 与 `structure_checks`，`classical_root_profile` 区分墓库、余气、禄旺与阴长生参考。

- **月令格局 vs 扶抑 vs 调候**：`candidate_selection.selected_month` 与 `chosen_path_id` 对应月令格局路径，`layers` 中 `heuristic` 属强弱扶抑参考，`reference_only` 属调候简表。三者语境不同，冲突元素通过 `conflicts` 分列。
- **人元司令与交气**：`evidence_chain.month_command.intra_month_duty` 保留来源条文与透藏状态，`selected_stem=null` 时不强定司令；`calendar_context` 中节气 `datetime_with_offset` 保留偏移与 `fold`，起运年龄区分 `start_age_unrounded` 与整数 `start_age`。
- **四墓根力与通关**：`root_effects`（`storage_movement_effects`）区分 `null` 与 `[]`，保留 `event_retention_multiplier` 与 `remaining_hidden_mass`；`passage` / `passage_relations` 视图展示通关流转与合绊条件，`effective_passage=not_adjudicated` 时不将路径存在写成已解冲或已成格。
- **从格与承载**：`from_child` 视图核对从儿前提与 `ordinary_fuyi_requires_review`；`carriers` / `hidden_carriers` 视图分别读取本柱主气、藏根与盖头截脚；`stem_energy` 视图核对天干能量账本；`classical_routes` 视图核对月令取用见证与十神连接。
- **词条核对**：需查阅任注燥湿、根字或合化原义时，可调用 `knowledge_read(domain="bazi", category="classical_force_semantics", key=...)`，保留原典与当前计算的差异。

`career_type/traits/suitable_roles` 属于 FateBridge 的规则类比，解读时须与《子平真诠》格局术语及用户现实条件分开说明。
