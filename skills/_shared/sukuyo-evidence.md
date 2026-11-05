# 宿曜与宿占取证

只在本轮实际使用宿曜／宿占时读取。以工具当前公开Schema和同run结果为准，计算由引擎完成，不能用星图或模型重算本命宿。

## 双人相性

`sukuyo_compatibility`默认用固定UTC+08现代中国农历月日及T1299下卷十五日望宿逆顺法。可明确选择calendar_basis=japanese_hutime_1002_1_utc09：HuTime 1002.1冻结逐日参考，范围1872-02-09至2031-01-22，固定UTC+09。宿主历法、出生时区、calendar_profile及物理星图分别保留；不能因选择日本参考便猜出生时区为东京，默认出生时区仍为+08:00。双方共用一套basis，范围外不能改用中国历补齐。

日本参考须读取calendar_reference的来源类别、支持范围、数据指纹及资料差异。出版方2015年起的区段标作参考推算，不称已核对逐年神宫原刊；UTC+09是明示参考日期政策，不是历史日本地方时复原。旧月度候选资料仍被拒绝；新后端由完整逐日记录派生，保留1989月度结束边界的差异及文档到2033与实体到2031的不同范围，不把739个范围外空响应删掉后称全资料通过。

另可显式选择calendar_basis=japanese_naoj_historical_utc09：NAOJ冻结月首参考，前推公历0001-01-01至1872-12-31、固定UTC+09。不能因地点或出生年代自动选择。453阴历年及以前为儀鳳暦平朔回推；454起也须区分具历史校正的参考、实际颁历与当时钟时。阴历年0是来源字段，不是公元0年出生输入。1872年旧历十二月因改历只保留两天，1873-01-01不能续算旧历或自动切换现代后端。

历史参考的calendar_reference.cross_source_comparison逐日保留HuTime1001.1不同月日／闰标志，control_applied_to_primary=false。全域有210个分歧日期，两个来源部分共用历史文献；即使宿名相同也不能隐去月日分歧，不能称完整历史历法已获一致或独立证实。固定UTC+09和前推公历标签是明示计算政策，尚未复原历史地方时、平明日界或唐代颁历。

公元1年的固定时差date_support可出现0000-12-31来源分支或UTC端点。它是天文年编号的区间标签，与epoch秒一起保留，用于判断范围外候选；不表示支持公元0年出生、真实历史UTC或已知生时。范围外分支仍使候选不完整，不能删掉后宣称唯一宿。

单一历日的 `profile_calculation.host_calculation`同时返回生日加十三含首位法，两法互核；NAOJ朔日宿表是配宿表参照，日本逐日日期另有1872年327天的独立对照，不能混称全日本历已独立验证。未知时间不填0点或中午；其他时区当地日期可能对应多个所选宿主历日，读取 `date_support`及各 `calendar_candidates`的完整历法与条件关系。经纬度不参与该算法。

`date_support.utc_support_intervals`是当地日期所有可能时刻的范围，不是实际出生时刻；POSIX民用秒数不是概率或含闰秒的物理时长。夏令日可能23／25小时，政治回拨可能令同日47小时；不擅自按24小时或最多两个参考历日解释。条件关系逐行保留日期来源，未定主关系不能从某一行挑选。完整候选同宿时只确定宿和关系，唯一历日与出生钟时仍未定；范围外分支或闰月政策未定不能因已算分支同宿就宣称完整。已知不存在／重复钟时及整天跳过的当地日期仍须核对。

首轮按问题选发布的 `relationship`或 `calendar`视图字段；核对 `status`、`person1/2.calendar`、各自 `natal_su27`、两个方向及 `rulesets`。视图名不是请求参数。`su27_basis`是算法版本，`pair`是界面配对类别，不能说成双向综合得分。`sequence_group`是三九组序，`distance=null`不能补为近中远；结交条文不能泛化为必然婚姻或人格结论。

