# 金钥匙冬至起元的计数起点与选元切换

当前金钥匙日计与明确选择 `key_hour_winter_jiazi_v1` 的时计，先选输入瞬间已经过的最近冬至，再取该冬至所选钟面所属日或此前甲子。下一冬至前的甲子即使已经开始，当前算法也不会提前选用尚未到达的冬至。本次不改变这套数值算法；原典年度启元时点仍未裁定。

`origin_effective_date` 是计数基准日，时计的 `origin_clock` 是所选钟面子初标签。它们与每年选择下一冬至起元的切换瞬间不同：日计的计数基准是零时，时计采用23时子初，当前选元切换则发生在冬至实刻。因此冬至当天也可能在实刻前后换用不同起元，不能从基准日名反推程序在该日零时就已切换。

同次结果新增 `taiyi.winter_origin_selection`，复制本盘已用的冬至UTC标签、计数起点钟面、钟面类别与原书来源。`selection_switch_basis` 是 `winter_solstice_instant`，`classical_activation_adjudicated=false`。该对象不重新求节气、不另算一盘，也不认证古代UTC标签或物理精度。确定性快照与导出各保留同一条“冬至选元约定：”说明。其他年、月及默认至点时计不附这份起元说明。

[《太乙金钥匙续集》原文](https://www.shidianguji.com/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8)日计给出冬至前甲子积44日，时计给出74日887时；另论二至后阴阳局。图39、44书影和此次核读条目见冻结来源（本地数据：`../tests/fixtures/taiyi_origin_activation_v45/source-readings.json`）。此前独立史历表映射及本轮声明的现代定气重放中，这两例都在相应冬至之后，不能裁定冬至之前启元的算法；这也不证明原书古代冬至实刻。[前集求时计条文](https://www.shidianguji.com/book/NGJ89241199902106666022/chapter/1lq8dkvlnkx7u)另列不同正法与捷法，本轮不把它们拼接成续集启元结论。冬至同日甲子取法与完整古历仍保留未决。

在假定相邻冬至所属钟面日期相距365或366日的条件下，60种日相位共120个整数对照，前甲子基准可相距360日（109例）或420日（11例）。420日对360日公周期差60，不能把全部日计起元视为同相位。对应时计差4320或5040时，均被720整除，已实现周期位置虽可相同，完整积时及已过周期数仍不同。这是条件数学对照，新增独立古例、物理观察和原典启元裁定均为0。

首读可选命名视图 `winter_origin_selection` 所发布的字段；视图名不是请求参数。仅对上述两种配置使用，保持 `strict_fields=true`。原日计、时计视图没有被改成新视图。实际输入示例是虚构的工程核对：

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 12 --analysis-day 21 --analysis-hour 12 \
  --analysis-timezone UTC --no-use-true-solar-time --calculation-mode day \
  --fields taiyi.winter_origin_selection taiyi.solar_anchors.winter_origin \
  --strict-fields --response-char-limit 0
uv run --locked --extra dev python scripts/audit_taiyi_origin_selection.py \
  --output /tmp/taiyi-origin-selection-report.json
```

96个独立民用日期整数参考用于检查当前声明策略，天文冬至沿用相同Swiss轨道数据谱系，不是96次独立物理观测。另有32个真太阳钟面同盘来源检查，不据此声称新增太阳时独立真值。V45记录（本地数据：`validation/taiyi-jinjing-v45/README.md`）分别列改前数值、说明缺口、修复后协议检查与原失败；总验收要求（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续为未完成。
