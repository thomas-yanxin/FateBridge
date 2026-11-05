# 占星骰：符号、原典关系与天象背景

阅读导航：[骰面输入](#输入) · [知识与来源](#知识范围与来源) · [运动与日速](#瞬时运动与速度核验) · [坐标与参考](#坐标含义太阳高度与独立视运动参考) · [验证边界](#验证范围与现实预测)

`otherbu` 解读用户已有的三枚骰面，规则版本 `astrodice_symbolic_v7`。它不代替用户抽骰，不接收塔罗牌阵。缺失或无效骰面会被拒绝，不再默认为太阳、白羊、一宫。

## 输入

`planet`、`sign`、`house` 三项必填。`house` 保持原有的 **0..11 索引**：实体骰子的第 1 宫传 `0`，第 12 宫传 `11`。输出 `symbolic_details.house_number` 为自然宫号 1..12。浮点数、布尔值、负数和越界值不能被截断或钳制。

支持 `Sun/Moon/Mercury/Venus/Mars/Jupiter/Saturn/Uranus/Neptune/Pluto/NorthNode/SouthNode`，以及对应中文名和符号。星座接受十二星座英文名、中文名和符号。南北交点是月球轨道交点，不是两颗实体行星。

仅解读骰面不需要日期、地点或出生资料：

```bash
uv run --locked --extra dev fatebridge otherbu \
  --planet Mercury --sign Virgo --house 6 \
  --question '虚构示例：合作沟通中应核对什么？' \
  --fields planet sign symbolic_details interpretation rulesets rule_trace validation \
  --strict-fields
```

MCP 可直接传 `{"planet":"☊","sign":"处女座","house":11}`。默认首轮视图保留解释、规则、出处和验证边界；视图名不是请求参数。REST 的投影参数放在 URL query：

```bash
curl -sS -X POST \
  'http://localhost:8010/api/divination/otherbu?fields=planet&fields=symbolic_details&fields=interpretation&fields=rulesets&fields=rule_trace&fields=validation&strict_fields=true&include_snapshot_text=false' \
  -H 'Content-Type: application/json' \
  -d '{"planet":"Mercury","sign":"Virgo","house":6}'
```

若请求独立天象背景，同时提供 `date`、`time`、`zone` 及完整经纬度（`lat/lon` 或 `gps_lat/gps_lon`）。不再默认上海坐标和东八区。日期为公历，时间为当地民用时，可保留秒和微秒；IANA 时区的夏令时歧义或不存在时刻应拒绝，使用已核对的 UTC 偏移消歧。`chart.params` 保留实际 UTC 时刻、星历模型和历法/时间尺度信息。

有效本地年 1／9999 的 UTC 标签可能跨到天文年 0／公历年 10000。现在保留该物理时刻及扩展年份字符串，例如 `0000-12-31T10:00:00+00:00`、`+010000-01-01T11:59:00+00:00`，不裁剪输入日期。UTC 整数日序、微秒、固定闰秒假设和三种协议的限定验收见UTC 跨年界修复；Python `datetime` 不能直接解析这些扩展标签。

同时提供文本坐标和 GPS 坐标时，两者须一致（数值比较容差 `1e-9°`，经度按圆周比较，`180°/-180°` 等价）；该容差仅吸收表示误差，不宣称实地定位精度。无效或空白的任一已提供别名均会拒绝，GPS 布尔值不能变成 `0/1°`。有精确 GPS 而文本坐标只是约数时，只提交已核对的 GPS 一组即可。`chart.params.birthLatitude/birthLongitude` 和快照保留实际用于计算的浮点坐标。

`tradition`、`hsys`、`zodiacal`、`fortune_method` 仅影响附加天象。它们不重写骰面，不把骰面的星座转换为恒星黄道，也不因 `tradition=true` 删除用户投出的外行星或交点。

**输出变化：** 没有天象输入时 `chart=null`；`diceChart` 仅含投出的一个符号和假设整宫轮。其星体不再附带虚构的 `lon=15°`、`signlon` 或二十八宿，`angles={}`，不再复制真实星体。调用方不能继续把 `diceChart` 当真实天文盘。

## 知识范围与来源

| 层 | 依据 | 实现与边界 |
| --- | --- | --- |
| 十二骰面与组合结构 | Rev Bill Duvendack，2013，[作者说明](https://418ascendant.com/wp-content/uploads/2012/01/What-are-Astro-Dice.pdf) | 日月、八行星、南北交点，与星座、宫位组合。作者另述的出生盘比较属于扩展，本工具不声称实现它 |
| 七曜星座关系 | Claudius Ptolemy，《Tetrabiblos》，J. M. Ashmand 英译，1822，卷一 [XX 行星的庙](https://sacred-texts.com/astro/ptb/ptb23.htm)、[XXII 擢升](https://sacred-texts.com/astro/ptb/ptb25.htm) | 星座级入庙、擢升、落陷；“失势”另标为入庙对宫约定。没有声称这些章节记载星骰法 |
| 七曜三分性 | Claudius Ptolemy，《Tetrabiblos》，F. E. Robbins，Loeb 1940，卷一 [I.18](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html#18)；另核对 Ashmand 1822 的 XXI 章 | 分别保留昼、夜条件；不为骰面假定昼夜，不采用 Dorotheus 的轮替三主星表 |
| 七曜昼夜分派 | 同译本 [I.7](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/1B%2A.html#7) | 太阳、木星、土星为昼曜，月亮、金星、火星为夜曜；水星按晨星／昏星保留条件，不据此选定骰面对应的实际盘昼夜 |
| 七曜喜乐宫 | William Lilly，《Christian Astrology》，1647，pp.51–56，[原文转录](https://www.skyscript.co.uk/lilly_houses.html) | 水星1、月亮3、金星5、火星6、太阳9、木星11、土星12；只核对骰面宫号关系，不移用原文的生死、灾祸或临床断言 |
| 现代解释与示意轮 | FateBridge contributors，`astrodice_symbolic_v7` | 中文词义、元素/模式、角续果宫、现实核对提示及假设整宫轮，明确标作产品约定，不伪称原典直译 |

`symbolic_details.sign_condition.condition_evidence` 固定按 `domicile/exaltation/detriment/fall` 返回四项依据。七曜的 `matched` 是 `true/false`；超出七曜范围则为 `null`，对应 `basis_signs=null`，不能解释为四项均被否定。每项保留适用星座、推导方式、实际规则集和具体来源页。入庙使用 Ashmand XX，擢升和落陷使用 XXII；失势的对宫定义另引 Deborah Houlding [作者说明第二部分](https://www.skyscript.co.uk/dig2.html)，不再将混合结果全部挂在托勒密条文下。检索定位、短引文和页面 SHA-256 保留在来源见证（本地数据：`../tests/data/astrodice/tables/detriment-source.json`）。合成的 `sign_relationships` 规则属于 FateBridge，另列 `supporting_ruleset_ids`。

`interpretation.evidence` 把每段解释的 `text_path` 映射到实际 `fact_paths`、`rule_ids`、`ruleset_ids` 与解释类型。现代关键词、传统含义的现代转述、昼夜条件解释、现实核对提示分别标明；转述没有被标为原文引文。键名如 `condition_meanings_0` 可用点路径投影，`text_path` 才是实际文字位置。所有引用路径均针对同一份完整业务结果；只读了摘要的调用方应按同一 run 取回所需字段，不能为补来源另算一盘。现有 `verify_calculation_claims` 可核验这些字段的同 run 引述；它不认证任意自由文本语义。

问题原文仍在 `question` 和 `input_normalized.question` 中完整保留。快照的“问题原文（JSON引用）”及 `question_adjustment` 使用可逆的单行引用：换行、Unicode 行分隔符及引号不能伪造 `[符号解释]` 或 `[依据与边界]` 章节。问题内容不作为计算断语，`question_adjustment` 的依据类型为 `user_context`。

`symbolic_details.sign_condition.conditions` 允许多个关系同时存在，例如水星处女座同时 `domicile/exaltation`，水星双鱼座同时 `detriment/fall`。不使用互斥标签，不给三王星或交点强套七曜尊贵。`domicile_ruler` 是骰面星座的传统守护星；若恰为骰面本身，`dispositor_status=self_symbolic` 表示已知的符号自定位；否则为 `not_in_roll`，不得从假设轮或天象背景补写其骰面位置、定位星链或互容。

`symbolic_details.house_condition` 单独保留喜乐宫依据。七曜的 `in_joy` 为宫号比较结果；三王星和交点为 `null`，不能将“未定义”写成“不喜乐”。喜乐不是入庙、擢升或吉凶分数，例如水星处女一宫可同时具备两项星座关系与一项喜乐宫关系，三者不叠加成事件成功率。

附加天象从核心引擎同一次计算的 `context_geometry` 取未舍入的星体、宫头、角度、南交点和福点。福点调用共享的 `LOTS.fortune`／`compute_lot`，使用实际 ASC、核心太阳地平线判定的昼夜及同一黄道坐标，适配层不另写公式。早期适配器曾把第一宫宫头当上升点、按太阳所在宫判断昼夜；v3 修正公式来源，v4 继续消除中途四位小数舍入。等宫宫头在布局计算阶段也保留未舍入值。

例如南交点 359.99996° 仍在双鱼座，福点 29.99999° 仍在白羊座；不能先舍入至 0° 或 30° 再定星座、落宫。`chart` 数值现保留计算浮点值，`coordinatePolicy=unrounded_engine_values_not_an_accuracy_claim`；本工具天象文本也保留这些数值，避免把临界位置写成下一星座的起点；判断依据始终使用原值。数值位数不代表星历、输入资料或时间尺度的真实准确度。天象黄道转换也复用共享的半开区间归一化，避免极小负差取模时舍入成360°而被误归白羊；相同约定用于共享福点函数。其他旧式变形示意盘仍按各自合同处理。

恒星黄道背景采用 Swiss Ephemeris 的原生 Lahiri 接口：星体位置与速度使用 `FLG_SIDEREAL`，宫头与角度使用原生恒星黄道宫位接口。旧实现把含章动的视黄经减去不含章动的平均偏移，核验样例中造成约4–18角秒偏差；现已修复。`chart.params.chart_profile` 的 `sidereal_position_method`、`sidereal_house_method`、`ayanamsha_includes_nutation` 保留实际方法，`ayanamsha` 与 `ayanamsha_mean` 分别保留含章动和平均偏移，不能混作同一数值。地平线、赤纬和太阳昼夜条件仍使用实际天球坐标，不能用恒星黄道黄经代替。无 Swiss 运行时时仍明确标为偏移近似，不冒充原生计算。

原生接口一致性验证只证明符合声明的方法，独立 NASA/JPL 样本仍负责天文参考核对；二者均不能外推为全历元正确或占卜有效。依据见 [Swiss Ephemeris §12.2、§15.4](https://www.astro.com/swisseph/swephprg.htm)，本轮证据见恒星黄道审计。

`fortune_method` 选择附加天象福点的具体公式：

| 值 | 计算与来源 |
| --- | --- |
| `sect_reversing`（默认） | 昼为 ASC + Moon − Sun，夜为 ASC + Sun − Moon；保留共享 `LOTS.fortune` 约定，来源标为 `runtime_convention`，没有将它认证为指定原典 |
| `ptolemy_iii10` | 按 Ptolemy／F. E. Robbins 1940《四书》[III.10 正文中的福点公式](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/3B%2A.html#10)，昼夜均为 ASC + Moon − Sun；只采用这一公式，不采用本章的寿命推断 |

两式可能在夜盘相差很大，不能悄悄替换，也不能把一种公式的输出归给另一种原典。`chart.params.fortuneDefinition` 返回选定方法、实际公式、适用昼夜、作者、版本和来源；`ptolemy_iii10` 的 `sect_applied=null` 表示公式不随昼夜反转。这里认证的范围仅为所列公式，恒星黄道下使用同一算式也不代表整盘符合托勒密体系。两种选择都不影响骰面解释、喜乐宫或三分性条件。

天象背景通常以 `housePositionMethod=ecliptic_longitude_cusp_intervals` 按黄经宫头区间落宫。宫头需构成单圈顺行的十二个区间，边界比较保留输入浮点数的精确关系。高纬度 Regiomontanus 或 Polich/Page 宫头可能逆序或折返，此时原先的“不断加360°”会展开成多圈并错误分宫。现在保留原宫头及其宫号，改用 `swisseph_house_pos_zero_ecliptic_latitude`：按 [Swiss Ephemeris §16](https://www.astro.com/swisseph/swephprg.htm) 的原生 `house_pos`，传入热带黄经和0°黄纬，返回连续宫位，整数部分对应宫号。恒星黄道显示不会被直接当作热带输入。

原生投影参数保留在 `chart.params.housePositionProjection` 及核心 `chart_profile.house_position_projection`，包括版本、ARMC、真黄赤交角、地理纬度、宫制和输入坐标系。星体、交点与福点保留 `ecliptic_house_position`，快照也说明实际方法。0°黄纬投影延续仅依赖黄经的选择，不等于计入星体实际黄纬的空间落宫；逆序或折返的宫头标为 `native_nonprograde_cusps`。投影失败返回错误，不补成第一宫、十二宫或其他宫制。具体反例与限定验证见宫序与落宫审计。

极区宫制若采用相反的ASC或MC制宫分支，`chart_profile.house_axis_convention` 分别保留公开天球轴和原制宫轴；原宫头与落宫投影继续保留。占星骰快照同步附上这一字段的说明，解读时按各字段使用对应的轴。

`lunarNodeModel=mean_node_and_its_opposite` 表示平北交点及其对点，不把它写成真交点。落宫方法和交点模型均需连同天象输出保留。

`chart.params.ephemerisReferencePoints` 保留天象坐标的参考点。按[Swiss Ephemeris §2.4](https://www.astro.com/swisseph/swisseph.htm)，有卫星的原生行星位置采用系统质心；日月及无卫星的水星、金星为本体中心。本工具没有请求巨行星的 `CENTER_BODY` 修正，不能将系统质心写成本体中心。字段分别列出 `body_centers/system_barycenters/theoretical_points/approximate_points/unresolved_points/derived_points`，部分天体回退时按实际模型归类，近似位置不继承原生参考点的声明。快照同步呈现同一说明；这不改变既有数值或骰面解释，也不认证每个位置的绝对准确度。

已发布的 `astronomical_context` 视图同时读取实际输入、完整独立天象与计算依据；视图名不是请求参数，应将其 `fields` 传入调用。它保留默认 `symbolic` 首轮的用途。若天象业务字段分页延后，读取同一run的完整投影载荷并核对SHA-256后再解读，不把未读取当作不存在，也不重算来代替取回。

独立底层核验使用[Horizons几何向量](https://ssd-api.jpl.nasa.gov/doc/horizons.html)：明确TT、ICRF、地心、无光行时／光行差修正，并让目标ID与上述参考点一致。它避开不同日期黄道模型的混淆，但只核验给定时标的几何数据，不代替民用时标、视位置修正、宫位或交点验证。冻结协议（本地数据：`../tests/data/astrodice/tables/kernel-protocol.json`）的方向容差为0.02角秒，坐标分量诊断线为 `1e-8 AU`；不能事后放宽以掩盖失败。补充的9999年12月29日样本不会替代原协议中无法获取的12月31日参考。

本轮两平台各比较270组可用向量，方向检查全部在冻结容差内，但108组坐标分量未达诊断线，另有10组原始请求缺少外部参考。因此数值验收仍返回失败；应用回归通过不替代天文精度验收。原始响应、失败分布、独立原始系数插值探查及限定结论见参考点与底层星历审计。

源码环境可执行数据验收，报告保留每项结果、失败和缺失参考；数值失败退出1，只有参考缺失退出2，两者都不能称为完整通过：

```bash
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_kernel \
  --ephe ephe --protocol tests/data/astrodice/tables/kernel-protocol.json \
  --reference tests/data/astrodice/tables/kernel-horizons.json \
  --output /tmp/astrodice-kernel.json
```

需要更高的向量精度时，可显式选择[JPL原始DE441二进制文件](https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/)，绕过压缩数据及其求值路径。将完整文件放入 `SE_EPHE_PATH` 的搜索目录，设置 `FATEBRIDGE_JPL_FILE` 为文件名（不含目录）。该模式仅支持原始直接访问格式的DE441，不接受SPK/BSP文件；默认压缩数据路径保持原有行为。

也可准备完整、连续的所需年域，避免下载完整三万年文件。下例约下载 929 MB 原始记录，覆盖公历年 1 至 9999，并在两端保留至少 32 日供光行时和求导使用。准备器复制全部天体、原始常数及系数字节，只调整文件头的标题和覆盖范围；保存 HTTP 范围、ETag、字节摘要及失败状态。该 `--output` 年域模式与原有整文件下载的 `--dest`／`--ca-file` 模式互斥。它拒绝覆盖已有文件，不在计算请求中下载，也不切换默认来源。缓存应放在仓库及安装包之外。

```bash
uv run --locked --extra dev python -m fatebridge.fetch_jpl \
  --start-year 1 --end-year 10000 \
  --output /absolute/path/to/raw-jpl/de441-0001-10000.eph
uv run --locked --extra dev python -m fatebridge.fetch_jpl \
  --output /absolute/path/to/raw-jpl/de441-0001-10000.eph --verify-only
```

使用该文件时将下例的 `FATEBRIDGE_JPL_FILE` 改为 `de441-0001-10000.eph`。`--end-year` 为不包含的结束年；例如 `3000` 至 `3600` 会生成整个 600 年段，约 56 MB。单个测试记录窗口不能替代这样的完整来源。

```bash
SE_EPHE_PATH=/absolute/path/to/raw-jpl \
FATEBRIDGE_JPL_FILE=linux_m13000p17000.441 \
uv run --locked --extra dev python -m fatebridge.cli otherbu \
  --planet Jupiter --sign Aries --house 0 \
  --date 2000-01-01 --time 12:00 --zone UTC --gps-lat 51.5 --gps-lon 0
```

文件不存在、结构不支持、时刻越界或原生库降级时，返回 `ephemeris_source_inconsistent` 错误，不以近似星体位置完成该次天象计算。此选择作用于FateBridge托管的原生带标志调用；`time_equ` 等无星历选项的原生辅助函数仍保留自身算法，不能因此全部改标为原始JPL计算。并发集成仍须遵守共享运行时锁，无法保证不参与锁的外部原生调用不干扰状态。

缺少原生库时返回 `dependency_missing`；原生初始化异常也返回明确错误。即使整宫制原本支持离线近似，显式选择JPL后也不以这种近似代替请求的天象。只读取三枚骰面时仍不需要天象或JPL文件。

JPL模式的 `chart.params.chart_profile.physical_ephemeris_source` 返回实际文件SHA-256、DE版本及头部区间。原生文件槽对JPL返回零区间和零版本，因此这些信息由直接访问文件头读取，不能用零值或文件名猜测。大文件采用分块散列以控制内存；每次天象计算仍有完整文件读取成本。JPL文件不属于现有 `.se1` 指纹清单，`matches_packaged_manifest=false` 不应改写为已获官方校验和认证。测试所附J2000文件只是明确声明的三个连续记录，不能当作完整安装。

相同冻结协议也可直接比较原始JPL路径：

```bash
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_kernel \
  --ephe /absolute/path/to/raw-jpl --jpl-file linux_m13000p17000.441 \
  --protocol tests/data/astrodice/tables/kernel-protocol.json \
  --reference tests/data/astrodice/tables/kernel-horizons.json \
  --output /tmp/astrodice-jpl-kernel.json
```

原始JPL路径通过可用样本也不能补成Horizons未返回的十项原始时刻，或认证全部视位置、时标、交点、宫位和原典解释。这里仍保留Swiss对给定TT的星历参数处理，未独立认证TT/TDB转换或实际观测精度。

可选路径、严格错误边界、双平台实际数据比较及未通过项见原始JPL路径审计。

### 瞬时运动与速度核验

附加天象保留 `chart.chart.objects[].motion` 中未经舍入的 `longitude_speed`（度/日）、`direction`、`reference_frame`、`basis` 和 `source_model`，以及修正前的 `native_longitude_speed`、实际应用的 `light_time_correction` 与 `rotation_correction`。最终日速是原生值与返回修正项之和。热带与Lahiri分别使用对应原生参考系，不能只平移经度却复用热带速度。原生接口缺少请求的 `FLG_SPEED` 或返回非有限日速时，以 `coordinate_motion_unavailable` 原因拒绝本次天象，不把缺值、NaN或未计算的零值解释成顺行。

`direct/retrograde` 根据最终未经舍入日速的正负判定；恰为零时返回 `zero_instantaneous_rate`，它没有定位一次留站事件。南交点是北交点黄经加180°，继承其同参考系日速；福点缺少上升点导数，返回 `not_computed`，不只用月亮减太阳日速拼出完整福点运动。近似轨道路径未提供导数的星体及其依赖点也保留未知。`chart.params.motionPolicy` 列出实际未计算点和范围，快照读取同一日速字段。依据是[Swiss程序手册§3.3.3、§3.4、§12.2](https://www.astro.com/swisseph/swephprg.htm)的速度选项、六分量返回值及原生恒星黄道接口。

`chart.params.chart_profile.longitude_motion` 记录源码推导的方法、版本、适用状态及物理来源。针对已检查的原生2.10.03／绑定2.10.3.2，月球JPL与Swiss物理后端增加所采用光行时定义的链式导数，并经光行差位置变换的雅可比传播；热带日速另补最终黄道转动中的章动黄赤交角导数项，Lahiri的NONUT路径不加此项。这些项来自位置算法的求导，不按参考残差拟合。未验证版本或不支持的月球后端保留原生值并明确标记；参与修正的来源、坐标标志或位置重现不一致时拒绝计算。位置及骰面规则保持原算法。

独立参考仍有超线项及模板不确定性，新增留出样本的局部改善不等于整体通过。原始量46失败、早先模板失败和缺失端点均保留。推导与后续证据见视运动调查及月球运动审计。

复核新的月球诊断时，物理数据仍按前述环境变量选择；显式JPL示例：

```bash
SE_EPHE_PATH=/absolute/path/to/raw-jpl FATEBRIDGE_JPL_FILE=linux_m13000p17000.441 \
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_lunar_motion \
  --protocol tests/data/astrodice/tables/lunar-chain-protocol.json \
  --reference tests/data/astrodice/tables/lunar-chain-reference.json \
  --output /tmp/astrodice-lunar-motion.json
```

该诊断保留数值失败退出码；应用回归通过不能将它改记为通过。

这些运动属于独立天象背景，不是骰面星的运动条件，不能替三枚骰面添加逆行、留站或应期。`astronomical_motion` 是已发布字段视图；按其字段列表传 `fields`，视图名本身不是参数。保留 `motionPolicy` 和 `validation`，不能只读一个方向标签。

底层几何速度另按冻结速度协议（本地数据：`../tests/data/astrodice/tables/velocity-protocol.json`）核验。它复用已有公开Horizons参考中的速度分量；阈值在查看速度残差前固定为每坐标分量 `1e-10 AU/日`、视线单位向量导数差 `0.002角秒/日`，不改动原位置容差，也不把方向导数称为黄经速度。这是限定工程诊断，不是全历元Swiss精度保证，也不是新盲测。协议明确保留原始缺失时刻和补充样本的区别。

```bash
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_kernel \
  --ephe /path/to/jpl-directory --jpl-file linux_m13000p17000.441 \
  --protocol tests/data/astrodice/tables/kernel-protocol.json \
  --reference tests/data/astrodice/tables/kernel-horizons.json \
  --velocity-protocol tests/data/astrodice/tables/velocity-protocol.json \
  --output /tmp/astrodice-jpl-velocity.json
```

[Horizons手册](https://ssd.jpl.nasa.gov/horizons/manual.html)说明内部动力学采用TDB。这里比较的是已有TT标签历元返回的几何状态；没有独立认证TT速率变换、日期黄道视黄经日速、真实留站时刻或现实预测能力。已知失败、缺项、负对照和双平台结果见运动审计。

### 坐标含义、太阳高度与独立视运动参考

原生返回值还须符合请求的坐标约定：核心热带位置、赤道位置和Lahiri位置分别核对球坐标、度、日期参考系、地心及视位置修正标志；Lahiri原生计算自动加入 `NONUT`，不能将它误判为异常。有限的赤经仍不是黄经，有限的弧度也不是度。标志不符返回 `coordinate_contract_changed`；缺失、非有限或越域的坐标／太阳高度返回 `coordinate_values_unavailable`，不继续解释为有效盘面。

太阳几何中心高度为零仍计昼，这一约定只作用于有效的有限高度。旧实现中 `NaN>=0` 为假，会错误选夜，连带改变按昼夜反转的福点；现已拒绝这种来源错误。原生地平接口返回畸形结果也不会靠近似回退掩盖；正常的接口不可用回退仍按已有近似模型标注。

新的冻结视运动协议（本地数据：`../tests/data/astrodice/tables/apparent-motion-protocol.json`）单独比较Horizons量45/46的视ICRF方向与角速度，含光行时、引力偏折及光行差；目标参考点和TT历元均显式记录。新增30个日期由固定SHA-256种子选定，不根据残差挑选。ERFA的IAU2006/2000A偏置—岁差—章动矩阵及真黄赤交角只用于这30个现代日期的显示黄道核验，并保留坐标轴导数，不能只旋转位置后遗漏速度中的参考系运动。

本次取得570组可用视方向／速率和300组现代显示黄道参考，但量46与位置求导出现不一致。为查明差异，另在发现问题后冻结位置求导协议（本地数据：`../tests/data/astrodice/tables/apparent-derivative-protocol.json`），获取每个可用时刻前后的六个位置，用固定一小时和半小时五点模板分别求导。它是追加诊断，不能冒充原始盲测、替换原协议或抹掉原始速率比较失败。两步模板之间也有高于诊断线的差异，不能把全部派生速率当作无误差真值。

目前这些证据没有证明视黄经日速全面达标；原生速度与位置导数的残余差异仍须调查。原始响应、来源量之间的差异、模板收敛、具体计算修复和双平台结果见视运动与坐标契约审计，光行时链式导数原型和后续运行修正分别见调查推导及月球运动审计。几何速度通过、位置通过、应用测试通过分别保留，不合并成“满分”。

```bash
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_apparent \
  --ephe /path/to/jpl-directory --jpl-file linux_m13000p17000.441 \
  --protocol tests/data/astrodice/tables/apparent-motion-protocol.json \
  --reference tests/data/astrodice/tables/apparent-horizons.json \
  --derivative-protocol tests/data/astrodice/tables/apparent-derivative-protocol.json \
  --derivative-reference tests/data/astrodice/tables/apparent-position-derivative.json \
  --output /tmp/astrodice-apparent-motion.json
```

天体原生计算失败时，仅该天体回退到轨道近似，其他成功的原生位置继续保留；旧实现会因一颗失败而丢弃整盘原生结果。出现回退时，`chart.params.chart_profile.planetary_models` 逐颗保留模型，`orbital_fallback.approximate_planets` 列出近似天体，核心摘要和快照同时说明。混合盘标为 `mixed_precision_runtime_model` / `swisseph_api_with_approximate_orbits`；恒星黄道下，成功天体继续用原生Lahiri接口，回退天体采用已声明的黄道偏移近似，`sidereal_planetary_methods` 逐颗区分两者。

轨道近似保留原有UT日数、忽略TT差异的约定，不能当成原生星历或远期精度认证。[Schlyter方法说明](https://stjarnhimlen.se/comp/ppcomp.html)明确列出这类简化及远期局限；FateBridge的具体近似实现以返回的 `source_path` 为准，不将教程的误差说明认证为本实现保证。回退信息的 `candidate_files` 是候选行星／月球分段清单，不是文件完整性或已加载模型检查。

成功天体的模型标签取自原生返回标志。平交点不是实体行星；[Swiss文档§2.2.1](https://www.astro.com/swisseph/swisseph.htm)说明平交点使用另行构建的月球理论模型，JPL星历本身不提供平交点。因此平北交点返回 `swieph` 标志，并不证明它读取了某份 `.se1` 文件，也不能用这个标志认证节点的独立天文准确度。

远期日期可按[官方分段表](https://www.astro.com/swisseph/swisseph.htm)补齐数据：`uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 9999` 选择 `sepl_96.se1` 和 `semo_96.se1`。600年分段交界会同时选择相邻年份可能需要的文件。自定义下载目录须设置 `SE_EPHE_PATH`，服务重启后再核对实际模型。仅解读三枚骰面仍不需要星历下载。具体反例和验证记录见逐体回退与分段审计。

缺少原生星历时，共享近似角度公式仍按东侧黄道／地平交点选取ASC。旧公式在部分高纬度时刻会选中西侧对点，偏差可达180°，并传递到宫位和福点；现已增加东半球分支判定。核验分别检查[USNO地平坐标方程](https://aa.usno.navy.mil/faq/alt_az)的地平线约束、东侧方向，以及相同ARMC和黄赤交角下的原生接口。近似恒星时和黄赤交角仍有误差，分支修正不能认证所有历元的天文准确度。[Swiss Ephemeris通用文档§6.4](https://www.astro.com/swisseph/swisseph.htm)说明了其东半球约定。

精确地理极点（纬度±90°）保留星体、宫位和角度的约定计算，`chart.params.chart_profile.angle_definition` 同时返回 `geographic_pole_meridian_convention`：输入经度在此定义参考子午线；固定天球方向不发生由地球自转造成的每日升落。ASC、天顶、宫位和依赖ASC的福点应连同此约定读取，不能当作物理升起时刻。核心摘要与本工具快照使用同一说明；邻近极点的普通纬度不被改标为精确极点。几何推导、具体反例、测试范围与残余问题见高纬度角度审计。

另一种退化发生在黄道与地平面接近重合时。按[USNO地平坐标方程](https://aa.usno.navy.mil/faq/alt_az)推导，零黄纬方向的高度满足 `sin(alt)=A cos(λ)+B sin(λ)`，其中 `A=cos(φ) cos(ARMC)`、`B=cos(φ) sin(ARMC) cos(ε)+sin(φ) sin(ε)`。`R=hypot(A,B)` 是两平面锐夹角的正弦，`R=0` 时整条黄道均在地平面上，不存在唯一几何ASC。这是从坐标方程得出的几何结论，不是某部占星原典的引文。

`angle_definition` 在 `R≤sqrt(binary64 ε)` 时返回 `ecliptic_horizon_ill_conditioned`，在 `R≤64 binary64 ε` 时改为 `ecliptic_horizon_numerically_unresolved`、`geometric_ascendant_resolved=false`。前者仍有数值交线但对扰动高度敏感；后者不能用这些浮点数分辨唯一ASC，返回角度仅为后端数值约定。这里的阈值用于数值条件检查，不是观测、经纬度、时间或天文模型误差界，也不能证明物理平面精确重合。返回实际ARMC、黄赤交角、系数、R和所用阈值；核心摘要与占星骰快照保留同一解释。仅依赖ASC的宫头、落宫及福点受此限定，MC和不依赖ASC的星体位置继续保留。

检查使用实际角度模型：原生路径读取 `houses_ex` 的赤道ARMC及与其内部UT1／Delta-T约定一致的真黄赤交角；恒星黄道也不把Lahiri黄经或黄道偏移当作ARMC。离线路径使用自身的近似恒星时和平均黄赤交角。原有数值没有被替换成一个假定的正确上升点。具体反例及验证范围见地平交线退化审计。

`chart.params.chart_profile.earth_rotation` 记录实际采用的地球自转模型。`fatebridge_standard_rotation_v2` 在J2000前后各200儒略年范围内采用[IERS 2010表5.2e](https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt)的恒星时表达式，并使用Swiss的章动及平均黄赤交角；范围外保留Swiss长期模型的变化形状，在对应边界加一个常数相位差，使两模型的角度连续衔接。范围和常数由FateBridge确定；[Swiss文档6.1](https://www.astro.com/swisseph/swisseph.htm)提供的是常数偏移衔接的方法说明，不是对本系统边界或精度的认证。

旧采纳边界的硬切换会产生约0.36、0.68角秒的跳变，现由相位对齐消除。公开原生几何接口接收的是经恒星时差旋转后的计算坐标系经度，用户输入的实际经纬度继续保留；不改动UTC、UT1或TT输入。`longterm_phase_alignment` 在使用长期相位对齐时记录方法、边界和未认证范围，未应用时为 `null`。常数对齐只保证所检验的角度衔接，不保证导数连续，也不证明远期绝对位置准确。

独立ERFA参考冻结39个时刻、195个地点组合，生成进程不导入FateBridge或Swiss；它核验给定TT／UT1下的恒星时与空间两轴，不独立认证输入时标、实测地球定向或所有宫制。原生Lahiri合同继续以 `1e-9` 度容差检查几何及黄道转换，同时让时钟接受独立参考核验；不再把2050年后采用不同默认时钟的原生 `houses_ex` 当作同模型对照。故意关闭标准自转或恢复边界硬切换的负对照必须失败。具体数值及残余问题见恒星时模型与衔接审计。

`symbolic_details.triplicity_condition` 将《四书》Robbins I.18 的总体分派与条件角色分别保留。`assigned_rulers` 列出该章分派给三角的主星，`in_assigned_group` 表示骰面星在这个总体分派中的关系；火象为太阳、木星，土象为月亮、金星，风象为土星、水星，水象为火星、月亮、金星。这不是对所有昼夜条件逐一授予尊贵，也不是 Dorotheus 的三主星轮替。

`rulers_by_sect.day/night` 继续列首要主星及原文明确列出的条件共管主星，`matches_by_sect` 继续只比较这些所列角色。`match_definition` 保留这一口径，`roles_by_sect` 用 `primary/co_ruler/assigned_not_selected/not_assigned/outside_seven_planet_scope` 说明具体关系。比如木星白羊座属于火象三角总体分派，但昼条件所列首要主星为太阳：`in_assigned_group=true`、`matches_by_sect.day=false`、`roles_by_sect.day=assigned_not_selected`；夜条件则为木星首要治理。原解释“不属于该组”在v6中修正为对总体分派和具体条件角色的分别说明。

水象保留火星与昼金星／夜月亮共管。`sect=null` 保留未知；三王星、交点的总体匹配及条件匹配均为 `null`，不是 `false`。`interpretation.triplicity_meaning` 和 `conditional_triplicity` 规则链同步呈现总体分派与昼夜条件，附加天象不会替骰面选择昼夜。`sign_condition.unassessed` 中的 `applied_triplicity_sect` 仍表示尚未选定适用条件。原典转录及反例见三角分派参考表（本地数据：`../tests/data/astrodice/tables/triangle-assignment-robbins-1940.json`）和v6原典角色审计。

`symbolic_details.planet_sect_condition` 在v7补入同译本I.7的星体昼夜分派。`natural_sect` 是原典对星体的分派：太阳、木星、土星为 `day`；月亮、金星、火星为 `night`。土星和火星的分派按原文的调和原则说明，不能按“冷就属夜、干热就属昼”倒推。它也不是I.18的三分性治理角色，例如木星是昼曜，不改变其在火象三角的夜条件首要治理角色。

水星的 `natural_sect=null`；`assignments_by_solar_phase` 同时保留 `morning_star=day`、`evening_star=night`，表示尚缺晨昏条件，不把“兼具两种条件”输出成一个已选定的 `neutral` 派别。三王星、交点超出七曜范围，分派和条件表均为 `null`。所有骰面均保留 `solar_phase/applied_chart_sect/matches_chart_sect=null`；骰面宫号不决定太阳高度，独立天象背景也不为符号骰面补上观测位置。新增解释、规则链和快照均引用同一字段及I.7来源，见原典标注（本地数据：`../tests/data/astrodice/tables/planet-sect-robbins-1940.json`）。

三枚骰面没有精确度数、两颗星的实际相对位置或实际盘的昼夜条件，因此不计算界、面、度数尊贵、出入相、逆行、燃烧、是否合派／逆派、接纳或精确应期。星体的原典昼夜分派与这些未计算项分别保留。没有列出四种星座关系不等于“游离”或“毫无尊贵”。

假设整宫轮以骰面星座位于骰面宫为约定，向前后排满十二星座。`symbolic_house_ring` 与 `houses_ruled_by_rolled_planet` 仅展示这种约定下的议题连接；轮上的宫首经度不是实际宫头，第一宫不是计算出的上升点。没有出生盘输入时，不做出生盘比较。

每项结果保留 `rulesets` 的作者、版本、来源 URL／仓库相对路径、来源类型和范围，以及 `rule_trace` 的输入、命中规则和结果。现代关键词和现实建议不冒充原典引文；附加天象也不能为骰面解释补充不存在的事实。

## 验证范围与现实预测

独立数值参考和原始物理资料保存在 `tests/data/astrodice`，由 `reference-material.json` 给出唯一当前相对路径、来源身份和原始数据摘要。原始 JPL 系数、Horizons 响应、打印区间、源算法常数及原协议中的全部样本与误差线保留。维护中的 Python 文件和原生二进制不作为正确性真值；退役的生产源码、执行日志和整盘快照不参与当前评分。

`scripts/astrodice/audit_astrodice_display_rate.py` 对原开发／留出群体的 40 项目标／后端组合执行当前计算，再与独立区间参考比较；`scripts/astrodice/audit_astrodice_lunar_pipeline.py` 对原 12 项月球固定框架组合执行相同流程。位置线为 `0.02` 角秒，日速线为 `0.002` 角秒／源日。每项失败、不可用状态和两种后端都保留，不以选择编码、尺度或删除样本改善结果。源坐标使用的名义 TDB 数值与 TT 命名参数相同，不证明两种物理时标等价；共享旋转也不是独立显示框架精度证明。

在原 `3000-12-07T04:07:32` 数值时刻，压缩星历后端的月球视黄经日速仍比原独立区间高约 `0.00260713472` 角秒／源日，超过 `0.002` 原线；位置误差约 `0.00030606` 角秒，在 `0.02` 原线内。独立原始 DE441 系数核对将主要速度残差定位到压缩星历的几何源层；原生速度与自身位置多步长求导相符，不能用重新求导恢复已丢失的源精度。当前官方 `semo_30.se1` 与所检查的本地文件字节一致。对 2.10.3.2 所含原生 C 源码的系数计数作独立解包和重新编译实验，保留末个有效项或全部项后，该点仍分别约为 `0.00260317`、`0.00260318`，均未过线，且留出样本有轻微变差；这些实验未替换运行库或默认数据。

`scripts/astrodice/audit_astrodice_lunar_precision.py` 评分当前完整固定接收框架导数，并把原生未修正速度另列诊断。原 137 个中心中的 135 个可评项保留，另两项缺测仍未通过；当前可评项只有上述月球点的日速超过 `0.002`，最大位置误差约 `0.00206794` 角秒。该审计继续返回非零。REST、MCP、CLI 在该点交付相同的原生来源、位置及日速，传输一致不改变数值失败结论。NASA 将原始 DE 系数的积分时标定义为 [TDB](https://ssd.jpl.nasa.gov/planets/eph_export.html)；在该点代入两种时标模型的日速灵敏度约为 `0.000019` 角秒／日，不能解释现有超差，也不构成年 3000 的物理时标精度证明。

显式选择准备器生成的完整 AD1 至 AD10000 原始 DE441 源后，原 135 个可评项均满足原线，最大方向日速误差约 `0.00109586` 角秒／日、位置误差约 `0.00213165` 角秒；两项原缺测仍为缺测，因此完整 137 项审计返回 `reference_evidence_unresolved` 和退出码 2。另在查询和候选评分前声明的 12 个跨域留出时刻，228 个同 TT／ICRF／地心参考探针得到的日速与位置误差最大分别约 `0.00055658`、`0.00170741` 角秒，均满足原线。这条精确来源路径使用已有公开 JPL 选择，不代表恢复了 Swiss 压缩文件的信息，也不改判其原失败。新留出的原协议和 NASA 响应位于 `tests/data/astrodice/precise-source-holdout`。

原缺证的两个中心另有独立补证，未修改旧 137 项参考：AD1 中心原来因采集器不能表示年 0，漏取了 7 个负偏移探针。按 Horizons 的公元前标签重新请求后，全部 19 个原模板探针可得；完整 JPL 源的方向日速误差约 `0.00044182` 角秒／日、位置误差约 `0.00131508` 角秒，模板步长差约 `0.00004922` 角秒／日，均满足原线。AD9999 中心则仍受 NASA 实际返回的 `9999-DEC-30 12:00:00.0011 TT` 上界限制，原模板的 6 个正偏移探针不可得；不改用单边模板。[Horizons 文档](https://ssd.jpl.nasa.gov/horizons/manual.html#long-term-ephemerides)也说明当前公开年域受 Y10K 问题限制。因此可报告原 135 项加独立补证 1 项，另 1 项原协议仍未验收；不能称旧 137 项文件通过。新补证的协议、原始响应及实际采集时间保存在 `tests/data/astrodice/original-endpoint-supplement`。

按现行进程环境复核补证，命令在完整 JPL 源下仍返回退出码 2，保留 AD9999 未验收状态：

```bash
SE_EPHE_PATH=/absolute/path/to/raw-jpl FATEBRIDGE_JPL_FILE=de441-0001-10000.eph \
uv run --locked --extra dev python -m scripts.astrodice.audit_astrodice_lunar_endpoint_supplement \
  --directory tests/data/astrodice/original-endpoint-supplement \
  --output /tmp/astrodice-lunar-endpoint-supplement.json
```

历史负证据单独保存在 `historical-failures.json`，不作为当前原生输出的预期快照，也不因当前工程测试通过改判。保留的问题包括：压缩星历的月球日速超线、近太阳盘内或盘后水星的位置／日速分离、金星参考模板与标签预算未决、远未来缺测，以及原始几何坐标分量诊断线失败。独立模型或新增局部留出通过只限定所列样本与参考模型；事件根比较通过也不能替代同点位置精度；原完整数值门槛、物理时标、全历元准确度和现实预测效度仍不能据此认证。

骰面规则的可复现、原典解释的忠实程度、天文数值精度和现实预测效度分别验收。符号组合的描述不等于事件概率，也不能用工程回归通过替代现实证据。
