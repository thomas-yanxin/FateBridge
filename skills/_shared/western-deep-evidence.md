# 西占深层证据按问题读取

这份参考供用户明确追问古典条件、关系方向、中点／映点或特殊配置时使用。普通主题先按[西占主题参考](western-topic-evidence.md)取证，不为覆盖工具而展开本页所有分支。位置计算交给引擎；传统含义用已核对的作者或知识条目，新增解释与引擎原结论分开。

工具发现中的 `example_input` 仅为虚构的合同与传输演示，旁列 `example_context.fictional=true`、`use_as_user_default=false`；不能补入用户未提供的出生或问事资料。需要完整交付时沿用同 run 的 `result_delivery`：紧凑引用可能省略 `first_page_uri`，先读取其 `manifest_uri`，核对结果 ID、原 run 和长度，再沿 manifest 的分页地址读取全文；需要完整性核对时使用结果核验入口；不能用另一次计算替换。这些示例只用于接口和传输检查，不作为原典或现实预测证据。

东方／西方先读 `classical.orientality_policy`；Ptolemy层单独保留同名政策。当前按已给定黄经的精确数值分类，不用0.0001度死区吞掉非零角距；水星的实际阶段继续传到昼夜归属、得宗派和halb。它是黄经阶段，未求解物理升落或偕日可见性。精确合相留未知；精确对分沿用共享层的东方端点约定，不据此宣称Lilly分别描述的上行星／月亮端点已经校定。Lilly原例3／7及其他未通过门槛保留。

宫头反序、折返或非常接近时，连同 `house_axis_convention` 读取同run的 `house_position_projection`；预测合同在对应 `calculation_basis` 下读取。R／C的 `precision.checks` 并列实际输入热带黄经、原生值、交付值、工作精度和修正方式。预测模块的派生角点与宫头在显示转换前保留原始热带投影输入；不要从恒星黄道显示角度反加偏移去替换记录输入。它按黄纬0°的几何平面复核，不能解释成计入真实黄纬的空间落宫；0.001″是声明的相位边界余量，不是占星容许度。交付值可能不同于原生的黄经邻近宫头吸附结果，不能用原生值覆盖；字段中的物理误差未知仍须保留，检查行数与重复输入不是预测样本数。R的地理极点状态 `native_geographic_pole_convention_not_requalified` 只保留原生约定，不表示已校定唯一几何分宫。

