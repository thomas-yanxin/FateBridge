# DE441 端点与远期交点独立参考

`reference.json.gz` 保存 1、2999、3000、3001、5399、5400、6000、9998、9999 年的
全部216个节气，以及实际相邻上下文所需的0年大雪／冬至、10000年小寒／大寒，共220项。
原1684—2304及1200年参考包保持原值。

参考由[独立生成器](../../../scripts/astronomy/build_de441_solar_reference.py)计算：
CALCEPH5.0.1读取原始DE441系数，Skyfield1.53计算视位置，ERFA及Swiss2.10.03
确定相同日期框架。生成器不导入FateBridge，不用候选交点作初值。包内保存完整生成源码、
版本、输入摘录和库的SHA256、每个交点的相邻TT浮点括区。

每年使用NASA官方原文件的连续记录，按原32日格向外取整，普通年覆盖元旦前32日至次年
元旦后32日。1和9999年的独立摘录扩大至前后64日，以包含额外相邻事件的完整独立搜索
括区；运行模型并未随之扩大。只改摘录标题和覆盖头，常数和系数字节不变。首次较窄摘录
导致独立参考生成失败，失败和下载回执保留在本轮外部证据，未改成通过。

各年分别运行，端点额外传入两项：

```sh
python scripts/astronomy/build_de441_solar_reference.py \
  --library /absolute/path/libcalceph.dylib \
  --kernel /absolute/path/de441-original-1-guard.eph \
  --first-year 1 --last-year 1 --extra-event 0:22 --extra-event 0:23 \
  --output /absolute/path/year1.json
```

9999年使用`--extra-event 10000:0 --extra-event 10000:1`；其余年份不传额外事件。
输入文件身份来自各次实际运行，不是完整远端2.79GB文件的哈希认证。
合并包SHA256：`615ed1e9a1fd6c252fe86b7e6d55804b482002b0e49318ec570db052215679fd`。

门槛保持1秒TT与0.001角秒；本组当前最大差约0.322毫秒和0.000013581角秒。
这不是1—9999年全部连续时刻、历史／未来UTC或独立天体观测的认证。
无原生库时，现代冻结原子偏移到TT的路径可以工作；1960年前既有历史钟时政策需要原生库，
缺失时报钟时错误，不猜测TT或交付线性节气。

来源：[JPL星历定义](https://ssd.jpl.nasa.gov/planets/eph_export.html)、
[CALCEPH时间与读取接口](https://calceph.imcce.fr/docs/latest/html/c/calceph.multiple.cusage.html)、
[Skyfield视位置](https://rhodesmill.org/skyfield/positions.html)。
