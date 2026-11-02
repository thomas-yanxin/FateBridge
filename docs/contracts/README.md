# 按需 MCP 调用合同

由 `scripts/build_codex_call_contracts.py` 从实际 MCP 生成，不手改。
已连接且定义清楚时直接调用；只有本地离线核对或定义缺失时，读取所选文件，不加载全部合同。
当前连接的工具名、Schema 与公开范围优先；文件存在不代表该工具已连接。

- [human_design](human_design.json)
- [astro_horary](astro_horary.json)
- [astro_election](astro_election.json)
- [astro_relative_chart](astro_relative_chart.json)
- [sixyao](sixyao.json)
- [gua_lookup](gua_lookup.json)
- [meihua_analysis](meihua_analysis.json)
- [meihua_cast](meihua_cast.json)
- [astro_guolao_chart](astro_guolao_chart.json)
- [astro_germany_chart](astro_germany_chart.json)
- [astro_chart13](astro_chart13.json)
- [ziwei_birth](ziwei_birth.json)
- [ziwei_horoscope](ziwei_horoscope.json)
- [ziwei_rules](ziwei_rules.json)
- [qimen](qimen.json)
- [taiyi](taiyi.json)
- [sanshiunited](sanshiunited.json)
- [astro_india_chart](astro_india_chart.json)
- [astro_vimshottari](astro_vimshottari.json)
- [bazi_career](bazi_career.json)
- [bazi_source_compare](bazi_source_compare.json)
- [two_person_compatibility](two_person_compatibility.json)
- [timing_analysis](timing_analysis.json)
- [fengshui_assess](fengshui_assess.json)
- [heluo](heluo.json)
- [canping](canping.json)
- [western_timing_analysis](western_timing_analysis.json)
- [otherbu](otherbu.json)
- [sukuyo_compatibility](sukuyo_compatibility.json)
- [suzhan](suzhan.json)
- [liureng_gods](liureng_gods.json)
- [liureng_runyear](liureng_runyear.json)
- [jinkou](jinkou.json)
- [knowledge_registry](knowledge_registry.json)
- [knowledge_read](knowledge_read.json)

每个文件保留完整输入约束、参数说明、首轮字段及任务视图。视图名不是请求参数。
摘要投影与完整导出分别使用 first_view 和 fields=null；完整结果读取同一 run。
输入日期使用公历；不猜生时、不套示例；出生与分析时刻、时区及太阳时策略以各工具合同为准。
