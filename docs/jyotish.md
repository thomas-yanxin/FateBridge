# 印度占星：本命、分盘、Sthana Bala 与 Vimshottari

当前源码候选提供 `parashari_lahiri_core_v29` 有限 Parashari 实现。`astro_india_chart`（REST `/api/astro/india`）生成本命与分盘，`astro_vimshottari`（REST `/api/astro/vimshottari`）生成月宿 Vimshottari 主运／次运。CLI、REST 和 MCP 共享请求、计算和输出模型。源码功能与已发布包可能存在版本差异；本页不表示已完成发布。

印占出生钟制必须已确认。民用时刻须显式填写合法 `birth_timezone`（IANA 名称或 UTC 偏移），或由受支持且不歧义的 `birth_place` 解析；未知时区在星历计算前拒绝，不再默认 UTC。明确 UTC 及显式已知的 LMT／LAT 继续支持；坐标、分析时区和太阳钟显示不能确定出生民用时区。旧盘须结合保留的原始请求及运行回执核对，不能仅凭计算正文追认时区。反例、原回归失败、归档恢复与当前接入范围见出生时区来源审计（本地数据：`validation/jyotish-timezone-input-audit.md`）。

v29将D1逐星`physical_state.longitude_speed_degrees_per_day`接入共享视位置导数，并用同一返回速度判定顺逆／驻留及所选Santhanam太阳角距分支；原生值保留在`longitude_speed_native_degrees_per_day`。`longitude_motion_context.rate_basis`逐体、逐后端区分完整视位置导数、月球光行时链部分修正及原生值，不把月亮或木土星的有限修正写成已具备完整导数。Rahu／Ketu保留声明的解析交点理论。辅助采样后端变化时，只有精确复现原中心状态及文件上下文才保留原生速率；其他来源错误继续拒绝。该改动不替换古典平均运动或Cheshta Bala，不认证驻留时刻与现实事件精度。原参考与未达标案例、来源修复和主工作区验收见D1瞬时速度审计（本地数据：`validation/jyotish-d1-motion-audit.md`）。

原 96 案的位置及速度框架差异现已作全量归因，但原 64/96 结果不重评。新增七曜 112 条参考已冻结，当前 110 条通过参考自检、两条远期月亮速度仍未收敛，新框架实现尚未比较；见框架归因与新参考（本地数据：`validation/jyotish-lahiri-frame-attribution-audit.md`）。

逐星 `physical_state.longitude_motion_context.continuous_frame_state` 另提供连续Lahiri框架的笛卡尔／球面状态对照，使用 `R x` 与 `R (gamma v) + R' x` 同时生成位置和速度。当前 `status=partial`：输入仍为原生J2000视位置／近似速度，单位时间映射与完整物理视速度未认证，不替换主D1因子或顺逆标签。原生J2000孤立位置分支的差异继续显式返回，不能把新的连续模型核对替换原兼容性失败。独立完整状态参考、业务日期端点、来源恢复与协议验收范围见连续状态接入审计（本地数据：`validation/jyotish-continuous-state.md`）。

月球在同一对象的 `source_derivative_state` 中另给出已核查固定框架源公式的三维导数变换，包含光行时与观测者导数；固定输入基底和随TT变化的输出框架分别处理。该状态仍为 `partial`，保留原生速度对照和原有主字段；未应用时按具体来源原因解释。数学参考、检出限制和保留失败见月球源状态审计（本地数据：`validation/jyotish-lunar-continuous-source-state.md`）。

`india.profile.earth_rotation` 回显四轴实际采用的自转政策、TT/UT1历元与来源限定；`local_apparent_sidereal_meridian_degrees` 是当地视恒星子午圈的赤经角度，不能当作黄道MC经度。领域调用中显式选择的C04来源会传入隔离计算进程，并在表外报错；印占公开请求仍使用既有选项。默认结果保护、来源反例及旧版策略检查迁移见印占自转依据审计（本地数据：`validation/jyotish-rotation-provenance.md`）。

后续完整核验了原112条的Horizons直接ICRF角速度，但其打印预算及与方向差分的冲突仍未解决，不能用它替换原参考；密集TT列表也因返回时刻不符被拒绝。见参考角速度来源审计（本地数据：`validation/jyotish-horizons-rate-source-audit.md`）。

独立DE441几何解码器已对照全部364687条官方样本，360001条达原准则、4686条缺源，总门槛未通过；修正了该研究解码器的最终文件端点及无效零状态输入。它只提供TDB几何参考基础，不认证TT视位置、原典或现实预测，见独立几何解码审计（本地数据：`validation/jyotish-direct-de441-decoder-audit.md`）。

独立接收时刻原型已保留全部112例、两种时间口径及五阶段的1120组视位置与完整导数结果；内部四步长差分和ERFA公式核对一致，远期时间模型资格及原两条月球速度参考仍未解决。未修改生产算法或重评旧门槛，见完整视位置导数原型审计（本地数据：`validation/jyotish-apparent-prototype-audit.md`）。

后续重新核对112份原始响应及224个旧速度向量，并完成42560个时间标签／舍入控制，未发现可单独解释原月球差异的舍入口径；两条旧失败保留。三来源数值时差模型随后完成独立解码、同输入CSPICE核对及局部TT逆解，原月球冲突及各源缺覆盖仍保留，未授予新物理参考资格；见时间绑定与舍入控制（本地数据：`validation/jyotish-clock-sampling-audit.md`）及数值时间独立核验（本地数据：`validation/jyotish-integrated-clock-audit.md`）。

锁定月球源码的独立分解进一步验证了已有光行时链JVP，并保留两项剩余速度近似及其完整求导比较。该研究只在固定ICRF连续模型中成立，未接入生产或授予完整月球认证，见月球源公式导数审计（本地数据：`validation/jyotish-lunar-native-derivative-audit.md`）。

后续已将其中的空间光行差雅可比修正接入共享速度计算，光行时链项和空间项分别返回；D1继续声明为部分修正。加速度及框架传播检查、所有误差增大行、原生算术逐位一致性失败和源码恢复范围见月球空间速度修正审计（本地数据：`validation/jyotish-lunar-spatial-motion.md`）。旧参考及原门槛未重评，未新增现实预测证据。

新一轮已接入观测者加速度及固定接收框架的源公式导数余项，直接使用原生光行差前状态，按同一文件窗口选择预定差分方向并精确恢复中心。采样输入、估计及不适用原因保留，数值分项和文字同步；完整移动框架、原生二进制身份及物理TT时差映射仍未认证，见月球观测者与源导数审计（本地数据：`validation/jyotish-lunar-observer-motion.md`）。旧失败没有改判，现实预测和独立解释盲审样本仍为0。

