"""Separate an uncollated candidate table, selected source layers and actual stem positions.

Developer collations cover the Jia selections, Bing unit, selected passages for all Ding months, and
selected Wu/Yi passages and selected Ji passages for all twelve months.
The chart-conditioned 用神 decisions remain open.
Printed outlines, body conditions and commentator layers remain distinct.
"""

from __future__ import annotations

import json
from copy import deepcopy
from functools import lru_cache
from importlib.resources import files
from typing import Any, Mapping

from fatebridge.utils.data import BRANCH_HIDDEN_STEMS

_SOURCE_PROFILES = {
    "甲": ("jia", "selected_jia_passages_not_full_acceptance"),
    "丙": ("bing", "bing_unit_developer_collation_not_full_acceptance"),
    "丁": ("ding", "selected_ding_spring_passages_not_full_acceptance"),
    "戊": ("wu_you", "selected_wu_yi_passages_not_full_acceptance"),
    "乙": ("yi_zi", "selected_wu_yi_passages_not_full_acceptance"),
    "己": ("ji_spring", "selected_ji_spring_passages_not_full_acceptance"),
}


@lru_cache(maxsize=len(_SOURCE_PROFILES))
def _source_profile(day_stem: str) -> dict[str, Any]:
    name, _ = _SOURCE_PROFILES[day_stem]
    profile: dict[str, Any] = json.loads(
        files("fatebridge.data")
        .joinpath(f"bazi_seasonal_qiongtong_{name}_v1.json")
        .read_text(encoding="utf-8")
    )
    for group in profile.get("month_groups", ()):
        branches = group["branches"]
        layers = group["layers"]
        summaries = group.get("summaries_by_branch")
        profile["months"].update(
            {branch: {**layers, "summary": summaries[branch]} for branch in branches}
            if summaries is not None
            else dict.fromkeys(branches, layers)
        )
        profile["month_sources"].update(
            dict.fromkeys(branches, group["source_context"])
        )
    if day_stem == "丙":
        profile["input_witness_notes"] = json.loads(
            files("fatebridge.data")
            .joinpath("bazi_seasonal_qiongtong_bing_input_notes_v1.json")
            .read_text(encoding="utf-8")
        )
    return profile


def seasonal_reference_layers(
    day_stem: str,
    month_branch: str,
    lookup: dict[str, Any],
    pillars: Mapping[str, tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Keep unadjudicated candidates separate from source-supported choices."""
    result = {
        **lookup,
        "method_id": "seasonal_reference_layers_v2",
        "lookup_scope": "日干与月支的未校勘简表候选；不是全盘最终用神",
        "chart_adjudication_status": "not_performed",
        "source_review_status": "source_not_collated",
    }
    candidates = {lookup["primary"], *lookup["secondary"]} - {None}
    profile = _source_profile(day_stem) if day_stem in _SOURCE_PROFILES else None
    if profile is not None and month_branch in profile["months"]:
        layers = deepcopy(profile["months"][month_branch])
        if "general_fire_context" in profile:
            layers["general_fire_context"] = deepcopy(profile["general_fire_context"])
        if "input_witness_notes" in profile:
            witness = profile["input_witness_notes"]
            matching = [
                n for n in witness["notes"] if n["month_branch"] == month_branch
            ]
            if matching:
                layers["input_witness_notes"] = {
                    **{k: deepcopy(v) for k, v in witness.items() if k != "notes"},
                    "notes": deepcopy(matching),
                }
        source_context = profile.get("month_sources", {}).get(month_branch, profile)
        result.update(
            source_review_status=source_context.get(
                "source_review_status", _SOURCE_PROFILES[day_stem][1]
            ),
            source_ref=deepcopy(source_context["source"]),
            source_layers=layers,
            source_scope=source_context["scope"],
        )
        candidates.update(layers["body"]["stem_sequence"])
        candidates.update(layers["body"].get("condition_stems", []))
    if pillars is not None:
        result["stem_observations"] = [
            {
                "stem": stem,
                "visible_positions": [
                    p for p in ("year", "month", "day", "hour") if pillars[p][0] == stem
                ],
                "hidden_positions": [
                    {"pillar": p, "branch": pillars[p][1], "hidden_rank": rank}
                    for p in ("year", "month", "day", "hour")
                    for rank, hidden in enumerate(BRANCH_HIDDEN_STEMS[pillars[p][1]])
                    if hidden == stem
                ],
            }
            for stem in "甲乙丙丁戊己庚辛壬癸"
            if stem in candidates
        ]
        result["observation_scope"] = (
            "只核对本次四柱的干见与支藏，含日干时保留实际位置；"
            "有字不等于得用，不裁定力量、合化或半月分界。"
        )
    return result
