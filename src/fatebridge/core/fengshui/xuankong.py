"""Consolidated Zhongzhou XuanKong: natal charts, KongWang, triples, robbery, RuQiu, city gate, and interpretation."""

from __future__ import annotations

import json
from fractions import Fraction
from functools import lru_cache
from itertools import combinations
from pathlib import Path
from typing import Any, cast

from fatebridge.core.fengshui.calendar import lichun_resolution, year_context
from fatebridge.core.fengshui.directions import (
    classify_facing_band,
    raw_rule_data,
    wrap9,
)
from fatebridge.core.fengshui.models import (
    CityGateObservation,
    CityGateRequest,
    ExternalFormObservation,
    FixedLingzhengRequest,
    HousePeriod,
    LingzhengObservation,
    Placement,
    XuankongInterpretationRequest,
    XuankongRequest,
)
from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES
from fatebridge.utils.timezones import parse_timezone_name

_OUTER_DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_OPPOSITE = {d: _OUTER_DIRECTIONS[(i + 4) % 8] for i, d in enumerate(_OUTER_DIRECTIONS)}
_PARENTAL_GROUPS = ((1, 4, 7), (2, 5, 8), (3, 6, 9))
_LI_TRINE = ("S", "E", "NW")
_KAN_TRINE = ("N", "SE", "W")
_CONSECUTIVE_TRIPLES = frozenset(
    frozenset((wrap9(a), wrap9(a + 1), wrap9(a + 2))) for a in range(1, 10)
)
_HOST_GUEST_LABELS = {
    "same_element": "比和",
    "guest_generates_host": "生入",
    "guest_controls_host": "克入",
    "host_generates_guest": "生出",
    "host_controls_guest": "克出",
}


@lru_cache(maxsize=1)
def _bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "xuankong-v1.json"
    bundle = cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    validate_replacement_catalog(bundle)
    return bundle


@lru_cache(maxsize=1)
def _city_gate_bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "city-gate-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _interp_bundle() -> dict[str, Any]:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "natal-interpretation-v1.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _lingzheng_bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "fixed-lingzheng-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _timeliness_bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "wang-timeliness-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _geometry_bundle() -> dict[str, Any]:
    path = (
        Path(__file__).parents[2] / "data" / "fengshui" / "wang-mutual-geometry-v1.json"
    )
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _host_guest_bundle() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data" / "fengshui" / "host-guest-v1.json"
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def validate_replacement_catalog(bundle: dict[str, Any]) -> None:
    mountains = bundle["mountains"]
    catalog = bundle.get("replacement_catalog", {})
    if (
        len(mountains) != 24
        or len(catalog) != 24
        or set(catalog) != {m["name"] for m in mountains}
    ):
        raise ValueError("替星表须完整登记二十四山，缺项不能默认保留原星")
    directions = raw_rule_data("directions")
    changed = {}
    for mountain in mountains:
        name = mountain["name"]
        entry = catalog[name]
        original = directions[mountain["direction"]]["palace_number"]
        star = entry.get("replacement_star_number")
        if (
            type(star) is not int
            or star not in (1, 2, 6, 7, 9)
            or type(entry.get("native_star_number")) is not int
            or entry["native_star_number"] != original
            or type(entry.get("changes_number")) is not bool
            or entry["changes_number"] != (star != original)
        ):
            raise ValueError(f"替星表{name}原星、替星或改数状态冲突")
        if star != original:
            changed[name] = star
    if len(changed) != 13 or changed != bundle["replacement_stars"]:
        raise ValueError("完整替星表须与十三改数山位及十一同数山位一致")


def _compact_resolution(res: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in res.items() if k not in {"civil_point", "time_basis"}}


def _period_interval(index: int, timezone_name: str) -> dict[str, Any]:
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
            "start": _compact_resolution(first),
            "end": _compact_resolution(last),
        },
    }