v27修正Uchcha及Dig角距的提前舍入：保留给定二进制经度、上升／天顶及其未舍入对点，求短弧后才把角距和力量各自转换为最终浮点数。原Santhanam系数、零力点和公式不变；Dig的`basis.numerical_policy`区分显示对点与实际操作数。冻结数学集合中旧实现分别有16和654个末值差异，最大约10^-14 Virupa；这不是天文或现实预测误差界。来源、完整依赖核对、失败记录和验收范围见力量角距数值审计（本地数据：`validation/jyotish-strength-arithmetic-audit.md`）。

v26修复地方平均午夜附近的日期进位：对实际返回的UT1儒略日和给定经度按其精确二进制值分类，避免先把两者相加到大浮点数再转换日期。360／30日岁月主口径、传统历元和时间尺度模型均沿用原定义；更正日期后，岁月主、星战前置回执、Kala分支及生时网格、相关主题事实与数值文字须使用同一更正结果。297个冻结边界探针的旧45处差异全部消除；这是特定输入的数值检验，不是总体错误率或现实预测准确率。完整比较、首次重放失败与缓存缺失后的恢复范围见平均日期边界审计（本地数据：`validation/jyotish-mean-date-audit.md`）。

v25另列Aiyar1905自己的七曜原始PAV／BAV／SAV及自身削减链，位于`india.ashtakavarga.charts.D1.source_profile_comparison.aiyar1905`。逐项原页核验发现其672个规则单元中有6个与Rao表不同，月亮／金星总量及SAV337仍相同，不能只凭总量或一个软件相符就认证同一来源。Rao默认保留；原v24比较继续表示“在Rao原始BAV上仅换削减读法”。新分支对每张盘和生时样本各用自己的完整输入，主题原生文字同时给两源实际局部计数与同run引用。非D1应用及分盘构造是另行声明的比较选择，不称Aiyar整书已验收，详见完整原始表来源比较（本地数据：`validation/jyotish-aiyar-bav-audit.md`）。

v24另提供Aiyar1905英译注的八分法削减比较，位于每张表`reduction_analysis.source_profile_comparison.aiyar1905_commentary`。该口径完整保留其三合原始双零规则和同主单占据等值规则，回显逐步输入、规则与结果；Rao默认口径的空值与Pinda不被替换。来源是第IX章英文N.B.注释，不能写成Varahamihira某偈的逐字规则或整部Aiyar译本已验收。新口径只给削减计数及其和，没有另配Rao的Pinda乘数。实际来源与当前候选验收见译注削减比较审计（本地数据：`validation/jyotish-aiyar-reductions-audit.md`）。

v23将Vimshottari各层的精确有理数偏移保留到同一个出生历元，最终边界只取最近微秒、正中取偶，避免已舍入主运起点再次带入递归舍入。`vimshottari.time_quantization`回显本次出生UTC、年长微秒数、月宿精确比例及实现口径；比例分子／分母以十进制字符串保存，避免JSON客户端整数精度丢失。Rao16.2／16.3负责传统比例，微秒舍入属于另列的FateBridge实现约定，不表示出生钟、月亮位置或事件预测的微秒准确度。当前候选验收与旧输出变化清单见全局边界舍入修复审计（本地数据：`validation/jyotish-dasha-global-epoch-audit.md`）。

v19统一可选太阳时显示与本命计算的物理时标：保留记录民用时刻，从同一TT、模型UT1及视太阳时角推导无时区的墙钟标签。SDK对象携带的旧派生标签在本次隔离会话内重算，不移动其出生UTC；本命、分盘和达沙不因显示开关改变。`clock_context.solar_display_context`回显太阳来源、TT／UT1、均时差、模型和可表示状态。缺少可表示标签时保留物理计算，不能把显示精度当作实测DUT1或出生钟准确度。详见太阳时显示一致性审计（本地数据：`validation/jyotish-solar-display-audit.md`）。

共享视黄经速度候选`fatebridge_complete_position_derivative_v6`处理重叠星历文件在求导途中切换的问题。原生中心状态须精确复现，辅助方向须来自同一文件上下文并通过连续三层联合检查；原有成功计算路径保留。原接缝出生时刻必须计算成功，不能由相邻日期替代。来源重建与数值收敛不是原典或预测有效性认证；候选的完整验收状态与独立参考范围见星历接缝求导审计（本地数据：`validation/jyotish-segment-motion-audit.md`）。

共享前版`compressed_file_endpoint_context_v1`在受管理的物理`calc/calc_ut`实际落入已观察文件终点64个TT浮点单位内时，先以文件头选择邻接上下文，再重算完全相同的原调用。它可能修正原生中心星位，须与随后v6“保持传入中心”的求导契约分开解释。`india.profile.native_execution_context.compressed_file_endpoint_policy`记录原始／所选六维状态、TT、文件名、锚点和累计调用数；锚点只是文件选择，不是出生时刻。未能保持模型、DE版本、返回帧或原时标时拒算。尚非所有重叠文件的统一策略，也不覆盖第三方内部直接调用或原生日出搜索内部的每次求值。方法、独立参考与完整验收状态见文件端点上下文审计（本地数据：`validation/jyotish-endpoint-context-audit.md`）。

此前`compressed_file_endpoint_context_v2`在印占私有进程中先清理所拥有的原生缓存，以原接收时刻的几何太阳预选来源，再执行完全相同的目标坐标调用；外部调用者保留旧的后调用保护。相关接收／发光时刻的依赖采样先验证同一文件区间、已建立的新接收状态、实际依赖TT及前后文件身份，再保留该上下文，不放宽来源检查。`native_coordinate_contexts`逐项回显实际目标和帧，未知的旧目标状态保持null，不伪称星位未变。`apparent_position_policy`及D1逐星`native_position_interpretation`直接给出太阳内部虚拟方向的模型限定；达沙生时分组保留离散含义，不把连续射线几何变成更多分组。参见私有坐标上下文审计（本地数据：`validation/jyotish-private-coordinate-context-audit.md`）。

共享层另以`external_geocentric_solar_dependency_rebuild_v1`为普通原生地心视太阳调用重建接收与两个回溯时刻的共同来源，不重置外部调用者配置。它解决原1800年普通星盘的中心状态与求导两侧不一致；原收敛线与失败记录保留，印占私有计算继续沿用已有隔离。332条修改前来源记录及独立算术的范围见太阳共同来源审计（本地数据：`validation/jyotish-solar-common-window.md`），不作为新增物理精度、原典或现实预测资格。

连续辅助状态的`continuous_native_input_binding_v2`将实际原生向量、返回标志和来源身份绑定到匹配输入的独立数学期望。全部518组当前输入在FateBridge之外逐位重建，2590次高精度投影核对通过；原夹具和阈值保留，49组旧生产者兼容性差异继续标为未通过。契约迁移与数学／物理资格的区别见输入绑定核验（本地数据：`validation/jyotish-native-input-binding.md`）。

