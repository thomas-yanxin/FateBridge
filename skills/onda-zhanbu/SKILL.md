---
name: onda-zhanbu
description: 用 FateBridge 围绕一个具体问题起卦或起局，呈现可复核的卦变、体用或盘局依据，把传统提示转成现实中需确认的条件与下一步。Use when 用户明确求一卦、占卜、梅花易数、六爻、奇门、大六壬、金口诀、太乙、宿占、三式合参、星骰或西洋卜卦；已有结果解释沿用原卦，不反复起卦，不代替用户决定。
---

# 问事与占卜

围绕用户悬而未决的一件事，讲清「这次卦／局是什么、传统读法强调哪处变化、现实中还需确认什么」。算出的卦象要可见、可复核，不能起卦后只回一段通用鼓励，也不能把传统吉凶变成真实成败承诺。

## 共用范围与安全

先读短的[咨询核心](../_shared/consultation-core.md)。主题重叠或扩展才查[范围选择](../_shared/consultation-routing.md)，涉及目标时段才查[时间选择](../_shared/timing-selection.md)；遇生死、临床判断或医疗择时先按[硬边界](../_shared/safety-boundaries.md)停止相关计算。

## 引用路径与按需资料

发现入口可能是软链接。先进入入口目录，以 shell 内建 `pwd -P` 取得真实目录，再解析相对引用；不要裁剪 `.agents/skills/onda-*` 的字符串父目录。

- 参数不清楚或需要完整交付时定位：[../_shared/fatebridge-engine.md](../_shared/fatebridge-engine.md)
- 需要表达或来源细则时定位：[../_shared/onda-counsel.md](../_shared/onda-counsel.md)
- 主题重叠或扩展时定位：[../../docs/scenario-routing.md](../../docs/scenario-routing.md)

所有起卦、装卦、体用、用神与起局交给引擎；不得用临时随机数、手算或模型记忆替代。用户提供的既有卦例要沿用，所选工具无法接收该卦例时说明范围，不暗中换成当前时间重新起卦。

## 先明确一件事与取法

用户已经说明具体问题与起卦方式就直接沿用，不重复盘问。问题含糊到会改变判断对象时，一次用一两句核对：问的是哪个选项、考虑到什么时候。不要为起卦强要生辰或完整人生背景。

太乙四计或三式合参的技法核对、已有结果解释也从本入口读取对应参考。用户已给日期、配置或原结果时，按这些资料复核；不为解释计算另索现实占问、出生资料或换成当前时刻起局。

用户未指定卜法时，以时间梅花为默认的一项主证。普通现实决定但未请求术数时，不因“要不要”三个字自动起卦。

