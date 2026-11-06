# 印占的计算事实与传统解释

适用于用户指定印度／吠陀占星、Jyotish、D9／D10 或 Vimshottari，或主题咨询确有新增价值的印占视角。先守[硬边界](safety-boundaries.md)及[本轮范围](consultation-routing.md)，不扩大用户所问主题。

## 选择与资料

本命用 `astro_india_chart`（或 `astro_chart` 的 `chart_variant=india_chart`，二选一）；达沙用 `astro_vimshottari`。已确认的公历出生日期、钟时、城市／位置与时区按实际 Schema 整理；未知生时不能猜。默认民用时刻，不沿用八字的太阳时默认。城市可由引擎解析，无需先索取坐标。

核心固定 Lahiri 恒星黄道与整宫制，`node_mode` 区分平／真交点，Ketu 与 Rahu 相对。显式旧式宫制／黄道覆盖仍可取历史参考，但 `india.status=configuration_not_supported` 时不能补写印占分盘。缺少星历时不以低精度轨道冒充分盘或达沙。

只有用户确认出生钟时的误差范围才传 `birth_time_uncertainty_minutes`；None 表示未评估。`changes_detected` 给出抽样中的分盘上升／落宫变体，`no_change_on_sample_grid` 不能证明整个区间绝对不变，也不表示出生时刻准确。用户不知范围时保留相关限制，不反复索取。

## 首次字段与解释

按已发布 `evidence_views` 复制 `fields`；卡名不是请求参数。设置 `strict_fields=true`、`include_snapshot_text=false`。完整 JSON／完整时间线首次 `fields=null`，从同一 run 的 `result_delivery` 取回，不重算或承诺摘要投影能恢复全文。

| 本轮任务 | 卡／工具 | 主证 |
| --- | --- | --- |
| 本命、做事特点 | `natal` / `astro_india_chart` | `india.charts.D1`、`nakshatras`、`topic_evidence.personality` |
| 事业结构 | `career` / `astro_india_chart` | D1 与 D10 的第十宫、宫主落宫、尊贵与实际 graha drishti；主题 factors 区分事实和传统含义 |
| 单人伴侣相处 | `relationship` / `astro_india_chart` | D1 与 D9 第七宫相关事实；D9 也涉及 dharma，不单独判婚姻成败 |
| 指定分盘 | `divisions` / `astro_india_chart` | 实际 D1／D2／D3／D7／D9／D10／D12／D30；D30只给星座与整宫，其余分盘坐标是线性显示约定；未计算分盘不能补写 |
| 阶段、目标钟时 | `stage` / `astro_vimshottari` | `current_major/current_sub` 真实起止、`birth_balance`、年长、`natal_ruler_context` 及对应本命结构 |

印占只用 `india` 内独立规则。顶层 `classical/aspects` 等西占字段为历史兼容参考，不能把西占入庙、容许度或现代星座文案归为印占。印占相位为所选整宫 graha drishti；本版不赋予节点相位／尊贵。旧 dignity 是星座层标签；D1 physical_state.degree_condition 另含 moolatrikona 度数、Baladi 与独立 Uchcha Bala（0–60 Virupa），须同步核对。任何分盘变换坐标不套用 D1 物理速度、燃烧或最高点距离。dispositor_relationship 是有方向的星体关系，不当作人的友敌。完整 Shadbala、其他作者的燃烧规则与复杂 Yoga 未验收，不从解读补齐。combustion 是 Santhanam 第 7 章注释表的角距条件，核对 source_layer=translator_commentary、方向、阈值及 boundary/ambiguous；不直接当作真实可见性、现实失能或所有 Yoga 已失效。

`topic_evidence` 中 `engine_facts` 是计算，`traditional_meaning/factors` 是有来源的传统解释；用户现实行动单独说明。不把入旺当能力认证、落陷当失败或术语连成必然事件。宫主联系可以讨论工作职责或相处议题，不由个人盘直接判断对方心意、信用与双人互动。

## 时间口径与来源

Vimshottari 以月宿为种子；次运从原始完整主运开始分配，不能把出生剩余主运重新均分。`year_basis` 的恒星年／365.2425 日固定年／360 日 savana 年不可混用。出生与分析时刻均须有效，DST 重复钟时用明确偏移消歧；日期级目标默认零点，年／月缺日的锚点见工具说明，不能称全年逐段已审。

