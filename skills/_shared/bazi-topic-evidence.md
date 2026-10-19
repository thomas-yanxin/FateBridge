# 八字专题细问的证据读取

专题首次调用前先按已明确任务选择所选工具公开 `evidence_views` 的 `fields`；没有对应任务卡时使用已验证首轮字段并按实际合同补齐主证。事业方向比较选 `direction`，含目标年度安排选 `target_year`；视图名不是请求参数，不能先投影通用摘要再补算本来就需要的依据。六项专项（性格、婚姻、桃花、学业、六亲、子女）与事业、财务、健康同样有稳定预设。实际名称以工具描述／CLI describe 为准，不把本页路径当新增参数。这里是已有专项的深入读取地图，不要求再调用综合八字或收集完整生活问卷。

## 按用户问题补证

| 任务与工具 | 应读取的实际路径 | 怎样用于回答与追问 |
| --- | --- | --- |
| 岗位方向比较：`bazi_career` | `career_analysis.dominant_ten_gods`（含 `top_gods` 每项 `ten_god/weight/career_type/traits/suitable_roles`）、`interpretation_scope`、`career_structure` | 按实际权重一起读并列和次项，`primary_career_type` 只是排序首标签，不等于显著优势；岗位映射是本实现的现代类比，不是能力测评。先比较自主决策、流程责任等用户真实职责，不凭单标签排除另一个岗位 |
| 创业角色／目标年度：同一事业专项 | `career_analysis.entrepreneurship/career_structure/career_timing/timing_context`，及实际返回的标签判据／范围 | “官印相生”“食神制杀”等专项标签先按共现规则线索解释，不升级为古典成格；指数是本工具倾向值，不是成功概率。目标年信号只解释已算时段，空列表不是没有机会 |
| 财星结构、收入与积累：`bazi_wealth` | `wealth_analysis.wealth_stars` 的位置与正偏财权重；`wealth_structure` 的日主强弱、财力、`pattern/notes`；`wealth_style` | 分开说明计算权重、传统结构与现实收入安排；权重不是收入金额，正偏财标签不是投资建议。用户追问“为什么这样说”就引用已保留位置与结构，不再排一次盘 |
| 明确问财库：同一财务专项 | `wealth_analysis.wealth_storage.has_storage/storage_hits/summary`，条目含 `pillar/branch/stores/opened` | `opened` 只表示本命地支是否匹配本工具的冲库规则。说明实际库支与冲关系，不将“开库进财／易得大财”模板直接交付为发财或置业预测；未带库也不代表不能积累。问哪一年时才读取已返回 `wealth_timing/timing_context`，不从静态 opened 编年份 |
| 学习方式与专业比较：`bazi_education` | `education_analysis.study_stars`、`wenchang`、`subject_orientation`、`suggestions` | 核对印、食伤等实际权重、文昌命中柱及 `conditional_elements/reference_scope`。科目是文化类比，不能直接指定专业；对照用户已给的兴趣、课程与表现。`education_level.score/tier` 不作为智力、学历上限或录取概率 |
| 考试阶段：同一学业专项 | `education_analysis.exam_timing.timing_signals`、`timing_context` | 只解释实际规则命中和所算年度。空列表只表示专项未命中；要独立时间补证按共享时间选择，不反复重跑相同大运流年，也不编某月会发挥更好 |
| 原生家庭与支持：`bazi_relatives` | `relatives_analysis.parents/siblings/palaces/support`；实际父母星权重、年／月柱关系和 notes | 这是命主视角的传统对应，不能补家庭史、判断家人品行或认定亲情强弱。问具体双方互动时需要双方事实／双人结果，不拿单人的父母星当另一人的命盘 |
| 子女对应与相处：`bazi_children` | `children_analysis.interpretation_scope/gender_basis/child_star/child_palace/affinity/relationship/children_timing` | 先说明命主视角；时柱、对应星位置与实际关系条目支持传统说明。`affinity.score` 不作亲子好坏判决，`relationship.achievement` 不推孩子成就。孩子本人学习用孩子资料；不交付数量、性别、生育能力与结局预测 |
| 性格特点：`bazi_personality` | `personality_analysis.core_nature/dominant_traits/disposition/strengths/weaknesses/advice` | 用实际主导十神、权重与强弱条件说明不同倾向；传统“仁义／诚信”等不能认定道德、信用或心理诊断。问阶段变化另接时间层，不靠静态性格编年度变化 |
| 单人婚恋／桃花：`bazi_marriage`、`bazi_romance` | `marriage_analysis.spouse_star/spouse_palace/marriage_quality/marriage_timing/risk_factors`；`romance_analysis.gender_basis/peach_blossom/hongluan_tianxi/opposite_sex_star/peach_quality/romance_timing` | 先保留实际性别规则与传统分类；单人结构不证明另一人心意、外貌或行为，风险模板不能变成出轨、疾病、关系成败断言。时机信号不等于恋爱／结婚必然发生，双人互动须另有双人事实 |

