# 紫微本命与动态结果的证据读取

先按本轮主题和[共享时间选择](timing-selection.md)取证。本页约束的是对象身份和计算连接，不另造事业评分器；有已返回连接时直接解释，不为同一连接重复排本命。

## 三种宫位身份

| 实际数据 | 对象身份与能回答的部分 | 不能改称 |
| --- | --- | --- |
| `ziwei_birth.palaces` 每项 `name/ganzhi/stars_detail`；命身另看 `ming_gong/shen_gong` | 本命十二宫；`stars_detail.name/brightness/mutagen` 是本命星、亮度与本命四化 | 目标年份的流年官禄／财帛等功能宫 |
| `ziwei_horoscope.scopes` 的 `scope/scope_palace_role/natal_palace_name/branch/palace_ganzhi` | `scope_palace_role=ming_palace_activity_index` 时，是该运限命宫活动索引所临的本命宫 | 该运限同名功能宫；如所临本命迁移宫不等于已完整审查流年迁移宫 |
| `scopes[].palace_map` 的 `scope_palace_name/branch/natal_palace_name/natal_palace_ganzhi` | 引擎计算的该层十二宫功能名映射；`natal_stars_detail` 仍是本命星位 | 全部流曜、飞宫四化或某流派完整动态盘；旧部署缺此表时不能手补为引擎结果 |

普通动态首轮取实际合同的 `analysis_context`、`birth_context`、`ziwei_horoscope.ruleset/interpretation_scope/nominal_age/calendar_rules/scopes`。`scopes` 数组整体取回，再按 `scope` 选本次需要的大限、流年等层；不编 `scopes.流年` 或数字索引投影。核对 `analysis_context.context_role=target`、`analysis_datetime` 及其时区；`birth_context` 用于出生处理核对。

`birth_context` 是动态接口的出生回执；本命 `ziwei_birth_chart` 的出生回执仍是 `analysis_context/person_info`，不能因两工具资料相似而复制投影路径。

本命首轮使用实际合同发布的 `evidence_views.natal`。`reading_view.palaces` 保留全部本命星曜，`stars[].name/brightness/mutagen` 与完整 `palaces[].stars_detail` 对应；`null_star_fields_omitted` 声明缺少的亮度／四化属性等于完整字段的 `null`，不能补造。`major_stars=[]` 只代表没有十四主星，继续读取同宫 `stars`。`sanfang_sizheng_branches` 按 `sanfang_branch_order` 与同一视图十二宫关联，不在首轮复制四遍星曜。结构问题需要展开时用 `structure` 视图，查规则步骤用 `rules` 视图；用户要完整结果时使用 `detail=audit`、`fields=null`。

## 四化连接先认星，再认宫

当前每层 `mutagen` 是该层天干的四化星名；`mutagen_natal_links` 每项明确 `transformation/star/natal_palace_name/natal_palace_ganzhi/natal_branch/natal_star_label/natal_star_brightness/natal_mutagen`。新版连接另含 `scope_palace_name`，明确该星位在本层的功能宫；与该层 `palace_map` 核对，不能把 `natal_palace_name` 当成同名功能宫。这是动态标记连接本命星的落宫，优先使用引擎给出的连接，不重复调用本命。解释需要更多本命配合而已有本命盘时，再复用 `palaces[].stars_detail`；没有连接的旧部署可按实际星名核对已保留本命表，不能猜落宫。

- 示例读法：本命官禄有天机，目标流年 `mutagen.化科=天机` 且对应连接落本命官禄，可以说“该流年化科标记关联到本命官禄中的天机”。这不等于“流年官禄宫化科”。
- 本命 `natal_mutagen` 与流年 `transformation` 分开，不能把年度四化永久写入本命。某星没有连接时说明这一项未连接，不能假定另一个宫位。
- “化科便晋升”“化忌便不得转职”不是这些字段的结论。星曜、亮度、四化及相关宫位的传统含义需另有可靠作者／规则来源；有来源时可给与所问相关的条件式解释，未核对时保留为计算连接，不冒充已核实原典。

## 专题解释与新增价值