v17把印占请求的来源会话延伸到出生钟时解析之前，记录LAT反解迭代、最终求值与往返检查的实际太阳来源，并与名义时刻重算及原生赤道太阳对照。不同来源的旧对象返回类型化503来源错误，出生时刻不静默重定位。统一Moshier和完整数据文件均继续支持；LMT不增加太阳星位前提。旧对象缺少原始身份时保留`original_sun_identity_incomplete`，不能据此认证文件读取或出生钟精度。完整专项及跨平台验收状态见钟时来源修复审计（本地数据：`validation/jyotish-clock-source-fix-audit.md`）。

v18将一次完整印占计算放入新的私有exec进程：从服务层出生钟时解析到星位、宫位、太阳事件、全部生时样本与达沙证据，均使用该进程的原生状态。它排除父进程陈旧Delta-T表及手动覆盖值，保留当前显式数据路径、JPL选择与冻结执行钟；SDK出生对象仍保留原始物理时刻。`india.profile.native_execution_context`记录隔离方式及辅助时间文件候选的首末指纹范围。外部表／旧名表与闰秒辅助文件的途中新增、删除或内容改变均返回类型化来源错误；这些检查不认证表内数值或原子文件读取。修复前反例与较弱原型的漏检保留在Delta-T状态调查（本地数据：`validation/jyotish-delta-t-investigation.md`），当前验收见完整原生上下文修复审计（本地数据：`validation/jyotish-native-context-fix-audit.md`）。

v16新增逐物理星体、逐坐标帧的星历来源核验。本命、赤道帧及实际存在的J2000运动帧记录可观察文件的SHA-256、DE编号与覆盖范围；生时网格拒绝混合后端、跨样本改变版本或同名文件内容的比较；原生印占网格可使用合法相邻同版本数据段。通用建盘兼容层还受独立的运动差分收敛检查约束，冻结验收快照在2400年连接处的已知限制见v17修复审计。统一Moshier网格继续支持；不会删去不一致样本，也不自动把全盘改成较弱模型。`india.profile.physical_ephemeris_source`与`birth_time_sensitivity.source_comparison`保存来源及网格引用，单项可用如`by_factor.ecliptic_Sun.model`的严格字段投影读取。文件首末指纹相同不证明原子读取或天文精度，详见来源一致性审计（本地数据：`validation/jyotish-source-cohort-audit.md`）。

v15修复同一UT1日期内出现两个日出或两个日落时，旧逐日一次查询漏掉第二个事件的问题。支撑窗口保持八日，逐个检索当前日界内的后续事件，日主／时主和昼夜三分使用实际完整事件序列；`solar_events.enumeration`回显检索口径。1秒仅是越过同一数值根的查询步长，事件时刻本身不平移，也不表示记录或观测精度。129个独立DE421／Skyfield事件及已知反例见太阳事件枚举审计（本地数据：`validation/jyotish-solar-enumeration-audit.md`）。

v14修复极夜结束后因缺少不相关日落而抹去日主／时主／三分主星的问题。Dina／Hora使用连续日出对，Tribhaga独立使用当前相邻昼夜端点；`solar_context`分别回显`sunrise_day_status/active_arc_status`，部分有依据时保留部分结果。生时网格记录各依赖状态和覆盖数，解读回执携带同run状态；不补假日出、午夜或未知时主。详见太阳事件依赖审计（本地数据：`validation/jyotish-solar-brackets-audit.md`）。

v13增加独立的 `drekkana_profile=santhanam_27_6|raman_36`，默认继续使用Santhanam。选择 `saptavargaja_profile=raman_30` 与 `drekkana_profile=raman_36` 后，五个位置分量及其合计可以完整对照已冻结的参考实现；其关系、分盘输入仍保留各自来源，不认证完整单一原典六力。Raman详细条文36及例12取15 Virupa，书末摘要105却取60，冲突保留在 `source_reading_conflicts`。详见分段力量来源审计（本地数据：`validation/jyotish-drekkana-audit.md`）。

v10 的完整生时网格、独立运期运算对照及未通过项目见本轮验收记录（本地数据：`validation/jyotish-dasha-grid-audit.md`）。这些检查不证明现实预测有效。

v7新增显式可选的五星运动力平均模型，默认 `cheshta_model=unadjudicated` 继续保留五星缺失。选择 `simon1994_j2000` 后，在1900–2050出生TT窗口内用Simon等人的完整长期平均黄经多项式及另算的几何真位置计算；两者统一到J2000平均动力黄道／春分点。此口径独立于D1的Lahiri地心视位置，不能把D1／分盘经度或真太阳代入平均位置。太阳平均黄经取地球平均黄经加180度。

这是一项明确声明的现代天文模型，不代表Raman的1900历元表已通过验收。原表54项关系矛盾及参考软件反例仍保留在运动力来源审计（本地数据：`validation/jyotish-cheshta-audit.md`）；后续第二版见证校勘（本地数据：`validation/jyotish-raman-motion-collation-audit.md`）发现19个清晰单元与现用见证不同，较早见证自身仍有34条关系冲突，两版输入不能拼接。新模型来源、独立对照、适用范围与失败记录见平均模型审计（本地数据：`validation/jyotish-mean-model-audit.md`）。完整六力总量仍为null，真实事件独立检验仍为0例。

主题事实按本次宫主实际采用的来源标注运动力：太阳取同run的Ayana，月亮取同一性质分支的Paksha，二者不因选择五星模型而获得Simon标签。其余五星仅在模型实际计算时附带Simon辅助来源；默认未裁定或越界时明确未计算。`calculation_context.method_context.input_claims`保留实际上游字段路径和值，不把全局选择当成本宫主已用的算法。详见逐宫主来源修复（本地数据：`validation/jyotish-ruler-provenance-audit.md`）。

五星来源回执还会核对声明TT、模型均值、实际操作数、几何字段与完整角度分支，拒绝末值相同但过程矛盾的包；实际对径仍保留双分支和null。该计算链校验（本地数据：`validation/jyotish-cheshta-chain-audit.md`）不替代独立星历参考、原典裁定或真实模型盲审，正常输出保持原值。

## v9 名义盘、条件证据与解读范围

`india.reading_basis`明确按所填出生时刻的名义值计算。没有给出生时误差时，`options_basis=nominal_only`且敏感性仍为`not_assessed`，不能当作已证实精确；给定误差后，星宿、宿主及宿足与分盘使用同一最多30秒UTC网格。`nakshatra_alternatives`列出发生变化的星体／上升及覆盖数，覆盖数不是概率；没有列出变化也不证明连续区间内没有边界。原生解读会把名义月宿与抽样候选一并陈述，达沙摘要也明确使用名义生时。

