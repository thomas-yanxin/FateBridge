# FateBridge 引擎参考层（fatebridge-engine）

这是所有 FateBridge 场景 Skill 共用的计算层。

用户要求完整 JSON、全部时间线或完整文件导出时，第一次调用设 `fields=null`（CLI 省略 `--fields`），保留默认响应预算；下文精简首轮字段仅用于普通摘要咨询。输出投影先于交付保存，分页不会恢复投影已排除的字段，所以不能先裁成摘要再补算全文。

一条铁律：所有排盘、干支、十神、大运流年、神煞、合婚分、安星、起局、星盘，全部交给 FateBridge 引擎算，AI 永远不要手算。统一使用可复核的计算结果，避免临时拼出另一套历法或时区规则。AI 负责读取算法输出、标注来源和限制，再用人话说明；可复现的计算不等于已证实的现实预测。

---

## 怎么调引擎

已连接 FateBridge MCP 时，按所选工具的实际定义直接调用，不为用户咨询先运行安装诊断、搜索仓库或项目历史。当前聊天已确认的资料足够时直接计算；只有用户要求沿用历史资料才核对历史。以下 CLI 是无连接时的本地后备及可复核示例；不需要起 REST 服务。两种 CLI 写法等价：

已加载的调用合同包含完整参数且工具公开时，不重复发现；其他工具按名称一次取得实际 inputSchema 与描述，再调用。工具描述的首轮 `fields` 来自共享字段配置；首轮设 `strict_fields=true`、`include_snapshot_text=false`，详细追问才展开更多字段。没有首轮预设时，依据实际输出合同选字段，不猜路径。下面的出生数据都是示例，不能当作用户资料。

接收调用或资源结果时，先核对实际返回形状：可能是 JSON 字符串、文本 `content` 或 `structuredContent`，不能固定假设存在 `contents[0]` 或 `structuredContent.run_metadata`。有截断标记的 JSON 片段不能解析成完整合同；改读所选工具的实际定义或更小的资源，勿反复解析同一片段。字段选择先用已核对的顶层业务字段，需要细节再展开，不为首轮遍历整个 `$defs`。

MCP 默认响应字符预算为8192；超限返回 `result_delivery`，原结果没有被截断，仍由同一 run 保留。先读其 `manifest_uri`，按所需字段的资源取值；点路径支持对象和数组数字索引，资源模板为 `fatebridge://results/{result_id}/fields/{path}/{offset}`，首 offset 为0。每页是完整 JSON 包装，其中 `text` 是文档片段；需要完整字段时按 `next_offset` 拼接并核对 `sha256`，不把单页当全文解析，不重新计算。先取窄字段，不一次打印重组后的大对象。引用约一小时过期，也可能因容量回收失效；失效须如实说明。

REST/CLI 默认继续完整交付，可显式设置 `response_char_limit` / `--response-char-limit` 获得同一限量合同。MCP 的 `response_char_limit=0` 仅供可保存完整 JSON 的程序客户端；聊天咨询不要用它规避分页，否则宿主仍可能截断。

用户要求保存本机完整文件时，可读取 `file_path` 指向的私有临时记录，按 `file_payload_path`（当前为 `payload`）取出原结果，以 `ensure_ascii=False,separators=(",", ":")` 序列化后核对 `sha256` 并保存。外层记录还含过期时间，其文件散列不等于原结果散列；不把外层记录交付为完整计算结果。保存后的用户文件独立于临时引用保留。

在本仓库使用本地后备时，优先已存在且已安装 FateBridge 的 `.venv/bin/python`，例如 `.venv/bin/python -m fatebridge.cli describe <tool>`。下方 `python3` 是已安装环境的通用写法，不表示系统默认解释器可导入本包；咨询不因解释器缺包而安装依赖、接受系统许可或修改用户配置。解析软链接用 shell 内建 `pwd -P` 即可，不依赖 Python 或 Xcode。

```bash
# 先通过 uv sync --locked 安装本仓库并激活 .venv
# python3 必须来自该环境，src 布局不能仅靠切到仓库根目录导入
python3 -m fatebridge.cli <tool> [参数...]

# 安装后也可以使用控制台入口
fatebridge <tool> [参数...]
```

