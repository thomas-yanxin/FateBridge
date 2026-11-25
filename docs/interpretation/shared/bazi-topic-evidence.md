# 八字专题细问的证据读取

专题首次调用前先按已明确任务选择所选工具公开 `evidence_views` 的 `fields`；没有对应任务卡时使用已验证首轮字段并按实际合同补齐主证。事业方向比较选 `direction`，含目标年度安排选 `target_year`；视图名不是请求参数，不能先投影通用摘要再补算本来就需要的依据。六项专项（性格、婚姻、桃花、学业、六亲、子女）与事业、财务、健康同样有稳定预设。实际名称以工具描述／CLI describe 为准，不把本页路径当新增参数。这里是已有专项的深入读取地图，不要求再调用综合八字或收集完整生活问卷。

## 按用户问题补证

| 问题 | 先读 | 按需补读 |
| --- | --- | --- |
| 事业与角色 | `career_analysis.evidence_chain.topic.first_view` | `topic.stars` 的官杀、印、食伤和财星位，及 `structure_checks` 的实际前提 |
| 学习 | `education_analysis.evidence_chain.topic.first_view` | 文昌 `topic.markers`、印和食伤的透藏位置 |
| 婚恋 | 相应专题的 `topic.first_view` | 日支 `topic.palaces.day`、传统选星分支和各运年触点 |
| 财务与六亲 | 相应专题的 `topic.first_view` | 具体星位、对应柱位、墓库及关系 |
| 分析时间 | `timing_context` | `topic.timing.layers` 的透藏十神和逐柱触点 |

## 必须保留的范围

- 将特征归因“本工具”时，只能转述实际 `career_type/traits/suitable_roles` 等字段支持的含义。压缩句子也不能增加属性：例如劫财字段只写竞争、行动与冒险时，不能改称工具给出“竞争协作”。新增岗位联系须另标为助手的条件式类比，说明用户实际职责如何支持；善沟通、协作、领导等不能由工具未说的内容补成能力判断。
- 所有路径从相应 `<dim>_analysis` 根读取，不能套 `bazi_birth` 或其他专项的前缀；九专项自动时间背景读取各自 `<dim>_analysis.timing_context`，不冒用聚合时间前缀。数组取整个所属字段，再按返回名称选择条目解释，不构造不存在的数组条件投影。
- 八字专项需要已确认出生时刻；不知道就停止同项追问，不填 0／12 时，不用默认值补时柱。已有授权的候选时段结果保留条件差异；不能为问孩子／财库强行产生一张确定盘。
- 专项已自动返回的大运／流年及其规则在同一目标范围与精度内直接复用；交节当日或用户指定小时而专项只算日期零点时，按[共享时间选择](timing-selection.md)补真正所需小时层，不能以“已有流年”阻止边界补证。只补有独立价值的新层。更正资料才重建受影响输入并关联原 trace；只解释已有结论、或用户要求不重算时不重新计算。
- 普通首轮选最贴问题的两三条事实，详细请求才展开本表相应分支。完整 JSON／全部时间线首次 `fields=null`，保留默认预算、读取同一 run；投影遗漏不能靠分页恢复。
- 输出有传统标签并不等于可直接交付：生死、疾病、临床、医疗择时与生育结局先按[硬边界](safety-boundaries.md)处理；财务与教育建议要能由现实条件独立核对。

## 格局、扶抑与调候分别取证

根气细问还可读取同一`evidence_chain.classical_root_profile`，标准命盘在`bazi_birth.classical.root_profile`。这是《秘本子平真诠》PDF22–23的根类形式化：墓库、余气、禄旺与阴长生参考分列，阴旺同气根不等于阳刃格资格。阴长生有原典轻根参考而无同气藏干时，两条事实同时保留；不得补造藏干，也不能抹去原典异说。`global_strength_status=not_adjudicated`，根类不能覆盖数值旺衰、解释成已判身强或自行追加根损结论。详见[精度深化](../../bazi-assessment.md)。

