"""Readable facts preserve the same method/subject scopes as structured JSON."""

from typing import Any, Dict, List, Tuple

from fatebridge.core.aa1996_solar import MODEL_ID as AA1996_SOLAR_MODEL
from fatebridge.core.analytic_solar import MODEL_ID as ANALYTIC_SOLAR_MODEL
from fatebridge.core.de440_solar import (
    HISTORICAL_MODEL_ID,
)
from fatebridge.core.de440_solar import MODEL_ID as DE440_SOLAR_MODEL
from fatebridge.core.moshier_solar import MODEL_ID as COMPLETE_MOSHIER_SOLAR_MODEL
from fatebridge.core.vsop2013_solar import MODEL_ID as VSOP2013_SOLAR_MODEL

from .host_guest import statements as host_guest_statements
from .source_comparison import comparison_statements


def _bazhai_scope(entry: Dict[str, Any]) -> str:
    subject = f"{entry['subject_kind']}:{entry['subject_id']}"
    if entry["subject_kind"] == "occupant":
        subject += f" 起法{entry['gender_convention']}"
    elif "house_candidate_id" in entry:
        subject += (
            f" 坐卦{entry['house_sitting_trigram']} 编号{entry['house_candidate_id']}"
        )
    return subject + (
        "（未确认候选）" if entry["candidate_only"] else "（已确认作用域）"
    )


def _bazhai_application(entry: Dict[str, Any]) -> str:
    relation, trace = entry["palace_star_relationship"], entry["you_nian_trace"]
    star = entry["star"]
    return (
        f"{star['name']}（{star['element']}）；"
        f"基本星性用途匹配：{entry['matches_convention']}；"
        f"{relation['traditional_label']}（宫{relation['palace_element']}，星{relation['star_element']}）；"
        f"累计变爻{trace['operation_count']}次，净变{trace['net_changed_line_count']}爻"
    )


def _calendar_cautions(layer: Dict[str, Any]) -> List[str]:
    """Render actual clock policies without changing year or natal results."""
    stack: List[Any] = [layer]
    historical = future = moshier = analytic = guarded_de440 = aa1996 = False
    vsop2013 = complete_moshier = False
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            moshier |= current.get("ephemeris_model") == "moshier"
            complete_moshier |= (
                current.get("ephemeris_model") == COMPLETE_MOSHIER_SOLAR_MODEL
            )
            analytic |= current.get("ephemeris_model") == ANALYTIC_SOLAR_MODEL
            aa1996 |= current.get("ephemeris_model") == AA1996_SOLAR_MODEL
            vsop2013 |= current.get("ephemeris_model") == VSOP2013_SOLAR_MODEL
            guarded_de440 |= (
                isinstance(current.get("ephemeris_model"), str)
                and current.get("ephemeris_model")
                in {DE440_SOLAR_MODEL, HISTORICAL_MODEL_ID}
                and current.get("uncertainty_reason")
                in (
                    "de440_solar_model_guard_not_accuracy_certification",
                    "de440_historical_solar_model_guard_not_accuracy_certification",
                )
            )
            basis = current.get("time_basis", {})
            if isinstance(basis, dict):
                historical |= basis.get("historical_ut1_convention") is True
                future |= basis.get("future_leap_seconds_assumed_unchanged") is True
            stack.extend(current.values())
        elif isinstance(current, (list, tuple)):
            stack.extend(current)
    lines = []
    if moshier:
        lines.append("交节所报TT处星历为Moshier；该配置完整范围尚未通过1秒实现验收。")
    if complete_moshier:
        lines.append(
            "交节采用完整Moshier太阳修订；逐边界保留1996年级数与完整月球依赖，有限TT验收不认证全部时刻或绝对UTC。"
        )
    if vsop2013:
        lines.append(
            "交节采用FateBridge VSOP2013太阳模型；TT数值对照与边界候选保护不认证绝对UTC精度。"
        )
    if aa1996:
        lines.append(
            "交节采用FateBridge AA1996太阳模型；边界候选保护不表示绝对UTC精度已获认证。"
        )
    if analytic:
        lines.append(
            "交节采用FateBridge解析太阳模型；边界候选保护不表示秒级精度已获认证。"
        )
    if guarded_de440:
        lines.append("交节采用DE440轨道计算；边界候选保护不表示绝对UTC精度已获认证。")
    if historical:
        lines.append("历史交节钟时采用UT1/ΔT约定；UTC形式的标签不表示当时已有UTC。")
    if future:
        lines.append("未来交节UTC按冻结闰秒表不变假设换算；不保证实际UTC交节秒。")
    return lines


