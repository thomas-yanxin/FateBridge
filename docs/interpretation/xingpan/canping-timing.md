# 参评配运与原典依据

[取证入口](numerology.md) · [计算口径与复核](../../numerology-audit.md)

配运问题先按公开`timing_policy`视图保留本命和同次首行，再解释所查阶段。不要因`first_period=null`或没有查询时刻就漏掉有实际编号、年龄标签和可读条文的`first_row`。

实际年界据`solar_year_context`、同次边界和模型回执解释。封装DE440独立年表当前登记1700—2300年；附法与连续法在该范围端点的完整120年序列另有具名有界立春许可，包括1700年立春前所需的1699年界及上端至2420年的派生年界。这不扩大独立年表范围，不改所选配运法或认证原典／未来UTC；显式其他模型与严格原生JPL仍按各自实际来源和范围，不因同属邵子工具就套用这一许可。

同次`schedule_basis.reading_context`汇总本次方法、钟制日期条件及已连接的书名／版本／书影、页码和引用角色，可与原始`sources`、`clauses`核对后用于解释。地区规则的未来落点、显式固定偏移假设和旧法无实际日期映射分别说明；不将统一的未来地区条件套给所有方案，也不因信息汇总而提升原典或预测认证状态。

向用户给出配运起止日期时，将本次`date_mapping_statement`的适用条件与日期一起交代；已读到条件不表示答复已经交付该条件。来源解释分别回答某个步长在哪部书出现、该原句在本次方法中是否采用：书中出现的数值和`applied_clause_ids`／`role`是两项依据。旧法的另书对照保留其具体子平背景，仍不产生旧法日期认证；不把书目名称或“程序设置”当作已说明步距来源。

按所选`schedule_basis.profile_id`及`applied_clause_ids`解释起运方向、折算和落点；连续法未执行整数借除，旧法不借附段认证实际日期。对`schedule_basis.clauses`中的方法区别原句，交代各自对象、阳／阴对应的年数及本次`role`，不将别种大运制度混为本次方法。

每条引文用其`source_id`连到同次`schedule_basis.sources`，将书名、可核对版本或唯一书影链接／对象ID、PDF或印页放在该引文旁。目录标注而未独立核定的印年继续明示，不能猜一个年份补齐书目；只列书名或页码也不能识别是哪一份书影。现代日期映射另据`calendar_mapping`、`age_conversion_result`和`future_clock_policy`解释。

参评明确出生时刻、时区和已知性别，不能默认男命。`method=gu` 用真实日支，显式 `ming` 是月支变法。配运另由 `dayun_method` 控制，默认 `bazi_appendix_v1`；连续折算和旧命宫方案各有名字。核对实际 `canping_timing.profile_id`、政策和来源，不把具名附法说成卷六唯一排法，也不把它混称河洛六九年卦运。

配运核对先按公开`timing_policy`视图取同次`schedule_basis`、`first_row`、`first_period`与`selected`。`first_row`保留同次`dayun[0]`的实际编号、岁运栏及条文，旧法也有首行年龄标签；旧法`first_period=null`只表示无已核日期首运，不表示无首行。现代日期首运与`first_row`的已返回事实须一致；两种首行摘要都不能代替查询当段；全运再读`periods`，完整立春另读`calendar_boundaries`。`schedule_basis.clauses`按`role`区分实际完整采用的目标附段、来源语境与另书子平背景；`applied_clause_ids`不能跨方法套用。卷七原段的整数借除与实际`calendar_mapping/age_conversion_result`分开；连续法未执行该整数条，legacy没有已核实际日期。引用原句交付各自书名、版本与页码，《三命通会》十年文字不能冒充所核河洛附段明载。结合实际`future_clock_policy`和验收布尔状态说明日期与证明范围。

显式旧命宫方案的流年也按实际出生年柱对应的年标签起排；立春前首行可标上一公历年，并非更改出生日期。核对`liunian_series.birth_pillar_year/year_boundary/age_policy`，不把标签年龄当作已核UTC区间。

需要核对参评替支本身时，`canping_luck_substitution_v1`来源轨迹给出所选本PDF64释文及实际查询配对；无查询时`query_pair=null`，不从第一运补当前配对。原生日支／时支、流年太岁和当段运支分别核对，部别仍取出生年纳音。固定四柱Python函数的相对年序不是出生接口新模式，也不能把未知公历年补成某个甲子年。

实际时刻查询用带时区 `analysis_datetime`，读取同次 `canping_timing.selected` 与 `numerology_evidence.selected_texts`；`not_started` 不生成流年编号和断语，不取第一运代替。年行 `status=split` 时必须按 `segments` 的实际边界解释，不能把其中一段扩成全年。120行是干支年序覆盖，`age` 不是寿命或精确周岁；日期显示不能提升出生资料精度或原典应期精度。
