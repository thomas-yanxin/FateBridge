# 家居风水现场资料、口径与分层结果解读指南

[基础规则与来源](rule-sources.md) · [中州派玄空](xuankong.md) · [家居风水参考](../../fengshui.md) · [硬边界](../shared/safety-boundaries.md) · [咨询核心](../shared/consultation-core.md) · [示例索引](../../examples/README.md)

本指南定义 FateBridge `fengshui` 家族 8 个工具的现场资料采集口径、边界护栏与分层输出读法。所有计算由引擎完成，引擎仅产出确定性结构化事实，不生成化解处方、摆件疗效或全宅吉凶总分。

开始前先核对[硬边界](../shared/safety-boundaries.md)与[咨询核心](../shared/consultation-core.md)：不涉及生死寿命、灾祸断言、临床诊断治疗或医疗择时；未知出生时刻或宅向不猜、不套示例默认值；只解释当前聊天已确认的资料。

## 1. 八个真实工具的输入与缺项处理

按用户实际问题、指定方法与已确认资料选择工具，不预设固定主题的调用组合。八个工具均支持 `detail=compact`（默认）与 `detail=audit`（配合 `fields=null` 取完整载荷、全部时间线与完整来源引文），各工具实时参数以当前连接的 Schema 为准。

| 工具名称 | 核心输入与口径 | 必填与互斥规则 | 缺项与 `partial` 处理 |
| --- | --- | --- | --- |
| `fengshui_directions` | 可选 `bearing_degrees`（0°–360°）、`north_reference`（`magnetic` \| `true`）、`geomagnetic_reference` | 传入 `bearing_degrees` 时必传 `north_reference`；地磁分支须提供 WGS84 经纬度、椭球高 km、`evidence` 及 `model_date` / `decimal_year` 之一 | 不传角度仍返回固定后天八卦与洛书宫位（`complete`）；地磁仅返回模型换算候选，不自动改宅向 |
| `fengshui_minggua` | `birth_date`、`effective_birth_year` 或 `birth_at`（含时区）；`timezone_name`（默认 `Asia/Shanghai`）；`year_boundary`（`lichun` 默认 \| `january_1`）；可选 `gender_convention` | `birth_date`、`effective_birth_year`、`birth_at` 三者最多提供一项；日期与时刻限 1801–2199 年 | 缺年份依据返回 `partial`；缺 `gender_convention` 时同时返回 `male`/`female` 两套候选并记入 `missing_inputs` |
| `fengshui_bazhai` | `house`（`sitting_trigram` 或 `facing_degrees` + `north_reference`，可选 `bearing_uncertainty_degrees` 0°–180°）；`occupants` 列表；`placements` 列表（`door` \| `bed` \| `desk` \| `stove`） | `placements` 须至少提供 `location_direction` 或 `facing_direction`；传 `facing_direction` 须配对 `facing_role`（`door_facing` \| `headboard` \| `desk_facing` \| `fire_mouth`）；`subject_id` 与 `subject_ids` 互斥 | 缺 `house` 或 `occupants` 返回 `partial`，不阻止另一侧单独计算；`placements` 缺 `location_direction` 记入缺失而不臆造 |
| `fengshui_jinsuo` | `features` 列表，每项含 `object_id`、`direction`（八宫）或 `mountain`（二十四山）、`classification`（`sand` \| `water` \| `mixed` \| `unknown`）、`classification_basis`（`measured` \| `user_confirmed`）、`evidence` | `direction` 与 `mountain` 至少提供一项，同传时须属同一宫；`object_id` 不可重复 | `features` 为空或存在 `mixed` / `unknown` 时返回 `partial`，同时仍输出八宫与二十四山基础砂水偏好表 |
| `fengshui_annual_stars` | `effective_year`（1800–2199）或 `query_at`（1801–2199，含时区）；`timezone_name` | `effective_year` 与 `query_at` 互斥，不可同时提供 | 都不传返回 `partial`（不取系统当前日期）；落入立春 5 秒数值保护区返回 `partial` 与候选年 |
| `fengshui_monthly_stars` | `query_at`（1801–2199，含时区）或成对 `(effective_solar_year, solar_month_number)`；`include_daily_hourly`（默认 `true`） | `query_at` 与 `(effective_solar_year, solar_month_number)` 互斥；`effective_solar_year` 与 `solar_month_number`（1–12）须成对 | 都不传返回 `partial`；落入十二节 5 秒数值保护区返回 `partial` 与 `candidate_months` |
| `fengshui_xuankong_house_chart` | `house`（必须 `north_reference="magnetic"`、`bearing_uncertainty_degrees` 0°–7.5°）；`period`（`basis` + `evidence` + `period_number` / `effective_event_year` / `event_at` 三选一）；可选 `current_period_number`、`interpretation`、`city_gate` | 宅向传入 `true` 真北会校验拒绝；`confirmed_major_renovation` 须 `qualifies_for_period_reset=true`；`expert_confirmed` 须显式 `period_number` | 缺磁北宅向或定运返回 `partial`；跨越 24 山分界或 20 年换运立春边界时保留多候选并标 `partial` |
| `fengshui_assess` | 继承 `BazhaiRequest`（`house`、`occupants`、`placements`），并可传入 `methods`、`analyze_layout`（默认 `false`）、`features`、`effective_year`、`query_at`、`timezone_name`、`xuankong`、`monthly` | 至少选择一层计算；`effective_year` 可与 `query_at` 并用；顶层 `house` 与 `xuankong.house` 同传时须完全一致 | 未传 `methods` 时按已供输入自动选层；仅 `xuankong.house` 有宅向而选 `bazhai` 时自动复用；合法缺项只标对应层 `partial` |