默认档案闰月 `unresolved`时保留已算出的农历、已确定一方与候选宿，只限制未定关系；同名月候选不保证穷尽。`repeat_month`是明确选择的同名月约定，不声称T1299已给出唯一规则。`source_table_variant`逐个输入保留大正藏印本28宿月建表；其中含牛且可能与27宿结果不同。它既不是本次已应用的三九宿，也不是月亮实际天文宿位。不要为消除差异自行替换算法。

可选 `calendar_profile=hinoo_t1299_host27`把《桧尾口诀》的闰月复用和小月缺日补配应用于所选宿主历法，默认现代中国历；不等于复原唐历或完整历史日本历。初一前/后半候选不同时，必须明确原典半日参数；已知出生民用时刻也不能自动推成某半。闰月与小月规则次序有歧义时保留现代重建候选，不能说成原典明载两种算法。`candidate_relation_analysis`交付已列候选各自的双向关系，`applied_to_primary=false`；不得挑某一行作确定相性，排列也不是优劣排名。

`profile_calculation.source_bundle_sha256`与其host_calculation、缺日计算的同名字段，是同次加载的规则JSON指纹；原文件指纹另见source_sha256。Hinoo的active_primary_evidence指向downloaded_primary_edition，交付直接下载SAT完整HTML响应指纹、两段原文和五条校记；完整响应不等于原抄本、嵌入字图全部取得或影印校勘。原本与甲本的书目、异读分别保留，不合成唯一正文。旧cached_primary_excerpt是历史缓存摘录，末句人工句号与新原文闭引号的差异明示，其摘录哈希仍不是完整底本哈希。闰月段“其正月”是相对闰月的本月，不是所有闰月都重用农历一月；小月段“假令正月”则举一月为例。半已上／半已下与星／室原字差异继续保留，不据摘录补现代钟时。两个望宿算法共用同一锚点表，互相一致不能代替独立原典或历表核验。

Hinoo另返`critical_calendar_reference.image_witness_research`时，按其中冻结采集时间解释已取得资料：真福寺034／035的历法段已定位，但卅日室及两半句未作最终接受；名古屋上下卷异版及古写本说分别归属馆方著录和据序转述。天文台旧入口11张2500像素图不补新版缺069，也不满足原尺寸要求；旧078字数首读与更正只限该图，不改NAGO075。保留曜／曉、西／酉及上卷十宿／歌诀九宿层次，不把研究参考当作已经应用的新历法、半日钟点或补配优先。需要展开逐字对照时再读取所列来源命名空间和首读证据，不把选录片段说成完整定本。

## 十二宫分足查表

`palace_reference`仅以本次历日宿名查T1299上卷的108足表；宿占在sukuyo内，双人在person1/2内。`textual_pada`或person1/2_textual_pada是显式查表条件，不能因已知出生钟时或现代月亮位置而补造。未指定足序保留四足；翼等跨宫宿保留多宫。某宿四足同宫时可仅确定表内宫名，不等于排得足位；历日宿候选未穷尽时，即使已列候选同宫也不能选定唯一宫。

宫序第一为师子，不是House1；牛宫也不是牛宿。太阳分/太阴分为原典分区，不能当昼夜生盘。`birth_pada_established=false`及未给历史黄经原点时，不得将查表宫名解释为实际本命宫、实测月亮星座或据此合成双方相性。逐足序号是沿原文宫序展开的明示约定，原文列的是各宫所占足数。

## 宿占日课与具体事项

`suzhan`的time可省略或给null：沿用已确认日期和输入时区，计算历法、日期候选及事项证据；chart、astronomy保持null，params.birthTimeImputed=false。缺钟时不计算宫位、瞬时天文28宿或角距tithi；经纬度、宫制及盘式选项没有用于历法层。已知钟时仍可生成完整星图，不能用默认、示例或0点换取星图。先核实际公开Schema；旧连接尚要求time时不要补时，改用已更新接口或完成客户端重连。

`suzhan`把三类依据分开：`sukuyo`为农历历日，`calendar_day`为黑白月日名与时段条文，`astronomy`为七曜物理天文。默认天文是现代距星视赤经不等宽研究口径，不能称唐代宿界已经复原；显式legacy方法是旧版等分黄道示意。

