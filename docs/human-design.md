# 人类图计算、原典依据与专业验收

[文档中心](README.md) · [算法覆盖](algorithm-coverage.md) · [调用合同](contracts/human_design.json)

`human_design` 提供记录出生瞬间和设计瞬间的双组星体激活、门／线／Color／Tone／Base、四箭头Variable、九中心、36通道、类型与子型、策略、权威、定义分群、单门桥接候选及全部最少桥接方案、人生角色、原典轮回交叉名称、384线极性星体和本命同门／谐振固定依据。REST 为 `POST /api/astro/human-design`，MCP 与 CLI 为 `human_design`，三端共用领域计算。

这是可追溯的机制实现。现实预测没有可评估样本，完整原典认证也未通过；不将软件测试数或来源知名度换成专业能力或预测分数。

解释验收配置复核（本地数据：`validation/human-design-evaluation-native-config-v1/README.md`）修复参考MCP遗漏显式星历环境变量的问题：准备和执行两阶段共用并校验同一份五项数据选择声明，保留空值、未设置状态及原失败结果。声明摘要相同只证明配置选择字节一致，实际后端旗标、文件见证及天文精度仍分别核对；旧答卷没有的配置不能事后补证。

验收路径上下文复核（本地数据：`validation/human-design-evaluation-path-context-v2/README.md`）进一步绑定显式相对路径的原始解析目录，避免源码快照或模型临时目录改变实际星历选择。原路径列表与JPL文件名保持原值，MCP从冻结源码的绝对脚本入口启动，防止数据目录里的同名Python包抢先导入。旧版记录不补造工作目录依据；路径声明、实际后端、源码绑定和物理准确度分别验证。

[激活门与中心语境复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-gate-activation-context.md)区分activated、定义中心内的active和未定义中心内的dormant，同时保留公开资料对悬挂门的宽窄口径。完整结果逐一绑定实际联合见证，旧结果按明确契约兼容且不补发新增认证；原有数值、说明和失败案例保留。

[周期参考时刻小数单位复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-reference-fraction-precision.md)修复小数小时／分钟被误读为小数秒，以及字符串固定位置触发的闰秒误识别。保留原126项独立民用参考、原错误回执、全部旧案例和专业验收标准。

[逐年采样与太阳遮掩视位置复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-calendar-span-precision.md)在原参考之外固定1200个出生TT，发现一个所选Swiss后端超差点，定位到太阳盘内的引力偏折约定分歧。原失败及原门槛保留；完整年代验收仍未通过。

## 计算口径

输入公历年月日、当地出生小时／分钟及明确时区；日期范围1800–2399，不自动转换历史儒略历。秒省略为0，仅表示采用记录分钟的起点。时区支持 IANA 或明确偏移，拒绝夏令时不存在／未消歧的重复时刻。无需经纬度：地心黄经不使用地表位置、宫制或上升，也不作真太阳时重定时。

十进制小时偏移先精确计算，再按最近微秒取偶转换；确实量化时回显0.5微秒输入误差上界。亚秒UTC偏移在原生进程、周期输入排序及完整解释重放中保持一致。原先整秒舍入的24项独立有限案例和初版共享回归失败均保留，详见[十进制时区精度复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-decimal-offset-precision.md)；这不改变完整历法、原典及现实预测的未验收状态。

[闰秒小数标签复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-fractional-leap-precision.md)进一步覆盖全部27次已公布正闰秒的135个既有合法输入：主盘保留经日历表确认的原始UTC标签，实际浮点TT的逆算显示另按原观测保留，完整解释核验不再把两者混用。保留原先9微秒错误标签的误通过回执，并核对同一浮点TT上的周期先后；它不认证微秒级天文精度或真实地方钟。

