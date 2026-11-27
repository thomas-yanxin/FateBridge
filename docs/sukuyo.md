# 宿曜与宿占参考

[文档中心](README.md) · [API 参考](api-reference.md) · [算法覆盖](algorithm-coverage.md) · [结果解读参考](interpretation/shared/sukuyo-evidence.md)

`suzhan`（宿占）与 `sukuyo_compatibility`（宿曜双人相性）保留实际所选宿主历法、配宿档案与原典条文，完整输入契约见[宿占合同](contracts/suzhan.json)与[宿曜相性合同](contracts/sukuyo_compatibility.json)。历日宿名、天文角距与行为条文各有适用条件，不能互换身份。

## 历法与配宿档案

`calendar_basis` 支持现代中国农历（`chinese_hko_utc08`，UTC+08）、HuTime 日本逐日参考（`japanese_hutime_1002_1_utc09`，UTC+09，1872-02-09 至 2031-01-22）及 NAOJ 日本历史月朔参考（`japanese_naoj_historical_utc09`，UTC+09，0001-01-01 至 1872-12-31）；超出对应历法支持范围直接报错，不静默切换。

`calendar_profile=t1299_fullmoon27` 按 T1299 望日逆顺及生日加十三法配宿；`hinoo_t1299_host27` 应用 T2465 的闰月、小月分宿条件（需在初一前后半有歧义时传入 `calendar_day_part` / `person1_calendar_day_part` / `person2_calendar_day_part`）。当地日期已知而出生时刻未知时，系统转换到宿主时区并保留全部可能日期与候选宿。

`suzhan` 在已知钟时（`time`）下计算星图时须提供完整经纬度（`latitude` / `longitude`，`0°` 有效）；钟时未知时可省略 `time` 与坐标，仅返回日期与历日候选宿。

## 相性与条文结构

双人相性按本命宿之间的有向模环关系计算三九秘法位置（`distance_rule` 支持 `symmetric` 与 `directional`）；存在候选宿时传播为候选关系列表，不取均值。条文查询还区分三九日、六宫宿、二十七宿四足（`textual_pada` / `person1_textual_pada` / `person2_textual_pada`，按宿名查表）与十二宫前提，并随同一次结果交付各自版本、来源及异读。
