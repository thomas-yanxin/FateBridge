# 节气重复小时的无损交付

节气实际时刻原已保留时区，内部月界、节后经过量及起运采用同一物理瞬间比较；公开`SolarTerm.as_dict()`却只给去掉时区的本地钟面。回拨时同一钟面可能出现两次，消费端重新附加时区会默认选第一次，造成一小时误差。这是计算结果交付中的事实丢失，不能靠解释文字补正。

Python的[PEP 495](https://peps.python.org/pep-0495/)将重复钟面的先、后两次分别记为`fold=0/1`，也指出时区跳变不一定是一小时。[datetime文档](https://docs.python.org/3.12/library/datetime.html#aware-and-naive-objects)区分带偏移时刻与不能唯一定位瞬间的裸钟面。本次保留旧`datetime`显示值，另给实际`datetime_with_offset`、`utc_offset_seconds`、`fold`及`timezone`。偏移精确到实际秒值，不取整为整小时或整分钟；未知时区的旧对象不借用宿主时区补造事实。

## 完整队列与原始失败

冻结方案（本地数据：`../tests/fixtures/bazi_term_offset_v1/protocol.json`）先固定原1899—2101年全部4,872个已暴露节气时刻、pytz 2026.5 / IANA 2026e的597份TZif原字节、修复前完整源码和门槛。扫描全部2,908,584个配对，保留两种fold和全部时区别名，未预筛选成功年份或地区。首次发现（本地数据：`validation/bazi-term-offset-discovery-first-v1.json.gz`）包含160条重复钟面记录、15个不同节气事件，旧默认还原有81条失败，最大误差3,600秒。时区别名、共享事件及对照并非独立样本，不能累加成预测准确率。

端到端例按预先规则取出生范围内最早、再按时区字典序的fold=1记录：1921年夏至、Africa/Algiers，实际为`1921-06-21T23:35:35.727999+00:00`；旧`1921-06-21 23:35:35.727999`若默认fold=0，会被附成+01:00，提前一小时。虚构出生取两日前正午，避免把公开输入本就拒绝的歧义生时当成有效出生。本例是开发回归，已暴露，不是独立留出验证。

首次修复回放（本地数据：`validation/bazi-term-offset-repair-first-v1.json.gz`）保留全部160条及4,872条UTC对照，均精确还原传入瞬间；逐项旧字段相同，历法顶层数值函数AST相同。十工具完整结果对照（本地数据：`validation/bazi-term-offset-public-first-v1.json.gz`）在两个独立进程分别使用冻结旧序列化器和新序列化器，保存综合及九专题完整业务结果，66个节气对象补入信息，原字段、文本、旺衰及起运值全部一致。这是同一现行依赖下的序列化对照，不冒充整个旧后端复现。

首次测试的`fold=true`漏检保存在原始失败（本地数据：`../tests/fixtures/bazi_term_offset_v1/pytest-first-failure.log`）；Schema的Literal接受了Python中与1相等的布尔值。新增明确整数校验，拒绝布尔、浮点、字符串及超范围fold，同时允许只投影fold或只投影带偏移时间的合法部分响应。旧裸钟面仍兼容；新带偏移时间若与同时供给的偏移或旧钟面矛盾，统一执行层拒绝该错误事实。两次探测的多余`birth_second`及缺少模块搜索路径失败亦分别保留。

## 解释验收及未完成部分

综合与九专题实际REST、原生MCP和CLI分别核对完整日历子树与严格叶字段投影，检查实际模型、来源、偏移、fold及`engine_is_approximate`；未用模拟工具结果代替协议验收。详见[测试](../tests/test_bazi_term_offsets.py)及本地验收回执（本地数据：`validation/bazi-term-offset-local-v1.json`）。

解释中需要复原交气瞬间、比较两个时刻或核对经过量时使用`datetime_with_offset`；旧`datetime`只作本地显示。`fold=1`表示重复钟面的后一次，不表示第二个节气或把日期改一天。`timezone`是实际tzinfo的名称或描述，自定义固定偏移的描述不保证能直接用作出生时区参数。

这里保证保留已算时刻，未认证实际时刻的绝对物理精度。1961年前仍按已有UT1历史约定，未来规则是冻结时区库的推算；TZif复现不证明所有历史资料或未来法律正确。实际命名太阳模型和原生Moshier控制仍按[既有独立TT审计](bazi-moshier-model-audit.md)分别报告，原生501个超差点与1秒线不变。

本次没有裁定日主与印的有效承载、月内司令日界或有效通关。此前24组314条记录、268输入和25个分歧的固定回归保持；当前共享登记另有已暴露的完整性情35造，完整复放（本地数据：`validation/bazi-term-offset-source-corpus-v1.json.gz`）为25组349记录、303输入、26个不同输入分歧，原19例仍未解。新增登记不算本次修复带来的准确度改善。

既有三批真实模型答案、首次综合工具约束失败与逐句审阅不重写，33例重算的机械成绩仍逐例相同。但相关回归发现共享`evaluate_agent.py`的`grade/observations`已发生额外变更，原“评分器AST保持不变”守卫失败，保留为失败，没有改测试或改门槛放行。新增时间字段尚未追加真实模型解释试验，也未完成独立专家验收，因此不能宣称当前解释验收全部通过。现实预测无真实数据，继续`not_tested`，不据本次局部修复宣布满分或权威预测效度。

后续[评分规则隔离](bazi-grader-policy-audit.md)已恢复原函数身份和旧用例的实际执行路径，原守卫通过；本页首次回执中的失败保留不变。新增拒绝规则独立命名，33例完整原评分及原始失败保持，仍未增加模型解释或现实效度信用。

## 复算

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_term_offsets --output /tmp/bazi-offset-discovery.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_term_offset_repair --output /tmp/bazi-offset-repair.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_term_offset_public --output /tmp/bazi-offset-public.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_term_offsets.py
```

脚本拒绝覆盖已有输出；首次结果、全部原始输入、TZif及源码散列继续保留。
