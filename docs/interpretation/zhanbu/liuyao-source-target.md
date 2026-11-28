# 六爻：纳甲结构与《增删卜易》取证

六爻计算采用版本化结构层 `zengshan_structural_v2`（`liuyao_evidence.ruleset_id`），返回确定性的逐爻月令旺衰、日辰生克冲合、暗动／日破、进退神、伏神、三合局、反吟伏吟与日级条件窗口；不直接下吉凶断言或把日级条件写成事件发生保证。

从同次返回读取以下对象，不另算一卦补字段：

| 问题 | 同次依据 | 交付要求 |
| --- | --- | --- |
| 卦象基本盘面与世应动静 | `lines`、`moving_lines`、`hexagram_info`（含 `shi_line`、`ying_line`、`gua_shen`）、`patterns`、`pattern_flags` | 区分本卦（`current_hexagram`）与变卦（`changed_hexagram`）；六冲/六合/伏吟/反吟按实际 `patterns` 与 `pattern_flags` 说明 |
| 逐爻月令旺衰、日建冲合、旬空与进退 | `liuyao_evidence.lines[]` | 按爻位读取 `month_strength`、`day_growth_stage`、`is_xunkong`、`is_month_broken`、`is_void_clashed`、`is_dark_moving`、`is_day_broken`、`day_clash_status`、`shensha` 与 `transformation`（`back_relation`、`advance`、`retreat`） |
| 动静多寡取象重点 | `liuyao_evidence.moving_focus_guidance` | 读取 `mode`、`moving_count`、`primary_focus_positions` 与 `rule`，说明静卦、独动或重动时的主要观察位置 |
| 已指定用神及其生克角色 | `liuyao_evidence.focus` | 仅当请求传入 `focus_line`、`focus_kinship` 或 `focus_kind` 时解析；读取 `status`、`selected`、`candidates` 与 `roles`（用神/元神/忌神/仇神/同类）。未传参数时 `status="not_requested"`，不代用户自定用神 |
| 伏神与飞神关系 | `liuyao_evidence.hidden_spirits[]` 与 `hidden_policy` | 伏神严格按本卦缺失六亲取本宫纯卦同位；`present_in_changed` / `changed_positions` 仅标注变爻是否出现该六亲，不掩盖本卦伏神。读 `flying_to_hidden_relation` 与 `calendar_relations` |
| 三合局成局状态 | `liuyao_evidence.three_harmony[]` | 区分 `complete_in_lines`、`complete_with_calendar` 与 `pending_one_branch`，列明 `line_members`、`calendar_members` 与 `missing_branches` |
| 反吟与伏吟结构明细 | `liuyao_evidence.fanfu` | 读 `regions`（`inner` / `outer` 纳支关系）、`moving_line_relations` 与 `explicit_body_example` |
| 未来干支日条件候选 | `liuyao_evidence.timing_candidates` | 仅当 `timing_days > 0` 且已明确可用焦点时生成 `windows[]`（`effective_date`、`day_ganzhi`、`start_at`、`end_at`、`matched_rules`、`requires_month_reassessment`）。条件窗口只表示干支触发规则，不是事件发生日期保证 |

## 按视图读取与交付边界

- 需要常规逐爻读取时用 `evidence_views["liuyao"]["line_reading"]`；已明确用神和日级窗口时用 `focus_and_timing`；细查伏神、三合、反吟伏吟与神煞时用 `structural_relations`。
- 首次需要完整结构证据时使用 `include=["*"]`（省略 `fields`），不重算另取全文。调用方法见[引擎调用](../shared/fatebridge-engine.md#怎么调引擎)。
- 月令节气交界存在模型差异时，核对可选字段 `liuyao_evidence.month_model_comparison`，保留未比较探针说明。
- 交付时用日常语言说清已核结构事实与未决条件（如多现未决、月破、旬空、跨月需重估 `requires_month_reassessment`），不把结构条目贴满全文或替引擎补出总吉凶分数。
