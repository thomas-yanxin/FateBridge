# 实测工位：条件解释与可行方案

[技能入口](../SKILL.md) · [完整字段与算法范围](../../../docs/fengshui-workstation-layout.md) · [虚构请求](../../../docs/examples/fengshui-workstation-measured.json)

已有人工标注边界、家具/物件尺寸、坐者和门窗位置，或明确要求生成可行方案时，用 `fengshui_assess.workstation_layout`。资料不足时可先走原形态/活动入口解释已有依据，不猜米数、眼高、头顶高度、方位、立极或许可。

图纸 +y、坐者左右/近远、桌面九格、罗盘方向与所选宅盘落宫分别核对。`compass.chart_binding_confirmed` 是调用方确认的范围与中心绑定，不由几何质心自动成立。`sector_anchor` 明确取坐者还是书桌中心；真北/磁北及误差保留。照片和误差结果是候选，多扇窗要明确对象，未确认完整清单不把未列项目当不存在。

`workstation_layout` 的评价运及证据独立于历史宅运；工作/学习按署名作者取向星角色，向星不是座位朝向，也不表示桌上需要放水。实际年/月/宅盘及来源范围各自说明。已有王亭之时令和沈氏主客仅按明确版本及实际覆盖范围引用，不补全81组合、金锁24山或其他学派。

桌面 `ruleset_ids` 必须逐个另选：`desktop_bagua_btb_v1` 是坐者九格，`wofs_desktop_compass_v1` 是有限 WOFS 罗盘/坐者规则。不能互相旋转或合并。活植物身份、`healthy`、位置和物件容纳分别核对；普通手机、水杯或摆件可能没有独立规则，直接说明，不追加资料制造处方。旧工位参考分支仍是 reference_only，新规则只在明确选择的实测分支开启。

`search.domains` 给实际考虑的位置/角度域，搬转许可沿用 `layout_constraints`。每个方案重算入口、背靠、梁、物件与净空及实际方区；固定物件约束不能被搬桌绕过。`ready` 只意味着登记的几何与动作门槛满足，仍需说明每个所选作者的判断和限制。普通解释无需等待动作 ready。

位置用 `positions` 或 `grid` 二选一；网格明确原点、步长和角度，默认从房间或所属桌面自动生成中心候选，可另给中心搜索区。返回 `search.resolved_domains` 与全部回执，不把有限网格称为连续空间最优。实际竖直屏幕可用 `items[].screen` 提供尺寸、朝向与高度，`required_visible` 明确是否为硬约束；视线按整面透视遮挡计算，不由物件名称或屏幕中心点推断，也不承诺无眩光。

首轮可复制 `evidence_views.measured_workstation.fields`；明确要方案时再选 `measured_workstation_search`。视图名不是参数。实际返回在 `layout_analysis.workstation_layout_analysis`：解释读 `geometry/readings/rule_comparisons`；方案读 `search.candidates` 的动作、坐标参考系和各自结果。`search.receipts` 保留全部组合、失败与未知，显示上限不减少已算范围；默认预算延后时读取同一 run。

交付可保留的现状、明确条件下可调的动作和未覆盖部分。候选前沿代表规则与变动量间的取舍，没有统一风水分数；引用实际作者、版本与来源，不承诺职业、财富或健康改善。

审查算法是否全部完成时读取 `research_completion_status/research_coverage`。当前总状态为 incomplete；完整81配对及金锁24山细断等未完成范围和条件须照实交付，不以本次请求 complete 或搜索完整枚举改称全部算法完成。
