# 紫微本命与动态结果的证据读取

先按本轮主题和[共享时间选择](timing-selection.md)取证。本页约束的是对象身份和计算连接，不另造事业评分器；有已返回连接时直接解释，不为同一连接重复排本命。

## 三种宫位身份

| 实际数据 | 对象身份与能回答的部分 | 不能改称 |
| --- | --- | --- |
| `ziwei_birth.palaces` 每项 `name/ganzhi/stars_detail`；命身另看 `ming_gong/shen_gong` | 本命十二宫；`stars_detail.name/brightness/mutagen` 是本命星、亮度与本命四化 | 目标年份的流年官禄／财帛等功能宫 |
| `ziwei_horoscope.scopes` 的 `scope/scope_palace_role/natal_palace_name/branch/palace_ganzhi` | `scope_palace_role=ming_palace_activity_index` 时，是该运限命宫活动索引所临的本命宫；旧 `palace_name` 是兼容名 | 该运限同名功能宫；如所临本命迁移宫不等于已完整审查流年迁移宫 |
| `scopes[].palace_map` 的 `scope_palace_name/branch/natal_palace_name/natal_palace_ganzhi` | 引擎计算的该层十二宫功能名映射；`natal_stars_detail` 仍是本命星位 | 全部流曜、飞宫四化或某流派完整动态盘；旧部署缺此表时不能手补为引擎结果 |

普通动态首轮取实际合同的 `analysis_context`、`birth_context`、`ziwei_horoscope.ruleset/interpretation_scope/nominal_age/calendar_rules/scopes`。`scopes` 数组整体取回，再按 `scope` 选本次需要的大限、流年等层；不编 `scopes.流年` 或数字索引投影。核对 `analysis_context.context_role=target`、`analysis_datetime` 及其时区；`birth_context` 用于出生处理核对。旧部署若仍把出生日期放在 `analysis_context`，不能将出生日期冒充目标回执；按实际可核验目标范围说明，不把缺回显解释成整张盘无用。

上述 `birth_context` 是动态接口新增字段；本命 `ziwei_birth` 的出生回执仍是 `analysis_context/person_info`，不能因两工具资料相似而复制投影路径。

本命首轮使用实际合同发布的 `evidence_views.natal`。`reading_view.palaces` 保留全部本命星曜，`stars[].name/brightness/mutagen` 与完整 `palaces[].stars_detail` 对应；`null_star_fields_omitted` 声明缺少的亮度／四化属性等于完整字段的 `null`，不能补造。`major_stars=[]` 只代表没有十四主星，继续读取同宫 `stars`。`sanfang_sizheng_branches` 按 `sanfang_branch_order` 与同一视图十二宫关联，不在首轮复制四遍星曜。结构问题需要展开时用 `structure` 视图，查规则步骤用 `rules` 视图；用户要完整结果时仍首次 `fields=null`。

## 四化连接先认星，再认宫

当前每层 `mutagen` 是该层天干的四化星名；`mutagen_natal_links` 每项明确 `transformation/star/natal_palace_name/natal_palace_ganzhi/natal_branch/natal_star_label/natal_star_brightness/natal_mutagen`。新版连接另含 `scope_palace_name`，明确该星位在本层的功能宫；与该层 `palace_map` 核对，不能把 `natal_palace_name` 当成同名功能宫。这是动态标记连接本命星的落宫，优先使用引擎给出的连接，不重复调用本命。解释需要更多本命配合而已有本命盘时，再复用 `palaces[].stars_detail`；没有连接的旧部署可按实际星名核对已保留本命表，不能猜落宫。

- 示例读法：本命官禄有天机，目标流年 `mutagen.化科=天机` 且对应连接落本命官禄，可以说“该流年化科标记关联到本命官禄中的天机”。这不等于“流年官禄宫化科”。
- 本命 `natal_mutagen` 与流年 `transformation` 分开，不能把年度四化永久写入本命。某星没有连接时说明这一项未连接，不能假定另一个宫位。
- “化科便晋升”“化忌便不得转职”不是这些字段的结论。星曜、亮度、四化及相关宫位的传统含义需另有可靠作者／规则来源；有来源时可给与所问相关的条件式解释，未核对时保留为计算连接，不冒充已核实原典。

