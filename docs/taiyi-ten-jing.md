# 太乙十精：天时十二支规则与原例差异

日计及十精数值规则版本`1.1.0`采用寅起顺行十二支计算“天时”，不在十二支中插入巽等四维。原先该项未计算；现在可以返回规则值，原例的不同读数继续单列为差异。日计钟面、甲子锚点、主客算、定计、八门均不因此改变。

依据分别来自：

- [《太乙金镜式经》卷七](https://zh.wikisource.org/w/index.php?title=太乙金鏡式經_(四庫全書本)/卷07&oldid=773942)天时条，明列小周十二、吕申起、顺行十二辰。
- [《太乙统宗宝鉴》卷二十](https://www.shidianguji.com/zh/book/CADAL02094393/chapter/1lcppxguguiai)天时条，同列十二辰规则。
- [《太乙金钥匙续集》图33](https://upload.wikimedia.org/wikipedia/commons/1/19/NLC892-411999021066-66022_%E5%A4%AA%E4%B9%99%E9%87%91%E9%91%B0%E5%8C%99.pdf#page=33)辛酉年度例，明确余十，从寅顺行至戌为九，终点在亥。这与十二支顺序相符。

《金钥匙》日例却在余八的算路中写入巽，终点在大武坤，课式也作七宫坤。按十二支通则，第八位是酉。这里采纳有年度算例支持的通则，并列原读数；没有改写扫描图，也没有裁定原文必为抄错。

| 项目 | 原书读数 | 本次规则结果 | 处理 |
| --- | --- | --- | --- |
| 年例天时，余10 | 亥 | 亥 | 通则的算例补证 |
| 日例天时，余8 | 坤 | 酉 | 明确不符，继续保留 |
| 年例天尊，余2 | 子起顺行，卯 | 日例逆行规则得酉 | 年日方向差异保留，不宣称四计全同 |
| 年例三风，余4 | 只载除三七二，未写终宫 | 日例规则得酉 | 来源未写出，不把推算值补入原文 |
| 日例太乙数 | 正文四宫，课式第44局 | 局序44；宫位未知 | 不把局序当宫位 |

太乙数的五元七十二局定义、年度例22及日课式44支持局序含义，但还不能解释日正文的“四宫”。它继续返回`palace=null`，不放入宫位标记，阴遁也不会把局序44当作可对冲的方位。

V9冻结材料（本地数据：`../tests/fixtures/taiyi_jinjing_v9/manifest.json`）包括年度段的全部十组余数与终位，以及五行两年续例，共22观察；缺终位与方向差异都在要求中。该数值参照直接使用原书积数10155478，不把当前公开年度模式改成金钥匙十精。当前公开年度模式的金镜十神、日计十精仍有各自范围。

V9年度22观察为21可评、20相符、1差异、1未决。既有丁未日34观察的材料和预期值未变；天时从未知转为明确不符，因此成为33可评、28相符、5差异、1未决。两组数字不合并为系统准确率，原典验收继续失败。报告（本地数据：`validation/taiyi-jinjing-v9/report.json`）保留全部差异与未知。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1562 --analysis-month 1 --analysis-day 6 --analysis-hour 12 \
  --analysis-timezone '+08:00' --no-use-true-solar-time --calculation-mode day \
  --strict-fields --fields taiyi.ten_jing.records.heaven_time taiyi.ten_jing.records.taiyi_ordinal
uv run --locked --extra dev python scripts/audit_taiyi_ten_jing.py \
  --output /tmp/taiyi-ten-jing-report.json
```

审计脚本退出1。`daily_essences`首读包含天时的`rule_evidence`和`source_comparisons`；同盘快照明确区分“天时酉”与“原例坤”，返回取法依据和来源。日例日期转换仍沿用[V8的独立历表验收](taiyi-historical-dates.md)，不借规则变更改动日期。此次没有实现天气断语、完整古历或完整四计十精，也没有认证现实预测效力。
