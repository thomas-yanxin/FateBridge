---
name: onda-jiating
description: 回答原生家庭、家庭责任、六亲与亲子相处的文化参考问题，区分命主视角、家人本人及双方互动，按需要加入阶段变化。孩子本人的学习用 onda-xueye；不预测亲人死亡、生育能力、子女数量性别或真实家庭事件。
---

# 家庭与亲子

先识别用户在问自己的家庭对应、孩子／家人本人，还是两个人的相处。对象不同，使用的资料和可解释范围不同。

## 共用规则与资料

先读短的[咨询核心](../_shared/consultation-core.md)。主题重叠或扩展时读[范围选择](../_shared/consultation-routing.md)；涉及阶段、日期或变化才读[时间选择](../_shared/timing-selection.md)。采用八字、紫微或西占解释时，分别定位[八字证据](../_shared/bazi-topic-evidence.md)、[紫微证据](../_shared/ziwei-topic-evidence.md)或[西占证据](../_shared/western-topic-evidence.md)的相关条目。参数、分页或 CLI 有缺口时再查[引擎参考](../_shared/fatebridge-engine.md#怎么调引擎)；表达细节按需查[解读参考](../_shared/onda-counsel.md)。软链接先解析真实目录，再读相对引用。

资料采集、摘要投影、完整交付与追问复用统一按咨询核心执行。

## 按问题选择依据

| 用户任务 | 候选依据 | 对象与范围 |
| --- | --- | --- |
| 原生家庭／六亲对应 | `bazi_relatives`；`ziwei_birth` 相关宫位；`astro_chart` 家庭相关配置 | 命主视角，不由盘替用户补家庭史或认定家人行为 |
| 我的子女对应／子女缘文化含义 | `bazi_children` 与本命相关配置 | 使用命主资料，不解释为孩子本人的性格、能力或生育事实 |
| 孩子／家人本人的特点 | `analyze_destiny`、`bazi_personality` 或所选本命盘 | 使用该人资料，接认识自己主题；学习转相应主题 |
| 亲子／家人双方互动 | `two_person_compatibility`、`astro_relative_chart` | 双方资料齐全且确需比较；按已确认关系用 family，不由名字推关系 |
| 家庭阶段／责任变化 | `timing_analysis`、`ziwei_horoscope`、`western_timing_analysis` 或 `firdaria` | 只加当前问题所需时段，不把阶段标签写成家人会发生事件 |

## 读取结果与对象边界

八字专项读取 `relatives_analysis`／`children_analysis` 实际规则；不据星宫与时间信号预测生育或子女数量。紫微宫位和西占家庭配置同样只说明所选传统视角。双人分数不是亲子关系好坏的判决，个人内部事件不能说成双方冲突。

专题细问按[八字证据参考](../_shared/bazi-topic-evidence.md)读取所选专项的真实结构、位置、权重与已返回时间背景；不把传统分类或模板当现实结果。

## 交付与后续

将解释连接到用户已说的责任、安排或相处问题；未知时使用条件句，给一次可讨论的具体事情。生死、疾病、诊断、生育与治疗问题先按硬边界处理，不因家庭主题或对方是亲人解除限制。家庭空间布局转风水主题，不把命主八字代入全家环境喜忌。