由民用 UTC 经公共时间层转换 TT，以 [Swiss Ephemeris](https://www.astro.com/swisseph/swephprg.htm)计算视位置、回归黄道、当日黄道坐标。返回每颗星实际 `return_flags` 和后端：无数据文件时可使用并明确标注 Moshier；`require_swiss_files=true` 时拒绝此降级。Swiss 不可用或星体返回异常时直接报错，不套粗略轨道替代。

`calculation_policy.ephemeris_model_scope=physical_bodies` 只汇总十个原生物理天体；节点及体系对点另见 `nonphysical_factor_models`。平交点的模型是 `swisseph_analytical_mean_node`；激活的 `native_return_flag_model/return_flags` 保留回显位，不能据此宣称读取了 Swiss／JPL 矢量文件。生时抽样也把物理模型与非物理因素分开，四箭头的因素模型仍按实际依赖披露。

运行者显式设置 `FATEBRIDGE_JPL_FILE` 时，`physical_backend_policy=strict_jpl`。主盘和真／平交点约定比较仍使用所选配置，`reference_computation_performed`表示完整参考盘是否成功完成；附加 Moshier 对照则显式返回 `reference_disabled_by_strict_jpl_policy` 与 `reference_computation_performed=false`；未执行的对照不是精度证据。缺文件、坏文件或越出主计算范围仍报来源错误，不能用“对照未执行”掩盖。`require_swiss_files=true` 保留仅要求 Swiss 压缩数据文件的含义，与显式 JPL 不相容时返回具名配置冲突。设计时刻求根仍使用出生前110至70日的原括定窗口；新增192日原始系数夹具（本地数据：`../tests/fixtures/human-design-de441-j2000.provenance.json`）覆盖J2000虚构出生时刻的完整窗口，只修改原始文件头的范围双精度数，六个记录的系数不变，且与旧96日夹具逐字节重叠。旧夹具保留，不能冒称完整DE441年代覆盖。

1960年采用[IAU SOFA 2023-10-11](https://www.iausofa.org/2023-10-11c)的UTC偏移／日漂移；1961–1971年使用[IERS历史UTC关系表](https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history)的13段关系，包含一天内的连续漂移。1960年前仍显式采用历史UT1输入约定；使用标准关系不等于已核实当地出生钟或国家授时台的实际实现。SOFA补表独立保存，没有改写原IERS文本或13条记录。历史分数秒调整若使TT没有唯一的标准datetime标签，`design_utc=null`，在`utc_label_status`说明原因，仍以准确TT计算设计激活；不造一个午夜标签。1961年元旦的5毫秒调整也按此处理。

独立编译未修改的SOFA C源文件，经`iauDtf2d(UTC) → iauUtctai → iauTaitt`生成233个固定时刻（本地数据：`../tests/fixtures/historical-utc-sofa.json`），覆盖1960–1971各月和系数切换边界。事先容差为0.2毫秒；修复前18个1960年时刻未通过，最大差约22.5毫秒，修复后233个均通过，最大差约0.039毫秒。1960-06-15 11:55 UTC的本地Swiss月亮回归案例由Tone2／Base1变为Tone1／Base5；这是按固定日期分钟搜索发现的同引擎回归案例，不能当作独立黄经真值。完整证据见1960时标复核记录（本地数据：`validation/human-design-utc1960-verification.json`）。

规则1.23.0补齐已公布正闰秒的出生入口。`birth_second=60`先按所填时区换算，再核对冻结[IERS插秒表](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)中的真实插入记录；普通日期、错误当地分钟、历史分数秒调整和未公布的未来插秒均拒绝。UTC的2016-12-31 23:59:60与上海的2017-01-01 07:59:60对应同一TT，区别于下一分钟的00秒；不借Python datetime把60秒归并到午夜。后续设计根、真／平交点对照、后端对照、生时范围和可选周期均沿用该出生TT。周期参考ISO时刻也接受经确认的60秒，分数部分最多6位。

闰秒盘另返回`birth_clock_evidence`，包含当地与UTC标签、插秒前后的TAI−UTC、实际TT、原始IERS文档和冻结表散列，以及未认证出生记录的声明。`interpretation.birth_clock_meaning`和新增逐句依据绑定该见证；完整解释核验会拒绝标签、当地时区、TT、来源或文字被篡改后重新计算哈希的结果。普通出生保持原有计算及这八条固定说明；1.24.0增加交点比较说明，1.25.0在原九条之后增加出生时间范围说明；闰秒说明仍置于首条。`birth_clock`证据卡仅用于闰秒盘，字段列表从调用合同取得。

独立SOFA生成器从已固定官方源码选取全部27次正闰秒，每次保留59秒、60秒、次日00秒，共81个时刻（本地数据：`../tests/fixtures/human-design-leap-sofa.json`）。全部通过原有0.2毫秒TT容差，最大差约0.0251毫秒；这是单个二进制TT儒略日相对SOFA两段TT的换算误差，不是星体位置误差或出生记录精度。未改写旧233例、29门印刷分界、官方名称失败或Moshier精度失败；全过程见正闰秒复核记录（本地数据：`validation/human-design-leap-verification.json`）。

```bash
uv run --locked --extra dev fatebridge human_design \
  --birth-year 2016 --birth-month 12 --birth-day 31 \
  --birth-hour 23 --birth-minute 59 --birth-second 60 --birth-timezone UTC \
  --fields birth_utc birth_clock_evidence time_scales.personality interpretation.birth_clock_meaning
```

规则版本1.13.1统一了设计时刻及TT区间样本的UT1回算。此前这两处总以SWIEPH旗标计算ΔT，与1960年前民用输入所用的Swiss `utc_to_jd`默认规则不同；安装Swiss文件时，1800年固定样本相差约0.297秒、1900年约0.037秒。现在复用共享`ut1_from_tt`，与正算采用同一历史策略。[Swiss原始日期转换代码](https://github.com/aloistr/swisseph/blob/master/swedate.c)明确使用`deltat_ex(..., -1)`，其[编程文档](https://www.astro.com/swisseph/swephprg.htm)也说明ΔT会随星历固有的月球潮汐加速度变化。这次修复影响UT1元数据；同机固定样本的TT根、原始坐标、细分及图结构保持原值。UT1仍是模型估计，不是实测IERS DUT1，也不能据往返一致宣称真实出生钟准确。详见UT1策略复核记录（本地数据：`validation/human-design-time-policy-verification.json`）。

人格盘为出生瞬间；设计盘求解 `太阳黄经(出生) - 太阳黄经(设计) = 88°`，在连续TT上括定后二分，而非在不连续的民用UTC上求根或固定减88天。残差、求根区间宽度与实际相隔天数都在 `design_solver`。例如虚构输入1990-04-06 09:33 Asia/Shanghai，间隔约87.516天；求根到亚毫秒量级是内部数值收敛，不证明实际出生时间有毫秒精度。规则依据为 [Ra Uru Hu 官方介绍](https://jovianarchive.com/blogs/human-design-basics/introduction-to-the-human-design-system)。

规则集1.18.0将设计太阳弧继续收敛至相邻可表示的TT浮点时刻，或一个实际求值为零的时刻；从最终端点选择绝对残差最小者，平局取较早TT。旧算法在0.0002秒区间内取中点，并不保证这个选择。残差现在由两个返回黄经的精确二进制有理数求差后再做角度环绕，避免先浮点相减丢失低位。固定10个线性太阳函数的独立有理数案例中，旧算法有6例没有选择最佳可表示TT；这些修复前记录保留，修复后10例全部匹配。它们是数值反例，不是真实出生记录或独立星历参考。

`design_solver.numerical_precision`保留出生太阳函数值、最终上下端点、选中点、原始太阳黄经及精确残差分数；分数的分子、分母用十进制字符串避免JSON客户端舍入。`solar_endpoint_subdivisions`仅分类求根函数端点的太阳与地球对点，`observed_solar_changed_levels`列出端点间实际变化。即使区间只约40微秒，边界附近仍可能有不同Base；不能从小区间或零残差宣布细分确定、连续稳定或物理时刻准确。其他设计天体的根区间敏感性未在此评估，`physical_time_accuracy_certified`与`other_bodies_bracket_sensitivity_assessed`均为false。主盘保留选定TT的实际星历坐标，不将黄经强制吸附到理论边界。

[Swiss接口](https://www.astro.com/swisseph/swephprg.htm)使用双精度TT儒略日；[Python nextafter](https://docs.python.org/3/library/math.html#math.nextafter)用于确认没有可表示的中间TT。`interpretation.design_time_precision_meaning`绑定本次根区间和端点细分；`precision`及`ephemeris`视图可读取。完整结果及其完整后端参考都须通过新的根见证检查；保留的旧版本原始夹具只能核对旧有关系，其`checked_adjacent_solar_root_count=0`，不能升级为新版精度证据。删去当前结果的根见证仍被拒绝。详见设计根精度复核（本地数据：`validation/human-design-solar-root-verification.json`）。

太阳、月亮、水星至冥王星和北交点直接计算；地球为太阳对点，南交点为北交点对点，共每侧13激活。`node_mode=true/mean` 是显式约定，默认true；同时比较另一口径对门线及类型、权威等的影响。尚未认证原版软件所用交点口径，不以个人认同程度选择口径。

41门从黄经302°开始，每门5°37′30″，每线56′15″，其下6 Color、6 Tone、5 Base。使用输入浮点数的精确有理表示进行半开区间分类，先分类再展示，不用 epsilon 或提前舍入把边界点推至一侧。Color/Tone/Base 是计算细分，尤其接近边界时对秒数、星历口径敏感，不能视为健康、认知或遗传机制已得到验证。

地球与南交点还须保留派生前的精度。依据[官方Earth词条](https://jovianarchive.com/pages/human-design-dictionary)的日地对点关系，地球从太阳、南交点从北交点的原始浮点黄经取精确有理数，加180°后直接分类，最后才生成显示用`longitude`。派生激活带`derived_from`和`derivation_source_longitude`；不能只拿显示黄经再次分类，因为它可能已舍入到边界。比如合成来源角度`43.32812499999999°`的对点显示为`223.328125°`，实际仍在Tone3／Base5一侧，不能按显示值改成Tone4／Base1。

已对69,120个均匀Base边界的两个相邻浮点数实施138,239个有效合成探针：旧的浮点加180°再分类在20,223个探针中出错，亦涉及门和线；新实现与独立有理数宽度检查全部一致。这些是刻意靠近边界的算术压力测试，不是出生人群错误率、独立星历观测或全面原典验收。生时变体见证保留派生来源，节点后端比较也使用相同精确关系；完整run核验拒绝来源重绑定，即使重新计算业务哈希。详见对点边界复核记录（本地数据：`validation/human-design-opposition-verification.json`）。

设计时刻即使落在插入的UTC闰秒内，也继续用精确TT计算星体并显示 `23:59:60`；不把它平移为次日0点。`design_solver`分别报告TT日数与可表示的民用日数，跨闰秒时两者可相差一秒；出生秒输入目前仍为0–59，出生记录本身为闰秒的输入尚需扩展。所有27个冻结正闰秒的内部与边界均有测试。

后端差异也会影响精细结果：在1971-12-01 00:58 UTC这一回归案例，本地Swiss数据文件与Moshier月亮黄经相差约0.37″，落在不同Base。该例的IERS时刻校正约0.141秒，在Swiss文件后端改变了Base，不能把同一Base期望套到所有后端。实际`return_flags`与后端必须随结果保留；这不是已确定的全时域误差界。

`node_backend_comparison`在同一人格／设计TT时刻实际计算Moshier真交点，与所选后端逐层比较；另外重算只替换节点后的完整通道、类型和权威，保留所选盘。其他星体和太阳弧时刻未换后端，故不是另一后端的完整重排。官方[节点文档](https://www.astro.com/swisseph/swisseph.htm)报告JPL与Moshier真交点的最大差异约70″，JPL与Swiss约0.1″；前者大于Base的18.75″宽度。发布者近似差异及当前后端差值均不是每盘误差上界。

若所选节点已是Moshier，返回`same_backend_not_independent`，不以零差值认证精度；平交点属于分析平均要素，切换后端旗标不能制造独立模型，返回`analytic_mean_node_not_cross_validated`。参考计算失败须保留`reference_unavailable`，不能当作吻合。真／平交点约定仍单独读取`node_convention_comparison`。

共享来源标记进一步区分实际计算模型与原始旗标：平交点的`ephemeris_model`为`swisseph_analytical_mean_node`，节点另以`native_return_flag_model`保留原始返回旗标解出的标签。原始`return_flags`不变，SWIEPH标签不再被解释成解析平交点读取了行星文件。Moshier节点参考须同步更新自身标签，不能复制主盘的SWIEPH标签。完整参考盘核验拒绝伪造来源标签；旧冻结样本的测试适配仅从原旗标补齐新标签，不改原数值，也不放宽这项拒绝检查。旗标自洽不认证天文精度或见证真实性。

### 整盘后端与独立设计根

`ephemeris_backend_comparison`在同一出生TT、同一交点约定下，实际用Moshier重算全部26个激活，并重新求解其自身88°太阳弧设计时刻。设计盘两侧TT可能不同；逐项差值包含求根位移，不能当作同一时刻的坐标误差。`reference_chart`保留完整参考坐标、时间、实际旗标和图结构，`mechanical_comparison`给出同一参考的桥接、线固定及Variable联合依据；主盘不因比较而被替换。

物理天体也可能跨线界，不能只检查交点。固定回归输入1810-07-02 12:00 UTC中，设计冥王星在Swiss文件后端为63.6、Moshier参考为63.5，差约3.285″；两者设计TT相差约0.199秒。该民用日期采用已声明的历史UT1约定，不能声称出生钟已被核实。

当所选物理天体均已采用Moshier时，返回`same_backend_not_independent`，不作重复计算并伪造认证。实际模型见`selected_physical_models`，全部原始旗标另留在`selected_provenance`。平交点可在无文件环境返回SWIEPH旗标，它是解析平均要素，不计入物理文件后端判断。参考失败返回`reference_unavailable`，不能变成零差异或吻合；`ephemeris`证据卡提供紧凑摘要，完整参考须读取同一run。

预先固定的天文计划（本地数据：`../tests/fixtures/human-design-astronomy-plan.json`）选取1800–2399范围内122个出生TT，不使用引擎结果选择日期。独立[DE440／Skyfield生成器](../scripts/gen_human_design_astronomy_reference.py)不导入FateBridge或Swiss，分别求出122个设计根，并冻结两个时刻的十个视位置，共2,440项。使用[NASA DE440内核](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440.bsp)与[Skyfield真黄道／真春分点当日参考系](https://rhodesmill.org/skyfield/api-framelib.html)，内核按NASA公布校验值核验，参考结果在独立数值文件（本地数据：`../tests/fixtures/human-design-astronomy-de440.json`）。

目标须一致：[Swiss文档的星体中心说明](https://www.astro.com/swisseph/swisseph.htm)指出常规火星至冥王星采用行星系统质心；这里没有将其冒充卫星已分辨的星体中心。十个目标不包含地球体系对点或月交点。另以[Horizons量31](https://ssd.jpl.nasa.gov/horizons/manual.html)直接读取TT，对预先固定的太阳、月亮、冥王星18个出生／设计锚点交叉核对；完整原始响应在锚点参考（本地数据：`../tests/fixtures/human-design-astronomy-horizons.json`）。Horizons的IAU76/80与Skyfield的当日参考系并非完全相同，18项最大差约1.220″，均在采集前声明的2″比较容差内，不据此认证全部2,440项。

同一TT的2″位置容差、设计根的5秒比较容差均在采集前固定。当前Swiss文件后端2,440项位置和122个设计根均通过：最大位置差约0.037″、根差约0.061秒；Moshier有228项位置超容差，最大约8.452″，并保留1项跨线、8项Color、22项Tone、77项Base差异。Moshier的122个设计根虽均在5秒内，也不能替代其他天体位置或细分验收。参考自身求根的微小残差只是数值收敛，不代表出生记录精度。

这些是有限TT样本，不能推成全时域误差界、全部临界细分或原典全本认证。完整生成环境、失败项、三端／安装包与Linux复核见整盘星历复核记录（本地数据：`validation/human-design-astronomy-verification.json`）。

覆盖1800年初的出生资料时，设计时刻可能退至1799年；只装`sepl_18.se1`、`semo_18.se1`仍会在设计盘降级。完整支持范围需另有`sepl_12.se1`、`semo_12.se1`，放在操作员设置的`SE_EPHE_PATH`或项目`ephe/`。文件来源为[Astrodienst官方仓库](https://github.com/aloistr/swisseph/tree/master/ephe)。数据文件不随安装包自动下载；用`require_swiss_files=true`验收两侧全部激活的实际后端。本机已补齐缺失的前一段文件，并保存下载字节、Git blob散列和修复前后对照。

安装包也可显式运行`python -m fatebridge.fetch_ephe --profile human_design`，从固定官方提交下载并校验`sepl`／`semo`／`seas`的`12`、`18`、`24`三个分段，共9个文件。文件配置涵盖1799–2465年：既包含出生前设计时刻，也包含最晚出生输入的可选65儒略年周期搜索与凯龙星轨道。已有项目`ephe/`会原地补齐；没有项目数据时使用可校验的用户缓存，下一次运行自动发现。显式`SE_EPHE_PATH`继续优先，下载不会改写操作员配置；自定目录或已有优先目录时按命令提示配置路径。`--verify-only`可离线核验；`fatebridge doctor`的人类图项分别报告当前目录和缓存的文件完整性，不执行天文精度或完整专业验收。数据仍不随wheel分发，计算不会自动下载。范围内有文件不证明所有时刻准确，实际返回后端和原有独立参照仍必须核验。仓库外的真实安装包、原228项超差、完整解释与协议对照见安装精度复核（本地数据：`validation/human-design-installation-verification.json`）。

太阳附近三方历表与光偏折复核（本地数据：`validation/human-design-calendar-horizons-v1/README.md`）进一步保留原3.803758″天王星失败点，并在预先固定的17个TT时刻查询太阳与天王星。Horizons、原DE440/Skyfield及Swiss默认采用不同坐标／光偏折约定；关闭光偏折的配对诊断定位了主要差异，但不替代绝对黄经、原2″阈值或完整历表验收，新增近太阳点仍有超差。原审计脚本保留，扩展结果由独立版本入口提供。

## 四箭头Variable

`variables`把实际人格／设计的日地、南北交点四组Tone汇总为左右箭头。依据为[Ra的四组Variable说明](https://jovianarchive.com/blogs/deeper-mechanics-system-theory/a-simple-guide-to-variable)及[官方Tone分组](https://jovianarchive.com/pages/the-basics-of-substructure-in-human-design)：Tone1–3向左，4–6向右。编码先P（人格）后D（设计），各组先日地、后交点；例如固定测试时刻2000-01-01 12:00 UTC、Swiss文件后端为`PRR DLL`。

每个箭头列出两颗实际星体的Tone引用、数组路径、所用后端及图上位置。日地或交点对的Tone缺失、类型错误或彼此不同，保留对应状态，不拼出一个编码。四箭头是体系内数值记法；不把L/R转换成现实认知、学习能力、饮食或健康结论。

`variables`证据卡同时给出字段绑定释义与生时、交点约定、后端差异。后端比较返回`selected_structure`和`reference_structure`，并实际重建替换节点后的Variable；不沿用原盘编码。生时区间中各Variable与同一个实际见证绑定，不能跨时刻拼接四个箭头。与官方样本吻合不等于任意生时、后端或临界黄经下都准确，`subdivision_accuracy_certified=false`继续保留。

## 专业结构与解释依据

- 人格与设计激活取并集，完整通道的两端才定义中心。一个中心可未定义但有激活门；完全开放还要求没有激活门。
- 类型依中心和连通路径判定；骶骨定义为生产者，马达与喉中心连通时为显示生产者子型。间接路径也计算，不能只检查20–34，也不能把“有马达＋有喉”当作已经连接。
- 权威按情绪、骶骨、脾、意志、自我表达等结构优先关系判定。心理投射者的环境过程与反映者月亮过程明确为无内在权威；四类型、八种权威过程与原典传统名称分开保存。
- 定义用完整通道图的连通分量，输出无定义／单一／二分／三分／四分及中心群。`single_gate_bridges`列出增加一个门即可合并部分既有群的候选；`definition_bridging`另给连接全部原分组的所有最少门方案。假设桥接不表示人的缺陷。
- Profile由人格太阳线／设计太阳线组成；只接受12种合法组合。轮回交叉给人格日地、设计日地四门、右角／并列／左角及2001版原典名称，保留原拼写和版本号；名称不代表事件预言。
- 每个通道保留两侧来源，区分人格完整、设计完整和仅混合后完整。`gate_evidence` 给出实际激活门的原典中心、门回路标签、通道端点和PDF页码。门回路与通道分类不可互相覆盖。

### 角色、上下卦与第六线过程

`profile_evidence`分别绑定人格、设计两侧实际日地线号，保留原始数组路径、六线传统称谓、主题及上下卦；数字顺序保持人格在前、设计在后。传统conscious／unconscious标签不表示已经测量了人的心理意识状态。日地缺项、线号类型错误、两星不一致、非法组合或与交叉角度冲突时，结构返回对应未完成状态，不补造主题。

角色角度与单条线的上下卦分别判定。[官方角色说明](https://jovianarchive.com/pages/understanding-profile-in-human-design)列出7个右角、1个并列、4个左角组合；[4/6教学简介](https://jovianarchive.com/products/the-4-6-profile)明确两条上卦线仍组成右角角色，不能因为4与6朝向人际互动就改标左角。4/1单列并列结构，保留`Fixed Fate`这个原类别名，不能将其解释为现实结局不可改变。

只有角色本身含6线，`sixth_line_process`才列出传统三阶段顺序与受影响的人格／设计侧；普通月亮、节点或其他激活落在第六线并不能触发这项角色说明。[Ra公开六线讲解](https://jovianarchive.com/blogs/chart-interpretations-components/the-six-lines-of-the-hexagram)使用土星与Kiron回归作转折标记，并给出约28–29及50–51岁的教学近似年龄。这些不是已求出的天文事件；本命角色证据的`current_phase`与`computed_return_dates`保留`null`，状态为`not_assessed_in_natal_profile_evidence`。可选周期交会在独立的`cycle_context`与`cycle_summary`返回，不写入只由26激活及八个Tone决定的联合快照缓存，不按30／50岁生日划阶段，更不把6/3本命角色改写为3/3。

[紧凑事实参考](../src/fatebridge/data/human_design/profile-2026-reference.json)由[独立提取器](../scripts/build_human_design_profile_reference.py)从两页公开来源的标题、类别和周期标记提取，不导入FateBridge计算模块，不保存完整课程或384线正文。六线中文主题是简短转述，不认证人格测验或现实效力。12组标题事实及19组既有官方盘的实际角色／角度均已作有限核对；这不解决2001年印刷线界或15项交叉名称分歧。

`profile`是证据卡名称；调用时使用其`fields`清单，不能把卡名当作请求参数。`fields=profile`只会取得角色数字，详细结构读取`profile_evidence`。该卡保留角色专属作者、版本、来源与当前印刷分歧影响。固定模板的角色句绑定同次`profile_evidence`；时间、交点及后端联合快照各保留自己的角色结构，不能从名义盘挪用，也不能将近似年龄包装成已计算阶段。完整范围见角色复核记录（本地数据：`validation/human-design-profile-verification.json`）。

具体爻义的来源参考通过既有`knowledge_registry(domain="human_design")`与`knowledge_read(domain="human_design", category="lines", key="1.1")`提供。全部384线都有固定公开副本的页码、块散列与原极性星体索引；1.1至2.6共12条有本地简短转述，待独立复核，其余372条的爻义为null并明确标为未整理；覆盖数从实际组合目录计算。原v1保留，第二批经独立补充与条件绑定（本地数据：`validation/human-design-line-knowledge-v2/README.md`）追加，独立完整线义验收仍为0。2.3原文服务回报有永久连接14门、形成2–14通道的条件，查询不自动判断个人是否符合；未记录条件也不表示其他条目无条件。2.6上升段的接纳视野狭窄含义保留。条目不选择个人适用极性；解释时仍须读取同run实际门线、`fixing_state`及供给固定的路径。1.4重复措辞保留为疑点，不作勘误或完整语义通过。该入口不改变本命或周期计算，资料可读、局部转述、独立语义验收与出版母本认证继续分开，见线参考与解释边界复核（本地数据：`validation/human-design-line-knowledge-v1/README.md`）。

完整回执绑定的名义盘线参考包（本地数据：`validation/human-design-bound-line-reading-v1/README.md`）提供新的本地Python API与模块CLI：先验证完整原run，再保留所选名义盘全部26激活及未知爻义，单独绑定固定侧重与2.3上升段的通道条件。包核验必须提供外部另存的可信原始run，拒绝整包换盘、缺行、额外文字或虚报认证。其他口径、生时样本及周期的新增线义仍明确未组装；原始完整结果与旧核验保留。该入口未新增REST或MCP工具，亦不改变原计算／Schema，不认证完整爻义或现实效力。

### 可选行星周期交会

规则集1.15.0接受`cycle_reference_datetime`，必须是出生之后、带明确时区的ISO时刻。省略时`cycle_context.status=not_requested`，不采用当前时间。提供后，从人格出生黄经起连续展开黄经，搜索65儒略年内土星首轮360°回归、天王星180°对冲及凯龙星（Kiron／Chiron）首轮360°回归；出生后很快逆行重访原黄经不算完成一圈。65年仅是搜索上限，不能解释为寿命或教学分期。

计算使用2日TT网格，细查已观测速度变号，并保留目标黄经的顺行、逆行再次交会及最后顺行交会。周期仅使用名义出生瞬间；`birth_time_uncertainty_minutes`的已有评估不覆盖周期事件日期。数值根附TT、夹根端点、角度残差、运动方向和实际原始旗标；全部计算点作为可重放见证随同次run保存。根区间收敛至0.0002秒只是该数值函数的收敛，不认证星历物理准确度、所有隐藏交会或实际出生记录。未来UTC标签保留未公布闰秒不变的假设。

规则集1.20.0修复多年代搜索的展开角累加漂移：逐段浮点角差改为实际返回二进制黄经的精确有理差。相邻差精确相加后等价于当前黄经减出生黄经再加整数圈，不改变原星历坐标、2日网格、0.0002秒夹根阈值或`1e-7`度残差阈值。[Swiss编程接口](https://www.astro.com/swisseph/swephprg.htm)以TT儒略日计算位置，返回双精度黄经，速度需明确请求且单位为度／日；有理差只消除后续运算漂移，不提高这些输入的物理准确度。

预先冻结的24项解析方案（本地数据：`../tests/fixtures/human-design-cycle-phase-plan.json`）中，修复前4项数值区间未包含已知解析根，22项残差与直接相对本命黄经求差不一致，最大时刻偏差约0.0002414秒。全部原案例与修复前结果（本地数据：`validation/human-design-cycle-phase-before.json`）保留，修复后24项均通过。解析函数的已知零点与返回黄经舍入后的函数零值须区分：某些对冲位置经双精度返回后会有极小非零角差；不将其改写为原生函数恰好为零。这些是数值算法反例，不是独立星历或出生记录。

每个接触的`exact_residual`用十进制字符串保留分子／分母，`phase_arithmetic_method`明确所用方法；紧凑`cycle_summary.arithmetic_scope`解释其精度边界，完整回执重放也检查这些字段及说明。该次数值复核对应周期子规则1.2.0。完整结果与验收过程见周期角度复核（本地数据：`validation/human-design-cycle-phase-verification.json`）。原有多触结果、原典起点／首末触分歧、未认证连续穷尽与未分配第六线阶段的状态均保留。

凯龙星另需操作员安装Swiss小行星文件；它不加入本命13激活。其原始返回旗标描述Earth／修正计算所用后端，不能把Swiss小行星轨道误称为JPL行星内核或Moshier解析轨道。缺文件、超出文件范围、搜索中发生后端切换时保留`unavailable`／`partial`、已观测接触及原因；不填零度或教学年龄。来源配置变化仍触发共享一致性错误。

固定样例1980-01-01 00:00 TT中，土星首轮一次交会，天王星对冲和凯龙星首轮各三次。将评估时点设为2029-07-01 UTC，会返回凯龙星`between_observed_contacts`；不会替原始教学指定首触或末触为唯一阶段边界。[原始词典](https://jovianarchive.com/pages/human-design-dictionary)的天王星对冲条目明确以出生位置为原点；该出生epoch与人格侧的对应另依据出生／设计计算定义，不能外推为其他回归的原点或逆行首末触优先。当前周期子规则1.4.2在完整`cycle_context.bodies[*].origin_source_evidence`逐项列明来源，摘要也区分这项明文与土星／凯龙星原点及全部多触优先性的未定状态，见周期原点来源复核（本地数据：`validation/human-design-cycle-origin-v2/README.md`）。所有数值交会保持，第六线阶段继续不作唯一分配。传统阶段顺序也不表示已测量的成熟度、健康或未来事件。

1.15.0的初始独立核对预先固定1980、2000、2020年元旦三个TT出生时刻，以DE440与另行取得的JPL Horizons凯龙星SPK，使用CSPICE几何状态和Skyfield视位置独立寻找根；25次接触及顺逆行顺序全部吻合。九组样例同一时刻黄经在原先固定2″门槛内，独立根处的角度残差在4″门槛内；仍保留凯龙星最多约374秒的时刻差，不授予秒级时刻认证。另有六个Horizons quantity31固定位置核对SPK21适配过程，最大差约0.0911″。这是一组有限的天文验证，不能证明原典阶段取舍或现实预测。

1.16.0补充逐点文件上下文：`cycle_context.source_evidence`保存原生槽0／1的行星与月亮上下文，并为凯龙星单独保留槽2的小行星轨道；每个`evaluation_witnesses`条目都有对应的`evaluation_source_context_indices`。文件记录保留SHA-256、DE版本、有效范围与是否吻合固定官方清单，不以安装目录中“有文件”推定实际用到了该文件。Moshier计算不冒领残留的行星槽；凯龙星的Earth计算为Moshier时仍须保留其Swiss小行星文件。

批次检查路径策略、文件身份与版本；每次原生计算检查文件签名，结束时再次读取并核对文件哈希。发现文件字节、路径或同角色DE版本发生变化，返回明确的`ephemeris_source_inconsistent`，而非继续拼接同旗标下的不同数据。原先三种变动均可在旗标仍为Swiss时被接受，回归已保留修复前失败。后调用文件槽只是观察到的上下文，不是完整原子读取集合；`atomic_file_read_proven`与`accuracy_certified`继续为`false`。

周期出生基准在原始人格激活计算时直接捕获，包含当时实际位置、速度、旗标和来源索引。1800年端点中，清空原生缓存后重算同一TT曾出现微角秒级差异，使先前的精确校验误拒绝结果；现在复用真正用于本命激活的原始计算，不扩大相等容差、不替换出生黄经。参考时刻换算、长时间搜索及后端比较仍各自保持原有职责。

本机原凯龙星文件是2023年DE431版本；按仓库已有固定提交的官方清单，已升级并补齐`seas_12.se1`、`seas_18.se1`、`seas_24.se1`。旧文件在`.fatebridge-ephemeris-backups/<SHA-256>/`保留并复核。使用同一份未改动的JPL参考，最大凯龙星交会时刻差从约374秒降至约286秒，仍不认证秒级时刻。此变化来自数据版本，文件检查本身不提高轨道精度。原374秒结果继续留在上轮记录中。

其他安装可显式获取相同文件，计算过程不会自动下载：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe \
  --files seas_12.se1 seas_18.se1 seas_24.se1
```

1800年初的设计根及2399年出生后65年的周期搜索还需相应的行星／月亮分段。缺段时不填教学年龄或零度。本轮来源变动、数据升级、原始出生基准、边界与协议复核见周期文件来源复核记录（本地数据：`validation/human-design-cycle-sources-verification.json`）。

CLI调用示例（REST与MCP使用相同字段）：

```bash
uv run --locked --extra dev fatebridge human_design \
  --birth-year 1980 --birth-month 1 --birth-day 1 \
  --birth-hour 0 --birth-minute 0 --birth-timezone UTC \
  --cycle-reference-datetime '2029-07-01T00:00:00Z' \
  --fields profile cycle_summary validation --strict-fields
```

`cycles`证据卡给出紧凑摘要；需要完整JSON时首次`fields=null`，再读同一run的`result_delivery`，按`next_offset`读至结束并核对SHA-256，不重算全文。当前可选周期摘要另声明`summary_format=human_design_cycle_summary_compact_v1`：`contact_defaults`给出省略的重复UTC状态，`motion_evidence_defaults`声明原生速度与搜索段方向的默认对应；逐条例外显式保留，`segment_phase_trend=null`表示未知，不能当作方向一致。每条交会的TT、民用标签、原生运动、区间宽度与残差仍在摘要中；完整坐标见证及原有约定全文见同次`cycle_context`和`summary_conventions`。此格式独立于本命1.39.0与周期1.6.0计算版本，旧格式完整回执仍按原条件核验。原8192字符两项失败在原测试不变的条件下通过，但较大摘要仍须按实际`result_delivery`分页，不能以此认证全部原典或完整解释。见摘要语义与传输复核（本地数据：`validation/human-design-cycle-summary-v1/README.md`）。作者、来源事实散列、星历口径、失败案例及三端／安装包复核见周期复核记录（本地数据：`validation/human-design-cycles-verification.json`）。

## 通道回路与整合结构

`bodygraph.circuitry`仅统计完整定义通道，按实际通道列出回路主题与群内数量：Individual为赋能，Collective为分享，Tribal为支持；Integration四通道作为子集另列，同时计入Individual群，不当作第四大回路群，也不从数量推断主导人格、能力等级或现实结果。主题依据为[官方回路说明](https://jovianarchive.com/pages/what-is-circuitry-in-human-design)。

规则集1.12.0修复此前将Integration排除在三群计数之外的问题。[官方词典Individual词条](https://jovianarchive.com/pages/human-design-dictionary)明确包含Knowing、Centering与Integration；[官方回路概览](https://jovianarchive.com/pages/what-is-circuitry-in-human-design)也将Integration列在个体群中。单列拓扑不等于排除群归属。10、20、34、57四门齐全时仍是6条完整通道，其中4条为整合；个体群应为6而非2。三群数量之和应等于完整通道总数，整合小计已包含其中，不能再加一次。全部36通道的条件性群计数为15／14／7；这是图结构枚举，不是可实现的某人出生盘或能力测量。

`bodygraph.circuitry.group_membership`保留所采用的群归属来源和参考散列；`source_consistency.circuit_group_memberships`只验收回路至群的映射，不会把其余30条通道的弱推断升级。新[事实参考](../src/fatebridge/data/human_design/circuit-group-2026-reference.json)由[独立提取器](../scripts/build_human_design_circuit_group_reference.py)核对公开页面，不导入计算器。完整修复及三端／安装包记录见群归属复核记录（本地数据：`validation/human-design-group-verification.json`）。

原实现误把20–57归入Integration。根据[官方通道说明](https://jovianarchive.com/blogs/chart-interpretations-components/keynoting-stephen-kings-design-part-2)，Integration四通道是10–20、10–57、20–34、34–57；同四门之间另外还有10–34（Centering）和20–57（Knowing）。2001版原典57门在PDF第118页说明其连接喉中心属于Knowing的直觉通道，与此次修正相符。四门齐全意味着六条连接，而不是六条Integration。此项修正不改变中心连通、类型或权威的判定。

`source_consistency.channel_classifications`区分6条直接列明的分类与30条由原典两端门标签相同所作的推断。后者的证据较弱，不能称为36条通道分类均通过独立原页复核。[冻结事实索引](../src/fatebridge/data/human_design/circuitry-2026-reference.json)独立摘录来源，不由通道实现表生成，也不采用来源文章的名人事后归因、健康或现实预测断言。

规则集1.21.0另加[扫描页事实](../src/fatebridge/data/human_design/circuit-pages-1996-reference.json)：署名Ra Uru Hu、1995年版权、Chaitanyo于1996年11月修订的《From the Book of Letters》，从[公开镜像](https://www.barlenoble.nl/_downloads/2d09d9adaf77b157456f399f0e067b41)取得。七张通道列表逐页目视核对，36项分类与实现一致；原6项官方直接分类和30项端点推断检查未替换。`archival_channel_pages`是本扫描本的直接观察，不是出版方母版认证，也不证明全书一致。两处OCR将57识成51，原OCR数字与图像读数分别保留。[构建器](../scripts/build_human_design_circuit_pages.py)校验原PDF、冻结目视事实及OCR差异，不导入计算引擎，也不自动将OCR改成实现期望值。

新增观察还保留一项未解决标签分歧：扫描PDF第76页、印刷第69页的防御回路“Motors”列出Root／Solar Plexus，但同页通道59–6、27–50的端点按既有2001中心事实对应Sacral／Solar Plexus两种运动中心。原标签不改写，不据标题额外定义Root或Solar Plexus，也未取得出版方勘误。例如只有27–50时，实际定义Sacral与Spleen，类型仍按这条真实连接计算。当前资料只支持这一结构性比较，不认证原书的生物、健康或现实作用解释。

`bodygraph.circuitry.topology_completion`按六个回路与单列整合拓扑分别返回所需、已定义及未定义通道集合。单一定义描述中心群连通；只有4–63时虽为单一定义，逻辑回路仍只定义1／7条。10、20、34、57四门齐全会定义6条通道：整合拓扑的4条齐全，相邻10–34与20–57仍分别属于归心与知晓，不能据此宣称六个回路都齐全。缺项只是集合差，不自动指定要寻找的人或行动。

`interpretation.circuit_topology_meaning`逐项解释本盘七组集合、来源身份与标签分歧；完整核验重建这些字段和文本，`checked_circuit_topology_count=7`。824组由源通道子集构造的门集均以独立门对存在条件核对，包含整合共享门的交叉成通道情形。`topology`证据卡提供该结构及来源限定；完整过程见拓扑与扫描页复核（本地数据：`validation/human-design-circuit-topology-verification.json`）。完整384线线义与自由文本语义验收仍未完成。

追问回路时使用`circuitry`证据卡；该卡保留本题通道汇总、带版本标识的方法、来源URL与事实参考散列、6／30来源层级及当前印刷差异影响，完整作者和全局规则集保留在完整run中，避免在任务卡重复所有无关主题的来源；`interpretation.circuitry_meaning`与逐句`circuitry`说明绑定实际通道和汇总。没有完整通道时明确保留激活单门，不生成固定回路主题或能力缺陷判断。

分类与解释复核记录（本地数据：`validation/human-design-circuitry-verification.json`）保存修正前后的来源审计、针对性与Linux检查、黄金快照差异审阅，以及尚未完成的专业验收。

解释为字段绑定的简要中文释义，实际依据在 `rule_trace`、`rulesets`、`gate_evidence`。同次结果引用可由[结构化引用核验](../src/fatebridge/validation/claims.py)核对，不能把该核验说成所有自由文本的语义认证。

## 新增193盘的完整结构与解释核对

规则集1.22.0另按预先冻结的计划（本地数据：`../tests/fixtures/human-design-cross-coverage-plan.json`）核对193个新官方整盘（本地数据：`../tests/fixtures/human-design-official-cross-charts.json`）：1980年的64个人格太阳门分别各取右角、并置和左角，另取按顺序搜索的首个四分定义。全部输入在读取新官方结果前固定，属于实现参与选取的结构覆盖，不是盲测人群。原19盘、494个门线和15项名称失败均保持不变。

新193盘的5018个门线、UTC、完整图、类型、权威、定义、角色、四门及角度、Variable和策略均一致；含五种显示类型、四个四分定义。新增名称只有107项字面一致，86项仍失败，编号和旧拼写不做别名归并。全192个门角组合各有一次观察，不代表每种角色／生时组合、1800—2399全时域或细分边界均已认证。

页面观察事实（本地数据：`../tests/fixtures/human-design-cross-coverage-observations.json`）保留26个激活、已定义通道和中心；下载PDF的13项属性文字独立提取并逐盘核对，只规范空白。PDF激活图是图像，文字提取并不构成门线的第二个独立读取。原PDF仅本地保存，目录记录SHA-256；转录校验不等于来源或天文真实性认证。[构建器](../scripts/build_human_design_cross_coverage.py)从这些事实及原PDF生成参考，不导入计算引擎，也不从计划中的实现诊断生成期望值。

`source_consistency.expanded_cross_name_comparison`单独返回同四门、同角度的新官方标签与源PDF散列；`incarnation_cross.name`继续采用2001版，原19盘的比较仍单列。`interpretation.expanded_cross_name_meaning`逐盘解释名称是否字面一致；完整核验重建该说明、来源及未达标状态。193盘均执行完整固定模板核验，仍不认证384线全文或任意自由文本。

1.30.0增加`primary_diagrams`视图与`source_consistency.primary_transcript_diagrams`。新核看的公开《Incarnation Crosses by Profile》转录本中，[卷二PDF第105页、印刷第95页](https://s3.amazonaws.com/kajabi-storefronts-production/file-uploads/sites/71623/themes/2152708825/downloads/70163f-880f-aa8c-b68-620a7ce376c1_Incarnation_Crosses_by_Profile-Quarter_2.pdf)标出Identification 1的16/9｜63/64；[卷四PDF第93页、印刷第83页](https://s3.amazonaws.com/kajabi-storefronts-production/file-uploads/sites/71623/themes/2152708825/downloads/04baf1-21e5-a374-d186-bfd72ccede3_Incarnation_Crosses_by_Profile-Quarter_4.pdf)标出Identification 2的9/16｜64/63。四门按人格太阳、人格地球、设计太阳、设计地球排列；文本坐标提取与图像核对分别保留，见[事实目录](../src/fatebridge/data/human_design/primary-diagrams-2008-reference.json)与[独立提取器](../scripts/check_human_design_primary_diagrams.py)。

两份公开副本均声明未经校对，尚未认证为出版方母本；所取图均在5/1段落，不能据此补写其他角色或完整线义。仅当实际有序四门与左角度完全相同时，解释才追加带页码、散列和这些限定的`primary_transcript_diagram`；其他盘保留未观察状态。2001名称、原19盘及新增193盘的所有字面失败仍保留，不把图示旁证称为官方16/6课程列项的勘误。验收见原典图示复核记录（本地数据：`validation/human-design-primary-diagrams-verification.json`）。

还有一项来源冲突：[官方课程页](https://jovianarchive.com/products/intermediate-2-profiles-lines-and-incarnation-crosses)两次将Identification列为16/6｜63/64，而冻结的左角16门官方整盘为16/9｜63/64。课程列项与日地对宫关系不符；两个原记录都保留，未取得出版方勘误，不据课程列项改写实际激活。

2026-10-23的一手来源复查（本地数据：`validation/human-design-source-recheck-2026-10-23.json`）仍观察到课程页与独立产品页的同一列项。出版方公开样章仅含目录及印刷正文第3–4页；目录列出的Identification正文第36–39页并未公开，不能据目录推断勘误，也不能把Eden示例当成争议样本的验收。原2001名称、29门分界和所有失败案例继续保留。

`cross_sources`证据卡保留本盘四门、完整新增来源比较、完整新解释和未达标状态；原19盘及29门印刷分界明细仍可读取既有卡和同次完整run。首轮摘要的`source_summary`保留作者、规则版本、原典与官方样本URL、原范围声明及未验收状态；完整`rulesets`及所有主题来源仍在完整run中，避免首轮重复全部URL。两个层级均由完整回执核验，不删减来源验收要求。

全部失败、数值门槛、三端及安装包证据见扩展交叉覆盖复核（本地数据：`validation/human-design-cross-coverage-verification.json`）。

## 原典与未决分歧

数值核对采用 Ra Uru Hu 著、Jovian Archive Corporation 2001年版 [The Complete Rave I’Ching](https://www.myhumandesign.be/downloads/Rave-I%27Ching.pdf)。这是作者原始著作的公开托管副本；出版信息在PDF第3页。另核对官方2016年手册及公开机制文章，来源清单（本地数据：`../tests/fixtures/human-design-sources.json`）保留下载散列。未把全部解读文本复制进代码或数据。

[冻结的数值摘录](../src/fatebridge/data/human_design/rave-2001-reference.json)由独立脚本直接提取PDF，不导入计算器。64门范围、64门中心、36通道端点均一致；384条线界中382条与统一等分吻合，29门1线终点及2线起点两条记录存在分歧。原书PDF第63页将狮子座25°16′15″写作共享界点；统一56′15″线宽给出25°26′15″，相差10′。已对书影目视复核。

实现明确采用统一六等分，原典印刷值原样保留在 `source_consistency.discrepancies`，没有改参考值使审计全绿。这可能是印刷错误，但尚无经核验的官方勘误；故 `classical_acceptance_passed=false`，不声称符合全本。书中的全部线义尚未实现；现已提供384线的极性星体事实索引及192个角度对应的交叉名称；数值表一致不替这些内容验收。

另找到New Sun Services America于1999-07-04刊出的[原始通讯勘误](https://humandesignsystem.com/archive/newsletters/0602.pdf)：PDF第1页将62门第3线的固定星体由Mercury更正为Venus。现有2001版事实目录已将其落陷星体记为Venus，本轮没有改动该值。这份历史勘误只佐证这一项，未涉及29门角度，不能据此关闭29门分歧；文件散列与核对范围保存在本轮来源追查记录（本地数据：`validation/human-design-time-policy-verification.json`）。

`source_consistency.activation_impacts`逐一检查当前返回的26个激活黄经；若位于受分歧影响的区间，列出实际位置、统一等分线号和原书印刷线号。例如黄经145.35°在实现中为29.1，而印刷表为29.2。未受影响只说明当前数值位置相同，不能把全书未决问题改成通过。

已另取得官方手册 [Discover Your Design](https://s3.amazonaws.com/static1.jovianarchive.com/DiscoverYourDesign-The3StepstoTransformation-JovianArchive.pdf) 的乔布斯示例盘（PDF第7页，印刷第6页），逐项目视冻结26个门线、三条通道及类型／权威／Profile。以声明的名义出生时刻1955-02-25 03:15 UTC计算，真交点26/26一致，平交点有4个交点线号不同。手册未印出生钟，名义出生资料本轮没有独立核实；这只是有条件的单例对照（本地数据：`../tests/fixtures/human-design-official-example.json`），不认证实际出生资料或普遍交点口径，更不属于现实预测样本。

最初按采集前固定的8组虚构冬季输入，通过[官方公开计算器](https://jovianarchive.com/pages/get-your-human-design-chart)正常交互生成PDF；不填邮箱，不使用返回401的直接接口。源图明确回显当地时间与UTC时间，包括1971年英国冬季的UTC+1。原8组观察值（本地数据：`../tests/fixtures/human-design-official-charts.json`）保持不变，原始采集记录见Variable复核（本地数据：`validation/human-design-variable-verification.json`）。

随后先冻结11组分支覆盖输入（本地数据：`../tests/fixtures/human-design-authority-plan.json`），再正常交互采集独立官方观察值（本地数据：`../tests/fixtures/human-design-official-authority-charts.json`）。这11组由本地引擎有限扫描选择，专门补齐稀有分支，不能称为盲测或总体准确率研究；计划中的引擎诊断值不充当官方期望值。合并19组覆盖5种显示类型、8种权威标识、12种角色、16种Variable、3种交叉角度，以及无定义、单一定义、二分及三分定义。494项门线和所列盘面结构在Swiss文件后端吻合；四分定义、全部交叉家族和细分天文精度仍未由这些例子认证。Moshier的2000年Variable分歧继续保留为失败。

新增字面名称核对保留15/19项差异：2001原典的变体编号、`CONTAGEN`、`MAIA`及`UPHEAVEL`，与当前官方显示名称存在不同。只规范大小写及空白，不删除编号、不改写原典或暗设别名，因此含字面名称的完整官方对照仍为失败；机械结构匹配另列。PDF散列、转录复核、采样方法及失败项见权威分支复核记录（本地数据：`validation/human-design-authority-verification.json`）。

`bodygraph.classification_evidence`返回权威优先序实际检查过的中心、已定义中心、每个可达动力中心到喉中心的一条确定性最短路径，以及选中权威的连接依据。仅使用本次已完整的通道，悬挂门不能补成路径。[官方意志显化说明](https://jovianarchive.com/pages/ego-manifested-authority-in-human-design-the-will-that-speaks)明确允许21–45直接连接，也允许51–25经G中心的间接连接；本轮官方例子同时覆盖两种。心理投射者可仅定义头顶／逻辑中心，不能额外要求喉中心已定义；无内在权威与反映者月亮过程分别保留。`interpretation.authority_structure`解释本次实际依据，`authority`证据视图可直接读取这些字段。

规则集1.17.0新增[来源版本事实](../src/fatebridge/data/human_design/source-variants-2026-reference.json)及[独立提取器](../scripts/build_human_design_source_variants.py)：重新从原书提取384条线界的整数角秒，不通过已舍入的十进制角度还原印刷边界；分类仍采用实际激活的精确有理黄经和半开区间。原有2001版目录、19个官方盘及失败记录均未修改。官方词典的[Profile Foundation词条](https://jovianarchive.com/pages/human-design-dictionary)明确每线56′15″；印刷29.1为46′15″、29.2为66′15″，各偏10′。该明文规则支持等分计算，不能代替出版方对2001版的正式勘误。

`source_consistency.version_comparison`保留全部19个名称观察：4项字面一致，12项为当前标签未显示原编号，3项还存在不同拼写。`cross_name_comparison`只展示冻结样本中四门与角度均相同的官方标签和原PDF散列；未观察的组合返回`not_observed_in_frozen_cohort`。编号、省略和拼写只用于诊断，不成为别名或通过条件，严格整盘对照仍保留15项名称失败。

`activation_impacts.conditional_printed_line_effects`将本盘所有印刷线号差异同时代入26激活的线固定，再列出实际变化和人格／设计日地是否同线。固定回归输入2000-08-18 00:00 UTC中，人格太阳按等分为29.1，按印刷为29.2，而地球仍为30.1；因此不生成一个2/3替代角色。线界分歧没有给出另一套Color／Tone／Base定义，相关替代值保留`null`，`full_alternative_chart_computed=false`。这项条件比较不改变主盘、星历坐标或默认名称，也不宣称天文误差减小。

`interpretation.source_discrepancy_meaning`及新增第八条`source_discrepancies`将上述影响写入同次固定解释；`grounding`视图同时保留其`source_consistency`依据。原有七条解释继续全部核验。重新计算业务哈希后，删除冲突、改造角色、清空固定差异、接受虚构别名或删除第八条也必须被拒绝；该验收覆盖固定模板，384线全文及任意模型自由文本仍未验收。复核记录见来源分歧复核（本地数据：`validation/human-design-source-variants-verification.json`）。

## 线极性与可核验解释

[深度事实目录](../src/fatebridge/data/human_design/rave-2001-depth.json)由独立提取器读取同一原典书影，保存64门、36通道、192交叉名称及384线的极性星体，不复制线义正文。375条线有双极性，另9条不补造缺失的极性；54.4没有极性星体。375条双极性的数量另与[Ra 1997年问答](https://humandesignsystem.com/archive/newsletters/0402.pdf)核对。

本命固定采用[官方公开的同门／谐振门规则](https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition)：指定星体可直接激活本线、同门的其他线或通道另一端，且须保留两侧每个实际触发位置。两极同时有触发则返回 `juxtaposition`，不以顺序覆盖。该公开文章署名Ryan Hanna，不能当作2001年原书逐线解释。极性不是优劣或能力分数，也不等同于西占的行星星座尊贵。官方乔布斯示例盘中的5个箭头仍保留原样验收，包括同门其他线和谐振门触发。

[署名资料复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-primary-fixing-source-audit.md)另以IHDS2024年Lynda Bunnell说明核对两项11.4星体事实及14项披露的开发组合，保留原2001正文附加金星依据；公开Ra音频只作为带散列和时间位置的待复核线索。它不认证全部384线，也不改变既有失败和验收标准。

规则集1.19.0修复了交点接受固定的缺口。[1997年6月30日通讯](https://humandesignsystem.com/archive/newsletters/0402.pdf)第2页Martin Grassinger的文章说交点不固定其他线，限制的是主动固定角色；不能由此推出交点位置不能接受行星固定。这段话此前误注为Ra，现已纠正。原有19份官方PDF中有11个交点位置带可见极性标记，例如1971年样本的设计北交点55.2，由人格地球39.1在谐振门触发下降极性。现在交点作为接受位置参与计算，仍不充当固定星体。

`polarity_kind`保留2001原典类别，`fixing_state`另给本盘实际触发状态。8条单极性线不因类别而自动算作已触发；54.4原典未列极性星体，返回`not_applicable_no_planet_polarity`，不补造第二极。为兼容既有类别，单极性的`status`仍为`unitary_polarity`，应以`fixing_state`读取实际触发。26项`line_fixings[].reading`分别解释原典指定星体、实际触发的侧别／门线／关系及字段路径；`fixing_summary`计数，`fixing_policy`明确角色和来源作者。联合变体的`fixing_state_changed`也能表示单极性类别不变但实际触发变化。

[可见标记事实](../src/fatebridge/data/human_design/fixing-2026-reference.json)由[独立提取器](../scripts/build_human_design_fixing_reference.py)从全部19份未修改PDF的原始激活栏图片取得，按比较前冻结的颜色、连通区域和三角方向方案提取，无计算器导入。494位置中138个可见极性全部匹配，包括11个交点和2个实际触发的单极性位置；修复前的138项比较及13项缺口（本地数据：`validation/human-design-fixing-before.json`）保留。494个显示投影全部匹配也不能认证494个完整固定状态：356处无可见标记，官方公开渲染器的组合符号缺少对应图形，空白无法区分未固定、两极固定等状态。完整固定状态和384线全文语义验收继续为未完成，原有15项名称失败与29门线界冲突没有删除或改为通过。

紧凑`fixing`证据视图提供实际计数、方法及解释摘要；逐项机制读取`depth`或同次完整结果。固定机制说明不等于完整线义。复核命令及完整测试记录见固定机制验收（本地数据：`validation/human-design-fixing-verification.json`）。

`interpretation.statements`将类型、权威、定义、回路、Profile、Variable、交叉及来源分歧八条说明各自绑定到字段路径、原值与来源。1.24.0保留这八条，另增加交点比较说明；闰秒盘还包含出生钟说明。`verify_human_design_reading`核验完整run的回执、逐句文本、黄经分类全部派生字段、四箭头、类型／权威、回路、Profile、交叉及固定依据；也核对来源记录、规则路径和验收声明。地球及南交点逐项绑定同侧实际来源，按派生前精度重建分类。修改文字、Tone左右向、四箭头引用、对点来源或认证标志，即使重新计算业务哈希，也不能绕过内部关系检查。它严格验证固定模板，不把未约束的模型自由文本自动认证为忠实。

规则版本1.14.0还逐项重建生时、交点口径和后端比较中的联合快照，核对门线、八个Variable Tone、角色结构、完整桥接方案、固定依据及摘要；整盘参考的黄经分类、对点来源、图结构、太阳弧及摘要也须吻合。此处核验的是投影内部数学关系，不认证投影真实出现于声称的TT时刻；见证的天文位置仍需按同一星历配置重放并独立复核。

1.24.0补齐交点比较报告本身的核验。此前更改角秒差、所选／参考黄经、返回旗标、TT、约定标签，或删除变化列表后重新计算哈希，12个有效探针仍会通过；另一个探针因路径写错没有实际测试，原始记录也保留。现在两项比较分别保存`reference_node_positions`，每侧记录原生北交点黄经、速度、返回旗标和实际TT，由该见证精确派生南交点、细分、四箭头、图结构及整份报告。真实不可用、平交点解析模型和严格JPL下未执行的节点后端对照以`reference_node_positions=null`表示，不补坐标。完整核验无需重新调用星历；它只验证所提供见证的内部关系，不能认证调用真实发生、失败实际发生或见证是真实天空位置。

`interpretation.node_comparison_meaning`按实际约定、细分变化和后端状态生成说明：有完整对照时给四项节点的最大观测差，同为Moshier时不称独立验证，缺项不说成一致，平交点不把旗标切换当作独立模型。`nodes`证据卡保留两项比较的原生见证、完整细分变化、四项后端差值表和说明；在8192字符预算内若仅环境元数据过长，可按`result_delivery`读取同次run的`run_metadata.runtime`，不能重算另一run替代。全部联合结构和完整JSON也从该run读取。复核过程、首次失败及保留的旧案例见交点比较验收记录（本地数据：`validation/human-design-comparison-verification.json`）。

### 返回旗标、实际模型与坐标口径

1.14.0补上主盘来源核验的缺口：每侧13个激活的实际模型须与原始`return_flags`相符；真／平交点的计算模型和节点原始旗标标签分别检查。地球、南交点的速度与模型来源须与同侧来源严格一致，物理后端摘要、非物理因子映射、强制Swiss文件及严格JPL策略也须相容。此前七种来源／速度／策略矛盾在重新计算业务哈希后仍可被误判为通过；回归保留旧结果，新增检查逐项拒绝这些矛盾。

[Swiss编程文档3.3与3.5节](https://www.astro.com/swisseph/swephprg.htm)说明实际返回旗标可能不同于请求，速度需明确请求，其他旗标可改变坐标、参考系或目标。计算入口现在要求唯一后端，并拒绝未声明的赤道、弧度、日心、地表、恒星黄道、J2000、系统中心目标等旗标；激活计算还须返回SPEED旗标。太阳弧求根不需要速度，但仍检查坐标口径。此处拒绝的是与当前规则集不符的结果，不是说这些Swiss选项本身无效。

`calculation_policy.position_frame_scope=physical_bodies`明确视位置描述的适用范围；`lunar_node_frame`另标数学交点的地心、回归黄道、当日参考系。平交点没有可观测的物理视位置，不能把它与行星视位置混为同类。紧凑`ephemeris`证据卡提供口径，原始旗标仍读取同次完整结果。旗标相容不证明坐标真实由该后端算出，不认证速度精度、出生钟或任意自由文本；完整回归与失败过程见来源口径复核记录（本地数据：`validation/human-design-provenance-verification.json`）。

### 本命与设计根的文件身份

1.26.0将文件一致性检查扩至普通本命盘、设计时刻太阳求根、出生时间范围、交点口径与后端对照；不再只在显式周期搜索中检查。固定的原始三项探针（本地数据：`validation/human-design-natal-source-before.json`）保留了原生库已拒绝的损坏文件案例，以及旧1.25仍会接受的临时切换后恢复路径、DE元数据变化；另有主盘算完后改变文件（本地数据：`validation/human-design-natal-source-late-before.json`）的接受案例。四项均用独立副本保留，变化会返回不可自动重试的`ephemeris_source_inconsistent`，不向调用方暴露私有文件路径。

`ephemeris_source_evidence`记录每次原生位置调用后的文件上下文：文件名、SHA-256、DE号、数据范围与所见作用、天体、原始旗标模型、实际调用次数和TT包络。所有已识别文件在结束时重新核对身份与哈希；历法和DeltaT调用不计入该位置次数，周期仍另读`cycle_context.source_evidence`。解析平交点与内置Moshier算法不伪造文件依赖。`ephemeris_source_summary`提供紧凑汇总，`source_files`证据卡从合同读取；完整上下文按同次`result_delivery`取回。

[Swiss编程文档2.6节](https://www.astro.com/swisseph/swephprg.htm)将该接口定义为原生文件结构的调用后上下文。实际部分文件环境可能留下文件名非空、头部为零的失败辅助slot，返回SWIEPH旗标也不足以证明相应月球文件可识别。此类slot在`unresolved_slots`中明确保留，汇总为`identity_incomplete`；不将缺失上下文当作已识别文件。`require_swiss_files=true`同时拒绝这类未识别文件上下文，不能只凭旗标声称文件要求已满足。

文件身份核对不是完整原子读取集合、原生调用真实性、速度或位置精度认证；所列次数不是独立样本数、覆盖率或概率。观测后的首个哈希不能证明首个原生读取之前的文件内容。原有2″／设计根5秒等精度阈值、原典冲突、Moshier超差与所有原有失败均保留。完整验收与开发中失败见本轮文件来源复核记录（本地数据：`validation/human-design-natal-source-verification.json`）。

文件身份检查不能单独排除原生库的进程内状态污染。已冻结的Delta‑T探针（本地数据：`validation/human-design-native-state-before.json`）显示：相同文件、相同输入，在父进程预设0.1日固定Delta‑T后，1800与1900年出生TT分别偏移约8621.5秒、8641.7秒，门线细分也会变化，旧解释核验仍可通过。1960与1990年作为原始控制输入保留；该人为覆盖值不是实际测得的Delta‑T。

1.27.0把出生历法换算、设计时刻求根、26激活、交点与后端对照、范围采样及可选周期搜索放在同一独立原生进程。父进程只锁定配置；不重置调用方的固定Delta‑T或潮汐加速度，也不继承其旧辅助表缓存。当前路径中的`swe_deltat.txt`、`sedeltat.txt`及`seleapsec.txt`候选在父、子进程的端点分别核对，变化返回不可自动重试的来源错误。旧文件故障仍在独立开发进程中注入并检查，没有把父进程补丁传播到生产计算。新增状态隔离检查与整体验收进度见生产整合记录（本地数据：`validation/human-design-native-state-verification.json`）；原实验记录（本地数据：`validation/human-design-native-state-experiment.json`）保留其历史范围。

`native_execution_context`及`native_context`证据卡回显实际操作边界、辅助文件候选身份和压缩文件端点诊断。文件列项是候选身份，动态次数与记录是诊断声明；均不能认证原生执行真实性、完整内部调用集合、原子读取、物理精度或现实预测。完整记录过长时，读取同次`result_delivery`并核对SHA-256。

1.28.0进一步隔离可选周期参考时间的请求校验。原12组探针（本地数据：`validation/human-design-cycle-input-before.json`）保留了合法／非法输入与未变控制：1.27在父进程固定DeltaT后，会误拒绝1959年末出生、1960年初评估的合法请求，也会在相反次序上误放行；部分请求还会重置调用方的潮汐加速度。请求层现在在独立短进程中执行原有TT次序比较，完整计算仍在自己的进程内再次校验，未改成按民用字符串排序。两次操作各核对当前辅助文件候选；请求校验中的来源变化仍是503来源错误，不被Pydantic包装成出生参数错误。原输入、无时区及早于出生等拒绝条件均保留，进度见请求时标复核记录（本地数据：`validation/human-design-cycle-input-verification.json`）。

1.29.0补上普通时标回执缺口（本地数据：`validation/human-design-ordinary-clock-before.json`）与非名义样本UT1漏检（本地数据：`validation/human-design-interval-clock-before.json`）。`clock_evidence`记录本次工作进程实际完成的民用钟转换、四次DeltaT逆迭代的输入／原生旗标／返回值，以及TT到UTC的实际显示标签；重复记录去重。核验器纯回放这些记录，同时检查出生输入、固定时区规则身份、历法／太阳钟策略、方法与未来闰秒假设，覆盖主盘、设计时刻、整盘后端对照和全部实际生时样本。周期参考与交会标签也改用这些见证核验，不再为验收重新调用原生时标转换。原九项探针与重建整份区间后的反例均保留，连同新增设计／对照／周期／见证篡改共25项；记录见时标回放验收（本地数据：`validation/human-design-clock-replay-verification.json`）。

民用标签与TT核对仍使用原0.0002秒阈值；四次DeltaT迭代逐步精确回放，未扩大物理天文2″、设计根5秒等阈值。Swiss将1972年前输入按UT1处理，FateBridge继续显式使用SOFA的1960与IERS的1961—1971 UTC漂移表；更早标签沿用历史UT1约定，原生TT返回作为见证保留。[Swiss编程文档9.2—9.3节](https://www.astro.com/swisseph/swephprg.htm)说明了TT／UT1返回顺序与历史输入约定。公开出生年份仍为1800—2399；2600年仅作为内部引擎及周期参考的边界控制。

转换见证来自被核验结果，能检查内部矛盾，但不是数字签名、独立原生执行认证、实测UT1或物理精度证明。若调用方同时伪造一整套自洽记录，纯本地回放不能证明其真实性；仍需保管可信原始回执。全部原典冲突、缺页、独立精度超差及现实预测缺少实证的问题继续单列。

调用方应保管可信的完整原始结果；哈希本身不等同于数字签名或计算来源认证。可对该结果执行：

1.31.0修复参考输入在单个双精度TT儒略日内的先后判定。冻结反例（本地数据：`validation/human-design-reference-order-before.json`）包含23个输入、原先7个错误判定，原有12组跨时标／污染控制与九项普通时标、区间重建反例继续保留。请求和完整领域计算都在源定义的连续TT有理数上核对：1972年后使用冻结TAI−UTC，1960—1971年按原表十进制系数和完整微秒日分数计算，更早输入继续使用历史UT1与本次实际原生DeltaT。正闰秒保持独立标签；小数秒超6位显式拒绝，避免datetime静默截断。`cycle_context.reference_ordering`保存两侧来源、精确分数、物理TT与先后关系；`cycle_summary.reference_ordering`保留摘要，完整核验纯回放并检查原始参考输入。星历坐标、TT求根与周期接触关系仍使用原双精度TT，输入分辨率不等于出生记录或物理时刻精度。见参考顺序验收记录（本地数据：`validation/human-design-reference-order-verification.json`）。

1.32.0补齐实际设计激活的数值根端点比较。七个冻结输入（本地数据：`validation/human-design-root-body-before.json`）使用公开接口可表达的整秒出生时刻：三例月亮跨门、四例跨Base，其中1999-02-28的候选结构会改变生产者子型。原先的太阳函数端点细分仍保留；现在另对实际SPEED位置逐项推导全部13项设计激活、通道及其来源、中心、类型／子型、权威、定义、角色和Variable。所选端点复用原始设计激活，另一端点实际计算，重复TT只记一次；新求值在文件来源层标为`root_bracket_activation`。当前主盘仍按原最小太阳弧残差选根，不按候选结果改变主盘。

`design_solver.numerical_precision.design_body_endpoint_assessment`保留原生黄经、速度、旗标及候选结构，`root_endpoints`视图读取其摘要。完整原始结果核验不再调用原生计算；整盘后端参考和每个实际生时样本也保留自己的设计根与端点见证，样本格式升级为`human_design_all_evaluated_sample_scalars_v2`。固定说明逐盘描述实际差异，不能把一个端点的月亮与另一个端点的通道拼成一盘。这些1或2个数值TT端点不是物理误差界；相同不认证连续稳定，不同也不提供现实概率。原天文2″、设计根5秒、时标0.0002秒阈值及全部原失败案例保留。见实际设计端点验收（本地数据：`validation/human-design-root-body-verification.json`）。

原生浮点捕获按平台绑定。macOS与Linux的原版1.31运行会在少量黄经／速度末位上不同，因此原版回归必须与同平台、同数据文件的原版比较；Linux基准由固定原版wheel独立执行七个原输入生成，不能使用新版输出当预期。原macOS捕获、Linux原版捕获及首轮跨平台逐位比较失败全部保留；门至Base变化、结构和原数值阈值不变。

1.33.0将数值根端点验收延伸到解释依赖。预先冻结的七例（本地数据：`validation/human-design-root-interpretation-before.json.gz`）全部保留：1976-03-14的设计月亮12→15门，使未移动的人格海王星5.3从上升极性触发变为两极同时触发；设计月亮自身的触发状态虽然相同，触发星体与依据却不同。1974与1999两例还改变回路拓扑，1999例改变桥接结构。四例仅Base变化的控制仍保留。固定规则按[Jovian的同门／谐振门说明](https://jovianarchive.com/blogs/chart-interpretations-components/line-fixing-in-human-design-exaltation-detriment-and-juxtaposition)核对双侧完整26位置；该2026教学文不是384线原始全文验收或既有原典印刷分歧的勘误。

`design_body_endpoint_assessment.endpoint_interpretations`逐端点保存26项状态、完整固定记录SHA、全部变化记录及其条件说明、完整假设桥接门集、回路拓扑和角色依据。SHA可从同次原始位置纯重建，不能作为来源认证；依据路径均相对该候选盘，不能指向所选主盘或别的端点。角色组合未支持时保留未完成状态。摘要保留人格侧变化数、触发状态变化数、依据变化数及完整门集差异，数量相同不能视为依据一致。实际区间每个样本与完整后端参考均使用自身见证，完整核验覆盖所有层；精度说明逐盘提示解释差异。原最小残差选根、原始坐标、全部旧案例和2″／5秒／0.0002秒阈值保持，完整384线线义、源分歧及现实预测验收状态不变。见端点解释验收记录（本地数据：`validation/human-design-root-interpretation-verification.json`）。

1.34.0将已观测驻点和周期交会细化到函数零值或相邻二进制TT，并从实际端点选择速度／精确角残差绝对值最小者，平局取较早TT。原0.01秒驻点、0.0002秒交会与1e-7度残差上限不变；驻点两侧分别处理，只有同一已观测零值可去重，共享非零端点不合并交会。每个驻点保留完整速度区间、精确目标角残差及未认证连续根数量的标记；每个接触保留两个端点的精确有理数残差。`cycle_summary.numerical_scope`解释这些数值约定，完整核验从全部原始见证重建。周期子规则版本1.3.0。

预先冻结24例（本地数据：`validation/human-design-cycle-station-before.json`）的解析二次曲线各有两个已知根，旧版23例没有返回两次交会。12例返回峰值可以区分，新版全部保留两次交会，修复其中11例；另12例的返回黄经已将峰值量化到目标，数值输入不足以认证解析根数量。后12例的原始二根预期、旧输出和未验收状态全部保留，不能将单个观测零值计作恢复两根。有限搜索仍不认证连续穷尽、物理精度或传统阶段分界。见驻点与交会精度验收（本地数据：`validation/human-design-cycle-station-verification.json`）。

本轮另核对IHDS正式提供的[2005年Life Cycles Analysis学生手册预览](https://www.ihdschool.com/digital-products/8/life-cycles-analysis-student-manual)。取得的预览含目录与开篇，没有完整的相关计算章节；目录标题不能裁定人格／设计起点或首末触优先性，也不能替代该章节全文验收。

2026-10-27另找到公开可读的2005年课程转录副本，包含正文至印刷第142页。它扩展了可读材料，仍未经出版方母本认证。太阳回归的双侧时点说明与凯龙解读时机建议分别按章节限定，不能外推为土星／凯龙取点或逆行首末触算法。检索未找到明确算法不能证明全文不存在该算法，原周期要求保持未完成。见公开原典条款续核（本地数据：`validation/human-design-primary-clause-scope-v1/README.md`）。

1.35.0补上原典正文中的两项额外星体。原[384线符号目录](../src/fatebridge/data/human_design/rave-2001-depth.json)与散列不变；[独立提取器](../scripts/build_human_design_additional_polarities.py)逐页扫描同一固定2001版的384个线段，确认11.4正文另列金星上升（原符号月亮，PDF第27页）、25.4正文另列木星上升（原符号金星，第55页）。[补充事实目录](../src/fatebridge/data/human_design/additional-polarities-2001.json)保存角色、原符号、附加星体、页码、原句散列和来源身份，不保存线义全文。这是两条明确句式的事实提取，不能替代全本文义或出版方母版认证。

同一公开2001版的133页包含384线正文，资料可读与完整审校是两项事实。[新增条款审查器](../scripts/audit_human_design_source_clauses.py)将专名、星体形容词、无极性／无上升／无落陷条款一起纳入候选，保留全部384行与11个候选的页码、块散列及限定审查结果。两条额外星体已由旧实现处理；其余候选没有新增固定触发依据。完整语义审查计数仍为0，要求完整解释时退出1；候选数量不能当作完整线义覆盖率。

固定匹配将这两项与原符号合并，继续核对本命双侧同门／谐振门并排除交点施加固定。只有实际触发附加星体的记录才新增`additional_polarity_basis`与对应条件说明；原`exaltation_planet`仍专指印刷符号，不冒充完整星体列表。375条双极性及9条非双极性分类不变，25.4另列木星不会凭空增加下降极性。`additional_poles`证据卡给出来源及实际接收位置／施加星体路径，完整reading仍读同次`line_fixings`。

六个冻结公开输入（本地数据：`validation/human-design-additional-poles-before.json`）保留原坐标、结构、Variable和旧固定结果：三例2024-11-08金星11.4、两例2022-05-21木星25.4原来未触发，另有一例2022-05-17已由原金星依据触发。新版补齐五例状态及一例附加依据，不把控制删掉；原数值阈值、全部源分歧与完整384线未验收状态保留。见正文附加星体验收（本地数据：`validation/human-design-additional-poles-verification.json`）。

1.36.0按Jovian公开的[Motivation说明](https://jovianarchive.com/pages/the-gift-of-awareness-understanding-motivation-in-human-design)与[View说明](https://jovianarchive.com/pages/seeing-through-your-unique-perspective-understanding-view-in-human-design)，增加人格Color类别：前者取人格太阳／地球，后者取人格交点。两页各列六个类别，[事实目录](../src/fatebridge/data/human_design/personality-color-reference.json)仅保存短类别名、依赖和来源指纹，由[独立提取器](../scripts/build_human_design_personality_color_reference.py)读取公开HTML，不导入计算器。这是当前出版方教学页面的有限事实，不认证原始讲稿全文或心理测量。

`variables.personality_colors`逐项保留实际Color、类别名、人格激活路径与一致对点检查。缺失或对点冲突不生成类别；`observed_transference`、`observed_distraction`、`observed_alignment`均为null。本命计算不能据这些数值断定实际动机、转移或分心。`interpretation.personality_color_meaning`只解释同次类别及实际交点口径差异；`personality_colors`证据卡可按需读取。

两组实现前冻结案例（本地数据：`validation/human-design-personality-color-before.json`）在真／平均交点下全部门线和四箭头Tone相同，人格交点Color却分别为6／5、5／2。因此承载新类别的联合投影升级为`gate_line_tone_personality_color_v2`，保留人格日地／交点Color；不因箭头相同合并这两种解释。过渡状态增加同源Color，太阳与交点的Tone／Color仍各计一个独立依赖，地球与南交点镜像不重复计事件。旧箭头、原始天文坐标和既有失败案例保留；未将所有Color／Tone／Base全组合或连续穷尽列为已认证。见人格Color验收（本地数据：`validation/human-design-personality-color-verification.json`）。

1.37.0统一设计根与实际激活的太阳坐标请求：均采用同一后端的地心视黄道坐标并带`SPEED`，对应[Swiss编程手册3.3.3](https://www.astro.com/swisseph/swephprg.htm)的速度选项；手册允许默认请求速度，不由此宣称位置的物理精度提高。`numerical_precision.sun_coordinate_policy`记录约定，完整核验逐位绑定出生太阳、所选设计太阳与每个实际根端点太阳，不再用原1e-7度松弛量容纳两种请求口径。原1e-7度残差上限、2″天文、5秒设计根及0.0002秒时标门槛保持。

11组旧版完整输出（本地数据：`validation/human-design-solar-flags-before.json.gz`）保留全部七个原设计根反例及四组日历控制；Linux旧版输出（本地数据：`validation/human-design-solar-flags-linux-before.json.gz`）来自实际1.36.0安装包，两个平台原始浮点不互相替代。另一个固定顺序的488次旗标比较有185次黄经差异，最大约0.000300″；这不是出生人群错误率或旧盘的物理误差上界。

[独立整数格点搜索器](../scripts/build_human_design_solar_speed_reference.py)不导入FateBridge，从原122个出生TT在两个后端搜索244个数值根；它仍用同一Swiss库和数据，不能冒充独立天文观测。macOS参考（本地数据：`../tests/fixtures/human-design-solar-speed-lattice.json`）与Linux参考（本地数据：`../tests/fixtures/human-design-solar-speed-lattice-linux.json`）分别保留。严格所选根逐位比较仍有macOS 2项、Linux 1项不一致，均为Moshier；[严格检查器](../scripts/check_human_design_solar_speed_lattice.py)的`--require-exact`仍返回非零，不改写原参考，也不将它们计为精确一致通过。

这些差异对应真实返回函数在极近TT邻点的数值不单调。`local_solar_lattice`保存原括区外各4个可表示TT的实际太阳与精确残差、反向步、符号括区和零值；自然360度回卷不会误报反向。若观察到多组候选，`local_root_family`逐个候选TT实际计算完整设计激活、同一人格盘下的联合结构、26项固定、桥接、回路与角色解释，`local_root_family_summary`给摘要。没有额外多候选时摘要计数0，原1或2个根端点仍在`design_body_endpoint_assessment`。`root_endpoints`卡同时给出这些摘要。主盘保留原括区选根；不为追平另一搜索器或压低数值残差而换根，有限候选也不认证连续唯一性或物理误差范围。完整结果、整盘后端参考及全部实际生时样本均核验自己的见证。见太阳口径与局部候选验收（本地数据：`validation/human-design-solar-flags-verification.json`）。

1.38.0修正额外数值候选解释的比较方向与来源标注。原代码按所选盘、当前候选盘排列，却沿用“before/after为较早/较晚TT”和“同索引端点evaluations”的说明；当前候选也可能更早或与主盘同刻。现在外层候选与完整解释均带`comparison_basis`，绑定索引0所选设计、索引1当前候选、实际TT、时序关系及当前family索引的原始位置路径。比较顺序保持所选盘→候选盘，不为匹配说明文字重排数据；原历时端点解释保持原规则。完整核验从实际原始位置和求根时刻重建比较依据，重算业务哈希也不能通过伪造的方向、时刻或来源。Mac旧输出（本地数据：`validation/human-design-comparison-basis-before.json.gz`）保留全部5个公开候选及原错误说明；同输入的Linux旧安装包输出（本地数据：`validation/human-design-comparison-basis-linux-before.json.gz`）有4个候选，包含较早时刻，两边分别保留，不截断为统一数量。复核记录（本地数据：`validation/human-design-comparison-basis-verification.json`）记录验收范围。这是解释忠实性修复，未改变实际星体位置、求根选择、物理精度门槛或原典分歧。

1.39.0修复JSON对象键序对完整核验的影响。旧代码按`activations`字典的插入顺序生成接收者与固定星体列表，原典线界影响列表和中心轨迹也有同类问题；客户仅对对象键排序、业务哈希仍有效时，完整解释却会被拒绝。现在接收者及固定来源均按人格、设计的明确侧序生成，中心轨迹按领域中心序生成，原激活数组及其索引保持严格。数组重排、错误路径、错误类型和伪造说明仍拒绝。顺序修复与验收记录（本地数据：`validation/human-design-object-order-verification.json`）保留旧核验对100份原始排序回执的失败；同一旧运行环境仅替换三项派生实现后，原回执的字段、数组、业务哈希均不改而通过。该对照不把旧回执改成本版，也不认证原生星历真实性。

另增[出版方直接样章](https://cdn.shopify.com/s/files/1/0872/4984/6576/files/Life-Cycles-Analysis-preview.pdf?v=1757008879)的一个课程本命样例：印刷第2页将Krishnamurti标为单一定义显化者，所给1895年出生钟为12:25 PM，但该注记没有时区。独立[提取器](../scripts/build_human_design_publisher_natal_reference.py)核对原PDF散列并生成[两项结构事实](../src/fatebridge/data/human_design/publisher-natal-2005-reference.json)，不导入引擎。预先固定的两种显式时区假设在双交点、双后端下均匹配这两项；仍只计1个样例、2项事实。两假设相差约530秒，12条激活的细分及设计月亮的固定依据有差异，即使类型、定义、角色和交叉相同，也不能据此认证生时或完整解释。未印刷的AM诊断组不计字面验收；精确整盘门线、来源时区与全书验收仍未通过，`--require-exact-source-chart`继续失败。原19盘、新193盘、全部38条专业要求及原失败项均保留。

当前来源核验针对规则集1.39.0的完整输出，包含声明的原生操作边界与辅助文件候选身份、实际原生位置的文件上下文与身份复核、全部实际区间求值及其固定说明、完整交点比较及其固定说明、已公布正闰秒的日历见证与说明、官方标签与课程分歧、来源摘要、六回路与整合拓扑、26项固定机制说明、交点接受角色、实际权威路径、优先序、角色结构、假设桥接、联合变体与可选周期搜索、精确残差及文件上下文检查。时标见证仅接受内部一致性回放；旧回执应保留当时实现和原始结果，不凭显示黄经补造缺失的派生来源，也不把旧规则回执未通过当前核验直接解释为整盘无效。

```python
import json
from fatebridge.validation.human_design import verify_human_design_reading

with open("human-design-full-result.json", encoding="utf-8") as source:
    report = verify_human_design_reading(json.load(source))
assert report["status"] == "verified_fixed_template_reading", report
```

## 分离定义的假设桥接

[官方定义说明](https://jovianarchive.com/pages/understanding-definition-in-human-design)按完整通道的连接分组解释定义，并说明门或通道可以形成桥接。`bodygraph.definition.single_gate_bridges`沿用原义：一个新增门只要合并了部分原有分组就会列入，并不承诺整盘连通。

`definition_bridging`补充连接**全部原有定义分组**所需的最少不同新增门，以及所有等量最小方案。计算允许通过原来未定义的中心；同一门参与多条通道只计一次，不能简单相加通道缺门数。每组方案保留新增门、新完整通道、结果分组和合并的原分组索引。它是固定门集与36通道表下的FateBridge图论分析，官方页面只支持定义与桥接概念，不能将这个优化算法冒充原典教义。

原盘的类型、权威、通道及定义保持原值；新增门是假设条件，不能写成某个人将会出现、未来行运必然激活、关系匹配分或心理缺陷。分析针对同次结果的名义出生时刻，不认证整个生时区间内的桥接方案不变。无分离定义时返回`not_applicable_no_split`，最少门数为`null`，不补造方案。

例如，冻结官方输入中的1980-01-02中午伦敦样例有三组定义，原单门列表只合并其中两组；连接全部三组最少需要3个不同新增门，共23组等量最小方案。1980-01-14样例最少需要2个门。四分合成样例最少需要6个门、141组方案；该合成验证不替代官方整盘；1.22.0另取得四个官方四分定义样本，二者分别记录。

独立穷举参考（本地数据：`../tests/fixtures/human-design-bridge-oracle.json`）由[单独的C并查集程序](../scripts/human_design_bridge_oracle.c)枚举22组固定门集的全部候选子集，直到完成首个可连通门数的整个层级，累计检查37,256,606个子集。输入来自事前冻结计划（本地数据：`../tests/fixtures/human-design-bridge-plan.json`）及2001数值摘录，生成器不导入FateBridge计算模块；它采用不同算法复核最少门数及完整方案族，属于本项目算法交叉验证，不是第三方研究、天文观测或人类图现实效力验证。输入选择受前期探索引导，不能称为盲测。复现脚本为[参考生成器](../scripts/build_human_design_bridge_reference.py)，完整工程取证见桥接复核记录（本地数据：`validation/human-design-bridging-verification.json`）。

`definition`证据视图只预览前三组方案的新增门及新通道，保留总数、预览截断标识、作者、版本和来源。完整输出的`minimum_solutions`保留全部见证；需要全文时首次请求`fields=null`，沿用同一run的`result_delivery`读取，不能为补齐摘要而重算。固定释义及回执核验会重建全部方案，拒绝漏项、假门、错误最少门数、篡改预览或将假设写成现实断言。

## 三项专业验收与独立的现实预测记录

| 维度 | 已完成的可复核范围 | 未完成的验收 |
| --- | --- | --- |
| 历法／天文 | NASA/JPL 1900–2099选定时刻的120项物理星体黄经，本地Swiss文件后端最大差异约0.560″，Linux Moshier约1.979″；早于1962年的两个样本使用UT1，后续使用UTC；4组出生／设计太阳弧最大差异约0.001″，均在事先2″容差内 | 不是全部年份、交点或官方完整身体图对照；2″容差不能认证临界处所有精细细分 |
| 历史UTC | 未修改的IAU SOFA C代码独立生成233个1960–1972边界时刻；补齐1960年，全部满足事先0.2毫秒容差，原IERS13段与SOFA重叠部分一致 | 不认证当地钟表记录、国家授时台实现、实测UT1或星体黄经 |
| 真交点天文 | 独立DE440月球位置／速度与ERFA坐标变换，1799–2399固定122时刻；补齐数据后Swiss最大差异约0.040″，全部满足事先1″阈值；Moshier仅3/122满足，门号亦有1例不同 | 有限时刻对照不是连续全时域误差界、平交点原型或官方交点约定认证；失败的Moshier对照保留 |
| 原典 | 2001版64门范围、64中心、36通道端点；6条回路直接分类及30条端点标签推断；保留382/384线界一致及29门两条未决记录 | 完整原典、官方交点口径、整盘和其余通道回路分类独立复核未通过 |
| 解释忠实 | 固定字段释义、实际规则路径、来源页码；三端同值与篡改引用拒绝测试 | 已增加固定模板逐句与内部派生核验；真实模型多轮行为与任意自由文本语义未认证 |
| 现实预测 | 返回未验证状态、样本量0，无成功概率 | 尚无固定可证伪预测规则、事前外部登记、独立结果和复制研究 |

太阳弧对照的设计候选时刻由本实现选择，JPL黄经是独立返回值，不能称为独立选择设计时刻的算法。参考值来自 [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html)，原始响应、请求URL与散列见太阳参考（本地数据：`../tests/fixtures/human-design-horizons.json`）及物理星体参考（本地数据：`../tests/fixtures/western-horizons.json`）。没有把本实现输出回填成独立期望值。

节点参考（本地数据：`../tests/fixtures/human-design-node-de440.json`）由[独立生成器](../scripts/gen_human_design_node_reference.py)读取NASA官方DE440，校验官方MD5，保留原始地心月球位置／速度、一次月球光时修正、ERFA IAU2006矩阵及章动量，再以轨道面与黄道面的交线求升交点。生成器不导入FateBridge或Swiss；全部采样时刻及1″阈值在采集前固定，没有按吻合程度选样。本轮节点与数据范围复核记录（本地数据：`validation/human-design-node-verification.json`）保留修复前后的失败与范围。

现实研究首先需要具体预注册假设，例如固定期限的明确决策结果，并与无出生信息的基线或盲化打乱的反馈比较；须保留全部入组者、缺失结果、事前预测、独立结果和训练／留出隔离。现有[预测验证流程](prediction-validation.md)可用于已事前定义的二元预测研究；体验日记本身不能认证预测能力。没有这些资料时不生成效果分数，也不将可复现、满意度或测试通过率代替现实有效性。

## 调用

以下为虚构测试资料，不能替代用户的真实出生资料：

```bash
uv run --locked --extra dev fatebridge human_design \
  --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-timezone Asia/Shanghai \
  --fields bodygraph profile source_consistency interpretation validation \
  --strict-fields
```

`birth_time_uncertainty_minutes`为用户确认的正负范围，最大60分钟，0为未评估。使用10秒连续TT网格，并在检测到星体速度变号的相邻网格间细查候选；返回`classification_variants`、`activation_variants`及各状态的首次观察见证。`comparisons`保留两端与名义盘的比较以便核对，但不再只据三点推测内部状态。

联合快照保留同一时刻两侧26个门线、四箭头所需的八个Tone、完整最少桥接方案及每条线的固定触发位置。引用路径指向该快照，外层见证保留出生／设计TT、实际后端与返回旗标；不同见证不能拼接。缓存只在本次调用内按实际依赖复用，缓存数量不是采样数量、覆盖率或概率。`node_convention_comparison`与`node_backend_comparison`也重建这些联合派生；后者仍只替换节点。

实际回归案例1980-02-04 12:00 UTC、Moshier、正负10分钟：设计月亮由62.6变为56.1，旧结构摘要只保留1个状态；两端最少桥接门数均为2、方案均为8组，但具体门集改变。新投影保留3个联合状态，报告`bridge_families_changed=true`而`bridge_minimum_gate_count_changed=false`。单独C穷举程序对两端累计检查1,982个子集，两组完整最少方案均吻合；这是不同算法核对固定门集，不是独立天文真值。该案例由引擎搜索选出，较宽区间搜索未命中的结果也保留，不能称为盲测。

`uncertainty`证据卡给出`joint_evidence_summary`、采样范围与节点比较摘要；首次变化含预览和同一run完整见证路径，预览不是完整方案清单。生时范围为0时摘要、采样及缓存均为`null`，不能解读为稳定。完整回归、负例、跨接口、Linux及安装包证据见联合变体复核记录（本地数据：`validation/human-design-joint-verification.json`）。

已发现固定Moshier回归案例：名义时间1916-05-21 22:18:53、正负60分钟，北交点在两端和名义盘为60.5／Color5／Tone2／Base2，区间内部却出现Base1。该数据是固定范围内搜索得到的实现回归案例，不是独立天文参考，且该年代民用标签采用已声明的历史UT1约定。

采样在TT上直接计算双组激活，不通过datetime四舍五入回UTC；因此可以保留闰秒内或历史分数秒调整中没有唯一民用标签的样本。`sampled_nonstandard_civil_labels`记录实际观察到的特殊标签，未列出不代表区间没有这类时刻。见证的数值时间不是准确变化边界，更不是出生记录精度。

有限网格和速度变号候选仍不是连续区间穷尽证明，`sampling.continuous_interval_certified=false`。压缩月球文件在分段边界可能有微小不连续，速度变号候选不能自动认证为真实驻留；依据见[Swiss Ephemeris节点说明](https://www.astro.com/swisseph/swisseph.htm)。实际后端与未来闰秒假设在报告中回显。盘面释义明确限于名义时刻，不能把样本相同说成全区间确定相同。逐层值集合不是所有值的笛卡尔积；不可跨不同时刻拼接激活门以制造未出现的通道、类型或Profile。

区间敏感性复核记录（本地数据：`validation/human-design-interval-verification.json`）保留遗漏案例、TT特殊标签测试、184项本地与326项Linux相关测试、安装包真实stdio验收，以及黄金快照首次不匹配和四处元数据差异的复核依据。测试通过数不换算连续区间覆盖率或专业满分。

### 全部实际采样点的重放验收

1.25.0保留旧1.24验收漏洞（本地数据：`validation/human-design-sampling-before.json`）中的全部15个真实改动案例。此前，删除激活变体、改错端点来源TT、虚构速度变号候选、篡改模型摘要或将有限采样描述为连续认证，在重新计算业务哈希后仍可能通过完整解释核验。冻结负例计划（本地数据：`../tests/fixtures/human-design-sampling-plan.json`）逐项检查，不删除旧失败或修改原始输入。

`time_sensitivity.evaluation_witnesses`保存本次**每一个实际求值点**两侧各11个原生因子的黄经、速度与返回旗标，以及完整时间尺度、出生和设计标签；地球与南交点从来源精确派生。重放运行原有有限网格、速度变号二分与联合过渡细查，逐项核对实际消耗的点、全部激活变体及首次见证、两个完整端点比较、来源与未来闰秒假定、特殊标签和固定范围声明。额外、重复、遗漏或脱离名义盘的见证均拒绝；重放不再次调用星历。证据时间字典与主盘分开保存，避免内存中修改见证同时改变主盘锚点。

`time_sensitivity.summary`和`interpretation.birth_interval_meaning`给出实际求值数、观察到的激活／联合结构变化及未分开的多依赖区间。新增`birth_interval`证据卡可在通常8192字符预算内读取摘要与解释；完整原始矩阵由同次`result_delivery`分片取回并核对SHA-256，不能重算代替原结果。`birth_time_uncertainty_minutes=0`明确返回未评估，不据此判断附近时刻稳定。原九条固定说明、所有原典分歧和既有失败均保留；完整过程见本轮复核记录（本地数据：`validation/human-design-sampling-verification.json`）。

现代UTC标签沿用冻结表和0.2毫秒标签容差；1972年前的民用授时实现、UT1／TT物理实现、提供的原生速度和坐标真实性仍未独立认证。所给原生数值与报告完全自洽，也不能证明原生执行真实发生。有限网格和驻点候选不提供连续区间完备性；变体数及求值数不是概率，不能跨采样拼接整盘。物理天体2″、设计根5秒、节点既定参考阈值与64 MB结果存储上限保持不变。

### 同一网格内的联合状态遗漏

规则集1.13.1细化已观察到多项独立依赖变化的取样区间。冻结的搜索计划（本地数据：`../tests/fixtures/human-design-transition-plan.json`）先规定1980年1月、10秒步长、Moshier及首个候选标准；扫描207,349个时刻后，发现固定案例（本地数据：`../tests/fixtures/human-design-transition-case.json`）：名义时刻1980-01-24 23:57 UTC、正负1分钟，旧13点只得到2种联合状态。两个不同变化落在同一10秒区间内：

| 共同取样点 | 人格太阳 | 人格月亮 | 旧网格是否保留 |
| --- | --- | --- | --- |
| 左端 | 41.3，Tone5 | 24.2 | 是 |
| 新增中点见证 | 41.3，Tone6 | 24.2 | 否 |
| 右端 | 41.3，Tone6 | 24.3 | 是 |

新增1次完整TT排盘得到第3种状态；每个见证重算自身88度设计根、全部激活及派生，不拼接不同取样点。这些是同模型取样点，不能当作精确事件时刻、真实出生记录或独立天文观测；搜索不是盲抽样或人群错误率。

`joint_transition_refinement`保留初始TT样本、22项独立源依赖的共同状态表和细化树。其依赖与完整联合快照的门线／四组Tone及人格日地／交点Color一致，日地和南北交点的对点关系不重复计事件；不枚举所有星体的全部Color／Tone／Base联合组合。只有相邻样本至少两个独立依赖变化才继续细分。目标括区宽度0.2毫秒、最多新增4096次完整排盘；数值分辨率内仍未分开的区间及预算耗尽明确保留，不能断言精确同时。没有候选不等于稳定，未被初始样本发现的折返或更短事件仍可能遗漏，因此连续区间认证始终为false。

跨平台复算另保留原始浮点差异：出生TT及离散门线／细分／后端旗标须一致，设计根沿用0.2毫秒括区分辨率；位置比较沿用此前冻结的物理天体2″、节点1″参考阈值，不改写原始坐标。原始数值不完全相同会明确记录；速度差只作诊断，未认证其精度。位置容差通过不替代完整天文验收。

`joint_transition_refinement_summary`用于紧凑的`uncertainty`证据卡；0分钟时两项都为null。完整结果的[取样树核验](../src/fatebridge/validation/human_design_transition.py)检查分割、状态集合、计数、预算和同次摘要，拒绝重新计算业务哈希后的篡改；它不认证状态真实出现于声明的TT。[只读回放脚本](../scripts/check_human_design_transition_case.py)可重现案例，`--replay-search`重放整个有序搜索，不改写冻结文件。详见联合过渡复核记录（本地数据：`validation/human-design-transition-verification.json`）。


若原始生时未知，不应通过填任意名义时刻伪造确定盘。完整结果使用 `fields=null`，MCP大结果读取同一run的交付，而非再算一次。

## 复核与维护

太阳附近的视位置约定、同次原生坐标及名义圆盘投影，见[视位置与解释依据](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-apparent-position-evidence.md)。该扩展保留原天文超差、原典分歧和全部未完成验收状态。

[基础／过渡角色分区](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-profile-partition.md)将实际日地角色与精确回退 88° 的理想分区分别记录，保留求根边界差别；新增证据视图、来源和解释均从同一完整计算包核验。本轮记录（本地数据：`validation/human-design-profile-continuation-v1/README.md`）保留 96/768 个官方组合、69 个名称失败和 Linux 旧凭据跨平台重放失败，未将冻结快照的 2457 项通过等同于完整专业验收。

[跨平台投影算术](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-portable-projection.md)进一步以整数区间确定新回执的规范化 binary64 投影值和原有分类，完成新回执在 macOS / Linux 的双向严格重放。旧格式 24 份跨平台失败、原天文超差和原典要求继续保留。2470 项冻结回归通过只对应已声明的人类图及交付范围，不代表专业目标已完成。

最终源码与 CI 复核（本地数据：`validation/human-design-portable-projection-ci-v1/README.md`）另保留格式、类型与生成器身份整理后的 2470 项回归、同一最终 wheel 的双向接口重放及全部旧拒绝。官方角色核对扩至 192/768，4992 门爻、192 份结构及当前固定模板一致；135 个名称失败、576 个缺项保留。全仓库 Black／isort／mypy 仍未通过，原 38 项标准仍有 4 失败、3 未完成。

随后完整官方集合协调复核（本地数据：`validation/human-design-profile-cohort-integrity-v1/README.md`）保留原 19／193 例，并将原 768 计划的已观察部分扩至 288 例。500 例逐组核对，计划中这 288 例的 7488 个门爻、288 份结构及全部 500 份固定模板一致；本批 179 个名称失败、480 个缺项保留，原 15／86 及此前 135 个名称失败均逐项未变。共享词汇门槛、领域计算及原验收阈值没有改动，原 38 项完整专业要求仍未通过。

前次公开资料续核（本地数据：`validation/human-design-public-source-continuation-v1/README.md`）封存447/768例，其中前384例与原19／193例共同完成审计：596份机械字段和固定模板一致，矩阵内237个字面名称失败，命令退出1；当时额外63例仅核对来源，第448例提交后尚未保存。原500例逐项检查完全相等。新增29号争议点的独立DE440太阳残差约0.000653″，支持当前官方29.1／30.1的软件行为；印刷区间会得到29.2／30.1，条件性固定影响与解释全部保留，未代替出版方勘误。

最新完整768组合复核（本地数据：`validation/human-design-profile-all768-v1/README.md`）已按原输入顺序收齐全部官方观察并完成来源绑定：每份PDF的13项文字属性与网页相等，实际64门×12角色全部匹配，无重复或缺项。连同原19／193例共980份，25480个门爻、980份机械字段及固定模板一致；字面名称失败15／86／487，共588例，联合审计仍退出1。原596例逐项判定不变，新增审计检查器的10项测试通过，旧384前缀的缺项失败也保留。矩阵内487个名称失败分为414个编号缺省及73个其余字面差异，仅作诊断、不接受别名。领域计算、原参考、阈值与合同未变；原38项的4失败／3未完成、现实预测样本0及此前未通过的全仓库检查均未改变。

后续太阳圆盘与历史钟时复核（本地数据：`validation/human-design-solar-disc-clock-v1/README.md`）新增五份现代及原22项中的13份公开观察，九项仍缺。五个历史输入与官方UTC标签相差75秒，海王星19.5／19.6失败保留；五个改钟时控制也仍有两处不符。新命令按原计划SHA检查缺项，并可逐例解释钟时链接，默认原判定不变。解释核验另明确支持完整、已记录的历史v2原生声明，标出其与当前策略的区别，未知或改造声明继续拒绝；原24份和新增32份完整包的56份回放均保持原proof字段。它不认证新旧原生执行、完整爻义、全历法或预测。

海王星换爻区间续核（本地数据：`validation/human-design-neptune-transition-v1/README.md`）按冻结二分程序取得26份公开观察，四个相邻分钟区间及全部PDF文字属性已绑定。原站1840年海王星换爻落在03:12–03:13，而当前DE441零钟差候选约为03:25；同日太阳及两次月亮控制吻合。全部8种模型与2种固定时钟假设均未能同时解释四区间，统一钟差的补充约束也无交集。新增命令保留所有失败模型、重复控制和原输入顺序；没有切换生产星历或重标原专业验收。

历史数据与源码续核（本地数据：`validation/human-design-historical-models-v1/README.md`）进一步发现当前默认算法配DE406能兼容四个既有原站区间，固定C源码与已装绑定的两条执行路径均相容。五个名义历史标签只有三份实际文件树，不能虚增独立版本证据。DE406的3600条公开原始位置／速度参考通过JPL自身警戒线，但原有32个默认视黄经点仍有19个超过2″，最大约8.97″；源码和数据身份、软件相容与物理精度分别报告。新增核验命令保留全部14条执行路径和旧失败，生产星历、原典与解释验收状态均未切换。

```bash
uv run --locked --extra dev pytest -q tests/test_human_design.py tests/test_human_design_depth.py tests/test_human_design_circuitry.py tests/test_human_design_sensitivity.py tests/test_human_design_transports.py tests/test_historical_utc.py
uv run --locked --extra dev pytest -q tests/test_human_design_precision.py tests/test_human_design_variables.py
uv run --locked --extra dev pytest -q tests/test_human_design_opposition.py
uv run --locked --extra dev pytest -q tests/test_human_design_joint.py
uv run --locked --extra dev pytest -q tests/test_human_design_astronomy.py
uv run --locked --extra dev pytest -q tests/test_human_design_profile.py
uv run --locked --extra dev python scripts/build_human_design_profile_reference.py /absolute/path/profile.html /absolute/path/six-lines.html --check
uv run --isolated --no-project --with skyfield==1.55 --with jplephem==2.23 --with numpy==2.5.4 python scripts/gen_human_design_astronomy_reference.py --kernel /absolute/path/de440.bsp --check
uv run --locked --extra dev python scripts/build_historical_utc_reference.py --check
uv run --locked --extra dev pytest -q tests/test_utc1960.py
uv run --locked --extra dev python scripts/build_utc1960_reference.py /absolute/path/sofa/20231011/c/src --check
uv run --isolated --no-project --with pyerfa==2.0.1.5 --with jplephem==2.23 --with numpy==2.5.4 python scripts/gen_human_design_node_reference.py --kernel /absolute/path/de440.bsp --check
uv run --locked --extra dev python scripts/audit_human_design.py --output /tmp/human-design-audit.json
uv run --locked --extra dev python scripts/audit_human_design.py --require-professional-acceptance
```

普通审计退出0表示成功产出报告；最后一条应退出1，保留三项专业目标尚未完成的状态；现实预测另行记录，不替代或阻塞三项专业验收。本次审计快照（本地数据：`validation/human-design-audit.json`）包括实现与参考的散列，不以软件测试通过数换算原典或预测分数。

SOFA参考维护命令需可用的C编译器；生成器核验官方发布的8个源文件／头文件散列，不导入FateBridge或Swiss。普通测试使用冻结数值事实，无需下载、编译或新增运行依赖。SOFA源文件本身不随FateBridge分发。

本轮历史UTC与Linux复核记录（本地数据：`validation/human-design-history-verification.json`）保留macOS及Linux x86_64的选定测试、已匹配的人类图Linux黄金快照、实际后端及安装包／真实stdio证据，也保留首次失败及修正依据。先前深度复核记录（本地数据：`validation/human-design-depth-verification.json`）作为历史快照，不用最新通过项覆盖原有失败。

独立参考只在显式维护时刷新，普通测试离线执行：

```bash
uv run --locked --extra dev python scripts/gen_human_design_horizons_reference.py
uv run --locked --extra dev python scripts/build_human_design_reference.py /tmp/hd-rave-iching-2001.pdf
uv run --locked --extra dev python scripts/build_human_design_depth_reference.py /tmp/hd-rave-iching-2001.pdf --check
```

第二条需先自行取得上述原典PDF并安装 `pdftotext`。提取器保存数值事实与来源定位，不保存384线正文；不能先改冻结参考再宣称独立验收。当前人类图黄金快照已在Linux x86_64 / Python3.12.3参考进程核对；其回归字节一致不替代独立天文或完整专业验收。

真实模型解释另有[8题开发验收记录](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-semantics-evaluation.md)：同一套预先固定标准下，桌面内置CLI完成8题，24条人工语义复核通过，141个原答单元及实际同run证据完整保留。旧PATH运行环境的两次失败及各7个未运行案例仍在原始记录中；它们没有被重新评分为通过。此开发样本没有独立留出集，人工判断也没有独立裁判认证；原38项要求中的完整模型忠实性只推进为未完成。投影文件、实际观察到的输出、完整业务盘和任意模型自由文本的验收范围分别保留，不能用字段或哈希绑定制造满分。

本轮[时区来源复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-timezone-source-evaluation.md)修复缓存规则与后读文件指纹不一致、以及冷启动缺失数据误报用户错误的问题。来源变化时拒绝计算，不静默重载后继续混用；18组提前冻结的正常完整结果保持一致。完整历法及原典验收门槛继续保留。

[参考目录来源视图](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/human-design-reference-snapshots.md)进一步将12份运行时事实目录的实际字节、解析值和指纹绑定，并在计算及完整解释核验中复核。原来6/2角色解释使用旧目录却引用新文件指纹的反例已保留；未核对的冷启动文件、目录中途变化及内存改写均拒绝。原14份参考、数值门槛及所有原典分歧继续保留，来源身份核验不替代完整线义或出版方母版认证。

2026-10-25从IHDS当前页面新生成的公开链接重新下载后，确认PDF与此前Jovian预览逐字节相同（10页，SHA256为`5bbc572b33609ee1f23e33ee7a36645ddc565da9f256635a95043295369a33e6`）；这不增加原典页覆盖或独立教材内容。下载身份与初次失败均保留在本轮证据（本地数据：`validation/human-design-cycle-origin-v2/evidence/preview-identity.json`）。


2026-10-26的历史极性续核（本地数据：`validation/human-design-historical-polarity-v1/README.md`）新增58.5来源冲突比较。2002年zc design通知转述月亮与太阳均属上升极性，而2001字面星体表列月亮上升／太阳下降。按结果揭晓前冻结的选择，原768集合中全部两张人格太阳58.5官方PDF均目视显示下降标记；不把这两个不符合通知假设的观察删去，也未切换默认极性表。该通知不是经认证的出版方母版勘误，其适用版次仍未定。

完整包新增`historical_polarity_context`及同名解释，规则集为`human_design_historical_polarity_v1@1.0.0`。它仅沿用名义盘真实双侧固定路径，逐项比较58.5在两个来源假设下的状态；交点可接受固定但不作为触发星体。选中的原26项固定、数值星历、设计时刻和完整逐项reading保持原计算，不将假设替代全线爻义。`historical_polarity`证据视图读取这项完整比较；原`fixing`摘要也保留其未决状态、涉及位置计数和解释。其他联合见证须读取其自身选中结果，不能套用名义盘的条件状态。

公开旧通讯的冻结检索覆盖档案页明确列出的1993–2004年86份PDF、208页，并对全部页做OCR，候选规则事先固定。关键正面事实另做目视核对；OCR命中不是原典认证，未命中也不证明全文或其他来源没有相关规则。1999年另一勘误只给旧书页码，不能自动映射为当前29.1／29.2界线更正。完整384线义、周期首末触优先、原天文超差、官方交叉字面名称和现实预测证据的验收门槛均未降低。

2026-10-27的坐标含义与完整解释续核（本地数据：`validation/human-design-coordinate-interpretation-v2/README.md`）明确太阳角距的地心顶点、坐标架和AU单位，并修正交点接受／供给角色、26项固定机制和周期来源层次的解读。当前5题开发复验的全部原答保留，20条任务标准通过，但完整答案另有1处交付哈希术语未认证，不能宣布全面语义验收。当前相关124项测试和三端检查不替代原38项门槛；上次临时目录中丢失的15份模型原始材料单独标为不可复现，没有拿本轮执行冒充恢复。旧16个封存目录4454个已索引文件仍逐字节一致。

周期参考微秒边界续核（本地数据：`validation/human-design-cycle-reference-brackets-v1/README.md`）进一步修复参考民用时刻舍入到交会TT端点、从而误报括区内的问题。周期规则1.5.0改用已声明时标的精确有理TT比较，并交付`cycle_summary.reference_contact_ordering`。28个事先冻结的边界输入保留原14个误判，两个旧完整错误包在当前核验中明确拒绝；全部原坐标、求根与见证不改。另按完整冻结定义识别同名v5原生策略的历史与当前说明，不把旧声明认成当前保障。微秒比较修正不认证微秒物理精度，也不解决原典取舍、完整线义或原全历法验收缺口。


本命规则保持1.39.0，可选周期规则1.6.0补上速度驻点与返回黄经极值之间的数值差异。在开发搜索得到的整秒输入1863-10-25 15:01:33 UTC中，凯龙有限数值候选从3条增至5条；原3条交会与原有全部数值见证保持。原扫描作为完整前缀，随后作有限坐标补探，仅在目标进入严格扩展的已观察极值范围时重新分段。另处理网格端点零速度及连续零值候选，保留原24个解析控制和12个量化未决案例。`motion_evidence`区分原生速度符号与搜索段相位方向。原一秒区间符合性仍有失败，不能将候选增多或括区变窄视为物理精度认证。阴性探查、原失败和完整数据见周期坐标极值续核（本地数据：`validation/human-design-cycle-solar-stations-v1/README.md`）。


太阳求根参考现按原244行完整报告，缺少原参考端点的局部观测会保留为未评估且不通过，不能因检查器崩溃而漏掉后续行。本次macOS严格对照为241行一致、3行不符；首个Swiss例存在调用上下文差异，原两个Moshier分歧仍在。原参考、生成器及原验收断言未改，完整结果见太阳参考上下文核对（本地数据：`validation/human-design-solar-oracle-context-v1/README.md`）。这不认证连续物理精度或完整原典解释。

完整原始回执可用本地模块生成逐上下文线参考包（本地数据：`validation/human-design-context-line-reading-v2/README.md`）。新版原样嵌入名义盘v1包，并分别从实际交点口径、后端参考、全部保留的生时求值、设计根端点及局部根候选重建26项固定和爻义绑定。每个上下文保留实际坐标、细分及原典分歧，条件判断不沿用名义盘；未执行的对照和缺完整双时刻盘的周期接触明确保留为未组装。它是Python API与本地模块CLI，不新增REST／MCP工具，不认证完整384爻义或现实预测。

```bash
uv run --locked --extra dev python -m fatebridge.validation.human_design_context_lines_cli build docs/validation/human-design-context-line-reading-v2/evidence/gate14_transition_interval.json.gz --output /tmp/fatebridge-hd-context-lines.json.gz
uv run --locked --extra dev python -m fatebridge.validation.human_design_context_lines_cli verify docs/validation/human-design-context-line-reading-v2/evidence/gate14_transition_interval.json.gz /tmp/fatebridge-hd-context-lines.json.gz
```

上述输入是已披露的虚构工程回归样例；输出路径已存在时拒绝覆盖。核验需要另行提供可信原始回执，成功仅表示固定组装与计算绑定一致。已有未知释义、来源冲突和失败案例不作通过处理。

线参考新增显式分类`lines_v3`，见第三门原典内容续核（本地数据：`validation/human-design-gate3-knowledge-v3/README.md`）。该版保留384定位，局部待复核转述由12条增至18条，另366条未整理，独立完整语义验收仍为0；默认`lines`仍为v2，旧384个默认参考和旧v1/v2解释包不变。第三门六条包含具体线义、引导语与原文疑点；出版方公开样本只互证六条线名，不能据目录认证未提供的正文。

当前MCP工具`knowledge_read`可明确选择新版本：

```json
{"domain":"human_design","category":"lines_v3","key":"3.4","fields":["reference_details","provenance"],"strict_fields":true,"include_snapshot_text":false}
```

逐上下文解释包的构建与核验均可添加`--reference-category lines_v3`。版本是验包时另行提供的可信输入；省略时仍按v2验收，不能由待验包自行降级版本。v3包原样保留名义v1包，新增引导语的个人适用性仍为未知，不将其伪装成已经核验的通道条件。当前聊天实际六次MCP读取、三端协议与安装包状态分别记录，不以一次连接读取推断其他部署已更新。

显式分类`lines_v4`在v3上增加局部结构条款注释（本地数据：`validation/human-design-context-clauses-v1/README.md`）：2.3、6.3、7.2、12.6、42.1共5条，其中2.3已存在于v2，不重复算作新增爻义。完整384条定位不变，局部转述仍18条，待整理366条，独立完整语义验收仍0。默认`lines`与显式`lines_v3`的参考内容和旧解释包保留原版本。

`knowledge_read(domain="human_design", category="lines_v4", key="7.2")`返回来源注释，仍不选择个人极性。模块CLI的构建与核验均显式添加`--reference-category lines_v4`，逐一绑定每份实际保留的完整盘。7.2观察7–31，12.6观察12–22；6.3位于引导语，不能误归上升段，也不据其生物叙述计算生育结果。上述三句未明说永久性，注释不补写该断言。固定状态、图结构观察与现实效果分别记录，不据通道更改实际固定状态或承诺社会影响。

42.1的“特别是在与根部有定义关系时”保留直接42–53通道、骶骨至根部完整通道连通两种观察。独立定义的根部不等于连通；该措辞不是必要或充分条件，资源是否有余和原典具体拓扑口径仍未知。核验器使用外部可信原始回执及另行指定的版本，拒绝删改注释、选定尚未解决的口径、虚构适用性与自由改写固定模板。该工程绑定不认证任意模型文字、完整爻义、物理精度或现实预测。

显式分类`lines_v5`再增加第4门六条局部转述（本地数据：`validation/human-design-gate4-knowledge-v5/README.md`）。2001公开副本PDF第12、13页已完整目视核对；六条线名、极性星体与块定位另行冻结。v5共24条本地转述、360条待整理，独立完整语义验收仍为0；没有出版方逐爻正文旁证或母版认证。默认`lines`、`lines_v3`、`lines_v4`保留旧内容，注册表只追加新分类。

使用`knowledge_read(domain="human_design", category="lines_v5", key="4.4")`，解释包构建和核验均显式添加`--reference-category lines_v5`。第4门的公式或答案保留为待检验的可能，不能写成已证实事实或内在权威；4.1的时机不改写成事件日期，4.4的线名不用于认定当事人撒谎。六项引导语均未转成个人可计算条件，适用性仍为未知。每份实际完整盘分别绑定自己的门线、固定侧重与引导语，保留v4全部结构注释。

该轮冻结的7个新增虚构输入与8个既有回执保留239份完整盘、6214条激活绑定，其中79条为第4门。首次直接领域计算缺少公开run元数据而被拒绝，7份原结果与首轮失败保留；同组输入通过公开应用入口重新捕获，未补造元数据或降低核验要求。当前聊天的旧MCP实际拒绝v5分类，源码、安装包和该连接的交付状态分别记录，不将本地测试当作连接已刷新、任意模型解释或现实预测验收。

完整原队列真交点续核（本地数据：`validation/human-design-calendar-nodes-v1/README.md`）保留原1800–2399季节队列1200组出生样本、人格与设计共2400个TT，用既有DE440／ERFA独立节点方法补齐全部时刻。原122个控制逐项重现；Swiss全部2400项在原1角秒门槛内，最大差约0.113191角秒。Moshier有2248项超差，最大约62.5113角秒；另有4项在1角秒内但Base不同，分别保留角度门槛与细分投影判定。南交点为同一北交点的精确对置，不增加独立样本。

新核验器绑定原48000条物理位置验收，不以节点通过抵消原Swiss的1条及Moshier的2265条失败。本次生产批次的这些物理黄经和返回旗标与原记录逐项相同，旧太阳根、2角秒位置及5秒根门槛未重评。比较命令严格退出1，全部样本、失败与参考原字节保留。该轮只增加独立参考、验收脚本和离线回归，没有改生产星历、共享三端合同、默认后端、原38项要求或已有解释版本；不认证连续全历法、交点速度、平交点、官方交点约定或现实预测。

生时区间坐标候选续核（本地数据：`validation/human-design-interval-coordinate-extrema-v1/README.md`）将默认有限取样升级为`human_design_continuous_TT_coordinate_interval_v2`：保留原10秒网格和速度变号前缀，补查网格零速度及返回黄经极值候选，并将每次整盘求值绑定到激活、Variable、联合结构和解释。修改前冻结的四个合成控制实际为三例捕获、一例漏项，原结果全部保留；修复后四例均捕获，不能计为独立天文样本。有限黄金分割有4096次新增整盘预算，不认证单峰、连续穷尽、真实驻留或物理精度。新输出合同明确区间及坐标细查类型，旧合同只按原v1算法重放。

同轮真实1916年Moshier正负60分钟调用曾因隔离进程JSON超过64MiB而失败。仅去掉分隔符空格即可无损交付完整结果，原上限和全部见证保持；Moshier/Swiss两个正负60分钟结果及两项既有控制均通过禁止原生重算的完整重放。165项去重定向测试及候选wheel的REST、CLI、全新stdio合同/完整解释检查通过。当前聊天实测能返回新计算，但仍附旧缓存合同，交付层分别记录。原38项仍为31通过、4失败、3未完成，严格命令退出1；土星/凯龙首末触规则、完整语义与历法外部符合性等缺口没有据此转为通过，现实预测仍未测试。

历史时区续核（本地数据：`validation/human-design-timezone-history-v1/README.md`）保留同版IANA2026e主要数据、完整`backzone`及当前pytz2026.5的全部597个已支持名称，共1071960个检查点。发现16个名称的4946个历史检查点以`-00`表示偏移未指定，旧入口却按零偏移排盘。共享入口现在拒绝该实际未知状态，并通过明确错误码和固定提示要求核实偏移；已知零偏移和同名时区有效规则期保持。原错误接受的完整排盘及失败日志保留，两项有效控制在候选包REST、CLI、全新stdio的完整业务结果与修复前相同。

本轮没有将历史扩展数据替换为默认规则。主要/扩展版的历史冲突、GMT规范化字面分歧及旧C工具对部分未来POSIX尾规则的读取分歧继续保留，严格比较仍失败；不能据工程一致或回执核验认证当地历史钟、完整历法、原典或现实预测。新源码合同为`bf0220bac02ebe6270b2ce051e4f3b4d7b356a253073bdce47bac81b64c031f3`；当前聊天虽已实际拒绝未知状态，父进程合同缓存仍旧，验收层分别记录。

完整时区窗口与历史整盘续核（本地数据：`validation/human-design-timezone-window-v1/README.md`）保留上轮全部失败，另以同源IANA2026e C工具和显式`-r`／`-R`区间保留597个名称、全部原检查点和失败窗口新增时间戳，共1,076,348点。共享解析器现保留GMT零偏移的GMT缩写；4808个重复标签点被修复，偏移、DST、实际时刻与本地有效性没有变化。新参考四项模型比较为零差异，单用`-r`产生的UTC/CMT及2399年异常参考仍保留；这不是历史实况或天文精度满分证明。输出合同未因标签修复改变。

六组事先冻结的历史／现代对照保存18份完整盘及解释，五组规则分歧改变16至19项激活细分；喀什1900工程样例还改变Profile。五份跨候选解释错配均被拒绝，现代相同解释未算负例通过。两套历史规则仍是条件模型，不按盘或解释倒选出生钟。原38项专业验收仍31通过、4失败、3未完成；完整384线、周期原典未决、模型咨询及现实预测的缺口继续保留，详见同轮报告。


周期原点条件对照续核（本地数据：`validation/human-design-cycle-origin-comparison-v1/README.md`）新增显式`compare_cycle_origins=true`，必须同时提供`cycle_reference_datetime`。默认请求保留原业务结果；人格出生原点仍是主结果，另按本盘实际88度太阳弧设计TT作同一65儒略年有限搜索。完整`cycle_origin_comparison`保留另一路全部接触、驻点／坐标探查、失败、来源索引和数值见证，并比较两个集合首末候选的TT数值差；数量不同也不按序号强配。它不是88个历日或生物学日期推断，也没有选定新的传统原点、首末触优先或第六线人生阶段。

当前公开Jovian词典明确天王星出生位置；IHDS《Life Cycles Analysis Student Manual》的产品说明和公开预览仍不足以裁定土星／凯龙原点与首末触优先。设计原点明确为数学敏感性假设，不赋予同等原典依据。新固定解释与原点、实际设计星体位置、全部见证及来源逐项绑定；正确业务哈希不能使删除接触、改原点、改来源索引或虚构传统优先的文字通过。该核验仍不认证自由模型文字或完整384线义。

下列是已披露的虚构工程样例；完整请求读取同一次运行的交付结果，摘要使用已发布`cycle_origins`视图对应字段：

```json
{
  "birth_year": 1980,
  "birth_month": 1,
  "birth_day": 1,
  "birth_hour": 0,
  "birth_minute": 0,
  "birth_second": 0,
  "birth_timezone": "UTC",
  "cycle_reference_datetime": "2029-07-01T00:00:00+00:00",
  "compare_cycle_origins": true,
  "fields": [
    "cycle_origin_comparison.status",
    "cycle_origin_comparison.selected_origin",
    "cycle_origin_comparison.hypothesis_origin",
    "cycle_origin_comparison.summary",
    "cycle_origin_comparison.interpretation"
  ],
  "strict_fields": true,
  "include_snapshot_text": false
}
```

这个1980样例中，土星已观察交会数为人格1／设计假设3，天王星3／1，凯龙3／3。差异证明原点选择会实际影响结果，但不能据此倒选原典。无凯龙轨道文件时仍保留`partial`、`unavailable`和未知差值，严格Swiss要求仍拒绝缺失数据。

完整对照叠加原1916正负60分钟区间暴露了新的传输溢出：旧类型封装消息为71,908,983字节，超过原64MiB上限。人类图隔离进程现显式协商有限JSON树结果编码；它保留全部值、类型和时钟记录，将同一完整消息降至64,274,458字节。原字节上限、区间、探查预算、所有失败与旧协议均保留；其他领域默认仍用原类型编码，含日期或元组的结果也沿用原编码。最终实际大案例、三端、完整解释与原38项状态见本轮报告；数值传输修复不等于天文精度或专业目标满分。


显式分类`lines_v6`新增第5门六条局部转述及来源极性呈现（本地数据：`validation/human-design-gate5-knowledge-v6/README.md`）。当前30条本地转述、354条待整理，完整独立语义验收仍0；默认`lines`及旧v3／v4／v5的1536条完整参考输出保持原内容。使用`knowledge_read(domain="human_design", category="lines_v6", key="5.6")`，解释包构建及核验均显式添加`--reference-category lines_v6`。

5.6上升栏海王星图符与正文无极性、未列下降星体的说明同时保留，图文约定尚未独立裁定；新下降转述为空值，解释仅枚举来源实际列出的极性，不据此改写实际固定机制或补造另一极性。16组事前固定输入的完整默认业务结果未变，新解释绑定120份完整上下文、3120条激活，其中241条为第5门，5.6同时覆盖实际上升固定及未固定。旧测试中两个恰有四版目录的断言仍失败，原断言保留；新包和当前聊天旧MCP分别验收，不宣称完整384线、任意模型文字、天文精度或现实预测满分。

显式分类 `lines_v7` 新增第6门原典限定句与完整解释续核（本地数据：`validation/human-design-gate6-knowledge-v7/README.md`）：36条本地转述、348条待整理、完整独立语义验收仍0。默认 `lines` 及旧v3／v4／v5／v6的1920条完整参考输出保持原内容。6.3的引导语注释保持与固定极性分离，直接6–59通道仅作结构观察，不据此评估生物结果；新版补充资料也不能用额外字段覆盖继承的原典注释。

40组事前固定输入的完整默认业务结果均未改变，新解释绑定300个完整上下文及7800条激活。6.3实际22条均未固定，通道存在15条、不存在7条；其他固定状态仅有单独标识的合成图结构控制。新40项测试和候选安装包实际三端验证通过，旧目录数量断言的失败保留；当前聊天常驻MCP仍不认识 `lines_v7`。原38项严格专业验收仍31通过、4失败、3未完成，严格命令退出1；本轮未新增独立天文精度或现实预测认证。
