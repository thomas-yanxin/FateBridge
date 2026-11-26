# 印占原典与独立数值参考

[源码职责](architecture.md#分层职责) · [实现、来源与未决范围](jyotish.md)

本页维护当前计算的来源、独立参考和固定验收范围。每次运行的测试数、打包文件数、临时观察和工作树状态不属于算法依据；实际结果以当前命令和环境为准。

## 计算职责与来源

| 责任 | 来源与约定 | 保留的未决项 |
| --- | --- | --- |
| 本命位置 | Swiss Ephemeris Lahiri、显式平／真交点、同次精确Ketu对点 | 物理后端、时间尺度和来源窗口分别核验 |
| 十六分盘 | Santhanam卷一第6章；星座分配和线性显示坐标分开 | D30只有星座，没有唯一盘内度数；已冻结FLINT表只覆盖其中八盘 |
| 位置、方向与自然力 | Santhanam第27章、独立选择的Raman七分盘／Drekkana读法 | Drekkana详细条文15 Virupa与摘要60冲突 |
| 相位力 | Raman113–120的有方向分段及附加量 | 原书例53–55矛盾；月亮／水星性质保留条件分支 |
| 时间、运动与星战 | 太阳事件、Santhanam时间分量、具名Simon长期平均模型、Raman76–77星战 | Simon不是Raman1900表；同经、跨零和多人星战不造胜者 |
| 八分法与Pinda | Rao八目标表、Aiyar七目标表及各自削减 | Rao单占据且等值非零的条文缺项保留null |
| 分期与生时网格 | Rao第16章、显式年长、完整父期递归和共同历元量化 | 网格只说明实际样点；名义UTC日与连续SI历时分开 |

来源见证、内部重算、接口一致性和独立数值对照分别验收。Santhanam的另一相位读法作为来源见证保留，不与当前Raman数值混用。

## 原典和独立数值参考

分盘参考采用R. Santhanam译、Ranjan Publications《Brihat Parashara Hora Shastra》卷一固定扫描本。D2、D3、D7、D9、D10、D12、D30对应PDF68、69、70、71、72、73、79页，印刷页分别为69、70、71、72、73、74、80。具体重印版未核定。[馆藏记录](https://elibraryofyoga.com/items/13b2600f-95fd-4bb5-86b4-a18396c68993/full)与[扫描文件](https://elibraryofyoga.com/bitstreams/0a9652fc-4c10-4904-82bd-7e0c331f1961/download)标识所选见证。

[分盘参考](../tests/data/jyotish_varga_flint_v1/README.md)保存12星座目标矩阵、D30奇偶座区段、准则及固定输入。python-flint0.9.0／FLINT3.6.0独立完成精确分区及IEEE binary64最近偶数编码，不导入FateBridge，也不用Fraction／fmpq的float转换生成期望值。开发集13498个角度、验证集1280个角度各覆盖八盘，共118224个输入－分盘组合；修复前267组失败及其全部字段继续保留。

当前分盘所有者在最终交付处分别舍入完整经度与盘内度数。消费者使用同次计算的星座、盘内度数和完整经度，不从已舍入完整经度反算盘内度数。D30的经度和度数均为null。八盘固定表没有覆盖其余八盘的独立参考资格。

## 平均太阳与昼夜互补值的后续对照

[互补值参考](../tests/data/jyotish_complement_flint_v1/README.md)保存26783个固定控制：Simon六组长期平均黄经及太阳对点为12067个开发例和2000个验证例；Nathonnatha为10716个开发例和2000个验证例。修复前5608例太阳字段和4664例夜组不符，原19600个重叠失败字段保留。

Simon等1994[原论文](https://articles.adsabs.harvard.edu/pdf/1994A%26A...282..663S)印刷673–676页给出系数：常数为度，高次项为角秒，时间为J2000起的儒略千年。参考按独立逐幂有理数和计算；生产Horner结果保持精确，Earth加180度后才交付Sun。TT替代TDB慢变参数的约定仍单列。

Nathonnatha依据Santhanam27.8–9，印刷268／PDF267页。给定两个二进制角度后，以精确最短弧分别计算日组和夜组，再各自转换浮点；水星固定60。两组精确值之和为60，不能从已舍入一组反推另一组。

## 力量合计与源式链

[位置力小型参考](../tests/data/jyotish_sthana_total_flint_v1.json)保留三组原失败输入及独立期望值。[时间链参考](../tests/data/jyotish_temporal_chain_flint_v1/README.md)和[位置链参考](../tests/data/jyotish_positional_chain_flint_v1/README.md)分别核对源式结果到前置合计、星战及时间力的传播。

同次Natha、Paksha、Ayana、Uchcha、Sthana和Dig在所属组件保留精确源值；各输出标量只在交付边界舍入。星战前置合计仍按Raman76–77只取Sthana、Dig及Natha至Hora，不包含Ayana。独立字典API尊重实际传入的浮点值和缺项，不从来源回执恢复未交付精度。

时间链固定36组输入、3782个重叠字段的严格binary64差异原为94项；旧1e-12粗门槛在修复前已通过。位置链参考保留16组合与2直接控制、原始差异、因果分支和所选门槛。不同参考的样本、叶分量和重复字段不合并为独立算法数。

## 当前验证入口

[精确数值回归](../tests/jyotish/test_jyotish_exact_reference.py)读取已冻结FLINT资料，不用被测实现重建答案。原典、PyJHora和JPL参考中未随Git分发的资料位于本地 `tests/fixtures/jyotish-*.json` 及 `tests/data/astro/source_materials/`；缺失时报错，不能当作通过。生成脚本在 `scripts/jyotish/`，独立环境和命令见[印度占星验证](jyotish.md#数值与软件验证)。

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q tests/jyotish
uv run --locked --extra dev python -m pytest -q tests/jyotish/test_jyotish_exact_reference.py tests/jyotish/test_jyotish_transports.py
```

[三端检查](../tests/jyotish/test_jyotish_transports.py)分别调用本地REST、stdio MCP和CLI，核对当前合同、未舍入业务事实与同run分页。计算精度、三端一致性、安装包、真实模型解读和远程部署各自验证，历史调用次数不替代当前结果。

## 尚未通过的目标

完整Shadbala、Raman算例内部矛盾、月亮／水星分类、星战特殊条件、Rao削减缺项及不同作者的规则分歧继续保留。PyJHora4.8.7提供独立规则实现对照，但与生产共用Swiss天文库；不能把软件一致当作独立天文真值。物理坐标、框架、时间尺度、来源窗口和完整原典资格见[当前实现范围](jyotish.md)及[分层精度验收](precision-acceptance.md)。
