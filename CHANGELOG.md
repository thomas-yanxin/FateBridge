# Changelog

- 太乙武经旁证审计追加全部45旧未知的书影补读，明确13项、保留32未决及原45差异；生产算法未改。见[补读说明](docs/taiyi-wujing-facsimile.md)。

- 太乙日计及明确金钥匙时计补充同盘冬至选元说明，分列计数起点与冬至实刻切换；数值策略不变，原典年度启元未裁定。见[核对说明](docs/taiyi-origin-activation.md)。

All notable changes to FateBridge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The version is single-sourced from `src/fatebridge/__init__.py::__version__`.
A version bump updates package metadata. `.github/workflows/publish.yml` publishes
new versions after master push CI succeeds (or a GitHub Release is published),
then creates the matching tag and GitHub Release after a successful PyPI upload.

## [Unreleased]

- 太乙金镜两算新增另一种代数实现的冻结参照，完整核查128计数输入及288原表两算，区分生产算术、源位置重算和原表内部差异；保留原11算差与3处始击分歧，生产数字未改。见[独立核查](docs/taiyi-independent-arithmetic.md)。

- 太乙武经旁证新增国图明刻本原页及无生产引擎依赖的288两算槽位条件核查；保留阴德／阳德名位冲突、阳四局55／25异文与全部旧成绩，不按较高相符数选定原典。见[两版与书内算路](docs/taiyi-wujing-internal-counts.md)。

- 太乙武经旁证加入冻结的同书十六神名位，明确16个大族位置并揭示阴德／阳德35项映射冲突；完整1440字段及旧评分并列保留，生产金镜规则未改。见[同书名位核对](docs/taiyi-wujing-names.md)。

- 修复太乙及三式在显式DE440年份端点的邻年误拒、自动模式来源混用及奇门置闰年表的来源缓存；按民用输入年统一选择，并保留晚子时跨年的来源观察。独立全年范围、原置闰算路和太乙积数公式保持，见[输入年与邻年节气](docs/taiyi-solar-context-years.md)。

- 太乙月／日／时计交付同次节气对象和实际轨道模型，区分换节／换遁与冬至起元；摘要、快照及导出共用保存值。补齐验证用星历数据闭包，查明临时快照缺数据导致的Moshier回退与边界差异，保留原失败及古历未通过状态，见[来源核对](docs/taiyi-solar-sources.md)。

- 独立模型评测显式传递太阳模型及SPK文件选择，修复计划Native却可能实际采用默认DE440的来源错位。解释指导对照未稳定通过，候选已撤回，失败保留；只读结果读取障碍另已复现，见第五十八轮核对（本地数据：`docs/validation/numerology-explanation-conditions-audit.md`）。

- 定位Native空目录的已知节气差异主要来自实际Moshier回退的上游位置模型；保留全部96点、12项超线与原1秒门槛。具名Swiss文件配置单列，不改生产算法或以另一配置通过覆盖失败，见第五十七轮诊断（本地数据：`docs/validation/heluo-native-precision-diagnosis.md`）。

- 太乙及三式增加同盘完整计数的360／60／72周期分解、实际单位与摘要视图；快照及导出共用保存值。十卷所选题注逐条核对，保留相位矛盾与数值失败，不据分组认证古历或修改默认起点，见[周期与题注核对](docs/taiyi-counter-cycles.md)。

- 修复密集三式视图仍有重复回执定位信息挤占首屏业务字段的问题；在原预算内明确将完整回执放入同次manifest，首屏保留运行标识，完整事实及哈希可恢复，见本轮交付验证（本地数据：`docs/validation/taiyi-jinjing-v42/README.md`）。

- 参评配运回执增加固定释文、书目、完整原句角色及时钟一致性校验，并绑定同次钟面、来源轨迹与快照段；冲突在字段裁剪前报不可重试503。六份正常结果保持，原模型遗漏不重判，见第五十六轮核对（本地数据：`docs/validation/canping-receipt-binding-audit.md`）。

- 三式四维宫并列同次六壬两支实际神将与来源路径，继续标明寄支未定；抽出共享纯布将步骤，以金镜原例明确条件核对，保留朝暮差异、天空／天定异文与完整原例未通过状态，见[原例核对](docs/taiyi-dangshi-sectors.md)。

- 河洛补入泰否十二爻完整注文与标题，单次目校层各72／384；三处引卦保存实际段落条件，否九四引观不再受限于仅岁运段的引用结构。疑读不补字，原60条保持，见第五十五轮核对（本地数据：`docs/validation/heluo-taipi-commentary-audit.md`）。

- 三式合参可显式选择已有六壬贵人表，新增同盘实际起贵本位与金镜明钞／四库当时法的逐版来源对照及导出；保留两版十项分歧，默认选表不变，朝暮判界与完整联合断法仍待核。同步月计1.2.0旧说明，见[贵人对照](docs/taiyi-dangshi-nobles.md)。

- 西占七曜日运动去掉冗余的 TT→UT1 试算，C04 有效末端仍可计算下一 TT 日位移；修正 Lahiri 偏移跨 360°／0° 时给全部行星速度叠加一整圈、误翻顺逆行的问题。原典例题差异和解释／现实验收缺口继续保留，见核验记录（本地数据：`docs/validation/western-lilly-daily-tt/report.md`）。

- 修复默认金镜月计把大雪锚年重复减一而少计12个月的问题；按所求名义年生成完整积月、盘面和同次回执，规则实现升为1.2.0。补齐金钥匙附例及1561全年对照，保留全部古历失败和旧基线，见[名义年修正](docs/taiyi-key-worked-accumulation.md)。

- 修正固定四柱Python流年函数在未知公历年时沿用生日支、起运前套第一运的回退；保留相对干支及按需延展，公历年保持未知，并新增卷六PDF64替支释文回执，见第五十四轮核对（本地数据：`docs/validation/canping-relative-years-audit.md`）。
- 修正旧命宫流年表在立春前从错误太岁起排，首年按实际年柱对应的年标签定位并纠正取数／岁运选文；保留旧配运未核UTC映射的范围，见第五十三轮核对（本地数据：`docs/validation/canping-legacy-year-label-audit.md`）。
- 参评新增配运原句与现代日期映射回执、同次首运摘要及`timing_policy`短视图；分别标明整数附法、连续法和未核旧命宫法的来源角色，另书十年背景不冒充所核河洛附段。源据改写返回不可重试503，完整时间线保留，完整验收仍未通过，见第五十二轮核对（本地数据：`docs/validation/canping-schedule-basis-audit.md`）。

- 河洛新增小畜履十二条完整注文及履六条标题单次目校，按真实三段支持未单列不葉者的小畜九三；有条件引巽初与正式后天巽四同卦异爻分别保留。旧48条注文与54条标题保持，见第四十七轮核对（本地数据：`docs/validation/heluo-xiaochuli-commentary-audit.md`）。

- 河洛新增师比十二爻完整单次目校，纠正比六二混入全卦纳甲句及师比若干错录；师三有条件引升三单列核对，不替代正式后天卦。旧36条保留、336条仍待校，见第四十六轮核对（本地数据：`docs/validation/heluo-shibi-commentary-audit.md`）。

