# 八字完整业务结果的计算依据校验

完整工具结果不能只保留一个空业务对象就报告成功。本次在共享执行层加入八字完整依据校验，覆盖历法、四柱、身印收支、月令与通关、专题及运年来源；合法摘要投影继续使用原有部分输出模型。校验只比较已返回事实，不调用求解器，不补缺失出生资料，也不修改数值公式。

## 范围与首次证据

实际入口共11个：综合`analyze_destiny`、标准命盘`bazi_birth`及九专题。综合仅有MCP／CLI，标准命盘和九专题有REST／MCP／CLI。此前所称十工具回归实际为标准命盘加九专题；这些历史结果保持原记录，不能把它们扩称为综合入口已经验收。本轮同时覆盖独立综合入口，不增加不存在的REST路由。

预先冻结方案（本地数据：`../tests/fixtures/bazi_complete_anchors_v1/protocol.json`）保存范围、首次失败及原门槛。86份修复前有效结果（本地数据：`../tests/fixtures/bazi_complete_anchors_v1/baseline-first.json.gz`）使用明确的虚构出生资料，覆盖男女、未知性别、未起运、手动运年及太阳时跨1899／2101农历支持边界；不支持的参数没有传入相应工具，适用范围另记，重复输入不算独立样本。

143个首次缺项控制（本地数据：`../tests/fixtures/bazi_complete_anchors_v1/counterexamples-first.json.gz`）从原有效结果分别删除或清空业务根、历法、证据链、身印、通关、月令、时运及专题依据。旧完整输出校验全部接受。这些是人工故障探测，86份原生产结果没有缺项，不能写成143个真实命例算错，也不增加原典符合率或现实预测准确率。

## 完整依据与未知状态

规则按实际领域构建函数及公开Schema制定，校验内容包括：

- 命盘及综合的四柱干支、日主及同次旺衰回执，历法时区、节气来源和月界经过量。
- 全部入口的四柱实际干藏证据、十神类别、身印分量、来源规则、月令、根类、通关节点与路径汇总。
- 九专题各自的主要计算区块与叶字段、对应专题依据，自动运年的日期和时区锚点或手动覆盖的来源。

空观察列表、数值0、布尔`false`仍是合法结果。`selected_stem=null`、`chosen_path_id=null`及未裁定状态不改写；未知性别保留两套配偶星依据，不能伪选一套或补婚姻分数。明确手动运年不强求不存在的自动分析时刻；未起运的大运柱和年龄可为`null`。太阳时跨出农历支持范围时，保留`lunar_calendar=null`及支持状态、范围和原因。

农历`conversion_source`在当前生产者中是补充表日期的条件字段，普通日期未统一提供此专字段；本次不伪造来源。节气实际来源字段为`resolution_provider/ephemeris_model`。首份原型误将`conversion_source`普遍设为必需，并误用节气`source`字段，导致86份有效结果被原型拒绝；首份原型（本地数据：`../tests/fixtures/bazi_complete_anchors_v1/first-domain.py.txt`）及失败日志保留。依据实际构建函数和公开字段修正后，原86份输入与全部143项拒绝门槛均未删改。

完整校验在共享`execute_spec/execute_tool`内、任何投影之前执行，缺项成为内部输出错误。公开部分模型仍能读取合法投影及历史对象；不能拿投影结果当完整业务结果重新送入完整校验。错误信封与其他领域保留各自合同。

## 交付验证与尚未完成的部分

原始控制回放（本地数据：`validation/bazi-complete-anchors-accepted-v1.json.gz`）保留143项新旧判定及86份有效分支的逐项结果。两个独立进程的完整业务对照（本地数据：`validation/bazi-complete-anchors-public-first-v1.json.gz`）分别使用冻结旧完整校验与新校验，覆盖全部11入口；有效输出、文本及公开部分Schema保持相同。两进程共用当前依赖和领域代码，不冒充整个历史运行环境。

实际支持的协议面分别检查正常摘要投影，以及只请求摘要时仍拒绝空完整业务结果。综合的MCP／CLI独立验收；标准命盘与九专题另验REST。协议故障注入不是真实模型解释试验，旧三批模型与首次失败保持。

完整旺衰回放（本地数据：`validation/bazi-complete-anchors-source-corpus-v1.json.gz`）保留原19个分歧与全部既定门槛。本轮没有新增数值修复、原典符合例或现实数据；独立专家和新增真实模型解释验收仍未完成，现实预测继续`not_tested`。

本地回执（本地数据：`validation/bazi-complete-anchors-local-v1.json`）分别记录测试、首次失败、构建及全仓检查。完整性校验只证明所列必需依据没有被静默丢失，不证明这些依据已达到原典或现实预测满分。

新增170项测试在源码和冻结构建后的wheel中分别通过；914份必需包文件与构建快照逐字节相符。首轮169通过、1失败是新增测试漏填既有错误信封必需的`retryable`，原测试及失败保留；修正测试输入后，仍同时拒绝这份原缺项错误信封，错误模型未放宽。构建后其他聊天继续修改共享历法等源码，本地回执分别保存冻结构建和随后工作树的范围，不能将该wheel验收扩称为未来工作树或部署验收。

相关133项回归为123通过、10失败，不能写成全部通过。十项都是旧通关视图的8192字符不分页门槛：业务事实相同，但补充运行时元数据触发`result_delivery`。未提高预算、删掉原断言或隐去分页。首次预算探测（本地数据：`validation/bazi-complete-anchors-budget-first-v1.json.gz`）及同次载荷重放（本地数据：`validation/bazi-complete-anchors-budget-replay-v1.json`）确认原／新完整校验都会触发分页，原门槛继续未过。首个读取器误把文件外层记录的字节与载荷散列比较，原错误结果保留；随后按实际`file_payload_path=payload`与既有序列化规则核对同一份归档，两个载荷散列及长度均相符，无重算或丢失业务事实。

```bash
uv run --locked --extra dev python -m scripts.audit_bazi_complete_anchors --output /tmp/bazi-complete-anchors.json.gz
uv run --locked --extra dev python -m scripts.audit_bazi_complete_anchors_public --output /tmp/bazi-complete-public.json.gz
uv run --locked --extra dev python -m pytest -q tests/test_bazi_complete_anchors.py
```

审计脚本拒绝覆盖已有结果。
