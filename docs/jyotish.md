# 印度占星：本命、分盘、力量与Vimshottari

阅读导航：[输入与来源](#坐标速度与来源限制) · [力量与未决项](#力量口径与未裁定分支) · [计算范围](#计算范围与来源) · [接口](#接口与独立视图) · [示例](#可复制的虚构示例) · [验证](#数值与软件验证)

当前提供`parashari_lahiri_core_v29`有限Parashari实现。`astro_india_chart`（REST `/api/astro/india`）计算本命与分盘，`astro_vimshottari`（REST `/api/astro/vimshottari`）计算月宿主运／次运。CLI、REST和MCP共用领域服务；源码可用范围、已发布包及部署验收分别报告。

民用出生时刻须明确合法`birth_timezone`或可支持且不歧义的`birth_place`。未知时区在计算前拒绝，坐标与太阳钟显示不能代替出生钟制。已知历史LMT／LAT另由明确的`birth_clock_basis`输入；历史时标约定不认证真实地方钟。

## 坐标、速度与来源限制

D1的`physical_state.longitude_speed_degrees_per_day`使用逐体声明的视位置导数，并据同一值判断顺逆／驻留和Santhanam太阳角距分支。原生速度保留在`longitude_speed_native_degrees_per_day`。`longitude_motion_context.rate_basis`分别标明完整视位置导数、月球光行时链／空间光行差／观测者项的部分修正，以及仍采用的原生近似；Rahu／Ketu使用声明的交点理论。这不替换古典平均运动或Cheshta Bala。

连续Lahiri辅助状态按`R x`与`R (gamma v) + R' x`同时传播位置和速度。`continuous_frame_state/source_derivative_state`仍为`partial`：原生J2000输入近似、完整移动框架、物理TT时差映射及完整原生二进制身份尚未统一验收，辅助状态不替换D1主因子。内部高精度公式符合不能代替物理参考资格。

原96例位置／速度框架比较的64／96结果仍有限；112条补充七曜参考中两条远期月亮速度未收敛。Horizons打印角速度与方向差分存在冲突，时间标签与舍入控制没有单独消除该冲突；密集TT查询的返回时刻不符也不能被默认为通过。共有112例、两种时间口径、五阶段的1,120组原型结果只支持其具名研究范围。

独立DE441几何解码参考共有364,687条官方样本：360,001条满足原准则、4,686条缺少来源，总门槛未通过。它提供TDB几何参考，不认证TT视位置、原典或预测。不同时间模型／CSPICE一致也不自动授予新的物理参考资格。

受管理求导须复现传入中心、绑定同一文件上下文和实际依赖TT，按既定文件窗口选取预定差分方向；来源错误拒绝，不删样本或换日期。当前私有原生进程覆盖出生钟解析、Lahiri／赤道／几何状态、宫位、太阳事件、生时范围和达沙，保留显式数据路径、JPL选择与执行钟，避免调用者陈旧Delta-T状态进入计算。辅助表或文件途中变化会报类型化来源错误，首末指纹相同不证明完整原子读取。

`india.profile.earth_rotation`回显实际TT／UT1和自转来源。`local_apparent_sidereal_meridian_degrees`是当地视恒星子午圈赤经，不能当黄道MC。C04在表外不外推或静默回退；历史模型UT1不是实测地球定向。

地方平均日期以给定UT1和经度的精确二进制值分类，角距与对点也先按未舍入值运算，再显示Virupa。它们解决给定数值的边界算术，不提高出生记录或星历物理精度。

## 力量口径与未裁定分支

公开作者profile各自保留，不混取较高分。完整Shadbala仍未完成。默认`cheshta_model=unadjudicated`保留五星运动力缺项；可选`simon1994_j2000`仅在1900–2050出生TT范围内使用Simon完整长期平均黄经多项式及另算几何真位置，同属J2000平均动力黄道／春分点。它不是D1的Lahiri视位置，也不认证Raman1900历元表。

Raman运动表的54项关系矛盾、不同扫描见证的19个清晰单元差异及较早见证34条冲突均不以混接输入消除。Drekkana详细条文15 Virupa与摘要60的冲突另列`source_reading_conflicts`，不凭参考软件选常数。

运动力对径角保留两个中点，仅在两条精确有理数强度相同时给共同值；显示成相同float不足以成立共识。太阳使用本次Ayana、月亮使用本次性质分支Paksha，不因选择五星模型获得Simon来源标签。逐宫主证据绑定自己的操作数、实际字段、条件和不可计算原因，不由全局设置推断已算。

## 名义盘、条件证据与解读范围

Ketu由同次Rahu精确加180°得到。分盘、星宿与宿足使用这项未舍入派生关系，名义盘和时间误差采样采用同一口径；返回的经度仍为浮点数。独立传入的手工原盘继续尊重其显式Ketu值，不据Rahu重建。边界与三端回归见[对点分区测试](../tests/western/test_western_antipodes.py)，不构成独立天文精度认证。

`india.reading_basis`明确按所填出生时刻的名义值计算。没有给出生时误差时，`options_basis=nominal_only`且敏感性仍为`not_assessed`，不能当作已证实精确；给定误差后，星宿、宿主及宿足与分盘使用同一最多30秒UTC网格。`nakshatra_alternatives`列出发生变化的星体／上升及覆盖数，覆盖数不是概率；没有列出变化也不证明连续区间内没有边界。原生解读会把名义月宿与抽样候选一并陈述，达沙摘要也明确使用名义生时。

每项主题力量的`calculation_context`携带该宫主自己的条件数值、实际同run字段路径、模型／性质约束和局部不可用依据。`computed_consensus`是已算分支一致，`conditional_results`是分支都已计算但结果不同，`unavailable`是当前无可用数值，`partially_computed`是部分分支有值；共识不等于原典裁定。不能把null统一写成零、漏算或用户资料不足，也不能由某个星体的全局缺项否定另一个宫主的已算结果。

Vimshottari生时端点／中心样本若晚于目标，返回`omitted_samples`和实际覆盖数，不能悄悄略过后声称全范围完成。这里核验的是计算和原生文案的证据传递；任意模型自由文本仍须独立审阅。6个语义准备案例属于已知开发回归集，不计作独立留出样本或现实预测。详见解读证据审计。

## 条件式星战金额

`kala_bala.components.yuddha_bala`按已核验页图的Raman76–77计算：遍历五星全部10对，以最短黄经差严格小于1度检索候选；两星独立交战时，取Sthana、Dig及Natha至Hora的同分支合计差，除以原书固定Bimba系数差，按较小黄经者加、另一星减。该前置合计不含Ayana、Cheshta、Drik、Naisargika或星战自身。固定盘面系数不是当前测得的角直径，不按天文距离动态替换，也不自行截断到60。

计算保留每一分支的输入、前置合计、分母、金额及来源。水星／月亮性质未裁定时保持相关分支；最终Kala按同一分支相加，不能先拿不唯一的分量摘要相加。同经或跨黄经零点的独立星战虽未裁定胜者，前置输入齐全时仍能算出无符号金额，但两星获配的正负值继续缺失；连成三颗以上的同时交战或缺少前置输入时，金额也保持缺失。独立的另一对可计算。生时网格记录候选／判定变化及每个分支范围，范围与覆盖数均不是概率。

这是Raman星战公式对本次已声明力量输入的应用：上游仍各有Santhanam／所选七分盘读法，不认证完整单一Raman六力。Santhanam27.20给出另一公式，不混作同一规则。详见星战规则与独立对照审计。

## 时间分量与月亮分类修正

`kala_bala`计算视太阳昼夜、月相、昼夜三分、岁／月／日／时主和Ayana；第九项星战在v8按上文条件计算；无候选给0，不能计算的参与者保留缺失。Hora为日出后的等长平均小时，和西占昼夜不等时小时分开；岁／月主为原书360／30日传统口径。`cheshta_bala`太阳取本次Ayana、月亮取本次Paksha；其他五星默认保留null，v7可显式选择上文的现代平均模型。它们都是出生时刻的本命分量，不是分析年份的时运。

此前v5只按盈亏处理月亮性质；原书还列有第八日窗口的另一表述。v6保留这项作者内分歧及边界日段，不能挑较高分或把条件分支当概率。新增赤道坐标与日出事件均有后端记录，严格星历模式覆盖两者；无极地日出不造默认时间。新JPL请求超时后，用原有21个JPL黄道位置及独立ERFA转换复核赤道帧，没有冒充新增数据。

细节、失败和复现方法见时间分量审计。完整六力总量仍为null，未给出强弱达标排名。

## 新增力量计算

`india.strengths` 新增 `dig_bala`、`naisargika_bala`、`drik_bala` 及 `shadbala_assessment`，每层保留自身来源、算法和范围。

- 方向力依据 Santhanam 27.7，使用实际恒星上升／天顶及其对点的黄经，从无力点取最短弧除以3。整宫起点不能代替角点；UT1仍是已声明的模型估计。
- 自然力依据 Santhanam 27.14，土、火、水、木、金、月、日依次为 `60/7` 的1至7倍。它是固定传统系数，不是亮度实测，也不区别个人现实能力。
- 相位力采用 Raman 113–120：从施相星到受相星的有方向黄经差，普通分段值加特殊相位附加值，再按施相星的传统正负分类取四分之一。它不同于已有的整宫相位，不能转成无方向最小夹角。按附加规则，土星某些角距值可超过60，没有擅自截断。

Santhanam 第26章偈颂专式与注释附加法存在差异，第27.19又提到水星／木星完整相位量；本层选择有明确分段与例表的 Raman 条文，并登记选择与差异，不能宣称整套六力均按同一作者无争议实现。已核对固定Raman扫描本PDF43、87–93页图，具体重印版仍未核定。端点统一用右侧半开区间，是声明的实现约定，不冒充作者已裁定的端点。

原书例53–55的角距及合计存在内部矛盾，现由`drik_bala.source_witness`与`source_reading_conflicts`保留。标准算例将水星判为负性质的脚注没有给出可推广的数值关联阈值，因此任意盘仍保留条件分支。公式数值未改，不能用有矛盾的例表反调公式或认证完整单一原典六力。详见页图与算例审计。

Santhanam第26章与27.19现另有未施用来源字段，记录译文／注解读法、火星249度与Raman240度差异，以及540行普通表中的两处坐标关系冲突。初次转录漏读续表的更正过程、精确有理数审计及未通过的来源门槛见Santhanam相位校勘。新增字段不改变当前Raman数值；各读法不能拼接取高分。较早Raman见证现另有完整给定输入核验，区分原印数字冲突、公式计算和算例性质，不将不同版本的黄经或水星符号拼接。正式主题解释还会按本次D1核对完整相位力计算链，拒绝与矩阵、性质、贡献或来源声明不一致的包；这类内部错误不会要求用户改动出生资料。见计算链核验。

水星“好／坏关联”的精确判据尚未裁定，不用同星座或燃烧阈值擅自补成定论。`drik_bala.scenarios` 分别保存水星为传统 benefic／malefic 的结果及逐星贡献；v6同时保留月亮盈亏与原书第53节第八日窗口的不同读法，有分歧或边界不明时保留分类分支。`summary` 仅在所有分支值相同时给数值，否则为 `null`；null不表示零或没有相位，分支也不是成功概率上下界。正负号仅表示所选传统规则，不能直接翻译成现实事件吉凶。

生时误差沿同一UTC网格给方向力连续范围及相位各分类分支的范围与样本覆盖数，覆盖数不是概率。`shadbala_assessment` 仍未完成：Kala、Cheshta及相位分类裁定未齐，总量为null，不拼完整六力总分或达标排名。详见方向与相位力量审计。


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

新增规则及来源版本、教材冲突、剩余能力见深度规则审计。仍未覆盖完整 Shadbala（已实现位置力五分量、方向力与自然力，相位力保留分类分支）、八分法占据读法的唯一裁定与未决削减分支及事件推断、其他作者燃烧规则与真实出没可见性、复杂 Yoga 成格验收、D1/D2/D3/D7/D9/D10/D12/D30 以外分盘、其他 Dasha、出生时校正。`astro_vedicprog` 是已有的恒星二次推运，与本页的 Vimshottari 分开。

## 接口与独立视图

`astro_india_chart` 接受 `node_mode`、`divisions`、`birth_time_uncertainty_minutes`、`ephemeris_policy`、`saptavargaja_profile`、`cheshta_model`。`divisions` 默认为 `[9,10]`，可选不重复的 `2,3,7,9,10,12,30` 或 `[]`；D1 始终计算。`[]` 只控制导出的分盘，位置强度仍计算内部所需的七盘星座。`astro_chart` 的 `chart_variant=india_chart` 接受相同选项；其他盘型允许协议自动传入中性的默认值，拒绝非默认印占设置。

独立印占证据在 `india.profile/nakshatras/charts/topic_evidence/birth_time_sensitivity`。印度盘顶层通用西占字段是另一个公开参考视图，不能把其中西占尊贵、相位容许度或现代星座文案解释为印占规则。两种坐标算法可能因原生恒星实现与历史岁差平移存在微差，印占分盘与达沙始终使用 `india` 原生数据。

通用印度盘入口允许显式覆盖 `zodiacal`／`hsys`；当不再是 Lahiri 恒星黄道、整宫时，返回 `india.status=configuration_not_supported`，不计算印占核心。独立 Vimshottari 工具直接拒绝这种配置。Swiss Ephemeris 缺失或运行失败时明确报错，不以低精度轨道生成分盘或达沙。实际物理 SWIEPH／Moshier／JPL 模型记录在 `india.profile.ephemeris_model`、逐星 `ephemeris_by_body` 及执行回执。`ephemeris_policy=auto` 保持自动选择并回显降级；`require_data_files` 在任一物理天体（包括生时抽样）回退 Moshier 时拒绝计算。`ephemeris_quality` 只表示后端来源，不认证精度或现实预测有效。

`ephemeris_model_scope=physical_bodies` 的模型汇总只含七个物理天体及其实际赤道／所选几何运动帧；`nonphysical_factor_models` 另列 Rahu／Ketu。平交点采用 `swisseph_analytical_mean_node`，`native_node_return_flags` 保留原生回显位。依据 [Swiss 2.10.03 的解析实现](https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L1493)，请求的 SWIEPH／Moshier／JPL 位不证明平交点读取了相应物理矢量文件。`physical_backend_policy=strict_jpl` 是运行者显式 JPL 选择，黄经、赤道、Lahiri、J2000 几何运动帧及支撑太阳事件均遵守；文件缺失、损坏或超界会报来源错误，不能默退 Moshier。原生位置与可选运动几何共用受管理的配置会话，防止它们之间被其他线程切换数据目录；这不证明完整原子文件读取或现实预测有效。

严格JPL已补充J2000系数子集与完整DE441文件的正向实算、5点网格、调用者ΔT隔离、异常拒降级及三端核对，见严格DE441审计。`physical_ephemeris_source.time_scale_policy`保留TT接口／TDB原始文件范围及未应用转换的近似；JPL原始头只返回TDB范围字段及`range_time_scale=TDB`，不再提供伪TT别名；这项标签修正没有实现TT／TDB物理转换。有限样本通过不认证完整历法、Lahiri、原典或现实预测。

另有1900–2050的30个固定TT历元、150项五星J2000几何核对，原TT全部通过原0.02角秒线；补充量化TT／TDB近似在该组的影响，但移位参数不参与验收、不改变出生钟或运行时默认计算。它只验证可选几何帧的有限网格，不能外推到D1视速度或全时段观测精度。见跨年代几何与时标诊断。

显式太阳钟时与建盘需保持来源一致。此前跨配置复用对象的问题及修改前归档见钟时来源衔接调查；v17候选的来源核验与完整验收见上方修复审计。

## 时间与不确定性

`astro_vimshottari` 使用出生地时区解释 `analysis_year/month/day/hour/minute`。显式年份未给月／日时各取 1；显式月份未给日时取 1；未给年份时从冻结调用时刻 `as_of` 取出生时区年份，完全未给日期时取该本地日期。未给钟时取 `00:00`。这是内部锚点，不等于全年时间线扫描。

| `year_basis` | 固定日数 | 默认 |
| --- | --- | --- |
| `sidereal_365_25636` | 365.25636 | 是 |
| `tropical_365_2425` | 365.2425 | 否 |
| `savana_360` | 360 | 否 |

年长是显式实现选择，原书也讨论不同口径。本实现按 UTC 日历标签与每天 86400 名义秒的 datetime/timedelta 口径计算（不表示跨闰秒的连续原子时历时，见 `elapsed_time_convention`），不采用公历周年、当地夏令时日历加法或随季节变化的实际回归年。宿序为 Ketu、Venus、Sun、Moon、Mars、Rahu、Jupiter、Saturn、Mercury，各年数为 7、20、6、10、7、18、16、19、17；出生已行比例由月亮在出生宿内的进度确定。次运必须从完整原始主运起算，不能重分出生剩余期。

边界采用 `[start,end)`，输出为带 UTC 偏移的 ISO 时间。时间线是**目标所在的 120 年规则周期**，首运可始于出生前；`timeline_scope.cycle_index=0` 表示以出生主运起点开始的周期。超过该周期的目标定位到后续相同规则周期。120 年不是寿命估计，计算出的微秒位不代表出生记录或现实事件有该精度。

`astro_vimshottari`可选`dasha_depth=2..6`，默认2层MD／AD；3至6层依次加入PD、SD、PAD、DAD。`vimshottari.subdivisions.current_levels`返回当前完整运主链，`siblings_by_level`列出每个当前父期的九个子期；原有`timeline`继续只含九个MD与81个AD。内核按完整父期递归，从完整MD起点保留有理数偏移，输出边界只舍入一次；不将出生剩余期重新分割。生时抽样以完整`period_lord_chain`分组，宫主上下文来自各自候选。读取视图`evidence_views.dasha_levels`前须显式选择大于2的深度。来源、实现约定与分阶段验收见递归分期核验；层级细分不代表现实事件精度。

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

`tests/jyotish/test_jyotish.py` 使用原书第 6 章算例 16／17 核对 D9／D10，第 16 章算例 50 核对给定月亮位置的剩余运；给定经度算例与真实天文重新排盘分开。还验证全部主／次运边界、周期切换、节点、相位、DST 和生时敏感性。

`tests/fixtures/jyotish-reference.json` 来自隔离安装的 **PyJHora 4.8.7**，包含软件版本、源文件哈希及配置；6 组虚构资料覆盖三种年长、平／真交点、D1／D9／D10 和各 81 个次运起点。双方均使用 Swiss Ephemeris 天文库，所以这是独立规则实现对照，不是独立天文模型证明。PyJHora 的本地 JD 输入显式采用 UT1 加时区；分期比较相对出生锚点的历时，不将其 UT1 日期直接解释为 UTC。不同的 JD 浮点路径可相差约 40 微秒，并被分盘或多年运期放大；测试上升／分盘按分度放宽数值容差，达沙起点允许 1 秒差。

另用 [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html) 的地心视黄经冻结数据独立对照七个物理天体、三个 UTC 时刻；不使用 FateBridge 或 Swiss 产生参考答案。精确有理数测试覆盖星宿、足、D1／D9／D10 分界及主次运公式，独立几何公式另核对上升。验收范围、发现的缺陷和原书例 50 的日期分歧见独立算法审计。

`india.ashtakavarga`按具名Rao2000规则为每张返回分盘提供PAV（逐贡献者二元表）、BAV（八个贡献者计数）及SAV（七曜BAV合计）。1按该作者称rekha，SAV不合计上升目标表，上升仍作为贡献者。分盘沿用各自声明的构造方法及来源，不能写成整部Rao原书已验收。生时变体位于`india.birth_time_sensitivity.ashtakavarga_variants`，按每个样本自己的星座保留完整计数；样本数不是概率。另保留[Rao原书的D10与BAV／SAV转录](../tests/data/astro/source_materials/jyotish-ashtakavarga-primary-supplement.json)作为来源资料；保留资料本身不增加已完成的验证样本数。

一手参考准备在实现前已冻结768个规则单元和89组软件数值；未削减计数的验收见接入审计。读取任务视图`evidence_views.ashtakavarga`提供的fields即可；视图名不是输入参数。

v21另在每张表的`reduction_analysis`提供三合／同主削减与Pinda，明确选择七曜作为占据者，上升仍是原始BAV贡献者。原始PAV／BAV／SAV保持未削减；单占据且两座非零相等的原文缺项保留`null`，不当作零。生时变体按各自输入重算。可用`evidence_views.ashtakavarga_reductions`所列fields读取，来源、逐步算式、637个目标参考及软件反例见具名削减接入审计。该选择未证明整部原典的唯一读法，Pinda也不作为成功概率或事件择时结论。

v25新增`ashtakavarga_source_profiles`字段视图，分别读取Rao主表和Aiyar自己的完整原始表与削减链；视图名不是输入参数。`source_profile_comparison.aiyar1905`位于每张表上，旧的`reduction_analysis.source_profile_comparison.aiyar1905_commentary`位于Rao削减分析内，两者输入来源不同，不能互相替代。新分支不补造上升目标BAV或Pinda乘数。

v24的Aiyar比较使用每张名义分盘和每个生时变体自己的同一原始BAV及七曜占据集合，只改变削减读法，不认证原始BAV或分盘构造也符合Aiyar。上层Rao的`partial_source_rule`不否定比较口径已算出的数值；比较口径完整也不填补Rao的缺项。`reduced_sum`是整数计数之和，不是Pinda、物理力量或成功概率。现有`ashtakavarga_reductions`字段视图包含新比较；请求参数没有新增。

原书补充检查另复核例39与例108的给定输入和计数，并保留削减规则的未决读法及独立软件差异。这些公开算例提供算术与来源一致性的证据，不证明现实预测有效。

可在单独环境重建数值 fixture，生产依赖无需 PyJHora：

```bash
uv venv --python 3.12 /tmp/fatebridge-jyotish-oracle
uv pip install --python /tmp/fatebridge-jyotish-oracle/bin/python --no-deps PyJHora==4.8.7 pyswisseph==2.10.3.2 numpy pandas
uv pip install --python /tmp/fatebridge-jyotish-oracle/bin/python geocoder geopy python-dateutil timezonefinder scipy pytz requests
/tmp/fatebridge-jyotish-oracle/bin/python -m scripts.jyotish.gen_jyotish_reference
uv run --locked --extra dev pytest -q tests/jyotish/test_jyotish.py tests/jyotish/test_jyotish_reference.py tests/jyotish/test_jyotish_transports.py
```

NASA 数据重取及独立检查（普通测试使用冻结数据，无需联网）：

```bash
uv run --locked --extra dev python -m scripts.jyotish.gen_jyotish_horizons_reference
uv run --locked --extra dev pytest -q tests/jyotish/test_jyotish_independent_audit.py
```

`tests/jyotish/test_jyotish_transports.py` 通过真实 REST、原生 MCP 协议及 CLI 验证配置和输出。上述验证证明所声明口径下的工程一致性，不认证传统解释或现实预测。

## 现实预测研究

没有独立现实数据时保留 `not_tested`。已实现预注册、完整队列封存与延后揭盲流程，含材料指纹、训练／盲测隔离、基线与覆盖率检查。流程合成测试和规则算例均不计作预测成绩。

## 时间与原典增量

度数规则、Uchcha Bala 和 Baladi 已对照 R. Santhanam 卷一的固定扫描本，太阳角距条件明确来自译者第 7 章注释表。顺逆阈值、源文与注释层、端点及 OCR 算例差异见时间尺度与原典复核。仅确认这些具体条文及注释，未声明整部原典已验收。

## 分盘与位置强度

新增 D2（传统日月 Hora）、D3、D7、D12、D30，采用上述 Santhanam 扫描本第 6 章。D30 是五个不等长区段的星座分配，原表没有唯一的盘内度数，故其 `longitude/degree_in_sign=null`；其他等分盘的盘内度数是声明的线性显示约定，不是天文黄经。D30 的符号与宫位不用于补写原典未审的事件解释。

`india.strengths.sthana_bala` 返回七个物理天体的 Uchcha、Saptavargaja、Ojayugma、Kendradi、Drekkana 五分量及总量。单位为 Virupa，60 Virupa 为 1 Rupa；没有人为归一化的满分。节点及上升不填虚构的零分，完整 Shadbala 仍标记 `not_complete`。逐盘关系取 D1 本命位置，不能在各分盘重新计算临时友敌。

`saptavargaja_profile` 仅选择七分盘分量的读法：

| 参数 | 系数：moola／own／great friend／friend／neutral／enemy／great enemy | moola 作用域 |
| --- | --- | --- |
| `santhanam_27`（默认） | 45／30／20／15／10／4／2 | 第 27.2–4 节“其他六盘同值”的逐字星座读法；不是唯一作者意图的裁定 |
| `raman_30` | 45／30／22.5／15／7.5／3.75／1.875 | [B.V. Raman 固定扫描本](https://astrojyotish.info/pdf/graha-bhava-balas.pdf)第30节明确仅D1，PDF27–28页图已核对；具体重印版未核定 |

两者都明确采用星座分配，和 D1 独立的 moolatrikona 度数状态分开。`profile_comparison` 保存两种七分盘分量及其对总量的影响；它不是误差区间或成功概率。其余三分量采用Santhanam27.1、27.4–5的公式，Raman20、31–35也有相同算术。Drekkana独立选择：默认 `santhanam_27_6` 的第二段为月／金、第三段为水／土；`raman_36` 将这两组对调。两者均采用物理D1每星座内的[0,10)、[10,20)、[20,30)区间及15 Virupa，不能改用分盘D3经度。单选 `raman_30` 仍只改变七分盘计分。`drekkana_profile_comparison` 固定当前七分盘读法再比较Drekkana，原有 `profile_comparison` 则固定当前Drekkana比较七分盘读法；不能混取两组最高分。Kendradi 按 Rasi 整宫组，和另选 Bhava 中点算法分开。

原书页图、手算、独立 PyJHora 的对齐项和保留差异见位置强度审计。重建参考数据与测试：

```bash
# 用明确配置的独立参考环境运行生成器；普通测试不重建期望数据。
uv run --locked --extra dev pytest -q tests/jyotish/test_jyotish_sthana.py tests/jyotish/test_jyotish_transports.py
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

印占本命和Vimshottari始终使用记录的民用出生时刻，经时区解析后进入共享UTC／TT／模型UT1转换；开关仅增加太阳钟显示。默认false的盘面、力量和运期数值不变。

`india.profile.clock_context`列出记录时刻、计算UTC、显示开关、无时区的`solar_wall_datetime`、修正分钟及来源。太阳钟标签可能跨日／跨年，甚至与某个IANA夏令时缺失钟时的数字相同；它不是该时区的另一个时间戳，不改变出生日期、达沙起点、分析日期锚点或平均模型窗口。太阳钟显示使用同一TT、模型UT1与视太阳时角，不把UTC直接当作实测UT1，也不认证记录精度或实测地球自转。

已知历史LAT／LMT记录按其真实钟制和明确的`birth_clock_basis`转换，不能先当民用资料再打开显示开关。直接领域调用也拒绝已经太阳时重定位而与记录时刻不一致的旧`AstroBirthInfo`。详见物理时刻修复验收。

## 已知历史太阳钟输入

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

这是虚构技术验算，不是历史人物预测。范围与独立对照见太阳钟输入验收。
