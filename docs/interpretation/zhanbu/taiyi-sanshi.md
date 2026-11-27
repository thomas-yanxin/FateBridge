# 太乙与三式：按本次实际依据解释

仅在用户选择太乙或三式合参时读取。`taiyi.calculation_mode` 支持年（`year`）、月（`month`）、日（`day`）、时（`hour`）四计（默认年计）；三式合参可通过 `taiyi_options` 显式指定计法与配置。

## 计法、历法与起元

首先核对 `calendar_rules` 与 `calendar_summary` 的实际模式、节气来源（`anchor_ephemeris_model`）、时区与钟面；重复民用钟时在太乙单术中可通过 `analysis_utc_offset` 消歧，钟表时间与真太阳时分开处理。现代天文与钟面适配不等于完整古历复原；玄命未实现。

| 计法 | 配置与主要字段 | 解读边界 |
| --- | --- | --- |
| 年 `year` | 默认金镜年计（正月初一换岁）；可选历史表 `jinjing_year_historical_table_v1`（381–385）与 `jinjing_year_qiliang_table_v1`（501–505） | 四柱立春年与真太阳时跨日不改变本计现代农历年界；502 年闰月异说保留 |
| 月 `month` | 默认 `jinjing_month_jie_360_v1` 六纪节月；可选 `key_month_tianzheng_jie_v1` 金钥匙积月 | 均按十二节月计算，中气不递增节月；两种起元与原门段分歧分别解释 |
| 日 `day` | 金钥匙 `key_day_winter_jiazi_v1` 冬至前甲子积日；读 `daily_calendar`、`daily_essences`、`ten_jing` | 零时换日，不套时计 23 时子初；保留十精未知、正文与课式异数 |
| 时 `hour` | 默认 `jinjing_hour_solstice_v1`；可选 `key_hour_winter_jiazi_v1` 金钥匙完整积时 | 默认至点时计不附定计门盘；金钥匙时计读完整积时、阴阳四门与 `winter_origin_selection` |

- **日计细则（`calculation_mode=day`）**：采用金钥匙冬至前甲子积日法（合参时置 `taiyi_options`），按所选钟面零时换日而不套时计 23 时子初或 720 时相位不变。先设 `day` 再取 `daily_calendar` / `daily_essences` 视图，保留十精未知与正文／课式异数（不拿全年十神充当十精，天时和太乙数四宫语义仍未知或异数并列时忠实解释，不按有利结果改写计算值）。
- **时计细则（`calculation_mode=hour`）**：默认至点时计不附定计门盘；显式传 `key_hour_winter_jiazi_v1` 可读完整积时、定计及三项原例差异，时计三门主体仍未裁定，不按有利结果换法。

## 主客事实、条件与合参

- **字段视图**：按 `evidence_views` 复制 `fields`（三端始终严格校验路径）。年计核心用 `year_core`，深读可选 `taiyi_depth`、`counter_cycles`、`shiji_derivation`、`count_sources`、`conditions`、`gates`、`victory_matrix`、`long_cycle_summary` 与 `noble_sources`；年／月八门与定计用 `gates`、`gate_comparison`、`determinate` 分源深读，始击读 `shiji_derivation`，原表读 `count_sources`。
- **主客、始击与数格**：`core_board` 与 `shiji_derivation` 给出天盘计神起法与主客算数，中五星标在 `core_board`／`center_marks`；无天、无地、无人等属传统数格分类。`patterns` 与 `enclosure_assessment` 列出掩、击、迫、囚、关、格、对与正宫提挟条件；`three_gates`、`menju_jiangfa` 与 `victory_matrix` 按三值条件合取与钤表栏位保留未决项。
- **三式合参（`sanshi_combined_chart`）**：先读 `synthesis.time_scopes` 分清太乙计法与奇门／六壬时刻。`palace_correspondences` 按方位联接五将与奇门星门神及六壬地盘支位（中五不寄坤，四维寄支在 `sector_candidates` 保留候选），`noble_source_assessment` 区分通行与探原协纪贵人表。

解读时先结合本次计算事实说明传统含义，再提供现实中可核对的条件，保留 `rulesets` 版本来源与 `partial`／未知边界；需要完整结果与依据时传 `detail=audit` 且 `fields=null`，不凭 `detail=compact` 默认裁剪作否定，也不重算替代。
