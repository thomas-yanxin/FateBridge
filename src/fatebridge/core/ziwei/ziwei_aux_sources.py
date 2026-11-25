"""Source-conditioned auxiliary placements; incomplete clauses stay incomplete."""

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
            .joinpath("data/classical/ziwei-naj-ming-auxiliaries.json")
            .read_text(encoding="utf-8")
        ),
    )


def auxiliary_placement_source_evidence(
    palaces: List[Dict[str, Any]],
    *,
    lunar_month: int,
    lunar_day: int,
    is_leap: bool,
    hour_branch: str,
    year_branch: str,
    rule_profile: str,
) -> Dict[str, Any]:
    """Compare actual star objects with the scope the cited passage supports.

    Monthly rules are unresolved for leap inputs; the Ming/Shen leap clause
    cannot certify them. Fire/bell hour positions are unresolved even at 子.
    No source expectations replace the active profile's placements.
    """
    source = _source()
    branches = "子丑寅卯辰巳午未申酉戌亥"
    if not 1 <= lunar_month <= 12 or not 1 <= lunar_day <= 30:
        raise ValueError("辅星来源比较要求有效的农历月日")
    hour_index, year_index = branches.index(hour_branch), branches.index(year_branch)
    objects: Dict[str, Dict[str, Any]] = {}
    for i, palace in enumerate(palaces):
        for j, star in enumerate(palace["stars_detail"]):
            # The source batch excludes 旬空, which may have two placements.
            if star["name"] in objects:
                continue
            objects[star["name"]] = {
                "actual_branch": palace["ganzhi"][1],
                "calculation_path": f"ziwei_birth.palaces.{i}.stars_detail.{j}",
            }
    methods: Dict[str, Dict[str, Any]] = {}
    rows: List[Dict[str, Any]] = []
    expected_positions: Dict[str, str] = {}
    for method in source["methods"]:
        mid, axis = method["id"], method["input_axis"]
        methods[mid] = {key: method[key] for key in ("frame", "section", "quote")}
        for rule in method["rows"]:
            star = rule["star"]
            if axis == "day_from_month_star":
                anchor = expected_positions[rule["via_star"]]
                offset = lunar_day - 1
            else:
                anchor = rule["anchor"]
                offset = {
                    "hour": hour_index,
                    "year_branch": year_index,
                    "month": lunar_month - 1,
                }[axis]
            direction = 1 if rule["direction"] == "forward" else -1
            branch = branches[(branches.index(anchor) + direction * offset) % 12]
            expected_positions[star] = branch
            unresolved = is_leap and axis in {"month", "day_from_month_star"}
            row = {
                "star": star,
                "basis_id": mid,
                **objects[star],
                "expected_branch": None if unresolved else branch,
                "matches_source_rule": (
                    None if unresolved else objects[star]["actual_branch"] == branch
                ),
            }
            if unresolved:
                row["unresolved_reason"] = "leap_month_policy_not_stated_for_this_rule"
            rows.append(row)
    fire = source["fire_bell"]
    methods["fire_bell"] = {key: fire[key] for key in ("frame", "section", "quote")}
    methods["fire_bell"].update(
        pair_as_written=next(
            r["pair_as_written"] for r in fire["pairs"] if year_branch in r["branches"]
        ),
        hour_instruction_status=fire["hour_instruction_status"],
        active_hour_method=(
            "selected_year_branch_only_reading_no_hour_progression"
            if rule_profile == "quanshu_v2_excerpt"
            else "software_both_forward_from_zi_hour_not_certified_by_this_verse"
        ),
    )
    for star in ("火星", "铃星"):
        rows.append(
            dict(
                star=star,
                basis_id="fire_bell",
                **objects[star],
                expected_branch=None,
                matches_source_rule=None,
                unresolved_reason="hour_instruction_not_stated_even_for_zi_hour",
            )
        )
    covered = {r["star"] for r in rows}
    return {
        "method_id": source["id"],
        "version": source["version"],
        "source": source["source_url"],
        "printed_volume": source["printed_volume"],
        "scope": "selected_natal_auxiliary_positions_given_lunar_inputs_only",
        "inputs": dict(
            lunar_month=lunar_month,
            lunar_day=lunar_day,
            is_leap_month=is_leap,
            hour_branch=hour_branch,
            year_branch=year_branch,
        ),
        "methods": methods,
        "placements": rows,
        "source_name_mapping": dict(source["name_mapping"]),
        "unchecked_star_names": sorted(set(objects) - covered),
        "manual_reader_count": source["manual_reader_count"],
        "compared_rules_applied": False,
        "whole_book_conformance_claimed": False,
    }
