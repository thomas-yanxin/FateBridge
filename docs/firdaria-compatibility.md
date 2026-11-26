# 法达计算口径与验收约定

法达为人生阶段类问题提供一种传统占星分期依据。夜盘顺序与年长口径的选择会影响分期日期；比较结果时，需要同时核对时区、时间边界与版本。下方列出可选口径、来源及验收约定，供调用者选参和维护者检查兼容性。

独立 `firdaria` 与综合 `western_timing` 共用两项选择。固定年现按UTC名义经过时长计算；旧地方钟结果与当前结果须区分，不承诺夏令时场景的旧日期保持不变。

[文档中心](README.md) · [算法覆盖](algorithm-coverage.md) · [API 参考](api-reference.md)

直接调用先看[参数与调用](#参数与调用)；比较日期先核对[口径](#两套口径)、[时区](#时区约定)与[边界算法](#公历周年闰日与等分)。profile ID 仅作参考和测试标签，不是接口参数。

## 参数与调用

| 参数 | 可选值 | 默认值 |
| --- | --- | --- |
| `firdaria_night_order` | `nodes_at_end`（夜盘水星后接交点）、`nodes_after_mars`（夜盘火星后接交点） | `nodes_at_end` |
| `firdaria_year_basis` | `fixed_365_2425`（UTC固定名义日）、`calendar_anniversary`（公历周年、UTC七等分） | `fixed_365_2425` |

两项可独立选择，夜盘顺序选项不改变日盘顺序。它们在共用的 `WesternTimingRequest` 家族中公开，顺序和年长算法只用于综合时运中的法达层及独立法达工具；其他独立技法忽略这两项。出生与分析时区由共有边界解释，公历模式另校验生成周年钟时。非法枚举在三端均被公开请求模型拒绝。

所有新结果均在法达对象内返回 `calculation_options`，记录 `night_order/year_basis/subperiod_basis/timezone`；两种年长的子限均为 `utc_elapsed`。公历周年模式的每段大运还增加 `nominal_start_age/nominal_end_age`，大小运均增加 `start_display/end_display`；精确 `start/end` 始终参与计算。`analysis_context.age_years` 是其他西占技法共用的固定年年龄，不随法达口径改变；法达周年边界以 `nominal_*_age` 为准。

REST 请求体与 MCP `firdaria` 参数使用相同字段，例如（地点明确为测试假设）：

```json
{
  "birth_year": 2001, "birth_month": 10, "birth_day": 12,
  "birth_hour": 11, "birth_minute": 40,
  "birth_timezone": "Asia/Shanghai",
  "birth_longitude": 121.4737, "birth_latitude": 31.2304,
  "analysis_year": 2026, "analysis_month": 10, "analysis_day": 19,
  "analysis_hour": 12, "analysis_minute": 0,
  "firdaria_night_order": "nodes_after_mars",
  "firdaria_year_basis": "calendar_anniversary"
}
```

REST 地址为 `POST /api/astrology/timing/firdaria`；综合接口为 `POST /api/astrology/timing`，MCP 对应 `western_timing`。CLI 对应：

```bash
uv run --locked --extra dev fatebridge firdaria \
  --birth-year 2001 --birth-month 10 --birth-day 12 \
  --birth-hour 11 --birth-minute 40 --birth-timezone Asia/Shanghai \
  --birth-longitude 121.4737 --birth-latitude 31.2304 \
  --analysis-year 2026 --analysis-month 10 --analysis-day 19 \
  --analysis-hour 12 --analysis-minute 0 \
  --firdaria-night-order nodes_after_mars \
  --firdaria-year-basis calendar_anniversary \
  --no-include-snapshot-text --strict-fields \
  --fields firdaria.calculation_options firdaria.current_major firdaria.current_sub
```

综合命令使用 `western_timing`，字段路径相应为 `time_lords.firdaria.*`。`return_timezone` 仍属于返照／行运地点，不改变法达边界或法达展示时区；法达始终按出生时区输出，调用方可转换精确瞬间用于其他时区显示。运行中的 Desktop MCP 连接可能缓存旧 Schema，更新源代码后需重载连接再使用新参数。
## 两套口径

| 项目 | `fixed_365_2425`（当前固定年） | `calendar_anniversary`（公历周年） |
| --- | --- | --- |
| 状态 | 默认年长，可独立选择两种夜盘顺序 | 可选年长，可独立选择两种夜盘顺序 |
| 年长 | 每年31556952名义秒，即365.2425个86400秒日 | 大运边界为原始出生钟时的公历周年 |
| 大运推进 | 在UTC连续累加固定时长，出生区只用于显示 | 从原始出生日期按累计名义年龄独立求周年 |
| 小运 | 主运实际UTC时长等分为七段 | 将大运两端对应的UTC历时七等分，独立计算各边界 |
| 序列重复 | 每 75 个固定年重复 | 每累计 75 个公历年重复 |
| 显示 | ISO 8601，保留实际计算出的秒／微秒及偏移 | `start/end` 保留微秒；`start_display/end_display` 截到分钟，不四舍五入 |

原夹具中的 `fatebridge_firdaria_legacy_v1` 和 `user_reference_calendar_bonatti_v1` 保留为历史参考标签，不是接口参数，也不认证第三方产品。当前固定年已经修订时间轴；365.2425是声明的模型常量，不能因为变量名为 `TROPICAL_YEAR_DAYS` 就宣称它是逐年求解的真实回归年或太阳返照，也不处理闰秒。

固定年长也可能采用 365.25 等其他约定，但本参考不将它们与这两套口径混用。

## 来源与工程补充

最初来稿未提供作者、版本或可核验的第三方实现，继续作为原输入资料保存；新增原典、软件和独立时间参考分别记录，不能把来稿标签当作权威来源。

- 来稿提供：九段年限、日夜顺序、七等分小运、交点不分小运、两个分钟显示示例。
- 比鲁尼《占星术要素指南》列出日夜盘各自的七星顺序，两交点均在七星之后，龙头三年、龙尾二年，无共主。第 395 节给出七等分，从本主星起按降序轮转。 [R. Ramsay Wright 1934 年译本 §§395、438–439](https://www.skyscript.co.uk/pdf/pubs/texts/albiruni/docs/albiruni.pdf) · [数序对照](precision-acceptance.md#firdaria-biruni-round157)
- Öner Döşer 列出总计 75 年的九段及七等分规则。图 6 把夜盘交点置于火星之后，第 38 页说明到期从原起始发光体重启。 [《Astrological Prediction》节选，第 38–40 页](https://bendykes.com/wp-content/uploads/2016/08/ap-extract.pdf)
- Steven Birchfield 引述 Abu Maʿshār 的夜盘水星后接交点规则，并讨论通常归于 Bonatti 的另一种理解。仓库历史标签中的 `bonatti` 沿用这一归属。 [《Firdar》，2020 修订，第 2–6 页及附表](https://birchfieldastrology.com/wp-content/uploads/2020/07/firdar_revision-02-2020-07-13.pdf)
- Bonatti 1550 年巴塞尔印本列出日盘火星后的龙头三年、龙尾二年，随后复归太阳。夜盘从月亮开始，并参照日盘的行星伙伴与圈序。印本未明列夜盘交点接位或满 75 年后的重启主星。 [《De Astronomia Tractatus X》，Pars V，Caput III，印列 813–815](https://www.digitale-sammlungen.de/en/view/bsb10196207?page=447)
- 本项目的工程选择：固定UTC名义日、时区处理、UTC七等分、闰日回退、原始出生锚点、微秒量化、分钟截断及边界归属。这些不冒充来稿已说明或第三方产品已经实现的规则。

Birchfield 三个附表有 16 处水星／金星位置与正文规则及 Döşer 图 7 冲突。产品的 `nodes_after_mars` 有 Döşer 图 6 的明确依据。Bonatti 印本文义允许据日段类推，夜盘次序的历史归属仍有分歧。 [固定参考](../tests/fixtures/firdaria-reference.json)

[Morinus所选提交](https://github.com/shin10567/Morinus-Source-Codes)用于公历模式的日期级对照，原模块实际执行，只适配输出词汇。它不接收出生钟时，所选版本的闰日出生会报错，不能认证亚日精度或本命天文。[Cosmic Patterns公开示例](https://www.astrosoftware.com/Firdaria.htm)的无交点版本只在首70年与所选顺序可比；其日粒度表在固定UTC年轴、UTC日期解释下相合，但未公布确切年常量和显示时区，不能由此推定内部设置或秒级符合。实际Temporal参考则独立核对所声明的名义时间模型，不认证物理计时或传统预测。

## 年限、顺序与日夜盘

固定年限为太阳 10、金星 8、水星 13、月亮 9、土星 11、木星 12、火星 7、北交 3、南交 2，总和严格为 75。

| 大运 | 日盘名义年龄 | 默认夜盘名义年龄 | 来稿夜盘名义年龄 |
| --- | --- | --- | --- |
| 太阳 | 0–10 | 39–49 | 44–54 |
| 金星 | 10–18 | 49–57 | 54–62 |
| 水星 | 18–31 | 57–70 | 62–75 |
| 月亮 | 31–40 | 0–9 | 0–9 |
| 土星 | 40–51 | 9–20 | 9–20 |
| 木星 | 51–63 | 20–32 | 20–32 |
| 火星 | 63–70 | 32–39 | 32–39 |
| 北交点 | 70–73 | 70–73 | 39–42 |
| 南交点 | 73–75 | 73–75 | 42–44 |

七星小运按“日、金、水、月、土、木、火”的循环从本段主星开始；两交点不参与小运，也不再分七段。

核心数学验收显式给定日夜盘，不用示例年月日反推。三端验收另提供明确虚构的上海坐标并实际计算本命盘，不将测试地点当作来稿已给事实。来稿没有出生地点，无法核验其“太阳五宫／十宫”是否成立。当前引擎的 `determine_sect` 按实际太阳高度分日夜：原生盘使用已计算的 `is_diurnal`，其他后端以 TT 太阳坐标及 UT1 地平线求高度，非负为日盘。它不再按太阳第7—12宫推断日夜，也不把缺失宫位自动当作夜盘。边界行为以[共享实现](../src/fatebridge/core/predictive/_common.py)及其后端输入为准。

## 时区约定

### 默认固定年模式的可观测行为

出生与分析钟时按共有边界解析，分析钟时以出生时区解释；验收始终显式提供时区和分析钟时，不依赖系统现在、出生小时的默认回填或未知地点。

默认固定年模式从已确认出生UTC瞬间出发，按固定名义秒数推进，最后转换到出生区显示。旧地方钟加法会随夏令时或时区改制改变实际时长，现已修订。例如1990年上海夏令时出生的后续固定年边界与旧快照相差一小时；旧值作为反例保留，不继续保护。当前接口没有法达专用的出生 `fold` 消歧参数。

已知期界落入 TZif `-00` 区间时，起止字段显示带 `Z` 的 UTC 时间，表示当地偏移未知。公历模式的分钟展示沿用该标签，活动期仍按精确端点判断。 [三端时点对照](precision-acceptance.md#elapsed-clock-labels-round71)

### 参考版本的新增约定

1. 测试将两个原文例子明确实例化为 `Asia/Shanghai`，这只是时区测试条件，不代表已知出生地点。也接受显式固定 UTC 偏移；固定偏移不自动获得某城市的历史夏令时规则。
2. 出生、分析和公历周年共用项目锁定的 IANA 时区版本及其未来延续规则。公历模式校验生成的周年，拒绝不存在、重复或当地偏移未定义的钟时，错误指出钟时角色及名义年龄。接口尚无端点单独消歧入口。使用已确认的固定偏移时，整个时间线都采用这一偏移。固定年模式采用 UTC 时长。见[独立 TZif 前像对照](precision-acceptance.md#firdaria-locked-tzif-round127)。
3. 先在出生时区建立大运周年端点，再用 UTC 日序求差与七等分，最后投影回出生时区。出生、分析钟时或期界对应的 UTC 可落在辅助年 0 或 10000，只要待交付的当地钟面仍在公历年 1 至 9999。
4. 两种模式用 UTC 日序比较精确时刻。公历周年模式在分析时刻早于出生时返回验证错误。当前或预览期需要超出当地公历范围的周年终点时，返回不可重试的 `validation_error`。已取得完整预览和当前期时，无需计算越界的后续周年。 [固定年界对照](precision-acceptance.md#firdaria-calendar-anniversary-round154)

## 公历周年、闰日与等分

参考版本采用延伸公历；本文用例均为现代日期，不宣称历史改历场景已经兼容。设出生时刻为 `B`，累计名义年龄为整数 `a`：

```text
anniversary(B, a):
  目标年 = B.year + a
  月、钟时仍取原始 B
  日 = min(B.day, 目标年月的最后一天)
```

出生在 2 月 29 日时，非闰年回退 2 月 28 日，后续闰年恢复 2 月 29 日。所有边界均以原始出生日期为锚点，不能从已经回退到 2 月 28 日的上一段继续加年。例如夜盘 `2000-02-29 12:00 UTC`，9 岁为 `2009-02-28 12:00`，20 岁恢复为 `2020-02-29 12:00`，75 岁为 `2075-02-28 12:00`；2100 年不是闰年。

大运 `[S, E)` 内的第 `k` 个小运边界：

```text
boundary(k) = S_UTC + round_half_even((E_UTC - S_UTC) × k / 7)
k = 0..7，量化单位为微秒
```

从同一个起点独立求各边界，不把截断后的分钟数逐段相加。最后一个边界严格等于大运结束，下一段开始复用该边界。微秒量化可能使各段相差 1 微秒，这是时间表示精度，不是额外的小运时长。

大运、小运均为左闭右开 `[start, end)`：恰在边界属于下一段；交点大运的当前小运为空；恰在 75 年边界进入下一周期。名义年龄不能由显示日期反算成 `75.1` 后再决定周期。

## 显示与参考示例

参考版本的原始边界保留微秒；分钟展示只在时区转换之后将秒、微秒归零。展示值不回写计算，也不影响边界归属。名义年龄使用整数累计年限，第一周期结束固定标为 75，原文的 `75.1` 仅作为未核验的产品展示描述保留。

| 场景（时区补充为 Asia/Shanghai） | 参考精确小运结束 | 参考分钟展示 | 默认固定年模式小运结束 |
| --- | --- | --- | --- |
| 1997-12-28 18:25，夜盘月亮首段 | 1999-04-12T08:07:51.428571+08:00 | 1999-04-12 08:07 +08:00 | 1999-04-12T08:45:24+08:00 |
| 2001-10-12 11:40，日盘太阳首段 | 2003-03-18T04:48:34.285714+08:00 | 2003-03-18 04:48 +08:00 | 2003-03-18T06:16:00+08:00 |

原文的分钟总数 4,733,280 和 5,258,880 正确；除以七分别为 `676182 + 6/7`、`751268 + 4/7` 分钟，不能将省略小数后的整数写成精确等式。若四舍五入到分钟，会得到 08:08 和 04:49，与原文不一致。

## 验证范围

固定输入、来源身份和独立期望值在[固定参考](../tests/fixtures/firdaria-reference.json)，核心入口为 [`tests/western/test_firdaria_reference.py`](../tests/western/test_firdaria_reference.py)，三端入口为 [`tests/western/test_firdaria_transports.py`](../tests/western/test_firdaria_transports.py)。原来稿、实际Temporal、未改动的Morinus日期与文献字面分歧分列保存，不从当前生产输出重建期望值。

| 类别 | 验收内容 | 实际被测对象 |
| --- | --- | --- |
| 序列 | 两套夜盘九段年龄；日盘九段；每段七星小运；交点无小运 | 生产核心全部四种组合；三端实际日／夜盘调用 |
| 示例 | 两个原文分钟结果、精确微秒、大运结束及当前版本差异 | 独立参考数学、生产核心、REST / MCP / CLI |
| 闰日 | 非闰年回退、后续闰年恢复、2100 世纪年、75 年锚点 | 独立参考数学与生产周年函数；固定年生产结果另测 |
| 时区 | 固定UTC名义日、周年UTC七等分、显示转换、固定偏移与地区时区区别 | 独立时间参考与生产核心；旧本地加法保留为历史反例 |
| 歧义 | IANA 出生／分析／周年端点的重复和不存在钟时不自动猜测 | 生产核心及三端错误回执 |
| 边界与取整 | 秒数跨分钟、各段连续、微秒精度、边界归下一段、交点为空、75 年重启 | 两套分别验证；参考小运不留尾差 |

```bash
uv sync --locked --extra dev
uv run --locked --extra dev python -m pytest -q tests/western/test_firdaria_reference.py tests/western/test_firdaria_transports.py
```

生产核心不依赖测试内的参考函数。返回时间线最多12段，`current_major/current_sub`独立覆盖查询时刻；固定时间线由Temporal独立参考核对。
