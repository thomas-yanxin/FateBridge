# 人类图取证与解读

用户明确人类图、BodyGraph、类型、权威或 Profile 时使用 `human_design`。不把八字、西占星座或 Gene Keys 的词义自动混入人类图。

先核对公历出生日期、小时、分钟、时区；未知生时不能补默认。人类图只需要民用出生瞬间，不要求经纬度，不套真太阳时、宫制或恒星黄道。秒省略按所记分钟第0秒计算，不代表秒级资料可靠。

历史时标按实际返回说明：1960年使用IAU SOFA的UTC偏移／日漂移，1961–1971年使用IERS，1960年前仍采用历史UT1约定。233个独立SOFA时刻对照只验证标准换算，不证明实际出生钟或地方授时实现；1961年元旦的5毫秒调整若无唯一民用标签，保留TT与对应状态。

首轮按实际问题选择已发布 evidence_view 的 fields 或 include（三端始终严格校验路径）：类型／权威用 `structure`，固定摘要用 `fixing`，逐项固定用 `depth`，周期用 `cycles`，太阳圆盘口径用 `apparent_positions`。细分、真／平交点或时间边界用 `precision`／`root_endpoints`。卡名可传给 `include`（不可作为 `fields` 路径）；无损完整 JSON 使用 `include=["*"]`（省略 `fields`）。投影没有某字段不表示该项未评估，也不能把摘要结果当成完整业务盘。

从 `bodygraph.channels` 与 `definition.components` 说明类型和定义：两端激活才构成通道，两侧激活合并计算。`generator` 的 `manifesting_generator` 是子型，马达至喉可经间接路径。`undefined` 仍可能有激活门，完全开放中心（`status="undefined"` 且 `activated_gates=[]`）才表示该中心没有激活门；不能解释为能力或人格缺陷。

权威优先读实际 `bodygraph.authority`，不靠已激活门或个人喜好另判。`environment_no_inner_authority` 和 `lunar_no_inner_authority` 没有内在权威；不能称为头脑内在权威。`profile` 前数是人格太阳线，后数是设计太阳线。轮回交叉按原典返回四门、角度和名称；名称可能保留原拼写。

轮回交叉按原典返回四门、角度和名称；名称可能保留原拼写，并附 `incarnation_cross.source_pdf_page_one_based` 页码索引。`bodygraph.gate_sources` 保留门的来源信息，门回路标签与通道分类分别查看。

问回路时读取`circuitry`卡，按`bodygraph.circuitry`（含 `defined_channel_count`、`circuits`、`group_channel_counts`、`integration`）中实际完整通道解释赋能／分享／支持主题；数量不等于主导人格或能力强弱。整合四通道是10–20、10–57、20–34、34–57；同四门中的10–34属Centering，20–57属Knowing，不把六条都算Integration；6条官方直接说明与30条两端门标签推断的来源区分不将后者说成独立原页认证。

`birth_time_sensitivity` 对已确认的生时范围（`birth_time_uncertainty_minutes` 1..60）使用30秒连续TT网格；读取 `changed_structure_fields` 与 `activation_variants` 的实际见证。未观察到变化（`status=stable_on_grid`）只能说检查样本未变，不能说整个区间确定稳定。盘面解释仍针对名义时刻，不能扩展为全区间共同结论；不可跨不同见证时刻拼接单门、通道或角色，逐层数值集合也不能自行作笛卡尔组合。Color/Tone/Base 是黄经细分；不得据此诊断身心或制定饮食处方。`depth` 卡提供原典384线极性星体目录及本盘26位置的实际同门／谐振门触发。月交点不作为供给固定的星体，但四个节点位置可以接受固定；逐项读取 `depth_evidence.line_fixings` 的 `fixing_state`、`fixing_planets` 和 `recipient_kind`，不能写成节点自身未评估。尚未实现 PHS、完整384线解读、合盘和流运，不套其他体系补足。

交点口径默认 `node_mode="true"`，可显式切为 `"mean"`；`activations` 中每颗星体记录自身的 `ephemeris_model`、`return_flags` 与 `native_return_flag_model`。同后端或解析平交点不能当作独立精度认证；`require_swiss_files=true` 可拒绝非 Swiss 星历回退。

