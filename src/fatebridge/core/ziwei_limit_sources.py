"""Explicit literal limit readings, kept separate from complete-school claims."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, List, cast


@lru_cache(maxsize=1)
def _source() -> Dict[str, Any]:
    return cast(
        Dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-limits.json")
            .read_text(encoding="utf-8")
        ),
    )


def limit_source_evidence(
    chart: Dict[str, Any],
    scopes: List[Dict[str, Any]],
    *,
    nominal_age: int,
    gender: str,
    natal_year_branch: str,
    target_year_branch: str,
    actual_doujun_branch: str,
) -> Dict[str, Any]:
    """Show literal start differences and the adopted year-only fire reading.

    Age ordinals/bureau age are conditional inputs; no claim of a uniquely
    established historical birthday/year boundary or flowing-period system.
    """
    source = _source()
    branches = "子丑寅卯辰巳午未申酉戌亥"
    profile = chart["ruleset"]["id"]
    selected = profile == "quanshu_v2_excerpt"
    forward = (chart["year_stem"] in "甲丙戊庚壬") == (gender == "男")
    sign = 1 if forward else -1
    ming = chart["ming_gong"]["branch"]
    first_age = chart["wuxing_ju"]["number"]
    actual_first = next(p for p in chart["palaces"] if p["daxian_period"] == 1)
    by_scope = {s["scope"]: s for s in scopes}
    expected_first = source["daxian"]["initial_palace_by_direction"][
        "forward" if forward else "reverse"
    ]
    expected_daxian = None
    if nominal_age >= first_age:
        expected_daxian = branches[
            (branches.index(ming) + sign * (1 + (nominal_age - first_age) // 10)) % 12
        ]
    xiao_start = next(
        r["branch"]
        for r in source["xiaoxian"]["anchors"]
        if natal_year_branch in r["year_branches"]
    )
    xiao_sign = 1 if gender == "男" else -1
    expected_xiao = branches[
        (branches.index(xiao_start) + xiao_sign * (nominal_age - 1)) % 12
    ]
    birth = chart["lunar_date"]
    expected_doujun = (
        None
        if birth["is_leap_month"]
        else branches[
            (
                branches.index(target_year_branch)
                - (birth["month"] - 1)
                + branches.index(chart["hour_branch"])
            )
            % 12
        ]
    )
    pair = next(
        r
        for r in source["fire_bell"]["pairs"]
        if natal_year_branch in r["year_branches"]
    )
    actual_stars = {
        s["name"]: p["ganzhi"][1] for p in chart["palaces"] for s in p["stars_detail"]
    }
    expected_fire = {"火星": pair["fire"], "铃星": pair["bell"]}
    return {
        "method_id": source["id"],
        "version": source["version"],
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "scope": "literal_limit_and_selected_year_only_fire_readings_given_age_and_calendar_inputs",
        "daxian": {
            "frame": source["daxian"]["frame"],
            "source_reading": source["daxian"]["quote"],
            "literal_initial_palace": expected_first,
            "actual_initial_palace": actual_first["name"],
            "matches_literal_initial_palace": actual_first["name"] == expected_first,
            "first_age": first_age,
            "age_basis": source["daxian"]["age_basis"],
            "expected_branch_given_bureau_age": expected_daxian,
            "actual_branch": by_scope["大限"]["branch"],
            "matches_literal_reading_given_bureau_age": (
                None
                if expected_daxian is None
                else by_scope["大限"]["branch"] == expected_daxian
            ),
            "active_scope_is_childhood_substitute": False,
            "formal_scope_status": by_scope["大限"]["status"],
            "before_formal_decade_start": nominal_age < first_age,
            "pre_decade_substitution_verified": False,
        },
        "xiaoxian": {
            "frame": source["xiaoxian"]["frame"],
            "source_reading": source["xiaoxian"]["quote"],
            "given_age_ordinal": nominal_age,
            "expected_branch_given_age": expected_xiao,
            "actual_branch": by_scope["小限"]["branch"],
            "matches_source_given_age": by_scope["小限"]["branch"] == expected_xiao,
            "age_boundary_rule": "software_lunar_new_year_not_independently_certified_here",
        },
        "doujun": {
            "frame": source["doujun"]["frame"],
            "source_reading": source["doujun"]["quote"],
            "actual_branch": actual_doujun_branch,
            "expected_branch": expected_doujun,
            "matches_source_rule": (
                None
                if expected_doujun is None
                else actual_doujun_branch == expected_doujun
            ),
            "leap_birth_month_rule_verified": False,
            "downstream_month_day_hour_rules_verified": False,
        },
        "fire_bell": {
            "frame": source["fire_bell"]["frame"],
            "adopted_reading": source["fire_bell"]["adopted_reading"],
            "actual_positions": {s: actual_stars[s] for s in expected_fire},
            "positions_under_selected_reading": expected_fire,
            "matches_selected_reading": all(
                actual_stars[s] == b for s, b in expected_fire.items()
            ),
            "reading_applied_to_active_profile": selected,
            "reading_support_source": source["modern_reading_support"]["url"],
            "unique_ming_hour_interpretation_certified": False,
        },
        "manual_reader_count": source["manual_reader_count"],
        "whole_book_conformance_claimed": False,
    }
