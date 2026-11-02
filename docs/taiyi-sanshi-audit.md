# 太乙与三式合参：原典、历法与解释验收

V44修复[输入年与邻年节气](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-solar-context-years.md)的端点误拒及模型混用；合参同时修复奇门置闰年表的输入年与来源缓存。原720条端点控制、全部参考根及首轮605／720保留；不增加独立古例或实际模型解释通过数，见V44记录（本地数据：`validation/taiyi-jinjing-v44/README.md`）。

V43补齐[实际节气模型与数据闭包](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-solar-sources.md)：确认V42临时快照因缺少项目星历数据，在503／504年回退Moshier而产生约1.23秒漂移；带回预先冻结的同批37份数据后，原大差异消失，约10微秒的表示差异另保留。两模型28个TT点与8个事后边界反例分开记录，新增同次换节／换遁与冬至起元的模型证据；不据共享模型一致性宣称古历或原典通过。旧报告与模型评分不重判，见V43验证（本地数据：`validation/taiyi-jinjing-v43/README.md`）。

V42补齐[完整计数与纪元坐标](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-counter-cycles.md)：同盘交付360／60／72分解及单位，避免局号、行宫捷数冒充完整积数；未据分组推定实际干支或改默认起点。十卷所选题注包含10条案例，9条在明确坐标假设下有唯一相位，1条题注不相容；数值相符仍不替代完整原例通过。全部差异与旧成绩保留，见V42验证（本地数据：`validation/taiyi-jinjing-v42/README.md`）。

V41补齐[当时法完整条件与四维两支候选](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-dangshi-sectors.md)：同次六壬实际地盘神将全部并列，保持未选寄支；核心十项旧例相符不替代完整古例。明钞五项候选相容只有两项单支直接相符，四库“天定”原字未改，寅时自动夜贵与源例朝条件的负对照保留。两本完整原例均未通过，古历与V25原评分保持，见V41验证（本地数据：`validation/taiyi-jinjing-v41/README.md`）。

V40补齐[当时法贵人逐版对照](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-dangshi-nobles.md)：四库与明钞完整二十项朝暮本位有十项不同，现有通行／探原协纪配置分别对应两版表。三式新增显式选表、同盘实际起点及来源路径，默认不变、不按结果自动选版；本位相符不认证朝暮判界、四维寄支或全套联合断法。月计专题和咨询参考的旧取年措辞也已同步到V39实际1.2.0计算。所有原历法／原典失败和V25原模型评分保留，见V40验证（本地数据：`validation/taiyi-jinjing-v40/README.md`）。

太乙公开计算已从第三方命法移植改为有来源范围的年计核心 `jinjing_year_core_v1`，并扩展六纪节月 `jinjing_month_jie_360_v1` 与冬夏至换遁时计 `jinjing_hour_solstice_v1`。后两者明确使用现代天文节气及所选时钟适配，不称为唐历复原。依据为唐王希明《太乙金镜式经》四库本转录，计算规则取卷一、二，独立主客算表取卷三，整十将位另核卷六、九。原始转录、72局预期值和指纹在 冻结材料（本地数据：`../tests/fixtures/taiyi_jinjing_v1/manifest.json`），实际结果在 审计报告（本地数据：`validation/taiyi-jinjing-v1/report.json`）。

V29进一步修复明确回拨瞬间在月／日／时计被二次校验误拒的问题，太乙单术增加明确偏移校验与同次瞬间回执；来源、参数语义和验收范围见[民用时刻](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-civil-clock.md)与V29记录（本地数据：`validation/taiyi-jinjing-v29/README.md`）。这不改变原典分歧或整体验收状态。

V30按先冻结的日本2025—2027完整节气表及香港2027中气表，分别核对native、DE440、auto和节／中气、二至边界；原26项官方预期及60秒容差保持，来源身份按明确后端逐项要求，见[太阳源与定界](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-solar-boundaries.md)和V30记录（本地数据：`validation/taiyi-jinjing-v30/README.md`）。分钟资料未认证亚秒精度或完整古历。

V31两版邢云路《古今律厯考》卷65书影确认梁例“九日甲申非八日”及入纪21／22异议，扩核十项盘面，发现原积数9项相符而始击卯／酉不同、加一假设十项全异。源位置重算单列揭示客算相同不能认证始击；日期、历元、算路与外迫解释分别保留，详见[梁例校议](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-liang-collation.md)及V31记录（本地数据：`validation/taiyi-jinjing-v31/README.md`）。本次未安装古历、改原文或增加完整有日期原例通过数。

