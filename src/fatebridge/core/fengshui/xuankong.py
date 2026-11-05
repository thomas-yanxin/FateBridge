"""Versioned Zhongzhou natal charts. No annual overlay or automatic house age."""

import json
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple, cast

from fatebridge.utils.timezones import parse_timezone_name

from .calendar import lichun_resolution, year_context
from .city_gate import analyze_city_gate
from .directions import rule_data, wrap9
from .integrity import validate_natal_chart
from .models import HousePeriod, XuankongRequest
from .source_comparison import compare_natal_sources
from .structure import natal_structure
from .structure_integrity import validate_natal_structure


@lru_cache(maxsize=1)
def _bundle() -> Dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "xuankong-v1.json"
    bundle = cast(Dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    validate_replacement_catalog(bundle)
    return bundle


def validate_replacement_catalog(bundle: Dict[str, Any]) -> None:
    """Missing data must not masquerade as one of eleven legitimate same-star rows."""
    mountains = bundle["mountains"]
    catalog = bundle.get("replacement_catalog", {})
    if (
        len(mountains) != 24
        or len(catalog) != 24
        or set(catalog) != {m["name"] for m in mountains}
    ):
        raise ValueError("替星表须完整登记二十四山，缺项不能默认保留原星")
    changed = {}
    for mountain in mountains:
        name = mountain["name"]
        entry = catalog[name]
        original = rule_data("directions")[mountain["direction"]]["palace_number"]
        star = entry.get("replacement_star_number")
        if (
            type(star) is not int
            or star not in (1, 2, 6, 7, 9)
            or type(entry.get("native_star_number")) is not int
            or entry["native_star_number"] != original
            or type(entry.get("changes_number")) is not bool
            or entry["changes_number"] != (star != original)
        ):
            raise ValueError(f"替星表{name}原星、替星或改数状态不完整或冲突")
        if star != original:
            changed[name] = star
    if (
        len(changed) != 13
        or any(type(n) is not int for n in bundle["replacement_stars"].values())
        or changed != bundle["replacement_stars"]
    ):
        raise ValueError("完整替星表须与十三改数山位及十一同数山位一致")


def natal_rules() -> Dict[str, Any]:
    return deepcopy(_bundle())


def natal_provenance() -> Dict[str, Any]:
    bundle = natal_rules()
    selected = bundle["ruleset"]
    selected["sources"] = [
        dict(source_id=s, **bundle["sources"][s]) for s in selected["source_ids"]
    ]
    selected["bundle_version"] = bundle["bundle_version"]
    return cast(Dict[str, Any], selected)


def _period_interval(index: int, timezone_name: str) -> Dict[str, Any]:
    start = 1864 + index * 20
    first = lichun_resolution(start, timezone_name)
    last = lichun_resolution(start + 20, timezone_name)
    return {
        "number": index % 9 + 1,
        "start_year": start,
        "end_year": start + 19,
        "valid_from": first["moment"],
        "valid_until": last["moment"],
        "timing": {
            "start": first,
            "end": last,
            "year_boundary_convention": "explicit_engineering_convention_lichun",
        },
    }


def period_context(period: HousePeriod) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "basis": period.basis,
        "evidence": period.evidence,
        "qualifies_for_period_reset": period.qualifies_for_period_reset,
        "selection_scope": "caller_selected_historical_event_no_automatic_reset",
        "rule_id": "xuankong_zhongzhou_v1.house_period",
        "source_ids": ["X1", "X2", "X4"],
        "resolution_status": "resolved",
    }
    if period.period_number is not None:
        return {
            **result,
            "number": period.period_number,
            "input_basis": "confirmed_period_number",
            "effective_event_year": None,
            "valid_from": None,
            "valid_until": None,
        }
    time = year_context(
        period.effective_event_year, period.event_at, period.timezone_name
    )
    year_uncertain = time.get("effective_year_status") == "requires_confirmation"
    years = (
        time["candidate_effective_years"]
        if year_uncertain
        else [time["effective_year"]]
    )
    indices = sorted({(year - 1864) // 20 for year in years})
    event_fields = {}
    if year_uncertain:
        event_fields = {
            "effective_event_year": None,
            "effective_event_year_status": "requires_confirmation",
            "candidate_effective_event_years": list(years),
            "provisional_effective_event_year": time["provisional_effective_year"],
            "candidate_period_numbers": [index % 9 + 1 for index in indices],
        }
    event_boundary = None
    if period.event_at is not None:
        local_year = period.event_at.astimezone(
            parse_timezone_name(period.timezone_name)
        ).year
        event_boundary = lichun_resolution(local_year, period.timezone_name)
    if len(indices) > 1:
        reason = time.get("boundary_resolution", {}).get("uncertainty_reason", "")
        if reason.startswith("moshier"):
            confirmation_reason = (
                "moshier_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("complete_moshier_solar"):
            confirmation_reason = (
                "complete_moshier_solar_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("analytic_solar"):
            confirmation_reason = (
                "analytic_solar_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("vsop2013_solar"):
            confirmation_reason = (
                "vsop2013_solar_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("aa1996_solar"):
            confirmation_reason = (
                "aa1996_solar_model_precision_guard_in_period_changeover_year"
            )
        elif reason.startswith("de440_"):
            confirmation_reason = (
                reason.removesuffix("_guard_not_accuracy_certification")
                + "_precision_guard_in_period_changeover_year"
            )
        else:
            confirmation_reason = "approximate_lichun_in_period_changeover_year"
        return {
            **result,
            **event_fields,
            "resolution_status": "requires_confirmation",
            "number": None,
            "input_basis": "aware_datetime",
            "event_time_context": time,
            "timing": {
                "event_year_boundary": event_boundary,
                "year_boundary_convention": "explicit_engineering_convention_lichun",
                "candidate_period_intervals": [
                    _period_interval(index, period.timezone_name) for index in indices
                ],
            },
            "confirmation_reason": confirmation_reason,
            "valid_from": None,
            "valid_until": None,
        }
    window = _period_interval(indices[0], period.timezone_name)
    timing = window["timing"]
    if event_boundary is not None:
        timing["event_year_boundary"] = event_boundary
    if year_uncertain:
        event_fields["resolution_scope"] = "period_number_only_event_year_unconfirmed"
    return {
        **result,
        "number": window["number"],
        "input_basis": time["input_basis"],
        "effective_event_year": time["effective_year"],
        "event_time_context": time,
        "start_year": window["start_year"],
        "end_year": window["end_year"],
        "valid_from": window["valid_from"],
        "valid_until": window["valid_until"],
        "timing": timing,
        "interval_scope": "historical_event_period_window_not_natal_expiry",
        "year_boundary": "lichun",
        "epoch_year": 1864,
        **event_fields,
    }


def _fly(center: int, yang: bool = True) -> Dict[str, int]:
    return {
        d: wrap9(center + i * (1 if yang else -1))
        for i, d in enumerate(rule_data("flight_path"))
    }


def _selector(angle: float) -> Tuple[int, str, str]:
    mountains = _bundle()["mountains"]
    index = int(((angle + 7.5) % 360) // 15)
    mountain = mountains[index]
    offset = (angle - mountain["center_degrees"] + 180) % 360 - 180
    if abs(offset) < _bundle()["central_half_width_degrees"]:
        return index, "lower", "central_nine_degrees"
    neighbour = mountains[(index + (1 if offset > 0 else -1)) % 24]
    if (
        mountain["direction"] == neighbour["direction"]
        and mountain["polarity"] == neighbour["polarity"]
    ):
        return index, "lower", "same_palace_same_polarity_no_replacement"
    return index, "replacement", "cross_palace_or_different_polarity"


def _selector_regions(
    angle: float, uncertainty: float
) -> List[Tuple[Tuple[int, str, str], Dict[str, Any]]]:
    """Partition the *whole* interval; sampling endpoints alone misses small cells.

    At an exact dividing line include both one-sided limits. This is an explicit
    conservative application policy, not a claim that ancient sources specify
    modern floating-point endpoints. Callers can merge charts by mountain/mode
    while retaining every intersecting region and its selection reason.
    """
    # Adding two finite floats can round an endpoint onto a dividing line even
    # when the exact sum lies strictly on one side. Compare the exact rational
    # values supplied by the caller; do not expand by a floating-point epsilon.
    center_angle, radius = Fraction(angle), Fraction(uncertainty)
    lower, upper = center_angle - radius, center_angle + radius
    regions = []
    for i in range(-1, 26):
        center = i * 15
        for left, right, midpoint in (
            (-7.5, -4.5, -6),
            (-4.5, 4.5, 0),
            (4.5, 7.5, 6),
        ):
            # Closed-cell intersections include both limits only when the
            # supplied interval actually touches a line. No epsilon expansion.
            start, end = max(lower, center + Fraction(left)), min(
                upper, center + Fraction(right)
            )
            if start <= end:
                selector = _selector((center + midpoint) % 360)
                regions.append(
                    (
                        selector,
                        {
                            "from_degrees_exact": str(start),
                            "until_degrees_exact": str(end),
                            "endpoints_included": True,
                            "mode_reason": selector[2],
                        },
                    )
                )
    return regions


def _selectors(angle: float, uncertainty: float) -> List[Tuple[int, str, str]]:
    found: Dict[Tuple[int, str], Tuple[int, str, str]] = {}
    for selector, _ in _selector_regions(angle, uncertainty):
        found.setdefault(selector[:2], selector)
    return list(found.values())


def _star_trace(
    seed: int, physical: Dict[str, Any], period: int, mode: str
) -> Dict[str, Any]:
    rules = _bundle()
    home_star = period if seed == 5 else seed
    # In period 5 the forward base is the native Luo Shu chart: five is only
    # central, so no outer sitting/facing seed can be five. No invented fallback.
    assert home_star != 5
    mapped = rules["star_home_mountains"][str(home_star)][physical["yuan"]]
    mapped_mountain = next(m for m in rules["mountains"] if m["name"] == mapped)
    yang = mapped_mountain["polarity"] == "yang"
    center = seed
    replacement = rules["replacement_catalog"][mapped]["replacement_star_number"]
    if mode == "replacement" and seed != 5:
        center = replacement
    decision = (
        "lower_chart_not_using_replacement"
        if mode != "replacement"
        else (
            "five_yellow_has_no_substitute"
            if seed == 5
            else (
                "same_star_explicitly_retained"
                if center == seed
                else "different_star_substituted"
            )
        )
    )
    return {
        "seed_star_number": seed,
        "home_star_number_for_polarity": home_star,
        "yuan": physical["yuan"],
        "mapped_mountain": mapped,
        "polarity": "yang" if yang else "yin",
        "flight": "forward" if yang else "reverse",
        "center_star_number": center,
        "replacement_applied": center != seed,
        "replacement_lookup": {
            "decision": decision,
            "chart_mode": mode,
            "mapped_mountain": mapped,
            "catalog_star_number": replacement if seed != 5 else None,
            "original_seed_star_number": seed,
            "selected_center_star_number": center,
            "polarity_scope": "original_same_yuan_mountain_not_replacement_star_home",
            "source_ids": ["X8", "X9"],
        },
        "five_yellow_policy": (
            "borrow_period_same_yuan_keep_five" if seed == 5 else None
        ),
        "rule_id": "xuankong_zhongzhou_v1.same_yuan_then_replacement",
        "source_ids": ["X2", "X3", "X9"] if seed == 5 else ["X1", "X2", "X8", "X9"],
    }


def _chart(period: int, selector: Tuple[int, str, str]) -> Dict[str, Any]:
    index, mode, reason = selector
    mountains = _bundle()["mountains"]
    facing, sitting = mountains[index], mountains[(index + 12) % 24]
    base = _fly(period)
    mountain = _star_trace(base[sitting["direction"]], sitting, period, mode)
    water = _star_trace(base[facing["direction"]], facing, period, mode)
    mountain_chart = _fly(
        mountain["center_star_number"], mountain["polarity"] == "yang"
    )
    facing_chart = _fly(water["center_star_number"], water["polarity"] == "yang")
    palaces = {
        d: {
            "direction": d,
            "palace_number": rule_data("directions").get(d, {"palace_number": 5})[
                "palace_number"
            ],
            "period_star_number": base[d],
            "mountain_star_number": mountain_chart[d],
            "facing_star_number": facing_chart[d],
        }
        for d in base
    }
    chart: Dict[str, Any] = {
        "candidate_id": f"{period}:{sitting['name']}-{facing['name']}:{mode}",
        "period_number": period,
        "facing": deepcopy(facing),
        "sitting": deepcopy(sitting),
        "chart_mode": mode,
        "mode_reason": reason,
        "palaces": palaces,
        "period_chart": base,
        "mountain_chart": mountain_chart,
        "facing_chart": facing_chart,
        "trace": {"mountain": mountain, "facing": water},
        "flight_path": rule_data("flight_path"),
    }
    validate_natal_chart(
        chart, period=period, facing=facing, sitting=sitting, mode=mode
    )
    chart["structure"] = natal_structure(chart)
    validate_natal_structure(chart)
    return chart


def xuankong_natal(req: XuankongRequest) -> Dict[str, Any]:
    house = req.house
    missing = []
    if house is None or house.facing_degrees is None:
        missing.append("xuankong_natal.house.facing_degrees_magnetic")
    if req.period is None:
        missing.append("xuankong_natal.period")
    period = period_context(req.period) if req.period is not None else None
    if period is not None and period["resolution_status"] != "resolved":
        missing.append("xuankong_natal.period.effective_year_or_period_confirmation")
    result: Dict[str, Any] = {
        "status": "partial",
        "subject_id": house.object_id if house is not None else "house",
        "period_context": period,
        "orientation_context": {
            "facing_degrees": (
                house.facing_degrees % 360
                if house is not None and house.facing_degrees is not None
                else None
            ),
            "north_reference": house.north_reference if house is not None else None,
            "orientation_basis": house.orientation_basis if house is not None else None,
            "uncertainty_degrees": req.effective_bearing_uncertainty,
            "boundary_policy": "both_one_sided_candidates_at_exact_dividing_lines",
            "confirmed_sitting_trigram": house.sitting_trigram if house else None,
            "candidate_constraint": "respect_confirmed_sitting_trigram",
        },
        "chart": None,
        "candidates": [],
        "missing_inputs": missing,
        "interpretation_scope": "fixed_natal_numbers_no_annual_overlay_or_form_verdict",
        "mountain_registry": natal_rules()["mountains"],
    }
    if req.city_gate is not None:
        orientations: Dict[int, Dict[str, Any]] = {}
        if house is not None and house.facing_degrees is not None:
            mountains = _bundle()["mountains"]
            for selector, region in _selector_regions(
                house.facing_degrees % 360, req.effective_bearing_uncertainty
            ):
                index, mode, _ = selector
                facing, sitting = mountains[index], mountains[(index + 12) % 24]
                if (
                    house.sitting_trigram is not None
                    and rule_data("directions")[sitting["direction"]]["trigram"]
                    != house.sitting_trigram
                ):
                    continue
                if index not in orientations:
                    orientations[index] = {
                        "orientation_candidate_id": "city-gate-facing:"
                        + facing["name"],
                        "facing": deepcopy(facing),
                        "sitting": deepcopy(sitting),
                        "bearing_regions": [],
                        "natal_modes_not_used": [],
                    }
                orientations[index]["bearing_regions"].append(region)
                if mode not in orientations[index]["natal_modes_not_used"]:
                    orientations[index]["natal_modes_not_used"].append(mode)
        result["city_gate_analysis"] = analyze_city_gate(
            req.city_gate, list(orientations.values()), _bundle()
        )
    if missing:
        result["source_comparison"] = compare_natal_sources([])
        return result
    assert house is not None and house.facing_degrees is not None and period is not None
    supported: Dict[Tuple[int, str], Dict[str, Any]] = {}
    for selector, region in _selector_regions(
        house.facing_degrees % 360, req.effective_bearing_uncertainty
    ):
        key = selector[:2]
        if key not in supported:
            chart = _chart(period["number"], selector)
            mountains = _bundle()["mountains"]
            validate_natal_chart(
                chart,
                period=period["number"],
                facing=mountains[selector[0]],
                sitting=mountains[(selector[0] + 12) % 24],
                mode=selector[1],
            )
            validate_natal_structure(chart)
            chart["bearing_support"] = {
                "rule_id": "xuankong_zhongzhou_v1.closed_angle_interval_support",
                "source_ids": ["X2"],
                "source_scope": "angle_partition_rules_only; closed_endpoints_and_exact_arithmetic_are_engineering_policy",
                "arithmetic": "exact_rational_values_of_supplied_binary_floats",
                "coordinate_system": "unwrapped_about_normalized_reported_facing",
                "regions": [],
                "mode_reasons": [],
                "scope": "angle_support_only_not_probability_or_measurement_certification",
            }
            supported[key] = chart
        support = supported[key]["bearing_support"]
        support["regions"].append(region)
        if selector[2] not in support["mode_reasons"]:
            support["mode_reasons"].append(selector[2])
    candidates = list(supported.values())
    for chart in candidates:
        reasons = chart["bearing_support"]["mode_reasons"]
        if len(reasons) > 1:
            chart["mode_reason"] = "multiple_supported_angle_regions"
    if house.sitting_trigram is not None:
        directions = rule_data("directions")
        candidates = [
            c
            for c in candidates
            if directions[c["sitting"]["direction"]]["trigram"] == house.sitting_trigram
        ]
    result["candidates"] = candidates
    result["source_comparison"] = compare_natal_sources(candidates)
    if len(candidates) == 1:
        result["status"] = "complete"
        result["chart"] = candidates[0]
    else:
        result["missing_inputs"] = ["xuankong_natal.unambiguous_bearing"]
    return result
