# 计算、解释与现实预测的验证

历法数值、某部原典的规则、解读是否引用实际结果、现实预测效果需要分别验证。一个维度通过，不能替其他维度计分；有限样本全部符合，也不能证明所有输入或未来事件均正确。

## 八字的历史对照与未决范围

| 维度 | 固定版本的可复核结果 | 尚未成立的部分 |
| --- | --- | --- |
| 历法 | 2026–2028 年 72 个香港天文台节气时刻均在 60 秒容差内，最大差异约31秒（以当次审计快照为准）；另有上海、纽约的 144 个交节／中气月界探针 | 未覆盖全部支持年份、历史地方时及所有独立历书；发表到分钟的资料不验证秒级精度 |
| 原典 | 冻结的《秘本子平真诠》命例取格名称目前10/10相符；原文明示旺衰仍为1/3；7例原文未裁定 | 十例已用于开发，不再是盲测；两例旺衰分歧及成格、相神、救应的完整规则仍未通过；`classical_acceptance_passed=false` |
| 解读忠实 | 新增同 run、完整业务摘要、路径、值与类型的结构化引用核验；时运快照显示已声明出生时间范围及大运候选 | 不验证任意自由文本的全部语义；也未完成真实模型多轮行为验收 |
| 现实预测 | 新增固定队列、事前预测、外部结果和基线的评估模块；空示例实际运行返回 `not_tested` | 没有独立现实预测／结果数据，不能计算现实准确率或认证权威 |

