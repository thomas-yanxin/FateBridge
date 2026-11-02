# 八字四项能力的独立验收

历法数值、某部原典的规则、解读是否引用实际结果、现实预测效果需要分别验证。一个维度通过，不能替其他维度计分；有限样本全部符合，也不能证明所有输入或未来事件均正确。

## 当前证据

| 维度 | 本轮可复核结果 | 尚未成立的部分 |
| --- | --- | --- |
| 历法 | 2026–2028 年 72 个香港天文台节气时刻均在 60 秒容差内，最大差异约31秒（以当次审计快照为准）；另有上海、纽约的 144 个交节／中气月界探针 | 未覆盖全部支持年份、历史地方时及所有独立历书；发表到分钟的资料不验证秒级精度 |
| 原典 | 冻结的《秘本子平真诠》命例取格名称目前10/10相符；原文明示旺衰仍为1/3；7例原文未裁定 | 十例已用于开发，不再是盲测；两例旺衰分歧及成格、相神、救应的完整规则仍未通过；`classical_acceptance_passed=false` |
| 解读忠实 | 新增同 run、完整业务摘要、路径、值与类型的结构化引用核验；时运快照显示已声明出生时间范围及大运候选 | 不验证任意自由文本的全部语义；也未完成真实模型多轮行为验收 |
| 现实预测 | 新增固定队列、事前预测、外部结果和基线的评估模块；空示例实际运行返回 `not_tested` | 没有独立现实预测／结果数据，不能计算现实准确率或认证权威 |

