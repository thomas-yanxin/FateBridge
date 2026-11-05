# 沈氏固定零正与飞星条件分别读取

[玄空有限解读](xuankong-interpretation.md) · [历史宅盘](xuankong.md) · 原页与完整数表（本地数据：`../../../tests/data/fengshui_lingzheng_v1/reference.json`）

`shen_fixed_lingzheng_v1@1.0.0` 明确选用《增广沈氏玄空学》卷一“论阴阳零正”。[历史影印上册](https://vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4/%E6%B2%89%E6%B0%8F%E7%8E%84%E7%A9%BA_%E4%B8%8A.pdf)完整 SHA-256 为 `30d653cd53a768a957d2416d2c1586b65310f3aad3b103c90cf8af4347e4a490`，确切印记未认证。仓库保留PDF第40–42页的原始页图、指纹与转录，方便独立核对；不是整本校勘或现实效力认证。

原页可直接核对：印刷80–81页（本地数据：`../../../tests/data/fengshui_lingzheng_v1/shen-upper-40.png`）、82–83页（本地数据：`../../../tests/data/fengshui_lingzheng_v1/shen-upper-41.png`）、84–85页（本地数据：`../../../tests/data/fengshui_lingzheng_v1/shen-upper-42.png`）。

- 沈竹礽正文（SFL1，印刷81–82）：明确当元正神数、对待零神数，五运前十年寄坤、以八为零；后十年寄艮、以二为零。正文还明确否定把“山顺水逆”误当作山盘一律顺飞、水盘一律逆飞。
- 志伊署名按语（SFL2，印刷82–83）：引用温明远，说明飞星语境的旺星与实际山水，不能拿它替代固定地盘。
- 王则先署名按语（SFL3，印刷83–84）：固定零正随运而异，山向飞星还随向变化，二者分别检查；正神要求高山实地，零神要求河流低洼。

## 启用与五运分段

在 `interpretation` 中显式设置 `fixed_lingzheng`，评价运仍使用既有成对的 `current_period_number/period_evidence`，不读取历史宅运、年星或系统日期。

```json
{
  "current_period_number": 5,
  "period_evidence": "示意：独立确认评价五运，不能作为真实用户资料",
  "fixed_lingzheng": {
    "five_period_half": "first_decade",
    "half_evidence": "示意：已确认评价运前十年"
  }
}
```

非五运时省略分段。五运分段未知时省略两个分段字段，程序同时保留前后十年的候选，`selection_status=requires_five_period_half`；不能选择更有利的一项。已确认分段时，前半正神五寄西南、零八在东北，后半正神五寄东北、零二在西南。五的原宫仍记中宫，寄宫仅用于此固定地盘分支，不改宅盘、五黄五行或替星起飞依据。

## 实际形势的三值事实

`fixed_lingzheng.observations` 按已确认全宅中心的磁北八宫提供 `direction`、`observation_basis`、非空 `evidence` 及至少一项明确事实：

- `high_solid_terrain_present`：高山实地存在。
- `low_lying_terrain_present`：低洼地形存在。
- `river_water_present`：原按语所指外部河流存在。一般有水、室内水杯、水景或摆件不能直接替代这项事实。

各事实取真、假或未知，未知不当作不存在。无山不推出低洼，河流存在也不自动确认低洼。正神只检查高实条件；零神同时检查低洼与河流。宫内可有不同位置的高低形势，因此不强制高实与低洼互斥；要判断其具体配合仍须更细现场资料。本分支不把另一分支的一般水形判断扩充成河流事实。已有飞星外局明确无水时，不能又在同宫确认河流存在。

照片只返回候选，`condition_match=null`；五运分段未知时两组亦保持候选。确认不存在可以否定对应存在条件，不能由此宣称全宅不利。

## 输出与飞星比较

读取 `layers.xuankong_natal.interpretation.fixed_lingzheng_analysis`。它包含固定方位、候选、每宫形势、独立的 `flying_star_comparisons`、缺失资料及逐项 `rule_trace`；顶层 `rulesets` 保留上述三组署名来源。

比较只读取同一候选的实际山星、向星，按明确评价运识别当前星，不把历史宅运当作当前运。固定正神与当令山星的形势要求同类，固定零神与当令向星的要求同类；另一角色分别列入 `different_current_star_roles`。同宫双当令时可同时列出同类和不同类要求，不能相互抵消。

这些只是形势要求的同类比较，不表示两套规则的条件完全相等。不能单凭它认定实际山水冲突、整体可用或现实应验。既有山向存在条件、床门用途、王氏时令表及此固定地盘分别返回，不自动合成分数、吉凶或执行许可。完整输出超过预算时读取同一运行的 `result_delivery`。

## 核对范围

十组完整数字对照覆盖八个非五运及五运两个分段，期望来自本轮助手对原页的视觉转录，独立于生产公式，尚无独立人类专家复核。原页、转录和散列同时保留。测试另覆盖三值条件、照片、分段未知、跨分支事实冲突、原有432盘不变及三个接口一致性；这些不提供现实预测准确率。