## 专题解释与新增价值

事业方向可读实际本命官禄、命身相关星曜配置；目标年度则说明大限背景、该年标记关联哪些已确认本命对象。来源查询可使用 `knowledge_registry/knowledge_read` 或已核验作者文本，记录作者、版本、章节／页码及适用范围。排盘与外部软件一致，只核验所选口径下的计算；它不是星性、现代职业类比或现实预测有效性的出处。

用户明确要求原典版本与页码的审查中，在线转录的卷／章节定位不能冒充书影页码；未核到所选版本和页码的解释只列作未验参考，不作为已验收的传统主证。也不能从单星象意补出未查证的“运限四化连接本命宫后如何断事”组合规则。此时仍交付计算连接、已核实的其他依据和独立现实建议，不靠增加调用填补来源缺口。

把“返回事实”“来源解释”“现实建议”分开：例如先给出年度四化关联本命官禄的事实，只有查到相应解释规则后才讨论它怎样联系本次工作任务；面试材料、岗位授权、薪资和交接计划作为独立现实条件。没有相关解释来源时，不用别的主题象意或笼统吉凶填空，仍可交付已有八字／其他有据视角。

第二方法应补充原先没有的主题结构、时段条件或真实分歧；相同出生数据共享历法输入，不能当作独立统计印证。删除紫微会丢掉一个新字段，只能证明信息增量；咨询增益还要看它是否改善本次判断及表达。

## 规则配置与结构依据

首轮保留 `ziwei_birth.ruleset` 或 `ziwei_horoscope.ruleset`。默认 `iztro_2_5_8` 是软件兼容口径；`quanshu_v2_excerpt` 1.3.2 选择闰月、壬年四化、亮度表、长生方向、旬空双支、部分年度流曜，并采用邻宫起大限及火铃年支定点读法，余项仍有软件回退，不能称全书认证。与 1.2.0 相比，摘录配置的十二宫大限年龄区间及火铃位置会变化；不能只换版本名继续引用旧值。该闰月条文只覆盖本命安身命；目标流月闰月仍保留软件半月规则。动态层复用所选四化表为软件约定。配置不同要先解释真实差异，不挑更符合叙事的盘。目标时间可显式传 `target_minute/target_timezone`，与出生时区独立；分钟输入不构成分钟级预测。

本命 `palaces[].structural_evidence` 提供十四主星名单、是否无主星及本宫／两三合宫／对宫的实际星位。空宫只表示没有十四主星，不等于没有任何星；对宫星没有搬入本宫。三方四正是盘面关系，不自动认证古典成格、吉凶或现实结果。性别未知仍可读本命非运限结构，大限范围留空，不把未知当女命排运。

本命新增 `chart_masters` 与 `calendar_cycles`，命主按命宫支、身主按生年支；不要把命主／身主当成命宫／身宫所在的主星。十二长生和博士十二神分层读取，未知性别留空，循环名称不作临床或寿命判断。所选亮度表与同卷散文有分歧；身主转录火玲、明刊火鈴仍不足以裁定单取哪颗，保留显式软件约定，不按咨询叙事挑选规则。

摘录配置自 1.2.0 起的旬空显示两支，因此 `reading_view` 是 66 种星名、67 条星曜落点；软件配置为 66 条，不把条数当新增星种。`voids` 视图的 `source_name_mapping` 说明古天空对应今地空、原文本生年解神对应年解，不能拿软件另列的同名星替代。

摘录配置的流年 `flowing_stars` 返回禄羊陀及天德、月德、丧门、吊客、白虎、官府，共九项；软件配置仍为三项。结合 `scope_palace_name/natal_palace_name/system_id`，不当成已计算全部流曜，也不搬移本命星。流年月德按目标年支，不以本命月德替代；年度官府不等于博士官府。`annual_three_sha` 只给原文明示三支集合，逐名位置为空时不把奏书、将军、直符依顺序配宫，也不从博士同名标记补齐。

