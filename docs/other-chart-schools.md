# 其他流派星盘：德国中点、子午宫表与 13 等分扇区

本页记录源码新增的两个明确范围。西方古典、果老星宗和[印度占星](jyotish.md)另有各自规则与验收；不能用本页的几何测试为这些体系整体认证。源码能力也不表示已发布到 PyPI。

另有Gauquelin 历史分区审计（本地数据：`validation/gauquelin-cfepp-calculation-audit.md`）：完整保留 CFEPP 原公布1066条和补充54条，主算法仍有13条原表差异。这是离线计算取证，尚非公开排盘或现实预测验收；结果见第二十五轮回执（本地数据：`validation/other-chart-schools-v25-verification.json`）。随后修复了把 `G` 静默改成普通宫制的问题；29个公开工具现在明确拒绝已识别的 Gauquelin 名称，见第二十六轮输入保护（本地数据：`validation/gauquelin-request-input-guard.md`）。第二十七轮进一步修复 `Alcabitus` 等有效名称被误排为 Placidus 的问题，并取消显式非法宫制的默认回退；数值反例及40个参数入口的范围见宫制选择核验（本地数据：`validation/house-system-selection-audit.md`）。第二十八轮另修正历史审计的地心／站心标注，并完整比较六种 Gauquelin 定义；固定的有折射升落法可复现全部粗分区，但圆心／圆边仍不可由该表唯一判定，见方法定义核验（本地数据：`validation/gauquelin-method-definition-audit.md`）。

## 德国盘的实际增量

`astro_germany_chart`（REST `/api/astro/germany`）和 `astro_chart` 的 `chart_variant=germany` 返回同一 `midpoint_analysis`。当前版本为 `hamburg_midpoint_geometry_v3`，作者为 FateBridge。

旧实现只有七曜的 21 个两两短弧中点及五种西占相位。新增层提供：

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

`profile.hypothetical_element_source` 区分 `library_builtin` 与 `external_file`。后一种回显第一个可读 `seorbel.txt` 的 SHA-256 和搜索路径序号，不公开服务器目录；因素另有实际 `element_name`。文件第 1–8 项必须仍对应八个汉堡因素，接受 Vulcanus／Vulkanus 拼写，不把换序或其他自定义天体冒充 Cupido／Zeus。物理星体实际星历模型与这一轨道来源分开，`moshier` 返回标志本身无法判断假设点是否读取了外部文件。