V32补齐[节月积数、经朔累月与年标](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-month-count-domains.md)的来源及交付。武经书影确认章岁657而非线上652，另记庆历甲申年／月片段与两版福应经月法；两版金镜逐月保留小余，八组假设均核13个月首／12个月长。明钞一支为12／13月首、10／12月长相符，原例积日仍不同，未选用该分支改生产古历。默认月计新增实际取年及单位回执，摘要／快照同源，数值公式保持；V32记录（本地数据：`validation/taiyi-jinjing-v32/README.md`）继续保留完整古历和全盘验收未完成状态。

V33修正前轮明钞日干支漏读，分四库年字、明钞故事段日字和重述积数句保存依据；给定原积数与明钞甲申日局部相合，八组日期求积日候选仍全部不符。新增闰余／小余量纲及冬至—经朔精确相位诊断，两种取年皆可通过模60而展开间隔不同；展开历元仍为条件假设，不能据此选年或安装古历。见[日字与朔气相位](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-day-token-phase.md)及V33记录（本地数据：`validation/taiyi-jinjing-v33/README.md`）。

V34补齐[积日计数表示](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-day-count-encodings.md)：已过日数和从一日号须耦合转换日名；两篇历算研究的27项外部相位控制单列，不充作太乙古例。全部八组经朔候选、两种初始商解释与完整355日保留，初九的一支条件整数吻合仍不能通过原书初八、授时22、始击及全年约束。新诊断收紧日期存在性，最佳326个日名吻合中只有325个有效日期；完整目标仍未通过，见V34记录（本地数据：`validation/taiyi-jinjing-v34/README.md`）。

V35核《宋书》元嘉历原图，分清梁初历史历法与王氏同元四分历。所选完整501—505五年63个月首干支、62个月长和1831日干支均可重放，但502年闰四月与两种中气解释所得闰五月／六月不同，月标及完整日期仍未联合通过。旧梁例积数、初八／初九、授时22和始击分歧不因换用另一历法而消失，见[元嘉算法与历表](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-yuanjia-calendar.md)及V35记录（本地数据：`validation/taiyi-jinjing-v35/README.md`）。

V36将已冻501—505完整齐梁史历表接入明确的年计配置`jinjing_year_qiliang_table_v1`；原表502闰四月、元嘉候选闰五月／六月及未决状态随同次结构化／快照交付。范围外、默认配置及日／月／时计不自动换历，既有16份完整服务结果保持；来源、实际三端与投影验收见[历史年计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-year-calendar.md)和V36记录（本地数据：`validation/taiyi-jinjing-v36/README.md`）。这不是王氏古日积或完整古例恢复。

V38将明钞经朔、同本冬至和完整月份身份接起来，八组固定候选逐项核旧五年63月首、62月长及1831日。各支均不全合，整日／分数置闰还在505年给出闰二月／三月差别；缺月、未覆盖中气与不存在的三十日不借位或记成通过。没有修改生产古历或把代数推导补成原字，见[王氏完整朔气窗口](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-wang-mean-calendar.md)及V38记录（本地数据：`validation/taiyi-jinjing-v38/README.md`）。

V39取得金钥匙续集末尾完整积日算例，七个中间数可复算；同段月名／日名仍需不同编号解释。独立1561全年14月首、13月长及384日比较保留全部八支失败，算出707887076但月标为四月亦不能冒作源五月。该例另与武经“年前十一月”共同约束十二节月取年，修复默认金镜月计重复减年的少12月问题；计法仍是现代节月适配，不修改古日积或安装新古历。见[算例与名义年修正](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-key-worked-accumulation.md)及V39记录（本地数据：`validation/taiyi-jinjing-v39/README.md`）。

## 三个工程目标继续分别验收

