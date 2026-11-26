# 派生太阳钟标签与农历、时支

`reference.json` 固定8个真实可用民用输入，检查派生太阳钟标签在共享历法层
不被重新解释成另一个民用瞬间。此处不裁定各传统体系应优先采用太阳钟或民用钟，
不改变现有按所选日期查中国农历的约定。

独立参考生成进程未导入FateBridge。民用瞬间由原生pytz直接`localize`取得；
以已保存原始源码所编译的sxtwl 2.0.6直接调用`fromSolar`和`getHourGZ`，
取得农历年月日及小时干支。版本、原包／绑定／二进制SHA-256记录在JSON中。
另新下载[香港天文台2011年表](https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2011e.txt)
和[2026年表](https://www.hko.gov.hk/en/gts/time/calendar/text/files/T2026e.txt)，
逐行核对全部8个日期的农历月首及日数，保留原始行和文件散列。
这只验证所选公历日期的公布映射，不认证每个时区的独立天文农历。

梅花上下卦及动爻由所选[《梅花易數》卷一固定转录](https://zh.wikisource.org/w/index.php?oldid=2690596&title=梅花易數/卷一)
「周易卦數」「年月日時起例」独立作整数运算：年支序数加农历月日取上卦，
再加时支序数取下卦及动爻，整除时分别取8或6。这不是第二套完整梅花实现，
也不等于完成影印原典校勘或预测有效性验收。

太阳钟与民用钟的区别依据[USNO的均时差定义](https://aa.usno.navy.mil/faq/eqtime)，
时区规则范围依据[IANA说明](https://www.iana.org/time-zones/theory)。
参考中的`expected.solar_datetime`来自直接Swiss `time_equ`的相同UTC近似UT1约定，
只用于说明输入落在哪个日期／小时；其毫秒与当前托管Swiss配置略有差别，
不得用来声称独立均时差精度通过。精度门槛是离散年月日、时支及取数完全相同，
另要求生产返回的农历钟面与本次生产实际算出的`corrected_datetime`原标签完全一致。

原HEAD版本的完整`almanac.py`以Git对象读取后在独立模块中重放，原请求和
`pre_fix`保留。纽约、巴黎、悉尼的春季跳时把太阳钟02点改成03点，时支和下卦、
动爻随之错误；Apia整日跳跃把2011-12-30改成12-31，农历十二月初六误作初七。
Lord Howe半小时跳时另把02:22改成02:52，虽然所选时支及取数恰好相同，
该钟面失败仍保留。纽约、Lord Howe秋季正常输入和UTC为未失败控制。

修复后的8项独立离散参考全部相符，生产自己的太阳钟原标签也全部保留。
`pre_fix`与`post_fix`是同一队列的前后重放，不是16个独立样本，也不是所有
DST转换、连续时域、物理钟时、全体系专家可用或SOTA认证。

完整生成器、独立原始输出、原HKO文件、原HEAD源码与前后比较保存在
`~/.codex/artifacts/fatebridge-solar-clock-labels-20261117/`。
JSON记录生成器散列与实际原版本提交，测试只消费冻结结果，不在测试中安装第三方库。
