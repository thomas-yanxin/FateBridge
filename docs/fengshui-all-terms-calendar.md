# 全部24节气的独立TT验收

[历史宅运覆盖](fengshui-historical-calendar.md) · [日时选表的未决条件](fengshui-day-calendar-selection.md) · 冻结协议（本地数据：`../tests/fixtures/fengshui_all_terms_v1/protocol.json`）

立春通过不能替代其余23个节气。第三十四轮独立收集1784–2204年全部24节气，共10,104个交点，覆盖历史宅运端点及日时研究所需的中气。原421个立春与4,812个十二节协议、参考表、门槛和失败均保留。

先固定全部年份、全部节气、每月两个搜索区间和1秒TT门槛，再调用[Skyfield官方节气接口](https://rhodesmill.org/skyfield/almanac.html#solar-terms)。收集器不导入FateBridge，用完整JPL DE440和40次向量二分，记录Skyfield1.53、jplephem2.24、numpy2.2.6及其他实际依赖。参考资料在新增校验器和候选运行之前冻结；不是盲测或前瞻预测数据。

参考文件SHA-256为`ab7ddadaa02e0fd71b3049c3146f3ec5bae01441309356372b9668c65afab371`，协议为`0d81e9f0f564c3c4d44a08a15d8fb0495ba33f053183c80580dd630e3c13a0dd`。完整内核及其SHA-256沿用[上一轮来源记录](fengshui-historical-calendar.md#来源与选用范围)。原始收集器副本（本地数据：`../tests/fixtures/fengshui_all_terms_v1/collector.py.txt`）和捕获清单一并保留；重算清单散列不能替换这份已经冻结的参考。

## 比较实际输出

审计实际调用风水`solar_term_resolution`，保留每项模型、钟时政策和完整来源。对具名数值模型同时验证两个对象：原始`selected_crossing_jd_tt`与实际输出钟时重新换算的TT；其中一个正确不能遮盖另一个错误。近似回退、未知来源、来源错误或缺失原始根均不能取得对应通过。两个对象均沿用1秒门槛，五秒候选保护不参与精度评分。

| 本轮路线 | 实际模型与结果 |
| --- | --- |
| 无外部严格JPL配置的默认auto | 原打包DE440模型9,624项，历史扩展480项；全部10,104项在1秒内 |
| 显式native、空星历路径 | 全部实际返回Moshier；8,908项通过，1,196项失败，最大差约2.608秒 |

默认路线原始TT根的最大差约0.000081秒，输出钟时换回TT的最大差约0.000121秒。这是两套软件读取共同JPL轨道资料后的实现差异，不是天文观测误差上界。历史UT1／ΔT约定及未来闰秒假设继续保留，不能把该数字宣传成绝对UTC精度。

Moshier控制组包含原4,812个十二节样本的569项失败，以及原421个立春样本同样46个失败年份；不会因默认模型通过而撤销它们。自动配置变化、显式解析／SPK或严格JPL另行选用的路线没有自动取得本轮成绩。公开请求年份没有扩张。

## 复现和范围

在源码环境生成新的报告；失败路线按原门槛退出1：

```bash
uv run --locked --extra dev python scripts/audit_fengshui_solar_terms.py \
  --output /tmp/fengshui-all-terms.json
FATEBRIDGE_SOLAR_TERM_MODEL=native SE_EPHE_PATH=/absolute/empty/directory \
  uv run --locked --extra dev python scripts/audit_fengshui_solar_terms.py \
  --output /tmp/fengshui-all-terms-native.json
uv run --locked --extra dev python -m pytest -q tests/test_fengshui_solar_terms.py
```

运行控制组前须确保没有另配置`FATEBRIDGE_JPL_FILE`，并检查报告的实际模型。输出路径存在时脚本拒绝覆盖。独立重新收集需要原内核和固定研究依赖，可用`build_fengshui_all_terms_reference.py --kernel ... --protocol ... --output ... --check`核对冻结表；不加`--check`则必须指定新输出路径。

本轮没有改变生产求根数式、轨道资料、公开工具或原典选表。日时表仍缺完整适用条件；2026年245日多解及6月19日反例继续保留。数值通过不能给原典全本、自由模型解释或现实预测授予通过。测试、冻结输入、各轮失败及平台范围见第三十四轮证据（本地数据：`validation/fengshui-all-terms-v34-evidence.json`）。
