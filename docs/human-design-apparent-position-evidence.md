# 同次视位置、名义太阳投影与解释依据

[人类图说明](human-design.md) · 本轮验收记录（本地数据：`validation/human-design-apparent-position-verification.json`） · [保留的天文反例](human-design-calendar-span-precision.md)

本文保留视位置证据 `1.0.0` 首次实现的来源与验收记录。当前 `1.1.0` 的[整数区间投影算术](human-design-portable-projection.md)已完成新回执双向严格重放，另保留旧格式 24 份 Linux 拒绝结果；未更换星历、降低旧标准或消除原典分歧。下述首次回归数字不作为当前完整版本的测试数量。

本轮补足太阳附近计算约定的解释与回执证据，没有替换生产星历、改变门线细分或降低原验收门槛。原38项专业要求及其范围保留，完整原典、完整解释与全历法精度仍未验收。

## 来源能够支持什么

[Swiss Ephemeris附录A](https://www.astro.com/swisseph/swisseph.htm)说明，太阳遮掩期间的行星视位置没有直接可见的观测对应；库通过透明太阳质量分布延拓光偏折计算。前轮3.803758角秒反例定位到了这一约定与另一流程的差异，但尚未取得原始人类图软件的算法规范。不能通过挑选较容易通过的后端，宣布原典或天文精度问题已经解决。

[IAU2015 B3决议](https://www.iau.org/common/Uploaded%20files/IAUGA2015-Resolution-B3-recommended-nominal-conversion.pdf)给出的695700000米是名义太阳半径换算常数，不是真实太阳半径或不透明边缘的认证。[JPL星历资料](https://ssd.jpl.nasa.gov/planets/eph_export.html)记载IAU2012采用的天文单位为149597870700米。新几何使用这两个常数，只描述给定坐标中的名义圆盘投影；距离排序另列，不能把太阳前方与后方的目标混同，也不能用这些不同光行时的视位置冒充完整物理遮掩解。

## 计算与解释现在如何绑定

完整结果增加`apparent_position_context`。它保存同次`positions_at_tt`原生调用实际返回的黄经、黄纬、距离、黄经速度与返回旗标；没有为新证据另求一次星历。名义人格侧和设计侧通过内部实际对象关系绑定到各自批次，输出使用确定的批次编号，不输出Python对象标识。

完整物理天体批次包含十个天体，以太阳为参照，对另外九个天体计算天球角距、名义太阳角半径及投影关系。地球激活是既有太阳对点，交点是数学要素，均不伪造物理黄纬或距离。单独太阳求根、单独交点对照和周期搜索的单体调用不在此批次范围内。

参考后端可能中途失败。新增记录保留失败前已返回的物理天体前缀，并单列完整与中断批次数，不补齐未知位置。全量回归发现最初实现会遗漏这些前缀，造成部分结果被错误拒绝；修复前日志、原测试和新增故障注入记录全部保留。补充黄纬或距离不可用时只返回几何未定，不填默认值。

`interpretation.apparent_position_context`逐侧说明实际名义盘投影，附有同run字段引用、原生批次与来源；原有十条结构释义保持不变。完整核验器重建几何，核对批次计数与既有原生来源记录、同侧TT、黄经、速度、模型和旗标，再核对文字及字段引用。重算业务哈希不能跳过这些关系检查。

这验证的是可信原始回执内的数学关系。它不独立认证所报黄纬、距离或原生执行真实性，也不认证任意模型自由文本、384线正文或现实预测。已知旧合同可以继续核验原有内容，明确返回新证据不在旧合同内；当前或未知合同删除新增区、规则集、规则轨迹或解释后仍会被拒绝。

完整回归还发现，新几何检查提前拒绝时会压住既有来源错误诊断；现在保留新拒绝原因并继续原检查。新增来源标识也曾使原8192字符周期卡片额外延后来源信息。交付层现优先省略可从同次不可变清单取得的重复文件定位，保留清单URI、结果身份、散列、有效期及全部业务和来源事实；没有修改原预算、字段选择或失败测试断言。原输出、清单和文件内容保持可无损恢复。

## 独立几何参考与旧结果对照

实现前计划（本地数据：`../tests/fixtures/human-design-solar-projection-plan.json`）固定了前轮全部1200组出生TT及其设计TT、全部九个非太阳物理目标，共21600组几何输入。没有按本次实现结果筛选或删除输入。

[独立生成器](../scripts/gen_human_design_solar_projection_reference.py)不导入FateBridge或Swiss，用mpmath1.3.0、100位十进制精度，将保存的binary64坐标按精确二进制有理数解释。参考文件（本地数据：`../tests/fixtures/human-design-solar-projection-reference.json.gz`）可按固定环境逐字节复现；[检查器](../scripts/check_human_design_solar_projection.py)绑定计划、生成器和参考散列。21600组全部保留，预定几何比较分辨率为1e-12弧度，参考中有7组名义盘内投影。这个几何分辨率没有替换原2角秒天文、5秒设计根或其他既有门槛。

七组预先保存的合成业务对照包含普通出生、已知分歧附近、平交点、生时区间、已公布闰秒、周期及Moshier回退。去掉明确新增的证据、规则轨迹、解释区及相应回执变化后，旧业务字典和全部原有binary64数值保持一致，原生求值次数未增加。这些是开发控制，不是独立出生记录、官方新命盘或盲测。

## 保留的未通过项目

原122组独立参考及228个Moshier失败、前轮1200组参考中的1个所选Swiss失败和2238个Moshier失败均保留。3.803758角秒反例仍影响Tone与Base，不因新增投影解释改记为通过。原15项及扩展86项名称失败、29.1／29.2印刷界分歧也未改动。

专业总审计保留原38项要求，仍有4项失败、3项未完成，包括原始周期口径、官方整盘名称、全历法精度、2001数值分歧、完整原典解释和完整模型忠实性。已有8题模型解释只是开发样本，没有独立留出集；本轮几何与固定模板核验不能替代它。现实预测有效样本仍为0。

## 调用与复核

按需合同增加`apparent_positions`证据视图。视图名称不是请求参数；实际`fields`见[生成合同](contracts/human_design.json)。需要完整批次时读取同run完整结果或交付文件，不能用摘要重算替代原始结果。

```bash
uv run --locked --extra dev python scripts/check_human_design_solar_projection.py --output geometry.json
uv run --locked --extra dev pytest -q tests/test_human_design_solar_projection.py tests/test_human_design_apparent_positions.py tests/test_human_design_apparent_transports.py
PYTHONPATH=.:src uv run --locked --extra dev python scripts/audit_human_design.py --require-professional-acceptance --output professional.json
```

最后一条仍应退出1。具体完整回归、安装包、macOS与Linux、实际外部协议调用及失败运行状态，以本轮验收记录为准；不把局部通过汇总成原典或预测满分。

最终固定快照的2401项人类图测试及17项通用交付测试全部通过；此前2399项运行的5个失败、2401项运行的2个失败均完整保留。离线Linux对同一wheel完成55项选择测试，两平台另各保留24份完整协议回执及12次投影调用。当前工作树也通过55项针对检查；并行的其他体系改动另列，不能把快照验收称为全部当前源码或全部Linux测试验收。本轮5份变更文档的317个本地链接及三种导出示例通过，全仓文档检查仍保留无关归档和并行文档的断链失败。
