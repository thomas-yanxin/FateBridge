# FateBridge 引擎调用参考

本页说明 FateBridge 的工具调用、字段读取和错误处理。按当前问题查阅对应章节；咨询范围见[硬边界](safety-boundaries.md)与[问题范围](consultation-routing.md)，时间问题另查[时间选择](timing-selection.md)。

用户要求完整 JSON、全部时间线或完整输出时，使用 `detail=audit` 且 `fields=null`（CLI 省略 `--fields`）；普通摘要咨询默认使用 `detail=compact`，或按已发布 `evidence_views` 传入 `fields`（始终严格校验路径）。

一条铁律：所有排盘、干支、十神、大运流年、神煞、合婚分、安星、起局、星盘，全部交给 FateBridge 引擎算，AI 永远不要手算。统一使用可复核的计算结果，避免临时拼出另一套历法或时区规则。AI 负责读取算法输出、标注来源和限制，再用人话说明；可复现的计算不等于已证实的现实预测。

---

## 阅读导航

[调用与错误](#怎么调引擎) · [输出与首轮读取](#输出形态与首轮读取) · [共用参数](#参数字典共用字段) · [常用工具](#常用工具按家族) · [调用示例](#典型调用样例) · [调用纪律](#全局调用纪律) · [风水基础](#家居风水基础计算)

本页是 Agent 的调用参考；面向开发者的工具、输出分级与回执概念集中在[核心概念](../../concepts.md)。按当前缺口读取，不把完整工具地图当成必调清单。

## 怎么调引擎

已连接 FateBridge MCP 时，按所选工具的实际定义直接调用，不为用户咨询先运行安装诊断、搜索仓库或项目历史。当前聊天已确认的资料足够时直接计算；只有用户要求沿用历史资料才核对历史。以下 CLI 是无连接时的本地后备及可复核示例，不需要启动 REST 服务。

MCP 仅公开 `discover_tools` 与 `run_calculation` 两个入口（无资源 URI）。已知能力和业务参数时，用 `run_calculation(tool=能力名, arguments=业务输入)`；三端默认均为 `detail=compact` 返回精简核心业务字段。完整 JSON、全部时间线或方法依据使用 `detail=audit`、`fields=null`。需要参数时按名称用 `discover_tools(tool=能力名)`（需要 `output_schema` 时加 `detail="full"`，注意 `detail="full"` 须配合 `tool`、`family` 或 `q` 过滤），不把能力名当独立的 MCP 协议工具调用。已取得完整参数且能力公开时，不重复发现。工具描述的默认 `compact_fields` 与推荐 `suggested_fields` 来自共享字段配置；部分工具还发布按用户任务选择的 `evidence_views`（CLI `discover <tool>`、REST `/api/tools?tool=<tool>` 也可读取）。先选任务卡，再把其中 `fields` 复制到真实请求；卡名和 `view` 不是请求参数，不发送 `evidence_views/view/task`。关系盘按规范模式选卡，西占时运按 stage／annual／short_term 选卡；事业岗位／年度安排按 direction／target_year 选卡，西占事业补证可合并 career 卡，确保并列十神、判断范围和目标时间依据进入首次字段；细节卡与主任务字段合并去重，不用细节卡取代主层。默认视图是安全后备，不表示每次需要解释全部分支。三端对 `fields` 始终严格校验，无效路径返回 `unknown_projection_path` 并在 `constraints.available` 列出可用键名；详细追问时再按合同展开更多字段。没有首轮预设时，依据实际输出合同选字段，不猜路径。下面的出生数据都是示例，不能当作用户资料。

接收调用结果时，先核对实际返回形状（如 MCP 的 `structuredContent` 或文本 `content` JSON），确认结构完整后再解析；不要固定假设某种包装字段始终存在，也不要反复解析被宿主截断的片段。字段选择先用已核对的顶层业务字段，需要细节再展开，不为首轮遍历整个 `$defs`。

本地 CLI 示例须使用已安装 FateBridge 的虚拟环境。在仓库中按以下方式准备；这属于安装／开发任务，已连接的普通咨询无需运行：

```bash
uv sync --locked --extra dev
source .venv/bin/activate
```

以上为 macOS / Linux；Windows PowerShell 激活命令为 `.\.venv\Scripts\Activate.ps1`。下文 `python3` 指激活后该环境中的解释器，不使用未经核实的系统解释器。两种 CLI 形式 `fatebridge <tool>` 与 `python3 -m fatebridge.cli <tool>` 等价。

在本仓库使用本地后备时，优先已存在且已安装 FateBridge 的 `.venv/bin/python`，例如 `.venv/bin/python -m fatebridge.cli discover <tool>`。下方 `python3` 是已安装环境的通用写法，不表示系统默认解释器可导入本包；咨询不因解释器缺包而安装依赖、接受系统许可或修改用户配置。解析软链接用 shell 内建 `pwd -P` 即可，不依赖 Python 或 Xcode。

```bash
# 先通过 uv sync --locked 安装本仓库并激活 .venv
# python3 必须来自该环境，src 布局不能仅靠切到仓库根目录导入
python3 -m fatebridge.cli <tool> [参数...]

# 安装后也可以使用控制台入口
fatebridge <tool> [参数...]
```

常用控制开关与发现命令：

- `--detail {compact,audit}`：默认 `compact` 返回核心业务字段与精简回执；`audit` 返回完整业务载荷、全部时间线与 `calculation_evidence`。
- `--fields KEY [KEY ...]`：按点号路径严格投影，始终保留 `run_metadata`。
- `--as-of AS_OF`：传入带时区的 ISO 8601 时刻，冻结隐式当前时钟以便复现。
- `--request-file PATH`：所有 90 个工具命令均支持从 JSON 文件加载输入，命令行显式参数覆盖同名顶层字段。
- `fatebridge list`：以分类文本列出全部工具。
- `fatebridge discover [tool]`：输出目录摘要或指定工具的完整参数 schema、接口与示例（JSON，加 `--detail full` 附带 `output_schema`）。记不清参数时，先 `discover`，不要猜 flag。

调用前先过一遍自检：

- 不确定某工具要哪些字段 → 先 `discover <tool>`。
- 跑完先看 exit code 和 JSON 是否完整，再解读。
- 报错先读报错，多半是缺必填字段、投影路径有误或 flag 名写错，按 `discover` 或 `constraints` 改，不要重试同一条。

**成功和失败都走 stdout JSON。** 工具调用在 stdout 输出 JSON；`list` / `--help` 输出文本，`discover` 输出 JSON，成功是结果，失败是 `{"error": ..., "error_code": ..., "status_code": ..., "retryable": ...}`。用 exit code ≠ 0 判断失败，再读 stdout 里的 `error_code`/`error` 决定怎么改，不要只在出错时去读 stderr，错误信息不在那儿。

常见 `error_code`：

- CLI 调用层：`usage_error`（缺必填或 flag 写错）、`unknown_tool`（返回 `constraints.suggestions`）。嵌套输入工具支持 `--request-file`，不能仅因输入嵌套就判定不可调用。
- 引擎层（与 REST/MCP 一致）：`validation_error`（含 `unknown_projection_path` 等）、`dependency_missing`、`timeout`、`internal_error`。

`retryable=true` 才值得重试。

---

## 输出形态与首轮读取

全部工具均通过 `detail=compact`（默认）与 `detail=audit` 返回确定性结构化业务字段及 `run_metadata`；精确读取一律以结构化业务字段为准，不猜字段始终存在。

**结构化字段怎么读（需要精确时）：**

- `bazi_overview` → 根字段 `four_pillars`、`day_master`、`ten_gods`、`structure_profile`、`element_distribution`、`element_distribution_basis`、`person_info`。普通画像首轮可取这七项；格局解释读完整 `structure_profile` 的 `candidate_selection`、`layers/conflicts/conditional_elements/limitations`、`dominant_structure.formation_status` 和 `decision_basis`。月令主类、旧共现候选与尚未选定的原典取用路径分开，不能只取最终 `useful_elements`；按[八字专题取证](bazi-topic-evidence.md)区分月令格局、扶抑与调候。五行分布不等于喜用。
- `bazi_birth_chart` → `bazi_birth.four_pillars`、`bazi_birth.day_master` 等嵌套字段。它与 `bazi_overview` 的输出根结构不同，不能共用 `bazi_birth.` 前缀。
- `ziwei_birth_chart` → `ziwei_birth.ming_gong/shen_gong/palaces/sihua`；核对出生处理口径时按需加 `person_info`、`analysis_context`。
- `ziwei_timing` → 普通运限首轮可取 `analysis_context`、`birth_context`、`ziwei_horoscope.interpretation_scope`、`ziwei_horoscope.nominal_age`、`ziwei_horoscope.calendar_rules`、`ziwei_horoscope.scopes`；默认 `detail=compact` 已预设精简核心视图。`scopes` 是数组，当前投影必须整体取，不能编造 `scopes.流年` 或索引路径；按本轮粒度解释其中所需层，其余不展开。核对 `analysis_context.context_role=target` 及 `analysis_datetime`，出生处理另读 `birth_context`。本命／运限宫位身份与四化连接读[紫微专题取证](ziwei-topic-evidence.md)。
- `astrology_chart` → `angles`、`chart_profile`、`planets`、`aspect_evidence`、`classical`、`person_info`。按问题读取位置、相位或具名版本的原典条件。
- 八字九专题 → `<topic>_analysis.evidence_chain.topic.first_view` 为首轮取证，完整 `evidence_chain` 含星位、根气、格局前提与运年触点。`timing_context` 列实际所用时柱和时间来源。
- `bazi_compatibility` → `natal_contexts`、`cross_chart_relations`、`directional_ten_gods`。结合实际关系与问题解读双方盘式和跨盘接触。
- `sukuyo_compatibility` → 现代中国农历月日及T1299下卷望宿两法定27宿，**有方向**：`person1_to_person2` 与 `person2_to_person1` 分别读取；`pair`仅为配对类别，`su27_basis`是算法版本，各自本命宿在 `person1/2.natal_su27`。闰月或可选桧尾半日/补配次序未定时保留候选；`candidate_relation_analysis`仅列条件组合，不能挑一行当已定结果；`source_table_variant`是T1299印本28宿月建表异文，不能替代三九所用27宿。
- `relationship_chart` → `relationship_profile`、`inner_chart`、`outer_chart`、`synastry_aspects`、`chart`、`compatibility`。

**精确投影 `--fields`：只取你要的结构化字段，省 token。** 支持顶层 key，也支持点号子路径（从输出根算起的绝对路径，不深搜）。多个字段用空格分隔，不是逗号（逗号会被当成一个字段路径并在严格校验下返回 `validation_error`）。`run_metadata` 始终保留。

```bash
# 单字段：直接拿四柱
python3 -m fatebridge.cli bazi_birth_chart <出生参数> \
  --fields bazi_birth.four_pillars

# 多字段（空格分隔）：四柱 + 三元
python3 -m fatebridge.cli bazi_birth_chart <出生参数> \
  --fields bazi_birth.four_pillars bazi_birth.three_origins

# 专项嵌套字段：只取正缘时机信号
python3 -m fatebridge.cli bazi_romance <出生参数> \
  --fields romance_analysis.romance_timing
```

路径按所调用工具自己的输出根结构填写：`bazi_birth_chart` 带 `bazi_birth.` 前缀，`bazi_overview` 直接取根字段，八字 9 专项带 `<dim>_analysis.` 前缀。输入参数相似不代表输出路径相同。三端对 `fields` 始终严格校验：路径不存在时返回 `validation_error` 并在 `constraints.available` 提示可用键名，应核对合同后修正，不要编造字段。

请求的 `fields` 沿对象路径投影，数组取其所属字段（例如 `planets`、`aspects`、`ziwei_birth.palaces`）；传入数字索引（如 `fields=["planets.0"]`）会报 `non_object_projection_path`。读取后核对星体／宫位名称，再选与问题有关的项目解释，不把列表首项自动当成重点。

**三端等价。** 控制面在 REST / MCP / CLI 上语义一致：REST 用查询参数 `?detail=compact|audit&fields=...&as_of=...`（`fields` 可重复，等价于 CLI 的空格分隔）；MCP `run_calculation` 用同名参数 `detail` / `fields` / `as_of`；CLI 用 `--detail` / `--fields` / `--as-of`。无论哪端，都需要保留 `run_metadata` 以便核对时钟与口径；需要复现或固定时钟时传入 `as_of`；只解释未改变的结果不重算。

---

## 参数字典（共用字段）

**出生信息（中式工具：八字 / 时运 / 紫微 / 六壬）**

```
--name 张三 --gender 男|女
--birth-year 1992 --birth-month 8 --birth-day 15
--birth-hour 14 --birth-minute 30
--birth-place 北京          # 用于查经度算真太阳时
--birth-longitude 116.40    # 可选，直接给经度更准
--birth-timezone Asia/Shanghai
--use-true-solar-time       # 开启真太阳时校正（推荐）
```

- 性别影响大运顺逆，具体必填性按工具模型；`bazi_luck_cycles` 要求 `gender`，默认按目标瞬间选运，`analysis_age` 仅作显式年龄参考，不能与 `analysis_*` 日期组合。
- 对实际 Schema 必填小时的计算，缺小时只阻止该次计算；先简短核对，用户已说不知道或无法提供时停止同项追问。可以解释已有结果、传统概念或已给的现实选项；确有不依赖缺项的工具时再选择适用路线。不能省略或擅自填 0 当作无时盘。只有「上午」等时段不能复用某个精确时刻的命盘；用户明确选择假设时刻比较后分别标明假设，保留时段内不稳定结论。
- 用户用日常语言提供历法、日期、时间范围和城市即可，由助手按合同转译参数。这些 `birth_*` 接口使用公历；历法确有歧义时才核对，农历先转换。出生时区依出生地与历史日期解析并核对实际回执，不要求用户自己提供 IANA 名称，也不能直接套当前聊天时区。真太阳时默认开启，通常省略开关沿用引擎默认；显式 `true` 表示必须完成校正，缺地点／经度时可能报错，不能机械抄入默认值。仅按用户明确要求关闭；未知经度可省略，以返回精度限制说明，不能猜经度。
- 出生地用于地点与太阳时解析，给到城市并保留返回精度；支持的城市交给引擎解析，不要求用户自行查经纬度。所选接口确需显式坐标且不能可靠解析时再说明补充方式，不能把示例坐标当事实。中式工具不能套入西占 `birth_latitude` 参数。

**分析时点（按所选工具核对）**

```
--analysis-year 2026 --analysis-month 6 --analysis-day 18   # 想看哪天的运
--analysis-age 35                                            # bazi_luck_cycles 的独立年龄参考，不与分析日期组合
--analysis-year 2026                                         # bazi_yearly_timing 指定流年
```

八字九维专项工具（marriage/career/...）会自动推算当前大运、流年，用户不用懂大运。`--dayun-pillar`/`--liunian-pillar` 只是手动覆盖，正常别传。

出生时点使用 `birth_*`，分析时点使用该工具的 `analysis_*` 或提问时间字段。未指定的当前时间才由引擎取当前值；需要复现时传带时区 ISO `as_of`，它不能替代明确的分析年月日，也不补出生时刻。起卦等要求显式时间的工具仍须按实际必填项传入。

**西占核心盘、关系盘与推运分别核对合同：** 核心盘的经纬度可由引擎从已支持的 `birth_place` 解析，不要求用户自己查坐标；核对实际解析来源、时区与精度。地点不能解析时再补必要资料，不接受默认未知地点作真实位置。关系盘与西占推运需显式经纬度。核心／关系盘默认民用钟时，`use_true_solar_time=false`；不要把中式工具默认太阳时套过来。推运按自身实际 Schema 核对。

```
--birth-latitude 39.90 --birth-longitude 116.40   # 核心盘可按支持城市解析；关系/推运需明确坐标
--birth-timezone Asia/Shanghai
--house-system P         # 核心/关系盘与西占推运均用 --house-system（支持 P/W/D 等字母、名称或 0..8 整数）
--zodiac-type Tropic     # 核心/关系盘与西占推运均用 --zodiac-type（Tropic=回归，Sidereal=恒星）
# 目标时间分别传 --analysis-year、--analysis-month、--analysis-day
# 精确目标钟时另传 --analysis-hour 12 --analysis-minute 0（按出生时区）
```

西占聚合推运及 11 个单项技法的 `analysis_hour` / `analysis_minute` 按 `birth_timezone` 解释，显式零值有效；省略时分别沿用出生小时／分钟以兼容日期级 调用。需要精确分析时刻时两项都传，并核对 `analysis_context.analysis_datetime`。 `as_of` 只冻结缺省日期的当前时钟；`return_timezone` 转换同一时刻到分析地点， 不替代输入时区。REST 请求体、MCP 参数与 CLI 开关语义一致。

核心星盘优先使用 `swisseph`；缺包时可回退内置轨道近似，显式复杂宫制除外。西占推运/事件/生命周期缺 backend 时直接报错，不能按近似结果解读。`swisseph` 可导入仍可能使用 Moshier 模型，检查 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`。`pyswisseph` 是常规依赖，星历数据另行获取，见 [快速入门](../../getting-started.md#星历数据与精度)。

---

## 常用工具（按家族）

当前 REST 公开 90 个工具，MCP 通过两个入口提供 90 项业务能力，目录共有 90 条记录，CLI 可执行 90 条。完整清单见[算法覆盖](../../algorithm-coverage.md)，请求合同以 `discover` 和[API 参考](../../api-reference.md#22-三端能力边界)为准。

### 八字 · 命主本命

- `bazi_birth_chart`：完整命盘，含四柱三元、纳音、十神、藏干、格局调候、十二长生、当前大运流年、神煞。
- `bazi_overview`：综合命理，八字 + 喜用 + 格局，一站式。

### 八字 · 九大专项（结构化 JSON，自动带时机信号）

`bazi_marriage` 婚姻、`bazi_romance` 正缘桃花、`bazi_career` 事业、`bazi_wealth` 财运、`bazi_health` 健康、`bazi_children` 子女、`bazi_education` 学业、`bazi_personality` 性格、`bazi_relatives` 六亲。

均接受 `--analysis-year/month/day`，内部自动推大运/流年（结果在 `<dim>_analysis.timing_context`）。返回 JSON 包含 `{analysis_type, <dim>_analysis}` 及 `run_metadata`。

### 配合度 · 双人（结构化 JSON）

- `bazi_compatibility`：八字合婚 / 合作配合度，含综合分、五行互补、共同喜用、优势/挑战/建议。两人各一套 `--person1-*` / `--person2-*` 字段（名/年/月/日/时/性别）。
- `sukuyo_compatibility`：按固定UTC+08现代中国农历月日及T1299望宿法定27宿，有方向性，不按月亮经度。可选桧尾研究档案须明确原典半日，不能由民用钟时自动猜测。UTC+08历日可只给双方 `--person1-date/--person2-date`，未知生时不猜；经纬度兼容字段不参与本命宿计算。

### 时运 · 推命

`bazi_timing` 时运综合、`bazi_luck_cycles` 大运、`bazi_yearly_timing` 流年、`bazi_monthly_timing` 流月、`bazi_daily_timing` 流日、`bazi_hourly_timing` 流时、`solar_term_timeline` 节气时间轴、`solar_terms_for_year` 节气年表、`lunar_calendar_time` 农历时间换算。

**综合 vs 颗粒怎么选**：`bazi_timing` 是聚合器，一次把当前大运 + 流年（+ 流月等）的综合影响给全，问「最近运势/这两年怎么样」用它；`bazi_luck_cycles`/`bazi_yearly_timing`/… 是单层颗粒，只盯某一层（如就看某个大运、某个特定流年）才单独调。综合工具的内容与颗粒工具有意重叠，别为了拼一个时运全景去逐层调颗粒再自己拼，那是 `bazi_timing` 的活。

### 占卜 · 问事起卦（按实际输出读取）

- `meihua_time_cast`：梅花易数，读取结构化 `meihua` / `summary` / `interpretation`，`--question`（可选）+ 起卦时间必填 `--analysis-year/month/day/hour`（要按当下起卦就传当前日期时间）。
- `liuyao`：六爻，`--question`，CLI 手摇用 `--coins`（六掷之和，初爻到上爻，每项 6/7/8/9）或 `--gua-code`，也可按时间起。`lines` 对象列表使用 REST/MCP 传入，CLI 不解析对象字符串。
- `combine_four_gua`：统摄四卦组合，读取实际 `taiyin/taiyang/shaoyang/shaoyin`；固定默认不是用户起卦，不实现蓍草十八变／大衍随机起卦。
- `gua_lookup`：八卦与六十四卦批量查询（支持 `queries` 与 `lookup_mode`）。
- `qimen`：奇门遁甲，起局 + 用神。
- `taiyi`：太乙神数，支持明确选择年／月／日／时计；合参对应选项放入`taiyi_options`。先按[太乙取证](../zhanbu/taiyi-sanshi.md)核模式、起元、钟面和实际证据，现代适配不冒称完整古历。年／月八门与定计用`gates`、`gate_comparison`、`determinate`分源深读；日计读`daily_calendar/daily_essences`，始击读`shiji_derivation`，原表读`count_sources`。`menju_jiangfa`为三值条件合取，时计三门仍未裁定；默认至点时计不附定计，显式`key_hour_winter_jiazi_v1`可读完整积时和定计并保留原例三项差异，不按有利结果换法。
- `jinkou`：金口诀，`--di-fen` 地分 + 时间。
- `liuren_chart`：大六壬起课。
- `liuren_yearly_timing`：六壬流年（行年）。
- `suzhan`：历日27宿与七曜物理天文28宿分别读取。天文默认现代距星视赤经研究宿界，不当作唐代宿界；活动解释读取整个 `activity_assessment` 与 `calendar_day`，保留各卷条文、日名和昼夜例外。`conflicted`不能挑一条宜忌合成结论；`clock_evaluation_status=not_computed`不能写成具体时刻已验吉。六类标签和三九组序均不当成功概率或近中远距离。
- `interpret_astrology_dice`：解读用户实际提供的行星／星座／宫位骰面；不自动随机抽骰，不能把默认骰面当本次抽取。
- `sanshi_combined_chart`：三式合参（奇门 + 太乙 + 六壬同盘）。

### 紫微斗数

- `ziwei_birth_chart`：紫微命盘（含十二宫安星）。
- `ziwei_timing`：紫微六层运限与动态四化。
- `ziwei_rules`：紫微规则查询（`--year-stem`）。

### 占星 · 出生盘与关系盘

- `astrology_chart`：标准盘。
- `thirteen_sector_chart`：13 扇区盘。
- `hellenistic_chart`：希腊盘。
- `guolao_chart`：果老星宗。
- `vedic_chart`：印度盘。
- `hamburg_midpoint_chart`：德国盘。
- `relationship_chart`：三端使用 `inner_birth_*` / `outer_birth_*`。CLI 对应 `--inner-birth-*` / `--outer-birth-*`，REST 路由为 `/api/astrology/relationship-chart`。每方须提供 `year/month/day/hour/longitude/latitude`，以及可解析的时区或出生地。

### 西占 · 推运（需要 backend，缺失时报错）

`western_timing` 时运综合、`solar_return` 太阳返照、`lunar_return` 月返、`transit_chart` 行运、`solar_arc` 太阳弧、`chart_for_year` 指定年盘、`profection` 年小限、`primary_directions`/`primary_directions_chart` 主限、`zodiacal_releasing` 黄道释放、`firdaria` 法达星限、`decennials` 十年星限。

同八字时运的逻辑：`western_timing` 是综合聚合，要整体推运用它；`solar_return`/`transit_chart`/`profection`/… 是单一技法颗粒，只看某一术时单独调。两者内容有意重叠。

### 西占 · 事件与生命周期

事件工具：`mundane_ingress_chart`、`planetary_returns`、`horary_chart`、`evaluate_election_time`。

生命周期工具：`harmonic_chart`、`planetary_ages`、`triplicity_ruler_periods`、`lunar_phase_progressions`、`bounds_directions`、`balbillus_periods`、`numeric_aspect_periods`、`planetary_periods_129_years`、`planetary_arc_directions`、`persian_directions`、`age_point`、`sidereal_progressions`、`declination_progressions`。仅在需要相应技法时调用，完整输入先查 `discover`。

### 知识 helper

- `knowledge_catalog`：知识目录。
- `knowledge_read`：读取词条（`--domain --category --key`）。

用于给一段结果补充传统词条释义。

知识查询优先沿用工具公开的 `call_guidance`。目录的分类与键位于 `domains[].categories[]`，严格投影先读所属根，不猜 `domain/categories` 根路径。西占相位按 `category=aspect` 与实际角度／键定位；`object_a/object_b` 仅标注对象，不能单独找到词条，返回的通用相位含义也不冒充该星体对的专属规则。健康传统词条中的病名或调理说法不应用为个人医学结论。

---

## 跨体系交叉印证（文化视角对照）

八字、紫微、西占采用不同的传统规则，但共享出生信息、历法或星历输入。多体系一致可用于整理文化视角，不是独立统计证据，也不能证明现实预测准确。专题综合主动评估有新增价值的相关视角；单项或限定方法按其范围。选两到三套时保留来源：

- 多套描述重合 → 合并说明哪些规则产生了共同描述，再与用户实际经验对照。
- 某结论只有一套提到 → 标出该体系与适用范围；另两系未提到不自动表示它较弱，也不补造旁证。
- 两套描述矛盾 → 先核对是否在说同一人物、命题、时段和条件，再核对时区、坐标、太阳时策略、独立年界和模型。长期特点与某年安排不直接对冲；同一命题仍有分歧时分别呈现，不自行断言是用户的内在张力。

读法：调用前写清每种方法要补哪个子问题，首次字段覆盖该主证。按实际结构化字段形成“事实 → 有来源的规则解释 → 本次条件式应用”，现实建议另说明可核对条件。第二方法须增加相关事实、改变适用条件、发现冲突或收窄判断；只重复描述就不增加调用。正文合并真正重合的判断，保留各自来源与分歧，不能按体系票数增加把握。同一八字专项与综合是共享来源的补充字段，不计作两份独立印证。

---

## 典型调用样例

以下资料与日期均为虚构示例，在上文已准备的虚拟环境中运行。需要完整输出与方法依据时加 `--detail audit`。

```bash
# 八字本命盘
python3 -m fatebridge.cli bazi_birth_chart \
  --name 小南 --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 \
  --birth-hour 14 --birth-minute 30 --birth-place 北京 --use-true-solar-time

# 八字婚姻专项（自动带当前大运/流年）
python3 -m fatebridge.cli bazi_marriage \
  --gender 女 --birth-year 1994 --birth-month 3 --birth-day 2 --birth-hour 9 --birth-place 上海

# 双人合婚
python3 -m fatebridge.cli bazi_compatibility \
  --person1-name 小A --person1-gender 男 --person1-birth-year 1992 --person1-birth-month 8 --person1-birth-day 15 --person1-birth-hour 14 \
  --person2-name 小B --person2-gender 女 --person2-birth-year 1994 --person2-birth-month 3 --person2-birth-day 2 --person2-birth-hour 9

# 流年看 2026
python3 -m fatebridge.cli bazi_yearly_timing \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 --analysis-year 2026

# 梅花易数问事（起卦时间必填，按当下就传当前日期时间）
python3 -m fatebridge.cli meihua_time_cast --question "这份 offer 该不该接" \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15

# 占星标准盘
python3 -m fatebridge.cli astrology_chart \
  --name Mia --birth-year 1995 --birth-month 6 --birth-day 1 --birth-hour 8 --birth-minute 20 \
  --birth-latitude 31.23 --birth-longitude 121.47 --birth-place 上海
```

参数不清楚时运行 `python3 -m fatebridge.cli discover <tool>`。安装、连接或依赖错误按实际报错处理，参见[故障排除](../../troubleshooting.md)。

---

## 全局调用纪律

按实际工具覆盖选择方法，完整调用约定见[接入指南](../../agent-guide.md)。本节集中列出工具调用的执行约定。

- **命盘复用**：综合命理画像调一次 `bazi_overview`（已含命盘 + 喜用 + 格局），不要再调 `bazi_birth_chart`；只要原始四柱才单用 `bazi_birth_chart`。同一出生信息跨八字/紫微/西占复用，不重复采集。
- **聚合优先**：时运全景用 `bazi_timing` / `western_timing`，不连发多个单技法；只要一项才用单工具。
- **粒度匹配**：年级信号（如 `romance_timing`）不许说成「几月」，要月级才升级 `bazi_monthly_timing`，日级才 `bazi_daily_timing`。
- **首轮收口**：默认 `detail=compact`，按已发布 `evidence_views` 选择 `fields` 精确取数（三端始终严格校验）；需要完整业务载荷与审计证据时传 `detail=audit` 且 `fields=null`。
- **按问题核对资料**：使用已确认信息，由助手把日常表述转成参数；只核对会改变所选计算的缺项，不串行问每个字段。缺项仅限制依赖它的结论，已有部分先交付；用户明确不知道或无法提供时停止同项追问，说明可继续的解释或适用替代路线。合同已齐全不重复发现，报错先读 `error_code` 再改，不盲重试。

---

## 交叉印证与去重（防矛盾）

按结构、互动、阶段、目标时段与候选时刻分别选择依据，不按领域永久指定唯一主体系。专题综合通常评估两套相关视角，工具数不是配额；简单单项与指定方法可只用一套。新增工具须补未回答的问题或独立层，已有命盘和时机不重算。共同描述合并且署明来源，分歧先查输入再保留，不投票、不平均，不以多体系同向增加现实预测置信度。完整规则见[本轮范围及多视角](consultation-routing.md)。

## 家居风水基础计算

完整空间咨询使用[风水资料参考](../fengshui/consultation.md)：它整合下述工具、形态与桌面作者规则，核对现场事实和行动约束，并跟踪无规则／待确认项目。出生和宅向只对需要这些资料的层核对。

| 工具 | 应读取的层 | 输入要点 |
| --- | --- | --- |
| `fengshui_directions` | `layers.directions` | 固定后天方位；角度须明确参考北 |
| `fengshui_minggua` | `layers.minggua` | 公历 `birth_date`、含时区 `birth_at`、有效生年三选一；非立春当日无需小时，男女起算法未知则保留候选 |
| `fengshui_bazhai` | `layers.bazhai` | 坐山宅盘与逐人命盘独立；门床桌灶位置／朝向分开 |
| `fengshui_jinsuo` | `layers.jinsuo` | 明确砂／水／混合／未知分类及依据，不由物品名称推断 |
| `fengshui_annual_stars` | `layers.annual_stars` | 立春换年；固定宫数与临宫年星分开 |
| `fengshui_xuankong_house_chart` | `layers.xuankong_natal` | 磁北宅向、历史定运依据；中州派运山向／兼向替星；角度不明返回候选 |
| `fengshui_assess` | 三个独立基础层及显式选定的宅盘 | 住宅请求 JSON；逐人差异、规则来源／版本、覆盖缺失 |

这组工具不需要完整八字生辰；组合 CLI 用 `--request-file`，文件合同与 REST/MCP 请求一致。完整字段、可复制住宅请求和来源边界见 [家居风水](../../fengshui.md)。合法缺失资料为 `partial`，不是引擎失败。三层的条件和时间范围不同，禁止合成总分、让户主覆盖其他住户，或把年盘说成完整玄空山向盘。玄空宅盘须显式选择 `methods` 的 `xuankong_natal` 并提供 `xuankong.period`，以历史事件定运，不用当前元运覆盖宅运。金锁 24 山／形态元运和自动户型几何未实现。

```bash
python3 -m fatebridge.cli fengshui_minggua --effective-birth-year 1990 --gender-convention female
python3 -m fatebridge.cli fengshui_annual_stars --effective-year 2026
fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json --detail compact
```

太乙 `calculation_mode=day` 采用金钥匙积日法。先设 `day` 再取 `daily_calendar` / `daily_essences`，零时日界不可套时计 23 时子初；天时和太乙数宫位未知、正文/课式异数需忠实解释。需要完整结果与依据时传 `detail=audit`，不凭 `detail=compact` 默认裁剪作否定。
