# 汉堡中点与德国盘取证

只在指定德国／汉堡／中点盘及其太阳弧时读取，使用 `hamburg_midpoint_chart`。全部几何由引擎计算。

## 先选本次需要的层

从当前公开 `evidence_views` 复制所选视图的 `fields`（三端始终严格校验路径）；视图名不是参数。

| 问题 | 视图与必须核对的内容 |
| --- | --- |
| 方法与范围 | `overview`：`midpoint_analysis.status/profile/reading_guide/limitations`；计数只是几何联系数量 |
| 一条原文解释为什么适用 | `source_meaning`：实际 `interpretations`、`factors`、`sources/rule_trace` 与 `time_sensitivity` |
| 确认的生时误差范围 | `time_sensitivity`：完整重排样点、记录／计算 UTC、`source_pattern`，不能用概览中的状态代替条件 |
| 用户指定带时区目标时刻的太阳弧 | 传 `analysis_datetime` 并选 `solar_arc`：实际 `profile`、`interpretations`、`birth_time_sensitivity`、`sources/rule_trace` |
| Witte 日推运天顶 | 同样传明确目标时刻并选 `daily_meridian`：读取 `solar_arc_analysis.daily_meridian` 的实际上下天顶、目标太阳、时间口径及自身样点 |
| 要核对某条两／三／四因素式 | `geometry` 或 `contact_evidence`：因素种类、原始经度、实际度盘及命中式 |
| Witte1924换基或镜点四点系统 | `comparative_geometry`：来源、实际白羊点、五个锚点框架及自身生时条件；需要具体点时首次加入框架或`radix_systems`路径；样点须选择完整`birth_time_sensitivity.samples`数组，再读各项`point_systems` |

完整 JSON 使用 `detail=audit`、`fields=null`；不另算一个盘补齐摘要未选的字段。

## 本命几何与原文含义

- 原生 `midpoint_analysis` 有 22 因素，包括八个**数学假设点**；`contains_hypothetical` 与因素 `kind/model` 必须保留。这些点不是 NASA/JPL 观测到的天体。顶层七曜 `midpoints/midpoint_aspects` 与原生 90°／45°盘的因素范围和容许度不同。
- v3 的 `dials.*.two_factor_contacts` 是两个不同因素的本命硬相位。`A=B` 只表示折叠度盘接近：按 `aspect_degrees` 说明 0／45／90／135／180° 类型，按 `separation_degrees` 说明实际夹角，保留 `signed_orb/orb`。`factor_offset_degrees` 是 A−B 的全圆方向偏移，不等于模 180° 的中点轴偏移；180° 对冲不能叫合相。`unique_two_factor_pair_count` 跨盘按因素对去重，仍不是独立事件证据数。几何命中本身不提供尚未审读的原书关键词。
- `profile.hypothetical_element_source` 说明用库内置参数还是外部 `seorbel.txt`；因素的 `element_name` 保留实际名字。不要把物理星体的 Moshier／Swiss 返回标志当成“假设点也必定用默认轨道”的证据。自定义轨道版本未对照出版社星历时，不套用默认模型已验收的结论。
- `A/B=C/D` 的折叠关系不自动表示 `A+B-C=D` 在完整 360°圆上直接占据。核对 `sensitive_point.occupancy/direct_orb`；`folded_only` 不能说成直接合相。中点式转和差式的周期与容许度都加倍，不能混用角偏差。
- 当前原文含义只覆盖 Udo Rudolph《ABC für Planetenbilder》1996 首版、出版社摘页**印刷页 14／PDF 第 6 页**的 `MA+JU-ZE=MC` 示例。实际 `interpretations` 命中后，才可归因为关于个人目标与行动成效的象征讨论；保留 `source_id/source_section/basis_expression/direct_orb_degrees/maximum_orb_degrees`。
- `interpretations=[]` 只表示当前没有生成这条限定解释；参考未定时不能把空列表当作已知未命中。它不表示整部书没有其他解释，也不能补写未核对的关键字。相同 `claim_id` 在不同度盘或零弧图重复出现只算同一坐标依据，不增加证据权重。
- 几何条文另据 Ludwig Rudolph《17 Gesetze für Planetenbilder》，《Hamburger Hefte》1979/2、第 74 期、第 1 页，第 3、7、13–16 条。几何条文核对不等于整部原书已验收。