综合与九专题现有 `evidence_chain`：综合读取 `structure_profile.evidence_chain`，专题读取 `<topic>_analysis.evidence_chain`。需要深入时选公开 `depth` 视图，核对 `ten_gods` 的透藏位置、`roots` 同字／同五行根、独立 `growth_phase_roots`、`financial_seal_positions`、`month_command` 和 `structure_checks`。`prerequisite_not_met` 是本限定规则的具体反证，`pending_adjudication` 仍未裁定成格；不要将 `matched` 的单项条件升级为整体成格。`topic.timing` 是目标生效柱及其天干／藏干、宫位、运年间和合会刑组触点，不是事件或吉凶结论；专题的未知性别只限制大运顺逆，保留本命和独立流年。规则范围与原典定位见[深化审查](../../bazi-assessment.md)。

综合入口 `bazi_overview` 与标准命盘 `bazi_birth_chart`分别按实际结果取证；标准命盘的证据链在`bazi_birth.structure_profile.evidence_chain`，不能把两者的工具验收范围混写。完整业务缺少必需计算依据时是内部输出错误，不能解释成“没有相关星”或改用较弱入口躲过失败；合法字段投影的省略也不是原局缺项。范围见[完整结果校验](../../bazi-assessment.md)。 起运年龄另分同次`start_age_unrounded`折算值、旧名`start_age_precise`的两位展示和`start_age`整数展示。整数沿未舍入值向上取整、至少1岁，不能解释成实际周岁生日；实际交运及运段沿用`start_at/end_at`。未舍入数字不认证出生记录或天文精度，见[起运整数与原值](../../bazi-timing.md)。

需要解释整体取用时，`bazi_overview` 取完整 `structure_profile`：先核对 `candidate_selection.selected_month` 的本气与所选取神、各路径的可观察前提及未知力量条件；`chosen_path_id=null` 时不能指名已选用神或相神。`dominant_structure`现在只是月令主类参考，`legacy_dominant_structure/recognized_structures`保留旧共现候选供追溯，不按旧优先级认证成格。再读 `layers` 每层的 `source/status/useful_elements/avoid_elements`、`conflicts`、`conditional_elements` 与 `limitations`。`decision_basis` 不覆盖明确的待判状态，单凭 `useful_elements` 不能还原全部条件。无需此层时不为普通岗位问题追加综合八字。

- 月令格局用神是所声明格局规则中的取用对象；扶抑是本引擎依据强弱作的 `heuristic` 参考；调候简表是日干、月支查得的 `reference_only` 干支。三者不是同一问题、不能互换，也不因同名“用神”而合成补元素处方。
- `pattern_candidate` 或 `candidate_only` 只支持说明“哪些十神组合被识别为线索”。事业专项共现标签与综合格局候选不必同名，不相同也不等于计算错误。没有根气、位置、制化、破格及救应的已验证判断，不能写“已成食神制杀格，所以适合创业”。可以据实解释“本规则检测到食神与七杀并见，提供输出与约束如何配合的讨论线索”，再对照真实工作。
- 同一元素在扶抑与格局候选中一支持一反对，分列支持／反对来源及各自条件，不选一个列表宣布永久喜忌。调候干支已透、藏与是否需要新增也分开；简表没有判断剂量与原局已否调和。

月令人元司令细问，按对应综合或专题前缀读取同次`evidence_chain.month_command.intra_month_duty`；其`source_reference`分别保留原注日序、任注条件及三命数字条目。先核来源和作者层次，再核明确干的实际透藏；`canonical_stem=null`的原字身份不当成已确认缺少。来源数字的合计差异是待核的数字文本问题，不能改成本命历法错误、自动缩放成30日，或补入常用藏干目录。`selected_stem=null`和`effective_command_status=not_adjudicated`时，仍不能宣称已算定司令或据此重判身强；完整说明见[司令来源分层](../../bazi-assessment.md)。