`variables`卡读取四组实际 `variables.arrows` 与 `phs_determination`、`environment`、`motivation`、`view`、`cognition`、`sense`：P为人格，D为设计，每组先日地、后交点；1至3为L，4至6为R。日地或交点对的Tone若不完整／不一致，不能自行补出编码。Variable解释只限当前名义盘；不拼接不同样本的箭头，不据L/R诊断认知、学习能力或制定饮食／健康方案。当前个案以实际回执为准。

地球／南交点的细分使用同侧来源黄经加180°后的精确有理坐标，显示`longitude`可能舍入到边界。需要重放或核验时同时读取`derived_from`与`derivation_source_longitude`，不能仅凭显示角度改判Tone／Base；生时见证也沿用其实际派生来源。138,239个边界算术探针不表示真实出生人群或星历误差率。

普通答复先解释用户所问类型／权威的体系内含义，再接实际门、通道或角色依据，给可自愿记录和对照的生活观察。计算、体系解释和现实证据分开，方法边界见[人类图参考](../../human-design.md)。

## 固定解释与同次依据

逐句复核读取 `grounding` 卡（含 `profile`、`incarnation_cross`、`bodygraph`、`depth_evidence` 与 `design_solver`），核对每项实际字段。自动核验须使用同一完整run和可信回执；投影或任意自由文本不能直接当作核验通过。设计时刻使用连续TT求根，若返回UTC闰秒标签（`design_solver.utc_is_leap_second=true`），保留秒60与TT，不自行改成次日0点。

核对Identification交叉时，可读`primary_diagrams`卡（返回 `profile` 与 `incarnation_cross`）；两幅2008公开转录图仅支持16/9｜63/64或9/16｜64/63的有序四门及左角度，未匹配不能借相似名称套用。

## 周期参考与数值先后

周期参考输入最多6位小数秒，超限拒绝。`cycle_summary.bodies[*].reference_relation`（及完整 `cycle_context.reference_jd_tt`、`cycle_context.birth_jd_tt`）核对源定义连续TT上的输入先后；微秒输入分辨率不代表出生记录或天文精度。周期接触仍按双精度TT（`contacts[*].jd_tt`）和实际返回 `reference_relation`（`before_first_observed_contact` / `between_observed_contacts` / `after_last_observed_contact`）解释，不因浮点舍入推断接触区间内部位置，也不裁定逆行首末触取舍或第六线阶段。

## 设计根端点与周期数值范围

实际设计数值根摘要见`root_endpoints`卡（`birth_utc`、`design_utc`、`design_solver.bracket_width_seconds`）；完整求根过程在同次`design_solver`（含 `target_solar_arc_degrees`、`design_jd_tt`、`birth_jd_tt`、`residual_degrees`、`bracket_width_seconds`、`iterations`、`method`）。若给出 `birth_time_uncertainty_minutes`，各变化候选见 `birth_time_sensitivity`（`changed_structure_fields`、`activation_variants`），按名义主盘与见证差异分别说明，不混拼候选；端点一致或括区极窄不证明物理精度或连续稳定。

`cycle_summary`（`status=computed_finite_search`）与 `cycle_context`（`method_id`、`reference_utc`、`reference_jd_tt`、`birth_jd_tt`、`bodies[*]`）说明土星回归、天王星对冲、凯龙星回归为有限采样搜索，每个接触记录 `jd_tt`、`utc_label`、`longitude`、`longitude_speed`、`motion` 与 `residual_degrees`；三项数值起点均为出生时刻的本命黄经。土星／凯龙多触首末取舍仍未裁定，不据此分配第六线当前阶段（`cycle_summary.sixth_line.phase_status`）。

## 线义与极性触发

`additional_poles`卡保留2001正文另列的11.4金星、25.4木星及本盘实际采用它们的依据；原exaltation_planet字段只对应印刷符号。附加星体仍须实际出现在同门或谐振门，不能无条件补造触发，交点不施加固定。两项正文事实不等于384线全文验收，也不改变25.4的非双极性类别。