## 生时误差会改变哪些判断

仅使用用户确认的名义时刻与 `birth_time_uncertainty_minutes`；未声明误差为未知，不能写作零误差。未知生时不猜一个名义值。±N 分钟是资料范围，不是统计分布。

用户已记录秒数时，德国盘及 13 等分盘可传 `birth_second=0..59`。省略仅表示用该分钟的起点计算，不表示生时精确到秒；有秒数也不自动把未知误差改成零。按实际 `base_chart.person_info`（13 等分为 `person_info`）核对钟时及 UTC，不截掉已给出的秒数。

已知输入记录是地方平太阳时／真太阳时，才传 `birth_clock_basis=local_mean_solar/local_apparent_solar`，同时省略 `birth_timezone`、保持 `use_true_solar_time=false`；默认 `civil` 表示民用区时。读取 `person_info.clock_conversion`（德国盘在 `base_chart` 下）的原始钟时与换算后 UTC。太阳钟时的误差区间先转换端点后才生成 UTC 样点，不把输入 ±N 分钟当成精确等长的 UTC 秒数。

`time_sensitivity.source_pattern.sampled_status` 及解释中的 `birth_time_sampled_status` 决定这条含义如何表达：`varies_across_samples` 表示已找到范围内反例，要保留“名义时刻满足，但范围内会变化”。全部样点满足仍不证明连续区间稳定。

精确地理极点的MC只有输入经度所定子午线约定时，本命和太阳弧的原文条件都须保留未定：读取 `unresolved_reference_sample_count`、`unresolved_reference_sample_indices`、`resolved_condition_sample_count` 及 `condition_by_sample`。范围外弧的 `unavailable_sample_count` 与参考未知数分开。名义解释的 `source_application_status=underdetermined_reference_geometry` 及 `reading_zh` 表明适用条件未知；仅 ASC 交线退化不限制独立 MC。

## 指定时刻的真太阳弧

`midpoint_analysis.solar_arc_analysis` 仅在传入目标时刻时计算。它选用每 365.25 个 UTC 日历日对应 1 个 TT 星历日的符号钥匙，以实际太阳位移旋转本命因素；核对 `profile.analysis_utc/key_years/solar_arc_degrees/key_policy/sun_ephemeris_models`。

`profile.progressed_julian_day_tt` 是实际推进太阳查询时刻，由保留的出生 TT 和精确日历钥合成；`profile.key_years` 是显示值，日子午和生时样点用各自绑定的太阳观测。

`directed_factors` 是象征旋转，不是目标时刻天上观测位置。每条联系的 `natal/solar_arc` 标签和 `zero_arc_identity` 保留；当前限定原文解释为 `Mars.natal+Jupiter.natal-Zeus.natal=Midheaven.solar_arc`，不能把推运 MC 改成本命 MC，也不能将这一时刻扩展为整年。

太阳弧解释的生时条件读取自身 `birth_time_sensitivity.source_pattern`，该层会在每个生时样点重新计算实际太阳弧及推运 MC。

太阳来源读取 `solar_arc_analysis.profile.sun_ephemeris_source`：`observations` 以实际 TT 时刻去重，`sun_observation_indices` 按本命／推移顺序引用它；相同 TT 共用一次观测。不同日期可能使用不同模型，同一角色的生时样点模型或文件内容不一致时，须按来源错误核对数据配置。