`source_reference.scanned_witness`另保留CADAL完整书影的月条、原页及章末评议。该见证同有32／26／380的字面合计，不能一概说成OCR错误；也不冒充识典确切底本已核。新读己／己土与旧数字已分别归源。首份人元章中艮土、坤土身份保持未知；附加`cross_chapter_identities`按同书戊土段对读艮土为戊，保留原页、相反脉络及当前月条的实际透藏，坤土仍未指定干。跨章身份不等于分日司令，不能据艮土五日条消去ML02六日戊司令的分歧。月条出现不等于实体藏根或有效司令，不能因此补寅中己、酉中丁，或由“年日時不论”一句删除同次已返回的年日时根。详见[书影见证](../../bazi-assessment.md)。

核对交气瞬间或节后经过量时，沿同次`calendar_context`读取节气`datetime_with_offset`及实际来源；旧`datetime`是兼容本地钟面，重复小时不能仅据它复原瞬间。`fold=1`表示回拨后同一钟面的后一次，不是另一个节气或日期；偏移、时区、太阳模型及历史时标约定须同时保留。精确交付不证明绝对UTC正确，也不自动确定月内司令，见[重复小时审计](../../bazi-timing.md)。

核对实际四墓根力时，标准命盘／综合可选公开`root_effects`字段视图；九专题沿本次`evidence_chain.strength_context.storage_movement_effects`读取已供给的旺衰回执。`null`表示未供给计算，`[]`表示计算后没有这类事件，不能互换。`event_retention_multiplier`仅为本事件系数；其他合绊与刑冲仍会作用，最终损耗系数及实际剩余根量分别在`combined_loss_multiplier/remaining_hidden_mass`。原文区分冲动与冲克，未给0.75等数值；不得把模型系数说成古法定量结论，或由本事件保留土根改称开库、成格。见[四墓土冲动审计](../../bazi-assessment.md)。

### 原典与现代解释的来源层

讨论身、印或身食财力量时，读取公开 `force_components` 视图。 `evidence_chain.force_components`分别保留身、印、食伤、财、官杀的实际藏根、透干位置与同次工程能量； 工程身印总占比高不能改述为原典已经判定身强，印重也不等于身重。 原书PDF73明确区分身重印轻与身轻印重；本表的`classical_adjudication`仍为`not_adjudicated`。 `engineering_composition`中的能量大小只是现有模型的组成比较，未提供时保留`not_supplied/null`，不补算或当作零。 引用`source_star_refs`须同时保留同一run的`ten_gods`；原局藏根不改称刑冲合化后的剩余根力。

“从／假从”与普通身强身弱也分开：原典有取从官却明确“非身衰论”的例子，不能将从格统一转成弱，或由一个根加一比劫自行提为强。实际藏干存在、工程预算存留、原典功能根能否生扶是三条不同判断；未返回完整受生、根损与从格裁定时不补写。来源、整章反例及未采用的实验见[身印与假从审查](../../bazi-assessment.md)。

讨论从儿或食伤生财与普通扶抑冲突时，可读公开`from_child`视图。`from_child_reference`分别保留月干／月支本气锚点、食伤分布、透藏财及印官阻碍；`ordinary_fuyi_requires_review=true`时普通扶抑仅列条件，不能因工程身弱便补称喜印比。从儿不以普通身弱为必要条件，比劫和真实身根也不单独排除；两柱食伤是存在性筛选，不是原典力量阈值。`formation_status=not_adjudicated`不许改述为已从儿，条件食财、条件忌印官也不直接成为全局处方。来源及完整顺反局比较见[从儿路径审查](../../bazi-assessment.md)。

问“为何这次冲后保留某根”时，可按需读取`clash_reasoning`视图的`strength_context.clash_comparison`。该表复用实际初始预算比较，不是完整原典冲力；合解冲、土动与旧输入未记录分别列示，不从最终余量倒推原因。未计入的盖头、生扶、距离权重和寒暖不能被解释成已经参与；见[六冲实际依据](../../bazi-assessment.md)。

