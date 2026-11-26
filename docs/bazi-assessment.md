# 八字旺衰与喜用的计算范围

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

八字本命、九专题及双人分析共用领域计算。工程旺衰索引、原典力量裁定、根的存在、格局适用条件分别交付。规则索引没有成功概率含义。

离散十神、纳音、藏干、长生和原始关系层的有限第三方对照，见[八字离散规则与关系层核对](bazi-relations-audit.md)。相邻五合现在交付候选化神与“相合”，不再由字面配对直接断成“合化”；这项修复不代表完整成化、旺衰或喜忌已经验收。

来源条件层含30项原页校读，绑定32条已登记记录，包括从儿与身力、寒暖、根气及官杀承载等条件。原页录文、编辑编释、运段条件与本命事实分别保留；这些校读不提供工程支持占比阈值，也不补定原书没有给出的三档。当前差异及集合约束见[原典资料与未决范围](#原典资料与未决范围)。 [原页校读与工程回归](precision-acceptance.md#八字本气根覆盖与官杀承载复核)

## 当前旺衰算法

`day_master.engineering_index` 标明 `quantity_kind=uncalibrated_strength_policy_index`：`strength_level` 是既有预算和结构覆盖政策的工程档，`numerical_strength_level` 是纯数值阈值档。原有 `day_master.strength`／内部 `strength_level` 也表示该工程政策档；不是原典身强身弱的已定结论。工程参数、原始预算和既有评分没有因本次拆分重新校准。

`day_master.classical_adjudication` 由独立的[原典力量职责](../src/fatebridge/core/classical_force.py)提供，同次结果的 `force_components.classical_adjudication` 复用它。身、印、身印关系及普通扶抑适用性分别记录；未知为 `null`，`status=not_adjudicated`，并列待核前提。物理根位不等于有效根力，工程档不回填原典结果，登记命例标签也不参与这一计算。

`season_root_revelation_relations_v12` 按每个原柱的藏干预算、月支季相、透干、根损与关系状态计算。日干不为自己增加非日干预算；合局的合成预算不成为物理藏根。同一根参与多个关系时，保留最严格的剩余预算，不累加重复扣减。

辰、午、酉、亥同支重见的自刑事件采用《三命通会》卷二〈论三刑〉的字面关系出处。工程层将重见事件标为活动，并使用 `0.90` 的根预算保留系数。五个固定公开盘的自刑出处得到更正，同批有理算术两臂各通过 45 项。

季相按木火土金水的旺相休囚死区分；藏干分配、显干激活、合绊及冲刑系数属于明确的软件参数。当前算法使用同次关系前提重建精确有理账本，阈值比较采用原始精确数，显示舍入不改变判级。天干只实施唯一相邻且不涉及日干的合绊，保留物理干字与五行；不实施未裁定的局部成化算法。

工程政策档还会受到具名结构规则的覆盖。`threshold_arithmetic`、`structural_decision`、`root_qualifications` 与原始账本应一起读取，不能把数值档当作工程政策标签的全部理由。这些结构覆盖仍采用工程根保留门槛，不能仅因附有原典出处便升级为充分的原典力量裁定。十二长生是阶段查表；实际藏干、根位、根量和有效根力分别记录。

`structural_decision.method_id=engineering_root_capacity_priority_v4` 保留得令、合格根、同类会局、顺生路径和冬水无木根等工程覆盖。至少两处同类本气根同时遇到至少两处有根官杀透出、且缺少有根印比透干承接时，暂缓按根数覆盖，保留数值档并令 `ordinary_fuyi_requires_review` 为真。1947年本的寅月寅时甲木“木嫩气虚”仍是根数充分判法的反例。原典三档还须核实身印承接、食财官负载、寒暖和作用路径。 [本气根覆盖与官杀承载复核](precision-acceptance.md#八字本气根覆盖与官杀承载复核)

实现位于 [`strength.py`](../src/fatebridge/core/strength.py)、[`strength_thresholds.py`](../src/fatebridge/core/strength_thresholds.py) 和 [`elements.py`](../src/fatebridge/core/elements.py)。独立 Fraction 参考使用字面藏干、季相及预算等式；其关系成立条件仍是待核前提，不因此认证古典有效力量。

## 喜用分层与冲突

调候的具名来源层目前覆盖 69 个日干月支组合，包括《穷通宝鉴评注》的甲、乙、丙、丁、戊各节月及己土寅至戌的九个节月。其余 51 格继续提供待校的简表候选。已校层交付提要、正文条件、注语、书影页码和实际干藏位置。全盘制救、力量、合化与取用仍待裁定。 [戊酉与乙子](precision-acceptance.md#seasonal-wu-yi-source-round71) · [戊戌与乙丑](precision-acceptance.md#seasonal-wu-xu-yi-chou-round72) · [戊亥与乙亥](precision-acceptance.md#seasonal-wu-hai-yi-hai-round73) · [戊子与乙戌](precision-acceptance.md#seasonal-wu-zi-yi-xu-round74) · [戊丑与乙酉](precision-acceptance.md#seasonal-wu-chou-yi-you-round77) · [戊寅与乙申](precision-acceptance.md#seasonal-wu-yin-yi-shen-round79) · [戊申与乙未](precision-acceptance.md#seasonal-wu-shen-yi-wei-round81) · [戊卯与乙午](precision-acceptance.md#seasonal-wu-mao-yi-wu-round90) · [戊辰与乙巳](precision-acceptance.md#seasonal-wu-chen-yi-si-round90) · [戊巳与乙辰](precision-acceptance.md#seasonal-wu-si-yi-chen-round92) · [戊午与乙卯](precision-acceptance.md#seasonal-wu-wu-yi-mao-round93) · [戊未与乙寅](precision-acceptance.md#seasonal-wu-wei-yi-yin-round95) · [己土三春](precision-acceptance.md#bazi-ji-spring-source-round128) · [己土三夏](precision-acceptance.md#bazi-ji-summer-source-round187) · [己土三秋](precision-acceptance.md#bazi-ji-autumn-source-round192)

`structure_profile.resolution_policy=source_force_before_preference_v4` 保留月令参考、从儿等条件结构、扶抑、调候与通关观察。全局来源喜忌须先有原典力量和普通扶抑路径的适用结论。当前仍为 `assessment_status=not_adjudicated`，`useful_elements`／`avoid_elements` 为空、五行列在待定项；空数组不表示“没有有利元素”或已经排除互助。对外 `favorable_elements_status` 一并交付。部分投影缺少状态时不能从空数组补造结论。

`engineering_favorable_elements` 保留既有工程扶抑参考；`structure_profile.engineering_reference` 保留原有候选冲突消解后的工程方向。原局取证可以按字段读取工程参考及原典取用两种状态。来源层与工程层不互相回填，也不重算第二个原局。

读取 `formation_status`、`pending_conditions`、`conditional_elements` 和每层来源，区分已观察事实与尚未成立的方向。物理有根不证明根有足够作用，印多不证明日主承受能力，出现通关路径不证明实际流通。事业、财务、学习等专题复用原局计算，按主题投影实际星位和具名条件。

## 专题星位与结构候选

九专题由共享 `build_natal_evidence` 提供四柱、透藏、根气和格局前提，`build_topic_evidence` 选取专题相关的星、宫、神煞和目标运年关系。面向首轮的 `topic.first_view` 摘录可核对的星位，完整 `topic.stars` 保留每次命中。

食神生财和普通伤官用财的候选会核对财根。见实际藏干根时满足这一观察前提，只有十二长生阶段参考时保留待核，两者皆无时标记前提不满足。候选状态与实际生财关系分别交付。食神结构检查另列财透，财印兼用另查自身条件。 [《子平真诠》书影与固定对照](precision-acceptance.md#bazi-wealth-root-round63)

综合与九专题可用 `evidence_views.classical_routes` 的字段清单核对月令、星位节点及原典生克合路径。日期级专题的 `timing_context` 采用本地零点锚点；立春或其他交节当日的具体钟时须查相应时运结果，不能以零点代表全天。时间规则见[八字时运](bazi-timing.md)。

## 专题模块职责清查

专题复用共享十神计数、神煞、初始根预算和出生上下文；并列首位逐项交付，不把同分项压成唯一首位。健康文化分档采用整数计数比较，支持量与份额复用精确账本；展示舍入不改变边界。

事业、财务、学习、子女、婚姻、双人和五维中的固定权重、基准与阈值属于未经现实校准的工程政策。健康文化分档、人物外观／性情／行业／学科词典，以及年支／日支选锚的逐条原典核对继续未完成。职责和验收状态见[源码职责](architecture.md#分层职责)。

## 原典资料与未决范围

冻结的十例资料需要从维护者取得原快照 `tests/data/bazi_classical_v1/`，其中 `cases.json` 记录书中标签和已裁定范围。取书影应使用[上海世界图书馆发行本《秘本子平真诠》](https://commons.wikimedia.org/wiki/File:NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)，按原页重录所得资料应作为独立复核，不能代替冻结标签。

1947 年任注本 PDF 第 416 页的 HJ06 写寅月寅时甲木“木嫩气虚”。逐条去除工程强档条件的静态对照最后仍落数值中和；来源所录弱档分歧继续保留。XQ30 原书“无土”仍未形成可删除午中己土的通用规则。子卯关系保留实际重复实体；《秘本子平真诠》丙子月官之刑只按所选条文的月令与实体条件准入。完整有效根力、寒暖、身印承接与作用优先顺序仍待裁定。

当前随包的 [`bazi-source-annotations.json`](../src/fatebridge/data/reference/bazi-source-annotations.json) 有370条来源记录、324个字面输入。原367条记录和321个输入及后来两条〈寒暖〉命例完整保留，新增一条《三命通会》卷八字面命例。现有247条未提供明确日主三档，不能作为相符项。来源条件、书名、发行者、页码、原文锚点和编辑编释分别记录；古代四柱不认证现代公历、时区或人物身份。

当前来源审计原24组不同输入先修复GS12，再由v12修复六组，仍有17组与保留三档编释不符，另有2项集合约束违规及4项局部冲向分歧。两项集合违规分别为SJ05从儿不以身强弱论的适用域，以及QQ02官印承受能力未定；不据“非弱”任意选强或中和。3个原集合约束均纳入回执；`--require-full`在完整原典验收未成立时退出1。冲突和未知不改成通过，不以新字段数量增加独立命例信用。

`bounded_comparison` 的允许集合来自登记编释。1947 年影印本第 393 页讨论从儿论法的适用条件，第 238 页在独印、财官和连续生化的语境下论日主之气。将这些局部断语对应到工程三档是编释步骤。固定复跑保留 17 个档差、SJ05 与 QQ-02 的两项违规，以及 GH-07 的一项符合。新增书例用于核对相邻合绊和根载体，日主三档与取用继续待裁。 [书证与固定三端对照](precision-acceptance.md#bazi-bound-attribution-round110)

这一分母继续比较原工程政策档与原标签，不因新增未知裁定而消失。审计另列 `classical_grade_comparison`：123条有三档来源的记录目前全部尚未由通用规则裁定，未决不计通过。17组已重新核对原页；“气馁”“弱中之旺”等语义疑点另行保留，不改冻结标签来降低分歧数。

运行当前审计：

```bash
uv run --locked --extra dev python -m scripts.bazi.audit_bazi_source_corpus --output /tmp/bazi-source-audit.json
uv run --locked --extra dev pytest -n0 tests/bazi/test_bazi_current_accuracy.py tests/bazi/test_bazi_source_bounds.py
```

《滴天髓》当前开发者字面校读另保留558例、1380条原文主张、3项输入疑问及22项字形疑问；它尚不允许作为完整已验收命例库使用。资料与原书见 `tests/data/bazi`。同一原书的重叠记录不相加为独立样本，文本校读不等于数值或预测有效性验证。

原典概念通过 `knowledge_read(domain="bazi", ...)` 查询；引文、作者、编者说明及当前程序定位分别归属。完整本命与专题字段见[按需合同](contracts/README.md)，时运边界见[八字时运](bazi-timing.md)。

<a id="month-use-witnesses-round35"></a>
## 杂气月令的并存见证（R35）

所选沈孝瞻《秘本子平真诠》NLC影印PDF41–43／印刷32–34的杂气整章，明确一透一用、兼透兼用、透会并用，并举甲辰申子水印。新共享month_use领域保每项实际透干／完整三合见证，区分月藏干、实际透出十神与会支五行／十神类；作者、发行本、PDF页与原文范围随同结果交付；源文件校验保留在内部资料中。该章还保有情／无情与救应反转，见证并存不表示均为喜用，不认证全合化、成格或现实效果。

候选、星位路由和必要条件共用同次见证集合；完整会支在具体正偏身份未定时不伪造唯一干。普通月沿用原有限方法，杂气不从旧selected/original单锚补出唯一路径。月令主标签改为取用见证参考，旧单格和structure_god明确历史作用。强弱权重、有效根力、原367／321记录及17差异／两约束不因这一来源修复而改判。

所选影印十例分别按单一格名与书中取用角色核对。[原典审计脚本](../scripts/bazi/audit_bazi_classical.py)保留单一格名比较的 7/10，并另外用共享取用见证核对书中标注的十神，结果为 10/10。书影 PDF65–66 的孤官例、宣参国例分别有乙官与己官透干，PDF83 的秦龙图例有己伤官透干。宣参国例另有独立木局见证，其正偏身份仍由现行规则保留为未定。旧格名三条差异、旺衰 1/3、七例原书未裁旺衰，以及十例成格和用神／相神的未通过状态均保留。 `tests/data/bazi_classical_v1/cases.json`（另备的固定命例）

<a id="chen-store-ren-witness"></a>

## 辰月明壬的取用见证

上海世界图书馆发行本《秘本子平真诠》的《论杂气》《论墓库刑冲》举出辰月明壬的甲印、丙煞、丁官、己财。现行 `revealed_month_store_stem` 在这四个日干的辰月盘中记录实际透出的壬、柱位及十神。源码按甲、丙、丁、己分别交付偏印、七杀、正官、正财，以及该例的 PDF 页码和书证。辰的字面藏干仍为戊、乙、癸。明壬、同字透癸与完整申子辰可以并存。乙日及其他未举日干的原典适用范围待校。遇辰戌冲时仍须另审通月令和实际作用，格局保持未裁定。 [国图藏本 PDF42–45](https://commons.wikimedia.org/wiki/File:NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)
