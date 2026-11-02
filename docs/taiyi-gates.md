# 太乙八门、三门具与定计的来源范围

年计和月计新增 `taiyi.gates` 与 `taiyi.determinate_calculation`。计算沿用本次太乙盘，来源、门盘锚点、逐项落门和定算路径都可以继续核读；三式合参返回相同太乙结果。这不完成古历时实、全书断法或现实预测验证。

## 门盘不能混用

王希明[《太乙金镜式经》卷一](https://zh.wikisource.org/wiki/太乙金鏡式經_(四庫全書本)/卷01)另立年计新术，240年一周，每门30年，开、休、生、伤、杜、景、死、惊依次行。年计采用与本盘相同相位的起元，724年积数3361；计数含首年，故第30年仍在开，第31年转休。月计用本盘连续节月积数，每门30月，不能先约去360再求240的门周。月界仍为明确标注的现代节月适配。

`selected_profile` 预先固定：年计 `wang_annual_240`、月计 `wang_month_240_with_modern_jie_adapter`。所直门加本盘太乙宫，沿乾、坎、艮、震、巽、离、坤、兑八方布门。太乙宫数不是洛书宫数，也不能按数值1至9的次序布门。

李淳风常开法列为 `old_open_frames`：开门分别加太乙、主大将、客大将、定计大将。前三盘的核对主体据[《太乙统宗宝鉴》卷二](https://www.shidianguji.com/zh/book/CADAL02055529/chapter/1l5erjww44w8a)分别为文昌、太乙与文昌、太乙与始击。定计大将门盘只布门，三门核对主体尚未裁定。将临中五时不擅自寄坤，保留未评估。

另本[《太乙金钥匙续集》](https://www.shidianguji.com/zh/book/NGJ89241199902106666022/chapter/1lq8dkylq3yn8)把直事门加定计目，另存 `dingmu_comparison_frame`。它与王法所用锚点不同，不能把其中有利的一盘替换已选方法，也不把多张派生盘当多份独立证据。

## 三门与五将分别核对

所选王法门盘检查太乙、文昌是否临开、休、生。每项保存实际位置、所属八方扇区、门值及 `gate_source_path`。间神沿所在扇区布门，如巳属巽九；这不是把巳的起算值改成九。

临开或生记录“两门不具”，临休记录“三门不具”；两者均阻断本项三门具条件。三门条件与[卷四五将的三项条件](taiyi-conditions.md)合取，得到本配置的 `menju_jiangfa`。这里只代表注明的条件组合；《武备志》还附“算长而和”，完整断法、旺相、玄命等没有因此完成。条件满足不等于事件会成功。

默认至点时计保持 `gates.status=not_computed_for_selected_mode`、`three_gates.status=not_assessed`。V15起`menju_jiangfa`采用三值合取：五将有实际阻断则为false，否则为null；三门未知不变，不把它改为不具。其序数不能冒充原典天正时实。明确选择[金钥匙时计](taiyi-hour.md)后可计算该本四门直使和定计；三门主体仍未裁定，不把已布门记为已具门。

## 定计的计算与分歧

年、月计以合神加本计太岁或月建，按同一十六神盘查看文昌所临，得到定计目；仍按二目规则数至太乙宫前，再求大将和参将。返回平移步数、每步算值、定计目及大小将标记；将入中五也保留。默认至点时计不附定计；金钥匙时计以本书时支合神加临，并保留原例三项分歧。

《金钥匙》1561辛酉年例定目辰、定算1、大将1、参将3；同书戊戌月例定目戌、定算17、大将7、参将1。《武备志》1571辛未年例定目午、定算24、大将4、参将2。所核字段相符，但没有据此宣布后本全书符合。

《统宗》图37崇祯甲戌例明确写32算、大将三宫、参将六宫；正文去十规则得到二宫、参六。原读数保留为大将3/2分歧，不为这一例加例外。

## 独立证据与失败状态

v5冻结材料（本地数据：`../tests/fixtures/taiyi_jinjing_v5/manifest.json`）包括原始网页指纹、剔除现代译文的古籍原文段落、国家图书馆藏本选定影像和人工读数。生产算法没有参与生成期望值。

- 《统宗》图31/32全部18行门表均保留，应核36项。年号换算下已核34项，27项相符；中统、至元、正统、弘治条有7项门值或干支冲突。末行康熙年数字形未裁定，2项未评估，仍计入36项要求，不计通过。
- 4个选定课例摘录共32项，29项相符。《金钥匙》戊戌月前段积月695，门段却为684、周余184、死门四月，按前段连续积月得到惊门五月，保留两项失败。另有上述定计大将3/2分歧。
- 《武备志》辛未例八门全部落宫、三门具而五将不发的组合相符。它验证空间门序和组合，不能推出真实军事应验。

审计报告（本地数据：`validation/taiyi-jinjing-v5/report.json`）继续返回失败，退出码为1。软件边界测试、接口一致性、全书符合与现实预测分别报告，不合并分母制造全书准确率。总缺口见验收清单（本地数据：`validation/taiyi-jinjing-v2/requirements.json`）。

## 调用与复核

调用合同中 `gates`、`gate_comparison`、`determinate` 是复制到fields的视图；三式合参对应 `taiyi_gates`、`taiyi_gate_comparison`、`taiyi_determinate`。视图名不是计算参数。首次摘要可以只读门盘或定计，全文仍通过同一run交付。

```bash
uv run --locked --extra dev fatebridge taiyi \
  --analysis-year 2026 --analysis-month 4 --analysis-day 4 --analysis-hour 12 \
  --calculation-mode year --no-use-true-solar-time \
  --strict-fields --include-snapshot-text false --response-char-limit 0 \
  --fields taiyi.gates taiyi.condition_assessment taiyi.determinate_calculation
uv run --locked --extra dev python scripts/audit_taiyi_gates.py \
  --output docs/validation/taiyi-jinjing-v5/report.json
uv run --locked --extra dev python -m pytest -q tests/test_taiyi_gates.py tests/test_taiyi_transports.py
```

[金钥匙日计](taiyi-day.md) 的日数不乘十二，沿用该本阴阳四门序加定计目；门表先约240与四门120日复现分别说明。日计三门主体仍未知，不借年计条件补齐。

V10新增[金钥匙天地二正月计与门数校验](taiyi-month.md)。八门扇区修正丑辰未戌四处归宫；原月段差异与朔月假设/节月比较的不匹配继续保留，原例实际月界仍未裁定。
