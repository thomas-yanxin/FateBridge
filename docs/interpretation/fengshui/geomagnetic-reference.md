# 地磁参考与方位换算候选

本分支只由 `fengshui_directions.geomagnetic_reference` 显式启用，规则版本 `geomagnetic_wmm2025_v1@1.1.0`。它提供上游地磁参考，不替用户确认现场磁北，也不自动改写八宅或玄空宅向。原始 `bearing` 保持原参考北；模型换算另存 `conversion.candidate`。

## 资料与所选范围

作者为 NOAA NCEI Geomagnetic Modeling Team 与 British Geological Survey，[WMM2025模型数据](https://doi.org/10.25921/aqfd-sd83)的历元2025.0、阶数12；正式系数来自[官方系数包](https://www.ncei.noaa.gov/sites/default/files/2024-12/WMM2025COF.zip)。90行系数含168个主场项及对应年变化项；不是90个独立球谐系数，也不是高分辨率WMMHR。系数头日期11/13/2024与官网对外发布日期不是同一字段。

领域内核按[WMM技术报告](https://doi.org/10.25923/prbc-s316)的标量磁势求梯度，采用报告给定的WGS84精确扁率；90行NOAA原系数不变。[勒让德递推](https://dlmf.nist.gov/14.10.E3)经Schmidt半归一化后连同纬度导数计算，正阶项保留 `P/cos(纬度)` 的有限形式，避免在近极区丢失有效数字。每次计算使用独立的50位十进制精度上下文，最后转为输出浮点数。内核标识为 `fatebridge_wmm2025_wgs84_v1`。

`model.implementation_identity`登记椭球、精度与所用计算口径，执行回执另记录实际`mpmath`版本。旧移植依赖及其专属源码核对已移除。上述标识用于解释和复算，不能当作进程防篡改认证；全局环境回执仍按不可变部署每进程缓存，部署变更需重启。

输入必须明确：WGS84地理纬经度、**椭球高km**、资料来源，以及UTC参考日期或小数年之一。海拔/MSL与椭球高不相同；未知不能填0。引擎限定小数年 `[2025.0,2030.0)`、椭球高 `[-1,850]km`；这是本分支支持范围，不能当成任意空间天气下的物理精度保证。日期按当日UTC零点及该公历年的实际天数换算，不假设当地测量时刻，也不使用出生时间或真太阳时。

## 方位与误差

磁偏角D向东为正；同一方向 `真北方位 = 磁北方位 + D`，再归一到0–360。真北转磁北减D，反向加D。换算候选的八方／二十四山只是模型点估计落区，不能据此确认落山或抹去测量边界候选。

换算按输入方位与已交付D的精确二进制值相加减、归一并分区，最后才舍入显示角度；`conversion.angle_exact`以十进制字符串分子／分母保留该和式，`arithmetic_method`为`exact_binary64_heading_conversion_v1`。显示值可能恰好落在分界上，而精确和式仍略在界前，落区应读取同次候选与精确回执，不能从显示角度反算。这只消除换算的中间舍入，不恢复D在主场输出前的精度，不提高现场或地磁物理准确度。

[NOAA误差与限制](https://www.ncei.noaa.gov/products/world-magnetic-model/accuracy-limitations-error-model)给出的D误差估计为 `sqrt(0.26²+(5417/H)²)°`，H单位nT，含义为地表假想测量与模型差的一倍标准差。它不是保证上限、现场罗盘总误差或概率；本分支不把它填入`house.bearing_uncertainty_degrees`。高空仍返回该公式的参考数值时，须保留其地表统计作用域。

`H<2000nT`为黑障区，模型不提供方向换算；`2000≤H<6000nT`为慎用区，保留警示。地理极点没有唯一真北方位，也不提供换算候选。数值场量可继续返回，`calculation_status=complete`只表示数值计算完成，不表示方位可用或现场已经确认。

局部钢筋、电器、地壳异常和外部时变磁场会造成模型与现场差异。本分支不查询实时磁暴。应按现场条件复测，不以WMM消除室内磁扰。即使候选为magnetic，也不能直接宣告它满足玄空的已确认磁北输入条件。

## 验收与可解释性

所有场量、换算候选、原始输入、模型系数版本、来源及限制均在同一运行返回；`rulesets` / `rule_trace` 增加独立地磁条目。只投影时优先保留完整 `layers.directions.geomagnetic_reference` 与原始 `bearing`。
