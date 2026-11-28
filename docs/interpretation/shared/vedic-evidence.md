# 印占的计算事实与传统解释

适用于用户指定印度／吠陀占星、Jyotish、D9／D10 或 Vimshottari，或主题咨询确有新增价值的印占视角。先守[硬边界](safety-boundaries.md)及[咨询核心](consultation-core.md#任务路由与多视角)。

## 选择与资料

本命用 `vedic_chart`，达沙用 `vimshottari_dasha`。默认使用出生民用时刻，城市可由引擎解析；未知生时不能猜测。核心固定 Lahiri 恒星黄道与整宫制，`node_mode` 区分平／真交点；缺少星历时不以低精度轨道替代分盘或达沙。

## 首次字段与解释

按工具公开 `evidence_views` 复制 `fields` 或传给 `include`（三端始终严格校验路径）；无损完整 JSON 使用 `include=["*"]`（省略 `fields`）。

| 本轮任务 | 视图／工具 | 主证 |
| --- | --- | --- |
| 本命、做事特点 | `natal` / `vedic_chart` | `vedic_chart.charts.D1`、`vedic_chart.nakshatras`、`vedic_chart.yogas`、`vedic_chart.strengths.shadbala_assessment` |
| 事业结构 | `divisions` / `vedic_chart` | `vedic_chart.charts.D1` 与 `vedic_chart.charts.D10` 第十宫、宫主落宫、尊贵与 `graha_aspects`（亦可配合 `natal` 视图看综合格局） |
| 单人伴侣相处 | `divisions` / `vedic_chart` | `vedic_chart.charts.D1` 与 `vedic_chart.charts.D9` 第七宫相关事实（亦可配合 `natal` 视图） |
| 指定分盘 | `divisions` / `vedic_chart` | `vedic_chart.charts` 下的实际 D1／D2／D3／D4／D7／D9／D10／D12／D16／D20／D24／D27／D30／D40／D45／D60（D30 仅星座与整宫） |
| 阶段、目标钟时 | `stage` / `vimshottari_dasha` | `vimshottari.current_major` / `vimshottari.current_sub` 起止、`vimshottari.birth_balance`、`vimshottari.year_basis` 与 `vimshottari.timeline` |

印占仅使用 `vedic_chart` 内独立规则，不把西占入庙或容许度套入印占。相位按整宫 graha drishti（`vedic_chart.charts.D1.graha_aspects`），`vedic_chart.charts.D1.planets.*.physical_state` 包含 `degree_zone`（含 moolatrikona）、`baladi_avastha` 与 `combustion` 等条件，同时保留边界状态。

## 力量、时间口径与来源

- **Sthana / 方向 / 相位与时间力**：可通过 `strength` 视图读取 `vedic_chart.strengths.sthana_bala`、`vedic_chart.strengths.drik_bala`（`natures` / `summary`）、`vedic_chart.strengths.kala_bala`（含 `components.yuddha_bala`）、`vedic_chart.strengths.cheshta_bala` 与 `vedic_chart.strengths.shadbala_assessment`（`status="complete"`，给出七星 `total_virupa`、`total_rupa`、`required_rupa`、`is_strong` 与 `ishta_kashta`）。七分盘与三分盘口径分别由 `saptavargaja_profile`（`santhanam_27` / `raman_30`）与 `drekkana_profile`（`santhanam_27_6` / `raman_36`）控制，`cheshta_model` 默认 `simon1994_j2000`（可选 `unadjudicated`，回退 `sidereal_angular_fallback`）。
- **Vimshottari 达沙**：次运从原始完整主运分配，区分恒星年、365.2425 日固定年与 360 日 savana 年；`vimshottari.timeline_scope` 为 120 年规则周期。生时敏感性摘要记录在 `vimshottari.birth_time_sensitivity`。
- **时制与星历回执**：核心采用出生民用钟物理瞬间，历史星历与时标政策记录在 `vedic_chart.profile.time_scale_context`、`vedic_chart.profile.ephemeris_by_body` 与 `vedic_chart.profile.physical_ephemeris_source`；启用 `ephemeris_policy=require_data_files` 可拒绝低精度回退。