T投影的 `fatebridge_topocentric_zero_ecliptic_latitude_v1` 按实际纬度求解位线，已替换原生逆算中±89.999°的纬度钳制及旋转纬度残差停止条件。以实际地平半球和东西分支选支，读取每条 `precision.checks.topocentric_branch` 的实际纬度、所选根和全部该物理象限内的候选；候选不止一个时必须说明选支约定，不能说几何唯一。交付相位采用明确的前移0.001″政策，区别于原生的黄经宫头吸附；不要拿原生整数宫头覆盖交付宫号。精确地理极点仍是另列的原生极限约定，未计作独立数值通过。这里只修复实际选用的T投影，顺行宫头采用黄经区间的既有选择仍保留；黄纬仍为0°，不能解读为含星体实际黄纬的空间落宫，也不能称Polich／Page原典全套技法已通过。分支定义见[极区天球四轴与制宫分支](../../docs/western-astrology.md#极区天球四轴与制宫分支)。

黄道与地平面近重合时，按实际 `angle_definition` 区分高度敏感的交线与数值未解析的后端约定；已作高精度复核仍不能消除出生时地与角度模型误差。Placidus的 `house_cusp_scope` 若为 `placidus_horizon_endpoints1_7_checked_intermediate_native_time_fraction_cusps_retained`，仅表示ASC／DESC端点已复核，中间半弧宫头保留原生结果。不能称为全套Placidus原典认证，也不能因另一软件固定迭代输出不同而直接改盘；原始失败门槛和Lilly原例未通过状态继续保留。

数字 `hsys=6` 是Topocentric（T），不是Campanus（C）；当前本命数字入口0..8不含C。C在支持 `house_system="C"` 的预测合同中另行核对，不能靠改称6补成支持。此前协议覆盖标注的更正记录保留，依据实际返回的 `house_code` 和方法标识解释。

## 本命中的古典细问

`classical.source_profile=mixed_dorothean_egyptian_lilly` 表示多来源组合，不能整体归给某一原典。点名 Ptolemy 时读 `classical.ptolemy` 的作者、Robbins 1940 版本、`chapters/status` 及实际星体关系；目前覆盖 I.7、I.13–19 与 III.10 的福点算式，恒星黄道不适用。I.18 水象为火星主掌，并列昼金星／夜月亮共治，不改写成 Dorotheus 三分表。`classical.ptolemy.lot_of_fortune` 按 Robbins 主文昼夜同用 `ASC + Moon − Sun`，与原有混合传统夜盘反转的 `classical.lots.fortune` 分别解释；核对实际 `formula/longitude/source_url`。不补原典未返回的界表、擢升度数或寿命判断。`astro_chart` 公开的 `evidence_views.ptolemy` 可按需取此层。

昼夜由太阳中心真实地平高度确定，整宫第1／7宫不能直接决定昼夜。核对 `chart_profile.time_scale/horizon_method/sect_convention`；未来闰秒沿用假设见 `future_leap_seconds_assumed_unchanged`。普通西占保持民用钟时默认值，不能用真太阳时重置追求“更准”。`interpretation_evidence` 是确定性现代象征模板的依赖路径；需要时绑定同 run 原始回执核对，不能当成 Ptolemy 原文或现实预测证明。范围和来源见[西方占星验证说明](../../docs/western-astrology.md)。

原典的 `classical.ptolemy.sign_relationships` 依据 I.13–16，按星座关系返回相位、命令／服从、相互注视及离隔；I.16先排除其他亲缘关系。现代度数相位另看 `chart_profile.aspect_policy/aspect_evidence`，不把两层相位名称直接互换。`interpretation.original_text_relations` 为原典关系说明，其余现代模板有各自 `policy_id`。元素／模式并列、南北交点不计入本体统计的口径都应保留；最小偏离度不称为最强相位。

日月返照取分析时刻之前最近一次，读取实际 `return_datetime/return_datetime_utc/solver`；`residual_arcseconds` 表示数值零点残差，不能当成现实事件时刻误差或预测置信度。推运的 `calculation_basis` 交代实际星历与时间尺度。半弧主限在恒显／恒隐点无定义时应保留错误，不由模型替换纬度或制造落点；已有近似方法标签继续保留。

与外部星历比较时，先核对TT／UT1与UTC标签、地心／站心、视位置约定、坐标框架及本体中心／系统质心。不同框架或不同参考点的数值差异不能直接当作历法计算错误；相同条件下有限样本通过也不代表所有历元或现实预测通过。保留实际版本和首次差异，不由模型旋转、平移或更换星体目标来配平。方法见[参考点、模型与日速来源](../../docs/western-astrology.md#参考点模型与日速来源)。

后端核对不能只看 `FLG_SWIEPH`：已核对的原生 `sweplan()` 在缺少月球文件时可用Moshier月球把地月质心换成地球，而顶层仍返回SWIEPH。地心物理坐标须连同实际行星／月球文件覆盖核查；`swiss_dependency_unavailable` 是来源错误，不是没有天象、没有事件或事情不成。修复统一入口后仍保留明确的Moshier对照、解析平交点／平远地点及不依赖该月球输入的参考原点，不把顶层标志当作完整读取证明或绝对精度认证。

核对私有原生上下文时，预检原点看 `preflight_reference_origin`，目标实际原点看 `coordinate_reference_origin`，不能将二者互换。模型探测坐标丢弃后重置缓存，不作为新增物理观测；站心标志可能覆盖请求中的日心／质心位，来源资格按实际返回标志核查。`coordinate_is_defined_zero=true` 是原生参考恒等式，不是测得的太阳／地球位置，不能从零向量推断其物理矢量文件已被读取。

西占请求可显式传 `ephemeris_policy=require_data_files`；本命、关系盘、推运、卜卦和择日的已观测物理坐标及太阳钟／抽样调用均拒绝解析或轨道回退，默认 `auto` 保留实际可用模型。严格请求成功后，可取 `evidence_views.data_files` 的 `fields` 读取 `ephemeris_data_policy`；视图本身不会设置输入政策。核对实际模型、文件名称与版本、零向量和私有进程回执，不能把调用次数当成独立天文或现实观测。组件原有的局部 `auto` 参数保留，其上仍受本次严格准入约束。日出／日落仅探测查询与返回时刻，原生求解内部读取尚未完全可见；恒星目录公式、虚星轨道、解析交点和地球自转另列，不据此认证绝对精度、整部原典或预测能力。果老暂不支持该西占选项，印占沿用其既有政策。支持范围见[星历政策](../../docs/ephemeris.md)。

首次调用前按问题在工具公开的输出合同中选择下列业务字段；普通摘要仍严格投影、关闭快照。工具公开的 `evidence_views.classical_detail/fixed_stars/planetary_hours` 是对应按需字段卡，复制其中 `fields`，卡名不是请求参数。下表路径是解读索引，不是新增输入参数。先复用已保留的同 run 结果；投影曾排除某层时不能靠分页补回，也不能在用户要求不重算后另排一张盘。

| 触发问题／何时值得加 | 实际读取 | 新增信息与解释边界 |
| --- | --- | --- |
| “福点和精神点有什么区别？”或明确要古典资源／行动视角 | `classical.sect`、`classical.lots.fortune/spirit`，相关 `classical.planets` | 核对实际昼夜公式所得经度、星座、`dispositor/almuten`，再解释两点在所选传统中的不同角色。它们不是财富金额或意志力评分；本分支未返回点的宫位／相位时不由模型补算 |
| 明确问婚姻点／子女点 | `classical.lots.marriage/children` 及所涉星体条件 | 只作该版本点位与定位星的文化参考，不替代真实双人互动，不推断配偶身份、孩子能力、数量、生育结局或寿命 |
| “命主力主为何是这颗星？”“与上升守护星一样吗？” | `classical.almuten_figuris.winner/totals/points`、`classical.topic_almutens`、`classical.planets` | 命主力主是本工具对实际纳入点的尊贵加权汇总；逐点贡献和缺少的点都要保留。它与上升守护星、某宫宫头力主是不同规则，不把最高分星当成整个人的唯一性格 |
| 用户问产前朔望／为何参与命主力主 | `classical.syzygy`、`classical.almuten_figuris.points` | 核对实际返回的朔望类型、`julian_day`、经度及参与情况，再说明所选传统怎样使用它。`null` 表示本次未提供这一层，不猜朔望，不因此否定已完整的其他点 |

朔望的`ephemeris_source`描述整次搜索及显示调用，出生历元的`chart_profile.planetary_models`不能替代它。`models_stable=false`时须说明搜索或显示发生星历模型切换；有效结果仍保留，但不声称来源一致、根附近连续性已证或残差等于天文精度。调用次数、文件名称和模型名称均不是独立观测或原典验收。来源完整性错误不能解释为“没有出生前朔望”。

朔望的日期表示另读`utc_representation`。`datetime_representable=false`只限制Python日期载体；实际返回的TT／UT1、经度和总主星参与点仍应解释。扩展标签中的天文年0对应纪元前1年，不是公元1年，也不扩大出生输入范围。`event_datetime_utc`是标签字符串，可能含扩展年份或闰秒；历史调整时也可能没有唯一民用标签。1960年前UTC命名的历史载体按模型UT1读取，不冒充原子UTC；日期显示限制不等于没有朔望。
| 明确问恒星合某星／角度 | `fixed_stars`、该点实际落点及 `chart_profile.fixed_stars` | 先核对实际 `status/model_id/julian_day_tt/longitude_frame/orb_limit/earth_ephemeris_model`，再逐条读 `star/cn/point/orb/star_longitude/star_latitude/nature_components`。当前生产层以20颗SIMBAD ICRS星表观测量传播自行、视差与径向速度，再计算本次地心视位置；不能说成仅用固定黄经线性岁差推进。合相只比较同黄道黄经，黄纬不参与命中，因此不是球面近合、掩星或赤纬平行。`status=unavailable`的空表表示未计算，`computed`的空表表示本次目录／容许度内无命中；均不代表完整天空。最紧一条未必最贴主题，不把传统星性当灾祸事件 |
| 明确问出生行星日／行星时 | `planetary_hours`、`person_info` | 读 `is_day/day_ruler/hour_ruler/hour_number`，这是按出生地日出日落划分的不等时辰。缺星历或极昼夜可能为 `null`；不改用民用整点凑一颗主星，也不把出生行星时说成未来活动的吉时 |

对资源、关系等普通问题，只有这层能补独立信息时才取。气质／身体部位的传统对应不作为诊断或器官状态；不因某星、恒星或点位带有传统凶名就预告灾祸。

## 历史日期标签

卜卦／择日资料明确为儒略历时，分别传 `question_calendar=julian`、`candidate_calendar=julian`；其他入口仍按已公布的格里历合同。公开 `calendar_input` 字段卡保留原日期、历法和规范化本地钟时，核 `calendar_conversion` 与实际TT／UT1，不能把日期标签JDN当实际时刻。准确历法仍不自动补齐原典钟时、地方平／视太阳时、地区改历或英国旧式换年；输入年份须已规范为公元1月1日换年。夏令时歧义按换算后的日期处理。资料未说明历法时不从国家／年代猜，普通现代输入沿用公开默认；复核历史原图时先说明日期与钟时的确认范围。

原资料已确认平／视太阳时后，卜卦用 `question_clock_basis`、择日用 `candidate_clock_basis` 声明 `local_mean_solar`／`local_apparent_solar`，并省略／null `timezone_name`；太阳时与民用时区不能叠加。普通民用模式为 `civil`，省略时区仍是兼容默认 `+08:00`，不是已确认的时区资料。按 `clock_input` 卡连同原历法读取 `clock_conversion`：输入钟面与解出的物理UTC命名载体、TT／UT1分开，1960年前的载体承载UT1约定。地心LAT不认证具体日晷；不按ASC拟合原书口径，不把数值残差或来源相容当成原记录精度／原典整图／现实预测验收。

资料明确为正午起算小时标签时，卜卦传 `question_hour_origin=noon`、择日传 `candidate_hour_origin=noon`；默认 `midnight` 仍接现代24小时钟面。Lilly1647第30–31页星历表的0是同日正午，14为次日02:00；不能泛化到全部原图，已换算AM／PM的钟面也不再套一次。按 `hour_origin` 卡读原日期、小时、日进位与最终钟面，再依已确认的民用／LMT／LAT处理。此处不计算实际持续时长、制宫表坐标或时区偏移。中间历法标签不可表示时 `normalized_local_datetime=null` 仅限该中间层，最终钟面仍可有效；以 `clock_conversion.input_wall_datetime` 和实际物理轴为准。UTC闰秒标签与中间日期限制见[西占时间输入](../../docs/western-astrology.md#输入与天文精度)。

## Lilly判断前审查

按公开 `lilly_radicality` 字段卡读取 `horary.radicality` 的12项手工条款、实际不等时主、报告上下文和缺项。上升恰好27°属于晚度，月亮晚度仍无原文数值阈值；不把上升界限套给月亮。早晚度例外只复用已确认的 `radicality_context`，不猜年龄／外貌，也不为消除警示另索资料；已知提问钟时不等于确定事件图。空亡保留几何，同时解释所返主星强弱例外及四个星座的限定，不直接断失败。七宫受损适用前提与土星第七宫另条分开；证词相当不等于第115页加权余额零。`safe_to_judge=null` 和未知条款保留，时主对应或无已知警示都不认证整盘。视太阳行星时与几何昼夜在晨昏可能不同，按各自实际返回解释，不强行统一。原典范围见[判断前审查复核](../../scripts/western/audit_western_lilly_radicality.py)。

卜卦和择日先核对同run `calculation_basis.angle_definition`。`geometric_ascendant_resolved=false` 时，实际上升、问者主星、依赖ASC的福点与成事候选为空；`backend_convention` 只保留后端约定供复核，不能拿其主星或分数补回实际结论。择日按 `unresolved_factors/score_bounds` 解释未知贡献，范围不是概率；已解析MC命中仍保留一次，不因ASC未知抹去。仅病态但已解析的ASC保留数值与限定，不自动改为空。独立星体、月亮事件及不依赖ASC定义的宫制事实继续按实际字段解读；本项资格核验不认证整部原典或现实效力。

## Lilly卜卦的容许度与居宫

核对左相／右相时，按 `lilly_sign_rays` 字段卡读取 `horary.significators.directed_sign_relationship`，方向固定为求问者主星向所问主星发出相位，不是接纳的主人／客人方向，也不替代希腊化的overcoming。第108页顺黄道星座次序为左相、逆次序为右相；冲相在该表未分左右，共处同一星座也不自动证明身体合相。第109页仅列32组有向不相照星座对，另16组未列入两表，保留 `not_in_either_table`，不补推正负关系。实际度数／容许度候选与星座表分开，`selected_degree_aspect_agrees=false` 时说明不一致，null按实际候选缺失或来源覆盖不足解释；不重选候选、不加右相分数、不推定成事。恒星黄道保留扩展资格；ASC未解析时主层此证据为空，同一主星不构成两个独立行为星。

核对卜卦原典时，按公开 `lilly_orbs_houses` 字段卡读取同 run 的 `orb_table`、原始行星、主星角色、`p126_127_dwelling`、事件可用状态与完整判断标志。第107页两列容许度都是原书变体，按实际 `orb_profile` 解释；当前半和范围的等号是实现约定，不补成原书定论。第113页太阳状态阈值与相位容许度是两种数量。

`house` 是主星所代表的问者／事项宫，`occupied_house` 才是实际落宫；第48页序次以其他尊贵相等为前提，第115页宫位分值只覆盖表中一行。两者都不能变成成功概率。第126–127页不支持仅凭所问主星落一宫断成；月亮接触方向与当前出入相是已经实现的必要子条件，`event_paths` 的接纳／历史条件另看。未知、重叠根区间与角色重合均不补成传光；即使子条件为真，也须保留 `full_judgement_accepted=false` 的范围。实际输出已满足的传统子条件可以作条件性解读，不以未完成整盘判断为由抹掉这些事实。

核对行星强弱时，公开 `lilly_fortitudes` 字段卡读取第115页41行表的逐星摘要；需要理由时读取同 run 的 `fortitudes.planets.Sun.rows` 等实际行星路径。`applied_conditions` 说明本次满足哪些条款，`unknown_rows` 未核定，`not_applicable` 不适用于该星；未知项不补零。快慢用实际24小时位移，顺逆另看瞬时方向，日月不计顺行奖励。当前恒星按该历元视位置，原页印刷度数只作另列的历史对照；不能混成同一坐标。

宫位条款的“计分归某宫”读取 `inputs.scored_house`；实际落宫仍看 `inputs.occupied_house` 或原始行星的 `occupied_house`。宫头五度效力可使两者不同，不能把第四宫计分解说为实际落第四宫；事项主星代表的 `house` 也须分别说明。

`literal_table_balance` 是声明政策下逐行累计，不是本次问事成功率，也未复现原书全部例题。太阳本垣／三分、日光束和例题恒星加分等差异须保留，不为配平而删行。按实际满足的尊贵、落宫和接触解释其传统条件意义，仍保留完整原典判断未通过的状态；余额为空时，只解读已核定行。

原典累计的补充依据见[商人本命盘校勘](../../scripts/western/audit_western_lilly_merchant.py)：第744页将金星本垣5分和本界2分同时计入，不能因另一例太阳少列三分分值而改成“只取最高尊贵”。第744–745页本命算例将第八宫减损记为4分，与第115页七曜表的2分不同；不能把跨篇例题差异直接改成全局权重。图示金星与太阳名义相距17角分而列日心，与当前闭端点政策相容，但印刷到分的坐标不认证物理位置的亚分精度；缺失的一日位移、交点或恒星输入继续保留未知。

核对福点时，按公开 `lilly_fortune` 卡读取 `horary.fortune` 的实际公式、上升点、`house_assignment`、已满足条件和缺项。Lilly昼夜同用上升＋月亮－太阳，与混合传统的夜盘反转分开；不以第一宫宫头代替上升。几何落宫、最近宫头五度效力和主星代表的事项宫各有实际字段，第145页福点第六／八宫减4分，不能套用七曜减2分。恒星也逐星区分：第179页轩辕十四为六度、角宿一为五度，第115页大陵五为五度，不能统称恒星五度；这些七曜范围用于福点时仍是声明的迁用。严格射线、恒星范围迁用和原书超五度宫头例题差异均保留声明范围；余额为空只解释已核定条件，不推出财富金额或现实成功率。

## 关系盘的方向与深读

先按[星盘技能的规范模式表](../onda-xingpan/SKILL.md#关系盘的读法)取得用户所选主层。工具公开的 `evidence_views.relationship_detail` 是额外证据的权威字段卡；按需与该模式卡的 `fields` 合并去重后调用。`evidence_views` 是描述信息，不能作为请求参数发送。它补充主层，不取代主层。

| 追问 | 实际字段与方向 | 可解释范围 |
| --- | --- | --- |
| “A 对 B 与 B 对 A 有什么不同？” | `in_to_out_aspects` 是 A（inner）星体到 B（outer）星体；`out_to_in_aspects` 反向。每组 `id` 是源，`objects[].id/aspect/delta` 是目标、相位和偏离 | 先说谁的哪一配置联系谁的哪一配置，再谈所问合作／相处情境。几何方向标签不证明对方有相应情绪、心意或行为 |
| “某人的星体碰到另一人的中点了吗？” | `in_to_out_midpoint` 的键是 A 的源星，`midpoint.idA/idB/longitude` 是 B 本命两星中点，`aspect/delta` 是实际命中；`out_to_in_midpoint` 反向 | 对象归属必须说清；不是 A 与 B 两个人的合成中点，也不等于组合盘。只解释已返回命中，不手算缺少的中点 |
| “映点／反映点有什么补充？” | `in_to_out_antiscia/in_to_out_contra_antiscia` 中 `idA` 为 A 源星、`idB` 为 B 目标星；反向字段交换所属人，`delta` 是实际偏离 | 这层是对目标星映点／反映点的几何接近，说明传统读法与普通相位不同。不是新增事件，也不将双向相同命中算成两份独立支持 |

Marks读取 `marks_charts.inner/outer` 两个个人盘，分别核其实际 `derivation_policy` 和所选Davison变体；`chart`只是内方别名。旧的组合盘与时空盘混合配方已撤除，不得沿用。兼容分数来自基础跨盘自定义规则，不能改称Marks个人盘评分、原典权重或关系概率。

追问普通相处时优先复用相关的两三条主层事实；用户点名高级层再展开。说明新增层是否改变原解释，不将不同技法的命中次数相加成关系成功概率。各自本命、实际交互、第三盘和影响图盘始终分开。

## 实现与来源复核

追问近太阳位置差异时，按公开 `solar_position_model` 字段卡读取同 run 的 `apparent_position_policy`。`behind_solar_disc` 描述原生未偏折有限视线穿过模型太阳；`virtual_continuous_solar_disc_extension` 是该模型为保持连续而定义的延拓位置。`foreground_of_solar_disc` 是前景天体，不能据投影重合说成位于太阳后方。该几何不是光学遮掩、边缘接触或实际可见性求解；`not_evaluated` 与边界疑义保留未知，`maximum_physical_error_arcseconds=null` 不能补成零误差。关闭偏折所得对照仅用于诊断，不代换实际返回的位置，也不改变原典条件或现实预测的验收状态。

追问近太阳日速、差分收敛或某个窗口为何不可用时，读取同run的`longitude_motion.complete_position_derivatives`，保留实际`method_id/selected_stencil`、`directional_checks`、`sampling_stabilization`及适用时的`source_branch_motion`。v5的分段方向只描述原生太阳质量插值模型内的数值条件；内部0.0002角秒／日一致性不是物理误差界，更不是人生预测置信度。已恢复计算的窗口可以解读实际返回事实，仍不可用的窗口不补成“没有事件”；精确节点或未知分段不由模型猜方向。具体证据与未通过项。

若实际返回v7的`source_branch_motion.decimal_reduction`，该次辅助采样采用共享原生几何状态的50位数学化简，按原太阳质量分段和同一收敛线求导，显示星位没有改写。`decimal_reduction_previous_attempt`与原始差分尝试保留旧失败；不能把50位运算、框架正交检查或分段内三层一致当成50位天文精度。源文件、坐标标志和框架不一致仍须停止计算。回归及恒星黄道的检查入口见[天球轴与制宫分支](../../docs/western-astrology.md#极区天球四轴与制宫分支)。

涉及 Moshier 的共享日速时，按需读取同 run 的 `longitude_motion.complete_position_derivatives`，核实际 `method_id`、框架与 `status/reason`。完整位置求导只校正该解析位置模型内的日速一致性，不把它升级成另一套动力学星历。`not_applied` 的未收敛记录保留；月亮缺少独立光行时分项时，也须另核完整位置求导是否已执行。对象 `motion` 中的原生日速、交付日速和修正分项分别解释，不沿用其他算法的版本名。

Lahiri 的交付日速跟随实际恒星黄道零点的运动，不能复制热带日速；果老七政的 `longitude_speed` 仍为热带日速，所选黄道位置另读 `zodiac_longitude`。代码采用的标准 Lahiri 定义与某版原刊是否整例相符分开核验。内部收敛、外部计算参考通过数和驻留求根的小数位都不表示物理误差界或现实预测准确率。共享层回执保留超限、平台差异和未验证范围。

以上字段对应 `core/astro/classical.py`、`core/classical_western.py`、`core/astro/aspects.py` 与 `core/astro/relationship.py` 的实际输出。实现文件说明计算口径，不能替代传统解释来源；引用某作者时仍核对原条目。内置知识没有对应内容就说明可核对的范围，不编引文。

## 汉堡日推运的版本比较

用户点名 Witte 日推运时，读取同 run 的 `midpoint_analysis.solar_arc_analysis.daily_meridian`，核实际 `ruleset_id/profile/source_comparison`。当前采用 1924 黄道和差式；1923 原载宫表例的 3°04′差值已由该例第八宫宫头偏移解释，不给当前命盘统一加此差值。`source_comparison.computed_for_current_chart=false` 表示这些数字只属于历史例，另项原刊敏感点比较仍有 4′残差。按返回的实际坐标解释所选技法，保留完整时间钥匙及整部原典未验收状态；不把象征天顶说成目标日物理天顶或现实事件时刻。

## 汉堡本命子午宫表

用户点名 Witte 1923 本命子午宫表时，按公开 `evidence_views.meridian_houses` 读取 `midpoint_analysis.meridian_houses` 与同 run 生时样点。宫头沿赤经每30°等分，黄道上一般不等宽；第一宫宫头为赤道上升点，不能替换 `factors` 的实际 ASC，也不能把 `base_chart` 所选宫制说成 X。核对实际 `profile.native_angle_julian_day_tt/true_obliquity/ayanamsha_apparent`；角度后端的 TT 与共享 TT 分列，差值不是测得的出生钟时误差。`physical_ascendant` 仍须连同基础盘的极点／地平退化约定读取，子午宫头本身不要求解析唯一ASC。用户确认的生时误差逐样点重算宫头；未知误差不是零，样点范围不是连续误差界或概率。宫头定义与原表范围见[子午宫表几何复核](../../scripts/western/audit_meridian_house_geometry.py)；新增天体落宫另读下段，不补完整推运钥匙、原书关键词或现实预测。

要看天体在子午宫的位置，选公开 `evidence_views.meridian_placement`，读取同run `factor_placement` 的输入黄经／黄纬、赤经、`house/house_position`、种类与模型。它用完整方向投影，`longitude_only_control_house`只是零黄纬反事实诊断；不能按黄经宫头区间另算后覆盖结果。物理天体、解析交点与数学假设点分别解释，不把19因素当19颗实测行星；3个角点参考未纳入。`factor_ayanamsha_apparent`取天体同历元，制宫交角历元另列，两者不能混用。数值极点未定不补RA0或宫1。

生时条件先读`birth_time_sensitivity.factor_placement_summary`；`varies_across_samples`须说明已找到换宫样点，需要时再读取同run的`time_sensitivity.samples.meridian_factor_positions`。全部样点同宫不等于连续区间稳定，频次不是概率。Witte1924第59页宫表在两个预定交角模型下仍有第11、12、2宫未协调，不能因投影测试通过称原例或整部原典通过；也不套入原文的伤害、寿命或事件断言。方法及差异见[赤经落宫复核](../../scripts/western/audit_meridian_factor_placement.py)。

## 原生参考角与13扇区退化

分别核对四种角色：基础盘用实际`chart_profile.house_system/house_system_code/house_system_label_zh`；当前数码1是Alcabitus（Swiss `B`），不能称等宫。原生`reference_angle_model.house_code=E`且`cusp_output_used=false`只记录参考角提取，同run样点及太阳弧的本命来源另有对应字段；不能据此把基础盘宫制改称E。`meridian_houses.profile.house_code=X`为独立赤经宫表，`fatebridge_equal13_v1`为13扇区自定义规则。缺失的来源角色保留未记录，不按盘名、数码或另一层的标签补猜。

先读实际层的 `angle_definition`。`geometric_ascendant_resolved=false` 表示本角度模型无法解析唯一ASC，不能把后端约定值解释为确定的物理上升。德国盘原生因素、依赖该参考点的中点／太阳弧联系及同run生时样点携带 `coordinate_basis/reference_angle_basis`；`physical_reference_geometry_resolved=false` 的联系仅为相应约定下的形式几何。MC、星体位置与赤经子午宫表不因这种地平退化一并失效。精确地理极点的子午线约定与数值未解析是不同情况，按各自说明读取。

13扇区 `sector_profile.status=underdetermined_ascendant` 时，实际 `anchor_longitude`、各星 `sector13` 为null，`thirteen_sectors`为空；`backend_convention_*`只供复核。敏感性保留每个样点，未知落区为null，不算落空条件或额外扇区；`computed_sample_count/unresolved_sample_count`不是概率。ASC跨度未定时，`backend_convention_span`不是实际误差界。未知项存在时不能把其余样点概括为全区间稳定。

## 汉堡太阳弧年长钥匙

询问年长钥匙或是否符合 Witte 原法时，读取公开 `evidence_views.progression_key`。实际 `profile.key_policy/year_days/key_years/progressed_julian_day_tt` 描述本次采用的 365.25 日约定；`key_source_comparison` 只是历史原刊比较，`computed_for_current_chart=false`。1923 推运常数原页有两项时角算术不一致，残差是时角时间秒，不是用户钟时误差或黄经修正。保留原值、两项失败及正午起算日期标签未裁定状态，不把其中一个数改成“原典正确值”，也不将当前钥匙冒充原法。依据见[原刊常数核查](../../scripts/western/replay_witte_progression_constant.py)；原典整体和现实效果仍待验收。

太阳弧的名义目标有效，而确认的生时区间跨越当前0..150年长钥匙支持范围时，`birth_time_sensitivity.status=partial`只限制该层；本命、名义太阳弧和日推运坐标仍按实际返回解读。保留全部样点，核`computed_sample_count/unavailable_sample_count`及各样点的`status/reason_code`；未计算的`source_condition_met`不能当成false，`source_pattern.sampled_status=underdetermined`也不能改说全部成立或全部不成立。范围是实现口径，不是寿命推断；不缩短用户区间、补零太阳弧或以样点频次当概率。日推运敏感性沿用同一未计算样点，跨度只覆盖已计算部分。

## 日推运参考与同run绑定

`daily_meridian`须读取自身`profile.reference_angle_basis/physical_reference_geometry_resolved`、`input_coherence`及生时条件。依赖未解析MC的实际坐标为null，`backend_convention`仅保留形式值；太阳和可计算弧继续交付。样点的参考未定数与太阳弧范围外数分开；名义未知不丢其他已知绝对值，实际范围不跨未知间隙。只有ASC交线退化时不限制独立MC。`input_coherence`核对同run网格、时钟／主TT及太阳观测角色，不证明独立星历精度；错配503不能让用户重填出生事实。

## 德国盘原文条件的参考资格

本命和太阳弧的`source_pattern`都按实际MC资格判断。精确地理极点的子午线约定不计入已知成立或缺失；读`unresolved_reference_sample_count`、`unresolved_reference_sample_indices`、`resolved_condition_sample_count`与逐样点条件，形式结果保留在`backend_convention`。太阳弧超范围与MC参考未知分别计数；太阳弧本身可计算不表示原文条件已知。名义解释的`source_application_status=underdetermined_reference_geometry`及`reading_zh`表达适用条件未知，原形式文案保留在`backend_reading_zh`。只退化ASC时仍按独立MC实际值判断；空解释列表、未知样点或形式命中都不能改成现实否定或保证。来源、实际字段与示例见[德国盘与其他盘式](../../docs/other-chart-schools.md)。

## Witte1924比较换基与四点镜像

用户点名Witte1924比较换基或镜点时，可选公开`evidence_views.comparative_geometry`。按实际`profile/frame_summary`区分五个锚点框架，镜点轴用原生白羊点表示热带基准；旋转后的Aries Point因素不是新的镜像轴。`defined_anchor_identity`表示坐标按定义指定，不把未解析ASC／MC或整个框架方向说成已经解析。具体四点、已解析与后端形式值以及生时偏移再取同run字段；未知生时误差保持未知，有限样点不证明连续稳定或概率。Witte1924原表四行仍不协调，不把此具名几何当作整部原典、第五版反映点章、地球宫解释或现实事件预测已经验收。来源与命令见[比较几何审计](../../scripts/western/audit_witte_comparative.py)。

## Witte1925原表与分步舍入

已有用户确认的出生及目标资料，且需要原表来源核对时，可选公开 `evidence_views.witte1925_table`。纯原文问题直接据原刊回答，不为取得这张卡编造出生／目标时刻。`original_table_1925` 属历史表及原载算例，`computed_for_current_chart=false`，不能当成本次太阳弧。38行342个年数格全部保留；20年列的度数疑义传播成24个 `null`，不是0，涉及它们的正权重插值不能给唯一值。318个已解析格不是318个独立天文或预测案例，次年1月6日也不能合并回年初。

按实际 `worked_example` 说明原载56′＋54°17′＋34′＝55°47′成立；不逐步舍入的55°47.925′是另一数值政策，不是已验收原法，也不能将差值加到用户盘面。完整历法／闰日／亚日／跨年和舍入规则未裁定，实际365.25日钥匙保持原值。依据见[1925原表重演](../../scripts/western/replay_witte1925_table.py)。未知格、局部数值检查和现实预测的验收状态分别保留。


太阳时反解落入UTC闰秒时，卜卦／择日保留原生TT／UT1继续计算，`converted_utc`可返回含`23:59:60`的标签。`clock_conversion.utc_representation`明确区分UTC标签、闰秒与Python datetime可表示性；不要截断、平滑、移秒或把显示限制说成星盘不可算。仍不推断原资料精度、实测EOP、完整原典或现实预测有效性。


## Gauquelin 分区的当前范围

公开十二宫请求尚未提供 Gauquelin 的36分区技法。已识别的 `G`／Gauquelin 名称现在会在请求校验时报 `unsupported_house_system`，不再回落普通宫制；说明及三端取证。不要通过改传 Placidus 绕过拒绝，也不能与 Witte 十二个赤经子午宫混称。历史 CFEPP 离线复算的1053条原分区一致是计算比较，不是职业预测命中；13条主算法差异、897条未完成独立钟时核对及无前瞻验证状态须保留。需要这部分依据时读历史分区审计，不自行补出生秒数、折射或完整原典验收。

卜卦／择日可按明确需求选 `ut1_source=iers_c04`；默认仍为 `swiss_delta_t`。先读 `ut1_input` 字段卡中的 `clock_conversion.ut1_reference` 与盘面 `calculation_basis.earth_rotation`：固定日值覆盖1962-01-01 00:00至2026-09-19 00:00 UTC，需要UT1的起盘、宫位及地平时刻超出范围会拒绝；地心TT黄经事件不需要试算时刻的UT1，可在不外推UT1的情况下跨边界搜索。按实际事件 `status` 解释可用性，不能仅因事件超出C04边界就说它未知；真实失败仍不能当无相位／空亡。已发布日值与日间线性插值分开；只应用UT1，极移、CIP偏移、日内潮汐未应用，形式标准差不能说成精确置信界。来源标识和数值通过不证明原始出生钟时准确、原典完整或现实预测有效。模型路径引用为null，不能据此说工具失败。


宫制选择按实际返回的 canonical 字母和名称解释。`Alcabitus`／`Alcabitius` 均取B，`Whole Signs`取W，`Axial Rotation`取X，Swiss等宫字母E等价规范为A；I与i保留为不同Sunshine模型。未知／空白名字、布尔值和浮点编号现在报参数错误，不再默认成另一宫制。`hsys`为0..8共用编号，仍须遵守各技法额外限制；省略参数的既有默认值保留。收到`invalid_house_system`或`invalid_house_code`时修正该选择，不把错误解释为命盘结论，也不改传P后沿用用户原来的流派名称。源码与数值反例。


历史样本的文件数不等于独立证据数。涉及 Gauquelin／CFEPP 的现实验证时，再读来源关联审计：975 条 Ertel 来源关联含一条人物疑点；145 条未关联记录尚未证明独立。正式 Comité Para 队列与带星号的未发表队列要分开，不能删除重复或疑点后追认留出验证，也不能把来源计数当作职业预测成绩。


用户明确要求德国盘太阳弧的交错组合时，读取 `evidence_views.mixed_pairs` 的实际字段；具体式子再取同run新层 `mixed_pair_geometry.dials` 与原生因素。按 `factor_layer_assignments` 区分本命／太阳弧，系数0的 `arc_invariant_contacts` 不随共同弧长改变，不能称新增择时触发。每残差组的四种层次安排、两度盘和零弧重合组不是独立证据。有确认的生时范围时，另读 `evidence_views.mixed_pair_sensitivity`：完整有限域逐样点评估，保留名义盘没有而样点新出现的关系；未列出组须分已证缺失与仍有未知，不能一概当未命中。已知成立和不成立样点证明变化，不被其他未知样点抹去。缺失太阳弧只限制非零系数；系数0仅能据本命因素核相对几何，不补零弧或宣称域外推运坐标。弧长不变不等于生时不变，样点频次不是概率，也不证明连续区间；旧source_pattern状态不能移用。新目录仍无原书事件关键词，保留参考角限定。原刊与有限枚举域。

核对历史盘的自转来源时，读取 `earth_rotation.tt_argument_policy`。v3自定义校正与共享时钟采用相同的TT政策；1960年前的默认历史UT1路径、1960年后的现有SWIEPH关系与明确选择的C04分别回显。旧适配器重推TT的差额仅描述其自转公式参数不一致，不能说出生钟时或所有星位错移同样秒数。原生区间内未启用自定义校正时回显原生内部路径；方法修复不认证历史钟时、实测UT1或绝对精度。细目。

核对明确启用的西占民用钟真太阳时重置时，读取 `person_info.true_solar.time_reference`（德国盘在 `base_chart.person_info`）。`western_solar_rebase_coherent_tt_ut1_v2` 使用记录时刻的主TT太阳赤经与选定UT1上的既定GAST，保留实际太阳来源和自转模型；不要把该记录时刻的太阳当成重置后盘面时刻的太阳。旧 `western_solar_rebase_ut1_v1` 是原生 `time_equ` 规约，原96点及0.0002秒门槛仍保留；新旧数值不一致不应改写旧结果为通过。来源标识、同一模型的独立实现比较和精确回放都不认证绝对精度、历史钟面识别或现实预测。未启用校正、明确LMT／LAT和印度／果老路径不由此改口径。

明确启用西占民用钟太阳时重置时，再核 `time_reference.rebase_arithmetic`。`frozen_recorded_utc_offset_v1` 表示把既定校正量按原记录的UTC偏移相加，保留 `recorded_local_datetime/recorded_utc_offset_seconds/recorded_utc` 与 `rebased_solar_clock_datetime/rebased_utc/rebase_utc_shift_seconds`。重置后的固定偏移太阳钟标签不是该IANA地名在那一钟面上的合法民用钟时，不能再次按夏令时、重复时段或跳日规则选偏移。明确UTC起点的生时样点可穿越重复时段；原始出生钟面有歧义时仍需明确偏移，不猜fold。此重置仍是既定合成钟移政策，记录UTC样点跨规则切换时，校正量本身可能不连续；不能把结果称连续物理时轴、历史LAT逆解或预测概率。