需要具体爻义参考时，可调用`knowledge_read(domain="human_design", category="lines", key="门.线")`；先用同run实际激活定位，不从角色数字推算具体门线。目录保留全部384线的来源块与极性星体，当前1.1至2.6共12条有本地简短转述，仍待独立复核，完整独立线义验收0条；其余372条的`editorial_paraphrase=null`表示尚未整理，不能补造。参照`depth_evidence.line_fixings`实际`fixing_state`说明被强调的极性，不声称另一极性永不发生；juxtaposition并列两极，unfixed只列原文已有可能，不能仅凭知识条目选定。`source_polarity_planets`包含11.4金星和25.4木星的附加事实，列出星体不等于本盘触发。1.4原文重复措辞的疑点须随解释保留，不称作已勘误。2.3须保留原文服务回报的永久2–14通道条件，结合同run实际固定状态与永久通道证据再讨论，不能改成无条件结果或自动推断逆命题；知识查询的条件适用性为null。2.6上升段也有视野狭窄的含义，不一概美化。其他条目的条件未记录表示未评估，不表示无条件。覆盖数以当前目录coverage为准。知识条目本身不评估个人适用性，亦不认证完整384线或原典母本。

## 人格 Color

`personality_colors`卡按人格日地的Color读取Motivation类别，按人格交点的Color读取View类别；检查实际Color、人格路径与对点一致性。缺失或冲突不补类别。英文类别是官方教学来源的体系术语；出生盘的转移、分心、是否对齐均未评估。交点口径的四箭头即使相同，Color类别仍可能不同，按同一口径的完整联合见证分别说明。联合投影v2保留人格Color，过渡四元状态的Tone与Color属同一个源依赖，对点不算额外证据。该有限类别功能不代表完整PHS或384线线义已验收。

## 额外数值根候选与完整交付

`root_endpoints`卡包含出生/设计UTC与 `design_solver.bracket_width_seconds`；完整求根与时间尺度数据在 `design_solver` 与 `time_scales`。完整回执的JSON对象键可重新排序，数组与其`calculation_path`索引不能重排。字段核验逐值检查实际完整结果；独立保管的原始文件不能用重新生成的结果替代，核验失败时按具体字段查因。官方样例只匹配类型或定义也不能代替生时、全部激活及完整解释验收；历史出生注记缺时区时，不用匹配结果挑选时区或改写午前／午后。

交付核验须区分原run一致性与业务读取范围。请求了 `fields` 时，返回只包含实际保留字段；完整交付须使用 `include=["*"]`（省略 `fields`）取得全部所需业务字段，不重算替代原run。

索取全部激活／固定时覆盖双侧实际26项，依据各项 `calculation_path` 列侧、星体、门线和 `fixing_state`。`status` 的单极性类别不等于本盘已经上升触发；`unfixed` 不等于无极性星体，也不等于行运或人际互动永远不触发。固定机制及其逐项解释不构成完整原典爻义，未取得的正文不补写为已验收解释。

公开2001版PDF包含384线正文；“未交付／未完成审校”不能说成“公开正文不存在”。逐线条款续核已检查全部384个文本块和11个星体／极性候选，仍不构成384线完整解释验收。另找到公开2005年周期课转录：太阳回归的双侧时点说明只用于该节范围；凯龙七年窗口是解读时机建议，不能代替数值求根范围、误差容限或首末触规则。第三方转录副本不作出版方母本认证，土星／凯龙起点及多触优先性继续按实际未决状态交付。

## 历史极性分歧

58.5的历史分歧读取 `historical_polarity` 卡（`depth_evidence.line_fixings` 与 `depth_evidence.fixing_summary`）：当前2001字面表、条件模型及既有标记差异分别说明，不声称完整线义解决。来源分歧和限定见[当前计算说明](../../human-design.md)。

## 视位置、坐标框架与周期摘要约定

星体视黄经、速度及所用星历在 `activations`（`longitude`、`longitude_speed`、`ephemeris_model`、`return_flags`、`native_return_flag_model`）与 `calculation_policy`（`ephemeris_model`、`ephemeris_version`、`require_swiss_files`）中读取；即使求根括区极窄、有限端点的门至Base一致，也不认证物理精度、整个连续区间或真实出生记录。当前批次为地心视黄经，不自行改换观测原点。

`cycle_summary` 返回周期摘要，完整接触见证与 TT 坐标在同次 `cycle_context`（默认通过 `default_omit` 省略，可传 `include=["cycle_context"]` 或 `include=["*"]` 展开）中读取，不重算替代；每次接触的顺逆运动与速度取自 `contacts[*].motion` 与 `contacts[*].longitude_speed`。
