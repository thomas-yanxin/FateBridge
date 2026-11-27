# 中州派玄空宅盘规则与可选条件解读

[现场资料与解读](consultation.md) · [基础规则与来源](rule-sources.md) · [家居风水参考](../../fengshui.md) · [示例索引](../../examples/README.md)

本文档说明 `fengshui_xuankong_house_chart`（及 `fengshui_assess` 的 `xuankong_natal` 图层）所实现的中州派历史宅盘起盘规则，以及 5 个显式启用的可选条件解读规则集。历史宅盘依定运事件固定，不随查询年份或流年飞星自动换运。

## 1. 玄空规则集清单

| 规则 ID（`ruleset_id`） | 版本 | 启用路径 | 核心覆盖 | 登记来源 ID |
| --- | --- | --- | --- | --- |
| `xuankong_zhongzhou_v1` | `1.4.0` | 默认基础宅盘 | 历史定运、磁北下卦/13 山替星、五黄借运、经典结构与对宫比较 | `X1`–`X12`, `S7`, `S8`, `S9` |
| `xuankong_conditioned_v1` | `1.0.0` | `interpretation` | 山向星有序五行、显式评价时运、全宅八方外局存在与床/门落宫 | `N1`, `N2`, `N3`, `N4`, `E1` |
| `wang_zhongzhou_timeliness_v1` | `1.1.0` | `interpretation.timeliness_ruleset_id` | 王亭之上卷基本时令（旺生衰死）与先后天互用数字及图位 | `WZT1` |
| `shen_city_gate_v1` | `1.0.0` | `city_gate` | 向首邻宫同元龙正/副城门数字推导与水形存在条件 | `G1`, `G2` |
| `shen_fixed_lingzheng_v1` | `1.0.0` | `interpretation.fixed_lingzheng` | 《沈氏玄空学》卷一固定正零方位、五运前后十年寄宫与高实/低洼河流条件 | `SFL1`, `SFL2`, `SFL3` |
| `shen_2011_host_guest_v1` | `1.0.0` | `interpretation.host_guest_ruleset_id` | 沈氏整理本坐山宫与向首宫四组盘层主客生克出入 | `HGT1`, `HGT2`, `HGT3`, `HGT4` |

## 2. 历史宅盘起盘规则（`xuankong_zhongzhou_v1@1.4.0`）

### 2.1 来源核对与版次限制

本版采用已登记网络文献与影印资料交叉锁定的中州派规则，不宣称为全部玄空流派统一法，也不代表《沈氏玄空学》整册校勘本：

- **基础与传法文献**：`X1`（《沈氏玄空学》卷四网络转录：24 山、三元龙与 1864 锚点）、`X2`（玄霖易学《第一篇 玄空基础 2》：下卦/替卦 9°+3°+3°、五黄借运同元龙与 13 山替星例）、`X3`（AFSI 2005 教材 pp.8–9：交叉核对五黄借建造运同元龙阴阳）、`X4`（陈癸龙《大厦元运及换天心》：普通装修不自动换运）、`X5`（《沈氏玄空学》卷二：分金寄宫与外宫五黄入中区分）。
- **天文与交节核对**：`S7`（Sean Chan 2026）、`S8`（香港天文台 2026 年历）、`X6`（香港天文学会 2024-02-04 立春 16:27 分钟对照）、`S9`（香港天文台二十四节气官方 XML）。
- **影印与原书数字核对**：`X7`（《沈氏玄空学》下册影印 PDF 45/46/50 页逐像核对四运卯酉、一运酉卯、六运巽乾顺逆）、`X8`（上册卷一论起星影印 PDF 45–52 页 24 山替星口诀）、`X9`（王亭之《中州派玄空学》上卷 PDF 23–27 页）、`X10`（卷二影印 PDF 7–8 页论反吟伏吟）、`X11`（卷一影印 PDF 66/71 页父母三般卦）、`X12`（王亭之上卷 PDF 43 页山向对角合十数式）。
- **已校订的文献笔误与差异**：`X2` 网页存在“阳阳互兼用替”及十一山清单与紧接图例自相矛盾的笔误，引擎以 13 山替星口诀及完整 24 山补集（11 同数山）校订，并在 `validate_replacement_catalog` 强制校验 24 山完备性；`X5` 所载不同五黄寄宫法不混入外宫五黄入中。

### 2.2 历史定运与磁北输入

