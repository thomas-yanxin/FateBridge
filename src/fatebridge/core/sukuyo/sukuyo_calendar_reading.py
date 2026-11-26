"""Render the selected host calendar, named days and conditional Sukuyo readings."""

from __future__ import annotations

from typing import Any

from fatebridge.core.sukuyo.sukuyo_activity_day_reading import (
    activity_day_reading_lines,
)
from fatebridge.core.sukuyo.sukuyo_calendar_basis import (
    HISTORICAL_CALENDAR_BASIS,
    JAPANESE_CALENDAR_BASES,
)
from fatebridge.core.sukuyo.sukuyo_daily_source_reading import (
    daily_source_reading_lines,
)
from fatebridge.core.sukuyo.sukuyo_date_support import input_timezone_reading
from fatebridge.core.sukuyo.sukuyo_dayan_reconstruction import (
    reconstruction_scope_lines,
)
from fatebridge.core.sukuyo.sukuyo_hinoo_text import (
    hinoo_unassigned_month_start_lines,
    profile_calculation_lines,
)
from fatebridge.core.sukuyo.sukuyo_historical_calendar import (
    compatibility_reference_notes,
)
from fatebridge.core.sukuyo.sukuyo_koya import printed_reference_lines


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


def render_day_reading(day: dict[str, Any]) -> str:
    """Native prose from this result, retaining every matched activity clause.

    This is an authored deterministic renderer. It does not grade or certify
    the semantics of another model's independently written answer.
    """
    calendar = day["calendar"]

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

        lines.extend(reconstruction_scope_lines(reconstruction_scope, calendar))
    if calendar.get("calendar_system") == "modern_chinese_lunisolar":
        lines.append(
            "本次声明的现代中国历日采用HKO（香港天文台）年度历表参考，"
            f"计算后端为{calendar['calendar_backend']}。"
            "本次返回未附现代中国历日的全域独立验收范围，不能仅据年度参考认证古代日界、"
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
    lines.extend(daily_source_reading_lines(day, calendar, name, reference_zone))
    special = day.get("special_day_evidence")
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
    lines.extend(activity_day_reading_lines(day, calendar, name))
    return "\n".join(lines)