活动按发布的 `activity`视图读取，必须同时有：

- `sukuyo.calendar`和 `sukuyo.calendar_day`：日名、上/下卷名称、一般日类、昼夜限制及差异。
- `sukuyo.lower_methods`：下卷七宿性及七曜证言，与上卷分别保留；火曜成亲、征债等相反条文不能只选一边。轻宿标题軫／輕与急速卖／买卖校记保留，当前下卷选大正主文，不擅自混用明本扩大购入范围。牛宿仍仅为参考表成员，不能补进27宿历日。
- `sukuyo.personal_day`：本命到历日的有向三九；没有本命时不能代填。
- `sukuyo.six_palace_reference`：原典六个本命相对位置，命／事／意／聚／同／克分别从本命本身计第1／10／4／16／20／13宿。未给已确认本命时保留natal_mansion_required，不以历日宿代填；不随目标日期改变。seven_luminary_transits_evaluated及三九参断evaluated仍为false，不能据此称已发生七曜犯宿、六害期间或现实灾祸；此六宫宿与十二宫分足分别读取。
- `sukuyo.taibai_direction_reference`：下卷太白所在章按calendar.lunar_day实际入月日查表，不能改用公历日、tithi、Hinoo补配宿序或实测金星。八方、中央入地与天上分别保留；后两者horizontal_direction=null，不能补0度或说成北方。明本校记删去初十、二十、三十的天上行，row_deleted_in_apparatus仅表示该见证缺行，不能说成没有太白、无影响或可以行动。明本只是所选底本校记的重建，尚无独立明刻本校勘；返回大／太、正南等字面与两数据库的校记差异。movement_alignment_evaluated=false、applied_to_activity_assessment=false时，不能把顺／逆擅定成面向／背向、顺时针／逆时针、天文顺逆行或GPS方位角，更不能抵销既有宜忌。未知历日的每个candidate_days另保留条件参考。
- 衣事选`activity=clothing`及发布的clothing字段卡。裁缝、制作、修理、穿着及穿新衣分别确认；仅裁缝推制作、新衣穿着推穿着，不能反向推断，也不以衣事代替买衣。`royal_wearer`仅为明确王者身份。`clothing_reference`保留主文十四宿正表与“余并失”补集，明本校记“井→并”“余并失→并大吉”另列；不补并为井或给明本未列宿补入同样忌条。专章口诀和上卷裁衣原句没有进入事项汇总，必须同时说明，汇总列宜不等于全部文献一致，更不据原句断言现实疾病或灾祸。完整半日候选共同的专章表项可单独成立，宿名仍未定；候选不穷尽则不据单候选定宜。
- 同run上下文核验v4要求完整`sukuyo.candidate_days`，单一历日为空数组。公开`suzhan`的未知时刻日期分支条文须全部保留；time省略/null后同时读取各candidate_days及其candidate_mansion_days，不能为取得星图或通过检查补钟时。衣事还须完整`clothing_reference`，通用activity主题也不能省略该见证。

- `sukuyo.lower_mansion_day`及 `sukuyo.conjunction_doctrine`：逐宿条文与文本问题，宿月配合的文献分组不可冒充实际天文月亮。
- 整个 `sukuyo.activity_assessment`：事项、已确认细节、分层状态、全部 `matched_rules/conditional_rules`、来源和适用范围。

`activity_details`只填当前聊天已确认且与activity同类的行为事实。设学对应founding_school，入学受业可匹配beginning_study或learning_with_teacher，技艺学习对应skill_learning；不能把这些都推成所有考试适宜。借入、出借、买卖、经营、索债、远行、南行等分别由引擎匹配；purchase为购入，business_operation为明确经营，collecting_debt只对应债款催收。远行向外国需同时具备long_distance_journey和journey_abroad，不能只给其一；any_of任选其一，all_of须全部具备。普通出行不能擅加远行限定，上下卷不同范围按各自原文保留；不因想得到某个结论而补条件。`conditional_rules`是细节未定或读法未校定的条款，不计入当前汇总；`conditional_only`也不是已核定宜忌。未匹配的细节不能当作已被否定。