- **定运输入（`period`）**：须含 `basis`（`construction_completion` \| `first_occupancy` \| `confirmed_major_renovation` \| `expert_confirmed`）、非空白 `evidence`，以及 `period_number`（1–9）、`effective_event_year`（1800–2199）或含时区 `event_at`（1801–2199）三者之一。`expert_confirmed` 须显式传入 `period_number`；`confirmed_major_renovation` 须显式确认 `qualifies_for_period_reset=true`（算法本身不鉴定建筑大修资格）。粉刷装修或查询年份跨入新运不会自动改写宅盘。
- **交节与换运边界**：`1864` 年为一运锚点，每运 20 年、九运 180 年循环（2024–2043 为九运）。事件时刻按立春交节；落在跨运年份立春 5 秒保护区内时，`period_context.resolution_status="requires_confirmation"` 并保留 `candidate_period_intervals`，若两候选年同属一运则仍可定运并保留年份待确认注记。
- **磁北与不确定度**：`house` 传入 `facing_degrees` 时必须 `north_reference="magnetic"`（真北输入直接校验拒绝）；`bearing_uncertainty_degrees` 限 `0°–7.5°`，按精确有理数闭区间分段枚举并按 `(mountain, chart_mode)` 去重，保留 `bearing_support.regions` 与 `mode_reasons`。多候选时 `chart=null`、`status="partial"`。

### 2.3 下卦、兼向替星与五黄规则

每山 15°，以山中心为基准，正中 9°（`|offset| < 4.5°`，按 `xuankong.py` `central_half_width_degrees`）一律用**下卦**（`lower`）；外侧各 3° 若相邻山与本山**同宫且同阴阳**（如子山兼癸、同属坎宫阴），仍用下卦（`same_palace_same_polarity_no_replacement`）；若**异阴阳或跨宫出卦**（如子山兼壬、虽同属坎宫但一阴一阳），则启用**替卦**（`replacement`）。

起星与替星顺序：先在运盘查出坐山/向首所在宫的原运星，再在该运星所属固定洛书宫中找出与物理山/向**同元龙**的山位定其阴阳顺逆（阳顺阴逆）；若为 `replacement` 模式，再取该映射山的替星入中飞布，**替星不重新决定阴阳顺逆**。

| 原运星（宫） | 地元龙 | 天元龙 | 人元龙 | 十三改数替星（其余 11 山保留原星数） |
| ---: | --- | --- | --- | --- |
| `1`（坎） | 壬（阳） | 子（阴） | 癸（阴） | **壬→2**（子、癸仍 1） |
| `2`（坤） | 未（阴） | 坤（阳） | 申（阳） | **申→1**（未、坤仍 2） |
| `3`（震） | 甲（阳） | 卯（阴） | 乙（阴） | **甲→1，卯→2，乙→2** |
| `4`（巽） | 辰（阴） | 巽（阳） | 巳（阳） | **辰→6，巽→6，巳→6** |
| `6`（乾） | 戌（阴） | 乾（阳） | 亥（阳） | 戌、乾、亥均保留 6 |
| `7`（兑） | 庚（阳） | 酉（阴） | 辛（阴） | **庚→9**（酉、辛仍 7） |
| `8`（艮） | 丑（阴） | 艮（阳） | 寅（阳） | **丑→7，艮→7，寅→9** |
| `9`（离） | 丙（阳） | 午（阴） | 丁（阴） | **丙→7**（午、丁仍 9） |

**五黄规则**：五黄（`seed == 5`）入中时，借当前宅运 `period` 所属宫中与物理山/向同元龙的阴阳决定顺逆，仍以 `5` 入中飞布且**永不替星**（`five_yellow_kept_without_replacement=true`）。五运元旦盘 5 在中宫、外宫星数不可能为 5，不引入五运十年寄宫规则。

### 2.4 经典结构识别（`structure`）

每个确定盘与候选盘均附 `structure`（同时输出本命宅运与可选 `current_period_number` 评价运的结果）：