追问燥湿、生发、根字与有效作用、隐显或众寡时，可按所问读取`knowledge_read(domain="bazi", category="classical_force_semantics")`中的`燥湿与生发条件`、`物理藏根与功能根`、`隐显与制化`或`众寡与日主符合`，不要求全部查询。词条只编释指定1947年任注原页及当前程序范围；正剩余根、印多、出现量和全局成平不能替代原典日主强弱。原典与本次计算分歧须如实保留，不用词条覆写同次结果，见[三章完整检验](../../bazi-assessment.md)。

讨论合化与根的关系时，同一`物理藏根与功能根`修订2补充GS12合而不化、GS13合而必化的整段对照。先分清假设、转折与最终判断；不把有任意藏根或没有重根当成通用成化判据，也不用词条补造本次未返回的成化或全局旺衰，见[现行校勘](../../bazi-assessment.md)。

问原局通关、杀印流转或冲中是否仍能生扶时，按需选择`passage`，全部藏干及跨干支、同柱步骤另读`passage_hidden/passage_mixed`。 运年能否补通，要另核已算时间层的中介与合冲，不能把本表静态路径改称当年已经生效。 日支藏印可以接到本柱日干，不能因没有透干中介就说无印生身；相邻、隔位、越位与同柱是位置事实。 可以按来源解释中介的传统作用；`effective_passage=not_adjudicated`时，不能将路径存在改述为已解冲、已成格或已由弱转强。 `binding_state=no_binding_recorded`只表示无已记合绊，不表示没有争合、半合、转化、冲损或其他待核条件；未返回对应关系证据时不能宣称条件全部清楚。路径五行、根状态和合绊状态须忠于实际节点，汇总数量须忠于同次列表；摘要字段也不支持改写这些事实。验收范围见[回执一致性](../../bazi-assessment.md)。 需要这些条件时选择`passage_relations`，逐项读取同次原事件与节点引用。透干合不能套给同柱藏干；透干的支关系按已给同五行根账本跨柱连接，藏干只连自身物理载体。零剩余根所在柱仍有条件记录；`null`账本与已给空列表分开。`conditioned_transformation`、`partial_tendency`等是工程模型状态，不能改述为原典已成化或已有效通关，见[同次关系条件](../../bazi-assessment.md)。 这组路径采用李雨田校订兼发行、大东书局经售的1947年《任注滴天髓阐微》，与下方《子平真诠》出处分别归属，见[通关与实数对照](../../bazi-assessment.md)。

解释原典“一杀四制”“五杀五制”等实数时读取`star_occurrences`，透干与每个藏干各项为1，日干不作额外支持票；不要换成藏干0.5的加权分数或制化力量。 “杀”是否仅七杀、“制”是否兼食伤须依该段来源核对；印不透与没有藏印分开，不能把未透改写为不存在。

问运年承载时，可读取主题工具的`carriers`视图：`topic.timing.pillar_carriers`把本柱主气、本柱真实藏根和原局外援分开。原局有乙根不能说乙酉本柱有根；十二长生名也不能补造藏干。盖头须以支为所喜、截脚压力须以干为所喜，布尔条件不等于真实喜忌、根损或吉凶。综合时运另有`carriers`摘要及`carriers_detail`；按实际时间层解读，不用任注十年运法替代月日时边界。来源与有限判据见[干支承载审查](../../bazi-timing.md)。

盖头目标细问可读`hidden_carriers`视图：本命在`evidence_chain.natal_hidden_carriers`，时运在已算`hidden_target_carriers`，按`node_id`对应旧`pillar_carriers`。丁丑对本气己为相生，对藏辛为相克，两者须同时保留；`covering_candidate_if_target_desired`只对应具体藏干为所喜的条件，不能扩成全支受克、已损根或已判吉凶。`hidden_rank`是现有表序号，不是原典气量排序。来源与验证见[逐藏干承载](../../bazi-assessment.md)。

专题运年藏干细问选`hidden_carriers_timing`，时运工具选`hidden_carriers`或`carriers_detail`，同时保留公共`hidden_target_reference`。该引用给方法、作者、版本、页码和未裁定范围；不要把逐柱省去的重复来源当作没有来源，或只凭旧本气视图补写原典效力结论。

