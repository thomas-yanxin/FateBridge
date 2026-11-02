# 八字精度深化：均时差、原典根类与预测证据

后续增加JPL逐日独立来源对照、财库／藏干财根修正、性格并列保留与预注册协议完整性检查，
见[太阳时与根气审计](bazi-solar-and-roots-audit.md)。已有Swiss算法与根类实现继续复用。

本轮继续沿四项能力改进计算和验收。历法、原典规则、结果表达与人事预测各用对应证据，不把天文事件可计算改名为八字人事预测已验证，不用新加的规则探针替换既有原典失败。

## 真太阳时的实际精度缺口

旧均时差使用 `B=2π(doy-81)/364` 的三个三角项，只取本地年内日期。它忽略真实出生瞬间、年际差异和一天内的连续变化；同一物理瞬间在日界线两侧可能取到不同日期，从而计算不同均时差。

当前改用 `swiss_time_equ_utc_instant_v1`。先将明确的出生钟时转为UTC，按UT输入调用 Swiss Ephemeris `time_equ`，将返回的日数乘1440得到分钟，再与经度和夏令时修正合并。[官方接口第9.4节](https://www.astro.com/swisseph/swephprg.htm)与当前安装包文档均说明其输入为UT、输出为真太阳时减平太阳时。历史文档其他章节存在旧ET措辞，不据旧标题改传TT。

UTC在这里近似UT1，没有观测DUT1；不能声称获得秒以下的实际太阳钟时。Swiss内部所用数据或分析模型由共享运行环境管理，`time_equ`本身没有返回逐次后端标志，不能只凭该函数名称宣称使用了DE431。缺少已声明的Swiss依赖时显式报错，不静默回到旧简式。经度修正专用规则仍可独立运行。

时间回执新增 `equation_of_time_method`、`equation_of_time_time_scale` 和 `solar_time_strategy`，使完整视太阳时与只修经度的规则可区分。关闭真太阳时的既有结果保持直接民用钟时口径。地方时的夏令时歧义继续要求明确偏移。

### 独立参考保留完整原表

NOAA原始表及提取记录（本地数据：`../tests/fixtures/noaa_solar_v1/reference.json`）来自[官方计算资料](https://gml.noaa.gov/grad/solcalc/calcdetails.html)链接的全年ODS原文件（本地数据：`../tests/fixtures/noaa_solar_v1/NOAA_Solar_Calculations_year.ods`），SHA-256为 `28b4c196700e2a57e0ff32c4c88729d5506e3b8f425700ece71397e801a0b0a6`。

期望值取ODS保存的数值缓存，包含2010-01-01至2011-01-01共366条带日期记录，全部保留。B4为固定UTC−7，表内当地正午对应19:00 UTC；D列日期、E列日内比例、F列儒略日、V列均时差分别核对。生产代码不生成参考数值。

同一批记录预设容差为60秒：旧简式有9条越界，最大差异约61.30秒；新算法366条均在容差内，最大差异约3.01秒。这里报告观察到的差异，不把它改写为跨年份的3秒精度保证。NOAA已说明该计算器停止维护，电子表格适用1901–2099；这一批有限比对不是机构认证，也不替代其他历法年份、历史地方时或实际测量。

虚构边界回归为2024-12-06 00:52、UTC、经度0°、开启真太阳时。旧式校正仍在00时，新式已过01时，时支从子切换为丑；REST、MCP、CLI应返回同一结果。另核对闰日、跨日界线同一瞬间、夏令时和不可用依赖。

## 原典根类与数值根量分别呈现

依据[国家图书馆藏《秘本子平真诠》书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)PDF22–23、书页13–14，新增 `ziping_root_categories_v1`。它提供根类证据，不改写现有数值旺衰判级。

| 所选原典的区分 | 当前形式化 |
| --- | --- |
| 长生禄刃与墓库余气的轻重不同 | 分列禄根、阳刃根、阳长生根、同气旺地根、墓库和余气；不换算成数值倍数 |
| 墓库须对应日主五行 | 甲未、丙戌可查同气库根；乙戌、丁丑不因十二阶段显示墓就补造木火根 |
| 余气不等于藏干数组序号 | 乙辰、丁未按对应五行余气记录，不把排序直接当力量等级 |
| 阴长生不能照搬阳长生 | 乙午、丁酉保留原典轻根参考，同时明确无同五行藏干；两条事实不能互相抹掉 |
| 阴干旺地根与阳刃格不是同一资格 | 癸亥、乙寅可记录帝旺同气根，不能因此套五阳干的月刃取格 |
| 合冲会影响根，须辨条件 | 保留冲的具体对端与位置，`effect_status=root_effect_not_adjudicated`；没有直接宣布失根或解冲 |

根类开发探针（本地数据：`../tests/fixtures/bazi_roots_v1/reference.json`）手工录入原文例子，不由新算法生成；这是有限规则检查，不是新的完整命例盲测。工程扩展条件及阴旺根还各有反例回归，不能与原文逐字例子混称同一标注来源。

根类可在标准命盘的 `bazi_birth.classical.root_profile`，以及综合／专题的 `structure_profile.evidence_chain.classical_root_profile` 或 `evidence_chain.classical_root_profile` 读取。`global_strength_status=not_adjudicated` 必须保留。程序摘要逐项呈现实际根类，不把“有根”自动写为“身强”。公开 `roots` 字段视图同时提供数值日主判级与时间回执，便于对照不同依据。

梁、谢两例的现有数值模型仍判弱；原文明示标签仍保留强，原典总审计仍是取格名称10/10、可裁定强弱1/3，另7例未裁定，成格／相神完整验收仍未通过。根类改进暴露了模型对根的分类与赋权差异，没有将新解释当作修复强弱误判的证据，也没有修改冻结命式、预期或分母。

```bash
uv run --locked --extra dev fatebridge bazi_birth \
  --birth-year 2024 --birth-month 12 --birth-day 6 \
  --birth-hour 0 --birth-minute 52 --gender 男 \
  --birth-timezone UTC --birth-longitude 0 --use-true-solar-time true \
  --analysis-year 2026 --analysis-month 10 --analysis-day 12 \
  --fields bazi_birth.four_pillars bazi_birth.classical.root_profile \
    bazi_birth.person_info.time_adjustment \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

## 现实预测：点估计与证据门槛分开

评估器升级为 `preregistered_binary_evaluation_v2`，`registered_numeric_gate_met`表示点估计及覆盖条件，
`preregistered_performance_gate_met`还要求协议声明完整，`statistical_evidence_gate_met`进一步要求统计界通过。
三者不能互换。样本准确率全对、Brier点估计超过基线、统计证据足够以及外部真实性成立，分别是不同判断。

新增门槛依据[Hoeffding原论文](https://doi.org/10.1080/01621459.1963.10500830)的独立有界变量上界，并按事先登记的 `planned_evaluations` 使用[Bonferroni分配](https://www.itl.nist.gov/div898/handbook/prc/section4/prc463.htm)。默认只登记一次检验；软件不能鉴定实际是否额外偷看结果，执行情况仍须外部核验。

设固定基线概率为 `b`、预测为 `p_i`、二元结果为 `y_i`、注册最低Brier技能阈值为 `s`。逐主体取 `Z_i=(1-s)(b-y_i)^2-(p_i-y_i)^2`，范围为 `[-1,1-s]`。计划共检验 `m` 次，总体单侧置信水平为 `c`，其均值的保守下界为：

```text
lower_excess = mean(Z) - (2-s) * sqrt(log(m/(1-c)) / (2*n))
```

只有下界大于0、原点估计门槛成立、全队列可评估且满足注册最低样本数，新统计门槛才通过。以默认95%水平、0.5基线、最低技能0作虚构数学例：10/10预测全对仍不足以通过此保守界；100/100在一次预定检验中可通过，但将检验次数事先设为两次时，同一批记录又不足以通过。这些数字只验证公式和门槛行为，不是现实预测记录。

此界假设独立主体、固定模型／解释政策及固定基线；不要求正态分布，但较保守，不是所有研究设计的最佳统计方法。重复主体、聚类事件或未登记的多次检验不满足这里的条件。计划参数、样本目标、窗口和队列应在看结果前冻结；不能看分数后修改置信水平或反复换终点。详见[预测验证流程](prediction-validation.md)。

当前没有可评估的独立现实预测记录，空示例继续输出 `real_world_efficacy=not_tested`，数值、完整预注册及统计门槛均为false。既不填补虚构成功样本，也不把合成数学用例计为效度。

## 复核

```bash
uv run --locked --extra dev pytest -q \
  tests/test_solar_time_astronomy.py tests/test_classical_roots.py \
  tests/test_bazi_accuracy_depth_transports.py tests/test_prediction_evidence_gates.py

uv run --locked --extra dev python scripts/audit_bazi_classical.py \
  --output /tmp/fatebridge-classical-depth.json
```

原典命令仍应以退出1表示未完成验收。工程全量检查、Linux黄金字节对照、真实大模型解释归因与现实研究执行需要各自的回执，不从本页的有限对照外推通过。

本轮源码快照、1,333项专项验收、完整测试失败清单及后续复核见本地验证记录（本地数据：`validation/bazi-accuracy-depth-v5.json`）。较早快照的全量失败保留原状，后续专项通过不替代最终全仓验收。
