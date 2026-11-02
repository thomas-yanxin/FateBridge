# 太乙日计：积日、十精与正文／课式异数

`calculation_mode=day` 明确采用《太乙金钥匙续集》的冬至前甲子积日法，配置标识 `key_day_winter_jiazi_v1`。日数不乘十二，每三日移一宫；冬至后用阳局，夏至后用阴局。它与金镜年度十神、金镜至点置一时计、金钥匙完整积时分别标注来源，不能按吉凶选择结果。

## 历法与钟面

先以民用UTC瞬间判定是否已交冬、夏至，再按已选民用钟或真太阳钟的所属日期计算积日。日界明定为该钟面零时；同一日期23时不加日，不能套用时计23时子初。`calendar_rules.day_origin` 保存现代冬至UTC及提供者、所选钟面、甲子日、目标日干支和积日。共用四柱的边界与本日计日支分别说明，不把共用日柱代换进日计。

冬至所属日若为甲子，本配置将该日纳入起点，这是明示现代约定，古例仍未裁定。返回的 `alternative_strict_previous_count` 另列严格前一甲子的候选积日，不自行改选。两甲子日相距60日，而60不能整除72，因此会改变日计局序；上一轮时计相差720时的相位恒等式不能借来认证日计起点。

现代日期示例2026-02-02在这一配置下同属44日相位，可用于接口复现；不能据此声称已把嘉靖四十年十一月二十一日转换为该公历日期。V8已另用独立历表核对原例为推算公历1562-01-06，详见[历史日期验收](taiyi-historical-dates.md)；完整古历回算仍未完成。

## 丁未44日课例

[原书图39—43](https://upload.wikimedia.org/wikipedia/commons/1/19/NLC892-411999021066-66022_%E5%A4%AA%E4%B9%99%E9%87%91%E9%91%B0%E5%8C%99.pdf)及冻结读数（本地数据：`../tests/fixtures/taiyi_jinjing_v7/day-worked.json`）在生产实现之前分别记录正文和课式。主客二目沿实际十六神算路求和，定目以合神加日支，直门加定计目。

| 项目 | 正文 | 课式 | 本盘规则结果 |
| --- | --- | --- | --- |
| 主算 | 33 | 32 | 33 |
| 合神 | 午 | 三宫艮 | 午 |
| 八风 | 阴德乾 | 三宫艮 | 二宫起顺行九宫所得巽九 |
| 天时 | 十二辰规则及含巽的算路，落大武坤 | 七宫坤 | V9采十二支通则得酉；原坤读数单列不符 |
| 太乙数 | 四宫 | 甲子元第四十四局 | 局序44；宫位语义未裁定，位置null |

其余明确数值包括主大／参3／9、客大／参4／2、客算14、定计32与定大／参2／6、生门第14日等。三门主体仍未裁定，已布门不等于门具。V15起所选三值合取保留五将实际阻断，本例`menju_jiangfa=false`；`three_gates`仍为未知，不把合取false误写成三门不具。日计计神按前文明列的阴局起申；末段概括阴阳差异时未列计神，也仍需完整阴局古例核对。

V7当时审计结果（本地数据：`validation/taiyi-jinjing-v7/report.json`）保留34条数值／位置观察：32条可评、28条相符、4条分歧、2条未决。正文与课式对同一结果的不同读数均在分母中；它们不是独立案例，不能合并周期遍历数来提高“准确率”。该V7数值审计脚本退出1，不核历史日期；V8选定日期验收另列，全部断语与全书符合仍未认证。

## 十精

新结果 `ten_jing` 与年度 `long_cycles` 分开。天皇从申起、四维重留，地符从戌起、四正重留；飞鸟为九宫循环，天尊为子酉午卯，五行为乾子艮巽坤，八风为二至九再一，五风为一三五七九二四六八，三风为三七二六一五九四八。V9天时采寅起十二支规则，有年度余10在亥及金镜/统宗补证；日例坤与实际酉并列，详见[天时取法与完整十精补证](taiyi-ten-jing.md)。

阴局依原文取阳局所在的对冲方位；若阳局落中五，原文未给对冲或寄宫，阴局位置保持未知。太乙数只给局序，不强行当宫位对冲。未知星位不填入宫位标记，原典未实现的天气或事件断语不由模型补写。

两项日计专用视图 `daily_calendar`、`daily_essences` 要先选择day。十精首读保留位置、未知理由和异文，完整顺序、周期在同一run的 `taiyi.ten_jing.records` 续读。它们不是其他计法的默认视图。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 2 --analysis-day 2 --analysis-hour 12 \
  --analysis-timezone Asia/Shanghai --no-use-true-solar-time \
  --calculation-mode day --strict-fields --response-char-limit 0 \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.day_source_comparisons taiyi.ten_jing
uv run --locked --extra dev fatebridge sanshiunited \
  --date 2026-02-02 --time 12:00:00 --zone Asia/Shanghai \
  --taiyi-options '{"calculation_mode":"day"}' \
  --no-use-true-solar-time --strict-fields --response-char-limit 0 \
  --fields taiyi.calendar_rules taiyi.core_board taiyi.day_source_comparisons taiyi.ten_jing
uv run --locked --extra dev python scripts/audit_taiyi_day.py \
  --output docs/validation/taiyi-jinjing-v7/report.json
```

日计不接受 `hour_profile` 或合参的rotation覆盖。REST、MCP、CLI共享日计实现。仍须按完整验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续完成古历范围、来源分歧、全盘断法与真实模型解释验收。

核对金镜梁天监三年古例时，另读[古日计历法与积数](taiyi-day-epoch.md)。当前金钥匙积日和金镜上元累计数不是同一定义，不以“都是日计”默认可比。史历表日期与王氏同元四分历的关系仍未裁定；给定原积数重放两个宫位不能代替从原日期求出积数。明列阴局计神起申与末段摘要省略分开保留，不从省略推出当前算法应改用阳局。

首读先核对 `result_delivery.deferred_fields`。仅 `run_metadata.runtime` 延后时业务依据仍内联，环境复核再取回完整运行凭据；业务字段延后则从同一run读取 `first_page_uri` / `next_uri` 并核对SHA-256后解释该字段。内联业务完整性与完整凭据恢复分别验收。

V8补充：[选定历史日期与完整公开重放](taiyi-historical-dates.md)，保留本次全部源文差异与未决项。

V9补充：[天时十二支规则与完整年度十精参照](taiyi-ten-jing.md)。原日例仍是34要求、28相符，天时从未知转为不符，现为5差异、1未决；不提高匹配数。

V45补充：[冬至起元的计数起点与选元切换](taiyi-origin-activation.md)。计数基准日与冬至实刻选元分列，原典年度启元及同日甲子仍未裁定，既有数值策略不变。
