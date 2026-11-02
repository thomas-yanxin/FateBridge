# 八字太阳时、根气与解释准确度审计

本轮修复共享太阳时计算及财务、性格解释，并为综合八字和九项专题增加原典根气证据。
四项能力分别验收；没有将回归测试数量、原典命例或合成预测数据换算成权威分数。

## 已修复的计算问题

旧均时差只按年内日期套用364天周期近似式，忽略年份、闰日和日内时刻；临近时辰边界时足以换错时柱。
先实现并冻结了以完整UTC瞬间求值的 Meeus/NOAA 太阳方程候选；合并时保留主工作区已完成的
Swiss Ephemeris `time_equ` 实现，继续用独立JPL资料验证，没有以精度较低的候选覆盖它。
另外修复已有时区的输入被直接更换时区标签的问题，改为转换同一瞬间；
明确的UTC瞬间可以解析夏令时回拨，未消歧的本地出生钟仍不能自动猜选。
`time_adjustment.equation_of_time_method`、`equation_of_time_time_scale` 记录实际算法及时间尺度。

公式依据 [NOAA源程序](https://gml.noaa.gov/grad/solcalc/main.js)与
[计算说明](https://www.gml.noaa.gov/grad/solcalc/calcdetails.html)。该计算器已停止维护，
引用公式不等于获得NOAA认证。独立期望来自 [NASA/JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html)
的太阳目标、格林尼治地表视太阳时（量34）与UT1−UTC（量49），原查询和原响应全部保留。
LAT−LMT与UTC/UT1的差别按响应中的DUT1处理；1962年前Horizons的UT直接采用UT1。

| 对照 | 样本及事先固定条件 | Meeus/NOAA候选最大误差 | 旧算法最大误差 |
| --- | --- | --- | --- |
| 开发组 | 2000、2026年，每月15日12 UT，共24个；容差5秒 | 2.694秒 | 79.468秒 |
| 首次保留组 | 1900、1950、1984、2025、2050、2100年同样取样，共72个；整年隔离 | 3.174秒 | 81.166秒 |
| 后续范围扫描 | 1900-01-01至2100-12-31，每日12 UT，共73,414个；候选算法、容差未改 | 3.948秒 | 91.066秒 |

上述候选全部有限样本均在5秒容差内。首次比较前已冻结候选源文件SHA-256为
`fea19ba2d4666a119a23947b7f1ce0c7ee6bfff1ee1747eef68abeab0328b3e8`。
后续逐日扫描是扩大范围的探索验证，不能重复计为新的盲测。冻结记录与结果见
候选记录（本地数据：`validation/bazi-solar-candidate-v1.json`）、原候选源码（本地数据：`validation/bazi-solar-candidate-v1.py.txt`）、
原候选首次审计（本地数据：`validation/bazi-solar-jpl-v1.json`）。

最终共享实现采用Swiss Ephemeris，以同一批73,414个JPL逐日午时参考复核，最大误差约**0.209秒**，
平均约0.056秒，全部符合原5秒容差，详见合并后审计（本地数据：`validation/bazi-solar-swiss-jpl-v1.json`）。
此时资料已经公开给本次开发者，必须记作独立来源回归，不能把前一候选的首次保留组身份转移给新实现。
独立资料在 `tests/fixtures/bazi-solar-jpl-v1.json` 和 `tests/fixtures/bazi_solar_sweep_v1/`，
包含原始响应、请求及散列；生成器拒绝覆盖既有冻结版本。

一个实际边界反例是：2026-02-15 09:14，Asia/Shanghai，经度120.1°，启用真太阳时。
旧式校正约为08:59:49，落辰时；新式及另外保留的JPL参考约为09:00:19，落巳时。
这验证的是指定输入的太阳钟与时辰；年、月柱仍按同一出生物理瞬间判节，不用校正后太阳钟挪动交节。

此处不是全历法认证：逐日午时不能覆盖所有时刻；程序用UTC近似UT1，不提供实时地球自转观测值；
经度、历史时区、出生钟记录及秒数不确定性仍需分别处理。JPL远期DUT1也不是未来实测值。
旧有香港天文台72个分钟级节气对照仍独立保留，不混入太阳时样本数。

## 原典知识及专题修正

所选原典为沈孝瞻《秘本子平真诠》，国图藏本 `NLC416-11jh010455-35296`，
[原书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)
SHA-256为 `71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`。
PDF页序自1起。没有混入其他书的条文并统称原典结论。

| 原典定位 | 新增或修复 | 仍未裁定 |
| --- | --- | --- |
| PDF22–23，根气与长生禄旺 | 分开记录同字根、同五行根、墓库藏根、本气／余气与长生禄旺；阴长生另列参考，既不捏造藏干，也不简单否定其原典意义；浮干比劫另列 | 无普遍数值倍率；根损、相对身食财力量及整体身强弱仍未知 |
| PDF43–45，墓库刑冲 | 财库只记录真实库支、六冲端点与层次；`clash_present`为事实，`opened=null`表示尚未裁定；流年无本命财库／实际冲时不凭库支输出进财 | 冲不自动等于开库、成格或发财 |
| PDF76–78，食神 | 月令选择确为食神才进入食神生财前提检查；财透、实际根及阴长生参考分列 | 身、食、财相对力量、破救及完整成格仍为 `not_adjudicated` |

综合及九专题复用共享 `evidence_chain.classical_root_profile` 返回以上可追溯观察，
财务另有 `wealth_analysis.classical_context`，可从公开 `depth` 视图读取。
月令格局用神与扶抑元素继续分开。冻结十例取格名称仍10/10，可裁定旺衰仍1/3，
另7例原文未知；没有改预期、给未知补标签或把新增局部反例冒充独立完整命例。

财务修复了“完全无财仍说藏财”和只看支本气漏掉藏干财根受冲的问题；
规则分数明确为未校准索引，不推收入、投资收益或财力。
性格保留最高及第三位的全部并列十神，不再由枚举顺序选唯一主性格；
日主模型的强弱也不再直接推出外向、依赖性或决断能力。现代映射明确作为讨论线索。
根类的更细区分复用[已有深化实现](bazi-accuracy-depth.md)，不保留重复的第二套根类判据。
公开知识查询的8条财务、3条性格释义同步修正，防止计算已经改正后，查询仍返回“冲库必进财”或“强弱定外向”等旧说法；
原典条件和现代类比分列，三端读取同一知识正文。

## 现实预测与防止指标取巧

复用现有 [StudyPlan／Forecast／Outcome评估器](prediction-validation.md)，
新增解释政策散列绑定、基线冻结时刻及外部登记引用检查。
缺少这些承诺或训练主体声明，仍可计算描述性指标，但只能报告数值门槛，不能通过完整预注册门槛；
即使合成样本全部命中也一样。更换解释政策的预测被拒绝，避免计算模型未变却事后改解读。

本地登记字段仍只是声明，不能自动认证外部登记真实性或盲法。
当前无真实独立预测与结果，`real_world_efficacy=not_tested`。
四项总审计保留 `overall_score=null`、`four_axis_full_marks=false`、`authority_certified=false`。
后续应在未见结果前冻结事件、解释政策、队列和基线，再逐批纳入外部核实结果；
不使用已见命例、幸存样本或事后重定义事件取得分数。

```bash
uv run --locked --extra dev python scripts/audit_bazi_solar_accuracy.py --with-sweep --output /tmp/bazi-solar.json
uv run --locked --extra dev python scripts/audit_bazi_authority.py --output /tmp/bazi-four-axes.json
uv run --locked --extra dev pytest -q tests/test_bazi_solar_accuracy.py tests/test_bazi_root_and_wealth_rules.py tests/test_prediction_validation.py
```

总审计退出1表示仍有未验收维度。解释检查只覆盖程序模板及结构化引用；
本轮未运行真实模型逐句语义验收，也未部署或发布。最终工程结果另见
本地验证记录（本地数据：`validation/bazi-solar-roots-local-verification.json`）。
