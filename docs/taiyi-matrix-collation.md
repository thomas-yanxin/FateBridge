# 太乙钤表的明钞本校勘

V21增加《太乙金镜式经》明钞本的整表物理栏初录，用于继续核查[四库本胜败钤](taiyi-victory-matrix.md)的六处天目几何差异、四个空栏及一处缺字。初录覆盖十六神的前后两半，共32栏；逐宫对应仍未裁定，不能称为128格已经校定。

## 独立版本与原栏

[国家图书馆藏明钞本306.6 06604的扫描](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf)共124个PDF图像页。原PDF的SHA-256为`54be545fb26f42af1be700cc93bcf0a86d7797f8709f1385db61f9a05c136fee`；本批来源记录（本地数据：`../tests/fixtures/taiyi_jinjing_v21/source-metadata.json`）保留其字节数、SHA-1、下载页版本及渲染方法。页数是PDF一基页号，不是原书叶码。

实施前初录清单（本地数据：`../tests/fixtures/taiyi_jinjing_v21/manifest.json`）绑定六页未增强书影、卷二同版十六神名位及卷三32物理栏字组（本地数据：`../tests/fixtures/taiyi_jinjing_v21/physical-columns.json`）。卷二用PDF34—36页，钤表用52—54页；栏位按每半页从右数定位，小字另记字组序、右左分股。字组边界只帮助找字，没有据此划定条件、结果或宫数。

本地书影：卷二34（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page34.png`）、35（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page35.png`）、36（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page36.png`）；卷三52（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page52.png`）、53（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page53.png`）、54（本地数据：`../tests/fixtures/taiyi_jinjing_v21/ncl-page54.png`）。

这些是代理逐图校读，没有经过独立人类专家覆核，校读者也已见过四库资料和当前代码。初录字段误用了human一词；署名订正（本地数据：`../tests/fixtures/taiyi_jinjing_v21/metadata-correction.json`）及订正清单（本地数据：`../tests/fixtures/taiyi_jinjing_v21/correction-manifest.json`）追加澄清，初录、字组及指纹均未覆盖。独立性指扫描底本独立于生产计算，不表示盲读或专家认证。

卷二的神名条文用来核对同版表头位置；巽神名暂读“大昊”，酉神名蔟/簇字形保留待校。索引中的名称不是逐字校定结论，也没有据此改写四库本的大炅、太蔟或公共神名。

## 本次查到了什么

审计索引四库原栏中33条可单独读取的天目几何文字。六条既有差异所用词句，都可在明钞本同神、同四宫半表的物理栏找到：

| 四库待核格 | 词句 | 明钞PDF页、半页及从右数栏 |
| --- | --- | --- |
| 酉三 | 天目格 | 52右9 |
| 子四 | 天目内迫 | 52左4 |
| 丑七 | 天目外迫 | 53左4 |
| 巳二 | 天目外迫 | 53右2 |
| 午八 | 天目内迫 | 54右2 |
| 坤六 | 天目囚 | 54右4 |

同神半表仍含四个宫数；词句在同栏出现不足以证明对应同宫。明钞本有些条件、胜败语及并行小字连写，例如酉前半栏的“天目格主大胜”。没有把它强拆成四库既定格子，也没有用几何算得的结果选择最合的分栏。

明钞本吕申后半栏末尾另见“先胜后负”，可作为继续核对四库空栏的线索；目前不把它指定为某宫结果。四库原128格、四个空栏、一处缺字及六处几何差异全部保持。此批新增逐宫校定数、几何相符数和有日期古例数均为0。

## 审计与下一步

```sh
uv run --locked --extra dev python scripts/audit_taiyi_matrix_collation.py \
  --output /tmp/taiyi-matrix-collation.json
uv run --locked --extra dev pytest tests/test_taiyi_matrix_collation.py
```

审计不导入生产太乙算法。报告保留原图定位、两版初录指纹、并行重复词句、六处争议和全部空缺；因128格逐宫对应仍未裁定，退出码继续为1。字串检索命中不是计算符合率，也不提供当前盘胜败。

后续须先根据表头、字组、栏序和其他版本裁定逐宫对应，再核完整条件、将星客主及适用计法；取得独立规则证据后才调整计算。此批不改变生产数值、公开输出合同或原有格局判断。完整历法、原典与解释忠实要求仍见总清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`），本批记录见V21验收材料（本地数据：`validation/taiyi-jinjing-v21/README.md`）。
