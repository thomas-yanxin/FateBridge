# 原典姓名与出版者标注勘误

本轮将已有书影支持的两处姓名错配和58条出版者标注更正送入公开`bazi_source_compare`结果。新索引为`source_annotations_v8_witness_identity`，旧v7索引、原编号、命式、强弱标签及未知项完整保留。原19例仍有17例旺衰分歧；资料勘误新增旺衰符合数为0。

| 原编号保留 | 原登记姓名保留 | 同一命式在原页所印姓名 |
| --- | --- | --- |
| ZP-PROSPECTIVE-17-MAO-HEAVY | 茅状元 | 馬參政 |
| ZP-PROSPECTIVE-18-MA-LIGHT | 马参政 | 茅狀元 |

依据是《秘本子平真诠》PDF73原页（本地数据：`../tests/fixtures/bazi_condition_evaluation_v1/model-inputs/primary/ziping-p73.png`）的字面命式与姓名，不等于已确认真实历史人物。该页的“此身重印轻”“此身轻印重”分别保留，不能因姓名更正而改动原强、弱映射，或把印重直接等同于身强。

同一整书PDF1书名页（本地数据：`validation/bazi-condition-evaluation-files-v1/ziping-title-p1-first.png`）印“上海世界圖書館發行”，旧索引58条同书记录误记“世界书局发行”。整书SHA-256为`71402a780b0351b54edf121a51bc4a4a4ce5896496c35b954563ee06f1a6f620`。新版只改对应出版者标注，原登记文字、原记录散列、书影页码和图片散列随`source_identity_revision`返回；两条姓名记录另有`name_as_printed`和保留旧名的`name_correction`。

全部367条公开登记、321个字面输入、123条已标注、244条未知及3条集合约束保持。对修改前冻结的367份完整公开结果，与冻结源码及wheel的同输入结果逐项比较，只有事前声明的资料字段、索引元数据和说明文字变化；计算对象、原典标签和JSON类型不变。7个旺衰、身印、通关及精确阈值计算文件的散列保持。以上证明资料修复和数值保持，不证明原典力量算法已完整实现。

首次新增测试18通过、2失败，发现校验器将布尔值与整数相等视为同一事实；更正为保留JSON类型的比较。首次公开协议测试14通过、5失败，又发现字面量字段允许布尔／整数混淆；新增来源修订字段现作严格类型检查。两次首次源码、XML和失败均保留，未改动测试断言。

既有相关测试修改前86通过、6失败；增加20项测试并只更新旧8项错误注入的当前索引文件名后，106通过、6失败。六个失败名称集合保持，未声称原旧完整数值门槛通过。索引文件名之外的旧测试AST、八种错误注入和断言均保持。冻结测试环境首次另缺共享夹具和生成脚本，依赖补入单独散列绑定的重放材料，首次失败未删除。

最终冻结源码与安装包各39项新增测试通过。独立构建wheel的1278个包文件与冻结来源逐字节一致。各完成24份实际本地REST、stdio MCP和子进程CLI回复，首份最大8180字符，固定预算8192；各22份需同run回读。首次采集脚本误用REST引用的读取入口、随后误把CLI精简引用当完整清单，错误均保留。现分别使用REST清单端点、MCP清单资源和CLI `result-read`完整校验分页，核对原run及散列，不重算代替旧结果。原完整视图“不分页”门槛继续未通过。

磁盘耗尽使一份复测XML未能写完，未计为通过。之后只清理逐字节相同的旧临时构建副本和原典库副本；已封存wheel、工作区原典原件、首次日志和未匹配内容保留。类型检查首次内部错误另存，独立缓存检查通过；不把工具内部错误改记成功。

这是本地源码与wheel验收，当前聊天未连接`bazi_source_compare`工具，未声称已有远端服务更新。新增19题真实模型解释验收仍待既有授权问题回复，未启动模型；此前旧11题的授权和成绩不挪用。现实预测没有真实数据，继续`not_tested`；独立专家审阅、剩余旺衰分歧和全范围目标未完成。

```bash
uv run --locked --extra dev python scripts/build_bazi_source_index_v8.py --check
uv run --locked --extra dev pytest tests/test_bazi_source_identity.py tests/test_bazi_source_identity_transports.py
uv run --locked --extra dev python scripts/audit_bazi_source_identity.py --output /tmp/bazi-source-identity-audit.json
```

本轮封存回执（本地数据：`validation/bazi-source-identity-local-v1.json`）保留完整范围、首次失败与前序证据绑定；审计只读原件，不调用模型或重判原标签。
