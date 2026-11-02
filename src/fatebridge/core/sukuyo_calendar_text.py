"""Literal T1299 calendar variants and black/white day evidence.

The printed 28-mansion month table is an alternative textual witness, never an
astronomical position and never silently substituted into the 27-mansion 三九法.
Civil clock boundaries are not inferred from prose saying day/night/midday.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_arc_clock import arc_clock_reference
from fatebridge.core.sukuyo_commentarial_clock import (
    commentarial_boundary_lines,
    commentarial_boundary_reference,
)
from fatebridge.core.sukuyo_date_support import input_timezone_reading
from fatebridge.core.sukuyo_documentary import (
    clock_position_reference,
    japanese_calendar_comparison,
    text_placement_label,
)
from fatebridge.core.sukuyo_futen_clock import futen_clock_lines, futen_clock_reference
from fatebridge.core.sukuyo_general_days import general_day_evidence
from fatebridge.core.sukuyo_guchureki_clock import clock_arithmetic_reference
from fatebridge.core.sukuyo_senmyo_phase import (
    phase_annotation_lines,
    phase_annotation_reference,
)
from fatebridge.core.sukuyo_sources import load_source
from fatebridge.core.sukuyo_waterclock import (
    source_specific_time_lines,
    source_specific_time_reference,
)

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_days.json"
COMPARATIVE_TIME_SOURCE = (
    Path(__file__).resolve().parents[1] / "data/sukuyo_comparative_time_units.json"
)
_ACTIVITY_DETAIL_LABELS = {
    "tailoring_garments": "裁衣",
    "making_garments": "制作衣服",
    "repairing_garments": "修补衣服",
    "wearing_garments": "穿衣",
    "wearing_new_garments": "穿新衣",
    "royal_wearer": "王者着衣",
    "sale": "出售",
    "borrowing": "借入",
    "lending": "借出",
    "earning_money": "求财",
    "sale_lactating_livestock": "出售乳畜",
    "sale_livestock": "出售牲畜",
    "spending_property": "支出财物",
    "receiving_property": "收取财物",
    "returning_property": "归还财物",
    "wealth_competition": "争财",
    "purchase": "购入",
    "business_operation": "经营",
    "collecting_debt": "索取债款",
    "repaying_debt": "偿还债款",
    "purchase_precious_goods": "购入金宝",
    "purchase_livestock": "购入牲畜",
    "land_purchase": "购入田地",
    "land_sale": "出售田地",
    "long_distance_journey": "远行",
    "journey_abroad": "出国",
    "personal_departure": "自家出行",
    "private_journey": "私事出行",
    "royal_or_official_traveler": "王者或使者出行",
    "long_distance_traveler_entering_residence": "远行者入宅",
    "southbound_journey": "向南出行",
    "northbound_journey": "向北出行",
    "eastbound_journey": "向东出行",
    "westbound_journey": "向西出行",
    "water_journey": "水路出行",
    "diplomatic_mission": "使节任务",
    "skill_learning": "学习技艺",
    "founding_school": "设立学舍",
    "beginning_study": "入学",
    "learning_with_teacher": "从师学习",
    "religious_learning": "宗教学法",
    "monastic_dharma_request": "出家人求法",
    "teaching_classics": "教授经典",
    "riding_training": "学习骑乘",
    "social_gathering": "聚会",
    "forming_friendship": "结交朋友",
    "classical_text_study": "研读经典",
    "debate_learning": "学习论辩",
}


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def source_digest() -> str:
    return load_source(SOURCE).sha256


def _input_reference_lines(calendar: dict[str, Any]) -> list[str]:
    """Distinguish observed input from the reference date used by lookups."""
    reference_date = calendar["calendar_date"]
    reference_zone = calendar.get("calendar_timezone")
    if not reference_zone:
        return []
    if (
        calendar.get("input_origin")
        == "derived_calendar_date_candidate_not_observed_birth_date"
    ):
        return [
            f"此支为{reference_zone}参考历日{reference_date}的推导候选；"
            "不是另一个已观测的出生日期，也没有补造出生钟时。"
        ]
    moment = calendar.get("input_datetime")
    precision = input_timezone_reading(calendar)
    prefix = [precision] if precision else []
    if moment:
        date_relation = (
            "换算后参考历日与输入当地日期不同"
            if calendar.get("input_date") != reference_date
            else "换算后参考历日与输入当地日期相同"
        )
        return prefix + [
            f"已知输入民用时刻为{moment}（输入时区{calendar['input_timezone']}）；"
            f"将同一时刻换算至所选宿主时区{reference_zone}，参考历日为{reference_date}，{date_relation}。"
            "输入时区不自动选择宿主历法；本次七曜与特殊日索引均按该参考历日。",
            "本次以已知时刻的单一瞬间确定参考日。未知钟时则须取输入当地整日的完整UTC原像，"
            "保留全部非空参考日期及其支持区间，不能用零时、正午、最长区间或本次已知时刻替代整天。"
            "这是两种输入模式的区别说明，本次未另算未知钟时结果。",
            "已知民用钟时不表示已确定古代平明日界，也不据此自动判定原典前后半日。",
        ]
    if calendar.get("input_date"):
        return prefix + [
            f"仅知输入当地日期{calendar['input_date']}（输入时区{calendar['input_timezone']}），"
            f"未提供出生钟时；本支查表按{reference_zone}参考历日{reference_date}，未补造钟时或古代日界。"
        ]
    return []


def hinoo_unassigned_month_start_lines(
    calendar: dict[str, Any], profile: dict[str, Any]
) -> list[str]:
    """Explain an unneeded split using the predecessor already in the trace."""
    if (
        not profile.get("hinoo_source")
        or calendar.get("lunar_day") != 1
        or profile.get("short_month_assignment") is not None
    ):
        return []
    trace = next(
        (
            row
            for row in calendar.get("rule_trace", [])
            if row.get("rule_id") == "t2465_repeat_and_short_month_assignment"
        ),
        None,
    )
    previous = trace["inputs"].get("previous_lunar") if trace else None
    if previous is None:
        return []
    month_label = "大" if previous["lunar_day"] == 30 else "小"
    month_label += "闰月" if previous["is_leap_month"] else "月"
    return [
        f"本次初一所用前一参考日为{previous['calendar_date']}，"
        f"农历{previous['lunar_year']}年"
        f"{'闰' if previous['is_leap_month'] else ''}"
        f"{previous['lunar_month']}月{previous['lunar_day']}日；"
        f"相邻前月为{previous['lunar_day']}日{month_label}。"
        + (
            "前月没有缺失第三十日，本次未生成小月分宿，仍按实际档案结果交付；"
            if previous["lunar_day"] == 30
            else "本次未生成小月分宿，所列相邻前月事实与档案分配状态分别保留；"
        )
        + "这不确定原典半日钟时或闰小月优先次序。"
    ]


def _hinoo_critical_lines(reference: dict[str, Any]) -> list[str]:
    primary = reference["selected_primary"]
    comparisons = reference["selected_example_comparisons"]

    def examples(field: str) -> str:
        return "、".join(
            f"{r['lunar_month']}月{r['lunar_day']}日{r[field]}" for r in comparisons
        )

    lines = [
        f"京都大学藏《{primary['title']}》第{primary['canvas_index_one_based']}幅所选黑字："
        + examples("kyoto_manuscript_mansion")
        + "；大正选文："
        + examples("taisho_literal_mansion")
        + "；本档案宿主望宿算法："
        + examples("host_calculated_mansion")
        + "。各项分别保留，写本例题未替换计算结果。"
        "这三项为既有归一化工作选录的字符串对照，"
        "后段叠改数字另属不同字位，不将相合称为独立校勘验收。"
    ]
    limits = [f"目录记作{primary['catalogue_copy_description']}"]
    if not primary["copy_date_established"]:
        limits.append("写成日期未定")
    if not primary["identified_as_taisho_base_or_ko_witness"]:
        limits.append("未识别为大正底本或甲本")
    if not reference["complete_critical_edition_accepted"]:
        limits.append("尚未完成全本校勘")
    lines.append("；".join(limits) + "，不据所选例题裁定补配次序或半日钟时。")
    span = reference["apparatus_span_reference"]
    lines.append(
        f"十六字校记按字数限定的候选范围为{span['normalized_candidate_span']}"
        f"（{span['character_count']}字）；保留イ标记，未独立取得甲本，不将其认定为无条件删文。"
    )
    if "current_scope_qualification" in span:
        lines.append(span["scope"])
    from fatebridge.core.sukuyo_printed_pages import hinoo_printed_page_lines

    lines.extend(hinoo_printed_page_lines())
    return lines


def month_table_variant(
    month: int, day: int, selected: str, resolved: bool = True
) -> dict[str, Any]:
    if type(month) is not int or not 1 <= month <= 12:
        raise ValueError("原表农历月须为1至12的整数")
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("原表农历日须为1至30的整数")
    bundle = source_bundle()
    row = bundle["printed_month_table_28"][day - 1]
    literal = row["mansions_by_month"][month - 1]
    # Only the common orthographic forms are normalized, not the sequence.
    mansion = literal.translate(str.maketrans("虛婁畢參張軫", "虚娄毕参张轸"))
    return {
        "ruleset_id": "t1299_printed_month_table_28_v1",
        "lunar_month": month,
        "lunar_day": day,
        "literal_mansion": literal,
        "table_mansion_28": mansion,
        "reference_month_day_mansion_27": selected,
        "reference_is_primary_result": resolved,
        "differs_from_selected_27": mansion != selected,
        "source_url": bundle["source_url"],
        "locator": row["locator"],
        "source_sha256": bundle["source_sha256"],
        "applied_to_sanjiu": False,
        "scope": "大正藏上卷大唐月建图的字面28宿表，含牛；保留与27宿例题差异，不当作物理天文宿位或唐历复原。",
    }


def calendar_day_evidence(
    day: int, *, host_calendar_label: str = "中国农历"
) -> dict[str, Any]:
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("黑白月入月日须为1至30的整数")
    if host_calendar_label not in {"中国农历", "日本旧历参考"}:
        raise ValueError("未知的日名宿主历法")
    bundle = source_bundle()
    named = bundle["named_days"][(day - 1) % 15]
    general_days = general_day_evidence(day)
    classifications = general_days["classifications"]
    # The lower volume explicitly glosses 一夜 as 十一夜. Preserve the literal
    # abbreviation, but never promote a bare digit into a first-night rule.
    literal_phases = {}
    interpreted_phases = {}
    restrictions = []
    for witness in bundle["timing_witnesses"]:
        name = witness["witness"]
        literal_phases[name] = next(
            (r["phase"] for r in witness["entries"] if r["literal_lunar_day"] == day),
            None,
        )
        selected = next(
            (r for r in witness["entries"] if r["interpreted_lunar_day"] == day), None
        )
        interpreted_phases[name] = selected["phase"] if selected else None
        if selected:
            restrictions.append(
                {
                    **deepcopy(selected),
                    "witness": name,
                    "assessment_before_release": "caution",
                    "locator": witness["locator"],
                    "source_excerpt": witness["source_excerpt"],
                    "release_locator": witness["release_locator"],
                    "release_excerpt": witness["release_excerpt"],
                }
            )
    literal_variant = any(
        literal_phases[f"{volume}_prose"] != literal_phases[f"{volume}_verse"]
        for volume in ("upper", "lower")
    )
    semantic_conflict = any(
        interpreted_phases[f"{volume}_prose"] != interpreted_phases[f"{volume}_verse"]
        for volume in ("upper", "lower")
    )
    resolution = (
        {
            **deepcopy(bundle["verse_abbreviation_resolution"]),
            "applies_to_current_lunar_day": day == 11,
        }
        if day in (1, 11)
        else None
    )
    restrictions.extend(
        {k: v for k, v in row.items() if k != "lunar_day"}
        for row in bundle["individual_time_witnesses"]
        if row["lunar_day"] == day
    )
    from fatebridge.core.sukuyo_dayan_reconstruction import (
        reconstruction_scope_reference,
    )
    from fatebridge.core.sukuyo_phase_clock import phase_clock_reference

    comparative = load_source(COMPARATIVE_TIME_SOURCE)
    clock_doctrine = {
        **deepcopy(bundle["clock_doctrine"]),
        "textual_position_reference": clock_position_reference(),
        "historical_clock_arithmetic": clock_arithmetic_reference(),
        "futen_research_clock_arithmetic": futen_clock_reference(),
        "dayan_reconstruction_scope_reference": reconstruction_scope_reference(),
        "commentarial_boundary_reference": commentarial_boundary_reference(),
        "phase_and_time_reference": phase_clock_reference(day),
        "senmyo_phase_annotation_reference": phase_annotation_reference(),
        "comparative_time_systems": {
            **comparative.data,
            "source_bundle_sha256": comparative.sha256,
        },
        "source_specific_time_calibration": source_specific_time_reference(),
        "arc_printed_reference": arc_clock_reference(),
    }
    return {
        "ruleset_id": bundle["id"],
        "lunar_day": day,
        "lunar_half": "白" if day <= 15 else "黑",
        "half_day": (day - 1) % 15 + 1,
        "upper_name": named["upper_name"],
        "lower_name": named["lower_name"],
        "upper_name_locator": named["upper_locator"],
        "lower_name_locator": named["lower_locator"],
        "classifications": classifications,
        "japanese_selected_reference": japanese_calendar_comparison(
            day, classifications, primary_reference=general_days["reference"]
        ),
        "time_restrictions": restrictions,
        "name_variant": named["upper_name"] != named["lower_name"],
        "classification_variant": len({r["assessment"] for r in classifications}) > 1,
        "prose_verse_time_variant": literal_variant,
        "prose_verse_time_semantic_conflict": semantic_conflict,
        "verse_abbreviation_resolution": resolution,
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": source_digest(),
        "clock_evaluation_status": "not_computed",
        "clock_doctrine": clock_doctrine,
        "clock_scope": "保留原文昼夜、日中与夜半条件；未确定古代日界及太阳时换算政策，不将民用12:00或00:00自动认作原典边界。",
        "scope": f"按所选{host_calendar_label}入月日读取原典条文，非角距tithi；日名、一般日类与时段例外分别保留，不生成全天综合吉凶。",
    }


def profile_calculation_lines(selection: dict[str, Any] | None) -> list[str]:
    """Render only the supplied profile calculations and their source conditions."""
    lines: list[str] = []
    if selection:
        host = selection["host_calculation"]
        lines.append(
            f"历法档案{selection['calendar_profile']}：本月表定十五日望宿为{host['fullmoon_mansion']}，逆顺法与生日加十三含首计数均得{host['direct_mansion']}；表定望日不等于实际满月瞬间。"
        )
        assignment = selection.get("short_month_assignment")
        if assignment:
            first, second = assignment["slots"]
            first_text = "、".join(first["candidate_mansions"])
            lines.append(
                f"相邻前月有{assignment['previous_lunar']['lunar_day']}日；T2465分宿重建前半候选{first_text}、后半{second['mansion']}（{assignment['locator']}）。"
            )
            previous = assignment["previous_lunar"]
            lines.append(
                f"相邻前月末为农历{previous['lunar_year']}年"
                f"{'闰' if previous['is_leap_month'] else ''}{previous['lunar_month']}月{previous['lunar_day']}日。"
            )
            omitted = assignment.get("omitted_day_calculation")
            if omitted:
                host = selection["host_calculation"]
                lines.append(
                    f"相邻月补配路径的前半使用该月缺失三十日，按{omitted['lunar_month']}月{omitted['lunar_day']}日查得{omitted['direct_mansion']}；"
                    f"本月常规初一另按{host['lunar_month']}月{host['lunar_day']}日查得{host['direct_mansion']}，也是后半的来源。"
                    "宿名相同仍分别保留来源；闰月初一若有另一重建路径，继续按下列分支交付。"
                )
            if assignment["selected_day_part"]:
                part = (
                    "前半"
                    if assignment["selected_day_part"] == "first_half"
                    else "后半"
                )
                lines.append(
                    f"已明确提供原典日序{part}；"
                    + (
                        "按此取宿，没有按民用钟时自动判半。"
                        if selection["resolved"]
                        else "规则次序仍有歧义，未取唯一宿；没有按民用钟时自动判半。"
                    )
                )
            elif first["candidate_mansions"] == second["candidate_mansions"]:
                lines.append("两个半日候选同宿，故宿名已定；未推断半日钟时。")
            else:
                lines.append(
                    "前/后半未定，候选宿全部保留；已知民用钟时不自动解决原典半日界。"
                )
            precedence = assignment.get("leap_short_month_precedence")
            if precedence:
                for branch in precedence["reconstruction_calculations"]:
                    label = {
                        "adjacent_month_short_day_assignment": "相邻月补配重建",
                        "repeat_regular_month_first_day_assignment": "重用普通月初一重建",
                    }[branch["id"]]
                    previous = branch["previous_lunar"]
                    first_calc = branch["first_half_calculation"]
                    second_calc = branch["second_half_calculation"]
                    lines.append(
                        f"{label}：所用前月末为农历{previous['lunar_month']}月{previous['lunar_day']}日；"
                        f"前半按{first_calc['lunar_month']}月{first_calc['lunar_day']}日查得{first_calc['direct_mansion']}，"
                        f"后半按{second_calc['lunar_month']}月{second_calc['lunar_day']}日查得{second_calc['direct_mansion']}。"
                    )
            if (
                precedence
                and precedence["adjacent_month_first_half"]
                != precedence["repeat_true_month_first_half"]
            ):
                lines.append(
                    "闰月复用与缺日分宿的先后未由原典明确，两个现代重建次序在前半不同；未将重建分支说成原典两条明定算法。"
                )
        if selection.get("hinoo_source"):
            from fatebridge.core.sukuyo_hinoo_text import hinoo_source_lines

            lines.append(
                "Hinoo研究档案使用T1299望宿主表，保留T2465十二月三十日星/室字面差异；未复原历史日本旧历。"
            )
            critical = selection["hinoo_source"].get("critical_calendar_reference")
            if critical:
                lines.extend(_hinoo_critical_lines(critical))
            lines.extend(hinoo_source_lines(selection["hinoo_source"]))
    return lines


def render_day_reading(day: dict[str, Any]) -> str:
    """Native prose from this result, retaining every matched activity clause.

    This is an authored deterministic renderer. It does not grade or certify
    the semantics of another model's independently written answer.
    """
    calendar = day["calendar"]
    from fatebridge.core.sukuyo_calendar_basis import (
        HISTORICAL_CALENDAR_BASIS,
        JAPANESE_CALENDAR_BASES,
    )

    japanese = calendar.get("calendar_basis") in JAPANESE_CALENDAR_BASES
    historical = calendar.get("calendar_basis") == HISTORICAL_CALENDAR_BASIS
    reference_zone = "UTC+09" if japanese else "UTC+08"
    calendar_label = (
        "日本历史参考历日"
        if historical
        else "日本旧历参考历日" if japanese else "中国历日"
    )
    name = day["day_mansion"]
    if name:
        mansion_text = f"本次历日27宿为{name}"
    else:
        candidates = calendar.get("candidate_su27s") or (
            [calendar["candidate_su27"]] if calendar.get("candidate_su27") else []
        )
        mansion_text = "本次历日27宿未定" + (
            f"；候选{'、'.join(candidates)}未作为确定宿应用" if candidates else ""
        )
    lunar_year_text = (
        f"{calendar['lunar_year']}年" if calendar.get("lunar_year") is not None else ""
    )
    lunar_date_text = (
        f"农历{lunar_year_text}{'闰' if calendar.get('is_leap_month') else ''}{calendar['lunar_month']}月{calendar['lunar_day']}日"
        if "lunar_month" in calendar
        else f"农历入月第{calendar['lunar_day']}日"
    )
    lines = [
        f"{calendar_label}{calendar['calendar_date']}（{reference_zone}），{lunar_date_text}；{mansion_text}。",
        f"按{reference_zone}民用历日，七曜为{day['weekday']['luminary']}曜；上卷宿性为{day['nature'] or '未定'}。原典平明日界尚未核定。",
    ]
    lines.extend(_input_reference_lines(calendar))
    reconstruction_scope = day["calendar_day"]["clock_doctrine"].get(
        "dayan_reconstruction_scope_reference"
    )
    if reconstruction_scope is not None:
        from fatebridge.core.sukuyo_dayan_reconstruction import (
            reconstruction_scope_lines,
        )

        lines.extend(reconstruction_scope_lines(reconstruction_scope, calendar))
    if calendar.get("calendar_system") == "modern_chinese_lunisolar":
        lines.append(
            "本次声明的现代中国历日采用HKO（香港天文台）年度历表参考，"
            f"计算后端为{calendar['calendar_backend']}，历日来源为{calendar['calendar_source']}。"
            "本次返回未附现代中国历日的全域独立验收范围，不能仅据年度来源链接认证古代日界、"
            "桧尾半日、闰小月次序或现实预测效力。"
        )
    profile = calendar.get("profile_calculation") or {}
    lines.extend(hinoo_unassigned_month_start_lines(calendar, profile))
    if calendar.get("calendar_day_part") in {"first_half", "second_half"}:
        half = calendar["calendar_day_part"]
        half_label = "前半" if half == "first_half" else "后半"
        lines.append(
            f"本次已声明原典半日条件为{half_label}（{half}）；"
            "这是明确输入，不由民用钟时、时正或研究的辰刻边界推定，也未确立古代半日钟界。"
        )
    elif profile.get("hinoo_source"):
        lines.append(
            "本次原典半日条件未声明；已知民用钟时、时正或研究的子半模型均未补出前半或后半。"
        )
        if (
            profile.get("short_month_assignment") is None
            and profile.get("resolved")
            and name
        ):
            lines.append(
                "本日未触发小月缺日补配的半日分配，"
                f"未声明半日没有阻止本档案算得{name}宿；这不表示古代半日钟界已确定。"
            )
    else:
        lines.append(
            "本次实际原典半日字段calendar_day_part=null（未声明）；"
            "当前档案未以原典半日分配宿名，已知民用钟时也未补出前半或后半。"
        )
    if historical:
        reference = calendar["calendar_reference"]
        early = (
            reference["date_provenance"]
            == "naoj_reconstructed_gihou_mean_new_moons_not_contemporary_observation"
        )
        lines.append(
            f"采用NAOJ冻结月朔参考，输入日期按延伸格里历、参考日界固定UTC+09；阴历纪年为{calendar['lunar_year']}，与公历年分别保留。"
            + (
                "本日属于依据仪凤历平朔推算的早期纪年，不是当年实测或已证实的颁历。"
                if early
                else "本日依据NAOJ推算并按历史资料校订的历日。"
            )
            + "未复原历史地方时或原典平明日界，也未完成全部原始颁历校勘。原典配宿为本次回推查表，不表示该年代已行用本经。"
        )
        from fatebridge.core.sukuyo_historical_calendar import (
            compatibility_reference_notes,
        )

        lines.append(compatibility_reference_notes([calendar], ["本次"]))
    elif japanese:
        origin = calendar["calendar_reference"]["date_provenance"]
        labels = {
            "published_almanac_entries": "出版方整理的刊载旧历日期",
            "provider_reconstruction_from_published_astronomical_data": "出版方根据刊载朔与节气资料重建的旧历",
            "provider_transcription_of_jingu_almanacs_with_disclosed_editorial_choices": "出版方整理的神宫历资料，保留已声明的例外与勘误",
            "provider_reference_projection_not_whole_jingu_edition_verified": "出版方的参考推算，未核定为逐年神宫原刊",
        }
        lines.append(
            f"采用HuTime 1002.1冻结逐日参考；本日来源为{labels[origin]}。固定UTC+09为明示参考日界，不是历史日本地方时复原；出生时区与所选历法分别保留。"
        )
    position = day["calendar_day"]["clock_doctrine"].get("textual_position_reference")
    if position:
        lines.append(
            "下卷段落位置校记：0398页注15与0399页注16两端互指，"
            "明本将248字特殊日段（太陽至禍）与93字分时段（一切至一，含平明及昼八夜八）互换位置；"
            "这是同底本所载的一组位置异文，不是两个独立见证。邻注另记删去前文的一字‘一’。"
            "∞表示位置转换，此组校记没有记八改六或删除分时段；不据此改写本曜宿字、事项或运行钟时。"
            "仅示意这组位置关系，电子校记自身没有提供具名明本原页，未由校记重建全部字句，也未解决古代日界、桧尾半日或补配次序。"
        )
        direct = position.get("direct_japanese_print_reference")
        if direct:
            lines.append(
                "京都大学附属图书馆藏《修註宿曜經》RB00017017、题录延宝九年刊另作直接印本对照："
                "帧71末至72右先见平明、每日八时、夜亦八时及明日晓时次后曜当直，随后为七曜占，"
                "特殊日表则在帧76至78。这个次序与上述位置交换方向相合，但前文諸國后的‘一’仍见于该印本，"
                "不能据位置相合就认定为大正【明】见证或混合重建全文。"
                "乃至□戌的字形保留酉／西未定，前文典籍后的具／且及并字异体也未作全段逐字验收；"
                "当直的直字可读。未由这些读字选择现代平明、昼夜时长、桧尾半日或闰小月优先。"
            )
        chinese = position.get("direct_chinese_print_reference")
        if chinese:
            lines.append(
                "台大馆藏《永樂北藏》第一三〇册影印所选上下卷的56页正文图像，"
                "与网络分卷逐页解码图像哈希一致，两处下载只计同一影像来源。"
                "印页592（整册PDF第596页）先见‘平明’、昼八夜八和‘明日曉時’，"
                "随后为七曜占，特殊日三表在印页596至597；段序与大正明本位置校记方向相合。"
                "这不能认证它就是该校记所指的明本，也未核定确切印次年代。"
                "正文译者署名有宋字，整册前置目录作唐，字面差异保留；"
                "尚未由所选五句及段序建立现代钟时、逐时七曜顺序、桧尾半日或闰小月优先。"
                "‘萬不失一’是原典效力宣称，未作为现实预测证据。"
            )
    if day["weekday"]["luminary"] == "月":
        lines.append(
            "上卷月曜主文私精与下卷私情字面不同；未改字补定上卷旅行规则，因私出行条件仅按下卷匹配。"
        )
    comparative_clock = day["calendar_day"]["clock_doctrine"].get(
        "comparative_time_systems"
    )
    if comparative_clock:
        lines.append(
            "分时原典对照：《大智度论》所选段记从旦至旦、一日夜三十时，春秋分昼十五夜十五，"
            "五月至昼十八夜十二，十一月至昼十二夜十八；"
            "《大唐西域记》正文每时五牟呼栗多、六时成一日夜，行内注为昼三夜三；"
            "居俗八时的行内注为昼四夜四，每时各四分。"
            "三十时不是现代三十小时，居俗八时也不是T1299昼八夜八；"
            "这些对照未证明旦等于平明、现代固定钟时、太阳高度或桧尾前后半，未代入本次计算。"
        )
    source_specific_clock = day["calendar_day"]["clock_doctrine"].get(
        "source_specific_time_calibration"
    )
    if source_specific_clock:
        lines.extend(source_specific_time_lines(source_specific_clock))
    commentarial_clock = day["calendar_day"]["clock_doctrine"].get(
        "commentarial_boundary_reference"
    )
    if commentarial_clock:
        lines.extend(commentarial_boundary_lines(commentarial_clock))
    phase_clock = day["calendar_day"]["clock_doctrine"].get("phase_and_time_reference")
    if phase_clock:
        from fatebridge.core.sukuyo_phase_clock import phase_clock_lines

        lines.extend(phase_clock_lines(phase_clock))
    senmyo = day["calendar_day"]["clock_doctrine"].get(
        "senmyo_phase_annotation_reference"
    )
    if senmyo:
        lines.extend(phase_annotation_lines(senmyo))
    historical_clock = day["calendar_day"]["clock_doctrine"].get(
        "historical_clock_arithmetic"
    )
    futen_clock = day["calendar_day"]["clock_doctrine"].get(
        "futen_research_clock_arithmetic"
    )
    if futen_clock:
        lines.extend(futen_clock_lines(futen_clock))
    if historical_clock:
        lines.append(
            "具注历时刻研究对照：相马充、渡边瑞穗子、谷川清隆2019年研究所选998至1020年记录，"
            "时点按一日50刻、一刻6分、一辰刻25分；初为零刻，时正为12.5分，四刻一分到下一辰刻边界。"
            "同页昼夜长度的100刻尺度、宣明历一刻84分的100刻制、延喜式48刻制分别保留，不能混算。"
            "延喜式从第1刻编号，其分制及解码尚未接纳；不能套用具注历从零起计的时点读法。"
            "半分与半刻按名义24小时日分别相当于144秒和864秒；只是单位比值，不是本次实际钟时。"
            "英文摘要称half koku，日文摘要的‘半’未明单位，正文及表3的分半按半分增量，差别保留，未推定作者意图。"
            "表3共40组、42对读数，芒种13日与大雪13日的带半分和不带半分均保留；"
            "和数相对25分的六组非零残差未调平：大寒8日、立夏13日、大暑8日、立冬13日为多一分，"
            "另两组的两读分别少半分或一分。"
            "通日是省没日的360日平气名义轴，不直接对应公历日；末段18只闭合这个360单位循环。"
            "实际年份的没日位置和平气瞬时尚未提供，不能将通日减一加到公历冬至，也不能改用现代定气。"
            "滅日另属朔望月名义三十分段，不能据此决定桧尾补配。"
            "论文把所选日出入解释为无大气差的太阳中心过几何地平，这只是作者对该记录的推断；"
            "未重做其天文比较，也未给T1299平明设零度、转换本次日界或桧尾半日，未改变事项。"
        )
    printed_clock = day["calendar_day"]["clock_doctrine"].get("kenyu_printed_reference")
    if printed_clock:
        from fatebridge.core.sukuyo_kenyu import printed_clock_reading_lines

        lines.extend(printed_clock_reading_lines(printed_clock))
    taibai = day["taibai_direction_reference"]
    lines.append(
        f"下卷太白月日方位主表在入月第{taibai['lunar_day']}日列为{taibai['location']}；这是日序查表，不是实测金星方位或天文顺逆行。顺逆行路判据尚未核定，未据此改变事项宜忌。"
    )
    if not taibai["witnesses_agree_for_selected_day"]:
        lines.append(
            "明本校记删去初十、二十、三十的天上行；本日该见证未列，不补为天上，也不解释成没有太白或行动已获允许。"
        )
    clothing = day.get("clothing_reference")
    if clothing:
        labels_clothing = {"favorable": "列可用", "caution": "按余并失列慎用"}
        membership = clothing["primary_assessment"]
        lines.append(
            "衣事专章按大正主文十四宿正表及未列宿补集核对；"
            + (
                f"本次{'已核定日宿' if clothing['mansion'] else '完整候选共同结论'}{labels_clothing[membership]}。"
                if membership
                else "本次尚无可采用的唯一或完整候选共同表项。"
            )
            + "裁缝、制作、修理、穿着及王者身份的条文另依明确动作核对。"
        )
        lines.append(
            "明本校记将井改作并，并将余并失改为并大吉；并字未补作井宿，未列宿也未补成同样慎用。专章口诀及上卷裁衣原句另作为文献见证保留，未转作现实病灾断言或事项评分。"
        )
        for candidate in clothing["candidate_references"]:
            verse = candidate.get("verse") or {}
            cutting = candidate.get("upper_literal_cutting_statement") or {}
            excerpts = [verse.get("taisho_text"), cutting.get("source_excerpt")]
            if any(excerpts):
                lines.append(
                    f"衣事候选{candidate['mansion']}宿的独立原文见证："
                    + "／".join(text for text in excerpts if text)
                    + "；口诀与上卷裁衣断语分别保留，未纳入事项汇总，不保证现实应验。"
                )
        predicate_limits = {
            "教女人裁衣服": "此条含教学与身份条件，不能泛化为任何人裁衣",
            "初王者嚴服觀兵": "此条同时要求王者严服与观兵，王者身份不能代替观兵条件，也未泛化为普通穿衣",
            "取衣取財": "取衣未自动解释为买衣，取财也未补作购买或付款事实",
        }
        for predicate in clothing["unmapped_clothing_predicates"]:
            lines.append(
                f"衣事未映射谓词：{predicate['literal']}（{predicate['locator']}）；"
                + predicate_limits.get(predicate["literal"], predicate["reason"])
                + "；未代入本次行为规则。"
            )
    six = day.get("six_palace_reference")
    if six and six["status"] == "natal_reference":
        members = "、".join(f"{r['name']}宿{r['mansion']}" for r in six["members"])
        lines.append(
            f"以已给定本命{six['natal_mansion']}宿本身计一，六宫宿为{members}（{six['locator']}）。"
            "这是本命相对位置参考；七曜运行犯宿及原文要求的三九参断均未计算，不据此生成当日吉凶。"
        )
    elif six and six["status"] == "natal_mansion_required":
        lines.append(
            "本次未提供本命宿，个人三九日关系未计算，六宫位置未计算；"
            "七曜运行犯宿未计算，原文要求的三九参断亦未完成，未以历日宿或星期代替。"
        )
    methods = day.get("lower_methods") or {}
    group = (methods.get("nature") or {}).get("selected_group")
    if group:
        lines.append(
            f"下卷按明列成员归为{group['name']}宿（{group['locator']}），与上卷分别保留；牛宿只在参考表中，不进入历日27宿。"
        )
        for variant in group["textual_variants"]:
            lines.append(
                f"下卷校勘：{variant['meaning']}（校记{variant['apparatus_id']}）。"
            )
    if methods:
        lines.append(
            f"下卷七曜证言为{methods['weekday']['literal_title']}（{methods['weekday']['locator']}）；继续按声明的{reference_zone}民用日索引，未核定平明钟时边界。"
        )
    special = day.get("special_day_evidence")
    if special:
        primary_labels = "、".join(special["primary"]["matched_labels"])
        lines.append(
            "特殊日主表采用上卷大正："
            + (
                (primary_labels or "未匹配标签")
                if name
                else "历日宿未定，候选不代入标签"
            )
            + "；下卷合宿文仅作历日宿名查表，未判定实际月亮合宿。"
        )
        for candidate in special.get("candidate_primary", []):
            candidate_labels = "、".join(candidate["matched_labels"])
            lines.append(
                f"候选{candidate['mansion']}的上卷主表"
                + (f"标签为{candidate_labels}" if candidate_labels else "未匹配标签")
                + "；未作为确定本日标签或事项结论，不以该支匹配或未匹配情况排除其他见证的未定字。"
            )
        relevant_labels = {
            label
            for witness in [
                special["primary"],
                *special["comparisons"],
                *special.get("direct_printed_comparisons", []),
                *special.get("candidate_primary", []),
            ]
            for label in witness["matched_labels"]
        }
        meanings = [
            (
                "甘露",
                "T21n1299_p0398b25-26",
                "宜冊立、受灌頂法、造作寺宇及受戒、習學經法、出家修道，一切並吉",
            ),
            (
                "金刚峰",
                "T21n1299_p0398c01-02",
                "宜作一切降伏法，誦日天子呪及作護摩，并諸猛利等事",
            ),
        ]
        lower_body = special["textual_position_reference"]["blocks"][0][
            "normalized_base_text"
        ]
        for label, locator, clause in meanings:
            if label in relevant_labels:
                if clause not in lower_body:
                    raise ValueError("特殊日词义参考原段已变，须重新校勘")
                lines.append(
                    f"{label}标签的传统词义另参考下卷大正{locator}：“{clause}”。"
                    "这是该卷的专门事项范围，不表示所有学习、交易或旅行均宜；"
                    "未声称其他印本说明全文相同，也不由此选择候选主宿、改变本次事项或认证现实效果。"
                )
        witness_names = {
            "upper_taisho": "上卷大正",
            "lower_taisho": "下卷大正",
            "upper_ming_apparatus": "上卷明本校记重建",
            "lower_ming_apparatus": "下卷明本校记重建",
        }
        for witness in [special["primary"], *special["comparisons"]]:
            witness_items = []
            for row in witness["rows_for_weekday"]:
                item = f"{row['label']}位{row['literal_mansion']}"
                main_literal = row.get("source_main_literal")
                if main_literal and main_literal != row["literal_mansion"]:
                    item += f"（正文{main_literal}，校记重建{row['literal_mansion']}）"
                main_weekday = row.get("source_main_weekday_index")
                if main_weekday is not None and main_weekday != row["weekday_index"]:
                    item += (
                        f"（正文{'日月火水木金土'[main_weekday]}曜，"
                        f"校记重建{row['luminary']}曜）"
                    )
                witness_items.append(item)
            matched_text = "、".join(witness["matched_labels"]) or "未匹配标签"
            if not name:
                matched_text = "日宿未定，候选不代入确定标签"
            completeness = (
                "本次标签集合完整"
                if witness["labels_complete_for_selected_day"]
                else "标签集合未定，未匹配不等于确定没有特殊日"
            )
            lines.append(
                f"{witness_names[witness['witness']]}本曜表项："
                + "、".join(witness_items)
                + f"；本次{matched_text}；{completeness}。"
            )
        for comparison in special["comparisons"]:
            witness_name = witness_names[comparison["witness"]]
            if comparison["unresolved_rows"]:
                words = "、".join(
                    r["literal_mansion"] for r in comparison["unresolved_rows"]
                )
                lines.append(
                    f"{witness_name}本曜宿字{words}未识别，不默改为胃或氐；该卷标签集合未定，不把未匹配当作无此特殊日。"
                )
            if comparison["disagrees_with_primary"]:
                witness_labels = "、".join(comparison["matched_labels"]) or "未匹配标签"
                lines.append(
                    f"{witness_name}本次为{witness_labels}，与主表不同；明本对照不代入主表或确定事项。"
                )
        if not day.get("activity_assessment"):
            lower_special = next(
                (
                    row
                    for row in special["comparisons"]
                    if row["witness"] == "lower_taisho"
                ),
                None,
            )
            lower_candidate_rasetsu = (
                [
                    row["mansion"]
                    for row in lower_special["rows_for_weekday"]
                    if row["label"] == "罗刹"
                    and row.get("mansion") in (calendar.get("candidate_su27s") or [])
                ]
                if lower_special and not name
                else []
            )
            if lower_special and (
                "罗刹" in lower_special["matched_labels"]
                or lower_special["unresolved_rows"]
                or lower_candidate_rasetsu
            ):
                lines.append(
                    "下卷罗刹条文为“不宜舉百事”，属传统事项慎用证言"
                    "（T21n1299_p0398c06）；"
                    + (
                        "本次该卷已识别宿字与组合命中，但仅为所选日宿查表，未判物理合宿。"
                        if "罗刹" in lower_special["matched_labels"]
                        else (
                            f"若主宿候选取{'、'.join(lower_candidate_rasetsu)}，该卷已识别宿字对应罗刹；"
                            "这是该候选的条件慎文，主宿仍未定，未反填确定本日标签。"
                            if lower_candidate_rasetsu
                            else "本曜宿字未识别，不能将该慎文确定应用于本日；未定字不代替条文本身的含义。"
                        )
                    )
                    + "本次没有事项输入，未形成事项汇总；不是现实失败或灾祸预告。"
                )
    selection = calendar.get("profile_calculation")
    if special:
        for printed in special.get("direct_printed_comparisons", []):
            is_kyoto = printed["witness"] == "lower_kyoto_enpo_selected"
            is_ntu = printed["edition"] == "ntu_yongle_northern_reprint_volume130"
            printed_labels = "、".join(printed["matched_labels"]) or "未匹配标签"
            table_items = "、".join(
                f"{row['label']}位{row['literal_mansion'] or '宿字未定'}"
                for row in printed["rows_for_weekday"]
            )
            lines.append(
                (
                    printed["display_name"] + "的直接影印对照："
                    if is_ntu
                    else (
                        "京都大学藏RB00017017、题录延宝九年刊《修註宿曜經》下卷的直接印本对照："
                        if is_kyoto
                        else "1897年脇田文绍缩刷本下卷的直接印本对照："
                    )
                )
                + f"本曜为{table_items}；本次"
                + (printed_labels if name else "日宿未定，未作为确定标签")
                + "；与大正正文及同底本明本校记重建分别保留，不代入主表或确定事项。"
            )
            if printed["unresolved_rows"]:
                lines.append(
                    (
                        "京都本土曜金剛峯格的元／亢字形仍未定，也没有建立元字与宿名的对应；"
                        if is_kyoto
                        else "该印本本曜罗刹位的宿字尚未核定，巨／亢仅为未接纳的字形候选；"
                    )
                    + "不补作氐或亢，标签集合未定，空匹配不表示确定没有特殊日。"
                )
            reference = printed["source_reference"]
            lines.append(
                f"该印本共保留21个所选宿字位置，其中{reference['accepted_mansion_readings']}项已识别，"
                f"{reference['unaccepted_glyph_slots']}项未核定；未完成全本或页上校记校勘，"
                "没有独立人工转录验收，也不作为独立历史观测或古代平明钟时的证明。"
            )
            if is_ntu and printed["volume"] == "upper":
                lines.append(
                    "永樂北藏上卷第三组按段落上下文对齐为罗刹类，"
                    "组名中刹／利字形未唯一接纳；此疑字与已识别的21个宿字分别保留。"
                    "该影印上卷甘露火曜井、金刚峰火曜昴水曜壁；"
                    "下卷分别为尾、壁、昴，上下卷互异没有合成一张表。"
                )
    lines.extend(profile_calculation_lines(selection))
    variant = calendar.get("source_table_variant")
    if variant:
        lines.append(
            f"印本月建28宿表此格为{variant['table_mansion_28']}（{variant['locator']}）；此异表未代入27宿三九，也不是物理月亮宿位。"
        )
    printed = calendar.get("printed_edition_reference")
    if printed:
        from fatebridge.core.sukuyo_koya import printed_reference_lines

        lines.extend(printed_reference_lines(printed))
    named = day["calendar_day"]
    lines.append(
        f"黑白月日名：{named['lunar_half']}月第{named['half_day']}日，上卷称{named['upper_name']}日，下卷称{named['lower_name']}日。"
    )
    labels = {
        "favorable": "一般吉日条目",
        "conditional": "随宿曜条件条目",
        "unlisted": "本段未单列",
    }
    lines.append(
        "一般日类："
        + "；".join(
            ("上卷散文" if r["witness"] == "upper_prose" else "下卷散文")
            + "记为"
            + labels[r["assessment"]]
            for r in named["classifications"]
        )
        + "；不覆盖事项与时段条件。"
    )
    comparison = named.get("japanese_selected_reference")
    if comparison:
        membership = (
            "列入正文吉祥日名单"
            if comparison["current_body_list_membership"] == "listed_favorable"
            else "未列入该正文名单；未列不等于忌"
        )
        body_days = "、".join(
            str(number)
            for number in comparison["selected_body_day_sequence"]["lunar_days"]
        )
        differences = "；".join(
            "与T1299"
            + ("上卷散文" if row["witness"] == "upper_prose" else "下卷散文")
            + "一般吉日名单的差别为"
            + (
                "、".join(str(number) for number in row["symmetric_difference_days"])
                + "日"
                if row["symmetric_difference_days"]
                else "无"
            )
            for row in comparison["full_favorable_membership_comparison"]
        )
        lines.append(
            f"具名对照：善通寺109-5《护摩法略抄》所选影像正文，本日{membership}。"
            f"该正文列{body_days}日；{differences}，未替换本次日类或事项。"
            "难读旁注未补入正文，抄本实物年代与T2465见证身份未核定；"
            "承和七年正月初一至初八的土日月火水木金土是连续日曜序的一组相关证言，"
            "不是日内分时，也不新增八个独立历法验证。未解决古代日界、桧尾前后半或闰月补配优先次序。"
        )
        timing = comparison["selected_body_time_restrictions"]
        lines.append(
            f"善通寺109-5所选正文的昼夜条件另记：{timing['normalized_body_literal']}。"
            "这是该来源的八条昼夜证言，未换算现代钟时，不代入本次事项；"
            "一般吉日名单与所列时段限制分别保留。"
        )
    if named["prose_verse_time_variant"]:
        resolution = named["verse_abbreviation_resolution"]
        lines.append(
            f"偈文保留白一夜／白十一夜的字面差别；下卷夹注明确一夜指十一夜（{resolution['locator']}），上卷同偈由平行散文及此注互证；未据省文另加初一夜限制。"
        )
    for restriction in named["time_restrictions"]:
        witness = {
            "upper_prose": "上卷散文",
            "upper_verse": "上卷偈文",
            "lower_prose": "下卷散文",
            "lower_verse": "下卷偈文",
            "lower_named_day": "下卷日名逐日条文",
        }[restriction["witness"]]
        phase = "昼" if restriction["phase"] == "daylight" else "夜"
        release = "日中" if restriction["release_after"] == "midday" else "夜半"
        lines.append(
            f"{witness}另列此日{phase}的限制，并称{release}后通用（{restriction['locator']}）。"
        )
    lines.append("昼夜条文尚未换算成民用钟时，不能据此认定具体时刻或整天适宜。")
    lines.append(
        "T1299本层平明起曜、昼夜各八时；未核定其唯一逐时曜神序列和现代钟时边界，未套用西方24行星时。"
    )
    personal = day.get("personal_day")
    if day.get("kenyu_lingbi_reference"):
        from fatebridge.core.sukuyo_kenyu_lingbi import lingbi_reading_lines

        lines.extend(lingbi_reading_lines(day["kenyu_lingbi_reference"]))
    if personal:
        relation = personal["relation"]
        lines.append(
            f"以本命{relation['self_su27']}为命，顺数至历日{relation['other_su27']}为{relation['relation']}；此为有向三九日关系。"
        )
        lines.append(
            f"上卷条文：{personal['upper_volume']['meaning']}（{personal['upper_volume']['locator']}）"
        )
        if personal.get("lower_volume_variant"):
            alternative = personal["lower_volume_variant"]
            lines.append(
                f"下卷异文：{alternative['meaning']}（{alternative['locator']}）"
            )
        if personal["textual_conflict"]:
            subject = "业日所作" if relation["relation"] == "業" else "危日婚姻"
            lines.append(
                f"{subject}的所选原文存在宜忌冲突，保留已列相反见证，不投票或互相覆盖。"
            )
        witnesses = personal.get("source_day_evidence")
        if witnesses:
            for row in witnesses["witnesses"]:
                volume = "上卷" if row["volume"] == "upper" else "下卷"
                kind = "又一说" if row["source_witness"] == "another_saying" else "主文"
                lines.append(
                    f"三九日{volume}{kind}见证：{row['meaning']}（{row['locator']}）"
                )
            priority = witnesses["priority_clause"]
            lines.append(
                f"三九与长行历：{priority['meaning']}（{priority['locator']}）"
            )
    doctrine = day.get("conjunction_doctrine") or {}
    group = doctrine.get("selected_group")
    if group:
        lines.append(
            f"历日宿名在下卷宿月配合段归入{group['label']}（{group['locator']}）；仅为文献分类，未据此移动物理月亮或推定过宿钟时。"
        )
        if group["membership_basis"].startswith("inferred_"):
            lines.append(
                "此组九宿成员由27宿序扣除已列六宿及十二宿推得；原文本段没有逐宿列名。"
            )
    lower = day.get("lower_mansion_day") or {}
    for note in lower.get("mapping_notes", []):
        lines.append(
            f"下卷逐宿原段限定：{note}；与具体服务事项规则分别保留，未据此作现实行动总裁决。"
        )
    if not day.get("activity_assessment"):
        for rule in lower.get("topic_rules", []):
            excerpts = rule.get("source_excerpts") or [rule["source_excerpt"]]
            condition = (
                f"；适用条件为{rule['topic_condition']}"
                if rule.get("topic_condition")
                else ""
            )
            lines.append(
                f"下卷逐宿条件参考：{rule['meaning']}；原文"
                + "／".join(dict.fromkeys(excerpts))
                + f"{condition}（{rule['locator']}）；未据此补造事项或实际行为。"
            )
    for issue in lower.get("textual_issues", []):
        lines.append(
            f"下卷逐宿文本问题：{issue['issue']}（{issue['locator']}）"
            + (
                f"；归属未定原文为{issue['literal']}，未应用于事项。"
                if issue.get("literal")
                else ""
            )
        )
    if day.get("palace_reference"):
        from fatebridge.core.sukuyo_padas import render_palace_reference

        lines.append(render_palace_reference(day["palace_reference"]))
    directions = day.get("directional_travel")
    if directions and directions["selected_records"]:
        lines.append(
            "下卷行动禁闭法另按明列日宿查方向；宫名只作本段标签，不是本命宫，方向未从出生地或GPS推定。"
        )
        for record in directions["selected_records"]:
            placement = text_placement_label(record)
            lines.append(
                f"方向条件文：{record['meaning']}（{record['locator']}；{placement}）。"
                "正文／夹注层次据所选出版方TEI标记，夹注作者身份未独立核定。"
            )
            opposing = [
                rule
                for rule in lower.get("topic_rules", [])
                if "travel" in rule["activities"]
                and rule["assessment"] != record["assessment"]
                and set(rule.get("activity_detail_any_of", []))
                & set(record["activity_detail_any_of"])
            ]
            for rule in opposing:
                lines.append(
                    f"下卷逐宿章同向条件文（{text_placement_label(rule)}）：{rule['meaning']}；"
                    f"条件为{rule['topic_condition']}（{rule['locator']}）。"
                )
            if opposing:
                lines.append(
                    "两章同向出行证言相反，分别保留，未据此改变本次事项匹配状态；"
                    "未声明出行方向时仍是条件参考。"
                )
            for variant in record["textual_variants"]:
                lines.append(
                    f"方向校记：{variant['literal']}（{variant['locator']}）；未替换大正主文。"
                )
    if directions:
        if name and not directions["selected_records"]:
            lines.append(
                f"下卷行动禁闭法未找到已识别的{name}宿方向条文；"
                "空匹配不能证明准许或禁止某行向，不能补齐未列方向。"
            )
        for issue in directions.get("textual_issues", []):
            lines.append(
                f"方向原文校勘问题：{issue['issue']}（{issue['locator']}）；"
                "未定选择字及另一见证的增删均未改写当前主文或事项。"
            )
    activity = day.get("activity_assessment")
    direction_names = {
        "northbound_journey": "向北出行",
        "eastbound_journey": "向东出行",
        "southbound_journey": "向南出行",
        "westbound_journey": "向西出行",
    }
    declared_directions = [
        detail
        for detail in (activity or {}).get("activity_details", [])
        if detail in direction_names
    ]
    if declared_directions:
        lines.append(
            "本次已明确行向："
            + "、".join(direction_names[d] for d in declared_directions)
            + "；行向不自动代表远行。"
        )
    if directions and directions.get("candidate_records"):
        complete = calendar.get("profile_calculation", {}).get(
            "candidate_set_complete_under_declared_reconstructions"
        )
        if complete is True:
            lines.append(
                "所列日宿候选在本次声明的现代重建下完整；不代表所有古法已穷尽。"
            )
        else:
            lines.append("下列仅为已列日宿候选的方向参考，未据此证明候选已穷尽。")
        for branch in directions["candidate_records"]:
            for record in branch["records"]:
                required = record.get("activity_detail_any_of", [])
                applies = bool(set(required).intersection(declared_directions))
                condition = (
                    "本次已声明行向与该支本条方向相符"
                    if applies
                    else (
                        "本次已声明行向与该支本条方向不符"
                        if declared_directions
                        else "本次未明确本条所需行向"
                    )
                )
                lines.append(
                    f"候选{branch['mansion']}方向条文：{record['meaning']}；"
                    f"{condition}（{record['locator']}；{text_placement_label(record)}）。"
                )
        lines.append(
            "以上只核对各候选条文与已声明行向，未代入未定主宿或顶层事项；不能将一支方向相符提升为全案宜行。"
        )
    if activity:
        if activity.get("activity_details"):
            lines.append(
                "本次已确认事项细节："
                + "、".join(
                    _ACTIVITY_DETAIL_LABELS[detail]
                    for detail in activity["activity_details"]
                )
                + "；只呈现已声明输入，推导分类另列，不补其他事实。"
            )
        if activity.get("detail_inferences"):
            lines.append(
                "行为分类仅从已声明细节推出："
                + "；".join(
                    f"{r['from_detail']}归入{r['implied_detail']}"
                    for r in activity["detail_inferences"]
                )
                + "；未推断方向、路程、付款方式或其他事实。"
            )
        topic = {
            "social": "社交",
            "marriage": "婚姻",
            "travel": "出行",
            "relocation": "迁居",
            "commerce": "交易",
            "study": "学习",
            "clothing": "衣事",
        }[activity["activity"]]
        status = {
            "favorable": "所匹配文献仅列宜条",
            "caution": "所匹配文献仅列忌条",
            "conflicted": "所匹配条文兼有宜与忌，须核对动作和卷别后判断是否构成同条件冲突",
            "uncovered": "选定条文未覆盖此事项",
            "conditional_only": "只有尚未满足适用条件或读法待校定的条文，未取确定宜忌",
        }[activity["evidence_status"]]
        lines.append(f"所问{topic}：{status}；不是全天综合判断或现实成功概率。")
        for rule in activity["matched_rules"]:
            condition = (
                f"；本次适用条件：{rule['topic_condition']}"
                if rule.get("applicability_status")
                == "matched_declared_activity_detail"
                else ""
            )
            lines.append(
                f"{rule['rule_id']}：{rule['meaning']}{condition}（{rule['locator']}）"
            )
        if activity.get("conditional_rules"):
            lines.append(
                "以下条文的适用条件未满足或文本读法未校定，未计入上述宜忌状态："
            )
            for rule in activity["conditional_rules"]:
                required = [
                    d
                    for d in rule.get("activity_detail_any_of", [])
                    if d in direction_names
                ]
                if (
                    required
                    and declared_directions
                    and not set(required).intersection(declared_directions)
                ):
                    lines.append(
                        "本次已声明行向不满足此条所需的"
                        + "、".join(direction_names[d] for d in required)
                        + "；不能将已知其他行向说成方向全部未知。"
                    )
                lines.append(
                    f"{rule['rule_id']}：{rule['meaning']}；条件为{rule['topic_condition']}（{rule['locator']}）。"
                )
    if not activity:
        lines.append(
            "本次没有事项输入，以上保留各层文献证言，未形成事项汇总；"
            "不据一般吉日、单条宜慎或来源标签裁决现实行动。"
        )
    from fatebridge.core.sukuyo_candidate_reading import candidate_day_lines

    lines.extend(candidate_day_lines(day.get("candidate_mansion_days", [])))
    return "\n".join(lines)
