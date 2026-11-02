"""Selected documentary comparisons; no calendar or clock policy is inferred."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Sequence

from fatebridge.core.sukuyo_kyoto_enpo import kyoto_enpo_clock_reference
from fatebridge.core.sukuyo_printed_special import NTU_YONGLE_SOURCE
from fatebridge.core.sukuyo_sources import load_source

DATA = Path(__file__).resolve().parents[1] / "data"
LAYERS = DATA / "sukuyo_selected_text_layers.json"
JAPANESE = DATA / "sukuyo_japanese_selected_calendar.json"
CLOCK_POSITION = DATA / "sukuyo_t1299_clock_transposition.json"


def with_text_layers(rule: dict[str, Any]) -> dict[str, Any]:
    """Attach publisher placement to a detached rule, retaining paired passages."""
    result = deepcopy(rule)
    source = load_source(LAYERS)
    identifiers = source.data["rule_passages"].get(rule["rule_id"])
    if identifiers:
        result["source_passages"] = [
            deepcopy(source.data["passages"][identifier]) for identifier in identifiers
        ]
        result["source_layer_bundle_sha256"] = source.sha256
    return result


def japanese_calendar_comparison(
    day: int,
    classifications: Sequence[dict[str, Any]],
    *,
    primary_reference: dict[str, Any],
) -> dict[str, Any]:
    """Compare membership in this body clause, never infer an unlisted taboo."""
    if type(day) is not int or not 1 <= day <= 30:
        raise ValueError("文献对照入月日须为1至30的整数")
    source = load_source(JAPANESE)
    result = deepcopy(source.data)
    listed = day in result["selected_body_day_sequence"]["lunar_days"]
    body_days = set(result["selected_body_day_sequence"]["lunar_days"])
    result.update(
        source_bundle_sha256=source.sha256,
        current_lunar_day=day,
        current_body_list_membership="listed_favorable" if listed else "unlisted",
        primary_general_day_reference=deepcopy(primary_reference),
        full_favorable_membership_comparison=[
            {
                "witness": row["witness"],
                "primary_favorable_lunar_days": list(row["favorable_lunar_days"]),
                "body_favorable_lunar_days": sorted(body_days),
                "primary_only_days": sorted(
                    set(row["favorable_lunar_days"]) - body_days
                ),
                "body_only_days": sorted(body_days - set(row["favorable_lunar_days"])),
                "symmetric_difference_days": sorted(
                    set(row["favorable_lunar_days"]) ^ body_days
                ),
                "applied_to_primary_or_activities": False,
            }
            for row in primary_reference["witnesses"]
        ],
        primary_general_day_comparison=[
            {
                "witness": row["witness"],
                "primary_assessment": row["assessment"],
                "favorable_list_membership_differs": listed
                != (row["assessment"] == "favorable"),
            }
            for row in classifications
        ],
    )
    return result


def text_placement_label(rule: dict[str, Any]) -> str:
    """Describe layout, without assigning note authorship or textual priority."""
    passages = rule.get("source_passages", [])
    if not passages:
        return ""
    if rule["layer"] == "travel_direction":
        if rule.get("auspicious_time_cannot_release"):
            return "主文列禁行方向，‘纵吉时亦不可行’在行内注"
        label = "主文列宫名，取宿及行向说明在行内注"
        if (
            rule.get("direction_binding_basis")
            == "following_已上_clause_for_paired_rows"
        ):
            return label + "；连属的‘已上’段一并保留"
        return label
    return "所选条文在主文，未混入行内注"


def clock_position_reference() -> dict[str, Any]:
    """One reciprocal apparatus operation, never a new clock or table policy."""
    source = load_source(CLOCK_POSITION)
    ntu = load_source(NTU_YONGLE_SOURCE)
    return {
        **source.data,
        "source_bundle_sha256": source.sha256,
        "direct_japanese_print_reference": kyoto_enpo_clock_reference(),
        "direct_chinese_print_reference": {
            "witness": "ntu_yongle130_selected",
            "source_reference": ntu.data["source_reference"],
            "source_bundle_sha256": ntu.sha256,
            **ntu.data["clock_reference"],
        },
    }