路径优先级遵循 [Swiss 编程手册 2.1](https://www.astro.com/swisseph/swephprg.htm)：非空 `SE_EPHE_PATH` 优先于函数显式路径，再使用项目目录或已加载库的默认搜索路径。后者在当前运行时含工作目录；没有 `.se1` 文件不等于没有外部轨道输入。此前代码可能回报“已应用显式目录”，而 C 库实际读取环境目录，现已修正为实际选择。超过当前 Swiss 2.10 接口 242 个编码字节的路径会报错，防止底层静默回到默认目录。

一次因素计算前后都会读取轨道文件指纹；生时样点之间及与名义盘的来源不一致时拒绝交付混合结果。回执库存也纳入辅助文本文件并在每次回执重新散列；大型 `.se1` 的内容散列由文件大小、mtime、ctime、inode 和设备号失效缓存，不再只按目录缓存。它们是离散检查，不是连续文件不可变证明；服务运行期间仍应保持数据不变，更新后重启复核。自定义轨道文件与回执一致也不建立现实预测有效性。

原生物理因素另有 `profile.physical_ephemeris_source`，依据 [Swiss 手册 2.6](https://www.astro.com/swisseph/swephprg.htm)在实际 `calc()` 后读取文件上下文：保留文件名、覆盖 TT 区间、DE 版本、SHA-256 和与打包清单是否匹配，不输出服务器目录。`by_factor` 将实际返回模型与观察到的文件上下文关联；节点、假设点和地球自转另行说明。Moshier 即使留下旧文件槽，也不归属那些 Swiss 文件；缺少查询接口或无法读取文件时明确标记来源未完全识别。文件上下文并非完整依赖图，首尾散列也不是原子读取证明。

`ephemeris_model_scope=physical_bodies` 表示盘级 `ephemeris_model`、中点层及生时样点的 `ephemeris_models` 只汇总物理天体。平交点采用 `swisseph_analytical_mean_node`，基础盘另列 `nonphysical_factor_models`；中点因素保留 `native_return_flags`。依据 [Swiss 2.10.03 的平交点入口](https://github.com/aloistr/swisseph/blob/v2.10.03/sweph.c#L859)和[解析实现](https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L1493)，这些标志可回显请求的星历类别，不证明读取了该类别的物理矢量文件。空目录真实复现：三种请求标志的平交点坐标完全相同，而返回模型位各异。过去由此把全 Moshier 物理天体误报为 `mixed`，现已修正；若只有交点近似，计算质量仍为混合精度，但物理天体模型不因此混合。实际物理后端混用仍为 `mixed`，物理天体全部采用简化轨道则为 `none`。解析理论及其拟合系数也不是独立的动力学认证。

运行者显式设置 `FATEBRIDGE_JPL_FILE` 时，德国盘的原生因素循环与恒星层的地球观测者、原生恒星传播均经过受管理的严格 JPL 调用；缺文件、原生回退或越出覆盖范围会报来源错误。恒星目录与运行者星历目录在共享锁内合并，调用后恢复。默认 Swiss／Moshier 模式保留，节点与假设点不因返回 JPL 位变为物理观测。回归使用保留原始 DE441 系数的 96 日、40,720 字节子集，不能由此声称完整 DE441 年代覆盖已验收。

生时敏感性新增 `physical_ephemeris_sources`，样点的 `physical_source_index` 指向去重的来源记录。逐因素模型、同名文件内容或 DE 版本改变时，不把这组差异解释为纯生时影响。例如只安装 1800 段时，2400 年文件真实覆盖边界的两侧可分别返回 Swiss 与 Moshier；程序要求补齐整段输入所需数据，不缩短用户区间或改为统一的低精度回退。同一 DE 版本的正常相邻文件切换仍允许。集成检查需另行取得范围内文件：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe --years 1800 2500
uv run --locked --extra dev pytest -q tests/test_other_chart_physical_sources.py
```

三端用 `error_code=ephemeris_source_inconsistent`、HTTP 503 和 `retryable=false` 表达这类运行数据问题；`issues` 的 `runtime.ephemeris_data` 给出 `model_changed`、`edition_changed` 或文件变更等具名原因。它不是出生资料有误，也不再被“错误文字含 ephemeris”这一通用规则抹成缺依赖。补齐范围数据并重新加载运行时后再执行同一请求；不通过缩短区间、删除样点或改容许度获得通过。

`swieph` 标签本身不代表固定 DE431：本次实际文件头为 DE441。NASA/Horizons 与 Swiss 可以共享同一套底层 DE441 数据，因此外部响应交叉检查不能算作两套独立天体动力学证据，更不能作为现实事件验证。实际 DE 版本与读取范围随文件记录，不由库版本或宣传文案推断。

计算与基础盘共用 `ephemeris_time`：TT 计算因素，估算 UT1 计算角点，公历为 Python/ISO 的前推格里历。冻结闰秒表到期后的假设由 `future_leap_seconds_assumed_unchanged` 回显。v1 的原生中点层单独调用 Swiss UTC 转换，远期输入可能与基础盘分歧；v2 已统一路径。恒星显示使用原生 Lahiri 标志；白羊点仍代表**回归春分点**，也要转换到所选显示黄道，不能在恒星盘里直接写作恒星 0°。切换显示黄道后，所有因素一致旋转，中点对称关系应保持一致。

原始方法依据为 Ludwig Rudolph 的[《17 Gesetze für Planetenbilder》](https://www.witte-verlag.com/hamburger-hefte-menu/datenbank/823.html)，载《Hamburger Hefte》1979/2、第 74 期、第 1 页，出版社数据库条目 823。`rule_trace` 将三因素、四因素、折叠关系及白羊点分别定位到第 3、7、13–16 条。`axis_offset_degrees=0` 表示直接中点轴，90 表示四分偏移，45／135 表示八分偏移，避免把间接式写成精确直接中点。测试中的四组整数示例是根据条文另行手算构造，**不是原书刊载的命例**；这部分核对不涵盖文章的现实作用断言，也不等于整部《Rules for Planetary Pictures》的验收。

v3 补齐该文第 13／16 条的两因素层。此前原生层虽有 22 因素，却只输出三／四因素式；顶层七曜相位与太阳弧跨层联系不能替代 22 因素的本命两因素硬相位。`dials.90.two_factor_contacts` 覆盖 0／90／180°，`dials.45.two_factor_contacts` 另包含 45／135°。每盘按无序因素对列一次，禁止自身配对；两盘重复的因素对在 `unique_two_factor_pair_count` 去重。每盘数量另见 `contact_counts.*.two_factor`，不增加独立预测证据。

每条两因素式回显 `aspect_degrees`（最接近的 0／45／90／135／180° 硬相位）、`separation_degrees`（原始圆上实际较小夹角）、`signed_orb/orb`（所选度盘偏差），以及 `factor_offset_degrees`（A−B 方向上最近的度盘倍数，0–359°）。例如 A=0°、B=90° 时，方向偏移为 270°、实际夹角与相位类型均为 90°；它不是合相。这里不用代表中点轴的模 180° 字段，避免将 180° 对冲误标为 0°。边界仍按未舍入输入、包含 1°；新增手算／三角交叉检查不是原作者数值命例，也没有新增关键词或事件概率。

相关技术依据另见 [Swiss Ephemeris 编程手册](https://www.astro.com/swisseph/swephprg.htm)的 3.2.3、9.2、12 节；假设因素说明见[技术文档 2.7.1](https://www.astro.com/swisseph/swisseph.pdf)。[Witte 出版社的实际工作器具](https://witte-verlag.com/produkte/arbeitsmittel.html)也列出 90°、45°度盘及中点尺。

顶层 `midpoints/midpoint_aspects` 继续提供七曜 360° 视图，原生 22 因素使用 `midpoint_analysis`。v2 也将七曜视图改为舍入前求中点和相位，避免 `180.00001°` 先舍入为 `180°` 后把短弧中点从 `270.000005°` 翻到 `90°`；精确相对的两点则明确给出两个等价端点。数值因此可能比旧输出更精细，不能依赖旧的四位小数表示进行二次推导。缺少 Swiss 的整宫回退仍使用未舍入的近似轨道值，并回显 `approximate_raw_orbits`。

顶层 `planets` 是 `base_chart.planets` 的同值入口，使通用 `astro_chart` 的既有必需字段合同在德国盘模式下也成立；其中不混入八个假设点。两个视图的因素范围、度盘与容许度分别回显。缺少 Swiss 时原生 22 因素层明确为 `unavailable`。

### Witte 1923 本命子午宫表

`midpoint_analysis.meridian_houses` 新增 `witte1923_natal_meridian_house_geometry_v1`，采用 [Witte 原刊页 34](https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf)描述的赤经等分构造与 Swiss `X`：从上天顶的赤经起每 30°取一个宫头，返回其黄经与赤经。黄经宽度一般不等；第一宫宫头为**赤道上升点**，不能替换实际 ASC。基础盘沿用所选宫制，当前默认 Placidus，与此具名子层分别读取。

公开 `evidence_views.meridian_houses` 给出按需字段卡。`profile` 保留 UT1、原生角度模型采用的 TT、共享 TT、真黄赤交角和实际 Lahiri 视偏移；原生角度 TT 依照 `houses_ex` 的 `UT1+deltat_ex`，两种 TT 的差值不能直接当作出生钟时误差。确认的生时误差逐样点重算十二宫头，`birth_time_sensitivity.cusp_spans` 为样点范围；原始输入与宫头位于同 run 的 `time_sensitivity.samples`。未知误差保持 `not_assessed`，不视为零。

宫头层的原刊表在两个预声明黄赤交角模型下都保留残差，不调整本命钟时、天顶或参数去拟合。详见定义、原表对照与验证范围（本地数据：`validation/witte-meridian-house-geometry.md`）。

`meridian_houses.factor_placement` 由 Witte1924第56、58页的赤经构造结合Swiss X定义重建天体落宫：复用本次原生黄经、黄纬，恒星显示先用天体同历元实际视偏移还原回归黄经，再按已披露的原生制宫交角投影。原文未单列完整黄纬操作步骤，不声称逐字复现。完整方向与仅用黄经的反事实结果分别给出；后者不能替代实际落宫。德国盘分别报告10个物理天体、1个解析平均月交点及8个数学假设点，未把3个角点参考算成天体。

用户确认生时误差时，每个样点重新投影，并给出各因素的实际宫位集合；未知误差、数值极点退化及宫界附近的比较保持相应限制，不转为概率。原刊第59页的另一张宫表，在两种预定交角模型下仍有第11、12、2宫未能于声明的印刷舍入区间内协调，未用调参勘误。本层不提供未核读的宫内关键词、完整推运钥匙或现实事件判断。范围与复现见赤经落宫复核（本地数据：`validation/witte-meridian-factor-placement.md`）。

第二十一轮的最终冻结快照在 macOS／Linux 各通过 75 项针对性检查，并经 Linux 断网安装包实调。此前广泛回归的旧七政四余秒数拒绝断言及其对照失败另列保留；已按现行合同改为验证秒数实际进入 UTC 和太阳坐标，没有改动七政四余生产计算。历元核查中的错误参考状态假设也已撤回，没有计为修复。阶段、重叠用例及源码范围见验证回执（本地数据：`validation/other-chart-schools-v21-verification.json`）；另备一项八条判据的解释用例及真实 MCP 参照，模型和人工语义验收仍未执行。

### 原刊数值命例与钟时精度

Alfred Witte [1919 年《Sensitive Punkte》原刊扫描](https://astrax.de/pdf/02_Sensitive_Punkte%201919%20AstrRundschau%2023-29.pdf)的印刷页 26（PDF 第 5 页）有一组出生日期、钟时和 12 项经度。PDF SHA-256 为 `18fcf0aa0ce530fc3c594ed9ff42c92b536948b716c1b1e2ca7f69432dd345a2`；数值从原页图像人工读取，见独立转录（本地数据：`../tests/fixtures/uranian-witte1919-natal.json`），没有用引擎结果生成预期位置。此时原文没有后来的八个汉堡假设点，不能把今天的 22 因素都冒充该表内容。

原刊该段只写 1879 年 5 月 14 日夜间 11 点、Hamburg，没有在这里明确钟时基准及分钟／秒的记录精度。Karsten F. Kröncke [2009 年复核文第 1 页](https://astrax.de/pdf/KEN2009_07_MethPlanetenb7.pdf)另给出 `23:00 OZ = 22:20:50 WZ/GMT` 和 10°E／53°33′N。采用这一后出数值时，必须注明秒数与坐标来自后出作者，不能称作 Witte 原始记录。若**条件性地**把 23:00 当作 10°E 的地方平太阳时，直接换算应为 GMT 22:20:00，与该文差 50 秒；这不证明原文采用平太阳时，也没有认证后出的换算。原刊期号在索引与后文中也有差别，保留扫描与印刷页定位。

本次比较把该后出 GMT 数值作为明确声明的研究输入。`birth_timezone=UTC` 是传输标识；共享时间层对 1960 年前按 UT1 处理，不声称 1879 年已经存在原子 UTC。原刊表与当前计算仍有未裁定差异，例如月亮、海王星等位置不能都落入同一印刷单位。报告完整保留原刊数值、当前值和有符号差异，分别列半个／一个印刷单位比较；原刊的舍入方式未知，这两列不构成整部原典验收阈值。不修正出生时刻、替换旧表或放宽阈值来消除这些差异，也不采用文章的事件、疾病或因果断语。第九轮的 1879 年 NASA/JPL 请求失败；本轮成功重取同一组预定 TT 历元的月球、木星与海王星响应，保存原始字节与哈希，见历史星历参考（本地数据：`../tests/fixtures/uranian-historical-horizons.json`）。这只核对固定 TT 的天体经度，仍未裁定原刊钟时和印刷差异。

研究同时暴露了真实接口缺口：底层支持秒数，公开接口却只收分钟。现在专用德国盘、13 等分盘及 `astro_chart` 对应变体接受 `birth_second=0..59`；`chart`／`hellen` 变体仍拒绝非零秒数，七政四余按自身现行合同保留秒及小数秒，不能套用旧的拒绝断言。秒数进入基础盘、TT／UT1、原生因素、生时样点和可选太阳弧／日天顶。德国盘的实际钟时见 `base_chart.person_info`，13 等分盘见 `person_info`。在上述明确输入下，省略 50 秒会让 MC 移动约 12.8′，并改变原生三／四因素命中集合。输入秒数不等于生时已经精确；省略秒数仅表示用所给分钟起点作为计算表示，误差未声明仍为 `not_assessed`。

### 显式民用、平太阳与真太阳钟时

德国盘与 13 等分盘的 `birth_clock_basis` 声明**输入记录本身的钟时基准**。依据 [Swiss 编程手册 9.2／9.4](https://www.astro.com/swisseph/swephprg.htm)及其[均时差实现](https://github.com/aloistr/swisseph/blob/master/sweph.c)，当前可选：

| 值 | 输入含义与换算 |
| --- | --- |
| `civil` | 默认民用钟时，使用 `birth_timezone` 或既有地点时区推断 |
| `local_mean_solar` | 已知地方平太阳时 LMT；按东经为正，UT1 = LMT − 经度／15 小时 |
| `local_apparent_solar` | 已知地方真太阳时 LAT；先按地心视太阳时角反解均时差，再由 UT1 经共享时标转换到计算 UTC／TT |

太阳钟时模式应省略 `birth_timezone`，并保持 `use_true_solar_time=false`；组合冲突会报错。旧开关保留民用钟时的历史兼容重置语义，输入 LMT／LAT 使用上述明确基准。通用 `astro_chart` 的 `germany/chart13` 变体使用本节入口；`india_chart` 的同名钟时输入另按印度盘当前合同处理。`OZ` 等未辨明的原刊记号需要核实，不能按哪种盘更像原书或更符合事件选择基准。

同一地名的 IANA 历史偏移不一定代表记录地点的地方太阳钟时。例如当前固定规则库对 1879 年的 `Europe/Berlin` 给出的 23:00 对应 UTC 标签 22:06:32；声明 10°E 的 LMT 23:00 则对应历史 UT1 标签 22:20:00。它们回答不同的输入问题。原刊的实际基准仍未认证，新入口只提供明确条件下的计算。

换算规则 `fatebridge.local_solar_birth_clock.v1` 作者为 FateBridge。`person_info.clock_conversion`（德国盘位于 `base_chart` 下）保留原始无时区标签、基准、实际经度、UT1 与计算 UTC、来源和数值往返误差。LAT 另回显地心视太阳赤经、GAST、均时差、实际太阳星历模型和 IERS 恒星时模型。`person_info.birth_timezone=UTC` 与 `birth_datetime` 显示换算后的计算时刻；原钟时从 `clock_conversion.input_wall_datetime` 读取。13 等分文本导出也保留原钟时。微秒表示与小数 JD 的数值分辨率不构成生时记录或历史地球自转的准确度认证；`clock_accuracy_certified/measured_eop_applied` 均为 false。

本轮同时修正了共享时标的反向路径：1960 年前的 `utc_to_jd/jdet_to_utc` 在 [Swiss 日期代码](https://github.com/aloistr/swisseph/blob/master/swedate.c)中使用 `deltat_ex(...,-1)`；旧 UT1／TT 辅助函数却选 `FLG_SWIEPH`，自动月球潮汐参数不同。原程序在 1879 年的往返偏差约 0.071 秒，在公元 400 年约 30 秒。现保留既有民用正向口径，并让历史辅助函数使用同一选项；1960 年起的显式 UTC 偏移路径继续使用原来的选项。`0.0002` 秒仅是本次数值往返检查界限，不表示古代 ΔT 已知到该精度。

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

确认的生时区间跨越当前钥匙年支持范围时，名义目标有效则继续交付本命、名义太阳弧和日推运；相应 `birth_time_sensitivity` 标为 `partial`，保留全部样点及未计算原因。`computed_sample_count/unavailable_sample_count` 分列数量，`source_pattern.sampled_status=underdetermined`不能当成全部不成立；偏差及坐标跨度仅覆盖已计算样点。边界反例、三端与可运行请求见生时区间核验（本地数据：`validation/solar-arc-boundary-sampling.md`）。

`directed_factors` 是本命坐标的象征性旋转，不是目标日观测到的行星或角点。恒星显示仍采用同一个回归真太阳弧，并固定本命 Lahiri 显示偏移；推运太阳不能冒充目标日实际太阳或次限时刻重新计算的 Lahiri 太阳。

双盘返回 90°／45°度盘的两因素、两种方向的点—中点以及推运中点—本命中点联系。每个因素均有 `natal/solar_arc` 层标识，跨层同名因素保留；零弧恒等式单独标记，根级计数也报告其数量。列表不截取最前几项，计数不作为证据权重或事件概率。同样坐标依据保持同一个 `claim_id`，包括零弧时本命与推运的同一条原文解释。

年长钥匙另有 `profile.key_source_comparison` 和公开 `evidence_views.progression_key`。第二十二轮核读 Witte 1923 年推运常数原刊的八项时角运算，确认两项所印结果分别与本行操作数相差 −60 秒、+3600 秒；源算术检查保留失败，独立回放器退出码为 1。该历史例及正午起算的日期标签未裁定，不参与当前盘计算，不修正用户钟时或黄经。太阳弧元数据版本升至 2，365.25 日钥匙和数值公式未改。原值、传播诊断和范围见常数原页核对（本地数据：`validation/witte-progressive-constant-audit.md`）。

该增量在两平台完成各 72 项回归，再以最终来源校验故障归类完成各 15 项补充检查；两阶段用例重叠，不累加为独立案例。六组同源前后对照保留了全部既有业务数值，Linux 断网安装包实调也通过。解释用例已固定八条判据并取得真实 MCP 参照，模型与人工语义评分仍未执行。源码阶段、原刊失败和完整范围见第二十二轮回执（本地数据：`validation/other-chart-schools-v22-verification.json`）。

### Witte 1925 完整太阳弧表与未定格

`original_table_1925` 整理原刊第87–88页的38行、342个年数格及38个末列值，保留每格原始读数。20年列在3月2日的度数标记未能清楚确定，影响其后至10月18日共24格；这些规范化值保持 `null`，其余318格可以按明确度数递承。涉及正权重未定格的插值返回 `underdetermined`，不补零或拿现代星历选值。末行是次年1月6日，不能并回年初；末列的61′是弧分量，不按六十进制分钟字段拒绝。

原载例的56′＋54°17′＋34′＝55°47′算术成立。精确有理数双向插值与不逐步舍入的延伸得到55°47.925′，只作另一舍入政策的诊断，不能据此宣称原刊算错或改写其结果。原文没有给出生钟时／时区，不补造UTC作现代星历验收。

公开 `evidence_views.witte1925_table` 选择来源、覆盖、算例及 `computed_for_current_chart=false`；完整原表读取同 run 的完整结果或显式表路径。当前太阳弧仍采用原有真实太阳位移及365.25日钥匙，太阳弧元数据版本为3。数值表坐标插值不等于完整历法到太阳弧算法，闰日、亚日、跨年末列及全程舍入仍未裁定。详见原表复核（本地数据：`validation/witte1925-solar-arc-table.md`）。

第二十三轮冻结2533个输入，macOS／Linux各103项通过、零跳过；真实MCP、REST、CLI保留来源限定与全部未定格。六组同源前后对照保留全部既有业务值，断网安装的Linux wheel通过实际服务、Schema和字段卡验收。原表1275个重叠探针中1128个可计算、147个未定，来源完整性检查仍退出1；初次四项字段卡失败及修复保留。详见完整回执（本地数据：`validation/other-chart-schools-v23-verification.json`）。本轮没有新增天文观测、真实模型语义评分或现实结果数据。

### Witte 1924 黄道和差式日推运天顶

指定目标时刻后还返回 `midpoint_analysis.solar_arc_analysis.daily_meridian`。它采用 [Witte 1924 原期刊扫描件](https://www.astrax.de/pdf/34_35_Die%20Differenzierung%20der%20Radixsonne%20und%20die%20des%20unteren%20Geburtsme.pdf)印刷页 15 的明确黄道算式，具名为 `witte1924_ecliptic_day_meridian_v1`：

```text
日推运 IC = 本命 IC + 真太阳弧 − 本命回归太阳 + 目标时刻实际回归太阳
日推运 MC = 日推运 IC + 180°                    （均模 360°）
```

目标太阳单独以目标 TT 计算，并回显时刻、时间尺度、星历模型与闰秒假设；本命黄道显示框架保持不动。日推运上下天顶是此来源的**象征坐标**，既不是目标时刻的物理天顶，也不是仅将本命 MC 加太阳弧。使用两颗回归太阳的差，不能在恒星显示下混入不同年代的岁差偏移。生时误差的每个样点均重算太阳弧、本命 MC 与本命太阳，再给出上下天顶及相对名义值的圆周位移；只证明已采样范围，不代表连续稳定、全部命中式稳定或概率。

原页给出下天顶输入巨蟹 7°15′、太阳弧 62°23′、本命太阳水瓶 6°58′、目标太阳白羊 20°50′，结果为天蝎 23°30′。该**原作者算术例**已单独保存，原坐标是否精确、完整日期到太阳弧的时间钥匙及历史事件含义没有因此验收。本实现年长仍采用上节声明的 365.25 日钥匙。

[1923 年较早文章](https://www.astrax.de/pdf/26_Der%20progressive%20Meridian%20waehrend%20eines%20Jahres.pdf)印刷页 36 对同一例报告的上天顶是金牛 26°34′；1924 下天顶反推的上天顶为金牛 23°30′，相差 **3°04′**。第二十轮逐页复核后，差值可由原文宫头构造解释：1923 用第八宫宫头天蝎 10°19′，1924 算式在此例等价的等距参考为天蝎 7°15′，恰差 3°04′。两项原值均保留，差值不能当通用修正量；另项敏感点比较仍差 4′，完整时间钥匙及整篇原典仍未验收。详见原页、逐行表与独立回放（本地数据：`validation/witte-meridian-original-comparison.md`）。`daily_meridian.source_comparison` 明确其历史例范围，当前坐标仍采用 1924 公式。索引写 1923 年 11 月，而旧文扫描附加页眉写 12 月，月份差异也保留。此层不采用原文关于事件、引力或“从不失败”的主张。

Udo Rudolph 摘页第 14 页还明确提到推移 MC 占据该敏感点的情形。只在实际推运 MC 满足直接占据门槛时，返回该例的限定象征主题，并附 `factor_layers`、目标 UTC 与实际太阳弧。已声明生时范围时，每个样点分别重算太阳弧与推运 MC；输出样点弧度、直接偏差及是否成立。尚未覆盖完整交错层四因素式、实际行运、Witte 逐日 MC、完整关键词或经过验证的现实事件模型。

独立天文验收使用仓库已保存的 **8 个 NASA/JPL 太阳位置与 4 个差值**，位置／弧度容差在比较前固定为 2／4 角秒。这些时刻原先为另一项引擎检查选定，太阳位置从 NASA 响应独立取得，不能把时刻选择本身也称为独立金标准。本次重新读取响应中的数值，并保留原检索日期及来源文件哈希；新联网请求超时，未宣称重新从 NASA 取得数据。旧采集器只保存解码后的 JSON，其原 HTTP 响应正文的字节哈希无法从重新序列化的数据复核；新参考另存可复核的星历正文哈希，新联网采集器也保留原编码字节。

Witte 出版社 [AstrologicPC 手册第 7 页](https://witte-verlag.com/pdf/source/AL319_HINWEISE.pdf)另有 22 对本命／太阳弧坐标，图注为静态 8°示例。PDF SHA-256 为 `f319a3590d2214347af1d99bdb5d2d5634133cfb3c0cbc89f16c822f97851692`。逐对读取可见印刷差为 8°00′或 8°01′；按各栏 1′精度核对后，共同弧度区间相容。原未舍入坐标未知，因此不强行把所有印刷值当成精确输入，也不把这张软件插图当成经典原载命盘、目标日期到弧度的金标准或现实预测证据。

日推运天顶另按原生MC参考资格交付：精确极点的依赖坐标为null，形式值另存；太阳和弧长继续保留。实际网格另核对UTC／TT、零样点及太阳观测角色，错配按运行时来源错误处理。可解析范围不跨未知样点连线，名义参考未知也不抹去其他已知绝对样点。字段、原文和可执行例见日推运参考核验（本地数据：`validation/day-meridian-reference-qualification.md`）。

### 声明生时误差后的重新排盘

德国盘与 13 等分盘现在接受 `birth_time_uncertainty_minutes`：用户已确认的记录时刻正负误差，范围为 0–120 分钟。省略表示未知，返回 `not_assessed`；明确传 0 才评估单个已确认时刻。专用工具与通用 `astro_chart` 对应变体使用相同计算，其他未实现此功能的变体会拒绝该参数，避免静默忽略。

实现版本为 `fatebridge.specialty_birth_time_sensitivity.v1`，作者 FateBridge。在**记录时刻的 UTC 时间轴**上取不超过 30 秒间隔的样点，包含两端和名义时刻；每个样点重新计算原生因素。跨夏令时回拨时不重新猜测含混的墙钟。若用户选择现有真太阳时重置模型，则在每个记录时刻重新应用该模型；记录 UTC 与计算 UTC 分别回显。微秒是 datetime 的表示精度，不是原始生时记录的精度。

已计算的样点用 `factor_scope/factor_count` 明确范围：德国盘为 22 个汉堡因素，13 等分盘只需 14 个物理／参考因素，不读取假设轨道并标记 `hypothetical_element_source.status=not_used`。因此一个不适用于汉堡目录的自定义假设点文件不会阻塞 13 等分的物理分区；它也不会被偷偷用来生成错名因素。未声明误差时仍不生成任何样点。

德国盘的 `midpoint_analysis.time_sensitivity` 返回未舍入因素、TT／估算 UT1、相对名义时刻的坐标变化，以及当前原文符号示例在各样点的直接占据情况。名义解释继续保留，并附 `birth_time_sampled_status`。13 等分盘的顶层 `time_sensitivity` 返回每颗星在各样点的分区及观察到的跨区。

虚构反例 `2000-01-01 04:30 UTC, 0°E/0°N, ±10分钟` 中，名义时刻满足该原文符号示例，41 个样点里有 13 个不再满足；天王星在 13 分区中出现第 2／3 区变化。这些计数证明已找到范围内反例，**不是置信概率**。未出现反例也不能证明整个连续区间稳定；窄于采样间隔的变化可能遗漏。此层尚未评估全部中点命中集合、地点误差、时区规则误差或星历误差。缺少 Swiss 时明确返回 `unavailable`，不以近似轨道伪装这项重排验收。

Witte 出版社的[2024 进阶课程说明](https://witte-verlag.com/?catid=49&id=205%3Ahamburg-grundkurs-astrologie-2023&view=article)明确讨论资料质量、生时不确定性，以及太阳弧半弧／全弧／倍弧和 Witte 的逐日推运天顶。该课程支持继续核查这些技术；30 秒网格与上述状态分类是 FateBridge 的工程选择，并非原典规定。虽已取得并重放上述 1924 算式，完整时间钥匙、不同年代推运方法及独立数值命盘仍需验收，不能用已实现的通用西占推运替代。

核对原载数值命例时还必须保存生时来源版本。出版社的[Witte 传记](https://witte-verlag.com/alfred-witte.html)并列个人自述 21:12 LMT 和登记记录 22:00 LMT；正文及脚注的 GMT 换算差值不同，尚待考订。本实现没有挑选更能拟合事件的版本当成唯一真值，也未用事件倒推用户出生时间。

### 原文条件与极点参考

本命及太阳弧的原文条件现与实际MC参考资格一致：精确地理极点的形式MC不再被统计为已知成立或已知缺失；原数值及形式文案保留在`backend_convention/backend_reading_zh`，实际条件和角距为null，并交付未定样点数。太阳弧范围外与MC参考未定分别计数，保留全部已确认样点。只退化ASC的情形不限制独立MC。依据、读取方法及可执行虚构例见原文条件资格核验（本地数据：`validation/specialty-source-pattern-qualification.md`）。

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

基础盘十二宫制、原生参考角提取、X子午宫与13等分扇区分别有实际来源。当前数码1是Alcabitus／Swiss B；原生参考角的E调用不表示采用E宫头。上一轮说明的错误标签已勘误，新增字段与声明核验见宫制角色核验（本地数据：`validation/specialty-house-roles.md`）。

### Witte1924比较换基与四点镜像

德国盘另有`midpoint_analysis.comparative_geometry`：按Witte1924第138–139页重建五种锚点换基与四点镜像，使用同run实际白羊点表示热带轴，并复用全部已确认生时样点。未解析参考保留null和后端形式值；锚点自身按定义指定的位置不等于物理参考已解析。原表36行在所声明舍入假设下32行相容，三条海王星行及一条太阳框架子午线行仍不协调，全部原值保留；没有采用未裁定的地球宫表或事件解释。来源、现代因素扩展、投影范围与调用见比较换基核验（本地数据：`validation/witte-comparative-geometry.md`）。

## 13 等分扇区的修复与含义

`astro_chart13`（REST `/api/astro/chart13`）和 `astro_chart` 的 `chart_variant=chart13` 使用实际上升为起点，每区宽 `360/13` 度，区间沿黄道采用 `[start,end)`。它与另行选择的十二宫制独立，返回 `sector_profile`、13 个区间及各星的 `sector13`。

旧算法直接用浮点数除以 `360.0/13`，紧邻边界的输入可能跨区；极小负角度取模还可能舍入为 360，产生第 14 区。现改为先对输入浮点值作精确有理数分区，再输出显示数值。每颗星另给 `sector13_evidence` 的未舍入黄经和上升，避免客户端按旧显示习惯舍入后复算到相邻分区。未声明生时误差时仍标记未评估，声明后链接上述实际重排结果；不能把数值精度当成出生记录精度。区间边界浮点显示是近似值，严格定义始终是 `ascendant+n*360/13`。

ASC无法在本角度模型中解析时，实际13扇区返回未定，后端约定值另行保留；德国盘原生参考角、相关中点／太阳弧与生时样点也携带对应限定。具体null语义、未丢弃的样点及三端复现见参考角退化核验（本地数据：`validation/specialty-reference-angle-qualification.md`）。

这是 FateBridge 自定义等分规则 `fatebridge_equal13_v1`，没有把它宣称为某部传统原典，也没有赋予新的性格或事件预测意义。IAU 的天文星座边界并不等宽，见 [IAU FAQ](https://iauarchive.eso.org/public/faq/)。本工具不计算 IAU 星座归属，名称和返回说明已改为“13 等分扇区”。通用西占星座说明仍以实际十二星座与宫位为依据。

## 独立验收与四项状态

参考值来自 [Witte 出版社 2026 星历的原始下载](https://a182559.uranus.1blu.de/data/public/4b5ecc.php?dl=true)，由[出版社页面](https://witte-verlag.com/)提供链接。PDF 版次标为 2026-08-14；SHA-256 为 `61e973148b74711196d5ec3b4a03e202cb3d1f1cfce8e6827bc51347f769bc57`。

从第 1、7、12 页各取月初 00 UT 的 19 因素，合计 57 项。Sun/Moon 原表到角秒，其余到角分；比较前固定容差分别为 2 角秒、1 角分。提取脚本不导入生产计算，不用 Swiss 生成预期值；字体映射、表头和首行与渲染 PDF 核对。物理天体表列 DE442/LE442，假设点另列 Shudde/Neely 元素；二者的证据性质分别保留。

| 目标 | 本轮可检验内容 | 尚未完成的要求 |
| --- | --- | --- |
| 算对历法与几何 | 57 项独立位置表、TT/UT1 口径、独立倍角公式、13 分区全边界探针；实际生时重排；8 个 NASA 太阳位置／4 个真太阳弧及 22 对出版坐标的舍入区间；目标太阳与日推运天顶的分层和样点重排 | 全年代与全地点天文验收、历史钟时、连续区间界与其他误差传播；NASA 数据是既存同一批参考，不是新增独立队列 |
| 符合某部原典 | Rudolph 1979 几何条文、Udo Rudolph 1996 原载符号示例及 Witte 1924 页 15 算式定位；同一历史例三项算术回放，1923／1924 天顶差值由原刊宫头偏移解释；已实现 1923 本命子午宫头构造并保留原表两列残差，另项 4′残差仍在 | 整部原书、完整日期到坐标命盘、其余原文差异裁定和专家复核；整体仍为 `not_assessed` |
| 解释忠于计算 | 敏感点门槛、原文归因、度盘及零弧重复依据去重；真实接口核对本命／推运分层及生时条件 | 真实模型对话的盲审、跨轮资料修正与错误事实注入验收 |
| 能够预测现实 | 已计算指定时刻的象征太阳弧；现实效果尚无结果数据 | 固定事件定义、时间窗、模型及基线，事前登记独立队列，记录失败与弃答，完成盲法结果核验和外部复现；当前 `not_tested` |

本轮没有为四项打满分，也没有把“子集全部测试通过”改写为系统整体权威认证。现有[预测研究评估器](../src/fatebridge/validation/predictions.py)可用于登记后的二元结果，但本几何／符号推运层还没有冻结可验证的事件预测模型或真实研究队列。

预测研究评估器v4另将每条预测和结果绑定完整方案，防止同一批记录在更换事件、窗口、基线或统计政策后直接重用。未绑定的旧资料保留诊断，但不能通过完整协议与统计门槛；具体反例、可执行的负面示例与外部核验边界见方案绑定核验（本地数据：`validation/other-chart-study-plan-binding.md`）。这项保护不增加现实预测样本或效力认证。

咨询技能现有[汉堡中点取证卡](../skills/onda-xingpan/references/hamburg-evidence.md)，明确本命／推运 MC、直接／折叠占据、同一依据去重及出生误差条件。另备 5 个虚构模型验收用例（本地数据：`../tests/fixtures/agent_behavior/other_chart_cases.json`），参数已通过当前公开工具的预检；真实独立模型执行与人工语义复核尚未完成，不能将用例已准备记为解释忠实度已验收。执行和审阅方法见[Agent 验收](agent-evaluation.md)。

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
  tests/test_other_chart_physical_sources.py tests/test_other_chart_historical_reference.py \
  tests/test_ephemeris_source_errors.py tests/test_runtime_and_errors.py \
  tests/test_other_chart_clock_basis.py tests/test_other_chart_birth_seconds.py tests/test_other_chart_two_factor.py \
  tests/test_other_chart_orbit_sources.py tests/test_ephemeris_runtime.py \
  tests/test_other_chart_meridian_houses.py tests/test_other_chart_meridian_transports.py tests/test_other_chart_meridian_native_clock.py \
  tests/test_other_chart_day_meridian.py tests/test_other_chart_solar_arc.py tests/test_other_chart_sensitivity.py \
  tests/test_other_chart_depth.py tests/test_other_chart_schools.py tests/test_other_chart_schools_transports.py
uv run --locked --extra dev python scripts/audit_other_chart_schools.py \
  --output docs/validation/other-chart-schools-evidence.json
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
```

另有三颗历史天体的离线 NASA/JPL DE441 参考，历元和容许度在上轮请求失败前已固定。新响应完整保存在 `tests/fixtures/uranian-historical-horizons.json`，含原始 HTTP JSON 字符串、SHA-256、TT 历元、地心观测点与视黄道坐标定义；它们不替换 Witte 原刊数值，也不确认原始出生钟时。此精度检查需要另行取得并核验 Swiss 星历文件：

```bash
uv run --locked --extra dev python -m fatebridge.fetch_ephe
uv run --locked --extra dev pytest -q tests/test_other_chart_historical_reference.py
```

没有星历文件时的 Moshier 回退必须单独报告：此次海王星误差约 1.097″，超出预定的 1″ 门槛，不能改容许度或省略此案例。使用已核验星历文件后重跑的结果也必须保留实际模型和文件哈希；文件完整性本身不是天文精度保证。此新增固定 TT 检查与共享审计中的旧 57 项出版社参考分列，但同样纳入 `numerical_subset_checks_passed`：当前 Moshier 报告返回失败，已核验 Swiss 数据报告返回通过。完整保留回退模型失败报告（本地数据：`validation/other-chart-schools-v10-moshier-evidence.json`），不合并为原典整例或现实预测验收。

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

REST 把业务参数放请求体，`fields/strict_fields/include_snapshot_text` 放查询参数。MCP 使用同名工具；摘要从公开 `evidence_views` 复制字段，完整几何首次 `fields=null`，再读取同一 run 的 `result_delivery`。数组整体选取，不把 `planets.sector13` 当作数组字段投影。`file_path` 是结果存储包络文件，`file_payload_path=payload` 指定文件内的 JSON 路径；回执 SHA-256 对应分页拼接得到的完整业务 JSON 字节，不包含外层到期时间包络。

重新获取并核对独立原表（普通测试不联网）：

```bash
curl --fail --location 'https://a182559.uranus.1blu.de/data/public/4b5ecc.php?dl=true' \
  --output /tmp/witte-ephemeris-2026.pdf
uv run --locked --extra dev python scripts/gen_uranian_witte_reference.py \
  --pdf /tmp/witte-ephemeris-2026.pdf --check
```

源文件哈希、提取规则或参考行变化都需要人工审阅；不自动接受生产结果为新预期答案。数值与原文条文检查见机器可读报告（本地数据：`validation/other-chart-schools-evidence.json`）。

第十三轮扩展到基础物理星盘：海王星同一 TT 的黄道／赤道两次真实查询曾被另一受管理线程切换目录，混合 Swiss 经度和 Moshier 赤纬，却仅标记为 Swiss。现在单天体状态及整盘配置会话保护覆盖黄道、赤道和 Lahiri 复算；坐标来源改变不会被吞成轨道近似。13 等分盘在 `chart_profile.physical_ephemeris_source` 保留本命物理来源，并与生时样点共同核对；德国盘基础来源另在 `base_chart.chart_profile.physical_ephemeris_source`，有效的原生中点层仍按自身来源保留，不因基础层明确的近似而被丢弃。普通坐标字段、节点解析与已有近似回退口径分别保留。依据 [Swiss 手册 §3.3–3.5](https://www.astro.com/swisseph/swephprg.htm)，黄道和赤道是不同坐标表达，实际返回标志须逐次核对；文件上下文及首尾哈希仍不证明完整依赖或原子读取。

第二十轮验收见完整回执（本地数据：`validation/other-chart-schools-v20-verification.json`）与原页算术证据（本地数据：`validation/other-chart-schools-v20-source-evidence.json`）。重新核读 Witte 1923／1924 原刊，同一历史例的三项运算可回放；3°04′天顶差值由旧文第八宫宫头相对黄道等距位置的偏移解释，另项敏感点比较的 4′残差仍保留。当前 1924 坐标计算函数的语法树未变，四组前后结果除来源说明外精确相同；不能把本轮计成天文精度提升。结构化输出、调用字段卡和解读参考同时注明历史例范围，不采用通用修正量。

计算与协议冻结版在 macOS／Linux 各 80 项通过；最终字段卡更新后，两端各补验同一批 9 项，其中 8 项与原批次重叠，不累加成 89 个独立案例。两批冻结输入分别为 1,289／1,291 项，首尾哈希一致。四个相关运行文件与最终 wheel／sdist 字节一致，实际安装的 Linux wheel 已验证服务与调用指导。当前共享工作区另有并行修改，冻结验收不延伸为全仓认证；真实模型语义对话和现实结果观测本轮均为零。完整原典、四项满分及权威认证仍未通过。

第十九轮验收见完整回执（本地数据：`validation/other-chart-schools-v19-verification.json`）。Moshier 的完整位置求导移至共享经度运动层，覆盖十个物理天体的热带与 Lahiri 黄道；果老仍只采用七政的热带速度，并共用一次修正。输出中的方法名与状态来自实际求导记录，原生速度及各修正分项保留。无原生星历时，太阳视位置策略保留未知 TT，不再把空值当数字；有原生后端却缺少 TT 仍明确报错。本轮不据共享层的接入自动认证各独立原生体系。

定义核对（本地数据：`validation/other-chart-schools-v19-source-provenance.json`）采用独立 ERFA 长期岁差实现复算代码所用的标准 Lahiri 零点及其运动，并保留 1956 参考点的 IAU1976 修正。依据 [Swiss 定义说明](https://www.astro.com/swisseph/swisseph.htm)与[接口手册 §12.2](https://www.astro.com/swisseph/swephprg.htm)，标准 Lahiri、ICRC 与 1940 口径不能互换；真／平零点和黄道框架也须分别处理。该复算符合底层代码定义，1989 年原刊对应页尚未取得，不作为原典整例通过。

847 个候选生产／配置输入先冻结，再取得 2040、2060、2090 年四季各一个预先指定 TT 的 NASA 计算参考。全部对照（本地数据：`validation/other-chart-schools-v19-motion-evidence.json`）保留两端、两种模型及两种黄道的原生与交付速度：沿用 0.002″／日检查线，Swiss 两端前后均为 240／240；Moshier 在 Mac 为 122→164／240、Linux 为 125→164／240。两端均有 156 项绝对残差减小、82 项增大、2 项相同，76 项超限仍保留，最大约 0.47736″／日。同批非速度状态与原生速度逐项相同。NASA 参考属于计算星历，且可能与 Swiss 共享 DE441 动力学，不能当作新增天体观测或现实预测盲测。

最终 94 项专项在两端均通过、零跳过，用例身份一致。80 个开发样点均通过不变的差分检查，实际完整修正覆盖分别为 Mac 80／80、Linux 78／80；Linux 的 2020 年冥王星两种框架均保留未收敛状态。新参考中另有同一水星时刻的两种框架未施加完整求导。内部收敛线仍为 0.0002″／日。初稿测试误要求每点都有完整修正字段；最终测试保留原差分门槛，并按既定契约核对实际应用或未收敛的记录。覆盖数单独报告，初稿失败、修改前对照和更正理由均保留在回执中。

69 个相关生产文件与 wheel／sdist 字节一致，并验证实际安装的 Linux wheel。Mac 宽回归 1,319 项通过，邻近四项既有离线失败已在两端修复；Linux 宽回归完成 206 项后优先验收新增路径，其余未运行项不计通过。黄金对照（本地数据：`validation/other-chart-schools-v19-golden-review.json`）的 91 例前后均正常计算，22 例的速度、相位运动或元数据改变；一处土星驻留求根提前约 4.39 秒，其独立时刻精度仍未验收。黄金输出的静态说明前后保持一致，占星骰明确列出的运动数值随计算更新。保存预期前后均只有同一批 29／91 匹配，62 项既有差异保留，未改写黄金文件。部分时运／卜卦文本嵌入完整 JSON 后较长，渲染与耗时还需继续优化。

离线重放回执（本地数据：`validation/other-chart-schools-v19-frame-replay.json`）验证 1,320 个原始位置样点、240 个派生速度及全部步长差值。原采集器字节单独保存在夹具中；维护脚本仅调整导入排序，协议、参考与容许度不变。可在源码环境审计当前实际后端，或用指定依赖重放保存字节：

```bash
uv run --locked --extra dev python scripts/audit_moshier_frames.py --output /tmp/fatebridge-motion-audit.json
env -u PYTHONPATH uv run --no-project --python 3.12 --with pyerfa==2.0.1.5 --with numpy==2.5.4 python scripts/replay_moshier_frame_reference.py --output /tmp/fatebridge-motion-replay.json
```

审计退出 1 表示实际数值超限，退出 2 表示参考或来源未完备；重放不会访问 NASA，uv 首次准备依赖可能联网。原典整例、真实模型语义及人类现实结果盲测尚未完成，四项满分与权威认证均为 false。

第十八轮验收见完整回执（本地数据：`validation/other-chart-schools-v18-verification.json`）：果老为七政的 Moshier 完整视位置接入独立求导，保留原生速度及修正余项。核对 [Swiss 2.10.03 月亮源码](https://github.com/aloistr/swisseph/blob/v2.10.03/swemmoon.c#L915-L928)与实际绑定源码字节后，复现了原生几何速度公式的一阶曲率项，以及4.32秒名义间隔在浮点历日中的表示差。修正针对速度与所选位置模型的一致性，完整视位置和解析轨道理论本身不被重写。二进制取样采用连续收敛和正反方向联合检查；原生版本不符、未收敛及来源错误分别说明。

候选的816个生产／配置输入先冻结，再采集2036、2056、2086年十二个预先声明TT的NASA参考；924个原始位置样点与84个派生速度已按保存字节离线重放一致。沿用0.002″/日外部检查线，Swiss修改前后均84／84；同一批Moshier样点由30／84提高到52／84，59点绝对残差变小、25点变大，32项超限全部保留，最大约0.761322″/日。没有用新参考挑选日期、拟合逐点修正或放宽门槛。内部收敛线为0.0002″/日，不能当作物理模型误差上界；Swiss与NASA仍可能共享DE441动力学。

Linux与macOS核对相同1,228项专项用例，均通过且零跳过。另份兼容修复快照在两端各通过相同207项，与前组及邻接组有重叠，不能累加。原邻接检查两端各有9项失败：8项仍硬写旧辅助取样数，1项试图把父进程补丁传入新的原生工作进程。针对这些失败撤销果老修改的对照同样失败。修复后按实际辅助查询核对完整来源覆盖，在工作进程本地检验同一配置锁，并另验真实进程边界；原始失败记录保留。349项邻接用例按原有通过项加修复项获得增量覆盖，没有声称原整组一次全绿。

28组未取整原始对照中，Swiss／JPL全部字段相同；Moshier只改变声明的七政速度、修正分项及相应说明，其他坐标、四余、角度、宫头、时间、模型和星表相同。官方黄金收集明确强制Moshier：91例均正常计算，90例逐字节相同；果老一例新增7个修正字段、6个舍入速度变化及对应策略对象，其余字段与全部解释文本相同。保存的果老预期在修改前已含底层模型／版本差异，因此本轮未改写任何黄金文件；冻结时保存预期仅31／91匹配，60项差异保留。

67个选定生产文件与wheel／sdist字节一致，并验证实际安装的Linux wheel返回七政原生及修正速度。当前工作区另通过109项macOS集成检查，所选130个输入运行前后哈希相同；这不把冻结版的跨平台、构建验收扩大到所有后续并行改动。共享检查两端各72通过、2失败，针对两项失败的修改前macOS对照仍失败。Moshier历史海王星超限仍保留。原典整例、真实模型语义及现实预测尚未完成验收，四项满分与权威认证均为false。

第十七轮验收见完整回执（本地数据：`validation/other-chart-schools-v17-verification.json`）：果老七政接入已有的视黄经速度修正链，分别保留原生速度、光行时、章动旋转及完整视位置导数余项。本命与目标盘说明实际模型、版本和已观察的来源文件；速度对应热带视黄道、单位为度/TT日，所选恒星黄道另作位置显示。四余模型及传统格局规则保持原口径。参数和框架依据 [Swiss 接口手册](https://www.astro.com/swisseph/swephprg.htm)与 [NASA Horizons 第45项视赤经／赤纬定义](https://ssd.jpl.nasa.gov/horizons/manual.html)。

候选计算源码先冻结，再按预先声明的2027、2047、2077年十二个固定TT采集、转换新增NASA参考；全部168项对照（本地数据：`validation/other-chart-schools-v17-motion-holdout.json`）同时保留两种模型。沿用0.002″/日检查线，Swiss为84／84通过，原生速度为51／84，修正后最大残差约0.000941″/日；Moshier为27／84，57项超限，月亮最大约0.917289″/日。独立的是采集与转换链，NASA与Swiss仍共享DE441动力学；有限样点一致不认证全域精度或现实预测。

同一冻结版在Linux、macOS各通过相同930项果老专项、零跳过。宿曜赤经研究分支另修复有效内核内位置被无关速度求导越界阻断的问题：只请求位置，保留实际位置来源检查。该修复快照在两端各通过相同217项；它与前组有重叠，不能累加为独立用例数。前后28组默认原始结果完全一致，91个默认黄金输出也逐字节一致；修复不改变历日本命宿、二十七宿事项或默认果老盘。两份构建分别有63／64个选定生产文件与wheel、sdist一致。这些是有指纹的冻结源码验收；工作区其后的并行改动不自动获得验收。 随后对当前工作区的速度、来源、协议和位置专用分支另做64项macOS集成检查，全部通过；所选121个输入的运行前后哈希相同。这不是完整当前工作区的跨平台或构建验收。

速度集成前后，91个官方默认案例只有果老一例的27处速度或来源字段变化，原生速度另存且等于旧值，其他数值与解释文本完全一致。逐项核对后只更新这一例的黄金预期，保留旧字节及59份先前差异，记录时仅32／91份保存预期匹配。邻接346项采用203项默认环境与143项实际星历数据环境的同用例覆盖，原85项环境失败保留；共享检查两端各72通过、2失败，针对这两项撤销果老修改的macOS对照仍失败，不能称全仓全绿。

另份Moshier诊断（本地数据：`validation/other-chart-schools-v17-moshier-diagnostic.json`）在已观察时刻区分原生速度与自身位置求导的一致性、以及相对NASA的物理模型残差。自行求导后仍有明显外部残差，部分点还变差；本轮没有据分数挑选公式、替换失败样点或放宽门槛。Moshier历史海王星超限仍保留。原典整例、真实模型语义和现实预测仍未验收，四项满分与权威认证均为false。

第十六轮验收见完整回执（本地数据：`validation/other-chart-schools-v16-verification.json`）：果老七政的黄道、赤道及目标天区调用遵守所选严格 JPL；距星查找使用同一受管搜索路径，并另记实际地球观测者模型。缺失、损坏、越界内核拒绝交付；原生距星标志、物理观测者模型与罗孛计炁的解析模型分别说明。576 日夹具覆盖原有全年节气扫描窗口，没有缩短扫描或替换失败样例。

冻结计算版在 Linux、macOS 各通过相同 838 项果老专项。辅助状态来源角色修正另在两端各通过相同 145 项检查，与前组有重叠，不累加为独立用例总数；辅助文件变更仍被拒绝。24 组常规数值前后相同；两份构建分别有 57／60 个选定生产文件与源码字节一致。这些是本地冻结源码验收，不代表整个当前工作区、部署或发行验收。

原全量黄金调用因太乙资料指纹错误失败。逐例诊断保留两项相同失败并取得 89 项正常输出；前后只有果老 profile 新增来源回执，计算值与解释文本相同，来源角色修正未改变这些默认输出。现有果老黄金文件已等于实际修正输出，本轮没有改写黄金文件。邻近检查两端各 201 通过；共享检查各 71 通过、3 失败，撤销本轮果老修改的对照同样复现三项失败，不能称全绿。

距星目录快照保护的另一份冻结兼容检查在 macOS 为 34 通过，Linux 为 32 通过、2 失败。两项失败发生在产品调用前：固定长度目录在 Linux 合并后仅 195 字节，没有达到测试要求的 242 字节边界。改为按编码字节构造长目录，保留原边界、坐标与配置恢复断言后，同一生产源码的这两项检查在两端均通过；原始失败保留，采用增量覆盖，不冒充一次新的 34 项 Linux 整组通过。

新增框架与目标中心诊断（本地数据：`validation/other-chart-schools-v16-frame-diagnostic.json`）保存预先声明的组合、五份 NASA 原始响应及全部结果。旧参考的 IAU76/80 框架和行星本体中心与默认输出存在差异；匹配质心参考并请求 JPL Horizons 近似模式后，三个固定 TT 残差约 0.001–0.0013″。近似模式与同源 DE441 交叉检查不构成绝对精度证明，旧 Moshier 超限与原门槛完整保留。另份速度诊断（本地数据：`validation/other-chart-schools-v16-motion-diagnostic.json`）发现果老仍使用原生黄经速度：30 个 Swiss 月亮样点均超过既有 0.002″/日检查线，固定 TT 实际函数调用复现该路径。该轮尚未完成其修正集成，也未据此推断现有格局判断错误。原典整例、真实模型语义和现实预测仍未验收，四项满分与权威认证均为 false。

第十五轮验收见完整回执（本地数据：`validation/other-chart-schools-v15-verification.json`）：印度原生盘的黄道、赤道、运动坐标及太阳事件复核进入严格 JPL 调用；可选运动坐标与原生位置保持同一配置会话。印度盘、人类图的物理模型汇总与解析平交点分开，原始节点标志另列。人类图主盘不再因严格 JPL 禁止可选 Moshier 参考而整体失败，参考明确标记未计算；`require_swiss_files` 仍要求实际 Swiss 压缩数据文件，不以 JPL 偷换其含义。

保留原断言和容许度、修正日出枚举夹具及补齐快照 Git 属性后，同一组 1,594 项专项在 Linux、macOS 均通过、零跳过；Linux 为完整用例清单的串行分组，逐项核对两端用例身份，原中断与失败报告保留。另份含后续并行改动的冻结副本在两端各通过 257 项兼容检查，两份构建各有 50 个相关生产文件与 wheel／sdist 字节相同。12 组有数据／Moshier、三个年代及两种交点约定的前后对照中，坐标、设计时刻求根、太阳事件和机械结构精确相同。91 个默认黄金案例只有三例、43 处来源元数据及并行版本标签变化，渲染文本逐段核对；只更新两份印占预期，人类图预期已与保存的 Linux 输出相同而未改。其余 35 份先前差异保留，保存输出与基线为 56／91 匹配，不能称全绿。

邻近检查两端各为 873 通过、1 项 Moshier 历史海王星超标；共享检查各为 72 通过、2 项失败，六爻回放和风水视图失败在撤销本轮修改的对照中同样出现。数据模式的有限数值审计通过，Moshier 约 1.097″ 的失败仍保留。新 192 日 JPL 夹具只验证虚构 J2000 人类图的既定求根范围，不是完整内核或全年代认证。后续还复现果老严格 JPL 旁路，另行修正验收；本轮不认证其他流派全部完成。原典整例、真实模型语义及现实预测仍未验收，四项满分与权威认证均为 false。

第十四轮验收见完整回执（本地数据：`validation/other-chart-schools-v14-verification.json`）：平交点单列解析模型，物理模型汇总不再由交点回显位误报为混合；严格 JPL 选择进入德国原生因素、恒星观测者与恒星传播。66 个逐星状态、两种黄道的 22 因素及 40 个默认恒星位置与修改前相同；严格模式的 20 个物理黄经与直接 JPL 调用完全相同。黄金对照发现新标签曾使下游把平交点误归为未确认，故采用当前工作区已有的具名理论点适配与对应回归；错误中间快照和差异均保留，没有放进元数据白名单。

计算层冻结版在 Linux、macOS 各通过 348 项专项；分类适配修正后，两端各通过 602 项扩展回归，37 个相关生产文件与 wheel／sdist 字节一致。90 个默认案例前后只有 7 个案例、27 处明确模型元数据变化，其他坐标、联系、参考点分类和解释文本相同；仅逐项更新对应预期并保留旧字节、执行并发核对。对修正版本的真实 Linux 输出再次比较交付预期，完整黄金仍为 46／90 匹配，剩余 44 项修改前差异原样保留，不能称全绿。共享检查两端各为 73 通过、1 项六爻旧回放失败；另份含并行改动的冻结版本通过 121 项针对性兼容检查。已验证数据的有限数值审计通过，Moshier 历史海王星约 1.097″ 超标不放宽；原典整例、真实模型语义及现实预测仍未验收，四项满分与权威认证均为 false。后续探针还复现印度原生盘绕过严格 JPL 及人类图交点来源标签问题，本轮不宣称其他流派全部修复。

第十三轮验收见完整回执（本地数据：`validation/other-chart-schools-v13-verification.json`）：同一冻结生产代码在 Linux、macOS 各 325 项专项通过；星表预热夹具明确清除环境目录覆盖后，生产字节相同的快照两端各 466 项邻近回归通过，原失败报告保留且未改断言。最终 33 个相关生产文件与 wheel／sdist 相同。两项默认黄金输出只新增物理来源对象，旧业务字段精确相同；先保存旧字节、核对并发哈希后更新预期，最终 Linux 已重跑匹配。共享检查两端各 71 通过、2 失败，分别为六爻旧回放与行内／完整文件回执不一致，未据此宣称全仓通过。后续 JPL 来源和托勒密／Lilly 字段的并行改动保留，另用最新冻结快照复核 124 项默认模式兼容性；不等于严格 JPL 或全部当前代码验收。旧模型汇总包含解析交点标志的问题仍保留，应读取逐物理因素来源。1960 交界探针区分此前 UT1 载体与此后的历史 UTC，不把跨口径约 22.5 毫秒标签差当作同尺度天文误差，也未修改时间换算。原典整例、真实模型语义及现实预测仍未完成验收。

第十二轮针对太阳弧与日推运的太阳计算链：同一 TT 的两次真实太阳查询曾被另一受管理工作线程切换目录，分别使用 Swiss／Moshier，令零时差产生约 0.0000010054° 的假太阳弧。现在整批查询共用配置锁，相同 TT 复用一次观测；`profile.sun_ephemeris_source` 保留逐时刻模型、文件上下文与哈希，本命／推移／目标及各样点用索引引用。出生太阳全部使用 Swiss，不代表约 40 象征年后的推移太阳样点也保持同一来源：真实数据覆盖边界已复现这一反例；现在按语义角色逐组检查，补齐相邻文件后仍使用原来的 ±1 分钟、5 样点。不同物理日期合法使用不同模型时如实报告，不强制把所有时刻降级。原生本命与重算本命的太阳文件身份也须一致。核对 [Swiss 2.10.03 源码 sweplan](https://github.com/aloistr/swisseph/blob/v2.10.03/sweph.c#L1844) 后，另确认月球内部回退时太阳仍可能返回 Swiss 标志；真实月球覆盖边界探针复现了这种情况，故比较包含已观察月球文件及其出现／消失，全部文件仍做首尾哈希检查；这些措施不证明完整原子读取或天文精度。来源语义依据 [Swiss 官方接口手册 §3.5](https://www.astro.com/swisseph/swephprg.htm)，请求的模型不等于实际返回的模型。

本轮最终冻结源码的 Linux、macOS 各 311 项专项通过；29 个相关生产文件与 wheel／sdist 逐字节一致，两项默认黄金输出相同，未改基线。正确重跑的共享检查两端各 72 通过、1 项旧六爻回放失败。首个探针未截获调用、早期共享脚本用了不存在的测试名，以及只检查太阳主文件的中间方案，均被排除或替换，详见第十二轮回执（本地数据：`validation/other-chart-schools-v12-verification.json`）。当前工作区另补齐并行相位契约遗漏的 `Literal` 导入，40 项兼容性检查通过；期间还有其他并行源码修改，因此不把它写成完整当前工作区验收。Moshier 超标、原典差异、真实模型与现实预测未验收状态继续保留，四项目标和权威认证仍为 false。

第十一轮回执（本地数据：`validation/other-chart-schools-v11-verification.json`）记录原生物理星历的实际文件上下文、哈希与 DE 版本，以及生时样点逐因素模型／文件／版本的一致性保护。只安装部分段时，2400 年实际覆盖边界的同一 ±1 分钟区间曾混用 Swiss／Moshier；补齐相邻段后仍保留原来的 5 个样点，不改区间或容许度。三端具名来源错误与补齐后的完整结果均已验证，通用关键字规则不再将其抹成缺少依赖；固定白名单消息不回显服务器路径。最终冻结版本 Linux、macOS 各 296 项通过，45 个相关生产文件与 wheel／sdist 字节相同。冻结共享检查为 58 通过、2 失败：其中宿曜来源哈希漂移已用正式生成器修复，当前场景／路由／依赖 14 项及并行钟时接口兼容性 133 项另行通过；六爻旧回放预期失败仍保留。冻结默认输出两端均匹配保存的基线；本轮唯一已审阅的新增预期为德国盘物理来源对象，所有旧业务字段相同并已保留旧字节。随后并行的托勒密界限表新增及当前基线未被覆盖。Moshier 历史海王星超标报告、原刊差异与真实模型／现实预测未验收状态均保留，完整四项目标仍未实现。

第十轮回执（本地数据：`validation/other-chart-schools-v10-verification.json`）记录 1960 年前共享 TT／UT1 正反算选项修复，以及民用／地方平太阳／地方真太阳钟时的显式输入、原始标签溯源和误差区间映射。最终 Linux 只读源码 240 项专项通过；macOS 初稿及邻近回归 605 项、最终钟时和三端复核 81 项通过，范围与源码差异分别列明。新增三颗历史天体的 NASA/JPL 原始响应使用上轮预定历元和容许度：已核验 Swiss 星历 3／3 通过，Moshier 回退 2／3，海王星约 1.097″ 超出 1″ 门槛，失败不跳过、不放宽。两种模式都已进入最终审计，失败报告与通过报告分别保留。共享回归为 59 项通过、1 项六爻旧回放预期失败；默认两端黄金差异仅为共享地球自转溯源元数据，其他数值及业务字段相同，本轮未更新基线。原典数值整例、真实模型语义和现实预测仍未验收，四项目标与权威认证仍为 false。

第九轮回执（本地数据：`validation/other-chart-schools-v9-verification.json`）记录已知秒数经专用／通用请求、三端协议、生时样点和推运完整传递：Linux 只读快照 184 项专项、macOS 含邻近回归 223 项通过；共享输入、缓存、回放与调用合同合计 58 项通过、2 项失败。失败分别是六爻非法输入的旧回放预期，以及八字事业断言 75 与当前返回 93 不一致，均未通过改写预期掩盖。原刊 12 项经度、后出 GMT 换算及条件性的地方平太阳时算术分开记录，原典数值整体验收仍未通过，新增 NASA/JPL 请求也未成功取证。默认德国盘业务字节不变；13 等分只有共享 `equal_mc` 标签及其导出副本的文案更正，已按 Swiss 手册和实际第 10 宫宫头等于 MC 核实，数值未变。当前两端基线与保存的 Linux 实际字节相同，该轮未写入基线；回执只覆盖冻结源码及列出的当前等值范围，不认证全部并行工作区。

第八轮回执（本地数据：`validation/other-chart-schools-v8-verification.json`）记录 v3 两因素硬相位、全圆角度身份与跨盘去重：当时 Linux 只读快照 154 项专项与 macOS 含邻近回归 193 项通过，三端返回一致。两组角度边界和三组 22 因素输入与归档旧代码比较，已有几何完全相同。标准黄金输出另保存未舍入 Linux 原始响应，以独立三角式核对新命中及偏差；不从分别舍入至八位小数的黄金坐标推算原始偏差，也没有放宽容许度。移除声明的新增字段及版本／说明变更后，德国盘整个旧业务输出相同；13 等分业务字节未变。只在保存旧字节、分类差异与最终并发比对后更新德国盘基线。共享回放为 35 通过、1 失败，其他未通过的共享检查见该轮回执；这些数量不等于现实预测验收。

第七轮回执（本地数据：`validation/other-chart-schools-v7-verification.json`）记录实际环境目录优先级、外部轨道来源及因素身份、样点来源一致性、回执指纹刷新，以及 13 扇区与未使用轨道的隔离；当时 Linux 137 项专项与 macOS 含邻近回归 176 项通过。共享回放有一项非法／空白六爻输入与旧测试预期冲突，不据此宣称全量通过。该轮黄金差异仅新增八个因素名和一个来源对象，已有业务事实完全不变；两端基线与当时保存的 Linux 实际字节相同，该轮没有写入基线。

第六轮回执（本地数据：`validation/other-chart-schools-v6-verification.json`）保留具名 1924 日推运天顶、原载算术例与未裁定差异、Linux 只读快照 109 项专项、macOS 含邻近回归 148 项，以及发行构建字节核对。

第五轮回执（本地数据：`validation/other-chart-schools-v5-verification.json`）保留当时取证卡、模型用例准备、共享测试修复，以及冻结副本 138 通过／2 失败和生成合同重建后的独立复核；真实模型及现实预测仍未验收。

真太阳弧后的 macOS／Linux 各 90 项专项、构建文件、源码指纹，以及当时尚未通过的共享检查和默认黄金快照，见第四轮验收回执（本地数据：`validation/other-chart-schools-v4-verification.json`）。第三轮各 71 项（本地数据：`validation/other-chart-schools-v3-verification.json`）、第二轮各 44 项（本地数据：`validation/other-chart-schools-v2-verification.json`）及首轮各 28 项（本地数据：`validation/other-chart-schools-local-verification.json`）保留当时范围；共享数值报告会更新，历史回执中的旧报告哈希只对应当时字节。多人并行修改工作区时，回执只描述列出的源码指纹与检查，不表示其他领域或整个工作区已验收。


### 本命与太阳弧的交错配对

新增 `solar_arc_analysis.mixed_pair_geometry`，核读Witte1925第53–54页后，对四个不同因素的本命／同一太阳弧混合配对作具名代数重建。系数±0.5的关系与弧长抵消的关系分列，保留每组四个等价层次安排；旧同层目录与计数不混入新目录。后者不能当作新增择时触发或独立证据。实际来源、完整有限域和名义盘重放见交错组合核验（本地数据：`validation/hamburg-mixed-pair-geometry.md`）。

交错组合现可复用同run的完整已确认生时网格，分别记录成立、不成立、变化和未定，也保留名义盘没有而样点中新出现的关系。弧长不可用或物理参考角未解析时保留对应未知，不把未列出或共同太阳弧抵消解释为生时稳定。原生因素与太阳弧样点须共享有效UTC标签及主TT历元；错配按运行时来源不一致报告。规则、公开摘要视图与可执行例子见交错组合的生时样点评估（本地数据：`validation/hamburg-mixed-pair-sensitivity.md`）。第三十四轮回执（本地数据：`validation/other-chart-schools-v34-verification.json`）记录两端各103项专项与三端结果；有限网格测试不证明连续区间或现实预测有效性。
