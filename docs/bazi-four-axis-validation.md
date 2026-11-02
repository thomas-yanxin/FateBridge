# 八字四项验证与本轮修正

后续的太阳时算法修复、73,414个JPL逐日参考、根气／财库深化和预注册政策约束见
[太阳时与根气审计](bazi-solar-and-roots-audit.md)。本文保留上一阶段的结果与范围。

“历法计算正确”“符合指定原典”“解释忠于结果”“预测现实有效”需要四套不同的证据。
有限测试全通过不能推成四项满分，也不能合成一个“权威分”。本轮提供可复跑审计，
继续暴露失败、未知及未覆盖项。

| 维度 | 本轮实际结果 | 范围与缺口 |
| --- | --- | --- |
| 历法 | HKO 独立公布时刻 72/72 在60秒容差内；修复默认日期的出生地时区 | 覆盖2026–2028年；不是全部支持年份、历史地方时或换日流派认证 |
| 指定原典 | 冻结10例取格名称10/10；可裁定旺衰仅1/3符合，另7例未知 | 这10例已用于开发，不能再称盲测；完整成格、相神和取用语义未验收 |
| 解释忠实 | 修正三项专题的计数越界、合冲遗漏及“未提供”误报；增加确定性反例及三端回归 | 只证明已覆盖程序模板；真实大模型逐句证据归因尚未评估，其余旧模板仍需继续外审 |
| 现实预测 | 新增二元事件评估器；没有真实预测记录，返回 `not_tested` | 需独立留存的事前预测、明确定义的事件、全部登记样本、外部核实结果与基线 |

## 计算与原典规则

综合命盘先建立同一份出生计算上下文，再用该上下文的时区解析默认分析日。
例如 `as_of=2026-10-12T02:00:00Z` 时，纽约应为10月11日；REST、原生MCP和CLI必须一致，
并继续只归一化出生时间、排出生四柱各一次。

月令选择 `month_command_qualified_officer_v3` 延续实际禄刃资格与杂气候选，补上限定的
“本气正官、财印透出辅助”分支。仅在非四墓、透出的月藏干不超出官财印、未见食伤七杀透干、
且没有月支参与的完整三合局时应用；不据此裁定成格或财印作用成立。
遇到完整会局时保留会局处理，不能把一个官格规则推广为所有月份均不变格。
`legacy_label` 保留旧版“本气比劫即禄刃／其余优先透干”的结果供审计。

依据为[《秘本子平真诠》国图藏本影印](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)，
本轮重新下载并核对SHA-256：`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`。
PDF31–32的用神变化与PDF65–66的正官章分开阅读；薛例的印透不自动替代官格，
孤官例的戊未也不因己劫财而具阳刃资格。冻结原典预期未修改。

十二长生输出另列 `hidden_stem_roots`，只表示同五行藏干是否存在。
兼容字段 `strong_roots` 仍保留旧阶段集合，但附 `strong_roots_scope`，
快照不再把乙午、丁酉的阴长生写成已确认强根。两类观察都不裁定根深或有效力量。

## 专题解释修正

- 学业：分数保持兼容的固定计分，标为未校准规则索引，并公开分项公式；层级改为索引区间。
  官印、食伤印的计数同现不再宣称成格、高学历或智力优势；学科类比保留并列计数，需成绩与兴趣核实。
- 六亲：偏财、正印、比劫只返回计数与传统对应；宫位六合、六冲保留字与位置。
  不从计数推亲人存在、人数、慈爱、亲疏或实际助力。
- 桃花：神煞目标与实际命中分开；同时有合、有冲时全部保留端点。
  不再由合冲给他人贴“正／烂桃花”标签，也不把星多解释为追求者多、必然婚嫁或添丁。
- 学业与桃花时间输出：`assessment_status` 区分 `missing_timing_input`、`no_matching_rule` 与 `matched`。
  空命中不是缺输入，也不代表现实不发生事件。

三模块公开相同 `counting_basis`：非日干每次1，所有柱支每个藏干每次0.5；
跳过日干、保留日支藏干。这是固定出现量，不是传统旺衰的数值测量。

## 现实预测与同次引用核验

复用[四项独立验收](prediction-validation.md)中的 `StudyPlan/Forecast/Outcome` 与
`verify_calculation_claims`，不另建预测记录格式。登记、固定队列、事前预测、外部核实、
基线、覆盖率、Wilson区间和Brier指标的使用条件，以该文及实际Schema为准。
另补充可声明的训练主体清单以检查队列泄漏，以及按固定五档报告概率校准；
没有声明训练清单时保留未知，不将其解释为已经检查无泄漏。

本地填写的时间、来源引用及散列不能自行证明事前登记或独立核实；
空示例仍返回 `real_world_efficacy=not_tested`，合成数据不能认证现实效果。
本轮四项审计聚合现有72个官方时刻、冻结原典对照、指定模板反例及空评估流程，
保持 `overall_score=null`、`four_axis_full_marks=false`、`authority_certified=false`。
不把已用于开发的案例重新标记为盲测。

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python scripts/audit_bazi_authority.py --output /tmp/bazi-four-axes.json
uv run --locked --extra dev python scripts/audit_prediction_study.py --plan docs/examples/prediction-study/plan.json --forecasts docs/examples/prediction-study/forecasts.json --outcomes docs/examples/prediction-study/outcomes.json --as-of 2028-01-02T00:00:00Z --output /tmp/bazi-prediction.json
uv run --locked --extra dev pytest -q tests/test_bazi_authority_boundaries.py tests/test_prediction_validation.py
```

四项审计退出1表示尚未满足全面验收；不是命令运行失败。单独评估命令退出0仅表示报告写入成功。
本轮工程验收与源码指纹另存本地验证记录（本地数据：`validation/bazi-authority-local-verification.json`），
四维数据见审计快照（本地数据：`validation/bazi-four-axes-local.json`）。没有真实数据的缺口不能由代码或承诺补齐。
