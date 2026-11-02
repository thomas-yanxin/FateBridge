---
name: onda-xingpan
description: 直接处理用户指定的人类图、星盘、八字、紫微本命与方法解读，包括河洛理数、邵子参评／金锁银匙、流派盘、关系盘及法达等技法；按实际主题读取相关证据，不自动扩展其他体系。普通生活问题由相应主题主持，时间选择共享参考。
---

# 命盘与指定方法解读

让用户看清「这张盘最突出的两三处是什么、它们有什么张力、可以怎样拿现实经验对照」。先回答所问主题，再给盘面依据；日月上升是入口，不能用一句太阳星座性格替代整张盘。

## 共用范围与安全

先读短的[咨询核心](../_shared/consultation-core.md)。主题重叠或扩展才查[范围选择](../_shared/consultation-routing.md)，涉及目标时段才查[时间选择](../_shared/timing-selection.md)；遇生死、临床判断或医疗择时先按[硬边界](../_shared/safety-boundaries.md)停止相关计算。

## 引用路径与按需资料

发现入口可能是软链接。先进入入口目录，以 shell 内建 `pwd -P` 取得真实目录，再解析相对引用；不要裁剪 `.agents/skills/onda-*` 的字符串父目录。

- 参数不清楚或需要完整交付时定位：[../_shared/fatebridge-engine.md](../_shared/fatebridge-engine.md)
- 需要表达或来源细则时定位：[../_shared/onda-counsel.md](../_shared/onda-counsel.md)
- 主题重叠或扩展时定位：[../../docs/scenario-routing.md](../../docs/scenario-routing.md)

所有位置、宫位、相位、尊贵与中点交给引擎。默认现代本命盘；用户已明确流派或盘型时直接按其选择，不先展示工具菜单。

## 指定中式方法

太乙年／月／日／时计、三式合参及其技法核对由[问事与占式入口](../onda-zhanbu/SKILL.md)处理，读取其中太乙参考；用户只核对已给日期或结果时，不另索现实占问或出生资料。指定占式的方法名不自动变成本命盘请求。

明确六壬／金口诀时，即使只是核对起课技法、没有现实问事，也读取[问事与占卜](../onda-zhanbu/SKILL.md)及[六壬与金口诀取证](../onda-zhanbu/references/ren-evidence.md)，沿用已给时间、配置及同次结果；不为进入该分支另要现实问题。

紫微规则与四化表来源可用已声明的 `ziwei_rules` 核对实际配置；查规则不另排命盘，也不将表项核对扩为整书认证。

明确河洛理数用 `heluo`，邵子参评／金锁银匙用 `canping`；按[数术取证](references/numerology.md)区分起数、具名配运和原典序号，只解释同次实际卦爻、编号和选文。

原典命例已明确四柱时，用 `bazi_source_compare` 取得当前旺衰和全部同柱编释，不反推生日、补生时或选择有利标注。差异、未知与未收录须按实际返回解释，相符也不能认证全书或现实预测。

明确要求原始八字用 `bazi_birth`，综合八字结构用 `analyze_destiny`，紫微本命用 `ziwei_birth`；紫微动态用 `ziwei_horoscope`。宿曜／宿占按[宿曜取证](../_shared/sukuyo-evidence.md)区分历日27宿、原典异表和物理天文28宿。明确法达用 `firdaria`，八字大运／流年用 `dayun_analysis`／`liunian_analysis`，按共享时间选择核对所需目标。指定一法不先跑其他体系。跨体系主题解释按对应主题主持并复用已有结果。

## 选择实际盘型

| 用户所问 | 主证工具 | 本次应让用户看到什么 |
| --- | --- | --- |
| 本命、日月上升、性格或某个生活主题 | `astro_chart` | 与主题有关的行星落点、角度与相位，连成两三条可对照的特点 |
| 河洛理数／邵子参评／金锁银匙 | `heluo`／`canping`（按所选方法） | 起数、实际卦爻或编号、选文与来源；条件未定时保留未知 |
| 人类图／BodyGraph | `human_design` | 按[人类图取证](references/human-design.md)解释实际类型、权威、定义和Profile；不套太阳时与西占宫位 |
| 希腊／古典盘 | `astro_hellen_chart` | 实际昼夜属性、上升主星与角宫星；按问题进一步取古典条件 |
| 果老星宗 | `astro_guolao_chart` | 按[果老取证](references/guolao-evidence.md)读七政四余、宫主度主与格局；核对底本顺数安命所用的研究输入，命度与历史宿界仍未验收 |
| 印度盘 | `astro_india_chart` | 实际恒星黄道、岁差参数、上升宿与月宿；没有返回的分盘或达沙不能补写 |
| 德国／中点盘 | `astro_germany_chart` | 按[汉堡中点取证](references/hamburg-evidence.md)读原生因素、限定原文解释、生时误差及指定时刻太阳弧；本命与推运层分开 |
| 13 扇区盘 | `astro_chart13` | 实际 `thirteen_sectors`、`sector13_evidence` 与生时误差；这是自定义等分规则，不当作天文学星座边界 |
| 两人的比较、互动或组合盘 | `astro_relative_chart` | 先确认盘型，再解释双方实际交互相位或第三盘，区分各自本命特点 |
| 未来阶段、行运、返照与推运 | `western_timing_analysis` | 按 onda-shiyun 处理所问时间范围；不从静态本命盘编出日期 |

