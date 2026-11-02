# 金钥匙月计：天地二正、节月适配与门数差异

`calculation_mode=month`可明确选择`month_profile`。默认`jinjing_month_jie_360_v1`保留金镜六纪节月起元；新增`key_month_tianzheng_jie_v1`采用金钥匙的完年乘十二、加天地二正及当月名义序。二者预先选择，不按门值或课例匹配程度自动切换。

默认金镜配置从`calendar_rules.month_origin`交付大雪公历锚年`cycle_year`、实际所求名义年`counted_year=cycle_year+1`、祖积年与十二节月单位。V39修正了重复减年，积月比旧默认增加12，实现版本为1.2.0；此前1.1.0“数值相位保持”的说明只适用于那次回执补充，不能继续描述当前计算。`source_year_label_adjudicated=false`保留完整古历年界尚未裁定的范围，不否定已经补证的局部起元修正；节月积数不能当作章岁章月求日计经朔的累月。金钥匙已有回执另行保留。来源及完整月序诊断见[节月、经朔累月与年标](taiyi-month-count-domains.md)。

[《太乙金钥匙续集》图36—38](https://upload.wikimedia.org/wikipedia/commons/1/19/NLC892-411999021066-66022_%E5%A4%AA%E4%B9%99%E9%87%91%E9%91%B0%E5%8C%99.pdf#page=36)以弘治十七年1504甲子截元，嘉靖四十年1561辛酉为第58年，减一得57，乘十二为684；加天地二正及九月，共11，得695个月。原例由此入335周、壬子元47局，太乙巽九第二月，文昌卯四，计神辰，始击丑，主客算4／8，定计目戌、定算17及大／参7／1。

实现使用原书年度祖数10155478，先减完年，再乘十二并加月序，得到完整积月121865735。它与截数695相差121865040，是720的整数倍；720为所用12、18、24、72、240、360周期的公倍数，因此该截法保留这些数值相位。1504年前截数可为负，实际起局使用正的完整积月，不把负截数直接当积月。

## 月名、朔月假设与现代节月分别核对

本配置仍以现代天文十二节月为边界，寅月切换名义年标签，不是完整古历、原书岁首或所有历史月份的复原。原例只写“九月戊戌”，不足以单独证明采用朔月；《金镜》卷一另有按逐月节气时刻为正的明文，也不能直接替金钥匙裁定。上轮将历表九月称为“原例农历月”的表达过强，本轮更正解释，保留原计算、历表事实及不匹配结果。

薛仲三、欧阳颐《两千年中西历对照表》1940年本、印刷第313页独立载明：嘉靖四十年九月初一为儒略历1561-10-09，即推算公历1561-10-19、戊子；十月初一为儒略历1561-11-07，即推算公历1561-11-17、丁巳。冻结来源（本地数据：`../tests/fixtures/taiyi_jinjing_v10/manifest.json`）保留原图、月首干支与星期。

代表日期1561-10-20在该农历九月与现代戌节月的交集内；正午、固定`+08:00`只是接口验收钟面，不补造原例地点、日时。1561-11-10仍属历表农历九月，但现代节月已经进入亥月，名义序为10。`month_origin.calendar_reference`继续返回`month_label_matches=false`及`counter_matches=false`，同时明确`comparison_hypothesis=original_month_label_as_lunar_month`、`source_calendar_basis=not_adjudicated`。它否定“节月适配全程等同该历表朔月”，尚不能证明原例必用朔月，亦不能证明原书边界已复原。

## 门段三种读数不能择优

| 输入或阶段 | 按240门周的结果 | 性质 |
| --- | --- | --- |
| 前段695积月 | 余215，惊门第5月 | 本盘沿连续积月通则 |
| 门段所写684积月 | 余204，死门第24月 | 原输入的算术诊断 |
| 门段所报余184 | 死门第4月 | 原文门值所对应的阶段 |

原段还写再行26月方足，随第4月可算满30月；本盘第5月则剩25月。实现不改原文684／184／死4，也不为匹配原例挑选其中一个输入。`gates.source_comparisons`保留5项差异；`source_counter_alternatives`仅作诊断，明确不能替换本盘所用积数。课式只写“壬子元第四”，缺完整局数，该来源要求仍未评估；实际计算所得47局照常返回。

本配置将直门加定计目。太乙主客三门核对主体仍未独立裁定，返回`not_assessed`。V15起两层合取保留五将实际阻断：若五将明确不满足则`menju_jiangfa=false`，否则为null；两者都不证明三门已核定，不借用王法的太乙／文昌判断补齐。金镜年度十神也不会混入此月盘。

## 八门扇区的既有错误

旧代码把每个正宫及后一个间神均分成两神一组，导致丑归坎八、辰归震四、未归离二、戌归兑六。[《金镜》卷二](https://zh.wikisource.org/zh-hant/太乙金鏡式經_(四庫全書本)/卷02)明确辰巳属巽九、戌亥属乾一；卷九的未申西南与东北对冲及四钩方位补证支持四维归宫。修正为丑艮寅归三、辰巽巳归九、未坤申归七、戌乾亥归一，子卯午酉分别独占其正方。推论范围与全部16神见独立参照（本地数据：`../tests/fixtures/taiyi_gate_sectors_v1/sectors.json`）。

这项修正影响所有已计算太乙门盘的间神归宫、定计目门盘与三门判断，门法规则版本更新为1.1.0；不改变二目算路中“间神起一”的数值，不改变三式四维寄支的未决状态。1900—2099年受控对照有44年落门改变、5年三门判断改变；它们是软件影响范围，不是200个独立古例或预测样本。

## 验收与调用

月段29要求为28可评、23相符、5差异、1未决；两个月首日期事实单独核对。既有V5四课例32字段、门表36要求继续保留并报失败，不把新组并入分母提高匹配率。月计报告（本地数据：`validation/taiyi-jinjing-v10/report.json`）仍退出1；扇区报告（本地数据：`validation/taiyi-jinjing-v10/sector-report.json`）只通过16神八方几何，不代表全书通过。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 1561 --analysis-month 10 --analysis-day 20 --analysis-hour 12 \
  --analysis-timezone '+08:00' --no-use-true-solar-time \
  --calculation-mode month --month-profile key_month_tianzheng_jie_v1 \
  --strict-fields --fields taiyi.calendar_rules.month_origin taiyi.core_board taiyi.gates.counter taiyi.gates.source_comparisons
uv run --locked --extra dev python scripts/audit_taiyi_month.py --output /tmp/taiyi-month.json
uv run --locked --extra dev python scripts/audit_taiyi_gate_sectors.py --output /tmp/taiyi-gate-sectors.json
```

三式合参把两个选项放入`taiyi_options`。`monthly_key_calendar`视图仅适用于此月计配置，首读包含起元、截数、历史月序比较与门段差异；完整 JSON 仍从同一run续读。完整古历、全部断法、真实模型自由解读及部署验收继续追踪在总清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）。