- 西占补齐8,078项同参考点／共同框架外部位置复核，保留原始跨框架及混点失败，并修正恒星传播和C04边界的咨询旧说明；没有修改生产坐标或放宽0.02角秒线，完整原典与现实预测仍未验收。

- 西占月亮／七曜地心黄经事件改用完整TT试算，不再因C04范围外的冗余UT1查询而失去可计算结果；宫位与地平仍严格检查UT1。新增边界外部参照，固定位置比较线仍有失败，未宣称精度或预测满分。

- 参平补齐完整120年配运所需的未来立春，保留121个实际边界、显式模型及同次查询两端；新增原系数包与先冻全队列比较，公开年限、原典／现实预测验收不变，见第四十五轮核对（本地数据：`docs/validation/canping-projection-audit.md`）。

- 修复Marks关系盘的字段卡与技能旧说明：现在读取双方个人盘、声明内方别名和实际Davison配方，安全联合投影在其他模式保留空根；加入真实模型解释诊断准备，未宣称语义已验收。

- 西占卜卦／择日新增显式 `ut1_source=iers_c04`：固定每日实测合成UT1及连续UT1−TAI插值，保留默认Swiss ΔT。返回源指纹、覆盖／插值依据，范围外不回退；其余EOP和完整预测能力仍未认证。

- 河洛化工／至点与二数时令统一使用民用年共享节气窗口，修复显式模型端点年因相邻年查询失败的问题，保留实际来源并拒绝上下文／分类冲突；不扩大模型公开年份，见第四十四轮核对（本地数据：`docs/validation/heluo-solar-context-audit.md`）。
- 河洛新增按出生年干支核对的逐阶段“无正而有反”计算，分开候选命中、缺席前提和只看上下体的范围比较；拒绝源表／实际卦体冲突，保留反中有救未决，见第四十三轮核对（本地数据：`docs/validation/heluo-yuanqi-opposition-audit.md`）。
- 河洛新增需讼十二条完整注文单次目校，总覆盖36／384，旧文与草稿撤回保留。修复非空换文／交换条件正文仍沿用已校身份的问题，分列规范内容与载入字节散列，并让来源标题按实际覆盖生成，见第四十二轮核对（本地数据：`docs/validation/heluo-xusong-commentary-audit.md`）。

- 西占卜卦／择日太阳时反解保留TT／UT1原生轴，支持UTC闰秒标签；区分秒60与datetime载体，昼夜判定及卜卦事件显示不再重解析／丢弃该标签。

- 河洛新增二十四节卦查表、七十二项原候卦标签及两种显式六十卦名义日序；保留原印爻名与卦形差异、原例／表头对照和未定模型，不自动选择实际候卦或化工，见第四十一轮核对（本地数据：`docs/validation/heluo-jiehou-audit.md`）。

- 河洛修复岁运年标签／干支冲突可改变卦的问题，新增卷一百刻与六日移支的精确相对算术、同次源式证据及来源故障防护。六十块全年闭合不冒充日内分制或实际日期映射完成，见第四十轮核对（本地数据：`docs/validation/heluo-clock-year-context-audit.md`）。

- 河洛新增屯蒙十二爻完整注文目校，修复雖／難、顯達及原页字面等解释差异；总覆盖24／384，旧文与初读撤回分别保留。标题／注文来源损坏改为不可重试503来源故障，见第三十九轮核对（本地数据：`docs/validation/heluo-tunmeng-commentary-audit.md`）。

- 河洛固定四柱起命补验年干／月干、日干／时干衔接，两数公开实际所用柱的原句、步数及同次证据；内部不一致返回来源故障。原书一条冲突取数例保留原柱与35／24，仅作形式算术，不伪造已验出生盘，见第三十八轮核对（本地数据：`docs/validation/numerology-pillar-links-audit.md`）。

- 河洛新增渐卦四体八体结构证据，区分三爻体、六爻卦、倒序与移爻，公开同阶段原爻位映射及具名算子推演。复现一个原书结构例，加入能识别倒序／阴阳全翻巧合的反例；完整伏体、得体及葉否仍未裁定，见第三十七轮核对（本地数据：`docs/validation/heluo-structure-audit.md`）。

- 西占卜卦／择日新增显式儒略历日期输入，支持世纪闰日，先换算日期再校验时区与夏令时；原日期、内部日期及日期标签JDN分别回执。新增默认历法回执、`calendar_input`卡及择日按需合同，未推断地区改历、旧式年份或原典太阳钟时。第115页整度与第145页度分恒星输入的敏感性另列，未改旧例题配平；见历法与精度核验（本地数据：`docs/validation/western-civil-calendar/report.md`）。
- 西占卜卦／择日接入共享地方平／地心视太阳钟时反解，显式区分民用钟时，阻止与时区重复修正；新增 `clock_conversion` 回执与 `clock_input` 字段卡。日期先换算、平太阳时使用UT1，民用省略时区仍保留旧 `+08:00` 默认并标来源。有限独立操作数复用及真实三端核验见事件钟时核验（本地数据：`docs/validation/western-event-clocks/report.md`），未认定原书未说明的钟时或预测效度。
- 西占卜卦／择日新增独立的 `hour_origin` 午夜／正午日起点参数，按Lilly1647第30–31页规范小时标签，保留原日期与进位后钟面，先合并整数日进位再检验最终范围；修复有效终点被不可表示中间日期误拒绝的路径，时区／太阳时随后解析。未改变原典评分配平，也未隐藏原有UTC闰秒载体缺口，见正午日起点核验（本地数据：`docs/validation/western-noon-origin/report.md`）。

- 河洛按具名主本的阴元堂、阳应爻原句新增逐先后天有援证据，保留两版字面。旧`youYing`明确为先天通用阴阳相异，不冒充十体有援总判；加入同阶段契约和来源故障检查，见第三十六轮核对（本地数据：`docs/validation/heluo-support-clause-audit.md`）。

- 西占按Lilly1647第121–123页补齐判断前审查清单、实际不等时主、可选严格上下文与条款例外；修复上升恰好27°漏判及燃烧之路上界，月亮晚度阈值、未报告受损条件和完整判断资格保留未知。新增字段卡、卜卦按需合同及CLI嵌套JSON入口；四个印刷对应例复现，完整原典与现实预测未认证，见条款复核（本地数据：`docs/validation/western-lilly-radicality/report.md`）。

- 西占新增Lilly昼夜同式福点、第145页独立28项表及第33页最近宫头五度效力回执；福点第六／八宫减分与七曜表分开，未知归属不补零。原书两个福点算式复现，第180页超五度归宫与累计差异仍明确失败，未扩大阈值或删行配平；见原图与接口核验（本地数据：`docs/validation/western-lilly-fortune-houses/report.md`）。

- 八字新增暖局与用神、日元强弱与性情措辞、根位与有效接引三条限域知识，原82条保持。完整性情35造纳入回归，现349条记录中保留26个不同输入分歧；新承载候选零新修正而未采用。修复完整回归脚本直接启动的导入错误，见[整章检验](docs/bazi-mediated-capacity-audit.md)。