照片与现场确认边界：在玄空扩展观察（`ExternalFormObservation`、`CityGateObservation`、`LingzhengObservation`）中，`observation_basis="image_observed"` 只产出 `candidate_only` 候选并写入 `missing_inputs`；金锁 `EnvironmentFeature` 仅接受 `measured` 或 `user_confirmed`，不接受照片直接定性砂水。普通结果解读可直接交付已有计算事实与条件说明，无需等待现场实测或全部行动条件齐备。

## 2. 地磁偏角换算与宅向测量不确定度

### 2.1 地磁参考分支（WMM2025 与 IGRF-14）

地磁偏角计算仅通过 `fengshui_directions.geomagnetic_reference` 显式启用，用于提供上游地球物理偏角参考与坐标换算候选。

- **模型选择与支持范围**：`model_id="auto"` 时，小数年 `[2025.0, 2030.0)` 选用 WMM2025（`selected_model_id="wmm2025_v1"`，`ruleset_id="geomagnetic_wmm2025_v1@1.1.0"`，12 阶），`[1900.0, 2025.0)` 选用 IGRF-14（`selected_model_id="igrf14_v1"`，`ruleset_id="geomagnetic_igrf14_v1@1.0.0"`，1900–1995 为 10 阶、2000–2025 为 13 阶、2025–2030 SV 8 阶）。显式指定 `igrf14_v1` 可覆盖 `1900.0–2030.0` 全段。
- **高程与时间输入**：必须明确 WGS84 地理经纬度、`height_km_wgs84`（椭球高 km，范围 `-1` 至 `850`，不是海拔 MSL，未知不得填 `0`）、`evidence`，以及 `model_date`（`YYYY-MM-DD`，按当日 UTC 零点与当年实际天数换算）或 `decimal_year` 之一。
- **换算公式与精确保留**：磁偏角 D 东偏为正，换算公式为 `true = magnetic + D (mod 360)`。计算使用输入角与交付 `D` 的精确有理数 `Fraction` 加减并分区后再显示，`conversion.angle_exact` 以分子/分母字符串保留该和式。`conversion.original_input_retained` 恒为 `true`，`conversion.automatically_applied_to_house` 恒为 `false`。
- **异常区与误差边界**：水平分量 `H < 2000 nT` 为黑障区（`zone="blackout"`），地理极点（`|latitude| == 90`）无唯一真北，二者均返回 `declination_usable_as_heading_reference=false` 且 `conversion.status="unavailable"`；`2000 <= H < 6000 nT` 为慎用区（`zone="caution"`）。`uncertainty.declination_degrees` 为 `sqrt(0.26^2 + (5417/H)^2)` 的地表一倍标准差参考（`one_sigma_at_earth_surface_not_hard_bound`），不是现场罗盘总误差上限，不得自动填入 `house.bearing_uncertainty_degrees`。模型换算为 `magnetic` 候选后仍须经现场条件核对，不能直接代替玄空已确认磁北输入。

### 2.2 宅向误差、24 山子区与空亡线界

