"""Separate main-text weekday tables from apparatus-derived readings.

The lower text's 月與宿合 is a documentary name lookup here. No observed lunar
conjunction, historical daybreak or default Ming reading is inferred.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, Sequence

from fatebridge.core.sukuyo_documentary import clock_position_reference
from fatebridge.core.sukuyo_printed_special import (
    KYOTO_ENPO_SOURCE,
    ntu_yongle_comparisons,
    printed_lower_comparison,
)
from fatebridge.core.sukuyo_sources import load_source

SOURCE = Path(__file__).resolve().parents[1] / "data/sukuyo_t1299_special_days.json"
MANSIONS = frozenset("角亢氐房心尾箕斗女虚危室壁奎娄胃昴毕觜参井鬼柳星张翼轸")


def source_bundle() -> dict[str, Any]:
    return load_source(SOURCE).data


def source_digest() -> str:
    return load_source(SOURCE).sha256


def scope_for_weekday_basis(scope: str, weekday_basis: str) -> str:
    """Bind the legacy metadata's date label, never alter a source quotation."""
    zones = {
        "modern_utc_plus08_civil_midnight": "UTC+08",
        "modern_utc_plus09_civil_midnight": "UTC+09",
    }
    if weekday_basis not in zones:
        raise ValueError("特殊日须明确已支持的UTC+08或UTC+09民用七曜依据")
    marker = "现代UTC+08历日"
    if scope.count(marker) != 1:
        raise ValueError("特殊日说明的宿主日界占位已改变，须重新核验")
    return scope.replace(marker, f"现代{zones[weekday_basis]}历日")


def special_day_evidence(
    mansion: Optional[str],
    weekday: int,
    candidates: Sequence[str] = (),
    *,
    weekday_basis: str,
) -> dict[str, Any]:
    if type(weekday) is not int or not 0 <= weekday <= 6:
        raise ValueError("七曜索引须为日曜零起的0至6整数")
    if weekday_basis not in {
        "modern_utc_plus08_civil_midnight",
        "modern_utc_plus09_civil_midnight",
    }:
        raise ValueError("特殊日须明确已支持的UTC+08或UTC+09民用七曜依据")
    if (mansion is not None and mansion not in MANSIONS) or any(
        name not in MANSIONS for name in candidates
    ):
        raise ValueError("特殊日查表只支持27宿（不含牛）")
    bundle = source_bundle()

    def evaluate(witness: dict[str, Any], name: Optional[str]) -> dict[str, Any]:
        rows = [r for r in witness["rows"] if r["weekday_index"] == weekday]
        matched = [r for r in rows if name is not None and r["mansion"] == name]
        unresolved = [r for r in rows if r["mansion"] is None]
        return {
            "witness": witness["id"],
            "volume": witness["volume"],
            "edition": witness["edition"],
            "matched_labels": [r["label"] for r in matched],
            "matched_rows": deepcopy(matched),
            "rows_for_weekday": deepcopy(rows),
            "unresolved_rows": deepcopy(unresolved),
            "labels_complete_for_selected_day": name is not None and not unresolved,
            "applied_to_primary": witness["applied_to_primary"] and name is not None,
        }

    selected = next(
        w for w in bundle["witnesses"] if w["id"] == bundle["selected_primary"]
    )
    primary = evaluate(selected, mansion)
    comparisons = []
    for witness in bundle["witnesses"]:
        if witness["id"] == selected["id"]:
            continue
        result = evaluate(witness, mansion)
        result["disagrees_with_primary"] = (
            result["matched_labels"] != primary["matched_labels"]
            if result["labels_complete_for_selected_day"]
            else None
        )
        comparisons.append(result)
    return {
        "ruleset_id": bundle["id"],
        "status": "named_day_comparison" if mansion else "candidate_only",
        "mansion": mansion,
        "weekday_index": weekday,
        "primary": primary,
        "comparisons": comparisons,
        "direct_printed_comparisons": [
            printed_lower_comparison(mansion, weekday, primary["matched_labels"]),
            printed_lower_comparison(
                mansion,
                weekday,
                primary["matched_labels"],
                source_path=KYOTO_ENPO_SOURCE,
            ),
            *ntu_yongle_comparisons(mansion, weekday, primary["matched_labels"]),
        ],
        "candidate_primary": (
            [
                {
                    "mansion": name,
                    "matched_labels": evaluate(selected, name)["matched_labels"],
                    "applied_to_primary": False,
                }
                for name in dict.fromkeys(candidates)
            ]
            if mansion is None
            else []
        ),
        "source_url": bundle["source_url"],
        "source_sha256": bundle["source_sha256"],
        "source_bundle_sha256": source_digest(),
        "textual_position_reference": clock_position_reference(),
        "selected_primary": bundle["selected_primary"],
        "selected_lower_activity_witness": bundle["selected_lower_activity_witness"],
        "weekday_basis": weekday_basis,
        "physical_lunar_conjunction_evaluated": False,
        "classical_daybreak_boundary_acceptance": False,
        "scope": scope_for_weekday_basis(bundle["scope"], weekday_basis),
    }
