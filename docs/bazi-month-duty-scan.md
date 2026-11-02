# 月令司事的完整书影见证

综合与九专题的`evidence_chain.month_command.intra_month_duty.source_reference.scanned_witness`新增独立命名的书影来源。综合的证据链仍在`structure_profile.evidence_chain`。它补足具体月条、原字读法、页码及章末限制条件，不选择司令干，也不修改旺衰或实体藏根。

## 来源及完整核对

采用浙江大学图书馆／CADAL的[《三命通會·卷二》06066038.cn](https://archive.org/details/06066038.cn)，馆藏元数据题四库全书本、明万民英撰，共232页。完整PDF（本地数据：`../tests/fixtures/bazi_month_duty_scan_v1/06066038.cn.pdf`）的SHA-256为`af4a8ca65cc4dfdf63d6294adc7925a868214563d0d52664c7ba779b833db14a`；下载字节数及MD5与所获馆藏文件元数据一致。Commons的[同一CADAL编号目录](https://commons.wikimedia.org/wiki/File:CADAL06066038_三命通會·卷二.djvu)提供另一种文件格式；本轮未证明两种格式逐像素相同。

实际章节由原PDF66页〈論人元司事〉起，至73页“人命重提綱厥有旨哉”止，其后进入〈論四時節氣〉。66–74页摘录（本地数据：`../tests/fixtures/bazi_month_duty_scan_v1/chapter66-74.pdf`）保留完整章节及前后边界，9页的渲染像素逐页与原PDF相同。转录以助手直接读图为据；IA的OCR误读严重，只作为保留的检索尝试，未作为数字或字形的判定器。

方案（本地数据：`../tests/fixtures/bazi_month_duty_scan_v1/protocol.json`）在查看扫描页前冻结，既有识典及维基数字文字已暴露，不是盲测。全部24个月条、69项时长、年度句及完整章末评议在首次转录（本地数据：`../tests/fixtures/bazi_month_duty_scan_v1/witness-first.json`）中冻结，再运行结构核对。页码指原232页PDF序号，不是摘录页号或识典平台页号。

## 数字异常确实见于该扫描本

| 所列条目 | 书影原数字及位置 | 字面结果 |
| --- | --- | --- |
| 随后表的酉月 | 原PDF70：辛20、庚7、丁5 | 合计32 |
| 随后表的子月 | 原PDF70：癸18、壬5、辛3 | 合计26 |
| 年度句 | 原PDF69：甲丙庚壬各35，乙丁辛癸各35，戊己各50；末称360 | 所列数相加380，与所称360不同 |

这些数字与此前保存的识典数字条目一致，不能再把差异一概归因于OCR。本轮没有改成30或360，也不把上述名义时长当成现代实际历月长度。该扫描本与识典底本的确切复本身份仍未建立；相同数字不证明所有版本相同，更不是两组独立预测验证。

六处条目的本次书影读法为“己／己土”，数字文字保存为“已／已土”。新见证按所读“己”列实际透藏，原数字资料、未知身份及首次记录保持原值；没有在旧资料内悄悄替换。首份人元章见证中，艮土、坤土的阴阳干及透藏位置保持`null`；后续跨章对读另见下节，不覆盖这份首次转录。这些字形读法及引文尚未由第二位独立专家核读。

寅月表虽列己，现行寅藏干目录仍为甲、丙、戊；酉月表虽列丁，酉藏干仍只有辛。条目出现与原局实体藏干是两类事实，不能把前者加入根预算。来源字形或名义时长也不证明当下己、丁已在司令。

## 同书跨章的艮土与坤土身份

后续按预先冻结方案（本地数据：`../tests/fixtures/bazi_month_duty_identity_v1/protocol.json`）读完同一卷〈論天干陰陽生死〉原PDF9–35页，保留9–36页摘录（本地数据：`../tests/fixtures/bazi_month_duty_identity_v1/chapter9-36.pdf`），含十干段、完整章末议论及下一章边界。28页摘录的同次渲染像素与原书逐页相同；只转录所列七个锚句，不声称整章逐字转录。此前数字文字已经暴露，这仍是同一开发者目读，不是盲测、第二位专家或独立文字识别。

| 术语 | 书影依据 | 本次身份结论及范围 |
| --- | --- | --- |
| 艮土 | 原PDF17戊土段：“寅屬艮艮為山山為剛土即戊土也” | 同书跨章可对读戊；引用上下文为戊土、寅生及丙火相生，不能自动移作月内分日历 |
| 坤土 | 原PDF27癸水段称申中坤土庚金；19页是乾坤媒妁比喻，30页论土之体用与申坤位 | 所读章节不足以唯一指定戊或己，继续未知；不从坤卦阴阳推定天干，也不声称全书其他章节均无定义 |

原PDF29–35还讨论土生寅／申等说、体与用、气与质，并有评前说偏处及再引其他论述的文字。首次身份转录（本地数据：`../tests/fixtures/bazi_month_duty_identity_v1/witness-first.json`）保留相反脉络与七个原页锚句，没有把某一句择成通用长生、根力或旺衰公式。

新增交付位于`scanned_witness.cross_chapter_identities`。`identity_claims`列定义、上下文及适用范围；`month_term_observations`只关联当前月条实际出现的术语。寅月艮土另列`cross_chapter_canonical_stem=戊`及原局实际透藏，申月坤土仍为`null`，其他月没有这种月条观察。原层的`canonical_stem`、原字、时长及首次透藏`null`均不改写；未知位置与实际没有透干的空列表也分别保留。

身份对应仍不决定司令。寅月开头是艮土五日，随后表列己土七日，ML02所选《滴天髓》原文则说六日戊司令。明确艮土可对读戊不能消除时长和日序规则的差异，更不能据此选择对ML02有利的表。出生瞬间、古日序到连续经过量的映射、有效力量及通关依旧未裁定。

身份层首轮审计（本地数据：`validation/bazi-month-duty-identity-first-v1.json.gz`）逐一保存原19例的对应条目。349份完整旧证据在只去除新身份层后全部相同；十工具完整进程对照（本地数据：`validation/bazi-month-duty-identity-public-first-v1.json.gz`）同样只增加10处身份对象，原文本、身印收支、旺衰及起运值不变。原REST、原生MCP、CLI另验证该字段的严格投影。这些是源码与协议验收；尚未给新增来源安排新的真实模型解释试验或第二位专家审阅，不能扩大成解释满分。

本轮19例逐项解释审阅（本地数据：`validation/bazi-month-duty-identity-semantics-first-v1.json`）另记录85条说明及其返回字段，核对未知身份不是“无土”、术语对应不是已在司令、通关候选不是有效通关，以及身印沿用同次收支。审阅对象是结构化证据与拟交付说明，真实模型答复数为0；此前三批模型10/11、10/11、11/11及首次工具约束失败均保留，不拼接成绩或给新增身份层挪用验收信用。

本次完整原典回放（本地数据：`validation/bazi-month-duty-identity-source-corpus-v1.json.gz`）仍为25组349记录、303个不同输入、26个不同输入分歧，原19例全未解。本地回执（本地数据：`validation/bazi-month-duty-identity-local-v1.json`）分别记录检查及首次失败。此次没有据以采用的新力量规则或新增计算数值修复，正确例数不增加；现实预测继续`not_tested`。

新增26项测试及相关96项回归通过。冻结930项构建输入后，wheel的894个Python／JSON文件逐项与快照一致，同26项用例在该wheel再通过，不重复计作独立准确性证据。两项领域模块及两项审计模块类型检查通过；全仓类型检查、全仓文档与全部合同检查的未通过结果另列本地回执，不借本次局部通过宣称全仓通过。源码尚未发布或部署。

## 原书自己的限制与十九例

原PDF71–73完整保留醉醒子曰及章末评议，涉及主客、初中末浅深与轻重，并反问岂能以三五七日为限。末段还有“又支中所藏止以月论年日時不论”等原措辞；它的取用范围须依完整来源理解，不能据一段文字自行删除本次计算已返回的年、日、时藏根。当前没有据此采用另一套藏干或取格方法。

这也没有解决ML02在所选《滴天髓》段落所说的立春后六日、戊土司令。不同书的数字与原字不能择优混用来改对某一例；其余18个原始分歧仍没有所选原文节后日序，19例均无可唯一恢复的公历出生瞬间。`selected_duty_stem=null`、有效司令及有效通关未裁定均保持。

## 计算与交付核对

原始核对（本地数据：`validation/bazi-month-duty-scan-first-v1.json.gz`）与现行完整核对（本地数据：`validation/bazi-month-duty-scan-closure-v1.json.gz`）保留全部读法、数字和算术差异。校验器验证冻结转录、结构化条目及页面散列的对应，不冒充独立的文字识别或专家目校；来源若出现不同数字，比较器保留差异，不以必须相同作为发布门槛。

349份既有完整证据对象逐一比较，只移除新增`scanned_witness`后，所有旧字段和值相同。综合和九专题的实际REST、原生MCP及CLI严格投影一致；两个独立进程的十工具完整结果（本地数据：`validation/bazi-month-duty-scan-public-first-v1.json.gz`）保存新旧来源交付对照，所有原业务字段、文本、旺衰及起运值相同，仅10处证据对象新增书影字段。

完整旺衰回放（本地数据：`validation/bazi-month-duty-scan-source-corpus-v1.json.gz`）仍为25组349记录、303个不同四柱输入及26个不同输入分歧，与上一轮全部349条结果相同；原19例仍未解。原始反例、首次失败和采用门槛没有变化。本轮没有发现可据此修正的新增数值计算错误，因而没有调整公式或扩大正确数。

本地验收回执（本地数据：`validation/bazi-month-duty-scan-local-v1.json`）分别记录源码、协议和构建检查。新增来源尚未做真实模型解释试验，也未完成独立专家验收；既有三批模型结果与首次失败保持。现实预测无真实数据，继续`not_tested`，总体完成和权威认证仍未成立。

共享`uv.lock`在本轮期间增加jplephem、pyerfa和numpy，首个“起始到收尾锁文件完全相同”的收尾断言失败，原失败留存；没有恢复或覆盖并行工作。最终快照、构建与已执行的新旧业务对照所用锁一致。本轮涉及的五个既有力量／证据计算文件不变，不能将这项局部不变性扩大成整个研究期间全部依赖不变。

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_month_duty_scan --output /tmp/bazi-duty-scan.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_month_duty_scan_public --output /tmp/bazi-duty-scan-public.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_month_duty_scan.py
uv run --locked --extra dev python -m scripts.audit_bazi_month_duty_identity --output /tmp/bazi-duty-identity.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_month_duty_identity_public --output /tmp/bazi-duty-identity-public.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_month_duty_identity.py
```

输出已存在时审计脚本拒绝覆盖。