- 宋历来源组件新增精确辰刻及完整时支区间比较，区分一日百刻、初刻零起点、子正源日及子时两段；1206亥时跨交节时保留两侧可能，不补生时或偷换公开月柱，见第三十五轮核对（本地数据：`docs/validation/heluo-song-clock-audit.md`）。
- 河洛历史历法研究新增统天／梅氏三位读法，复算两份印本演算工作表，保留分步舍入及累加端点差额；1206开禧旧例的纪日和“大雪前一日”冲突不改写，见第三十四轮核对（本地数据：`docs/validation/heluo-tongtian-audit.md`）。
- 河洛历史历法研究补上纪元、统元两套原页气朔算术，保留不同起日、细分分母及整数进位；同两旧例的日期比较保留白露一日差异和实际用历归属未决。新增Python来源算术入口，未接管公开四柱或伪造UTC，见第三十三轮核对（本地数据：`docs/validation/heluo-song-qi-audit.md`）。

- 西占新增Lilly1647第115页41行尊贵／减损回执，使用实际TT日位移、独立瞬时方向和历元恒星位置；日月不计顺行奖励，未知行不补零，起点坐标与来源变化拒绝混配。封存原页、勘误与单盘七曜应用，逐行累计仅复现原书3/7，日光束、三分、恒星等差异保留；新摘要卡与类型契约见全表核验（本地数据：`docs/validation/western-lilly-fortitudes/report.md`）。

- 八字综合、流月、流日、流时及大运统一使用完整的默认分析瞬间，修复“当前”被月初、月中或零点替代的问题；补充实际时刻、UTC偏移／fold及缺省来源回执，拒绝显式歧义／不存在钟时，并用UTC区分月日缓存的重复钟时。保留有效部分日期查询原字段与原旺衰算法，见[分析瞬间修复](docs/bazi-analysis-instant.md)。

- 河洛与参评公开推算格里历输入约定及同次历制证据，避免历史儒略历标签直接混用；四个原命例的五种题注读法与具名年号历表核对，保留三个日柱差异及一个年干支冲突。未改日期数值算法或声称完成宋代颁历复原，见第三十二轮核对（本地数据：`docs/validation/heluo-historical-calendar-audit.md`）。

- 西占补充标称历元的太阳位置模型回执，区分原生未偏折视线位于太阳后方、前景凌日、圆面外及未知边界；本命、希腊盘、印度盘与卜卦公开 `solar_position_model` 字段卡。新增291个JPL开发对照，保留太阳后方默认视位置的0.02角秒比较失败；诊断不替换坐标或认证物理可见性，见位置模型核验（本地数据：`docs/validation/western-solar-position/report.md`）。

- 八字按紫金山天文台原表完整提取1900–2025年46,021日，冻结后核对农历与纪日干支均一致；原HKO73,030完整格及19部分格保持，重合来源不累加独立样本。补充合法出生输入经真太阳时跨至表外的三端回归，保留未知农历、首次表头拦截及请求参数首败；未改历法数值或旺衰门槛，见[完整逐日核对](docs/bazi-pmo-calendar-audit.md)。

- 西占修复近太阳位置导数的假收敛，按已核对的太阳质量插值分段验证局部导数，保持原精度门槛和显示位置。固定84组源模型对照通过，2024年原中断历史恢复151个有限扫描事件；公开多层／方向／分段回执，并补齐成功历史的可空失败字段。近太阳严格位置诊断及完整原典仍未验收，见源模型与交付核验（本地数据：`docs/validation/western-solar-disc-motion/report.md`）。

- 河洛修复月份表缓存期旧数据与新文件散列混配的问题，分开规则与数据版本；补齐八纯卦纳甲基础原页核对，实际六爻返回直接条目或基础推演来源，源表冲突明确失败；13条卦解与64卦软件应用分别计数，保留解卦两版次序未决。新增四条月份／纳甲句，坎的及時不指定月号，见第三十一轮核对（本地数据：`docs/validation/heluo-najia-foundations-audit.md`）。

- 八字修订学业、子女、六亲及重复文昌共14条旧知识，补齐所选子平本的身印、财印、伤官用官与宫分条件，说明程序文昌只按日干及专题实际计数范围；其余68条、此前38个已编释条目保持。10条完成所声明条件校读，文昌两条及女命取象两条仍部分待校；原72条全部待独立外审，不新增原典命例或现实预测成绩。见[专题知识复核](docs/bazi-topic-knowledge-audit.md)。

- 河洛卦月条件修正月号未中时整句被误报否定的问题；九条月份／年命纳甲原句分列同阶段已知事实，连接范围与例外继续待定。新增离、井、涣十八项正纳原页核对，保留解卦次序差异，见第三十轮核对（本地数据：`docs/validation/heluo-najia-qualifiers-audit.md`）。

- 西占卜卦按Lilly1647第107页原图修复混合容许度，明确支持两列源表；新增实际落宫、分别保留的宫位强弱序次／宫位分值，以及第126–127页居宫的月亮传递必要子条件。修复新视图在事件成功时请求缺失失败字段造成的严格投影422，保留原图、修改前反例和2024年金星导数未收敛缺口。完整原典和现实预测仍未认证，见原典与交付核验（本地数据：`docs/validation/western-lilly-orbs-houses/report.md`）。

- 八字完整读取1947年任注《燥湿》《隐显》《众寡》九造并事前冻结三个不变算法；3个明确日主／日元素标注均未匹配，承载候选继续不采用。新增四条有版本、页码与程序边界的知识，原78条保持、当前82条；来源覆盖检查另拦截并完整纳入并行顺反局26造，当前23组304条记录、24个不同输入分歧。首败和未知均保留，见[完整三章检验](docs/bazi-conditional-force-audit.md)。

- 参评土部三格原图复读，一格录晝字形、两格保留疑读；校勘层1.11.0为1123格确定、47格未决，3379原有正确转录保持。修复继承语料读取的可变缓存泄露，调用方不能污染后续旧文与文件散列的对应，见第二十九轮核对（本地数据：`docs/validation/canping-earth-rereading-audit.md`）。

- 八字新增21组完整已暴露原典回归入口，补齐默认9组及季气18组以外的后续整章材料；保留269条原记录、重复与未知，当前登记范围有21个不同输入分歧，原19例均未解决。局部冲向、否定条件和录文内部一致性分别核对；修复旧回执新增审计字段与历史全对象比较冲突，原数值和判级仍精确保持，首次失败保留。见[完整回归审计](docs/bazi-source-corpus-audit.md)。

- 参评按馆藏原图复读金部15格疑文，4格确定、11格仍未决，保留麴蘖与追遊世；3314时运仅明花字，不借用女文。当前1122格确定、48格未决，校勘层1.10.0追加金部批次并保留旧见证和疑读历史，见第二十八轮核对（本地数据：`docs/validation/canping-gold-rereading-audit.md`）。

- 八字十九例继续核对身印、月令司令与通关，修复身印占比沿用展示舍入值的问题，补充同次未舍入分量及距节令UTC秒数；19个原典分歧和既定门槛保持。解释运行器公开既定工具限制并等待MCP就绪，第三轮11例机械通过、194句段开发者复核；前两轮失败、选择性文件读取与初版审阅索引均保留。见[定点审计](docs/bazi-body-month-passage-audit.md)与[解释验收](docs/bazi-semantics-evaluation.md)。无真实数据，预测效度仍未验证。

