# 王亭之基本时令与互用数字

[玄空有限解读](xuankong-interpretation.md) · [计算合同](../../../docs/fengshui-xuankong.md) · 独立数字转录（本地数据：`../../../tests/fixtures/fengshui_timeliness_v1/reference.json`）

`wang_zhongzhou_timeliness_v1@1.1.0`明确采用王亭之《中州派玄空学》上卷第十六节“九星生旺衰死”，印刷第16–17页（PDF第18–19页）。底本为艺微文化服务社有限公司扫描本，版次年未核实，以完整文件 SHA-256 `8fed6915f2deeaa60eaddcc2376abe0867b358f59d1d64f29f02580a4b98c7c5`固定；作者署名在PDF第2页。[原书扫描链接](https://www.vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4/%E4%B8%AD%E5%B7%9E%E6%B4%BE%E7%8E%84%E7%A9%BA%E5%AD%A6_%E4%B8%8A%E5%86%8C_%E7%8E%8B%E4%BA%AD%E4%B9%8B.pdf)仅作为该作者版本的依据，不认证整本或其他流派。仓库保留规则、转录及本轮校勘单页图，不分发全本扫描件。旧1.0.0只列数表，新1.1.0另列先后天图位来源。

## 显式选择与实际星数

在 `xuankong.interpretation`（独立宅盘工具直接为 `interpretation`）中设置：

```json
{
  "timeliness_ruleset_id": "wang_zhongzhou_timeliness_v1",
  "current_period_number": 7,
  "period_evidence": "示意：已独立确认评价时运，不能当作真实用户事实"
}
```

规则读取每个候选、每宫的实际山星或向星数，不读取固定宫数，不由历史宅运或年星入中数补出评价时运。未提供评价运时返回 `unknown`；未选择该作者版本时维持原有限层的 `current/not_current`。

`timeliness.mountain/facing.author_classification` 保留基本 `phase`、原书术语 `traditional_label`、实际星数、显式评价运、循环差以及独立的 `mutual_use_reference`。顶层 `rulesets` 与解释内 `timeliness_ruleset` 保留作者、版本、原书定位与文件身份；逐宫 `rule_trace` 保留角色和输入。

## 基本表和原书例外分别读取

基本表将当运星记为旺，循环将来一二运的两星记为生，循环过去一二运的两星记为衰，其余四星记为死。术语“死”指这张时令表的类别，不涉及人的生死、灾祸或实际成败。

原书紧接着说明基本表仅是大原则，并列出按先后天卦互用的数字。程序同时保留两表，不强制二选一：七运四绿在基本表为死，同时属于七运互用数 `[7,1,4]`；七运五黄为衰，却不在该互用数列。九运一白为生，一运八白为衰，循环不能只按数字大小判断。

互用保留数字成员和整列数字，`application_status=numeric_reference_only_no_site_verdict`。1.1.0在`mutual_use_reference.geometry`另给两条先后天有向图位记录；原表顺序与推导路径顺序独立。五运仅列`[5,2,8]`而无第五卦推导，未知评价运保持未知。图位只解释数字来源，不证明现场卦位、形势或用途合格；`numeric_membership=false`也不能据此推出不可用。来源、字段与原始故障见[图位与时令校验](https://github.com/thomas-yanxin/FateBridge/blob/99a5cecea99201823fc7e00d55a80dd9fd490c59/docs/fengshui-mutual-geometry.md)。

同一扫描第17页还有未解决差异：基本表把七运九紫列为生，邻近正文却只列七、八两星可用。现有证据不足以判定原因，不认定笔误，也不选一处改写另一处。本版限定实现数表，`source_disagreements` 保留正文与表格；章节一致性验收为假。

基础层 `external_form_analysis` 仍只检查明确评价运的当令山星配山、向星配水。此扩充不把生气、衰死或互用星自动纳入该条件，不改变床门取用、图片候选或动作许可，也不产生全宅综合吉凶。

## 验证范围

本轮助手逐格视觉核对并转录原书完整九运基本表81格，尚无独立人类专家复核。独立于生产公式的夹具另列完整九运互用表并逐星核对81项成员判断。生产基本分类使用循环公式，期望值来自原书逐格转录，未由引擎生成。哈希锁定转录，审计器拒绝缺列、重复运或漏星；人为改动预期标签会保留不一致。

这些核对只验证所选两张表的实现；不等于整本原典相符，更不提供现实预测准确率。原先网络转录的三项差异、NOAA参考数值差异和真实数据缺口仍独立保留。
