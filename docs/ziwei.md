# 紫微斗数：当前盘式、时间层与来源

[文档中心](README.md) · [API 参考](api-reference.md) · [算法状态](algorithm-status.md)

公开入口为 `ziwei_birth`、`ziwei_horoscope` 与 `ziwei_rules`。本命与运限保持来源和规则选择，规则查询提供具名条文、前提与未覆盖项。参数和输出字段见[按需合同](contracts/README.md)。

## 盘式与四化

`rule_profile` 保留 `iztro_2_5_8` 与 `quanshu_v2_excerpt`，分别表达软件对照配置与限定原典摘录配置。`sihua_source=rule_profile` 沿用所选配置；`naj_ming_v1` 显式采用明刊原页四化表。选择其中一表不代表整部原典已获验收。

本命保留命身宫、五行局、十四主星、辅星、四化、庙旺表、三方四正、长生与博士循环、旬空及相关宫位证据。完整三合视图不自动成为吉凶评级。年干四化使用所选农历年；不能把八字立春年柱挪作紫微农历年。

闰月、日界、早晚子时、火铃顺逆、限宫首位和附星采用所选规则集。原书缺文、同图疑字及版本异读随规则来源和盘内比较返回，不用当前程序通则填补原字。`independent_review` 等状态只约束实际已复读内容，不认证未审阅章节。

## 时钟与岁序

出生民用时钟、真太阳排盘时钟、目标时钟各自记录；已知重复钟时需明确UTC偏移。真太阳日期可改变安星日期，但岁序统一采用 `birth_civil_timezone`：将出生和目标的实际瞬间转换到出生民用时区，再按当地日期查所采用的东亚农历日期表，以正月初一00:00换岁。

本命、运限与规则查询都接受 `day_divide=current|forward`，默认 `current`。`current` 在23:00–23:59保留当日农历，同时用当日早子日干、时干；`forward` 把本命与目标的晚子统一视作次日早子，农历年月日、流年、流月、流日落宫与流日／流时天干一起推进。00:00以后两种口径相同。出生采用实际校正后的排盘钟面，目标采用目标民用钟面。晚子进入闰月、出闰月或跨正月初一时，先选当日／次日农历，再应用所选闰月规则。岁序保持出生民用时区正月初一00:00换岁，因此 `forward` 的除夕晚子可以已经采用新年流曜、岁序仍属旧年。

所选口径随 `ruleset.day_divide`、`calendar_rules.day_divide`、`calendar_basis.day_divide` 及各层 `stem_origin` 返回。`calendar_basis` 分列实际选用的排盘日期、农历与原民用日期；快照也列明23:00或00:00换日。`forward` 的时钟摘要农历也随所选日期更新；原 `four_pillars` 与本命 `calendar_context` 仍记录共享历法计算，原民用农历另存于日历依据，不能替代紫微所选流日、流时干。内部用同一命盘计算运限时，拒绝与本命不一致的 `day_divide`。

这一软件约定不重建历史地方朔时，也未认证古典岁首。目标实际时刻早于出生时刻明确拒绝，不能把小于1的错误钳为1。内部规则审计使用的合成农历输入只是条件盘；无实际出生时钟不能自行推定岁序。

## 大限、小限与流曜

运限分列大限、小限、流年、流月、流日和流时，实际落宫与目标历法地支分别表达。给定岁序小于所选局数起岁时，大限返回 `status=not_started`、起岁与原因；落宫、宫干与四化为空，映射及连接为空列表。独立 `childhood_limit` 保留具名童限，不拿童限替代正式大限。

起大限当岁按所选配置计算实际宫位；大限上、下五年的限定分段保留实际前提与未决解释。流月斗君、流日及流时的共享索引按所选规则使用，相关出生月、时支和目标月日均随同次本命前置链返回。未知性别只限制需要顺逆的层，不抹去已经确定的本命事实。