`astro_chart` 的 `chart_variant` 与上述专用工具等价，二选一即可。流派名不代表所有该流派技法均已覆盖，解读只到本次返回的盘层。

## 输入与时间精度

使用已确认的公历日期、出生小时／分钟、出生地与出生时区。出生时刻未知不能填中午或 0；只有时段时，保留上升、宫位和边界不确定性，用户授权后才做假设时刻比较。

- 核心本命／流派盘的坐标是可选参数：已支持的 `birth_place` 可由引擎解析。已有明确城市即可按实际 Schema 调用，核对返回坐标、时区和精度；解析不出或所问需要更精确地点时再补，不把示例坐标写成用户资料。
- 关系盘两方分别要求经纬度；西占推运也要求经纬度。缺少该工具必需位置资料时一次核对。
- 西占默认使用记录的民用钟时，`use_true_solar_time=false`；中式工具的真太阳时策略不能直接复制过来。用户明确选择太阳时才改，跨体系对照保留各自时钟。
- 宫制 `hsys` 与黄道 `zodiacal` 按实际盘型默认及用户选择处理，返回的 `chart_profile` 才是本次口径。不要为显得完整随意切换宫制重算。
- 更正分钟时重建受影响输入，沿用 `trace_id`／`parent_run_id`，先比较上升、MC和宫位边界，再比较主题解释；只解释已有结果不重算。

## 从字段到解读

普通首轮使用工具已验证的精简 `fields`、`strict_fields=true`、`include_snapshot_text=false`。下表是按问题扩展的取证地图，不是全部必读清单。当前摘要没包含某个维度，不能把没读取当作不存在；按需要补取。已有同 run 的 `result_delivery` 时读其字段／分页，不重新计算；首轮被投影排除的数据不会凭分页恢复。

| 想说明的内容 | 实际字段 | 如何转换成用户可用的信息 |
| --- | --- | --- |
| 日月上升的区别 | `planets` 中 id 为 Sun／Moon 的记录、`angles.ascendant`、`interpretation` | 分开说明行动关注、情绪需要与外在呈现，再点出共同处或张力；不把引擎文案当现实人格测验 |
| 所问领域的重心 | 相关星体的 `house/sign_zh/degree_in_sign`，必要时 `houses` | 说明重点落在哪类生活安排；不能只凭一个落宫指定职业或事件 |
| 相位如何牵动这个主题 | `aspects` 的 `planet_a/planet_b/aspect/orb` | 选与问题有关的两端和实际容许度，解释配合或拉扯。列表首项通常最紧，不自动最相关；未返回入相／出相时不声称已有 |
| 整体元素／模式 | `element_balance`、`modality_balance`、`balance_basis` | 只作盘内分布背景，说明统计口径；不把占星元素当八字喜用，也不把计数当能力评分 |
| 古典条件（点名福点／精神点、朔望、命主力主、恒星或行星时读[按需卡](../_shared/western-deep-evidence.md)） | `classical.sect/planets/dispositors/topic_almutens`、`classical_patterns` | 围绕所问宫位与星体读尊贵、定位链和具体条件；只展开相关条目，不靠术语堆叠增加分量 |
| 特定流派或中点 | `hellenistic`、`india`、`guolao`、`thirteen_sectors` 或 `midpoints/midpoint_aspects` | 先说实际多了哪层证据，再说它是否改变本次解释；未命中或未覆盖就明确保留 |
| 实际模型与钟时 | `person_info`、`chart_profile`、`run_metadata` | 核对实际出生时刻、时区、地点、宫制、黄道和星历模型。地点近似、星历近似与时间未知分开说明 |

## 关系盘的读法

仅选择两人关系盘或用户追问关系盘细节时读取。 [读取本分支](references/relationship-reading.md)。

## 交付与复核

普通短答通常 200–300 字：先讲所问主题最突出的特点，把两三项盘面事实自然嵌入说明，再给一项现实中可观察／尝试的安排。用户要详细盘才展开简短落点表或相位表；表中同时保留星体、宫位／相位和生活含义，后接连贯解释，不只交原始 JSON。

有多个读法时说明「哪个配置支持什么、另一配置怎样形成拉扯」，不抹成一个统一人格结论。用户限定西占时按其范围；专题综合按共享选择规则加入有价值的其他视角，已有结果直接复用；共同描述用于文化视角对照，不增加统计置信度。

发送前核对：每条判断是否有对应落点；本命与两人互动是否分清；关系背景是否沿用用户事实；没有实测星盘图时不画示意图冒充精确盘轮。上升／宫位敏感或近似星历限制在相关处简述一次。不作医疗／心理诊断，不以灾祸、必然婚恋结果或职业定命解盘。

用户要求完整 JSON、完整盘或完整文件时，首次 `fields=null`，保留默认响应预算，再按共享层读取同 run 的 `result_delivery`；核对业务 payload 的 SHA-256，不重新排盘补全文。

## 可复核示例

仅需要本地 CLI 复核时使用；已有 MCP 定义直接调用。 [读取本分支](references/examples.md)。

## 印度占星视角

印度／吠陀／Jyotish 本命用 `astro_india_chart`；明确 D9、D10 使用 `divisions`，D1 始终保留。先读[印占取证](../_shared/vedic-evidence.md)，按 `natal/career/relationship/divisions` 卡选首次字段。Vimshottari 用 `astro_vimshottari` 的 `stage` 卡，不从本命静态盘补写达沙日期。
