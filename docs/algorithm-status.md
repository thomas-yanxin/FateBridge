# 当前算法状态与未验收范围

[文档中心](README.md) · [API 参考](api-reference.md) · [覆盖矩阵](algorithm-coverage.md)

本页维护当前计算路径及已知限制。完整工具清单见[覆盖矩阵](algorithm-coverage.md)，请求和响应以[实际接口合同](api-reference.md)为准。局部数值回归、原典对照、接口一致性和现实预测分别验收，不能相互替代。

代表请求中发现的未决状态、已修复的条件缺口与后续裁定所需证据见[工具结果未决项审查](unresolved-calculations.md)。

## 当前采用的路径

| 范围 | 当前计算与边界 | 详细依据 |
| --- | --- | --- |
| 方法及运行证据 | 当前93条目录记录（92个MCP入口）登记65个共享领域方法；已核验的精确比例、整数环路、九宫步进及名义投影交付条件输出界和操作数边；全部上游语义证明及物理误差传递保持未决 | [计算证据合同](computation-evidence.md) |
| 细粒度源码清单 | 清单按当前源码登记计算、规则、支持职责及未映射定义，计数见链接中的统一索引。工具调用、职责审读、分支覆盖和独立验收分别登记；职责数不是细算法总数，全仓语义清查仍未完成 | [细粒度清单](algorithm-inventory.md) |
| 太阳地平线 | 自动路径复用DE440原始记录及域外有界DE441，完整有向序列服务于印度太阳日和西占行星时。完整10288个固定窗口、14459事件与独立原始JPL符合原1毫秒TT／UT1线，源码与Python3.10安装包最大约0.081毫秒。配置的JPL文件现由实际文件读数与完整TDB光学处理，192窗364事件的源码比较最大约0.040毫秒。原生Moshier30／32项同源失败和原生JPL364项时间失败均保留；最终版本、安装和三端按实际检查另记；部署与现有聊天进程另验 | [太阳地平线参考与未通过范围](../tests/data/solar_horizon_v1/README.md) |
| 西占九分度 | 所选Parashari映射使用给定浮点数的精确值判定3度20分半开区间，消除10度／20度落入前一份的错误。1296000项一角秒网格原24项错误已修复；另核324个边界邻点、12288个固定留出及两个书中例。固定PyJHora同边界也误判，仍以具名原表为准；不认证Hellenistic历史归属或现实预测 | [九分度来源与数值范围](western-astrology.md#九分度的来源与数值边界) |
| 主限后续算术与时点分类 | 推进弧、坐标环、容许度和相对岁数保留未舍入值，不让展示舍入参与后续运算。固定14个Ptolemy热带黄道场景的原4分类、45容许度及154法盘经度失败保留；修复后按相同独立操作数和门槛均通过。原天球模型、年长及0.01年窗口未改；完整原典、其他方法和物理／预测效度另验 | [主限坐标](western-astrology.md#推运返照与主限坐标) |
| 西占显式太阳钟面重置 | 沿用已发布的改变计算时刻约定；6个固定民用／重置服务请求在相同SwissΔT条件下满足原0.2毫秒时刻线及54个天体分量线。首次参考误用UT1=UTC的3个时刻失败另行保留，未修改生产时钟代码；不认证实际出生时刻、实测地球自转或历史钟时精度 | [钟时约定](western-astrology.md) |
| 八字本命 | `engineering_index` 保留 `season_root_revelation_relations_v12` 的原工程政策档与数值档；`classical_adjudication` 独立记录原典力量未决，不回填工程结果；格局候选与成格、有效力量分开 | [八字判定](bazi-assessment.md) |
| 八字藏干与特殊日事实 | 四柱六个位置对的藏干五合、所选禄位往来、缺中神拱候选与原典十组拱禄／拱贵分列；填实可排除，透干不自动增强。四生分类与实际驿马分开，日贵所需昼夜与既有6—18时参考分开；名单和有限符号对照不替代完整成格或力量验收 | [八字关系核对](bazi-relations-audit.md#后续藏干与特殊日事实层) |
| 八字柱内与柱间事实 | 明干至本气和每个藏干的方向分列，不以两类相生冒称完整覆载；六个柱对的同柱、干四冲、支六冲各自交付。120个单柱与3600个有序甲子对按全部相应位置作独立字面对照；原力量差异和约束违规保留 | [字段调整与范围](bazi-relations-audit.md#柱内与柱间关系的后续核对) |
| 八字专题与双人评分 | 明确消费工程索引与 `engineering_reference`，原分数和权重保留；来源喜忌未决另列，不把空来源方向当无互助；年、时配偶星的早晚信号同时命中时并列保留、未裁定 | [双人评分](compatibility-scoring.md) |
| 合盘条件与规则索引 | `compatibility_weighted_rules_v3` 保留权重，未命中喜用不补为忌，单方或无取用依据的名义合局不加双向支持分；缺项状态与逐人取用一起交付 | [双人评分](compatibility-scoring.md) |
| 五维文化索引 | `life_dimension_tanh_v2` 的已知零计数同式连续；未知爱情为null，参与层与不可用层单列，必需时间层失败返回错误 | [接口合同](api-reference.md) |
| 八字时运 | `single_layer_natal_budget_retention_projection_v2` 投影单层冲刑及唯一大运干合绊对既有预算的影响；不添加时间干支能量，未解会合或争合保留阻塞 | [时运与历法](bazi-timing.md) |
| 太阳交节 | 文件源保持原生TT求根；缺文件且原生探测返回Moshier时改用具名内置DE441同源视位置。原14904项及1200补充交点对独立原始JPL／CALCEPH／Skyfield进行角度与实际求根对照；原DE440一秒门槛及额外诊断失败分开保留。不是全时域、绝对UTC或SOTA认证 | [太阳后端](solar-backends.md) |
| 交节时刻不可用 | 移除1900年线性固定气回退；所选模型无根或来源未核实时返回明确错误，不用近似边界继续推断年、月或宅运 | [太阳后端](solar-backends.md) |
| 解析星历回退 | 同一连续有界DE441源提供接收地球／太阳及十个物理目标；源p／v／a、地心TDB时钟、隐式光锥、有限源偏折、Lorentz及显示旋转共同求局部TT日速；保留可用的其他原生天体 | [西占来源与差距](western-astrology.md#离线轨道近似的来源与差距) |
| 原生辅助归算的框架 | 复用明确的原生坐标变换，删除近共面天体位置反求；734组原作者C单位轴对照符合原门槛。3848组原源算术参考符合原线，但相对旧实现1475组误差略增，保留全部记录；原C差分116失败、330未稳定及194逐点劣化仍另列 | [反求病态与验收](precision-acceptance.md#原生框架反求病态修复) |
| 无原生库的Lahiri原点 | 完整均原点与77项章动共用实际轨道TT，日速扣同一原点解析TT导数；24532个TT与显式原生Lahiri符合原数值线，旧线性公式退役；不改变物理轨道失败 | [分项验收](precision-acceptance.md) |
| 历史UTC源算术、有效域与反解 | 1960–1971年共用发布十进制仿射偏移，负调整删除的日尾标签拒绝；同一所有者处理精确TT点和显式IEEE语义。原17842点加256控制的六个入口按各自适用域核对，均符合预声明分类与残差线；微秒舍入保持在合法源段 | [分项验收](precision-acceptance.md) |
| 西占回归与界推运 | 回归在有限窗口内按实际黄经根选择，停滞日格分段；界推运采用精确弧与半开区间，保留所选界表和时间钥 | [西方占星](western-astrology.md) |
| 西占派生几何与方法选择 | 调波分座、合相，年龄推进点归宫与年度标记，波斯向运排序和截取均先使用未舍入量；时间钥等具名方法在请求边界校验，不静默替换算法 | [西方占星](western-astrology.md#推运返照与主限坐标) |
| 共享等分宿区 | 27星宿与28等分研究宿区按原始双精度值的精确有理数判定半开区间；消除40°、90°等整边界落前一宿及同次印占字段冲突，不更改具名不等距宿界 | [算法覆盖](algorithm-coverage.md) |
| 派生交点 | 南交／Ketu的精确对点关系保留到分座、分盘、星宿和归宫；公开经度仍为浮点显示值，不增加原坐标的物理精度 | [西方占星](western-astrology.md) · [印度占星](jyotish.md) |
| 六爻条件传递 | 本位金化巳的长生／回头克资格未明时，伏神受生门槛和生扶来源保留待决；已确认阻断及月破日克无根门槛分别核对 | [六爻审计](liuyao-depth-audit.md) |
| 卜卦事件序列 | 停滞、成相的根区间决定能否严格排序；重叠及提问边界保留未知，不由局部模式直接断成事 | [西方占星](western-astrology.md) |
| 印占六力 | 确定量与未裁定项分列；未知星战胜负不抹掉可确定的绝对量，Cheshta双分支仅精确同值时交付共识值 | [印度占星](jyotish.md) |
| 太乙异本 | 阴37／43／44并列《金镜》与米泽藏《武经》六字段，保留原分歧、原图身份与比较范围，不以异本替换默认算法 | [太乙异本](taiyi-sanshi-audit.md#阴374344局的具名版本书影旁证) |

公开盘式的名称可能含版本号或 `legacy`；它们表示明确选择的盘式。当前领域服务不依靠退役源码回放或旧输出哈希判断正确性。

## 仍未通过的项目

2026-11-11的[历法边界核对](calendar-boundary-audit.md)修复了辅助年份、UTC标签和流月完整瞬间的实际故障。固定4392个Temporal算术案例与336个原生求根比较符合各自预声明门槛；未把同源星历或未来钟时假设写成全范围物理精度认证，以下未通过项保持。

2026-11-11补核[八字离散规则与日序](bazi-relations-audit.md)：固定第三方表的十神、藏干、长生与时支相符，纳音两项名称修正后60项相符；五合输出改为相合与候选化神。两套独立实现的1900—2100年73,414个民用日序相同，标准路径相同；原偏移路径全部不同，已退役并保留全部原差异。这些结果未消除下表的八字力量与取用缺口。

| 范围 | 必须保留的分歧或缺口 |
| --- | --- |
| 八字 | 367记录／321不同输入的工程政策与原标签比较仍17组不同，3个集合约束仍2项违规。123条有三档来源的记录尚无通用原典力量裁定，单列未验收；244条无三档来源不算相符。17组原页已复读，语义疑点与缺少充分规则分别保留，不改原标签或借未知消除旧分歧 |
| 原版及更广Moshier太阳范围 | 原版Swiss Moshier的96点中12项仍超原1秒线，保留为原模型失败。当前完整修订在已验收内部范围零超差，更广原队列仍15项超1秒；不以修订身份混报原版或全时域通过 |
| UTC来源与表示的剩余资格 | 原浮点54失败及原始参考保持不变；同输入在修正后的普通UTC有效域另验，50项唯一、3项不可表示、1项域外，当前入口与源分类相符。负调整删除的两个原输入现拒绝。原506点仍有76项不可表示和4项UTC前未裁定；其中4个旧可表示点落入不超过3纳秒的源模型缝隙，继续未知。未以微秒显示、C04插值或原生库一致证明历史物理钟时精度 |
| 原生近太阳约定与压缩月球来源 | 原native水星透明日盘约0.892角秒差及Swiss月球约0.002607角秒／来源日日速超差保留。显式不透明太阳坐标的原7070七曜位置及新增9点过原0.02角秒线；完整DE441精确源的原135个可评月球样本及新增12点满足原0.002／0.02线，原2项缺证不改判。参见[分项精度验收](precision-acceptance.md) |
| 解析回退的全范围位置与数值稳定性 | 当前完整TT导数重跑原40380位置、36140现代日速及固定2560／1280留出，均符合原外部线；240新导数留出加10原诊断点符合独立90位完整映射的1e-6角秒／TT日线。旧两模板仍36139／36140符合，土星原失败保留；其解析日速与局部参考相符，但最大与原Swiss位置0.02日五点参考的差增至约0.407150角秒／日，不能据此称全部更接近第三方或SOTA。太阳盘内13项导数消减失败已修复；旧ERFA二进制8项与更高精度参考的分歧不改判。全部原参考与门槛保留 |
| 奇门 | 核心51个函数及7个局部定义已逐体审读；共享地盘／领导星门并修复太阳标签错取时柱，来源现逐卷固定。共享农历和日干支73414个民用日期七字段与Sxtwl相符；独立程序38组完整排盘仍8组定局不同。原表2格差异与全部9项来源未决保持，完整原典与SOTA尚未通过 |
| 太乙 | 全144局环路与两算算术有条件证明；原《金镜》11个两算、3个始击位置分歧保留。源位置重算解释阴43／44两项，却在阴37新增冲突，净多1项相符、仍10项不同；不据数学约束冲突裁定版本优先级 |
| 金口诀 | 原64课仍46合、16异、2缺日；已知部分约束不能恢复唯一日期或通过整课验收 |
| 河洛与参评 | 月表来源冲突、部分文字、百刻现代日期原点及完整取用仍有未定前提；具名计算方案不代表全书已裁定 |
| 印占 | Moon／Mercury部分原文口径及完整Cheshta来源模型未统一，不拼接作者或制造阈值得出唯一完整六力总分 |
| 风水地磁与玄空 | WMM2025精确WGS84内核在固定2564输入的17948分量上有独立多项式与Arb舍入证据；原12点84项仍相合，原100点末位差异由旧实现354项变为325项，原C常数口径另有340项差异，均保留；见[主场求值](precision-acceptance.md#wmm2025的精确wgs84主场求值)。玄空216项下卦比较的3项正文及1项盘图分歧、书影补证分别保留，不作全书通过 |
| 人类图完整原队列 | 原生Swiss位置1项及Moshier诊断2238项超差仍保留；显式太阳点质量模型在全部原24000固定TT位置符合原2角秒线，最大0.038386角秒；候选全部1200设计根在原5秒线内，最大0.055442秒；自身根位置24000项在原2角秒线内，最大0.053665角秒。原典模型优先级未定。原生两侧各1200根符合原5秒线；官方文字与完整解释仍未通过 |
| 物理精度与现实效度 | 近太阳视位置、后端有效范围与时标须按实际回执评估；分数、传统判断和可复现性均未建立现实预测认证 |

上述数字属于已登记的固定资料范围，不能推广成整个体系的准确率。未读取、缺失或未裁定的项目保持未知；原始失败、参考与门槛不能通过清理改判。

## 余项验收与独立检出对账

本节是2026-11-25的目录与发布状态快照，检出基点为 `c63968b5fe11b59e24a37d8aec4bd2c3d87751ed`。上文历史成绩没有在本单元重新认证。核对使用本工作树的已跟踪文件及GitHub实际PR头；主审计原件保持只读，其他工作树的本地资料和测试结果没有进入本单元。存在驱动、测试或PR不能代替对应原始资料、独立书证或现实结果。

该基点实际有 `scripts/evaluation/`、`tests/evaluation/` 和 `docs/examples/prediction-study/{plan,forecasts,outcomes}.json`；示例是三个虚构主体、空预测及空结果。按 `git ls-files` 计，`tests/data/`有149个已跟踪文件，`tests/fixtures/`有56个已跟踪文件；研究正文提及的 `tests/data/meihua/weather_evidence`、`tests/fixtures/meihua-prospective-v1`、`tests/data/bazi_disagreement_review_v1` 及多组书证目录没有随该检出提供。不能据驱动文件存在声明这些历史研究已经重放。资料闭包和旧缺参考链接由单元22处理；本单元不重建原件、不改分母、不以合成数据补历史证据。

### 首批PR的实际头

2026-11-25 11:00 UTC查询时，PR193–203均为OPEN，`mergedAt=null`，远端master仍为上述基点。下表仅登记发布身份，没有在本单元检出或验收这些头；打开的PR不属于master已交付行为。

| PR | 范围 | 查询到的完整头SHA |
| --- | --- | --- |
| [193](https://github.com/thomas-yanxin/FateBridge/pull/193) | 通蓍法显式输入 | `d44349012fb4dac3bc80fcf2dee8d4db08820e29` |
| [194](https://github.com/thomas-yanxin/FateBridge/pull/194) | profile交付 | `c1a855346d0138baaa78294df931e8c2d101eb51` |
| [195](https://github.com/thomas-yanxin/FateBridge/pull/195) | 西占时主ASC资格 | `d7772e5055894e046cdf983d66c627d00f5ff8ef` |
| [196](https://github.com/thomas-yanxin/FateBridge/pull/196) | 太乙始击异本 | `179f7d776558f2911a8f991bd41688a0d8f2e315` |
| [197](https://github.com/thomas-yanxin/FateBridge/pull/197) | 小限／给定年／ZR资格 | `14645211fce145d2fe9cc368850ae9357c20e497` |
| [198](https://github.com/thomas-yanxin/FateBridge/pull/198) | 回归实际黄经根 | `c08da126caf6f9820510eb8587c592018cb96e83` |
| [199](https://github.com/thomas-yanxin/FateBridge/pull/199) | 古典盘角点 | `74ed03547137f286f56f1796cba40fa8500def16` |
| [200](https://github.com/thomas-yanxin/FateBridge/pull/200) | 关系盘角点 | `978eddb8a9ffb3d1f6f738a56ba8aee8e1cdb4a6` |
| [201](https://github.com/thomas-yanxin/FateBridge/pull/201) | 八字分析柱 | `c995e2eef22d1b810fed6ef97e705190a6e875ff` |
| [202](https://github.com/thomas-yanxin/FateBridge/pull/202) | 奇门秒级钟时 | `43440b340a0763529489c0605a50c31993021612` |
| [203](https://github.com/thomas-yanxin/FateBridge/pull/203) | 紫微未知性别流层 | `e54f0dde1a6ad720f1f50f7ec067793c63ae2412` |

### 本批26单元的证据归属

同次查询已发布的本批PR均为OPEN。头SHA为查询快照；后续提交、合并或其他单元的验证须单独核对，不能沿用此表作验收。未查到对应PR表示该时点没有发现发布记录，不判断其他工作树的进度。各行保留批准范围中的原分母与缺口，具体当前结果应读取对应PR及其原回执。

| 单元 | 实际驱动／证据归属 | 保留的门槛、分母或未决 | 查询到的对应PR与头SHA；均未在本单元验收 |
| --- | --- | --- | --- |
| 1 主限／行运ASC | `core/predictive/`；`tests/western/test_western_timing_tools.py` | 6个主限／法盘、4个行运及7个正常盘分别验；依赖#197资格意义 | [213](https://github.com/thomas-yanxin/FateBridge/pull/213) `7f7b7db08d334e3cd8b30f8fa3af06330545930e` |
| 2 近极太阳根 | `core/astro/solar_events.py`；太阳地平测试 | 原53根、23通过及1毫秒线不重定 | [220](https://github.com/thomas-yanxin/FateBridge/pull/220) `97bc5ce6a661d17738d390c0fdde9aa939b34519` |
| 3 停驻／事件排序 | `scripts/western/audit_western_event_paths.py` | 699本体／6质心；旧混合120秒门保留 | 未查到对应PR |
| 4 Lilly强弱／福点 | `scripts/western/audit_western_lilly_{fortitudes,fortune}.py` | 3/7原印完整对照、福点3对−2、6°25′及五度门 | [208](https://github.com/thomas-yanxin/FateBridge/pull/208) `123882a4cc87f3ebc249de4b0f27c30eb90512fc` |
| 5 候时钟时／条件 | `scripts/western/audit_western_election_conditions.py`；候时测试 | 7图、13组、117读数中45差及另17条件差 | 未查到对应PR |
| 6 果老运动源 | `scripts/guolao/audit_guolao_{motion,moshier_motion}.py` | Swiss84/84；Moshier原27/84、后续52/84分列 | 未查到对应PR |
| 7 果老原尺 | `tests/data/guolao/ruler_flint_v1/generate_reference.py` | 210格、七端点差、三组年率矛盾；22635项仅录文算术 | [215](https://github.com/thomas-yanxin/FateBridge/pull/215) `ff3e5070d3a95b3974fe7b436cb37e3b60b5cbf9` |
| 8 八字力量 | `scripts/bazi/audit_bazi_authority.py` | 367记录／321输入、17组差、2项违规；独立人工双读未证 | [216](https://github.com/thomas-yanxin/FateBridge/pull/216) `be3480663b5efb060dc953c8bf098159c2367133` |
| 9 八字合绊 | `core/{stem_effects,timing_strength}.py` | 配对与预算资格分开；有效根力和权重未裁定 | [210](https://github.com/thomas-yanxin/FateBridge/pull/210) `109888c73012dce98229ecfe9fc66eb5bddee1d2` |
| 10 紫微晚子／流层 | `scripts/ziwei/audit_ziwei_limits.py` | 20例2440字段、旧18差；与#203分工 | 未查到对应PR |
| 11 六壬／金口诀 | `scripts/ren/audit_ren_depth.py`、`audit_jinkou_construction_diagnosis.py` | 原64课、46/62；P35/P52第二底本身份仍需核实 | 未查到对应PR |
| 12 太乙长周期 | `scripts/taiyi/audit_taiyi_long_cycles.py` | 720格、33格固定分歧；与#196分工 | [212](https://github.com/thomas-yanxin/FateBridge/pull/212) `be261dbd061c55ad05a7605310f11c10b0b36353` |
| 13 玄空原图 | `core/fengshui/xuankong.py`；[玄空文档](fengshui-xuankong.md) | 216图、3正文及1格原图差；五黄作者口径分列 | [222](https://github.com/thomas-yanxin/FateBridge/pull/222) `feb99c2a259527cbab47891f2476d63b18c1cc5b` |
| 14 参评／河洛 | `src/fatebridge/core/canping_texts.py`、`heluo_yuantang.py`；[数术文档](numerology-audit.md) | 1620格、450缺、47疑；月序未证不推现代日期 | [214](https://github.com/thomas-yanxin/FateBridge/pull/214) `7b28863f75fd60fc6a95ce550b90b862ab70ef75` |
| 15 奇门／六爻 | `scripts/qimen/audit_qimen.py`；[六爻审计](liuyao-depth-audit.md) | 38盘8差、4096装卦证据；效力未定 | [218](https://github.com/thomas-yanxin/FateBridge/pull/218) `5b1f5689fcd73d08b70465facca12d48ece8e6e4` |
| 16 梅花钟界／外应 | `scripts/meihua/`；[梅花文档](meihua.md) | 农历与交节向量分开；跨篇语义未证 | [211](https://github.com/thomas-yanxin/FateBridge/pull/211) `afb1e4bee22f5b8220946350ab7b8744bb1971a8` |
| 17 印占六力 | `scripts/jyotish/`；`tests/jyotish/` | 54关系矛盾、19单元异文、64/96天文及两条月速未收敛 | [217](https://github.com/thomas-yanxin/FateBridge/pull/217) `088e0f361ef33e3f2459d62c8bf75cd4ab842e41` |
| 18 Vimshottari | `tests/jyotish/test_jyotish_dasha_levels.py` | 309/309、27/27仅原范围；印例与深层端点分别核 | [219](https://github.com/thomas-yanxin/FateBridge/pull/219) `bd1a59327195aa096eaf172a91e2d8bcbe971bd0` |
| 19 人类图 | `scripts/human_design/`；[人类图审计](human-design-algorithm-audit.md) | 原严格238/244根、337/338门线；三种模型分别记账 | 未查到对应余项PR；#209属于另一批交付改动 |
| 20 宿曜历史钟面 | `tests/sukuyo/test_sukuyo_historical_calendar.py` | NAOJ/HuTime225日、210差；日期书证不由物理月相裁定 | 未查到对应PR |
| 21 IPIP最小发布 | 批准范围为 `core/psychometrics/`、具名50题计分 | 基点没有该模块或常模材料；常模、中文词义和临床研究未证 | 未查到对应PR |
| 22 资料闭包 | `scripts/run_ci_checks.py`；`scripts/check_docs.py` | 缺Horizons／Ren参考及旧文档链接归本单元；不得放宽数值门 | [224](https://github.com/thomas-yanxin/FateBridge/pull/224) `46dc3960915d3b81a58b873d47e750066192d0d2` |
| 23 Agent交付 | `tests/integration/{test_capability_discovery,test_full_surface_validation,test_result_delivery}.py` | 本地协议、模型行为和部署分列；与#194分工 | 未查到对应PR |
| 24 西占长尾 | `tests/western/test_western_{lifespan,timing_tools}.py` | 具名时间钥／边界／坐标分别核；与#195/#197分工 | [221](https://github.com/thomas-yanxin/FateBridge/pull/221) `d2922f075a929b980ccccd9a065f9064304ae8a3` |
| 25 其余领域边界 | `tests/{astronomy,fengshui,western}/`及领域文档 | 交节、DST、太阳跨日、五黄和关系方法；原例及实际三端分别验 | [223](https://github.com/thomas-yanxin/FateBridge/pull/223) `41213c470369b18779648e05762aa3a13566d9ef` |
| 26 实证协议对账 | `scripts/evaluation/audit_prediction_study.py`；`tests/evaluation/test_prediction_*.py` | 仅合成流程、冻结分母、基线、弃权及负例；现实效度未证 | 当前分支；发布身份见本PR |

PR204–207及209是另一批输出／输入交付改动，不充当上述余项的书证或现实效度验收。所有未决的现实效度、人工双读和常模仍按真实状态保留。梅花原365日前瞻的分析时间仍为2027-11-30 00:00香港时间起的原门槛；其前不解析结果，资料和重放限制见[预测验证](prediction-validation.md#独立检出的资料与复跑资格)。

## 维护与历史材料

当前文档维护现行行为、依据和限制；独立参考、反例及未裁定项保留。逐轮日志、旧算法回放和迁移哈希链已退出当前维护范围。清理与恢复规则见[仓库维护](repository-maintenance.md)。