原文属性读取 `symbolism` 视图：`symbolic_properties.records` 把引句、原字五行与实际本命星位连接。化财、化印、化善、遇帝为权等文字不是禄权科忌赋值，也不直接认证人格或现实事件；以 `natal_mutagen` 为实际本命四化。天同水金、七杀火金、贪狼水木保持 `elements_as_written`，不擅自裁为软件常用单一五行。16 条属性不是全书象意或所有组合断语，实际支持范围与部分明刊书影核对分开说明。

指定刻本的四化追问用 `evidence_views.editions`：`ziwei_rules.rule_catalogue.sihua_source_comparison` 比较全表，本命 `sihua_source_comparison` 只连接当前年干的异文。明刊卷三庚年刻“日武同相”，`sihua_source=rule_profile`时两基础配置仍取太阴化科、天同化忌；`compared_position` 指向实际存在的本命星，其 `natal_mutagen` 仍是当前盘的真实值，不能说当前天相已化忌。壬年比较随配置改变，摘录配置天府化科与该刊本相合，软件配置左辅化科则有差异。`compared_assignments_applied=false` 不能解释为已经切换成明刊整盘；同一年干相合不认证全书。

核查安紫微原典时读 `evidence_views.rules` 的 `rule_trace`：`ziwei_tianfu_placement.outputs.source_comparison` 比较实际紫微位置与所列明刊资料，仅在已知五行局和农历日的前提下有效。`source_kind=prose_derived_with_unresolved_grid_label` 表示据原文规则推导，不能说直接辨清了图中字形。木三局十一日缺列、十二日辰巳两处冲突时，`expected_ziwei_branch` 与 `matches_source_record` 均为 `null`；这表示刊本文字不能给出唯一核对值，实际星位仍由所选计算配置返回，不是紫微未算、宫中无星或整盘失败。候选里包含实际星位也不能据此宣布原典符合。原文图表、推导、未决项与当前星位分别说明。

前置链另看 `wuhu_dun_nayin_ju.outputs.source_comparison`：`expected` 依明刊卷三安身命、五虎遁与纳音元素推导，`actual` 是当前配置实算。默认配置闰月上半月与该刊本不同；`compared_rules_applied=false` 时不得把来源比较值说成当前命宫或五行局。`matches_source_chain` 只比较已输入农历月、时支、年干之后的命身宫、十二宫序、宫干及纳音元素／局数，不认证公历换算、时支确定、纳音全名、其他月系星曜或整书。宫名采用明确列出的现代对应名，比较时忽略“宫”后缀；不能说原书使用了相同的现代名称。纳音内部字形未定时，末字元素仍可单独核对，但不能宣布完整词形已校勘。

逐颗辅星来源用 `evidence_views.auxiliary_sources`：`auxiliary_placement_sources.placements` 的 `actual_branch/calculation_path` 连接当前实算星位，`expected_branch/matches_source_rule` 只比较所列明刊条文。正常月的十六颗辅星有完整方向规则；闰月的左辅、右弼、天刑、天姚、三台、八座比较值为空，因为安身命条文不认证这些月系规则。火铃条文仅列四组二支，没有明确生时指令，即使子时恰与二支相合也保留裸条文比较值为空；默认配置仍按生时双顺，摘录配置自 1.3.0 起采用年支定点读法。`unchecked_star_names` 表示本批未校核其安星规则，不表示星不存在、算错或不值得解释。原文天空在本批对应今地空，不能拿软件另列的天空替代；来源比较不改动实际盘面，也不认证星性、组合断语或现实预测。

