# 占星骰参考

[文档中心](README.md) · [API 参考](api-reference.md)

`interpret_astrology_dice` 对用户已投出的三枚占星骰（星体、星座、宫位）进行符号条件与来源依据解读（规则版本 `astrodice_symbolic_v7`），并在提供完整时空坐标时可选附带独立天象背景。工具不代替抽骰，也不接收塔罗牌阵。

## 输入与调用

`planet`、`sign`、`house` 三项必填。`house` 采用 **0..11 索引**（第 1 宫传 `0`，第 12 宫传 `11`），输出 `symbolic_details.house_number` 为自然宫号 `1..12`。`planet` 支持日月、八行星及南北交点（中英文或符号均可）；`sign` 支持十二星座中英文或符号。

仅解读骰面时无需日期或坐标：

```bash
uv run --locked --extra dev fatebridge interpret_astrology_dice \
  --planet Mercury --sign Virgo --house 6 \
  --question '虚构示例：合作沟通中应核对什么？' \
  --fields method_id planet sign house symbolic_details rulesets rule_trace validation \
  --strict-fields
```

REST 请求示例（字段投影参数放在 URL query）：

```bash
curl -sS -X POST \
  'http://localhost:8010/api/divination/astrology-dice/interpret?fields=method_id&fields=planet&fields=sign&fields=house&fields=symbolic_details&fields=rulesets&fields=rule_trace&fields=validation&strict_fields=true&include_snapshot_text=false' \
  -H 'Content-Type: application/json' \
  -d '{"planet":"Mercury","sign":"Virgo","house":6}'
```

如需附加独立天象背景（`chart`），须同时提供公历 `date`、当地民用 `time`、时区 `zone` 及经纬度（`lat`/`lon` 或 `gps_lat`/`gps_lon`）。可选选择器 `tradition`、`hsys`、`zodiacal` 与 `fortune_method`（默认 `sect_reversing`，可选 `ptolemy_iii10`）仅作用于附加天象，不改写骰面符号。

## 符号规则与传统来源

| 层 | 依据来源 | 实现与边界 |
| --- | --- | --- |
| 十二骰面与组合结构 | Rev Bill Duvendack, 2013（*What are Astro Dice*） | 日月、八行星、南北交点与星座、宫位组合；不实现出生盘比较 |
| 七曜星座关系 | Claudius Ptolemy，《Tetrabiblos》Ashmand 1822 英译，I.XX / I.XXII | 星座级入庙、擢升、落陷；失势按入庙对宫约定（Deborah Houlding 阐释） |
| 七曜三分性 | Claudius Ptolemy，《Tetrabiblos》Robbins Loeb 1940，I.18 | 分别保留昼夜条件主星（火日木、土月金、风土水、水火月金），不替骰面选定昼夜 |
| 七曜昼夜分派 | 同译本，I.7 | 太阳/木/土为昼曜，月/金/火为夜曜，水星按晨星/昏星保留条件 |
| 七曜喜乐宫 | William Lilly，《Christian Astrology》，1647，pp.51–56 | 水1、月3、金5、火6、日9、木11、土12（按 `symbolic_details.house_condition` 返回） |

超出七曜范围的三王星与南北交点在星座尊贵、喜乐宫与自然昼夜条件中保留 `null`，不按否定处理。`rulesets` 与 `rule_trace` 随结果返回作者、版本、来源路径与命中依据；可用 `evidence_views` 中的 `astronomical_context` 或 `astronomical_motion` 字段清单展开附加天象详情。

## 附加天象边界

附加天象复用核心星盘几何、即时黄经日速（`chart.chart.objects[].motion`）与原生/近似星历标识；显式需要 JPL 原始 DE441 源时可在环境变量配置 `SE_EPHE_PATH` 与 `FATEBRIDGE_JPL_FILE`，相关配置见[星历数据安装](ephemeris.md)。
