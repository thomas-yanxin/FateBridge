# 八字旺衰与喜用的计算范围

解释八字中的强弱与喜用，需要区分结构计数、有效力量和候选条件。旺衰模型、喜用分层、版本回执与原典对照共同说明这些结果的计算依据，供 Agent 解读事业、财务等主题，也供开发者维护和核对实现。

读取时先核对模型和状态，再进入相应解释层；结构计数、有效力量与喜用候选分别承担不同含义，不能互相替代。

交节来源另见[分钟判定与JPL SPK](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-spk-solar-audit.md)：一秒交点误差门槛不保证所有分钟输入换月正确；显式SPK路径保留实际文件、时标与有限对照范围，不改旺衰和取用算法。

后续源码接入[随包DE440默认交节](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-de440-default-audit.md)，把原始轨道系数用于默认计算，保留旧解析与原生对照。完整交点与分钟队列的通过只认证对应历法组件；原典26个不同输入分歧和全部解释、现实验证缺口继续保留。

[出生秒数与输入分量](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-birth-seconds-audit.md)补齐已知整秒的传递，并区分显式00分／秒与兼容默认值。省略分量不代表真实生时精确，也不自动生成误差区间。

[出生重复钟时与已知UTC偏移](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-birth-fold-audit.md)补齐八字与时运入口的重复钟时消歧；偏移须符合已解析的时区规则，后续交运保留原地区时区。未知偏移不猜选，跳过钟时继续拒绝。

[派生秒数与漏采事件](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-derived-clock-audit.md)修复历史偏移变更后范围样本被重新归零的问题。原始秒数仍可未知；连续范围内的中间候选和完整交运极值尚待完成，不由逐分钟结果代替。

[文档中心](README.md) · [能力覆盖](algorithm-coverage.md) · [双人评分](compatibility-scoring.md)

综合与九专题的星位、根气、格局前提、运年触点及剩余盲区见
[八字深化审查](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-depth-audit.md)。新证据链补充逐项核对，不替换本页旺衰权重或宣称原典验收已通过。
所选月令、生克合路径及事业日支漏计修正见[原典路径审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-classical-routes-audit.md)。
通关位置、日支藏印与一杀四制的数量单位见[通关与实数对照](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-passage.md)。
天干合绊的完整精度修复及未通过的成化候选见[天干计力审查](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-stem-energy.md)。
五行知识的原典分类、数字与现代类比见[限域编释](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-knowledge-curation.md)；出现量和旺衰标签不测量智力、品德或身体状态。最新完整能量诊断（本地数据：`validation/bazi-element-knowledge-audit-v1.md`）保留全部349份旧回执，简单删除印支持或季相乘数仍不能解决官制刃反例，未改变生产判级。