def period_context(period: HousePeriod) -> dict[str, Any]:
    result: dict[str, Any] = {
        "basis": period.basis,
        "evidence": period.evidence,
        "qualifies_for_period_reset": period.qualifies_for_period_reset,
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
        period.event_year, period.event_at, period.timezone_name
    )
    year_uncertain = time.get("effective_year_status") == "requires_confirmation"
    years = (
        time["candidate_effective_years"]
        if year_uncertain
        else [time["effective_year"]]
    )
    indices = sorted({(year - 1864) // 20 for year in years})
    event_fields: dict[str, Any] = {}
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
        prefixes = (
            "moshier",
            "de441_solar",
            "analytic_solar",
            "vsop2013_solar",
            "aa1996_solar",
        )
        matched_prefix = next((p for p in prefixes if reason.startswith(p)), None)
        if matched_prefix:
            confirmation_reason = (
                f"{matched_prefix}_model_precision_guard_in_period_changeover_year"
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
                "candidate_period_intervals": [
                    _period_interval(i, period.timezone_name) for i in indices
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
        "start_year": window["start_year"],
        "end_year": window["end_year"],
        "valid_from": window["valid_from"],
        "valid_until": window["valid_until"],
        "timing": window["timing"],
        **({"event_time_context": time} if year_uncertain else {}),
        **event_fields,
    }


def _fly(center: int, yang: bool = True) -> dict[str, int]:
    step = 1 if yang else -1
    return {
        d: wrap9(center + i * step) for i, d in enumerate(raw_rule_data("flight_path"))
    }


def _selector(angle: float) -> tuple[int, str, str]:
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
) -> list[tuple[tuple[int, str, str], dict[str, Any]]]:
    center_angle, radius = Fraction(angle), Fraction(uncertainty)
    lower, upper = center_angle - radius, center_angle + radius
    regions = []
    for i in range(-1, 26):
        center = i * 15
        for left, right, midpoint in ((-7.5, -4.5, -6), (-4.5, 4.5, 0), (4.5, 7.5, 6)):
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


def _star_trace(
    seed: int, physical: dict[str, Any], period: int, mode: str
) -> dict[str, Any]:
    rules = _bundle()
    home_star = period if seed == 5 else seed
    assert home_star != 5
    mapped = rules["star_home_mountains"][str(home_star)][physical["yuan"]]
    mapped_mountain = next(m for m in rules["mountains"] if m["name"] == mapped)
    yang = mapped_mountain["polarity"] == "yang"
    replacement = rules["replacement_catalog"][mapped]["replacement_star_number"]
    center = replacement if (mode == "replacement" and seed != 5) else seed
    return {
        "seed_star_number": seed,
        "home_star_number_for_polarity": home_star,
        "yuan": physical["yuan"],
        "mapped_mountain": mapped,
        "polarity": "yang" if yang else "yin",
        "flight": "forward" if yang else "reverse",
        "center_star_number": center,
        "replacement_applied": center != seed,
        "catalog_star_number": replacement if seed != 5 else None,
        "five_yellow_kept_without_replacement": seed == 5,
    }


def _period_distribution(chart: dict[str, Any], eval_period: int) -> dict[str, Any]:
    sitting = chart["sitting"]["direction"]
    facing = chart["facing"]["direction"]
    if "mountain_chart" in chart:
        mountain_at = next(
            d for d, n in chart["mountain_chart"].items() if n == eval_period
        )
        facing_at = next(
            d for d, n in chart["facing_chart"].items() if n == eval_period
        )
    else:
        palaces = chart["palaces"]
        mountain_at = next(
            d for d, p in palaces.items() if p["mountain_star_number"] == eval_period
        )
        facing_at = next(
            d for d, p in palaces.items() if p["facing_star_number"] == eval_period
        )
    labels = {
        (sitting, facing): ("at_sitting_and_facing", "到山到向"),
        (facing, sitting): ("reversed_sitting_and_facing", "上山下水"),
        (sitting, sitting): ("both_at_sitting", "双星到坐"),
        (facing, facing): ("both_at_facing", "双星到向"),
    }
    code, label = labels.get((mountain_at, facing_at), ("other", "其他星位结构"))
    return {
        "eval_period_number": eval_period,
        "code": code,
        "traditional_label": label,
        "sitting_direction": sitting,
        "facing_direction": facing,
        "mountain_period_star_direction": mountain_at,
        "facing_period_star_direction": facing_at,
    }


def _lingxing_ruqiu(chart: dict[str, Any], eval_period: int) -> dict[str, Any]:
    if "mountain_chart" in chart:
        m_center = chart["mountain_chart"]["C"]
        f_center = chart["facing_chart"]["C"]
    else:
        m_center = chart["palaces"]["C"]["mountain_star_number"]
        f_center = chart["palaces"]["C"]["facing_star_number"]
    return {
        "eval_period_number": eval_period,
        "mountain_center_star": m_center,
        "facing_center_star": f_center,
        "mountain_in_center": m_center == eval_period,
        "facing_in_center": f_center == eval_period,
        "lingxing_ruqiu": (m_center == eval_period or f_center == eval_period),
    }


def _opposite_comparison(chart: dict[str, Any]) -> dict[str, Any]:
    sum_to_ten_dirs = []
    for d in _OUTER_DIRECTIONS:
        opp = _OPPOSITE[d]
        if chart["mountain_chart"][d] + chart["facing_chart"][opp] == 10:
            sum_to_ten_dirs.append(d)
    cm, cf = chart["mountain_chart"]["C"], chart["facing_chart"]["C"]
    return {
        "sum_to_ten_directions": sum_to_ten_dirs,
        "all_eight_sum_to_ten": len(sum_to_ten_dirs) == 8,
        "center_numeric_pair": {
            "mountain_star_number": cm,
            "facing_star_number": cf,
            "sum": cm + cf,
            "matches_sum_to_ten": cm + cf == 10,
        },
    }


def _trine_robbery(
    triples: dict[str, list[int]], directions: tuple[str, ...]
) -> dict[str, Any]:
    groups = [
        next((list(g) for g in _PARENTAL_GROUPS if sorted(triples[d]) == list(g)), None)
        for d in directions
    ]
    same_group = (
        groups[0]
        if groups[0] is not None and all(g == groups[0] for g in groups)
        else None
    )
    roles_span = False
    if same_group is not None:
        roles_span = all(
            sorted(triples[d][idx] for d in directions) == same_group
            for idx in range(3)
        )
    return {
        "directions": list(directions),
        "palace_triples": {d: triples[d] for d in directions},
        "matched_group": same_group,
        "roles_span_group": roles_span,
        "matched": same_group is not None and roles_span,
    }


def numeric_patterns(chart: dict[str, Any]) -> dict[str, Any]:
    directions_map = raw_rule_data("directions")
    ground = {d: p["palace_number"] for d, p in directions_map.items()}
    ground["C"] = 5
    flight_path = chart["flight_path"]

    triples = {
        d: [
            chart["period_chart"][d],
            chart["mountain_chart"][d],
            chart["facing_chart"][d],
        ]
        for d in flight_path
    }
    parental_match = all(
        any(sorted(triples[d]) == list(g) for g in _PARENTAL_GROUPS)
        for d in flight_path
    )
    lianzhu_match = all(
        len(set(triples[d])) == 3 and frozenset(triples[d]) in _CONSECUTIVE_TRIPLES
        for d in flight_path
    )

    li_robbery = _trine_robbery(triples, _LI_TRINE)
    kan_robbery = _trine_robbery(triples, _KAN_TRINE)
    qixing_dajie_match = parental_match and (
        li_robbery["matched"] or kan_robbery["matched"]
    )

    ground_roles = {}
    for role in ("mountain", "facing"):
        vals = chart[f"{role}_chart"]
        ground_roles[role] = {
            "same_ground_directions": [d for d in flight_path if vals[d] == ground[d]],
            "opposite_ground_directions": [
                d for d in flight_path if d != "C" and vals[d] == 10 - ground[d]
            ],
            "whole_ground_repeat": all(vals[d] == ground[d] for d in flight_path),
            "whole_ground_reverse": all(vals[d] == 10 - ground[d] for d in flight_path),
            "whole_period_plate_same": vals == chart["period_chart"],
        }

    sitting_dir, facing_dir = (
        chart["sitting"]["direction"],
        chart["facing"]["direction"],
    )
    opposite_endpoints = (
        chart["mountain_chart"][sitting_dir] + ground[sitting_dir] == 10
        and chart["facing_chart"][facing_dir] + ground[facing_dir] == 10
    )
    full_repeat = any(v["whole_ground_repeat"] for v in ground_roles.values())

    return {
        "opposite_star_comparison": _opposite_comparison(chart),
        "parental_triples": {"all_nine_match": parental_match},
        "lianzhu_triples": {"all_nine_match": lianzhu_match},
        "qixing_dajie": {
            "matched": qixing_dajie_match,
            "li_gong_dajie": li_robbery,
            "kan_gong_dajie": kan_robbery,
        },
        "ground_comparison": {"roles": ground_roles},
        "volume_two_named_refrain": {
            "applicable": chart["chart_mode"] == "lower",
            "numeric_match": (
                (full_repeat or opposite_endpoints)
                if chart["chart_mode"] == "lower"
                else None
            ),
            "whole_ground_repeat_present": full_repeat,
            "own_role_sitting_facing_both_opposite_ground": opposite_endpoints,
        },
    }


def natal_structure(
    chart: dict[str, Any], current_period: int | None = None
) -> dict[str, Any]:
    natal_period = chart["period_number"]
    ten = [
        {
            "left_role": left,
            "right_role": right,
            "all_nine_sum_to_ten": all(
                chart[f"{left}_chart"][d] + chart[f"{right}_chart"][d] == 10
                for d in chart["flight_path"]
            ),
        }
        for left, right in combinations(("period", "mountain", "facing"), 2)
    ]
    eval_period = current_period if current_period is not None else natal_period
    result: dict[str, Any] = {
        "reference_period_number": natal_period,
        "distribution": _period_distribution(chart, natal_period),
        "lingxing_ruqiu": _lingxing_ruqiu(chart, natal_period),
        "combination_of_ten": ten,
        "classical_patterns": numeric_patterns(chart),
    }
    if eval_period != natal_period:
        result["eval_period_distribution"] = _period_distribution(chart, eval_period)
        result["eval_lingxing_ruqiu"] = _lingxing_ruqiu(chart, eval_period)
    else:
        result["eval_period_distribution"] = result["distribution"]
        result["eval_lingxing_ruqiu"] = result["lingxing_ruqiu"]
    return result


def _chart(
    period: int,
    selector: tuple[int, str, str],
    *,
    current_period: int | None = None,
    band: dict[str, Any] | None = None,
) -> dict[str, Any]:
    index, mode, reason = selector
    mountains = _bundle()["mountains"]
    directions_map = raw_rule_data("directions")
    flight_path = raw_rule_data("flight_path")
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
            "palace_number": directions_map.get(d, {"palace_number": 5})[
                "palace_number"
            ],
            "period_star_number": base[d],
            "mountain_star_number": mountain_chart[d],
            "facing_star_number": facing_chart[d],
        }
        for d in base
    }
    return {
        "candidate_id": f"{period}:{sitting['name']}-{facing['name']}:{mode}",
        "period_number": period,
        "facing": dict(facing),
        "sitting": dict(sitting),
        "chart_mode": mode,
        "mode_reason": reason,
        "facing_subband": band["facing_subband"] if band else None,
        "adjacent_mountain": band["adjacent_mountain"] if band else None,
        "kongwang": band["kongwang"] if band else None,
        "kongwang_seam_degrees": band["kongwang_seam_degrees"] if band else None,
        "palaces": palaces,
        "trace": {"mountain": mountain, "facing": water},
        "structure": natal_structure(
            {
                "period_number": period,
                "facing": facing,
                "sitting": sitting,
                "chart_mode": mode,
                "period_chart": base,
                "mountain_chart": mountain_chart,
                "facing_chart": facing_chart,
                "flight_path": list(flight_path),
            },
            current_period=current_period,
        ),
    }


