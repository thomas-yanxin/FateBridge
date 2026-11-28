# 奇门盘面证据

只对本次已读结果解释，沿用同一次 run。默认规则是时家转盘、中五寄坤二（`lodging_policy="kun2"`，`ju_method="zhirun"` 为置闰，`chaibu` 为另列的拆补约定）。`ju_term` 为定局用气，与 `calendar_policy.corrected_datetime` / 实际节气在置闰时可以不同；`rule_profiles.god`、`rule_profiles.season`、`rule_profiles.lodging` 标明实际采用口径，不得跨口径混读，也不将局部规则校对称为整部原典认证。

- **旬空与双支宫范围**：`xun_head` / `kongwang` 为时旬，`day_xun_head` / `day_kongwang` 为日旬；盘级 `void_palaces` 列出落空宫名，各宫顶层 `branches`、`hour_void_branches`、`day_void_branches` 及 `hour_void_scope` / `day_void_scope`（`"none"` | `"partial_branch"` | `"full_palace"`）直接标明单支空还是全宫空，禁止把双支宫的 `partial_branch` 说成全宫空，也不得混用时旬与日旬。
- **马星与真太阳时**：盘级 `horse_star` 与各宫 `is_horse_palace` 标出驿马所在宫。`qimen.calendar_policy`（含 `civil_datetime`、`corrected_datetime`、`hour_clock`、`day_boundary`、`solar_term_provider`，默认通过 `default_omit` 省略）可通过 `include=["qimen.calendar_policy"]` 或 `include=["*"]` 读取完整钟表与节气换算边界，不得自行按民用表时重算干支。
- **寄宫与天禽**：`zhifu.star` 保留天禽身份；当坤二等宫 `star="天芮"` 且 `hosted_stars` 含 `"天禽"` 时属正常寄宫，`heaven_stems` 与 `earth_stems` 同时保留主干与寄干（`hidden_stem` 为原宫寄干），解读格局时须同时核对主干与寄干。中宫在转盘下 `door`、`star`、`god`、`heaven_stem` 为 `null`，天禽与中干在所寄之宫读取。
- **宫级平铺证据（全部直接位于 `palaces[i]` 顶层，不额外嵌套子对象）**：
  - `palaces[i].door_palace_relation` 与 `palaces[i].door_pressure`：给出门宫生克及按歌诀门克宫判定的门迫标记；`door_pressure=false` 时仍需核对 `door_palace_relation`（宫克门等），`door_pressure=true` 不得美化为吉。
  - `palaces[i].star_season_state`：按 `rule_profiles.season`（默认 `yanyi_vol1_verse`，可选 `yanyi_vol3_table` / `yanyi_vol3_prose`）与实际月支计算九星旺相休囚死，不同口径不得混用。
  - `palaces[i].wonder_tombs` 与 `palaces[i].punishments`：分别给出该宫命中的天盘三奇入墓干与六仪击刑干（主干与寄干均核）。
  - `palaces[i].god` 与 `palaces[i].god_sequence_index`：`rule_profiles.god` 默认按卷三正文排布，不得套用六壬十二天将；未自动判定的神煞合奇门解忌条件不得臆断化解。
- **格局与同宫冲突（`patterns[]`）**：每条格局包含 `rule_id`、`name`、`palace`、`facts` 与可选 `coexisting_conflicts`。吉格若携带 `coexisting_conflicts`（如同宫门迫、三奇入墓、六仪击刑、青龙逃走、太白入荧、时旬空/半空），须并列说明冲突约束，禁止用“三奇得使”“天遁”等吉格名称覆盖同宫凶格或空亡。
- **日时干支与盘级结构**：
  - `stem_context.day`（`ganzhi`、`literal_stem`、`xun_head`）与 `stem_context.hour`（`ganzhi`、`literal_stem`、`effective_stem`、`xun_head`）列出日干与时干的字面与遁甲取值；甲干借直符六仪取用，不可自行替成戊干或日旬。
  - `structure` 分开给出 `hour_branch_tomb`、`stars_fuyin`、`stars_fanyin`、`doors_fuyin`、`doors_fanyin`、`stems_fuyin`、`stems_fanyin`、`five_not_meet`、`tian_xian_time`，不得把时格与星/门/干伏吟混为一谈。
- **源典分歧与边界**：盘级 `source_disagreements` 列出命中时局的古籍异文或口径分歧；`fushi_hexagram`（与宫级 `door_hexagram`）为派生参考卦；非转盘（`layout`）与非 `kun2` 寄宫约定（`lodging_policy`）不作支持。
- **交付要求**：结合 `assessment.calculation_scope` 与 `assessment.classical_conformance` 确认本次计算范围，先述相关宫 `palaces[i]` 实际组合、`patterns[].coexisting_conflicts` 与 `hour_void_scope` / `day_void_scope`，再给可核实条件，将吉凶限定在对应盘面事实内。
