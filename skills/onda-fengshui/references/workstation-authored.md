# 工位作者规则：活动、隔挡与材料施用条件

[场景技能](../SKILL.md) · [室内关系与材质](sourced-interior-rules.md) · [候选合同](scene-planning.md) · [请求示例](../../../docs/examples/README.md)

工位活动、入口隔挡与材料施用条件通过 `fengshui_assess` 计算，REST/MCP/CLI 共用模型和计算；玄空床／门解释保持独立。WOFS 非 BTB 桌面摆法只保留作者参考，不注册证据不足的摆放规则。

## 版本与来源

| 规则版本（均1.0.0） | 范围 | 直接来源 |
| --- | --- | --- |
| `workstation_activity_authored_v1` | 明确清醒工作／学习活动的向星用途参考 | Kartar Diamond：2018 [同室不同用途](https://fengshuisolutions.net/the-feng-shui-approach-to-the-same-room-different-function-by-kartar-diamond/)、2024 [阴阳房间](https://fengshuisolutions.net/feng-shui-interpretation-of-yin-rooms-and-yang-rooms-by-kartar-diamond/)、2025 [山向角色](https://fengshuisolutions.net/excerpt-from-the-mountain-dragons-and-water-dragons-case-study-by-kartar-diamond/) |
| `afsi_entry_barrier_v1` | 明确入口—坐者直线中的植物／屏风隔挡 | [AFSI FS305](https://www.amfengshui.com/wp-content/uploads/2014/09/fs305-0508.pdf)，2008，印刷/PDF第30–31页 |
| `afsi_application_conditions_v1` | 水体、金属和植物的附加条件；目标绑定独立 | [Janice Sugita／AFSI FS227](https://www.amfengshui.com/wp-content/uploads/2014/09/fs227.pdf)，2006，印刷28–29/PDF32–33页；[Larry Sang／AFSI](https://www.amfengshui.com/wp-content/uploads/woocommerce_uploads/2013/12/tpofs.pdf)，印刷23、25/PDF40、42页 |
| `workstation_source_boundaries_v1` | 尖角、物件路线等作者分歧与范围说明 | [Joey Yap 2014尖角说明](https://masteryacademy.com/Academy/media/columncontent.asp?iframe=academic_colum&nid=1967)、2005装饰象征文章；WOFS及Sean Chan署名立场 |

完整来源、定位及已登记的原始内容散列见 src/fatebridge/data/fengshui/workstation-authored-v1.json。作者用途规则不冒充中州派校勘原典；不同作者文章不作多份独立效果验证。起盘仍来自当前明确的历史宅盘版本。

## 请求和读取分支

`environmental_context.workstation_review` 可包含 `activities`、`entry_barriers`，至少一项非空，每项必须显式填写对应 `ruleset_id`。不需要用虚假方向或占位家具满足接口。只有实际提交该审查才返回 `layout_analysis.workstation_analysis`；首轮 fields 按需追加这个分支，并保留 rulesets、rule_trace。材料施用仍在 `layout_analysis.material_analysis`。

### 工作／学习用途

`activities` 每项提供 `object_id`、`activity`、`observation_basis`、`evidence`。对象须是已经明确登记的书桌，不能仅由 label 猜用途。`activity` 接受 work、study、meditation、storage、mixed、unknown；当前清醒取向星的规则只覆盖 work/study。其他已知用途直接报告未覆盖，unknown 才保留事实确认。

可独立提供 `space_mixed_use` 的 value、`observation_basis`、`evidence`，说明空间是否混用。它不代替这张桌的实际活动，也不产生全室综合判断。

使用 `placements.location_direction` 关联本轮已算历史宅盘；`facing_direction` 只表示坐向。输出各候选的向星数、其自身五行、同宫山星及有序五行关系；生克关系不等于吉凶。测量有候选时逐一保留。用途参考不要求先确认外部水形；另有旧版外局审查时分开读取，不能把水星理解成真实水装置需求。

评价运可在 `workstation_review.evaluation_period` 中独立提供 number（1–9）及 `evidence`；也可采用同轮已显式提供的 `xuankong.interpretation` 评价运，两处不得矛盾。省略则时运未知，不从历史宅运、年度或系统日期补值。现有有限当令识别仅比较相等，其余 `not_current` 不等于凶。

有活动事实就可以先解释角色参考。缺位置或宅盘只阻塞具体星数关联，不要求先取得搬动许可，也不会因此开启摆位处方。

虚构示例：[活动与历史宅盘](../../../docs/examples/fengshui-workstation-activity.json)。旧 `xuankong_conditioned_v1` 中 desk 仍是未覆盖；新结果在独立 `workstation_analysis`，不能把旧版本的范围回执当作新分支已失败。

### 入口隔挡

`entry_barriers` 每项明确 `relation_id`、`entrance_id`、`desk_id`、`barrier_id`、`barrier_kind`（plant/screen）、`operation`（retain/relocate/add），以及物件身份的 observation_basis/evidence。入口须为明确实际门，不把通道或厕门当房间入口；三端必须是不同对象。隔挡独立登记为实际物件，不能伪装为门床桌灶。

下列每个观察都是独立的 value（true/false/null）、`observation_basis`、`evidence`：

- `entry_line_through_user`：实际入口直线是否经过坐者。
- `barrier_between_entry_and_user`：该隔挡是否确实位于入口与坐者之间。
- `entrance_view_maintained`、`circulation_clear`、`operating_space_clear`、`physically_feasible`：执行时的视野、通行、操作和容纳条件；这些是工程检查，不是新增传统吉凶规则。

明确没有入口直线关系时返回 `not_indicated`，不追隔挡执行条件。明确关系或身份只来自照片时保留候选，也可以先解释条件依据。无来源的长度、遮挡百分比和植物数量不补成阈值。

`relocate` 读取隔挡自身的 `can_relocate`，`add` 读取书桌的 `can_add_items`；`retain` 不要求移动许可，但确认未在其间时不能算可执行隔挡。准备状态 `ready` 仍要求身份、相关关系及工程条件确认，不能由允许移动补足几何。`blocked` 动作不追执行条件；独立未知事实仍可按本次问题择要核对。

虚构示例：[明确入口关系的屏风候选](../../../docs/examples/fengshui-entry-barrier.json)。本规则不处方罗盘方位，不证明事业或健康改善。

### 材料施用条件

`material_facts` 保留原属性与 `element_use`。需要附加检查时提供 `application`，显式 `ruleset_id=afsi_application_conditions_v1`：

| 实际材料 | 本版检查 |
| --- | --- |
| water | `water_clean`、`water_moving`、`proportionate_to_space` |
| metal | `metal_exposed`、`proportionate_to_space` |
| living_plant | `plant_healthy`；原有 `plant_alive` 仍独立 |

各项同样用独立 value/observation_basis/evidence。不允许给水体填 `metal_exposed` 等不对应观察。`proportionate_to_space` 是来源中的定性人工核对，不是引擎算出的足量标准。颜色、器形和材料不能互证；复合物件继续保留独立属性，不相加成为分数。

`application_analysis` 分开返回初步资格、各作者条件、`target_binding`、未评估维度。材料资格尚未知时为 `needs_material_confirmation`，不提前索取施用条件。缺条件为 `needs_confirmation`；确认不符合可结束该项施用结论，不为凑齐清单追其余条件。全部条件确认只到 `conditions_reviewed`；剂量、实际位置、摆放利弊及现实效力仍未评估，不产生 `ready`。

`target_request_id` 可选引用同轮 `element_adjustments.request_id`。只有真实已算的 `introduced_element` 与明确 `element_use` 一致，才返回 `bound_to_computed_target`。目标未算、目标不指示调节、元素不匹配和候选不确定各自返回理由；绑定不证明材料物件已位于该宫。没有绑定时仍能解释材料，不能由资格推导环境需要。

虚构示例：[金属资格符合、尺度尚未确认](../../../docs/examples/fengshui-material-application.json)。AFSI 与 Diamond 对柜内金属的不同意见分列；本条件检查采用前者，不自动合并。

## 候选、解释和兼容

使用原 `layout_constraints`／`layout_alternatives`。活动和入口隔挡事实放候选 `environmental_context.workstation_review`。候选可以仅含涉及移动对象的明确工位关系，无需伪造门／桌方向；任一关系端移动，都要重核原入口／坐者／隔挡三端，换关系不能跳过旧项。本次明确评价运是查询条件，可以沿用；活动几何与入口关系仍需新证据。已确认活动、隔挡种类、材料属性和绑定目标不能借搬转改写；缺原施用条件保留待确认。

未提供这些输入时，不增加 `workstation_analysis` 或材料 `application_analysis`。工位尖角／明确桌角关系以及材料代表物问题分别保留作者分歧元数据，原 WOFS 判据不被覆盖。无来源处方、作者排除、已知不匹配、规则未实现和未知事实分别说明。

WOFS桌面内容仅在 `workstation_analysis.non_btb_desktop_reference` 中作为带来源参考，`placement_rules_enabled=false`；不注册其方位摆放、龙虎高低、手机方向或水晶球规则。BTB 仍需明确另选；这些规则不自动触发 BTB。

三个入口均可读取示例 JSON：REST POST /api/fengshui/assess；MCP `fengshui_assess`；CLI `fatebridge fengshui_assess --request-file`。严格字段投影按本次实际存在的分支选择。
