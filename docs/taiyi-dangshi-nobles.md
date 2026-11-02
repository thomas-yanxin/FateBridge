# 三式当时法：两版贵人表与实际起贵本位

《太乙金镜式经》卷一明确提出以日度加时、因步六壬，读取太乙及主客将所在十二神。但同一篇的贵人表在四库本与明钞本并不相同。当前三式可以显式选择已有六壬贵人配置，并从同次实际算路对照两版原文，不自动选取更有利或更相符的一版。

## 两种原文都保留

[四库本原扫描](https://commons.wikimedia.org/wiki/File:CADAL06056494_太乙金鏡式經·卷一~卷四.djvu)第53图给出单干及“反是”关系；[NCL明钞本](https://commons.wikimedia.org/wiki/File:NCL-06604_太乙金鏡式經.pdf)第23页按干组明列。原生书影和二十项逐版期待在新数值审计与生产修改前冻结（本地数据：`../tests/fixtures/taiyi_dangshi_noble_v40/freeze.json`），整理者为Codex，已知现有表值，非盲读，独立人类校审为0。

| 日干 | 四库朝／暮本位 | 明钞朝／暮本位 |
| --- | --- | --- |
| 甲 | 未／丑 | 丑／未 |
| 乙 | 申／子 | 子／申 |
| 丙 | 酉／亥 | 亥／酉 |
| 丁 | 亥／酉 | 亥／酉 |
| 戊 | 丑／未 | 丑／未 |
| 己 | 子／申 | 子／申 |
| 庚 | 丑／未 | 丑／未 |
| 辛 | 寅／午 | 午／寅 |
| 壬 | 卯／巳 | 巳／卯 |
| 癸 | 巳／卯 | 巳／卯 |

甲、乙、丙、辛、壬共十项朝暮读数不同。当前`liuren_common_v1`二十项均与这份明钞表相符；`tanyuan_xieji_v1`二十项均与这份四库表相符。交叉比较各为10／20；全部八十次条件比较保留，不合并为准确率。它们是同一小表的重复对照，不是八十个独立古例。

这只证明贵人本位表的对应，不证明两部书整套六壬规则同源，也不证明哪一版应当覆盖另一版。现有两配置仍保留各自规则名称、作者和来源，未把《探原》冒署为唐本。三式默认仍使用通行表；调用者事先明确指定另一个配置才会切换整份实际六壬神将盘。

## 同次事实怎样交付

`synthesis.noble_source_assessment`读取本次`liureng.rule_trace`中唯一的`liuren.guiren_start`，返回实际配置、实际日干、所选昼夜、实际起贵本位、原字段路径及两版对应读数。比较起点是天盘神的本位，不是旋转后贵人的地盘落支；不会因碰巧地盘落在某支就判为原表相符。

缺少唯一算路、无效起支或配置／昼夜回执不一致时保持未评估，不改盘或补算以迎合某版。更改返回的对照对象不会污染后续调用的来源缓存。结构化证据、快照及导出使用同一份对照，新增导出栏目为“三式贵人来源对照”。

朝／暮在这里明确按本次六壬已选择的昼／夜作条件对照。现有卯至申为昼、酉至寅为夜或调用者显式选择，仍由`liureng.meta.diurnal_evidence`交付；未据此认证唐代朝暮判界、星出星没或古历加时。太乙为年／月／日计时，仍可核对当前时刻的六壬表，但标为跨时间层表值对照，不称为当时法验收。

## 调用

```bash
uv run --locked --extra dev fatebridge sanshiunited \
  --date 2026-10-25 --time 12:00:00 --zone '+08:00' \
  --no-use-true-solar-time --taiyi-options '{"calculation_mode":"hour"}' \
  --liureng-guiren-profile tanyuan_xieji_v1 \
  --strict-fields --no-include-snapshot-text \
  --fields synthesis.noble_source_assessment liureng.meta synthesis.time_scopes
```

REST及MCP的同名参数为`liureng_guiren_profile`，值只有`liuren_common_v1`、`tanyuan_xieji_v1`。来源目录ID不是请求配置。三式已发布`noble_sources`选读视图；复制其中`fields`即可，视图名不是请求参数。首轮`scoped_evidence`也交付这份对照。

完整JSON仍读取同一run的`result_delivery`。修改配置属于新输入，必须重算受影响的六壬神将与合参事实；只解释已返回的对照无需重算。不得为了得到喜欢的结果往返换表。

## 未完成的更大条件

四库第56—57图及明钞第24页的十月庚申例仍保留：贵人朝治大吉两本相同，客参将所乘神四库作“天定”、明钞作“天空”。没有据另一本默改原字，原例缺公元年，亦未补造确切时刻。V41追加[完整条件核对和同方位两支并列](taiyi-dangshi-sectors.md)，使用同一生产布将函数；朝条件下明钞五项候选相容，其中仅两项单支直接相符，不能替代四维寄支裁定。四维、中宫未评估及完整联合断法缺口继续保留。

```bash
uv run --locked --extra dev python scripts/build_taiyi_dangshi_nobles.py --check
uv run --locked --extra dev python scripts/audit_taiyi_dangshi_nobles.py \
  --output /tmp/taiyi-dangshi-nobles-v40.json
```

生成检查验证运行目录与冻结资料相同；来源审计保留全部分歧后返回1。新对照没有改变太乙、奇门数值或默认六壬选表，没有解决V38／V39古历置闰和梁例日期冲突，没有新增模型评测、完整有日期合参古例或现实预测证据。V40验证记录（本地数据：`validation/taiyi-jinjing-v40/README.md`）保留首次集成错误、修复、协议检查及全部旧目标。