- 参评按原图复读木部四格正文疑读，三格确定、一格保留；撫手、玉藍、門帳按底本保留，傾□然不凭文义补齐。当前1118格确定、52格未决，追加木部批次并保留水火旧见证，见第二十七轮核对（本地数据：`docs/validation/canping-wood-rereading-audit.md`）。

- 八字逐页复核并保留全部十九个旺衰分歧，新增连续中和／源流／通关单元核对，候选仍未达采用门槛。修复预测验证器极小损失下溢及负无穷JSON输出，区分真实零值与数值下溢；解释运行器隔离历史验收材料，顺序完成11个虚构用例，首次机械10例通过、综合例失败保留，204句段及表格行完成开发者复核，独立外审待完成。见[逐例复核](docs/bazi-nineteen-disagreements.md)与[现实验证流程](docs/bazi-prediction-workflow.md)。

- 八字完整校勘1947年《衰旺》二十造，保留第十二造壬子／旧转录戊午时柱差异及原典极旺极衰状态，未将重复命例计作新改善。修复敏感性脚本混用新基线和旧扰动算法的问题，保存全部扰动数值、未知源标签和修复前源码；日常旺衰默认数值不变。

- 参评按原图复读火部11格正文疑读，六格确定、五格仍未决；修订鴛□为蒼鷹，保留浩雲等底本字面及未定末字。全表1115格确定、55格未决；分批见证保留水部历史，不增加编号格或独立复核，见第二十六轮核对（本地数据：`docs/validation/canping-fire-rereading-audit.md`）。

- 八字综合、九专题及根工具新增三会季支与同次工程季相门槛的分层依据，保留辰土本气、寅卯辰归组木和实际门槛的差异；未据此改旺衰。完成《八格》与后续四单元冻结核对，季气候选仍未达新源改善门槛，保留未知与失败记录。

- 参评复查六处遮损／淡损编号，十八格仍未决；新增正文与编号归属分层证据、严格投影字段类型及载入防护，避免将正文可读误计为编号已核。全表1109格确定、61格未决保持，见第二十五轮核对（本地数据：`docs/validation/canping-header-evidence-audit.md`）。

- 参评按同馆藏IIIF原坐标图像复读水部40格疑读，30格确定、10格仍未决；保留旧疑读、修订原因、短句和原页圈空。全表1109格确定、61格未决，不增加编号格或独立复核数，见第二十四轮核对（本地数据：`docs/validation/canping-native-rereading-audit.md`）。

- 八字综合与九专题新增五行出现分层：天干（含日干）、地支本气、全部藏干分别保留字位、出现与缺项，避免将原典某层“无金”误写成全局没有金。新增《形象》《方局》30例及上一章尾例的冻结核对；第三次旺衰候选未达新例改善门槛，未改生产默认值。

- 参评核读土部78行234格，修正“蚌內／虹內”等取文差异并恢复原页圈空，三格正文疑读保留；复用旧三格、净新增228格。全表1170格均已单次目读，1079格确定、91格未决，新增状态分开报告目读覆盖与读法确认，完整验收仍未通过，见第二十三轮核对（本地数据：`docs/validation/canping-earth-audit.md`）。

- 八字补充所选1947年《任注滴天髓闡微》的身杀两停、旺衰冲向及干支位置语义，保留此前75条知识内容。整章43例及未知、首次计算、退化与未采纳结论可复跑；季相单项候选未替换旺衰默认算法，见[六冲力量审查](docs/bazi-clash-power-audit.md)。

- 参评核读木部78行234格，修正陌上箏／恒上箏、權衡／權行及补写圈空等取文差异；四处遮损编号的三栏均保留未定。全表851格已确定、88格未决、231格未目读，见第二十二轮核对（本地数据：`docs/validation/canping-wood-audit.md`）。

- 参评核读火部78行234格，修正孤舟／孫舟、亦難／難難及补写圈空等取文差异；两处遮损编号另列暂定归属，三栏均保留未定，不因正文可读升级。全表633格已确定、72格未决、465格未目读，见第二十一轮核对（本地数据：`docs/validation/canping-fire-audit.md`）。

- 参评核读金部78行234格，按所选底本修正末11行号文归属并保留继承旧文；计算编号不重映射。全表420格读法已确定、55格疑读、695格未目读，新增逐部覆盖；差异归因和独立复核仍待完成，见第二十轮核对（本地数据：`docs/validation/canping-gold-audit.md`）。

- 八字按所选原典分列25条月令取用路径，保留本气与有限取神选择、变格兼格疑点、实际透藏及未裁定力量。旧共现首候选不再越级授予全局喜用，历史标签与账本完整保留；综合及九专题新增同次路径视图，见[月令与取用条件](docs/bazi-month-paths.md)。这未消除原典旺衰反例，也不认证完整成格或真实模型解释。

- 河洛新增逐先后天实际元堂的爻位偏好、二五君臣位与众宗式，拒绝仅凭五同一异而忽略实际用爻的匹配。快照将旧`dangWei`明确改称位序阴阳比较，原典阴月当位定义继续待核；不补十体评分或反面断语，见第十九轮核对（本地数据：`docs/validation/heluo-line-conditions-audit.md`）。

- 河洛／参评统一公开与领域入口的省略／null时区为固定`+08:00`，修复历史夏令时期间可差一小时、改变时柱的默认政策分歧；显式地区时区保留历史规则，空白／非法时区拒绝。同次出生证据新增实际偏移、夏令时及规则库身份，见第十八轮核对（本地数据：`docs/validation/numerology-timezone-audit.md`）。

- 八字旺衰升级为`season_root_revelation_relations_v3`，按《子平真诠》书影区分四墓土冲动与一般冲克；不再统一扣减土根，保留其他关系及实际剩余根量，新增严格回执与同次摘要。参数和冻结原典预期未调优，完整旺衰／成格验收仍未通过，见[四墓土冲动审计](docs/bazi-storage-movement.md)。

- 参评新增文明书局本36格局部对读，保留实际主选文、同栏对读文本及跨页编号、两版疑读与载入散列；更正此前把部分底本差异一概归为继承错字的结论，不替换主选文或增加已校数，见第十七轮核对（本地数据：`docs/validation/canping-witness-audit.md`）。
- 参评整段核读水部78行234格，修正南山／商山、鐵杵／鐵柱及补写圈空等转录；新增原页局部圈空与编辑疑读的独立状态，累计201格已确定单次目校、40格疑读、929格未目读，未把疑读计入完成数，见第十六轮核对（本地数据：`docs/validation/canping-water-audit.md`）。
- 参评按影印修正火2838、土3373的继承错号及两处转录，新增具体男女／岁运栏、顺逆有无、同号一行及载入语料散列；区分原页圈空、本地缺行和未选性别，固定四柱性别别名规范化。13／1170格单次目校仍待独立复核，附列2869编号与栏目未决，不再作为通用补文，见第十五轮核对（本地数据：`docs/validation/canping-text-audit.md`）。
- 河洛固定四柱不再将整个子／午月默定为一个阴阳令；比较元堂与后天结果，一致则保留唯一命卦与未知半年，有分歧则明确要求半年。新增原页元堂配时核读、实际性别／顺逆／至点及换卦轨迹、严格字段视图和三端验证，见第十四轮核对（本地数据：`docs/validation/heluo-yuantang-audit.md`）。

