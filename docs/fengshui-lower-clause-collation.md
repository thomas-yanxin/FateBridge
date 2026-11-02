# 沈氏下卦条文的同版图文校勘

[玄空计算](fengshui-xuankong.md) · [深度审计](fengshui-depth-audit.md) · 冻结转录（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/reference.json`）

本页保留216条正文与三图抽点的阶段范围；后续[完整216图5,832星数校勘](fengshui-lower-diagram-collation.md)已另立证据，发现一项图数差异，未清除本页三处正文冲突。

固定整理本卷四的全部24山、每山九运，共216条下卦种子及顺逆条文，程序吻合213条，保留3条差异。这三处同版图中的81个星数又全部与程序一致。当前证据支持“指定整理本存在这三处图文冲突”；不能只称网页转录错误，也不能据此认证整本或任意一种校订。

## 底本和范围

底本为[《沈氏玄空学》整理本PDF](https://www.vr-d.com/pdf-file/%E9%A3%8E%E6%B0%B4%2F%E6%B2%88%E6%B0%8F%E7%8E%84%E7%A9%BA%E5%AD%A6.pdf)，沈竹礽编，姚国华、柯誉整理，中央编译出版社，ISBN978-7-5117-0801-4。PDF5的CIP（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-005.png`）记2011.3／2016.2重印，PDF6版权页（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-006.png`）明确记2011年6月第1版、2016年2月第3次印刷，两项分别记录。此前冻结夹具对CIP月份的简写保留，不能以CIP月份代替版次月份。PDF9整理说明（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-009.png`）自述以1934年《增广沈氏玄空学》为底本，这个历史归属未独立认证。原文与署名按语分别保留，不把整理者与原作者混为一人。完整文件SHA-256为 `b0c2a7af0a1b94f36cf1cc9f0d2ce4b65e8ea49bd793bc128b8fdc525b5ba847`。

本次完整范围是PDF286–452的216条种子／顺逆前缀，不是216张图的全部5,832个星数、替卦、卷六日时选局、整本义理或真实住宅结果。PDF284起的24个章节标题与九运条文按文字顺序定位；同一页可同时出现前一山末尾条文和后一山标题，不能按整页最后标题归属。

## 三处冲突

| 宅盘 | 整理本正文 | 同版图的中宫→乾宫，山／向 | 旧影印正文 | 整理本页图 |
| --- | --- | --- | --- | --- |
| 四运卯山酉向 | 山向均逆 | 2／6→3／7，山向均顺 | 山向均顺 | PDF302（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-302.png`） |
| 一运酉山卯向 | 山逆向逆 | 3／8→2／9，山逆向顺 | 山逆向顺 | PDF307（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-307.png`） |
| 六运巽山乾向 | 山向均顺 | 5／7→6／6，山顺向逆 | 山顺向逆 | PDF324（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/modern-page-324.png`） |

三个图均按原图方位读取；PDF324页首文字属于前一张五运盘，中间图及下方文字属于六运盘。分别人工看图抄录九宫运、山、向全部81个星数，冻结图数参考（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/diagram-checks.json`）后才运行本轮引擎对照。中宫与乾宫用于显示顺逆差异，全部81数也逐一核对。助手看图未替代独立人工专家校勘。

此前旧影印三处校核（本地数据：`../tests/fixtures/fengshui_classical_v1/facsimile-checks.json`）仍保留；其确切出版底本未认证。完整216条整理本数字前缀与既有网页转录完全一致，故不能以旧影印吻合清除整理本的图文冲突，或改称整理本全文已通过。

## 提取、冻结和校核

[采集器](../scripts/collect_fengshui_lower_clauses.py)只用PyMuPDF读取原生PDF文字并渲染原页裁片，不导入FateBridge。先固定协议，再提取216个唯一山运组合；两条壬山丙向条文把山、向顺逆分开叙述，首次提取214条的失败记录保留，补足句式后仍未进行模型比对。完成的转录散列在首次本轮引擎对照前冻结为 `85a10d759544d5b7729e6ffbec6427a1a5ee443b353184d0daa49e34f3b5ac88`。

夹具保留全部216张前缀裁片、原页矩形、图像散列、文字、数字字段和独立的三张整页图。Apple Vision revision3以简繁中文、accurate且关闭语言纠错，辅助核对216张裁片；215条完整前缀与原生文字相同。一条把“八到向”误识成“儿到向”，看图仍为八，原始OCR（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/ocr-checks.json`）和人工看图记录（本地数据：`../tests/fixtures/fengshui_lower_clauses_v1/ocr-manual-review.json`）分别保留。OCR一致不是独立专家认证，也未用OCR置信度给原典打分。

使用单独的来源研究环境重建裁片，输出目录须为新目录；项目依赖不增加PyMuPDF或Apple Vision：

```bash
uv run --no-project --python 3.12 --with pymupdf==1.26.5 python \
  scripts/collect_fengshui_lower_clauses.py \
  --pdf /path/to/shen-modern.pdf \
  --protocol tests/fixtures/fengshui_lower_clauses_v1/protocol.json \
  --captures /tmp/shen-lower-crops-new \
  --output /tmp/shen-lower-reference.json
```

采集器文件散列也进入结果，后续仅格式变化会改变该项身份；应核对216条数据与图片，不覆盖历史冻结文件。当前采集器经Black格式化，与实际冻结时的采集器AST一致。

## 程序验收和算法决定

[校勘器](../src/fatebridge/validation/fengshui_lower_clauses.py)要求全部216个山运组合、相对山向、明确种子与顺逆，核对前缀文字与数字元数据一致；加载时固定转录身份并校验228个证据文件，删除不合项、重新散列被改写转录、缺失裁片或省略冲突图不能获得通过。比较过程不修改任何来源。

```bash
uv run --locked --extra dev pytest -q tests/test_fengshui_lower_clauses.py
uv run --locked --extra dev python scripts/audit_fengshui_sources.py \
  --output /tmp/fengshui-source-audit.json
```

来源命令应退出 **1**。`same_edition_lower_clauses.printed_prose_matched=213`、`unresolved_source_conflict_count=3`、`complete_printed_clause_acceptance_passed=false`。`diagram_spot_checks_passed=true`只表示三图81数吻合。原有 `unresolved_disagreement_count=0` 的范围现明确为旧网页与旧影印三处比较，不能解读为所有来源争议已解决。

本次不修改飞布、五黄、替星或历法数值，也不切换原典取得满分。保留原算法与来源冲突，后续须完成216张图的完整转录及独立复核，再逐项判定图、文、版本或实现应如何处理。所有全本、日时选局、自由模型解释、现实预测与权威认证标志继续为false；用户确认暂无真实前瞻案例，不能产生现实预测准确率。

本轮隔离源码回归2,254项通过、零失败和跳过，属于本地原生环境工程验证；Linux、安装包、部署、自由模型解释与现实案例未因此取得通过。原始日志、冻结散列、历史失败与范围见第二十三轮验收记录（本地数据：`validation/fengshui-primary-clauses-v23-evidence.json`）。

逐盘的这三处正文差异现随 `source_comparison` 返回，并与盘图比较分开。运行字段、同次释义及替卦未覆盖状态见[运行来源比较](fengshui-source-comparison.md)。完整216条和原始差异仍参与审计，未改成例外白名单。
