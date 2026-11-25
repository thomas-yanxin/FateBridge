# IPIP-50 五因子计分

本域发布 `ipip_big_five`，REST 为 `POST /api/psychometrics/ipip-big-five`，MCP 为同名逐工具调用，CLI 为 `fatebridge ipip_big_five`。`action=list_items` 提供题序、英文题文、中文词义释义与计分键；`action=score` 接受 `responses`（字符串题号到整数）或 `ratings`（按第1题起的顺序列表），两者互斥。值为1–5整数，省略或 null 为缺题；至少一题有效作答。CLI 的 `--ratings` 只接受连续整数；含 null 的列表须经 `--subject-file` 传入 JSON，或用 `--responses` 的明确题号表示缺题，不可删除中间题后压缩题序。`domain` 仅供列题筛选。计分默认仅输出五个维度，`include_item_breakdown=true` 可附逐题核验事实。

## 来源与范围

英文题文、题序及正反向键采用 IPIP 官方 [50题示例问卷](https://ipip.ori.org/new_ipip-50-item-scale.htm)，该页说明五因子量表用于测量 Goldberg, L. R. (1992), *The development of markers for the Big-Five factor structure*, Psychological Assessment, 4, 26–42 所报告的标记。1992 是标记论文年份，不能据此宣称当前中文问卷在1992年已验证。IPIP 页允许公有领域条目的使用、改写与翻译。

五维依次为 Extraversion（外向性）、Agreeableness（宜人性）、Conscientiousness（尽责性）、Emotional Stability（情绪稳定性）、Intellect/Imagination（智识/想象力）。最后一维保留原名，不把它等同智商或完整的开放性量表。`gloss_zh` 为 FateBridge 根据同一英文题文编写的中文词义释义，未采用有独立验证证据的正式中文版；例如 feel blue 表示低落，exacting 表示严格要求，take time out for others 表示为他人腾出时间。中文释义、信度、测量等值和适用人群常模尚未独立验证。

## 计分与缺题

[IPIP计分说明](https://ipip.ori.org/newScoringInstructions.htm)规定正向题按1、2、3、4、5计分，反向题按5、4、3、2、1计分，即 `6 - raw_score`，对各量表所属题相加。这里每个因子独立含10题，26道正向、24道反向；不会把五种不同因子的题和或均值解释为人格总分，因此没有 `scale_raw_sum` / `scale_mean`。

IPIP所引两页未规定缺题阈值。当前 `contract_v1` 的8/10是 FateBridge 发布策略，不是 IPIP 授权的缺题标准或经验证的插补方法：

| 因子有效题数 | 状态 | 原始和 | 均值与折算和 |
| --- | --- | --- | --- |
| 10 | complete | 已答题反向后之和 S | mean=S/10；prorated_sum=S |
| 8或9 | prorated | 已答题反向后之和 S | mean=S/n；prorated_sum=10S/n |
| 0至7 | insufficient_items | 仍保留已答题的 S | 两者均为 null |

均值和折算和各自从未舍入的 S/n 计算后保留4位小数。折算只是把已答题均值放回10题尺度，隐含缺答题可由已答均值代表的假设；缺题与被测特质有关时会偏差。缺题题号和数量始终保留。整体状态为50题齐全时 complete；所有维度均不足8题时 insufficient_items；其余 partial。不足某维度不阻塞其他可算维度。

## 验收资格

专项测试从官方具名题序键独立列出50项预期，对每题1–5的250种响应逐一验正反向，再按五维各7/8/9/10题与独立有理数算术核边界。真实 REST POST、FastMCP 逐工具、CLI 在固定 as_of 下分别运行列题、完整计分、缺题、非法输入及严格字段投影。`tests/psychometrics/test_ipip_big_five.py` 已纳入现有CI选择。

算术与协议互校只证明实现按所声明规则计算。此发布未加入人群常模、百分位、临床分界或诊断效度数据；不能从测试通过推得这些资格。元数据的来源、中文释义和项目缺题策略随结果返回，允许调用方准确说明证据范围。