- 河洛按影印校正乾坤十二爻完整注文及坤六四重复串文，保留底本异文与葉／不葉／岁运条件；诗歌和旧吉凶摘要明确来源待核，标题、注文及缓存实际加载内容各自追溯。新增同次选文视图和三端验证，完整验收仍未通过，见第十三轮核对（本地数据：`docs/validation/heluo-commentary-audit.md`）。

- 人类图对点改为精确180°关系先分类、后生成浮点显示，修复浮点加法把地球／南交点推过门线及细分边界的问题；新增派生来源字段、生时见证回放和同次来源核验，节点后端及原典影响检查同步使用准确坐标。138,239个合成边界探针仅验收条件算术，不代表真实出生盘或星历错误率。

- 河洛／参评在开启真太阳时却缺经度时改为明确报错，修复静默套用上海经度导致错误日时柱的问题；钟表时未提供经度返回null，两工具新增同次`birth_clock`证据与视图，区分民用时刻、UTC瞬间和计算钟面。见第十二轮核对（本地数据：`docs/validation/numerology-clock-audit.md`）。

- 人类图与共享星历时间层补齐1960年UTC偏移／日漂移及1961年元旦5毫秒调整，保留原IERS13段；使用未修改的IAU SOFA C代码冻结233个独立时刻，修复可改变Tone／Base的毫秒级时标偏差，同步印占时间来源标签与三端对照。标准时标换算不认证实际出生钟记录。

- 修订十神基础词条中的泛化结果断语，补充身强印旺、身重印轻与身轻印重的限域语义；JSON与快照逐条返回作者、版本、页码、原网址和编辑范围，旧上游时间与词条修订时间分开。保留原典旺衰反例；后续清理八个健康旧断语，区分六个医籍出处仍待校勘的条目与54个未改旧条目，不把措辞修订当原典验收。见[知识编释台账](docs/bazi-knowledge-curation.md)。

- 调候摘要改为简表候选，保留全部120格兼容值；核对国图藏本甲木十二月提要和选定正文，公开申酉次序、未月半月条件及丑月操作次序与必要性的区别。综合及九专题新增同次来源与透藏位置视图；完整调候裁定与其他108格仍待完成，见[调候来源分层](docs/bazi-seasonal-source-layers.md)。

- 八字拒绝粗略线性节气回退参与年、月和时间边界计算；四柱、流月及流日窗口的派生缓存跟随星历环境，综合和九专题公开同次`calendar_basis`及实际模型。冻结4,872点DE440独立TT参考，保留Moshier的501个1秒门槛失败；超长运行环境通过同次交付物完整读取，避免挤掉首轮分析。见[模型与缓存审计](docs/bazi-ephemeris-context-audit.md)。

- 按香港天文台2100年12个月首补齐农历至2100-12-31；326天逐日映射与73,058天旧值保留分开验证，返回版本和来源，未加入存在2057年30天分歧的候选库。时间轴保留节气边界小数秒，回放分钟跳过不存在／重复钟时，防止重复小时内回放到事件之前。

- 人类图增加四箭头Variable及两颗实际星体的同次Tone引用；节点后端和生时变体实际重建编码，避免沿用原盘或跨样本拼接。新增8组预先固定的官方公开计算器对照、208个门线和8种Variable编码，保留未覆盖的类型／角色／交叉与原典印刷分歧；固定模板核验扩至七条，并拒绝伪造左右向和箭头引用。

- 人类图新增独立DE440/ERFA的122个真交点参考、节点后端差异及实际结构变化检查，保留Moshier未满足1角秒阈值的结果；补齐本机1800年初设计盘所需前一段星历数据并说明部署要求，不把同后端吻合或有限样本当作全面精度认证。

- 综合与九专题新增`force_components`公开证据视图，分别列身、印、食伤、财、官杀的原局藏根、透干与同次工程能量，保留未裁定的原典力量。冻结根势候选后新增34例逐页对照，明确旺衰7例仅符合4例；未触发改判分支的候选保持实验状态，没有用已知25/25开发结果替换验收结论。

- 人类图生时范围改为10秒连续TT网格与检测到的速度变号候选细查，修复只看名义点和两端漏掉内部往返细分的缺口；保留闰秒/历史UTC调整样本、各变体见证与名义解释范围，不将有限采样标成连续稳定性认证。

- 八字事业计数补回日支全部藏干，统一主导十神、共现信号及创业规则的口径，保留最高和第三位全部并列；索引与现代岗位类比不再使用事业层级断语。综合与九专题新增所选月令及八条原典星位路径、同根和财印隔位，提供可解析的同次证据引用与`classical_routes`字段视图；既有旺衰分歧仍保留，见[审计说明](docs/bazi-classical-routes-audit.md)。

- 修复人类图20–57通道误归Integration，按官方资料归为Knowing；增加完整通道的回路主题与逐句字段引用，区分四条整合通道及相邻Knowing/Centering。来源审计分别报告6条直接分类与30条端点标签推断，保留未完成的全本验收。

- 河洛第五轮核读二数与时令十一页，补齐十一数式与六个实际节气窗口，保留字面范围、余数奇偶及原文重叠；修正25／30相等误称季节得中，增加同次条件轨迹、摘要及严格合同，三端核对重叠与空窗。完整时令、得体及综合葉否继续列未决，见第五轮审计（本地数据：`docs/validation/heluo-seasonal-audit.md`）。

- 修复人类图与共享星历时间层将1961–1971年UTC当UT1的问题；按IERS原表独立提取13段历史偏移／日漂移，保留历史分数秒调整中的精确TT及无唯一民用标签状态。人类图独立星位对照扩至1900–2099选定时刻的120项，不冒称全时域验收。

- 参评数默认配运改为明确命名的卷七附子平方案，要求明确性别，保留连续折算与旧命宫方案的独立版本；新增带时区时刻查询、立春年界和交运分段，修复未起运套第一运、全年套同一大运及单次流年隐式取第一支。保存公文书馆三页影印、规则推演与三端回归，明确卷六配运归属和日内折算仍待校定，见第四轮审计（本地数据：`docs/validation/canping-timing-audit.md`）。

- 人类图设计时刻改为连续TT求解并保留UTC闰秒标签，修复民用时间根落在秒60时的不可表示问题；增加原典192交叉名、384线极性星体、同门／谐振门固定及逐句固定模板核验，保留29门印刷线界分歧。

- 宿曜第三轮逐格保留T1299印本360格月建异表，增加黑白月30日名、18条事项规则和偈散昼夜差异；原生说明保留全部匹配条文，修正GPS零坐标显示及咨询入口旧算法误述，增加同run完整解释上下文核验。历史小月分宿、原典七曜时和模型语义盲评仍未完成，见三项验收（本地数据：`docs/validation/sukuyo-three-axis-validation.md`）。

- 八字共享太阳时补充JPL独立参考：1900–2100年73,414个逐日午时样本，最终Swiss实现最大差异0.209秒；保留原Meeus/NOAA候选首次检验结果和来源，区别首次保留组与后续回归。综合／九专题增加原典根气层，修复财库冲与藏干财根遗漏及性格并列裁切；现实预测评估绑定解释政策、基线冻结与登记引用。各维度仍分别验收，见[审计说明](docs/bazi-solar-and-roots-audit.md)。

