# 时运技法按问题选择

本参考用于阶段细问、用户点名技法或要求生命周期结构时；普通主题先按[共享时间选择](../../_shared/timing-selection.md)，不默认全栈。工具是否公开、参数与返回以当前 Schema 为准。下面的年龄范围是计算范围，不是寿命估计；遇到寿命、生死、灾祸和临床请求先停止该推算。

## 聚合与单技法

已有聚合结果直接复用其分支；只缺某一层时才调用单技法。首次严格投影应保留 `analysis_context`、所需业务根和相关 `natal_reference`，不只取一句 summary。单项与聚合路径不同：单项读下表根，聚合才有 `time_lords/returns/directions/transits` 前缀。字段名不是输入参数。

| 所问任务／选用条件 | 工具与业务根 | 新增依据、输入及复用 |
| --- | --- | --- |
| 当前人生阶段、何时换段 | `firdaria` → `firdaria.current_major/current_sub`；需邻段取 `firdaria.timeline` | 主分运实际起止、昼夜顺序与年长口径。首次沿用工具的法达首轮字段；`calculation_options` 只在非默认夜盘顺序或年长口径下返回，不能无条件加入严格投影。用户确实选择变体时可取完整 `firdaria` 根并核对实际选项；不为获取该字段改变算法版本。使用已确认出生资料和目标日期；已有主／分运不重算，追问只读同 run 的相邻条目 |
| 目标生日年度重点／按月细分 | `profection` → `profection`；相应单项实际返回的月限字段按合同 | 年龄对应的激活宫、星座与年主，不等同公历全年。用相关本命配置解释年主；已有聚合小限复用，不为增加方法数另算 |
| 返照时点、返回时刻和角度 | `solarreturn` → `solarreturn`；`lunarreturn` → `lunarreturn` | 确需年度／月度返照参考才用；目标日期、实际返照地点与时区按合同。业务根读 `return_datetime/ascendant/medium_coeli/sun/moon`，返照地点独立读 `analysis_context.return_location`，不能拼成 `solarreturn.location` 或 `lunarreturn.location`。当前返回不是完整12宫与全部行星相位，不据此编完整返照盘 |
| 指定时点的行运联系 | `transit` → `transit` | 读 `analysis_datetime/orb_limit/hits/exact_hits` 及命中两端、相位、容许度；需目标钟时和已确认位置。筛选列表不是全年事件表；行运自身 house 不当本命叠宫 |
| 用户指定某年盘或太阳弧 | `givenyear` → `givenyear`；`solararc` → `solararc` | 按实际 `year_start/year_end` 或 `arc_degrees`、返回点位和 hits 分开解释；目标日与钟时按合同。不把符号弧度当观测天空，不重跑聚合已有层 |
| 明确主限、某主限接触或图 | `pd` → `pd`；`pdchart` → `pdchart` | 核对所选根实际返回的 `method/time_key/pd_type/coordinate_system`；`pd` 读 `current_window/timeline`，`pdchart` 读 `hits` 与自身图盘点位，不能交叉照搬子路径。事件年龄／时间保留其时间钥及 backend 精度，不把方法标签、当前弧度或单条精确时间写成事件预言 |
| 要按福点／精神点比较分期 | `zr` → `zr.fortune/spirit` | 各轨 `current_level_1..4`、`level_1_timeline..level_4_timeline`、`lot/base_point/peak_signs` 保留所属轨和层级。先按问题选择轨，不将“高峰／解结”标签等同成功或灾祸；已保留轨直接读，不重复算另一套凑一致 |
| 点名十年星限或需另一种分期机制 | `decennials` → `decennials.current_level_1/2/3/timeline` | 核对 `base_order/resolved_start_planet` 与各段 start/end；这套机制与法达独立，只有新增问题需要才加，不累加为预测置信度 |

## 生命周期任务卡

共同输入是已确认的公历出生日期、钟时、地点／时区及接口必需坐标；不能将示例和默认出生小时当用户事实。技术参数未指定时可采用实际合同默认并标明口径，不要求普通用户决定所有算法参数。用目标日期的三项工具与整段年龄表要区分，不能照目录概括成“全部无需目标时刻”。

