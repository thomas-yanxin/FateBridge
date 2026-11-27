# 家居风水计算参考

[文档中心](README.md) · [API 参考](api-reference.md) · [可运行示例](examples/README.md) · [现场咨询指南](interpretation/fengshui/consultation.md) · [基础规则与来源](interpretation/fengshui/rule-sources.md) · [玄空参考](interpretation/fengshui/xuankong.md)

FateBridge 的 `fengshui` family 提供 8 个确定性、带规则与来源追溯的风水计算工具，覆盖后天方位与地磁换算、命卦、八宅与阳宅三要、金锁玉关砂水、年/月/日/时紫白、中州派玄空宅盘以及多层合参评估。引擎只产出结构化计算事实与条件匹配状态，不生成摆件处方、颜色建议或吉凶断言。

## 8 个工具速查

| 工具名（MCP / CLI） | REST 路由（`POST`） | 核心输入 | 核心输出层（`layers.*`） | 适用场景 |
| --- | --- | --- | --- | --- |
| `fengshui_directions` | `/api/fengshui/directions` | `bearing_degrees`、`north_reference`、可选 `geomagnetic_reference` | `directions` | 八方与 24 山角区索引、兼向/空亡识别、WMM2025/IGRF-14 磁偏角换算候选 |
| `fengshui_minggua` | `/api/fengshui/minggua` | `birth_date` / `birth_at` / `effective_birth_year`、`gender_convention`、`year_boundary` | `minggua` | 单人 1864 锚点命卦、东西四命及个人八方游年关系 |
| `fengshui_bazhai` | `/api/fengshui/bazhai` | `house`、`occupants`、`placements` | `bazhai`（及 `conflicts`） | 坐山宅盘、逐人命盘、门床桌灶位置/朝向校验及阳宅三要（门/主/灶） |
| `fengshui_jinsuo` | `/api/fengshui/jinsuo` | `features`（`object_id`、`direction`/`mountain`、`classification`、`classification_basis`、`evidence`） | `jinsuo` | 金锁玉关八宫（1234 砂 / 6789 水）与 24 山砂水偏好逐项核对 |
| `fengshui_annual_stars` | `/api/fengshui/annual-stars` | `effective_year` 或 `query_at`、`timezone_name` | `annual_stars` | 立春换年九宫紫白飞星、二十年元运及太岁/岁破/三煞/五黄/二黑 |
| `fengshui_monthly_stars` | `/api/fengshui/monthly-stars` | `query_at` 或成对 `effective_solar_year` + `solar_month_number`、`include_daily_hourly` | `monthly_stars` | 十二节换月中性月紫白；传入 `query_at` 时默认同步计算日紫白与时紫白 |
| `fengshui_xuankong_house_chart` | `/api/fengshui/xuankong-house-chart` | `house`（磁北 `facing_degrees`）、`period`、可选 `current_period_number`、`city_gate`、`interpretation` | `xuankong_natal` | 中州派历史定运、下卦/13 山替星宅盘、古典格局、城门与条件式解读 |
| `fengshui_assess` | `/api/fengshui/assess` | `methods`（或由请求字段推断）、各层参数及可选 `analyze_layout=true` | 所选各层 + `palace_overlay` + `layout_analysis` | 多层合参主入口，支持四层紫白与宅盘叠宫及门床桌灶跨层布局评估 |

## 统一响应结构

8 个工具共用同一顶层结构（`AssessOutput` / `BaseFengshuiOutput`），默认 `detail=compact` 返回精简视图，需要完整宫位、时间边界、岁煞或来源引文明细时传入 `detail=audit`：