- 河洛第三轮按影印本逐爻核对正纳与乾坤借用，修复上下纯卦表合并造成的年命纳甲误报及借用漏报，公开六爻命中位置与严格合同。指定岁运快照使用实际用爻，简化月表、日干及阴阳令比较不再冒称综合判断；新增香港天文台2026–2028年72节气参考和当前三维目标验收，详见第三轮审计（本地数据：`docs/validation/heluo-najia-audit.md`）。

- 真太阳时改用真实UTC瞬间的Swiss均时差，增加366条NOAA原表缓存独立对照与时辰边界三端回归；八字新增保留阴长生异说的原典根类，分开墓库、余气与旺地根，保持未裁定根损及全局强弱状态。预测评估新增预登记检验次数、配对Brier保守证据界，保留旧点估计门槛含义，不用合成数据认证现实效度。详见[八字精度深化](docs/bazi-accuracy-depth.md)。

- 宿占默认改为七曜视赤经与现代距星不等宽研究宿界，旧等分黄道图须显式选择；修复宿内度数跨30度显示，冻结42个JPL坐标样本。宿曜增加T1299六类活动条文，保留业日及危日婚姻矛盾；提供配对去重、文件冻结、预测封存、盲法结局表和到期Brier评价流程。当前无真实样本，未声称现实预测有效，见[审计与迁移](docs/sukuyo.md)。

- 河洛第二轮核读上海文明书局印行本影印四页，新增有独立原页算例的流年、月卦与日卦定式，提供显式年标签及月日序号选择、实际选文和来源。修复立春前出生的大限年标签及無妄字形漏匹配；年界、寄刻与现代日期桥接保持未完成，不将定式序号当作现实应期。详见第二轮审计（本地数据：`docs/validation/heluo-timing-audit.md`）。

- 新增人类图三端工具：精确求解88°设计时刻、26激活与门线细分、中心通道图、类型权威、定义与人生角色；加入交点和生时敏感性、JPL对照、2001版原典数值摘录及公开未决分歧，现实预测仍未验证。见[人类图](docs/human-design.md)。

- 太乙公开入口改为《太乙金镜式经》年计核心，修复间神计数、始击求位、整十将位、岁首混用及中宫丢失，增加逐步规则路径；三式移除无依据的积数旋转与格名取模，明确年计和时刻盘范围。冻结72局独立表与争议影像，保留两项底本表文与通则分歧，现实预测效力仍未检验，见[审计说明](docs/taiyi-sanshi-audit.md)。
- 太乙增加六纪节月与冬夏至换遁时计的现代天文适配、秒输入和明确时钟约定；冻结完整阴72局、六纪首配置、天文台节气及扫描校勘，不修改原表掩盖11项分歧。补充掩击迫囚关格对空间条件；三式按实际方位对应五将与星门神，保留未校定的四维/中五寄支。默认证据视图和REST/MCP/CLI同步验证，完整日计、古历复原和联合断法仍待验收。
- 太乙年计补卷五年度十神与大游天目的独立起元、巡宫年序，保留绛宫、明堂、玉堂；逐项核对三元五纪原表720项及724/915年来源算例，保留直符中元33项异文并在结果显示双方读数，地乙缺文取得明钞本补证，六条新增年度宫位例通过；版本积年异文与大游天目时率继续标未决。新增年度深读视图，三式来源摘要保留原盘路径和未决条数。
- 太乙增加卷四五将三项合取条件，逐项引用同次实际阻断关系；三门未评估时保留门具将发为null。引入何丙郁论文完整10条历史入局参照，保留元徽二年理地/理人分歧，独立审计仍失败；新增三端可读取的组合条件视图。

- 河洛理数改用出生瞬间判断节气与至点半年，修正三元五寄宫循环及天地数归卦；参评数修复同支十三位和91岁后大运钳制，默认改为原典日支法 `gu`，月支变法须显式 `ming`。两工具增加规则轨迹、条文与来源、有限验证状态；不再把简化命中量宣称为综合葉否。新增原典算例、外部24节气及三端测试，详见[审计说明](docs/numerology-audit.md)。

- 增加八字四项分离审计与事前二元预测记录评估；没有真实记录时不生成效果结论。补充正官财印辅助的限定取格规则、旧标签与藏干根语义，修复综合命盘默认日期时区，以及学业、六亲、桃花模板中的结果越界和同时合冲遗漏。详见 [四项验证](docs/bazi-four-axis-validation.md)。

- 八字月令取格校正建禄／阳刃坐支资格，增加杂气透干会支的有限选择证据，保留原典分歧；时运新增显式生时范围及当前大运候选，拒绝未消歧的夏令时出生钟。扩展72个独立节气时刻核对，增加同次计算结构化引用核验和预注册二元预测评估器；无现实数据时保持未检验状态，详见[四项独立验收](docs/prediction-validation.md)。

- 修复八字大运按整数生日切换及过早舍入，增加带版本的十二步交运时间轴、按日期查询与未起运状态；补齐两条底层路径的立春年界。综合时运新增保留位置的刑冲会合、藏干十神与岁运并临证据，移除缺少原局条件的固定吉凶评分，将元素变化明确为结构占比；增加天文台节气对照和三端回归。详见 [八字时运审计](docs/bazi-timing.md)。

- 八字综合与九项专题新增逐星透藏／根气、财印位置、五类格局有限前提及运年触点证据链和公开 depth 视图；未知性别保留本命与独立流年。修复婚姻选星漏日支藏干、未知性别默认女命、神煞未实际命中即输出及男命墓库选星方向错误。原典分歧与未裁定条件仍显式保留。

- 新增完整印占核心：Lahiri 九曜、Nakshatra/Pada、D1/D9/D10、可追溯宫主／尊贵／graha drishti、出生时间敏感性与独立 Vimshottari 主／次运工具；同步 REST/MCP/CLI、咨询路由及软件数值对照。


### Changed

- 缩减根 AGENTS.md，生成逐工具按需合同；Onda 以短核心和条件参考组织阅读，补齐风水参数说明。
- 增加可选 topic MCP 加载范围与 doctor 验收，保留默认 complete 和条件分支覆盖回执。
- 增加 16 类真实 Codex 行为用例与轨迹检查；每批冻结技能、合同和实际执行的后端，分别保留机械评分与人工解读验收。
- Onda 插件携带当前后端源码、锁定运行依赖及来源散列，通过 `${PLUGIN_ROOT}` 启动；不再固定调用未包含本次优化的旧 PyPI 后端。
- PyPI 自动发布成功后同步创建对应提交的 Git 标签与 GitHub Release；重复执行保留
  已有发布，标签提交不匹配时停止，普通同版本提交不重打标签。
- 重写中英文 README 的安装与接入路径，补齐 stdio MCP 客户端配置、FastMCP HTTP
  启动、版本与 Onda 技能分发说明；新增 MCP 部署指南，覆盖 Windows、远程接入、
  协议验证、常驻服务及升级停用，并同步相关文档导航。

## [0.1.1] - 2026-10-20

### Changed

