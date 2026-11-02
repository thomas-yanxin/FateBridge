# 合会候选、当前筛选与同次事件的完整保留

本轮修复一处会误导条件审查的输出缺口：现行算法的实际事件列表不包含所有字面候选。若把没有事件误当作不存在合会，就会漏看被冲或已占用位置压住的半合。现已在领域服务中独立保留候选、当前筛选状态和实际事件引用，并连接到通关节点的真实根载体。未改变旺衰算术、系数、阈值、司令选择或原典强弱标签。

前轮联合相生候选的四个失败反例仍保留，采用门槛仍是四失败、一通过，规则未采用；见[拒绝决定及完整反例](bazi-joint-generation-rejection.md)。新增清单使这些反例暴露的遗漏可见，不把失败候选重新包装为通过。

## 资料和计算范围

原典条件继续沿用已冻结的[原19例逐页校读](bazi-original19-source-conditions.md)及前轮《滴天髓阐微》1947年本《通关》PDF197–200的完整四页。合会候选清单描述现行v8目录中的三会、三合、字面六合及含旺支半合，不声称覆盖所有流派、暗合、拱局或所有支关系；不据图形存在认定合化或有效通关。

在生产修改前冻结协议（本地数据：`../tests/fixtures/bazi_branch_inventory_v1/protocol-first.json`）、[独立字面表](../tests/fixtures/bazi_branch_inventory_v1/literal_geometry.py)，并对未修改的原算法直接追踪全部20,736种四支排列在半合筛选前的实际占位与活动六冲位置。新清单与该轨迹一致，字面候选没有遗漏。这里核对的是关系几何与程序筛选，不是历法、全书符合度或现实预测。

完整局包括重复物理支位，二支候选保留每个实际柱位组合；非相邻六合和被筛掉的半合也保留。实际事件顺序、原状态和根账本沿用同次回执，附合不额外占预算；未知方法或未提供回执时，筛选状态保持未知，空列表和未知不互换。

新增位置为`current_calculation.branch_combination_candidates`，以及八字证据链`classical_passage_relations.branch_combination_candidates`。节点的`potential_branch_candidate_refs`指向其已给物理根载体涉及的候选。旧调用不提供四柱时保留旧形状，不从出生资料或节点猜四柱。公开`bazi_source_compare`新增`branch_candidates`视图，复制其字段到`fields`使用，见[生成合同](contracts/bazi_source_compare.json)。

## 原19例的本轮逐例回查

下面身、印分别取同次精确工程量，不能当作日主本体强弱、原典权重或概率。全部十九例的月内司令仍为`not_adjudicated`，没有借原文相对天数重建出生瞬间。原页条件、身印物理根、完整实际关系和候选节点连接保存在逐例完整记录（本地数据：`validation/bazi-branch-inventory-files-v1/original19-condition-inventory-first.json`）。

`recorded_event`表示已有实际事件，具体是合绊、争议或条件转化仍须读取原状态；`suppressed_before_half_evaluation`表示半合因已有占位或活动六冲而未进入评估；`outside_current_adjacency`和`contained_in_complete_bureau`分别保留非邻接及完整局包含事实。这些都不是有效通关裁定。

