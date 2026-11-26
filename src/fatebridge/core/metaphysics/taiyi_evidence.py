"""Render the evidence retained on a Taiyi board."""

from typing import Any

from fatebridge.core.metaphysics.taiyi_civil_calendar import civil_lunar_text
from fatebridge.core.metaphysics.taiyi_conditions import conditions_text
from fatebridge.core.metaphysics.taiyi_counts import counts_text
from fatebridge.core.metaphysics.taiyi_cycles import counter_cycles_text
from fatebridge.core.metaphysics.taiyi_elemental_relations import (
    elemental_relations_text,
)
from fatebridge.core.metaphysics.taiyi_enclosures import enclosures_text
from fatebridge.core.metaphysics.taiyi_month import jinjing_month_origin_text
from fatebridge.core.metaphysics.taiyi_oppositions import oppositions_text
from fatebridge.core.metaphysics.taiyi_origin_selection import (
    winter_origin_selection_text,
)
from fatebridge.core.metaphysics.taiyi_shiji import shiji_derivation_text
from fatebridge.core.metaphysics.taiyi_source_alignment import source_alignment_text
from fatebridge.core.metaphysics.taiyi_ten_jing import ten_jing_text
from fatebridge.core.metaphysics.taiyi_victory_matrix import victory_matrix_text
from fatebridge.core.metaphysics.taiyi_year_calendar import historical_year_text


