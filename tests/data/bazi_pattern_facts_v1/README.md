# 八字藏干、拱候选与特殊日参考 v1

`reference.json.gz`是冻结的独立输出，SHA256对解压后的原始JSON计算。
普通CI只读取该文件，不安装或运行第三方包，也不以FateBridge生成期望值。

- 藏干有序表和五合对象来自既有固定[lunar-python 1645ad3版本](https://github.com/6tail/lunar-python/tree/1645ad3b3653635e5cb31b0c6df22b5e4298f8ce)，原文件身份见相邻的`bazi_discrete_relations_v1.json`。生成全部144个有序支对，包含不同柱位同支的情况。
- 拱候选实际运行[china-testing/bazi 33b1835版本](https://github.com/china-testing/bazi/tree/33b18354d5407727640e545c3aaec0efb4bf5282)的`common.py::check_gong`及原`get_zhi_detail`；表取原`ganzhi.py`，使用bidict0.23.1。没有替换函数体或格式化依赖。对20,736组四支赋值的六个位置对分别传入三合／三会表，共248,832次原函数调用、11,616条命中。此调用范围比其CLI默认位置选择广，不能称为对该CLI所有行为的复现。
- `source-rules.json`是同一开发者对《三命通会》与既有《秘本子平真诠》原页的具名整理。十组拱禄／拱贵读取[四库影印扫描304–305页](https://zh.wikisource.org/wiki/Page:文淵閣四庫全書_0810冊.djvu/304)。数字转录的“巳未”与原页“己未”差异保留；并未把电子本当作逐字校勘通过。
- 日贵、魁罡和四生／四正／四墓等名单另固定[卷六oldid657375](https://zh.wikisource.org/w/index.php?oldid=657375)。[卷三天乙贵人](https://zh.wikisource.org/w/index.php?oldid=657369)中的阴阳、昼夜异说继续保留，不以6—18时证明实际日出入或唯一古法。
- 日贵钟时检查直接验证声明的6—18时约定，覆盖60个日柱与未知时刻及全部24小时，共1,500个输入。该约定不作为独立昼夜证据。

原始第三方文件、实际执行生成器、编译的函数片段身份、原网页与书影、旧输出和失败在外部审查档案`fatebridge-bazi-hidden-special-20261111`保存。上述独立实现不是全流派权威认证；原文整理不是独立专家裁定。输入中有大量符号赋值，不是实际出生盘。缺中神、名单相符或填实可排除均不能证明完整成格、力量或预测效力。
