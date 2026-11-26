# 人类图算法、独立参考与验证范围

[计算与调用](human-design.md) · [源码职责](architecture.md#分层职责) · [算法状态](algorithm-status.md)

本文维护当前算法所有者、独立参考及已知差异。调用参数、默认口径、原典覆盖和来源分歧见[人类图计算说明](human-design.md)；函数归属见细算法清单。

## 算法所有者与入口

| 计算 | 所有者与实际消费者 |
| --- | --- |
| 88度太阳弧、精确细分与数值候选 | `human_design_solar_root`、`human_design_solar_lattice`及端点／候选整盘模块，由中央`human_design`服务供REST、CLI及MCP共用 |
| 生时范围及联合细化 | `human_design_sensitivity`与区间模块，按明确请求保留有限样本、驻点和预算 |
| 三天体周期及原点比较 | `human_design_cycles`、`human_design_cycle_origins`，人格出生原点为主，设计原点为显式假设 |
| 有限源太阳点质量对照 | `human_design_point_mass`，按`compare_apparent_models`请求计算自己的设计根，不替换原生结果 |
| 名义太阳投影 | `human_design_interval_geometry`经`human_design_solar_projection`进入实际坐标批次的`apparent_position_context` |
| 线义参考 | `human_design_knowledge`经中央`knowledge_registry`及`knowledge_read(domain=human_design)`发布`lines`、`lines_v3`至`lines_v7` |
| 完整盘及上下文参考包核验 | `validation/human_design*`和专用本地CLI，未登记为额外中央REST／MCP工具 |

六个知识类别分别保留其资料覆盖，版本名表示当前可选来源类别。后续目录依赖早期目录及补充文件，不因编号较小而退役。各类别均保留384个键；具有本地待复核转述的条目数依次为12／18／18／24／30／36，其余爻义为空，完整线义独立接受仍为零。

## 三个视位置与几何模块的具名映射

[整数区间实现](../src/fatebridge/core/human_design/human_design_interval_geometry.py)使用缩放整数端点；乘除与平方根向外舍入。正余弦采用精确有理数象限约化及级数，反正切采用半角约化和交错余项界，π采用Machin恒等式。单位球面向量的叉积模与点积给出分离角，名义半径与距离给出太阳角半径，二者相减得到余量。

只有包络两端舍入到同一binary64且分类已确定时才返回；128至8192位有限预算耗尽保留未解决状态。名义半径为695700000米，AU为149597870700米，分类分辨率为原binary64 `1e-12`弧度。坐标输入按其精确有理值处理，不扩大容差或过滤盘缘邻点。

数学来源为[NIST正余弦级数](https://dlmf.nist.gov/4.19)、[反三角级数](https://dlmf.nist.gov/4.24)及[约化方法](https://dlmf.nist.gov/4.45)。Machin关系可直接核对：`tan(2 atan(1/5))=5/12`，`tan(4 atan(1/5))=120/119`，再减`atan(1/239)`得到第一象限且正切为1的角，因此为π/4。名义半径见[IAU 2015 B3](https://www.iau.org/common/Uploaded%20files/IAUGA2015-Resolution-B3-recommended-nominal-conversion.pdf)，AU见[JPL固定定义](https://ssd.jpl.nasa.gov/planets/eph_export.html)。

[便携参考](../tests/data/human_design_interval_flint_v1/README.md)使用python-flint 0.9.0／FLINT 3.6.0及16384位Arb。独立参考以`acos(dot)`计算分离角、`asin(radius/distance)`计算角半径，产品以`atan2(cross-norm,dot)`及自己的整数区间计算。参考方法见[Johansson的Arb论文](https://arxiv.org/abs/1611.02831)、[FLINT 3.6.0](https://github.com/flintlib/flint/releases/tag/v3.6.0)及[python-flint 0.9.0](https://pypi.org/project/python-flint/0.9.0/)。

| 固定参考 | 覆盖与判据 |
| --- | --- |
| 354组几何 | 128随机、40重合／对跖、96近重合／近对跖／小黄纬、90盘缘邻点；1062个标量舍入及354个分类相符，66个解析退化控制不计独立Arb信用 |
| 320组基础运算 | 16／64／128／512／2048位，每组11项，共3520项精确向外格点端点；分母为正，平方根输入按声明钳制至非负 |
| binary64编码 | 原354组的三个标量各取两端，共2124项整数商余数、中点取偶编码相符，参考编码不调用`Fraction.__float__` |

这些固定回归无需原生星历或在线下载。原21627组投影、36个盘缘控制以及后续432组、287组坐标检查各有自己的输入与判据，不合并为独立物理样本量。287组包含99组方向／距离控制、128组宽距离随机输入及60组分类切点邻点；861个标量舍入、287个分类相符，44组解析退化控制单列，另3个非法距离按边界拒绝。

## 有限邻点选根与严格参考

二分收敛后，保留初始相邻括区或精确零点以及四ULP观察窗口。窗口内全部正到负相邻括区和精确零点参与选择，先按绝对精确有理残差、再按较早TT排序；最终端点随所选接触更新，初始括区继续单列。反向交叉保留在观察及候选整盘中，不作为正向太阳弧根。方法标识为`human_design_observed_contact_solar_root_v2`。

[独立枚举参考](../tests/data/human_design_finite_contacts_v1/README.md)不导入产品求根、邻点或残差函数，使用整数binary64编码，覆盖三个正TT量级、两个黄经原点及全部七点三值组合，共13122个函数、48114个可用初始括区／零点窗口。全部端点与选择相符；这一有限集合不证明连续域的唯一性或最优性。

原244组严格参考保持输入、生成器和精确相等判据，目前238项相符、6项失败。失败包括1800年Swiss、2170年Moshier，以及采用较小数值残差邻点的2160年7月、2270年、2350年和2399年末；不能按邻近或残差较小改称严格通过。报告回归逐行核对身份、顺序、精确TT及太阳值、汇总和`--require-exact`退出状态，不固定平台失败数量，也不要求未来必须存在失败。

## 重叠月球文件、私有状态与严格验收的边界

1800年控制中，重叠Moon文件可以影响太阳低位：行星文件仍为`sepl_12.se1`，Moon文件分别为`semo_18.se1`和`semo_12.se1`。两个Moon文件同时覆盖2378487.555370702至2378515.1300229887 TT，版本同为DE441；相同版本标签不保证同一组压缩曲线。所检查的边界处理序列产生精确`17 / 2^44`度差异。

[Swiss原生实现](https://github.com/astrorigin/swisseph)在已打开文件仍覆盖请求时刻时可保留该文件；地球由`Earth = EMB - Moon / (1 + EARTH_MOON_MRAT)`重建，因此地心Moon差异会传至太阳地心位置。普通外部调用保留调用者状态；公开人类图的工作进程和私有源审计分别核对自身实际配置与文件身份。来源回执及内部回放不构成全部原生C缓存的真实性认证。

历史UTC负调整也按来源边界拒绝：1961-07-31最后一分钟秒分量小于59.95，故`1961-07-31T23:59:59.999999Z`无效。依据为[USNO UTC表](https://maia.usno.navy.mil/ser7/tai-utc.dat)的−1/20秒调整及[ERFA 2.0.1日长规则](https://raw.githubusercontent.com/liberfa/erfa/v2.0.1/src/dtf2d.c)；原无效输入保留为拒绝控制，1959／1960时标切换的TT顺序另行检查。

## Moshier原生级数与星历版本差异

原DE440队列保留122个人格TT及122个独立设计TT，共2440项物理位置；判据为同TT视黄经2角秒、设计根5秒。Swiss同TT位置全部通过，最大约0.036755角秒，122根最大约0.061235秒；Moshier的122根最大约2.560396秒，但仍有228项位置超过2角秒。另有18个Horizons锚点核对原参考管线。扩展1200对时刻队列的24000位置及显式点质量对照见[计算说明](human-design.md#显式视位置模型对照)。

| 原DE440队列天体 | Moshier视黄经超差项 | 最大视黄经差，角秒 |
| --- | --- | --- |
| Moon | 3 | 2.245211 |
| Uranus | 9 | 2.400112 |
| Neptune | 88 | 5.009454 |
| Pluto | 128 | 8.451937 |

[作者AA5.6说明](https://www.moshier.net/aadoc.html)及其`readme.404`将行星表标为1995年DE404拟合。八颗行星的32组原生系数／参数数组与作者版数值相同，1952项原级数经度差最多约2.940e-7角秒；这些样本支持实现忠实性，不建立现代星历精度。作者完整版月球级数在Williams／DE403框架退回J2000的候选诊断中更接近DE440，但精确框架、完整视位置、速度与业务资格仍未完成，生产模型未切换。

[DE442文件](https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de442.bsp)覆盖同2440项：Swiss全部符合2角秒线，Moshier仍有209项超差。DE440与DE442天王星黄经最大相差1.892032角秒，因此九项原天王星失败同时保留为参考版本敏感项。CALCEPH 5.0.1与jplephem的4880个DE440／DE442同源几何向量分量差小于1毫米，符合1厘米读取器比较线；DE403的1620项因容器不受支持，原6500向量计划仍为partial。

4096个分层随机留出TT与原244个TT不重合。原生Moshier月球留出视黄经对DE440有59项超差，最大约2.860226角秒，对DE442有57项。作者完整版候选在所声明框架下对DE440几何方向最大约1.260785角秒，4096项均小于2角秒，但其中3978项仍超过另列的0.02角秒诊断线；几何方向不能替代原视黄经判据。

### 同源DE441路径与时钟

完整DE441原文件的几何结果与原生TT数值直接作为TDB的控制一致，4340项最大方向差约8.65e-9角秒。相对于同一TT正确转换后的TDB，留出中近似时钟的方向差最多约0.001068角秒；压缩Swiss与完整原文件在相同近似时钟下最多相差约0.000594角秒。两者与视位置处理分别记录，不相加为误差界。版本与适用范围见[JPL DE440／DE441说明](https://ssd.jpl.nasa.gov/doc/de440_de441.html)。

| 4096个留出上的实际路径 | 对同源DE441的最大ICRS视方向差，角秒 |
| --- | --- |
| 原生Swiss压缩文件 | 0.002418 |
| Swiss输入的显式opaque_solar | 0.001879 |
| 原生完整DE441文件 | 0.002232 |
| 完整DE441输入的显式opaque_solar | 0.001694 |
| 共享有界DE441回退 | 0.000008202 |

共享回退调用既有`ApproximateEphemeris`、`AnalyticObserver`及`de441_source`，使用TDB时钟、接收地球／发射月球、局部TT延迟光锥和光行差。其日期黄经采用Vondrak／77项章动显示框架，留出最大差约0.003061角秒；独立日速验收尚未完成。相同留出对DE440／DE442的0.02角秒跨来源方向诊断，Swiss及其opaque_solar各有907／605项超差，共享有界路径为910／601项。同源一致性不能裁定不同JPL积分的绝对真值。
