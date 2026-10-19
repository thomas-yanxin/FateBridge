---
name: onda-mingge
description: 围绕性格、天赋、做事方式、优势与限制，组织 FateBridge 的八字、紫微或西占相关视角，说明可与实际经验核对的区别。学习考试用 onda-xueye，六亲亲子用 onda-jiating；多主题画像由 onda-zige 组合，不为一个特点问题展开人生报告。
---

# 认识自己与个人发展

按用户这次想理解的特点组织依据，避免把人格、能力或人生写成命定结论。问孩子或家人本人时用那个人的资料；命主六亲对应不是他人的人格盘。

## 共用规则与资料

先读[按用户问题组织咨询](../_shared/consultation-routing.md)、[硬边界](../_shared/safety-boundaries.md)、[引擎调用](../_shared/fatebridge-engine.md)和[解读层](../_shared/onda-counsel.md)。涉及日期、阶段或变化时读[共享时间选择](../_shared/timing-selection.md)；采用西占主题解释时读[西占证据参考](../_shared/western-topic-evidence.md)。发现入口可能为软链接，先以 `pwd -P` 解析真实目录，再读相对引用。

资料使用当前聊天已确认内容，一次核对所选计算真正必要的缺项；不猜出生时刻，不把其他方法的缺项升级为必答。普通首轮严格字段投影、关闭快照；完整导出首次 `fields=null`，读同 run 交付。追问复用未变结果，只补所需新层。

## 按问题选择依据

| 本次问题 | 候选依据 | 选择条件 |
| --- | --- | --- |
| 性格／天赋／做事方式 | `analyze_destiny`、`ziwei_birth`、`astro_chart` | 综合问题选择有解释价值的相关视角，单项或限定体系按其范围 |
| 更深的性格专项 | `bazi_personality` | 主盘不足以回答当前细问时补，不重复同一描述 |
| 阶段与变化 | `timing_analysis`、`ziwei_horoscope`、`western_timing_analysis` 或 `firdaria` | 用户确实问变化时按共享时间流程加入；不把本命结构当时运 |
| 原始四柱／完整盘 | `bazi_birth` 或所选本命盘 | 只在明确要原始命盘时；已有八字综合不重复排盘 |
| 指定数算 | `ziwei_rules`、`canping`、`heluo` | 用户明确选择且问题在允许范围；查表不替代个案计算 |

## 读取结果与来源

八字读根字段 `day_master/ten_gods/structure_profile` 及实际判断依据，最大五行不等于喜用。紫微命身宫位置不足以解释星曜，须读对应 `ziwei_birth.palaces` 的 `stars_detail/sihua`。西占按相关日月上升、星体和相位，不能只用太阳或南交定义整个人。

## 交付与后续

按一个特点解释共同点、不同点和适用条件，再给一项可与实际行为核对的小尝试。分歧先查输入口径，仍不同就分别呈现，不编生活情境消除矛盾。尊重用户自我认识，不把规则标签当已验证人格或能力测评。学业、六亲追问转入对应主题但复用已有命盘，不重新收资料。