上述历法夹具保留官方原始 XML 及散列（本地数据：`../tests/fixtures/calendar_hko_v1/reference.json`），数据来自[香港天文台二十四节气](https://www.hko.gov.hk/en/gts/astronomy/Solar_Term.htm)，期望值未由 FateBridge 生成。边界探针在已发表分钟前后各两分钟查询，以避免把参考资料舍入误差当换月错误。

## 原典修正如何复核

[月令领域实现](../src/fatebridge/core/classical.py)将建禄、阳刃的资格与“本气是比肩／劫财”分开；戊日未月不能因己土劫财直接命名月刃，戊巳建禄与戊午阳刃也不能只看主气判定。规则依据所选[《秘本子平真诠》书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)的《论阳刃》（PDF86–87，书页77–78），并以不同命式反例核对。

杂气月增加“透干且有实际会支支持”的有限取格条件；仍保留所有候选，不把会支存在解释为已经合化或成格。PDF65的戊日丁未月命例因此从误报月刃改为正官。后续又按PDF65–66正官章补上本气正官、财印辅助的限定分支，同页乙日壬申月命例不再因印透自动改为印格；详细条件、旧标签和藏干根语义见[本轮四项验证](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-four-axis-validation.md)。`original_structure`、`seat_qualification`、`selection_rule`显示选择依据，不能把标签当完整原典裁定。

```bash
uv run --locked --extra dev python scripts/audit_bazi_classical.py \
  --output /tmp/fatebridge-classical-audit.json
```

当前此命令应退出 1，表示算法验收仍未通过。不得通过修改冻结命例或将未裁定强弱补成中和来取得满分。书目、冻结范围及分组状态见[原典对照](bazi-assessment.md#原典对照基准与未覆盖范围)。

## 同次结果引用核验

[核验模块](../src/fatebridge/validation/claims.py)接受完整原始结果及结构化引用。先从可信调用获得完整 JSON，保留其 `run_metadata`；不要用投影结果重建摘要。示例中的 `payload` 是这次实际调用的原始字典：

```python
from fatebridge.validation.claims import CalculationClaim, verify_calculation_claims

receipt = payload["run_metadata"]
claim = CalculationClaim(
    path="dayun_info.pillar",
    value=payload["dayun_info"]["pillar"],
    run_id=receipt["run_id"],
    business_output_sha256=receipt["business_output_sha256"],
)
verification = verify_calculation_claims(payload, [claim])
assert verification["status"] == "verified_structured_facts"
```

换 run、修改标签或数值、把布尔值当整数、引用不存在或未计算的时间层、以投影结果冒充完整输出均不能通过。哈希核对只在可信原始回执的前提下成立，不提供数字签名，也不能认证自造回执。这一接口适合调用方核对解读所引用的事实；自由文本推论与现实建议仍需独立审核。出生范围的计算与摘要约束见[时运审计](bazi-timing.md#出生时刻范围与解释忠实)。

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
这些新增字段为兼容旧记录允许省略，但`protocol_blockers`会逐项列出缺失，
`protocol_status`不会报为完整，且完整预注册门槛保持false；描述性指标仍可计算。
填写引用、时间及散列只构成内部声明，外部登记真实性和执行时间仍须独立核验。

通用评估器v4另核对每条预测与结果的 `study_plan_sha256`，其值为 `digest(StudyPlan.model_validate_json(plan_text).model_dump(mode="json"))`。它绑定整个校验后方案，包含事件、窗口、队列、基线及统计政策；不是原始文件字节散列。错配直接拒绝，缺少绑定的旧记录仍可作数值诊断，但列出 `missing_forecast_plan_commitment`／`missing_outcome_plan_commitment`，不能通过完整预注册或统计证据门槛。不能在看过结果后补字段并冒充当初承诺。具体反例、生成方法和虚构完整流程见方案绑定核验（本地数据：`validation/other-chart-study-plan-binding.md`）。审计脚本的输出路径必须尚不存在，避免覆盖以前的报告。

输出包括准确率、[NIST Wilson 准确率区间](https://www.itl.nist.gov/div898/handbook/prc/section2/prc241.htm)、Brier分数、固定基线比较与覆盖率。10/10的样本全对，在独立样本假设下95% Wilson下界仍约为72.25%；不能据此宣称总体准确率为100%。现新增`statistical_evidence_gate_met`，以配对损失的Hoeffding保守单侧界检验注册的技能阈值，并对登记检验次数作Bonferroni分配；`preregistered_performance_gate_met`表示点估计、覆盖及协议完整门槛，`registered_numeric_gate_met`只表示数值门槛；统计门槛也不能绕过协议缺失。该方法不是Brier技能比值的专用区间，也不证明现实记录真实性。公式、假设及反例见[精度深化](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-accuracy-depth.md#现实预测点估计与证据门槛分开)。

`training_subject_ids`可声明训练主体匿名清单；与评估队列重叠会被拒绝，省略时报告`not_declared`，不能假定已经检查无泄漏。概率另按固定五档给出样本数、平均预测概率和实际发生比例；空档保留，不把小样本校准表当效度认证。

可以直接运行不包含任何预测和结果的[虚构流程示例](examples/prediction-study/plan.json)：

```bash
uv run --locked --extra dev python scripts/audit_prediction_study.py \
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
  tests/test_hko_calendar_independent.py \
  tests/test_bazi_second_iteration.py \
  tests/test_prediction_validation.py \
  tests/test_bazi_timing_transports.py
```

这组测试覆盖有限历法对照、资格反例、出生范围、三端共享合同、结构化引用与统计计算；它不将软件回归数量换算为四项能力总分。


## 同一事件的逐例冻结基线

通用评估器自v3起可二选一使用常数 `StudyPlan.baseline_probability` 或逐例 `StudyPlan.baseline_forecasts`。逐例记录为 `BaselineForecast`，包含案例、概率、发布时间、同一目标定义、完整窗口、原始来源引用和SHA256。全部记录须唯一覆盖注册队列，发布不得晚于统一冻结，冻结不得晚于注册；目标或窗口不同、漏例、重复、事后发布及非有限概率直接拒绝，不回退到常数参照。

模型和参考按case ID配对同一可评估子集的实际事件，比较各自Brier损失。逐例参考值不能预先平均成常数，也不按输入列表顺序配对。原配对Hoeffding单侧界及Bonferroni分配仍适用其原有独立有界假设，未把参考异质性改成新置信度或权威分；主体相关性和预注册执行仍须外部核验。输出 `baseline_comparison` 明确标记常数／逐例模式，来源与参考强度都没有本地认证。

在未绑定方案的旧人工记录上，同一组1000条预测相对0.5常数有Brier技能0.75，但更强逐例参考使技能变为−24；预测和结果记录哈希不变。这种对照现在只保留为诊断，两个方案均不能靠这些无绑定记录通过协议门槛；已绑定记录不能换基线方案重用。这只说明技能依赖所选参照，不是任何术数的现实成绩。参考依据为[ECMWF逐例Brier定义](https://www.ecmwf.int/sites/default/files/elibrary/2006/74335-application-and-verification-ecmwf-products-member-states-and-co-operating-states_0.pdf)和[Hoeffding独立有界和](https://doi.org/10.1080/01621459.1963.10500830)。后见结果后挑选基线、同一资料反复调参和真实来源造假均不能由数值门槛解决。