`favorable/caution`描述所列文献条文。`conflicted`表示已匹配证据兼有宜与忌，必须说明各自的动作条件、卷别和出处；不同动作的宜忌不自动等于同一条件下原文自相矛盾，不能挑一条、按票数或自行设权重合成“综合吉日”。`uncovered`是该项未覆盖，不能说成凶；`not_evaluated`是对应层没有输入，不能说成无影响。日名“得财”本身不等于所有交易都宜；建宅也不自动等于迁居。

社交聚会social_gathering与明确结交交友forming_friendship（不限首次相识）分别匹配；不能因参加已有朋友的聚会便推断要结交，反向也不成立。下卷月曜“私情出行”只按明确private_journey匹配，不由personal_departure本人启程、远行、方位或使节任务推断因私；未声明因私也不证明公务。下卷日曜“王公百官等东西南北远行”同时需要royal_or_official_traveler及long_distance_journey，出差或diplomatic_mission本身不证明原文行旅身份。上卷远行未加相同身份限定，继续分别保留；上卷月曜主文“私精”未默改为下卷“私情”补规则。

有本命宿时，`personal_day.source_day_evidence`逐条保留上卷、下卷及下卷“又一说”。危／坏的远行条文需明确long_distance_journey；又一说的“不得进路”按personal_departure匹配；下卷安日“远行人入宅”另需long_distance_traveler_entering_residence，不因入宅便补造启程或本次远行事实。荣日启请法要须明确出家人身份与动作，使用monastic_dharma_request；religious_learning本身不证明出家人身份。前者可归入宗教学法，不能反向推断。下卷“己身三九若吉”优先说明也交付，但其“长行历”覆盖范围尚未核定，`priority_clause_applied_to_aggregate=false`时不能据此删除相反见证或把危日婚姻改判为吉。

`calendar_day.clock_evaluation_status=not_computed`时，原文“昼／夜、日中／夜半”的条件尚未映射为民用钟时，不能给出已核定的上午／下午或整天结论。两卷偈文一夜的字面保留，0393c26下卷夹注明确释为十一夜。读取 `verse_abbreviation_resolution`及 `prose_verse_time_semantic_conflict`，不能把省文再断成初一夜限制或未决冲突；上卷同偈的释义另标平行散文互证。通用日类、事项和时段限定分开解释。

`calendar_day.clock_doctrine`说明所选原段平明起曜、昼夜各八时；逐时曜神序列未逐项列出，不能填入西方24行星时序列，原文的确定性断语不是实证验收。

`effective_activity_details`与 `detail_inferences`明示行为分类推导：购入金宝／牲畜、田地购入／出售、出售哺乳牲畜和骑乘学习可归入对应买／卖／技能；`activity_details`保留用户已确认细节。不要把分类推导当新收集事实，也不由此补远近、方向、付款、现金流或开始时间。还钱需repaying_debt，不能以returning_property替代；研读经典、教授经典、学论辩及宗教学法分别为classical_text_study、teaching_classics、debate_learning、religious_learning，原文经书不任意限为宗教典籍。

`weekday.basis=modern_utc_plus08_civil_midnight`或显式日本参考的modern_utc_plus09_civil_midnight只是所选民用参考日界；`classical_daybreak_boundary_acceptance=false`时，不得声称已复原原典平明起算及昼夜各八时。半日、候选与闰月政策照常保留，选日本参考不能自动解决这些原典条件。

`special_day_labels`仍按上卷大正主表；`special_day_evidence`把上下卷大正与各卷所载明本校记分别列出。明本表是同一底本校记的重建，不是独立明刻本校勘，也未替换确定事项。下卷大正“冒、底”未默改为胃、氐；`labels_complete_for_selected_day=false`时，空匹配不表示无此特殊日。未定字对应的不利规则保留在conditional_rules，不因已有宜条而丢掉。甘露学道／经法限明确religious_learning，不能用于一般学习或考试。下卷“月与宿合”仅以历日宿名查文献，`physical_lunar_conjunction_evaluated=false`时不能称已测定月亮与物理宿合；`unresolved_source_rules_present`须与正反证言一起说明。