运限的 `evidence_views.source_rules` 返回 `ziwei_horoscope.source_comparison`。大限分别给明文首宫和当前首宫，默认命宫起与明文邻宫起不同，摘录配置才按邻宫起；岁数比较以给定五行局起岁为前提。童限替代记录不能说成已验证正式大限。小限只核对给定岁序后的顺逆和落支；现代农历岁首计虚岁仍是单独约定。斗君仅在普通生月核对，出生闰月的期待值留空，不能把斗君吻合扩成全部流月、流日、流时和动态四化符合。火铃的 `positions_under_selected_reading` 是明确选择的年支定点读法，现代作者自序只作读法存在的补证，不能据此宣称已取得明刊唯一历史解释或借用作者自述准确率。

历法依据使用 `evidence_views.calendar` 的 `calendar_basis`：`placement_lunar_date` 才是当前盘的排盘农历；`civil_date_lunar_date` 是输入钟表日期查表结果；`reference_lunar_date` 是同一实际时刻转固定 UTC+08 后的日期查表结果。先看摘要的 `lunar_date_basis/calendar_date_shift_days`，跨日再展开，不将三个值混写。现行外国民用日期采用既有日期表，未按当地时区重算朔日；节气仍用物理时刻。原典时钟选择未认证。春节附近出生太阳日期与目标钟表日期混用可使现有岁序小于1，该边界明确未支持；不能解读为实际早于出生，也不能自行补成虚岁1或改出生年。

童限专题使用 `evidence_views.childhood` 的 `childhood_limit`：明刊卷三安童限诀明示一至六岁之命、财、疾厄、妻、福、官禄，现对应现代宫名并连接该宫真实本命星曜。它与正式大限分列；`scopes` 的大限在起岁前标记 `status=not_started`，宫位、宫干和四化为空，不用童限替代。不能把童限给定岁序落宫说成正式大限或第七层动态四化。`natal_stars_detail.mutagen` 仍是本命四化，`childhood_sihua_supported=false`；当前软件岁首的年龄计算尚未获原典认证。七岁以后本批未得唯一规则时，`status=unresolved_from_source`、宫位为空，仅限制该童限规则，不否定六层运限或本命星曜；也不能把“十五命宫看端的”自行补成完整七至十五岁排法。

循环专题使用 `evidence_views.cycle_sources` 的 `cycle_source_comparison`：`positions.changsheng/positions.boshi` 各按地支返回当前 `actual`、明刊 `candidates` 及 `match`。性别已知时按各自条文核对顺逆；默认软件长生在阴年与明刊男顺女逆不同，不能凭起点和对宫相同就称整套相合。性别未知时，起点及对宫在两方向下标签相同，所以每套循环保留两个可确定值，其余十宫仍未定；候选两项不是同时存在两个标记。`direction_match=null` 表示顺逆尚不能核定，不是否定整盘。长生“病”等仅是传统阶段名，不能作临床状态。明刊博士为蜚廉、大耗、官府；博士层蜚廉对应当前飞廉，与年支蜚廉分层，不能把旧转录天耗／宫府当明刊原字。未知性别的大限仍留空。

校时精度专题使用 `evidence_views.time_input`，读取本命 `calendar_basis.time_input`，运限则读取 `calendar_basis.birth.time_input`；首轮 `analysis_context.time_input_status` 或出生上下文先保留简短状态。`solar_unavailable` 表示请求校正但缺经度而降级；`civil_clock_selected` 表示选用钟表时间；`timezone_assumed` 表示默认时区或经度邻近整数UTC偏移的假设；`province_longitude` 表示仅用省级代表经度。其他状态的假设也须核对 `timezone_assumed/advisories`，不能只凭一个状态判定准确。没有应用校正时，分量为 `null` 表示未评估，不能解读为均时差或夏令时为零；实际施加总修正为零是另一事实。程序导出的秒数不证明出生记录精确到秒，省级经度的误差界未量化，固定偏移不确认当地历史夏令时。`timezone_rules` 记录本次所用数据库和指纹，不认证用户出生点或古典时钟口径；对局限作说明后仍解释实际计算结果。

