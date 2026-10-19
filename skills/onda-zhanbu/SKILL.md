---
name: onda-zhanbu
description: 用 FateBridge 围绕一个具体问题起卦或起局，呈现可复核的卦变、体用或盘局依据，把传统提示转成现实中需确认的条件与下一步。Use when 用户明确求一卦、占卜、梅花易数、六爻、奇门、大六壬、金口诀、太乙、宿占、三式合参、星骰或西洋卜卦；已有结果解释沿用原卦，不反复起卦，不代替用户决定。
---

# 问事与占卜

围绕用户悬而未决的一件事，讲清「这次卦／局是什么、传统读法强调哪处变化、现实中还需确认什么」。算出的卦象要可见、可复核，不能起卦后只回一段通用鼓励，也不能把传统吉凶变成真实成败承诺。

## 共用范围与安全

先读[咨询硬边界](../_shared/safety-boundaries.md)与[本轮范围及多视角选择](../_shared/consultation-routing.md)。按当前问题展开，首轮明确要求详细就覆盖；不自动附带全部相关主题。时间追问读[共享时间选择](../_shared/timing-selection.md)，保留原主题与已有相关视角，只补需要的新层。生死、临床判断与医疗择时在选法前停止。

## 引用路径与必读资料

发现入口可能是软链接。先进入入口目录，以 shell 内建 `pwd -P` 取得真实目录，再解析相对引用；不要裁剪 `.agents/skills/onda-*` 的字符串父目录。

- 计算与完整结果交付：[../_shared/fatebridge-engine.md](../_shared/fatebridge-engine.md)
- 表达与事实边界：[../_shared/onda-counsel.md](../_shared/onda-counsel.md)
- 场景取舍与去重：[../../docs/scenario-routing.md](../../docs/scenario-routing.md)

所有起卦、装卦、体用、用神与起局交给引擎；不得用临时随机数、手算或模型记忆替代。用户提供的既有卦例要沿用，所选工具无法接收该卦例时说明范围，不暗中换成当前时间重新起卦。

## 先明确一件事与取法

用户已经说明具体问题与起卦方式就直接沿用，不重复盘问。问题含糊到会改变判断对象时，一次用一两句核对：问的是哪个选项、考虑到什么时候。不要为起卦强要生辰或完整人生背景。

用户未指定卜法时，以时间梅花为默认的一项主证。普通现实决定但未请求术数时，不因“要不要”三个字自动起卦。

| 用户的选择／所问 | 主证工具 | 实际输入与交付重点 |
| --- | --- | --- |
| 即时问事、指定时刻梅花 | `meihua_analysis` | `analysis_year/month/day/hour/minute/timezone` 按实际合同；本卦、动爻、变卦和体用 |
| 已有四卦的统摄组合 | `tongshefa` | 按用户实际给定的 `taiyin/taiyang/shaoyang/shaoyin` 四卦组合左右卦、潜藏与亲和；固定默认不是本次起卦。当前不实现蓍草十八变／大衍随机起卦，用户要后者时直接说明范围 |
| 六爻 | `sixyao` | 手摇初爻至上爻六个 6／7／8／9 用 `coins` 或已有 `gua_code`；REST/MCP 可传 `lines`。随机起卦保留 seed，解释已得卦不再摇一次 |
| 奇门方位、时机与谋略 | `qimen` | 所选时间及实际选项；先读局与相关宫，未返回的用神或事件判定不补写 |
| 大六壬起课 | `liureng_gods` | 实际起课时间／选项及返回课传；不把复杂盘名当已确定具体事件和应期 |
| 六壬行年 | `liureng_runyear` | 出生信息与分析年，按实际流月结果读；与即时一卦分开 |
| 金口诀 | `jinkou` | 地分 `di_fen` 与起课时间；不猜地分 |
| 太乙 | `taiyi` | 实际起局时间与所选选项；仅按返回的大势盘层解释，不直接外推个人小事 |
| 宿占 | `suzhan` | 实际时间与所需地点；说明采用宿度／星宿口径 |
| 三式合参 | `sanshiunited` | 仅用户要求合参时用，逐系保留来源及分歧；多盘不增加成败概率 |
| 解读已有星骰 | `otherbu` | 核对用户实际提供的 `planet/sign/house`，宫位按 Schema 索引；不自动抽骰，不把默认骰面当新抽取，也不称作已实现塔罗牌阵 |
| 西洋卜卦 | `astro_horary` | 提问时刻 `question_*`、地点 `longitude/latitude`、时区与 category；不把出生时间当提问时间 |
| 查已得卦的含义 | `gua_lookup`／`gua_meiyi` | 按卦名／号查询；查义不另起卦，引用与本卦关联的条目 |

