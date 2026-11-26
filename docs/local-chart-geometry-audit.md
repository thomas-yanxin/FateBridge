# 本地宫位工作几何

`suzhan` 的已知钟时星图和 `otherbu` 的附加天象复用共享天文引擎。本页说明原始角度到星座、宫位和交付记录的转换；星历物理精度与传统规则来源分别核验。

## 工作坐标与落宫

`HouseGeometry` 保存十二个有标签的精确工作宫头及方向。正常宫头必须构成一圈分区，使用无容差的半开区间；整宫从原始 ASC 所在星座开始，等宫从原始第一宫宫头开始。翻转保留第一宫并反转后续宫序。非分区的原生宫头保留原标签，落宫使用同次原生投影的工作相位，不能以黄经排序猜测其空间含义。缺少所需投影时报错。

原始有限浮点输入按其精确有理数值处理，线性派生角度先完成计算，再生成同侧的浮点交付值。共享的黄经显示边界保证 `lon` 在 `[0,360)`、`signlon` 在 `[0,30)`；更多位数不代表更高物理准确度。南交点保留原始北交点的对点，福点保留所选共享公式、实际昼夜与来源。星座和落宫不能由舍入后的显示坐标决定。

R／C／T 投影保留模型、收敛线和误差检查，将 mpmath 工作值精确转换成有理数继续使用。十进制文本及最终浮点宫位不充当翻转的输入。核心星体与上下文复用同次 `HouseCoordinate`，派生交点、福点另算。

## 公开字段

- `houseSystemResolved` 保留实际共享模型键，例如 `equal_mc`。
- `houseAssignmentBasis` 和 `houseGeometryModel` 区分原宫头分区、原生相位、原始 ASC 整宫覆盖与原始首宫头等宫覆盖。
- 原生投影保留实际 `housePositionMethod`、`housePositionProjection`、工作相位及来源。精确地理极点的原生约定明确标注，不能认证为唯一物理解。
- `angleDefinition` 及快照保留极区轴的定义，包括显式整宫覆盖；日期模式不生成宫位，缺少已知钟时星图所需坐标仍拒绝。

## 所选参考宫位缺失

不可用的天文参考轴、宫头和落宫分别保留为 `None`、空列表和 `None`，工作宫位几何为可选值。整宫只在实际 ASC 可用时生成，普通参考布局只在其宫头可用时生成。

星曜记录、历日以及请求的现代／旧等分宿位继续交付。没有参考落宫的星曜在快照中独立列出；`chart.ok` 表示已有星曜记录生成，宫位可用性由 `houseGeometryStatus` 和各空值字段表达。请求参数与实际应用状态分别保留，已知钟时仍是已知钟时。

本地星图展示核心行星列表的七政记录；四余与功能宫属于源引擎的其他结构。`validation.chart_source` 保留规范引擎的原典命度未重建、研究口径和 `classical_acceptance_passed=false` 等限制；`rulesets.chart` 附加其五项来源分组。历法 `rulesets` 字典及已知钟时的三个计算层状态保持原合同。

## 参考与回归

圆周次序使用 [CGAL `Direction_2`](https://doc.cgal.org/latest/Kernel_23/classCGAL_1_1Direction__2.html) 的精确有理数核，并以有理数区间公式交叉核对。相位到有理菱形方向的单调映射是本项目的胶水代码，不能算成 CGAL 独立提供的天文转换。原生宫位和坐标语义见 [Swiss Ephemeris 程序员手册 §16](https://www.astro.com/swisseph/swephprg.htm)。工作数值转换使用锁定的 [mpmath 1.3.0 `libmpf.py`](https://github.com/mpmath/mpmath/blob/1.3.0/mpmath/libmp/libmpf.py) 的 `to_rational`，保留工作数值，而非精确物理解。

便携回归向 REST、CLI 和 MCP 注入冻结的原始核心输入，隔离原生天文库构建造成的末位差异。参考数据、输入范围与来源说明见[固定圆周参考](../tests/data/local_house_geometry_cgal_v1/README.md)及[缺失宫位来源](../tests/data/local_partial_house_v1/README.md)，应用检查见[宫位几何回归](../tests/integration/test_local_chart_geometry_reference.py)。原生天文和非线性投影作为输入，缺失宫位作为交付边界控制，二者不算独立数值落宫成功。
