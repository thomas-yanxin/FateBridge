"""Explicit axis host/guest definitions, separate from fortune interpretation."""

import hashlib
import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from fatebridge.core.hexagram_relations import ELEMENT_CONTROLS, ELEMENT_GENERATES
from fatebridge.core.public_output import same_public_value as _same
from fatebridge.utils.errors import FengshuiCalculationError

DATA_SHA256 = "476bbec41149a8ade4e47586618a18e3091d65513e0cb02eb9063267e0470449"
KINDS = ("earth_period", "period_mountain", "period_facing", "axis_pair")
LABELS = {
    "same_element": "比和",
    "guest_generates_host": "生入",
    "guest_controls_host": "克入",
    "host_generates_guest": "生出",
    "host_controls_guest": "克出",
}
RELATIONS = {label: operation for operation, label in LABELS.items()}
SCOPE = "axis_host_guest_operations_only_not_timeliness_fortune_or_site_eligibility"


def _check(value: bool) -> None:
    if not value:
        raise FengshuiCalculationError("natal_host_guest_inconsistent")


@lru_cache(maxsize=1)
def _facts() -> dict[str, Any]:
    try:
        path = Path(__file__).parents[2] / "data/fengshui/host-guest-v1.json"
        raw = path.read_bytes()
        _check(hashlib.sha256(raw).hexdigest() == DATA_SHA256)
        value = json.loads(raw)
        _check(isinstance(value, dict))
        return cast(dict[str, Any], value)
    except (OSError, ValueError, TypeError) as error:
        raise FengshuiCalculationError("natal_host_guest_inconsistent") from error


def provenance() -> dict[str, Any]:
    data = _facts()
    return {
        **deepcopy(data["ruleset"]),
        "sources": [
            {"kind": "primary_facsimile", **deepcopy(source)}
            for source in data["sources"]
        ],
        "loaded_data_sha256": DATA_SHA256,
        "source_reference_sha256": data["source_reference_sha256"],
        "source_policy_notes": deepcopy(data["source_policy_notes"]),
    }


def _number(value: Any) -> int:
    _check(type(value) is int and value in range(1, 10))
    return cast(int, value)


def classify(host: int, guest: int) -> dict[str, str]:
    """Calculate an operation; this does not classify auspiciousness."""
    elements = _facts()["star_elements"]
    h, g = elements[str(_number(host))], elements[str(_number(guest))]
    if h == g:
        operation = "same_element"
    elif ELEMENT_GENERATES[g] == h:
        operation = "guest_generates_host"
    elif ELEMENT_CONTROLS[g] == h:
        operation = "guest_controls_host"
    elif ELEMENT_GENERATES[h] == g:
        operation = "host_generates_guest"
    else:
        _check(ELEMENT_CONTROLS[h] == g)
        operation = "host_controls_guest"
    return {"operation": operation, "label": LABELS[operation]}


def _charts(natal: dict[str, Any]) -> list[dict[str, Any]]:
    charts = natal.get("candidates", [])
    return charts or ([natal["chart"]] if natal.get("chart") is not None else [])


def _direction(chart: dict[str, Any], axis: str) -> str:
    mountain = chart[axis]["name"]
    directions = [
        d for d, names in _facts()["sector_mountains"].items() if mountain in names
    ]
    _check(len(directions) == 1)
    _check(chart[axis]["direction"] == directions[0])
    return cast(str, directions[0])


def _raw_number(chart: dict[str, Any], direction: str, role: str) -> int:
    if role == "earth":
        return cast(int, _facts()["fixed_earth_numbers"][direction])
    number = _number(chart[role + "_chart"][direction])
    _check(chart["palaces"][direction][role + "_star_number"] == number)
    return number


def _literal(chart: dict[str, Any]) -> dict[str, Any]:
    rows = [
        r
        for r in _facts()["lower_clauses"]
        if r["period"] == chart["period_number"]
        and r["sitting_mountain"] == chart["sitting"]["name"]
        and r["facing_mountain"] == chart["facing"]["name"]
    ]
    _check(len(rows) == 1)
    return cast(dict[str, Any], rows[0])