同一住宅的宅向测量误差半径 `house.bearing_uncertainty_degrees` 同时影响八宅与玄空，未提供时按点方位计算（不代表现场误差为零）。

- **八宅闭区间支持**：八宅支持 `0°–180°` 误差半径，以精确有理数闭区间 `[facing - r, facing + r]` 枚举所有相交的坐山八宫（含跨北向端点）。跨越多宫时 `house=null`，`house_candidates` 列出全部候选并标记 `candidate_only=true`，同时写入 `house.unambiguous_sitting_trigram`。不确定宅卦的作用域不进入 `layout_analysis.adjustment_options[].agreed_matching_directions` 交集，但已确认的住户命卦仍可独立解读。若同时提供 `sitting_trigram` 且与误差区间不相交则报错拒绝。
- **24 山子区与空亡线界**：每山宽 15°（左闭右开，如子山为 `[352.5°, 360°) ∪ [0°, 7.5°)`）。偏离山中心 `|offset| <= 1.5°` 为 `zhengxiang`（正向）；`1.5° < |offset| <= 4.5°` 为 `jianxiang_lower`（小兼向，仍在中央 9°）；`> 4.5°` 为 `jianxiang_replacement`（大兼向，进入外侧 3°）。距山界 `7.5 - |offset| <= 0.5°` 标记空亡：`da_kongwang`（跨八宫边界大空亡）、`yinyang_chacuo`（同宫异阴阳差错）或 `xiao_kongwang`（同宫同阴阳小空亡），并附 `adjacent_mountain` 与 `kongwang_seam_degrees`。
- **玄空候选枚举**：玄空限制误差半径在 `0°–7.5°` 内，枚举闭区间触及的每段 24 山子区并按 `(mountain, chart_mode)` 去重；存在多候选时 `chart=null`、`status="partial"`，逐候选保留 `bearing_support.regions` 与 `mode_reasons`。

## 3. 立春换年与十二节换月边界

年星、命卦（默认）与玄空定运以**立春**（地心太阳视黄经 315° 瞬间）换年，不以春节、2 月 4 日午夜或真太阳时替代；命卦另可选 `year_boundary="january_1"`，显式传入有效年则表示调用方已确认边界归属。月紫白严格按**十二节**（立春 1 寅月至小寒 12 丑月）换月，中气不换月。

解读时间结果时需逐项核对 `time_context`：

1. **有效区间与钟时标签**：区间采用前闭后开（`interval_policy="start_inclusive_end_exclusive"`），起止由 `valid_from` 与 `valid_until` 给出。若当地钟面在该瞬间未定义（如历史无明确偏移时段），结果保留 `local_moment=null`、`local_clock_status="undefined"` 与 `utc_moment`，`january_1` 边界下 `effective_year` 置 `null` 并标 `requires_confirmation`。
2. **求解模型与时标政策**：`timing.start_resolution` 与 `end_resolution` 记录 `provider`、`ephemeris_model` 及 `time_basis`（TT 动力学根、`civil_policy`、1972 年前历史 UT1/ΔT 约定、`future_leap_seconds_assumed_unchanged` 及冻结闰秒表到期日）。默认打包 DE440 覆盖 1800–2200 年，历史端点由 `fatebridge_de440_solar_historical_v1` 补足 1784–2204 年。若选定模型无法求解交点则直接报错，不使用线性近似回退。
3. **5 秒数值边界保护**：`MOSHIER_BOUNDARY_GUARD_SECONDS = 5.0` 为工程候选保护窗口（不是误差上界或精度认证）。当查询或事件时刻落在交节前后 5 秒保护区内时，输出 `effective_year_status="requires_confirmation"` 或 `month_status="requires_confirmation"`，主字段 `effective_year` / `solar_month_number` 置为 `null`，同时提供 `provisional_*` 追踪字段与 `candidate_year_intervals` / `candidate_months`。仅有 `birth_date` 且交节在当地民用日或保护区跨日时，命卦亦标记 `requires_confirmation` 而绝不编造出生小时。
4. **玄空定运跨界处理**：历史事件年落在跨 20 年大运的立春保护区时，`period_context.resolution_status="requires_confirmation"` 并给出 `candidate_period_intervals`；若两个候选有效年仍属同一大运，可确定 `period_number` 而仅保留事件年待确认注记。

## 4. 分层结构、四层叠盘、布局解读与来源交付

### 4.1 顶层结构与 `status` / `coverage` / `conflicts`