每项主题力量的`calculation_context`携带该宫主自己的条件数值、实际同run字段路径、模型／性质约束和局部不可用依据。`computed_consensus`是已算分支一致，`conditional_results`是分支都已计算但结果不同，`unavailable`是当前无可用数值，`partially_computed`是部分分支有值；共识不等于原典裁定。不能把null统一写成零、漏算或用户资料不足，也不能由某个星体的全局缺项否定另一个宫主的已算结果。

Vimshottari生时端点／中心样本若晚于目标，返回`omitted_samples`和实际覆盖数，不能悄悄略过后声称全范围完成。这里核验的是计算和原生文案的证据传递；任意模型自由文本仍须独立审阅。6个语义准备案例属于已知开发回归集，不计作独立留出样本或现实预测。详见解读证据审计（本地数据：`validation/jyotish-fidelity-audit.md`）。

## v8 条件式星战金额

`kala_bala.components.yuddha_bala`按已核验页图的Raman76–77计算：遍历五星全部10对，以最短黄经差严格小于1度检索候选；两星独立交战时，取Sthana、Dig及Natha至Hora的同分支合计差，除以原书固定Bimba系数差，按较小黄经者加、另一星减。该前置合计不含Ayana、Cheshta、Drik、Naisargika或星战自身。固定盘面系数不是当前测得的角直径，不按天文距离动态替换，也不自行截断到60。

计算保留每一分支的输入、前置合计、分母、金额及来源。水星／月亮性质未裁定时保持相关分支；最终Kala按同一分支相加，不能先拿不唯一的分量摘要相加。同经、跨黄经零点、连成三颗以上的同时交战或缺少前置输入仍保留该对缺失；独立的另一对可计算。生时网格记录候选／判定变化及每个分支范围，范围与覆盖数均不是概率。

这是Raman星战公式对本次已声明力量输入的应用：上游仍各有Santhanam／所选七分盘读法，不认证完整单一Raman六力。Santhanam27.20给出另一公式，不混作同一规则。详见星战规则与独立对照审计（本地数据：`validation/jyotish-war-audit.md`）。

## v6 时间分量与月亮分类修正

`kala_bala`计算视太阳昼夜、月相、昼夜三分、岁／月／日／时主和Ayana；第九项星战在v8按上文条件计算；无候选给0，不能计算的参与者保留缺失。Hora为日出后的等长平均小时，和西占昼夜不等时小时分开；岁／月主为原书360／30日传统口径。`cheshta_bala`太阳取本次Ayana、月亮取本次Paksha；其他五星默认保留null，v7可显式选择上文的现代平均模型。它们都是出生时刻的本命分量，不是分析年份的时运。

此前v5只按盈亏处理月亮性质；原书还列有第八日窗口的另一表述。v6保留这项作者内分歧及边界日段，不能挑较高分或把条件分支当概率。新增赤道坐标与日出事件均有后端记录，严格星历模式覆盖两者；无极地日出不造默认时间。新JPL请求超时后，用原有21个JPL黄道位置及独立ERFA转换复核赤道帧，没有冒充新增数据。

细节、失败和复现方法见时间分量审计（本地数据：`validation/jyotish-kala-audit.md`）。完整六力总量仍为null，未给出强弱达标排名。

## v5 新增力量计算

`india.strengths` 新增 `dig_bala`、`naisargika_bala`、`drik_bala` 及 `shadbala_assessment`，每层保留自身来源、算法和范围。

- 方向力依据 Santhanam 27.7，使用实际恒星上升／天顶及其对点的黄经，从无力点取最短弧除以3。整宫起点不能代替角点；UT1仍是已声明的模型估计。
- 自然力依据 Santhanam 27.14，土、火、水、木、金、月、日依次为 `60/7` 的1至7倍。它是固定传统系数，不是亮度实测，也不区别个人现实能力。
- 相位力采用 Raman 113–120：从施相星到受相星的有方向黄经差，普通分段值加特殊相位附加值，再按施相星的传统正负分类取四分之一。它不同于已有的整宫相位，不能转成无方向最小夹角。按附加规则，土星某些角距值可超过60，没有擅自截断。

Santhanam 第26章偈颂专式与注释附加法存在差异，第27.19又提到水星／木星完整相位量；本层选择有明确分段与例表的 Raman 条文，并登记选择与差异，不能宣称整套六力均按同一作者无争议实现。已核对固定Raman扫描本PDF43、87–93页图，具体重印版仍未核定。端点统一用右侧半开区间，是声明的实现约定，不冒充作者已裁定的端点。

原书例53–55的角距及合计存在内部矛盾，现由`drik_bala.source_witness`与`source_reading_conflicts`保留。标准算例将水星判为负性质的脚注没有给出可推广的数值关联阈值，因此任意盘仍保留条件分支。公式数值未改，不能用有矛盾的例表反调公式或认证完整单一原典六力。详见页图与算例审计（本地数据：`validation/jyotish-drik-primary-audit.md`）。

Santhanam第26章与27.19现另有未施用来源字段，记录译文／注解读法、火星249度与Raman240度差异，以及540行普通表中的两处坐标关系冲突。初次转录漏读续表的更正过程、精确有理数审计及未通过的来源门槛见Santhanam相位校勘（本地数据：`validation/jyotish-santhanam-drishti-audit.md`）。新增字段不改变当前Raman数值；各读法不能拼接取高分。较早Raman见证现另有完整给定输入核验（本地数据：`validation/jyotish-drik-editions-audit.md`），区分原印数字冲突、公式计算和算例性质，不将不同版本的黄经或水星符号拼接。正式主题解释还会按本次D1核对完整相位力计算链，拒绝与矩阵、性质、贡献或来源声明不一致的包；这类内部错误不会要求用户改动出生资料。见计算链核验（本地数据：`validation/jyotish-drik-chain-audit.md`）。

水星“好／坏关联”的精确判据尚未裁定，不用同星座或燃烧阈值擅自补成定论。`drik_bala.scenarios` 分别保存水星为传统 benefic／malefic 的结果及逐星贡献；v6同时保留月亮盈亏与原书第53节第八日窗口的不同读法，有分歧或边界不明时保留分类分支。`summary` 仅在所有分支值相同时给数值，否则为 `null`；null不表示零或没有相位，分支也不是成功概率上下界。正负号仅表示所选传统规则，不能直接翻译成现实事件吉凶。

生时误差沿同一UTC网格给方向力连续范围及相位各分类分支的范围与样本覆盖数，覆盖数不是概率。`shadbala_assessment` 仍未完成：Kala、Cheshta及相位分类裁定未齐，总量为null，不拼完整六力总分或达标排名。详见方向与相位力量审计（本地数据：`validation/jyotish-balas-audit.md`）。


## 计算范围与来源

