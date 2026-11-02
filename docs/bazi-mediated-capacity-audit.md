# 根气承载、暖局与用神的整章检验

生产旺衰本轮保持原算法。新的承载候选在314条旧记录中修正8条已知标注、没有新增退化，但完整〈性情〉35造没有新修正，未达到采用门槛。所有35造及新增错误均已纳入当前回归：25组349条记录、303个不同四柱，26个不同输入仍不符。记录数、重复输入和独立验证不是同一个数量。

## 冻结的机制

候选协议（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/protocol.json`）在计算前绑定候选、三个旧候选对照、10项数值依赖、全部314份旧回执和保守曝光登记。曝光登记含314个不同字面输入，其中也有工程变体，不能当作314位独立人物。

候选仅在原加权分支增加两个充分条件假设：

1. 沿用旧根量负荷候选：至少两处合格身根，至多一处透出官杀的健全重根，合格身根实际预算不小于所有克身根预算。
2. 增加印比承载候选：至少一处合格身根，有透比劫、有透印且该印确有存留的重根，至多一处透出有根官杀。

五行均按同一规则处理，不拟合系数、不合并身印、不删除己巳等根类。印实际有根仍不证明已经能受生、通关或解冻；这些是工程假设，不是原典给出的充分条件定理。

首次开发比较（本地数据：`validation/bazi-mediated-capacity-development-first-v1.json.gz`）逐项重现314份原生产完整对象。105条明确标注中，生产符合79条，新候选符合87条；旧容量v3、藏印v5分别符合89、90条。这些有重复和已暴露语境，不换算独立准确率。GH07不得判强仍通过；SJ05非身弱论也仍失败，没有把未新增退化写成全部约束通过。

## 完整新章的首次结果

开发门槛通过后，按方案读取1947年上海大东书局本[《任注滴天髓闡微》](https://commons.wikimedia.org/wiki/File:SSID-11335994_%E6%BB%B4%E5%A4%A9%E9%AB%93%E9%97%A1%E5%BE%AE.pdf)完整〈性情〉单元。整书SHA-256为`d6a7d1daf6513ce9fb9940ff8331b96804c10cdafbeac00d4d3d0a37229e1803`。保留PDF426–451原页（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/source-chapter.pdf`），边界的〈子象〉尾文和〈疾病〉标题后内容不计本章。

35份完整转录（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/reference.json`）、冻结时间与散列（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/reference-freeze.json`）先于任何新章计算。按日元／日主五行的直接旺衰、虚弱语境标注10条；其余25条保留未知。火烈、性情强拗、当令、从势、食神旺、刃旺或局中和没有自动转换成日主三档。人物经历不生成答案，未补造出生日期和司令日数。标注由同一开发者完成，独立原典专家仍待复核。

首次新章比较（本地数据：`validation/bazi-mediated-capacity-prospective-first-v1.json.gz`）保留全部35份生产及四个候选完整回执。35个字面输入与冻结曝光登记均无精确重合，但不是预训练盲测或现实样本。

| 范围 | 生产v6 | 根量v2 | 容量v3 | 藏印v5 | 新承载v1 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 10条明确强弱符合 | 9 | 9 | 8 | 8 | 9 |
| 新承载相对生产的新修正 | — | — | — | — | 0 |

新候选改变了两条未知记录，不能将其计成修正；相对各旧条件的新增互补收益门槛也未通过，候选继续不采用。旧候选的首败和本次首跑不覆盖、不因扩大样本而追认。

## 新反例指向的缺口

庚午、乙酉、庚午、壬午的和中堂例，原注论三午官星制酉刃，继称五行无土、弱可知；五个算法仍都判强。当前藏干表的午中有己，原文的无土却是有效生扶语境。两种观察都保留：不能删除藏己来贴标签，也不能因藏印预算为正就断言已经能生身。得令、印的工程支持与官星实际制刃力量，仍需统一裁定。

另两造丙寅、甲午、丙申、壬辰与丙申、甲午、丙寅、壬辰，年日支易位。原注分别论日坐申金生拱壬水，与申在年远隔且被比劫所夺；只加总根量或增加一个透印条件，不能表达位置与接引成效。源条件是进一步机制研究的输入，不据这两例拟合固定距离权重。

## 已公开的知识补充

`knowledge_read`的`bazi/classical_force_semantics`新增三键：

- `暖局与用神`：周侍郎例丙火解冻而用辰土；熊忠丞例丁火敌寒而用酉金。取暖局之火与取用神须核对完整原文，不推广成所有冬金必用土金。
- `日元强弱与性情措辞`：区分刃强与日主弱、火烈与强弱档、人格强拗与日主强；不得由行运和人物叙事倒填标签。
- `根位与有效接引`：保留日坐／远隔、合局改变功能以及物理藏印／有效生身的不同层次。

补充协议（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/knowledge-extension-protocol.json`）和逐项检查（本地数据：`../tests/fixtures/bazi_mediated_capacity_v1/knowledge-review.json`）证明该次补充后旧82条完整对象均保持，当时85条。该次原72条的42项修订、30项未改、40项出处待审和独立专家未完成状态不变。三条词义卡共用本章来源，不是三个新队列或新增预测成绩。

后续五行词条校勘及[旺衰用词当前修订](bazi-body-vocabulary-knowledge.md)另有冻结版本和验收记录。修订2追加来源区别时写错木四态的三处对应，修订3据原页与既存20项全表纠正，并保留修订2错误及工程验收历史。旧校勘和本章失败采用结果继续按各自的首次版本核对，不改判为算法采用通过；新摘要纠错不抵扣原26处分歧。

```bash
uv run --locked --extra dev fatebridge knowledge_read --domain bazi --category classical_force_semantics --key 暖局与用神 --response-char-limit 0
uv run --locked --extra dev python scripts/audit_bazi_mediated_capacity.py --output /tmp/bazi-mediated-development.json.gz
uv run --locked --extra dev python scripts/audit_bazi_mediated_prospective.py --output /tmp/bazi-mediated-prospective.json.gz
uv run --locked --extra dev python scripts/audit_bazi_source_corpus.py --output /tmp/bazi-source-current.json.gz
```

新章审计预期退出1，表示采用门槛未通过；已存在的输出拒绝覆盖。完整回归的直接脚本入口曾因无法导入仓库`scripts`命名空间而中断；原错误和执行器保留，现按仓库已有做法仅在直接启动时补入仓库根路径，不改评分或数值。

当前完整回归见v5首次回执（本地数据：`validation/bazi-source-corpus-first-v5.json.gz`）。历法全范围、原典有效力量与成格取用、自由文本独立外审仍未完成；现实预测没有新增前瞻结果，继续未验证。本轮工程检查、包内验证和保留失败另记于本地验收（本地数据：`validation/bazi-mediated-capacity-local-v1.json`）。
