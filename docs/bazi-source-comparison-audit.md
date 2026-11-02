# 原典字面四柱核对

`bazi_source_compare` 让已明确四柱的原典命式直接进入研究核对。它先计算当前模型的旺衰，再查全部同柱登记记录；无需补造历史人物的出生日期、性别、地点或生时。REST 为 `POST /api/cn/bazi/source-compare`，MCP 和 CLI 使用同名工具。

当前索引文件v4保留26组361条记录、315个不同四柱输入。121条有保留强弱编释，240条未知或未作身强弱标注；旺衰算法仍为v7，23个不同输入存在已知差异。[新增三个完整单元](bazi-capacity-three-units-audit.md)的12条全部纳入，原349条完整对象保持相等。[完整会局升级](bazi-calendar-point-and-bureau-adoption.md)保留原26项首败，修复其中3项，未改原柱、标签或数值权重。全部材料已暴露，查询相符不增加独立试验、全书符合度或现实预测的验证信用。当前登记（本地数据：`../tests/fixtures/bazi_source_corpus_v7/registry.json`）与扩展协议（本地数据：`validation/bazi-capacity-caid-fenyu-enyuan-v1/index-extension-protocol.json`）约束完整范围；首次协议（本地数据：`../tests/fixtures/bazi_source_comparison_v1/protocol.json`）继续保留。

## 计算与编释分别返回

`current_calculation` 返回当前计算、方法和审计分量；`source_comparison.records` 返回所有同柱登记编释、来源文件散列及可取得的底本定位。状态分别表示相符、差异、编释相互冲突、只有未裁定记录或未收录。没有相符记录也不能据此断言原书不存在该例。

以《滴天髓阐微》1947年本所录“庚午 乙酉 庚午 壬午”为对照，当前仍判强，保留编释为弱，状态为 `known_annotation_mismatch`。接口展示这一差异，不从参考标签改写计算。原文对三午制酉与生扶效力的论述，仍需在机制层解决；不能通过移动阈值或按命例查表冒充改进。

以下命令已在本地安装包运行，参数来自原典录文，不是用户的出生资料：

```bash
uv run --locked --extra dev fatebridge bazi_source_compare \
  --year-pillar 庚午 --month-pillar 乙酉 --day-pillar 庚午 --hour-pillar 壬午 \
  --fields four_pillars input_context current_calculation.strength_level source_comparison summary \
  --strict-fields true --include-snapshot-text false
```

直接给出的柱只要求干支字符与长度正确。即使原录不合现代五虎遁、五鼠遁或甲子配对，也保留原柱，另列内部关系检查；不认证其历史公历出生瞬间。完整结果的 `calendar_accuracy_assessed` 和 `historical_birth_datetime_verified` 均为假。

## 来源身份与首次失败

首次v1索引保留；v2仅根据明确的整书散列补足来源身份，不能按命例编号推断底本。v3修复一条中和篇记录继承了衰旺篇容器标题的问题，依据是该条明确的不同来源链接。v4追加完整三章12条，原349条连同来源对象逐项保持v3原值。字面匹配方法仍为v3，索引文件版本v4和登记v7另行标识；六条旧合局材料缺少明确整书身份，标题与链接继续为空，不擅配另一版本。电子转录也未升级为已核书影或独立专家认证。

历史完整对象核对首次失败于已有新增字段 `assessment.stem_energy_accounting.source_order_review`。该字段在本接口协议冻结前已经存在；核对说明（本地数据：`../tests/fixtures/bazi_source_comparison_v1/baseline-reconciliation-v1.json`）保留首败。仅将这一已声明的新增溯源字段单列，全部旧字段、数值和判级仍逐项精确相等，新增字段要求数值政策未采用且计算效力为无。

v3的实际生成器及其散列已冻结，其历史生成检查属于当时的v6登记。当前生成入口为 `scripts/build_bazi_source_index_v4.py --check`，保留全部旧索引字节；旧生成器依赖旧范围，不再宣称覆盖当前新增材料。

## 本地验收范围

本地回执（本地数据：`validation/bazi-source-comparison-local-v1.json`）与归档索引（本地数据：`validation/bazi-source-comparison-v1-logs/artifact-index.json`）保留源码清单、安装包、首败及恢复材料：

- 冻结源码378项、无可选天文后端的安装包55项通过；全部349份旧数值回执和26个分歧保留，旧出生请求模型与目录顺序保持。
- REST、原生MCP、CLI核对完整结果与已发布投影；损坏的专业字段不能被投影隐藏。
- 源码与安装包的独立stdio进程各完成7次有效调用、1次缺项拒绝、41页同次结果散列核对；另有3个实际安装包CLI命令。
- 一次源码检查在378项断言通过后，发现构建器改写临时快照的打包清单；归档前后字节并恢复原散列后，重新完成378项及完整性检查。全部1,094个源文件可由安装包和12份差异字节恢复，且已逐文件实际恢复核验。
- 公共文档／合同首轮仍有4项涉及风水模块计数或示例的失败，原日志保留；本轮没有将全仓检查、Linux黄金字节、部署或真实模型解释验收记为通过。

没有新增模型执行、原典独立外审或现实前瞻样本。解释忠实与预测效度继续各自验收，现实预测保持 `not_tested`。