| 层 | 实际实现 | 口径 |
| --- | --- | --- |
| 天文基础 | Swiss Ephemeris 原生恒星位置 | `SE_SIDM_LAHIRI`、`SEFLG_SIDEREAL`、地心视位置、日期黄道；默认民用出生钟时 |
| 九曜 | 日、月、水、金、火、木、土及 Rahu／Ketu | `node_mode=mean` 默认平交点，可选 `true`；Ketu 恒为 Rahu 加 180° |
| 星宿 | 27 Nakshatra、宿主、四分段 Pada | 每宿 13°20′，每足 3°20′；原始经度参与计算，不先舍入 |
| D1 | Rasi、上升、整宫、宫主落宫 | 采用七曜守护星，节点不另赋宫主 |
| D9 | Navamsa | 每座九分，起座按火白羊、土摩羯、风天秤、水巨蟹，再顺行 |
| D10 | Dasamsa | 每座十分；奇数星座从自身起，偶数星座从第九座起，再顺行 |
| D2／D3／D7／D12／D30 | Santhanam 第6章所列分盘 | D2固定传统日月Hora，D30不等长区段只给星座；盘内度数和读法见下方v4说明 |
| Sthana Bala | 五项位置分量、逐盘证据、总量及来源口径比较 | 七曜，60 Virupa为1 Rupa；选定七分盘读法，不等于完整Shadbala |
| 尊贵与状态 | 星座级标签；D1 的 moolatrikona 度数、Baladi、Uchcha Bala；黄纬、速度、太阳黄经间距 | 度数条件独立；Uchcha Bala 仅一个 0–60 Virupa 分量；按 Santhanam 注释给太阳角距条件；D9/D10 不套物理状态 |
| 星体关系 | D1 星体对所在星座主星的自然、临时与复合关系 | 采用《Brihat Jataka》1905 版 II.16–18；方向不强制互反，不当作人际信用 |
| 相位 | 整宫 graha drishti | 七曜第七宫；火星另第四／八，木星第五／九，土星第三／十；节点相位保留未覆盖 |
| 主题 | 自我呈现、事业、单人伴侣关系 | 输出宫主事实、所选规则作用、来源和条件式传统解释；D10／D9 与 D1 分层 |
| 分期 | Moon-nakshatra Vimshottari | 出生剩余主运、当前主运／次运、目标所在周期 9 主运和 81 次运 |

