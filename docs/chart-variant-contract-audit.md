# 聚合星盘输出合同

`astro_chart` 支持 `chart`、`chart13`、`hellen_chart`、`guolao_chart`、`india_chart` 和 `germany`。聚合入口复用各专用入口的计算、领域类型及必要业务根，不维护另一套星历或 DTO。

## 完整结果与字段投影

输出模型工厂合并六个领域所有者的根字段，嵌套类型沿用 `CHART_FIELDS`。共享执行在领域返回后和附加回执后验证完整结果，并将原请求传入验证边界：

- 聚合入口按请求的 `chart_variant` 检查对应必要根，拒绝缺失、null或仅为空对象的必要业务事实。
- `chart_profile.chart_type` 必须与原请求盘型一致；专用入口必须与其固定盘型一致。
- 已声明业务字段继续接受领域类型校验；合法扩展字段保持开放。
- 完整验证先于字段投影。允许投影省略字段，不表示完整计算可以缺少必要事实；验证不重新序列化或改写业务值。

缺少原请求的独立 `validate_output` 调用只能检查报告盘型，不能证明请求身份。完整合同也不保证每个可选事实齐全，或已逐字段绑定同盘型的全部出生资料。

## 发现信息

工具发现中的 `full_result_required_fields_by_variant` 与输出 Schema 的 `x-fatebridge-full-result-required-for-chart-variants` 均由同一组专用所有者派生。该扩展说明完整执行的必要根，不是标准 JSON Schema 的 `required`，也不要求合法投影返回所有业务根。

## 维护与验证

盘型、必要根、数值类型、中性扩展及回执后请求绑定由 [合同测试](../tests/integration/test_chart_variant_contracts.py) 维护；三端投影与完整输出分别见 [投影测试](../tests/integration/test_output_projection_contracts.py) 和 [完整输出测试](../tests/integration/test_complete_output_contracts.py)。新增盘型时更新现有领域所有者和共同装配，按 [开发指南](development-guide.md) 重建调用合同并检查漂移。

这些检查验证交付合同。数值算法、传统来源、现实预测和部署状态按各专题分别验收；合同一致不能证明算法精度或SOTA。