事业方向可读实际本命官禄、命身相关星曜配置；目标年度则说明大限背景、该年标记关联哪些已确认本命对象。来源查询可使用 `knowledge_catalog/knowledge_read` 或已核验作者文本，记录作者、版本、章节／页码及适用范围。排盘与外部软件一致，只核验所选口径下的计算；它不是星性、现代职业类比或现实预测有效性的出处。

用户明确要求原典版本与页码的审查中，在线转录的卷／章节定位不能冒充书影页码；未核到所选版本和页码的解释只列作未验参考，不作为已验收的传统主证。也不能从单星象意补出未查证的“运限四化连接本命宫后如何断事”组合规则。此时仍交付计算连接、已核实的其他依据和独立现实建议，不靠增加调用填补来源缺口。

把“返回事实”“来源解释”“现实建议”分开：例如先给出年度四化关联本命官禄的事实，只有查到相应解释规则后才讨论它怎样联系本次工作任务；面试材料、岗位授权、薪资和交接计划作为独立现实条件。没有相关解释来源时，不用别的主题象意或笼统吉凶填空，仍可交付已有八字／其他有据视角。

第二方法应补充原先没有的主题结构、时段条件或真实分歧；相同出生数据共享历法输入，不能当作独立统计印证。删除紫微会丢掉一个新字段，只能证明信息增量；咨询增益还要看它是否改善本次判断及表达。

## 规则配置与结构依据

### 基础配置与本命结构

- **规则版本与差异**：首轮保留 `ziwei_birth.ruleset` 或 `ziwei_horoscope.ruleset`。默认 `iztro_2_5_8` 是软件兼容口径；`quanshu_v2_excerpt` 1.3.2 选择闰月、壬年四化、亮度表、长生方向、旬空双支、部分年度流曜，并采用邻宫起大限及火铃年支定点读法，余项仍有软件回退，不能称全书认证。与 1.2.0 相比，摘录配置的十二宫大限年龄区间及火铃位置会变化，不能只换版本名继续引用旧值。该闰月条文只覆盖本命安身命；目标流月闰月仍保留软件半月规则。动态层复用所选四化表为软件约定；配置不同先解释真实差异，不挑更符合叙事的盘。目标时间可传 `analysis_minute/analysis_timezone`，与出生时区独立，分钟输入不构成分钟级预测。
- **三方四正与空宫**：本命 `palaces[].structural_evidence` 提供十四主星名单、是否无主星及本宫／两三合宫／对宫的实际星位。空宫只表示没有十四主星，不等于没有任何星；对宫星没有搬入本宫。三方四正是盘面关系，不自动认证古典成格、吉凶或现实结果。性别未知仍可读本命非运限结构，大限范围留空，不把未知当女命排运。
- **命身主与长生博士**：本命新增 `chart_masters` 与 `calendar_cycles`，命主按命宫支、身主按生年支，不要把命主／身主当成命宫／身宫所在主星。十二长生和博士十二神分层读取，未知性别留空，循环名称不作临床或寿命判断。所选亮度表与同卷散文有分歧；身主转录火玲、明刊火鈴仍不足以裁定单取哪颗，保留显式软件约定，不按咨询叙事挑选规则。
- **旬空与流曜条数**：摘录配置自 1.2.0 起的旬空显示两支，因此 `reading_view` 是 66 种星名、67 条星曜落点；软件配置为 66 条，不把条数当新增星种。`voids` 视图的 `source_name_mapping` 说明古天空对应今地空、原文本生年解神对应年解，不能拿软件另列的同名星替代。摘录配置的流年 `flowing_stars` 返回禄羊陀及天德、月德、丧门、吊客、白虎、官府共九项（软件配置仍为三项），结合 `scope_palace_name/natal_palace_name/system_id` 读取，不搬移本命星。流年月德按目标年支，年度官府不等于博士官府；`annual_three_sha` 逐名位置为空时不依顺序配宫或从博士同名标记补齐。
- **原文星义与 `symbolism`**：读取 `symbolism` 视图的 `symbolic_properties.records` 连接引句、原字五行与实际本命星位；化财、化印、化善、遇帝为权等文字不是禄权科忌赋值，以 `natal_mutagen` 为实际本命四化，天同水金、七杀火金、贪狼水木保持 `elements_as_written`。16 条属性不是全书象意或全部组合断语。明刊星义专题用 `contextual_symbolism` 先核条件或 `ming_symbolism` 读 `ming_textual_properties`（完整输出用 `detail=audit`、`fields=null`）；明刊保留七杀“將星”、文昌“文魁之宿”、天梁“化陰”，`occurrences.kind` 区分本命星、实际本命四化与博士循环标记，四化属性五行不改被化星原属性、五行局或亮度。古天空只连接本系统地空，博士飞廉不连接年支蜚廉；病符、官府未写五行时保持空，未配层的歲君、丧门等不否定已算年度层。廉贞“在官禄”按实际本命官禄宫、“在身命”按命或身明示读法；七杀“遇帝”几何未定，`condition_match` 为 `null` 不自选范围，化禄喜见禄存等三条同样保留未裁定条件，不把寿、病、孤等字当寿命或临床判断。