## 必须保留的范围

- 将特征归因“本工具”时，只能转述实际 `career_type/traits/suitable_roles` 等字段支持的含义。压缩句子也不能增加属性：例如劫财字段只写竞争、行动与冒险时，不能改称工具给出“竞争协作”。新增岗位联系须另标为助手的条件式类比，说明用户实际职责如何支持；善沟通、协作、领导等不能由工具未说的内容补成能力判断。
- 所有路径从相应 `<dim>_analysis` 根读取，不能套 `bazi_birth` 或其他专项的前缀；九专项自动时间背景读取各自 `<dim>_analysis.timing_context`，不冒用聚合时间前缀。数组取整个所属字段，再按返回名称选择条目解释，不构造不存在的数组条件投影。
- 八字专项需要已确认出生时刻；不知道就停止同项追问，不填 0／12 时，不用默认值补时柱。已有授权的候选时段结果保留条件差异；不能为问孩子／财库强行产生一张确定盘。
- 专项已自动返回的大运／流年及其规则在同一目标范围与精度内直接复用；交节当日或用户指定小时而专项只算日期零点时，按[共享时间选择](timing-selection.md)补真正所需小时层，不能以“已有流年”阻止边界补证。只补有独立价值的新层。更正资料才重建受影响输入并关联原 trace；只解释已有结论、或用户要求不重算时不重新计算。
- 普通首轮选最贴问题的两三条事实，详细请求才展开本表相应分支。完整 JSON／全部时间线首次 `fields=null`，保留默认预算、读取同一 run；投影遗漏不能靠分页恢复。
- 输出有传统标签并不等于可直接交付：生死、疾病、临床、医疗择时与生育结局先按[硬边界](safety-boundaries.md)处理；财务与教育建议要能由现实条件独立核对。

## 格局、扶抑与调候分别取证

需要解释整体取用时，`analyze_destiny` 取完整 `structure_profile`：先核对 `dominant_structure/recognized_structures` 的 `formation_status`，再读 `layers` 每层的 `source/status/useful_elements/avoid_elements`、`conflicts`、`conditional_elements` 与 `limitations`。`decision_basis` 的概括不得覆盖明确的候选状态；单凭 `useful_elements` 不能还原全部条件。无需此层时不为普通岗位问题追加综合八字。

- 月令格局用神是所声明格局规则中的取用对象；扶抑是本引擎依据强弱作的 `heuristic` 参考；调候简表是日干、月支查得的 `reference_only` 干支。三者不是同一问题、不能互换，也不因同名“用神”而合成补元素处方。
- `pattern_candidate` 或 `candidate_only` 只支持说明“哪些十神组合被识别为线索”。事业专项共现标签与综合格局候选不必同名，不相同也不等于计算错误。没有根气、位置、制化、破格及救应的已验证判断，不能写“已成食神制杀格，所以适合创业”。可以据实解释“本规则检测到食神与七杀并见，提供输出与约束如何配合的讨论线索”，再对照真实工作。
- 同一元素在扶抑与格局候选中一支持一反对，分列支持／反对来源及各自条件，不选一个列表宣布永久喜忌。调候干支已透、藏与是否需要新增也分开；简表没有判断剂量与原局已否调和。

### 原典与现代解释的来源层

术语核对版本：沈孝瞻《秘本子平真诠》，书影封面题“上海世界图书馆发行”（PDF1），国图藏本 `NLC416-11jh010455-35296`。冻结书影 SHA-256：`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`，PDF页序自1起。

| 原典定位 | 本页采用的解释范围 | 不由该出处支持的内容 |
| --- | --- | --- |
| 〈论用神〉印刷17页／PDF26 | 用神从月令取，顺用逆用有不同配合；不能统一解释成补足元素 | 本工具的扶抑计权、现代行业名单 |
| 〈论用神成败救应〉印刷19–21页／PDF28–30 | 成败须审四柱配合，书中逐格举身强弱、根、位置与救应条件；十神共现不足以直接成格 | 事业倾向指数、共现加分或岗位能力评价 |
| 〈论相神紧要〉印刷30页／PDF39 | 相神是辅佐用神成局的关系，不与用神混称 | 把某元素直接变成职业或行动处方 |

这组原典只核对所列术语与条件，不为所有引擎规则背书。`career_type/traits/suitable_roles` 及创业计权属于 FateBridge 的现代规则／岗位类比，回答时将“本工具的类比”与“传统结构解释”分开；用户兴趣、经历、岗位权责和资金条件是现实建议的独立依据。
