# 天干先后与月时五合复核

综合、标准八字命盘及九专题的 `stem_order` 字段视图增加原典先后复核。字段卡中的 `fields` 才是调用参数；视图名称不直接传给计算工具。该视图同时保留本次旺衰判级、身印裁定、月内司令状态及通关摘要。

复核依据为沈孝瞻《秘本子平真诠》所选国图藏本〈论生克先后分吉凶〉，PDF47–48、印刷38–39页。[原书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)的版本与完整散列随 `source` 返回。本章的部分例只给天干及月支，不能补成完整四柱或出生日期。

`stem_energy_accounting.source_order_review` 将以下事实分开：

- 月干与时干是否具有五合字对，四柱坐标中是否隔着日干；
- 所选原典的非日干次序候选，以及同一次 `assessment.relations` 是否实际记录该月时事件；
- 年干、日干是否另有同字配对可能。这是观察，尚未选择争合胜方。

`recorded_relation_refs=null` 表示事件表未提供，空数组表示表已提供但未记录该对，两者不能互换。`unrecorded_source_candidate_count` 同样区分未知与零。

默认内核仍使用已有天干合绊政策。原页直接支持的月时戊癸例与其他五合字对的类推资格分别说明；类推候选没有逐类独立校验。`candidate_numeric_policy_adopted=false`、`effective_combination=not_adjudicated`、`calculation_effect=none` 表明本字段不改变预算，也不判定合效、成化、通关或现实事件。`current_numeric_policy` 中的 v6 指沿用的天干合绊子政策，整体旺衰方法可以是 v7。

标准命盘快照遇到候选时增加一句来自同次回执的事实说明；导出正文沿用这一句。它不另排一盘，不把“事件未记录”写成“原典不合”，也不把“候选存在”写成“已有效合去”。身与印的实际藏根及能量仍分列；只有四柱时，月令司令及有效通关继续保留未裁定。

来源全文条款、隔离候选未采用的原因、十九个历史锚点的当前状态、首次失败及源码／安装包的验证范围见本地验收（本地数据：`validation/bazi-ordered-conditions-v1.md`）。