运限结果中，`analysis_context` 记录目标时刻，`birth_context` 保留出生校正；`target_minute`、`target_timezone` 默认分别为 0 和 `Asia/Shanghai`。宫位字段分工如下：

| 字段 | 含义 |
| --- | --- |
| `scopes[].palace_name/natal_palace_name` | 本层命宫活动索引所临的本命宫；角色见 `scope_palace_role` |
| `palace_map` | 本层十二宫功能与本命星位的映射 |
| `mutagen_natal_links` | 本层四化与本命星曜、宫位的连接；`scope_palace_name` 标出本层宫位 |
| `natal_prerequisites` | 同次运限内部使用的农历、年干、时支、命身宫、五行局及推导轨迹 |

解释起大限岁数或局数来源时，可读 `evidence_views.natal_prerequisites` 的字段清单，无需另起本命计算。本命官禄不等于流年官禄，出生年干、岁序与目标层天干也不能互换。这些连接不表示全部流曜或飞宫体系已经实现。

## 当前检验与限制

`tests/data/ziwei_independent` 保留一手书影、HKO历表与独立字面规则参考。软件交叉对照只证明对指定配置的有限一致；条件宫位审计不认证历法转换，春节边界与同一瞬间跨区岁序另用独立日期资料检验。

2026-11-09 在原1,080例之外，新增固定 [iztro 2.5.8](https://github.com/SylarLong/iztro/tree/2.5.8) 默认配置的普通月日时、六十年时序和四个闰月网格。13,936条比较记录对应13,910组不同输入；66颗本命星的919,776条记录及334,464个长生／博士格无差异，同时核对命身宫、五行局、命身主、宫名宫干及大限序列。104条不存在的闰月三十日保留为来源无效日期控制，未计通过。参考及采集计划位于本地 `tests/data/ziwei_independent/natal_factor_grid_v1`；网格有重叠，未覆盖所有年份的完整组合，也不裁定其他规则配置、原典异文或全部流曜。

历史2026-11-19记录的20例、2,440字段保持原分母：所选2.5.8口径2,440／2,440，2.6.5为2,422／2,440，18差集中于三个晚子案例的流日／流时干、四化及本命连接。该轮原始驱动、输入清单及结果档案现已缺失，本次不能把新用例称为原20例的重跑，也不把旧18差清零。保留下来的18例2.5.8软件参考独立保存于 `tests/data/ziwei_horoscope_reference.json`；其中三例正式起限前差异继续显式断言，晚子行的旧丁日、庚时四化也原样保留，与当前丙日、戊时结果逐项区分。`rule_profile=iztro_2_5_8` 仍选择原安星配置，新增 `day_divide` 独立选择分日，不表示默认晚子干继续逐值等于2.5.8发布包。

本次回归另外覆盖普通晚子、午夜、春节、闰二月与闰十一月交接，验证本命及四层流曜的所选日期一致，并在固定 `as_of` 下通过真实REST POST、逐工具FastMCP和CLI严格投影核对日期依据、流日／流时、四化连接与流年禄羊陀。此类日期一致性检查是工程性质，不代替原典分日书证。参考生成器支持显式 `--version`、`--day-divide` 并要求指定 `--output`，避免默认覆盖旧软件参考；本次真实参考包执行被自动审批以“Code from External”拒绝，不能声明两版实时对照已完成。

```bash
uv run --locked --extra dev python -m pytest -n0 tests/ziwei/test_contract_regressions.py tests/ziwei/test_ziwei_horoscope_crosscheck.py tests/ziwei/test_ziwei_twenty_first_iteration.py
uv run --locked --extra dev python -m scripts.ziwei.audit_ziwei_natal --fixtures tests/data/ziwei_independent/natal_factor_grid_v1 --output /tmp/ziwei-natal-factor-grid-audit.json
```

精确的索引、可复现结果和局部文字符合度不证明现实预测有效。整书、全部流派、未知生时、连续未来时间以及实际事件预测仍需各自的独立验收。
