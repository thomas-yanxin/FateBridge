# 紫微本命与动态结果的证据读取

先按本轮主题和[共享时间选择](timing-selection.md)取证。本页约束的是对象身份和计算连接，不另造事业评分器；有已返回连接时直接解释，不为同一连接重复排本命。

## 三种宫位身份

| 实际数据 | 对象身份与能回答的部分 | 不能改称 |
| --- | --- | --- |
| `ziwei_birth.palaces` 每项 `name/ganzhi/stars_detail`；命身另看 `ming_gong/shen_gong` | 本命十二宫；`stars_detail.name/brightness/mutagen` 是本命星、亮度与本命四化 | 目标年份的流年官禄／财帛等功能宫 |
| `ziwei_horoscope.scopes` 的 `scope/scope_palace_role/natal_palace_name/branch/palace_ganzhi` | `scope_palace_role=ming_palace_activity_index` 时，是该运限命宫活动索引所临的本命宫 | 该运限同名功能宫；如所临本命迁移宫不等于已完整审查流年迁移宫 |
| `scopes[].palace_map`（`dict[str, str]`，映射 `scope_palace_name -> "<branch>:<natal_palace_name>"`） | 引擎计算的该层十二宫功能名映射（可结合 `ziwei_birth.palaces[].stars_detail` 查本命星位） | 全部流曜、飞宫四化或某流派完整动态盘；缺此表时不能手补为引擎结果 |

普通动态首轮取实际合同的 `analysis_context`、`birth_context`、`ziwei_horoscope.ruleset/interpretation_scope/nominal_age/calendar_rules/scopes`。`scopes` 数组整体取回，再按 `scope` 选本次需要的大限、流年等层；不编 `scopes.流年` 或数字索引投影。核对 `analysis_context.context_role=target`、`analysis_datetime` 及其时区；`birth_context` 用于出生处理核对。

`birth_context` 是动态接口的出生回执；本命 `ziwei_birth_chart` 的出生回执仍是 `analysis_context/person_info`，不能因两工具资料相似而复制投影路径。

本命首轮使用实际合同发布的 `evidence_views.natal`。`reading_view.palaces` 保留全部本命星曜，`stars[].name/brightness/mutagen` 与完整 `palaces[].stars_detail` 对应；`null_star_fields_omitted` 声明缺少的亮度／四化属性等于完整字段的 `null`，不能补造。`major_stars=[]` 只代表没有十四主星，继续读取同宫 `stars`。`sanfang_sizheng_branches` 按 `sanfang_branch_order` 与同一视图十二宫关联，不在首轮复制四遍星曜。结构问题需要展开时用 `structure` 视图，查规则步骤用 `rules` 视图；用户要无损完整结果时使用 `include=["*"]`。

## 四化连接先认星，再认宫

当前每层 `mutagen` 是该层天干的四化星名；`mutagen_natal_links` 每项明确 `transformation/star/natal_palace_name/natal_branch/natal_star_brightness/natal_mutagen/scope_palace_name`（未命中本命盘时返回 `status=not_located_in_natal_chart`）。`scope_palace_name` 明确该星位在本层的功能宫；与该层 `palace_map` 核对，不能把 `natal_palace_name` 当成同名功能宫。这是动态标记连接本命星的落宫，优先使用引擎给出的连接，不重复调用本命。解释需要更多本命配合而已有本命盘时，再复用 `palaces[].stars_detail`；没有连接的旧部署可按实际星名核对已保留本命表，不能猜落宫。

- 示例读法：本命官禄有天机，目标流年 `mutagen.化科=天机` 且对应连接落本命官禄，可以说“该流年化科标记关联到本命官禄中的天机”。这不等于“流年官禄宫化科”。
- 本命 `natal_mutagen` 与流年 `transformation` 分开，不能把年度四化永久写入本命。某星没有连接时说明这一项未连接，不能假定另一个宫位。
- “化科便晋升”“化忌便不得转职”不是这些字段的结论。星曜、亮度、四化及相关宫位的传统含义需另有可靠作者／规则来源；有来源时可给与所问相关的条件式解释，未核对时保留为计算连接，不冒充已核实原典。

## 专题解释与新增价值

事业方向可读实际本命官禄、命身相关星曜配置；目标年度则说明大限背景、该年标记关联哪些已确认本命对象。来源查询可使用 `knowledge_catalog/knowledge_read` 或已核验作者文本，记录作者、版本、章节／页码及适用范围。排盘与外部软件一致，只核验所选口径下的计算；它不是星性或现代职业类比的出处。