| 顶层字段 | 含义与读取约定 |
| --- | --- |
| `status` | `"complete"` 或 `"partial"`；任一已请求层存在 `missing_inputs` 即为 `"partial"`，仅限制对应层或未定分支，不否定其余已算层 |
| `layers` | 按请求方法挂载各层计算结果（`directions`、`minggua`、`bazhai`、`jinsuo`、`annual_stars`、`monthly_stars`、`xuankong_natal`） |
| `palace_overlay` | 仅 `fengshui_assess` 包含宅盘或年/月/日/时紫白任一层时生成，按 `C` 与八方叠加 `natal_period_star`、`natal_mountain_star`、`natal_facing_star`、`annual_star`、`monthly_star`、`daily_star`、`hourly_star` |
| `layout_analysis` | 仅 `fengshui_assess` 传入 `analyze_layout=true` 时生成，包含 `status`、`calculation_scope`、`placement_findings`、`adjustment_options`、`environment_adjustments`、`element_relationships`、`missing_inputs` |
| `coverage` | 报告 `implemented_layers`、`missing_inputs`、`unavailable_layers`、`not_requested_layers`；启用布局、城门或玄空解读时附带 `requested_analysis_status` 等子状态 |
| `conflicts` | `fengshui_bazhai` 与 `fengshui_assess` 返回坐山与命卦、或住户之间的同方位吉凶极性差异（`detail=compact` 下的 `fengshui_assess` 默认省略，传 `detail=audit` 或 `--fields conflicts` 读取） |
| `rulesets` / `source_catalog` / `rule_trace` | 分别登记本次命中的规则集元数据（ID、版本、方法、来源 ID）、去重后的书目详情与按方法对齐的审计追踪链 |

## 关键规则与坐标系约定

### 方位、24 山兼向空亡与地磁换算

- **角区划分**：以 `0°` 正北顺时针计量，采用左闭右开区间（`left_closed_right_open`）；八方每宫宽 `45°`（半宽 `22.5°`），24 山每山宽 `15°`（半宽 `7.5°`）。
- **兼向与空亡**：距山心 `|Δ| ≤ 1.5°` 为正向（`zhengxiang`）；`1.5° < |Δ| ≤ 4.5°` 为下卦兼向（`jianxiang_lower`）；`|Δ| > 4.5°` 为替卦区（`jianxiang_replacement`）。距山界 `≤ 0.5°`（`7.5° - |Δ| ≤ 0.5°`）标记空亡：`da_kongwang`（跨八宫）、`yinyang_chacuo`（同宫异阴阳）或 `xiao_kongwang`（同宫同阴阳）。
- **WMM2025 / IGRF-14 地磁参考**：通过 `geomagnetic_reference` 传入 WGS84 坐标与日期（`model_date` 或 `decimal_year` 二选一）。`model_id="auto"` 在 `[2025.0, 2030.0)` 选用 12 阶 `wmm2025_v1`，在 `[1900.0, 2030.0]` 其余年份选用 13 阶 `igrf14_v1`。系统按 `true = magnetic + east_positive_D (mod 360)` 给出换算候选并保留原始角度，绝不自动改写宅向；地理极点或水平磁场 `< 2000 nT` 的地磁盲区返回 `unavailable`。

### 历法边界、八宅与金锁玉关

- **立春与十二节月界**：`annual_stars`、默认 `minggua`（可选 `january_1`）及玄空定运以 `1864` 年为一运锚点，每 `20` 年一运，按立春交节换年；`monthly_stars` 以立春换年支、十二个「节」（1=立春寅月至 12=次年小寒丑月）换月。交节前后 `5` 秒（Moshier 数值保护窗口）或无确定时刻的边界日期保留候选，不擅自裁定唯一年份或节月。
- **八宅与阳宅三要**：命卦按 `1 - (year - 1864)`（男）与 `5 + (year - 1864)`（女）模 9 取数，五黄男寄坤 2、女寄艮 8；按 `8×8` 八卦变爻计算大游年八星与宫星五行生克。`placements` 严格区分落宫（`location_direction`）与朝向（`facing_direction` + `facing_role`），约定 `stove` 落宫（`location`）偏凶、火门（`fire_mouth`）及门/床/桌其余位置与朝向偏吉；提供门/床/灶落宫时同时输出《阳宅三要》门主灶卦组关系与东西四宅一致性（`yangzhai_sanyao`）。
- **金锁玉关**：固定洛书 `1, 2, 3, 4` 宫（坎/坤/震/巽所属 12 山）喜砂（`sand`），`6, 7, 8, 9` 宫（乾/兑/艮/离所属 12 山）喜水（`water`）。支持八宫 `direction` 或精确 24 山 `mountain`（二者同传须一致）；`mixed` 与 `unknown` 保持 `undetermined`，不从名称猜测砂水。