def _conjunction(values: list[bool | None]) -> bool | None:
    return False if False in values else None if None in values else True


def _city_gate_form(observation: CityGateObservation | None) -> dict[str, Any]:
    if observation is None:
        return {"status": "not_requested", "condition_match": None}
    water = observation.water_present
    if water is None and any(
        getattr(observation, name) is True
        for name in (
            "sole_opening_with_water",
            "three_way_water_junction_present",
            "water_reflects_towards_site",
        )
    ):
        water = True
    if (
        observation.multiple_openings_present is True
        or observation.water_present is False
    ):
        match: bool | None = False
        patterns: dict[str, bool | None] = {}
    else:
        patterns = {
            "encircled_sole_water_opening": _conjunction(
                [
                    observation.encircling_form_present,
                    observation.sole_opening_with_water,
                ]
            ),
            "reflecting_three_way_water": _conjunction(
                [
                    water,
                    observation.three_way_water_junction_present,
                    observation.water_reflects_towards_site,
                    (
                        None
                        if observation.multiple_openings_present is None
                        else not observation.multiple_openings_present
                    ),
                ]
            ),
        }
        match = (
            True
            if True in patterns.values()
            else None if None in patterns.values() else False
        )
    image = observation.observation_basis == "image_observed"
    status = (
        "candidate_only"
        if image
        else (
            "needs_confirmation"
            if match is None
            else (
                "selected_pattern_matched" if match else "selected_pattern_not_matched"
            )
        )
    )
    return {
        "status": status,
        "pattern_matches": patterns,
        "condition_match": None if image else match,
        "candidate_only": image,
    }


