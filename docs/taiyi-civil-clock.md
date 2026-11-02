# 太乙民用时刻：明确偏移、重复钟面与真太阳钟

太乙单术支持可选的`analysis_utc_offset`。它与`analysis_timezone`及输入年月日时分秒共同校验：保留命名时区，以明确偏移选定实际瞬间。偏移格式为`±HH:MM`或`±HH:MM:SS`，不能替代日期，也不能让不存在的当地钟面变得有效。

例如，纽约2026年11月1日01:30出现两次。`America/New_York`配`-04:00`选择05:30 UTC，配`-05:00`选择06:30 UTC；不提供偏移仍报歧义，`-06:00`则因不一致而拒绝。年、月、日、时配置均可使用该参数。省略此参数时不新增消歧回执。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 11 --analysis-day 1 \
  --analysis-hour 1 --analysis-minute 30 \
  --analysis-timezone America/New_York --analysis-utc-offset=-05:00 \
  --calculation-mode hour --hour-profile key_hour_winter_jiazi_v1 \
  --no-use-true-solar-time --strict-fields \
  --fields analysis_context taiyi.calendar_summary taiyi.calendar_rules
```

## 两个入口的输入含义

太乙单术的钟面、命名时区与偏移必须相互一致。三式合参已有的ISO带偏移`time`表示实际瞬间，再转换到`zone`；例如`time="05:30:00+00:00"`、`zone="America/New_York"`可转为当地第一次01:30。三式不新增`taiyi_options.analysis_utc_offset`，也不把ISO转换说成相同的钟面联合校验。

V29修复了三式月／日／时计在实际瞬间已经消歧后，领域层再次按未消歧钟面拒绝的缺陷。四个明确回拨输入、四种默认模式的修复前重放中，年计4项有效，其他12项误拒；修复后16项均有效。太乙单术复用共享民用时刻解析器，并附下述可追溯回执。

## 回执和解释

提供偏移且校验成功时，`taiyi.calendar_rules.civil_clock_resolution`及`calendar_summary`同名项记录实际输入钟面、命名时区、声明／采用偏移、`fold`和`instant_utc`，以及本次时区规则提供者；命名时区记录版本与TZif指纹，固定偏移只记录显式偏移提供者。`fold=0/1`区分回拨的第一次／第二次；普通时刻规范为0。快照使用同一回执，不在渲染时重新选择瞬间。首读可复制已发布`clock_basis`视图的fields，视图名不是请求参数。

重复钟面对应两个不同瞬间，不要求所有计数必定不同。民用标签计数仍按其声明的适配；真太阳钟按实际UTC、经度和均时差产生，可能跨时支、跨日。年计实际农历日期仍由[输入民用日期](taiyi-year-calendar.md)确定，不随太阳钟跨日改写。

纽约2026年3月8日03:30是有效民用时刻；以经度−74计算的太阳钟约为02时，不能因当地民用02时处于跳时缺口而拒绝这个太阳钟标签。校验对象是实际输入的民用时刻。反之，输入当地02:30配`-04:00`或`-05:00`均无效；阿皮亚2011年12月30日整日被跳过，也不能借明确偏移强行补出一盘。

节气锚点与民用时刻消歧是两层验证。新增[2025—2027太阳源与换局控制](taiyi-solar-boundaries.md)以分钟刊载值比较时刻，再检查前后边界，不据此认证原典古历或真实秒级精度。

## 来源和验收范围

控制来自[IANA北美规则](https://data.iana.org/time-zones/tzdb/northamerica)、[大洋洲规则](https://data.iana.org/time-zones/tzdb/australasia)和[亚洲规则](https://data.iana.org/time-zones/tzdb/asia)，本轮冻结版本（本地数据：`../tests/fixtures/taiyi_jinjing_v29/version`）为2026e。七个有效、六个无效输入在参数实现前封存了预期UTC、回拨序号或拒绝类型，包含纽约一小时回拨、豪勋爵岛半小时回拨、上海历史秒级LMT和跳日。完整文本及冻结顺序见V29记录（本地数据：`validation/taiyi-jinjing-v29/README.md`）。

这是所选时区规则的输入与计算一致性验收。IANA本身提示其记录可修订；运行回执报告实际环境，不能用一次冻结版本认证所有时期、地点或未来法律。上海LMT控制只核该规则的秒偏移，不认证古代地方钟制。太阳钟控制验证输入瞬间和标签边界，不提供新的独立秒级天文精度结论。

本轮未增加完整有日期古例、古历提供者、原典符合通过数或独立模型调用；全部既有原典差异及总目标（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续保留。软件协议通过不代表完整古历、自由解释或现实预测已经通过。
