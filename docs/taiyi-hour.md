# 太乙时计：完整积时、行宫捷数与古历量纲

`calculation_mode=hour` 可明确选择 `hour_profile`。省略仍用 `jinjing_hour_solstice_v1`：按已声明的现代至点实刻置一，合神取日支，八门与定计未计算。`key_hour_winter_jiazi_v1` 按《太乙金钥匙续集》冬至前甲子积时规则，合神取时支，并计算定计和阴阳四门。两法预先选择，不按吉凶择优；都没有宣称完整古历复原。

太阳源变更及临界换遁按[独立节气与边界核对](taiyi-solar-boundaries.md)解释：返回的anchor_provider只标识实际节气锚点，分钟资料不认证返回微秒的物理精度，也不把均时差自动归给同一后端。

## 完整积时不能换成行宫捷数

[《太乙金钥匙续集》](https://www.shidianguji.com/zh/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8)图44记载丁丑日庚戌时：自冬至前甲子日计入第74日、第11时，完整积时为 `(74-1)×12+11=887`，入戊子元23局。太乙在巽九，文昌乾，计神辰、始击申，主算16、客算23，主大／参6／8、客大／参3／9。

同页另用甲戌日甲子时至所求时计47，明确限定为只求太乙行宫、不求局。47与887的太乙宫相同，但若把47当完整积时，文昌会误成卯，不能拿它代替本例完整积时或23局。

新配置通过 `calendar_rules.hour_origin` 返回冬至UTC及提供者、所选钟面、甲子锚点、所属日、日数、时序和完整积时。先按实际UTC瞬间判二至换遁，再按已选民用钟或真太阳钟计数。23时子初换日、同日甲子纳入起点都是明确的现代适配，不能当成原书子正夜半或古历时实已经复原。

两个甲子日相差60日，即720时；当前核心的72、24、18、12周期及四门120时周期都整除720，因此相位不因选相邻甲子锚而变。此为计算周期的恒等关系，不是古历年月日已获独立验证。夏至换阴遁时保持完整积时，不把它重置为1；独立夏至完整古例仍待补齐。

## 四门直使与未决课语

本书阳遁直门序为开、生、惊、休，阴遁为杜、死、伤、景，每门30时，120时一周。生门直使不等于只布四个方位；所直门仍按八方门盘加定计目。完整887的直门相位与47相同，都是生门第17时。

本书时计合神以时支戌合卯；《金镜》另一时例以日支取合神，不能不分来源地混用。空间七类和五将三项条件仍分别标注《金镜》来源，不冒称为《金钥匙》全套断语。

图45/46的定计目为巳，列出的算路为 `巳1+午2+坤7+酉6+乾1+子8+艮3+卯4=32`，原文却写33、大将3、参将9。程序保留通则所得32／2／6，同一相位在 `determinate_calculation.source_disagreements` 保存三组双方值，快照同时显示。没有为符合这一例而改加总或单设例外。

本例另有“门具将发”的课语，但三门核对主体、不同门盘与主客论断的对应仍未裁定。本例虽已布门，仍返回 `three_gates.status=not_assessed`、`menju_jiangfa=null`；原文课语保留在审计要求中，不把null记为通过。V15起其他相位若五将有明确阻断，两层合取可为false，三门未知状态仍保留。

## 古历常数不能只靠数值看似合理

钱大昕[《潜研堂文集》卷30原跋](https://zh.wikisource.org/wiki/濳研堂文集_(四部叢刊本)/卷第三十)指出《统宗》日法与气朔策分别沿用不同分母，并提示所见本有后人续增。所核NLC第1册图18载日法10500、岁实3835046.25分、气策15日2184.375分、朔实310071.2265分、朔策29日5305.93分。

若全部按日法10500解释，岁实与24个气策相差 `699/2800` 日；朔实与朔策相差 `75799/3000000` 日。按钱氏指出的异单位解释，气朔二策改用10000作为分母，两条关系恰好成立；两条恒等关系支持钱氏异单位解释，统一日法假设据此被否定；这不能计成原书两项错误。这些诊断未加入公共历法。钱氏引述岁实3835048.25，与本图3835046.25又有2分异数。不能把校算所得数反填原文后宣称已复原古历；现代天文适配也不能替这套常数取得古历认证。

v6冻结材料（本地数据：`../tests/fixtures/taiyi_jinjing_v6/manifest.json`）保留原图、原文与全部要求；审计结果（本地数据：`validation/taiyi-jinjing-v6/report.json`）中完整课例20项，19项可评、16项相符，三项定计分歧与一项未决课语均保留。阴阳四门序另列8项规则核对，量纲和引文异数另列三项诊断，其中两项否定统一分母假设、一项引文异数待校勘，不合并为全书准确率。脚本继续退出1，完整目标仍见总验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）。

## 调用

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 4 --analysis-day 4 --analysis-hour 12 \
  --analysis-timezone Asia/Shanghai --no-use-true-solar-time \
  --calculation-mode hour --hour-profile key_hour_winter_jiazi_v1 \
  --strict-fields --response-char-limit 0 \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.determinate_calculation taiyi.gates
uv run --locked --extra dev fatebridge sanshiunited \
  --date 2026-04-04 --time 12:00:00 --zone Asia/Shanghai \
  --taiyi-options '{"calculation_mode":"hour","hour_profile":"key_hour_winter_jiazi_v1"}' \
  --no-use-true-solar-time --strict-fields --response-char-limit 0 \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.determinate_calculation taiyi.gates
uv run --locked --extra dev python scripts/audit_taiyi_hour.py \
  --output docs/validation/taiyi-jinjing-v6/report.json
```

REST、MCP、CLI共享上述选择。年、月计传入 `hour_profile` 会报参数错误；不静默忽略。合参首读保留奇门日／时取用与来源，岁干、月朔及时干支入墓细节按同盘 `qimen.stem_context` 续读，未选字段不当作不存在。

首读同时保留奇门三套已选配置的名称、原书链接和异文说明；具体八神顺序、九星旺相映射和未采用入墓候选在同盘 `qimen.rule_profiles` 续读。按需调用合同由生成器发布为 [taiyi](contracts/taiyi.json) 和 [sanshiunited](contracts/sanshiunited.json)。

V8补充：[选定历史日期与完整公开重放](taiyi-historical-dates.md)，保留本次全部源文差异与未决项。

V45补充：[冬至起元的计数起点与选元切换](taiyi-origin-activation.md)。明确金钥匙时计的子初起点与冬至实刻选元不是同一时点；720相位相同不证明完整积时相同。
