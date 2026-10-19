---
name: onda-shiyun
description: 用 FateBridge 的八字、紫微或西占时运计算，说明当前阶段、当年与月度节奏；按实际边界交付简明时间线或候选时段对照，让用户据此安排现实准备。Use when 用户问今年明年运势、大运流年流月、人生转折、何时做事、择日、本命年或运势起伏；仅在有相应粒度结果时细化，不预言具体事件。
---

# 人生时运与候选择时

用户明确要求完整结构、全部时间线或保存完整文件时，第一次调用必须设 `fields=null`（CLI 省略 `--fields`），保留默认响应预算；本技能的精简首轮字段只适用于普通摘要咨询。随后用 `result_delivery` 读取同一 run，不能先裁成摘要再补算全文。

来问时运的人，要的是「我现在在哪一段、接下来大概什么节奏」。盘给的是节奏感，不是日历上的判决。

## 共用范围与安全

先读[咨询硬边界](../_shared/safety-boundaries.md)与[本轮范围及多视角选择](../_shared/consultation-routing.md)。按当前问题展开，首轮明确要求详细就覆盖；不自动附带全部相关主题。时间追问读[共享时间选择](../_shared/timing-selection.md)，保留原主题与已有相关视角，只补需要的新层。生死、临床判断与医疗择时在选法前停止。

## 用户能得到什么

先回答所问时段最有参考价值的变化，挑 2–3 项实际依据，再给一项现实准备。短答不需要铺全部技法；只有时间之间确有可比较的返回，才用时间线或短表。

| 本次问题 | 实际计算依据 | 合适的交付 |
| --- | --- | --- |
| 当前处在哪段／今年怎样 | `dayun_analysis`、`liunian_analysis` 与当前 `liuyue_analysis` | 分开讲阶段背景、当年主题和当前月，指出同向与分歧；不把当月扩写成全年每月 |
| 全年月份／某段安排 | 明确所需范围后，选择 `analysis_calendar.liuyue_timeline` 及实际起止边界 | 以“时段／有何区别／准备什么”列出最相关的几段，完整请求保留全部；节气换月和公历月不混写 |
| 西占推运／紫微运限 | 相应聚合的实际时间主星、时间线、运限或四化，按该体系读取 | 说明哪些层是阶段背景、哪些落在目标时点；各体系分开署明，不把多体系同向当作预测有效性的证据 |
| 明确活动择时 | `astro_election` 的实际候选与条件 | 对照已计算候选和用户的现实可用时段；普通运势不能替代择日结果，吉时也不保证活动结果 |

全年时间线在普通首轮字段之外：问题本来就要求全年结构或全部时间线，首次即 `fields=null`，随后读同一 run 的 `result_delivery`；首轮只做摘要时不能声称未保留的月份已交付。没有真实时间差异就直接说明，不为表格补出“更旺”的月份。准备动作如核对项目截止、预算或沟通安排，来自现实建议，不能写成计算出的事件。

用户把某个月与另一年比较时，开头就说明粒度不同，再分清未变的长期背景、新目标实际返回的信号和仍不可比较的部分。月度十神与年度十神不同，不足以推出后一年的责任、收入或压力比前一年更强；只有同粒度、同口径的依据才作强弱比较。年度仍有某主题，就说“仍有”，不把不变结构包装成新利好；不为凑出升降额外跑齐所有专项。

解释 `element_changes.original/new/change` 时核对参照基准：每次“增强”可能都是相对本命，不是比上一次分析继续增加。跨年比较同一元素，应比较两次对应的 `new` 值；若两年都高于本命、后一年反而降低，就分别说明，不能只重复“仍增强”。这些权重变化本身仍不证明收入、精力或事情成败变化。

## 引用路径

发现入口可能是软链接。优先进入入口目录后用 shell 内建 `pwd -P` 取得真实目录，再按它读取下面的相对引用；不要为解析路径调用未经核实的系统 `python3`。不能先裁剪 `.agents/skills/onda-*` 入口的字符串父目录，否则会误指到 `.agents/skills/_shared` 或 `.agents/docs`。读取已知引用无需搜索仓库。

