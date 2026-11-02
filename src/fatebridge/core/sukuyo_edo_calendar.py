"""Named Edo calendar periods and scoped intercalation research, not new rules."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_edo_calendar_reference.json"


def calendar_method_reference(
    year: int, month: int, leap: bool
) -> dict[str, Any] | None:
    """Classify the printed lunar year; an era name cannot select the method."""
    if type(year) is not int or type(month) is not int or type(leap) is not bool:
        raise ValueError("历法期别须使用已算定的阴历年、月与明确闰标志")
    if not 1 <= month <= 12:
        raise ValueError("月份须为1至12")
    if not 1685 <= year <= 1872:
        return None
    source = load_source(SOURCE)
    data = source.data
    periods = [
        p
        for p in data["calendar_periods"]
        if p["first_printed_lunar_year"] <= year <= p["last_printed_lunar_year"]
    ]
    if len(periods) != 1:
        raise ValueError("具名历法期别缺失或重叠，不能猜测历法")
    period = deepcopy(periods[0])
    research = None
    if period["id"] in {"horeki", "corrected_horeki"}:
        rows = deepcopy(data["all_ten_selected_published_leap_rows"])
        current = [r for r in rows if r["year"] == year]
        research = {
            "source": deepcopy(data["sources"]["uchida1973"]),
            "all_ten_selected_rows": rows,
            "current_year_record": current[0] if current else None,
            "current_month_is_source_reported_leap": bool(
                current and leap and month == current[0]["published_leap_month_number"]
            ),
            "source_reported_anomalies_are_not_independent_recomputations": True,
            "author_rule_applied_to_primary": False,
            "decimal_strings_are_modern_clock_times": False,
        }
    reform = None
    if (year, month, leap) == (1872, 12, False):
        reform = {
            **deepcopy(data["raw_NDL_comparison"]["difference"]),
            "source": deepcopy(data["sources"]["ndl_sizes"]),
            "nominal_size_does_not_extend_covered_calendar": True,
        }
    return {
        "source_bundle_sha256": source.sha256,
        "calendar_period": period,
        "period_source": deepcopy(data["sources"]["naoj_reforms"]),
        "period_assignment_basis": "printed_lunar_year_not_civil_year_or_era_name",
        "midnight_notation_source": deepcopy(data["midnight_notation_source"]),
        "intercalation_research": research,
        "reform_month_length_reference": reform,
        "calendar_labels_changed": False,
        "sukuyo_daybreak_or_half_mapping_established": False,
        "leap_short_month_priority_established": False,
        "independent_historical_observations_added": 0,
        "scope": data["scope"],
    }


def reading_lines(reference: dict[str, Any]) -> list[str]:
    period = reference["calendar_period"]
    lines = [
        f"按本次参考阴历年，NAOJ馆藏说明对应的历法期别为{period['name']}；"
        "历法名称与年号分开，不能仅凭宝历年号认作宝历历法。"
        "这是具名文献时段说明，不据此复原古代钟时或原典平明／半日界。"
    ]
    research = reference["intercalation_research"]
    if research is not None and research["current_year_record"] is not None:
        row = research["current_year_record"]
        lines.append(
            f"内田正男《宝暦暦法置閏の疑問》第3表记{row['year']}年颁历闰"
            f"{row['published_leap_month_literal']}；"
            + (
                f"作者第2表认为依其所述规则应置闰{row['conventional_leap_month_in_table2']}月。"
                if row["source_describes_irregular_placement"]
                else "本行是十年比较记录之一，未被作者列为三项修閏例。"
            )
            + "这里保留颁历记载与作者判断，未按中气／朔的时刻先后重写本次月份；"
            "第3表另一月名列是规则闰月的翌月，不能当作替换闰月。"
            "原颁历、作者天象计算及宿曜补配先后仍未由此认证。"
        )
    if reference["reform_month_length_reference"] is not None:
        lines.append(
            "NDL大小表把1872年十二月列为大月，当前历史参考因明治改历仅覆盖该月两天；"
            "原定月大小与实际覆盖天数分开，保留30／2差别，不补出已停用的旧历日期。"
        )
    return lines
