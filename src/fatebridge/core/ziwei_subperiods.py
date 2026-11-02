"""Selected Ming text on limit halves, conditional on the existing age convention."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, cast


@lru_cache(maxsize=1)
def _source() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(
            files("fatebridge")
            .joinpath("data/classical/ziwei-naj-ming-subperiods.json")
            .read_text(encoding="utf-8")
        ),
    )


def decade_half(
    palaces: list[dict[str, Any]], scope: dict[str, Any], nominal_age: int
) -> dict[str, Any]:
    """Split the actual selected ten-ordinal interval, never age modulo ten."""
    result: dict[str, Any] = dict(
        status="unresolved",
        nominal_age=nominal_age,
        natal_branch=scope.get("branch"),
        selected_decade_age_range=None,
        year_ordinal_in_decade=None,
        half=None,
        selected_half_age_range=None,
        textual_group=None,
        conditional_on_existing_age_convention=True,
        calendar_boundaries_classically_verified=False,
    )
    if scope.get("status") == "not_started":
        result.update(
            status="not_started", unresolved_reason="formal_decade_not_started"
        )
        return result
    candidates = [p for p in palaces if p["ganzhi"][1] == scope.get("branch")]
    try:
        if scope.get("status") != "computed" or len(candidates) != 1:
            raise ValueError("no unique computed decade")
        lo, hi = (int(v) for v in candidates[0]["daxian"].split("~"))
        if lo < 1 or hi - lo != 9 or not lo <= nominal_age <= hi:
            raise ValueError("invalid decade range")
    except (ValueError, TypeError, AttributeError, KeyError):
        result["unresolved_reason"] = "selected_decade_range_missing_or_inconsistent"
        return result
    upper = nominal_age - lo < 5
    result.update(
        status="computed_given_selected_age_convention",
        selected_decade_age_range=[lo, hi],
        year_ordinal_in_decade=nominal_age - lo + 1,
        half="upper_five_years" if upper else "lower_five_years",
        selected_half_age_range=[lo, lo + 4] if upper else [lo + 5, hi],
        textual_group="north" if upper else "south",
        unresolved_reason=None,
    )
    return result


def limit_subperiod_evidence(
    palaces: list[dict[str, Any]], scopes: list[dict[str, Any]], *, nominal_age: int
) -> dict[str, Any]:
    """Expose textual groups and actual positions without choosing encounter geometry."""
    source = _source()
    half = decade_half(palaces, scopes[0], nominal_age)
    # 小限's map is available even before the first formal decade. It is only a
    # container for the unchanged natal stars, not a choice of relevant stars.
    occurrences: dict[str, list[dict[str, Any]]] = {}
    for i, p in enumerate(scopes[1]["palace_map"]):
        for j, star in enumerate(p["natal_stars_detail"]):
            occurrences.setdefault(star["name"], []).append(
                dict(
                    star=star["name"],
                    natal_branch=p["branch"],
                    natal_palace_name=p["natal_palace_name"],
                    natal_mutagen=star["mutagen"],
                    calculation_path=f"ziwei_horoscope.scopes.1.palace_map.{i}.natal_stars_detail.{j}",
                )
            )
    records = []
    for row in source["group_rows"]:
        group = row["group"]
        for name in row["stars"]:
            records.append(
                dict(
                    star=name,
                    definition_id=row["definition_id"],
                    source_frame=row["frame"],
                    source_quote=row["quote"],
                    textual_group=group,
                    textual_daxian_half=(
                        "upper_five_years"
                        if group == "north"
                        else "lower_five_years" if group == "south" else None
                    ),
                    unresolved_reason=(
                        "dual_north_south_label_no_unique_half"
                        if group == "both"
                        else None
                    ),
                    actual_occurrences=deepcopy(occurrences.get(name, [])),
                    selected_as_relevant_star=None,
                )
            )
    classified = {r["star"] for r in records}
    return dict(
        method_id=source["id"],
        version=source["version"],
        source=source["source_url"],
        frame=source["frame"],
        source_section=source["section"],
        source_reading={
            "north": source["north_quote"],
            "south": source["south_quote"],
            "adjacent_context_not_evaluated": source["adjacent_context_quote"],
        },
        transcription_method=source["transcription_method"],
        independent_human_reviewers=0,
        independent_model_reviewers=0,
        daxian=half,
        xiaoxian=dict(
            status="unresolved_calendar_boundary",
            half=None,
            half_start=None,
            half_end=None,
            north_textual_half="upper_half_year",
            south_textual_half="lower_half_year",
            unresolved_reason="passage_does_not_define_unique_civil_or_lunar_half_year_boundaries",
        ),
        group_definition_source=source["group_source_url"],
        group_definition_section=source["group_section"],
        natal_star_groups=records,
        unclassified_natal_stars=sorted(set(occurrences) - classified),
        relevant_star_geometry_defined=False,
        full_traditional_judgment=None,
        source_outcome_claim_adopted=False,
        actual_assignments_modified=False,
        whole_section_certified=False,
        whole_book_acceptance_passed=False,
        limitations=deepcopy(source["limits"]),
    )
