# 人类图取证与解读

用户明确人类图、BodyGraph、类型、权威或 Profile 时使用 `human_design`。不把八字、西占星座或 Gene Keys 的词义自动混入人类图。

先核对公历出生日期、小时、分钟、时区；未知生时不能补默认。人类图只需要民用出生瞬间，不要求经纬度，不套真太阳时、宫制或恒星黄道。秒省略按所记分钟第0秒计算，不代表秒级资料可靠。

历史时标按实际返回说明：1960年使用IAU SOFA的UTC偏移／日漂移，1961–1971年使用IERS，1960年前仍采用历史UT1约定。233个独立SOFA时刻对照只验证标准换算，不证明实际出生钟或地方授时实现；1961年元旦的5毫秒调整若无唯一民用标签，保留TT与对应状态。

首轮按实际问题选择已发布 evidence_view 的 fields，`strict_fields=true`、`include_snapshot_text=false`：类型／权威用 `structure`，固定摘要用 `fixing`，逐项固定用 `depth`，周期用 `cycles`，太阳圆盘口径用 `apparent_positions`。细分、真／平交点或时间边界用 `precision`／`root_endpoints`。卡名不是请求参数；完整 JSON 首次 `fields=null`，沿用同 run 的结果交付。投影没有某字段不表示该项未评估，也不能把投影交付文件当成完整业务盘。

从 `bodygraph.channels` 与 `definition.components` 说明类型和定义：两端激活才构成通道，两侧激活合并计算。`generator` 的 `manifesting_generator` 是子型，马达至喉可经间接路径。`undefined` 仍可能有激活门，`completely_open` 才表示该中心没有激活门；不能解释为能力或人格缺陷。

权威优先读实际 `bodygraph.authority`，不靠已激活门或个人喜好另判。`environment_no_inner_authority` 和 `lunar_no_inner_authority` 没有内在权威；不能称为头脑内在权威。`profile` 前数是人格太阳线，后数是设计太阳线。轮回交叉按原典返回四门、角度和名称；名称可能保留原拼写，不将英文名称扩成命运或职业断语。

`gate_evidence` 给出原典的中心、门所属回路标签、通道端点及 PDF 页码；门回路标签与通道分类不是同一个字段。`source_consistency` 保留2001版29门1/2线的印刷分界与等分公式分歧；不能声称全本原典已通过。

问回路时读取`circuitry`卡，按`bodygraph.circuitry`中实际完整通道解释赋能／分享／支持主题；数量不等于主导人格或能力强弱。整合四通道是10–20、10–57、20–34、34–57；同四门中的10–34属Centering，20–57属Knowing，不把六条都算Integration。`source_consistency.channel_classifications`区分6条官方直接说明与30条两端门标签推断，不将后者说成独立原页认证。

`node_convention_comparison` 展示真／平交点约定造成的差异，不以哪个“更像本人”挑口径。`time_sensitivity` 对已确认的生时范围使用10秒连续TT网格，并细查检测到的速度变号候选；读取`classification_variants`与`activation_variants`的实际见证。`continuous_interval_certified=false`，未观察到变化只能说检查样本未变，不能说整个区间确定稳定。盘面解释仍针对名义时刻，不能扩展为全区间共同结论；不可跨不同见证时刻拼接单门、通道或角色，逐层数值集合也不能自行作笛卡尔组合。Color/Tone/Base 是黄经细分；不得据此诊断身心、制定饮食处方或断现实事件。`depth` 卡提供原典384线极性星体目录及本盘26位置的实际同门／谐振门触发。月交点不作为供给固定的星体，但四个节点位置可以接受固定；逐项读取 `depth_evidence.line_fixings` 的 `fixing_state`、`fixing_planets` 和 `recipient_kind`，不能写成节点自身未评估。尚未实现 PHS、完整384线解读、合盘和流运，不套其他体系补足。

`node_backend_comparison`另列同一TT的节点后端差异和只替换节点后的结构变化。`same_backend_not_independent`的零差值不能认证精度；平交点也不能因换旗标就当作两个独立模型。Moshier真交点可能改变门线或Tone/Base；实际后端差值及发布者约70角秒的近似最大差异都不是每盘误差上界。122个独立DE440/ERFA时刻对照不能扩为全时域或官方交点约定认证。1800年初出生的设计时刻可能在1799年，只有18段文件不足以保证两侧均为Swiss。