def analyze_city_gate(
    config: CityGateRequest,
    orientations: list[dict[str, Any]],
    registry: dict[str, Any],
) -> dict[str, Any]:
    _city_gate_bundle()
    period = config.reference_period_number
    if period is None:
        return {
            "status": "partial",
            "calculation_status": "partial",
            "reference_period_context": {
                "number": None,
                "evidence": config.period_evidence,
            },
            "candidates": [],
            "missing_inputs": ["city_gate.reference_period_number"],
            "unmatched_observations": [
                {"mountain": o.mountain, "evidence": o.evidence}
                for o in config.observations
            ],
        }
    path = raw_rule_data("flight_path")
    directions = raw_rule_data("directions")
    ring = list(directions)
    mountains = registry["mountains"]
    by_name = {m["name"]: m for m in mountains}
    base = {d: wrap9(period + i) for i, d in enumerate(path)}
    observations = {o.mountain: o for o in config.observations}
    ambiguous = len(orientations) > 1
    candidates = []
    used = set()
    for orientation in orientations:
        facing = orientation["facing"]
        gates = []
        index = ring.index(facing["direction"])
        for side, direction in (
            ("counterclockwise", ring[(index - 1) % 8]),
            ("clockwise", ring[(index + 1) % 8]),
        ):
            physical = next(
                m
                for m in mountains
                if m["direction"] == direction and m["yuan"] == facing["yuan"]
            )
            seed = base[direction]
            home = period if seed == 5 else seed
            assert home != 5
            mapped = by_name[registry["star_home_mountains"][str(home)][facing["yuan"]]]
            reverse = mapped["polarity"] == "yin"
            flight = {
                d: wrap9(seed + (-i if reverse else i)) for i, d in enumerate(path)
            }
            numeric_match = reverse and flight[direction] == period
            pair = sorted(
                (
                    directions[facing["direction"]]["palace_number"],
                    directions[direction]["palace_number"],
                )
            )
            hetu_pair = pair in ([1, 6], [2, 7], [3, 8], [4, 9])
            form = _city_gate_form(observations.get(physical["name"]))
            if physical["name"] in observations:
                used.add(physical["name"])
            gates.append(
                {
                    "direction": direction,
                    "side": side,
                    "gate_type": "primary" if hetu_pair else "secondary",
                    "gate_type_zh": "正城门" if hetu_pair else "副城门",
                    "mountain": dict(physical),
                    "same_yuan": facing["yuan"],
                    "seed_star_number": seed,
                    "flight": "reverse" if reverse else "forward",
                    "star_at_gate": flight[direction],
                    "reference_star_reaches_gate_by_reverse_flight": numeric_match,
                    "usable": numeric_match,
                    "fixed_luoshu_pair": pair,
                    "hetu_generation_pair": hetu_pair,
                    "form_assessment": form,
                    "combined_condition_match": (
                        None
                        if ambiguous
                        else _conjunction([numeric_match, form["condition_match"]])
                    ),
                }
            )
        candidates.append(
            {
                "orientation_candidate_id": orientation["orientation_candidate_id"],
                "facing": dict(facing),
                "candidate_only": ambiguous,
                "reference_period_number": period,
                "gates": gates,
            }
        )
    missing = []
    if not orientations:
        missing.append("city_gate.confirmed_magnetic_house_facing")
    elif ambiguous:
        missing.append("city_gate.unambiguous_facing_mountain")
    for c in candidates:
        for gate in c["gates"]:
            if gate["form_assessment"]["status"] in {
                "candidate_only",
                "needs_confirmation",
            }:
                missing.append(
                    f"city_gate.observations.{gate['mountain']['name']}.source_pattern_confirmation"
                )
    return {
        "status": "partial" if missing else "complete",
        "calculation_status": "complete" if orientations else "partial",
        "reference_period_context": {
            "number": period,
            "evidence": config.period_evidence,
        },
        "candidates": candidates,
        "missing_inputs": list(dict.fromkeys(missing)),
        "unmatched_observations": [
            {"mountain": m, "evidence": observations[m].evidence}
            for m in observations
            if m not in used
        ],
    }


