# 地磁参考与方位换算候选

本分支只由 `fengshui_directions.geomagnetic_reference` 显式启用，规则版本 `geomagnetic_wmm2025_v1@1.0.1`。它提供上游地磁参考，不替用户确认现场磁北，也不自动改写八宅或玄空宅向。原始 `bearing` 保持原参考北；模型换算另存 `conversion.candidate`。

## 资料与所选范围

作者为 NOAA NCEI Geomagnetic Modeling Team 与 British Geological Survey，[WMM2025模型数据](https://doi.org/10.25921/aqfd-sd83)的历元2025.0、阶数12；正式系数来自[官方系数包](https://www.ncei.noaa.gov/sites/default/files/2024-12/WMM2025COF.zip)。90行系数含168个主场项及对应年变化项；不是90个独立球谐系数，也不是高分辨率WMMHR。系数头日期11/13/2024与官网对外发布日期不是同一字段。

本实现用独立第三方 [pygeomag 1.1.0](https://github.com/boxpet/pygeomag/releases/tag/v1.1.0)计算，固定使用仓库中核对过的NOAA系数，不读取库的默认模型，不由模型生成地磁数值。NOAA不对第三方实现背书；官方C复算与外部测试值分别核验。

每次启用该分支时，核对已安装发行版版本、包自报版本，以及 `__init__.py`、`geomag.py` 的SHA-256。期望值来自 `uv.lock` 锁定、校验完整散列的上游wheel，独立清单（本地数据：`../../../tests/fixtures/fengshui_geomagnetic_v1/implementation-reference.json`）保留wheel地址与文件散列。实际版本写入 `model.implementation`，算法源码散列与核对范围写入 `model.implementation_identity`；全局 `run_metadata.runtime.dependencies.pygeomag` 也记录版本并参与环境指纹。不能把固定的“已验证版本”文字当作实际安装版本。

版本／源码不符、依赖或发行元数据缺失、源码文件无法读取时，不输出该模型结果；三端返回既有依赖故障合同。普通方位计算不因此启用地磁分支。当前支持可读取上述源码文件的常规wheel安装；此核对是发行版元数据与磁盘源码身份，**不证明进程内对象未被修改**，也不是防篡改认证。全局环境回执按不可变部署每进程缓存；部署变更需重启，不能用它承诺热更新期间的完整复算。

输入必须明确：WGS84地理纬经度、**椭球高km**、资料来源，以及UTC参考日期或小数年之一。海拔/MSL与椭球高不相同；未知不能填0。引擎限定小数年 `[2025.0,2030.0)`、椭球高 `[-1,850]km`；这是本分支支持范围，不能当成任意空间天气下的物理精度保证。日期按当日UTC零点及该公历年的实际天数换算，不假设当地测量时刻，也不使用出生时间或真太阳时。

## 方位与误差

磁偏角D向东为正；同一方向 `真北方位 = 磁北方位 + D`，再归一到0–360。真北转磁北减D，反向加D。换算候选的八方／二十四山只是模型点估计落区，不能据此确认落山或抹去测量边界候选。

[NOAA误差与限制](https://www.ncei.noaa.gov/products/world-magnetic-model/accuracy-limitations-error-model)给出的D误差估计为 `sqrt(0.26²+(5417/H)²)°`，H单位nT，含义为地表假想测量与模型差的一倍标准差。它不是保证上限、现场罗盘总误差或概率；本分支不把它填入玄空 `bearing_uncertainty_degrees`。高空仍返回该公式的参考数值时，须保留其地表统计作用域。

`H<2000nT`为黑障区，模型不提供方向换算；`2000≤H<6000nT`为慎用区，保留警示。地理极点没有唯一真北方位，也不提供换算候选。数值场量可继续返回，`calculation_status=complete`只表示数值计算完成，不表示方位可用或现场已经确认。

局部钢筋、电器、地壳异常和外部时变磁场会造成模型与现场差异。本分支不查询实时磁暴。应按现场条件复测，不以WMM消除室内磁扰。即使候选为magnetic，也不能直接宣告它满足玄空的已确认磁北输入条件。

## 验收与可解释性

所有场量、换算候选、原始输入、模型系数散列、来源及限制均在同一运行返回；`rulesets` / `rule_trace`增加独立地磁条目，不伪装为古典原文规则。只投影时优先保留完整 `layers.directions.geomagnetic_reference` 与原始 `bearing`。

12组官方简表的84个主场项按发布小数位吻合。系数包100组高精度表的700项中354项超出其最后一位半单位；最大约0.000719nT。NOAA当前官方C也产生相同差异，本实现与官方C另以明确的浮点容差核对。原表差异不删除，不改容差使其通过，不把官方C吻合改名为原表逐位吻合。工程记录和复算方法见[地磁合同](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/fengshui-geomagnetic.md)。

这属于地球物理模型和确定性输入链验证；不属于风水“能够预测现实”的验证，也不证明某部原典的吉凶断语成立。
