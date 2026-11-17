# 原始 DE441 独立太阳交点

`reference.json.gz` 固定 1684—2304 年全部 14904 个事件及原1200年小寒。
由[维护中的生成器](../../../scripts/astronomy/build_de441_solar_reference.py)在独立环境实算：
CALCEPH5.0.1 读取原始 JPL 双精度系数，Skyfield1.53 计算光行时、引力偏折和光行差，
ERFA 长周期岁差／IAU2006 偏置与 Swiss2.10.03 标量黄赤交角／完整章动确定同定义日期框架。
每月15日上下30个TT日独立括区；不使用 FateBridge 输入根、系数读取或光学实现。

命令形式如下。库和星历从独立来源准备，不从 FateBridge 生产实现导出。

```sh
python scripts/astronomy/build_de441_solar_reference.py \
  --library /absolute/path/libcalceph.dylib \
  --kernel /absolute/path/de441-original.eph \
  --first-year 1684 --last-year 2304 --extra-event 1200:0 \
  --output /absolute/path/reference.json.gz
```

本包使用原始JPL记录的1000—2500年连续摘录；只有文件标题与覆盖头字段为摘录而改写，
系数与常数记录保持原字节。输入文件SHA256为
`44b01b1bdca257372a991a7b29685f984831830ee9f050ff2edb5a15516c9355`，
它不是远端完整2.79GB文件的SHA256；下载范围、HTTP身份与上游C测试另存此次验收证据。
完整参考包SHA256为
`4ee41c9515a5d6ec4f981119de3f53e6ce5639d52106d84742a4d72c61fdc2fb`。
包内另保留实际生成器、CALCEPH库与输入文件身份、版本及逐项相邻TT浮点括区。

原门槛为1秒TT和0.001角秒。与原始JPL SDK的约毫秒差包括TT／TDB处理差异；
旧DE440／P03参考另存并保留原1秒线，不替换成这个较接近的参考。
数值一致不认证全部连续时刻、绝对民用UTC、观测精度或现实预测。

来源：[JPL星历定义](https://ssd.jpl.nasa.gov/planets/eph_export.html)、
[CALCEPH时间和读取接口](https://calceph.imcce.fr/docs/latest/html/c/calceph.multiple.cusage.html)、
[Skyfield视位置](https://rhodesmill.org/skyfield/positions.html)。
