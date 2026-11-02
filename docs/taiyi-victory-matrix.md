# 太乙三门五将胜败钤逐栏核对

`victory_matrix_assessment`以同次盘的文昌十六神位置和太乙宫数，回引《太乙金镜式经》四库本卷三对应格。128格全部纳入；原条件栏、结果栏、空栏、缺字及书影页栏位置分别保留。它补足此前未交付的整表参照，并把原格文字与当前盘实际几何分开核对。

## 来源与读表

[卷三转录](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03#太乙三門五將立成勝敗鈐)将表格压成连续文字，不能按空格可靠拆出128格。[CADAL06056494四库本书影](https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu)97页表头及97—105页全表给出四栏布局：每神先列太乙一至四宫条件，再列六至九宫条件，再列对应的两栏结果。每栏四个上下位置，共十六神、八宫。

实施前清单（本地数据：`../tests/fixtures/taiyi_jinjing_v20/manifest.json`）冻结九页书影、128格人工录文、旧网页转录和校读原则；预期录文没有由生产公式生成。每栏`locator`记录`scan_page`、从右数栏及从上数位置。并行小字用“／”分隔；分号只是编辑分隔，不表示各句必须合取。

吕申九宫、大威九宫、大武九宫的结果栏以及大威三宫的条件栏共四个空栏保留为null；阳德九宫保留“客大〔缺〕”。大威九宫“先起败囚”、大武九宫“客大胜”等仍在书影所见条件栏，不擅自挪到结果栏补空。结果栏里的“小将囚”等也不删去。

卷二十六神名位补核本表天目为文昌的对应位置；卷三“大炅”与卷二“太炅”均对应巽，“大神”与卷二“太神”对应巳。这个对应只用于本表，不能扩展成卷四其他语境的天目、地目全局别名。

## 当前盘怎样对照

`source_cell`只回引对应原栏；`actual_geometry`另列本盘文昌、主客大小将的实际位置、数值字段路径、十六神环位距离及同宫、对宫、内外邻接。中五和缺失将位保持未知，不制造环位。计数入口只接受单个十六神和严格整数的非中五太乙宫数；空字符串、连续位置片段、布尔值及浮点宫数被拒绝。查表遇到无效位置返回not_assessed，不因子串包含关系误接收或异常退出。

`clauses`保留两栏所有分句。只有可单独读取的“天目／大将／参将／小将／大小将”加“内迫／外迫／迫／囚／格”作几何比较。“天目格”只比较是否正对，不给本盘文昌强添一个“格”模式；既有格、对异称仍由opposition_assessment负责。囚迫、关囚、门具将发及其他复合文字完整保留为未裁定片段。

天目可按本表文昌对应来比较；未写客主的将星同时给出主、客候选，不因某一方较合便裁定原文指代。`comparison_summary`分开列出天目几何相符、不同、未知，将星未定客主、未决分句、空栏和缺文。`whole_cell_conformance_assessed=false`，不把某条几何相符当整格符合。

例如武德申、太乙八子，原条件栏为“大将迫”。依现用卷二计数通则主算为8，主大将8子与太乙同宫，当前几何为囚、非迫。该主方候选差异保留；原文未标客主，也不因此改主算、改将位或直接应用“主小胜”。

## 全表审计仍有差异

全128格查表覆盖与计算准确率分开。初次全表几何审计中：

- 可单独读取的33条天目几何文字，27条与现用环位相符，6条不同：酉三、子四、丑七、巳二、午八、坤六。原栏与本盘事实均保留，尚不能裁为生产计算或原书某一方错误。
- 51条未标客主的将星文字，展开为61个主方候选几何谓词时，39相符、17不同、5未知；这只检验一种候选，不裁定客主，也不是原典准确率。表未给客目，整表审计没有猜客将。
- 76个复合、门法或其他未裁分句，四个空栏、一格缺字继续在总表内。未实现部分没有从分母删掉。

128格是录文与检索覆盖，不是128个有日期古例；抄录字段计入计算命中的数量为0。门盘、客目、时间层适用及完整断法未核定，`table_applicability_verified=false`、`source_outcome_applied=false`。原栏胜败不作为当前盘总体结论，现实效力仍未检验。

## 读取与验证

太乙`victory_matrix`、三式`taiyi_victory_matrix`是选字段视图名，不能作为计算参数。首读选取源格、实际几何、比较摘要、规则版本与范围；完整分句可另选`taiyi.victory_matrix_assessment.clauses`。如出现result_delivery，读取同一run及其摘要指纹，不另起盘补全文。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone +08:00 --calculation-mode year --no-use-true-solar-time \
  --strict-fields --fields taiyi.victory_matrix_assessment taiyi.calendar_summary
uv run --locked --extra dev python scripts/build_taiyi_victory_matrix.py --check
uv run --locked --extra dev python scripts/audit_taiyi_victory_matrix.py \
  --output /tmp/taiyi-victory-matrix.json
```

规则作者FateBridge contributors，版本`jinjing_victory_matrix_columns_v1@1.0.0`；运行资料返回作者、来源与两层指纹。源审计继续退出1。旧空间模式、主客算、三门五将条件合取及此前原典差异不因增加本表而通过；完整古历、全书、三式联合断法、自由解释盲审和远程部署验收仍须分别完成。

V21另冻结[明钞本全32物理栏初录](taiyi-matrix-collation.md)及同版神名位。六处争议词句均在对应神名的四宫半表栏可见，但逐宫归属尚未裁定，新增几何相符数为0；四库原128格、六处差异、四空栏和缺字均不覆盖。此批只增加校勘资料与审计工具，没有据同词命中修改生产计算。