| 要核对什么 | 阅读位置 |
| --- | --- |
| 强弱怎样判定，系数来自哪里 | [旺衰实际计算](#旺衰实际计算v11) |
| 喜用、条件项和中性项怎样区分 | [喜用分层与冲突](#喜用分层与冲突) |
| 当前输出的具体含义 | [回归案例](#回归案例) |
| 原典标注能验证什么 | [原典对照基准与未覆盖范围](#原典对照基准与未覆盖范围) |

## 旺衰实际计算：v11

`day_master.strength` 仍返回 `强 / 中和 / 弱`，底层现为
`season_root_revelation_relations_v11`，已替换旧版计数加月令2分的判级。
专项分析及 REST、MCP、CLI 均读取这一判级。实现见 [`core/strength.py`](../src/fatebridge/core/strength.py)。
v3按所选原典区别四墓土冲动与一般冲克，参数及强弱阈值未为本次命例调优，见[四墓土冲动审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-storage-movement.md)。
v4补上庚巳、壬申等实际阳长生重根在结构规则中的资格，逐柱记录原始根量、
剩余根量及是否计入；数值预算、参数和覆盖规则门槛保持原值，见[结构根资格审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-root-qualification.md)。
v5修复同一完整会合局的重复支被误判为竞争局，并将真实藏干通根与合成贡献分开。
逐藏干剩余账本也分别供应身、印等角色核对，见[同局重支与实际根量](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-complete-bureaus.md)。
v6修复合绊扣减使用展示取整值的问题，改用完整精度并提供逐干能量账本；
权重、阈值未调整，未启用未通过原典验收的局部成化候选。
v7增加完整同类三会／三合且至少两个合格存留重根的结构判级，保留原数值分量。完整会局存在不等于全部成化；该规则是指定原页原则的工程编码。完整349条回放修复3个已知分歧，没有已匹配标签退步，仍有23个不同输入分歧；来源、版本与旧首败见[升级审计](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-calendar-point-and-bureau-adoption.md)。

现行实现还包含完整局同目标外支的归属记录，以及只由同次实际成立会合提供解刑条件、唯一实体子卯对的单端解刑条件；策略分别见 [`formation_affiliations.py`](../src/fatebridge/core/formation_affiliations.py) 与 [`punishment_resolution.py`](../src/fatebridge/core/punishment_resolution.py)。这些是既有v8–v10规则，不能将上面v7的历史回放数字当作当前验收。

2026-11-03 岁运根类补充只复用原局根类分类，未修改本页旺衰权重、门槛或判级。修改前后完整登记回放均为27组367条、321个不同输入、24个不同输入分歧，原19例及逐组结果保留；新增根类与关系引用不等于已计算行运后有效力量，见[岁运根类与根位触点](bazi-timing.md#岁运根类与根位触点)。

随后对这24个不同输入登记待验证机制，并检查有根的官印身路径候选。该候选只在旧资料中纠正QQ-01，未达到原定新源改善与机制充分性门槛，未采用。该次审计时生产为v10及24个不同输入分歧；原标签、参考数据、未知项和首败继续保留。新增[单层根预算投影](bazi-timing.md#单层岁运支对原局根预算的限定投影)只复用原系数计算限定冲刑影响，不认证完整岁运有效力量。

2026-11-03 全域算法审查修正季相囚／死倒置，升级为v11：克当令者为囚，当令所克者为死。例如春木当令，金囚、土死；此前代码反写为金死、土囚。依据[《三命通会·论五行旺相休囚死并寄生十二宫》电子转录](https://www.shidianguji.com/zh/book/SK1610/chapter/1kf5v6ol1tqg5)，未改数值权重、强弱阈值、会合解刑或取用策略。十二月支按既有本气口径分别核对，四季土月仍是既有工程简化，不等同已完成司令分日或全书校勘。该修复会改变有效能量、份额及部分判级，旧数值账本保留，不能沿用旧“数值不变”验收。

字面四柱乙卯／己卯／辛卯／癸卯无本模型关系事件，独立手算得到木27、土1/8、水1/4、其余0，辛日扶身份额为1/219；旧倒置映射为3/439。测试同时锁定五季字面全表和旧v10／新v11的解刑合同。旧二十一例方向保持21/21，十九例份额改变。随包v8原典索引367条、321个不同输入按同一现行算法分别传旧／新季相回放，九个输入判级改变；以“至少一个精确标签分歧或集合约束违反”计，前后均26个不同输入，无匹配状态退步。这与前述27组审计指标不同，不据此宣称完整原典验收或现实预测有效。

### 原文原则与工程参数

参考 [《子平真诠·得时不旺失时不弱》](https://www.donglishuzhai.net/chapter/3719.html)、
[《论刑冲会合解法》](https://www.donglishuzhai.net/chapter/3720.html)、
[《论十干合而不合》](https://www.donglishuzhai.net/chapter/3718.html) 与
[《滴天髓·地支论》](https://zh.wikisource.org/zh-hant/滴天髓/03)。
原文支持月令与全局并看、根重于浮干、合有位置和争合条件、冲要辨根气轻重。
原文没有提供数值权重；下列系数及判级门槛是明确版本化的工程约定，
不是古法原定常数，也不是统计训练得到的成功概率。

| 因素 | 实际进入计算的方式 |
| --- | --- |
| 月令 | 逐五行采用旺2、相1.5、休1、囚0.75、死0.5；月支根气预算另乘2 |
| 通根 | 每支总预算2，按本中余顺序归一分配：单藏1、双藏2:1、三藏4:2:1；不再把本气与其藏干重复相加 |
| 透干 | 藏干有同字天干时乘1.25；年、月、时天干按实际剩余藏干根气从浮干0.25连续提升到有根1；合成贡献不冒充根，日干自身不再额外投票 |
| 六冲 | 根据含月支预算的根气资源比较承受力，强方保留0.9、弱方0.5，同五行或相等保留0.75；重复冲不连乘损耗 |
| 四墓土冲动 | 辰戌／丑未之冲、丑未戌齐全三刑单列；本事件不统一扣减土根，不增加土能量或释放其他元素。参与支水根的保留系数仍用原工程参数；其他合绊、自刑等作用另记，最终根量不等于本事件系数 |
| 合化 | 完整三会、三合及邻柱六合，须化神当令、透干、无争合及未受未解之冲；满足时把非目标根气的80%转移，预算守恒，保留余气 |
| 合绊 | 不满足化成条件的完整合局保留原五行，根气乘0.85，不伪造化神 |
| 半合 | 只作成势，把参与支非目标预算的20%转为趋势贡献，不称合化；趋势贡献与真实藏干根分开记录 |
| 刑 | 三刑取全组、子卯取成对，自刑取重见，轻减至0.9；与冲等叠加取最强减损，不机械连乘 |
| 相互解救 | 唯一完整会合或邻柱六合可解外冲；两端同时有不相容会合时保留冲并标争议；半合不冒充完整解刑 |
| 天干合 | 邻干且无争合时只折减相关干的作用；日主自身之合与争合保留复核，不删除日主、不认证化气格 |

未被证明应当失根的六害及寅巳两支等不完整三刑，不机械扣根。
三会中的六合不再重复计分；一个实体地支不能同时被多个合局重复消费。
同一完整三合／三会中的重复支按实体位置取并集，只形成一个同局候选。
不完整半合的共用旺支及不同关系争支仍按原规则保留未决，不以同五行目标强行合并。

### 判级顺序

先得到经过上述处理的五行力量，印比为扶身、食伤财官杀为减身，
扶身份额大于0.60为强，小于0.40为弱，其余为中和。份额是模型内部度量。

再执行有明确条件的结构规则：

1. 财星有根透出、两个有根官杀透出，且无印比透出、日主至多一处健全根时，
   按财生官杀而缺外援判断弱，不能仅被一个得令分数盖过。
   对照 [《滴天髓阐微·中和》王观察造](https://www.shicihui.com/zh-tw/book/ditiansuichanwei/16288)。
2. 得令、有含月支在内的至少两处健全根，且数值扶身过半时，判断强。
3. 至少两处健全根，年、月、时三干全为印比时，按得地得势判断强，
   避免失令就机械判弱。
4. 其余保留数值判级。每次返回触发的规则及数值原判，不隐藏规则覆盖。

健全根须属所选原典的重根或同五行本气根，且有实际同气藏干，
其剩余真实藏干根量至少为原根量的0.75；这也是工程门槛。
合局产生的趋势贡献不能冒充藏干根，阴长生无同气藏干也不能补造根。
`root_qualifications`保留逐柱资格，`structural_decision.numerical_label`保留数值原判；
两者均不声称已完成原典的全局力量裁定。
旺衰极端或四项参数±15%扰动导致判级变化时，停止自动扶抑取用，
分别提示从格／专旺复核或边界敏感。格局候选、调候参考仍各自保留。

### 验证与边界

旧转录命例夹具（本地数据：`../tests/fixtures/bazi-strength-reference.json`） 收录衰旺篇二十造，
涵盖五行各四例，以及中和篇一例得令转弱。
这是原文对照与规则回归，不宣称独立盲测或现实预测效度。
另按1947年书影完整校勘《衰旺》二十造（本地数据：`../tests/fixtures/bazi_seasonal_bureau_v4/reference.json`）：
第十二造时柱为壬子，旧转录为戊午；两套输入分别保留，不把两者都符合弱档当作版本已认证。
三档强弱映射也未实现原典太旺、旺极、太衰、衰极的细分。

[十九个声明分歧](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-nineteen-disagreements.md)已按原始书影逐例复核，原标签、异文和所有反例保留；
同次工程收支核对一致，尚未解决日主与印合计、食财承载、通关与寒暖的原典力量判定。
完整续读中和、源流、通关三单元仍未达到既定新源改善门槛，未采用候选或改动日常旺衰数值。

[身印、司令与通关定点复核](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-body-month-passage-audit.md)另修复身印占比重复使用六位展示值的问题，
改用同次未舍入分量；增加距节令的UTC经过秒数，司令干仍未裁定。
18组公开回放的原有业务字段逐项保持，19个分歧仍未解决；这些精度与来源修复不增加原典符合数。

[完整登记回归](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-source-corpus-audit.md)补齐后续三组已暴露章节，保留21组269条源记录、224个不同四柱输入。
原19例仍全部未解，另有2个已暴露输入不符；总计21个登记范围内的不同输入分歧。
明确未知、没有身强弱标注、内部公式不一致及局部条件分别保留，不过滤或换算成通过率。

随后[完整读取燥湿、隐显、众寡](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-conditional-force-audit.md)，9造中3个明确日主／日元素力量映射均未匹配，
原候选未改善、不采纳；另纳入共享工作树中新完整顺反局26造。
截至该轮登记为23组304条、258个不同输入，24个不同输入分歧保留。
新四条知识编释不改变生产旺衰，原78条知识保持，当前共82条。

后续[根量与君臣母子检验](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-root-load-audit.md)虽消除旧候选的JC01退化，仍未达到新源改善门槛，继续拒绝采用。
完整追加四章10造后，最新登记为24组314条、268个不同输入，25个不同输入分歧保留；原19例仍未解。

无根受生候选也未采用：它在旧367条开发记录中只改善一条已曝光分歧，在预定的〈顺逆〉完整三造中未触发、没有新增纠正，未达到采用门槛。原未知标签和生产规则保持；完整协议、首次结果及八项冻结检查保存在本地材料 `validation/bazi-unrooted-reception-v1/`，不能把研究候选当成现行判级规则。

[月令司事来源分层](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-month-duty-sources.md)补入原注与任注条件、三命完整两套月条及实际透藏，公开数字待核和日界未知。源文时长条目不作为藏干根或有效司令，旺衰公式、原标签与上述分歧保持。

[完整书影见证](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-month-duty-scan.md)另核CADAL卷二的全部月条，确认该印本也存在32／26／380的字面合计，保留字形读法与章末限日批评；没有据此改月内日界、藏干、旺衰或原19例标签。

后续读完同卷十干章9–35页，新增有原页依据的跨章身份层：艮土可对读戊，坤土仍未指定某干。保留章末不同土生说法及首次转录，不从术语身份升级为有效司令、根力或通关。349份旧证据与十工具原业务值全部保持；原19例与26个不同输入分歧没有因此减少。

[完整结果依据校验](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-complete-anchors.md)另覆盖综合`analyze_destiny`、标准命盘及九专题11入口，拒绝143个人工缺项控制，并保留86份有效分支和合法投影。此前十工具记录指标准命盘加九专题，不能替代独立综合入口的协议证据。该修复没有提高原典符合数；8192字符通关视图的十项不分页门槛仍未通过，首次失败及其完整载荷保留。

[节气重复小时交付](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-term-offset-audit.md)修复公开节气时刻丢失偏移与fold的问题，保留全部81个旧还原失败；原四柱、经过量与起运计算不变，旧本地钟面兼容，新增带偏移时刻供无损复核。该修复不增加原典符合数或认证绝对UTC精度。

验证脚本对照21例，
并对15个参数逐个±15%扰动，共630次。测试另覆盖月令与旺衰不等价、
月令／通根／透干去除对照、冲的方向、合解冲与争合、成局不化、
刑不尽拔根、预算守恒、日主不自我投票及120种日干月支组合。

复算：`uv run --locked --extra dev python scripts/validate_bazi_strength.py`，默认仅输出汇总；
需要完整报告时显式传入 `--output <文件路径>`。
扰动试验与日常入口现在共用所采纳的未取整预算算法；修复前脚本隐式调用旧算法的报告另行保留。
完整报告保存全部扰动的强弱及未取整占比，未知源标签保留为空，不计为符合或失败。
旧21例的630次扰动修复前后均未翻档；修复统一的是验证算法，未声称原典符合率因此提高。
参考命例极端情形偏多；原文的整体“中和纯粹”不自动等同于日主强弱字段的“中和”。
计分系数仍待更广样本和流派复核，不据上述命例符合率声称现实预测有效。

本版尚未计算节气后逐日人元司令、燥湿土差别、完整生克流通、
根气受损的所有门派异说，以及从格／化气格的成立。
`element_distribution` 是原结构计数；旺衰依据
`day_master.assessment.relations / effective_elements`，分别说明关系处理与有效五行预算。
两者的计算目的和计量口径不同，不能互相替代。

## 喜用分层与冲突

`structure_profile.resolution_policy = source_conditions_before_preference_v2`：

- `layers` 分别保留扶抑、各格局候选、调候简表的取用及忌避。
- 中和不再自动喜日主本五行；基础扶抑在这个区间不提供方向偏好。
- 月令主类以同次选择为参考，成格与取用未裁定；不再输出旧共现首候选的 `legacy_dominant_structure` 兼容字段。
- `candidate_selection`分列25条原典路径、月令本气与所选取神、可观察前提及未知力量条件；没有用固定优先级选定相神。
- `month_path_conditions_v4` 对伤官兼用财印路径另核财、印各有实际透干；《秘本子平真诠》同版书影PDF83–84的“干头两清”不能只由藏干出现代替。缺此条件返回 `observable_prerequisite_not_met`，藏干证据继续保留；财印已透仍不认证两不相碍、相对力量或成格。金水伤官用官等不同路径不套用这一透干门槛。
- `useful_elements` 只保留基准扶抑支持且没有反向参考的五行；未裁定的旧候选不单独提升全局喜用。
- `avoid_elements` 只保留基准扶抑提出且没有正向参考的忌避；旧候选单独提出的忌避也列条件项。
- `conditional_elements` 收纳喜忌冲突、仅旧候选或仅调候提出的五行。
- `neutral_elements` 表示本轮规则没有给出取舍，不代表有益或有害。
- 四个列表互斥且覆盖五行；`conflicts` 记录正反来源。未列为喜不自动为忌。
- `useful_ten_gods` 从最终喜用五行导出，避免元素与十神口径分离。

原典依据、月令与兼格的区别、藏杀与透杀及九专题视图见[月令取用路径](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-month-paths.md)。
这些是原典条件的有限形式化与规则冲突处理，不是已经完成的古典成格算法。
`assessment_status=conditional`，顶层喜用也只是规则参考，不是新增元素处方。
结构候选仍未检验制化力度、成格和破格的完整条件。

调候简表只以日干、月支索引。本版本返回主辅天干以及它们在原局的透干、
藏干位置，不判断剂量是否足够、寒暖是否已经调和或是否需要添加。
不同门派或不同分析层的分歧保留，不互相抵消。

事业行业、贵人方位与学业方向统一读取上述喜用解析；不再从
基础中和标签独立推导“喜水”。事业的忌行业也不再取喜用集合的补集。
这些现代应用仍只是传统对应参考，不构成职业或人生效果的验证。
健康文化结果只保留盘内分类、五行传统对应与关系变化，不使用喜用生成调理方案。

### 读取结果时的顺序

1. 在 `day_master.assessment` 核对模型版本、判级状态、触发规则与敏感性，再解释 `day_master.strength`。
2. 在 `structure_profile` 核对 `resolution_policy`、`assessment_status`、各层依据与冲突，再解释最终四组五行列表。
3. 解释专项或双人结果时，保留这些上游状态；个人层的 `rule_based` 不能替代喜用层的 `conditional`。

## 回归案例

对 `庚辰 / 戊子 / 壬寅 / 乙巳`：

| 项目 | 当前结果的含义 |
| --- | --- |
| 旺衰 | 新模型名义判强，扶身份额约0.611；参数扰动出现强／中和两种分类，明确返回边界敏感 |
| 喜用候选 | 空列表；参数敏感的基准不提供扶抑方向，旧共现首候选不再重新授予土、金 |
| 无条件忌避 | 空列表 |
| 条件项 | 木、火、土、金；旧共现、冲突及调候参考分列，原典有效力量未裁定 |
| 中性项 | 水；中和不再机械要求增加水 |
| 调候 | 戊为主、丙为辅，丙藏于寅巳；不由藏干存在推断调候已经足够 |

这是输出规则的回归说明，不是对真实人生的预测。

## 原典对照基准与未覆盖范围

原典标注夹具（本地数据：`../tests/fixtures/bazi_classical_v1/profile.json`）采用
《秘本子平真诠》扫描本的月令格局口径，版本为
`ziping_zhenquan_month_command_text_v1`。冻结夹具历史元数据将发行者记为“世界书局”；
同一书影封面（PDF1）实际题“上海世界图书馆发行”，当前引用以书影为准，
见[版本与页码](../skills/_shared/bazi-topic-evidence.md)。此次仅勘误书目，
不改历史冻结夹具、命式或裁定预期。
命式与裁定（本地数据：`../tests/fixtures/bazi_classical_v1/cases.json`）、
规则（本地数据：`../tests/fixtures/bazi_classical_v1/rules.json`）、
局部及未知输入检查（本地数据：`../tests/fixtures/bazi_classical_v1/probes.json`）和
分歧（本地数据：`../tests/fixtures/bazi_classical_v1/disagreements.json`）由人工目读整理，
未由生产输出生成；这不是第三方专家盲审。
冻结清单（本地数据：`../tests/fixtures/bazi_classical_v1/provenance/reference-freeze.json`）
记录输入与标注的哈希；
原文交叉核对（本地数据：`../tests/fixtures/bazi_classical_v1/provenance/source-crosscheck-addendum.json`）
保留原页位置、版本异文和适配器勘误，不更改冻结预期。

复算使用 `uv run --locked --extra dev python scripts/audit_bazi_classical.py --output <仓库外报告路径>`；
可用 `--split development` 或 `--split reserved` 选择已声明的分组。
脚本退出1表示原典算法验收仍有差异或未覆盖，测试通过只说明冻结、范围与
差异留存机制正常。已经用于比较的分组不重新宣称为未见盲测。

需要继续保留的限制：

- 透干、杂气兼透及“不失本格／兼格”不能用固定十神优先表代替。
  当前已修正禄刃坐支资格，并补充有限杂气会支选择条件；月令标签仍不证明完整成格。
  当前冻结命例月令名称匹配为10/10，原文明示旺衰仍为1/3；这些案例已用于开发，详见[四项独立验收](prediction-validation.md)。
- 根的存在、种类与权重是不同对象；局部通根相符不证明整体旺衰已获裁定。
  原文未明确总强弱的命式保留 unknown，不补成中和答案。
- 共现候选不等于完整成格、破格、制化救应或相神判断；
  格局用神／相神与现代五行扶抑列表不能直接作集合相等比较。
- 只有四柱的古代命式不验证历史公历、出生时刻、时区或节气换算；
  缺时柱不补默认值，也不以古代官职记述认证现代职业或现实效果。

主参考为[国家图书馆藏《秘本子平真诠》扫描本](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)；
[东里书斋文本](https://www.donglishuzhai.net/chapter/3722.html)提供导航和校异线索，
与扫描同源，不计作第二独立裁判。

## 原典知识查询

概念查询不需要出生资料。`knowledge_registry` 可查看当前分类与查询键，`knowledge_read` 返回正文、作者及来源；REST、MCP、CLI 共享业务数据。四柱、年柱、月柱属于 `domain=bazi`、`category=basics`，例如：

```bash
uv run --locked --extra dev fatebridge knowledge_read \
  --domain bazi --key 四柱 \
  --fields title lines citation provenance.entry_curation.source_refs \
  --strict-fields --include-snapshot-text false
```

其他来源资料按以下分类读取，具体参数见[API 参考](api-reference.md)：

| 分类 | 查询键示例 | 阅读范围 |
| --- | --- | --- |
| `source_vocabulary` | `旺衰与强弱的编者分层`、`得时得势得地的判读对象`、`五行取用表的适用范围` | 李雨田编者术语及完整30行取用表，保留正常五行与从、化、变格的适用条件 |
| `classical_force_semantics` | `日元强弱与性情措辞` | 任氏五行四态的20项来源关系；来源比拟没有提供四态的可计算阈值 |
| `source_contrasts` | `只换一字与干支联动` | 原典的字面比较、配月配时联动、未知条件与未印出的反事实盘 |

`provenance.entry_curation` 区分原典释义、工程说明与编辑边界；补充包各自保留版本与来源绑定。数字转录核对不等于书影校勘，单读者校读不等于独立专家认证。词条不会改变生产强弱政策，也不抵扣原典分歧或现实预测缺口。来源文字、全部表格与完整结果应沿同一 run 的 `result_delivery` 继续读取。

## 历史核查

逐次修复、未采用候选、反例和初次失败保留在[固定版本文档](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/bazi-assessment.md#专题核查索引)及配套冻结数据中；它们说明对应版本的范围，不作为当前全量验收通过的声明。
