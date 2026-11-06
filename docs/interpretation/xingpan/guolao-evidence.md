# 果老研究盘取证

`astro_guolao_chart` 与 `astro_chart(chart_variant="guolao_chart")` 等价。先读本次
`guolao.profile/validation`，再按已发布 `astronomy/classical/reading/timing` 视图取字段。
视图名不是请求参数；使用对应 `fields`、`strict_fields=true`、`include_snapshot_text=false`。

七政及四余在 `guolao.bodies`，保留黄经、赤经、速度、宫主、研究宿位和度主。
宫主和度主归属表校对自东北大学藏陆位辑校本卷一；本次星位由现代星历与距星表计算。
宫主/度主归属正确，不代表宿界或整张盘已经复原原典。

- `life_palace.method=source_hour_count_with_declared_research_inputs_v1`：按底本顺数安命与二至例外；核对太阳宫、生时、计数锚点和钟面。所选现代30度太阳宫与交节瞬间端点仍为研究映射，不能称完整原典安命已验收。命度/命宿为null，不拿`angles.ascendant`补出命宿或“命坐两歧”。
- `mansion.placement_basis=modern_equatorial_research_anchors_v1`：不等赤经研究宿界；不能写成底本历史宿界，不能把现代角度与古度混算。
- `conditions` 回显太阳几何高度和节气季节；不能改回固定6–18点或公历11–1月。
- 真太阳时选项取另行回显钟面的生时地支，可改变命宫及其格局，不改变出生瞬间或物理星位。UTC、UT1、TT和实际星历模型见 `profile`。
- 显式地方平太阳时／真太阳时输入核对 `profile.input_clock` 与 `life_palace.clock_basis`。原生TT／UT1瞬间可以有效而UTC标签为空；不能因此称七政位置未计算，也不能补一个UTC钟时。沿用本次标签取时的实际政策，解释时不再移动瞬间。
- `god_positions`是本底本天乙昼贵、玉堂夜贵及岁驾的实际宫支，含本次按昼夜选出的贵人；不能再用外部八字表换回。年干支的立春换年政策仍需说明，未据两页表文认证全年历法。
- `purple_model_audit`保存原典周积舍入缺口；它不是新紫气黄经。紫气仍为软件拟合虚点，现代历元未校准；罗为平交点、计取对点、孛为平均远地点。说明所用模型，不把四余说成四颗实体天体。
- `profile.astronomical_house_frame/method`说明参考天文宫头采用的黄道；`houses/planets.house`与按安命逆布的`guolao.palaces`分别读取。恒星整宫制修复不等于原典命度验收；离线授时距算复算也不能直接代入现代出生日期。
- `moira_patterns` 为兼容格局，每条保留未通过原典验收的标记。未命中只表示已实现规则本次没触发，不能推成无传统格局或现实无机会。
- 不使用其他西方盘的性格文案、旺陷表或相位冒充果老原典解释；以本run的 `rule_trace` 与实际宫主/度主关系为据。
- 用户明确目标瞬间后可传带时区偏移的`analysis_datetime`；`guolao.timing.small_limit`是原页小限逆数结果，暂按明示立春政策换年，`transit_bodies`为当时七政及四余模型位置，并回显本命功能宫。未给目标时`status=not_requested`，不默取今天，也不用`as_of`替代目标。目标星空无地点/地平几何，真太阳钟面不能移动其物理时刻。
- 月限须显式选择本次支持的 `guolao_month_basis`，核对 `timing.month_limit` 的状态、出生及目标月序、年小限宫与实际月限宫。节令月序和UTC+08现代农历是分别声明的研究政策；不根据结果切换，闰月或资料不足时依实际状态保留未分配，不能当作没有职业事件。
- 对无UTC标签的原生瞬间，月序资料若返回 `calendar_date/calendar_date_evidence`，只说明已证明固定UTC+08的日期可用于查历；`calendar_datetime=null`仍不提供UTC钟时。日期证明不等于古代月制、现代出生记录或整套历法已验收。没有这项日期证据时也不自行按TT的日期标签填月序。
- 小限落宫和当时星位还不是完整流年判断；洞微大限、童限未完成，不能由静态盘补写事件日期，或由落官禄宫推出晋升。尚无独立前瞻验证，不把规则标签、软件一致性或可复现性解释为现实命中率。

交付先回答可答的盘面含义，说明传统的主从、生克对应，再给现实中可观察的安排。
只在对应结论旁说明其未验收依赖，不用限制列表代替全部解释。完整JSON首次 `fields=null`，
其后读取同run `result_delivery`，不以摘要重新排盘。