用户明确要求原典版本与页码的审查中，在线转录的卷／章节定位不能冒充书影页码；未核到所选版本和页码的解释只列作未验参考，不作为已验收的传统主证。也不能从单星象意补出未查证的“运限四化连接本命宫后如何断事”组合规则。此时仍交付计算连接、已核实的其他依据和独立现实建议，不靠增加调用填补来源缺口。

把“返回事实”“来源解释”“现实建议”分开：例如先给出年度四化关联本命官禄的事实，只有查到相应解释规则后才讨论它怎样联系本次工作任务；面试材料、岗位授权、薪资和交接计划作为独立现实条件。没有相关解释来源时，不用别的主题象意或笼统吉凶填空，仍可交付已有八字／其他有据视角。

第二方法应补充原先没有的主题结构、时段条件或真实分歧；相同出生数据共享历法输入，不能当作独立统计印证。删除紫微会丢掉一个新字段，只能证明信息增量；咨询增益还要看它是否改善本次判断及表达。

## 规则配置与结构依据

### 基础配置与本命结构

- **规则版本与差异**：首轮保留 `ziwei_birth.ruleset` 或 `ziwei_horoscope.ruleset`。默认 `iztro_2_5_8` 是软件兼容口径；`quanshu_v2_excerpt` 1.3.2 选择闰月、壬年四化、亮度表、长生方向、旬空双支、部分年度流曜，并采用邻宫起大限及火铃年支定点读法，余项仍有软件回退，不能称全书认证。与 1.2.0 相比，摘录配置的十二宫大限年龄区间及火铃位置会变化，不能只换版本名继续引用旧值。该闰月条文只覆盖本命安身命；目标流月闰月仍保留软件半月规则。动态层复用所选四化表为软件约定；配置不同先解释真实差异，不挑更符合叙事的盘。目标时间可传 `analysis_minute/analysis_timezone`，与出生时区独立。
- **三方四正与空宫**：本命 `palaces[].structural_evidence` 提供十四主星名单、是否无主星及本宫／两三合宫／对宫的实际星位。空宫只表示没有十四主星，不等于没有任何星；对宫星没有搬入本宫。三方四正是盘面关系，不自动认证古典成格或吉凶。性别未知仍可读本命非运限结构，大限范围留空，不把未知当女命排运。
- **命身主与长生博士**：本命新增 `chart_masters` 与 `calendar_cycles`，命主按命宫支、身主按生年支，不要把命主／身主当成命宫／身宫所在主星。十二长生和博士十二神分层读取，未知性别留空，循环名称不作临床或寿命判断。所选亮度表与同卷散文有分歧；身主转录火玲、明刊火鈴仍不足以裁定单取哪颗，保留显式软件约定，不按咨询叙事挑选规则。
- **旬空与流曜条数**：摘录配置自 1.2.0 起的旬空显示两支，因此 `reading_view` 是 66 种星名、67 条星曜落点；软件配置为 66 条，不把条数当新增星种。`voids` 视图的 `ziwei_birth.void_systems.xun` 区分旬空双支与软件单支口径，古天空对应今地空、原文本生年解神对应年解，不能拿软件另列的同名星替代。摘录配置的流年 `flowing_stars` 返回禄羊陀及天德、月德、丧门、吊客、白虎、官府共九项（软件配置仍为三项），结合 `scope_palace_name/natal_palace_name/system_id` 读取，不搬移本命星。流年月德按目标年支，年度官府不等于博士官府；`annual_three_sha` 逐名位置为空时不依顺序配宫或从博士同名标记补齐。
- **原文星义与 `symbolism`**：按本命实际 `palaces[].stars_detail`（或 `reading_view`）、`sihua` 与 `ruleset` 解读本命星曜、亮度与四化，不把文献中的比喻性文字直接写成禄权科忌赋值；若需完整明细可使用 `include=["*"]`。
- **指定刻本四化（`editions` / `sihua_source`）**：`ziwei_rules.rule_catalogue` 的 `sihua_by_year_stem` 与 `ruleset` 给出所选口径四化表；`sihua_source=rule_profile` 时两基础配置在庚年仍取太阴化科、天同化忌。显式指定明刊四化表时在本命、运限和规则查询一致传 `sihua_source=naj_ming_v1`（`ruleset.sihua_source="naj_ming_v1"`、`ruleset.sihua_rule` 为 `naj_ming_v1`）；此时庚干为太阳禄、武曲权、天同科、天相忌，壬干为天梁禄、紫微权、天府科、武曲忌，以实际 `stars_detail.mutagen` 和 `mutagen_natal_links` 解释，不表示整书、时钟、亮度或运限复用获原典认证。
- **安紫微日表与前置链（`rules`）**：核查历法约定、规则版本与安星方法时读 `rules` 视图（`ziwei_birth.ruleset`、`ziwei_birth.calendar_rules`）及 `ziwei_rules.rule_catalogue`；不把软件规则或局部对照表扩写成整部原典认证或公历/时支/纳音全表校勘。
- **明刊结构条件与分段（`classical_conditions` / `limit_subperiods`）**：本命格局条件读取 `ziwei_birth.named_patterns`（含 `total_checked`、`matched_count`、`matched`、`unmatched_ids`），结构与流派规则核对使用 `ziwei_rules.rule_catalogue.named_patterns` 与 `cycle_methods`；展开运限层级与大限起岁请通过 `ziwei_timing` 的 `scopes`、`childhood_limit` 与 `nominal_age_calendar` 核对，未到起岁时大限仍保留 `not_started`，不补写事件断言。

