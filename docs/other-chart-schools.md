# 其他流派星盘：德国中点、子午宫表与 13 等分扇区

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

阅读导航：[德国盘](#德国中点盘) · [钟时](#显式民用平太阳与真太阳钟时) · [太阳弧](#指定目标时刻的真太阳弧与双盘) · [生时误差](#声明生时误差后的重新排盘) · [13 等分](#13-等分扇区的定义与边界) · [示例](#调用与复现) · [未决范围](#整部原典仍缺哪些核对)

本页说明德国中点盘与自定义 13 等分扇区。西方古典、果老星宗和[印度占星](jyotish.md)另有各自规则与验收；不能用本页的几何测试为这些体系整体认证。源码能力也不表示已发布到 PyPI。

Gauquelin是36个顺时针分区，十二宫公开接口拒绝其名称，不静默改成其他宫制。离线CFEPP审计保留原公布1066条及补充54条；六种具名定义分开比较，固定有折射升落法可复现粗分区，但主算法仍有13条原表差异，圆心／圆边不能由此表唯一裁定。它尚非公开排盘能力或现实预测验收。显式非法宫制不会选择默认值，Alcabitus等有效名称按当前映射处理。

## 德国中点盘

`astro_germany_chart`（REST `/api/astro/germany`）和 `astro_chart` 的 `chart_variant=germany` 返回同一 `midpoint_analysis`。当前版本为 `hamburg_midpoint_geometry_v3`，作者为 FateBridge。

当前中点层提供：

| 内容 | 本版本的规则 |
| --- | --- |
| 22 因素 | 十个物理天体、月亮平交点、上升、天顶、白羊点，以及八个汉堡派数学假设点 |
| 253 中点轴 | 无序组合允许同一因素与自身配对；每条轴回显相隔 180° 的两端，避免正反中点重复计数 |
| 两因素式 | `A=B`，两个不同因素的硬相位；保留实际夹角和最近硬相位，不把折叠重合都写成合相 |
| 三因素式 | `C=A/B`，三个因素必须各不相同 |
| 四因素式 | `A/B=C/D`，四个因素必须各不相同，排除可约化恒等式对统计的膨胀 |
| 折叠度盘 | 90° 与 45° 分别计算，45°盘还合并八分相位；不能将两盘的重复式相加当成独立证据 |
| 容许度 | 默认且当前固定为 1°，包含边界；这是本实现选择，并非原书唯一标准 |
| 精度 | 原生未舍入坐标参与比较；有理数运算保留输入浮点数位于边界哪一侧的信息 |
| 回溯 | 每个因素记录种类和模型；每条轴与对称式记录规则 ID、偏差、是否涉及假设点，附版本、作者和来源 |

八个假设点为 Cupido、Hades、Zeus、Kronos、Apollon、Admetos、Vulkanus、Poseidon。Swiss Ephemeris 使用的数学轨道元素不等于物理观测；这些点没有因位置表一致而变成 NASA/JPL 发现的天体。`contains_hypothetical` 可用于辨认每条式子涉及的因素。

### 外部轨道文件与实际来源

`profile.hypothetical_element_source` 区分 `library_builtin` 与 `external_file`。后一种回显第一个可读 `seorbel.txt` 的来源说明和搜索路径序号，不公开服务器目录；因素另有实际 `element_name`。文件第 1–8 项必须仍对应八个汉堡因素，接受 Vulcanus／Vulkanus 拼写，不把换序或其他自定义天体冒充 Cupido／Zeus。物理星体实际星历模型与这一轨道来源分开，`moshier` 返回标志本身无法判断假设点是否读取了外部文件。

路径优先级遵循 [Swiss 编程手册 2.1](https://www.astro.com/swisseph/swephprg.htm)：非空 `SE_EPHE_PATH` 优先于函数显式路径，再使用项目目录或已加载库的默认搜索路径。后者在当前运行时含工作目录；没有 `.se1` 文件不等于没有外部轨道输入。此前代码可能回报“已应用显式目录”，而 C 库实际读取环境目录，现已修正为实际选择。超过当前 Swiss 2.10 接口 242 个编码字节的路径会报错，防止底层静默回到默认目录。

一次因素计算前后都会读取轨道文件指纹；生时样点之间及与名义盘的来源不一致时拒绝交付混合结果。回执库存也纳入辅助文本文件并在每次回执重新散列；大型 `.se1` 的内容散列由文件大小、mtime、ctime、inode 和设备号失效缓存，不再只按目录缓存。它们是离散检查，不是连续文件不可变证明；服务运行期间仍应保持数据不变，更新后重启复核。自定义轨道文件与回执一致也不建立现实预测有效性。

原生物理因素另有 `profile.physical_ephemeris_source`，依据 [Swiss 手册 2.6](https://www.astro.com/swisseph/swephprg.htm)在实际 `calc()` 后读取文件上下文：保留文件名、覆盖 TT 区间、DE 版本和与打包清单是否匹配，不输出服务器目录。`by_factor` 将实际返回模型与观察到的文件上下文关联；节点、假设点和地球自转另行说明。Moshier 即使留下旧文件槽，也不归属那些 Swiss 文件；缺少查询接口或无法读取文件时明确标记来源未完全识别。文件上下文并非完整依赖图，首尾散列也不是原子读取证明。

`ephemeris_model_scope=physical_bodies` 表示盘级 `ephemeris_model`、中点层及生时样点的 `ephemeris_models` 只汇总物理天体。平交点采用 `swisseph_analytical_mean_node`，基础盘另列 `nonphysical_factor_models`；中点因素保留 `native_return_flags`。依据 [Swiss 2.10.03 的平交点入口](https://github.com/aloistr/swisseph/blob/v2.10.03/sweph.c#L859)和[解析实现](https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L1493)，这些标志可回显请求的星历类别，不证明读取了该类别的物理矢量文件。空目录真实复现：三种请求标志的平交点坐标完全相同，而返回模型位各异。过去由此把全 Moshier 物理天体误报为 `mixed`，现已修正；若只有交点近似，计算质量仍为混合精度，但物理天体模型不因此混合。实际物理后端混用仍为 `mixed`，物理天体全部采用简化轨道则为 `none`。解析理论及其拟合系数也不是独立的动力学认证。

运行者显式设置 `FATEBRIDGE_JPL_FILE` 时，德国盘的原生因素循环与恒星层的地球观测者、原生恒星传播均经过受管理的严格 JPL 调用；缺文件、原生回退或越出覆盖范围会报来源错误。恒星目录与运行者星历目录在共享锁内合并，调用后恢复。默认 Swiss／Moshier 模式保留，节点与假设点不因返回 JPL 位变为物理观测。回归使用保留原始 DE441 系数的 96 日、40,720 字节子集，不能由此声称完整 DE441 年代覆盖已验收。

生时敏感性新增 `physical_ephemeris_sources`，样点的 `physical_source_index` 指向去重的来源记录。逐因素模型、同名文件内容或 DE 版本改变时，不把这组差异解释为纯生时影响。例如只安装 1800 段时，2400 年文件真实覆盖边界的两侧可分别返回 Swiss 与 Moshier；程序要求补齐整段输入所需数据，不缩短用户区间或改为统一的低精度回退。同一 DE 版本的正常相邻文件切换仍允许。集成检查需另行取得范围内文件：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 1800 2500
uv run --locked --extra dev pytest -q tests/western/test_other_chart_physical_sources.py
```

三端用 `error_code=ephemeris_source_inconsistent`、HTTP 503 和 `retryable=false` 表达这类运行数据问题；`issues` 的 `runtime.ephemeris_data` 给出 `model_changed`、`edition_changed` 或文件变更等具名原因。它不是出生资料有误，也不再被“错误文字含 ephemeris”这一通用规则抹成缺依赖。补齐范围数据并重新加载运行时后再执行同一请求；不通过缩短区间、删除样点或改容许度获得通过。

`swieph` 标签本身不代表固定 DE431：本次实际文件头为 DE441。NASA/Horizons 与 Swiss 可以共享同一套底层 DE441 数据，因此外部响应交叉检查不能算作两套独立天体动力学证据，更不能作为现实事件验证。实际 DE 版本与读取范围随文件记录，不由库版本或宣传文案推断。

计算与基础盘共用 `ephemeris_time`：TT 计算因素，估算 UT1 计算角点，公历为 Python/ISO 的前推格里历。闰秒表到期后的假设由 `future_leap_seconds_assumed_unchanged` 回显。恒星显示使用原生 Lahiri 标志；白羊点仍代表**回归春分点**，也要转换到所选显示黄道，不能在恒星盘里直接写作恒星 0°。切换显示黄道后，所有因素一致旋转，中点对称关系应保持一致。

原始方法依据为 Ludwig Rudolph 的[《17 Gesetze für Planetenbilder》](https://www.witte-verlag.com/hamburger-hefte-menu/datenbank/823.html)，载《Hamburger Hefte》1979/2、第 74 期、第 1 页，出版社数据库条目 823。`rule_trace` 将三因素、四因素、折叠关系及白羊点分别定位到第 3、7、13–16 条。`axis_offset_degrees=0` 表示直接中点轴，90 表示四分偏移，45／135 表示八分偏移，避免把间接式写成精确直接中点。测试中的四组整数示例是根据条文另行手算构造，**不是原书刊载的命例**；这部分核对不涵盖文章的现实作用断言，也不等于整部《Rules for Planetary Pictures》的验收。

v3 补齐该文第 13／16 条的两因素层。此前原生层虽有 22 因素，却只输出三／四因素式；顶层七曜相位与太阳弧跨层联系不能替代 22 因素的本命两因素硬相位。`dials.90.two_factor_contacts` 覆盖 0／90／180°，`dials.45.two_factor_contacts` 另包含 45／135°。每盘按无序因素对列一次，禁止自身配对；两盘重复的因素对在 `unique_two_factor_pair_count` 去重。每盘数量另见 `contact_counts.*.two_factor`，不增加独立预测证据。

每条两因素式回显 `aspect_degrees`（最接近的 0／45／90／135／180° 硬相位）、`separation_degrees`（原始圆上实际较小夹角）、`signed_orb/orb`（所选度盘偏差），以及 `factor_offset_degrees`（A−B 方向上最近的度盘倍数，0–359°）。例如 A=0°、B=90° 时，方向偏移为 270°、实际夹角与相位类型均为 90°；它不是合相。这里不用代表中点轴的模 180° 字段，避免将 180° 对冲误标为 0°。边界仍按未舍入输入、包含 1°；新增手算／三角交叉检查不是原作者数值命例，也没有新增关键词或事件概率。

相关技术依据另见 [Swiss Ephemeris 编程手册](https://www.astro.com/swisseph/swephprg.htm)的 3.2.3、9.2、12 节；假设因素说明见[技术文档 2.7.1](https://www.astro.com/swisseph/swisseph.pdf)。[Witte 出版社的实际工作器具](https://witte-verlag.com/produkte/arbeitsmittel.html)也列出 90°、45°度盘及中点尺。

顶层 `midpoints/midpoint_aspects` 提供七曜360°视图，原生22因素使用 `midpoint_analysis`。两层都在舍入前求中点和相位；精确相对的两点明确给出两个等价端点。公开小数是显示表示，不用于后续边界判断。缺少Swiss时的整宫近似采用未舍入轨道值，并回显 `approximate_raw_orbits`。

顶层 `planets` 是 `base_chart.planets` 的同值入口，使通用 `astro_chart` 的既有必需字段合同在德国盘模式下也成立；其中不混入八个假设点。两个视图的因素范围、度盘与容许度分别回显。缺少 Swiss 时原生 22 因素层明确为 `unavailable`。

### Witte 1923 本命子午宫表

`midpoint_analysis.meridian_houses` 新增 `witte1923_natal_meridian_house_geometry_v1`，采用 [Witte 原刊页 34](https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf)描述的赤经等分构造与 Swiss `X`：从上天顶的赤经起每 30°取一个宫头，返回其黄经与赤经。黄经宽度一般不等；第一宫宫头为**赤道上升点**，不能替换实际 ASC。基础盘沿用所选宫制，当前默认 Placidus，与此具名子层分别读取。

公开 `evidence_views.meridian_houses` 给出按需字段卡。`profile` 保留 UT1、原生角度模型采用的 TT、共享 TT、真黄赤交角和实际 Lahiri 视偏移；原生角度 TT 依照 `houses_ex` 的 `UT1+deltat_ex`，两种 TT 的差值不能直接当作出生钟时误差。确认的生时误差逐样点重算十二宫头，`birth_time_sensitivity.cusp_spans` 为样点范围；原始输入与宫头位于同 run 的 `time_sensitivity.samples`。未知误差保持 `not_assessed`，不视为零。

宫头层的原刊表在两个预声明黄赤交角模型下都保留残差，不调整本命钟时、天顶或参数去拟合。

`meridian_houses.factor_placement` 由 Witte1924第56、58页的赤经构造结合Swiss X定义重建天体落宫：复用本次原生黄经、黄纬，恒星显示先用天体同历元实际视偏移还原回归黄经，再按已披露的原生制宫交角投影。原文未单列完整黄纬操作步骤，不声称逐字复现。完整方向与仅用黄经的反事实结果分别给出；后者不能替代实际落宫。德国盘分别报告10个物理天体、1个解析平均月交点及8个数学假设点，未把3个角点参考算成天体。

用户确认生时误差时，每个样点重新投影，并给出各因素的实际宫位集合；未知误差、数值极点退化及宫界附近的比较保持相应限制，不转为概率。原刊第59页的另一张宫表，在两种预定交角模型下仍有第11、12、2宫未能于声明的印刷舍入区间内协调，未用调参勘误。本层不提供未核读的宫内关键词、完整推运钥匙或现实事件判断。

### 原刊数值命例与钟时精度

Alfred Witte [1919 年《Sensitive Punkte》原刊扫描](https://astrax.de/pdf/02_Sensitive_Punkte%201919%20AstrRundschau%2023-29.pdf)的印刷页 26（PDF 第 5 页）有一组出生日期、钟时和 12 项经度。PDF SHA-256 为 `18fcf0aa0ce530fc3c594ed9ff42c92b536948b716c1b1e2ca7f69432dd345a2`；数值从原页图像人工读取，见独立转录（本地数据：`../tests/fixtures/uranian-witte1919-natal.json`），没有用引擎结果生成预期位置。此时原文没有后来的八个汉堡假设点，不能把今天的 22 因素都冒充该表内容。

原刊该段只写 1879 年 5 月 14 日夜间 11 点、Hamburg，没有在这里明确钟时基准及分钟／秒的记录精度。Karsten F. Kröncke [2009 年复核文第 1 页](https://astrax.de/pdf/KEN2009_07_MethPlanetenb7.pdf)另给出 `23:00 OZ = 22:20:50 WZ/GMT` 和 10°E／53°33′N。采用这一后出数值时，必须注明秒数与坐标来自后出作者，不能称作 Witte 原始记录。若**条件性地**把 23:00 当作 10°E 的地方平太阳时，直接换算应为 GMT 22:20:00，与该文差 50 秒；这不证明原文采用平太阳时，也没有认证后出的换算。原刊期号在索引与后文中也有差别，保留扫描与印刷页定位。

历史例比较把该后出 GMT 数值作为明确声明的研究输入。`birth_timezone=UTC` 是传输标识；共享时间层对 1960 年前按 UT1 处理，不声称 1879 年已经存在原子 UTC。原刊表与当前计算仍有未裁定差异，例如月亮、海王星等位置不能都落入同一印刷单位。检查分别列出原刊数值、当前值和有符号差异，分别列半个／一个印刷单位比较；原刊的舍入方式未知，这两列不构成整部原典验收阈值。不修正出生时刻、替换旧表或放宽阈值来消除这些差异，也不采用文章的事件、疾病或因果断语。1879年的同一组预定TT历元另有月球、木星与海王星原始NASA/JPL响应，见历史星历参考（本地 `tests/fixtures/uranian-historical-horizons.json`）。这只核对固定 TT 的天体经度，仍未裁定原刊钟时和印刷差异。

专用德国盘、13 等分盘及 `astro_chart` 对应变体接受 `birth_second=0..59`；`chart`／`hellen` 变体仍拒绝非零秒数，七政四余按自身现行合同保留秒及小数秒。秒数进入基础盘、TT／UT1、原生因素、生时样点和可选太阳弧／日天顶。德国盘的实际钟时见 `base_chart.person_info`，13 等分盘见 `person_info`。在上述明确输入下，省略 50 秒会让 MC 移动约 12.8′，并改变原生三／四因素命中集合。输入秒数不等于生时已经精确；省略秒数仅表示用所给分钟起点作为计算表示，误差未声明仍为 `not_assessed`。

### 显式民用、平太阳与真太阳钟时

德国盘与 13 等分盘的 `birth_clock_basis` 声明**输入记录本身的钟时基准**。依据 [Swiss 编程手册 9.2／9.4](https://www.astro.com/swisseph/swephprg.htm)及其[均时差实现](https://github.com/aloistr/swisseph/blob/master/sweph.c)，当前可选：

| 值 | 输入含义与换算 |
| --- | --- |
| `civil` | 默认民用钟时，使用 `birth_timezone` 或既有地点时区推断 |
| `local_mean_solar` | 已知地方平太阳时 LMT；按东经为正，UT1 = LMT − 经度／15 小时 |
| `local_apparent_solar` | 已知地方真太阳时 LAT；先按地心视太阳时角反解均时差，再由 UT1 经共享时标转换到计算 UTC／TT |

太阳钟时模式应省略 `birth_timezone`，并保持 `use_true_solar_time=false`；组合冲突会报错。`use_true_solar_time`选择民用钟时的太阳时钟面重置；输入 LMT／LAT 使用上述明确基准。通用 `astro_chart` 的 `germany/chart13` 变体使用本节入口；`india_chart` 的同名钟时输入另按印度盘当前合同处理。`OZ` 等未辨明的原刊记号需要核实，不能按哪种盘更像原书或更符合事件选择基准。

同一地名的 IANA 历史偏移不一定代表记录地点的地方太阳钟时。例如当前固定规则库对 1879 年的 `Europe/Berlin` 给出的 23:00 对应 UTC 标签 22:06:32；声明 10°E 的 LMT 23:00 则对应历史 UT1 标签 22:20:00。它们回答不同的输入问题。原刊的实际基准仍未认证，新入口只提供明确条件下的计算。

换算规则 `fatebridge.local_solar_birth_clock.v1` 作者为 FateBridge。`person_info.clock_conversion`（德国盘位于 `base_chart` 下）保留原始无时区标签、基准、实际经度、UT1 与计算 UTC、来源和数值往返误差。LAT 另回显地心视太阳赤经、GAST、均时差、实际太阳星历模型和 IERS 恒星时模型。`person_info.birth_timezone=UTC` 与 `birth_datetime` 显示换算后的计算时刻；原钟时从 `clock_conversion.input_wall_datetime` 读取。13 等分文本导出也保留原钟时。微秒表示与小数 JD 的数值分辨率不构成生时记录或历史地球自转的准确度认证；`clock_accuracy_certified/measured_eop_applied` 均为 false。

1960年前的 `utc_to_jd/jdet_to_utc` 使用[Swiss日期代码](https://github.com/aloistr/swisseph/blob/v2.10.03/swedate.c)声明的历史UT1转换。传输中的 `+00` 标签不声称原子UTC已经存在。历史来源、现代UTC和未来闰秒假设分别回显，不能把不同时间尺度之间的标签差当作同尺度天文误差。

声明太阳钟时 ±N 分钟时，先分别换算该钟时区间的两端，再在相应物理 UTC 区间采样，保留名义时刻且间隔不超过 30 秒。结果增加 `input_clock_basis/recorded_interval_start_clock/recorded_interval_end_clock/requested_clock_radius_seconds`，`represented_radius_seconds` 表示映射后物理区间的最大半径。原钟时分钟与 UTC 秒数不强行视作完全等长；未知误差仍为 `not_assessed`。不支持的 UTC 闰秒标签会明确拒绝，避免滑到相邻时刻。

条件性 LMT 算术示例（未认证原刊的实际基准）：

```bash
uv run --locked --extra dev fatebridge astro_germany_chart \
  --birth-year 1879 --birth-month 5 --birth-day 14 --birth-hour 23 \
  --birth-longitude 10 --birth-latitude 53.55 \
  --birth-clock-basis local_mean_solar \
  --fields base_chart.person_info midpoint_analysis.profile \
  --strict-fields --no-include-snapshot-text
```

### 敏感点与限定原文解释

v2 增加 Udo Rudolph [《ABC für Planetenbilder》出版社摘页](https://witte-verlag.com/component/djcatalog2/?fid=12&format=raw&task=download)的印刷页 14（PDF 第 6 页）依据。原文给出 `MA+JU-ZE=MC` 与 `MC/ZE=MA/JU` 的等价示例。这是原作者的符号示例，**不是原载数值命盘**；测试用的角度另行构造，实际三端验收资料也是明确标记的虚构输入。

每条四因素式的 `sensitive_point` 给出 `A+B-C=D`、实际敏感点与占据因素经度。中点式按周期 P 比较，转成和差式必须用 **2P 周期、两倍角偏差和两倍容许度**。`direct_orb` 在完整 360°圆上另算；`folded_only` 不能被解释成敏感点的直接占据。

只有确实满足该原文符号结构、且在声明容许度内直接占据时，才给出该例关于个人目标与行动成效的限定象征解释。其他结构不会自动套用此例。相同依据在两种度盘重复出现时使用相同 `claim_id`；根级 `interpretations` 去重，防止重复命中被当成更多独立证据。它是来源明确的传统解释，不是成功概率或未来事件断言。原书完整关键词与预测方法尚未验收。

尚未提供完整汉堡宫制、完整原书解释关键词库、完整 Witte 推运体系或现实事件预测；指定目标时刻的真太阳弧及具名 1924 日推运天顶子集见下文。外部 `seorbel.txt` 可以覆盖 Swiss 的假设轨道默认值；位置验收必须连同实际环境核对。共享时间层对 1960 使用 SOFA 历史偏移口径，对 1961–1971 使用 IERS 历史 UTC 速率／偏移表，1960 年前沿用 Swiss UT1／Delta-T 口径；地点误差及古代钟时仍需另审。

### 指定目标时刻的真太阳弧与双盘

德国盘及通用 `astro_chart` 的 `germany` 变体接受带时区偏移的 `analysis_datetime`，省略时仍只计算本命。新层为 `midpoint_analysis.solar_arc_analysis`，规则版本 `hamburg_true_solar_arc_v1`，作者 FateBridge。

真太阳弧取次限太阳与本命太阳的实际回归黄经之差，并将同一弧度加到各本命因素。方法见 Klaus Bonert [2007 年作者摘文](https://www.astro.com/astrologie/in_sonnenbogen_g.htm)。本实现显式选择 **365.25 个 UTC 日历日对应 1 个 TT 星历日** 的儒略年符号钥匙，支持出生后 0–150 钥匙年；这不是寿命范围，也不宣称是 Witte 唯一的年长约定。UTC 日历减法不计闰秒，实际年长、两次太阳位置、TT 儒略日、浮点时间分辨率及实际星历模型均回显。太阳弧不固定为每年 1°，并同时回显与该简化值的差。

确认的生时区间跨越当前钥匙年支持范围时，名义目标有效则继续交付本命、名义太阳弧和日推运；相应 `birth_time_sensitivity` 标为 `partial`，保留全部样点及未计算原因。`computed_sample_count/unavailable_sample_count` 分列数量，`source_pattern.sampled_status=underdetermined`不能当成全部不成立；偏差及坐标跨度仅覆盖已计算样点。

`directed_factors` 是本命坐标的象征性旋转，不是目标日观测到的行星或角点。恒星显示仍采用同一个回归真太阳弧，并固定本命 Lahiri 显示偏移；推运太阳不能冒充目标日实际太阳或次限时刻重新计算的 Lahiri 太阳。

双盘返回 90°／45°度盘的两因素、两种方向的点—中点以及推运中点—本命中点联系。每个因素均有 `natal/solar_arc` 层标识，跨层同名因素保留；零弧恒等式单独标记，根级计数也报告其数量。列表不截取最前几项，计数不作为证据权重或事件概率。同样坐标依据保持同一个 `claim_id`，包括零弧时本命与推运的同一条原文解释。

年长钥匙另有 `profile.key_source_comparison` 和公开 `evidence_views.progression_key`。Witte1923年推运常数原刊的八项时角运算中，两项所印结果分别与本行操作数相差−60秒、+3600秒；独立原页算术检查保留失败并退出1。该历史例及正午起算的日期标签未裁定，不参与当前盘计算，也不修正用户钟时或黄经。当前太阳弧保持365.25日钥匙和所声明的数值公式。

### Witte 1925 完整太阳弧表与未定格

`original_table_1925` 整理原刊第87–88页的38行、342个年数格及38个末列值，保留每格原始读数。20年列在3月2日的度数标记未能清楚确定，影响其后至10月18日共24格；这些规范化值保持 `null`，其余318格可以按明确度数递承。涉及正权重未定格的插值返回 `underdetermined`，不补零或拿现代星历选值。末行是次年1月6日，不能并回年初；末列的61′是弧分量，不按六十进制分钟字段拒绝。

原载例的56′＋54°17′＋34′＝55°47′算术成立。精确有理数双向插值与不逐步舍入的延伸得到55°47.925′，只作另一舍入政策的诊断，不能据此宣称原刊算错或改写其结果。原文没有给出生钟时／时区，不补造UTC作现代星历验收。

公开 `evidence_views.witte1925_table` 选择来源、覆盖、算例及 `computed_for_current_chart=false`；完整原表读取同 run 的完整结果或显式表路径。当前太阳弧仍采用原有真实太阳位移及365.25日钥匙，太阳弧元数据版本为3。数值表坐标插值不等于完整历法到太阳弧算法，闰日、亚日、跨年末列及全程舍入仍未裁定。复核入口见[1925原表重演](../scripts/western/replay_witte1925_table.py)。

### Witte 1924 黄道和差式日推运天顶

指定目标时刻后还返回 `midpoint_analysis.solar_arc_analysis.daily_meridian`。它采用 [Witte 1924 原期刊扫描件](https://www.astrax.de/pdf/34_35_Die%20Differenzierung%20der%20Radixsonne%20und%20die%20des%20unteren%20Geburtsme.pdf)印刷页 15 的明确黄道算式，具名为 `witte1924_ecliptic_day_meridian_v1`：

```text
日推运 IC = 本命 IC + 真太阳弧 − 本命回归太阳 + 目标时刻实际回归太阳
日推运 MC = 日推运 IC + 180°                    （均模 360°）
```

目标太阳单独以目标 TT 计算，并回显时刻、时间尺度、星历模型与闰秒假设；本命黄道显示框架保持不动。日推运上下天顶是此来源的**象征坐标**，既不是目标时刻的物理天顶，也不是仅将本命 MC 加太阳弧。使用两颗回归太阳的差，不能在恒星显示下混入不同年代的岁差偏移。生时误差的每个样点均重算太阳弧、本命 MC 与本命太阳，再给出上下天顶及相对名义值的圆周位移；只证明已采样范围，不代表连续稳定、全部命中式稳定或概率。

原页给出下天顶输入巨蟹 7°15′、太阳弧 62°23′、本命太阳水瓶 6°58′、目标太阳白羊 20°50′，结果为天蝎 23°30′。该**原作者算术例**已单独保存，原坐标是否精确、完整日期到太阳弧的时间钥匙及历史事件含义没有因此验收。本实现年长仍采用上节声明的 365.25 日钥匙。

[1923 年较早文章](https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf)印刷页36对同一例报告的上天顶是金牛26°34′；1924下天顶反推的上天顶为金牛23°30′，相差 **3°04′**。差值可由原文宫头构造解释：1923用第八宫宫头天蝎10°19′，1924算式在此例等价的等距参考为天蝎7°15′，恰差3°04′。两项原值均保留，差值不能当通用修正量；另项敏感点比较仍差4′，完整时间钥匙及整篇原典仍未验收。`daily_meridian.source_comparison`明确其历史例范围，当前坐标采用1924公式。索引写1923年11月，而原文扫描附加页眉写12月，月份差异也保留。此层不采用原文关于事件、引力或“从不失败”的主张。

Udo Rudolph 摘页第 14 页还明确提到推移 MC 占据该敏感点的情形。只在实际推运 MC 满足直接占据门槛时，返回该例的限定象征主题，并附 `factor_layers`、目标 UTC 与实际太阳弧。已声明生时范围时，每个样点分别重算太阳弧与推运 MC；输出样点弧度、直接偏差及是否成立。尚未覆盖完整交错层四因素式、实际行运、Witte 逐日 MC、完整关键词或经过验证的现实事件模型。

独立天文验收使用仓库已保存的 **8个NASA/JPL太阳位置与4个差值**，位置／弧度容差在比较前固定为2／4角秒。这些时刻原先为另一项引擎检查选定，太阳位置从NASA响应独立取得，不能把时刻选择本身也称为独立金标准。资料保留原检索日期及来源文件哈希；其中仅保存解码后JSON的响应，其原HTTP正文的字节哈希无法从重新序列化的数据复核。可复核的星历正文哈希与原编码字节分别记录，不能把缺失的原始编码声称为已取得。

Witte 出版社 [AstrologicPC 手册第 7 页](https://witte-verlag.com/pdf/source/AL319_HINWEISE.pdf)另有 22 对本命／太阳弧坐标，图注为静态 8°示例。PDF SHA-256 为 `f319a3590d2214347af1d99bdb5d2d5634133cfb3c0cbc89f16c822f97851692`。逐对读取可见印刷差为 8°00′或 8°01′；按各栏 1′精度核对后，共同弧度区间相容。原未舍入坐标未知，因此不强行把所有印刷值当成精确输入，也不把这张软件插图当成经典原载命盘、目标日期到弧度的金标准或现实预测证据。

日推运天顶另按原生MC参考资格交付：精确极点的依赖坐标为null，形式值另存；太阳和弧长继续保留。实际网格另核对UTC／TT、零样点及太阳观测角色，错配按运行时来源错误处理。可解析范围不跨未知样点连线，名义参考未知也不抹去其他已知绝对样点。

### 声明生时误差后的重新排盘

德国盘与 13 等分盘现在接受 `birth_time_uncertainty_minutes`：用户已确认的记录时刻正负误差，范围为 0–120 分钟。省略表示未知，返回 `not_assessed`；明确传 0 才评估单个已确认时刻。专用工具与通用 `astro_chart` 对应变体使用相同计算，其他未实现此功能的变体会拒绝该参数，避免静默忽略。

实现版本为 `fatebridge.specialty_birth_time_sensitivity.v1`，作者 FateBridge。在**记录时刻的 UTC 时间轴**上取不超过 30 秒间隔的样点，包含两端和名义时刻；每个样点重新计算原生因素。跨夏令时回拨时不重新猜测含混的墙钟。若用户选择现有真太阳时重置模型，则在每个记录时刻重新应用该模型；记录 UTC 与计算 UTC 分别回显。微秒是 datetime 的表示精度，不是原始生时记录的精度。

已计算的样点用 `factor_scope/factor_count` 明确范围：德国盘为 22 个汉堡因素，13 等分盘只需 14 个物理／参考因素，不读取假设轨道并标记 `hypothetical_element_source.status=not_used`。因此一个不适用于汉堡目录的自定义假设点文件不会阻塞 13 等分的物理分区；它也不会被偷偷用来生成错名因素。未声明误差时仍不生成任何样点。

德国盘的 `midpoint_analysis.time_sensitivity` 返回未舍入因素、TT／估算 UT1、相对名义时刻的坐标变化，以及当前原文符号示例在各样点的直接占据情况。名义解释继续保留，并附 `birth_time_sampled_status`。13 等分盘的顶层 `time_sensitivity` 返回每颗星在各样点的分区及观察到的跨区。

虚构反例 `2000-01-01 04:30 UTC, 0°E/0°N, ±10分钟` 中，名义时刻满足该原文符号示例，41 个样点里有 13 个不再满足；天王星在 13 分区中出现第 2／3 区变化。这些计数证明已找到范围内反例，**不是置信概率**。未出现反例也不能证明整个连续区间稳定；窄于采样间隔的变化可能遗漏。此层尚未评估全部中点命中集合、地点误差、时区规则误差或星历误差。缺少 Swiss 时明确返回 `unavailable`，不以近似轨道伪装这项重排验收。

Witte 出版社的[2024 进阶课程说明](https://witte-verlag.com/?catid=49&id=205%3Ahamburg-grundkurs-astrologie-2023&view=article)明确讨论资料质量、生时不确定性，以及太阳弧半弧／全弧／倍弧和 Witte 的逐日推运天顶。该课程支持继续核查这些技术；30 秒网格与上述状态分类是 FateBridge 的工程选择，并非原典规定。虽已取得并重放上述 1924 算式，完整时间钥匙、不同年代推运方法及独立数值命盘仍需验收，不能用已实现的通用西占推运替代。

核对原载数值命例时还必须保存生时来源版本。出版社的[Witte 传记](https://witte-verlag.com/alfred-witte.html)并列个人自述 21:12 LMT 和登记记录 22:00 LMT；正文及脚注的 GMT 换算差值不同，尚待考订。本实现没有挑选更能拟合事件的版本当成唯一真值，也未用事件倒推用户出生时间。

### 原文条件与极点参考

本命及太阳弧的原文条件现与实际MC参考资格一致：精确地理极点的形式MC不再被统计为已知成立或已知缺失；原数值及形式文案保留在`backend_convention/backend_reading_zh`，实际条件和角距为null，并交付未定样点数。太阳弧范围外与MC参考未定分别计数，保留全部已确认样点。只退化ASC的情形不限制独立MC。

## 整部原典仍缺哪些核对

不能把 1979 年条文、1996 年 ABC 摘页及不同版本的《Regelwerk für Planetenbilder》合成一部已验收的“原典”。德国国家图书馆公开的[第 5 版两页目录](https://d-nb.info/455720827/04)可以定位下列缺口，但没有提供这些章节正文。目录页码只属于该版，不证明相应算法或命例已读到。

| 第 5 版目录定位 | 当前能力与待取得的证据 |
| --- | --- |
| 第 31、57 页：度盘算例与教学命例 | 已有独立位置表、手构几何和出版社软件静态示例；仍缺这两章原载输入、逐步计算和原版坐标，不用手构角度替代 |
| 第 40 页：本命反映点 | 已另具名实现Witte1924比较换基与四点镜像；本书该章正文仍未取得，不能自动视为本章通过 |
| 第 62、65、70 页：宫位、宫内因素含义 | 已实现独立具名的 Witte 1923 本命子午宫头几何；未验收本书全部宫制及宫内含义。基础盘沿用所选宫制，当前默认 Placidus，不能冒充本书宫制 |
| 第 74 页：赤经表；第 82 页：推运 | 已实现具名的真太阳弧子集与显式 365.25 日钥匙；仍缺原章的时间钥匙、赤经使用和逐日推运天顶的完整数值验收 |
| 第 84、96、102–371 页：解释结构及分因素规则 | 现仅采用 ABC 摘页的一条有条件含义，未取得并逐条裁定本书完整关键词与组合规则 |

[出版社第 7 版说明](https://witte-verlag.com/international-books/deutsch/14-witte-lefeldt-regelwerk-fuer-planetenbilder.html)署名 Ludwig Rudolph 与 Hermann Lefeldt，ISBN `978-3-920807-52-2`；说明相较第 5 版有三百余处增补或订正，核心部分页码大体保留。实际验收应保存所选版次、页影及变更，不因页码相近就把两版含义视为完全一致。以上是来源定位和能力缺口，**不是取得全文、规则通过或预测有效的证据**。

基础盘十二宫制、原生参考角提取、X子午宫与13等分扇区分别有实际来源。当前数码1是Alcabitus／Swiss B；原生参考角的E调用不表示采用E宫头。

### Witte1924比较换基与四点镜像

德国盘另有`midpoint_analysis.comparative_geometry`：按Witte1924第138–139页重建五种锚点换基与四点镜像，使用同run实际白羊点表示热带轴，并复用全部已确认生时样点。未解析参考保留null和后端形式值；锚点自身按定义指定的位置不等于物理参考已解析。原表36行在所声明舍入假设下32行相容，三条海王星行及一条太阳框架子午线行仍不协调，全部原值保留；没有采用未裁定的地球宫表或事件解释。

## 13 等分扇区的定义与边界

`astro_chart13`（REST `/api/astro/chart13`）和 `astro_chart` 的 `chart_variant=chart13` 使用实际上升为起点，每区宽 `360/13` 度，区间沿黄道采用 `[start,end)`。它与另行选择的十二宫制独立，返回 `sector_profile`、13 个区间及各星的 `sector13`。

13分区按输入浮点值的精确有理数分类，再输出显示数值。每颗星的 `sector13_evidence` 保留未舍入黄经和上升，避免按显示小数复算到相邻分区。未声明生时误差时标记未评估，声明后链接实际重排结果；数值精度不是出生记录精度。区间边界浮点显示是近似值，严格定义始终为 `ascendant+n*360/13`。

ASC无法在本角度模型中解析时，实际13扇区返回未定，后端约定值另行保留；德国盘原生参考角、相关中点／太阳弧与生时样点也携带对应限定。

这是 FateBridge 自定义等分规则 `fatebridge_equal13_v1`，没有把它宣称为某部传统原典，也没有赋予新的性格或事件预测意义。IAU 的天文星座边界并不等宽，见 [IAU FAQ](https://iauarchive.eso.org/public/faq/)。本工具不计算 IAU 星座归属，名称和返回说明已改为“13 等分扇区”。通用西占星座说明仍以实际十二星座与宫位为依据。

## 独立验收与四项状态

参考值来自 [Witte 出版社 2026 星历的原始下载](https://a182559.uranus.1blu.de/data/public/4b5ecc.php?dl=true)，由[出版社页面](https://witte-verlag.com/)提供链接。PDF 版次标为 2026-08-14；SHA-256 为 `61e973148b74711196d5ec3b4a03e202cb3d1f1cfce8e6827bc51347f769bc57`。

从第 1、7、12 页各取月初 00 UT 的 19 因素，合计 57 项。Sun/Moon 原表到角秒，其余到角分；比较前固定容差分别为 2 角秒、1 角分。提取脚本不导入生产计算，不用 Swiss 生成预期值；字体映射、表头和首行与渲染 PDF 核对。物理天体表列 DE442/LE442，假设点另列 Shudde/Neely 元素；二者的证据性质分别保留。

| 目标 | 当前可检验范围 | 尚未完成的要求 |
| --- | --- | --- |
| 算对历法与几何 | 57 项独立位置表、TT/UT1 口径、独立倍角公式、13 分区全边界探针；实际生时重排；8 个 NASA 太阳位置／4 个真太阳弧及 22 对出版坐标的舍入区间；目标太阳与日推运天顶的分层和样点重排 | 全年代与全地点天文验收、历史钟时、连续区间界与其他误差传播；NASA 数据是既存同一批参考，不是新增独立队列 |
| 符合某部原典 | Rudolph 1979 几何条文、Udo Rudolph 1996 原载符号示例及 Witte 1924 页 15 算式定位；同一历史例三项算术回放，1923／1924 天顶差值由原刊宫头偏移解释；已实现 1923 本命子午宫头构造并保留原表两列残差，另项 4′残差仍在 | 整部原书、完整日期到坐标命盘、其余原文差异裁定和专家复核；整体仍为 `not_assessed` |
| 解释忠于计算 | 敏感点门槛、原文归因、度盘及零弧重复依据去重；真实接口核对本命／推运分层及生时条件 | 真实模型对话的盲审、跨轮资料修正与错误事实注入验收 |
| 能够预测现实 | 已计算指定时刻的象征太阳弧；现实效果尚无结果数据 | 固定事件定义、时间窗、模型及基线，事前登记独立队列，记录失败与弃答，完成盲法结果核验和外部复现；当前 `not_tested` |

当前未建立四项目标全部通过或系统整体权威的结论。现有[预测研究评估器](../src/fatebridge/validation/predictions.py)可用于登记后的二元结果，但本几何／符号推运层还没有固定可验证的事件预测模型或真实研究队列。

预测研究评估器将每条预测和结果绑定完整方案，防止同一批记录在更换事件、窗口、基线或统计政策后直接重用。这项保护不增加现实预测样本或效力认证。

方法参考包含[汉堡中点取证卡](interpretation/xingpan/hamburg-evidence.md)，明确本命／推运 MC、直接／折叠占据、同一依据去重及出生误差条件。另备 5 个虚构模型验收用例（本地数据：`../tests/fixtures/agent_behavior/other_chart_cases.json`），参数已通过当前公开工具的预检；真实独立模型执行与人工语义复核尚未完成，不能将用例已准备记为解释忠实度已验收。执行和审阅方法见[Agent 验收](agent-evaluation.md)。

## 调用与复现

使用虚构示例，参数与返回内容都来自当前工具目录：

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 1800 2500
uv run --locked --extra dev fatebridge astro_germany_chart \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --fields midpoint_analysis.profile midpoint_analysis.contact_counts midpoint_analysis.reading_guide midpoint_analysis.limitations \
  --strict-fields --no-include-snapshot-text

uv run --locked --extra dev fatebridge astro_chart13 \
  --name 演示甲 --birth-year 1990 --birth-month 4 --birth-day 6 \
  --birth-hour 9 --birth-minute 33 --birth-place 上海 \
  --fields sector_profile planets thirteen_sectors interpretation.variant_note \
  --strict-fields --no-include-snapshot-text

uv run --locked --extra dev pytest -q \
  tests/western/test_other_chart_physical_sources.py tests/western/test_other_chart_historical_reference.py \
  tests/astronomy/test_contract_regressions.py tests/integration/test_runtime_and_errors.py \
  tests/western/test_other_chart_clock_basis.py tests/western/test_other_chart_birth_seconds.py tests/western/test_contract_regressions.py \
  tests/western/test_other_chart_orbit_sources.py tests/astronomy/test_ephemeris_runtime.py \
  tests/western/test_other_chart_meridian_houses.py tests/western/test_contract_regressions.py tests/western/test_other_chart_meridian_native_clock.py \
  tests/western/test_other_chart_day_meridian.py tests/western/test_other_chart_solar_arc.py tests/western/test_other_chart_sensitivity.py \
  tests/western/test_other_chart_depth.py tests/western/test_other_chart_schools.py tests/western/test_other_chart_schools_transports.py
uv run --locked --extra dev python -m scripts.western.audit_other_chart_schools \
  --output /tmp/fatebridge-other-chart-schools-current.json
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
```

另有三颗历史天体的离线 NASA/JPL DE441 参考，历元和容许度在请求前固定。响应完整保存在 `tests/fixtures/uranian-historical-horizons.json`，含原始 HTTP JSON 字符串、SHA-256、TT 历元、地心观测点与视黄道坐标定义；它们不替换 Witte 原刊数值，也不确认原始出生钟时。此精度检查需要另行取得并核验 Swiss 星历文件：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
uv run --locked --extra dev pytest -q tests/western/test_other_chart_historical_reference.py
```

没有星历文件时的 Moshier 回退必须单独报告：海王星误差约 1.097″，超出预定的 1″ 门槛，不能改容许度或省略此案例。数值审计报告须保留重跑时的实际模型和文件哈希；文件完整性本身不是天文精度保证。固定TT检查与共享审计中的57项出版社参考分列，但同样纳入 `numerical_subset_checks_passed`：当前 Moshier 报告返回失败，已核验 Swiss 数据报告返回通过。原典整例和现实预测仍未据此验收。

指定目标时刻并保留同一虚构资料的生时误差：

```bash
uv run --locked --extra dev fatebridge astro_germany_chart \
  --name '虚构：太阳弧验收' \
  --birth-year 2000 --birth-month 1 --birth-day 1 \
  --birth-hour 4 --birth-minute 30 --birth-timezone UTC \
  --birth-longitude 0 --birth-latitude 0 --birth-time-uncertainty-minutes 5 \
  --analysis-datetime '2000-02-01T00:00:00Z' \
  --fields midpoint_analysis.solar_arc_analysis.profile midpoint_analysis.solar_arc_analysis.interpretations midpoint_analysis.solar_arc_analysis.birth_time_sensitivity \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

明确已确认 ±5 分钟时，可在上述命令增加 `--birth-time-uncertainty-minutes 5`，德国盘读取 `midpoint_analysis.time_sensitivity`，13 等分盘读取 `time_sensitivity`。首次需完整样点时不以概览字段代替全文；沿同一 run 的 `result_delivery` 读取。

复现上述虚构反例，只读取原文解释及其生时条件：

```bash
uv run --locked --extra dev fatebridge astro_germany_chart \
  --name '虚构：生时误差反例' \
  --birth-year 2000 --birth-month 1 --birth-day 1 \
  --birth-hour 4 --birth-minute 30 --birth-timezone UTC \
  --birth-longitude 0 --birth-latitude 0 --birth-time-uncertainty-minutes 10 \
  --fields midpoint_analysis.interpretations midpoint_analysis.time_sensitivity.source_pattern \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

REST 把业务参数放请求体，`fields/strict_fields/include_snapshot_text` 放查询参数。MCP 使用同名工具；摘要从公开 `evidence_views` 复制字段，完整几何首次 `fields=null`，再读取同一 run 的 `result_delivery`。数组整体选取，不把 `planets.sector13` 当作数组字段投影。`file_path` 是结果存储包络文件，`file_payload_path=payload` 指定文件内的 JSON 路径；需要核验存储完整性时，使用结果 ID 与原 run 调用校验读取接口；公开回执不提供 SHA-256。

重新获取并核对独立原表（普通测试不联网）：

```bash
curl --fail --location 'https://a182559.uranus.1blu.de/data/public/4b5ecc.php?dl=true' \
  --output /tmp/witte-ephemeris-2026.pdf
uv run --locked --extra dev python -m scripts.western.gen_uranian_witte_reference \
  --pdf /tmp/witte-ephemeris-2026.pdf --check
```

原始外部来源、提取规则或参考行发生变化都需要人工审阅，不自动接受生产结果为新预期答案。

## 共享运动与当前物理限制

十个物理天体的热带与Lahiri黄道共用完整位置求导；果老采用七政热带速度。输出保留原生速度、各修正分项、实际物理模型与未收敛原因。角度单位为度，日速单位为度／TT日；内部0.0002角秒／日收敛线不等于物理模型误差上界。

[Swiss标准Lahiri定义](https://www.astro.com/swisseph/swisseph.htm)与[接口§12.2](https://www.astro.com/swisseph/swephprg.htm)区分标准Lahiri、ICRC和1940口径。独立ERFA长期岁差投影保留1956参考点的IAU1976修正，检验的是声明的标准Lahiri坐标框架；1989原刊对应页尚未取得，不能视为完整原典命例通过。

共享参考保留2040、2060、2090年四季各一个预声明TT、十天体、两框架，共240组速度和1320个原始NASA位置。外部速度检查线为0.002角秒／日，参考差分及运动框架不确定度也分别按原0.002线判断。两个框架复用相同天体资料，不能记成240次独立天象观测。当前采样必须保留全部失败及原生速度对照，不能由旧输出替代实际运行。

Moshier模型有明确未通过事实：既有240组对照中76项超限、最大约0.47736角秒／日；另一个84组七政队列有32项超限、最大约0.761322角秒／日。这些是已暴露的参考队列，当前方法变更不能据此自动继承通过数，也不能删除旧有失败样本或改线。三颗历史天体的1角秒位置控制另有海王星约1.097角秒超限。NASA与Swiss可能共享DE441动力学，数值一致不构成独立观测或现实预测认证。

当前原始响应可由维护中的独立ERFA／NumPy生成器重新解析及归算，无须保存旧FateBridge实现或源码AST。检查保留位置、两框架速度、全部差分与步长不确定度；不访问NASA。uv首次准备独立依赖可能联网。

```bash
uv run --locked --extra dev python -m scripts.astronomy.audit_moshier_frames --output /tmp/fatebridge-motion-audit.json
env -u PYTHONPATH uv run --no-project --python 3.12 --with pyerfa==2.0.1.5 --with numpy==2.5.4 python -m scripts.astronomy.verify_moshier_frame_reference --output /tmp/fatebridge-motion-reference-check.json
```

审计退出1表示实际数值超限，退出2表示来源或参考未完备。来源完整性、原典整例、真实模型解释和现实预测分别验收。


### 本命与太阳弧的交错配对

`solar_arc_analysis.mixed_pair_geometry`，核读Witte1925第53–54页后，对四个不同因素的本命／同一太阳弧混合配对作具名代数重建。系数±0.5的关系与弧长抵消的关系分列，保留每组四个等价层次安排；同层目录与计数不混入混层目录。后者不能当作新增择时触发或独立证据。

交错组合现可复用同run的完整已确认生时网格，分别记录成立、不成立、变化和未定，也保留名义盘没有而样点中新出现的关系。弧长不可用或物理参考角未解析时保留对应未知，不把未列出或共同太阳弧抵消解释为生时稳定。原生因素与太阳弧样点须共享有效UTC标签及主TT历元；错配按运行时来源不一致报告。
