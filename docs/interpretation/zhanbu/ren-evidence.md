# 六壬与金口诀的同次结果取证

只在本次已选六壬或金口诀时读取。先使用工具发布的 `evidence_views.core.fields`（视图名不是请求参数，三端对 `fields` 始终严格校验）。未裁定的综合条件只限制对应层次，不影响已返回结构的解释。

## 六壬起课与行年

核对 `analysis_context` 的输入时刻、校正时刻与 `four_pillars`，月将看 `liureng.month_general` 与 `meta.month_general_basis`（中气换将）。用户给出秒数时保留 `analysis_second`。`calendar_policy` 说明子初换日（23:00）与交气模型来源（如 `swisseph`、`jpl_de440` 或解析模型），503 `dependency_missing` 表示缺可靠天文交气而非参数错误。`published_date_reference` 对照香港天文台 1901–2100 逐日表，仅说明刊载日期一致与否。

`meta.guiren_profile` 区分通用贵人表 `liuren_common_v1` 与《探原》贵人歌 `tanyuan_xieji_v1`；`meta.diurnal_evidence` 标明昼夜是显式选择还是按时支约定。

| 依据 | 实际字段 | 解读范围 |
| --- | --- | --- |
| 四课上下与日干 | `four_lessons.upper_branch/lower_branch/anchor_branch/upper_lower_relation` | 寄宫只负责定位，第一课仍以日干五行比较 |
| 干支相加课体 | `day_placement_patterns` | 日干寄宫临日支与日支临寄宫分向读取 |
| 交车六合 | `cross_harmony` | 分边核对干上神与日支、支上神与日干寄宫支；五个同宫日排除并保留原因 |
| 取传与细课体 | `board_style/board_style_detail`、`classification`、`three_transmissions` | 细名按《探原》总说推导；`ganzhi=null` 因旬空无遁干，不自行补干 |
| 三传关系与课体条件 | `transmission_relations` | 内外战、名义局体、斫轮/铸印/轩盖及课体纲要条件，保留 `comprehensive_judgement=null` |
| 本空、坐空与例外 | `xun_kong/seated_kong`、`emptiness_evidence` | 分开本空与坐空，及天盘支/地盘年命例外 |
| 德禄马与月序 | `auxiliary_stars` | 天盘星支落地盘位置，区分月建节月与农历月 |
| 行年与年命落盘 | `runyear`、`runyear.year_fate` | 按出生民用时区正月初一换岁的虚岁行年（男丙寅顺、女壬申逆） |
| 支位关系与季节 | `branch_relations`、`transmission_progression`、`seasonal_evidence` | 同支、合冲刑破害、连茹进退及五季五态分别读取 |

## 金口诀四位

金口诀可传 `birth_year_ganzhi`、`year_fate_age` 与性别读取行年课（`year_fate` 视图），`year_fate` 与主课分开引用。注意区分 `overview.month_general`（中气月将本位）与 `overview.yuejiang`（月将加时落地分的将神），并核对 `overview.di_fen_source`（显式输入或按时支回退）。

| 依据 | 实际字段 | 解读范围 |
| --- | --- | --- |
| 四位与贵神 | `rows`、`overview.guishen` | 区分贵神固有干支 `intrinsic_ganzhi` 与当日五子遁干 `dun_stem` |
| 季节与位内旺衰 | `rows.seasonal_power`、`internal_strength` | 两者分开读取，未裁定保留 `null` 或候选列表 |
| 四位生克与遁干 | `position_interactions`、`stem_relations` | 区分四位支位生克与神将当日遁干生克配对 |
| 得气与阴阳用位 | `qi_evidence`、`overview.use_position`、`use_evidence` | 仅按阴阳次第五用及实际受克、空破条件，未裁综合用位 |
| 六十四课钤 | `patterns.matched/unresolved`、`definition_evidence` | 58 条已评估、6 条疑义保留未判，分别保留原文版本条件 |
| 三合、动象与空破 | `combinations`、`motions`、`rows.xun_kong/si_da_kong/month_break` | 支齐虚一不代合化；保留《四库》/京本/早稻田等异文对照 |
| 四绝、四败与岁日 | `relations.si_jue/si_bai`、`relations.calendar.checks` | 传入 `natal_branch` 时才核大绝，不以占时或行年替代 |

金口诀本课不借大六壬三传定用，`guiren_profile` 仅作用于附带 `liureng` 盘。需要完整结果时请用 `detail=audit` 且 `fields=null`，不重算替代原课。