| 用户任务／选择条件 | 工具、额外输入与实际读取 | 新增信息与边界 |
| --- | --- | --- |
| 想看粗粒度传统人生阶段 | `astro_planetary_ages`：可选 `analysis_year/month/day` 标当前段；读 `planetary_ages.bands/active_planet/current_age_years`、各段 natal_condition | 七分期年龄带与主星条件；不是个体事件时间表。追问当前段时复用已返回 bands，不重新生成整表 |
| 点名三分主星、比较三阶段 | `astro_triplicity_rulers`：`division/lifespan`；读 `triplicity_rulers.sect/sect_light/element/stages/lifespan_years` | 昼夜光体所据三分主星及阶段年龄、角色与本命条件。`lifespan` 仅人为划分参数，绝不答能活多久；默认75年也不是命定寿命。三阶段相同长度来自口径，不当个案验证 |
| 想看月相周期的阶段转换 | `astro_lunation_phase`：`max_age_years`；读 `lunation_phase.natal_phase/progression_rate_deg_per_year/synodic_cycle_years/phase_ingresses` | 当前实现从本命日月距角按固定平均速度推八相年龄边界，非逐日星历搜索的精确次限新月日期。按返回年龄说阶段，不能补精确公历应期；同表覆盖范围内追问直接复用 |
| 点名界推运／分配法 | `astro_distributions`：`time_key/max_age_years`；读 `distributions.direction_model/rate_deg_per_year/periods`、段内 participants | 目前为黄道上升按时间钥经过埃及界的分段及星体接触年龄；不是赤道／地方半弧主限的替代。时间钥不改来挑好答案；已保留段可继续解释其分配星与参与星 |
| 点名调波或某阶共振 | `astro_harmonic`：`harmonic/orb`；读 `harmonic_chart.harmonic/positions/resonant_conjunctions` | 本命黄经乘阶数得到的配置及合相。调波是结构转换，本身不返回人生阶段，不因默认9阶就编九年周期；追问相同阶数复用，改变阶数才新增计算 |
| 点名 Balbillus 分期 | `astro_balbillus`：`start_planet/mode/max_age_years`；读 `balbillus.mode/start_planet/zodiacal_order/periods` 及 sub_periods | 读取本版本起星、距离模式和大小段年龄，不与另一种129系统混同。表的上限是取数范围，不是寿命；先说明新增机制，普通年运无需默认加入 |
| 点名数字相位／120年关键点 | `astro_keypoints`：`release_mode/max_age_years`；读 `keypoints.release_mode/positions/activations` | 月亮或上升释放模式的数字位置、周期激活与年龄；这是该模型的结构条目，不能把“关键点”命名当现实重大事件保证，不能自行换 soul/body 找吻合 |
| 点名129年小年轮值 | `astro_yearsystem129`：`start_planet/max_age_years`；读 `yearsystem129.sequence_model/start_planet/total_cycle_years/periods` | 本实现是本命黄经排序的轮值，`sequence_model` 明示不是原后端逐值核验；129年是模型周期。与 Balbillus 独立，不能只因名字相似合并结论 |
| 想看指定日期的某行星弧 | `astro_planetaryarc`：`arc_source/orb/analysis_year/month/day`；读 `analysis_context.analysis_datetime`、`planetary_arc.arc_source/arc_degrees/positions/hits` | 所选源星的二次推运弧施于整盘，再对本命取相位；不同源星不等于太阳弧。同日期追问读保留 hits，改日期才需补目标计算 |
| 点名波斯向运 | `astro_persiandirected`：`max_age_years`；读 `persian_directed.rate_deg_per_year/hits/hit_count` | 符号1°／年的推移，对本命星体与宫头命中，当前最多保留按年龄排序前120条；未出现不证明没有后段命中。返回 date 是该符号模型日期，不是事情发生日；不补小行星／中点／阿拉伯点的未覆盖命中 |
| 点名 Huber 年龄点 | `astro_agepoint`：`max_age_years`；读 `age_point.years_per_house/cycle_years/points/contacts` 与 `analysis_context` | 实际强制 Koch 宫、每宫6年、72年一周；继承的 house_system 不改变本方法。年龄点接触是符号进程，不把72年当寿命，也不由宫位推疾病 |
| 点名恒星黄道二次推运 | `astro_vedicprog`：`orb/analysis_year/month/day`；读 `analysis_context.analysis_datetime/ayanamsha`、`vedic_progression.zodiac/positions/hits` | 本实现用 FateBridge 的 Lahiri 式偏移，`vedic_progression.positions` 为恒星黄道，`analysis_context.zodiac_type` 是 `Sidereal` 而分支 `zodiac` 是 `sidereal`；当前顶层 `natal_reference` 仍来自热带基准，不冒充恒星本命落点。不是完整吠陀达沙或分盘。按实际点位与命中解释，不能因工具名就称已覆盖印度全部时间技法 |
| 点名赤纬推运／平行相 | `astro_jaynesprog`：`orb/analysis_year/month/day`；读 `analysis_context.analysis_datetime`、`jaynes_declination.parallels` | 逐条读 natal/progressed、赤纬、kind、orb；这与黄经合相不同。空表只限制此容许度内的赤纬命中，不否定其他阶段依据 |

## 交付和追问复用

选择前说清这层能回答什么、新增什么；没有新增价值就沿用现有阶段。交付实际边界及相关主星／点位的两三项事实，再给与用户已知安排有关的一项建议。不同机制保留分歧，不按命中次数投票，不展开未问的整个人生。

年龄表中的段界、主星、接触与峰段都是传统计算结构，不作事件、成败或健康结局。具体某年问题仍需对应年层，不能从粗分期编月份。返回只精确到年龄时保持年龄精度，不能自行手算精确日期。

同出生资料、同参数和已覆盖范围的追问，读取原 run 已保留分支／分页；用户只要解释不重算。完整时间线或文件首次 `fields=null`、保留默认预算，再按同一 run 交付；字段裁除后分页不会恢复。改日期、阶数、时间钥等确需新增计算时关联原 trace，并明确改变了哪项输入。

## 非个人盘

`astro_mundane` 用于年度节气入宫等世俗盘；`astro_extrareturns` 用于其他行星回归时点。仅在用户明确所问相关机制时选择，按其实际输入读取 `mundane`／`extrareturns`；不默认加入个人年运，不把世俗盘用于确定政治、金融或灾害结果。

实现核对入口：`services/western_lifespan.py`、`core/requests/western_lifespan.py`、`core/astrology_lifespan.py` 与 `core/output_western.py`。这是计算口径的复核索引，不替代具体传统解释来源。