`minute_sensitivity` 比较给定钟表分钟内秒0与59.999999两个假设端点；真太阳时模式在后一实际时刻重新计算修正，基准命盘仍用秒0。首轮 `time_input_minute_sensitive=true` 表示端点跨了时支或排盘日期，按需读取端点结果，先说明基准再解释实际命盘。它不猜出生秒数，不把端点当两份真实出生资料，不覆盖四舍五入、记录误差等所有可能时间；也不把样本的天文残差当全局误差界。午夜附近可能保持同为子时却跨农历日期或年，不能只检查时支是否变化。真实太阳时端点的天文学比较不认证古典排盘应采用哪个时钟或哪个日期。

明刊星义专题用 `evidence_views.contextual_symbolism` 先核条件，或 `ming_symbolism` 读取 `ming_textual_properties` 的完整定义与计算连接；较长完整视图需沿同run `result_delivery` 取齐。旧 `symbolic_properties` 仍是固定在线转录，不把它冒充明刊整段原文。明刊保留七杀“將星”、文昌“文魁之宿”、天梁“化陰”，不覆盖旧转录降／首／荫。`occurrences.kind` 区分本命星、实际本命四化与博士循环标记；四化属性的五行不改被化星原属性、五行局或亮度。古天空只连接本系统地空，博士飞廉不连接年支蜚廉；病符、官府本条未写五行时保持空，不从另条官符火补值。未配层的歲君、丧门、吊客、白虎、官符只是本批定义尚未映射，不否定已计算的年度层。

核对起紫微日表时，读取本命`rule_trace`中`ziwei_tianfu_placement.outputs.source_comparison`。`matches_source_record`只比较最初选定转录，不能称已校定原图；同处`independent_review`另列更正后的隔离复读。水二局二十一、木三局十一、火六局初六没有唯一直接标签，木三局十二有两处直接宫位；火六局初八有未位直接读法，但寅位仍有疑读候选。`matches_unique_direct_branch=null`是未能形成唯一直接比较，不是不匹配；`unambiguous_after_rereading=false`的疑义不能由当前计算落宫来裁定。146项唯一直接读法也不等于整表150项全过，新复读不是新版本或外部人工专家认证。原转录与首次失败都保留，不据疑字改星位。

廉贞“在官禄”按实际本命官禄宫核查；“在身命”采用命或身的明示读法，两个条件可重合，原文角色不改实际宫名或断言现实结果。七杀“遇帝”的几何本段未定，虽显示实际同宫／三合／对宫，`condition_match`仍为`null`，不能自选“遇”的范围或把“为权”补成实际化权。化禄喜见禄存等三条也保留未裁定条件。原文十八正曜与逐名十九个现代名的差异、将军条尾字候选与单次手读限制均保留；不把星义中的寿、病、孤等字当作寿命、临床状态或现实结局。

大限起止专题可用 `evidence_views.decade_activation` 核对 `source_comparison.daxian.formal_scope_status`、`first_age` 和 `actual_branch`，完整六层记录按需读同run `scopes`。默认1.1.2、摘录1.3.2起，未到所选局数起岁时 `status=not_started`、`mutagen=null`、`palace_map=[]`、`mutagen_natal_links=[]`；这些是该层未生成，不能改述为无化忌、化忌为零、命宫大限或童限四化。其他五层依实际返回解释；童限六个明文岁序仍可独立连接本命星曜。`is_childhood_limit=false`不表示大限已经开始，须读取status；所采用的岁首仍未获原典认证。

明确指定明刊四化表时，在本命、运限和规则查询一致传`sihua_source=naj_ming_v1`；省略沿用基础配置，不因读到异文而偷偷换表。组合`ruleset.version`含`+sihua.naj-ming-v1`，`sihua_source_url`专指四化原页，`classical_source`仍属于基础配置。显式选择后庚干实际为太阳禄、武曲权、天同科、天相忌，壬干为天梁禄、紫微权、天府科、武曲忌；以实际`stars_detail.mutagen`和`mutagen_natal_links`解释，不保留旧天同化忌或再给太阴补科。`compared_assignments_applied=true`仅说明此表被显式采用，不表示整书、时钟、亮度或运限复用获原典认证。文字天相化印仍是传统象义，不新增化印赋值。来源专题可用`sihua_source`视图核对，较长完整结果继续读取同run交付物。

