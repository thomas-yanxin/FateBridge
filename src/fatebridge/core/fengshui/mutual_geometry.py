"""Wang's two diagram overlaps, kept separate from actual site usability."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any

from fatebridge.core.public_output import public_value
from fatebridge.utils.errors import FengshuiCalculationError

DATA_SHA256 = "11e5b866a930baebe2dc4c6145e6bc2c9d4c3ecff994e83ea63b7f984beb7659"
SCOPE = "diagram_overlap_and_printed_members_only_not_site_eligibility"
PATHS = (("later_heaven", "earlier_heaven"), ("earlier_heaven", "later_heaven"))


def _require(condition: bool) -> None:
    if not condition:
        raise FengshuiCalculationError("natal_mutual_geometry_inconsistent")


@lru_cache(maxsize=1)
def _facts() -> dict[str, Any]:
    path = Path(__file__).parents[2] / "data/fengshui/wang-mutual-geometry-v1.json"
    try:
        raw = path.read_bytes()
        _require(hashlib.sha256(raw).hexdigest() == DATA_SHA256)
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise FengshuiCalculationError("natal_mutual_geometry_inconsistent")
        return data
    except (OSError, ValueError, TypeError) as error:
        raise FengshuiCalculationError("natal_mutual_geometry_inconsistent") from error


def geometry_provenance() -> dict[str, Any]:
    data = _facts()
    return {
        "format_id": data["format_id"],
        "version": data["version"],
        "source_id": data["source_id"],
        "source_locator": data["source_locator"],
        "loaded_data_sha256": DATA_SHA256,
        "source_diagrams": {
            key: deepcopy(data[key]) for key in ("earlier_heaven", "later_heaven")
        },
        "orientation_convention": data["orientation_convention"],
        "scope": data["scope"],
    }


def describe_mutual_geometry(number: int, current: int | None) -> dict[str, Any]:
    data = _facts()
    members = [] if current is None else data["printed_mutual_numbers"][str(current)]
    paths = []
    if current is None:
        status = "unknown_evaluation_period"
    elif current == 5:
        status = "literal_table_only_no_fifth_trigram"
    else:
        status = "derived_from_two_diagram_overlaps"
        trigram = data["star_trigrams"][str(current)]
        numbers = {v: int(k) for k, v in data["star_trigrams"].items()}
        for origin, other in PATHS:
            direction = next(d for d, t in data[origin].items() if t == trigram)
            paired = data[other][direction]
            paths.append(
                {
                    "current_layout": origin,
                    "current_trigram": trigram,
                    "diagram_direction": direction,
                    "coincident_layout": other,
                    "coincident_trigram": paired,
                    "coincident_star_number": numbers[paired],
                }
            )
    derived = [current, *(p["coincident_star_number"] for p in paths)] if paths else []
    return {
        "rule_id": "wang_zhongzhou_timeliness_v1.diagram_overlap",
        "source_ids": ["WZT1"],
        "source_data_sha256": DATA_SHA256,
        "status": status,
        "star_number": number,
        "current_period_number": current,
        "printed_period_numbers": deepcopy(members),
        "paths": paths,
        "diagram_derived_numbers": derived,
        "diagram_members_match_table": set(derived) == set(members) if paths else None,
        "selected_star_path_indices": [
            i
            for i, path in enumerate(paths)
            if path["coincident_star_number"] == number
        ],
        "selected_star_is_current": None if current is None else number == current,
        "scope": SCOPE,
        "site_eligibility_established": False,
    }


def validate_mutual_geometry(
    value: dict[str, Any], *, number: int, current: int | None
) -> None:
    """Check the served trace from fixed source positions, without its builder."""
    try:
        data = _facts()
        _require(type(number) is int and number in range(1, 10))
        _require(current is None or (type(current) is int and current in range(1, 10)))
        members = (
            [] if current is None else data["printed_mutual_numbers"][str(current)]
        )
        for key, expected in {
            "rule_id": "wang_zhongzhou_timeliness_v1.diagram_overlap",
            "source_ids": ["WZT1"],
            "star_number": number,
            "current_period_number": current,
            "printed_period_numbers": members,
            "scope": SCOPE,
            "site_eligibility_established": False,
        }.items():
            _require(type(value[key]) is type(expected) and value[key] == expected)
        paths = value["paths"]
        _require(all(type(n) is int for n in value["diagram_derived_numbers"]))
        _require(all(type(n) is int for n in value["selected_star_path_indices"]))
        if current is None or current == 5:
            _require(paths == [] and value["diagram_derived_numbers"] == [])
            _require(value["diagram_members_match_table"] is None)
            _require(value["selected_star_path_indices"] == [])
            _require(
                value["status"]
                == (
                    "unknown_evaluation_period"
                    if current is None
                    else "literal_table_only_no_fifth_trigram"
                )
            )
        else:
            _require(value["status"] == "derived_from_two_diagram_overlaps")
            _require(len(paths) == 2)
            trigram = data["star_trigrams"][str(current)]
            for path, (origin, other) in zip(paths, PATHS):
                direction = path["diagram_direction"]
                paired = path["coincident_star_number"]
                _require(
                    path["current_layout"] == origin
                    and path["coincident_layout"] == other
                    and path["current_trigram"] == trigram
                    and data[origin][direction] == trigram
                    and type(paired) is int
                    and data["star_trigrams"][str(paired)] == data[other][direction]
                    and path["coincident_trigram"] == data[other][direction]
                )
            derived = [current, *(path["coincident_star_number"] for path in paths)]
            _require(value["diagram_derived_numbers"] == derived)
            _require(set(derived) == set(members))
            _require(value["diagram_members_match_table"] is True)
            _require(
                value["selected_star_path_indices"]
                == [
                    i
                    for i, path in enumerate(paths)
                    if path["coincident_star_number"] == number
                ]
            )
        expected_current = None if current is None else number == current
        _require(value["selected_star_is_current"] is expected_current)
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise FengshuiCalculationError("natal_mutual_geometry_inconsistent") from error


def validate_author_geometries(
    interpretation: dict[str, Any],
    natal: dict[str, Any],
    *,
    current: int | None,
    require_current_version: bool = False,
) -> dict[str, int]:
    """Bind every role's trace to the actual candidate, not its copied numbers."""
    counts = {"checked": 0, "diagram_derived": 0, "five_table_only": 0, "unknown": 0}
    try:
        profile = interpretation.get("timeliness_ruleset")
        if profile is None:
            _require(not require_current_version)
            return counts
        _require(profile["ruleset_id"] == "wang_zhongzhou_timeliness_v1")
        modern = profile["version"] == "1.1.0"
        _require(
            modern or (profile["version"] == "1.0.0" and not require_current_version)
        )
        if modern:
            _require(
                all(
                    public_value(
                        profile["geometry_provenance"]["source_diagrams"][layout]
                    )
                    == public_value(_facts()[layout])
                    for layout in ("earlier_heaven", "later_heaven")
                )
            )
        _require(
            type(interpretation["current_period_context"]["number"]) is type(current)
        )
        _require(interpretation["current_period_context"]["number"] == current)
        charts = natal.get("candidates", [])
        if not charts and natal.get("chart") is not None:
            charts = [natal["chart"]]
        candidates = interpretation["candidates"]
        _require(len(candidates) == len(charts))
        for candidate, chart in zip(candidates, charts):
            _require(candidate["candidate_id"] == chart["candidate_id"])
            _require(
                type(candidate["natal_period_number"]) is int
                and candidate["natal_period_number"] == chart["period_number"]
            )
            _require(candidate["candidate_only"] is (len(charts) > 1))
            _require(set(candidate["palaces"]) == set(chart["palaces"]))
            for direction, palace in candidate["palaces"].items():
                for role in ("mountain", "facing"):
                    number = chart["palaces"][direction][role + "_star_number"]
                    _require(
                        type(palace[role + "_star_number"]) is int
                        and palace[role + "_star_number"] == number
                    )
                    basic = palace["timeliness"][role]
                    _require(
                        type(basic["star_number"]) is int
                        and basic["star_number"] == number
                    )
                    _require(
                        type(basic["current_period_number"]) is type(current)
                        and basic["current_period_number"] == current
                    )
                    _require(
                        basic["status"]
                        == (
                            "unknown"
                            if current is None
                            else "current" if number == current else "not_current"
                        )
                    )
                    author = palace["timeliness"][role]["author_classification"]
                    _require(
                        type(author["star_number"]) is int
                        and author["star_number"] == number
                    )
                    _require(
                        type(author["current_period_number"]) is type(current)
                        and author["current_period_number"] == current
                    )
                    validate_author_phase(author, number=number, current=current)
                    if not modern:
                        continue
                    value = author["mutual_use_reference"]["geometry"]
                    validate_mutual_geometry(value, number=number, current=current)
                    counts["checked"] += 1
                    counts[
                        (
                            "unknown"
                            if current is None
                            else (
                                "five_table_only" if current == 5 else "diagram_derived"
                            )
                        )
                    ] += 1
        return counts
    except (KeyError, TypeError, IndexError, AttributeError) as error:
        raise FengshuiCalculationError("natal_mutual_geometry_inconsistent") from error


