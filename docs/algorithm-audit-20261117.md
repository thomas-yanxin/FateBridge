# 算法与公开工具核查记录（2026-11-17）

本次是全目录实际调用与完整源码机械普查的检查点。**语义算法清单、每一定义的实际执行与权威第三方逐项验收仍未完成，不能认证全仓专家水平或 SOTA。** 现有[细粒度初审索引](algorithm-inventory.md)继续保留原失败、未决与适用范围；不能把工具数量、方法合同、源码定义或职责条目混称为算法总数。

本页按版本保留各批证据；[最新延续](#source-eligibility-domain-round34)记录河洛／参评日期闭包、Swiss来源策略与几何源式的有限对照，累计二十七个独立根因／能力改进。原出生对象／独立工作进程、太阳交节主轴、离线同源坐标、实际参考点定义、子卯实体、丙子月官准入、起运／地磁换算、返照数值终止及校准收敛证据保持。此前调用和统计不自动升级为最新版本的全部验收。

## 本批根因修复与剩余缺口

首批实际修复六个根因。样本、重复字段、审读定义与三端调用均不计作额外优化问题；没有为满足10或50的数量要求拆分同一根因。

| 优先级 | 根因与自然修复 | 独立对照的有限结论 |
| --- | --- | --- |
| P0 | 普通年份的名义JD重复浮点拼接；统一使用既有精确日历并最终舍入 | 固定381920时刻中的148项非最近值消除；[完整分母](precision-acceptance.md#名义日历与标量tt的单次舍入) |
| P0 | UTC微秒在加入原子偏移前量化；精确求和后才交付标量TT | 原18469项非最近值消除；65536项与SOFA合成标量相同，但仍全部劣于其原两部表示，原强门槛未通过 |
| P0 | 已解TT点误套名义午夜别名并从舍入边界取秒60小数 | 全27闰秒的270边界观测分类及134项微秒符合原参考；[点语义与旧门槛](precision-acceptance.md#已解tt点的闰秒边界) |
| P0 | 精确TT构造先转换成Python UTC datetime，合法本地时刻跨UTC年界时溢出；改为复用整数日历 | 独立SOFA精确构造8控制中，原2溢出消除、6普通控制不变；仅验证调用者明确指定原子偏移的数值假设 |
| P1 | 分盘丢弃已有盘内度数，再从舍入后的总经度反算；直接交付同次分量 | 118224输入—分盘控制对原16800差异消除；[FLINT参考](jyotish-algorithm-audit.md#盘内度数与位置力合计的后续对照) |
| P1 | 位置力摘要与所选profile的求和路径不同，Rupa又除以已舍入总量；统一精确分量和分别交付 | 7168组固定分量原2906个字段差异消除，叶分量未变，不认证完整六力 |

八字原367条记录／321输入的17组工程政策差异与2项集合违规保持；123条有原典三档标注的记录仍未通用裁定，不能用未知、调权重或命例覆写消除。证据在`~/.codex/artifacts/fatebridge-20261117-bazi-p1/`。太乙的新[第三方实际执行对照](taiyi-independent-model-comparison-20261117.md)有233154个可比字段相同，另保留424项表示差异；原《金镜》288个两算仍有11项不同。共同原典及未查清的实现谱系不构成完全独立的权威认证。

首批新增13个项目回归节点只编写、未运行，均位于既有自包含CI文件；两处旧测试清理了名义／物理点语义错位，原独立来源、散列、容差和分母保留。实际优化问题仍少于50，按本轮批量约定没有启动pytest、CI、格式／类型检查或项目构建。独立源差分与实际协议调用分别记录。完整算法语义清点、全部参数分支、真实模型、安装包和部署验收，以及现实预测效度仍未完成。

## 起始快照分母

| 统计口径 | 实际数量 | 含义与边界 |
| --- | ---: | --- |
| 中央目录记录 | 93 | 按当前 `ToolSpec` 逐项记录；关系盘 REST 与 MCP 请求形状分列 |
| MCP 工具／REST 业务入口／CLI 工具 | 92／91／92 | 13 个 MCP family；不含另列的发现、健康与结果读取入口 |
| 唯一登记 `method_id` | 65 | 62 项 calculation、3 项 reference；包含复合方法，均为 `not_fully_accepted` |
| 生产 Python 文件 | 1,154 | 对 `src/fatebridge` 全部 Python 文件作独立 AST 遍历 |
| 具名定义 | 7,200 | 5,288 个函数／方法、1,912 个类；保留行号及 getter／setter 各自身份 |
| 初审索引直接具名定义／未直接具名定义 | 3,715／3,485 | 后者包含合同、支持、适配与计算，不能称为 3,485 个遗漏算法 |
| 直接顶层赋值／注解位置 | 2,691 | 其中 2,538 个位置未直接具名；重复赋值各自保留 |
| 模块结构语句位置 | 2,741 | 其中 2,588 个位置未直接具名；与赋值队列重叠，不能相加 |
| 初审职责条目／源码位置组 | 10,146／2,499 | 包括计算、规则、参数与支持职责，仍含复合待拆项 |
| 生产数据文件 | 355 | 路径、字节数与原内容单列；不是 355 个算法，来源与实际消费关系仍需语义核查 |

机械普查与现有初审索引统计一致。源码层面没有用目录遗漏解释既有差异，也没有把具名登记当作已逐项调用或通过。数据表、公式系数、原典转录、非默认选项及连续输入域继续是独立审查队列。

## 处理优先级

沿用[初审清单的排序规则](algorithm-inventory.md#审查优先级与完成条件)：先看错误传播范围和结果影响，同级先处理已复现且有独立可比参考的失败。

| 优先级 | 计算与规则范围 | 验收要点 |
| --- | --- | --- |
| P0 | 民用时刻消歧、UTC／UT1／TT／TDB、太阳钟、农历日序、干支日时、交节；共享星历、光路、坐标框架、宫轴与地平事件 | 固定时标、历法、坐标系、源版本和单位，保留所有原始失败与预先确定的误差门槛 |
| P1 | 各体系定盘与基础规则：八字、紫微、奇门、六壬／金口诀、太乙、梅花／六爻、河洛／参评、宿曜、西占宫制、印占分盘／六力、人类图、果老、风水方位／宅盘／地磁 | 按细粒度规则、原典版本及可区分反例比较，不能以软件多数或支持职责替代核心算法 |
| P2 | 流运、运限、推运、返照、时主、事件搜索、达沙、关系盘、布局条件、判词、专题与合参 | 先核上游输入，再查区间端点、顺逆序和作用条件；工程指数不作现实成功概率 |
| P3 | 来源索引、资料读取、请求／输出合同、投影、快照、导出、结果读取 | 核对公开范围与完整事实交付；通过不提高 P0—P2 的独立验收等级 |

每一算法的第三方比较还需具名来源与版本、原始输入、比较量／单位、预先固定门槛和完整失败分母。原典符合、数值算术、物理观测和现实预测分别验收；`>=` 必须落到这些具体比较量，不能由单个“通过”标签代替。

## 公开工具逐项实际调用

复用当前 `tests/fixtures/surface_payloads.py` 的代表请求，固定 `as_of=2026-11-16T16:00:00Z`（北京时间 2026-11-17 00:00）。实际完成 **275 次调用：REST 91／91、MCP 92／92、CLI 92／92 均返回成功**。REST 使用本地 ASGI 客户端，MCP 使用 in-process FastMCP 客户端，CLI 经实际参数解析与 `run`；本批没有启动 pytest、CI、格式检查或构建。

下表 `200` 是 REST 状态码，`0` 是 MCP 无错误响应或 CLI 返回码，`—` 表示该目录记录没有此端。它们只说明这一个代表请求的调用状态，**不是第三方算法比较通过，也不是该工具全部选项、内部定义或整个输入域已执行**。

| 目录 key | family | REST 路由与状态 | MCP 工具与状态 | CLI 命令与状态 |
| --- | --- | --- | --- | --- |
| `analyze_destiny` | `bazi` | — | `analyze_destiny` · 0 | `analyze_destiny` · 0 |
| `bazi_birth` | `bazi` | `/api/bazi/birth-chart` · 200 | `bazi_birth` · 0 | `bazi_birth` · 0 |
| `bazi_marriage` | `bazi` | `/api/bazi/marriage` · 200 | `bazi_marriage` · 0 | `bazi_marriage` · 0 |
| `bazi_career` | `bazi` | `/api/bazi/career` · 200 | `bazi_career` · 0 | `bazi_career` · 0 |
| `bazi_wealth` | `bazi` | `/api/bazi/wealth` · 200 | `bazi_wealth` · 0 | `bazi_wealth` · 0 |
| `bazi_health` | `bazi` | `/api/bazi/health` · 200 | `bazi_health` · 0 | `bazi_health` · 0 |
| `bazi_children` | `bazi` | `/api/bazi/children` · 200 | `bazi_children` · 0 | `bazi_children` · 0 |
| `bazi_education` | `bazi` | `/api/bazi/education` · 200 | `bazi_education` · 0 | `bazi_education` · 0 |
| `bazi_personality` | `bazi` | `/api/bazi/personality` · 200 | `bazi_personality` · 0 | `bazi_personality` · 0 |
| `bazi_relatives` | `bazi` | `/api/bazi/relatives` · 200 | `bazi_relatives` · 0 | `bazi_relatives` · 0 |
| `bazi_romance` | `bazi` | `/api/bazi/romance` · 200 | `bazi_romance` · 0 | `bazi_romance` · 0 |
| `bazi_source_compare` | `bazi` | `/api/bazi/compare-sources` · 200 | `bazi_source_compare` · 0 | `bazi_source_compare` · 0 |
| `two_person_compatibility` | `compatibility` | `/api/bazi/compatibility` · 200 | `two_person_compatibility` · 0 | `two_person_compatibility` · 0 |
| `timing_analysis` | `timing` | `/api/bazi/timing` · 200 | `timing_analysis` · 0 | `timing_analysis` · 0 |
| `dayun_analysis` | `timing` | `/api/bazi/timing/luck-cycles` · 200 | `dayun_analysis` · 0 | `dayun_analysis` · 0 |
| `liunian_analysis` | `timing` | `/api/bazi/timing/yearly` · 200 | `liunian_analysis` · 0 | `liunian_analysis` · 0 |
| `liuyue_analysis` | `timing` | `/api/bazi/timing/monthly` · 200 | `liuyue_analysis` · 0 | `liuyue_analysis` · 0 |
| `liuri_analysis` | `timing` | `/api/bazi/timing/daily` · 200 | `liuri_analysis` · 0 | `liuri_analysis` · 0 |
| `liushi_analysis` | `timing` | `/api/bazi/timing/hourly` · 200 | `liushi_analysis` · 0 | `liushi_analysis` · 0 |
| `jieqi_timeline_analysis` | `timing` | `/api/calendar/solar-term-timeline` · 200 | `jieqi_timeline_analysis` · 0 | `jieqi_timeline_analysis` · 0 |
| `jieqi_year` | `timing` | `/api/calendar/solar-terms` · 200 | `jieqi_year` · 0 | `jieqi_year` · 0 |
| `nongli_time` | `timing` | `/api/calendar/lunar-time` · 200 | `nongli_time` · 0 | `nongli_time` · 0 |
| `gua_lookup` | `divination` | `/api/divination/gua` · 200 | `gua_lookup` · 0 | `gua_lookup` · 0 |
| `gua_meiyi` | `divination` | `/api/divination/gua/meanings` · 200 | `gua_meiyi` · 0 | `gua_meiyi` · 0 |
| `meihua_analysis` | `divination` | `/api/divination/meihua/time-cast` · 200 | `meihua_analysis` · 0 | `meihua_analysis` · 0 |
| `meihua_cast` | `divination` | `/api/divination/meihua/cast` · 200 | `meihua_cast` · 0 | `meihua_cast` · 0 |
| `tongshefa` | `divination` | `/api/divination/combine-four-gua` · 200 | `tongshefa` · 0 | `tongshefa` · 0 |
| `sixyao` | `divination` | `/api/divination/liuyao` · 200 | `sixyao` · 0 | `sixyao` · 0 |
| `canping` | `divination` | `/api/divination/canping` · 200 | `canping` · 0 | `canping` · 0 |
| `heluo` | `divination` | `/api/divination/heluo` · 200 | `heluo` · 0 | `heluo` · 0 |
| `suzhan` | `divination` | `/api/divination/suzhan` · 200 | `suzhan` · 0 | `suzhan` · 0 |
| `sukuyo_compatibility` | `compatibility` | `/api/compatibility/sukuyo` · 200 | `sukuyo_compatibility` · 0 | `sukuyo_compatibility` · 0 |
| `otherbu` | `divination` | `/api/divination/astrology-dice/interpret` · 200 | `otherbu` · 0 | `otherbu` · 0 |
| `sanshiunited` | `divination` | `/api/divination/sanshi` · 200 | `sanshiunited` · 0 | `sanshiunited` · 0 |
| `ziwei_birth` | `metaphysics` | `/api/ziwei/birth-chart` · 200 | `ziwei_birth` · 0 | `ziwei_birth` · 0 |
| `ziwei_horoscope` | `metaphysics` | `/api/ziwei/timing` · 200 | `ziwei_horoscope` · 0 | `ziwei_horoscope` · 0 |
| `ziwei_rules` | `metaphysics` | `/api/ziwei/rules` · 200 | `ziwei_rules` · 0 | `ziwei_rules` · 0 |
| `liureng_gods` | `metaphysics` | `/api/liuren/chart` · 200 | `liureng_gods` · 0 | `liureng_gods` · 0 |
| `liureng_runyear` | `metaphysics` | `/api/liuren/timing/yearly` · 200 | `liureng_runyear` · 0 | `liureng_runyear` · 0 |
| `qimen` | `metaphysics` | `/api/qimen` · 200 | `qimen` · 0 | `qimen` · 0 |
| `taiyi` | `metaphysics` | `/api/taiyi` · 200 | `taiyi` · 0 | `taiyi` · 0 |
| `jinkou` | `metaphysics` | `/api/jinkou` · 200 | `jinkou` · 0 | `jinkou` · 0 |
| `export_registry` | `export` | `/api/export/formats` · 200 | `export_registry` · 0 | `export_registry` · 0 |
| `export_parse` | `export` | `/api/export/parse` · 200 | `export_parse` · 0 | `export_parse` · 0 |
| `knowledge_registry` | `knowledge` | `/api/knowledge/catalog` · 200 | `knowledge_registry` · 0 | `knowledge_registry` · 0 |
| `knowledge_read` | `knowledge` | `/api/knowledge/read` · 200 | `knowledge_read` · 0 | `knowledge_read` · 0 |
| `human_design` | `astro` | `/api/human-design/chart` · 200 | `human_design` · 0 | `human_design` · 0 |
| `astro_chart` | `astro` | `/api/astrology/chart` · 200 | `astro_chart` · 0 | `astro_chart` · 0 |
| `astro_chart13` | `astro` | `/api/astrology/thirteen-sector-chart` · 200 | `astro_chart13` · 0 | `astro_chart13` · 0 |
| `astro_hellen` | `astro` | `/api/astrology/hellenistic-chart` · 200 | `astro_hellen_chart` · 0 | `astro_hellen_chart` · 0 |
| `astro_guolao` | `astro` | `/api/astrology/guolao-chart` · 200 | `astro_guolao_chart` · 0 | `astro_guolao_chart` · 0 |
| `astro_india` | `astro` | `/api/astrology/vedic-chart` · 200 | `astro_india_chart` · 0 | `astro_india_chart` · 0 |
| `astro_vimshottari` | `astro` | `/api/astrology/vimshottari-dasha` · 200 | `astro_vimshottari` · 0 | `astro_vimshottari` · 0 |
| `astro_germany` | `astro` | `/api/astrology/hamburg-midpoint-chart` · 200 | `astro_germany_chart` · 0 | `astro_germany_chart` · 0 |
| `astro_relative` | `astro` | `/api/astrology/relationship-chart` · 200 | — | — |
| `astro_relative_chart` | `astro` | — | `astro_relative_chart` · 0 | `astro_relative_chart` · 0 |
| `western_timing_analysis` | `western_timing` | `/api/astrology/timing` · 200 | `western_timing_analysis` · 0 | `western_timing_analysis` · 0 |
| `solarreturn` | `western_timing_tool` | `/api/astrology/timing/solar-return` · 200 | `solarreturn` · 0 | `solarreturn` · 0 |
| `lunarreturn` | `western_timing_tool` | `/api/astrology/timing/lunar-return` · 200 | `lunarreturn` · 0 | `lunarreturn` · 0 |
| `transit` | `western_timing_tool` | `/api/astrology/timing/transit-chart` · 200 | `transit` · 0 | `transit` · 0 |
| `solararc` | `western_timing_tool` | `/api/astrology/timing/solar-arc` · 200 | `solararc` · 0 | `solararc` · 0 |
| `givenyear` | `western_timing_tool` | `/api/astrology/timing/chart-for-year` · 200 | `givenyear` · 0 | `givenyear` · 0 |
| `profection` | `western_timing_tool` | `/api/astrology/timing/profection` · 200 | `profection` · 0 | `profection` · 0 |
| `pd` | `western_timing_tool` | `/api/astrology/timing/primary-directions` · 200 | `pd` · 0 | `pd` · 0 |
| `pdchart` | `western_timing_tool` | `/api/astrology/timing/primary-directions-chart` · 200 | `pdchart` · 0 | `pdchart` · 0 |
| `zr` | `western_timing_tool` | `/api/astrology/timing/zodiacal-releasing` · 200 | `zr` · 0 | `zr` · 0 |
| `firdaria` | `western_timing_tool` | `/api/astrology/timing/firdaria` · 200 | `firdaria` · 0 | `firdaria` · 0 |
| `decennials` | `western_timing_tool` | `/api/astrology/timing/decennials` · 200 | `decennials` · 0 | `decennials` · 0 |
| `astro_harmonic` | `western_lifespan` | `/api/astrology/harmonic-chart` · 200 | `astro_harmonic` · 0 | `astro_harmonic` · 0 |
| `astro_planetary_ages` | `western_lifespan` | `/api/astrology/timing/planetary-ages` · 200 | `astro_planetary_ages` · 0 | `astro_planetary_ages` · 0 |
| `astro_triplicity_rulers` | `western_lifespan` | `/api/astrology/timing/triplicity-ruler-periods` · 200 | `astro_triplicity_rulers` · 0 | `astro_triplicity_rulers` · 0 |
| `astro_lunation_phase` | `western_lifespan` | `/api/astrology/timing/lunar-phase-progressions` · 200 | `astro_lunation_phase` · 0 | `astro_lunation_phase` · 0 |
| `astro_distributions` | `western_lifespan` | `/api/astrology/timing/bounds-directions` · 200 | `astro_distributions` · 0 | `astro_distributions` · 0 |
| `astro_balbillus` | `western_lifespan` | `/api/astrology/timing/balbillus-periods` · 200 | `astro_balbillus` · 0 | `astro_balbillus` · 0 |
| `astro_keypoints` | `western_lifespan` | `/api/astrology/timing/numeric-aspect-periods` · 200 | `astro_keypoints` · 0 | `astro_keypoints` · 0 |
| `astro_yearsystem129` | `western_lifespan` | `/api/astrology/timing/planetary-periods-129-years` · 200 | `astro_yearsystem129` · 0 | `astro_yearsystem129` · 0 |
| `astro_planetaryarc` | `western_lifespan` | `/api/astrology/timing/planetary-arc-directions` · 200 | `astro_planetaryarc` · 0 | `astro_planetaryarc` · 0 |
| `astro_persiandirected` | `western_lifespan` | `/api/astrology/timing/persian-directions` · 200 | `astro_persiandirected` · 0 | `astro_persiandirected` · 0 |
| `astro_agepoint` | `western_lifespan` | `/api/astrology/timing/age-point` · 200 | `astro_agepoint` · 0 | `astro_agepoint` · 0 |
| `astro_vedicprog` | `western_lifespan` | `/api/astrology/timing/sidereal-progressions` · 200 | `astro_vedicprog` · 0 | `astro_vedicprog` · 0 |
| `astro_jaynesprog` | `western_lifespan` | `/api/astrology/timing/declination-progressions` · 200 | `astro_jaynesprog` · 0 | `astro_jaynesprog` · 0 |
| `astro_mundane` | `western_event` | `/api/astrology/events/mundane-ingress-chart` · 200 | `astro_mundane` · 0 | `astro_mundane` · 0 |
| `astro_extrareturns` | `western_event` | `/api/astrology/events/planetary-returns` · 200 | `astro_extrareturns` · 0 | `astro_extrareturns` · 0 |
| `astro_horary` | `western_event` | `/api/astrology/events/horary-chart` · 200 | `astro_horary` · 0 | `astro_horary` · 0 |
| `astro_election` | `western_event` | `/api/astrology/events/evaluate-election-time` · 200 | `astro_election` · 0 | `astro_election` · 0 |
| `fengshui_directions` | `fengshui` | `/api/fengshui/directions` · 200 | `fengshui_directions` · 0 | `fengshui_directions` · 0 |
| `fengshui_minggua` | `fengshui` | `/api/fengshui/minggua` · 200 | `fengshui_minggua` · 0 | `fengshui_minggua` · 0 |
| `fengshui_bazhai` | `fengshui` | `/api/fengshui/bazhai` · 200 | `fengshui_bazhai` · 0 | `fengshui_bazhai` · 0 |
| `fengshui_jinsuo` | `fengshui` | `/api/fengshui/jinsuo` · 200 | `fengshui_jinsuo` · 0 | `fengshui_jinsuo` · 0 |
| `fengshui_annual_stars` | `fengshui` | `/api/fengshui/annual-stars` · 200 | `fengshui_annual_stars` · 0 | `fengshui_annual_stars` · 0 |
| `fengshui_monthly_stars` | `fengshui` | `/api/fengshui/monthly-stars` · 200 | `fengshui_monthly_stars` · 0 | `fengshui_monthly_stars` · 0 |
| `fengshui_xuankong_natal` | `fengshui` | `/api/fengshui/xuankong-house-chart` · 200 | `fengshui_xuankong_natal` · 0 | `fengshui_xuankong_natal` · 0 |
| `fengshui_assess` | `fengshui` | `/api/fengshui/assess` · 200 | `fengshui_assess` · 0 | `fengshui_assess` · 0 |

相同序列化请求之间，排除 `run_metadata` 后的完整业务输出共有 272 组端间比较：260 组精确相同、8 组因代表请求形状或取值不同未比较、4 组有末位差异。后四组来自 `astro_india` 和 `astro_vimshottari` 的 CLI 对 REST／MCP；分别涉及 3、4 个 D9／D10 `degree_in_sign` 叶值，完整原值保留在 `business-difference-details.json`。本批期间 `core/jyotish/jyotish.py` 发生并行修改，源码版本发生漂移，因此这些观察不作为冻结同版本的三端一致性验收，也未改判为精确相同。

## 目录之外的发现与结果交付

另外实际读取 9 次 REST GET，覆盖 7 条不同路由：`/health`、`/ready`、`/metrics`、`/api/tools`、`/api/results/{result_id}`、`/api/results/{result_id}/pages`、`/api/results/{result_id}/verified`。分页和验证读取各补一个点路径请求，全部返回 200。

实际读取 9 种 MCP 资源（1 个固定资源、8 个资源模板）：

- `fatebridge://catalog/summary`
- `fatebridge://families/{family}`
- `fatebridge://tools/{tool}`
- `fatebridge://tools/{tool}/input`
- `fatebridge://results/{result_id}`
- `fatebridge://results/{result_id}/pages/{offset}`
- `fatebridge://results/{result_id}/fields/{path}/{offset}`
- `fatebridge://results/{result_id}/verified/{run_id}/{offset}`
- `fatebridge://results/{result_id}/verified/{run_id}/fields/{path}/{offset}`

另执行 CLI `list --json`、`discover --family bazi`、`describe bazi_birth --detail input` 及两种 `result-read`（全文第一页／点路径），均返回 0。结果读取复用本批原始 `bazi_birth` 完整结果，没有为读取重算。这里只覆盖成功样例，不认证全部鉴权、错误分支、分页输入域、stdio 子进程、真实模型行为或部署状态。这些支持入口不增加独立算法数。

## 原始证据与版本

本批起始 Git HEAD 为 `c63968b5fe11b59e24a37d8aec4bd2c3d87751ed`；开始时已有未提交改动，实际源码不能仅用该提交代表。外部产物目录为：

```text
~/.codex/artifacts/fatebridge-audit-20261117/inventory-surface
```

- `summary.json`、`definitions.json`、`module-bindings.json`、`module-statements.json`：完整机械分母与逐位置待审身份。
- `tools.json`、`inventory-rows.json`、`data-files.json`：93 条目录合同、初审映射与 355 个生产数据文件。
- `invocations.json`、`invocation-summary.json`、`requests/`、`outputs/`：275 次原始输入、完整返回及逐项状态；请求带精确样例身份，不能当作第三方真值。
- `surface-business-comparisons.json`、`business-difference-details.json`、`source-drift.json`：完整端间比较与保留差异、源码漂移。
- `auxiliary-summary.json`、`auxiliary/`：另列的 23 次发现与原结果读取响应。
- `initial-source/`：逐文件哈希一致时冻结的 1,154 个 Python 文件及 355 个生产数据文件；不包含运行环境之外的全部外部依赖与观测资料。
- `census.py`、`invoke_surface.py`、`invoke_auxiliary.py`、`summarize_surface.py`：本次原始审计程序。辅助脚本首次启动的同目录 `requests/` 命名空间遮蔽失败单独保存在 `auxiliary-shadowed-namespace.log`；从仓库目录经标准输入运行后完成，不计为产品故障。

起始逐文件清单的 SHA-256：

```text
source-files.json  4827acffb88010496eccae75e974652f8bc433e51337f07699c009a417a610c3
data-files.json    5fd1952094d7a5163121d14e46e49264c9135a53fb33ba38f042ef23f55c62cb
tools.json         c20a312ba1d6296a67aa9b503b4cfefb8c460487308f2f09e1704d7d5c9b7e6e
```

本报告没有删除旧测试、清空反例、放宽门槛或把来源路径存在改作来源验收。全仓语义清查和所有工具／定义的逐项权威对照继续进行；[当前算法状态](algorithm-status.md)及各领域原始失败保持独立含义。

## 时标与印占定向调用及清点增量

在本轮时标与印占的五个生产文件冻结后，另作 6 个工具／选项场景、共 18 次定向调用。REST 仍用本地 ASGI；MCP 改为独立新启动的真实 stdio 子进程；CLI 各自启动独立子进程。每次返回成功，排除 `run_metadata` 后的完整业务输出在三端精确相同。所改五个文件在调用前后 SHA-256 相同；本段不把起始 275 次调用升级为最终版本的全目录验收。

| 场景 | 公开工具与选项 | REST／stdio MCP／CLI | 完整业务输出 |
| --- | --- | --- | --- |
| 专用印占默认 | `astro_india_chart` | 200／0／0 | 三端精确相同 |
| 聚合印占默认 | `astro_chart`，`chart_variant=india_chart` | 200／0／0 | 三端精确相同 |
| Vimshottari 默认 | `astro_vimshottari` | 200／0／0 | 三端精确相同 |
| 印占非默认来源组合 | `astro_india_chart`，`saptavargaja_profile=raman_30`、`drekkana_profile=raman_36` | 200／0／0 | 三端精确相同 |
| 历史 TT 固定反例 | `astro_india_chart`，1964-02-06 12:04:54.308587 UTC，经度 0、纬度 51.5 | 200／0／0 | 三端精确相同；返回 TT 符合冻结精确分数的一次 binary64 舍入 |
| 普通历史公历观察 | `astro_guolao_chart`，1027-08-26 03:42:43.267583 UTC 式标签，经度 0、纬度 51.5 | 200／0／0 | 三端精确相同；仅为来源范围与协议观察 |

印占场景完整读取 `india.charts` 和 `india.strengths.sthana_bala`，包括 `summary`、`profile_comparison` 与 `drekkana_profile_comparison`。五个工具／选项场景的七曜在三端共 105 条交付记录，各记录的摘要 `total_virupa` 均与所选 Saptavargaja、Drekkana profile 的对应总分精确相同；这些是同一有限场景的运输重复，不是 105 个独立原典或第三方案例。源算术验收由领域独立报告另列。

1964 固定反例的独立冻结 TT 分数为 `42136105025861137882925761/17280000000000000000`，三端实际标量均为 `0x1.29a90007ce469p+21`，保留旧值 `0x1.29a90007ce46ap+21`。这里只核对该名义 UTC 式标签与已声明历史仿射偏移的算术，不认证物理时刻精度。1027 场景的前 1960 年路径仍经原生 `utc_to_jd`，公开 TT／UT1 的约定另属一层；不能用这一场景声称本次内部名义 JD 修复已获外部数值验收。

最终定向原始输入、完整输出、stdio 与 CLI 日志、所改五个源文件及前后哈希位于外部产物的 `final-directed/`，实际程序为 `final_directed.py`。同目录的 `final-census.json` 与 `final-census/` 列出修改后独立 AST 普查结果：

| 口径 | 起始快照 | 该阶段清点 |
| --- | ---: | ---: |
| 生产 Python 文件 | 1,154 | 1,154 |
| 函数／方法定义 | 5,288 | 5,289 |
| 类定义 | 1,912 | 1,912 |
| 全部具名定义 | 7,200 | 7,201 |
| 直接具名／未直接具名定义 | 3,715／3,485 | 3,718／3,483 |
| 初审职责条目 | 10,146 | 10,149 |
| 源码位置组 | 2,499 | 2,500 |
| 不同文件／符号组合 | 3,867 | 3,870 |
| 清单涉及源码文件 | 626 | 626 |
| 直接顶层赋值／注解位置（未具名） | 2,691（2,538） | 2,691（2,538） |
| 模块结构语句位置（未具名） | 2,741（2,588） | 2,741（2,588） |
| 生产数据文件 | 355 | 355 |

新增定义是精确名义日值载体 `UTCCalendar.julian_day_exact`，已有两个定义补入清单；清单增量不增加算法通过数量。公开目录仍为 93 条、MCP 92／REST 91／CLI 92、13 个 family、65 个唯一方法合同；全仓语义算法总数与逐项第三方验收仍未完成。

## 追加闰秒 TT 点的三端定向核对

随后 `physical_epoch.py` 修复已解 IEEE TT 点错误套用名义午夜别名的问题；`time_scales.py` 另有一次不改变语义的导入排版。上述 18 次定向调用的原版本身份继续保留，本节另冻结全部六个改动生产文件，不将两批混作同一版本。

只追加一个场景、三次调用：`astro_guolao_chart` 输入 2012-07-01 00:00:00 本地平太阳钟、经度 `-0.0018187053501605988`、纬度 40、`birth_clock_basis=local_mean_solar`、`use_true_solar_time=false`，省略民用时区。采用原复现文件指定的严格投影 `person_info.clock_conversion` 与 `guolao.profile`；REST 返回 200，新启动的真实 stdio MCP 和独立 CLI 子进程均返回无错误，完整投影业务结果在三端精确相同。

三端均实际返回：

| 事实 | 固定期望与实际返回 |
| --- | --- |
| TT binary64 | `0x1.2bd16c0197aebp+21` |
| UTC 标签 | `2012-06-30T23:59:60.999984+00:00` |
| 闰秒身份 | `utc_is_leap_second=true` |
| 标签一致性 | `person_info.clock_conversion.converted_utc`、`guolao.profile.utc_datetime` 和原生时间轴 `utc_label` 精确相同 |

六个改动生产文件在本批调用前后哈希一致。完整输入、投影、输出、stdio／CLI 日志、六文件源码及哈希清单保存在外部产物的 `final-leap-directed/`，程序为 `final_leap_directed.py`；独立固定点与来源入口见 `~/.codex/artifacts/fatebridge-physical-epoch-point-20261117/public-tool-reproducer.json`。

该经度通过生产逆算构造，仅用于证明公开工具能够到达预先冻结的 TT 点。期望来自已冻结的官方 SOFA `dat.c`／`cal2jd` 精确闰秒区间，不能把生产逆算输出当真值。本段是一个根因反例的三端交付核对，不增加独立算法通过数，不认证全部时标约定、物理钟精度或 SOTA；未运行 pytest／CI。

## 收拢时的源码与清点

最后的`TTInstant.from_utc`输入域修复发生在上述21次定向调用之后，只复用整数日历并删除三个旧模块常量。其8个固定SOFA数值控制另存，未把先前调用改写成这个版本的重新验收。普通控制的精确结果不变；新支持的UTC辅助年界只是明确偏移假设下的数值构造，未增加公开工具或更改请求／响应Schema。

<a id="primary-axis-continuation"></a>

## 同日延续：主时间轴、出生所有者与清单账本

本次延续新增**两个实际根因修复**，与前批六项合计八项；同一根因在多个消费者中的修复、受影响定义数、参考单元和实际调用均不拆成额外问题。累计仍未超过50，未运行pytest、CI、格式／类型检查、构建或合同检查。完整细算法清点、逐项优先级及每个定义的独立验收仍未完成，总目标继续保留，不能标记专家级或SOTA通过。

### 已解UT1不能被显示用UTC反写

`PhysicalEpoch.from_ut1`原来先从给定UT1取得TT，再把TT格式化为微秒UTC，并用该显示重新运行民用转换。固定种子历史输入共20000项，其中206项的UT1和TT均被移动一个标量JD末位，约20.117或40.233微秒；旧0.2毫秒容差没有发现这种主轴替换。现直接保留给定UT1和所选转换的TT，UTC仅供表示。与独立进程直接执行的原生Swiss方程比较，同一20000项主轴全部一致，原206项显示标签不变。11项小型参考和来源限制保存在[固定资料](../tests/data/ut1_primary_epoch_v1.json)；它是原作者相同模型的独立入口，不能称为第二套历史地球自转模型或物理观测真值。[Swiss接口](https://www.astro.com/swisseph/swephprg.htm)提供所选UT1与DeltaT关系，项目原有历史旗标政策保持。

实际公开调用又发现同一根因在出生链路继续传播：太阳钟回执保留原UT1，但`chart13`从显示datetime重建后，盘内TT／UT1仍移动一位。现在出生对象统一保存已解`PhysicalEpoch`，由`AstroBirthInfo.time_scales`提供时标，排盘、宫轴、Hamburg因子、印占、果老和主限消费者复用该所有者。原无datetime的`NativeSolarBirthInfo`仍保留独立边界；普通太阳钟输入也保存主轴，不由回执字典重造物理时刻。私有原生进程明确传递该类型及原出生对象身份；印占太阳显示也消费原主轴。零偏移样本保留名义主轴，实际改时刻和果老目标盘清除旧epoch。

时空中点及其本命消费者也统一保留已解轴。既有直接太阳出生对象组合在改前可复现同样的偏移；另512组合法分钟粒度民用输入未观察到偏移，后者不算失败或新增优化问题。改造期间独立静态审查发现Davison派生对象没有`recorded_datetime`，零样本交付可能解引用空值；已按既有“recorded或local”约定修复，并保留原失败记录，不把修复本轮引入的回归计入原始优化数。

### C04时标转换只依赖已选时标来源

`PhysicalEpoch.from_ut1`原来在检查所选来源之前无条件要求并初始化Swiss，造成原本可独立完成的IERS C04时标构造不可用。现在由已有`tt_from_ut1`管理提供者要求：默认DeltaT仍要求Swiss，已选C04直接用其固定日表。22个既有冻结SOFA／C04控制在无Swiss时均可构造并保留UT1；最大TT差约40.233微秒，在原0.2毫秒线内。完整C04独立FLINT参考的23638个日锚点和70911个内部控制原已为最近标量值，未改动该内核，也未把标量精度提升为SOFA两部表示。[ERFA/SOFA taiut1](https://github.com/liberfa/erfa/blob/v2.0.1/src/taiut1.c)直接消费IERS的UT1−TAI，不要求轨道星历。这项内部可用性修复不表示完整星盘可在缺少原生天文引擎时执行。

### 公开调用、独立复核与版本范围

延续阶段原始产物位于`~/.codex/artifacts/fatebridge-audit-20261117-round2/`。`calendar.md`及两份静态复核记录列出实际修复、保留反例和依赖边界；原始修改前／后结果与源码散列保存在`calendar/`。小型参考已加入精确Git忽略例外，没有放开历史大数据目录。

- `primary-ut1-transports/`：一个既有数值反例经构造的LAT输入到达择时工具，实际本地REST、独立新stdio MCP、单独CLI共三次成功；投影钟时业务相同，UT1和TT符合原参考。该阶段早于出生所有者的完整改造。
- `birth-axis-transports/`：在15个生产模块冻结后，`chart13`、印占及果老三个实际场景分别经上述三端共九次成功；所有回执与盘内主轴相同，完整投影业务三端相同，15文件前后散列相同。印占场景实际经过私有工作进程。
- `birth-axis-zero-transports/`：随后只对样本输出的可选记录修复追加显式零不确定性的`chart13`三端调用；其结果与最终散列单列，不将前九次调用改写成这个版本的全部重验。

这里的成功不代表全部工具、全部输入分支、安装包、真实模型、部署或预测验收。新增回归只编写、未运行，集中测试仍等待累计超过50个真实优化问题。

### 清单与仍未通过的核心规则

中央目录仍为93条记录、MCP／REST／CLI分别92／91／92个入口、13个family、83种请求模型和65个唯一method_id。当前[初审清单](algorithm-inventory.md)为10173项计算及支持职责、2510个位置组，覆盖627个实现文件；7202个源码定义中3728个直接具名、3474个尚未直接具名。这些口径均不等于独立算法总数；原逐行优先级及运行时字符串选择域仍未穷尽。

既有清单程序新增`--manifest`，复用中央目录、Schema缓存和方法合同，导出完整请求声明、类／基类源码、职责／来源／验收、待审位置和当前文件散列；大型账本保存在仓库外。它不执行一致性检查或算法验收，不生成新的通过标签，也不构成已证明调用图。新增十个具名定义包含计算、类型和包装，不能当作十项算法修复。

印占从作者网站重新读取Rao原书，768个贡献表单元及96次实际调用的9216个移位单元无差异；限定为所选原文表与移位符合，不是完整印占第三方软件验收，来源缺项不借其他作者覆盖。八字重新读取原页并保持参数做因果拆分：去掉QQ02的寅亥预算转移仍不能消除力量差异，SJ05又涉及从儿适用性；未改权重、阈值或冻结标签。原17组差异、两项约束违规和123条未裁定仍保留。详见产物内`jyotish.md`、`bazi.md`，不将审读或未发现新错计作优化或SOTA通过。

最终机械普查见外部产物`closing-census/`：具名定义仍7201，直接具名3718、未具名3483；职责10149、位置组2500、文件／符号3870、源码文件626。删除旧常量后，直接顶层绑定为2688位置／2685文件名称身份，其中2535位置待审；模块结构语句2738，其中2585待审。其余分母不变，完整355个生产数据文件仍只作队列，未授予语义来源验收。上述`final-census`保留为前一阶段记录，不覆盖原文件。

仓库只保留生产修正、现有测试中的回归、小型独立资料和审计导航；一次性脚本、完整大队列、构建的第三方参考与失败原件均在仓库外。原有未提交改动保留，本轮未提交、推送或发布。

<a id="solar-point-continuation"></a>

## 第三批延续：来源选择、两部日期与交节主点

本批新增**三个实际根因优化**，与此前八项合计十一项。两个算术所有者、多个交节消费者、样本数、审读定义数和三端重复调用均不拆成额外问题。累计仍未超过50，没有运行pytest、CI、格式／类型检查、构建、合同检查或`check_inventory()`。本批完整原件位于`~/.codex/artifacts/fatebridge-audit-20261117-round3/`。

### 显式解析来源不应依赖未选中的求根器

显式`analytic`原先仍先执行另一套原生求根，只有其成功才运行已选解析来源。现在在捕获的来源上下文内直接分派到所选求解器，年份范围由缓存键所有者提前校验；1800..2200输入年域、严格JPL冲突和私有相邻年边界政策保持。

同一2026年24项实际结果的模型、已选TT根和民用显示完全相同，未选原生求根调用24→0；令该未选求根器不可用时，原来失败、现在仍计算24个解析根。1799／2201拒绝、1800／2200许可及严格JPL冲突保留。证据在`analytic-routing/`；单次耗时观察不是性能基准，也不是解析太阳物理精度提升。最初诊断中的可变列表引用错误另存为`before-instrumentation-alias-error.json`，不算产品缺陷。

### 两部日期的间隔只在交付标量时舍入

`analytic_solar._epoch`及`reference_frames.precession_angles`原来在减历元、加第二部分和除单位时逐步舍入。现在用输入浮点数的精确分数完成该间隔，再舍入一次；公式、系数、模型和输入域保持。同一4096项冻结输入相对独立Decimal100／200位间隔参考，非最近标量值1115→0。小型来源资料见[两部间隔参考](../tests/data/solar_two_part_interval_v1.json)。

这是比[ERFA原C求值顺序](https://github.com/liberfa/erfa/blob/v2.0.1/src/pfw06.c)更强的原语算术标准，不能把1115项称为1115个原C违规或物理模型错误。256项`pfw06`实际原生对照中118个角字段改变，原作者数值线零失败，最大差约`1.388e-17`弧度；不保证全部下游向量逐点改善，也不宣称与原C逐位相同。`two-part-normalization-*`及`precession-native-after.json`保留原值和新值，独立静态复核见`analytic-review.md`。

### 已选交节TT点不能由显示日期重新定义

太阳求根本来给出标量或两部TT点，但果老原生节月／立春年比较从显示日期重建TT。6625个冻结的1960年前参考点中有44个显示回代变化；这只是同一根因的观测数。1687清明的原始根与独立CALCEPH／Skyfield参考均为`0x1.1d513159015b7p+21`，显示回代却为下一浮点数，晚约40.233微秒。前一点／原点／后一点原归卯／卯／辰，修复后按原半开定义归卯／辰／辰。

`SolarTerm`现在由实际求解者保留不可变`TTInstant`，内部来源字典明确使用`SolarTermProvenance`；果老年／月及风水原生探针直接消费主点。两部DE440的24项控制精确保留两部分，24项均不同于相加舍入的标量；私有TT对象不进入`as_dict()`或公开来源JSON。参评两个派生生产者与历史风水显示路径也按已解点反解，不靠显示回执重造根。1799派生立春的旧标量／点语义显示差12微秒，但都回到同一标量TT，没有把显示差异虚报为新的年界错误。

两组年／月前后邻点共六项有限分类控制符合原定义。新增三项聚焦回归位于`tests/astronomy/test_de441_solar.py`，只编写未运行。旧果老半开测试不再从公开日期反写TT，改为显式原生标量根及相邻浮点数；两部根的保留由独立回归覆盖，不用标量探针冒充其精确端点。完整静态审查见`solar-term-propagation-review.md`；原梅花公众日历回代门槛保留，没有用本修复改写旧失败。

### 实际运输核对及版本范围

- `solar-mode-transports/`：2026解析年表、1799解析范围拒绝、1687原生DE441年表各经本地REST ASGI、独立新stdio MCP和独立CLI，共九次实际调用。两组正常完整投影业务相同；范围拒绝为REST400、MCP错误、CLI退出1。原始错误对象不完全相同，严格相等仍记false；相同的`error/error_code/retryable`另列，状态和operation封装差异保留。八文件在调用前后哈希相同。
- `guolao-boundary-transports/`：公开无普通datetime本命输入加1900立春目标时刻，三端均返回目标TT与交节TT为`0x1.26ce75f3db0cfp+21`、年份1900，完整投影业务相同。此前重编码边界会错误取1899。与内部服务原件直接比较仍为false：现有公开边界移除七个内部完整性哈希；按`core.public_output`既有合同投影后的完整比较为true，没有忽略算法字段。十文件在调用前后哈希相同。
- 最初把聚合输入的`chart_variant`传给专用果老入口，三端均拒绝该多余字段；原失败保存在`guolao-boundary-invalid-wrapper/`。修正调用载荷后才得到上述成功，不修改公开Schema迁就诊断脚本。
- 最终显示补全后，`canping-boundary-transports/`对1800年公开输入返回的121项年界作完整投影三端比较，均成功且精确相同；首项1799立春为`17:55:30.291936+00:00`，符合已解点语义。`fengshui-historical-transports/`的1800年合成建成事件三端同样成功，完整宅运上下文相同，实际第六运起点消费1784历史DE440来源，保留默认上海时区当时`+08:05:43`显示。两个场景各三次调用，七个相关源码前后散列均相同；它们只核对实际交付，不提供独立物理或玄空原典认证。

前两组调用早于最后补齐的参评／历史风水显示路径，不升级为最终版本的全分支重验；后两组仅补核各自一个实际公开场景。参评／历史显示的定向数值观察及最终源码身份单列于`solar/`。合成输入只证明公开计算可达性与主点保留，不认证原始出生钟时、历史UTC、传统定盘唯一性或现实预测。

### 当前来源基线与清单

本批还用当前DE441前向计算重放15125个原始JPL／CALCEPH／Skyfield冻结参考历元，原0.001角秒线零超差、零域外，最大约`1.3581e-5`角秒。该基线发生于本批间隔算术改动前；DE441在此路径仅以固定J2000调用该岁差函数，间隔为零不变，但不把旧基线伪装成改后全图重跑。旧Moshier模型的15／21项一秒失败仍属旧模型，不是当前DE441的新失败或已被删除的义务；全部模型和版本身份保留。

占星骰、相位和本地适配三个所有者已完整审读，补登记30个原未具名定义与38个绑定；新增`SolarTermProvenance`只计支持契约。最终当前清单为10331职责／2572位置组／630实现文件，7203个定义中3759具名、3444仍未具名；明确优先级79组（P0 10、P1 33、P2 11、P3 25），2493组尚待语义归层。93目录记录、92／91／92三端入口、83请求模型与65方法合同均不变。它们都不是最终独立算法总数，详细账本与分母见[细粒度清单](algorithm-inventory.md)及外部`inventory.md`。

太乙原11个两算／3个位置差异与第三方424项表示差异、奇门9项来源未决均保留。新读原图支持阴一局主算／大将／参将均为五，以及所选神假条文用九地；没有为消除软件差异改成None或九天，也没有新增修复计数。全仓语义算法总数、完整逐项优先级、所有定义／选项实际执行、权威逐项比较、真实模型、安装和部署以及现实预测验收继续未完成，目标保持进行中。

<a id="offline-frame-continuation"></a>

## 第四批延续：离线同源宫轴与地平、完整入口声明

本批新增**一个实际根因修复**，累计十二项。UT1显示的旧根因传播、方法合同覆盖、审读定义、控制点及运输重复均不增加数值优化计数。未达到超过50项的门槛，未运行pytest、收集、CI、格式／类型、构建、合同检查或清单检查；按规定正常生成了一次按需调用合同，生成结果未产生文件差异，没有运行`--check`。原件位于`~/.codex/artifacts/fatebridge-audit-20261117-round4/`。

### 真黄道射线必须配匹配的赤道与恒星时

现行DE441回退射线已经采用Vondrak标量真黄道及77项章动，但无原生引擎的宫轴、地平仍采用Meeus平均恒星时、线性平均交角，并在已有TT时改用UT1求倾角。现在由共享`analytic_earth_attitude`复用射线的bias／岁差／章动生成同一个NPB、真交角和GAST，layout／chart／原生推运消费者传递原有TT；退役无生产消费者的旧`_gmst`，不保留平行旧公式或换系数拟合参考。

生产修改前固定7个历元乘6地点共42组，原作者Swiss角参数／制宫内核、ERFA LTP／NUMAT／S06／EORS／ATIOQ与独立90位ERA构成同源几何参考。原0.001角秒门槛下，84个轴值的77项超线及42个高度的42项超线均消除；修改后最大差约`5.4894e-7`及`3.0695e-10`角秒。远期大差值不是物理天空误差界；任意NPB的GST06运算性质也不认证S06远期外推或完整实测地球姿态。

固定合法公开输入为2024-03-20 06:30 UTC、东经174.34371536776604°、纬度0°、chart／整宫。默认来源且受控无原生引擎时，两版均保留UT1 `2460389.7708333335`、TT `2460389.771634074`；原太阳高度约−0.000602289°，误判`night`，独立同源几何为+0.000524964029101°，修复后为+0.000524964029119°并判`day`。经度用来将已固定的几何差距转成可审查的业务反例，不代表真实出生资料或错误发生率。

该同一输入随后经实际本地REST ASGI、新真实stdio MCP和独立CLI，返回200／0／0、`sect=day`及`Sun.above_horizon=true`，完整投影业务相同，八个生产文件前后散列相同。三端共用仓库外absence bootstrap控制可选原生依赖不可用，未为样本修改请求Schema；它不是实际卸载原生库后的安装包验收。默认UT1仍声明UTC近似，没有虚构C04公开参数、实测DUT1或未来闰秒。完整记录见`offline-frame-transports/`，源和根因报告见`calendar.md`。

最后用实际已安装原生引擎对同一请求另作三端调用，200／0／0且完整投影相同；实际源为`swieph`，`angle_method=swisseph`、`horizon_method=swisseph_true_altitude`，已选TT成功传入受管地平入口，八源散列仍稳定。其UT1按默认Swiss模型，与无原生的UTC近似不同；没有要求两个不同来源模式的全部业务值相同。该一个实际原生场景与全部原生文件／分支验收分开，见`native-frame-transports/`。

独立参考初稿误带日周光行差，修改生产前已按地心几何关闭；原初稿和诊断旧签名错误均保存，正式before／after共用冻结的地心无折射定义，不用改门槛或丢失败换通过。小型[同源参考](../tests/data/offline_frame_v1.json)与三项聚焦回归已写未运行；新回归文件已加入自包含CI列表，只有准备工作，不记CI通过。旧极区／退化测试只将平均框架的构造输入换成同源真框架，原几何断言与容差保留。

### 已解UT1事件显示继续沿用物理点语义

`datetime_from_ut1`尚把求出的TT标量送入名义别名转换；现明确传`TTInstant`。27次闰秒的54项原固定控制在真实UT1→TT回代后，42项原别名差异降为0：包括原先把插秒末尾误显为午夜、把插秒前最后微秒误报不可表示两类。普通`datetime_from_tt(float)`的名义合同保持。这属于先前根因的遗漏消费者，**不另计修复**；没有声称真实日出恰好落在这些人工边界点。

原native SOFA257个姿态控制、4428个WGS84名义接收者控制也按各自原门槛观察，未见新超线；共享原图、旧太阳地平事件和物理失败继续保留，不以这组同模型对照代替测量EOP、光学事件或全部原生验收。

### 每个公开入口都有可读取的方法声明

原来唯一无方法声明的`bazi_personality`仍执行共享出生计算和自身符号／工程计算；其旧排除与本轮全工具范围不一致。现移除这项例外，登记共用出生合同及单独`bazi_personality_symbolic`合同，后者明确六个嵌套输出、0.5步计数、第三名截止与首位同分全部保留，以及FateBridge编辑词典的未认证状态。性格计算不读取性别／大运／流年参数，它们仅存在外层附带上下文；出生合同的整根依赖也不冒充细粒度因果证明。未改人格算法、计数、词义、权重或业务输出，更不增加优化问题数。

真实REST、独立CLI和新stdio MCP各成功一次，完整`personality_analysis`业务投影相同；REST／CLI／MCP公开完整发现均返回相同的两份声明，运行回执也实际登记它们。`not_fully_accepted`、`real_world_validity=not_established`、误差界null和语义证明false继续保留。原观察脚本的旧依赖名错误、REST查询项误放JSON导致的422及唯一修正均另存，不算领域计算失败。详见`personality-registration/transports/`及独立静态复核。

当前93条目录记录全部非空登记，共66个唯一方法（63 calculation、3 reference），不是66个全部验收算法。[完整入口优先级](algorithm-tool-priorities.md)已对93条记录分别排序：P0 4、P1 27、P2 55、P3 7；各入口内部共享时标仍属P0，不能由专题入口等级替代底层优先级。这一入口清点不加入源码职责分母，也不替代尚未完成的细算法逐项排序。

### 保留逐点差距，不按较小最大误差替换模型

原96个冻结JPL均时差参考分别比较当前UTC近似、已解UT1的原生调用、已有同TT／UT1太阳时路径。三者均在原5秒线内，最大差约0.20816／0.20533／0.08581秒，但后两者相对当前逐点有37／28项误差增大。原参考的站心／地心、DUT1缺项和未来钟时资格仍未对齐到更强精度门槛，故本批没有凭较小max更换通用太阳钟或授予新SOTA。原96项及每一点新旧误差、未决和源版本见`solar-clock-policy/`。

印占实际独立执行固定PyJHora `27500c0bb81640391c74479f897ece3f5ca2458c` 的削减与Pinda链，91个原输入／637目标／17199阶段字段中16758项确切相同，441项Rao原文缺项仍留分母，已定义值未见新差异。第三方默认处女乘子5和额外Lagna占据分别保留608／192项原字段差异，没有借默认参数覆盖所选Rao6或缺项。输入封装hash首轮诊断错误、原数值操作数和双程序重放身份保留；此项不增加修复数或认证全部八分法，见`jyotish/report.md`。

### 当前清单和未完成范围

九个完整所有者的47个当前定义已逐体登记；补具名25个定义并退役原已具名`_gmst`，覆盖净增24。最终清单为10473职责／2630位置组／636实现文件，7204定义中3783直接具名、3421仍未具名；149组明确归层（P0 41、P1 43、P2 12、P3 53），2481组仍待语义分类。源码定义、职责、入口和方法合同继续使用各自分母。外部`inventory-manifest.json`为6458411字节，SHA256 `7ffcdfc1e71f6f4d55f2c3ea15aff186ded6384097efce5289446fcfec1fcb53`，旧账本和原失败保留。

全仓细算法总数、所有定义／参数执行及权威逐项验收仍未完成；旧八字、奇门、太乙、其他原典和物理失败未被改判。没有提交、推送、安装发布或清除旧参考；一轮源内一致性和代表运输结果不认证全部算法、真实模型、部署或现实预测。目标继续进行。

<a id="source-identity-continuation"></a>

## 第五批延续：实际参考点定义与原失败的因果分离

本批新增**一个独立来源定义根因**，累计十三项。离线越界判断属于上一批同源框架的遗漏消费者，不另计数；来源审读、控制点、同一问题的多体影响及三端调用也不拆成额外问题。累计未超过50，继续不运行pytest、收集、CI、格式／类型、构建、生成合同检查或清单检查。原始材料在`~/.codex/artifacts/fatebridge-audit-20261117-round5/`。

### 当前DE441回退不能继续声明参考点未解析

现行回退已经统一读取DE441各行星系、EMB、地心月球及太阳，但旧`ephemeris_reference_points`仍只承认Pluto系统质心，把其余九个物理目标称为“不解析本体中心与系统质心”。按[JPL原始export格式](https://ssd.jpl.nasa.gov/ftp/eph/planets/ascii/ascii_format.txt)、[原作者读取指南](https://ssd.jpl.nasa.gov/ftp/eph/planets/fortran/userguide.txt)及[Swiss§2.4](https://www.astro.com/swisseph/swisseph.htm)核对实际组槽和Earth／Moon的EMRAT重建后，共同回执现交付已知的四个本体中心、六个行星系质心；平均交点单列理论点。点身份已知与物理精度认证分开，原`accuracy_certified=false`及全部位置、日速、光路和误差门槛保留。

在修改前冻结来源、输入和精确分类条件。直接十体差异9→0；原生控制0→0、单Saturn回退1→0、无原生回退9→0。三组完整角度、行星、宫位、古典层及行星时子树逐值不变；全部其他文本变化均可由旧说明精确替换为新说明得到，包括summary、snapshot_text及snapshot_export，原差异和逐处证明保留。它们是同一根因的观察量，不是十九个修复。

回执更新为v2，输出Schema追加可选`additional_source_urls`，当前回退附原JPL格式及实际DE441源地址。普通合同生成实际执行，`docs/contracts`无差异；没有执行`--check`。原生、单Saturn回退、无原生各在实际REST ASGI、新真实stdio MCP、独立CLI成功一次，200／0／0且模式内完整严格投影相同，12个生产源散列稳定。后两种模式使用仓库外受控bootstrap，不冒称实际卸载后的安装包或部署验收。后续生产变化不能自动继承这批版本身份，详见`reference-points/report.md`及各`*-transports/`。

既有natal参考点回归仅更新当前DE441回退的过时身份预期，原协议资料、场景、来源散列和数值线保留，未删除有效测试或运行套件。初版重复字典键、源下载证书失败及观察器漏列快照路径均有原记录和自然修正，不充作领域优化；重复键清理前的九次协议观察及原散列另存，不与最后版本混记。

### 离线古典层沿用同源倾角，并在投影舍入前判锥界

共享`reference_frames`现在持有只依赖TT的不可变`EclipticSourceFrame`，`earth_attitude`只在其上组合UT1相位；古典层直接复用源真交角，无需捏造UT1。原生层有已解TT时直接`calc(ECL_NUT)`，仅旧的UT1调用保留`calc_ut`。四个默认无原生公开输入的44个目标，原交角全未知／越界全未知；同一源射线与原作者Swiss交角／坐标转换及ERFA旋转对照，44项均相符（3真、41假），最大赤纬差约`6.06e-11″`。这仅验收所选理想黄道交角判据，不认证实际全年太阳赤纬极值；无原生日出求解器的行星时仍未知。

补齐后进一步保留了真实边界回归：原浮点赤纬经`asin`与度数转换，能把零黄纬节点误判越界。合法`astro_chart13`请求2039-01-14 23:35:02 UTC、经度0／纬度40／整宫，在受控无原生模式的实际REST／新stdio MCP／CLI均返回North Node越界为真；两个更早的微秒请求被现有Schema正确拒绝，拒绝原稿不充作产品失败，也未宣称已找到分钟级反例。

当前通用谓词从原始热带黄道向量直接比较`abs(z)>abs(sin(epsilon))`，采用独立96位上下文，不经赤纬展示舍入，没有节点名字特例、epsilon、deadband或参考标签回填。图表另传原始热带坐标，保留原`interpretation_states`与恒星黄道日速政策；旧仅赤纬API及缺输入未知的语义保持。修改前以独立FLINT0.9／Arb3.6的384位运算冻结200控制，含44原物理射线、44邻点、56整数秒及56通用几何点；旧标量判定15项不同，当前200项全部相同，不据此证明连续域的全部判定。

最后原生／单Saturn回退／无原生的默认chart各一组，加上述无原生chart13秒级反例，共四组请求再次经真实三端观察：十二次均200／0／0，模式内部完整严格投影相同，13个最终生产源散列前后稳定；节点现为假，三个默认模式的Moon越界仍为真。此前的参考点协议、中间同源交角版本和节点before均按原版本另存，不重复计成独立样本或新修复。四个聚焦回归只写未运行，原始参考与完整报告见`calendar.md`及[同源古典层](precision-acceptance.md#offline-classical-frame)。

### Human Design原Uranus超线没有换参考改判

原Swiss队列仍为23999／24000、1项失败；原Moshier仍为21762／24000、2238项失败。对原2236-03-01 12:00 TT输入的设计时刻`2537715.3390767695 TT`再次实际观察，Uranus相对原DE440仍差`3.8037582349033983″`，超过原2″线。FateBridge受管调用与相同配置的直接Swiss完整六坐标／返回旗标逐值相同，没有发现本样本的包装或TT转发错误。

同TT、同ICRF下，默认Swiss与原NASA45完整方向差约3.27249″，禁太阳偏折则约0.00007479″；但禁偏折对原DE440黄经差反而增至4.83353″。原Swiss透明太阳有效质量延拓、Skyfield点质量公式及NASA未完全公开的盘内分支不是一个函数；没有按某一更小残差切换默认或授予出版方Human Design软件口径。NASA31日期框架的共同偏移与偏折差分别保留，不以相对太阳差替换原绝对比较。

该差异虽不跨门线，仍使Uranus的Tone／Base由原参考1／5变为当前2／1；没有以同门线掩盖细分失败。四箭头只读取日地和交点Tone，不能据这个Uranus差异声称四箭头已变。官方88度、Definition、Tone左右和25–51权威四个窄定义及实际主链另行审读；不扩称其余原典、出版方坐标口径、完整线义或现实效力通过。本项新增修复数为0，独立Skyfield重放缺依赖的原失败也保留，详见`human-design-report.md`。

### 本批最终清单与仍未完成的范围

本批完整阅读18个相连坐标、宫位、参数与交付所有者，共3427行、96个定义、34项直接绑定，另逐体登记7项共用参数；不是96种独立算法。150组246项手写职责取代原13组57项粗映射，新增传播6组17项，原粗行原文另存；同源定义、来源限制、假设因子及未复核的书页均分开登记。最后只导出一次静态机器账本，没有调用`check_inventory()`。

最终快照为10679项职责／2773组／4101个文件符号映射／641个实现文件。1154个生产Python文件共7207定义（5292函数方法、1915类），3856直接具名，3351定义／766文件仍未直接具名；307组明确归层（P0 81、P1 68、P2 37、P3 121），2466组仍待语义归层。模块绑定2688位置中246具名、2442待审；这些分母互相重叠，不相加作算法数、修复数或已通过数。

`inventory-manifest.json`为6622519字节，SHA256 `5e25b94b958c1dd9ceea5c1d4e9f6ecd66e9d44df850b2c193756787d090f3f3`，与最终13个生产源身份一致。目录仍93记录、66共享方法（63 calculation／3 reference）；全部工具代表请求已有使用，不等同每个定义／参数已执行或独立验收。

完整细粒度算法数、全部定义的来源和分支比较、独立专家接受、安装包／真实模型／部署及现实预测仍未完成。八字17组差异与2项约束、太乙原表11项与异文、奇门9项义务及其余旧物理失败继续保留。下一批按原典实体关系与尚未具名的六爻职责继续推进；不把新一批未完成工作提前算入本批通过或优化数。

<a id="zi-mao-entities-continuation"></a>

## 第六批延续：子卯重见与合去实体后的关系准入

本批新增**一个实际来源规则根因**，累计十四项；同一规则在力量、候选回执、输出验证和公开端的传播不拆分计数。仍未超过50，未运行测试套件、收集、CI、格式／类型、构建、生成合同检查或清单检查。原件位于`~/.codex/artifacts/fatebridge-audit-20261117-round6/`；六爻本批范围及奇门补证已按各自有限分母完成，未完成的全仓目标与下一批候选另列。

### 原页要求保留实体重数，不能仅查子卯集合

重新目读固定[《秘本子平真诠》原扫描](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)的PDF24末栏至25首栏（印刷15—16页）：原文分别说明“二卯不刑一子”，以及戌合去一卯后“一合而一刑”。正文先说明按地支宫分论关系；甲／丙日主是示例语境，不以具体命例名或强弱标签触发修正。原页、正确来源散列及修改前条件均随本批`bazi`材料保留。

旧力量层只判断子卯集合齐全，就把全部实体记作active刑并应用既有0.9政策扣减。现在共享`punishment_resolution`保留实际柱位，只对原文明示的**一子二卯**读取同次已成立会合的cover：没有合去一卯时不作active刑，合去一卯后只有余下唯一子卯对参与。没有把此规则外推成一子三卯、反向重见、双重见或全部三刑通则。

离散政策版本为`completed_combination_zi_mao_entity_resolution_v3`，新增可复用实体谓词；力量层、候选状态和输出验证共用事实。回执保留`source_positions`、`combination_removed_positions`及具体`source_id`，新`source_repetition_no_punishment`状态与active／已解关系分别呈现；实际合去的实体仍存在于命盘及原有根和会合，不删除地支或藏干。工程方法族v12、权重、阈值和四柱历法均保持。

### 合法公开见证与保留的原失败

对下列两个已选日期，另重新下载并实际执行[固定6tail/lunar-python原作者代码](https://github.com/6tail/lunar-python/tree/1645ad3b3653635e5cb31b0c6df22b5e4298f8ce)，未导入FateBridge，34个源文件执行前后身份相同；明确当地Gregorian标签、无太阳钟修正及23时换日口径，两日期的8个四柱字符串均与见证相同。该有限补证不认证全部历法、时区史、交节物理精度、刑冲解释或力量；下载、原代码、协议及完整输出在`calendar-witness-reference/`，不增加修复或盲测样本数。

两组实际可达合成输入均用Asia/Shanghai、06:00、无真太阳时：1976-01-05为乙卯／戊子／丙辰／辛卯，原子卯三实体active改为来源明确的不刑；1915-12-21为乙卯／戊子／丙戌／辛卯，原日时卯戌binding保留，刑的参与位置由年／月／时改为年／月，时柱的合去位置另列。它们由当前真实排柱观测确认可达，不冒称本批独立历法精度验收。

每个日期的`bazi_birth`与对应字面四柱的`bazi_source_compare`，在修改前和修改后各通过实际REST ASGI、新真实stdio MCP、独立CLI，共每阶段十二次；全为200／0／0，四组完整严格投影业务均在三端相同，五个生产源在各自阶段前后散列稳定。按已发布视图选字段并追加所需上下文，原原件、policy、每处业务差异及精确份额变化均另存，不忽略数值字段后声称不变。

无合见证的支持份额由`5100/10849`变为`5520/11717`，是撤销错误刑扣减后的既有算术结果，不是新的来源强弱标签；有合见证仅调整实际参与关系及其引用。六组字面领域控制另留四组正常控制，当前输出模型接受完整结果且不改变实际返回值。普通合同生成实际执行、`docs/contracts`无差异，未运行`--check`。

原17组来源档位差异及三项集合约束逐项保留：GH07仍符合其禁止强约束，SJ05／QQ02仍违反另外两项。原YX01恰属一子二卯，精确份额由`26/83`变为`128/393`，仍弱，仍与原强标签不同；没有把合法关系准入修复冒称解决力量差异。原367记录／321输入、123条未裁定和无来源记录的范围没有缩减，新源规则修复1项、原力量验收解决0项。

五个生产所有者为`punishment_resolution`、`strength`、`branch_candidates`、`output_branch_candidates`、`output_passage_relations`。新增回归只写未运行并加入明确的自包含CI列表；旧测试仅更新一处政策版本断言，不删除节点、原数值或原失败。完整版本、原页及前后结果由本批`bazi`报告维护，完整传统规则、全局旺衰、现实预测与全仓SOTA仍未通过。

### 六爻职责清查与奇门文本见证均不增加修复数

完整读取18个六爻所有者、2947行／65个定义／43项模块绑定及实际加载的15份JSON。运行stages v16与literal v15.0.1、额外《易冒》火顺推、growth各优先profile分别登记；未发现其生产回执版本错误。旧清单“十二长生”改为实际长生／帝旺／墓／绝四位，“贪生忘克等停克”改为实际土巳例外及支持条件；这些是清单纠正，不计算法优化。实际重读的《增删卜易》85、97、98、122、123页与额外《易冒》托管文字，只授予本次所读语境，不将JSON自述当全部原页校勘。

奇门另外完整读取10个小所有者及相关构造／冲突保留定义，共13个定义，8组直接操作数回执保留未决。新实际目读《古今图书集成》艺术典704卷page112，并冻结4份具名托管转录，确认不同书影中乙六／二及丁墓、三诈、人假层次仍有不同说法；不能据另一书的字句改写当前《演义》。原四字段失败和全部九项义务均保留，新增生产修复0、没有新1080表算、完整例盘或预测样本，详见`qimen.md`。

本批最终清单10916职责／2907组／4207个文件符号／649实现文件；7208定义中3911直接具名，3297定义／747文件未具名。455组明确归层（P0 81、P1 143、P2 37、P3 194），2452组仍待语义归层；目录93、共享方法66不变。一次静态导出的`inventory-manifest.json`为6790391字节，SHA256 `bf71a096002f83255918a65c0bef03198033b5e844a02b0ace68d5e63b9a9bf4`，与本批18个冻结生产源身份一致；未执行`check_inventory()`，未把定义、规则资料、公开可达导航或散列相同称为数值／原典／SOTA通过。

第五批古典参考补入精确.gitignore例外后已出现在Git未跟踪清单，原值／散列不变；没有删除历史参考或无关改动。下一批继续剩余六爻所有者、紫微基础及子卯酉月官语境的来源准入；甲酉例的原字／位置疑问先保留，不能把电子转录自动当所选原页。目标仍在进行。

<a id="month-officer-continuation"></a>

## 第七批延续：按清楚原字决议月官之刑

本批新增**一个来源关系准入根因**，累计十五项；刑的阶段分离、新函数、回执、分支数与协议重复不拆成额外修复。原力量验收解决0项，所有旧分母和失败保留。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查。材料在`~/.codex/artifacts/fatebridge-audit-20261117-round7/`。

### 先核原字，再限定可实现的来源分支

所选《秘本子平真诠》PDF25清楚说明：丙生子月、卯刑子，另逢酉时，卯酉冲而不刑月令之官。旧实现只分别识别子卯刑与卯酉冲，两者同时活动，未落实这条关系准入条件。新共享源函数只处理原字清楚的丙子月官条件、唯一子卯酉、真实同次活动的替代卯酉冲；实际会合、重复实体和另一活动冲争用的边界保留原政策，未扩成通用刑冲优先级。

同页甲酉例重新高分辨率读字后为“卯日冲子”，与常见电子改文不同。原Q1观察将年卯／日寅误标为原文明示，现明确更正并保留原19条冻结，不覆盖原图或改用电子“卯来”；甲酉位置含义仍未裁，不编码对称推广。另两条初始“不竞争”控制实际含完整会局，其错误假设和完整结果也保留，不充作生产反例。非邻接六合和半会夺合只形成后续来源义务，本批未全局开放。

### 关系先决议，再应用损益

现有已经决议的六冲、三会、三合、六合和半合保持原样；刑阶段分为形成最终事件和统一应用active刑损益。没有先扣根再修改状态，也未引入全局新关系框架。`zi_month_officer_clash_alternative`与输出验证复用同一源资格，政策明确升级为`completed_combination_zi_mao_month_officer_resolution_v4`；新回执保留丙日角色、受保护月位、替代关系及其实际位置，不声称月官绝对安全、整格成立或有现实预测证明。

30条预先保存的来源／控制观察中，仅P1／P2／P8改变刑准入及其自然预算；P3的替代冲已被实际辰酉合解掉，子卯刑继续活动，其他相冲、重数与全部甲酉／非邻接控制保留。完整30条结果被当前输出模型接受且未丢字段。原20条力量观察的等级、精确份额、结构规则、关系及根账本不变；原17差异仍17，GH07继续符合其否定强约束，SJ05／QQ02仍违反另外两项。P2因自然预算跨原阈值的变化，不被称为原典力量改善。

公开合成见证2035-12-31 18:00 Asia/Shanghai、无太阳时校正、明确分析日期2036-01-01，真实`bazi_birth`返回乙卯／戊子／丙寅／丁酉；1855候选只作内部Calendar可达观察，不冒充公开出生范围。固定6tail原作者代码独立执行同一当地日期，四柱全部相同，34个原文件身份保持，未导入FateBridge；该一项补证不认证完整历法、未来时区史或力量。

上述出生请求和P1／P2／P3字面`bazi_source_compare`，在生产修改前／后各经真实REST ASGI、新真实stdio MCP、独立CLI，共每阶段十二次，均200／0／0，四组完整严格投影业务相同，五生产源在各阶段前后散列稳定。P1／P2实际输出新的已解刑状态，原卯酉冲、倍率及来源保持；P3继续给出冲已解、刑活动。普通合同生成已执行，`docs/contracts`无差异，未运行`--check`。

只扩展既有子卯实体回归，并更新一处政策版本文字；没有新增迭代测试文件、删除旧节点或运行套件。33个本批选定全局生产源已冻结，完整来源与边界见`bazi/report.md`。全仓算法清查、逐项专家接受、物理模型与现实效力目标仍未完成。

### 六爻剩余所有者与紫微基础按真实职责归层

六爻再完整读取22个所有者，5688行／115定义（32个可调用、83个字段类）及10项直接绑定，另读8份实际加载JSON。effects的23条实际all／any公式逐条归P1；同次闭包、真实UTC窗口、传统时序候选和交付分开，不将所有PROFILE或字段类当独立算法。与上批合计，当前40个`liuyao_*`／`output_liuyao_*`文件的180定义均已逐体登记；共享装卦、纳甲、历法、全部规则原页与连续输入仍有各自未完成范围，不称六爻全算法通过。

紫微完整读取15个所有者、3454行、67定义及23项模块绑定，另细分本命31项、运限8项内部职责。22次共享公开ToolSpec执行单元观察覆盖三工具及选定四化／闰月／未知性别分支；它们不是三协议、原13936网格或全分支验收。六张原扫描实际目读，五项原日表疑读／冲突与各流派差异保留，三份零字节PDF不充来源；本lane生产修复0，原有限一致性未升级为SOTA，详见`ziwei.md`。

最终清单11298职责／3184组／4312个不同文件符号；7209定义（5294函数方法、1915类）中3981具名，3228定义／726文件仍未具名。774组明确归层（P0 82、P1 269、P2 83、P3 340），2410组仍待语义归层；目录93和共享方法66不变。本批新增具名70定义含1个新生产helper，其余69是既有位置，不是70个实际优化。

只导出一次最终`inventory-manifest.json`，7143903字节、SHA256 `cd16372c21a609c20c2a7741fae30b43edd6f1c1ab83d86e9b3e7a11619a3e73`，33个冻结源身份相同。静态位置与源码散列不授予算法或原典通过，未运行`check_inventory()`。已解决问题、未裁来源、原失败、真实协议、实际模型与预测仍分列；全仓目标继续进行。


<a id="round8-source-inventory"></a>

## 第八批延续：继续来源裁定与职责清查

本批新增实际根因修复0项，累计十五项。原件位于`~/.codex/artifacts/fatebridge-audit-20261117-round8/`。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或`check_inventory()`；不把职责、定义或协议观察累计为修复。

八字保留26条不同来源观察及原17组档位差异、2项约束违反、3项来源约束。QQ02的缺口是有效接收与根力决议，实际路径节点存在；“有根＋邻接＋未绑定”的泛条件也命中作者区别处理的QQ01／QQ03，因此没有覆盖作者标签或调系数。壬学完整阅读21个所有者、66定义及44项绑定，原64课46同／16异／2项缺日期及其他原始义务不变，本批修复0。完整材料分别见`bazi/report.md`和`ren.md`。

最终清单为11702项职责／3510组／4584个不同文件符号。7209定义中4123直接具名，3086定义／690文件尚未具名；1193组明确优先级（P0 88、P1 375、P2 233、P3 497），2317组仍待归层。2692项绑定中462具名、2230待审；2742条模块语句中2280待审。目录仍93记录、MCP92／REST91／CLI92、13族；66共享方法含63计算及3参考，均不等同独立算法数或验收通过数。

本批只导出一次最终静态`inventory-manifest.json`，7556549字节、SHA256 `3ab64a636a87053bb5897ec9e46e42e61249f5fe8e9cecddb2fd355d15c45268`。全局72个所选源身份无变化；静态清单不授予数值、原典或SOTA通过。

另冻结24个2024太阳节气主点和独立ERFA前向时标比较：合法河洛输入`2024-08-07 00:09:16.454006 UTC`仍在保留立秋主点之前约0.396576微秒，原消费者却依显示微秒判为立秋。相同显示点前后1微秒及减去18个名义UTC日的六输入，经真实REST／新stdio MCP／CLI共18次完整调用，业务三端一致但暴露相同传播缺口。两次观察脚本使用错误的原尝试另存，不计产品失败。独立合同审查未找到“显示微秒替代主点”的已发布政策；修复需同步生产、消费者、binder和输出验证，仍属已有主点传播根因，不另加计数，留到下一批实现。该数值反例不认证物理交节在0.4微秒尺度的准确度。

<a id="retained-civil-point-continuation"></a>

## 第九批延续：共同民用主点、季节判断与完整绑定

本批新增实际根因0项，累计十五项；这是已计主点传播根因的同步补全。21个新增定义节点、字段、消费者和协议调用均不拆成额外优化。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或`check_inventory()`。材料位于`~/.codex/artifacts/fatebridge-audit-20261117-round9/`，原不相关修改、参考、失败和拒绝保留，未提交或发布。

### 时标所有者保留坐标，显示适配不重解时钟

共享`CivilPoint`持有精确名义Gregorian JD分数和原普通区间的排除显示上限；纯日历舍入下移utils，没有反向导入天文模块。`utc_point_from_tt`提取现有现代原子、历史仿射和前UTC求解的未舍入坐标；旧Calendar／datetime接口是同一反解的显示适配。原标量名义别名、显式TT点意图、唯一域与200微秒回代门槛均保留，前UTC没有新增1960夹限，也没有把间隙或删除标签变成可用时刻。

48条预先冻结时钟输入仍37返回／11拒绝，旧标签／错误逐项零变化，14个历史名义标量别名保持。另10条来源／载体输入为8返回／2条原删除标签拒绝，三条原独立历史TT分数精确反解相符；辅助年0／10000、显示cap与JSON大整数字符串分别保留。完整输入、旧结果、来源身份及未满足条件分母见`clock/report.md`，这不是全历史UTC或物理微秒精度通过。

### 所选根的比较、间隔与输出使用同一事实

太阳各实际生产路径及参平两个派生构造器同次保留TT、精确民用点和带区显示。邻接窗口、立春岁首、十二节月、农历节气上下文及起运名义间隔消费保留点；经过日数／秒数先取精确分数差，再在最终量单次转浮点。旧`utc_key`只表示显示格点，原calendar-only夹具保持标签精度，不据TT元数据补造精度。

河洛的当前节气、前一至点、下一四立和六个季节时窗用同一坐标排序、比较；typed context保留实际SolarTerm到唯一caller，JSON只在输出边界产生。土用起点是四立主点减18个名义Gregorian日；显示起点仍独立保持终点显示标签减18日，没有换成18个TT日。公开分子／分母为十进制字符串，完整cap显式null／object，partial缺cap保持未知；输出比较已知坐标，只有已知完整cap才核对格式，不查当前clock。

原24个2024主点及旧公开记录全部保持。独立冻结偏移方程与[ERFA前向时标链](https://github.com/liberfa/erfa/blob/v2.0.1/src/utctai.c)对照中，24个精确民用点全部相符；72个显示标签左右微秒输入的排序、节气／节月半开区间和立春年界均相符。24个根及其显示标签比较在第八批保留，72邻点参考与观察在本批冻结；它们不相加成独立物理太阳样本，原太阳模型失败不改判。新便携资料为[保留民用点](../tests/data/retained_civil_points_v1.json)。

原六个河洛输入重新通过真实REST ASGI／新stdio MCP／独立CLI，共18次200／非error／0，完整严格业务相同，仅排除顶层run_metadata，无result_delivery截断。`2024-08-07 00:09:16.454006 UTC`在原立秋根前约0.396576微秒，现在为大暑／土用真；减18名义日的`2024-07-20`同钟面在土用起点前约0.396576微秒，现在土用假。四个邻点维持原分类，全部根及原before结果不动；15个相关生产源观察期身份稳定。详见`heluo/report.md`及完整body。

独立静态复核另发现梅花完整绑定器还按显示标签重算间隔，要求精确float相等，使本批中间版本的合法整秒`2024-08-07 00:09:16 UTC`公开请求在REST返回500，具体为`month.elapsed_since`。原拒绝与堆栈保留；修复使绑定器读取同一完整point及分数间隔，缺cap不补全。相同请求随后真实三端200／非error／0，完整严格投影相同、五源稳定；这是同步改造中发现并消除的中间回归，不算另一个原项目根因。原时钟、种子与传统取数均不改写。

新增回归写入既有历法年界、河洛上下文和梅花钟时文件，复用同一独立便携资料，均未执行。两个旧故障注入文件只改为当前point入口，原节点、错误断言和门槛保留；聚焦节点已加入显式CI列表，CI未运行。普通合同生成执行一次，`docs/contracts`无差异。全部临时观察、源码前像和日志放在仓库外。

### 宿曜职责及最终静态快照

本批完整逐体阅读22个宿曜相连所有者，共6087行、107定义、49项顶层绑定；三种实际历法、望宿配宿、未知时刻日期原像、联合候选和日／事项证据分别具名。18份JSON共2617248字节，14小档逐值读，4大档明确局部读取；没有把23155历史月首或1966现代日本月表的结构／选段阅读当成逐记录原典校勘。CBETA所选T1299原XML重新取得且SHA与运行来源一致，NAOJ官方朔日表另保留；HuTime未刷新，旧资料元数据不授予当前全域独立验收。本lane无新增执行或修复，也不宣布宿曜全范围通过。

最终为3768组／12084项职责／4759个不同文件符号；1466组明确优先级，P0 131／P1 403／P2 319／P3 613，2302组仍未归层。1155个生产Python文件含7229定义（5307函数方法、1922类），4248具名，2981定义／667文件仍未具名；2693绑定位置中512具名、2181待审，2743条模块语句中2231待审。新增具名126定义含105既有位置和21新节点；仅退休旧日历舍入helper一个映射，实际数学已迁至共同carrier，不据节点数提高优化计数。

本批只导出一次静态`inventory-manifest.json`，7918874字节、SHA256 `976b4ff8d521f8fd9302accae554279145d122d05264ea0304bda0f95ce87d49`；83个所选生产源与冻结身份无差异。目录仍93、共享方法66（63计算／3参考），这些都不是最终细算法数或已通过数。

参平分段／查询、出生范围节令探针及起运进位逆像仍有显示坐标消费，已转入下一批按完整契约和合法请求继续核对，不能宣布全部下游接受。原八字17组差异／两项约束违反、太阳模型、天文框架、人类图、太乙、奇门和壬学失败继续保留；剩余清单、全部参数与源分支、独立专家、真实模型、安装／部署和现实预测仍未完成。目标继续进行。

<a id="canping-retained-intervals-continuation"></a>

## 第十批延续：参平年序保留数值区间

本批新增根因0，累计十五；未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查。源码和专业依据的完整材料位于`~/.codex/artifacts/fatebridge-audit-20261117-round10/`。所有原失败、参考及不相关修改保留，没有提交或发布。

### 同一立春根与查询，不再从显示标签重建区间

修改前预声明2001—2021各立春21候选并保留全部结果，原精确偏移与ERFA判断相符。首个2001立春显示值`2001-02-03 18:28:49.643537 UTC`仍在保留数值主点前约0.169914876微秒；固定出生2000-05-15 09:00 UTC、男、无太阳钟和默认120年范围的公开查询，原三端均提前返回2001年序。没有换根、输入或阈值来改变方向。

同次源、分段与查询现在使用`ResolvedProjectionBoundary`、`ResolvedCanpingInterval`和`ResolvedAnnualSeries`，实际年界保留typed SolarTerm，查询保留typed interval，不从公开JSON回读已知主点。原SDK入口仅作同一计算的JSON适配。生日加法、起运方法、模型许可及原120年范围不变。不同精确端点可显示为同一微秒，正长度区间不能被显示舍入删除；cap只描述源时钟的显示上限，不是年序排他end。

输出与完整绑定同步核对数值半开区间、连续分段、出生裁剪、年度来源、实际大运和query所属年／段；partial缺点或cap保持未知，无日期legacy行不补时间。共同`CivilPointLabelEvidence`供中文、河洛和参平来源记录复用，移去重复显示验证，没有另造时钟或反向导入。

修改后原21个TT根、精确民用点和完整source receipt全部保持；原同一请求重新经真实REST／新stdio MCP／独立CLI，均200／非error／0，selected.year均为2000，完整严格业务相同，仅排除顶层run_metadata，无截断。原121个全年来源回执、12段大运旧日期／年龄／取数／取文原样保留；只增加point／policy，19个源码与合同路径在观察期身份稳定。详见`canping/report.md`及完整body，不能将数值传播符合当成独立物理太阳或现实预测SOTA。

共享显示验证迁移后，原河洛边界和原梅花整秒输入又各经一次真实REST，均200且完整所选业务等同第九轮。四个新参平回归和一个旧显示端点假设修正置于既有文件，加入明确CI列表但未执行；原范围拒绝、输入、参考和门槛不删除。普通合同生成实际执行一次，`docs/contracts`无差异。

### 事件零宽点与实际wall阈仍分开保留

出生范围及起运事件五个所有者另作独立只读审查。固定原2024立秋根，两组合法整秒±1分钟范围输入实际REST200；公开立秋与名义月进位事件均把早于保留坐标0.396576429微秒的显示值列为零宽点。direct相同，26个所选文件身份稳定；内部floor零宽范围还错误纳入了范围外立秋，明确只是内部微秒SDK控制。未证明候选状态遗漏，原guard与连续完备性限制保留；另三事件所有者消费显示值作metadata或reference身份，实际求解走既有wall上下文，不能一刀切算成三个新算术错误。

两路独立理论裁定发现：round-to-even日历月进位的理想阈并非名义根±六小时本身，方向产生±1/240微秒偏移，tie改变首个受影响微秒格点；24项预声明纯政策控制中8项不被名义floor／ceil外包。它们不是新太阳根／产品失败，当前float链仍有未冻结误差。只修名义回执不能借此授予实际wall阈定位或连续候选完整性。旧observer导入名与naive时区错误另存并更正，不计产品反例。下一批先传播typed来源与明确名义坐标，原actual-wall及连续接受继续未完成，不通过改定义求过线。

### 本批静态快照与未完成范围

唯一静态manifest为7970301字节、SHA256 `5f4bcf55c28f4df1c7a75c06c155085b4a6c4e480c4d61312f762f1589f39953`，86个冻结源身份无差异。当前3803组／12102职责／4781映射；P0 135、P1 404、P2 329、P3 640共1508组明确归层，2295待归层。7244定义（5316函数方法／1928类）中4269具名，2975定义／665文件待具名；2694绑定位置中513具名、2181待审，2744模块语句中2231待审。新具名22定义含16新节点和6旧位置，移去一个重复河洛validator，均不计新算法通过或优化。

目录仍93、共享方法66。完整清单、剩余来源／参数／分支及专家接受、真实模型、安装／部署与现实效度继续未完成；旧天文模型、八字17组差异及两项约束、太乙／奇门／壬学原失败未借本批改判。目标继续进行。

<a id="nominal-event-enclosure-continuation"></a>

## 第十一批延续：事件保留来源与名义包络

新增独立根因0、累计十五。完整报告在`~/.codex/artifacts/fatebridge-audit-20261117-round11/report.md`。本批是原保留点传播的下游补全，不以函数、字段、guard或协议重复累计修复；未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查。

`DayunStartResolution`保存actual SolarTerm、localized birth、方向／年干及精确名义日差，旧十一字段details仅作JSON适配。原float(days)再除3、乘86400及wall乘120／1e6／round／divmod／relativedelta操作次序保持；不是实际wall量化修复。纯`nominal_calendar_bracket(day)`供CivilPoint和输出验证复用，不消费cap；partial缺cap不临时构造uncapped point。最后纯抽取另存stage，七输入21操作的严格JSON／float.hex／wall／拒绝兼容观察属于抽取前，不冒称同一最终身份。

Jie范围成员及游标使用保留point，名义carry取实际root±index/4日并另带reference_point；事件明确为`nominal_gregorian_microsecond_enclosure_v1`，at_utc是上端格点。原guard保留，合法natal Jie两端维持原零carry旁guard；其他三实际wall逆像所有者数学未重写。

原两合法整秒±一分钟请求各经真实REST ASGI／新stdio MCP／独立CLI，共六次200／非error／0，仅排顶层run_metadata后的完整业务严格相同，无result_delivery。五生产源及26所选观察路径稳定。原LiQiu根不变，Jie及首个名义carry原`.454006`零宽显示现为`.454006`至`.454007`的1微秒外包，精确坐标符合原冻结参考；内部floor零范围误纳Jie由1变0，仍1 probe。六旧context的details／wall／offset不变，全部旧natal及dayun probe事实保留；两请求natal为9→10／5→5，dayun均5→8，current-dayun候选不变。新增guard不算独立物理样本或连续证明。

实际wall义务继续未过：理想半偶舍入相对名义点有方向相关±1/240输入微秒偏移，24理论控制中8项不被名义包络包含，既有binary64链另有未量化误差。它们不是24个新产品失败；显式nominal basis不能改写实际wall验收目标。原`continuous_completeness_certified=False`及未决layer保持，普通clock资格、物理亚微秒精度和预测均未认证。

八字另目读21原页、审读34定义，固定29初始及4补读身份。QQ02甲→丙→己→辛可见路径已存在，末辛无金藏根仍有原文受生，因此“全链有根”会排除目标；原367记录／321输入的预声明静态查询所得9四干顺生输入都是旧样本。没有来源可执行的安全承接规则，生产修复0，未调阈值／权重或按case特判；原17差异／两约束违反／123未裁保留。

回归只写未运行；三旧synthetic wall mock迁到typed fixture，原111 IANA分母和expected保持。普通合同生成一次，docs/contracts无差异。清单唯一manifest为8002149字节、SHA256 `b12a8eda6fe64c63646f6ebd4d4e1f1ff8f325ee71dce86cafccaffa8f6f4286`，89冻结源相符。当前3825组／12137职责／4796映射；7251定义中4284具名、2967未具名（663文件），P0 142／P1 404／P2 332／P3 654、2293组未归层。绑定2181和模块语句2231待审队列重叠，不相加为算法。

目录仍93、共享方法66；新具名15＝7实际新节点＋8旧service定义，不是15优化。全仓细算法、逐项来源／参数／分支、外部专家接受与SOTA未完成；旧失败和所有无关改动保留。下一批继续实际wall量化／逆像根因及高优先级职责清查，目标继续进行。

<a id="round12-rounding-invariants"></a>

## 第十二批延续：起运与地磁换算的精确中间量

本批新增两个独立实际根因，累计十七。完整报告在`~/.codex/artifacts/fatebridge-audit-20261117-round12/report.md`。三生产所有者改变、新生产定义0；审读超过十个定义不冒称十个独立修复，样本、字段与协议不拆成优化数。未超过50，没有运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查；普通合同生成一次，docs/contracts无差异。

起运原float跨度／连乘制造半微秒tie。首固定小暑源见证为男UTC`2024-06-06T14:20:03.398557Z`，精确放大偏移应311040000000093微秒，旧链变成末尾92.5再取偶为92，使实际wall早1微秒。现仅由typed Fraction跨度直接乘整系数、单次half-even，再用原360／30分解、Gregorian及DST政策；旧十一字段details／float.hex、实际source及方向保持。原198预声明候选的174来源匹配中，四个Q／wall差异变0；24跨到另一Jie的前提不匹配全保留，直接整秒输入原0差异仍0。七旧输入21操作兼容保持，synthetic helper只读138种整秒offset保持原目标，不冒称重跑IANA队列。

同一source／方向、民用日期／偏移及整年／月cell中，输入微秒对应精确放大值的偶整数120平移，因此半偶舍入后的wall有−119／121整数斜率。原54固定cell／固定target的两条假零宽内括区间随此根因消除，36返回括区间都夹原target，18跨carry未决保留；未改三actual-wall逆像所有者，也不由外guard或continuous=false赦免原假括区间。两合法整秒±分钟范围before准确为两REST；after六次真实REST／新stdio MCP／独立CLI全部200／非error／0，同版本完整业务仅排run_metadata后三端相同、无截断。全部旧probe事实与before／active候选保留，forward8→16、reverse8→8，原非affine未决消除，其他layer与continuous=false保持。

地磁另预声明原独立Rodrigues十二输入的1728构造边界，D物化值均相符但320条角区／显示因中间舍入有差。首磁北21.218517883865147°与已交付D精确和为22.5−2^-50，原提前归NE／艮／丑，应N／坎／癸。现只让geomagnetic_reference及bearing_context保留Fraction加减／正模及半整数比较到分区后，公开精确角度回执并最终显示；原1728差异0、完整主场field变化0。第一stage后预声明的72环绕控制15→0，stage全存，属于同一修复。两合法合成请求before／初after／final各六次真实三端、共18次全成功且同stage完整业务相同；原before与final只变conversion角区及新增算术回执。该已交付binary64值的半开分类有独立代数证明，不恢复未舍入D、提高WMM物理或现场精度。

并行全文审读八个星历／光学／帧所有者64定义、24直接绑定及四实际JSON，36旧未具名定义完成登记；原十五粗组及其验收全文外置保留。源数学、TDB钟时、有限光锥、透明太阳和物理框架的限制继续分列，本lane新修复／新计算为0。原权威资料访问失败、旧Saturn／光学／Lahiri等分母和未通过结论不据职责拆分改写。

最终3932组／12257职责／4853映射；7251定义中4320具名、2931未具名（656文件）。P0 222／P1 405／P2 332／P3 696，共1655组明确归层，2277组仍待归层；2160绑定及2210模块语句待审，队列重叠不能相加。唯一manifest为8187009字节、SHA256 `9bdfade1a606a1367810eb27507730cbd8d3372829d8e40ed07daad14712511b`，99冻结生产源相符。目录仍93、共享方法66（63计算／3参考），都不是最终细算法总数或通过数。

新回归只写未运行，旧测试／来源／门槛及无关改动保留，无提交或部署。原太阳／框架、人类图、八字17差异及两约束、太乙／奇门／壬学等失败仍在；全仓细算法、逐项权威接受、真实模型、安装／部署与现实预测证据继续未完成，目标保持进行中。

<a id="retained-primary-tt-continuation"></a>

## 第十三批延续：TT主点贯通实际星历、框架与几何

本批新增独立根因0、累计十七，是既有大JD过早舍入问题的传播补全；字段、定义、接口和修正中间实现不拆分计数。完整材料在`~/.codex/artifacts/fatebridge-audit-20261117-round13/`。未超过50，没有运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查；原参考、门槛、失败及无关修改保留。

### 保留点是唯一真值，原生标量只在实际边界适配

`UTCClock`及`EphemerisTime`只保存可空`TTInstant`，原`jd_tt`由主点导出，不同时保存两个可冲突日期。精确原子UTC入口保留日分数及公布偏移；显式float入口只保留其IEEE点，不猜回原民用微秒。旧第三位置float构造及dataclass replacement沿同一个`tt`字段处理，没有增加双关键字别名。原子UTC前未知／模型、历史调整有效域、ordinary cap及默认／C04的原有资格限制保持。

十二个核心源、九个实际消费者及六个几何源改变；另一个纯角度宫位所有者完整复核后未改。离线DE441及相对时钟、岁差章动、交角、目标赤道、宫位与高度使用保留点，局部offset先在主点累加。native `calc`、Lahiri及恒星调用明确转float；原生射线源框架仍匹配SDK实际scalar历元，不给scalar源附上不同精确点的源基底。产前朔望保留出生点作严格顺序比较，求根本身仍是原标量算法，未据接线宣布亚标量事件精度。

原私有worker信封新增`tt_instant`整数分子／正分母分支，未知输入只在协议边界校验一次。实际JSON与两次注册新进程`jyotish.positions`操作保留精确民用点和原IEEE点的区别；两者虽同`jd_tt`，UTC点语义显示分别为`.465208`和`.465215`。这是stage1的载体／worker观察，非最终stage2数值验收；codec所属源最终未变。observer最初误读不存在的`julian_day_ut1`，现从原body的`julian_day_ut`另作投影订正，原null／脚本保留、未因此重算。

### 原65536强标准没有被新字段或新门槛替换

修改前原32时刻的标量均劣于官方SOFA两部；原16现代时刻±1／0微秒的48次实际离线Sun调用均丢失原TT尾数，15组三点全同。原局部offset在大JD相加也合并了NorthNode三点；相同IEEE系数的独立有理模型能区分16组三点，不把同源算术控制当物理轨道参考。

共同stage1冻结后，原65536时刻的完整clock队列只重新执行一次：canonical主点65536项与原精确源相同，0拒绝、0项劣于原SOFA两部；旧`jd_tt`仍65536项劣于原SOFA两部，原18277警告不变。实际48次离线Sun参数尾数损失变0，局部NorthNode48次与直接同点模型一致，16组Sun及16组node三点最终均可区分。原32框架与从同一精确源独立构造的integer-head ERFA桥接输出相符；最终high／low分部不是原桥接的逐值相同入参，只裁定有限源／框架桥接，非独立物理精度。

随后从已保存65536主点单独测实际`as_parts`，初版integer-head分部为33772更好／15574相同／16190较差，不能用canonical零误差掩盖。按[ERFA两部日期合同](https://github.com/liberfa/erfa/blob/v2.0.1/src/pnm06a.c)，最终改为`high=float(days)`、`low=float(days-Fraction(high))`，不提前重加；原float自然为`(原值,0)`。相同已存分母逐行重放后65536项表示误差均小于原SOFA两部，0相同／较差；没有重调65536时钟或轨道。stage1失败逐行保留。两个double不声称可无损表示任意有理数，数值表示改善不等于真实钟时、轨道或下游C运算完全精确。

### 合法公开输入、传统来源与未运行回归

原计划中的默认chart非零秒请求不被现有Schema允许，已在实际调用前改为同一合法分钟起点；微秒控制没有混进公开分母或扩Schema。原生／受控缺库两模式、热带／Lahiri两选择共四输入，每stage真实REST／新stdio MCP／独立CLI十二次均成功；各stage仅排顶层run_metadata后的完整业务一致，保留帧与全部数值逐叶比较后四输入跨stage也无业务变化。最终stage2与stage1各十二次分开记录，不叠成独立样本。缺库由原bootstrap控制，不是卸载、真实模型或部署验收。117个生产源在各观察窗口均无漂移。

并行太乙20定义只读复核没有安全新规则：原288比较277相同／11差异、原576位置573相同／3差异及全部源内矛盾保留。Rust的5→None与现有5／中不是足以统一改数的证据，金镜原页115明确出现主算／主大将／主参将5；中宫出位、计数及不同原文层分别裁定。原233578条第三方比较为233154相同／424不同，旧摘要误写required分母233154也原样保留并明确说明。

壬学本批没有新引擎调用或修复；原64格54相同／4不符／6未决，重建46相同／16不同／2缺日及strength11/12继续保留。现有P52／53与P56—59见证不足以独立裁定新关系规则。新增《六壬神課》扫描只找到元数据；读取超大小、两次HTTP429未取得PDF，不宣称新书影校勘。随后用系统bsdtar只读索引本地综合rar的全部266条目录，19词面命中保留17大六壬／金口候选及另两项；仅取出两份DOC共737792字节，通用编辑账号和相冲突的文件日期不足以认证书作者／版本，正文与争议条款尚未校勘，不运行EXE或整包提取。替代转录12/12不能覆盖原扫描11/12。

六个新回归函数只写未运行，旧Lahiri类型期待及polar上下文按实际point边界迁移，原独立目标和有效范围未删除；已有CI选择整个所属文件，无需重复聚焦登记。所有临时脚本、下载错误、前像、阶段结果与完整日志均在仓库外。完整源码清查与最终manifest另列本批收尾，数值、来源规则、协议、部署与现实预测继续分开验收。

后续只读调用链发现`jyotish.positions`与`predictive.build_native_subject`仍将派生`jd_tt`传给已支持point的目标姿态／宫位／高度，优先列P0继续；其native `calc`、ayanamsha及motion-source的scalar边界则有实际SDK依据，不能整体替换。returns的scalar相等／先后尚须冻结实际输入及反例，不因看到比较就计成已证根因。本轮没有把剩余调用者标为已贯通或独立通过。全src构造／隐式序列化静查未见旧`jd_tt`关键字构造或遗漏的dataclass字段依赖，这只是已读路径负发现，不是全部运行分支验收。

### 本批最终静态清单

五个钟时所有者最终完整登记52定义、73组151职责；其余24个相关所有者按实际变化职责补36组67项TT传播映射，不把diff阅读说成这些模块全文复核。全27个变化源新增生产定义9、退役0，清单新增具名23＝既有14＋新节点9，支持定义不计新算法或根因。

最终4013组／12376职责／4876文件符号映射，分布687实现文件；7260生产定义＝5330函数方法＋1930类，4343具名、2917定义／652文件仍待具名。P0 288／P1 405／P2 332／P3 734，共1759组明确归层，2254组未归层；2160绑定与2210模块语句待审，队列互相重叠。目录93／共享方法66（63计算、3参考）、MCP92／REST91／CLI92不变，不充作细算法总数或通过数。

普通合同生成一次exit0、stderr空、docs/contracts无差异；唯一manifest为8375316字节、SHA256 `2a2ec7bae6bf1f8d0e2ad0b57888e516e9268363c90ea1429070847563bf8fb1`，与117所选生产源身份一致。导出时静态普查两种AST身份无差、无失效映射或未解析行，没有运行`check_inventory()`。完整算法总数、逐定义权威来源及全参数／分支、专家独立接受、真实模型、安装／部署与现实预测仍未完成，原失败和无关改动继续保留，目标保持进行中。

<a id="retained-target-tt-continuation"></a>

## 第十四批延续：印占、推运与主限实际目标TT

上一轮改变源码与实际比较证据，属于实际进展；本轮按已定位P0路径继续，没有缩小全仓目标。新增独立根因0、累计十七；同一大JD舍入根因的下游传播、类型、字段和协议不另计数。完整证据在`~/.codex/artifacts/fatebridge-audit-20261117-round14/`。未超过50，没有运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查；原数据、门槛、失败及无关修改保留。

### 单一领域TT取代提前投影，SDK源历元保持

`NativeSubject`只保存`tt: TTInstant`，派生`julian_day_tt`；构建者用保留点处理目标宫位、宫轴、地平高度及旋转政策。实际native行星、ayanamsha及其原有限差分、来源政策和公开JD共用局部`native_tt=tt.as_float()`，没有两个stored真值或新的并行kwargs。主限新增五实际字段的`PrimaryDirectionEquatorialContext`，替代float字典及一组重复几何参数；同一个context供六处调用／三个消费者族使用，不放回公开JSON。没有保留无生产消费者的预留属性。

印占`positions`只将既有canonical guard及四个point-aware目标调用同步；native行星、ayanamsha、motion、mean／kala及scalar receipt不改公式或历元。所有native射线的源框架仍按SDK实际scalar解码，目标点与源历元分别说明。三个人工NativeSubject fixture和一个48记录JSON读取边界按原IEEE操作数适配，原gzip／hash、fsum输入语义和全部期望／gates不变，不在生产添加旧关键字alias或推测性worker信封。

### 原输入、实际目标与完整SDK转录分别比较

原1979微秒三点与同日合法分钟控制、热带／Lahiri两选择构成八次实际推运盘构建，另十六次实际原生natal目标日／月返照。原72个target TT均丢尾数、矩阵与精确源时刻直接ERFA不同；修改后72个均保点且矩阵差异0。72个native源框架输入仍匹配实际SDKscalar，35840条完整SDK调用的参数、结果及次序前后严格相同，标准JSON身份为`dc0b5a77a554be863cde67c96fa77ca9530210b5fc5ab954e8e90c6741110b0e`。八个subject的canonical值与原冻结点逐项相同，不只靠新字段判过。该参照裁定实际IAU框架桥接，不认证观测EOP、原子钟或天体物理精度。

印占同四个原点各经真实注册worker和独立新进程逐次转发观察，两个模式在before／after分别保留。12个真实目标由全部丢点／矩阵不同变为全部保点／精确源ERFA相同；每点2308／2308／2308／1376条native完整转录、源基底、模型与文件回执逐值保持。worker与观察进程完整业务仅五处执行环境metadata不同，未假称父进程spy进入了fresh worker。少量RA／赤纬及midheaven末位变化完整记录，原SDK邻微秒坐标相同不当作失败。

两个原合法分钟pdchart请求分别用equatorial／mundane-semiarc，各实际REST观察两个context、16个physical target及14条native调用。context／target原提前`1388625/131072`微秒的点差全部变0，SDK始终scalar且完整转录相同。公开完整业务变化分别58／72处，包含56／70个数值末位及各两处导出文字；全值变化保留，最大绝对数值差分别约`5.684e-14`／`1.421e-13`，不以容差删去差异或称全结果不变。

最终主限两case及印占原`17:17:13.465208Z`／`17:17:00Z`两case，共四case×REST／新stdio MCP／独立CLI十二次，均200／非error／0；完整业务仅排顶层run_metadata后三端相同。PD after追踪REST直接作协议基线，没有重复REST增加分母。印占实际Schema支持的秒／微秒没有外推为Western公开支持；原±1微秒邻点仍只在内部队列。原两REST before不冒称十二次before协议。

### 返照端点别名不借目标矩阵改善改判

十六个实际返照都选中analysis scalar端点，十六个scalar点均不等于精确analysis点；十二个内部微秒控制的scalar点晚约6—8微秒，四个分钟控制早约10.59微秒。旧solver／not-after报告及原点差同时保留，before／after十六条别名行逐值不变。这是数值点身份差异，不足以推断连续真实交点在未来。

本轮returns只订正“已知民用标签就是同一个精确TT点”的三行注释：它只能见证相同SDK查询。原搜索、括区间、阈值、输出和gate保持；向下挪查询格点可能跳到前周期，不以此换取通过。连续交点、原子点身份与严格physical not-after的强目标继续未决，不靠改basis、换参考或添加receipt求过。

三项新回归函数只写未运行，分别观察实际推运目标／native源、主限context／SDK边界和四输入印占target／源框架。原测试只迁实际类型读取边界，未删除有效门槛。root observer初次目录与前像目录同名在导入前失败，另设输出目录后执行，原脚本／错误保留；衍生摘要一个自比较标志从原冻结点map重投影订正，0引擎重跑，原错误摘要也保存。这些工具错误不充作产品问题或修复。

初始共同135源before保留；印占before按其15项真实源码／合同／测试依赖冻结，未假称同时135／139全局不变。最终将其中四个已预冻runtime依赖合为139生产源，SHA256 `91dae7c2a0371cf9f26ea9293dec2617b3fab46390081685af180fee0d88de96`，各after观察前后稳定。三个计算owner与returns仅注释改变，生产新定义仅NativeSubject标量属性和主限context类两项，不作两root。普通合同生成一次exit0、stderr空、docs/contracts无差异；最终清单另列收尾。

### 本批最终清单与剩余范围

三个predictive完整所有者及印占明确范围共46定义节点（43函数／3类）、14个直接绑定；47旧源码位置组按实际职责展开成82组191项。新增具名3＝原validate_clock＋两实际新生产定义，另14个原绑定首次具名，无退休。类型、输入边界、原生源、物理target、投影和输出分别归层，不把46节点当46算法或独立修复。

最终4048组／12422职责／4893文件符号映射，分布687实现文件；7262定义＝5331函数方法＋1931类，4346具名、2916定义／652文件仍未具名。P0 304／P1 416／P2 357／P3 764，共1841组明确归层，2207组未归层；2146绑定及2196模块语句待审，队列重叠不相加作算法。目录93／共享方法66（63计算、3参考）、MCP92／REST91／CLI92不变。

唯一静态manifest为8418539字节，SHA256 `9397698ba1554087411be7cf268f11f062b88333a661639975c4eeefef1307ef`；中央清单SHA256 `570fabeced1433be4861cb3dc324426a808bbd6697225c3dee6b040460da6467`。139冻结源与manifest／live一致，两种AST普查身份无差、无未解析行或失效映射；这是一次静态导出而非`check_inventory()`。完整细算法及来源／参数／分支、传统异文与旧天文失败、返照连续根、专家独立接受、真实模型／安装／部署及现实预测仍未完成，目标保持进行中。

并行壬学只读补证转换了上一轮精准提取的两份DOC，并重看原冻结京本PDF118—121四页；没有新引擎调用或修改规则。《括囊赋》略疏文本自署刘英忠，却属于大六壬四课三传；不能把相邻体系的内外／贵人前后直接套进金口诀四位。大DOC现代编辑者与版次未认证，黄陶中只是其所引底本编者，且正文自承对疑似起错课式“将错就错”。P52的甲申与京本戊申、P53的“相丑”差异原样保留，不猜字或选能合算者；文本转换未恢复的课图也不从引擎补造。

六疑文逐条仍不能分离所选配对／昼夜归属／前后盘层／丁干起点。P52木／水／木／水和P53土／金／土／金的原正例同时满足两种候选隔生配对，重复原例不能唯一裁定。P56仍缺实际观星条件，P57／58／59的身份、距离、带神或鬼对象未补齐。原64课54／4／6、日时重建46／16／2及扫描strength11/12保持，另转录12/12不替换；新增安全patch与root均0。所有局部文字、日字、图像与来源资格在本批`ren-source-notes/report.md`，不据此授予现代DOC原典独立性或预测效度。

<a id="solar-guolao-and-return-resolution-continuation"></a>

## 第十五批延续：太阳钟、果老主点与返照早停

本批新增一个独立数值求根根因，累计十八；共享太阳钟／果老仍属既有保留TT根因的传播补全，不按字段、函数、输入或协议累计。上一轮源码与实际对照完成为真实进展，本轮继续原全仓目标。完整材料在`~/.codex/artifacts/fatebridge-audit-20261117-round15/`。未超过50，没有运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单检查。

### 原作者C对照定位可表示TT尚未求尽的终止缺口

固定原四个1979热带natal目标，各analysis−1／0／+1秒，Sun／Moon共24对，与实际Swiss2.10.03 `solcross`／`mooncross`比较。直接SDK坐标函数、SWIEPH|SPEED旗标、原数据文件及所有target逐值相同；按同370／32日窗口枚举作者前向crossings后取不晚于同一scalar analysis的最近项，所有越界candidate也保存，没有加endpoint epsilon。原作者1mas线双方原本24/24均过，但逐点精确残差原7项Fate较差，都是Moon差一个现代TT格点约40.233微秒。

七行实际对应三个独特输入，未缩原24分母。对原函数`sys.settrace`取得三个实际终帧：括区宽`9.313225746154785e-10day`＝两ulp，尚有内部SDK点，且它恰为原作者root、残差更好，其中两点为零。旧`high-low<=1e-9`在评价中点前退出。现只删这个提前停止项，以中点不能再表示于端点之间作为终止；64cap、原扫描、穿越方向／不连续检查、最小残差端点政策及scalar not-after界均保留，没有拟合新常数或放宽验收门槛。

同原24对重放后，24个TT值及精确有理残差均与作者C逐项相同，原17相同／7较差变24相同／0较差；全部author candidate、flags、target和参考函数值原样，source／库及两个se1身份不变。只给这个数值终止问题新增1 root。原16端点别名、连续物理交点／严格physical not-after和其他epoch／flags继续未验，不借本批结果改判。

便携JSON仅从修改前author记录提取三个独特反例和一个不变Sun控制，完整24记录及所有原失败另存；新意义回归只写未运行，期望不是候选solver生成。初始root准备曾猜错不存在的HD文件名，实际`rg --files`及import拥有者核对后在任何引擎调用前订正，错误单列，不算产品根因。

### 单一太阳钟上下文与果老实际消费边界

`SolarClockContext`仅携带UT1和主TT，替代私有`_sun_clock`的平行参数；forward使用已知TT，UT1逆解只保原模型IEEE点，旧dict／回执SDK字段仍float。初版对不需要Sun的LMT分支增加了无关TT assert，静态peer发现后仅将它移回LAT分支；初版源像保留，未发生runtime失败或计新root。原1979零微秒偏移与分钟点各components／rebase的四次新进程观察，八target原均丢点／矩阵不同，现八次精确保点／同ERFA；40底层SDK转录、四份结果字典、源框架及原两REST业务完全保持。原RA1e-10度／EOT及GAST200微秒线前后本来都过，不能以它们掩盖旧point失败，也不捏造可见钟时改善。旧112／96／96队列仍未重跑。

果老四所有者将目标高度／赤道／sidtime／宫位、原生年／节月成员、候选年hint、历史UTC8解析及时间差改为读取canonical point；真实SDK行星／星／交角／ayanamsha和公开JD保持scalar。原六case各真实service worker与独立positions转发观察，26个actual target的point／ERFA相符由2/26变26/26；LMT逆解本来只有IEEE点的2/2负控始终正确。每phase11463条SDK转录、源框架／矩阵、states／extras与28宿界逐值相同。

固定原Round8的2024立春root不变，六限定原生点／有效标签控制的年和节月成员各2/6→6/6；它们不是ordinary public solar calendar全域可达证明。原nativeLMT至固定1978-01-01T00:00:01Z的span从1.648150384426117秒变为原保留点参考1.6481538262367248秒，约−3.44181微秒差变0，200微秒guard未变。缺label hint／历史UTC8分支只静态传播，普通solar calendar资格继续未验。两个observer的privatebytes strictJSON及service参数类型准备错误保留，仅重取失败capture／固定span，不当作引擎错误。

### 完整三端、原生载体与最终静态清单

最终五个合法case×真实REST／新stdio MCP／独立CLI共15次全部成功，各case完整业务只排顶层run_metadata后三端相同。两太阳钟after REST直接复用，所以finalobserver仅新增13次协议调用；原before只两REST，不假称15before。Guolao原LMT回执保留convertedUTC `1977-12-31T23:59:60.351846`、不可datetime表示及子时，没有偷移午夜；second60是resolved carrier而非非法输入。公开lunarreturn只用原1979分钟birth和17:18analysis，原生TT2444199.220719722及残差0，UTC显示17:16:59.999989早约11微秒的事实保留，不能当原16alias已通过。

Human Design本轮实际所读natal／Design链全调用native float `calc`，没有把标量传入已支持point的离线轨道／目标姿态函数；其88度求根已细分到相邻TT并另述数值contact。没有因看到`.jd_tt`就全局换类型或回填precision receipt。此为限定只读负发现，原Uranus／Moshier、出版方口径、cycles／interval与全体原典／物理效度仍未验。

六所有者完整审读最终37节点（含新增SolarClockContext类）和16直接绑定，原33组209职责按实际跨层角色展开为97组246项；root另仅同步已读returns停止职责。新增具名2＝原nested calculate＋新类，16原绑定首次具名，零退休；这些不是算法通过或独立root数。最终4112组／12459职责／4911不同文件符号，687实现文件；7263定义＝5331函数方法＋1932类，4348具名，2915定义／651文件仍未具名。P0 334／P1 433／P2 365／P3 806，共1938组明确归层，2174待归层；2130绑定与2180模块语句队列重叠，不相加成算法。

七个预期计算owner前后身份明确，全部152所选生产源最终SHA256 `2eaf6bd8dbd86ac673081e5804ad53935799da62c707adb80201d979ec7c6b6f`，每after窗口稳定。普通合同生成恰一次exit0、stderr空、docs/contracts无差异；唯一manifest8509321字节，SHA256 `3aed80f740f4064c810d6f51537f32a03fa44f5c789c2a2a6bbd5e31fa402980`，中央清单SHA `f59f1d7ac870b0c60eea8086461f921663b25d29c72a701ca5b2f6490c17b811`。两种AST普查无差、无stale／未解析行，不是清单check或项目测试。

旧物理模型、八字17差异及两约束、太乙／奇门／壬学异文与失败、完整细算法数及全定义来源／分支、专家独立接受、真实模型／安装／部署和现实预测仍未完成；全部旧资料、原门槛与无关改动保留，没有提交或部署。目标继续进行。

本批末尾静态核对补入7项已有Round14／15回归的CI选择，没有执行或移除原选择。返照文件本来已整档选入；新增原作者native比较实际依赖原两份外部se1，现明确标记`local_data`并固定文件散列，不能称为自包含CI节点。小JSON原被忽略，已精确加入白名单；期望沿用author-before起点并在测试运行时调用实际作者C，不由候选生成，也不要求跨平台Mac输出逐位一致。临时环境／native路径改用已有嵌套上下文恢复，不修改全局`_configured_path`。原源／门槛、24对分母及旧失败均保持；只是未运行回归准备修正，新增root为零。152生产源及唯一manifest／中央清单身份未变，不重复生成合同或导出清单。

<a id="root-force-and-cycle-inventory-continuation"></a>

## 第十六批延续：原典根力反证与周期职责清点

本批新增实际根因修复0，累计仍十八。第十五批末尾的原作者回归准备与CI登记已独立静读复核，原24对／7旧较差／16旧别名及152生产源身份保持；它们不因小参考白名单或local_data修正增加算法修复数。本批材料在`~/.codex/artifacts/fatebridge-audit-20261117-round16/`。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同或清单检查；没有再生成合同。

### 三条强档覆盖不能代替有效力量模型

本批先冻结原17差异／两约束、原页及当前所有者身份，再重读1947年任注本PDF416、相关相反例及NLC根类／身印页。HJ06原页写寅月寅时的甲木“木嫩气虚”及丙火解冻敌寒、丁壬合化木反生丙火；旧三档“弱”是保留的来源注释，不能说原文直接给出当前工程三档值。局部合化语境不等于当前相邻非日干合绊政策，也不足以扩出普遍化气系数。

只对原HJ06及XQ30执行两次实际服务函数观察，无协议调用或完整367重跑。HJ06仍为工程强／精确数值中和（3358/5615），三个强覆盖前提均真。依当前源码作静态优先级反事实：只删当令多旺根仍落两本气根强，再删仍落多根有根印强；全删才落数值中和，仍没有解决原弱注释。反事实没有修改或运行拷贝求解器。不能据此进行甲寅特判、调整权重或清除旧差异。XQ30仍数值强（59/75），午中己土三个真实实体保留；原“无土”语境尚不能支持删除藏干。

这定位到有效根力、寒暖发展、印身承接及作用优先的通用规则缺口。根存在、工程份额与完整原典力量裁定仍分别交付。原33项关键源／资料与本批45项身份无漂移，17差异／两约束及SJ05／QQ02旧失败不改判；本批16个相关定义的支持／反证清单只记录实际完整或局部阅读范围，不提前扩大中央覆盖。

### 金口诀四条疑文不能据合算回写

四条已有候选保全：P05／P25在所选确定公式下本可重建，属于课结构／定义冲突的负控，不能混充16条重建差异。P35要同时符合辛人元及丑位朱雀，日干约束交集为丁，但固定子日支又不容丁子；网上壬子仅修人元却破贵神。P52的甲申加显式昼贵只是多条件约束解，原字和观星昼夜没有唯一订正责任链。

未猜日期、地点或昼夜，也未重跑64课／240贵神格／120遁干格。原课型54合／4不符／6未决、重建46合／16异／2缺日保持；旧16条完整逐case actualrows本批未定位，不能宣称已逐条覆盖。书影欠定不等于当前确定公式已被唯一反证，0可安全patch。

### 六个完整所有者的逐职责归层

完整重读八字根与预算五所有者895行／19定义，加人类图周期828行／23定义，共1723行、42定义（32函数／方法、10类，含6嵌套函数）及33直接模块绑定。旧6组13职责保留并逐项迁移，现103组205职责；29个既有定义与33既有绑定首次具名，没有新增／退休生产定义。职责、来源、门槛、交付和类型分列，不将42节点或205职责称为算法修复。

独立静态复核收窄了快照实际显示范围，并修正草案Markdown原生旗标中的未转义竖线；初稿外置保存。这些是清单准备问题，无新增生产根因。人类图实际周期路径仍调用native scalar calc，精确民用参考轴另存；不盲换成TTInstant。新读出版方周期／词典／六线与Swiss接口，只支持所读定义及编号，仍不能裁定土星／凯龙人格与设计起点、逆行首末触、连续穷尽或物理／现实效度。旧12量化近峰和其余旧失败保留。

最终中央清单为4209组／12651职责／4973文件符号、688实现文件；7263定义中4377已具名，2886定义／645文件仍待具名。P0 355／P1 451／P2 375／P3 860，2168组仍未分类；2097绑定与2147结构语句队列重叠，不相加成算法数。本批仅导出一次静态manifest，8612600字节，SHA256 `62a0f99a00cfce04596962386dccba02601185f76a426add284793b65a91fe92`；中央清单SHA `e6672d0652d68e3620151c99a02557bbf76ea58944b3d823acd31c21fba8b734`。158所选生产源同before／live／manifest一致，未运行check_inventory；文件身份与完整未决见外置最终报告。全仓目标继续进行，未通过的传统、物理、独立专家、真实模型／安装／部署与预测证据仍未完成。


<a id="temporal-chain-and-native-event-continuation"></a>

## 第十七批延续：时间力源公式链与原生事件成员

本批确认并修复一个独立数值根因，累计十九；原生事件的TT成员及入宫起盘保点是已有根因的传播补全，新增计数0。太乙与紫微只有有界来源／旧输入复核，新增计数也为0。没有按94个字段、36案例、审读定义或协议调用拆分优化问题。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`或清单checker。普通调用合同生成一次成功，生成文件无变化。

### 时间力提前舍入的独立源公式对照

固定Santhanam卷一印刷268与277页注释，保留Raman76–77截至Hora的星战输入集合。原Natha／Ayana叶值已正确舍入，但同次Kala／星战链又消费这些显示值。现在两私有精确公式所有者同时服务原float API和复合计算，精确Natha／Paksha参与星战，精确Ayana参与Kala及太阳运动力；不改原典读法、分支、系数、缺失值或封顶。前置回执按实际全部输入键给`exact_inputs_virupa`，Kala声明算术策略；上游Sthana／Dig继续是其已交付二进制操作数，不恢复原公式全部精度。

修复前冻结四实际坐标输入及32受控操作数，独立python-flint0.9.0／FLINT3.6.0及整数IEEE编码器不导入产品。全部3,782字段的严格最近binary64差异94→0，其中实际坐标输入8字段、受控86；原3,688相同字段保持。原1e-12粗门槛前后都通过，原叶值／已舍入前置总量／前置显示输入不变。完整36输出差分另核：94数值、690精确输入表新增、690旧Paksha单项回执移除、36策略声明，其他元数据、分支及缺失值变化0。独立当前实现peer接受这一根因及完整参考分母，未执行测试。

便携小参考保留全部36输入及3,782独立期望路径，来自修复前FLINT而非候选输出。新回归写入既有自包含CI模块；三个旧回归只改读完整精确回执并保留数值标准。详见[时间力精度验收](precision-acceptance.md#时间力源值在星战与合计中的延迟舍入)与同轮`jyotish-kala/`。

### 原生TT成员与完整三端

十二固定源案例保留同一Swiss2.10.03、原生数据与作者C比较，四季交点维持0或一TT间隔差，原1毫角秒门槛均通过。木星2001-01-25T03:00UTC的原生同点因逆解标签晚1微秒而被旧路径放到未来；现按源TT分侧，原+1微秒标签保持，三同刻控制2/3→3/3，其余11完整时刻输出不变。前后各40,660实际motion记录中40,658条搜索／来源查询相同，仅该例最后两条选定结果验证查询改变。四个原季节案例的实际领域起盘消费者均收到原求根TT、标签不变；这不是四个新独立输入或完整服务前像。原64细化／8次显示同侧门槛、Round14十六别名、连续物理端点和停滞擦触完备性继续未决。

共同冻结1,482生产Python／JSON路径后，印占三原请求、返照一原请求及春分盘一after-only请求，共15次REST／新stdio MCP／CLI全部成功，各场景完整业务仅排顶层`run_metadata`后三端相同，窗口内源漂移0。印占每请求每端21处变化仅是策略与回执，数字业务保持；不把这三个运输场景冒充94字段的数值反例。返照每端13处变化完整保留，涉及土星／木星／北交点最近及下次UTC／本地标签和摘要。春分UTC2026-03-20T14:45:57.445059没有before，不写成成对比较。完整源和协议范围见[事件成员说明](calendar-boundary-audit.md#native-event-membership)及同轮两个protocol目录。

### 原典未决与继续范围

太乙重读19定义并用11预先固定输入核对独立转录正文三年环，原88／90／91／117／120表文冲突保持；阴37仍为计算坤25、原表午25及源位重算27，直符中元33格不能用整体移原点解决。紫微复用原八输入，528星记录／192周期格／344组同原iztro2.5.8参考；这是旧输入的限定重核，不能替代原13,936大分母或原典认证。两个领域均0生产patch，未因新读资料清掉旧失败或升级来源资格。

原八字17差异／两约束、金口诀16重建差异与2缺日、太乙／奇门／壬学异文、原物理与连续域失败全部保留。完整细算法数、每一定义的执行与专业来源、独立专家验收、真实模型、安装／部署及预测效度仍未完成。下一批只读发现另在Round18外置目录，不算入本批生产改动或算法通过；全仓目标保持进行。


四个完整所有者本批实际审读1,418行／34定义／13直接绑定，另只核对`TemporalBala`相关类及新增字段，不授予整个输出模块新覆盖。五旧粗组21职责迁移为52组80职责，另五既有组只补实际归层；7新增生产定义与16既有定义首次具名，13绑定首次具名，没有将它们当作23项算法修复。中央现为4,256组／12,710职责／5,009不同文件符号、689实现文件；7,270定义中4,400已具名，2,870定义／642文件未具名。P0为367、P1为466、P2为382、P3为883，2,158组仍待归层；2,084绑定和2,134模块结构语句队列重叠。两套独立静态AST身份一致，工具目录仍93、MCP92／REST91／CLI92、66共享方法；这些是源码清点口径，不是最终算法数或专家通过数。

本批唯一静态manifest为8663202字节，SHA256 `427e9c57020cc0ef066c6bdcad0654f9bd02b3c65248f6ac3d164e7067abe637`；中央清单SHA256 `908f0cdf3a0cc3158cab2836484dfd514d6a1b22676208ba5da972589fa89aba` 与导出及交接输入相符。161所选源、1,482生产Python／JSON及导出源身份一致，无漂移；1507源码／数据身份保留，未解析行0。未运行`check_inventory`，没有重复导出或合同生成。完整封存见`~/.codex/artifacts/fatebridge-audit-20261117-round17/report.md`及`inventory-final-artifacts.json`。


<a id="relationship-mode-dispatch"></a>

## 第十八批延续：关系盘准入、月相源对照与支持职责

本批新增一个经独立after复核接受的调度／准入根因，累计二十。先核对1,482生产Python／JSON路径与第十七批封存完全一致，再分别推进关系盘、现代月相、显式梅花与印占已审身份的精确清点。完整细算法数、全部定义的运行／专业来源接受与全仓SOTA目标没有缩减；原八字、太乙、奇门、金口诀、物理／连续域及预测效度未决全部保留。没有执行pytest、收集、CI、格式／类型、构建、合同`--check`或清单checker。

### Marks未消费共同盘的准入根因

四完整关系盘所有者共1,271行、27定义（含一个嵌套残差）及五绑定均逐体审读。支持层与P2几何／产品约定分列，未具名不等于从未读过。实际源审读保留Astrodienst当前Davison变体正文；Composite当前HTTP200是浏览器挑战，Marks原站404、镜像TLS主机名校验失败，均没有冒充新原典认证或绕过校验。原作者镜像／UT1亚秒／经度展开政策和七曜自定义关系评分的未校准资格不升级。

修改前冻结四个实际服务请求：原A/B的未校正／球面Marks，以及两人40°N、经度0°／180°的球面Marks与选中TimeSpace负控。球面共同中点在北极；每人与该点再取中点在原子午线65°N。原Marks先起一张不会交付或消费的共同TimeSpace盘，在北极Placidus失败后阻断尚未进入的两个个人盘。两条独立原生C `houses_ex(P)`调用已在固定个人位置返回12宫头／8角值；不需要把共同盘宫位当个人盘准入条件。

修复只收窄一处条件：仅`normalized_mode == timespace`时起完整共同盘，Marks仍按原Davison变体求必要共同数据并起两个个人盘。没有添加异常捕获、宫制回退、纬度截断、默认宫头或新方法。相同四请求after中，原两普通Marks的完整业务／快照差异0，起盘次数各5→4；极区Marks实际起两张40°N本命盘和两张65°N个人盘，均保持Placidus／原黄道，各11星体、12宫头。选中TimeSpace仍返回原Placidus错误，完整错误差异0。

原生个人宫头与实际共享起盘器交付宫头的描述性最大差约1.98e-7／7.40e-7度，完整记录保留。预先规定的原生对照是请求宫制在这两位置可计算，不是新逐位宫头验收；共享起盘器既有provided-TT／canonical-angle约定未被此调度修复修改或认证。没有凭新容差把旧数值失败改成通过。

三固定请求（普通Marks、极区Marks、极区TimeSpace）各经真实REST／新stdio MCP／CLI，before9次、after9次。普通请求每端完整before／after差异0；极区Marks由400／true／1变200／false／0，恢复后的三端完整业务只排顶层`run_metadata`后差异0。TimeSpace保持400／true／1，逐端完整错误不变；原错误形状另有MCP的`operation/status_code`和CLI的`status_code`差异，仍完整保留，不称全部9次完整相同。各窗口1,482源身份稳定，唯一生产变化是该一行调度；三份实际MCP完整工具定义无变化，不只比较输入Schema。

新增一项自包含实际三端回归，保留所选TimeSpace拒绝。旧调用次数测试原要求Marks额外起共同盘，现只把该Marks元组从`(0,1,2)`改为`(0,0,2)`，其余断言／输入保持，没有删原数值参考或放宽标准。两文件只编写未运行，新增节点在既有CI runner精确登记。完整原输入、调用转录、原错误、全输出及每一差异见同轮`relationship/`。

### 相位独立原始DE440与直接作者C

先确认现有官方CALCEPH5.0.1／SOFA2023-10-11二进制、原DE440全文及ICRF／TDB／NAIF接收地心资格，再冻结完整2026年1月TT窗、四相位及原门槛。实际一次生产窗口得4事件；独立不导入项目的DE440／SOFA参考与直接作者C Moshier各求4根。336条生产原生调用有同TT直接C控制，六维state（含符号零）及旗标逐值相同，4选定TT相同。四项原0.01度线均通过，新／满月原60秒线2/2；季度时差只描述，最大交付减DE440约2.458秒，不新设季度时间通过线。

这四事件与旧2026数据重叠，不是四个新独立历史或留出样本；同库闭合与毫秒显示不代表毫秒物理精度。原248／1302／25／50资料未重跑或合并；混源连续性、详细动力学／框架、观测钟时和现实效度继续未决。1,181冻结身份含1,155生产Python的两个源窗口均稳定，全部源调用结束后才落关系盘修复。新增根因0、生产算法修改0；[完整有限源比较](precision-acceptance.md#月日相位的固定单月独立源对照)与同轮`calendar-comparison/`保原始四根、源样本和失败资格。

### 显式梅花与已审印占身份

梅花闭包完整四所有者774行、14函数及五绑定，其中只有一个原未具名函数是P1季节规则，其余支持／已读身份不能称为十个缺算法。实际17个预注册顶层起卦调用涵盖12方法及五项歧义／方向／字形／声类反控，整数seed、上下动爻、本变互卦及指定元数据全相符；17来源身份稳定。所报声类上2不按旧原例去3覆写，from南方不反转，简繁字形只影响原例文字匹配。旧9例＋4探针、480场景、四项语义未决及原页均保留；没有通过更换读法制造或清除失败，新增根因0。

印占先对账旧23所有者／114已审函数。现119 AST身份包括116函数及3类壳；新增的两个精确时间力helper已在R17具名，不称本轮十个新算法。原54未具名身份为51已审支持函数和3类壳，现逐体读当前函数及类自身结构后补真实角色；101旧文本同一身份与13跨阶段变化分别保留，不以qualified名称相同证明body未变。79原未具名模块绑定中43项取得实际值及61个明确消费者引用，其余36继续列队；不按文件名推断计算角色。原典来源、每种输入实际执行、完整六力、物理与预测仍分别验收，清单登记新增根因0。

### 最终清单分母与封存

四scope保原7组36职责，按实际定义、分支、参数及支持迁移为193组367职责；新增具名91既有定义及57绑定，没有新增／退役生产定义。最终4,442组／13,041职责／5,157文件符号、696实现文件；7,270定义中4,491具名，2,779定义／618文件未具名。P0／P1／P2／P3分别392／503／414／982，2,151组仍待归层；2,027绑定和2,077结构语句队列重叠。印占36未核消费绑定仍待审，未放入已审行。两套静态AST身份一致，不是全部分支执行或算法总数认证。目录仍93、MCP92／REST91／CLI92及66共享方法。

唯一静态manifest为8853961字节、SHA256 `e34234c60695fe8ade59e635b3a8642f8986716d753a2337bd6f017622b9d70c`；中央SHA256 `c39db141b6dce5084c8c6bffa9276afac27e0fd154d4e5897e98e40947b36977` 同交接／导出一致。1,482最终生产Python／JSON与live／manifest同值，无漂移，1507源码／数据身份保留，未解析行0。没有运行`check_inventory`或重复导出。本批模型、目录与合同未改，三场景实际MCP完整工具定义前后相同，未重新生成合同，亦未宣称合同`--check`通过。原失败、来源、真实模型／安装／部署与现实预测门槛均保留；目标继续进行。完整外置报告为`~/.codex/artifacts/fatebridge-audit-20261117-round18/report.md`。


<a id="calibration-and-c04-source-axis"></a>

## 第十九批延续：校准尺度与C04源轴

本批确认一个独立数值根因，累计二十一；C04主点传播仍属既有保留TT根因，新增0。没有将40个失败字段、八个源码消费者或已复读的定义拆成额外问题，也没有声称本批解决十个独立根因。全仓目标仍在进行，未达到每项算法／定义的专家或SOTA验收。材料在`~/.codex/artifacts/fatebridge-audit-20261117-round19/`。未超过50，未运行pytest、收集、CI、格式／类型、构建、合同`--check`、清单checker或其他项目检查。

### 非惩罚校准的尺度相关早停

离线职业研究评估器的logit校准只中心化输入，绝对score停止条件随预测变量单位变化。修改前冻结17组合成数学输入、原门槛及独立参考：十组对称二项设计覆盖五个精确概率跨度和两种斜率方向，另保留原27对解析控制及六种未定义状态。独立mpmath1.3.0、110位参考不导入产品，也不读取候选输出；对称设计有唯一有限极大值、正定信息和相同的非零似然增益。

八组输入的40个数值字段原超门槛，其中六组在迭代0把零斜率报为finite_MLE。修复只在同一函数内增加可逆的中心／尺度坐标，继续原二项似然、IRLS、线搜索和原容差，以同一Jacobian还原系数与Wald协方差。原66数值字段由40失败变0，35状态／null比较前后均符合，原解析控制和六种未定义状态保留。旧BCa／SciPy参考与10000次抽样分布未重跑或改判。独立最终peer完整读当前函数、diff、全部17before／17after和每个比较字段，无静态阻碍；只接受这一个限定数值根因。

独立17组期望随小JSON保存到既有tests/data目录，新增一项既有文件内回归和CI选择；原30函数及装饰器不变。可移植回归、来源哈希、忽略规则与selector另经静读peer，仍未执行。一般非零中心／全设计收敛与渐近区间覆盖率未验，数值校准不生成职业预测，也未增加真实研究主体。详细推导与资格见[校准精度记录](precision-acceptance.md#calibration-predictor-scale)。

实际离线CLI的Schema给出当前分析指纹，携旧源码指纹的合成空记录方案在指标／抽样之前被明确拒绝。首次适配器错误把冻结文件名改为不存在的名称，其FileNotFoundError原始日志保留，不能计为预期拒绝；预先记录修正后只恢复原文件名，输入、门槛与源码不变。共三次CLI尝试，两个合格边界观察、一次无效适配；没有静默迁移旧登记，也没有用REST／MCP调用私有评估组件。

### C04同一精确源轴与已解TT

原九输入显示，UTC至TT主点本已符合独立原子偏移9/9，但向C04传入float后，首日前1微秒及末日后1微秒被错误接纳。现在源十进制DUT1、历史／现代原子偏移、TT锚点和UT1保留精确值；范围、bracket、权重和前向同轴，反解直接求同一仿射段的逆。共有解析器返回TTInstant，原float API为实际SDK适配；物理历元、太阳钟、旋转姿态、源回执和出生前朔望fallback消费该主点。默认Swiss运算及fromUT1原到期标志政策不变，不新增公共字段或来源模型。

原九输入的成员失败2→0；七个原可评前向的UT1浮点与原最近值／0.2毫秒门槛保持，三个原可评逆的浮点也相同，当前完整有理TT另与原精确参考3/3相同。这三行共用一个实际IEEE逆查参数，不增加独立样本数。四个本来域外的显式UT1浮点现拒绝，不把它们改称旧插值失败或通过。六个原源行作after-only typed控制，前向／逆／已知TT回执6/6相符；不混入paired-before分母。源末端TT的最近float实际晚14.201微秒，必须拒绝，不能贴回精确端点。原测试前像、0.2毫秒线、22控制、23638日／70911内部点、五项历史Astropy差异和末端不可用均保留，新增四聚焦回归未运行，沿用既有整模块CI选择。详细范围见[C04源轴与旧失败](precision-acceptance.md#c04-retained-source-axis)。

实际两个原合法整秒请求，各经REST／新stdio MCP／独立CLI作before与after，共十二次调用全部成功；同版本每个case完整business只排顶层run_metadata后三端一致，实际MCP工具定义完整比较零差异。每次六调用窗口的1482个生产Python／JSON身份均无漂移，没有为内部类型变动重复生成公开合同。原始Pydantic alias警告保留，不能当新数值问题或静默删除。

before／after完整业务并非不变：卜卦107项、择日20项差异在三端各自相同，全部逐字段保留。两者UT1各移动一个JD浮点间隔，源权重／连续秒差、宫轴和福点／宫头距离操作数随之改变；卜卦五个时间显示字段因同模型精确反解移动2–13微秒。原离散标签与其余业务保持。这是给定来源下的数值传播说明，不据此宣称107／20项独立优化或完整天文绝对误差下降，详见外置`c04-protocols/field-explanation-review.json`。

四个C04聚焦回归最终归入已有自包含的`tests/astronomy/test_utc_clock_domains.py`，沿用原整模块CI选择，没有新建单次测试模块。初稿误选依赖四个未跟踪参考文件的本地容器；静态peer发现后迁移。随后端点分支因宽泛首匹配误插默认Swiss用例，已按完整函数原像恢复，并只在两个实际C04用例调整已证域资格；错误阶段及修正前后全文保存。冗余四个新CI节点也已撤去。两次均为尚未运行的测试准备问题，不计新生产根因，也不以静读替代执行。

本批唯一静态manifest导出成功、stderr空，没有调用check_inventory。中央为4461组／13053职责／5166文件符号、697实现文件；7272定义＝5337函数方法＋1935类，4495具名、2777定义／618文件仍未直接具名。P0／P1／P2／P3／null＝402／503／417／1000／2139；2022绑定与2072模块语句队列重叠，不相加成算法。真实新增生产定义只有一个源求值载体和一个共享解析器，无退休；四个新具名定义另含两个旧校准定义，五个源身份绑定不作新算法计数。中央SHA256 `b3f4eb85dc1a4aec5a1c4e472937777612b54416b01acc071f69c7ee9b76c17b`；唯一manifest8898114字节，SHA256 `1f71be69540414957f81d48c3ec5cc6e68f44018350b25164311ecf74d05ffa0`。1482生产Python／JSON最终身份与导出一致；九个预期生产变更之外无源变更，完整源码／数据索引1507项。源阅读、优先级记账和导出不授予算法独立通过，完整细算法总数仍未确定。

### 保留的原典分歧与未决

果老Moira与太阳生成两个所有者逐字节等于此前完整审读及原selected-rule证据，复读不作新算法修复或新独立样本。12兼容名的617808所选单元原通过仍有信用；完整规则图的额外reject边及整盘／古籍仍未验，文档只澄清这一区别。太阳生成的七处刊数分歧、原29行81单元和终端空值不因同多项式恒等而改判。职业研究评估器是离线统计工具，不能混称新的果老断职业规则。

六爻复读十个定义的470行实际范围，并按原书页资格冻结十二次组件操作，全部声明字段相符；强弱、远近等是给定前提，不是整盘验收。原4096、反伏吟十例、进退九例及三条订正范围保持，不因重复调用增覆盖。八字17差异及两集合违规、太乙／奇门／壬学异文、全部语义算法与分支、真实模型／安装／部署、专业独立接受和现实预测仍未完成。仓库内保留自然领域所有者与必要小参考，单次脚本／原始日志放在外置审计目录；无关改动未清除，没有提交、推送或部署。


<a id="hamburg-retained-source-arc-continuation"></a>

## 第二十批：太阳弧源值、实际链路与原门槛

**全仓目标仍未完成。** 本批只新增一个独立数值根因：原两太阳黄经的精确差先交付为float，再被内部几何回读，造成阈值及坐标变化。领域层现在持有同次不可变`SolarArcState`，由原两Sun求唯一精确弧；原字典SDK入口只在交付时投影。六个既有所有者与一个窄源值所有者自然衔接，没有新字段、依赖、容许度或源码答案表。累计21→22，不把179字段、18案例或同弧传播拆成优化数量，也未达到十个独立根因一批的要求。

原六对Sun与三个MC相邻float构成18个预冻结数学输入；独立整数格与显式最近偶数编码参考不导入产品、不使用Fraction oracle或候选答案。原完整门槛的179项差异／九例（含六个误命中）变为0：72旋转、3600关系候选、960共有余量、324混合组及12混合余量全部保留，零弧控制未删。18个显示弧本来正确，不能冒充修复。旧字典→显式float→几何负控的全部逐例结果仍逐项等于before，未重新解释调用者真正提供的float。细节见[精度与限制](precision-acceptance.md#hamburg-retained-source-arc)。

一次透明合成的实际`enrich_solar_arc`在原一度线下消除90／45盘两项Mercury→MC误命中；显示150、22本命／22推运因子、原native／Sun角色／TT／缓存／cohort和网格校验保持。完整10922项输出变化外置保存，没有把其他接触移除、八个坐标投影及所有下游差异都追加为独立验收。注入黄经明确为数学见证，原生星历调用虽然实际发生，也不说明注入值来自星历。

同两组原公开工程请求各经REST／新stdio MCP／CLI，before／after各六次成功；完整业务仅排顶层run_metadata后同版本及跨版本均零差异，两实际工具定义亦零差异。另同一零龄五网格REST前后均200，三computed／两target-before-birth unavailable与完整业务保持。后阶段合计七次，1483生产Python／JSON前后身份无漂移；不是当前常驻聊天客户端、真实模型、安装或部署验收。原零龄before观察器保存响应后误逐path重复整map散列的中断／退出130记录仍完整保留；有效原响应未重跑。

after-only传播参考仅复用18原输入：162日子午坐标、36形式源条件数值及18布尔符合；布尔全False，不含True／两度边界，也不增加paired-before或根因信用。初版报告三项0与0/1字符串差是有理表示差别，原报告保留，另存精确值比较修正；产品和参考未重跑。日子午跨度仍用投影坐标，本批没有其新反例或源精确跨度通过。

宿曜、人类图与八字三条并行来源复核均0新根因、0新领域／数值参考调用。原宿曜210异日及半日／闰小月／星室异本，人类图旧激活及桥接证据的有限范围，八字367记录／321输入、17差异和两集合违规全部保持。没有足够原典算子时不调权重、改标签或把未知当相符。

原35组70职责迁移为53组92职责，完整原验收前像与映射外置。当前中央4479组／13075职责／5179文件符号、698实现文件；7277定义＝5340函数方法＋1937类，4505具名、2772定义／618文件仍未直接具名。P0／P1／P2／P3／null＝402／503／431／1006／2137；2020绑定与2070模块语句队列重叠。实际净新增五定义（另两原错误类型定义迁移）、十个新具名位置及三绑定分别记账，完整语义算法总数仍null；支持职责不升级为算法通过。

便携18参数回归沿原整数参考固化，原三函数及辅助函数AST未变；三个旧测试只迁移typed输入或错误注入接口，28日子午故障及八mixed故障标签／原参数和断言保持。唯一不可由typed值构造的旧任意status改为构造边界TypeError。夹具可随仓库携带，CI原整模块选择已覆盖；新旧测试均未执行。累计22未超过50，继续不运行pytest、收集、CI、格式、类型、构建、合同或清单检查。

独立源码、保存结果与回归静态peer分别记录，不能替代独立专业人工或运行测试。Bonert原作者索引摘要只支持统一太阳位移；本批原页访问遇JavaScript challenge，出版社AL319 PDF超时，未冒称原页取得或历史时间钥匙通过。全部原典、物理模型、连续域、现实预测与全项SOTA仍未完成。无重置、提交、推送、部署或依赖变更；无关改动保留。完整证据在`~/.codex/artifacts/fatebridge-audit-20261117-round20/`。


本批唯一`--manifest`静态导出成功，未调用checker；中央4020710字节、SHA256 `09861c0637ec0e021b480345d827c54bb27e9fb8c523eaa8f4d9f51c565621b0`，manifest8919795字节、SHA256 `022903b1ce78e07ed25986ea83746c85808fb72c2e9c0b3b40486c7c0259d481`。全部93公开声明与R19逐值相同；完整源码／数据1508路径相较R19恰六旧变更加一个新模块，余1501项不变。7所有者39定义已读，其中38直接具名；旧`biwheel_geometry.contact`闭包仍在2772未具名队列，不把审读等同具名完成。导出不授数值或全仓语义通过，细算法总数仍为未确定。


<a id="planetary-retained-source-arc-continuation"></a>

## 第二十一批：行星弧传播与实际剩余源差距

**全仓目标仍未完成，累计独立根因保持22。** 行星弧的原两源黄经差与逐点旋转仍在相位判断前舍入；当前与通用太阳弧共享`source_arc_positions`纯域函数，保留给定两float的精确差和全部旋转值到原相位门槛。三个既有所有者改动、净增一个共享函数，无新时间／星历载体、字段、参数或校验。通用Sun仍使用原两个实际Sun操作数，不替换成显示／归一别名，原1.5度与top8保持；行星弧原缺源Moon分支、orb0至15、五相位和top12保持。这是已计R20源弧根因的传播补全，不按九源、字段或接口凑新优化数量。

修改前冻结9个数学输入，逐个覆盖实际公开七曜及ASC／MC九种源；每例9点、81位置与3645因素／相位候选。独立整数格和显式最近偶数编码器在未看产品输出时求参考：原16成员差（14额外／2缺失）、30位置字段及34个精确旋转输入差均变为0。完整139命中和逐例最多12、合计66条公开命中稳定序相符；源标签、目标原float、orb及其他元数据保持。显示弧原9／9已经相同，不能冒充新增修复，零位移／排序控制不删。原完整before、独立seal和所有失败分母保留，见[行星弧门槛](precision-acceptance.md#planetary-retained-source-arc)。

Moon请求与共享算法的Sun兼容负控，各经REST／新stdio MCP／CLI作before与after，共12次实际成功；仅排顶层run_metadata后的同版本完整业务一致。Moon跨版本只变Saturn／MC两点共六个经度交付数值，Sun完整业务不变。实际请求／输出合同、校验后的请求与两实际工具定义均零差异。全1483生产Python／JSON在各观察窗稳定，跨版本恰三个预期所有者不同。原Pydantic alias警告照留；未把freshstdio当作当前常驻聊天客户端、安装或部署验收。

### 地平事件的有限当前复核

先发现最初四个旧漏极值窗口已经在既有后续版本通过，故其重跑提案在执行前取消，原计划及身份保留。实际仅选原first-spectral失败序中每定义首个Moshier失败72／76，加匹配季节、半球、定义和构造偏移的Swiss64／68；后两者并非相同站点／日期控制。原33／30完整失败数组保持，不把四窗更新推广为全队列通过。

四窗当前都返回原顺序三个落／升／落事件，但76仍两项超原1毫秒线，分别约+2.173及+1.368毫秒。10个冻结TT／UT1同点光学及站点控制符合原1e-6角秒和0.0001米线；12个当前根括区间均对应旧独立C实际局部符号变化。原Moshier输入函数在根邻域多次变号的事实仍在，不能挑更近参考根、加epsilon或豁免门槛。此处补足当前状态证据，不给新算法或物理精度根因信用。

固定作者C原二进制、SOFA、绑定／ERFA扩展、源文件及编译回执的身份均核定；旧编译器本体hash未记录，当前编译器hash只表示当前可用，不倒推旧身份。只执行一次C10点和一次当前四窗加10点控制，未重求原作者根或重跑大队列。源码及参考依赖零漂移。另定位到Moshier Earth速度名义差分分母与实际浮点采样间距的潜在线索；单行分母C-copy只写计划，尚未编译或执行，未断言其解释全部抖动或能够安全改生产。

### 来源与清单继续推进

太乙14相关定义复核仍无充分通用规则支持补丁：原11差异分为九个同输入规则／表数冲突及两个始击源位分歧，阴37原三个位置／十个内部冲突另列，不造第12算差。米沢《武經總要》原定向旁证不替换1599《金镜》底本，原288两算、424表示差异及直符来源信用保持。公开非默认模型／宫制闭包读16具体函数体及13选项定义；hsys0至8与西占23字母是不同公开范围，India非支持配置明确partial，不能把已声明政策当新错配。两lane均0新领域／参考调用、0安全补丁或新增通过信用。

四个共享星历所有者的30个未归层组按实际分支细分为39组，原113职责每项恰一次保留；12组P0输入／坐标基础、一组P1因素范围、26组P3载体／来源／委派。原24定义及6绑定早已完整读过，本批不宣称新覆盖。原六义务Solar行按P2／P3拆开，阶段大组只移出行星弧义务，其余14项及Balbillus原限制不变；新共享函数另具名，算法总数仍未确定。

新的九参数便携回归放进已有整模块CI选择的太阳弧精度测试；原六顶层定义AST保持，完整collector与top12分别验，参考解压逐字匹配独立封印。没有新增CI选择或测试执行。多余重复的新orb断言已去重；一次清单迁移草稿在写入前因多余标签断言停止，简化后按源路径／符号／原义务精确迁移，错误草稿与修正留外置，不计生产根因。

当前语义清点、每一定义／选项的独立执行、原典异本、全部物理误差、专业独立接受及现实预测效度仍未完成。累计22尚未超过50，继续不运行pytest、收集、CI、格式、类型、项目构建或合同／清单检查。无依赖改动、提交、reset、推送或部署；已有无关改动保留，不宣称Git工作树全干净。


本批唯一`--manifest`静态导出成功，checker仍0；中央4034141字节、SHA256 `b9fba5671c810abf354160fa4d9b3931db31fb8c1c1ba4ccc98d3b4dc6225a19`，manifest8936238字节、SHA256 `888497522244779674b2a5eea5fdb591cf0c6cdf53d33e13a33ee89f00436c7f`。4493组／13082职责／5180文件符号、698实现文件；7278定义＝5341函数方法＋1937类，4506具名、2772未具名／618文件；P0／P1／P2／P3／null＝414／504／435／1034／2106。2020绑定与2070模块语句队列重叠；93完整公开声明与66方法同R20逐值一致。完整源码／数据1508路径恰三个所有者改变、余1505不变，无增删；1483 Python／JSON最终源map为`d7c34ccf8e2462f31b904a9f112eea71011b96d47957ab25e28e1d77a5ad5e83`，观察及最终身份无漂移。计数不是细算法总数或通过等级，完整目标仍继续。


<a id="actual-lunation-phase-continuation"></a>
## 第二十二批：实际星历月相方法、源算子分离与清单优先级

本批从已封存R21的22个独立根因继续，生产Python／JSON的1483路径起始零漂移。修复一个实际星历月相能力／默认方法缺口，累计为23；均速模型本身已在旧解读文档披露，不能说成完全未披露，也不把合理的均速约定本身说成算术错误。新增资格只限本批固定窗口，完整算法、每个定义／选项的专业独立验收和全仓SOTA仍未完成。各字段、wrapper、source choice、相位样本、来源哈希、兼容比较及重新归优先级均不另计根因。

### 月相方法与自然共享所有者

原默认只读取本命日月距角，以12.1908°／年推进，不能生成出生后实际日月星历交点。现 `build_lunation_phase_payload` 接收实际birth_info与native subject，经中央Sun／Moon来源、共享trace及每完整pair的同模型／DE版次cohort搜索45°八相。旧固定速率与单周期字段、生产常量及对应旧测试退休；不增一个仅为遮掩方法切换的兼容模式，旧run及原始源码／输出／断言完整外置保留。

Rudhyar的1959文章与1969章节支持实际出生后星历及日年对应；1949／1950两篇直接原文补齐八个45°区间和英文名称。中文为项目标签，半开角区／360归零及精确固定年键单独声明。1969原例缺日号、原星位只到角分及1959早期抓取资格保持，不拿印刷约数造精密真值；原文及条目见[实际月相方法](western-astrology.md#实际星历月相推运)。

原始typed交点引擎抽自研究四相所有者，保留实际查询的native TT、原生夹区和残差；不把未查询的精确出生TT或已显示毫秒伪装成求根点。研究四相保其Moshier／90°／半开窗／毫秒合同；公开八相沿用auto／require_data_files，不静默改Moshier或均速fallback。已有次限36524219／100000年键与六字段回执共用，原整数微秒换算数学不变。交点经共享UTC逆转换取得精确CivilPoint.day，先按0<age<=原cap筛选，再对Fraction作三位小数舍入；ceil微秒只构造搜索包络，不成为年龄真值或舍入wall阈。

### 事先固定的完整数值与真实三端

唯一工程输入为UTC2000-01-01T12:00、0°经纬度、热带盘、40象征年，即出生后40名义UTC日。源、flags258、八个目标、完整0.25日独立扫描、128次二分、C的1e−8度／1毫秒、DE440的0.01度／60秒及0.0005象征年显示界均先于候选输出固定。独立参考不导入FateBridge、不读旧或新输出，两个源根表先保存才互评，完整分母不按候选挑选。参考8,144,705字节，SHA256 `b481bb457c2cdb673e1e6d1dcab7a4688dd0e6a0c29359f91d858e6bf94e5f56`。

两个独立源各找到11点，顺序315／0／45／90／135／180／225／270／315／0／45。旧均速同序但11项年龄都超过原显示线，绝对误差约0.0040234761至1.0034034116象征年。新11个TT逐位等于原作者C，精确民用点和未舍入年龄误差0；三位年龄最大约0.0004688977年。全部同源与DE440角／时间线通过；两个独立参考自身最大时差约3.218651毫秒。所有候选点都在已封存源cache，无额外C／DE查询或参考重跑。完整原年龄错误、73／74项版本业务差异、实际Schema／MCP定义变化保持，不声称前后业务或定义未变。

两种策略×REST／独立新stdioMCP／锁定CLI，before及after各6次，全部成功；每版本完整业务跨端差异0，仅排除顶层run_metadata。1483源路径在每观察窗均零漂移。本地协议不替代部署、当前附着聊天MCP、真实模型或外部专家验收。研究四相另按同一事先固定物理40日窗口比较原版与新版，完整JSON及错误差异0，不把原Jan2026四相资格扩成所有季度／八相全域接受。

### 保留失配与补充内部来源观察

冻结比较中的公开哈希检查仍为false：既有公开边界和Schema递归省略sha／hash等完整性字段，不是观测到不等摘要。原检查及结果原样保留，缺失不被改判为公开哈希通过。另行冻结一次同严格请求的canonical execute_spec观察，原始计算trace与严格策略的两份文件哈希均等于独立参考；按既有公开规则及快照开关处理后，与首次严格REST完整业务逐值相同。该补充没有改生产公开边界、参考、门槛或原失败。

便携5文件参考只从独立封存结果提取全部11＋11根、精确年龄、括区、源状态及身份，没有从候选构造期望。实际源回归放在独立月相测试文件并标local_data，显式固定两份se1／暂清JPL覆盖，先恢复环境再恢复原生路径。原生命周期测试22个顶层定义仅退休旧均速1项，其余21个AST不变；短暂CI选择草稿撤回，最终CI文件与本批前像逐字相同。新测试未导入或执行；外部源案例按既有云端范围排除，并非改容差或对失败静默skip。

### Moshier外部算子实验不重复授信

外部原作者C的两份源码只改Earth有限差分分母一行，同当前clang／SDK／flags配对编译，进程隔离。原24个TT保留，无搜索新根。先冻结stock操作数，独立整数IEEE解码／最近偶舍入oracle先复现全部72个stock名义执行，再封candidate期望；后调用candidate。候选72／72符合实际原生节点间隔算子，本组也恰与精确有限割线最近编码相同，三组共216个位置分量逐位不变。

同24点再配对apparent／NOABERR Sun共96调用，全部源4／flags保持；NOABERR的72位置分量逐位不变，apparent经纬变化仅作像差路径的因果描述。实际节点有限割线、含舍入分子的C执行算子及连续物理导数是不同目标。现有Decimal连续名义步长所有者、原500Sun／2720planet信用、历史编译器身份缺口及原C分歧不改；本实验0新生产修复／0根因／0物理精度升级。R21原窗口76的约2.173／1.368毫秒两失败与原1毫秒线、原33／30失败数组保持，未用此实验选根或放宽门槛。

### 清单与继续范围

compressed_ephemeris的26原未分优先级组按完整函数实际责任细分为48组，131原职责每项恰一次、来源／消费者／验收文字保持；31组P0、17组P3。原26定义／七模块绑定已审过，不算新覆盖。post-yield窗口检查只在成功退出执行，finally恢复成功与异常的令牌；不为未证明竞态或防御假设加补丁。

新月相实际所有者、共享clock、请求与交付职责按新来源和受限验收另行登记；旧研究资格、原典异本、八字17差异及两约束、Taiyi／Qimen／Ren、标量TT与全部物理／预测缺口继续保留。职责／函数／类／绑定均不冒充细算法总数。累计23尚未超过50，pytest、收集、CI、格式、类型、项目build、合同／库存checker均未运行。外部C参考编译与声明manifest导出分别报告，不冒称项目检查。没有依赖改动、安装、reset、提交、推送或部署；无关在途改动保留，不宣称Git工作树全干净。


R22最终中央清单4,074,082字节，SHA256 `16d1cc0df61c5d1d603446f0cfb3cede80fe8826524bc5ae06a09383fe038e2a`。4531组／13116职责／5190文件符号映射、700个已映射实现文件；7283定义＝5344函数方法＋1939类，4514具名、2769未具名／618文件。P0／P1／P2／P3／null＝452／506／437／1059／2077；模块绑定2695位置（2692名字）、677具名／2018待归，语句2745、677具名／2068待归，两队列重叠。93目录／92MCP／91REST／92CLI／13family／66方法登记保持。unparsed行0不等于未分类职责0，更不等于独立细算法总数已知。

最终另修正模块说明中“每个builder只收本命字典”的旧泛化表述；1347行及整个非模块说明AST（含位置）完全相同，原数值与协议无需重跑。原协议源map `be67dac710a75b88d68ee3ba28ba3b899b0e2e4cbc5eaaf9bc32934c72015511` 保留，最终Python／JSON1483路径map为 `00ba0563378a9f926cf4d1429c546eefe6ca890f280fe16ed0d30f88fe034235`。为保持真实源身份，第一次声明manifest原样保留（8,989,612字节、SHA256 `edf39b6e60901b2f256309f382ed09745d85aa18c461dd9177f4a3a3b3a42585`），再另导出最终manifest（同字节数、SHA256 `57e14c411ecff2dd1cddf07506ce5920a42f713e468f8b2f34116928d0dc9f53`）；两次均为声明导出、checker仍0。两份manifest及偏离原一次导出计划的原因均封存，没有覆盖原记录。

最终完整源码／数据1508路径相对R21恰8个现有所有者改变、1500不变，无增删；15个外部独立源资产也均零哈希漂移。下一批14项具体定义义务只读登记owner、源身份、一手来源及独立工具，未启动新域／参考／协议／测试执行，不把14候选义务当14新bug。完整目标继续为active／未完成。

<a id="moira-full-source-profile"></a>

## 完整 Moira 源规则的显式领域方法（R23）

本批接受一项有范围的解释器能力补全，累计独立根因／能力改进由23至24。当前v3诚实声明兼容条件子集，不能将未实现的完整源覆盖全算作旧合同错误，也没有把14项语义职责或547个条件拆成多个根因。完整细算法语义总数和全仓专家级／SOTA验收仍未完成。

新增纯类型化源目录编译／求值所有者及原生事实适配器；`guolao.build_chart`只在显式注入外置`CompiledProfile`时使用新方法。原作者298声明展开为547条件、163逻辑别名；五个正常目标覆盖使原原生别名表为321，未强行改分母。原Hashtable顺序、急切操作、源文字自动抑制边、逐跳三段优先级、穿过false／未求值节点的抑制、周期缓存null、内部节点、别名与展示政策分别保留。unknown、作者未定义布尔false、原式abort及未求值不混同。详细来源、精确输入限定和公开范围见[源规则方法](guolao-source-profile.md)。

独立原Java在读取候选前先封源／26输入／门槛并执行一次；候选首次完成58个canonical求值，26,282条件—政策状态四字段、编译身份／顺序／rank／覆盖数、321原别名映射及完整有序喜忌结果全部0差异。参考与候选文件均零漂移，另有代理独立只读逐文件复核。16个完整源事实输入中的30个附加神煞和等分宿界为显式假设，不冒称原程序历法或天文生成。原诊断查询显示246条件有真假两侧、301从未为真，完整条件／动态图分支未通过；没有重跑原51484队列。

同两固定工程出生输入另实际调用显式原生方法，各返回547／163目录，未知条件均160，类型合同有效、原式错误0、错误纳入的未决展示0。命度／命宿、源黄经宿界、额外神煞与源月柱／农历日均未补造。与旧公开响应直接比较各有5项额外私有哈希字段：原raw门槛保留失败；单独预冻后对保存结果应用既有公开边界，19项预期源方法变更之外差异0。没有重算来替换原失败，公开哈希验证仍非通过。

现有v3公开路径before／after各6次真实REST／新stdioMCP／CLI全部成功；每版本跨端及同端前后完整业务差异0，只排除顶层run_metadata。这不是新显式方法的三端验收。原GPL规则目录与完整许可留在外部审计证据，不打包或静默调整项目Apache声明；当前公开默认没有切换。

金口诀位内旺衰／季节土旺、Dorothean阶段时长及Jyotish完整Cheshta／Moon-Mercury性质各发现通用定则或版本仍不足，均0补丁／0新增根因，原案例失败和分歧分母保留。没有根据单例调权、软件投票或用现代均位置冒充Raman表。

累计24仍未超过50，pytest、收集、CI、格式、类型、项目build、合同与清单checker均0；原Java外置observer编译、域／协议对照、AST／哈希读取和声明manifest分别记账。既有v3仍公开使用，旧子集测试保留；新增独立小语法控制回归仅编写、不运行。无新依赖、安装、reset、提交、推送或部署；无关在途改动与旧失败原像继续保留，不能据此声称整个Git工作树已干净。原目标继续active／未完成。

<a id="moira-explicit-source-provider"></a>

## 显式 Moira 来源提供器与失败后端的分离（R24）

本批接受一项有范围的来源提供器能力，累计独立根因／能力改进由24至25。33个神煞、504个角度输入、6048个事实投影、各命名空间及接口载体不拆作独立根因。它补齐显式源规则所需的来源事实；公开默认仍为已声明的v3子集，完整历法、真实宿界、原典与现实预测效度没有因此通过。

### 明确前提与原作者独立比较

同一Moira1.50Final源commit的外置资源由一个不可变provider profile读取。年表、干支表、月时、分组、主表资格及成对别名共用一个纯提供器；原长生使用酉首`twelve_signs`，不误用戌首`full_zodiac`。日夜与日／月经度只用于原卦气前提，各缺项按实际依赖保留未知；已知关闭／无源位置另列known_absent。资源与完整规则均未打包，项目分发许可未改变。

独立原Java先封存444组完整给定前提；原作者首个星位observer因FileIO.base未初始化而失败，但444神煞结果已保存并封存，没有重算。候选后续一次完成444×33＝14652单元，实际有序支宫、别名后完整宫位、主表资格及成对映射均0差异。两个部分历法投影与原144／60个完整上下文一致；原软件说明表、流年主表与公历转原历法没有纳入该神煞验收。

星位observer按原公开AppIO初始化后，完成56次原始与56次computeStar调用；原首失败仍记为历史第113次尝试之一。原28星目录及旧DE406文件与现代DE441资产分别保留。两个上下文共504个固定边界／严格距离探针先由独立整数IEEE oracle封答案，再比较纯提供器。504标签／严格近界及6048个十一曜／身投影均相符。原Java在两处boundary.nextDown因加360舍入返回`?invalid?`，精确圆周区间为室火；两项原结果完整保留，不把精确输入政策冒称原Java全等。

### 原生集成与未知覆盖

显式`MoiraNativeProvider`须与同源规则profile共同注入。calendar对象缺席时，只复用本次已有立春研究年柱和实际时支；对象存在时，其`None`字段不回退。来源层先移除其明确未知／已知无位置所对应的旧研究值，再覆盖源事实，避免旧值优先查找掩盖缺项。源月柱未知也移除原太阳季节四布尔，陆位神煞与其书影证据不受污染；现代赤经宿位不混入源黄经宿界。

原两工程出生的直接领域基线与两次新增调用比较，794／781项变化均落在事先声明的源图／来源回执／规则集／限制范围，其他字段和无关trace均0差异。第三次提供year=None、month=丙寅的工程控制，435项变化也仅在同范围；年柱没有被补入，源春季从给定月支得出。三次类型合同有效，源式错误与错误纳入未决展示均0；另一个合成merge控制覆盖@／%／$／?的替换与输入不变。三组事实仍缺命度、源宿位和农历日，不作为新增来源真值案例。

### 现代 SDK 原门槛失败

另一新候选用当前安装SDK读取原legacy目录。独立stock C参考在候选之前封存，固定两个TT、56星查询。输入、名称、flags和实际DE441文件身份相同，但原逐位门槛仍失败：56向量中42个、336分量中62个不同；56个精确修正点中7个不同。独立整数离线归因表明候选56点全都准确使用其实际SDK操作数，7处差异继承上游经度；没有证据支持修补下游算术或以编译器原因下定论。

随后同两上下文的直接SDK对照使用相同路径／cache顺序，不导入FateBridge。保存结果的336星分量、12个Earth分量、58组参数／flags／文件上下文及配置顺序均与原managed结果逐位相同；原对C的42／62／7失败不变。第一次观察脚本在配置前误hash不存在的slot路径，第二阶段离线比较误处理close的None路径，两项observer错误与原始输出均保存；只修正外部observer／离线比较，没有重取数值结果、重跑C／Java或放宽门槛。此诊断0新根因，不认证实际物理误差或SDK完整来源／构建一致性。

该未发布恒星候选没有仓库消费者，9512字节原像与原始SHA已完整归档到本批外部证据，然后移出生产目录；不保留空壳或兼容入口。归档0修复信用，不消除42／62／7原失败。领域／协议观察的1487源身份仍原样保留，最终生产1159Python＋327JSON＝1486路径另列；没有把未再执行的最终树冒称协议原观察版本。

公开两请求各经REST、新stdioMCP和CLI，共六次成功；同端对R23及本轮跨端完整业务均0差异，只排除顶层run_metadata。新提供器没有经公开请求启用，该结果只认证现有v3连续性；实际MCP定义中的新增可选输出结构另外保留。项目测试与检查继续为0，累计25尚未超过50。八字原367／321／17／2分母、太乙与壬学异文、R23原16完整上下文的301从未为真条件，以及全范围天文／原典／预测缺口均不改判。完整目标继续active／未完成。

<a id="source-calendar-policy-and-priorities"></a>

## 原历法口径诊断与共享历法／奇门优先级（R25）

本批从R24最终1486个生产Python／JSON路径零漂移继续，尚无新增独立修复，累计仍25。补齐59个既有位置组的语义优先级：共享历法39组178职责按实际计算、准入与支持拆为71组；奇门20组61职责维持20组。全局4675组／13288职责，P0／P1／P2／P3／未归层＝489／578／437／1153／2018。职责数不作细算法总数，原审读、具名与有限验收信用不重计。原始239职责语义每项保留一次，其中238条文字不变，一条旧缓存包装器的构造职责定位改至实际年表生产者，原行及更正证据均留存。来源、消费者和验收限制保持。

### 原作者27例仅作诊断

先完整读取所选原Java方法及实际调用链，分别核对普通输入、zone转换、调钟、太阳节气、新月、太阳历／农历和六柱。原资源默认longitude_adjust=2、DST=1、晚子换日=1；字段初始化的0不能冒称桌面默认。固定9个人工标签各选默认LAT2、显式标准钟0与LMT1，共27例。原词表使用原UTF16字节，同版本城市／DST文件按Git blob身份取得；公开AppIO与City.loadCities初始化采用作者流程，没有空表替身或作者源码补丁。

独立外置observer先冻结源码、既有class、JDK、27输入和资源，再仅编译该observer。两次静态peer后，原方法单次完成27例／108个所选历法事实；异常与stderr为0。配对位置查询1464次／8784分量，全部flags2、有限且无错误／警告，另9次EOT配对成功。配对调用发生在原结果保存之后，不是内部transit读集或嵌套次年模型的见证。源码1486路径、作者class／资产和输入前后无漂移；没有重跑R24的444神煞或504宿界队列。

原程序把节气／新月数组移到名义北京坐标，却把另一路当地标准标签交给成员判定；调钟后的标签另供年种子和日时柱。旧EOT还把UT数值直接传入ET计算API，原Java Calendar保留的子分钟字段、当前JDK时区数据与潜在嵌套次年数组各有限制。这些原行为已保存，不要求产品照抄。固定GMT 2024-02-04 12:00例，按原软件自己保存的立春名义UT约08:26已经在后，原太阳年仍因当地标准／北京坐标比较取前一年；该口径差异须先裁定定义，不能自动当成FateBridge差距。

本批没有因软件一致率而改动现行高精度时钟、立春边界或公开默认。完整原历法、实际天文、原典解释与预测效度仍未通过。项目测试、收集、CI、格式、类型、项目build及合同／清单checker继续0；仅源观察、静态编辑验证和声明导出按实际分别记录。目标继续active／未完成。

随后另行冻结9个原民用输入，只比较原标准钟分支，实际调用现行birth builder与默认v3领域builder各9次，不注入规则profile、历法或预设源事实。全部成功，原始完整领域输出已封存；9个GMT标签相同，9个年柱均符合事先从原已保存操作数独立计算的瞬时年界成员关系。与原软件历法年柱只有上述GMT案例不同，现行甲辰／原癸卯各原样保留。这证明该有限队列的年界侧别，不能用旧Java太阳模型的给定操作数认证现代星历物理精度或全时区、连续端点正确性。

纽约例的现行民用12:00−04:00与原标准钟11:00仍明确分列；时支碰巧同为午，不把标签差抹去或改作相同钟制。原月柱／农历日未注入现行v3，也不从其他历法字段拼成通过。1486生产路径与63项输入／SDK／星历／参考资产前后零漂移；生产代码本批未改，新增根因仍0。原作者27例及R24全部旧失败不重跑、不改判。


<a id="round26-positional-chain"></a>
## 位置力源值贯通与西方古典优先级（R26）

本批由R25的1486生产Python／JSON路径零漂移继续，累计独立根因／能力改进仍为25。修复印占位置力／方向力在星战前再消费显示浮点值的传播缺口，属于第十七批已有早舍入家族；6个计算文件、13个新增／变更定义不计13个根因。单一Uchcha公式与typed Sthana／Dig结果在名义和生时网格路径一致传入temporal→war，独立直接字典仍按实际交付数／缺项计算，没有从JSON恢复精度、增加显示／精确双入参或新模式。公开总量采用源式最终投影，旧显示分量相加判据明确保留为历史目标。

固定4个新合成坐标×4来源组合、另2直接控制，先以独立FLINT和原整数IEEE编码器生成盲答案，后各作一次候选前后观察。源式总量2/224、前置5/80、幅度7/12及带符号值14/112差异均归零；原560位置叶项、112方向叶项及26直接控制不变，336精确有理数与结构均相符。旧目标／四个因果分支及全部差异保留，不算44条重叠差异记录为44问题，也不重判原第十七批36／3782通过。原256总体的仓内便携选择只有3例／84行；旧数据字节不改，历史交付操作数重建和新的16源式组合分别验收。新回归及原mock边界迁移只编写未运行。[来源页图、原门槛与分母](precision-acceptance.md#jyotish-positional-source-chain)和外置`round26/jyotish-positional-chain-discovery/`完整保留。

两组固定合法公开请求各经REST、新stdioMCP、独立CLI完成前后12次，全部成功；同版本完整业务跨端0差异，实际工具定义不变。每例每端保留16项前后差异，全为源位置输入的精确回执字符串，其余已返回事实不变；公开输入没有人为注入合成失败。源码1486路径及3原生资产运行间无漂移，只有6个意图内源文件相对R25改变，首个修复候选的源map为`888ceba5f821bed6af1121d4a2641417b35fd78d1d43455f110b27df3b61b0a9`。真实模型、安装／部署、全部选项、连续域及物理／预测资格未因此升级。

西方古典原47个未分级位置组的171职责按完整所有者拆为112组：P0=2、P1=69、P2=4、P3=37；4个原已分级组不改。独立重建确认职责、来源、消费者、验收限制完全保持。13个实际位置链定义再按计算与支持职责迁移，所有旧义务留存；当前总计见中央统一索引，不把职责行当细算法总数。Python3.13的空AST字段省略导致的一次47项静态簿记差异已保留，locked-uv同源序列化确认不是产品错误。

奇门公共阅读器只观察到0/0页、控件禁用及同一404文件地址；99页元数据没有升级为可读原典证据，原9项义务不变。后续Ibn Ezra原文、Zoller变体与软件五点子模型的14项来源义务只作R27准备，未据现有明确子集发明新缺陷或拼入日／时加分。R24现代源42/56向量、62/336字段、7/56修正点失败，八字367记录／321输入的17差异与2约束，太乙／壬学异文及其他未验收范围继续保持。

本批项目pytest、collection、CI、格式、类型、build与合同／清单checker仍0；累计25未严格超过50，未提前运行测试。原准备性比较脚本的结构失配保存缺口在执行前另作修正版，初稿与冻结保留；一条迟到的AFTER参数提醒来自早期草稿，正确primitive签名修改先于最终冻结，未发生无效候选重跑。这些均0根因信用。完整目标保持active／未完成，不能宣称每项达到专家级或SOTA。


收尾静读另发现本轮新record:Object与两个summary消费者之间的类型缺口。SthanaResolution增加同字典的typed summary视图，两循环改读它；war边界明确可空局部映射类型。无新Any／cast、公式或JSON变化，也不将自修类型缺口另计改进。独立静读后最终同两请求补6次真实协议，均成功且相对首个AFTER完整业务0差异，源／原生资产无漂移；本轮协议总计18次但仍只有2公开上下文，原16+2算术与盲参考不重跑。首个中央／manifest保留原封印，第二份声明导出如实绑定最终源，不覆盖首份或冒作checker。最终1486源map为`ce4755fd43e79ce5d3d75de0feccf2891e7340b56eed839a45832b9ed74c0e56`，累计25和所有原失败／未决不变。


<a id="almuten-method-delivery-continuation"></a>
## 第二十七批：五点命主的同次方法交付与现代SDK残差诊断

累计独立根因／能力改进保持25，本批新增0。已有五点本质尊贵小计是明确可用的混合传统子集，现有证据没有证明一个新的数值计分错误。原典完整命主法、逐算法及逐定义的专业独立验收、物理精度与现实预测效度仍未完成，不能宣称全仓专家级或SOTA。

### 计分子集、来源及局部投影

实际读取Sela校勘《Nativities and Continuous Horoscopy》的公开镜像原页及原厂Solar Fire手册。前者实物版权2014，机构目录2013另列；printed101支持五处和5／4／3／2／1组成，后面还有相位及宫位，不替整个混合表、固定平手或完整法背书。6°／10°燃烧和18°日光是不同术语／来源范围，不凭数值不同宣布原文矛盾。镜像并非出版社认证副本，未作再分发权利判断；完整相位档位、累加及同分裁定继续未决。

三个原所有者只增加同次method、局部输出类型与快照范围说明，不改分数／胜者／点集。最终method的15项事实包括直接保留的实际is_day、权重、主要昼夜三分主、埃及界、Chaldean面与固定平手次序、实际参与／缺点和带适用范围的作者版本页码。参与列表来自同一次被接受的per_point；不补缺朔望。空集只说“未形成计分候选”，不扩成历史法不存在命主。输出类型支持已有部分投影，完整输入／工具方法登记和合同生成器的输入范围未改变。

四种固定合成覆盖形状（5／4／1／0点）验证旧业务事实与新增交付。原before及14字段after各4builder＋4snapshot观察保留，最终补实际is_day再作4builder观察；合计20个helper操作仍只有4种输入，不是20个精度样本。helper体内未调用原生坐标不代表整个进程零native初始化，导入／set_ephe_path内隐工作未受同一计数覆盖。没有独立数值或预测信用。

真实协议为同一默认Western工程盘：原before完整三端3次，14字段阶段完整和严格子树三端6次，最终15字段阶段完整REST1次及严格子树REST／新stdioMCP／CLI3次，共13次。全部成功；仅排顶层run_metadata时每阶段跨端完整业务相同。最终子树逐值等于实际完整REST，is_day=false与父层sect=night一致；较14字段完整结果只新增该值，快照不再变化。原before至after的method和两处snapshot业务差异原样保留。最终未重跑完整MCP／CLI，不把旧14字段观察改记成15字段通过。

实际输出Schema新增method属性与两种嵌套类型，阶段3只再加Optional is_day属性；输入Schema及所选工具非outputSchema字段不变，不能据此说93个工具的完整输出Schema全相同。实际1486生产路径与三native资产在各观察窗零漂移。该本地协议证据不替代当前常驻聊天进程、部署或真实模型行为。

### 现代SDK残差的有界因果排查

原R24现代源的42／56向量、62／336字段、7／56修正点失败不改判。本轮只固定原M00的地球与原顺序前四颗星，四个独立进程分别调用安装Python SDK、同一已加载SDK导出的C符号、既有作者fast和off二进制，共20次显式坐标操作；初始化／元数据另计。两原prefix重放门槛通过，同一image的C与Python全部30字段逐位相同。fast对SDK7／30、off对SDK10／30、off对fast11／30字段不同；off不能消除差异，不推出已安装历史编译flags或哪个物理更准。无SPEED时清零的速度不作为独立日速证据。

九个关联object的Apple clang21 producer、DWARF4无源码MD5及debugmap／mtime仅为具体元数据；当前九个编译C文件与作者源逐字相同也不能倒推历史链接字节。三份二进制及全部104执行资产不变，无构建／安装／新库变体。该诊断排窄caller边界与单一off／fast解释，未定位可安全落地的新根因，不恢复已归档实验模块、不接入默认后端或放宽门槛。

### 优先级、清单及继续范围

完整视日速所有者的28个null组／57职责按实际分支迁移为29组：24组P0、5组P3，原全部职责／来源／消费者／验收保持。12绑定保留所需“模块规则与配置”前缀；原提案格式遗漏、独立修正版及恢复经过外置留存。实际来源终结与配置／文件准入是P0，不因表现为trace或guard就当纯回执支持；16定义和12绑定已读，不重复授首次覆盖或根因信用。

五点交付新增7个P3组／14职责，两新类与一ID绑定分别登记；原快照renderer从未具名队列具名，不称新增函数。最终4761组／13321职责／5279文件符号映射，实际704实现文件；7358定义＝5378函数方法＋1980类，4590具名、2768未具名。P0／P1／P2／P3／null为515／654／441／1211／1940；直接绑定690具名／2018待审，结构语句690具名／2069待审，两队列重叠。根代理独立重建全部4761行，历史stage2中央与原14字段记录保留；细算法语义总数仍为null。

八字367记录／321输入的17差异及2约束、奇门9项来源义务、太乙／壬学异本、连续与物理日历、解释和预测缺口继续保持。累计25未严格超过50，项目pytest、收集、CI、格式、类型、build、合同与清单checker均0；新增回归只写不运行。声明manifest另行导出并记录最终身份，不冒作checker。无依赖变更、安装、reset、提交、推送或部署，保留无关改动，不宣称Git工作树全干净。完整目标仍active，后续工作继续。


R27唯一声明manifest为9,274,873字节，SHA256 `f651e6d64740e0121b44ae37b853fe80c399aac469393b7e15c5c80d0cf3d01d`；中央SHA256 `5ee75f698738970d72529d94535f2c43ca8dcac6fff380d3e535ad357e349f3b`。93完整目录／输入／66方法与R26逐值不变，manifest不含输出Schema；1511源码／数据在导出窗零漂移，1486生产源map为`86ec2ad80425ddef59c7699466a2e70fca170ca57866f823f954e75d88f26b8d`。中央／manifest原14字段阶段与最终15字段阶段分别保存；声明导出1次，checker仍0，目标继续。


<a id="dayun-source-ceiling-continuation"></a>
## 第二十八批：起运整数的源跨度取整、旧测试资格与并行来源复核

累计独立改进保持25，本批新增0。修复的是既有点保留／过早投影家族的一个交付消费者，不按13反例、71控制、14细义务或多个入口另凑根因。当前完整细算法语义清点、逐项专业接受及全仓专家级／SOTA目标仍未完成。

### 给定源量的离散取整

DayunStartResolution已经保留Fraction nominal_days，整数起运岁数仍经float(days)/3再ceil，可能把整数正邻域的实际余量抹掉。产品观察前冻结独立整数商余参考及全部71输入：年龄1至10的3n日，各含±1微秒、±1／16384微秒、±2／16384微秒和exact边界，再加zero最小1。原71项13个整数不符；当前只在原函数内改为ceil(nominal_days/3)，同一71项整数差异0，原另外十字段、float.hex、sourcepoint逐值保持。两版本各71helper操作、源观察窗均无漂移；无test导入，不把导入内隐native初始化说成整个进程零native。

这些是给定有理操作数的算术控制，不是71真实太阳根或预测样本。日历wall／实际选运不读整数值，本批不改动；公共整数实际经age_info.start_age传播至大运、综合时运和八字时运概览，Canping continuous也保留start_details。九专题等可能计算大运但不直接交付该整数，不能沿旧19工具列表泛称19项结果修复。现快照明确原始间隔整数与浮点展示，不让读者用显示3.0反算4。实现保留在原所有者，无新helper、类型、参数、epsilon或猜测性防御。

### 回归与实际协议的准确范围

新增一个亚微秒邻域回归定义（50参数），仅编写、未导入或执行。两个旧测试把真实SolarTerm.moment当精确point／exactzero，但两者没有相等保证；现改明确给定的calendar-grid源，保原整数边界和zero不延迟义务。原完整test前像外置保留，其余旧定义AST不变，没有删除任何旧测试，也不宣称未经运行的旧测试已失败。原真实太阳root、已保留physical point与全域日历分别接受。

一实际合法虚构dayun_analysis工程请求在最终两所有者身份下各经REST／新stdioMCP／CLI一次，三次均成功。仅排顶层run_metadata后完整业务三端0差异；实际请求Schema等于冻结声明，1486生产路径与三native资产观察窗0漂移。普通输入返回start_age=4、unrounded约3.0003999416959055，与纯有理边界反例不同；快照两条新限定文字真实返回。这里只有最终版本三端一致性，没有公共before。最初公共before准备在源fence处停止、尚未导入或调用；原稿与错误保留，未为制造前后成对证据回退源码或重跑。后续一处快照措辞补全另冻结stage2计划，观察器字节相同，旧0call计划原样保留。

### 来源复核并行推进，但不制造新通过

全self_data文件名及相关题名元数据共9687路径核对，旧02的970路径size／mtime保持，新增350为三处CHM展开目录；旧02之外8367路径。33宽泛奇门入口中27为新笔记／索引，未取得程道生《遁甲演义》的确切同书线索。文件名／目录未命中不证明本地无书，未执行EXE或展开361归档，旧四Archive底本、9义务、NCL404及阅读器0页资格不变。

八字复读30相关定义，strength长函数只读650–970尾段不冒全文；367记录／321输入、17差异、三约束中2违规、123有三档与244无三档来源全部保留。差异不全是异文，实质仍缺有效根力、印身承接、寒暖与适用域的通用来源条件；没有以删覆盖／藏干、改注释或float再调整代替规则。八组假说均未证明新可安全补丁，0新数值重放或接受。

DE440 owner完整478行、12函数与19AST节点分列；原12组89职责及五profile来源／consumer资格保留。NAIF Type2／SPKR02／SPKE02与ERFA dtdb原件支持当前格式、单位和TT用法，三次光时及P03／2000B为明确模型政策，未据不同模型判bug。没有新数值、API或参考坐标调用；54点source-record端点／连接提案只作准备，未执行。原14472根、历史421、Canping120年以及PMO22和其他物理失败不改判。

完整独立原失败、来源版本、未决及所有门槛继续保持。累计25尚未严格超过50，pytest、collection、CI、格式、类型、build、合同／清单checker仍0；声明manifest另列，不作checker。没有依赖、安装、reset、提交、推送、部署或许可证操作。仓库仅自然修改既有两个生产所有者及相关回归／说明，无关dirty改动保留，不能说整个Git工作树全干净。目标继续active，不是暂停或完成。


R28唯一声明manifest为9,275,308字节，SHA256 `45edfac92b41361b657b98b48c7aca8b691c74ae506f1226de92c8d19a576c3e`；中央SHA256 `ebc2dba3973b71eaa2269011ccc4fc2213f6748ad823b1fbed8ee961438d4a98`。93完整目录／输入／66方法对R27逐值相同，manifest不含outputSchema；1511源码／数据在导出窗零漂移，1486生产源map为`9f0dc02c9b47f15cf69b49c41bed8cef7b1323d32e84b5bc6291ccdc3c04aff9`，相对R27仅timing与timing_snapshots改变。组／职责／定义分母不变，声明导出1次、checker0、累计25，目标继续。


<a id="source-record-and-support-owner-continuation"></a>
## 第二十九批：原始记录比较、支持定义补名与来源条件

本批累计独立改进保持25，新增0；生产Python／JSON1486路径与已封R28逐字相同。清单归层、source-policy／知识支持定义补名、有理参考、外部脚本修正及来源复读不冒充新算法修复。完整细算法语义总数、全部定义／选择器的独立执行和全仓专家级／SOTA仍未完成。

### 原始SPK与真实CALCEPH的固定比较

原始DE440 SPK与既有CALCEPH5.0.1二进制、原十个reader／header及旧recipe身份核定，原configure初失败及后续成功的历史回执均保留，未新编译／安装。原little-endian DAF目录直接读出六view与30原记录，不依赖产品恢复。54底层输入及精确域／record先冻结：两profile×三pair×三边界×三个fractional邻点，42域内12域外。

独立有理参考先完成并封存，再各一次CALCEPH和产品state54调用。产品当前全部54返回，精确source-view域12不符，内部join左邻点另六个actual record不符。CALCEPH324分量中208为最近目标，产品域内252中81为最近目标；只在严格静态同源／同record条件的144分量里，误差等64、native较小71、产品较小9。两总体分母不能直接比率，条件子集的native record只是源码公式预测，未实际instrument内部。完整全部差异、失败、excluded与raw保存，见[源记录诊断](precision-acceptance.md#de440-original-record-boundaries)。

这些底层IEEE邻点未证明普通公开时间请求可达；nearest目标更强于原有限执行政策，不倒改旧接受。view末端左record与完整SPK下一右record分别计算，native的recT和Tc是两种舍入路径，不简化成单一rounded epoch，也不把合法record政策差当错误。当前没有source补丁、epsilon、snap、兼容模式或容差调整，0新root／event窗口；原14472／14905、421／120年、PMO22及其他失败原样保持。

最初DAF原文提取的uv-Python TLS证书链失败、正常TLS curl修正均保留；首稿未生成54输入或求坐标。两个未执行observer的finite/messages资格缺项另版修正，旧107资产及先封参考不改／不重跑；两个coordinate arm及首次saved comparator各一次，统计只读已保存结果。该观察器元数据错误不计生产根因。全1486源及107＋9资产各观察窗稳定。

### 实际源码职责与影响优先级

DE440原12null组／89职责按真实输入、数值、来源与交付分为26组：P0 15组62职责，P3 11组27职责。所有原职责与来源／消费者／验收逐字保留，不把R28已完整读过的12函数或19AST节点再计首次覆盖。

完整读physical_source_observation的15AST定义及两绑定，登记31组53职责；模型／returned flags／实际origin／窗口／sticky拒绝是P0，散列／计数／回执和载体是P3。原ephemeris_call五条编排职责保持，source-policy活跃范围、native event内部未证、worker未扁平计数、JPL当前owner只观察slot0、旧公开SHA字段缺失均限定，未为假设竞态或恶意worker增加防御。

知识store与service的26定义／四绑定登记38组82职责，均为P3支持。root完整独立读两owner并逐项核AST／职责；原四个binding首列漏模块前缀另保存stage2，仅改四label，原34行／82职责／来源／消费者／验收保持。physical提案由独立代理复核，knowledge提案由root独立复核；补名41个既有定义，不是新增41函数、算法或专业通过。

<a id="knowledge-data-definition-census"></a>
### 数据内定义也单独列分母

基础四域206个命名键＋BaZi三个supplement七项，共213；其中201静态卡、12将模板。六壬另有144将支注记、两个别名、未被此store读取的12个辅助shen_info；house1728只参数组合空间。astro labels40、qimen blocks600、tips791只作结构定位，不按句、空行或组合凑算法。

68个curation均属BaZi，62条有source_refs、六条空；86次ref对应17个元数据对象，不等于17本已核原典或独立专家。13条未显式给review_status而走既有保守默认，25条基础BaZi明确legacy_unreviewed。foundations组件真实version2与ID后缀v1、上游2026-04-05包时间和后来词条curation日期分开，不据历史description旧85造bug。

BaZi leaf实际deepcopy并覆盖逐条curation来源，service全域目录另组合河洛／参评／人类图，PartialOutput extra=allow；不能从基础index旧source或类型未显式列字段推断来源丢失。该census只证明原始键与元数据结构，所有正文语义、来源正确性、影印、专业独立接受及现实效度仍待逐条完成。

### 有效力量的来源条件仍须裁定

只读四种直接相关资料与旧NLC页，形成18条条件／反条件义务并映射22定义；19旧完整、两本轮选定完整、一_evaluate旧尾段局部不升级整owner。资料区分名义生扶、有效承接与寒暖，却无可直接执行的通用剂量；徐注与正文的阴长生／张参政释例分歧保留，不能拼接梁氏三用神与当前NLC profile。旧367记录／321输入／17差异／两约束、HJ06等既有反例不重跑、不调阈或删覆盖。

当前中央4844组／13456职责／5326文件符号，707实现文件；7358定义中4631具名、2727未具名／615文件。P0／P1／P2／P3／null为545／654／441／1276／1928，binding696已名／2012待审，结构语句696已名／2063待审，队列重叠。root从R28前像独立重建全部4844行，原全部表和旧接受文字保留；细算法数仍null。

累计25未严格超过50，pytest、collection、CI、格式、类型、项目build、合同／清单checker均0；没有新的项目测试执行或回归编写。声明manifest另计，不作checker。无依赖、安装、reset、提交、推送、部署或许可证动作；无关dirty工作保留，Git并非全干净。所有旧失败、原典异本、连续／物理／预测及全项SOTA缺口继续保持。R30源坐标／求值候选和六个空来源卡的精确出处正准备，均未执行新pilot／改生产，目标继续active。


R29唯一声明manifest为9,388,855字节，SHA256 `89e42edbeb048349db33d1a440563387fae5afe3c0bcb72dd4e214b81098406e`；中央SHA256 `ccf57c98f4cc0203b7025ecc8b8624b83ddd3b3b98cd3507469b3c56f21e100b`。93完整目录／输入／66方法与R28逐值不变，1511源码／数据也完全相同，导出窗零漂移；1486生产源map仍`9f0dc02c9b47f15cf69b49c41bed8cef7b1323d32e84b5bc6291ccdc3c04aff9`。声明导出1次／checker0。所有54诊断失败保持，未作生产修复或完整算法通过；累计25，目标继续。

<a id="de440-source-kernel-and-citations"></a>
## 第三十批：原始源点、插值内核与六卡窄来源

**完整目标继续进行，累计独立改进仍25。** 本轮实际修改两个生产所有者：DE440 state的源点／求值，和BaZi六张知识卡的数据；没有把54输入、378内部点、六卡、来源映射或接口字段拆成新根因，也没有达到十个新独立问题一批的要求。全仓语义算法总数、逐工具／定义／分支的独立专业接受与现实预测仍未完成。

原R29 source字节不变的BEFORE直接复用，没有重跑参考／原生／产品旧阶段。先以Fraction保留实际两部TDB，精确选record/offset、最后投影x；固定54的12域误接纳和6记录失配消除，42域内全部选到独立原SPK字词。252数值nearest81保持，11改善与11退化分列，说明坐标正确不意味着完整求值更准。

实际126次现有Clenshaw内核pilot加378个事先固定内部点，在独立原记录有理参考先封后完成；同coeff/x direct控制和所有两种完整速度链均保留，不按case挑最好。内部点位置nearest148→351、统一速度153→267（各／378），仍有17个位置与45个速度的配对绝对误差退化。统一采用现有内核及单次单位缩放，删重复循环，保15profile段、公开Schema、全部边界和旧两个caller。最终54生产观察nearest81→194／252；原24同目标子集相对CALCEPH为104等误差／25产品较小／15原生较小，**仍有不劣于权威条件的失败**。源字精度、物理精度与全域SOTA不混称，详细分母、原链退化及source-point投影限制见[精度记录](precision-acceptance.md#de440-shared-kernel-continuation)。

六卡仅更新tip0与curation，其他12条程序计数／解释边界、所有其他卡、键、实现和契约保持。所选《素问·金匮真言论》四部丛刊扫描54–57固定修订逐张目读，支持木肝／火心／土脾／金肺／水肾；王冰注与林亿等校正不混成单一原作者，影印发行年未核。木胆／土胃另用《灵枢·本输》固定数字转录640546，正文明确跨段整理，原叶仍待目读，不冒单句引文。source_refs仅归tip0，软件依据与编辑边界各归本身；不认证旧Xingque的历史摘录来源、全书／专家、医学或现实预测。

root按R29同一identity字段重建：四个BaZi文件仍68个curation，非空refs62→68、source-ref occurrences86→97，同口径distinct identity17→22；不是书本数、算法数或专业通过数。长citation已压缩为人可读书／篇／页，固定URL、hash、版本及支持范围留在结构化source_refs，没有为凑完整来源将软件阈值归给古籍。

当前官方参考另经只读复核：NAIF已有DE442，官方说明主旨为天王星质心及新观测更新，范围约1550–2650，尚未作FateBridge同目标误差比较；更新不等于全目标更准。SOFA仍2023-10-11 Release19，CALCEPH稳定5.0.1与既有独立库一致。现行modern赤道已用2006/2000A，2000B只属相应太阳支路，fallback另有长周期／Simon77政策；不笼统宣称全项目只2000B或把版本号当修复。没有下载新kernel、装库、升级、构建或替换默认源。

回归只静态准备：54原输入以实际读取record字节作观察，不镜像record选择算法；原fsum测试保完整精确项和与原输入，只撤去陈旧产品whole-snapshot运算顺序冻结，旧raw及独立门槛不覆盖。新小参考单文件在既有白名单区登记，CI选择不改。项目pytest、collection、CI、format、type、build及合同／清单checker仍0；仅边界／参考／实际协议观察和声明导出分别记账。

中央仍4844组／13456职责、5326文件符号映射、707实现文件；7358定义、4631具名／2727未名，P0/P1/P2/P3/null为545/654/441/1276/1928。只同步26条DE440旧行的实际职责、当前AST锚点与局部验收，不以行数或元数据宣称细算法普查完成。旧现代42／56向量、62／336字段、7修正点，八字367记录／321输入／17差异／2约束，奇门9义务及太乙壬学异文全部保留。无关dirty改动保留；没有reset、提交、推送、部署或许可证操作，不能说整个Git工作树全干净。外置完整证据为`~/.codex/artifacts/fatebridge-audit-20261117-round30/`。

本轮实际协议共24次：coordinate-only阶段的一节气年／六知识卡各经REST、新stdioMCP、CLI，21次均成功；采用kernel后只补同一节气年三端3次，均成功。每阶段仅排顶层run_metadata时，完整business三端0差异；1486生产路径与四个所选native资产在各窗0漂移，实际所选MCP完整定义／输入／输出Schema跨阶段不变。六卡没有为数值变更重复调用，代表输入不冒全参数验收。

两版本节气完整业务并非不变：2000年立冬／小雪的精确civil_point分子及TT低部／根括区间变化，在原两个数组中合计16leaf差，三端相同；显示日期、snapshot/export及其他字段无额外差异。原值和float hex外置保存，不将它们凑16项优化或物理精度信用。原public source hash缺失／redaction资格按实际回执保留，不能用内部hash核验冒称public hash已经齐全；Pydantic运行警告原文保留。真实模型、常驻聊天进程、安装包与部署另验。

R30最终唯一声明manifest为9,395,437字节，SHA256 `1d1742a4e6d58a8fa8dc65bb89c3828a33417f398f4f75ab7797b40222d57188`；中央SHA256 `e4e3da982f6cb429393e79cbbd57df6760e9e40e836dedd2e4f4a645c2993242`。导出exit0／stderr0，未调用checker；93完整目录／输入及66方法与R29逐值一致，manifest不含outputSchema，不能借此宣称全输出不变。1511源码／数据路径与live完全一致，较R29只两个意图内源变更；1486生产canonical map为`999c51c8014a2c8d7ba86721ff0337cc393d6547c9f6496e5c4455d0e832b183`。独立静态peer重建全部4844行与26个实际AST锚点，余4818行字节保持；2727定义、2012绑定及2063结构语句仍在队列，不能把声明导出当语义普查或算法通过。

<a id="compensated-polynomial-round31"></a>
## 第三十一批：递推残差与完整天体量的最终投影

**累计独立根因／能力改进25→26，完整目标继续active。** 在固定同binary64系数／同float-x输入上隔离出源多项式递推丢弃运算残差这一项新根因；补偿和sum／product残差共同保留，没有单独multiply-only消融，不声称仅乘法为唯一因果。三个来源所有者改用纯`astro/chebyshev.py`，full-c0及两阶解析导数共用typed carrier，Fraction局部坐标、单位及Earth／Moon组合到完整天体量后才投影。后三项属已有早投影家族续修，不另计根因，11新增AST节点、字段与测试数也不作独立改进数。

实际读到ORTHOPOLY作者v1、大学论文postprint及相关EFT／Cheb1正文，未运行或复制作者程序，软件与论文许可分列；2011完整PDF仍403。独立整数／有理参考先封，再观察统一候选。342条实际源多项式×13固定x的4446输入，原raw nonnearest2929／13338、完整源组单位nonnearest4094／13338，最终生产v2均0，全部26676字段与原型相同，无精确绝对误差退化；其中四个raw dx平手只修最近偶编码，不称严格误差改善。原始DE441数据record与完整缓存逐字相同，packaged给定字单独参考，不把量化词当原字。[完整分母及来源](precision-acceptance.md#compensated-source-polynomial)与外置R31全部原始阶段保持。

原R29的54输入及精确源点目标直接复用，没有重跑原生／参考／旧产品阶段。最终54实际state返回42／预期范围错误12，域／record／Fraction x失配0；位置126和完整速度126均为原有理目标RNE，R30的194／252升至252／252，58误差缩小／194相同。原24共同目标子集144分量相对既有CALCEPH为106等误差／38产品较小／0原生较小；原30排除和native实际record未instrument继续明确。这通过该同源固定算术比较，不能替代完整物理或全域SOTA。

实际Sun／Mercury／Earth／Moon的direct与packaged共8消费者另有先封双层精确参考。direct原字24→33→36／36、packaged给定字27→30→36／36；v1原9残差、4个相对BEFORE的误差退化保留。原摘要混合direct33与packaged偶合1成34、其后一度误述8残差，原stdout及勘误均保存，正确分母为direct3＋given6＝9。v2的packaged对原字仍0／36，相对v1有6误差更大／30相同，偶合1→0；源表示差没有修复，不据given-word通过宣称物理进步。一般Fraction的两浮点近似与EFT无中间溢出／下溢前提保持，没有全输入正确舍入或全SOTA证明。

同一合法节气年在v1、v2各作一次REST／fresh stdioMCP／CLI，共6公开调用，复用R30已有3baseline；同版及各跨版完整业务0差异，仅排除run_metadata。实际所选输入／输出Schema、完整MCP定义及outputSchema0差异；原公开warning／INFO与hash redaction保持。连同原8 BEFORE与两轮8 AFTER，该lane共30次新操作，不计30独立场景。最终生产1487个Python／JSON路径canonical SHA256为`9887bd4931c55221d4975209eb129b5a961beb175cccc326c108614b748db275`；相对R30只有3个旧源变更与新纯模块，知识数据不变。

太乙四个实际所有者1347行、28定义（含3nested）和17bindings按完整分支细读：原4组5义务迁移为64组99义务，P1 29组54义务、P3 35组45义务，补名23个旧定义与17绑定，不称新增算法或传统通过。独立peer纠正实际委托owner、缺core时的unknown条件及center5只适用于将而非有效Taiyi core三处表述；原11／3／10／424／33及1／30失败和异本保留。新数学8组37职责迁移25组64职责，37旧义务唯一归属、全部原来源／consumer／验收留存，52其他行只更新AST锚点。来源前缀去重曾截断四条带括号的Wikisource目标，导出前恢复完整原字符串；坏阶段及更正另存。

当前中央4921组／13577职责、5378文件符号映射／708实现文件，P0／P1／P2／P3／null为560／683／441／1314／1923。1160 Python文件中7368定义＝5387函数方法＋1981类，4664具名／2704待名（611文件）；bindings715具名／1995待审，结构语句715／2046，两队列重叠。完整语义算法总数仍null；工具／定义／选择器的逐项独立专业接受仍未完成，清单细分不授算法正确性。

八字湿己／无根火来源只读与两个字面四柱观察保持不改生产、不增根因。任注1947影印实际读72／printed22及两个原例，区分丁印化煞／解冻、阴火不能生湿土与丙火寅根，不能压成一条通用有效力量权重。两个实际source-compare调用及18内部政策评估均明确engineering未校准、classical未裁定；生土／调候轴未暴露不当False。原367记录／321输入／17差异／2约束保持，C06页源已有旧R237—239记录，不称新发现。

只静态编写及peer新的完整4446／26676便携回归和四体双层J2000回归；CI仅选不依赖本地`.eph`的单个kernel节点，原测试义务／fixture保留，旧API自然迁移。累计26未严格超过50，项目pytest、collection、CI、格式、类型、build、合同／清单checker继续0；声明导出单独记录。原现代42／56向量、62／336字段、7／56点、奇门9义务、太乙六壬异文、事件14472／14905／421／120年／PMO22、真实模型／安装／部署及物理／预测缺口均不改判。保留无关dirty工作，无依赖、安装、reset、提交、推送、部署或许可证动作，不能称Git全干净。完整证据目录为`~/.codex/artifacts/fatebridge-audit-20261117-round31/`。

最终独立清单peer另收窄3行5格：plus／minus不借4446队列宣称通过，分别关联实际Moon及Earth／Moon组合结果；Fraction分支另由原54及8消费者有限约束，de440不误列为地月加减直接调用者。只补验收关联与consumer范围，旧37＋5职责、全部来源及分母不变。中央最终SHA256 `4aab47339900cf79ad2212f058e852085fc6f951511bb5fcc23fe60098622638`。唯一声明manifest为9,519,209字节／SHA256 `4f97f9e7398c07c831289189a1d2b339679672683e8a8d4ed42cd9ae8ec12d98`，exit0／stderr0，93条完整目录／输入／方法记录与R30相同；1512源码／数据路径与导出前后live身份一致。manifest没有outputSchema，所选实际输出的比较另由协议观察支持。root首个saved簿记脚本猜错source-files键、在比较前失败，修正后只读原manifest重建成功，失败另存；没有重跑导出、参考或产品。R30的report／final-status／release-index三封印逐字未变。

<a id="qimen-calendar-round32"></a>
## 第三十二批：奇门私有日序、源表示预算与基础规则清点

累计独立根因／能力改进仍26，新增0，目标继续active。并行完整审读八字基础规则／候选／喜忌闭包20函数＋7类及6绑定、星历表示链26定义，以及奇门定局与公开时钟／来源闭包。读集不按定义数计优化；没有为凑数改原典异法、工程权重或已如实保留的unknown。

奇门确认四个有效公开时刻被内部日期载体拒绝：原固定六例中年1／9999的7月15日12UTC两例失败，99／999及2026年冬／夏四控制成功；另封年1元旦00UTC和9999年末23UTC也失败。year0大雪键及year10000续排／目标formatter均到达真实源后才抛错。候选在原调度所有者用整数Gregorian ordinal及显式日期索引格式，退役两个私有helper；新小来源叶仅查前大雪／当年芒种及大雪，计算与回执复用同一选取规则、各自接受源验证。每个邻年保原自身model／原guard授权，cache仍在真实source校验之后。原十五日推进、三处>=9、四个top-level调度For、局表和默认AST保持，原九项典籍未决未改。

BEFORE8与AFTER8逐输入各一次；四拒绝恢复，四原成功完整JSON逐类型／float.hex差异0。另两个显式chaibu after-only只核当前节气来源与整数事实，不造旧版比较，合计18领域调用。先封HKO三干支锚＋独立Gregorian日序／甲己符头／三元条件的10个AFTER有限目标均符合；没有小时干独立oracle、完整古盘或古代天文接受。三个实际anchor的UTC日序／微秒、provider／model及完整details与before操作数相同。端点实际用swieph，2026用DE440；本机year0原全年可解、低年strftime也补四位，均未当新实测故障。[全部因果与原分母](calendar-boundary-audit.md#qimen-private-calendar-guards)及外置R32原始错误保存。

两个原端点请求另各一次完成REST／freshstdioMCP／CLI，共6公开调用，状态与完整领域门槛均过、每例完整业务仅去顶层run_metadata后三端0差异。实际request Schema与R31声明0差异；输出模型及完整MCP定义只确认同窗口稳定，不虚构缺失的历史outputSchema。1488生产Python／JSON及已冻资产0漂移；37配置se1另对旧封印同值，35项未纳本协议lane即时前像，配置集合和更大窗口端点身份不是原生原子readset。

打包星历完整72对原字／给定字的936保存点、2808源组p／v／a及816实际系数按既定量化路径核对。量化整数、解码给定字、q／2与解析传播界均无违例，84个非零源词量化为0仍保；原字nearest为位置31／936、速度0／936、加速度0／936，36组合仍0／36原字相同。由明示量化产生的表示差不自动算现行预算bug。固定单part02无损pilot压缩19739029→45057126B，raw数组53477376B保持；外置单次加载峰RSS329728000→380289024B。成本和临时缓冲保留，不外推14块或实际产品峰值，不替换默认／data；[详细限域](precision-acceptance.md#de441-representation-budget)。无新产品、原生或多项式参考求值。

八字三owner1926行、27定义／6绑定只读，五页原NLC影印支持有限月令／格局条件。力量、身印相对量、相神及位置救应仍未一般化裁定；MAO本气印与有限selected杀、旧17差异／2约束及来源未知保持。未在已读出生／专题／双人消费者发现unknown被冒作source-known／False，分数仍工程未校准。旧9组24职责细分39组72职责（P1 14／P2 8／P3 17），补14个原待名定义；类型与helpers不套NLC五页认证。SOURCE展开方向及两个helper逐父组历史限定在集成层纠正，原提案保留。

奇门原23组94职责迁25组98职责，94旧义务唯一迁移，16行仅更新AST锚点；N08明确各自调用同一选取函数而非共享同tuple实例，N12明确已解计算钟面同时包括民用／太阳。其他原典／规则职责及未归层行不冒称新验收。当前中央4953组／13629职责、5397文件符号／709实现文件；P0／P1／P2／P3／null为562／696／449／1332／1914。1161 Python文件含7367定义＝5386函数方法＋1981类，4677具名／2690待名（608文件）；bindings721／1989、结构语句721／2040，队列重叠。完整语义算法数仍null。

旧cache填充、来源拒绝探针及年末provider测试只自然迁接：保原断言义务，移除无关下一整年是实际计算依赖的陈旧假设。新增端点回归只复制先封日期目标，未执行。项目pytest、collection、CI、格式／类型、build及合同／清单checker继续0，未严格超过50不放行。原现代42向量／62字段／7点、八字367／321／17／2、太乙六壬异文、事件14472／14905／421／120年／PMO22、完整物理／预测及SOTA未决保持；无依赖、安装、提交、推送、部署或许可证动作，无关dirty工作保留。证据目录为`~/.codex/artifacts/fatebridge-audit-20261117-round32/`。

最终独立peer重建4953全表及全部AST／绑定／语句分母，只32旧行118职责迁为64新行170职责、3头部与一R32段，其他全文字节保持；零未解析行、缺symbol、错anchor或未闭source链接。中央SHA256 `d8b342b03eefc4dea06c057232dc1d993d718b518b4e2f1e5f35252f2a40abe3`。唯一声明导出exit0／stderr0，manifest9554866字节／SHA256 `b27d77430de912c8e5a1eda080e01618052b372fa5247ab9a7febe4d62edd9b1`；完整93目录／input／method记录与R31相同，1513源／数据路径与导出前后live身份一致，仍不含outputSchema。生产1488 Python／JSON的canonical SHA256为`a83f9cda1245f15cf12104625c5a65b633379468197ba65621b0d16ee17734d6`，恰两旧Qimen源变更及一个source叶新增；R31数学源及知识数据未变，R31三根封印逐字保持。新端点回归的四日期目标不变，root静态复核撤去四条无关品牌／当前未决状态冻结，保日期与结构／民用钟义务；未运行测试。集成准备误猜7个资格格而实际8个的外置断言失败保存，只改簿记、不算产品失败或新优化。

<a id="nominal-clock-round33"></a>
## 第三十三批：共享名义钟面与真实民用时刻分离

累计独立根因仍26，新增0；全目标继续active。原四固定请求各一次复现两个太阳标签跨年界的`internal_error/500`与两个库级UTC转换溢出，专业原C源先执行并封存。另封现代四控制，独立Gregorian／实际timedelta量化及HKO日干支／既有小时表／原文符头元的目标只用source／BEFORE操作数生成，未取AFTER。数字分析和本地字符串入口现共用一个领域seed owner，以一个无zone的日序／微秒标签供日时与农历日期，实际带区民用输入供交节／源年；Person复用已有校正。完整说明、源身份、各自分母和限制见[共享太阳标签与UTC端点](calendar-boundary-audit.md#nominal-clock-labels-round33)。

AFTER仍原4＋独立现代4各一次。原2奇门均完整九宫，并符合先封标签／日时／符头元；两均时差均有限且hour／JD hex与原C2／2相同，严格EOT bit只有1／2相同，B1差异明确保留，未调整源／输入／目标／门槛，也未将其武断计成新根因。现代4完整业务按类型与float.hex全量0差，不排字段。另9受影响工具12固定场景×REST／新stdioMCP／独立CLI共36次全部成功，同场景完整business只排顶层run_metadata后三端0差；12保存体严格投影与partial model接受不重算。原2Qimen及现代Ren/Jinkou四请求沿用，其他8仅AFTER控制，不冒称独立精度或旧版比较。

领域观察v1为1490生产Python／JSON，canonical `9d40117704e42023afd49e238e62f80c3b767f3ee5cbde29b330f8ef2d030b4f`；8领域的126资产及36协议的133资产均含全部37配置se1即时前后同值。实际input Schema9份与R32声明相同，actual output Schema／完整MCP定义只证当前窗稳定，历史outputSchema未提供。原生配置集合仍非仪器化原子读集，SDK／原C编译及物理资格分开。最后peer仅补一处TypedDict返回注解传播，函数计算体／参数／decorator不改；最终v2与v1只此type-only差异，观察字节身份不偷换，纯类型变更不重跑业务。

旧测试、审计脚本与validation的private owner／seed／label调用按实际赋值链迁接，未删除旧测试函数或规则断言。静态首版三处误迁经peer纠正，旧错误前像保留，AST与assert数量不冒作语义正确证明。新增八固定source条件回归与小fixture保存独立目标，没有采用AFTER或冻结当前未决状态。累计26未严格超过50，pytest、collection、CI、格式／类型、build、合同／清单checker继续0。旧现代42向量／62字段／7点、八字367／321／17／2、奇门9义务、太乙六壬异文、事件14472／14905／421／120年／PMO22及物理／预测／SOTA缺口不改判；无依赖、安装、reset、提交、推送、部署或许可证动作，无关dirty工作保留。完整证据在外置`fatebridge-audit-20261117-round33/`。

最终中央4982组／13667职责、5425文件符号映射／714实现文件；P0／P1／P2／P3／null为579／700／449／1346／1908。1163 Python文件含7379定义＝5396函数方法＋1983类，4702具名／2677待名（606文件）；bindings724／1987、结构语句724／2038。旧13629职责按索引唯一迁移，4953原consumer／source格逐字保留，acceptance保原前缀、仅EOT追加本轮严格失败。26新行／38新职责只登记实际新载体、共享装配与已读适配，不提高root数；consumer误泛化与路径误选的静态阶段保原像并修正。独立peer完整重建4982表行、235变化段、全部5425符号与锚点及AST分母，无缺项／错锚；不是全仓语义或独立精度通过，语义算法总数继续null。

中央最终SHA256 `b1aa0673088c24d28fff4058703815ac8a1690999bca9ecd9dcc676def4f9ce9`。本轮唯一声明manifest导出exit0／stderr0，9591783字节，SHA256 `377e9fe5bb6eef143fabb4b61764f5de1b228d51ad4020222b873d049d301664`；没有运行checker。完整93目录／input／method记录与R32相同，1515源／数据记录和最终1490生产路径均与导出前后live身份一致；最终v2 canonical为`85e8ee64f03c12cfb80c49412eead19e04ddcc55eee1343a02112827cbcf541c`，只36旧源变化与2新叶，无删除。manifest仍不含outputSchema，不能借93记录相同宣称全部输出Schema或完整工具参数已验。R32三根封印逐字不变，所有旧失败和范围保留。

<a id="source-eligibility-domain-round34"></a>
## 来源预置适用域与完整日期／几何路径（R34）

**累计独立改进26→27，全目标仍active。** 新增仅一项producer／consumer来源策略适用域错配：合法远年Swiss flags2交节，生产者未要求现代pin，而验证者却无条件执行同TT Moshier预飞，导致9999年底金口诀被另一个无覆盖算法拒绝。原UTC／TT载体、主点保留及延迟投影不能修复这个额外前置条件，因此与既有26项根因分开；河洛／参评整数历和几何两项仍为既有家族传播，不按8文件、14定义、72字段、样本或协议加数；14个实际变动定义不冒称14个独立根因。

共享纯条件以实际TT bracket中点落在[1799-01-01,2202-01-01)决定source-pin，producer、consumer与prime边界共用；这个区间是FateBridge登记策略，不是Moshier完整可用域或物理准确域。完整现代回执必须包含并精确核对native_source_context，不能删字段降级；稀疏投影仍只验证共存字段。域外合法Swiss继续同flags重观原两端，保留model／library、窄bracket、交点包裹、TT／civil与环境一致性，不伪造现代pin，不换星历，也不catch超域错误充作成功。

独立作者Swiss2.10.03 C（tag commit175e1fcb）按原R02冻结TT恰5次calc：冬至和次年小寒的4端点均flags2、有限、同对文件上下文不变且low<0<=high；第5个原Moshier中点仍ERR，原625000.5..2818000.5域错误保留。37se1及原contract dylib前后无漂移。现代另恰1个冬至求根、1个完整require与1个仅删context的require，完整来源被接受，删context在首calc前拒绝；实际SDK calc397+28、M03为0，全部1490源码／47资产即时身份不变。共同作者谱系与SDK／C编译、物理精度和原逐位失败分别限定，未将此称为独立轨道准确性认证。

[河洛／参评固定六输入](calendar-boundary-audit.md#retained-domain-carriers-round34)的原2成功／4失败在AFTER均完整返回；两旧成功raw字节相同，无字段排除。C01保留完整12运、120行与121实际边界；BEFORE给定小寒4civil天→1年的条件整数目标相符，全部新立春仅作实际准入／区间操作数，不冒独立天文gold。连续配运端点和上端默认120年序未观察，古代UTC、源物理及传统原典资格未由载体修复授予。

[几何固定九输入](precision-acceptance.md#precision-equal-source-round34)的旋转半开错误1→0，六equal的原72给定ASC源式字段36差→0；六ASC与当前raw输入均逐位不变。原猜想的shift分支未进入，未执行中间补丁、因果更正和完整变化保留。原474／1角秒源目标与现代SDK／C的42／62／7失败不改判；新公式线不替代旧物理线。

9场景×REST ASGI／新stdio MCP／独立CLI共27次，各200／无error／0且领域完整。同场景完整业务只排顶层run_metadata后0差，R33现代Heluo／Canping两个历史完整publicbody也各0差；历史runtimev1与初始R34v2的纯注解区别仍单列。公开Vehlow确实进入80／120位精度路径，保实际UT1／TT、ASC与8–11宫头变化；这一个AFTER公开场景不冒作旧物理gold。5工具input与当前output Schema、完整MCP定义在窗口0差，历史outputSchema不作全目录声明。1490生产map canonical为`f3b8962b35d49d8023327874df2048a6f9340f2d7d3cf0aad7861779d060f54f`，协议50资产含37se1即时前后同值，不是原生原子读集。

太乙另读15个真实计算定义，并直接查看《古今图书集成》艺术典卷687／册477图76，支持现有直符十二位、三年一宫、三十六年循环；原720格中33个中元原表差异、9例24字段和版本分歧全部保留，未无益重跑720或修改公式／原表凑分。传统力量、奇门九义务、太乙／壬学异文、R33 EOT B1、全时域／全部定义／物理及现实预测与SOTA继续未通过。

本轮改8生产owner，13既有定义与1新增条件函数，另1个区间参数绑定；无共享契约字段、依赖或源许可扩大。只写最小源条件回归，不执行pytest、collection、CI、格式／类型、build、合同／清单checker；累计27未严格超过50。CLI负offset改用--flag=value是执行前编码修正，草案与原值保留，不当产品根因。无安装、reset、提交、推送、部署或许可证动作，原无关dirty工作保留，不能说整个Git树干净。完整原件在外置`fatebridge-audit-20261118-round34/`，最终清单与声明身份另列。

最终清单为4984源码组／13669职责，P0／P1／P2／P3／null＝586／700／451／1347／1900；5427文件符号映射／714实现文件。生产1163 Python中7380定义＝5397函数方法＋1983类，4703具名／2677待名（606文件）；binding725具名／1987待审，statement725／2038。全部4982旧行13667职责唯一迁移，旧consumer／source／acceptance三列逐字保留；15语义／priority与110锚点变化、44选中旧行未变，2新行仅真实predicate及区间绑定。独立全表／AST peer缺项／错锚／重建差异均0，不授算法通过，语义算法总数仍null。

中央最终4528084字节，SHA256 `e46056a9071d5856426cacd0726f3f7266aa1e59b8822ca814b9d53502cc95c1`。R34唯一声明manifest导出exit0／stderr0，9596566字节，SHA256 `b0d5de930ec8706cd4bfe3d02c7abfb4f4339acad0401ee2e9b204bbb2ddf26f`；93完整public／input／method记录与R33相同，66 method ID、1515源／数据与live及导出前后一致。manifest不含outputSchema；declaration export1、project checker0，不能用声明同值扩大运行范围。最终1490生产源与全部AFTER同f3b8962b，无post-observation生产修改；独立根因27、全目标继续active。


<a id="lossless-source-month-uses-round35"></a>
## 原字星历、杂气并用与连续配运（R35）

本轮从R34的1490路径／f3b8962b零漂移开始。三个所有者并行处理实际失败：连续配运的合法下端UTC载体、DE441系数表示损失、杂气月用被单锚过滤。只后两项各新增一个独立根因，累计27→29；字段、路径、源字、定义、清单与Schema修正不拆计。项目测试、collection、CI、格式／类型、build和合同／清单checker仍未运行，因29未严格超过50。

DE441先封原17历元×11天体的187状态／1683个p/v/a字段及原误差线，再分别运行精确原字多项式、CALCEPH5.0.1与当前v3。原v3和CALCEPH都通过1683项绝对门；最近舍入分别46／1190项。单一正式构建器随后按原8144字节源记录提取选定binary64字，不做数值反序列化／重编码、拟合或量化；14块无损压缩资源实测627633182字节，原v3为274774415字节。独立程序逐原始连续slice核对114129记录、93129264字及745034112字节全部相同，保原时间格、AU／EMRAT和来源限定。原准备文件不是整份未修改的NASA远程文件，完整远程SHA未验证的状态不变。

当前运行时只用lossless_de441_planetary_source_v4，原v3资源完整归档后移出src，无双后端或按工具开关。原187状态AFTER仍用同两份冻结参考：1683／1683最近舍入且原绝对门全过；相较v3为1637更近／46相同／0更差，相较CALCEPH为493更近／1190相同／0更差。两实际公开消费者jieqi_year和nongli_time各走REST、fresh stdio MCP、CLI，六调用完整且同例全业务0差（只排顶层run_metadata），父REST的实际Moshier4旗标与随后加载的v4／array d分别记录，不冒称Moshier就是JPL；child native未追踪。公开哈希被既有策略移除，记为missing-public-field，不冒作wire digest通过。详细有限源算术范围见[原字系数与原作者对照](precision-acceptance.md#lossless-de441-round35)。

杂气月用按所选沈孝瞻《秘本子平真诠》NLC影印PDF41–43读出“兼透兼用、透会并用”及甲辰申子会水印的来源资格。新共享month_use所有者保全部透干／完整三合见证、实际柱位、作者／版本／页与权限；同次集合由候选、星位路由、必要条件和真实读出共同消费。会支只到十神类时不强定正偏或化干，旧单锚仅作明示历史参考，未调强弱／喜忌权重。固定SDK五例和两个独立定位公历请求的BEFORE／AFTER均保；AFTER两例各三协议完整且同例业务0差。该限定遗漏已修复，不升级成格、全合化、相对力量、原321／367比较、17差异／两约束或预测有效性。

连续配运只修改共享TimingAnalysis边界函数，复用既有整数历与时区所有者，不复制起运公式或缩短120年／121界。C01原500在三端完整返回，给定源条件参考及同例三端相同；原控制的严格全业务门仍61通过／2失败。1138差全部为内部BEFORE到公开REST AFTER的既有完整性字段移除，共同字段0差；对保存BEFORE应用实际未变公开策略的派生比较0差，不能改称真实public BEFORE或重新授原门通过。见[连续配运的下端载体](calendar-boundary-audit.md#continuous-carrier-round35)。

DE441状态与六协议观察窗为1493路径canonical SHA256 5dddf48013234f8a8eb32cb883b88e1b28413e40456fd4603d83d1abc2954a23；随后财富读出／类型修正仅改变bazi_root_context.py与output_bazi.py，终窗canonical为0a4e4659130dae8896586925f5b7f3cc63ec1813fe4e3574245293349dd7ea50。财富同P01的实际REST BEFORE1为200，真实进入analysis.wealth→wealth_rule_context，纠正早前只搜core/services却推广为全src不可达的推论。AFTER三端完整且同例业务0差；各对BEFORE的4处差仅历史role、reference_scope及两处snapshot文本，数值、见证与checks不变。输入Schema0差，REST输出Schema5差为opaque到共享typed上下文，MCP实际outputSchema与REST相同；只声明新增两字段，不伪称全部旧opaque事实已类型化。该追加是同根因读出／契约遗漏，不增加root或重跑已封source187。完整原件、首次失败、未执行草案、成本和归档在外置fatebridge-audit-20261118-round35。原B1严格EOT、SDK／C的42／62／7、八字17／2、奇门九义务、太乙／壬学异文、未具名定义、物理／预测和全项SOTA未决继续保留。这里只关闭所述有限根因与观察层，不宣称全仓清查完成或整个Git树干净。


R35最终中央清单为5027源码组／13745职责，P0／P1／P2／P3／null＝591／711／451／1388／1886；5453文件／符号映射／717实现文件。1166 Python含7395定义＝5401函数方法＋1994类，4722具名／2673待名（605文件）；binding732／1987、statement732／2038，后两队列不相加。旧4984 parent中4983为单child、1个拆为2child，另42追加组76职责；13669旧职责逐项唯一迁移，旧consumer／source／acceptance三列逐字保留。17个Timing后续锚点在独立peer中按真实qualified owner修正，初任意AST行号校验只作机械定位；最终19个受影响Python owner的202行qualified归属均核符。earth_attitude旧11组仅完成5P0／6P3优先级分类，不增语义算法或根因。

中央4571398字节，SHA256 2f8d4adc0547988edcacbabaf640da8f9fd3c1d22eafb9ca8362c03ab507fb58。R35唯一声明导出exit0／stderr0，manifest9656583字节、SHA256 542542a5eeaa519f5febbeea7fec480737520711bafd1d69a14c789a7cf1a198。独立saved peer确认93完整public／input／method记录对R34逐值0差，66 method ID、1518源／数据记录与当前逐bytes／SHA相符；1493生产map成员和值均符，终值0a4e4659130dae8896586925f5b7f3cc63ec1813fe4e3574245293349dd7ea50。manifest不含outputSchema，不能把声明同值覆盖实际财富输出Schema5差；declaration export1、project checker0。语义算法总数仍null，全目标继续active。

<a id="modern-c04-eop-round40"></a>
## 现代C04时钟与同EOP地球姿态（R40）

R38的两项同次工作量优化后累计31，R39来源交付新增0；本轮只按两个根本差距计31→33：每日仿射C04模型不足以实现所选现代瞬时UT1；零EOP姿态没有把极移／CPO一致传给接收者与当地轴。新27定义、退役1定义、14绑定、谐波列、字段和样本均不拆计。两根因只获下述有限模型接受，不代表所有算法、消费者、物理或预测层完成。

现有 `iers_c04` 方法升级为 `iers20_c04_lagrange4_zonal62_subdaily2010_tt_ut1_v2`，没有新增生产兼容后端。唯一提供者在连续TT上对UT1−TAI去同源Z62、四点插值、还query Z62，再加入一次ocean／libration；反解固定外部给定UT1，直接解同一pair残差。独立printed-table区间参考先封8个TT及各自认证IEEE逆输入，正向和逆向用不同正确目标；最大两端误差分别2.7999e−14秒和9.1250e−14秒，原门均1e−11秒。含正向／逆向／zonal／pole／CPO的7类共56门全部符合；旧正逆16失败及约26.08微秒最大差完整保留，不放宽原门或改输入。

物理三轴只加一次有资格CPO，保model s／EO；同一W／GAST供SOFA接收者、geodetic ENU及共享有效站点。原版SOFA20231011库恰4原控制／19字段加36几何调用，共40次顶层调用，符合原门。固定2时刻、4站点、2射线的候选120分量全部过线；旧版有对应API的44分量4过／40失败，没有补造旧ENU接口。接收者对同一给定模型的最大差由13.4332米降至3.7660e−8米；这是模型一致性，不能当真实站点或EOP测量误差。名义速度不冒称完整SI／LOD／极移率／地壳形变速度，原Fortran七控制未运行。

两例公开输入是2024普通C04择日与原普通Swiss盘，两版各经真实REST／fresh stdio MCP／独立CLI，共12次且均完整成功。同版完整业务只排顶层run_metadata后三端0差；Swiss前后0差，C04每端53处时标回执／宫轴／姿态／快照变化全部保留。选中input、实际outputSchema及完整MCP定义的原差都保存，不拿业务同值冒称Schema未变。public及直接math运行的virtualenv启动文件未预冻结，原资格保留；public stderr中的既有Pydantic alias warning／INFO不抹去。几何观察另在运行前补齐实际启动与所用运行包身份，均只授各自selected端点范围；private worker内部及原生原子readset不由此获证。结构化脱敏与snapshot字符串保hash的既有不对称仍未关闭。

本轮实际生产源由R39 f9b64的1495 Python／JSON、1521非pyc文件变为27c365的1497／1524，21个源码或资源owner变化，没有观察后生产改写。中央清单5084组／13816职责，7429定义＝5412函数方法＋2017类，4760具名／2669待名；134既有组505职责的位置和后三历史列逐字保留，28组当前语义单列，旧23638日／70911线性控制不授现代全域。40新组54职责只补实际实现／支持定义，语义算法总数仍null，Sukuyo另一26组／46职责提案未整合。

旧10份C04 fixture不变，新便携目标仅来自独立reference，迁移掉强制现代实现等于旧linear／zero-EOP模型的断言，保旧失败、原0.02角秒线及历史数据。两条second60.5 synthetic旧输入和200微秒断言原样保留，其现代模型兼容性本轮未运行；新8点／4站点pytest只编写未导入或执行。唯一声明 `--manifest` 导出9747563字节，SHA256 `447c57f725a9116fa0c2e596d1f5515689091a32a16533bcbb147563543516da`，exit0／stderr0／已绑输入0漂，模式在checker前退出；它不含outputSchema，也不是测试、checker或生成调用合同。33未严格超过50，pytest／collection／CI／格式／类型／build／合同生成与检查均未运行。

native houses／azalt正逆／事件源的独立数值验收、早年CPO、所有未到达边界、完整观测／传统／预测与SOTA仍待完成。旧42／62／7、B1 strict1／2、R35 Timing61／63、传统异文和全仓未具名队列保留。完整首错、未执行草案、模型／原C／三端原体、环境限定和独立peer在外置 `fatebridge-audit-20261119-round40/`；当前细分来源与接受层见[精度验收](precision-acceptance.md#modern-c04-eop-round40)。未安装、提交、推送、部署或清掉原有无关dirty工作，全目标继续active。