- **`distribution` / `eval_period_distribution`**：识别当令星落位为 `到山到向`、`上山下水`、`双星到坐`、`双星到向` 或 `其他星位结构`。
- **`lingxing_ruqiu` / `eval_lingxing_ruqiu`**：令星入囚，检查山星或向星的当令数是否飞入中宫（`C`）。
- **`combination_of_ten` 与 `opposite_star_comparison`**：分别计算全九宫运山、运向、山向同宫合十，以及外八宫山星与对宫向星之和等于 10 的方向（中宫数和单独列示，出自 `X12`）。
- **`parental_triples`、`lianzhu_triples` 与 `qixing_dajie`**：`parental_triples` 检查九宫每宫三数是否均为 `(1,4,7)`、`(2,5,8)` 或 `(3,6,9)`；`lianzhu_triples` 检查九宫每宫是否为互异连续三数（含环绕如 8-9-1、9-1-2）；`qixing_dajie` 在全盘满足父母三般卦前提下，检查离宫三般（`S, E, NW`）或坎宫三般（`N, SE, W`）是否且运/山/向各角色分别遍历该组三数。
- **`ground_comparison` 与 `volume_two_named_refrain`**：记录山盘、向盘各宫与固定洛书地盘同数（伏吟）或相加为十（反吟）数式；`volume_two_named_refrain` 仅在 `chart_mode="lower"`（下卦）时给出卷二所列举局名数式匹配，兼向保留数式但不自动套用下卦局名。

## 3. 可选条件解读层（`xuankong_conditioned_v1@1.0.0`）

通过 `interpretation` 显式启用，仅读取已有宅盘而不修改 `xuankong_zhongzhou_v1` 起盘结果。登记来源为 `N1`（玄霖易学理气入门 3）、`N2`/`N3`（Kartar Diamond 作者文章，不采用其 2044 九运端点）、`N4`（AFSI FS351 第 56 页九星五行）与 `E1`（AFSI *The Principles of Feng Shui* Ch.3 印刷 23、25 页有向五行生克）。

- **有序山向五行关系（`ordered_pair`）**：按 `1` 水、`2/5/8` 土、`3/4` 木、`6/7` 金、`9` 火映射（五黄保持土），输出 `same_element`、`mountain_generates_facing`、`facing_generates_mountain`、`mountain_controls_facing`、`facing_controls_mountain`。山与向有序不可互换，本版**不包含** 81 组合断语、合十吉凶或疾病/求子断言。
- **评价时运（`current_period_number` + `period_evidence`）**：必须成对显式提供，不从宅运、年星或系统日期暗补。基础层仅标 `current`（星数等于评价运）与 `not_current`（非当令，不等于凶星）。
- **外局存在条件（`external_forms`）**：以全宅为中心按外八方记录 `mountain_present`、`water_present`、`observation_basis`、`evidence`（中宫 `C` 标为 `not_applicable_center`）。当令山星检查该宫 `mountain_present`，当令向星检查该宫 `water_present`；非当令星标为 `rule_not_covered_not_inauspicious`。无山不推有水、无水不推有山；`image_observed` 保持 `candidate_only` 并记入 `missing_inputs`；存在只表示必要条件，不等于山水形态、距离或纳气合格。
- **室内用途检查（`placement_findings`）**：读取 `placements` 中的位置（`location_direction`），仅覆盖 **`bed`（取该宫山星配山）与 `door`（取该宫向星配水）**；`desk` 与 `stove` 明确标为 `status="unsupported"`。

## 4. 王亭之时令与先后天互用（`wang_zhongzhou_timeliness_v1@1.1.0`）

在 `interpretation` 中传入 `timeliness_ruleset_id="wang_zhongzhou_timeliness_v1"` 时附加在每宫 `timeliness.*.author_classification` 中。来源为 `WZT1`（王亭之《中州派玄空学（上卷）》第十六节“九星生旺衰死”，印刷 16–17 页／PDF 18–19 页）。

- **基本时令相位**：按 `(star_number - current_period) % 9` 分类：`0` 为 `prosperous`（旺）、`1/2` 为 `growing`（生）、`7/8` 为 `declining`（衰）、`3/4/5/6` 为 `dormant`（死）。“死”是古籍时令术语而非人的生死，不得仅据基本时令否定某房间。
- **先后天互用参考（`mutual_use_reference`）**：同时列示原书互用数表 `printed_period_numbers`（1→`[1,2,7]`、2→`[2,1,4]`、3→`[3,8,9]`、4→`[4,2,7]`、5→`[5,2,8]`、6→`[6,8,9]`、7→`[7,1,4]`、8→`[8,3,6]`、9→`[9,3,6]`）与图位几何推导 `diagram_derived_numbers`（先天八卦与后天八卦同方位叠合对应；5 运无第五卦图位，标为 `literal_table_only_no_fifth_trigram`）。保留原书七运表列 `[7,8,9]` 与紧邻正文仅写 `[7,8]` 可用的文献差异 `WZT1-P17-SEVEN`，不做自动裁决。

