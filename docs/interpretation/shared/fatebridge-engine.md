# FateBridge 引擎调用参考

本页是 Agent 调用 FateBridge 引擎、读取结构化字段与处理错误的速查手册。咨询边界与范围见[硬边界](safety-boundaries.md)与[咨询核心](consultation-core.md)，时间层选择见[时间选择](timing-selection.md)，核心概念见[核心概念](../../concepts.md)。

**铁律**：全部排盘、干支、十神、运限、神煞、星历坐标、卦局与风水位次都交给 FateBridge 引擎计算，AI 不手算。普通摘要沿用默认核心层（被省略的可选重型路径记入 `run_metadata.omitted_fields`）或按工具发布的 `evidence_views` 传入 `fields` / `include`；需要无损完整 JSON 或全部时间线时，首次即传 `include=["*"]`（省略 `fields`）。

[调用与错误](#怎么调引擎) · [参数与首轮字段](#共用参数与输出读取) · [常用工具](#常用工具速查) · [家居风水](#家居风水基础计算) · [调用样例](#典型调用样例) · [跨体系原则](#跨体系与复用原则)

## 怎么调引擎

已连接 FateBridge MCP 时直接按公开工具定义调用，不先跑安装诊断或翻仓库历史；CLI 是无连接时的本地后备与可复核示例。三端控制面与通道细节见[接入指南](../../agent-guide.md#按通道接入)和[API 参考](../../api-reference.md#22-三端能力边界)。

- **发现与调用**：MCP 公开 `discover_tools`、`run_calculation` 与 `run_batch`（0 资源 URI）。查参先用 `discover_tools(tool=能力名)`；`detail="full"` 须带 `tool`/`family`/`q` 过滤，且 **`output_schema` 仅在显式传 `include_output_schema=True`（REST `?include_output_schema=true`，CLI `--include-output-schema`）时返回**。多工具或多对象共享同一人物资料时优先使用 `run_batch`（REST `POST /api/batch`、CLI `fatebridge batch --request-file ...`）。已取得合同不重复发现。
- **任务视图与严格投影**：部分工具发布按任务组织的 `evidence_views`（`discover` 可读）。先选卡再把其中的 `fields` 复制到请求；卡名与 `view` 不是请求参数。三端对 `fields` 始终严格校验点号对象路径（数组整体取字段，不传数字索引、不传逗号分隔），无效路径返回 `unknown_projection_path` 并在 `constraints.available` 列出可用键名。控制面细节见[输出控制与结果读取](../../agent-guide.md#输出控制与结果读取)。
- **本地环境与后备**：本地仓库先用 `uv sync --extra dev` 准备 `.venv`（macOS/Linux `source .venv/bin/activate`，Windows `.\.venv\Scripts\Activate.ps1`），步骤见[快速入门](../../getting-started.md#安装)。以下 `python3` 指激活环境中的解释器；`fatebridge <tool>` 与 `python3 -m fatebridge.cli <tool>` 等价。
- **常用 CLI 开关**：`--include INCLUDE [INCLUDE ...]`（按需展开路径、`evidence_views` 名称或 `"*"`）、`--fields KEY [KEY ...]`（与 `--include` 互斥）、`--as-of AS_OF`（冻结默认当前时钟以便复现）、`--request-file PATH`（全工具支持从 JSON 文件加载输入，显式参数覆盖顶层同名字段），以及 `fatebridge list` / `fatebridge discover [tool]`。
- **错误处理**：CLI 成功与失败均输出 stdout JSON；以 exit code ≠ 0 判错，先查 `isError`、`error_code`（如 `usage_error`、`unknown_tool`、`validation_error`、`dependency_missing`、`timeout`）与 `constraints` 再修正，**仅 `retryable=true` 才重试**。完整错误表见[错误恢复与复现](../../agent-guide.md#错误恢复与复现)及[故障排除](../../troubleshooting.md)。

## 共用参数与输出读取

出生时钟、分析时钟与 `as_of` 各自独立；下列示例资料均属虚构，不能当作用户真实资料。请求族明细见[共享请求族](../../api-reference.md#3-共享请求族)。

- **中式输入（八字 / 时运 / 紫微 / 六壬）**：使用公历 `birth_year/month/day/hour/minute`、`gender` 与可解析的 `birth_place`（或显式 `birth_longitude` / `birth_timezone`）；真太阳时默认开启，无需手抄示例坐标或硬套 `birth_latitude`。对必填小时的工具，未知生时不猜、不填 `0`，明确不知道后停止追问同项并交付可答部分。
- **西占输入（核心盘 / 关系盘 / 推运）**：核心盘可由支持的 `birth_place` 解析经纬度与时区；关系盘与西占推运须显式传 `birth_latitude` / `birth_longitude`，默认民用钟时（`use_true_solar_time=false`），统一使用 `--house-system` 与 `--zodiac-type`。聚合推运及 11 项单项技法的 `analysis_hour/minute` 按 `birth_timezone` 解释（省略沿用出生时分）；缺星历或推运后端时报错而不按低精度近似解读，见[星历数据与精度](../../getting-started.md#星历数据与精度)。

### 常用输出根与首轮字段

不跨工具混用路径前缀，严格按所调用工具自己的输出根投影（数组整体取字段，不传数字索引）：

| 工具 | 常用输出根 / 首轮字段 | 说明 |
| --- | --- | --- |
| `bazi_overview` | `four_pillars`, `day_master`, `ten_gods`, `structure_profile`, `element_distribution`, `favorable_elements`, `favorable_elements_status`, `avoid_elements`, `person_info` | 综合画像直接读根字段；格局另看 `structure_profile` 喜忌与调候 |
| `bazi_birth_chart` | `bazi_birth.four_pillars`, `bazi_birth.day_master` | 带 `bazi_birth.` 前缀，不与 `bazi_overview` 混用 |
| `bazi_<dim>`（九专项） | `<dim>_analysis.topic_facts`, `<dim>_analysis.timing_context` | 自动带大运流年触点；详细取证见[八字专题取证](bazi-topic-evidence.md) |
| `bazi_compatibility` | `natal_contexts`, `cross_chart_relations`, `directional_ten_gods`, `element_complementarity`, `day_pillar_synergy` | 无综合分或内置建议文案；另含 `element_relationship`, `nayin_comparison`, `cross_shensha` |
| `ziwei_birth_chart` | `ziwei_birth.ming_gong/shen_gong/palaces/sihua` | 核对出生处理加 `person_info`, `analysis_context` |
| `ziwei_timing` | `analysis_context`, `birth_context`, `ziwei_horoscope.interpretation_scope/nominal_age/calendar_rules/scopes` | `scopes` 整体取回，详见[紫微专题取证](ziwei-topic-evidence.md) |
| `astrology_chart` | `angles`, `chart_profile`, `planets`, `aspect_evidence`, `classical`, `person_info` | 深入读[西占主题参考](western-topic-evidence.md) |
| `relationship_chart` | `relationship_profile`, `summary`, `synastry_aspects`, `in_to_out_aspects`, `out_to_in_aspects`, `chart`, `inner`, `outer`, `marks_charts` | 按盘型选同名 `evidence_views`，见[关系盘读法](../xingpan/relationship-reading.md) |
| `sukuyo_compatibility` | `person1/2.natal_su27`, `person1_to_person2`, `person2_to_person1` | 有方向性；候选项与异文保留，见[宿曜取证](sukuyo-evidence.md) |

## 常用工具速查

当前 REST 公开 91 个工具（另提供 `/api/batch` 批处理入口），MCP 通过三个入口提供 91 项业务能力，目录共有 91 条记录，CLI 可执行 91 条。完整清单见[算法覆盖](../../algorithm-coverage.md)。

- **八字本命与九大专项**：综合画像一次调 `bazi_overview`（已含四柱、喜用与格局，不再重调 `bazi_birth_chart`）；仅需原始四柱才用 `bazi_birth_chart`。九大专项（`bazi_marriage`、`bazi_romance`、`bazi_career`、`bazi_wealth`、`bazi_health`、`bazi_children`、`bazi_education`、`bazi_personality`、`bazi_relatives`）接受 `analysis_year/month/day`，自动推算大运/流年并写入 `<dim>_analysis.timing_context`。
- **双人配合**：`bazi_compatibility` 输出根字段为 `relationship_type`、`person_info`、`natal_contexts`、`element_relationship`、`nayin_comparison`、`day_pillar_synergy`、`element_complementarity`、`cross_shensha`、`cross_chart_relations`、`directional_ten_gods`（无综合分或内置建议文案，须结合双方关系解读）。`sukuyo_compatibility` 按固定口径定 27 宿并区分双向（`person1_to_person2` 与 `person2_to_person1`），详见[宿曜与宿占取证](sukuyo-evidence.md)。
- **时运推命与西占推运**：全景优先用聚合 `bazi_timing` / `western_timing`，只在盯单一层级或单技法时调用颗粒工具（`bazi_luck_cycles/yearly/monthly/daily/hourly_timing`、`solar_term_timeline`、`solar_terms_for_year`、`lunar_calendar_time`；`solar_return`、`lunar_return`、`transit_chart`、`solar_arc`、`chart_for_year`、`profection`、`primary_directions`/`primary_directions_chart`、`zodiacal_releasing`、`firdaria`、`decennials` 等），不把年度信号细化为几月或吉日。事件盘与生命周期技法（`mundane_ingress_chart`、`planetary_returns`、`horary_chart`、`evaluate_election_time`、`harmonic_chart`、`planetary_ages` 等）按需先 `discover` 核对输入。
- **占卜与三式**：`meihua_time_cast`（必填起卦年月日时）、`liuyao`（手摇 `--coins` 或 `--gua-code`，对象列表 `lines` 用 REST/MCP）、`combine_four_gua`（固定组合非随机起卦）、`gua_lookup`、`qimen`、`taiyi`（年/月/日/时计见[太乙与三式](../zhanbu/taiyi-sanshi.md)）、`jinkou`、`liuren_chart`、`liuren_yearly_timing`、`suzhan`（区分历日 27 宿与物理天文 28 宿，不将相反条文挑边合成或将 `not_computed` 写成已验吉）、`interpret_astrology_dice`（只解读用户已给骰面，不代抽）、`sanshi_combined_chart`。
- **紫微、占星与知识**：紫微有 `ziwei_birth_chart`、`ziwei_timing`、`ziwei_rules`；占星出生盘有 `astrology_chart`、`thirteen_sector_chart`、`hellenistic_chart`、`guolao_chart`、`vedic_chart`、`hamburg_midpoint_chart`、`relationship_chart`。术语与原典释义用 `knowledge_catalog` 与 `knowledge_read`（`--domain --category --key`，`domains[].categories[]` 先查目录，不拿通用相位词条冒充专属星体对规则）。

## 家居风水基础计算

这 8 个工具不要求完整八字生辰，合法缺失资料返回 `partial` 而非引擎失败；组合工具 `fengshui_assess` 在 CLI 用 `--request-file`（与 REST/MCP 同构）。完整字段、示例请求与现场核对规范见[家居风水](../../fengshui.md)和[风水咨询闭环](../fengshui/consultation.md)。

| 工具 | 对应输出层 | 输入与解读要点 |
| --- | --- | --- |
| `fengshui_directions` | `layers.directions` | 固定后天八卦与洛书方位；角度须明确参考北 |
| `fengshui_minggua` | `layers.minggua` | `birth_date`、`birth_at`、有效生年三选一；立春日边界留候选项，未知性别保留双候选 |
| `fengshui_bazhai` | `layers.bazhai` | 宅盘与逐人命盘独立；门/床/桌/灶位置与朝向分开读取 |
| `fengshui_jinsuo` | `layers.jinsuo` | 支持 8 宫与 24 山砂水极性分类；须明确分类与依据，不由物品名推断 |
| `fengshui_annual_stars` | `layers.annual_stars` | 立春换年；固定宫数与临宫年星分开，不把年盘当完整玄空山向盘 |
| `fengshui_monthly_stars` | `layers.monthly_stars` | 立春换年、十二节月起星（可选日/时紫白）；独立于年盘与宅盘 |
| `fengshui_xuankong_house_chart` | `layers.xuankong_natal` | 磁北宅向与历史定运事件；中州派运山向与兼向替星，角度不明保留候选 |
| `fengshui_assess` | `layers` 叠加 + `palace_overlay` / `layout_analysis` | 住宅评估总入口；须保留 `coverage` 与逐人差异 |

> [!NOTE]
> 金锁玉关已实现 8 宫与 24 山砂水极性计算；当前 `coverage.unavailable_layers` 仅指金锁形态元运与自动户型几何。禁止把三层结果合成为总分，也不由户主命卦覆盖其他住户。

## 典型调用样例

以下资料与日期均属虚构示例；需无损完整输出时传 `--include "*"` 并省略 `--fields`。

```bash
python3 -m fatebridge.cli bazi_birth_chart \
  --name 小南 --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 \
  --birth-hour 14 --birth-minute 30 --birth-place 北京 --use-true-solar-time

python3 -m fatebridge.cli bazi_marriage \
  --gender 女 --birth-year 1994 --birth-month 3 --birth-day 2 --birth-hour 9 --birth-place 上海

python3 -m fatebridge.cli bazi_compatibility \
  --person1-name 小A --person1-gender 男 --person1-birth-year 1992 --person1-birth-month 8 --person1-birth-day 15 --person1-birth-hour 14 \
  --person2-name 小B --person2-gender 女 --person2-birth-year 1994 --person2-birth-month 3 --person2-birth-day 2 --person2-birth-hour 9

python3 -m fatebridge.cli bazi_yearly_timing \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 --analysis-year 2026

python3 -m fatebridge.cli meihua_time_cast --question "这份 offer 该不该接" \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15

python3 -m fatebridge.cli astrology_chart \
  --name Mia --birth-year 1995 --birth-month 6 --birth-day 1 --birth-hour 8 --birth-minute 20 \
  --birth-latitude 31.23 --birth-longitude 121.47 --birth-place 上海

python3 -m fatebridge.cli fengshui_minggua --birth-year 1990 --gender female
python3 -m fatebridge.cli fengshui_annual_stars --effective-year 2026
python3 -m fatebridge.cli fengshui_monthly_stars --effective-solar-year 2026 --solar-month-number 3
fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json
```

## 跨体系与复用原则

多体系共享出生与历法输入；同一主题已有专项与综合命盘也不重复计作两份独立证据。按“结构 / 互动 / 阶段 / 目标时段 / 候选时刻”各司其职，已有结果在追问中复用而不重算，详细路由与分歧保留规则见[咨询核心](consultation-core.md#任务路由与多视角)。
