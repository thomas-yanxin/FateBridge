# 激活门、中心定义与完整结果解释复核

[人类图说明](human-design.md) · [调用合同](contracts/human_design.json) · 验收记录（本地数据：`validation/human-design-gate-context-verification.json`）

本次补齐激活门的中心语境，并强化完整结果的解释核验。它没有改写黄经、门线分界、设计根、原有十条／闰秒十一条固定说明，或原38项专业要求。核心及人生角色规则仍为1.39.0；新增独立子规则为`human_design_gate_activation_context_v1@1.0.0`。

## 公开资料的两种悬挂门口径

[Jovian Archive词典](https://jovianarchive.com/pages/human-design-dictionary)把activation与active/dormant分开：未定义中心中的本命激活仍然存在，其表达称为dormant。不能把休眠误报为没有激活，也不能把单门当作完整通道。

同站两篇文章对hanging使用了不同口径：[2025年64门文章](https://jovianarchive.com/blogs/chart-interpretations-components/the-64-gates-in-human-design-what-they-represent-in-your-chart)包含定义与未定义中心中未接成完整通道的门；[2026年中心、门与通道文章](https://jovianarchive.com/blogs/human-design-basics/centers-gates-and-channels)把hanging限于定义中心，把未定义中心中的激活称为dormant。两篇署名Ryan Hanna，作者说明包含AI辅助写作与分析师复核；不能将其称为Ra Uru Hu的2001年原稿。

因此保留既有`bodygraph.hanging_gates`的宽口径，同时明确返回：

- `activated_gates`：人格和设计两侧的本命激活并集。
- `active_in_defined_centers`：并集中位于定义中心的门。
- `dormant_in_undefined_centers`：并集中位于未定义中心的门，仍属于本命激活。
- `broad_unpaired_activated_gates`：没有参与任何完整通道的激活门，与既有hanging字段一致。
- `defined_center_hanging_gates`：上述未接通门中位于定义中心的子集。

每个门还保留人格／设计来源侧、所属中心，以及已完整和未完整连接的端点对。整合区域中的一个门可以同时参与已接通和未接通的连接，不能因其中一条接通便丢弃其他连接。以上是体系内的结构分类，不认证心理、基因、中微子或现实因果，亦不涉及尚未实际计算的人际合图或行运定义。

另保存一项新的公开资料分歧：[现行门与六爻说明页](https://jovianarchive.com/pages/gates-and-hexagrams-in-human-design)将太阳白羊10°举例为25门，而冻结2001数值表及现行计算对应21门。原文、表值、网址与采集散列分别保留；未取得勘误，没有改动算法以迎合该例，也没有把这个反例评分为通过。它不取代既有29.1／29.2印刷分界及交叉名称分歧。

## 同一次运行中的完整核验

完整结果新增`gate_activation_context`。`nominal`仅解释名义盘；`witnesses`逐项读取已发布的交点约定、交点后端、整盘后端和生时范围中的联合见证，保留实际数组路径、各侧门号引用、完整通道引用及投影散列。不把名义盘中心状态拼接到另一TT、后端或生时样本。见证数量是路径语境数，可能对应重复状态，不能当成独立样本数；没有生成新的物理时刻。

`interpretation.gate_activation_context`提供带同run字段依据的确定性说明。`verify_human_design_reading`重建所有新语境及文字、检查逐项引用，拒绝换门、换中心、改来源作者／散列、混用见证、删除见证、改写说明和伪造物理认证，即便调用方重算业务散列也不能通过。JSON对象排序不改变语义，见证输出按确定性的路径顺序产生；数组顺序仍保留。

旧契约兼容由两项已冻结的完整Schema指纹明确识别，不依赖样例ID或“字段缺失就算旧版”。旧契约且四个新增区域均不存在时，继续完整核对原有说明和数学事实，返回`gate_activation_context_status=not_in_declared_legacy_contract`，不认证旧结果中的新能力。新版或未知契约必须完整提供新区域；删掉全部新增字段、重新散列仍拒绝。存在任何新增区域就按新增要求核验。元数据本身不是数字签名，调用方仍须保管可信原始回执。

摘要配方名`gate_context`仅表示调用合同中的`fields`列表，不是请求参数。完整验收必须读取完整同run结果，摘要投影不能替代完整结果。REST把`fields`作为查询参数；MCP放在调用参数中；CLI使用`--fields`列表。新增来源标识令原8192字符周期卡越过旧回执边界，传输层现优先从同一清单取得重复的首页URI，保留业务字段与完整来源回执，不提高预算、不截短字段。原始结果与URI仍在同一次运行的不可变结果文件／清单中。

## 独立参考与验收边界

改生产代码前固定计划和独立图参考。参考生成器不导入FateBridge，读取未改动2001表中的64门中心与36通道，覆盖空图、全部64单门、每条通道与其余62门、整合四门的全部16子集、单侧／双侧激活和提前固定种子的1024对门集合，共3339个图案例。压缩仅改变存储方式，解压后的原始参考SHA256保持`35948eae3e18b5e50fee5a5f8737c9faf940f39457bc6527012c6bea811aec50`。这些是合成图结构事实，不是3339位真人或独立预测。

```bash
uv run --locked --extra dev python scripts/build_human_design_gate_context_reference.py --check
uv run --locked --extra dev pytest -q tests/test_human_design_gate_context.py tests/test_human_design_gate_context_transports.py tests/test_human_design_gate_context_delivery.py
uv run --locked --extra dev python scripts/build_codex_call_contracts.py --check
uv run --locked --extra dev python scripts/build_scenario_manifest.py --check
```

验收记录（本地数据：`validation/human-design-gate-context-verification.json`）分别报告原2131案例保留、完整回归、旧出版方回执、原26完整结果的精确比较、60分钟最大输入、Linux安装包、真实stdio MCP／外部CLI与黄金快照。首次REST参数误用、对象顺序缺陷、历史回执兼容失败和摘要预算回归均保留原始失败记录，修复后按原要求复验。软件回归通过不能认证完整384线正文、全部固定规则、完整历法范围或任意模型自由文本。原专业验收仍按38项报告，未完成项和失败项不改名、不删除；现实预测仍没有可评估样本。
