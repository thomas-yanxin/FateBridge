# 调候提要、正文与命盘事实

旧调候函数只有日干、月支两个输入，却返回`primary`和`secondary`；人类可读摘要又把它们写成“主用”“辅用”。这会让日干月支简表看起来像经过全盘判断的用神结论。本次保留原120格候选值供兼容，将其明确标为简表，并新增出处层次及相关干的实际位置。

## 所选版本与核对范围

本次核对[国家图书馆藏本《窮通寶鑑評註》](https://upload.wikimedia.org/wikipedia/commons/9/93/NLC416-12jh004238-48608_%E7%AA%AE%E9%80%9A%E5%AF%B6%E9%91%91%E8%A9%95%E8%A8%BB.pdf)，编号NLC416-12jh004238-48608，乾乾书社出版，277个PDF页面。封面题东海乐吾氏评注，卷首题余春台原编、乐吾氏评注；大字原编、小字评注及喜用提要分别记录。原文件SHA-256为`b7f17fc7fcb7d8faa991efa74d0db391c5066a3793b3fc6787d2612bc6b350a8`。

范围是全部十二个甲木月支的提要和选定正文段落，不是全书校勘。比较前保存旧运行值与方法范围；因已观察到甲木申酉月疑点，这是一项公开的开发审计，不是盲测。所选段落的转写仍待独立专家复核，其余108格尚未对应本印本逐条校勘。

## 不能压成一个排名的内容

| 月支 | 提要首列 | 正文的条件或次序 | 当前处理 |
| --- | --- | --- | --- |
| 申 | 庚 | PDF32以丁为尊、庚次且不可少 | 两层并列，不自动覆盖其一 |
| 酉 | 庚 | PDF33丁先、丙次、庚再次，分制金与调候 | 两层并列，保留各自作用 |
| 未 | 癸 | 提要分上半月、下半月；PDF24—26另有六月丁庚专段 | 半月界及分支保留未裁定 |
| 戌 | 庚 | 提要分土旺用甲、木旺用庚；PDF35—37另论丁与壬癸 | 不由当前加权强弱自动选择原典分支 |
| 丑 | 丁 | PDF43先庚引丁，PDF44又说丁不可缺 | 操作次序与不可缺项分别说明 |

其余月份同样保留提要、正文页码与条件。提要列出的多个干不是同时为喜，也不能把正文某句抽成所有命盘的统一顺序。这些差异没有被改造成十二个完整调候成功案例。

## 输出与使用

综合入口的`bazi_birth.classical.seasonal_climate`及九专题的`<topic>_analysis.evidence_chain.seasonal_reference`使用同一领域函数。十个入口均发布`seasonal_reference`证据视图；把视图中的`fields`传入调用，不把视图名当请求参数。

- `primary`、`secondary`：保持原有120格候选值；`lookup_scope`明确说明属于旧简表。
- `chart_adjudication_status=not_performed`：未执行全盘最终取用判断。
- `source_layers`：已核对的甲木提要、正文、页码、条件及差异；其他日干不补造这一字段。
- `stem_observations`：从本次四柱逐一列出相关干的天干位置与支藏位置，保留藏干序号；不存在的字返回空列表。有字不等于得用，不隐含根气有效、合化或全局力量成立。

```bash
# 虚构资料，用同次计算核对简表与出处差异。
fatebridge bazi_birth --birth-year 1990 --birth-month 9 --birth-day 16 \
  --birth-hour 12 --gender male --use-true-solar-time false \
  --fields bazi_birth.classical.seasonal_climate --strict-fields true \
  --include-snapshot-text false --response-char-limit 0
```

人类可读摘要改称“调候简表候选”，并显示已核对正文的条件；不再把首列直接称为全盘“主用”。本项也不改变健康专题的五行寒暖工程分组，两个算法的输入、出处和范围不同。

冻结资料见审计说明（本地数据：`../tests/fixtures/bazi_seasonal_jia_v1/README.md`）。完整调候算法、其他108格对应校勘、半月界、格局互参及真实模型能否忠实解释这些层次仍是未完成项，见三项目标要求（本地数据：`validation/bazi-three-axis-requirements.json`）。
