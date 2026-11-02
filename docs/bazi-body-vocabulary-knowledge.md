# 八字旺衰用词与工程三档

`bazi/classical_force_semantics/日元强弱与性情措辞`现为修订3，方法标识`dtcw1947_body_vocabulary_semantics_v3`。修订2的木四态摘要有三处对应错误，本次据同版PDF177—178及此前冻结的20项全表纠正。原始错误、首次失败断言与修订2的15项工程检查记录保留；这些工程检查未验证四态对应，不能作为这项原典语义的通过证据。

| 木的状态 | 原页关系，现已纠正 | 修订2的问题 |
| --- | --- | --- |
| 太旺 | 似金，宜火炼 | 此项原来相符 |
| 旺极 | 似火，宜水克 | 错写成土止 |
| 太衰 | 似水，宜金生 | 与衰极对应互换 |
| 衰极 | 似土，宜火生 | 与太衰对应互换 |

当前第八条内容按冻结的五行×四态共20项关系生成，`provenance.entry_curation.source_relation_binding`同时保留20项、来源页码、原转录标识和散列。结构化关系与实际呈现文字逐项核对，核查不只覆盖木。此表是原段的有条件取用比拟，未定义可计算的四态数值阈值，没有改变字面五行或实现新的强弱分类器。

其余七条、另外84个词条对象和85条总量保持。新增内容的不同声部仍分别归属：PDF50〈初学捷径·衰旺强弱之别〉为李雨田增补，PDF175—178的相关根气与四态文字属于“任氏曰”；工程强／中和／弱和编辑边界另列。独立原典复核、有效力量判定及现实预测没有因此获得认证。

## 读取与校验

```bash
uv run --locked --extra dev fatebridge knowledge_read --domain bazi --category classical_force_semantics --key 日元强弱与性情措辞 --include-snapshot-text true --response-char-limit 0
uv run --locked --extra dev python scripts/build_bazi_four_state_knowledge.py --check
```

第一条命令应返回八条内容、词条修订3及20项来源关系；最后一条命令核对源表驱动的生成结果，不修改资料。生成器仅整理这一词条，不运行旺衰计算，也不从人物经历补造标签。

本次事前协议（本地数据：`validation/bazi-body-vocabulary-knowledge-v3/protocol-first.json`）与验收记录（本地数据：`validation/bazi-body-vocabulary-knowledge-v3/report-first.json`）保留：

- 原修订2的完整85条资料及三处错误关系；纠正前，生成检查与来源关系检查均失败。
- 冻结源码中21项检查通过，覆盖原页转录与20项关系、旧错误负例、其余84条保持及REST／MCP应用协议／CLI交付一致性；1,919个输入运行后散列不变。
- 独立stdio新进程返回修订3、八条内容及20项关系，七个内容和来源字段与冻结服务结果一致。
- 本次现有MCP连接观测仍为修订1。共享进程未重启，不能把新进程结果称为既有连接已更新。

修订2协议与历史记录（本地数据：`validation/bazi-body-vocabulary-knowledge-v2/report-first.json`）保持原样。旧版本测试按归档的修订2字节核对，当前交付测试明确验证修订3；原来的2项版本绑定失败另存，没有改写成首次通过。

本轮没有新模型解释试验，也未调整数值内核、原典力量标签或先前原26处分歧的分母。另排队的五例仍绑定原先冻结的输入和后台；旧五例机械0／5、原40,219条包络失败证据、41项边界冲突以及独立原典复核条件均保留。本次三处摘要纠错不能抵扣原26处分歧，也不是现实预测成绩。