出生钟时处于夏令时重复区间且用户有明确偏移记录时，可传`birth_utc_offset`（两出生工具），运限目标可另传`target_utc_offset`；格式`±HH:MM`或含历史秒数的`±HH:MM:SS`。偏移只核对已解析的命名时区并选定物理瞬间，不应把`birth_timezone`改成固定偏移而丢失当地历史规则。未给仍拒绝歧义，错误偏移或春季不存在钟时仍拒绝。`calendar_basis.civil_clock`列出实际偏移、fold、UTC瞬间及运行时区数据指纹；首轮上下文的`civil_instant_utc`与`civil_utc_offset`保留区分。运限分别读出生和目标回执，实际先后按UTC瞬间，不能把回拨后的较小钟面当成出生前。真太阳时标签继续只作排盘标签，不附会成第二个民用瞬间。此选择不认证出生记录、古典时钟政策或既有混合时钟岁序。

明刊结构条件专题可用`evidence_views.classical_conditions`读取`ming_structural_conditions.index`。当前五条核对紫府同宫守命及甲干、紫微辅弼同宫、紫府／魁钺／左右夹命。`geometry_match`只报告实际星位几何；`evaluated_necessary_premises_match`只合并本批已经核对的几何、落支和年干前提，不能说原文全部条件已满足。`source_literal_example_matches`仅比较所录两个具体宫位例，旋转或反向的一般双邻宫读法与原例匹配不同。缺少或重复星对象为`null`，不能说无该组合；某个已知必要前提为false则可说明此项不符，不因此推断现实不利。

需要完整条文、原注、未裁定条件和每个实际星对象的`calculation_path`时，首次选`evidence_views.classical_condition_details`的fields，较长结果沿该run的`result_delivery`取齐。完整原始JSON首次`fields=null`。索引视图没有请求records，不能从该索引run回补未投影字段，也不应以分页补充回执的可读性冒充全文已被保存。无杀凑、月份例注及三方替代条件未完成完整裁定，`full_traditional_judgment=null`，`source_outcome_claim_adopted=false`；即使几何符合，也不能据“贵格”“奇格”推成财富、地位、性格或职业事实。结构条文1.1.0按两份隔离原图复读把左右夹命小注更正为“九月十一月”；“加吉方论”归紧邻“魁钺命身多折桂”，不再并入魁钺夹命。月份例注未变成通用安星条件。紫微辅弼的财帛小注两份新读不同，`source_annotation=null`表示未裁定唯一转录；通过`annotation_revision.prior_annotation/reader_annotations`分别说明旧读和新分歧，不能把null说成原书无注，也不能擅自给它加财帛或官禄宫判据。`source_revision`给出此次来源指纹、两位隔离模型读者及零新增见证／零外部人工专家；它不是整书或版本独立互证。此视图不改安星、四化、命身宫名或其他条件读法，不认证整个章节、原典时钟或现实预测。

明刊运限分段专题首次按需展开`evidence_views.limit_subperiods`或`limit_subperiod_details`的fields，读取`ming_limit_subperiods`。上/下五年依已选虚岁和实际大限十岁区间，不用年龄末位取余；起限前仍为not_started，不据此认证古典岁首。分类保留原文北斗、南斗、南北斗双属以及擎陀火铃，不从为福邻句筛吉星；六个双属名不选唯一五年段，未标属的星不自动补类。`natal_star_groups`的路径连接同次scopes.1.palace_map中的真实本命星，这个容器不代表该星参与小限应验。相关几何未定，`selected_as_relevant_star=null`；小限半年起止未定，不补公历7月1日或农历七月，`half/half_start/half_end`仍null。`full_traditional_judgment=null`，不把分段或原文应字改述为已经验证的事件。完整明细须首次请求，摘要run不能回补未投影字段；单次助手目读不等于独立专家、第二模型、整书或现实效果验收。