### 运限起止、童限与循环比较

- **运限规则与来源（`source_rules`）**：读取 `ziwei_horoscope.ruleset` 与 `ziwei_horoscope.calendar_rules`（含 `school`、`id`、`overrides`、`day_divide`、`year_divide`）。摘录配置按邻宫起大限、火铃年支定点；小限按 `scopes` 实际落支解释，斗君见 `ziwei_horoscope.doujun_branch`。
- **童限与大限起止（`childhood` / `decade_activation`）**：`childhood_limit` 明示一至六岁童限落宫与本命连接，与正式大限分列；一至六岁外（七岁及以上）`childhood_limit.status=not_active`。未到起岁时 `scopes` 中大限 `status=not_started`、`mutagen=null`、`palace_map=[]`、`mutagen_natal_links=[]` 是该层未生成，不能改述为无化忌或童限四化。需要解释起岁、五行局或本命前置链时首次可选 `natal_prerequisites` 读 `ziwei_horoscope.natal_prerequisites`（不覆盖 `nominal_age_calendar` 与目标流年干）。
- **长生与博士循环（`cycle_sources`）**：读取 `ziwei_birth.calendar_cycles` 与各宫 `palaces[].changsheng12` / `boshi12`。默认软件长生在阴年与明刊男顺女逆不同；性别未知时循环字段留空或按实际返回解释，不按咨询叙事挑规则。

### 历法、校时精度与岁序时钟

- **历法来源与日期对照（`calendar` / `calendar_sources`）**：`calendar_basis` 区分 `placement_lunar_date`（当前排盘农历）、`civil_date_lunar_date`（输入钟表日期查表）与 `reference_lunar_date`（转固定 UTC+08 后查表），跨日时保留三者区分；`calendar_basis.method_id`、`day_boundary` 与 `ziwei_birth.calendar_rules` 核对历法与闰月约定。
- **校时精度与重复钟时（`time_input`）**：本命读 `ziwei_birth.calendar_basis.time_input` 与 `civil_clock`，运限读 `ziwei_horoscope.calendar_basis.{birth,target}.time_input` 与 `civil_clock`（运限另有 `nominal_age_calendar`）。区分 `solar_unavailable`、`civil_clock_selected`、`timezone_assumed` 与 `province_longitude`；未应用校正时分量为 `null` 不代表均时差或夏令时为零。夏令时重复钟时若有明确记录可传 `birth_utc_offset` / `analysis_utc_offset`（`±HH:MM[:SS]`）在已解析命名时区中选定物理瞬间，实际先后按 `civil_clock` 的 UTC 瞬间比较。
- **岁序时钟**：`ziwei_timing` 默认 `nominal_age_basis=birth_civil_timezone`，把出生与目标实际瞬间均转到出生民用时区查农历年，正月初一 00:00 换岁；先读 `nominal_age_calendar` 两端年份、`day_boundary` 与参考时区。本命安星及年干仍取出生排盘钟，流年／月／日／时仍取目标钟；春节前后分别得到实际岁序（不靠把 0 岁钳成 1 岁）。
