# 梅花易数计算、原典与验证

`meihua_analysis` 以指定公历钟时查中国农历，执行《梅花易數》年月日時起例。`meihua_cast` 接收物件数量、声音、长度、已核定字形／四声、端法资料或已有单动爻卦。REST、MCP、CLI 共用计算；不以通过软件测试宣布全书符合或现实预测有效。

[文档中心](README.md) · [时间入口合同](contracts/meihua_analysis.json) · [显式起卦合同](contracts/meihua_cast.json)

| 任务 | 阅读范围 |
| --- | --- |
| 选择起卦入口与输入 | [对应章节](#入口输入与取数) |
| 核对钟时、农历与交节 | [对应章节](#历法时区与资料精度) |
| 解释体用与条件 | [对应章节](#体用动静与条件推理) |
| 核对所问题篇与外应 | [对应章节](#问事专题与现场外应) |
| 复核天时规则、固定研究和负结果 | [对应章节](#天时占与固定天气研究) |
| 运行本地检查 | [对应章节](#运行与验收) |

规则与来源按具体分支读取；天气研究保留历史版本、固定分母及负结果，不作为当前咨询的成功率。

## 入口、输入与取数

### 来源与规则范围

采用维基文库固定修订的[卷一](https://zh.wikisource.org/w/index.php?oldid=2690596&title=梅花易數/卷一)、[卷二](https://zh.wikisource.org/w/index.php?oldid=1441921&title=梅花易數/卷二)、[卷三](https://zh.wikisource.org/w/index.php?oldid=1441927&title=梅花易數/卷三)，时间规则集为 `meihua_lunar_time_v1@1.0.0`。转录尚未完成全书影印校勘；另有先前九处选段校读及天时章当前规则关联的影印选段，不认证作者归属或版本年代。

| 所据章节 | 实际规则 |
| --- | --- |
| 卷一「周易卦數」「年月日時起例」 | 子年至亥年为1至12，农历月日按序数；年月日和除8为上卦，加时支数除8为下卦，总和除6为动爻。整除取8或6，分钟不另加数 |
| 卷一「互卦起例」 | 下互取二三四爻，上互取三四五爻；纯乾、纯坤依「乾坤無互，互其變卦」取变卦之互 |
| 卷三「變卦式八則」「體用互變之訣」 | 动者为用、静者为体；体在上则上互为体互，反之亦然 |
| 卷二「體用總訣」 | 用、互、变分别表示传统初、中、终分析层次；变用及两互始终与本卦静体比较，不在变卦重新分体用 |
| 卷一「卦氣旺」「卦氣衰」 | 返回原文明确列举的旺、衰；其他元素标「原文未定」，不扩充成未经声明的数值权重 |

各条原文、章名与规则类型在 `meihua.ruleset`；逐步算式及取互对象在 `meihua.rule_trace`。原文中的占验故事仅用于核对演算，不能充当经独立核验的现实预测样本。

### 显式原始资料与已有卦

`meihua_cast` 的 `casting.method` 是必填判别字段，只有对应方法的参数可用。无需出生资料，不补当前时间；未提供已核定的 `season_month_branch` 时，季令返回 `null`，而不是假定一个月份。原有方法采用 `meihua_explicit_casts_v1@1.5.0`；新增的所选类别端法另用 `meihua_observed_categories_nlc1925_v1@1.0.0`，均与公历时间换算入口分别标记。

| method | 必要原始资料 | 取数范围 |
| --- | --- | --- |
| `object_count` | 实际物件数量 `count` 与确认的 `hour_branch` | 物件数为上、时支数为下；取爻以原数量或声明的上卦卦序，加原时支数一次。超八保留 `line_sum_basis` 的两套结果，不将下卦余数当作原时数 |
| `sound_groups` | `first_count/second_count/hour_branch` | 两组实际声音依序取上下卦，加时数取爻；超八边界保留 `line_sum_basis` 与另法动爻，不能把原例1和5外推成唯一计数口径 |
| `observed_trigrams` | `upper_trigram/lower_trigram/hour_branch` | 端法以已确认的物象为上、方位为下；按乾一、兑二等先天卦序加时取爻，不用洛书数代换，不自动猜现场取象 |
| `observed_categories` | 已确认的 `subject_category/subject_description/single_subject_confirmed/direction/direction_role/hour_branch` | 只查文明书局所选五类端法物象及八方；来、往、所在关系必须明示，来方不反换成行进方向；先天卦序加原时支数一次取爻 |
| `length_zhang_chi` | `zhang/chi`，可记录 `cun` | 丈数上、尺数下，合原数取爻；寸数记录在 `ignored_components`，不参与；不加时 |
| `length_chi_cun` | `chi/cun/hour_branch`，可记录 `fen` | 尺数上、寸数下，合原数加时取爻；分数不参与 |
| `single_character_strokes` | 楷书 `script_style=regular`、`left_strokes/right_strokes/total_strokes` | 接收已核定的左右阴阳画，全画取爻；草书、缺画或重复计画拒绝，不自动拆字 |
| `text_strokes` | 二三字的实际 `strokes` | 少字为上、多字为下，合原画数取爻；不以现代规范字笔画替换实际字形 |
| `text_tones` | 四至十字逐字四声 `tones`；可声明 `tone_reference` | 平／上／去／入为1／2／3／4；少字为上，合原数取爻，不暗加时。音系与来源声明未经自动鉴定，不把现代拼音调号代入，不将四声一概当作唯一中古音 |
| `text_count` | 已确认 `character_count`；`text_basis` 与 `line_sum_basis` 分别声明文字依据和取爻口径 | 默认固定转录至100字、默认原字数取爻；影印“百余字”须显式选依据，超过100标为原文精确范围未裁定的软件扩展。原字数与两卦卦序数不同则保留两套实际卦变，不加时、不静默猜字数 |
| `existing` | 初爻至上爻 `hexagram_code`、唯一 `moving_line` | 沿用实际原卦，不重起；不接收多动爻，也不猜原始时刻 |
| `lunar_time_added_count` | 已确认 `year_branch/lunar_month/lunar_day/hour_branch/added_count` | 农历年支数、月、日及加数为上卦原数，再加原时支数一次作为下卦及动爻原数；不自动查姓氏笔画或补公历年份 |

#### 按已报物象类别起端法卦

`observed_categories`把所选原文的归卦查表放在领域计算中，不要求调用方先算出上下卦。它只接已确认的原书类别与单一对象，不分析照片或描述来猜取象，也不设老人、少年的数值年龄界线。五类来自文明书局卷一的明确原例：

| subject_category | 所选原例类别 | 上卦及取爻数 |
| --- | --- | --- |
| `elder_person` | 老人 | 乾1 |
| `young_person` | 少年 | 艮7 |
| `cow` | 牛 | 坤8 |
| `chicken` | 鸡 | 巽5 |
| `dry_wood` | 槁木、枯木 | 离3 |

普通木材、未确认枯木的落枝、未知人物类别、其他动物或声音不能默认套入这五类。`subject_description`保留已报资料但不用于覆盖类别；`single_subject_confirmed`须明确为布尔`true`，数字1、`false`及缺项均不接受。此确认不是现场鉴定，也不代表完整起占条件已裁定。

`direction`是已确认的八方标签。原图南离、北坎、东震、西兑、东南巽、西南坤、东北艮、西北乾；取数为先天卦序乾1、兑2、离3、震4、巽5、坎6、艮7、坤8。后天的方位不等于用洛书宫数取爻。不会从GPS角度自动划扇区、推定北向或补磁偏角。

`direction_role`必须分别给`from`（从该方来）、`toward`（往或落向该方）、`at`（在该方）。本入口直接使用所报方，不改成相反行进方向：老人原例往巽方用巽；少年从离方来仍用离，不能因行进向北而换坎。动物所在方、枯枝落地方分别如实填写；不知道参照关系时不补。它也不会据此填入占者坐行立或外应资料。

取爻用上卦数、下卦数及所报原时支数相加，除6余零为6；时数只加一次。`meihua.seed.observation_basis`保留逐项输入路径、对应原句、原页及查表结果，`rule_trace`保留实际算式。`subject.quote`含原例上下文，原例句里的方位不替代本次`direction`字段，故事结局也不是本次计算所得。新方法使用单独配置，既有`observed_trigrams`仍接调用方已经确认的上下卦，`existing`仍只沿用原卦。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"observed_categories","subject_category":"dry_wood","subject_description":"虚构工程示例：一根已确认的枯枝向西坠落","single_subject_confirmed":true,"direction":"west","direction_role":"toward","hour_branch":"辰"}' --fields input_normalized meihua.seed meihua.base_hexagram meihua.changed_hexagram --strict-fields true --response-char-limit 0
```

该示例取上离3、下兑2，加辰5共10，四爻动，睽变损。所选来源及冻结清单（本地数据：`../tests/fixtures/meihua_observed_categories_v1/manifest.json`）含五则复用原例和480组类别／方位／时支的参数核对；参数格点有240种本卦及动爻几何，其中也包含原例组合，不作485个独立样本。所有现场声明均未独立核实，完整起占条件、其他取象路径及原文叙事争议未裁定；原书故事不计作新增现实预测证据。

长度以已经确认的传统单位数输入，不自动从米、厘米换算或四舍五入。部分单位为零按余数零取坤，是软件扩展约定。字占遵具体章节和演算例，不将一般“取爻当以时加之”机械套到全部方法。合同见[显式入口](contracts/meihua_cast.json)。

加数法按文明书局本《起卦加數例》的明确演算：寅3、十二月、初一共16，加王姓原文给出的4为20；再加午7为27，上震、下离、三爻动，丰变震。影印此处为“零三为爻”，固定转录1441921另作“余三为初爻”，保留异文而不把27余6改成初爻。田6、王4、韓21只表示这则原书给定的数，不是现代通用笔画表。三例依次为井变升、丰变震、益变中孚；不补绝对年份，也不据十二月填丑节月。月长、闰标志与真实时区均未由这些局部资料验证。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"lunar_time_added_count","year_branch":"寅","lunar_month":12,"lunar_day":1,"hour_branch":"午","added_count":4}' --fields meihua.seed interpretation.internal_countercontrol summary --strict-fields true --response-char-limit 0
```

### 四声字占的音系与原例依据

文明书局本原PDF零起算第24页的「今日動靜如何」明确取今平1、日入4、動去3、靜去3、如平1、何平1。上8坤、下5巽，总13取初爻，升变泰。教育部字书所列《廣韻》的[動字原片](https://dict.variants.moe.edu.tw/book_piece/025/24340.png)与[靜字原片](https://dict.variants.moe.edu.tw/book_piece/025/189956.png)则归上声；[小學堂资料库说明](https://xiaoxue.iis.sinica.edu.tw/zhongguyin/Content/Files/zhongguyin-Get_Started.pdf)也分别收录不同历史声韵系统。因此不能把“古四声”当成不分时代、音系的一套唯一读法，更不能因另部韵书不同便改写梅花原例或认定原例错字。这里尚未鉴定原例实际方音与时代。

`tone_reference`可记录已确认的`system_name`、`source`及`reading_scope`（`lexical_category`、`reported_pronunciation`或`worked_example`）；编码只能是`ping_shang_qu_ru`。未提供依据时保持未知，提供声明也只记为调用方声明，`reference_independently_verified=false`。程序不按字形、拼音或一个反切自动指派声调，不联网验证声明，不套用连读变调。`meihua.seed.text_tone_basis`与两处证据范围保留逐字类别、事实路径、来源状态和与所选原例的比较，摘要明确按所报类别计算。

只在文字对应所选「今日動靜如何」六字短语时，比较所报数组是否为`[1,4,3,3,1,1]`；动／動、静／靜只用于辨认这句原例，不改原输入。类别相同不证明已鉴定同一历史音系；类别不同则明确本次不是该原例取音的复现。其他文字或没有提供文字时不冒用原例认证。所有四声起卦均保留`conditional_on_reported_tone_categories`，表示算术依赖所报类别，不能据此宣称音韵来源已核定。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"text_tones","text":"今日動靜如何","tones":[1,4,3,3,1,1],"tone_reference":{"system_name":"所选梅花原例取音","source":"NLC1925原PDF索引24","reading_scope":"worked_example"}}' --fields meihua.seed.text_tone_basis meihua.evidence_scope.text_tone_basis interpretation.evidence_scope.text_tone_basis interpretation.status summary --strict-fields true --response-char-limit 0
```

将上例仅動、靜的数值改为2，算术即为上7艮、下4震、总11取五爻，颐变益，原体震、用艮为体克用；原例则是体坤、用巽为用克体。这是说明取音差异会改变卦象与解释的数值对照，**不是整句《廣韻》取音校勘**，也不自动生成另一卦供择优。实现前固定的原页、两份韵书字片和三个手推对照（本地数据：`../tests/fixtures/meihua_tone_basis_v1/manifest.json`）均保留；助手目读及手算不作独立专家、全音系或现实预测认证。

### 字数法的影印异文与取爻边界

固定转录2690596写“至于百字”；所选文明书局本原PDF零起算第17页、德聚堂影印原第7页（所选PDF第1页）都可见“百餘字”。修改前保存的字句与影像（本地数据：`../tests/fixtures/meihua_text_count_v1/collation.json`）分别保留文字、原页及原始PDF哈希。文明书局所选“二卦總取爻”位置未见固定转录的“數”字，德聚堂所选为“二卦總數取爻”；不凭熟悉转录补字。这是助手对选段的目读，未作独立专家、作者归属或全书鉴定。

`text_basis` 默认 `fixed_transcription_2690596`，仍只接受11至100。显式选 `nlc1925_selected_span` 可按“百余字”作超过100的算术扩展，但原文没有给出可据以编码的精确上界；**1,000,000只是软件保护上限，不是声称原书支持百万字**。所有超过100的输入均保留 `range_status=software_extension_exact_textual_extent_unadjudicated`，不能拿数值可计算冒充该数量范围已获原文唯一裁定。`meihua.seed.text_count_basis`、两处证据范围和摘要均保留这一条件；范围未定不能因两种取爻结果相同而消失。

“合二卦总数”在所选短句中没有唯一消除原分组字数与八除后卦序数的区别。`line_sum_basis=raw_counts` 保留原字数总和，默认数值不变；`trigram_numbers` 是另一个明示的计数解释，合上下卦序数取爻。两种均不暗加时，不能说已校定为同样权威的古法。它们产生不同动爻时，`counting_variants` 保留两套本互变、体用、季令和所选题篇条件；解释须使用本候选的事实路径，不按已知结果挑选口径。

例如17字分8／9：本卦均为泰。按原字数17取五爻，变需，原体乾、用坤，为用生体；按卦序8＋1取三爻，变临，原体坤、用乾，为体生用。32字的两种动爻还会因纯坤取变卦之互而得到不同互卦。上述是算术边界探针，不是原书占验或现实预测样本；默认11至100的90个原字数计算另逐项保留。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"text_count","character_count":17,"line_sum_basis":"trigram_numbers"}' --fields meihua.seed meihua.counting_variants interpretation.casting_readings summary --strict-fields true --response-char-limit 0
```

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"text_count","character_count":101,"text_basis":"nlc1925_selected_span"}' --fields meihua.seed meihua.evidence_scope interpretation.status summary --strict-fields true --response-char-limit 0
```

本次没有改变传统四声、笔画、长度或农历时间的取数法，也未修改天气原实测或未来账本。单组声音取爻、完整原典优先级与现实预测能力仍未完成。

### 端法总数与占者活动的名义比例

`observed_trigrams` 或 `observed_categories` 且明确提供占者 `observer_activity` 时，`motion` 字段卡的 `interpretation.motion_context.postheaven_count_reference` 另列端法名义数。原上下卦先天序数加原时支数一次，取除六前总数，按行取半、坐加倍、立取原数计算精确分数。未知活动不默认站立，物象主体的行动不代替占者；数起卦、时间起卦及起法未知的现成卦不借用该式。

以下是虚构工程算术资料，非个人预测。总数10、动爻4，所报占者行，名义数应为5；不能取动爻4的一半。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"observed_trigrams","upper_trigram":"乾","lower_trigram":"巽","hour_branch":"卯"}' --observer-activity walking --fields interpretation.motion_context --strict-fields true --include-snapshot-text false --response-char-limit 0
```

半数为3/2、17/2等时保留精确比例，不取整，也不自动转换成一天半或八天半。影印“二花皆朝夕”与转录“二日花皆朝夕”、“待/特”等差异保留；不能据转录多出的日字生成两日期限。原文变通未被自动裁定，时间单位、起算点、日期及现实观测窗口仍为 `null`。既有天气研究次日窗口、失败和365日前瞻试验不变。来源、独立参照和失败修复见端法应期数记录。

### 年月日时的明列支标签

求名、求财的 `topic` / `topic_audit` 父字段另含 `topic_reading.qi_branch_timing_reference`，各取数候选在自身 `topic_clause` 下分列。年时用原seed；节月与名义农历月序标签分开，23时日界备选不改原年支，未知不补、分歧不挑相符者。坤四土支只另属月，未申见于四单位；数字、五行、季节及完整应期未裁定。详见四单位与历法口径。

### 当前可选资料合同

两入口只使用当前 `MeihuaInterpretationOptions` 校验已报资料。外应、事项类别、占者活动、闻见、同次方应与求名情境各自保留类型和题篇限制；省略或null表示未采集，不推定已确认不存在。现场、角色和未来结果不能由问句补猜。

## 历法、时区与资料精度

### 必须区分的历法约定

原文未唯一说明现代时区、夏令时、23点换日和闰月边界。本规则集明确选择：

- 梅花年支取农历年、春节换年。返回的八字年柱仍按立春，两者可以不同。
- 按所选时区的民用日期查农历，午夜换日；23点进入子时，但不提前改农历日期。按钟时取支，不作真太阳时修正。
- 闰月保留闰月标记，取本月名义数，不加一，不改变后续月序。
- 季令用节气月支，辰戌丑未优先按四季土月，其余按春夏秋冬。这是明示的实现约定，不能称为原文唯一规定。
- 夏令时重复钟时在未给偏移时返回输入错误；可保留地区时区并给`analysis_utc_offset`消歧。不存在的钟时、整日跳过或不符该地区规则的偏移仍拒绝，不能靠换偏移补成有效。超出1900-01-01至2100-12-31的日期返回输入错误。1900年一月前30日使用共享历法中注明紫金山天文台来源的历史民用日期补段，另与臺北历表逐日核对；1900–1911年的编表口径保留清代时宪书日期，不能扩张为各时区所有瞬间的天文月相精度。2100年扩展段使用[官方年表补充数据](#来源与规则范围)，并非向2101年外推。

这些约定保留在 `meihua.calendar_policy` 及 `seasonal_strength.basis`。跨时区输入采用各自当地民用日期与时辰，不保证同一瞬间在不同当地时区起相同卦。独立历表对照验证所列时区正午的民用日期标签；历史 `Asia/Shanghai` 偏移并非始终UTC+8，不能把验证范围描述为所有瞬间的统一UTC+8换算。

### 民用钟时、地区时区与明确偏移

已确认分钟、秒数时，分别可选传入严格整数 `analysis_minute=0..59`、`analysis_second=0..59`。两者未知时省略或传 `null`，数值计算分别补00；这只是参考时刻，不代表事件确实发生在整点或整分。明确传0与省略可定位同一参考时刻，但保留不同的已提供分量和请求哈希。分、秒只定位钟时，不另加到年月日時起卦的取数。`60`、布尔、字符串和小数均拒绝；本接口不表达闰秒标签。

读取 `meihua.calendar_policy.civil_clock_resolution.input_components` 核对已提供分量、缺失项与计算补位。来源只证明本次校验请求的字段记录，不认证现场时钟精度。未知分量不自动解释成截断、四舍五入、某个误差范围或整段历法稳定；`uncertainty_interval=null`、`calendar_stability=not_assessed`。摘要明确提示季令解释仅对应该参考时刻，不能扩成整个未知时段的结论。REST、CLI与MCP保留同一规则，含旧请求默认分钟0的本地兼容情形。详见钟时输入来源审查。完整结果会从本次请求重核UTC、偏移、fold及历法比较时刻，字段筛选之前拒绝互相矛盾的记录；有效时间表示保持，详见时刻绑定审查。

返回时间记录的ISO解析保留小数秒偏移。`+00:00:00.000001`含非零偏移，不能按`Z`或零偏移UTC接受；`+00:00:00.000000`等合法等价表示仍可核对。这不扩展上述请求分、秒或明确偏移的输入格式，也不认证微秒级天文精度。原8个失败样本及扩展故障、合法对照、原来源门槛见偏移保真审查。

返回时间记录由专用解析器按固定的软件约定解码，避免 Python 版本不同而改变周日期、基本日期或小数偏移的含义；空小数、越界分秒和无法精确表示的非零微秒以下位会拒绝，额外尾零仍可接受。它不扩展请求字段，也不把软件时间精度当作天文测量精度。冻结样本、Python 官方来源和各版本的实际验证范围见时间文本兼容审查。

例如固定参照中的2000年小寒位于香港钟时09:00:40附近，09:00:38与09:00:43的农历日期、时支及起卦数相同，节气月支分别为子、丑。秒级输入让接口能够表达两侧时刻，不改变太阳求根算法，也不认证用户钟表、历史UTC或预测精度。现有7项香港天文台节气日期分歧仍保留。紫金山天文台的[国家标准解读](https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504886119982.pdf)提出用于日期判断的朔与节气计算须达到1秒要求；本次接口修复不等于已通过整套农历编算标准。

```bash
uv run --locked --extra dev fatebridge meihua_analysis --analysis-year 2000 --analysis-month 1 --analysis-day 6 --analysis-hour 9 --analysis-minute 0 --analysis-second 43 --analysis-timezone=+08:00 --fields analysis_context meihua.seed meihua.calendar_policy.civil_clock_resolution calendar_context.bazi_month_boundary --strict-fields true --response-char-limit 0
```

秒数实现前锁定的48次节气两侧参照（本地数据：`../tests/fixtures/meihua_input_seconds_v1/manifest.json`）覆盖2000、2025年全部节与中气，没有删去跨分钟的6次；42次两侧落在同一分钟。TT参照由独立实现读取DE440生成，再用[USNO公布的TAI−UTC表](https://maia.usno.navy.mil/ser7/tai-utc.dat)转换两年的现代UTC，两者仍共享DE440动力学，不能当作独立天文观测或现实占验。秒数审查保留变更范围与验收状态。

`meihua_analysis`可同时接收`analysis_timezone`及`analysis_utc_offset`。偏移格式为`±HH:MM`或`±HH:MM:SS`，须与给定地区在该钟时的规则相符；偏移只选择实际时刻，不替换命名时区。没有给偏移时，重复钟时仍拒绝；跳过的钟时或整日始终不能用偏移救回。公历日期和时支继续取原地区的民用钟时，四柱交节比较则使用已确认的同一个UTC时刻。

[NIST的2026年规则](https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst)列明美国11月1日回拨：纽约`01:30`配`-04:00`为`05:30 UTC`，配`-05:00`为`06:30 UTC`。两者的地区、钟表日期和时支相同，不能为了体现差异而强求不同卦；两次交节比较的实际经过时长须相差3600秒。Lord Howe的半小时回拨按1800秒处理，不能一律写成一小时。

```bash
uv run --locked --extra dev fatebridge meihua_analysis --analysis-year 2026 --analysis-month 11 --analysis-day 1 --analysis-hour 1 --analysis-minute 30 --analysis-timezone America/New_York --analysis-utc-offset=-05:00 --fields analysis_context meihua.seed meihua.calendar_policy.civil_clock_resolution calendar_context.bazi_month_boundary --strict-fields true --response-char-limit 0
```

`analysis_context.civil_utc_offset/civil_instant_utc`和`meihua.calendar_policy.civil_clock_resolution`保留已核对偏移、实际UTC、fold及实际时区数据库版本／TZif哈希，`rule_trace`保留消歧步骤。`fold=0/1`只用于区分重复钟时的先后，不是两个独立占验；普通UTC钟时规范为0。共享解析器此前让第二个等价候选把UTC标成1，现按[PEP495的含义](https://peps.python.org/pep-0495/)保留首个规范候选。该修复不改变UTC实际时刻或偏移。

[IANA2026e原始规则](https://data.iana.org/time-zones/releases/tzdata2026e.tar.gz)所列上海1900年采用`+08:05:43`，与现代`+08:00`分开核对；其1900年末重复钟时的两次`23:55`相差343秒。此处验证的是所选数据库的整秒记录，不是历史现场钟表已经核实。原文件还保留`8:05:43.2`和改用标准时日期的资料不确定性，不据程序通过作秒级历史或天文精度认证。未来规则也是固定版本的延用，不保证未来立法不变。

实现前冻结的8项手推UTC、10项负例和原始规则（本地数据：`../tests/fixtures/meihua_civil_clock_v1/manifest.json`）与实现后、首次探测前另锁定的历史回拨补充（本地数据：`../tests/fixtures/meihua_civil_clock_v1/historical-fold-supplement-lock.json`）分别记录。后者没有冒充原先预置探针。原始行号定位有两项一行偏差，更正单（本地数据：`../tests/fixtures/meihua_civil_clock_v1/source-line-locator-amendment.json`）保留原记录和正确定位，未改来源字节、8项UTC预期或10项拒绝预期。软件钟时消歧不是《梅花易數》已唯一规定IANA、夏令时或闰月，也不是现实预测认证。

太阳模型的13处浮点求和使用显式`math.fsum`，避免受支持Python版本之间的内建`sum`差异传播到原始TT求根记录。原系数、时间字段、求根阈值和参照不变；实际版本、独立有理数检查及完整4,824项范围见数值求和审查。这项修复不认证物理精度或现实预测。

### 公布历表与未来天文日期的不确定性

香港天文台[对照表註二](https://www.hko.gov.hk/tc/gts/time/conversion.htm)明确指出，远期月相或节气接近午夜时，相关日期可能相差一日；列出的三个朔日为2057-09-28、2089-09-04、2097-08-07。当前计算继续采用已公布的农历标签，不能把逐日对表一致解释成未来天文日期保证无误。

时间入口另返回 `meihua.calendar_policy.label_precision`，其组件为 `meihua_calendar_precision_v1@1.0.0`，与原有取数公式版本分别记录。`matched_events` 命中时，一般与天时摘要均保留复核提示；既不拒绝这些输入，也不猜一日偏差的方向、概率或另一套农历和卦象。月日若因后续历表修订而改变，相关输入须重新起算。

| 官方点名的朔日 | 固定年表的下一月初一 | 软件复核范围，右端不含 |
| --- | --- | --- |
| 2057-09-28 | 2057-10-28 | 2057-09-27 至 2057-10-28 |
| 2089-09-04 | 2089-10-04 | 2089-09-03 至 2089-10-04 |
| 2097-08-07 | 2097-09-06 | 2097-08-06 至 2097-09-06 |

这些范围由软件按“点名朔日的前一日，加已公布的该农历月”设定，以其他公布月首不变为复核范围假设；并非天文台公布的置信区间或唯一受影响日期边界。未命中不等于精确度认证；1900年输入位于该HKO年度表范围外，仍按其实际历史补表来源计算。本组件没有裁定同一说明中的节气案例，也不把节气日期误当作农历月首。

官方说明、三份年表和修改前固定的手算及范围用例（本地数据：`../tests/fixtures/meihua_calendar_precision_v4/manifest.json`）与精度披露审计可复核。所选手算属于计算测试，不是现实观测或独立人类专家验收。

### 节气时刻与官方日标签

时间入口的 `meihua.calendar_policy.solar_term_date_reference` 对照四条实际返回记录：当前／下一节气，以及 `calendar_context.bazi_month_boundary` 的起、终锚点。比较统一使用固定UTC+08日期，保留原始带偏移时刻、模型、民用时约定、官方日期、原始来源指纹和事实路径。纽约等地的本地日期与参考日期不同，并不自动构成历表差异。交节月令沿用本软件已声明的季令约定，取数另沿用已声明的农历及时支约定。

参考数据是香港天文台1901—2100年固定年表的4800条日标签，数据版本与载入内容指纹随结果返回。它不提供可替代的精确交节时刻，`date_difference_days` 也不是时刻误差或物理置信区间。四条记录中重复出现的同一事件只计一次差异；四条路径的覆盖状态与不同事件数分别列出。

`publisher_named_near_midnight` 记录官方固定说明点名的2021年冬至、2051年春分、2083年立春、2084年春分；这是对说明内容的保留，不把已过去的年份称为未来，也不认定每次日标签相同便已解决精度问题。实际差异或点名事件会进入摘要，起卦数、交节时刻、月支及季令仍沿用本次计算。该层与三个朔日的 `label_precision` 分开，不拿节气日标签替换农历月首。

同年同名事件若返回不同交节时刻，状态为 `inconsistent_returned_instants`，保留各条事实路径，摘要说明本次时间依据存在冲突。缺少带偏移时刻时不猜时区；1900年或2101年事件没有本层年表，不否定该输入的其他有效计算。日标签相同、来源对照或软件测试通过均未建立现实预测效力。

仓库根目录可运行下面的合成输入，读取已离开相邻节气对、但仍作为月令起点的大雪记录：

```bash
uv run --locked --extra dev fatebridge meihua_analysis \
  --subject-file docs/examples/meihua-solar-date-reference.json \
  --fields meihua.calendar_policy.solar_term_date_reference summary \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

固定原始年表及所选时刻用例见参考指纹（本地数据：`../tests/fixtures/meihua_solar_reference_v1/manifest.json`）。`uv run --locked --extra dev python -m pytest -q tests/meihua/test_meihua_solar_reference.py`逐项核对来源转录及所给时刻的日期对照；合成正午不是天文事件观测，不合并成4800份现实预测证据。

## 体用、动静与条件推理

### 解释怎样对应实际计算

`stage_relations` 逐条给出原体、对照卦、五行关系、原文规则ID及事实路径。`interpretation.traditional_stage_readings` 据这些实际关系生成，支持生助与制约并存；不把本卦卦名的现代积极描述强行推广到结论。

`classical_text_reference` 按本卦卦码和实际动爻引用《周易》转录经文，并保留其独立来源。卷二「占卜總決」与「先天後天論」对爻辞使用侧重不同，本工具保留经文参照，不以一条爻辞自动断现实成败。

原始爻辞仍保存在 `moving_yaoci.text`／`classical_yaoci.text`；展示与异文溯源另列 `moving_yaoci_rendering`／`classical_yaoci_rendering`。按固定修订的[维基文库“另”模板](https://zh.wikisource.org/w/index.php?title=Template:%E5%8F%A6&oldid=5438530)，`{{另|德車|得輿}}` 展示为“德車〔一作「得輿」〕”，保留两个完整读法及转录顺序，不择定某字为校勘正解。`variants` 保留原标记、两读和原文／展示偏移，偏移为从零起、末端不含的Unicode码点。未知或未完整解析的标记使 `display_text=null`、`status=unresolved_markup`，原文保留待核。全部384条经文中的44条、48个异文标记已有字面展示核对，这不等于全书影印校勘或解释模型验收；详见审查记录。

`moving_line_phase`、`position_hint`、卦义库的建议及 `action_hint/risk_hint` 是现代联想或建议。六条 `line_oracles` 中只有 `is_active=true` 是本次动爻；其余是其他爻单独变化的假设参考。动五爻不能证明事情已到现实结果阶段，动爻序号也不是发生日期。

`moving_line_phase.stage` 保留六种现代爻位联想名称，`real_stage_inferred=false`；“五爻主位”不表示现实已到结果阶段。各条实际／假设爻的 `position_hint` 用于提出需要现实资料核实的问题，不把爻位写成已经发生的阶段。

`line_oracles` 及 `moving_line_oracle` 的 `timing` 沿用“先小后大”等现代行动次序短语，`timing_scope=modern_action_order_hint_not_event_time`，不能读成应期。`transition_scope=computed_hexagram_change_not_real_outcome_forecast` 表示只确认哪一爻改变后得到哪一变卦；变卦的现代卦义不证明现实将如此发展。体用的生助、耗泄、制约是所列五行关系，其现实资源、权限、投入和阻力另须核实。原典条件断语与实际动爻经文仍原样保留。

首轮字段及 `reading/audit` 字段卡见[生成调用合同](contracts/meihua_analysis.json)。字段卡是 `fields` 的参考，不新增 `view` 参数；详细解释沿用同次结果。

真实模型解释另按[梅花语义验收](#来源与规则范围)准备和执行。10个虚构单轮案例不等于已验收；只读MCP参照与模型实际收到的回执分开记录，未运行、未审阅和失败均保留。

### 内卦之间的制约

人事分支在 `interpretation.internal_countercontrol` 给出文明书局本《體用》所选两条：生体之卦再受其他卦克，生助受限；克体之卦又受其他卦克，只取“稍解其凶”。原体、初用、体互、用互、变用为五个分析角色，静体只列一次；角色重复出现不代表独立观测。`nodes` 与 `control_edges` 的事实路径连回这次卦图，`qualifications` 保留原有生克，不把受制后的生助改写成克体，也不抹去被制约的克体。

井变升中离火制兑金；丰变震中初用离火也制体互兑金，但离火同时泄木体。原书保留“亦不纯美”，当前解释也同时呈现制金与耗泄，不据一个制约关系输出唯一好坏。季令弱或未知不自动删除五行制约；制约者自身再受克仅列为事实，尚未裁定多层先后、强弱与外应的综合结果。天时分支仍不分体用，该字段为 `null`。

每个取数候选保留自己的这层证据及事实路径。一般、题篇摘要均说明相关直接制约；完整图与原文可用 `internal_control` 字段卡核对。两条所选字句和三则原书算例仅作有限计算、文本符合性检查，助手目读不作独立专家鉴定，书中的应验故事不计入现实预测样本。修改前固定材料及保留原始手推错误的勘误见参考清单（本地数据：`../tests/fixtures/meihua_internal_v1/manifest.json`），审计见当前记录。

### 内卦的紧次与生体迟速条件

`interpretation.stage_emphasis`按文明书局卷三所选句呈现“用最紧、互次之、变又次之”，互层另列“体互最紧、用互次之”。`ordered_layers`是原文的分析紧次，不是权重、胜出规则或忽略用互的许可。生体与克体角色仍来自同次卦图，静体不换。

当前`meihua_stage_emphasis_nlc1925_v1@1.1.0`接收可选`matter_scenario`：`favorable_matter`表示调用方已确认属于原文“问吉事”的事项，`unfavorable_matter`表示已确认属于原文“问不吉之事”的事项。它是所问事项类别的声明，不是希望得到的答案、文字情绪、系统断出的吉凶或已发生结果。未知时不提供；题篇、问题关键词和有无生体均不替代确认。天时占携带此参数拒绝，因为该分支不分体用。

未提供时，`matter_scenario=not_collected`、`scenario_declaration=null`，`scenario_condition_met`保持`null`；若所选条款要求的卦内结构已确定不满足，`full_clause_applies=false`，结构满足但情境未知时才保持`null`。这一“不适用”只排除该句，不认定事项类别或现实结局。此条件求值修正及旧结果保留范围见专项记录。明确提供后，`scenario_declaration`保留原值、调用方声明未独立核实的状态及输入路径；主卦与各候选共用同一声明，各自核对自己的关系。`scenario_condition_met`判断声明是否匹配原文前提；`full_clause_applies`只核对所选句的前提，不能用作综合吉凶或实际成败。两种入口的路径分别为`input_normalized.matter_scenario`和`analysis_context.matter_scenario`。

《占卦訣》的迟速句以“问吉事”为前提。`relative_generation_clauses`分别保留生体落在用、互、变时的“即成就”“漸漸成”“稍稍遲耳”。情境匹配且用／变生体时，可标所选句条件适用；所报为“问不吉之事”则这些吉事情境句不适用。互层两侧分别列出，迟速句的“互”是否只取某侧尚未裁定：即使已报吉事情境且互层有生体，整句仍为`null`，`unresolved_conditions`保留`mutual_phrase_scope`。多个位置同时有生体时全部保留，不取最早、最迟或最高分。

生体与克体并见时，`mixed_generation_control`还核对吉事情境下的“事有阻節好中不足”，不能只读生体迟速句。`scenario_clauses`新增三条：吉事情境无生体且有克体的“事不諧”；不吉事情境有生体的“有救無害”；不吉事情境无生体的“事必不吉”。它们是传统条件断语，不能转成现实无害保证、灾祸断言或成功概率。已有季令与生助受制等资格随角色保留，条款可同时成立，尚未裁定净作用。原文“無尅體之卦則吉事必可成就矣”的前段条件承接未裁定，没有加成无克体即成功的规则。这里的有生体／无生体只核对四个实际内卦角色，已报外应另列；内卦无生体与外应有生助可以同时出现，当前没有内外综合净结果。

每个取数候选使用自己的原体、四段关系、季令和制约。相同初始比和的两种口径，变用可分别生体、克体；已报同一不吉事情境时，分别匹配有生体、无生体的不同原句，不得复制主候选断语。天时此层仍为`null`。

可用`stage_emphasis`字段卡读取声明、所选层及显式入口的计数候选，或用`stage_emphasis_audit`连同原始卦图、季令和制约核对。原有迟速句不计算持续天数、日期、实际成败或权重；另列的条件化阻节计日见下一节。综合优先级尚未实现，不把所选9句当整章完成。初版6句、18个阅读单元和13图的原固定清单（本地数据：`../tests/fixtures/meihua_stage_emphasis_v1/manifest.json`）及复用勘误（本地数据：`../tests/fixtures/meihua_stage_emphasis_v1/reuse-errata.json`）保留；1.1.0另有情境与39组规则上下文（本地数据：`../tests/fixtures/meihua_matter_scenario_v1/manifest.json`），它们是13张已勘误旧图乘三个声明状态，不是39张新图或现实观测。影印与转录字句分别保存，助手目读未经过独立人类专家鉴定。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"011010","moving_line":5}' --matter-scenario favorable_matter --fields input_normalized interpretation.stage_emphasis --strict-fields true --response-char-limit 0
```

### 生克并见时的阻节计日

`interpretation.stage_emphasis.obstruction_timing`补入文明书局本卷三《占卦诀》的计日句（原PDF索引107，纸面卷三六），与卷一《周易卦数》（索引12，纸面卷一一）对读。乾克体阻一日、兑克体阻二日是两条明例；离3、震4、巽5、坎6、艮7、坤8按“之类推之”及卦数推得，分别标`explicit_source_example`与`derived_by_source_analogy`，不把六条类推写成六条原句明例。

必须已有调用方明示的`matter_scenario=favorable_matter`，且本候选实际内卦同时有生体、克体角色，才激活`activated_day_candidates`。未报情境不从问句、主题或愿望补足。天气不使用人事体用计日。每种取爻口径分别读取自己的静体、四辅助角色、关系和制约路径；同一卦出现在多个角色时保留全部角色并按卦名分组，不累计成多份延迟，不在不同卦数间取和、最大、最小或平均。

`nominal_source_day_count`是该卦在此句中的条件化原文日数。`selected_clause_applies`仅核所选内卦关系和已报情境：生体与克体未同时出现时为false，即使情境未采集；结构满足但情境未采集时保持null，不说明制约已解除或现实会延误相应天数；原有旺衰、日气、直接制约均保留，未合成净效力。原文未在这句给出起算点、首尾日计数或与坐行立倍半的优先级，因此`net_effective_delay/calendar_anchor/inclusive_counting_convention/event_time`均为null；不按当前日期加日数生成完成日期。完整克应、内外应及年月日合参仍未完成。

`obstruction_days`字段卡连同计算事实读取此层；来源、失败记录与验证范围另列。下例是虚构声音计数工程例，两种口径分别保留；旧现实研究结果不因新增原典规则而改写：

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"sound_groups","first_count":12,"second_count":5,"hour_branch":"酉"}' --matter-scenario favorable_matter --fields meihua.body_trigram interpretation.stage_emphasis interpretation.casting_readings --strict-fields true --response-char-limit 0
```

### 旺衰标签与生克合读

`interpretation.seasonal_qualification` 使用当前实际 `meihua.seasonal_strength`，按文明书局本卷二《衰旺論》所选六条呈现三个联合条件与三类偏好。`condition_checks` 分别核对体旺逢生、体衰逢克、体衰有生；`preferences` 分列体宜旺、生体之卦宜旺、克体之卦宜衰。这些偏好各自记录，不能把体与生体之卦同时为旺设为必要门槛，也不累加成吉凶分。

已知旺或衰时核对对应条件；“原文未定”及缺少已确认节月保持 `pending_strength/unknown_strength`，不能当中性、偏弱或反面结论。条件中的四个外于原体的角色沿用实际初用、体互、用互、变用；重复角色不是独立应验次数。井变升在申节月可同时触发体衰受克与有生：摘要保留受克之忧加重与“衰稍解”。生体之卦受制、克体之卦又被制也在 `countercontrol_qualifications` 保留，尚未裁定这些条件的净作用。

每个取数候选使用自己的原体、生克和同一已报节月。`roles.strength_fact_path` 对主卦指向 `meihua.seasonal_strength`，对候选指向其自己的 `interpretation.casting_readings` 内季令记录；卦图关系仍连回对应 `meihua.counting_variants`，不借用主候选的强弱。`strength` 字段卡给主卦，`strength_audit` 另含候选与直接制约。天时分支继续不分体用，此字段为 `null`。

该范围依据原PDF零起算89页的选段，沿用已声明的节月季令约定，不据此声称原书已经唯一裁定现代节月、月日合参或全书优先级。“重遇克”的“重”没有确定计数阈值，保留为 `not_adjudicated`，不私设两次或合计票数。卷三另有“乘旺……虽有他卦克之，亦无大害”的措辞，比较记录保留，未拿来自动抵消卷二条件。所选目读及四个手推卦图的13个节月上下文检查见固定材料（本地数据：`../tests/fixtures/meihua_seasonal_reading_v1/manifest.json`）与审计记录；不是完整原典、实际模型或现实预测认证。

#### 卷三乘旺限定与克体例外

`seasonal_qualification.volume3_qualification`按文明书局本《體用衰旺之訣》（原PDF索引109—110）另核所选节月下的四项条文。体旺而受克的“亦無大害”、体衰及体旺有生分别列条件；用、体互、用互、变用逐个核对“乘旺皆吉，但不要尅體之卦氣旺”。克体且旺时为`excluded_by_attacker_exception`，不引用乘旺皆吉；其余角色须实际标旺才匹配，“原文未定”与缺节月保持`pending_strength`。`favorable_clause_applies`与`attacker_wang_exception_applies`分别核对吉句和旺克例外：克体已知时吉句为false，即使旺衰未定；例外本身在旺衰未定时仍为null。`pending_strength`只说明强弱未定，不补成吉句仍可能适用。

`matched_selected_month_conditions`只表示所选月令标签及原始内卦关系满足该句条件；已有生助受制、克体被制、耗泄等资格仍保留，未求净作用或章节优先级。每个计数候选使用自己的原体、关系、旺衰和路径。原卷二文字保留为`volume2_summary`；`summary`带卷二、卷三来源标签并列两段所选条件，主结果和各候选摘要同步使用。默认字段清单和`reading`卡均包含完整`interpretation.seasonal_qualification`。摘要接入、天气投影修正及未完成验收见交付审计。这些是所选条件并列，不是完整旺衰判断或章节优先级裁定。天时分支不增加此人事体用层。

内外有生、内外并无生及体党多等句保留为`not_adjudicated`，只列已知内卦生体角色；`external_support_or_absence=null`表示该月令内卦层未裁定外应，不表示调用方没有提供外应。原书的“並無”与固定转录“並也”差别保留；未决字句和党多阈值不补成唯一算法。未计算概率、实际安全或成败、诉讼或临床结局及应期。预期与范围见事前固定材料（本地数据：`../tests/fixtures/meihua_strength_exceptions_v1/manifest.json`）。验证、已保留失败与未完成范围

两段声数超过八时，另一取爻口径甚至会改变体用：11声、1声、子时按原声数为初爻动、离为体而体克用；按余数卦序为五爻动、乾为体而用克体。此时 `counting_variants` 保留两套变卦与体用，解释标为 `conditional_on_declared_convention`，不把默认口径当唯一原典答案，也不按所求吉凶事后选口径。

物数占的原文是“以時數配作下卦”“卦數並時數總除六”。例如1件物品、酉时，酉数10取下卦为兑2，动爻仍为 `(1+10)%6=5`，不是 `(1+2)%6=3`，也不再加一次10。数量9、酉时的上卦为乾1；按默认原数量取爻为1，按 `line_sum_basis=trigram_numbers` 的上卦卦序加原时数取爻为5。两个口径的体卦分别为乾与兑，必须随各自动爻解释。参数名称沿用显式入口，但物数占只约简上卦取数，原时数始终保留。

当前 `counting_variants` 对物数与两段声音的分歧都给各自的本、变、互卦、原体和四段 `stage_relations`，事实路径指向对应候选，不能从选中卦借用体互、用互或变用关系。纯乾、纯坤的候选也分别从各自变卦取互；另一动爻可能连互卦一起改变。候选卦内的现代卦义仍标 `modern_editorial_summary`。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"sound_groups","first_count":1,"second_count":5,"hour_branch":"酉"}' --fields meihua.seed meihua.base_hexagram.name meihua.changed_hexagram.name --strict-fields true
```

显式资料审计包含九则原文演算与四项独立规则探针。`少年有喜色`的原体离火遇体互坎水受克，而用互震木与变用巽木生体；原文“互变俱生之”的“互”可能只指用互，解释范围未裁定。`牛哀鸣`也不能把比和的体互坤土说成克体。`西林寺`体用互变皆比和，但卷二另按象理作不同判断，说明不能将多段生克投票或加总为通用成败分数。这些分歧保留在审计材料中，不反向修改五行关系求全绿。

选段影像与物数审计另保存德聚堂刊本影印和文明书局扫描本的七处人工核对，涵盖乾坤取互、物数、单组声音下卦句、西林七画、少年与牛例的互字范围、借斧例的频数。来源分别为[故宫珍本丛刊415影像](https://commons.wikimedia.org/w/index.php?title=File:GGZBCK415_梅花易數_増補詳注六爻一撮金易數_官板大六壬神課金口訣_邵子易數_大六壬課經集.pdf&oldid=1155031066)及[国图藏本的Commons影像](https://commons.wikimedia.org/w/index.php?title=File:NLC416-12jh005426-44577_梅花易數.pdf&oldid=808894944)。题署年代与馆藏归属采用托管页书目记录，尚未独立鉴定；原页、零起算PDF页码、位置及哈希均可复核。

两本都印“西字七画”，因此这不是只见于当前转录的一处七字；规范字形如何计成七画、是否承袭讹误仍未证明。两本也都保留少年与牛例的争议句，故不能改掉计算关系来求一致。单组声音下卦句仍有“加时”措辞，不能未经裁定当作“以时数”的物数占。新增五项物数探针均为事先手算的规则测试，不计作原书演算或真实观测。物数能力以具名1.1.0配置及当前所列原文范围为准，不扩张为全书裁定。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"object_count","count":1,"hour_branch":"酉"}' --fields meihua.seed meihua.rule_trace --strict-fields true
```

1.2.0补足一般分支的候选解释：`interpretation.casting_readings`为每个保留口径分别返回固定原体下的生克、同一已报节月的旺衰和本候选实际动爻爻辞。依据路径指向自身的`meihua.counting_variants`；纯乾坤分别按自己的变卦取互。`casting_comparison`比较具体差异，不能以相同初应或体气推出相同终应，也不裁定哪种计数口径能预测现实。`reading`与`audit`字段卡均保留候选解释。天时分支的这两个一般体用字段为`null`，共享审计投影仍可读取；实际天气候选仍在`interpretation.weather`中按不分体用的规则解释。

例如两组声音为11、1、子时，原数与卦序数分别动初爻、五爻，原体从离变为乾；已报午月时，前者体旺，后者体衰，不能复用所选候选的体气。声音12、5、酉时的两种口径初应同为比和，终应却分别用生体、用克体。新候选解释审计先固定九项逐步推导参考，另核对《周易》[大有](https://zh.wikisource.org/w/index.php?title=周易/大有&oldid=10645712)、[恒](https://zh.wikisource.org/w/index.php?title=周易/恒&oldid=10646486)、[履](https://zh.wikisource.org/w/index.php?title=周易/履&oldid=10647513)、[乾](https://zh.wikisource.org/w/index.php?title=周易/乾&oldid=2404991)的所选爻辞。参考由助手制作，未经过独立人类专家验收；这些计算探针不是新的原书演算、真实模型验收或现实观测。新增字段曾造成天时共享审计卡422，失败用例与修复后全套测试记录均保留。

#### 卷五四状态原表对照

`seasonal_qualification.volume5_table_comparison`逐角色并列文明书局本卷五《五行四時旺相休囚例》（原PDF索引202—203，纸面卷五十五—十六）。所查表只列旺、相、休、囚四个状态栏目，保留20个印刷单元格；不按常见五态表补“死”，也不替换“囚”栏。各列未列出的五行保持`table_state=null/status=element_not_listed`，不能解释为衰、死或中性。JSON将印刷竖栏转置为状态行，`table_cell_relative_path`相对于该对照对象。

例如同用已报寅月时，卷五表列木旺、火相、水休、土囚，金未列；既有卷一月令标签仍按自己的所选条款显示，卷二、卷三资格条件继续以那些标签核对。此对照给出每个候选自身的原体、初用、体互、用互、变用及事实路径；缺月不填状态，天时分支保留原输出。节月与土月映射沿用既有软件约定，没有从该表推定新的历法边界。

卷五此表处于测字材料语境，尚未裁定为人事体用的唯一主导规则；本层不会覆盖原旺衰或主摘要。年月日合参、净吉凶、应期、概率和现实结果仍为空。来源冻结、对照范围、旧门槛失败及分层验收见卷五表审查。

### 八卦生体克体的专属象义

两入口的人事分支新增`interpretation.trigram_relation_symbols`，使用独立配置`meihua_trigram_relation_symbols_nlc1925_v1@1.0.0`。所选依据是文明书局本《体用总诀》原PDF索引60—62的八组生体、八组克体原句；修改前固定的影像、逐句读稿与384张卦形参考（本地数据：`../tests/fixtures/meihua_trigram_symbols_v1/reference-freeze.json`）分列，助手校读未经独立人类专家鉴定。

五行关系相同不表示具体引文相同。例如坎体遇乾金、兑金同为用生体，乾生体段列公门、功名等备选，兑生体段列主宾、朋友讲习等备选。只有本次四个实际辅助角色对固定原体为`用生体`或`用克体`时，才按该角色的实际卦名匹配相应条款；体生用、体克用、比和不倒置成生体／克体。初用、体互、用互、变用分别保存，重复卦名不是多个独立应验。

`selected.role_evaluations`保留实际路径、条款ID、原文、源页、原有直接受制资格和季令标记。`counting_candidates`每个候选使用自身原体、互变和同一已报节月；不复制主结果。`matched_raw_relation`只表示引文的表面关系条件，不把受制或季令未定删除，也不裁定递归净作用。无匹配不等于全卦没有任何生克，末句“生尅不逢止隨本卦而論之”没有据此自动触发。

所选影印与固定转录的差异保留：巽克体段“謀事乃南方之人／謀事乃東南方之人”、坎生体“水邊人進入／水邊人進利”、兑生体“市口之人／帶口之人”。所选版按目见记录，不因通常巽属东南或更通顺的读法改字；这些差异未获独立专家裁定。原文各“或”为备选列举，不自动指认现实人物、姓氏、性别、地点、来财或不利事件。身心、灾祸等旧称仅为史料原句，不生成临床、灾祸或人生断言。

此层不改旧卦形、历法、原摘要或天气解释，天时分支为null。得失概率、应期、现实结果和有效综合结论仍不计算。`trigram_symbols`字段卡可单独读取本层与受制、旺衰和候选；完整资源仍读取同run分页。范围、协议和失败记录

### 内卦、外物与占者的动静

文明书局本卷三《体用动静之诀》在原 PDF 索引110、111（纸面卷三九、十）分别讨论内卦、外物和占者。`meihua_motion_nlc1925_v1@1.0.0`只选取其中9个句组，返回在`interpretation.motion_context`，天气分支为`null`。

- `inner_roles`从同次实际卦图列原体静、体互静、用互静、初用动、变用动。这是原文的符号角色，不能当成现场物体正在移动。各计数候选用自己的原体、互卦与路径。
- 可选`observer_activity`接已确认占者当时的`seated`（坐）、`walking`（行）或`standing`（立）。未知省略，不从问句、车辆运动或外物动静推断。`observer`保留调用方声明及原始输入路径；迟、速、半迟半速是所选原文相对措辞，没有持续天数或日期。
- `external_observations`每条可选`motion=moving`或`stationary`。未填保持未知，返回资料不补`motion:null`。原书同时列井沼、山岩之静与担水、负土之动，不能按水、土或器物类别默认。`external_motion`逐条关联已报资料及本候选的外应资格；实物／形色资格仍按既有独立层保留。

外应“动而吉”“动而凶”的速应句需要外应吉凶判断。当前没有内外综合判定，`omen_valence`及`omen_condition_met`保持`null`，不会把内卦某条生克、占者活动或`matter_scenario`的“问吉事”声明当成已判吉应，也不向调用方索取所希望预测的吉凶以填足条件。明确不动时，这两条动应句的条件不符；原文“不动而应者，吉凶之未见也”仅作为所选静止句保留，不扩大成无事发生、不吉或取消已有起卦。

影印本目读为“未见”“事应于迟／速”“我立则半迟半速”，固定旧转录为“末见”“事应之迟／速”“我立而半迟半速”，分别留在配置中，旧转录未改。此处为助手目读，未经过独立人类专家校勘。心境之静与“不动不占”的完整起占条件尚未裁定；三种动静也未合成为时间或结局。`duration`、`event_time`、`combined_outcome`保持`null`，可复现这些句组不证明现实预测有效。

用`motion`字段卡可读取这层及外应资格，显式入口同时保留计数候选。未提供新事实时，只新增结构化原文角色层，不向既有摘要追加缺项提示。冻结来源及清单（本地数据：`../tests/fixtures/meihua_motion_v1/manifest.json`）包含13张已勘误旧图的内卦角色，以及同一旧图上24组声明组合；37组不是37张新图或独立现实观测。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"011010","moving_line":5}' --observer-activity seated --external-observations '[{"manifestation":"actual_water","label":"虚构担水工程示例","motion":"moving"}]' --fields input_normalized interpretation.motion_context --strict-fields true --response-char-limit 0
```

### 静室与无所闻见的声明条件

两入口可选 `observation_context`，其中 `label` 必须非空；`quiet_room`、`nothing_heard`、`nothing_seen` 分别接严格布尔值或 `null`。它们指同次起卦、同一占者的已报条件，不由问句、描述、内卦动爻或占者坐行立补足。未提供整个对象为 `not_collected`；提供后仍有未知且无明确不符项为 `pending_declared_conditions`；任一明确 `false` 为 `declared_conditions_not_met`；三项均为 `true` 才是 `declared_conditions_met`。不满足本句条件也不能反推一定存在外应。

`meihua_quiet_context_nlc1925_v1@1.0.0` 选取文明书局本卷二《静占》（原 PDF 索引92，纸面卷二三九）：所报静室且无所闻见时，按这句“不论外卦”，仍保留实际内卦、原体用和可用月令。该版本“凡應占”“靜室占”比固定转录多两字，原貌与对读分别保留。原句后半还要求全卦年月日五行衰旺合参；已有取数历法值、月令和条件可用的日气层分别保留，完整年气与合参仍未裁定，`complete_year_month_day_strength_synthesis=null`。`known_seed_calendar_values`既读取时间入口的实际历法值，也读取显式`lunar_time_added_count`的已确认嵌套年支、农历月日，并指回实际参数路径；不把这些标签当作已核定绝对日期、日支或年气。范围和原回归失败见标签来源修复。

声明不是独立现场核验，`absence_of_all_actual_omens_independently_verified=false`。物理静室不等于心境之静；这层不裁定“不动不占”、起卦资格或现实结局，不取消既有起卦，也不追溯排除旧预测样本。未采集 `external_observations` 仍不等于确认无外应，空数组仍为非法输入。

三项均真时不能同时提供同次外应记录；`sound_groups` 与“无所闻”声明冲突，观物两入口与完整静室无所闻见声明冲突。单个“无所见”标记不会替所有观物资料推定感知方式。天气分支不接这段体用静占条件，显式传入时报校验错误；默认天气的该解释层为 `null`。

用 `quiet` 字段卡读取 `interpretation.observation_context`；显式入口各计数候选另有自身原体、卦图和月令路径。字段卡只是建议的 `fields`，不是请求参数。示例为虚构工程资料：

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"100111","moving_line":1}' --observation-context '{"label":"虚构静室工程示例","quiet_room":true,"nothing_heard":true,"nothing_seen":true}' --fields input_normalized meihua interpretation.observation_context --strict-fields true --response-char-limit 0
```

静占冻结清单（本地数据：`../tests/fixtures/meihua_observation_v1/manifest.json`）记录28组声明条件、复用卦图及零新增现实观测；这些工程材料不认证预测效力。省略或显式null表示该项现场事实未提供；当前唯一选项模型校验显式事实。

### 日气与月日衰旺

`interpretation.day_qi` 补充文明书局本卷三《日应》（原 PDF 索引129，纸面卷三二八）及卷二《复明时令之应》（索引83、84，纸面卷二三〇、三一）。`meihua_day_qi_nlc1925_v1@1.0.0` 按日支取寅卯木、巳午火、申酉金、亥子水、辰戌丑未土；日气只是五行，不把土日唯一配成坤或艮，也不把金日唯一配成乾或兑。

各实际原体、初用、体互、用互和变用分别按所选月日表标记旺、衰或原文未定。生体角色的日气偏好为旺，克体角色为衰；其他关系不补偏好。日气对原体的生、比和与克、泄按所选《日应》读法分列，原体克日气未在该段明说有利，`selected_day_clause_preference=null`。卦字所指的选择及原貌随规则保存，未宣称唯一完整解释。月衰与日旺等组合可以同时出现，`month_day_comparison=different_labels_no_aggregation`，不投票、平均或抵消，`net_strength` 仍为 `null`。

时间入口自动从已确认的本地民用日期计算日干支，沿用本工具已声明的午夜换日软件约定。附带的八字日柱在23时会翻至下一日，因此不能直接充当午夜日气。23时保留 `local_midnight` 与 `zi_start` 两个候选，分别列日期、日支、日气及本候选原体的标记；所选午夜口径并非已由原书唯一裁定。日期是本次计算时刻的日标，不是预测事件日期。

显式起卦没有绝对日期，不从年支、农历日数、时支、问句或当前系统时间补日支。明确提供时可传 `day_qi_context={label,day_branch}`；`label` 非空，`day_branch` 为一个已报日支，可选 `declared_day_boundary=local_midnight`／`zi_start`。没有公历日期时，这项日界声明不能独立核实，也不据此推导其他日期。未知省略整个对象，输出该层为 `null`。天气不接所选体用日气条款，显式传入报校验错误；时间入口不接受 `day_qi_context` 覆盖实际计算。

`day_qi` 字段卡保留本层、原体、月令与归一化资料，显式入口同时保留各取数候选自身的路径；`quiet` 字段卡也可读取日气。示例为虚构工程资料：

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"100111","moving_line":1}' --day-qi-context '{"label":"虚构已报寅日工程示例","day_branch":"寅"}' --season-month-branch 申 --fields input_normalized meihua.body_trigram meihua.seasonal_strength interpretation.day_qi --strict-fields true --response-char-limit 0
```

原书所选影印的“看所占卦日屬何卦”“水旺則火衰”“生體之卦氣”与固定转录分别保留，未用转录覆盖多字。当前只补日气及月日分列，年气和完整年月日衰旺合参仍未成立，不修改旧天气研究的入组条件、分母或负结果。日气审计分别报告60个原始日历单元格、全区间日期算法对照、复用卦图及协议验证。

### 章句卦气的明列日支核对

求名、求财且已有 `day_qi` 时，`topic` / `topic_audit` 字段卡的 `interpretation.topic_reading.qi_day_timing_reference` 另列章句指定角色的日支原子。求名名成、求财得财直接句取实际生体角色；在任日期、求财破财直接句取实际克体角色，在任及无克体前提仍按原状态保留。各取数候选读自己的 `topic_clause.qi_day_timing_reference`。

本层只核时序里明列且含日的地支。坤的“辰戌丑未月”限定月，日支原子取“未申年月日時”中的未、申，不用四土月或日气五行代换；其他数字、季节、五行与日干组合未解析。不符不否定全部条文，相符不表示应验。23时午夜／子初是同一输入钟时的两种日界标签，均保留，不挑相符者生成日期。

以下为虚构工程标签核对，不是回款预测：原体乾、初用坤为用生体，已报未日符合坤时序的明列日支原子；换成辰日则该原子不符，但完整时序条件仍未裁定。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"000111","moving_line":1}' --interpretation-topic wealth --day-qi-context '{"label":"合成未日标签，非现实观察","day_branch":"未"}' --fields interpretation.topic_reading interpretation.day_qi --strict-fields true --include-snapshot-text false --response-char-limit 0
```

没有搜索最近匹配日，也没有生成实际应期、收支、名成、处分或现实窗口。来源、96条原子与原96条规则原子与事实范围见本节。

历史完整结果比较先核当前已审查的条件、引文和角色，再按窄范围还原历史表示；不重写原期望。原始失败与迁移后检查分别报告，见日气历史比较记录。

## 问事专题与现场外应

### 人事题篇与版本

两种入口均可显式选择下列题篇，使用 `topic` 字段卡。默认仍为 `general`；问句中出现“交易”“赚钱”等字样不会自动换章、改卦或更换版本。此层为 `meihua_topic_clauses_nlc1925_v1@1.0.0`，所选依据是文明书局本原PDF第67、68页（均零起算）的四章初始体用条款，与前述固定转录的时间取数规则分别标识。

| interpretation_topic | 所选章名 | 用卦在该章中的角色 |
| --- | --- | --- |
| `planning` | 求謀占第八 | 所谋之应 |
| `reputation` | 求名占第九 | 名 |
| `wealth` | 求財占第十 | 财 |
| `transaction` | 交易占第十一 | 交易之应 |

各章分别列出体克用、用克体、体生用、用生体、体用比和五条。`topic_reading` 按实际原体与原用选择一条，公开章名、原文、体用事实路径和条件象义；不从爻辞或另一候选借用关系。其余四段生克、已报节月旺衰和动爻经文另列为上下文，尚未综合为该章的最终判断。

版本差异会改变读法：所选文明书局本交易体克用作“交易成迟”，固定转录1441921作“有财”；交易用卦角色亦分别作“交易之应”与“财”。求谋的“所谋之应／所谋之事”“成亦有害／谋亦有害”等差异一并保留。修改前固定的所选字句、5个手推卦图在四个题篇下的20项匹配检查和2组取爻候选（本地数据：`../tests/fixtures/meihua_topics_v1/manifest.json`）与当前审计可核对，不能为了取得希望的结论切换引文。字形尅／克只用于规范规则键，影印所选原文保留尅。 未作同义裁定的比较标为 `comparison_reading.semantic_status=not_adjudicated`，不能由未标定差异反推两版已证同义。

`casting_readings.topic_clause` 属于各候选自己的原体用。例如11声、1声、子时，原数动初爻为离体乾用，卦序数动五爻则乾体离用；交易所选章句分别为成迟与不成。即使两个候选初始都比和，其变用关系也可能相反，因此相同初始章句不等于相同过程或结局。

“成迟”仅是原文相对措辞，未换算几天、几月；财象不等于可验证收益或投资建议。`success_probability/event_time/real_outcome_verdict` 均为 `null`。当前保留四章初始20条，求财另有下述补充句关系成分；进一步互变旺衰综合、应期方位和全章占断仍待完善；助手影印目读和软件测试不等于独立人类专家、真实模型语义或现实预测认证。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"100111","moving_line":1}' --interpretation-topic transaction --fields interpretation.topic_reading --strict-fields true --response-char-limit 0
```

#### 出行与谒见

两入口另支持 `interpretation_topic=travel`（《出行占第十二》）和 `meeting`（《謁見占第十四》），仍须显式选择。所选文明书局本原PDF索引68、69的10条初始体用句使用独立规则集 `meihua_journey_clauses_nlc1925_v1@1.0.0`，原四章20条及其版本保持原样。`topic_reading`和各候选的`topic_clause`均引用自己的原体、原用、原文及跨页定位，不按问句关键词自动进入题篇。

出行章的 `topic_reading.chapter_qualifications` 另核“体宜乘旺”和“诸卦宜生体”：已知旺、衰分别保留偏好符合与不符；无节月或“原文未定”保持未知。后句按四个辅助角色各自关系列示，受制条件另读对应的 `internal_countercontrol`，不要求四角色全部生体，也不合计为许可或吉凶分数。重复角色不是新的应验次数。

“乾震多主动”“坤艮多主不动”的阈值及计数范围未明，保留原体一次的五角色计数和本互变六位置计数作为诊断，不自行定“多”。巽舟、离陆、坎失脱等句的角色范围亦未裁定；它们是所选原文记录，不自动选择交通方式或路线。所选影像末句作“坎防失脱。主纷争之应也”，该处目读未见“兑”字；固定转录1441921另作“坎妨失脱，兑主纷争”。两者分列，不用另一转录补影印主语。没有可指认的主语时，`actual_matching_roles=null`表示未赋予角色。

出行章在用克体时的“祸”字仅作为历史用语记录，不构成现实灾祸判断；财象、可见／不见也不是实际行程、收益或会面结果。`event_time/success_probability/real_outcome_verdict`仍为`null`，出行补充层的方位、方式指令、灾祸及现实结果也不计算。原文舟／陆并非地理方位，不从这一章补指南针方向。来源、完整384卦形与13种节月上下文的核对见两章审计。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"100111","moving_line":1}' --interpretation-topic travel --season-month-branch 申 --fields interpretation.topic_reading --strict-fields true --include-snapshot-text false --response-char-limit 0
```

### 家宅、屋舍与候选题篇摘要

显式选择`interpretation_topic=household`读取文明书局本家宅章，`dwelling`读取屋舍章；问句不自动选篇。家宅影印「比利」与转录「比和」的对应未裁定，五行相同时`topic_reading.source_relation_condition=null`，不能自动套家宅安稳句；屋舍保留「資財冷退／資財衰退」两份文字。家宅生体转引只核所列四个实际内卦辅助角色，完整内外范围及跨章净结论仍为未定。两章均不构成风水现场评估、住宅安全鉴定、失盗或财务结果、选房迁居许可及日期预测。

所有显式人事题篇的`casting_readings[i].traditional_judgement`使用该候选自身`topic_clause`的题篇、原体、初用、引句与限定，随后保留自身受制、旺衰、求财补充及后续附层。一般阶段文本保留在`traditional_stage_readings`，不拿泛体用模板代替题篇初始含义。完整证据、原始失败及范围

### 已报外应的实物与形色资格

两种梅花入口可选传 `external_observations`，每条须含明确的 `manifestation` 类别和 `label` 描述；目前只用于一般人事与六个显式题篇。未确认类别时省略整个资料，不从问句、未查看的现场或颜色自动猜测实物。空列表、未知类别、空白描述及天气分支携带这层体用资料会返回校验错误。最多12条只是软件保护，不是原典数量限制。

依据文明书局影印卷三《體用生尅之訣》，原PDF零起算108、109页，传统五行归属还要区分所报形态。选段目读与23组人工配对在实现前固定于材料清单（本地数据：`../tests/fixtures/meihua_external_v1/manifest.json`）。这不是已验证的物理因果、临床或灾祸评估；原书中的“真生真克”也不等于软件测得了作用强度。

| 已报类别 | 原体与所选条款 |
| --- | --- |
| `furnace_flame`、`candle_flame`、`red_purple_color` | 乾、兑金体下，区分炉中真火、微细烛火、仅见红紫形色 |
| `sharp_metal_tool`、`metal_ornament_or_utensil` | 震、巽木体下，区分快刀巨斧与所列饰物器皿、琐屑金属 |
| `actual_water` | 离火体下列真水之克；震、巽木体下列真水之生，两者分别核对 |
| `black_or_damp_appearance` | 离火体下的黑色或湿象，不自动等同实际水 |
| `soil`、`fired_pottery` | 乾、兑金体下保留“土能生金，瓦不能生”的原文区别 |
| `cut_firewood`、`living_tree` | 离火体下区分已伐柴薪与未伐树木的相对捷、迟，不转换成钟时 |

例如土与瓦器都按原文归土类，对乾体的 `raw_relation_to_body` 都是用生体，但所选 `qualification` 分别保留土生金与瓦不能生。符号关系没有被反向改写；详细条款没有覆盖的配对返回 `not_addressed_in_selected_pairs`，不把“同属五行”自动升级为作用已成立，也不补成中性或吉利。

`interpretation.external_omens` 保留已报资料、实际原体路径、原始关系、资格、规则ID和原页定位。各取数候选另列自身的 `casting_readings[].external_omens`；11、1声、子时两种口径的原体分别为离、乾，所报同一炉火不能借用另一候选的资格。没有资料时该层为 `null`，仍表示未采集，不能解释为确认没有外应。时间入口无取数候选，`external`字段卡不请求不存在的 `casting_readings` 路径。

原页有“值之始有不吉”“生火之遲也”等字样，固定网络转录另作“必”“炎”，差异随规则集保留，不默改所选本。红紫形色句跨108、109两页，定位补充（本地数据：`../tests/fixtures/meihua_external_v1/source-locator-supplement.json`）注明原109指针是句末所在页，引用页列表保留两页；原预期、原始清单和引文未改。目读未经独立人类专家鉴定，配置为 `meihua_external_manifestations_nlc1925_v1@1.0.0`，不认证全章、作者归属或现实预测效力。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"111111","moving_line":6}' --external-observations '[{"manifestation":"soil","label":"虚构示例：土"},{"manifestation":"fired_pottery","label":"虚构示例：瓦器"}]' --fields meihua.body_trigram interpretation.external_omens --strict-fields true --include-snapshot-text false --response-char-limit 0
```

该层只补外应所选配对，不改变取数、动爻、互卦、内卦制约或初始题篇，也不与内卦计票、抵消成结论。`numeric_effect_strength/real_outcome/event_time/combined_outcome` 保持 `null`；相对“捷、迟、轻、重”不转换成强度、概率、收益或日期。实际场景与类别由调用者提供，独立核验观测数仍为0。

### 宝象、凶器与原体限定

所选文明书局本卷二《内外论》（原PDF索引90、纸面卷二三七）有两则明确限定：金银虽属世宝、通常取吉象，震巽为体时，因金克木“反为不吉”；兵刃通常取凶象，坎为体时，因金生水“反为不凶”。不把“不凶”改成“吉”或物品安全，也不把“不吉”扩大成现实灾祸。

两入口的`external_observations[].manifestation`增列`gold_silver_treasure`与`weapon`，仅在调用方明确已报原文金银世宝或兵刃类别时使用。`weapon`是原文兵刃类，不泛指所有现代武器、木棒或普通刀锯；所配金是典籍类别，不认证实测材质。未知类别省略，不从普通金属饰物、锐器、问句愿望或标签文字猜分类。多个已报类别各自保留，不投票，也不把记录数当作独立见闻。

`interpretation.external_omens.body_relative_symbols`保留通常象义、本候选实际原体、生克、原文条件、限定后的象义与事实路径。仅木体的两卦震巽、坎水体分别满足这两则明示条件；其他原体的限定象义为null，不据通常吉凶象填成结论。各计数候选使用自己的原体，不取变卦重新分体用。

旧实物资格与新象义分别读：原`sharp_metal_tool`不自动等于兵刃，`metal_ornament_or_utensil`不自动等于金银世宝。新类别不擅自继承旧实物对照里的真克、无实克或真生；未覆盖的实物资格仍是`not_addressed_in_selected_pairs`。旧11类及其结果保持原值，未报新类别时不新增此层。普通外应卡仍含完整外应对象，也可用`external_symbol`字段卡。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"111010","moving_line":1}' --external-observations '[{"manifestation":"weapon","label":"虚构明确已报原文兵刃的工程例"}]' --fields meihua.body_trigram interpretation.external_omens summary --strict-fields true --include-snapshot-text false --response-char-limit 0
```

本层只实现两则原体限定，不实现同段的临床、生死、生产判断，不认证现场或现实结果，也未完成内外、旺衰及多应的净综合。材料、候选算术更正及验证范围见审计说明。

### 求财补充句的内卦关系

显式选择 `interpretation_topic=wealth` 时，`interpretation.wealth_components` 补入同一文明书局影印本卷二《求財占》随后两句的关系成分，来源为原PDF零起算68页、印刷叶卷二十五。原页和11组手推卦图先固定在材料清单（本地数据：`../tests/fixtures/meihua_wealth_components_v1/manifest.json`）。固定网络转录无法在该范围重新打开，比较仅采用此前已有哈希的文字；所选原页重新下载并核对完整PDF哈希。目读由助手完成，未经独立人类专家验收。

补充句的“有财”侧点出体克用、生体，“破财”侧点出克体、体生用。引擎核对初用、体互、用互、变用各自对同一原体的实际关系，记录每项是否存在、出现在哪些角色，以及其已有季令和直接制约。纯乾坤从本次实际变卦取互；同一静体不重复算成另一个作用者。每个计数候选均沿用自己的原体及事实路径。

例如已有井卦、五爻动，原体巽：初用坎为用生体，体互兑为用克体，用互离为体生用，变用坤为体克用。四项关系并存；初始“进益”条款不能掩掉互卦中的受克和耗泄，生助受制与克体被制仍按原资格保留。这里没有因此算出实际净收入、投资结果或损失金额。

`source_groups` 保留两句原文及各自成分；`all_named_components_present` 只说明所列成分在当前范围内是否全部出现。原文“及”的组合含义仍未唯一裁定，因此 `full_clause_applies=null`，不将这项布尔值当成完整财运断语。两侧成分可同时存在，不计票、不抵消，不覆盖原初始体用条款。`timing_reference` 保留原文卦气措辞，`event_time/real_financial_change/success_probability` 均为 `null`；已知起卦日期也不能自动转换成进财或破财日期。

`wealth` 字段卡用于本分支的摘要，`topic/topic_audit/audit` 卡也保留该层。计数有分歧时，另读 `interpretation.casting_readings[].wealth_components`，不能复用主候选的原体、季令或制约。这一补充只适用于所选求财篇；其他分支为 `null`，问题文字不会自动切换题篇。原初始20条、取数与天气研究政策保持原版本；新的局部关系成分配置单列 `meihua_wealth_components_nlc1925_v1@1.0.0`，不冒充全章或现实预测验收。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"011010","moving_line":5}' --interpretation-topic wealth --fields interpretation.topic_reading interpretation.wealth_components --strict-fields true --include-snapshot-text false --response-char-limit 0
```

### 同次现场的方应、天时应、地理应与人事应

两个人事入口可选`response_context`，只接同次起卦时已经报告的现场事实，须有非空`label`及严格布尔`same_casting_episode_confirmed=true`。没有该对象时旧输出保持原样；对象已给但各类均未知时保留待齐状态，不把未知视为没有外应。仅在已提供该对象时读`situational`字段卡，其字段参考须复制到`fields`，不传`view`参数。

| 可报字段 | 原文类别与实际查表 |
| --- | --- |
| `querent_position={direction,reference_label}` | 来占之人所在的八方及已报参照，方位图配卦；不是行进、朝向、住址或端法所见对象的方向 |
| `weather` | `clear`晴明离、`rain`雨、`snow`雪均配坎，`rain_or_snow`表示雨雪未分、`wind`风巽、`thunder`雷震；为当时条件，不是所问未来天气或日雨量标签 |
| `setting` | `bamboo_woodland`竹林震巽、`rivers_streams_or_pools`江河溪涧池沼坎、`metal_place`五金乾兑、`kiln_stove_or_fire`窑灶炉火离、`earth_or_tiles`土瓦坤艮 |
| `human` | `elderly_man/elderly_woman/young_boy/young_girl`对应原文老人乾、老妇坤、少男艮、少女兑；`heard_laughter/weeping_encountered`只列笑语喜庆象、哭泣悲愁象，不造一个卦 |

后三项可报列表；多项并列，不重复填同项增票，也不按结果选一个。竹林、五金、土瓦的两个原文卦全部保留。每项与本候选自身原体算五行关系，候选之间不共用原体；方应的生体、比和及克体、体生之偏好依原句分列，原体克方卦一项原句未述，不补作有利。天时另核对原文明示的离宜晴、坎宜雨、巽宜风、震宜雷。雨与雪均取坎象，但“宜雨”不自动扩成“宜雪”；雨雪未分且原体为坎时，条款适用性为null待定；原体不符时为false。`matches_actual_body`只核对体卦，不能代替`clause_applies_to_reported_conditions`。不从同五行擅自扩充精确原句配对。

所选文明书局本卷三《占卜十应诀》原PDF索引128—130，八方图索引21。影印总目有方应，固定转录1441927总目漏列方应；影印作“所坐立之方卦”，转录作“方位”。影印天时句为“體見雷為比和”，转录为“火見雷為比和”；前者主语接续未裁定，后者若取离火对震木，通用五行关系仍为用生体，不能静默改成比和。原文见证、候选映射和计算关系分别保存，不凭熟悉转录补字。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"111101","moving_line":1}' --response-context '{"label":"虚构现场工程示例","same_casting_episode_confirmed":true,"weather":["thunder"],"setting":["metal_place"]}' --fields meihua.body_trigram interpretation.situational_responses summary --strict-fields true --include-snapshot-text false --response-char-limit 0
```

同次完整静室无所闻见声明不能同时附带已报现场事实；已闻笑语也不能与`nothing_heard=true`并存。未知资料、单一知觉字段或别的输入不补成矛盾。该层仅适用于人事体用分支，`interpretation_topic=weather`拒绝；不改卦、不自动识别场景，不合成完整十应、年月日旺衰、现实结果、概率或应期，也不改变旧研究标签、入组或分母。范围与验证

### 失物占的体用与变用方位类象

显式选 `interpretation_topic=lost_property`，使用 `topic` 或 `topic_audit` 字段卡。该分支采用文明书局本卷二《失物占第十五》，PDF 索引69为题目、70为正文，原PDF SHA-256为 `af608094ab11ae209eae91a9365565e7c9cff604aac3da5e753e04d1cc4598c0`。五种初始体用条款和八卦方位类象分别保留；旧四题篇20条及出行、谒见10条没有改写。

`interpretation.topic_reading` 按原体、初用匹配五种关系，`chapter_qualifications` 单列位置条款。原文“又以變卦為失物之所在”在此明确采用变动的三爻经卦，即 `changed_use`，并提供实际动爻及 `trigram_fact_path`。卷一观梅例区分“初爻變咸”和“變為艮土”的用语支持这一操作性读法，尚未独立裁定为失物章的唯一解释。方向直接取失物原文，不从先天卦序数字换算角度。乾卦初爻或四爻动时均为变用巽、东南；不会把仍为乾的另一半卦误取为西北。

声数组11、1、子时的原数与卦序数取爻，分别为初爻与五爻，初始条款为“可尋遲得”与“不可尋”，变用分别为巽、乾。`casting_readings[].topic_clause.chapter_qualifications` 各自读取自身卦图与事实路径；差异保留，不用主候选替代，也不按结果选择口径或投票。

影印本与固定转录1441921保留“公廨／公榭”“倉廩／倉稟”“舟車／舟居”“庖廚／皰廚”“爐／爐冶”等字句差异。影印页经放大复核，将初读“倉庫”更正为“倉廩”；初读和更正记录随冻结参考保留。图像与所选字句仍是助手选段阅读，未经独立人工专家鉴定，不能据此宣称校勘定本。

“物不失矣”仅是比和条款的历史占辞，不能否认已报遗失，也不能断言已找回。地点为原文类象；没有现场参照原点、数值方位角、坐标、实际位置或搜索许可。`real_location/loss_or_recovery_verified/event_time` 保持 null。详见失物章选段与变用绑定审查。工程检查不计作新的现实占验，也不改变已有天气研究的失败、未到期计划或四项未满分状态。

### 求名占的在任条件与原文时序方道

求名分支 `interpretation_topic=reputation` 在初始五类体用之外，另提供 `topic_reading.chapter_qualifications`。本层选用文明书局本卷二“求名占第九”补充五句，分别列出生体卦气、职任方道、无克体条件、在任见克体及其时序依据；初始20条规则集保持原样，没有宣称完成全章综合。

可选 `reputation_context` 要求非空 `label`；`currently_in_office`、`seeking_official_appointment` 只接收已确认的布尔值，未知省略或 `null`。前者指原文的“在任”情境，后者指“職任之處”的问事范围，不能从普通就业、考试、晋升愿望、问题文字或 label 推定，两项分别声明。提供该对象必须显式选求名分支。

每个取数候选均沿用自己的原体，四个辅助角色的生体与克体分别列出时序原句，同时绑定自身受制资格与旺衰字段路径。内卦已有克体会否定“無尅體”的必要条件；所列内卦无克体只能说明这一已知范围，不能确证完整内外范围无克体。在任声明为真且已见内卦克体时，才满足所选在任句的明示条件；这不构成现实处分、失职或灾祸判断。

“變卦之方道”采用明示的变用经卦读法，逐候选核对实际动爻和 `changed_use`，未声称唯一原典裁定。所选影印本巽的**方道**栏印“東”，同本**地理**栏印“東南方之地”，固定转录方道亦作“東南”。结果保留三处证据，不用常见八卦方位表静默替换；`single_geographic_direction`、实际任所和方位角保持未定。

八卦時序保存影印原字和固定转录对照。震“春二月／春三月”、乾“五金／一四九”、巽“時日月／時月日”及所列月份等差异未裁定，不转换成公历月份、经过天数或应验日期。所选在任句“上責罰／上司責罰”“退職／退居”等也分别保留。影印读稿由本次助手核读，尚无独立专家认证；权威藏本的出处不能代替语义和现实预测验证。

`topic` 和 `topic_audit` 字段卡均已含上述依据；每个 `casting_readings.topic_clause.chapter_qualifications` 应独立读取。REST、MCP、CLI 共用新输入合同；已有客户端须以当前连接实际 Schema 为准。详见审查。

### 行人占的原体与初用参照

显式选 `interpretation_topic=traveler`，读取 `topic` 或 `topic_audit` 字段卡。文明书局本卷二《行人占第十三》的五条返归关系仍以原体为主；`chapter_qualifications.initial_use_frame` 则另以本候选初用为受作用者，列出原体、体互、用互、变用对它的有向生克。体生用意味着初用可受原体之生，不能与用生体混写。原体方向、返归条款与各取数候选自己的旺衰、路径均保留。

“逢衰受尅”核初用的衰标记和实际受克是否同时成立，缺月令及“原文未定”保持未知。受生和受克可以并存，受制另外列出，不按票数抵消成结局。完整内外角色范围、震多艮多的门槛与分母尚未裁定；坎兑句只标明初用经卦的工作读法。影印引句暂读“又以用卦為行人之盈旺”，固定转录作“又以用卦看行人在外之情況”，末句“紛爭之應/紛爭”等差异随规则保留，未经独立专家裁定。

下例是虚构卦形的工程核对，不是个人问事。原体离火、初用艮土为体生用，补充中的原体角色应为生初用；原卦不被改写。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"101001","moving_line":4}' --interpretation-topic traveler --season-month-branch 寅 --fields interpretation.topic_reading --strict-fields true --include-snapshot-text false --response-char-limit 0
```

归迟、未归、即归及不日不换算为天数；没有核实返归、行踪、安全或现实结果，`event_time`、`return_verified`、`real_location`、`hazard_verdict`、`success_probability` 和 `real_outcome` 保持 `null`。完整来源、独立参照的8条互卦修订及验证范围见行人占核对记录。这项扩展不改变已保留的天气失败验收，也不认证全书或预测能力。

### 婚姻章的两家角色、旺气与比利异文

两入口可显式选`interpretation_topic=marriage`，使用`meihua_marriage_clauses_nlc1925_v1@1.0.0`。所选文明书局本原PDF索引65—66的《婚姻占第五》首段五条沿用本次原体与初用，逐条保留“或”及相对“成迟”。问句里的结婚、求婚等字样不自动换章；日期、概率与实际婚姻结果未核定。

`topic_reading.chapter_qualifications.family_frame`依“体为所占之家，用为所婚之家”分别列原体、初用，不默认男方女方或指派现实人物。两条`strength_clauses`分别核原体旺与初用旺：按已有所报节月约定标旺则符合，标衰则不符，“原文未定”或缺节月则为`null/pending_known_strength`。相应的“此家门户胜”“彼家资盛”仍是传统条件措辞，不是查得两家财富；这里没有完成年月日与内外合参。

首段影印明写“体用比和婚姻吉利”，可按实际原体用同气匹配。后段跨页却写“若体用比利则彼此相就良配无疑”，固定转录1441921作“比和”。两处分别保留：后段`bili_supplement.source_relation_condition=null`，即使本次五行相同也不自动套用“良配无疑”。不能用熟悉转录把影印“比利”改掉，再宣称同版无歧义。

补充的生体、体生句逐项列本次初始关系及四个实际辅助角色中的关系成分，保留“或”字及角色事实路径。原句未在该处明写完整作用角色，`full_source_clause_applies=null`；没有据此确定婚财、嫁奁或任何人的求婚意愿。原书随后八条相貌、品行文字另作历史记录，原段未明定取哪个角色指向谁，程序不据卦象给现实人物贴相貌、品行或族群标签。各取数候选均用自己的原体、初用、旺气和章句。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"sound_groups","first_count":10,"second_count":3,"hour_branch":"子"}' --interpretation-topic marriage --season-month-branch 申 --fields interpretation.topic_reading interpretation.casting_readings --strict-fields true --include-snapshot-text false --response-char-limit 0
```

实现前固定的原页、读稿及4,992组上下文（本地数据：`../tests/fixtures/meihua_marriage_v1/manifest.json`）来自复用384种卦形乘13种节月状态，不是新占验或现实观测。影印目读未经过独立人类专家鉴定。范围与验证见审查说明。

### 饮食章的酒食象与直接制约

两入口可显式选`interpretation_topic=dining`，使用`meihua_dining_clauses_nlc1925_v1@1.0.0`。文明书局本原PDF索引66—67的《飲食占第七》五种初始关系沿用本次原体、初用；问句里的饮食、赴宴等字样不会自动换章，也不因此重起卦。

`topic_reading.chapter_qualifications.symbols`另读“有坎则有酒、有兑则有食”的酒食象，并保留索引89《體用類》的“如遇坤艮则坎亦无酒”“离值则兑亦无食”直接制约。每个符号分别保留原始出现、实际角色、制约者、制约者自身受制及相应事实路径。所选两条饮食制约句没有“多”字门槛；单个已列明的坤、艮或离即可触及相应内卦条件。季令衰不自动禁用直接制约，制约者自身受制也不递归取消；这些限制仍未合成为完整内外净结论。

本层明示以原体一次加四个辅助角色为内卦工作范围，并保留本、互、变六个位置。384种旧卦形中两种表示的出现集合相同，因此“有／无”不依赖把静体重复计一次；角色重复不作独立证据或应验投票。没有列明的内卦制约也不证明完整内外无制约，`complete_internal_external_control_assessment=null`。

影印索引67作“兑坎生身酒肉醉饱”，固定转录1441921作“兑、坎生体，酒肉醉饱”。原文“身”是否指本次原体、兑坎如何组合，均未裁定。程序只另列各候选相对原体的实际生体成分，`source_target_binding/full_source_clause_applies=null`。在普通五行圈中，金生水、水生木不能同时指向同一个原体五行；这项条件性算术事实不能据以改写底本或替原句选择“或”。

影印标题“體用類”与转录“體用”分列，旁注“飲食八事類者……”亦照存，不补成“八卦类”。所食何物与席上何人只保留原文转引及两侧实际互卦，选用角色与互卦侧尚未裁定。`actual_menu/actual_attendees/real_food_or_drink_available`等现实字段保持`null`；酒食象不是实际餐食供应、饮酒指令、营养或临床建议。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"sound_groups","first_count":1,"second_count":9,"hour_branch":"丑"}' --interpretation-topic dining --season-month-branch 子 --fields interpretation.topic_reading interpretation.casting_readings --strict-fields true --include-snapshot-text false --response-char-limit 0
```

上例两种口径均为初始比和，原数动六爻、卦序数动四爻，却有不同互变及食象制约；同一初始章句不能替代各候选自身酒食象。原页、身／体异文及实现前算术见冻结清单（本地数据：`../tests/fixtures/meihua_dining_v1/manifest.json`），验证范围见审查说明。4,992组上下文复用384种卦形和13种节月状态，不是独立现实观测。

历史天气研究的已发2008条预测、1004个唯一目标日期、13057条来源观测与研究政策身份保留在 `tests/data/meihua/weather_evidence/`。独立核对原273日主队列仍为正确贡献29、始终无雨基线158；该负结果不由当前producer重算或改判，不代表当前预测已有改进。缺失出版时点、非盲回顾、未知真实性与未获现实效度认证的范围继续保留。

## 天时占与固定天气研究

### 天时占独立分支

两种入口都可显式指定 `interpretation_topic="weather"`，执行卷二「天時占第一」的选定条款。原文要求不分体用，天气解释不会套用人事的体用吉凶、爻位阶段或现代行动模板；问句关键词不自动选择分支。一般模式仍为 `general`，`weather_context` 必须与天气分支一起提供。

天气层包含40项通象及条件读法，返回 `interpretation.weather.ruleset`、六个卦位、计数和逐条条件轨迹。新增的朝、暮两项来自同一句原文，不计为两份独立证据或观测。原文中的夏旱、冬雪和久雨转晴须对应已确认的 `weather_context.season`（`spring/summer/autumn/winter`）及 `prior_condition`。前期天气可明确声明 `prolonged_rain`（久雨）、`prolonged_clear`（久晴），或在两个条件均已确认不成立时传 `neither_prolonged`。省略或 `null` 仍表示未知；不能为了消除待定而补成 `neither_prolonged`。这个新增值扩充事实输入，不新增原典条款，不替原文给“久”规定天数。

`neither_prolonged` 只使依赖久雨／久晴的四项条款不满足，其他36项仍按自己的条件计算；缺季节和缺“多”阈值不会因此补齐，单卦也不会因此产生唯一预报。已确认某个必要条件为假时，该条款为 `not_met`，即使其他条件仍未知；未确认的前期天气继续保留相应 `pending_context`。不从时区、当前天气、卦象或五行旺衰推造事实，也不把一天无雨、间歇降雨或缺测自动判为两个长期条件均不成立。

“无雨”与“晴”属于不同观测维度。香港天文台的[2009年预报检验论文](https://www.hko.gov.hk/tc/publica/reprint/files/r829.pdf)第2.2、2.3节分别检验天空状况与降水；前者使用日照、云量，不能只凭雨量判定。它是方法资料，不作为今天的完整业务标准或古文“晴”的唯一气象定义。公开[日平均云量资料](https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-mean-amount-of-cloud)也与日雨量分别记录。因此，雨量低于研究阈值不能直接填 `prolonged_clear`，也不能把旧研究的“晴象转无雨”代理改称晴天预测通过。月度发布的回顾数据不证明某日起卦时已经可得；未核定当时可用时间和持续时长口径时，不自动回填天气条件。

观测映射诊断保留原1,004个目标日期及完整雨量／云量记录、缺测状态和全部云量值分布，不生成晴天标签或前期天气输入。事先选定的100%云量极值探针只对应1条云量记录、无雨同现数为0，不能凭这个小分母判定雨量与晴的等价关系；原始0结果及随后补充分母、全分布的探索说明均保留。604个低于雨量阈值的日记录对应的日均云量范围为0%至95%，没有据此另选晴天阈值。该诊断没有重标旧预测或更换273日主终点，旧预测仍未胜过固定基线。

以下是明确声明前期两个长期条件均不成立的接口示例，不是现场天气事实：

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"001010","moving_line":4}' --interpretation-topic weather --weather-context '{"prior_condition":"neither_prolonged"}' --fields interpretation.weather.context interpretation.weather.pending_rule_ids --strict-fields true --response-char-limit 0
```

“全观”以本、互、变上下六个位置计数，“相逢／在上”等组合在同一重卦内匹配，均是明示的软件范围约定；不加入错卦、综卦。“多”没有原文数值阈值。可在事前以 `many_min_count` 明示2至6的研究约定，否则相应条款待定；不能看过结果后调阈值追求命中。六位置是计数位置，重复卦象也不形成独立观测样本。

例如重离在本卦出现、互变又见兑艮时，晴象与阴云象均可返回；久雨逢艮与其他雨象也可能同时成立。`conflicts` 保留未定时段条款的并列关系，不能据此断定它们描述同一实际时刻。明确朝暮的关系另看 `time_scope_comparison`，不把多条原文投票为一个“最准”的天气答案。`single_forecast=null` 表示尚无经独立验收的唯一预测政策；不能只选有利条文去匹配已经知道的天气。`weather` 字段卡见两份生成调用合同。

```bash
uv run --locked --extra dev fatebridge meihua_cast --casting '{"method":"existing","hexagram_code":"101101","moving_line":1}' --interpretation-topic weather --weather-context '{"season":"summer"}' --fields interpretation.weather interpretation.evidence_scope summary --strict-fields true
```

初版天时规则审计核对固定卷二转录的31处引文（入口及初版30条条款），并用8项手算条件探针检验计数、季节、缺项和不跨卦拼配。这些探针没有真实天气观测；不计为原书占验，更不计为前瞻命中。乾兑制震巽、秋冬非常雷、部分互卦句义及全书优先级仍未完成校勘，覆盖状态保留为 `partial`。

当前基础天时配置为`meihua_weather_v1@1.7.0`，其朝暮、季节、频数与取数候选按下述范围分别核对，另接入 `meihua_weather_controls_v1@1.0.0`。卷二「體用」「體用論」明确列乾兑金多制震雷、巽风，坤艮土多制坎雨，坎水多制离晴。`controls` 对这些直接条款逐一保留已声明阈值及计数候选，不把“见坎”的通象当成已排除制约的雨断，也不把坎雨受制扩展为其他来源的雨象全被取消。

计数本身也有需要校勘的边界：卷一借斧例记“三乾金、二巽木”，本互变上下六个位置会得到三乾三巽；本卦两位、互卦两位、变用一位，只计一次静卦，才复得三乾二巽。`frequency_views` 保留这两种计数与实际字段路径。五位置得到该原例支持，但不能自动推为天时全章唯一规定，因此不静默改掉原六位置频数政策。乾兑／坤艮合计或任一单卦计数也分别保留；候选有分歧时标 `scope_unresolved`，不投票决定。

1.2.0把这一前提核对扩展到四条含“多”的基础条款。`status`继续表示明示六位置约定下的原始结果；`frequency_assessment`另列两种分母的计数、阈值、判断和事实路径。若六位置满足、五位置不满足，`effective_status`为`conditional_on_unresolved_frequency`，`conditional_tags`保留对应条件性象义，`selected_readings`及摘要会直写“频数范围未裁定”。例如离卦初爻变、阈值为3时，六位置计三个离，静卦只计一次则为两个，不能把“离多”当成无争议事实。重离的独立组合条款仍按自己的条件核对，不因含“多”条款有分歧而一并取消。八项手算探针不计作真实天气观测。

秋冬震多“无制”的条件仍未实现：未命中目前所列的金多制震条款，不等于证明已排除所有制约。该缺项保留在`unresolved`，不能由此推出确定的“非常之雷”。这次修复没有改动已冻结的2025年负结果或未来天气研究政策，也没有建立1.2.0的现实预测效力。

共享农历扩展后的326日另列为同源年表映射核验，原73,058日的对照范围保持独立记载；这326日不重复计作独立天文准确率。该天气规则范围尚无独立真实模型语义验收。

1.3.0把显式取数的实际候选接到天时解释：`casting_variants`分列每种口径的实际动爻、本互变卦码、六位置频数、命中条文、制约状态及依据路径，`casting_variant_traces`保留各候选完整条件轨迹。两者都来自同次计算，使用相同的已确认天气条件；首轮`weather`字段卡保留候选解读，`weather_audit`卡选取原始`meihua`与完整轨迹。需要完整审计时首轮用该卡或`fields=null`；`result_delivery`只保留本次已投影的字段，不能假称摘要卡未选的轨迹仍可取回。候选事实路径指向`meihua.counting_variants`的实际结构，不误指所选主卦。该结构路径含数组位置，不是`fields`的逐项选择语法，数组按整项读取。

例如九件物、酉时，原数法与卦序数法的动爻为1与5。前者变卦见坎，后者变卦见离；若明确夏季及“多”的阈值2，两者命中的天气条文不同。`casting_comparison`报告差异条款及制约，不合并频数或投票得预报。`same_rule_results_for_supplied_context`只表示所选规则在当前资料下结果相同：同一组听声候选可以夏季相同、冬季不同；不能据此认证唯一古法或实际天气。七项新增手算探针含这一反例，真实天气样本及真实模型运行均为零。

1.4.0补入“艮多则久雨必晴”，与原有“久雨得艮，取止雨象”分别核对。前一条须确认久雨、明示“多”的阈值，并保留五／六位置计数分歧；只有一个艮、前期天气未知或已知久晴时，不能据此条断晴。两套影印本的所选原页与人工校读（本地数据：`../tests/fixtures/meihua_weather_gen_v4/collation.json`）都保留“久晴不雨，得此亦然”，没有借此消除“此”的指代疑义。新增七项手算探针不是实际天气观测，未建立当前版本的预测效力。

该范围“人工／手算”指助手对影像逐页目读及逐步推导，未由生产计算器生成预期答案，也未经过独立人类专家验收；不把助手自身的复核写成人类或学术机构认证。核读方法说明与冻结参考哈希另存，原字句及预期值保持不变。

1.5.0补入“震多则春夏雷轰”“巽多则四时风烈”“兑多则不雨亦阴”，分别核对已报春／夏、明示“多”的阈值及五／六位置资格；巽多四时不额外要求季节，兑阴也不是无雨标签。另按同一重卦匹配艮巽风云际会，不把不同卦的艮、巽拼成同卦。十六项预先固定的数学探针覆盖缺项、季节排除、频数及制约资格，实际天气观测仍为零。

`selected_readings.source_witnesses`逐条保留固定转录与影印所选字句：两本可辨的重坎后句作“四时多雨”，所引固定转录作“四时必雨”；文明书局本另有“水火未济”“昏濛”等异文，德聚堂本的天时标题为第二，文明书局本为第一。当前保留转录原引文和各自读法，不据熟悉的卦名或程序结果改掉影印字句。乾卦久雨条款的影印选段仅清楚辨得“久雨必晴”后句，其完整乾卦主语未确认，不声称该选段认证了全句。

选段校读与更正记录（本地数据：`../tests/fixtures/meihua_weather_chapter_v5/collation.json`）区分35条规则关联的选段、重复引用、字形未决和主语未确认；章内知识清单（本地数据：`../tests/fixtures/meihua_weather_chapter_v5/inventory.json`）沿原章次序列36个阅读单元，保留秋冬“无制”、泛冬坎雪、春土雨、互卦虹霞及暮朝天气等未完成部分。阅读单元不是准确率分母，也不以关联到一条规则就宣称整句完成。校读由助手目读，未作独立人类专家验收或全章逐字、字义认证。初录曾过度补全乾卦句，原值与更正记录保留，数学预期文件未改。

扩展规则后，频数审计另列`numerical_probe_rule_ids`与`quote_only_rule_ids`：旧八项探针只验证四条原有含“多”规则的数值条件；艮条款在1.4.0另有七项探针，1.5.0其余新增条件在该范围另有十六项探针，不能把新增引文核对当成旧探针已覆盖其计算。原72,723日历表子队列保留其原分母，所比字段无差异；与新增覆盖分列。

#### 1.6.0的季节句与版本差异

季节条件审计补入固定卷二转录1441921的三条条件。它们的计算依据是该转录，不能把不同影像的字句拼成一部无异文原典。

| 条款 | 本次明示的计算条件 | 文明书局原PDF第63页所选读法 |
| --- | --- | --- |
| 秋金晴明 | 已确认秋季，本互变见乾或兑 | 可见“乾兌之金秋明晴”；“之金”与转录“為金”分别保留 |
| 冬坎雪冷 | 已确认冬季，本互变见坎；不附加“坎多无离” | 所选连续字句为“乾兌之金秋明晴冬雪凜冽”，此处未见“坎之水”，不补入未见的主语 |
| 春土雨泽 | 已确认春季，本互变见坤或艮 | 所选字形读“坤兌之土春雨澤”，与转录“坤、艮”有异，不据五行常识静默改字 |

“乾兑金”“坤艮土”按所列卦类任一出现匹配，是明确的软件成员条件；不要求两卦同现，也不添“多”的阈值。每条继续返回 `textual_status`、`source_witnesses` 与实际事实路径。春季土雨的依据是坤艮，不能因土制坎水就连该雨象一并取消；秋金晴也不能随坎水制离而取消。两个取爻候选分别以自己的本互变核对冬坎，不继承所选候选才有的坎象。

修改前固定的16项探针与校读（本地数据：`../tests/fixtures/meihua_weather_seasonal_v6/manifest.json`）包含实际动爻、本互变、纯乾坤取互、跨卦位出现、未知或不符季节，以及两项独立来源制约条件。卦名的兑／兌、离／離仅作表示归一，不改卦画。旧35条规则和旧数值预期保留；旧v5校读报告明确列出该范围三条不在其原35条范围内。影像读法与逐步推导由助手完成，尚未经独立人类专家验收。“夏火炎蒸”的主语、秋冬震多“无制”及全章优先级仍未裁定；此前1.0.0和1.5.0现实检验不能认证该范围1.6.0。

#### 天时类象与明示季令

`interpretation.weather.symbolic_attributions` 补列所选文明书局本的类象，包含原文、实际本互变位置及季令核对。主天气规则仍为1.7.0的40条，补充配置另记 `meihua_weather_attributions_nlc1925_v1@1.0.0`，不把它冒充已进入旧研究的雨晴标签映射。

| 实际卦类 | 所选原文类象 | 本层核对的明示季令 |
| --- | --- | --- |
| 乾或兑 | 霜、雪、霰、雹 | 末段只明确“霜、雪”验于冬月，不能推广给霰、雹 |
| 离 | 日、电、虹、霓 | 末段的夏天句用于电，未给日、虹、霓同一季节限制 |
| 震 | 既有雷象 | 补核夏天句；不据此裁定秋冬“无制”等例外 |

成员是否出现不需要“多”的阈值，完整六位置与实际事实路径仍保留。缺少季节时，相关核对为 `pending_context`；季令相符为 `season_matched`，不符为 `season_not_matched`，这两个状态都不表示实际天气已经出现或一定不会出现。没有相应卦名时不补列类象；每个取爻候选用自己的本互变和路径，不能继承主候选的卦象。

原PDF索引63的所选字序为“乾兌為霜雪霰雹”，固定转录1441921为“乾、兌為霜雪雹霰”，两者分别记录，不为统一顺序而改原文。索引64的“震離為電為雷應在夏天”“乾兌為霜為雪驗於冬月”另列为季令依据。本层不把“日”改写成晴或无雨，不把日、电、虹、霓解释成同时发生，也不擅自把霰、虹、霓定义为现代可评分观测量。

这项补充没有裁定全章制化、无制例外或综合优先级；季令相符不能当作未受制天气判断。旧天气轨迹、控制、频数、朝暮与研究负结果保持原值。新增真实观测、独立模型语义验收均为0，`single_forecast/event_datetime/success_probability` 保持 `null`。原页、四项新增选段与既有雷象的对照、实现前1,920组参照见固定材料（本地数据：`../tests/fixtures/meihua_weather_attributions_v1/manifest.json`），范围及验证

#### 1.7.0的朝暮与未定时段

朝暮条件审计核对“離在艮上，暮雨朝晴”。固定转录1441921和文明书局原PDF第64页所选字句均保留。实际同一重卦上离下艮时，分别返回 `time_scope=morning` 的朝晴与 `time_scope=evening` 的暮雨；不把它们加入未定时段的晴雨矛盾。上下倒置、仅在不同重卦见离艮、或另一取爻候选才有旅卦，均不能套用本条。

| `time_scope_comparison`字段 | 可说明的关系 |
| --- | --- |
| `groups` | 按原文时段分列原始象、已具资格象、待定与受制标签；不把标签当实测天气 |
| `unspecified_time_conflicts` | 旧未定时段条款并列，亦保留在 `weather.conflicts`，不据此认定同一时刻 |
| `same_daypart_conflicts` | 同一原文时段的不同象义仍并列，不投票选胜者 |
| `separated_daypart_pairs` | 明确朝暮的不同象义；不自动假定已定位同一具体公历日 |
| `unresolved_time_relations` | 未定时段与朝暮之间的关系未核定；未定不等于全天，不自动求交集或赋予优先级 |

朝暮不换算几点、日出日落或目标日期；显示顺序也不是已发生事件的时间线。已知 `analysis_context.analysis_datetime` 是起卦输入，不能因此把原文朝暮自动定位为当天应验。另用香港天文台[2026年历表](https://www.hko.gov.hk/tc/gts/time/calendar/text/files/T2026c.txt)的正月初三，手推2026-02-19香港时间06:00的午7、月1、日3、卯4：上数11取离、总数15取下艮及动三爻，得到本卦旅；这个新增接口探针在实现后固定，与修改前16项卦图分开，不是现实天气观测。

修改前固定的16项卦图和6项合成时段判据（本地数据：`../tests/fixtures/meihua_weather_dayparts_v7/manifest.json`）另核对两组取爻候选：原38条状态相同，新增朝暮条款却因本候选才有旅而不同，不共用主结果的时段读法。按本工具2–5爻取互方式，普通互卦只有16种图式，完整旅卦不在其中；这项卦图约束不裁定后句“離互艮宮”的语义，也不据此改掉原文。后句及精确应期仍未实现。所选字句由助手目读，未作独立人类专家或整章认证；旧现实检验和1.6.0模型准备均不能认证1.7.0预测效力。

`rule_trace.status=matched` 只表示原条款的表面条件命中。读法须核对 `effective_status`、`controlled_tags`、`conditional_tags` 与 `control_checks`。首轮 `weather` 字段卡改用 `selected_readings`，每条带实际资格、依据路径和引文；`weather_audit` 卡保留完整条件轨迹。当前只实现直接制约，尚未递归裁定制约者再受制、秋冬非常雷或全局优先级。跨章制约审计保留一项既有原例的频数复核及八项新增手算探针。

未来降雨试验记录另固定2026-11-01至2027-10-31天文台单站的365个当地日期，预先保存70个雨、141个无雨、154个弃权标签及逐日证据，尚无观测结果。来源为香港天文台的[每日总降雨量数据集](https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-total-rainfall)，目标是日雨量至少0.1毫米，要求数据完整标记，缺失不按零雨量处理。

此试验的未来日期取数网格、次日窗口及“晴象转无雨标签”都是明确的研究操作定义，不冒称原典唯一法。固定基线为始终有雨及始终无雨；保留全部日期、弃权和缺失，不因阶段命中率好看提前停止。单站连续日期有相关性，不包装成365个独立主体。计算账本已逐行复跑，现实预测仍未通过验收。

账本最初为本地未封存记录，现另有外部时间见证：[FreeTSA](https://www.freetsa.org/index_en.php)于2026-10-21 21:03:44 UTC签署原清单摘要，早于首个目标窗口。只提交摘要请求，原模型、方案、标签和原压缩包均保持不变。解压后已复核消息摘要、nonce、服务公开且已固定指纹的CA证书链及目标窗口先后顺序，篡改清单验证失败。此凭证不等于公共科研注册、独立结果判定、操作系统信任库认可或预测效果认证；原方案的本地未封存状态文字作为历史内容保留。

### 固定旧政策的历史负结果

2025年完整回测使用此前固定的旧基础配置1.0.0、解释政策和次日雨量至少0.1毫米目标，在下载观测CSV前保存全年预测及证据哈希。它是历史回测，不是前瞻预注册；没有用这批结果调阈值、更换日期或修改旧政策。2026–2027未来账本保持原样，研究按原已发向量和原政策身份解释，不用当前预测重算历史标签。

| 指标 | 固定旧政策 | 固定基线 |
| --- | --- | --- |
| 非弃权的同一209日 | 128日正确，61.24% | 始终无雨134日正确，64.11%；始终有雨75日正确，35.89% |
| 完整365日 | 156次弃权，209次作出标签 | 始终无雨232日正确；始终有雨133日正确 |
| 观测完整性 | 365日均有可判定观测，其中53日为Trace区间 | 不把Trace伪造为实测0，不删除弃权 |

这套研究组合未胜过两个固定基线中的较好者。结果只覆盖该旧版规则、解释映射与窗口组合；当前制约组件仍无独立预测效力验收，不把新增条款宣称为已提高现实命中率。天气结果的 `research_validation` 会披露此负结果、所测旧版指纹和范围。

原始CSV及数据字典均保存哈希。数据文件本身注明Trace小于0.05毫米，因此在已固定0.1毫米阈值下可判为无雨标签，实测数值仍为 `null`。全历史CSV还含1900-02-29缺失占位行；它在已固定2025年队列之外，未移除任何有效2025日期，队列年份内的非法日期仍报错。日界依据[香港天文台2024年出版物](https://www.hko.gov.hk/en/publica/tc/tc2024/section1.html)的香港时间午夜定义，报告明确标为跨文档推断。单站连续观测不使用独立伯努利置信区间。解压复跑记录验证原365次计算、固定标签和完整评估报告一致。

### 原365日前瞻账本的验真与结果接入

[接入器](../src/fatebridge/validation/meihua_weather_prospective.py)核对原2026-11-01至2027-10-31账本、政策文档、365条已发预测和证据绑定，并用OpenSSL验证FreeTSA RFC 3161签名、nonce及清单摘要。原时间戳为2026-10-21 21:03:44 UTC，早于目标窗口；70次有雨、141次无雨、154次弃权保持原值，不用当前引擎重算，也不追补原先不存在的逐条方案哈希。

原方案只允许在**2027-11-30 00:00香港时间之后做一次结果分析**。此前只核对账本、窗口及不透明结果字节的哈希，不解析雨量或评分；伪填未来`--as-of`不能提前开启真实数据分析。明确标为`synthetic`的未来时钟测试单列为合成重放。离线读取器不能认证系统时钟、来源或跨运行的一次分析纪律，需另存操作记录与独立复核。

结果接入使用[香港天文台日雨量CSV](https://data.gov.hk/en-data/dataset/hk-hko-rss-daily-total-rainfall)及含`source_url/retrieved_at/body_sha256/data_kind`的来源回执。资料按月更新，窗口结束不代表数据已公布；按[数据字典](https://data.weather.gov.hk/weatherAPI/doc/data_dictionary_daily_total_rainfall.pdf)处理C、#、***完整性标记。全部365日保留，缺失和不可判定不补零，Trace沿用源文件的小于0.05毫米区间。哈希相符只证明内容一致。

```bash
uv run --locked --extra dev python -m scripts.meihua.audit_meihua_weather_prospective --study /path/to/original-study --attestation /path/to/original-attestation --output /tmp/meihua-prospective-readiness.json
```

验签需要支持`-attime`和`-check_ss_sig`的`openssl ts`；可用`--openssl /path/to/openssl`或Python的`openssl_binary`选择，否则使用PATH。入口保留两次完整验签及程序身份记录，不删必需选项或自动换程序。使用固定FreeTSA根证书与TSA证书，在已签时间验签，未查吊销状态。时间戳只证明所绑定字节已存在，不认证科学注册、原典或预测效力；未新增REST/MCP工具。

### 1.5.0政策的完整年度检验

2024年追加回顾使用固定1.5.0政策的35条规则，以前一民用日香港午时取数，检验次日雨量至少0.1毫米。只给资格明确且无相反候选的晴雨象分类；其他状态弃权，不补季节、“多”的阈值或前期天气。全年366日及闰日保留。

| 指标 | 1.5.0与固定解释政策 | 固定基线 |
| --- | --- | --- |
| 非弃权的同一29日 | 均标无雨，16日正确，55.17% | 始终无雨亦16日正确；始终有雨13日正确 |
| 全366日主终点 | 正确贡献16，弃权337，未通过 | 始终无雨214日正确；始终有雨152日正确 |
| 完整性 | 366日观测可判定，12个月均报告 | 缺失和弃权不移出主终点分母 |

方案、政策、日期网格与终点在本批标签及观测连接前固定，但设计时已知旧2025负结果，2024观测也已在此前下载的CSV中，故不属于盲验或独立留出。16/366是全队列正确贡献比例，不能当作非弃权命中率。`research_validation.additional_profile_audits`分别披露本次范围、旧2025结果与原未来账本，不跨政策合并。

### 1.7.0的完整日期降雨检验

当前规则的范围感知研究使用固定 `meihua_weather_v1@1.7.0` 与 `qualified_scope_aware_daily_rain_clear_v3@1.0.0`。主队列预先选定2026-01-01至2026-09-30全部273天，2024与2025全年另列回顾。两种情形分别提供按起卦日实际节月映射的季节，或保持季节未知；仍不补久雨久晴和“多”的门槛。1,004个目标日期产生2,008份情形记录，不能算作2,008个独立观测。

研究在前一民用日香港时间午时取数，将所选原文时段暂配至次日，并以日总雨量至少0.1毫米为目标。这是明确的研究桥接，原典和引擎都没有据此给出实际日期。未定时段晴象转无雨仍属假设；朝晴、暮雨可以在同一日共存，朝晴不能直接转成全天无雨。v3保留这个差别，旧v2仍只接受其固定1.5.0轨迹。未映射的变动天气、止雨与雪及其待定条件保持弃权，不按已知雨量挑条款。

| 队列 | 季节资料 | 全部日期 | 有类别标签 | 正确 | 弃权 | 全队列始终无雨正确 |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 2026年1—9月（主检验） | 按节月明示 | 273 | 49 | 29 | 224 | 158 |
| 同一2026队列（敏感性） | 未提供 | 273 | 21 | 13 | 252 | 158 |
| 2024全年 | 按节月明示 | 366 | 63 | 33 | 303 | 214 |
| 2024全年 | 未提供 | 366 | 29 | 16 | 337 | 214 |
| 2025全年 | 按节月明示 | 365 | 61 | 40 | 304 | 232 |
| 2025全年 | 未提供 | 365 | 28 | 21 | 337 | 232 |

六组全部未胜固定基线。主检验的29/49只是非弃权标签中的正确比例；主终点按全273天记正确贡献29，对比始终无雨158，未通过。各组有类别标签全部为无雨，同日始终无雨也得到相同正确数。提高覆盖或出现较高子集比例不能据此宣称有预测优势。

方案、24个逻辑探针及全部日期在实现政策和评分前固定，2,008份标签在接入本次观测文件前封存。但全历史CSV此前已下载，当前官方链接在锁定前的资料核查中也已打开，结果早已公开；本检验是追加回顾，不能称盲验、独立留出集或前瞻通过。本次下载与此前固定CSV哈希相同，原旧报告及未来账本保持不变。完整旗标、Trace区间、缺失与日界按既有评估器处理；1,004日均有可判定观测。

全部1,004个起卦日期另对照固定香港天文台历表的8项农历与取数种子字段，0差异；不扩张为所有瞬间、太阳时精度或节月映射的唯一原典依据。午时队列没有命中明确朝暮条款，因此不能用这组现实结果认证朝暮细节。新增公开 `research_validation.current_profile_study` 保留当前1.7.0的独立记录，旧1.0.0、1.5.0结果继续分别显示，禁止跨情形、年份或版本拼接命中率。新增实际前瞻观测及独立模型调用仍为0。

### 固定预测向量的可达评分上限

在投入新的观测队列前，先检查固定模型在既定主终点下是否有可能胜过基线。对完整的 N 日预测，记有雨标签 R 次、无雨标签 D 次、弃权 A 次；弃权没有正确贡献，两个常量基线均覆盖全队列。即使允许所有可能的二元真实天气组合，模型相对较好常量基线的最大正确贡献差仍只有 `min(R, D, R + D - ceil(N / 2))`。这是该完整固定向量的精确上限，不是准确率、成功概率或原典规则。

上述273日主队列为0次有雨、49次无雨、224次弃权，模型至多得到49次正确贡献，而较好常量至少有137次，最大差为−88。因此，这个固定向量在任何完整二元观测下都无法通过原主终点；实际29对158的负结果保持原值。`research_validation.current_profile_study.primary_attainable_skill_bound` 披露该条件性结论；研究元数据版本为1.6.0，所测天气规则仍为1.7.0，两种版本各有所指。

另对2026-11-01至2027-10-31的365日作了无目标观测的容量诊断：沿用前一民用日午时、明示节月季节、不补久雨久晴或“多”阈值，当前规则／v3政策给出0次有雨、64次无雨、301次弃权，最大差为−119。它是计算网格，**没有启动新的确认性前瞻试验，也没有获取未来观测**。旧1.0.0未来账本的70次有雨、141次无雨、154次弃权保持原样；在同一全队列终点下其理论最大差为28，表示某些假设观测可能通过，不能证明它会通过或已具有效力。

午时数为7，上下卦取数相差7；模8与模6的共同周期使固定午时最多覆盖24种本卦／动爻几何。365日实际覆盖这24种；按四季逐一核对的96种条件只有17种无雨、79种弃权，本、互、变均未出现旅卦，因而无法检验对应朝晴暮雨条款。12个时支的算术组合上限为192种，已有卦入口则可提供384种；这些是取数几何和软件条件，不是独立现实观测。缺少条件造成的弃权不能靠临时换起卦时刻、改晴雨映射或选有利日期消除。

审计入口为 `uv run --locked --extra dev python -m scripts.meihua.audit_meihua_weather_feasibility --vector <固定向量.json> --expected-sha256 <事先保存的SHA-256>`。输入必须列出完整唯一队列和每项标签，缺项、重复JSON键、未知标签及指纹不符均拒绝。文件指纹核对不能单独认证预注册时间或研究来源；精确上限的固定材料（本地数据：`../tests/fixtures/meihua_weather_feasibility_v1/manifest.json`）包含实现前的独立穷举及旧主队列标签，均保留。

### 固定午时研究的符号状态事前检查

```bash
uv run --locked --extra dev python -m pytest -q tests/meihua/test_meihua_weather_reachability.py
```

检查固定1.7.0规则与v3标签政策，不读取降雨观测或用引擎附带的旧摘要决定标签。年月日和S加24保持模8／模6图式不变；完整枚举12时支×24余数、未知及四季，共288组取数、1,440组解释，前期天气和“多”阈值保持未知。这是实际日历输入的超集，符号可达不能证明已有实际日期或预测成功。

午时120组状态全部为dry或abstain，并保留拒绝rain的逐项证书。因dry的正确贡献均属于同日期always_dry，在原全队列终点下不可能严格胜过这一基线；结论只约束该版本、政策与条件域。所有时支按原顺序报告，不按历史结果选时；旧1.0.0未来账本及273日29对158的失败保持独立。

领域测试逐项核对完整队列和午时结构性失败；通过只表示事实与反例得到保留，不表示预测门槛通过。完整报告可由 `fatebridge.validation.meihua_weather_reachability.audit_time_weather_reachability()` 取得。诊断已知旧负结果，不属于盲验，也未新增公共预测工具。

### 相同旧标签的天气参考基线补充

补充诊断保留原2,008份标签、1,004个日期及273日主终点，不重算卦象。参照采用[香港天文台检验论文](https://www.hko.gov.hk/tc/publica/reprint/files/r829.pdf)所述持续性思路，以及[1991—2020常年值](https://www.hko.gov.hk/en/cis/normal/1991_2020/normals.htm)的固定月度多数类；不复刻完整官方业务评分。10,958个训练日均保留，12个月平均雨日数与官方表2的公布精度一致；缺测不删除，半数相等保持待定。

起卦时是目标日前一天中午，持续性只能取当时最近已完整结束的一天，即目标日前两天。窗口结束、声明发布时间和实际可得性分别核对，不以日期标签或下载时间充当历史发布证据。

| 同一完整日期队列 | 旧梅花主情形正确贡献 | 始终无雨 | 最近完整日持续性 | 固定月度参照 |
| --- | ---: | ---: | ---: | ---: |
| 2026年1—9月，273日 | 29 | 158 | 183 | 190 |
| 2024全年，366日 | 33 | 214 | 250 | 252 |
| 2025全年，365日 | 40 | 232 | 223 | 260 |

两项参照均以已保存历史数值为条件，历史发布时间证据下可确认可用日期均为0，`operational_superiority_gate=null`；未知不能按0分处理。同一49个主情形类别日期上，两参照各正确31次、旧标签29次。六种年份／季节情形全部报告，包括2025持续性低于始终无雨，不据结果更换主终点。`research_validation.reference_baseline_supplement`保留这些条件；本补充不是新模型或前瞻通过，也未检验天空晴况、朝暮实况及“久”的时长。

### 完整日期参考与运行条件

全支持区间的固定对照范围为1900-01-01至2100-12-31，共73,414个唯一民用日期。原子队列保留1901-01-01至2100-02-08的72,723日，不因扩展覆盖而改变其分母；1900年365日另查臺北市立天文科學教育館印表，并分别运行固定UTC+08:00和Asia/Shanghai；2100年尾段另查326日。合计73,779次调用含时区重复，不是同等数量的独立日期或现实占验。年度来源共201份，其中生产也摄入同一香港天文台出版物的2100年尾段只证明忠实摄入，不能当作独立天文验证。

```bash
uv run --locked --extra dev python -m pytest -q tests/meihua/test_meihua_calendar.py
```

审计以所选时区的民用正午取数。相同正午时支只有有限的不同卦图组合，完整日期对照不能扩大为所有时辰、所有时区、全部384种单爻变化或全原典符合性。香港天文台关于2057-09-28、2089-09-04、2097-08-07新月日期可能相差一日的说明仍保留；公布历表标签相同不等于未来物理时刻已获分钟级认证。

四个历法审计入口现以[包级源码检查](../src/fatebridge/validation/meihua_source_guard.py)记录开始与结束的软件包文件及随包资源，排除字节码和缓存。检查拒绝内容修改、删除和新增，大小及时间戳相同也不能掩盖字节变化。它只检查两次读取时的磁盘内容，仍应在新进程与稳定快照中运行；不证明任意热更新、进程已加载代码、外部依赖或原生星历资源全部一致。包级范围比所用依赖更宽，其他模块的并行改动也可能使审计失效，不应靠删去不匹配日期或缩小源文件清单求通过。

历表核对、独立公式、事实路径及守卫故障注入分别报告。这些检查不是实际模型解释评分或现实预测有效性认证。

#### 固定星历资源后再比较历法

源码相同不保证 `auto` 模式使用相同太阳模型。`ephe/`位于包外，实际原生文件、环境配置和调用标志共同决定数值模型。2026年24个节气的交叉控制显示所选资源会改变时刻，原有模型分离和严格时刻差异保留。该控制只说明所测差异的来源，不证明哪种模型有绝对物理精度。

四个历法审计入口现在还返回 `runtime_input_guard`，在前后检查有效搜索路径的指纹、已配置星历文件、太阳策略、已加载时钟表与原生绑定文件。显式原生JPL配置也记录所选文件名及可见文件内容指纹。`swe_deltat.txt`及兼容的`sedeltat.txt`都纳入资源清单，年节气缓存键也跟踪两种名称；Unix分号搜索路径不能当作单一文件夹。受控原生调用已证实 ΔT 表可改变换算结果，不能只凭源码和 `.se1` 文件认定运行环境相同。

比较须固定计算时使用的星历资源、库版本及策略，并在新进程中核对实际结果所报模型。缓存键失效不证明 C 库已经重读了修改后的辅助文件。`runtime_input_guard`是配置输入在两个检查点间保持一致的检查，不是原生原子读取清单、内存代码鉴定或天文精度证书；部分未选择的可选模型也不能据此称为已验收。历表日标签、节气的日期或时刻、卦象及旺衰分别验证，不以它们通过替代现实预测验证。

节气对照报告保留4800条官方日期的7处差异，并给出4826个候选事件的外部TT位置对照及6个模型分离整分钟输入。共享DE440与原生模型分别报告；固定参考比较不认证全部输入或现实预测。

#### 节气秒级比较与分钟标签

[紫金山天文台对农历国家标准的解读](https://pmo.cas.cn/xwdt2019/kpdt2019/202203/P020240201504886119982.pdf)指出，1900—2100年用于日界判定的朔、节气时刻须达到1秒精度，并说明尚未公布闰秒的处理。只比较官方年表的日期或分钟显示，不能验证这一精度，也不能省略朔、置闰和钟时的其他检查。

新增审计入口要求事先保存参考文件的SHA-256，完整比较1900—2100年全部4,824个节气；缺项、重复ID、重复JSON键、非有限TT值及指纹变化均拒绝。退出码0仅表示对所给参考满足固定的1秒TT差值门槛，退出码1保留所有超限项。文件指纹和参考自报来源不能单独认证其独立性。

```bash
uv run --locked --extra dev python -m scripts.meihua.audit_meihua_solar_seconds --reference tests/fixtures/meihua_solar_seconds_v1/reference-2000a.json --expected-sha256 45dd2ab73b54e5d3a4cdbd6b00501180d0f1eb291a8264b9c473dca914ba0e37 --output audit-solar-seconds.json
```

固定副本的DE440输出与独立IAU 2006/2000A实现比较，4,824项最大相差约0.0631秒，均在原门槛内；原审计中原版 Swiss Moshier、空外部星历目录的对照有494项超限，最大约2.094秒。两份实现共享DE440动力学来源，不能由软件相符推导绝对民用钟时精度。TT、UT1、UTC以及历史／未来换算条件分别保留，原有7处香港天文台日标签分歧仍未消除。

国立天文台原始分钟表中的 `1979/01/20 24:00` 作为当日结束的显示保留，可规范化为次日零时的**名义显示值**，不据此认定实际交节已经越过午夜。其分钟舍入规则未获认证，不能自行补出±30秒误差区间或1秒合格结论。材料、三种模型的实际范围及1936年雨水附近的三次时间入口核对见秒级审计记录。该范围没有改写生产节气算法或天气政策，也没有新增现实预测结果。

### 已发天气向量与负结果

原2,008条预测、1,004个目标日期、13,057条观测及政策身份保存在`tests/data/meihua/weather_evidence`。核验读取原向量、原观测和决策事实，不执行退役源码或重建历史标签；[完整日期检验](#170的完整日期降雨检验)中的273日正确贡献29、基线158、差值−129和非盲回顾限制保持原值。

### 天气研究的官方农历日期标签绑定

`fatebridge.validation.meihua_weather_calendar_binding.calendar_bound_weather_label(record)`在原演算绑定外，分别核对`calendar_actual/calendar_expected`的`year/month/day/is_leap_month`及日期政策。两份字段相同不代表正确：共同改成相隔12年的年份或共同改错闰标志仍可能保留卦象，核验必须拒绝。

参考从HKO2022—2026中英文原始年表提取，先固定原文件、哈希、1,826行双语对照和10个字面锚点，不由生产库生成。闰月同时核对中文閏字；前两日缺前置月首锚点，支持范围为2022-01-03至2026-12-31的1,824日。整数农历年按研究春节换年政策派生，不冒充逐格印刷值。

原1,004个起卦日（2023-12-31至2026-09-29）在两情形的2,008份记录中均吻合；不以次日目标日期代替，不重复计算独立样本，未读天气结果。旧农历／演算报告、标签、失败和未来账本保留。`published_lunar_date_binding`只认证公布标签与所选政策；`calendar_labels_independently_authenticated=false`仍保留，UTC瞬间、节月、发布时间和天文精度未获此认证，同出版者双语也不是两次独立观测。

```bash
uv run --locked --extra dev python -m scripts.meihua.audit_meihua_weather_study --check calendar --study /path/to/frozen-study --output /tmp/new-calendar-binding-receipt.json
```

输出须为研究目录外的新文件，保留已有回执与输入。

### 天气研究的交节时分与节月标签绑定

工程入口 `scripts/meihua/audit_meihua_weather_study.py --check solar --study <原完整研究目录> --output <研究目录外的新文件>` 在原农历／机械核验之上，另用冻结的HKO2022—2027二十四节气XML刊载时分核对起卦节月及原研究季节声明。144条原始时分、60项同出版者年历中气对照和取名顺序先固定；不调用生产历法生成预期。

刊载分钟未找到明确取整规则。输入按完整民用分钟处理，刊载时分两侧各60秒是明示的软件守卫，非官方置信区间或真实误差界；整分钟须在两个相邻节气守卫外，交界未定和首尾范围外均保留。按原研究寅卯辰春等四季约定，未提供季节的情形仍不补值，不替换成旺衰层土月划分。独立研究约定不冒充原典唯一法。

原2008份记录、1004个起卦日均吻合，原完整农历／演算报告及标签不变；未读取现实天气结果。另对照144个实际DE440交节时刻，最近整分钟表示均相同，最大距刊载分钟中心约29.76秒；这不认证未刊秒数或覆盖原4800日期门的存档差异。见审查。

### 固定午时政策补前提后的容量限制

工程入口 `scripts/meihua/audit_meihua_weather_study.py --check context-capacity --study <原完整研究目录> --output <研究目录外新文件>` 穷举固定午时1.7.0/v3政策的24种取数余数、120种现有声明组合，保留2880条符号状态及全部六个原队列／情形组。它只分析可能输出的标签，没有取得前期资料或现实结果。

即使允许每一天任意选现有前期条件和多字阈值，原273日主队列最多77日可分类；较好常量基线在任何完整二元真值下至少正确137日，最乐观贡献差仍为−60。原默认向量的−88上限保持。不能通过补声明、按结果调阈值或删除弃权使这一固定政策胜出；这不排除其他有来源的新方法，也不取消其他版本原365日前瞻计划。

`--require-primary-potential-superiority`的实际失败退出2保留完整报告。逐日任挑条件只用于放宽后的数学上限，不是可采用的预测方法。公式、事前固定的125组独立小样本穷举、原2880轨迹及保留失败见审查。

## 运行与验收

### 可复现验收

原始资料与独立期望保留在 `tests/fixtures/` 和 `tests/data/`。当前测试直接核对取数、几何、来源文字和未决条件，不加载退役实现，也不由当前计算结果重写预期。

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q tests/meihua
```

| 验收轴 | 本次证据与界限 |
| --- | --- |
| 历法 | 当前完整日期审计覆盖1900-01-01至2100-12-31全部73,414个民用日期，所比历表字段0差异。原72,723日基准分母保留，另列1900年365日与2100年326日补段；后者为生产和参考共用HKO出版物的读取检验。限定所列时区正午和字段，远期朔日披露已知不确定性，不扩张为所有瞬间或天文精度认证 |
| 指定原典 | 时间法两则、显式法九则原文演算，天时40项读法及三条跨章制约；三季节句按固定转录保留版本异文，一句朝暮分两时段且不补钟时。另有选段校读、物数探针、64卦图与384次单爻变化。未宣称全书或所有术家规则通过 |
| 解释忠实 | 关系、事实路径和制约资格逐项核对，原文、现代提示与假设爻分开；REST/MCP/CLI包含严格字段投影的结果对齐。真实模型自由文本尚未完成独立语义验收 |
| 现实预测 | 各旧政策回顾结果分别保留；1.7.0主队列全273日正确贡献29，对比始终无雨158，主终点未通过。固定向量的理论最大差−88，另365日无观测容量诊断最大差−119，均限所列输入、政策及终点。前瞻实际观测仍为0，不作权威认证 |

人工初版坤卦探针曾把体互与用互对调；更正记录保存在冻结的 `adjudications.json`，保留原值、逐爻推导及原文依据，没有为匹配程序修改算法。扩展历法验证时完整纳入200个年度，没有按匹配率选择年份。

1900年支持日期另有独立公布历表；当前日期范围和分母见上表。臺北市立天文科學教育館[原始发布页](https://tam.gov.taipei/News_Content.aspx?n=2D5F18609004C0CE&s=AC19298B0509F078&sms=3AABB000A3E78431)、PDF、365个印刷单元格和人工目验锚点先冻结，再与生产计算比较；不由生产算法反向生成预期。1900年另核对固定 `UTC+08:00` 与 `Asia/Shanghai`，两个时区仍只计335个独有日期，起卦年支、月日、午时支均一致。1900年底农历十一月初十与香港历表1901年初的十一连续；原有支持起止日期保持不变。这个结果补齐日期标签的证据缺口，该范围没有因此改写历法算法，也不扩张为历法所有细节或预测效力满分。

尚未完成物数超八和单组声音计数口径的唯一裁定、自动现场取象、自动音韵或字形取画、完整外应、精确事件应期及全书分类占断；原八个人事题篇分别保留原四章20条、出行／谒见10条、失物5条及行人5条；另支持家宅/屋舍十个文字分支，其中家宅比利的关系条件未裁定，另列求财成分、出行偏好、失物8卦方位类象、行人初用受生受克及外应资格。出行多字、舟陆等角色范围及末句主语仍未裁定，未完成全章综合；天时层仅覆盖所列条件条款。卷三存在「觀梅恒卦」等疑似讹误，不能用程序结果反向校改原文消除分歧。

现实预测后续使用现有 `fatebridge.validation.predictions` 和 `scripts/evaluation/audit_prediction_study.py`：先固定可观察事件、时间窗、模型与解释政策、队列和基线；在事件窗口前记录预测，再独立判定结果。缺失、弃权及未随访必须保留，开发集与最终验收分开；不能从卦象关系生成假结果、事后改问题或只展示命中例。即使有限样本全对，也不能据此证明总体100%或最权威。
