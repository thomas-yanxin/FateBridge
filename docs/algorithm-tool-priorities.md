# 公开工具审查优先级

[细粒度算法与职责清单](algorithm-inventory.md) · [现行范围与未决项](algorithm-status.md)

本表按主要输出职责为当前 92 个公开工具定级，覆盖 13 个工具族与 65 个共享方法合同。P0 有 4 项，P1 有 27 项，P2 有 54 项，P3 有 7 项。现行接口与迁移说明见[接口名称与升级](api-reference.md#接口名称与升级)。

P0先查共享时标、历法与物理坐标；P1查各体系定盘与基础规则；P2查时运、关系、专题和综合解释；P3查资料与交付。入口等级按其主要输出职责确定；例如专题入口列P2，其内部时标仍属P0、基础四柱仍属P1，不能因入口分组跳过上游。相同等级内按目录顺序列出，不表示准确率高低；已有可复现且有同定义外部参考的失败先于尚无可比依据的项目。

优先级是本次工程审计的判断，依据传播范围与结果影响，不冒充原典作者的分级。合同登记不代表相关传统、编辑词义或现实预测已通过；`bazi_personality`的编辑词典及计数单独标明未完成来源与人格效度验收。

第十四批补全`jyotish.positions`及`predictive.build_native_subject`的目标姿态、宫位与高度TT，并让主限使用单一typed context；实际SDK单double边界独立保留。returns的16个标量端点别名已实际观察，精确点身份与连续物理交点／严格not-after仍须不同证据，未以目标矩阵通过改判。Human Design、果老及其他TT命中尚须逐条追实际消费者，不因出现scalar就预判错误。传统来源P1仍保留太乙版本异文、壬学4不符／6未决与八字17差异／两约束；清单未具名及未归层队列继续按实际定义审读，不因已有工具代表调用而跳过。

第十五批再补齐共享太阳钟与果老实际target、限定年／节月成员和TT差；果老普通solar calendar及未执行分支仍未验。原生日／月返照的提前停止缺口已用同一24对原作者C结果复比，7较差变0；原16别名、连续物理root与其他epoch／flags仍列P0未决。Human Design本轮所读natal／Design路径实际全部调用native scalar SDK，不作无依据的全float替换；其余cycle／interval及旧物理失败继续按实际scope审查。

| 级别 | 目录记录 | MCP／CLI 名称 | REST 路径 | 审查重点 |
| --- | --- | --- | --- | --- |
| P0 | `jieqi_timeline_analysis` | `solar_term_timeline` | `/api/calendar/solar-term-timeline` | 共享历法与物理坐标 |
| P0 | `jieqi_year` | `solar_terms_for_year` | `/api/calendar/solar-terms` | 共享历法与物理坐标 |
| P0 | `nongli_time` | `lunar_calendar_time` | `/api/calendar/lunar-time` | 共享历法与物理坐标 |
| P0 | `astro_chart` | `astrology_chart` | `/api/astrology/chart` | 共享历法与物理坐标 |
| P1 | `analyze_destiny` | `bazi_overview` | `/api/bazi/overview` | 八字定盘与来源判定 |
| P1 | `bazi_birth` | `bazi_birth_chart` | `/api/bazi/birth-chart` | 八字定盘与来源判定 |
| P1 | `bazi_source_compare` | `compare_bazi_sources` | `/api/bazi/compare-sources` | 八字定盘与来源判定 |
| P1 | `meihua_analysis` | `meihua_time_cast` | `/api/divination/meihua/time-cast` | 数算、起卦与符号基础 |
| P1 | `meihua_cast` | `meihua_cast` | `/api/divination/meihua/cast` | 数算、起卦与符号基础 |
| P1 | `tongshefa` | `combine_four_gua` | `/api/divination/combine-four-gua` | 数算、起卦与符号基础 |
| P1 | `sixyao` | `liuyao` | `/api/divination/liuyao` | 数算、起卦与符号基础 |
| P1 | `canping` | `canping` | `/api/divination/canping` | 数算、起卦与符号基础 |
| P1 | `heluo` | `heluo` | `/api/divination/heluo` | 数算、起卦与符号基础 |
| P1 | `suzhan` | `suzhan` | `/api/divination/suzhan` | 数算、起卦与符号基础 |
| P1 | `otherbu` | `interpret_astrology_dice` | `/api/divination/astrology-dice/interpret` | 数算、起卦与符号基础 |
| P1 | `ziwei_birth` | `ziwei_birth_chart` | `/api/ziwei/birth-chart` | 中式定盘与课传基础 |
| P1 | `liureng_gods` | `liuren_chart` | `/api/liuren/chart` | 中式定盘与课传基础 |
| P1 | `qimen` | `qimen` | `/api/qimen` | 中式定盘与课传基础 |
| P1 | `taiyi` | `taiyi` | `/api/taiyi` | 中式定盘与课传基础 |
| P1 | `jinkou` | `jinkou` | `/api/jinkou` | 中式定盘与课传基础 |
| P1 | `human_design` | `human_design` | `/api/human-design/chart` | 各星盘基础派生 |
| P1 | `astro_chart13` | `thirteen_sector_chart` | `/api/astrology/thirteen-sector-chart` | 各星盘基础派生 |
| P1 | `astro_hellen` | `hellenistic_chart` | `/api/astrology/hellenistic-chart` | 各星盘基础派生 |
| P1 | `astro_guolao` | `guolao_chart` | `/api/astrology/guolao-chart` | 各星盘基础派生 |
| P1 | `astro_india` | `vedic_chart` | `/api/astrology/vedic-chart` | 各星盘基础派生 |
| P1 | `astro_germany` | `hamburg_midpoint_chart` | `/api/astrology/hamburg-midpoint-chart` | 各星盘基础派生 |
| P1 | `fengshui_directions` | `fengshui_directions` | `/api/fengshui/directions` | 风水基础方位与宅盘 |
| P1 | `fengshui_minggua` | `fengshui_minggua` | `/api/fengshui/minggua` | 风水基础方位与宅盘 |
| P1 | `fengshui_bazhai` | `fengshui_bazhai` | `/api/fengshui/bazhai` | 风水基础方位与宅盘 |
| P1 | `fengshui_jinsuo` | `fengshui_jinsuo` | `/api/fengshui/jinsuo` | 风水基础方位与宅盘 |
| P1 | `fengshui_xuankong_natal` | `fengshui_xuankong_house_chart` | `/api/fengshui/xuankong-house-chart` | 风水基础方位与宅盘 |
| P2 | `bazi_marriage` | `bazi_marriage` | `/api/bazi/marriage` | 八字专题与合参 |
| P2 | `bazi_career` | `bazi_career` | `/api/bazi/career` | 八字专题与合参 |
| P2 | `bazi_wealth` | `bazi_wealth` | `/api/bazi/wealth` | 八字专题与合参 |
| P2 | `bazi_health` | `bazi_health` | `/api/bazi/health` | 八字专题与合参 |
| P2 | `bazi_children` | `bazi_children` | `/api/bazi/children` | 八字专题与合参 |
| P2 | `bazi_education` | `bazi_education` | `/api/bazi/education` | 八字专题与合参 |
| P2 | `bazi_personality` | `bazi_personality` | `/api/bazi/personality` | 八字专题与合参 |
| P2 | `bazi_relatives` | `bazi_relatives` | `/api/bazi/relatives` | 八字专题与合参 |
| P2 | `bazi_romance` | `bazi_romance` | `/api/bazi/romance` | 八字专题与合参 |
| P2 | `two_person_compatibility` | `bazi_compatibility` | `/api/bazi/compatibility` | 八字专题与合参 |
| P2 | `timing_analysis` | `bazi_timing` | `/api/bazi/timing` | 时间层与关系层 |
| P2 | `dayun_analysis` | `bazi_luck_cycles` | `/api/bazi/timing/luck-cycles` | 时间层与关系层 |
| P2 | `liunian_analysis` | `bazi_yearly_timing` | `/api/bazi/timing/yearly` | 时间层与关系层 |
| P2 | `liuyue_analysis` | `bazi_monthly_timing` | `/api/bazi/timing/monthly` | 时间层与关系层 |
| P2 | `liuri_analysis` | `bazi_daily_timing` | `/api/bazi/timing/daily` | 时间层与关系层 |
| P2 | `liushi_analysis` | `bazi_hourly_timing` | `/api/bazi/timing/hourly` | 时间层与关系层 |
| P2 | `sukuyo_compatibility` | `sukuyo_compatibility` | `/api/compatibility/sukuyo` | 时间层与关系层 |
| P2 | `sanshiunited` | `sanshi_combined_chart` | `/api/divination/sanshi` | 时间层与关系层 |
| P2 | `ziwei_horoscope` | `ziwei_timing` | `/api/ziwei/timing` | 时间层与关系层 |
| P2 | `liureng_runyear` | `liuren_yearly_timing` | `/api/liuren/timing/yearly` | 时间层与关系层 |
| P2 | `astro_vimshottari` | `vimshottari_dasha` | `/api/astrology/vimshottari-dasha` | 时间层与关系层 |
| P2 | `astro_relative_chart` | `relationship_chart` | `/api/astrology/relationship-chart` | 时间层与关系层 |
| P2 | `western_timing_analysis` | `western_timing` | `/api/astrology/timing` | 西占时运与事件 |
| P2 | `solarreturn` | `solar_return` | `/api/astrology/timing/solar-return` | 西占时运与事件 |
| P2 | `lunarreturn` | `lunar_return` | `/api/astrology/timing/lunar-return` | 西占时运与事件 |
| P2 | `transit` | `transit_chart` | `/api/astrology/timing/transit-chart` | 西占时运与事件 |
| P2 | `solararc` | `solar_arc` | `/api/astrology/timing/solar-arc` | 西占时运与事件 |
| P2 | `givenyear` | `chart_for_year` | `/api/astrology/timing/chart-for-year` | 西占时运与事件 |
| P2 | `profection` | `profection` | `/api/astrology/timing/profection` | 西占时运与事件 |
| P2 | `pd` | `primary_directions` | `/api/astrology/timing/primary-directions` | 西占时运与事件 |
| P2 | `pdchart` | `primary_directions_chart` | `/api/astrology/timing/primary-directions-chart` | 西占时运与事件 |
| P2 | `zr` | `zodiacal_releasing` | `/api/astrology/timing/zodiacal-releasing` | 西占时运与事件 |
| P2 | `firdaria` | `firdaria` | `/api/astrology/timing/firdaria` | 西占时运与事件 |
| P2 | `decennials` | `decennials` | `/api/astrology/timing/decennials` | 西占时运与事件 |
| P2 | `astro_harmonic` | `harmonic_chart` | `/api/astrology/harmonic-chart` | 西占时运与事件 |
| P2 | `astro_planetary_ages` | `planetary_ages` | `/api/astrology/timing/planetary-ages` | 西占时运与事件 |
| P2 | `astro_triplicity_rulers` | `triplicity_ruler_periods` | `/api/astrology/timing/triplicity-ruler-periods` | 西占时运与事件 |
| P2 | `astro_lunation_phase` | `lunar_phase_progressions` | `/api/astrology/timing/lunar-phase-progressions` | 西占时运与事件 |
| P2 | `astro_distributions` | `bounds_directions` | `/api/astrology/timing/bounds-directions` | 西占时运与事件 |
| P2 | `astro_balbillus` | `balbillus_periods` | `/api/astrology/timing/balbillus-periods` | 西占时运与事件 |
| P2 | `astro_keypoints` | `numeric_aspect_periods` | `/api/astrology/timing/numeric-aspect-periods` | 西占时运与事件 |
| P2 | `astro_yearsystem129` | `planetary_periods_129_years` | `/api/astrology/timing/planetary-periods-129-years` | 西占时运与事件 |
| P2 | `astro_planetaryarc` | `planetary_arc_directions` | `/api/astrology/timing/planetary-arc-directions` | 西占时运与事件 |
| P2 | `astro_persiandirected` | `persian_directions` | `/api/astrology/timing/persian-directions` | 西占时运与事件 |
| P2 | `astro_agepoint` | `age_point` | `/api/astrology/timing/age-point` | 西占时运与事件 |
| P2 | `astro_vedicprog` | `sidereal_progressions` | `/api/astrology/timing/sidereal-progressions` | 西占时运与事件 |
| P2 | `astro_jaynesprog` | `declination_progressions` | `/api/astrology/timing/declination-progressions` | 西占时运与事件 |
| P2 | `astro_mundane` | `mundane_ingress_chart` | `/api/astrology/events/mundane-ingress-chart` | 西占时运与事件 |
| P2 | `astro_extrareturns` | `planetary_returns` | `/api/astrology/events/planetary-returns` | 西占时运与事件 |
| P2 | `astro_horary` | `horary_chart` | `/api/astrology/events/horary-chart` | 西占时运与事件 |
| P2 | `astro_election` | `evaluate_election_time` | `/api/astrology/events/evaluate-election-time` | 西占时运与事件 |
| P2 | `fengshui_annual_stars` | `fengshui_annual_stars` | `/api/fengshui/annual-stars` | 风水时间与综合条件 |
| P2 | `fengshui_monthly_stars` | `fengshui_monthly_stars` | `/api/fengshui/monthly-stars` | 风水时间与综合条件 |
| P2 | `fengshui_assess` | `fengshui_assess` | `/api/fengshui/assess` | 风水时间与综合条件 |
| P3 | `gua_lookup` | `gua_lookup` | `/api/divination/gua` | 资料、查表和交付 |
| P3 | `gua_meiyi` | `gua_meanings` | `/api/divination/gua/meanings` | 资料、查表和交付 |
| P3 | `ziwei_rules` | `ziwei_rules` | `/api/ziwei/rules` | 资料、查表和交付 |
| P3 | `export_registry` | `export_formats` | `/api/export/formats` | 资料、查表和交付 |
| P3 | `export_parse` | `export_parse` | `/api/export/parse` | 资料、查表和交付 |
| P3 | `knowledge_registry` | `knowledge_catalog` | `/api/knowledge/catalog` | 资料、查表和交付 |
| P3 | `knowledge_read` | `knowledge_read` | `/api/knowledge/read` | 资料、查表和交付 |

## 同级的具体审查依据

| 范围 | 决定依据 |
| --- | --- |
| P0 · 共享历法与物理坐标 | 先核时标、交节／日序、同源坐标与宫轴；错误会传播到多个体系。 |
| P1 · 八字定盘与来源判定 | 先核四柱、取数和力量前提；原典分歧及工程政策保持分列。 |
| P1 · 数算、起卦与符号基础 | 先核实际起卦／整数环路、历法定宿及规则前提，再核派生时运与词义。 |
| P1 · 中式定盘与课传基础 | 逐层核定盘、星位／课传和规则版本；不以同表或同源软件代替原典裁定。 |
| P1 · 各星盘基础派生 | 核对应坐标、宿区／分盘／激活与基础几何；共享天文内核仍按P0先处理。 |
| P1 · 风水基础方位与宅盘 | 核北向基准、离散分区与盘式；作者条件、现场事实及现实效力分别验收。 |
| P2 · 八字专题与合参 | 先继承已核出生与规则事实，再核专题索引、条件解释及未校准分数。 |
| P2 · 时间层与关系层 | 核顺逆、端点、派生对象、关系方向及上游依赖；不把多个共享层当独立证据。 |
| P2 · 西占时运与事件 | 核实际搜索／时间钥／排序与作用条件；先复用已核时标、轨道和坐标定义。 |
| P2 · 风水时间与综合条件 | 核流盘边界、实际启用层和条件汇总；不以综合状态覆盖未完成的子层。 |
| P3 · 资料、查表和交付 | 核查询身份、原文与作者版本、完整输出和投影；资料读取通过不提升核心算法验收。 |

各定义的实现位置、审读状态和验收范围见[细粒度清单](algorithm-inventory.md)。截至本轮，检查器登记 14,869 项审查职责。源码扫描另列 1,557 个未归档定义、1,664 个模块绑定和 1,713 条模块语句，仍需逐项确认其职责及影响。

第十六批继续核P1八字有效力量与金口诀原典。HJ06的三条强档覆盖与寒暖反证仍未得到通用来源修复，P35／P52又不能据合算唯一改日时，继续保留原优先队列和失败；周期native求根的完整职责归层没有替代其连续／物理验收。当前逐职责计数见[中央清单](algorithm-inventory.md)。