| 用户的选择／所问 | 主证工具 | 实际输入与交付重点 |
| --- | --- | --- |
| 即时问事、指定时刻梅花 | `meihua_analysis` | `analysis_year/month/day/hour`及已确认时区；分、秒已知才给，按实际合同；本卦、动爻、变卦和体用 |
| 已有卦、实际物件数量／听声／字形／长度／端法资料 | `meihua_cast` | 用 `casting.method` 选择原法，提供该方法的实际资料；物数用 `object_count`、确认数量和时支，超八核对计数口径及两套卦变，不用下卦余数代替原时支数。已有卦用 `existing`、卦码及唯一动爻，不另起。见[显式取法](../../docs/meihua.md#显式原始资料与已有卦) |
| 已有四卦的统摄组合 | `tongshefa` | 按用户实际给定的 `taiyin/taiyang/shaoyang/shaoyin` 四卦组合左右卦、潜藏与亲和；固定默认不是本次起卦。当前不实现蓍草十八变／大衍随机起卦，用户要后者时直接说明范围 |
| 六爻 | `sixyao` | 手摇初爻至上爻六个 6／7／8／9 用 `coins` 或已有 `gua_code`；REST/MCP 可传 `lines`。随机起卦保留 seed，解释已得卦不再摇一次 |
| 奇门方位、时机与谋略 | `qimen` | 所选时间及实际选项；先读局与相关宫，未返回的用神或事件判定不补写 |
| 大六壬起课 | `liureng_gods` | 实际起课时间／选项及返回课传；按[六壬取证](references/ren-evidence.md)核贵人配置、旬遁与取传，课名不直接确定事件和应期 |
| 六壬行年 | `liureng_runyear` | 出生日期、性别与分析时刻；读取农历虚岁行年和该时刻课盘，当前没有逐流月预测，不编流月结果 |
| 金口诀 | `jinkou` | 地分 `di_fen` 与起课时间；不猜地分，按[四位取证](references/ren-evidence.md)区分季节旺衰、位内旺衰和阴阳取用。明确指定京本行年时另用已确认的出生年干支、指定一岁起算岁序及男／女；原问课与推导另课分开，缺项不借六壬行年代替 |
| 太乙 | `taiyi` | 按[太乙取证](references/taiyi-sanshi.md)选择已实现的年／月／日／时计，核对所选起元、钟面、主客算与实际格局；现代适配不冒充完整古历或玄命 |
| 宿占 | `suzhan` | 日期与输入时区；钟时未知可先读历法与候选，星图／天文宿位须已知钟时和所需地点；按[宿曜取证](../_shared/sukuyo-evidence.md)区分事项冲突及昼夜条件 |
| 三式合参 | `sanshiunited` | 仅用户要求合参时用；所选太乙计法放入 `taiyi_options`，按[分层取证](references/taiyi-sanshi.md)读实际 `time_scopes`、方位对应和来源分歧，不把三系合成统一胜负或概率 |
| 解读已有星骰 | `otherbu` | `planet/sign/house` 必填，实际第N宫传 `house=N-1`（0..11）；支持南北交点和中英名/符号。无需时间地点；附加天象须完整提供实际时地。按 `symbolic_details/interpretation/rule_trace/rulesets/validation` 解释，逐项来源看 `condition_evidence`，转述依据看 `interpretation.evidence`；问题原文不是计算断语，不把假设轮当实际盘，不补度数、互容或应期，不自动抽骰；缺少合同才读 [otherbu](../../docs/contracts/otherbu.json) |
| 西洋卜卦 | `astro_horary` | 提问时刻 `question_*`、地点 `longitude/latitude`、时区与 category；不把出生时间当提问时间 |
| 查已得卦的含义 | `gua_lookup`／`gua_meiyi` | 按卦名／号查询；查义不另起卦，引用与本卦关联的条目 |

## 固定问时，保留同一卦

交节附近保留同次`calendar_conventions.cast_at`和`calendar_context.bazi_month_boundary`的完整小数秒与时区，核对实际使用的前后节界。农历与公历时刻字符串现在也保留计算消费的小数秒，不能自行截成整秒再据此解释换月。天文机构的分钟表只能提供该公布精度的对照，不把分值补成已知精确第0秒；数值求解的小数位也不是物理准确度证书。复核范围见[交节审计](../../docs/liuyao-solar-boundary-audit.md)。

时间梅花需要明确起卦年月日时。用户指定时刻时原样保留日期、小时及已确认的分、秒和 `analysis_timezone`；未知分、秒省略或null，不把计算补00冒充用户提供。核对 `analysis_context.analysis_datetime/timezone/question`。按当下起卦才取得当前时间和相应时区，不用示例日期或默认时区冒充用户选择。`as_of` 不能代替所选工具的显式起卦参数。

其他卜法按各自输入，不强套梅花的年月日要求；有用户手摇记录就不改为随机摇卦。复问同一件事先解释、核对或复盘原结果，不重复起卦凑答案。资料更正确实影响计算时重建输入，沿用 `trace_id`／`parent_run_id`，说明哪一事实变化。

普通首轮使用实际合同中验证过的 `fields`、`strict_fields=true`、`include_snapshot_text=false`。按所选工具检查结构化业务结果，不把快照只有文本误读为业务结果只有文本，也不套用梅花式字段；确无独立业务字段时保留必要文本。

## 星骰：总体分派与条件角色

解读 `otherbu` 的三分性时，读取 `symbolic_details.triplicity_condition`：`assigned_rulers/in_assigned_group` 保留原典的三角总体分派，`rulers_by_sect/roles_by_sect` 保留各昼夜条件下的首要或明确共管角色；`matches_by_sect` 只比较后者，口径见 `match_definition`。

例如木星白羊座属于总体分派，昼条件所列首要主星为太阳，夜条件为木星。`in_assigned_group=true` 且某条件的 `matches_by_sect=false` 时，说明总体分派及该条件的具体角色，不能写成“不属于该三角”或“没有尊贵”。`sect=null` 时保留两种条件，附加天象的昼夜不替骰面选定条件；七曜以外的 `null` 保留为范围未定义。分页标为延期的解释与来源按 `result_delivery` 从同一 run 取回，不重算或补写。详细字段与原典范围见[占星骰说明](../../docs/astrodice.md)。

## 梅花：让卦变解释这件事

端法已确认上下卦仍用`observed_trigrams`。若明确提供原文五类物象，可用`observed_categories`，由领域代码查表：elder_person老人乾、young_person少年艮、cow牛坤、chicken鸡巽、dry_wood槁木离。须有非空subject_description、确认单一对象的布尔single_subject_confirmed=true、八方direction、from/toward/at的direction_role及hour_branch；当前聊天已明示这些事实即可据实填写，不重复追问。未知类别、普通木材或未确认枯木的落枝、群物不补分类，不猜年龄门槛。来方不换成相反行进方向；少年从南来用南离，不因向北走改坎。用先天卦序加原时支一次取爻，不用洛书宫数或默认GPS扇区。读`meihua.seed.observation_basis`或`observation_source`字段卡，按输入路径核对原句、原页、声明与实际卦图；新入口不补占者活动、外应或季令，现场与完整起占条件仍未独立核实。五类有限范围、复用原例及参数格点都不证明唯一古法或现实预测有效。详见[已报类别端法](../../docs/meihua.md#按已报物象类别起端法卦)。

时间入口`meihua_analysis`仅在相应分量已确认时可选给严格整数`analysis_minute=0..59`、`analysis_second=0..59`；未知省略或null，数值计算补00，仅是名义参考，不保证未知时段内月令相同。读`civil_clock_resolution.input_components`区分已提供分量与计算补位，按摘要如实说明参考时刻；输入位数不认证现场精度，缺项不推断四舍五入、截断或误差区间，`calendar_stability=not_assessed`不能说成已验证稳定。秒数只定位实际时刻，不参与起卦取数，也不证明时钟、星历或预测精度。可保留`analysis_timezone`并给`analysis_utc_offset`核对重复钟时，不能把地区时区静默换成固定偏移。读取`analysis_context.civil_utc_offset/civil_instant_utc`及`meihua.calendar_policy.civil_clock_resolution`；未知偏移不猜，跳时或整日跳过不能靠偏移补成有效。交节比较沿用已确认实际UTC，农历日期和时支仍取原地区民用钟时。不同UTC若当地日期时支相同可以同卦，不强求卦象不同或算作独立占验。实际回拨可为一小时、半小时或所选历史记录的343秒，不能套固定时长。历史偏移只证当前tzdb记录，不证明现场钟表或秒级天文精度；消歧约定不是原典唯一时制或现实预测验收。详见[钟时消歧](../../docs/meihua.md#民用钟时地区时区与明确偏移)。

四声字占`text_tones`的1／2／3／4是所报平／上／去／入类别，不是现代拼音一至四声，也不能笼统认证为唯一中古音。可用`tone_reference`记录已确认音系、来源及读音层次；缺项保持未知，声明存在仍非工具独立鉴定。读取`meihua.seed.text_tone_basis`及两处证据范围，逐字类别与事实路径照录。所选「今日動靜如何」原例动静取去声，另一韵书归上声不能用来静默改原例；该句类别比较只核对所报数组，不是全历史音系认证。数组不同时说明本次没有复现该原例取音；其他文字及未给文字不借用原例认证，不自动查字、套连读变调或生成另一卦择优。详见[四声依据](../../docs/meihua.md#四声字占的音系与原例依据)。

字数起卦须先区分文字依据和取爻口径。`text_count`默认固定转录2690596的11至100工作范围；显式`text_basis=nlc1925_selected_span`保留影印百餘字，超过100仅为精确原文范围未裁定的软件算术扩展，1百万保护上限不是古籍上限。读取`meihua.seed.text_count_basis`及两处证据范围，不把范围未定转成原典完全符合。`line_sum_basis`可明示原字数或两卦卦序数，分歧时每支候选的本互变、原体用、季令和题篇均分别读取；17字可从用生体变为体生用，32字还可能改变互卦。它们是未唯一裁定的计数解释，不是已证同等古法，不因所问结果挑口径或版本，不将字数说成声数，不补未给时数；两口径暂同也不证明全局唯一。

明确提供农历年支、月、日、时支与已报加数时，可用 `meihua_cast` 的 `lunar_time_added_count`；不自动按姓氏猜笔画或补绝对年份。上卦原数含加数，再加原时支一次取下卦及动爻。文明书局本的田6、王4、韓21仅属该例所给数；影印27余6为三爻与丰变震相符，固定网络转录“初爻”异文保留。局部资料不能验证月长、闰标志或节月；详见[显式取法](../../docs/meihua.md#显式原始资料与已有卦)。

人事解释还读取 `interpretation.internal_countercontrol` 或 `internal_control` 字段卡。生体之卦受制时说明生助受限，克体之卦被制仅取稍解其凶；不改原有四段关系。离火制兑金时仍可能同时泄木体，两面均需解释。五个分析角色不是五次独立观测，季令弱或未知不自动关掉制约；制约者再受克不递归抵消、不计票或加权成最终成败。每个计数候选沿用自己的节点与事实路径，天时分支该字段为 `null`。原文局部符合性不等于现实效力或完整章节综合通过。

已报外应可明确选原文金银世宝`gold_silver_treasure`、兵刃`weapon`，读`external_symbol`卡或完整`interpretation.external_omens.body_relative_symbols`。只有当前聊天明确类别才填，不从普通金属饰物、刀锯、标签文字或所希望的吉凶补分类；兵刃不泛指所有现代武器或木棒。金为典籍类别，不认证材质。震巽木体见金银，原句反为不吉；坎水体见兵刃，原句反为不凶，不能改成必吉或现实安全。其他体的所选限定为null，不能用通常吉凶象填结果。旧实物资格仍独立，未覆盖的新类别不继承真克、无实克或真生。每个计数候选用自己的原体与路径，多记录不投票或充作独立观测。不作临床、生死、生产判断，不把两则限定说成完整内外合参或现实预测通过。详见[原体限定](../../docs/meihua.md#宝象凶器与原体限定)。

人事内卦紧次与情境条件读`interpretation.stage_emphasis`或`stage_emphasis`字段卡，审计用`stage_emphasis_audit`。`matter_scenario`只接已确认的原文事项类别：`favorable_matter`为问吉事、`unfavorable_matter`为问不吉之事；未知不补，不从愿望、题篇或问题情绪推断，也不是预测出的吉凶。声明与原始输入路径随`scenario_declaration`保留，未独立核实。未给时情境字段保持null；必要卦内结构已不满足时整句适用为false，结构满足但情境未给时才为null，不从不适用反推情境。已给时`full_clause_applies`只核对所选条文前提，不能变成成败、无害或灾祸保证。用互变的紧次不是权重；互层迟速句范围未裁定，互中有生体且所报吉事情境也仍待定。生体与克体并见，吉事情境的阻节句要同时保留；三条`scenario_clauses`区分吉事无生有克、不吉事有生与无生。生助受制与旺衰仍需说明，不抵消或投票成净结果。每个候选共用所报情境但分别核对自身原体与关系；不擅选最早最迟，不推日期或概率。天时不接此参数。详见[内卦情境条件](../../docs/meihua.md#内卦的紧次与生体迟速条件)。

默认字段清单与`reading`卡已包含`interpretation.seasonal_qualification`；旺衰与生克合读也可使用 `strength` 字段卡；有取数候选时用 `strength_audit` 保留各自季令与直接制约。按所选卷二《衰旺论》分列体旺逢生、体衰逢克、体衰有生三个条件，体衰受克与有生可同时成立，加重与“衰稍解”都要解释。`preferences` 的体宜旺、生体宜旺、克体宜衰不是联合必要条件，不加总打分。`原文未定`与缺节月保持待定，不写中性或弱；生助受制等仍须同看，未裁定净结果。“重遇克”不补次数阈值，未作月日合参或全书章节优先级。候选的 `strength_fact_path` 指向自己的 `casting_readings` 季令，不引用主候选强弱；天气不使用这一人事层。另读`volume3_qualification`：体旺受克的限定、体衰、体旺有生与逐角色乘旺句分列；克体且旺属于明示例外，不能引用乘旺皆吉。分读`favorable_clause_applies`与`attacker_wang_exception_applies`，克体角色即使强弱未知，吉句也为false，旺克例外本身仍可null；不以pending_strength补吉句。`matched_selected_month_conditions`不是净作用；受制、卷二条件与日气仍并列。`seasonal_qualification.summary`已带卷二、卷三来源标签并列两段所选条件，主摘要及各候选同步呈现；原卷二文字在`volume2_summary`保留；内外有生／无生及党多仍待裁定，未评估外应不等于确认外无生。不据无大害措辞保证现实安全、临床或诉讼结果。

已明确提供外应类别及描述时，可传`external_observations`并读`interpretation.external_omens`或`external`字段卡，仅用于已发布的人事分支。未知不补、无现场资料不猜；null是未采集，不是确认没有外应。原体仍取本次实际静体，各计数候选用自己的原体与路径。`raw_relation_to_body`只给符号生克，按所选卷三实物／形色条款另读`qualification`：炉火、烛火、红紫色，锐器、饰物器皿，土、瓦器，柴薪、未伐树分别解释；详细配对未覆盖就保留未知，不自动外推。勿把真生真克说成实测物理、临床或灾祸判断，不把捷迟轻重换成数值强度、现实成败或日期；当前未做内外综合。11个类别及12条配对是局部范围，12条输入上限仅软件保护。原页与用字差异随`ruleset`保留，详见[已报外应资格](../../docs/meihua.md#已报外应的实物与形色资格)。

求财补充还读 `interpretation.wealth_components` 或 `wealth` 字段卡，先确认显式 `interpretation_topic=wealth`。按文明书局《求財占》补充句逐角色核对原体与初用、体互、用互、变用；有财相关体克用／用生体与破财相关用克体／体生用可同时出现，初始条款、生助受制、克体被制及耗泄都要保留。`all_named_components_present` 仅为成分全有的事实，原文“及”组合及综合效力未裁定，不能作整句适用、净财运或确定事件。每个取数候选另读自己的 `casting_readings[].wealth_components` 与路径；不计票、抵消或借用主候选。`timing_reference` 只是原文依据，不把卦气、起卦日期换成进财破财日，不作金额、投资或收益保证。详见[求财补充](../../docs/meihua.md#求财补充句的内卦关系)。

失物问事显式用 `interpretation_topic=lost_property`，读 `topic` 或 `topic_audit` 字段卡的 `interpretation.topic_reading.chapter_qualifications`。五条初始体用与位置类象分别读取；原句“物不失矣”不能否认用户已报遗失，也不能断定已找回。方位采用已明示的变用经卦读法，按自身动爻核对 `selected_trigram`、`trigram_fact_path`，不取未变的一半、不用互卦替代，也不混入先天序数。每个取数候选读自己的 `topic_clause.chapter_qualifications`，有分歧时保留，不按希望结果选择。影印本“舟車”、转录“舟居”等异文不混用；该角色读法尚未唯一裁定，方向没有现场参照原点，地点是原文类象，不是实际位置或进入现场的许可，不补寻获日、坐标或概率。详见[失物占](../../docs/meihua.md#失物占的体用与变用方位类象)。

问天气时显式用 `interpretation_topic=weather`，读取 `weather` 字段卡。卷二天时占不分体用，下表中的体用人事解释不用于天气；先读 `selected_readings` 的 `effective_status/controlled_tags/conditional_tags`，不能只凭原始 `matched` 断天气。`controls` 保留金制震巽、土制坎、水制离及五／六位置计数分歧。季节与久雨久晴只用已确认事实，“多”无默认阈值，不按已知天气调口径。旧研究政策的2025回测未胜较好固定基线，不能说当前新组件已提高现实预测力。`single_forecast=null` 不补造唯一晴雨预测。详见[天时分支](../../docs/meihua.md#天时占独立分支)。

读取 `research_validation` 时分开旧政策2025记录与 `additional_profile_audits` 的当前1.5.0政策2024记录。后者16/29与同日恒无雨相同，337日弃权；全366日主终点正确贡献16，对比恒无雨214，未通过。全队列正确贡献不是非弃权命中率，不跨政策或年份合并；追加回顾检验也不称为盲验或前瞻通过。

当前1.7.0另读 `research_validation.current_profile_study`：预先固定的2026年1—9月主队列273天，按起卦节月明示季节时49天有无雨标签、29天正确、224天弃权；全队列正确贡献29，对比始终无雨158，未通过。2024、2025及季节未知的敏感性情形另列，不能选较好子集替换主结果。2,008份情形记录只对应1,004个日期，且是单站相关时间序列，不作独立样本计数。朝晴不能映射成全天无雨；午时队列并未命中朝暮条款，不能因此认证朝暮预测。日期桥接和晴象转无雨是研究假设，资料早已公开，不能称盲验、前瞻通过或权威认证；原未来账本保留。

参考基线另读 `research_validation.reference_baseline_supplement`：现代持续性和1991—2020月度多数类不属于梅花预测。前一日中午不能使用尚未完成的当日总雨量；最近完整日为目标日前两日，观测完成与实际公布分别核对。273日条件性历史参照正确183、190，对应旧标签正确贡献29；同49个类别日期参考各31、旧标签29。但资料当时的发布时间未证，可确认历史可用日期均0，`operational_superiority_gate=null`，不能把这些数字说成实盘基线已验收，也不能把未知参考记0分让卦象胜出。12个月常年雨日数核对相符只支持所选观测统计，不是现实预测或古文“晴”验收；旧29对始终无雨158未通过的主终点保留，不跨年份或情形挑胜者。

若天气结果的 `casting_variants` 非空，逐候选读取其自身的 `selected_readings/control_statuses`，核对 `casting_comparison`，不把所选候选的天气条款套给另一套卦。`same_rule_results_for_supplied_context` 只表示已提供条件下所选规则结果相同，不能说计数法已被原典唯一裁定或天气预报已一致；不合并候选频数、不按已知天气挑候选。需要完整候选条件轨迹时，首轮选 `weather_audit` 或 `fields=null`，再从该 run 的 `result_delivery` 读取 `casting_variant_traces`；摘要投影没有选取的轨迹不能假称已保留或已读取。不另起卦凑答案。

区分一般“久雨得艮”的止雨象与“艮多久雨必晴”的晴象，后者另核已确认久雨、明示阈值及计数分歧；不能把单见艮或前期天气未知直接写成放晴。“久晴不雨，得此亦然”的指代仍未唯一裁定，不补出见艮必雨的反向断言。`prior_condition=neither_prolonged` 仅用于久雨与久晴两个条件均已确认不成立；`null` 是未知，不为消除待定而补值。一天无雨不证明久晴，缺测、间歇天气也不自动证明两者均不成立。该值只关闭四项前期条件条款，不补季节、阈值或唯一晴雨结果；旧负面实测保留，新增输入状态不是预测提升的证据。

天时条文同时核对`source_witnesses`：影印所选字句与固定转录有“多雨／必雨”等差异，未确认的字形和主语不凭熟悉文本补齐。震多春夏另核季节，巽多四时及兑多亦阴另核阈值和计数资格；兑阴不是已确认无雨。影印选段目读不当作独立专家或全章认证。

1.6.0的秋金晴、冬坎雪、春土雨明确按固定卷二转录1441921；仅用已确认季节，乾兑或坤艮任一实际出现即可，不添多字阈值。所选文明书局冬句未见“坎之水”，春句读“坤兌”，与转录“坤艮”不同，照录来源差异，不据五行常识修字。春土雨不能随受制的坎雨一并取消，秋金晴不能随受制的离晴一并取消。取爻候选各按自身卦象核对冬坎；旧1.5.0现实检验不认证本轮新增条款。

1.7.0的“离在艮上暮雨朝晴”各按实际同一重卦上离下艮核对，朝晴、暮雨保留各自 `time_scope`，并读 `time_scope_comparison`。不同朝暮不当作同窗矛盾；未定时段不当作全天，与朝暮的关系仍待核定，不自动交集、排序或裁优先级。已知起卦 `analysis_datetime` 不自动定位原文的应验日，也不补几点或日出日落；每个取爻候选使用自己的卦图和时段比较。后句“离互艮宫”仍未裁定，不据普通互卦图式猜出其含义。

求谋、求名、求财、交易的主题明确时，可显式选 `planning/reputation/wealth/transaction` 并读取 `topic` 字段卡。当前题篇层依据文明书局本卷二四章的初始五种体用条款，读取 `topic_reading` 的原体、用、章句与版本。交易体克用在所选影印作“交易成迟”，固定转录另作“有财”，两者分别列出；不按所求结果换版本。“迟”不换算具体日期，财象不换算收益概率。互变、旺衰尚未在该题篇层综合为现实结论。各 `casting_readings.topic_clause` 属于本候选的原体用，不能套主候选的条款；首轮可用 `topic` 卡，规则核对用 `topic_audit` 卡。

明确问出行或谒见时，两入口另可显式选 `travel`／`meeting`，依据同本两章的10句并保留独立规则集。出行的 `topic_reading.chapter_qualifications` 另列“体宜乘旺”与四辅助角色各自生体偏好；未知节月或“原文未定”保持未知，受制另看本候选资格，不合计成许可、吉凶分数或要求全部生体。多字阈值、舟陆等角色范围未裁定，不据内卦计数选交通方式或路线。影印末句未见“兑”字，不能用固定转录“兑主纷争”补其主语。原文“祸”等用语只作历史文本记录，不能变成实际灾祸判断；可见／不见、财象也不代替现实行程、会面或收益证据，不补应验日。默认一般解读不因关键词自动换到这两章。

一般占断若保留取爻口径候选，读取`interpretation.casting_readings`中各自的原体、生克、季令与实际动爻经文，不能把所选口径的体气、互卦或爻辞套给另一候选。纯乾坤按各自变卦取互；节月未知则季令待定。`casting_comparison`只比较所列事实，不由初应比和或体气相同裁定同一结局。

细分生体、克体的象义时，读`trigram_symbols`字段卡的`interpretation.trigram_relation_symbols`。同为金生水，乾与兑分别对应《体用总诀》的不同原句，不能只按五行互换卦名。`selected.role_evaluations`只按本次原体与四个实际角色匹配；`counting_candidates`各用自己的原体、关系、受制和旺衰。`matched_raw_relation`是引用条件匹配，受制不被抹去、未知旺衰不补定，未合成有效净象。原文“或”是备选列举，不能据此识别现实人物、姓氏、性别、实际地点或事件；灾祸与身心用语只保留史料语境。所选影印巽克体段作“南方”，固定转录作“东南方”，两者分列，不按通常巽位改字或输出导航。天时不分体用，此层为null。详见[八卦生体克体象义](../../docs/meihua.md#八卦生体克体的专属象义)。

按以下证据链组织，短答只呈现最有用的两三处，详细请求再扩展互卦与错综：

| 需要看清什么 | 实际字段 | 解读动作 |
| --- | --- | --- |
| 这一次到底算了什么 | 时间法的 `analysis_context`，或显式法的 `input_normalized`；`meihua.method` | 时间取数用 `meihua_analysis`；原始资料／已有卦用 `meihua_cast`，不能暗换方法或补当前时刻 |
| 当前局面到变化 | `meihua.base_hexagram`、`meihua.seed.moving_line`、`meihua.changed_hexagram` | 用一行「本卦 → 动几爻 → 变卦」呈现，再用实际卦义说明前后变化；不只念卦名或贴吉凶 |
| 主客如何作用 | `meihua.body_trigram/use_trigram/body_use_relation`、`interpretation.body_use_reading` | 先核对体用关系，再按用户问法作条件式角色对应；不能直接认定用卦是对方内心 |
| 初中终的实际制约 | `meihua.stage_relations`、`meihua.seasonal_strength`、`interpretation.traditional_stage_readings` | 用、体互、用互、变用始终相对于原体；生助和制约并存时保留混合，不在变卦重分体用。季令的「原文未定」不等于中性或弱 |
| 哪一步值得留意 | `interpretation.moving_line_phase/moving_line_oracle` | 说明返回所用的阶段与条件；阶段象意不是事件发生日期 |
| 可用处与限制 | `interpretation.action_hint/risk_hint`、卦内 `guidance/caution` | 各取实际相关的一处，转换为所问事项的注意点；生活建议另作标记 |
| 详细复盘的其他视角 | `meihua.mutual_hexagram/cuo_hexagram/zong_hexagram`、实际 `interpretation` | 用户要求才展开；每层说明自身依据，不强造它们都支持同一结论 |

引用经典时核对 `interpretation.classical_text_reference` 的实际动爻原文与来源；`position_hint`、`moving_line_phase`、卦义库建议是现代提示，不能冒充爻辞。`line_oracles` 只有 `is_active=true` 是本次动爻，其余是假设参考。首轮可用 `reading` 字段卡，核对规则用 `audit` 卡；详见[梅花计算与验收](../../docs/meihua.md)。季令只按本次实际返回标记解释，不补五态权重、未提供的外应或精确应期。

核对 `meihua.calendar_policy`：梅花按农历春节换年，四柱可按立春换年，两者不同不是自动矛盾；闰月沿用本月数，民用午夜换日。原文未唯一规定的边界是软件约定，不称为原典唯一口径。`evidence_scope.classical_coverage=partial` 只限制未实现分支；仍解读已返回的体用互变，不把测试通过说成现实预测认证。

人事动静读`interpretation.motion_context`或`motion`字段卡：`observer_activity`只接已确认占者当时seated坐／walking行／standing立；外应各条`motion`只接moving／stationary，未知省略，不从类别、描述、问句或车辆运动推断。体互静、用变动是内卦符号角色，与现场运动及占者活动分列。各候选保留自己的原体、角色与外应资格路径。坐行立只对应所选迟、速、半迟半速，无天数日期。动而吉／凶的速应句缺外应吉凶综合判断时仍待定，不能把`matter_scenario`的问吉事情境当成已判吉应，也勿索取所想预测的吉凶来补条件。影印未见与旧转录末见分存；不以静止取消已有起卦或断无事。不动不占与心境之静尚未自动裁定，三项未合成现实结局，天时不接此层。详见[三类动静](../../docs/meihua.md#内卦外物与占者的动静)。


人事静占条件用`observation_context`及`quiet`字段卡：只传当前聊天明确确认的同次`quiet_room`、`nothing_heard`、`nothing_seen`，严格布尔，未知省略或null，非空label说明资料。对象缺省是未采集，任一false为已报不符，三项均true仅为已报符合本句，不能说现场已独立证实无外应；不符也不等于一定有外应。三项均真不能同附外应记录，听声法与无所闻声明矛盾，观物法与完整静室无所闻见声明矛盾。不从内动爻、占者走动、问句或描述补知觉；物理静室不等于心境之静，不裁定不动不占，不取消卦或追溯排除预测样本。候选各读自己的原体、内卦和月令路径；原句年月日衰旺合参未完整实现，勿把seed历法取数说成合参完成。天气分支不接此层。原页多字与固定转录分存，详见[静占声明](../../docs/meihua.md#静室与无所闻见的声明条件)。

日气读`interpretation.day_qi`或`day_qi`字段卡。时间入口从实际民用日计算；23时按已声明午夜口径与子初口径分列，不能把八字晚子时日柱直接作午夜日气。显式入口只有已确认日支才传`day_qi_context`及非空label，可选声明日界，没有公历日期仍不能核实；未知省略，不借年支、农历日数、时支、问句或系统当前时间补齐。日支只配五行，不唯一配一个卦；各取数候选分别读自身原体、日气标记和月令路径。生体角色日气偏好旺、克体角色偏好衰；原文未定不是中性分数。月衰日旺并存时不抵消或投票，原体克日气不自动说有利；卦字所指的所选读法与异文随ruleset保留。日历日期不是事件应期，年气和完整年月日合参仍未完成，天气不接该层，不据新解释追溯删去旧预测样本。详见[日气与月日衰旺](../../docs/meihua.md#日气与月日衰旺)。

梅花所问涉及原文阻节计日时，用`obstruction_days`字段卡读同次`interpretation.stage_emphasis.obstruction_timing`及各计数候选。只在已明示问吉事情境且本候选内卦同时生体、克体时读激活日数；不为激活规则替用户补情境。乾一兑二是原句明例，其余六卦是按类推句与卦数推得，交付时分清。重复同卦不累计，不对多个日数擅取和、最大、最小或平均；核对实际原体和制约路径。它们是原文条件日数，不是净延误天数、实际成败或完成日期；起算点与首尾日边界未定，不能按当前钟时加日。已存在的日气、月令与直接制约仍同时保留，未知、未激活和无克体分别按字段解释。详见[阻节计日](../../docs/meihua.md#生克并见时的阻节计日)。

仅在当前聊天已经确认同次起卦现场事实时，两个梅花人事入口可传`response_context`及非空label、严格布尔`same_casting_episode_confirmed=true`，读`situational`字段卡。`querent_position`是来占者所在方位与参照，不借端法对象方向、行进或住址补齐；`weather/setting/human`是原文有限类别，不自动识别或猜年龄。风雨雷晴为当时实况，不是未来天气。雨与雪均配坎，但坎体宜雨只明确雨：已知雨用rain、已知雪用snow、确实未分用rain_or_snow；雪无原句精确偏好，未分者保留待定。matches_actual_body只检查体卦，完整条款读clause_applies_to_reported_conditions，不把null当false或把雪说成不利。竹林震巽、五金乾兑、土瓦坤艮都保留两卦；笑语／哭泣只列原文象，不配卦或投票抵消。逐项读本候选原体与实际五行关系；影印“體見雷”与转录“火見雷”分列，主语未裁定，不能强改生克为比和。未知现场资料省略，未给对象时旧输出保持原样；已给但类别未齐保持待定。完整静室无所闻见与已报现场事实冲突，已闻笑语与nothing_heard=true冲突，不从单一未知知觉推断其他冲突。天气占分支拒绝此人事层，不合成完整十应、现实成败、概率或日期，不追溯排除旧预测样本。详见[十应现场条件](../../docs/meihua.md#同次现场的方应天时应地理应与人事应)。

## 其他盘局也要有可见依据

奇门先核 `ju_method/calendar_policy` 与原典范围，细读时[读取奇门证据分支](references/qimen-evidence.md)。奇门使用公开 `evidence_views.directional` 字段卡，六爻使用 `line_reading` 卡（它们的默认首轮已保留核心盘面）；卡只是首次请求的 `fields` 参考，不传 `view` 参数。详细读法如下，不以 snapshot 或 summary 替代已经存在的结构化事实。

| 本次要回答什么 | 实际读取 | 如何解释及保留范围 |
| --- | --- | --- |
| 奇门这一次的起局与核心宫 | `analysis_context/four_pillars`、`qimen.ju_text/dun_type/xun_head/kongwang/zhifu/zhishi/palaces` | 固定问时，先找值符／值使实际所在宫，再按已说明的所问角色读相关宫；不由宫名直接认定某个人的心意 |
| 奇门某方向或选项 | `qimen.palaces` 的门星神、`heaven_stems/earth_stems/hosted_stars/evidence` 及 `structure/patterns/rulesets` | 天禽和寄干须一起读；时旬空亡与日旬分开。九星旺衰以返回规则为准，不能套八字旺相口诀；只解释实际匹配的格局，不以单门排现实选项，不把九宫方位当房屋风水定宫 |
| 六爻本卦到变卦与起卦来源 | `input_normalized/nongli/current_hexagram/changed_hexagram/moving_lines`；需要核起卦方式时加 `cast` | 本变卦与动爻来自同一次结果；手摇、指定卦码、随机和时间梅花分别标明，不能把自动时间装卦说成用户摇卦 |
| 六爻装卦、世应和变化细读 | `lines` 的 `position/branch/element/liuqin/liushen/shi_ying`、动爻及 `changed_branch/changed_liuqin/is_fuyin_line`；`hexagram_info` | 按初爻至上爻核对位置，引用实际世应、六亲、六神与变支。动爻专属字段可能不存在，不能为静爻补变支；装卦已实现不等于自动完成取用神、月日旺衰、空破与精确应期判定 |
| 六爻反吟、伏吟 | `liuyao_evidence.fanfu` 及同次 `patterns` | 分开读底本明列的 `explicit_body_example`、内外卦 `regions` 和实际 `moving_line_relations`。`changed_chart_branches` 包含静爻位置时仅作卦盘结构比较，不能添静爻变支或生克边；未变经卦不因支相同就算伏吟。乾变坤是所选底本的卦体明例，不能靠无支冲否定，也不外推完整错卦表。`outside_explicit_example_table` 表示未覆盖，不能说已排除卦体反吟；效力仍须用神旺衰与回头冲克，格局名称不直接等于吉凶、心理状态或确定迁移 |
| 六爻明确取用及条件细读 | `liuyao_evidence.conditional_analysis.focus/lines/interaction_edges` | `focus_line/focus_kinship/focus_kind` 是明确给定的取用前提，不能说成自动发现；`selected.location` 区分明爻、实际变爻、伏神、日月，同位原爻不能冒充变爻或伏神。明爻和实际变爻多现保留候选，不能跳过变爻先寻伏神。元忌仇与六亲分开；月令层不等于总旺衰，受合的作用边不当作已经生效，变爻只作用同位原动爻 |
| 六爻三合与飞伏 | `liuyao_evidence.conditional_analysis.three_harmony/hidden_conditions/classical_scan` | 三支静齐、两支待补与内初三外四六限定动变分别解释；不任意混搭本变，不把局五行生克方向直接作胜负。飞伏六项支持与五项阻碍不相减计票；读取 `hidden_conditions.reception` 区分伏神自身承受门槛与 `flying_generation` 来源资格；飞生条目的旧 `matched` 是关系记录，可用资格读 `qualified_matched/qualification_status`；飞神空破便于引拔不等于飞神已能生伏，门槛匹配也不等于最终出伏；`matched=null` 及 `adjudication` 保留未决，总旺衰未裁定不能说已出伏。同时读 `stage_knowledge/hidden_conditions.stage_conditions`：整表不完整不等于每个具体阶段问题都未知，已核戌墓也不等于真入墓；只让关联本次承受的缺项限制相应层。影印校勘仅限已列页，疑文与火表缺项须随结果保留 |
| 六爻元忌效力与通关候选 | `liuyao_evidence.conditional_analysis.routing_conditions/role_effects` 及同次 `interaction_edges` | 元神五项支持六项阻碍、忌神五项支持七项阻碍按原文逻辑分别解释，`matched=null` 不当作否定；月令层不能填成总旺衰。`successive_generation_candidate` 只是忌→元→用的候选路径，仍须审用神有气；元神受合时不能据同动解克。`direct_control_requires_yuan_routing_review` 保留克的方向并提示审接续相生，不可读成已经克害或已经通关。取用是变爻、日月时不能让其他原爻越位生克它们 |
| 六爻有根生扶与三墓 | `liuyao_evidence.conditional_analysis.classical_assessment.focus/lines/resolution_notes` | 生扶与受克并见或来源效力待审时保留未知，不按条数相减。只把已返回的明确分支读作有根生扶或休囚受克；这不是全局旺衰或成事裁定。三墓区分日墓、动墓、本位化墓，`month_tomb_relation` 另列；静爻不能冒充动墓，原爻不能冲破变爻墓。`is_true_tomb=false` 不等于全局吉，`null` 不等于不入墓。影印第53页“五”字异文保留，机制按同版第100、127页的明确定义，不增造五墓 |
| 六爻旬空与受阻来源 | `liuyao_evidence.conditional_analysis.void_conditions`，同次 `lines.outgoing_obstructions`、`interaction_edges` 与 `classical_assessment.*.strength.blocked_supports` | 先核原支是否在旬空，再读空／不空条件；原支与本位变支分别核对。不作真空不等于此刻可用，`permanent_void_status=not_adjudicated` 不能写成到底无用；条件 `status=unresolved` 不是假。季令真空标签不替代总旺衰，有气静爻与旺扶条件冲突时保留原章疑义及旬内旬外差别。回头克来源保留生克方向，但不能按普通可用生扶计入；飞伏、三合成员与元忌路径的来源受阻也必须保留。别的元神仍须分别审查，不能因一条受阻就全否定，也不能因同动就直接通关。影印“有气”及“明夷之小过”的校勘不覆盖旧转录；不代用户重摇来消除矛盾 |
| 六爻日级候选 | 同次 `liuyao_evidence.conditional_analysis.timing_candidates`、`calendar_conventions.cast_at` | 只有明确用爻才展开 `timing_days`；明爻与变爻规则分开，伏神及日月取用若返回规则未覆盖就不套明爻应期。三墓逢冲开也只是原局关系的日级候选，不等于真墓或事件已经应验。保留空候选及 `requires_month_reassessment`。窗口是传统条件匹配，23:00为干支日界，不是事件发生时刻或保证；不补分钟排名、成事概率 |
| 用户点名六合／六冲等结构 | 按实际合同加 `patterns/pattern_flags` | 只解释本次命中的结构及来源，空表不补“隐含”格局；不能由一个结构断成败 |

没有返回完整取用神、旺衰和应期规则时，直接说明该判断未自动覆盖；仍交付已有宫盘／装卦支持的传统解释，不把“没读到”说成“引擎没实现”，也不照别家教程替引擎补算。大六壬、金口、太乙及西式卜卦按实际字段或文本保留两三项关键事实，与解释分开。不要为展示“全面”把各家术语混成一套。

六爻的 `efficacy=not_adjudicated` 必须保留为未综合裁定，不能把旬空、墓绝或进退结构配对直接变为失效、凶事或即时进退。进退先读同次 `liuyao_evidence.conditional_analysis.lines[].progress_conditions.state/clauses`：`retreat_held_for_near_event` 是近事有扶而不退；待旺、待填与未决都不能写成当下进退。只有问题已明确远近时传 `event_horizon=near/long_term`，不从 `timing_days` 或模型自行猜测。原爻季节无扶不等于动爻向外无作用；本位比和也不独立证明有根。元忌条件的 `matched` 保留原始结构谓词，解释进退需同时读 `progress_atom_values/progress_adjusted_matched/progress_adjusted_status`，未知不能改成假，也不能把支持条件当成最终效力。原典与版本见 `source_revisions/textual_issues/rule_trace`；自由解读引用同次结果，不因重选用爻能得到更顺眼的解释就改用神或重摇。完整范围及疑文见[六爻深度审计](../../docs/liuyao-depth-audit.md)。

动静克制还须读同次 `liuyao_evidence.conditional_analysis.control_conditions`、`lines[].activity_condition_status` 与元忌层 `conditional_atom_values/conditional_matched/conditional_status`。休囚动爻仍可能克旺静爻；静爻不克已明确活动的爻，受动爻克的静爻向外克须先审解救，不能因卦中另有一爻发动就删除全部静克。`activity_prerequisites_unresolved` 表示原暗动候选的扶源未决，不能说已经暗动；`active_to_active_requires_arbitration` 不能擅判先克后克。`blocked_oppositions` 保留被排除的克制条件，方向存在不等于实际受伤；受伤静爻的克制受阻也不等于所有生扶永久归零。原始 `matched` 与进退调整字段仍供溯源，涉及克制和活动资格时以完整条件层及其未决状态交付，不计条数定输赢。

日冲另读同次 `liuyao_evidence.conditional_analysis.clash_conditions`：冲空填实、静爻日破、明动冲散与回头克分别解释。`day_void_fill_condition=true` 不删除原旬空支表，也不解除另有克制；`moving_scatter_condition=false` 只表示所列条件下不能因冲判散，不等于毫发无伤。同日比和又相冲而独立根气未明时，日破与活动资格保留未知；三合、伏神和墓的来源也不能据原暗动候选确认。衰动冲散待审不能补成必散或现实命中概率。以条件层为准，不用原始 `injured_relation` 的日冲提示覆盖综合核对。

向外生扶另读同次 `liuyao_evidence.conditional_analysis.generation_conditions`：`condition_match` 是生源资格，`target_reception_condition` 是受生爻当前空破无根门槛，`benefit_now` 是两者在所列条件下的合取，均不是现实成功判断。原爻得本位变爻回头生，可以保留其向外生扶条件，同时保留日月克制，不等于整体旺相无伤；变爻仍不能跨位直生他爻。受生爻旬空未填、月破待审或月破日克无独立根时，不以收到生扶就认定有效。原始元忌谓词保留，综合 `conditional_atom_values`、生扶边与伏神生源读取同次资格；静爻混合动卦的未覆盖分支不补为绝对不能生。

讨论某爻当前可用、月破值日或本位回头关系时，按[来源与目标分读](references/liuyao-source-target.md)同时说明与问题相关的来源资格、目标承受和具体作用；不能只说“有扶但全局未决”而漏掉已核资格或已核阻碍。长结果补读仍绑定原回执与完整payload散列，不按临时文件的新旧顺序猜本次结果。

本位回头生读取同次 `liuyao_evidence.conditional_analysis.back_generation_conditions`，强弱、生扶与克制共用其空破、冲空事实；`control_conditions` 的 `source_back_generation_condition/back_generation_source_path/source_rescue_used` 标明使用依据。回头生可支持日月反制下的克静条件，但不删除 `source_calendar_oppositions`，也不把 `source_calendar_supported=false` 解释为整体无力。`source_rescue_used=true` 不是全部解救或最终受伤判定，仍读本条 `condition_match/status`、原爻空破合绊及多动制化。暗动可借已匹配的实际回头生扶源，不能借静爻变盘同位支；变爻的日月关系保留，匹配门槛不等于变爻已全局无伤。

元忌接续相生读取同次 `liuyao_evidence.conditional_analysis.routing_conditions`：原始 `role_effects.chains[].status` 只保留结构路径，实际逐段资格见 `route_condition_match/route_status/route_source_path` 及对应 `conditions`。回头克、合绊或用神无根使当前路径未通过时，不再说只是泛泛“相生候选”；某一链不通过也不能否定另一条已匹配的路径。`routing_conditions.focus.condition_match=true` 仅为所列路径门槛匹配，不代表直接克制已消失；读作用边的 `qualified_routing_condition/status` 时仍保留原控制方向和条件。伏神承受未裁定就保留未知，不能借飞神的同位承受条件。新校勘更新见该层 `textual_issues[].resolution_update`，不因旧转录仍保留就忽略原典差异。

## 交付给用户的判断辅助

金逢巳日读取同次`liuyao_evidence.conditional_analysis.growth_conditions`。`position_match`只是长生帝旺位置，`condition_match`才是本条资格；已核月令生扶可按此条件论长生，但不能删除月合、回头克、旬空或其他反制。原始火克金的五行关系仍保留，`day_control_in_calendar_oppositions=false`只说明该作用层在指定原典条件下没有同时把同一个巳日列作日克反制。无月扶而其他来源未审时保持未知，不凭“长生”二字作得生。角色支持采用`conditional_matched/conditional_atom_values`，月令事实沿`month_support_fact_paths`复核。[原典及修复范围](../../docs/liuyao-growth-audit.md)保持明确。

土逢巳读取同次`liuyao_evidence.conditional_analysis.cessation_conditions`：`position_match`只是绝位，`condition_match=false`可表示已核独立生扶下本项论生不论绝，不能解释成全部无害；未知不补成真绝。保留另有回头克和变爻月破，角色条款采用`conditional_matched/conditional_atom_values`，旧原始匹配只供回溯。独立支持及其多段依赖以`support_fact_path`核对，不能用被判断的巳支或无外部根的相生循环证明其自身已生土。化散未裁定时，综合`changed_adverse`仍可未知。[原典及资格范围](../../docs/liuyao-cessation-audit.md)保持明确。

巳寅申读取同次`liuyao_evidence.conditional_analysis.penalty_conditions`：`condition_match`仅指所列作用范围内三支齐备，`effect_condition_match=null`保留刑的总作用未裁定，不能据此断刑害或凶事。巳爻在寅日的`growth_conditions.condition_match=false`表示本条不再按该日长生、生扶计入，原木生火关系与长生位置仍在；申暗动资格未知时，本项也未知。别爻变支和静爻变盘支不借来补齐，伏神另读自身`reception.penalty`，不借飞神本位变支。`yin_generation_allowed`按第98页特定条款先于第10章一般回头生许可：三支齐备时，所列寅月、寅日、动寅及本位变寅不计为巳爻寅生扶；活动未定时资格未知。`back_generation_conditions.sources`的`raw_condition_match`保留一般空破门槛，`condition_match`才是综合资格，不能见原始木生火就复写为回头生已经许可。`generation_conditions.generations`的`condition_match`描述来源，`target_yin_generation_allowed`与`benefit_now`描述该目标，不能把只对巳爻的排除推广为寅爻对所有目标均失效。其他独立生扶与反制照实保留。[原典与修复范围](../../docs/liuyao-penalty-audit.md)保持明确。

先回答这次传统参考最值得留意什么，随即展示真实卦变或盘局依据，通常 200–300 字。一项支持推进的提示与一项需要留意的条件只有返回确实包含时才写；结果混合就把混合说清，不强迫落成“会／不会”。

现实建议围绕用户已给的选项：下一步最值得确认的条件、低成本试验或何时复盘。比如用户问项目试点，只有他们确有该选项时才谈范围、资源与验收条件；不能说卦已经算出客户会答应。要比较多个现实选项时，可按「选项／已知条件／尚待验证／可逆下一步」做一张小表，明确这部分是现实决策整理，不是卦象计算排名。

不读他人内心，不预告疾病、灾祸或具体财务结果。生死、临床判断和医疗择时请求在调用前停止；法律和重大财务事项的行动以事实及专业判断为依据，决定由用户自己作。边界在相关处说明一次，不用长篇免责声明挤掉卦义。

六爻的 `fields` 必须写完整路径，表格中 `/` 分隔的子项不能当成单个路径。三合细读可用 `fields=["liuyao_evidence.conditional_analysis.three_harmony","liuyao_evidence.calendar_conventions"]`，配合 `strict_fields=true`、`include_snapshot_text=false`。`conditional_analysis.three_harmony` 或顶层 `calendar_conventions` 都不是合法路径。保持默认响应预算，让超长回复进入 `result_delivery`；不要用 `response_char_limit=0` 把长回复交给宿主截断。一次成功回复已经包含所需事实时，直接使用该回复；补读已有 `result_delivery` 的字段或分页使用原 `result_id`，不能为了换 `fields` 重新调用 `sixyao`，即使沿用了 `trace_id/parent_run_id`，它仍是另一次计算。

首轮被裁掉的字段不能靠分页恢复。已有 `result_delivery` 时读同 run 的所需字段／分页；用户要求完整 JSON 或完整文件时，首次 `fields=null`、保留默认响应预算，核对业务 payload 的 SHA-256，不另起一卦补交付。

## 可复核示例

仅需要本地 CLI 复核时使用；已有 MCP 定义直接调用。 [读取本分支](references/examples.md)。

求名另读 `topic_reading.chapter_qualifications`，逐候选核对自身原体、生体与克体角色及实际路径。`reputation_context` 仅声明用户已确认的原文“在任”与“職任之處”条件，未知省略或 null；已就业、考试、问句和 label 不能自动补成条件。只列所选原文時序，不把数字、年月日時换成具体日期。方道明示采用变用经卦读法，尚未唯一裁定；巽方道作“東”，同本地理与固定转录作“東南”，震時序“春二月／春三月”、乾“五金／一四九”等保留差异。内卦无克体不等于完整内外无克体，在任句是史料条件，不据此作处分或灾祸判断，也不推实际任所或概率。详见[求名补充](../../docs/meihua.md#求名占的在任条件与原文时序方道)。


行人题篇的技法核对显式用 `interpretation_topic=traveler`，读 `topic` / `topic_audit` 的 `interpretation.topic_reading.chapter_qualifications`。返归条款保留原体；在外补充另以各候选初用为受生受克对象，核对 `initial_use_frame.actors` 及各自事实路径。体生用可以表示初用受原体之生，用生体不能改写为用受生。逢衰受克要求初用月令衰与实际受克同时成立，缺项和原文未定保持未知，内卦无记录不证明完整内外没有。震多艮多门槛、完整角色范围及影印盈旺等用字未裁定；坎兑只列明初用读法。保留并存作用及受制，不投票生成结局，不补归期、行踪、安全、灾祸或实际返归核实。计算前仍核硬边界。详见[行人占参照](../../docs/meihua.md#行人占的原体与初用参照)。


端法名义应期数读取已有 `motion` 字段卡的 `interpretation.motion_context.postheaven_count_reference`：仅 `observed_trigrams` / `observed_categories` 且占者 `observer_activity` 明确时适用。用上、下卦先天序数与原时支数的未除六总数，行取半、坐加倍、立用原数；不得拿动爻余数、约化时数或物象主体活动替代。名义数不是已确定时长，分数不取整；时间单位、起算点、具体日期、完整变通和现实窗口未定。影印二花／转录二日花不产生两日期限，不从问题词语选例外；未知占者活动不猜，时间起卦和现成卦不借用此式。详见[端法总数](../../docs/meihua.md#端法总数与占者活动的名义比例)。


求名／求财已有日支时，用 `topic` / `topic_audit` 读取 `topic_reading.qi_day_timing_reference` 与 `interpretation.day_qi`。按原章句实际生体／克体角色核明列日支，各取数候选沿用自身角色；在任条件为假或未知、完整内外无克体未认证时，照实交付。坤辰戌丑未月不能当成日支，其明列日支原子为未／申；旺衰、其他月份、数字、五行及日干谓词不代入。原子相符不等于应验，不符不否定全部未解析条文。23时午夜与子初候选均保留，不挑相符者充作预测；已报日支不独立认证为真实日期，不补最近匹配日或现实窗口。详见[卦气明列日支](../../docs/meihua.md#章句卦气的明列日支核对)。


求名／求财用 `topic` / `topic_audit` 父字段读 `qi_branch_timing_reference`；逐单位解释实际年、月、日、时支标签，各候选读自己的 `topic_clause`。年时沿用原seed，节月与名义农历月序标签分列；后者只作月序映射，闰标记及完整月界未裁定。23时换日备选不改原年支，未知不补，不挑更相符的标签拼成预测。坤辰戌丑未只另属月、未申见于四单位；单项不符不否定全部未解析时序，相符不证明应验，不补日期、成功率或现实窗口。原日支层保持，详见[四单位标签](../../docs/meihua.md#年月日时的明列支标签)。


### 家宅与屋舍题篇及候选摘要

用户明确选择家宅或屋舍占时，分别用`interpretation_topic=household/dwelling`，沿用本次实际资料或已有卦，不因问句关键词重起或自动选篇。读取`topic/topic_audit`父字段。家宅影印比利与转录比和未裁定：`source_relation_condition=null`时不能因五行相同就套家宅安稳句。屋舍保留冷退/衰退异文，不默改底本。`chapter_qualifications.household_support_reference`只列本候选四个内卦辅助角色中的实际生体；所列范围未见不等于完整内外无生，完整跨章净判断未计算。历史多凶、失盗、冷退等字句不作现实灾祸、盗窃、住宅安全或财务断言；这两个题篇不是现场风水评估或选房迁居许可。

全部人事题篇的计数候选按自己的`topic_clause`解释，`traditional_judgement`须保留本候选题篇、引句及限定。一般`traditional_stage_readings`只作其来源范围的阶段参照，不替代题篇初始条款；实际动爻经文、受制、旺衰和后续层仍逐候选核对。原页、条件和验收边界见核对记录（本地数据：`../../docs/validation/meihua-households-candidate-fidelity-review.md`）。


### 婚姻章的两家参照

用户明确选梅花婚姻占时，用`interpretation_topic=marriage`，沿用已确认资料或已有卦，读取`topic/topic_audit`父字段。按每个候选自己的原体、初用和章句解释；`chapter_qualifications.family_frame`依原文所占之家／所婚之家，不默认男方女方。两条`strength_clauses`分别读实际角色的旺气条件，`null`不改成衰或不符。首段比和与后段比利分开，后者不能借转录比和自动套“良配无疑”。生体、体生补充只列关系成分，保留“或”及未裁定角色范围，不推求婚意愿、婚财或嫁奁。八卦相貌品行词只作历史文本，不给现实人物贴特征或道德标签；没有由该层核定的同意、婚姻成败、概率或日期。详见[婚姻章参照](../../docs/meihua.md#婚姻章的两家角色旺气与比利异文)。


### 饮食章的酒食象与制约

用户明确选梅花饮食占时，用`interpretation_topic=dining`，沿用已确认资料或已有卦，读`topic/topic_audit`父字段。逐候选读取`chapter_qualifications.symbols`的原始出现、直接制约、制约者自身受制及实际路径，不只见坎兑就说实际有酒有食。列明的坤艮制坎、离制兑不需“多”阈值，不因季令衰或制约者再受制自动删除；完整内外净作用未计算。影印“生身”与转录“生体”分列，未裁定的目标和组合不补成原体生助。原文转引和两侧互卦不等于已知菜单或席上人物；该层没有核定实际餐食供应、饮酒指令、营养或临床建议、概率或日期。详见[饮食章参照](../../docs/meihua.md#饮食章的酒食象与直接制约)。