常用全局开关：

- `--no-metadata`：去掉 `run_id`/`trace_id` 等溯源字段；复核或日志场景建议保留，示例用此开关简化输出。必须放在工具名之前。
- `fatebridge.cli list`：列出全部工具。
- `fatebridge.cli describe <tool>`：输出某工具的完整参数 schema、接口、类型、是否必填，返回 JSON。记不清参数时，先 `describe`，不要猜 flag。

调用前先过一遍自检：

- 不确定某工具要哪些字段 → 先 `describe <tool>`。
- 跑完先看 exit code 和 JSON 是否完整，再解读。
- 报错先读报错，多半是缺必填字段或 flag 名写错，按 `describe` 改，不要重试同一条。

**成功和失败都走 stdout JSON。** 工具调用在 stdout 输出 JSON；`list` / `--help` 输出文本，`describe` 输出 JSON，成功是结果，失败是 `{"error": ..., "error_code": ..., "status_code": ..., "retryable": ...}`。用 exit code ≠ 0 判断失败，再读 stdout 里的 `error_code`/`error` 决定怎么改，不要只在出错时去读 stderr，错误信息不在那儿。

常见 `error_code`：

- CLI 调用层：`usage_error`（缺必填或 flag 写错）、`cli_unsupported`（未公开 CLI 请求合同，按错误提示选择其他入口）、`unknown_tool`。已启用 JSON 请求合同的嵌套工具可用 `--request-file`，不能仅因输入嵌套就判定不可调用。
- 引擎层（与 REST/MCP 一致）：`validation_error`、`dependency_missing`、`timeout`、`internal_error`。

`retryable=true` 才值得重试。

---

## 输出形态与首轮读取

