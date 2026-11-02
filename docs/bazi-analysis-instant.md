# 当前时运使用哪个瞬间

完全省略分析日期时，旧综合时运会算本月1日零点，旧流月会算本月15日零点；流日丢失钟时，流时丢失分钟和秒。这些替代时间可能跨过立春、节令月、晚子时或交运边界。修订后，综合、流月、流日、流时及独立大运统一使用本次`as_of`或执行开始时刻，转换到已解析的出生民用时区；保留UTC偏移、`fold`、秒和微秒。

这项修复没有调整太阳模型、节气精度门槛、农历表、真太阳时、旺衰权重或原典标签。出生太阳钟与分析民用瞬间继续分开。微秒是输入表示精度，不是天文模型或出生记录准确到微秒的认证。

## 已确认的计算差异

以下均为虚构工程输入，`as_of`表示固定的UTC瞬间，出生资料相同、关闭出生太阳钟校正。

| 入口及固定时刻 | 旧替代时间 | 修复后的当地分析瞬间 |
| --- | --- | --- |
| 综合，2025-02-04 04:37:49.123456Z | 2月1日零点 | 2月4日12:37:49.123456+08:00 |
| 流月，2025-02-01 04:37:49Z | 2月15日零点 | 2月1日12:37:49+08:00 |
| 流日，2025-03-01 15:30:00Z | 3月1日零点 | 3月1日23:30+08:00 |
| 流时，2025-02-03 14:37:49Z | 2月3日22:00 | 2月3日22:37:49+08:00 |

第一例旧时点在立春之前，新时点在立春之后。第三例按项目既定23时换日政策，仍显示民用3月1日，日柱对应3月2日；PMO原表该日为庚午。流时内原有的`liushi_info.analysis_datetime`保持整点缓存标签，供旧调用方兼容；它不是交气或交运比较瞬间。实际瞬间一律读取新`analysis_reference`及同次历法上下文。

首次受控对照（本地数据：`validation/bazi-analysis-instant-first-v1.json.gz`）保留17条全部记录：11份有效显式／部分日期请求的原业务字段完全不变，4条默认时刻反例得到修正，2条此前被接受的不存在／重复分析钟时改为明确拒绝。比较只排除新增加的`analysis_reference`；没有删除旧快照、预算或其他业务字段来取得保留结论。

## 部分日期与显式年龄

提供任一`analysis_year/month/day/hour/minute`仍进入已有的部分日期补齐规则，零是显式值。

| 工具 | 缺失分量取执行时钟 | 其余固定补齐 |
| --- | --- | --- |
| `timing_analysis` | 年、月 | 日1、时分0 |
| `liuyue_analysis` | 年、月 | 日15、时分0 |
| `liuri_analysis` | 年、月、日 | 时分0 |
| `liushi_analysis` | 年、月、日、时 | 分0 |
| `dayun_analysis` | 年 | 月日1、时分0 |

表中只对缺失分量取值，已提供值不覆盖。拼出的日期若无效则报错，不凭空截日。显式`analysis_age`的独立大运没有分析日时，也不能与分析日期组合；综合工具的年龄覆盖只影响其大运年龄参考，其他时间层仍使用实际分析瞬间。

## 偏移与夏令时

