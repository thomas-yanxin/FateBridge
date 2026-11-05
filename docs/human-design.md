# 人类图计算、依据与验证范围

[文档中心](README.md) · [算法覆盖](algorithm-coverage.md) · [调用合同](contracts/human_design.json)

`human_design` 计算出生与设计两个时刻的激活、门／线／Color／Tone／Base、Variable、中心、通道、类型、权威、定义、桥接方案和Profile，并返回来源分歧及可核验的固定解释。REST 为 `POST /api/astro/human-design`，MCP 与 CLI 为 `human_design`；三端共用领域服务。

计算验证、原典解释、来源身份和现实预测分别报告。当前没有可用于认证现实预测的数据，完整原典、完整线义及出版方全部软件约定也未验收。内部算术一致或测试通过不能代替这些证据。

[公开教学来源索引](../tests/data/human_design/source_materials/public-teaching-index.json)保留出处、取得日期及具体未决范围；索引不是全文校勘。近太阳的[原17时刻调查输入](../tests/data/human_design/source_materials/horizons-investigation-inputs.json)保留当时暴露的3.803758角秒天王星差异；当前同源共同框架参考另行核对，不把旧输出作为当前预期答案。

## 计算口径

民用输入经共享时间层转换为TT。物理天体使用[Swiss Ephemeris](https://www.astro.com/swisseph/swephprg.htm)的地心视位置、回归黄道和当日坐标；每项保留实际`return_flags`、后端和数据来源。没有数据文件时可使用明确标记的Moshier；`require_swiss_files=true`拒绝该降级。异常返回不以粗略轨道代替。

`calculation_policy.ephemeris_model_scope=physical_bodies`只汇总十个物理目标。地球、南交点是体系派生对点；平交点是`swisseph_analytical_mean_node`。节点的`native_return_flag_model`保留原始旗标标签，不能由SWIEPH旗标推断解析平交点读取了行星文件。

显式`FATEBRIDGE_JPL_FILE`选择`strict_jpl`。缺文件、坏文件及范围不足须报来源错误；附加Moshier对照按该策略禁用，返回`reference_disabled_by_strict_jpl_policy`和`reference_computation_performed=false`。这不是独立一致性证据。`require_swiss_files=true`仍只表示要求Swiss压缩文件，与严格JPL配置冲突时明确拒绝。

JPL原始文件头范围是TDB，返回`range_time_scale=TDB`及`start_julian_day_tdb/end_julian_day_tdb`；Swiss SE1范围使用TT字段。不再把JPL头的原始TDB数值命名为TT。当前原生TT数值作为JPL参数使用的限制仍按[共享物理来源政策](../src/fatebridge/core/astro/physical_sources.py)声明；字段更名没有实现TDB到TT的物理转换。

### 出生钟、历史时间与闰秒

1960年采用[IAU SOFA](https://www.iausofa.org/2023-10-11c)的UTC偏移／日漂移；1961–1971年采用[IERS UTC−TAI历史关系](https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history)。1960年前采用声明的历史UT1输入约定。UT1回算沿用同一时间策略；模型ΔT不是实测DUT1，也不证明当地出生钟已经核实。

`birth_second=60`及周期参考中的60秒必须对应[IERS已公布正闰秒](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)；普通日期、错误当地分钟和未公布的未来插秒均拒绝。主盘保留经日历规则确认的原始UTC标签，浮点TT的逆算显示另列，不能混作同一精度来源。历史分数秒调整没有唯一民用标签时返回`null`及具名原因，计算仍在TT上进行。

数字时区按十进制小时解释并舍入至最近微秒（中点取偶）；ISO小数小时／分钟保持自身单位。周期参考最多6位秒小数，使用精确民用标签及已声明时标关系比较先后，不能先转换成相同double TT再决定先后。微秒标签不认证微秒物理精度。

独立SOFA参考保留233个历史UTC时刻、81个闰秒邻点，以及全部135个分数偏移闰秒输入、126个ISO约分形式和24个十进制偏移输入。时间换算门槛为0.2毫秒；资料在[当前参考目录](../tests/data/human_design/)及[SOFA历史UTC向量](../tests/fixtures/historical-utc-sofa.json)。这些是时标算术检验，不能认证星体坐标或真实地方钟。

### 设计太阳弧与精确分类

人格盘取出生瞬间；设计盘解`太阳黄经(出生) − 太阳黄经(设计) = 88°`，在出生前110至70日的TT窗口求根，不固定减88天。求根继续至零残差或相邻可表示TT，再取绝对残差较小的端点，平局取较早TT。两黄经先转精确二进制有理数再做角差与环绕。

门、线、Color、Tone、Base采用64×6×6×6×5等分及半开区间。地球与南交点从同侧来源精确加180°后分类，再输出float显示；不能用舍入后的对点显示值重新分类。138,239个有效边界探针使用独立有理数宽度核对；它们是刻意构造的算术输入，不能换算为出生人群错误率。

本地太阳根可能有多个相邻数值候选或非单调量化。结果区分所选端点、实际观测括区、残差、局部候选及其完整联合结构；候选不是多次真实出生时刻。数值根收敛不认证星历物理误差，局部光滑性也不是连续区间根数证明。

### 整盘后端与独立物理参考

`ephemeris_backend_comparison`实际用对照后端重算26项激活并独立求出自身设计根。两盘的设计TT可不同，因此差值包含求根位移，不能当成同一TT的位置误差。`reference_chart`保留参考坐标、旗标、时标和结构；主盘不被替换。所选天体已为Moshier时返回`same_backend_not_independent`；对照不可用不能记成零差。

[预声明天文计划](../tests/fixtures/human-design-astronomy-plan.json)保留1800–2399年的122个出生TT。[独立DE440生成器](../scripts/gen_human_design_astronomy_reference.py)不导入FateBridge或Swiss，分别求122个设计根，两时刻十个物理目标共2,440位置。[原参考](../tests/fixtures/human-design-astronomy-de440.json)及[18个Horizons锚点](../tests/fixtures/human-design-astronomy-horizons.json)保留原数值与出处。

原门槛是同TT位置2角秒、设计根5秒。当前Swiss文件后端通过这批2,440位置及122根；Moshier保留228项位置超差、1项跨线、8项Color、22项Tone及77项Base差异。Moshier设计根通过5秒不弥补其它天体位置超差。该有限样本不建立全时域或临界细分误差界。

[扩展季节参考](../tests/fixtures/human-design-calendar-span-de440.json)保留1,200对双时刻。其方向检查对全部48,000个后端位置运行当前算法，节点参考另覆盖2,400个时刻及原122个控制。门槛仍分别为物理位置2角秒、节点1角秒、根5秒；不能仅据相同返回旗标宣布通过。

[太阳附近诊断](../tests/data/human_design/calendar_horizons/)和[ICRF诊断](../tests/data/human_design/icrf_horizons/)各保留17个TT下太阳与天王星的34个位置，直接绑定原NASA请求、响应和DE440参考。当前采样保留超过2角秒的绝对位置／完整方向差异。无光偏折及共同框架对照用来定位约定差异，不替换原绝对坐标，也不将一维黄经吻合改称三维方向通过。

### 数据安装与计算期间的一致性

出生1800年初时设计盘可退至1799年；可选周期搜索又会延至出生后65年。数据覆盖须包含实际全部计算时刻。

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile human_design
uv run --locked --extra dev python -m fatebridge.fetch_ephe --profile human_design --verify-only
```

此配置安装`sepl/semo/seas`的`12/18/24`分段。数据不随wheel分发，普通计算不自动下载。显式`SE_EPHE_PATH`优先；`doctor`只检查当前数据完整性，不能代替独立天文比较。

本命、设计根、生时范围及周期计算记录实际文件上下文，临时切换、内容变化或来源不一致报`ephemeris_source_inconsistent`。共享原生路径的线程局部记录与最近实际应用路径在同一锁内核对，恢复管理路径后不能沿用另一线程的Moshier上下文。文件身份及旗标一致仍不认证物理精度或原生调用真实性。

## 专业结构与解释依据

通道连接、中心、类型及权威依赖同一联合见证。生成者子型与显化通道分开；投射者权威按实际定义路径判断，环境／无内在权威与反映者月周期另列。Profile取人格／设计太阳线；第六线传统阶段不能由年龄模板直接认证。

分离定义报告定义分群、单门桥接候选和全部最少桥接门集。门数相同不保证方案相同；生时变体须保留完整门集与同次见证，不能拼接不同时刻的门来制造通道。

### Variable与人格Color

四箭头按实际太阳／地球和节点Tone生成，另保留Color、Tone、Base和依赖路径。人格Motivation及View使用六类来源术语；相同箭头不代表Color相同。没有实际观察时不推断转移、分心、对齐或心理测量结果。

### 门语境、线极性与来源分歧

激活门的activated／active／dormant语境依赖该次中心和通道状态；不同公开来源对悬挂门的宽窄定义分别标明。每个联合盘／区间见证使用自己的语境。

`lines`及`lines_v3`至`lines_v7`是当前发布的来源分类，按各自资料覆盖提供引用及有限解释；保留全部384行，不把已核个别门扩成全本认证。来源文件摘要用于绑定实际读取的资料字节，不代表出版方认证。

2001表的极性、同门／谐振触发、26项本命固定分别计算。交点可接受固定但不作触发星体。19份官方图的494个显示投影和138个可见极性标记不能认证356处空白的完整固定状态。

29门印刷分界与均匀线算法仍有分歧；原典名称也有不同拼写和序号，不自动改写为一致。当前19图对照保留15项字面名称失败；193图扩展也不建立完整原典接受。

58.5保留2001表与2002通讯假设的条件比较；两张已观察官方PDF的下降标记不删除，也未据未经认证的通讯切换默认极性。该分支的historical指真实来源年代，不是退役软件兼容。

[当前原始PDF索引](../tests/data/human_design/primary-source-index.json)保留当前目录／观察表直接引用的234份唯一PDF字节。索引和出处使材料可检查，不自动认证作者、图上符号含义或未公开原典。

## 可选行星周期交会

`cycle_reference_datetime`须为不早于出生、带明确时区的ISO标签。省略即`not_requested`，不取当前钟。搜索人格出生黄经起算的土星首轮360°、天王星180°及凯龙首轮360°，上限65儒略年；这不是寿命或教学阶段。

搜索使用2日TT网格、已观测速度变号及有限坐标极值补探，保留顺行、逆行和最后顺行候选。出生后逆行重访原黄经不等于完成一圈。根区间0.0002秒、驻点区间0.01秒及角度残差1e−7度是数值判据，不是天文误差界；12项量化近峰控制仍不认证连续根数。

`cycle_context`保留同次原始计算见证，`cycle_summary`始终输出当前紧凑格式及显式默认约定。摘要压缩必须保留每次交会的数值事实和运动分歧，不能借缺字段推断已知值。参考时刻与交会以精确TT关系比较；实际民用标签的浮点量化限制另列。

天王星人格起算有明确资料；土星／凯龙起点和多触首末优先未统一。`sixth_line.current_phase=null`，不把有限求根结果升级为已认证阶段。凯龙数据缺失或失败逐项保留，不能删除失败目标后宣布周期完整。

## 生时范围

`birth_time_uncertainty_minutes`在TT上计算实际联合样本和变体，包含细分、类型、权威、Profile、桥接及Variable的完整依据。它不覆盖可选周期事件日期。

有限网格、速度候选和局部极值细查不构成连续区间穷尽，`continuous_interval_certified=false`。结果相同只能说明已计算样本相同；逐层值集合不是笛卡尔积。范围为0时评估字段为`null`，不能读成已证明稳定。原生月球文件的分段边界和量化使驻点／变化边界仍有限制。

## 验证范围与现实预测

当前验证器重建实际数据关系、源码对应的当前规则、精确分类、同次来源和固定文字，拒绝篡改后重新计算业务哈希的结果。`run_metadata`是执行收据，不作为新的业务出生钟记录遍历。返回`verified_fixed_template_reading`只说明限定模板和见证关系核验，不能认证真实出生资料或任意模型自由文本。

外部资料的时钟及缺失行逐项保留。盘面时钟对照中22个计划仅13个观察、缺9个；338门线有337项吻合，Neptune19.6／19.5反例仍失败，5项名义钟差75秒不能归因于单一星历。完整官方角色对照也不能用名称或基本结构吻合替代细分精度。

盘外模型保留24个输入、520个模型数值、10条转录观察、14条缺失及5项钟时冲突。对应原PDF未取得，`primary_source_status=not_available`，转录条件下的兼容不认证原始来源或出版方后端；当前24次运行只验证实际算法与已有条件参考的关系，不能从当前输出制造期望值。

192／768角色来源集合继续保留576项未收集缺口；有限已知开发题不是独立留出集。来源冲突、物理超差、解释范围与预测数据缺失均独立阻断相应认证。

## 显式视位置模型对照

原生后端的完整固定队列每侧含 24,000 个位置、1,200 个设计根：Swiss 位置 23,999／24,000，保留 1 项失败；Moshier 位置 21,762／24,000，保留 2,238 项失败。两侧各 1,200 根均在原 5 秒线内。Swiss 未过项为天王星设计位置，差 3.803758 角秒；关闭光偏折的单项诊断没有消除它，原生产旗标和参考未改。以下显式候选另行比较，不替换原生验收。

`compare_apparent_models=true`在实际人格与设计TT上增加`apparent_model_comparison`。方法`swiss_barycentric_sun_monopole_iau2006_v1`使用同一套重心几何状态、有限源太阳点质量偏折、ERFA光行差及IAU2006/2000A真黄道。输出保留地球、目标发射时刻和太阳近光路时刻的状态与实际输入旗标；这些旗标不冒充最后派生视位置的原生旗标。所有10天体采用同一约定，不按误差逐行切换模型。

该对照需要`jpl`额外依赖及实际可用的重心星历文件；缺ERFA返回显式不可用，文件状态失败不降级到无法提供重心状态的Moshier。原生激活、原设计根和默认节点模式保留。候选可用时输出`design_root_recomputed=true`、`candidate_design_root`及`candidate_design_epoch`，并将原生设计TT与候选根相差秒数单列。求根全程使用候选自己的太阳位置与既有88度求解器，保留相邻浮点格、残差和实际旗标；不读参考根作为输入。候选不可用时显式保留原因。

原超差天王星位于所给名义太阳盘投影内。Swiss使用透明太阳质量分布延拓，点质量模型有另一套数学延拓；太阳盘内结果不能解释成可见天体位置。依据见[Swiss附录](https://www.astro.com/swisseph/swisseph.htm)、[ERFA有限源偏折](https://github.com/liberfa/erfa/blob/master/src/ld.c)及[Skyfield偏折实现](https://github.com/skyfielders/python-skyfield/blob/master/skyfield/relativity.py)。本方法显式取偏折限制参数`1e-11`，不是通用IAU规定值；只计太阳单极项，未计行星偏折。

同原封存DE440参考、原1200时刻双侧10天体、原2角秒门槛的24000位置均符合，最大差0.038386角秒。候选自己的全部1200设计根也在原5秒门槛内，最大差0.055442秒；人格TT及自身设计根的24000位置在原2角秒线内，最大差0.053665角秒。原Swiss的1项失败与Moshier的2238项失败仍单列；没有改参考、删太阳近旁点或调整门槛。该有限队列比较不证明全域物理误差界、原版软件模型或现实效度。

```bash
uv run --locked --extra dev python scripts/audit_hd_point_mass.py --output /tmp/hd-point-mass.json
```

## 调用与复核

输入、`evidence_views`及支持字段以[当前合同](contracts/human_design.json)为准。摘要按问题选字段，完整JSON首次不限制字段；分页／延迟字段从同一run的`result_delivery`读取，不重算另一run冒充完整交付。

```bash
uv run --locked --extra dev fatebridge human_design \
  --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-timezone Asia/Shanghai \
  --fields type authority profile bodygraph interpretation \
  --strict-fields --include-snapshot-text false

uv run --locked --extra dev pytest -q -n0 \
  tests/test_human_design_astronomy.py tests/test_human_design_cycle_phase.py \
  tests/test_ephemeris_thread_paths.py
```

示例是虚构工程输入。离线包验证、当前本地三端协议和真实模型答复分别验收；任何一项通过不自动证明其它层。
