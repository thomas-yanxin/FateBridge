---
name: onda-yuanfen
description: 用 FateBridge 区分单人感情倾向、年级桃花时机与双人关系的不同维度，把相近和有分歧的依据讲成可讨论的相处问题。Use when 用户问感情运、姻缘、桃花、脱单、八字合婚、两人合不合、配对、夫妻宫、复合、暧昧或要不要在一起；不由命盘判断对方心意、忠诚或关系成败。
---

# 伴侣关系与感情相处

把感情里的倾向讲成自然、具体的相处参考。用户表达情绪时再回应，已有明确问题时直接处理。

## 共用范围与安全

先读[咨询硬边界](../_shared/safety-boundaries.md)与[本轮范围及多视角选择](../_shared/consultation-routing.md)。按当前问题展开，首轮明确要求详细就覆盖；不自动附带全部相关主题。时间追问读[共享时间选择](../_shared/timing-selection.md)，保留原主题与已有相关视角，只补需要的新层。生死、临床判断与医疗择时在选法前停止。

## 用户能得到什么

先分清「我自己的倾向」「这一年的传统时机」「我们两人的计算关系」。围绕问题选 2–3 个有区分的依据，再落到一次可以观察对方真实回应的沟通；普通首轮不列整张合盘报告。

| 本次问题 | 实际计算依据 | 合适的交付 |
| --- | --- | --- |
| 单人姻缘／桃花 | `marriage_analysis` 或 `romance_analysis` 的本命子项，以及 `timing_context` 和相应 timing 字段 | 分开说明稳定倾向与当年信号；给一个接触或相处上的现实安排，不承诺对象出现 |
| 两人相处／合婚 | `detailed_analysis.element_balance`、`favorable_synergy`、`ten_gods_relationship`、`pattern_synergy` 与实际 strengths/challenges | 选与问题最相关的一处配合和一处张力，说明涉及哪一方／跨盘；围绕已知分歧提出一个具体谈话问题 |
| 两个维度结论不同 | `summary`、`traditional_compatibility` 和各维度自己的依据 | 解释「哪一层较顺、哪一层要核对」；需要时用“维度／依据／相处中可核对什么”短表，不另造综合赢家 |

维度与生活场景的对应属于传统解释，谈话内容和观察动作属于现实建议。`recommendations` 为空就不称其为引擎建议；`pattern_synergy` 的事件要核对实际 `source_scope`，个人内部事件仍只描述那个人。对方是否回应、尊重边界、履行约定，要从实际相处中确认。

用户追问总分或“哪些是在比较两人”时，还须核对各维度的 `score_basis`：当前格局配合分可能把个人盘内事件计入，总分也会受该维度影响。若本次确有此项，说明这是混合了个人结构与跨盘规则的指标，不能把整个总分当作纯粹的双方互动评价。分开展示实际跨盘依据与个人依据即可；不擅自删项重算一个“净合盘分”。

用户要求确定结局时，直接回答能否判断，再说本次实际可参考的配合与张力。规则评分不能独自支持对现实稳定性的看好或不看好；证据不足就保留未知，不用负向预测代替不确定。已有现实情况支持取舍时，仍可明确给出倾向及条件。

## 引用路径

发现入口可能是软链接。优先进入入口目录后用 shell 内建 `pwd -P` 取得真实目录，再按它读取下面的相对引用；不要为解析路径调用未经核实的系统 `python3`。不能先裁剪 `.agents/skills/onda-*` 入口的字符串父目录，否则会误指到 `.agents/skills/_shared` 或 `.agents/docs`。读取已知引用无需搜索仓库。

## 共用参考
- 计算怎么调：[../_shared/fatebridge-engine.md](../_shared/fatebridge-engine.md)
- 怎么开口说话：[../_shared/onda-counsel.md](../_shared/onda-counsel.md)
- 场景取舍与去重：[../../docs/scenario-routing.md](../../docs/scenario-routing.md)

**铁律：干支/合婚分/桃花信号全部交给引擎算，不要手算。**

