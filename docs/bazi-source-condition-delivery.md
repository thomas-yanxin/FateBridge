# 原19例条件校读的公开交付

本轮把既有19份原页条件校读接入`bazi_source_compare`，对应21条来源记录。两条重复来源原本没有强弱标签，仍保持未知。补充的是原文条件及其校读出处，全部旧命式、标签、未知、集合约束和计算保留；不将19份开发者校读计作独立专家结论或新增原典命中。

每份`source_condition_review`提供所选书影的PDF散列、页码及页图散列，区分段落条件、原文回指、身印分别陈述和需要外审的语义映射，保留身印与通关条件说明。摘录标为开发者按范围转录，不能当作自动校勘完成的逐字原文。ML-02另列原文“立春后六日、戊土司令”；没有从这句话补造公历出生瞬间、认定日数起算约定或给工程月令选择司令。

旧v8索引逐字节不变，新增校读层由冻结方案生成。运行时按索引原记录、命式和散列核对绑定；已给出的条件事实不能改成别例、另一页或已经裁定有效。部分字段缺失仍保持缺失。数据层不打包私有验收题号、标准答案、评分规则、模型输入散列或历史模型成绩；旧19题模型方案和后台保持封存。

可使用已发布的`source_conditions`视图：把该卡的`fields`复制到请求，设置`strict_fields=true`和`include_snapshot_text=false`；视图名不是请求参数。数组按既有投影合同整段选取，完整结果需要时读取同一run的`result_delivery`。首次错误视图曾穿过数组，19例HTTP422与首次源码均保留，修正字段配置，没有放宽预算或改造投影器来迁就它。

复核前39项来源勘误测试通过；新增条件层后，其中要求完整输出只含上一轮勘误字段的旧测试失败，原门槛与失败均保留。此前v66冻结源码和安装包39项通过的回执不改写。新阶段按预先声明的新增字段核对全部367条完整结果，不能将新字段白名单挪用为旺衰或原典符合率。

原19例仍有17例分歧，身印有效力度及通关仍未裁决。新增19题真实模型解释验收待单独授权；当前新增模型调用为0。现实预测缺少真实数据，继续`not_tested`。全仓文档检查此前失败的原件保留，不修改历史或封存副本以换取绿灯。

```bash
uv run --locked --extra dev python scripts/build_bazi_source_condition_reviews.py --check
uv run --locked --extra dev pytest tests/test_bazi_source_conditions_public.py tests/test_bazi_source_conditions_public_transports.py
```

本地复核结果：冻结源码与独立wheel各75项新检查通过，1292个包文件逐字节相同。两套环境各完成126次实际响应，覆盖19例及两个对照、完整结果及条件视图的REST/MCP/CLI；结构化JSON和MCP实际文本最长8103字符，CLI实际stdout最长8173字符，均不超过8192。每套117份分页结果均核对同run完整散列，另外9份首轮即完整。REST为本地TestClient，MCP为实际stdio，CLI起算为子进程；不可变结果逐页由同一CLI解析入口读取。未发布或部署，也不宣称模型已阅读这些条件。

协议读取器首次重复写入已预读页、随后错误假定压缩引用含REST路径和页大小，错误日志及当时原件均保留。恢复只读取已保存的首次工具响应、原结果ID和散列，再调用尚未执行的用例；原MCP起算调用数仍为每套42次。额外预读助手曾在旧助手仍运行时启动，已取消并保留轨迹；旧助手随后因缺少快捷字段终止后，才确认切换到按实际返回页求步长的读取器。没有放宽字符预算、页大小或完整散列断言。

原页母记录见19例条件校读原件（本地数据：`validation/bazi-condition-evaluation-files-v1/reviewer-only-all19-source-conditions-first.json`），ML-02可对照PDF172整页（本地数据：`../tests/fixtures/bazi_condition_evaluation_v1/model-inputs/primary/ditian1947-p172.png`）。本轮证据清单见封存回执（本地数据：`validation/bazi-source-conditions-public-local-v1.json`）。

```bash
uv run --locked --extra dev python scripts/audit_bazi_source_conditions_public.py --output /tmp/bazi-source-conditions-public-audit.json
```