### 明刊四化、安星与辅星来源

- **指定刻本四化（`editions` / `sihua_source`）**：`ziwei_rules.rule_catalogue.sihua_source_comparison` 比较全表，本命 `sihua_source_comparison` 只连接当前年干异文。明刊卷三庚年刻“日武同相”，`sihua_source=rule_profile` 时两基础配置仍取太阴化科、天同化忌，`compared_assignments_applied=false` 不表示已切换成明刊整盘。显式指定明刊四化表时在本命、运限和规则查询一致传 `sihua_source=naj_ming_v1`（组合 `ruleset.version` 含 `+sihua.naj-ming-v1`，`sihua_source_url` 专指四化原页）；此时庚干为太阳禄、武曲权、天同科、天相忌，壬干为天梁禄、紫微权、天府科、武曲忌，以实际 `stars_detail.mutagen` 和 `mutagen_natal_links` 解释，`compared_assignments_applied=true` 不表示整书、时钟、亮度或运限复用获原典认证。
- **安紫微日表与前置链（`rules`）**：核查安紫微原典时读 `rule_trace` 中 `ziwei_tianfu_placement.outputs.source_comparison`。`source_kind=prose_derived_with_unresolved_grid_label` 表示据原文规则推导，水二局二十一、木三局十一、火六局初六无唯一直接标签，木三局十二有两处宫位，火六局初八寅位仍有疑读；`matches_source_record` 只比较最初选定转录，隔离复读另列于 `independent_review`，同时出现 `targeted_rereading` 时若 `unique_source_confirmation_supported=false`，不得据旧匹配声称已唯一确认。`matches_unique_direct_branch=null` 是未能形成唯一直接比较，实际星位仍由所选配置返回。前置链另看 `wuhu_dun_nayin_ju.outputs.source_comparison`：`compared_rules_applied=false` 时不把比较值当当前命宫或五行局，`matches_source_chain` 不认证公历换算、时支确定或纳音全名校勘。
- **逐颗辅星来源（`auxiliary_sources`）**：`auxiliary_placement_sources.placements` 的 `actual_branch/calculation_path` 连接当前实算星位，`expected_branch/matches_source_rule` 只比较所列明刊条文。正常月十六辅星有完整方向规则；闰月左辅、右弼、天刑、天姚、三台、八座及裸条文火铃比较值为空（摘录配置自 1.3.0 起采用年支定点火铃）。`unchecked_star_names` 表示本批未校核，不表示算错或不存在。
- **明刊结构条件与分段（`classical_conditions` / `limit_subperiods`）**：`classical_conditions` 读取 `ming_structural_conditions.index` 核对五条格局几何（`geometry_match` 与 `evaluated_necessary_premises_match` 不表示原文全部条件满足，`source_literal_example_matches` 仅比所录两具体宫位例，缺对象为 `null`）；完整条文、原注与 `calculation_path` 须首次选 `classical_condition_details` 或 `detail=audit`、`fields=null`。1.1.0 按两份隔离原图复读将左右夹命小注更正为“九月十一月”，“加吉方论”归紧邻“魁钺命身多折桂”，紫微辅弼财帛小注分歧保留 `source_annotation=null` 与 `annotation_revision`。运限分段展开 `limit_subperiods` 或 `limit_subperiod_details` 读 `ming_limit_subperiods`：上／下五年依已选虚岁与大限十岁区间，不按年龄末位取余，起限前为 `not_started`，六个双属星名不选唯一五年段，小限半年 `half/half_start/half_end` 仍 `null`，`full_traditional_judgment=null` 不转述为已验事件。

