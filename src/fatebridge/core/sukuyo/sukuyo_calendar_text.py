"""Read the selected textual calendar tables and assemble named-day evidence."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from fatebridge.core.sukuyo.sukuyo_arc_clock import arc_clock_reference
from fatebridge.core.sukuyo.sukuyo_calendar_reading import render_day_reading
from fatebridge.core.sukuyo.sukuyo_dayan_reconstruction import (
    reconstruction_scope_reference,
)
from fatebridge.core.sukuyo.sukuyo_documentary import (
    clock_position_reference,
    japanese_calendar_comparison,
)
from fatebridge.core.sukuyo.sukuyo_futen_clock import futen_clock_reference
from fatebridge.core.sukuyo.sukuyo_general_days import general_day_evidence
from fatebridge.core.sukuyo.sukuyo_guchureki_clock import clock_arithmetic_reference
from fatebridge.core.sukuyo.sukuyo_hinoo_text import (
    hinoo_unassigned_month_start_lines,
    profile_calculation_lines,
)
from fatebridge.core.sukuyo.sukuyo_phase_clock import phase_clock_reference
from fatebridge.core.sukuyo.sukuyo_senmyo_phase import phase_annotation_reference
from fatebridge.core.sukuyo.sukuyo_sources import load_source

__all__ = [
    "calendar_day_evidence",
    "hinoo_unassigned_month_start_lines",
    "month_table_variant",
    "profile_calculation_lines",
    "render_day_reading",
    "source_bundle",
]

SOURCE = Path(__file__).resolve().parents[2] / "data/sukuyo_t1299_days.json"

COMPARATIVE_TIME_SOURCE = (
    Path(__file__).resolve().parents[2] / "data/sukuyo_comparative_time_units.json"
)


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE)


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

    comparative = load_source(COMPARATIVE_TIME_SOURCE)
    clock_doctrine = {
        **deepcopy(bundle["clock_doctrine"]),
        "textual_position_reference": clock_position_reference(),
        "historical_clock_arithmetic": clock_arithmetic_reference(),
        "futen_research_clock_arithmetic": futen_clock_reference(),
        "dayan_reconstruction_scope_reference": reconstruction_scope_reference(),
        "phase_and_time_reference": phase_clock_reference(day),
        "senmyo_phase_annotation_reference": phase_annotation_reference(),
        "comparative_time_systems": comparative,
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
        "clock_evaluation_status": "not_computed",
        "clock_doctrine": clock_doctrine,
        "clock_scope": "保留原文昼夜、日中与夜半条件；未确定古代日界及太阳时换算政策，不将民用12:00或00:00自动认作原典边界。",
        "scope": f"按所选{host_calendar_label}入月日读取原典条文，非角距tithi；日名、一般日类与时段例外分别保留，不生成全天综合吉凶。",
    }