日期来源专题首次选`evidence_views.calendar_sources`的fields，读取`calendar_basis.date_conversion_provenance`。`lookups`分别指实际排盘、钟表和UTC+08参考日期；不能把一条日期的provider移给另一条。1900年原始印刷参照是TAM全年表，最初30日实施使用PMO补表；1901—2100参照HKO，2100-02-09以后实施使用HKO补表。实施数据不是独立验证，两个出版机构也不是两次独立物理观测。源记录、出版者和范围按实际字段解释；未选来源或未换算的日期可为null，不补HKO。真太阳时跨年／跨表时三条来源可能不同。一般`calendar`视图保留时钟证据，来源账本在首次所选fields中单独请求；完整长结果沿同run取齐。`time_input/civil_clock=null`只说明该项未生成，不推成均时差、夏令时为0或已消除歧义。日期标签通过不认证原典校时；岁序默认已用出生民用时区统一两端，`legacy_mixed_clock`仍可显式回放旧混合规则。两者的原典岁首认证均未完成。

普通日期由`fatebridge_lunardate_adapter_v1`实施，不能改述成未经本系统处理的上游原表。`applied_year_info_correction`逐时钟记录实际农历年使用的登记值；公历1934年一月仍可能使用农历1933年修正，不凭公历年替换。编码来自实施登记，不是额外独立天文观测。
## 岁序时钟

`ziwei_horoscope`默认`nominal_age_basis=birth_civil_timezone`：把出生与目标的实际瞬间都转到出生民用时区，分别查该区日期的农历年，正月初一00:00换岁。先读`nominal_age_calendar`的两端年份、方法、参考时区和`difference_from_legacy`。本命安星及年干仍取已声明的出生排盘钟，流年／月／日／时仍取目标钟；跨时区时这些年标签可以不同，不能据计岁年份重写星位或阴阳顺逆。

`legacy_mixed_clock`显式回放旧算法，包含原有春节边界报错。默认修复不靠把0岁钳成1岁；春节前后应分别得到实际岁序。`boundary_source_evidence`仅说明明刊所选段落支持哪些给定岁序后的操作，不能把软件换岁约定说成原典已定、整书已认证或现实预测有效。


旧公式比较值不是另一份旧口径成功回执。读取legacy_mixed_clock_age时同时核对legacy_comparison_applied、legacy_comparison_is_separate_run和legacy_ordinal_status：默认比较未应用、未另运行；0值标为would_reject_below_one，显式旧口径会拒算。ordinal_at_least_one只核公式下限，不保证完整旧运行成功，不能把比较值0说成旧回执返回0岁。

原典比较同时出现`independent_review`与`targeted_rereading`时，两者是分阶段的读法记录。后者是五个输入的同一书影复读；若其`unique_source_confirmation_supported=false`，不得据旧`matches_source_record=true`或R22的唯一直接标签匹配，声称当前已由原文唯一确认。复读的冲突、未确认和旧记录均需按本次实际回执保留，不用安星结果补字；五个目标也不扩成全表或新版本认证。


运限问题要求解释起岁、五行局或本命前置链时，首次可选`evidence_views.natal_prerequisites`的fields，读取`ziwei_horoscope.natal_prerequisites`。这是本次运限内部已生成本命的原值与原三个规则步骤，并非独立`ziwei_birth`运行；`separate_birth_run=false`。按实际出生排盘农历月时到命身、年干与命宫干支到纳音元素／局数，说明足够的连接，不能只复述局数。`nominal_age_calendar`的岁序参考年和目标流年干分别属于另外两层，不覆盖此处本命年干。`rule_trace`内的原典比较仍是给定农历条件下的比较，不能据此声称HKO原表已在本run重新核验、甲人语义唯一或原典岁首已证实；纳音元素比较不等于原书纳音名称校勘。来源核对按实际`date_conversion_provenance`区分实施表和印刷参照，未独立打开原表就如实说明，不能补写一次来源核验。完整JSON首次仍`fields=null`，沿同run交付并核验。
