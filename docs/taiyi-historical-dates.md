# 太乙选定课例的历史日期验收

V8将《太乙金钥匙续集》的两条课例接入实际公开日期入口，日期来源独立于太乙计算程序。验收限于选定日期及声明的现代适配，整体目标继续进行。

薛仲三、欧阳颐《两千年中西历对照表》1940年本（NTUL-9900013521F03），PDF第101页、印刷第313页给出嘉靖四十年十一、十二月的逐日日期及月首干支、星期。原页与指纹保存在独立日期材料（本地数据：`../tests/fixtures/taiyi_jinjing_v8/manifest.json`）。[中研院的历制说明](https://sinocal.sinica.edu.tw/)明确区分儒略历与格里高利历；1582年前的旧式西历标签不能直接作为推算公历输入。

| 原例日期 | 历表的儒略历 | 接口的推算公历 | 现代适配结果 |
| --- | --- | --- | --- |
| 嘉靖四十年十一月二十一日丁未 | 1561-12-27 | 1562-01-06 | 日计44日、44局 |
| 嘉靖四十年十二月二十二日丁丑庚戌时 | 1562-01-26 | 1562-02-05 | 第74日、积时887、23局 |

原书年号与西历跨年并不矛盾。两个独立月首另行核对：十一月初一儒略历1561-12-07、丁亥；十二月初一儒略历1562-01-05、丙辰。四条日期观察与完整课例的观察数分别报告。

公开验收明确用固定`+08:00`及钟表时间，避免把IANA历史地方平时误称现代东八区。日计12时只是当日的代表钟面；时计20时是原载戌时内的代表钟面。它们不补造古例地点或具体分秒，也不证明原书使用现代定气、零时或23时子初约定。输入始终为推算公历，转换函数不会猜测国家改历日期。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1562 --analysis-month 1 --analysis-day 6 \
  --analysis-hour 12 --analysis-timezone '+08:00' \
  --calculation-mode day --use-true-solar-time false \
  --fields taiyi.calendar_rules taiyi.core_board --strict-fields

uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1562 --analysis-month 2 --analysis-day 5 \
  --analysis-hour 20 --analysis-timezone '+08:00' \
  --calculation-mode hour --hour-profile key_hour_winter_jiazi_v1 \
  --use-true-solar-time false \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.wenchang_palace --strict-fields

uv run --locked --extra dev python scripts/audit_taiyi_historical_dates.py \
  --output /tmp/taiyi-historical-report.json
```

V8当时审计返回退出码1：日期四观察通过，日例34观察为28相符、4差异、2未决；时例20观察为16相符、3差异、1未决。V9采纳[十二支天时通则](taiyi-ten-jing.md)后，原日例34观察与匹配数不变，转为5差异、1未决，仍退出1。历表通过不能抵消原典的差异，也不能认证整部古历或全部断法。完整记录见历史重放报告（本地数据：`validation/taiyi-jinjing-v8/historical-report.json`）。

把时例儒略历1562-01-26直接当推算公历会得到767时、47局、文昌卯；正确转换后是887时、23局、文昌乾。两者太乙都在9宫，直门都为生门第17时。因此回归同时核对完整积数、局数和文昌，不能只用太乙宫、直门两个碰巧相同的字段证明历法正确。

匹配选定日期时，`calendar_rules.historical_date_reference`返回原日期、历制、转换日期、历表作者版本页码、原例与本次实际积数。不同时间导致不符时，返回的匹配标志为false；注释不会修改计算。此对象支持严格字段投影，并与同盘快照一起交付。三式合参沿用同一对象，不把三套输出合成概率或认证分数。

首读还分别核对业务与运行环境回执：仅`run_metadata.runtime`延后时，业务依据保留内联；环境复核从同一run取回完整清单。业务字段延后则先取回该字段再解释。V7/V8受控对照使用相同74种视图、相同业务结果和35个星历文件，只替换共享交付模块：业务完整内联由45/74变为74/74；29个分页引用仍保留，指向完整环境凭据。交付对照（本地数据：`validation/taiyi-jinjing-v8/delivery-comparison.json`）保留前后哈希与实际字段检查，测试不再以“没有分页引用”代替“业务完整可读”。

原典全文的差异裁定、完整历史历法、完整断法与真实模型自由解读盲测仍待完成。工程回归不认证现实预测效力。
