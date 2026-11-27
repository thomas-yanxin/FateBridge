# 宿曜与宿占取证

只在本轮实际使用宿曜／宿占时读取。以工具当前公开 Schema 和同 run 结果为准，计算由引擎完成，不能用星图或模型重算本命宿。

## 双人相性

### 历法基准与历史参考

- **默认中国农历（`sukuyo_compatibility`）**：默认按固定 UTC+08 现代中国农历月日及 T1299 下卷十五日望宿逆顺法。
- **日本现代参考（`calendar_basis=japanese_hutime_1002_1_utc09`）**：HuTime 1002.1 冻结逐日参考，范围 1872-02-09 至 2031-01-22、固定 UTC+09；默认出生时区仍为 `+08:00`，不因选日本参考便猜东京时区。双方共用一套 basis，范围外不能改用中国历补齐。读取 `calendar_reference` 的来源类别、支持范围、资料版本及差异（2015 年起标作参考推算，保留 1989 月度边界差异及文档 2033 与实体 2031 范围差别）。
- **日本历史参考（`calendar_basis=japanese_naoj_historical_utc09`）**：NAOJ 冻结月首参考，前推公历 0001-01-01 至 1872-12-31、固定 UTC+09（不因地点或出生年代自动选用）。453 阴历年及以前为儀鳳暦平朔回推，454 起区分具历史校正的参考、实际颁历与当时钟时；阴历年 0 是来源字段，不是公元 0 年出生输入。1872 年旧历十二月因改历仅两天，1873-01-01 不续算旧历。读取 `calendar_reference.cross_source_comparison` 保留 HuTime 1001.1 210 个分歧日期（`control_applied_to_primary=false`）；公元 1 年固定时差 `date_support` 中 `0000-12-31` 分支用于判断范围外候选，不代表公元 0 年出生。
- **单日核验与不确定时区范围**：`profile_calculation.host_calculation` 同时返回生日加十三含首位法；未知时间不填 0 点或中午，经纬度不参与本算法。其他时区当地日期可能对应多个宿主历日，读取 `date_support.utc_support_intervals` 与各 `calendar_candidates` 的完整历法与条件关系；夏令日（23／25 小时）或政治回拨（如 47 小时）不按固定 24 小时猜，完整候选同宿时仅宿和关系确定，唯一历日与钟时仍未定。

### 视图读取、闰月与桧尾口诀

- **首轮字段与方向性**：按问题选 `relationship` 或 `calendar` 视图字段（视图名不是请求参数），核对 `status`、`person1/2.calendar`、各自 `natal_su27`、双向关系（`person1_to_person2` 与 `person2_to_person1`）及 `rulesets`。`su27_basis` 是算法版本，`pair` 是界面配对类别，`sequence_group` 是三九组序，`distance=null` 不补近中远；结交条文不泛化为必然婚姻或人格结论。
- **闰月与印本异文**：默认档案闰月 `unresolved` 时保留已算农历与候选宿，只限制未定关系；`repeat_month` 为显式同名月约定。`source_table_variant` 保留大正藏印本 28 宿月建表（含牛且可能与 27 宿不同），它不是本次三九宿或月亮实测宿位。
- **桧尾口诀（`calendar_profile=hinoo_t1299_host27`）**：应用《桧尾口诀》闰月复用与小月缺日补配，初一前／后半候选不同时须明确原典半日参数；`candidate_relation_analysis`（`applied_to_primary=false`）仅列候选组合，不得挑一行作确定相性。保留书目、版本、URL、原段与校记（SAT HTML、历史缓存与真福寺／名古屋写本异读分别说明；`critical_calendar_reference.image_witness_research` 按冻结采集时间解释，不把研究参考当已应用历法）。

## 十二宫分足查表

- **`palace_reference` 条件查表**：仅以本次历日宿名查 T1299 上卷 108 足表（宿占在 `sukuyo` 内，双人在 `person1/2` 内）。`textual_pada` / `person1/2_textual_pada` 为显式查表条件，不据出生钟时或实测月亮补造；未指定保留四足，跨宫宿保留多宫。
- **宫序与太阳／太阴分**：第一为师子而非 House 1，牛宫非牛宿，太阳分／太阴分非昼夜生盘。`birth_pada_established=false` 及未给历史黄经原点时，不把查表宫名解释为实际本命宫、实测月亮星座或双方相性。

## 宿占日课与具体事项

### 钟时、星图与三类依据

- **钟时与经纬度门槛**：`suzhan` 的 `time` 可省略或传 `null`，仅算历法、日期候选及事项证据（`chart` / `astronomy` 为 `null`，`params.birthTimeImputed=false`）。已知钟时须同时传完整 `latitude` / `longitude`（`0°` 有效）才生成星图，缺项报错而不用默认地点或 0 点换取星图；旧连接尚要求 `time` 时不补时。
- **三类依据分离**：`sukuyo` 为农历历日，`calendar_day` 为黑白月日名与时段条文，`astronomy` 为七曜物理天文（默认现代距星视赤经不等宽研究口径，不称唐代宿界；`legacy` 为旧版等分黄道示意）。

### 活动视图与行为细节匹配

按发布的 `activity` 视图读取时，须同时保留：

