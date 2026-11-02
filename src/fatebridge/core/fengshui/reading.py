"""Deterministic natal explanations with complete, same-response context quotes.

This renderer does not calculate a chart, authenticate an input, grade arbitrary
model prose, or turn a selected presence condition into a fortune verdict.
"""

from copy import deepcopy
from typing import Any, Dict, List

from fatebridge.utils.errors import FengshuiCalculationError

from .host_guest import statements as host_guest_statements
from .host_guest import validate as validate_host_guest
from .mutual_geometry import validate_author_geometries
from .opposite import OPPOSITE
from .source_comparison import comparison_statements

FORMAT = "fengshui_natal_calculation_reading_v1"
READING_VERSION = "1.2.0"
SUPPORTED_READING_VERSIONS = {"1.0.0", "1.1.0", READING_VERSION}
VERSIONS = {
    "xuankong_zhongzhou_v1": ("1.3.0", "1.4.0"),
    "xuankong_conditioned_v1": "1.0.0",
    "wang_zhongzhou_timeliness_v1": ("1.0.0", "1.1.0"),
    "shen_fixed_lingzheng_v1": "1.0.0",
    "shen_2011_host_guest_v1": "1.0.0",
    "shen_city_gate_v1": "1.0.0",
    "shen_2011_lower_numeric_comparison_v1": "1.0.0",
    "shen_2011_natal_numeric_comparison_v2": "2.0.0",
}
TIMELINESS = {
    "current": "当令",
    "not_current": "非当令（不等于凶）",
    "unknown": "评价运未确认，未判当令",
}
RELATIONS = {
    "same_element": "山向同五行",
    "mountain_generates_facing": "山星生向星",
    "facing_generates_mountain": "向星生山星",
    "mountain_controls_facing": "山星克向星",
    "facing_controls_mountain": "向星克山星",
}
PRESENCE = {
    "not_applicable_center": "中宫不适用八方外局条件",
    "needs_current_period": "评价运未确认，不能核定当令外局",
    "rule_not_covered_not_inauspicious": "不在本条存在规则覆盖内，不据此判凶",
    "needs_confirmation": "存在事实仍待确认",
    "candidate_only": "仅为候选，不能当作已确认",
    "matches_presence_requirement": "指定存在条件满足，未评价完整形势质量",
    "required_form_absent": "指定存在条件未满足，不等于整体不利",
    "selected_presence_matched": "指定存在条件满足，未评价完整形势质量",
    "selected_presence_not_matched": "指定存在条件未满足，不等于整体不利",
    "not_requested": "没有提交该现场观察",
    "selected_pattern_matched": "指定水形条件符合，未评价完整纳气与形势",
    "selected_pattern_not_matched": "指定水形条件未符合，不等于整体不利",
}


