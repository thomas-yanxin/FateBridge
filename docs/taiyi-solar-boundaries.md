# 太乙节气源与换月、换遁边界

太乙月计以十二节换月，中气不另增月数；至点时计以冬、夏至实际瞬间换遁。这些是已声明的现代适配。独立公布的节气时刻可以核对适配的天文输入，不能证明古代历法、原典岁首或完整断法已经恢复。

本轮以日本国立天文台2025—2027年完整节气表，以及香港天文台2027年十二中气表，验证native和DE440两种明确后端及当时的auto策略。84条刊载记录对应72个不同节气；其中2026年24条已在V2使用，2025、2027年新增48个不同节气，香港12条与日本同年对应项重叠，不能计为12个新事件。来源、初次失败和全部对照见V30验收记录（本地数据：`validation/taiyi-jinjing-v30/README.md`）。

## 时区、精度与来源分别核对

日本表为中央标准时`+09:00`，香港表为`+08:00`。2027年霜降分别列10月24日00:33和10月23日23:33，换算后都是10月23日15:33 UTC。直接比较当地日期会误认差一天；把日本钟面原样当香港钟面输入，也会错一小时。

资料只刊到分钟，本轮保留原有60秒比较容差，未推定未明确注明的舍入方向。三年表中的最大绝对刻度偏移，native约29.635秒、DE440约29.655秒；它们是求解瞬间到刊载整分钟的差，不能解释成物理误差上界。两个后端最大相差约0.031秒，分钟资料不足以据此判定谁更准确，也不能认证返回微秒的物理精度。

换月控制取每条日本记录前后各120秒：十二节应增加一个月计数，十二中气保持同一节月；两种月计配置分别核对。二至控制验证六个至点前后的阴阳换遁，覆盖两种时计和民用／真太阳钟。默认至点时计在所选控制后端置一，金钥匙完整积时不被改成同一计数。固定经度0仅是虚构工程控制，不是恢复出来的古例地点。

两来源或两后端相合，不形成多份独立现实预测证据。机构时刻本身也是历算刊载值，并非本轮实测；软件后端还可能共享模型、常数或参考系。当前三年结果没有覆盖1800—2200全部支持区间，也没有裁定秒级临界输入的独立真值。

## 解释本次实际采用的锚点

先读取`calendar_rules.anchor_name`、`anchor_utc`、`anchor_provider`和实际计数，不把当前节气名称直接当作月计起点。2027年霜降是中气，月计仍以此前寒露为锚点；下面是公开钟面的工程示例：

```bash
FATEBRIDGE_SOLAR_TERM_MODEL=de440 uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2027 --analysis-month 10 --analysis-day 23 \
  --analysis-hour 15 --analysis-minute 35 --analysis-timezone UTC \
  --calculation-mode month --no-use-true-solar-time --strict-fields \
  --fields taiyi.calendar_rules.anchor_name taiyi.calendar_rules.anchor_utc \
  taiyi.calendar_rules.anchor_provider taiyi.calendar_rules.counter \
  taiyi.ruleset.classical_acceptance_passed taiyi.ruleset.real_world_efficacy
```

`anchor_provider=jpl_de440`说明这一个节气锚点的来源。它不表示真太阳钟的每个分量都来自DE440：当前均时差使用Swiss `time_equ`，并以UTC近似UT1；本轮不新增DUT1实测或均时差精度认证。输入民用时刻、计算钟面与年计农历日期仍按[民用时刻](taiyi-civil-clock.md)和[年计日期](taiyi-year-calendar.md)分别读取。

共享auto策略改变后，V29六种旧完整载荷的节气时刻、锚点与来源等字段发生变化，原差异和失败没有重评。本轮分别明确指定native／DE440进行相同机构预期的对照，没有把来源限制放宽为任意字符串，也没有重写冻结日期。native对照保持旧来源，DE440分支必须返回自己的身份；不根据盘面是否有利选择后端。

## 复现和未完成项

```bash
uv run --locked --extra dev python scripts/audit_taiyi_solar_sources.py \
  --output /tmp/taiyi-solar-sources.json
uv run --locked --extra dev pytest -q \
  tests/test_taiyi_solar_sources.py tests/test_taiyi_periods.py
```

审计保留全部252项时刻比较、288项节／中气控制和48项二至控制；组合数不是独立机构样本数。即使这些控制全部符合，脚本仍以退出1保留整体历法验收未完成的状态。原典11项两算分歧、三处始击分歧、古历时实及独立自由解释验收不因这一轮更新而完成；完整总目标清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续适用。