def _comparison(chart: dict[str, Any], axis: str, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {
        "scope": "literal_lower_clause_operation_words_not_fortune_verdict",
        "comparison_basis": "axis_pair_as_defined_p453_p910",
        "basis_determined_from_clause_alone": False,
        "source_angle_applicability_verified": False,
    }
    if chart["chart_mode"] != "lower":
        return {
            **result,
            "status": "not_applicable_lower_chart_corpus",
            "matched": None,
        }
    row = _literal(chart)
    labels = row["labels"]["山" if axis == "sitting" else "向"]
    return {
        **result,
        "status": (
            "source_ambiguous"
            if len(labels) != 1
            else "matches" if label == labels[0] else "differs"
        ),
        "matched": label == labels[0] if len(labels) == 1 else None,
        "literal_labels": deepcopy(labels),
        "literal_full_clause": row["literal_full_clause"],
        "pdf_page": row["page"],
    }


def _record(
    chart: dict[str, Any], direction: str, kind: str, host: str, guest: str
) -> dict[str, Any]:
    elements = _facts()["star_elements"]
    h, g = _raw_number(chart, direction, host), _raw_number(chart, direction, guest)
    return {
        "kind": kind,
        "direction": direction,
        "host": {"role": host, "number": h, "element": elements[str(h)]},
        "guest": {"role": guest, "number": g, "element": elements[str(g)]},
        **classify(h, g),
        "rule_id": "shen_2011_host_guest_v1.operation",
        "source_ids": ["HGT1", "HGT2", "HGT3", "HGT4"],
    }


def analyze(natal: dict[str, Any]) -> dict[str, Any]:
    charts = _charts(natal)
    candidates = []
    for chart in charts:
        axes = {}
        for axis, role, other in (
            ("sitting", "mountain", "facing"),
            ("facing", "facing", "mountain"),
        ):
            direction = _direction(chart, axis)
            pairs = (
                ("earth", "period"),
                ("period", "mountain"),
                ("period", "facing"),
                (role, other),
            )
            records = [
                _record(chart, direction, kind, host, guest)
                for kind, (host, guest) in zip(KINDS, pairs)
            ]
            axes[axis] = {
                "direction": direction,
                "active_role": role,
                "relations": records,
                "literal_clause_comparison": _comparison(
                    chart, axis, records[-1]["label"]
                ),
            }
        candidates.append(
            {
                "candidate_id": chart["candidate_id"],
                "natal_period_number": chart["period_number"],
                "chart_mode": chart["chart_mode"],
                "candidate_only": len(charts) > 1,
                "axes": axes,
                "unassigned_palaces": {
                    d: (
                        "center_not_covered"
                        if d == "C"
                        else "other_six_not_assigned_under_this_source"
                    )
                    for d in _facts()["fixed_earth_numbers"]
                    if d not in {a["direction"] for a in axes.values()}
                },
            }
        )
    return {
        "ruleset": provenance(),
        "status": "computed_relations" if charts else "no_computed_chart",
        "candidates": candidates,
        "scope": SCOPE,
        "evaluation_timeliness_applied": False,
        "site_eligibility_established": False,
        "overall_auspiciousness": "not_produced",
    }


def validate(
    interpretation: dict[str, Any],
    natal: dict[str, Any],
    *,
    expected_selected: bool | None = None,
) -> dict[str, int]:
    """Verify from literal element table and raw planes, not the relation builder."""
    counts = dict(
        relations=0, source_matches=0, source_differences=0, source_ambiguous=0
    )
    value = interpretation.get("host_guest_analysis")
    if expected_selected is False:
        _check(value is None)
    if value is None:
        _check(expected_selected is not True)
        return counts
    try:
        data = _facts()
        _check(_same(value["ruleset"], provenance()))
        _check(value["scope"] == SCOPE)
        _check(value["evaluation_timeliness_applied"] is False)
        _check(value["site_eligibility_established"] is False)
        _check(value["overall_auspiciousness"] == "not_produced")
        charts = _charts(natal)
        _check(
            value["status"] == ("computed_relations" if charts else "no_computed_chart")
        )
        _check(len(value["candidates"]) == len(charts))
        for item, chart in zip(value["candidates"], charts):
            _check(chart["chart_mode"] in {"lower", "replacement"})
            circle = "壬子癸丑艮寅甲卯乙辰巽巳丙午丁未坤申庚酉辛戌乾亥"
            for axis in ("sitting", "facing"):
                name = chart[axis]["name"]
                _check(type(name) is str and len(name) == 1 and name in circle)
            _check(
                circle[(circle.index(chart["facing"]["name"]) + 12) % 24]
                == chart["sitting"]["name"]
            )
            for key, expected in {
                "candidate_id": chart["candidate_id"],
                "natal_period_number": chart["period_number"],
                "chart_mode": chart["chart_mode"],
                "candidate_only": len(charts) > 1,
            }.items():
                _check(_same(item[key], expected))
            _check(set(item["axes"]) == {"sitting", "facing"})
            used = set()
            for axis in ("sitting", "facing"):
                direction = next(
                    d
                    for d, names in data["sector_mountains"].items()
                    if chart[axis]["name"] in names
                )
                _check(chart[axis]["direction"] == direction)
                used.add(direction)
                active = "mountain" if axis == "sitting" else "facing"
                other = "facing" if axis == "sitting" else "mountain"
                a = item["axes"][axis]
                _check(a["direction"] == direction and a["active_role"] == active)
                _check(len(a["relations"]) == 4)
                raw = {"earth": data["fixed_earth_numbers"][direction]}
                for role in ("period", "mountain", "facing"):
                    n = chart[role + "_chart"][direction]
                    _number(n)
                    _check(
                        type(chart["palaces"][direction][role + "_star_number"]) is int
                    )
                    _check(chart["palaces"][direction][role + "_star_number"] == n)
                    raw[role] = n
                hosts = ("earth", "period", "period", active)
                guests = ("period", "mountain", "facing", other)
                for i, record in enumerate(a["relations"]):
                    _check(
                        record["kind"] == KINDS[i] and record["direction"] == direction
                    )
                    for side, role in (("host", hosts[i]), ("guest", guests[i])):
                        expected = {
                            "role": role,
                            "number": raw[role],
                            "element": data["star_elements"][str(raw[role])],
                        }
                        _check(_same(record[side], expected))
                    label = data["host_guest_matrix"][record["host"]["element"]][
                        record["guest"]["element"]
                    ]
                    _check(
                        record["label"] == label
                        and record["operation"] == RELATIONS[label]
                    )
                    _check(record["rule_id"] == "shen_2011_host_guest_v1.operation")
                    _check(record["source_ids"] == ["HGT1", "HGT2", "HGT3", "HGT4"])
                    counts["relations"] += 1
                comparison = a["literal_clause_comparison"]
                _check(
                    comparison["comparison_basis"] == "axis_pair_as_defined_p453_p910"
                )
                _check(comparison["basis_determined_from_clause_alone"] is False)
                _check(comparison["source_angle_applicability_verified"] is False)
                _check(
                    comparison["scope"]
                    == "literal_lower_clause_operation_words_not_fortune_verdict"
                )
                if chart["chart_mode"] == "lower":
                    source = next(
                        row
                        for row in data["lower_clauses"]
                        if row["period"] == chart["period_number"]
                        and row["sitting_mountain"] == chart["sitting"]["name"]
                        and row["facing_mountain"] == chart["facing"]["name"]
                    )
                    labels = source["labels"]["山" if axis == "sitting" else "向"]
                    match = (
                        None
                        if len(labels) != 1
                        else labels[0] == a["relations"][-1]["label"]
                    )
                    status = (
                        "source_ambiguous"
                        if match is None
                        else "matches" if match else "differs"
                    )
                    _check(
                        comparison["status"] == status
                        and comparison["matched"] is match
                    )
                    _check(comparison["literal_labels"] == labels)
                    _check(
                        comparison["literal_full_clause"]
                        == source["literal_full_clause"]
                    )
                    _check(
                        type(comparison["pdf_page"]) is int
                        and comparison["pdf_page"] == source["page"]
                    )
                    counts[
                        {
                            "matches": "source_matches",
                            "differs": "source_differences",
                            "source_ambiguous": "source_ambiguous",
                        }[status]
                    ] += 1
                else:
                    _check(comparison["status"] == "not_applicable_lower_chart_corpus")
                    _check(comparison["matched"] is None)
            unassigned = {
                d: (
                    "center_not_covered"
                    if d == "C"
                    else "other_six_not_assigned_under_this_source"
                )
                for d in data["fixed_earth_numbers"]
                if d not in used
            }
            _check(_same(item["unassigned_palaces"], unassigned))
        return counts
    except (
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        AttributeError,
        StopIteration,
    ) as error:
        raise FengshuiCalculationError("natal_host_guest_inconsistent") from error


def statements(value: dict[str, Any]) -> list[tuple[str, str, str]]:
    """Render only the already returned values; never recalculate a relation."""
    names = {"earth": "地盘", "period": "运盘", "mountain": "山盘", "facing": "向盘"}
    result = []
    for ci, candidate in enumerate(value["candidates"]):
        qualifier = "（宅盘待确认候选）" if candidate["candidate_only"] else ""
        for axis, a in candidate["axes"].items():
            title = "坐山宫" if axis == "sitting" else "向首宫"
            for i, record in enumerate(a["relations"]):
                h, g = record["host"], record["guest"]
                text = f"{candidate['candidate_id']}{qualifier}，历史{candidate['natal_period_number']}运，{title}{a['direction']}：{names[h['role']]}数{h['number']}（{h['element']}）为主，{names[g['role']]}数{g['number']}（{g['element']}）为客，出入关系为{record['label']}。这是主客五行名称，不是评价时令、现场取用或现实吉凶。"
                result.append(
                    (
                        "host_guest_relation",
                        f"candidates.{ci}.axes.{axis}.relations.{i}",
                        text,
                    )
                )
            comparison = a["literal_clause_comparison"]
            status = comparison["status"]
            if status == "not_applicable_lower_chart_corpus":
                text = "本候选为替卦，不拿下卦关系词给它授予来源吻合。"
            elif status == "source_ambiguous":
                text = f"原书PDF{comparison['pdf_page']}该角色关系词为{comparison['literal_labels']}，出现缺项或重复主体，保留未解，不补字。"
            else:
                text = f"原书PDF{comparison['pdf_page']}该角色关系词为{comparison['literal_labels']}，与本次山向二星主客比较{'相合' if comparison['matched'] else '不同，保留差异'}；原按另记与运盘比较的口径，不任意改换基准配平，也不预断原文为笔误。"
            result.append(
                (
                    "host_guest_source_comparison",
                    f"candidates.{ci}.axes.{axis}.literal_clause_comparison",
                    f"{candidate['candidate_id']}{qualifier}，{title}{a['direction']}：{text}",
                )
            )
    return result