表中成绩来自既有固定审计，不是本轮重新执行的结果。上述历法夹具保留官方原始 XML 及散列（本地数据：`../tests/fixtures/calendar_hko_v1/reference.json`），数据来自[香港天文台二十四节气](https://www.hko.gov.hk/en/gts/astronomy/Solar_Term.htm)，期望值未由 FateBridge 生成。边界探针在已发表分钟前后各两分钟查询，以避免把参考资料舍入误差当换月错误。

## 原典修正如何复核

[月令领域实现](../src/fatebridge/core/classical.py)将建禄、阳刃的资格与“本气是比肩／劫财”分开；戊日未月不能因己土劫财直接命名月刃，戊巳建禄与戊午阳刃也不能只看主气判定。规则依据所选[《秘本子平真诠》书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)的《论阳刃》（PDF86–87，书页77–78），并以不同命式反例核对。

杂气月增加“透干且有实际会支支持”的有限取格条件；仍保留所有候选，不把会支存在解释为已经合化或成格。PDF65的戊日丁未月命例因此从误报月刃改为正官。后续又按PDF65–66正官章补上本气正官、财印辅助的限定分支，同页乙日壬申月命例不再因印透自动改为印格；详细条件和藏干根语义见[八字判定](bazi-assessment.md)。`original_structure`、`seat_qualification`、`selection_rule`显示选择依据，不能把标签当完整原典裁定。

```bash
uv run --locked --extra dev python -m scripts.bazi.audit_bazi_classical \
  --output /tmp/fatebridge-classical-audit.json
```

当前此命令应退出 1，表示算法验收仍未通过。不得通过修改冻结命例或将未裁定强弱补成中和来取得满分。书目、冻结范围及分组状态见[原典对照](bazi-assessment.md#原典资料与未决范围)。

## 同次结果引用核验

[核验模块](../src/fatebridge/validation/claims.py)接受完整原始结果及结构化引用。先从可信调用获得完整 JSON，保留其 `run_metadata`；不要用投影结果重建摘要。示例中的 `payload` 是待核对结果，`original_payload` 是调用方另行可信保存的完整原结果：

```python
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

receipt = payload["run_metadata"]
claim = CalculationClaim(
    path="dayun_info.pillar",
    value=payload["dayun_info"]["pillar"],
    run_id=receipt["run_id"],
)
verification = verify_calculation_claims(payload, [claim], trusted_payload=original_payload)
assert verification["status"] == "verified_structured_facts"
```

换 run、修改标签或数值、把布尔值当整数、引用不存在或未计算的时间层、以投影结果冒充完整输出均不能通过。完整内容通过与 `trusted_payload` 逐值比较；未提供时只核对所供字段与 run，不认证完整原结果或自行提交的回执。这一接口适合调用方核对解读所引用的事实；自由文本推论与现实建议仍需独立审核。出生范围的计算与摘要约束见[时运审计](bazi-timing.md#范围与检验)。

## 可证伪的现实预测评估

[评估模块](../src/fatebridge/validation/predictions.py)只计算外部提交的记录，不生成预测概率，也不将八字分数除以 100 当概率。当前范围为一个完整时间窗口内、每个独立主体一次的二元事件评估；多次观察、连续结果、生存时间或多目标检验需要另设统计方案。

在观察目标窗口前固定 `StudyPlan`，包括可操作的目标定义、窗口、模型与解释政策指纹、完整队列、基线概率、决策阈值、置信水平、`planned_evaluations`检验次数和最低样本／Brier条件。基线不能从测试结果反推。计划需要存入可外部核验的事前登记系统；[COS 的预注册说明](https://www.cos.io/initiatives/prereg)解释了计划与结果揭晓的时间关系。开发数据与已经看过的古代命例不能重新命名为独立盲测。

| 记录 | 必需信息 |
| --- | --- |
| `Forecast` | 注册 case、完整方案的 `study_plan_sha256`、目标窗口开始前的发布时刻、已登记模型散列、计算及解释政策证据散列、预测概率；明确弃权用 `null` |
| `Outcome` | 同一 case、同一完整方案的 `study_plan_sha256`、是否发生、阳性事件时刻、完整窗口结束后的记录时刻、外部来源引用及散列 |
| `StudyPlan` | 固定匿名主体与 case 一一对应；同一主体不重复计为独立样本 |

评估会拒绝重复 case、未注册记录、迟发预测、模型替换、未结束即确认的阴性结果及非有限概率。缺预测、弃权和未随访记录保留在队列及覆盖率中；`as_of` 之后才记录的结果不参与指标。全队列可评估、样本数足够且超过预设 Brier 条件时，`registered_numeric_gate_met` 才可能为 true。完整的 `preregistered_performance_gate_met` 还要求登记引用、解释政策、基线冻结及训练主体声明完整；这仍不等于外部认证。

`StudyPlan.registration_reference`保存外部事前登记引用，`interpretation_policy_sha256`冻结解释政策，
`baseline_frozen_at`不得晚于计划登记时刻。每条`Forecast.interpretation_policy_sha256`必须与计划一致；
即使计算模型不变，也不能更换解释政策后混入同一评估。
描述性诊断允许资料尚未齐全，`protocol_blockers`会逐项列出缺失，
`protocol_status`不会报为完整，且完整预注册门槛保持false；描述性指标仍可计算。
填写引用、时间及散列只构成内部声明，外部登记真实性和执行时间仍须独立核验。

通用评估器v4另核对每条预测与结果的 `study_plan_sha256`，其值为 `digest(StudyPlan.model_validate_json(plan_text).model_dump(mode="json"))`。它绑定整个校验后方案，包含事件、窗口、队列、基线及统计政策；不是原始文件字节散列。错配直接拒绝，缺少绑定的记录仅可作数值诊断，但列出 `missing_forecast_plan_commitment`／`missing_outcome_plan_commitment`，不能通过完整预注册或统计证据门槛。不能在看过结果后补字段并冒充当初承诺。虚构完整流程见下方示例。审计脚本的输出路径必须尚不存在，避免覆盖以前的报告。

输出包括准确率、[NIST Wilson 准确率区间](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)、Brier分数、固定基线比较与覆盖率。10/10的样本全对，在独立样本假设下95% Wilson下界仍约为72.25%；不能据此宣称总体准确率为100%。现新增`statistical_evidence_gate_met`，以配对损失的Hoeffding保守单侧界检验注册的技能阈值，并对登记检验次数作Bonferroni分配；`preregistered_performance_gate_met`表示点估计、覆盖及协议完整门槛，`registered_numeric_gate_met`只表示数值门槛；统计门槛也不能绕过协议缺失。该方法不是Brier技能比值的专用区间，也不证明现实记录真实性。

`training_subject_ids`可声明训练主体匿名清单；与评估队列重叠会被拒绝，省略时报告`not_declared`，不能假定已经检查无泄漏。概率另按固定五档给出样本数、平均预测概率和实际发生比例；空档保留，不把小样本校准表当效度认证。

可以直接运行不包含任何预测和结果的[虚构流程示例](examples/prediction-study/plan.json)：

```bash
uv run --locked --extra dev python -m scripts.evaluation.audit_prediction_study \
  --plan docs/examples/prediction-study/plan.json \
  --forecasts docs/examples/prediction-study/forecasts.json \
  --outcomes docs/examples/prediction-study/outcomes.json \
  --as-of 2028-01-02T00:00:00Z \
  --output /tmp/fatebridge-prediction-audit.json
```

预期 `evaluable_count=0`、`real_world_efficacy=not_tested`、`authority_certified=false`。退出 0 只表示评估流程成功执行。示例中的全零模型／解释政策散列、登记占位引用和三个虚构主体是流程占位，不能作为真实预注册使用。实际研究应另外创建带有真实固定模型、外部登记与独立结果的数据集；报告保留计划、预测及结果的散列，软件本身不能鉴定时间戳、来源真实性或盲法执行情况。

## 验证命令

```bash
uv run --locked --extra dev pytest -q \
  tests/astronomy/test_hko_calendar_independent.py \
  tests/bazi/test_bazi_second_iteration.py \
  tests/evaluation/test_prediction_validation.py \
  tests/bazi/test_bazi_timing_transports.py
```

这组测试覆盖有限历法对照、资格反例、出生范围、三端共享合同、结构化引用与统计计算；它不将软件回归数量换算为四项能力总分。


## 同一事件的逐例冻结基线

通用评估器自v3起可二选一使用常数 `StudyPlan.baseline_probability` 或逐例 `StudyPlan.baseline_forecasts`。逐例记录为 `BaselineForecast`，包含案例、概率、发布时间、同一目标定义、完整窗口、原始来源引用和SHA256。全部记录须唯一覆盖注册队列，发布不得晚于统一冻结，冻结不得晚于注册；目标或窗口不同、漏例、重复、事后发布及非有限概率直接拒绝，不回退到常数参照。

模型和参考按case ID配对同一可评估子集的实际事件，比较各自Brier损失。逐例参考值不能预先平均成常数，也不按输入列表顺序配对。原配对Hoeffding单侧界及Bonferroni分配仍适用其原有独立有界假设，未把参考异质性改成新置信度或权威分；主体相关性和预注册执行仍须外部核验。输出 `baseline_comparison` 明确标记常数／逐例模式，来源与参考强度都没有本地认证。

在未绑定方案的旧人工记录上，同一组1000条预测相对0.5常数有Brier技能0.75，但更强逐例参考使技能变为−24；预测和结果记录哈希不变。这种对照现在只保留为诊断，两个方案均不能靠这些无绑定记录通过协议门槛；已绑定记录不能换基线方案重用。这只说明技能依赖所选参照，不是任何术数的现实成绩。参考依据为[ECMWF逐例Brier定义](https://www.ecmwf.int/sites/default/files/elibrary/2006/74335-application-and-verification-ecmwf-products-member-states-and-co-operating-states_0.pdf)和[Hoeffding独立有界和](https://doi.org/10.1080/01621459.1963.10500830)。后见结果后挑选基线、同一资料反复调参和真实来源造假均不能由数值门槛解决。


## 奇门研究的盘面绑定

`scripts/qimen/audit_qimen_study.py` 将每条预测绑定到实际问时、明确的排局口径、完整奇门结果和冻结解释策略，然后逐案重算再交给通用二元结果评估器。它检查研究记录的一致性，不是已经验证的预测模型，也不提供权威认证。

目前没有可核验的真实奇门预测队列。当前演示脚本生成明确标为 `synthetic` 的三个人工案例、全部弃权和空结果列表，可评估数为0，现实效度为 `not_tested`。演示中的目标、日期、主体、记录哈希和时间戳都不是外部登记或经验材料。

### 输入、策略与封存

- `StudyInput` 须包含完整 `plan/policy/castings`。当前v3沿用v2的完整输入绑定，并纳入逐例基线的概率、发布时刻、相同目标／窗口及来源记录。计算错误和弃权留在队列；仅同步删除所有列表里的弃权案例或改基线，不能沿用原证据哈希通过评估。
- 每条起局须明确带时区的物理时刻、时区名、经度、记录时刻和问事原始档案的引用及哈希。当前计算接口只有分钟精度，拒绝静默截去秒数；不猜地点和时区。记录只接受注册后、目标窗口前的实际问时，不用于未来候选择时盘。
- 策略冻结置闰／拆补、八神章节、旺衰章节、真太阳时开关及原典分歧处理方式。模型指纹绑定整个包的源码及数据、项目锁文件、Python与平台、依赖版本、关键历法依赖实际文件、Swiss原生模块和配置搜索路径中的星历文件清单。实际盘面还包含所用时区规则指纹。无关包文件变化也会使研究环境失配，需要在独立固定环境重放。
- 发布预测只读取问事记录与盘面，不读取结果标签。规则概率是研究者事前明确冻结的假设值，`null` 是弃权；程序不把格局数、吉凶、旺衰或传统规则分换算为概率。这个接口不提供经过验证的概率映射。
- 解释策略采用有序的首条匹配规则，`all_of` 为合取。规则条件有真、假、未知三态；已知假能排除一条规则，可能匹配却含未知的较早规则会弃权，不能跳到后面的有利规则。日甲身份未明时，伏干／飞干特征为未知，不会把未输出格局当作不存在；其他已知门星神仍可独立使用。
- 格局名命中与附加条件已观察到是两种不同特征。计算保留整条格局证据、同宫冲突及源文限定；附加条件字段未评估时返回未知。`pattern_conditions_observed=true` 只表示至少一个匹配结构的已记录条件满足，不是全盘吉或现实成功。
- 真实数据封存使用当前本地时钟，不接受手填历史发布时间。计算期间源码或星历改变、时钟倒退，或实际封存时目标窗口已经开始，均拒绝。合成演示才允许注入时刻。
- 评估先重算每个实际奇门盘及策略决策，再检查预测、证据哈希与已封存结果。重放检查预测是否由该策略算得；全包指纹另核对是否仍是事前封存的那份计划及预测。真实研究必须提供从独立登记或可信存档取得的事前全包指纹，拒绝缺失或不匹配。仅靠重放不能发现整个计划、基线、队列和收据被一致重做；合成演示可以省略外部指纹，但报告明确标为未锚定的合成包。

当前采用 `qimen_forecast_commitment_v3`，对应常数／逐例基线二选一的研究输入。封存不得通过补字段或重算而冒充原来的事前承诺。`study_input_sha256` 在封存时绑定完整输入，不证明计划在问事发生前已经外部登记。

盘级 `qimen.source_disagreements` 可预先固定为 `source_disagreement_action=abstain` 或 `use_declared_rules`。前者保留该例并弃权，后者保留该例分歧并按已声明规则计算；不能看过结果再切换。这个开关不等于所有原典范围、释读和优先未决项都已完成自动裁决或自动弃权。整条引用或冻结条件的检查不认证任意自由文本解释。

### 合成演示与重放

源码环境先执行 `uv sync --locked --extra dev`。以下目录须是尚未生成过这些文件的新目录；命令拒绝覆盖已有封存记录。

```bash
uv run --locked --extra dev python -m scripts.qimen.demo_qimen_study \
  --output-dir /tmp/fatebridge-qimen-synthetic-demo

uv run --locked --extra dev python -m scripts.qimen.audit_qimen_study fingerprint \
  --policy /tmp/fatebridge-qimen-synthetic-demo/policy.json \
  --output /tmp/fatebridge-qimen-synthetic-demo/fingerprint.json

uv run --locked --extra dev python -m scripts.qimen.audit_qimen_study seal \
  --study /tmp/fatebridge-qimen-synthetic-demo/study.json \
  --synthetic-at 2026-12-31T00:00:00+00:00 \
  --output /tmp/fatebridge-qimen-synthetic-demo/resealed.json \
  > /tmp/fatebridge-qimen-synthetic-demo/reseal-receipt.json

uv run --locked --extra dev python -m scripts.qimen.audit_qimen_study evaluate \
  --commitment /tmp/fatebridge-qimen-synthetic-demo/resealed.json \
  --outcomes /tmp/fatebridge-qimen-synthetic-demo/outcomes.json \
  --as-of 2027-03-01T00:00:00+00:00 \
  --expected-commitment-sha256 "$(uv run --locked --extra dev python -c \
    'import json,sys; print(json.load(open(sys.argv[1]))["commitment_sha256"])' \
    /tmp/fatebridge-qimen-synthetic-demo/reseal-receipt.json)" \
  --output /tmp/fatebridge-qimen-synthetic-demo/replayed-report.json
```

预期：注册案例数3、可评估数0、覆盖率0、`real_world_efficacy=not_tested`、`authority_certified=false`。其中一例保留《演义》已知分歧，一例保留日甲未决身份，一例检查纽约重复钟时的明确偏移。当前实现保留 `casting_at` 对应的实际UTC时刻及IANA时区，全部弃权仍无可评估结果。合成时间可设在未来，不代表已经收集到未来资料。

`seal` 的标准输出提供 `commitment_sha256/study_input_sha256`；演示脚本也保存 `seal-receipt.json`。上面只演示读取封存时另存的本地收据，未进行真实外部登记。该指纹计算自经模型验证后的规范化JSON，不是对磁盘JSON文件直接执行 `sha256sum` 的结果；缩进和对象键顺序不影响指纹。

公开奇门接口可同时给 `analysis_timezone=America/New_York` 和 `analysis_utc_offset=-04:00`（或该重复小时的 `-05:00`）；偏移须与该命名时区在指定钟时的规则一致，不会把全年时区换成固定偏移。研究接口从已知 `casting_at` 自动提取偏移，历史整秒偏移也保留；裸重复钟时和不存在的钟时继续拒绝。输出 `qimen.calendar_policy.civil_clock_resolution` 保留原偏移、核对后的偏移、fold和实际UTC时刻，正文同步显示。

实际时刻的先后统一换成UTC比较，原记录不改写。包含同一个ZoneInfo对象的重复小时也要遵守注册、起局、记录、发布及结果窗口顺序；窗口未结束或结果记录晚于评估时刻时不能计入。新增回拨对抗案例是软件回归，不是现实预测样本。

### 真实研究输入

输入结构可参照上方演示命令生成的 `study.json`，不能沿用其中虚构资料当作实测资料。完整机器字段由 `StudyInput`、`FrozenQimenPolicy`、`Condition` 和通用 `StudyPlan/Outcome` 定义。

| 部分 | 必须事先明确的内容 |
| --- | --- |
| `plan` | `data_kind=real_world_submission`、目标定义、注册时刻、共同结果窗口、完整队列、基线及冻结时刻、训练主体（无也须显式 `[]`）、样本与停止规则、计划检验次数、模型与解释策略指纹、真实外部登记引用 |
| `policy` | 排局／章节口径、冲突处理、唯一规则ID、有序条件、每条规则的冻结概率或弃权、显式兜底概率或弃权 |
| `castings` | 队列中每例的 `case_id/subject_id/casting_at/timezone_name/longitude/recorded_at/question_record_sha256/question_record_reference` |
| `outcomes` | 每例独立判定的是否发生；发生时刻（阳性必需）、完整窗口结束后的记录时刻、原始结果档案哈希和引用 |

`plan.model_sha256` 使用 `fingerprint` 输出的模型指纹，`plan.interpretation_policy_sha256` 使用该命令输出的策略指纹。指纹生成只是本地草稿，不替代事前外部登记。登记后不得改写目标、队列、基线、概率映射、样本量或停止规则；变更须作为新研究或明确的探索分析。真实研究封存命令去掉 `--synthetic-at`，真实评估也拒绝未来的 `--as-of`。

真实研究封存后、目标窗口开始前，应将完整封存包及其规范化指纹提交可信独立登记或存档，并在评估时从该记录取得 `--expected-commitment-sha256`。不得在看过结果后从当前待评文件新算一个指纹，再把它称为事前外部锚。程序核对调用者提供的指纹是否吻合，不能自行认证它何时、由谁保存，故 `expected_digest_provenance_authenticated/external_registration_authenticated` 仍为false；指纹吻合不等于预注册、盲法或独立结果核验已经完成。

条件目录限定为全盘星／门伏吟反吟、五不遇、所选卷二六组时干支入墓，指定外八宫的门／主星／神、主星旺衰、门迫、时旬空亡范围，以及已经实现的格局存在／已记录附加条件。`hour_branch_tomb` 是字面时柱条件，不检查天盘时干的墓宫。不能给任意JSON路径，不能读取结果或主体ID，也不能给中宫补门星神。岁格、月朔格可使用 `year_stem_block/lunar_month_start_block`；年界、甲身份或历法锚点未解决时返回未知，不能把缺项当阴性。`stem_pair` 表示已实现干对类别中的任意命中，不是某个格名或总体吉凶。

目前研究接口仅支持共同窗口下的二元事件、每例一个独立主体，重复主体会拒绝；重复观察、聚类、连续结果、不同结果窗口、人工自由解释盲评及打乱问时对照需要另行预注册和实现。独立的现实信息基线与对照不能由本程序凭空补出。

规则取法必须在策略中事先冻结。三奇入墓、六仪击刑的广义／窄读、门迫方向、三诈共享证据、五假及人假未知等条件，统一按[奇门规则与未决范围](qimen-depth-audit.md)核对；`pattern_conditions_observed` 不表示全盘条件满足。未知不能补为否，原文比例不能变成预测概率，旧封存不按新格名回填。

### 核验边界

本地哈希不证明问时真实、时钟可信、档案存在或不可回写，也不证明外部登记的内容一致、盲法执行、纳入规则执行、样本独立、主体同意、无人泄露结果、未试过其他未披露策略或结果判定公正。包源码与依赖文件指纹也不证明进程内代码未被篡改。研究应在独立固定检出和新进程中运行，并由可信登记和独立结果核验补足这些边界。即使全部程序门槛通过，也只得到提交记录的有限统计结果，不能据此宣称普遍预测有效、100%总体准确或最权威系统。


真太阳时版本还应冻结 `calendar_policy.solar_time_adjustment` 所载实际分项与方法。当前UTC近似UT1，不将距换时／换日的秒数当作误差界或确定性；独立太阳钟在5秒核对容差内仍有一例边界不能认证。每条研究证据绑定整个返回，修正依据变化会改变证据及引擎指纹；旧封存必须沿用其固定环境，不能据传统规则仍为2.12.0补写新回执。



逐例基线与统计公式使用本页[同一事件的逐例冻结基线](#同一事件的逐例冻结基线)。演示也可添加 `--baseline-kind per-case`；所生成的0.5概率、主体与来源均为人工示例，不成为真实外部参照。
