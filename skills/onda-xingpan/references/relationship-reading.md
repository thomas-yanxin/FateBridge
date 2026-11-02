## 关系盘的读法

首次调用前按工具公开的 `evidence_views` 选择与盘型同名的字段卡，复制其 `fields`，不要把卡名当成请求参数。默认联合视图保留安全主层，但已知模式时优先用对应卡，不能用通用摘要或跨盘相位替代指定主盘。计算后核对 `relationship_profile.relative_mode_normalized/primary_layer`，实际映射如下：

| 用户盘型／规范值 | 常用输入别名 | 返回主层／实际应读 |
| --- | --- | --- |
| 比较盘 `compare` | `Comp`、`compare`、0 | `directional_synastry`：`synastry_aspects` 与双向 `in_to_out_aspects/out_to_in_aspects` |
| 组合盘 `composite` | `Composite`、1 | `composite_chart`：`chart` 的实际星体、宫位、角度和相位 |
| 影响盘 `influence` | `Synastry`、`synastry`、2 | `influence_chart_pair`：`inner/outer` 双方视角下的影响图盘，实际盘在各自 `.chart` |
| 时空中点盘 `timespace` | `TimeSpace`、3 | `timespace_chart`：`chart`，双方出生时间与地理位置中点生成的第三盘 |
| 马克斯盘 `marks` | `Marks`、4 | `marks_chart_pair`：`marks_charts.inner/outer`，双方各自与两人Davison资料再次计算Davison，分别读取各自的角度、星体、宫位与相位 |

尤其 `Synastry` 在本引擎归一为影响盘；不能照其他软件惯例把它直接当 compare。普通“比较两个人”用 compare；已明确 Synastry／影响盘直接沿用，无需重问专业术语。`inner_chart/outer_chart` 是各自本命，不能误读为 `inner/outer` 影响图盘。`synastry_aspects` 的 inner／outer 表示实际两端归属。组合、时空的 `chart` 是关系第三盘；Marks的 `chart` 只别名内方个人盘，`primary_chart_role=inner`，不能当成双方共同盘或复制给外方。

Marks专用字段卡保留两个人的 `marks_charts`。旧的组合盘／时空盘混合算法已撤除，不能沿用旧说明。先核对每盘 `chart_profile.derivation_policy`、实际 `davison_variant` 及双方身份，再讨论各自的传统象征体验，不能据此确定对方心意。`compatibility` 来自基础跨盘的自定义规则，不是两张Marks盘的原典评分或关系成功率；需要说明评分时另读实际 `compatibility_evidence`。当前配方来源仍为作者课文镜像，未与原始存档完整校勘，不能宣称原典或现实效力已认证。

双向中点、映点／反映点等专业追问读[深层证据卡](../../_shared/western-deep-evidence.md#关系盘的方向与深读)，按工具 `relationship_detail` 卡补证；不以单人的本命中点代替两人方向性命中。

用户明确恋爱／婚姻时可用 `relationship_focus`，未说明取 general；合作、家人和朋友不强套浪漫或性吸引。围绕所选主层实际返回的相位、星体落宫或其他配置说明本次特点，再给一项能由双方回应检验的相处安排。影响盘可依据双方视角的实际落宫交付，不要求另加相位才有解释；没有保留相位时不补写。只有实际依据同时支持配合和张力时才分别说明，不为凑正负各一条编造。`compatibility` 的各分数保留名称，不解释为关系成功率。
