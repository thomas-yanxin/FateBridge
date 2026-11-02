# FateBridge 算法与能力覆盖矩阵

第六十五轮据文明书局本PDF154—156补入谦六爻标题与完整条件注文，两层各90／384、各294条待校；90表示已作目校记录，仍含未决字形，不表示全部读字确定。初、四爻有条件引明夷／小过，目标爻未印，不替代正式后天晋／颐；二、五爻諂／謟、彀字候选仍未决，初稿错误及撤回拟改保留。旧84条不变，原历法12项超差、五处同版月号冲突及完整验收false继续保留，见谦原页、条件与计算结果核对（本地数据：`validation/heluo-qian15-commentary-audit.md`）。

第六十四轮按实际太阳边界回执修正二数固定JPL引用，并为AA1996补齐有界派生立春及来源不足503。原96点与全部1800—2200年9624点分别量验，AA1996具名候选在原1秒线内，Native旧失败仍保留；不改默认源或取数算法。完整回归及范围见太阳模型来源与有界立春（本地数据：`validation/numerology-solar-providers-audit.md`）。

第六十三轮据文明书局本PDF151—153补入大有六爻完整标题与条件注文，两层各84／384、各300条待校。九三有条件引睽只列卦名，未指定目标爻或引其正文，不替代正式后天革上；八组初稿修订及独立模型读稿全部分歧保留，复读修正误字和增字，矜／衿仍未决；人工专家及全语料独立复核未完成。原历法12项超差、同版五处月号冲突及完整验收false不改变，见大有原页与计算结果核对（本地数据：`validation/heluo-dayou-commentary-audit.md`）。

河洛卦月新增同版卷首64条与后卷卦条63条的具名位置方案，保留晋、节、睽、震、井五处原文差异及無妄缺号。方法可改变实际月号匹配，未据吻合度改原书或授予完整得时，见月表来源位置核对（本地数据：`validation/heluo-month-source-profiles-audit.md`）。

[文档中心](README.md) · [核心概念](concepts.md) · [API 参考](api-reference.md)

一项工具是否适合当前产品或咨询任务，取决于实际计算范围、数据依赖和精度。下表按 MCP 集合逐项列出工具与实现状态，说明可以使用的能力、近似路径与未覆盖内容，便于在接入和解读前核对。

输入参数查 [API 参考](api-reference.md)，按用户问题选工具查[场景路由](scenario-routing.md)。

