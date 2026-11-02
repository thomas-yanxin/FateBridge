# 西方占星的计算、原典与验证

本命盘现在分别处理民用 UTC、行星运动的 TT 和地球自转的 UT1。昼夜宗派使用太阳中心的真实地平高度，整宫、象限和 MC 等宫制不能替代地平线。古典混合规则与有明确版本的原典子集分别返回。

七曜日运动沿用前向一 TT 日的五点采样，地心试算不消耗范围外的 UT1；恒星黄道盘按同一 TT 计算 Lahiri 偏移，其速度差分跨越 360°／0° 时按圆周展开，避免制造虚假高速或把逆行翻成顺行。名义宫位和地平仍要求有效 UT1。有限天文对照、同库算术控制、三端回执与尚未通过的 Lilly 印刷例题分别记录，见日运动与角度环绕核验（本地数据：`validation/western-lilly-daily-tt/report.md`）。

## 输入与天文精度

西占可选的`use_true_solar_time=true`旧式出生钟面重置，现按记录时刻解析出的UT1调用均时差，名义出生和生时区间逐点重算共用同一实现。`person_info.true_solar.time_reference`交付记录UTC／TT、实际均时差UT1及未来闰秒假设；德国盘在`base_chart.person_info`下读取。这次只修正均时差输入时标，旧式重置仍须与默认民用时间、明确LMT／LAT输入区分，不能用它推定未知钟时或认证历史精度。96个固定模型时刻、完整盘面与三端回执见均时差时标核验（本地数据：`validation/western-solar-eot-ut1/report.md`）。

内部日期采用Python的前推格里高利历。卜卦可用 `question_calendar`、择日可用 `candidate_calendar` 显式选择 `julian`，默认仍为 `proleptic_gregorian`；其他出生／分析接口仍按已公布的格里历合同处理。日期先转换，再按指定时区校验和转换钟时；不按1582年或地区自动改历。夏令时跳过钟时拒绝计算，重复钟时要求明确UTC偏移，不能暗选其中一次。同一物理时刻的TT、UT1和盘面位置保持一致。

`calendar_conversion` 保留原历法、原日期、原钟时及换算后的本地日期；`analysis_context.input_calendar/input_date` 同样保留原标签，`question_datetime/candidate_datetime` 为内部格里历本地钟时。儒略历1700年2月29日合法，换算为格里历3月11日；格里历同名闰日仍拒绝。输入年采用公元1月至12月编号，不推断英国旧式3月25日换年或双年份。转换超出Python公元1–9999年范围时明确拒绝。`date_label_jdn` 是日期标签的整数日编号，不能当成实际UTC／UT1／TT历元。原典钟时、地方平太阳时／视太阳时及地区改历仍须另核，见历法入口与历史例题诊断（本地数据：`validation/western-civil-calendar/report.md`）。

