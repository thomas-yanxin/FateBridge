# 沈氏城门：同元龙、独立运盘与水形条件

[玄空宅盘](fengshui-xuankong.md) · [专业审计](fengshui-depth-audit.md) · [虚构请求](examples/fengshui-city-gate.json)

`shen_city_gate_v1@1.0.0` 在现有 `fengshui_xuankong_natal`／`fengshui_assess` 中显式启用，计算向首左右相邻两宫、同元龙具体山位，以及该宫运星入中后令星是否逆飞到门。参考运独立输入，历史宅运、年星和系统日期都不会暗中代填；原始中州派山向盘保持原值。

## 来源与验收范围

规则版本、印本来源、数字排法、术语差异与现场适用条件统一维护在[风水技能参考](../skills/onda-fengshui/references/city-gate.md)。独立夹具（本地数据：`../tests/fixtures/fengshui_city_gate_v1/reference.json`）保留20项原文关系、定位及四张页图指纹；审计保留负例并拒绝删样。它只验证选定条款，尚未完成全书与现实预测验收。

## 调用与状态

独立工具传 `city_gate`；聚合传 `xuankong.city_gate` 并选 `methods=["xuankong_natal"]`。仅算城门门位不必提供历史 `period` 或现场观察：

```bash
uv run --locked --extra dev fatebridge fengshui_xuankong_natal \
  --request-file docs/examples/fengshui-city-gate.json \
  --fields layers.xuankong_natal.city_gate_analysis coverage.city_gate_status rulesets rule_trace \
  --strict-fields
```

该示例为虚构315°磁北宅向、二运城门参考。未提供历史定运时，原始宅盘可为 `partial`，而 `city_gate_analysis.calculation_status=complete`；分支各读自己的范围，不能用原始宅盘缺项否定已完成的门位计算。参考运不完整或省略证据会直接报校验错误。

输出 `layers.xuankong_natal.city_gate_analysis` 含独立规则来源、参考运、朝向候选、每门数字追踪、水形条件及未匹配观察；`coverage.city_gate_status/city_gate_calculation_status/city_gate_missing_inputs` 支持严格投影。出现角度候选时保留所有不同向山，既不挑最有利门位，也不从候选数量计算概率。同一向山的下／替模式不进入本版城门宫运公式；所用角区及未使用模式明确保留。

## 观察输入与解释范围

`observations` 按需提供全宅中心、磁北二十四山水形，含 `mountain`、`observation_basis`、`evidence` 及至少一项事实。事实字段和交叉约束以共享Schema为准；未提供观察时只计算门位，照片保持候选，未匹配山位单列。

数值符合、水形符合及现场是否已确认分别保留。`combined_condition_match=true` 只表示选定数字与已确认条件同时满足；传统含义及未覆盖的形势质量见[技能参考](../skills/onda-fengshui/references/city-gate.md)。本分支不生成施工或开门指令，也不以条件布尔值表示现实成功概率。