### 运限起止、童限与循环比较

- **运限来源比较（`source_rules`）**：读取 `ziwei_horoscope.source_comparison`。大限分别给明文首宫和当前首宫，摘录配置才按邻宫起；小限只核对给定岁序后的顺逆和落支，斗君仅在普通生月核对，火铃 `positions_under_selected_reading` 是显式年支定点读法，现代作者自序仅作读法存在补证。
- **童限与大限起止（`childhood` / `decade_activation`）**：`childhood_limit` 明示一至六岁命、财、疾厄、妻、福、官禄，对应现代宫名并连接本命星曜，与正式大限分列；七岁以后未得唯一规则时 `status=unresolved_from_source`。大限起止读 `decade_activation` 的 `source_comparison.daxian`（默认 1.1.2、摘录 1.3.2 起）：未到起岁时 `status=not_started`、`mutagen=null`、`palace_map=[]`、`mutagen_natal_links=[]` 是该层未生成，不能改述为无化忌或童限四化，`is_childhood_limit=false` 不表示大限已开始。需要解释起岁、五行局或本命前置链时首次可选 `natal_prerequisites` 读 `ziwei_horoscope.natal_prerequisites`（`separate_birth_run=false`，不覆盖 `nominal_age_calendar` 与目标流年干）。
- **长生与博士循环（`cycle_sources`）**：`cycle_source_comparison` 的 `positions.changsheng/positions.boshi` 按地支返回 `actual`、`candidates` 及 `match`。默认软件长生在阴年与明刊男顺女逆不同；性别未知时起点与对宫保留两可确定值、`direction_match=null`。明刊博士为蜚廉、大耗、官府（博士蜚廉对应当前飞廉，与年支蜚廉分层）。

### 历法、校时精度与岁序时钟

- **历法来源与日期对照（`calendar` / `calendar_sources`）**：`calendar_basis` 区分 `placement_lunar_date`（当前排盘农历）、`civil_date_lunar_date`（输入钟表日期查表）与 `reference_lunar_date`（转固定 UTC+08 后查表），跨日时保留三者区分。展开 `calendar_sources` 读 `calendar_basis.date_conversion_provenance`：1900 年印刷参照为 TAM 全年表（最初 30 日实施用 PMO 补表），1901—2100 参照 HKO（2100-02-09 以后用 HKO 补表），实施由 `fatebridge_lunardate_adapter_v1` 完成，`applied_year_info_correction` 逐时钟记录实际农历年登记修正（如 1934 年一月仍可能用 1933 年修正）。
- **校时精度与重复钟时（`time_input`）**：本命读 `calendar_basis.time_input`，运限读 `calendar_basis.birth.time_input`。区分 `solar_unavailable`、`civil_clock_selected`、`timezone_assumed` 与 `province_longitude`；未应用校正时分量为 `null` 不代表均时差或夏令时为零。`minute_sensitivity` 以秒 0 对照 `59.999999` 秒端点，`endpoint_seconds=[0]` 时上端点缺失；`time_input_minute_sensitive=true` 表示端点跨时支或排盘日期，先说明基准再解释。夏令时重复钟时若有明确记录可传 `birth_utc_offset` / `analysis_utc_offset`（`±HH:MM[:SS]`）在已解析命名时区中选定物理瞬间，实际先后按 `calendar_basis.civil_clock` 的 UTC 瞬间比较。
- **岁序时钟**：`ziwei_timing` 默认 `nominal_age_basis=birth_civil_timezone`，把出生与目标实际瞬间均转到出生民用时区查农历年，正月初一 00:00 换岁；先读 `nominal_age_calendar` 两端年份与参考时区。本命安星及年干仍取出生排盘钟，流年／月／日／时仍取目标钟；春节前后分别得到实际岁序（不靠把 0 岁钳成 1 岁），`boundary_source_evidence` 不认证整书或现实预测有效。