## 5. 沈氏正副城门（`shen_city_gate_v1@1.0.0`）

通过 `city_gate`（独立调用或 `xuankong.city_gate`）启用，输出 `city_gate_analysis`。来源为 `G1`（《增广沈氏玄空学》卷一历史影印 PDF 57–60 页）与 `G2`（2011 中央编译重印本 PDF 90–94、128 页）。

- **输入与规则**：须提供 `reference_period_number`（1–9）与非空白 `period_evidence`（与历史宅运、年星独立），以及可选 `observations`（24 山观察）。
- **数理与门类判定**：取向首相邻左右两宫中与向首**同元龙**的山位；以 `reference_period_number` 运盘该邻宫星数入中（若为 5 则借参考运同元龙阴阳），排布九宫并判断当“逆飞且飞回该城门宫恰等于参考运数”时标记 `usable=true`。同时按向首宫与城门宫固定洛书数是否构成河图生成对（`[1,6]`、`[2,7]`、`[3,8]`、`[4,9]`）区分 `primary`（正城门）与 `secondary`（副城门）；不跨语境对正马/借马统一排名。
- **水形条件**：仅在显式提供对应 24 山观察时核对 `encircled_sole_water_opening`（环抱＋唯一水口）或 `reflecting_three_way_water`（有水＋三叉水口＋水光返照＋非多缺口）；`image_observed` 保持 `candidate_only`。

## 6. 沈氏固定零正与五运分段（`shen_fixed_lingzheng_v1@1.0.0`）

在 `interpretation.fixed_lingzheng` 中显式启用，输出 `fixed_lingzheng_analysis`。来源为 `SFL1`（沈竹礽正文，卷一论阴阳零正）、`SFL2`（志伊谨案）与 `SFL3`（王则先谨按）。固定地盘零正与山向飞星分别列示，不覆盖飞星当令要求。

- **方位规则**：当评价运 `current_period_number != 5` 时，`zheng_direction` 为 `current` 对应固定洛书宫，`ling_direction` 为 `10 - current` 对应固定洛书宫。当 `current == 5` 时，前十年 `first_decade` 五黄寄坤二为正、零神在艮八，后十年 `second_decade` 五黄寄艮八为正、零神在坤二；未传入 `five_period_half`（须与 `half_evidence` 成对）时保留两套候选并标 `status="partial"`。
- **观察条件**：正神宫核对 `high_solid_terrain_present`（高实山地），零神宫须同时核对 `low_lying_terrain_present` 与 `river_water_present`（低洼与河流）。无山不推低洼、无水不推高实；`image_observed` 保持 `candidate_only`。

## 7. 沈氏主客生克出入（`shen_2011_host_guest_v1@1.0.0`）

在 `interpretation` 中传入 `host_guest_ruleset_id="shen_2011_host_guest_v1"` 时输出 `host_guest_analysis`。来源为 `HGT1`（《沈氏玄空学》整理本所收未署作者《地理精纂·生克吉凶篇》）、`HGT2`（卷四王则先谨按）、`HGT3`（卷四江志伊录九宫挨星掌诀）与 `HGT4`（所收姚廷銮本《紫白诀》上篇五行）。

- **计算范围**：仅对每候选盘的**坐山宫**（以山星为 `active_role`）与**向首宫**（以向星为 `active_role`）各计算四组机械盘层关系：`earth_period`（地运：固定地盘 `earth` 为主、运星 `period` 为客）、`period_mountain`（运山：`period` 为主、`mountain` 为客）、`period_facing`（运向：`period` 为主、`facing` 为客）、`axis_pair`（坐山宫取 `mountain` 为主/`facing` 为客；向首宫取 `facing` 为主/`mountain` 为客）。
- **输出与限制**：按九星五行给出 `比和`（`same_element`）、`生入`（`guest_generates_host`）、`克入`（`guest_controls_host`）、`生出`（`host_generates_guest`）或 `克出`（`host_controls_guest`）。五黄保持土；旁六宫与中宫不赋予此主客规则，主客生入不等于时令生气，也不合成 81 组合吉凶断语。
