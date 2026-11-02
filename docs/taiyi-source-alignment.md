# 太乙原表位置与两算校读

count_source_assessment把同次盘的实际位置与两算、卷三原表所读位置与两算、按源表位置重走卷二通则的算路分别交付。源位置重算是校勘用的条件计算，当前盘的二目、算数、将位和断法仍使用原来实际返回的核心，没有以原表值覆盖算路或用当前算法回写原文。

## 先核位置，再核加总

[《太乙金镜式经》卷二](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷02#推太乙運式法)以二目所在起算，正宫按本数、间神起一，数至太乙前；同宫取本宫数的所选阅读另有既有课例支持。[卷三立成表](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03)有完整阴阳各72局，原来冻结的288项主客算继续保留，新增太乙、文昌、始击、计神四位置共576项。

所选源层有573/576位置相符，3处始击位置不同：阴37原表大威午、当前大武坤；阴43原表大武坤、当前大神巳；阴44原表太蔟酉、当前大武坤。阴37两算仍相同，因此只核两算不能证明上游目位相同。

原有两算保持277/288相符及11项分歧；以原表位置按所选通则重算是另一组288次检查，其中278项与表算相符、10项不合。阴43、44把所读原表始击位置代入通则后能重得表算38、31，说明这两项算差与上游位置有关，未裁定哪一层应改。阴37原表目午按通则得27而表算25，差异以前被相同的实际算25遮住。阴46原表目乾、太乙一宫，同宫通则得1，表算2继续保留，不能以源目不同笼统解释。

这些是不同观察对象，不相加为准确率，也不据此宣布原书错误。原表可能有版本、排印、转录或未明适用条件；完整四将、古历与断语仍待独立验收。

## 原转录与书影分别保留

[CADAL06056494四库本书影](https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu)图111的阳41计神为戌，旧转录为戊；图123的阴59文昌语义索引为大炅，V18初录误写为大神，旧转录本已为大炅。阳41是转录/书影差异，阴59是本次录入错误，分别交付，不混作两项旧转录错误。原转录与初录均不删除。V18当时仅选读部分书影；V23已追加[完整144局六列语义核读](taiyi-native-columns.md)，巽神具体字形仍未逐字裁定。

初始清单（本地数据：`../tests/fixtures/taiyi_jinjing_v18/manifest.json`）在新组件实现前冻结144行原字及旧两算。手写加数补证（本地数据：`../tests/fixtures/taiyi_jinjing_v18/supplement-manifest.json`）另有12条算路检查，来源行与原字不变，不算新增历史课例。初录名表引句把原转录夘写成卯，映射均为卯；逐字订正（本地数据：`../tests/fixtures/taiyi_jinjing_v18/correction-manifest.json`）保留初录与独立卷二证明，没有改变位置、两算或名称映射。复核另冻结144行逐字校读（本地数据：`../tests/fixtures/taiyi_jinjing_v18/transcription-collation-manifest.json`），按已有卷三原文片段核验576位置，13行初录字面差异中12行为字形归一化、1行为阴59录入错误。此次校读发生在初次实现后，保留被中断的495项测试及原始快照，所选位置和所有数值结果未变。先前V1至V17所有材料、未决和验收范围继续保留。

运行目录由build_taiyi_source_alignment.py从冻结资料生成，--check检测漂移；不手工改运行表。规则作者FateBridge contributors，当前版本jinjing_core_table_alignment_v1@1.1.0；V23追加书影初录/订正指纹、本局页栏和六列来源层，原典作者、版本、来源和资料指纹随结果交付。

## 调用与解释

太乙count_sources、合参taiyi_count_sources为选字段视图，适用于年/月/日/时计循环核心；视图名不是请求参数。首读设strict_fields=true、include_snapshot_text=false，完整载荷仍通过同一次运行的result_delivery读取。当前字段路径在actual_path、actual_count_path、actual_marker_path中；源表重算算路仅在source_position_recount中。

出现差异时，pattern_summary.source_table_warning及文本快照同时给出范围；相符仅限所读四位置和两算。缺少明确阴阳、局序、完整核心、身份不一致或位置为空/多字符时保持not_assessed，不猜源行。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1938 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone +08:00 --no-use-true-solar-time --strict-fields \
  --fields taiyi.count_source_assessment taiyi.core_board
uv run --locked --extra dev python scripts/build_taiyi_source_alignment.py --check
uv run --locked --extra dev python scripts/audit_taiyi_source_alignment.py \
  --output /tmp/taiyi-source-alignment.json
```

审计仍退出1，原11项两算分歧未删除，完整古历与全书验收未通过。源表重算也不证明现实预测有效。

V24追加[始击同盘转盘算路](taiyi-shiji.md)：以实际计神加和德艮，逐步列出天地盘配对，零步和主客算分别解释；本盘始击与推步终位即使不同也保留双方。武经书影在阴37/43/44的18个选定字段支持当前核心，但未取代金镜四库原表，三处位置及11两算分歧继续未决。

V49补充[独立加数核查](taiyi-independent-arithmetic.md)：现有源位置重算复用生产函数，本轮另以冻结的累计和差分参照覆盖128种输入及全部288源算。程序数字与算路一致，原10处内部差异、11处实际表算差异和3处始击差异保留；本盘的重算字段本身不因此变成独立实现，软件对照也不增加古例。
