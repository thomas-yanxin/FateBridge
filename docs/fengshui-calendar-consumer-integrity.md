# 月盘数式与历法消费端验收

[历法与精度](fengshui-calendar.md) · [月紫白](../skills/onda-fengshui/references/monthly-stars.md) · [全部交节参考](fengshui-all-terms-calendar.md) · [月区间分层](fengshui-month-interval-fidelity.md)

这轮补齐两项独立检查：月紫白的原表数字与九宫飞布，以及交节误差传到年盘、月盘、命卦和宅运之后的分支选择。两项分别验收；候选保护成功不能抵消交点数值超差，也不能算现实预测命中。

## 已保存的旧错误回执

受控测试保留正确的2026年第1节月输入，把入中八改为九，九宫全部同步加一并循环，名称、五行和固定释义也同步重写。九星仍是完整1–9排列。原服务返回成功，旧核验器又因原run散列、回执、排列及文本相符而授予位置覆盖。

这说明旧检查遗漏了原表与数式的一致性；不是已经观察到真实住宅的预测错误，也不表示常规公式曾自然产生这个注入结果。正确、错误两次实际运行的完整响应、原回执、旧核验结果和输入先行冻结在故障档案（本地数据：`../tests/fixtures/fengshui_monthly_fault_v1/hashes.json`）。后续不重算原请求冒充旧run，也不重写这些文件。

## 源表、计算与文字分别核对

新检查从早已冻结的原书读稿（本地数据：`../tests/fixtures/fengshui_monthly_v1/reference.json`）取36个入中数，保留PDF731图像（本地数据：`../tests/fixtures/fengshui_monthly_v1/table-731.png`）。图数为《沈氏玄空学》整理本玄空辑要的三组年支、十二个月；文件与署名仍按月紫白原版本登记。六月节候原印大暑、小暑的差异保持不变。新增检查没有获得独立人类专家校勘、全书或新作者认证。

`monthly_integrity`不调用月盘构建器、生产年组配置或固定文本来生成自己的预期，分别检查：

- 有效年、年支、节月、月支和原表入中数；五黄在源表中的数仍保留。
- 全部九宫的固定宫数、实际月星、既定洛书宫序、月星名称与五行身份。九星完整排列不能代替逐宫数式。
- 起止区间、实际查询时刻及对应节名、民用年，确认输入与返回上下文的绑定。
- 当前近边界结果不冒充唯一月份／有效期，候选相邻且暂取区间确实包含所查询的时刻。旧缺项响应不被追授新候选区间覆盖。

领域构建后、固定释义生成前执行一次；服务交付前再检查实际请求与返回层。内在矛盾返回 `fengshui_calculation_inconsistent`，具体原因 `monthly_plate_inconsistent`，路径为 `runtime.fengshui.monthly_stars`；REST503、MCP错误、CLI退出1，非可重试。只投影状态也不能绕过。

离线 `verify_monthly_reading`先核上述内部关系，再核原始回执和完整固定文本。`derived_monthly_numeric_consistency_verified=true`仅表示确有完整月盘且这些数式成立。正确旧回执仍可核验，保存的同步错误回执被拒绝；缺月或交节候选没有唯一盘数字信用。`calendar_accuracy_verified`、自由模型正文、全书符合及现实预测标记仍为false，天文精度须另看独立比较。

正常生产结果、原 `position_reading@1.0.0`文字格式及公开Schema没有因新检查变化。它防止错误的派生结果被接受，不给原本正确的计算虚构额外准确率。

## 整个公开年份范围的分支验收

在执行前固定新协议（本地数据：`../tests/fixtures/fengshui_calendar_consumers_v1/protocol.json`），复用原10,104交点参考，取公开查询范围1801–2199的全部十二节，共4,788个事件。没有删掉旧参考的其他年份或中气，也不缩减其一秒数值验收。每个事件预定参考TT交点−10秒、交点、+10秒三个时刻，各配置14,364个查询；查询不从待测模型的交点生成。

主队列的显示时区固定UTC；UTC、上海、纽约、Lord Howe和Kiritimati的2026立春样例另作等价性检查，不把这些样例扩称全时区扫描。

TT转民用查询遵循同次冻结代码中的历史UT1／UTC与闰秒政策，再核查询换回TT的闭环。该做法只检查明确钟时政策下的软件分支，不认证历史实测UTC或未来实际闰秒。独立交点的采集定义来自[Skyfield节气文档](https://rhodesmill.org/skyfield/almanac.html#solar-terms)及固定JPL内核；[Swiss Ephemeris说明](https://www.astro.com/swisseph/swisseph.htm)也将Moshier列为近似模型，不能由其安装或求解成功推定精度通过。

每个查询核年盘和月盘；全部立春节界另核命卦与历史宅运。交点处要求保留两个节月，立春处也保留前后有效年；前后十秒要求选择参考对应的一侧并生成正确数字，且有效期包含查询时刻。同一宅运内，事件年待确认不强制抹掉可确定的宅运号；跨运时保留两个运数。

| 明确测试配置 | 消费端分支 | 同队列的一秒数值线 | 综合状态 |
| --- | --- | --- | --- |
| DE440 | 全部14,364查询通过；年／月各14,364次，命卦／宅运各1,197次 | 4,788交点通过，民用输出换回TT最大差约0.000121秒 | 本队列通过 |
| 原生、空星历目录且实际模型为Moshier | 同样没有错误唯一分支 | 保留569项超差，最大约2.455秒 | 不通过 |

两种配置的事件与预定时刻重叠；多个消费端又读取相同的年份／节月依据，不能相加为独立天文样本，更不是现实案例。原10,104交点、原421立春、原4,812十二节及其失败继续按原范围保留。Moshier这569项失败的身份与先前记录相同；五秒仍只是操作保护，没有改成五秒数值门槛。

可在新的输出目录重放完整队列：

```bash
uv run --locked --extra dev python scripts/audit_fengshui_calendar_consumers.py \
  --configuration de440 --output-dir /tmp/fengshui-consumers-de440
uv run --locked --extra dev python scripts/audit_fengshui_calendar_consumers.py \
  --configuration moshier --output-dir /tmp/fengshui-consumers-moshier
```

脚本按所选配置固定太阳模型并使用空外部星历目录，逐点记录实际模型、查询TT和钟时、决定与错误，不覆盖已存在的输出目录。Moshier应保留非零退出；完整队列未完成、原文数表变化或协议被缩短，都不能取得通过。这里是领域消费端验收；REST、stdio MCP、CLI、真实模型及部署须分别提供证据。