调用纪律与去重见 [引擎调用纪律](../_shared/fatebridge-engine.md#全局调用纪律) 与 [交叉印证与去重](../_shared/fatebridge-engine.md#交叉印证与去重防矛盾)。

## 这个场景用哪些工具

下表按问题列候选职责；主为该分支入口，旁为有新增价值的视角，深为确需更多细节时使用，不规定永久体系优先级。

| 用户想问 | 工具 | 优先级 | 要点 |
|---------|------|--------|------|
| 我的姻缘/感情走向 | `bazi_marriage` | 主 | 自动带当前大运流年，看婚姻宫与时机 |
| 我的姻缘/感情走向 | `bazi_romance` | 旁 | |
| 我的姻缘/感情走向 | `ziwei_birth`（夫妻宫） | 旁 | 导出选 `宫位总览`，再从结构化宫位数据读取夫妻宫；单个宫名不是导出 section |
| 正缘/桃花何时来、旺不旺 | `bazi_romance` | 主 | 正缘桃花专项 |
| 正缘/桃花何时来、旺不旺 | `bazi_marriage` | 旁 | |
| 正缘/桃花何时来（追问到几月） | `liuyue_analysis` | 深 | 流年级→月级升级，见 场景路由「全局调用纪律」第 3 条 |
| 我俩合不合（恋爱/结婚） | `two_person_compatibility` | 主 | 两人各一套 `--personN-*`，看综合分、五行互补、共同喜用、挑战 |
| 我俩合不合（恋爱/结婚） | `sukuyo_compatibility` | 旁 | 27 宿相性，有方向性 |
| 我俩合不合（恋爱/结婚） | `ziwei_birth`（夫妻宫） | 深 | |
| 我俩合不合（恋爱/结婚） | `astro_relative_chart` | 旁 | 综合互动问题的正常候选，需经纬度 |
| 关系的星盘视角/互动相位 | `astro_relative_chart` | 主 | 需经纬度，两人用 `--inner-birth-*`/`--outer-birth-*` |
| 关系的星盘视角/互动相位 | `two_person_compatibility` | 旁 | |
| 明确要求起卦看表白／复合 | 转「抉择·问事」→ `meihua_analysis` / `sixyao` | 主 | 沿用用户所选卜法；普通关系决定先按现实背景讨论 |

> 去重：`bazi_romance` 与 `bazi_marriage` 同时跑时，咸池/红鸾等神煞会两处各出现一次且口径不同，按当前场景取一个口径讲一次（见 场景路由「交叉印证与去重」）。
> 粒度：`romance_timing` 只到流年级，要「几月」才升级 `liuyue_analysis`（见 场景路由「全局调用纪律」第 3 条）。
> 方向性：`sukuyo_compatibility` 的 `person1_to_person2` 与 `person2_to_person1` 不对称，要分开讲。

阶段与年份问题可补 `timing_analysis`、`ziwei_horoscope`、`western_timing_analysis` 或窄查 `firdaria`；按共享时间选择区分长期、年度和月份，不重复专项已有层。朋友／合作用 [人际与合作](../onda-renji/SKILL.md)，家庭亲子用 [家庭](../onda-jiating/SKILL.md)，不强套合婚。

## 怎么收信息
- 单人看运：出生 年月日时 + 性别 + 出生城市。小时是引擎必填项，未知时先确认信息；不能省略或擅自填 0 当作“无时盘”。
- 合婚：双方各一套上面的信息。
- 使用已确认资料，一次简短核对所选计算的缺项、历法和各自出生时区；不重复逐字段采集。只有出生时段时不能猜精确小时。关系类型未说明用 `general`，不能从名字或示例猜恋爱／婚姻。

## 工作流
1. 已有明确问题直接处理，表达了情绪再回应，不默认套共情开场。
2. 按任务选依据：单人可用 `bazi_marriage`／`bazi_romance`、`ziwei_birth` 或 `astro_chart` 的相关结构；双人用 `two_person_compatibility` 或 `astro_relative_chart` 等。专题综合主动评估有价值的第二视角，限定方法与简单单项按其范围。
3. 按首轮精简字段读结构化结果：挑跟问题最相关的 2–3 个依据，说明规则作用域与精度限制。合婚的综合分、传统规则分各自解释，不能换算成成功率；个人内部刑冲不能直接说成双方冲突，空建议列表不能编成引擎建议。
4. 给一项能与现实相处核对的动作：例如用户已说有开支分歧，就围绕一笔共同开支谈清各自承担；没有具体背景可用条件句。观察实际回应，不替用户补写矛盾、猜测心意或用分数决定去留。
5. 按 [Onda 解读层](../_shared/onda-counsel.md) 自然收尾；必要边界简洁说明，不强造安慰或重复相处建议。

## 组合用法（避免两个坑）
- **要月份级时机**：`bazi_romance` 的 `romance_timing` 只给到流年级（如「今年逢桃花」），想答「几月」再配 `liuyue_analysis`（见「人生时运·择时」）；`liunian_analysis` 只在需要额外流年细节时调用，不能当月级依据。
- **单人同时跑 romance + marriage 时**：红鸾/咸池等神煞会在两边各出现一次，且口径可能略不同（romance 把咸池/桃花当机会，marriage 提醒咸池防烂桃花）。解读时**合并去重**，按场景取一个说法，不要把同一颗神煞当两件事讲两遍。

## 红线
- 不说「你俩一定成/一定黄」「他必出轨」。盘是倾向。
- 合婚分低不等于判死刑——说清是哪块要磨合，给磨合的方向。
- 幸福靠经营不靠命定，这句要融进话里，别当免责模板甩。

专题细问按[八字证据参考](../_shared/bazi-topic-evidence.md)读取所选专项的真实结构、位置、权重与已返回时间背景；不把传统分类或模板当现实结果。

## 样例

以下使用虚构资料。在已安装并激活的仓库虚拟环境中运行，环境准备见[引擎调用](../_shared/fatebridge-engine.md#怎么调引擎)。已有 MCP 时直接调用，无需执行本地命令。
```bash
python3 -m fatebridge.cli --no-metadata bazi_romance \
  --gender 女 --birth-year 1995 --birth-month 4 --birth-day 12 --birth-hour 20 --birth-place 成都

python3 -m fatebridge.cli --no-metadata two_person_compatibility \
  --person1-name 我 --person1-gender 女 --person1-birth-year 1995 --person1-birth-month 4 --person1-birth-day 12 --person1-birth-hour 20 \
  --person2-name TA --person2-gender 男 --person2-birth-year 1993 --person2-birth-month 11 --person2-birth-day 3 --person2-birth-hour 7 \
  --relationship-type general --strict-fields --no-include-snapshot-text \
  --fields summary strengths challenges traditional_compatibility detailed_analysis recommendations person_info element_relationship
```