- 包版本更新为 `0.1.1`。
- 修复 Windows 私有文件权限常量与场景文件编码，MCP 安装诊断保留失败阶段及有界子进程日志；
  主分支 push 始终运行全量 CI，避免文档提交掩盖未完成的代码检查。
- 清理仅为旧响应保留的五行关系计分实现及专属测试，旺衰统一使用现有 assessment；
  删除 `jieqi24`、农历查询的 `year/time` 和梅易查询根部重复条目，迁移路径见迁移指南。
- 请求绑定直接传递全部模型字段，删除静默丢参适配；移除已退出仓库的审计目录 CI 特例
  与源码、测试中的阶段性实现叙述，保留日常维护工具和独立规则夹具。
- 修复局部技法将零经纬度替换为默认坐标的问题，统一坐标解析并拒绝越界、非有限值、
  分数超界及方向不匹配的输入。
- 大结果交付在 Windows 使用仅当前用户可访问的 ACL、拒绝重解析点并使用原生文件锁；
  POSIX 保留私有权限与 flock，CI 增加 Windows 启动、分页、权限和并发回归。
- 五维分值缺少信号时使用中性 50，不再将未知性别的爱情维度显示为 11.9；
  其余非零权重与归一化口径保持。
- 删除无效的 `nongli_time.after23_new_day` 开关、未使用的公历月份换柱 helper
  与个人电脑专用的 MCP 配置文件；迁移方式见迁移指南。
- 星历下载使用临时文件与原子替换，失败时保留已有数据；合并重复测试请求夹具，
  修正文档中的旧许可和外部应用说明，并替换维护脚本中弃用的 SDK 属性访问。
- 按首次使用、任务指南、接口参考和原理说明重组项目文档，新增核心概念与结果阅读指南，
  统一锁定环境命令、导航及可运行示例。
- Onda 扩展为九个生活主题、三个服务入口与一个多主题组合入口，共 13 个技能包；
  场景发现同步主题、任务、时间范围和共享咨询策略。
- 公共请求模型与共享执行层拒绝已知明确的生死、临床判断和医疗择时请求；
  卜卦与择时移除相关类别，健康与子女输出限定为命主盘内的传统文化解释。
  文本检测不能替代调用方对完整上下文的判断。
- 结果交付仅接受当前带元数据的临时记录，不再自动升级旧格式记录。
- 包管理统一使用 uv：提交 `uv.lock` 与默认 Python 3.12 配置，源码安装使用
  `uv sync --locked`，开发环境追加 `--extra dev`；发布构建使用 `uv build`，
  CI 增加锁定环境检查并保留最新版与最低依赖版本回归。

## [0.1.0] - 2026-10-19

首次正式发布到 PyPI，包版本统一为 `0.1.0`，Git 标签为 `v0.1.0`。
此前 `0.2.0` 为未发布的开发版本；下方保留其开发记录。

- 提供 `pip install fatebridge==0.1.0` 安装方式，以及
  `fatebridge`、`fatebridge-api`、`fatebridge-mcp` 三个命令入口。
- 随安装包分发计算规则、知识与场景 JSON、`py.typed`、LICENSE 和 NOTICE；
  场景技能随 Git 仓库提供，外部星历文件另行获取。

### Added

- 新增文档离线校验命令 `scripts/check_docs.py` 与 CI 检查，覆盖本地链接、标题锚点、围栏及 JSON 语法；新增迁移指南和按用途组织的请求示例索引。

- 补齐九类八字专题、宿曜双向关系、知识目录/来源/查询及导出模板/动态设置/分段的嵌套输出合同，并复用到各工具 snapshot_export；严格校验保持可空事实、扩展字段、部分投影及既有整数/浮点数原样输出。

- 专业输出补齐主限坐标与命中、递归时主、寿限、古典/关系盘及中国术数的嵌套合同；三端共用校验和发现 schema，保留动态键、扩展字段、可空事实、部分投影及既有数值。嵌套类型违规在投影前按内部失败处理。
- 场景 manifest 从 9 个技能 YAML 与住宅路由生成，共 10 个发现入口，REST `/api/scenarios`、CLI `scenarios`、MCP resources 共用；工具发现支持 scenario 筛选，可选 MCP scenario profile 与 family 取交集。
- 共享调用上下文支持 as_of / trace_id / parent_run_id；固定默认时间，保留显式日期、时区和手动起卦优先级，随机六爻记录本次 seed。
- 成功元数据增加格式/包版本、输入/合同/业务输出摘要、环境及数据指纹、耗时、口径和 replay 参数。新增字段可选，旧基础字段和 CLI --no-metadata 保留；有效标识传播到领域与校验失败，CLI profile 建立根/子关联。

- 玄空宅盘 `fengshui_xuankong_natal`（中州派 v1）：历史事件定运、24山／三元龙、五黄同元龙借运、下卦与兼向替星，分界和测量误差返回候选；REST/MCP/CLI 共用合同，合参与年度飞星分层。登记规则出处、网页版本和笔误范围，新增独立公开盘例及固定第三方比对差异记录。
- Six residential Feng Shui tools across REST, MCP and CLI: fixed directions,
  personal Ming Gua, sitting-trigram Eight Mansions, basic Jin Suo sand/water,
  annual Zi Bai stars and layered assessment. Versioned source registry,
  per-person results, explicit partial coverage and scoped differences are
  preserved; Xuan Kong natal charts are recorded in the separate entry above.
- Opt-in JSON `--request-file` and nested JSON flags for residential tools,
  shared layered output schemas, factual snapshots, offline independent
  reference fixtures and three-transport contract tests.

### API compatibility notes
- MCP results use FastMCP's native `ToolResult` with FastMCP >= 3.4.2;
  the custom SDK constructor adapter has been removed. Linux x86_64 / Python 3.12
  reference validation completes all golden comparisons without skips.
- Feng Shui `Ruleset` output fields now permit omission in dotted projections;
  native MCP clients can validate single-rule-field results. Full results and
  rule versions are preserved; catalog-wide projection regression checks cover
  nested objects, arrays and the REST/MCP/CLI schemas.
- Invalid projection paths now return additive `projection_warnings` while
  retaining the existing selected data and success status by default. Opt in to
  `strict_fields=true` (CLI `--strict-fields`) for shared 422 validation failures.
- Progressive discovery adds summary/filter/single-tool views to `/api/tools`,
  JSON `discover` / `list --json` CLI commands, and MCP catalog resources. REST
  defaults to full records; existing CLI text listings and `describe` remain.
  `FATEBRIDGE_MCP_FAMILIES` optionally narrows the registered MCP tools.
- MCP execution annotations derive from the same catalog hints exposed by REST
  and CLI. These describe environmental effects, not deterministic output.
- Requests now reject unknown fields and invalid civil dates with safe field-level
  `issues`. Explicit invalid election topics and horary categories are rejected;
  omitted selectors retain their defaults. Remove previously ignored fields from
  ordinary tool requests; CLI subject profiles still select fields for each tool.
- MCP errors now set native `isError=true`. FastMCP Client callers that inspect
  error payloads must use `raise_on_error=False`; successful text JSON remains
  available alongside structuredContent.
- All catalog tools publish projection-compatible output schemas. REST documents
  API Key authentication and error statuses, and uses stable catalog operationIds.
  Successful JSON shapes are preserved; schema-validation errors use 422 across
  REST/MCP/CLI. CLI command syntax errors retain exit 2 / usage_error.