卜卦的 `question_clock_basis`、择日的 `candidate_clock_basis` 现在可显式选择 `civil`、`local_mean_solar`、`local_apparent_solar`。默认 `civil` 沿用民用时区；`timezone_name` 省略／null时仍采用兼容默认 `+08:00`，回执标明 `legacy_api_default`，不能把它当成已确认地点时区。太阳时必须省略／null时区，避免重复修正。按 [USNO钟时定义](https://aa.usno.navy.mil/faq/eqtime)和[Swiss接口9.4节](https://www.astro.com/swisseph/swephprg.htm)，平太阳时为UT1加东经时差，视太阳时再加均时差（LAT−LMT）；后者按地心视太阳反解，未复原具体日晷的站心、折射或读数误差。

日期规范化完成后再解析声明的钟时。`clock_conversion` 与公开 `clock_input` 字段卡分别保留原钟面、钟时口径、有效民用时区、UTC命名载体及实际TT／UT1；`question_datetime/candidate_datetime` 仍是规范化后的输入钟面，须连同 `analysis_context.input_clock_basis` 解释，太阳时的 `analysis_context.timezone=null`，内部载体时区在 `chart_timezone`。1960年前的UTC命名载体承载模型UT1，不能据名称宣称当时已有原子UTC。太阳时反解复用共享引擎，未改变普通现代输入的物理时刻；钟时数值残差不认证原始分钟记录的准确度。原书未说明的钟时保持未知，不能按上升点或结局拟合。见显式事件钟时核验（本地数据：`validation/western-event-clocks/report.md`）。

卜卦 `question_hour_origin`、择日 `candidate_hour_origin` 独立声明小时日起点：`midnight`（默认）按午夜计0–23，`noon` 的0为同日12:00、12–23为次日00:00–11:00。[Lilly1647第30–31页](https://iiif.wellcomecollection.org/image/b30338724_0065.jp2/full/2400,/0/default.jpg)的星历表按正午起算，午后第14小时对应次日02:00。AM／PM已经换成现代24小时钟面时沿用 `midnight`。日起点与民用／LMT／LAT分开声明，依已确认原页选择，不从年代、地区或ASC拟合推断，也不把制宫表坐标当作提问钟时。

太阳时反解落入UTC闰秒时，卜卦／择日保留原生TT／UT1继续计算，`converted_utc`可返回含`23:59:60`的标签。`clock_conversion.utc_representation`明确区分UTC标签、闰秒与Python datetime可表示性；不要截断、平滑、移秒或把显示限制说成星盘不可算。仍不推断原资料精度、实测EOP、完整原典或现实预测有效性。见物理时刻与闰秒核验（本地数据：`validation/western-leap-epoch/report.md`）。

`clock_conversion.hour_origin_conversion` 保留原历法日期、原小时标签、整数日进位和最终格里历钟面；进位完成后才验证最终日期范围，再处理时区／夏令时或太阳时。该操作是标签规范化，未计算实际持续时长或时区偏移。例如儒略历公元1年1月2日午后第12小时最终为格里历1年1月1日00:00；中间日期无法表示时，`calendar_conversion.normalized_local_datetime=null`、`normalized_date_representable=false`，原标签与日编号仍保留，最终钟面可以有效。不能据中间null否定已返回的最终钟面。验证范围及1978年元旦UT1映射至不可表示UTC闰秒的原有缺口见正午日起点核验（本地数据：`validation/western-noon-origin/report.md`）。

1972 年起，`TT = UTC + (TAI−UTC) + 32.184 秒`。偏移表固定自 [IERS Bulletin C 72](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second.dat)，包含来源指纹及有效期。到期以后的日期沿用最后已知闰秒，并返回 `chart_profile.future_leap_seconds_assumed_unchanged=true`。这是一项假设；未来闰秒并未被预测。1961–1971年使用[IERS历史UTC关系表](https://hpiers.obspm.fr/eoppc/bul/bulc/UTC-TAI.history)的分段偏移和日漂移，1960年使用已声明的SOFA关系；更早输入沿用Swiss Ephemeris的历史UT1／ΔT约定，仍非实测地球自转或原典钟时重建。

行星使用 `swe.calc(TT)`，宫位和地平坐标默认使用 Swiss ΔT 模型反解的 UT1。卜卦／择日可显式选择下述 IERS20 C04 UT1；其他入口及未指定选项的默认路径仍使用模型。`chart_profile` 返回 `calendar/time_scale/julian_day_tt/julian_day_ut1/horizon_method/sect_convention`。实际星历文件模型仍看 `ephemeris_model`，不能只看是否安装了包。[Swiss Ephemeris 官方接口文档](https://www.astro.com/swisseph/swephprg.htm)区分这些时间尺度与 `azalt` 的真实／折射高度。

跨年代位置还依赖对应的`sepl`／`semo`分段。可用现有下载器按固定清单补齐公元1–9999年的34份日月／行星分段，再用`SE_EPHE_PATH`显式选择；这不包括小行星、EOP或未来钟时认证。覆盖与位置专项（本地数据：`validation/western-ephemeris-coverage/report.md`）在同一133个TT时刻、266组日月参考中保留补全前的49项超线和184项不可计算；补全后主机与ARM Linux均符合原0.02角秒线，最大差异约0.00217角秒。参考与数据共享DE441谱系，不是独立动力学或全历元绝对精度证明。普通本命统一来源看`chart_profile.ephemeris_model`；`planetary_models`仅在混合／近似分支出现，详细物理来源也按入口条件交付，不能请求不存在于本次结果的条件字段。共享输入中的非默认`ephemeris_policy`目前只对印占开放。

独立安装版还须核对实际默认发现，不能用仓库已有历表替代安装验收。2026-10-25已将固定清单的34份分段发布到本机用户缓存；未设`SE_EPHE_PATH`的新安装进程可自动发现，常驻进程未重启。相同266组参考由补齐前6组符合原判定线、76组超线、184组不可计算，改善为266组符合；这是默认数据配置的修复，不增加独立天文样本或现实预测证据，见安装版默认历表核验（本地数据：`validation/western-default-data/report.md`）。

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --year-range 1 9999 --dest /tmp/fatebridge-western-ephe
uv run --locked --extra dev python scripts/audit_western_ephemeris_coverage.py --ephe-dir /tmp/fatebridge-western-ephe --output /tmp/western-coverage-audit.json
```

昼夜约定为地心太阳中心、无折射、真实高度 ≥0 为昼。行星的 `above_horizon` 也取实际地平高度，缺少高度时返回未知。行星时采用日出日落分段，有自己的视圆／折射口径；两者在地平附近不能当作同一定义。极区没有适用的象限宫位时仍报错，不悄悄替换宫制。

#卜卦／择日的 `ut1_source=iers_c04` 使用固定版本的 IERS20 C04 最终每日合成值，覆盖 **1962-01-01 00:00 至 2026-09-19 00:00 UTC（含端点）**，共23,638日。来源经 Astropy 官方数据镜像固定提交获取，原始文件与派生包均有SHA-256；没有宣称本次从IERS服务器成功直取。`swiss_delta_t` 保持默认。日间查询先移除真实TAI−UTC（含1972年前漂移／调整），在TT上对连续UT1−TAI线性插值，闰秒不会当普通UTC秒插值。太阳时反解、恒星时与Lahiri选项沿用同一来源；没有外推、预测值或静默模型回退。覆盖外起盘返回错误；地心TT黄经事件搜索直接使用TT星历，不再因无关的试算UT1超范围而返回未知。宫位、地平与日出等仍要求对应UT1来源覆盖。这项可用性修复不提高外部位置核验成绩，见TT事件边界核验（本地数据：`validation/western-tt-events/report.md`）。

`clock_conversion.ut1_reference` 和 `calculation_basis.earth_rotation.ut1_reference` 返回名义历元的源日、日值、形式标准差、插值权重及指纹；公开 `ut1_input` 字段卡可整组读取。模型路径该引用为null。只应用UT1，**未应用极移、天极偏移和日内潮汐**；[IERS C04指南](https://hpiers.obspm.fr/eoppc/eop/eopc04_05/C04.guide.pdf)说明日值与完整地球定向的差别，指南版本为2009年的05C04，不能冒称本实现复现20C04的生产算法。形式标准差不是插值或瞬时物理误差界，数值守卫也不是外部精度认证。数据、参考生成器修正及残留差异见IERS UT1核验（本地数据：`validation/western-iers-ut1/report.md`）。

## 太阳圆面内的位置模型

`chart_profile.apparent_position_policy`、原生推运盘的 `calculation_basis.apparent_position_policy` 和事件历史同名字段，说明标称历元的太阳偏折模型。公开 `solar_position_model` 字段卡可读取这一层。它按未偏折有限视线区分太阳后方、太阳前方、圆面外及边界疑义；未核对版本或不支持的后端保留 `not_evaluated`。月亮、太阳自身和虚点不在此几何覆盖范围内。

[Swiss 官方文档附录 A](https://www.astro.com/swisseph/swisseph.htm)说明：太阳后方不可见天体的位置，采用透明太阳质量分布作连续延拓。`virtual_continuous_solar_disc_extension` 表示这种约定；前景凌日不能据投影重合误报成位于太阳后方。这不是光学遮掩、太阳边缘接触或实际可见性求解，`maximum_physical_error_arcseconds=null` 也不是零误差。

固定291个天体／历元的新增 JPL 开发对照中，65组背景延拓与 JPL 视位置存在明显差异；关闭偏折可诊断这层差异，却会破坏圆面外的对照。因此默认坐标保持原样，原0.02角秒比较仍记失败，不能靠切换约定过线。来源、完整分母与工程复跑见位置模型核验（本地数据：`validation/western-solar-position/report.md`）。

### 朔望与行星时

出生前朔望现在在 TT 上对日月视黄经差的0°／180°交点括界求解，选取严格早于出生 TT 的最近一次。事件以跨越后首个可表示 JD 记录；出生 TT 恰好等于该事件 JD 时，选前一次朔望。`classical.syzygy` 保留 `julian_day_tt/julian_day_ut1/event_datetime_utc/solver`，旧 `julian_day` 明确为 UT1。新月取太阳经度，满月取月亮经度；恒星黄道使用朔望事件历元的原生 Lahiri 坐标，不能将回归黄经直接写入恒星盘。事件小数位数是数值表达，不是外部观测精度。

`classical.syzygy.ephemeris_source`另行记录整个朔望搜索和恒星黄道显示实际使用的模型、样本上下文与文件身份。`models_stable=false`表示其中发生模型切换；不能把出生历元的Swiss来源概括为整个搜索的来源。支持的降级结果保留并披露，不通过删除它们伪造一致；回执不认证跨来源函数的连续性或事件绝对精度。原生坐标框架、视位置约定、有限值、请求日速及文件完整性出现矛盾时返回来源错误，不能把错误吞成“未提供朔望”后继续评分。

`classical.syzygy.utc_representation`把日期显示与朔望计算分开。公元1年初的出生前朔望可落在天文年0（纪元前1年）；现在保留原有TT／UT1、经度、来源及其参与总主星的计算，`event_datetime_utc`可使用扩展纪年标签，并返回`datetime_representable=false`，不因Python日期范围而删除整项朔望。该字符串是标签，不能无条件交给`datetime.fromisoformat`。闰秒和历史非唯一UTC表示也复用共享标签机制；1960年前的UTC命名载体仍是模型UT1，不能声称当时已有原子UTC。公开出生输入范围仍为公元1–9999年，数值格式不认证历史钟时或天文绝对精度。

行星时从实际相邻日出／日落建立昼夜弧，各等分12段，以左闭右开区间分配小时。原先固定向前减24小时，会在日出逐日提前时选到更早一天的日出；2026年4月15日格林尼治日出后1秒曾因此被标为火星日昼第8时，修复后为水星日昼第1时。日主读取开启该行星日的日出在用户时区中的民用星期；UT1先转TT，再按冻结UTC政策转民用时间，不能把UT1日历字段直接当UTC。

保留的行星时日出口径为海平面、1013.25 hPa、0°C、含折射的太阳中心。它与[通常年历采用的太阳上边缘日出](https://aa.usno.navy.mil/faq/RST_defs)有差别，也不能代替本命宗派的地心真高度判据。`planetary_hours.sunrise_convention`、弧与小时的UTC起止时间、UT1弧端点均返回。极区缺少相邻适用事件或转换失败时返回未知，不夹限到第1／12时，也不伪造日出。

小时主星顺序与24时跨日递推的限定原典依据为[Cassius Dio《Roman History》37.19，Loeb 1914](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Cassius_Dio/37%2A.html#19)。该段并未指定现代折射或不等时几何；`source_scope` 明确分开这些实施政策，手工标注仍待独立校勘。

朔望与行星时审计（本地数据：`validation/western-lunations-hours-evidence.json`）使用[美国海军天文台2026年月相表](https://aa.usno.navy.mil/calculated/moon/phases?year=2026)的全部25次新月／满月作独立分钟级对照，固定容差60秒；按其[UT定义](https://aa.usno.navy.mil/faq/UT)比较UT1。日出前后检查属于声明口径的行为回归，尚未获得独立日出几何或现场天气验证。

```bash
uv run --locked --extra dev pytest -q tests/test_western_lunations_hours.py tests/test_planetary_hours.py
uv run --locked --extra dev python scripts/audit_western_lunations_hours.py --output /tmp/western-lunations-hours.json
```

出界比较使用出生历元的真实黄赤交角，返回 `classical.obliquity`，不把当代固定阈值用于全部历史日期。星历存在但角度或地平计算退化时，整体精度标为混合，并保留 `angle_method/horizon_method`。

保留的 `use_true_solar_time=true` 是历史兼容的钟时重置，会改变计算时刻；它不是改善西方星历准确度的选项。普通西占使用默认的民用钟时。远古历法、历史时区精度、观测坐标精度、极区与近似轨道仍需分别验收。

## 推运、返照与主限坐标

推运底座现在直接使用 `fatebridge_swisseph_native`，与本命盘共用 TT／UT1 政策，保留内部完整黄经、小数秒及用户输入的纬度。`natal_reference.calculation_basis`、行运／次限／返照的 `calculation_basis` 返回星历模型、时间尺度、TT／UT1、未来闰秒假设和黄道偏移。恒星黄道采用明确的 Lahiri 偏移，整宫宫头按该黄道的星座边界确定；不沿用第三方库的默认偏移或极区纬度夹限。

太阳和月亮返照求解 TT 黄经的有括界零点，取不晚于分析时刻的最近一次。未找到括界就报错，不能补一个未来返照。`solver` 返回目标与求解黄经、残差及 `event_not_after_analysis`；`return_datetime_utc` 与带原时区偏移的 `return_datetime` 都保留秒以下数值。这些位数表示求解器的数值精度，实际误差仍受星历、输入和未来时间尺度假设限制。

主限的赤道投影现在使用 TT 星体坐标和 UT1 恒星时，MC 保留真实赤纬；半弧方法的 ASC／MC 使用实际赤纬和半弧。两种投影都测试零推进量还原原盘，恒星黄道在投影前后显式转换。半弧方法遇到恒显／恒隐点时拒绝无定义投影，不用任意极小分母制造坐标。现有 `axis_static_key` 与 `mundane_semiarc_static_key` 仍是带明确近似标签的方法；数值修复不等于完整复现某部原典的主限体系。

## 数值边界与显示

本命、关系盘和推运的数值坐标保留计算精度，星座、宫位、相位及古典条件均使用未舍入值。四位小数舍入曾让白羊末度同时显示为黄经30°、星座内30°，并让刚超过8°容许度的相位进入结果。现在坐标满足黄经 `[0,360)`、星座内度数 `[0,30)`；`chart_profile.aspect_policy` 集中交代现代容许度政策；`aspect_evidence` 保留逐项的 `separation/exact_angle/orb/orb_limit/rule_id`，可直接核算。常规 `aspects` 仍给出完整命中列表与未舍入的偏离度，首轮摘要无需重复每条的政策元数据。公开模型拒绝不可能的坐标。

导出中的“星座＋度数”统一为星座内度数。例如绝对黄经75.123°显示为“双子15.12°”；末度接近边界时显示29.99…°，保留所在星座。JSON保留数值精度，文本位数不表示观测精度。

边界、原典配对和解释反事实的可复现审计（本地数据：`validation/western-fidelity-evidence.json`）与测试见 `tests/test_western_semantic_fidelity.py`。这是限定条件的自动检查，不给自由文本或整个专业系统自评满分。

34个西占 REST 基线在规定的 Linux x86_64／Python 3.12 环境逐字节核对，迁移记录见基线验收（本地数据：`validation/western-linux-golden-migration.json`）。可运行 `uv run --locked --extra dev python scripts/audit_western_golden.py --output /tmp/western-golden-check.json` 重验；此命令只核对、不重写基线，且拒绝用其他平台代替参考环境。基线证明回归一致，独立天文准确度仍由下文的 NASA／香港天文台资料验收。

## 关系盘的时间、空间与方法

关系盘的双方基础盘及 Davison／Marks 实盘，直接复用相同宫制、黄道和时刻的本命盘结果，保留原生 Lahiri 坐标、含纬度的宫位计算及 TT／UT1 依据。影响图盘另声明为将源星体黄经放入对方宫头扇区的符号叠盘，不冒充同一时刻的地平重算。

`davison_variant` 在嵌套 REST 与扁平 MCP／CLI 输入中使用同名参数；只对 `TimeSpace` 和 `Marks` 有效，其他模式不会静默接受非默认变体。方法依据为[Astrodienst 的 Davison 变体说明](https://www.astro.com/cgi/h.cgi?f=gch&h=gch64&lang=e)：

| 参数值 | 时间 | 地点 |
| --- | --- | --- |
| `uncorrected`，默认 | 两出生时刻的模型 UT1 JD 算术平均 | 纬度平均、经度先按短弧展开再平均 |
| `corrected` | 从未校正中点附近括界求解，使回归黄道 MC 对齐双方 MC 的中点子午轴 | 同未校正地点 |
| `spherical` | 同未校正时间 | 球面最短大圆距离中点，非 WGS84 椭球中点 |

例如179°E与179°W的经度中点在日期线，不能算成0°。经度展开、模型UT1平均和小数秒政策是明确的实施约定；来源只描述平均出生时间，未规定原子时间细节，本实现不宣称与 Davison 原书逐字校勘。MC校正按[Astrodienst FAQ 的“子午轴”口径](https://www.astro.com/faq/fq_fh_round_f.htm?lang=e&nho2=2&nhor=2)选择接近原中点的方向，保留目标、实际MC、校正秒数与残差；未直接改写MC坐标。参考地点重定位变体尚未接入。

组合盘采用[Astrodienst 的对应中点法](https://www.astro.com/faq/fq_fh_compo_e.htm)，星体、ASC、MC及适用宫头分别取短弧中点，不自动把水星／金星移到相反方向。它没有真实出生时刻或出生地点，`positions_from_single_instant=false`；符号纬度平均亦明确标记。精确相隔180°的两点没有唯一短弧中点：组合盘报告歧义；比较盘的中点目录保留两个未决候选，交换输入不会随意选另一端。相位和中点命中使用未舍入数值，`relative_midpoint_policy` 与逐项 `aspect_evidence` 可核查。

`Marks` 现在分别计算“甲与双方Davison资料的Davison”和“乙与双方Davison资料的Davison”，以 `marks_charts.inner/outer` 返回；`chart` 为内方个人盘，`primary_chart_role=inner`。旧版组合盘与时空盘混合坐标的算法已撤除，不能再解释为 Bob Marks 方法。计算配方来自[Bob Marks 作者课文镜像](https://astroer.com/htmls/bob/bobmar/markschart28.0.htm)；原站返回404、镜像尚未与原始存档校勘。作者的个案成功陈述未被采纳为有效性证据。 公开 `marks` 字段卡保留双方的 `marks_charts`，安全联合视图亦保留此根；非Marks模式为空对象。旧 `chart` 仅为内方别名，不能被当成共同盘或复制给外方；字段卡主层为 `marks_chart_pair`。

各模式共用两张本命盘的七曜与跨盘相位计分，`compatibility_evidence.source_paths` 指向同次返回的本命资料与相位表。关系分数的 `compatibility_policy` 交代七曜元素／模式重叠、相位加减及三项平均，是 FateBridge 自定义启发式，未作经验校准。v2 按未舍入容许度选择最紧密24条，并保留第24条处的全部精确并列项，因此入选数可能超过24；名称或甲乙顺序不再决定舍弃哪条。只差一个浮点步长也不是并列，不设人为 epsilon。元素／模式分先舍入，再与截断到0–100的相位分取平均；均为最近整数、半数取偶。`compatibility_evidence` 保留人数分布、重叠计数、分母、入选相位在同次 `synastry_aspects` 中的索引、逐项±4、截断前后分数及平均过程；空相位的50是规则基线，不是观察到的关系质量。投影入选明细时选择整个 `selected_contacts` 数组。

该修复纠正计算对称性，不校准评分的专业解释。冻结的合成角度反例中，旧版交换甲乙得到64／67，新版双方均为63；测试同时覆盖边界修复让分数升高或降低，不能以“分更高”作为验收。24条名额、所有合相一律加分及等权平均仍是粗略产品约定，尚无原典或经验依据认证。评分审计（本地数据：`validation/western-relationship-scoring-evidence.json`）保留反例、政策及来源指纹。文本导出增加“自定义评分依据”；其中长数组沿用通用摘要上限并显示省略提示，逐项复算应读取同次完整JSON。

原典关系判断的缺口也需单独保留：[Ptolemy《Tetrabiblos》IV.7，Robbins 1940](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/4B%2A.html#7)优先考察双方日、月、上升和福点的星座关系，并继续考察位置高低与其他行星的见证；它没有给出此处的七曜百分制。当前自定义评分尚未实现该章完整判断链，不能称为该章的实现，也不能将其综合分解释成关系成败概率。

球面几何有47个来自独立 GeographicLib 2.1 的冻结参考（本地数据：`../tests/fixtures/western-geographiclib-midpoints.json`）；该参考只证明所列球面中点，不验证MC星历或原典解释。关系盘审计（本地数据：`validation/western-relationship-evidence.json`）与 `tests/test_western_relationship_geometry.py`、`tests/test_western_relationship_transports.py` 分开记录外部几何、内部一致性和真实三端协议检查。

```bash
uv run --locked --extra dev pytest -q tests/test_western_relationship_geometry.py tests/test_western_relationship_transports.py
uv run --locked --extra dev python scripts/audit_western_relationship.py --output /tmp/western-relationship.json
uv run --locked --extra dev python scripts/audit_western_relationship_scoring.py --output /tmp/western-relationship-score.json
```

## 宫位与四轴的独立核验

`equal_mc`（Swiss `D`）的标准名称更正为“天顶为第10宫宫头的等宫制”；[官方接口定义](https://www.astro.com/swisseph/swephprg.htm)明确规定第10宫宫头为MC，原先的“中点”标签不忠于计算。旧中文名称仅保留为输入别名。等宫头从原始锚点一次旋转，避免先算MC+90°、再旋转回第10宫造成二次舍入；落在浮点边界时保留精确输入和整周旋转所确定的星座分区。这不增加出生资料的精度或天文信息。

独立采集协议（本地数据：`../tests/fixtures/western-houses-protocol.json`）先固定1角秒容差，再用 PyERFA 2.0.1.5／NumPy 2.5.4 的 IAU 2006/2000A 恒星时、真黄赤交角及向量平面交线求ASC和上子午线MC；另外编译 Astrolog 8.00 固定提交的独立宫位算法，禁用其 Swiss／Placalc 后端。保留1900–2099年、七种纬度、三种经度的126个天球几何输入以及每个输入的13种宫制输出。TT／模型UT1由 FateBridge 作为共同输入提供，故本研究独立检查几何与旋转，不独立验证历法、时间尺度或实测EOP。

修复前审计（本地数据：`validation/western-houses-independent-evidence.json`）保留原始失败证据：ASC／上子午线交点84/126组满足固定容差；13宫制共1638组中1068组满足容差、72组方法无定义、498组存在差异。旋转基准修复后的完整审计（本地数据：`validation/western-rotation-independent-evidence.json`）为126/126组轴满足同一容差，宫头1488组满足、72组无定义、78组仍有差异。全部样本及预先固定的阈值均保留；完整审计仍返回非零。无定义和 Astrolog 的替代宫制不计为数值通过，剩余差异涉及其十次固定迭代的 Placidus、极区宫头和MC分支，尚不能全部归因于某一实现。

修复前最大ASC差约74.50角秒，上子午线MC约1.98角秒。[Swiss 2.10.03源码](https://github.com/aloistr/swisseph/blob/v2.10.03/swephlib.c)及[官方说明6.1节](https://www.astro.com/swisseph/swisseph.htm)表明原生恒星时在1850／2050年转换长期表达式。现在按 [IERS Table 5.2e](https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt)实现ERA、多项式、章动及34项补充项，沿用当前Swiss章动和平均黄赤交角。在J2000前后两个儒略世纪采用此表达式，1850–2050的原生路径保持；外侧保留Swiss长期变化并在相应边界作常量相位对齐。窗口位置及对齐常量为FateBridge策略，不能说成IERS规定的精度保证；远古／远未来绝对精度和导数连续性尚未认证。

适配仅使用公开Python接口：根据“地方恒星时＝格林尼治恒星时＋经度”对传给底层几何的经度参考架作旋转，公开出生地经纬度保持原值。宫位、地平坐标和日出事件由同一共享入口处理；事件在返回时刻迭代相位，未收敛时报错，并恢复观察者状态。运行时不新增ERFA或NumPy依赖，也不使用部分Windows轮包未导出的私有C函数。Windows检查目前限于轮包导出表，尚无本轮真实Windows执行证据。

剩余差异进一步按几何定义核查：Placidus方程诊断（本地数据：`validation/western-placidus-equation-diagnostic.json`）对全部126组保留记录，在90组可定义输入中，独立以ERFA的ARMC和真黄赤交角求第11／12宫半昼弧方程残差；Swiss最大约0.0059角秒，Astrolog约3077.36角秒。这支持继续调查独立实现的固定迭代收敛问题，但本诊断是在发现差异后建立，不设追认通过阈值、不更改原始参考答案或完整审计状态。R／C在极区交换MC／IC还见[官方6.4节](https://www.astro.com/swisseph/swisseph.htm)；T的对应分支仍需源码及方法复核。这里核对的是公开几何定义，不能冒充Placidus原书的版本验收。

`chart_profile.earth_rotation`和原生推运盘的`calculation_basis.earth_rotation`公开模型、TT／UT1历元、适用窗口、长期对齐及已选择的UT1来源／未应用的其余EOP修正等边界；近似四轴不会冒充此原生模型。另有独立ERFA公式核参考（本地数据：`../tests/fixtures/western-rotation-kernel-erfa.json`）：12个共同TT／UT1及章动输入，固定0.001角秒阈值；它检验公式实现，不检验UTC换算或观测精度。部分象限宫制的另一端MC单列于各宫制结果，不能混入物理轴误差统计。原典完整覆盖及实际模型解释仍须继续验收。

```bash
git clone --depth 1 --branch v8.00 https://github.com/CruiserOne/Astrolog.git /tmp/astrolog-house-reference
uv run --locked --extra dev python scripts/build_astrolog_house_oracle.py --source-dir /tmp/astrolog-house-reference
uv run --locked --extra dev --with pyerfa==2.0.1.5 --with numpy==2.5.4 python scripts/gen_western_houses_reference.py --protocol tests/fixtures/western-houses-protocol.json --astrolog-executable /tmp/astrolog-house-reference/house_oracle --output /tmp/western-houses.json
uv run --locked --extra dev python scripts/audit_western_houses.py --output /tmp/western-houses-audit.json
uv run --locked --extra dev python scripts/audit_western_placidus_residuals.py --reference tests/fixtures/western-houses-erfa-astrolog.json --output /tmp/western-placidus-residuals.json
uv run --locked --extra dev --with pyerfa==2.0.1.5 --with numpy==2.5.4 python scripts/gen_western_rotation_kernel_reference.py --output /tmp/western-rotation-kernel.json
```

构建需Git和C++编译器；本次采集使用Linux x86_64／Python 3.12。源代码数学部分未改写，配置、编译器、可执行文件和结果均保留指纹；这里只将原始公式入口接到固定几何输入，不使用 Matrix 行星位置。该编译产物属于独立校验工具，不是运行时依赖。

## 极区天球四轴与制宫分支

同一地点与时刻的天球子午线MC不随宫制变化。Swiss [6.4节](https://www.astro.com/swisseph/swisseph.htm)说明部分极区宫制会交换MC／IC，并使用逆向宫序；[固定版本源码](https://github.com/aloistr/swisseph/blob/v2.10.03/swehouse.c)也包含Polich-Page的相反分支处理。FateBridge现在以E计算中的东侧地平交点及赤经等于ARMC的子午线交点作为公开ASC／MC，保留所选宫制的原始宫头和落宫投影。存在相反分支时，`chart_profile.house_axis_convention`及推运的`calculation_basis.house_axis_convention`同时提供公开轴、原生制宫轴、黄道坐标系及来源；公开MC不要求等于第10宫宫头。该公共字段定义是FateBridge的显式选择，不能当成所有流派唯一的MC用语。

修复前，1900-01-01 00:30 UTC、经度0°、纬度−80°的同一输入，整宫MC约106.3271°，Regiomontanus／Polich-Page却将286.3271°的制宫分支直接放进公开MC。修复后公开MC统一，制宫分支及第10宫宫头仍为原值；热带／Lahiri及推运盘都核验，宫头与星体落宫没有为追求软件一致而重排。独立记录（本地数据：`validation/western-polar-independent-evidence.json`）保留126组原几何、1638次方法请求与72次无定义结果；1566组可定义方法的公开ASC／MC满足原定1角秒容差。该范围是几何检验，不包含独立历法／实测EOP验证。

另按预先固定的求根协议（本地数据：`../tests/fixtures/western-placidus-root-protocol.json`）建立Placidus独立二分参考（本地数据：`../tests/fixtures/western-placidus-bisection.json`）。对完整黄道各点均有升落的域，以半昼弧／半夜弧方程在赤经区间单调求根；算法不导入FateBridge或Swiss数值函数，不读取Astrolog宫头来求解。90组可定义输入的全部12宫头满足原定1角秒容差，36组域外输入明确保留。Astrolog只在其中54组满足同一容差，支持其固定迭代收敛差异的诊断。既有13宫制完整审计及其78组原始差异继续保留，不能用新子研究替换完整目标，也不能据此宣布Placidus原书版本验收完成。

服务层重建解释后，实际产生的极点／交线条件、相反制宫轴及轨道回退说明现在保留在摘要和文本导出。真实模型能否正确读取这些依据仍需单独验证。

```bash
uv run --locked --extra dev python scripts/gen_western_placidus_roots.py --reference tests/fixtures/western-houses-erfa-astrolog.json --protocol tests/fixtures/western-placidus-root-protocol.json --output /tmp/western-placidus-roots.json
uv run --locked --extra dev python scripts/audit_western_polar_geometry.py --reference tests/fixtures/western-houses-erfa-astrolog.json --roots tests/fixtures/western-placidus-bisection.json --output /tmp/western-polar-audit.json
```

## 相位边界与瞬时入出相

本命、关系相位、映点、关系中点和共享推运相位，现按输入浮点数的精确值完成圆周差、派生中点、容许度比较与排序，再转换成公开小数。所有既有容许度保持不变，也不加模糊的数值宽限。这里保存输入已有的区别，并未增加出生资料或天文观测精度；[Python数值说明](https://docs.python.org/3/library/fractions.html)也明确区分浮点数的精确值与使用者原本想输入的十进制数。

例如水星 `0.5000000000000001°`、土星 `352.5°` 的最短黄经差略大于8°，旧算法在相减／跨周界时舍入为8°，误收为合相；修复后排除。原始失败（本地数据：`validation/western-modern-aspect-wrap-open.json`）保持原样，由独立十进制审计（本地数据：`validation/western-angular-predicates-evidence.json`）另记解决情况。关系中点与映点的后续比较保留精确中间量，避免先显示再归类；线性黄经算式转回浮点时保持在原来的半开星座区间内。该例是合成边界输入，不是已观测的天象或预测命中。

旧入出相算法推进0.05天（72分钟）再比较，可能跨过精确成相点而反向分类。例如黄经0°、速度13°／天的天体正接近位于0.1°的静止目标，当前仍在入相，旧算法却判为出相。现在依据当前黄经差与有符号相对速度判定，`classical_patterns.aspect_motion` 分列 `applying`、`separating`、`exact`、`stationary`（相对黄经同速）及 `unavailable`；精确、同速与未知速度不再当作出相。距离与速度依据、方法及边界保存在 `application_policy`，正文与导出同时列出状态。独立卜卦引擎也已同步采用该判定，并取消黄经／速度先舍入的路径。

[Robbins 1940 I.24](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html#24)的接近／离开概念是此处明确限定的参考；该章还区分合相的黄纬条件、相位射线及其他效力条件。`ptolemy_latitude_condition` 现单列合相黄纬同侧／异侧／缺项；相位射线标为无需该项。使用共享闭半球约定，位于黄道上的天体可与任一侧共享半球，此零点约定明确保留。判定直接比较符号，避免极小异号纬度相乘下溢成零；未知纬度不补零。此条件不改变现代黄经相位列表，也不独自建立完整的托勒密入相；未来成相、停滞反转及全部效力条件仍待验收。结构化状态经过本地 REST、原生 MCP、CLI 的完整输出与严格投影核对；实际模型的自由解释仍需单独检验。

`astro_chart`、`astro_chart13`、`astro_hellen`、`astro_india`、`astro_germany` 发布 `aspect_motion` 证据视图，将星体、相位、格局与适用限制一起读取；使用时把视图的 `fields` 复制到请求，视图名称本身不是请求参数。本轮验收（本地数据：`validation/western-angular-verification.json`）分别记录独立算术、原始输入回放、三端、快照和安装包，保留范围与未完成项。

```bash
uv run --locked --extra dev pytest -q tests/test_western_angular_predicates.py tests/test_western_angular_transports.py
PYTHONPATH=src:. uv run --locked --extra dev python scripts/audit_western_angular_predicates.py --output /tmp/western-angular-audit.json
```

## 卜卦月亮事件与Lilly条件

卜卦从明确提问时刻起盘。`horary.moon.motion_basis` 使用与起盘相同的TT、地心视黄经、黄道与星历配置，搜索月亮下一星座界前严格未来的主相位。每30分钟扫描后，按黄经差给根定界并二分到相邻可表示JD；保留实际事件黄经、TT、UTC、根区间和物理星历来源。该步长不是事件时刻精度，原生模型也不是观测精度认证。月亮与各目标的相对运动必须满足所声明的顺行／单调条件；7天只是搜索保护界，失败返回未知。事件根区间与入宫根区间重叠时，也保留边界未决，不强行判为没有相位。

旧算法只查看当前容许度内的入相，并用相位距离代替月亮将行经的度数。因此会漏掉当前容许度外、出宫前能成的相位，也会把移动目标导致出宫后才能成的相位收进去，还可能按距离错排时间。生产调用现用实际星历逐次求根；仅供直接几何研究的恒速投影另有方法名，不用来冒充原生搜索。

原生Lahiri起盘与月亮事件共用严格的原生岁差偏移：运行失败、非有限值或失败标志均不能改成线性近似后宣称成功。起盘失败返回错误；只有事件搜索失败时返回未知，也不把它当成空亡。已选择星历的数据一致性错误仍按原错误类型传递。遗留近似调用的显式回退另保留，不能给原生路径背书。

预先固定的协议（本地数据：`../tests/fixtures/western-horary-motion-protocol.json`）选择三个TT窗口、四天长度与10分钟JPL网格。独立采集器不导入生产代码，先由[JPL observer表的TT与视黄经](https://ssd-api.jpl.nasa.gov/doc/horizons.html)建立事件参考，再比较原生二分解。核验（本地数据：`validation/western-horary-jpl-evidence.json`）保留12,117组位置、全部事件顺序与时刻残差；原定位置容差2角秒、时刻容差30秒均未修改。该有限窗口不能认证其他历元、全部空亡流派或完整卜卦判断。

所选 [Lilly 1647原书](https://wellcomecollection.org/works/s7z7c46y)第112页以离开前星、在本星座内是否继续应用来谈空亡。此处工程查询为“严格未来黄经成相是否早于下一星座界”，`apply`、`forthwith`、历史容许度及此前分离背景的文本条件尚未全部验收，不能把两者视为唯一等价定义。无出宫前相位，也不直接证明现实事情不成。

原书图像及人工标注（本地数据：`../tests/fixtures/western-lilly-motion-1647.json`）分别记录第111页的传光定义、第125–126页的成事判断。第111页例子为白羊土星20°、火星15°、水星16°：水星把火星的光传给土星，两端本来就有合相，故不能加上“两端必须无相位”的限制。传统轻重次序也不等于某一瞬间速度排名；停滞的月亮不会因此变成比土星更重的聚光星。共享格局现核对这两点，并通过 `light_configuration_policy` 标明仍是结构候选。

第126页另外涉及接纳、遇到其他星之前的真实顺序及其他成事条件；不能拿当前入出相替代。`horary.perfection.candidate` 保留已算的结构，`perfects=null` 表示成事路径尚未核完，两造同主星也不自动构成独立成事证明。当前完整判词为 `uncertain` 并列缺项；旧代理规则的 `heuristic_verdict` 仅留作明确标注的研究对比，严格 `motion_conditions` 视图不读取它。这是保留待完成的实际方法缺口，不是将“所有条件均未知”认作原典验收通过。

### 黄经方位与水星昼夜归属

`classical.orientality_policy` 及 `classical.ptolemy.orientality_policy` 交代共享东方／西方判断的范围。原角差函数已使用有理数，本轮去除其调用方的0.0001度死区，保留非零输入的实际阶段；对分两侧的结果保持不变。水星阶段传到昼夜归属、`sect_placement` 和 `in_halb`；这些是给定坐标与所选传统下的条件，不能据此增加观测精度。精确合相保留未知，精确对分沿用既有东方端点约定。

Lilly第114页分别讨论上行星、金水和月亮；共享几何端点约定尚未认证为这些作者／对象的完整过渡规则。黄经阶段也没有求解实际升落或偕日可见性，三项对应认证字段保持false。独立角度参考、实际后端探测、完整输出差异及原门槛保存见边界核验（本地数据：`validation/western-orientality-boundaries/report.md`）。

### Lilly本质尊贵与有向接纳

`horary.planets` 保留七曜未舍入状态与 `essential_condition`。规则 `lilly_christian_astrology_1647_p104_112_v1` 按原图人工标注（本地数据：`../tests/fixtures/western-lilly-reception-1647.json`）计算第104–105页指定表：三分随实际昼夜，水象由火星兼管昼夜；界与面按声明的半开区间比较。表头虽称“依Ptolemy”，仍不能替换为Robbins1940界表，例如狮子起界的星主就不同。擢升的星座尊贵与所列特定擢升度数分别记录。所选范围为七曜，不包含原表中的交点格或全书判断。

接纳回执明确 `receiver`、`guest` 与 `guest_longitude`：接纳者在客星所在度数持有尊贵；互纳要求两个方向都成立，同一星体不构成双向关系。`mutual_same_kind` 另外记录双方共有的接纳类型，不能把“没有同类型互纳”当成“完全没有接纳”。第112页的三个互纳例子独立保留；实际满足该页前提时，`p112_mutual_reception.conditional_reading_zh` 给出该条规则的条件性支持解释，也注明它不是整盘或现实结果认证。

`perfection.candidate_scope` 明确旧 `candidate` 布尔值只描述瞬时几何代理。即使该代理未找到路径，第112页的双向接纳仍可能成立；不能用 `candidate=false` 抹去已经核算的互纳支持。

`horary.perfection.lilly_conditions.routes` 列出本评估器中的全部直接、传光、聚光候选，避免首个研究代理遮住同类路径；第126–127页的居宫方法及旧月亮共同征象代理的完整来源仍未验收。第126页传光的接纳限定为源星以庙、三分或界接纳载光星；仅旺或面不满足这个列举条件。聚光则是两端分别接纳较重的聚光星，不能反转方向。第125页冲相的特定情况要求庙的互纳，也不能以其他互纳替代。每项都有实际真假或待核状态与页码；问事时刻的接纳不冒充未计算的历史／成相历元接纳。

月亮作为载光星时，逐项条件还核对原生出宫前窗口的第一接触对象；与其他事件的根区间重叠则保留未知。其他载光星的未来事件、此前实际分离、换座／停滞／退行撤回、阻碍及完整宫位偶然条件仍须继续实现。没有在有限窗口找到接触，也不能推断窗口之外没有事件。

第112页把白羊10°的土星列为游离，即使它同时落陷：游离是没有正面本质尊贵，失势本身不是尊贵。共享完整古典层已修复这项误判，中文显示“游离”；未知昼夜若影响三分或分值则返回待定，已知的庙、旺、界、面及失势仍保留。`planets[].dignity` 和择日的星座级摘要只检查庙、旺、落陷；原先错误的 `peregrine` 回退现为 `no_major_dignity` 并附范围，不能据此判断完整游离。依赖旧字面值的接入应读取完整古典层的 `essential.peregrine`，或卜卦指定版本的 `essential_condition.peregrine`。

表格与边界核验（本地数据：`validation/western-lilly-reception-evidence.json`）包含2,520组独立Decimal比较及印例；它是所选原图转录和算术证据，不是独立专家校勘。交付验收（本地数据：`validation/western-lilly-reception-verification.json`）分别记录三端、冻结环境、共享输出迁移与安装包。`lilly_reception_conditions` 严格视图同时读取事实、条件与限制，不能只取一条支持句当成完整结论。

```bash
uv run --locked --extra dev pytest -q tests/test_western_lilly_reception.py tests/test_western_lilly_reception_transports.py
uv run --locked --extra dev python scripts/audit_western_lilly_reception.py --output /tmp/western-lilly-reception.json
```

### Lilly两列容许度、实际落宫与居宫条款

卜卦新增 `orb_profile=lilly_1647_p107_first|lilly_1647_p107_second`，分别对应1647年第107页左右两列。默认第一列与印刷的土星5°、金星4°半径例题一致；原书允许两套值，第二列保留可选。`rule_profile.orb_table` 返回全容许度、半径、来源与选取理由；两星范围取全容许度半和，先判定再舍入。原来火星8°不在任一印列中，现已修正：火星／水星7.4°残差会被两列都排除，7.125°则如实保留两列分歧。闭区间的等号是声明的实现约定，不冒充原书数学端点定论，也不与第113页太阳状态的17°界限混用。

`significators.*.house` 仍表示问者／所问事项的主掌宫；`occupied_house` 表示该行星实际落宫，不能互相替代。`house_condition` 分别给出第48页角／续／果分类、原文的宫位序次与第115页宫位分值。前者只在两星其他尊贵相等时比较，后者仅是偶然尊贵表的宫位一行，不能合成为成功概率或完整力主分数。该旧字段仅是几何落宫的宫位行；第33页效力归属另读 `house_assignment`，详见下节。完整历史居宫变体、非Regiomontanus宫制及恒星黄道扩展仍须核验。

第126–127页明确不接受“所问主星落一宫就必成”的捷径。`lilly_conditions.p126_127_dwelling` 检查实际落宫、月亮前次／下次七曜接触的方向，以及当前对应出相／入相；根区间重叠、缺失窗口、未知速度和角色重合保留未知。`named_necessary_conditions_satisfied` 只覆盖这些必要子条件，不能冒充完整传光或成事；更严格的第126页事件接纳与两造历史分离仍由 `event_paths` 分别返回。三端公开的 `lilly_orbs_houses` 严格视图同时保留来源、实际状态和未完成标志。

原图与修改前反例（本地数据：`validation/western-lilly-orbs-houses/report.md`）记录封存资料、独立算术与接口验收。2024年示例窗口另外发现一处金星导数未收敛；修改前卜卦实现配合相同数值底座也复现该失败，见缺口记录（本地数据：`validation/western-lilly-orbs-houses/native-2024-window-open.json`）。该原始失败回执保留；后续v5已恢复此窗口，详见近太阳导数续修（本地数据：`validation/western-solar-disc-motion/report.md`）。表格修复或协议测试本身不证明天文精度。

```bash
uv run --locked --extra dev python scripts/audit_western_lilly_orbs_houses.py --output /tmp/lilly-orbs-houses.json
uv run --locked --extra dev pytest -q tests/test_western_lilly_orbs_houses.py tests/test_western_lilly_orbs_houses_transports.py
```

### Lilly全表回执与原书例题差异

卜卦的 `fortitudes` 按第115页列出每颗星完整41行，涵盖本质尊贵、宫位计分、运动、对日阶段、太阳状态、精确接触、交点、土火夹持及三颗具名恒星。公开 `lilly_fortitudes` 卡先读逐星摘要，`applied_conditions` 列实际满足的条款；完整行可按 `fortitudes.planets.Sun.rows` 等路径读取。宫位条款的“计分归”对应 `inputs.scored_house`，几何落宫保留在 `inputs.occupied_house`；例如实际第三宫、按宫头效力计为第四宫，不能解说成实际第四宫。此前错误标签的修复回执（本地数据：`validation/western-lilly-house-wording/report.md`）保留原反例和数值不变证明。日月明确不计“顺行+4”，未知项不补成零，`literal_table_balance=null` 只限制相应行星的完整余额。

第178页例题以24小时位移比较中运动。实现取同源的五个原生位置，展开一完整TT日黄经位移，以其绝对量比较原书中运动；瞬时顺逆分开。标称起点须与盘面坐标在算术舍入量内一致，采样后端、框架或配置改变时报错。精确分数回执保留输入浮点值之间的位移，不增加天文观测精度。恒星范围逐星读取：第179页轩辕十四为六度、角宿一为五度，第115页大陵五为五度；当前使用对应历元的视黄经。原页印刷度数另作历史对照，不固定套到现代盘。此前把长体s的“six”误录为“five”，勘误与旧反例（本地数据：`validation/western-lilly-regulus-orb/report.md`）保留原标注、修改前结果和完整例题分母；七曜方法版本为v3，边界闭合与仅比较黄经仍是声明的实现约定。

这套逐行累计不是原典完整强弱判定。封存的原页与单盘七曜应用（本地数据：`validation/western-lilly-fortitudes/report.md`）显示，只有3/7与原书的逐项应用和总计相同；太阳三分、日光束及月亮恒星加分等处仍有分歧。审计保留失败，不删行配平；非Regiomontanus、恒星黄道、不同夹持／精确成相读法及完整居宫政策仍属声明范围之外。已核定条件可作具名传统解读，分值不变成人生事件成功率。

### Lilly福点与宫头效力

`horary.fortune` 按Lilly第143–144页昼夜同用 `ASC + Moon − Sun`，使用实际上升点，不以第一宫宫头替代；与混合传统夜盘反转福点分别保留。第145页独立28项表（含白羊零分行）逐项给出条件、实际贡献与缺项，福点第六／八宫减4分，不套用七曜第115页的减2分；福点不自行发出相位射线。公开 `lilly_fortune` 字段卡先读公式、归宫与实际满足条件，深入读取同 run 的 `horary.fortune.rows`。

`planets.*.occupied_house` 和 `house_condition` 保留几何落宫事实；另列 `house_assignment` 按第33页最近宫头五度政策给出效力归属，七曜强弱表采用该归属。等距宫头保留未知，五度等号为声明的闭区间约定，不增加同星座门槛；宫头缺失、逆序／投影宫位或原生落宫不符时不臆造归属。事项主星所代表的 `house` 仍须单独解读。所有这些信息不改原生坐标、宫头或原有启发式判词。

原图及复核（本地数据：`validation/western-lilly-fortune-houses/report.md`）保留两份福点算式、完整第145页表及第180页应用的分母。两个算式复现，第180页却将距下一宫头6°25′的福点归给第二宫，并省略脱离日光束与火星界条款；按第33页五度政策和声明逐行规则得到3，原书为−2。审计继续失败，不扩大宫头五度阈值、不删除条款配平。第145页未明定福点相位容许度；严格黄经射线和七曜恒星范围（轩辕十四为六度、角宿一与大陵五各五度）的迁用均明确列为实现政策。福点方法版本为v2，完整原典解释尚未认证。

### Lilly判断前审查与资料未知

`horary.radicality` 逐条保留第121–123页的12项手工条款清单，分别记录实际条件、适用前提、报告的例外、转述变体及未知项；这12项是本次整理的清单，不冒充原书编号或全书规则。公开 `lilly_radicality` 字段卡同时读取条款、时主对应、上下文与完整验收状态。上升早度采用 `[0,3)`，晚度采用 `[27,30)`，修复恰好27°漏判；燃烧之路采用 `[195,225)` 并保留原页“部分作者”归属。原文月亮晚度没有数值界限，不能另套上升27°。

早度的极年轻且体貌相应、晚度的年龄对应或确定事件时刻例外，都只接受已有的可选 `radicality_context` 报告。填写准确提问时间不自动成为确定事件图；缺失报告为未知，不从年龄、外貌、分值或问题措辞推断，不索取这些资料来消除警示。`figure_origin=timed_event` 只提供该条上下文，不构成完整事件占星方法。CLI可用 `--request-file` 和 `--radicality-context` JSON对象传入；REST、MCP共用严格嵌套模型，字符串布尔值及未知键被拒绝。

时主使用实际UT1、地点、日出／日落的不等时段，未取民用整点模24。时主与上升主的同主、所选昼夜三分及自身冷热干湿分别返回；第104页所选三分与任一所列三分的敏感性分开。共享日出采用视太阳中心，盘面昼夜采用几何太阳中心，晨昏边界可以不同；日出函数未提供实际后端标志，不声称已独立验收1647年表法。原页短升星座保留为北半球语境印刷清单，不代称所有地点实际升起时间。

空亡几何仍保留，同时列出主星强弱例外及金牛、巨蟹、射手、双鱼“仍有所作为”的限定，不能只凭空亡判失败。七宫受损的非七宫事项前提与另一条土星第七宫规则分开；土星归宫采用已声明宫头效力，几何居宫另列。上升主焦伤区别日光束／日心；“不利”和证词相当未由任意强弱阈值或第115页余额零自动替代。`safe_to_judge=null` 保留完整判断资格未建立，不能把没有命中警示说成整盘已获原典许可。

封存原页与核验（本地数据：`validation/western-lilly-radicality/report.md`）复现四个印刷时主对应例；昼夜重复是敏感性控制，不增加独立算例分母。它们没有完整星盘或现实结果，完整原典、真实模型忠实度与现实预测均须独立验收。

### 日心、焦伤与日下

第113页原图及定义标注（本地数据：`../tests/fixtures/western-lilly-solar-1647.json`）写明日心17′、焦伤8.5°且同星座、日下至17°。原先15°的日下界限与漏掉同星座的焦伤判定已修复；17′用精确分数17/60比较。`classical.solar_condition_policy` 记录来源、区间与黄道政策。日心含17′、焦伤严格小于8.5°、日下严格小于17°是明确的实现区间；不声称原书解决了每个数学端点或现代恒星黄道扩展。

原页同时把太阳白羊18°、另一星白羊28°的10°示例称为焦伤，与同页8.5°明文定义不一致。此冲突保留为未决文本问题，不静默改数、不扩大界限来让例子通过，`full_page_acceptance=false`。`solar_conditions` 视图同时读取实际太阳状态、定义与冲突记录；印度盘中的共享字段仍是明确标注的西方兼容层，不据此认证印度原典方法。

### 择日的实际条件与分数回执

择日使用与起盘相同的TT原生月亮搜索，读取下一星座界前的严格未来主相位、根区间和物理星历来源。旧72分钟推进会跨过近处成相点而误判，也会用当前容许度或相位距离错代剩余时间；原失败记录（本地数据：`validation/western-election-motion-open.json`）保持原样，修复核验（本地数据：`validation/western-election-calculation-evidence.json`）记录当前结果。直接几何研究的恒速函数另有方法名，不作为生产路径。这里仍采用声明的“出宫前精确黄经成相”操作定义，Lilly第112页全部措辞与流派差异尚未认证。

`election.axes` 区分物理ASC／MC与第一／十宫宫头。依[Swiss接口定义](https://www.astro.com/swisseph/swephprg.htm)，轴与宫头属于不同返回数组；整宫、Vehlow等宫制尤其不能替代。择日现按物理轴比较既有5°黄经距离，保留原容许度；这项二轴接近条件不是实际落角宫或四轴完整角性判断。卜卦也改用物理ASC核对求问者与早晚度数，完整小数不会提前舍入到30°。

月亮太阳状态复用上述Lilly第113页定义：日心和跨星座近太阳不自动算焦伤，8.5°端点沿用公开的严格小于政策。只有实际落入焦伤分支才触发原有-12因子，日下或日心没有为提高分数新增奖励。精确新月／满月分别显示`new`／`full`；旧+8与-6仍按声明的半周区间计算，不能把相位边界误写成已经渐盈／渐亏。

原生事件或速度未知时，`score=null`、`unresolved_factors`和`score_bounds`共同保留未核项；没有把未知逆行当作速度零。范围由已知原始小计加未核算贡献后再截到0–100，属于固定政策的范围，不是置信区间或成功概率。已知硬限制仍保留；只有可能存在的硬限制则为未知。未完成且没有已知硬限制时返回`incomplete`，不能输出吉利结论。

这套数值权重和75／55／40分档是未校准的产品约定，不能称作Lilly全书择日判断；`scoring_policy`明确来源范围和未完成状态。基准样例的48分没有为本次修复调整。`calculation_conditions`严格视图同时读取原生事件、轴、太阳定义、已知因子、待核项与分数政策。交付验收（本地数据：`validation/western-election-conditions-verification.json`）分开记录计算、原典条件、接口和安装包；相应历史失败和未完成目标均保留。

```bash
uv run --locked --extra dev pytest -q tests/test_western_election_conditions.py tests/test_western_election_conditions_transports.py
uv run --locked --extra dev python scripts/audit_western_election_conditions.py --output /tmp/western-election-conditions.json
```

本阶段交付验收（本地数据：`validation/western-horary-verification.json`）分别记录独立JPL对照、宿主与冻结Linux测试、六份共享快照的审查、安装包及未通过的共享检查；不把这些检查合并成原典全文或实际模型解释的认证。

```bash
uv run --locked --extra dev pytest -q tests/test_western_horary_motion.py tests/test_western_horary_motion_transports.py
uv run --locked --extra dev python scripts/audit_western_horary_motion.py --output /tmp/western-horary-jpl.json
```

## 恒星位置、黄道与原典标签

`fixed_stars` 使用20颗已明确识别恒星的 [CDS SIMBAD 天体测量记录](https://simbad.cds.unistra.fr/Pages/guide/sim-url.htx)，每颗的ICRS J2000坐标、自行、视差、径向速度、文献及采集回执存于[随包来源表](../src/fatebridge/data/western_stars/sources.json)。这是现代观测资料，不重建古代观测星表。Swiss原生视位置按本次TT传播；[官方固定恒星接口](https://www.astro.com/swisseph/swephprg.htm)说明该计算包含自行、岁差、章动、光行差和视差。回归盘使用日期真黄道，恒星盘使用原生Lahiri位置，恒星与盘内因素必须处于同一坐标基准。

先前统一线性岁差遗漏自行等项，而且恒星黄道盘仍与回归恒星比较。旧近似在本轮独立样本中最大黄经残差约99.57角秒；在1°判定边界附近可以产生漏报和误报。预先固定的协议（本地数据：`../tests/fixtures/western-fixed-star-protocol.json`）采用1角秒阈值，20颗星乘6个1900–2099年TT历元共120个位置；独立ERFA参考（本地数据：`../tests/fixtures/western-fixed-stars-erfa.json`）与原生计算共享星表输入，但不共享数值算法或地球状态。宿主数据星历环境最大黄经坐标残差约0.00085角秒、纬度约0.00056角秒；冻结Linux的Moshier环境分别约0.01716与0.00898角秒，均按原先1角秒阈值验收。这属于所列输入上的算法一致性，不是观测绝对精度认证。

`chart_profile.fixed_stars` 返回星表指纹、TT、黄道、模型版本及状态。星表单独随包分发，调用不依赖可选完整 `sefstars.txt`；缓存和操作员路径在共享锁下隔离。本轮实测恒星函数可返回SWIEPH请求标志，而地球状态实际回退Moshier，故保留恒星标志并另测、另列 `earth_ephemeris_model`，不由请求标志认证精度。状态为 `unavailable` 时文本明确显示“未计算”，空列表不能被解释成没有合相。

合相按未舍入黄经分类、保留原始小数；默认1°是产品采用的传统容许度政策，不是I.9给出的参数。这里比较黄经，不比较球面角距，也不表示掩星，`star_latitude`与`conjunction_basis`显式保留这一差别。远古／远未来、双星轨道与星表协方差仍未完成独立验收。

传统性质与天体测量分别给出来源。按 [Robbins 1940《Tetrabiblos》I.9](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html#9)，昴星团属月亮／木星；此前昴宿六的月亮／火星标签已更正，后者是巨蟹座积尸气一类的归属。行星性质标签仅表达该处传统对应，不凭合相单独补出事件判断。审计记录（本地数据：`validation/western-fixed-star-independent-evidence.json`）同时保留旧模型残差和一对合成边界反例，不能将反例称为实盘命中。

[I.9区域对应与限定词](../src/fatebridge/data/western_stars/nature_rules.json)单列星座区域和现代对象的识别政策。`nature_components`保留角宿一、天狼、南河三的火星“较轻程度”，以及心宿二木星的“一定程度”，并进入文本导出；`unqualified`仅表示该段没有相对程度限定，不表示等权数值。区域规则的人工标注仍不是独立专家校勘，`nature`平铺列表只保留旧接口兼容，完整解释应读取限定词。

实现与交付验收（本地数据：`validation/western-fixed-star-verification.json`）分别记录冻结Linux、宿主与隔离安装包；34份西方回归输出及1份共享印度盘输出单列。印度盘旧回归恒星误配所列4个命中已改为同黄道下的2个命中，并以独立ERFA追加复算；这个20位置、1历元的事后队列不合并为原先120位置的预先协议。快照回归与原典解释、绝对观测精度各自验收，当前整体目标仍未完成。

## 指定版本的原典子集

依据为 [Ptolemy《Tetrabiblos》，F. E. Robbins，Loeb，1940](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html)。`classical.ptolemy` 单独列出作者、版本、章节、规则 ID、输入黄经和所得关系。

| 章节 | 已实现的限定内容 | 关键区别 |
| --- | --- | --- |
| I.7 | 七曜自然宗派；水星按晨／昏关系区分 | 日夜盘性质与某颗星的自然宗派分开 |
| I.13 | 星座间六合、刑、拱、冲及原文和谐分类 | 按星座关系；现代度数相位的容许度另算，同星座单列 |
| I.14 | 命令／服从星座关系 | 按春秋分轴对称与原文北方夏／冬半球口径，不随出生地改写 |
| I.15 | 相互注视、等力关系 | 按二至轴对称的星座配对 |
| I.16 | 离隔关系 | 先排除I.14／I.15亲缘关系，不能将所有相邻或150°星座一律标成离隔 |
| I.17 | 十二星座的传统守护关系 | 此处的 houses 是星座守护，不是十二宫宫头 |
| I.18 | 四组三分及昼夜治理 | 水象为火星主掌，加昼金星／夜月亮共同治理；不换成 Dorotheus 三主星表 |
| I.19 | 旺与弱的星座关系 | 本章节未给出的精确擢升度数不补造 |
| I.20–21，仅界表与分配顺序 | 分别返回埃及界、迦勒底界、托勒密界的主星和区间 | 依 Robbins 纸本主表；迦勒底界按昼夜交换土星／水星次序；不混算尊贵分数 |
| III.10，仅福点算式 | `ASC + Moon − Sun`，昼夜相同 | 按 Robbins 主文选式；不采用注释讨论中的夜盘反转，也不实施该章寿命判断 |

此层规则 ID 为 `ptolemy_tetrabiblos_robbins_1940_bounded_v4`，只对回归黄道计算，恒星黄道返回 `unsupported_zodiac`。`classical.ptolemy.lot_of_fortune` 保留选式、完整经度与 [III.10 来源](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/3B%2A.html#10)。原有 `classical` 仍为 `mixed_dorothean_egyptian_lilly`：埃及界、Dorotheus 三分、Chaldean 面与 Lilly 权重等不同来源的组合，其福点按昼夜反转。两层在夜盘可能不同，不能混称同一原典结论。它们都不是《四书》全文实现。

`classical.ptolemy.planets.<planet>.terms` 使用 `egyptian`、`chaldaean`、`ptolemaic` 三个键，保留 `lord`、`start_degree`、`end_degree`、`chapter_ref`。连续黄经按含起点、不含终点的 `[start,end)` 归界；这个数值约定把原表的度数区段映射到现代坐标，先归界再显示，不能四舍五入后分类。例：白羊13°在埃及界属水星，在托勒密界属金星；白羊16°在迦勒底界昼属土星、夜属水星。此层不由界主单独推断整体强弱或现实事件。

[Robbins 1940 纸本扫描](https://commons.wikimedia.org/wiki/File:Loeb_435_-_Ptolemy_-_Tetrabiblos_by_Robbins_(1940).pdf)第96–97页埃及表与第106–107页托勒密表已人工逐格对读。第106页希腊文和第107页英文均为天秤最后6°属火星（24–30°）；LacusCurtius HTML 同格重复为土星。本实现依纸本主表，并公开 `term_source_url`、`term_policy`、`term_transcription_note`。这是指定版本的取表政策，纸本校勘栏中的其他传本读法继续保留为未穷尽的差异，不能称为“唯一权威界表”。

冻结的手工表（本地数据：`../tests/fixtures/western-ptolemy-terms-robbins-1940.json`）与可复算审计（本地数据：`validation/western-terms-evidence.json`）分别保存版页、来源指纹和在线转录差异。4320个整度／区间内探针、1080个相邻浮点边界探针复用同一组表，不是5400份独立观测；故意恢复在线天秤错误会被相同审计拒绝。手工原典标注与算术回归不替代独立专家校勘。

三端、快照和安装包验收记录（本地数据：`validation/western-terms-verification.json`）分列宿主、冻结Linux及隔离安装结果；共享全工具检查的两项其他卜算代表输入失败也保留，不以相关子集通过替代仓库全绿。

尚未验收的内容包括 I.20–21 全部传本差异与论证链、原典全文的判断链、整套接纳与偶然条件、完整主限体系、恒星双星运动与协方差、远古远未来星表传播和所有流派变体。

## 参考点、模型与日速来源

`calculation_basis.ephemeris_reference_points` 明确区分原生本体中心、行星系统质心、解析交点和派生轴。Swiss 默认的火星、木星、土星等位置是相应系统质心；不是已经做过本体中心修正的坐标，依据[官方文档2.4及附录C第6例](https://www.astro.com/swisseph/swisseph.htm)。`center_body_correction_applied=false` 如实保留。太阳、月亮、水星、金星与上述点分别列出；这项说明也进入月亮与七曜事件的回执，不通过改名把其他点认作本体中心。

坐标原点与目标参考点分开核对：`BARYCTR` 改变原点，`CENTER_BODY` 则改变行星目标点；同为地心日期黄经，也不能据此认作同一点。[官方接口3.2.2及3.3.1](https://www.astro.com/swisseph/swephprg.2.10.pdf)分别说明这些选项。当前标准消费者未请求本体中心覆盖，原生返回若带此标志，会报 `coordinate_contract_changed`，不继续按默认系统质心发布；守卫验收（本地数据：`validation/western-point-flag/report.md`）区分了受控故障与正常星位保留检查。未启用新的本体中心模式，也未由此改变既有精度失败的判据。

精密比较还须匹配时间尺度、地心／站心、视位置约定及坐标框架。本轮核对的原生2.10.03源码默认采用Vondrák2011岁差、IAU2000B章动与IAU2006框架偏置；它与Horizons第31量的IAU76/80日期黄道不能直接认作同一框架。这是指定源码版本的默认定义，不是对任意安装版本或运行时底层配置的认证。完整共同框架复核（本地数据：`validation/western-tt-common-frame/report.md`）保留原始跨框架失败，另用JPL ICRF方向及独立ERFA旋转核对相同参考点，不通过替换原生坐标或放宽容差来配平。

主本命盘、希腊盘和十三等分盘也在 `chart_profile.ephemeris_reference_points` 返回同一参考点合同，并将实际分组说明带入摘要与文本快照；归组依据每颗因素的实际模型，单颗回退近似时不会继续声明它是原生系统质心。交点与派生轴／阿拉伯点分别标记。本命盘来源交付验收（本地数据：`validation/western-natal-reference-points/report.md`）核对共享映射、完整结果与严格字段投影；这些说明不改变星位或证明物理观测、原典全文及现实预测有效。

推运／事件底座的 `ephemeris_model` 现在只汇总物理天体的实际后端，解析交点单列。此前单一Moshier或Swiss数据模式会因加入解析月交点而误报 `mixed`；现在只有实际物理后端混合才用该标签。底座还返回物理数据来源和计算期间配置一致性检查，文件身份不等于观测精度认证。

历表来源完整性错误返回 `ephemeris_source_inconsistent`、状态503及实际 `issues` 原因，整次计算停止。升落、行星时日期、黄赤交角、岁差、宫位和扩展纪年日期等辅助路径保留该错误类型；普通极区无事件和可选量不可用仍按原有规则表达。来源异常交付核验（本地数据：`validation/western-source-errors/report.md`）分别记录故障注入、正常盘数值保全和三端结果。共享请求中的非默认 `ephemeris_policy` 当前仍只对印占开放，西占严格策略入口是未完成项。

月亮接触和七曜事件的UTC标签也保留来源错误。普通日期表示限制仅留空标签，已经求得的TT事件仍保留；来源错误继续交由既有错误合同处理。事件标签来源核验（本地数据：`validation/western-event-label-sources/report.md`）将这两类情况及合成错误载体、完整生产搜索分别验证。

`longitude_motion` 保留原生版本、源码函数、已应用／未应用修正及显示框架偏移日速；七曜事件状态分别给出 `speed_native`、适用的光行时／旋转修正、`speed_position_derivative_correction` 和显示偏移项，最终 `speed` 是实际应用各项之和。共享底座对适用天体的完整位置差分还返回候选步长、选取政策、收敛差异和辅助物理来源；完整位置差分已经包含的框架运动不会重复相加。Moshier不适用的修正明确返回未应用，不能认作已经验证。

自转适配器的 `earth_rotation.policy_id` 为 `fatebridge_standard_rotation_v3`，`tt_argument_policy` 回显本次实际路径。自定义自转校正从共享历法政策取得TT：1960年前沿用原生历史UT1转换的无星历位政策，1960年起保留现有SWIEPH关系；选用C04时由该表反解TT。此前适配器始终用SWIEPH重推TT，与历史盘的物理时钟不一致，并会在下端窗口附近选错分支。时钟一致性核验（本地数据：`validation/western-rotation-tt-policy/report.md`）保留原失败及修复后结果。这里修复的是公式时间参数，不能解释成行星或出生资料整体错移同样秒数，也不认证古代实测UT1或更高绝对精度。

原生绑定版本的重复发现采用有界缓存，每次仍检查二进制文件身份；替换原生版本、二进制文件或版本解析函数后重新取值，无法识别文件时保持无缓存行为。安装依赖更新后需要重启计算进程。同历元旋转修正复用也核对原生和绑定版本；这项优化不缓存轨道位置或求根结果，不放宽未知版本的修正门槛。

原先约205秒的土星停滞差异，经过冻结的参考框架诊断（本地数据：`../tests/fixtures/western-event-frames-protocol.json`）和中心对照协议（本地数据：`../tests/fixtures/western-event-reference-points-protocol.json`）后，发现原JPL目标699是土星本体中心，而默认原生点对应目标6。仅更换参考框架仍有约205秒差异；统一为系统质心后，两个独立ERFA框架的停滞差异约0.9秒和0.75秒。所用120秒停滞与30秒成相／入宫容差均未改变。新的对照（本地数据：`validation/western-reference-points-evidence.json`）覆盖同一批106项事件、两种框架；两种框架复用观察，不算212个独立事件，也不把同点通过记成本体中心验证成功。原始失败报告（本地数据：`validation/western-event-paths-evidence.json`）及全部原始资料继续保留。

上述212次事件比较属于引入完整位置导数前的冻结Swiss实现。Moshier单列复跑（本地数据：`validation/western-reference-points-moshier-evidence.json`）为210/212，木星一次入宫在两种框架中均超出30秒容差，不能沿用Swiss的通过数。引入严格完整位置导数后的早期Swiss复跑（本地数据：`validation/western-reference-points-current-evidence.json`）曾因近太阳样本未收敛，仅有49项事件可比较；后续光行时历元稳定化（本地数据：`validation/western-position-convergence/report.md`）已恢复全部106项事件，并在两种框架下再次符合原时刻容差。前后源码和失败记录分别保留。

更严格的0.02角秒位置诊断仍未整体通过：水星接近太阳时有约0.89角秒差异。[Swiss附录A](https://www.astro.com/swisseph/swisseph.htm)说明太阳遮掩范围内使用连续的虚拟引力偏折延拓；当前已记录太阳角距等诊断，但未宣称这已独立证明全部差异的来源。原来的2角秒位置验收与新增严格诊断分别记账，不放宽后者，也不删除失败时刻。

```bash
uv run --locked --extra dev python scripts/audit_western_reference_points.py --output /tmp/western-reference-points.json
uv run --locked --extra dev pytest -q tests/test_western_reference_points.py tests/test_western_reference_point_transports.py
```

后续v5已恢复本轮2024年窗口，并保持原106项事件、两框架的212次时刻比较通过；审计仍因严格位置诊断而退出1，事件时刻通过不能代替该诊断或完整原典验收。早期未完成窗口的回执保留原样。新增参考量是事后定位问题的对照，不是重新命名的盲测。本轮报告（本地数据：`validation/western-station-frames-report.md`）说明当前四项状态，交付验证（本地数据：`validation/western-station-frames-verification.json`）分别记录数值保存、协议、安装包和未完成要求。

## 近太阳导数的假收敛与分段

`fatebridge_complete_position_derivative_v5`修复了一类“相邻步长看似稳定、实际导数仍超线”的问题。固定发展的42个历元在两种框架下共84组对照，旧实现有12组误差超过原0.002角秒／日门槛、2组不可用；当前84组都在原门槛内。70位用于独立数学归算，输入星历仍为双精度原生物理数据，不能称作70位天文精度或盲测。

所有数值阶段都核对多层中心差分及两种密度的单边拟合，内部0.0002角秒／日线保持。太阳内部质量表按半径分段插值；普通对称模板跨越近处节点时，只有严格位于已知分段内部、全部采样节点同段的方向才可参与局部单边导数。所有适用方向都要共同通过三层检查，不能挑有利的一边；未知分段或精确节点不补成有效计算。`complete_position_derivatives`中的`directional_checks`、`source_branch_motion`与`sampling_stabilization`保留方法、被排除的方向、原失败阶段和量化尺度，显示位置不由该算法改写。

v7在既有路径全部未收敛、且已确认位于原生有限太阳模型分段内部时，可对水星／金星／火星的辅助几何状态作50位数学化简。它按原质量表处理光偏折和光行差，恢复原生迟延历元的小数余量，并用经核对的原生基向量转换显示框架；仍须满足全部适用方向、三层及原0.0002角秒／日线。实际采用时在`source_branch_motion.decimal_reduction`记录运算位数、质量表散列、框架检查和适用限制，旧失败在`decimal_reduction_previous_attempt`保留。50位运算不等于50位天文精度，显示星位不改写；数值化简报告（本地数据：`validation/western-decimal-reduction/report.md`）分别记录共享星历上的独立数学参考与尚未完成的绝对天文验收。

本轮源模型与交付报告（本地数据：`validation/western-solar-disc-motion/report.md`）同时列出原120组JPL速率对照、212次事件时刻比较和仍失败的0.02角秒位置诊断。2024年±30日原生历史已恢复，计算得到151项有限扫描事件；没有新增这151项的独立时刻预期或连续完备性证明。成功历史明确返回可空的失败字段，使`reference_points`严格视图在成功和失败两种状态下都能读取诊断。完整原典与现实预测效度仍未据此认证。

## 卜卦的实际事件路径

`horary.significators.directed_sign_relationship` 补充Lilly1647第108–109页的有向星座表：由求问者主星向所问主星，顺星座次序为左相、逆次序为右相，冲相原表不分左右。同星座共处与第106页的身体合相分别核对。第109页实际列出32组有向不相照关系，另16组在相照／不相照两表均未列出，明确保留 `not_in_either_table`，不按简单距离规则扩表。

这层证据与当前所选容许度内的度数相位候选分别返回，允许两者不一致；不会重选原有候选、修改未来事件或给右相另加分。第109页“较有力”的文字没有数值系数，本项不推定成事。方向不是接纳主人／客人，也不替换希腊化overcoming。`lilly_sign_rays` 字段卡可读取对应依据和解释；恒星黄道标作扩展，同一主星的两个角色不当作独立行星，ASC未解析时主层证据为空。核验报告（本地数据：`validation/western-lilly-sign-rays/report.md`）保留独立于生产代码的144组手工原表参考和原有未通过门槛。

`horary.perfection.event_history` 在提问前后各30个TT日内，对七曜实际视黄经求成相、顺逆行入宫和速度过零事件。相对速度转折用于分割求根区间，返回根区间、事件双方状态及区间端点状态；未知TT或原生失败不转用匀速近似。该有限扫描没有连续区间完备性证明，未找到某次成相不能解释为永远不会成相。

完整位置导数未收敛时，事件层返回 `status=unavailable`、`unavailable_code=position_motion_not_converged` 和失败天体／TT时刻，并保留已计算的提问时刻状态。此时空事件列表表示未知；不能推断没有成相、没有阻碍或事情失败。其余数据源、坐标框架、配置和后端不一致仍作为计算错误返回。`reference_points` 证据视图包含事件层状态和失败原因，摘要投影也不会隐藏这个限制。收敛失败样本仍计入未完成覆盖，不替换成原生日速或调宽门槛。

`horary.perfection.lilly_conditions.event_paths` 将事件与所选Lilly1647第110–111、125–126页的条件对照。第126页首先涉及两颗主星彼此的历史分离；传光星从其中一星分离是另一个条件，两者分别返回。非月亮传光星也检查实际前次接触和下次接触，不能跳过中间先遇到的其他行星去挑有利目标。重叠的根区间保留未知，已有先后顺序不能由数组顺序决定。

接纳回执读取对应事件的客星黄经，同时明确保留提问盘昼夜政策；这不代表原典对所有事件历元的解释已获校勘。根区间跨越尊贵边界时保留端点接纳与不确定性；若始终有其他尊贵保证接纳，仍保留确定成立的部分。第111页的两种顺行追越例和成相前转为逆行的特定结构可由真实事件顺序识别；其他阻碍变体、原典居宫／偶然条件与完整判词仍未验收。满足一组时序条件不等于整条原典路径已成立。

新JPL冻结参考（本地数据：`../tests/fixtures/western-event-paths-horizons.json`）来自两个21日TT窗口、7070组七曜黄经，原始响应逐字归档（本地数据：`../tests/fixtures/western-event-paths-raw.zip`）。预定2角秒、成相／入宫30秒和停滞120秒容差均未放宽。独立审计（本地数据：`validation/western-event-paths-evidence.json`）中106项事件的身份和数量一致，其中105项时刻符合容差；土星停滞约205秒差异仍未通过。原三点停滞参考、参考舍入问题及五点细化结果均保留，细化没有消除该差异。[Swiss官方](https://www.astro.com/swisseph/swephprg.htm)说明默认视位置与Horizons的IAU76/80及EOP参考框架不同；这是保留的上一轮本体中心对照；上节新的中心控制已定位土星系统质心与本体中心的混用。不能仅凭位置落在2角秒内就认证停滞时刻精度，也不能把同点通过改写成原本体中心比较通过。

```bash
uv run --locked --extra dev pytest -q tests/test_western_event_paths.py tests/test_western_event_paths_transports.py
uv run --locked --extra dev python scripts/audit_western_event_paths.py --output /tmp/western-event-paths-evidence.json
```

审计当前应退出1，表示仍有上述独立对照未通过；测试检查解析反例与协议保真，不把该失败计成通过。资料的作者、印页与两类分离的校勘见原典回执（本地数据：`../tests/fixtures/western-lilly-event-paths-1647.json`）。公开严格视图 `event_paths` 同时包含原生事件、来源、原始状态与未完成条件。

## 解释如何对应本次计算

`interpretation` 的现代象征模板使用 `modern_symbolic_templates_v2`，原典关系另以 `original_text_relations` 返回，采用 `ptolemy_robbins_sign_relations_v1`。`interpretation_evidence` 给出各段实际依赖的 `source_paths/kind/policy_id`，包括盘型补充说明；成长建议标记为 `practical_suggestion`。现代模板不被归为 Ptolemy 原文。

界主说明单列 `original_text_terms`，政策为 `ptolemy_robbins_printed_terms_v1`，逐项读取本次返回的七曜界主、区间与昼夜盘；同文进入摘要和文本导出。它叙述传统位置归属，不增加自定义分数或事件判断。JSON证据路径包括表格政策和纸本校勘说明。

统计解释保留全部并列首位，不按字母顺序挑“最强”；宫位和星座本体计数同时排除南、北交点。MC象征读取MC自身星座，不借用上升星座的气质。相位说明使用“偏离精确角度最小”，并逐类报告命中条数；几何距离和条数均不换算整体强弱。导出与JSON的符号来源保持一致。


宿主可用完整原始结果、同一 `run_id` 与 `business_output_sha256`，通过 `validation.claims.verify_calculation_claims` 核对结构化引用。缺失字段、错误值、不同回执或事后改动不得通过。字段路径和哈希只支持核查原始事实，不自动证明自由文本的语义忠实，也不替代真实模型对话验收。

## 独立数值审计与复现

固定数据来自 [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html)，保留请求参数、完整响应和 SHA-256。覆盖 1900—2099 年十二个时刻、十个实际天体，共 120 组黄经／黄纬；容差在采集前固定为 2 角秒。节点、宫位、现实事件不在该外部数据集内。[Horizons 时间说明](https://ssd.jpl.nasa.gov/horizons/tutorial.html)明确未来沿用最后已知闰秒；本轮比较采用同一公开假设。

测试先发现 UTC 直接当 UT1 会使 2099 年月亮黄经误差约 15.20 角秒。修正时间尺度并保留未舍入坐标后，无外部文件的 Moshier 模型在该样本集的月亮最大黄经误差约 1.34 角秒；十天体最大黄经误差约 1.98 角秒。使用已核验文件的 Swiss 模型，十天体最大黄经误差约 0.56 角秒。这里核对的是星历位置，不是人生事件。

```bash
uv sync --locked --extra dev
uv run --locked --extra dev pytest -q tests/test_western_accuracy.py tests/test_western_accuracy_transports.py
uv run --locked --extra dev python scripts/audit_western_accuracy.py --output docs/validation/western-independent-evidence.json
# 需要刷新外部数据时才联网；不能用本引擎重写参考值。
uv run --locked --extra dev python scripts/gen_western_horizons_reference.py
```

机器可读审计记录（本地数据：`validation/western-independent-evidence.json`）列明每个样本、误差、来源和代码指纹。黄金快照维护接口回归；它不充当独立算法答案。不能通过放宽容差、删掉失败年代或增加内部规则命中次数提高验收结果。

后续推运独立审计（本地数据：`validation/western-timing-independent-evidence.json`）将相同 120 个位置用于原生推运底座，并独立向 NASA 采集六个日月返照零点，另与[香港天文台 2026 年二十四节气](https://www.hko.gov.hk/en/gts/astron2026/files/2026SolarTerms24.pdf)的四个季节交点核对。返照覆盖闰日出生、民用跨年与 2099 年；采集前固定太阳 120 秒、月亮 15 秒容差。所有样本均保留请求／响应及指纹，未用 FateBridge 生成外部答案。推运底座 120/120、返照 6/6、季节交点 4/4 通过各自容差。后两项仍属天文事件，不能记入人生事件预测成绩。

同一批样本也以当前本地 Swiss 数据文件复核，文件模式审计（本地数据：`validation/western-timing-swieph-evidence.json`）记录实际 `swieph` 模型及三个文件的 SHA-256。120 组位置最大黄经误差约 0.560 角秒；空目录 Moshier 模式约 1.979 角秒，均在原先固定的 2 角秒内。六个返照在文件模式下太阳最大时刻误差约 5.45 秒、月亮约 0.39 秒。文件由使用者单独取得，未随源码重新分发，也未改变容差以适配观测结果。

```bash
uv run --locked --extra dev pytest -q tests/test_western_timing_accuracy.py tests/test_western_accuracy_transports.py
uv run --locked --extra dev python scripts/audit_western_timing_accuracy.py --output docs/validation/western-timing-independent-evidence.json
# 已按项目星历流程取得文件后，用同一数据和容差复核实际文件模式：
uv run --locked --extra dev python scripts/audit_western_timing_accuracy.py --ephemeris-dir ephe --output docs/validation/western-timing-swieph-evidence.json
# 仅需刷新 NASA 独立返照参考时运行：
uv run --locked --extra dev python scripts/gen_western_returns_reference.py
```

首轮本地验收记录（本地数据：`validation/western-local-verification.json`）与推运深化验收记录（本地数据：`validation/western-timing-local-verification.json`）分别记录对应代码状态的专项、三端、类型、格式、构建及全仓检查，不能把不同状态下的通过数直接相加。

## 当前四项验收分别记账

当前请求包含历法／天文、指定原典、解释忠实和现实预测四个维度。四项均保留为要求，当前通过的子集不替代完整目标。详细缺口与下一步见要求账本（本地数据：`validation/western-three-axis-requirements.json`）及四项状态回执（本地数据：`validation/western-four-axis-status.json`）；账本沿用历史文件名，旧报告的三项范围不被追溯改写。

| 维度 | 当前可支持的结论 | 尚缺的证据 |
| --- | --- | --- |
| 算对历法／天文 | 已修复历法、UTC/TT/UT1、昼夜、DST及舍入越界；本命、推运、日月返照及四季交点获得有限独立对照 | 更广年代、完整EOP、其他入口的实测UT1、宫位独立对照、朔望／行星时边界和其他推运技法的验证 |
| 符合某部原典 | Robbins 1940 I.7、I.13–19、I.20–21三种界表与顺序、III.10福点算式的明确子集；现代容许度政策与原典星座关系分开 | 其余章节及传本校勘、已发布高级技法的逐项来源和完整判断链复核 |
| 解释忠于计算 | 坐标与显示一致；并列、MC、虚点计数和相位措辞有反事实回归；三端事实与回执一致 | 全部公开专业技法的文字覆盖、真实模型行为和遗漏／矛盾测评 |
| 能够预测现实 | 通用二元事件评估器已有事前登记、完整队列、冻结基线及配对损失检验；目前没有独立核验的西占现实事件研究 | 明确问题与人群、真实事前预测、独立现实结果、强基线比较和复现；合成测试不计现实成绩 |

四项不平均、不互相替代。当前未建立“四项满分／最权威预测系统”的结论。现实研究须在结果揭晓前固定计划与方法，参见 [COS 预注册说明](https://www.cos.io/initiatives/prereg)；已有[评估流程](prediction-validation.md#可证伪的现实预测评估)可复用，其八字示例不属于西占数据。

```bash
uv run --locked --extra dev pytest -q tests/test_western_semantic_fidelity.py tests/test_western_accuracy_transports.py
uv run --locked --extra dev python scripts/audit_western_fidelity.py --output docs/validation/western-fidelity-evidence.json
```

[西占真实模型解释诊断](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/western-semantics-evaluation.md)覆盖八个虚构场景、44条人工要求；仅准备参照或通过机械测试不提高语义验收状态，真实模型须按当前代理授权规则另行执行和审阅。