def validate_author_phase(
    author: dict[str, Any], *, number: int, current: int | None
) -> None:
    """Validate the old basic-table contract too, without awarding new geometry."""
    offset = None if current is None else (number - current) % 9
    phase = "unknown"
    if offset is not None:
        phase = next(
            label
            for label, offsets in (
                ("prosperous", {0}),
                ("growing", {1, 2}),
                ("declining", {7, 8}),
                ("dormant", {3, 4, 5, 6}),
            )
            if offset in offsets
        )
    labels = {
        "unknown": None,
        "prosperous": "旺",
        "growing": "生",
        "declining": "衰",
        "dormant": "死",
    }
    expected = {
        "rule_id": "wang_zhongzhou_timeliness_v1.basic_phase",
        "source_ids": ["WZT1"],
        "phase": phase,
        "traditional_label": labels[phase],
        "star_number": number,
        "current_period_number": current,
        "forward_cycle_offset": offset,
    }
    for key, value in expected.items():
        if type(author[key]) is not type(value) or author[key] != value:
            raise FengshuiCalculationError("natal_author_timeliness_inconsistent")
    members = (
        [] if current is None else _facts()["printed_mutual_numbers"][str(current)]
    )
    actual = author["mutual_use_reference"]
    match = None if current is None else number in members
    if (
        actual["period_numbers"] != members
        or any(type(n) is not int for n in actual["period_numbers"])
        or actual["numeric_membership"] is not match
        or actual["application_status"] != "numeric_reference_only_no_site_verdict"
    ):
        raise FengshuiCalculationError("natal_author_timeliness_inconsistent")