def _get(payload: Dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


def _boolean(value: Any) -> str:
    if value is True:
        return "符合"
    if value is False:
        return "不符合"
    if value is None:
        return "尚未确认"
    raise ValueError("不支持非布尔条件")


def _period(value: Any) -> str:
    if value is None:
        return "未确认"
    if type(value) is not int or value not in range(1, 10):
        raise ValueError("不支持的运数")
    return f"{value}运"


def _condition_text(condition: Dict[str, Any]) -> str:
    text = PRESENCE[condition["status"]]
    labels = {
        "high_solid_terrain_present": "高实",
        "low_lying_terrain_present": "低洼",
        "river_water_present": "外部河流",
    }

    def observed(value: Any) -> str:
        if value is True:
            return "存在"
        if value is False:
            return "不存在"
        if value is None:
            return "未确认"
        raise ValueError("不支持的观察值")

    if "observed" in condition and condition["status"] != "not_applicable_center":
        facts = condition["observed"]
        text += "；观察记录为" + (
            "、".join(labels[key] + observed(value) for key, value in facts.items())
            if isinstance(facts, dict)
            else observed(facts)
        )
    for name, label in (
        ("raw_condition_match", "本候选存在条件运算"),
        ("raw_pattern_match", "原始水形运算"),
    ):
        if name in condition:
            text += f"；{label}{_boolean(condition[name])}，不替代观察或适用性的确认"
    return text


def _numeric_statements(chart: Dict[str, Any]) -> List[tuple[str, str, str]]:
    """Describe returned relations, without recomputing or extending the rules."""
    statements = []
    structure = chart["structure"]
    directions = {"C", "N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    pairs = structure["combination_of_ten"]
    patterns = structure["classical_patterns"]
    if (
        len(pairs) != 3
        or {(p["left_role"], p["right_role"]) for p in pairs}
        != {("period", "mountain"), ("period", "facing"), ("mountain", "facing")}
        or any(set(p["palace_sums"]) != directions for p in pairs)
        or set(patterns["parental_triples"]["palaces"]) != directions
        or set(patterns["ground_comparison"]["roles"]) != {"mountain", "facing"}
        or set(patterns["ground_comparison"]["reference_numbers"]) != directions
    ):
        raise ValueError("固定数式释义需要完整三对、九宫和两侧参照")
    roles = {"period": "历史运星", "mountain": "山星", "facing": "向星"}
    for index, pair in enumerate(structure["combination_of_ten"]):
        left, right = pair["left_role"], pair["right_role"]
        evidence = "、".join(
            f"{d}:{chart[left + '_chart'][d]}+{chart[right + '_chart'][d]}={total}"
            for d, total in pair["palace_sums"].items()
        )
        statements.append(
            (
                "numeric_sum_ten",
                f"structure.combination_of_ten.{index}",
                f"{roles[left]}与{roles[right]}九宫全部同宫合十：{_boolean(pair['all_nine_sum_to_ten'])}；逐宫原数与已算数和为{evidence}。全盘条件不符合不表示没有局部合十；这也不是异宫对角合十、完整夫妇用法或现实吉凶。",
            )
        )
    parental = patterns["parental_triples"]
    statements.append(
        (
            "parental_summary",
            "structure.classical_patterns.parental_triples",
            f"全局父母三般卦数字条件：{_boolean(parental['all_nine_match'])}；须九宫各自具足所列{parental['groups']}之一的三个不同星数。局部组别、普通连续三数组、七星打劫及实际取用分别处理，不由本标记推定后三者已成立。",
        )
    )
    for direction, palace in parental["palaces"].items():
        group = palace["matched_group"]
        label = f"匹配父母组{group}" if group is not None else "未匹配所列父母组"
        statements.append(
            (
                "parental_palace",
                f"structure.classical_patterns.parental_triples.palaces.{direction}",
                f"{direction}宫历史运、山、向原数依次为{palace['ordered_period_mountain_facing']}，{label}；本宫状态不能代替九宫全局条件，也不表示此处吉凶。",
            )
        )
    for role, comparison in patterns["ground_comparison"]["roles"].items():
        statements.append(
            (
                "numeric_refrain",
                f"structure.classical_patterns.ground_comparison.roles.{role}",
                f"{roles[role]}与固定洛书地盘全盘同数（伏吟数式）：{_boolean(comparison['whole_ground_repeat'])}，同数宫位{comparison['same_ground_directions']}；固定地盘全盘对数（反吟数式）：{_boolean(comparison['whole_ground_reverse'])}，对数外宫{comparison['opposite_ground_directions']}。全盘对数的中宫仅是数值条件，中宫没有空间对宫；外宫列表不含中宫。另与本宅历史运盘全盘同数：{_boolean(comparison['whole_period_plate_same'])}，同数宫位{comparison['period_plate_same_directions']}。三种比较独立；全盘不符合不抹掉局部匹配，不把历史运盘当固定地盘或当前评价运。",
            )
        )
    named = patterns["volume_two_named_refrain"]
    if named["applicable"] is not (chart["chart_mode"] == "lower"):
        raise ValueError("下卦局名适用范围与候选模式不一致")
    if named["applicable"]:
        label = (
            f"卷二所列下卦反伏局名的有限数字对应：{_boolean(named['numeric_match'])}"
        )
    else:
        if named["numeric_match"] is not None:
            raise ValueError("替卦不能冒用下卦名单的布尔结论")
        label = (
            "替卦不适用此段下卦局名名单，对应状态未判定；未判定不等于数式不存在或不利"
        )
    endpoints = "、".join(
        f"{roles[role]}在{named['endpoint_evidence'][key]['direction']}宫为{named['endpoint_evidence'][key]['star_number']}，固定地盘数{named['endpoint_evidence'][key]['ground_number']}"
        for key, role in (
            ("mountain_at_sitting", "mountain"),
            ("facing_at_facing", "facing"),
        )
    )
    statements.append(
        (
            "named_refrain",
            "structure.classical_patterns.volume_two_named_refrain",
            f"{label}。原始端点为{endpoints}；本侧坐向两端各与地盘对数的条件{_boolean(named['own_role_sitting_facing_both_opposite_ground'])}，存在固定地盘全盘同数的条件{_boolean(named['whole_ground_repeat_present'])}。局部对宫与全盘数式分别保留；本段名单不覆盖各作者全部反伏用语，不能以未对应名单宣称原典一概没有反伏吟。",
        )
    )
    return statements


def _opposite_statements(chart: Dict[str, Any]) -> List[tuple[str, str, str]]:
    comparison = chart["structure"]["classical_patterns"]["opposite_star_comparison"]
    root = "structure.classical_patterns.opposite_star_comparison"
    directions = {"N", "NE", "E", "SE", "S", "SW", "W", "NW"}
    if set(comparison["pairs"]) != directions or comparison["spatial_pair_count"] != 8:
        raise ValueError("对宫释义须保留八个有向配对，不能只取四轴或中宫")
    center = comparison["center_numeric_pair"]
    if (
        center["spatial_opposite_exists"] is not False
        or center["included_in_spatial_conjunction"] is not False
    ):
        raise ValueError("中宫不能充当空间对宫或混入八宫合取")
    statements = [
        (
            "opposite_star_summary",
            root,
            f"山向异宫对角合十的八个有向对宫条件：{_boolean(comparison['all_eight_sum_to_ten'])}；本条逐一比较某宫山星与其对宫向星，不是同宫求和。中宫仅作数字相加{center['mountain_star_number']}+{center['facing_star_number']}={center['sum']}，数和为十条件{_boolean(center['matches_sum_to_ten'])}；中宫无空间对宫，不参与八宫合取。本条数式不等于所有反吟定义，不能代替同宫合十、父母组或原书局名；替卦仅显示算数关系，不继承原书下卦例盘或应期裁决。",
        )
    ]
    for direction, pair in comparison["pairs"].items():
        if (
            pair["mountain_direction"] != direction
            or pair["facing_direction"] != OPPOSITE[direction]
        ):
            raise ValueError("对宫配对的目标或参照宫不完整")
        statements.append(
            (
                "opposite_star_pair",
                root + ".pairs." + direction,
                f"山星{pair['mountain_star_number']}在{pair['mountain_direction']}宫，配对向星{pair['facing_star_number']}在{pair['facing_direction']}宫，已算数和{pair['sum']}，对宫合十条件{_boolean(pair['matches_sum_to_ten'])}；这是有方向的两星配对，不据此作整体吉凶判断。",
            )
        )
    return statements


def build_natal_reading(
    payload: Dict[str, Any], *, version: str = READING_VERSION
) -> Dict[str, Any]:
    """Read every natal candidate and requested sublayer; never select the best.

    All field quotations are separate from the generated prose. A verifier can
    compare both against the full original response and a trusted receipt.
    """
    basis: Dict[str, Any] = {}
    statements: List[Dict[str, Any]] = []

    def quote(path: str) -> str:
        if path not in basis:
            basis[path] = deepcopy(_get(payload, path))
        return path

    def add(
        kind: str, text: str, paths: List[str], target_path: str | None = None
    ) -> None:
        target = target_path or paths[0]
        statements.append(
            {
                "kind": kind,
                "target_path": target,
                "text": text,
                "basis_paths": list(dict.fromkeys(quote(p) for p in [*paths, target])),
            }
        )

    try:
        if version not in SUPPORTED_READING_VERSIONS:
            raise ValueError("未支持的固定释义版本")
        root = "layers.xuankong_natal"
        natal = _get(payload, root)
        registered = {r["ruleset_id"]: r for r in payload["rulesets"]}

        def require(key: str, record: Dict[str, Any] | None = None) -> None:
            expected = VERSIONS[key]
            allowed = (expected,) if isinstance(expected, str) else expected
            if registered[key]["version"] not in allowed:
                raise ValueError("未支持的规则版本")
            if record is not None and any(
                record.get(field) != registered[key].get(field)
                for field in ("ruleset_id", "version", "source_ids")
            ):
                raise ValueError("分支规则与来源登记不一致")

        require("xuankong_zhongzhou_v1", natal["ruleset"])
        comparison = natal.get("source_comparison")
        if comparison is not None:
            comparison_profile = comparison["ruleset"]["ruleset_id"]
            if comparison_profile not in {
                "shen_2011_lower_numeric_comparison_v1",
                "shen_2011_natal_numeric_comparison_v2",
            }:
                raise ValueError("未支持的原书数字比较版本")
            require(comparison_profile, comparison["ruleset"])
            comparison_root = root + ".source_comparison"
            for target, text in comparison_statements(comparison):
                paths = [
                    comparison_root + ".ruleset",
                    comparison_root + ".summary",
                    comparison_root + "." + target,
                ]
                if target.startswith("candidates."):
                    paths.append(root + "." + target)
                add("source_comparison", text, paths, comparison_root + "." + target)
        add(
            "sources",
            "本释义仅解释已选择的玄空计算及其子层；来源、版本与作用域如下。不能据此认证原典全本、历法精度、完整现场或现实预测。",
            ["rulesets"],
        )
        add(
            "natal_context",
            f"历史宅运为{_period((natal.get('period_context') or {}).get('number'))}；它用于本宅盘起盘，不能当作当前评价运。方位、误差及缺失项仍按原运行记录读取。",
            [
                root + ".period_context",
                root + ".orientation_context",
                root + ".status",
                root + ".missing_inputs",
            ],
        )
        period = natal.get("period_context") or {}
        if period.get("effective_event_year_status") == "requires_confirmation":
            years = "、".join(map(str, period["candidate_effective_event_years"]))
            conclusion = (
                f"所有候选年均属{_period(period['number'])}，宅运已确定；事件有效年仍未确认。"
                if period["number"] is not None
                else "候选年跨运，历史宅运仍待确认。"
            )
            add(
                "natal_event_year",
                f"事件有效年候选为{years}；{conclusion}模型暂取年仅供追踪，不作为已确认事实。",
                [root + ".period_context"],
            )
        charts = natal.get("candidates", [])
        for index, chart in enumerate(charts):
            distribution = chart["structure"]["distribution"]
            qualifier = "待确认候选" if len(charts) > 1 else "本次计算候选"
            add(
                "natal_distribution",
                f"{qualifier}{chart['candidate_id']}，历史{_period(chart['period_number'])}：历史当运山星在{distribution['mountain_period_star_direction']}，向星在{distribution['facing_period_star_direction']}，数字结构为{distribution['traditional_label']}。这不是当前旺衰或现场吉凶。",
                [f"{root}.candidates.{index}"],
            )
            if version != "1.0.0":
                prefix = f"{qualifier}{chart['candidate_id']}，历史{_period(chart['period_number'])}、{ {'lower': '下卦', 'replacement': '替卦'}[chart['chart_mode']]}："
                for kind, target, text in _numeric_statements(chart):
                    add(
                        kind,
                        prefix + text,
                        [f"{root}.candidates.{index}"],
                        f"{root}.candidates.{index}.{target}",
                    )
                if version == "1.2.0":
                    for kind, target, text in _opposite_statements(chart):
                        add(
                            kind,
                            prefix + text,
                            [f"{root}.candidates.{index}"],
                            f"{root}.candidates.{index}.{target}",
                        )
        if not charts:
            add(
                "missing_natal",
                "尚无可解释的历史宅盘候选，不能补造星数或宫位；独立子层已返回的事实仍可分别解释。",
                [root + ".missing_inputs"],
            )
        interpretation = natal.get("interpretation")
        if interpretation is not None:
            validate_author_geometries(
                interpretation,
                natal,
                current=interpretation["current_period_context"]["number"],
            )
            validate_host_guest(interpretation, natal)
            require("xuankong_conditioned_v1")
            ir = root + ".interpretation"
            current = interpretation["current_period_context"]["number"]
            add(
                "evaluation_context",
                f"当前评价运为{_period(current)}，与历史宅运分开。非当令不表示皆凶；基础层仅核对指定存在条件，不生成全宅综合吉凶或动作许可。",
                [
                    ir + ".current_period_context",
                    ir + ".limitations",
                    ir + ".missing_inputs",
                    ir + ".overall_auspiciousness",
                ],
            )
            if interpretation.get("timeliness_ruleset"):
                require(
                    "wang_zhongzhou_timeliness_v1", interpretation["timeliness_ruleset"]
                )
                add(
                    "author_scope",
                    "王亭之基本旺生衰死表与先后天互用数字分别读取，互用不改基本标签，也不证明现场可用；原书所登记的未解决表文差异仍保留。",
                    [ir + ".timeliness_ruleset"],
                )
            for ci, candidate in enumerate(interpretation["candidates"]):
                for direction, palace in candidate["palaces"].items():
                    pair = palace["ordered_pair"]
                    qualifier = (
                        "（宅盘待确认候选）" if candidate["candidate_only"] else ""
                    )
                    text = f"{candidate['candidate_id']}{qualifier}，历史{_period(candidate['natal_period_number'])}、评价{_period(current)}，{direction}宫：山星{palace['mountain_star_number']}为{TIMELINESS[palace['timeliness']['mountain']['status']]}，向星{palace['facing_star_number']}为{TIMELINESS[palace['timeliness']['facing']['status']]}；{RELATIONS[pair['relationship']]}，不由生克直接断吉凶。山形：{_condition_text(palace['external_form_analysis']['mountain'])}；水形：{_condition_text(palace['external_form_analysis']['water'])}。"
                    for role, label in (("mountain", "山星"), ("facing", "向星")):
                        author = palace["timeliness"][role].get("author_classification")
                        if author:
                            mutual = (
                                "互用数字未确定"
                                if author["current_period_number"] is None
                                else f"互用数字为{author['mutual_use_reference']['period_numbers']}"
                            )
                            text += f"王氏{label}基本时令为{author['traditional_label'] or '未定'}，术语仅指时令；{mutual}，本星成员条件{_boolean(author['mutual_use_reference']['numeric_membership'])}，仅为数字参考，不证明现场可用。"
                    add(
                        "natal_palace",
                        text,
                        [f"{ir}.candidates.{ci}", ir + ".current_period_context"],
                        f"{ir}.candidates.{ci}.palaces.{direction}",
                    )
                    if version == "1.2.0" and (
                        interpretation.get("timeliness_ruleset", {}).get("version")
                        == "1.1.0"
                    ):
                        for role, label in (("mountain", "山星"), ("facing", "向星")):
                            geo = palace["timeliness"][role]["author_classification"][
                                "mutual_use_reference"
                            ]["geometry"]
                            if geo["status"] == "unknown_evaluation_period":
                                detail = "评价运未确认，未选择先后天互用图位。"
                            elif geo["status"] == "literal_table_only_no_fifth_trigram":
                                detail = f"五运仅列原表数字{geo['printed_period_numbers']}；八卦图没有第五卦，本次未补造五黄寄宫或两条图位推导。"
                            elif geo["status"] == "derived_from_two_diagram_overlaps":
                                labels = {
                                    "earlier_heaven": "先天",
                                    "later_heaven": "后天",
                                }
                                parts = [
                                    f"{labels[p['current_layout']]}{p['current_trigram']}在图位{p['diagram_direction']}，同位为{labels[p['coincident_layout']]}{p['coincident_trigram']}，对应{p['coincident_star_number']}星"
                                    for p in geo["paths"]
                                ]
                                detail = (
                                    "；".join(parts)
                                    + f"；原表数字{geo['printed_period_numbers']}，图位有向推导次序{geo['diagram_derived_numbers']}，数字成员相合不表示两条路径可以交换。"
                                )
                            else:
                                raise ValueError("未支持的先后天图位状态")
                            add(
                                "mutual_use_geometry",
                                f"{candidate['candidate_id']}{qualifier}，{direction}宫{label}{geo['star_number']}：{detail}这是传统图位的来源说明，不认证现场北向、实际落宫、可用与否或动作许可。",
                                [
                                    ir + ".timeliness_ruleset",
                                    f"{ir}.candidates.{ci}",
                                    ir + ".current_period_context",
                                ],
                                f"{ir}.candidates.{ci}.palaces.{direction}.timeliness.{role}.author_classification.mutual_use_reference.geometry",
                            )
                for pi, placement in enumerate(candidate["placement_findings"]):
                    purpose = {"bed": "床", "door": "门", "desk": "桌", "stove": "灶"}[
                        placement["purpose"]
                    ]
                    if placement["status"] == "unsupported":
                        text = f"{candidate['candidate_id']}（历史{_period(candidate['natal_period_number'])}、评价{_period(current)}）的第{pi+1}项{purpose}用途：本有限床门规则不覆盖该用途，不能外推床门取用规则。"
                    elif placement["status"] == "needs_location":
                        text = f"{candidate['candidate_id']}（历史{_period(candidate['natal_period_number'])}、评价{_period(current)}）的第{pi+1}项{purpose}用途：全宅中心落宫未确认，朝向不能代替位置，未据此补出用途星数。"
                    else:
                        role = {"mountain": "山星", "facing": "向星"}[
                            placement["selected_star_role"]
                        ]
                        qualifier = "（仅候选）" if placement["candidate_only"] else ""
                        text = f"{candidate['candidate_id']}（历史{_period(candidate['natal_period_number'])}、评价{_period(current)}）的第{pi+1}项{purpose}用途{qualifier}：落宫{placement['location_direction']}，本规则取{role}{placement['selected_star_number']}；{_condition_text(placement['external_form_condition'])}，不生成整体适用结论或移动许可。"
                    add(
                        "placement_role",
                        text,
                        [f"{ir}.candidates.{ci}", ir + ".current_period_context"],
                        f"{ir}.candidates.{ci}.placement_findings.{pi}",
                    )
            host_guest = interpretation.get("host_guest_analysis")
            if host_guest is not None and version == READING_VERSION:
                require("shen_2011_host_guest_v1", host_guest["ruleset"])
                hr = ir + ".host_guest_analysis"
                add(
                    "host_guest_scope",
                    "本次另选整理本所收主客定义：坐山宫论山主、向首宫论向主，地盘与运盘等层次分别计算；旁六宫和中宫不套此主客规则。生入、生出不同于王氏时令之生，不合并书内相争的吉凶口径。",
                    [
                        hr + ".ruleset",
                        hr + ".scope",
                        hr + ".evaluation_timeliness_applied",
                    ],
                )
                for kind, target, text in host_guest_statements(host_guest):
                    add(
                        kind,
                        text,
                        [hr, root + ".candidates"],
                        hr + "." + target,
                    )
            fixed = interpretation.get("fixed_lingzheng_analysis")
            if fixed is not None:
                require("shen_fixed_lingzheng_v1", fixed["ruleset"])
                fr = ir + ".fixed_lingzheng_analysis"
                add(
                    "fixed_context",
                    f"固定零正参考评价运为{_period(fixed['reference_period_number'])}；它是固定地盘，不代替随运、随向变化的山向飞星。五运分段未知时保留两组候选，不选取较有利结果。",
                    [
                        fr + ".ruleset",
                        fr + ".selection_status",
                        fr + ".reference_period_number",
                        fr + ".reference_frame",
                        fr + ".missing_inputs",
                    ],
                )
                for vi, variant in enumerate(fixed["candidates"]):
                    qualifier = (
                        "分段未确认的候选"
                        if variant["candidate_only"]
                        else "本次固定方位"
                    )
                    half = {
                        None: "非五运分段",
                        "first_decade": "五运前十年",
                        "second_decade": "五运后十年",
                    }[variant["five_period_half"]]
                    for direction, palace in variant["palaces"].items():
                        if palace["role"] == "not_selected":
                            continue
                        label = {"zheng": "正神高实", "ling": "零神低洼河流"}[
                            palace["role"]
                        ]
                        text = f"{qualifier}，固定评价{_period(fixed['reference_period_number'])}，{half}，{direction}的{label}条件：{_condition_text(palace['form_assessment'])}。正神数{variant['zheng_number']}原宫{variant['zheng_native_palace']}、应用宫{variant['zheng_direction']}；零神数{variant['ling_number']}应用宫{variant['ling_direction']}。"
                        for comparison in palace["flying_star_comparisons"]:
                            chart_candidate = (
                                fixed["flying_star_comparison_status"]
                                == "candidate_only"
                            )
                            if comparison["candidate_only"] != (
                                chart_candidate or variant["candidate_only"]
                            ):
                                raise ValueError("固定零正比较的候选上下文不一致")
                            comparison_qualifier = (
                                "（宅盘与分段均为候选）"
                                if chart_candidate and variant["candidate_only"]
                                else (
                                    "（宅盘仍为候选）"
                                    if chart_candidate
                                    else (
                                        "（仅本分段候选下的比较）"
                                        if variant["candidate_only"]
                                        else "（本次计算宅盘）"
                                    )
                                )
                            )
                            text += f"对照宅盘{comparison['candidate_id']}{comparison_qualifier}：同类角色{comparison['matching_current_star_roles']}，不同类角色{comparison['different_current_star_roles']}；只比较要求类别，不表示条件等价、实际冲突或相互抵消。"
                        add(
                            "fixed_form",
                            text,
                            [
                                f"{fr}.candidates.{vi}",
                                fr + ".selection_status",
                                fr + ".flying_star_comparison_status",
                            ],
                            f"{fr}.candidates.{vi}.palaces.{direction}",
                        )
        city = natal.get("city_gate_analysis")
        if city is not None:
            require("shen_city_gate_v1", city["ruleset"])
            cr = root + ".city_gate_analysis"
            add(
                "city_context",
                f"城门独立参考运为{_period(city['reference_period_context']['number'])}，不重置历史宅运；数字与水形条件分别读取，不据数字符合推导现场已经合格。",
                [
                    cr + ".ruleset",
                    cr + ".reference_period_context",
                    cr + ".missing_inputs",
                    cr + ".limitations",
                ],
            )
            for ci, candidate in enumerate(city["candidates"]):
                for gi, gate in enumerate(candidate["gates"]):
                    qualifier = (
                        "方位待确认候选"
                        if candidate["candidate_only"]
                        else "本次方位候选"
                    )
                    text = f"{qualifier}，城门参考{_period(city['reference_period_context']['number'])}，宅向{candidate['facing']['name']}，{gate['mountain']['name']}城门逆飞数字条件{_boolean(gate['reference_star_reaches_gate_by_reverse_flight'])}；水形：{_condition_text(gate['form_assessment'])}；结合条件{_boolean(gate['combined_condition_match'])}。符合仅限该条数字或存在条件，不证明完整纳气、现实效果或开门许可。"
                    add(
                        "city_gate",
                        text,
                        [f"{cr}.candidates.{ci}", cr + ".reference_period_context"],
                        f"{cr}.candidates.{ci}.gates.{gi}",
                    )
        return {
            "format_id": FORMAT,
            "version": version,
            "status": "rendered",
            "covered_layers": ["xuankong_natal"],
            "uncovered_layers": [
                name for name in payload["layers"] if name != "xuankong_natal"
            ],
            "uncovered_topics": [
                "layout_actions",
                "material_remedies",
                "whole_site_quality",
                "free_model_prose",
                "real_world_events",
                *(
                    [
                        "ordinary_triples_usage",
                        "seven_star_robbery",
                        "authored_fortune_verdicts",
                    ]
                    if version != "1.0.0"
                    else []
                ),
            ],
            "basis": basis,
            "statements": statements,
            "text": "\n".join(s["text"] for s in statements),
            "scope": "fixed_templates_only_not_arbitrary_model_prose_or_real_world_prediction",
        }
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        AttributeError,
        FengshuiCalculationError,
    ) as exc:
        return {
            "format_id": FORMAT,
            "version": version,
            "status": "unsupported_context",
            "basis": {},
            "statements": [],
            "text": "现有资料或规则版本不符合本固定释义合同，未生成释义；原计算结果仍保留。",
            "reason": type(exc).__name__,
            "scope": "no_fidelity_acceptance_from_unsupported_context",
        }