### Changed

- 重整 README 与文档中心，集中安装配置、接口约定和迁移说明；风水路由归入 API 端点家族，统一已知契约直接调用、完整结果交付及文档信源维护流程。
- Synchronize maintained guides with nine Onda skills and ten discovery scenarios;
  complete Feng Shui topic navigation and the seven-tool entry table, and correct
  Xuan Kong examples to port 8010. Document same-run full export, post-projection
  retention, SHA-256 verification and explicit Western analysis clock inputs.
- Build compact call contracts without materializing full output schemas; copy
  timing-cache containers directly while preserving caller isolation. Benchmark
  reports separate initial calls, warm samples and the execution environment.
- Normalize hourly timing inputs before truncation and measure solar-term
  intervals in UTC across daylight-saving transitions. Metadata attachment and
  final output validation now share correlated internal errors across transports.
- Synchronize nine reviewed BaZi golden fixtures with the explicit timing-pillar
  provenance already added by the preceding implementation; existing numerical
  values and sections remain identical.
- Isolate golden output generation from locally discovered ephemeris files and
  restore the shared ephemeris configuration and derived caches on exit.
- Align maintained guides with the retired helper modules and transport-specific
  capability counts; check the complete algorithm tool matrix and per-family
  counts against the live catalog. Clarify bundled reference JSON, external
  ephemeris files, Git-only skills, and the scope of accuracy/performance evidence.
- Cache default model schemas and contract fingerprints with bounded, model-identity
  and rebuild-aware entries; public schemas remain independent copies and business
  executions are never cached. Remove the redundant third REST output validation.
- Build native MCP structured results directly from response dictionaries;
  move internal imports and transport tests to canonical modules and native
  registration paths while preserving retained transport contracts and numbers.
- Remove the obsolete `iztro-verify` extra, unused imports and private parameters,
  unreachable compatibility error forwarding and repeated export-section mapping.
  Bind documented CLI example tests to their test interpreter and refresh document
  navigation and maintenance guidance.
- Align integration, architecture, security, and Onda documentation with the
  current catalog and request models: distinguish transport bindings, document
  REST projections and 422 errors, and clarify installation, solar-time defaults
  and actual ephemeris precision. Simplify contribution steps and add a
  documentation maintenance and verification workflow.

- **Adopt the PyPA-recommended `src/` layout** (`fatebridge/` → `src/fatebridge/`).
  The package is no longer importable from the repo root without installing it,
  so a bare `pytest`/`import` runs against the *installed* package — packaging
  gaps (like the missing data files fixed in 0.2.0) now fail locally instead of
  only after `pip install`. Import name, wheel contents, and the three console
  scripts are unchanged. Repo-root-relative lookups (`.env`, `ephe/`) had their
  parent-index depth bumped so they still resolve to the repo root.

### Added
- `[project.urls]` (Homepage / Repository / Issues / Changelog) so the PyPI
  project page links back to the repository.
- `Typing :: Typed` and `Topic ::` classifiers.

### Removed
- Remove the remaining Python compatibility facades and aliases. Requests now
  use canonical Python field names on REST, MCP and CLI. Relative charts use
  `relative_mode`, directional snake_case fields and the primary `chart` layer;
  duplicate camelCase fields and `composite_chart` are removed. Export sections
  match current titles without legacy remapping. Primary directions use
  `equatorial` in place of the two historical method names.
- Remove the custom MCP result adapter; require FastMCP >=3.4.2 and use its
  native success/error results.
- Retired Python compatibility modules, package re-exports and REST/MCP wrapper
  aliases; remove `POST /api/calculate` and CLI `calculate_legacy`. Use
  `/api/cn/bazi/birth` / `bazi_birth` for a standalone chart and MCP / CLI
  `analyze_destiny` for composite analysis; see
  [migration guide](docs/architecture.md#旧入口迁移).
- `requirements.txt`, which duplicated `[project.dependencies]` with no check
  against drift. Docs now point at `pip install -e .` / `pip install fatebridge`.

### Fixed
- Preserve the actual selected Liu Ren lesson through transmission selection,
  so duplicate upper gods cannot mislabel 发用 or change Jin Kou 用神.
- Correct lunar month lengths in 1933, 1954 and 1978 without mutating the
  dependency's global tables; all 73,058 supported solar dates now agree with
  sxtwl. Cache immutable lunar-date values for repeated calendar requests.
- Resolve Zi Wei ages and flowing palaces using lunar boundaries and natal
  month/hour rotation, including childhood and leap-month handling. Expose
  calendar conventions and distinguish palace stems from transformation stems.
- Replace simplified Liu Ren transmission selection with the nine-method
  rules, use the day stem's element in the first lesson, and place generals
  using the nobleman's earthly position (including the 戌 reverse boundary).
- Include the equation of time in shared apparent-solar analysis inputs,
  bringing Qi Men / Liu Ren / Tai Yi / Jin Kou into agreement with birth inputs.
- Replace the Zi Wei oracle's calendar-branch comparison with actual active
  palaces; add pinned independent calendar and Liu Ren regression fixtures.
- README status badge and "项目状态" section said Alpha `0.1.0`; corrected to
  Beta `0.2.0` to match the `Development Status` classifier.

## 0.2.0 development notes - 2026-07-01 (unpublished)

First packaging-hardening release: the distribution is now installable and
usable from a wheel (previously the reference-data JSON was omitted, so several
engines crashed at runtime after `pip install`).

### Fixed
- **Ship reference data in the wheel/sdist.** Declared
  `[tool.setuptools.package-data]` so `fatebridge/data/**/*.json`
  (canping / heluo / knowledge stores) is packaged. Without it an installed
  wheel raised `FileNotFoundError` because the engines load these files via
  `Path(__file__).parents[1] / "data" / ...` at runtime.

### Added
- **PEP 561 typed marker** (`fatebridge/py.typed`) so downstream mypy / IDEs
  consume the package's inline type hints.
- `SECURITY.md` disclosure policy and a `publish.yml` GitHub Actions workflow
  that publishes to PyPI via Trusted Publishing (OIDC, no API tokens).
- `__all__` and a "Public API" note in the top-level package docstring.

### Changed
- Version `0.1.0` → `0.2.0`; `Development Status` classifier `3 - Alpha`
  → `4 - Beta` to reflect the stabilized, CI-locked API.
- Migrated license metadata to the PEP 639 form: SPDX `license = "Apache-2.0"`
  + `license-files = ["LICENSE", "NOTICE"]`, dropping the deprecated
  `License :: OSI Approved ::` classifier. `build-system` now requires
  `setuptools>=77.0.0` (first version to support the SPDX expression).

## Initial development (unpublished)

- Initial FateBridge engine: 80 tools across 13 families exposed over three
  transports (FastAPI REST, FastMCP, `fatebridge` CLI) from a single central
  tool catalog. Golden-master numeric locks and a 4-version CI matrix.

[Unreleased]: https://github.com/thomas-yanxin/FateBridge/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/thomas-yanxin/FateBridge/releases/tag/v0.1.1
[0.1.0]: https://github.com/thomas-yanxin/FateBridge/releases/tag/v0.1.0