def sections(result: Dict[str, Any]) -> List[Tuple[str, List[str]]]:
    output = [("起盘信息", [result["summary"], f"覆盖状态：{result['status']}"])]
    if "method_policy" in result:
        policy = result["method_policy"]
        output.append(
            (
                "方法选择",
                [
                    "主法参考：九宫飞星、金锁玉关、八宅；局部按此前两法优先，实际计算仅含已选层。",
                    "本次计算顺序：" + "、".join(policy["selected_method_order"]),
                    "八字、紫微及周围人的个人喜忌不代入客观环境；八宅个人命卦独立。",
                    "优先级表示审查顺序，不产生综合评分或抵消。",
                    f"现状优先方法审查：{policy['priority_review_status']}；"
                    f"未覆盖优先法：{'、'.join(policy['priority_missing_methods']) or '无'}；"
                    "与已选计算完成状态分别读取，显式排除不追资料。",
                ],
            )
        )
    for name, layer in result["layers"].items():
        lines = [
            f"规则：{layer['ruleset']['ruleset_id']}@{layer['ruleset']['version']}"
        ]
        if name == "directions":
            lines.extend(
                f"{d} {p['trigram']} 宫数{p['palace_number']}"
                for d, p in layer["directions"].items()
            )
            if layer["bearing"]:
                b = layer["bearing"]
                lines.append(
                    f"输入方位：{b['bearing_degrees']}° {b['north_reference']} {b['direction']} {b['mountain']}"
                )
            geomagnetic = layer.get("geomagnetic_reference")
            if geomagnetic is not None:
                field, conversion = geomagnetic["field"], geomagnetic["conversion"]
                model_input = geomagnetic["input"]
                lines.append(
                    f"地磁参考：{geomagnetic['ruleset']['ruleset_id']}@{geomagnetic['ruleset']['version']}；"
                    f"纬度{model_input['latitude']} 经度{model_input['longitude']}；"
                    f"WGS84椭球高{model_input['height_km_wgs84']}km；小数年{model_input['effective_decimal_year']}；"
                    f"东正磁偏角{field['declination_degrees_east']:.4f}°；"
                    f"区域{geomagnetic['heading_context']['zone']}；换算{conversion['status']}"
                )
                if conversion["candidate"] is not None:
                    candidate = conversion["candidate"]
                    lines.append(
                        f"模型换算候选：{candidate['bearing_degrees']:.4f}° {candidate['north_reference']}；"
                        "尚未确认现场方向，未用于修改宅盘。"
                    )
                if conversion["unavailable_reason"] is not None:
                    lines.append(f"换算不可用：{conversion['unavailable_reason']}")
                lines.extend(geomagnetic["limitations"])
        elif name == "xuankong_natal":
            period = layer.get("period_context")
            if period:
                number = period["number"]
                label = (
                    number
                    if number is not None
                    else "待确认（候选"
                    + "、".join(map(str, period.get("candidate_period_numbers", [])))
                    + "）"
                )
                lines.append(
                    f"历史宅运：{label}；定运依据：{period['basis']}；证据：{period['evidence']}"
                )
                if period.get("effective_event_year_status") == "requires_confirmation":
                    years = "、".join(
                        map(str, period["candidate_effective_event_years"])
                    )
                    conclusion = (
                        f"所有候选年均属{number}运，宅运已确定，事件有效年仍未确认。"
                        if number is not None
                        else "候选年跨运，尚不能选定唯一历史宅盘。"
                    )
                    lines.append(f"事件有效年待确认：{years}；{conclusion}")
            lines.append(f"候选数：{len(layer['candidates'])}；状态：{layer['status']}")
            for chart in layer["candidates"]:
                lines.append(
                    f"{chart['candidate_id']} {chart['sitting']['name']}山{chart['facing']['name']}向；{chart['chart_mode']}；{chart['mode_reason']}"
                )
                support = chart["bearing_support"]
                lines.append(
                    "测量区间支持（围绕输入宅向展开的角度；端点含，分数字符串为精确值）："
                    + "；".join(
                        f"[{region['from_degrees_exact']}, {region['until_degrees_exact']}]° {region['mode_reason']}"
                        for region in support["regions"]
                    )
                    + "；角区支持不表示概率或测量认证。"
                )
                lines.extend(
                    f"{d} 固定宫数{p['palace_number']} 运星{p['period_star_number']} 山星{p['mountain_star_number']} 向星{p['facing_star_number']}"
                    for d, p in chart["palaces"].items()
                )
                structure = chart["structure"]
                distribution = structure["distribution"]
                lines.append(
                    f"历史{structure['reference_period_number']}运星位结构："
                    f"{distribution['traditional_label']}；"
                    f"山星当运数在{distribution['mountain_period_star_direction']}，"
                    f"向星当运数在{distribution['facing_period_star_direction']}；"
                    "仅为数字结构，不代表当前旺衰、外局匹配或现实吉凶。"
                )
                for role, trace in chart["trace"].items():
                    decision = trace["replacement_lookup"]["decision"]
                    decision_label = {
                        "lower_chart_not_using_replacement": "下卦未启用替星",
                        "five_yellow_has_no_substitute": "五黄不替，仍五入中",
                        "same_star_explicitly_retained": "完整替星表同数，明确保留原星",
                        "different_star_substituted": "按同元龙查表实际改星",
                    }[decision]
                    lines.append(
                        f"{role} 原星{trace['seed_star_number']} 同元龙{trace['mapped_mountain']} {trace['polarity']} {trace['flight']} 入中{trace['center_star_number']}；五黄借法：{trace['five_yellow_policy']}；替星判断：{decision_label}，顺逆仍按原同元龙阴阳"
                    )
                patterns = structure["classical_patterns"]
                opposite = patterns["opposite_star_comparison"]
                center = opposite["center_numeric_pair"]
                lines.append(
                    f"山星与对宫向星的八个有向配对全部合十：{opposite['all_eight_sum_to_ten']}；"
                    f"中宫只作数字相加{center['mountain_star_number']}+{center['facing_star_number']}={center['sum']}，不算空间对宫，也不参与八宫合取。"
                    "该数式不同于同宫合十或完整反吟判定。"
                )
                for direction, pair in opposite["pairs"].items():
                    lines.append(
                        f"对宫有向配对：{direction}山星{pair['mountain_star_number']} + {pair['facing_direction']}向星{pair['facing_star_number']} = {pair['sum']}；合十条件：{pair['matches_sum_to_ten']}"
                    )
                lines.append(
                    f"全局父母三般卦数字条件：{patterns['parental_triples']['all_nine_match']}；"
                    "须逐宫具足147、258或369三个不同星数，不能以同组余数或普通连续三数组代替。"
                )
                for role, comparison in patterns["ground_comparison"]["roles"].items():
                    lines.append(
                        f"{role} 固定地盘全盘同数（伏吟数式）：{comparison['whole_ground_repeat']}；"
                        f"固定地盘全盘对数（反吟数式）：{comparison['whole_ground_reverse']}；"
                        f"与历史运盘全盘同数：{comparison['whole_period_plate_same']}。三个比较分别读取。"
                        f"固定地盘同数宫位：{'、'.join(comparison['same_ground_directions']) or '无'}；"
                        f"固定地盘对数外宫：{'、'.join(comparison['opposite_ground_directions']) or '无'}；"
                        f"与历史运盘同数宫位：{'、'.join(comparison['period_plate_same_directions']) or '无'}。"
                    )
                named = patterns["volume_two_named_refrain"]
                lines.append(
                    f"卷二所列下卦反伏局数字对应：{named['numeric_match']}；适用下卦：{named['applicable']}。"
                    "局部对宫与全盘五入中有别；以上仅为原典数字结构，不代表吉凶、现实事件或动作许可。"
                )
            comparison = layer.get("source_comparison")
            if comparison is not None:
                lines.extend(text for _, text in comparison_statements(comparison))
            interpretation = layer.get("interpretation")
            if interpretation is not None:
                lines.append(
                    f"有限解释：{interpretation['ruleset_id']}；状态{interpretation['status']}；"
                    f"当前评价运{interpretation['current_period_context']['number']}，不重置历史宅运"
                )
                profile = interpretation.get("timeliness_ruleset")
                fixed = interpretation.get("fixed_lingzheng_analysis")
                if fixed is not None:
                    lines.append(
                        f"独立固定零正：{fixed['ruleset']['ruleset_id']}@{fixed['ruleset']['version']}；"
                        f"评价运{fixed['reference_period_number']}；选择{fixed['selection_status']}。"
                        "固定地盘与山向飞星分别读取，不以匹配数字代替现场形势。"
                    )
                    for variant in fixed["candidates"]:
                        lines.append(
                            f"零正候选{variant['candidate_id']}：正神数{variant['zheng_number']}应用宫{variant['zheng_direction']}；"
                            f"零神数{variant['ling_number']}应用宫{variant['ling_direction']}；候选状态{variant['candidate_only']}。"
                        )
                        for direction, value in variant["palaces"].items():
                            if value["role"] != "not_selected":
                                lines.append(
                                    f"{direction} 固定{value['role']}存在条件：{value['form_assessment']['status']}，不能推导综合吉凶或执行许可。"
                                )
                if profile is not None:
                    lines.append(
                        f"作者时令：王亭之《中州派玄空学》上卷16–17页，{profile['ruleset_id']}@{profile['version']}；"
                        "基本时令与先后天互用数字分开，不能据衰死一律判不可用。"
                    )
                for candidate in interpretation["candidates"]:
                    lines.append(f"解释候选：{candidate['candidate_id']}")
                    for direction, palace in candidate["palaces"].items():
                        pair = palace["ordered_pair"]
                        forms = palace["external_form_analysis"]
                        lines.append(
                            f"{direction} 山星/向星五行：{pair['relationship']}；"
                            f"山形条件{forms['mountain']['status']}；水形条件{forms['water']['status']}"
                        )
                        if profile is not None:
                            for role, label in (
                                ("mountain", "山星"),
                                ("facing", "向星"),
                            ):
                                phase = palace["timeliness"][role][
                                    "author_classification"
                                ]
                                lines.append(
                                    f"{direction} {label}{phase['star_number']}：王氏基本时令{phase['traditional_label'] or '未定'}；"
                                    f"互用数字成员{phase['mutual_use_reference']['numeric_membership']}，仅数字参考，不证明现场可用。"
                                )
                    for use in candidate["placement_findings"]:
                        lines.append(f"用途对象{use['object_id']}：{use['status']}")
                host_guest = interpretation.get("host_guest_analysis")
                if host_guest is not None:
                    lines.append(
                        "独立主客出入：坐山宫山主、向首宫向主；其他六宫与中宫不套此规则，出入名称不作时令或吉凶结论。"
                    )
                    lines.extend(
                        text for _, _, text in host_guest_statements(host_guest)
                    )
                lines.extend(interpretation["limitations"])
            city_gate = layer.get("city_gate_analysis")
            if city_gate is not None:
                lines.append(
                    f"独立沈氏城门：{city_gate['ruleset']['ruleset_id']}@{city_gate['ruleset']['version']}；"
                    f"参考运{city_gate['reference_period_context']['number']}；计算{city_gate['calculation_status']}；"
                    "不重置历史宅运，门位数字不等于现场已合格。"
                )
                for candidate in city_gate["candidates"]:
                    lines.append(
                        f"城门朝向候选：{candidate['facing']['name']}；元龙{candidate['facing']['yuan']}；未确认候选{candidate['candidate_only']}"
                    )
                    for gate in candidate["gates"]:
                        lines.append(
                            f"{gate['direction']} {gate['mountain']['name']}门位；运星{gate['seed_star_number']}，"
                            f"映射{gate['mapped_mountain']} {gate['mapped_polarity']} {gate['flight']}；"
                            f"门位星{gate['star_at_gate']}；令星逆飞到门{gate['reference_star_reaches_gate_by_reverse_flight']}；"
                            f"水形{gate['form_assessment']['status']}；本条组合条件{gate['combined_condition_match']}。"
                        )
                for observation in city_gate["unmatched_observations"]:
                    lines.append(
                        f"水形{observation['mountain']}：不属于本次向首同元龙旁宫门位，未转成其他山位。"
                    )
                lines.extend(city_gate["limitations"])
        elif name == "monthly_stars":
            lines.extend(s["text"] for s in layer["position_reading"]["statements"])
            lines.extend(layer["limitations"])
        elif name == "annual_stars":
            if layer.get("effective_year") is not None:
                lines.append(
                    f"有效年：{layer['effective_year']}；入中：{layer['center_star_number']}"
                )
                lines.extend(
                    f"{d} 固定宫数{p['palace_number']} 年星{p['annual_star_number']} {p['annual_star']['name']}"
                    for d, p in layer["palaces"].items()
                )
                lines.append(
                    f"有效期：{layer['time_context']['valid_from']} 至 {layer['time_context']['valid_until']}（结束不含）"
                )
        elif name == "jinsuo":
            lines.extend(
                f"{d} 偏好{p['preferred_classification']}"
                for d, p in layer["preferences"].items()
            )
            lines.extend(
                f"{f['object_id']} {f['direction']} {f['classification']}：{f['finding']}；依据：{f['evidence']}"
                for f in layer["feature_findings"]
            )
        elif name in {"bazhai", "minggua"}:
            lines.append(
                "宫星关系按本版本星表逐项计算，不合成全宅吉凶；伏位采用木，"
                "另有‘随门而化’文本语境，本次未自动套用。"
            )
            house = layer.get("house")
            orientation = layer.get("house_orientation_context")
            if orientation:
                lines.append(
                    f"宅向名义值{orientation['nominal_facing_degrees']}°，"
                    f"提供的误差半径{orientation['bearing_uncertainty_degrees']}°；"
                    f"来源{orientation['uncertainty_input_path']}；坐卦状态{orientation['status']}。"
                    "仅为所给区间的计算支持，不是现场误差认证或候选概率。"
                )
            houses = layer.get("house_candidates") or ([house] if house else [])
            for house in houses:
                lines.append(
                    (
                        f"宅卦：{house['sitting_trigram']}；住宅：{house['object_id']}"
                        if "candidate_id" not in house
                        else f"宅卦{house['candidate_id']}：{house['sitting_trigram']}；住宅：{house['object_id']}；"
                        + ("未确认候选" if house["candidate_only"] else "坐卦已确定")
                    )
                )
                lines.extend(
                    (
                        f"宅盘 {d} "
                        if "candidate_id" not in house
                        else f"宅盘{house['candidate_id']} {d} "
                    )
                    + f"{p['star']['name']} {p['star']['polarity']}；"
                    f"{p['palace_star_relationship']['traditional_label']}"
                    for d, p in house["sectors"].items()
                )
            people = layer.get("occupants", [layer] if name == "minggua" else [])
            for person in people:
                for candidate in person["candidates"]:
                    lines.append(
                        f"住户{person['subject_id']} {candidate['gender_convention']}：有效生年{person['time_context']['effective_year']}；原始数{candidate['raw_number']}；寄宫后{candidate['palace_number']} {candidate['trigram']}；{person['status']}"
                    )
                    lines.extend(
                        f"个人盘 {person['subject_id']} 起法{candidate['gender_convention']} {d} {p['star']['name']} {p['star']['polarity']}；"
                        f"{p['palace_star_relationship']['traditional_label']}"
                        for d, p in candidate["sectors"].items()
                    )
            lines.extend(
                f"{_bazhai_scope(f)} 对象{f['object_id']} {f['aspect']} "
                f"{f['facing_role'] + ' ' if f['facing_role'] else ''}{f['direction']}；{_bazhai_application(f)}"
                for f in layer.get("placement_findings", [])
            )
        lines.extend(_calendar_cautions(layer))
        output.append(
            (
                {
                    "directions": "公共方位",
                    "minggua": "住户命卦",
                    "bazhai": "八宅分层",
                    "annual_stars": "年度飞星",
                    "monthly_stars": "月紫白",
                    "jinsuo": "砂水判定",
                    "xuankong_natal": "玄空宅盘",
                }[name],
                lines,
            )
        )
    if "layout_analysis" in result:
        layout = result["layout_analysis"]
        lines = [
            f"布局计算状态：{layout['status']}；范围：{layout['calculation_scope']}"
        ]
        for option in layout["adjustment_options"]:
            agreement = (
                "尚无已确认作用域"
                if option["resolution"] == "no_confirmed_scope"
                else "、".join(option["agreed_matching_directions"])
                or "已确认作用域之间没有共同匹配方位"
            )
            lines.append(
                f"对象{option['object_id']} {option['aspect']} 当前{option['current_direction']}；已确认作用域共同基本星性匹配方位：{agreement}；"
                "仅按星性筛选，不表示宫星条件、现场形态或搬移可行性均合格。"
            )
            if option.get("action_status") == "blocked":
                lines.append(
                    f"对象{option['object_id']} {option['aspect']}调整受限：用户明确禁止相应动作"
                )
            for scope in option["scopes"]:
                lines.append(
                    f"{_bazhai_scope(scope)} 当前{scope['direction']}：{_bazhai_application(scope)}；"
                    f"基本星性匹配方位：{'、'.join(scope['matching_directions'])}"
                )
                lines.extend(
                    f"{_bazhai_scope(scope)} 备选{d}："
                    f"{_bazhai_application(evidence)}"
                    for d, evidence in scope["matching_direction_evidence"].items()
                )
        for finding in layout.get("form_analysis", {}).get("findings", []):
            lines.append(
                f"对象{finding['object_id']} 形态判定：{finding['finding']}；依据：{finding['evidence']}"
            )
            lines.extend(
                f"{check['criterion']}：{check['finding']}；规则：{check['rule_id']}"
                for check in finding["checks"]
            )
        for finding in layout.get("element_remedies", []) + layout.get(
            "annual_remedies", {}
        ).get("findings", []):
            lines.append(
                f"对象{finding['object_id']} 元素方案：{finding['status']}；元素：{finding.get('introduced_element', '未生成')}；范围：{finding.get('application_scope', '条件不足或不适用')}"
            )
        for surface in layout.get("surface_analysis", {}).get("findings", []):
            lines.append(
                f"桌面{surface['object_id']} 目标{surface['goal']}；参考系：坐者近侧桌沿，不是罗盘落宫"
            )
            for option in surface["action_options"]:
                lines.append(
                    f"物件{option['item_id'] or '可选代表物'} {option['action']} → {option['to_zone_label']}；"
                    f"{option['status']}；规则{option['rule_id']}；{option['traditional_reason']}"
                )
            for item in surface["item_findings"]:
                if item["status"] == "no_independent_placement_rule":
                    lines.append(
                        f"物件{item['object_id']}：没有独立摆放规则，不按名称推断五行或吉侧"
                    )
        for proposal in layout.get("alternatives_analysis", {}).get("findings", []):
            lines.append(
                f"对象{proposal['object_id']} 候选{proposal['candidate_id']}：{proposal['status']}；计算{proposal['calculation_status']}；新位置形态独立核对，未沿用旧观察"
            )
        context = layout.get("environmental_context")
        for finding in layout.get("interior_analysis", {}).get("findings", []):
            lines.append(
                f"室内关系{finding['source_object_id']} → {finding['target_object_id']}："
                f"{finding['kind']}，{finding['status']}；规则{finding['rule_id']}；"
                f"动作{finding['action_status']}，按各对象独立核对。"
            )
        for finding in layout.get("material_analysis", {}).get("findings", []):
            lines.append(
                f"材质器形{finding['object_id']}：{finding['finding']}；"
                f"材料资格{finding['material_eligibility']}，颜色资格{finding['colour_eligibility']}；"
                "器形参考不等于实际尖角关系，代表物资格不认证摆位。"
            )
            application = finding.get("application_analysis")
            if application is not None:
                lines.append(
                    f"材料施用条件：{application['status']}；"
                    f"目标绑定：{application['target_binding']['status']}；"
                    "剂量、目标位置、摆放利弊与效力仍未评估。"
                )
        for finding in layout.get("workstation_analysis", {}).get("findings", []):
            if "activity" in finding:
                lines.append(
                    f"工位{finding['object_id']} 活动{finding['activity']}：{finding['status']}；"
                    f"角色{finding['selected_star_role']}；规则{finding['rule_id']}。"
                )
                lines.extend(
                    f"候选{c['candidate_id']} 落宫{finding['location_direction']}："
                    f"向星{c['selected_star_number']}／{c['star_element']}；"
                    f"山星{c['mountain_star_number']}；评价时运{c['timeliness']}；"
                    "不是综合吉凶或真实水装置需求。"
                    for c in finding.get("candidates", [])
                )
            else:
                lines.append(
                    f"入口隔挡{finding['entrance_id']} → {finding['desk_id']}，"
                    f"物件{finding['barrier_id']}：{finding['status']}；"
                    f"规则{finding['rule_id']}，不规定吉侧。"
                )
                lines.extend(
                    f"隔挡动作{a['operation']}：{a['status']}；"
                    f"受阻原因：{'、'.join(a['blocking_reasons']) or '无已确认阻碍'}；"
                    "执行许可、视野与通行分别核对。"
                    for a in finding["action_options"]
                )
        if "workstation_analysis" in layout:
            lines.append("WOFS非BTB桌面摆放仅作者参考，未启用摆放规则。")
        measured = layout.get("workstation_layout_analysis")
        if measured is not None:
            geometry = measured["geometry"]
            lines.append(
                f"实测工位：{measured['status']}；图纸{geometry['frame_id']}；"
                f"名义几何可行{geometry['physically_feasible']}；候选观察{geometry['candidate_only']}。"
            )
            for seat in geometry["seats"]:
                lines.append(
                    f"工位{seat['desk_id']}：按{seat['sector_anchor']}关联候选方区"
                    f"{'/'.join(seat['location_directions']) or '未绑定'}；"
                    f"实际位置与坐向分列，绑定状态{seat['chart_binding_status']}。"
                )
            for reading in measured["readings"]:
                lines.append(
                    f"工位{reading['desk_id']}／{reading['direction']}／候选{reading['chart_candidate_id']}："
                    f"历史{reading['historical_period_number']}运；评价运{reading['evaluation_period_number']}；"
                    f"{reading['conclusion']}"
                )
            for comparison in measured["rule_comparisons"]:
                if comparison["reference_frame"] in {
                    "seated_desktop_nine_cells",
                    "desktop_compass_not_house_palace",
                    "seated_right_with_higher_left_object",
                }:
                    lines.append(
                        f"桌面物件{comparison['object_id']}：{comparison['rule_id']}；"
                        f"{comparison['status']}；参考系{comparison['reference_frame']}，不与房间落宫混同。"
                    )
            search = measured.get("search")
            if search is not None:
                lines.append(
                    f"有限布局搜索：已算{search['evaluated_count']}个完整组合，"
                    f"拒绝{search['rejected_count']}个；完整枚举{search['enumeration_complete']}；"
                    f"显示{len(search['returned_candidate_ids'])}个取舍方案，"
                    f"另有{search['omitted_frontier_count']}个前沿方案未显示。"
                )
                for candidate in search["candidates"]:
                    lines.append(
                        f"方案{candidate['candidate_id']}：{candidate['status']}；"
                        f"直接调整{len(candidate['actions'])}个对象；不是综合吉凶或效果保证。"
                    )
        if context is not None:
            orientation = context["orientation_review"]
            lines.append(
                f"环境上下文：{context['status']}；实际分宫确认："
                f"{orientation['physical_sector_binding_allowed']}；人物象征对应不代替环境方位。"
            )
            for member in context["household_correspondences"]:
                for association in member["associations"]:
                    lines.append(
                        f"家庭成员{member['subject_id']}：主宫{association['primary_palace']}，"
                        f"对宫{association['opposite_palace']}为次级关注；"
                        f"实际落宫{association['physical_sector_binding']}；"
                        f"作用域{association['scope']}，非八宅个人命卦，不据此推断事件。"
                    )
            for influence in context["floor_review"]["influences"]:
                for scope in influence["subject_scope"]:
                    lines.append(
                        f"楼层影响{influence['influence_id']} 对{scope['subject_id']}："
                        f"{scope['status']}；共同因素不取消。"
                    )
            for finding in context["environment_findings"]:
                lines.append(
                    f"环境对象{finding['object_id']} {finding['feature']}："
                    f"{finding['finding']}；无独立规则不编绝对禁忌。"
                )
            lines.extend(context["limitations"])
        lines.extend(layout["limitations"])
        output.append(("布局计算", lines))
    output.append(
        (
            "冲突清单",
            [
                f"{c['direction']} {c['kind']}：{c['resolution']}"
                for c in result["conflicts"]
            ]
            or ["无已确认的方向差异；各方法保持独立作用范围"],
        )
    )
    output.append(
        (
            "覆盖范围",
            [
                "缺失输入：" + "、".join(result["coverage"]["missing_inputs"]),
                *(
                    [
                        "请求整体状态："
                        + result["coverage"]["requested_analysis_status"],
                        "布局缺失输入："
                        + "、".join(result["coverage"]["layout_missing_inputs"]),
                    ]
                    if "layout_status" in result["coverage"]
                    else []
                ),
                "未实现层：" + "、".join(result["coverage"]["unavailable_layers"]),
                *(
                    [
                        (
                            "场景范围：仅已提交对象与所选规则，不代表全宅审查；本次玄空只含有限五行、当令外局与床门条件，完整形势、门主灶结构及81组合断法尚未覆盖"
                            if result.get("layers", {})
                            .get("xuankong_natal", {})
                            .get("interpretation")
                            is not None
                            else "场景范围：仅已提交对象与所选规则，不代表全宅审查；完整形势、门主灶结构及宅盘组合解释尚未覆盖"
                        )
                    ]
                    if "scene_scope" in result["coverage"]
                    else []
                ),
            ],
        )
    )
    output.append(
        (
            "规则来源",
            [
                f"{ruleset['ruleset_id']}@{ruleset['version']} {source['source_id']} {source['title']} {source['url']}；范围：{source['scope']}"
                for ruleset in result["rulesets"]
                for source in ruleset["sources"]
            ],
        )
    )
    return output
