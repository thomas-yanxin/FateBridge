# 八字原典命例输入一致性核查

后续进展见[原典命例输入与断语引用对齐](bazi-census-input-claim-alignment.md)：同一组 8 条修订现已接入标准全集核查，并核对其 8 条关联说明。下文保留第一轮独立视图的证据与当时状态；剩余 4 条输入问题仍未解决。

本轮发现并在独立修正版视图中修正了 8 条原页录入错误。原始 558 条记录与首轮失败报告完整保留；修正版仍有 4 条异常，未通过验收。此工作没有调整强弱算法、原典标签、评分门槛或原有 26 处分歧的分母。

## 范围与参照

核查覆盖《滴天髓阐微》1947 年图版整理的全部 558 条命例，其中 530 条有完整四柱，28 条保留缺项。重复、假设、原作者质疑、关系反事实和未登记类型的记录全部保留，不因种类而豁免符号核查。

独立核查器不导入 FateBridge 计算模块。它将原书第 32、34—35 PDF 页的年干配月、日干配时表，与[香港天文台的干支说明及表格](https://www.hko.gov.hk/tc/gts/time/stemsandbranches.htm)作完整比较：120 个配月格、120 个配时格一致，另保留完整六十甲子表。下载 HTML、原页图像、原始命例和输入散列均已冻结。

原书第 35—36 页另有夜子时说明。核查器对所有子时分别保留普通配时和原书夜子候选，不从干支反猜出生日期或午夜前后。原始视图有 33 条子时记录，修正版有 34 条；其实际早晚子钟点均未确认。通过配对检查不证明历史出生资料成立，也不证明原页抄录正确。

## 首轮失败与原页修订

原始完整核查实际以退出码 1 结束：11 条命例有 12 项关系异常，年月至少一项不符 6 次，日时至少一项不符 6 次。原始报告不被修正版替换。

| 命例 | PDF 页 | 原录四柱 | 原页确认的四柱 |
| --- | --- | --- | --- |
| MAIN-C014 | 58 | 癸酉 甲子 辛酉 戊午 | 癸酉 甲子 癸亥 辛酉 |
| MAIN-C087 | 139 | 庚寅 丙辰 乙卯 丁亥 | 丙辰 庚寅 乙卯 丁亥 |
| MAIN-C133 | 187 | 丙辰 己未 壬午 癸卯 | 丙辰 乙未 壬午 癸卯 |
| MAIN-C445 | 442 | 己丑 丙戌 丙午 庚寅 | 乙丑 丙戌 丙午 庚寅 |
| MAIN-C514 | 491 | 戊辰 庚申 甲子 壬申 | 庚申 庚辰 戊辰 戊午 |
| MAIN-C515 | 491 | 己丑 丙寅 壬寅 丁卯 | 甲子 丙寅 己丑 甲子 |
| MAIN-C516 | 491 | 丙子 壬寅 丁卯 乙未 | 壬申 壬寅 丙子 乙未 |
| MAIN-C517 | 491 | 戊辰 戊午 甲子 庚辰 | 己亥 丁卯 庚申 庚辰 |

原因包括把首步大运当作时柱、年月倒置、乙字误读为己，以及第 491 页四个纵排小图跨列混录。第 491 页四图全部重新核验，包含原先配对检查通过的 MAIN-C514。这一反例说明仅凭公式筛出异常再修改，仍会漏掉真实录入错误。

8 条修订都有原对象散列、全页和局部图像绑定。修正版保留所有原对象，只修四柱及原本由四柱直接拼成的标题；其他说明、类型和强弱标签均不改。8 条原标签均未知，不补造强弱结论。

## 仍然失败的 4 条

| 命例 | PDF 页 | 状态 |
| --- | --- | --- |
| MAIN-C219 | 253 | 图版确印戊辰年、己酉月，与配月表冲突；原“弱”标签仍保留 |
| MAIN-C368 | 383 | 图版确印丁卯年、丙寅月，与配月表冲突 |
| MAIN-C488 | 477 | 图版及说明确指己卯日、丙辰时，与配时表冲突 |
| MAIN-C457 | 450 | 时干字形尚未可靠辨定，保留原录壬辰及异常，等待独立字形核验 |

前三条保留为图版内部不一致；不能拿公式反改原书。第四条也不能凭配时公式、传记或其他版本挑选一个能通过的字。修正版实际退出码仍为 1，留下 2 项年月及 2 项日时异常。

## 验证与使用限制

16 项工程测试通过，155 份冻结输入前后散列一致。测试使用模块运算独立对照全部 558 条原始及修订记录、全部 240 格表，并检查早晚子候选、缺项保留、篡改拒绝和完整命令回执。这不是 16 个预测样本，也不是解释模型验收。

尚未把修订覆盖到原始全集及其配套说明、主体引用与断语关系。当前修正版显式设置 `source_claim_alignment_review_complete=false`、`force_comparison_allowed=false`；必须完成说明对齐和来源复核后，才能冻结下一版全集并开展原典强弱比较。没有覆盖写入旧全集，没有据此重算原来的 26 项分歧。

独立复查可在新的输出位置运行；核查失败会写出完整报告并返回 1，已有输出拒绝覆盖：

```sh
uv run --locked --extra dev python scripts/audit_bazi_census_pillar_consistency.py \
  --output /tmp/bazi-census-raw-new.json
uv run --locked --extra dev python scripts/resolve_bazi_census_pillar_inputs.py \
  --output-directory /tmp/bazi-census-corrected-new
uv run --locked --extra dev python scripts/audit_bazi_census_pillar_consistency.py \
  --study /tmp/bazi-census-corrected-new --output /tmp/bazi-census-corrected-new.json
```

证据位于 完整核查归档（本地数据：`validation/bazi-census-pillar-consistency-v1/report-first.json`）、原始失败报告（本地数据：`validation/bazi-census-pillar-consistency-v1/assessment-first.json`）、修正版失败报告（本地数据：`validation/bazi-census-pillar-consistency-v1/assessment-resolved-first.json`）及原页修订记录（本地数据：`validation/bazi-census-pillar-consistency-v1/case-input-corrections-first.json`）。

原始 40,219 条包络失败、41 项边界冲突、26 项原典分歧与旧 5 例解释验收仍未全部关闭。历法原始重放尚在运行，原解释机械结果仍为 0/5；本轮新增模型调用为零。现实预测有效性未被此项工作验证，不给总体满分或权威认证。