| 目标 | 本轮做到的范围 | 尚不能声称的结论 |
| --- | --- | --- |
| 算对历法 | 农历岁首、立春与太岁口径分开；采用输入钟表日期定年，真太阳时跨日不改年计。用香港天文台2025、2026、2033、2034年表核对边界，涵盖闰六月和2033闰十一月后的岁首 | 月/时计节气另核两家天文台；并未复原唐代四分历或认证全部历史日期；岁首和时辰边界是已声明的约定 |
| 符合某部原典 | 卷三阴阳共144局、288项两算逐项比较；阳70/72、阴63/72，合计133/144局、277/288项相符；11项分歧全部保留 | 这些数据只验两算，不能扩大为全书、完整时计/命法认证；原典审计仍失败 |
| 解释忠于计算结果 | 主客算返回每一步宫位、数值及求和；将位由同一算数导出；输出实际命中的掩、击、迫、囚、关、格、对空间条件。三式按实际方位查同次原盘，快照与导出共用结果 | 完整独立自由解释验收未完成；V25实际13例为案例作者语义复核50/52、机械流程0/13，非独立专家盲测。没有命中所实现的关系不能理解成无凶或必吉 |

同一冻结表中，旧公开核心的主客算有23/72局、79/144项相符。修正后的结果必须运行审计取得，不能用软件回归通过数或自行打分代替。这个对比只涉及主客算，不表示旧系统或新系统的现实准确率。

## 已修复的问题

1. **把软件移植一致误当规则正确。** 原有14例 `kintaiyi` 对齐测试仍保留，作为历史软件差分参考；公开入口改用单独实现的原典年计规则，不再称其为完整人道命法。
2. **间神漏加一、同宫算成零。** 卷二例“太乙九宫、天目大义亥”应计 `亥1 + 子8 + 艮3 + 卯4 = 16`。正宫与太乙同宫时按本宫数起算，并用卷三对应局数验证。
3. **始击机械重复36项表。** 改按“计神加和德，求文昌所临”在十六神上旋转求位。它改变客算，不能只移动展示星标。
4. **主客算与大将来自不同来源。** 现在大将从本次算数导出。整十取首位，例如卷九第二十五局的客算40、大将4、参将2，不再把所有整十统一置5。
5. **立春年与农历年混用。** 2026年立春后、正月初一前，四柱年可以是丙午，但本配置的太岁仍按农历乙巳年。输入2026-02-17 00:01即使真太阳时退到前一天，年计也按钟表日期使用丙午。
6. **中宫星标丢失。** 十六宫结构保留，中宫另放在 `taiyi.center_marks`。主客将落五宫不会被静默丢弃，快照和导出均包含中宫。
7. **任意旋转与格名取模。** 删除三式入口中直接翻转、偏移太乙星标并挑选“龙德扶身格”等名称的逻辑。非零 `accNum/acc_num`、手动逆布和未知选项均拒绝；年/月计仅兼容0和顺布作为无操作参数，时计不接受 `rotation` 覆盖，阴阳遁从至点计算。
8. **年计与时刻盘被混成共同预测。** `synthesis.time_scopes` 按所选太乙年/月/时计区分时间层，并记录奇门、六壬时刻盘；三式共用输入及历法，没有三份独立证据或综合胜率。输出记录实际事实路径，未定义共同事件规则时 `agreement` 为未评估。
9. **新增依据未进入导出合同。** 注册了中宫、太乙规则依据和合参范围，防止导出静默裁掉原典限制与计算路径。
10. **合参首轮摘要超预算而丢失证据。** 原先同时展开三张完整盘会触发结果裁剪。现在 `scoped_evidence` 保留三系关键事实及各自规则来源；核算太乙另有 `taiyi_depth`。真实MCP测试使用默认响应限制，验证所选视图没有裁掉应读内容。

年计新增卷五三基五福等年度十神的独立数值核心，详见[年运审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-annual-cycles.md)。年、月定目定算及太乙八门另有[后本补证与门法审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-gates.md)，各自声明方法，不由旧软件移植值混入。默认至点时计不附定计；明确选择[金钥匙时计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-hour.md)另算完整积时、定计和阴阳四门，保留三项数值分歧及未决课语。古历时实与完整断法仍未完成。

## 原典与历法来源

