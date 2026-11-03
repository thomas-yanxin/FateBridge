# 河洛理数与邵子参评数：计算口径与使用

`heluo` 提供河洛本命卦与时运，`canping` 提供参评取数及具名配运方法。两者的取数、年代、原典与时间映射分别核对，不把河洛本命卦、皇极经世、铁板数和金锁银匙统称为一个已认证体系。

[文档中心](README.md) · [调用合同](contracts/README.md) · [可选太阳后端](solar-backends.md)

原典只覆盖指定底本的已读段落。逐爻解说、诗诀、疑字、引用卦爻与正式后天盘分别返回；未核内容保留待核，不按已核比例推定全书符合。参评时间线保持120条年序；具现代立春映射的方法保留121个边界，其他方法不补造未知的 UTC 映射。

民用钟时须结合地区时区与必要的明确偏移；重复钟时的两种瞬间不能互换。DE440／VSOP2013 的有限 TT 网格按原1秒线报告，原生12个超差及历史失败继续保留。历法、原典、解释与现实预测各自验收，不因来源修复改判其他层。

逐轮运行成绩、原始反例、诗诀／爻段覆盖增量及旧英文报告见[历史记录](https://github.com/thomas-yanxin/FateBridge/blob/73ec8912677b2b687a4b11ccb06727332296e8e1/docs/numerology-audit.md)与[历史英文报告](https://github.com/thomas-yanxin/FateBridge/blob/73ec8912677b2b687a4b11ccb06727332296e8e1/docs/numerology-audit.en.md)。以下对照表及复核记录仅适用于其具名版本。

## 调用

```bash
uv sync --locked --extra dev

uv run --locked --extra dev fatebridge heluo \
  --date 2026-06-21 --time 16:30:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false --response-char-limit 0

uv run --locked --extra dev fatebridge canping \
  --date 1990-06-15 --time 09:33:00 --zone Asia/Shanghai \
  --gender 男 --method gu --use-true-solar-time false \
  --fields benming numerology_evidence --strict-fields true \
  --include-snapshot-text false --response-char-limit 0

uv run --locked --extra dev fatebridge heluo \
  --date 1990-06-15 --time 09:33:00 --zone Asia/Shanghai \
  --gender 男 --use-true-solar-time false --analysis-year 2028 \
  --month-index 3 --day-index 10 \
  --fields heluo_timing.selected_annual heluo_timing.selected_month \
    heluo_timing.selected_day heluo_timing.selected_texts heluo_timing.calendar_policy \
  --strict-fields true --response-char-limit 0

uv run --locked --extra dev fatebridge canping \
  --date 2026-02-06 --time 04:02:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false \
  --dayun-method bazi_appendix_v1 \
  --analysis-datetime 2037-02-06T04:02:00+08:00 \
  --fields canping_timing numerology_evidence.selected_texts \
  --strict-fields true --include-snapshot-text false --response-char-limit 0

uv run --locked --extra dev fatebridge heluo \
  --date 2026-02-10 --time 12:00:00 --zone Asia/Shanghai \
  --gender 女 --use-true-solar-time false \
  --fields chart.tian chart.di judge.seasonal_numbers \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

示例为虚构测试输入。`--use-true-solar-time false` 是显式选择；使用默认真太阳时应提供实际经度。REST 路径仍为 `/api/divination/heluo`、`/api/divination/canping`，MCP 工具名仍为 `heluo`、`canping`；请求与输出模型由同一工具目录发布。

两工具均须明确 `gender`，不能默认男命。河洛已知中英文性别别名归一化；缺失、未知或拼写错误直接报错，因为性别影响命卦和元堂。

两工具的 `time` 也必须是已知的当地钟时，空白、未知与夹带时区的字符串会拒绝；时区单独放 `zone`，显式 `00:00` 有效。`judge.deTime` 仅为卦属月匹配，另述窗口、来源及未决边界见 `judge.month_affinity`；其中月号暂按四柱月支解释，不等于农历月或精确节气区间。

真太阳时默认开启，须提供明确经度`lon`或数值`gps_lon`，0°有效；缺经度不再用上海缺省值。只在用户选择钟表时时明确传`use_true_solar_time=false`，不为绕过错误自动改换钟制。两工具的`birth_clock`视图可核对实际输入来源与所用钟面。

解释时先使用 `rule_trace` 和实际选中条文。`selected_texts` 仍可能同时包含葉者、不葉者、岁运等分支；现阶段没有完整综合判断，不能挑最有利的一段充当确定结论。

上面的 `month-index 3 / day-index 10` 是原典序号，不是3月10日。缺父级选择、超过卦序范围或无效序号会报错，不回退当前年或最后一步大运。完整年序位于 `heluo_timing.annual_rows`，月序位于 `monthly_rows`，日定式位于 `daily_template`；大结果按同次交付机制读取。

## 来源及版本限制

- [《河洛理數》卷一，识典古籍转录](https://www.shidianguji.com/book/NA09030/chapter/1m8od60nhc1me)：取数、五寄宫、元堂、后天卦、化工。正文有明显 OCR 错字和混排，例如第一例总数转录与分项运算不一致；参考夹具保留手算方法说明，未声称影印逐字校勘完成。
- [卷六转录](https://www.shidianguji.com/zh/book/NA09030/chapter/1m8od6rwizt4b)：金锁银匙五行算例，以及大运替时、流年用太岁与大运支的规则。金部明确给出同支十三位，可独立定位移植错误。
- [日本国立公文书馆卷四至七影印](https://www.digital.archives.go.jp/DAS/contents/pdf/lossy/03050271000050/0001.pdf)：核读PDF第50、105、106页，保存三张原页及散列。卷七把附入的子平运法与河洛六九年卦运明确区分；卷六的配运段落未唯一指定采用哪套时间轴。[馆藏目录](https://www.digital.archives.go.jp/file/3611497)记载明刊／清印，具体印年未定。
- [国家图书馆藏本影印 PDF 的公开镜像](https://upload.wikimedia.org/wikipedia/commons/4/4a/NLC416-13jh000625-42999_%E6%B2%B3%E6%B4%9B%E7%90%86%E6%95%B8.pdf)：提供后续底本校勘入口；本次未完成整本图像核读。
- [日本国立天文台 2026 年暦要項](https://eco.mtk.nao.ac.jp/koyomi/yoko/2026/rekiyou262.html)：24 节气时刻，原表为日本标准时 UTC+9，测试按绝对时刻比较。
- [中央研究院中国文哲研究所维护的《参评秘诀金锁银匙歌》馆藏记录](https://hannom.openmuseum.tw/muse/digi_object/c814fd85d043d6e38fbb7ca4723db287)：该抄本记录编者不详。它是另一文献记录，不能据此确认本系统条文全部出自邵雍。

`numerology_evidence.selected_texts` 中河洛条文按 `text_provenance` 分开报告爻辞、注文与诗歌状态；九卦54条爻辞按指定影印目校，其余330条仍待校，独立复核尚未完成。`corpus_sha256` 仅标识继承语料，`yaoci_collation.sha256` 标识局部校勘层，旧文与页码随所用条目保存。另附已有周易语料中的同卦同爻经文、修订号和散列作为参照；它不替代河洛版本校勘。散列只能证明内容身份，不能证明内容正确。

土用目前明确采用“四立前十八个连续日、左闭右开”的计算约定。卷一季月十八日的计日法、不同底本及纯卦阴阳令与其他月令术语的差异需继续核对，不能把工程边界测试当作版本争议已经解决。

## 规则与时间口径

1. **交节时刻**：原服务按生日零点取化工，又用月支近似冬夏半年；现在以出生民用时刻代表的绝对瞬间判断节气及至点。真太阳时仍可调整四柱日时，不用调整后的墙钟重新判断太阳交节。
2. **三元五寄宫**：由弘治十七年甲子（1504）上元起，六十年一元、180 年循环；2044 年回到上元。公历一月仍属于上一个干支年时，用该干支年确定寄宫。
3. **天地数归卦**：超过正数时只减一次 25／30，再按原文去十取零；不反复作模运算。例如天数 55 减 25 得 30，取 3，旧循环算法会得到 5。该扩展用例是规则推演，区别于书中四组现成算例。
4. **参评数同支**：卷六金部的申日申时例绕行一周，连首尾计十三位，结果 3322。旧实现顺数为一位，误得 2122；现在顺逆均为十三位。其余非同支按顺逆各自的包含首尾计数。
5. **默认方法**：`canping.method` 从 `ming` 改为 `gu`。`gu` 使用真实日支，符合卷六该段不用月令的规则；显式 `ming` 保留月支反向变法，输出说明其与该段原典不同。未知方法直接拒绝，避免拼写错误静默换流派。
6. **后天卦与纳甲**：后天卦包含明确上下卦，先后天均参与匹配。第三轮进一步改为实际六爻纳甲，并纳入乾坤借用，修正旧的上下纯卦全表合并造成的误报及借用漏报。五卦原页已核对，其余按规则推演；不代替完整得势判断。
7. **参评长时间线**：先修复91–120岁钳制，第四轮再移除默认固定一岁起运和命宫顺排。默认 `bazi_appendix_v1` 明确选用卷七附子平法的月柱顺逆、三日一岁及余日借除；连续折算另列 `bazi_continuous_v1`，旧方法须显式 `legacy_minggong_v1`。卷六未唯一指定配运法，民用日计数、生日加整年和立春年界均作为具名实现约定。120行是年序覆盖范围，绝非寿命预测。
8. **解释边界**：简化 `judge.xie` 只表示元气或化工命中。快照不再据此宣布综合葉否；天地数“有余／不足”只与25／30比较，相等称正数。`judge.seasonal_numbers` 另列至弱太过、十一数式和六个时令窗口；原文重叠不裁优先，得中数值条件为 `null`。缺条、空条和缺字标注语料状态，不据此断现实灾祸。

## 固定版本的对照范围

第三十九轮新增屯蒙十二爻完整注文核读，注文覆盖增至24／384、待校360；保留原页龍妾、掌無權等异读，八组草稿撤回不冒充继承错误。修复来源损坏被归为出生参数400的问题，标题／注文损坏返回不可重试503；实际选文、条件分支和同次散列一致，见第三十九轮核对（本地数据：`validation/heluo-tunmeng-commentary-audit.md`）。

第三十八轮核卷七附法起月、起时头干，修复固定四柱只验各柱合法、却接受柱间不相容组合的问题。两数新增同次`pillar_links`证据，采用实际所用年柱／日柱；原书一条庚午年戊戌月取数例与口诀冲突，原文和35／24算术保留，完整起命拒绝，不将其计为已验出生盘，见第三十八轮核对（本地数据：`validation/numerology-pillar-links-audit.md`）。

第三十七轮复原卷一渐卦四体八体结构，逐阶段公开三爻倒序、全卦倒序及抽第三爻移顶的原爻位映射。八条含六个三爻体与两个六爻卦，不能冒充八个互体合并纳音；其他卦的算子推演与一个原书结构例分开。五命干支字表另存，未自动选柱或统一改用纳音，见第三十七轮核对（本地数据：`validation/heluo-structure-audit.md`）。

第三十六轮将十体“有援”主本原句按实际阴元堂、阳应爻接入先后天证据，保留别本省“爻”的字面。通用阴阳相异与原句匹配分开，旧`youYing`明确仅先天，未匹配不推出无援或现实结果。复用两张原页及一张同页新区域，没有新增命例或第二审阅，见第三十六轮核对（本地数据：`validation/heluo-support-clause-audit.md`）。

第三十五轮按原页常数与发敛步骤补上三套来源辰刻归一，复核上轮两份计算的既有钟时题注，区分百刻、初刻零起点及子正源日。1206大雪为亥初一刻余，题注亥时完整区间跨交节，不能补一分钟选定月界；戌时或次源日等可确定的相对关系仍正常返回。新增两张图、复用四张见证，无新增出生命例或历史UTC，见第三十五轮核对（本地数据：`validation/heluo-song-clock-audit.md`）。

第三十四轮新增统天正文及梅文鼎三位躔差读法，复算两份原书计算工作表，保留两次半进舍入、前后皆减及次年重算冬至与逐气累加终点的差别。1206大雪推得十月廿八乙亥，原例丙子日和“大雪前一日”仍冲突；不改题注换取吻合，也未确定作者实际用历或历史钟时。十张整页、两份印本演算、五组推演和同一个旧例分别计数，见第三十四轮核对（本地数据：`validation/heluo-tongtian-audit.md`）。

第三十三轮据《钦定宋史》原页新增纪元、统元两套精确气朔算术组件，分开己卯／甲子起日与60／180细分分母；八行推演和同两旧例的四项日期比较分开计数。1150处暑次日可相容，1155初一白露仍差一日；史载历名与实际算法混用，不能按年份自动定派。当前公开四柱未切换，未核UTC；见第三十三轮核对（本地数据：`validation/heluo-song-qi-audit.md`）。

第三十二轮把四例的五种题注读法与历史历表和具名年号数据库交叉核对，保留三个纪日差异与绍兴三年／戊子的年干支冲突；日柱局部吻合不升级整例验收。两数公开输入、证据与快照明确推算格里历，不自动切换儒略历或转换历史阴历。宋代注历节气与现代太阳交节分别处理，新增已验证历史瞬间为0。见第三十二轮核对（本地数据：`validation/heluo-historical-calendar-audit.md`）。

第三十一轮补核五个纯卦的三十项正纳，八纯卦基础表全部覆盖；原有五个复卦观察与基础位置分开计数，不把六十四卦的软件应用称为逐卦原页核定。逐爻返回直接条目或纯卦内外位推演来源，计算表与源表冲突时拒绝；解卦两版列举次序问题继续保留。另登记震、艮、巽、兑四条月份／纳甲句，坎的及時不臆定月号。见第三十一轮核对（本地数据：`validation/heluo-najia-foundations-audit.md`）。

第三十轮修正未决附加条件在月号未中时被报为整条false的问题。九条原句分列月号与同阶段年命纳甲事实，及字连接范围、解卦例外与月界仍待核；新增离、井、涣十八项正纳核对，保留解卦列举次序差异，不增加命例或预测样本。见第三十轮核对（本地数据：`validation/heluo-najia-qualifiers-audit.md`）。

第二十九轮以三页原图复读土部三格疑文，3377女文首字可辨晝，两格末字仍未定；当前1123格字面确定、47格未决。字形与词义分开，3379现有檠／晝转录正确，撤回拟改而不虚构修订。另修复继承语料读取函数暴露可变缓存的问题，防止后续继承旧文与文件散列脱节，见第二十九轮核对（本地数据：`validation/canping-earth-rereading-audit.md`）。

第二十八轮复读金部15格旧正文疑读，4格确定、11格仍未决；保留麴蘖、追遊世的字面，3314时运只辨出花，其后仍为□，不抄同号女文补齐。当轮全表1122格确定、48格未决，金部223／11；旧水火木及编号见证保持，见第二十八轮核对（本地数据：`validation/canping-gold-rereading-audit.md`）。这是同一审阅者复读，不是独立复核或预测成绩。

第二十七轮复读木部四格旧正文疑读，三格确定、一格仍未决；保留撫手、玉藍、門帳字面，2519只辨出傾而继续保留后一字□，不升级整格。当轮全表1118格确定、52格未决，前两批复读及编号见证保持，见第二十七轮核对（本地数据：`validation/canping-wood-rereading-audit.md`）。

第二十六轮复读火部11格旧正文疑读，六格确定、五格仍未决；旧鴛□按原图修为蒼鷹，浩雲等少见字面保留，暗字可辨而末字仍方框的格不升级。当轮全表1115格确定、55格未决，旧水部见证与火部新批次分别保存，未覆盖历史或新增独立复核，见第二十六轮核对（本地数据：`validation/canping-fire-rereading-audit.md`）。

第二十五轮复查五页原坐标图像中的六个遮损／淡损编号，仍全部未定，十八格不升级；新增正文状态与编号归属的分层证据、公开字段类型及载入防护。已确定1109、未决61的计数不变，不将14格正文可读计成已确定格，见第二十五轮核对（本地数据：`validation/canping-header-evidence-audit.md`）。

第二十四轮从馆方IIIF公开原坐标区域复读水部原有40格疑读，30格读法确定、10格仍未决；保留初稿撤回、短句与少见读法，不依典故填字。全表1109／1170格确定、61格未决，新增编号格与独立复核数均为0；旧手录与复读修订分别保留，见第二十四轮核对（本地数据：`validation/canping-native-rereading-audit.md`）。

第二十三轮核读土部78行234格，231格确定、3格正文未决，复用旧三格、净新增228格。五部1170格均已单次目读，1079格确定、91格未决、0格未目读；新增状态分别报告目读覆盖完成与读法全部确认，后者仍为false，不代表全书符合或独立复核完成。修正“蚌內／虹內”等并恢复被补写圈空，见第二十三轮核对（本地数据：`validation/canping-earth-audit.md`）。

第二十二轮核读木部78行234格，218格读法及号文归属确定，16格未决；四行遮损编号下三栏全部保留未定。修正陌上箏／恒上箏、權衡／權行等差异，并恢复被补写的原页圈空；全表已确定851／1170格、88格未决、231格未目读。边界两页复用既有火金见证，不重复称新见证，见第二十二轮核对（本地数据：`validation/canping-wood-audit.md`）。


第二十一轮核读火部78行234格，217格读法及号文归属可确认，17格未决；其中2743、2248编号遮损，三栏六格全部保留暂定继承键归属，不因正文可读升级。全表已确定633／1170格，72格未决、465格未目读。修正孤舟／孫舟、亦難／難難等取文差异及补写圈空，快照区分正文与编号疑读，见第二十一轮核对（本地数据：`validation/canping-fire-audit.md`）。


第二十轮核读金部78行234格，219格读法确定、15格疑读继续待核；全表已确定420／1170格，另有55格疑读和695格未目读。末11行出现继承数据与所选底本的连续号文归属差异，按原页编号选文并保留继承旧文，计算编号不重映射；差异归因仍未定。新增逐部覆盖及整段原页夹具，未增加完整命例、独立历法时刻或现实结果，见第二十轮核对（本地数据：`validation/canping-gold-audit.md`）。


第十九轮据十体小注补上逐先后天实际元堂的二五君臣位、五同一异众宗式及爻位偏好。修复把通用位序阴阳比较直接称作原典“当位”的标签；旧布尔值保留为明确别名，原典阴月当位继续未知，不补成至点半年。未匹配正面式不推出反面断语，也不生成十体评分，见第十九轮核对（本地数据：`validation/heluo-line-conditions-audit.md`）。

第十八轮统一两数公开与领域入口的默认时区：省略／null均使用固定`+08:00`，不再在领域入口暗用历史`Asia/Shanghai`；空白与非法时区拒绝，显式地区时区保留历史规则。出生证据新增实际偏移、夏令时和规则库身份。1990年两次调钟的四个边界探针与同瞬间不同表示分开核对，来源访问限制及完整验收未通过状态保留，见第十八轮核对（本地数据：`validation/numerology-timezone-audit.md`）。

此次请求包括“历法正确、符合指定原典、解释忠于计算结果、能够预测现实”四项。第三轮新增逐爻纳甲修正、同次岁运摘要和香港天文台三年参考，见第三轮核对（本地数据：`validation/heluo-najia-audit.md`）；第四轮补上参评的具名配运方案和实际交运分段，见第四轮核对（本地数据：`validation/canping-timing-audit.md`）。机器报告继续分别保留 `three_dimension_acceptance_passed` 专业三项门与含现实验证的 `four_dimension_acceptance_passed`；两项均未通过，不能用其中一个替代另一个。

第五轮核读二数与时令十一页，新增十一种数式、六个节气窗口及同次解释，保留原文的数式和窗口重叠；正数相等不再称为季节得中，见第五轮核对（本地数据：`validation/heluo-seasonal-audit.md`）。

第六轮修复河洛性别缺失、拼写错误及女命别名可能走男命计算的问题；按影印PDF第119–141页加入九卦54条爻辞的局部校勘层，保留330条待校与单次目校待复核状态，见第六轮核对（本地数据：`validation/heluo-text-audit.md`）。

第七轮据底本修正睽、震、节的所属月份，十二项直接月表锚点与另述跨月窗口分开返回；乾卦八月边界与无妄宫世疑点保留。两工具不再将空时间补为零点，详见第七轮核对（本地数据：`validation/heluo-month-audit.md`）。

第八轮逐卦核读64卦总论，63项有明确所属月；另修正井卦由三月改为二月，保留后述三月与纳甲条件。21条额外月份条件区分离散、连续、跨年、季节、及时与失时；随卦正月冲突、颐卦九月边界和未决附加条件如实返回，同次快照分别说明。完整月界、无妄所属月、独立二次复核及综合判断仍待完成，见第八轮核对（本地数据：`validation/heluo-month-depth-audit.md`）。

第九轮互核NLC与日本国立公文书馆两种影印，将旧日干映射移至`judge.day_stem_mapping`；`judge.deTi`改为年纳音与先后天实际上下／互体的有向关系证据。第51页“无元气且卦体生纳音”与第87页双向相生分开，完整得体的`present=null`。此为公开输出迁移，未把局部关系层宣布为完整得体，见第九轮核对（本地数据：`validation/heluo-body-audit.md`）。

第十轮保存两版九张原页，新增四组完整四柱的步骤对照。原始地数33／30冲突、初二／初三异文和大雪前却用子月柱等问题保留，新增已核历史出生瞬间与真实预测结果均为0。修复阴阳令字符串真值、元堂负索引及卦名／爻形不一致可改变后天卦的问题，手工半年与实际至点来源分开，见第十轮核对（本地数据：`validation/heluo-worked-audit.md`）。

第十一轮按两版反化工原文补上春分至夏至同时成立的离、巽；新增`judge.qi_phases`，按先后天的实际上下／互体分别返回正反元气、化工与得失，旧聚合字段明确为并集。乙亥例“乾化工”与白露时节按定义取离的冲突保留，显式空候选不再静默退回月支近似，见第十一轮核对（本地数据：`validation/heluo-qi-audit.md`）。

第十二轮修复开启真太阳时却在缺经度时默用上海的问题。缺经度报错，钟表时未提供经度返回null；`numerology_evidence.birth_clock`分列同次民用时刻、UTC瞬间、计算钟面、经度来源与是否使用。复用四个独立JPL时刻核对两工具、两经度共16个钟面，最大差0.586433秒；不计作新原典命例或新独立时刻，见第十二轮核对（本地数据：`validation/numerology-clock-audit.md`）。

第十三轮按影印PDF119–124页逐条核读乾坤十二爻完整注文，修复错字及坤六四重复串文，保留本印本异文。注文分段保留葉／不葉、岁运和嵌套条件，未自动裁定适用性；诗歌未见于这些已核段落，来源待核，旧吉凶摘要也未获底本认证。标题和注文分别计数、散列与待复核，12条注文已目校、372条待校、诗歌0条已校，见第十三轮核对（本地数据：`validation/heluo-commentary-audit.md`）。

第十四轮据PDF26–32页核读元堂图式，修复固定四柱把整个子／午月定成单一阴阳令的问题：若两半年结果一致则保留唯一命卦与未知半年，若有分歧则要求明确半年；同时核后天卦，避免只看元堂相同。公开日期服务继续用实际至点，新增性别、配时序列、顺逆、半年敏感性和换卦的同次轨迹与`yuantang`视图。108个直接图式位置、24个明文推演及24次不敏感重复比较分别计数，三至尊術語仍列未决，见第十四轮核对（本地数据：`validation/heluo-yuantang-audit.md`）。

| 维度 | 已完成的证据 | 尚未通过的范围 |
| --- | --- | --- |
| 历法 | 国立天文台2026年24节气最大时差29秒；香港天文台2026–2028年72节气最大时差30秒，容差均为60秒。另测交节前后、至点半年、太阳时与绝对时刻分工 | 不是所有年代、地点、历法转换与出生时刻精度的满分认证 |
| 原典 | 原有四组取数例及新增四组四柱步骤（保留一处总数冲突）、五行参评例、元堂配时、纯卦、三至尊卦、三元寄宫；岁运54行直接算例及12行规则推演；五卦30个正纳与18个借用 | 刊本总数及日期矛盾、全书逐字校勘、土用版本差异、综合葉否、岁运卦序到现代日期的完整映射尚未完成 |
| 解释 | 返回同次计算的取数轨迹、元堂条文、来源、语料散列和未决事项；三端输出与严格投影一致性测试 | 任意模型自由生成的解释未获语义忠实度认证 |
| 现实预测 | 保持 `not_validated`；本次没有可评估的前瞻真实研究 | 不报告成功率，不授予权威称号 |

验收结果见 JSON 中的 `calculation_checks_passed` 与 `four_dimension_acceptance_passed`。两者含义不同；四项总验收目前为 `false`。有限参考样本全部通过，也不能推出样本外全部正确。

## 影印本岁运卦序

已下载并按 SHA-256 固定 NLC416-13jh000625-42999 PDF，封面明确为上海文明书局印行本，具体出版年份尚未确认。核读 PDF 第37–40页（卷一页二五至二八）并保存四张原页图像、来源清单和独立手录算例。此举只完成指定页的规则核读，不把近代印本说成明刻原叶，也不等于整本校勘完成。详见岁运第二轮审计（本地数据：`validation/heluo-timing-audit.md`）。

`heluo_timing` 现在提供：

- 阳爻九年和阴爻六年的小象游变；每一大限重新以其交运首年的干支阴阳判定，不重复使用出生年的阴阳。
- 十二个月卦序；奇数月递进，偶数月只从对应奇数月取应爻，偶数月结果不喂给下一个奇数月。
- 三十日定式；五个六日块各自从原月卦变出，各块自初爻至上爻配六个序号。尚未实现原文寄刻与实际节月长度衔接，不返回假定的公历或农历日期。
- 显式选中的年、月序、日序对应条文和周易参照。`changed_pos` 是变爻，`pos` 是选文所用爻位；两者在日定式中含义不同。

另修复立春前出生的大限 `yearStart` 偏到下一公历年的问题，统一用出生年柱对应年标签；修复月卦表中“无妄／無妄”字形不同导致的得时漏判。年份标签仍不宣称确定的年度起止瞬间。月卦锚点采用实际流年爻位；现代转述中遇本命原卦改用本命元堂的另一读法未混入本规则。

第三轮把实际六爻正纳、借用及命中位置放入 `judge.najia`。`deSheng` 仅表示这项年命纳甲匹配；`deTime` 与 `deTi` 仍分别是继承的月支表和日干映射，不能独自选定综合葉否。`yuanTang.heLi` 仅表示用爻阴阳与所用阴阳令是否同类；快照已去掉把它直接称为“顺气／逆气”的概括。指定岁运的快照现在使用对应年、月序、日序的实际用爻。

## 参评实际配运

`canping` 现在要求明确 `gender`，不能默认男命。`dayun_method` 与本命取数参数 `method` 分别控制配运和日支起数。默认附法按出生民用日期到前／后节的日差作整日借除；日内分数如何折算仍有未决处，结果不会把该约定称为原典秒级应期。新方案不使用命宫，因此 `ming_gong` 为 `null`；实际起运信息位于 `canping_timing`。

`analysis_datetime` 必须是带时区ISO时刻。查询按实际大运区间和立春干支年取数，不默认当前时刻。流年 `segments` 在交运时刻拆分；整年若有多个段，不再返回一个冒充全年通用的数。`not_started` 不产生大运／流年编号和断语，也不套第一运。具体同次选文位于 `canping_timing.selected.verses` 及 `numerology_evidence.selected_texts`。

## 《豫》六爻与逐条爻辞状态

新增所选印本豫六爻标题／完整注文目校，各96/384、288待校，仍含暂读；固守替换继承有守，两项错误首稿撤回，六二注文与九四头辞各一字未决。九四嵌套条件保留在不葉者父段内。修复全局标题状态覆盖单条疑字的问题，实际三端及临时stdio核验完成。完整相关104模块4954通过／2跳过，原全部节点保留；不是全仓CI。Native原96点仍12项超1秒，原典冲突、上轮模型未满足项及预测未验证状态不变，本轮模型调用0、现实结局0。详见报告（本地数据：`validation/heluo-yu16-commentary-audit.md`）与原始材料（本地数据：`../tests/fixtures/heluo_yu16_v1/README.md`）。


## 配运阅读上下文

配运结果新增同次`reading_context`，连接实际方法、钟制条件与书名／版本／书影、页码、引用角色；地区未来规则、固定偏移假设与旧法无日期映射分别披露。原始条款、首行、首运、查询身份与计算值保留。公开审计中的显式审阅私有段在模型工作区过滤，完整源文仍供人工审阅；完整历法、原典和模型解释验收仍未完成。执行状态和证据见审计报告（本地数据：`validation/canping-reading-context-audit.md`）。


## 参评扩围端点的完整年界

共享DE440独立年表登记1700—2300年后，参评新增具名有界立春数据与许可，覆盖低端1699年界和高端完整120年序列至2420年；旧产品、旧出生范围的计算与原判据继续保留。派生许可不扩大独立年表范围，原典符合、未来UTC及解释满分仍未建立；数值与完整相关验证见审计报告（本地数据：`validation/canping-extended-projection-audit.md`）。


## 太阳提供器来源身份与120年年界前置资格

修复VSOP2013完整来源配置可被非空改写、配置读取异常漏出统一来源错误的两类缺陷；修订1.1.0将工作TT终点扩至2421年初。完整节气队列仍仅1684—2304年，另对2305—2420年116个立春完成原1秒TT线对照，服务于计划输入1700—2300年的参评120年边界。源码及独立安装包各15,020项通过，原14,904根逐点不变；新增最大差0.816974秒。当前工作区44项来源检查、2项默认三端兼容检查通过，24,372份旧夹具保持。全局选择器及公开排盘尚未接入VSOP2013，原生96项的84过／12失不重评；原典、模型解释及现实预测缺口保持。完整报告（本地数据：`validation/numerology-vsop-projection-audit.md`）和初败与数值证据（本地数据：`../tests/fixtures/vsop2013_projection_v1/README.md`）保留。


## 《剝》六爻与摘要较窄条件

新增所选印本《剝》六爻标题、完整注文及24个父段目校，各138/384、246待校；剝二标题仍有疑读，剝五首稿误字已撤回。泰二和剝上短摘要保留较窄前提，适用性未知且不替换正式卦盘。120模块6227项完整回归通过；随后审计水部／全局分母修复另经5项验收。默认安装包1426文件一致，新stdio14次查询与六个排盘的三端18次调用通过，共享MCP未重连。原始失败、25,537份历史夹具与原数值容差保留，三个专业维度及四维总验收仍均未通过。详见报告（本地数据：`validation/heluo-bo23-adoption.md`）。
## 重跑验收

```bash
uv run --locked --extra dev pytest \
  tests/test_numerology_accuracy.py tests/test_numerology_transports.py \
  tests/test_heluo_tool.py tests/test_canping_tool.py tests/test_heluo_timing_depth.py \
  tests/test_heluo_najia_depth.py tests/test_hko_calendar_independent.py \
  tests/test_canping_timing_depth.py tests/test_heluo_seasonal_depth.py \
  tests/test_heluo_input_and_text_depth.py tests/test_heluo_month_depth.py \
  tests/test_heluo_body_depth.py tests/test_heluo_worked_depth.py \
  tests/test_heluo_qi_depth.py tests/test_numerology_clock_depth.py \
  tests/test_heluo_commentary_depth.py tests/test_heluo_yuantang_depth.py \
  tests/test_canping_text_depth.py tests/test_canping_water_depth.py \
  tests/test_canping_witness_depth.py tests/test_numerology_timezone_depth.py \
  tests/test_heluo_line_conditions_depth.py tests/test_canping_gold_depth.py tests/test_canping_fire_depth.py tests/test_canping_wood_depth.py tests/test_canping_earth_depth.py tests/test_canping_rereading_depth.py tests/test_canping_header_evidence_depth.py tests/test_canping_fire_rereading_depth.py tests/test_canping_wood_rereading_depth.py tests/test_canping_gold_rereading_depth.py tests/test_canping_earth_rereading_depth.py -q

uv run --locked --extra dev python scripts/audit_numerology.py \
  --output docs/validation/numerology-audit.json

uv run --locked --extra dev python scripts/audit_numerology.py \
  --require-four-dimensions
```

第二条命令检查限定范围内的手算与已支持规则，成功可退出0；原文全部字面总数是否一致另看`all_literal_source_totals_agree`，当前为false。最后一条要求四项完整验收，目前应退出2；前三项子集可用`--require-three-dimensions`，也未完成。旧 horosa 文本夹具保留，测试显式列出与旧版不同的纳甲命中、标签和同支编号，避免用本程序重算结果冒充独立标准。

现实预测层应使用预先登记、锁定代码和规则的研究，预先定义可判定事件、时间窗、样本、基线和主要指标，保存预测发出时间与独立结果来源，公开漏报、弃权及缺失。已交付可执行研究方案草案（本地数据：`validation/numerology-prospective-protocol.md`），状态为尚未预注册，不能计作已验证。仓库已有 `scripts/audit_prediction_study.py` 支持研究计划、预测及结果审计；其防泄漏和评分测试不构成本术数的实际有效性证据。没有真实前瞻数据时保持未验证，不生成虚构“命中案例”，不通过事后改口或挑样本抬高分数。

<!-- agent-evaluation-private:start -->
## 解释评估的历史记录

公开河洛／参评入口拆为短入口及六张任务资料卡，保留原41个资料块（39个原样、两处更新过时覆盖表述）。修复旧评测文档进入模型工作区的隔离缺口，普通原典资料仍可读。原有11例、61判据不变：当前旧组24/25、新组36/36；仍有未来钟制条件漏述及一处额外引文缺口，不能认证解释满分。本地相关118项通过；原96历法点仍12项超过1秒，原典各90/384已目校及未决项不变，新增现实结局0。未执行本轮全仓回归。详见报告（本地数据：`validation/numerology-guidance-retrieval-audit.md`）与原始证据（本地数据：`../tests/fixtures/numerology_guidance_retrieval_v1/README.md`）。

<!-- agent-evaluation-private:end -->
