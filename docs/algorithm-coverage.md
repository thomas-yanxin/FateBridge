# FateBridge 算法与能力覆盖矩阵

[文档中心](README.md) · [核心概念](concepts.md) · [API 参考](api-reference.md)

当前采用的方法版本、已知分歧和未验收范围见[算法状态](algorithm-status.md)。工具清单与实现范围以本页及中央目录为准；代表性回归和来源对照不等于全部子算法的完整专家认证。

一项工具是否适合当前产品或咨询任务，取决于实际计算范围、数据依赖和精度。下表按 MCP 集合逐项列出工具与实现状态，说明可以使用的能力、近似路径与未覆盖内容，便于在接入和解读前核对。

输入参数查 [API 参考](api-reference.md)，按用户问题选工具查[工具覆盖](algorithm-coverage.md)。

查找体系、方法和适用场景先看[分类与方法矩阵](#分类与方法矩阵)；核对接口再看[总览](#1-总览13-个-family--92-个工具)和[工具清单](#2-逐-family-工具清单)。评估结果精度再看[依赖说明](#3-精度与依赖说明)与[快照覆盖](#4-快照协议覆盖)。八字和双人模型的版本分别见[八字判定](bazi-assessment.md)、[双人评分](compatibility-scoring.md)，风水规则见[家居风水](fengshui.md)。

状态分类：

- `Implemented`：仓库内已有实现，可通过中央目录声明的接口访问；不代表所有端均有同名入口，也不代表预测有效性已被验证
- `Approximate`：可用，但算法明确是离线近似、轻量近似或依赖回退路径
- `Partial` / `Limited`：已实现明确子集，仍有未覆盖、未裁定或未验收的规则；具体范围以各行和领域文档为准
- `Placeholder`：合同或模式入口存在，但主输出层仍是占位兼容
- `Excluded`：当前仓库不提供该能力

> 工具的唯一信源是中央目录 `src/fatebridge/services/tool_catalog.py`。REST 公开 **91 个工具**，MCP 公开 **92 个工具**，分为 **13 个 family**。本页按 MCP 集合统计；目录有 93 条记录，CLI 可执行 92 条，差异见 [API 参考](api-reference.md#24-三端能力边界)。下表逐 family 列出全部工具；新增能力时请同步本页（总数、逐 family 数量与完整工具清单由 `tests/quality/test_doc_tool_counts.py` 锁定）。

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

## 分类与方法矩阵

本表按体系与使用场景整理，不按接口数量计数；一项方法可能包含多个工具，也可能只是工具中的一种模式。`Implemented` 表示所列计算路径存在，`Partial` / `Limited` 表示限定子集，`Approximate` 表示存在明确近似或回退；均不表示全流派、完整原典或现实预测效力已获认证。实际使用时还须核对输入、规则版本、后端和返回的覆盖状态。传统解释供自我探索，不是心理测量、临床诊断或现实决策的可靠预测。

| 大分类 | 具体计算方法 | 实现程度 | 适用场景 | 主要限制 |
| --- | --- | --- | --- | --- |
| 八字 | 四柱命盘、日主、五行、十神、旺衰、喜用与格局 | Implemented，限定规则 | 按出生资料排盘，探索传统命理结构 | 结果依赖历法、出生时刻与所选判定模型；不等于完整流派认证 |
| 八字 | 字面四柱与登记原典编释比较 | Implemented，限定材料 | 核对已知四柱与来源说法 | 不从四柱反推生日；冲突及未知保留 |
| 八字专题 | 事业、行业与创业倾向 | Implemented，限定模型 | 讨论传统事业主题 | 类别或评分不是职业成功概率 |
| 八字专题 | 正偏财、财库与求财方式 | Implemented，限定模型 | 探索传统财务主题 | 不预测收益，不替代财务决策 |
| 八字专题 | 婚姻、配偶星与配偶宫 | Implemented，限定模型 | 探索婚姻与相处主题 | 不保证婚期或关系结果 |
| 八字专题 | 桃花、红鸾、天喜与正缘 | Implemented，限定模型 | 探索恋爱主题 | 象意不证明具体对象或关系结果 |
| 八字专题 | 日主心性、十神性格 | Implemented，限定模型 | 探索传统性格描述 | 不是经验证的心理测评或人格诊断 |
| 八字专题 | 印星、食伤、官星、文昌与学业 | Implemented，限定模型 | 探索学习和考试主题 | 不保证学历、考试结果或时间 |
| 八字专题 | 子女星与子女宫 | Implemented，限定模型 | 从命主视角讨论传统家庭象意 | 不推断子女数量、生育能力或生育时间 |
| 八字专题 | 父母、兄弟姐妹等六亲星宫 | Implemented，限定模型 | 探索家庭关系的传统象意 | 不代替对亲属真实情况的了解 |
| 八字专题 | 五行权重、寒暖与传统健康名称 | Implemented，限文化解释 | 了解传统身心文化分类 | 不提供疾病风险、临床诊断、治疗或医疗择时 |
| 八字时运 | 大运与交运 | Implemented，限定历法和换算口径 | 查看阶段及交运边界 | 依赖出生与节气时刻；不证明事件应期 |
| 八字时运 | 流年、流月、流日、流时及综合时运 | Implemented，限定规则 | 查看岁运关系、原典根类、单层冲刑及唯一大运干五合对原局既有预算的投影 | 运干数值作用只限大运非日干唯一配对；其他时间层干合及未解会合阻塞；完整旺衰、制化和应期未覆盖 |
| 历法 | 节气时间轴、年度节气、农历与干支 | Implemented，精度依赖模型 | 排盘前的时间换算与边界核对 | 不同历法、时区和后端范围不同；时间分辨率不等于物理精度 |
| 历法 | 经度与均时差真太阳时修正 | Implemented，按入口支持 | 所选规则需要太阳时的排盘 | 依赖地点和明确时钟口径；不能猜未知生时 |
| 双人关系 | 八字双人配合 | Implemented，限定评分模型 | 探索婚恋或合作中的两人互动 | 分数不是成功概率；不等于多人团队模型 |
| 双人关系 | 宿曜二十七宿、三九之秘法相性 | Implemented，限定历法与规则 | 查看两人宿曜关系 | 日期参考和规则口径影响结果；不认证现实相容性 |
| 紫微斗数 | 本命十二宫、星曜、五行局与四化 | Implemented，版本化规则 | 排本命盘、核对星宫结构 | 软件基线与部分原典摘录各有范围，并非全书或全部流派 |
| 紫微斗数 | 大限、小限、流年、流月、流日、流时与动态四化 | Implemented，限定运限规则 | 查看不同时间层的宫位和四化 | 不包含全部流曜或飞宫体系；注意本命与运限宫位角色 |
| 紫微斗数 | 规则查询、三方四正与部分童限 | Implemented，限定证据 | 追溯规则与盘内结构 | 童限及原典分歧仍有未认证范围 |
| 奇门遁甲 | 时家转盘、置闰、拆补、寄宫与格局证据 | Implemented，限定规则 | 明确起局后查看盘式与传统象意 | 原典仅片段验收，现实预测未验证 |
| 大六壬 | 天地盘、四课三传、天将、九宗门、关系与空亡证据 | Implemented，部分原典核对 | 起课与核对课内结构 | 取传对照不认证全部神煞、有效空亡或综合断法 |
| 大六壬 | 农历虚岁行年与分析时刻课 | Implemented，限定范围 | 查看行年及其关联课 | 不含逐流月预测 |
| 太乙 | 年计、月计、日计、时计，阴阳局、五将与部分门法 | Partial | 指定计法起局和技法核对 | 各计法仅支持声明的规则与历法范围，原表和案例分歧保留 |
| 太乙 | 指定历史年计 | Partial，限定历史历表 | 核对受支持的历史年计 | 仅覆盖指定年代及历表，不认证完整古历或古日计 |
| 金口诀 | 四位、用位、空破、动法、部分旺衰、课钤与三合 | Implemented，限定规则 | 起课并核对已登记的结构证据 | 部分课钤未决；完整合化、综合取用未裁定 |
| 三式合参 | 太乙、六壬、奇门分层与部分位置对应 | Partial | 比较三式各自证据 | 四维寄支及完整联合断法未校定；不能把同一事实重复当独立证据 |
| 易学 | 六十四卦查询与批量卦义 | Implemented | 查阅卦象及登记的卦义 | 知识条目不等于具体问事结论 |
| 梅花易数 | 时间取数、体用、互卦、变卦、季令 | Implemented，有限原典规则 | 明确起卦后的结构分析 | 不同日界及原文语义可能有分歧；预测未证实 |
| 梅花易数 | 物数、声音、尺寸、字占、端法、报数及既有卦 | Implemented，限定起卦法 | 按明确提供的起卦材料计算 | 缺项不补猜；取爻和原文分歧需查看回执 |
| 易学 | 统摄四卦组合 | Implemented，限定组合规则 | 根据给定四卦计算左右卦、潜藏与亲和 | 不实现蓍草十八变或大衍随机起卦；固定默认不是用户起卦 |
| 六爻 | 纳甲、动爻、日月关系、伏神候选与部分原文规则 | Implemented，限定规则 | 查看卦爻结构和部分取用证据 | 总旺衰、完整应期和现实预测未验收 |
| 数术 | 邵子参评数／金锁银匙 | Implemented，限定数算口径 | 查看取数与年序 | 原典分支、历法和现实预测仍有未决范围 |
| 数术 | 河洛理数、取数、元堂、卦序与部分节候 | Implemented，限定规则 | 查看数算轨迹、卦序及原文参照 | 原典注文、历法、规则分歧及完整预测仍未验收 |
| 宿占 | 二十七宿、宫足及宿占 | Implemented，限定参考历法 | 查询个人宿位及传统对应 | 不同参考历法、日期边界和覆盖范围影响结果 |
| 占星骰 | 星体、星座、宫位骰面与部分符号规则 | Implemented，限定规则 | 已有骰面时解读符号 | 骰面解释和实际天象分层；现实预测未验证 |
| 西方占星 | 核心本命盘、行星、宫位、相位与部分古典规则 | Implemented / Approximate，依赖后端 | 查看本命结构与传统解释 | 星历、宫制、输入时刻和实际后端影响结果；部分路径可近似回退 |
| 西方占星 | 希腊盘 | Implemented / Approximate，依赖后端 | 查看所提供的希腊盘式 | 并非希腊占星全部方法或原典认证 |
| 德国占星 | 22因素、253中点轴、90°／45°对称、太阳弧 | Implemented，依赖 Swiss | 探索中点几何及指定时刻推运 | 完整原典与现实效力未验收；太阳弧是符号推运 |
| 自定义星盘 | 以上升为起点的13等分扇区 | Implemented / Approximate，依赖底盘 | 研究等分扇区位置 | FateBridge 自定义规则，不是 IAU 星座边界 |
| 西方关系盘 | 比较盘、组合盘、相互影响盘、时空盘、Marks盘 | Implemented / Approximate，依赖底盘 | 比较两人盘或派生关系盘 | 不同模式含义不同，不能把结果视为关系成功概率 |
| 西占推运 | 太阳返照、月亮返照 | Implemented，依赖后端 | 查看日月回归时的盘 | 精度取决于星历和时地点；不是事件保证 |
| 西占推运 | 行运、太阳弧、指定年盘、年小限 | Implemented，依赖后端 | 按目标时间查看不同推运方式 | 各方法口径不同，不应把符号时间当实测事件 |
| 西占推运 | 主限与主限法盘 | Implemented，声明近似／坐标策略 | 查看主限方向与命中 | 实际坐标和近似策略须随结果核对 |
| 西占推运 | 黄道释放、法达星限、十年星限 | Implemented，依赖后端 | 查看传统时主与阶段划分 | 年长、夜盘等口径可改变边界；不认证事件应期 |
| 西占推运 | 综合推运总览 | Implemented，依赖后端 | 在一次结果中查看所选推运 | 汇总不使方法互相独立或提高预测效力 |
| 西占阶段技法 | 调波盘、行星年龄、三分主星、月相推运 | Implemented，依赖后端 | 研究本命盘的周期或阶段 | 具体定义和适用范围以各工具为准，不能据此推断寿命 |
| 西占阶段技法 | 界推运、Balbillus 129年系统、129年系统 | Implemented，依赖后端 | 研究传统分期 | 不同系统不可直接视为同一方法；不推断寿命 |
| 西占阶段技法 | 数字相位、行星弧、波斯向运、年龄推进点 | Implemented，依赖后端 | 研究不同方向与年龄推进 | 符号技术并非对实际事件时间的验证 |
| 西占阶段技法 | 恒星推运、赤纬推运 | Implemented，依赖后端 | 研究相应坐标推运 | 依赖具体坐标和后端，不证明现实预测 |
| 事件占星 | 世俗入宫盘、多重回归 | Implemented，依赖后端 | 计算指定事件或回归盘 | 依赖天文求解、输入时区及所选口径 |
| 事件占星 | 卜卦占星 | Implemented，限定规则 | 根据明确提问时刻研究卜卦盘 | 部分容许度和宫位规则已核对；完整判词与判断资格未验收 |
| 事件占星 | 择日占星 | Implemented，限定规则 | 比较明确候选时刻 | 不保证现实结果；不得用于医疗择时 |
| 印度占星 | Lahiri 九曜、星宿／Pada、宫主、尊贵与相位 | Implemented，依赖 Swiss | 查看所选印占本命结构 | 部分原典分支未决，时区、生时和星历影响结果 |
| 印度占星 | D1、D2、D3、D7、D9、D10、D12、D30 分盘 | Implemented，限定规则 | 查看受支持的分盘 | 边界对生时敏感；并非全部分盘或流派 |
| 印度占星 | Ashtakavarga 八分法、削减与 Pinda | Implemented，声明占据及来源口径 | 查看分值表与削减链 | 原文缺项和不同来源分支保留；计数不是事件概率 |
| 印度占星 | Vimshottari 出生余运、主运、次运及可选更深子期 | Implemented，依赖 Swiss | 查看达沙周期和子期 | 年长口径与生时影响边界，细分不代表事件精度 |
| 果老星宗 | 七政四余、研究宿界、宫主／度主、部分小限 | Implemented，需 Swiss | 研究星位、宫度与指定时刻 | 完整流年、原典全盘及现实效力未验收 |
| 人类图 | 88°设计时刻、双侧激活、门／线／Color／Tone／Base | Implemented，限定机制 | 生成双时刻激活与细分 | 生时和实际星历影响边界；细分不代表健康或认知机制已验证 |
| 人类图 | 九中心、36通道、类型、策略、权威、角色、Variable、交叉与桥接 | Implemented，限定规则 | 查看图结构及其传统术语 | 原典存在数值和口径分歧；完整解释及现实预测未验收 |
| 人类图 | 土星回归、天王星对冲、凯龙星回归的有限搜索 | Implemented，限定搜索 | 查看指定评估时刻附近的周期交会 | 有限搜索不保证穷尽，也不证明现实事件 |
| 风水 | 后天八方、洛书宫数、24山方向索引 | Implemented | 将已确认方位映射到宫位或角区 | 方向索引不等于完整24山断法 |
| 风水 | 命卦与个人八方关系 | Implemented，版本化规则 | 查看个人方位关系 | 须核对出生年界和所选规则；不是现实成功率 |
| 风水 | 八宅坐山宅盘与逐人命盘 | Implemented，版本化规则 | 按实际坐向讨论位置与朝向 | 位置和朝向用途分开；现场事实不由软件猜测 |
| 风水 | 金锁玉关八宫固定砂水 | Implemented，限定来源 | 审查已确认的环境砂水特征 | 形态距离、元运等未覆盖；照片只能保留候选 |
| 风水 | 年度紫白与立春区间 | Implemented，依赖节气模型 | 查看年度九宫星位 | 交节后端可能近似；星位不证明现实结果 |
| 风水 | 十二节月紫白 | Limited | 查看月星位置及固定释义 | 未实现月星布局处方或年／月叠加断事 |
| 风水 | 中州派玄空历史定运、下卦与兼向替星 | Implemented，限定规则版本 | 计算所选山向与运的宅盘 | 他派及全部历史规则未认证；保留外部盘例差异 |
| 风水 | 多层布局、室内关系、家具候选与条件式方案 | Implemented，限定登记规则 | 根据已确认事实比较空间方案 | 缺失事实、未覆盖规则与动作可行性分别保留；不自动完成户型几何 |
| 基础能力 | 内置知识域目录及条目读取 | Implemented | 查询八字、占星、六壬、奇门知识 | 知识覆盖不等于整个领域完整；需核对具体来源 |
| 基础能力 | 快照解析、导出协议与章节筛选 | Implemented，按工具合同 | 阅读、集成或导出计算结果 | 快照、导出及筛选并非每个工具都支持 |

各方法的逐接口名称、技术依赖和具体验收情况见下文及对应领域文档。尤其须区分计算可复现、原典一致性、解释质量与前瞻性现实预测验证；它们不能互相替代。

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
| `western_lifespan` | 13 | 传统阶段与周期技法（保留内部 family 名称） | Implemented（依赖 backend；不用于寿命推断） |
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
| `bazi_marriage` | 配偶星／宫及传统关系信号，不保证婚期或婚姻结果 | Implemented，限定规则 |
| `bazi_career` | 事业：事业类型、行业、创业倾向、贵人方位 | Implemented |
| `bazi_wealth` | 财运：正偏财、财库、求财方式/方位、破财风险 | Implemented |
| `bazi_health` | 传统健康文化：盘内权重／寒暖分类和传统名称对应；疾病风险禁用，不作体质诊断或调理处方 | Implemented |
| `bazi_children` | 命主视角的子女星／宫传统对应；不推数量、生育能力或生育时间 | Implemented |
| `bazi_education` | 印星／食伤／官星、文昌与传统学业信号，不保证学历或考试结果 | Implemented，限定规则 |
| `bazi_personality` | 性格：日主心性、十神性格、刚柔内外向 | Implemented |
| `bazi_relatives` | 六亲：父母/兄弟姐妹星、六亲宫位、贵人 | Implemented |
| `bazi_romance` | 桃花咸池、红鸾天喜等传统关系象意，不确认具体对象或相遇时间 | Implemented，限定规则 |

八字11个出生资料入口与七个时运入口可接收已知整秒，提供秒数时须显式提供分钟；出生上下文保留省略分量与兼容00值，见[出生秒数与输入分量](bazi-timing.md)。这是输入传递能力，不认证真实出生记录精度，也不提高原典或现实预测的验收等级。

上述入口可用已确认的 `birth_utc_offset` 消歧重复民用钟时；偏移须匹配已解析时区，未来交运保留原IANA地区规则。未知选择和跳过钟时继续拒绝，见[重复钟时审计](bazi-timing.md)。

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
| `tongshefa` | 按给定四卦作统摄组合；不实现大衍随机起卦 | Implemented，限定组合规则 |
| `sixyao` | 六爻纳甲分析 | Implemented |
| `canping` | 邵子参评数 / 金锁银匙（数算） | Implemented |
| `heluo` | 河洛理数（数算） | Implemented |
| `suzhan` | 宿占分析 | Implemented |
| `otherbu` | [占星骰](astrodice.md)：十二骰面、七曜星座关系、条件三分性与喜乐宫；可追溯解释与独立天象，现实预测未验证 | Implemented（符号规则） |
| `sanshiunited` | 三式分层证据、五将按实际方位对应奇门星门神，明确地支对应六壬十二神；四维寄支和完整联合断法未校定，见[审计](taiyi-sanshi-audit.md) | Partial |

河洛与参评数提供同次取数轨迹、版本来源和规则状态；固定四柱入口核对干支衔接，原文冲突算例保留形式取数，不计作已验出生盘。参评数默认 `gu` 日支法，显式 `ming` 为月支变法；配运 `reading_context` 保留方法、钟制、书影定位及引用角色。

河洛的元堂、卦序、具名月表、节候、纳甲及条件注文分别给出依据与未决项；百刻相对边界不代替现代日期原点，卷首／卦条五处月号差异和未定文字仍保留。端点节气和参评完整年序消费实际所选太阳来源，派生许可不扩大独立年表范围。现行方法、历法边界和原典定位见[河洛与参评数](numerology-audit.md)，完整原典一致性与现实预测效力尚未验收。

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
| `taiyi` | 《太乙金镜式经》年计及卷五年度十神、六纪节月与冬夏至时计的现代天文适配；阴阳144局两算、七类空间条件、卷四五将合取；年/月定计及[分法八门](taiyi-sanshi-audit.md)，另有明选[金钥匙时计](taiyi-sanshi-audit.md)完整积时与四门，及[金钥匙日计](taiyi-sanshi-audit.md)积日与分源十精；原表与定计课例分歧、古历异单位解释及引文异数保留，见[审计](taiyi-sanshi-audit.md)；显式[历史年计](taiyi-sanshi-audit.md)支持381—385晋历及501—505齐梁史历主表，502年闰标异说随结果保留，未据此认证原典古日计 | Partial |
| `jinkou` | 四位、阴阳用位及受克空破、五动三动、季节与有限课内旺衰、得气、六十四课钤逐条三态判定、四绝及岁日结构、三合齐缺与成员空破条件 | Implemented（58条课钤结构已评估，6条未决，全部64条以true/false/null区分命中、未命中、未判；四败仅临地分，大绝按显式本命支计算、缺命保留未知；支齐不等于合化，完整合化及综合取用未裁定） |

> 紫微斗数以 iztro 2.5.8 为对齐基线，采用正月初一年界、虚岁自然年递增、本命晚子时算当天、闰月后半月算下月的规则。当前冻结 1,080 张本命软件参考盘及 18 个运限用例，分别核对本命星曜／长生博士等和六层落宫／四化；流月/流日/流时比较实际落宫索引，不能用历法地支代替。返回的 `branch` 是实际落宫，`palace_ganzhi` 是本命宫干支，`stem` 是该运限四化所用天干；后两者可能不同。另以 `childhood_limit` 独立返回原文明示一至六岁之命、财帛、疾厄、夫妻、福德、官禄宫及实际本命星曜；后续岁序留空，岁首及大限前替代关系未认证。既有起大限前童限替代与独立童限分别披露；农历日期或大限超出支持范围时明确报错。

> 紫微现另提供版本化 `quanshu_v2_excerpt`（1.3.1 选择闰月、壬年四化、亮度、长生、旬空双支、部分年度流曜、邻宫起大限及火铃年支定点读法，仍非全书认证）、规则轨迹、三方四正证据和六层十二宫功能名映射。新增16星原文属性到本命星位连接，文本化义与实际四化分栏。200年HKO历表、1900年NASA朔日补证、部分明刊书影校勘及三项专业验收范围见[紫微专业能力与验收](ziwei.md)；未知性别的长生／博士仅保留两方向都相同的起点和对宫标记，另有逐宫来源比较；其余位置仍未定。软件对齐不代表全书认证或现实预测已验证。

> 运限的 `natal_prerequisites` 另携带同次内部本命的月时、年干、命身、宫干支纳音与局数推导，供解释局数及起限岁数时直接引用。它核实实际计算之间的连接；公历起算、原典岁首与现实效度仍需分别验收。

> 六壬按九宗门取传，第一课生克使用日干五行，寄宫负责定位；天盘顺布与贵人顺逆分别计算。原独立 daliurenpython 三传参考覆盖720张天地盘，全部12个时支展开为8,640组；原始向量保存在 三传参考（本地 `tests/fixtures/liureng_transmissions_reference.json`），由[当前对照测试](../tests/integration/test_metaphysics_reference.py)读取。此范围只核三传，不认证全部课名、神煞、流派或现实预测。

> 金口诀使用本法地分与贵神固有干支，不借大六壬课体决定取用。四位的季节旺衰、课内旺衰、得气和阴阳用位分别返回；综合用位、完整合化及原典疑文保持未知。64课逐条使用true／false／null区分命中、未命中与未判，原四位重建46相符、16不同、2缺日的完整分母保留。三合支齐不证明合化，命支未给不补造大绝。来源、课钤对照及未决范围见[六壬与金口诀](liuren-jinkou-audit.md#盘面规则与同课条件)。

> 三工具的`calendar_policy`声明输入瞬间、计算钟面、23:00子初换日、实际星历与时间尺度。交气使用TT求解及具名历史UTC／闰秒转换，求解失败不回退线性近似；小数秒是数值分辨率。原3,024个公布分钟标签在原生Swiss、有文件解析和无文件默认配置下分别有21／22／22项超差；4,536组换将边界均符合，同一队列DE440 TT对照在原1秒线内。1901—2100年HKO全部4,800个节气日期在四种配置下仍有原7项差异；日期级来源不替代天文瞬间或强制修改计算交界。原完整日期、失败项及交节当日未定范围见[历法依据](liuren-jinkou-audit.md#完整年表队列与历法依据)。

> IMCCE OPALE三种时间路线分别保留原分母和1秒线：初始504项的原生／解析配置各1项历史UT1超差；文档时间约定244项分别4／3项超差；来源自身钟差换算TT的288项均在该线内。这些比较复用原PMO事件，不能相加为新增独立观测；时间定义、物理模型与分钟标签失败分开报告，见[交气时间尺度](liuren-jinkou-audit.md#交气时间尺度与边界序列化)。

> 六壬分层返回`classification`、`transmission_relations`、`emptiness_evidence`、`branch_relations`、`transmission_progression`、`seasonal_evidence`及`life_stages`。天将与支神生克、三合名义局体、三传初末生墓、空亡角色例外、进退支序及十二运各有实际盘面依据；47项接触、34,560组符号盘和48份金口诀课内参考是有限规则检查，不能当作现实样本。局部不空、支序方向和季节五态不推出完整有效空亡、合化或综合进退。月建五行由`month_building_element`承担，实际十二长生由`life_stages`承担，见[规则说明](liuren-jinkou-audit.md#盘面规则与同课条件)。

> 金口诀`overview.month_general`是中气月将本位，`overview.yuejiang`是月将加时后落在地分的将神；两者是不同事实。`branch_stars`列七项历法目标及三位本支，驿马按月建、天赦比完整日干支；`year_fate`按生年旬、显式岁序及男女起点推导另课地分，不以推导值冒充观测方位。月序、岁首、实际年龄联动与综合效力各自声明未认证范围。

> `diurnal_evidence`区分显式昼夜选择、默认时支约定与未记录的现场星象，固定时支不冒充星出星没观测。引用校验绑定同一run完整业务结果，不能代替自由文本语义验收。原六例真实模型研究首次机械5／6、人工21项中18符合及3覆盖不全的事实保留；当前新增说明未因此取得新的真实模型成绩。完整历法、全原典、独立自由解释与现实效度仍分别未完成，见[验收范围](liuren-jinkou-audit.md#解释忠实与现实预测)。

### 2.6 `astro` —— 离线核心星盘与关系盘（Implemented，精度依赖星历）

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_chart` | 离线核心星盘（`chart_variant` 切换盘式） | Implemented / Approximate（见 §3.1） |
| `astro_chart13` | 上升起点的 13 等分扇区，精确分界；自定义分区，不是 IAU 星座 | Implemented / Approximate（天文底盘依赖星历） |
| `astro_hellen_chart` | 离线希腊盘 | Implemented / Approximate |
| `astro_guolao_chart` | 七政四余连续坐标、不等赤经研究宿界、宫主/度主与规则轨迹 | Implemented（需 Swiss；原典全盘与现实效力未验收，见[果老说明](guolao.md)） |
| `astro_india_chart` | Lahiri 九曜、星宿／Pada、D1/D2/D3/D7/D9/D10/D12/D30、宫主／尊贵／相位、生时敏感性、未削减八分法及声明七曜占据口径的削减／Pinda；另列Aiyar1905自己的原始表与削减链，各具名参考口径分开读取 | Implemented（需 Swiss Ephemeris；原典未决分支保留空值，非预测有效性认证，见[印占范围](jyotish.md)） |
| `astro_vimshottari` | Moon-nakshatra 出生余运、MD／AD完整目标周期、可选2—6层当前路径及逐层子期；三种年长与完整运主链生时网格 | Implemented（需 Swiss Ephemeris；计算范围见[印占说明](jyotish.md)，细分不代表事件精度） |
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

法达支持独立选择夜盘交点顺序和固定年／公历周年口径，默认行为保持；参数与日期边界见[年长与夜盘交点顺序](firdaria-compatibility.md)。

### 2.8 `western_event` —— 事件占星（Implemented，依赖 backend）

求解天文时刻后起盘的一组事件类工具，走 `fatebridge.core.astrology_events` / `astrology_horary` / `astrology_election`。

| 工具 | 说明 | 状态 |
| --- | --- | --- |
| `astro_mundane` | 世俗入宫盘 | Implemented（依赖 backend） |
| `astro_extrareturns` | 多重回归 | Implemented（依赖 backend） |
| `astro_horary` | 卜卦判断 | Implemented（依赖 backend） |
| `astro_election` | 择日 | Implemented（依赖 backend） |

此处Implemented表示接口与计算路径存在。卜卦已逐项实现Lilly1647的两列相位容许度、实际落宫、分别保留的宫位序次／宫位分值及居宫的必要月亮条件；完整偶然尊贵、传光／阻碍与全盘判词仍未验收，`verdict=uncertain`。具体来源与未通过项见[西方占星](western-astrology.md)。判断前审查按第121–123页12项手工清单与报告的例外，四个时主对应例复现；未知月亮晚度、受损定义及整盘判断资格仍保留，不能据此认证现实预测。

卜卦与择日另支持显式儒略历日期，分别通过 `question_calendar`、`candidate_calendar` 选择；日期先按相应闰年规则校验、换成内部格里历，再处理时区。原日期与规范化日期并列返回，默认仍为前推格里历；其他出生／分析入口未据此扩展。地区改历、旧式年份与原典钟时不推断，见[西占历法与方法](western-astrology.md)。

已确认的地方平／地心视太阳时可分别由 `question_clock_basis`／`candidate_clock_basis` 显式输入，不能与民用时区叠加；默认民用钟时及省略时区的旧 `+08:00` 行为保留并标来源。`clock_conversion` 分开输入钟面和物理时刻；太阳时卜卦的行星日按声明钟时的开启日出日期取星期，未借用内部UTC载体的日期。两组复用JPL历元及手工算术只验有限转换，原书钟时鉴定、整图验收和现实预测仍未成立，见[西占钟时](western-astrology.md)。

另以 `question_hour_origin`／`candidate_hour_origin` 显式处理午夜／正午起算的小时标签，支持跨日、世纪儒略闰日和有效终点越过不可表示中间日期。范围先在整数日编号上合并，再建立最终格里历钟面，时区与太阳时在后；没有推断全部历史原图的日起点。所选Lilly1647第30–31页条款及公开JD数例分别核验，1978年元旦UT1的UTC闰秒载体缺口仍列为失败，相关边界见[西方占星](western-astrology.md)。

太阳时反解落入UTC闰秒时，卜卦／择日保留原生TT／UT1继续计算，`converted_utc`可返回含`23:59:60`的标签。`clock_conversion.utc_representation`明确区分UTC标签、闰秒与Python datetime可表示性；不要截断、平滑、移秒或把显示限制说成星盘不可算。仍不推断原资料精度、实测EOP、完整原典或现实预测有效性。详见[西方占星](western-astrology.md)。

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
| `fengshui_annual_stars` | 年度紫白九宫、立春区间、当前元运 | Implemented（交节时刻依赖所选节气模型，求根不可用时明确失败） |
| `fengshui_monthly_stars` | 十二节月紫白、跨年有效年、九宫中性位置与固定释义 | Implemented / Limited（原表36数、独立节气口径；保留原表六月节候倒序，未实现月星用途处方或现实效度认证） |
| `fengshui_xuankong_natal` | 中州派历史定运、24山／三元龙、五黄、下卦与兼向替星 | Implemented（xuankong_zhongzhou_v1） |
| `fengshui_assess` | 多层布局关联、匹配方位、现代作者室内形态、条件式元素/年度方案、分歧与版本 | Implemented（限已登记规则版本） |

布局入口设 `analyze_layout=true`。扩展覆盖包括场景选法与优先审查状态、家庭人物及楼层上下文、12 类明确室内关系、独立材质／器形事实、家具候选比较，以及显式启用的玄空有限解释；只按已确认事实与登记版本计算。照片候选、缺失资料、未覆盖规则和动作可行性分别保留，`complete` 不等于所有方法均已审查或可立即执行。输入与来源详见 [风水输入与来源](fengshui.md)。

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

检查 `chart_profile.engine_precision` / `engine_backend` 确认代码路径，再用 `chart_profile.ephemeris_model` 确认实际模型：`swieph` / `jpl` 为相应数据模型，`moshier` 为内置模型，`mixed` 表示混合。`run_metadata.engine_is_approximate` 会标记已识别的降级。数据获取、路径与版本复现见 [星历安装](ephemeris.md)。

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

卜卦／择日的显式 `ut1_source=iers_c04` 接入固定IERS20 C04日值及TT上连续UT1−TAI线性插值；默认与其他西占入口仍为Swiss ΔT模型。固定覆盖期仅1962-01-01 00:00至2026-09-19 00:00 UTC，不外推。只应用UT1，极移／CIP／日内潮汐、插值物理误差、完整原典、实际模型解释与现实预测继续待验收。来源与限制见[西方占星](western-astrology.md)。

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
