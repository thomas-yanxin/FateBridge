# 太乙年运十神：卷五起元、巡宫与异文

`calculation_mode=year` 增加《太乙金镜式经》卷五的年度十神计算，另列大游天目。`taiyi.long_cycles` 保存起元、积年、巡宫年序和原表异文；`long_cycle_summary` 是首读摘要。月计、时计不会拿自己的积数冒充年度积数，返回明确的未附年运状态。这里只实现数值巡行，日计另见[金钥匙日计](taiyi-day.md)，完整古历和完整断法仍由总验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续追踪。

## 三组起元必须分开

| 计算族 | 724年积数 | 本次实现的巡行 |
| --- | --- | --- |
| 君基、臣基、民基 | 285011；书中另给近元611，模360同余 | 都从戌起，依次每邦30、3、1年 |
| 五福 | 13331 | 乾、艮、巽、坤、中，每宫45年，225年一周 |
| 大游 | 13331；另给354年至724年371的近元 | 七宫起，按七八九一二三四六顺行，每宫36年，分治天/地/人各12年 |
| 大游天目 | 13331 | 依《推大游天目所在法》七十二、十八取余，从天道未起，坤乾各重留一次；总则216周率、18行率与此条关系仍待独立校勘 |
| 小游 | 3361 | 一二三四六七八九，每宫3年，24年一周；外周240与24同余 |
| 四神、天乙、地乙、直符 | 3361 | 每位3年，顺行一至九再接绛、明、玉；分别从1、6、9、5起 |

八将年计原有积数1937281不用于替代这些起元。各记录包含 `epoch_id/accumulation/cycle_length/cycle_year/years_per_position/position_index/year_in_palace`；起元相差年份按所选农历年减724求得。每个位置年序采用1至行率，满行率后的次年换宫；卷五三元表的甲子、乙丑、丙寅同宫提供三年边界的直接核对。所有原始常数和算例均独立冻结，不从生产函数生成预期值。

年计岁首仍采用已声明的现代民用农历正月初一约定；四柱立春年或真太阳时跨日不改年度。没有宣称这里复原了唐代完整历法。

## 来源和独立核验

原典为[卷五转录](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷05)，底本另核浙江大学图书馆[CADAL06056495扫描](https://commons.wikimedia.org/wiki/File:CADAL06056495_太乙金鏡式經·卷五~卷十.djvu)。起元和五福算例核图4、7、8、12；直符中元争议核图23至31。原始HTML、文本、人工转录720项和相关扫描指纹在冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v3/manifest.json`）。

独立核对不只使用同一规则的重算：卷五明确给出724年五福在辽东第11年，对应艮；[苗润博《被改写的政治时间：再论契丹开国年代问题》](https://www.lhp.sdu.edu.cn/__local/3/FB/9D/4B8E48F090D37A9A92FEFE5F735_279BE8FA_4F736B.pdf#page=104)（《文史哲》2019年第6期，第99页）另给915年君基子邦第22年的完整数学推步。程序逐项验证这两条结果及卷五的三组积数，未把文章中的政治史叙事当成预测应验。另核NCL图71至74明示的904年小游六宫、907年四神六宫、622年天乙玉堂、930年大游七宫、934年地乙明堂、976年直符九宫；这些算例均列入冻结预期值并通过，未据其原文后接的灾祥事例验证现实预测。930年例还约束了大游288年整周的首宫处理。

三元五纪表保留60行、12列共720项，四神、天乙、地乙各180项相符；直符147/180项相符，总计687/720。33项分歧集中在直符中元辛卯至癸亥，扫描确认了这些读数，尚不能仅据程序判断底本错或程序错。审计报告（本地数据：`validation/taiyi-jinjing-v3/report.json`）逐项保留两值并返回失败状态。原先卷三阴阳两算的288项另立审计，不能相加分母后包装成全书准确率。

生产返回 `table_position` 与按正文计算的 `position`，`table_disagreement` 标记本年是否冲突；快照在同一次结果中展示双方读数。原表通过[生成脚本](../scripts/build_taiyi_long_cycle_reference.py)打包，生成过程不调用领域计算。审计比较的是正文算法与独立手录原表，而非拿程序产出反填目标。

四库转录缺少地乙独立推法，NCL-06604明钞本图73/74补出完整正文，明确命起九宫、顺行尽九宫再接绛明玉。该行序与四库三元表相符；`source_method/source_reference/source_edition` 明示补证范围，积年仍用已核四库3361，不混用明钞本另处待核的积年读数。大游天目按所在法求余的实现与总则时率的关系也继续列为未决。

## 盘面与解释

能对应十六宫或中五的标记进入原盘；绛宫、明堂、玉堂另存在 `extra_palace_marks`。这三个名称尚未校定物理方位，不能丢掉，也不能自动寄坤或硬套奇门九宫。十神是传统年度巡行模型，不是天空实测星体经纬度；古代辽东、西蜀等分野不直接对应今天的行政区，更不能凭其单独宣告地区或个人吉凶。

小游与本盘年计太乙同相位，不是第二份独立证据。三式仍分别显示时间层，本次没有把年度十神加进奇门、六壬的胜负投票。各实际结果须连同规则版本、异文和适用层解释。

## 调用和复现

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 4 --analysis-day 4 \
  --analysis-hour 12 --analysis-timezone Asia/Shanghai \
  --calculation-mode year --no-use-true-solar-time --strict-fields \
  --fields taiyi.calendar_rules taiyi.long_cycles taiyi.extra_palace_marks
uv run --locked --extra dev python scripts/build_taiyi_long_cycle_reference.py --check
uv run --locked --extra dev python scripts/audit_taiyi_long_cycles.py \
  --output docs/validation/taiyi-jinjing-v3/report.json
uv run --locked --extra dev python -m pytest -q tests/test_taiyi_long_cycles.py \
  tests/test_taiyi_transports.py tests/test_taiyi_accuracy.py
```

审计仍有33项原表分歧，退出码为1；工程测试验证分歧保留和输出忠实，可以同时通过。工程验收另见v3记录（本地数据：`validation/taiyi-jinjing-v3/engineering.json`），不以此宣布三个总目标满分。