## 固定问时，保留同一卦

时间梅花需要明确起卦年月日时。用户指定时刻时原样保留日期、分钟和 `analysis_timezone`；核对 `analysis_context.analysis_datetime/timezone/question`。按当下起卦才取得当前时间和相应时区，不用示例日期或默认时区冒充用户选择。`as_of` 不能代替所选工具的显式起卦参数。

其他卜法按各自输入，不强套梅花的年月日要求；有用户手摇记录就不改为随机摇卦。复问同一件事先解释、核对或复盘原结果，不重复起卦凑答案。资料更正确实影响计算时重建输入，沿用 `trace_id`／`parent_run_id`，说明哪一事实变化。

普通首轮使用实际合同中验证过的 `fields`、`strict_fields=true`、`include_snapshot_text=false`。按所选工具检查结构化业务结果，不把快照只有文本误读为业务结果只有文本，也不套用梅花式字段；确无独立业务字段时保留必要文本。

## 梅花：让卦变解释这件事

按以下证据链组织，短答只呈现最有用的两三处，详细请求再扩展互卦与错综：

| 需要看清什么 | 实际字段 | 解读动作 |
| --- | --- | --- |
| 这一次到底算了什么 | `analysis_context`、`meihua.method` | 固定提问与起卦时刻；本工具是时间取数，不能承诺接收任意报数／声音起卦 |
| 当前局面到变化 | `meihua.base_hexagram`、`meihua.seed.moving_line`、`meihua.changed_hexagram` | 用一行「本卦 → 动几爻 → 变卦」呈现，再用实际卦义说明前后变化；不只念卦名或贴吉凶 |
| 主客如何作用 | `meihua.body_trigram/use_trigram/body_use_relation`、`interpretation.body_use_reading` | 先核对体用关系，再按用户问法作条件式角色对应；不能直接认定用卦是对方内心 |
| 哪一步值得留意 | `interpretation.moving_line_phase/moving_line_oracle` | 说明返回所用的阶段与条件；阶段象意不是事件发生日期 |
| 可用处与限制 | `interpretation.action_hint/risk_hint`、卦内 `guidance/caution` | 各取实际相关的一处，转换为所问事项的注意点；生活建议另作标记 |
| 详细复盘的其他视角 | `meihua.mutual_hexagram/cuo_hexagram/zong_hexagram`、实际 `interpretation` | 用户要求才展开；每层说明自身依据，不强造它们都支持同一结论 |

引擎生成的 `moving_line_oracle`、`base_oracle` 等是本工具的结构化解释，不自动等同《周易》原文爻辞。要引用经典必须另核原文与来源，不能把模板语句伪装古文。月令强弱、外应和精确应期没有本次计算支持时保留未覆盖，不从卦名补算。

## 其他盘局也要有可见依据

奇门使用公开 `evidence_views.directional` 字段卡，六爻使用 `line_reading` 卡（它们的默认首轮已保留核心盘面）；卡只是首次请求的 `fields` 参考，不传 `view` 参数。详细读法如下，不以 snapshot 或 summary 替代已经存在的结构化事实。