所有 8 个工具共用同一响应信封（`layers`、`rulesets`、`source_catalog`、`coverage`、`conflicts`、`rule_trace`、`summary`），`fengshui_assess` 额外可包含 `palace_overlay` 与 `layout_analysis`：

- **`status` 与 `coverage`**：`status="partial"` 仅表示部分图层或请求项缺少必要输入（详见 `coverage.missing_inputs` 与各层 `missing_inputs`），**不代表**已完整计算的图层失效。合参结果须同时检查 `coverage.implemented_layers`、`not_requested_layers`、`unavailable_layers`（如当前未涵盖的 `jinsuo_forms_and_periods`、`automatic_floorplan_geometry`），以及 `requested_analysis_status`、`natal_interpretation_status` 与 `city_gate_status`。
- **`conflicts`（多主体八宅差异）**：`fengshui_bazhai` 与 `fengshui_assess` 在存在多个已完成（`status="complete"`）的宅盘与住户命盘时，自动比对八方星性极性并列出 `house_person_scope_difference` 与 `personal_direction_difference`（注：`fengshui_assess` 的 `detail=compact` 视图会裁剪 `conflicts`，读取完整差异需使用 `detail=audit` 且 `fields=null`）。绝不能将宅卦、命卦、年星、月星或金锁偏好折算为单一总分或多数票。

### 4.2 四层 `palace_overlay` 与 `layout_analysis` 读法

- **九宫叠盘 `palace_overlay`**：当 `fengshui_assess` 包含至少一层飞星数据时返回，按 `flight_path` 覆盖 `C, NW, W, NE, S, N, SW, E, SE` 九宫，逐宫并列 `natal_period_star`、`natal_mountain_star`、`natal_facing_star`、`annual_star`、`monthly_star`、`daily_star`、`hourly_star`（其中日、时紫白在启用 `monthly_stars` 且传 `query_at` 与 `include_daily_hourly=true` 时同步生成）。解释时必须区分固定洛书宫数、宅盘运/山/向星与流年/流月/流日/流时飞星，不可混用五行或跨层覆写。
- **布局分析 `layout_analysis`**：由 `analyze_layout=true` 启用，包含四项结构化输出：
  - `placement_findings`：逐对象按已选层列出评估结果——八宅分别评估 `aspect="location"` 与 `aspect="facing"`（对照传统用途星性偏好 `matches_convention`）；年星、月星与玄空本命盘仅评估已确认的 `location_direction`（`aspect="location"`），朝向不能代替落宫位置。
  - `adjustment_options`：针对八宅计算各已确认/候选作用域的 `matching_directions`，并仅对**已确认作用域**求交集得到 `agreed_matching_directions`。
  - `environment_adjustments`：透传金锁 `feature_findings` 与 `target_classification`。
  - `element_relationships`：按各层实际落宫星五行给出 `same_element`、`generating_element`、`draining_element`、`controlling_element`、`controlled_element`，仅用于结构说明，不生成物品、颜色或风水处方。

### 4.3 默认视图与必须交付的来源字段

按[输出控制与结果读取](../../agent-guide.md#输出控制与结果读取)，单层工具默认 `evidence_views` 投影为 `status layers rulesets coverage rule_trace`，`fengshui_assess` 默认投影为 `status rulesets coverage rule_trace`；且 `detail=compact` 会将 `rulesets` 裁剪为 `{ruleset_id, version, method, source_ids}`、将 `source_catalog` 裁剪为 `{source_id: {title}}`。

向用户正式解释或交付依据时，若需完整作者、版本、链接与典籍页码定位，必须使用 `detail=audit` 且 `fields=null`（或按需投影 `source_catalog`、`rulesets`、`rule_trace`），并如实交代：

1. **规则与版本**：`rulesets[]` 中的 `ruleset_id`、`version`、`method`、`scope` 与 `conventions`（以及 `rule_trace` 对应的方法映射）。
2. **典籍与作者来源**：`source_catalog[source_id]` 中的 `title`、`author`、`edition`、`isbn`、`url`、`kind`，以及 `rulesets[].source_citations[source_id]` 中的 `locator`、`pages`、`source_version`、`scope`、`boundary` 与 `source_disagreements`。
3. **版本限度声明**：网络转录或特定作者资料仅代表该登记版本在 `scope` 内的依据，不能外推为整部古籍校勘定本或全门派统一结论，更不构成现实预测效力保证。
