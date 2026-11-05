# 八字旺衰与喜用的计算范围

八字本命、九专题及双人分析共用领域计算。`day_master` 的三档强弱、根的存在、结构成立条件和现实能力分别表达不同问题。规则索引没有成功概率含义。

## 当前旺衰算法

`season_root_revelation_relations_v12` 按每个原柱的藏干预算、月支季相、透干、根损与关系状态计算。日干不为自己增加非日干预算；合局的合成预算不成为物理藏根。同一根参与多个关系时，保留最严格的剩余预算，不累加重复扣减。

季相按木火土金水的旺相休囚死区分；藏干分配、显干激活、合绊及冲刑系数属于明确的软件参数。当前算法使用同次关系前提重建精确有理账本，阈值比较采用原始精确数，显示舍入不改变判级。天干只实施唯一相邻且不涉及日干的合绊，保留物理干字与五行；不实施未裁定的局部成化算法。

数值扶抑档还会受到具名结构规则的限定。`threshold_arithmetic`、`structural_decision`、`root_qualifications` 与原始账本应一起读取，不能把数值档当作最终标签的全部理由。十二长生是阶段查表；实际藏干、根位、根量和有效根力分别记录。

`structural_decision.method_id=source_root_capacity_priority_v3`修复得令且多处合格旺根的既有规则被“扶抑比例过半且数值档为中和”反向拦截的问题。仍要求月令旺、月根合格和至少两处合格旺根，其他结构优先级保留。GS12因此由中和变强；同一规则也改变未提供三档来源的SJ06，该条仍属未知，不计正确命例。没有添加命例ID分支或改系数。

v12在此基础上采用1947年本明确记载的有限结构条件：两处本气合格根；多处合格旺根配合实际有根印比；完整财官印身四支顺生且时归禄旺的隔支通关；冬水无实际木根时不将旺印等同身强。通关记录实际中介柱位，不制造预算或把一般隔冲自动解除。结构三档与数值扶抑分开核验；即使结构等级对参数稳定，数值三档不稳定或与结构等级不同时，普通扶抑喜忌继续待判，不由新等级自动发布。系数及既有保留门槛未改；TG01、GS01、GS03、DZ12、ML02、JH02六个不同输入修复，原先相符的明确三档无退步；受影响的25条无三档记录继续未知。

实现位于 [`strength.py`](../src/fatebridge/core/strength.py)、[`strength_thresholds.py`](../src/fatebridge/core/strength_thresholds.py) 和 [`elements.py`](../src/fatebridge/core/elements.py)。独立 Fraction 参考使用字面藏干、季相及预算等式；其关系成立条件仍是待核前提，不因此认证古典有效力量。

## 喜用分层与冲突

`structure_profile.resolution_policy=source_conditions_before_preference_v3` 保留月令参考、从儿等条件结构、扶抑、调候与通关观察。`dominant_structure` 只接受严格的月令参考结构；未裁定成格时不发布确定的喜忌数组。部分投影保留缺项，不从缺项补造事实。

读取 `formation_status`、`pending_conditions`、`conditional_elements` 和每层来源，区分已观察事实与尚未成立的方向。物理有根不证明根有足够作用，印多不证明日主承受能力，出现通关路径不证明实际流通。事业、财务、学习等专题保留当前计数和具名规则索引；不再输出退役评分分档。

## 原典资料与未决范围

当前随包的 [`bazi-source-annotations.json`](../src/fatebridge/data/reference/bazi-source-annotations.json) 保留367条来源记录、321个字面输入；244条未提供明确日主三档，不能作为相符项。来源条件、书名、发行者、页码、原文锚点和编辑编释分别记录；古代四柱不认证现代公历、时区或人物身份。

当前来源审计原24组不同输入先修复GS12，再由v12修复六组，仍有17组与保留三档编释不符，另有2项集合约束违规及4项局部冲向分歧。两项集合违规分别为SJ05从儿不以身强弱论的适用域，以及QQ02官印承受能力未定；不据“非弱”任意选强或中和。3个原集合约束均纳入回执；`--require-full`在完整原典验收未成立时退出1。冲突和未知不改成通过，不以新字段数量增加独立命例信用。运行当前审计：

```bash
uv run --locked --extra dev python -m scripts.bazi.audit_bazi_source_corpus --output /tmp/bazi-source-audit.json
uv run --locked --extra dev pytest -n0 tests/bazi/test_bazi_current_accuracy.py tests/bazi/test_bazi_source_bounds.py
```

《滴天髓》当前开发者字面校读另保留558例、1380条原文主张、3项输入疑问及22项字形疑问；它尚不允许作为完整已验收命例库使用。资料与原书见 `tests/data/bazi`。同一原书的重叠记录不相加为独立样本，文本校读不等于数值或预测有效性验证。

原典概念通过 `knowledge_read(domain="bazi", ...)` 查询；引文、作者、编者说明及当前程序定位分别归属。完整本命与专题字段见[按需合同](contracts/README.md)，时运边界见[八字时运](bazi-timing.md)。
