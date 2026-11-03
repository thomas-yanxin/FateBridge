# 宿曜与宿占：历法、规则与来源

宿曜的本命宿、双人关系与宿占历日使用不同输入和规则。先选宿主历法、当地日期与已确认的钟时，再读取候选、引用和三九日等条件；未知出生时刻不能用默认时间补齐。

本页维护公开调用、历法选择、已读原典与结果边界。古代日界、闰月／小月补配先后、未读清的宿字及所选书影的异文仍未裁定；现代计算或局部书影一致不能补足这些条件。各候选的共同假设应保留，不能把依赖同一重建的两份结果当作独立印证。

逐轮资料检索、读录修订、模型首评及修复后复评保存在[历史记录](https://github.com/thomas-yanxin/FateBridge/blob/73ec8912677b2b687a4b11ccb06727332296e8e1/docs/sukuyo.md)。原失败、未知与验收范围随原版本保留；本页的参考数量不构成当前全量或现实效力认证。

## 计算规则与依据

| 旧实现的问题 | 本次处理 | 可核对来源 |
| --- | --- | --- |
| 从春分点把黄道等分28段，取月亮段名作为本命宿 | 本命宿改取农历月日，不调用星图、不依赖出生经纬度 | [国立天文台二十七宿朔日表](https://eco.mtk.nao.ac.jp/koyomi/wiki/C6F3BDBDC8ACBDC9.html) |
| 牛宿按黄经中点硬分到斗或女 | 拒绝此转换；不得把天文28宿宿名直接当历日27宿 | 同上，二十七宿不含牛 |
| 农历库部分月份起始日错一天 | 按公布历表纠正1933、1954、1978年各30天，共90天；其余日期仍由库计算 | [香港天文台公历农历表](https://www.hko.gov.hk/en/gts/time/conversion.htm)，原始字节及每年SHA-256冻结在测试资料中 |
| 将三个九宿组标作相性“近、中、远”，同一配对正反方向距离不同 | `distance=null`；`sequence_group=1/2/3`仅表示三九组序 | [T1299](https://cbetaonline.dila.edu.tw/zh-tw/T1299)，0391b06–18、0397c01–19 |
| 同宿推成性格价值相同，业胎写成前世牵引，荣亲断成最佳相性 | 移除这些无所选原文支持的断语，分别返回两人的单向结交判断 | T1299 0391b14–18 |
| 天文宿位用等宽黄道带，度数又误用30度星座内度数 | 默认改为七曜当日视赤经与现代距星不等宽宿界；显示真实宿内度数，保留显式旧示意模式 | [国立天文台：中国28宿宽度不等，基于赤道与天极](https://eco.mtk.nao.ac.jp/koyomi/wiki/C6F3BDBDC8ACBDC9.html)；[JPL Horizons视赤经/赤纬定义](https://ssd.jpl.nasa.gov/horizons/manual.html) |

默认 `calendar_profile=t1299_fullmoon27`直接实现T1299下卷0394c20–0395b08的十五日望宿逆顺法；另按生日加十三、望宿本身计一的略算法独立互核。正月到十二月十五日锚点为翼、角、氐、心、箕、女、室、娄、昴、觜、鬼、星，`profile_calculation.host_calculation`交付两法中间量及段落。十五日是表定日序，不换成实际天文满月瞬间。派生的朔日表与NAOJ独立参照的360个月日组合一致，默认宿名数值不变，方法版本改为 `t1299_lower_fullmoon27_v1`。

正月到十二月的朔日宿为：室、奎、胃、毕、参、鬼、张、角、氐、心、斗、虚。初一后逐日顺数、模27。T1299 0391b11的“二月五日为毕”例，及0397c01–06以毕为命的全部27个关系，作为独立原典例题验证。

第三轮把上卷0388a22–0388b23印本月建表的**360个格值**单独冻结，并通过 `calendar.source_table_variant`逐个输入交付：例如二月初五印表作胃，0391b11的例题却作毕；十二月初五印表有牛，选定27宿表则为奎。保留字面、出处、差异及 `applied_to_sanjiu=false`，不改写原表来制造一致。闰月未定时，比较所用同名月27宿也明确标作候选。

**没有把原典差异修掉**：T1299上卷“大唐月建图”含牛，为28宿表，不能直接套入27宿三九法；“业宿日”上卷0391b19–20称吉，下卷0398a07–08却称不成就；下卷0398a02将危日用于定婚姻，0398a09–10又称危坏日不宜婚姻；上、下卷七类宿性中胃、牛等归组也不同。运行结果的 `rulesets.unresolved`、`textual_variants` 和 `personal_day.textual_conflict` 保留这些差异。`nature`字段采用上卷0390c16–0391a26；`lower_methods`另列下卷宿性与七曜证言，事项引擎分别匹配。七曜特殊日仍采用上卷0392c17–28。

## 公开调用与迁移

### 现代月日角距与历日白黑分

完整宿占默认天文口径在 `astronomy.lunar_phase_reference` 返回同次TT的月减日视黄经差及现代12度tithi分段，含各自实际星历模型、坐标约定与精确二进制输入比值。比值分子分母用十进制字符串保留，JSON客户端需要精确复核时使用大整数；显示舍入不改变原分段。它不是原典仪轨条件、古代日界、日内前后半、闰小月优先或真实月宿合的判定，也未求tithi结束时刻或日出历日。

以下计算示例为现代中国农历九月十六、历日黑初一、毕宿；现代黄经差170.12539666198924度却仍属现代白分第15段。两项按各自依据交付，不以角距覆盖历日日号，也不凭日号认证满月。现代分段以半开区间计算，恰180度开始现代黑分第一段；T1796以正圆满名白十五的原文另存。

```bash
uv run --locked --extra dev fatebridge suzhan --date 2026-10-25 --time 18:20:00 --zone +08:00 --fields astronomy.lunar_phase_reference sukuyo.calendar.lunar_day sukuyo.calendar.natal_su27 validation --strict-fields --no-include-snapshot-text --response-char-limit 0
```

关闭 `doubing_su28` 或选择 `legacy_equal28` 时，本次 `astronomy` 为空且明确现代角距参考未计算；基础星图和历日知识仍按其原范围交付。不能用舍入坐标由解释模型补算，或借用其他模式结果。现代定义及实现见第五十一轮报告（本地数据：`validation/sukuyo-lunar-phase-v51-validation.md`）。第五十二轮五年对照（本地数据：`validation/sukuyo-phase-reference-v52-validation.md`）已补全原定1700、1900、2000、2026、2100年全部248条主月相，均在原0.01度环绕角距门槛内；原协议和领域数值保持。该项通过限于这些主月相参考点，不能扩展为全支持期历法、所有tithi结束时刻、古代日界、闰小月先后或现实效力已认证。

### 明确选择宿主历法

默认calendar_basis=chinese_hko_utc08，继续使用现代中国农历、固定UTC+08。可选japanese_hutime_1002_1_utc09使用HuTime 1002.1冻结逐日参考，范围1872-02-09至2031-01-22，固定UTC+09为明示参考日期政策。出生时区和calendar_profile分别声明；选择日本参考不自动把出生时区改为东京，旧默认出生时区仍为+08:00。双人接口双方共用同一basis。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2017-06-24 --time 12:00:00 --zone +09:00 \
  --calendar-basis japanese_hutime_1002_1_utc09 \
  --fields sukuyo.calendar sukuyo.reading_text rulesets.calendar_reference \
  --strict-fields --no-include-snapshot-text
```

此例日本参考为闰五月初一，中国历为六月初一。日本参考保留候选参，默认闰月政策未定时主宿仍为null；不能为了得到确定宿自动选择repeat_month。calendar_reference交付数据指纹、实体范围、日期来源及资料差异：1910–1946年属出版方重建，1947–2014年属其神宫历整理并保留例外／勘误，2015年起为参考推算，不称已核对逐年神宫原刊。固定UTC+09也不是历史日本地方时、完整天保历或唐历复原。

文档宣称到2033年与实体范围到2031年的差异、739个范围外空响应、目录标签1002.2链接到1002.1及1989月份结束边界差异继续保存。范围外返回错误或保留未穷尽候选，不能改用中国历补齐；原典半日与闰月次序也不会因选日本参考自动解决。

### 历史日本历日参考

显式calendar_basis=japanese_naoj_historical_utc09采用NAOJ冻结月首，支持前推公历0001-01-01至1872-12-31；固定UTC+09是参考日期政策，不是当时地方钟时。阴历年0只作首端来源上下文，不接受公元0年出生。453阴历年及以前的儀鳳暦平朔回推、454年起的参考及历史校正分别披露，不据此宣告实际颁历或完整历史历法已复原。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 0820-03-22 --time 12:00:00 --zone +09:00 \
  --calendar-basis japanese_naoj_historical_utc09 \
  --fields sukuyo.calendar sukuyo.reading_text rulesets.calendar_reference \
  --strict-fields --no-include-snapshot-text
```

此例NAOJ为820年二月初一，HuTime1001.1为闰正月三十；二者可能同配奎宿，但calendar_reference.cross_source_comparison保留月、日及闰标志不同，control_applied_to_primary=false。全域210个分歧日期逐项保留，两来源部分共用历史文献，不将一致部分称为独立实证。1872年旧历十二月只保留两天，1873-01-01改公历后不续算旧历；更早的唐代颁历、历史地方时和原典平明起算仍须另行验收。

特殊日的 `weekday_basis`、其范围说明及 `rulesets.special_days.scope`使用与本次 `weekday.basis`相同的宿主日界。日本现代及历史参考均为声明的UTC+09民用日界；未知出生时刻所产生的每条候选历日分别保留依据。该字段与文字一致不表示古代平明钟时已经建立。

### 太白月日方位章

`suzhan.sukuyo.taibai_direction_reference`以本次宿主历法的实际入月日查T1299下卷0399b29—0399c18，主表初一／十一／廿一东方，按十日组轮转到八方、中央入地与天上。它是另一份历日表，不能用实测金星、天文逆行、公历日或桧尾补配后的宿序替代。原文大白／太白的字面分别保留。

明本校记删去初十／二十／三十“常在天上”整行，主表仍可返回天上，而该见证状态为row_deleted_in_apparatus、位置null。缺文不等于无太白或已获行动允许；九／十九／廿九的中央入地也不换成水平角度。原文顺逆所指的行路相对关系尚未核定，不按面向／背向、顺时针或GPS角度补造规则，也不改写当前事项宜忌。SAT与CBETA的相关电子校记字面不同，原始引文和指纹分别保留，不称独立明刻本校勘完成。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-02-07 --time 12:00:00 --zone +08:00 \
  --fields sukuyo.calendar sukuyo.taibai_direction_reference sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

此例为入月初十，主表天上，明本校记缺行。字段的physical_venus_position_evaluated、astronomical_retrograde_evaluated、movement_alignment_evaluated及applied_to_activity_assessment均为false，不能转成具体出行许可或现实概率。未知日期保留各candidate_days的完整条件，不挑一个方位作确定判断。

### 古序、记日正文与边按

`calendar.printed_edition_reference.preface_scholarly_reference`保留會谷佳光2013年整理本、成田山刊本及享保覺勝古序的身份，另含ARC下卷第28图所选正文及上栏校按。古序年不等于实际印刷年，两馆实物同一性及未定字仍保留。现代翻刻中的“重直兩日”未被改解成桧尾前后半，也未确定闰月与小月的执行先后。

历史NAOJ参考只在对应同名月日返回`calendar_reference.early_weekday_documentary_comparison`，逐条保留原文、原有／缺失干支、参考曜名及前后一天的诊断。806与807两例条件相合，808年二月七日正文蜜日与参考火曜不合；邻日不是出生候选，唐历四日的“准拟”没有实算。`early_weekday_editorial_comparison`另比较上栏拟正月七日及二月火曜的主张；其相合不替换三条正文，也不改输入、主宿或候选。正文、夹注、边按与现代计算分层，完整边按未接纳。字段位于单人宿占的`sukuyo.calendar`及双人各自`calendar`；未知钟时保留各实际日期分支，不借文献校按替选。

### 双人相性

UTC+08历日可只给公历出生日期，不猜未知生时：

```bash
uv run --locked --extra dev fatebridge sukuyo_compatibility \
  --person1-date 1990-06-15 --person2-date 1992-03-20 \
  --fields status person1 person2 person1_to_person2 person2_to_person1 rulesets \
  --strict-fields --no-include-snapshot-text
```

命宿改算后，历史结果可能变化。这是纠正口径，不兼容旧错误数值。`natal_su28`、`moon_longitude`保留为null；`natal_su27`来自嵌套 `calendar`。`person1_to_person2`明确为“以第一人为命，顺数至第二人”，不能交换方向。六类配对标签是界面归类，不是六级吉凶，也不是概率。

### 当地日期已知、出生时刻未知

第九轮支持直接提交其他时区的当地出生日期，不再因缺少时刻整单报错，也不补零点或中午：

```bash
uv run --locked --extra dev fatebridge sukuyo_compatibility \
  --person1-date 2025-01-29 --person1-zone UTC \
  --person2-date 2025-03-04 \
  --fields status person1.calendar person2.natal_su27 candidate_relation_analysis pair summary \
  --strict-fields --no-include-snapshot-text
```

此例第一人的当地日期对应中国历日2025-01-29／30，农历为正月初一／初二，宿为室／壁。主宿与主关系为null，条件配对分别为安壊／危成；`candidate_relation_analysis`列每个宿候选的日期来源，未代入主结果。`date_support`保留完整UTC区间及实际时区规则指纹，`calendar_candidates`逐日交付历法与桧尾／闰月条件；区间端点是可能时刻集合的边界，不是出生时刻。

按TZif整数秒规则完整枚举当地日期的UTC原像，没有用固定小时抽样。上海1986-05-04的23小时夏令日仍只对应一个固定UTC+08历日，可直接定宿；夸贾林1969-09-30重复至47小时，对应三个中国历日，全部保留。整天被跳过的当地日期仍应核对；已知钟时落入夏令时缺失／重复区间仍报错，不任取fold。

若完整的不同日期候选恰好同宿，可只确定宿和关系，唯一历日与生时仍未定；若存在范围外日期或闰月政策未定，不能因为剩余已算分支同宿就宣称确定。分足表的唯一宫名也遵守候选完整性。日期与小月半日两层不确定性同时保留，不相互代填。

### 宿占历日与本命三九日

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-04 --time 12:00:00 --zone +08:00 \
  --natal-mansion 女 \
  --fields sukuyo rulesets validation --strict-fields --no-include-snapshot-text
```

此例历日宿为毕，本命女顺数至毕为业。`sukuyo.personal_day`同时保留上卷和下卷对业日的不同说法，不合成“综合吉日”。未给本命宿时仍交付历日宿、七曜、黑白月分、七类宿性及特殊日组合。黑白月分是所选原典的日序分类，不是用日月角距计算的印度tithi。

### 本命六宫宿位置

提供已确认natal_mansion时，sukuyo.six_palace_reference按T1299上卷0392b04–20计算命、事、意、聚、同、克六宫宿。本命本身计一，各位置为第1、10、4、16、20、13宿；原典注释以娄起算的第四毕、第十星、第十三轸是独立例题。娄的完整六位置为娄、星、毕、氐、箕、轸。它们只取决于输入本命宿，目标日宿未定或日期候选未穷尽时仍可返回；没有本命输入则返回natal_mansion_required和空成员，不从目标日代填。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-04 --time 12:00:00 --zone +08:00 --natal-mansion 娄 \
  --fields sukuyo.six_palace_reference sukuyo.personal_day sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

原段的条件为七曜运行犯宿，且夹注要求共三九秘宿相参。当前seven_luminary_transits_evaluated、joint_reading_requirement.evaluated和applied_to_day_assessment均为false，不根据日宿或星期制造“六害期间”或现实灾祸；六宫宿与十二宫分足、双人六类配对分别交付。上下文引用检查v2要求同时引用六宫结构及其未计算条件，字段检查仍不能认证另一模型的自由文本语义。

### 三代格引文的日期层次

京大《類聚三代格》卷八所选文书署822年三月二十八日，内引766年二月二十日旧敕；两处日期均未载干支。引文直接提供二十日，但未解决《续日本纪》甲午底文与丙午校改，也未认定校者一本或研究所引352页版次。实物写年未定，不当作766年原敕或822年同时代原件。

结果`sandaikaku_edict_reference`只在766年二月和822年三月普通月分别绑定旧敕／传载文书角色；整月关联不把当前日期改成文书日期，其他年月与闰月明确为空。详见第五十九轮报告（本地数据：`validation/sukuyo-sandaikaku-v59-validation.md`）。

### 766年原书异文与回指

《续日本纪》卷二十七所选两部影像并非都写丙午：鵜飼刊本是甲午，1897校订本承认原作甲午而据一本改作丙午，该一本尚未识别；二十日来自同书六月回指与同诏内容，非二月正文直书。两种条件月首干支丁亥／乙亥与当前NAOJ丙戌单列，不当作两套认证历法或绝对日期。

结果新增所选原书比较及全327行固定宿主对照范围；别月没有对应影像则明确为空，不继承二月证据。52项方向分歧和1项未知保留，真实预测样本仍0；详见第五十八轮报告（本地数据：`validation/sukuyo-shoku766-v58-validation.md`）。

### 大衍进朔研究选表与月首对照

竹迫忍2022/12/27版更新表的327行作为具名研究对照接入NAOJ历史参考。想定限、作者進／不進字面、原典栏及当前NAOJ月首分别交付；第263行横杠不补成不进，带星号例外不由机械阈值覆盖。按源表大余及明确方向模六十推得的标签，保留52处与当前NAOJ不同及1处未知，不把循环差认证为公历日期差或直接改写宿名。

新字段只比较所选研究的月首条件；全来源引用、真实颁历及全部764—861年月表未因此校定，详见第五十七轮报告（本地数据：`validation/sukuyo-dayan-advance-v57-validation.md`）。原NAOJ／HuTime未列分歧的语句已限定两家既有对照，不抹去新研究分歧。

### 宣明弦望完整条件与已下异文

《高麗史》所选条文先以不盈昏明小余作严格小于比较，后列望有食且初亏在晨初以前时仍退日的例外。独立晨初条件未明则保留候选；此项不重写当前输入的历日或宿名。京都大学藏安藤《長慶宣明暦筭法》所选句作已下，按包含相等的文本解释另列，与高麗史在等值处的差异不合并；京都本未认作所引早稻田同一实物，也未校完全部安藤食例外。

1117研究引述的2557／2193及不退与当前输入严格区分，未认证古报告错误；昏明、晨初、T1299平明与桧尾半日均没有等同。完整原转月条件及两重建候选保持，见第五十六轮报告（本地数据：`validation/sukuyo-senmyo-phase-v56-validation.md`）。

### 永樂北藏具名影印与卷间差异

台大所刊《永樂北藏》第一三〇册的所选上、下卷影像，与网络分卷56页正文图像经实际解码像素及掩膜属性比对一致，仅计一份影像来源。上下卷各21个宿位分别接为直接对照，保留上卷甘露火曜井、金刚峰火曜昴水曜壁与下卷尾、壁、昴的差异，不替换大正主表。上卷第三组名字形仍未唯一接纳；所选读文相合不认证大正明本实物身份或全本校勘。

五条分时句与段序提供日界文献旁证，尚未建立现代钟时、桧尾半日或闰小月优先。首次署名误录及更正、1424通过1失败的旧字符串断言、修订后的完整1425通过均保留，见第五十五轮报告（本地数据：`validation/sukuyo-yongle130-v55-validation.md`）。

### 全宿主转月与同宿来源

新增离线检查器从原始HKO、HuTime、NAOJ参考字节重建完整朔日期望，覆盖三个既有历法全部27581朔日及未明／前半／后半共82743条件。固定协议不接收抽样范围或改容差；缺前月的partial条件也保留。此检查支持现有现代重建的实现核对，未裁定原典优先次序、历史唯一钟界或现实效力。

原生说明现在同时交代前月阴历年、闰月和缺失三十日，以及本月常规初一的计算来源；即使宿名相同也分别说明。八例首次全文复核的一项遗漏及修复后的同题结果见第五十四轮报告（本地数据：`validation/sukuyo-month-transitions-v54-validation.md`）。新取东大目录与影像的交叉身份不合另记，未用错配书名加入规则或认证全本校勘。

### 符天研究时刻与名义日界

新增 `sukuyo.calendar_day.clock_doctrine.futen_research_clock_arithmetic`，按竹迫忍具名研究的两种明确时制，交付所引1240年三个时点的精确分数、原印整数及差额。万分与8400分模型的刻分、1164年的百分／小分和995年的8分33分别保存；名义子半起点不能替代T1299平明、固定UTC+09或桧尾前后半。

第五十三轮报告（本地数据：`validation/sukuyo-futen-clock-v53-validation.md`）保留起、中、末不对称及作者疑误意见，没有把它认证为原抄本错误、实际食时、完整符天历或补配优先。所引原1240年文书未独立校读，新增参考不改本次日期、主宿和候选；所选研究单位的精确换算不等于历史钟时已统一。

### 公开校订与校订后月键

NAOJ历史宿主结果另附当前月份的公开月校订条目，按校订后的阴历年、月与闰标记匹配；改月名的行与另印月首前后值的行分别保留，只有月名的行不补西历月首。未列不证明本月从未调整，9条节气记录和18条早期两历比较不猜绑为当前月校订。来源页此前已用于书目关系核对，本次新增完整表格规范化及逐月解释，不计新原典见证。

原印西历按数据库默认约定解释：1582-10-15含当日起格里历、之前儒略历；目录表本身未另写这项声明，所有209条实际明确月首日期均位于儒略侧。768年原印7月19日对应前推格里历7月23日；当前参考已包含校订，不能再改月、再进朔或移动配宿。这些同提供方记录不能认证古代平明或桧尾优先。详见第六十三轮报告（本地数据：`validation/sukuyo-naoj-adjustments-v63-validation.md`）。

### 大衍名义定朔与宿主月份依赖

764—861农历年另列名义A／D经朔、太阳与月行订正；793—819农历年按预先声明政策用D，其余用A，同时交付两个模型。经朔由现有宿主月首在固定三日内选择，不能反过来独立认证月名、置闰或颁历；名义JD／JDN未赋物理UTC／TT，也不改变现用历日、配宿或替作者判断进朔。

1212是完整宿主月份的数值实现对照范围，327是另选研究表行数；表外月在范围内仍列模型，现代HKO输入没有应用该大衍模型。固定when_exe系数、同提交gemspec的Takashi SUGA署名与论文表格／原始古籍逐字校勘分别列证。详见第六十二轮报告（本地数据：`validation/sukuyo-dayan-reconstruction-v62-validation.md`）。

### 符天研究的经朔与限值算术

具名2024研究的十五行算术与历史颁历分开：普通十一月和闰十一月保留各自循环分值，所选表仍处于退朔改月之前。入转明确使用未加闰应的闰余，日月订正值取自印表，尚未复原其函数。图注印值、索引干支、遗漏常数和取整差额不覆盖。

限值换算沿既有2015研究的8400／10000分模型作条件比较，不将分母写成2024所选图注原印，不以名义18时替代T1299平明、桧尾半日或宿主日界。现代中国历日说明另交付实际HKO年度来源及后端，当前返回没有附全域独立验收报告，不能用年度链接代替其他三轴的证明。详见第六十一轮报告（本地数据：`validation/sukuyo-futen-arithmetic-v61-validation.md`）。

### 桧尾目录候选与无补配月份

高山寺简目中84函1号id7744《檜尾口決》登记建久六年写，只作匹配SAT底本描述的候选，尚无原图或实物同一认证；79函85号四条含组目、包纸与正文，不能拆算独立写本。两次数字档案门户0命中不证明甲本或馆藏不存在。

桧尾初一未生成小月分宿时，单人和双人说明仍交付追踪中已有的前一参考日、阴历年月、闰月身份及月长；双人逐人明确半日是否声明，不用钟时补半，也不由同宿裁定次序。目录补充与修复均未改历日、主宿、候选及关系计算。详见第六十轮报告（本地数据：`validation/sukuyo-hinoo-catalog-v60-validation.md`）。

### 显式桧尾研究档案

可选 `calendar_profile=hinoo_t1299_host27`，把T2465《桧尾口诀》的闰月复用及小月补配规则应用于所选宿主历法，默认现代中国历。29日月缺少的三十日宿配给次月初一前半，后半仍为该月正常初一宿；前/后半解读参考Kotyk 2022，不自动映射为民用12:00。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2024-08-04 --time 09:00:00 --zone +08:00 \
  --calendar-profile hinoo_t1299_host27 --calendar-day-part first_half \
  --fields sukuyo.calendar sukuyo.reading_text rulesets \
  --strict-fields --no-include-snapshot-text
```

此例前一日是农历六月廿九，补配前半为星，后半为张；未给 `calendar_day_part`时保留候选星、张，主宿为null。已知民用09:00也不自动替用户选前半。双人接口分别用 `person1_calendar_day_part/person2_calendar_day_part`；`candidate_relation_analysis`只列候选条件下的双向关系，主关系仍为null。候选次序不是优劣排序，完整性标志只针对所声明现代重建口径。

闰月复用与补配的先后次序没有明确原典规定。1903-06-25及1957-09-24的前半在两种现代重建顺序下分别产生鬼/参和角/轸，均保留为partial。后半可单独确定。大正电子正文十二月三十日字面星与通用望宿法所得室也保留，不静默改字。顶层来源哈希仅指T1299，T2465另列SAT直接HTML响应指纹。第二十七轮新增京都新写本所选片段及例题对照，尚未完成整部抄本或影印校勘。本档案不是唐历或日本旧历的完整复原。

两人合盘另返回 `candidate_relation_analysis.shared_reconstruction_analysis`，只分析“双方共同采用同一套已声明现代重建”的明确条件，不断言古代各时期规则相同。完整边际外包络保存在 `unconstrained_rows`；在支持完整时，`rows`列同一模型内有联合支持的组合。每条 `joint_support`保留模型身份、双方各自参考日期、半日与宿名，不能再把这些字段分别投影后任意交叉。双方半日未知时各自独立；来源或宿主身份不同不绑定，覆盖不完整时不删原组合。“无共同支持”只限已列模型及共享假设，不等于原典禁止或历史绝不可能；两模型恰好同宿也不能裁定优先次序。它不改变单人主宿、不选定模型，也不把候选关系提升为确定相性。

`hinoo_source.critical_calendar_reference`另交付京都大学RB00017868《檜尾口決 朱校》第28幅的八个所选片段与三个例题：十二月初一虚、十五星、三十室；最后一项异于大正主文星。馆藏标新写，写成日期及其是否属于大正原／甲本未定，不把相合的单例当完整算法认证。校记“十六字”按字数重建到“故傍月”，仅截至“是傍十二月也”为13字；保留イ标记，不认证甲本无条件删除。伴随参考绑定实际大正引文，另有自己的JSON、图像和清单指纹。`short_month_assignment.leap_short_month_precedence.reconstruction_calculations`保存两条现代重建各自的前月上下文、前／后半望宿计算和同次源表指纹，不因此确定优先级。

原生 `reading_text`现在也按同次计算逐支展开前月、前后半查表月日及宿名，并区分京都选读、大正选文与宿主算法的例题；目录新写、传本身份未定及十六字校记重建限制随之交付。不是由新写本例题改写算法或解决半日钟时。

第十三轮修复源资料返回对象会污染后续计算的问题。修改取证辅助函数返回的锚点表，曾可令后续正月十五从翼变成角，而两种望宿算法仍同时显示一致；现在返回数据与缓存隔离。每次档案计算只捕获一份源表，主算法、缺日补配和重复月分支共用该次规则表及指纹；`profile_calculation.source_bundle_sha256`及各子计算的同名字段可以核对。此指纹标识规则JSON，不是古籍原文件；原文指纹另见source_sha256。两个算法共用同一锚点，数值一致不能替代独立原典或历表核验。

此前SAT服务维护时取得的cached_primary_excerpt保留为历史记录。第十八轮直接取得166,529字节官方HTML响应并冻结指纹；active_primary_evidence改指downloaded_primary_edition，交付两段原文及五条校记。书目注的原本为建久六年写高山寺藏本，甲本为宝历十一年写智山专门学校藏本；如半＋也、十／月及十六字异读删除等校记分别保留，不改写为同一正文。旧摘录末句的人工句号与下载原文闭引号不同，明确登记且不修改旧夹具。完整HTML不等于字图全部取得或影印校勘；完整响应作本地研究保存，仓库仅保存选定引用、指纹和验证方法。闰月段“其正月”指相对闰月的本月；小月段“假令正月”则举农历一月为例，不能把所有闰月都重复一月宿。半日钟时与两规则交叠次序仍未解决。

### 黑白月日名及昼夜条件

`sukuyo.calendar_day`补齐15组、30个入月日的日名、上/下卷一般日类和昼夜限制，来源为0392c29–0393c06及0393c18–0394c16。友朋／朋友、大战／力战、吉祥／吉相分别保留；“得财”是日名，不能据名推成所有交易适宜。现有20条日名事项规则，不将建宅扩大成迁居或宗教专属学法扩大成一般学习。第七轮补出十二／廿七日借贷差别：上卷仅限放债，下卷同时限放债与取债，不互相改写。

两卷偈文作“一夜”，散文作“十一日夜”；下卷0393c26夹注明说“所謂一夜者，十一夜也”，说明这是省文。第十轮纠正此前漏读夹注造成的错误：`time_restrictions`按十一夜交付，初一不再因一字省文增加夜限。`prose_verse_time_variant`在初一／十一保留字面差别，`prose_verse_time_semantic_conflict=false`说明本次释义已由源注解决。`verse_abbreviation_resolution`保留原字、注释、适用日及出处；下卷直接依注，上卷同偈依其平行散文及下卷注互证，不改写原文。

四组通用证言逐条交付原文和解除条件来源。一般日类的条件日清单仍有实际差异。`time_restrictions`列出昼或夜、日中或夜半后的例外及位置；**`clock_evaluation_status=not_computed`**，尚未将现代民用12:00／00:00认作原典太阳时边界。省文解释解决日序，未解决现代钟时；某项宜文不能覆盖时段限制，也不能转换成全天综合结论。

第七轮另补八条下卷逐日日名中的昼夜证言，不只读取通用散文／偈文清单。`clock_doctrine`保留0399b25–28所说平明起曜、昼八时／夜八时；该段没有逐项列出日内曜神顺序，不能用每日七曜顺序或西方24行星时补写。原文的确定性断语也不是实证验证结果，物理钟时映射仍未完成。

第三十九轮（本地数据：`validation/sukuyo-kenyu-clock-validation.md`）新增名古屋大学148.8-Ke藏、NIJL100159236《宿曜經撮要》的具名印本对照。`calendar_day.clock_doctrine.kenyu_printed_reference`返回实际参考日曜标签下的全部条件支时查表：图中昼分卯至戌八支，夜分亥、子、丑、寅各跨两格；例如日曜午行水、土曜寅支上金下土。没有用现代出生钟时自动选支或上下项，总层时曜继续留空，T1299本层的唯一日内解释与古代日界仍未定。56个曜字经两现有模型角色分别读图相合，但上刻／上判、晝／畫形、小字和行号等分歧照留，不能据格值补原字；两角色共享提供方和旧上下文，不是人类独立校勘。

第四十轮（本地数据：`validation/sukuyo-kenyu-lingbi-validation.md`）核读同册帧8右页的23行月朔曜条件表及帧7左页的序后入纸。`sukuyo.kenyu_lingbi_reference`交付具名表值：普通月仅条件于声明的宿主民用月首曜查询，不能拿当天七曜替换月首曜；未列的朔曜条件返回null，不能判成确定无陵逼。七月金曜止三日、十二月金曜止三十日均保留局部放大后的读数及初读修订。右表旁注“潤月全如本月”与左页“潤月朔宿全如本月”分别归属；闰月继承哪个朔曜未定时保留七种条件，不据此裁定T2465小月补配先后。月序或闰月身份缺失只限制这一新增参考层，不补推输入或阻断原有独立日宿、日号和事项计算。

入纸在“陵逼之間”内讨论三九，尤其“若有急事欲作之者”后才称可用衰危坏，同段列荣成友亲安不可取用。它自述御傳、末有取意，不能全当T1299逐字正文，也不把生命灾祸措辞转为个体断言。T1299下卷0398a18–26另要求知道实际天体所在宿；本印本月朔表不是这项天文计算，尚未用于主宿或事项汇总。序文寺名、署记、复杂字及字形规范化限制照留；所谓八十六年中唯六年无陵逼是未经复算的来源自述，不增加真实验证样本。两角色对23行最终读录相合仍不是独立人类校勘。古代平明、逐时曜序、整套轮图和闰月补配优先次序继续列为未完成。

同书第8帧的“潤月朔宿全如本月”仅明说朔宿；月大小取曜、轮图对位、“朔日二日兩日”“兩度値”及有分歧的推日句一起保留，未改写成T2465初一前后半或闰小月唯一优先算法。1833阁笔、1849自序／作品题录、据内容估1859的无刊记馆藏分别记录。新8个合成情境只扩展这项新印本组件的语义验证，不替换既有完整解释验收或其不利记录；现实样本仍为零。

最终夹具验收（本地数据：`validation/sukuyo-kenyu-clock-golden-followup.md`）仅同步一份宿占单人金样中的新增参考和原生说明片段；双人合盘完整规范化响应一致，既存星图／快照差异继续保留。C运行代码与B相同，未通过改写无关金样消除差异。

`sukuyo.reading_text`及根部快照改为依本次结果生成的原生说明，包含异表、三九方向、日名、所有匹配的事项条文与未判定的钟时条件。GPS覆盖文本坐标时使用实际解析坐标，零经纬度也正确显示；不再把计算所用0°显示成“无”。这只验证原生模板路径，另一模型自行撰写的解释仍须语义盲评。

### 七曜特殊日的各卷、各本读法

第十二轮将三类特殊日由硬编码主表改为带原文及校记的 `t1299_special_day_witnesses_v1`。`special_day_labels`继续采用上卷大正，保留原有21个组合；`special_day_evidence`另列下卷大正及两卷所载明本校记表，分别查看，不混合取有利结果。上卷甘露火曜的尾／井、金刚峰月曜心／女及火水曜互换，会使同一输入在不同见证中得到不同标签。明本只据所用底本校记重建，未宣称取得并独立校勘明刻本。

下卷大正罗刹日正文分别作“冒、底”，校记明本作“胃、氐”。前两字未归并为一般异体字：遇对应曜日时，下卷返回未定行和 `labels_complete_for_selected_day=false`，不能把空匹配当作确定没有特殊日。未定字可能涉及的不利条文继续在 `conditional_rules`保留，不计入已匹配宜忌；`unresolved_source_rules_present=true`时，不能只据宜条宣称全盘有利。下卷“月与宿合”的对照只按当前历日宿名称查原句，`physical_lunar_conjunction_evaluated=false`，不是实测月亮合宿，也未解决平明日界。

甘露日的学道求法、受灌顶及习学经法分别按各卷列证，只在已明确 `religious_learning`时匹配；普通学习和技艺学习不会因此得到甘露学习宜条。金刚峰的名称不推出所有事项有利，也不输出伤害操作。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-06-24 --time 12:00:00 --zone +08:00 \
  --activity study --activity-details religious_learning \
  --fields sukuyo.special_day_labels sukuyo.special_day_evidence sukuyo.activity_assessment sukuyo.reading_text rulesets.special_days \
  --strict-fields --no-include-snapshot-text
```

此例为火曜井宿；上卷大正不匹配甘露，上卷明本校记表匹配甘露，下卷所载明本仍不匹配。对照结果不代入当前主表或确定事项。2025-04-15火曜尾宿则按大正主表匹配甘露，明确宗教学法后可分别读取上下卷学习条文。

### 出行方向与版本异文

第十一轮补入下卷0397a26–0397b15“行动禁闭法”：四条具名日宿禁向、十二行宫名／日宿方向表，均进入独立 `travel_direction` 事项层。通过 `northbound_journey/eastbound_journey/southbound_journey/westbound_journey` 明确给方向；空列表或仅给远行／出国不自动推定方向，也不从出生地、GPS或目的地猜角度。原典未在本段给出方位角宽，东北等斜向不能擅自归类。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-13 --time 12:00:00 --zone +08:00 \
  --activity travel --activity-details northbound_journey \
  --fields sukuyo.directional_travel sukuyo.activity_assessment sukuyo.reading_text rulesets.travel_directions \
  --strict-fields --no-include-snapshot-text
```

此例历日宿为轸，方向章明确列北行为慎用，并保留“纵吉时亦不可行”夹注；它不能被其他条文的吉时描述抵销。`evidence_status`仍列所选全部条文的宜忌证言，不会用多数票给行动许可。壁宿南行则有真正冲突：逐宿章0396b21称不宜南行，方向章0397b06–07含壁日的南行宜条；二者均交付，结果保留conflicted。

`directional_travel`也保留所选日宿相关行的原文、方向来源、宫序字面及校记。前八宫行两两承接“已上”的方向句，明确记录这一文本绑定；不是按现代星座补方向。方向章以羊宫为第一、狮子宫为第五，不能与上卷以师子宫为第一的分足表合并，更不能据此确定个人本命宫。蝎宫“互”字未识别，不猜作氐，也不按明本把尾加入大正蝎宫。第十摩竭、第一羊、第二牛宫的所选大正文本行内注作凶，所载明本校记作吉；当前按大正交付并展示相反校记，不改写为一致。明本仅为所用底本内的校记，尚非独立明刻本校勘。

### 算曜直章的工程积算

东京大学T30107合册抄本另保存算曜直章选段。本轮领域函数`classical_weekday_arithmetic`按明确积年、入年月数、入月日数复算其整数公式，逐步保留整商与余数。入年月数先加入上位，再乘7、除228求积闰；不能把月份放在求闰之后。末尾甲辰及月曜分别计一，零余数为癸卯、日曜。

它没有接受公历／HKO／日本参考字段到这套积算的自动映射，也没有成为新的公开历法档案。同册后附的分数平均日和岁差重算另列，未混入前式常数500或伪装成同一算法。默认七曜仍采用声明宿主历日的民用午夜。原页、例题及失败反例（本地数据：`validation/sukuyo-weekday-arithmetic-validation.md`）说明当前可复算内容及尚未完成的校勘。

后附文化十三年重算另由`classical_mean_cycle_arithmetic`复算完整19年周的无偏置分数平均日；`classical_solar_recalculation`只复算所选两个太阳年系数及积年乘积。后者日周为一万，3652423.49669203须除10000才是日数，不能直接当作3652423日。四个选定分数／乘积数值在原文所示精度对上，但共同来自一组重算，不能算四个独立历史样本。

上一轮把全部12位小数描述为截断不准确：15112.873399715505是舍入值，截断应为15112.873399715504。现保存精确分数、舍入和截断显示，后续运算不读显示字符串。末尾周数暂读为235815，与所载950707.412894553709日除7所得135815不合，保留字形候选和差额，未擅改原文。该例“文化十三年二月经朔，水曜”与NAOJ所选月首1816-02-28的民用星期相合，仅为一个具名历日对照；经朔时刻、古代日界、唐代历元及完整订正链仍未接纳。原页指纹与限定复算（本地数据：`validation/sukuyo-weekday-recalculation-validation.md`）记录这些差别。

`day_evidence`现在要求上下文携带已支持的宿主时区，缺失时不再默认UTC+08。公开请求仍按其声明的历法默认政策构造上下文；这一内部检查不把后附公式用于公开历法。

1897年脇田文绍《缩刷宿曜经》印本第40–41页另载《算曜直章》。本轮九项所选整数算法常数与T30107读数相同；它们是相关传本，不能算独立历史观测。`classical_source_year_count`按“开元二年1501、以后每年加一、以前每年减一”导出具名年份的积年；1816标签得到2603，与后附例题相合。它不认定该年正月初一等于公历一月一日，也不接受公历瞬间、闰月次序或完整历元日期映射。

`classical_calibration_precision`另复算选定的五项订正精度对照。岁差分母取965850名义日，若误换成950737.1266…平均日，该例积日会差约0.097日；此为防误用代数反例。统一采用所选小数最后一位正负一个单位，不用拟合容差。两项精度对照不相容，保留原读数与精确分数；其中第一项相对于精确11/703基准，原文另列的基准小数转换尚未归一，不据此断定原书算错。第二项也仍需完整保留位数及独立转录核验。完整订正链、古代日界与八时曜次仍未接纳。详见印本与精度验收（本地数据：`validation/sukuyo-wakita-validation.md`）。

### 裁缝与穿衣条文

衣事查询使用 `activity=clothing`。`sukuyo.clothing_reference`按T1299下卷0397b16–27分别交付二十七句口诀、大正主文十四宿名单和明本校记重建；上卷裁衣原句另列。大正“餘並失”形成其余十三宿的限制，明本末句“並大吉”不提供同样补集。名单的“井／并”差异未被自动纠正，明本对井和未列宿的判断保留空值。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-02-11 --time 12:00:00 --zone +08:00 \
  --activity clothing --activity-details tailoring_garments \
  --as-of 2026-10-22T12:00:00+08:00 \
  --fields sukuyo.clothing_reference sukuyo.activity_assessment sukuyo.candidate_days sukuyo.reading_text rulesets.clothing \
  --strict-fields --no-include-snapshot-text --response-char-limit 0
```

此例为张宿。专章补集对裁缝列慎用，逐宿段落又有制作宜条；本次声明的裁缝归制作，三条证言均匹配，结果保留 `conflicted`。穿新衣及王者身份没有从裁缝动作推得。上卷“必被官夺”与下卷“張必官奪”仅按原句交付，不转成现实事件预测或评分。角宿上卷“終當逃亡”与下卷“角必安隱”亦分别保留；汇总列宜不代表所有原文已调和或现实风险为零。

38条选定衣事规则区分裁缝、制作、修理、穿着及新衣；只有裁缝→制作、新衣→穿着这两个声明的分类关系。“王者服新衣”须同时明确王者身份及新衣动作，“教女人裁衣服”“取衣取財”等未映射谓词另列，不扩大为普通裁衣或购衣。主题标注尚未获独立学术校勘验收。

完整且所有候选同属一项名单时，可解释共同表项；闰月候选未穷尽时，即使仅列一个毕，也不能据它确定当天列宜。同run衣事引用须包含完整 `candidate_days` 和 `clothing_reference`；通用activity引用不能绕过后者。该校验防漏引、篡改及错run，不代替自由文本语义审读。公共宿占接口仍要求明确 `time`；无时刻跨日候选的回归属于领域计算与引用校验层。本轮验证（本地数据：`validation/sukuyo-clothing-validation.md`）列出限定范围与原始证据。

### 天文二十八宿与活动条文

`mansion_method=equatorial_research28`现为默认：七个物理天体（日、月、水、金、火、木、土）使用地心当日真赤道/真春分点视赤经，按声明的现代距星赤经划分28个不等宽、左闭右开的宿界。`astronomy`返回赤经赤纬、宿界、宿宽、距边界角度、TT/UT1时刻、实际星历模型及星表指纹。星图宫制、当地经纬度和黄道选项不改变地心宿位或农历月日宿。天王星等外行星及虚点暂不赋此宿位。

第二十六轮起，`catalogue_sha256`绑定本次实际交给原生库的星表字节，`catalogue_sources_sha256`绑定同次解析的来源元数据字节；计算途中替换磁盘文件不会把新旧结果与指纹混配。原生库使用临时捕获星表，辅助文件及操作者路径顺序保留；指纹不认证古代宿界，也不覆盖所有外部星历文件。

`chart.objects[].su28`和宿内度数因纠正方法会变化；某些宿宽超过30度，显示不再模30。示例2025-03-04 12:00 +08，**历日宿为毕，物理月亮在本研究宿界中为娄**，两者不可替换。需要旧图时显式传 `--mansion-method legacy_equal28`，输出标为等分黄道示意；`--no-doubing-su28`不计算天文宿位。

天文研究分支只请求位置，共用引擎跳过未使用的速度导数与观测者角度。所选 JPL 内核仍须满足原生位置计算的实际依赖和范围检查；额外速度取样窗口不再使有效的赤经位置失败。历日本命宿与事项规则不因这一工程修正改变。

这套宿界复用声明的现代SIMBAD研究星表，并非唐代距星身份、历元与宿度复原。`classical_boundary_acceptance=false`，现代360度也不能直接等同古代周天度。42个独立[JPL Horizons](https://ssd.jpl.nasa.gov/horizons/manual.html)样本只核验七曜赤经、赤纬，不能证明古代宿界选择正确；靠近边界仍需星表及坐标不确定性分析。

第十四轮另修复星表目录与用户星历目录拼接过长时的原生查找失败。Swiss 2.10实现对搜索路径预留文件名空间，实际限制为242个编码字节；超长时会静默使用默认目录。现在优先使用同一目录的较短相对拼写，仍过长则使用计算期间的临时目录链接，保持原文件及搜索顺序，不改变进程工作目录；不能建立有效路径时明确失败，不以另一星表或较低精度结果冒充原配置。长路径与普通路径的坐标一致性已回归，尚未完成Windows平台验收。

活动查询支持结交、婚姻、出行、迁居、交易、学习及衣事七类（`social/marriage/travel/relocation/commerce/study/clothing`）：

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-04 --time 12:00:00 --zone +08:00 \
  --natal-mansion 奎 --activity marriage \
  --fields sukuyo.activity_assessment sukuyo.calendar_day sukuyo.personal_day astronomy params \
  --strict-fields --no-include-snapshot-text
```

此例命奎至毕为危，婚姻条文冲突。`activity_assessment`按三九、上／下卷宿性和七曜、特殊日及日名分层，保留全部匹配规则、上/下卷和段落；同时有宜与忌时返回 `conflicted`，不投票、不合成分数、不转为成功概率。`uncovered`表示选定条文无对应规则，未给本命时三九层为 `not_evaluated`。原有三九／上卷宿性／七曜等31条、日名20条、下卷逐宿40条、下卷宿性／七曜27条，共118条事项证据分库存放，另列方向、特殊日和本轮四条下卷三九补充规则。每条交付 `source_excerpts`，与另行抽取的原文窗口核对；字面包含检查不能认证主题标注或整部原典完整性。没有将月曜“私情出行”泛化成所有出行，也未将“出财”泛化为所有交易。

`personal_day.source_day_evidence`按11种三九关系分别交付卷别、选定原句和段落；不以双人结交的宜忌替代日课。第十四轮纠正下卷危／坏日“远行”条文误套到所有出行的问题：不提供路程时上下卷均保留条件项。下卷“又一说”另外列命、胎、危、坏日“不得进路”，只在personal_departure明确本人启程时匹配；安日“远行人入宅”只在long_distance_traveler_entering_residence明确远行人入宅时匹配。入宅、启程、一般旅行和远距离行程不互相补造。安日迁徙及荣日出家人启请法要另按原句交付；monastic_dharma_request须明确身份与请教法要的行为，普通religious_learning不能代入。下卷“己身三九若吉，但用无妨”的优先说明也保留，但尚未确定“长行历”覆盖现有各层的范围，不据此自动丢掉相反条文或合成吉日。

### 下卷逐宿、行为条件与宿月配合

`sukuyo.lower_mansion_day`索引下卷0395b23–0396c01的27个具名条目，提供40条六类事项证据。其中25条至少有一个事项分支须提供行为细节或继续文本校勘，不能一律算入确定宜忌；其余也只是文献证言，不保证现实结果。原有多主题规则亦按事项收窄：**设学不等于所有学习，入学受业包括从师受教，不能任意限于首次入学或推成所有考试；远行不等于一切短程活动。**

第七轮纠正了此前过窄与过宽两类映射：上卷初六／廿一“出行”没有“远”字，不再误限远行；下卷初二／十七则明确“远行”，不能当所有出行。下卷轸宿“远行向外国”需要远行与赴外同时成立，不能只给一项。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-04 --time 12:00:00 --zone +08:00 \
  --activity commerce --activity-details borrowing \
  --fields sukuyo.lower_mansion_day sukuyo.activity_assessment sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

此日历日宿为毕。“不宜取债放债”只有明确借贷行为才匹配；只给commerce或sale时，它仍为 `conditional_rules`，不泛化成所有交易的禁忌。该参数只声明已知细节，不表示其他条件已被否定；不得为得到有利结果补造事实。可传多个同类值：

| activity | activity_details |
| --- | --- |
| commerce | purchase、sale、business_operation、borrowing、lending、collecting_debt、repaying_debt、earning_money、sale_livestock、sale_lactating_livestock、purchase_precious_goods、purchase_livestock、land_purchase、land_sale、spending_property、receiving_property、returning_property、wealth_competition |
| travel | long_distance_journey、journey_abroad、personal_departure、private_journey、royal_or_official_traveler、long_distance_traveler_entering_residence、northbound_journey、eastbound_journey、southbound_journey、westbound_journey、water_journey、diplomatic_mission |
| study | founding_school、beginning_study、learning_with_teacher、skill_learning、classical_text_study、teaching_classics、religious_learning、monastic_dharma_request、debate_learning、riding_training |
| social | social_gathering、forming_friendship |
| clothing | tailoring_garments、making_garments、repairing_garments、wearing_garments、wearing_new_garments、royal_wearer |

`matched_rules`为本次事项和已声明细节实际匹配的证据；`conditional_rules`为尚缺细节或读法未校定的条款，不进入当前状态。`conditional_only`表示只有待定条件文，不能解释为已确定宜或忌。修宅／粮食入宅不扩大成迁居，生财、竞财也不擅自扩大为所有交易。

`detail_match`交付所需 `required_any_of`（至少一项）及 `required_all_of`（全部）、已满足与缺失条件、文本读法状态和是否计入。借入、出借、索债与买卖分别匹配；新增火曜出财／征债、安重索债、水曜举债等条文。行为标签只声明已知事实，不能为得到有利结论补条件。购入金宝／牲畜、田地购入／出售及骑乘学习等具体行为，沿声明的分类关系匹配上位买／卖／技能；`effective_activity_details`及 `detail_inferences`交付推导，原始 `activity_details`保留。分类不推断远近、目的、身份、付款方式、现金流或开始时间。

第十六轮将18条结交／聚会条文按具体动作限定。`social_gathering`不推出本次要结交，`forming_friendship`也不推出聚会；月曜聚会不再因“结交”条文误报冲突。`personal_departure`只明确本人启程，不能证明`private_journey`因私目的。下卷日曜“王公百官等东西南北远行”需要身份与远行两项同时明确，不由工作出差、方位或使节任务补造身份；上卷远行未加同样身份条件，独立保留。上卷月曜“私精”未默改为下卷“私情”。匹配条文的本次适用条件进入原生解释；`conflicted`仍表示已匹配证据兼有宜忌，但不同动作的宜忌不自动构成同条件原文矛盾，业日及危日婚姻等真实相反见证继续保留。

规则缓存以同次读取的字节生成数据和SHA-256；进程中磁盘换表后不会把旧缓存冒报成新文件指纹。修改来源须重启加载并重新验证。返回的规则、分组及桧尾资料已作隔离，调用方修改结果不会污染下次计算。

氐宿后0396a15–16另有未署宿段落，保留归属未决；女宿“呈学伎艺”即使给skill_learning，也暂不计入确定宜忌。亢宿宜不／不宜、危宿皈／贩保留字面及明本异文。XML段落边界不等于宿条目边界，柳与七星在同一段中，索引按原文具名和页栏行划分。

`sukuyo.conjunction_doctrine`补充0395b09–21的六宿未到、十二宿左右合、九宿如犊随母。末九宿成员由27宿序扣除已列前18宿推得，明确标注推导。此处只按本次历日宿名交付文献分组；`applied_to_physical_moon=false`、`angular_offset_degrees=null`，没有发明统一角距、移动现代月亮宿界或宣称求出过宿钟时。未定历日宿的各候选仅列条件分组，不选主组。

### 下卷七宿性、七曜及相反证言

第八轮 `sukuyo.lower_methods`补入下卷0396c02–0397a25的七宿性及0398c09–0399b20的七曜章法，新增12条宿性、15条七曜事项证据。上卷宿性继续在 `nature`；下卷用明列成员独立索引，胃在上卷急速、下卷猛恶。参考表中牛宿保留，不能代入27宿历日。

轻宿段大正标题作“軫”，校记0397004明本作“輕”；按段内明确的井、亢、女、虚、危五成员索引，不误添第六宿。急速段大正“賣交關”与明本“買賣交關”（校记0396032）分别保留，当前选定大正主文，故下卷卖交关不自动用于购入。上卷另有买卖条文时仍独立匹配。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-04 --time 12:00:00 --zone +08:00 \
  --activity commerce --activity-details collecting_debt \
  --fields sukuyo.lower_methods sukuyo.activity_assessment sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

此例为火曜：上卷不得出财征债，下卷宜征债，`weekday`与 `lower_weekday`分别列忌与宜，状态保留 `conflicted`。同日上卷结婚为宜、下卷成亲不吉也同时保留。不用条文数量裁决，不以纳入下卷宣称原典已完整验收。下卷平明日界仍未映射，七曜继续按声明的UTC+08民用历日索引。

还钱按偿还债务核对，不能等同返还任意物品；习读经书不任意限为宗教书，学论议不任意限为宗教学法。水路／使节行程、骑乘学习、田地买卖、金宝／牲畜购入及聚会庆祝各按具体细节，营造宅舍不自动代替迁居。

### 二十七宿四足与十二宫查表

`palace_reference`完整实现T1299上卷0387b02、0387b14–0388a02的27宿×4足＝12宫×9足。宿占见 `sukuyo.palace_reference`，双人见 `person1/2.palace_reference`。宫序从师子宫开始；牛宫不是牛宿，宫序也不是星图House编号。太阳分／太阴分是原典分区，不是现代占星的昼夜生盘。

原文列各宫占某宿几足，并未逐格写第几足；代码沿原典宫序展开并明示1..4足序约定。翼等九宿跨宫，不能凭一个历日宿选出唯一宫：

| 宿名 | 第1足 | 第2足 | 第3足 | 第4足 |
| --- | --- | --- | --- | --- |
| 翼 | 师子 | 女 | 女 | 女 |
| 角 | 女 | 女 | 秤 | 秤 |
| 氐 | 秤 | 秤 | 秤 | 蝎 |
| 斗 | 弓 | 磨竭 | 磨竭 | 磨竭 |
| 虚 | 磨竭 | 磨竭 | 瓶 | 瓶 |
| 室 | 瓶 | 瓶 | 瓶 | 鱼 |
| 昴 | 羊 | 牛 | 牛 | 牛 |
| 觜 | 牛 | 牛 | 婬 | 婬 |
| 井 | 婬 | 婬 | 婬 | 蟹 |

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 2025-03-12 --time 12:00:00 --zone +08:00 \
  --textual-pada 1 \
  --fields sukuyo.calendar sukuyo.palace_reference sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

该日为二月十三、历日宿翼，显式查第1足得到表内师子宫；第2足则查得女宫。`textual_pada`是查表条件，不是计算得出的出生足位。双人分别用 `person1_textual_pada/person2_textual_pada`；省略时保留四足，没有默认取第1足，也不从钟时、House或现代月亮经度补足位。

毕等四足同宫时可仅确定表内宫名，仍不确定足位。桧尾档案2024-08-04候选星／张均落表内师子宫，可单独交付这一有限结论；默认闰月政策未定、候选未保证穷尽时则不选唯一宫。所有情况下 `birth_pada_established=false`、`applied_to_modern_chart=false`，未校定历史黄经原点，也未据此确定个人本命宫或合成宫位相性。

### 时区、范围与闰月

- 默认中国历范围1901-01-01至2099-12-31，固定UTC+08；显式HuTime日本参考范围1872-02-09至2031-01-22，固定UTC+09。已知出生时刻先从其明确时区转换至所选参考日期；不套八字23点换日或真太阳时。
- 未知出生时间时，按所给当地日期、时区完整列所选宿主历法的可能日期；只有完整候选支持时才确定宿，不自动取中午。夏令时不存在或重复的已知钟时不能静默选择一个瞬间；整天跳过的当地日期不能当作有效出生日期。
- 这里不是唐代历法或日本地方旧历的复原。香港天文台未来历表的午夜附近日期也可能随天文预报更新；证据以冻结版本为准。
- 默认T1299望宿档案不隐式套入桧尾补配；可选桧尾研究档案及其歧义见上文，不给默认唯一历史规则。`leap_month_policy=unresolved`时已知一方、农历和候选仍返回，关系保持null，`status=partial`。明确选择 `repeat_month`可沿用同名月，但不能宣称完整T2465历史算法已实现。
- 摘要首轮见工具发布的 `evidence_views`；展开同run结果而不重新计算。完整输入合同由生成器维护：[宿曜](contracts/sukuyo_compatibility.json)、[宿占](contracts/suzhan.json)。

历史NAOJ参考另返回 `calendar_reference.day_ganzhi_reference`：以原始响应的日干支锚点和公历序数日差递推，固定UTC+09民用午夜换日。23,166个捕获月首日干支与225条逐日响应均另行核对；它不是八字日柱，也不证明古代地方日界。东京大学《大日本史料》延喜三年六月版面中四个明确日期标记作为一个限定月份的对照，保留论文日期异议，详见日干支验收记录（本地数据：`validation/sukuyo-day-cycle-validation.md`）。

```bash
uv run --locked --extra dev fatebridge suzhan \
  --date 0903-07-13 --time 00:00:00 --zone +09:00 \
  --calendar-basis japanese_naoj_historical_utc09 \
  --fields sukuyo.calendar.calendar_reference.day_ganzhi_reference sukuyo.reading_text \
  --strict-fields --no-include-snapshot-text
```

本例所选参考为延喜三年六月十一、日干支庚辰。原始锚点的负序数日仅作公元1年边界的来源上下文，未开放公元0年出生输入。

## 验证范围与现实预测

| 维度 | 验收证据 | 仍未证明的内容 |
| --- | --- | --- |
| 算对历法与物理坐标 | 1901—2099年共72,684日逐日对照HKO；显式日本参考1872-02-09至2031-01-22共58,057日公开计算链路对照HuTime逐日原始记录，其中327日另对照NAOJ；42个JPL赤经赤纬样本、固定2角秒阈值；28宿边界与跨30度显示回归 ；NAOJ历史参考683,734日内核对源、46,310个月首／月末公共管线日期核验，保留210个跨来源分歧日 | 历史唐历、完整日本旧历和历史日界、逐年神宫刊本及全范围独立校勘、范围外日期、古代宿界选择、全时域坐标精度；未来历表可能修订 |
| 符合某部原典 | 指定版次段落、360格字面异表、望宿两法360组及5个字面例题、可选小月补配、原文例题27关系、729方向组合；六宫宿计数另有三个原注例题及27起点回归；108足表、上／下卷七宿性及七曜证言、上卷21个特殊日组合及四见证84表位／756查询格、118条既有事项原文窗口、另38条衣事动作规则及二十七句衣事原文／三条校记、16行方向原文及108方向格、30日名与八条逐日时段证言；T2465直接原段及五条校记 | 整部T1299相关章法及其异文、主题标注独立校勘、衣事动作标注及明本独立刻本、日式抄本校勘、历史半日钟时映射、闰月补配次序、原典七曜时、实际七曜犯宿等 |
| 解释忠于计算 | 同run完整上下文引用检查；原生结果说明保留方向、候选、所有匹配条文及钟时未定；更正共享咨询资料的月亮经度及综合分误述 | 原生模板和字段校验不能认证真实模型自由文本语义；八组旧快照、六组衣事、四组天文／历日区别及八组补配／日界等问题的解释分别通过双代理分离上下文复核，均为定向合成案例，尚无广泛独立语义验收 |
| 能够预测现实 | 真实样本0；已有配对前瞻注册、实际材料指纹、窗口前预测封存、盲法结局表与到期评价流程；合成记录验证缺失／弃权保留原分母、强逐例基线可使技能分转负、新来源不能复用旧承诺 | 独立先验基线、真实招募同意、外部可信时间戳、未接触的现实结局、独立裁定和复现；尚无现实命中率或预测效力认证，不能用程序、原典或合成指标替代 |

`validation.sukuyo.verify_sukuyo_context_claims`在一般事实核验之上，要求所选主题的完整上下文，拒绝只引用冲突日的一条真实宜文、遗漏反向关系或省略闰月/时段条件。v4另强制完整候选历日数组及衣事参考。通过状态为 `verified_context_complete_quotes`，仍明确 `semantic_review_required=true`，不把机器引用检查当语义满分。

第二十二轮衣事语义复核（本地数据：`validation/sukuyo-clothing-semantic-review-execution.json`）的六份衣事解释均被复核者判为通过，未报告事实或关键条件问题；原答案及全部裁定均保留。它与此前八例属于不同冻结源码上的定向合成案例，不合并成总体准确率、样本覆盖率或现实预测成绩。

第二十八轮双路径语义复核（本地数据：`validation/sukuyo-reading-semantic-review-execution.json`）分别记录八份模型解释和八份完整原生说明。相同八个开发案例在修复日界范围文字矛盾及三处原生输入交代遗漏后重跑；前两次执行、全部原答案和不利裁定仍在归档，不视为新留出集，不把两种生成路径合成总体准确率。原生说明现在保留输入时刻至宿主参考历日的换算关系，并将缺时输入的推导候选与已观测出生日期分清。另有四个追加日界／改历案例，日期输入案例明确验证领域层，不宣称公共宿占已接受未知钟时。

该轮第三次八组复核的两条路径分别八份通过，共审查612项实质断言；前次三项原生遗漏仍保留。四个追加案例（本地数据：`validation/sukuyo-reading-additional-semantic-review-execution.json`）单独报告，不将相关断言数当独立样本数，不以通过这些定向案例认证普遍可靠性。

第二十七轮八例语义复核（本地数据：`validation/sukuyo-boundary-semantic-review-execution.json`）覆盖补配交叠、明确半日条件、跨参考日界、征债冲突、足表、六宫宿与重复日期。八份生成解释均通过，复核160项实质断言；另八个人为错误对照均被判需修订，发现14处主要问题。两组结果分开，不合并成模型正确率。原答案、控制文字和全部裁定见证据归档（本地数据：`validation/sukuyo-boundary-semantic-review-evidence.zip`）。两代理复用既有分离上下文，控制错误较明显，且本地封存无独立时间戳；这不证明广泛解释能力或现实预测效力。

第二十六轮四例语义复核（本地数据：`validation/sukuyo-sky-semantic-review-execution.json`）检查现代天文宿位、旧示意方法、关闭标注及闰月未决的解释，四例均通过，复核87项实质断言。生成与复核沿用用户授权的两份既有分离上下文，不代表新建隔离上下文或独立人工校勘。完整原输出、视图、答案及裁定见证据归档（本地数据：`validation/sukuyo-sky-semantic-review-evidence.zip`），不能由四例通过推广为全体解释可靠。

第十二轮特殊日见证与条件验收（本地数据：`validation/sukuyo-special-days-validation.md`）记录当前实现；第十一轮出行方向与版本证言验收（本地数据：`validation/sukuyo-travel-directions-validation.md`）、第十轮夹注释义与时段纠错验收（本地数据：`validation/sukuyo-time-gloss-validation.md`）、第九轮未知时刻日期映射验收（本地数据：`validation/sukuyo-date-support-validation.md`）、第八轮下卷章法及相反证言验收（本地数据：`validation/sukuyo-lower-methods-validation.md`）、第七轮条文适用范围与来源一致性验收（本地数据：`validation/sukuyo-rule-scope-validation.md`）、第六轮分足与宫宿边界验收（本地数据：`validation/sukuyo-palace-pada-validation.md`）、第五轮逐宿与行为条件验收（本地数据：`validation/sukuyo-lower-mansions-validation.md`）、第四轮望宿与桧尾验收（本地数据：`validation/sukuyo-fullmoon-hinoo-validation.md`）及第三轮清单（本地数据：`validation/sukuyo-three-axis-validation.md`）保留此前快照。尚未证明全部要求，不计算一个替代性的“权威总分”。

完整步骤、文件格式和可执行命令见前瞻验证流程（本地数据：`validation/sukuyo-prospective-protocol.md`）。每个人不能在多对关系中重复计作独立样本；训练主体不混入验收，缺失保留在分母，到期一次评价，传统标签不自动转成概率。本地时间与哈希不能自行认证同意、外部时间戳或裁定独立性。独立语义复核按冻结案例另行记录，少量案例通过不代表广泛解释能力已验收。

第三十一轮（本地数据：`validation/sukuyo-witness-layers-validation.md`）补入善通寺109-5《护摩法略抄》的具名影像对照：13个吉祥日号、八条昼夜限制和承和七年八日曜序，正文名单与T1299在9／10／16／24／25的成员身份不同，未列不是忌。`calendar_day.japanese_selected_reference`不覆盖现用日类或事项；旁注未接纳、抄本实物年代及T2465身份未定。方向规则的 `source_passages`另保留17个原段的正文／行内注，壁宿正文南行忌与方向夹注南行宜均交付，不裁定优先。古代日界、桧尾半日、闰月补配顺序和全本校勘仍未完成。

第三十二轮（本地数据：`validation/sukuyo-clock-position-validation.md`）补入下卷248字特殊日段与93字平明分时段的明本位置校记：两端互指是一组异文，邻注删“一”另存。`calendar_day.clock_doctrine.textual_position_reference`与`special_day_evidence.textual_position_reference`交付同源证据；∞为位置转换，不能改写成八改六、删掉分时段或完整明刻本重建，也不覆盖上卷曜位／宿字异文、当前主表、事项或补配次序。

第三十二轮语义复核还发现四份生成解释漏掉善通寺八条昼夜条件、两份原生说明漏交已确认的宗教学法输入。首版不利裁定完整保留；原生说明已增加明确输入行，推导分类另列，解释指导保留该来源的全部昼夜条件。修复后的同题回归与首版分开报告，不算新增独立样本。

第三十三轮（本地数据：`validation/sukuyo-clock-units-validation.md`）将 `calendar_day.clock_doctrine.historical_clock_arithmetic` 作为具名研究参考交付。所选50刻模型中一辰刻25分，初为零刻，時正为12½分，四刻一分是下一辰刻边界，不能据此确定民用换日。英文摘要的half koku与正文／表3的半分读法分别保留；日文摘要仅写半，不能补上未印单位。半分144秒与半刻864秒只是在名义24小时下的换算。表中34条和数为25分，另4条多1分、2条少半分、2条少1分；既不改表，也不把同一研究表格计作独立观测。论文对所选日记的太阳中心几何地平解释属于作者推断，本轮未复做其太阳位置比较，不把它用于T1299平明、现代输入日期或闰月补配。

第三十三轮首轮语义复核保留生成解释6项通过／2项需修订、原生说明0项通过／8项需修订的裁定。随后补齐末段18、延喜式刻序和显式半日输入，并要求交付未核定罗刹条件的实际慎用含义。首版15份材料及失败原句完整另存；同八题回归不增加独立案例，也没有修改历法或事项计算结果。

修复版同八题的8份生成解释与8份原生说明均通过完整复核，原标准和首版失败仍保留；这是复用两角色上下文的已反馈回归，新增独立案例为0。709项冻结领域测试通过，既有日期范围、210个来源分歧、两处精度参考差别和2角秒容差均不变，真实样本仍为0。

当前离线证据见第三十三轮快照审计（本地数据：`validation/sukuyo-clock-units-checkpoint-audit.json`）：Moshier模式42个样本最大赤经/赤纬差异约1.38角秒；保留原定2角秒门槛，六个瞬间另核对星表及元数据指纹。此前第二轮工程记录（本地数据：`validation/sukuyo-depth-verification.md`）、第二轮审计（本地数据：`validation/sukuyo-depth-audit.json`）及首轮报告（本地数据：`validation/sukuyo-local-audit.json`）是历史快照，不替代当前代码指纹。旧审计的prose_verse_disagreement_days只能证明其当时记录的字面差别，不能继续据此宣称一夜／十一夜是未决语义冲突；该漏读已由第十轮更正。没有宿曜真实结局数据，前瞻流程尚未注册真实研究。

英文HKO原表缺失2069-12-30；中文版该日为十七，作为明确补充来源保留，未静默插值。下载与再生成：

```bash
uv run --locked --extra dev python scripts/fetch_sukuyo_reference.py --download
uv run --locked --extra dev python scripts/fetch_sukuyo_reference.py --check
uv run --locked --extra dev python scripts/build_sukuyo_japanese_calendar.py --check
uv run --locked --extra dev python scripts/build_sukuyo_historical_calendar.py --check
uv run --locked --extra dev python scripts/check_sukuyo_historical_daily.py
uv run --locked --extra dev python scripts/audit_sukuyo_taibai_primary.py
uv run --locked --extra dev python scripts/audit_sukuyo.py --output /tmp/sukuyo-audit.json
uv run --locked --extra dev pytest -q tests/test_sukuyo_boundary_receipts.py tests/test_sukuyo.py tests/test_sukuyo_depth.py tests/test_sukuyo_calendar_text.py tests/test_sukuyo_time_gloss.py tests/test_sukuyo_directions.py tests/test_sukuyo_special_days.py tests/test_sukuyo_profiles.py tests/test_sukuyo_lower.py tests/test_sukuyo_lower_methods.py tests/test_sukuyo_padas.py tests/test_sukuyo_rule_scope.py tests/test_sukuyo_date_support.py tests/test_sukuyo_study.py tests/test_sukuyo_transports.py
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
```

下载仅在显式 `--download` 时联网；普通运行及测试读取冻结原始ZIP。生成修正时把公布历表作为外部资料，不把生产输出写成“标准答案”。若未来资料、库版本或差异集合改变，重新审查源数据和来源缺口，不能为保持分数静默改期望值。

English scope: calendar-based 27-mansion Sukuyo defaults to the fixed UTC+08 modern Chinese calendar. The explicit Japanese reference option uses frozen HuTime 1002.1 daily records for 1872-02-09 through 2031-01-22 under a declared fixed UTC+09 policy; it does not reconstruct historical Japanese local time or certify complete Jingu source collation. T1299 full-moon counting and the Hinoo research addendum apply to the selected host calendar; textual-half and precedence uncertainty remain explicit. The independent NAOJ mansion table corroborates the counting method, and 327 NAOJ calendar dates corroborate only the 1872 daily reference segment. Physical seven-luminary mansions default to a declared modern unequal equatorial research model, independently sampled against JPL; ancient boundaries remain unaccepted. The pair-aware prospective workflow has no real samples or registered real study. Classical agreement, semantic fidelity and real-world performance remain separate claims.

Historical reference scope: the explicit japanese_naoj_historical_utc09 basis uses frozen NAOJ month starts for proleptic Gregorian AD 1 through 1872, under a fixed UTC+09 date policy. It retains early reconstructed chronology, all 210 differing dates against HuTime 1001.1, and the two-day final Meiji old-calendar month. The providers partly share historical sources. Source conformance does not certify published ancient calendars, historical local clocks, complete manuscript collation, free-text interpretation fidelity or predictive efficacy. Year-zero derived interval endpoints do not enable year-zero birth inputs.

Taibai reference scope: the final T1299 chapter is a printed lunar-day direction table, distinct from physical Venus. Taisho lists ten rows; the Ming apparatus deletes the sky row for days 10, 20 and 30. Missing text is not absence of the deity or travel permission. Neither a horizontal bearing for sky/underground positions nor a movement-alignment rule is inferred. Selected SAT and CBETA apparatus differences remain explicit; independent manuscript collation and free-text semantic acceptance are incomplete.


第八十轮：梵文版本、原刊误读修正与独立语义扩展（本地数据：`validation/sukuyo-sanskrit-editions-v80-validation.md`）。各版计时链及未定日界／补配先后分开保留，旧四轴与失败门槛未改。


第八十一轮：共同模型交付、日界与版本核查（本地数据：`validation/sukuyo-yano-delivery-v81-validation.md`）。四状态合同及具体支持已修正；原180题仍有重要遗漏，日界／补配争议与零样本前瞻门槛继续保留。


第八十二轮：真福寺历法平行段与合配册分层（本地数据：`validation/sukuyo-composite-witness-v82-validation.md`）。新增影像定位及异读保全；原尺寸收图门槛仍失败，原历法与验收标准未改。


第八十三轮补充馆方版次、旧阅览器页次与完整工程答复（本地数据：`validation/sukuyo-native-and-audit-v83-validation.md`）；工程取证按[完整答复指引](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/sukuyo-engineering-evidence.md)绑定实际问题及完整相关证据。原尺寸、古代日界、半日和闰小月先后未裁定，原180题失败及四轴原门槛继续保留。

## 所选影像研究随结果交付

桧尾配置新增 `hinoo_source.critical_calendar_reference.image_witness_research`，宿占与双人相性随实际结果保留冻结采集日期、真福寺分宿段、名古屋上下卷配合本、天文台旧入口页次、双方首读及未决字句。新增说明没有把现代民用时刻选作原典半日，也没有选定闰月与小月补配交叠先后；原尺寸仍0／17，现实样本0。

实现与本轮验收（本地数据：`validation/sukuyo-witness-delivery-v84-validation.md`） · 来源与剩余问题（本地数据：`validation/sukuyo-witness-delivery-v84-sources.md`） · 前瞻流程（本地数据：`validation/sukuyo-witness-delivery-v84-prospective.md`）
