# 占星骰：符号、原典关系与天象背景

`otherbu` 解读用户已有的三枚骰面，规则版本 `astrodice_symbolic_v7`。它不代替用户抽骰，不接收塔罗牌阵。缺失或无效骰面会被拒绝，不再默认为太阳、白羊、一宫。

## 输入与迁移

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

有效本地年 1／9999 的 UTC 标签可能跨到天文年 0／公历年 10000。现在保留该物理时刻及扩展年份字符串，例如 `0000-12-31T10:00:00+00:00`、`+010000-01-01T11:59:00+00:00`，不裁剪输入日期。UTC 整数日序、微秒、固定闰秒假设和三种协议的限定验收见UTC 跨年界修复（本地数据：`validation/astrodice-utc-boundary.md`）；Python `datetime` 不能直接解析这些扩展标签。

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

`symbolic_details.sign_condition.condition_evidence` 固定按 `domicile/exaltation/detriment/fall` 返回四项依据。七曜的 `matched` 是 `true/false`；超出七曜范围则为 `null`，对应 `basis_signs=null`，不能解释为四项均被否定。每项保留适用星座、推导方式、实际规则集和具体来源页。入庙使用 Ashmand XX，擢升和落陷使用 XXII；失势的对宫定义另引 Deborah Houlding [作者说明第二部分](https://www.skyscript.co.uk/dig2.html)，不再将混合结果全部挂在托勒密条文下。检索定位、短引文和页面 SHA-256 保留在来源见证（本地数据：`../tests/fixtures/astrodice-detriment-source.json`）。合成的 `sign_relationships` 规则属于 FateBridge，另列 `supporting_ruleset_ids`。

`interpretation.evidence` 把每段解释的 `text_path` 映射到实际 `fact_paths`、`rule_ids`、`ruleset_ids` 与解释类型。现代关键词、传统含义的现代转述、昼夜条件解释、现实核对提示分别标明；转述没有被标为原文引文。键名如 `condition_meanings_0` 可用点路径投影，`text_path` 才是实际文字位置。所有引用路径均针对同一份完整业务结果；只读了摘要的调用方应按同一 run 取回所需字段，不能为补来源另算一盘。现有 `verify_calculation_claims` 可核验这些字段的同 run 引述；它不认证任意自由文本语义。

问题原文仍在 `question` 和 `input_normalized.question` 中完整保留。快照的“问题原文（JSON引用）”及 `question_adjustment` 使用可逆的单行引用：换行、Unicode 行分隔符及引号不能伪造 `[符号解释]` 或 `[依据与边界]` 章节。问题内容不作为计算断语，`question_adjustment` 的依据类型为 `user_context`。

`symbolic_details.sign_condition.conditions` 允许多个关系同时存在，例如水星处女座同时 `domicile/exaltation`，水星双鱼座同时 `detriment/fall`。不使用互斥标签，不给三王星或交点强套七曜尊贵。`domicile_ruler` 是骰面星座的传统守护星；若恰为骰面本身，`dispositor_status=self_symbolic` 表示已知的符号自定位；否则为 `not_in_roll`，不得从假设轮或天象背景补写其骰面位置、定位星链或互容。

`symbolic_details.house_condition` 单独保留喜乐宫依据。七曜的 `in_joy` 为宫号比较结果；三王星和交点为 `null`，不能将“未定义”写成“不喜乐”。喜乐不是入庙、擢升或吉凶分数，例如水星处女一宫可同时具备两项星座关系与一项喜乐宫关系，三者不叠加成事件成功率。

附加天象从核心引擎同一次计算的 `context_geometry` 取未舍入的星体、宫头、角度、南交点和福点。福点调用共享的 `LOTS.fortune`／`compute_lot`，使用实际 ASC、核心太阳地平线判定的昼夜及同一黄道坐标，适配层不另写公式。早期适配器曾把第一宫宫头当上升点、按太阳所在宫判断昼夜；v3 修正公式来源，v4 继续消除中途四位小数舍入。等宫宫头在布局计算阶段也保留未舍入值。

例如南交点 359.99996° 仍在双鱼座，福点 29.99999° 仍在白羊座；不能先舍入至 0° 或 30° 再定星座、落宫。`chart` 数值现保留计算浮点值，`coordinatePolicy=unrounded_engine_values_not_an_accuracy_claim`；本工具天象文本也保留这些数值，避免把临界位置写成下一星座的起点；判断依据始终使用原值。数值位数不代表星历、输入资料或时间尺度的真实准确度。天象黄道转换也复用共享的半开区间归一化，避免极小负差取模时舍入成360°而被误归白羊；相同约定用于共享福点函数。其他旧式变形示意盘仍按各自合同处理。

恒星黄道背景采用 Swiss Ephemeris 的原生 Lahiri 接口：星体位置与速度使用 `FLG_SIDEREAL`，宫头与角度使用原生恒星黄道宫位接口。旧实现把含章动的视黄经减去不含章动的平均偏移，核验样例中造成约4–18角秒偏差；现已修复。`chart.params.chart_profile` 的 `sidereal_position_method`、`sidereal_house_method`、`ayanamsha_includes_nutation` 保留实际方法，`ayanamsha` 与 `ayanamsha_mean` 分别保留含章动和平均偏移，不能混作同一数值。地平线、赤纬和太阳昼夜条件仍使用实际天球坐标，不能用恒星黄道黄经代替。无 Swiss 运行时时仍明确标为偏移近似，不冒充原生计算。

原生接口一致性验证只证明符合声明的方法，独立 NASA/JPL 样本仍负责天文参考核对；二者均不能外推为全历元正确或占卜有效。依据见 [Swiss Ephemeris §12.2、§15.4](https://www.astro.com/swisseph/swephprg.htm)，本轮证据见恒星黄道审计（本地数据：`validation/astrodice-sidereal-audit.json`）。

`fortune_method` 选择附加天象福点的具体公式：

| 值 | 计算与来源 |
| --- | --- |
| `sect_reversing`（默认） | 昼为 ASC + Moon − Sun，夜为 ASC + Sun − Moon；保留共享 `LOTS.fortune` 约定，来源标为 `runtime_convention`，没有将它认证为指定原典 |
| `ptolemy_iii10` | 按 Ptolemy／F. E. Robbins 1940《四书》[III.10 正文中的福点公式](https://penelope.uchicago.edu/Thayer/E/Roman/Texts/Ptolemy/Tetrabiblos/3B%2A.html#10)，昼夜均为 ASC + Moon − Sun；只采用这一公式，不采用本章的寿命推断 |

两式可能在夜盘相差很大，不能悄悄替换，也不能把一种公式的输出归给另一种原典。`chart.params.fortuneDefinition` 返回选定方法、实际公式、适用昼夜、作者、版本和来源；`ptolemy_iii10` 的 `sect_applied=null` 表示公式不随昼夜反转。这里认证的范围仅为所列公式，恒星黄道下使用同一算式也不代表整盘符合托勒密体系。两种选择都不影响骰面解释、喜乐宫或三分性条件。

天象背景通常以 `housePositionMethod=ecliptic_longitude_cusp_intervals` 按黄经宫头区间落宫。宫头需构成单圈顺行的十二个区间，边界比较保留输入浮点数的精确关系。高纬度 Regiomontanus 或 Polich/Page 宫头可能逆序或折返，此时原先的“不断加360°”会展开成多圈并错误分宫。现在保留原宫头及其宫号，改用 `swisseph_house_pos_zero_ecliptic_latitude`：按 [Swiss Ephemeris §16](https://www.astro.com/swisseph/swephprg.htm) 的原生 `house_pos`，传入热带黄经和0°黄纬，返回连续宫位，整数部分对应宫号。恒星黄道显示不会被直接当作热带输入。

原生投影参数保留在 `chart.params.housePositionProjection` 及核心 `chart_profile.house_position_projection`，包括版本、ARMC、真黄赤交角、地理纬度、宫制和输入坐标系。星体、交点与福点保留 `ecliptic_house_position`，快照也说明实际方法。0°黄纬投影延续仅依赖黄经的选择，不等于计入星体实际黄纬的空间落宫；逆序或折返的宫头标为 `native_nonprograde_cusps`。投影失败返回错误，不补成第一宫、十二宫或其他宫制。具体反例与限定验证见宫序与落宫审计（本地数据：`validation/astrodice-house-position-audit.json`）。

极区宫制若采用相反的ASC或MC制宫分支，`chart_profile.house_axis_convention` 分别保留公开天球轴和原制宫轴；原宫头与落宫投影继续保留。占星骰快照同步附上这一字段的说明，解读时按各字段使用对应的轴。

`lunarNodeModel=mean_node_and_its_opposite` 表示平北交点及其对点，不把它写成真交点。落宫方法和交点模型均需连同天象输出保留。

`chart.params.ephemerisReferencePoints` 保留天象坐标的参考点。按[Swiss Ephemeris §2.4](https://www.astro.com/swisseph/swisseph.htm)，有卫星的原生行星位置采用系统质心；日月及无卫星的水星、金星为本体中心。本工具没有请求巨行星的 `CENTER_BODY` 修正，不能将系统质心写成本体中心。字段分别列出 `body_centers/system_barycenters/theoretical_points/approximate_points/unresolved_points/derived_points`，部分天体回退时按实际模型归类，近似位置不继承原生参考点的声明。快照同步呈现同一说明；这不改变既有数值或骰面解释，也不认证每个位置的绝对准确度。

已发布的 `astronomical_context` 视图同时读取实际输入、完整独立天象与计算依据；视图名不是请求参数，应将其 `fields` 传入调用。它保留默认 `symbolic` 首轮的用途。若天象业务字段分页延后，读取同一run的完整投影载荷并核对SHA-256后再解读，不把未读取当作不存在，也不重算来代替取回。

独立底层核验使用[Horizons几何向量](https://ssd-api.jpl.nasa.gov/doc/horizons.html)：明确TT、ICRF、地心、无光行时／光行差修正，并让目标ID与上述参考点一致。它避开不同日期黄道模型的混淆，但只核验给定时标的几何数据，不代替民用时标、视位置修正、宫位或交点验证。冻结协议（本地数据：`../tests/fixtures/astrodice-kernel-protocol.json`）的方向容差为0.02角秒，坐标分量诊断线为 `1e-8 AU`；不能事后放宽以掩盖失败。补充的9999年12月29日样本不会替代原协议中无法获取的12月31日参考。

本轮两平台各比较270组可用向量，方向检查全部在冻结容差内，但108组坐标分量未达诊断线，另有10组原始请求缺少外部参考。因此数值验收仍返回失败；应用回归通过不替代天文精度验收。原始响应、失败分布、独立原始系数插值探查及限定结论见参考点与底层星历审计（本地数据：`validation/astrodice-kernel-reference-audit.json`）。

源码环境可执行数据验收，报告保留每项结果、失败和缺失参考；数值失败退出1，只有参考缺失退出2，两者都不能称为完整通过：

```bash
uv run --locked --extra dev python scripts/audit_astrodice_kernel.py \
  --ephe ephe --protocol tests/fixtures/astrodice-kernel-protocol.json \
  --reference tests/fixtures/astrodice-kernel-horizons.json \
  --output /tmp/astrodice-kernel.json
```

需要更高的向量精度时，可显式选择[JPL原始DE441二进制文件](https://ssd.jpl.nasa.gov/ftp/eph/planets/Linux/de441/)，绕过压缩数据及其求值路径。将完整文件放入 `SE_EPHE_PATH` 的搜索目录，设置 `FATEBRIDGE_JPL_FILE` 为文件名（不含目录）。该模式仅支持原始直接访问格式的DE441，不接受SPK/BSP文件；默认压缩数据路径保持原有行为。

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
uv run --locked --extra dev python scripts/audit_astrodice_kernel.py \
  --ephe /absolute/path/to/raw-jpl --jpl-file linux_m13000p17000.441 \
  --protocol tests/fixtures/astrodice-kernel-protocol.json \
  --reference tests/fixtures/astrodice-kernel-horizons.json \
  --output /tmp/astrodice-jpl-kernel.json
```

原始JPL路径通过可用样本也不能补成Horizons未返回的十项原始时刻，或认证全部视位置、时标、交点、宫位和原典解释。这里仍保留Swiss对给定TT的星历参数处理，未独立认证TT/TDB转换或实际观测精度。

可选路径、严格错误边界、双平台实际数据比较及未通过项见原始JPL路径审计（本地数据：`validation/astrodice-jpl-kernel-audit.json`）。

### 瞬时运动与速度核验

附加天象保留 `chart.chart.objects[].motion` 中未经舍入的 `longitude_speed`（度/日）、`direction`、`reference_frame`、`basis` 和 `source_model`，以及修正前的 `native_longitude_speed`、实际应用的 `light_time_correction` 与 `rotation_correction`。最终日速是原生值与返回修正项之和。热带与Lahiri分别使用对应原生参考系，不能只平移经度却复用热带速度。原生接口缺少请求的 `FLG_SPEED` 或返回非有限日速时，以 `coordinate_motion_unavailable` 原因拒绝本次天象，不把缺值、NaN或未计算的零值解释成顺行。

`direct/retrograde` 根据最终未经舍入日速的正负判定；恰为零时返回 `zero_instantaneous_rate`，它没有定位一次留站事件。南交点是北交点黄经加180°，继承其同参考系日速；福点缺少上升点导数，返回 `not_computed`，不只用月亮减太阳日速拼出完整福点运动。近似轨道路径未提供导数的星体及其依赖点也保留未知。`chart.params.motionPolicy` 列出实际未计算点和范围，快照读取同一日速字段。依据是[Swiss程序手册§3.3.3、§3.4、§12.2](https://www.astro.com/swisseph/swephprg.htm)的速度选项、六分量返回值及原生恒星黄道接口。

`chart.params.chart_profile.longitude_motion` 记录源码推导的方法、版本、适用状态及物理来源。针对已检查的原生2.10.03／绑定2.10.3.2，月球JPL与Swiss物理后端增加所采用光行时定义的链式导数，并经光行差位置变换的雅可比传播；热带日速另补最终黄道转动中的章动黄赤交角导数项，Lahiri的NONUT路径不加此项。这些项来自位置算法的求导，不按参考残差拟合。未验证版本或不支持的月球后端保留原生值并明确标记；参与修正的来源、坐标标志或位置重现不一致时拒绝计算。位置及骰面规则保持原算法。

独立参考仍有超线项及模板不确定性，新增留出样本的局部改善不等于整体通过。原始量46失败、早先模板失败和缺失端点均保留。推导与后续证据见视运动调查（本地数据：`validation/astrodice-apparent-motion-investigation.md`）及月球运动审计（本地数据：`validation/astrodice-lunar-motion-audit.json`）。

复核新的月球诊断时，物理数据仍按前述环境变量选择；显式JPL示例：

```bash
SE_EPHE_PATH=/absolute/path/to/raw-jpl FATEBRIDGE_JPL_FILE=linux_m13000p17000.441 \
uv run --locked --extra dev python -m scripts.audit_astrodice_lunar_motion \
  --protocol tests/fixtures/astrodice-lunar-chain-protocol.json \
  --reference tests/fixtures/astrodice-lunar-chain-reference.json \
  --output /tmp/astrodice-lunar-motion.json
```

该诊断保留数值失败退出码；应用回归通过不能将它改记为通过。

这些运动属于独立天象背景，不是骰面星的运动条件，不能替三枚骰面添加逆行、留站或应期。`astronomical_motion` 是已发布字段视图；按其字段列表传 `fields`，视图名本身不是参数。保留 `motionPolicy` 和 `validation`，不能只读一个方向标签。

底层几何速度另按冻结速度协议（本地数据：`../tests/fixtures/astrodice-velocity-protocol.json`）核验。它复用已有公开Horizons参考中的速度分量；阈值在查看速度残差前固定为每坐标分量 `1e-10 AU/日`、视线单位向量导数差 `0.002角秒/日`，不改动原位置容差，也不把方向导数称为黄经速度。这是限定工程诊断，不是全历元Swiss精度保证，也不是新盲测。协议明确保留原始缺失时刻和补充样本的区别。

```bash
uv run --locked --extra dev python scripts/audit_astrodice_kernel.py \
  --ephe /path/to/jpl-directory --jpl-file linux_m13000p17000.441 \
  --protocol tests/fixtures/astrodice-kernel-protocol.json \
  --reference tests/fixtures/astrodice-kernel-horizons.json \
  --velocity-protocol tests/fixtures/astrodice-velocity-protocol.json \
  --output /tmp/astrodice-jpl-velocity.json
```

[Horizons手册](https://ssd.jpl.nasa.gov/horizons/manual.html)说明内部动力学采用TDB。这里比较的是已有TT标签历元返回的几何状态；没有独立认证TT速率变换、日期黄道视黄经日速、真实留站时刻或现实预测能力。已知失败、缺项、负对照和双平台结果见运动审计（本地数据：`validation/astrodice-velocity-audit.json`）。

### 坐标含义、太阳高度与独立视运动参考

原生返回值还须符合请求的坐标约定：核心热带位置、赤道位置和Lahiri位置分别核对球坐标、度、日期参考系、地心及视位置修正标志；Lahiri原生计算自动加入 `NONUT`，不能将它误判为异常。有限的赤经仍不是黄经，有限的弧度也不是度。标志不符返回 `coordinate_contract_changed`；缺失、非有限或越域的坐标／太阳高度返回 `coordinate_values_unavailable`，不继续解释为有效盘面。

太阳几何中心高度为零仍计昼，这一约定只作用于有效的有限高度。旧实现中 `NaN>=0` 为假，会错误选夜，连带改变按昼夜反转的福点；现已拒绝这种来源错误。原生地平接口返回畸形结果也不会靠近似回退掩盖；正常的接口不可用回退仍按已有近似模型标注。

新的冻结视运动协议（本地数据：`../tests/fixtures/astrodice-apparent-motion-protocol.json`）单独比较Horizons量45/46的视ICRF方向与角速度，含光行时、引力偏折及光行差；目标参考点和TT历元均显式记录。新增30个日期由固定SHA-256种子选定，不根据残差挑选。ERFA的IAU2006/2000A偏置—岁差—章动矩阵及真黄赤交角只用于这30个现代日期的显示黄道核验，并保留坐标轴导数，不能只旋转位置后遗漏速度中的参考系运动。

本次取得570组可用视方向／速率和300组现代显示黄道参考，但量46与位置求导出现不一致。为查明差异，另在发现问题后冻结位置求导协议（本地数据：`../tests/fixtures/astrodice-apparent-derivative-protocol.json`），获取每个可用时刻前后的六个位置，用固定一小时和半小时五点模板分别求导。它是追加诊断，不能冒充原始盲测、替换原协议或抹掉原始速率比较失败。两步模板之间也有高于诊断线的差异，不能把全部派生速率当作无误差真值。

目前这些证据没有证明视黄经日速全面达标；原生速度与位置导数的残余差异仍须调查。原始响应、来源量之间的差异、模板收敛、具体计算修复和双平台结果见视运动与坐标契约审计（本地数据：`validation/astrodice-apparent-motion-audit.json`），光行时链式导数原型和后续运行修正分别见调查推导（本地数据：`validation/astrodice-apparent-motion-investigation.md`）及月球运动审计（本地数据：`validation/astrodice-lunar-motion-audit.json`）。几何速度通过、位置通过、应用测试通过分别保留，不合并成“满分”。

```bash
uv run --locked --extra dev python scripts/audit_astrodice_apparent.py \
  --ephe /path/to/jpl-directory --jpl-file linux_m13000p17000.441 \
  --protocol tests/fixtures/astrodice-apparent-motion-protocol.json \
  --reference tests/fixtures/astrodice-apparent-horizons.json \
  --derivative-protocol tests/fixtures/astrodice-apparent-derivative-protocol.json \
  --derivative-reference tests/fixtures/astrodice-apparent-position-derivative.json \
  --output /tmp/astrodice-apparent-motion.json
```

天体原生计算失败时，仅该天体回退到轨道近似，其他成功的原生位置继续保留；旧实现会因一颗失败而丢弃整盘原生结果。出现回退时，`chart.params.chart_profile.planetary_models` 逐颗保留模型，`orbital_fallback.approximate_planets` 列出近似天体，核心摘要和快照同时说明。混合盘标为 `mixed_precision_runtime_model` / `swisseph_api_with_approximate_orbits`；恒星黄道下，成功天体继续用原生Lahiri接口，回退天体采用已声明的黄道偏移近似，`sidereal_planetary_methods` 逐颗区分两者。

轨道近似保留原有UT日数、忽略TT差异的约定，不能当成原生星历或远期精度认证。[Schlyter方法说明](https://stjarnhimlen.se/comp/ppcomp.html)明确列出这类简化及远期局限；FateBridge的具体近似实现以返回的 `source_path` 为准，不将教程的误差说明认证为本实现保证。回退信息的 `candidate_files` 是候选行星／月球分段清单，不是文件完整性或已加载模型检查。

成功天体的模型标签取自原生返回标志。平交点不是实体行星；[Swiss文档§2.2.1](https://www.astro.com/swisseph/swisseph.htm)说明平交点使用另行构建的月球理论模型，JPL星历本身不提供平交点。因此平北交点返回 `swieph` 标志，并不证明它读取了某份 `.se1` 文件，也不能用这个标志认证节点的独立天文准确度。

远期日期可按[官方分段表](https://www.astro.com/swisseph/swisseph.htm)补齐数据：`uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 9999` 选择 `sepl_96.se1` 和 `semo_96.se1`。600年分段交界会同时选择相邻年份可能需要的文件。自定义下载目录须设置 `SE_EPHE_PATH`，服务重启后再核对实际模型。仅解读三枚骰面仍不需要星历下载。具体反例和验证记录见逐体回退与分段审计（本地数据：`validation/astrodice-ephemeris-fallback-audit.json`）。

缺少原生星历时，共享近似角度公式仍按东侧黄道／地平交点选取ASC。旧公式在部分高纬度时刻会选中西侧对点，偏差可达180°，并传递到宫位和福点；现已增加东半球分支判定。核验分别检查[USNO地平坐标方程](https://aa.usno.navy.mil/faq/alt_az)的地平线约束、东侧方向，以及相同ARMC和黄赤交角下的原生接口。近似恒星时和黄赤交角仍有误差，分支修正不能认证所有历元的天文准确度。[Swiss Ephemeris通用文档§6.4](https://www.astro.com/swisseph/swisseph.htm)说明了其东半球约定。

精确地理极点（纬度±90°）保留星体、宫位和角度的约定计算，`chart.params.chart_profile.angle_definition` 同时返回 `geographic_pole_meridian_convention`：输入经度在此定义参考子午线；固定天球方向不发生由地球自转造成的每日升落。ASC、天顶、宫位和依赖ASC的福点应连同此约定读取，不能当作物理升起时刻。核心摘要与本工具快照使用同一说明；邻近极点的普通纬度不被改标为精确极点。几何推导、具体反例、测试范围与残余问题见高纬度角度审计（本地数据：`validation/astrodice-polar-angle-audit.json`）。

另一种退化发生在黄道与地平面接近重合时。按[USNO地平坐标方程](https://aa.usno.navy.mil/faq/alt_az)推导，零黄纬方向的高度满足 `sin(alt)=A cos(λ)+B sin(λ)`，其中 `A=cos(φ) cos(ARMC)`、`B=cos(φ) sin(ARMC) cos(ε)+sin(φ) sin(ε)`。`R=hypot(A,B)` 是两平面锐夹角的正弦，`R=0` 时整条黄道均在地平面上，不存在唯一几何ASC。这是从坐标方程得出的几何结论，不是某部占星原典的引文。

`angle_definition` 在 `R≤sqrt(binary64 ε)` 时返回 `ecliptic_horizon_ill_conditioned`，在 `R≤64 binary64 ε` 时改为 `ecliptic_horizon_numerically_unresolved`、`geometric_ascendant_resolved=false`。前者仍有数值交线但对扰动高度敏感；后者不能用这些浮点数分辨唯一ASC，返回角度仅为后端数值约定。这里的阈值用于数值条件检查，不是观测、经纬度、时间或天文模型误差界，也不能证明物理平面精确重合。返回实际ARMC、黄赤交角、系数、R和所用阈值；核心摘要与占星骰快照保留同一解释。仅依赖ASC的宫头、落宫及福点受此限定，MC和不依赖ASC的星体位置继续保留。

检查使用实际角度模型：原生路径读取 `houses_ex` 的赤道ARMC及与其内部UT1／Delta-T约定一致的真黄赤交角；恒星黄道也不把Lahiri黄经或黄道偏移当作ARMC。离线路径使用自身的近似恒星时和平均黄赤交角。原有数值没有被替换成一个假定的正确上升点。具体反例及验证范围见地平交线退化审计（本地数据：`validation/astrodice-horizon-degeneracy-audit.json`）。

`chart.params.chart_profile.earth_rotation` 记录实际采用的地球自转模型。`fatebridge_standard_rotation_v2` 在J2000前后各200儒略年范围内采用[IERS 2010表5.2e](https://iers-conventions.obspm.fr/content/chapter5/additional_info/tab5.2e.txt)的恒星时表达式，并使用Swiss的章动及平均黄赤交角；范围外保留Swiss长期模型的变化形状，在对应边界加一个常数相位差，使两模型的角度连续衔接。范围和常数由FateBridge确定；[Swiss文档6.1](https://www.astro.com/swisseph/swisseph.htm)提供的是常数偏移衔接的方法说明，不是对本系统边界或精度的认证。

旧采纳边界的硬切换会产生约0.36、0.68角秒的跳变，现由相位对齐消除。公开原生几何接口接收的是经恒星时差旋转后的计算坐标系经度，用户输入的实际经纬度继续保留；不改动UTC、UT1或TT输入。`longterm_phase_alignment` 在使用长期相位对齐时记录方法、边界和未认证范围，未应用时为 `null`。常数对齐只保证所检验的角度衔接，不保证导数连续，也不证明远期绝对位置准确。

独立ERFA参考冻结39个时刻、195个地点组合，生成进程不导入FateBridge或Swiss；它核验给定TT／UT1下的恒星时与空间两轴，不独立认证输入时标、实测地球定向或所有宫制。原生Lahiri合同继续以 `1e-9` 度容差检查几何及黄道转换，同时让时钟接受独立参考核验；不再把2050年后采用不同默认时钟的原生 `houses_ex` 当作同模型对照。故意关闭标准自转或恢复边界硬切换的负对照必须失败。具体数值及残余问题见恒星时模型与衔接审计（本地数据：`validation/astrodice-rotation-model-audit.json`）。

`symbolic_details.triplicity_condition` 将《四书》Robbins I.18 的总体分派与条件角色分别保留。`assigned_rulers` 列出该章分派给三角的主星，`in_assigned_group` 表示骰面星在这个总体分派中的关系；火象为太阳、木星，土象为月亮、金星，风象为土星、水星，水象为火星、月亮、金星。这不是对所有昼夜条件逐一授予尊贵，也不是 Dorotheus 的三主星轮替。

`rulers_by_sect.day/night` 继续列首要主星及原文明确列出的条件共管主星，`matches_by_sect` 继续只比较这些所列角色。`match_definition` 保留这一口径，`roles_by_sect` 用 `primary/co_ruler/assigned_not_selected/not_assigned/outside_seven_planet_scope` 说明具体关系。比如木星白羊座属于火象三角总体分派，但昼条件所列首要主星为太阳：`in_assigned_group=true`、`matches_by_sect.day=false`、`roles_by_sect.day=assigned_not_selected`；夜条件则为木星首要治理。原解释“不属于该组”在v6中修正为对总体分派和具体条件角色的分别说明。

水象保留火星与昼金星／夜月亮共管。`sect=null` 保留未知；三王星、交点的总体匹配及条件匹配均为 `null`，不是 `false`。`interpretation.triplicity_meaning` 和 `conditional_triplicity` 规则链同步呈现总体分派与昼夜条件，附加天象不会替骰面选择昼夜。`sign_condition.unassessed` 中的 `applied_triplicity_sect` 仍表示尚未选定适用条件。原典转录及反例见三角分派参考表（本地数据：`../tests/fixtures/astrodice-triangle-assignment-robbins-1940.json`）和v6原典角色审计（本地数据：`validation/astrodice-triplicity-role-audit.json`）。

`symbolic_details.planet_sect_condition` 在v7补入同译本I.7的星体昼夜分派。`natural_sect` 是原典对星体的分派：太阳、木星、土星为 `day`；月亮、金星、火星为 `night`。土星和火星的分派按原文的调和原则说明，不能按“冷就属夜、干热就属昼”倒推。它也不是I.18的三分性治理角色，例如木星是昼曜，不改变其在火象三角的夜条件首要治理角色。

水星的 `natural_sect=null`；`assignments_by_solar_phase` 同时保留 `morning_star=day`、`evening_star=night`，表示尚缺晨昏条件，不把“兼具两种条件”输出成一个已选定的 `neutral` 派别。三王星、交点超出七曜范围，分派和条件表均为 `null`。所有骰面均保留 `solar_phase/applied_chart_sect/matches_chart_sect=null`；骰面宫号不决定太阳高度，独立天象背景也不为符号骰面补上观测位置。新增解释、规则链和快照均引用同一字段及I.7来源，见原典标注（本地数据：`../tests/fixtures/astrodice-planet-sect-robbins-1940.json`）。

三枚骰面没有精确度数、两颗星的实际相对位置或实际盘的昼夜条件，因此不计算界、面、度数尊贵、出入相、逆行、燃烧、是否合派／逆派、接纳或精确应期。星体的原典昼夜分派与这些未计算项分别保留。没有列出四种星座关系不等于“游离”或“毫无尊贵”。

假设整宫轮以骰面星座位于骰面宫为约定，向前后排满十二星座。`symbolic_house_ring` 与 `houses_ruled_by_rolled_planet` 仅展示这种约定下的议题连接；轮上的宫首经度不是实际宫头，第一宫不是计算出的上升点。没有出生盘输入时，不做出生盘比较。

每项结果保留 `rulesets` 的作者、版本、来源 URL／仓库相对路径、来源类型和范围，以及 `rule_trace` 的输入、命中规则和结果。现代关键词和现实建议不冒充原典引文；附加天象也不能为骰面解释补充不存在的事实。

## 验证范围与现实预测

星历文件获取采用[固定官方提交](https://github.com/aloistr/swisseph/tree/c69c14adb7a0f94829586ffd92cd422aacb21e86/ephe)的完整SHA-256指纹，覆盖清单中的153份 `.se1` 文件。下载和缓存复用都检查完整内容；旧缓存替换前保留原文件，`--verify-only` 可离线核验。它修复了两字节 `SW` 内容被接受、以及月球文件错存为行星文件仍被复用的问题。清单只包含指纹，实际数据仍单独获取。

本地已补齐公元1–9999年所需的34个行星／月球分段。文件区间、每年年首年尾及600年换段邻域的原生返回模型另行核查；这证明指定数据与运行时的可用性，不能据此声称所有历元位置、未来UTC/UT1或宫位都无误差。实际JPL数据版本取自原生文件头，平交点仍按其单独理论模型说明。来源、反例和限定验证见文件完整性与年代覆盖审计（本地数据：`validation/astrodice-ephemeris-integrity-audit.json`）。

| 方面 | 可检验内容 | 当前证据能支持什么 |
| --- | --- | --- |
| 算对历法/天文 | 独立 NASA/JPL 经度、闰日跨日、等价时区、秒/微秒、夏令时边界、实际星历模型 | 骰面层无历法运算；附加天象按具体参考时刻和容差核验。不能将“不适用”算成100分 |
| 符合指定原典 | 指定译本中的七曜×十二星座，84 项星座关系与昼夜三分性关系逐一对照，并对照七曜喜乐宫、I.7昼夜分派及水星晨昏条件 | 自行根据原文标注的参考表与实现一致；这是限定子集、第一方转录核验，未获独立学者的整部原典认证 |
| 解释忠于结果 | 穷举1,728组合，检查骰面、宫号、关键词、尊贵标签及规则链；检查问题/天象选项不改变符号证据 | 保证本工具的确定性解释模板与所返字段相符；不能据此认证外部大模型的任意自由文本 |
| 能够预测现实 | 冻结规则、预注册、独立前瞻样本、基线、盲评、覆盖率与不确定性 | 当前没有本星骰系统的已核验现实预测样本，状态为 `not_validated`，无可报告的准确率 |

七曜参考表在 astrodice-sign-reference.json（本地数据：`../tests/fixtures/astrodice-sign-reference.json`），不是从运行时规则生成。原有视黄经测试复用带原始响应和 SHA-256 的 NASA/JPL 样本，覆盖七个实体及三个时刻；2角秒阈值含输出经度四位小数的量化误差。新增几何向量核验采用上文单独的协议、容差和失败记录。这两组证据都不涵盖全部历元、节点、宫头或黄道偏移，不能外推成全时域保证。

运行：

```bash
uv run --locked --extra dev python -m pytest -q \
  tests/test_astrodice.py tests/test_astrodice_depth.py \
  tests/test_astrodice_geometry.py tests/test_astrodice_context.py \
  tests/test_astrodice_explanation.py tests/test_astrodice_sidereal.py \
  tests/test_astrodice_house_positions.py tests/test_astrodice_triplicity_roles.py \
  tests/test_astrodice_planet_sect.py \
  tests/test_astrodice_transports.py
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
```

测试是本地算法与协议验证；真实大模型行为、远程部署和现实预测研究需分别验收。v2历史证据见首轮审计（本地数据：`validation/astrodice-audit.json`），v3变更及验收见深度审计（本地数据：`validation/astrodice-depth-audit.json`），v4见计算与原典审计（本地数据：`validation/astrodice-v4-audit.json`）；坐标与福点方法后续核验见天象背景审计（本地数据：`validation/astrodice-context-audit.json`）；v5解释忠实度见解释审计（本地数据：`validation/astrodice-explanation-audit.json`）。现实研究的可执行流程见前瞻验证方案（本地数据：`validation/astrodice-prediction-protocol.md`）。

v7的I.7昼夜分派、原有1,728组合不变性、负对照、同run分页核对、坐标示例修正及双平台验收见原典分派与接口审计（本地数据：`validation/astrodice-planet-sect-audit.json`）。

内行星与太阳另有完整视位置导数余项 `position_derivative_correction`。它与原生日速、光行时及旋转项共同组成最终 `longitude_speed`；`complete_position_derivatives` 保留实际方法版本、尝试步长、所选差分或多项式路径、失败的初始尝试和来源。外部验收误差线仍为 0.002 角秒/日，内部收敛线为 0.0002 角秒/日。来源模型改变、坐标合同不符或所有有界尝试均不收敛时拒绝计算，不能用未知速度填成顺行。月球继续使用单独方法。

本轮两批内行星留出按版本分开封存，共 180 项；跨年代月球新增宽模板仍保留两个不完整端点，Swiss 后端也仍有超线及调用顺序反例。数值与历史失败见后续审计（本地数据：`validation/astrodice-position-motion-audit.json`）和调查记录（本地数据：`validation/astrodice-apparent-motion-investigation.md#2026-10-22内行星留出验收与跨年代模板复核`）。不能据此宣称全历元正确或预测有效。

跨压缩星历文件边界的月球计算现通过共同光路窗口处理，方法和各参考系状态见 `chart.params.chart_profile.longitude_motion.lunar_source_windows`。黄道、赤道及 ICRF 核验入口均在观测与迟发时刻的共同文件覆盖范围内重算。首次原生状态保留为 `initial_native_state`，实际采用的状态为 `coherent_native_state`；最终日速中的原生项采用后一状态。新旧失败、重新冻结的 48 项边界留出和仍未通过的压缩数据日速见调查记录（本地数据：`validation/astrodice-apparent-motion-investigation.md#后续修复共同光路窗口与全参考系入口`）。

端点参考另有两项冻结的单侧研究，每项保留两个旧端点和 8 个新历元。两项均有 4 个参考步长检查未通过，尚不能认证端点日速；数据完整不代表参考精度合格。原对称模板的缺失记录、候选超线值与固定误差线均未改写。源状态精度和历元舍入的进一步诊断见端点补证（本地数据：`validation/astrodice-apparent-motion-investigation.md#剩余源数据误差与端点补证2026-10-23`）。

新增的 双段 TDB 参考（本地数据：`validation/astrodice-split-time-reference.md`）含 16 个新跨年代历元及 4 个控制历元，独立读取和标量复算均通过所声明模型的质量检查。它没有转换或认证 TT 日期，也没有回填旧端点。原始 JPL 结果现通过 `physical_ephemeris_source.time_scale_policy` 披露原生 TT／TDB 近似；文件头提供正确的 TDB 范围字段，历史 TT 范围名称仅作注明含义的兼容别名。压缩数据仍有日速超线。

当前 v6 的跨年代 TT 验收（本地数据：`validation/astrodice-v6-wide-tt.md`）新增 166 个目标历元的独立参考研究。公元 1 年跨界探针使用明确 BC 标签，并按返回 JD 匹配，补齐了该端点的对称模板；9 项月球限定比较均在原定线内。156 项内行星／太阳比较中，155 项满足固定线，一项近太阳水星参考模板未合格；远未来端点也仍缺资料。后续局部尺度诊断单独保留，没有改判首次失败或把旧样本重计为新留出。

同轮还穷举核对了公元 1—9999 年的全部公历年月日组合：有效午夜日期精确一致，无效日期状态保留。两项初始 UTC 年界溢出已有后续修复与冻结验收（本地数据：`validation/astrodice-utc-boundary.md`），原始失败仍保留；全时间域及物理天文准确度尚未完成验收。

多尺度模板与新近太阳留出（本地数据：`validation/astrodice-reference-refinement.md`）进一步固定五档步长和三个阶数，只按参考自身质量选尺度。6 组新几何条件含 12 个新目标历元，两后端均有 11 项满足原定线；另两项已知控制作为回归保留。2500 年水星参考仍不收敛，整批未通过；已知 3000 年控制的新方法结果没有覆盖旧失败。

局部打印区间参考（本地数据：`validation/astrodice-local-interval-reference.md`）另冻结 6 个新条件及 2 个已知控制，使用可精确重放的区间证书并计入参考余量。双平台、双后端均有 4 项满足本轮条件、3 项数值超线、1 项参考不完整。新增反例指向近太阳引力偏折约定的差异，仍需修正和新的独立验收；原失败、缺失探针及固定误差线均保留。

太阳修正与分层验收（本地数据：`validation/astrodice-solar-layers.md`）修复了日速参考不合格时跳过中心位置的问题，并将核心已有的太阳盘前后景及原生视位置约定呈现在占星骰快照。又冻结 6 个跨年代条件，保留两个太阳盘后水星的位置、日速超线，以及两项远未来参考缺测。JPL 数据后端仍由 Swiss 修正引擎计算；模型差异没有被改判为通过。数值公式、固定误差线和全部历史失败保持不变。

参考请求首历元保护（本地数据：`validation/astrodice-tlist-first-epoch.md`）显式保留一个更早的整数 JD 辅助行，在不扩大批次预算、不改变主 TT 或误差线的条件下，补齐 7 个已见条件的 2023 个主探针。6 项局部日速参考达到声明质量线，1 项仍未决，太阳盘后水星仍数值超线。另冻结的四个源时间身份条件全部满足历元匹配线，其四项宽差分日速模板的失败也继续保留；不计作新增候选数值精度留出。

5 秒参考与局部模型反证（本地数据：`validation/astrodice-grid5-reference.md`）保留全部原观测及固定门槛，5 份精确证书证明部分金星观测与所选局部模型、打印区间不相容。原四项跨年代条件在当前冻结源码的 Swiss 路径下仍满足限定比较，旧太阳盘后水星仍超线；旧完整候选与平台日志缺失的证据边界也已列明。另四项新冻结条件因 Horizons 服务错误未取得任何参考，保持未决。版本绑定、日速明细及三端检查通过，没有把测试通过或参考不可用记为天文精度、全面原典或预测效度通过。

DE441 原始记录与时刻表示诊断（本地数据：`validation/astrodice-de441-records.md`）提取 7 个固定年代的原始连续系数，以两个独立有理数算法核对 420 个组件，并完成原生 JPL 几何比较。原金星反证对绝对 JD 舍入的几何代理敏感，仍需确认实际服务的时标与视位置路径；原失败和打印区间未改。诊断节选只覆盖各 96 日，不代表完整 DE441 安装；这项名义 TDB 几何研究没有替换原 TT／Horizons 验收。

连续视位置参考与内行星日速验收（本地数据：`validation/astrodice-apparent-source.md`）从原始 DE441 记录独立求完整视位置导数；3 个已见控制和 28 个预定首次源模型条件均满足原位置／日速线，另由标量基函数算法重放。结点两侧 A／B 两批均在打开前固定，未调整生产公式。新增验收器完整入口回归已修复，错误版本与失败日志保留，31 条重跑与首次结果完全一致。这里仍按名义 TDB 相同数值参数和共享显示旋转比较；旧 Horizons 水星超线、金星模板未决及四项精确 TT 留出未决保持原判，不能称为全时域或预测有效性通过。

完整视位置的时标误差包围（本地数据：`validation/astrodice-clock-budget.md`）将时差幅值与时标变化率分开处理，冻结 28 个新诊断条件，并用向外舍入区间和独立 100 位参考交叉核对。两项太阳盘后水星在声明的源模型与分析时标假设内仍与旧参考显著分离，不能只调毫秒偏移来消除差异。长年代时标模型物理外推仍未合格，新增候选精度通过数为 0；旧失败、金星反证及精确 TT 留出未决保持原判。

插值节点邻近历元的修复与留出验收（本地数据：`validation/astrodice-knot-neighbour.md`）修复近太阳水星的 8 个日速计算拒绝项：辅助高精度约化使用稳定叉积判断自身单元，并在来源身份匹配时支持 JPL 文件后端。A 组已见 32 项修复回归及 B 组预定 32 个邻近数值历元均满足原位置／日速线，旧 24 个成功项数值未变。64 项旧有限差分参考仍不合格，另一个独立区间导数参考与其并存；本轮未替换旧 TT／Horizons 判定。实际 REST、MCP、CLI 交付保持 v2 来源与失败尝试证据，现实预测仍未验证。

等价 TT 输入与交叉验收（本地数据：`validation/astrodice-dual-encoding-tt.md`）在参考服务恢复后补采原四项跨年代条件，发现 JD 与 MJD 输入各有不同的标签拒绝，保留两条完整链并增加独立有理数 MJD 校验。查询前冻结的交叉规则要求所有合格参考区间相容、候选同时过线，原四项后续比较及另外四项首次留出均满足原线。两条单链各自仍退出 2，旧服务错误、全部拒绝节点及旧太阳盘后水星超线保持原判；新结果仅覆盖所列条件及声明的参考模型，生产公式和公开接口未在该轮更改。

太阳盘内外模型与冻结留出（本地数据：`validation/astrodice-solar-limb-model.md`）按原始 DE441 几何预先选择 A／B 各 16 个新时刻，量 1／12／45 及 JD／MJD 双路径支持近太阳偏折约定差异的定位：两组默认模型各有 8 个盘内位置超线，全局关闭偏折则各有 8 个盘外位置失败。预先声明的分段假设仅作诊断，没有改入生产算法或覆盖原判；本研究不验收日速、精确盘缘或物理 TT／TDB 转换。固定误差线、原完整数值门槛退出 1 及全部旧失败保持不变。

金星输入表示与串行补采（本地数据：`validation/astrodice-venus-epoch.md`）保留原8103年中心的五份精确反证与完整参考未通过状态。相同13个支持点的MJD／日历输入虽然改变反证组合，但完整网格各有8个标签超预算，不能据此通过。采集入口现共享跨进程串行控制和503退避，原两项预定留出在复用166个成功批次、补取29个失败批次后，JD参考及两后端位置／日速均满足原线；MJD／日历各26个标签拒绝仍未决。生产数值公式、固定误差线和原完整数值门槛退出1保持不变，首次并发采集及全部故障记录另存。

时刻包围与错误缓存修复（本地数据：`validation/astrodice-epoch-envelope.md`）对三项已见金星条件保留完整网格、窗口、阶数及原误差线，明确检验尚未认证的时刻／斜率假设。66组必要外包围虽取得精确证书，参考半径仍超质量线，三项继续未决；独立原始单位算法复核264个最优值，不把代数可行性认证为真实时刻或预测准确度。HTTP200服务错误现保留但不复用为成功缓存，130份历史错误的离线恢复资格已核对，未发出新请求。原数值门槛退出1和全部旧判保持不变。
