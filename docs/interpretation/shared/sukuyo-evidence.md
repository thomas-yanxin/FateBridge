# 宿曜与宿占取证

只在本轮实际使用宿曜／宿占时读取。以工具当前公开 Schema 和同 run 结果为准，计算由引擎完成，不能用星图或模型重算本命宿。

## 双人相性

### 历法基准与历史参考

- **默认中国农历（`sukuyo_compatibility`）**：默认按固定 UTC+08 现代中国农历月日及 T1299 下卷十五日望宿逆顺法。
- **日本现代参考（`calendar_basis=japanese_hutime_1002_1_utc09`）**：HuTime 1002.1 冻结逐日参考，范围 1872-02-09 至 2031-01-22、固定 UTC+09；默认出生时区仍为 `+08:00`，不因选日本参考便猜东京时区。双方共用一套 basis，范围外不能改用中国历补齐。核对 `calendar_basis`、`calendar_system`、`calendar_backend`、`calendar_timezone` 与 `input_timezone`（2015 年起为参考推算，文档 2033 与实际支持范围 2031 存在边界差别）。
- **日本历史参考（`calendar_basis=japanese_naoj_historical_utc09`）**：NAOJ 冻结月首参考，前推公历 0001-01-01 至 1872-12-31、固定 UTC+09（不因地点或出生年代自动选用）。453 阴历年及以前为儀鳳暦平朔回推，454 起区分具历史校正的参考、实际颁历与当时钟时；阴历年 0 是来源字段，不是公元 0 年出生输入。1872 年旧历十二月因改历仅两天，1873-01-01 不续算旧历。公元 1 年固定时差 `date_support` 中 `0000-12-31` 分支用于判断范围外候选，不代表公元 0 年出生。
- **单日核验与不确定时区范围**：`profile_calculation.host_calculation` 同时返回生日加十三含首位法；未知时间不填 0 点或中午，经纬度不参与本算法。其他时区当地日期可能对应多个宿主历日，读取 `date_support.utc_support_intervals` 与各 `calendar_candidates` 的完整历法与条件关系；夏令日（23／25 小时）或政治回拨（如 47 小时）不按固定 24 小时猜，完整候选同宿时仅宿和关系确定，唯一历日与钟时仍未定。

### 视图读取、闰月与桧尾口诀

- **首轮字段与方向性**：按问题选 `relationship` 或 `calendar` 视图字段（视图名可传给 `include`，不可直接传给 `fields`），核对 `status`、`person1/2.calendar`、各自 `natal_su27` 与双向关系（`person1_to_person2` 与 `person2_to_person1`）。`su27_basis` 是算法版本，`pair` 是界面配对类别，`sequence_group` 是三九组序，`distance=null` 不补近中远；结交条文不泛化为必然婚姻或人格结论。
- **闰月与印本异文**：默认档案闰月 `unresolved` 时保留已算农历与候选宿，只限制未定关系；`repeat_month` 为显式同名月约定。大正藏印本另有含牛宿的 28 宿月建表异文，与本次 27 宿三九计算和实测月亮宿位分开。
- **桧尾口诀（`calendar_profile=hinoo_t1299_host27`）**：应用《桧尾口诀》闰月复用与小月缺日补配，初一前／后半候选不同时须明确原典半日参数；`candidate_relation_analysis`（`applied_to_primary=false`）仅列候选组合，不得挑一行作确定相性。读取实际返回的 `profile_calculation.mansion_method_id`、`profile_calculation.ruleset_id` 与 `profile_calculation.short_month_assignment`（含 `leap_short_month_precedence`），不把研究参考或现代重建次序当已定古历。

## 十二宫分足查表

- **`palace_reference` 条件查表**：仅以本次历日宿名查 T1299 上卷 108 足表（宿占在 `sukuyo` 内，双人在 `person1/2` 内）。`textual_pada` / `person1/2_textual_pada` 为显式查表条件，不据出生钟时或实测月亮补造；未指定保留四足，跨宫宿保留多宫。
- **宫序与太阳／太阴分**：第一为师子而非 House 1，牛宫非牛宿，太阳分／太阴分非昼夜生盘。`palace_reference.textual_pada` 为 `null`（`status=palace_resolved_pada_unspecified` / `mansion_or_pada_ambiguous`）及未给历史黄经原点时，不把查表宫名解释为实际本命宫、实测月亮星座或双方相性。

## 宿占日课与具体事项

### 钟时、星图与三类依据

- **钟时与经纬度门槛**：`suzhan` 的 `time` 可省略或传 `null`，仅算历法、日期候选及事项证据（`chart` / `astronomy` 为 `null`，`params.birthTimeImputed=false`）。已知钟时须同时传完整 `latitude` / `longitude`（`0°` 有效）才生成星图，缺项报错而不用默认地点或 0 点换取星图；旧连接尚要求 `time` 时不补时。
- **三类依据分离**：`sukuyo` 为农历历日，`calendar_day` 为黑白月日名与时段条文，`astronomy` 为七曜物理天文（默认现代距星视赤经不等宽研究口径，不称唐代宿界；`legacy` 为旧版等分黄道示意）。

