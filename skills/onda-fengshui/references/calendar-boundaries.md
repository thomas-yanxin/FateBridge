# 立春边界与时间政策

[场景技能](../SKILL.md) · [基础规则来源](rule-sources.md) · [独立验收](../../../docs/fengshui.md)

命卦、年星与历史宅运分别保留所选换年约定；日历计算不证明某个古本统一采用同一换年或定运事件。立春是地心太阳视黄经达到315°的交点，地点不改变同一交点的真实时刻，时区只影响当地日期与钟时标签。不把春节、2月4日午夜、真太阳时或当前年份替代该交点。

有效年明确覆盖时，以已确认有效年为依据；无须交节求解的命卦不补一个时间或时间政策。仅有出生日期时，按既有日期／边界合同处理，不编造小时；交点不可用时明确失败，不补造边界。宅盘事件只决定历史宅运；年星查询时刻不改写宅运。

保护区内，唯一有效年与年度有效期为null，模型暂取年仅供追踪，候选年区间另列。历史事件两个候选有效年若同运，可以确定宅运而保留年份待确认；跨运则返回完整候选运区间，不能以暂取年选唯一盘。快照和固定释义同步保留这个区别，字段与虚构示例见[事件有效年分层](../../../docs/fengshui.md)。月层也逐项返回候选节月的有效期与实际交节来源；同年内换月仍保留已确定有效年，详见[月区间分层](../../../docs/fengshui.md)。

## 实际求解与精度

`boundary_resolution`、`timing.start_resolution/end_resolution` 及宅运端点分别返回 `provider`、`approximate`、`precision_scope`。`linear_1900_fallback` 是1900固定气近似；`approximate=true` 是实际分辨记录，不能因前端名称变化而漏掉。快照与 `run_metadata.engine_is_approximate` 同步反映真实回退，远离边界的可用结果不因此改成未知年份。

`provider=swisseph` 表示使用该API求交点，不证明实际加载了完整星历文件。`ephemeris_model` 核对所报TT处太阳位置的实际返回标志，作用域在 `ephemeris_model_scope`；`swieph`、`moshier` 与API名称分开。它不是全部迭代调用的逐步日志。Moshier是数值天文模型，不能把它称为固定气回退；它会使外层运行回执标记降级，但不冒称与完整星历达到相同误差。

无外部严格JPL配置时，默认自动模式在1800–2200年使用打包DE440，风水历史端点另用`fatebridge_de440_solar_historical_v1`补足1784–2204范围。`provider=jpl_de440`须连同实际`ephemeris_model`、`solar_model_details`和钟时政策解释。显式解析路线也可返回`provider=fatebridge_analytic`及`fatebridge_analytic_solar_v1`；它是另一具名数值模型，不是固定气回退，也不能改名Moshier。Moshier控制须显式选择原生模式并核对实际返回模型。

数值模型的五秒边界保护与精度验收分开：年界的 `boundary_resolution.uncertainty_reason`、月界的 `precision_policy.boundary_model_policies`、宅运的 `confirmation_reason` 及日期命卦的 `boundary_precision_policy` 必须保留实际模型原因。保护范围内保留候选，不把它解释为误差上界或已经通过一秒门槛；不编造出生小时。选定模型无法求根时返回错误，不以近似值继续分类。无需求交点的已确认有效出生年命卦不新增这些观测。

需取得完整数据时用[安装配置](../../../docs/fengshui.md)。逐文件身份、实际返回模型与独立天文门槛分别验收；仅安装成功不能升级现实预测或古典断语的证据等级。

最新[独立24节气比对](../../../docs/fengshui.md)覆盖1784–2204年10,104个TT交点，默认DE440原始根及输出钟时回算均在固定1秒门槛内。原421项立春及4,812项十二节协议保留，Moshier全量控制仍有1,196项失败。接近交界时，依据同次实际模型、保护原因和全部候选解释；五秒保护不表示已获绝对精度认证。TT软件相合不认证实际UTC钟时、原典日时选表或风水现实效果。

上述Moshier数字属于实际运行该模型的控制记录，不能赋给自动模式或其他具名模型。旧Swiss、解析、SPK及严格JPL路线也按自己的参考、范围和门槛验收。[第二十二轮边界核验](../../../docs/fengshui.md)保留当时修复范围，不追授新版模型、全本原典或现实预测成绩。

## TT、历史UT1与未来UTC

TT动力学交点与民用钟时换算分别核对。每个实际天文分辨记录的 `time_basis` 保留 `root_time_scale`、`civil_policy`、`historical_ut1_convention`、`future_leap_seconds_assumed_unchanged` 和冻结闰秒表有效期。固定气回退不虚构已求得TT根。

按实际引擎政策，1960年前采用Swiss UT1／ΔT约定；带UTC形式的标签不表示当时已经使用UTC。1960按共享引擎的SOFA历史UTC段、1961–1971按IERS历史UTC速率／偏移段换算，1972年起按冻结闰秒表换算。超过表的有效期时，继续使用最后TAI−UTC偏移是显式假设，不是已经知道未来闰秒或实际UT1。快照分别提示历史约定与未来假设；计算完成仍不等于绝对秒级精度已经认证。

日历政策来源见已冻结的[IERS闰秒资料](../../../src/fatebridge/data/knowledge/western-leap-seconds.json)、[IERS历史UTC资料](../../../src/fatebridge/data/knowledge/western-historical-utc.json)与[SOFA 1960资料](../../../src/fatebridge/data/knowledge/western-utc1960.json)。天文外部参考见[JPL DE440技术说明](https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/planets/de440_tech-comments.txt)和[Skyfield节气API](https://rhodesmill.org/skyfield/almanac.html#solar-terms)，它们不对本系统的风水解释背书。