规则来源为 [P.V.R. Narasimha Rao《Vedic Astrology: An Integrated Approach》](https://www.vedicastrologer.org/articles/vedic_astro_textbook.pdf)，重点为第 2–4、6、10、16 章；天文接口来源为 [Swiss Ephemeris Programmer's Manual](https://www.astro.com/swisseph/swephprg.htm)。采用书中有限规则；有分歧的节点尊贵、节点相位和共主没有纳入本版本。`india.rulesets/rule_trace` 保留来源和规则 ID。

新增规则及来源版本、教材冲突、剩余能力见深度规则审计（本地数据：`validation/jyotish-depth-audit.md`）。仍未覆盖完整 Shadbala（已实现位置力五分量、方向力与自然力，相位力保留分类分支）、八分法占据读法的唯一裁定与未决削减分支及事件推断、其他作者燃烧规则与真实出没可见性、复杂 Yoga 成格验收、D1/D2/D3/D7/D9/D10/D12/D30 以外分盘、其他 Dasha、出生时校正。`astro_vedicprog` 是已有的恒星二次推运，与本页的 Vimshottari 分开。

## 接口与兼容

`astro_india_chart` 接受 `node_mode`、`divisions`、`birth_time_uncertainty_minutes`、`ephemeris_policy`、`saptavargaja_profile`、`cheshta_model`。`divisions` 默认为 `[9,10]`，可选不重复的 `2,3,7,9,10,12,30` 或 `[]`；D1 始终计算。`[]` 只控制导出的分盘，位置强度仍计算内部所需的七盘星座。`astro_chart` 的 `chart_variant=india_chart` 接受相同选项；其他盘型允许协议自动传入中性的默认值，拒绝非默认印占设置。

独立印占证据在 `india.profile/nakshatras/charts/topic_evidence/birth_time_sensitivity`。现有印度盘顶层通用西占字段保持兼容，属于独立历史参考，不能把其中西占尊贵、相位容许度或现代星座文案解释为印占规则。两种坐标算法可能因原生恒星实现与历史岁差平移存在微差，印占分盘与达沙始终使用 `india` 原生数据。

旧印度盘允许显式覆盖 `zodiacal`／`hsys`；当不再是 Lahiri 恒星黄道、整宫时，返回 `india.status=configuration_not_supported`，不计算印占核心。独立 Vimshottari 工具直接拒绝这种配置。Swiss Ephemeris 缺失或运行失败时明确报错，不以低精度轨道生成分盘或达沙。实际物理 SWIEPH／Moshier／JPL 模型记录在 `india.profile.ephemeris_model`、逐星 `ephemeris_by_body` 及执行回执。`ephemeris_policy=auto` 保持自动选择并回显降级；`require_data_files` 在任一物理天体（包括生时抽样）回退 Moshier 时拒绝计算。`ephemeris_quality` 只表示后端来源，不认证精度或现实预测有效。

`ephemeris_model_scope=physical_bodies` 的模型汇总只含七个物理天体及其实际赤道／所选几何运动帧；`nonphysical_factor_models` 另列 Rahu／Ketu。平交点采用 `swisseph_analytical_mean_node`，`native_node_return_flags` 保留原生回显位。依据 [Swiss 2.10.03 的解析实现](https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L1493)，请求的 SWIEPH／Moshier／JPL 位不证明平交点读取了相应物理矢量文件。`physical_backend_policy=strict_jpl` 是运行者显式 JPL 选择，黄经、赤道、Lahiri、J2000 几何运动帧及支撑太阳事件均遵守；文件缺失、损坏或超界会报来源错误，不能默退 Moshier。原生位置与可选运动几何共用受管理的配置会话，防止它们之间被其他线程切换数据目录；这不证明完整原子文件读取或现实预测有效。

严格JPL已补充J2000系数子集与完整DE441文件的正向实算、5点网格、调用者ΔT隔离、异常拒降级及三端核对，见严格DE441审计（本地数据：`validation/jyotish-strict-jpl-audit.md`）。`physical_ephemeris_source.time_scale_policy`保留TT接口／TDB原始文件范围及未应用转换的近似；兼容字段名中的TT不能当作已转换的TDB边界。有限样本通过不认证完整历法、Lahiri、原典或现实预测。

另有1900–2050的30个固定TT历元、150项五星J2000几何核对，原TT全部通过原0.02角秒线；补充量化TT／TDB近似在该组的影响，但移位参数不参与验收、不改变出生钟或运行时默认计算。它只验证可选几何帧的有限网格，不能外推到D1视速度或全时段观测精度。见跨年代几何与时标诊断（本地数据：`validation/jyotish-jpl-grid-audit.md`）。

显式太阳钟时与建盘需保持来源一致。此前跨配置复用对象的问题及修改前归档见钟时来源衔接调查（本地数据：`validation/jyotish-clock-source-investigation.md`）；v17候选的来源核验与完整验收见上方修复审计。

## 时间与不确定性

`astro_vimshottari` 使用出生地时区解释 `analysis_year/month/day/hour/minute`。显式年份未给月／日时各取 1；显式月份未给日时取 1；未给年份时从冻结调用时刻 `as_of` 取出生时区年份，完全未给日期时取该本地日期。未给钟时取 `00:00`。这是内部锚点，不等于全年时间线扫描。

| `year_basis` | 固定日数 | 默认 |
| --- | --- | --- |
| `sidereal_365_25636` | 365.25636 | 是 |
| `tropical_365_2425` | 365.2425 | 否 |
| `savana_360` | 360 | 否 |

年长是显式实现选择，原书也讨论不同口径。本实现按 UTC 日历标签与每天 86400 名义秒的 datetime/timedelta 口径计算（不表示跨闰秒的连续原子时历时，见 `elapsed_time_convention`），不采用公历周年、当地夏令时日历加法或随季节变化的实际回归年。宿序为 Ketu、Venus、Sun、Moon、Mars、Rahu、Jupiter、Saturn、Mercury，各年数为 7、20、6、10、7、18、16、19、17；出生已行比例由月亮在出生宿内的进度确定。次运必须从完整原始主运起算，不能重分出生剩余期。

边界采用 `[start,end)`，输出为带 UTC 偏移的 ISO 时间。时间线是**目标所在的 120 年规则周期**，首运可始于出生前；`timeline_scope.cycle_index=0` 表示以出生主运起点开始的周期。超过该周期的目标定位到后续相同规则周期。120 年不是寿命估计，计算出的微秒位不代表出生记录或现实事件有该精度。

`astro_vimshottari`可选`dasha_depth=2..6`，默认2层MD／AD；3至6层依次加入PD、SD、PAD、DAD。`vimshottari.subdivisions.current_levels`返回当前完整运主链，`siblings_by_level`列出每个当前父期的九个子期；原有`timeline`继续只含九个MD与81个AD。内核按完整父期递归，从完整MD起点保留有理数偏移，输出边界只舍入一次；不将出生剩余期重新分割。生时抽样以完整`period_lord_chain`分组，宫主上下文来自各自候选。读取视图`evidence_views.dasha_levels`前须显式选择大于2的深度。来源、实现约定与分阶段验收见递归分期核验（本地数据：`validation/jyotish-deep-dasha-audit.md`）；层级细分不代表现实事件精度。

拒绝不存在或有歧义的 DST 钟时；重复时刻可用明确 UTC 偏移消歧。经纬度或城市解析范围由现有出生工具处理。

民用钟时转换到 UTC 后，1972 年起使用随包冻结的 IERS TAI−UTC 表取得 TT，再由 Swiss Delta-T 模型估计 UT1。不能把 UTC 数字直接视作 UT1，也不让远期日期悄悄切换输入语义。`india.profile.time_scale_context` 回显来源指纹、表的到期日和 `future_leap_seconds_assumed_unchanged`；过期后沿用最后偏移是明确假设。1961–1971年改用[IERS历史UTC偏移／日漂移表](https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history)，1960年另用[IAU SOFA](https://www.iausofa.org/2023-10-11c)的标准关系；1960年前保留 UT1 输入假设并返回 `julian_day_utc=null`。1960年也回显UTC的实际来源，不认证出生钟或地方授时实现。可选的太阳钟时重定位会改变计算时刻，不能理解为同一物理时刻的另一种显示。

`birth_time_uncertainty_minutes` 仅填用户确认的正负范围，最大 120 分钟。未给范围标记 `not_assessed`，不默认精确；给定范围按 UTC 区间最多 30 秒网格比较上升和九曜在各分盘的星座／宫位，输出实际变体，并记录 D1 度数区间／Baladi／顺逆行变体及 Uchcha Bala、Sthana 五分量与总量的抽样范围。`no_change_on_sample_grid` 仅表示抽样未见变化，不保证区间内没有边界。达沙复用同一完整网格比较目标时刻的主运／次运，`stage_variants` 保留全部抽样组合及对应生时下的宫位、宫主和D1条件；不能把名义盘上下文套到其他候选。`sample_segments` 保留不连续出现的区段，`adjacent_stage_change_brackets` 只夹定相邻样本间的变化，不声称精确边界。`period_boundary_ranges` 和度数范围是样本最小最大值，不是置信区间；跨零度时数值范围可能很宽。`requested_sample_count/evaluated_sample_count/omitted_samples` 针对完整网格，目标早于候选出生的每个点均显式略过；另列去重后的实际时刻数量。旧 `samples` 保留端点与中心子集，其计数另列 `endpoint_subset_*`。顶层 `natal_ruler_context` 明确只对应名义生时。地点误差未纳入该敏感性分析。

`cheshta_model=simon1994_j2000` 的 `model_context` 回显出生TT、平均多项式来源、共同坐标框架、逐星几何后端和角度过程。适用窗口为 `[1900-01-01 TT,2051-01-01 TT)`；越界只保留该层缺失，其他本命证据可继续返回。生时抽样跨过窗口会记录模型状态变化；网格覆盖不是概率。`analysis_year` 不改变本命模型的适用窗口。严格星历模式也检查新增J2000几何位置的后端。TT代入TDB慢变平均参数是一项显式近似，并不把全部时间尺度视为相同。

## 可复制的虚构示例

以下人物均为虚构演示，不能替代用户资料。使用源码环境：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge astro_india_chart \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --node-mode mean --divisions 9 10 --birth-time-uncertainty-minutes 5 \
  --fields india.profile india.charts india.topic_evidence india.birth_time_sensitivity india.rulesets india.rule_trace \
  --strict-fields --no-include-snapshot-text

uv run --locked --extra dev fatebridge astro_vimshottari \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --analysis-year 2026 --analysis-month 10 --analysis-day 22 \
  --analysis-hour 12 --analysis-minute 0 --year-basis sidereal_365_25636 \
  --fields analysis_context vimshottari.current_major vimshottari.current_sub vimshottari.birth_balance vimshottari.natal_ruler_context india.profile india.rulesets india.rule_trace \
  --strict-fields --no-include-snapshot-text
```

显式选择现代五星平均模型的独立示例：

```bash
uv run --locked --extra dev fatebridge astro_india_chart \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --cheshta-model simon1994_j2000 \
  --fields india.profile india.strengths.cheshta_bala \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

REST 的 `fields/strict_fields/include_snapshot_text` 是查询参数；出生与计算选项放请求体：

```bash
curl -sS -X POST 'http://127.0.0.1:8010/api/astro/vimshottari?fields=analysis_context&fields=vimshottari.current_major&fields=vimshottari.current_sub&strict_fields=true&include_snapshot_text=false' \
  -H 'Content-Type: application/json' \
  -d '{"name":"演示甲","birth_year":1990,"birth_month":4,"birth_day":6,"birth_hour":9,"birth_minute":33,"birth_place":"上海","analysis_year":2026,"analysis_month":10,"analysis_day":22,"analysis_hour":12,"analysis_minute":0,"year_basis":"sidereal_365_25636"}'
```

MCP 使用同名工具及相同业务参数。首次按工具公开的 `natal/career/relationship/divisions/strength` 或 `stage/timeline` 卡选择字段；卡名不是请求参数。完整 JSON／全部时间线请求从 `fields=null` 开始并保留默认响应预算，按 [同次结果交付](agent-guide.md#完整结果交付与同次导出)读取同 run 的文件／字段／分页和 SHA-256。摘要投影排除的字段不在该导出中。

## 数值与软件验证

`tests/test_jyotish.py` 使用原书第 6 章算例 16／17 核对 D9／D10，第 16 章算例 50 核对给定月亮位置的剩余运；给定经度算例与真实天文重新排盘分开。还验证全部主／次运边界、周期切换、节点、相位、DST 和生时敏感性。

`tests/fixtures/jyotish-reference.json` 来自隔离安装的 **PyJHora 4.8.7**，包含软件版本、源文件哈希及配置；6 组虚构资料覆盖三种年长、平／真交点、D1／D9／D10 和各 81 个次运起点。双方均使用 Swiss Ephemeris 天文库，所以这是独立规则实现对照，不是独立天文模型证明。PyJHora 的本地 JD 输入显式采用 UT1 加时区；分期比较相对出生锚点的历时，不将其 UT1 日期直接解释为 UTC。不同的 JD 浮点路径可相差约 40 微秒，并被分盘或多年运期放大；测试上升／分盘按分度放宽数值容差，达沙起点允许 1 秒差。

另用 [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html) 的地心视黄经冻结数据独立对照七个物理天体、三个 UTC 时刻；不使用 FateBridge 或 Swiss 产生参考答案。精确有理数测试覆盖星宿、足、D1／D9／D10 分界及主次运公式，独立几何公式另核对上升。验收范围、发现的缺陷和原书例 50 的日期分歧见独立算法审计（本地数据：`validation/jyotish-independent-audit.md`）。

未削减八分法已接入源码候选的`india.ashtakavarga`，按具名Rao2000规则为每张返回分盘提供PAV（逐贡献者二元表）、BAV（八个贡献者计数）及SAV（七曜BAV合计）。1按该作者称rekha，SAV不合计上升目标表，上升仍作为贡献者。分盘沿用各自声明的构造方法及来源，不能写成整部Rao原书已验收。生时变体位于`india.birth_time_sensitivity.ashtakavarga_variants`，按每个样本自己的星座保留完整计数；样本数不是概率。

一手参考准备（本地数据：`validation/jyotish-ashtakavarga-reference-audit.md`）在实现前已冻结768个规则单元和89组软件数值；未削减计数的验收见接入审计（本地数据：`validation/jyotish-ashtakavarga-implementation-audit.md`）。读取任务视图`evidence_views.ashtakavarga`提供的fields即可；视图名不是输入参数。

v21另在每张表的`reduction_analysis`提供三合／同主削减与Pinda，明确选择七曜作为占据者，上升仍是原始BAV贡献者。原始PAV／BAV／SAV保持未削减；单占据且两座非零相等的原文缺项保留`null`，不当作零。生时变体按各自输入重算。可用`evidence_views.ashtakavarga_reductions`所列fields读取，来源、逐步算式、637个目标参考及软件反例见具名削减接入审计（本地数据：`validation/jyotish-pinda-implementation-audit.md`）。该选择未证明整部原典的唯一读法，Pinda也不作为成功概率或事件择时结论。

v25新增`ashtakavarga_source_profiles`字段视图，分别读取Rao主表和Aiyar自己的完整原始表与削减链；视图名不是输入参数。`source_profile_comparison.aiyar1905`位于每张表上，旧的`reduction_analysis.source_profile_comparison.aiyar1905_commentary`位于Rao削减分析内，两者输入来源不同，不能互相替代。新分支不补造上升目标BAV或Pinda乘数。

v24的Aiyar比较使用每张名义分盘和每个生时变体自己的同一原始BAV及七曜占据集合，只改变削减读法，不认证原始BAV或分盘构造也符合Aiyar。上层Rao的`partial_source_rule`不否定比较口径已算出的数值；比较口径完整也不填补Rao的缺项。`reduced_sum`是整数计数之和，不是Pinda、物理力量或成功概率。现有`ashtakavarga_reductions`字段视图包含新比较；请求参数没有新增。

原书补充检查（本地数据：`validation/jyotish-pinda-reference-audit.md`）另复核例39与例108的给定输入和计数，并保留削减规则的未决读法及独立软件差异。这些公开算例提供算术与来源一致性的证据，不证明现实预测有效。

可在单独环境重建数值 fixture，生产依赖无需 PyJHora：

```bash
uv venv --python 3.12 /tmp/fatebridge-jyotish-oracle
uv pip install --python /tmp/fatebridge-jyotish-oracle/bin/python --no-deps PyJHora==4.8.7 pyswisseph==2.10.3.2 numpy pandas
uv pip install --python /tmp/fatebridge-jyotish-oracle/bin/python geocoder geopy python-dateutil timezonefinder scipy pytz requests
/tmp/fatebridge-jyotish-oracle/bin/python scripts/gen_jyotish_reference.py
uv run --locked --extra dev pytest -q tests/test_jyotish.py tests/test_jyotish_reference.py tests/test_jyotish_transports.py
```

NASA 数据重取及独立检查（普通测试使用冻结数据，无需联网）：

```bash
uv run --locked --extra dev python scripts/gen_jyotish_horizons_reference.py
uv run --locked --extra dev pytest -q tests/test_jyotish_independent_audit.py
```

`tests/test_jyotish_transports.py` 通过真实 REST、原生 MCP 协议及 CLI 验证配置和输出。上述验证证明所声明口径下的工程一致性，不认证传统解释或现实预测。

## 现实预测研究

没有独立现实数据时保留 `not_tested`。已实现预注册、完整队列封存与延后揭盲流程（本地数据：`validation/jyotish-prospective-study.md`），含材料指纹、训练／盲测隔离、基线与覆盖率检查。流程合成测试和规则算例均不计作预测成绩。

## v3 时间与原典增量

度数规则、Uchcha Bala 和 Baladi 已对照 R. Santhanam 卷一的固定扫描本，太阳角距条件明确来自译者第 7 章注释表。顺逆阈值、源文与注释层、端点及 OCR 算例差异见时间尺度与原典复核（本地数据：`validation/jyotish-times-classics-audit.md`）。仅确认这些具体条文及注释，未声明整部原典已验收。

## v4 分盘与位置强度

新增 D2（传统日月 Hora）、D3、D7、D12、D30，采用上述 Santhanam 扫描本第 6 章。D30 是五个不等长区段的星座分配，原表没有唯一的盘内度数，故其 `longitude/degree_in_sign=null`；其他等分盘的盘内度数是声明的线性显示约定，不是天文黄经。D30 的符号与宫位不用于补写原典未审的事件解释。

`india.strengths.sthana_bala` 返回七个物理天体的 Uchcha、Saptavargaja、Ojayugma、Kendradi、Drekkana 五分量及总量。单位为 Virupa，60 Virupa 为 1 Rupa；没有人为归一化的满分。节点及上升不填虚构的零分，完整 Shadbala 仍标记 `not_complete`。逐盘关系取 D1 本命位置，不能在各分盘重新计算临时友敌。

`saptavargaja_profile` 仅选择七分盘分量的读法：

| 参数 | 系数：moola／own／great friend／friend／neutral／enemy／great enemy | moola 作用域 |
| --- | --- | --- |
| `santhanam_27`（默认） | 45／30／20／15／10／4／2 | 第 27.2–4 节“其他六盘同值”的逐字星座读法；不是唯一作者意图的裁定 |
| `raman_30` | 45／30／22.5／15／7.5／3.75／1.875 | [B.V. Raman 固定扫描本](https://astrojyotish.info/pdf/graha-bhava-balas.pdf)第30节明确仅D1，PDF27–28页图已核对；具体重印版未核定 |

两者都明确采用星座分配，和 D1 独立的 moolatrikona 度数状态分开。`profile_comparison` 保存两种七分盘分量及其对总量的影响；它不是误差区间或成功概率。其余三分量采用Santhanam27.1、27.4–5的公式，Raman20、31–35也有相同算术。Drekkana独立选择：默认 `santhanam_27_6` 的第二段为月／金、第三段为水／土；`raman_36` 将这两组对调。两者均采用物理D1每星座内的[0,10)、[10,20)、[20,30)区间及15 Virupa，不能改用分盘D3经度。单选 `raman_30` 仍只改变七分盘计分。`drekkana_profile_comparison` 固定当前七分盘读法再比较Drekkana，原有 `profile_comparison` 则固定当前Drekkana比较七分盘读法；不能混取两组最高分。Kendradi 按 Rasi 整宫组，和另选 Bhava 中点算法分开。

原书页图、手算、独立 PyJHora 的对齐项和保留差异见位置强度审计（本地数据：`validation/jyotish-sthana-audit.md`）。重建参考数据与测试：

```bash
/tmp/fatebridge-jyotish-oracle/bin/python scripts/gen_jyotish_sthana_reference.py
uv run --locked --extra dev pytest -q tests/test_jyotish_sthana.py tests/test_jyotish_transports.py
```

查看完整位置分量的虚构示例：

```bash
uv run --locked --extra dev fatebridge astro_india_chart \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --divisions 2 3 7 9 10 12 30 --saptavargaja-profile santhanam_27 \
  --fields india.profile india.charts india.strengths.sthana_bala india.rulesets india.rule_trace \
  --strict-fields --no-include-snapshot-text
```

## 民用时刻与太阳钟标签

v11修复旧版显式`use_true_solar_time=true`将太阳钟重新当民用钟、从而移动星历时刻的问题。印占本命和Vimshottari现在始终使用记录的民用出生时刻，经时区解析后进入共享UTC／TT／模型UT1转换；开关仅增加太阳钟显示。默认false的盘面、力量和运期数值不变。

`india.profile.clock_context`列出记录时刻、计算UTC、显示开关、无时区的`solar_wall_datetime`、修正分钟及来源。太阳钟标签可能跨日／跨年，甚至与某个IANA夏令时缺失钟时的数字相同；它不是该时区的另一个时间戳，不改变出生日期、达沙起点、分析日期锚点或平均模型窗口。当前显示按上文v19使用同一TT、模型UT1与视太阳时角，不把UTC直接当作实测UT1，也不认证记录精度或实测地球自转。

已知历史LAT／LMT记录需要按其真实钟制转换，不能先当民用资料再打开此开关；v11尚未提供此输入；v12通过明确的birth_clock_basis接受LMT/LAT。直接领域调用也拒绝已经太阳时重定位而与记录时刻不一致的旧`AstroBirthInfo`。详见物理时刻修复验收（本地数据：`validation/jyotish-civil-instant-audit.md`）。

## 已知历史太阳钟输入（v12）

`birth_clock_basis`可明确指定`local_mean_solar`（LMT）或`local_apparent_solar`（LAT），默认仍为`civil`。太阳钟记录省略`birth_timezone`，并保持`use_true_solar_time=false`，避免重复换算。日期统一为已正确换成的公历；未知原始历法、钟制或年代不凭星位／事件拟合补出。原记录中的秒可用`birth_second`，数值换算余数可用`birth_microsecond`，省略是分钟起点而非精确记录声明。

LMT以东经正向加在UT1上；LAT再涉及视太阳均时差。换算沿用共享TT／UT1及历史UTC规则，原钟面无时区，输出的UTC载体在1960年前仍是历史UT1约定。`person_info.clock_conversion`与`india.profile.clock_context`同时保留原标签、钟制、经度、转换时刻、数值往返残差和实际太阳后端；数值残差不认证原记录准确。严格星历政策也检查LAT逆算的每次太阳坐标和误差区间端点。

太阳钟的误差范围按原钟面加减分钟后先换算端点，再建立最长30秒的物理UTC网格，不强行当成对称UTC分钟，也不把点数截成481。达沙的`analysis_timezone`可另选目标民用时区；省略时民用出生沿用其时区，太阳钟出生明确默认UTC。该参数不改变出生换算，不把目标钟时重新当LMT/LAT。

```bash
uv run --locked --extra dev fatebridge astro_vimshottari \
  --birth-year 1879 --birth-month 5 --birth-day 14 --birth-hour 23 \
  --birth-longitude 10 --birth-latitude 53.55 \
  --birth-clock-basis local_mean_solar --analysis-year 2026 \
  --analysis-timezone Asia/Shanghai \
  --fields india.profile.clock_context analysis_context vimshottari.current_major \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

这是虚构技术验算，不是历史人物预测。范围与独立对照见太阳钟输入验收（本地数据：`validation/jyotish-solar-input-audit.md`）。