| 原例 | 原标签→当前 | 身／印工程量（精确分数） | 候选及当前筛选 |
| --- | --- | --- | --- |
| ZP37-LIANG | 强→弱 | 404/105 ／ 1/7 | 三合未卯亥：recorded_event；半合未卯：suppressed_before_half_evaluation；半合卯亥：suppressed_before_half_evaluation |
| ZP37-XIE | 强→弱 | 7/2 ／ 2/7 | 半合申子：recorded_event；半合子申：recorded_event |
| ZP41-SHI | 强→弱 | 52/21 ／ 2/3 | 六合酉辰：recorded_event |
| ZP-PROSPECTIVE-02-YANG | 强→弱 | 39/56 ／ 12/7 | 当前目录无字面候选 |
| ZP-PROSPECTIVE-17-MAO-HEAVY | 强→中和 | 117/28 ／ 16/7 | 当前目录无字面候选 |
| ZP-PROSPECTIVE-18-MA-LIGHT | 弱→强 | 15/8 ／ 104/7 | 六合巳申：outside_current_adjacency；半合巳酉：recorded_event |
| DTCW1947-TG-01 | 强→弱 | 19/16 ／ 15/4 | 当前目录无字面候选 |
| DTCW1947-GS-01 | 强→弱 | 15/7 ／ 141/70 | 六合酉辰：outside_current_adjacency |
| DTCW1947-GS-03 | 强→弱 | 561/280 ／ 153/35 | 半合寅午：suppressed_before_half_evaluation；半合午寅：suppressed_before_half_evaluation |
| DTCW1947-GS-12 | 强→中和 | 36/5 ／ 4/7 | 当前目录无字面候选 |
| DTCW1947-HJ-01 | 弱→强 | 9/7 ／ 1417/105 | 六合亥寅：recorded_event |
| DTCW1947-HJ-06 | 弱→强 | 64/7 ／ 57/20 | 当前目录无字面候选 |
| DZ-12 | 强→弱 | 29/21 ／ 3/35 | 六合辰酉：recorded_event；半合酉巳：suppressed_before_half_evaluation |
| GH-15 | 弱→强 | 2 ／ 184/15 | 当前目录无字面候选 |
| XX-16 | 强→强 | 407/84 ／ 17/70 | 三会巳未午：recorded_event；六合未午：contained_in_complete_bureau；半合巳酉：suppressed_before_half_evaluation |
| XX-19 | 弱→中和 | 6 ／ 55/28 | 六合申巳：recorded_event |
| FJ-08 | 强→强 | 153/70 ／ 717/560 | 三会卯辰辰寅：recorded_event |
| SP-02 | 弱→强 | 15/14 ／ 703/35 | 三会卯辰寅：recorded_event；半合未卯：suppressed_before_half_evaluation |
| ML-02 | 强→弱 | 309/112 ／ 27/7 | 当前目录无字面候选 |

仍有17例不同，XX-16和FJ-08沿用前轮已一致的结果；未挪走反例、减少分母或重标未知。原文司事的26／32日、380／360日及顺序差异继续保留，没有把文献异文变成算术规则。

## 本地验收和未完成项

新增测试首次为8失败、1通过；补齐领域输出后7通过、2个缺少输出模型的失败；首轮部分字段校验又留下3失败、1通过。修复保留了这些首次记录，未覆盖失败文件。最终冻结源码与独立安装wheel各46项专项通过，包含20,736种排列核对和综合、原始盘、九专题的33项三端错误拦截。伪造事件、漏掉候选或错误载体引用，在不相关字段裁剪前也会被拒绝。

408条完整旺衰及历史算术值和类型完全不变，八字证据链只增加声明字段；367条公开记录仅增加清单，原标签、未知、约束及旧值不变。原19例逐例结果保持不变。相关旧测试前后均为416通过、6失败；未改旧断言，其中固定历史版本、旧完整输出和前轮源码哈希约束仍失败，不能声称全套已绿。源码哈希类断言读取共享当前工作区，即使切换旧运行时也会看到当前文件；这点单独保留在验收说明中。

实际REST、stdio MCP和CLI在冻结源码与独立安装wheel各取得93份首次返回，覆盖综合、原始盘、九专题和四个反例的源核对，固定8192字符预算。大结果沿用同一次运行的校验哈希和分页读取完整内容；没有重算替代全文。两后端及同次三端的业务值一致，见协议和安装包核对（本地数据：`validation/bazi-branch-inventory-files-v1/qualified-backends-first.json`）。原先不分页的失败门槛没有改判。`analyze_destiny`本身没有REST路由；其余对应入口实际验证REST。

wheel从冻结运行时副本构建，用于本地代码与资源一致性验证。该运行时快照不含发布元数据所用README、LICENSE、NOTICE，构建产生缺文件警告；未称为可发布发行包。快照中其他术数体系的并行改动单独记录，不归于本轮八字修改。全仓文档检查的遗留失败单独保留，不把本轮文档链接通过当成全仓通过。

```bash
uv run --locked --extra dev pytest -q tests/test_bazi_branch_inventory.py tests/test_bazi_branch_inventory_transports.py
uv run --locked --extra dev python scripts/audit_bazi_branch_inventory.py --output /tmp/bazi-branch-inventory-audit.json
```

十九题补充模型解释验收仍待原授权回复，新模型调用为零；旧十一题已执行结果保留，不能代替新增字段的模型解释验收。独立专家复核未完成，现实预测继续为`not_tested`。本轮没有新增原典符合度信用，整体目标未完成，未作满分或权威认证。
