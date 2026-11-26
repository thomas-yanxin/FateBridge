# 按需 MCP 调用合同

由 `scripts/build_codex_call_contracts.py` 从实际 MCP 生成，不手改。
已连接且定义清楚时直接调用；只有本地离线核对或定义缺失时，读取所选文件，不加载全部合同。
当前连接的工具名、Schema 与公开范围优先；文件存在不代表该工具已连接。
这里只保存常用工具的离线合同，不是全部公开工具清单；其他工具可用 `fatebridge discover <tool>` 离线核对。
生成命令会移除本目录中已不再发布的 JSON；`--check` 同时检查缺失、内容漂移和遗留文件。

- [human_design](human_design.json)
- [horary_chart](horary_chart.json)
- [evaluate_election_time](evaluate_election_time.json)
- [relationship_chart](relationship_chart.json)
- [liuyao](liuyao.json)
- [gua_lookup](gua_lookup.json)
- [meihua_time_cast](meihua_time_cast.json)
- [meihua_cast](meihua_cast.json)
- [guolao_chart](guolao_chart.json)
- [hamburg_midpoint_chart](hamburg_midpoint_chart.json)
- [thirteen_sector_chart](thirteen_sector_chart.json)
- [ziwei_birth_chart](ziwei_birth_chart.json)
- [ziwei_timing](ziwei_timing.json)
- [ziwei_rules](ziwei_rules.json)
- [qimen](qimen.json)
- [taiyi](taiyi.json)
- [sanshi_combined_chart](sanshi_combined_chart.json)
- [vedic_chart](vedic_chart.json)
- [vimshottari_dasha](vimshottari_dasha.json)
- [bazi_career](bazi_career.json)
- [compare_bazi_sources](compare_bazi_sources.json)
- [bazi_compatibility](bazi_compatibility.json)
- [bazi_timing](bazi_timing.json)
- [fengshui_assess](fengshui_assess.json)
- [heluo](heluo.json)
- [canping](canping.json)
- [western_timing](western_timing.json)
- [interpret_astrology_dice](interpret_astrology_dice.json)
- [sukuyo_compatibility](sukuyo_compatibility.json)
- [suzhan](suzhan.json)
- [liuren_chart](liuren_chart.json)
- [liuren_yearly_timing](liuren_yearly_timing.json)
- [jinkou](jinkou.json)
- [knowledge_catalog](knowledge_catalog.json)
- [knowledge_read](knowledge_read.json)
- [ipip_big_five](ipip_big_five.json)

`input` 描述 `run_calculation.arguments`。工具名和控制参数（`detail`、`fields`、`as_of`）放在 `run_calculation` 的外层。
首次摘要使用 `detail="compact"` 并省略 `fields`。需要指定业务字段时，可按问题选择 `first_view.fields` 或 `evidence_views` 中的字段（默认严格投影）。
完整输出使用 `detail="audit"` 并省略 `fields`。
输入日期使用公历；不猜生时、不套示例；出生与分析时刻、时区及太阳时策略以各工具合同为准。