def _describe_mutual_geometry(number: int, current: int | None) -> dict[str, Any]:
    data = _geometry_bundle()
    members = (
        [] if current is None else list(data["printed_mutual_numbers"][str(current)])
    )
    paths = []
    if current is None:
        status = "unknown_evaluation_period"
    elif current == 5:
        status = "literal_table_only_no_fifth_trigram"
    else:
        status = "derived_from_two_diagram_overlaps"
        trigram = data["star_trigrams"][str(current)]
        numbers = {v: int(k) for k, v in data["star_trigrams"].items()}
        for origin, other in (
            ("later_heaven", "earlier_heaven"),
            ("earlier_heaven", "later_heaven"),
        ):
            direction = next(d for d, t in data[origin].items() if t == trigram)
            paired = data[other][direction]
            paths.append(
                {
                    "current_layout": origin,
                    "diagram_direction": direction,
                    "coincident_layout": other,
                    "coincident_trigram": paired,
                    "coincident_star_number": numbers[paired],
                }
            )
    derived = [current, *(p["coincident_star_number"] for p in paths)] if paths else []
    return {
        "status": status,
        "printed_period_numbers": members,
        "diagram_derived_numbers": derived,
        "paths": paths,
    }


def _classify_timeliness(number: int, current: int | None) -> dict[str, Any]:
    data = _timeliness_bundle()
    offset = None if current is None else (number - current) % 9
    phase = (
        "unknown"
        if offset is None
        else (
            "prosperous"
            if offset == 0
            else (
                "growing"
                if offset in (1, 2)
                else "declining" if offset in (7, 8) else "dormant"
            )
        )
    )
    members = [] if current is None else list(data["mutual_use_numbers"][str(current)])
    return {
        "phase": phase,
        "traditional_label": data["phase_labels"][phase],
        "star_number": number,
        "current_period_number": current,
        "forward_cycle_offset": offset,
        "mutual_use_reference": {
            "period_numbers": members,
            "numeric_membership": None if current is None else number in members,
            "geometry": _describe_mutual_geometry(number, current),
        },
    }


def _analyze_fixed_lingzheng(
    config: FixedLingzhengRequest, current: int | None, natal: dict[str, Any]
) -> dict[str, Any]:
    directions = raw_rule_data("directions")
    by_number = {p["palace_number"]: d for d, p in directions.items()}
    observations = {o.direction: o for o in config.observations}
    charts = (
        [natal["chart"]]
        if natal.get("chart") is not None
        else natal.get("candidates", [])
    )
    variants = []
    missing = []
    if not charts:
        missing.append("interpretation.fixed_lingzheng.computed_natal_for_comparison")
    if current is None:
        missing.append("interpretation.current_period_number")
    elif current == 5:
        halves = (
            [config.five_period_half]
            if config.five_period_half
            else ["first_decade", "second_decade"]
        )
        if config.five_period_half is None:
            missing.append("interpretation.fixed_lingzheng.five_period_half")
        hosting = _lingzheng_bundle()["five_period_hosting"]
        for half in halves:
            variants.append({"five_period_half": half, **hosting[half]})
    else:
        variants.append(
            {
                "five_period_half": None,
                "zheng_direction": by_number[current],
                "ling_direction": by_number[10 - current],
                "ling_number": 10 - current,
            }
        )
    ambiguous = len(variants) > 1
    results = []
    for variant in variants:
        fixed_id = (
            f"fixed_period_{current}_{variant['five_period_half'] or 'whole_period'}"
        )
        palaces = {}
        for direction in directions:
            role = (
                "zheng"
                if direction == variant["zheng_direction"]
                else (
                    "ling" if direction == variant["ling_direction"] else "not_selected"
                )
            )
            obs = observations.get(direction)
            reqs = (
                ["high_solid_terrain_present"]
                if role == "zheng"
                else (
                    ["low_lying_terrain_present", "river_water_present"]
                    if role == "ling"
                    else []
                )
            )
            facts = {k: getattr(obs, k) if obs else None for k in reqs}
            match = (
                False
                if False in facts.values()
                else None if not facts or None in facts.values() else True
            )
            image = obs is not None and obs.observation_basis == "image_observed"
            cond_status = (
                "not_selected"
                if not reqs
                else (
                    "candidate_only"
                    if (ambiguous or image)
                    else (
                        "needs_confirmation"
                        if match is None
                        else (
                            "selected_presence_matched"
                            if match
                            else "selected_presence_not_matched"
                        )
                    )
                )
            )
            if cond_status in {"needs_confirmation", "candidate_only"}:
                prefix = f"interpretation.fixed_lingzheng.observations.{direction}"
                missing.extend(f"{prefix}.{k}" for k, v in facts.items() if v is None)
                if image:
                    missing.append(f"{prefix}.user_or_measurement_confirmation")
            palaces[direction] = {
                "fixed_palace_number": directions[direction]["palace_number"],
                "role": role,
                "form_assessment": {
                    "status": cond_status,
                    "observed": facts,
                    "condition_match": None if (ambiguous or image) else match,
                },
            }
        results.append(
            {
                "candidate_id": fixed_id,
                "candidate_only": ambiguous,
                "reference_period_number": current,
                **variant,
                "palaces": palaces,
            }
        )
    return {
        "status": "partial" if missing else "complete",
        "reference_period_number": current,
        "candidates": results,
        "missing_inputs": list(dict.fromkeys(missing)),
    }


