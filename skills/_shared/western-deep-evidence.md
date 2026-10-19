# 西占深层证据按问题读取

这份参考供用户明确追问古典条件、关系方向、中点／映点或特殊配置时使用。普通主题先按[西占主题参考](western-topic-evidence.md)取证，不为覆盖工具而展开本页所有分支。位置计算交给引擎；传统含义用已核对的作者或知识条目，新增解释与引擎原结论分开。

## 本命中的古典细问

首次调用前按问题在工具公开的输出合同中选择下列业务字段；普通摘要仍严格投影、关闭快照。工具公开的 `evidence_views.classical_detail/fixed_stars/planetary_hours` 是对应按需字段卡，复制其中 `fields`，卡名不是请求参数。下表路径是解读索引，不是新增输入参数。先复用已保留的同 run 结果；投影曾排除某层时不能靠分页补回，也不能在用户要求不重算后另排一张盘。

| 触发问题／何时值得加 | 实际读取 | 新增信息与解释边界 |
| --- | --- | --- |
| “福点和精神点有什么区别？”或明确要古典资源／行动视角 | `classical.sect`、`classical.lots.fortune/spirit`，相关 `classical.planets` | 核对实际昼夜公式所得经度、星座、`dispositor/almuten`，再解释两点在所选传统中的不同角色。它们不是财富金额或意志力评分；本分支未返回点的宫位／相位时不由模型补算 |
| 明确问婚姻点／子女点 | `classical.lots.marriage/children` 及所涉星体条件 | 只作该版本点位与定位星的文化参考，不替代真实双人互动，不推断配偶身份、孩子能力、数量、生育结局或寿命 |
| “命主力主为何是这颗星？”“与上升守护星一样吗？” | `classical.almuten_figuris.winner/totals/points`、`classical.topic_almutens`、`classical.planets` | 命主力主是本工具对实际纳入点的尊贵加权汇总；逐点贡献和缺少的点都要保留。它与上升守护星、某宫宫头力主是不同规则，不把最高分星当成整个人的唯一性格 |
| 用户问产前朔望／为何参与命主力主 | `classical.syzygy`、`classical.almuten_figuris.points` | 核对实际返回的朔望类型、`julian_day`、经度及参与情况，再说明所选传统怎样使用它。`null` 表示本次未提供这一层，不猜朔望，不因此否定已完整的其他点 |
| 明确问恒星合某星／角度 | `fixed_stars`、该点实际落点及 `chart_profile` | 逐条读 `star/cn/point/orb/star_longitude/nature`。本实现用内置目录及岁差推进后的黄经合相，属于所列目录和容许度的命中；不是完整恒星天空、赤纬平行或灾祸事件判定。最紧一条未必最贴主题，空表不等于天空没有恒星 |
| 明确问出生行星日／行星时 | `planetary_hours`、`person_info` | 读 `is_day/day_ruler/hour_ruler/hour_number`，这是按出生地日出日落划分的不等时辰。缺星历或极昼夜可能为 `null`；不改用民用整点凑一颗主星，也不把出生行星时说成未来活动的吉时 |

对资源、关系等普通问题，只有这层能补独立信息时才取。气质／身体部位的传统对应不作为诊断或器官状态；不因某星、恒星或点位带有传统凶名就预告灾祸。

## 关系盘的方向与深读

先按[星盘技能的规范模式表](../onda-xingpan/SKILL.md#关系盘的读法)取得用户所选主层。工具公开的 `evidence_views.relationship_detail` 是额外证据的权威字段卡；按需与该模式卡的 `fields` 合并去重后调用。`evidence_views` 是描述信息，不能作为请求参数发送。它补充主层，不取代主层。

| 追问 | 实际字段与方向 | 可解释范围 |
| --- | --- | --- |
| “A 对 B 与 B 对 A 有什么不同？” | `in_to_out_aspects` 是 A（inner）星体到 B（outer）星体；`out_to_in_aspects` 反向。每组 `id` 是源，`objects[].id/aspect/delta` 是目标、相位和偏离 | 先说谁的哪一配置联系谁的哪一配置，再谈所问合作／相处情境。几何方向标签不证明对方有相应情绪、心意或行为 |
| “某人的星体碰到另一人的中点了吗？” | `in_to_out_midpoint` 的键是 A 的源星，`midpoint.idA/idB/longitude` 是 B 本命两星中点，`aspect/delta` 是实际命中；`out_to_in_midpoint` 反向 | 对象归属必须说清；不是 A 与 B 两个人的合成中点，也不等于组合盘。只解释已返回命中，不手算缺少的中点 |
| “映点／反映点有什么补充？” | `in_to_out_antiscia/in_to_out_contra_antiscia` 中 `idA` 为 A 源星、`idB` 为 B 目标星；反向字段交换所属人，`delta` 是实际偏离 | 这层是对目标星映点／反映点的几何接近，说明传统读法与普通相位不同。不是新增事件，也不将双向相同命中算成两份独立支持 |

追问普通相处时优先复用相关的两三条主层事实；用户点名高级层再展开。说明新增层是否改变原解释，不将不同技法的命中次数相加成关系成功概率。各自本命、实际交互、第三盘和影响图盘始终分开。

## 实现与来源复核

以上字段对应 `core/astro/classical.py`、`core/classical_western.py`、`core/astro/aspects.py` 与 `core/astro/relationship.py` 的实际输出。实现文件说明计算口径，不能替代传统解释来源；引用某作者时仍核对原条目。内置知识没有对应内容就说明可核对的范围，不编引文。
