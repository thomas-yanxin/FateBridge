# 始击推步：计神加和德，逐步核对天地盘

`shiji_derivation`显示本盘文昌、计神如何推出始击。计算采用《太乙金镜式经》卷二的“计神加和德”，以和德艮为地盘起点，顺布十六神，读取天盘文昌所临的地盘位置。它与主客两算分别计算，阴阳两遁使用同一转盘方向。

## 规则与版本

四库本卷二书影78页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/jinjing-native-page78.png`）、79页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/jinjing-native-page79.png`）跨页写出计神加和德、求文昌所临宫；图书集成第687卷所在原册68页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/tushu-page68.jpg`）明确顺行十六神、取天目所临之下，并给出辛丑的给定位置例。原例文昌丑、计神丑，始击为艮；本批没有将其猜换为某个公元年或日期。

这个文昌、计神同位的例子不能单独区分正反公式；方向还须依据正文的加临主体、顺行和读取哪一盘。三次手工推步用于检查该阅读的执行，不充作三条独立原典方向课例。

明钞本36页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/ncl-page36.png`）第五条写计神加和德及艮为鬼门，未写出四库本“求文昌所临宫”这一短句。两本不冒认逐字同文。明钞本54页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/ncl-page54.png`）在矩阵末栏后接“五子元积年立成法”、署卷三终，55页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/ncl-page55.jpg`）起卷四；此处没有插入四库的144局表。这只是所读位置的版本结构观察，不证明全书别处没有该表，也不据此推断版本谱系或删去四库要求。

规则作者FateBridge contributors，版本`jinjing_shiji_rotation_v1@1.0.0`；原典王希明编录，图书集成规则另作补证。来源清单（本地数据：`../tests/fixtures/taiyi_jinjing_v24/manifest.json`）在本批新实现前封存书影、原网页、给定位置例和手工配对；读者为已知原代码的Codex代理，没有独立人类专家覆核，也不是盲读。

## 步数怎样读取

起点的天盘神为本盘计神，地盘为艮，记为第0步。每前进一位，两盘都顺行一位，直到天盘到达文昌。`step_count`是间隔数，`pairs`保留起点和终点；不是包含起神的计数，更不是主算或客算。

例如阴37：文昌寅、计神申。第0步为申／艮，顺行8个间隔后，天盘寅对应地盘坤，始击取坤。这里有9条天地配对记录，但步数是8。文昌和计神同位时，只有起点一条记录、间隔0，始击仍为艮。

`wenchang_path`、`jishen_path`、`actual_path`回指同一盘的实际字段。`derived_shiji`是本次转盘终位，`actual_shiji`是当前盘已返回值；二者即使不同也并列保留，以`matches_actual=false`显示，不将前者写回后者。缺失或多字符位置返回`not_assessed`，不推测位置。

## 三处原表分歧继续保留

本批核读《武经总要》相应书影：114页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/wujing-native-page114.png`）、115页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/wujing-native-page115.png`）阴37、120页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/wujing-native-page120.png`）阴43、121页（本地数据：`../tests/fixtures/taiyi_jinjing_v24/wujing-native-page121.png`）阴44。六个字段共18项与当前核心相符，但它仍是旁证，没有取代指定的金镜四库本。

| 局 | 本盘文昌／计神 | 四库金镜表：始击／客算 | 武经书影：始击／客算 | 当前推步：始击／客算 |
| --- | --- | --- | --- | --- |
| 阴37 | 寅／申 | 午／25 | 坤／25 | 坤／25 |
| 阴43 | 午／寅 | 坤／38 | 巳／1 | 巳／1 |
| 阴44 | 未／丑 | 酉／31 | 坤／38 | 坤／38 |

这组证据支持当前转盘方向，但不足以裁定金镜表的差异应如何改字或归因。阴37的客算相同，仍不能证明始击相同。旧三处始击、11项两算及10项源位置通则重算分歧继续存在，见[原表位置与两算校读](taiyi-source-alignment.md)。

给定位置原例1条、三次手工规则应用和25条天地配对分别统计；后三项来自旧争议行，不是新增独立古例。没有把旁证相符计成金镜原典通过，也没有修改现有数值以追平表文。

## 调用与交付

太乙`shiji_derivation`、合参`taiyi_shiji_derivation`是已发布字段视图，覆盖年、月、日、时计；视图名不是请求参数。首读保留当前实际二目/计神、逐步配对和原表差异摘要，完整结果仍从同一run读取。

```sh
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone +08:00 --no-use-true-solar-time --strict-fields \
  --fields taiyi.wenchang_palace taiyi.core_board.jishen taiyi.core_board.shiji \
  taiyi.shiji_derivation taiyi.count_source_assessment.summary
uv run --locked --extra dev python scripts/audit_taiyi_shiji.py \
  --output /tmp/taiyi-shiji.json
uv run --locked --extra dev pytest tests/test_taiyi_shiji.py
```

文本快照读取同一份推步事实，明确天盘、地盘、间隔数和实际始击，不由语言模型重算盘。数值核心及旧判断保持；这份确定性解释不替代真实模型自由解读盲测、完整古历和全书验收。工程与来源记录（本地数据：`validation/taiyi-jinjing-v24/README.md`）。
