# 六爻：来源资格与目标承受分别说明

解释某爻“当前可用”时，先说明问题涉及的局部条件，再说明尚未裁定的范围。来源受扶、来源可向外生扶、目标能承受、具体作用匹配、整体效力是不同问题；同一爻可以同时有已核事实和未决事实。

从同次 `liuyao_evidence.conditional_analysis` 读取以下对象，不另算一卦补字段：

| 问题 | 同次依据 | 交付要求 |
| --- | --- | --- |
| 本爻是否有已核生扶与另有反制 | `classical_assessment` 的相应主体与 `strength` | 有扶、反制及未知分别说明，不以“总体未决”替代已核内容 |
| 这个来源是否具备向外生扶资格 | `generation_conditions.sources` 的本位置 `condition_match/status` | 匹配时说明本项资格已核；不匹配时说明实际阻碍；未知不能写成无作用。资格匹配本身不创造原本不存在的生向 |
| 用爻作为受方能否承受 | `generation_conditions.focus.target_reception_condition/target_status` | 与来源资格分别说明；这不是用爻自身向外生扶的判定 |
| 某条生扶能否在所列条件下受益 | `generation_conditions.generations` 的对应来源、目标及 `benefit_now` | 只说实际存在的方向，不把某源可用扩成所有目标都已受益 |
| 本位变化有什么作用 | `back_generation_conditions` 及本爻 `outgoing_obstructions`、对应克制条件 | 回头生的原门槛与当前资格分别读。回头克存在时，连同向外生扶是否受阻一起说明；不能只说该克仍在，然后跳到全局未决 |

`month_break_conditions` 保留原月破和同支值日的本项限定。原始月令分类不删除，限定后月令反制不匹配也不排除独立动克、暗动、回头克、旬空或合绊。实际变支、飞神、伏神分别用自己的支值；不借另一主体值日。所列静克静分支是限定条款，不外推成一切静爻永远不能伤临日之爻。

当前合同若提供 `generation_conditions.focus.source_condition_match/source_status/source_condition_path`，它们与同一位置的生源记录相连，可和原有 `target_reception_condition/target_status` 一起读取。`source_explanation/target_explanation` 分别转述这两项实际资格；摘要会明确写出已核向外生扶受阻，不能再省略成只有“另有克制、全局待审”。字段尚未提供的旧版本继续读原 `sources`，缺少新字段不等于资格为假。该焦点对象仅适用已明确的可见本爻；变爻、伏神或日月主体返回空时，转读其对应条件，不借原爻焦点代替。

遇 `result_delivery`，先使用原回执直接给出的 `manifest_uri`、字段资源或 `file_path`；不能遍历临时目录后按修改时间挑“最新结果”。需要核验时使用同run引擎读取接口，传入原结果ID和run ID，由内部清单核对存储完整性；再提取实际所需字段，不重算取全文。完整读取方法见[引擎交付](../../_shared/fatebridge-engine.md)。

交付用日常语言说清这些已读事实。字段检查是取证方法，不要求把整份Schema贴给用户；总效力未裁定继续保留，不把局部门槛匹配改写为现实成败。