### 活动视图与行为细节匹配

按发布的 `activity` 视图读取时，须同时保留：

- `sukuyo.calendar` 与 `sukuyo.calendar_day`：入月日、上下卷名称（`upper_name`/`lower_name`）及一般日类（`classifications`），不代补未计算的昼夜分时。
- `sukuyo.lower_methods`：下卷七宿性与七曜证言（保留火曜成亲／征债等相反条文，牛宿仅为参考表成员）。
- `sukuyo.personal_day`：本命到历日的有向三九（`personal_day.relation`）；无本命时不代填。
- `sukuyo.six_palace_reference`：原典六本命相对位置（命／事／意／聚／同／克第 1／10／4／16／20／13 宿），未给本命保留 `natal_mansion_required`；未评估七曜犯宿、六害或灾祸。
- `sukuyo.lower_mansion_day`、`sukuyo.conjunction_doctrine` 与完整 `sukuyo.activity_assessment`：事项、已确认细节、分层状态、`matched_rules/conditional_rules`、来源与适用范围。
- **行为细节（`activity_details` vs `effective_activity_details`）**：`activity_details` 只填当前聊天已确认且与 `activity` 同类的事实（如设学 `founding_school`、入学 `beginning_study`/`learning_with_teacher`、远行外国须同时 `long_distance_journey` + `journey_abroad`、`social_gathering` 与 `forming_friendship` 分开、月曜“私情出行”须明确 `private_journey`、日曜王公远行须 `royal_or_official_traveler` + `long_distance_journey`、启请法要须 `monastic_dharma_request`）。`effective_activity_details` 与 `detail_inferences` 明示行为分类推导（如还钱 `repaying_debt`、经书分类等），不把推导当新收集事实。
- **宜忌状态与同 run 完整上下文**：相互冲突的条文（`matched_rules` 内 `favorable`/`unfavorable` 并见）须说明各自条件、卷别与出处，不挑边合成“综合吉日”；`conditional_rules` 不计入确定汇总；未覆盖事项或 `not_evaluated` 不说成凶或无影响。同 run 核验须保留完整 `sukuyo.candidate_days`；衣事选 `activity=clothing` 及 `clothing` 卡并保留完整 `clothing_reference`（裁缝、制作、修理、穿着与穿新衣分别确认，`royal_wearer` 仅限明确王者身份）。

### 特殊日、昼夜与太白方位

- **太白方位（`sukuyo.taibai_direction_reference`）**：按 `calendar.lunar_day` 实际入月日查表（`location`、`horizontal_direction`、`realm`、`row_id`），保留八方、中央入地与天上（后两者 `horizontal_direction=null` 不补 0°），不将顺逆定为面向／背向或抵销宜忌。
- **昼夜条件与民用日界**：未进行原典平明八时分时计算时，不给出已核定的上午／下午或整天结论，也不填入西方 24 行星时；`weekday.basis=modern_utc_plus08_civil_midnight`（或日本 `modern_utc_plus09_civil_midnight`）按现代午夜日界计曜，不称已复原平明起算。
- **特殊日名（`special_day_labels` / `special_day_evidence`）**：分别列 `primary` 与 `comparisons`（上下卷大正校记），保留“冒、底”字面（`unresolved_rows`）与甘露学道限 `religious_learning`；仅按历日宿名查表，不称实测月亮与宿合。

## 新旧历与二十八宿名目的来源核对

- **《宿曜帳》117-20 与新旧历**：第 10—11 帧“无相違”论七曜直日，不等于月宿、全部历数或闰月法相同；第 17 帧“三月／昴畢并见”已由窄裁复核更正为“二月／即畢”，保留旧读作审查历史，不继续当原典异文。详细校读见[宿曜参考](../../sukuyo.md)。
- **日本近世历法与善通寺 109-4**：采用 NAOJ 日本历史宿主（`calendar_basis=japanese_naoj_historical_utc09`）时按实际 `calendar_system`、`calendar_backend`、`date_support` 及具名阴历时段解释。善通寺 109-4 题记与工作读法按[所选读录与前瞻文件](../../sukuyo.md)区分旧接纳片段与模型候选。

## 发送前核对

- **`directional_travel` 禁闭方向**：只有明确 `northbound_journey/eastbound_journey/southbound_journey/westbound_journey` 才适用，不从地点／GPS／角度猜或扩成斜向；四条具名禁向“纵吉时亦不可行”不被吉时抵销，壁宿南行相反条文与十／一／二宫校记并列保留。
- **终检与复核**：核对历日宿与天文月宿有无混用、主客方向有无颠倒、候选是否写成确定、原典冲突与时段条件是否保留。需要无损全量引用核验时首次即传 `include=["*"]`（不重算补齐）；`validation.calculation_layers` 标明实际计算层，自由文本语义仍须独立核对。更多见[算法、来源和未决项](../../sukuyo.md)。