| 本次要回答什么 | 实际读取 | 如何解释及保留范围 |
| --- | --- | --- |
| 奇门这一次的起局与核心宫 | `analysis_context/four_pillars`、`qimen.ju_text/dun_type/xun_head/kongwang/zhifu/zhishi/palaces` | 固定问时，先找值符／值使实际所在宫，再按已说明的所问角色读相关宫；不由宫名直接认定某个人的心意 |
| 奇门某方向或选项 | `qimen.palaces` 各条的 `name/trigram/heaven_stem/earth_stem/god/door/star`，变换盘另核 `content_palace/content_trigram` | 说清宫位与门星神、天地盘干的实际组合及所用传统解释。数组整体读取后选相关宫，不构造不存在的筛选路径；位置槽和内容来源分开，不仅凭“某门吉”排现实选项，不把九宫方位当房屋风水定宫 |
| 六爻本卦到变卦与起卦来源 | `input_normalized/nongli/current_hexagram/changed_hexagram/moving_lines`；需要核起卦方式时加 `cast` | 本变卦与动爻来自同一次结果；手摇、指定卦码、随机和时间梅花分别标明，不能把自动时间装卦说成用户摇卦 |
| 六爻装卦、世应和变化细读 | `lines` 的 `position/branch/element/liuqin/liushen/shi_ying`、动爻及 `changed_branch/changed_liuqin/is_fuyin_line`；`hexagram_info` | 按初爻至上爻核对位置，引用实际世应、六亲、六神与变支。动爻专属字段可能不存在，不能为静爻补变支；装卦已实现不等于自动完成取用神、月日旺衰、空破与精确应期判定 |
| 用户点名六合／六冲等结构 | 按实际合同加 `patterns/pattern_flags` | 只解释本次命中的结构及来源，空表不补“隐含”格局；不能由一个结构断成败 |

没有返回完整取用神、旺衰和应期规则时，直接说明该判断未自动覆盖；仍交付已有宫盘／装卦支持的传统解释，不把“没读到”说成“引擎没实现”，也不照别家教程替引擎补算。大六壬、金口、太乙及西式卜卦按实际字段或文本保留两三项关键事实，与解释分开。不要为展示“全面”把各家术语混成一套。

## 交付给用户的判断辅助

先回答这次传统参考最值得留意什么，随即展示真实卦变或盘局依据，通常 200–300 字。一项支持推进的提示与一项需要留意的条件只有返回确实包含时才写；结果混合就把混合说清，不强迫落成“会／不会”。

现实建议围绕用户已给的选项：下一步最值得确认的条件、低成本试验或何时复盘。比如用户问项目试点，只有他们确有该选项时才谈范围、资源与验收条件；不能说卦已经算出客户会答应。要比较多个现实选项时，可按「选项／已知条件／尚待验证／可逆下一步」做一张小表，明确这部分是现实决策整理，不是卦象计算排名。

不读他人内心，不预告疾病、灾祸或具体财务结果。生死、临床判断和医疗择时请求在调用前停止；法律和重大财务事项的行动以事实及专业判断为依据，决定由用户自己作。边界在相关处说明一次，不用长篇免责声明挤掉卦义。

首轮被裁掉的字段不能靠分页恢复。已有 `result_delivery` 时读同 run 的所需字段／分页；用户要求完整 JSON 或完整文件时，首次 `fields=null`、保留默认响应预算，核对业务 payload 的 SHA-256，不另起一卦补交付。

## 可复核示例

CLI 示例使用已安装并激活的仓库虚拟环境，准备方法见[引擎调用](../_shared/fatebridge-engine.md#怎么调引擎)。

以下为虚构问题与指定时间，不是“现在”。已有 MCP 时直接调用。

```bash
python3 -m fatebridge.cli meihua_analysis --question "是否先做小规模项目试点" \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15 --analysis-minute 20 \
  --analysis-timezone Asia/Shanghai --strict-fields --no-include-snapshot-text \
  --fields analysis_context meihua.base_hexagram.name meihua.seed.moving_line meihua.changed_hexagram.name meihua.body_use_relation interpretation.action_hint interpretation.risk_hint

python3 -m fatebridge.cli qimen \
  --analysis-year 2026 --analysis-month 6 --analysis-day 18 --analysis-hour 15 \
  --strict-fields --no-include-snapshot-text --fields analysis_context qimen.ju_text qimen.dun_type qimen.zhifu qimen.zhishi qimen.palaces

python3 -m fatebridge.cli tongshefa --fields summary

python3 -m fatebridge.cli sixyao --question "这个项目试点有什么需要留意" \
  --date 2026-06-18 --time 15:00:00 --seed 20260618 \
  --strict-fields --no-include-snapshot-text --fields input_normalized nongli current_hexagram changed_hexagram moving_lines lines hexagram_info

python3 -m fatebridge.cli astro_horary --category career \
  --question-year 2026 --question-month 6 --question-day 18 --question-hour 15 \
  --longitude 116.40 --latitude 39.90 --timezone-name Asia/Shanghai --fields summary
```

生辰参评、河洛本命卦等已有能力按 [onda-mingge](../onda-mingge/SKILL.md) 处理，不用出生条文替代本次问事卦。