- `sukuyo.calendar` 与 `sukuyo.calendar_day`：日名、上下卷名称、一般日类、昼夜限制及差异。
- `sukuyo.lower_methods`：下卷七宿性与七曜证言（保留火曜成亲／征债等相反条文及大正主文／明本校记，牛宿仅为参考表成员）。
- `sukuyo.personal_day`：本命到历日的有向三九（`source_day_evidence` 逐条保留上卷、下卷及下卷“又一说”，`priority_clause_applied_to_aggregate=false` 时不据“己身三九若吉”删相反见证）；无本命时不代填。
- `sukuyo.six_palace_reference`：原典六本命相对位置（命／事／意／聚／同／克第 1／10／4／16／20／13 宿），未给本命保留 `natal_mansion_required`；`seven_luminary_transits_evaluated=false` 时不称已发生七曜犯宿、六害或灾祸。
- `sukuyo.lower_mansion_day`、`sukuyo.conjunction_doctrine` 与完整 `sukuyo.activity_assessment`：事项、已确认细节、分层状态、`matched_rules/conditional_rules`、来源与适用范围。
- **行为细节（`activity_details` vs `effective_activity_details`）**：`activity_details` 只填当前聊天已确认且与 `activity` 同类的事实（如设学 `founding_school`、入学 `beginning_study`/`learning_with_teacher`、远行外国须同时 `long_distance_journey` + `journey_abroad`、`social_gathering` 与 `forming_friendship` 分开、月曜“私情出行”须明确 `private_journey`、日曜王公远行须 `royal_or_official_traveler` + `long_distance_journey`、启请法要须 `monastic_dharma_request`）。`effective_activity_details` 与 `detail_inferences` 明示行为分类推导（如还钱 `repaying_debt`、经书分类等），不把推导当新收集事实。
- **宜忌状态与同 run 完整上下文**：`conflicted` 须说明各自条件、卷别与出处，不挑边合成“综合吉日”；`conditional_rules` / `conditional_only` 不计入确定汇总；`uncovered` / `not_evaluated` 不说成凶或无影响。同 run 核验须保留完整 `sukuyo.candidate_days`、`sukuyo.candidate_mansion_days`；衣事选 `activity=clothing` 及 `clothing` 卡并保留完整 `clothing_reference`（裁缝、制作、修理、穿着与穿新衣分别确认，`royal_wearer` 仅限明确王者身份）。

### 特殊日、昼夜与太白方位

- **太白方位（`sukuyo.taibai_direction_reference`）**：按 `calendar.lunar_day` 实际入月日查表，保留八方、中央入地与天上（后两者 `horizontal_direction=null` 不补 0°），明本删去初十／二十／三十天上行记 `row_deleted_in_apparatus`；`movement_alignment_evaluated=false` 时不将顺逆定为面向／背向或抵销宜忌。
- **昼夜条件与民用日界**：`calendar_day.clock_evaluation_status=not_computed` 时不能给出已核定的上午／下午或整天结论；0393c26 下卷夹注释“一夜”为十一夜，读取 `verse_abbreviation_resolution` 与 `prose_verse_time_semantic_conflict`。`clock_doctrine` 平明起曜各八时不填入西方 24 行星时；`weekday.basis=modern_utc_plus08_civil_midnight`（或日本 `modern_utc_plus09_civil_midnight`）且 `classical_daybreak_boundary_acceptance=false` 时不称已复原平明起算。
- **特殊日名（`special_day_labels` / `special_day_evidence`）**：分别列上下卷大正与明本校记，保留“冒、底”字面与甘露学道限 `religious_learning`；`physical_lunar_conjunction_evaluated=false` 时不称实测月亮与宿合。

## 新旧历与二十八宿名目的来源核对

- **《宿曜帳》117-20 与新旧历**：第 10—11 帧“无相違”论七曜直日，不等于月宿、全部历数或闰月法相同；第 17 帧“三月／昴畢并见”已由窄裁复核更正为“二月／即畢”，保留旧读作审查历史，不继续当原典异文。详细校读见[宿曜参考](../../sukuyo.md)。
- **日本近世历法与善通寺 109-4**：采用 NAOJ 日本历史宿主并返回 `calendar_reference.edo_calendar_method_reference` 时，按实际阴历年与具名时段解释（宝历三、四年属貞享暦；`intercalation_research` 保留内田论文全十行及表 3 异月；`reform_month_length_reference` 保留 1872 十二月 30／2 日差别）。善通寺 109-4 题记与工作读法按[所选读录与前瞻文件](../../sukuyo.md)区分旧接纳片段与模型候选。

## 发送前核对

- **`directional_travel` 禁闭方向**：只有明确 `northbound_journey/eastbound_journey/southbound_journey/westbound_journey` 才适用，不从地点／GPS／角度猜或扩成斜向；四条具名禁向“纵吉时亦不可行”不被吉时抵销，壁宿南行相反条文与十／一／二宫校记并列保留。
- **终检与审计**：核对历日宿与天文月宿有无混用、主客方向有无颠倒、候选是否写成确定、原典冲突与时段条件是否保留。需要回执级引用核验时首次即传 `detail=audit`、`fields=null`（不重算补齐）；`validation.sukuyo.verify_sukuyo_context_claims` 通过只表示上下文引用完整，自由文本语义仍须独立核对。更多见[算法、来源和未决项](../../sukuyo.md)。
