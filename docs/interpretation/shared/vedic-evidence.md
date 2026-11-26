# 印占的计算事实与传统解释

适用于用户指定印度／吠陀占星、Jyotish、D9／D10 或 Vimshottari，或主题咨询确有新增价值的印占视角。先守[硬边界](safety-boundaries.md)及[本轮范围](consultation-routing.md)。

## 选择与资料

本命用 `vedic_chart`（或 `astrology_chart` 的 `chart_variant=india_chart`），达沙用 `vimshottari_dasha`。默认使用出生民用时刻，城市可由引擎解析；未知生时不能猜测。核心固定 Lahiri 恒星黄道与整宫制，`node_mode` 区分平／真交点；缺少星历时不以低精度轨道替代分盘或达沙。仅当用户确认生时误差范围时传 `birth_time_uncertainty_minutes`。

## 首次字段与解释

按工具公开 `evidence_views` 复制 `fields`，设置 `strict_fields=true`、`include_snapshot_text=false`；完整 JSON 首次用 `fields=null` 并从同次 `result_delivery` 读取。

| 本轮任务 | 视图／工具 | 主证 |
| --- | --- | --- |
| 本命、做事特点 | `natal` / `vedic_chart` | `india.charts.D1`、`nakshatras`、`topic_evidence.personality` |
| 事业结构 | `career` / `vedic_chart` | D1 与 D10 的第十宫、宫主落宫、尊贵与 graha drishti |
| 单人伴侣相处 | `relationship` / `vedic_chart` | D1 与 D9 第七宫相关事实 |
| 指定分盘 | `divisions` / `vedic_chart` | 实际 D1／D2／D3／D7／D9／D10／D12／D30（D30 仅星座与整宫） |
| 阶段、目标钟时 | `stage` / `vimshottari_dasha` | `current_major/current_sub` 起止、`birth_balance`、年长与本命运星上下文 |

印占仅使用 `india` 内独立规则，不把西占入庙或容许度套入印占。相位按整宫 graha drishti，`D1.physical_state.degree_condition` 包含 moolatrikona、Baladi 与 Uchcha Bala，`combustion` 保留 Santhanam 注释表角距条件与边界状态。

## 力量、时间口径与来源

- **Sthana / 方向 / 相位与时间力**：可通过 `strength` 视图读取 `india.strengths.sthana_bala`、`drik_bala`、`kala_bala`、`yuddha_bala` 及 `cheshta_model`（显式可选 `simon1994_j2000`）。七分盘与三分盘口径分别由 `saptavargaja_profile`（Santhanam / Raman）与 `drekkana_profile` 控制，未裁定分项（如 `shadbala_assessment.total_virupa=null`）保留空值不自加总。
- **Vimshottari 达沙**：次运从原始完整主运分配，区分恒星年、365.2425 日固定年与 360 日 savana 年；`timeline_scope` 的 120 年规则周期不作寿命估计。生时区间敏感性通过 `stage_variants` 按网格样点读取。
- **时制与星历回执**：支持 `civil`、`local_mean_solar` 与 `local_apparent_solar` 钟制，历史星历与时标政策记录在 `india.profile.time_scale_context`、`earth_rotation` 与 `physical_ephemeris_source`；启用 `ephemeris_policy=require_data_files` 可拒绝低精度回退。

交付时保留 `india.profile`、`rulesets` 与 `rule_trace` 中的版本和传统来源（如 P.V.R. Narasimha Rao《Vedic Astrology: An Integrated Approach》、Santhanam 译注 BPHS 与 Brihat Jataka）。
