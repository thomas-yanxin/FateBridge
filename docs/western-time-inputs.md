# 西方星盘的时间输入

民用钟面时间必须先有时区，才能确定一个计算时刻。西方本命盘、希腊盘、13扇区盘、德国盘、关系盘和使用共同本命入口的推运工具，不再把未解析的民用时区默认为UTC。

- 提供已确认的 `birth_timezone`，可以是IANA名称或UTC偏移；确认原记录为UTC时明确填写 `UTC`。
- 省略时区时，可以由支持的、无歧义的 `birth_place` 解析。经纬度本身不能确定民用时区。
- 省略、`null`、空字符串且地点无法解析时，返回 `validation_error`，领域校验的HTTP状态为400。需要补全资料后再计算，不能为通过校验随意填UTC。
- 关系盘双方分别满足这一前提；一方缺失时，不先交付另一方参与的关系盘。

四种主西占盘的 `person_info.timezone_source` 表示 `birth_timezone`（明确给定）、`birth_place`（地点解析）或 `solar_clock_conversion`（明确太阳钟面输入）。德国盘位于 `base_chart.person_info`。地点解析只是目录采用的时区规则，不能替代对某个历史出生记录的核实。

明确的地方平太阳时（LMT）和地方真太阳时（LAT）有各自换算路径。在目前支持它们的13扇区盘、德国盘入口，设置 `birth_clock_basis=local_mean_solar` 或 `local_apparent_solar`，省略 `birth_timezone` 并保持 `use_true_solar_time=false`。普通本命盘和希腊盘的公开请求没有因此新增LMT／LAT支持。`use_true_solar_time` 是已有的校正选项，不是声明原始记录采用太阳钟面的替代参数。

共享底层 `build_astro_birth_info` 仍可为旧的位置计算构造标为 `default_utc` 的对象，但西方专业星盘和共同推运入口拒绝把它当成已知出生时刻。印度盘保留其单独的旧有策略；果老、宿占的既有策略不由本次变更重新定义。

这是输入兼容性收紧。旧调用若依赖缺省UTC，需要先核实时间依据。它避免对不完整资料输出一个貌似精确的星盘，并不增加天文独立参考样本，也不证明占星预测有效。

时间换算依据可参阅 [Swiss Ephemeris编程文档](https://www.astro.com/swisseph/swephprg.htm) 的 `swe_utc_timezone` 和9.4节；历史民用时区的覆盖和限制见 [IANA时区数据库](https://www.iana.org/time-zones) 及其[理论说明](https://www.iana.org/time-zones/theory)。本次验证及当前连接仍运行旧代码的情况见验证报告（本地数据：`validation/western-timezone-source/report.md`）。