def evidence_text(board: dict[str, Any]) -> str:
    """Deterministic interpretation copied from the same board, never recast."""

    core = board["core_board"]
    calendar = board["calendar_rules"]
    mode = calendar.get("calculation_mode", "year")
    lines = [
        f"规则：{board['ruleset']['source_title']} / {board['ruleset']['id']}；{board['life_method']}。"
    ]
    if board.get("counter_cycles"):
        lines.append(counter_cycles_text(board["counter_cycles"]))
    if board.get("winter_origin_selection"):

        lines.append(winter_origin_selection_text(board["winter_origin_selection"]))
    resolution = calendar.get("civil_clock_resolution")
    if resolution:
        lines.append(
            f"民用时刻消歧：{resolution['wall_datetime']}，时区{resolution['timezone']}，"
            f"明确偏移{resolution['input_utc_offset']}，核对偏移{resolution['resolved_utc_offset']}，"
            f"fold={resolution['fold']}；实际UTC：{resolution['instant_utc']}。"
            + resolution["scope"]
        )
    if mode == "year":
        historical = calendar.get("historical_calendar")
        if historical:

            lines.append(historical_year_text(historical))
            lines.append(calendar["pillars_role"])
        else:
            lines.extend(
                [
                    f"年计岁首：农历正月初一（工程约定）；年干支：{calendar['year_ganzhi']}。",
                    f"年计采用钟表日期：{calendar['civil_datetime']}；农历年：{calendar['year']}，不随真太阳时跨日改变。",
                    civil_lunar_text(calendar["civil_lunar_calendar"]),
                ]
            )
    else:
        anchors = board.get("solar_anchors", {})
        if anchors:
            labels = {"boundary": "换节/换遁", "winter_origin": "冬至起元"}
            lines.append(
                "节气实际模型："
                + "；".join(
                    f"{labels.get(key, key)} {value['name']} "
                    f"{value['datetime_with_offset']} "
                    f"{value['resolution_provider']}/{value['ephemeris_model']}"
                    for key, value in anchors.items()
                )
                + "。"
                + board["solar_anchor_scope"]
            )
        lines.extend(
            [
                f"起点：{calendar['anchor_name']} / {calendar['anchor_utc']}；天文来源：{calendar['anchor_provider']}。",
                f"计数时钟：{calendar['clock_basis']}；所选计数：{calendar['counter']}。",
            ]
        )
        if mode == "hour":
            lines.append(
                f"时钟读数：{calendar['target_clock']}；至点时钟：{calendar['anchor_clock']}；{calendar['initial_interval']}。"
            )
            origin = calendar.get("hour_origin")
            if origin:
                lines.append(
                    f"时计配置：{calendar['hour_profile']}；冬至前甲子锚{origin['origin_effective_date']}，本次所属日{origin['target_effective_date']}（{origin['target_day_ganzhi']}）。"
                )
                lines.append(
                    f"完整积时：({origin['day_number']} - 1) × 12 + {origin['hour_number']} = {origin['accumulation']}；23时子初为现代约定。"
                )
        elif mode == "day":
            origin = calendar["day_origin"]
            lines.append(
                f"日计配置：{calendar['day_profile']}；冬至前甲子锚{origin['origin_effective_date']}，本次所属日{origin['target_effective_date']}（{origin['target_day_ganzhi']}），积{origin['accumulation']}日，不乘十二。"
            )
            lines.append(calendar["modern_conventions"])
            lines.append(calendar["pillars_role"])
        else:
            lines.append(f"月界：{calendar['leap_month_policy']}。")
            origin = calendar.get("month_origin")
            if origin and origin.get("profile") == "jinjing_month_jie_360_v1":

                lines.append(jinjing_month_origin_text(origin))
            elif origin:
                lines.append(
                    f"月计配置：{calendar['month_profile']}；完整积月({origin['annual_accumulation']} - 1) × 12 + 2 + {origin['nominal_month']} = {origin['accumulation']}；弘治17年截数为{origin['shortcut_count']}，相差{origin['full_minus_shortcut']}，按720月公周期同相位。"
                )
                lines.append(origin["year_label_policy"] + origin["scope"])
                reference = origin.get("calendar_reference")
                if reference:
                    lines.append(
                        f"朔月假设对照：{reference['source_label']}，独立历表月首儒略历{reference['lunar_month_start_julian']} → 推算公历{reference['lunar_month_start_gregorian']}，下月首{reference['next_lunar_month_start_gregorian']}；本盘节月名义序{reference['actual_nominal_month']}，所比历表农历月序{reference['source_month']}，一致标志{reference['month_label_matches']}。"
                    )
                    lines.append(
                        f"历表：{reference['calendar_authors']}《{reference['calendar_title']}》{reference['calendar_edition']}第{reference['calendar_printed_page']}页；{reference['calendar_source']}。{reference['scope']}"
                    )
    reference = calendar.get("historical_date_reference")
    if reference:
        lines.append(
            f"历史日期对照：{reference['source_date']}；儒略历{reference['western_source_date']} → 推算公历{reference['normalized_gregorian_date']}。"
            f"{reference['calendar_table_authors']}《{reference['calendar_table_title']}》{reference['calendar_table_edition']}第{reference['calendar_table_printed_page']}页；来源：{reference['calendar_table_source']}。"
        )
        lines.append(
            f"日期干支：原例{reference['source_day_ganzhi']}，本盘{reference['actual_day_ganzhi']}；积数：原例{reference['source_accumulation']}，本盘{reference['actual_accumulation']}。"
            + reference["scope"]
        )
    if board.get("shiji_derivation"):
        lines.append(shiji_derivation_text(board["shiji_derivation"]))
    for label, field in (("主算", "main"), ("客算", "guest")):
        trace = board["rule_trace"][field]
        path = " + ".join(f"{p['palace']}{p['value']}" for p in trace["path"])
        ending = (
            f"同宫取本宫数{trace['count']}"
            if not trace["terminal_excluded"]
            else f"止于{trace['terminal_palace']}宫前"
        )
        if "selected_count" in trace:
            lines.append(
                f"{label}卷二重算：{path} = {trace['count']}；{ending}。"
                f"本盘选用{label}{trace['selected_count']}；{trace['selected_count_basis']}。"
            )
        else:
            lines.append(f"{label}：{path} = {trace['count']}；{ending}。")
    lines.append(
        f"主大/主参：{core['main_general']}/{core['main_vice_general']}；客大/客参：{core['guest_general']}/{core['guest_vice_general']}。"
    )
    lines.extend(
        f"{p.get('variant', p['name'])}：{p['traditional_meaning']}；{p['scope']}。"
        for p in board["patterns"]
    )
    if board.get("count_assessment"):
        lines.append(counts_text(board["count_assessment"]))
    if board.get("victory_matrix_assessment"):

        lines.append(victory_matrix_text(board["victory_matrix_assessment"]))
    if board.get("elemental_guan_assessment"):

        lines.append(elemental_relations_text(board["elemental_guan_assessment"]))
    alignment = board.get("count_source_assessment")
    if alignment and (
        alignment["status"] == "not_assessed"
        or alignment["summary"]["status"] == "differences_unadjudicated"
        or alignment["facsimile_readings"]
    ):

        lines.append(source_alignment_text(alignment))
    lines.append(conditions_text(board["condition_assessment"]))
    if board.get("enclosure_assessment"):
        lines.append(enclosures_text(board["enclosure_assessment"]))
    if board.get("opposition_assessment"):
        lines.append(oppositions_text(board["opposition_assessment"]))
    lines.append(gates_text(board))
    if board.get("ten_jing"):

        lines.append(ten_jing_text(board["ten_jing"]))
    for comparison in board.get("day_source_comparisons", []):
        lines.append(
            f"{comparison['scope']} {comparison['field']}原文{comparison['source_value']}，本盘规则推算{comparison['rule_derived_value']}。"
        )
    lines.append("原典符合范围：部分，底本表文与通则分歧待裁定；现实预测效力：未检验。")
    return "\n".join(lines)