def _host_guest_relation(
    host_num: int, guest_num: int, elements: dict[str, str]
) -> dict[str, Any]:
    h, g = elements[str(host_num)], elements[str(guest_num)]
    if h == g:
        op = "same_element"
    elif ELEMENT_GENERATES[g] == h:
        op = "guest_generates_host"
    elif ELEMENT_CONTROLS[g] == h:
        op = "guest_controls_host"
    elif ELEMENT_GENERATES[h] == g:
        op = "host_generates_guest"
    else:
        op = "host_controls_guest"
    return {"operation": op, "label": _HOST_GUEST_LABELS[op]}


def _analyze_host_guest(natal: dict[str, Any]) -> dict[str, Any]:
    data = _host_guest_bundle()
    elements = data["star_elements"]
    earth = data["fixed_earth_numbers"]
    charts = (
        [natal["chart"]]
        if natal.get("chart") is not None
        else natal.get("candidates", [])
    )
    candidates = []
    for chart in charts:
        axes = {}
        for axis, role, other in (
            ("sitting", "mountain", "facing"),
            ("facing", "facing", "mountain"),
        ):
            direction = chart[axis]["direction"]
            raw_nums = {
                "earth": earth[direction],
                "period": chart["palaces"][direction]["period_star_number"],
                "mountain": chart["palaces"][direction]["mountain_star_number"],
                "facing": chart["palaces"][direction]["facing_star_number"],
            }
            relations = [
                {
                    "kind": kind,
                    "host": {
                        "role": h,
                        "number": raw_nums[h],
                        "element": elements[str(raw_nums[h])],
                    },
                    "guest": {
                        "role": g,
                        "number": raw_nums[g],
                        "element": elements[str(raw_nums[g])],
                    },
                    **_host_guest_relation(raw_nums[h], raw_nums[g], elements),
                }
                for kind, h, g in (
                    ("earth_period", "earth", "period"),
                    ("period_mountain", "period", "mountain"),
                    ("period_facing", "period", "facing"),
                    ("axis_pair", role, other),
                )
            ]
            axes[axis] = {
                "direction": direction,
                "active_role": role,
                "relations": relations,
            }
        candidates.append(
            {
                "candidate_id": chart["candidate_id"],
                "natal_period_number": chart["period_number"],
                "chart_mode": chart["chart_mode"],
                "axes": axes,
            }
        )
    return {
        "status": "computed_relations" if charts else "no_computed_chart",
        "candidates": candidates,
    }


def _ordered_relationship(mountain: str, facing: str) -> str:
    if mountain == facing:
        return "same_element"
    if ELEMENT_GENERATES[mountain] == facing:
        return "mountain_generates_facing"
    if ELEMENT_GENERATES[facing] == mountain:
        return "facing_generates_mountain"
    if ELEMENT_CONTROLS[mountain] == facing:
        return "mountain_controls_facing"
    return "facing_controls_mountain"