`variables`卡读取四组实际Tone与其引用：P为人格，D为设计，每组先日地、后交点；1至3为L，4至6为R。日地或交点对的Tone若不完整／不一致，不能自行补出编码。Variable解释只限当前名义盘；检查`node_backend_comparison`的所选与参考结构、`time_sensitivity`的同一时刻见证，不拼接不同样本的箭头，不据L/R诊断认知、学习能力或制定饮食／健康方案。已核对的有限官方样例不能认证所有生时、连续范围或完整原典；已封存的字面名称失败、印刷分歧和天文超差仍保留，当前个案以实际回执为准。

地球／南交点的细分使用同侧来源黄经加180°后的精确有理坐标，显示`longitude`可能舍入到边界。需要重放或核验时同时读取`derived_from`与`derivation_source_longitude`，不能仅凭显示角度改判Tone／Base；生时见证也沿用其实际派生来源。138,239个边界算术探针不表示真实出生人群或星历误差率。

普通答复先解释用户所问类型／权威的体系内含义，再接实际门、通道或角色依据，给可自愿记录和对照的生活观察。计算、体系解释和现实证据分开；没有实证样本就保留 `validation.prediction=not_validated`。规则来源与四项验收范围见[专业能力与审计](../../../docs/human-design.md)。

逐句复核读取 `grounding` 卡，`interpretation.statements` 的每条说明带实际字段与来源。自动核验须使用同一完整run和可信回执；投影或任意自由文本不能直接当作核验通过。设计时刻使用连续TT求根，若返回UTC闰秒标签，保留秒60与TT，不自行改成次日0点。

核对Identification交叉时，可读`primary_diagrams`卡：两幅2008公开转录图仅支持16/9｜63/64或9/16｜64/63的有序四门及左角度。按实际`observations`回执交付卷次、PDF页码、印刷页码与文件指纹；未匹配不能借相似名称套用。转录本未经校对，母本未认证，不是16/6课程列项的勘误，图所在5/1段落也不提供其他角色的完整线义。原2001名称及所有来源分歧仍保留。

周期参考输入最多6位小数秒，超限拒绝。`cycle_summary.reference_ordering`核对源定义连续TT上的输入先后，完整来源见同次`cycle_context.reference_ordering`；微秒输入分辨率不代表出生记录或天文精度。周期接触仍按原有双精度TT和数值区间解释。

周期参考时刻与交会括区的先后另读`cycle_summary.reference_contact_ordering`。当前按已声明时标的精确有理TT与已报告的闭合数值括区比较，不能因两者舍入成同一个浮点JD就说参考时刻在括区内。解释“之前／之间／之后”时限定为已算得的数值接触区间；这个修正不认证真实交会的微秒精度，也不裁定逆行首末触取舍或第六线阶段。历史回执若因已知边界丢失被拒绝，保留原答与原失败，不用旧版本兼容将其放行。

实际设计数值根端点见`root_endpoints`摘要；完整原生位置与结构在同次`design_solver.numerical_precision.design_body_endpoint_assessment`，每个实际生时样本也有自己的design_solver。若Moon等因素跨门或子型／通道变化，按各候选整盘条件分别说明，保留当前主盘的最小残差选根，不混拼候选；不能把端点一致说成物理精度或连续稳定，也不能把差异说成发生概率。

数值根端点的`design_body_endpoint_summary.interpretation_summary`同时比较双侧26项固定机制、桥接完整门集、回路与角色依据；设计侧变动也可能改变未移动的人格位置。完整变化记录及reading读取同一run的`design_body_endpoint_assessment.endpoint_interpretations`。所有依据路径相对该候选盘，不指所选主盘；依据相同不证明连续稳定，固定机制通过不等于384线完整原典线义通过。

周期的`cycle_summary.numerical_scope`说明交会和已观测驻点只细化到观测零值或相邻TT；完整驻点速度区间、接触精确角残差见同次`cycle_context`。黄经量化可能掩盖极近的两次交会，观测一个零值不能认证连续根数量。三项实际数值起点均为人格出生黄经；来源口径分别读取 `cycle_context.bodies[*].origin_source_evidence`。公开词典已明文以天王星出生位置为对冲基准；将出生时刻对应到人格侧的依据另列，不能说该定义直接写了Personality。土星／凯龙的原典起点以及三者多触首末传统取舍仍未裁定，不外推天王星明文，不据此分配第六线当前阶段。

