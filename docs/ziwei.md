# 紫微斗数参考

[文档中心](README.md) · [API 参考](api-reference.md) · [结果解读参考](interpretation/shared/ziwei-topic-evidence.md)

紫微斗数公开入口为 `ziwei_birth_chart`、`ziwei_timing` 与 `ziwei_rules`，完整输入与字段视图见[按需调用合同](contracts/README.md)。

## 流派、三盘与四化

- `school` 支持 `default`（软件三合基线）、`zhongzhou`（中州派：年支定命主、阴男阳女天伤天使互换、单星截空、大耗/龙德/劫杀、岁破）、`quanshu`（全书卷二摘录）与 `feixing`（飞星/钦天四化矩阵与来因宫）。
- `astro_type` 支持 `heaven`（天盘，命宫起盘）、`earth`（地盘，身宫为命宫重排）与 `human`（人盘，福德宫为命宫重排）。
- `sihua_source` 支持 `rule_profile`、`iztro_2_5_8`、`quanshu_v2`、`naj_ming_v1`、`feixing_liang` 与 `qintian`。
- `brightness_source` 支持 `rule_profile`、`iztro_2_5_8`、`quanshu_v2_selected_table`、`ziwei_doushu_qs`、`ziwei_doushu_xd1`、`ziwei_doushu_zz` 与 `ziwei_doushu_xd2`。
- 本命盘返回 `ming_gong`、`shen_gong`、`laiyin_gong`、`zidou_branch`、`wuxing_ju`、`daxian_direction`、`sihua`、`chart_masters`、`calendar_cycles`、`void_systems`、`flying_sihua`（十二宫飞星四化、离心自化、向心自化、忌冲与禄转忌/忌转忌）及 36 项确定性古典 `named_patterns`。

## 时钟、分日与岁序

- `day_divide` 支持 `current`（晚子 23:00–23:59 算当日）与 `forward`（晚子算次日早子，农历日序、流日/流时天干及虚岁换岁同步翻日）。
- `year_divide` 支持 `normal`（正月初一换年，默认）与 `exact`（立春换年）。
- `horoscope_divide` 支持 `normal`（农历月建，默认）与 `exact`（节气月建）；`natal_leap_month_policy` 统一覆盖本命与目标流月闰月规则。
- `age_divide` 支持 `normal`（农历新年换岁）与 `birthday`（农历生日换岁）。

## 大限、童限、斗君与批量运限

`ziwei_timing` 返回 `nominal_age`、`doujun_branch`（流年斗君）、1–6 岁激活态 `childhood_limit`（一命二财三疾厄，四岁夫妻五福德，六岁官禄）及 `scopes`（大限、小限、流年、流月、流日、流时）；另支持 `include_decadal_list`、`include_yearly_list`、`include_monthly_list` 一次性返回批量运限速览。