[Python对aware与naive时间的定义](https://docs.python.org/3.12/library/datetime.html#aware-and-naive-objects)区分了真实瞬间与未消歧的墙钟标签；[ZoneInfo文档](https://docs.python.org/3.12/library/zoneinfo.html#using-zoneinfo)明确说明从UTC转换时会设置正确的`fold`。

纽约2025-11-02的`05:30Z`和`06:30Z`分别是`01:30-04:00`、`01:30-05:00`。两者都是已确定的瞬间，不能因当地钟面重复而拒绝或都选择第一遍。月、日缓存现在用UTC瞬间区分aware输入；同一时区的两个fold在Python中可能比较相等，原缓存键会复用错误的节气经过量。时柱仍按民用钟面的小时分桶，不用小时缓存反推交气时刻。

显式填写纽约不存在的2025-03-09 02:30或重复的2025-11-02 01:30则不能自行确定瞬间。五个入口统一报非重试型输入错误。保持原出生时区，省略分析日期分量并用带时区的`as_of`提供已确认的目标瞬间，可以表达两个真实fold；不要为了消歧分析时刻而修改出生时区。

## 查询与同次说明

五个入口均发布`analysis_clock`视图，其`fields`为`["analysis_reference"]`。视图名不是请求参数。该对象记录完整当地与UTC瞬间、时区、fold、选择依据、用户提供分量、来自时钟的缺省项与固定缺省项。执行回执的`current_time_fields_defaulted`读取这个实际选择结果，不把固定的日1、日15或分0误报为读取了当前日期。

全部省略日期的快照附同次时刻依据，不重新排盘。原分钟显示、时柱整点与完整比较瞬间分别说明。单字段严格投影也可读取`analysis_reference.utc_datetime`，不要求同时返回其余兄弟字段。

```bash
uv run --locked --extra dev fatebridge timing_analysis \
  --birth-year 1990 --birth-month 5 --birth-day 15 \
  --birth-hour 10 --birth-minute 30 --gender 男 \
  --birth-timezone Asia/Shanghai --use-true-solar-time false \
  --as-of 2025-02-04T04:37:49.123456Z \
  --fields analysis_reference liunian_analysis.pillar liuri_analysis.pillar \
  --strict-fields true --include-snapshot-text false --response-char-limit 0
```

## 来源与验收边界

原始方案（本地数据：`../tests/fixtures/bazi_analysis_instant_v1/protocol.json`）、修改前完整结果（本地数据：`../tests/fixtures/bazi_analysis_instant_v1/before-results.json.gz`）、受控旧结果（本地数据：`../tests/fixtures/bazi_analysis_instant_v1/before-results-controlled.json.gz`）及环境补记（本地数据：`../tests/fixtures/bazi_analysis_instant_v1/environment-addendum.json`）全部保留。首次搬移的旧源码使用空星历路径而回退到解析模型；当前工作区使用项目星历文件。没有用该环境不一致证明保留，随后将相同旧源码和新源码都明确指向同一星历目录，再作17条逐字段比较。

补充日期见证（本地数据：`../tests/fixtures/bazi_analysis_instant_v1/date-side-witnesses.json`）取既有JPL/DE440的2025立春TT交点，按[IERS历史TAI−UTC表](https://hpiers.obspm.fr/iers/bul/bulc/Leap_Second_History.dat)的37秒及[USNO的TT定义](https://aa.usno.navy.mil/faq/TT)32.184秒换成该年UTC，在前后各5秒验证同一分钟内的年／月切换。它发生在初次工程对照之后，记录时序，不作新盲测信用，也不放宽原1秒模型门槛。PMO日标签和[HKO2025历表](https://www.hko.gov.hk/tc/gts/time/calendar/pdf/files/2025.pdf)也属于已暴露来源，不与旧逐日、逐节气验收重复累计。

本轮工程验证及失败记录见验收报告（本地数据：`validation/bazi-analysis-instant-local-v1.json`）。源码与构建包各通过同一123项时运检查；另有10项回放及92项投影检查。两个独立stdio进程分别读回52页同run完整结果并验证散列。重复运行不累计为独立准确率样本。当前聊天原已连接的MCP进程仍加载旧合同，拒绝新字段；本轮未重启共享进程或发布，独立进程通过不能替代该连接的部署验收。

任意时区、未来UTC、真实出生记录、完整原典力量和独立多轮解释仍未全部验收；该次时刻验收引用的24个旺衰四柱分歧不因修复减少；后续完整来源范围见[当前回归](bazi-source-corpus-audit.md)，目标继续未完成。
