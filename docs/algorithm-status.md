# 当前算法状态与未验收范围

[文档中心](README.md) · [API 参考](api-reference.md) · [覆盖矩阵](algorithm-coverage.md)

本页维护当前计算路径及已知限制。完整工具清单见[覆盖矩阵](algorithm-coverage.md)，请求和响应以[实际接口合同](api-reference.md)为准。局部数值回归、原典对照、接口一致性和现实预测分别验收，不能相互替代。

已有 132 项独立根因修复获得固定对照支持。首轮项目测试在第 51 项后启动。全仓逐定义专业验收仍在进行，独立语义算法总数未知。 [当前清单](algorithm-inventory.md) · [法达近期验收](#round154-157-firdaria) · [R151 验收](#round151-time-lord-civil-domain-and-source) · [R140 验收](#round140-recorded-clock-budget-and-firdaria) · [集中验证](#round48-consolidated-validation) · [R49 验收](#round49-shared-clock-admission) · [R50 验收](#round50-lunar-and-study) · [R51 验收](#round51-native-motion) · [DE441 补验](precision-acceptance.md#native-de441-motion-round53) · [R58 合批复验](#round58-regression-reconciliation) · [R59 合批复验](#round59-regression-reconciliation) · [R60 合批复验](#round60-regression-reconciliation) · [R61 合批复验](#round61-regression-reconciliation) · [R62 合批复验](#round62-regression-reconciliation) · [R63 合批复验](#round63-regression-reconciliation) · [R65 合批复验](#round65-calendar-ownership-and-peer-cautions) · [R66 合批复验](#round66-exact-replay-start-and-canping-date) · [R67 固定对照](#round67-generated-clocks-and-house-state) · [R70 固定对照](#round70-return-clock-and-geometry) · [R71 时点与来源](#round71-clock-labels-and-source) · [R79 固定对照](#round79-closed-orb-and-source) · [R84 集中复验](#round84-exact-direction-window) · [R86 集中复验](#round86-clock-gap-and-direction-state) · [R90 合并复演](#round90-recorded-epoch-combined) · [R120 验收](#round120-alias-distance-and-fengshui-date)

代表请求中发现的未决状态、已修复的条件缺口与后续裁定所需证据见[工具结果未决项审查](unresolved-calculations.md)。

截至R37已认可29项独立改进；R35的[DE441无损源字](precision-acceptance.md#lossless-de441-round35)与[杂气月并存见证](algorithm-audit-20261117.md#lossless-source-month-uses-round35)各计一项，R37的[精确UT1传播](precision-acceptance.md#retained-source-ut1-round37)属于已有精度家族补全，不重复计数。R34的来源准入及整数历有限接受保持。全仓语义、逐定义专业接受与SOTA仍未完成；项目测试按严格超过50项独立优化后执行。

R38在有限实际源操作和独立保存结果对照后认可两项减少重复工作的优化：同次窗口复用与试探点按需赤纬，累计独立优化31。固定C01三端完整业务同版及各端前后均0差，原raw输入Schema35差保留；[范围与未通过层](precision-acceptance.md#same-call-work-quantity-round38)继续分开，不提高物理精度或SOTA资格。

R39补充独立的[UTC定义与来源记录](precision-acceptance.md#utc-definition-source-round39)，区分CGPM2026规范生效日、冻结闰秒表的分发有效期和具体历元的实际政策。三个案例九次三端调用成功，旧数值／布尔不变；元数据及快照的真实差异保留。该轮新增0、累计31；R39冻结时的C04现代模型尚只有来源／系数准备。

R40实现并有限接受[现代C04时钟与同EOP地球姿态](precision-acceptance.md#modern-c04-eop-round40)两项根本差距，累计31→33。独立8点时钟／方向56门与2时刻4站点SOFA几何120门符合原线；旧16项时钟及40项几何失败保留。两请求两版共12次实际REST／MCP／CLI均成功，同版业务一致，Swiss控制前后不变，C04每端53差完整保留。支持类型、定义、系数和样本不另计根因；直接math／public启动文件未预冻结、native house／azalt独立数值及完整物理／预测／SOTA资格继续分开。33未严格超过50，项目测试及生成合同检查仍未运行。

## 合并后复验

- 农历换算的两个纽约重复钟时按显式 UTC 偏移分别解析。固定测试验证 REST、MCP、CLI 业务结果一致，节气起算的经过时间相差一小时。
- 风水单节气解析复用年度表的时标和星历求根。1926、2026、2041 三年共 36 个节界与年度表的 TT 完全一致。另以独立冻结参考复核 421 个立春时刻，原有一秒门槛保持。[立春参考测试](../tests/fengshui/test_fengshui_calendar_v10.py)
- 印占 Panchanga 日出前标志使用地理地方平太阳日期和实际太阳事件。角度交付保留精确分档，星宿进度由同一有理数余量求得。六力各分量及候选保留在 `india.strengths`，五星运动力可显式选择 Simon 1994。[印占计算](jyotish.md)
- 按 PyJHora 的所选 Traditional Parasara 分支核对 D4、D16、D20、D24、D27、D40、D45、D60。每个分盘检查 12 个星座各 240 个精确八分之一度样本。23,040 项的符号与度数符合对应半开区间公式。PyJHora 的浮点 `//` 在 D27 每个星座的 10° 和 20° 提前落入前一分区，共 24 项。这一分歧由精确区间判定解释。[PyJHora 分盘实现](https://github.com/naturalstupid/PyJHora/blob/master/src/jhora/horoscope/chart/charts.py)
- 92 个公开工具的固定样本均经共用交付层执行 `standard` 和 `compact`。压缩批次前，两种交付合计分别为 20,275,499 和 371,176 个 UTF-8 字节。随后以同一请求比较 11 个单项西占时运工具以及卜卦和择日的标准响应。关闭快照后业务字段逐值一致，合计从 8,843,808 降至 2,281,385 字节，统计排除运行回执。显式导出和审计可取得快照。[工具定级](algorithm-tool-priorities.md) · [交付选项](api-reference.md#25-字段投影与输出体积)

## 当前采用的路径

| 范围 | 当前计算与边界 | 详细依据 |
| --- | --- | --- |
| 方法及运行证据 | 当前 92 条目录记录覆盖 REST、MCP 和 CLI，登记 65 个共享领域方法。性格入口的出生前置与符号词典分别声明。已核验的精确比例、整数环路、九宫步进及名义投影交付条件输出界和操作数边；全部上游语义证明及物理误差传递保持未决 | [计算证据合同](computation-evidence.md) |
| 细粒度源码清单 | 清单按当前源码登记计算、规则、支持职责及未映射定义，计数见链接中的统一索引。工具调用、职责审读、分支覆盖和独立验收分别登记；职责数不是细算法总数，全仓语义清查仍未完成 | [细粒度清单](algorithm-inventory.md) |
| 共享种子与太阳标签 | 数字分析和本地组合工具共用领域 seed；实际民用时刻与 zone-free 日序／微秒标签分离，保原均时差与取整。原4边界拒绝恢复、现代4完整业务不变，9工具12场景36次三端同值。原 C 严格均时差比较仍为 1/2，B1 位差已归因于原生二进制的末段乘减融合 | [共享标签范围](calendar-boundary-audit.md#nominal-clock-labels-round33) · [原生位差归因](precision-acceptance.md#native-eot-build-attribution-round48) |
| 知识资料定义分母 | 基础四域与三个BaZi补充包213命名键、144将支注记及别名／组合空间分别登记；六张配属卡已补所选原典窄支持；68个curation、97次来源映射仍只表示有限来源范围。全文语义、原典／专家及现实效度未据此通过 | [资料分母](algorithm-audit-20261117.md#knowledge-data-definition-census)／[六卡窄来源](algorithm-audit-20261117.md#de440-source-kernel-and-citations) |
| 实际星历月相推运 | 默认由出生后实际日月星历搜索八相，退休均速／单周期字段。固定40日工程窗口的11个TT逐位等于独立作者C，精确民用点与年龄相同，全部符合DE440/SOFA原定角／时间线；两种源策略三端完整业务一致。公开哈希缺失的原检查仍为false，内部来源核验另列；历史／未来钟及全域SOTA未验 | [来源、原门槛与交付边界](precision-acceptance.md#actual-progressed-lunation) |
| 名义日历与标量TT舍入 | 精确日序／微秒及已发布原子偏移只在标量边界舍入一次；固定381920时刻的148项名义日值及18469项TT非最近值修复。65536项TT与官方SOFA最后合成的标量相同，但仍全部劣于原两部表示，原强门槛继续失败 | [单次舍入与完整分母](precision-acceptance.md#名义日历与标量tt的单次舍入) |
| 源记录与补偿插值 | 给定两部TDB精确选record/offset并保留Fraction局部x，递推、单位和地月组合完成后才投影。固定4446输入的26676字段均为最近偶目标；原54队列42域内／12域外资格正确，域／record／精确x失配0，252位置／速度分量为原目标。R31旧v3的packaged原字0/36保持历史；当前v4无损源与另封187状态另验。物理及全域SOTA仍未认证 | [分层参考与完整分母](precision-acceptance.md#compensated-source-polynomial)／[当前无损源](precision-acceptance.md#lossless-de441-round35) |
| 保留TT主点与两部适配 | 共享时钟、离线星历及目标几何保留唯一Fraction主点；原65536时刻的主点均与源算式完全相同。补偿两部适配在同一原分母均比原SOFA两部的表示误差小；中间integer-head版本16190项较差完整保留。标量原强失败、原生SDK／UT1与物理模型限制不改判 | [表示、实际消费与协议分别验收](precision-acceptance.md#retained-primary-tt) |
| C04源轴与已解TT | 当前在连续TT上对去Z62的UT1−TAI作四点插值，再还Z62并加入一次日内项；正逆解同一给定pair方程，8正向／8逆向符合各自原1e−11秒线。R19仿射模型的九输入、7前向／3有效逆及旧域外失败保留为历史，不能当现代模型全域验收 | [当前模型与有限范围](precision-acceptance.md#modern-c04-eop-round40)／[旧源轴审计](precision-acceptance.md#c04-retained-source-axis) |
| 同源UT1与旋转 | 精确C04名义UT1贯通时标、物理赤道、原生盘、太阳钟与私有codec，两个固定UTC历元的GAST符合独立高精度源目标；explicit-float行为不变。R37四case十二次三端完整业务同版一致，跨版94／9／4／0差逐项保留；完整EOP、物理精度及全域SOTA仍未验 | [保点、首错与有限接受](precision-acceptance.md#retained-source-ut1-round37) |
| C04天极、接收者与地平 | 准入CPO只加一次，保留model s／EO；同一极移W和GAST供WGS84接收者及geodetic ENU。原SOFA4控制19字段及36几何调用符合原门，候选120／120分量过线；名义速度不是完整SI／LOD／站点形变速度，传统宫制及实际大气没有因此获证 | [姿态、原C对照与未验消费者](precision-acceptance.md#modern-c04-eop-round40) |
| 离线logit校准 | 同一非惩罚二项模型在中心／尺度变换后求解，再还原系数和Wald协方差；固定17组合成输入的40数值失配变0，原解析及未定义状态保留。旧分析指纹仍拒绝；一般设计与真实职业预测未验 | [独立数值参考与边界](precision-acceptance.md#calibration-predictor-scale) |
| 印占与推运目标TT | NativeSubject及主限typed context保留TT，印占目标姿态／宫位／sidtime同点传播；推运72及印占12次实际目标从丢点／矩阵不同变为精确源ERFA相符，实际SDK及源框架保持。返照16端点别名与连续not-after义务继续未决，不能据target通过认证完整求根 | [第十四批真实边界](precision-acceptance.md#retained-target-tt) |
| 太阳钟与果老主点 | SolarClockContext保TT，LMT不新增无关Sun资格；原8太阳钟目标失配变0，原SDK／EOT及公开结果不变。果老26目标2→26相符，固定6年／节月成员各2→6，原生TT间隔误差归零；普通solar calendar与未执行分支仍未验 | [第十五批限定传播](precision-acceptance.md#solar-guolao-primary-tt) |
| 原生返照数值终止 | 删去仍有可评中点时的1e-9日早停条件，原24同源热带日／月返照与原作者C求根的TT及精确残差17→24相同，7较差变0；作者1mas线前后双方本来都过。连续物理交点、原16别名与其他输入域继续未验 | [原始反例、因果轨迹及作者比较](precision-acceptance.md#native-return-resolution) |
| 返照分析端点 | 扫描已读到分析端点的精确零残差时直接选该点。固定本命同点控制 46/48 → 48/48。原 16 个标量别名及连续物理根保留未决 | [分析端点和同源作者对照](precision-acceptance.md#return-analysis-endpoint-round59) |
| Marks所选个人盘准入 | 只在选中TimeSpace时起完整共同盘，Marks仍按原变体求共同数据及双方个人盘。原极区共同盘Placidus错误不再阻断两个65°N个人盘；原2普通结果完整保持，选中TimeSpace负控仍拒绝；原镜像与预测资格未升级 | [准入根因与完整三端](algorithm-audit-20261117.md#relationship-mode-dispatch) |
| 原生事件TT成员 | 最近点、去重和多重回归分侧直接消费保留的原生TT；木星同刻3控制由2→3正确，原+1微秒显示保持。四季入宫起盘消费原求根点，连续物理端点、停滞擦触与原16别名仍未验；这是已有主点根因的传播补全 | [事件成员与源比较](calendar-boundary-audit.md#native-event-membership) |
| 印占时间力源公式链 | Natha／Paksha／Ayana保留精确值至同次合计与运动力输出，星战仍截止Hora。36固定输入3,782字段的严格最近binary64差异94→0，原1e-12线前后均过；原阶段Sthana／Dig只作已交付操作数；本轮实际起盘贯通位置链源值，直接字典语义保留，完整六力仍未验 | [延迟舍入与独立FLINT参考](precision-acceptance.md#时间力源值在星战与合计中的延迟舍入) |
| 印占位置力至星战 | 名义／采样起盘保留同次Uchcha、Sthana、Dig源值至星战及Kala。固定16合成组合的224总量、80前置、12幅度与112带符号值符合独立FLINT原参考；原分量／直接控制不变，旧显示分量判据另列。这是已计根因的传播补全，不认证完整六力或SOTA | [源式、历史目标与完整分母](precision-acceptance.md#jyotish-positional-source-chain) |
| 已解TT点的闰秒显示 | 显式点语义与精确半开区间修复名义午夜误用；27次闰秒的270边界观测分类241→270相同，秒60微秒2/134→134/134。原名义接口270项行为保留；一个公开反例真实三端一致，不扩为全部UTC或物理钟时认证 | [固定点与保留门槛](precision-acceptance.md#已解tt点的闰秒边界) |
| 两部日期的间隔算术 | 原始浮点日值先作精确间隔、最后舍入；4096项独立Decimal参考的1115个非最近值消除。256项ERFA岁差对照符合原作者线，不声称逐位等同原C或物理模型改善 | [本批来源与范围](algorithm-audit-20261117.md#solar-point-continuation) |
| 交节主TT点 | 求根者保留标量或两部TT，不从显示日期重建；果老原生节月／立春年与风水原生探针直接消费主点。1687清明、1900立春的原40微秒端点误判修复，参评／历史显示也使用点语义；有限反例不作全域认证 | [原反例、协议与未决](algorithm-audit-20261117.md#solar-point-continuation) |
| 起运偏移与实际wall逆像 | typed来源的精确名义跨度单次半偶量化至偏移微秒；原4项偏移／wall误差、2个假零宽逆像括区间消除。旧details显示、Gregorian及DST政策保持；固定cell的整数斜率有数学依据，跨cell与连续完备仍未验 | [第十二批数值域与有限对照](algorithm-audit-20261117.md#round12-rounding-invariants) |
| 起运整数岁数 | 原始Fraction跨度除以3后直接取ceil，浮点只展示；71给定有理跨度的原13项整数差异变0，其余十字段及float.hex不变。两个旧边界测试改明确calendar-grid源，保留义务、未执行；不据此认证真实太阳交点或预测 | [整数边界与独立参考](precision-acceptance.md#dayun-source-integer-ceiling) |
| 地磁候选方位换算 | 输入方位±已交付D的精确和式先分区、后显示；原1728构造控制320项差异消除，主场field不变，精确角度回执可复核。只证明已交付binary64值的角区算术，不恢复未舍入D或确认现场朝向 | [地磁数值与现场边界](interpretation/fengshui/geomagnetic-reference.md) |
| 无原生引擎的宫轴与地平 | 回退真黄道射线、真赤道、交角与GAST共用原始TT／UT1和同源框架；42个固定同源控制的轴值77处／高度42处超线消除，合法公开反例的日夜盘误判修正。默认UTC近似UT1、远期物理姿态与其他来源限制继续保留 | [框架根因与协议范围](algorithm-audit-20261117.md#offline-frame-continuation) |
| 星历参考点身份 | 当前DE441回退按实际源分类本体中心、行星系质心与理论交点，不再把已知点身份称为未解析；v2回执附实际JPL来源。三模式原数值子树不变，点身份明确不授予物理精度认证 | [来源定义与完整差异](algorithm-audit-20261117.md#source-identity-continuation) |
| 太阳钟与农历日时 | 派生太阳钟仅解析一次；农历读取已解析的日期，交节仍用原民用瞬间。固定8个输入的原5项钟面漂移及其中4项离散错误修复，同队列符合sxtwl／HKO与独立取数；纽约及Apia完整／投影三端一致，不据此认证全部时区或均时差物理精度 | [太阳钟边界](calendar-boundary-audit.md#派生太阳钟与民用时区的边界) |
| 太阳地平线 | 自动路径复用DE440原始记录及域外有界DE441，完整有向序列服务于印度太阳日和西占行星时。完整10288个固定窗口、14459事件与独立原始JPL符合原1毫秒TT／UT1线，源码与Python3.10安装包最大约0.081毫秒。配置的JPL文件现由实际文件读数与完整TDB光学处理，192窗364事件的源码比较最大约0.040毫秒。原生Moshier30／32项同源失败和原生JPL364项时间失败均保留；最终版本、安装和三端按实际检查另记；部署与现有聊天进程另验 | [太阳地平线参考与未通过范围](../tests/data/solar_horizon_v1/README.md) |
| 西占九分度 | 所选Parashari映射使用给定浮点数的精确值判定3度20分半开区间，消除10度／20度落入前一份的错误。1296000项一角秒网格原24项错误已修复；另核324个边界邻点、12288个固定留出及两个书中例。固定PyJHora同边界也误判，仍以具名原表为准；不认证Hellenistic历史归属或现实预测 | [九分度来源与数值范围](western-astrology.md#九分度的来源与数值边界) |
| 主限后续算术与时点分类 | 推进弧、坐标环、容许度和相对岁数保留未舍入值，不让展示舍入参与后续运算。固定14个Ptolemy热带黄道场景的原4分类、45容许度及154法盘经度失败保留；修复后按相同独立操作数和门槛均通过。原天球模型、年长及0.01年窗口未改；完整原典、其他方法和物理／预测效度另验 | [主限坐标](western-astrology.md#推运返照与主限坐标) |
| 西占显式太阳钟面重置 | 沿用已发布的改变计算时刻约定；6个固定民用／重置服务请求在相同SwissΔT条件下满足原0.2毫秒时刻线及54个天体分量线。首次参考误用UT1=UTC的3个时刻失败另行保留，未修改生产时钟代码；不认证实际出生时刻、实测地球自转或历史钟时精度 | [钟时约定](western-astrology.md) |
| 古典五点尊贵汇总 | Almuten局部结果返回同次昼夜输入、方法、来源范围和参与／缺点列表；固定Chaldean平手次序明确，空集不判为历史程序无命主。四覆盖状态只验交付，最终严格子树三端与完整结果逐值一致；旧分数不变，完整Ibn Ezra程序与原数值差异仍未验收 | [方法与来源范围](western-astrology.md#五点本质尊贵汇总与方法范围) |
| 八字本命 | `engineering_index` 保留 `season_root_revelation_relations_v12` 的原工程政策档与数值档；子卯政策v4分别处理一子二卯实体、实际会合及清楚原字的丙子月官，不调权重，原17差异与2约束违规保留；`classical_adjudication` 独立记录原典力量未决 | [八字判定](bazi-assessment.md)／[月官与实体范围](algorithm-audit-20261117.md#month-officer-continuation) |
| 八字藏干与特殊日事实 | 四柱六个位置对的藏干五合、所选禄位往来、缺中神拱候选与原典十组拱禄／拱贵分列；填实可排除，透干不自动增强。四生分类与实际驿马分开，日贵所需昼夜与既有6—18时参考分开；名单和有限符号对照不替代完整成格或力量验收 | [八字关系核对](bazi-relations-audit.md#后续藏干与特殊日事实层) |
| 八字柱内与柱间事实 | 明干至本气和每个藏干的方向分列，不以两类相生冒称完整覆载；六个柱对的同柱、干四冲、支六冲各自交付。120个单柱与3600个有序甲子对按全部相应位置作独立字面对照；原力量差异和约束违规保留 | [字段调整与范围](bazi-relations-audit.md#柱内与柱间关系的后续核对) |
| 八字专题 | 共享原局证据，按专题选取实际星位、格局前提与运年关系 | [八字专题](bazi-assessment.md#专题星位与结构候选) |
| 双人八字 | 各自盘面、逐柱干支关系、定向刑及双向十神 | [双人八字取证](compatibility-scoring.md) |
| 八字时运 | `single_layer_natal_budget_retention_projection_v2` 投影单层冲刑及唯一大运干合绊对既有预算的影响；不添加时间干支能量，未解会合或争合保留阻塞 | [时运与历法](bazi-timing.md) |
| 太阳交节 | 文件源保持原生TT求根；缺文件且原生探测返回Moshier时改用具名内置DE441同源视位置。原14904项及1200补充交点对独立原始JPL／CALCEPH／Skyfield进行角度与实际求根对照；原DE440一秒门槛及额外诊断失败分开保留。不是全时域、绝对UTC或SOTA认证 | [太阳后端](solar-backends.md) |
| 交节时刻不可用 | 移除1900年线性固定气回退；所选模型无根或来源未核实时返回明确错误，不用近似边界继续推断年、月或宅运 | [太阳后端](solar-backends.md) |
| 解析星历回退 | 同一连续有界DE441源提供接收地球／太阳及十个物理目标；源p／v／a、地心TDB时钟、隐式光锥、有限源偏折、Lorentz及显示旋转共同求局部TT日速；保留可用的其他原生天体 | [西占来源与差距](western-astrology.md#离线轨道近似的来源与差距) |
| 原生辅助归算的框架 | 复用明确的原生坐标变换，删除近共面天体位置反求；734组原作者C单位轴对照符合原门槛。3848组原源算术参考符合原线，但相对旧实现1475组误差略增，保留全部记录；原C差分116失败、330未稳定及194逐点劣化仍另列 | [反求病态与验收](precision-acceptance.md#原生框架反求病态修复) |
| 无原生库的Lahiri原点 | 完整均原点与77项章动共用实际轨道TT，日速扣同一原点解析TT导数；24532个TT与显式原生Lahiri符合原数值线，旧线性公式退役；不改变物理轨道失败 | [分项验收](precision-acceptance.md) |
| 历史UTC源算术、有效域与反解 | 1960–1971年共用发布十进制仿射偏移，负调整删除的日尾标签拒绝；同一所有者处理精确TT点和显式IEEE语义。原17842点加256控制的六个入口按各自适用域核对，均符合预声明分类与残差线；微秒舍入保持在合法源段 | [分项验收](precision-acceptance.md) |
| 西占回归与界推运 | 回归在有限窗口内按实际黄经根选择，停滞日格分段；界推运采用精确弧与半开区间，保留所选界表和时间钥 | [西方占星](western-astrology.md) |
| 西占派生几何与方法选择 | 调波分座、合相，年龄推进点归宫与年度标记，波斯向运排序和截取均先使用未舍入量；时间钥等具名方法在请求边界校验，不静默替换算法 | [西方占星](western-astrology.md#推运返照与主限坐标) |
| 共享等分宿区 | 27星宿与28等分研究宿区按原始双精度值的精确有理数判定半开区间；消除40°、90°等整边界落前一宿及同次印占字段冲突，不更改具名不等距宿界 | [算法覆盖](algorithm-coverage.md) |
| 派生交点 | 南交／Ketu的精确对点关系保留到分座、分盘、星宿和归宫；公开经度仍为浮点显示值，不增加原坐标的物理精度 | [西方占星](western-astrology.md) · [印度占星](jyotish.md) |
| 六爻条件传递 | 本位金化巳的长生／回头克资格未明时，伏神受生门槛和生扶来源保留待决；已确认阻断及月破日克无根门槛分别核对 | [六爻审计](liuyao-depth-audit.md) |
| 卜卦事件序列 | 停滞、成相的根区间决定能否严格排序；重叠及提问边界保留未知，不由局部模式直接断成事 | [西方占星](western-astrology.md) |
| 印占六力 | 确定量与未裁定项分列；未知星战胜负不抹掉可确定的绝对量，Cheshta双分支仅精确同值时交付共识值 | [印度占星](jyotish.md) |
| 印占分盘与位置力交付 | 分盘直接交付同次计算的盘内度数；位置力摘要、所选profile及Rupa分别从同一精确分量和交付。固定118224分盘控制对及7168组分量的原差异消除；不认证叶分量的完整未舍入公式、原典唯一性或完整六力 | [独立FLINT与保留失败](jyotish-algorithm-audit.md#盘内度数与位置力合计的后续对照) |
| 太乙异本 | 阴37／43／44并列《金镜》与米泽藏《武经》六字段，保留原分歧、原图身份与比较范围，不以异本替换默认算法 | [太乙异本](taiyi-sanshi-audit.md#阴374344局的具名版本书影旁证) |
| 奇门置闰日期与计日 | 调度消费三个节气的本地整数日序，索引只作显示。私有年 0／10000 日期载体恢复四个原拒绝。所选四库本明例按首尾九日取序差八，三处置闰共用，现行回执为 `2.13.0`。逐日局表 3,685/4,286 → 4,286/4,286，次年重叠 161/204 → 204/204，两入口的三端定局 57/75 → 75/75。夏至锚异法、前置十二月三日差及原九项典籍未决仍有独立记录 | [端点与日序范围](calendar-boundary-audit.md#qimen-private-calendar-guards) · [首尾计日来源及对照](qimen-depth-audit.md#qimen-zhirun-inclusive-days-round57) |

公开盘式的名称可能含版本号或 `legacy`；它们表示明确选择的盘式。当前领域服务不依靠退役源码回放或旧输出哈希判断正确性。

汉堡太阳弧新增[源弧投影修复](precision-acceptance.md#hamburg-retained-source-arc)：同18合成输入的原179差异消除，实际受控库见证及两请求三端一致；只接受一个数值根因，累计22。原方法钥匙、来源全貌、物理／预测及全项SOTA继续未通过，项目测试按超过50项后执行。

行星弧已[补全同源位移的精确传播](precision-acceptance.md#planetary-retained-source-arc)，原九例的16成员、30位置字段与34精确map差异消除，新增根因0、累计仍22。显式原生太阳地平四窗当前复核仍有两项超原1毫秒线；古典来源、物理精度及全项SOTA不因此改判。

显式Moira[来源提供器](algorithm-audit-20261117.md#moira-explicit-source-provider)补齐外置源神煞与给定宿界事实：原Java444×33神煞及独立整数504角度对照相符，原生集成保持缺项与陆位证据分离。本批只接受一项能力，累计25；现代SDK对C的42向量／62分量／7修正点原逐位失败保留，未接入builder或公开默认。全部算法／定义的语义清查、专业独立验收及SOTA仍未完成；测试按超过50项后执行。

## 仍未通过的项目

第十六批对八字HJ06／XQ30的两次实际服务观察继续保留旧差异；HJ06的三条强档覆盖依次可接替，仅删首条不足，全删仍为数值中和，不能据此恢复原弱注释。尚缺可普遍执行的有效根力、寒暖与承接规则；未调权、特判或清理反例。金口诀P35／P52日时异文仍不能唯一订正；六所有者清单归层不计新算法通过。详见[本批根因裁定与职责范围](algorithm-audit-20261117.md#root-force-and-cycle-inventory-continuation)。

2026-11-11的[历法边界核对](calendar-boundary-audit.md)修复了辅助年份、UTC标签和流月完整瞬间的实际故障。固定4392个Temporal算术案例与336个原生求根比较符合各自预声明门槛；未把同源星历或未来钟时假设写成全范围物理精度认证，以下未通过项保持。

2026-11-11补核[八字离散规则与日序](bazi-relations-audit.md)：固定第三方表的十神、藏干、长生与时支相符，纳音两项名称修正后60项相符；五合输出改为相合与候选化神。两套独立实现的1900—2100年73,414个民用日序相同，标准路径相同；原偏移路径全部不同，已退役并保留全部原差异。这些结果未消除下表的八字力量与取用缺口。

| 范围 | 必须保留的分歧或缺口 |
| --- | --- |
| 八字 | 367记录／321不同输入的工程政策与原标签比较仍17组不同，3个集合约束仍2项违规。123条有三档来源的记录尚无通用原典力量裁定，单列未验收；244条无三档来源不算相符。17组原页已复读，语义疑点与缺少充分规则分别保留，不改原标签或借未知消除旧分歧 |
| 原版及退役Moshier太阳范围 | 原版Swiss Moshier的96点中12项仍超原1秒线；退役修订模型更广原队列的15项一秒失败也保留。当前具名DE441的限定对照另列于[本批基线](algorithm-audit-20261117.md#solar-point-continuation)，不覆盖旧失败或认证全时域 |
| DE440底层记录与源算术 | R29原54点的12域／6record差异及原144分量比较保留。当前保点与补偿实现对原54输入的域／record／精确x失配均0，42域内252位置／速度符合原最近偶目标；原24共同目标144分量为106等误差／38产品较小／0原生较小。30项原排除、native内部record未直接观察、公开可达和物理精度限制保持 | [原失败](precision-acceptance.md#de440-original-record-boundaries)／[当前有限对照](precision-acceptance.md#compensated-source-polynomial) |
| UTC来源与表示的剩余资格 | 原浮点54失败及原始参考保持不变；同输入在修正后的普通UTC有效域另验，50项唯一、3项不可表示、1项域外，当前入口与源分类相符。负调整删除的两个原输入现拒绝。原506点仍有76项不可表示和4项UTC前未裁定；其中4个旧可表示点落入不超过3纳秒的源模型缝隙，继续未知。未以微秒显示、C04插值或原生库一致证明历史物理钟时精度 |
| 原生近太阳约定与压缩月球来源 | 原native水星透明日盘约0.892角秒差及Swiss月球约0.002607角秒／来源日日速超差保留。显式不透明太阳坐标的原7070七曜位置及新增9点过原0.02角秒线；完整DE441精确源的原135个可评月球样本及新增12点满足原0.002／0.02线，原2项缺证不改判。参见[分项精度验收](precision-acceptance.md) |
| 解析回退的全范围位置与数值稳定性 | 当前完整TT导数重跑原40380位置、36140现代日速及固定2560／1280留出，均符合原外部线；240新导数留出加10原诊断点符合独立90位完整映射的1e-6角秒／TT日线。旧两模板仍36139／36140符合，土星原失败保留；其解析日速与局部参考相符，但最大与原Swiss位置0.02日五点参考的差增至约0.407150角秒／日，不能据此称全部更接近第三方或SOTA。太阳盘内13项导数消减失败已修复；旧ERFA二进制8项与更高精度参考的分歧不改判。全部原参考与门槛保留 |
| 奇门 | 核心51个函数及7个局部定义已逐体审读；共享地盘／领导星门并修复太阳标签错取时柱，来源现逐卷固定。共享农历和日干支73414个民用日期七字段与Sxtwl相符；独立程序38组完整排盘仍8组定局不同。原表2格差异与全部9项来源未决保持，完整原典与SOTA尚未通过 |
| 太乙 | 全144局环路与两算算术有条件证明；原《金镜》11个两算、3个始击位置分歧保留。源位置重算解释阴43／44两项，却在阴37新增冲突，净多1项相符、仍10项不同；不据数学约束冲突裁定版本优先级。年度长周期另核720原表单元687相符，直符中元33格分歧保持；见[年度原表](taiyi-sanshi-audit.md#年度长周期与原表) |
| 金口诀 | 原64课仍46合、16异、2缺日；已知部分约束不能恢复唯一日期或通过整课验收 |
| 河洛与参评 | 月表来源冲突、部分文字、百刻现代日期原点及完整取用仍有未定前提；具名计算方案不代表全书已裁定 |
| 印占 | Moon／Mercury部分原文口径及完整Cheshta来源模型未统一，不拼接作者或制造阈值得出唯一完整六力总分 |
| 风水地磁与玄空 | WMM2025精确WGS84内核在固定2564输入的17948分量上有独立多项式与Arb舍入证据；原12点84项仍相合，原100点末位差异由旧实现354项变为325项，原C常数口径另有340项差异，均保留；见[主场求值](precision-acceptance.md#wmm2025的精确wgs84主场求值)。玄空216项下卦比较的3项正文及1项盘图分歧、书影补证分别保留，不作全书通过 |
| 人类图完整原队列 | 原生Swiss位置1项及Moshier诊断2238项超差仍保留；显式太阳点质量模型在全部原24000固定TT位置符合原2角秒线，最大0.038386角秒；候选全部1200设计根在原5秒线内，最大0.055442秒；自身根位置24000项在原2角秒线内，最大0.053665角秒。原典模型优先级未定。原生两侧各1200根符合原5秒线；官方文字与完整解释仍未通过 |
| 物理精度与现实效度 | 近太阳视位置、后端有效范围与时标须按实际回执评估；分数、传统判断和可复现性均未建立现实预测认证 |

上述数字属于已登记的固定资料范围，不能推广成整个体系的准确率。未读取、缺失或未裁定的项目保持未知；原始失败、参考与门槛不能通过清理改判。

## 维护与历史材料

当前文档维护现行行为、依据和限制；独立参考、反例及未裁定项保留。逐轮日志、旧算法回放和迁移哈希链已退出当前维护范围。清理与恢复规则见[仓库维护](repository-maintenance.md)。


## R41现行非零EOP消费者观察范围

新增[宫位／地平坐标有限对照](precision-acceptance.md#native-eop-consumers-round41)：原200查询与12 builder全部完成，90组可计算宫位、33组地平坐标及12组构造参数符合原固定门；原5个极区ERR与fallback保留，候选错误状态一致。72个R／C／T落宫仅为原C诊断，尚缺精确实参的独立数学验收。候选两进程都漏预绑两个实际加载的astronomy包文件，因此本轮运行来源资格未通过，不倒签或重跑；有限数值符合不能授完整算法／物理／SOTA通过。

当前清单5110职责组／13862细职责，2650定义仍待具名，独立语义算法总数未定；本轮来源PDF原字节补证与目录补登均不算新优化。生产源码未改，累计仍33，超过50前继续暂缓项目测试；全部旧失败、传统分歧、完整太阳光路、预测效度与全项SOTA缺口保留。

## R42当前清单与落宫坐标交付

当前[算法清单](algorithm-inventory.md#western-high-impact-source-inventory-round42)为5133职责组／13910细职责，2629定义仍待具名，独立语义算法总数仍未定。本次补入21个既有定义、23组48职责并同步两个精度文件的实际锚点；清点数字不等于独立算法数或专家验收数。

[落宫坐标修复](precision-acceptance.md#house-coordinate-rounding-round42)消除原生容差覆盖高精度结果：原72项独立Arb对照的31项坐标舍入失败全部消除，工作相位、宫位和原目标保持；公开两请求、两版、三端共12次调用均成功，同版完整业务相同。跨版R每端11差、C每端17差全部保留，Schema与所选工具定义不变。独立数学保存结果复核无问题；公开主分类器原217门中的1项快照分类失败保留，另行逐段复核六份快照，仅有与结构化坐标及action逐值相同的变动。root按此有限范围接受一个原生保留舍入根因，累计33→34；案例、定义补登和回归资料不另计。有限输入的舍入证据不授全部宫制、物理或SOTA通过；T全域1mas偏移的专业来源仍未通过，需独立修订。R41来源漏项、全部旧失败和传统／预测限制保持，项目测试继续等待累计独立优化严格超过50。

## R43的T相位修订进展

当前[源码清单](algorithm-inventory.md#topocentric-precision-ownership-inventory-round43)为5143职责组／13941细职责，定义具名4811／7430、待名2619。T偏移死绑定已移除，求根的归属与舍入停止义务已按当前源码登记；另补登既有太阳8项、月球2项定义的来源与职责。这些结构变化不增加独立优化计数，独立语义算法总数仍未定。

[T未移位几何](precision-acceptance.md#topocentric-unshifted-round43)的原72例修订后八类数值门全符合，R/C48完整原始记录保持；T公开两版三端6次调用成功，同版完整业务相同，独立保存审阅已完整归类每端125差及快照内对应变化，Schema／声明／请求跨版不变。完整63282例的参考v2已取得61074个非极点目标的保存证书资格，2208个原生极点仍未重新验收；原版557项未知与失败尝试保留。完整产品BEFORE原门发现472项精确宫号错误、实际60602/61074通过；修复精确代数边界与数值括区交付判侧后，同一63282例单次AFTER的61074个非极点原门全过，472原失败逐ID修复，2208极点仍未获资格。独立保存复核符合，原附加诊断仍保留。最新源码的原72项八类数值门再次全部符合，但T24项根区间宽度变化令原结构相等门失败，不能称所有门通过。

精度修复的公开新窗口中断，原尝试3／返回2及缺失CLI、最终来源收据保持；独立新窗口只补充1次CLI成功。保存结果支持同版累计跨窗口业务一致，包含快照且仅排顶层run_metadata；不授原三端同窗完整资格。每端相对偏移修订版本109处业务差保留。回归fixture已安装并经独立保存审查，新增8条精确ignore例外允许必要固定输入／目标进入版本控制；数值gold不变，尚未暂存、提交或执行测试。root已接受T无来源1mas偏移与T求根／宫界稳定性两项有限根因，累计34→36；T24原结构宽度失败及其他历史失败、未覆盖项全部保留。太阳直接光路组合的原16输入已完成独立参考与产品对比，原门限16/16符合；这不授事件／折射／完整物理／全局SOTA接受，也不增加优化计数。下一优先是当前公开Timing来源资格与R35保留的61／63严格门，以及归档现代宿曜backend的准入问题。项目测试继续按严格超过50项的原门暂缓。

## R44公开快照与当前验收边界

[快照表示修复](precision-acceptance.md#snapshot-public-boundary-round44)在渲染前复用既有公开字段策略。固定择日请求两版各三端完整返回，原每端27项、共81处快照完整性字段披露修复后为0；独立从BEFORE重建的期望文本与全部AFTER结果完全一致，其余完整业务逐类型及浮点位相同。跨版真实业务差仅为每端的`snapshot_text`，Schema、声明及请求保持；指导description、运行metadata与交付manifest的全部差异分别保留。同run文件与正文一致。实际仅调用此择日请求，没有其他工具、导出或分页实调。

root接受一个有限工程表示边界根因，累计36→37，未增加数值、原典、物理或SOTA信用。75调用／18定义、五个泛型消费者、helper和C04指导不另计根因。两个新增回归仅编写，生成合同的两条旧说明仍待原门之后同步；37未严格超过50，项目测试及生成检查继续未运行。原R43中断窗与所有数值／来源失败保留。Timing静态复核没有找到可授新信用的当前根因，原61／63不改判；归档现代宿曜backend当前不在生产树，不为消除原42／62／7失败而恢复退役路径。PMO原22个时标记录的原页转录相符，但22项30秒门失败及源取整政策仍未决。

本轮另为12个既有八字P1函数补登34职责，独立复核后修正7个新增实现文件映射及3行过宽的公开消费者。当前清单5156源码位置组／13978职责，5575文件符号映射／731实现文件；7431定义中4824具名，2607仍待名，分布598文件。P0/P1/P2/P3/null＝622/733/461/1464/1876。补名、书目及消费者修正均不增加算法或优化信用；语义算法总数仍未知。原367来源／321输入、17等级差异／2约束失败及4局部冲向差异保持，未裁原典力量不算通过。

## R45三元有限对照与共享源职责

[三元固定对照](precision-acceptance.md#bazi-three-origins-round45)已实际执行钉版本6tail/lunar-python原作者模块与当前实现：固定10年干×12月支×12时支共1440组给定元组，4320个胎元／命宫／身宫柱字符串严格相等。独立保存审查44项通过，源文件、父子运行绑定与调用范围已核对；构造器1440次由固定循环推得，不作单独测量。候选目标阶段无历法／原生调用，导入阶段实际一次set_ephe_path另记。结果只覆盖所选离散柱算法，不认证真实日期、完整结果、公开三端或古典唯一性；命宫原文亥／子起序、胎元异法及身宫直接原典缺口仍见[来源限制](bazi-relations-audit.md#bazi-three-origins-round45)。旧八例未运行，“300随机盘”旧注释只更正来源说明，不改可执行AST、案例或断言。

[共享出生钟与Moon源职责](algorithm-inventory.md#shared-clock-source-round45)新增十个既有定义、十组28职责，P0九组、P1一组；只是影响排序与职责登记，没有新的数值或专业验收。当前清单5166源码位置组／14006职责、5585文件符号映射／732实现文件；7431定义中4834具名、2597待名，分布597文件。P0/P1/P2/P3/null＝631/734/461/1464/1876；模块绑定及顶层语句队列不变，独立语义算法总数仍未知。

本轮没有生产修复，新增独立根因为0，累计仍37。八字离散12项与西占推运32项的静态审查未建立新的当前缺陷；原17等级差异／2约束／4冲向差异及33诊断输入仍未裁定，不据有限三元一致补齐力量、取用或完整原典。R43的24项结构宽度失败、2208极点、原公开中断窗、现代42／62／7、B1严格1／2、Timing61／63、PMO22项30秒门，以及太阳完整光路、pre1984 CPO、Fortran7、物理／预测／全项SOTA缺口全部保留。37未严格超过50，项目测试、collection、CI、格式／类型、checker、build及生成合同／检查继续未运行；两条旧Field说明和C04指导的派生合同同步仍待原门之后处理。

## R46固定时标、运限与八门对照

C04节点前错误姿态回执7→0，LMT六条边界归属3/6→6/6，两条`60.5`控制维持2/2，分别补完R40的姿态回执及既有UT1提前舍入根因。另有两项具备独立根因证据。LAT原探针从域外失败，修后收敛于USNO给出的域内根区间。达沙网格改用精确对跖，每端217/243→243/243，仅26个范围端点改变。隔离前后、三端分母、原失败及同模型残差见[固定验收记录](precision-acceptance.md#bounded-acceptance-round46)。

紫微20例公开60/60成功，所选iztro 2.5.8口径每端2,440/2,440，iztro 2.6.5对保存服务结果仍有18项晚子差。奇门复用原38盘，在同局30盘的240格上，FateBridge保存结果240/240，Kinqimen 221/240，定局与原典冲突继续保留。[紫微版本和岁序](ziwei.md#horoscope-boundaries-round46) · [八门固定对照](precision-acceptance.md#bounded-acceptance-round46)

按所选TZif当地类型判定成员资格，修复剑桥湾`−07:00`已知成员被拒及麦夸里岛`−00`被误收。按区间内转换点切分，独立修复麦夸里岛有效起点提前3,600秒的问题。固定时点9/11→11/11、区间3/11→10/11、宿曜日期4/7→7/7，六爻、宿占、梅花四请求的三端结果0/12→12/12。`Factory`名称入口原拒绝保留。大运两个扫描复用类型资格，固定直接27/42→42/42、公开6/18→18/18。已观察到扫描计数和聚合，未来逆像事件与连续完备性仍待核对。[民用钟与大运原门](precision-acceptance.md#bounded-acceptance-round46)

本轮认可当地类型资格、区间切分、LAT试算域、达沙精确对跖四项独立根因，累计37→41。当前5,194组、14,076项职责，7,435个定义中仍有2,574个待具名，独立语义算法总数未知。各动态对照在隔离源码中执行，合并工作树逐文件核对。完整SOFA姿态、C04早期8,035对数值的发布语义、Fortran 7项、LAT全域单调性及此前未通过的门槛继续保留。项目测试及派生合同按累计独立优化严格超过50项的门槛暂缓。[细粒度清单](algorithm-inventory.md) · [根因及冻结证据](historical-evidence.md#evidence-20261119-round46-accepted-root-issues-json)

<a id="round48-consolidated-validation"></a>

## R47–R48 的独立对照与集中验证

R47 累计接受 47 项。新增范围包括大运闭区间右端、缺时顺延原像、TZif 固定尾段、印占历史 UTC 来源的生效域、行星时搜索与 C04 有效域的交集，以及六爻民用区间的 UTC 年界。独立对照分别核对了成员、搜索成本、来源资格和求根误差。其中四日行星时搜索的固定四入口比较由 2/20 到 20/20，六爻年界的公开三端比较由 6/12 到 12/12。 [固定对照](precision-acceptance.md#dayun-closed-inverse-round47) · [根因及前后证据](historical-evidence.md#evidence-20261119-round47-accepted-root-issues-json)

R48 的前四项独立修复涵盖 IANA `Factory` 当地类型、出生区间民用切点、分钟样本的同一时区投影、小数秒偏移回执。六爻年界节月复核随后补齐，固定公开比较由 6/12 到 12/12，沿用 R47 的同一根因。三个 C04 节点姿态固定对照均通过。发布者资料支持 1984 年 1 月 1 日的 CPO 来源起点，前 8,035 行零值的发布编码含义仍待裁。[固定对照](precision-acceptance.md#factory-clock-admission-round48) · [C04 发布语义](historical-evidence.md#evidence-20261119-round48-eop-publisher-semantics-followup-result-handoff-md)

R48 补跑了全部 7 项 IERS 原作者 Fortran 控制，保存 29 个输出。其中 23 个与作者印值舍入后的双精度位相同，六项残差逐项保留。作者注释未规定数值门槛，R40 的历史 0/7 保留。1962 年首节点与 2016 年末闰秒补齐了精确 UTC 标签及原 IEEE 输入的独立钟时参考。[作者程序和钟时边界](precision-acceptance.md#iers-author-controls-round48)

近极升落的 DE440 独立对照为 10/10，明示 Moshier 保持原 1 ms 门的 3/6。原作者地球速度的分母单独换成实际采样间隔后，六个局部交点移动约 264 至 528 ms，原高度门由 30/30 到 0/30。现有证据支持原生函数的多次变号和求根择区差，FateBridge 求解器仍缺有独立依据的修订方案。[太阳升落各臂结果](precision-acceptance.md#polar-solar-event-extrema-round48)

第 52 项修复按同一 TZif 字节索引未来的周期转换，同时保留 `ZoneInfo` 作为偏移与当地类型的所有者。597 份显式表保持一致，190 个周期尾段共 152,380 个未来转换秒与独立参考一致。原 30 个直接窗的读取成本门从 13/30 到 30/30，6 个民用区间从 0/6 到 6/6，两条公开请求三端从 0/6 到 6/6。各端原始业务和 Schema 保持相同，年 10000 的两个补充原像均符合独立端点。最初辅助年启动器的事后路径复验失败及恢复原字节的补充资格均保留。 [对照分母与来源](historical-evidence.md#evidence-20261119-round48-tzif-recurring-tail-final-handoff-final-findings-md) · [工作树合入](historical-evidence.md#evidence-20261119-round48-tzif-install-workspace-install-json) · [根因账](historical-evidence.md#evidence-20261119-round48-accepted-root-issues-json)

安装包原先漏收 C04 方向表，解包 wheel 读取失败。修复后的 wheel 和 sdist 各含 1,525 个包内文件，解包入口读取全部 23,638 行 C04。发布成员检查现在接受完整包并拒绝原漏包，工作流的 Python 验证片段在仓库外从解包 wheel 执行通过。两项打包和发布校验修复另行记账。实际云端发布、约 661 MB 的上传包额度仍待核对。 [打包前后对照](historical-evidence.md#evidence-20261119-round48-project-checks-distribution-assets-result-handoff-md)

原 2,208 个 T 宫制地理极点的坐标、宫号、精确相位及回执与 Swiss 2.10.03 作者 C 对照全部相符。该证据限定于同源原生约定。连续几何、旋转模型极点和公开可达性仍待核对，R43 的 24 个旧结构宽度差保留。 [原生交付对照](precision-acceptance.md#topocentric-native-geographic-poles-round48)

集中检查已在当时源码上完成 mypy 1,169 个文件、文档 125 份、清单和生成合同检查。初次全量 pytest 使用 Python 3.12.13，含本地资料用例，日志保留已出现的失败与错误。该快照的虚拟环境链接到工作树，普通导入与未显式绑定源码的 `-I` 进程可能选取不同源码。将按失败堆栈和隔离复验区分影响。六爻后续改动与当前完整快照的验证另记。 [集中检查与首轮日志](historical-evidence.md#evidence-20261119-round48-project-checks)

隔离集中复验覆盖原来的 288 个节点及 79 个兄弟控制。原批 261 通过、27 失败。迁移后，同一批 288 个节点全部通过，兄弟控制通过 77 个，余两项为 2024 年西占公开三端的 TT 入参断言。复验共 365 通过、2 失败，三个 worker 的收集顺序一致，运行前后源码和环境绑定无漂移。[节点配对和复验结果](historical-evidence.md#evidence-20261119-round48-project-checks-pytest-post-migration-observed-results-json) · [失败堆栈](historical-evidence.md#evidence-20261119-round48-project-checks-pytest-post-migration-observed-pytest-log)

随后核对 2024 年热带和恒星黄道请求的三端实际调用。78 次本命宫位和地平计算均收到精确 TT。旧探针还纳入 12 次行星时升落采样，误把与本命 TT 相差约 14.201 微秒的搜索端点作为断言对象。探针按每端的本命宫位和地平调用归属取值后，原四个节点在隔离版全部通过，其中两条 1800 年对照继续通过。原集中复验的 365/367 结果单独保留。本项修订测试归属，新增生产根因为 0。 [实际入参归因](historical-evidence.md#evidence-20261119-round48-project-checks-historical-gast-tt-attribution-qualification-json) · [四节点对照](historical-evidence.md#evidence-20261119-round48-project-checks-historical-gast-tt-attribution-four-node-observed-results-json)

人类图出生钟和周期参考共用插秒前偏移下的精确 TT，各自的标量最近偶数舍入由 109/135 到 135/135。原 SOFA 200 微秒门、有理排序、标签和偏移见证均保持通过。三例前后共 18 次公开调用，五份 Schema 对照相同，三份原 REST 结果仍可回放。隔离回归 316/316 通过。此项补齐既有单次舍入根因的消费者，R48 独立根因仍为 52 项。 [固定参考与回放](precision-acceptance.md#human-design-leap-epoch-round48)

<a id="round49-shared-clock-admission"></a>

## R49 的钟面与回执对照

第 53 项修复使梅花 HKO 日期对照和 NAOJ 次级对照共用原有严格钟面解析。两条路径的固定反例从各 6/12 到 12/12，旧可表示标签的 201/201 和不可用标签的 5/5 原门保持。异常标签来自领域反例，公开生产者的有效结果仍由其自身源模型比较。 [固定门、观察器勘误与范围](precision-acceptance.md#meihua-solar-clock-profile-round49) · [根因账](historical-evidence.md#evidence-20261119-round49-accepted-root-issues-json)

第 54 项修复让 C04 回执按准入的 TT／UT1 实参报告时标差、日内项和残差。直接对照从 413/428 到 428/428，原 200 微秒准入线保持。前后各六个公开响应的 318 项保存值检查均通过，同版 REST、MCP 和 CLI 业务一致。初次公开臂的三次返回及超时单独留存。 [独立对照及公开覆盖](precision-acceptance.md#c04-supplied-pair-receipt-round49)

第 55 项修复在归一化前保留钟面和偏移的完整小数。参评与六爻的原九条请求在每个公开端各有五条精确时刻、七条正确归属。修后各端的六条可表示时刻及归属全部相符，三条不可表示时刻均明确拒绝。`as_of` 的原八条、补充十三条、词法十五条及公开十二条均符合各自固定门。参评首次候选误收的内部 `Z` 在终候选恢复原拒绝。 [固定分母、三端对照和兼容范围](precision-acceptance.md#exact-shared-iso-clock-round49)

果老与德国盘专用入口及 `astro_chart` 的相应盘型依同一精确目标时刻规则准入。固定模型对照从 32/42 到 42/42，公开对照从 12/24 到 24/24。德国盘原版曾将超过 150 钥年上界 0.1 微秒的目标截断到边界。十二个可表示的公开控制保持业务和 Schema 相同。此项补齐已有共享 ISO 准入根因的消费者。 [固定输入与三端比较](precision-acceptance.md#astro-aware-target-clock-round49)

宿曜已知出生钟时也使用同一验证。UTC+08 独立历日对照从 9/11 到 11/11，相性三端从 18/24 到 24/24，宿占旁路对照两版均为 6/6。UTC+09 的覆盖来自共享调用链审读。 [固定历日、三端和错误合同勘误](precision-acceptance.md#sukuyo-known-clock-precision-round49)

DE440 地平光路和两条节气入口按有理 TDB 选择接收和发射记录。地平七点的全部记录归属从 52/56 到 56/56，节气十点从 51/60 到 60/60。节气黄经的原 `1e-6″` 门两版均为 10/10，发射时刻的独立 1 飞秒诊断仍为 16/30。固定卜卦和历史玄空的前后版三端业务及 Schema 相同。近接缝皮秒级归属来自直接对照。两项均归入既有精确历元传播根因。 [地平光路](precision-acceptance.md#de440-solar-reception-seams-round49) · [节气光路](precision-acceptance.md#de440-solar-term-seams-round49)

显式 SPK 直接按 DAF 描述符的原始相对秒判断段覆盖。独立段端点对照从 12/18 到 18/18，标量 TT 从 11/12 到 12/12，黄经原门两版均为 4/4。六爻公开恢复为 12/12，保留最初 0/12。公开样本覆盖正常消费，段界反例由直接观测见证。 [端点对照和公开范围](precision-acceptance.md#explicit-spk-descriptor-seconds-round49)

第 56 项修复按原生 Swiss 的搜索顺序读取辅助文件并记录德国盘根数来源。作者库固定目录顺序从 7/10 到 10/10，端点处置从 40/50 到 50/50。人类图公开对照从 3/12 到 12/12。德国盘来源状态、文件名和索引从 6/9 到 9/9，内部身份从 5/11 到 11/11，原公开哈希门仍为两版各 3/9。 [固定目录、来源和三端业务](precision-acceptance.md#swiss-ephemeris-path-ownership-round49)

共享恒星加载器补齐相同根因的星表与地球星历来源。作者库归属从 8/16 到 16/16，公开三端从 12/24 到 24/24。Windows 路径模拟另验，实机归属待核。 [恒星目录归属](precision-acceptance.md#fixed-star-catalogue-ownership-round49)

第 57 项修复在目标年月日完整时直接构造当地分析时刻。原版的多余时区投影在 UTC 年域两端溢出。直接对照从 9/11 到 11/11，公开行运三端从 6/12 到 12/12，两版 Schema 各 12/12。其他共享技法已核对调用链。 [完整日期的固定对照](precision-acceptance.md#western-explicit-target-clock-round49)

参评时序沿用 R35 的两条旧失败请求，从逐文件核对的原版取得实际公开 REST 响应。与保存的修复版 REST 响应比较，两例完整业务和输入／输出 Schema 均相同。原跨私有／公开边界的 61/63 和全部差异保留。此次新增独立根因为 0。[同入口补充证据](precision-acceptance.md#timing-public-boundary-round48)

<a id="round50-lunar-and-study"></a>

## R50 的月相搜索和奇门研究回放

月相跨圈定位由 0/16 到 16/16，固定端点由 32/56 到 56/56，首个根后格点由 0/8 到 8/8。99 个原生四相控制在两版均符合作者 C 和 USNO 的固定门，次限月相 12 次公开调用的业务和 Schema 一致。计入跨圈定位一个独立根因，时窗与源经度的精确传播沿已有根因续记。 [月相固定分母及三端结果](precision-acceptance.md#lunar-phase-source-grid-round50)

奇门研究在同一登记下切换计算源的三组反例均恢复为首例前拒绝。同源新旧包各在本版成功重放三例，原生文件逐例见证仍为 2/3。计入研究登记遗漏来源一个独立根因，累计 59 项。 [原生对照与四臂重放](precision-acceptance.md#qimen-study-source-binding-round50)

果老研究四相的最近偶毫秒对照由 1,284/1,302 到 1,302/1,302，有理边界对照由 44/68 到 68/68。两版均保留相同的原生括区及参考事件配对。该差距沿已有单次舍入根因登记。 [固定时间窗和逐事件对照](precision-acceptance.md#lunar-phase-millisecond-round50)

隔离快照的 407 项集中回归全部通过，文档、清单、生成合同及类型检查通过。原格式检查记录两处 Black 差异和一处导入排序差异。该快照早于毫秒投影修订。 [集中验证收据](historical-evidence.md#evidence-20261119-round50-consolidated-validation-results-json)

随后集中执行的 78 项回归全部通过，覆盖毫秒投影、显式交节源、六爻和六壬。该次回归早于六爻备选路径回执的最终简化。 [JUnit 报告](historical-evidence.md#evidence-20261119-round50-selected-source-and-millisecond-checks-pytest-xml)

第 60 项修复让六爻的备选路径回执沿用本次月界。显式解析模式的六个支持域端点请求从 0/18 到 18/18。最终实现的 54 次前后公开调用保持完整业务和 Schema，60 个独立 DE440 字段均符合原 1 秒门。普通及年界请求各少求解 48 个交节。两阶段计作同一根因。 [固定分母与三端比较](precision-acceptance.md#sixyao-selected-analytic-month-round50)

胎前朔望补齐日月源黄经的精确相减，固定反例由 6/10 到 10/10。USNO 分钟门 25/25、同源根与两侧符号 29/29 保持。独立源操作数的逐位门仍为 0/29，前后版各六个公开控制的业务与 Schema 相同。此项沿用已有月相根因。 [原始门、来源与三端比较](precision-acceptance.md#prenatal-syzygy-source-phase-round50)

<a id="round51-native-motion"></a>

## R51 的原生视黄经日速与月亮首个接触

第 61 项修复用实际 TT 横坐标计算原生日速。固定直接对照从 16/32 到 32/32，印占公开对照从 6/12 到 12/12。相对作者 C 位置的独立有理导数，最大速率差为 `9.823e-9″/TT 日`，原联合门仍为 `0.0002″/TT 日`。原等距控制业务相同，`SPEED` 诊断仍为 18/32。原生 JPL 补验的同采样法从 4/16 到 8/16，水星和金星的八个解析导数样本保留同采样法未过门。 [作者来源、逐项对照与范围](precision-acceptance.md#native-motion-abscissas-round51)

R52 和 R53 补验了 DE441 水星、金星的连续导数，两处边界各八项均过原 `1e-6″/原生数值参数日` 门。用另一个已核验节选覆盖 `2^22` 后，同采样门从 4/16 到 8/16，`SPEED` 诊断仍为 10/16。印占两条固定请求的三端成功率从 3/6 到 6/6，等点业务跨版相同。根因累计仍为 62。 [新增覆盖、原分母及实际三端](precision-acceptance.md#native-de441-motion-round53)

第 62 项修复将卜卦月亮的 `next_aspect` 与传光受方统一到月亮求解器的左开右闭括区。固定十一例中，两项资格分别从 8/11 到 11/11。原生 Swiss 控制的业务相同。固定轨迹在三端保留两个接触，同时将无法确定的首个接触留空。七曜闭区间的既有验证仍沿用各自的范围。 [固定数值和三端对照](precision-acceptance.md#horary-first-lunar-contact-round51)

较早的 R51 隔离快照集中回归通过 377/377。与原 356 个测试节点比较，314 个持续通过，6 个失败和 36 个准备错误恢复，另有 21 个节气节点通过。该快照早于日速与月亮首个接触合入。 [集中验证收据](historical-evidence.md#evidence-20261119-round51-verify-results-json) · [逐节点前后比较](historical-evidence.md#evidence-20261119-round51-verify-r50-r51-node-comparison-json)

两项合入后的 528 个隔离节点有 527 个通过。唯一失败是 R50 已有的导入环，底层星历运行时加载旋转适配时同时引入了依赖该运行时的 C04 回执。现将回执迁入独立模块，回执内容和数值适配保持原算法。 [原失败与源码核对](historical-evidence.md#evidence-20261119-round51-verify-integrated-pytest-stdout) · [现行回执模块](../src/fatebridge/core/astro/rotation_policy.py)

迁移后的源码快照通过 61/61 项定向复验，涵盖原导入环节点、印占 C04 工作进程和西占时钟／旋转回执三端读取。Black、isort、mypy、文档、清单和生成合同检查同批通过。Pydantic 的两条 `request` 别名警告仍在。 [复验收据和源码校验](historical-evidence.md#evidence-20261119-round51-verify-rotation-ownership-results-json) · [原始复验输出](historical-evidence.md#evidence-20261119-round51-verify-rotation-ownership-pytest-stdout)

T 宫位回归继续执行原 63,264 行与 1,294 个模型的断言，只在测试内复用输入逐位相同的精密求解结果。固定小样中实际求解从 480 次降至 328 次，逐行位置与回执相同。完整单节点通过，用时 670.27 秒。 [原断言与结果对照](historical-evidence.md#evidence-20261119-round51-t-phase-test-reuse-observation-handoff-md) · [完整运行](historical-evidence.md#evidence-20261119-round51-t-phase-test-reuse-validation-results-json)

<a id="round56-regression-reconciliation"></a>

## R56 的原节点复验

同一生产源码的两个隔离快照完成集中回归。第一批 888 项有 845 项通过，Placidus 与 C04 的固定原失败群均通过，近极太阳升落仍有 43 个节点失败。第二批 657 项全部通过，包含原有的 117 项调用失败、71 项准备错误和 469 项对照，覆盖印占太阳输入、胎前朔望、西占事件角和人类图。两批均核对四个工作进程的收集及来源，前后无记录漂移。 [第一批节点与结果](historical-evidence.md#evidence-20261119-round56-regression-batch-observed-results-json) · [第二批节点与结果](historical-evidence.md#evidence-20261119-round56-regression-followup-observed-results-json)

第三批配对 1,383 个原节点，1,302 个通过，含 151 个原调用失败和全部 1,151 个原通过对照。星骰 821 项、八字交节 40 项、太乙 236 项全过。果老仍有 73 个独立日界对照失败和 8 个恒星时输入校验节点失败。四个工作进程使用同一源码快照，收集顺序相同，全部节点均有结果，运行前后无记录漂移。与第二批相比，生产源码仅增加果老锚日所选 TT 的传播。 [第三批节点与结果](historical-evidence.md#evidence-20261119-round56-regression-domain-owners-observed-results-json) · [源码差异](historical-evidence.md#evidence-20261119-round56-regression-domain-owners-production-source-differences-json)

R54 至 R56 的五个定向快照按原节点去重后，原 1,882 项调用失败中有 1,383 项复验通过、124 项仍失败、375 项尚无配对结果。原 156 项准备错误均获得配对通过记录。初次全量快照的 145,534 通过、1,882 调用失败、156 准备错误、6 收集错误和 3 跳过保留。 [原全量索引](historical-evidence.md#evidence-20261119-round54-pytest-initial-index-json) · [五批去重记录](historical-evidence.md#evidence-20261119-round56-original-node-reconciliation-final-json)

显式 Moshier 的近极原失败窗补齐到 53 根。25 个窗口的事件数和顺序相同，23 根同时满足 TT 和 UT1 的原 1 毫秒门。另 30 根最大相差约 6.0752 毫秒。265 个同历元方向、高度和默认钟对照均符合原门，超差根的括区均见于原作者同向变号记录。 [完整逐根对照](precision-acceptance.md#polar-moshier-complete-sequence-round56)

<a id="round57-regression-reconciliation"></a>

## R57 的奇门、果老与原节点复验

奇门首尾计日由三个共同的日期判断修复一个根因。果老排盘把本命 UT1 主点传入两种真太阳日政策，领域日界中心从 80/228 到 228/228，固定三端响应从 18/30 到 30/30。独立细根窗的严格包含为 420/456，C04 严格源域为 12/16。该变更归入既有精确时标传播。远期姿态恢复原有恒星时供应边界，两处固定注入与对照从 6/20 到 20/20，原八节点通过。此恢复按回归处理。 [奇门首尾计日](qimen-depth-audit.md#qimen-zhirun-inclusive-days-round57) · [果老日界](precision-acceptance.md#guolao-exact-day-window-round57) · [恒星时供应边界](precision-acceptance.md#native-sidereal-provider-round57)

本批 319 个节点，243 个通过，76 个失败。三个新增奇门节点通过。首次因执行计划缺少附加选择字段而结束，实际执行零项。补全字段后用同一源码运行。六次隔离快照按原节点去重，原 1,882 个调用失败中有 1,391 个复验通过、119 个仍失败、372 个待配对。119 个失败包括果老日界 73 个、果老其余消费者 3 个及近极太阳 43 个。原 156 个准备错误均已配对通过，6 个收集错误另计。 [本批逐项结果](historical-evidence.md#evidence-20261119-round57-regression-cohort-observed-recovered-results-json) · [原节点对账](historical-evidence.md#evidence-20261119-round57-original-node-reconciliation-json)

显式 Moshier 固定 53 根的原毫秒门仍为 23/53。保存的原作者轨迹中，每根附近均有多个同向变号，51 根的同向括区跨度超过一毫秒。四种中心差分速度实验均未在这 53 根达到原门。它们所用的太阳速度定义与原生后向差分不同。 [原门与逐根结果](precision-acceptance.md#polar-moshier-complete-sequence-round56) · [变号跨度及速度诊断](historical-evidence.md#evidence-20261119-round57-polar-native-conditioning-saved-conditioning-comparison-json)

<a id="meihua-external-guidance-round57"></a>

## 梅花外应导读与《向背》

统一作者导读说明两种梅花入口均可在所支持的人事题篇报告有限的外物类别及动静。天时题与明确无所见闻的静室占各有原请求约束。两个生成合同仅更改 `external_manifestations` 导读。固定 29 组请求经直接绑定、REST、MCP、CLI 共 116 项前后均符合原门，接口导读从 0/6 到 6/6。业务响应与请求／响应 Schema 的逐项对照一致。该改进属于导读。 [现行外应说明](meihua.md) · [固定前后对照](historical-evidence.md#evidence-20261119-round57-meihua-rule-adjudication-comparison-before-after-json) · [合同生成收据](historical-evidence.md#evidence-20261119-round57-meihua-rule-adjudication-generated-contracts-generation-json)

文明书局本卷二《向背》区分趋近和离开，现行外应输入只可报告动静。两入口在四条原文条件上的 32 个尝试仍按当前请求规则拒绝。卷三所选实物规则区分真火与红紫、土与瓦、真水及轻重。如何把两篇的实物条件合用仍待裁定，全书外应与现实判断也待验。 [影印页、逐条读法及固定判据](historical-evidence.md#evidence-20261119-round57-meihua-rule-adjudication-source-adjudication-md)

<a id="round58-regression-reconciliation"></a>

## R58 的辰月明壬与原节点复验

辰月原先只从字面藏干目录寻找透干，导致共享月用见证遗漏所选《秘本子平真诠》单独列出的明壬。固定的 11 个有书证请求由 0/11 到 11/11，覆盖命盘与财富两个入口、甲丙丁己四个日干。固定五个控制逐值一致。三端源快照的两处变更共修复一个准入根因。辰戌冲后的月令作用、成格和其他日干适用范围待裁。 [书证与三端验收](bazi-assessment.md#chen-store-ren-witness)

原节点主批 320 项，155 通过、165 失败。七批去重后，原 1,882 个调用失败中有 1,479 个同名节点通过，284 个仍失败，119 个尚无同名结果。通过记录包含 39 个测试函数 AST 有变更的节点。五个迁移对应项、62 个主限用例及六份原收集错误另计。原 156 个准备错误都有配对通过结果。 [主批结果](historical-evidence.md#evidence-20261119-round58-original-node-batch-observed-results-json) · [原分母对账](historical-evidence.md#evidence-20261119-round58-original-node-reconciliation-main-batch-json)

第二批选择 376 项，260 通过、26 断言失败、90 准备错误。四个进程的节点顺序与执行前后源码一致。合并至原 1,882 个调用失败，最新同名结果为 1,615 通过、202 失败、35 准备错误及 30 缺同名结果。通过数包括按当时方法迁移的断言。90 个准备错误中，35 个原节点缺传输夹具，55 个补充节点缺业务对象夹具。 [第二批结果](historical-evidence.md#evidence-20261119-round58-migrated-node-batch-observed-retry-results-json) · [跨快照对账](historical-evidence.md#evidence-20261119-round58-original-node-reconciliation-migrated-batch-json)

第三批 129 项全部通过，四个工作进程的收集顺序一致，运行前后源码校验相同。原 1,882 个调用失败现在有 1,678 个同名节点通过、4 个改名对应项通过、170 个仍失败、30 个未配对。35 个准备错误修复后通过。12 个上升点输入和 20 个子午宫断言按现行口径复验，保留原输入和旧门结果。原 156 个准备错误与 6 个收集错误继续单列。 [第三批结果](historical-evidence.md#evidence-20261119-round58-meridian-and-fixture-batch-observed-results-json) · [原分母对账](historical-evidence.md#evidence-20261119-round58-original-node-reconciliation-meridian-fixture-batch-json)

第四批 38 项全部通过，含 11 个原失败和 27 个补充节点。四个进程的收集顺序一致，输入和源码收据相符。首次执行因月冲参数的预期项数误填而在收集后退出，重试只更正预期项数。原 1,882 个调用失败更新为 1,689 个同名节点通过、4 个改名对应项通过、159 个仍失败、30 个未配对。同名通过含 251 个测试函数 AST 有变更的节点。印度上升点同帧参考仍保留原容差，52 个岁差值的逐位对照中有 19 个差异。 [第四批结果](historical-evidence.md#evidence-20261119-round58-index-residual-ascendant-batch-observed-retry-results-json) · [原分母对账](historical-evidence.md#evidence-20261119-round58-original-node-reconciliation-index-residual-ascendant-batch-json) · [印度上升点参考](historical-evidence.md#evidence-20261119-round58-ascendant-and-source-faults-ascendant-released-v2-ascendant-comparison-json)

六爻月令所有者补入文明书局影印本明载的辰月木余气。固定两臂各 24 次三端调用，余气从 117/144 到 144/144，可裁静气从 123/141 到 141/141，固定静爻分类及可空真空各从 6/18 到 18/18。原季令标签和月冲对照通过，三项日冲活动及永久空仍待裁。第四批确认本项回归后登记为第 66 项独立根因。 [底本与比较](historical-evidence.md#evidence-20261119-round58-liuyao-month-residual-qi-handoff-md) · [根因账本](historical-evidence.md#evidence-20261119-round58-accepted-root-issues-json)

第五批 64 项全部通过，包含 39 个同名原失败、3 个保留原输入的六爻对应项和 22 个补充节点。四个工作进程收集顺序一致，全部节点都有 JUnit 回执，前后源码和环境无漂移。首次准备把新选择器当成原名，执行零个测试。固定交叉表保留了旧完成探针门。仅合并第五批时，原 1,882 个调用失败中有 1,728 个同名节点通过、7 个改名对应项通过、120 个仍失败、27 个未配对。另复核 22 个历史快照中的同测试字节结果，其中 6 个同名、16 个改名。合计为 1,734 个同名通过、23 个对应通过、120 个失败、5 个退役注入未配对。同名通过中 285 个函数 AST 已变更，原门与当前断言分别保留。原 156 个准备错误和 6 个收集错误继续单列。 [第五批结果](historical-evidence.md#evidence-20261119-round58-retained-boundary-and-source-probes-batch-observed-results-json) · [对账及旧门](historical-evidence.md#evidence-20261119-round58-original-node-reconciliation-retained-boundary-batch-json)

明动冲散现在消费同盘已有的月令余气。未火、丑水在补辰木余气前就能复现下游遗漏。固定八盘的冲散状态从 15/24 到 24/24，焦点有气从 9/21 到 21/21，独立日克及弱动未裁仍各有对应槽。可能回退到 DE441 的太阳缓存键改用固定包内来源身份，由实际选中的来源校验数据。两种未使用清单故障恢复 2/2 张 Swiss 年表、48 个节气及 6/6 个河洛三端响应，逐值等于清洁结果。选中 DE441 的清单、分块和 TDB 故障保留拒绝，原 72 项 JPL 对照继续满足两道门。两项各计一个根因，累计 68。包内 DE440 年表范围外的自动路径使用同一缓存身份，未加入这组实际调用。 [六爻书证与逐槽对照](historical-evidence.md#evidence-20261119-round58-liuyao-clash-source-adjudication-handoff-md) · [太阳来源对照](historical-evidence.md#evidence-20261119-round58-numerology-source-failures-fixed-comparison-json) · [第五批源码身份](historical-evidence.md#evidence-20261119-round58-retained-boundary-accepted-source-identities-json)

太乙月、日、时计用节气保留点选锚，月、时计从同一点计算距锚秒数。固定算术从 10/150 到 150/150，14 个固定三端请求的字段精确值从 12/42 到 42/42，两版各 42 个成功体通过 Schema。14 个 2026 年锚均在 NAOJ 原 60 秒门内。首次观察的 14 个 REST 422 源于观察器把 `Z` 写成小写，原响应保留。太乙修订归入既有保留点传播根因。 [独立复核及前后像](historical-evidence.md#evidence-20261119-round58-taiyi-retained-boundary-independent-handoff-md)

近极升落的 TT、UT1 原门各为 23/53。两处原生操作数分别重现速度与视黄经的数值差异。作者后向速度端点精化得到 34/53，属原作者轨迹的灵敏度实验。当前尚无达到原门的生产修法，43 个相关失败保留。 [操作数见证及原门](historical-evidence.md#evidence-20261119-round58-polar-backward-operator-handoff-native-intermediates-final-md)

<a id="meridian-samples-round58"></a>

### 子午宫样点重放

以 Swiss C 2.10.03、SOFA 和独立平面交点核对六组回归／Lahiri 请求。修前 72 个名义宫头及 144 个样点宫头达到 `1e-8°` 门槛，12 个公开样点都缺重放所需的源黄道原点。省略原点的旧公式在两组门槛中分别得到 0/72 和 0/144。修后用每个样点发布的 ARMC、交角、源原点与视岁差重放，144 个宫头的最大残差为 `5.68e-14°`，对独立参考为 `3.98e-13°`。六组完整结果在 REST、MCP、CLI 一致，严格字段投影返回同一组样点事实。固定样点的验收范围限于所选时钟与制宫几何。 [方法与字段](other-chart-schools.md) · [独立基准](historical-evidence.md#evidence-20261119-round58-meridian-sample-replay-reference-json) · [修前对照](historical-evidence.md#evidence-20261119-round58-meridian-sample-replay-before-comparison-json) · [修后对照](historical-evidence.md#evidence-20261119-round58-meridian-sample-replay-after-comparison-json)

<a id="round59-regression-reconciliation"></a>

## R59 的边界归属和合批复验

返照分析点的精确零残差、日期命卦的实际模型回执、西占地球姿态读取的错误归属各计一项，累计 71 项。风水立春、节月与月盘校核消费保留交节点，归入原时标传播。印占四个原节点现在按各自坐标框架核对，同一保留 TT、同一星历文件下分别比较 Swiss 源量和 SOFA 目标量，原 `1e-10°` 门为 4/4。旧跨框架相等门 0/4 留存。 [返照](precision-acceptance.md#return-analysis-endpoint-round59) · [风水](precision-acceptance.md#fengshui-retained-boundary-round59) · [错误归属](precision-acceptance.md#native-source-errors-round59) · [印占独立对照](historical-evidence.md#evidence-20261119-round59-jyotish-lunar-owned-window-handoff-md)

第七批 19 项通过，其中 9 项是原失败节点。原 1,882 个调用失败累计为 1,748 个同名通过、23 个对应项通过、106 个仍失败、5 个退役来源注入待配对。同名通过中 296 个测试函数 AST 已变更。原 156 个准备错误均有配对通过，6 个收集错误继续单列。各批结果来自各自的冻结源码。 [第七批结果](historical-evidence.md#evidence-20261119-round59-seventh-regression-batch-observed-results-json) · [原分母对账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-seventh-batch-json)

第八批固定 63 节点，61 通过、2 失败。两条失败都是等宫 `E` 请求在行运返回 `house_code=A`，其余 `A`／`equal` 四条同组控制通过。原 1,882 个调用失败累计为 1,791 个同名通过、24 个对应项通过、62 个仍失败、5 个退役注入待配对。同名通过的函数 AST 有 339 个变更、72 个一致、1,380 个未记录。六个原收集错误来自同一主限模块重复报错，两个后续批次各有 62 个对应见证通过。原收集错误的记录独立保留。 [第八批原分母](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-eighth-batch-json) · [收集错误对账](historical-evidence.md#evidence-20261119-round59-original-collection-reconciliation-json)

共享中点因子的宫轴数值、星历错误原因登记、十年星限快照的体积门分别获得一项独立根因资格，累计 74 项。中点独立直接对照由 24/32 到 32/32，公开对照由 24/30 到 30/30。六壬太阳与人类图 Design 分别核对实际来源故障，合计记一个登记缺漏。十年星限的原直接交付门由 209,412 字符降至 188,148 字符，公开默认结果含元数据仍约 434,524 字符。事业建议采用同次结构指数，归入已有交付修复。 [宫轴](precision-acceptance.md#western-specialty-axes-round59) · [错误登记](precision-acceptance.md#native-source-errors-round59) · [十年星限](precision-acceptance.md#western-retained-clock-and-delivery-round59) · [事业](precision-acceptance.md#career-advice-index-round59) · [根因账本](historical-evidence.md#evidence-20261119-round59-accepted-root-issues-json)

第九批 16 项中通过 15 项。两条等宫 `E` 原节点用 Swiss `E` 保留独立几何对照，并核对 FateBridge 的规范执行码 `A`。六个等宫节点均验证本命与行运层、三端、原 `1″` 门和落宫，独立物理实参仍为 0/6。太乙 V34 旧报告按原哈希恢复，现行审计保留 48 个候选、96 次比较及两类零联合命中。事业第二案先通过建议断言，随后仍报 `88 == 95` 失败。 [第九批原始结果](historical-evidence.md#evidence-20261119-round59-ninth-regression-batch-observed-results-json) · [等宫对照](historical-evidence.md#evidence-20261119-round59-equal-house-alias-review-canonical-e-followup-qualification-json) · [太乙保存对照](historical-evidence.md#evidence-20261119-round59-taiyi-dice-original-node-triage-historical-evidence-current-replay-saved-comparison-json)

原 1,882 个调用失败累计有 1,794 个同名通过、24 个对应项通过、59 个仍失败、5 个退役注入待配对。59 项包括近极升落 43 项、八字 15172 十二项、太乙三项和事业一项。156 个原准备错误均已有配对通过，6 个原收集错误单列。该对账汇集各批冻结源码的结果。 [逐节点累计对账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-ninth-batch-json)

八字 15172 的十二条旧 `弱` 断言继续保留。用现行十二支藏干、默认参数及八种灵敏度权重构造 9,072 个逐根保留量输入，精确有理门与现行乘积比较一致。其中 504 个恰在 `3/4`，最近非零距离为 `3/100`。输入覆盖当前取值的超集，含实际盘面未必产生的关系组合。这个结果只查既定工程根量的 `≥3/4`，15172 的全局旺衰仍缺充分原典裁定。 [逐根算术](historical-evidence.md#evidence-20261119-round59-bazi-root-predicate-replay-retention-arithmetic-superset-observed-json) · [15172 原门与页证](historical-evidence.md#evidence-20261119-round59-bazi-root-predicate-replay-handoff-md)

风水月紫白复用相邻两节做归属和回执，修正时区换年后无关年表触发的失败。原 12 次失败全部恢复，五组成功对照仅有节月入口回执变化。九组修后相邻节归属和 18 个端点的原 1 秒 TT 门通过。本项补入独立根因账本，累计 75 项。 [端点对照](precision-acceptance.md#fengshui-sectional-year-edges-round59)

第十批固定 114 节点全部通过，覆盖风水年份边缘、48 个香港天文台交节对照、重复钟面、共享历法消费者和三个太乙原节点。太乙 V33、V35、V38 区分原引用和现行清单，逐文件哈希、原典异文及原失败门继续保留。V36 的 16 个原始完整服务载荷仍缺，恢复报告保存了 16 个原比较结果。 [第十批复验](historical-evidence.md#evidence-20261119-round59-tenth-regression-batch-observed-results-json) · [原清单与现行引证](historical-evidence.md#evidence-20261119-round59-taiyi-dice-original-node-triage-historical-evidence-current-three-test-candidate-static-review-json)

原 1,882 个调用失败累计为 1,797 个同名通过、24 个对应项通过、56 个仍失败、5 个退役注入待配对。56 项包括近极升落 43 项、八字 15172 十二项和事业一项。156 个原准备错误已有配对通过，6 个原收集错误单列。 [第十批逐节点对账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round60-regression-reconciliation"></a>

## R60 的 ISO 小数、太阳穿越与合批复验

共享 ISO 钟面、太阳搜索的真实邻格、搜索网格与二分的孤立零判定各修复一项独立根因，累计 78 项。Vimshottari 的两个目标钟时入口补齐既有 TZif 已定义钟时规则。ISO 三端实际时点和归属为 24/24，完整业务等价为 9/12。太阳固定算术为 28/28，三个实景站点的九次公开复验符合冻结输入和轨迹。 [ISO 与分期](precision-acceptance.md#iso-clock-fraction-round60) · [太阳穿越](precision-acceptance.md#solar-crossing-isolation-round60)

集中复验在 1,592 个冻结路径及七个选择器下通过 179 项，路径无漂移。批次覆盖 ISO、分期目标准入、三个太阳穿越反例、既有固定 DE440 窗及太阳来源错误。原 1,882 个失败的对账沿用第十批状态。近极 Moshier 的 43 个原节点、八字 15172 的十二项和事业旧分数一项继续保留。 [复验及 JUnit](historical-evidence.md#evidence-20261119-round60-regression-batch) · [近极来源对照](historical-evidence.md#evidence-20261119-round60-polar-moshier-attribution-report-md) · [八字与事业页证](historical-evidence.md#evidence-20261119-round60-r59-bazi-career-evidence-index-handoff-md)

<a id="round61-regression-reconciliation"></a>

## R61 的宫头归属、时运结构份额与合批复验

小写 Sunshine `i` 宫头沿用正算编号，四个固定请求的三端对照通过 12/12。八字时运在交付浮点数前用有理数判方向，固定方向对照从 75,532/75,600 到 75,600/75,600，公开流年三端从 75/90 到 90/90。两项修复计入独立根因，累计 80 项。共享调用钟拒绝投影到 TZif 未指定时段的时刻，直接服务和三端各从 7/12 到 12/12，计入既有根因的消费者覆盖。 [Sunshine](precision-acceptance.md#sunshine-forward-labels-round61) · [时运结构份额](precision-acceptance.md#timing-structural-share-round61) · [共享调用钟](precision-acceptance.md#shared-call-clock-admission-round61)

集中复验在 15,383 个冻结路径及 13 个选择器下通过 490 项，路径无漂移。原 1,882 个失败的对账沿用第十批状态。近极候选源算子的 25 个固定控制和五窗导数对照已通过，连续高度及根证书待完成，原 TT 和 UT1 的 1 毫秒门各为 23/53。Sunshine 的极区取向和一般逆算、八字 15172 十二条旧断言及事业旧分数继续保留。 [集中复验与 JUnit](~/.codex/artifacts/fatebridge-audit-20261121-round61/regression-batch/) · [近极源阶段](~/.codex/artifacts/fatebridge-audit-20261121-round61/polar-continuous-certificate/report.md)

<a id="round62-regression-reconciliation"></a>

## R62 的佩印、当地钟面与合批复验

八字候选和结构检查共用印根前提，固定原典检查从 38/39 到 39/39，八组公开前后比较的差异限于佩印候选状态和印根观察。独立根因累计 81 项。六爻及三式合一在显式偏移投影后检查当地钟面类型，直接投影从 7/10 到 10/10，三端各从 10/12 到 12/12。这补全既有 TZif 根因的消费者。R60 原完整业务门仍为 9/12。 [佩印原典对照](precision-acceptance.md#bazi-hurt-seal-root-round62) · [钟面投影对照](precision-acceptance.md#explicit-local-projection-round62)

集中复验在 15,380 个冻结路径和十个选择器下通过 496 项，路径无漂移。原 1,882 个失败调用中，同名通过 1,797 个、映射通过 24 个、失败 56 个，另有五个已退役注入未配对。近极原 TT、UT1 各 23/53。固定五窗的后向跨度改变了端点符号，Sunshine 极区仍有 64 个无向交线失败，两项均保留原分母。 [集中复验与 JUnit](~/.codex/artifacts/fatebridge-audit-20261121-round62/regression-batch/) · [近极光学](precision-acceptance.md#polar-optics-span-round62) · [Sunshine 分支](precision-acceptance.md#sunshine-cardinal-branches-round62)

<a id="round63-regression-reconciliation"></a>

## R63 的财根、派生钟面与合批复验

食神生财和普通伤官用财共用财根观察，固定领域对照从 126/140 到 140/140，独立根因累计 82 项。年小限、指定年盘、法达周年和世俗盘补齐既有 TZif 钟面规则。隔离三端对照从 24/39 到 36/39，余下三项属于同一节气年表。 [财根与页证](precision-acceptance.md#bazi-wealth-root-round63) · [派生钟面对照](precision-acceptance.md#generated-local-clocks-round63)

集中复验在 15,381 个冻结路径和 11 个选择器下通过 763 项，路径无漂移。原 1,882 个失败调用的对账保留 56 个失败和五个退役未配对注入。近极原 TT、UT1 各 23/53，八字旧旺衰和事业分数继续待裁定。近极的五个固定窗口在精确跨度下排除了连续根，历史实际跨度在 `74-1` 给出下降交越括区。该结果沿用原门槛和历史求值顺序。 [集中复验与 JUnit](~/.codex/artifacts/fatebridge-audit-20261121-round63/regression-batch/) · [近极窗口证书](~/.codex/artifacts/fatebridge-audit-20261121-round63/polar-longitude-boundary-cover/report.md)

<a id="round64-annual-civil-receipts"></a>

## R64 的节气年表与下游钟面

节气年表及下游保留精确主点，按当地钟面的可用性选择带偏移或 UTC 显示。原 13 个请求的三端判据从 36/39 到 39/39，新增 16 个下游请求从 18/48 到 48/48。原年表 288 个精确主点一致。奇门置闰在所需地方日序未定义时返回结构化错误。拆补仍生成原局，源年回执的差异留待单独核对。这批修复计入既有 TZif 根因的消费者覆盖，独立根因累计 82 项。 [节气和下游对照](precision-acceptance.md#annual-solar-civil-receipts-round64)

冻结快照的 418 项集中复验及最终源码的 10 项定向复验均通过。原 1,882 个失败调用的对账仍为 1,797 个同名通过、24 个映射通过、56 个失败和五个退役未配对注入。近极 TT、UT1 的 1 毫秒门各为 23/53，25 个完整窗的定义域仍待证明。八字旧旺衰和事业分数沿用原门。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261121-round64/annual-civil-integration/regression/result.json) · [近极预检](~/.codex/artifacts/fatebridge-audit-20261121-round64/polar-full-53-diagnostics/handoff-preflight.md) · [原失败台账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round65-calendar-ownership-and-peer-cautions"></a>

## R65 的钟面切点、时运重放与古典警语

精确节气投影先确定切点归属，时运以精确区间右端限制重放，奇门拆补记录实际节气的源年。固定点 26/32 → 32/32，下游原请求 36/57 → 57/57。风水、六壬和金口诀的 UTC 标签及缺失状态扩展既有 TZif 根因的消费者覆盖。区间起点落在整分舍入边界时，最早可重放时刻仍待独立核验。 [钟面与重放验收](precision-acceptance.md#solar-term-clock-ownership-round65)

建禄月劫候选依据国图本报告官杀并透及两正官并透，固定领域门 48/111 → 111/111。本命与事业按原 Schema 交付来源警语，取清、制伏、成格与旺衰仍分别裁定。夏例的杂气月令资格和专旺仍留在来源审查范围。 [透干警语验收](precision-acceptance.md#peer-officer-source-cautions-round65)

本批认可四项独立根因，累计 86 项。冻结源码集中复验 465 项全部通过，无跳过、错误或路径漂移。随后两个源码文件的格式修正通过 AST 等价核对。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261121-round65/combined-calendar-integration/regression/result.json) · [格式修正核验](~/.codex/artifacts/fatebridge-audit-20261121-round65/combined-calendar-integration/format-final/changes.json)

近极光学固定 265 控制中，采用作者 TT 和实际后向差分跨度时，方向和高度各 265/265。改用连续 TT 时方向 256/265，高度 265/265。25 个根窗还有 90 个未决子格，正式两臂未释放。原始 53 根的一毫秒门和 43 个失败节点沿用原结论。 [近极域证明交接](~/.codex/artifacts/fatebridge-audit-20261121-round65/polar-full-53-diagnostics/handoff.md)

<a id="round66-exact-replay-start-and-canping-date"></a>

## R66 的重放左端、周年钟面与禄劫证据

重放按节气的精确左端和精确右端选择整分，固定有理数对照从 18/26 到 26/26。参评附法需要参考节令有已定义的当地日期，逐端语义检查从 24/36 到 30/36。余下六次检查涉及周年落入未定义钟面。两项分别补齐已有重放端点和 TZif 钟面准入根因。 [限定验收](precision-acceptance.md#exact-replay-start-and-canping-date-round66)

参评和大运共用周年钟面的归属及有效性校验。六个原请求的 18 次 `-00` 误接纳改为结构化拒绝。固定三端语义门为 18/39 → 36/39，原请求格式失败保留。严格业务等价为 12/13 → 6/13，错误回执在部分端上仍有框架字段差异。 [周年对照](precision-acceptance.md#canping-generated-anniversary-clock-round66)

八字禄劫用财和用食伤补录原书区分的透干和会支实位，本轮登记一项独立根因，累计 87 项。领域固定门从 87/138 到 135/138，正偏财顺序经独立核定后用保存结果重比为 138/138。公开字段门为 42/132 → 132/132，16 组三端业务及 Schema 一致。现有成格状态和力量裁定沿原规则。 [禄劫柱位验收](precision-acceptance.md#peer-wealth-output-witnesses-round66)

首批冻结复验 1,217 项中 1,195 项通过，22 项失败。用原断言复查这 22 项，第 65 轮为 22/22，第 66 轮为 0/22。独立读取 IANA 2026f 的 TZif 确认，旧结果有 18 个未定义首运钟面、四个未定义的首个十年结束钟面。修订后的断言保留原输入及可用的首运和跳时对照，并要求未定义边界明确拒绝。最终定向复验 811/811 通过，两个批次均无冻结路径漂移。 [首批结果](~/.codex/artifacts/fatebridge-audit-20261122-round66/regression-batch/result.json) · [配对复查](~/.codex/artifacts/fatebridge-audit-20261122-round66/regression-paired/result.json) · [原边界的 TZif 分类](~/.codex/artifacts/fatebridge-audit-20261122-round66/regression-paired/undefined-boundary-authority.json) · [最终定向结果](~/.codex/artifacts/fatebridge-audit-20261122-round66/regression-final/result.json)

<a id="round67-generated-clocks-and-house-state"></a>

## 生成钟面、Sunshine 逆算和数值目标时点

大运及西占周年要求前拨缺口两侧的当地时间均有定义。固定三端语义从 15/27 到 27/27。四组错误回执的框架字段随传输端不同，严格三端正文等价为 9/9 → 5/9。本次补齐已有 TZif 准入根因。 [生成钟面验收](precision-acceptance.md#defined-gap-offsets-round67)

Sunshine 逆算按所属图架恢复正算所用的太阳赤纬，48/48 个固定连续坐标与 Swiss 作者库逐位相同。果老和德国盘按带符号总微秒解析数值目标，固定模型时点从 168/240 到 240/240，三端时点门从 36/84 到 84/84。两项各登记一个独立根因，累计 89 项。 [Sunshine 逆算验收](precision-acceptance.md#sunshine-inverse-declination-round67) · [目标时点验收](precision-acceptance.md#numeric-target-clock-round67)

源码清单含 5,450 组职责和 14,616 项审查项。7,468 个函数或类定义中 5,059 个已具名，2,409 个待审。近极原 53 个根的 TT、UT1 毫秒门各为 23/53，原失败集合继续有效。 [职责清单](algorithm-inventory.md) · [近极固定窗](precision-acceptance.md#polar-moshier-complete-sequence-round56)

冻结合批复验覆盖七个选择器，共 674 项通过。最终时区文件的排版调整保持 AST 相同。原 1,882 个调用失败的存量对账保持 1,797 个同名通过、24 个映射通过、56 个失败、5 个未配对退役注入。 [合批复验](~/.codex/artifacts/fatebridge-audit-20261122-round67/regression-batch/result.json) · [原队列](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round70-return-clock-and-geometry"></a>

## 返照当地钟面、近极根窗与来源分歧

日返照、月返照及综合时运按 TZif 的当地类型决定是否交付当地时间，UTC 与 TT 各自保留。固定三端语义门从 18/27 到 27/27。此次补齐已有 TZif 根因的消费者覆盖，独立根因累计 89 项。行运和指定年盘的原诊断门为 6/12，六爻异拼写的旧严格业务门为 9/12。 [返照钟面验收](precision-acceptance.md#return-display-clock-round70) · [相邻消费者对照](~/.codex/artifacts/fatebridge-audit-20261122-round70/shared-clock-projection/final-handoff.md)

近极 Moshier 的 1,600 个固定带臂粗格有 1,512 个排零、10 个恰有一根、78 个未决。22 个局部有向根的 TT 和 UT1 证书宽度均小于 0.935 纳秒。原 53 根的 TT 和 UT1 各为 23/53，仍待配对到完整窗的独立根序列。Sunshine 四个原公开图架的普通点位为 33/33，原宫头标签和连续相位差异保留。 [近极根窗证书](~/.codex/artifacts/fatebridge-audit-20261122-round70/polar-full-53-diagnostics/handoff.md) · [Sunshine 几何对照](precision-acceptance.md#sunshine-public-geometry-round70)

八字 15172 的十二项原门和事业分数的一项原门仍失败。独立算术核对 45/45，已核原典支持部分局部条件，完整全局强弱与原事业分数仍无足够来源。原 1,882 个调用失败维持 1,797 个同名通过、24 个映射通过、56 个失败、5 个退役注入未配对。 [逐节点与版本页证](~/.codex/artifacts/fatebridge-audit-20261122-round70/bazi-original-gate-source-review/handoff.md) · [原失败队列](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

返照、西占时运与极区宫位的定向复验 572 项通过，15,373 个冻结路径无漂移。清单新增一个摘要交付职责，现有 5,451 组、14,617 项职责，7,469 个函数或类定义中 5,060 个已具名、2,409 个待审。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261122-round70/regression-batch/result.json) · [当前清单](algorithm-inventory.md)

<a id="round71-clock-labels-and-source"></a>

## 西占时点标签、调候出处与双臂根窗

行运和指定年盘的固定三端响应从 12/36 到 36/36，标签从 450/747 到 747/747。固定年与公历周年法达、十年星限和黄道释放的标签从 3,819/3,948 到 3,948/3,948，原区间算术及活动判定两臂分别为 3,192/3,192 和 702/702。以上补齐已有 TZif 根因的时点交付，累计独立根因仍为 89 项。 [固定三端验收](precision-acceptance.md#elapsed-clock-labels-round71)

戊酉和乙子各新增七条可定位的调候条件，来源范围为 26/120 格。领域断言 258/258，公开语义 794/794。同版三端业务 62/62，严格跨版业务 44/47，三份保存快照的文字差异另行逐项核对。全盘强弱、合化与取用继续待校。 [版本、页码和限制](precision-acceptance.md#seasonal-wu-yi-source-round71)

近极 25 个固定窗的两种连续模型各确认 53 个有向根，两时标根箱均窄于 1 纳秒。历史产品的原毫秒门仍为两轴各 23/53。原 1,882 个调用失败的对账保持 1,797 个同名通过、24 个映射通过、56 个失败和 5 个退役注入未配对。 [双臂闭覆盖](precision-acceptance.md#polar-closed-cover-round71) · [原失败对账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

首批集中复验含 888 项，884 项通过，包括按发布合同调用 MCP 的测试。四项新增直调用例因误传公开边界参数 `as_of` 失败，原结果保留。去掉该参数后，四项用例与三份调候测试文件合计 350 项通过。两批冻结路径均无漂移。清单现有 5,455 组、14,624 项职责，7,470 个函数或类定义中 5,064 个已具名、2,406 个待审。 [首批记录](~/.codex/artifacts/fatebridge-audit-20261122-round71/regression-batch/result.json) · [定向复验](~/.codex/artifacts/fatebridge-audit-20261122-round71/regression-correction/result.json) · [职责清单](algorithm-inventory.md)

<a id="round72-projected-clocks-and-source"></a>

## 西占生成时点与近极历史根

近极两种连续模型各与 25 个完整历史窗的 53 个根有序配对。原 ±1 毫秒门下，历史实际跨度臂通过 TT 5/53、UT1 4/53、联合 4/53，名义跨度臂双轴均为 0/53。历史实际跨度的 34 根距原扫描已见全部同向括区均超过 1 毫秒，仍需同历元分量隔离。原产品两轴各 23/53、43 个失败节点保持原判。 [固定门及相邻括区证据](precision-acceptance.md#polar-historical-root-comparison-round72)

次限、主限和多重回归按事件瞬间的时区资格交付钟面。两批固定三端对照的 2,034 个标签达到全部通过，前像为 1,998/2,034。两批时标算术在前后均通过。此次补齐已有 TZif 根因的消费者，累计独立根因仍为 89。折叠 Sunshine 的公开范围明确正算与逆算采用的宫制，原有向相位验收继续保留。 [事件钟面对照](precision-acceptance.md#projected-clock-labels-round72) · [Sunshine 固定对照](precision-acceptance.md#sunshine-folded-scope-round72)

戊戌、乙丑新增 19 条页证条件，已校调候月格增至 28/120。92 格与全盘取用仍待校。西占服务新增 13 个定义映射，清单现有 5,468 组、14,651 项职责。7,470 个函数或类定义中 5,077 个已具名、2,393 个待审。独立语义算法总数待定。 [调候来源验收](precision-acceptance.md#seasonal-wu-xu-yi-chou-round72) · [职责清单](algorithm-inventory.md#western-predictive-service-inventory-round72)

本轮合入后的 606 项定向复验均通过，冻结的 15,418 个路径无漂移。覆盖戊乙与丙火调候、三项西占钟面回归、次限图架、主限精度及极区轴线。118 条警告涉及旧农历接口与 Pydantic 的字段元数据。清单、文档、生成合同、定向类型与格式检查也已通过。 [定向复验](~/.codex/artifacts/fatebridge-audit-20261122-round72/regression-batch/result.json) · [检查收据](~/.codex/artifacts/fatebridge-audit-20261122-round72/quality/results.json)

<a id="round73-source-and-fixed-tt"></a>

## R73 调候书影、波斯向运与近极端点

戊亥、乙亥新增 20 条具名来源条件，调候覆盖 30/120。90 格仍保留待校简表，全盘力量、制救和取用仍待裁定。波斯向运在 16 个冻结输入上的截取成员和次序与独立 Decimal 全部相合，快照表头补明七曜推进、十颗本命星体及十二个固定宫头。作者日期和本系统日期采用各自约定，匹配的 158 项中有 107 项同日。两项合入均计零个独立根因，累计仍为 89。 [调候来源](precision-acceptance.md#seasonal-wu-hai-yi-hai-round73) · [波斯向运对照](precision-acceptance.md#persian-directed-round73)

近极 212 个固定端点中，保持 TT 及后向跨度、仅更换 UT1，使 101 点残差翻号。预选作者括区的正确有向变号由 2/53 降至 0/53，本轮没有新根证书。原产品两轴各 23/53。原 1,882 个节点仍为 1,797 个同名通过、24 个映射通过、56 个失败及 5 个退役注入未配对。对 56 个失败中的 12 个八字旺衰节点及一个事业节点已核对输入、分值计算、字段归属和版本，沿用原断言。 [固定端点](precision-acceptance.md#polar-fixed-tt-endpoints-round73) · [八字及事业逐节点证据](~/.codex/artifacts/fatebridge-audit-20261122-round73/original-bazi-career-contracts/handoff.md)

赤纬推运的冻结标量对照揭示三例异侧非零赤纬误归平行和一例四位显示精度导致的原距逆序。修复候选仍需三端实测，Jayne 本文的零点和容许度约定仍待查证。清单为 5,468 组、14,651 项职责，7,470 个函数或类定义中 5,077 个已具名、2,393 个待审。独立语义算法总数待定。 [赤纬对照](~/.codex/artifacts/fatebridge-audit-20261122-round73/jayne-declination-audit/handoff.md) · [职责清单](algorithm-inventory.md)

本轮集中复验的 603 项全部通过，冻结的 15,416 个路径无漂移。七个选择器覆盖调候来源层、波斯向运数值与西占请求合同。127 条警告涉及旧农历接口和 Pydantic 字段元数据。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261122-round73/regression-batch/result.json) · [检查收据](~/.codex/artifacts/fatebridge-audit-20261122-round73/quality/technical-results.json)

<a id="round74-derived-points-and-declination"></a>

### 派生点工作角、赤纬次序与两格调候书证

经典派生点保留有理工作角，供界、面、度主及福点的普通落宫比较。固定 3,280 案的界主、面主和度主分别由 2,896、3,088、3,192 案通过增至全部通过。Flatlib 具名埃及界和迦勒底面可复核，子女点方向、婚姻取式和度主权重有版本差异。福点背景盘的固定落宫由 192/240 到 240/240，本地顺排、逆排各由 96/120 到 120/120。派生点归类和普通落宫是同一项工作精度问题。 [经典点](precision-acceptance.md#lot-classification-round74) · [福点落宫](precision-acceptance.md#fortune-house-round74)

赤纬推运单独修正了跨半球分类和距离次序。两项分别通过独立切换核对，三端固定组由 15/33 到 33/33。原双残差集合 12/19 保留，Astrolog 的开区间和双命中优先顺序有 25 个标签差异。Jayne 合刊正文支持实体赤纬与其他变体分开，变动容许度的表值和边界待核。戊子与乙戌的两个来源单元使具名调候覆盖增至 32/120，另 88 格及全盘合化和取用仍待裁定。 [赤纬](precision-acceptance.md#jayne-declination-round74) · [调候](precision-acceptance.md#seasonal-wu-zi-yi-xu-round74)

中央清单有 5,476 组、14,660 项职责，7,472 个函数或类定义中 5,081 个已具名、2,391 个待审。原 1,882 个节点仍为 1,797 个同名通过、24 个映射通过、56 个失败及 5 个退役注入未配对。近极原 53 根的 TT 和 UT1 各通过 23 个 1 毫秒门。全域来源资格、独立语义算法总数和预测效度待验。 [中央清单](algorithm-inventory.md) · [原失败台账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

派生点工作精度、赤纬分类与赤纬排序各登记一项独立根因，累计 92 项。本轮集中复验 1,061 项全部通过，15,424 个冻结路径无漂移。576 条警告涉及农历旧接口与 Pydantic 字段元数据。测试后的排版只修改一份测试文件，前后 AST 相同。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261122-round74/regression-batch/result.json) · [排版核对](~/.codex/artifacts/fatebridge-audit-20261122-round74/quality/fortune-format.json)

<a id="round79-closed-orb-and-source"></a>

## R79 赤纬闭门、同次福点与调候书证

赤纬在精确比较闭容许度和稳定排序之后才转为四位展示。固定 24 个自然请求的三端配对门从 51/72 到 72/72，登记一项独立根因，累计 93 项。Astrolog 固定源码的默认标签相合 21/24，三处差异已逐项归因。Jayne 的可变容许度、黄道截点及混合配对待核。 [赤纬验收](precision-acceptance.md#jayne-exact-closed-orb-round79)

希腊盘的福点经度、星座和座内度取自同次经典层，固定三端一致性从 9/18 到 18/18，补齐 R74 派生点工作角的一个消费者。戊丑、乙酉的 22 条具名书证把调候覆盖增至 34/120，另 86 格及全盘合化和取用仍待裁定。 [同次福点](precision-acceptance.md#hellen-fortune-continuity-round78) · [调候书证](precision-acceptance.md#seasonal-wu-chou-yi-you-round77)

近极的固定局部扫掠显示 33,806 个跨零跳变。原 53 根的 TT 和 UT1 各有 23 个满足闭 ±1 毫秒门，尚无新根证书。原 1,882 个节点的分母和结果保留，其中 1,797 个同名通过、24 个映射通过、56 个失败、5 个退役注入未配对。 [近极扫掠](precision-acceptance.md#polar-time-word-cut-optics-round79) · [原节点台账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

中央清单有 5,477 组、14,660 项职责。在 7,471 个函数或类定义中，5,080 个已具名，2,391 个待审。具名职责用于安排逐项核对，独立语义算法总数、完整专业来源及全域验收仍待确认。 [中央清单](algorithm-inventory.md)

集中复验的 565 项中 554 项通过，10 项乙酉断言仍预期旧的待校状态。保留 9 月 16 日甲申和 9 月 17 日乙酉的相同请求，补 9 月 19 日丁亥的待校控制。迁移后的 30 项在核对过 15,417 个冻结路径的隔离副本全部通过，活树合入前后像与该副本相符。`astro_election` 的字段投影节点在原批次约 45 分钟时因耗时停止 worker。单列该未完成节点，保留原结果及零路径漂移记录。 [原批次](~/.codex/artifacts/fatebridge-audit-20261122-round79/regression-batch/result.json) · [迁移收据](~/.codex/artifacts/fatebridge-audit-20261122-round79/regression-source-review-migration/verified-isolated-migration.json)

<a id="round80-working-angle-and-source"></a>

## R80 主限法盘与调候书证

主限的普通点、福点与精神点按精确推进黄经分座、归界，坐标环与法盘复用同一工作角。固定普通点和虚点分别通过 243 和 200 个位置判据组，三端 30 个响应通过，原 14 例的时相、168 项容许度及 154 项经度对照均通过。此项补齐 R74 已登记的根因。戊寅、乙申新增 22 条定位到书影的条件，调候具名来源覆盖增至 36/120，84 格及全盘取用待校。 [主限对照](precision-acceptance.md#primary-direction-working-angle-round80) · [书证对照](precision-acceptance.md#seasonal-wu-yin-yi-shen-round79)

中央清单有 5,477 组、14,664 项职责、5,885 个文件／符号映射，分布于 767 个实现文件。7,473 个定义中 5,082 已具名，2,391 待审。累计 93 个独立根因。目录仍为 93 条和 66 个方法 ID，REST、MCP、CLI 分别公开 91、92、92 条。 [当前清单](algorithm-inventory.md)

DE440 同历元对照证实五个接缝的 31 对高度限值同号，并在四个固定窗口查到原系数解析光路的有限无解区间。原近极 53 根的毫秒门保持两轴各 23/53。Jayne 的黄道截点、混合配对及变动容许度有独立几何证据，印本数表和方法合同待核。原 1,882 个调用失败的对账仍为 1,797 个同名通过、24 个映射通过、56 个失败、5 个未配对。 [接缝](precision-acceptance.md#polar-de440-one-sided-seams-round81) · [Jayne 来源](precision-acceptance.md#jayne-source-scope-round81) · [原失败账本](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

集中复验的 411 项全部通过，零跳过。隔离结果绑定到合入时工作树的 15,417 个逐字节相同的路径。比较范围含主限、调候及迁移后的三端公开断言。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261122-round80/regression-batch/result.json)

<a id="round84-exact-direction-window"></a>

## R84 主限窗口、调候书证与民用载体

主限黄经时间线在有理工作角上判定岁数窗口。48 条固定应排记录中，两个普通太阳边界输入分别走顺推、逆推，两案均在精确 100 年上界外，原六条三端误列已修复。整组 32 个输入的三端归属由 69/96 到 96/96。新增一项独立根因，累计 94 项。戊申、乙未新增 21 条可定位条件，调候具名来源为 38/120；其余 82 格及全盘取用待校。 [主限窗口](precision-acceptance.md#primary-direction-timeline-window-round83) · [戊申与乙未](precision-acceptance.md#seasonal-wu-shen-yi-wei-round81)

集中批次首轮 370/418 通过，48 个旧浮点岁数断言失败。独立复算通过 3,500 条新岁数与钟面记录。更新岁数断言后，同批 418/418 通过，15,417 个冻结路径零漂移。 [首轮批次](~/.codex/artifacts/fatebridge-audit-20261122-round84/regression-batch/result.json) · [复验批次](~/.codex/artifacts/fatebridge-audit-20261122-round84/regression-batch-working-arc/result.json)

民用载体复核新增 11 组、18 项职责。中央清单有 5,488 组、14,682 项职责、5,903 个文件／符号映射。7,473 个定义中 5,100 个已具名，2,373 个待审。同算符 DE440 参考累计在 25 个固定窗口中的 14 个取得 24 个纳秒根箱，尚有 18 个未决原叶格。原 1,882 个节点的失败账本保留，近极 53 根的 TT 和 UT1 毫秒门仍各为 23/53。 [民用职责](algorithm-inventory.md#civil-carrier-inventory-round82) · [DE440 根箱](~/.codex/artifacts/fatebridge-audit-20261122-round84/polar-de440-handoff/report.md) · [原失败账本](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round85-static-key-and-election"></a>

## R85 主限静态钥、果老清单与甲木见证

黄经主限在工作龄和工作弧上确定相对弧、时相与排序。最终后像通过 79/79 个原节点，74 次公开业务核对沿用 R84 的固定判据。其余 76 个端组合未重新执行，MCP 包装输入与请求模型直接等同仍为 0/12。此项补齐 R83 已登记的主限工作精度根因。 [主限验收](precision-acceptance.md#primary-direction-static-key-consumers-round85)

果老与主限新增 14 组、33 项源码职责。甲木 12 个固定输入执行 420/420 次公开调用，144/144 组跨端业务一致。38 个具页月格累计完成 956/1,216 个公开组合，六戊与六乙仍有 260 个。调候具名原页覆盖为 38/120，原 `15172` 与事业分数差异保留。 [中央清单](algorithm-inventory.md) · [甲木见证](precision-acceptance.md#bazi-jia-public-witness-round85)

近极 DE440 的同算符配对在原 53 根的闭 1 毫秒门下为 0 通过、44 超差、9 未定。明示 Moshier 对作者的原门仍为 TT 与 UT1 各 23/53。原 1,882 个节点中 1,797 个同名通过、24 个映射通过、56 个失败、5 个退役注入未配对。 [近极逐根对照](precision-acceptance.md#polar-de440-historical-pairing-round86) · [原节点台账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round86-clock-gap-and-direction-state"></a>

## R86 生时标签间距与主限工作弧

生时误差网格先求相邻 `timedelta` 的最大值，再转成秒。日子午用同次 UTC 标签差核对间距与回执。30 个公开响应的最大标签间距逐位门由 9/30 到 30/30，新增一项独立根因。黄经主限的坐标环、事件余差和两类法盘复用同次工作弧，原固定门由 1,557/2,027 到 2,023/2,027，补齐已有主限根因的消费者。五模块的 603 项回归全部通过。该隔离批次同时包含择日候选，四个 R86 生产文件另有固定请求对照。 [标签间距](precision-acceptance.md#specialty-recorded-gap-round86) · [主限工作弧](precision-acceptance.md#primary-direction-exact-state-round86) · [合入身份](~/.codex/artifacts/fatebridge-audit-20261122-round86/integration-receipt.json)

## R87 自刑出处、闰秒取样与近极差异

八字自刑事件复用《三命通会》字面关系的来源条。前后各 11 项直接观察、11 次公开调用及 45 个有理算术判据支持此次出处修正。隔离合批通过 175 项，包含新增出处回归及既有的旺衰、流时和公开交付判据。原 15172 旺衰 0/12，事业第二案仍为 88 对原 95。 [自刑原典与对照](precision-acceptance.md#bazi-self-punishment-source-round87) · [合批结果](~/.codex/artifacts/fatebridge-audit-20261122-round87/strength-regression-complete-fixtures/result.json)

三个固定生时误差网格跨 2016 年末闰秒。UTC 标签相差 30 秒的相邻样点，实际 TAI 相差 31 秒，物理判据通过 3/12。近极 Moshier 的固定地球速度交换复现 `77-3` 的三个同历元异号。一项原生编译算术选择足以复现两组地球状态。两套算术均出现多个严格反号的相邻括区，仍缺适用于历史门的唯一择区依据。原 53 根的 TT／UT1 联合门为 23/53，历史 43 个近极失败节点仍须解决。 [生时取样](precision-acceptance.md#specialty-grid-leap-time-round87) · [近极同历元对照](precision-acceptance.md#polar-native-build-round87)

六戊、六乙补齐 260 个现代公开组合，87/87 组跨端一致。具页的 38 个月格累计有 1,216/1,216 个公开见证，严格 `seasonal_conditions` 为 1,028/1,216。38/120 具名原页覆盖及 82 格待校状态继续保留。 [戊乙逐项见证](precision-acceptance.md#bazi-wu-yi-public-witness-round86)

<a id="round87-leap-and-polar-factorial"></a>

### 近极根定位

近极 Moshier 的全交叉对照进一步核查了起始括区与求解路径。完整历史参考组合逐位复现原 53 根，现有实现的联合毫秒门仍为 23/53。 [近极全交叉](precision-acceptance.md#polar-moshier-factorial-round87)

## R88 生时网格精确端点

固定 14 个请求完成 42 次三端调用，其中 36 次成功。两类已准入的普通民用出生时刻实际多算 1 SI 秒，另一个 LMT 区间的精确上端点落在插入秒，三端均拒绝转换。历史 UTC 仿射漂移也可使名义 30 秒长于 30 SI 秒。独立整数对照验证了精确端点与采样间距可同时满足，真实 TT 和 UT1 已通过因子层直接观察。生产修复待贯通日子午、象征公历钥和真太阳时重置。 [固定观察与设计](precision-acceptance.md#specialty-exact-grid-design-round88)

近极 Moshier 的独立区间复算覆盖原 212 个端点、45 个焦点历元，另有 630 个同历元光学对照。在 `77-3` 和 `109-2` 的四个原生终括区，五种实数速度都失去反号。`77-3` 在实际跨度连续模型中的第三根仍超历史毫秒门。本轮保留历史基准和实现，原 TT／UT1 联合门为 23/53。 [独立区间和光学对照](precision-acceptance.md#polar-moshier-velocity-definitions-round88)

## R90 择日原生计算与调候书证

一次持锁的 Moshier 黄经导数复用已校验的几何元组。原择日投影节点两侧通过，完整业务与原运行逐字节一致，原生 `calc` 调用减少 76.03%。新增一项独立根因，累计 96 项。实际 Swiss 或 JPL 文件后端交替仍缺逐状态对照。 [择日验收](precision-acceptance.md#election-native-state-reuse-round90)

戊卯、乙午新增 24 条具页条件，戊辰、乙巳再增 21 条。调候书证覆盖 42/120，余 78 格待校。旧八字旺衰 12 项、事业一项和近极 Moshier 43 项仍为失败。原 1,882 项队列保留同名通过 1,797、映射通过 24、失败 56、退役注入未配对 5。 [戊卯与乙午](precision-acceptance.md#seasonal-wu-mao-yi-wu-round90) · [戊辰与乙巳](precision-acceptance.md#seasonal-wu-chen-yi-si-round90) · [原队列逐项台账](historical-evidence.md#evidence-20261119-round59-original-node-reconciliation-tenth-batch-json)

<a id="round90-recorded-epoch-combined"></a>

### R90 记录历元和 UTC 端点合并复演

印占与西占流派盘原先能从显示钟面重建样点，造成实际 TT 或 UT1 来源丢失。合并后共享记录网格保留物理历元，达沙依据另行可用的普通公历键。行星时单独修复端点依赖普通 `datetime` 的问题，保留原夜弧内的真实插入秒标签。两项各登记一个独立根因，累计 98 项。 [生时网格](precision-acceptance.md#recorded-grid-round90) · [行星时](precision-acceptance.md#planetary-hour-label-round90) · [根因账本](~/.codex/artifacts/fatebridge-audit-20261122-round90/accepted-root-issues.json)

153 次合并复演与各自的合格参考响应一致，含 12 次预期拒绝。六项行星时端点检查落在原 1 毫秒参考带。43 份指南文字差异和一次 MCP 进程组回收警告保留。原近极 Moshier 的 53 个根仅 23 个同时符合 TT、UT1 的 1 毫秒门，八字 `15172` 为 0/12，事业第二案为 88 对 95。生时网格的历史无唯一标签与真太阳时重置交集仍待核。 [合并复演对照](~/.codex/artifacts/fatebridge-audit-20261122-round90/combined-grid-validation/comparison-qualified.json)

## R91 岁运、印占采样与太阳闭窗

显式整岁按有理起运跨度选十年段，固定断面 **160/213 → 213/213**。这是 R28 原始跨度根因的消费者补全。默认时运导出按现有区段选择规则带上分析时刻依据，五个入口的固定门 **6/30 → 30/30**。印占民用 TT 网格使用共同半径与唯一名义槽，独立算术 **11/17 → 17/17**。导出及网格各登记一个根因。 [整岁断面](precision-acceptance.md#dayun-selection-round91) · [导出行为](precision-acceptance.md#timing-export-round91) · [TT 网格](precision-acceptance.md#recorded-grid-quantization-round91)

太阳谱节点收回各自闭窗后，原 2,730 个保存窗的越界交付 **54 → 0**。精确零两侧按严格反号保留可解区间，独立有理数 **6/10 → 10/10**。两处各登记一个根因，累计 **102 项**。隔离合并批通过 1,032 项，精确零后像专项通过 102 项。闭窗合并树实际公开重放 33 次，印占 21 次和行星时 12 次均与各自保存参考一致。精确零后像另按原输入复验行星时三端，插入秒边界均为 `2016-12-31T23:59:60.528903+00:00`，符合固定参考带。183 个保存窗的 370 条未交付严格格点变号及历史 Moshier 双轴门 **23/53** 保留。 [太阳闭窗](precision-acceptance.md#solar-closed-window-round91) · [精确零](precision-acceptance.md#solar-zero-bracket-round91) · [组合公开对照](~/.codex/artifacts/fatebridge-audit-20261122-round91/integration/comparison-public.json)

R90 活树大批次有 1,381 项通过、105 项失败。35 项按 `+30 s` 的民用标签查找样点，70 项查找 `±60 s`。105 项均在执行原固定时刻天文比较前退出。R90 封存报告曾将查询统一写成 `±30 s`，实际查询以原测试为准。原失败、测试和物理门保留，迁移依据待独立复核。原 1,882 项历史队列仍保留 56 个失败和 5 个退役注入未配对，八字 `15172` 为 **0/12**，事业第二案为 **88 对 95**。 [R90 完整失败表](~/.codex/artifacts/fatebridge-audit-20261122-round90/final-grid-quality/regression-failed-nodes.json)

当前源码清单有 **5,555 组、14,816 项职责**。7,505 个函数或类定义中 5,176 个已具名，2,329 个待审。戊巳和乙辰补录方案已核到 24 条原典条件，当前可交付来源覆盖仍为 **42/120**。独立语义算法总数与全仓专业验收待确认。 [源码清单](algorithm-inventory.md#round91-shared-owners) · [两格来源与原基线](~/.codex/artifacts/fatebridge-audit-20261122-round91/bazi-seasonal-source-adjudication/handoff.md)

<a id="round92-solar-grid-and-seasonal"></a>

## R92 太阳有限格点与调候来源

太阳高度搜索在原 13 点预算内按实际相邻 UT1 浮点数采齐闭分段。预算内 2,652 个固定闭窗逐项吻合，找回 210 个严格反号区间。全组 2,730 个窗仍有 78 个预算外闭窗缺 160 个区间。保存点的离散变号与连续太阳高度根分别裁定。卜卦与印占各一个公开请求在 REST、MCP、CLI 的业务字段和对应 Schema 与 R91 一致，印占的七个计算时刻回执也逐端一致。 [采样验收](precision-acceptance.md#solar-finite-grid-round92)

历史太阳钟测试分别核对固定旧标签时刻和物理 TT 网格。608 个原节点各保留 200 微秒 EOT 门，旧标签精确匹配仍为 503/608。R90 的 105 个原失败保存在原记录。 [固定试验及测试迁移](precision-acceptance.md#solar-clock-test-scope-round92)

补入戊巳、乙辰的 24 条具页条件和五个印例，具名调候来源达到 **44/120**，余 76 格待校。书证、字面柱位和全盘未裁状态分别交付。源位置清单现有 **5,561 组、14,831 项职责**，7,505 个函数或类定义中 5,180 个已具名、2,325 个待审。独立语义算法总数待确认。 [书证与跨端差分](precision-acceptance.md#seasonal-wu-si-yi-chen-round92) · [补登职责](algorithm-inventory.md#round92-solar-and-seasonal)

原 1,882 项队列仍为同名通过 1,797、映射通过 24、失败 56、退役注入未配对 5。近极 Moshier 双轴 1 毫秒门为 23/53；八字 15172 原 12 项仍为 0/12，事业原第二例数字为 88 对 95。全仓专业验收、连续物理精度和预测效度仍待证。 [R91 留存账本](~/.codex/artifacts/fatebridge-audit-20261122-round91/continuation-state-current.json)

## R93 德国盘原页与调候递进

具名调候来源扩至 **46/120**，余 74 格沿用待校简表。戊午和乙卯保留书影、异本读法及全盘未裁状态。Witte 1925、1923 原页表值与 30 个实际交付该层的保存响应一致，24 个未定格及两处印刷算术差继续保留。 [调候两格证据](precision-acceptance.md#seasonal-wu-wu-yi-mao-round93) · [德国盘原页对照](precision-acceptance.md#hamburg-witte-original-round93)

源码职责清单现有 **5,571 组、14,849 项职责**。7,505 个函数与类定义中 5,190 个已具名，2,315 个待审。此处补登的十个位置是时键、算术、来源及支持职责。独立语义算法总数待核。 [十项职责](algorithm-inventory.md#shared-source-support-round93)

## R94 德国盘推进历元

太阳弧和日子午共用按有理时键计算的推进 TT。固定公开对照通过 180 个可算样点、42 个取样请求的名义时刻及 18 个无取样时刻。历史声明与 S2 的原待裁门按原分母保存。同版本前像的声明一致。独立根因累计仍为 103 项。 [推进历元验收](precision-acceptance.md#hamburg-progressed-tt-round94)

源码职责清单现有 **5,573 组、14,852 项职责**，7,507 个函数与类定义中 5,192 个已具名，2,315 个待审。独立语义算法总数待核。 [算法清单](algorithm-inventory.md)

<a id="round96-retained-clocks-and-strength"></a>

R96 补齐无取样德国盘的精确名义日和目标准入，并修复八字特殊结构复核的快照诊断。前者归入既有时点传播问题，后者是原算术值与投影值混用的一项独立错误。当前清单有 **5,586 组、14,874 项职责**，7,508 个函数与类定义中 5,202 个已具名，2,306 个待审。 [太阳钟对照](precision-acceptance.md#germany-retained-nominal-key-round96) · [快照对照](precision-acceptance.md#bazi-strength-snapshot-round96) · [职责清单](algorithm-inventory.md#bazi-strength-support-round96)

独立重算复现了太阳光学定义切换导致的全部 88 个宽域 DE440 失败窗，候选仍留在隔离树。77 盘八字条件算术对照通过 6,538/6,538，`15172` 原定性断言与事业原分数门继续留存。1879 年 LMT 零半径控制仍待核。 [DE440 双定义](precision-acceptance.md#solar-de440-optical-tt-round96) · [八字条件账本](precision-acceptance.md#bazi-strength-ledger-round96)

## R95 戊未与乙寅调候书证

具名来源覆盖 **48/120**，其余 72 格使用待校简表。新增两格交付 21 条具页条件、6 条原印四柱及实际干藏位置。48 次三端公开调用通过 Schema 校验，120 格产物回归通过。生成调用合同同步更新 `bazi_career` 的两条调候视图说明。累计 **103** 项已验收独立根因，此次增加来源覆盖。 [书证与适用范围](precision-acceptance.md#seasonal-wu-wei-yi-yin-round95)

太阳光学候选保留了同一次 UT1 与 ΔT 的精确和，在远期子窗取得排根证书。原 DE440 的 96 个固定窗中，精确前像全部通过双轴 1 毫秒门，候选仅通过 8 个。候选留在隔离树，下一轮核对两种 TT 定义各自的独立参考。 [光学候选与原门](precision-acceptance.md#solar-optical-clock-round95)

<a id="round97-source-and-clock"></a>

## R97 星历范围准入、历史名义钟与丁火春月

DE441 下载器按 RFC 9110 解析字节范围、总长与比较字段。12 条固定 CLI 回放由 **4/12 到 12/12**，另 18 条直接回放全部通过。六份成功件均与保存的 JPL 记录独立拼接逐字节相同。1879 年地方平太阳钟保留前向名义日，私有封套字节对照由 **10/20 到 20/20**，三端公开数学与准入由 **6/18 到 18/18**，严格业务一致 **8/9**。 [星历来源准入](precision-acceptance.md#de441-acquisition-round97) · [公历键与封套](precision-acceptance.md#historical-mean-solar-clock-round97)

丁寅、丁卯、丁辰的选段来源将具名覆盖增至 **51/120**。117 个非目标格保持一致，72 条三端回执通过 Schema。辰月两干的逻辑关系、半月及全盘力量仍待裁。历史名义钟补齐既有根因，丁火春月增加出处覆盖。字节范围准入计入一项独立根因，累计 **105** 项。当前清单有 **5,609 组、14,915 项职责**，7,509 个定义中 5,220 个已具名、2,289 个待审。 [丁火书证](precision-acceptance.md#ding-spring-source-round97) · [源码职责清单](algorithm-inventory.md)

R96 冻结回归 641 项中 627 项通过，14 项失败。`15172` 的 12 项原断言仍为实际强、原期望弱。其余两项为 1879 年德国盘的名义时差及八字快照回归调用入口。R97 合入名义日修复，并将快照回归接到生成完整评估对象的生产入口。原 1,882 项总账继续保留 1,797 项同名通过、24 项映射通过、56 项失败和 5 项退役未配对。近极 Moshier 双轴 1 毫秒门为 **23/53**，事业原第二案 **88 对 95**。 [R96 失败归属](~/.codex/artifacts/fatebridge-audit-20261122-round96/integration/failure-disposition.md) · [近极括区对照](precision-acceptance.md#polar-moshier-bracket-ownership-round97)

<a id="round98-native-path-and-sources"></a>

## R98 原生星历路径与丁火夏月

完整 DE441 下载现在同时核对目录及文件路径的编码字节。作者 C 与下载 CLI 的固定对照由 **7/13 到 13/13**，合法成品逐字节一致。本轮共新增一项独立根因，累计 **106** 项。清单有 **5,623 组、14,947 项职责**，7,509 个函数与类定义中 5,230 个已具名、2,279 个待审。 [星历路径验收](precision-acceptance.md#de441-native-file-path-round98) · [职责清单](algorithm-inventory.md#native-ephemeris-admission-inventory-round98)

丁火夏月新增出处覆盖，具名调候来源共 **54/120**。72 次三端回执通过 Schema，117 个非目标格完整一致。近极 W04 的连续与原生落交仍有分歧。早期地方平太阳钟的亚微秒准入问题已在 REST 复现，修复仍在隔离树。原 1,882 项中 **56 项失败、5 项退役未配对**继续保留。 [丁火书证](precision-acceptance.md#ding-summer-source-round98) · [近极邻值](precision-acceptance.md#polar-moshier-w04-round98) · [地方平太阳钟的固定前臂](~/.codex/artifacts/fatebridge-audit-20261122-round98/historical-lmt-source-consumers/handoff.md)


<a id="round99-historical-clock-and-native-directory"></a>

## R99 历史太阳钟、原生目录与丁火秋月

早期地方平太阳钟向 Swiss 保留未经显示量化的秒参数，并把精确名义日传给太阳弧。29 个固定点的 TT、UT1 和精确名义日均通过作者对照。17 个原请求的三端准入由 **45/51 到 51/51**。完整 DE441 单目录准入的固定对照由 **6/12 到 12/12**。无效项目目录回退合格缓存的选路 **8/15 → 15/15**。丁火秋月加入三个具页月格，调候来源覆盖 **57/120**。此次沿用既有根因和来源范围，累计 **106 项独立根因**。 [历史太阳钟验收](precision-acceptance.md#historical-mean-solar-clock-round99) · [原生单目录验收](precision-acceptance.md#de441-native-single-directory-round99)

细粒度清单为 **5,636 组、14,984 项职责**，还有 **2,254 个函数或类定义**待审。果老所选盈缩公式逐点相符，7 处刊数字差值保留。原 1,882 项的 **56 个失败和 5 个退役未配对**继续保留，近极固定 53 根的双轴 1 毫秒门仍为 **23/53**。独立算法总数及全库验收仍待完成。 [职责清单](algorithm-inventory.md#historical-clock-and-source-inventory-round99) · [果老公式对照](precision-acceptance.md#guolao-solar-definitions-round99) · [丁火秋月验收](precision-acceptance.md#ding-autumn-source-round99)

## R101 原生搜索列表与近极时间舍入

压缩星历离线校验后先核对显式搜索列表的整体字节上限。固定作者库、运行时准入和字节校验各为 14/14，离线指引由 11/14 到 14/14。近极 W04 四点对照显示，作者舍入后的级数时间与逐项舍入累加共同改变两个固定点的过线判定。原近极 53 根双轴 1 毫秒门仍为 23/53。累计独立根因维持 106 项。 [原生搜索列表](precision-acceptance.md#ordered-native-search-guidance-round101)

## R101–R103 原生文件搜索、调候书证与果老字面运算

共享路径准入覆盖整条原生搜索列表到各文件名可达前缀。Human Design 的固定缺陷布局在 REST、MCP、CLI 均恢复成功。丁火冬月具名调候范围达到 **60/120**。果老离线固定字面对照 **799/799**，保留三见证的总宽差及横看断点。累计独立根因 **106 项**。 [星历搜索验收](precision-acceptance.md#ordered-native-filename-search-round102) · [丁火冬月书证](precision-acceptance.md#ding-winter-source-round102) · [果老字面对照](precision-acceptance.md#guolao-literal-registers-round103)

当时清单为 **5,648 组、15,022 项职责**，具名函数或类定义 **5,291**，另有 **2,222** 待审。原 1,882 项保留 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。近极 53 根中 **23 根**通过双轴 1 毫秒门；独立语义算法总数仍待审定。

## R106 星历资料和风水节气验收

清单补登 17 个定义，现有 **5,665 组、15,050 项职责**，**5,308** 个函数或类定义具名、**2,205** 个待审。DE440 共同档按原始 SPK 对照全部 101,494 条记录，解析太阳系数对照 ERFA 原码。风水全节气判定补齐内置 DE441，固定切片由 **0/24 到 24/24**。该项计入离线验收修复，现有 106 项算法及工具根因账本单列。 [职责清单](algorithm-inventory.md#solar-storage-fengshui-inventory-round106) · [原始对照](precision-acceptance.md#solar-source-and-fengshui-round106)

<a id="round107-project-files-warmth-polar"></a>

## R107 项目星历文件、寒暖书证与近极分段

自动发现依据项目目录中可用的普通 `.se1` 文件，三个不合格布局均恢复使用已核验缓存。该文件类型错误与 R98 的目录和拼接字节上限有各自的失败条件，新增一项独立根因，累计 **107 项**。两条〈寒暖〉原页进入八字来源对照，日主三档继续待裁。 [星历验收](precision-acceptance.md#native-project-files-round107) · [原页对照](precision-acceptance.md#bazi-warmth-source-conditions-round107)

清单现有 **5,678 组、15,077 项职责**。7,513 个函数或类定义中，**5,319** 个具名、**2,194** 个待审。W01 三条闭间隙严格排除门高零点，固定队列累计 **8/52**。首次异号的光学交换保留运行时绑定欠缺，补充同源编译臂说明九个给定点的速度字差异。原双轴 1 毫秒门保持 **23/53**，原 1,882 项仍有 **56 个失败和 5 个退役未配对**。 [细粒度清单](algorithm-inventory.md#bazi-source-comparison-inventory-round107) · [近极结果](precision-acceptance.md#polar-first-sign-and-w01-round107)

## R108 太阳钟面和辅助星历准入

两项独立修复使账本累计 **109 项**。太阳钟回代直接从有理日舍入到微秒，固定钟面 **12/18 → 18/18**，公开回代残差 **15/18 → 18/18**。辅助星历准入按原生语义跳过中间组件为文件的路径槽，固定人类图三端门 **6/15 → 15/15**。 [太阳钟面](precision-acceptance.md#solar-wall-clock-round108) · [辅助星历准入](precision-acceptance.md#native-auxiliary-enotdir-round108)

沿用 **5,678 组、15,077 项职责**。更新已具名的太阳钟、星历准入和来源索引职责，独立语义算法总数仍待清点。八字新增一条未知三档书例，W01 复核原六根箱。原近极 43 个失败节点、`15172` 的 12 个失败与事业分数一项仍在原队列，未退役的原测试均继续保留。 [职责清单](algorithm-inventory.md) · [书例和近极闭段](precision-acceptance.md#bazi-vol8-polar-w01-round108)

## R109 开日日出与星历运行回执

开日日出直接将原 UT1 传给太阳钟。固定 C04 钟面 **62/80 → 80/80**，日主和时主各 **74/80 → 80/80**。固定公开平太阳钟面 **6/12 → 12/12**。星历目录限制列举时，西占及印占在三个公开端恢复交付，并记录无法列举的目录槽。累计 **111 项独立根因**。 [开日日出算术与三端](precision-acceptance.md#planetary-opening-epoch-round109) · [星历回执及权限反例](precision-acceptance.md#ephemeris-inventory-permissions-round109)

清单有 **5,680 组、15,084 项职责**，覆盖 **6,174 个文件和符号组合**。7,513 个函数或类中有 **5,320 个具名、2,193 个待审**。W01 各臂仍有 89 个未决闭叶，原双轴 1 毫秒门保持 **23/53**。原 1,882 项仍有 56 个失败及 5 个退役未配对。独立算法总数和全库验收仍待完成。 [细粒度清单](algorithm-inventory.md#opening-epoch-and-inventory-round109) · [八字及近极未决](precision-acceptance.md#bazi-polar-r109)

## R110 八字编释归属、德国盘查找与近极首段

累计 **112 项独立根因**。八字集合约束按登记编释归属，原 **17 个档差、2 项违规、1 项符合**全部复现。专用德国盘三端固定门由 **18/24 到 24/24**，普通文件组件属于 R108 路径根因的后续消费者修复。W01 两臂各余 **87** 个未决叶，原双轴 1 毫秒门保持 **23/53**，全窗极值为 **0/25**。 [八字归属](precision-acceptance.md#bazi-bound-attribution-round110) · [拟体元素表](precision-acceptance.md#fictitious-source-enotdir-round110) · [近极闭段](precision-acceptance.md#polar-w01-right-leaf-round110)

清单仍为 **5,680 组、15,084 项职责**。7,513 个函数或类中有 **5,320 个具名、2,193 个待审**。原 1,882 项的 **56 个失败和 5 个退役未配对**保留，独立算法总数和全库验收待完成。 [细粒度清单](algorithm-inventory.md)

## R111 认证挑战、原生因子错误与八字快照

累计 **115 项独立根因**。REST 六个 401 挑战由 **0/6 到 6/6**。德国盘原生计算失败的固定检查由 **96/102 到 102/102**。八字完整会合局在三个发布位置交付中文判断依据，固定两案两版的四组三端业务一致。八字修复归入交付层，原旺衰算法失败继续计入原队列。 [认证](precision-acceptance.md#rest-authentication-challenge-round111) · [原生计算错误](precision-acceptance.md#native-factor-error-round111) · [八字快照](precision-acceptance.md#bazi-bureau-snapshot-round111)

细粒度清单有 **5,704 组、15,148 项职责**，覆盖 **6,221 个文件和符号组合**。7,514 个函数或类中 **5,367 个具名、2,147 个待审**。原 1,882 项仍有 **56 个失败、5 个退役未配对**。W01 两个候选叶经 R112 的去重复验正式闭合，每臂余 **85** 个待决叶。原双轴闭 1 毫秒门为 **23/53**，完整全窗极值为 **0/25**。独立算法总数、全域精度与整体 SOTA 仍待核实。 [细粒度清单](algorithm-inventory.md#共享执行验证与错误交付r111) · [近极对照](precision-acceptance.md#polar-w01-harmonics-round111)

<a id="round112-ziwei-clock-and-source-contrast"></a>

## R112 紫微民用钟与八字原典对照

紫微固定民用钟门由 **21/33 到 33/33**。分钟上端点资格新增一项独立根因，岁序日期资格补齐 R46 已登记根因的消费方。累计 **116** 项指通过固定对照的修复，R111 集中复验尚未封存。 [紫微对照](precision-acceptance.md#ziwei-civil-clock-membership-round112)

源码清单现为 **5,715 组、15,167 项职责、6,232 个文件和符号组合**。7,514 个函数或类中 **5,378 个具名、2,136 个待审**。八字固定六个四柱的独立算术为 **61/61**，可直接比较的三例原局分档为 **2/3**。分歧涉及冲损、盖头、泄身与财坏印的作用次序，书页未给出可采用的统一损失比例。`15172` 原 **0/12** 门及古典未裁保留。 [本批新增职责](algorithm-inventory.md#shared-astronomy-inventory-round112) · [八字页级对照](~/.codex/artifacts/fatebridge-audit-20261122-round112/bazi-root-capacity-source-contrast/handoff.md)

事业现行 D1、1965 两案通过所用版本的 95、88 分回归。原 95、95 分门仍为 **1/2**。原 1,882 项依旧记录 **56 个失败、5 个退役未配对**。R115 近极 W01 原 `seg:02` 两臂闭合后，每臂余 **83** 个待决叶。原 TT 与 UT1 联合闭 1 毫秒门为 **23/53**，完整全窗极值为 **0/25**。 [事业版本复放](~/.codex/artifacts/fatebridge-audit-20261122-round112/career-score-version-attribution/handoff.md) · [W01 分段证据](~/.codex/artifacts/fatebridge-audit-20261122-round115/polar-w01-luni281-cut/report.md)

果老关闭期钟面修复已合入。两入口三端的固定判据由 **12/36 到 36/36**，归入 R46 既有根因。当前清单有 **5,717 组、15,173 项职责、6,233 个文件和符号组合**，函数或类定义 **5,379 个具名、2,135 个待审**。R112 紫微集中回归为 **71/71**，两项数据目录的执行前绑定限制已记录。 [果老验收](precision-acceptance.md#guolao-civil-target-label-round116) · [当前清单](algorithm-inventory.md#guolao-target-inventory-round116) · [紫微回归](precision-acceptance.md#ziwei-civil-clock-membership-round112)

八字〈反局〉、〈戰局〉的独立工程算术 **140/140**。前者证实原典可在没有时癸盖巳的情形下判断火受冲损。后者的立夏后十日戊司令条件在字面合同中无法表达，两案全局旺衰保留未裁。近极 W01 已定位两条原超差根的多括区择根差异，每臂仍有 **79** 个待决叶。两条根的原作者对照、**23/53** 联合门及 **0/25** 全窗物理极值门均保留。 [八字固定反向控制](~/.codex/artifacts/fatebridge-audit-20261122-round113/bazi-clash-source-contrast/handoff.md) · [近极固定扫描](~/.codex/artifacts/fatebridge-audit-20261122-round117/polar-w01-author-scan-and-common-cut/report.md)

## R117、R118 农历钟面模式与原书隔位解冲

两项独立根因入账，累计 **118** 项。农历换算原 **69/78**，后臂 **75/78**，六次非法模式回执修正。72 次非目标回执逐端保持状态及业务相等。完整三端业务相等为 **20/26**，含两种新增校验错误的信封差异。Vostok 的三条原失败与共享契约补核分别保留。农历助手、坐标与历法传输、果老和八字的七个回归文件合计 **305/305**，15,430 个绑定路径无漂移，638 个项目模块来源均在绑定内。 [农历与节气对照](precision-acceptance.md#calendar-helper-clock-mode-round117) · [根因账本与回归身份](~/.codex/artifacts/fatebridge-audit-20261122-round117/accepted-root-issues.json)

隔位解冲限定于印十六所述年月日位置、唯一冲和无会合争用的情形。两条页证见证已修正，后臂 **205/205**，另有十二时支控制 **45/45**。`15172` 原 **0/12**、事业原 **1/2** 和原 1,882 项的 **56 个失败、5 个退役未配对**仍保留。近极两个超差根定位至离散括区选择，历史闭 1 毫秒门 **23/53** 和全窗极值 **0/25** 继续待解决。 [解冲与近极对照](precision-acceptance.md#bazi-zi-chou-clash-resolution-round118)

清单现为 **5,732 组、15,205 项职责、6,244 个文件和符号组合**。7,513 个函数或类中 **5,389 个具名、2,124 个待审**。P0、P1、P2、P3 分别为 **827、797、534、1,741** 组，另有 **1,833** 组待归层。独立语义算法总数、逐定义专业对照与整体 SOTA 仍待核实。 [细粒度清单](algorithm-inventory.md#calendar-clash-inventory-round117-118)

<a id="round118-119-seasonal-clock-and-coordinate"></a>

## R118、R119 风水季节钟面与坐标准入

风水五个季节查询入口的关闭期钟面判据从 **54/72 到 72/72**，归入 R46 既有民用钟面根因。坐标共享边界的直接精确对照从 **26/37 到 37/37**，公开接纳从 **18/36 到 36/36**，新增一项独立根因。河洛三条字段级错误文本门与宿占三个原展示差异仍列在原严格回执门 **30/36** 内。独立展示补核通过两案各三端。 [风水验收](precision-acceptance.md#fengshui-seasonal-query-clock-round118) · [坐标验收](precision-acceptance.md#coordinate-exact-admission-round119)

清单现有 **5,742 组、15,224 项职责、6,249 个文件和符号组合**。7,514 个函数或类定义中 **5,393 个具名、2,121 个待审**。P0、P1、P2、P3 和待归层分别为 **837、797、534、1,741、1,833** 组。R119 近极分段复算的闭叶仍为 **0/2**、接缝 **0/6**，两臂各有 **79** 个待决叶。八字 `15172` **0/12**、事业历史 **1/2**、近极原闭 1 毫秒门 **23/53**、全窗极值 **0/25** 均保留。 [当前清单](algorithm-inventory.md#seasonal-coordinate-inventory-round118-119) · [近极分段证据](~/.codex/artifacts/fatebridge-audit-20261122-round119/polar-w01-three-input-certificate/handoff.json)

R119 累计封存 **119** 项独立根因。风水季节钟面与坐标集中回归 **328/328**，15,427 个绑定路径无漂移，456 个项目模块来源全部绑定。 [封存验收](~/.codex/artifacts/fatebridge-audit-20261122-round119/closure-report.md)

<a id="round120-alias-distance-and-fengshui-date"></a>

## R120 占星骰别名距离与风水日期资格

占星骰经度圆距修复的固定直接对照 **13/16 → 16/16**，公开准入 **6/12 → 12/12**。GeographicLib 作者结果的 13 条经度距离及接纳判定相同，新增一项独立根因。风水命卦的固定业务门 **42/63 → 63/63**，两处日期资格修复归入 R46，另有三例元旦有效期端点待补证。 [占星骰对照](precision-acceptance.md#astrodice-alias-distance-round120) · [风水对照](precision-acceptance.md#fengshui-civil-date-round120)

当前清单有 **5,742 组、15,227 项职责**。原始 1,882 项验收中，1,797 项同名通过、24 项映射通过、56 项仍失败、5 项退役未配对。近极 53 根的源残差复核保留原双轴 **23/53** 及全窗极值 **0/25**。全定义专业来源、整体 SOTA 和预测效度继续按各自条件验收。 [清单](algorithm-inventory.md) · [近极源残差复核](~/.codex/artifacts/fatebridge-audit-20261122-round120/polar-original-scan-error-floor/report.md)

组合树集中回归 **72/72**，15,425 个绑定路径无漂移，564 个项目模块来源全部绑定。源码、格式、导入、文档和差分检查通过。 [组合树验收](~/.codex/artifacts/fatebridge-audit-20261122-round120/closure-report.md)

## R121 风水有效期端点与传统来源待决

风水命卦的元旦端点补齐 R46 在已知年份中的消费者。固定三端业务门 **21/33 → 33/33**，独立端点 **24/42 → 42/42**。累计独立根因仍为 **120** 项。 [端点验收](precision-acceptance.md#fengshui-january-validity-round121)

齐例已定位到鼎文版印页 72–81，所获公开样张止于印页 17。国图印本和敬一堂抄本的甲日酉月首段均未指定卯、戌、辰的柱位。八字原 **232/236**、`15172` **0/12** 与事业 **1/2** 继续保留。 [校勘交接](~/.codex/artifacts/fatebridge-audit-20261122-round121/bazi-xu-clash-source-collation/handoff.md)

<a id="davison-signed-status-round122"></a>

## R122 Davison 算术经度交付

普通、MC 校正和 Marks 的算术经度修复已合入。固定直接 **20/36 → 36/36**，三端 **18/36 → 36/36**。新增一项独立根因。清单登记 **5,743 组、15,230 项职责、6,250 个文件和符号组合**。7,515 个函数或类中 5,394 个具名、2,121 个待审。 [精度验收](precision-acceptance.md#davison-signed-midpoint-round122) · [三端对照](~/.codex/artifacts/fatebridge-audit-20261122-round122/davison-signed-midpoint/comparison.json)

近极独立参考的度转弧度常量初始化精度被定位并更正。两个固定点包络达到原宽度门，原 53 根的 TT、UT1 联合 1 毫秒门 **23/53** 和物理极值 **0/25** 仍保留。原扫描择根及全窗连续性继续审查。 [固定点包络](~/.codex/artifacts/fatebridge-audit-20261122-round122/polar-w01-interval-context/report.md)

## R123 球面中点、公历年区间与八字知识出处

Davison 与 Marks 的球面中点已修正近对跖经差补角的计算顺序。直接门 **0/40 → 40/40**，三端 **3/12 → 12/12**。风水公历命卦年区间按查询瞬间选取实际连续区间并交付有效端点标签，精确端点 **36/90 → 90/90**，归入既有民用时间区间根因。 [球面验收](precision-acceptance.md#davison-spherical-antipodes-round123) · [风水验收](precision-acceptance.md#fengshui-january-transitions-round123)

上海世界图书馆发行《秘本子平真诠》PDF 第 73 页、印刷第六十四页将壬寅、戊申、壬辰、壬寅列作「馬參政」，将己巳、癸酉、癸未、庚申列作「茅狀元」。`knowledge_read` 的两条词条与正确的 `bazi_source_compare` 对齐，题名与四柱绑定 **0/64 → 64/64**，固定门 **61/125 → 125/125**。齐例所需底本内页仍缺，力量与格局门各保留原判。 [印页](~/.codex/artifacts/fatebridge-audit-20261122-round123/bazi-xu-clash-print-verification/sources/ziping-excerpt-2.png) · [出处对照](~/.codex/artifacts/fatebridge-audit-20261122-round123/bazi-xu-clash-print-verification/handoff.md)

清单现列 **5,756 组、15,247 项职责、6,263 个文件和符号组合**，分布于 801 个实现文件。7,516 个函数或类中，5,407 个具名、2,109 个待审。近极连续 TT 交付单项对照恢复 **0/30** 个原双轴超差，原闭 1 毫秒门仍为 **23/53**。 [职责清单](algorithm-inventory.md) · [近极对照](~/.codex/artifacts/fatebridge-audit-20261122-round123/polar-clock-attribution/report.md)

## R124 近双极球面中点与太阳近极择根

Davison 与 Marks 的近双极球面中点修复补齐既有半角精度根因。固定直接对照 **12/48 → 48/48**，GeographicLib 2.1 同门 **48/48**，公开三端地点门 **6/12 → 12/12**。累计独立根因仍为 **123** 项。风水混合偏移的固定三端回执 **33/33**、端点 **114/114**，未发现新的端点合同缺口。 [球面验收](precision-acceptance.md#davison-spherical-polar-components-round124) · [风水验收](precision-acceptance.md#fengshui-mixed-offset-year-round124)

近极候选原生反号括区的两种连续模型对照 **12/12** 排零。后续两窗补齐 **16/16** 定量界后，共有 **48/48** 项可用定量界，该误差预算无法保证原 1 毫秒门。原生多括区的独立择根规则待定，原联合门仍为 **23/53**，物理极值 **0/25**。原 1,882 项中的 56 项失败和 5 项退役未配对继续保留。 [模型域对照](~/.codex/artifacts/fatebridge-audit-20261122-round124/polar-crossing-domain-alignment/report.md) · [后续定量界](~/.codex/artifacts/fatebridge-audit-20261122-round125/polar-nominal-span-derivative/comparison.json)

八字酉月司事的具名四库本 **24/24**。雍正本酉月续表的丁三日与四库本丁五日构成版本异读。对照厘清了证据出处，`15172` 的全盘静态旺衰仍待独立判据，原 **0/12** 保留。 [版本对照](precision-acceptance.md#bazi-month-duty-editions-round124)

## R125 派生民用钟面与酉月词条出处

关系盘派生标签三端 **3/21 → 21/21**，去同次 Marks 别名后 **3/18 → 18/18**。蒙罗维亚和夸贾林的标准偏移跳时与重时诊断 **12/12**，既有流日流时 **33/33**。戴维斯站开日日出发生于民用星期未定义的 `-00` 段，固定三端见证的日主和时主均改为缺项，两臂各 **21** 次调用中的六个控制保留完整业务。这些工作补齐既有民用钟面职责，独立根因累计 **123** 项。 [关系盘](precision-acceptance.md#relationship-civil-labels-round125) · [偏移诊断](precision-acceptance.md#standard-offset-diagnostics-round125) · [开日日出](precision-acceptance.md#planetary-civil-opening-weekday-round125)

八字酉月司事词条并列两版续表的丁三日与丁五日，出处交付 **0/8 → 8/8**。原后臂 **55/67** 保留，按既有公开摘要边界复核保存结果 **67/67**。司令采用及旺衰仍分别有待裁判据，`15172` 全盘旺衰保持 **0/12**。清单现列 **5,756 组、15,248 项职责**，7,516 个函数或类中 5,407 个具名、2,109 个待审。 [酉月词条](precision-acceptance.md#bazi-month-duty-edition-knowledge-round125) · [职责清单](algorithm-inventory.md)

## R126 印占回拨、TZif 时型与太阳括区

印占构盘已复用共享钟面资格检查，SDK 显式选择的回拨分支须与记录 UTC 一致。独立 TZif 固定 SDK 对照 **2/7 → 7/7**，按既有 HTTP 合同核对三端 **39/45 → 45/45**，原比较器 **37/45 → 43/45** 保留。混合已定义与未定义时型的拒绝按 `unresolved_timezone_offset` 归因，直接对照 **30/35 → 35/35**，三端 **30/39 → 39/39**。旧诊断同列为 **39/39 → 30/39**。两项均归入既有民用钟面根因。 [印占回拨](precision-acceptance.md#jyotish-civil-fold-round126) · [混合时型](precision-acceptance.md#mixed-tzif-local-clock-round126)

原近极 Moshier 25 窗的 6,253 个实际 UT1 求值中，53 对相邻严格反号与交付括区的端点逐字一致。原双轴闭 1 毫秒门 **23/53**、物理极值 **0/25** 和 43 个失败节点仍保留，未求值区间和独立物理择根继续审查。Troll 同数值偏移 `-00 → +00` 对照 **18/18**，原首批六个 CLI 参数错误保留。 [近极括区](~/.codex/artifacts/fatebridge-audit-20261122-round126/polar-resolved-bracket-audit/handoff.md) · [Troll 对照](~/.codex/artifacts/fatebridge-audit-20261122-round126/troll-birth-range-clock/handoff.md)

卜卦行星时已区分太阳弧缺项与开日日出的民用星期未定义。固定公开对照 **21/21**，三份戴维斯回执各只更正一处原因，另 **18/18** 份完整业务控制相同。保存响应两臂的 Schema 校验均为 **21/21**。计算归属与验收标志分别交付。累计独立根因仍为 **123**。 [卜卦缺项对照](precision-acceptance.md#planetary-hour-unavailable-reason-round126)

## R127 公历法达与分析钟面归属

公历法达综合和单项现在统一使用锁定的 IANA 时区解释出生、分析和生成周年。独立 TZif 前像裁定了哈瓦那回拨和圣保罗历史偏移在旧版本与锁定版本中的差异。九个固定请求的三端对照 **12/27 → 27/27**。正式法达周期兼容口径见专项文档。八字和西占的分析钟面保留共享未定义偏移错误，固定对照 **18/36 → 36/36**，归入既有民用钟面根因。 [公历法达验收](precision-acceptance.md#firdaria-locked-tzif-round127) · [分析钟面验收](precision-acceptance.md#analysis-clock-error-ownership-round127) · [周期约定](firdaria-compatibility.md)

合入后集中回归 **566/566**。公历法达在双方时型均已定义的样本中复现了规则来源替换，累计验收 **124 项独立根因**。宫制选择固定直接对照 **61/61**。清单现列 **5,770 组、15,268 项职责、6,277 个文件和符号组合**，分布于 803 个实现文件。7,516 个函数或类定义中 **5,421 个具名、2,095 个待审**。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261122-round127/integrated-regression/pytest-result.json) · [宫制选择与清单](algorithm-inventory.md#house-selector-inventory-round127)

太阳广域扫描中，实际形成反号括区的 **2,032** 个事件全部交付，160 个漏根样本均未采到负中心。光学 TT 干预仅符合 **8/96**，候选未合入。原近极双轴闭 1 毫秒 **23/53**、物理极值 **0/25**、八字 `15172` **0/12**、事业旧门 **1/2** 保留。原 1,882 项由 1,797 个同名通过、24 个映射通过、56 个失败及 5 个未配对退役项构成。 [广域太阳审计](~/.codex/artifacts/fatebridge-audit-20261122-round127/solar-wide-grid-ownership/handoff.md)

## R128 果老跨年界钟面与己土三月书证

果老命名区目标钟面改用共享扩展 UTC 公历投影。固定 `native` 模式三端 **9/15 → 15/15**，六个目标的同瞬间十一曜完全相等。原显式 Swiss 门维持 **9/24**，果老前置模型范围限制保留。此项补齐既有 R47 的消费者，累计独立根因仍为 **124**。 [固定对照](precision-acceptance.md#guolao-calendar-projection-round128)

己土寅、卯、辰具名书证覆盖 **60/120 → 63/120**。两臂固定请求三端回执共 **84/84**，原出处比较保留 **14/38**，按既有公开交付合同核对同一批受影响响应为 **24/24**。五印例已核历史出生历元仍为 **0/5**，保留书证异读和全盘取用待裁。 [书证与交付](precision-acceptance.md#bazi-ji-spring-source-round128)

合入后集中回归 **505/505**，检查覆盖果老同瞬间十一曜、八字书证及三端、锁定时区与公开合同。绑定的 16,283 个路径无漂移，本进程记录的 922 个项目模块全部有绑定来源。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261122-round128/integrated-regression/pytest-result.json)

## R129 大运分析年界、果老日期标签与法达版本

大运分析的未来钟面扫描和期界逆像复用共享扩展 UTC 日序。固定三端由 **12/21 → 21/21**，已有成功的同端完整业务 **12/12** 相同。显式零分钟与省略范围的严格配对仍为 **0/6**，六份差异只涉及导出快照的范围说明。六爻显式 analytic 门仍为 **3/15**。大运补齐 R47 消费者，累计独立根因保持 **124**。 [大运与六爻固定对照](precision-acceptance.md#dayun-analysis-utc-domain-round129)

合入后集中回归 **67/67**，覆盖大运跨 UTC 年界的三端结果、跳时、重时、闭端点与闰日。16,283 个绑定路径无漂移，记录的 399 个项目模块均有绑定来源。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261122-round129/integrated-regression/pytest-result.json)

果老的前推历日期标签在公元 1 至 9999 年与 Swiss 作者库全域相符，格里历正逆各 **3,652,059/3,652,059**，儒略历正逆各 **3,652,134/3,652,134**。香港天文台新增刊值 **30/30**，具名冬至条件窗 **8,719/8,719**，原日数端点 **104,628/104,628**。固定气策置闰、历史日界和物理历元继续分别裁定。中央清单现列 **5,777 组、15,279 项职责、6,283 个文件和符号组合**，7,516 个定义中 **5,427 个具名、2,089 个待审**。 [日期标签对照](guolao-algorithm-audit.md#calendar-date-labels-round129) · [职责清单](algorithm-inventory.md)

Bonatti 1550 年巴塞尔印本明列日盘火星后的交点及复归太阳。夜盘从月亮开始，原印未明定交点接位与 75 年后的重启。Döşer 对两项有明确页证。固定左极限首门 **17/18** 保留，按日盘印本年数独立重算后，同一批保存结果的限定门为 **18/18**。 [法达版本与证据](firdaria-compatibility.md#来源与工程补充)

近极太阳原 80 条下降漏报均跨显示 TT 切口。首个原见证在标量 TT 分段参考下，下降为跳变，随后同 TT 格内有连续上升根。R130 用同站的独立连续 TT、远期姿态与 DE441 光学复算原三个闭侧，均严格为正。证书只覆盖这三个区间，原 160 个漏报、联合 1 毫秒 **23/53**、物理极值 **0/25** 各按原门保留。 [分段参考](~/.codex/artifacts/fatebridge-audit-20261122-round129/solar-wide-grid-continuity/handoff.md) · [连续姿态复算](~/.codex/artifacts/fatebridge-audit-20261122-round130/solar-remote-attitude-envelope/handoff.md)

## R130–R134 行运年界、宣明书证与近极交越

当地公历可表示的 UTC 辅助年 0 行运已在原服务入口恢复。固定同区三端 **12/18 → 18/18**，异地三端 **6/18 → 18/18**。目的地钟面实际越界时返回不可重试的验证错误。历史时点的 TT 与 UT1 对照 Swiss Ephemeris 作者库逐位相同。三处生产修复补齐 R47 的既有民用时间根因，累计仍为 **124** 项。 [行运固定验收](precision-acceptance.md#transit-civil-domain-round130-132)

集中复验 **138/138**，包括四个跨年界行运节点、既有三端钟面、闰秒、出生历元、返照及宣明。16,284 个冻结路径无漂移，482 个进程内项目模块均有绑定来源。OpenAPI 生成时记录一条 Pydantic 字段别名警告。补充观察的 91 个 REST 业务入口仍声明所登记的直接请求模型，警告的最小触发条件待定位。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261122-round130/integrated-regression/pytest-result.json) · [请求体声明](~/.codex/artifacts/fatebridge-audit-20261122-round130/checks/openapi-warning.json)

宣明固定直接对照 **100/100**。公开成功及 Schema 为 **9/9**，首版范围门 **3/9** 保留，按字段语义复核同一批回执为 **9/9**。1117 年勘申的三个小余读数及不退结论已由《大日本史料》印本交叉核对。晨初条件未知，历史原件尚待核见。中央清单现列 **5,789 组、15,305 项职责、6,293 个文件和符号组合**，分布于 805 个实现文件。7,516 个函数或类中 **5,437 个具名、2,079 个待审**。 [宣明书证及结果](precision-acceptance.md#senmyo-phase-round130) · [职责清单](algorithm-inventory.md)

果老固定气策离线对照 **1,744/1,744**，覆盖按源日归月、月序和次正月截断、缺朔拒绝、平闰阈值。官历刊本的历史日界与现代历元仍待核对。 [固定气策书证及对照](guolao-algorithm-audit.md#fixed-qice-comparison-round130)

近极连续模型的原 78 个窄窗均排零。R134 复核 19 项职责及原保存求值，未发现两端均已求值却漏交付的严格反号相邻边。全局替换光学 TT 在两个 DE440 中心定义下各从 **48/48 降至 4/48**。原 160 条离散漏报、Moshier 联合毫秒 **23/53**、物理极值 **0/25** 继续沿原门。原 1,882 项中仍有 56 项失败及 5 项退役未配对。 [连续区间证书](precision-acceptance.md#polar-continuous-windows-round133) · [交越职责与反证](~/.codex/artifacts/fatebridge-audit-20261122-round134/solar-event-root-definition-audit/report.md)

2026 年 11 月 23 日复核文档时，290 处旧链接指向本机已无法读取的 R44–R60 外置工件。文档检查因此未通过。原路径和历次验收数字继续保留，相关旧证据的可复核性等待独立核证。 [文档检查原结果](~/.codex/artifacts/fatebridge-audit-20261122-round130/checks/docs.stdout)

<a id="round139-secondary-progression-regression"></a>

## R139 次限跨 UTC 年界复验

次限名义时差的 UTC 辅助年修复已合入，独立入口固定三端 **12/30 → 30/30**。综合时运的固定极端样本已通过次限和主限，随后在上次周年计算处失败。此项补齐 R47 的消费者，累计独立根因为 **124**。 [次限固定对照](precision-acceptance.md#secondary-progression-civil-round133)

合入后集中复验 **17/17**，覆盖次限框架、两个行星弧节点及四个行运年界节点。16,283 个绑定路径无漂移，381 个项目模块有绑定来源。文档检查仍报告 R44–R60 的 290 处历史外置链接缺失。 [集中复验](~/.codex/artifacts/fatebridge-audit-20261123-round139/integrated-regression/pytest-result.json)

## R137 与 R141 年小限、指定年盘和历史证据索引

年小限和指定年盘复用共享精确公历日序。固定公开对照分别为 **12/24 → 24/24** 和 **3/6 → 6/6**。综合推运固定门仍为 **1/2**，失败点沿调用链移到固定年法达。两处修复补齐 R47 的消费者。 [公历边界对照](precision-acceptance.md#profection-calendar-boundaries-round137)

历史文档的 **290 处**失效引用已接入 **268 条**索引记录。259 个原文件未找到可核副本，8 个目录缺原目录级身份，1 个固定输入有哈希一致的副本。原检查失败和各轮验收结论继续保留。 [历史证据索引](historical-evidence.md)

<a id="round140-recorded-clock-budget-and-firdaria"></a>

## R140、R142 出生误差预算与固定年法达

出生误差预算按实际记录钟基识别民用经过时间声明。固定三端由 **18/36 提升至 36/36**。同一回执的业务、交付信封及预算之外的证据一致。累计独立根因从 124 增至 **125**。 [出生钟基对照](precision-acceptance.md#recorded-clock-error-budget-round140)

固定年法达用共享 UTC 日序定位当前期，选取预览和当前期后再生成当地标签。单项固定三端 **18/30 → 30/30**，补充 REST **0/2 → 2/2**。原综合推运仍为 **1/2**，失败点移至十年星限。此项补齐 R47 的消费者。 [固定年法达对照](precision-acceptance.md#firdaria-fixed-calendar-round142)

合入树集中回归 **191/191**。16,283 个绑定路径无漂移，510 个项目模块有绑定来源。中央清单有 **5,811 组、15,353 项职责、6,317 个文件和符号组合、808 个实现文件**。7,517 个函数或类中 **5,461 个具名、2,056 个待审**。 [合入回归](~/.codex/artifacts/fatebridge-audit-20261123-round140/integrated-regression/pytest-result.json) · [职责清单](algorithm-inventory.md)

事业原固定门仍为 **1/2**，第二例为 **88 对 95**。同请求版本迁移后的 `[95,88]` 回归为 **2/2**。原分数差来自冬木无同元素藏根规则对旺衰工程档的调整，两版事业评分公式相同。印本支持分别审查藏根和调候，该例的全局旺衰及事业分值仍缺独立裁定。 [事业原门复核](~/.codex/artifacts/fatebridge-audit-20261123-round143/career-original-score-adjudication/handoff.md)

<a id="round151-time-lord-civil-domain-and-source"></a>

## R151 十年星限、黄道释放和官杀页证

十年星限固定三端 **18/30 → 30/30**，黄道释放 **18/30 → 27/30**。黄道释放的三个未通过槽位均先遇到本命星历缺文件。原综合时运 REST **1/2 → 2/2**，极值请求已贯通两个时主方法和异地行运。顺序保留版通过 18 个原成功槽位的完整业务对照。两处时间修复归 R47，累计独立计算根因仍为 **125**。 [时主固定门及综合对照](precision-acceptance.md#western-time-lord-civil-domain-round151)

R153 为同一条 9995 年请求补齐两份作者星历，再按原门核验三端。原实现于排期时溢出，合入版按当地期界返回不可重试的验证错误。补充门 **0/3 → 3/3**，原固定门 **27/30** 保留。 [星历补充对照](precision-acceptance.md#zodiacal-releasing-far-future-source-round153)

官杀校勘将印本「日主堅固」归到 GS-03，GS-04 保留未裁定。合入后集中回归 **150/150**，16,283 个绑定路径无漂移，433 个项目模块有绑定来源。清单为 **5,811 组、15,353 项职责**，本批为 21 个已有时主职责组补上影响层。7,517 个函数或类中 **5,461 个具名、2,056 个待审**。 [书影校勘](precision-acceptance.md#bazi-gs03-gs04-round147) · [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round151/integrated-regression/pytest-result.json) · [职责清单](algorithm-inventory.md)

已求值双端的近极太阳邻边复核未见丢失。原 1,882 项对账仍为 1,797 项同名通过、24 项映射通过、56 项失败和 5 项退役未配对。联合毫秒门 **23/53**、原离散漏报 160、物理极值 **0/25**、八字 15172 **0/12** 和事业 **1/2** 均保留。 [近极邻边复核](precision-acceptance.md#polar-solar-evaluated-edges-round149)

<a id="round154-157-firdaria"></a>

## R154、R157 公历周年法达与比鲁尼书证

公历周年法达以共享 UTC 日序处理辅助年 0 和 10000，按待交付期界的当地年域判定。固定六案三端 **9/18 → 18/18**，独立上界组三端 **0/9 → 9/9**，合入后集中回归 **109/109**。此项补齐既有 R47 的消费者，累计独立计算根因 **125**。 [固定年界及回归](precision-acceptance.md#firdaria-calendar-anniversary-round154)

比鲁尼书影与两份保存回执的 **122/122** 对照覆盖末尾交点版本的日夜主运、七星共主和交点无共主。夜盘火星后交点及周期重启继续沿用各自来源。 [比鲁尼页证](precision-acceptance.md#firdaria-biruni-round157)

<a id="round158-159-returns-and-solar"></a>

## R158、R159 多重返照年界与近极星历版本

多重返照按同一 UTC 日序定位出生与分析历元。固定可交付组三端 **9/12 → 12/12**，两个过去根仍落在 UTC 辅助年 0 的控制继续拒绝。该修复补齐 R47 的既有消费者，累计独立计算根因 **125**。 [多重返照验收](precision-acceptance.md#extra-returns-civil-epoch-round158)

近极旧作者库逐字复现六个原端点，单换新版外层 ΔT 已解释这六点的反号差异。邻近根和实测时标尚待独立裁定。原 1,882 项对账中，1,797 项同名通过、24 项映射通过、56 项失败、5 项退役未配对。原离散漏报 160、联合毫秒 **23/53**、物理极值 **0/25**、八字 15172 **0/12**、事业 **1/2** 继续按原门记录。 [近极六端点归因](precision-acceptance.md#polar-solar-six-endpoints-round159)

<a id="round160-163-progressions-and-source"></a>

## R160、R161、R163 次限出生钟与独立来源对照

直接次限共享出生 UTC 日序。太阳弧、月球行星弧、Lahiri 次限和 Jayne 赤纬推运的固定三端由 **24/48 到 48/48**。作者 C 构建的原逐位门保留 **45/136**，时标逐位 **16/16**，所验经度、弧值和赤纬配对均符合既定交付门。综合时运出生 UTC 年 0 仍有独立拒绝。累计已验收独立计算根因 **125**，本项归入既有 R47。 [次限出生钟](precision-acceptance.md#secondary-progression-birth-clock-round161)

多重返照与次限合入后集中回归 **59/59**，含两个新增年界回归节点。16,283 个绑定路径无漂移，421 个已加载项目模块均有绑定来源。清单迁移 50 处来源行号，仍登记 **5,811 组、15,353 项职责**。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round161/progressed-birth-clock/integrated-regression/pytest-result.json) · [当前清单](algorithm-inventory.md)

普通六合邻位补足韦氏与任注具名原页。任注的全盘反例限定了多本气根工程覆档的书证归属。三个近极原闭窗的 2,985 个离散样本逐位重现，新版三个原窗中无精确零或相邻反号，连续根仍待裁定。两项研究沿用原证据门和原失败分母。 [八字书证](precision-acceptance.md#bazi-full-chart-adjacency-round160) · [近极原闭窗](precision-acceptance.md#polar-solar-fixed-windows-round163)

<a id="round162-168-clock-and-source"></a>

## R162、R164–R168 主限、月相年界与固定来源

主限九案的固定三端 **12/27 → 27/27**，R161 的两个原综合时运请求 REST **1/2 → 2/2**。月相推运八案三端 **15/24 → 24/24**，按作者历史钟的 159 个 TT 括区逐位符合，原公开哈希门保留 **0/24**。两项补齐既有 R47 的消费者，累计独立计算根因仍为 **125**。合入后集中回归 **124/124**，清单更新 75 个源码引用。当前 **5,811 组、15,353 项职责**，**2,056 个函数或类待审**，独立语义算法总数待定。 [主限](precision-acceptance.md#primary-direction-civil-clock-round162) · [月相及回归](precision-acceptance.md#lunation-extended-clock-round166) · [清单](algorithm-inventory.md)

近极 W01 `73-2` 同一闭窗的旧连续外钟有一个上升根，新连续外钟无根。旧原生 17 条反号边均排除该连续根。任注三例工程和事实判据 **57/57**，作者作用裁定 **0/3**，韦氏近贴冲的具名分歧保留。原 1,882 项仍为 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。近极 **43** 个失败节点、联合 ±1 毫秒 **23/53**、漏报 **160**、物理资格 **0/25**，八字 15172 **0/12**，事业 **1/2** 且第二案 **88 对 95** 继续使用原门。 [近极连续闭窗](precision-acceptance.md#polar-w01-modern-continuity-round165) · [合局书证和执行](precision-acceptance.md#bazi-luck-clash-source-round164-167)

<a id="round169-174-return-clock-and-authority"></a>

## R169–R171、R174 返照钟面及原失败裁定

日月返照八案按冻结勘误参考，三端 **9/24 → 24/24**，逐项 **258/408 → 408/408**。原参考两门 **3/24 → 18/24** 和 **228/408 → 378/408** 保留。合入后集中复验 **119/119**，另有共享钟面的独立直接对照 **252/252**。清单迁移 23 个源码锚点，补全既有 R47 的返照消费者，累计验收 **125** 项独立计算根因。 [返照前后臂与复验](precision-acceptance.md#return-extended-clock-round169) · [当前清单](algorithm-inventory.md)

近极原窗的旧连续上升根，在指定的新旧 ΔT 插值中从右端退出。17 条原生反号边的独立择边未决。八字三案事实与工程 **78/78**，具页局部作用 **1/2**。徐注所述酉丑会局和现行辰酉先占仍分歧，局部变更的固定反事实未解除 15172 的结构覆盖。原 **1,882** 项、近极 **43** 个失败节点、联合毫秒 **23/53**、漏报 **160**、物理资格 **0/25**、八字 **0/12**、事业 **1/2** 均保留。 [近极连续根路径](precision-acceptance.md#polar-w01-clock-homotopy-round170) · [八字原档及对照](precision-acceptance.md#bazi-15172-four-layer-round171)

<a id="round172-176-179-ingress-and-sukuyo"></a>

## R172、R176、R179 世俗盘生效历元与宿曜来源

世俗入宫盘共用起盘历元的 UTC 钟面和盘面当地投影，公元 1 年冬至消除同一事件两份 UTC 相差 8 微秒的问题。原冻结比较 **132/135 → 135/135**，其余 14 份同端回执完整业务相同。本修复补齐既有第十七批的原生主点传播，累计独立计算根因 **125**。 [世俗盘参考与前后臂](precision-acceptance.md#mundane-single-epoch-round172)

宿曜的江户历法与日月岁名义量核对十个定义、24 项职责。首臂 **735/738**，独立直接检查 **247/247**，相性字段修正后的同一配对三端 **46/46**。中央清单为 **5,821 组、15,377 项职责、6,327 个文件和符号组合、810 个实现文件**。7,517 个函数或类定义中，5,471 个具名、2,046 个待审。 [原表及固定回执](precision-acceptance.md#sukuyo-historical-month-round176) · [职责清单](algorithm-inventory.md#sukuyo-historical-month-inventory-round176)

任注六个印例的工程与事实检查 **188/188**，所选作者裁定 **6/9**。双酉共丑、辰酉与申子辰交叠、双冲兼巳酉半会仍有作用差异。原 **15172 0/12** 和事业 **1/2**，第二例 **88 对 95**，保持原判。近极 W01 的六个原时刻中，仅替换太阳黄经即可解释全部三处严格符号差异，C 替换仍有 **30/42** 槽未获唯一舍入字。原近极 43 个失败节点、160 个离散漏报、双轴 ±1 毫秒 **23/53**、物理门 **0/25** 均保留。原 1,882 项仍为 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。 [任注页证和逐项比较](~/.codex/artifacts/fatebridge-audit-20261123-round175/bazi-15172-combination-retention/handoff.md) · [近极六时刻对照](~/.codex/artifacts/fatebridge-audit-20261123-round177/polar-w01-six-word-optics/report.md)

活树集中回归 **146/146**，包括公元 1 年新增世俗盘回归、2026 年及 Vostok 控制、返照和宿曜原有用例。16,396 个绑定路径无漂移，584 个已加载项目模块均有绑定来源。八条已有果老职责统一行首格式后，机器导出可读取其原优先级。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round179/historical-calendar-and-ingress/integrated-regression/pytest-result.json) · [标签迁移](~/.codex/artifacts/fatebridge-audit-20261123-round179/historical-calendar-and-ingress/priority-label-migration.json)

<a id="round178-181-event-and-month-clocks"></a>

## R178、R181 多重回归事件和果老月限查表日

多重回归固定公开槽 **6/13 → 13/13**，78 个事件的数值和交付 **861/861**，组合复验保留世俗盘 **135/135**。插入秒、历史无唯一普通标签和扩展年可保留求解事件及 TT。上界案只在 REST 固定矩阵中执行。此项补齐既有时标及年界消费者。 [多重回归独立对照](precision-acceptance.md#multi-return-utc-round178)

果老月限按原名义点决定固定 `UTC+08` 日期，显示舍入跨日时明确交付实查日期。五案两入口三端 **24/30 → 30/30**，两臂 Schema 各 **30/30**。四个控制的 24 份同端回执完整业务相等，组合复放的 30 份回执与原合格臂同端完整业务相等。月限归入 R96/R97 已登记的精确出生钟传播问题，本批累计独立根因仍为 **125**。中央清单有 **5,826 组、15,387 项职责、6,329 个文件和符号组合、810 个实现文件**。7,519 个函数或类定义中，5,473 个具名、2,046 个待审。 [月限固定对照](precision-acceptance.md#guolao-month-date-round181) · [当前清单](algorithm-inventory.md)

活树集中回归 **472/472**。八个文件覆盖普通及特殊返照、世俗盘、共享 UTC 钟面和果老月限。16,457 个绑定路径无漂移，475 个已加载项目模块有绑定来源。回归输出记录 32 条警告。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round178/multireturn-utc-delivery/integration/integrated-regression/pytest-result.json)

近极 W01 的六点用同一模型分别替换地月质心位置与速度、月球减项。配套替换地月质心状态出现三次翻号，单换月球减项或末级舍入无翻号。78 个高度区间排零，原 17 条相邻反号边的取舍仍待独立裁定。原 1,882 项对账保留 **1,797 同名通过、24 映射通过、56 失败、5 退役未配对**。原近极联合毫秒门 **23/53**、物理资格 **0/25**、160 个离散漏报、八字 `15172` **0/12** 与事业 **1/2**（第二例 **88 对 95**）均沿用原判。 [保存端点与单项替换](~/.codex/artifacts/fatebridge-audit-20261123-round182/polar-w01-emb-lunar-attribution/report.md)

<a id="round185-187-return-labels-and-seasonal-sources"></a>

## R185、R187 返照当地钟面与己土三夏书证

太阳返照、月亮返照和综合时运共用多重回归的当地插秒投影。精确插秒起点保留 `:60.000000`，固定九案三端 **15/27 → 27/27**，逐项 **555/585 → 585/585**。15 份同端完整业务相等，12 份只更正当地标签和对应文本。三时区精确起点直接对照 **15/18 → 18/18**。这次补齐 R90 已登记的 UTC 历元交付问题。 [返照钟面与作者数值参考](precision-acceptance.md#western-return-local-leap-round185)

己土巳、午、未共用三夏正文和来源，具名书证 **63/120 → 66/120**，117 个非目标格相等。60 份公开回执及 20 组同版三端一致性通过固定对照。干位首判 **44/52**，按运行前已绑定的春月参考补齐漏项后，同一批回执为 **52/52**。四个印例的历史出生历元仍为 **0/4**。秦本刊记及徐、秦、梁之间的异读已有独立复核。累计验收的独立根因仍为 **125**。 [三夏固定对照和书证](precision-acceptance.md#bazi-ji-summer-source-round187) · [版本复核](~/.codex/artifacts/fatebridge-audit-20261123-round188/bazi-ji-summer-independent-review/handoff.md)

返照、钟面、调候和调用合同的 11 个文件集中回归 **789/789**。16,457 个冻结路径前后相同，928 个已加载项目模块均有路径绑定。测试后仅调整调候加载器的格式，已逐节点确认 AST 相等。 [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round187/bazi-ji-summer-source-audit/integration/integrated-regression/pytest-result.json) · [格式化后源码身份](~/.codex/artifacts/fatebridge-audit-20261123-round187/bazi-ji-summer-source-audit/integration/formatted-source-identities.json)

R187 封存时，中央清单有 **5,826 组、15,389 项职责、6,329 个文件和符号组合、810 个实现文件**。7,519 个函数或类定义中，5,473 个具名、2,046 个待审。独立语义算法总数待定。 [清单](algorithm-inventory.md)

R190 固定作者合角和下游光学时，精确时间商与实数多项式及项和使近极 W01 的 497、517 端点由正变负。只换后向速度可复现这两个翻号，518 的速度单换与配套结果符号不同。四臂差分中的旧臂时间范围较窄，原数值保留为各臂定义的差分。W01 原 17 条反号边的事件取舍尚未裁定。原 1,882 项仍为 **1,797 同名通过、24 映射通过、56 失败、5 退役未配对**。近极 **43 个失败节点、160 个离散漏报、联合毫秒门 23/53、物理资格 0/25**，八字 `15172` **0/12** 及事业 **1/2**（第二例 **88 对 95**）沿用原判。 [固定端点和四臂结果](~/.codex/artifacts/fatebridge-audit-20261123-round190/polar-w01-real-emb-terms/report.md)

R191 校订参评配运卷七的一处跨栏脱字。三个配运方案和局部资料查询共 **12/12** 份目标回执恢复馆藏读法，三份整日借除对照保留原句。三端数值、规则用途及运期逐项相同。补登 **28 个定义、30 组、41 项职责**，原书证转录修订单列，累计独立算法与执行根因仍为 **125**。 [书影与三端对照](precision-acceptance.md#canping-schedule-reading-round191) · [新增职责](algorithm-inventory.md#canping-schedule-source-inventory-round191)

R191 集中回归首跑 **157/158**，仅历史转录摘要的版本绑定失败。保留 `1.0.0` 原摘要，并补充现行 `1.0.1` 的逐字节校勘断言后，同一节点隔离复验 **1/1**。首跑与复验覆盖原 **158/158** 个节点。 [版本迁移与两次回执](precision-acceptance.md#canping-schedule-reading-round191)

## R194 印占出生日序和己土三秋书证

印占固定三端在记录载体勘误后为 **9/27 → 27/27**，独立分期 **103/309 → 309/309**。本批完善 R47 已登记的 UTC 年界消费者。己土申、酉、戌具名书证 **66/120 → 69/120**，首判 **2,068/2,068**。两处预留的 `analyze_destiny` REST 槽无路由，两则印例的绝对出生历元 **0/2**。累计验收仍为 **125** 项独立根因。 [印占](precision-acceptance.md#india-birth-utc-calendar-round190) · [己土三秋](precision-acceptance.md#bazi-ji-autumn-source-round192)

集中回归首跑 **7,627/7,629**，两处测试签名和导入迁移在同节点复验 **2/2**，两次执行覆盖原 **7,629/7,629**。中央清单有 **5,856 组、15,431 项职责**，7,519 个函数或类中 **5,501 个具名、2,018 个待审**。原 1,882 项对账仍为 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。 [回归与迁移](precision-acceptance.md#bazi-ji-autumn-source-round192) · [当前清单](algorithm-inventory.md)

## R193 与 R196 的组合验收

印占生时网格固定三端 **12/33 → 33/33**，年界 **0/21 → 21/21**，独立 TT **37/37**。属于 R47 的消费者补齐。组合回归首跑 **386/388**，补齐星历 fixture 导入后原节点 **2/2**，两次执行覆盖原 **388/388**。 [印占对照](precision-acceptance.md#india-birth-grid-calendar-round193) · [组合回归](precision-acceptance.md#bazi-ji-winter-source-round196)

## R196 己土三冬书证

己亥、己子、己丑新增 22 条具页条件，调候具名覆盖 **72/120**，其余 48 格仍待校。固定 120 格简表继续全量对照。隔离首判 **2,078/2,078**，计划 78 个公开槽中有 76 个真实响应通过输出 Schema，另两个缺少 REST 路由。两则印例的绝对出生历元 **0/2**。全盘取用、力量及预测效度未裁，原 `15172` **0/12** 和事业 **1/2（88 对 95）**沿用原账。本批增加具名来源，独立根因增量 **0**。 [书证与固定对照](precision-acceptance.md#bazi-ji-winter-source-round196)

## R198 CLI 档案钟制

固定 CLI 主队列 **17/22 → 22/22**，六条太阳钟子项与独立命令业务一致性 **0/6 → 6/6**，组合回归 **8/8**。明确太阳钟制交由各子工具校验，兼容子项恢复计算。累计验收 **126** 项独立根因。 [钟制和数值对照](precision-acceptance.md#profile-recorded-clock-round198)

<a id="round199-place-resolution"></a>

## R199 地名解析与城市别名

合入短码位置、同跨度州与国家、逗号边界、行政祖级和乌兰巴托居民点别名五项独立修复，累计 **131** 项。最终组合的三端定位及 Schema 均为 **114/114**，目录为 **16,082/16,082** 和 **16/16**，集中回归 **208/208**。首个组合的门牌号回归及祖级首跑的退出资格缺口保留。 [固定对照与来源](precision-acceptance.md#place-qualifier-ownership-round199) · [最终三端](~/.codex/artifacts/fatebridge-audit-20261123-round200/place-combined-qualification/comparison.json)

中央清单登记 **5,873 组、15,472 项职责、6,380 个文件和符号组合、815 个实现文件**。7,520 个函数或类中 **5,518 个具名、2,002 个待审**。五项修复的验收范围是地址解析、代表点和调用一致性。 [中央清单](algorithm-inventory.md)

<a id="round200-pair-birth-domain"></a>

## R200 双人出生年份与历史事业分项

双人出生年份准入新增一项独立合同修复，累计 **132** 项。直接模型及两套公开 Schema 均由 **4/9 → 9/9**，实际三端由 **12/27 → 27/27**。成功控制业务相等，已生成同步后的 MCP 调用合同。中央清单现有 **5,884 组、15,490 项职责、6,393 个文件和符号组合、820 个实现文件**。7,520 个函数或类中 **5,529 个具名、1,991 个待审**。 [出生年份固定对照](precision-acceptance.md#pair-birth-domain-round200) · [源码职责](algorithm-inventory.md#pair-birth-domain-inventory-round200)

事业第二案由 95 到 88 的相邻版本、输入与每项计算已追溯，独立分项复算 **133/133**。原分数门仍为 **1/2**，八字 `15172` 原门仍为 **0/12**。原 1,882 项对账保持 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。 [事业版本归因](precision-acceptance.md#career-score-lineage-round200)

<a id="round202-western-birth-and-place"></a>

## R202 当地出生年份与跨文字地名

合入两项独立根因修复，累计 **134** 项。共享星盘和关系盘声明当地出生年为 **1–9999**，公开 Schema 的日期资格一致项由 **6/14 → 14/14**，准确错误字段和方向由 **0/12 → 12/12**。地名解析修正了相邻带大小写字母和数字的词界，固定三端由 **33/48 → 48/48**。蒙古语 `Улаанбаатар` 补入 R199 既有的城市别名记录。两项修复合入后，集中回归 **111/111**，17,527 个绑定路径无漂移。 [出生年份对照](precision-acceptance.md#astro-birth-year-domain-round202) · [地名对照](precision-acceptance.md#place-unicode-boundaries-round202) · [集中回归](~/.codex/artifacts/fatebridge-audit-20261123-round202/integrated-regression/pytest-result.json)

中央清单现有 **5,890 组、15,499 项职责、6,399 个文件和符号组合、821 个实现文件**。7,521 个函数或类中 **5,534 个具名、1,987 个待审**。原近极 53 根中，联合 TT／UT1 毫秒门仍为 **23/53**。原 160 条遗漏有 54 条不同的有向邻边，未发现与原 53 根同站、同 UT1 的事件对。梁湘润核对保留原 **15172 0/12**、事业 **1/2**，两项仍缺足够书证裁定现工程规则。 [中央清单](algorithm-inventory.md#western-birth-and-place-inventory-round202) · [近极原始配对审查](~/.codex/artifacts/fatebridge-audit-20261123-round202/solar-event-pairing-receipts/report.md) · [梁氏印例交付对照](~/.codex/artifacts/fatebridge-audit-20261123-round203/bazi-liang-source-delivery/handoff.md)

## R204 关系盘日期纠错与来源对照

关系盘 REST 保留双方出生日期各自的纠错路径。固定公开对照中，准确日期位置由 **14/19 提升到 19/19**，完整问题列表由 **31/35 提升到 35/35**。两臂各 **52/52** 按预期接受或拒绝。集中回归 **68/68**，累计验收 **135 项**独立根因。中央清单现有 **5,890 组、15,500 项职责、6,399 个文件和符号组合**。 [固定对照](precision-acceptance.md#relationship-calendar-error-path-round204) · [中央清单](algorithm-inventory.md)

近极指定邻边在同一冻结光学定义下相距 **20.116568 微秒**，左正右负。原三端日窗都有右端，双端同次观察仍是 **0/3**。独立姿态区间在右端含零，原联合毫秒门 **23/53**、物理门 **0/25**、离散漏报 **160 条**仍按各自判据记录。梁湘润两则印例的关系判据为 **3/6**。 [近极双端对照](precision-acceptance.md#polar-binade-observation-gap-round204) · [梁氏印例](precision-acceptance.md#bazi-liang-punishment-conditions-round204)

## R205 方法登记、地址邮区与正午纠错

字面排柱校核与紫微规则目录分别登记实际方法和来源，紫微本命、运限、规则目录均公开四化选择器。英国格式地址使用 UPU 固定邮区表，三端公开归属或预期拒绝由 **24/42 → 42/42**。两项独立根因合入后累计 **137 项**。卜卦与择日的正午纠错位置由 **0/34 → 34/34**，归入 R204 共用错误寻址。中央清单有 **5,894 组、15,514 项职责、6,406 个文件和符号组合**，仍有 **1,986 个定义待审**。 [方法与地址](precision-acceptance.md#method-and-address-scope-round205) · [正午对照](precision-acceptance.md#noon-origin-error-address-round205) · [中央清单](algorithm-inventory.md#method-address-inventory-round205)

R206 的近极窄窗候选恢复原 160 条漏边。独立控制中 **1,132/5,904** 个激活窗超过预定预算，**14/5,904** 丢失原已交付的交越，候选未合入。原联合毫秒门仍为 **23/53**，物理门为 **0/25**。 [独立控制](precision-acceptance.md#polar-narrow-seam-replay-round206)

## R209 条件方法与英国地址字段

占星骰的公开目录声明两种方法，运行证据按实际 `chart` 启用天象方法、图边和来源误差预算。固定三端方法与误差适用性 **12/12**、`chart` 归属 **12/12**，业务及运行策略与前像 **12/12** 相同。静态方法归属沿用 R205 的规则，运行时条件启用单列一项独立根因。地址道路字段和两岛居民点短写沿用既有根因，新三端 **30/30**、直接对照 **28/29**。 [固定对照](precision-acceptance.md#conditional-method-address-round209)

紧凑地点字段须能由同一实体、其祖级或相容辖区解释。此项修复独立于邮政道路识别，固定直接对照 **30/37 → 37/37**，三端 **39/60 → 60/60**。保留原探索失败和 `Walkabout` 原点位门。累计验收 **139 项独立根因**。 [完整地点字段对照](precision-acceptance.md#place-field-ownership-round209)

第一阶段集中回归 **260/260**，含地点解析 110 项、占星骰 113 项、计算证据 37 项。占星骰涵盖八个三端业务对照，计算证据组遍历全部 CLI 可用工具。最终地点字段版本单独通过 **120/120**。两阶段各核对 17,527 个路径，运行期间无漂移，已观测项目模块均有来源绑定。第二阶段合入的占星骰测试仅排版变化，语法树与第一阶段执行的文件完全相同。 [第一阶段回执](~/.codex/artifacts/fatebridge-audit-20261123-round209/integration/integrated-regression/pytest-result.json) · [最终地点回执](~/.codex/artifacts/fatebridge-audit-20261123-round209/integration/place-field-regression/pytest-result.json)

中央清单有 **5,901 组、15,531 项职责、6,408 个文件和符号组合**，**1,984 个定义待审**。93 个目录记录登记 68 个方法。原 1,882 项仍为 1,797 同名通过、24 映射通过、56 失败、5 退役未配对。算法总数、全域精度和整体 SOTA 仍待核实。 [当前清单](algorithm-inventory.md#conditional-method-address-inventory-round209)

## R214 行星时与英国信箱地址

开日日出的民用星期现从保留扩展年的 UTC 日历投影得到。固定三端 **12/15 → 15/15**，Swiss Ephemeris 2.10.03 对应三处升落相差至多 **0.131 秒**。这项改动补齐既有民用钟域根因的西占消费者。 [行星时固定对照](precision-acceptance.md#planetary-hour-extended-calendar-round208)

英国无道路信箱地址以唯一信箱、邮镇和完整邮编提供辖区证据。固定直接 **20/26 → 26/26**，三端 **15/24 → 24/24**。原探索失败及一般无道路建筑地址保留原验收范围。这项改动补齐既有英国邮政辖区根因。 [信箱地址固定对照](precision-acceptance.md#place-roadless-postal-round210)

合并源码集中回归 **295/295**，含西占钟面与星历来源 169 项、地点解析 126 项。原西占候选 **165/169** 保留，四条失败用例的注入已迁到实际 UTC 日历所有者，原断言在集中批次通过。绑定 **17,527** 个路径，无漂移及未绑定项目模块。合入排版仅将同一导入语句的两个名字排序。累计 **139 项独立根因**。中央清单有 **5,902 组、15,536 项职责、6,409 个文件和符号组合**，**1,984 个定义待审**。 [集中回归收据](~/.codex/artifacts/fatebridge-audit-20261123-round214/regression/pytest-result.json)
