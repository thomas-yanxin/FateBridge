# 成化校勘如何进入现行计算复核

1947年《任注滴天髓阐微》同段既有假设、转折，又有作者最终判断。此前GS12的一句“戊癸合而化火为忌”被误读成实际成化，虽然已另存勘误，三份现行说明和旧研究的默认历史重放仍会显示原来的预期。本轮修正现行说明，并补入独立的现行校勘复核入口；原始首次比较不覆盖。

## 原页与最终判断

所选底本为任铁樵增注、李雨田校订兼发行、上海大东书局经售1947年4月初版，[整本书影](https://upload.wikimedia.org/wikipedia/commons/d/db/SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf)SHA-256为`d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803`。本轮重看已按该版本保存的PDF209、210原图；保存两页（本地数据：`../tests/fixtures/bazi_classical_corrections_v2/source-pages209-210.pdf`）及比较后勘误（本地数据：`../tests/fixtures/bazi_classical_corrections_v2/errata.json`）均保持原散列。没有新增未见命例或第二位独立专家复核。

| 命例 | 原柱 | 原文最终局部判断 |
| --- | --- | --- |
| GS12 | 癸丑、戊午、丙午、壬辰 | 癸水仍通根，合而不化；不化反喜其合 |
| GS13 | 癸巳、戊午、丙午、壬辰 | 对比前造，戊癸合而必化 |

GS13的正文也说壬水通根身库，同时说没有金的滋助而清枯。按项目的实际藏干表，两造都有辰藏癸水。于是“没有本气／重根就能化”和“只要还有任意水根就绝不化”都不能区分这组原文。丑、巳的季候、生发、滋助及全局作用必须继续验证；不得据这两造拟合一个根量阈值，也不能将藏字改没来获得命中。

GS12的强标签继续保留。候选把它改强却误判成化，不能称为计算路径正确。日主强弱、局部五合、日主化气格和运年作用仍分别裁定。

## 同一预测，两套来源状态

新执行器先恢复原数值依赖，在新进程中运行完整v2研究，再逐值核对原首次报告的全部分组、摘要和采用门槛。只有完全一致，才按校勘改变现行预期及原文锚点。输出同时保存`historical_groups`与`current_groups`，不改预测、账本、强弱、未知、超范围状态或原首跑文件。

事前输入登记（本地数据：`../tests/fixtures/bazi_current_collation_v1/protocol.json`）是在已知勘误及旧2/3开发结果之后冻结，只用于可复现性，不冒称预测前盲测。更正必须匹配原文件散列、原值、命例、实体配对、页码与版本；重复、错位、未支持字段、未应用到目标或同一实体配对标签冲突均明确拒绝。

首次完整复核（本地数据：`validation/bazi-current-collation-first-v1.json.gz`）包含10组146条历史记录、117个不同四柱；57条明确强弱、89条未知保持原样。25条配对出现记录按四柱与实体配对去重后为22对，其中6对有明确局部成化判断、16对未知。两组历史记录重复收录了GS12、GS13，不增加独立样本数。

| 6个不同的已知配对 | 历史标签：符合／不符／超范围 | 现行校勘：符合／不符／超范围 |
| --- | --- | --- |
| 生产v6，仅合绊 | 1／4／1 | 2／3／1 |
| 成化候选v1 | 4／1／1 | 3／2／1 |
| 成化候选v2 | 5／0／1 | 4／1／1 |

超范围的原文明示配对涉及日干，不能把程序未执行算成正确阴性。上述变化来自判据更正，生产算法没有进步、候选没有退步；原始错误判据只是高估了它们。独立改善为0，候选仍未采用，原来的新章阳性／阴性及算子收益门槛也未改变。

## 实际查询中的功能根说明

`knowledge_read`的`bazi/classical_force_semantics/物理藏根与功能根`修订为2，在保留原四条说明的基础上补入上述两造的最终判断与功能差别。它有明确的PDF209–210来源，也保留原三章引用和仍未完成的力量裁定；词条不替引擎作成化或全局旺衰判断。

补充协议（本地数据：`../tests/fixtures/bazi_current_collation_v1/knowledge-supplement-protocol.json`）在修改这一个词条前冻结，逐项复核（本地数据：`../tests/fixtures/bazi_current_collation_v1/knowledge-review.json`）绑定修订前后完整数据。该次修订后为82条，其他81条、原四条正文、全部主键和知识索引不变；原72条中40条出处待审及独立专家未完成的状态也不变。

旧十四条专题修订的精确重放改与保留的原82条版本比较，原始散列和全部旧断言保留；该次检查对保留的精确82条版本证明只改了功能根词条；后续[性情三卡补充](bazi-mediated-capacity-audit.md)另证原82条保持，当前总量85条。初次集成遗漏旧生成器的这一版本定位而有1项失败，日志保留，未删去该重放检查或改动源案例标签。

```bash
uv run --locked --extra dev fatebridge knowledge_read --domain bazi --category classical_force_semantics --key 物理藏根与功能根 --response-char-limit 0
```

```bash
uv run --locked --extra dev python scripts/audit_bazi_current_collation.py --output /tmp/bazi-current-collation.json.gz
uv run --locked --extra dev pytest -q tests/test_bazi_current_collation.py tests/test_bazi_stem_effect_audit.py
```

执行器退出0只表示复核成功写入；报告中的`adopted=false`、`classical_acceptance_passed=false`仍须读取。已有报告或散列文件禁止覆盖。新脚本和词条不修改REST、MCP、CLI合同或领域默认计算；三项完整目标继续未通过，本轮验证（本地数据：`validation/bazi-current-collation-local-v1.json`）单独记录覆盖范围。

本轮源码相关166项检查及固定解包wheel的27项检查通过，后者是前者的子集，不累计为独立准确率。两次新建stdio分别核对10页同次全文及散列，实际连接的MCP也返回修订2；这只验证该词条交付和同次字段，不证明自由文本解释已全面忠实或完整原典已符合。源旺衰登记中的24个不同输入分歧仍未解决，开发包未发布。
