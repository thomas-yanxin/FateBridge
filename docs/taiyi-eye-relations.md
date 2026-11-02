# 太乙将目关系与五将条件

现在的同盘关系包括文昌与四将同宫的“关”，以及始击与四将同宫的“掩”。原有主将与客将之间的关、始击掩太乙等关系仍保留原来的索引；新增记录追加在后。年、月、日、时计以及三式合参共用这一层，不另起盘，不改主客算或宫数。

此前程序只核四种主将对客将的同宫关系，遗漏将与目的关系。例如阳十三局太乙酉六、文昌巽九、客大将九，原注明确写“关文昌”，旧程序仍判断五将三项满足。补齐这条关系后，`generals_unconnected`保留实际阻断；阳一局始击坤七掩主大将七，则阻断`shiji_clear`。阳二十七局同时返回主参艮三与文昌相关、始击卯四掩客参四。

## 来源与版本

[《太乙金镜式经》四库本卷三](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03)关条有“将目相宫齐”，掩条又明确涉及掩主大将。[《古今图书集成》艺术典693卷](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第693卷)及[694卷](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第694卷)的具体局注明列同阵将与文昌相关、客将与文昌相关及始击掩大小将。原书扫描为[NLC892第3216册](https://commons.wikimedia.org/wiki/File:NLC892-411999021002-92863_欽定古今圖書集成_第3216冊.pdf)。

实施前冻结阳1、2、7、11、13、15、18、27共8局的完整11项宫数、12条选定明载关系及来源影像。卷693至696的阳72局全文也保留，下载全文不表示全书断语已核验。数值期望由原书人工转录，未调用生产算法生成。见冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v13/manifest.json`）与逐局资料（本地数据：`../tests/fixtures/taiyi_jinjing_v13/eye-general-cases.json`）。88项宫数与12条关系分开计数，8个循环课注不算8次历史预测验证。

明钞本NCL-06604图46的关条只明列主客四将，没有明确写将目。V11的原裁定（本地数据：`../tests/fixtures/taiyi_jinjing_v11/adjudication.json`）保留；V13取得具体注例后增加本次读法，不能宣称各版本的范围完全一致。本次裁定（本地数据：`../tests/fixtures/taiyi_jinjing_v13/adjudication.json`）同时列出未扩展的分支：同阵大小将中五互关、二目互关、四郭固杜和挟闭。

## 同盘依据与解释

新增`patterns`记录带`relation_profile=wenchang_general_guan_shiji_general_yan_exact_palace_v1`。关以将为主体、文昌为另一端；掩以始击为主体，变体明确指出被掩的将。`basis`保留两个实际字段和值，`source`及`supplementary_sources`交付原典与局注，`scope`交付版本与否定范围。将只在九宫正位或中五，间神不按八门扇区并入正宫；中五无目时不制造将目关系。

`condition_assessment.ruleset.version=1.1.0`仍按卷四原有三项合取，增加`relation_profile`、`relation_sources`和`relation_scope`说明所核读法。全部阻断引用同次`patterns.N`，快照使用同份记录。三门按所选计法独立评估，未知保持`null`；不能把一条关或掩改成四郭成立，也不输出原文战争胜负或杀害结论。

发布的`conditions`／`taiyi_conditions`首读保留组合条件、全部关系与版本说明。使用`strict_fields=true`、`include_snapshot_text=false`；完整资料从同次`result_delivery`读取。视图名用于选择字段，不是请求参数。

较长的三式日计深度视图仍使用默认8192字符预算，全部请求的业务字段保持行内。必要时，补充回执`run_metadata.provenance`与`run_metadata.determinism`随运行环境存入同次不可变交付物，`deferred_fields`逐项明示路径。运行标识、输入／契约／业务散列及环境清单指纹仍在行内；按这些点路径可恢复原回执，原业务内容、字段选择和预算均未缩减。

核验命令：

```bash
uv run --locked --extra dev python scripts/audit_taiyi_eye_relations.py --report /tmp/taiyi-eye-relations.json
uv run --locked --extra dev python -m pytest -q tests/test_taiyi_eye_relations.py
```

审计脚本在选定8局通过时仍返回1，因为全72局注、阴遁注例、全书分歧、完整古历与解释盲测尚未完成。测试、局注符合与全书验收分别报告，既有失败字段和来源分母不变。规则作者：FateBridge contributors；原典作者与编录分别为唐王希明及清陈梦雷等，补证读法版本见上述配置与五将规则版本。