`daily_meridian` 采用 Witte 1924 印刷页 15 的黄道算式：本命 IC 加太阳弧、减本命回归太阳、加目标时刻实际回归太阳；相对的上天顶为 MC。核对它自己的 `profile.upper_meridian_longitude/lower_meridian_longitude/target_tropical_sun` 和 `birth_time_sensitivity`。该历史例 1923／1924 的 3°04′ 差值只适用于该历史例，不加到当前盘面。

日推运的 MC 参考资格另读其自身 `profile`：`partial` 可仅限制 MC 依赖坐标，太阳与可计算弧继续交付，形式值保留在 `backend_convention`。

## Witte1924比较换基与镜点

使用 `comparative_geometry` 视图读取 `midpoint_analysis.comparative_geometry` 摘要。五个锚点及四点坐标是本命资料的象征几何，镜像轴用实际原生白羊点；框架内名为 Aries Point 的输入因素同样旋转，轴基准仍取 `profile.native_aries_point_longitude`。`defined_anchor_identity` 只表示锚点坐标按定义抵消，实际坐标为 null 时保留其后端形式值限定。生时偏移只覆盖已确认有限样点。

## 交付时保留来源和含义

先解释实际返回且与所问有关的两三项关系，再把来源的限定象征含义联系到现实中可观察的目标、行动和成效标准。未命中原文解释时仍可解释实际几何关系和计算范围，不能为了给出断语另造关键词或事件。

作者、规则版本及来源回显在 `profile/rulesets/sources/rule_trace`。完整原书符合度为 `not_assessed`，不能被测试数量、多个度盘一致或出版物署名替代。

原生物理因素的数据版本与假设轨道分开读取：`profile.physical_ephemeris_source` 保留实际模型、文件名称及文件头 DE 版本；生时样点的 `physical_source_index` 对应 `physical_ephemeris_sources`。来源无法识别时保持该限制；模型／同名文件内容／DE 版本切换会使纯生时比较报错，需要补齐所声明区间的数据，不能删去失败样点。文件上下文不证明精度或原子读取。NASA 与 Swiss 可能共用 DE441，不能将交叉检查称作两套独立动力学证据。

基础盘另读 `base_chart.chart_profile.physical_ephemeris_source`。黄道经纬度、赤纬和恒星黄道复算共用受管理的配置会话；明确的基础盘轨道近似与原生中点层可能不同，按各层实际来源解释，保留有效部分。13 等分盘的对应来源在 `chart_profile.physical_ephemeris_source`，不是中点字段；它的生时比较还核对本命与样点来源，不能把数据切换当作生时效应。

`ephemeris_model_scope=physical_bodies` 下，模型汇总只含物理天体；平交点的 `swisseph_analytical_mean_node` 与基础盘 `nonphysical_factor_models` 另读。中点交点 `native_return_flags` 可回显请求位，不能据此断言读取 Swiss／JPL 矢量文件，或把全 Moshier 物理盘说成混合模型。交点近似仍影响计算质量，不能因物理模型标签一致而隐瞒。显式严格 JPL 选项也用于原生德国因素及恒星观测者，来源错误按实际原因交付；96 日系数子集测试不认证完整年代。

`ephemeris_source_inconsistent` 的 `issues` 指向 `runtime.ephemeris_data`，是来源配置／变更问题；保留其具名原因，不误述为出生资料错误或缺少 Python 包。`retryable=false` 时不原样反复调用；先补齐区间数据、重新加载后再重做相同输入，不变更用户已确认的误差区间。

原文链接：[Ludwig Rudolph 条文](https://www.witte-verlag.com/hamburger-hefte-menu/datenbank/823.html)、[Udo Rudolph 出版社摘页](https://witte-verlag.com/component/djcatalog2/?fid=12&format=raw&task=download)、[Klaus Bonert 2007 太阳弧作者摘文](https://www.astro.com/astrologie/in_sonnenbogen_g.htm)。最后一项只采用太阳位移的技法说明。