## 共用参考
- 计算怎么调：[../_shared/fatebridge-engine.md](../_shared/fatebridge-engine.md)
- 怎么开口说话：[../_shared/onda-counsel.md](../_shared/onda-counsel.md)
- 场景取舍与去重：[../../docs/scenario-routing.md](../../docs/scenario-routing.md)

大运起运、流年干支、节气换月与星历推运全部交给引擎，不能用临时手算或模型记忆代替。

调用纪律与去重见 [引擎调用纪律](../_shared/fatebridge-engine.md#全局调用纪律) 与 [交叉印证与去重](../_shared/fatebridge-engine.md#交叉印证与去重防矛盾)。

## 这个场景用哪些工具

本技能主持无主题限定的整体节奏、人生阶段或活动候选时刻；“今年事业／明年感情”仍由相应主题主持，读取共享时间参考即可，不转成全主题报告。

- 阶段：`dayun_analysis`、`ziwei_horoscope`、`firdaria` 等均为正常候选。西占按需 `zr`、`decennials`，不是所有阶段问题都需专家模式。
- 中式聚合 `timing_analysis`，单层为 `liunian_analysis`、`liuyue_analysis`、`liuri_analysis`、`liushi_analysis`；紫微动态用 `ziwei_horoscope`，静态列表不是动态计算。
- 西占多层用 `western_timing_analysis`；窄查按需 `profection`、`solarreturn`、`lunarreturn`、`transit`、`solararc`、`givenyear`、`pd`、`pdchart`。已有聚合不再跑其单层。
- 活动用 `astro_election` 评估给定候选；没有连续区间自动最优搜索，不提供医疗择时。
- 历法支持 `jieqi_timeline_analysis`、`jieqi_year`、`nongli_time`。
- 其他生命周期技法：`astro_planetary_ages`、`astro_triplicity_rulers`、`astro_lunation_phase`、`astro_distributions`、`astro_harmonic`、`astro_balbillus`、`astro_keypoints`、`astro_yearsystem129`、`astro_planetaryarc`、`astro_persiandirected`、`astro_agepoint`、`astro_vedicprog`、`astro_jaynesprog`。按其实际分期能力与本轮问题选择；`astro_mundane`、`astro_extrareturns` 为明确相关方法请求的补充。

生命周期和指定技法按[任务参考卡](references/techniques.md)选择，先明确新增信息、所需参数和实际业务根，不只取 summary。西占聚合首次按工具发布的 stage／annual／short_term 任务卡复制 `fields`，不要发送卡名为参数。完整粒度、时间边界、同口径比较、范围复用及西占返照／行运覆盖限制统一见共享时间选择；不把阶段切换日期写成现实事件必发生日期。

## 怎么收信息
个人运限核对出生年月日时、适用性别规则、城市／时区（西占推运需要经纬度 `--birth-latitude/longitude`），以及已要求的年／时段／年龄。活动择时 `astro_election` 使用候选时间与活动地点，不收出生资料；节气／农历换算也只核对所选日期，不套出生问卷。

一次核对缺项、历法及出生时区，出生与分析时间分开。综合首轮保留实际 `analysis_datetime`、时间校正及分析日历中的时区、当前／下一节气、八字换月边界。未给具体分析时点才使用当前值，复现用带时区 `as_of`；不能沿用示例日期冒充今天。

用户只给年或月时，不把自行选择的某日某刻说成用户指定。若确需选月中等内部取数锚点，简述该日期只是计算定位，结论仍限所问粒度；大运切换或节气边界可能影响覆盖时，按实际边界保留限制，不由一个锚点声称全年各时段均已审查。

西占聚合与单项推运都支持 `analysis_hour`、`analysis_minute`，明确时点时同时传入，零点／零分不可遗漏；它们按 `birth_timezone` 解释，换到行运地点只转换同一时刻。不能用 `as_of` 替代明确钟时，也不能让出生10:30覆盖分析12:00。首轮采用西占工具公布的精简字段，保留 `analysis_context.analysis_datetime` 和行运实际时点；大时间线需要时从 `result_delivery` 按字段分页读取原 run，不重复排盘。

## 工作流
1. 按用户已说的时段与目的选择运势或择时分支；只有会改变计算范围时再简短核对。
2. 调引擎：中式综合运势用 `timing_analysis`，只问流年细节才用 `liunian_analysis`。用户更换目标年份，仍要大运背景或月份对照时，直接用新目标的聚合，不先取流年专项再补聚合。纯流年窄查询可用已验证的 `fields=["liunian_info","personal_info","summary","target_year_jieqi"]`，按所问进一步缩小；普通解释不因缺首轮预设就默认 `fields=null` 取全快照。大运段用 `dayun_analysis --analysis-age N`（虚岁必填）。西占整体推运主用 `western_timing_analysis`，用户点名太阳返照或小限才分别调 `solarreturn` / `profection`，不默认连发单技法。
3. 读首轮结构化时运信号，按实际返回的年/月/日粒度和节气边界表述；仅有流年不能推断上半年或下半年。更细节奏只补尚未返回的层，不重算聚合已有内容；全年时间线在明确要求时展开。
4. 给节奏建议，不给死期。
5. 按 [Onda 解读层](../_shared/onda-counsel.md) 自然收尾；建议已在正文讲清就停，不重复排程或强造一句结尾。

## 红线
- 不报「灾年」「劫数」吓人；不下「某月必出事」的死期。
- 不顺的年份，说成「适合收一收、打基础的一段」，给可做的事。
- 核心星盘可回退轨道近似；西占推运缺 backend 时直接报 `dependency_missing`，不能按近似模型继续解读。实际星历模型仍需核对输出。

## 样例

以下使用虚构资料。在已安装并激活的仓库虚拟环境中运行，环境准备见[引擎调用](../_shared/fatebridge-engine.md#怎么调引擎)。已有 MCP 时直接调用，无需执行本地命令。
```bash
# 综合首轮：保留实际分析时间、时区及节气换月边界
python3 -m fatebridge.cli --no-metadata timing_analysis \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 \
  --analysis-year 2026 --analysis-month 10 --analysis-day 14 \
  --strict-fields --no-include-snapshot-text \
  --fields dayun_analysis liunian_analysis liuyue_analysis comprehensive_summary personal_info.analysis_datetime personal_info.time_adjustment analysis_calendar.analysis_date_context.timezone analysis_calendar.analysis_date_context.current_solar_term analysis_calendar.analysis_date_context.next_solar_term analysis_calendar.analysis_date_context.bazi_month_boundary

python3 -m fatebridge.cli --no-metadata liunian_analysis \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-place 北京 --target-year 2026

python3 -m fatebridge.cli --no-metadata profection \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京 --analysis-year 2026

# 生命周期：行星年龄，保留实际段界与主星条件
python3 -m fatebridge.cli --no-metadata astro_planetary_ages \
  --strict-fields --no-include-snapshot-text --fields analysis_context planetary_ages natal_reference \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京 --analysis-year 2026

# 月相推运：本命月相 + 八相时间轴（默认看到 90 岁）
python3 -m fatebridge.cli --no-metadata astro_lunation_phase \
  --name 我 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 --birth-minute 30 \
  --birth-latitude 39.90 --birth-longitude 116.40 --birth-place 北京

# 紫微运限：第三套时运体系，看目标时间点的六层运限+动态四化
python3 -m fatebridge.cli --no-metadata ziwei_horoscope \
  --gender 男 --birth-year 1992 --birth-month 8 --birth-day 15 --birth-hour 14 \
  --target-year 2026 --target-month 6 --target-day 19 --target-hour 14 --fields summary
```