`additional_poles`卡保留2001正文另列的11.4金星、25.4木星及本盘实际采用它们的依据；原exaltation_planet字段只对应印刷符号。附加星体仍须实际出现在同门或谐振门，不能无条件补造触发，交点不施加固定。两项正文事实不等于384线全文验收，也不改变25.4的非双极性类别。

需要具体爻义参考时，可调用`knowledge_read(domain="human_design", category="lines", key="门.线")`；先用同run实际激活定位，不从角色数字推算具体门线。目录保留全部384线的来源块与极性星体，当前1.1至2.6共12条有本地简短转述，仍待独立复核，完整独立线义验收0条；其余372条的`editorial_paraphrase=null`表示尚未整理，不能补造。参照`depth_evidence.line_fixings`实际`fixing_state`说明被强调的极性，不声称另一极性永不发生；juxtaposition并列两极，unfixed只列原文已有可能，不能仅凭知识条目选定。`source_polarity_planets`包含11.4金星和25.4木星的附加事实，列出星体不等于本盘触发。1.4原文重复措辞的疑点须随解释保留，不称作已勘误。2.3须保留原文服务回报的永久2–14通道条件，结合同run实际固定状态与永久通道证据再讨论，不能改成无条件结果或自动推断逆命题；知识查询的条件适用性为null。2.6上升段也有视野狭窄的含义，不一概美化。其他条目的条件未记录表示未评估，不表示无条件。覆盖数以当前目录coverage为准。知识条目本身不评估个人适用性，亦不认证完整384线、原典母本或现实效力。

`personality_colors`卡按人格日地的Color读取Motivation类别，按人格交点的Color读取View类别；检查实际Color、人格路径与对点一致性。缺失或冲突不补类别。英文类别是官方教学来源的体系术语，不据其字面判定现实动机或能力；出生盘的转移、分心、是否对齐均未评估。交点口径的四箭头即使相同，Color类别仍可能不同，按同一口径的完整联合见证分别说明。联合投影v2保留人格Color，过渡四元状态的Tone与Color属同一个源依赖，对点不算额外证据。该有限类别功能不代表完整PHS或384线线义已验收。

`root_endpoints`卡另含太阳口径、有限邻点及额外数值候选摘要。求根太阳与实际太阳按同一旗标逐位绑定；若返回`local_solar_lattice`的实际反向步或多组符号括区，不把它说成太阳物理逆行或多个真实时刻。`local_root_family`的每个候选均有自己的完整设计盘、固定与结构解释；保留原主盘，逐候选读依据，不拼接。摘要计数0只表示未观察到额外多候选，原1/2端点仍在基础评估。不同数值搜索器的严格根值差异继续保留失败，有限邻点一致也不认证物理精度、连续唯一性或完整历法验收。

额外候选的`comparison_basis`明确before为所选盘、after为当前候选盘，实际TT可能更早、相同或更晚；按这一次序解释变化，不把before/after说成时间先后。索引0设计来自主盘，索引1来自当前family索引的`native_positions`，两盘人格固定。各自的`calculation_path`相对于各自候选盘。原基础端点评估仍按较早／较晚TT排列，两种比较依据分别核对。

完整回执的JSON对象键可重新排序，数组与其`calculation_path`索引不能重排。分页文本散列须核对原始字节；重新序列化保存的文本另算文件散列，业务哈希和字段核验分别核对。核验失败时按具体字段查因，不凭重新生成哈希放行。官方样例只匹配类型或定义也不能代替生时、全部激活及完整解释验收；历史出生注记缺时区时，不用匹配结果挑选时区或改写午前／午后。

交付校验说明须明确对象：`result_delivery.sha256`核对本次交付文本；`run_metadata.business_output_sha256`标识投影前的完整业务对象。请求了`fields`时，同run文件仍可能只含所选字段，交付文本散列相符不等于完整业务散列已核对。只有实际读取同run完整业务对象并按业务摘要规则核对后，才能声称完整业务校验通过；核对投影时只说“所选字段交付的文本散列相符”。