def analyze_natal_interpretation(
    config: XuankongInterpretationRequest,
    natal: dict[str, Any],
    placements: list[Placement],
) -> dict[str, Any]:
    current = config.current_period_number
    author_profile = config.timeliness_ruleset_id is not None
    observations = {o.direction: o for o in config.external_forms}
    charts = (
        [natal["chart"]]
        if natal.get("chart") is not None
        else natal.get("candidates", [])
    )
    ambiguous = len(charts) > 1
    missing: list[str] = []
    if current is None:
        missing.append("interpretation.current_period_number")
    if not charts:
        missing.extend(
            natal.get("missing_inputs", []) or ["xuankong_natal.computed_chart"]
        )
    elif ambiguous:
        missing.append("xuankong_natal.unambiguous_bearing")

    elements = _interp_bundle()["star_elements"]
    candidates = []
    for chart in charts:
        palaces = {}
        for direction, palace in chart["palaces"].items():
            m_num, f_num = palace["mountain_star_number"], palace["facing_star_number"]
            m_elem, f_elem = elements[str(m_num)], elements[str(f_num)]
            ext = {}
            for key, role, num in (
                ("mountain", "mountain", m_num),
                ("water", "facing", f_num),
            ):
                field = "mountain_present" if role == "mountain" else "water_present"
                obs = observations.get(direction)
                observed = getattr(obs, field) if obs is not None else None
                image = obs is not None and obs.observation_basis == "image_observed"
                if direction == "C":
                    st = "not_applicable_center"
                elif current is None:
                    st = "needs_current_period"
                elif num != current:
                    st = "rule_not_covered_not_inauspicious"
                elif observed is None:
                    st = "needs_confirmation"
                    missing.append(f"interpretation.external_forms.{direction}.{field}")
                elif image:
                    st = "candidate_only"
                    missing.append(
                        f"interpretation.external_forms.{direction}.user_or_measurement_confirmation"
                    )
                else:
                    st = (
                        "matches_presence_requirement"
                        if observed
                        else "required_form_absent"
                    )
                ext[key] = {
                    "status": st,
                    "star_number": num,
                    "observed": observed,
                    "condition_match": (
                        observed
                        if st
                        in {"matches_presence_requirement", "required_form_absent"}
                        else None
                    ),
                }
            timeliness_info = {}
            for role, num in (("mountain", m_num), ("facing", f_num)):
                t = {
                    "star_number": num,
                    "status": (
                        "unknown"
                        if current is None
                        else ("current" if num == current else "not_current")
                    ),
                }
                if author_profile:
                    t["author_classification"] = _classify_timeliness(num, current)
                timeliness_info[role] = t
            palaces[direction] = {
                "direction": direction,
                "period_star_number": palace["period_star_number"],
                "mountain_star_number": m_num,
                "facing_star_number": f_num,
                "ordered_pair": {
                    "mountain_element": m_elem,
                    "facing_element": f_elem,
                    "relationship": _ordered_relationship(m_elem, f_elem),
                },
                "timeliness": timeliness_info,
                "external_form_analysis": ext,
            }
        findings: list[dict[str, Any]] = []
        for placement in placements:
            if placement.purpose not in {"bed", "door"}:
                findings.append(
                    {
                        "object_id": placement.object_id,
                        "purpose": placement.purpose,
                        "status": "unsupported",
                    }
                )
                continue
            if placement.location_direction is None:
                findings.append(
                    {
                        "object_id": placement.object_id,
                        "purpose": placement.purpose,
                        "status": "needs_location",
                    }
                )
                missing.append(f"placements.{placement.object_id}.location_direction")
                continue
            role = "mountain" if placement.purpose == "bed" else "facing"
            pal = palaces[placement.location_direction]
            ext_cond = pal["external_form_analysis"][
                "mountain" if role == "mountain" else "water"
            ]
            findings.append(
                {
                    "object_id": placement.object_id,
                    "purpose": placement.purpose,
                    "direction": placement.location_direction,
                    "selected_star_role": role,
                    "selected_star_number": pal[f"{role}_star_number"],
                    "status": ext_cond["status"],
                    "condition_match": (
                        ext_cond["condition_match"] if not ambiguous else None
                    ),
                }
            )
        cand_entry: dict[str, Any] = {
            "candidate_id": chart["candidate_id"],
            "candidate_only": ambiguous,
            "natal_period_number": chart["period_number"],
            "palaces": palaces,
            "placement_findings": findings,
        }
        if current is not None:
            cand_entry["eval_period_distribution"] = _period_distribution(
                chart, current
            )
            cand_entry["eval_lingxing_ruqiu"] = _lingxing_ruqiu(chart, current)
        candidates.append(cand_entry)

    fixed = (
        _analyze_fixed_lingzheng(config.fixed_lingzheng, current, natal)
        if config.fixed_lingzheng
        else None
    )
    if fixed is not None:
        missing.extend(fixed["missing_inputs"])
    host_guest = _analyze_host_guest(natal) if config.host_guest_ruleset_id else None

    result: dict[str, Any] = {
        **({"timeliness_ruleset_id": config.timeliness_ruleset_id} if author_profile else {}),
        **({"fixed_lingzheng_analysis": fixed} if fixed is not None else {}),
        **({"host_guest_analysis": host_guest} if host_guest is not None else {}),
        "status": "partial" if missing or not charts else "complete",
        "ruleset_id": config.ruleset_id,
        "current_period_context": {
            "number": current,
            "evidence": config.period_evidence,
        },
        "candidates": candidates,
        "missing_inputs": list(dict.fromkeys(missing)),
    }
    return result


