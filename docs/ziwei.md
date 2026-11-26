# 紫微斗数参考

[文档中心](README.md) · [API 参考](api-reference.md) · [结果解读参考](interpretation/shared/ziwei-topic-evidence.md)

紫微斗数公开入口为 `ziwei_birth_chart`、`ziwei_timing` 与 `ziwei_rules`。三者共用 `rule_profile` 与来源标注，完整输入与字段视图见[按需调用合同](contracts/README.md)。

## 盘式、庙旺与四化

`rule_profile` 支持 `iztro_2_5_8`（软件对照基线）与 `quanshu_v2_excerpt`（限定原典摘录配置）。`sihua_source` 默认沿用所选配置，也可显式指定 `naj_ming_v1`（明刊四化表）；`brightness_source` 默认沿用基础配置，也可显式选择 `iztro_2_5_8`、`quanshu_v2_selected_table`、`ziwei_doushu_qs`、`ziwei_doushu_xd1`、`ziwei_doushu_zz` 或 `ziwei_doushu_xd2`。显式选表仅替换对应表层，不改变安星或运限规则。

本命盘返回命身宫、五行局、十四主星、辅星、四化、庙旺表、三方四正、长生与博士循环及旬空证据；年干四化使用所选农历年，不以八字立春年柱替代。

## 时钟与岁序

出生民用时钟、真太阳排盘时钟与目标时钟分开记录，重复民用钟时需传 `birth_utc_offset`。真太阳日期可影响安星日界，但虚岁岁序统一按 `birth_civil_timezone` 的东亚农历正月初一 00:00 换岁；目标时刻不得早于出生时刻。

## 大限、小限与流曜

`ziwei_timing` 分层返回大限、小限、流年、流月、流日与流时；未达五行局起运岁数时，大限返回 `status=not_started`，独立童限由 `childhood_limit` 返回。`analysis_minute` 与 `analysis_timezone` 默认分别为 `0` 和 `Asia/Shanghai`。

| 字段 | 含义 |
| --- | --- |
| `scopes[].palace_name` / `natal_palace_name` | 本层活动命宫所临的本命宫（角色见 `scope_palace_role`） |
| `palace_map` | 本层十二宫功能与本命星位的映射 |
| `mutagen_natal_links` | 本层四化与本命星曜、宫位的连接 |
| `natal_prerequisites` | 同次运限内部计算的农历、年干、时支、命身宫、五行局及推导轨迹 |

解读起大限岁数与局数依据时，可直接按 `evidence_views.natal_prerequisites` 投影读取，无需重复调用 `ziwei_birth_chart`。
