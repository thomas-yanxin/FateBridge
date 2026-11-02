# 月令人元司事的原文层次与实际透藏

综合及九专题现在都提供`evidence_chain.month_command.intra_month_duty.source_reference`；综合入口位于`structure_profile.evidence_chain`。该字段并列所选原典的数字条目、作者层次、原局实际透藏和未裁定条件。司令干、日界及有效取用仍未裁定，原314条记录的旺衰计算保持，原19例及扩大登记的25个不同输入分歧仍保留。

这一步解决原局解释缺少具体司令来源和限制条件的问题。它没有把新资料变为日序选择器，也没有提高原典旺衰符合数。原书中的时长说法、现代节后经过秒数和全局有效力量，需要分别验证。

## 两部来源与完整保留范围

《任注滴天髓闡微》采用任铁樵增注、李雨田校订、上海大东书局经售1947年4月初版，[整书书影](https://commons.wikimedia.org/wiki/File:SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf)散列为`d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803`。本轮重读PDF170–173月令完整单元及PDF200通关末页；保留原页（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/ditian-month-and-passage.pdf`）还含PDF197–199通关上下文。原注与任氏增注分层，不把两层拼成统一日序算法。

另一来源为识典古籍公开的[《三命通会》卷二〈论人元司事〉](https://www.shidianguji.com/book/SK1610/chapter/1kf5v6o9by5o3)。平台自述四库全书本，书籍版本37、分卷版本36，出版信息为北京大学与字节跳动古籍开放文本库。完整公开页面（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/digital-source.html`）、页面原始JSON（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/digital-router.json`）及13段完整数字原文（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/digital-paragraphs.json`）保留散列。目录自述本章13段，所获段序连续1–13，平台页码296–303。这是数字原文转录，本轮尚未核对其对应书影，不把平台底本自述提升为已完成原刊校勘。

原来源冻结协议（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/protocol.json`）保留首次转录。后续两项校正分别保留：引句中的爲改为来源实际的為；年度土组保留原字戊、已，不以内部字段名把原字已认定为己。时长数字、所有月条、段落和未采用条件未改变。[当前数据](../src/fatebridge/data/bazi_month_duty_sources_v1.json)与第三版转录（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/source-layers-v3.json`）逐字相同。

## 原注日序、任注条件和三命条目分别负责什么

| 来源层 | 本次保留内容 | 尚不能推出 |
| --- | --- | --- |
| 滴天髓原注 | 寅月戊、丙、甲及七日前、八日后十四日前、十五日后等原措辞 | 古代计日边界与现代连续秒数的映射；其他11月同表规则 |
| 任氏增注 | 司令、透出、引助、寒暖和全局损益共同判断；戊虽司令出见仍可置而弗论 | 见字或透出便有效；司令干出现便日主强 |
| 三命开头逐月文字 | 完整12月，32项时长，寅月艮土5、丙5、甲20 | 与滴天髓原注为同一体系；艮土已经指定为某一阴阳干 |
| 三命随后数字表 | 完整12月，37项时长，寅月已土7、丙5、甲18；按原顺序保留 | 表列顺序就是现代可用的节后时段顺序 |
| 三命章末醉醒子曰与评议 | 完整保留对机械分日的批评及主客、初中末气浅深的条件 | 删除限制后将前面数字当作无争议的有效司令定理 |

ML02原文仍有立春后六日戊土司令及寒土喜火的具体判断。不同来源的数字会使同一“六日”落在不同名义条目，不能择取有利于该例的表提升旺衰分数。只有四柱的18个原始反例没有节后日序；即便具备出生瞬间，也仍须明确采用的原典、计日边界与有效力量规则。

## 保留数字不一致与未知身份

逐项核对报告（本地数据：`validation/bazi-month-duty-sources-first-v1.json.gz`）将24个月条、69项时长与捕获全文逐项比较，均一致。数字文本自身保留以下待核点：随后表中酉月20＋7＋5＝32，子月18＋5＋3＝26；年度句按甲丙庚壬各35、乙丁辛癸各35、戊与原字已各50计算为380，句末却写360。它们是已核实的数字文本算术差异，本轮没有书影证据证明原刊也如此，更不能擅改数字使之通过。

`computed_literal_duration_sum`是按所存数字相加，`equals_nominal_thirty_days`仅作与30的算术比较；不是判定原书某月错误或强行缩放到30。年度`matches=false`同样是来源数字间的不相等，不是本命历法算错，也不换算为有效力量或预测概率。

艮土、坤土、原字已等保持`canonical_stem=null`，其实际透藏位置也为`null`，不当作已确认缺少。明确的十干才按原局逐柱列`visible_positions`和`hidden_positions`。例如卯月数字表还列甲、癸，而现行藏干目录卯仅乙；本字段列出这种差别，不添加甲癸藏干或根预算，也不据此断言某一目录已由原典证实。

后续补入[CADAL完整书影见证](bazi-month-duty-scan.md)：原PDF66–73完整章节中，69项时长及32／26／380的算术差异仍在；六处己／己土读法单列，并保留原数字资料的已及未知身份。该见证与识典底本的确切复本关系未建立，因此本页原数字数据和其校勘状态不改写成已完成对应底本核验；新字段位于同次`source_reference.scanned_witness`，仍未采用日期表或改动有效司令。

## 计算、交付与解释验收

10个入口的REST、原生MCP协议和CLI均已核对同一字段。314条旧材料逐例比较新增证据前后的取证结果：移除这一处新增来源字段和明确补正的通关引用页200／印刷58后，旧字段和值均完全相同。该比较使用保留的三个旧文件及当前未变依赖，不冒充另一套独立历史运行环境。完整旺衰回放（本地数据：`validation/bazi-month-duty-source-corpus-current-v1.json.gz`）仍为24组314条、268个不同输入、25个不同输入不符。

通关来源原来漏列PDF200；原页仍有隔位、印受坏、运来引通等末例，因此补入PDF200及印刷58。这里只更正引用范围，未改路径几何、合绊、冲损或有效通关结论。

首次来源预检因引句爲／為不相同失败，原件及校正均保留。首次自动核对又因“八月，建酉”等原文标点而拒绝，保留原执行器及错误（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/source-auditor-first-failure.log`）；解析器现允许该标点，仍要求12月完整、顺序正确、每项名称及数字相符，没有删月或改数值。

```bash
uv run --locked --extra dev python scripts/audit_bazi_month_duty_sources.py --output /tmp/bazi-month-duty-source-replay.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_month_duty_sources.py
```

本轮没有启动新模型；当前源码的自由文本解释仍需真实模型与独立外部审阅。既有三轮11例的首败与逐句记录继续保留，不能将旧运行版本的局部通过当成新增证据层已经完成解释验收。没有真实事前预测及独立结果，现实预测继续`not_tested`；完整目标尚未完成。

本地相关检查为261项通过；随后来源身份与原始页面提取链的补充核对通过，未改变资料或运行规则。三端检查覆盖综合和九专题。共享读证说明的来源散列已按生成器同步；首次清单过期检查仍保留。

打包先后暴露了macOS临时目录规范路径比较错误、共享清单及其他模块源文件在构建后变化的问题，原失败没有改记通过。另行冻结874项构建输入（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/runtime-source-manifest.json`）和可携带源码包（本地数据：`../tests/fixtures/bazi_month_duty_sources_v1/runtime-source.tar.gz`），构建后逐项保持；所得包的838个Python／JSON文件与该快照相同，解包后27项本专题检查通过。这是冻结版本的本地分支验收，27项为前述261项的子集；没有发布，也不表示继续变化的整个工作树或部署已经验收。