def xuankong_natal(req: XuankongRequest) -> dict[str, Any]:
    house = req.house
    missing = []
    if house is None or house.facing_degrees is None:
        missing.append("xuankong_natal.house.facing_degrees_magnetic")
    if req.period is None:
        missing.append("xuankong_natal.period")
    period = period_context(req.period) if req.period is not None else None
    if period is not None and period["resolution_status"] != "resolved":
        missing.append("xuankong_natal.period.effective_year_or_period_confirmation")

    eval_period = req.current_period_number or (
        req.interpretation.current_period_number if req.interpretation else None
    )
    band = (
        classify_facing_band(house.facing_degrees)
        if house is not None and house.facing_degrees is not None
        else None
    )
    orientation_ctx: dict[str, Any] = {
        "facing_degrees": (
            house.facing_degrees % 360
            if house and house.facing_degrees is not None
            else None
        ),
        "north_reference": house.north_reference if house else None,
        "uncertainty_degrees": req.effective_bearing_uncertainty,
        "confirmed_sitting_trigram": house.sitting_trigram if house else None,
        "facing_subband": band["facing_subband"] if band else None,
        "adjacent_mountain": band["adjacent_mountain"] if band else None,
        "kongwang": band["kongwang"] if band else None,
        "kongwang_seam_degrees": band["kongwang_seam_degrees"] if band else None,
    }
    if house is not None and house.facing_mountain is not None:
        orientation_ctx["facing_mountain"] = house.facing_mountain
    result: dict[str, Any] = {
        "status": "partial",
        "subject_id": house.object_id if house is not None else "house",
        "period_context": period,
        "orientation_context": orientation_ctx,
        "chart": None,
        "candidates": [],
        "missing_inputs": missing,
    }
    if req.city_gate is not None:
        orientations: dict[int, dict[str, Any]] = {}
        if house is not None and house.facing_degrees is not None:
            mountains = _bundle()["mountains"]
            directions_map = raw_rule_data("directions")
            for selector, region in _selector_regions(
                house.facing_degrees % 360, req.effective_bearing_uncertainty
            ):
                index, _, _ = selector
                facing, sitting = mountains[index], mountains[(index + 12) % 24]
                if (
                    house.sitting_trigram is not None
                    and directions_map[sitting["direction"]]["trigram"]
                    != house.sitting_trigram
                ):
                    continue
                if index not in orientations:
                    orientations[index] = {
                        "orientation_candidate_id": f"city-gate-facing:{facing['name']}",
                        "facing": facing,
                        "sitting": sitting,
                        "bearing_regions": [],
                    }
                orientations[index]["bearing_regions"].append(region)
        elif house is not None and house.facing_mountain is not None:
            mountains = _bundle()["mountains"]
            m_idx = [m["name"] for m in mountains].index(house.facing_mountain)
            facing, sitting = mountains[m_idx], mountains[(m_idx + 12) % 24]
            orientations[m_idx] = {
                "orientation_candidate_id": f"city-gate-facing:{facing['name']}",
                "facing": facing,
                "sitting": sitting,
                "bearing_regions": [],
            }
        result["city_gate_analysis"] = analyze_city_gate(
            req.city_gate, list(orientations.values()), _bundle()
        )
    if missing:
        if (
            house is not None
            and house.facing_degrees is None
            and house.facing_mountain is not None
            and period is not None
            and period["resolution_status"] == "resolved"
        ):
            mountains = _bundle()["mountains"]
            m_idx = [m["name"] for m in mountains].index(house.facing_mountain)
            result["candidates"] = [
                _chart(
                    period["number"],
                    (m_idx, "lower", "facing_mountain_lower_candidate"),
                    current_period=eval_period,
                ),
                _chart(
                    period["number"],
                    (m_idx, "replacement", "facing_mountain_replacement_candidate"),
                    current_period=eval_period,
                ),
            ]
        return result

    assert house is not None and house.facing_degrees is not None and period is not None
    supported: dict[tuple[int, str], dict[str, Any]] = {}
    for selector, region in _selector_regions(
        house.facing_degrees % 360, req.effective_bearing_uncertainty
    ):
        key = selector[:2]
        if key not in supported:
            chart = _chart(
                period["number"], selector, current_period=eval_period, band=band
            )
            if req.effective_bearing_uncertainty > 0:
                chart["bearing_support"] = {"regions": [], "mode_reasons": []}
            supported[key] = chart
        if "bearing_support" in supported[key]:
            supported[key]["bearing_support"]["regions"].append(region)
            if selector[2] not in supported[key]["bearing_support"]["mode_reasons"]:
                supported[key]["bearing_support"]["mode_reasons"].append(selector[2])
    candidates = list(supported.values())
    if house.sitting_trigram is not None:
        directions_map = raw_rule_data("directions")
        candidates = [
            c
            for c in candidates
            if directions_map[c["sitting"]["direction"]]["trigram"]
            == house.sitting_trigram
        ]
    if len(candidates) == 1:
        result["status"] = "complete"
        result["chart"] = candidates[0]
        result["candidates"] = []
    else:
        result["candidates"] = candidates
        result["missing_inputs"] = ["xuankong_natal.unambiguous_bearing"]
    return result