查找某项能力先看[总览](#1-总览13-个-family--92-个工具)和[工具清单](#2-逐-family-工具清单)；评估结果精度再看[依赖说明](#3-精度与依赖说明)与[快照覆盖](#4-快照协议覆盖)。八字和双人模型的版本分别见[八字判定](bazi-assessment.md)、[双人评分](compatibility-scoring.md)，风水规则见[家居风水](fengshui.md)。

状态分类：

- `Implemented`：仓库内已有实现，可通过中央目录声明的接口访问；不代表所有端均有同名入口，也不代表预测有效性已被验证
- `Approximate`：可用，但算法明确是离线近似、轻量近似或依赖回退路径
- `Placeholder`：合同或模式入口存在，但主输出层仍是占位兼容
- `Excluded`：当前仓库不提供该能力

> 工具的唯一信源是中央目录 `src/fatebridge/services/tool_catalog.py`。REST 公开 **91 个工具**，MCP 公开 **92 个工具**，分为 **13 个 family**。本页按 MCP 集合统计；目录有 93 条记录，CLI 可执行 92 条，差异见 [API 参考](api-reference.md#24-三端能力边界)。下表逐 family 列出全部工具；新增能力时请同步本页（总数、逐 family 数量与完整工具清单由 `tests/test_doc_tool_counts.py` 锁定）。

所有目录记录现有统一的输入/输出 Schema，三端由同一 `ToolSpec` 发布并校验；这属于接口合同覆盖，不提高算法的 `Implemented` / `Approximate` 等级，也不表示全部嵌套专业字段已有完整类型定义。

摘要/筛选发现与 MCP family 配置同样派生自目录，不改变算法等级。annotations 描述环境影响，不承诺数值确定性；投影警告与严格模式见 [API 参考](api-reference.md#25-字段投影与输出体积)。

## 怎样核对一次结果

| 核对项 | 看什么 | 不能据此推出什么 |
| --- | --- | --- |
| 接口成功 | HTTP 状态、MCP `isError`、CLI 退出码与错误包络 | 所有请求层都完整计算 |
| 计算与规则覆盖 | 实际 `status`、`coverage`、缺失项及所选规则 | 未请求方法也已审查，或候选已经确认 |
| 数值与时间精度 | 实际后端 / 星历模型、时间修正、分析时刻及对应限制 | 包可导入就已加载星历，或“非近似”就能预测现实 |
| 可追溯性 | 原输入、`run_metadata`、版本、来源与环境 | 仅凭 run ID 可以恢复历史输入或永久取得结果 |

工具总量和 Schema 完整性是接口证据；具体计算、传统解释及现实建议分别核对。风水还需区分动作可执行与规则审查，见[分层状态](fengshui.md#分层结果与覆盖状态)。

## 1. 总览：13 个 family / 92 个工具

| family | 工具数 | 主题 | 总体状态 |
| --- | --- | --- | --- |
| `bazi` | 12 | 八字命盘、九大专项、综合命理及原典四柱核对 | Implemented |
| `compatibility` | 2 | 双人配合（八字合婚 / 宿曜相性） | Implemented |
| `timing` | 9 | 大运 / 流年 / 流月 / 流日 / 流时 / 节气 / 农历 | Implemented |
| `divination` | 11 | 梅花、六爻、统摄法、参评数、河洛、宿占、三式合参等 | Implemented |
| `metaphysics` | 8 | 紫微斗数、六壬、奇门、太乙、金口诀 | Implemented |
| `astro` | 9 | 核心星盘、印占本命／分盘／达沙及关系盘 | Implemented（精度依赖星历） |
| `western_timing` | 1 | 西占推运总览 bundle | Implemented（依赖 backend） |
| `western_timing_tool` | 11 | 独立西占推运技法（返照/行运/主限/法达…） | Implemented（依赖 backend） |
| `western_event` | 4 | 事件占星（世俗/卜卦/择日/多重回归） | Implemented（依赖 backend） |
| `western_lifespan` | 13 | 全生命周期 / 寿命技法（古典+西占） | Implemented（依赖 backend） |
| `knowledge` | 2 | 内置知识库目录与读取 | Implemented |
| `export` | 2 | 导出协议注册表与快照解析 | Implemented |
| `fengshui` | 8 | 公共方位、命卦、八宅、砂水、年／月紫白、玄空宅盘、分层合参 | Implemented（明确版本） |
| 仓库内前端 | — | 内置 Web UI | Excluded |
| 存储 / 账户 | — | 数据库、历史记录、用户体系 | Excluded |

## 2. 逐 family 工具清单

### 2.1 `bazi` —— 八字与命理分析（Implemented）

底层由 `fatebridge.core.calendar` / `elements` / `rules` 与 `fatebridge.services.bazi` / `calculation` 提供；九大专项维度的大运、流年缺省由命盘 + 分析日期内部推算，可用 `dayun_pillar` / `liunian_pillar` 覆盖。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `analyze_destiny` | 综合命理分析（八字 + 喜用 + 格局） | Implemented |
| `bazi_birth` | 离线八字命盘，完整 `snapshot_text` + 可筛选 `snapshot_export` | Implemented |
| `bazi_source_compare` | 已明确的字面四柱与登记编释逐项核对；保留计算、冲突与未知，不反推生日 | Implemented（已暴露材料核对） |
| `bazi_marriage` | 婚姻：配偶星/宫、婚期信号、婚姻质量 | Implemented |
| `bazi_career` | 事业：事业类型、行业、创业倾向、贵人方位 | Implemented |
| `bazi_wealth` | 财运：正偏财、财库、求财方式/方位、破财风险 | Implemented |
| `bazi_health` | 传统健康文化：盘内权重／寒暖分类和传统名称对应；疾病风险禁用，不作体质诊断或调理处方 | Implemented |
| `bazi_children` | 命主视角的子女星／宫传统对应；不推数量、生育能力或生育时间 | Implemented |
| `bazi_education` | 学业：印星/食伤/官星、学历倾向、文昌、考试时机 | Implemented |
| `bazi_personality` | 性格：日主心性、十神性格、刚柔内外向 | Implemented |
| `bazi_relatives` | 六亲：父母/兄弟姐妹星、六亲宫位、贵人 | Implemented |
| `bazi_romance` | 正缘桃花：桃花咸池、红鸾天喜、异性缘星、正缘时机 | Implemented |

八字11个出生资料入口与七个时运入口可接收已知整秒，提供秒数时须显式提供分钟；出生上下文保留省略分量与兼容00值，见[出生秒数与输入分量](bazi-birth-seconds-audit.md)。这是输入传递能力，不认证真实出生记录精度，也不提高原典或现实预测的验收等级。

上述入口可用已确认的 `birth_utc_offset` 消歧重复民用钟时；偏移须匹配已解析时区，未来交运保留原IANA地区规则。未知选择和跳过钟时继续拒绝，见[重复钟时审计](bazi-birth-fold-audit.md)。

### 2.2 `compatibility` —— 双人配合（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `two_person_compatibility` | 双人配合度分析（八字合婚 / 合作），复用两份个人分析做组合 | Implemented |
| `sukuyo_compatibility` | 宿曜双人相性（三九の秘法，二十七宿） | Implemented |

### 2.3 `timing` —— 时运与历法（Implemented）

八字时运默认按目标时刻与十二步大运交运边界选运；显式年龄查询保留参考口径。
综合结果增加原局与岁运的关系证据，不将十神、合冲或五行占比直接定为吉凶。
换算版本、独立节气对照及未覆盖的有效旺衰、制化与应期，见[八字时运审计](bazi-timing.md)。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `timing_analysis` | 综合时运（大运/流年/流月等综合影响） | Implemented |
| `dayun_analysis` | 大运分析 | Implemented |
| `liunian_analysis` | 流年分析 | Implemented |
| `liuyue_analysis` | 流月分析 | Implemented |
| `liuri_analysis` | 流日分析 | Implemented |
| `liushi_analysis` | 流时分析 | Implemented |
| `jieqi_timeline_analysis` | 节气时间轴分析 | Implemented |
| `jieqi_year` | 指定年份节气时刻表（calendar helper） | Implemented |
| `nongli_time` | 公历时刻转农历与干支（calendar helper） | Implemented |

> 历法基于本地算法（`fatebridge.core.almanac`），不依赖外部服务。真太阳时修正含经度 + 均时差，统一走 `fatebridge.utils.solar_time`；出生输入构造使用 `fatebridge.utils.birth_input`。

### 2.4 `divination` —— 占卜与本地技法（Implemented）

均为本地离线技法，输出分为双层快照、仅文本和结构化数据，详见 §4。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `gua_lookup` | 卦象查询（六十四卦义理） | Implemented |
| `gua_meiyi` | 卦义 helper（批量说明） | Implemented |
| `meihua_analysis` | 时间取数、体用互变、季令及经文参照；[有限原典规则与验收](meihua.md)，特定天气政策检验未胜基线，预测效力未证实 | Implemented |
| `meihua_cast` | 物数、两段声音、丈尺/尺寸、字占、端法、年月日時加已报数及既有卦；保留输入缺项、取爻约定及原文语义分歧 | Implemented |
| `tongshefa` | 统摄法 / 大衍筮法起卦 | Implemented |
| `sixyao` | 六爻纳甲分析 | Implemented |
| `canping` | 邵子参评数 / 金锁银匙（数算） | Implemented |
| `heluo` | 河洛理数（数算） | Implemented |
| `suzhan` | 宿占分析 | Implemented |
| `otherbu` | [占星骰](astrodice.md)：十二骰面、七曜星座关系、条件三分性与喜乐宫；可追溯解释与独立天象，现实预测未验证 | Implemented（符号规则） |
| `sanshiunited` | 三式分层证据、五将按实际方位对应奇门星门神，明确地支对应六壬十二神；四维寄支和完整联合断法未校定，见[审计](taiyi-sanshi-audit.md) | Partial |

河洛端点年改用共享民用年节气窗口，化工／至点、四立及二数时令保留实际来源并核对同次上下文，未扩模型年份；参平完整年序另补有界立春依赖，保留120年及121个边界和实际所选模型，见完整年序核对（本地数据：`validation/canping-projection-audit.md`）；河洛端点来源见上下文核对（本地数据：`validation/heluo-solar-context-audit.md`）。河洛反元气新增出生年干支目标核对与逐阶段无正而有反前提，区分候选命中和原句条件，救法未定，见相反前提核对（本地数据：`validation/heluo-yuanqi-opposition-audit.md`）。河洛补上二十四节卦、七十二项原列候卦标签、六十卦名义日序的两种具名重建；原印爻名和模型衔接差异并列，不按吻合度选模型或授予实际候卦／化工，见节候核对（本地数据：`validation/heluo-jiehou-audit.md`）。河洛新增卷一百刻支长、六日移支相对边界及岁运年上下文绑定，拒绝年标签／干支冲突改变卦序；六十块365源日不代替每日分制、物理原点或实际日卦日期，见百刻核对（本地数据：`validation/heluo-clock-year-context-audit.md`）。河洛注文新增小畜履十二爻及履六条标题，两层各60／384、各待校324；小畜九三按未单列不葉者的实际三段返回，小畜初有条件引巽初与正式后天巽四分清，见小畜履核对（本地数据：`validation/heluo-xiaochuli-commentary-audit.md`）。比六二全卦纳甲插段已分离，师三引升三仅作有条件单爻核对，不替代正式后天盘，见师比核对（本地数据：`validation/heluo-shibi-commentary-audit.md`）。条件原义及少见字面保留。标题／注文锁定该版规范内容身份，非空换文或交换正文不再冒充已校，来源标题按实际条数生成，见注文与内容核对（本地数据：`validation/heluo-xusong-commentary-audit.md`）。河洛与参评数新增已选年干起月、日干起时的衔接证据，固定四柱起命拒绝不相容组合；一条原文冲突算例照录并保留形式取数，不计为已验出生盘，见衔接核对（本地数据：`validation/numerology-pillar-links-audit.md`）。河洛与参评数提供取数轨迹、版本来源和未决规则；参评数默认 `gu` 日支法，显式 `ming` 为月支变法。渐卦四体八体结构另列原爻位映射、三爻／六爻区分及原例与算子推演来源，不改纳音或元气取体，见结构核对（本地数据：`validation/heluo-structure-audit.md`）。十体有援的具名主本阴元堂、阳应爻式按实际阶段给出，通用相异不代替原句或十体总判，见原句核对（本地数据：`validation/heluo-support-clause-audit.md`）。历法边界、同支十三位、三元循环及有限原典算例的独立校验见[河洛与参评数审计](numerology-audit.md)。完整原典一致性与现实预测效力尚未通过验收。

六爻现提供版本化《增删卜易》结构证据、日月支关系、伏神候选和实际动爻原文，另列明确取用、月令、动静合绊、变爻同位作用及日级候选条件；《周易》64 卦、384 爻的原文与现代摘要分开标注。总旺衰、完整应期及现实预测效力的缺口、独立历表与穷举校验范围见[六爻与周易深度审计](liuyao-depth-audit.md)。`Implemented` 表示工具接口与所列计算可用，不表示原典全书认证或现实预测满分。

### 2.5 `metaphysics` —— 中国术数独立盘（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `ziwei_birth` | 紫微斗数命盘 | Implemented |
| `ziwei_horoscope` | 紫微斗数运限（大限/小限/流年/流月/流日/流时 + 动态四化） | Implemented |
| `ziwei_rules` | 紫微斗数规则 helper | Implemented |
| `liureng_gods` | 四课三传、天将、按探原总说推导的细课名，及同盘支位合冲刑破害并存依据；表注仍有差异 | Implemented（部分原典核对） |
| `liureng_runyear` | 农历虚岁行年与分析时刻六壬课（不含逐流月预测） | Implemented |
| `qimen` | [时家转盘](qimen-depth-audit.md)：置闰／拆补、寄宫及有来源的格局证据；原典片段验收，现实预测未验证 | Implemented（限定规则） |
| `taiyi` | 《太乙金镜式经》年计及卷五年度十神、六纪节月与冬夏至时计的现代天文适配；阴阳144局两算、七类空间条件、卷四五将合取；年/月定计及[分法八门](taiyi-gates.md)，另有明选[金钥匙时计](taiyi-hour.md)完整积时与四门，及[金钥匙日计](taiyi-day.md)积日与分源十精；原表与定计课例分歧、古历异单位解释及引文异数保留，见[审计](taiyi-sanshi-audit.md)；显式[历史年计](taiyi-year-calendar.md)支持381—385晋历及501—505齐梁史历主表，502年闰标异说随结果保留，未据此认证原典古日计 | Partial |
| `jinkou` | 四位、阴阳用位及受克空破、五动三动、季节与有限课内旺衰、得气、六十四课钤逐条三态判定、四绝及岁日结构、三合齐缺与成员空破条件 | Implemented（58条课钤结构已评估，6条未决，全部64条以true/false/null区分命中、未命中、未判；四败仅临地分，大绝按显式本命支计算、缺命保留未知；支齐不等于合化，完整合化及综合取用未裁定） |

> 紫微斗数以 iztro 2.5.8 为对齐基线，采用正月初一年界、虚岁自然年递增、本命晚子时算当天、闰月后半月算下月的规则。当前冻结 1,080 张本命软件参考盘及 18 个运限用例，分别核对本命星曜／长生博士等和六层落宫／四化；流月/流日/流时比较实际落宫索引，不能用历法地支代替。返回的 `branch` 是实际落宫，`palace_ganzhi` 是本命宫干支，`stem` 是该运限四化所用天干；后两者可能不同。另以 `childhood_limit` 独立返回原文明示一至六岁之命、财帛、疾厄、夫妻、福德、官禄宫及实际本命星曜；后续岁序留空，岁首及大限前替代关系未认证。既有起大限前童限替代与独立童限分别披露；农历日期或大限超出支持范围时明确报错。

> 紫微现另提供版本化 `quanshu_v2_excerpt`（1.3.1 选择闰月、壬年四化、亮度、长生、旬空双支、部分年度流曜、邻宫起大限及火铃年支定点读法，仍非全书认证）、规则轨迹、三方四正证据和六层十二宫功能名映射。新增16星原文属性到本命星位连接，文本化义与实际四化分栏。200年HKO历表、1900年NASA朔日补证、部分明刊书影校勘及三项专业验收范围见[紫微专业能力与验收](ziwei.md)；未知性别的长生／博士仅保留两方向都相同的起点和对宫标记，另有逐宫来源比较；其余位置仍未定。软件对齐不代表全书认证或现实预测已验证。

> 运限的 `natal_prerequisites` 另携带同次内部本命的月时、年干、命身、宫干支纳音与局数推导，供解释局数及起限岁数时直接引用。它核实实际计算之间的连接；公历起算、原典岁首与现实效度仍需分别验收。

> 六壬取传按九宗门，第一课生克用日干五行、寄宫只定位；贵人顺逆按贵人实际落地盘的位置判断（巳至戌逆布）。已与独立 daliurenpython 的 8,640 种日干支/时支/月将组合对照，三传全部一致。初轮 kinliuren 参考软件的部分三传存在不稳定与异常，不能把与该软件的所有差异一律判为 FateBridge 错误。固定参考来源与 720 张独立天地盘保存在三传基准（本地数据：`../tests/fixtures/liureng_transmissions_reference.json`），[全组合回归](../tests/test_metaphysics_reference.py)遍历每张盘的 12 个时支位置。此对照限于三传，不包含所有神煞、课体解释、流派差异或金口诀的完整独立认证。

> 金口诀按本法地分起贵神，使用贵神固有干支；不以大六壬三传课体取用。六壬三传另返回日旬遁干、本空及坐空，空支不补造遁干；天盘顺布与贵人顺逆分开。三工具支持 `is_diurnal` 显式选择昼贵/夜贵，省略按时支约定。金口诀另据京本书影分列三合成员、虚一支、人元关系及空破事实，不据所忌支自身出现自动破局，详见第八轮验收（本地数据：`validation/jinkou-combinations-validation-2026-10-22.md`）。原典与历法各层范围见[专业能力审计](liuren-jinkou-audit.md)。

> 三工具以 `calendar_policy` 公布实际时钟和23:00子初换日；天文求解失败返回依赖错误，不用线性节气回退起课。交气使用TT求解后按历史UTC/闰秒政策转换，五个实际依赖公开转换方法及未来闰秒假设；小数秒只表示数值分辨率。第三十五轮对原3,024个分钟值及4,536组换将边界分别验证原生Swiss、有文件解析和无文件默认模型：分钟超差为21／22／22项，边界失败均为0；同一队列DE440 TT对照均在原1秒线内。当前HKO 73,049日农历标签重放符合，原326日空缺由现有来源表补充覆盖；这不是独立月球理论认证。旧7项节气日期差异及交节当日未定探针未在本轮重评，详见部署模型验收（本地数据：`validation/ren-model-matrix-validation-2026-10-22.md`）及保留的第七轮记录（本地数据：`validation/ren-timescale-validation-2026-10-22.md`）。完整历法域未认证。

> IMCCE OPALE三条时间路线也分别重放：原生／解析的初始504项均有1项历史UT1超差；文档时间约定244项分别有4／3项超差；来源自身钟差换算TT的288项均在原1秒线内。它们复用旧PMO事件，分钟差异继续保留，不能相加为新增独立命中。来源时间定义见第三十二轮验收（本地数据：`validation/ren-opale-seasons-validation-2026-10-22.md`），实际模型结果见第三十五轮（本地数据：`validation/ren-model-matrix-validation-2026-10-22.md`）。

> 六壬新增 `transmission_relations`，按《探原》分列天将与支神生克、初末生墓、递克、旬空、朝日朝枝及四组三合名义局体；原支六亲与取传不改，完整救制、有效空亡与合化未裁定，见第三十轮验收（本地数据：`validation/liuren-transmission-relations-validation-2026-10-22.md`）。

> 六壬规则集1.6.0新增 `emptiness_evidence`，将天盘本空、地盘落底空、日干寄宫地盘例外、太岁月建月将角色及占时本空分别计算。原旬空两支、三传本空与坐空标志保留；局部不空条件不等于综合有效空亡已裁定，年命、真空半空及填实冲实仍未决，见第三十六轮验收（本地数据：`validation/liuren-empty-scope-validation-2026-10-23.md`）。

> 六壬1.7.0新增 `branch_relations`，依《探原》印刷配对并列六合、六冲、六害、六破及双向刑，保留寅亥破合、巳申刑合。47项天地盘、四课、三传与年月日时接触是同盘位置比较，不据合独断成局；首课寄宫支不替代日干五行，金口诀附盘不覆盖其本课规则。原720盘核心数值保留，原典未决不重判，见第三十八轮验收（本地数据：`validation/liuren-branch-relations-validation-2026-10-23.md`）。

> 金口诀1.11.0补入京本六甲旬起行年与独立另课，明确出生年干支、指定岁序、男女起点及推导地分来源；原问课保留，资料不足不补猜。原书行年干合例与另课路径仍有疑义，岁首、实际年龄联动及综合喜用未认证，见第四十六轮验收（本地数据：`validation/jinkou-year-fate-validation-2026-10-23.md`）。

> 六壬／金口诀历史封套另按原始输入补齐完整依据，并核对四份业务合同及真实三端；旧时钟隔离与六合独断成局的文字缺口已修复。核心计算值保留，Linux全文件字节、原典全书和自由解释的未完成项分别记录，见第四十五轮验收（本地数据：`validation/ren-golden-evidence-validation-2026-10-23.md`）。

> 金口诀1.10.0新增 `branch_stars`，按京本PDF118–120列七项历法目标及三位本支相同位置；驿马按月建支，天赦比完整日干支。月序采用明确的软件约定，综合效力为null，完整原典认证仍为false；720课旧本课对象保留，见第四十四轮验收（本地数据：`validation/jinkou-branch-stars-validation-2026-10-23.md`）。

> 六壬1.9.0新增 `seasonal_evidence`，按《探原》五季25项状态表分别列支神、天将与地盘五态。月建支采用明确的季月整月配置，不冒充季末十八日异法已裁；支神本空真半只列条件，扶助冲剋、角色例外后的有效类别为null，原文效力折扣不转为成功率。原34,560组符号盘与48份金口诀本课对象保留，见第四十三轮验收（本地数据：`validation/liuren-seasonal-validation-2026-10-23.md`）。

> 六壬／金口诀的五项交气依赖另列 `published_date_reference`，用固定UTC+08对照香港天文台1901—2100全部4,800个刊载日期。匹配只到日期层，冲突不改交界，范围外为null；原7项差异在四种配置下均保留。规则集及原数值不变，参考正确不冒充天文瞬间、全历法或全原典认证，见第四十二轮验收（本地数据：`validation/ren-hko-dates-validation-2026-10-23.md`）。

> 六壬1.8.0新增 `transmission_progression`，按《探原》PDF110–111识别进退连茹与进退间断，另列仅按支神本空假设下的初空、末空及见空释读。支序方向与综合有效进退分开，后者仍为null；坐空与天将天空不替代本空，不更改九宗门或金口诀四位。冻结枚举与原典范围见第四十一轮验收（本地数据：`validation/liuren-progression-validation-2026-10-23.md`）。

> 金口诀 `overview.month_general` 保留中气月将本位，`overview.yuejiang` 是兼容字段名，实际为月将加时后落在地分的将神。快照分别显示“月将本位”和“将神落地分”，四位数值及取用不因改名改变。完整整秒队列、三端与逐行说明核对见第四十轮验收（本地数据：`validation/ren-seconds-validation-2026-10-23.md`）；固定参考下的一致性不作为全书、真实授时或自由文本预测认证。

> 六壬 `meta.diurnal_evidence` 与金口诀 `overview.diurnal_evidence/is_diurnal` 分列显式选择、默认时支和未记录的现场星象，快照同显依据。它们核验的是起贵人选择，不把固定时支或布尔覆盖冒充星出星没的天文观测，见第九轮验收（本地数据：`validation/ren-diurnal-validation-2026-10-22.md`）。金口诀课内旺衰、月建日辰得气与用位条件须回到同次四位核对，完整结果保留可空事实及唯一轨迹，见第三十三轮验收（本地数据：`validation/jinkou-strength-integrity-validation-2026-10-22.md`）。授权的六例真实模型已执行，首次机械检查5/6、人工21项中18符合和3覆盖不全，见第三十四轮记录（本地数据：`validation/ren-semantic-execution-validation-2026-10-22.md`）；本轮新增说明未再进行真实模型验收。

### 2.6 `astro` —— 离线核心星盘与关系盘（Implemented，精度依赖星历）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_chart` | 离线核心星盘（`chart_variant` 切换盘式） | Implemented / Approximate（见 §3.1） |
| `astro_chart13` | 上升起点的 13 等分扇区，精确分界；自定义分区，不是 IAU 星座 | Implemented / Approximate（天文底盘依赖星历） |
| `astro_hellen_chart` | 离线希腊盘 | Implemented / Approximate |
| `astro_guolao_chart` | 七政四余连续坐标、不等赤经研究宿界、宫主/度主与规则轨迹 | Implemented（需 Swiss；原典全盘与现实效力未验收，见[果老说明](guolao.md)） |
| `astro_india_chart` | Lahiri 九曜、星宿／Pada、D1/D2/D3/D7/D9/D10/D12/D30、宫主／尊贵／相位、生时敏感性、未削减八分法及声明七曜占据口径的削减／Pinda；另列Aiyar1905自己的原始表与削减链（本地数据：`validation/jyotish-aiyar-bav-audit.md`），保留仅换削减的历史口径（本地数据：`validation/jyotish-aiyar-reductions-audit.md`） | Implemented（需 Swiss Ephemeris；原典未决分支保留空值，非预测有效性认证，见[印占范围](jyotish.md)） |
| `astro_vimshottari` | Moon-nakshatra 出生余运、MD／AD完整目标周期、可选2—6层当前路径及逐层子期；三种年长与完整运主链生时网格 | Implemented（需 Swiss Ephemeris；v23候选全局舍入验收（本地数据：`validation/jyotish-dasha-global-epoch-audit.md`），细分不代表事件精度） |
| `astro_germany_chart` | 22 因素、253 中点轴、90°／45°对称式；可选指定时刻真太阳弧、本命／推运分层与生时重排；原文示例按实际直接占据触发并去重 | Implemented（需 Swiss Ephemeris；完整原典与现实效力未验收，保留七曜视图） |
| `human_design` | [人类图](human-design.md)：88°设计时刻、26激活、36通道、类型权威与原典数值分歧；现实预测未验证 | Implemented（限定机制） |
| `astro_relative_chart` | 离线关系/合盘（`compare`/`composite`/`influence`/`timespace`/`marks`） | Implemented / Approximate |

独立印占规则、兼容字段范围和数值对照见[印占说明](jyotish.md)。

德国中点几何的 Rudolph 条文、出版社星历对照，以及 13 等分扇区的边界修复与解释范围，见[其他流派星盘](other-chart-schools.md)。

### 2.7 `western_timing` + `western_timing_tool` —— 西占推运（Implemented，依赖 backend）

走 `fatebridge.core.predictive.*`；缺 `kerykeion` / Swiss Ephemeris 时**直接报错，不降级**（见 §3.3）。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `western_timing_analysis` | 西占推运综合总览 bundle | Implemented（依赖 backend） |
| `solarreturn` | 太阳返照 | Implemented（依赖 backend） |
| `lunarreturn` | 月亮返照 | Implemented（依赖 backend） |
| `transit` | 行运盘 | Implemented（依赖 backend） |
| `solararc` | 太阳弧 | Implemented（依赖 backend） |
| `givenyear` | 指定年盘 | Implemented（依赖 backend） |
| `profection` | 年小限 | Implemented（依赖 backend） |
| `pd` | 主限（primary directions） | Implemented（公开近似/坐标策略，见 §3.3） |
| `pdchart` | 主限法盘 | Implemented（含 coordinate / approximation 元数据） |
| `zr` | 黄道释放（zodiacal releasing） | Implemented（依赖 backend） |
| `firdaria` | 法达星限 | Implemented（依赖 backend） |
| `decennials` | 十年星限 | Implemented（依赖 backend） |

法达支持独立选择夜盘交点顺序和固定年／公历周年口径，默认行为保持；参数与日期边界见[版本兼容参考与验收约定](firdaria-compatibility.md)。

### 2.8 `western_event` —— 事件占星（Implemented，依赖 backend）

求解天文时刻后起盘的一组事件类工具，走 `fatebridge.core.astrology_events` / `astrology_horary` / `astrology_election`。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_mundane` | 世俗入宫盘 | Implemented（依赖 backend） |
| `astro_extrareturns` | 多重回归 | Implemented（依赖 backend） |
| `astro_horary` | 卜卦判断 | Implemented（依赖 backend） |
| `astro_election` | 择日 | Implemented（依赖 backend） |

此处Implemented表示接口与计算路径存在。卜卦已逐项实现Lilly1647的两列相位容许度、实际落宫、分别保留的宫位序次／宫位分值及居宫的必要月亮条件；完整偶然尊贵、传光／阻碍与全盘判词仍未验收，`verdict=uncertain`。具体来源与未通过项见容许度与居宫核验（本地数据：`validation/western-lilly-orbs-houses/report.md`）。判断前审查（本地数据：`validation/western-lilly-radicality/report.md`）补齐第121–123页12项手工清单与报告的例外，四个时主对应例复现；未知月亮晚度、受损定义及整盘判断资格仍保留，不能据此认证现实预测。

卜卦与择日另支持显式儒略历日期，分别通过 `question_calendar`、`candidate_calendar` 选择；日期先按相应闰年规则校验、换成内部格里历，再处理时区。原日期与规范化日期并列返回，默认仍为前推格里历；其他出生／分析入口未据此扩展。地区改历、旧式年份与原典钟时不推断，见历法与例题精度核验（本地数据：`validation/western-civil-calendar/report.md`）。

已确认的地方平／地心视太阳时可分别由 `question_clock_basis`／`candidate_clock_basis` 显式输入，不能与民用时区叠加；默认民用钟时及省略时区的旧 `+08:00` 行为保留并标来源。`clock_conversion` 分开输入钟面和物理时刻；太阳时卜卦的行星日按声明钟时的开启日出日期取星期，未借用内部UTC载体的日期。两组复用JPL历元及手工算术只验有限转换，原书钟时鉴定、整图验收和现实预测仍未成立，见事件钟时核验（本地数据：`validation/western-event-clocks/report.md`）。

另以 `question_hour_origin`／`candidate_hour_origin` 显式处理午夜／正午起算的小时标签，支持跨日、世纪儒略闰日和有效终点越过不可表示中间日期。范围先在整数日编号上合并，再建立最终格里历钟面，时区与太阳时在后；没有推断全部历史原图的日起点。所选Lilly1647第30–31页条款及公开JD数例分别核验，1978年元旦UT1的UTC闰秒载体缺口仍列为失败，见正午日起点核验（本地数据：`validation/western-noon-origin/report.md`）。

太阳时反解落入UTC闰秒时，卜卦／择日保留原生TT／UT1继续计算，`converted_utc`可返回含`23:59:60`的标签。`clock_conversion.utc_representation`明确区分UTC标签、闰秒与Python datetime可表示性；不要截断、平滑、移秒或把显示限制说成星盘不可算。仍不推断原资料精度、实测EOP、完整原典或现实预测有效性。见物理时刻与闰秒核验（本地数据：`validation/western-leap-epoch/report.md`）。

### 2.9 `western_lifespan` —— 全生命周期 / 寿命技法（Implemented，依赖 backend）

读取单张本命盘的一组全生命周期技法，走 `fatebridge.core.astrology_lifespan`。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_harmonic` | 调波盘 | Implemented（依赖 backend） |
| `astro_planetary_ages` | 行星年龄 | Implemented（依赖 backend） |
| `astro_triplicity_rulers` | 三分主星推运 | Implemented（依赖 backend） |
| `astro_lunation_phase` | 月相推运 | Implemented（依赖 backend） |
| `astro_distributions` | 界推运（distributions） | Implemented（依赖 backend） |
| `astro_balbillus` | Balbillus 129 年系统 | Implemented（依赖 backend） |
| `astro_keypoints` | 数字相位推运 | Implemented（依赖 backend） |
| `astro_yearsystem129` | 129 年系统 | Implemented（依赖 backend） |
| `astro_planetaryarc` | 行星弧方向 | Implemented（依赖 backend） |
| `astro_persiandirected` | 波斯向运 | Implemented（依赖 backend） |
| `astro_agepoint` | 年龄推进点（age point） | Implemented（依赖 backend） |
| `astro_vedicprog` | 恒星推运 | Implemented（依赖 backend） |
| `astro_jaynesprog` | 赤纬推运 | Implemented（依赖 backend） |

### 2.10 `knowledge` + `export` —— 知识库与导出（Implemented）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `knowledge_registry` | 列出内置知识域与分类 | Implemented |
| `knowledge_read` | 读取单条内置知识并支持导出裁剪 | Implemented |
| `export_registry` | 返回 FateBridge 导出协议注册表 | Implemented |
| `export_parse` | 将快照文本解析为可筛选的结构化 section | Implemented |

> 内置知识域：`astro`、`bazi`、`liureng`、`qimen`。`bazi` 域含十神（10）、神煞（12）、格局（10）、五行（5）、财运（8）、健康（8）、子女（4）、学业（6）、性格（3）、六亲（3）、正缘桃花（3）等条目。

### 2.11 `fengshui` —— 家居风水（Implemented）

| 工具 | 范围 | 状态 |
| --- | --- | --- |
| `fengshui_directions` | 后天方位／洛书宫数、八方与24山角区索引 | Implemented |
| `fengshui_minggua` | 1864锚点命卦、原始五数寄宫、个人八方关系 | Implemented |
| `fengshui_bazhai` | 坐山宅盘、逐人命盘、位置／朝向用途分开 | Implemented |
| `fengshui_jinsuo` | 八宫固定砂水偏好、已确认特征逐项判定 | Implemented（传本来源限制明确登记） |
| `fengshui_annual_stars` | 年度紫白九宫、立春区间、当前元运 | Implemented（交节时刻依赖现有节气引擎，可能近似回退） |
| `fengshui_monthly_stars` | 十二节月紫白、跨年有效年、九宫中性位置与固定释义 | Implemented / Limited（原表36数、独立节气口径；保留原表六月节候倒序，未实现月星用途处方或现实效度认证） |
| `fengshui_xuankong_natal` | 中州派历史定运、24山／三元龙、五黄、下卦与兼向替星 | Implemented（xuankong_zhongzhou_v1） |
| `fengshui_assess` | 多层布局关联、匹配方位、现代作者室内形态、条件式元素/年度方案、分歧与版本 | Implemented（限已登记规则版本） |

布局入口设 `analyze_layout=true`。扩展覆盖包括场景选法与优先审查状态、家庭人物及楼层上下文、12 类明确室内关系、独立材质／器形事实、家具候选比较，以及显式启用的玄空有限解释；只按已确认事实与登记版本计算。照片候选、缺失资料、未覆盖规则和动作可行性分别保留，`complete` 不等于所有方法均已审查或可立即执行。输入与来源详见 [风水专题导航](README.md#风水专题)。

所有工具三端可调用；复杂 CLI 请求用 `--request-file`。固定宫数、年／月紫白和八宅星分开，各法没有统一分数。24山方向索引不代表已经支持24山风水论断。月紫白限中性位置与固定释义，未实现月星布局处方或年／月叠加断事。金锁形态距离／元运与自动户型几何仍为 Excluded，输出明确列入 `unavailable_layers`。

验证包括固定第三方命卦400项／关系64项、独立2026年星盘和跨端合同，不代表现实预测有效性。来源、算法和输入合同见 [家居风水](fengshui.md)。

第二阶段的运／山／向宅盘与年星分层；版本选择、7套公开完整盘例及固定外部216盘比对的24项五黄差异见 [玄空宅盘](fengshui-xuankong.md)。

## 3. 精度与依赖说明

### 3.1 核心占星盘（`astro` family）

西方本命盘的历法、UTC／TT／UT1、地平宗派、Robbins 1940《四书》限定子集与 NASA/JPL 外部对照见[西方占星验证说明](western-astrology.md)。`classical.ptolemy` 与混合古典规则分开，`interpretation_evidence` 提供本次解释依赖的字段路径；天文容差、原典范围、文本忠实度与现实预测分别验收。

| 情形 | 状态 | 说明 |
| --- | --- | --- |
| 本地有 `swisseph` 且加载相应星历数据 | Implemented | 本地星历路径，实际模型由返回标志确定 |
| `swisseph` 可导入，但缺相应 `.se1` 数据 | Implemented / Approximate | 可能使用内置 Moshier 模型，不能仅凭包可导入或 `engine_backend` 判断数据精度 |
| 无 `swisseph` | Approximate | 回退到 FateBridge 内置近似轨道模型 |
| 显式 `hsys` 覆盖为 `1..8` 的离线宫制 | Implemented（但依赖 `swisseph`） | 缺失时**直接报错**，不静默退化为整宫制 |
| `zodiacal=1` sidereal(Lahiri-like) | Implemented | 离线 sidereal 模式，非联网服务 |

检查 `chart_profile.engine_precision` / `engine_backend` 确认代码路径，再用 `chart_profile.ephemeris_model` 确认实际模型：`swieph` / `jpl` 为相应数据模型，`moshier` 为内置模型，`mixed` 表示混合。`run_metadata.engine_is_approximate` 会标记已识别的降级。数据获取、路径与版本复现见 [快速入门](getting-started.md#星历数据与精度)。

`pyswisseph` 与 `kerykeion` 都是 `pyproject.toml` 的常规安装依赖。“缺依赖回退”描述的是异常/裁剪环境的能力边界，不是另一种官方安装模式。

### 3.2 关系盘（`astro_relative_chart`）

| 模式 | 状态 | 说明 |
| --- | --- | --- |
| `compare` | Implemented | 方向相位层为主 |
| `composite` | Implemented | 组合盘主层 |
| `influence` | Implemented | 影响盘双向主层 |
| `timespace` | Implemented | 时空中点盘（Davison）主层 |
| `marks` | Implemented | 派生关系主层 |
| 未识别的 `relative_mode` | Excluded | 返回 `validation_error`，不把非法 mode 当作受支持能力 |

兼容性提醒：

- `relative_mode="Synastry"` / `"synastry"` 按现代语义收敛到 `influence`
- 关系盘统一使用 `relative_mode`：`compare` 为比较盘，`synastry` / `influence` 为影响盘；旧字段 `relationship_mode` 已移除
- 两条语义不同，迁移旧调用时应显式区分

### 3.3 西占推运 / 事件 / 寿命（`western_*` families）

- 这四个 family 明确依赖 `kerykeion` / Swiss Ephemeris 运行时
- `ensure_predictive_backend_available()` 会在缺依赖时抛错（`dependency_missing`）
- 与核心 chart 不同，缺 backend 时不会使用 FateBridge 内置轨道近似；但这不保证所有 backend 都加载了相同星历数据，仍需检查返回的精度/模型字段
- `pd` / `pdchart` 虽已实装，但内部会公开其近似/坐标策略（time key、direct/converse、相位列表等），不应被误读为单一路径高精度结果

## 4. 快照协议覆盖

快照双层结构不是所有工具的通用保证。当前典型成功响应按以下形态组织；工具输入是否支持 `selected_sections` 另查 [API 参考](api-reference.md#23-selected_sections)。

| 形态 | 工具范围 | 读取方式 |
| --- | --- | --- |
| `snapshot_text` + `snapshot_export` | 八字独立盘/专项/综合分析、双人配合、全部时运与历法、卦义查询、三式合参、中国术数独立盘、knowledge、核心/关系星盘（中点盘除外）、独立西占推运、八个风水工具 | 业务数据为准，快照辅助阅读；支持选择的模型才裁剪导出 |
| `snapshot_text`，无 `snapshot_export` | `tongshefa`、`sixyao`、`canping`、`heluo`、`suzhan`、`otherbu`、西占事件与生命周期工具 | 读取文本与结构化业务数据；需要 section 解析时另调用 `export_parse` |
| 结构化数据，无双层快照 | `meihua_analysis`、`astro_germany_chart`、`western_timing_analysis`、`export_registry`、`export_parse` | 读取各自的业务字段；`export_parse` 直接返回解析结果，不再嵌套 `snapshot_export` |

使用建议：

- 存在的 `snapshot_text` 适合直接阅读；日志中的出生资料需按实际用途管理。
- `snapshot_export.export_text` 是可消费的导出层，不等于所有工具都支持筛选输入。
- `section_titles_detected` / `missing_selected_sections` 用于调试标题；`export_parse` 的这些字段位于响应根。
- `selected_sections` 不删除完整快照或业务数据。整体精简使用 `fields` 与 `include_snapshot_text`。

## 5. 这页不包含什么

算法正确性按历法、规则与数值对象分别核对；第三方一致率只适用于固定版本、约定与已比较的样本，不是项目整体的“准确率”。黄金快照锁定回归输出，不能证明现实预测有效性。性能数据也须注明环境、输入、冷/热启动、星历路径及计时范围；引擎计算耗时与模型选工具、MCP 宿主准备、网络往返分开报告。对话测量方法见 [Codex 使用指南](codex-guide.md#可复现体验)。

以下内容不应从本页推断：

- 不是所有能力都保证“天文级精度”（见 §3）
- 不是所有实现都意味着“无需本地依赖”（`western_*` 需要 backend）
- 关系盘模式有明确语义，迁移时须核对 `relative_mode`（见 §3.2）

如果你准备修改接口或新增能力，请同步更新本页，确保“文档状态”仍然是从代码反推出来的结果，而不是愿景描述。

卜卦／择日的显式 `ut1_source=iers_c04` 接入固定IERS20 C04日值及TT上连续UT1−TAI线性插值；默认与其他西占入口仍为Swiss ΔT模型。固定覆盖期仅1962-01-01 00:00至2026-09-19 00:00 UTC，不外推。只应用UT1，极移／CIP／日内潮汐、插值物理误差、完整原典、实际模型解释与现实预测继续待验收。见来源和验证（本地数据：`validation/western-iers-ut1/report.md`）。


<!-- agent-evaluation-private:start -->
## R66：资料检索与解释保真修复

公开河洛／参评入口拆为短入口及六张任务资料卡，保留原41个资料块（39个原样、两处更新过时覆盖表述）。修复旧评测文档进入模型工作区的隔离缺口，普通原典资料仍可读。原有11例、61判据不变：当前旧组24/25、新组36/36；仍有未来钟制条件漏述及一处额外引文缺口，不能认证解释满分。本地相关118项通过；原96历法点仍12项超过1秒，原典各90/384已目校及未决项不变，新增现实结局0。未执行本轮全仓回归。详见报告（本地数据：`validation/numerology-guidance-retrieval-audit.md`）与原始证据（本地数据：`../tests/fixtures/numerology_guidance_retrieval_v1/README.md`）。

<!-- agent-evaluation-private:end -->

本轮资料拆分与评测隔离的工程变更见审计报告（本地数据：`validation/numerology-guidance-retrieval-audit.md`）；历法、原典和模型解释的完整验收仍未完成。

## R67：《豫》六爻与逐条爻辞状态

新增所选印本豫六爻标题／完整注文目校，各96/384、288待校，仍含暂读；固守替换继承有守，两项错误首稿撤回，六二注文与九四头辞各一字未决。九四嵌套条件保留在不葉者父段内。修复全局标题状态覆盖单条疑字的问题，实际三端及临时stdio核验完成。完整相关104模块4954通过／2跳过，原全部节点保留；不是全仓CI。Native原96点仍12项超1秒，原典冲突、上轮模型未满足项及预测未验证状态不变，本轮模型调用0、现实结局0。详见报告（本地数据：`validation/heluo-yu16-commentary-audit.md`）与原始材料（本地数据：`../tests/fixtures/heluo_yu16_v1/README.md`）。


## R68：配运阅读上下文

配运结果新增同次`reading_context`，连接实际方法、钟制条件与书名／版本／书影、页码、引用角色；地区未来规则、固定偏移假设与旧法无日期映射分别披露。原始条款、首行、首运、查询身份与计算值保留。公开审计中的显式审阅私有段在模型工作区过滤，完整源文仍供人工审阅；完整历法、原典和模型解释验收仍未完成。执行状态和证据见审计报告（本地数据：`validation/canping-reading-context-audit.md`）。


## R69：参评扩围端点的完整年界

共享DE440独立年表登记1700—2300年后，参评新增具名有界立春数据与许可，覆盖低端1699年界和高端完整120年序列至2420年；旧产品、旧出生范围的计算与原判据继续保留。派生许可不扩大独立年表范围，原典符合、未来UTC及解释满分仍未建立；数值与完整相关验证见审计报告（本地数据：`validation/canping-extended-projection-audit.md`）。