索取全部激活／固定时覆盖双侧实际26项，依据各项 `calculation_path` 列侧、星体、门线和 `fixing_state`。`status` 的单极性类别不等于本盘已经上升触发；`unfixed` 不等于无极性星体，也不等于行运或人际互动永远不触发。固定机制及其逐项reading不构成完整原典爻义，未取得的正文不补写为已验收解释。

公开2001版PDF包含384线正文；“未交付／未完成审校”不能说成“公开正文不存在”。逐线条款续核（本地数据：`../../../docs/validation/human-design-primary-clause-scope-v1/README.md`）已检查全部384个文本块和11个星体／极性候选，仍不构成384线完整解释验收。另找到公开2005年周期课转录：太阳回归的双侧时点说明只用于该节范围；凯龙七年窗口是解读时机建议，不能代替数值求根范围、误差容限或首末触规则。第三方转录副本不作出版方母本认证，土星／凯龙起点及多触优先性继续按实际未决状态交付。

58.5的历史分歧读取 `historical_polarity` 卡：当前2001字面表、2002年zc design通知条件模型及两张既有官方盘的相反标记同时保留。逐项给所选与条件状态、实际供给路径；通知适用版次及出版方母版未认证，不自动切换默认、不声称完整线义解决。完整记录见历史极性续核（本地数据：`../../../docs/validation/human-design-historical-polarity-v1/README.md`）。

太阳附近视位置、名义太阳圆盘投影与偏折延拓分歧，按本盘 `apparent_position_context` 及相应解释说明；名义投影不是实际遮掩或可见性观测。既有独立参考行属于其冻结TT，不把差值移植为另一个民用输入的实测误差。即使求根括区极窄、有限端点的门至Base一致，也不认证物理精度、整个连续区间或真实出生记录。

用户要求完整解释精度边界时，同时读取 `solar_deflection_policy`、`policy_basis` 和 `original_human_design_software_convention_certified`：明确本次实际采用的太阳盘内透明质量偏折延拓，以及独立参考和原人类图软件口径尚未裁定的范围。只说明“名义圆盘不认证遮掩”没有交代偏折规范；不得把未说明的规范差异写成已经验收，也不把另一TT上的超差数值套入当前盘。


几何解释先读 `apparent_position_context.coordinate_context` 与 `interpretation.coordinate_frame_meaning`，核对观测原点、坐标架、单位和夹角顶点。当前批次只允许地心视位置：太阳角距是地心处太阳视线与目标视线的夹角；“太阳”是视线端点，不是观测原点。不能因名称含太阳就称日心角距，也不能把角距当日心距离。未读到这些字段时不能自行换原点；数值相同不代表几何含义相同。


周期规则1.6.0的`station_witnesses[*].coordinate_probe`保留有限坐标补探：原生速度零点不直接当作返回黄经极值，原扫描完成后才补探；目标进入严格扩展的已观察极值范围时才追加分段。网格端点零速度和连续已观察零值分别处理，不把零值段两端当作两次物理交会。`motion`仍取原生返回速度符号，对照`motion_evidence.search_segment_phase_trend`及`native_speed_agrees_with_segment_trend`；不一致时分别说明，不把搜索段方向说成已认证的瞬时导数。缺失的motion_evidence为未知，不能补造；完整新回执核验仍要求实际依据。新增数值候选不等于新增公转轮数，极窄括区也不证明物理时刻精度。原一秒参考分歧和连续根数未认证状态继续保留，见周期坐标极值续核（本地数据：`../../../docs/validation/human-design-cycle-solar-stations-v1/README.md`）。

`summary_format=human_design_cycle_summary_compact_v1`的周期卡将重复状态放在`contact_defaults`，方向约定放在`motion_evidence_defaults`。必须连同这些声明读取：每条显式例外优先，`segment_phase_trend=null`仍是未知；非空例外可与原生`motion`相反，不得说二者一致。省略完整分段端点只表示摘要投影，实际见证与原有范围说明在同次`cycle_context`及`summary_conventions`，需要时读取同一run，不重算替代。没有格式声明或默认表时不能猜省略值，也不能把默认映射当作瞬时坐标导数认证。完整接触日期、TT、运动、区间宽度及残差保留；原典取舍和第六线阶段未定状态不变。见摘要与三端复核（本地数据：`../../../docs/validation/human-design-cycle-summary-v1/README.md`）。