先回答所问事项，再用两三项计算事实及对应条文说明。比如危日婚姻有互相矛盾条文，应直接呈现冲突及其出处；现实安排另依据双方意愿和实际条件讨论，不把文献标签转成成功概率。

## 新旧历与二十八宿名目的来源核对

用户问《宿曜帳》117-20或新旧历方法时，可参照[所选页校读](../../docs/sukuyo.md)。第10—11帧跨页的“无相違”论七曜直日，不是新旧历的月宿、全部历数或闰月法相同。正文另比较旧历二十七宿和新历二十八宿，小字又存异说；这些是本册主张，未认证全部历史历本。

本册所述逐日二十八宿、T1299上卷月日二十八宿表、现代距星不等宽天文二十八宿以及legacy等分示意不可互换。现有`mansion_method`不能冒充本册新历排法，参考历法范围也不能证明古代平明、桧尾半日或闰小月先后。图像全部取得、数学相容、同提供方模型首评与原典定本、历史观察和现实预测效力分别报告。

校读涉及小字时先区分正文、干支旁注、返读记号及补写，不以历算吻合度选字。第17帧“三月／昴畢并见”的首读已由窄裁复核更正为“二月／即畢”；保留旧读是审查历史，不继续把已排除误读当作原典异文。仍未校定的字与小注则继续保留，不因一处改正宣布全本无误。

## 日本近世历法的名称与置闰比较

采用NAOJ日本历史宿主且实际返回`calendar_reference.edo_calendar_method_reference`时，按该对象的实际阴历年和具名时段解释，不由宝历、寛政等年号或公历年份推断历法。宝历三、四年仍属貞享暦；公历1755年初可能仍属阴历1754年。来源的夜半注法不等于宿曜平明或桧尾半日。

`intercalation_research`保留内田论文全十行以及作者提出的三例，表3另一月名是规则闰月的翌月。不能只取三例拟合普遍时刻规则，也不把作者判断改成本次宿主月号。`reform_month_length_reference`保留1872十二月原定大月与改历覆盖两天的30／2差别；两种单位不改标相等、不延长已停用日期。完整来源与边界见[近世历法资料](../../docs/sukuyo.md)。

核对善通寺109-4的题记、历法疑字或前瞻取证时，另读[所选读录与前瞻文件](../../docs/sukuyo.md)。旧接纳片段与新增模型也／己形、被／彼、改／放形工作读法分开；没有定字、实物年代或谱系证明时，不把新读录当已校改原典。目录“閏月小月宿”、仪轨“時”字及“七日等不解界”条名均不能裁定钟界或规则优先。

## 发送前核对

`directional_travel`是下卷行动禁闭法按明列日宿查方向的证言，只有明确 `northbound_journey/eastbound_journey/southbound_journey/westbound_journey` 才适用；不从出生地点、GPS、目的地或角度猜方向，不扩为东北等斜向。四条具名禁向的“纵吉时亦不可行”不能被吉时抵销。壁宿南行在逐宿章与方向章有相反条文，须同时解释；第十摩竭、第一羊、第二牛宫的大正凶／明本吉校记分别保留，不拼成一致判断。宫名及序号只属本段查表，不等上卷足表宫序、本命宫或现代宫位；未识别的互不猜成氐，明本移入的尾不混进大正主文。`directional_travel`的候选行不代入确定事项，未列方向也不表示已获允许。

核对实际历日宿与天文月宿有没有混用、主客方向是否颠倒、候选是否被写成确定、原典冲突与时段条件是否保留。需要回执级引用核验时，首次 `fields=null`、`include_snapshot_text=true`取得完整业务结果；超限读取同run全部分页并核对哈希，不能用摘要重算补齐。`validation.sukuyo.verify_sukuyo_context_claims`检查完整回执及必要的整段结构化上下文；通过仅表示上下文引用完整，自由文本语义仍须独立复核。不能把字段检查通过写成解释忠实度满分。

[算法、来源和未决项](../../docs/sukuyo.md)。
