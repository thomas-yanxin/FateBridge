# 太乙逐主体对宫与格／对源名

`taiyi.opposition_assessment`逐项核对文昌、始击、主大、主参、客大、客参是否与本盘太乙正对。计算使用同盘实际十六神方位，正对相隔八步；宫数的大小或差值不参与判断。中五返回`is_opposite=null`、`status=no_ring_bearing`，不寄到某一方位。`false`只否定所核对宫几何，不表示原典全部格对法不存在。

此前程序的关系列表只返回文昌的对及始击、客方两将的格，主方对宫没有专门结果。例如阳十三局太乙酉六、主参卯四，原注明列“格太乙”。本次把六个主体的对宫事实分别返回，主方摘要也进入`pattern_summary.main_oppositions`。原`patterns`的既有索引保持；它仍是已实现规则列表，不能据其中缺少主将格而否定主方对宫事实。主方源名的称名范围另列在本组件中。

## 原典范围

[《太乙金镜式经》卷三格、对条](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷03)的“客目大小将”文字范围与主方局注需要分别核验。[《古今图书集成》艺术典693](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第693卷)、[694](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第694卷)、[695](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第695卷)、[696卷](https://zh.wikisource.org/wiki/欽定古今圖書集成/博物彙編/藝術典/第696卷)的完整阳72局注中，所选主大／主参向太乙格或对的12条注记使用格10次、对2次。实施前人工冻结24个原文宫数、12个源名以及阳53的一条附带外迫；这不是12个完整命盘或12次历史应验。来源与范围见冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v14/manifest.json`）、原注数据（本地数据：`../tests/fixtures/taiyi_jinjing_v14/opposition-notes.json`）和裁定范围（本地数据：`../tests/fixtures/taiyi_jinjing_v14/adjudication.json`）。V1至V13原有失败字段及分母保持。

阳十三、十六等主参对宫写格，阳二十一、三十四主大对宫写对。程序先返回可核对的方位事实；主方`classical_names=["格","对"]`是已见的候选词，`name_status=variant_names_not_unified`表示没有把两种用字宣称为同一部原典的统一名称，也不代表同时成立两个独立格局。所选阳局同相位时，`source_comparison.source_name`仍逐字保留该条原名。阴局或缺少明确阴阳标志的外部旧核心，不借阳局条目制造源注相符结果。`core_board.yin_dun`现在明确保存生成核心时的阴阳布尔值，不从显示文字猜测。

阳五十三局的[NLC892第3217册](https://commons.wikimedia.org/wiki/File:NLC892-411999021002-92864_欽定古今圖書集成_第3217冊.pdf)图39给太乙二、主大八，图40却同时写外迫、格太乙。按当前向太乙前一辰／宫的外迫定义，子八与午二正对，外迫不符。`source_comparison.additional_readings`保留原词与不符标志，快照同时说明；原句是否还有其他参照尚未裁定，不把这处比较直接认作原书已错。

## 五将条件与解释

对宫事实不会新增为卷四五将的第四个条件。该条仍核始击无掩击、文昌无囚迫、主客大小将无相关；其版本范围见[将目关系](taiyi-eye-relations.md)。中五同阵互关、二目互关及四郭固杜也未因本组件而自动成立。

新组件的每个主体保留实际位置、两条同盘`basis`、十六神步距和几何状态。文本由同一评估生成；未出现的原注不当作否定，异称和不符不改写成一致。本层不输出战争胜负或现实成功概率。

太乙`oppositions`、三式`taiyi_oppositions`为已发布选字段视图，首读含全部六主体、来源及未统一项，配合`strict_fields=true`、`include_snapshot_text=false`。视图名不是请求参数；完整结果从同一run的`result_delivery`读取。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1952 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone +08:00 --no-use-true-solar-time \
  --strict-fields --fields taiyi.opposition_assessment taiyi.core_board.yin_dun
uv run --locked --extra dev python scripts/audit_taiyi_oppositions.py --output /tmp/taiyi-oppositions.json
```

1952只是现代日期取得阳53循环相位，不冒认原书古例日期。审计即使24宫数、12对宫全部相符仍退出1：称名未统一，阳53附带外迫的所核不符保留，完整原注与古历尚未验收。几何规则作者FateBridge contributors，版本`taiyi_six_actor_opposition_geometry_v1@1.0.0`；原文与书影来源逐项随规则及原注交付。
