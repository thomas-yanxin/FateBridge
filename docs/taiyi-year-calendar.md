# 太乙年计：输入农历、两种钟面与历史历表

年计按输入钟表日期确定农历年，真太阳时校正不会改写这个日期。`calendar_rules.civil_lunar_calendar`保存本次年计实际使用的年、月、日、闰月、输入日期及换算来源；`calendar_summary.used_lunar_date`提供首读日期。它们直接复制同一次换算结果，解释时不另算一份农历。

`analysis_context.input_datetime`是输入钟时，`corrected_datetime`是所选算法的计算钟面。通用`analysis_context.lunar_display`及`calendar_context.lunar_calendar`仍属于校正钟面的时间上下文，不能据此替代年计日期。例如虚构输入2026-02-17 00:05、固定`+08:00`、经度0、真太阳时，年计采用2026年正月初一；校正钟面落在2月16日，其上下文农历为腊月廿九。两者用途不同，快照分别标明。这个例子验证日期绑定与解释，不独立验证太阳时天文精度。

`provider=shared_offline_lunar_calendar`表示共享离线管线，含已发布的校正与边界历表。`conversion_source`只复制本次提供者实际返回的来源：1900年1月前缀保留紫金山天文台《1900—2025年日历》及清《时宪书》约定；2100年补充保留香港天文台月首历表。普通日期未单列来源时返回null和`not_reported_by_calendar_provider`，不补造逐日权威认证，也不宣称所有时区都得到独立天文验证。

核对年计可复制`year_calendar`视图的fields；三式用`taiyi_year_calendar`，并明确`calculation_mode=year`。两视图都保留两种钟面、实际年计日期、规则及来源，兼容下述明确选择的历史历表。视图名不是调用参数。三式父级的时间上下文也不替代太乙日期，奇门和六壬继续采用各自规则。

命名时区的重复钟面可通过`analysis_utc_offset`明确选择，实际UTC、偏移和回拨序号随本次回执保存，见[民用时刻核对](taiyi-civil-clock.md)。此选择不改变年计以实际输入民用日期定年的规则。

## 明确选择历史历表

目前可明确选择两套互不外推的史历表：`jinjing_year_historical_table_v1`为381—385晋历，`jinjing_year_qiliang_table_v1`为501—505齐梁主表。默认现代农历保持；不按输入年代自动改配置。

`calculation_mode=year`新增显式配置`year_profile=jinjing_year_historical_table_v1`。它依据薛仲三、欧阳颐《两千年中西历对照表》1940年本，重建381—385年晋历主表的完整五年。覆盖62个月、1831日，另保留386年正月月首作为不含的终界；范围外拒绝，不自动套用现代农历。默认配置及其原有支持范围保持不变。

