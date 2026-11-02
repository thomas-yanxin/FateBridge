# 同柱逐藏干生克与盖头目标

丁丑的天干丁火生地支本气己土，却克丑中辛金。只比较天干与支本气，会遗漏所选原典明确点名的盖头目标。本轮新增逐藏干关系表，让本气、其他真实藏干与具体所喜目标分别可见。

## 原典与计算范围

依据任铁樵增注、李雨田校订兼发行、上海大东书局经售1947年4月初版[《任注滴天髓阐微》书影](https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf)PDF391。原柱己未、丁丑、丙戌、戊戌，文中以丑藏辛财为用，继而论丁火盖头、通根未戌。保留PDF390–392（本地数据：`../tests/fixtures/bazi_hidden_targets_v1/source-pages390-392.pdf`）提供完整上下文；这个命例此前已用于开发，没有新增独立验证信用。

`literal_hidden_target_relations_v1`枚举本柱每个实际藏干，分别给出同五行、藏干生干、干生藏干、藏干克干、干克藏干。只有最后一类将`covering_candidate_if_target_desired`置真；它的含义是“若这个藏干是所喜，则存在同柱盖头候选”，不是已经判定喜忌、损伤或作用效力。

| 丁丑中目标 | 同柱关系 | 条件盖头候选 |
| --- | --- | --- |
| 己土 | 丁生己 | 否 |
| 癸水 | 癸克丁 | 否 |
| 辛金 | 丁克辛 | 是，仅在辛为所喜时 |

三个藏字均保留，旧`branch_covered_if_desired=false`仍准确表示本气己土未被丁克；不能把新表改述为旧本气判断算错，也不能把辛受克扩成全支所有藏干都受克。`hidden_rank`只索引现有藏干表，不是司令天数、原典气量排名或各派统一中余气顺序。原旺衰模型的工程预算另列，不由本表增加、减少或移转。

当前没有从这些关系裁定实际克制程度、透藏生发、跨柱保护、截脚、开库、根损或完整成格。原书一例证明藏干可以是具名讨论目标，不为任意同柱生克提供统一效力常数。

## 公开读取与同次解释

标准命盘、根工具及九专题的公开`hidden_carriers`视图提供对应`fields`：本命在`evidence_chain.natal_hidden_carriers`，命盘及根工具沿各自`structure_profile.evidence_chain`读取。时运的新`hidden_target_carriers`与原`pillar_carriers`用同一`node_id`对应，逐个时间层复用同一藏干算法；本气承载、本柱实根及原局外援仍分别保留。

时运把方法、来源和效力边界保存到公共`hidden_target_reference`，不在每柱重复。将它与新数组中的柱名、全部目标合读，可以逐项重建完整藏干关系回执；没有删除目标或关系。九专题的`hidden_carriers_timing`视图同时选取原承载表、新数组及公共引用，时运工具的`hidden_carriers`／`carriers_detail`也同时提供。旧本气数组及`carriers`视图的8192字符预算保持不变。

选取整个表后在同一结果内筛选目标；公开投影不支持穿透数组元素。快照复用本次回执，不根据展示文字重算。需要完整分页时读取原run并校验交付散列，不以摘要重算全文。

```bash
uv run --locked --extra dev fatebridge bazi_birth --birth-year 1980 --birth-month 1 --birth-day 14 --birth-hour 20 --gender 男 --birth-timezone Asia/Shanghai --use-true-solar-time false --fields bazi_birth.structure_profile.evidence_chain.natal_hidden_carriers --strict-fields true --include-snapshot-text false --response-char-limit 0
```

上例是为复现字面四柱而选择的虚构验证输入，不认证原书人物的公历生日或经历。

## 验证与仍未解决的计算

60个合法同柱与独立五行关系矩阵逐项对照；4个原局乘60柱的240份旧承载对象完全相等，无需删除任何字段。修改前清单（本地数据：`../tests/fixtures/bazi_hidden_targets_v1/protocol.json`）明确这些对象来自旧程序，只证明迁移保留，不是独立原典预期答案。

初测将一份独立藏字表的巳中余气排列误当成本功能规定，出现5项失败；原日志保留。现在按明确合同核对藏字集合、本气、逐项关系及表序号，没有改全局藏干表、气量、强弱标签或五行生克预期，也不将这种排列当作原典统一排序。

初版把新表嵌入旧承载数组，使部分旧视图超出预算；仅逐柱去重仍未解决全部超限。最终把新结果独立发布、用同一节点关联，完整保留来源及全部新事实，原九专题预算门槛和旧检查不改。三端新增时间视图测试最初没有给REST传相同的固定`as_of`，因而与MCP／CLI相差10天；修复测试输入后比较同一时点，没有改领域日期算法。

本轮另一个[多根承载候选](bazi-qualified-roots-audit.md)有7条开发改善、1条退化，未采用。新关系表不会据此自动修复根力、受生或原典强弱。工程检查和三端结果见本地验证记录（本地数据：`validation/bazi-hidden-carriers-v1.json`）；历法全范围、完整原典及更广解释验收仍未完成。

相关111项检查分别在源码和固定解包wheel下通过；它们是同一组回归，不是222个独立原典命例。两次独立stdio进程均核对本命全文122页、时运全文51页的同次交付散列及新回执。较广结构检查为101项通过、1项既存循环依赖失败；全库文档检查也仍有其他在建报告的缺失链接，没有宣告全库验收通过或发布新版本。