def gates_text(board: dict[str, Any]) -> str:
    gates = board["gates"]
    if gates["status"] != "computed":
        return f"太乙八门未计算：{gates['reason']}"
    counter = gates["counter"]
    lines = [
        f"太乙八门：{gates['selected_profile']}，积数{counter['accumulation']}，{counter['duty_gate']}门入第{counter['unit_in_gate']}计数单位。"
    ]
    is_key = gates["selected_profile"] in {
        "key_hour_four_gates_120_v1",
        "key_day_four_gates_120_v1",
        "key_month_eight_gates_240_v1",
    }
    label = {"day": "日计阴阳四门", "hour": "时计阴阳四门", "month": "月计八门"}.get(
        gates["calculation_mode"], "本计八门"
    )
    lines.append(
        f"所选门法：金钥匙{label}，直门加定计目。"
        if is_key
        else "所选门法：王希明卷一新术；三门主体补证：统宗卷二。"
    )
    lines.append(
        "；".join(
            f"{r['palace']}：{r['door']}门" for r in gates["moving_frame"]["rows"]
        )
    )
    for check in board["condition_assessment"]["three_gates"].get("checks", []):
        lines.append(
            f"{check['label']}在{check['position']}，按本门盘临{check['door']}门：{check['incomplete_kind'] or '未触发三门不具条款'}。"
        )
    if is_key:
        lines.append(board["condition_assessment"]["three_gates"]["reason"])
        for comparison in gates.get("source_comparisons", []):
            lines.append(
                f"月门原文差异：{comparison['field']}原文{comparison['source_value']}，本盘规则推算{comparison['rule_derived_value']}；原读数保留。"
            )
        for alternative in gates.get("source_counter_alternatives", []):
            lines.append(
                f"月门诊断：{alternative['epoch_basis']}；{alternative['accumulation']}按240门周得{alternative['cycle_position']}，为{alternative['duty_gate']}门第{alternative['unit_in_gate']}月。"
            )
    else:
        lines.append(
            "李法常开四盘及定计目加临门盘另列比较，未混成同一判断；定计大将门盘仅布门，三门主体未裁定。"
        )
    result = board["determinate_calculation"]
    if result["status"] == "computed":
        path = " + ".join(f"{p['palace']}{p['value']}" for p in result["trace"]["path"])
        lines.append(
            f"定计目{result['marker']}：{path} = {result['count']}；定计大/参将{result['general']}/{result['vice_general']}。"
        )
        lines.append("定计补证：金钥匙续集，不把重审之算当另一份独立证据。")
        for item in result.get("source_disagreements", []):
            lines.append(
                f"定计原文分歧：{item['field']}原文{item['source_value']}，按本盘算路{item['rule_derived_value']}；两值保留，未据程序改原文。"
            )
    return "\n".join(lines)