`timeline_scope` 为目标所在 120 年规则周期，其第一段可从出生前开始；120 年不是寿命估计。阶段边界与出生误差敏感性不能包装成事件会在该日发生。`astro_vedicprog` 的恒星二次推运不等同于此达沙。

最终解释保留本次 `india.profile/ruleset_id/rulesets/rule_trace`，注明实际返回的版本与对应规则来源：[P.V.R. Narasimha Rao, Vedic Astrology: An Integrated Approach](https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf)，天文口径参考 [Swiss Ephemeris Programmer's Manual](https://www.astro.com/swisseph/swephprg.htm)。来源与软件数值对照不证明预测有效。

技术核对若读取到逐星 `physical_state.longitude_motion_context.continuous_frame_state`，它是同次原生J2000输入的连续框架对照，须保留自己的模型、速度来源与时间尺度口径。`status=partial` 时，完整框架项不等于完整物理视速度或已核定TT/TDB转换；其数值不替换D1主字段、顺逆标签、力量或主题事实。原生位置差异、精确恢复回执及不适用原因按返回解释。该局部限制也不抹去原D1已有依据。见连续状态接入审计。

其中月球的 `source_derivative_state` 是另行标识的源公式三维导数对照：它可含光行时与观测者导数，但输入原生轨道速度、加速度和物理时间映射仍有限定。按其实际 `status`、来源、固定基底及单位解释；`not_applied` 不补零，也不把 `partial` 升格为物理视速度、主顺逆或现实预测认证。参考与剩余门槛见月球源状态审计。

核对上升或时间依据时，可读取 `india.profile.earth_rotation` 与 `local_apparent_sidereal_meridian_degrees`。前者按实际返回说明UT1来源、TT政策、相位模型及精度限定；后者是赤经方向的当地视恒星子午圈角度，不是黄道MC。C04日值来源不代表应用了完整地球定向改正，不能将其升级为瞬时观测或出生钟时认证。公开参数是否可选C04以当前Schema为准，见印占自转依据审计。

当前度数条件与太阳角距采用固定的 R. Santhanam BPHS 卷一扫描本（序言署 1984，具体重印版次未确认）；角距表属于译者注释，不能冒充梵文偈颂本身，星体关系采用 Brihat Jataka / Aiyar / 1905 第二版 II.16–18；以 rulesets 的具体 source_id 与条文为准，不称全部原典已验证。ephemeris_policy=require_data_files 可拒绝后端降级；data_files_used 也不认证现实预测有效。

运行者选择strict_jpl时，读取physical_ephemeris_source.time_scale_policy及实际文件身份。原始DE441范围属于TDB，历史TT字段只是兼容别名；原生TT近似及源码估计不是新的观测精度界限。已核对的J2000正向与拒降级案例也不认证全部年代、Lahiri或现实预测，见严格JPL审计。

profile.time_scale_context 保留行星 TT、模型 UT1、IERS 表来源与到期假设；未来闰秒未知，future_leap_seconds_assumed_unchanged=true 不能写成精确未来时间已核定。Vimshottari 的 elapsed_time_convention 为 UTC 日历标签与每天86400名义秒，不把闰秒省略的微秒边界当连续原子时精度。

位置强度用 `strength` 视图，读取 `india.strengths.sthana_bala` 的逐项证据、profile 与生时抽样范围。五分量总量是 Sthana，不是完整 Shadbala，不转换为吉凶、能力或成功概率。`saptavargaja_profile` 只改七分盘分量：Santhanam 27 的逐字七盘 moola 星座读法与 Raman 30 的 D1-only 读法分别标明；Drekkana另由 `drekkana_profile` 选择，默认 `santhanam_27_6`，可显式选 `raman_36`；月／金与水／土的第二、第三段分组相反。两者取D1原始十度区间，不能取D3变换经度。Raman36详细条文与例12取15，摘要105取60的书内冲突仍在 `source_reading_conflicts`；选详细读法不代表整本通过。其他三分量保留已声明公式及来源。`profile_comparison` 固定当前Drekkana比较七分盘，`drekkana_profile_comparison` 固定七分盘比较Drekkana；不挑最高值，也不把两个比较轴拼成实际结果。实际解读引用本次选定口径，不能把比较项混成一套结果。D30 无唯一盘内度数时不补写角度、物理状态或未审断语。

运动力的主题事实按该宫主的`calculation_context.method_context`读取来源：太阳复用本次Ayana，月亮复用同一性质分支的Paksha；`cheshta_model`的全局选择不参与日月分量。其余五星核对`five_star_mean_model_applied`、`calculation_status`及`input_claims`，只有实际计算模型才有Simon已应用辅助来源。越界／未裁定不能写成已算，已算模型但角度中点未裁定也不能写成未选模型。同run依赖核对不证明整部原典、自由文本语义或预测有效。见逐宫主来源审计。

方向力和自然力的来源分别为Santhanam27.7和27.14，方向力用实际角点，不把整宫起点当上升/天顶。相位力独立采用Raman113–120有方向分段与附加特殊值，不能与整宫graha drishti混同，超过60的附加值不自行截断。`drik_bala.summary=null`须读取同run的scenarios和nature_context：水星关联判据未裁定，月亮相位边界也保留分支，不能当作零、挑较高分或转成概率上下界。`shadbala_assessment.total_virupa=null`时不自行加总、不称完整六力达标；Kala/Cheshta及来源分歧保留未完成。生时抽样的方向力和各相位分支范围不是概率区间。

相位力的`source_witness`与`source_reading_conflicts`保留固定页图核对及原书算例冲突；数值分支一致也不等于原书全部一致。例55对标准算例水星的负性质说明不能推广为任意盘的燃烧角距规则，不能自行补阈值来消除分支。相关宫主事实的calculation_context包含这些来源路径，按同run证据解释；见原书算例审计。

时间分量读取`kala_bala`的components、scenarios、missing_components及solar_context；这是出生时刻的本命时间力，不是analysis_year/as_of的运势。Natha按视太阳过中天，Hora按日出后等长平均小时，日主日出换日，岁/月主采用360/30日传统口径；不能套西占不等时小时或把缺失极地日出补成6点。月亮盈亏与Raman53第八日窗口存在作者内分歧，v6按moon_readings保留两种分类。星战读取yuddha_bala的scenarios、evidence与upstream_profile：v8按Raman76-77对本次已声明力量输入计算，固定盘面系数不是实际角直径，较小黄经胜不等于现实胜负。Kala与星战须沿同一月亮／水星分支解释；同经、黄经零点、多星同时交战或缺少前置力量的参与者仍未知，不当0。上游作者差异仍保留，不认证单一原典完整六力；Ayana固定常数的越界保留，不自行截断。Cheshta默认仅日月有值，五星平均模型未选择；明确需要五星深层计算时可选cheshta_model=simon1994_j2000，读取model_context的出生TT、共同J2000框架、平均／几何真位置、来源与逐星过程。只覆盖1900–2050出生TT窗口；它是独立现代长期平均模型，不认证Raman1900原表，不能把D1的Lahiri视位置、真太阳、速度标签或拟合／瞬时轨道根数冒充平均位置。越界缺失只约束该层，不否定其他已返回证据；生时抽样的模型状态变化必须保留。仍不补齐完整六力总分，不把条件分支、抽样覆盖或模型日出当现实预测成绩。来源及限制见平均模型审计。


名义盘与条件证据：先核对`india.reading_basis`。未给误差是not_assessed，不能自行补0；星宿／宿足候选来自同一UTC网格，不只看分盘星座。名义上升、月宿、达沙结果不能冒充整个生时范围唯一成立。`calculation_context`里的computed_consensus、conditional_results、unavailable、partially_computed分别解释，直接使用其同run分支数值和约束，不挑较高分支；全局component部分结果不自动外推到另一个宫主。没有数值不一概是用户缺资料，先区分未选模型、年代范围、未裁定规则及实际输入缺项。Vimshottari的requested/evaluated_sample_count和omitted_samples须保留，不把被略过的候选写成已覆盖。开发回归案例、结构化事实核验、独立模型输出审阅和独立现实事件验收分别报告，不能互相冒充。

Vimshottari v10：生时给定范围按同一最长30秒UTC网格读取 `stage_variants`，不能仅看旧 `samples` 端点／中心子集。完整网格计数与子集计数分开；目标早于候选出生逐点略过。同一候选运主的本命条件只用该候选生时的 `natal_ruler_contexts`，按 `sample_segments` 网格序号关联，不能拼接不同样本的有利条件；顶层 `natal_ruler_context` 只属名义盘。连续区段、相邻变化夹区及边界最小最大值均属离散样本证据，不表示精确生时、所有中间边界或事件日期。D30候选仍仅星座与宫位，不能补盘内度数。

v11物理时刻：印占`use_true_solar_time=true`只显示太阳钟，不重定位民用出生时刻。解释依据仍用`india`的实际UTC／TT盘面；`india.profile.clock_context.solar_wall_datetime`无时区，不当另一出生或分析时间。太阳钟显示跨日、跨年或数字落入民用DST缺口，不改变物理时刻或Simon模型窗口。用户资料若明确是历史LAT/LMT，不能用此开关冒充钟制转换，也不能凭拟合推断钟制；v12可明确选择civil/local_mean_solar/local_apparent_solar，不能把原始太阳钟当民用后开显示开关。

v12历史钟制：只有原记录明确为LMT/LAT才选择对应birth_clock_basis，保持birth_timezone省略、显示开关false；不能按排盘贴合度推断钟制。秒／微秒字段仅保留已知或模型数值，非原始记录精度证明。太阳钟误差区间读clock_interval转换前后端点与实际网格，不能按UTC对称分钟替换。目标民用时区用analysis_timezone；太阳钟出生省略目标时区默认UTC，应核对任务目标，不把UTC载体说成原记录时区。

太阳事件可用性分开核对：Dina／Hora需要当前连续日出对，Tribhaga只需要相邻且种类相反的当前昼夜端点。`solar_context.sunrise_day_status/active_arc_status`分别回显，不因缺不相关日落而抹去已有分量；也不因其中一组有值补造另一组。两组几何支撑都齐不表示所有分量已裁定。`solar_bracket_states_on_grid`为抽样覆盖数，不能当概率或整段稳定证明；力量解释的同run`constraints/context_paths`含该层太阳依赖状态，局部无值只限制对应星体及分量。

太阳事件序列不按每个UT1日期仅一个日出／日落假设裁剪；v15保留同一日界内的第二个同类事件。读取solar_events.enumeration时，1秒是检索防重复步长，返回的事件时刻没有平移；它不是出生资料精度或实测日出误差。完整事件软件对照仍不是人生事件或现实预测盲测。

## 星历来源与生时网格

v16的`india.profile.physical_ephemeris_source`按物理星体与坐标帧记录后端和观察到的文件身份；例如`by_factor.ecliptic_Sun`。Rahu／Ketu的分析或派生模型仍单独读取，不能借其返回标志认证物理数据文件。`atomic_file_read_proven=false / accuracy_certified=false`保留，文件标识不是天文精度或预测证书。

生时范围的`source_comparison`保留完整网格的来源引用及可比较来源。新增运动帧只在实际可用点比较，其年代窗口缺项仍单独解释；观察数不是概率。若实际返回`ephemeris_source_inconsistent`及`runtime.ephemeris_data/model_changed`等原因，应说明计算来源不可比较并先修复数据覆盖，不能描述为用户未提供生时、删掉相应样本、补成零或继续解释被拒绝的网格。名义盘、太阳事件的独立来源范围仍分别核对；本轮未证明完整文件读取集合、原典或现实预测满分。

## 显式太阳钟时的来源衔接

v17在`clock_context.source_comparison`回显原钟面重算、原始太阳来源与当前原生太阳的核验。`physical_instant_shifted=false`不是生时校正，0.0002秒是既有数值往返阈值，不是出生钟准确度。LAT的`input_clock_conversion.solar_source_comparison`记录实际迭代／最终／往返太阳调用及来源；新出现的辅助文件上下文不能补写成早先已读取。

`original_sun_identity_incomplete`仅说明旧对象的原始文件身份未完整保存，不能据此认证源文件，但也不自动否定其他已计算的盘面。LMT保留独立UT1／TT映射，不增加太阳星位要求；Delta-T与地球自转来源仍单独对待。实际返回`birth_clock_source_mismatch`或`physical_configuration_changed`时，先统一环境并从原始钟面资料重新解析，不能手改出生时刻、忽略错误或把失败解释为吉凶变化。来源相容与传统规则、独立自由文本审阅、现实预测检验分别验收，见修复审计。

实际原因为`position_motion_not_converged`时，是运动差分没有满足内部收敛线；不能自动解释为出生资料不足、文件缺失或人生事件不确定。补齐文件不保证解除数值收敛错误，应保留被拒绝状态并转工程核查。冻结验收快照中2400年连接处的两个建盘入口限制是预期失败，未计为准确度通过；其他已独立返回的有效层仍按其证据范围解释。

Delta-T／UT1来源仍有已复现的缺口：旧外部表或固定值设置可能影响上升，当前物理星历来源及complete状态不能排除这种运行时历史。若已确认有这类设置或可复现异常，应由工程入口核对新进程与实际时间来源，再从原始资料复算；不能让咨询用户补生时、改钟时或把差异解释为吉凶。普通新线程在本轮macOS与Linux绑定表现不同，不作为跨平台修复保证。调查和未接入的防护原型见Delta-T状态调查。

完整原生上下文：v18的`india.profile.native_execution_context`说明本次计算使用新exec进程及辅助时间文件的首末完整性核对范围。它解决共享进程的旧Delta-T／固定值污染；不是测得UT1、辅助表数值正确或现实预测有效的证明。当前选中的外部表仍会影响结果，不能把隔离等同于自动纠正运行者输入的表。参见修复审计。

v19可选太阳时显示使用记录时刻的共享TT／模型UT1与太阳时角，读取`clock_context.solar_display_context`核对实际来源。其`solar_wall_datetime`不带时区，`physical_instant_shifted=false`；不能将墙钟标签再作民用时间重排，不能把微秒格式当作出生资料或实测地球自转精度。SDK旧派生标签可以重算，已确认的记录钟时与物理UTC保持不变。

若共享速度证据返回`center_file_replay`，它表示辅助求导精确重现了原生中心状态的文件上下文；`center_files_*`是工程单元标签，不是太阳半径、传统吉凶等级或额外天文精度。结合实际`status`、收敛与来源字段解释；不得把重建文件状态说成校正出生时刻、完成生时反推或验证现实事件。

若`native_execution_context.compressed_file_endpoint_policy`有修正记录，先区分原生端点星位修正与后续保持传入中心的求导。`original_native_state/selected_native_state`说明计算上下文造成的数值修正，`selection_anchor_jd_tt`不是替代生时；按实际`input_instant_shifted`与原`julian_day_tt`核对。记录中的调用数和重复记录不是独立天文样本或预测命中数。普通木星／土星采用系统质心，不能将它们说成已计算另需旗标和卫星文件的本体中心；缺少对应层或错误时不补造。验收范围见端点上下文审计。

若`chart_profile.apparent_position_policy`把某物理天体标为`behind_solar_disc`／`virtual_continuous_solar_disc_extension`，它是模型太阳内部的虚拟方向，不是已证明可观测的星位；即使与另一软件残差低于阈值，也不认证实际观测精度。不得把未返回该分类当作已排除这一状态；独立印度／达沙输出对此层的直接提示仍待完善。

v2私有坐标来源：以`india.profile.native_coordinate_contexts`逐项核对原TT和实际帧；`original_native_state=null`／`native_state_changed=null`表示没有先计算不可信的旧目标，不能解读为旧星位精确保留或已量化其变化。`native_execution_context`中的修正计数可包含预选太阳，不是不同出生或事件的数量。原生日出搜索和第三方直接调用仍不是逐点认证的范围。

印度／达沙已直接返回`india.profile.apparent_position_policy`与D1逐星`native_position_interpretation`；达沙同生时的运主分组保留其离散含义。读到虚拟方向仍可解释本次数学坐标下的传统规则，但不得说成可观测星位已获实测认证；不能把该物理含义搬到D9／D10的盘内坐标。不同样本的区域变化须保留，调用数、分组数、数值一致性均不是预测命中率。