来源为[国立台湾大学馆藏扫描F01](https://commons.wikimedia.org/wiki/File:NTUL-9900013521F01_兩千年中西曆對照表.pdf)印刷77页及78页首行。原图、人工转录、凡例和指纹在V12冻结清单（本地数据：`../tests/fixtures/taiyi_jinjing_v12/manifest.json`）。先冻结整页五年，再实现适配，未挑选只有太乙古例所在的385年。

| 晋历年份 | 原表儒略历正月初一 | 推算公历岁首 | 闰月 |
| --- | --- | --- | --- |
| 381 辛巳 | 381-02-10 | 381-02-11 | 无 |
| 382 壬午 | 382-01-31 | 382-02-01 | 九月 |
| 383 癸未 | 383-02-19 | 383-02-20 | 无 |
| 384 甲申 | 384-02-08 | 384-02-09 | 无 |
| 385 乙酉 | 385-01-27 | 385-01-28 | 五月 |
| 386 丙戌，仅终界 | 386-02-15 | 386-02-16，不含 | 未扩展 |

## 501—505齐梁史历表配置

`year_profile=jinjing_year_qiliang_table_v1`使用同书[馆藏F02](https://commons.wikimedia.org/wiki/File:NTUL-9900013521F02_兩千年中西曆對照表.pdf)印刷101页完整501—505五年及102页506年正月终界，覆盖62个月、1831日；范围为推算公历0501-02-06至0506-02-11之前。原读数与全部书影在V35冻结（本地数据：`../tests/fixtures/taiyi_jinjing_v35/freeze.json`），本次服务接入及回归范围在V36记录（本地数据：`validation/taiyi-jinjing-v36/README.md`）。

该配置忠实保留原表502闰四月、505闰二月。502年有元嘉中气归属诊断的闰五月／六月异说，尚未裁定，随`historical_calendar.source_disagreements`交付；`adjudicated=false`和`affects_selected_year`分别表示尚未裁定与本次是否处于该年。快照同源说明，不能把读表成功写成置闰算法或原典已经通过。

例如固定`+08:00`、直接钟面正午，推算公历0502-05-24对应原表502年闰四月初一；0504-07-07对应504年六月初八癸未。后者仍不等于金镜原书初八甲申、上元积日707501061或完整原盘已恢复。年计使用此历史年，日／月／时计不接受本配置，也不将该民用月份替换为太乙节月。详见[不同历法的完整比较](taiyi-yuanjia-calendar.md)。

`historical_calendar.profile_id`明确标识齐梁配置；`year_label_basis`说明显示的年度来自原表年栏，不推定逐日朝代移交或改元时刻。原儒略历月首、推算公历区间、作者版本、页码、数据SHA-256与未裁定范围均保存。三式仅其太乙年计采用该表，奇门、六壬仍按各自实际配置；另两术及共同古历时刻未因此认证。完整JSON继续读取同一run的交付物，不拼接来源。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 504 --analysis-month 7 --analysis-day 7 --analysis-hour 12 \
  --analysis-timezone '+08:00' --no-use-true-solar-time \
  --year-profile jinjing_year_qiliang_table_v1 \
  --strict-fields --fields taiyi.calendar_rules.historical_calendar taiyi.calendar_summary
```

三式将配置置于`taiyi_options.year_profile`，并保留`calculation_mode=year`。两种历史配置都可使用已有`historical_year_calendar`视图；省略配置、越界或与日／月／时计混用均不能自动回退。

## 对准确度的实际影响

历史年不能直接取公历年或四柱年。在推算公历385-01-27，原表仍属384年；385-01-28才进入乙酉年。年计分别为69、70局。把原表儒略历“385-01-27”原样输入公历字段，会落在前一年，这不是仅影响显示格式。

385年闰五月始于推算公历6月25日，因此7月1日为闰五月初七。这里的历史日期从原表月首间隔取得，不用现代天文农历倒推，也不把闰月当第十三个普通月重新编号。四柱继续使用独立的现代节气与所选钟面规则；太乙年界不随真太阳钟跨日改变。

`calendar_rules.historical_calendar`保留原儒略历月首、推算公历月首和次月首、当前历史年/月/日及闰标记、岁首区间、来源作者版本、原印星期/干支基数和数据指纹。通用`calendar_context.lunar_calendar`仍可能为空：此配置只扩展太乙年计，不伪造通用农历提供者已支持古代日期。单术快照标明历史历表日期；三式快照与`synthesis.limitations`说明另外两术仍采用各自现代适配，不认证三式共同古历时刻。

凡例另说明：原表Week与Cycle是加农历日序的基数。星期日零基为`(Week + day) % 7`；甲子一基为`(Cycle + day - 1) % 60 + 1`。只在月首时，这两个原印基数恰等于星期一零基与甲子零基，不能原样推广到非月首。完整1831日重建逐日核对这两个约定。

## 尚未完成的部分

这是指定史历表区段的离线日期映射，未重建古代天文常数、平定气朔算法、地点钟制或全年历算引擎。中研院[岁首调整说明](https://sinocal.sinica.edu.tw/luso_v2.html)列出子正、丑正及并立政权异历，因此晋历主表不能当作所有王朝的统一日期。太乙原典是否以该岁首切换年计，仍待独立条文与边界古例裁定；`year_boundary_status`明确保留此限制。

[正宫提挟](taiyi-enclosures.md)的太元十年乙酉古例，现在可以通过所选历史年配置进入公共入口。原例只载年度，没有给出具体日期、地点；7月1日正午固定`+08:00`是接口验收代表输入，不是恢复出来的原例时刻。原V11的11项宫数及2个主体保留，不重新计为另一条独立古例。全部原典差异和总目标清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）继续适用。

## 调用与验收

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 385 --analysis-month 7 --analysis-day 1 --analysis-hour 12 \
  --analysis-timezone '+08:00' --no-use-true-solar-time \
  --year-profile jinjing_year_historical_table_v1 \
  --strict-fields --fields taiyi.calendar_rules taiyi.core_board taiyi.enclosure_assessment
uv run --locked --extra dev python scripts/audit_taiyi_year_calendar.py \
  --output /tmp/taiyi-year-calendar.json
```

三式把该配置置于`taiyi_options.year_profile`。`historical_year_calendar`视图须先明确选择该年计配置，首读保留日期事实、来源和限制；视图名不是请求参数。审计分别报告63个月首、62个月区间、1831日重建及原古例重放；局部区段通过不代表全古历或全书通过，脚本仍退出1。

V27另用事先冻结的三例机构历表（本地数据：`../tests/fixtures/taiyi_jinjing_v27/freeze.json`）验证现代年计的边界来源与文字绑定，见记录（本地数据：`validation/taiyi-jinjing-v27/README.md`）。这三例不是新增古例，不能与1831日区段重建相加为总体历法准确率。
