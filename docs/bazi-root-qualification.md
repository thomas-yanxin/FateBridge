# 结构根资格：原典根类与实际根量

[八字判定](bazi-assessment.md) · [四墓土冲动](bazi-storage-movement.md) · [双人评分](compatibility-scoring.md)

本次修复一个会影响旺衰、喜用与下游评分的漏判：旧结构规则只检查地支本气是否与日主同五行，
因此即使已识别庚巳、壬申为阳长生重根，也不能将其计入结构规则。
旺衰版本现为`season_root_revelation_relations_v4`。

## 原文依据与实现范围

依据国家图书馆藏[《秘本子平真诠》书影](https://upload.wikimedia.org/wikipedia/commons/f/fe/NLC416-11jh010455-35296_%E5%AD%90%E5%B9%B3%E7%9C%9F%E8%A9%AE.pdf)，
上海世界图书馆发行，PDF22–23（书页13–14）。PDF23将长生、禄刃与墓库、余气分别论轻重，
并单列阴长生的不同口径。同一书影SHA256为
`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`。
本次仅连接已有根类识别与已有结构规则，不将比肩数量的古文比喻换成新的数值倍数。

| 层次 | 当前处理 |
| --- | --- |
| 原典根类 | 保留禄、阳刃、阳长生、阴干帝旺同气等既有分类；阴干帝旺同气根不授予阳刃格资格 |
| 实际藏干 | 必须有同五行实际藏干；无藏干的阴长生参考不能补成根 |
| 作用后根量 | 读取同次合、冲、刑等处理后的真实藏干预算；趋势转移的合成贡献不算藏干根 |
| 健全根资格 | 原典重根或本气同五行，且真实藏干剩余至少达到原量的0.75；门槛沿用原工程约定 |
| 全局判级 | 原数值判级与三条限定结构规则继续分别保存；一处重根不会自动把全局改判强 |

资格判断用`remaining_hidden_mass >= initial_hidden_mass * minimum_retention_policy`，
保留未舍入数值。比例显示与除法误差不能反向改变已经执行的门槛判断。
`root_qualifications`逐柱记录根类、真实藏干、初量、剩余量、保留比例、资格依据与是否计入。
`structure_profile.evidence_chain.strength_context.root_qualifications`复制同次结果，
不重算另一套力量。未计算时是`null`，不能解释为已计算但没有根。

## 可复核的变化与反例

公开虚构示例`庚午 辛巳 庚辰 辛巳`的数值扶身份额仍约0.43421，数值原判仍为中和。
v4中两处庚巳阳长生根达到保留门槛，且年、月、时均为印比，
因此触发原有的“两处健全根及三干印比”规则，最终改为强。
不改变份额、阈值或合盘权重来维护旧标签，喜用和下游分数如实变化。

`壬寅 壬寅 庚辰 辛巳`虽有一处庚巳重根，仍不能触发需要至少两处根的规则。
`壬寅 戊申 壬辰 壬寅`的申中壬根受当前冲损模型影响，剩余比例未达0.75，
不能仅因阳长生名称恢复资格。这是现有模型观察，尚未解决其原文身重与模型中和的分歧。
原文“身轻印重”也不能由身印合计直接裁定，根类修复没有解决这项全局力量问题。

原典冻结十例复核仍为：月令名称10/10，原文明示旺衰1/3，7例未明示；
成格及相神取用尚未通过。以上案例都已用于开发，不称新的独立盲测。
既有21例方向与630次参数扰动是规则回归，也不能代替上述未通过的原典验收。

[数值隔离审计](../scripts/audit_bazi_root_qualification.py)的历史模式执行原字节冻结的v3与v4内核，
使用相同、另行记录散列的共享数据，比较5个已知探针及480个当前历法生成的民用日期输入。
本轮485例的数值份额、有效能量、真实根量与关系回执均未变化，8例最终标签改变。
这些是因果回归输入，不是独立历法答案、未见原典命例或现实准确率。
v3、v4内核虽已冻结，共享依赖仍取当次代码，报告明确记录该范围，不能称完整历史环境复现。
后续v5另有同局重支与根量修复；默认比较当前实现会如实报告额外数值变化，
不会冒称仍是原来的纯根资格变更。该后续变化见[同局重支审计](bazi-complete-bureaus.md)。

## 解释、接口与舍入

标准命盘摘要读取同次资格和结构判级，明确数值原判及触发依据。
结构化引用仍以同run、完整业务摘要、路径与值核验；它不认证任意自由文本的语义或事实来源真实性。
`bazi_birth`和`analyze_destiny`发布`evidence_views.root_qualification.fields`，供调用方按需投影；
视图名不是请求参数。投影对象可含完整根数组；公开投影不支持继续穿透数组元素，严格模式会明确拒绝。

合盘另修正十进制加权舍入，版本`compatibility_weighted_rules_v2`，原关系权重不变。
三版独立手工加减账本、单人升级因果对照及75.85半分位案例见[双人评分](compatibility-scoring.md)。
旧账本保留；当前预期按已声明规则手工推导，不直接复制生产输出成为答案。

复核命令：

```bash
uv run --locked --extra dev pytest -q \
  tests/test_source_root_qualification.py \
  tests/test_root_qualification_transports.py \
  tests/test_compatibility_score_provenance.py
uv run --locked --extra dev python scripts/validate_bazi_strength.py
uv run --locked --extra dev python scripts/audit_bazi_root_qualification.py --historical-v4-replay --output /tmp/bazi-root-isolation.json
uv run --locked --extra dev python scripts/audit_bazi_classical.py --output /tmp/bazi-classical-v4.json
```

最后一条预期仍退出1，表示原典验收未通过，不能删去失败项换取满分。
历法独立对照、完整原典裁定、自由文本解释及现实预测属于四项分别验收的能力，
本轮不生成综合权威分数。现实预测须使用事前登记及独立结果，当前仍未验证，见[四项验收](prediction-validation.md)。

本轮执行证据见验证报告（本地数据：`validation/bazi-root-qualification-v1.json`）：固定快照相关回归1969项、
输出合同27项及Linux核心183项通过；完整原典验收仍未通过。
Linux旧基线逐项差异（本地数据：`validation/bazi-root-qualification-linux-golden-v1.json`）保留12份未匹配快照，
同时包含本次根资格／评分变化与此前星历来源、内嵌梅花等共享变化，未自动重冻。
固定快照的全仓库类型和全量调用合同检查，以及其后共享工作区的文档检查，
也分别保留未通过状态，不将专项通过代替全仓库通过。