工具按实际合同返回结构化业务字段、`snapshot_text` 和部分工具的 `snapshot_export`。只有文本快照不等于没有结构化业务字段；六爻、统摄组合、星骰等仍须先检查实际业务结果，不能只因没有 `snapshot_export` 就丢弃结构化依据。确无独立业务字段时保留必要文本，不猜字段始终存在。快照形式见 [快照覆盖](../../docs/algorithm-coverage.md#4-快照协议覆盖)。

一类工具的 `snapshot_text` 只是结构化字段的中文摘要，精确读取仍以业务字段为准。

**可以先从 `snapshot_text` 阅读的工具**

已实测核对：`bazi_birth`、`analyze_destiny`、时运全系、紫微、奇门、六壬、太乙、金口、`astro_chart` 等命盘/起局/起卦类。

读法：首轮读与问题对应的结构化字段。用户要求完整命盘或导出时，再读取存在的 `snapshot_text`；它记录算法生成的中文摘要，包括四柱、十神、格局、神煞、大运流年。

**`snapshot_text` 是摘要，细节看结构化字段的工具**

主要是八字 9 大专项：`bazi_marriage`、`bazi_romance`、`bazi_career`、`bazi_wealth`、`bazi_health`、`bazi_children`、`bazi_education`、`bazi_personality`、`bazi_relatives`，以及 `two_person_compatibility`、`sukuyo_compatibility`、`astro_relative_chart`。

读法：先读下面的业务字段，用实际返回值说明分数、落点与相位；快照只在需要文本摘要时展开。`astro_relative_chart` 的 `snapshot_text` 只摘要关系画像、互动相位、配合度，完整盘在结构化字段里。

**结构化字段怎么读（需要精确时）：**

- `analyze_destiny` → 根字段 `four_pillars`、`day_master`、`ten_gods`、`structure_profile`、`element_distribution`、`element_distribution_basis`、`person_info`。普通画像首轮可取这七项；格局解释读 `structure_profile.decision_basis/useful_elements`，五行分布不等于喜用。
- `bazi_birth` → `bazi_birth.four_pillars`、`bazi_birth.day_master` 等嵌套字段。它与 `analyze_destiny` 的输出根结构不同，不能共用 `bazi_birth.` 前缀。
- `ziwei_birth` → `ziwei_birth.ming_gong/shen_gong/palaces/sihua`；核对出生处理口径时按需加 `person_info`、`analysis_context`。
- `astro_chart` → 根字段 `angles`、`chart_profile`、`planets`、`aspects`、`interpretation`、`person_info`。普通首轮的解释子项按工具公布的字段选择；出生钟时读 `person_info`。`western_timing_analysis` 的 `analysis_context` 不能移作本命盘字段。
- 八字 9 专项 → `{"analysis_type": "...", "<dim>_analysis": {...}}`。解读读 `<dim>_analysis`，里面是该维度的子项。例如 `bazi_romance` → `romance_analysis.{peach_blossom, hongluan_tianxi, opposite_sex_star, peach_quality, romance_timing, timing_context}`；`bazi_wealth` → `wealth_analysis.{...}`。`timing_context` 段是引擎自动推算的当前大运/流年，看时机就看它。
- `two_person_compatibility` → `summary`（`overall_score` / `compatibility_level`）、`traditional_compatibility`、`detailed_analysis`（`element_balance` / `favorable_synergy`）、`strengths`、`challenges`、`recommendations`。不同规则段的分数保留各自名称与作用域，不合成成功概率；`person_info` 中的个人内部结构不能直接解释为双方互动。建议列表为空时如实说明，现实沟通建议另作标记。
- `sukuyo_compatibility` → 27 宿相性，**有方向**：`person1_to_person2` 与 `person2_to_person1` 各一套关系判定，别只读一边；另有 `pair`（双向综合）、`su27_basis`（各自本命宿）、`summary`。
- `astro_relative_chart` → `relationship_profile`、`inner_chart`、`outer_chart`、`synastry_aspects`、`chart`、`compatibility`。

取 `snapshot_text` 的稳妥写法：

```bash
python3 -m fatebridge.cli --no-metadata bazi_birth ... \
  | python3 -c "import json,sys;d=json.load(sys.stdin);print(d.get('snapshot_text') or json.dumps(d,ensure_ascii=False,indent=2))"
```

支持 `--selected-sections` 的工具可用空格分隔的段名筛选导出（带空格的单个标题需引号），不要用逗号拼成一个标题。段名可从 `snapshot_export.section_titles_detected` 查看；该参数只裁剪导出文本，完整 `snapshot_text` 和业务数据仍返回，不会自动缩小整个响应。八字九大专项没有 `selected_sections` 输入，使用 `--fields` 精简。

**精确投影 `--fields`：只取你要的结构化字段，省 token。** 支持顶层 key，也支持点号子路径（从输出根算起的绝对路径，不深搜）。多个字段用空格分隔，不是逗号，逗号会被当成一个不存在的 key，返回空对象。已附带的 `run_metadata` 会保留；`--no-metadata` 会关闭附加。

```bash
# 单字段：直接拿四柱
python3 -m fatebridge.cli --no-metadata bazi_birth <出生参数> \
  --fields bazi_birth.four_pillars

# 多字段（空格分隔）：四柱 + 三元
python3 -m fatebridge.cli --no-metadata bazi_birth <出生参数> \
  --fields bazi_birth.four_pillars bazi_birth.three_origins

# 专项嵌套字段：只取正缘时机信号
python3 -m fatebridge.cli --no-metadata bazi_romance <出生参数> \
  --fields romance_analysis.romance_timing
```

路径按所调用工具自己的输出根结构填写：`bazi_birth` 带 `bazi_birth.` 前缀，`analyze_destiny` 直接取根字段，八字 9 专项带 `<dim>_analysis.` 前缀。输入参数相似不代表输出路径相同。首轮使用 `--strict-fields`：路径不存在会返回校验错误，应核对合同后修正。默认宽松模式可能返回空对象及 `projection_warnings`，指不到字段就别说，别编。

请求的 `fields` 目前沿对象路径投影，数组取其所属字段（例如 `planets`、`aspects`、`ziwei_birth.palaces`）；不要把交付资源支持的数组数字索引照搬成 `fields=["planets.0"]`，这会报 `non_object_projection_path`。读取后核对星体／宫位名称，再选与问题有关的项目解释，不把列表首项自动当成重点。

**首轮关掉快照文本（`--no-include-snapshot-text`）。** 读取结构化字段时，加 `--no-include-snapshot-text`（或 `--include-snapshot-text false`）。脚本管道里想要单行紧凑 JSON 再加 `--compact`。CLI 默认美化缩进；是否包含快照随工具合同而定，不应假设所有工具都有文本。

```bash
# 只取结构化字段 + 关掉快照 + 紧凑：最省 token 的取数姿势
python3 -m fatebridge.cli --no-metadata bazi_birth <出生参数> \
  --no-include-snapshot-text --compact --strict-fields --fields bazi_birth.four_pillars
```

**三端等价。** 这套输出精炼在 REST / MCP / CLI 上语义一致。REST 用查询参数：`POST /api/cn/bazi/birth?include_snapshot_text=false&strict_fields=true&fields=bazi_birth.day_master&fields=...`（`fields` 可重复，等价于 CLI 的空格分隔）；MCP 工具用同名 keyword 参数 `fields` / `strict_fields` / `include_snapshot_text` / `compact`。无论哪端，已附带的 `run_metadata` 会保留；`--no-metadata` 会关闭附加。咨询后续需保留回执，用户更正资料时重建受影响输入，沿用 `trace_id`、`parent_run_id`；只解释未改变的结果不重算。

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

- 性别影响大运顺逆，具体必填性按工具模型；`dayun_analysis` 要求 `gender` 与 `analysis_age`。
- 对实际 Schema 必填小时的计算，缺小时只阻止该次计算；先简短核对，用户已说不知道或无法提供时停止同项追问。可以解释已有结果、传统概念或已给的现实选项；确有不依赖缺项的工具时再选择适用路线。不能省略或擅自填 0 当作无时盘。只有「上午」等时段不能复用某个精确时刻的命盘；用户明确选择假设时刻比较后分别标明假设，保留时段内不稳定结论。
- 用户用日常语言提供历法、日期、时间范围和城市即可，由助手按合同转译参数。这些 `birth_*` 接口使用公历；历法确有歧义时才核对，农历先转换。出生时区依出生地与历史日期解析并核对实际回执，不要求用户自己提供 IANA 名称，也不能直接套当前聊天时区。真太阳时默认开启，通常省略开关沿用引擎默认；显式 `true` 表示必须完成校正，缺地点／经度时可能报错，不能机械抄入默认值。仅按用户明确要求关闭；未知经度可省略，以返回精度限制说明，不能猜经度。
- 出生地用于地点与太阳时解析，给到城市并保留返回精度；支持的城市交给引擎解析，不要求用户自行查经纬度。所选接口确需显式坐标且不能可靠解析时再说明补充方式，不能把示例坐标当事实。中式工具不能套入西占 `birth_latitude` 参数。

**分析时点（按所选工具核对）**

```
--analysis-year 2026 --analysis-month 6 --analysis-day 18   # 想看哪天的运
--analysis-age 35                                            # dayun_analysis 按虚岁定位大运
--target-year 2026                                           # liunian_analysis 指定流年
```

八字九维专项工具（marriage/career/...）会自动推算当前大运、流年，用户不用懂大运。`--dayun-pillar`/`--liunian-pillar` 只是手动覆盖，正常别传。

出生时点使用 `birth_*`，分析时点使用该工具的 `analysis_*` 或 `target_*`。未指定的当前时间才由引擎取当前值；需要复现时传带时区 ISO `as_of`，它不能替代明确的分析年月日，也不补出生时刻。起卦等要求显式时间的工具仍须按实际必填项传入。

**西占核心盘、关系盘与推运分别核对合同：** 核心盘的经纬度可由引擎从已支持的 `birth_place` 解析，不要求用户自己查坐标；核对实际解析来源、时区与精度。地点不能解析时再补必要资料，不接受默认未知地点作真实位置。关系盘与西占推运需显式经纬度。核心／关系盘默认民用钟时，`use_true_solar_time=false`；不要把中式工具默认太阳时套过来。推运按自身实际 Schema 核对。

```
--birth-latitude 39.90 --birth-longitude 116.40   # 核心盘可按支持城市解析；关系/推运需明确坐标
--birth-timezone Asia/Shanghai
--hsys 3            # 核心/关系盘整型宫制 0..8；3 = Placidus
--zodiacal 0        # 核心/关系盘：0=回归，1=恒星
# 西占推运改用 --house-system P --zodiac-type Tropic
# 目标时间分别传 --analysis-year、--analysis-month、--analysis-day
# 精确目标钟时另传 --analysis-hour 12 --analysis-minute 0（按出生时区）
```

西占聚合推运及 11 个单项技法的 `analysis_hour` / `analysis_minute` 按
`birth_timezone` 解释，显式零值有效；省略时分别沿用出生小时／分钟以兼容日期级
调用。需要精确分析时刻时两项都传，并核对 `analysis_context.analysis_datetime`。
`as_of` 只冻结缺省日期的当前时钟；`return_timezone` 转换同一时刻到分析地点，
不替代输入时区。REST 请求体、MCP 参数与 CLI 开关语义一致。

核心星盘优先使用 `swisseph`；缺包时可回退内置轨道近似，显式复杂宫制除外。西占推运/事件/生命周期缺 backend 时直接报错，不能按近似结果解读。`swisseph` 可导入仍可能使用 Moshier 模型，检查 `chart_profile.ephemeris_model` 与 `run_metadata.engine_is_approximate`。`pyswisseph` / `kerykeion` 是常规依赖，星历数据另行获取，见 [快速入门](../../docs/getting-started.md#星历数据与精度)。

---

## 全量工具地图（按家族）

每个场景 Skill 只需引用与自己相关的几个；这张表是全集，REST 公开 86 项，MCP 公开 87 项，目录共 88 条；CLI 可执行 87 条。名称/嵌套请求差异以 `describe` 和 [API 参考](../../docs/api-reference.md#24-三端能力边界) 为准。

### 八字 · 命主本命（snapshot_text）

- `bazi_birth`：完整命盘，含四柱三元、纳音、十神、藏干、格局调候、十二长生、当前大运流年、神煞。
- `analyze_destiny`：综合命理，八字 + 喜用 + 格局，一站式。

### 八字 · 九大专项（结构化 JSON，自动带时机信号）

`bazi_marriage` 婚姻、`bazi_romance` 正缘桃花、`bazi_career` 事业、`bazi_wealth` 财运、`bazi_health` 健康、`bazi_children` 子女、`bazi_education` 学业、`bazi_personality` 性格、`bazi_relatives` 六亲。

均接受 `--analysis-year/month/day`，内部自动推大运/流年（结果在 `<dim>_analysis.timing_context`）。返回 JSON 包含 `{analysis_type, <dim>_analysis, snapshot_text, snapshot_export}`；精确读取 `<dim>_analysis`，快照用于摘要。

### 配合度 · 双人（结构化 JSON）

- `two_person_compatibility`：八字合婚 / 合作配合度，含综合分、五行互补、共同喜用、优势/挑战/建议。两人各一套 `--person1-*` / `--person2-*` 字段（名/年/月/日/时/性别）。
- `sukuyo_compatibility`：宿曜 27 宿双人相性（按月亮经度），有方向性。两人各一套 `--person1-date/-time/-zone/-lat/-lon` 等字段。

### 时运 · 推命（snapshot_text）

`timing_analysis` 时运综合、`dayun_analysis` 大运、`liunian_analysis` 流年、`liuyue_analysis` 流月、`liuri_analysis` 流日、`liushi_analysis` 流时、`jieqi_timeline_analysis` 节气时间轴、`jieqi_year` 节气年表、`nongli_time` 农历时间换算。

**综合 vs 颗粒怎么选**：`timing_analysis` 是聚合器，一次把当前大运 + 流年（+ 流月等）的综合影响给全，问「最近运势/这两年怎么样」用它；`dayun_analysis`/`liunian_analysis`/… 是单层颗粒，只盯某一层（如就看某个大运、某个特定流年）才单独调。综合工具的内容与颗粒工具有意重叠，别为了拼一个时运全景去逐层调颗粒再自己拼，那是 `timing_analysis` 的活。

### 占卜 · 问事起卦（按实际输出读取）

- `meihua_analysis`：梅花易数，读取结构化 `meihua` / `summary` / `interpretation`，`--question`（可选）+ 起卦时间必填 `--analysis-year/month/day/hour`（要按当下起卦就传当前日期时间）。
- `sixyao`：六爻，`--question`，CLI 手摇用 `--coins`（六掷之和，初爻到上爻，每项 6/7/8/9）或 `--gua-code`，也可按时间起。`lines` 对象列表使用 REST/MCP 传入，CLI 不解析对象字符串。
- `tongshefa`：统摄四卦组合，读取实际 `taiyin/taiyang/shaoyang/shaoyin`；固定默认不是用户起卦，不实现蓍草十八变／大衍随机起卦。
- `gua_lookup` / `gua_meiyi`：卦象查询 / 卦义。
- `qimen`：奇门遁甲，起局 + 用神。
- `taiyi`：太乙神数。
- `jinkou`：金口诀，`--di-fen` 地分 + 时间。
- `liureng_gods`：大六壬起课。
- `liureng_runyear`：六壬流年（行年）。
- `suzhan`：宿占 / 二十八宿。
- `otherbu`：解读用户实际提供的行星／星座／宫位骰面；不自动随机抽骰，不能把默认骰面当本次抽取。
- `sanshiunited`：三式合参（奇门 + 太乙 + 六壬同盘）。

### 紫微斗数（snapshot_text）

- `ziwei_birth`：紫微命盘（含十二宫安星）。
- `ziwei_horoscope`：紫微六层运限与动态四化。
- `ziwei_rules`：紫微规则查询（`--year-stem`）。

### 占星 · 出生盘与关系盘

- `astro_chart`：标准盘。
- `astro_chart13`：13 扇区盘。
- `astro_hellen_chart`：希腊盘。
- `astro_guolao_chart`：果老星宗。
- `astro_india_chart`：印度盘。
- `astro_germany_chart`：德国盘。
- `astro_relative_chart`：MCP / CLI 扁平关系盘；`astro_relative` 是 REST 的嵌套请求入口，尚未启用 CLI JSON 请求合同，不把两端名称当作任意互换的别名。扁平入口两人用 `--inner-birth-*` 和 `--outer-birth-*`（各需 year/month/day/hour/longitude/latitude，name/place/minute/timezone 可选），返回 JSON（见上）。

### 西占 · 推运（需要 backend，缺失时报错）

`western_timing_analysis` 时运综合、`solarreturn` 太阳返照、`lunarreturn` 月返、`transit` 行运、`solararc` 太阳弧、`givenyear` 指定年盘、`profection` 年小限、`pd`/`pdchart` 主限、`zr` 黄道释放、`firdaria` 法达星限、`decennials` 十年星限。

同八字时运的逻辑：`western_timing_analysis` 是综合聚合，要整体推运用它；`solarreturn`/`transit`/`profection`/… 是单一技法颗粒，只看某一术时单独调。两者内容有意重叠。

### 西占 · 事件与生命周期

事件工具：`astro_mundane`、`astro_extrareturns`、`astro_horary`、`astro_election`。

生命周期工具：`astro_harmonic`、`astro_planetary_ages`、`astro_triplicity_rulers`、`astro_lunation_phase`、`astro_distributions`、`astro_balbillus`、`astro_keypoints`、`astro_yearsystem129`、`astro_planetaryarc`、`astro_persiandirected`、`astro_agepoint`、`astro_vedicprog`、`astro_jaynesprog`。仅在需要相应技法时调用，完整输入先查 `describe`。

### 知识与导出 helper

- `knowledge_registry`：知识目录。
- `knowledge_read`：读取词条（`--domain --category --key`）。
- `export_registry`：导出注册表。
- `export_parse`：导出解析。

用于给一段结果补充传统词条释义。

---

## 读 snapshot_text 的速查（以八字为例）

引擎吐出的 `snapshot_text` 已经分好段，对应着事实。解读时按段取信号：

- `[起盘信息]`：真太阳时校正、农历、节气。先确认起盘对不对（出生地/时辰）。
- `[四柱与三元]`：年月日时柱、纳音、十神、藏干。日柱天干 = 日主（命主本人）。
- `[格局调候]`：月令格局（如正官格）、调候用神（如「主用丁」）、日主十二长生。用神 = 这个人最需要补的五行，是吉凶判断的轴。
- `[流年行运概略]`：当前大运、流年、流月，及五行力量增减。看时机就看这段。
- `[神煞...]`：桃花、驿马、华盖、天乙贵人、空亡、红鸾天喜等。神煞是色彩，别当铁口直断。

判吉凶的总原则：看某五行/十神是不是命主的喜用。喜用被生扶 = 顺；忌神当旺 / 喜用被克 = 有挑战。引擎已经把喜用、力量增减写在快照里，照着读即可，不要自己重排五行。

---

## 跨体系交叉印证（文化视角对照）

八字、紫微、西占采用不同的传统规则，但共享出生信息、历法或星历输入。多体系一致可用于整理文化视角，不是独立统计证据，也不能证明现实预测准确。用户确实需要多体系对照时，再调用两到三套并保留来源：

- 多套描述重合 → 合并说明哪些规则产生了共同描述，再与用户实际经验对照。
- 某结论只有一套提到 → 标出该体系与适用范围；另两系未提到不自动表示它较弱，也不补造旁证。
- 两套描述矛盾 → 先核对时区、坐标、太阳时策略和模型；输入一致后仍有分歧，分别呈现，不自行断言是用户的内在张力。

读法：先各看各的 `snapshot_text`/结构化字段，抓出每套最突出的 2–3 个信号，再横向比对哪些重合、哪些只此一家、哪些相反。重合处合并描述，相反处保留分歧，单一来源留余地。别把三套各背一遍堆给用户。

---

## 典型调用样例

```bash
# 八字本命盘
python3 -m fatebridge.cli --no-metadata bazi_birth \
  --name 小南 --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 \
  --birth-hour 14 --birth-minute 30 --birth-place 北京 --use-true-solar-time

# 八字婚姻专项（自动带当前大运/流年）
python3 -m fatebridge.cli --no-metadata bazi_marriage \
  --gender 女 --birth-year 1994 --birth-month 3 --birth-day 2 --birth-hour 9 --birth-place 上海

# 双人合婚
python3 -m fatebridge.cli --no-metadata two_person_compatibility \
  --person1-name 小A --person1-gender 男 --person1-birth-year 1992 --person1-birth-month 8 --person1-birth-day 15 --person1-birth-hour 14 \
  --person2-name 小B --person2-gender 女 --person2-birth-year 1994 --person2-birth-month 3 --person2-birth-day 2 --person2-birth-hour 9

# 流年看 2026
python3 -m fatebridge.cli --no-metadata liunian_analysis \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 --target-year 2026

# 梅花易数问事（起卦时间必填，按当下就传当前日期时间）
python3 -m fatebridge.cli --no-metadata meihua_analysis --question "这份 offer 该不该接" \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15

# 占星标准盘
python3 -m fatebridge.cli --no-metadata astro_chart \
  --name Mia --birth-year 1995 --birth-month 6 --birth-day 1 --birth-hour 8 --birth-minute 20 \
  --birth-latitude 31.23 --birth-longitude 121.47 --birth-place 上海
```

跑不通时永远的第一步：`python3 -m fatebridge.cli describe <tool>`。

---

## 全局调用纪律

权威全文与各场景的工具取舍见 `docs/scenario-routing.md`。本节是所有 onda 技能共享的执行铁律。

- **命盘复用**：综合命理画像调一次 `analyze_destiny`（已含命盘 + 喜用 + 格局），不要再调 `bazi_birth`；只要原始四柱才单用 `bazi_birth`。同一出生信息跨八字/紫微/西占复用，不重复采集。
- **聚合优先**：时运全景用 `timing_analysis` / `western_timing_analysis`，不连发多个单技法；只要一项才用单工具。
- **粒度匹配**：年级信号（如 `romance_timing`）不许说成「几月」，要月级才升级 `liuyue_analysis`，日级才 `liuri_analysis`。
- **首轮收口**：按已验证 `fields` 取结构化字段，开严格投影、关快照；`selected_sections` 只裁剪导出文本，不代替字段投影。仅文本结果按实际合同读取，不能通过关闭文本删掉唯一依据。
- **按问题核对资料**：使用已确认信息，由助手把日常表述转成参数；只核对会改变所选计算的缺项，不串行问每个字段。缺项仅限制依赖它的结论，已有部分先交付；用户明确不知道或无法提供时停止同项追问，说明可继续的解释或适用替代路线。合同已齐全不重复发现，报错先读 `error_code` 再改，不盲重试。

---

## 交叉印证与去重（防矛盾）

**主证 + 旁证 + 显式分歧**：需要个案计算时，按场景选择一个主证系统，其余只作旁证（加强/修正）；方法原理和已有结果的解释不为满足路由另开计算。系统间一致则合并去重；冲突则显式标注「两套口径不一」，不静默二选一。同一神煞在多个工具重复出现时，按当前场景取一个口径讲一次（如咸池在 romance = 机会 / marriage = 防烂桃花，合并讲一次）。各域主证分配见 [场景路由：交叉印证与去重](../../docs/scenario-routing.md#交叉印证与去重)。

## 家居风水基础计算

完整空间咨询使用独立 [onda-fengshui](../onda-fengshui/SKILL.md)：它整合下述工具、形态与桌面作者规则，核对现场事实和行动约束，并跟踪无规则／待确认项目。出生和宅向只对需要这些资料的层核对。

| 工具 | 应读取的层 | 输入要点 |
| --- | --- | --- |
| `fengshui_directions` | `layers.directions` | 固定后天方位；角度须明确参考北 |
| `fengshui_minggua` | `layers.minggua` | 公历 `birth_date`、含时区 `birth_at`、有效生年三选一；非立春当日无需小时，男女起算法未知则保留候选 |
| `fengshui_bazhai` | `layers.bazhai` | 坐山宅盘与逐人命盘独立；门床桌灶位置／朝向分开 |
| `fengshui_jinsuo` | `layers.jinsuo` | 明确砂／水／混合／未知分类及依据，不由物品名称推断 |
| `fengshui_annual_stars` | `layers.annual_stars` | 立春换年；固定宫数与临宫年星分开 |
| `fengshui_xuankong_natal` | `layers.xuankong_natal` | 磁北宅向、历史定运依据；中州派运山向／兼向替星；角度不明返回候选 |
| `fengshui_assess` | 三个独立基础层及显式选定的宅盘 | 住宅请求 JSON；逐人差异、规则来源／版本、覆盖缺失 |

这组工具不需要完整八字生辰；组合 CLI 用 `--request-file`，文件合同与 REST/MCP 请求一致。完整字段、可复制住宅请求和来源边界见 [家居风水](../../docs/fengshui.md)。合法缺失资料为 `partial`，不是引擎失败。三层的条件和时间范围不同，禁止合成总分、让户主覆盖其他住户，或把年盘说成完整玄空山向盘。玄空宅盘须显式选择 `methods` 的 `xuankong_natal` 并提供 `xuankong.period`，以历史事件定运，不用当前元运覆盖宅运。详见 [玄空合同及版本](../../docs/fengshui-xuankong.md)。金锁24山／形态元运、月盘和自动户型几何未实现。

```bash
python3 -m fatebridge.cli --no-metadata fengshui_minggua --effective-birth-year 1990 --gender-convention female
python3 -m fatebridge.cli --no-metadata fengshui_annual_stars --effective-year 2026
fatebridge fengshui_assess --request-file docs/examples/fengshui-home.json --compact
```