- [《太乙金镜式经》卷一](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01)：开元十二年724年积数1,937,281，逐年增一；太乙三年一宫、天目十八步及计神规则。
- [卷二](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02)：九宫编号、运式及计数例。太乙宫数不能套用奇门后天宫数。
- [卷三](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03)：阴阳各七十二局立成和七类空间条件。保留转录分歧，不拿新程序重生成预期表。
- [卷六](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷06)、[卷九](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷09)：将位算例及三才数字分类。分类名称作为传统术语呈现，不据此断言天灾、疾病或死亡。
- 香港天文台：[2025年](https://www.hko.gov.hk/en/gts/time/calendar/pdf/files/2025e.pdf)、[2026年](https://www.hko.gov.hk/en/gts/time/calendar/pdf/files/2026e.pdf)、[2033年](https://www.hko.gov.hk/en/gts/time/calendar/pdf/files/2033e.pdf)、[2034年](https://www.hko.gov.hk/en/gts/time/calendar/pdf/files/2034e.pdf)公历农历对照表。PDF已冻结并记录哈希。

已另核浙江大学图书馆 [CADAL06056494四库本影像](https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu)：Commons第111图的第39局主算确为“二十五”，第112图的第50局主算确为“六”。两张影像已冻结在验收材料中。这两处是底本表文与通则的冲突，不能简单归罪于网站转录，也没有把原读数改为程序算得的35和16。两项仍未决；新增阴表另有九项差异，均已核扫描底本，详见下节。

转录表与规则都来自同一部书，独立于生产代码，但尚不构成盲法外部专家裁定；其他相符局也未逐字核完影像。发现底本、版次或转录差异时，应新增校勘记录、保留原读数和证据图像，不能悄悄改预期值使测试通过。

## 调用及复现

```sh
uv sync --locked --extra dev
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 2 --analysis-day 4 \
  --analysis-hour 12 --analysis-timezone Asia/Shanghai \
  --no-use-true-solar-time --strict-fields \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.rule_trace taiyi.ruleset
uv run --locked --extra dev python scripts/audit_taiyi_classical.py \
  --output docs/validation/taiyi-jinjing-v1/report.json
uv run --locked --extra dev pytest -q \
  tests/test_taiyi_accuracy.py tests/test_taiyi_transports.py \
  tests/test_taiyi_kintaiyi_parity.py tests/test_metaphysics_lunar_required.py
```

审计脚本有未决分歧就返回非零；测试验证审计是否诚实保留这些分歧，所以测试绿色和原典审计失败可以同时成立。测试不得删去失败局或只改分母。

REST、原生进程内MCP和CLI的真实调用见 [传输测试](../tests/test_taiyi_transports.py)。它们验证相同输入、字段投影、依据及错误输出，不替代远程部署或真实模型行为验证。Linux参考环境的全仓黄金快照也须另验，不能用macOS结果认证。

黄金样本只同步本批太乙字段、对应快照及导出注册项，保留其他盘和历法字段；本机Docker服务未运行，未完成Linux参考环境字节比对。全仓回归另有其他模块与全局文档失败，详见 工程验收记录（本地数据：`validation/taiyi-jinjing-v1/engineering.json`），不能把针对性回归通过写成全仓通过。


## 本轮扩展与校勘

新材料在 v2冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v2/manifest.json`），阴阳审计结果（本地数据：`validation/taiyi-jinjing-v2/report.json`）保留全部144局和288个主客算字段。阳表的两项分歧没有因扩展而被删除或改分母。新增阴局11、15、25、26、27、43、44、46、70共九项，已逐页核CADAL图117、118、119、121、124；它们是现存底本读数与本次通则推导的分歧，尚不能判定一定是底本错或程序错。未把表值改成程序结果，也没有单独为失败局加补丁。审计依旧返回非零。

卷一六纪首配置人工转录了12项案例组，另加入《太乙当时法》阴27局的完整两算、二目、计神及四将课例。该例主算明载29，与当前通则一致；卷三阴27局的39仍作为底本分歧保留，不能凭这条旁证宣称全书已裁定。初次标注曾把“大威”误映为戌；卷二明确“午神曰大威”“戌神曰阴主”，据此更正两处配置标注为午，原文读数保持，前后值和依据保存在 校勘记录（本地数据：`../tests/fixtures/taiyi_jinjing_v2/collation.json`）。这与未解的主客算分歧分开记录。

### 月计与时计

`calculation_mode=month` 采用卷一《推六纪月建法》：甲子/甲午年大雪子月为初局；每节换月，三十年360节月，农历闰月不另加数。六纪首的太乙、天目、计神均逐项核对，不把另一套章数求积月常数混入本配置。`cycle_year` 指大雪至次年大雪的计数年；小寒和立春都继续前一次大雪开启的计数年。

`calculation_mode=hour` 依据王希明“冬至气应则太乙变行”“以此为元”“夏至以后变顺为逆”建立显式现代适配：至点实际瞬间换遁并计一，至点所在的部分时辰只计一次，下一时辰边界加一；23:00起子时。`use_true_solar_time=false` 按IANA钟表标签；未消歧重复钟面及不存在钟面拒绝；明确偏移可选择实际重复瞬间，见[民用时刻核对](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-civil-clock.md)。期间夏令时跳变按已声明的标签法处理。为true则按UTC瞬间＋经度＋均时差建立太阳钟，换时区表示不改计数。此边界约定仍待独立古例裁定，绝非全套古历时实复原。

阴遁按原典从巽九起逆布，天目与阳遁相对、计神从申起；主客算仍沿卷二计数环求和，不把“逆布”误作计数方向反转。将位从同一次主客算导出，中五保留。合神取月支或日柱支的口径写入 `calendar_rules.heshen_branch_basis`；时计依卷一庚申日/戊寅时例取日支合神，不拿时支替代。

现代节气分别核对[香港天文台2026中气表](https://www.hko.gov.hk/tc/gts/astron2026/files/2026SolarTerms24.pdf)的冬夏至和[日本国立天文台2026暦要項](https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html)全部24节气。原文件、分钟级期望值和哈希均冻结；容差60秒仅对应公布精度。返回秒数不构成独立的秒级精度认证。线性近似回退禁止用于月/时计定界。

图27的章岁657/章月8726、图30的日法49/月法2447/朔策29/小余36、图33/35的辰法3682/半辰法1341均已核图。多组数字内部不能互相推导；这些是待校勘问题，不能凭现代平均朔望月默默改字，也不能据此宣布本系统复原了古历。

另找到了台湾国家图书馆藏[NCL-06604明钞本](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf)。图10/11/13的章月8126、秒法100、闰差秒17、月法1447、朔余26、气法32193、辰法整数2682与四库转录有七处数字差别。月法满足1447＝29×49＋26，提供了比猜测改字更实在的校勘线索。选定页面、原PDF指纹和版本并列读数见他本校勘（本地数据：`../tests/fixtures/taiyi_jinjing_v2/calendar-variants.json`），该旧冻结记录不覆盖。V26原生书影确认四库气法33193、辰法3682，另处二至间隔分母确为32293；明钞对应分母32193、完整全数168842新增核读。不同位置／版本不全局替换，详见[常数量纲校勘](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-calendar-constants.md)。辰法小分数义、次气小余／秒与完整积时、置闰公式仍未裁定，未将另一版本常数静默拼进四库配置。

### 三式实际宫位对应

`synthesis.palace_correspondences` 返回太乙、主大、主参、客大、客参五个位置，并带本次原盘字段路径：

| 太乙宫数 | 实际方位 | 奇门后天宫数 |
| --- | --- | --- |
| 1 | 乾／西北 | 6 |
| 2 | 离／南 | 9 |
| 3 | 艮／东北 | 8 |
| 4 | 震／东 | 3 |
| 5 | 中央 | 5 |
| 6 | 兑／西 | 7 |
| 7 | 坤／西南 | 2 |
| 8 | 坎／北 | 1 |
| 9 | 巽／东南 | 4 |

对同方位实际奇门宫读取星、门、神及寄星；中五不制造独立星门神。太乙位置为子卯午酉时直接查同次六壬地盘支位的天盘支与十二神。四维按同方位并列两支实际事实，寄支仍返回 `not_assessed`，不任选邻支；中五不自动寄坤。卷一《太乙当时法》确有“因步六壬式”的五将合参，但本次几何联接没有冒称已完成其全套贵人顺逆、门具将发和主客断法；`joint_judgment=not_implemented`。

### 解释和交付

掩击迫囚关格对按卷三空间谓词输出；“上目无迫”排除始击作迫，囚的个别将位口径另由阳局一“主参一乾（囚）”验证。每项保留实际字段与值、命中主体、细分类和来源。复杂四郭固/杜、提挟/挟闭及完整胜负条件未实现，不用基本关系替代全格断法。

默认合参 `scoped_evidence` 保留各系核心事实、三传和来源。新增 `calendar_summary/pattern_summary` 供首读，完整依据仍在 `calendar_rules/patterns/rule_trace`；四课按六壬深读，太乙用 `taiyi_depth`，宫位对应另有 `palace_correspondences` 视图。视图是复制到fields的任务卡，不改变计算。真实MCP测试覆盖年/月/时模式下各卡的默认长度限制，REST/MCP/CLI验证秒输入和相同完整盘结果。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 6 --analysis-day 21 \
  --analysis-hour 17 --analysis-second 2 --analysis-timezone Asia/Shanghai \
  --calculation-mode hour --no-use-true-solar-time --strict-fields \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.rule_trace taiyi.ruleset
uv run --locked --extra dev fatebridge sanshiunited \
  --date 2026-06-21 --time 17:00:02 --zone Asia/Shanghai \
  --taiyi-options '{"calculation_mode":"hour"}' --no-use-true-solar-time \
  --strict-fields --fields synthesis.palace_correspondences
uv run --locked --extra dev python scripts/audit_taiyi_classical.py \
  --include-yin --output docs/validation/taiyi-jinjing-v2/report.json
uv run --locked --extra dev pytest -q tests/test_taiyi_periods.py \
  tests/test_sanshi_correspondences.py tests/test_taiyi_accuracy.py tests/test_taiyi_transports.py
```

卷五扩展另见[年度十神与720项原表核验](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-annual-cycles.md)。

卷四五将的三项合取条件已连接同次盘面；年、月门法另附同次三门条件，时计仍未评估。新增独立学术参照30项中有1项理地/理人分歧，原读数保留，详见[组合条件与历史参照](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-conditions.md)。八门18行原表与4个选定课例仍有分歧和未评估项，见[门法审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-gates.md)，不能把新条件接入写成全书通过。

新增工程验证见 v2记录（本地数据：`validation/taiyi-jinjing-v2/engineering.json`）。目标仍在进行：古历常数、日计、年度十神异文及完整断法、复杂格局、真实模型自由解释及联合课例各自保留未决状态，不能把本轮测试通过写成三项目标满分。

## 现实预测的独立验收

目前没有已注册的太乙或三式真实研究，`real_world_efficacy=not_tested`。可复用 [前瞻评估器](../src/fatebridge/validation/predictions.py) 与 [运行脚本](../scripts/audit_prediction_study.py)，但应先完成以下材料再开始收集结果：

- 预先固定可观测的事件定义、时间窗、来源、基线、入组队列、模型及解释策略指纹；预测在窗口开始前存证。只有年计的配置不能为同一年不同分钟制造不同太乙预测。
- 在独立训练集上确定解释到预测的规则；锁定后使用未用于调参的前瞻样本。修改规则后重新注册验证，不能把旧验证结果沿用为新模型成绩。
- 区分太乙单术、其他单术、简单基线与三式合参的增益；同一事件、同一主体及共同历法造成的相关性不能计成独立样本。存在重复观测时须采用另行注册的聚类或时间序列统计方案。
- 公布错误、弃权、缺失、未随访及全部已注册结果；先报告覆盖率，再报告准确率、概率校准和相对基线的分数。概率必须另有固定、可验证的估计程序，不能由传统规则分数直接转换。
- 外部核验时间戳、结果裁定和数据独立性。有限样本全部正确仍不能证明未来总体准确率为100%，也不能据此认证最权威系统。

完整古历时计、日计、年度十神异文及完整断法、复杂格局断法、三式共同断例与真实模型解释应分别继续建来源和验收集，不能用现有局部覆盖结束总目标。完整缺口见验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）。

## 日计与十精继续验收

新增 [金钥匙日计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-day.md) 使用独立积日，附同盘定计、直门与分源十精；34原文观察保留全部分歧和未知。V8新增[独立历表与两条历史日期重放](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-historical-dates.md)，选定日期通过；完整古历、完整阴局古例和断语仍待验收，未缩小总目标。

V9新增[天时十二支规则与十精补证](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-ten-jing.md)，保留日例坤/酉差异、年例天尊方向差异与三风缺终位；太乙数四宫仍未裁定。

V10新增[金钥匙天地二正月计与门数校验](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-month.md)。八门扇区修正丑辰未戌四处归宫；原月段差异与朔月假设/节月比较的不匹配继续保留，原例实际月界仍未裁定。

V14新增[六主体对宫与主方格／对源名](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-oppositions.md)。此前主方对宫没有单独结果，现在由同盘方位逐项返回；原关系列表及卷四五将合取不变。12条主方原注的24宫数、12正对几何均相符，格10／對2仍保留原词，阳53附带外迫与所核向太乙定义不符。中五无环向，不制造反向；这些局部几何核验不代表统一称名、完整古例或全书验收通过。

V15修正[五将未知范围与三值合取](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-conditions.md)：同阵同宫的相关范围未裁定时，不因关系列表没有记录而确认全部满足；已实现关系合取另存，实际阻断与未决事实均保留。三门与五将按同一三值逻辑合取，未知门层不覆盖已知五将阻断。4条中位原注与36个合成逻辑状态分列，所有此前原典差异、未知与总目标继续保留。

V16新增[主客算数格与分源和数](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-count-readings.md)：修正15/25/35未限定的足数标记，明列缺数、筹分解推导、杜塞、长短与数族分层。太乙与二目位置配数分别返回，不由字面上和覆盖；五条源文的23异级、33未列、三才清单差异及未决缩写、越界转录均保留，不把40数分类或合成位置遍历算成全书通过。

V17补齐[同方二将夹持](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-enclosures.md)：从实际大小将的短弧读取太乙与对方目将，含未并宫的间神，完整记录在同盘enclosure_assessment.two_general_enclosure.patterns，独立于旧李法分支；全部旧关系、索引、数值核心与五将合取保持。两条书影课例及阳72局全文中的17处提挟注分别冻结，初录13/17及卷二独立订正后的17/17均保留；不是原典全书或完整复合断法通过。

V18新增[原表位置与两算校读](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-source-alignment.md)：完整144局576位置与旧288两算分别核对。书影确认阳41戌/旧转录戊；阴59旧转录与书影均为大炅，初录大神是本次整理错误，三层保留；阴37/43/44始击原读数仍有差异。源位置重算单独显示，揭示阴37算同目异及阴43/44上游位置可复现原表算；未以重算覆盖当前盘或改掉11个旧算数分歧，完整目标继续保留。

V18逐字复核补记：初录把阴59旧转录“大炅”误写成“大神”，不能算作旧转录错误。另有12行字形归一化现在并列保留原字。144行576位置的原文片段校读已追加冻结，初录文件和清单未覆盖，所选位置、原两算及所有计算结果未变。初始封存回归495项通过后因本次来源标签错误主动中断，修正后另封存重新验收；不把中断运行当完整通过。

V19新增[二目五行相关](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-elemental-relations.md)：原空间关之外，按淘金歌十六神明列五行计算二目生克，保留卷四地目/天目角色语境及日计适用。两卷四例、两淘金歌例给定8位置、验12元素/关系输出；原断不并入五将三项或总体胜负。完整128格钤表与日计纳音仍待验收。

V20新增[三门五将胜败钤全128格逐栏对照](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-victory-matrix.md)：按四库书影97—105页完整冻结原栏、四空栏及一缺字；实际几何与未标客主的将星候选分列。33条天目几何中6条不同、76个复合/门法片段仍未裁定，原胜败不直接应用；128格查表覆盖不计成128次计算命中或全书通过。

V21增加[明钞本整表物理栏初录与同版名位](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-matrix-collation.md)：六页书影和32栏字组独立封存。六处争议词句在相应神名的半表栏可见，逐宫对应仍未裁定；新增逐宫校定、几何相符及有日期古例均为0。两版原录、四库全部空缺和旧审计差异保留，不把字串命中转成原典通过；历法、完整断法和真实模型忠实性验收继续进行。

V22增加[武经总要两套72局及四将逐字段审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-wujing-cycles.md)：144局、1440要求完整保留，45个不同字段与45个未决字段分列。书影确认阴13主算十二而主大将六，以及阴55/56天目不同而七字段重复；是否沿抄及应改哪一方仍待裁定。新底本作为旁证，没有替换金镜主原典，没有据检索或不同字段合计宣称全书通过，生产算路及旧差异保持。

V23完成[金镜144局六列的原生书影语义核读](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-native-columns.md)：576位置、288两算分别比较，三处始击和11两算分歧均保留。四处本轮读图录入错误追加订正，初录不覆盖；未列的568四将槽位不由公式补值。来源输出追加本局页栏与指纹，并修复空/多字符位置被误评估的问题；合法144软件盘的其余结果逐值保持。六列语义校读不等于逐字字形、全书或完整历法通过。

V24补齐[始击计神加和德的逐步算路](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-shiji.md)：实际文昌、计神、天地盘配对和当前始击随同盘及文本交付，阴阳同法，间隔不混作主客算。武经书影在三处争议的18选定字段与当前核心相符，原金镜三处始击及11两算分歧仍保留；明钞本所读卷三末此处未插四库144局表，不推断全书缺表或换底本验收。给定位置原例、手工推步、软件保留与原典符合分别报告。

V25修正[太乙／三式咨询指引并完成首批解释实测](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-semantics-evaluation.md)：入口曾把已实现日计／时计写作未实现，参考又把已实现的部分提挟一并否定；现按实际四计、版本、三值条件和同次盘面解释。13个虚构单轮案例、52条语义要求先于模型作答冻结，参照与模型自身回执分别保存。13例均已执行；严格机械0/13通过，作者逐条语义审阅50通过、2未满足，不是独立专家盲测。两项为预登记范围说明遗漏，未把当前数字算错；原评分、入口未读取及默认参数／业务拒绝表示的判据问题完整保留。新入口导向、范围源配置与评测器补丁在冻结后修正，未据旧模型回答声称新源已通过。详见V25记录（本地数据：`validation/taiyi-jinjing-v25/README.md`）。本批没有更换数值算法、主原典、原要求或未决差异，完整三项目标继续验收。

V27修正年计农历来源与两种钟面的忠实交付（本地数据：`validation/taiyi-jinjing-v27/README.md`）：年计取年原本正确，快照曾混用校正钟面农历并误标为直接时间。现从实际年计换算复制年月日与来源，区分输入钟时、计算钟面及通用上下文，增加年计历法首读视图并生成合同。三例机构历表边界输入事先冻结，8组改前事实保持；不修改数字核心、改造普通日权威来源或把模板修复计作模型盲测。梁天监三年积日探索未能闭合，未加常数凑合。全部旧原典差异与完整目标继续保留。

V28新增[古日计的历法与积数核对](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-day-epoch.md)：独立梁504历表完整12个月及次年终界先冻结，355日干支／星期重建相符。原载707501061在两种甲子编号下均非所选史历表六月初八癸未；四候选、八编号组合全留，仅一干支余数相符而无原积数相符。王氏自称另修同元四分历，二者关系未裁定；没有以历制差或补2日凑合、安装新历法或增加完整古例通过数。金钥匙日计阴局计神起申有明确书影，当前数值未因末摘要省略而改动。两处本轮整理错误追加订正，初录和首轮结果保留。V28来源与工程记录（本地数据：`validation/taiyi-jinjing-v28/README.md`）。

V37将502置闰线索推进到两部本纪完整首年段及张皇后段的27幅原生书影、42条日期观察。原表与两支元嘉算法均不能容纳全部段落；五月戊子等不存在日期与39条顺序边中的未知继续保留。它不是简单改闰月即可通过的证据，也不能据相关记事多数票裁定。全部源字、推定月号及候选诊断见[元嘉指南](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-yuanjia-calendar.md)和V37记录（本地数据：`validation/taiyi-jinjing-v37/README.md`）；公开历算与旧古例失败未改。

V45补充：[冬至起元选择说明](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-origin-activation.md)与V45记录（本地数据：`validation/taiyi-jinjing-v45/README.md`）。当前日计与明确金钥匙时计增加同盘选元依据，保持既有数值策略；原典年度启元仍未裁定，条件数学对照不增加古例或完整目标通过数。

V46继续[武经1440字段的书影补读](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-wujing-facsimile.md)：全部45旧未知逐项核读，13明列值与32未决分列；旧45差异和原金镜分歧不改，不把旁证补读计成新古例或全书通过。

V47追加[武经同书十六神名位](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-wujing-names.md)：原页明确大族为酉，并揭示阴德／阳德与金镜参照的35项位置冲突；统一同书映射后完整1440字段并列为1350相符、73不同、17未知。原评分和45差异保留，不按评分选择原典，不改生产金镜规则；真实解释、古历与现实效力继续未验收。

V48追加[武经明刻本与书内算路](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-wujing-internal-counts.md)：明刻同段名位与四库一致，阳四局主算所读55／25异文并列。新增不调用生产引擎的完整288槽位条件诊断；只交换阴德／阳德仍有25项不同，原方向与同点特例未决，不改源值、旧评分或金镜规则。

V49补强[金镜独立算术参照](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/taiyi-independent-arithmetic.md)：通过另一种代数实现核查全部128计数输入、实际288两算及288源位置重算，数字和算路一致。原表内部10差异、原11算差及3处始击差异完整保留，未将共用生产函数的重算当独立复核，未新增古例或全书通过数。