### 紫白四层与中州派玄空

- **紫白年/月/日/时四层**：年紫白按 `1 - (year - 1864)` 模 9 入中顺飞，并在 `detail=audit` 下返回 `annual_afflictions`（太岁、岁破、三煞、五黄、二黑）；月紫白按年支三组（子午卯酉起 8、辰戌丑未起 5、寅申巳亥起 2）逐节月逆推入中顺飞。传入 `query_at` 且 `include_daily_hourly=true`（默认）时，同步按《紫白诀》冬至/雨水/谷雨（阳遁顺行 1/7/4）与夏至/处暑/霜降（阴遁逆行 9/3/6）六段计算日紫白，并按日支三组结合阴阳遁计算时紫白。
- **中州玄空与条件解读**：`xuankong_zhongzhou_v1` 要求磁北宅向（`north_reference="magnetic"`，误差半径 `bearing_uncertainty_degrees ≤ 7.5`）与显式定运证据（`construction_completion`、`first_occupancy`、`confirmed_major_renovation` 须同时 `qualifies_for_period_reset=true` 或 `expert_confirmed` 须提供 `period_number`）。每山正中 `9°`（`|Δ| < 4.5°`）或两侧 `3°` 同宫同阴阳用下卦（`lower`），跨宫或异阴阳用 13 山替星（`replacement`）；五黄借宅运同元龙阴阳飞布而不替。宅盘附带到山到向/上山下水/双星分布、令星入囚、父母三般卦、连珠三般卦、离/坎七星打劫及反吟伏吟数式；可选启用 `city_gate`（`shen_city_gate_v1` 正/副城门与水形）及 `interpretation`（`xuankong_conditioned_v1`、`wang_zhongzhou_timeliness_v1`、`shen_fixed_lingzheng_v1`、`shen_2011_host_guest_v1`）。

## 可运行请求示例

### 示例 1：方位判定与 WMM2025 地磁换算候选（CLI）

```bash
uv run --extra dev fatebridge fengshui_directions \
  --bearing-degrees 180 \
  --north-reference magnetic \
  --geomagnetic-reference '{"latitude":39.9042,"longitude":116.4074,"height_km_wgs84":0.05,"model_date":"2026-06-01","evidence":"北京示例坐标"}' \
  --detail compact
```

### 示例 2：十二节月紫白与同日时紫白（CLI & REST）

```bash
uv run --extra dev fatebridge fengshui_monthly_stars \
  --query-at 2026-04-06T10:30:00+08:00 \
  --detail compact
```

```bash
curl -sS -X POST 'http://localhost:8010/api/fengshui/monthly-stars?detail=compact' \
  -H 'Content-Type: application/json' \
  -d '{"query_at":"2026-04-06T10:30:00+08:00","timezone_name":"Asia/Shanghai","include_daily_hourly":true}'
```

### 示例 3：中州玄空宅盘与多层住宅合参（CLI）

```bash
uv run --extra dev fatebridge fengshui_xuankong_house_chart \
  --request-file docs/examples/fengshui-xuankong.json \
  --detail compact

uv run --extra dev fatebridge fengshui_assess \
  --request-file docs/examples/fengshui-home.json \
  --analyze-layout true \
  --fields status layers palace_overlay layout_analysis coverage rulesets rule_trace \
  --detail audit
```
