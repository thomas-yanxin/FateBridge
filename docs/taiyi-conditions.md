# 太乙卷四组合条件与独立历史参照

`taiyi.condition_assessment` 把卷四《推五将发不发》的三项条件连接到同次结果的 `taiyi.patterns`。年、月、日、时计都按自己的盘核对，不另起盘，也不使用奇门八门替代太乙八门。

| 原典条件 | 本次读取的实际阻断关系 |
| --- | --- |
| 始击无掩击 | 始击的掩、击，包含实际前后/内外细分 |
| 文昌无囚迫 | 文昌的囚、迫，包含实际内外辰/宫细分 |
| 主客大小将无相关 | 已实现主客交叉将同宫及文昌与四将同宫的补证读法；同阵中五互关仍未裁定 |

三项必须同时满足。每个条件保存三值 `satisfied`、全部 `blockers` 和 `unassessed`；阻断项通过 `source_path` 指向 `taiyi.patterns.N`，未决项的 `basis` 指向同盘实际位置。快照使用同一份结果，不把未定写成不满足，也不把不满足写成现实失败。

[正宫提挟](taiyi-enclosures.md)另按同盘的三个主体核对，并明确保留挟闭、四郭固杜未评估；它不是本条五将三项中的额外阻断。[将目关系](taiyi-eye-relations.md)已由V13具体局注补证扩充，不冒认各版本完全一致；同阵大小将范围仍未裁定。[主方对宫](taiyi-oppositions.md)另保留格／对异称与原注不符，也不新增为本条第四项条件。

这里的 `five_generals.conditions_satisfied` 只回答这三条所选空间读法。同阵数齐的范围未决时，无阻断也只能返回null。`assessed_conditions_satisfied`另存旧的已实现关系列表合取，不能用它代替完整结论；单项也保留`assessed_satisfied`。缺少同盘核心位置时，不凭一个空关系列表证明全部满足。

年、月计另附[太乙八门](taiyi-gates.md)后，`three_gates` 核对所选门盘的太乙与文昌，`menju_jiangfa` 为两层三值合取：任一层明确不满足则合取false，否则只要一层未知即为null，只有两层明确满足才为true。三门未评估的状态和原因始终保留；false合取不表示三门已被判为不具。纯五将函数不补门。例如阳23局的文昌“对”不属于本条囚迫，三项在所选读法下满足；三门未评估时仍不能确认门具将发。

V15以实施前冻结的4条中位局注（本地数据：`../tests/fixtures/taiyi_jinjing_v15/center-notes.json`）补核中五事实：阳7客算、阳32/35/36主算均25，两将不出中位。原文“不出”保留，但不因此强行把中五定义为关，也不插入五将第四项。阴阳144软件循环盘有42盘出现同阵同宫，其中21盘原本因未列关而返回满足；现在保留未知，其余已有阻断仍为false。42/21是软件影响统计，4条局注不是4完整命盘。既有八个合成布尔例不改；新增9个两层、27个三项的完整三值真值表（本地数据：`../tests/fixtures/taiyi_jinjing_v15/truth-table.json`）另标为合成逻辑验收，不作为古例或全书正确率。

规则作者FateBridge contributors，版本`jinjing_vol4_five_general_conditions_v1@1.2.0`；卷四仍为三条，卷三同阵相关范围及完整断法继续待裁定。来源和实施前冻结范围见V15清单（本地数据：`../tests/fixtures/taiyi_jinjing_v15/manifest.json`）。原预期冻结后又补核原书影像（本地数据：`../tests/fixtures/taiyi_jinjing_v15/facsimile-check.json`），未改初始预期或原清单。

## 版本与核验材料

正文取[《太乙金镜式经》卷四](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷04)，另核[NCL-06604明钞本](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf)图55/56。原HTML、文本、影像与指纹在v4清单（本地数据：`../tests/fixtures/taiyi_jinjing_v4/manifest.json`）。三项条件的八种布尔组合是**合成边界测试**，不是八条古代课例；阴阳144局的字段路径检查也不是144条现实应验。

另引入何丙郁[《太乙术数与〈南齐书·高帝本纪上〉史臣曰章》](https://www1.ihp.sinica.edu.tw/Publications/Bulletin/111/Article/426)（中研院《史语所集刊》67.2，1996年，383–413页）提供独立数值参照。人工冻结其389页列表和390页首行续文，以全部10条年份为输入，核入360局数、太乙宫位与理天/地/人，共30项；不从生产代码生成预期值，也不筛掉失败年份。

这批参照29/30项相符：元徽二年（474）刊载“二百三十一局、六宫、理地”，程序与前两项一致，依每宫三年理天/地/人通则得到“理人”。放大核读确认了刊本“理地”，双方值保留在历史参照审计（本地数据：`validation/taiyi-jinjing-v4/historical-report.json`），脚本仍退出1。论文388/389页另把兴宁二年括注为346年，而389页表内锚用364年；未拿这个括注改动起元或删去后续课例。

公元前202年的参照使用明确的历史年与天文年换算，仅核循环核心。公共历法适配器并未因此支持古代公历日期，也未据政治史叙事验证现实预测。完整目标和原有44项表文分歧仍见总验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）。

## 读取与复现

调用合同的太乙 `conditions`、合参 `taiyi_conditions` 视图同时提供组合条件、实际关系、时间层和规则来源。视图名只是选字段的任务卡，不是计算参数。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 4 --analysis-day 4 --analysis-hour 12 \
  --analysis-timezone Asia/Shanghai --no-use-true-solar-time \
  --strict-fields --fields taiyi.condition_assessment taiyi.patterns taiyi.ruleset
uv run --locked --extra dev python scripts/audit_taiyi_historical.py \
  --output docs/validation/taiyi-jinjing-v4/historical-report.json
uv run --locked --extra dev python -m pytest -q tests/test_taiyi_conditions.py \
  tests/test_taiyi_transports.py
```

工程测试与独立历史参照审计分别报告，具体源码、接口和投影检查见v4工程记录（本地数据：`validation/taiyi-jinjing-v4/engineering.json`）。这些结果不认证全书符合、完整古历、三式联合断法或真实模型自由解释。