核对天干计力时读取`stem_energy`视图所列字段，逐干账本在`evidence_chain.strength_context.stem_energy_accounting`，综合命盘也保留同次`day_master.assessment`原账本。v6对合绊采用未取整能量，展示值不能反过来替代计算值。当前`conversion_policy`明确为原合绊政策，成化候选未采用，不能把作用五行或五合关系改述为已成化、已合去或日主化气格。原字、藏干身份和十神实数分别保留。原注与任注有分歧时须说明采用哪层，不以任意一段为整部书背书，见[天干计力审查](../../bazi-assessment.md)。

综合与九专题的公开 `classical_routes` 字段视图给出同次月令取用见证、原典路径与十神节点。 先读`month_command.use_resolution`的全部适用见证；杂气的`selected_god`和旧单锚标签只供历史追溯，不以它们或`candidates[0]`代替完整见证集。 `complete_month_triad`仅确定五行／十神类时，保留具体干和正偏未定；`requires_identity_adjudication`不能改述为已成某一正偏格。 `revealed_month_store_stem`记辰库明壬的十神与实际透干柱位，适用于所选底本列出的甲、丙、丁、己日。`month_hidden_stems=[]`沿用字面藏干目录。辰戌冲时能否通月令与实际力量须另审。 [辰月明壬书证与对照](../../bazi-assessment.md#chen-store-ren-witness) `from_star/to_star`须对应同一结果的`ten_gods`中`evidence_id`，不能将不同run的星位拼起来。 仅有生克合、隔位或同根事实，不足以断定相神有效、合去、根损或完整成格； `month_use_not_observed`及旧run的`not_applicable_to_selected_month`不表示没有相关星，也不据此否定尚未建模的半会读法。

共享 `evidence_chain.classical_root_profile` 将长生禄旺、墓库藏根、本气／余气及阴长生参考分列； `yin_growth_reference`不等于新增藏干，也不等于已裁定没有原典根气。 浮干比劫与地支根分开，局部根存在不裁定总强弱；相对力量与根损未定时保留未知。 财务`classical_context`先核同次`month_use_resolution/month_use_match`；食神身份匹配才进入食神生财前提，具体身份未定时继续待判。旧`month_command_role`只作参考，财透／根事实不升级为成格。 来源与有限验收见[太阳时与根气审计](../../bazi-assessment.md)。

术语核对版本：沈孝瞻《秘本子平真诠》，书影封面题“上海世界图书馆发行”（PDF1），国图藏本 `NLC416-11jh010455-35296`。冻结书影 SHA-256：`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`，PDF页序自1起。

| 原典定位 | 本页采用的解释范围 | 不由该出处支持的内容 |
| --- | --- | --- |
| 〈论用神〉印刷17页／PDF26 | 用神从月令取，顺用逆用有不同配合；不能统一解释成补足元素 | 本工具的扶抑计权、现代行业名单 |
| 〈论用神成败救应〉印刷19–21页／PDF28–30 | 成败须审四柱配合，书中逐格举身强弱、根、位置与救应条件；十神共现不足以直接成格 | 事业倾向指数、共现加分或岗位能力评价 |
| 〈论相神紧要〉印刷30页／PDF39 | 相神是辅佐用神成局的关系，不与用神混称 | 把某元素直接变成职业或行动处方 |
| 〈论杂气如何取用〉印刷32–34页／PDF41–43 | 兼透兼用、透会并用；完整会支提供五行／十神类资格，与已透具体十神分列 | 强定正偏化干、全合化、成格、喜忌或现实效果 |

这组原典只核对所列术语与条件，不为所有引擎规则背书。`career_type/traits/suitable_roles` 及创业计权属于 FateBridge 的现代规则／岗位类比，回答时将“本工具的类比”与“传统结构解释”分开；用户兴趣、经历、岗位权责和资金条件是现实建议的独立依据。
