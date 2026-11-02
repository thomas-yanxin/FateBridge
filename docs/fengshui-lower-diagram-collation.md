# 沈氏216张下卦盘的完整星数校勘

[条文校勘](fengshui-lower-clause-collation.md) · [玄空计算](fengshui-xuankong.md) · 冻结星数（本地数据：`../tests/fixtures/fengshui_lower_diagrams_v1/reference.json`）

同一整理本全部216张下卦盘、九宫运山向共5,832个星数已独立于本轮引擎输出完成转录。引擎吻合5,831数、215张完整盘；七运申山寅向的东宫山星，原图印五，引擎为二。保留这个差异，完整数字验收为false。此前三处正文顺逆与同版盘图的冲突也继续保留，完整盘图核验不能替它们授予正文通过。

## 底本与原图差异

底本仍为[《沈氏玄空学》整理本](https://www.vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4%2F%E6%B2%88%E6%B0%8F%E7%8E%84%E7%A9%BA%E5%AD%A6.pdf)，沈竹礽编、姚国华及柯誉整理，中央编译出版社2011年6月第1版、2016年2月第3次印刷，ISBN978-7-5117-0801-4。CIP月份与版权页版次分别登记，见[书目页](fengshui-lower-clause-collation.md#底本和范围)。完整PDF的SHA-256为 `b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847`。

| 核对位置 | 可直接读取的原图 | 程序及图内问题 |
| --- | --- | --- |
| 七运申山寅向，东宫山星 | 整理本PDF353整页（本地数据：`../tests/fixtures/fengshui_lower_diagrams_v1/modern-page-353.png`）及原始盘图（本地数据：`../tests/fixtures/fengshui_lower_diagrams_v1/native-images/申-寅-7.png`）均为五 | 引擎为二；原图山星重复五、缺二 |
| 同局旧影印 | PDF57／印刷37页左中（本地数据：`../tests/fixtures/fengshui_lower_diagrams_v1/historical-page-57.png`）也为五 | 旧图未消除新图差异，不改称只由现代整理者引入 |

旧影印来自[下册扫描](https://vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4/%E6%B2%89%E6%B0%8F%E7%8E%84%E7%A9%BA_%E4%B8%8B.pdf)，完整PDF散列为 `539308519005e1b7e95939c9cfee0da7582aae729b3488bb61c434cbbff7bff0`；确切出版印记未认证。旧图这一处是在完整星数首次比较后选看，作为后续原图核查，未增加盲测样本或独立专家计数。

该局正文记山四入中顺飞。按中、乾、兑、艮、离、坎、坤、震、巽的九宫顺序，四、五、六、七、八、九、一、二、三各出现一次；东宫即震宫为二。程序结果符合这个飞布数式，但无法同时满足原图东宫的五。当前保留数式与原图的冲突，不改原图、不改算法追随重复数，也没有通过切换底本清除失败。

## 完整转录过程

协议在数字采集前固定全体216盘及5,832数，没有预设可忽略盘例。依据原PDF图片与其随后条文的阅读顺序关联，保留页码、图片xref、矩形和216个唯一原图散列；四条横线与四条竖线均由原图像素找到，再按上南下北、左东右西读取九宫。每宫左上为山、右上为向、下方为运，所有字都有唯一编号与来源记录。

原尺寸及最近邻三倍放大分别使用Apple Vision revision3，简繁中文、accurate、关闭语言纠错，记录原始候选、置信度和位置。两次识别属于同一OCR系统的不同输入尺寸，不算两位独立专家。按[Apple对文字边界的说明](https://developer.apple.com/documentation/vision/vnrecognizedtext/boundingbox%28for%3A%29)，accurate模式的范围框不能假定具有单字精度；本次先用九宫几何裁宫，不用词框猜出整盘各字的位置。

另以原始笔画像素对“一、二、三”给保守候选，不使用飞布、缺数补齐、网页数值或生产模块。来源候选合并后，159字未识别、19字冲突，共178字逐项查看原宫裁片登记；其余5,654个候选按字形分组看图，18张候选图表与三张待核图表的原始像素和编号可在本轮研究记录复查。所有星数都在首次本轮引擎比对前冻结，参考SHA-256为 `44488715143b6e6aebcfe8ae638397ced12ed07dfee392cce81440a43c8de483`。助手辅助转录及看图不等于独立人工专家校勘。

只做来源内部检查即发现重复五、缺二；随后全量引擎比对保留同一数字差异。没有因程序给二而把来源五改成二。夹具含全部原始盘图、协议、每字出处、看图记录与完整身份清单；原始OCR、裁片和采集程序保留在仓库外固定研究目录。

## 验收与防止指标取巧

[完整图数校勘器](../src/fatebridge/validation/fengshui_lower_diagrams.py)验证全部216个山运组合、九宫三类星数和5,832个唯一来源编号，要求完整228项文件身份。删除不合盘、改五为二后重新散列、漏宫或空值均拒绝加载或验收；不设来源例外名单。

```bash
uv run --locked --extra dev pytest -q tests/test_fengshui_lower_diagrams.py
uv run --locked --extra dev python scripts/audit_fengshui_sources.py \
  --output /tmp/fengshui-complete-source-audit.json
```

来源命令应退出 **1**。`complete_lower_diagrams` 返回 `printed_charts_checked=216`、`printed_numerals_checked=5832`、`printed_numerals_matched=5831`；完整验收为false。原来 `same_edition_lower_clauses` 的三图81数是上一阶段抽点范围，不因本次扩展而覆写旧记录。

验收同时显示来源和引擎各星盘是否各含一至九。反例测试把程序东宫故意改成五后，字面吻合可达5,832数，但程序自身出现重复／缺数，完整验收仍为false。字面一致、数学一致和整本传统语义分别负责各自证据，不能互相抵消。当前未修改计算公式、公共Schema或原文来追求通过。

此轮只补全下卦盘图的数字来源证据。替卦全本、完整断事、日时选局、独立人工专家校勘、自由模型解释和现实预测仍未获得完整验收；没有真实前瞻结果，不产生现实准确率或权威认证。

本轮本地原生环境的55个风水／玄空测试文件共2,271项通过，零失败、零跳过；2,655个冻结文件运行后身份不变。记录、旧失败和验证范围见第二十四轮证据（本地数据：`validation/fengshui-full-diagrams-v24-evidence.json`）。

这些固定盘图现同时用于[运行来源比较](fengshui-source-comparison.md)。七运申寅东宫的原图五与计算二可在实际工具结果、快照及固定释义中一起读取；不改字、不替换计算值，也不以局部相合认证全本。
