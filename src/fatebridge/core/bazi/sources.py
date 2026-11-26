"""Literal classical-source index comparison for compare_bazi_sources (loaded on demand)."""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

from fatebridge.utils.data import EARTHLY_BRANCHES, HEAVENLY_STEMS

ORDER = ("year", "month", "day", "hour")
GRADES = {"强", "中和", "弱"}


@lru_cache(maxsize=1)
def _load_annotations_index() -> (
    tuple[dict[tuple[str, ...], list[dict[str, Any]]], dict[str, Any]]
):
    path = (
        Path(__file__).resolve().parents[2]
        / "data/reference/bazi-source-annotations.json"
    )
    data = json.loads(path.read_bytes())
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = {}
    records_by_id = {r["reference_id"]: r for r in data["records"]}
    for constraint in data["strength_constraints"]:
        records_by_id[constraint["reference_id"]].setdefault(
            "bounded_strength_constraints", []
        ).append(constraint)
    for record in data["records"]:
        grouped.setdefault(tuple(record["pillars"]), []).append(record)
    metadata = {
        "method_id": data["method_id"],
        "total_registered_records": data["record_count"],
        "total_registered_literal_inputs": data["literal_input_count"],
        "total_registered_strength_constraints": len(data["strength_constraints"]),
    }
    return grouped, metadata


def pillar_values(payload: Mapping[str, Any]) -> list[str]:
    if "pillars" in payload and isinstance(payload["pillars"], list):
        return [str(p) for p in payload["pillars"]]
    return [str(payload[f"{p}_pillar"]) for p in ORDER]


def input_consistency(values: list[str]) -> dict[str, Any]:
    return {
        "pillars": values,
        "valid_sexagenary_characters": all(
            len(v) == 2 and v[0] in HEAVENLY_STEMS and v[1] in EARTHLY_BRANCHES
            for v in values
        ),
    }


def compare_registered_annotations(
    pillars: Mapping[str, tuple[str, str]], computed_strength: str | None
) -> dict[str, Any]:
    index, metadata = _load_annotations_index()
    key = tuple("".join(pillars[p]) for p in ORDER)
    rows = deepcopy(index.get(key, []))
    expected = {r["retained_strength_annotation"] for r in rows} - {None}
    known = [r for r in rows if r["retained_strength_annotation"] is not None]
    for row in rows:
        grade = row["retained_strength_annotation"]
        row["comparison"] = (
            "unadjudicated"
            if grade is None
            else (
                "current_grade_missing"
                if computed_strength is None
                else "agrees" if grade == computed_strength else "differs"
            )
        )
    if not rows:
        status = "no_registered_literal_case"
    elif len(expected) > 1:
        status = "conflicting_registered_annotations"
    elif not known:
        status = "unadjudicated_records_only"
    elif computed_strength is None:
        status = "current_grade_missing"
    elif any(r["comparison"] == "differs" for r in rows):
        status = "known_annotation_mismatch"
    else:
        status = "agrees_with_known_annotations"

    return {
        "status": status,
        "computed_strength": computed_strength,
        "literal_match_count": len(rows),
        "known_annotation_count": len(known),
        "unknown_or_unannotated_count": len(rows) - len(known),
        "agreeing_known_count": sum(r["comparison"] == "agrees" for r in rows),
        "differing_known_count": sum(r["comparison"] == "differs" for r in rows),
        "retained_expected_strengths": sorted(expected),
        "records": rows,
        "reference_index": metadata,
        "calculation_overridden": False,
    }
